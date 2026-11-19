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

## Start here — checkpoint 2026-11-18

Read this section, then the rest of the file, then `MEMORY.md`. The branch is
`codex/seerr-cluster-security`; the checkpoint commit is `fdfa9360` (pushed after
this section was written — check `git log -1` and `git status -sb`).

### What this session delivered

1. **The shared MCP now lives in this repository.**
   `mcp-servers/bortus/` holds `server.py`, `launch.py`, `runner.py`,
   `policy.py`, `kube.py`, `engine.py`, `refresh-kubeconfig.py` and focused
   tests, copied out of the Veyra monorepo, which no longer carries it.
   Registration is **project-local** in `opencode.json` (never global):
   fixed `cwd`, `pool: true`, `protocol: "2026-07-28"`.
2. **Protocol migration.** The server is dual-era: modern requests are served
   statelessly (server/discover, `resultType`, `ttlMs`, `cacheScope`,
   `-32022` for an unknown version) and `initialize` still selects legacy
   semantics. The proxy renews a stale inventory kubeconfig and restarts the
   child so a pooled connection outlives the 12-hour token.
3. **Ruckus rollout cleared and deployed.** Image
   `docker.io/jtmb92/ruckus-bot@sha256:45c942c97add…` published, charts
   `validated` promoted to `217f24f` after 45 tests plus chart validation,
   pod `ruckus-bot-7b6df4897-c8xz4` Ready with 0 restarts on node03 and
   `GET /health` returning `{"status":"ok"}`.
4. **Cluster and repository audit completed.**
   `docs/audits/2026-11-18/cluster-repo-audit.md` plus three unapplied
   proposals in `docs/audits/2026-11-18/proposed/`. Headline risks: no API
   server audit logging, Pod Security unenforced in 25 of 30 namespaces, 24
   namespaces with no NetworkPolicy, `bortus-secrets` RBAC replicated into
   seven namespaces, newest Longhorn backup three days old.
5. **Skills installed in this repository:** `bortus-local-test` and
   `kubernetes-repo-audit` under `.opencode/skills/`.

### Verification already run (do not repeat)

- `python3 -B -m unittest discover -s mcp-servers/bortus/tests -p 'test_*.py'` → 40 tests OK.
- Modern: `server/discover` returns `2026-07-28` first, `tools/list` and a live
  `pods_list` succeed with `resultType: complete`; legacy `initialize` still
  answers `2025-06-18`.
- Renewal: an aged kubeconfig (7 h) was refreshed in place and the call
  succeeded.
- `opencode mcp list` in this repo shows `bortus connected`; from another repo
  the server is absent, as intended.

### Open items, in priority order

1. **Audit remediation has not started.** Begin with API server audit logging,
   then one namespace of default-deny NetworkPolicy (`kube-system`, `traefik`,
   `vaultwarden`, `wordpress` are the useful first four), then Pod Security
   `baseline`. Proposals are ready; nothing is applied.
2. **Pooling observation is still inferred, not measured.** The shared
   OpenCode server restarted repeatedly during the two-directory test, so no
   stable "two locations, one child" PID count exists yet. Config is correct;
   capture the count in a quiet window.
3. **Charts publisher limitation.** `local-publish.py` refuses this
   environment (`native_wsl_exact_sha_required`) because there is no native
   WSL clone of `branconet-charts`. The ruckus promotion ran the same gates
   manually and fast-forwarded `validated`. Either create the WSL checkout or
   fix the publisher; otherwise every release repeats that manual step.
4. **Longhorn backup freshness and restore evidence** (audit B2) and the
   `bortus-secrets` RBAC narrowing (A4) remain open.
5. **`docs/memory/planning-directory.json`** is untracked and was left alone.

### Paste this into the new chat

> Continue the BORTUS work in `/home/brajam/repos/branconet-homelab` on
> `codex/seerr-cluster-security`. Read `docs/operations/handoffs/opencode-takeover.md`
> first, starting at "Start here — checkpoint 2026-11-18", then `MEMORY.md`.
> Do not redo the MCP move, protocol migration, ruckus rollout or audit — they
> are done and verified. Start with audit remediation: API server audit
> logging, then default-deny NetworkPolicy for one namespace at a time, then
> Pod Security baseline. Read-only verification is fine; deployments go
> through `branconet-charts` and Flux. No subagents.

### Boundaries that still apply

No subagents. Repository-specific skills and MCP entries stay in the
repository, never in global config. Read-only until a change is explicitly
authorized; the audit proposals are review material. Secrets are read only
through the scoped MCP tool, never printed. One checkout: do not create
another.

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
