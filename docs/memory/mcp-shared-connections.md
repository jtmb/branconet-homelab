---
{"version":1,"scope":"repo","owner":"opencode-memory","id":"mcp-shared-connections","title":"MCP servers live here; any repository may opt in and share one pooled process","tags":["mcp","opencode","pooling","scope"],"kind":"decision","updated":"2026-11-19","verified":"2026-11-19","sources":["mcp-servers/README.md","opencode.json","mcp-servers/_shared/dual_era.py","docs/operations/handoffs/opencode-takeover.md"]}
---

James directed on 2026-11-19 that `bortus`, `netgear-xr500`, `pihole-dns`,
`plex-inventory` and `seerr-inventory` live in this repository's
`mcp-servers/`, and that they must
keep working for any other repository that chooses to register them in its
own `opencode.json`. The point is OpenCode 2.3.2 shared connections
(`"pool": true`), not limiting them to this repository.

- Registration stays in each consuming repository's `opencode.json`, never in
  the global config (consistent with `skill-location-scope`).
- To share the same process, another repository copies the entry exactly:
  same command, fixed `cwd`, `"pool": true`, `"protocol": "2026-07-28"`, and
  no added `environment` or `timeout`. Any difference starts a separate process.
- Servers must keep no per-project state and use absolute paths; credentials
  stay in each server's private `.env` beside it.
- All five are `"disabled": true` by default; only the global `wsl-interop`
  connects automatically, and a task connects and disconnects the one it needs.

Verified 2026-11-19: a scratch project outside this repository with the copied
entries connected all four servers as of that pass with no new process (same
four PIDs). Also verified 2026-11-19: `seerr-inventory`, after moving from
Veyra, connected from two directories in this repository with exactly one
`server.py` process, then disconnected from both while its entry stayed
disabled.
