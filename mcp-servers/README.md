# MCP servers for this repository

Every server here is a local stdio process. This repository registers all
five in its `opencode.json`; none is in the global config. Each entry uses the
installed command, a fixed `cwd` (its own directory), `"pool": true` and
`"protocol": "2026-07-28"`, so OpenCode 2.3.2 shares one process per server
across every directory that uses an identical entry.

**Disabled by default (2026-11-19).** Every entry carries `"disabled": true`;
only the global `wsl-interop` connects automatically. Turn one on for the
current directory when a task needs it, then off again:

```sh
loc=$(python3 -c "import urllib.parse,os;print(urllib.parse.quote(os.getcwd(),safe=''))")
opencode api post "/api/experimental/mcp/bortus/connect?location%5Bdirectory%5D=$loc"
opencode api post "/api/experimental/mcp/bortus/disconnect?location%5Bdirectory%5D=$loc"
```

The owner can do the same from `/mcps`. Do not remove `disabled` from the config.

**Using them from another repository.** Copy the entry from this repository's
`opencode.json` into that repository's `opencode.json`, unchanged: same
`command`, `cwd`, `pool` and `protocol`, with no added `environment` or
`timeout`. It then attaches to the same running process instead of starting a
new one (verified 2026-11-19 from a project outside this repository). Any
difference in those fields gets a separate process. For example:

```json
"bortus": {
  "type": "local",
  "command": ["/usr/bin/python3", "-B", "/home/brajam/repos/branconet-homelab/mcp-servers/bortus/launch.py"],
  "cwd": "/home/brajam/repos/branconet-homelab/mcp-servers/bortus",
  "pool": true,
  "protocol": "2026-07-28"
}
```

| Server | What it does | Credentials (local, ignored) |
| --- | --- | --- |
| `bortus/` | Kubernetes inventory, scoped Secret reads, optional guarded run | `.env` (inventory and Secret kubeconfig paths) |
| `netgear-xr500/` | Router status, DHCP pool, logs, outbound rules; DHCP changes proposed only | `.env` (`XR500_USERNAME`, `XR500_PASSWORD`) |
| `pihole-dns/` | Pi-hole API and resolver health, blocking state, local records | `.env` (`PIHOLE_APP_PASSWORD`); the public `lan-root-ca.pem` is committed |
| `plex-inventory/` | Plex health, library list, title search | `.env` (`PLEX_TOKEN`) |
| `seerr-inventory/` | Seerr health, title search, recent request status, expiry-bound request proposals | `.env` (`SEERR_API_KEY`); the public `lan-root-ca.pem` is committed |

`_shared/dual_era.py` gives the four LAN servers MCP revision 2026-07-28
(`server/discover`, stateless per-request `_meta`) while their original
legacy handlers keep answering `initialize` clients unchanged.
`_shared/read_only_media.py` is the bounded GET-only transport used by Plex
and Seerr. `bortus` has its own dual-era implementation.

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
