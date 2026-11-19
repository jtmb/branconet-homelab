# MCP servers for this repository

Every server here is a local stdio process registered only in this
repository's `opencode.json` (never in global config). Each entry uses the
installed command, a fixed `cwd` (its own directory), `"pool": true` and
`"protocol": "2026-07-28"`, so all OpenCode directories inside this repository
share one process per server.

| Server | What it does | Credentials (local, ignored) |
| --- | --- | --- |
| `bortus/` | Kubernetes inventory, scoped Secret reads, optional guarded run | `.env` (inventory and Secret kubeconfig paths) |
| `netgear-xr500/` | Router status, DHCP pool, logs, outbound rules; DHCP changes proposed only | `.env` (`XR500_USERNAME`, `XR500_PASSWORD`) |
| `pihole-dns/` | Pi-hole API and resolver health, blocking state, local records | `.env` (`PIHOLE_APP_PASSWORD`); the public `lan-root-ca.pem` is committed |
| `plex-inventory/` | Plex health, library list, title search | `.env` (`PLEX_TOKEN`) |

`_shared/dual_era.py` gives the three LAN servers MCP revision 2026-07-28
(`server/discover`, stateless per-request `_meta`) while their original
legacy handlers keep answering `initialize` clients unchanged.
`_shared/read_only_media.py` is the bounded GET-only transport used by Plex.
`bortus` has its own dual-era implementation.

```sh
python3 -B -m unittest discover -s mcp-servers/_shared/tests -p 'test_*.py'
python3 -B -m unittest discover -s mcp-servers/bortus/tests -p 'test_*.py'
opencode mcp list
```

To check pooling, open two directories in this repository and confirm one
`server.py` process per server (`pgrep -af mcp-servers/`) and log lines
`mcp connected server=<name>` without a `directory=` field.

The `.env` files are not in git. When setting up a new checkout, create each
`.env` with mode `0600` (see each server's README).
