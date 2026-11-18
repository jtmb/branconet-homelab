# OpenCode takeover — current state

> The full step-by-step chronology (2026-11-13 through 2026-11-17, ~2250
> lines) is preserved verbatim at
> [`docs/operations/history/opencode-takeover-chronology-2026-11.md`](../history/opencode-takeover-chronology-2026-11.md).
> This file is the current-state summary; read the chronology for how a
> given piece was built or for exact historical evidence paths.

James authorized moving this project from Codex to OpenCode; this is the
authoritative working repository (`/home/brajam/repos/branconet-homelab`,
branch `codex/seerr-cluster-security`). Do not create another checkout. No
subagents on this project. Disposable outputs stay on the existing H roots
(100 GB combined repository allowance).

## What's deployed and healthy (verified 2026-11-17)

- 3/3 nodes Ready (v1.37.2); 12/12 Flux Kustomizations and all HelmReleases
  Ready; 14/14 cert-manager Certificates healthy; 0 pending CSRs.
- BORTUS dashboard: live on `jtmb92/bortus@sha256:44a163a9…`, including the
  released Certificates UI (`/certificates`, `/api/certificates`).
- ntfy notifications: web UI enabled (`https://notifications.branconet.lan`),
  deny-all auth preserved, monitor/sender/watchdog/CSR-controller services
  active on their respective hosts. See `docs/NOTIFICATIONS.md`.
- Network hardening: 9 nftables profiles, boot-persistent, mesh enrollment
  for BORTUS + 7 Plex-stack apps + the pre-existing ambient set. See
  `docs/NETWORK-HARDENING.md`.
- Unattended kubelet-serving CSR approval is live — **node02 only** (see
  limitation in `docs/NOTIFICATIONS.md`).

## Fixed this session (2026-11-17 consolidation pass)

A full review of prior work found and fixed:

- **F1** Test notification was posted as a JSON body instead of using the
  `Title` header, rendering as an untitled raw-JSON card. Republished
  correctly and visually confirmed via an isolated browser session.
- **F2** The subscriber password had been written to an unprotected temp
  file and shared in chat. Rotated via the new
  `scripts/migration/update-ntfy-auth-user.py`; old file deleted.
- **F3** That script also prevents a repeat of the 2026-11-17 crash-loop
  (missing `:role` suffix in a hand-edited Secret entry): format validation,
  resourceVersion guard, verified restart, automatic revert on failure.
- **F4** Flux doesn't restart a pod on ConfigMap-only change; a
  `checksum/server-yml` annotation (enforced by a new test) now forces a
  restart whenever `server.yml` changes. Verified end-to-end: a new
  ReplicaSet appeared automatically.
- **F7** `build-bortus-release-image.py` tagged images as unqualified
  `bortus:release-<commit>`, which exports as `docker.io/library/bortus` and
  causes `ErrImageNeverPull` on preload. Fixed to the qualified
  `jtmb92/bortus:release-<commit>` tag used by every other build script here;
  regression test added.
- **F12** Sender's inner HTTPS timeout raised 3s→8s (strongly supported,
  not reproduced, mitigation for the 66.2-minute 2026-11-16 delay). See
  `docs/NOTIFICATIONS.md`.
- **F13** Added `scan_tls_endpoints()` to the certificate monitor: kubeadm/
  kubelet serving certificate expiry is now watched via a live TLS handshake
  to each node's `:6443`/`:10250` (no host/root access granted). Wired into
  the existing policy-driven scan cycle, and **deployed and live** on
  node02. Deployment itself surfaced two more real bugs: a SHA1-vs-SHA256
  mismatch in the hash guard, and "before" pins computed from an
  already-edited local file instead of the actually-deployed content — both
  caught by the guard refusing rather than silently overwriting, both fixed
  by verifying the live host content byte-for-byte first. After the fix
  deployed cleanly, every one of the 6 new TLS probes then failed because
  the service's `IPAddressAllow` sandbox only permitted the floating API
  VIP; this queued 6 false "unavailable" alerts which were deleted by exact
  UID (verified undelivered first) before the sender could spam ntfy with
  them. The sandbox was widened to the 3 node IPs the probe needs, nothing
  broader. All 6 endpoints now report healthy with real expiry dates.
- Cleanup: removed 3 leftover ntfy-fixture namespaces, 21 Failed pods, and
  orphaned `wordpress` namespace secrets (helm-release history + `-runtime`
  secrets with no live workload). **Not removed**: `source-acme-0..5` in
  that namespace — confirmed still referenced by six other charts'
  Ingress TLS (`mealie`, `aplb`, and others); removing them would have broken
  unrelated services.
- D4 (certificates-route typecheck divergence) required **no fix** — it was
  already resolved in the pre-existing staged auth refactor; my first attempt
  at a fix accidentally reverted part of that staged work and was discarded
  after comparing `git diff --cached` vs the working tree.
- `codex/seerr-cluster-security` pushed to `origin` with upstream tracking
  (previously local-only).

See `docs/memory/` for durable decisions and lessons extracted from this
pass, and the new skills `private-chart-delivery`, `native-secret-change`,
`bortus-image-release`, `node-host-ops` in `.agents/skills/` for the
patterns behind these fixes.

## Open items

Per `RULES.md` Rule 1 (2026-11-18), agents run routine checks themselves;
items 1, 4, 5 and 6 below were closed that way.

1. ~~Attended ntfy receipt~~ **Closed — verified by the agent** in the agent
   browser on 2026-11-17: signed in as `bortus-subscriber`, subscribed to
   `bortus-certificates`, and the "✅ Attended receipt test" title and message
   rendered legibly (screenshot under the agent-browser screenshots folder).
   Recorded as agent-verified, not as James personally viewing it.
2. ~~Sudo-password-gated host work~~ **Done 2026-11-17**, with the owner
   supplying the sudo password via a one-time 0600 file (deleted
   immediately after use, never pasted in chat). Docker stopped and
   disabled on node01 (FORWARD policy unchanged, Calico rules still take
   priority; Docker's own iptables chains remain as a harmless leftover,
   not fully removed). The F13 TLS-expiry monitor is deployed and verified
   live on node02 (see above) — this took two additional fix cycles on top
   of the original play.
3. **D3** (optional `notificationDelivery` field default) — **committed**
   (previously only an uncommitted edit, which a commit-based release build
   would have silently left out); 7/7 control tests pass. Ships with the next
   regular BORTUS release by James's decision. At that release: include it,
   then check an older snapshot without the field still renders and a
   current one still shows its real delivery state.
4. ~~kubelet CSR approval gap~~ **Closed 2026-11-18.** node01 and node03 now
   renew unattended; see `docs/NOTIFICATIONS.md` "Unattended kubelet
   certificate renewal". Evidence:
   `…/certificates-qualification-20261116/kubelet-multinode-rollout/`
   (watch/renew/verify per machine, plus the first node01 attempt that
   rolled back because the test script read the log too early).
5. ~~proxy.branconet.lan self-signed~~ **Closed 2026-11-18** (private charts
   `f269e31`); see `docs/NETWORK-HARDENING.md`.
6. ~~Operator-host DHCP reservation unverified~~ **Closed 2026-11-18** — the
   reservation lives on node03's DHCP server and matches this computer; see
   `docs/NETWORK-HARDENING.md` "Operator-host dependency".
7. This production monitor/notification/watchdog codebase
   (`certificate_monitor*.py`, `run-certificate-monitor.py`, etc.) was
   **entirely untracked in git** before this session despite running live on
   node02/node03 for weeks — only the files this session touched are now
   committed. A broader repo-hygiene pass to commit the rest is a separate,
   larger task.

## 2026-11-18 code-review fixes (six findings, all closed)

A review of the uncommitted changes found six defects; all are fixed and
verified. Commits `5e28fe6b`, `c9d24efa`, `f0cac82f`, `ee222c82`, `8eef5862`.

1. **Firewall no-ops (high, `5e28fe6b`)** — six restriction profiles whose
   published Service port differs from the pod target port (vaultwarden,
   mealie, aplb, minecraft-website, web-apps, ruckus-bot's 8088) never
   restricted anything: at the forward hook the packet already carries the
   translated pod port. Now matched pre-NAT in `prerouting` at -110, scoped
   to the node IP destinations; deployed to all three nodes and proven with
   accept/reject counters plus a temporary probe table.
2. **Undelivered expiry alerts (high, `c9d24efa`)** — the ntfy sender
   rejected the monitor's `tls-endpoint` events, so kubelet/kubeadm
   certificate-expiry alerts never reached the topic. Fixed, deployed to
   node02, and proven end to end through the real sender loop.
3. **Rollback hazard (high, `f0cac82f`)** — the rotation tool restored from
   a fixed shared backup on *any* failure, so a pre-flight refusal could
   overwrite kubelet's current certificate with an older one. Per-attempt
   verified backups; restore only after this attempt changed files; failed
   rollbacks are loud. Both paths proven live on node02.
4. **Wrong readiness names (medium, `ee222c82`)** — site.yml waited for the
   old SSH aliases after registration moved to node01/02/03; a successful
   install would always report failure. Derives wait targets from the same
   inventory field; verified live.
5. **Orphaned running job (medium — in the working tree, not committed)** —
   after a dashboard restart, a job row stuck at "running" disabled Run
   forever (stop 409, delete refused). New `src/lib/job-reconcile.ts`
   reconciles stale unowned rows to a terminal "interrupted" state,
   preserving the log; stop and history call it; the SSE stream treats
   "interrupted" as done. 8 unit tests plus a stream smoke test pass
   (8/8). **Deliberately uncommitted**: the touched routes and
   `job-stream.ts` are part of the large staged dashboard refactor this
   repository is preserving, so the whole fix rides with that body rather
   than sweeping four of its files into a fix commit.
6. **Release verifier could pass on the old pod (medium, `8eef5862`)** — now
   requires the exact pinned digest, a reconciled deployment and a Ready
   pod of the current ReplicaSet, and checks routes on that exact pod.
   Old-pod-partial-rollout now fails by unit test; live run passes.

## MCP and tooling gaps identified this session

- Kubernetes inventory MCP only lists pods/events — no Flux, HelmRelease,
  Certificate, CSR, or Longhorn status, forcing fallback to the admin
  kubeconfig for routine checks. A read-only extension is proposed in
  `docs/KUBERNETES-MCP-READONLY-CANDIDATE.md`.
- No read-only host-inventory MCP for the three nodes (systemd unit state,
  nftables counters, listeners) — everything went through ad-hoc Ansible.
- No ntfy MCP (subscriber poll + header-correct test publish) — would have
  caught F1 before it reached production.
- `netgear-xr500` MCP exposes DHCP pool bounds but not per-device
  reservations — can't verify item 6 above without a UI check or a new tool.
