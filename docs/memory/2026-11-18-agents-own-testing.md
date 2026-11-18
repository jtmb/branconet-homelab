---
{"version":1,"scope":"repo","owner":"opencode-memory","id":"2026-11-18-agents-own-testing","title":"Agents own routine testing; RULES.md is authoritative","tags":["rules","testing","browser","credentials","communication"],"kind":"decision","updated":"2026-11-18","verified":"2026-11-18","sources":["RULES.md","AGENTS.md","opencode.json","scripts/migration/saved-node-credential.py"]}
---

On 2026-11-18 James objected to being handed routine checks the agent could
do with the agent browser, and asked for an authoritative `RULES.md`, declared
in `AGENTS.md` and loaded through `opencode.json` instructions.

- Agents sign in, exercise pages and read what is on screen with the OpenCode
  agent browser, and use shell/cluster/network/MCP tools for the rest. Reuse
  valid evidence; record it as "verified by the agent". Involve James only for
  access, action or judgment that is genuinely his.
- The node admin password is already in his vault: use
  `scripts/migration/saved-node-credential.py`, never ask him for it.
- Explain plans and results to James in plain language with a clear "done
  when" and simple tables or diagrams (his explicit request, same date).
