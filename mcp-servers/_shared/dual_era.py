"""Serve a hand-written legacy MCP stdio server under revision 2026-07-28 too.

The LAN adapters (netgear-xr500, pihole-dns, plex-inventory) each keep their
existing legacy ``respond(message)`` exactly as it was. This module wraps it:

- ``server/discover`` advertises the supported versions, capabilities and
  server identity.
- A request whose ``params._meta`` carries
  ``io.modelcontextprotocol/protocolVersion`` is modern. Its version and client
  capabilities are checked per request, ``_meta`` is removed, the legacy
  handler answers, and a successful result is marked ``resultType: complete``
  with server identity. List results also carry the ``ttlMs``/``cacheScope``
  caching fields; call results must not, because their schema is closed.
  Modern clients never send ``initialize``.
- Every other request goes to the legacy handler unchanged, so a client that
  opens with ``initialize`` sees exactly the previous behaviour.

Nothing here keeps per-connection state, so one process can be shared by many
OpenCode directories (``"pool": true``). The same design is proven in
``mcp-servers/bortus/server.py``.
"""
import json
import sys

MODERN_VERSION = "2026-07-28"
SUPPORTED_VERSIONS = [MODERN_VERSION, "2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]
META_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
META_SERVER = "io.modelcontextprotocol/serverInfo"
LIST_METHODS = frozenset({"tools/list"})
CACHE_TTL_MS = 3600000
MAX_LINE = 65536


def make_responder(legacy_respond, name, version, instructions):
    """Return respond(message) that adds the modern era around legacy_respond.

    legacy_respond is never given a modern ``_meta`` and never sees
    ``server/discover``; its own validation and error text are kept.
    """
    identity = {"name": name, "version": version}

    def decorate(result, listing):
        """Mark a legacy result as a complete modern result."""
        decorated = {"resultType": "complete", **result}
        meta = decorated.get("_meta")
        meta = dict(meta) if isinstance(meta, dict) else {}
        meta[META_SERVER] = identity
        decorated["_meta"] = meta
        if listing:
            decorated.setdefault("ttlMs", CACHE_TTL_MS)
            decorated.setdefault("cacheScope", "public")
        return decorated

    def discover():
        """Modern discovery result."""
        return {"resultType": "complete", "supportedVersions": SUPPORTED_VERSIONS,
                "capabilities": {"tools": {}}, "_meta": {META_SERVER: identity},
                "instructions": instructions, "ttlMs": CACHE_TTL_MS, "cacheScope": "public"}

    def respond(message):
        """Answer one JSON-RPC message, or return None for a notification."""
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or "id" not in message:
            return legacy_respond(message)
        params = message.get("params", {})
        meta = params.get("_meta") if isinstance(params, dict) else None
        modern = isinstance(meta, dict) and isinstance(meta.get(META_VERSION), str)
        method = message.get("method")
        envelope = {"jsonrpc": "2.0", "id": message["id"]}
        if not modern:
            if method == "server/discover":
                return {**envelope, "result": discover()}
            return legacy_respond(message)
        requested = meta[META_VERSION]
        if requested not in SUPPORTED_VERSIONS:
            return {**envelope, "error": {"code": -32022, "message": "Unsupported protocol version",
                                          "data": {"supported": SUPPORTED_VERSIONS,
                                                   "requested": requested}}}
        if not isinstance(meta.get(META_CAPABILITIES), dict):
            return {**envelope, "error": {"code": -32602,
                                          "message": "Missing io.modelcontextprotocol/clientCapabilities"}}
        if method == "server/discover":
            return {**envelope, "result": discover()}
        if method == "initialize":
            return {**envelope, "error": {"code": -32601, "message": "Method not found",
                                          "data": {"supported": SUPPORTED_VERSIONS,
                                                   "hint": "modern clients do not initialize"}}}
        stripped = {key: value for key, value in params.items() if key != "_meta"}
        reply = legacy_respond({**message, "params": stripped})
        if isinstance(reply, dict) and isinstance(reply.get("result"), dict):
            reply = {**reply, "result": decorate(reply["result"], method in LIST_METHODS)}
        return reply

    return respond


def serve(respond):
    """Run the stdio loop: one JSON-RPC message per line, bounded in size."""
    while raw := sys.stdin.buffer.readline(MAX_LINE + 1):
        if len(raw) > MAX_LINE:
            raise SystemExit("MCP request exceeded the size limit.")
        try:
            message = json.loads(raw)
            reply = respond(message if isinstance(message, dict) else {})
        except (ValueError, RecursionError):
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if reply is not None:
            print(json.dumps(reply), flush=True)
