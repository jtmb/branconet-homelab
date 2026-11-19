# Plex inventory MCP

Run `/usr/bin/python3 -B server.py` over stdio. It imports
`mcp-servers/_shared/read_only_media.py` (bounded GET-only transport) and
`dual_era.py`. The ignored `.env` contains the existing
`PLEX_TOKEN` and must be mode 0600. The adapter sends it only to the floating
Plex HTTPS endpoint and verifies the server's Plex certificate and hostname.

Tools read server health, list libraries and search the library. Responses
exclude file paths, server identity and account data. The deployment does
not expose playback controls, sessions, account or cloud APIs.

The reviewed [upstream Plex MCP](https://github.com/aminamos/plex-mcp-server)
was pinned at `88e00acb6140d29d6c44d9bebbde56ac7d07343c`. This adapter uses a
fixed subset of the Plex API and does not load the upstream runtime.

## Location, protocol and pooling (2026-11-19)

This server moved from Veyra into `branconet-homelab/mcp-servers/` and is
registered only in this repository's `opencode.json`, with a fixed `cwd`,
`"pool": true` and `"protocol": "2026-07-28"`. It is dual-era through
`mcp-servers/_shared/dual_era.py`: `server/discover` and modern per-request
`_meta` are served statelessly, and a client that opens with `initialize` gets
the previous legacy replies unchanged. Credentials are re-read from `.env` on
every call, so one pooled process serves every directory in this repository.
Tests: `python3 -B -m unittest discover -s mcp-servers/_shared/tests -p 'test_*.py'`.
