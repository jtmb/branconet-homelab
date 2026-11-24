#!/usr/bin/python3
"""Local, time-limited nftables action for the floating Traefik HTTPS path."""
import argparse
from decimal import Decimal, InvalidOperation
import fcntl
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import stat
import struct
import subprocess
import sys
import time

TABLE = "branconet_traefik_lan"
CHAIN = "pre_dnat"
SET = "blocked_clients"
OWNER = "branconet-traefik-lan-v1"
LAN = ipaddress.IPv4Network("192.168.0.0/24")
PROTECTED = {1, 4, 5, 6, 8, 25, 26, 27, 251, 252, 253, 254}
STATE_PATH = "/api/v1/namespaces/traefik/configmaps/traefik-lan-ban-state"
STATE_KEY = "events-v1.json"
MAX_BANS = 128
MAX_EVENTS = 512
MAX_SECONDS = 900
MICROSECONDS = 1_000_000
API_BYTES = 131072
REQUEST_BYTES = 512
SNAPSHOT_BYTES = 16384
PUBLISHER_UID = 24531
READER_UID = 24532
RULESET = f"""create table inet {TABLE}
add set inet {TABLE} {SET} {{ type ipv4_addr; flags timeout; size 128; }}
add chain inet {TABLE} {CHAIN} {{ type filter hook prerouting priority raw; policy accept; }}
add rule inet {TABLE} {CHAIN} ip saddr @{SET} ip daddr 192.168.0.252 tcp dport 443 counter drop comment "{OWNER}"
"""


def nft(*args, data=None, check=True):
    result = subprocess.run(
        ["/usr/sbin/nft", *args], input=data, capture_output=True, text=True, timeout=5
    )
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or "nftables operation failed")
    return result


def listing(*args):
    result = nft("-j", "list", *args, check=False)
    if not result.returncode:
        return json.loads(result.stdout)["nftables"]
    if "No such file or directory" in result.stderr:
        return []
    raise RuntimeError(result.stderr.strip() or "nftables query failed")


def owned():
    rows = listing("table", "inet", TABLE)
    if not rows:
        return False
    rules = [row["rule"] for row in rows if "rule" in row]
    if len(rules) != 1 or rules[0].get("comment") != OWNER or rules[0].get("chain") != CHAIN:
        raise RuntimeError("The table exists without the expected ownership marker.")
    return True


def checked_address(value):
    address = ipaddress.IPv4Address(value)
    if address not in LAN or address.packed[-1] in PROTECTED | {0, 255}:
        raise ValueError("The address is outside the supported client scope.")
    return str(address)


def start():
    if not owned():
        nft("-f", "-", data=RULESET)


def stop():
    if owned():
        nft("delete", "table", "inet", TABLE)


def change(operation, value, ttl=None):
    address = checked_address(value)
    if operation == "add" and (ttl is None or not 1 <= ttl <= 900):
        raise ValueError("The timeout must be between 1 and 900 seconds.")
    if not owned():
        raise RuntimeError("The owned firewall table is unavailable.")
    if operation == "add":
        nft("add", "element", "inet", TABLE, SET, "{", address, "timeout", f"{ttl}s", "}")
    else:
        result = nft("delete", "element", "inet", TABLE, SET, "{", address, "}", check=False)
        if result.returncode and "No such file or directory" not in result.stderr:
            raise RuntimeError(result.stderr.strip() or "nftables delete failed")


def synchronize(snapshot, *, now=None, create=False):
    if not isinstance(snapshot, dict) or len(snapshot) > MAX_BANS:
        raise ValueError("Expected at most 128 address-to-expiry entries.")
    now = int(time.time()) if now is None else now
    elements = []
    for key, expiry in snapshot.items():
        address = checked_address(key)
        if type(expiry) is not int or expiry > now + 900:
            raise ValueError("Invalid shared ban expiration.")
        if expiry > now:
            elements.append(f"{address} timeout {expiry - now}s")
    if create:
        start()
    elif not owned():
        raise RuntimeError("The owned firewall table is unavailable.")
    transaction = f"flush set inet {TABLE} {SET}\n"
    if elements:
        transaction += f"add element inet {TABLE} {SET} {{ {', '.join(elements)} }}\n"
    nft("-f", "-", data=transaction)


def ticket_time(value):
    try:
        seconds = Decimal(value)
        if not seconds.is_finite() or not 0 < seconds < 10_000_000_000:
            raise ValueError("Invalid Fail2Ban ticket time.")
        return int(seconds * MICROSECONDS)
    except InvalidOperation as error:
        raise ValueError("Invalid Fail2Ban ticket time.") from error


def current_events(encoded, now):
    events = json.loads(encoded)
    if not isinstance(events, dict) or len(events) > MAX_EVENTS:
        raise ValueError("Invalid shared event journal size.")
    current = {}
    for key, entry in events.items():
        address, separator, stamp = key.partition("/")
        if not separator or checked_address(address) != address or not stamp.isascii() or not stamp.isdecimal():
            raise ValueError("Invalid shared event ID.")
        observed = int(stamp)
        if str(observed) != stamp or not 0 < observed <= now:
            raise ValueError("Invalid shared event time.")
        if not isinstance(entry, list) or len(entry) != 2:
            raise ValueError("Invalid shared event.")
        expiry, revoked = entry
        if (type(expiry) is not int or type(revoked) is not bool or
                (expiry == 0 and not revoked) or
                (expiry != 0 and not observed // MICROSECONDS < expiry <= observed // MICROSECONDS + MAX_SECONDS)):
            raise ValueError("Invalid shared event expiry or revocation.")
        if observed + MAX_SECONDS * MICROSECONDS > now:
            current[key] = entry
    return current


def active_bans(events, now):
    latest = {}
    for key, (expiry, revoked) in events.items():
        address, stamp = key.split("/")
        observed = int(stamp)
        if expiry and (address not in latest or latest[address][0] < observed):
            latest[address] = observed, expiry, revoked
    snapshot = {address: expiry for address, (_, expiry, revoked) in latest.items()
                if not revoked and expiry > now // MICROSECONDS}
    if len(snapshot) > MAX_BANS:
        raise ValueError("The shared active ban limit was exceeded.")
    return snapshot


def record_event(events, operation, address, observed, seconds, now):
    address = checked_address(address)
    if not 0 < observed <= now:
        raise ValueError("The ticket time is in the future or invalid.")
    if observed + MAX_SECONDS * MICROSECONDS <= now:
        return False
    key = f"{address}/{observed}"
    previous_expiry, revoked = events.get(key, (0, False))
    if operation == "publish":
        if not 1 <= seconds <= MAX_SECONDS:
            raise ValueError("Invalid shared ban duration.")
        expiry = observed // MICROSECONDS + seconds
        if previous_expiry and previous_expiry != expiry:
            raise ValueError("A retry cannot change the original ban expiry.")
        if not previous_expiry and expiry <= now // MICROSECONDS:
            return False
    else:
        expiry, revoked = previous_expiry, True
    entry = [expiry, revoked]
    if events.get(key) == entry:
        return False
    if key not in events and len(events) == MAX_EVENTS:
        raise ValueError("The shared event journal is full.")
    events[key] = entry
    active_bans(events, now)
    return True


def api_request(args, method, body=None):
    # Read the token again on each call so kubelet token rotation takes effect.
    token = Path(args.token_file).read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token):
        raise RuntimeError("The dedicated Kubernetes API token is missing or malformed.")
    context = ssl.create_default_context(cafile=args.ca_file)
    connection = http.client.HTTPSConnection(args.api_host, args.api_port, timeout=3, context=context)
    try:
        connection.request(method, STATE_PATH, body, {
            "Authorization": "Bearer " + token, "Content-Type": "application/json",
        })
        response = connection.getresponse()
        if method == "PUT" and response.status == 409:
            return None
        if response.status != 200:
            raise RuntimeError(f"Shared ban state {method} failed with HTTP {response.status}.")
        raw = response.read(API_BYTES + 1)
        if len(raw) > API_BYTES:
            raise ValueError("The shared API response exceeds its size limit.")
        return json.loads(raw)
    finally:
        connection.close()


def shared(args):
    for _ in range(4):
        obj = api_request(args, "GET")
        now = time.time_ns() // 1000
        data = obj.get("data", {})
        events = current_events(data.get(STATE_KEY, "{}"), now)
        if args.command == "read-shared":
            return active_bans(events, now)
        if not record_event(events, args.command, args.address, args.observed, args.seconds, now):
            return
        data[STATE_KEY] = json.dumps(events, separators=(",", ":"), sort_keys=True)
        if not obj["metadata"]["resourceVersion"]:
            raise ValueError("The API returned no resource version.")
        obj["data"] = data
        if api_request(args, "PUT", json.dumps(obj)) is not None:
            return
    raise RuntimeError("The shared ban record was modified during all four update attempts.")


def peer_uid(connection):
    credentials = struct.Struct("iII")
    peer = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, credentials.size)
    return credentials.unpack(peer)[1]


def receive(connection, limit):
    with connection.makefile("rb") as stream:
        packet = stream.readline(limit + 1)
    if len(packet) > limit or not packet.endswith(b"\n"):
        raise ValueError("Invalid local ban bridge message length.")
    return json.loads(packet)


def send(connection, value):
    connection.sendall(json.dumps(value, separators=(",", ":")).encode("ascii") + b"\n")


def bridge_request(args, request):
    if args.command == "serve-reader" and request == {"command": "read-shared"}:
        return shared(argparse.Namespace(**(vars(args) | request)))
    if args.command == "serve-publisher" and isinstance(request, dict):
        command = request.get("command")
        if command in ("publish", "revoke") and set(request) == {"command", "address", "observed", "seconds"}:
            seconds = request["seconds"]
            if (isinstance(request["address"], str) and type(request["observed"]) is int and
                    (type(seconds) is int if command == "publish" else seconds is None)):
                shared(argparse.Namespace(**(vars(args) | request)))
                return {"accepted": True}
    raise ValueError("The bridge role does not permit this request.")


def serve(args):
    path = Path(args.socket)
    os.umask(0o077)
    flags = os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC
    with os.fdopen(os.open(path.with_suffix(".lock"), flags, 0o600), "r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            previous = path.lstat()
        except FileNotFoundError:
            pass
        else:
            if not stat.S_ISSOCK(previous.st_mode) or previous.st_uid != os.geteuid():
                raise RuntimeError("Refusing to replace a socket path with unexpected ownership.")
            path.unlink()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(path))
            try:
                path.chmod(0o660)
                listener.listen(8)
                while True:
                    connection, _ = listener.accept()
                    with connection:
                        connection.settimeout(2)
                        if peer_uid(connection) != 0:
                            continue
                        try:
                            request = receive(connection, REQUEST_BYTES)
                            result = bridge_request(args, request)
                            send(connection, {"result": result})
                        except (OSError, ValueError, KeyError, TypeError, RuntimeError, http.client.HTTPException) as error:
                            print(f"Ban bridge request failed ({type(error).__name__}).", file=sys.stderr, flush=True)
                            try:
                                send(connection, {"error": "Ban bridge request failed."})
                            except OSError:
                                pass
            finally:
                path.unlink(missing_ok=True)


def local_request(path, uid, request):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(28 if uid == PUBLISHER_UID else 5)
        connection.connect(path)
        if peer_uid(connection) != uid:
            raise PermissionError("The ban bridge socket has an unexpected peer identity.")
        send(connection, request)
        response = receive(connection, SNAPSHOT_BYTES)
        if not isinstance(response, dict) or set(response) != {"result"}:
            raise RuntimeError("The ban bridge did not accept the request.")
        return response["result"]


def api_options(command):
    command.add_argument("--api-host", required=True)
    command.add_argument("--api-port", type=int, default=6443)
    command.add_argument("--token-file", required=True)
    command.add_argument("--ca-file", required=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    cmds = parser.add_subparsers(dest="command", required=True)
    for name in ("start", "check", "stop", "sync"):
        cmds.add_parser(name)
    ban = cmds.add_parser("ban")
    ban.add_argument("address")
    ban.add_argument("seconds", type=int)
    unban = cmds.add_parser("unban")
    unban.add_argument("address")
    for name in ("read-shared", "publish", "revoke"):
        command = cmds.add_parser(name)
        api_options(command)
        if name != "read-shared":
            command.add_argument("address")
            command.add_argument("observed", type=ticket_time)
        if name == "publish":
            command.add_argument("seconds", type=int)
        else:
            command.set_defaults(seconds=None)
    for name in ("serve-publisher", "serve-reader", "send-publish", "send-revoke", "sync-shared"):
        command = cmds.add_parser(name)
        command.add_argument("--socket", required=True)
        if name.startswith("serve-"):
            api_options(command)
        if name.startswith("send-"):
            command.add_argument("address")
            command.add_argument("observed", type=ticket_time)
        if name == "send-publish":
            command.add_argument("seconds", type=int)
        else:
            command.set_defaults(seconds=None)
    args = parser.parse_args()
    if args.command == "start":
        start()
    elif args.command == "check":
        if not owned():
            raise SystemExit("The owned firewall table is unavailable.")
    elif args.command == "stop":
        stop()
    elif args.command == "sync":
        raw = sys.stdin.buffer.read(SNAPSHOT_BYTES + 1)
        if len(raw) > SNAPSHOT_BYTES:
            raise ValueError("The shared ban snapshot exceeds the input limit.")
        synchronize(json.loads(raw))
    elif args.command == "ban":
        change("add", args.address, args.seconds)
    elif args.command == "unban":
        change("delete", args.address)
    elif args.command.startswith("serve-"):
        serve(args)
    elif args.command.startswith("send-"):
        request = {"command": args.command.removeprefix("send-"), "address": args.address,
                   "observed": args.observed, "seconds": args.seconds}
        if local_request(args.socket, PUBLISHER_UID, request) != {"accepted": True}:
            raise RuntimeError("Unexpected reply from the publisher.")
    elif args.command == "sync-shared":
        synchronize(local_request(args.socket, READER_UID, {"command": "read-shared"}), create=True)
    elif args.command == "read-shared":
        print(json.dumps(shared(args)))
    else:
        shared(args)


if __name__ == "__main__":
    main()
