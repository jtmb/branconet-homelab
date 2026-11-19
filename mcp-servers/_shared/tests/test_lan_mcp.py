"""Dual-era contract for the LAN MCP servers (netgear-xr500, pihole-dns, plex-inventory).

The adapter tests drive dual_era.make_responder against a recording fake
legacy handler. The server tests run each real server.py over stdio, the
way OpenCode starts it, and use only requests that never reach the router,
Pi-hole or Plex (discovery, listing and argument validation), so they need
no network or credentials.
"""
import json
from pathlib import Path
import subprocess
import sys
import unittest

SHARED = Path(__file__).resolve().parents[1]
SERVERS = SHARED.parent
sys.path.insert(0, str(SHARED))

import dual_era  # noqa: E402

MODERN = {"io.modelcontextprotocol/protocolVersion": "2026-07-28",
          "io.modelcontextprotocol/clientCapabilities": {},
          "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "0"}}


class AdapterTests(unittest.TestCase):
    """make_responder adds the modern era without changing the legacy handler."""

    def setUp(self):
        self.seen = []

        def legacy(message):
            """Record what the legacy handler receives; answer like the real servers."""
            self.seen.append(message)
            if "id" not in message:
                return None
            if message.get("method") == "tools/list":
                return {"jsonrpc": "2.0", "id": message["id"], "result": {"tools": [{"name": "t"}]}}
            if message.get("method") == "tools/call":
                return {"jsonrpc": "2.0", "id": message["id"], "result": {"content": []}}
            if message.get("method") == "initialize":
                return {"jsonrpc": "2.0", "id": message["id"], "result": {"protocolVersion": "2025-11-25"}}
            return {"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": "Method not found"}}

        self.respond = dual_era.make_responder(legacy, "fake", "9.9", "Fake tools.")

    def modern(self, method, meta=MODERN, **params):
        """Send one request carrying modern per-request metadata."""
        return self.respond({"jsonrpc": "2.0", "id": 7, "method": method,
                             "params": {**params, "_meta": meta}})

    def test_discover_advertises_modern_first_without_reaching_legacy(self):
        result = self.modern("server/discover")["result"]
        self.assertEqual(result["supportedVersions"][0], "2026-07-28")
        self.assertEqual((result["resultType"], result["cacheScope"]), ("complete", "public"))
        self.assertEqual(result["_meta"]["io.modelcontextprotocol/serverInfo"], {"name": "fake", "version": "9.9"})
        self.assertEqual(self.seen, [])

    def test_modern_list_strips_meta_and_adds_cache_fields(self):
        result = self.modern("tools/list")["result"]
        self.assertEqual(self.seen[-1]["params"], {})
        self.assertEqual(result["tools"], [{"name": "t"}])
        self.assertEqual((result["resultType"], result["ttlMs"], result["cacheScope"]), ("complete", 3600000, "public"))

    def test_modern_call_is_complete_but_has_no_cache_fields(self):
        result = self.modern("tools/call", name="t", arguments={})["result"]
        self.assertEqual(self.seen[-1]["params"], {"name": "t", "arguments": {}})
        self.assertEqual(result["resultType"], "complete")
        self.assertNotIn("ttlMs", result)
        self.assertNotIn("cacheScope", result)

    def test_unsupported_version_and_missing_capabilities_never_reach_legacy(self):
        reply = self.modern("tools/list", meta={**MODERN, "io.modelcontextprotocol/protocolVersion": "1900-01-01"})
        self.assertEqual(reply["error"]["code"], -32022)
        self.assertEqual(reply["error"]["data"]["requested"], "1900-01-01")
        meta = {k: v for k, v in MODERN.items() if k != "io.modelcontextprotocol/clientCapabilities"}
        self.assertEqual(self.modern("tools/list", meta=meta)["error"]["code"], -32602)
        self.assertEqual(self.modern("initialize")["error"]["code"], -32601)
        self.assertEqual(self.seen, [])

    def test_legacy_requests_pass_through_unchanged(self):
        """Clients that open with initialize see exactly the previous replies."""
        for message in ({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                        {"jsonrpc": "2.0", "method": "notifications/initialized"}):
            self.seen.clear()
            reply = self.respond(message)
            self.assertEqual(self.seen, [message])
            if reply is not None:
                self.assertNotIn("resultType", reply.get("result", {}))


class ServerTests(unittest.TestCase):
    """Each real server answers both eras over stdio with an unchanged tool set."""

    EXPECTED = {
        "netgear-xr500": ["router_status", "dhcp_pool", "router_logs", "outbound_rules", "propose_dhcp_pool_end"],
        "pihole-dns": ["pihole_health", "pihole_blocking", "pihole_local_records"],
        "plex-inventory": ["plex_health", "plex_libraries", "plex_search"],
    }
    # A tools/call for each server that fails argument validation before any network use.
    REJECTED = {
        "netgear-xr500": ("propose_dhcp_pool_end", {"expected_end": "not-an-ip", "new_end": "x"}),
        "pihole-dns": ("pihole_health", {"unexpected": 1}),
        "plex-inventory": ("plex_search", {"query": ""}),
    }

    def exchange(self, name, messages):
        """Run server.py exactly as registered and return one reply per request."""
        lines = "".join(json.dumps(m) + "\n" for m in messages)
        result = subprocess.run([sys.executable, "-B", str(SERVERS / name / "server.py")], input=lines,
                                capture_output=True, text=True, timeout=30, cwd=SERVERS / name)
        self.assertEqual(result.stderr, "")
        return [json.loads(line) for line in result.stdout.splitlines()]

    def test_modern_discovery_listing_and_validation(self):
        for name, tools in self.EXPECTED.items():
            with self.subTest(name):
                tool, arguments = self.REJECTED[name]
                discover, listing, rejected = self.exchange(name, [
                    {"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {"_meta": MODERN}},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {"_meta": MODERN}},
                    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                     "params": {"name": tool, "arguments": arguments, "_meta": MODERN}}])
                self.assertEqual(discover["result"]["supportedVersions"][0], "2026-07-28")
                self.assertEqual(discover["result"]["_meta"]["io.modelcontextprotocol/serverInfo"]["name"], name)
                self.assertEqual([t["name"] for t in listing["result"]["tools"]], tools)
                self.assertEqual(listing["result"]["resultType"], "complete")
                self.assertIn("ttlMs", listing["result"])
                failed = rejected.get("error") or rejected["result"].get("isError")
                self.assertTrue(failed, rejected)

    def test_legacy_handshake_still_works(self):
        for name, tools in self.EXPECTED.items():
            with self.subTest(name):
                init, listing = self.exchange(name, [
                    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}])
                self.assertEqual(init["result"]["protocolVersion"], "2025-06-18")
                self.assertEqual(init["result"]["serverInfo"]["name"], name)
                self.assertEqual([t["name"] for t in listing["result"]["tools"]], tools)
                self.assertNotIn("resultType", listing["result"])


if __name__ == "__main__":
    unittest.main()
