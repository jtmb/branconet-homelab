#!/usr/bin/python3
"""Run the staged independent Pi-hole on the worker."""
import configparser
import fcntl
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time

LOOPBACK_NAME = "branconet-independent-dns-loopback"
LAN_NAME = "branconet-independent-dns-lan"
LAN_ADDRESS = "192.168.0.5"
LAN_INTERFACE = "enp3s0"
FIREWALL_TABLE = "branconet_independent_dns"
FIREWALL_OWNER = "branconet independent dns lan v1"
FIREWALL_RULES = Path("/etc/branconet-independent-dns-lan.nft")
LABEL = "io.branconet.purpose"
IMAGE = "docker.io/pihole/pihole@sha256:d34134716fc32038b052a8674c7c6879e0ff21f0e6d8af345166fffa2c27c113"
STATE = Path("/var/lib/branconet-independent-dns")
CTR = ["/opt/containerd-k8s/bin/ctr", "--address", "/run/containerd-k8s/containerd.sock", "--namespace", "k8s.io"]
MAX_POLICY_BYTES = 128 * 1024**2


def run(*args):
    return subprocess.check_output(args, text=True, timeout=8)


def private_file(path, limit):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077
            or info.st_nlink != 1 or not 0 < info.st_size <= limit):
        raise ValueError(f"Unsafe staged resolver file: {path.name}")


def verify_loopback(config):
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read_string(config)
    expected = {
        "dns": {"port": 10554, "listeningMode": "BIND", "interface": "lo", "queryLogging": False},
        "dns.blocking": {"active": True, "mode": "NULL"},
        "webserver": {"port": ""}, "database": {"DBimport": False, "maxDBdays": 0},
        "ntp.sync": {"active": False}, "ntp.ipv4": {"active": False}, "ntp.ipv6": {"active": False},
    }
    if set(parser.sections()) != set(expected) or parser.defaults():
        raise ValueError("The staged FTL configuration has unqualified sections.")
    for section, settings in expected.items():
        parsed = {key: json.loads(value) for key, value in parser[section].items()}
        if section == "dns":
            records = {key: parsed.pop(key) for key in ("upstreams", "hosts", "cnameRecords")}
            if any(not isinstance(value, list) or not value for value in records.values()):
                raise ValueError("The staged DNS addresses or local records are missing.")
        if parsed != settings:
            raise ValueError("The staged FTL settings do not match the isolated loopback profile.")
    if int(Path("/proc/sys/net/ipv4/ip_unprivileged_port_start").read_text()) < 1024:
        raise ValueError("The host permits unprivileged processes to bind protected ports.")


def lan_config(config):
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read_string(config)
    parser["dns"]["listeningMode"] = json.dumps("NONE")
    parser["dns"]["interface"] = json.dumps("")
    parser["misc"] = {"dnsmasq_lines": json.dumps(["bind-interfaces", f"listen-address={LAN_ADDRESS}"])}
    result = StringIO()
    parser.write(result)
    return result.getvalue()


def require_lan_address():
    interfaces = json.loads(run("ip", "-j", "-4", "address", "show", "dev", LAN_INTERFACE))
    if not any(info["local"] == LAN_ADDRESS and info["prefixlen"] == 24
               for interface in interfaces for info in interface.get("addr_info", [])):
        raise ValueError("The qualified LAN address is absent from the worker interface.")


def firewall_handle():
    tables = json.loads(run("nft", "-j", "list", "tables"))["nftables"]
    if not any(item.get("table", {}).get("name") == FIREWALL_TABLE
               and item["table"]["family"] == "ip" for item in tables):
        return None
    # nft 1.0.2 does not include table comments in its JSON output.
    lines = run("nft", "-a", "list", "table", "ip", FIREWALL_TABLE).splitlines()
    prefix = f"table ip {FIREWALL_TABLE} {{ # handle "
    if (len(lines) < 2 or not lines[0].startswith(prefix)
            or lines[1].strip() != f'comment "{FIREWALL_OWNER}"'):
        raise ValueError("An unrelated firewall table uses the independent DNS name.")
    return int(lines[0][len(prefix):])


def firewall_start():
    require_lan_address()
    if firewall_handle() is not None:
        raise ValueError("The independent DNS firewall is already present.")
    private_file(FIREWALL_RULES, 8192)
    run("nft", "-f", str(FIREWALL_RULES))
    if firewall_handle() is None:
        raise ValueError("The independent DNS firewall was not installed.")


def firewall_stop():
    handle = firewall_handle()
    if handle is not None:
        run("nft", "delete", "table", "ip", "handle", str(handle))


def firewall_counters():
    if firewall_handle() is None:
        raise ValueError("The independent DNS firewall is inactive.")
    entries = json.loads(run("nft", "-j", "list", "chain", "ip", FIREWALL_TABLE, "prerouting"))["nftables"]
    counts = {}
    for entry in entries:
        if "rule" not in entry:
            continue
        rule = entry["rule"]
        label = rule.get("comment")
        if label not in {"dns53-tcp", "dns53-udp"} or label in counts:
            raise ValueError("The DNS firewall has an unexpected forwarding rule.")
        counts[label] = next(expr["counter"]["packets"] for expr in rule["expr"] if "counter" in expr)
    if set(counts) != {"dns53-tcp", "dns53-udp"}:
        raise ValueError("The DNS firewall is missing a transport counter.")
    print(json.dumps(counts))


def lan_check():
    for _ in range(10):
        sockets = run("ss", "-H", "-lntu", "sport", "=", ":10554").splitlines()
        bindings = {(line.split()[0], line.split()[4]) for line in sockets}
        allowed = {f"{address}:10554" for address in (LAN_ADDRESS, "127.0.0.1", "[::1]")}
        if any(address not in allowed for _, address in bindings):
            raise ValueError("An unexpected address is listening on the resolver port.")
        if all((protocol, f"{LAN_ADDRESS}:10554") in bindings for protocol in ("tcp", "udp")):
            try:
                for protocol in ("+tcp", "+notcp"):
                    answer = run("dig", f"@{LAN_ADDRESS}", "-p", "10554", "k8s-api.branconet.lan",
                                 "A", "+short", "+time=1", "+tries=1", protocol)
                    if answer.strip() != "192.168.0.251":
                        raise ValueError("The standalone LAN resolver returned an unexpected answer.")
                return
            except (subprocess.SubprocessError, ValueError):
                pass
        time.sleep(1)
    raise ValueError("The standalone LAN resolver did not pass its startup checks.")


def owned(name):
    if name not in run(*CTR, "containers", "ls", "-q").splitlines():
        return False
    info = json.loads(run(*CTR, "containers", "info", name))
    if info.get("Labels", {}).get(LABEL) != name or info.get("Image") != IMAGE:
        raise ValueError("A different container already uses the independent resolver identity.")
    return True


def start(name):
    runtime = Path("/run") / name
    if owned(name):
        raise ValueError("An existing independent resolver container needs reconciliation.")
    if IMAGE not in run(*CTR, "images", "ls", "-q").splitlines():
        raise ValueError("The pinned Pi-hole image is not locally available.")
    if run("findmnt", "-n", "-o", "FSTYPE", "--target", str(runtime)).strip() != "tmpfs":
        raise ValueError("The resolver runtime directory must be RAM-backed.")
    if shutil.disk_usage(runtime).free < MAX_POLICY_BYTES * 2:
        raise ValueError("The resolver runtime does not have enough space.")
    paths = [runtime / folder for folder in ("state", "logs", "run")]
    for path in paths:
        path.mkdir(mode=0o700)
        os.chown(path, 1000, 1000)
    config, gravity = STATE / "pihole.toml", STATE / "gravity.db"
    with (STATE / "refresh.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        private_file(config, 64 * 1024)
        private_file(gravity, MAX_POLICY_BYTES)
        settings = config.read_text()
        verify_loopback(settings)
        if name == LAN_NAME:
            settings = lan_config(settings)
        target_config = paths[0] / config.name
        target_config.write_text(settings)
        target_gravity = paths[0] / gravity.name
        shutil.copyfile(gravity, target_gravity)
        for target in (target_config, target_gravity):
            target.chmod(0o600)
            os.chown(target, 1000, 1000)
    command = CTR + ["run", "--rm", "--read-only", "--seccomp", "--net-host", "--user", "1000:1000",
                     "--cap-drop", "CAP_NET_BIND_SERVICE", "--cap-drop", "CAP_NET_RAW",
                     "--cap-drop", "CAP_NET_ADMIN", "--cpus", "0.5",
                     "--memory-limit", str(256 * 1024**2), "--label", f"{LABEL}={name}"]
    for source, target in zip(paths, ("/etc/pihole", "/var/log/pihole", "/run")):
        command += ["--mount", f"type=bind,src={source},dst={target},options=rbind:rw"]
    command += [IMAGE, name, "/usr/bin/pihole-FTL", "no-daemon"]
    os.execv(command[0], command)


def stop(name):
    if not owned(name):
        return
    if name in run(*CTR, "tasks", "ls", "-q").splitlines():
        run(*CTR, "tasks", "kill", "--signal", "SIGTERM", name)
    for _ in range(50):
        if not owned(name):
            return
        time.sleep(.2)
    raise ValueError("The independent resolver did not stop within its cleanup window.")


if __name__ == "__main__":
    try:
        args = sys.argv[1:]
        if args in (["start"], ["start", "lan"]):
            start(LAN_NAME if len(args) == 2 else LOOPBACK_NAME)
        elif args in (["stop"], ["stop", "lan"]):
            stop(LAN_NAME if len(args) == 2 else LOOPBACK_NAME)
        elif args == ["lan-check"]:
            lan_check()
        elif args == ["firewall-counters"]:
            firewall_counters()
        elif args == ["firewall-start"]:
            firewall_start()
        elif args == ["lan-cleanup"]:
            stop(LAN_NAME)
            firewall_stop()
        elif args == ["firewall-stop"]:
            firewall_stop()
        else:
            raise ValueError("Use start or stop with optional lan profile, or manage the LAN firewall.")
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        print(str(error) if isinstance(error, ValueError) else "The standalone resolver operation failed.",
              file=sys.stderr)
        sys.exit(1)
