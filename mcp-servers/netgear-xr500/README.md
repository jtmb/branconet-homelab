# Netgear XR500 MCP

Local stdio adapter for the Branconet XR500, launched as
`/usr/bin/python3 -B mcp-servers/netgear-xr500/server.py` from this repository.

Edit the local `.env` beside `server.py` to set `XR500_USERNAME` and
`XR500_PASSWORD`. Enter the values literally after the equals sign, without
shell quoting. Keep the file owned by your WSL user with permissions `0600`.
The server opens no listener and sends credentials only after the pinned HTTPS
certificate matches.

Branconet MCP implementations must support both Codex and OpenCode through
local stdio and use a private, ignored `.env` for credentials.

- `router_status` checks HTTPS reachability and authentication.
- `router_logs` requests the firmware event log and returns bounded text.
- `outbound_rules` requests the firmware service blocking table.

Authenticated log reads and the outbound page with zero rules were verified
on the installed firmware. Router logs are events, not a WAN packet capture.

## Request-only DHCP changes

`propose_dhcp_pool_end` compares the supplied end with the live pool and returns
the exact before and after bounds, the pinned router identity, a unique request
ID, a five-minute expiry and an approval digest. It reads the router and returns
`applied: false`.

`approval.consume` is the local admission contract for a future approved
executor. It accepts an independently supplied operator-approved digest,
checks the pinned target, rereads the exact live pool, and atomically records
the request ID in a private SQLite ledger before returning the admitted bounds.
A stale, changed, expired or consumed request is rejected. Keep the ledger
private and retain consumed IDs. An uncertain execution must be reconciled
against the router before another change can be proposed.

The MCP exposes the proposal only. The admission gate was tested with a
disposable ledger, including simultaneous attempts and a reopened database.
No live router writer is wired to it. A future write requires approval for
its exact digest and a readback of the resulting settings.

## Location, protocol and pooling (2026-11-19)

This server moved from Veyra into `branconet-homelab/mcp-servers/` and is
registered only in this repository's `opencode.json`, with a fixed `cwd`,
`"pool": true` and `"protocol": "2026-07-28"`. It is dual-era through
`mcp-servers/_shared/dual_era.py`: `server/discover` and modern per-request
`_meta` are served statelessly, and a client that opens with `initialize` gets
the previous legacy replies unchanged. Credentials are re-read from `.env` on
every call, so one pooled process serves every directory in this repository.
Tests: `python3 -B -m unittest discover -s mcp-servers/_shared/tests -p 'test_*.py'`.

References

- [Netgear XR500 user manual](https://www.downloads.netgear.com/files/GDC/XR500/XR500_UM_EN.pdf)
- [MCP stdio specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
- [OpenCode MCP configuration](https://opencode.ai/docs/mcp-servers/)
