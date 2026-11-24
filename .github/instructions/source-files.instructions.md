---
description: "Use when editing files under k8s-rewrite/ — after every source edit, check and update the corresponding docs in docs/ at the repo root"
applyTo: "k8s-rewrite/**"
---

When you edit, create, or delete any file matching this pattern, you MUST:

1. Check which docs in `docs/` at the repo root cover the behavior you changed
2. Re-read those docs
3. Update anything that's now wrong (paths, names, versions, behaviors, commands, diagrams, IPs, examples)

**Do not defer.** Apply doc updates in the same turn as the code change. Treat docs as part of the feature.
