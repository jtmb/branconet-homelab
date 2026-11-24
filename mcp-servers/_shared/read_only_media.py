"""Bounded, GET-only JSON transport and stdio for the LAN media adapters."""
import http.client
import json
import os
import socket
import ssl
import stat
from contextlib import closing
from urllib.parse import quote, urlencode

import dual_era

VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
LIMIT = 1024 * 1024
TIMEOUT = 5


class MediaError(Exception):
    pass


class FixedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, ip, port, ca_file):
        context = ssl.create_default_context(cafile=ca_file)
        super().__init__(host, port, timeout=TIMEOUT, context=context)
        self.ip = ip

    def connect(self):
        with socket.create_connection((self.ip, self.port), self.timeout) as raw:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


def credential(path, key):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as file:
        info = os.fstat(file.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_nlink != 1):
            raise MediaError("The local .env must be a private regular file.")
        value = file.read(4097)
    prefix = key.encode() + b"="
    line = value.rstrip(b"\r\n")
    if len(value) > 4096 or not line.startswith(prefix):
        raise MediaError("The local .env does not contain the expected setting.")
    secret = line[len(prefix):]
    if not 1 <= len(secret) <= 512 or any(c < 33 or c > 126 for c in secret):
        raise MediaError("The local credential is missing or invalid.")
    return secret.decode("ascii")


def get(endpoint, path, *, headers=None, query=None):
    if query:
        path += "?" + urlencode(query, quote_via=quote)
    with closing(FixedHTTPS(*endpoint)) as conn:
        conn.request("GET", path, headers={"Accept": "application/json", **(headers or {})})
        response = conn.getresponse()
        if response.status != 200:
            raise MediaError(f"Media service returned HTTP {response.status}.")
        data = response.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise MediaError("Media service response exceeded the size limit.")
    result = json.loads(data)
    if not isinstance(result, dict):
        raise MediaError("Media service returned an unexpected response.")
    return result


def select(item, *fields):
    return {name: item[name] for name in fields if type(item.get(name)) in (str, int, bool)}


def search_query(arguments):
    if not isinstance(arguments, dict) or set(arguments) != {"query"}:
        raise MediaError("Supply a single search query.")
    query = arguments["query"]
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 100 or any(
        ord(ch) < 32 or ord(ch) == 127 for ch in query
    ):
        raise MediaError("Use a search query between 1 and 100 printable characters.")
    return query.strip()


def describe(name, description, *, search=False):
    schema = {"type": "object", "properties": {}, "additionalProperties": False}
    if search:
        schema["properties"]["query"] = {"type": "string", "minLength": 1, "maxLength": 100}
        schema["required"] = ["query"]
    return {"name": name, "description": description, "inputSchema": schema,
            "annotations": {"readOnlyHint": True, "openWorldHint": False}}


def respond(server, tools, message):
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
                  "capabilities": {"tools": {}}, "serverInfo": {"name": server, "version": "0.2.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [tool[0] for tool in tools.values()]}
    elif method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str) or name not in tools:
            return {**envelope, "error": {"code": -32602, "message": "Unknown tool"}}
        spec, function, *validator = tools[name]
        args = params.get("arguments", {})
        try:
            if validator:
                value = function(validator[0](args))
            elif "required" in spec["inputSchema"]:
                value = function(search_query(args))
            else:
                if args != {}:
                    raise MediaError("This tool takes no arguments.")
                value = function()
            result = {"content": [{"type": "text", "text": json.dumps(value)}]}
        except MediaError as exc:
            result = {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
        except (OSError, http.client.HTTPException, ValueError, TypeError, KeyError, AttributeError):
            result = {"isError": True, "content": [{"type": "text", "text": "Media service request failed."}]}
    else:
        return {**envelope, "error": {"code": -32601, "message": "Method not found"}}
    return {**envelope, "result": result}


def serve(server, tools, instructions=""):
    """Serve both MCP eras; respond() above stays the legacy handler."""
    registry = {tool[0]["name"]: tool for tool in tools}
    legacy = lambda message: respond(server, registry, message)  # noqa: E731
    dual_era.serve(dual_era.make_responder(legacy, server, "0.2.0", instructions))
