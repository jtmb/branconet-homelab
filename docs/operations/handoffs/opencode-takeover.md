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

## Start here — checkpoint 2026-11-19

Read this section, then the rest of the file, then `MEMORY.md`. Branch
`codex/seerr-cluster-security`; confirm the tip with `git log -1` and
`git status -sb` before editing.

### What this session delivered (all verified by the agent)

1. **API server audit logging (audit A1), live on all three API servers**
   (`6e472ca7`; runbook `docs/API-AUDIT-LOGGING.md`). The audit's draft policy
   would have written Secret values and issued tokens to disk; the applied
   policy keeps them at Metadata, and a first-match test enforces it.
   Rolled out node02 → node03 → node01 with per-attempt backups, then
   persisted in `kubeadm-config`. Each new pod Ready with 0 restarts, probe
   recorded at Metadata, 0 credential bodies, 20 RBAC changes with bodies on
   node03, Flux 12/12 + 36/36 Ready, VIP back on node01.
2. **vaultwarden default-deny NetworkPolicy (A3)** through charts `0a5cf6f`,
   fixed in `9e6aa2c` (the hosting node sees the real client before SNAT; see
   `docs/NETWORK-HARDENING.md`). Ingress mirrors the mesh `allowed-callers`
   policy; egress is DNS plus public web ports. Before/after table in
   `docs/audits/2026-11-18/cluster-repo-audit.md` under A3.
3. **vaultwarden Pod Security `baseline` (A2)** through charts `6f8d1e9`;
   template admitted, privileged variant refused, pod not restarted.
4. **Charts publisher works here** (previous open item 3). All three charts
   commits went through `scripts/local-publish.py` prepare → check (45 tests,
   validator) → publish; the earlier refusal came from missing
   `--source-sha`/`--stage`. Exact commands are now in
   `.agents/skills/private-chart-delivery/SKILL.md`.
5. The untracked audit report was committed as-is (`cb87a777`) before edits.
6. Charts `main` is at `79014bd` (docs only: published ports bypass namespace
   policies for pods); `validated` stays at `6f8d1e9` until the next publish.
7. **MCP servers consolidated here and migrated to MCP 2026-07-28.**
   `bortus` (already here) plus `netgear-xr500`, `pihole-dns` and
   `plex-inventory` (moved from Veyra) live in `mcp-servers/`; the LAN three
   use `mcp-servers/_shared/dual_era.py`, which keeps their legacy replies
   unchanged. Two `bortus` bugs were fixed: a stale-token refresh swallowed
   OpenCode's `server/discover` (pooling never worked) and an oversized or
   timed-out inventory reply was handed to the next caller. Verified by the
   agent: live reads identical in both protocol eras, one pooled process per
   server across directories, and a project outside this repository with
   copied entries reused the same processes. Commits `c4d15b1b`, `eec2ffc4`,
   `f9b896d2`, `172ec228`. Veyra deletion commit `b6457ce8b` is local and
   unpushed by James's choice; `agent-browser` stays in Veyra.
8. **MCP defaults (James, 2026-11-19): only the global `wsl-interop` connects
   automatically.** Every entry in this `opencode.json` (`agent-browser`,
   `bortus`, `netgear-xr500`, `pihole-dns`, `plex-inventory`) and the global
   `browse` carry `"disabled": true`; connect one for the current directory
   when a task needs it and disconnect it after (`mcp-servers/README.md`).
   Other repositories may copy an entry unchanged to share the same process
   (memory note `mcp-shared-connections`).
9. **Global `browser-choice` skill and global AGENTS.md "Browsers" section.**
   Every chat is told to choose `browse` (the owner's shared real browser,
   needs the extension) or `agent-browser` (isolated, agent-only), connect
   only that one, and use `webfetch` for plain public pages.

Receipts: `/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/audit-remediation-20261118/`
(audit rollout) and `.../local-charts-publisher/local-charts-publish-{1f8535e1…,9f0672ed…,0d2dea40…}/`
(publisher). The temporary `netpol-probe-20261119` namespace was deleted.

### Open items, in priority order

1. **Continue A3/A2 one namespace at a time:** `kube-system` (only CoreDNS,
   calico-kube-controllers and snapshot-controller are pod-network; CoreDNS
   upstream addresses must be confirmed first), then `traefik` (egress to
   every backend plus API server), then the other application namespaces.
   Follow charts `docs/NAMESPACE-NETWORK-POLICIES.md`; `wordpress` has no
   pods and is last.
2. **Decision for James: vaultwarden's `:8096` is reachable from any pod.**
   A probe pod in another namespace got 200 from `node:8096` on all three
   nodes. kube-proxy SNATs it to node or tunnel addresses that the mesh and
   NetworkPolicy must admit, and the nftables profile admits the pod CIDR.
   This predates this session. Proposed fix: measure in-cluster callers with
   `conntrack -L --dport 8096`, then drop the pod CIDR from the `vaultwarden`
   nftables profile. Details in the audit's A3 section.
3. **Audit log follow-ups:** measure the gzip ratio after node01's first
   rotation (about 100 MB, a few hours after enablement); node01 keeps
   about 3 days; logs are node-local only.
4. **`docs/CLUSTER-TLS.md` is untracked** (1,536 lines of earlier work). It
   holds a four-line rollback note from this session, left uncommitted so
   the whole file is not swept in; commit it in the repo-hygiene pass.
5. **MCP follow-ups.** The servers are now disabled by default, so the
   2026-11-19 pooling and live-call evidence was taken while they were
   enabled; connect one and rerun its README check if behaviour is in doubt.
   `agent-browser` was not migrated (still in Veyra, not pooled, protocol
   unchecked). In `~/.config/opencode`, the skill catalog index row for
   `browser-choice` is left uncommitted because that file also carries
   another session's pending skill changes.
6. Longhorn backup freshness/restore evidence (B2) and `bortus-secrets` RBAC
   narrowing (A4).
7. `docs/memory/planning-directory.json` is untracked and was left alone.

Pre-existing, not investigated: `bortus-notifications/private-ntfy-rotation`
fails occasionally (2 retained failures 32 h apart; recent runs pass), and
`ingenium/veyra-workspace-preview-r14` is `Unknown` for 10 days.

### Paste this into the new chat

> Continue the BORTUS work in `/home/brajam/repos/branconet-homelab` on
> `codex/seerr-cluster-security`. Read `docs/operations/handoffs/opencode-takeover.md`
> first, starting at "Start here — checkpoint 2026-11-19", then `MEMORY.md`.
> Audit logging, the vaultwarden NetworkPolicy/Pod Security changes and the
> MCP consolidation are done and verified. Only `wsl-interop` connects by
> default; connect another MCP (for example `bortus`) only when the task needs
> it. Continue A3/A2 with the next namespace (`kube-system`) through
> `branconet-charts` and the local publisher. No subagents.

### Boundaries that still apply

No subagents. Repository-specific skills and MCP entries stay in the
repository, never in global config. Secrets are read only through the scoped
MCP tool or the documented saved-credential helper, never printed. One
checkout: do not create another. Charts changes go through Windows git and
`scripts/local-publish.py`, never a manual `validated` push.

### Earlier checkpoint (2026-11-18), still accurate

The shared BORTUS MCP lives in `mcp-servers/bortus/` with project-local
registration and dual-era protocol support (40 tests); the ruckus rollout is
live on charts `217f24f`; the audit is in `docs/audits/2026-11-18/`; skills
`bortus-local-test` and `kubernetes-repo-audit` are in `.opencode/skills/`.

## What's deployed and healthy (verified 2026-11-17)

- 3/3 nodes Ready (v1.37.2); 12/12 Flux Kustomizations and all HelmReleases
  Ready; 15/15 cert-manager Certificates healthy; 0 pending CSRs.
- ruckus_bot 1.1.0 deployed from charts `217f24f` on
  `sha256:45c942c9…`, pod Ready with 0 restarts (2026-11-18).
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

## 2026-11-18 code-review fixes and follow-up

A review of the uncommitted changes found six defects. Commits `5e28fe6b`,
`c9d24efa`, `f0cac82f`, `ee222c82`, `8eef5862` cover the five operational fixes
below; provisioning recovery remains with the unshipped dashboard refactor.

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
5. **Orphaned running job (medium — working tree, not shipped)** —
   an inherited Linux lock now blocks a new launch until the local runner
   releases the lock, even if the dashboard disappears. Jobs with unknown
   evidence stay blocked; a confirmed local exit without a result is marked
   `interrupted`, keeping the saved output. A real subprocess-death check
   with in-memory SQLite and a stream check passed; the running dashboard
   still needs end-to-end verification. A browser check of the compiled
   provisioning page against isolated fixture endpoints verified Run was
   disabled while running, then re-enabled after interruption, with the
   partial log retained. Preserve the existing
   staged refactor rather than sweeping those files into a fix commit.
6. **Release verifier could pass on the old pod (medium, `8eef5862`)** — now
   requires the exact pinned digest, a reconciled deployment and a Ready
   pod of the current ReplicaSet, and checks routes on that exact pod.
   Old-pod-partial-rollout now fails by unit test; live run passes.

## Subscriber credential follow-up

The subscriber password was rotated again after the earlier exposure. The
replacement is in James's Windows Credential Manager; no plaintext was
printed, and no historical plaintext was reused. The agent verified that
the stored replacement could read the exact private test notification over
trusted HTTPS. The previous verifier was replaced; the old plaintext was
not submitted as a negative test.

James subsequently requested the D3 release now. The committed frontend at
`776a02879642a749ac1abd55ba2414dcbff0865f` differs from the deployed source
`82580115b85a9aec0c092c2eda03328b6a810444` only in the fallback and its test.
The exact-pod verifier accepts a full new image digest explicitly and passed
against the current pod as the rollback baseline. Do not include the staged
dashboard refactor in that build.

The agent exercised both D3 states in a browser with the parser and monitor
panel loaded directly from the committed candidate: an older snapshot
remained monitoring and showed “no sender configured”; a current snapshot
remained monitoring and showed “delivery confirmed by the sender.” This
was an in-memory fixture, not a deployed image or a production data change.
The live rollback baseline remains `44a163a9…` on Ready pod
`bortus-6b77c798cf-ts757` at preflight. No new image or chart pin was created.
The pending build and export require storage admission under the existing
100 GB ceiling; the retained mixed recovery capsule remains protected and
its canonical attribution unresolved. The previous release's saved image
archive alone used 1,149,636,096 bytes.

Storage follow-up: removed only the `image.tar` transport copies from
`swarm-history/bortus-preload-c29fc8c44847172e040e83df11c51ad42f1da51e`
and `swarm-history/bortus-preload-7e30b9b428a66cd3f5e618cec5e694d5f03302ac-attempt-a7d0c401e1b2`
on the H-backed `storage-migration/builds/linux-tree-store/files` mount.
Both completed preloads retain their receipts, logs and byte-identical
export originals; the uncertain preload was untouched. Verified SHA-256,
independent inodes, containment and process/container/mount references
before deleting. Linux filesystem usage dropped by 2,297,221,120 bytes;
this is not a Windows physical-space claim.

After cleanup, the measured logical subtotal of named roots is
56,177,531,539 bytes excluding the mixed recovery capsule. Reserving that
protected capsule in full (53,920,129,364 logical bytes) puts the partial
account at 110,097,660,903 bytes before any release output. This is a
conservative admission calculation, not final ownership attribution:
two protected subtrees were unreadable and other mixed/shared directories
are not included. The cap could only admit the prior export size alone
with no more than 42,672,832,365 capsule bytes attributed to this project,
before allowing for any omitted usage, builder layers or preload copies.
The current staging path keeps a second archive during preload (two
4 GiB limits); avoiding only that copy does not resolve the conservative
overage. No image build or rollout was started.

The existing storage ownership ledger (`docs/operations/DOCKER-H-STORAGE.md`,
“Certificates & Trust build admission”) resolves the operational charge:
BORTUS/cluster operations owns full mixed-member recovery and must count
all 53,920,129,364 capsule bytes once. The recovery receipt is for a single
raw ext4 file with verified full reconstruction; the 255-entry historical
member list records names and review classes, not member sizes, owners or
compressed byte shares. It cannot establish an alternate split. Do not
mount or restore the raw image to invent an attribution.

With that charge, the known subtotal is 10,097,660,903 bytes over the
existing cap without any new output. A one-archive path at the prior
archive size would be 11,247,296,999 bytes over; the supported export and
preload path at that size would be 12,396,933,095 bytes over, before build
layers or omitted roots. The latter is a comparison using measured prior
output, not a D3 peak measurement. An approved change to the capsule
accounting or a bounded release-stage exception is required; the previous
existing-image review exception does not apply.

D3 release-input preflight passed the actual builder validator in memory:
164 files from commit `776a02879642a749ac1abd55ba2414dcbff0865f`,
9 excluded, 296,451 compressed bytes, SHA-256
`5f943b24a261e05eb5fd090402a4f6807ccf1382614110930f16f0c86cbb57ca`.
No image or disk output was created by this check. The read-only registry
lookup did not establish an existing candidate for this commit; it is not
proof the tag is absent. The separate provisioning qualification does not
gate the D3 release.

James approved proceeding with D3 now, including a one-time storage
exception for this release only. Generated the exact H-backed context,
verified it again, and dispatched the uniquely tagged build to node01.
`ui-release/d3-build-started.json` records the exact commit, tag and
provenance labels. Reconcile its corresponding outcome before any retry.
The existing Windows credential broker verified private registry access
and that the exact candidate tag was absent before publication. All
three containerd filesystems reported at least 19.9 GB free in preflight.
D3 deployed through private charts commit `b294521ab7ff9e42597649ade8bce199a9f73c2c`.
The exact image `96910c7b4f0287e5029107b8fcb67f9b43ca6cd96187d2211b78a98c87cf1edf`
was verified complete and unpacked on all nodes before the pin. The chart
publisher passed 45 tests and chart validation. Its watcher stopped between
validation and promotion; the existing publisher then promoted the exact
successful receipt without rerunning validation. Live pod
`bortus-6f87b47b88-2rzb7` passed the exact-image/route/HTTPS verifier with
zero restarts; Helm reported `UpgradeSucceeded`. Node01 Docker is inactive
and disabled again. Removed `ui-release/d3-image.tar` and
`ui-release/d3-registry.oci.tar` after preload and rollout, freeing
1,480,050,176 logical/allocated bytes; kept the exact published digest,
source, build, export and live verification receipts.

Signed-in browser and API checks passed for the Certificates page itself,
but exposed a separate compatibility defect: the live snapshot includes
six `tls-endpoint` rows, which the deployed parser rejects before showing
notification state. The working-tree parser fix accepts the bounded endpoint
shape without changing the required Kubernetes sources. Eight focused tests
passed; passing the unchanged live ConfigMap through the corrected parser
returned `monitoring`, `delivered`, six endpoints. Source commit
`560db763e7f8d2ade2be469bd9a7b521c28469e8` is verified on the existing
remote. Its frontend diff from the deployed D3 commit contains only the
parser and its test, excluding all provisioning changes. The exact
committed context was verified and its build dispatched to node01; see
`ui-release/tls-control-build-started.json`. Build and private publication
passed. The exact `026dae76d798a0b783202a8930696ec9958ca7e4142fe93b1260f362ec34a8e5`
image was verified complete and unpacked on all three nodes; node01 Docker
was stopped again and its FORWARD policy stayed DROP. The four-path private
charts change `43fca34fb235389400cc011515576f2396498dac` passed all 45 tests
and chart validation, and Flux applied it. Exact pod
`bortus-79bf8cc46d-nmckh` was Ready with zero restarts; see
`ui-release/tls-control-live-verification.json`. The signed-in agent
browser showed **Monitoring** and **delivery confirmed by the sender**,
agreeing with the live API (`200`, `monitoring`, `delivered`, six TLS
endpoints). No production snapshot was modified. The disposable
`ui-release/tls-control.oci.tar` was removed after rollout (330,414,080
logical / 330,420,224 allocated bytes); private registry and node copies
and verification receipts remain. The provisioning refactor was not
released; its full operator restart check remains separate.

Full operator-dashboard restart preflight: retained Next.js 15.5.28,
Prisma 6.19.3 and React 18.3.1 match the operator lockfile, but both
retained production server trees have zero occurrences of the restart
lock configuration or recovery marker in their compiled server code.
Their `/api/deploy/start` bundles are byte-identical to each other and
predate the fix. `next start` consumes a prior build; `next dev` writes
its build directory even with the existing dependencies. No supported
zero-build-output launch of the changed dashboard was identified.
Comparable prior successful H builds added up to 207,564,800 measured
bytes at peak; this does not cap an unrun operator build. Do not overwrite
the retained production build or point tests at the real database.
Once scoped output is admitted, use a persistent synthetic SQLite DB,
a harmless local child holding the real lock, and loopback browser
access. Verify duplicate Start refuses before any inventory writes,
then restart the dashboard, release the child, and verify `interrupted`,
retained output and Run re-enabled. Do not launch a real playbook.

Restart-test admission follow-up: the retained H dependency tree matches
499 installed entries of the current operator lockfile, with zero
required entries missing and zero version mismatches. `bwrap` successfully
started a read-only isolated process, so no dependency installation or
write access to the current checkout is necessary. The closest prior H
qualification added 207,564,800 bytes at its build peak and 933,888 bytes
in its fixture run. A proposed one-time **512 MiB** incremental H ceiling
would cover only the rebuilt operator dashboard, synthetic state and
small receipts, with a stop condition at the ceiling and cleanup before
close. This is not a measured current build peak or permission. The
earlier exception covered the Certificates release; the restart test
was not started under it.

## MCP and tooling gaps identified this session

- **Shared BORTUS MCP:** James requested one repo-independent credential
  workflow and a rename from `kubernetes-inventory` to `bortus`. The
  [implementation plan](../../planning/operations/00_START_HERE.md) and
  [fresh-chat handoff](../../memory/08_BORTUS_MCP_HANDOFF.txt) are ready.
- **Shared BORTUS MCP implemented (2026-11-18):** W1 and W2 are done. The
  Veyra checkout now has `mcp-servers/bortus/` (server, policy, Secret
  reader, Docker client, runner, launcher, 29 tests) and the old
  `kubernetes-inventory/launch.py` delegates to it. Registration moved to
  one global `mcp.servers.bortus`; this project and `ruckus_bot` no longer
  declare their own copy. Inventory parity was checked against the live
  cluster (same three tools, same table, same paging count) and a live
  `pods_list` through the new registration succeeded. Evidence:
  [implementation record](../../planning/evidence/2026-11-18-bortus-mcp-implementation.md).
  W3 read path was then proven live: a ServiceAccount limited to `get` on
  one Secret name read it over TLS, delivered it into a real container as an
  env value and a file, was denied every other name and verb, and left no
  container behind. The one property this host cannot provide is recorded as
  accepted residual **X1** in `records.json`: the runner shares the only
  interactive account, which is in `docker` and `sudo`. The
  `bortus-local-test` skill is installed at
  `.opencode/skills/bortus-local-test/` in this repository and was verified to trigger
  in a fresh session. See the same implementation record for the matrices.
- Plan delivery receipt (2026-11-18): task-owned PID `3811340` listens
  only on `127.0.0.1:18444`. The exact plan HTML, ZIP, and two workbook
  routes are generated in memory by `docs/planning/bortus-mcp/export_plan.py`;
  no generated package or certificate copy was written. Linux verified
  all 15 routes with the existing localhost certificate; Windows verified
  the plan HTML, ZIP and tracker. Unlisted routes returned 404. Keep the
  process only for review/download, then stop this exact owned process.
  Certificate: `/mnt/h/AgentArtifacts/projects/veyra/runs/harness-completion-20261115/private/tls/localhost.crt`.
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
