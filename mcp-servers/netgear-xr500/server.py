import base64
import hashlib
import http.client
import ipaddress
import json
import os
import re
import ssl
import stat
import sys
from html import unescape
from pathlib import Path

from approval import fingerprint, prepare

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))
import dual_era  # noqa: E402  (stdlib-only adapter for MCP 2026-07-28)

HOST = "192.168.0.1"
CERT_SHA256 = "e66d68657a119a26703c3f3b174c8142af46b15cb4388bf99764137ac23e62ec"
ENV_FILE = Path(__file__).with_name(".env")
PAGES = {
    "router_status": ("/", "Check the pinned router connection and authentication status."),
    "dhcp_pool": ("/LAN_lan.htm", "Read the router DHCP pool bounds."),
    "router_logs": ("/FW_log.htm", "Read recent router event log entries."),
    "outbound_rules": ("/BKS_service.htm", "Read the outbound service blocking table."),
}
MAX_PAGE = 512 * 1024
VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}


class RouterError(Exception):
    pass


def authorization():
    try:
        fd = os.open(ENV_FILE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RouterError("Could not open the local .env file safely.") from exc

    with os.fdopen(fd, "rb") as env:
        info = os.fstat(env.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_nlink != 1):
            raise RouterError("The .env file must be a regular file owned by you with mode 0600 or 0400.")
        data = env.read(8193)
    if len(data) > 8192:
        raise RouterError("The .env file is too large.")

    values = {}
    for line in data.decode("utf-8-sig").split("\n"):
        line = line.removesuffix("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep or key not in {"XR500_USERNAME", "XR500_PASSWORD"} or key in values:
            raise RouterError("The .env file contains an unknown, duplicate or malformed setting.")
        values[key] = value
    username = values.get("XR500_USERNAME")
    password = values.get("XR500_PASSWORD")
    if not username or not password:
        return None
    if ":" in username or any(ord(ch) < 32 or ord(ch) == 127 for ch in username + password):
        raise RouterError("The XR500 username or password contains an unsupported character.")
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return "Basic " + encoded

def fetch(path, auth):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    connection = http.client.HTTPSConnection(HOST, timeout=5, context=context)
    try:
        connection.connect()
        certificate = connection.sock.getpeercert(binary_form=True)
        if hashlib.sha256(certificate).hexdigest() != CERT_SHA256:
            raise RouterError("XR500 certificate pin mismatch. Credentials were withheld.")
        headers = {"Accept": "text/html, text/plain", "User-Agent": "Branconet-XR500-MCP"}
        if auth:
            headers["Authorization"] = auth
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        body = response.read(MAX_PAGE + 1)
        if len(body) > MAX_PAGE:
            raise RouterError("Router response exceeded the size limit.")
        return response.status, body.decode("utf-8", errors="replace")
    finally:
        connection.close()


def extract_log(page):
    areas = re.findall(r"<textarea\b[^>]*>(.*?)</textarea\s*>", page, re.I | re.S)
    if len(areas) != 1:
        raise RouterError("The firmware log page did not contain the expected log field.")
    return [line[:350] for line in unescape(areas[0]).splitlines() if line.strip()][:80]


def extract_rules(page):
    count = re.search(r"\bvar\s+array_num\s*=\s*(\d+)\s*;", page)
    mode = re.search(r"""\bvar\s+get_blockserv_ctrl\s*=\s*['"]([012])['"]\s*;""", page)
    if count is None or mode is None or int(count[1]) > 20:
        raise RouterError("The firmware response did not contain recognized service blocking settings.")

    rows = []
    for index in range(1, int(count[1]) + 1):
        rule = re.search(
            rf"""\b(?:var\s+)?block_servicesArray{index}\s*=\s*(["'])(.*?)\1\s*;""", page
        )
        fields = rule[2].split(" ") if rule else []
        if len(fields) < 7 or not all(re.fullmatch(r"\d{1,5}", field) for field in fields[2:4]):
            raise RouterError("The firmware response contained an unrecognized service rule.")
        rows.append({"service": unescape(fields[4])[:100],
                     "start_port": int(fields[2]), "end_port": int(fields[3]),
                     "target": unescape(fields[6])[:100]})
    return {"mode": {"0": "never", "1": "per_schedule", "2": "always"}[mode[1]],
            "untrusted_rules": rows}

def extract_dhcp_pool(page):
    bounds = {}
    for key in ("start", "end"):
        matches = set(re.findall(
            r"\bvar\s+dhcp_" + key + r"\s*=\s*['\"]([0-9.]+)['\"]", page))
        if len(matches) != 1:
            raise RouterError("The router response did not identify one DHCP pool.")
        try:
            bounds[key] = ipaddress.IPv4Address(matches.pop())
        except ValueError as exc:
            raise RouterError("The router returned an invalid DHCP address.") from exc
    if bounds["end"] < bounds["start"]:
        raise RouterError("The router returned reversed DHCP bounds.")
    return {"start": str(bounds["start"]), "end": str(bounds["end"])}


def call_tool(name):
    path, _ = PAGES[name]
    auth = authorization()
    if not auth and name != "router_status":
        raise RouterError("Set XR500_USERNAME and XR500_PASSWORD in the local .env file.")
    protected_status = name == "router_status" and bool(auth)
    if protected_status:
        path = PAGES["dhcp_pool"][0]
    status, body = fetch(path, auth)
    if (protected_status or name == "dhcp_pool") and status == 401:
        login_status, _ = fetch("/", auth)
        if login_status == 200:
            status, body = fetch(path, auth)
    if name == "router_status":
        if protected_status and status == 200:
            extract_dhcp_pool(body)
        return {"router_http_status": status, "credential_configured": bool(auth),
                "admin_authenticated": protected_status and status == 200}
    if status != 200:
        raise RouterError(f"The router returned HTTP {status}.")
    if name == "dhcp_pool":
        return extract_dhcp_pool(body)
    if name == "router_logs":
        return {"untrusted_router_log_entries": extract_log(body)}
    return extract_rules(body)


def propose_dhcp_pool_end(arguments):
    if not isinstance(arguments, dict) or set(arguments) != {"expected_end", "new_end"}:
        raise RouterError("Supply the expected and proposed DHCP pool end addresses.")
    try:
        expected = ipaddress.IPv4Address(arguments["expected_end"])
        proposed = ipaddress.IPv4Address(arguments["new_end"])
    except (ipaddress.AddressValueError, TypeError) as exc:
        raise RouterError("Use IPv4 addresses for both pool ends.") from exc
    if not all(isinstance(value, str) for value in arguments.values()):
        raise RouterError("Use IPv4 address strings.")
    current = call_tool("dhcp_pool")
    start = ipaddress.IPv4Address(current["start"])
    end = ipaddress.IPv4Address(current["end"])
    if expected != end:
        raise RouterError("The live DHCP pool end differs from the expected address.")
    if not start <= proposed < end:
        raise RouterError("The proposed end must narrow the current DHCP pool.")
    proposal = prepare({"host": HOST, "certificate_sha256": CERT_SHA256}, current, str(proposed))
    return {"setting": "dhcp_pool_end", "before": current["end"],
            "after": str(proposed), "current_pool_sha256": fingerprint(current),
            "proposal": proposal, "approval_sha256": fingerprint(proposal),
            "removed_address_count": int(end) - int(proposed),
            "applied": False}


def respond(request):
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}
    envelope = {"jsonrpc": "2.0", "id": request_id}
    if request.get("jsonrpc") != "2.0" or not isinstance(method, str):
        return {**envelope, "error": {"code": -32600, "message": "Invalid request"}}
    if "id" not in request:
        return None
    if not isinstance(params, dict):
        return {**envelope, "error": {"code": -32602, "message": "Invalid parameters"}}
    if method == "initialize":
        version = params.get("protocolVersion")
        result = {"protocolVersion": version if isinstance(version, str) and version in VERSIONS
                  else "2025-11-25", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "netgear-xr500", "version": "0.2.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [
            {"name": name, "description": description,
             "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
             "annotations": {"readOnlyHint": True, "openWorldHint": False}}
            for name, (_, description) in PAGES.items()
        ]}
        result["tools"].append({
            "name": "propose_dhcp_pool_end",
            "description": "Prepare a DHCP pool reduction for separate operator approval.",
            "inputSchema": {"type": "object", "properties": {
                "expected_end": {"type": "string"}, "new_end": {"type": "string"}},
                "required": ["expected_end", "new_end"], "additionalProperties": False},
            "annotations": {"readOnlyHint": True, "openWorldHint": False},
        })
    elif method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name != "propose_dhcp_pool_end" and (
            not isinstance(name, str) or name not in PAGES or arguments != {}
        ):
            return {**envelope, "error": {"code": -32602, "message": "Unknown tool or arguments"}}
        try:
            payload = (propose_dhcp_pool_end(arguments) if name == "propose_dhcp_pool_end"
                       else call_tool(name))
            result = {"content": [{"type": "text", "text": json.dumps(payload)}]}
        except (RouterError, OSError, http.client.HTTPException, UnicodeError) as exc:
            message = str(exc) if isinstance(exc, RouterError) else "Router request failed."
            result = {"isError": True, "content": [{"type": "text", "text": message}]}
    else:
        return {**envelope, "error": {"code": -32601, "message": "Method not found"}}
    return {**envelope, "result": result}


INSTRUCTIONS = ("Read-only tools for the certificate-pinned Netgear XR500 router: status, DHCP "
                "pool, recent logs and outbound rules. propose_dhcp_pool_end only prepares a "
                "change for separate operator approval; it never writes to the router.")


def main():
    """Serve both MCP eras; respond() above stays the legacy handler."""
    dual_era.serve(dual_era.make_responder(respond, "netgear-xr500", "0.2.0", INSTRUCTIONS))


if __name__ == "__main__":
    main()
