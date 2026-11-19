---
{"version":1,"scope":"repo","owner":"opencode-memory","id":"mcp-shared-connections","title":"MCP servers live here; any repository may opt in and share one pooled process","tags":["mcp","opencode","pooling","scope"],"kind":"decision","updated":"2026-11-19","verified":"2026-11-19","sources":["mcp-servers/README.md","opencode.json","mcp-servers/_shared/dual_era.py","docs/operations/handoffs/opencode-takeover.md"]}
---

James directed on 2026-11-19 that `bortus`, `netgear-xr500`, `pihole-dns` and
`plex-inventory` live in this repository's `mcp-servers/`, and that they must
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

Verified 2026-11-19: a scratch project outside this repository with the copied
entries connected all four servers with no new process (same four PIDs).
