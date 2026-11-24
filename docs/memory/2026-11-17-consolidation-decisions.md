---
{"version":1,"scope":"repo","owner":"opencode-memory","id":"2026-11-17-consolidation-decisions","title":"Owner decisions from the 2026-11-17 consolidation pass","tags":["bortus","ntfy","network","release","git"],"kind":"decision","updated":"2026-11-17","verified":"2026-11-17","sources":["docs/operations/handoffs/opencode-takeover.md","docs/NOTIFICATIONS.md","docs/NETWORK-HARDENING.md"]}
---

James reviewed a found-flaws report for the Certificates/Trust/network-
hardening work and made these explicit choices (all "recommended" options,
via the structured question tool):

- Push `codex/seerr-cluster-security` to `origin` with upstream tracking,
  rather than keep it local-only or push only the release commits. Done.
- Stop and disable Docker on node01 between builds rather than leave it
  running as a standing builder. The `bortus-image-release` skill now
  documents this as the expected pattern for future releases.
- Delete orphaned `wordpress` namespace secrets (helm-release history,
  `-runtime` secrets) with a dependency re-check and UID/resourceVersion
  guards, rather than delete the whole namespace or keep everything. The
  re-check found `source-acme-0..5` in that namespace are still live shared
  TLS secrets for six other apps' Ingresses — those were excluded from the
  deletion, narrowing the approved scope to what was actually safe.
- Apply the notification-sender timeout fix (3s→8s) now rather than wait for
  a reproduced failure, and not also raise the CPU quota.
- Ship D4 (certificates-route typecheck fix) in source now if needed, batch
  D3 (optional `notificationDelivery` field) with the next real BORTUS image
  release rather than trigger a production restart for it alone. (D4 turned
  out to need no action — already resolved by pre-existing staged work.)
- Scope for this pass: Phase 0 (receipt fix), Phase 1-2 (reliability),
  Phase 4 (cleanup), and docs/skills/memory/MCP — explicitly not the
  node01/node03 kubelet-CSR-approval expansion, which stays a separate,
  explicitly-authorized task per `node-host-ops` skill guidance.

Current acceptance status, the attended-receipt gate, and sudo-password-
gated host work (Docker stop/disable, TLS-expiry monitor deployment) remain
in `docs/operations/handoffs/opencode-takeover.md`, not here.
