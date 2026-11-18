---
{
  "version": 1,
  "scope": "repo",
  "owner": "opencode-memory",
  "id": "skill-location-scope",
  "title": "Repository-specific skills stay in the repository",
  "tags": ["skills", "opencode", "scope"],
  "kind": "decision",
  "updated": "2026-11-18",
  "verified": "2026-11-18",
  "sources": [".opencode/skills/bortus-local-test/SKILL.md", "docs/planning/evidence/2026-11-18-bortus-mcp-implementation.md", "opencode.json"]
}
---

James directed on 2026-11-18 that repository-specific skills must not be
installed in the global OpenCode configuration (`~/.config/opencode/skills`).
Install them in the owning repository under `.opencode/skills/<skill-id>/`,
where OpenCode discovers them for sessions started in that repository and its
subdirectories. Verified by loading and triggering `bortus-local-test` inside
this repository and confirming it is absent from a session started outside it.
The global skills directory stays for genuinely cross-repository workflows, and
a plan may still keep a reviewable skill design under `docs/operating-kit/`
until it is installed.
