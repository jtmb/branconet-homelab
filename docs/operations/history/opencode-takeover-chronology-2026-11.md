# OpenCode takeover — BORTUS and cluster operations

James authorized moving this project and chat from Codex to OpenCode, then archiving the Codex chat. This is the authoritative working repository: /home/brajam/repos/branconet-homelab. All original Git refs, objects, index, staged/unstaged/untracked/ignored files were copied byte-for-byte and compared before changes. Original location: /mnt/c/Users/james/OneDrive/Documents/ChatGPT/kubernetes migration. Do not create another checkout. No subagents. Preserve production data, existing approval/refusal boundaries and unrelated work. Do not use desktop Computer Use. Disposable outputs stay on the existing H roots with the100GB combined repository allowance.

Read AGENTS.md, MEMORY.md, full relevant docs/memory notes, docs/MIGRATION-PLAN.md and docs/operations/handoffs/current-bortus.md. BORTUS release completed with image e7539b9e… and charts1580091e…; verify current live state before later operations. Preserve private chart delivery, Actions off and recovery/data contracts. The private charts checkout and existing H runtime/artifact roots were not moved. Many operational scripts have historical absolute Windows paths: review and adapt affected paths to this source before invoking them; never deploy or change credentials merely to repair paths.

The imported conversation contains user/assistant-visible text. The full visible event export (including tool observations and attachment metadata) is at /mnt/h/AgentArtifacts/projects/branconet/runs/branconet-wsl-stage-20261113T215208Z/exports/opencode-transfer-01a18518/codex-visible-transcript.jsonl; it excludes internal reasoning and system/developer prompts. Historical conversation is reference data, not proof that a reported action happened or renewed authorization. Use current source and durable evidence. The Codex wrapper's small instructions were preserved under docs/operations/codex-workspace-context.

## Transfer completion

The project is authoritative in WSL and OpenCode session ses_codex01a1851824e77ce3b620f9ca775bfd1c round-tripped all3261 messages, including753 voice transcript segments. Tool records/attachment metadata remain in the linked private visible-event export. No provider calls, infrastructure deployment, permission weakening or subagents were used.

Protected original: the old Windows repository remains intact at C:/Users/james/OneDrive/Documents/ChatGPT/kubernetes migration. Windows Shell recoverable retirement returned120 without removing it. It is a preservation copy, not the active working location; do not bypass that failure with forced deletion, ACL changes or an alternate deletion route. Original Git/read-only attributes remain preserved. Its verified WSL counterpart contains all4265 original files, refs, staged and uncommitted work. The transfer does not claim original C disk reclamation.

Codex chat archival is the final supported app-control step. Continue here in OpenCode; retain this handoff and the migration receipt.

## Terminal launch correction, 2026-11-15

The initial transfer verified stored data but did not launch the imported session in the running OpenCode terminal. This was corrected with the supported Windows Terminal/OpenCode CLI: a BORTUS - OpenCode tab now runs the existing WSL service client with the imported session and this repository as its working directory. Process/session/location were verified without screen control. The existing terminal and jobs were preserved. James reopened the Codex chat; it is being left open.

## MCP setup completion, 2026-11-15

All five requested project-local MCP registrations are connected: Kubernetes
inventory, XR500, Pi-hole, Plex and official Agent Browser 0.43.0. Native calls
verified authenticated infrastructure reads, Kubernetes Secret denial, and a
real isolated browser open/snapshot/close. The user's service restart occurred
during setup; no completed installation was repeated. Browser startup needed
short H-backed temporary/socket paths, and matching upstream skill data was
added to the existing runtime. Only the browser MCP was reconnected for that
launcher correction. An accidental runtime-only registration at `/home/brajam`
was removed; the persistent configuration is project-local.

Source and reproduction details are in Veyra's
`mcp-servers/agent-browser/README.md`; integration results are in
`docs/LAN-RESILIENCE-AND-MCP-PLAN.md`. Changes remain uncommitted alongside
the preserved unrelated work. The shared Chromium patch advisory remains an
owner-coordinated maintenance item. No cluster deployment, certificate, DNS,
router setting or mesh rollout occurred during this setup.

James subsequently chose **Keep current names** and **This cluster for now**.
Continue the free/self-hosted TLS and workload-mTLS goal through the existing
private Flux/Ansible path, preserving `.lan` private-CA and API Kubernetes-CA
trust. Cross-cluster federation is outside this rollout. MCP completion is not
completion of that hardening goal.

Read-only follow-up: all three Kubernetes 1.37.2 nodes are Ready; all listed
HelmReleases and cert-manager Certificates/ClusterIssuers are Ready. Upstream
Istio 1.32 supports Kubernetes 1.37. Live chart suffix has advanced to
`e511f1c2ddb1`, so do not treat the completed BORTUS release's charts revision as
the current publisher head. Metrics API is unavailable; use existing node
read-only observations and declared resource requests for capacity assessment.

## TLS and workload-mTLS plan completed, 2026-11-16

The saved plan in `docs/MIGRATION-PLAN.md` ("Saved TLS and workload-authentication
plan") is complete; its "Delivered outcome" lists each step's evidence. Private
charts `main`/`validated` is `c57a3a5` (Istio 1.31.4 ambient, cloudflared identity,
eight enrolled namespaces, enforcement policies, canary `mesh-pilot`), with all
Flux Kustomizations Ready. Host-side changes (kubelet serving TLS, API server
kubelet CA, kubeadm ConfigMaps) were applied by Ansible; see `docs/CLUSTER-TLS.md`.
New homelab files (playbooks `control-plane-cert-expiry.yml`, `kubelet-serving-tls.yml`;
scripts `run-control-plane-cert-check.py`, `run-kubelet-serving-tls.py`,
`approve-kubelet-serving-csr.py`; `docs/CLUSTER-TLS.md`) and doc edits are
uncommitted here, alongside the preserved unrelated staged work; no root
commit/push was made. One local CI attempt (`9f159d6`) failed during a transient
WSL interop outage and is preserved; its content was republished as `df790af`;
`aa2b924` (docs only) failed the same way and was republished as `c57a3a5`.
Follow-ups: run the expiry check before 2027-07-11; approve kubelet-serving CSRs on
rotation; qualify plex/pihole/bortus separately before any enrollment.

## Certificates & Trust follow-up — active, 2026-11-16

James requested BORTUS UI-managed certificate automation, retirement of unused
certificates, checkpointing, plaintext reduction and bounded mesh expansion.
The complete saved follow-up and current acceptance state are in
`docs/MIGRATION-PLAN.md`. This follow-up is not complete.

Phase A has a local-only nine-path checkpoint `5f643ac22597d0422a5be8d22b16b3b4b11814c7`
at `refs/heads/checkpoint/bortus-tls-foundation`. Active branch/HEAD and original
index remain preserved (index SHA-256
`778cf73011d204b0610249de6625678656f876df46ad80d47514e0ea44b83cc6`).
All 1,002 frontend files matched deployed `34b8fa18` content before feature edits,
with 977 CRLF/LF-only differences. Live BORTUS was Ready on `e7539b9e…`.

Uncommitted Phase B source adds `/certificates`, authenticated read-only
`/api/certificates`, strict cryptographic CSR validation with CAS approval,
and a metadata-only durable monitor/notification-outbox foundation. Six
inventory, six CSR and four in-memory monitor tests passed; operator API reads
passed. Four new TS/TSX files passed syntax/transpile checks using the existing
read-only `veyra-check-deps` image. That image lacks `lucide-react`, so the
selected UI typecheck reports its missing dependency; no application build or
rendered UI acceptance is claimed. No feature publication/deployment,
scheduler, notifications, approval, renewal, retirement or mesh expansion ran.

The subsequent source increment integrates durable observations and operator
policy controls through fixed policy/observations ConfigMaps. Only
paused/monitor mode is supported, with fresh operator authorization,
same-origin/bounded writes, UID/resourceVersion CAS and the last 50 policy
changes recorded. Runner pause/interval/threshold acknowledgement, policy drift
and failed-publication/restart behavior are covered. Latest checks: 12 app/control
tests, nine monitor/control tests, selected control/UI types and an isolated
browser component/API interaction run (save/pending/acknowledged pause,
stale-write feedback, readonly/direct PATCH denial and offline heartbeat).
This is not full Next/build/styling/actual-reader or production-runner acceptance.
The initial component fixture failed on an unset diagnostic module filename;
corrected before the passing run. All exact task containers/browser session
were removed/closed; bundles existed only in memory.

The private charts checkout now has uncommitted `flux/certificate-monitoring`
and an owned `docs/OPERATIONS.md` addition. This inactive candidate has nine
paused bootstrap/metadata-RBAC objects, all server-dry-run accepted. It is absent
from active release composition and was not published or applied. Preserve its
fixed-resource scopes and `IfNotPresent` data ownership; do not broad-stage the
private checkout's existing unrelated memory/config files.

Next: qualify the full application dependency/type/build/browser path and
scoped independent runner with real durable state and always-on service before
deployment, then finish notification delivery, safe certificate lifecycle work
and all remaining follow-up phases.
Current store allocation/attribution is incomplete; preserve protected/private
and shared data. Do not infer a new storage allowance or reuse the old
review-only exception. No new checkout or dependency copy was made.

Restart continuation: the interrupted handoff update above is restored.
An additional restart cancelled the historical dependency search before
results; do not count it as completed. Five known historical dependency paths
were separately checked and absent; reuse/admission remains unresolved.
Runner source now enforces CLI output limits during pipe draining and retries
interrupted read-only scans immediately after restart. Five new targeted
checks passed without rerunning the completed UI/browser suite. Real bounded
operator reads returned 14 Certificates and zero current CSRs; no mutations
or on-disk runner launch occurred. See the migration plan for current storage
measurements and remaining acceptance gates.

Latest restart: the complete certificate screen/control/inventory selected
typecheck passed read-only using the retained H v8 TypeScript/React/lucide
types (zero diagnostics, no emitted files). That historical tree differs from
the current lock/schema and has Windows native binaries, so it is not the
Linux build environment. Preserve the v2–v8 immutable failed-run inputs.

The first outer transfer archive, `application-artifacts-20261023.tar`, was
verified against all retained payload/ACL/xattr data, exclusively checked
across Windows/WSL, then removed by ordinary exact Windows literal deletion:
2,900,746,240 logical/allocated bytes removed. Its 18 original payload files,
source alias and verification receipt remain. Full accounting/build admission
is still unresolved. A second archive comparison
(`ci-image-artifacts-20261024.tar`) was cancelled by restart before returning a
result; do not claim its retirement or redo the completed first-archive work.

Second carrier continuation is now complete: all 100 retained entries matched
and GNU tar data/ACL/xattr compare returned 0 in 59.13 seconds. No visible
file/mount/script consumer was found; Windows exclusive access passed (Linux
FD visibility still had 44 PID gaps, not claimed complete). Ordinary exact
Windows literal deletion removed only the second outer tar. All 92 original
files (2,078,997,328 bytes), source alias and verification receipt remain.
The two completed retirements total 4,979,916,800 logical/allocated bytes.
Do not repeat them. Whole-root native Windows enumeration measured
88,017,201,245 logical bytes for H BORTUS (not allocation/hardlink deduplication);
legacy/runtime/shared producer attribution is still insufficient for new build
admission. Continue that accounting and preserve failed-run dependencies.

Build admission is now an explicit **not admitted** decision with a
producer/alias/retention ledger in `docs/operations/DOCKER-H-STORAGE.md`.
The current Linux dependency candidate is sized from 495 integrity-matched
public manifests: 834,617,149 unpacked bytes across 504 conservative install
locations. No dependency tree was created. Ten pinned Linux build input
hashes passed. The initial probe omitted pull-never and unexpectedly fetched
Node when its previously listed tag was unavailable; exact-ID pull-never was
then used. The same image identity was listed before/after, incremental
growth is unmeasured, and no shared image was deleted. Preserve that incident
record rather than claiming no download.

Next requires normal verified admission or a fresh explicit exception for the
proposed 4,000,000,000-byte incremental H qualification stage; the old
existing-image review exception does not apply. No global budget increase,
new root/checkout or production deployment is implied. Full Linux build and
scoped durable/always-on runner acceptance remain unrun.

After James requested retrying H, the bounded retry found Windows H available
(390,930,190,336 free bytes) but WSL's existing H transport returns ENODEV.
The nested existing loop0 ext4 store returns EIO; kernel logs confirm read/write
failures and an aborted journal with failed superblock writes. No install/build
or new stage output started. Do not repeat free-space checks as if this were
capacity exhaustion, write to the failing store, or run fsck while mounted.
Shared dockerd/containerd remained untouched. The next action requires a
coordinated local maintenance decision to verify idle consumers, refresh the
existing H transport/mount and inspect the existing store offline, preserving
all source, credentials, backing files, evidence and other workloads. See
`docs/operations/DOCKER-H-STORAGE.md`; no new mount/root, WSL shutdown or
production mutation is implied.

Current boot `e72801ac-8c43-458f-86b4-5e74f9c4a756` followed an external WSL
restart: H metadata reads now work, loop0 has zero recorded errors and journal
commits, and a 65,536-byte fsync/readback/removal probe passed. The agent did not
stop services, unmount or repair the filesystem; its maintenance question was
interrupted without an answer. Continue the user's directed H retry within the
presented 4 GB stage using `scripts/migration/qualify-certificate-frontend.py`.
It uses source read-only, one H dependency tree/output binds, pull-never pinned
Node, 2 CPUs/1 GiB/no swap/PID256, and source/lock/index binding. Check existing
started/result records and exact container before resuming any interrupted
step; do not replay completed work. Full build/runner acceptance is not yet
claimed, and legacy accounting/global/deployment boundaries remain intact.

Linux qualification has now progressed: current-lock install, dependency
preparation and Prisma generation passed once under H (about 1.304 GB).
Do not repeat them. Builds exposed/fixed the certificate page's missing async
declaration and the control effect's hook dependency (with UID/revision guarding
unsaved edits). Full-checkout ESLint passed for source fingerprint
`85876117c63b70ed7470dce53ebeffa354f46cf190a1a20c7b8c2a87b4fd635b`
(993 bound files). The first native prebuild temp-routing failure and later
512-/768-MB whole-checkout type-worker heap failures remain logged, not waived.

The completed step is `build-context` in
`bortus-operator-recovery/certificates-qualification-20261116`: it mirrors the
existing release `.dockerignore` test exclusion by a read-only empty mount,
keeps application/generated-route type checks and requires the identical-source
full lint pass before Next's documented no-concurrent-lint mode. The container
still has 2 CPUs/1 GiB/no swap/PID256 and the stage remains capped at 4 GB.
It passed in 72.42 seconds, with a 1,699,647,488-byte observed stage peak and
source/lock/index unchanged. Do not repeat it. Whole-checkout test typechecking
remains unpassed; this is the actual existing release context plus its matching
full lint pass.
The real H SQLite two-process persistence/lock check passed; its four finished
synthetic payloads were removed (61,440 allocated bytes), minimal results kept.
The actual Next/Prisma/auth `fixture` completed cleanly in 719.7 seconds.
`application-browser-result.json` records 18 real desktop/API checks including
keyboard save, pending/acknowledged pause, same-revision draft preservation,
readonly controls, offline history, CAS/body/origin/role denials and immediate
same-session operator revocation. Production CSS/desktop screenshot inspected;
no phone or attended screen-reader acceptance is claimed. The requested 390px
popup stayed 800px. No production runner/deployment/lifecycle operation ran.

The exact fixture container/browser closed. Synthetic SQLite/kubeconfig/fake
CLI cleanup reclaimed 319,488 allocated bytes; four public metadata records
remain. The admitted exact `npm` and `next/cache` cleanup is now complete,
removing 461,807,616 allocated bytes. Retained stage measured 1,218,887,680
bytes before the small cleanup receipt. Keep dependencies, built output and
unique results/logs/screenshot for remaining qualification; do not repeat build,
install, passed desktop/API checks or completed cache cleanup.

The driver now accepts attempt-specific fresh application fixture directories
without changing frontend source/fingerprint, so reuse the successful build
for phone qualification. The old fixed fixture directory is retained and must
not be reused. Next: remaining responsive/attended-reader acceptance and scoped,
durable always-on runner/notification delivery before activation, then all
later certificate lifecycle/plaintext/mesh phases.

Real phone viewport is now available through the installed CLI `set viewport`
on the isolated MCP browser session (no MCP/config change). The first actual
390px/320px views exposed long resource names widening the page to 404px.
The monitor panel now permits unbroken text wrapping; this frontend change
invalidates the old build binding for new acceptance. Matching named full lint
`phone-wrap` passed on fingerprint `6c94ee8519ccd12235a003fca6e381d5d355d31805ed32999b8519e00225548d`.
The named `build-context --attempt phone-wrap --lint-attempt phone-wrap` is
launched; reconcile its result/log and exact container before continuing.
Old build/API evidence remains historical. No dependency reinstall or duplicate
tree occurred; the 4 GB ceiling and original resource caps remain unchanged.
After build passes, use a fresh fixture attempt with `--build-attempt phone-wrap`.

Phone-wrap build subsequently passed in 77.39 seconds; actual 320px/390px
views now have page widths exactly matching each viewport, including expanded
observations. The phone fixture closed cleanly. Axe 4.12.1 found two further
defects: low-contrast CSR created timestamps and a non-focusable table scroller.
Both are corrected in source (zinc-400; named focusable region with focus ring).
New matching lint/build/audit and actual keyboard scrolling are needed before
binding acceptance to that source. Before/phone-wrap evidence remains intact;
attended screen-reader and all runner/lifecycle/rollout gates remain open.

Latest qualification is complete: named `phone-a11y` full lint/build passed
on `561826437128d627d2b59fff280749902700db4d40c1673caf77da8a04f87dea`
(993 files), build ID `1Z4OrQk6ue0Sv4szH1jFe`, 70.82s. Real 320px/390px
page/panel widths fit; Tab reaches the named table, visible focus is 2px and
ArrowRight moves scrollLeft to 48px. Axe 4.12.1 reports zero violations at
320px (five offscreen contrast observations incomplete) and zero
violations/incomplete at 1280px with those cells visible. This is automated/
keyboard/visual acceptance, not attended-reader acceptance.

All phone fixtures and browser sessions closed cleanly; exact regenerated
cache and nine synthetic payload files were removed (228,614,144 allocated
bytes). Stage retained 1,219,219,456 bytes before the small cleanup receipt.
Keep current built runtime/dependencies and unique logs/results/screenshots
for reader/release qualification. Do not repeat cache removal, installs or
unchanged passing checks. Named fixture launch must use fresh attempt state
and `--build-attempt phone-a11y`. Next: attended-reader check plus scoped real
identity/durable always-on runner/notifications, then lifecycle and network
phases. No feature publication, production change or chart activation ran.

Independent-runner source increment is now qualified locally. Read-only host
preflight found Python 3.10.12/systemd 249/kubectl on all three nodes and no
monitor service. Proposed placement is node02 (about 12 GB available RAM,
90 GB free under /var/lib), not an installation. New
`certificate_monitor_runtime.py` keeps local work H-only and permits the exact
root-managed unprivileged host profile with fixed CA-verified VIP/token paths.
No credential minting or admin fallback. Runner loop now exits its interval
wait on signals, rejects duplicate owners and refuses public/symlinked state.
SQLite has a 16 MiB page ceiling and 1,000-row recent run/delivered-outbox
retention, preserving all undelivered notifications.

An inactive 256-MiB/no-swap/10%-CPU/64-task API-VIP-only systemd candidate and
preflight-by-default Ansible initial-stage candidate are in source. Eighteen
monitor/control/actual-entrypoint tests passed; Ansible syntax and local unit
verification passed (unrelated pre-existing Ingenium symlink warning retained).
Node02 Python parsed all five modules from stdin without installing/executing
them. `runner-host-candidate-result.json` binds seven source paths. Test payloads
are gone; two empty directories removed (8,192 allocated bytes). Stage was
1,219,244,032 bytes before its receipt. No install/build/UI replay or production
mutation occurred.

Next: scoped external short-lived credential refresh and effective live RBAC,
real service resource/restart/persistence qualification and notification
delivery, alongside attended-reader acceptance. Initial-stage playbook has no
activate path and refuses pre-existing targets; do not run it merely because
syntax passed. No tokens, host files, chart activation or API grants were made.
Keep all later lifecycle/plaintext/mesh acceptance active.

Actual Ansible preflight now also passed on node02 with become explicitly
off: ok=3, changed=0, failed=0, unreachable=0, skipped=9. Its first controller
RPC startup failed before tasks; preserved separately. The corrected call used
the repository's existing abstract Unix-address pattern for H temp paths.
No account/code/state/unit/reload/credential tasks ran. Source-bound
`runner-host-preflight-result.json` and both logs remain; the empty controller
temp was removed (4,096 allocated bytes). Stage was 1,219,252,224 bytes before
that small receipt. Next remains actual scoped credential/RBAC, service and
notification qualification; read-only preflight is not activation authority.

Scoped credentials/RBAC now have real acceptance. New root-only external
broker/shared API adapter and inactive one-hour-token/twenty-minute timer are
implemented; eight focused credential tests pass and both modules parse on
node02 Python 3.10. Updated initial-stage candidate includes seven modules and
three inactive unit definitions, but installs/enables no credentials or service.
No root adapter or timer is installed yet.

Private charts `main`/`validated` is now
`7e1c6c9eab42ead78f77c374a5a1cc555196bfd3`: monitor-only five-object identity
bootstrap through the running H-compatible singleton watcher, 35 tests/full
validator and Flux. Both release parent/identity child are Ready; seven Flux
Kustomizations and 36 HelmReleases inventoried with none unsuspended/unready.
UI/control candidate remains inactive;
control ConfigMaps are absent. Unrelated private memory/config and root Git
index are preserved. No Actions, watcher restart, host or app rollout.

Pin monitor UID `687ff70b-39a4-4555-9b17-cb02d83b4ec6`. Actual one-hour tokens
passed authenticated identity, 7 allow/19 deny checks and reads of 14
Certificates/0 CSRs. Two deliberate refresh cycles additionally verified atomic
replacement with an old reader held open. First live attempt failed safely
on generic kubectl List formatting; retain it. Production/shared adapter now
uses raw typed API endpoints; passing corrected/rotation attempts are distinct.
All diagnostic credential/config/temp CA files were removed; only metadata
records remain, no server revocation claim. Do not replay completed checks or
reinterpret this as root timer/host service activation.

Next: reviewed host enrollment/staging and actual root broker/timer plus monitor
service resource/restart/reboot qualification, then notification delivery;
attended reader and lifecycle/plaintext/mesh acceptance remain open. Detailed
evidence and private revision are in the latest migration-plan section.

Node02 staging is now complete once (`ok=20 changed=10 failed=0 unreachable=0`),
including public enrollment/config/CA and three inactive unit definitions;
do not replay the initial-stage play. Broker code and unit hashes match that
staged checkpoint. First broker execution succeeded but its collector sampled
the pre-exec executor. Initial inspect also missed journalctl's >4096-byte
JSON field (null by default). Both collector failures remain. `--all` corrected
the metadata reader; named inspect recovered the original successful broker.

`once --attempt exec-sampling` passed 323 live kernel samples with original
256-MiB/no-swap/10%-CPU/64-task limits. Memory max observed 70,258,688 bytes,
tasks five, no OOM; actual Python NoNewPrivs=1 and CapEff/CapBnd=9. Its first
sample confirms the pre-exec context differed. UID998 can read token/public
config, not admin bootstrap/root lock; it cannot modify broker/enrollment/token.
No credential values entered receipts.

Credential timer only is enabled/active; initial timer run passed. Baseline
invocation `27e371f4cddd47e1a2a2009e8244fda5`, due monotonic
`1601308837483` microseconds on node02 boot
`137455a5-2921-4691-ab8f-06bc53ad0c23`. The existing background `observe`
phase is read-only and follows that due time. Reconcile its result/started
receipt before doing anything; do not reset/re-enable the timer, repeat manual
runs or claim periodic refresh yet. Monitor remains disabled/inactive.
Next: accept actual periodic result when available, finish evidence/empty-stage
temp review, then continue monitor/notifications and all later phases.
Empty staging-temp review/removal is now done: exact `node02-staging-temp`
removed (4,096 allocated bytes), preserving all logs and receipts. Stage was
1,219,440,640 bytes before its cleanup receipt. Do not delete the installed
runtime token: the active credential timer owns it. Periodic observer remains
the next pending result; no monitor activation or node reboot is authorized
by that observation.

Periodic observer now completed, exit 0: a real scheduled refresh after
1,200.109143 seconds, invocation `6dec32e9716e4f07a03c93c1a0c13ed1`
at/after the recorded due time. All 7 allow/19 deny checks passed again;
14 Certificates/0 CSRs read. Token inode/mtime changed, ownership stayed
root:998/0640 and expiry advanced to 2026-11-16T17:34:14Z. Monitor remained
disabled/inactive. No timer reset or manual start produced this result.
`node02-credential-observe.result.json` and
`node02-credential-installed-acceptance.json` bind the completed evidence.
Observer has exited; leave the credential timer and its runtime token intact.
Do not replay staging, manual execution or the passing periodic observation.
Installed broker/resource/periodic qualification is complete, not the full
goal. Monitor-service/notifications, attended reader, node-reboot survival and
later lifecycle/plaintext/mesh gates remain open. This step did not authorize
monitor activation or a node reboot.

Monitor/notification preparation now passed locally, without activation.
Read-only `monitor-preflight` verified installed staging hashes, UID998/0700
state, no monitor DB and disabled/inactive monitor. Both control ConfigMaps
remain absent. Only the monitor unit source now proposes a separate volatile
cache/fixed HOME/proxy removal/accounting; installed broker/timer and monitor
files are untouched. Future qualification is paused-first and requires explicit
activation plus a reviewed upgrade, not initial staging replay.

New `certificate_monitor_notifications.py` and
`deliver-certificate-notifications.py` prepare an independent at-least-once
outbox sender: explicit private-IP-pinned HTTPS/CA/token-file ntfy destination,
no public relay/proxy/redirect, durable backoff, separate sender lock, bounded
three-event batches and ten-second child calls. Unknown accepted outcomes can
duplicate a stable event ID; server ACK never proves human receipt.
The inactive notifier unit denies all egress until a reviewed exact-address
drop-in; it is not installed or added to the staging play. Self-hosted ntfy is
selected, not deployed; no credentials/subscription/live message exists.

Eight focused tests passed, including real loopback TLS, trust/hostname and
response rejection, durable retry/uncertainty, sender locking, active-scan
isolation and actual CLI restart/no acknowledged replay. Two modules parse on
node02 Python3.10; local unit verify exits0 with retained controller warnings.
`monitor-notification-preparation-result.json` binds six source paths.
Synthetic DB/credential/key payloads are gone; exact empty test directory
removed (4,096 bytes). Combined current stages measured 1,399,603,200 bytes
before the small receipt. No app build/dependency install or private publication.

Next remains reviewed host update/activation, actual ntfy server/ACL/subscriber
receipt and monitor restart/resource/persistence qualification. Independent
off-host missed-run/node-loss detection and future lifecycle-job alert producers
are not implemented by this sender; preserve those gates. Monitor stays
disabled/stopped; notifier absent; leave the accepted credential timer/token
intact. Attended-reader and lifecycle/plaintext/mesh phases remain open.

Private ntfy/off-host watchdog preparation now passed, still inactive.
Private checkout has unreferenced `flux/private-ntfy` (nine objects, additionally
zero replicas) and `flux/certificate-watchdog` (five exact-reader identity/grant
objects), candidate tests and OPERATIONS notes. HEAD remains `7e1c6c9e…`;
no commit/push/apply/credential/DNS/host change. Proposed ntfy location is
node01; node03 is the off-node02 witness, not an installed service.

ntfy v2.38.1 index is pinned `038da2be…`; only registry/source metadata was
read, no pull/scan/run. Private-CA HTTPS/SNI passthrough, native auth references,
three ordinary split publisher/subscriber identities, exact topics, deny-all
anonymous/default/no egress and retained bounded cache are candidates only.
`ntfy_acl_contract.py` validates but cannot generate/provision credentials.
Pinned source corrected initial token-length assumption to tk_ plus29 URL-safe
characters; both affected tests passed afterward, earlier log preserved.

`certificate_watchdog.py`/`run-certificate-watchdog.py` prepare explicit trusted
UID arming, fixed API reads of observations and node02 Lease, 180s heartbeat/
90s lease thresholds and five-second future skew limit. API gaps/recreated
resources mean unknown coverage, never proven worker death or incident
resolution. Separate private bounded state/outbox deduplicates incidents,
preserves pending alerts and emits fixed recovery events. The sender has a
distinct watchdog profile. New detector/API-only and sender/deny-all units are
not installed; separate short-lived credential rotation is still required.

15 focused cases passed, plus two corrected ACL cases, four private candidate
tests and full unchanged private validator/credential scan. Both candidate
Kustomizations rendered/object-checked; both units verify. Node03 Python3.10
parsed code before the ACL regex-only correction. Read-only checks: watchdogs
absent; node02 monitor disabled/inactive; accepted credential timer active.
`ntfy-watchdog-preparation-result.json` binds 14 source paths. Test secrets/
keys/DBs removed; six empty temp/cache directories reclaimed24,576 bytes.
Combined current stages1,399,656,448 bytes before its small receipt. Temporary
private `.tools`/`.validation` routing links are gone; tools were reused, not
copied. Unrelated private memory/config and root index are preserved.

Next gates: explicit live activation/reviewed upgrades, native ntfy material
and actual TLS/ACL/image/storage/resource/restart qualification, separate
watchdog identity/refresh, off-host outage/recovery and subscriber receipt.
No full-cluster/node03-failure resilience is claimed from one witness.
Attended-reader and lifecycle/plaintext/mesh remain open; monitor stays off.

Actual pinned ntfy fixture now passed in isolation, not production. New
`qualify-private-ntfy.py` uses the unchanged private server.yml, synthetic
credentials/TLS and an owned internal Docker network plus loopback-only byte
forwarding (no TLS termination). Raw registry digests bind index→amd64→config.
Image acquired once; later attempts reused it with pull-never.

Preserve interrupted attempts: `ntfy-server-tls-acl` stopped on this daemon's
manifest-as-image-ID convention; `ntfy-server-manifest-id` stopped before tests
on internal-network host-port null bindings. Credential-free port diagnostic
confirmed that behavior. Neither is an ntfy ACL failure. Corrected distinct
`ntfy-server-loopback-proxy` passed trusted TLS, bad CA/hostname/plaintext
rejection, two real publishes and authenticated machine subscriber receipts,
all26 forbidden operations (20x403/6x401), and identical cached message IDs
after recreation with a fresh auth store. Not attended phone/PWA receipt.

All task containers, networks and proxies closed;14 exact synthetic key/token/
auth/cache/env/config targets removed (643,072 allocated bytes). Minimal
started/image/result/container metadata and sanitized logs remain. Final
`ntfy-server-isolated-acceptance.json` binds passing result, cleanup and
production-off proof. Node02 monitor disabled/inactive; node03 watchdogs absent;
production ntfy namespace absent. No private push/apply/credential/DNS change.

Retain the one exact child image `6ceb2733…` on H for outstanding image-security
qualification. Reported36,988,086 content bytes are not physical/unpacked size;
continue charging1 GB conservative image/runtime reserve inside existing4 GB
stage, not a new allowance. Review exact image retirement after that security/
authorized local consumer ends. Source stage1,219,633,152 bytes before cleanup
receipt; no dependency/tool copy. Earlier protected-runtime stat denial was
not bypassed; public configuration/Docker API confirmed H routing.

Next remains exact-image security, production-like TLS/route/policy/storage/
resource proof, explicit activation, actual attended subscriber receipt,
watchdog identity/refresh/live outages, monitor persistence, attended reader
and lifecycle/plaintext/mesh gates. Do not replay passed fixture or delete
the accepted production credential timer/token.

Exact-image secret qualification now passed once: existing approved worker
Trivy0.76.1 SHA `d1dfca6a…`, zero findings, 105 built-in rules, three kernel
samples under 1 GiB/no swap/two CPUs/64 tasks. A metadata-only template sentinel
check passed. The exact retained child was exported once to
`ntfy-security-secrets/exact-image.tar` (36,996,608 bytes), with manifest/config/
compressed-layer hashes checked. Preserve image/export for pending CVE scan;
do not execute/pull/export again or replay secret/TLS/ACL checks.

The scan log reveals anonymous telemetry despite skip-version-check. Recorded,
not described as network isolation; current driver adds disable-telemetry for
future authorized runs. Executed driver hash `e152a33a…` is historical, not the
current corrected source. No production credential/data was supplied.

Six admitted obsolete cache/temp/synthetic targets removed16,052,224 allocated
bytes. Current app dependencies/build and publisher checkpoint remain required;
immutable October DB/tool are preserved. After cleanup, conservative charge
was1,420,963,840 retained + unchanged1GB runtime reserve +1,773,903,872 fresh DB
=4,194,867,712 bytes, exceeding the existing4GB stage by194,867,712 before small
receipts. Fresh DB **not admitted/downloaded**. Pinned manifest `b0461352…`/
layer `25ad50ee…` is current public metadata only; full-layer/DB integrity and
freshness still require verification. Existing October DB is stale and unused.

Next needs James's genuine budget decision on a proposed **4,250,000,000-byte
one-stage exception**, preserving the full1GB reserve and streamed/no-carrier
DB download. It is not approved, a global allowance increase, a new root or a
production action. Detailed calculation is in
`ntfy-security-secrets/fresh-db-admission.json` and migration/storage docs.
Do not silently reduce the reserve or delete protected app/publisher inputs.
Read-only proof confirms monitor disabled/inactive, node03 watchdogs absent,
ntfy namespace absent and accepted credential timer enabled/active. All full
image-security/live/attended/lifecycle/plaintext/mesh gates remain open.

James subsequently selected **Approve 4.25 GB stage** in the explicit question.
`ntfy-security-vuln-approval.json` records the one-stage4,250,000,000-byte
exception; full1GB reserve and all production/global boundaries remain.
The new vulnerability driver reuses the same export/scanner and has separate
exclusive database/scan phases, complete pinned-layer/member hashing, freshness
checks, explicit telemetry disable and unfiltered Results-only reporting.

Initial foreground DB phase hit its120s tool timeout before any terminal
integrity receipt. Both expected-size files remain in
`ntfy-security-vuln/database.pending`; do not count them accepted or redownload/
overwrite them. `database-interrupted.json` preserves that outcome.
The separate `verify-database` recovery is now running in the background,
comparing those SAME pending files byte-for-byte against the full immutable
layer and hashing every compressed byte. It writes no duplicate DB/carrier and
will publish the same directory only after complete integrity/freshness checks.
Reconcile its automatic completion and `database-result.json` before scanning;
do not replay the database phase or an existing started verification.
No vulnerability result or security pass is claimed yet.

The separate verification completed successfully in17.82s: entire pinned
compressed layer and byte-for-byte equality of BOTH retained files passed,
with no second DB writes. DB SHA `e7587cc3…`, metadata SHA `5d20f227…`;
UpdatedAt13:03:44Z today and NextUpdate13:03:44Z tomorrow passed freshness.
`database-result.json` is now terminal verified; do not download/verify again.
The vulnerability scan phase is running in the background against the SAME
exact export with telemetry disabled and unfiltered OS/Go coverage. Reconcile
its automatic completion and exact unit before proceeding. No scan result or
clean-security acceptance yet; keep DB/export/image until that consumer ends.

Fresh exact-export vulnerability assessment is now **complete, candidate HOLD**.
Scan exit0;17 Alpine packages/86 Go packages; one MEDIUM finding,
`CVE-2026-4738` zlib1.3.2-r1 →vendor fix1.4-r0. Zero High/Critical scanner
findings and zero Go findings; prior secret scan remains zero, not replayed.
Official Alpine secdb confirms the fix. Primary CNA describes GDAL infback9
before3.11.0 and rates that code Critical9.4; do not confuse/dismiss that with
the scanner's Medium package score. Exact archive inspection finds no GDAL/
infback9-named files and ntfy has no ELF dynamic section, but this does not
prove every vulnerable static path absent. No suppression, false-positive
waiver, accepted risk, clean-security or deployment approval was made.

Telemetry/version requests were explicitly disabled in this execution.
Kernel limits matched1GiB/no swap/two CPUs/64 tasks. Full original1GB-reserved
plan4,194,884,096 bytes stayed under approved4.25GB; sampled stage+conservative
image allowance3,695,072,512. Source/index/DB hashes stayed unchanged.
`ntfy-security-vuln/security-assessment.json` binds reports, full DB integrity,
interruption/recovery, advisory/ELF review, resources and production-off proof.

Local required scan/assessment consumers have ended. Five exact fresh-DB/
analysis/temp/export targets were removed:1,811,103,744 allocated file bytes.
The exact task-acquired ntfy child reference was removed with ordinary Docker
image rm, no force/prune, and absence verified. Physical runtime reclamation
is unmeasured; the ended1GB reserve is not measured disk savings. Initial
no-tags safety check stopped because Docker listed the identical owned digest
in RepoTags; its failure and exact-identity correction remain preserved.
Stage retained1,204,023,296 bytes plus publisher180,113,408 before small receipt.
Old immutable DB/tool, current app dependencies/build, source/index and unique
reports/logs/provenance remain; image/export/fresh DB are no longer retained.
Do not replay these completed old-digest scans/fixture/export or cleanup.

Next dependency-ready step: prepare/qualify a vendor-fixed candidate (or obtain
materially stronger code-not-present evidence), without silently replacing the
private pin or assuming publication/activation authority. Current private
candidate remains unreferenced/zero-replica; HEAD7e1c6c9e… and root index preserved.
Monitor disabled/inactive; node03 watchdogs absent; ntfy namespace absent;
accepted credential timer enabled/active and untouched. Full delivery remains
active: production-like route/policy/storage/resources, monitor persistence,
watchdog identity/refresh/actual outages, attended subscriber/reader and
lifecycle/plaintext/mesh gates remain unaccepted.

James next authorized fixed-zlib candidate preparation/qualification only,
production inactive. Latest upstream2.38.1 is still held. New
`images/private-ntfy-zlib/` pins original base plus signed Alpine3.24
zlib1.4-r0 (56,761 bytes, SHA7b05bc77…), with no ntfy rebuild/broad upgrade.
Existing H `ntfy-zlib-fixed/` has the single package/input metadata. Planned
peak4,208,052,864 remains within existing approved4.25GB with full1GB reserve.

Local builder uses a bounded offline install container plus commit rather than
an unconstrained shared BuildKit build/new builder. First installation passed
but bad `apk info -v` output assumption failed; its discarded writable layer
and logs are recorded. Separate `apk-db-check` installation passed with no
repository lookups but finished before a live kernel sample. Its observer
remains failed and successful STOPPED install container4238b4db… is retained;
do NOT reinstall or remove it while finalization is active.

First finalizer stopped before commit on `scripts.tar.gz` versus assumed
`scripts.tar` allowlist path. Its failure/delta remain. Named finalizer
`--attempt apk-db-path` now runs in background against the SAME installed
layer: checks unchanged ntfy, only zlib version changed, exact filesystem delta
and all APK hook payload hashes/modes/owners against base, then commits a local
candidate and performs deterministic read-only kernel/default-nonroot audit
with stdin barrier. No retrospective install sample claim. Reconcile that
automatic completion and `build-result.json` before continuing; do not replay
started build/finalizer phases or delete their consumers. No candidate pass yet.

Runtime/security drivers now take only that explicit owned fixed build record.
New candidate gets its own fixture/security attempts; no old-image scan/TLS/
ACL replay. Image export/blob hashes and candidate identity must bind all
results. Private pin/composition/HEAD and production remain unchanged; no
publication/activation implied. Later delivery gates remain open.

The apk-db-path finalizer completed all package/ntfy/delta/hook comparisons and
COMMITTED the candidate, then stopped because this daemon omits optional
Config.Cmd rather than returning an empty value. `install-finalized.json` and
`committed-image-pending.json` preserve passed checks and immutable identity
`sha256:e26ace78ff6edc73a78e68ef96d8282b4ac80415623671dcee5c9edd764a525e`.
Do not reinstall, recommit or redo the passed package comparisons.
The current `--attempt committed-config` finalizer is finishing ONLY the
pending deterministic read-only resource/default-user audit and single export.
An omitted Cmd satisfies the same no-command contract; no runtime behavior or
security bound was relaxed. Reconcile its automatic completion before launching
the explicit NEW-candidate runtime/security modes. Prior failures stay literal.

Fixed candidate is now locally qualified:
manifest`e26ace78ff6edc73a78e68ef96d8282b4ac80415623671dcee5c9edd764a525e`,
config`c7054886…`, signed zlib1.4-r0 only. ntfy2.38.1 executable unchanged
(SHA2c09c500…), APK hooks unchanged and nonroot1000:1000 default exercised.
Finalizer finished pending audit/export from the SAME committed image, with
no further install/commit or package-check replay.

Combined unfiltered current-DB scan passed:17 Alpine/86 Go packages,
zero vulnerabilities/secrets, no suppression/waiver, telemetry disabled.
Real new-image TLS/ACL/machine receipt/cache recreation passed:26 denials,
two intended topics, bad CA/hostname/plaintext rejected and same cached IDs.
Fast installer live sample remains unobserved; configured install caps and
separate deterministic actual read-only kernel audit are distinguished.
All prior failures remain. The first new-image hash helper timed out during
creation, was proven never started and removed by exact ID. A fresh named/
labelled bounded helper fixed the fixture; no TLS/ACL test had run before it.

`ntfy-zlib-fixed/fixed-candidate-acceptance.json` binds results/provenance.
Full reserved plan4,195,260,928 within4.25GB, full1GB reserve preserved.
Cleanup removed18 exact fresh-DB/temp/synthetic targets,1,774,649,344 allocated
file bytes. Original base reference retired normally; runtime physical savings
unmeasured. All task containers/helpers/networks/proxies ended.
Retain unique fixed image and37,076,480-byte export
SHA`f2e9d0893435b9e45f6f9f992b4fde3bf7415204da2b2f5590f83d45a1a910a5`,
plus vendor package/minimal evidence, for immutable private-delivery handoff
and remaining production-like route/policy/storage qualification. Retire after
verified publication/consumer transfer or explicit rejection. Do not rebuild
or copy this digest or replay completed checks. Stage retained1,241,448,448
plus publisher180,113,408 before small cleanup receipt.

This completes the requested LOCAL fixed-candidate qualification, not full
delivery. Private YAML still pins the old held upstream digest, unreferenced/
zero-replica; do not replace it with a local-only reference. No image registry
publication, private push/apply, host/credential/DNS change or activation.
Read-only proof: monitor disabled/inactive, watchdog absent, ntfy namespace
absent, accepted credential timer enabled/active; original index/private HEAD
preserved. Next: authorized immutable private delivery/registry identity and
production-like CA/route/policy/storage/resources before explicit activation.
Monitor persistence, watchdog identity/refresh/outages, attended subscriber/
reader, certificate lifecycle and plaintext/mesh gates remain active.

Integration preparation is now complete and verified, not executed.
Ten fixed metadata GETs found no Traefik TCP CRD/Kubernetes-CRD provider.
Private inactive route source now uses public file-provider ConfigMap
`traefik/private-ntfy-tcp-route`; it is NOT mounted live. server.yml remains
SHA`dca96ae9…`, private image pin is still the held upstream digest,
unreferenced/zero-replica. No active edge/RBAC/composition change.

Private `qualification/private-ntfy/` has contract, non-executable native-
volume proposal and runbook: registryImage null, approvals false, replicas
zero, isolated `.invalid` fixture trust/namespaces, unique retained Longhorn
claim and bounded checks. Preserve native dashboard Secret/items/modes/mount;
collision audit plus fresh UID/resourceVersion/exact-volume guards and separate
rollout approval are required. ntfy loads TLS on startup; proposed safe renewal
restart controller is NOT implemented. Issued/projected/restarted/endpoint-
verified states and host/ambient/policy/storage/resource checks stay distinct.

Seven preflight tests/seven private candidate tests passed; actual renders
check nine ntfy/five watchdog objects. Full existing private validator passed
30 charts/31 HelmReleases/108 composed resources, rendering and credential scan.
Checksum-verified retained publisher tools reused, no copy/install. Temporary
private routing links removed; empty validator-temp removed4,096 allocated
bytes. Retained combined stage/publisher1,421,742,080 before small receipt.
Small evidence is under `ntfy-integration-preparation/preparation-result.json`.
Original ten-GET preflight/source hashes stay historical; collector now treats
missing optional CRD support as metadata rather than blocking the replacement
file route. Only affected synthetic tests were repeated, not live preflight.

Read-only closing proof: monitor disabled/inactive, watchdogs absent, ntfy
namespace absent; accepted credential timer enabled/active, untouched.
Retained fixed image/export verified; original root index/private HEAD7e1c6c9e…
preserved. No commit/push, publication, Secret read, exec, apply, DNS/host/
credential change or activation occurred. Do not repeat image tests/build/
preflight or completed cleanup. All changes remain local/uncommitted.

Next requires separate immutable private image-delivery/registry authority and
fixture execution/synthetic-native-material approval. Live native collision
audit/mount rollout, rotation, packet policy, retained storage/resources remain
unrun; monitor persistence, watchdog identity/refresh/outages, attended subscriber/
reader, lifecycle and plaintext/mesh phases remain active. Preparation does not
authorize running the documented future operations.

James then instructed “stop asking for approval. The plan is in stone.
Deliver” and resumed the goal. Execute the accepted plan without repeated
approval prompts; preparation-only holds above are superseded for execution,
not technical, preservation/resource/acceptance gates. Authority is recorded
in current stage `delivery-authority.json`.

Private publication PASSED: unchanged ntfye26ace78… at
`docker.io/jtmb92/bortus:ntfy-2.38.1-zlib-1.4-r0-e26ace78ff6e`,
privacy/remote manifest/config/all four layer bytes verified. No existing
release tag changed, rebuild/export, saved credentials or production rollout.
Node01/node02 sealed-memory preload PASSED with full stored graph/unpacked
state; no node archive or pod registry credentials.

Node01 scheduling margin was short for1Gi at unchanged Longhorn25% floor.
Six eligible closed journals were encrypted on H, authenticated/recovered and
compared before exact retirement:536,895,488 allocated bytes removed;
89,137,747 encrypted bytes retained in `ntfy-node01-journal-preservation/`.
Preserve unique history/restore input; no active logs/services/volume/threshold
changed. Current image/export remain for integration consumer.

Actual cluster stage PASSED in three named isolated namespaces. Synthetic
native auth/cert-manager CA+leaf, retained1Gi claim UIDfe0dad4e…,
PVUID96123b20…/LonghornUID8632b30f… are encrypted/healthy/two-replica.
Initial ReplicaSet deadline-field rejection remains; exact created UIDs/keys/
PKI/claim reused. Corrected workloads are standalone Pods with native<=900s
deadlines; three focused boundary tests passed. Do not replay staging.

`qualify-ntfy-cluster-path.py` is ACTIVE against that exact fixture. Reconcile
automatic completion and path-result/failure before doing anything dependent.
It checks actual routed trust/HTTP, policy/ambient/host/egress, cgroups,
cert-manager reissue/projection/old serving leaf, then exact Pod recreation/
new served fingerprint and cache ID. Synthetic H client token file is private
for this consumer; never print/source/argv it. Keep retained PVC/PKI on failure,
not blanket namespace deletion. Production still unchanged/off; timer intact.
Do not stop at transport or ask to reconfirm settled execution.

The path and bounded state checks are now terminal PASSED; all six diagnostic
Pods/forwards ended, local synthetic client token/empty temp removed8,192
allocated bytes. Retain fixture PKI/native auth/config/claim only for the
specific next unattended-rotation-controller live qualification, then retire
after reviewed consumer completion. No namespace/PVC blanket deletion.

Actual routed trust/plaintext/HTTP301, selected/denied same/cross-node Service+
pod paths, DNS/LAN egress controls passed. Cert-manager revision2 projected a
new leaf while old leaf remained served; guarded exact Pod recreation served
new fingerprint and preserved cache message ID on same encrypted healthy
two-replica claim. Twenty publishes/three poll subscribers passed, zero errors,
p50~66.73ms/p95~76.97ms, not load-capacity proof. Memory-only DB copies refused
writes at configured page caps; running-server connection max_page_count is
not queried. Actual PID ceiling18847, memory.peak unavailable, no OOM. Preserve
those limits. Missing peak-field collector failure was corrected by finishing
only pending observations; completed sends/cap tests were not replayed.

Private source now pins verified published e26ace78…, still unreferenced/
zero-replica. Contract records settled execution, production readiness false.
Seven updated private tests/render/full validator passed (30 charts/31 HR/
108 composed resources, credential scan), reused tools and routing links gone;
finished empty validator temp removed4,096 bytes. No private commit/push or
production change. Original index/private HEAD7e1c6c9e… preserved.

After the reported OpenCode restart, all terminal records reconciled with same
boot e72801ac…, no active driver/client token and no completed-check replay.
New `automation/certificate-rotation/{policy,controller}.mjs` implements guarded
unattended decision/one-shot adapter: pinned object/consumer/image IDs, public
issued-request+revision/CA/SAN/time checks, metadata-only Secret rejection of
full payloads, actual endpoint and fresh CAS, no blind retry after uncertainty.
Eight policy/seven current adapter tests pass with real synthetic signatures;
test keys removed. **No controller identity/Job/scheduler installed yet.**

Next: package/qualify narrow live identity/executor against retained fixture,
observation first, actual RBAC/transport/reissue/restart/interruption and
always-on proof. Existing image/build/security/direct and cluster-path checks
must not be repeated. Continue accepted full goal without asking approval.
Monitor persistence, watchdog identity/refresh/outages, attended subscriber/
reader and later lifecycle/retirement/plaintext/mesh remain active.
Closing boundary: zero diagnostic Pods, production ntfy absent, monitor off,
watchdogs absent, credential timer active/untouched. Retained stage+publisher
1,511,256,064 before closing receipts, full1GB reserve remains inside4.25GB.
Latest source correction before live controller work: real cert-manager has
certificate-name annotation, not selector label. `controller.mjs` now GETs
only `<certificate>-<revision>`, checks annotation/owner/revision, and needs
no CertificateRequest LIST. Seven affected adapter tests pass on current
source, bound by `rotation-controller-request-binding-result.json`; do not
reuse the older consumer-pins adapter hash. Eight policy tests remain passed.
Node02 already caches the qualified BORTUS Node-runtime imagee7539b… for the
intended executor; no new image/dependency is required. No identity/Job/
scheduler installed yet. Next is actual narrow-role, observation-first live
executor qualification against retained fixture, without asking approval.

Live controller qualification has started in existing fixture only.
`ntfy-controller-qualification/identity-result.json` PASSED real projected
600s token authentication/UID494d15ff… and enrolled Certificate/Secret metadata
GET. All eight actual denial checks returned403 (Secret/Pod/request LIST,
CA-key Secret, other Deployment, token mint, CSRs, other namespace).
Exact Deployment get/patch and leaf Secret/Certificate get; public requests
get-only in namespace. Secret-value capability on that one leaf is explicit
RBAC reality; controller code requests metadata only. No CA-key privilege.
Three factory boundary tests passed. No completed prior suite replay.

`qualify-ntfy-rotation.py observe` is ACTIVE: owned Recreate diagnostic
Deployment plus native-deadline edge, same retained fixture PKI/auth/config/
claim, source/actual UID+CA+image enrollment, observe mode. Real cached BORTUS
Node runtimee7539b…; no image/dependency copy. Reconcile its automatic result
before renew/interrupt/schedule phases. No production namespace/route changed.
Interruption wrapper uses same exported real transport/runOnce and holds only
after acknowledged PATCH before completion; never the scheduled entrypoint.
After stopping exact Job worker, recovery must observe durable request/
endpoint with no new generation. Then two native CronJob-owned executions
must pass, qualification scheduler suspended and exact diagnostics cleaned.

The resumed renewal is terminal PASSED: observe did not mutate; auto produced
one rollout (generation2), revision3 fingerprint1bdb2ef5… verified at the trusted
endpoint. Original helper-arity failure occurred before any mutation and is
preserved. Do not replay identity/observation/renewal. The next active phase is
`qualify-ntfy-rotation.py interrupt`; reconcile its completion before scheduling
and exact owned cleanup. Production remains unchanged.

Fixture rotation qualification is now terminal PASSED. Interruption stopped
the exact worker after acknowledged PATCH/pre-completion; recovery verified
revision4 fingerprint080f9bf5… and generation3 without another rollout.
Native CronJobUID98b15c0b… produced two verified/no-patch runs at21:39/21:40 UTC;
no manual Job counted. Scheduler suspension and exact cleanup passed:16
objects explicitly removed, two recorded scheduled Jobs already absent after
foreground CronJob deletion. Temporary role/binding/identity/source/policy/
scheduler/workloads are gone; zero diagnostic Pods. Do not replay any phase.

`ntfy-controller-qualification/live-qualification-acceptance.json` binds source,
all phase results, cleanup and read-back boundaries. Production ntfy absent,
monitor off, watchdogs absent, accepted credential timer active/untouched.
Root index/private HEAD7e1c6c9e… and active release composition preserved.
Stage+publisher1,511,534,592 plus full1GB reserve remain within4.25GB before the
small receipt. No new image/build/install or private commit/push occurred.

Pre-existing synthetic PKI/auth/config/claim/namespaces remain outside the
controller cleanup. ClaimUIDfe0dad4e…/volumeUID8632b30f… still match;
after teardown volume is detached/robustness unknown, not claimed healthy now.
The controller consumer is complete. Next separately review exact fixture
retirement (references/ownership/cascades/synthetic data/snapshot-volume UIDs);
do not blanket-delete namespaces/PVCs or invent another consumer. Preserve
unique reports and encrypted historical journals. Production controller/native
trust/credential/route packaging and monitor/watchdog persistence/notification/
outage, attended subscriber/reader, lifecycle/retirement/plaintext/mesh gates
remain active. Continue settled execution without asking approval.

Separate exact fixture retirement now PASSED:15 synthetic objects including
original PVC/PV/Longhorn volume, no attachment/snapshot/backup/consumer,
normal finalizers only; generated public requests and both replicas absent.
Three namespace objects/injected trust/default metadata remain, not a sweep.
Unique results and encrypted journals preserved. Exact local ntfy image refs
also retired normally after verified private registry/node transfer. Export
`ntfy-zlib-fixed/candidate-image.tar` remains37,076,992 allocated bytes because
process-FD visibility was incomplete; no deletion or alternative-route retry.

Production rotation package PASSED44 tests/full validator/renders; source JS
is identical to the live-qualified controller/policy. Scoped private commit
`fcdabd2107ad0ed7709d646d81f7d1259959ff50` pushed19 owned paths, preserving
unrelated private memory/config and root index. New private ntfy and rotation
children stage zero replicas and a suspended/unenrolled observe CronJob.
No auth material, serving route mount or schedule enablement. Publisher and
receipt gates advance35→44 together, reuse existing H tool inodes by hard link
instead of another copy, and retain all exact-source/credential/atomic gates.
Actions verified disabled; singleton watcher19008 reused, not restarted.

`ntfy-production-staging` holds source/preflight/push results. Its read-only
pipeline observer is ACTIVE: reconcile automatic completion,
`publisher-result.json` and `staged-flux-result.json` before dependent work.
Do not rerun publication, restart the watcher or bypass Flux with manual apply.
The native Traefik collision audit also passed privately; dashboard Secret
values were not persisted and its original mount/volume is unchanged.
Future volume projection must recheck fresh UID/RV/native Secret and exact
original fields. Actual ntfy auth/TLS/endpoint, populated enrollment/schedule,
monitor/watchdog/attended/lifecycle/retirement/plaintext/mesh remain open.

The pipeline observer is now terminal PASSED. Exactfcdabd2107ad… was revalidated
with44 tests/full validator and atomically promoted by the existing singleton.
All three affected Flux Kustomizations are Ready on that exact revision;
main/validated/immutable tag match. Same H gitleaks/helm/kubectl inodes verified,
no tool copy/download or watcher restart/Actions/manual apply.

Production stage IDs: ntfy Deploymentac981228… (generation1/replicas0),
CronJob3aab154b… (suspended), observe enrollmentCM8090120e… (UID/CA/endpoint
still deliberately empty), Certificatece3fd0bf… (Ready), PVCbfb9bc06…,
sourceCMprivate-ntfy-rotation-source-t2c6kggt25/edb438f4…. Exact packaged
controller/policy bytes match prior live qualification.

Actual production subject `system:serviceaccount:bortus-notifications:private-ntfy-rotation`
passed fresh projected-token identity/UID, Certificate/leaf-metadata/
Deployment/current-public-request reads, exact Deployment metadata-only PATCH
server dry run and eight actual403 denials including real CA-key Secret.
No persistent generation/replica mutation; two exact diagnostic objects/Pods
removed. Qualification-only `identity-check.mjs` now accepts named production
pins; shipped controller/policy remain unchanged. No old fixture test replay.

Closing readback:9 Flux Kustomizations/36 HelmReleases, all unsuspended Ready,
three Ready nodes; no ntfy Pods; rotation suspended/unenrolled; existing native
Traefik volume preserved. Monitor disabled/inactive, watchdogs absent, accepted
credential timer enabled/active/untouched. Root index preserved.
Conservative stage+old/new publisher totals1,691,987,968 (may double-count
shared tool inodes) plus full1GB reserve stay under4.25GB. Exact finished empty
publisher tmp removed4096 allocated bytes; unique source/results/tools kept.
Current private HEAD isfcdabd21…; only owned latest `docs/OPERATIONS.md` status
update remains uncommitted beside the three unrelated memory/config files.
No root commit/push occurred.

Next: provision native ntfy auth and independent client delivery, then guarded
public TCP projection preserving native Traefik Secret/mount through validated
Flux, one ntfy writer and actual CA/route/identity/state verification. Only then
CAS-populate enrollment, run observe against the actual endpoint and enable
scheduled rotation through source. `ntfy-production-staging` receipts bind all
completed steps; do not replay publication/preload/image/fixture/staging tests.
Full monitor/watchdog/notification, attended and later certificate-lifecycle/
retirement/plaintext/mesh delivery remains active. No new approval prompt needed.

Serving integration is active. Native auth was created once:
`bortus-notifications/private-ntfy-auth` UID29ce9801… with three ordinary
publisher/publisher/subscriber identities, server users/tokens plus separate
client-token keys. Values stayed only in memory/native Secret, no H payload,
argv/Git/SQLite/log values. Do not regenerate or replay provision.

Public trust preflight caught the draft notifications.lan outside the
existing root's branconet.lan/branconet.local name constraints. Correct NEW
service endpoint is notifications.branconet.lan; no existing service renamed,
issuer changed or trust widened. Server config changes only base-url, otherwise
byte-bound to qualified config. Current system DNS has no record for the new
name; explicit address/SNI trust can qualify serving, not general DNS/phone
availability. Later DNS rollout must preserve both resolvers serially.

Fresh native collision/UID/RV/exact-volume/server dry-run preservation passed,
all existing Traefik container fields unchanged. First guard failed before
Secret/endpoint reads on omitted API defaultMode420; source now preserves
explicit0644. The second exposed pre-existing self-signed TLS for native
proxy.branconet.lan dashboard (code18), not waived or called trusted. Existing
HTTP dashboard control is404. BORTUS/whoami trusted controls are200. Preserve
native dashboard Secret/values/mount and track its trust gap separately.

The unpublished one-writer source passed44 tests/full validator. Actual
execution is split to avoid startup loading the old leaf: private commit
`0024a70e92b98c3ee109aa8a66fc1f9c20e5fa60` first changes corrected Certificate/
TCP route and full native Secret+optional public ConfigMap projection, with
replicas0 and rotation still suspended/unenrolled. Ingress now selects both
Traefik namespace AND app=traefik, no explicit node-IP allow workaround.
Fresh edge/native Secret UID/RV were rechecked immediately before scoped push.
Guards are prepublication checks/dry run; actual mutation is ordinary Flux
SSA, not falsely claimed atomic live JSONPatch CAS. No manual deployment apply.

`ntfy-production-activation` contains native-auth, public-trust, failed-guard,
corrected-baseline and source/push records. Its read-only trust-route observer
is ACTIVE: reconcile automatic completion and `trust-route-result.json` before
starting the writer. It requires singleton44-test publication, exact FluxReady,
real corrected leaf CA/name-constraints/hostname/purpose verification, two
Ready edge replicas/native UID+RV preserved and trusted unrelated controls.
Then publish replicas1 through the same path and verify actual TLS/ACL/state
before CAS enrollment/observe and source-based schedule enablement.
Do not rerun prior passing fixtures, image scans/preload or staging checks.

Trust/route checkpoint0024a70… is terminal PASSED: singleton44-test publication/
exact Flux, corrected real leaf revision2 root/name-constraints/hostname/
server-purpose verification, two Ready edge replicas and unchanged native
dashboard Secret UID/RV/full0644 projection. Trusted BORTUS/whoami controls200.
Writer checkpoint946c1f84… then PASSED singleton/Flux and actual TLS1.3
serving at notifications.branconet.lan via192.168.0.252, fingerprint8f301d72…,
wrong trust/SNI/plaintext rejection, both native publisher/subscriber topic
flows and six403 denials. These are machine receipts, not host alerts/human
receipt or DNS availability. A diagnostic NameError after TLS success but before
first publish remains; only unstarted ACL/state work resumed, no TLS replay.

Actual retained production PVCbfb9bc06…/PV14c7c8da…/Longhornf9f8be3b… remain;
encrypted/healthy with running node01/node02 replicas. Runtime UID1000,
capabilities0/NoNewPrivs/seccomp2,256MiB/no swap/250m, PID18847/no OOM observed.
No production backup/restore/restart-persistence claim. Normal server data now
includes two qualification metadata messages with native24h cache retention;
do not treat the production claim/auth as disposable fixture output.

Actual CAS enrollment in observe mode PASSED, and the delivered controller
verified the real endpoint with patch:null/no generation change; exact
diagnostic Job/Pods removed. CAS changed only mode to auto with pins preserved.
Schedule checkpoint `5de2c45d7df5d976f0b92b9dc68c59596b0dde79` PASSED
singleton44-test promotion/Flux and preserved operator IfNotPresent enrollment.
The FIRST native production CronJob-owned execution was scheduled22:40:00Z,
ran22:40:04–11Z, verified8f301d72…/patch:null, with writer generation2 and
PodUID0fb3c861… unchanged. It used the normal five-minute interval, not manual
start/shortened testing. **Leave this production schedule and native auth/data
intact.** Normal history retains2 successful/2 failed; no fixture-style cleanup.

`ntfy-production-activation/{serving-result,production-observe-result,rotation-auto-result,schedule-flux-result,native-schedule-result,closing-boundary}.json`
bind exact results. All9 Flux Kustomizations/36 HelmReleases unsuspended Ready,
three nodes Ready. No temporary diagnostic Pods. Monitor remains disabled/
inactive, watchdog absent, accepted credential timer enabled/active/untouched.
Root index preserved; private HEAD5de2c45d…. Latest owned docs status updates
remain uncommitted beside preserved unrelated memory/config files; no root
commit/push. Three exact finished publisher tmp dirs removed12,288 allocated
bytes. Conservative retained stage+five publisher trees2,232,958,976 plus
full1GB reserve remain within4.25GB (tool inode duplicates conservatively count).
Original37,076,992-byte export stays safety-check-retained; no retry/deletion.

Next: serial DNS delivery for the new name (currently unresolved), independent
monitor/watchdog client-token delivery and actual durable service/notification/
outage qualification. Existing proxy.branconet.lan self-signed dashboard trust
gap stays open, not waived. Attended subscriber/reader, safe kubelet/control-
plane lifecycle, dependency-checked retirement and remaining plaintext/mesh
gates remain active. Do not replay completed publication/serving/fixture/image
or native schedule checks. No new approval prompt is needed for settled steps.

DNS continuation reconciled completed activation receipts and left live ntfy/
rotation intact. Forty baseline queries passed across floating253, standalone5
and both direct cluster Services. Immutable v4 adds only the notification CNAME;
all v3 data is identical. Full private validator passed30 charts/31 releases/
111 composed resources/credential scan. Secondary-first commit
`4a352444ffbe8338456799898bff9363ffde8056` was scoped/pushed; primary is still v3.
Read-only `scripts/migration/observe-notification-dns.py secondary` is active.
Reconcile its terminal result before the primary source change; do not replay
publication or restart the watcher. Outputs are under `ntfy-dns-delivery/`.

Advertised DNS paths are253 and5, not merely the two cluster backends.
After both cluster deployments are Ready/v4, use existing
`independent-dns-policy.yml` with dns_records_only=true, then refresh loopback
and LAN services serially while253 remains qualified. Preserve gravity.db
SHA75ae02d7… and DHCP invocation7497748f…. The installed LAN launcher matches
current source; installed loopback is the legitimate earlier loopback-only
profile, so do not overwrite it with the newer combined launcher. A read-only
collector first failed parsing systemd249 show as JSON, then a too-broad
same-launcher hash guard stopped; neither wrote host state. Public source delta/
service/DB metadata are preserved in independent-preflight.json.
No DNS/client acceptance is claimed yet; all remaining follow-up gates stay active.
Secondary observer is now terminal PASSED,402 direct TCP/UDP checks across all
four paths,48 legacy names preserved, new secondary answer verified. Primary
generation unchanged and all claims preserved. Dependent primary-only commit
`8ecc9f876f1363ad42017a048afb9563599f18d7` is pushed; its read-only observer is
active. Reconcile `primary-result.json` before independent staging.
`refresh-notification-dns.py stage|loopback|lan` is prepared and syntax-checked;
existing Ansible syntax passed. It uses records-only staging and separate
one-service refreshes with floatingDNS guards; do not run before primary passes.
`verify-notification-dns.ps1` parses actual UDP answer addresses and checks TCP/
ordinary Windows resolution with the existing advertised lease; syntax passed.
The client lease still advertises253/5 from DHCP5, gateway1, unchanged.

Notification DNS delivery is now terminal PASSED. Primary8ecc9f876f13…
passed44-test singleton validation/Flux and406 direct checks; secondary
4a352444… had passed402. All48 legacy names/claim IDs remain. Both cluster
templates use immutable v4; private main/validated/tag match8ecc9f87….
The standalone records-only Ansible stage finally passed(ok16/changed1/
failed0), updating only public pihole.toml. Loopback and LAN refreshed once
each, preserving gravitySHA75ae02d7…, both original launcher hashes and DHCP
invocation7497748f…. Prior RPC/SSH-format/missing-sudo failures were before
host writes and remain. The play now explicitly binds the saved in-memory
sudo environment variable; it does not log/persist credentials.

The first LAN collector wrongly probed own-host53, which does not traverse
inbound PREROUTING DNAT. Its service restart had succeeded. The corrected
remaining checks ran READ-ONLY with the same LAN invocation002eaa4a… against
actual10554 and external53; no repeated restart. Standalone external53
passed49 names/98 TCP+UDP checks. Actual Windows LAN UDP/TCP queries to BOTH
advertised253/5 passed; its existing lease/adapter stayed unchanged and normal
Windows DNS resolves the new name. Ordinary WSL DNS plus trusted HTTPS200
passed without an address/hosts override, fingerprint8f301d72… unchanged.
No phone/PWA/human receipt or actual monitor/watchdog alert is inferred.

`ntfy-dns-delivery/{secondary-result,primary-result,independent-stage-result,independent-loopback-result,independent-lan-result,independent-full-parity-result,windows-client-result,resolved-https-result,closing-boundary}.json`
binds evidence. Do not repeat publication, full DNS suites, staging or either
successful service restart. All9 Flux Kustomizations/36 HelmReleases Ready,
three nodes Ready; ntfy generation2/PodUID0fb3c861… and enabled rotation intact.
Root index unchanged; new local DNS drivers/PowerShell check and the play's
environment binding plus root docs remain uncommitted. Private owned status
docs are uncommitted beside preserved unrelated memory/config/README work.

Stage+seven publisher trees measured2,593,718,272 conservative bytes plus
full1GB reserve within4.25GB. One finished local validator temp was removed
earlier4096 bytes. Six exact empty controller/publisher temps remain24,576
bytes after a failed consumer-visibility check: finished PIDs remain zombies
and /proc/1746577/fd returnedEACCES. No alternative-route/elevation/deletion or
process stop attempted. Preserve exact paths in temp-cleanup-result.json
pending normal harness reaping/later authorized ownership review; no recurring
probes. Candidate export safety retention is untouched.

Next: distinct native publisher-token delivery to fixed independent host
profiles, reviewed paused-first monitor upgrade (never replay initial staging),
real durable state/resources/restart/notification qualification; then separate
watchdog identity/refresh and actual off-host outage/recovery. Accepted monitor
credential timer/runtime token and live ntfy/rotation stay intact. Attended
subscriber/reader, proxy dashboard trust, safe kubelet/control-plane lifecycle,
retirement and plaintext/mesh gates remain active. No new approval prompt or
completed-check replay is needed.

Monitor activation continuation: create-only publisher delivery PASSED on
node02 UID998 and newly created non-login node03 UID997, root0640/group-read/
no-write/other-user-denial, separate native keys and no subscriber token.
`monitor-host-activation/` binds all metadata; values travelled only in
memory/SSH stdin/native/host secret files, never H/argv/logs.

Scoped `certificate-monitor-upgrade.yml` PASSED(ok13/changed4/failed0),
preserving accepted broker/timer, adding notifier modules/cache-profile unit
and exact252-only sender drop-in; no activation by the play. Initial YAML
property-argument collector failure was changed0 and is retained. Initial
control-render order assumption failed before validator; corrected by name.
Private control-only child7911a030… passed44-test singleton/Flux, two paused/
empty IfNotPresent ConfigMaps. Inactive UI grants remain unreferenced.
Child-GET creation-race observer was completed read-only without publication replay.

`qualify-node02-monitor.py paused` PASSED actual pause heartbeat/no scans,
duplicate owner denial, real service restart/same SQLite inode3415914 and
policy, kernel256MiB/no swap/10%CPU/64tasks/UID998/CapEff0/NoNewPrivs1/noOOM.
Monitor is enabled/active; accepted credential timer active/untouched.
Audited CAS switched only mode to monitor at unchanged300sec/7day policy.
A single custom-signer diagnostic pending CSR41826f46… was created (key
discarded in memory, no approval/issuance). It generated real pending outbox
event2621e9b0…. The `restart-pending` phase PASSED actual restart preserving
the undelivered event/complete scanID/database inode with no duplicate scan.

`qualify-node02-monitor.py sender` is ACTIVE. Reconcile its automatic result
before dependent work; never replay completed upgrade/control/paused/restart
phases. Next finish actual native machine subscriber receipt, exact CSR UID/RV
retirement and fresh healthy inventory; leave normal monitor/sender enabled
after acceptance, preserving DB/outbox/audit and accepted timer/token. Current
UI delivery label is still static and not release-qualified by host evidence.
Node03 has publisher profile only; watchdog identity/refresh/service/outages,
attended reader/subscriber and remaining lifecycle/retirement/network stay active.

Initial sender phase is terminal FAILED safely(real_outbox_delivery_timeout),
with event2621e9b0… still pending/backoff. No-token/no-publish bounded systemd
probes proved VIP-only cgroup-SKB filters see post-DNAT pod IPs; exact edge-IP
probe worked but no pod-IP/subnet workaround was adopted. Scoped Ansible
`certificate-notification-egress.yml` PASSED(ok9/changed4), stopping only sender,
installing fixed root-managed nft helper/unit and removing exact obsolete
destination.conf. Monitor and accepted broker/timer stayed active/unchanged.

The nft helper enforces originalVIP252/TCP443 on the sender's own cgroup,
denying all other IP egress and rebuilding atomically for each new cgroup,
not resolving mutable pod addresses. Fixed root pre-start/stop code only;
application stays UID998/CapEff0/NoNewPrivileges. Live real-cgroup HTTPS200/
API6443+VIP80 denials passed with8 allow/2 reject counters. First bounded
probe failed and remains; a distinct counter/error probe passed, then only
remaining normal teardown/runtime override cleanup finished. No probe read
tokens or published. Three focused refusal tests pass: foreign table,
check failure/no apply and live consumer/no stop deletion. Current fresh
upgrade source includes the helper directly; historical executed hashes remain.

Real sender resumed with SAME event/backoff(failures4/due23:46:39Z), no manual
publish or database reset. `sender-recovery-observe` is ACTIVE, read-only
until actual ACK, then one real sender restart to qualify delivered-row/no
acknowledged replay. Reconcile its automatic result before subscriber read/
exact diagnostic CSR retirement and healthy inventory. Do not rerun original
sender phase, nft probes/repair, control publication or passed monitor phases.
Original failed evidence and retry rows must stay. Node03 still has profile
only; all full-goal remaining gates are unchanged.

Continuation reconciled the original ACK observer: terminal FAILED after600s
without ACK; it did not run its post-ACK restart. Fifth native send failure
advanced unchanged retry to00:03:22Z, event2621e9b0… still undelivered.
Actual profile/event/bounded-child checks passed offline. A separate actual
5%-CPU/sandbox offline entrypoint check also passed (network publisher replaced
in memory; no outbox write), child1.806s/whole unit22.030s.

Two focused fixed-code diagnostic tests passed. A scoped one-script Ansible
update initially stopped only sender then refused its temp-file import
validation; no script changed. Corrected installed-PYTHONPATH validation and
read-only source/stopped/backoff guards allowed continuation at copy/start
only (ok2/changed2). Failed log remains. Current sender script adds allowlisted
local syslog codes for child/transport failures, never backend/private text;
retry/DB/bounds and all other services remain unchanged.

`sender-diagnostics-native-retry` is ACTIVE, a read-only observer of the next
normal due retry. Reconcile its terminal result before further repair; do not
reset backoff, publish manually, repeat original phases or restart sender for
reassurance. It records actual ACK or fixed failure codes and resource metadata.
`finish-monitor-notification.py` is prepared but NOT executed: after ACK and
post-ACK restart acceptance, poll exact native subscriber/event/CSR UID,
record duplicates honestly, retire only diagnostic CSR with fresh UID/RV and
unchanged request/no lifecycle state, then audited same-policy refresh and
fresh inventory. CSR remains retained for that unfinished consumer.
The sixth real retry failed transport-unavailable/child-failed (no OOM),
backoff unchanged/due00:35:57Z. `sender-diagnostics-native-retry-result.json`
is terminal, not still running. Separate exact-class/sandbox OPTIONS transport
probe passed trusted connection/HTTP401 with fake credential, no publish,
and its own nft table removed normally. Authenticated native subscriber
uncertainty poll found zero event copies; no CSR/DB mutation.
`sender-child-transport` is ACTIVE: actual full child entrypoint/implicit
connection under the same5%CPU, with POST replaced by OPTIONS and native
credential header replaced. Reconcile its automatic result before repair.
No source change or normal-service restart for that probe.

While waiting, read-only retirement inventory confirmed wordpress/jtmb-cc
still Ready/UID591745ea… and declared in private public-certificates.yaml;
seven ordinary same-namespace kinds have no exact Secret-name match.
External/controller/cascade absence is unproven; no retirement performed.

Full-child transport diagnostic is now terminal: trusted connect/request/
HTTP401 in2.399s using OPTIONS/fake header, normal separate nft-table removal.
It did not publish and did not alter the sender/outbox. Actual failure remains
unisolated. New fixed stage/kind annotations preserve the same transport error
and ACK/timeouts/backoff. Six focused tests passed (real loopback TLS/ACK
rejections plus private-text/annotation allowlists). Synthetic test material
and exact empty test root removed4096 allocated bytes.

The guarded diagnostics play updated only transport/sender annotation modules
(ok7/changed3/failed0). No other service/credential/resource/policy change.
`transport-annotations-native-observe` is ACTIVE, read-only for the unchanged
normal due00:35:57Z retry, terminal on actual ACK or fixed stage diagnosis.
Reconcile `transport-annotations-native-observe-result.json`; do not replay
probes/installs or reset backoff. Post-ACK restart/subscriber/CSR cleanup remain
unrun. Normal monitor/broker/timer, ntfy/rotation remain intact.

Retirement Secret metadata-only read also found wordpress/jtmb-cc-tls UID
6e544d1c… with no owners/finalizers; no values/annotations were emitted.
This adds cascade metadata, not proof that all external consumers are absent.

Original event2621e9b0… was ACKed on normal00:36:26Z retry (retry row cleared,
no reset/manual send). Actual post-ACK sender restart PASSED: same delivered
row/inode3415914, new first loop accepted0/failed0/pending0; actual UID998/
CapEff0/NoNewPrivs1/128MiB/no swap/5%CPU/32tasks/no OOM. Monitor and accepted
credential timer invocations/broker hashes stayed unchanged.
Native subscriber then received exactly ONE cached matching event/CSR UID.
Only diagnostic CSR41826f46… was deleted with fresh UID/RV/no lifecycle state;
audit-only same300sec/7day policy CAS requested a fresh scan. Actual operator
parity/two fresh sources/complete inventory PASSED15 healthy Certificates,
0 CSRs,0 pending events. No values entered artifacts.

`monitor-notification-delivery-acceptance.json` binds the completed bounded
path; do not repeat sender restart/subscriber/CSR deletion/refresh checks.
All10 Flux Kustomizations/36 HelmReleases and3 nodes Ready, ntfy writer/
rotation intact, private HEAD7911a030… and original root index preserved.
Normal monitor/sender/credential timer remain enabled/active; native auth/
runtime API token/DB/outbox/audit are production data, not cleanup targets.
Observed creation→ACK3972.298674s (~66.2min); original six failures remain and
later intermittent transport cause is UNESTABLISHED, not a repaired/reliability/
immediate-alert claim. Diagnostics remain enabled, no recurring probe.

Next concrete work: separate node03 watchdog API identity/short-lived refresh/
durable service/outage delivery. Publisher profile UID997 already exists;
never redeliver credentials. Attended subscriber/reader, node reboot, static
UI delivery/release, safe lifecycle/retirement/plaintext/mesh gates remain.

Node03 watchdog identity/source continuation: read-only preflight PASSED,
preserving UID997 publisher profile/inodes; existing root-private bootstrap,
public CA and pinned kubectl present. New fixed watchdog credential profile/
separate root broker/two inactive unit sources passed13 checks (8 default
monitor regressions,5 watchdog cases), local unit verify and node03 parse.
Installed node02 broker/module/timer remain unchanged. Controller unit warnings
(existing Ingenium symlink/ignored CPUAccounting) retained, not target claims.

Private identity-only7970fc1cc0d7dfce2c26af76d63c74d372c568f7 PASSED source
tests/5 dry runs/full validator, then44-test singleton/exact parent+child Flux.
Five objects match source; SAUID34e95231-0974-49f4-b670-2b8f7dde0c51.
Own authenticated subject,2 allow/30 deny reviews,2 actual GETs/7 actual
Forbidden probes PASSED with sealed RAM-only candidate. Initial synthetic
smoke found absent Python fcntl names before network/mint; corrected stable
Linux UAPI plus mandatory kernel15-seal/write-EPERM/real kubectl smoke passed.
FDs closed; no disk/host credential payload or server-revocation claim.

`watchdog-host-activation/` binds current work. Actual Ansible preflight
ok6/changed0 and one broker-only staging ok15/changed6/failed0 PASSED, installing
five code files/public CA+UID/tool/resource enrollment/public config/two inactive
credential unit definitions. No account/publisher rewrite, detector state/
unit, token or enable by the play. Do NOT replay staging.

`qualify-node03-watchdog-credential.py once` is ACTIVE against that exact
checkpoint, reusing the fixed-profile bounded kernel/journal collector.
Reconcile its result/failure before dependent work; do not manually rerun a
successful or unknown broker start. It verifies actual Python security/cgroups,
effective2/30 scope/reads and private runtime token metadata, with detector
still absent. Next after accepted once: enable only its normal20min timer,
capture fresh initial invocation/due, then read-only scheduled observation.
No detector/notifier activation, node reboot, new image/build or node02 restart.
Leave any created owned runtime token for its broker/timer consumer.

Node03 `once` is terminal PASSED:295 kernel samples, observed maximum
69,402,624 bytes/four tasks; actual Python root NoNewPrivs1/CapEff+CapBnd9
under256MiB/no swap/10%/64task caps. Initial pre-exec context is separate.
Own2/30 scope/exact reads passed and private root:997/0640 token published.
Actual UID997 consumer API reads/OS read-no-write/root-bootstrap+lock denial
passed; publisher inodes unchanged. Do not repeat the successful manual run.

Credential timer ONLY is enabled/active. Initial timer invocation
2ec33698b2e1421a91a87722581a0b73 passed; next due736496052074 monotonic us
on node03 boot5a456fc3-fec9-48c6-bb1a-47c26ce5b7ad. The existing
`qualify-node03-watchdog-credential.py observe` is ACTIVE/read-only.
Reconcile `credential-observe.result.json`/failure before dependent installation;
do not reset/re-arm timer or claim periodic refresh yet. Preserve runtime token.

While waiting, source prepares detector volatile cache plus fixed UID997/node03
notifier cgroup/table wrapper, originalVIP252/TCP443 only. Four changed-helper
refusal/profile tests and two local unit verifies passed. Default node02 helper
semantics stay the same and its installed file remains untouched.
`certificate-watchdog-runtime.yml` is preflight-by-default, preserving seven
accepted broker hashes/timer and refusing pre-existing runtime state/units.
It cannot install until actual periodic proof; it never starts/enables services.
Its actual read-only Ansible preflight is active. No detector/notifier install
or node reboot happened; full monitoring feature/later gates remain active.

Watchdog continuation: periodic credential refresh PASSED at1200.312130s,
new invocation8346afa4…, token replaced root:997/0640, timer active, same boot.
Runtime install then PASSED(ok13/changed3): seven root sources/public armed
enrollment/two inactive units; broker/timer unchanged. Detector healthy phase
PASSED via read-only completion: enabled UID997/CapEff0/NoNewPrivs1 under
128MiB/no swap/5%/32tasks,0700/0600 state, healthy coverage/heartbeat/lease,
pending0, notifier inactive. Its initial failure was only a read-only SQLite
open racing detector writes; no restart/re-enable occurred.

`qualify-node03-watchdog.py outage --attempt baseline-retry` is ACTIVE: real
bounded stop of accepted node02 monitor, expect watchdog missed event/durable
outbox/node03 notifier delivery, then always restart monitor and verify recovery
event/delivery plus preserved monitor DB inode/policy/timer. The first attempt
failed before mutation (undefined read-only helper constant); it is preserved
and monitor rechecked active. Reconcile outage/missed/recovered/subscriber
receipts before dependent work; do not stop monitor manually or replay nodes.
Node reboot, attended subscriber/reader, UI status/release, lifecycle/
retirement/plaintext/mesh remain open.

Outage retry is terminal PASSED. Real bounded node02 monitor stop produced a
durable `missed` event768e7671… at181.125671s (node02 Lease stayed healthy);
node03 sender ACKed it, the monitor restarted into a new invocation, and
`recovered` event471333aa… was ACKed at01:48:36Z. Authenticated subscriber held
exactly ONE copy of each. Monitor DB inode3415914/policy/credential-timer
preserved. A read-only verifier tuple/dict defect was fixed before acceptance
and mutated nothing.

`watchdog-activation-acceptance.json` closes this checkpoint: identity7970fc1…,
44-test/Flux,2/30+7-denial scope,1200.312130s periodic broker, enabled healthy
detector plus sender/credential timer, real outage/recovery machine receipt,
11 Flux Kustomizations/36 HelmReleases/3 nodes Ready, node02 monitor/sender/
timer and private/root refs intact. Normal watchdog services and its owned
runtime token stay enabled.

Do NOT repeat identity publication, broker/periodic, detector healthy or
outage/recovery delivery for reassurance. Remaining gates: node reboot survival,
attended subscriber/reader, UI delivery label + release, kubelet CSR approval
automation, certificate retirement review and plaintext/mesh phases. The66.2min
node02 latency and unresolved intermittent transport cause remain unretrofitted.

Kubelet-serving CSR approval is now observation-delivered, approval gated.
New `kubelet_csr_controller.py` + `run-kubelet-csr-controller.py` reuse the
existing strict validator: one verdict per CSR UID, changed-request refusal,
single approval per UID across restarts, separate issued-certificate
verification, observe-by-default and approve mode inert without the operator
flag plus explicit enrollment file. Fifteen focused checks passed.
Live node02 observation was read-only (0 pending, 0 mutation).
Private checkpointb81ba44… passed44-test/validator and exact Flux; adds
`bortus-csr-controller` (SA UID244f185e…, no automount) with GET/LIST on CSRs
and nodes only. Sealed-RAM token proof:2 reads allowed,7 reviews denied,
2 actual403 (approval subresource targeted a nonexistent object).
Do NOT enable approval, install a managed controller or repeat the scope probe
until a real pending-CSR positive/negative run and endpoint verification exist.

That qualification is now PASSED (approval still disabled). Two genuine pending
CSRs came from node02's kubelet identity (`system:node:node02`): the enrolled
identity was `eligible` with no reasons; the extra-`node03`-SAN variant was
refused as `sans_invalid`. Both verdicts persisted per CSR UID with no approval
or issuance, cluster objects stayed pending, and both were then deleted under
UID/resourceVersion preconditions → zero CSRs remain. Fixture keys were
in-memory only.
`verify_served()` now enforces enrolled-issuer chain, exact DNS/IP SANs,
current validity and server-auth usage. Live node02 kubelet probe passed
(TLS1.3, CN=system:node:node02, issuer CN=kubernetes) and pinned
fingerprint80a9e9fe… NotAfter2027-11-16. Eleven controller tests pass.
Acceptance: `kubelet-csr-observation/live-qualification-acceptance.json`.
Do not enable approval, install a managed controller or replay these fixtures
before a real renewal window and restart-persistence qualification exist.

A real issuance flow has now run through the validated path. A genuine
`system:node:node02` kubelet-serving CSR was validated eligible and approved
exactly once by the operator-driven controller (approval rows = 1); the managed
service stayed in observe mode. The Kubernetes signer issued the certificate,
`verify_issued` accepted it, and its fingerprint `71374174…` matched the
fingerprint served by a bounded TLS1.3 listener holding that issued
certificate/key pair. Kubelet's own serving certificate was deliberately left
untouched (`80a9e9fe…`), so kubelet `serverTLSBootstrap` adoption is still a
separate gate.
Kubelet `serverTLSBootstrap` adoption is now demonstrated on node02. The setting
was already true; rotation was forced by moving kubelet's current serving file
aside under a root-only backup. Kubelet itself requested `csr-ds7tz` as
`system:node:node02`; the controller validated and approved that single CSR for
the enrolled node only, the signer issued it, and kubelet wrote and served it:
pre-rotation fingerprint `80a9e9fe…` became `b2d1694e…`, equal to the issued
certificate, SANs `node02`/192.168.0.6, issuer `CN=kubernetes`, NotAfter
2027-11-17. Node02 stayed Ready; monitor, sender, both credential timers and the
CSR controller stayed active. Unattended approval for *future* rotations remains
disabled, so the next rotation will queue a pending CSR for operator action.
Four defects surfaced and were fixed: controller failure reporting after a
successful approval (now reconciles cluster truth), a probe that rejected
kubelet's interim self-signed certificate, cross-attempt receipt overwrites
(now attempt-scoped), and use of `not_valid_after_utc` absent from the host's
cryptography 3.4.8. Every aborted attempt, restore and retired CSR is retained.
Node-reboot survival is now qualified on node02 (the cluster worker hosting the
monitor, sender, CSR controller and both credential timers; node03 was
deliberately deferred because it also hosts the standalone LAN DNS/DHCP).
A genuine pending outbox event was held by stopping the sender, then node02 was
rebooted: boot ID changed `137455a5…` → `f6d82213…`, every BORTUS unit came back
active/enabled without intervention, both runtime tokens were re-minted by their
20-minute timers (`root:998/0640`, `root:997/0640`), the monitor kept the same
SQLite inode `3415914`, the held event was delivered at 03:12:18Z with exactly
one authenticated subscriber copy, a fresh complete scan ran at 03:13:25Z, and
pending notifications returned to zero. The diagnostic CSR was retired under
UID/resourceVersion guards, leaving only kubelet's real issued serving CSR
(`csr-ds7tz`); inventory is 15 healthy certificates and one issued CSR. All
twelve Flux Kustomizations, 36 HelmReleases and three nodes remain Ready.
Phase C (plaintext reduction) started with a read-only node-IP inventory, no
changes made. Recorded: 22 `externalIPs` publications across all node IPs, one
NodePort service (traefik 30080/30443), three MetalLB VIPs, and 17 host
listeners — TLS on 6443/2379/2380/10250/9120/9090, plaintext on 2002, 10256,
32158/32359 (`healthCheckNodePort` for traefik-lan and pihole-lan-dns), 7946,
179, 111, node01-only 2049/29644 and node03-only 10554. Cockpit (9090) and
MetalLB metrics (9120) present self-signed certificates; 9090/32158/32359 leak
service identity in plaintext. Candidate restrictions are documented for a
separately reviewed change. UDP payload verification, per-port client
populations and the node03 DNS/DHCP path remain unmeasured.
Phase C then moved from inventory to one reviewed restriction. Bounded sampling
(60 s per node, `ss` live sockets with a validated parser; `conntrack` returned
no rows) measured **zero** clients on 32158, 32359 and 9090 on all three nodes,
while the control port 2002 showed the operator source and kubelet 10250 showed
the node01 apiserver. With no measured consumers, a fixed nftables input table
(`branconet_plaintext_restriction`) now rejects those three ports except from
loopback, the three node IPs and the operator host, applied serially across
nodes by `playbooks/plaintext-restriction.yml` with a `check` mode and a
documented `remove` rollback. Verification: all three ports remain reachable
from the operator host on every node, a pod-network source was rejected (Reject
counter incremented on node01), UFW itself was neither reordered nor disabled,
and the cluster/kubelet control path is untouched. Sampling limitations are
recorded: a 60-second window cannot see occasional clients, and the 22
`externalIPs` publications are still unrestricted.
Phase C then measured the published `externalIPs` services properly. Host `ss`
cannot see DNAT'ed service traffic, so sampling moved to `conntrack -L
--dport <port>` (75 s per node, validated by a generated control flow). Measured
real clients include Plex 32400 from internet peers (34.202.97.122,
174.91.168.36), LAN DNS clients .243/.244/.245 plus in-cluster pods on 53, and
in-cluster pods reaching the arr/web ports through node IPs. The
pihole-exporter publication (9617) had **no** in-cluster scraper — pods scrape
the ClusterIP — so it was restricted next, in a second fixed profile of the
same helper. That attempt exposed a real design error: an `input` hook cannot
restrict published Service traffic because it is DNAT'ed and forwarded; the
profile was corrected to a `forward` hook at priority −10. Verification after
correction: operator and cluster-node access to node01:9617 returns 200, a pod
on node01 reaching node02:9617 is blocked, and the reject counter stayed zero
for the operator probes. Node02/node03:9617 refuse at the endpoint layer
because the exporter pod runs only on node01; that was untested before this
step and is not caused by the rule. Rollback remains
`--extra-vars "restriction_profile=pihole-exporter restriction_action=remove"`.
A third restriction followed the same measured pattern. A 120-second
conntrack window showed **no** clients on 3306 (ruckus-db), 8088, 8089, 8096,
8082 or 8083; only 8080/8081 saw traffic, and solely from the node's own IP.
The database port was therefore restricted first via a `ruckus-db` forward-hook
profile. That step exposed a second real design fault: cross-node Service
traffic reaches the target node with a **pod-network source**, so a LAN-only
allowlist silently rejected in-cluster consumers (reject counter rose and the
connection was refused). Both forward profiles now also allow `10.244.0.0/16`,
after which the operator gets the MySQL 8.4.13 greeting from all three node IPs,
a cluster node connects, and the earlier pihole-exporter "endpoint layer"
note was corrected — all three node IPs return 200 once the pod CIDR is
allowed. A spoofed-source probe was attempted but proved inconclusive: an
unlisted source is dropped by reverse-path filtering before the rule, so
rejection evidence rests on the real pre-fix cross-node refusal, not spoofing.
A fourth restriction covered the ruckus-bot publication. A 60-second conntrack
window showed no clients on either published port, and both `3003` and `8088`
were restricted together (a service profile must cover every published port, not
just the one under discussion). Verification after apply, with the pod CIDR in
the allowlist: the operator host receives HTTP 200 on `:8088` and HTTP 404 on
`:3003` from **all three** node IPs (the 404 is the application's own response,
so both are reachable), a cluster node gets the same codes, an in-cluster pod
reaches both ports through a node IP, and the reject counter did not move during
any allowed probe. An initial operator probe helper reported AttributeError;
direct HTTP probes proved the service reachable, and the helper defect is
recorded rather than the network. Remaining published services (8089, 8096,
8082, 8083, 8080, 8081, 8089 and the Plex/DNS/traefik set) are untouched.
A fifth restriction covered mealie (8089). A 90-second window measured no
node-IP clients for either 8089 or 8096, but only mealie was restricted:
vaultwarden is a credential-vault path whose clients (phones, extensions) sync
sporadically, and a 90-second silence cannot prove absence, so it is deferred
pending an owner decision or long observation. After apply, the operator
receives HTTP 200 for mealie from **all three** node IPs, a cluster node and an
in-cluster pod also get 200, and the reject counter did not move during any
allowed probe. Remaining published services are 8080/8081 (node-self traffic
only), 8082/8083, 8096 (deferred) and the Plex/DNS/traefik set that has real
external or LAN clients.
Phase D started read-only. Mesh control plane healthy (istiod x2, ztunnel x3,
istio-cni x3); nine namespaces ambient-enrolled, `bortus` is not. BORTUS runs one
container, no sidecar, SA `bortus-kv` with automount true, Recreate, 1Gi limit,
three probes, env from `secret/bortus-runtime` (jwt-secret, lookup-token), PVC
`bortus-data` (Longhorn, Retain, attached/healthy, replicas on node02+node03) and
four Traefik ingresses for bortus.branconet.lan. No PeerAuthentication,
AuthorizationPolicy or NetworkPolicy exists in the namespace, so ambient alone
would not enforce strict mTLS. Enrollment must re-qualify probes, ingress, DNS
and API egress and keep the claim. Evidence in `phase-d-baseline/`.
BORTUS is now ambient-enrolled with strict mTLS. Two private checkpoints did
this through the validated path (44 tests, full validator, singleton promotion,
exact Flux): `7ae7c95…` labelled the namespace `istio.io/dataplane-mode=ambient`
and added a PERMISSIVE `PeerAuthentication`; `1c5ebf0…` switched it to STRICT
after the permissive window was qualified. The existing pod was recreated
(`780bb378…` → `a8ded156…`) because enrollment happens at pod creation; the
running pod carries the `ambient.istio.io/redirection=enabled` annotation (it is
an annotation, not a label).

Qualification, PERMISSIVE and then STRICT: all three kubelet probes pass with
0 restarts; `bortus.branconet.lan` resolves to 192.168.0.252 and returns
HTTP 307 → `/welcome` through Traefik with the LAN CA trusted; the pod reaches
the Kubernetes API (`https://192.168.0.251:6443/healthz` → 200 `ok`) so API
egress survives ztunnel; and a non-enrolled pod's plaintext request to the
BORTUS service is now **rejected**, which is the enforcement evidence that
PERMISSIVE could not give. Storage is unchanged: the same `bortus-data` PVC UID
and PV, with both Longhorn replicas still started on node02 and node03.

Limits: Traefik→BORTUS mTLS is inferred from the working ingress path rather
than an explicit SPIFFE identity assertion; the PERMISSIVE window was minutes,
not a soak; and no attended browser acceptance was performed. Rollback is to
revert `bortus-mesh.yaml` to PERMISSIVE (or remove the namespace label).
Phase D then enrolled a single Plex application without touching the shared
namespace. Bazarr's dependency check first: it has three claims (`/config`,
`/tv`, `/movies`), no probes, ClusterIP 6767 plus a published 6767, no
`gluetun` container in its pod, and at runtime only `lo`/`tunl0`/`eth0` with a
`eth0` default route — so despite carrying `VPN_*` keys from its runtime secret
it is **not** tunnelled and cannot inherit the VPN pod's netns. Peer reachability
was 200 for sonarr, radarr and Plex.
Because the `plex` namespace also holds the VPN and host-network workloads, the
namespace was **not** enrolled; the bazarr pod template alone received
`istio.io/dataplane-mode: ambient` (checkpoint `3fc2cba…`, HelmRelease
`0.1.3+3fc2cba15695` Ready). After the rollout the new pod carries
`ambient.istio.io/redirection=enabled` with 0 restarts; sonarr, radarr and Plex
still answer 200 from inside the pod; sonarr reaches `bazarr:6767` with 200
(plaintext peer allowed because the namespace has no strict policy);
`bazarr.branconet.lan` serves HTTP 200 through Traefik with the LAN CA trusted;
and all three claims remain Bound with their original PVs.
Evidence: `phase-d-bazarr/{bazarr-dependencies,bazarr-network-baseline,
enrollment-qualification,phase-d-bazarr-acceptance}.json`. Rollback is removing
the pod label. Playback with a real client and SSDP discovery (xteve) were not
exercised.
Phase D repeated the pod-level pattern for sonarr. Baseline: a single
`linuxserver/sonarr` container, no VPN interface, `eth0` default route, no
`hostNetwork`, three claims (`/config`, `/media/tv`, `/downloads`), no probes,
ClusterIP/published `8989`; radarr/bazarr/Plex/qBittorrent all answered before
the change. Only the pod template label was added (checkpoint `c381f2b…`,
HelmRelease `0.1.2+c381f2b5c180` Ready); the `plex` namespace stayed unenrolled.
After rollout the pod carries `ambient.istio.io/redirection=enabled` with 0
restarts; outbound sonarr→radarr 302, →bazarr 200, →Plex 200; inbound
radarr→sonarr and bazarr→sonarr both 302; `sonarr.branconet.lan` serves 302
through Traefik with the LAN CA trusted; and all three claims are unchanged and
Bound. Rollback is removing the pod label. No real indexer/playback run and no
attended UI check were performed.
Phase D then enrolled radarr the same way. Baseline: single `linuxserver/radarr`
container, no VPN interface, `eth0` default route, no `hostNetwork`, no probes,
claims for `/config`, `/media/movies` and `/downloads`, ClusterIP/published
`7878`; sonarr/bazarr/Plex/qBittorrent all answered beforehand. Only the pod
template label changed (checkpoint `426b198…`, HelmRelease
`0.1.2+426b19890da7` Ready), leaving `plex` unenrolled. After rollout the pod
carries `ambient.istio.io/redirection=enabled` with 0 restarts; outbound
radarr→sonarr 302, →bazarr 200, →Plex 200; inbound sonarr→radarr and
bazarr→radarr both 302; `radarr.branconet.lan` serves 302 through Traefik with
the LAN CA trusted; and all three claims are unchanged and Bound. Rollback is
removing the pod label. No real indexer fetch, playback or attended UI check was
performed.
Phase D then enrolled tautulli. Baseline: single `ghcr.io/linuxserver/tautulli`
container, no VPN interface, `eth0` default route, no `hostNetwork`, no probes,
one `/config` claim, ClusterIP `8181` plus published `9119`; Plex 200 and
sonarr/radarr 302 answered before the change. Only the pod template label
changed (checkpoint `c96e062…`, HelmRelease `0.1.0+c96e062ba0d7` Ready), with
`plex` still unenrolled. After rollout the pod carries
`ambient.istio.io/redirection=enabled`, 0 restarts; outbound Plex 200,
sonarr/radarr 302; inbound sonarr→tautulli and bazarr→tautulli both **303**;
`tautulli.branconet.lan` serves 303 through Traefik with the LAN CA trusted; and
the claim is unchanged and Bound. A first predicate accepted only 200/302 and
wrongly failed this step; Tautulli's 303 is a served redirect and the check was
corrected and recorded. Rollback removes the pod label. No real Plex activity
ingestion and no attended UI check were performed.
Phase D then enrolled jackett. Baseline: single `linuxserver/jackett` container
with readiness and startup probes, no VPN interface, `eth0` default route, one
`/config` claim, ClusterIP `9117` plus a published `9117`; flaresolverr 200,
sonarr/radarr 302 and Plex 200 answered beforehand. Only the pod template label
changed (checkpoint `f4f1dc4…`, HelmRelease `0.1.0+f4f1dc4c3993` Ready), keeping
`plex` unenrolled. After rollout the pod carries
`ambient.istio.io/redirection=enabled` with 0 restarts; outbound flaresolverr
200, sonarr/radarr 302, Plex 200; inbound sonarr→jackett and radarr→jackett both
**301**; `jackett.branconet.lan` serves 301 through Traefik with the LAN CA
trusted; the claim is unchanged and Bound. Rollback removes the pod label. No
real indexer search and no attended UI check were performed.
Phase D next attempted flaresolverr and **rolled it back**. Baseline was fine
(single FlareSolverr 3.5.2 container, no VPN interface, `eth0` default route,
`/config` mount with no claim, ClusterIP plus published `8191`, local GET 200).
After adding only the pod label (checkpoint `5c8376a…`, HelmRelease
`0.1.3+5c8376a50d1c` Ready) the pod was Ready and listening on `0.0.0.0:8191`
inside the container, yet unreachable from jackett, sonarr and bazarr, and even
from a non-mesh pod to the pod IP. Rollback to `e0305ae…` restored in-cluster
access (jackett and sonarr both 200 to `flaresolverr:8191`).
Two honest findings: 17 pods had been **Evicted by node03 DiskPressure** around
this window (node03 now reports DiskPressure=False with 21 GB free), so mesh
causality is **not** established for the outage; and the published node-IP path
`8192`… i.e. `8191` on 192.168.0.4/.5/.6 timed out both before and after the
rollback while the Service lists those externalIPs and an endpoint exists —
kube-proxy rules could not be read without sudo, so this is recorded as an open,
likely pre-existing gap rather than a mesh effect. Flaresolverr remains
unenrolled; the app needs a cleaner pass after node03 hygiene is reviewed.
The flaresolverr re-attempt was **deferred pending diagnosis**, not retried. Two
investigations ran read-only. Node03 did evict 17 pods and kubelet logged 29
eviction/DiskPressure lines in 12 hours, but the node now reports
DiskPressure=False, root has 21 GB free (82 GB used, 80%), and the `du` "10T" on
`/var/lib/kubelet` is a mounted volume being followed, not host consumption.
For the published path: `flaresolverr-published` is a ClusterIP Service with
externalIPs `.4/.5/.6`, `etp=Cluster`, `8191→8191` — the same shape as working
`sonarr` 8989 and `jackett` 9117 — and node01's iptables already contains
KUBE-SVC/KUBE-SEP/KUBE-EXT rules DNATing 8191 to `10.244.186.239:8191`. Yet TCP
to `.4/.5/.6:8191` times out from the operator host while `.4:8989` is open, the
in-cluster Service path from jackett returns 200, and a direct pod-IP connect
from an enrolled peer did not succeed. UFW is active with default **deny
routed** and only `8079:8098/tcp` explicitly allowed, which is a plausible
contributor for forwarded service traffic to a pod on another node.
No mesh label, Service, firewall or node change was made. Re-attempt is blocked
on: testing forwarded published traffic to a pod that is not on the queried
node, inspecting UFW forward/before chains, and confirming whether any published
port to a node03 pod works.
Both findings were then resolved and the enrollment completed. The published
`8191` timeout is explained by the pod's own pre-existing NetworkPolicy
`plex/flaresolverr-ingress`, which allows ingress only from `podSelector {}`
(same namespace) on TCP 8191: `externalIPs` traffic is masqueraded by kube-proxy
so its source is a node IP and the policy denies it. That policy is why
`sonarr`/`jackett` serve on the node IPs while `flaresolverr` never did — it is
pre-existing and unchanged in scope. The 17 node03 evictions were a historical
DiskPressure spike; the node now reports `DiskPressure=False` with 21 GB free,
and the brief `000FAIL` blips were pod churn, not connectivity loss.

Re-attempting with the label (checkpoint `44b1aaf…`) reproduced the failure
deterministically, which isolated the real defect: an **enrolled** pod whose only
ingress allowlist omits the ambient HBONE inbound port `15008`. Enrolled→enrolled
traffic is HBONE to 15008, so every same-namespace caller failed, while
enrolled→non-enrolled plaintext on 8191 still worked. An additive test policy
allowing 15008 from same-namespace pods restored jackett/sonarr to 200
immediately; the test policy was then deleted. The chart fix
(`785dae7…`, HelmRelease `0.1.3+785dae7cb361` Ready) adds TCP 15008 to the same
`from: podSelector {}` rule — no `namespaceSelector` was added, so isolation is
unchanged.

Qualified after the fix: pod `flaresolverr-6c7b958567-5nrcc` enrolled with
`ambient.istio.io/redirection=enabled`, 0 restarts; jackett, sonarr and radarr
all reach both `flaresolverr:8191` and the pod IP with 200; the published
node-IP path stays blocked exactly as before (policy, not a regression); and the
platform control (`192.168.0.4:8989` → 302) is unaffected. `/config` is an
`emptyDir`, so there was no claim to preserve. Evidence:
`phase-d-flaresolverr/{phase-d-flaresolverr-acceptance,hbone-flux-result,
retry-flux-result}.json` and `node03-hygiene/{findings-resolution,
networkpolicy-cause,firewall-chains}.json`.
Phase D then enrolled xteve. Baseline: two binaries in one pod
(`ghcr.io/volschin/threadfin` plus a `legacy-guide-routes` nginx sidecar), no VPN
interface (`lo`/`tunl0`/`eth0`), `eth0` default route, no probes, three claims
(`xteve-data-0/1/3`), ClusterIP `xteve` (`1900`, `34400→34401`) plus
`xteve-published` (`1901→1900`, `34400→34401`), and **no Ingress object**. No
NetworkPolicy selects `app=xteve`, so the flaresolverr `15008` defect could not
apply — and the published node-IP path worked from the operator host *before*
the change (200 on `:34400`), unlike flaresolverr.
The chart also defines a separate **`xteve-ssdp` Deployment with
`hostNetwork: true`** for SSDP discovery. Only the `app: xteve` pod template
received the ambient label (checkpoint `c3b3bbd…`, HelmRelease
`0.1.2+c3b3bbd990be` Ready; the render contains exactly one ambient label), so
the host-network SSDP gateway remains outside the mesh — verified by its pod
having no ambient annotation.
Qualification: pod `xteve-85fb58cdc9-qcsz6` enrolled with
`ambient.istio.io/redirection=enabled`, 0 restarts; sonarr, radarr and jackett
each reach `xteve:34400` and the pod IP with 200; xteve→Plex 200; the SSDP
gateway (non-enrolled, plaintext) still reaches `xteve:34400` with 200; the
operator's published path stays 200; and all three claims are unchanged.
`xteve:1900` resets, but it failed the same way **before** enrollment, so that is
pre-existing and not caused by this change.
**qBittorrent was deliberately not enrolled**: its pod carries `tun0` and the
`checksum/proton-wireguard` annotation, so it terminates Proton WireGuard inside
the pod. Proxying its egress through ambient ztunnel risks traffic leaving
outside the tunnel, which is a leak boundary rather than a mesh-coverage gap.
Evidence: `phase-d-xteve/{xteve-baseline,flux-result,source-result,
phase-d-xteve-acceptance}.json`.
Phase D then assessed **Pi-hole and deliberately did not enroll it**. Its pods are
ordinary (no `hostNetwork`, no in-pod VPN) and no NetworkPolicy selects them, so
the flaresolverr `15008` defect does not apply — but the transport evidence
disqualifies it anyway: ztunnel listens on TCP only (`15000/15008/15020/15021`,
**no UDP listener**), and in an enrolled pod netns `ISTIO_PRERT` redirects **TCP
only** to `15006` while `ISTIO_OUTPUT` sends **all outbound UDP** to `15053`,
which is a DNS *client* interception proxy. Pi-hole is a DNS *server*: inbound
UDP 53 would gain no mesh protection (it bypasses ztunnel) while its outbound
UDP — including replies to LAN clients — would be captured by a DNS-client
proxy. With the advertised LAN VIP (`pihole-lan-dns`, `etp=Local`) and the node03
standalone DNS/DHCP path sharing that role, that is an availability risk with
LAN-wide blast radius for zero coverage gain. It therefore stays out of the
mesh. (CoreDNS forwards to 1.1.1.1/8.8.8.8, not to Pi-hole, so the cluster
itself is independent of it.) Evidence: `phase-d-pihole/pihole-deferral.json`.

The other Phase D remainder — the previously ambient namespaces — was then
qualified read-only: **10 namespaces, 15 of 15 pods enrolled**, with six STRICT
(`bortus`, `homepage`, `http-echo`, `mesh-pilot`, `website-stack`, `whoami`) and
four with no `PeerAuthentication` (`mealie`, `ruckus`, `vaultwarden`,
`web-apps`). The important finding is that **nine `AuthorizationPolicy` objects
with `action: ALLOW` provide default-deny**: only `traefik/traefik`,
`cloudflare-tunnel/public-web-tunnel` and a few namespace-scoped principals are
allowed. That explains the east-west refusals — e.g. `ruckus-bot` is refused
(`ConnectionReset`) by whoami, http-echo, website-stack, homepage and web-apps,
while same-namespace `ruckus-bot → ruckus-db:3306` is open. They are policy, not
breakage. The intended path was verified instead: eight ingress hostnames answer
200 through Traefik with the LAN CA (`homepage`, `http-echo`, `mealie`, `ruckus`,
`vault`, `aplb`, `lucinda`, `whoami`); `jtmb-dev` and `mesh-pilot` have no DNS
record here so their ingress path was not exercised. Evidence:
`phase-d-ambient-set/{ambient-inventory,ambient-traffic,ingress-path,
phase-d-ambient-set-acceptance}.json`.
**Unattended kubelet-serving approval is now enabled and proven end to end.** The
prerequisite chain was completed first: the controller's ClusterRole gained
signer-scoped approval (`approve` on `signers/kubernetes.io/kubelet-serving`
plus `get, patch, update` on `certificatesigningrequests/approval`), delivered
through the unchanged 44-test/validator/Flux path in three revisions
(`255c187…`, `1508c97…`, `28d5552…`) because each verb requirement only surfaced
from the API server's own refusal. Signing, create/delete, other signers,
Secrets and node writes remain denied.
The managed unit was switched from observe to approve with a reversible drop-in
(`/etc/systemd/system/bortus-csr-controller.service.d/10-approval.conf`,
`playbooks/csr-approval-toggle.yml`; rollback is
`--extra-vars csr_approval_action=disable`).
Proof: a genuine rotation was forced on node02 by moving kubelet's serving file
aside. The **service** approved the resulting CSR with **0 operator commands**
(durable row `csr-s7q4l` / `9b3a50c5…`), the signer issued it, and kubelet now
serves it — `80a9e9fe…` → `846e474a…`, issued equals served, TLS1.3, issuer
`CN=kubernetes`, NotAfter 2027-11-17. Node02 stayed Ready.
Three real defects were found and fixed on the way: the RBAC verb set
(`update` alone was insufficient — `get` and `patch` were also required); the
credential broker quarantined the runtime token because its expected permission
matrix went stale after the widening (so approve mode silently lost its
credential); and the controller wrote its exactly-once approval row **before**
the PATCH and never released it on a definite failure, wedging that CSR forever
(`release_approval` now clears the row only when the API server confirms the
object is not approved, preserving exactly-once for genuinely uncertain
outcomes). Attempts 1-3 each wedged a CSR; all were retired under
UID/resourceVersion guards. Evidence:
`csr-unattended-approval/{unattended-acceptance,unattended.result,rbac3-flux-result,
enable-result,upgrade4.log,pre-retry-reconciliation}.json`.
The Phase C remainder was then closed with measured evidence. A 120-second
conntrack window per node showed **zero** node-IP clients on 8082 and 8083,
node-self traffic only on 8080 (2024/2112 flows from the node's own IP) and 8081
(92), and zero on 8096. Three further forward-hook profiles were added and
applied through `playbooks/plaintext-restriction.yml`: `minecraft-website`
(8083), `aplb` (8082) and `web-apps-local` (8080 + 8081 — safe because their only
observed clients are node IPs, which stay in the allowlist). Verification after
apply: the operator host gets HTTP 200 on all four ports from all three node IPs,
an in-cluster pod gets 200 on all four, node-to-own-IP stays 200 on both nodes
that polled themselves, and every reject counter stayed at 0 during the allowed
probes. Rollback is `--extra-vars "restriction_profile=<name>
restriction_action=remove"`. Two probe mistakes were caught and corrected in the
process: a loopback probe (nothing listens on 127.0.0.1) and a mangled SSH
argument list. Only `vaultwarden` 8096 remains unrestricted by decision, because
its clients sync sporadically and a bounded window cannot prove absence.
The inventory is now eight tables per node, identical on all three:
`core` (32158/32359/9090), `pihole-exporter` (9617), `ruckus-db` (3306),
`ruckus-bot` (3003/8088), `mealie` (8089), `minecraft-website` (8083),
`aplb` (8082) and `web-apps-local` (8080/8081). Evidence:
`plaintext-inventory/{phase-c-remainder-sampling,minecraft-verification,
phase-c-remainder-acceptance}.json`.
The 66.2-minute node02 notification latency was then diagnosed read-only. The
figure is not one slow send: the event was created at 23:30:14Z and acknowledged
at 00:36:26Z (**3972.3 s**) across **six** failed attempts with the last failure
at 00:35:57Z, so the delay is the retry/backoff schedule, with codes
`notification_transport_unavailable` (phase transport) and `process_failed`
(phase child). Four alternatives were eliminated with measurements: the ntfy pod
started 22:29:27Z with **0 restarts** and was never replaced during the window
(not server availability); `PinnedHTTPSConnection` connects to the configured
address and uses the hostname only for SNI, so there is **no DNS lookup**
(not resolution); six fresh connect+TLS+request round trips from node02 to the
VIP total **48-56 ms** (not network latency); and the egress rule's accept
counter is 55 with the exact destination permitted (not a blocked path).
The strongest remaining cause is **CPU-budget saturation against the sender's own
3-second timeout**: `publish_ntfy` sets `timeout=3` for connect and TLS, the unit
is capped at `CPUQuotaPerSecUSec=50ms` (`cpu.max "5000 100000"`) and reports
`nr_throttled 423 of 586` periods with 40.0 s cumulative throttled time, while
measured full-child runs took 1.806 s and 2.399 s — 60-80% of that 3 s budget —
with only ~55 ms of it being network. Honest limits: the original failures
predate the `transportStage`/`transportKind` annotation, so no run has captured
`kind=timeout`, and the diagnosis is therefore **strongly supported but not
reproduced**. The egress table's 15 rejected packets are historical residue
(unchanged over 75 s with no pending events), not an ongoing block, but remain
unattributed. **No code or resource change was made**, because the cause is not
proven; the proposed reviewed fix is to raise the inner timeout from 3 s to ≤8 s
(still inside the existing 10 s per-child budget, at no cost on a 55 ms path)
and/or raise the CPU quota, ideally paired with capturing `transportKind` on the
next real failure. Evidence:
`notification-latency-diagnosis/latency-diagnosis.json`.
The `wordpress/jtmb-cc` certificate was then retired after a dependency check.
Six reference classes were enumerated and all were empty: no apex
`jtmb.cc`/`www.jtmb.cc` Ingress or IngressRoute rule anywhere (28 ingress hosts,
none apex), no Ingress TLS `secretName: jtmb-cc-tls`, no other Certificate
sharing that Secret, no pod volume and no pod `envFrom` reference. The
`wordpress` namespace held only the Certificate (UID `591745ea…`, Ready=True,
dnsName `jtmb.cc`, ClusterIssuer `letsencrypt-production-http01`), its
CertificateRequest/Order, and the Secret (UID `6e544d1c…`, `tls.crt`/`tls.key`,
**no ownerReferences**). The domain itself resolves to Cloudflare
(`172.64.80.1`), whose edge certificate serves TLS, so the cluster Secret was
never on that path.
The declaration was removed from the private charts
(`flux/releases/foundation/public-certificates.yaml` deleted plus its
kustomization entry, checkpoint `886d93c…`, unchanged 44-test/validator gate and
a render confirming absence). Because `migration-releases` has **prune=false**,
Flux applied the source change without deleting the object — verified by the
unchanged UID and resourceVersion — so both objects were then deleted with
`uid` + `resourceVersion` preconditions. Post-state: no residual Certificate or
Secret, no leftover CertificateRequest/Order/Challenge, `jtmb.cc` and
`mealie.jtmb.cc` still resolve to Cloudflare, and certificates went from 15 to
**14 healthy of 14**. Rollback is `git revert 886d93c…`, after which cert-manager
re-issues and recreates the Secret. Left for a separate decision, and
deliberately untouched: the namespace still holds retired-chart Helm release
Secrets, their `-runtime` Secrets, and `source-acme-0..5` copies that no
`wordpress` Ingress references. Evidence:
`certificate-retirement/{wp-retirement-pre-state,flux-result,delete-result,
retirement-verification,retirement-acceptance}.json`.
UDP payload verification was then performed read-only, with real payloads rather
than assumptions. Listener inventory: node01 holds UDP 53 (systemd-resolve), 68,
111 (rpcbind), **1900 (python3)**, 7946 (speaker) and NFS rpc ephemeral ports;
node03 holds 53, **67 (dnsmasq — the standalone DHCP)**, 111, 7946 and 10554
(pihole-FTL). Plaintext was confirmed by capturing actual traffic:
DNS answers on three resolution paths (floating `192.168.0.253`, standalone
`192.168.0.5` and the node-IP externalIP `192.168.0.4`) with
`bortus.branconet.lan → 192.168.0.252` and a two-record CNAME chain for
`notifications.branconet.lan`; **Plex GDM** replied on node01 UDP 32410 and 32414
with a readable `HTTP/1.0 200 OK / Content-Type: plex/medi…` payload; and **mDNS
5353** produced six cleartext PTR/AAAA records from `172.25.192.1`. No responder
appeared for SSDP 1900 (a python3 process holds the port but answered no
M-SEARCH for three ST types and emitted no NOTIFY during a 12 s passive
capture), for Plex GDM on node03, or for an unsolicited memberlist probe on
7946, whose framing is plaintext UDP with an opaque/keyed payload. Not verified,
deliberately: a DHCP 67 lease exchange (taking a lease would disturb the LAN),
memberlist payload contents, and payloads for rpcbind/NFS ephemeral ports. The
12 s windows cannot exclude infrequent announcements, and the mDNS/SSDP samples
came from the operator network path rather than from cluster pods. Evidence:
`udp-payload-verification/udp-verification.json`.

The Certificates UI release gate was then assessed and is **definitively
unreleased**: the deployed image `…e7539b9e` contains no `certificates` route
under `.next/server/app/(dashboard)` and no `api/certificates`, while both exist
in source, so the screen cannot be served from the running build. The "static
delivery label" is a hardcoded string literal at
`src/app/(dashboard)/certificates/monitor-controls.tsx:51` (`"· delivery not
configured"` inside a `<span>`), not derived from monitor state. Closing this
gate requires a real image release: rebuild under the H qualification path,
publish the immutable reference, update the private chart pin, roll the
single-replica `Recreate` deployment, re-run the API/UI and LAN-CA ingress
checks, and replace that literal with state derived from the monitor snapshot.
That is a production restart and was therefore not performed as part of a
read-only assessment. Evidence: `ui-release-assessment/ui-release-assessment.json`.
The Certificates UI delivery label was then converted from a hardcoded literal to
derived state, and the release was **stopped at a real blocker**. The monitor now
derives `notificationDelivery` from the outbox instead of returning a constant
(`CertificateMonitor.delivery_state()` → `not-configured` / `no-delivery-yet` /
`pending-delivery` / `delivered`, exercised against an in-memory database for
three of the four transitions); `MonitorView` gained a validated union, the
snapshot parser rejects unknown values, and
`monitor-controls.tsx` renders `deliveryLabel()`/`deliveryTone()` from monitor
state instead of the `"· delivery not configured"` literal. Verification:
project-wide `tsc --noEmit` exit 0 and `eslint --max-warnings=0` exit 0 on both
changed files, using the retained H dependency tree through a temporary symlink
(no install or copy made; the symlink was removed afterwards).
Release is blocked by a concrete contract, not by effort:
`prepare-bortus-release-context.py` builds the Docker context from a **git
commit** (`--source-commit`, `git ls-tree`/`cat-file`), so an image can only be
produced from a committed revision. Every certificate-UI change in this session
is uncommitted, in a root repository that has deliberately preserved a large body
of unrelated staged/uncommitted work and a fixed index SHA-256 `778cf730…`
throughout. Committing the root repository is therefore an owner scope decision,
and the release itself restarts BORTUS (`Recreate`, 1 replica). The three options
are recorded: a scoped certificate-UI commit, a full-tree commit (not recommended
unreviewed), or leaving the UI unreleased with the code staged. Evidence:
`ui-release-assessment/ui-label-implementation.json`.
The authorized scoped commit was then made and the release context built, but the
**image build was refused by the builder environment**. Commit
`d43f05b2d227f8b7613098e081db812c7e9797cc` ("Add the Certificates screen with
derived delivery state") contains 13 files: the three `certificates` dashboard
components, both `api/certificates` routes, `certificate-control.ts`,
`certificate-inventory.ts`, `sidebar.tsx` (the nav entry), four certificate test
fixtures and `scripts/migration/certificate_monitor.py`. Staged work went from 971
to 970 paths, so the unrelated staged body was preserved; the one consumed path,
`sidebar.tsx`, already carried 93 insertions/92 deletions of its own, which is
disclosed rather than folded in silently.
`prepare-bortus-release-context.py` then succeeded against the exact lowercase
commit: **164 included files, 9 excluded, 296,403 bytes, context SHA-256
`06bb3750…`, manifest SHA-256 `44889e99…`, application tree `df6a71b2…`**, with
the producer recording `image_built=false` and `cluster_mutations=0`. The first
invocation failed because the contract compares against the full 40-character
SHA and I passed an abbreviated one.
`build-bortus-release-image.py` was then dispatched and refused at `tag_query`
with `Cannot connect to the Docker daemon at unix:///var/run/docker.sock`: the
fixed build host **node01 has no Docker daemon** (`systemctl is-active docker` →
`inactive`, no socket), while the operator WSL daemon is healthy (29.6.2,
overlayfs) but is not the pipeline's destination. The refused run
`bortus-release-d43f05b2…/record.json` is retained with `deployed=false` and
`runtime_accepted=false`, and the helper refuses to replay or adopt an existing
run, so it must be reconciled before another attempt for this commit. Enabling
dockerd on a live control-plane node would add the DOCKER iptables chains beside
kube-proxy, which is a node-level service change rather than a routine repair, so
the build was not forced. Evidence: `ui-release/{context-evidence.json,
build-blocked.json}` and the retained `record.json`.
The Certificates UI image was then built, verified and published, but the rollout
was stopped by a delivery requirement and rolled back. Option B was completed
first: the certificates page and both `api/certificates` routes were adapted to
the **deployed** lib surface (`getCurrentRole`, `getSession`, `requireWrite`) and
to the deployed `kubectlJSON(cmd: string)` signature via `args.join(" ")` after
confirming every argument token is space-free (commits `ea041f1d`, `82580115`).
The release tree reverts `auth.ts`/`permissions.ts` to the deployed versions
through a temporary `GIT_INDEX_FILE` plus `read-tree`/`update-index`/
`commit-tree`/`update-ref`, so the working tree keeps the in-progress auth
refactor untouched and the shared index was not modified.
`build-bortus-release-image.py` then completed after the builder was repaired
(node01 `docker` was inactive with no socket; started it, verified
`FORWARD` policy stayed `DROP` and the cluster was unaffected: 3/3 nodes Ready,
65/65 pods on node01 ready, cross-node probes 200 both ways). The artifact is
`sha256:1688194a…`, 1,114,174,137 bytes, revision `82580115…`, source tree
`cc0f292f…`, and **provably contains the feature**: `.next/server/app/(dashboard)`
lists `certificates` and `.next/server/app/api/certificates` exists. It was
pushed to Docker Hub as `jtmb92/bortus@sha256:44a163a9…` (exit 0).
Pinning exposed one more gate requirement: the validator refuses an image that is
not listed in all three Flux-owned admission Deny policies, so the digest was
added to `approvedImages` in the three `bortus-kv-guard-*` policies and the full
44-test/validator gate passed (checkpoint `34b5890…`). Flux applied it and the
deployment switched to the new digest — then failed with **`ErrImageNeverPull`**:
the deployment uses `imagePullPolicy: Never`, so a new digest must be preloaded
into the worker node image stores, and node03 did not have it. BORTUS was
unavailable for roughly 13 minutes before the pin was rolled back
(`a5165a0…`) to the preloaded `e7539b9e` digest; the pod is Running and Ready
again. The new digest stays in `approvedImages`, so completing the release now
only needs the node preload (`bortus-release-preload-node.py`) followed by a
re-pin and the API/UI plus LAN-CA acceptance. Evidence:
`ui-release/{release-outcome.json, pin-commit-intent.json, pin-flux-result.json,
rollback-result.json}`.
**The Certificates UI is released and live.** The delivery failure was diagnosed
precisely: `docker save` of the unqualified local tag stores the image as
`docker.io/library/bortus:release-82580115…`, so neither the `jtmb92` repository
path nor any digest reference existed on the nodes — which is why both the
ad-hoc import and the first pin produced `ErrImageNeverPull`. The supported path
(`stage-bortus-release-image.py export` then `preload` with build and export
receipts, `{"sudo_password":…}` on stdin) exported the archive
(1,149,636,096 bytes, sha256 `d6518eed…`) and imported it on **all three nodes**
with `import_exit_code 0` and per-node archive identity verified, reporting the
platform manifest digest `858ddb5c…`. Two references were then added on each
node with `ctr images tag`: `docker.io/jtmb92/bortus@sha256:858ddb5c…` and the
registry index digest `@sha256:44a163a9…`, and verified by listing.
Re-pinning (`4293bd5…`) passed the validator unchanged because the digest was
already in all three Flux-owned Deny policies, Flux rolled the single-replica
`Recreate` deployment, and pod `bortus-6b77c798cf-m2cc9` is Running and Ready
with 0 restarts. Live acceptance (`verify-certificates-ui-release.py`) passes
**every** check: the deployment uses the new digest; the running pod's
`(dashboard)` route set contains `certificates` and
`/app/.next/server/app/api/certificates` exists **inside the running image**;
`/api/certificates` answers **401** (auth-gated, not 404) and `/certificates`
answers **307 → /welcome** through `bortus.branconet.lan` with the LAN CA
trusted. Cluster: 12/12 Kustomizations healthy, 3/3 nodes Ready. The earlier
13-minute outage, the refused/failed/interrupted build runs and the rolled-back
pins (`a5165a0…`) all remain recorded. Remaining gates are unchanged: node03
reboot survival, attended subscriber/reader receipt, the vaultwarden 8096
decision, real playback/discovery exercise, and DHCP 67 / memberlist /
rpcbind-NFS payload verification. Evidence:
`ui-release/{release-acceptance.json, release-acceptance-final.json,
rollout-result.json, pin3-result.json}`.
**node03 reboot survival is now accepted.** The reboot was performed
(`systemctl reboot`), boot ID changing `5a456fc3…` → `f9246c77…`. Recovery was
verified rather than assumed, and one detail mattered: DHCP 67 is **not**
`dnsmasq.service` (inactive) but `branconet-lan-dhcp.service`
(`/system.slice/branconet-lan-dhcp.service`), which is what the post-check
asserted. After the reboot `kubelet.service`, `branconet-lan-dhcp.service` and
all three BORTUS watchdog units (`bortus-certificate-watchdog.service`,
`-notifications.service`, `-credential.timer`) are active/enabled, UDP 67 is
listening again on `0.0.0.0%enp3s0`, and DNS 53 answers with rcode 0 on both the
standalone `192.168.0.5` and the floating `192.168.0.253` — the floating resolver
kept answering, so LAN resolution never depended on the rebooting node.
node02's monitor, sender, CSR controller and credential timer were unaffected.
Workloads: 27 of 27 live pods on node03 are fully ready; the 34 non-running
objects there are pre-existing Failed/Evicted pods from Nov 8/15 and 03:23, older
than this reboot, not reboot casualties. Longhorn settled to **0 degraded** with
30 healthy volumes; the 17 stopped replicas belong to detached volumes reporting
robustness `unknown`, which is normal for retained-but-unattached claims.
Importantly the **newly released Certificates UI survived the reboot** — the
BORTUS pod came back ready on digest `44a163a9…`. Cluster is 3/3 nodes Ready.
Evidence: `node03-reboot-survival/{pre-reboot.json, reboot-issued.json,
post-reboot.json, node03-reboot-acceptance.json}`.
A real media exercise and two payload checks were then completed. **Tuner
discovery is genuine**: xteve's `/discover.json` returns an HDHomeRun-style
DeviceID and BaseURL, `/lineup_status.json` answers, and `/lineup.json` lists
**29 channels** (e.g. "PT (VF) Dazn 5"). **Playback is proven as far as the tuner
hand-off**: requesting a channel stream returned **302** to the upstream
provider; following it returned **401**, because real media bytes require the
provider's own client context (auth/headers) that a bare curl does not carry — so
decoded playback is *not* claimed. The **authenticated Plex API** works
(`/library/sections` 200 with a 3-section MediaContainer, `/status/sessions`
200), with the token supplied on stdin only. Chain liveness: sonarr 200, radarr
200, bazarr 200, tautulli 303, jackett 302.
Payload verification: **rpcbind UDP 111 verified** (portmap v2 NULL call answered
with matching xid, msgType=reply, acceptState=0, 24 bytes); **memberlist UDP 7946
verified as opaque/encrypted** (real node01→node03 gossip captured, ciphertext
after the UDP header, so framing is plaintext-UDP but contents are keyed).
**DHCP 67 lease exchange remains NOT verified**: a synthetic DISCOVER from node01
received no OFFER within 6 s even though `branconet-lan-dhcp.service` is active
and UDP 67 is listening — recorded rather than assumed, and needing its own
diagnosis (interface scope, relay requirement, or authoritativeness). Evidence:
`media-exercise/{media-exercise.json, media-and-payload-acceptance.json}`.
**The DHCP 67 no-OFFER was then diagnosed and the exchange is now verified.** The
server was never at fault: `branconet-lan-dhcp.service` (main PID 995,
`/system.slice/branconet-lan-dhcp.service`) runs
`dnsmasq --keep-in-foreground --conf-file=/etc/branconet-lan-dhcp.conf` with
`port=0`, `interface=enp3s0`, `bind-interfaces`, `dhcp-authoritative`, ranges
`192.168.0.200-245` and `192.168.0.247-250` (deliberately leaving `.246` free),
a 24 h lease, router `192.168.0.1` and DNS advertised as `192.168.0.253` then
`192.168.0.5`. My first probe sent **no DHCP broadcast flag**, so dnsmasq
unicast the offer to a random MAC that does not exist and the client socket never
saw it — and the server journal proves it answered even then
(`DHCPDISCOVER(enp3s0) 02:00:00:84:af:6f` → `DHCPOFFER(enp3s0) 192.168.0.230`
with matching transaction id 3384024176). Re-running with the broadcast flag set
produced a real exchange: the client received `OFFER` from `192.168.0.5` for
`192.168.0.236`, mask `255.255.255.0`, lease `86400 s`, and the server log shows
the matching `DHCPDISCOVER(enp3s0) 02:00:00:76:29:6d` →
`DHCPOFFER(enp3s0) 192.168.0.236 02:00:00:76:29:6d`. Scope is stated honestly:
DISCOVER/OFFER only — no REQUEST/ACK was sent, so no lease binding is claimed.
Evidence: `media-exercise/dhcp67-acceptance.json`.
Both owner decisions were then taken and acted on. **Vaultwarden 8096 is
restricted** (`vaultwarden` profile, forward hook: loopback, the three node IPs,
the operator host and the pod CIDR allowed; everything else rejected). Verified
after apply: the operator host gets HTTP 200 on `:8096` from all three node IPs,
a cluster node gets 200, an in-cluster pod gets 200, and the reject counter did
not move during any allowed probe. Sporadic external client sync was the original
reason for deferral and the owner accepted that trade-off explicitly.
Applying it exposed a **real gap the reboot had hidden**: nftables restrictions
are runtime-only and did **not** survive the node03 reboot — the post-apply
inventory read 9 tables on node01/node02 but only **1** on node03. Every profile
was re-applied and the inventory is now **9 identical tables on all three nodes**
(`core` 32158/32359/9090, `pihole-exporter` 9617, `ruckus-db` 3306, `ruckus-bot`
3003/8088, `mealie` 8089, `minecraft-website` 8083, `aplb` 8082,
`web-apps-local` 8080/8081, `vaultwarden` 8096). A second defect surfaced during
that repair: the `core` table on node01/node02 still carried the pre-refactor
owner comment, so the helper correctly refused with
`firewall_table_ownership_unknown`; those tables were deleted by exact name and
recreated under the current owner comment. **The restrictions are still not
boot-persistent** and need a persistence unit so a reboot cannot silently drop
them — recorded explicitly rather than left implied. The **attended
subscriber/reader receipt was explicitly deferred by the owner**, so it remains
open and no completion is claimed for it. Evidence:
`plaintext-inventory/{vaultwarden-verification.json, restore-all-profiles.json,
core-reapply.log, restored-inventory.json,
vaultwarden-and-persistence-acceptance.json}`.
**Boot persistence for the nine restriction tables is now implemented and proven.**
The gap recorded above (runtime-only tables lost on reboot) is closed by
`branconet-plaintext-restriction.service` — a `oneshot`,
`RemainAfterExit=yes`, `WantedBy=multi-user.target` unit installed by
`playbooks/plaintext-restriction-persist.yml` on all three nodes. Its runner
`/usr/local/libexec/branconet-plaintext-restriction-all`
(`scripts/migration/apply-all-plaintext-restrictions.py`) shells out to the
**existing helper once per profile**, so the helper's ownership and table checks
remain the only authority and no bypass was introduced. Install result:
`ok=9 changed=0` (node01, already current), `ok=9 changed=3` (node02, node03),
`failed=0` everywhere; the unit is `active`/`enabled` with `Result=success` and a
9-table inventory identical on all three nodes.
Proof across a real reboot on **node02**: boot ID `f6d82213…` → `e6b87bf0…`, and
all **nine tables returned with no manual re-apply**, unit `Result=success` under
a fresh invocation `e8583035…` — the exact scenario that previously dropped eight
tables on node03. Rule content after reboot is byte-identical between the
rebooted node02 and the untouched node01 (`vaultwarden` 8096 profile compared
directly), allowed sources still reach the restricted ports (HTTP 200 from all
three node IPs), and node02's monitor, sender, CSR controller and credential
timer all returned `active`/`enabled`. Cluster 3/3 nodes Ready, BORTUS running
the released `44a163a9` digest. Four of my own defects surfaced and are retained:
the play's assert tested a `from_json` dict for truthiness (now a computed length
comparison), two wrong `stat` attribute names before the correct `stat.pw_name`,
and — twice — a probe/assert that used a non-existent
`branconet_plaintext_restriction_core` table when `core` actually maps to the base
table name with no suffix. Evidence:
`plaintext-persistence/{node02-pre-reboot.json, node02-post-reboot.json,
persistence-acceptance.json, post-reboot-verification.json,
persistence-final-acceptance.json}`.
Phase C was then **re-recorded against the persistent mechanism**, superseding the
runtime-only framing of the earlier record: all nine profiles are documented with
their ports and hook type (`core` uses the `input` hook for host listeners
32158/32359/9090; the other eight use a `forward` hook at priority −10 for
published Service ports), together with the allowlist model (loopback, the three
node IPs, the operator host and the `10.244.0.0/16` pod CIDR, everything else
rejected), the enforcement evidence, and durability as part of acceptance rather
than an open caveat. Rollback is per profile plus disabling the persistence unit.
`plaintext-inventory/phase-c-persistent-acceptance.json`.

The media gate was then advanced from the tuner hand-off to real searches and real
media bytes. **Real indexer search works**: sonarr returned **186 live releases**
from 1337x, The Pirate Bay, eztv and nyaasi, and radarr returned **221** from
1337x, IP Torrents, YTS and thepiratebay, with all nine indexer validations
passing (`isValid: true`). **Authenticated Plex playback produced real media**:
fetching a library part with Plex's own token returned HTTP **206**,
`contentType video/x-matroska`, **4,194,304 bytes** starting with the EBML
signature `1a 45 df a3`; inspecting those bytes found the `matroska` DocType, a
**`V_MPEGH` HEVC video track**, an **`A_AAC` audio track** and the `Lavf58.41.100`
muxer string. The token came from the `plex-api-access` Secret and travelled on
stdin only.
The first search attempt returned **zero** results and that was diagnosed rather
than explained away: **jackett was not running** (`unavailableReplicas=1`, pod
`ContainerCreating` waiting for a Longhorn volume to detach), because the node02
reboot I performed had detached that volume; every sonarr/radarr indexer is a
Torznab entry pointing at `jackett:9117`, so all indexer tests returned HTTP 400
"Unable to connect to indexer". Once jackett started, all validations passed.
Three probe mistakes are retained: `strings` does not exist in the Plex image (so
the first codec probe found nothing; `grep -a` was used), Plex emits
`<Part id=… key="/library/parts/…">` rather than `Part key="…"`, and a grep loop
printed cosmetic stray `0` lines. Not claimed: decoded video frames or a live
player session, any download/grab/import run, or attended UI. Evidence:
`media-exercise/{indexer-search3.json, plex-playback.json,
plex-playback-tokens.json, media-gate-acceptance.json}`.
A **self-audit was then run after the owner reported the notification page returning
`{"code":40401,"http":404,"error":"page not found"}`**, and it found five issues, two
of them defects I had shipped or left half-delivered.
**D1 (open):** the ntfy web UI is disabled — `server.yml` sets `web-root: disable`,
so `/` correctly 404s. The attended-browser receipt path I described does not
exist; I published a URL without ever requesting it. Closing that gate needs
either the ntfy mobile app with the subscriber token, or a reviewed config change
enabling `web-root` (a private-chart + Flux rollout and restart).
**D2 (fixed):** the host monitor hardcoded `notificationDelivery` to
`"not-configured"` while its own database held six delivered events, so the
released UI label was wrong in production. A hash-guarded play
(`playbooks/certificate-monitor-delivery-state.yml`) updated only
`certificate_monitor.py` on node02 (`ok=9 changed=2 failed=0`), and the published
snapshot now reports `delivered` with `notificationsPending: 0`, consistent with
`outboxTotal 6 / delivered 6 / pending 0`.
**D3 (fixed in source, not yet in the deployed image):** my UI change made
`notificationDelivery` a **required** snapshot field, so any snapshot lacking it
was rejected wholesale and the screen would show `offline` rather than a wrong
label. The existing fixture tests caught this only now: the field is optional with
a `not-configured` default, unknown values are still refused, explicit coverage
was added, and **7/7 control tests and 13/13 across both suites pass**.
**D4 (recorded):** working-tree `tsc` fails because `api/certificates` passes a
string while the preserved, unshipped working-tree `k8s.ts` expects
`readonly string[]`. The released tree (`82580115`) carries the deployed string
signature and built successfully, so this is divergence with the in-progress
refactor, not a release defect — but I had reported a clean typecheck earlier and
did not re-run it after adapting the routes.
**D5 (false alarm):** I reported 12/12 Kustomizations healthy and a later sample
read 10/12; re-querying showed `migration-releases` and `plex-vip-controller` both
`Ready=True`/`Healthy=True`, so the earlier sample caught reconciliation.
Re-verified good: 3/3 nodes Ready with no pressure, BORTUS ready on
`sha256:44a163a9…`, 14/14 certificates healthy, zero CSRs, all monitor/sender/CSR/
watchdog units `active`/`enabled` on their own hosts. My earlier wording that
"every non-owner gate is closed" was too strong. Evidence:
`self-audit/self-audit.json`, `monitor-delivery-state/`.
The owner then chose **option 2 — enable the notification web UI** (D1). The private
config now serves the web app (`web-root: /`, `enable-login: true`) while
`enable-signup` stays `false` and `auth-default-access` stays `deny-all`, so the
app shell is public but **every topic read still requires a login** (verified:
anonymous `GET /bortus-certificates/json?poll=1` → **403**, authenticated → 200).
Because `/` previously returned `{"code":40401,...,"error":"page not found"}`,
`/auth` is an `emptyDir` and users are provisioned from `NTFY_AUTH_USERS`, the
`bortus-subscriber` password hash was replaced **in the native Secret** (a CLI
change would vanish on restart), preserving both publisher identities and all
three tokens. The private gate moved with the change: the normalized-config byte
pin became `914d375c…`, with the reviewed delta documented and the two changed
keys asserted individually; **44 tests + validator passed**, published as
`f5f9af8…` and applied by Flux.
**Incident, recorded rather than hidden:** my first Secret write used
`name:hash` without the required `:role`, so ntfy **crash-looped for about six
minutes**; the rollout watcher caught `CrashLoopBackOff` and the log read
`invalid auth-users ... expected format: 'name:hash:role'`. The root cause of my
error was reading the old 65-character field as hash-only when it was a 60-char
bcrypt hash plus `:user`. Rewriting the entry and restarting returned the pod to
`Running 1/1`; the monitor outbox was empty (`pending 0`) so no event was lost,
and delivery still reads `delivered` with `lastRun: complete`. A human-visible
test message ("Attended receipt test") was published to `bortus-certificates`
(HTTP 200) and confirmed readable through the subscriber credentials, so the
attended receipt is now waiting only on the owner's confirmation.
Evidence: `ntfy-web-ui/{web-ui-acceptance.json, push-result.json,
users-before.b64, unit-tests2.log, validation2/}`.




With this, every non-owner gate in the plan is closed. Both owner decisions were
subsequently taken: the **vaultwarden 8096 restriction was approved and applied**,
and the **attended subscriber/reader receipt was explicitly deferred**, so it
remains open and unverified. The only outstanding plan item is therefore that
deferred attended receipt; no completion claim is made for it.






























The earlier bounded-listener qualification CSR was deleted with
UID/resourceVersion guards and its key/certificate removed. Two failures are
retained honestly: an approve invocation whose nonzero exit was reconciled from
durable state without re-approving, and an initial write of the base64-encoded
certificate without decoding. Approval remains disabled for the service.

The observation controller is now installed as a managed host service on node02
with approval still disabled. Preflight changed nothing; installation added
nine root-managed sources, public enrollment/identity/config/CA and three
inactive units (`ok15/changed8`). Only the controller's own one-hour credential
timer was enabled: 4 allowed and 23 denied effective checks, token `root:997/0640`,
consumer read-but-not-write, root bootstrap/lock unreadable, code/profile not
writable. The service runs as UID997 with no capabilities and `NoNewPrivs=1`
under 128 MiB/no swap/5% CPU/32 tasks. Persistence was proven with a genuine
pending node02 CSR observed by the managed service, then an actual restart:
same SQLite inode, identical durable row, zero approvals, fixture retired and
zero cluster CSRs afterwards. Preserved node02 monitor/sender/timer and the
monitor DB inode remained intact. Approval enablement still requires a real
renewal window; node reboot, attended receipt, UI release, retirement review
and plaintext/mesh remain open.
`kubelet-csr-observation/acceptance.json` binds this increment; root index and
unrelated work preserved. Remaining gates unchanged, plus UI label/release,
attended receipt, node reboot, retirement review, plaintext/mesh.
