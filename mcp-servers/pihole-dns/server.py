"""Read-only MCP tools for the Branconet Pi-hole deployment."""
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import stat
import struct
import sys
from contextlib import closing, contextmanager

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "_shared"))
import dual_era  # noqa: E402  (stdlib-only adapter for MCP 2026-07-28)

HOST = "pi.branconet.lan"
HTTPS_IP = "192.168.0.252"
DNS_IP = "192.168.0.253"
VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
TIMEOUT = 3
MAX_BODY = 65536


class PiHoleError(Exception):
    pass


class PrivateHTTPS(http.client.HTTPSConnection):
    def connect(self):
        with socket.create_connection((HTTPS_IP, 443), self.timeout) as raw:
            self.sock = self._context.wrap_socket(raw, server_hostname=HOST)


def request(method, path, *, body=None, sid=None):
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(body).encode()
    if sid:
        headers["X-FTL-SID"] = sid
    context = ssl.create_default_context(cafile=str(HERE / "lan-root-ca.pem"))
    with closing(PrivateHTTPS(HOST, timeout=TIMEOUT, context=context)) as conn:
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        if response.status == 204:
            return {}
        if response.status != 200:
            raise PiHoleError(f"Pi-hole returned HTTP {response.status}.")
        data = response.read(MAX_BODY + 1)
        if len(data) > MAX_BODY:
            raise PiHoleError("Pi-hole response exceeded the size limit.")
        return json.loads(data)


def app_password():
    path = HERE / ".env"
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as env:
        info = os.fstat(env.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_nlink != 1):
            raise PiHoleError("The local .env must be a private file owned by you.")
        contents = env.read(8193)
    if len(contents) > 8192:
        raise PiHoleError("The local .env is too large.")
    lines = [line for line in contents.decode().splitlines() if line and not line.startswith("#")]
    if len(lines) != 1 or not lines[0].startswith("PIHOLE_APP_PASSWORD="):
        raise PiHoleError("Set only PIHOLE_APP_PASSWORD in the local .env.")
    value = lines[0].split("=", 1)[1]
    if not value or len(value) > 256:
        raise PiHoleError("The existing Pi-hole application password is needed in .env.")
    return value


@contextmanager
def session():
    auth = request("POST", "/api/auth", body={"password": app_password()})["session"]
    sid = auth.get("sid")
    if auth.get("valid") is not True or not isinstance(sid, str) or not sid:
        raise PiHoleError("Pi-hole did not establish an API session.")
    try:
        yield sid
    finally:
        request("DELETE", "/api/auth", sid=sid)


def read_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise PiHoleError("Incomplete DNS reply.")
        data.extend(chunk)
    return data


def end_name(packet, offset):
    while offset < len(packet):
        size = packet[offset]
        if size == 0:
            return offset + 1
        if size & 0xc0 == 0xc0 and offset + 1 < len(packet):
            return offset + 2
        if size > 63:
            break
        offset += size + 1
    raise PiHoleError("Invalid DNS record name.")


def dns_answers(host, *, tcp):
    ident = secrets.randbelow(65536)
    question = b"".join(bytes((len(label),)) + label.encode("ascii") for label in host.split("."))
    question += b"\x00\x00\x01\x00\x01"
    query = struct.pack("!6H", ident, 0x0100, 1, 0, 0, 0) + question
    if tcp:
        with socket.create_connection((DNS_IP, 53), TIMEOUT) as sock:
            sock.sendall(struct.pack("!H", len(query)) + query)
            size, = struct.unpack("!H", read_exact(sock, 2))
            if size > 4096:
                raise PiHoleError("DNS reply exceeded the size limit.")
            packet = read_exact(sock, size)
    else:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(TIMEOUT)
            sock.connect((DNS_IP, 53))
            sock.send(query)
            packet = sock.recv(4096)
    actual, flags, questions, count, _, _ = struct.unpack_from("!6H", packet)
    offset = 12 + len(question)
    if (actual != ident or flags & 0xfa0f != 0x8000 or questions != 1 or count > 32
            or packet[12:offset] != question):
        raise PiHoleError("DNS reply did not match the health probe.")
    addresses = []
    for _ in range(count):
        offset = end_name(packet, offset)
        kind, class_, _, size = struct.unpack_from("!HHIH", packet, offset)
        offset += 10
        if offset + size > len(packet):
            raise PiHoleError("Incomplete DNS record.")
        if (kind, class_, size) == (1, 1, 4):
            addresses.append(socket.inet_ntoa(packet[offset:offset + 4]))
        offset += size
    return sorted(addresses)


def health():
    status = request("GET", "/api/info/login")
    transport = {}
    for name, tcp in (("udp", False), ("tcp", True)):
        transport[name] = {
            "local_answer_ok": dns_answers("k8s-api.branconet.lan", tcp=tcp) == ["192.168.0.251"],
            "blocking_probe_ok": dns_answers("doubleclick.net", tcp=tcp) == ["0.0.0.0"],
        }
    return {"api_dns_active": status["dns"] is True, "floating_dns": transport}


def blocking():
    with session() as sid:
        response = request("GET", "/api/dns/blocking", sid=sid)
        return {"blocking": response["blocking"], "timer": response.get("timer")}


def records():
    with session() as sid:
        output = {}
        for key in ("hosts", "cnameRecords"):
            value = request("GET", f"/api/config/dns/{key}", sid=sid)["config"]["dns"][key]
            if not isinstance(value, list) or len(value) > 256 or not all(
                isinstance(entry, str) and len(entry) <= 512 for entry in value
            ):
                raise PiHoleError("Unexpected Pi-hole record response.")
            output[key] = value
        return output


TOOLS = {
    "pihole_health": (health, "Check the private Pi-hole API and the floating resolver over UDP and TCP."),
    "pihole_blocking": (blocking, "Read the current Pi-hole blocking state using the local app password."),
    "pihole_local_records": (records, "Read configured local address and CNAME records from Pi-hole."),
}


def respond(message):
    envelope = {"jsonrpc": "2.0", "id": message.get("id")}
    if message.get("jsonrpc") != "2.0":
        return {**envelope, "error": {"code": -32600, "message": "Invalid request"}}
    if "id" not in message:
        return None
    params = message.get("params", {})
    method = message.get("method")
    if not isinstance(params, dict):
        return {**envelope, "error": {"code": -32602, "message": "Invalid parameters"}}
    if method == "initialize":
        version = params.get("protocolVersion")
        result = {"protocolVersion": version if isinstance(version, str) and version in VERSIONS else "2025-11-25",
                  "capabilities": {"tools": {}}, "serverInfo": {"name": "pihole-dns", "version": "0.2.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [{"name": name, "description": description,
                             "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                             "annotations": {"readOnlyHint": True, "openWorldHint": False}}
                            for name, (_, description) in TOOLS.items()]}
    elif method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str) or name not in TOOLS or params.get("arguments", {}) != {}:
            return {**envelope, "error": {"code": -32602, "message": "Unknown tool or arguments"}}
        try:
            result = {"content": [{"type": "text", "text": json.dumps(TOOLS[name][0]())}]}
        except PiHoleError as exc:
            result = {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
        except (OSError, http.client.HTTPException, ValueError, KeyError, TypeError, struct.error):
            result = {"isError": True, "content": [{"type": "text", "text": "Pi-hole request or configuration failed."}]}
    else:
        return {**envelope, "error": {"code": -32601, "message": "Method not found"}}
    return {**envelope, "result": result}


INSTRUCTIONS = ("Read-only Pi-hole tools: API and floating-resolver health over UDP and TCP, "
                "blocking state, and configured local DNS records. Nothing is changed.")


def main():
    """Serve both MCP eras; respond() above stays the legacy handler."""
    dual_era.serve(dual_era.make_responder(respond, "pihole-dns", "0.2.0", INSTRUCTIONS))


if __name__ == "__main__":
    main()
