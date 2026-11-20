# Cluster TLS trust and renewal

Scope (operator decision, 2026-11-15): free/self-hosted only, keep current
service names, secure this single three-node cluster. No trust root was
replaced. Status verified 2026-11-16.

## Trust inventory

### BORTUS Certificates & Trust — implementation in progress

The working source now includes `/certificates` and authenticated read-only
`GET /api/certificates`. It reads cert-manager Certificate metadata and Kubernetes
CSR metadata without fetching TLS Secrets. Missing permissions, malformed or
incomplete responses are coverage gaps, never a healthy empty result. CSR
approval, issuance and installed/served verification are distinct.

This working-source increment does not deploy scheduled monitoring, approval, renewal or
retirement. Host kubeadm/kubelet checks, mesh CA observations, consumer mapping
and endpoint verification remain explicitly unavailable in the UI. No production
deployment of this feature is claimed. The follow-up scope and gates are saved
in `MIGRATION-PLAN.md`.

The metadata-only monitoring foundation is
`scripts/migration/run-certificate-monitor.py --once --state-dir <private H dir>`.
It requires an explicitly supplied scoped `KUBECONFIG`, serializes execution
with an exclusive lock, persists observations and run states in its own SQLite
database, retains but marks unavailable source data after API failure, and
deduplicates a durable notification outbox. Records contain selected metadata,
not raw CSR/certificate/Secret payloads or backend errors. A snapshot older than
15 minutes is stale. The runner can now consume policy and publish durable
observations through the fixed `bortus/bortus-certificate-policy` and
`bortus/bortus-certificate-observations` ConfigMaps using `--control-plane`.
`--loop --control-plane` publishes a heartbeat every 60 seconds while respecting
the operator's paused/monitor mode, 60–900 second scan interval and 1–30 day
cert-manager expiry-warning setting. It installs no service. Both ConfigMaps
must exist; there is no silent default, auto-creation or administrator fallback.
Policy changes during a scan and stale observation-resource versions refuse
publication. Notification delivery, service installation and host checks remain
unconfigured. Admit its H output before a local on-disk runner launch.

#### Independent host profile — candidate, not installed

Read-only host preflight found Python 3.10.12, systemd 249 and kubectl on all
three nodes, with no existing certificate-monitor service. Node02 is the
proposed always-on placement (about 12 GB available RAM and 90 GB free under
`/var/lib` at observation), not a claimed deployed service.

The runner's default local profile still confines state and an optional
synthetic `--kubectl` executable to the existing H store. `--managed-host`
requires the exact root-owned code installation under
`/usr/local/libexec/bortus-certificate-monitor`, an unprivileged user, fixed
private `/var/lib/bortus-certificate-monitor` state, root-managed CA-verified
VIP-only JSON kubeconfig, externally refreshed private token file and fixed
`/usr/local/bin/kubectl`. No exec plugin, insecure TLS, alternate identity,
ambient admin kubeconfig or credential minting is permitted by that profile.

`playbooks/files/bortus-certificate-monitor.service` is an inactive candidate:
unprivileged user, read-only system/home protection, no capabilities, cluster
API VIP-only network access, 256 MiB/no swap, 10% CPU, 64 tasks and a 20 MiB
individual-file ceiling. It has no Secret/approval/host-maintenance grant.
Termination wakes the runner's interval wait; owned CLI calls remain bounded.
Duplicate owners return a fixed `already-running` outcome; existing public or
symlinked lock/database state is refused. This is source preparation, not live
service/resource/RBAC/credential-rotation acceptance. Ansible installation,
short-lived scoped-credential refresh, service restart and notification delivery
remain required; nothing was staged or started on a node.

`playbooks/certificate-monitor-host.yml` is the initial Ansible candidate.
It defaults to read-only preflight on the stable `workernode1` alias, asserting
node02 identity. Explicit `stage` refuses all existing code/unit/config/state
targets, then installs the root-owned modules and inactive units without
token values, enabling or starting them. Explicit staging now also verifies
the actual hostname, fresh account/group, pinned kubectl and existing public CA
hash, then installs only public UID/audience/hash enrollment, public CA and the
fixed kubeconfig's runtime token-file reference. It deliberately has no activate action;
upgrades over existing installations require a separate reviewed path.

SQLite now enforces a 16 MiB main-database page limit, retaining the latest
1,000 run records and 1,000 delivered outbox records after a scan. Undelivered
notifications are never discarded to make space. If pending data consumes the
limit, the scan/publication fails visibly rather than manufacturing a healthy
heartbeat; notification delivery and independent missed-heartbeat detection
are still required before unattended operation. A rollback journal can add up
to a further database-sized temporary file; the unit's 20 MiB file limit is an
individual-file guard, not a claimed total filesystem quota.

The focused runtime suite (`tests/test_certificate_monitor_runtime.py`) uses an
explicit `BORTUS_MONITOR_TEST_ROOT` inside the admitted H stage. It exercises the
actual CLI entrypoint and bounded fake CLI subprocesses, persisted SQLite,
exclusive loop ownership, signal shutdown, path/profile refusal and sanitized
control failure. This is not a substitute for authenticating a real scoped
identity against live RBAC, installing a service or proving host availability.
After the growth/history changes, all 18 monitor/control/runtime tests passed.
Ansible syntax and local systemd unit verification passed (the latter emitted
an unrelated pre-existing Ingenium unit-symlink permission warning). Node02's
Python 3.10 parsed all five modules from stdin only. Minimal source-bound
results/logs remain under the existing qualification stage; synthetic payloads
and two empty temp directories are gone. Actual scoped authentication, token
refresh, installed service restart/resources and notification delivery remain
unqualified. See the latest execution section of `MIGRATION-PLAN.md`.
The candidate's actual Ansible preflight then passed on node02 with become off:
three OK tasks, zero changes/failures/unreachable hosts; nine staging tasks
skipped. A preceding long-H-path local RPC startup failure is preserved. The
repository's existing abstract Unix-address compatibility pattern corrected
that controller-only problem; no stage/install/reload/credential task ran.

#### External short-lived credential refresh — implementation in progress

Initial read-only discovery confirmed the API issuer is
`https://kubernetes.default.svc.cluster.local` and that the dedicated monitor
ServiceAccount was absent. The separate identity-only private-Flux bootstrap
has now reconciled; the UI/control profile and both control ConfigMaps remain
inactive/absent.

`certificate_monitor_credentials.py` prepares the refresh contract: a one-hour
TokenRequest for that fixed audience/account, pinned ServiceAccount UID before
and after checks, bounded token/expiry/claim validation, API-authenticated
SelfSubjectReview, representative effective allow/deny reviews and actual
metadata reads before publication. Local JWT parsing is not signature proof;
the authenticated API must independently accept the token and identity.
Known unsafe identity/permission quarantines the active owned runtime token;
transient errors do not replace a still-valid token. Values never enter result
objects, Git, SQLite, arguments or logs. External root adapter, refresh timer
and tests were initially in progress. Subsequent live qualification below does
not imply installing or activating either host service.

The external adapter candidate is
`refresh-certificate-monitor-credential.py`, executable only from the exact
root-managed installation as root. It uses a pinned existing kubectl and fixed
local `/etc/kubernetes/admin.conf` solely for the fixed ServiceAccount
metadata/TokenRequest. Candidate tokens remain in root-private `/run` scratch
files while actual authenticated identity, allow/deny reviews and metadata
reads run. Only a qualified token is atomically published group-readable to
the monitor; failed candidate files are removed. Known scope/UID violations
remove the owned active token file, stopping future reads; this is not a claim
of revoking an already-issued token at the API server.

Separate inactive root oneshot/timer candidates request one-hour credentials
every twenty minutes, using pinned UID/audience/kubectl-hash enrollment metadata.
They neither create RBAC nor activate/start the monitor. The root bootstrap
credential is never available to the unprivileged monitor. No bootstrap token,
installation, enrollment, timer or monitor activation has run.
The initial-stage candidate now includes seven modules and the three inactive
monitor/credential-service/timer definitions; it refuses existing targets and
still provisions no credentials or enabled service. Post-replacement I/O
failures explicitly report whether a candidate was already atomically replaced;
they never claim a known non-publication when the outcome is uncertain.
Focused credential tests use only synthetic tokens and H-local scratch. They
cover refresh gating, required/forbidden permissions, ServiceAccount recreation,
issuer/audience/subject/expiry failures, transient review failures, complete
atomic token replacement and rejected-candidate cleanup. These tests do not
qualify actual issued Kubernetes credentials or effective live permissions.
Operator qualification may reuse the same candidate-file and refresh logic in
a fresh private H directory with the existing operator kubeconfig and public
CA; this is not permission to invoke the fixed root adapter from WSL or create
host paths. Only the operator diagnostic supplies an alternate public-CA file;
the installed root adapter has no path override and remains fixed.
The monitor-only identity bootstrap was published through normal private CI
and Flux, separately from UI/control activation. The first real-token attempt
passed authenticated identity and all permission reviews, then correctly
refused publication when the diagnostic expected typed kinds from kubectl's
generic `get` formatter (`kind: List`). Candidate files were removed and failure
retained. The broker now probes the exact raw API endpoints, retaining typed
list identity; a distinct new token qualification is required for this fix.
The bounded `ApiQualification` adapter is shared by the installed broker and
the operator proof, so the new live attempt exercises the corrected production
request construction rather than a second independent diagnostic implementation.

Credential/RBAC qualification now passed on private charts
`7e1c6c9eab42ead78f77c374a5a1cc555196bfd3`: normal exact-source CI passed all
35 tests and the full chart validator, then promoted validated and Flux applied
the identity child. The current ServiceAccount UID is
`687ff70b-39a4-4555-9b17-cb02d83b4ec6`, with automount disabled.
An actual one-hour token passed API-authenticated identity, **7 allowed and 19
denied** SelfSubjectAccessReviews, then typed metadata reads (14 Certificates,
0 CSRs). A further deliberate two-cycle refresh proof rechecked all 26
permissions on each cycle and atomically replaced the existing credential:
held old readers retained the old complete file; new readers got a different
complete token. Values were never printed or stored in Git/SQLite. All candidate
and active diagnostic token/CA files were removed; this is not server revocation.
The initial formatter failure remains retained, not erased by the passing runs.

Eight credential tests pass, including UID recreation, broadened/missing
permissions, issuer/audience/subject/expiry rejection, transient failure and
atomic replacement/cleanup. Both new modules parse on node02 Python 3.10.
At that checkpoint the monitor, root credential service and timer were
absent/inactive on node02. Those results qualify shared refresh logic and real scoped API access,
not installed root service/cgroup/periodic timer/reboot acceptance. Those and
notification delivery remain required before unattended activation.

Node02 staging/credential-service qualification is now authorized by the user's
next-step request; the monitor must remain disabled/stopped. The broker unit
routes HOME/cache under its owned `/run` directory because ProtectHome blocks
root's ordinary kubectl cache. It adds CPU/memory/task/IP accounting and a
2 MiB per-file guard for runtime scratch; existing 256 MiB/no-swap, 10%-CPU,
64-task and VIP-only restrictions remain. These are definitions until actual
kernel/runtime observations establish enforcement.
Staging completed on node02 with no failed/unreachable tasks; it created the
fresh account/group, seven root-owned modules, public CA/enrollment/config,
private state directory and three inactive unit definitions. It created no
token and started/enabled nothing. The monitor remains disabled/inactive.

`qualify-node02-credential-service.py` owns fixed `once`, `timer` and read-only
`observe` phases. It checks installed file hashes/ownership and monitor-off
state, captures live cgroup/process limits for the actual broker, and can arm
only the credential timer. The observer follows the owned journal through the
real twenty-minute due time without resetting the timer or starting the monitor.
Started/result receipts prohibit blind replay after interruption. Actual
service/periodic acceptance is still pending, not inferred from this driver.
The first actual broker start exited successfully, but the initial process
sampling gate failed before accepting its resource proof. The driver now
retains first/last process and kernel metadata, separates systemd's pre-exec
executor from the Python broker and provides a read-only inspect phase.
Named correction receipts preserve the failed observation rather than replaying
or overwriting it. No runtime security property or resource cap was weakened.
Read-only reconciliation confirmed exit 0 and a root-owned 0640 runtime token;
the timer and monitor were disabled/inactive. The first inspector missed the
success message because journalctl's JSON default substitutes null for fields
over 4096 bytes. The collector now uses `--all` for the metadata-only result
and journal follower. Both failed collector receipts remain; neither is a
broker failure or permission to skip actual kernel/process qualification.

The corrected inspector recovered the original successful invocation. The
separately named execution then passed 323 real cgroup samples: 256 MiB memory,
zero swap, 64 tasks, 10% CPU; observed memory stayed at or below 70,258,688 bytes
and tasks at or below five, with no OOM events. The actual Python broker had
NoNewPrivs=1 and only CHOWN/FOWNER effective/bounding capabilities. The retained
first sample identifies systemd's unrestricted pre-exec executor, not the final
broker. This qualifies the actual observed limits, not destructive stress tests.

Node02 UID998 can read the runtime token/public config but not the admin
bootstrap or root lock, and cannot modify code/enrollment/token. Public CA
hash and fixed config validation passed. Only the credential timer has been
enabled; its initial invocation and actual periodic refresh passed. The bounded
read-only observer completed after a new invocation 1,200.109143 seconds later,
at/after the recorded due time, with 7 allow/19 deny checks, 14 Certificate/
0 CSR reads, and replacement of the root:998/0640 token. Its expiry advanced to
2026-11-16T17:34:14Z. `node02-credential-installed-acceptance.json` binds the
execution/resource, boundary, timer and periodic receipts. No timer reset or
manual start was used to produce the periodic result; the observer has exited.
The monitor is still disabled/inactive; do not restart the timer or replay
completed staging/execution after interruption. See the current migration-plan
section and its exact receipts.
Installed monitor-service/restart/persistence, node-reboot survival and
notification delivery remain separate unaccepted gates.

#### Notification delivery preparation — inactive, no destination configured

No existing ntfy/Gotify/SMTP destination was found in the repository's current
operational configuration. The selected preparation path is **self-hosted ntfy**
using its documented POST/topic acknowledgement contract, not the public
ntfy.sh relay. No server, client subscription, publisher credential or live
message has been created. Server configuration must deny anonymous access,
restrict publisher/subscriber identities, retain bounded messages and disable
external push/upstream forwarding unless separately approved.

`certificate_monitor_notifications.py` prepares a separate dispatcher so the
monitor retains API-VIP-only networking. An explicit configuration pins an
HTTPS hostname/topic, RFC1918/loopback address, trusted CA file and private
publisher-token file. There is no default origin, DNS-based routing, proxy,
redirect, attachment or dynamic callback. TLS verifies the URL hostname while
connecting only to the pinned private address. Responses are bounded and must
acknowledge the matching topic/message. A whole-process deadline is required
around each transport call in addition to socket timeouts.

The dispatcher opens existing monitor state, never constructs a monitor or
marks its running scan interrupted. Its separate lock must serialize senders.
Only a confirmed server acknowledgement marks an outbox row delivered. Failures
and uncertain crash outcomes retain pending alerts with a durable 60-second to
one-hour retry backoff; retries reuse the stable event ID. This is
**at-least-once**, not exactly-once: an accepted send followed by a local crash
can duplicate a notification. At most three events are attempted per batch;
HTTP runs outside SQLite write transactions. Server acceptance never proves
receipt by an absent operator. Real self-hosted destination, subscription,
missed-run/worker-outage alerting and attended receipt remain future acceptance.

`deliver-certificate-notifications.py` prepares the independent executable.
Local state/config/credential/CA paths must remain under H; managed-host mode
requires an exact unprivileged root-managed installation and fixed files.
It refuses missing state rather than creating a new monitor DB. Its private
notification lock serializes dispatchers separately from the monitor lock.
Each send runs in an isolated bounded child (10-second wall deadline,
1 KiB stdout/stderr); credential bytes enter neither argv nor stdout. Invalid
configuration and backend failures emit fixed codes only. The inactive
`bortus-certificate-notifications.service` candidate has no capabilities or
Kubernetes credentials, 128 MiB/no swap/5% CPU/32 tasks and deny-all networking.
It cannot send until a reviewed exact-destination address drop-in is supplied.
It is not installed and is not added to the initial staging play.

#### Monitor-service qualification preparation — no activation action

The existing qualification driver now has a read-only `monitor-preflight`
phase. It verifies installed modules/units against the preserved staging
checkpoint, confirms the monitor is disabled/inactive, and records private
state/database presence plus token metadata without reading token values.
Proposed local source differences are reported separately, never installed
or mistaken for the running checkpoint. This phase cannot start, stop, enable
or restart a monitor, alter policy, or provision control ConfigMaps.

The monitor unit source now proposes a separate private volatile runtime cache
and fixed HOME/XDG paths, because ProtectHome and a read-only root would prevent
ordinary kubectl discovery-cache writes. It also unsets proxies and requests
CPU/memory/task accounting. This is an **uninstalled unit revision**; the
running credential broker/timer and their accepted hashes remain untouched.
Do not replay initial staging to update it.

After explicit activation authority and a reviewed upgrade, qualification must:
1. Preserve/pin installed hashes, private DB/lock ownership and the exact
   identity-only Flux revision; provision only the paused control bootstrap
   through private validation/Flux, without broadening the reader identity.
2. Start disabled/not-enabled in paused mode first, sample the real unprivileged
   cgroup/security/cache behavior, and observe the exact policy UID/revision
   acknowledgement without a scan or certificate mutation.
3. Explicitly enable monitor policy, bind run/observation/outbox IDs to its
   acknowledgement, then stop/start the service and compare the same durable
   DB/inodes/run IDs. A recent completed scan must not replay; an interrupted
   read-only scan must retry, not pretend it completed.
4. Test API/credential/notification outages with bounded isolated controls,
   preserve pending alerts, validate recovery, and prove effective denials and
   resource ceilings without touching unrelated workloads.
5. Verify real private ntfy acceptance **and actual subscriber receipt**, then
   independently detect missed monitoring and loss of node02 from another
   always-on location. A co-hosted dispatcher cannot detect its own host dying.
6. Review the result before enabling persistent monitor startup. Node reboot
   testing requires its own authorized serial maintenance/recovery path.

Current control resources remain absent, no runtime monitor DB has been
claimed, and no monitor or notification service activation is performed by
this preparation. UI delivery remains explicitly unconfigured.

Focused notification qualification uses H-only synthetic SQLite/credentials
and an actual private loopback TLS receiver (not an installed ntfy server).
It checks durable retries and uncertain outcomes, no interference with active
monitor runs, actual trusted HTTPS, failed trust/hostname, no redirects,
authentication/error/mismatched/oversize acknowledgements, and real separate
CLI restarts plus sender-lock exclusion. These checks do not establish a live
destination, external availability, server-side ACLs or attended client receipt.
All eight checks passed. The read-only node02 preflight also passed: installed
checkpoint intact, monitor disabled/inactive, private UID998 state with no DB,
and both control ConfigMaps absent. Both notification modules parse on target
Python 3.10. Local unit verification returned 0 with the already-recorded
Ingenium symlink and controller CPUAccounting-version warnings; no target unit
was installed/reloaded. Source-bound results are in
`monitor-notification-preparation-result.json`. The test receiver is closed,
synthetic keys/tokens/DBs removed and the exact empty test root retired.

#### Private ntfy and off-host detector — inactive preparation

Private charts now prepare unreferenced `flux/private-ntfy` and
`flux/certificate-watchdog` candidates. ntfy additionally has zero replicas.
Upstream v2.38.1 image index/amd64 digests were read from registry metadata,
without pulling/scanning/running an image. The proposed node01 ntfy server is
independent of node02; node03 is the proposed independent watchdog host.
Node03 read-only preflight found about 12.9 GB available RAM and 17.7 GB free
under `/var/lib`, with no watchdog service. No install or activation occurred.

ntfy proposes private-CA `notifications.lan` (new proposed name, no DNS change),
HTTPS only with Traefik TCP SNI passthrough, no external egress/push/relay,
one retained cache claim, bounded cache/auth SQLite pages and ordinary users
with fixed topic permissions. Publisher/subscriber material must come from an
external native Secret, never Git. `ntfy_acl_contract.py` validates its exact
three-user/two-topic syntax without generating, printing or provisioning
credentials. Live TLS, storage/restart, effective ACLs and client receipt are
still unrun; syntactic validation is not authentication evidence.

The separate watchdog identity candidate can only get the exact observations
ConfigMap and node02 Lease; it cannot list, mutate, read Secrets or mint tokens.
`certificate_watchdog.py` checks enrolled ConfigMap/policy/Lease UIDs, fresh
policy heartbeat (180s), and node02 lease renewal (90s), allowing at most five
seconds of future-clock skew. Paused monitoring must still heartbeat.
Malformed/missing/unauthorized API responses are **coverage unavailable**, not
a fabricated worker-failure diagnosis. It keeps its own finite SQLite state
and durable deduplicated transition/recovery outbox. Unknown coverage never
silently resolves a prior incident; pending events survive restarts and
delivered history is bounded. This does not touch node02's database or service.
The existing sender now accepts fixed `recovered` events too.

`run-certificate-watchdog.py` prepares an explicitly armed node03-only host
profile with root-managed code/config, pinned observation/policy/Lease UIDs,
fixed CA-verified API VIP and a separate external short-lived token. Local
fixtures remain H-only. It reads only the two fixed raw API endpoints, with
bounded subprocesses, no administrator fallback, a private exclusive lock and
its own 16-MiB-page-capped DB. It does not instantiate the monitor or read its
DB. No account/config/token or unit is installed. Arming is an external reviewed
enrollment step after actual resources/UIDs exist, never an automatic first-read
trust decision.

The sender's new explicit `--watchdog` profile consumes only that independent
state and its own ntfy publisher credential. The detector candidate is API-only;
its separate notification unit defaults to deny-all until a reviewed exact
destination drop-in. Neither can read Kubernetes bootstrap credentials; the
sender also hides its runtime API credential. Proposed node03 host checks,
separate credential rotation/effective read-only RBAC, service resource/restart
qualification and actual off-host alert receipt remain unrun. Loss of node03
or the entire cluster is outside this single-witness availability guarantee.

New focused tests exercise stale/future/paused observations, missing/recreated
UIDs, unknown-vs-worker-failure semantics, deduplication/recovery and actual
separate watchdog processes with H-only fake API responses. They also check
unarmed no-network/no-state behavior, independent sender state, TLS recovery
messages, and rejection/redaction of overprivileged or duplicate ntfy material.
No live resource, service, credential or subscriber is used by these tests.
Pinned upstream v2.38.1 `user/util.go` additionally establishes the token
contract `tk_` plus 29 URL-safe characters. The provisioning validator/fixtures
were corrected from a longer documentation-example assumption before delivery;
the focused ACL checks must bind this corrected version-specific contract.
Preparation checks passed: 15 watchdog/notification tests, the two affected ACL
tests after that correction, four private candidate tests and the full unchanged
private chart validator/credential scan. Nine ntfy and five watchdog objects
rendered; neither candidate is referenced by active release composition.
Both watchdog units pass local definition checks. Node03 parsed candidate code
without installing it; node02 remains disabled/inactive, credential timer
untouched. Source-bound `ntfy-watchdog-preparation-result.json` records details
and limitations. No actual ntfy process, live ACL/credential, new certificate,
DNS record, host unit or off-host alert/subscriber acceptance is established.
Six empty test/validator directories were removed (24,576 allocated bytes),
with reports/logs preserved. See the current migration-plan section.

#### Actual pinned ntfy fixture — TLS/ACLs qualified in isolation

The next authorized step uses `qualify-private-ntfy.py` to run only the pinned
linux/amd64 child of the prepared image in a local isolated fixture. It reuses
the H-backed daemon/containerd and retained bcryptjs solely to generate
synthetic hashes. One exclusive attempt reserves 1 GB inside the existing
combined 4 GB stage, including image/runtime peak; it is not new global
admission. Registry metadata binds index, amd64 manifest and image config;
production credentials are never mounted or generated.

The real source server.yml is mounted unchanged with private synthetic TLS/
users/tokens, nonroot/read-only/no-capabilities/resource limits and a private
internal network published only on host loopback. Synthetic credentials stay
in H-private environment/stdin files, not argv or evidence. The fixture will
exercise actual publisher/subscriber/anonymous/cross-topic allow/deny behavior,
CA/hostname verification, plaintext rejection and cache survival across a
fresh-auth-store restart. Any result is machine subscriber evidence, not
attended phone/operator receipt, production routing or an image security scan.
Container/network cleanup is part of the driver; synthetic payload and an
exclusively acquired image require separate exact retirement review afterward.
No production server, monitor, notifier or watchdog may be activated by it.
The first isolated attempt acquired the pinned image but stopped before server
startup because this daemon's containerd image store exposes the manifest digest
as image ID, not its config digest. The original failure remains. The corrected
driver verifies raw index/manifest SHA-256 bytes, amd64 membership and exact
config digest plus the daemon descriptor, then reuses the existing immutable
image reference without another pull. No identity boundary is relaxed.
The next attempt passed image binding and started the server, but stopped
before TLS/ACL tests on an absent host-port mapping. A separate credential-free
probe confirms this daemon leaves internal-network host bindings null. The
fixture now uses a loopback-only byte forwarder into its owned internal bridge;
there is no Docker published port, TLS termination, external route or change
to production networking. Both earlier attempts remain distinct and preserved.

The third distinct `loopback-proxy` attempt passed with the actual pinned
server and unchanged candidate server.yml. Raw registry SHA-256 bytes bind the
index, amd64 manifest and config; reported server version is 2.38.1. Two real
publishers sent metadata messages to their respective topics, and a real
authenticated Bearer-token poll subscriber received each exact message once.
All **26 forbidden operations** failed (20 HTTP403, six HTTP401): publisher
reads, cross-topic/unrelated access, subscriber writes, anonymous operations
and invalid tokens. Denied writes did not appear in either topic.

Trusted hostname TLS at 1.2-or-newer succeeded; system-default untrusted CA,
wrong hostname and plaintext access were rejected. After a stopped/recreated
isolated server with a fresh synthetic auth store, the same persistent cached
message IDs were readable with the same intended subscriber. This is
**machine subscriber receipt**, not attended phone/browser/operator receipt.
It does not qualify production CA/Traefik/DNS, NetworkPolicy, kernel-resource/
volume enforcement, image vulnerabilities or full outage availability.

All fixture containers, internal networks and loopback forwarders are closed.
Fourteen admitted synthetic config/key/token/auth/cache payload targets from
the interrupted/passing attempts were removed (643,072 allocated bytes);
source-bound metadata and sanitized logs remain. One exact immutable image
remains on the existing H daemon for the outstanding image-security scan;
its reported 36,988,086 content bytes are not physical/unpacked allocation.
The conservative 1 GB runtime reserve remains charged inside the 4 GB stage.
Retire that exact reference after its security/local consumers finish; no
blanket prune or second image/dependency copy is authorized.

`ntfy-server-isolated-acceptance.json` binds the results and cleanup. Node02
monitor remains disabled/inactive; node03 watchdog units remain absent; the
production ntfy namespace is absent. No private publication, native auth/TLS
material, DNS change or production activation occurred.

#### Image-security continuation — not yet accepted

The verified existing worker scanner is Trivy0.76.1, SHA-256
`d1dfca6ae10a1ad4540bb94e64f0510077c47008920a9b554986b39dca573d83`.
Its retained October advisory snapshot is stale and remains immutable.
Fresh database admission exceeds the current 4 GB stage with its preserved
1 GB image/runtime reserve; no database was downloaded or old snapshot changed.
`qualify-private-ntfy-secrets.py` prepares the independent database-free secret
check. It exports but never executes/pulls the exact retained image, verifies
manifest/config/layer bytes, uses explicit empty config/ignore files and built-in
secret rules, and constrains the scanner to 1 GiB/no swap/two CPUs/64 tasks.
Its Results-only template further excludes secret match/source-code fields.
Zero secret findings, if obtained, would not establish vulnerability acceptance.
The secret-only execution subsequently completed: zero findings, OS/Go-binary
targets inventoried, 105 built-in rules logged and three kernel-limit samples.
The synthetic report projection preserved finding metadata but omitted image
Env, secret Match and Code. The scan used no advisory DB. Logs reveal anonymous
Trivy telemetry despite skip-version-check; this is recorded, not described as
network-isolated. The driver now explicitly adds `--disable-telemetry` for any
future authorized invocation; the completed passing scan is not rerun. Its
execution-source hash remains historical and distinct from that correction.

James explicitly approved 4.25 GB for the existing qualification stage only.
`qualify-private-ntfy-vulnerabilities.py` separates exclusive DB and scan phases.
The DB phase streams the pinned public layer without a saved compressed carrier,
checks every tar member/byte and the complete compressed digest, fsyncs/hashes
the DB/metadata, checks Version2/UpdatedAt/NextUpdate, then atomically publishes
the verified directory. The stale snapshot is untouched. The scan reuses the
already verified image export, approved Results-only template and exact scanner,
with all packages/severities/statuses and no VEX/ignore/unfixed suppression.
Telemetry is explicitly disabled. No passed secret/TLS/ACL check is repeated.
The full existing 1 GB reserve remains: 500 MB conservative retained-image/
metadata allowance plus up to 500 MB extra scan workspace. Workspace already
measured in stage usage is not charged a second time. The scanner retains its
1 GiB/no-swap/two-CPU/64-task limits; actual results remain pending.
The initial foreground download exceeded its tool's 120-second timeout before
publishing a terminal integrity receipt. Both expected-size pending files remain;
they are not accepted just because sizes match. The separate exclusive
`verify-database` recovery compares those same files byte-for-byte with a full
stream of the pinned original layer, hashes all compressed bytes and members,
checks unchanged inode/size/mtime and freshness, then publishes the same
directory. It writes no second DB or compressed carrier. The initial timeout
receipt remains. No vulnerability scan is authorized by an incomplete download.

The separate recovery then passed complete compressed-layer hashing and
byte-for-byte comparison of both original pending files, publishing the SAME
verified directory with current metadata and no second DB writes.
The subsequent unfiltered vulnerability scan completed:17 Alpine/86 Go
packages, **one MEDIUM zlib finding (CVE-2026-4738,1.3.2-r1 →1.4-r0)**,
zero HIGH/CRITICAL scanner findings and zero Go findings. The previous secret
scan remains zero. Scanner exit0 is not a clean-security result.

The primary CNA describes GDAL's infback9 code with Critical9.4 severity, while
Alpine maps the package fix and the scanner reports Medium. The exact archive
contains zlib but no GDAL/infback9-named files; ntfy is statically linked. This
does not independently prove all vulnerable code absent. **Candidate HOLD**:
no risk acceptance, suppression, false-positive waiver or production approval.
Prepare/qualify a vendor-fixed candidate rather than hide the finding.

The vulnerability log confirms telemetry disabled. Actual kernel limits matched
1 GiB/no swap/two CPUs/64 tasks; source/index/DB hashes stayed unchanged.
After the completed assessment, exact fresh DB/cache/temp/export targets were
retired (1,811,103,744 allocated file bytes) and only the task-owned local ntfy
image reference removed normally. Physical image reclamation is not measured.
Full reports, advisory/ELF review and provenance remain; no production or old
immutable input changed. See latest `MIGRATION-PLAN.md` and
`ntfy-security-vuln/security-assessment.json`. The old image/export/DB are no
longer retained inputs; do not replay their completed checks.

#### Vendor-fixed ntfy candidate — local preparation

James next authorized a vendor-fixed candidate, without activation. The latest
upstream release still has the held digest. `images/private-ntfy-zlib/` pins
the original amd64 image and Alpine3.24 signed zlib1.4-r0 package (SHA-256
7b05bc77…); no ntfy rebuild or broad package upgrade. The Dockerfile documents
the offline install recipe with a nonroot default.
The existing shared BuildKit driver lacks per-build CPU/memory controls, so
`prepare-fixed-ntfy.py` uses the equivalent exact task-owned offline APK install
container (two CPUs/1GiB/no swap/64 tasks), verifies vendor signatures using
the base's trusted keys, checks the ntfy executable is unchanged and commits
only the resulting local candidate. It then verifies every exported blob.
No new builder/tool/dependency tree, production mount, credential, pin change
or publication is authorized by preparation. The changed image needs new
security and runtime qualification; old-digest results are not replayed as proof.
The existing real-server fixture now accepts only the exact owned fixed build
record as an explicit alternate subject. It cannot pull a missing local candidate
or reinterpret a mutable tag as proof. It binds that record and local exported
manifest/config, requires the configured nonroot default, then runs without a
user override so the default itself is exercised. The unchanged TLS/ACL/cache
contract is rechecked only because this is a changed image, not a replay of the
held digest. No candidate pin is published or applied.
The first offline package install passed vendor verification and upgraded zlib,
but its collector wrongly expected a version from human-oriented `apk info -v`.
A bounded read-only probe confirmed it prints description/URL/size. No candidate
was committed; the initial logs and failed receipt remain, and the discarded
writable layer is recorded as reproducible state. The separate `apk-db-check`
attempt uses direct installed-database comparison, permits only zlib's version
to change, and supplies `/dev/null` repositories to prevent lookup attempts.
Vendor signature checks and all resource/production boundaries remain unchanged.
The existing security driver has an explicit owned candidate-record mode:
it uses the new verified export and a separate exclusive security directory/
unit, never the retired old image. A combined unfiltered vulnerability/secret
scan must inventory fixed zlib1.4-r0 and preserve all package/finding fields.
Its template omits image Env and secret Match/Code; a synthetic real-template
conversion verifies those omissions without suppressing finding metadata.
The still-fresh pinned public DB may be reconstructed for this NEW subject
under the existing4.25GB stage, with complete layer/member checks and no saved
compressed carrier. Neither old passing nor old failed image checks are replayed.
The corrected offline install completed with no repository warnings but finished
before a live kernel sample. Its observer remains failed and its stopped layer
is retained, not reinstalled. `finalize-fixed-ntfy.py` checks that exact successful
container's configured bounds, package-only delta, signed-install log and
unchanged ntfy executable, then finalizes it. A separate read-only candidate
audit uses a deterministic stdin start barrier for actual kernel-limit/default-
nonroot checks. It is explicitly not a retroactive sample of the fast install.
Both earlier observer failures remain. No bounds or signature checks are weakened.
The first retained-layer finalizer then stopped before commit on its exact path
allowlist: APK uses `scripts.tar.gz`, not the assumed `scripts.tar`. The
separately named continuation checks both the actual APK metadata path and
byte hashes/modes/owners of every contained hook against the base, rather than
allowing an unreviewed script change. The installed layer remains unchanged;
no package installation is replayed.
The package/delta/hook checks then passed and the local candidate was committed,
but Docker omits an empty Config.Cmd key, causing the collector to stop before
audit/export. Its immutable committed identity and passed install receipt are
preserved. `committed-config` continues only that pending audit/export with the
same image; it does not repeat installation, package comparisons or commit.
An omitted command and an explicitly empty command both satisfy the original
no-default-command contract; no application behavior is changed by this fix.
Finalization completed and the changed-image fixture's first attempt then
timed out before TLS/ACL tests while creating its synthetic hash helper.
Reconciliation proved the exact helper was still `created`, never started;
it was removed by exact ID without stopping other workloads. The fixture now
uses an explicitly named/labelled helper, longer bounded create/start calls and
ownership-checked cleanup that never logs credential hashes. The first attempt
remains failed; fresh DB reconstruction for the new subject completed once.
The distinct named-helper fixture subsequently passed for candidatee26ace78…/
configc7054886…. Signed zlib1.4-r0 is the only changed package; ntfy's
executable and APK hook payloads are unchanged. Default nonroot1000:1000 was
exercised without an override. Combined unfiltered current-DB scan reports
zero vulnerabilities/secrets over17 Alpine/86 Go packages, no suppression/
waiver, telemetry disabled. Actual TLS/Bearer ACL/machine-receipt/cache restart
passed, including26 denials and two intended topic flows. This is local
qualification, not attended receipt, production integration or availability.
Fast installer live sampling remains unobserved, distinct from configured
bounds and the passed deterministic read-only candidate kernel audit.
Eighteen obsolete DB/temp/synthetic targets reclaimed1,774,649,344 allocated
file bytes; original base reference retired normally. Unique candidate/export
remain for immutable delivery and route/policy/storage qualification, bound in
`ntfy-zlib-fixed/fixed-candidate-acceptance.json`. The private pin is still
the old held digest; nothing was published or activated. Later gates stay open.

#### Production-like integration preparation — no activation

New fixed metadata-only GET inventory (`prepare-ntfy-integration.py`) binds the
retained candidate and current Traefik/Calico/issuer/node/Longhorn metadata.
It has no Secret reads, exec, apply, dry-run POST, credential, host, DNS or
registry operation. Declared capacity sums are conservative, not metrics or
scheduler-fit proof. Preliminary discovery found no Traefik TCP CRD/provider;
the current inactive IngressRouteTCP therefore cannot be used as-is. Prepare
an already-enabled-file-provider route and a separately reviewed/unapplied
volume projection proposal preserving the existing native dashboard Secret.
Do not install CRDs/broaden RBAC or alter live Traefik during preparation.

Pinned ntfy2.38.1 source uses Go ListenAndServeTLS at startup, not a certificate
reload callback. A projected renewed Secret alone cannot prove installation
at the serving endpoint. Future qualification must distinguish issued,
projected, restarted and endpoint-fingerprint-verified certificates; a safe
approved restart/rollout mechanism is a prerequisite, not already automated.
Source preparation now replaces only the unsupported inactive route with a
public file-provider ConfigMap in the private checkout. It is not mounted
live; the qualified server.yml bytes and held deployment pin remain unchanged.
The separate `qualification/private-ntfy/` contract/proposal/runbook is outside
release composition and contains no executable patch/apply path. It requires
private native-key/identifier collision review and UID/resourceVersion/exact-
volume guards before any separately approved edge rollout, preserving native
dashboard Secret modes/items and read-only directory mount.
The runbook bounds policy/ambient/host controls, actual encrypted two-replica
retained storage/cap checks, resource observations and certificate stages;
it does not implement the proposed rotation controller or close live gates.
`test_ntfy_integration_preflight.py` exercises public projection, provider/
mount-approval behavior, declared-unit/request accounting, incomplete-list
rejection and backend failure propagation using synthetic data only.
The original ten-GET preflight is preserved with its original source hashes:
its unsupported-IngressRouteTCP blocker describes the pre-correction candidate.
The collector now reports missing CRD support as capability metadata, not a
dependency of the replacement file route; live mount/rotation/registry and
execution gates remain blocked. This small source correction needs only the
affected synthetic tests, not a replay of completed cluster reads.
Preparation validation passed: seven preflight projection/capacity/failure
tests and seven private route/inactivity/native-mount/unchanged-config tests;
actual ntfy/watchdog Kustomize object checks; full private validator
(30 charts/31 HelmReleases, effective rendering and credential scan).
The prepared contract/runbook remain inactive. Native file collision audit,
approved mount rollout and actual rotation/route/policy/storage/resource
execution have not happened. Existing image qualification was not repeated.
Small results in `ntfy-integration-preparation/preparation-result.json` bind
that distinction and the read-only closing production-off proof.
James subsequently directed delivery of the settled plan without repeated
approval questions. Earlier “separate authority” holds are superseded for
plan execution, not technical gates. `publish-fixed-ntfy.py` reuses the
established private repository and Windows credential helper with a new
ntfy-specific immutable tag, preserving existing BORTUS tags. It verifies
privacy, qualified digest/evidence/current advisory window, no tag overwrite,
and remote manifest/config plus every layer's full bytes. It neither rebuilds/
exports again nor deploys; credentials remain memory-only and temporary
credential-client config contains no secret values.
The private publication completed with identical digest/config and all four
layer bytes verified remotely. `preload-fixed-ntfy.py` uses the established
saved-node credential and sealed-memory archive receiver on node01/node02;
it preserves the original BORTUS receiver's source/identity contract unchanged.
This ntfy-specific path requires the published digest, bounded free-space
floor plus250MB import reserve per node, all four stored blob checks and
downloaded/unpacked state. No node disk carrier, credentials in pods or
production workload is created by preload.
Both node preloads passed. Node01 then had insufficient Longhorn scheduling
margin for the planned1Gi test claim at the unchanged25% floor. The dedicated
`preserve-ntfy-node01-journals.py` reuses established closed-journal (>72h,
root-owned, stable, no-open-FD) checks. At most six/600MB originals are streamed
to bounded encrypted H storage, authenticated/decrypted and fully compared
with modes/ownership/mtime/xattr metadata before an exact fresh recheck and
retirement. No active journal, rotation, service, volume or threshold change.
The preserved historical logs remain encrypted recovery data, not disposable
fixture output. Local peak admission includes650MB plus the full1GB reserve.
The encrypted node01 preservation completed: six originals fully recovered/
compared before exact retirement,536,895,488 allocated bytes removed;89,137,747
encrypted bytes retained. `ntfy_cluster_fixture.py` and `stage-ntfy-cluster.py`
now implement isolated real cert-manager synthetic CA/leaf issuance, encrypted
retained Longhorn1Gi claim, file-provider edge and selected/denied source pods.
Only named fixture namespaces may be created; no production credentials/keys,
claims or routes are used. The published image is preloaded (pull Never);
no registry credentials are given to pods. Durable create intents/results
record metadata only. Synthetic client tokens are0700-root-contained/0600 H
material for the immediate next phase, never source/argv/log values.
Pods have900-second or shorter deadlines and bounded CPU/memory; no node
reboot, threshold relaxation or production monitor activation. Startup checks
require two replica destinations above the unchanged25% floor plus margin.
`qualify-ntfy-cluster-path.py` follows that exact fixture without recreating
resources: verified routed TLS/public leaf fingerprints, wrong trust/name/
plaintext and unrelated HTTP controls; selected/denied ordinary-pod paths,
DNS/LAN egress controls and actual cgroup metadata. It requests a synthetic
cert-manager reissue by guarded fixture DNS-spec change, separately verifies
new projection while old TLS is still served, then a UID/revision-guarded
Recreate and the new served fingerprint/cache ID on the same claim. This is
real integration qualification, not installed unattended renewal automation.
The first cluster stage stopped before workload creation: Kubernetes forbids
activeDeadlineSeconds in ReplicaSet templates. Its exact rejection and completed
namespace/Secret/PKI/claim/ConfigMap identities remain. Diagnostic workloads now
use standalone Pods, which support native deadlines; this does not remove the
bound or change production's Recreate Deployment design. Explicit continuation
checks each existing UID/owner and creates only absent remaining resources.
The synthetic restart test uses UID/resourceVersion-preconditioned Pod deletion
and recreation on the same retained claim, not a production Deployment rollout.
The actual path check passed: routed trust/plaintext controls and unrelated
HTTP301 survive; selected cross-node source succeeds while unselected/same-
namespace/denied sources fail Service+pod paths. DNS UDP/TCP and owned LAN
node TCP egress fail with positive controls. Actual UID1000/capabilities0/
NoNewPrivs/seccomp2/read-only root,256MiB/no-swap/250m and bounded tmpfs were
observed. Existing kubelet PID ceiling is18847, **not** the local Docker64;
no global node PID setting is changed or falsely claimed.
Real cert-manager revision2 projected a new leaf while ntfy still served the
old one; guarded exact Pod recreation served the new fingerprint and retained
the machine message ID on the same claim/fresh auth tmpfs. No autonomous
rotation controller is installed. `qualify-ntfy-cluster-state.py` adds only
20 serial messages/three poll subscribers, actual resource/replica observations
and SQLite cap refusal on memory-only copies of synthetic DBs. Live file
page counts differ from connection-local max_page_count: the latter is not
claimed queried from ntfy's running connection. No production database touched.
The bounded20-message/three-subscriber run and both independent synthetic DB
cap refusals passed, then the resource collector stopped on an unavailable
memory.peak kernel file. Failure/partial results are preserved. The explicit
`--finish-observations` path reads only pending runtime/replica metadata,
records unavailable kernel fields honestly, and never repeats sends/cap fills.
Pending observations then passed: both actual Longhorn replica UIDs running
on node01/node02, same claim/volume healthy,20 publishes/three subscribers
zero errors (observed p50~66.73ms/p95~76.97ms), memory/RSS/no-OOM metadata.
Actual memory.peak is absent and PID ceiling18847; no local64/peak claim.
All six diagnostic Pods were deleted by UID/resourceVersion preconditions,
forwards closed, local synthetic client token/empty temp removed (8,192
allocated bytes). Retain only fixture PKI/auth/config/claim for the specific
unattended-rotation-controller qualification, then reviewed retirement.
Private source pin now uses the verified published fixed image; contract
records settled execution authority but production technical readiness remains
false, unreferenced/zero-replica. No production activation.
After the OpenCode server restart, terminal publication/preload/stage/path/
state/cleanup/source-validation records were reconciled; no active task driver
or local synthetic client token remained. Boot/store/index are unchanged.
Completed checks were not repeated.
`automation/certificate-rotation/policy.mjs` begins the scoped unattended
serving-leaf controller: observation by default, pinned object identities,
current cryptographically verified issuance and projection, trusted endpoint
observation, single-writer Recreate and fresh CAS. A requested annotation is
not verified renewal; retries reconcile it without another rollout.
This pure decision module has no network/mutation adapter or installed runner
yet. Existing completed cluster restart proof is not automatic-controller
acceptance. Native CA/private keys never enter it.
`controller.mjs` adds the bounded authenticated adapter: public certificate/
CertificateRequest owner+revision binding, pinned CA/signature/SAN/time
validation, mounted public projection, trusted actual endpoint and Secret
PartialObjectMetadata-only contract (reject full Secret payloads).
It re-collects all facts before one CAS annotation PATCH; ambiguous outcomes
are not retried. API TLS uses the existing Kubernetes CA/VIP, serving TLS the
separate pinned private CA. Tokens stay in projected files/memory, not argv/
logs; redirects/proxies/generic out-of-namespace requests are unsupported.
This executor still needs synthetic tests, narrowly scoped identity/manifests
and live observation/rollout qualification before unattended installation.
The focused adapter tests use real freshly signed synthetic public
certificates (ephemeral keys only in owned H test temp, removed afterward).
They cover trust/SAN/owner/revision, full-Secret response rejection,
projection/observation/verified states, pre-dispatch revision drift and
ambiguous response/no duplicate patch. They do not substitute mocked API
transport for effective live identity/RBAC or installed always-on acceptance.
The adapter also pins the Certificate's Secret consumer, the Deployment's
single qualified image and mounted Secret reference. Changed consumers require
attention rather than an inherited restart. Endpoint addresses are explicit
private IPv4 only (including isolated cluster/loopback qualification), with
hostname and CA trust still mandatory; no public redirect/proxy transport.
Read-only real cert-manager inspection corrected the adapter before live
execution: certificate-name is an annotation, not a selector label. The
controller now GETs only the current `<certificate>-<revision>` public request
and checks its annotation/owner/revision, requiring no request LIST privilege.
No controller Job or completed integration check was rerun for this correction.
`ntfy_rotation_fixture.py`/`qualify-ntfy-rotation.py` now package the live
qualification identity: namespace-only fixed Deployment get/patch, one leaf
Secret get (implementation accepts metadata only), one Certificate get and
public request get-only, no LIST/approval/token/host privileges. RBAC cannot
restrict Secret GET by Accept header: the credential can read that one leaf
Secret if misused, never CA-key Secrets; public-only projection and strict
adapter metadata contract are separate controls, not stronger RBAC claims.
Actual projected-token identity/403 tests run first. Jobs use the already
qualified cached BORTUS Node image,100m/128Mi, no swap claim, readonly/nonroot,
60s active deadline/no retry; only public tls.crt/ca.crt are mounted. Explicit
600s API-audience projected tokens remain in pods. NetworkPolicy permits only
API VIP and the selected isolated edge, no generic egress.
Observation then reuses the exact retained synthetic PKI/claim/config, creates
an owned single-writer Recreate diagnostic Deployment and deadline-bound edge,
enrolls actual UID/CA/image bindings and runs the unchanged controller in
observe mode. No production namespace or rollout is changed.
Subsequent phase-specific qualification keeps completed steps exclusive:
observe a reissued/projected leaf without mutation, enable the enrolled
controller for one CAS rollout, verify actual endpoint, then interrupt a
qualification wrapper after its real acknowledged PATCH but before completion.
The wrapper uses the same exported transport/runOnce path; it is not the
scheduled/production entrypoint and does not claim lost TCP-response testing.
Job suspension stops that exact worker; a fresh normal invocation must
reconcile annotation/endpoint without increasing workload generation again.
Finally two actual CronJob-owned scheduled executions (not manual Jobs) must
verify the endpoint. Forbid overlap,60s deadline,30s catchup and bounded history
apply; qualification scheduler is suspended afterward. This is installed
fixture scheduler evidence, not production enrollment or node-reboot proof.
The initial observation Job exited0 with no output and no controller action:
ConfigMap symlinks made argv[1] differ from Node's real import.meta path.
This is a preserved failure, not observation acceptance. CLI detection now
compares the resolved main path as well; a focused symlink regression proves
non-silent fail-closed startup. Explicit `resume-observe` refreshes public
source and creates only a fresh observation Job, reusing the existing
identity/workload/PKI/claim. No completed phase is replayed.
Qualification cleanup is separately callable only after successful native
scheduling proof and suspension: exact recorded object UIDs, no active Jobs,
remove RoleBinding first, then owned Jobs/scheduler/workloads and grants/source/
policy, never adopt by namespace label alone. Pre-existing synthetic fixture
PKI/auth/claim/namespaces are not automatically deleted. Deleting diagnostic
pods/identity is not described as immediate server-side token revocation.
Initial real observation then passed with the expected served fingerprint.
The first renewal driver stopped on helper-call arity before issuing any API
mutation; unchanged Certificate revision2/DNS and Deployment generation1 were
read back. Both incorrect helper calls were corrected. `resume-renew` resumes
only that unstarted mutation path and retains the original failure, without
replaying identity, initial observation or prior integration checks.
The resumed real renewal passed: observe mode left the workload untouched,
auto mode produced one CAS rollout (generation1→2), and the trusted endpoint
served the issued/projected revision3 fingerprint after replacement. The
interruption phase now exercises the same adapter against the next synthetic
revision; no production endpoint, identity or route was changed.
That interruption passed: acknowledged PATCH, actual stopped worker, recovery
verification of the new served fingerprint and unchanged generation3. Native
scheduling qualification is active, counting only successful Jobs owned by the
recorded CronJob UID, never manual Jobs.
The two native runs at21:39/21:40 UTC passed, both returning verified with no
patch for revision4's expected fingerprint. The qualification CronJob was
suspended afterward, then exact owned teardown passed: sixteen objects
explicitly removed; two recorded scheduled Jobs already absent after
foreground CronJob deletion. Zero diagnostic Pods remain; temporary
RoleBinding/Role/ServiceAccount and controller source/policy are gone.
Pre-existing fixture PKI/auth/config/claim/namespaces were preserved.
Native scheduling is independent of the WSL observer; this does not claim
node-reboot or production-controller acceptance.

#### Fixture retirement and production rotation packaging

The completed fixture was separately reviewed after controller teardown:
no workloads/endpoints, attachments, snapshots or backups; original UIDs,
synthetic-only data and no Secret owner cascades. Fifteen exact synthetic
objects including retained PVC/PV/Longhorn volume were retired with UID/
resourceVersion preconditions. Normal finalizers completed, replicas and
generated CertificateRequests disappeared; no forced finalizer removal or
physical-byte-reclamation claim. Three exact namespace objects and their
controller-injected trust/default metadata remain, not a blanket namespace
deletion. Unique pass/failure evidence and encrypted historical logs remain.

Private `flux/private-ntfy-rotation` now packages the byte-identical qualified
controller/policy, not diagnostic wrappers. Content-hashed source and separate
IfNotPresent enrollment, scoped grants, public-only mounts,600s projected token,
100m/128Mi/60s Job bounds and suspended five-minute CronJob preserve its model.
The unchanged controller pins the Kubernetes-CA-verified control-plane address
192.168.0.4:6443 (not the separate API VIP). New Flux children stage ntfy at
zero replicas and rotation suspended with uninitialized observe enrollment;
native auth/Traefik mount/actual serving/enrollment/enablement remain later
guarded steps. The publisher's exact discovered gate advances35→44 alongside
its verifier, preserving all prior checks and Actions-off. Existing H tool
inodes are reused by hard link, not downloaded/copied into another environment.
Exact private commitfcdabd21… subsequently passed singleton44-test validation,
atomic promotion and Flux: parent and both new children Ready on that exact
revision. Packaged source bytes match live qualification; zero ntfy Pods,
Ready private-CA Certificate and suspended/unenrolled rotation. Live edge
Secret/mount remains unchanged, no auth provisioned or serving activation.

The qualification-only `identity-check.mjs` now accepts explicit production
resource names/UID pins in its public ConfigMap. It verifies staged exact
Deployment/current public request GET and metadata-only resourceVersion-bound
PATCH with `dryRun=All`, plus the original eight actual deny boundaries,
including the real CA Secret path. This script is not part of the delivered
controller package and changes no passed controller/policy bytes. A new
production-subject token check is distinct from replaying the fixture checks.
That actual production identity check passed: exact subject/UID, positive
Certificate/Secret-metadata/Deployment/public-request GETs, metadata-only PATCH
server dry run, eight403 denials. Workload generation1/replicas0 and suspended
schedule did not change. The two exact diagnostic objects and Pods are gone.
Staged source/RBAC acceptance does not prove an actual serving endpoint,
notifications or enrolled scheduled renewal; those remain the next live steps.

#### Native authentication and trusted serving integration

Native `private-ntfy-auth` was created once with three ordinary identities,
server config and separate monitor/watchdog/subscriber token keys; values
remained in memory/native Secret only, never argv/Git/SQLite/logs or H payloads.
Passwords were discarded after hashing. Client delivery/actual ACLs are not
claimed by provisioning alone.

Public trust inspection exposed an unsuitable draft name: notifications.lan
is outside the existing root's branconet.lan/branconet.local constraints.
Before serving, the new service is corrected to notifications.branconet.lan;
existing service names/issuer/trust remain unchanged, not weakened. The
server configuration's only byte delta is base-url; actual trusted serving
will qualify that change without replaying image/build/security checks.

Source now proposes one writer and the existing full native Traefik Secret
plus one optional public TCP file in a read-only projected directory/no subPath.
Actual Secret keys/parsed identifiers and fresh UID/RV/exact original volume
are checked before publication and server dry run; Flux SSA owns the eventual
update, not a claimed atomic live JSONPatch CAS. Initial preflight stopped
before Secret/endpoint probes because it omitted the API's defaultMode420
field in its expected original volume. The new projection explicitly preserves
that live0644 mode, and the failure is retained. Ingress permits only selected
Traefik pods in the same namespace peer, with no node-subnet allow workaround.
Rotation remains suspended/unenrolled until real trusted serving passes.
Trust/edge source0024a70… then passed singleton/Flux and corrected revision2
root/constraints/hostname/purpose verification before startup. Writer
source946c1f84… passed singleton/Flux and actual TLS1.3 serving with fingerprint
8f301d72…; wrong trust/SNI/plaintext reject. Native topic publishers/subscriber
and six effective403 denials passed, unrelated trusted controls200, original
encrypted production claim/two running healthy replicas and actual runtime
limits observed. DNS/client/human receipt and monitor/watchdog delivery remain
separate. A diagnostic NameError before the first message was preserved and
only remaining ACL/state work resumed; passed TLS was not repeated.
Actual UID/CA/image/endpoint CAS observe enrollment and a delivered-controller
Job are now in progress before auto/schedule enablement.
That delivered-controller observe Job passed with no patch/generation change
and was removed. CAS changed only mode to auto with pins intact; source5de2c45d…
enabled the normal five-minute CronJob through singleton44-test promotion/Flux.
Its first actual native run at22:40 UTC returned verified/patch:null with the
expected8f301d72… fingerprint and no writer replacement. Source IfNotPresent
preserved operator enrollment. Keep bounded normal native Job history, not
fixture cleanup. No forced production renewal, reboot survival, DNS/human or
monitor/watchdog delivery is inferred; those remaining gates stay explicit.
Notification DNS delivery is now proceeding separately: immutable v4 adds
only the new CNAME, secondary-first checkpoint4a352444… passed exact private
publication/Flux and402 TCP/UDP checks, and primary reference checkpoint8ecc9f87…
is in validation/observation. Claims, CA, native auth, running ntfy and rotation
are unchanged. After cluster parity, the independent advertised resolver still
needs a records-only durable update and serial runtime refresh; cluster answers
alone are not general client/DNS acceptance.
That independent update/serial refresh and external full-record parity now
passed. Both advertised resolvers answered the new name over actual Windows
LAN TCP/UDP; ordinary Windows/WSL DNS and trusted HTTPS200 passed without an
override, serving the unchanged8f301d72… fingerprint. Native writer/rotation,
CA and48 existing names stayed intact. An invalid same-host53 collector was
finished read-only against10554 plus external53, without repeating the successful
restart. DNS acceptance is not human receipt or actual monitor/watchdog alerts.
Host activation continues with the exact previously staged node02 source/unit
checkpoint and no state DB, monitor disabled/inactive, credential timer active.
`deliver-notification-host-credentials.py` provides create-only native-token/
public-CA/config delivery for fixed node02 monitor and node03 watchdog profiles.
It preserves existing accounts and only creates the absent non-login node03
identity/profile needed for private delivery. Root0640/group-readable files,
parent ownership and actual unprivileged read/no-write/other-user denial are
checked. No values enter H/Git/argv/logs and no service starts. Actual monitor
upgrade, paused acknowledgement, durable restart and real alerts remain next.
Both publisher deliveries passed: node02 UID998 retained, node03 non-login
UID997 created; exact selected native token/public CA/config installed with
actual read/no-write/other-user-denial checks and no service activation.
The separate upgrade play preserves all ten accepted installed inputs,
adds only two notifier modules/updated units plus252-only destination drop-in,
and reloads without enabling. Private control-only bootstrap is split from
inactive UI grants; paused/empty IfNotPresent data adds no new authority.
Upgrade passed(ok13/changed4/failed0) with no activation. Live qualification
starts paused, confirms heartbeat/no inventory scans, rejects a duplicate
owner, restarts the actual service and requires the same committed DB/policy.
A custom qualification-signer CSR (no approval controller/key persistence)
will exercise actual pending inventory→durable outbox→host publisher→machine
subscriber delivery. It is not an expired production certificate or human alert
receipt, and must be retired by exact UID/RV after its consumer ends.
No API outage, issuer/CA change or broker/timer restart is used for this test.
Actual paused-first qualification passed: no inventory scan/outbox while
paused, duplicate owner rejected, actual systemd restart preserving the same
private SQLite inode/policy, and enabled monitor with notifier still stopped.
Kernel samples confirm UID998/CapEff0/NoNewPrivs1,256MiB/no swap/10% CPU/
64 tasks/no OOM. The actual pending diagnostic CSR now exists under a custom
qualification signer, with its key discarded in memory; fresh UID/RV policy
CAS and actor/audit changed only paused→monitor at the existing300-second
interval. Real inventory/outbox/restart qualification is active.
Native pending inventory produced one real outbox event; actual monitor
restart preserved its undelivered state, original complete scan ID and private
SQLite inode with no duplicate event. The separate sender is now being
qualified against that database. Do not confuse a durable pending event with
server acknowledgement or attended receipt.
The first sender phase timed out with its event still undelivered/backoff
preserved. Bounded no-token/no-publish systemd probes proved VIP-only
cgroup-SKB egress times out after Service DNAT; adding only current Traefik
pod IPs succeeds but is not durable and was not adopted. The reviewed fix uses
a root-managed fixed pre-start nft helper: only the sender cgroup, original
VIP252/TCP443 allow, all other IP egress reject, atomic owned-table replacement.
It resolves the cgroup on every start, not pod addresses. Stop cleanup refuses
surviving consumers/unknown tables. The application stays UID998/capability-free;
only fixed root policy installation runs pre-start. Actual positive/negative
kernel enforcement and resumed outbox acceptance remain required.
`qualify-notification-egress.py` uses a temporary root-owned runtime override
on only the stopped sender unit. With the actual cgroup policy, UID998 must
reach trusted notification HTTPS but fail API VIP6443 and notification VIP80;
those endpoints are first proven reachable outside the sender cgroup.
It reads no token and publishes nothing. Normal stop must remove the owned
table, then exact probe/override removal and daemon reload resume the unchanged
real outbox/backoff. Any uncertain result retains diagnostics and stops replay.
Actual nft checks now passed: trusted HTTPS200, API6443/VIP80 rejected,
eight allowed/two rejected packets observed on the exact owned table. First
bounded probe failed; the separate counter/error collector passed and
remaining normal teardown/runtime override cleanup completed without replaying
the successful sends (the probes never published). The real sender resumed
its same event/backoff; its acknowledgement/restart observer is active.
Current fresh-upgrade source includes the nft helper directly and no obsolete
VIP-only drop-in; the original executed upgrade/repair hashes remain historical.
`finish-monitor-notification.py` continues only after the original sender
acknowledgement/restart receipt. Its native subscriber poll checks the exact
stable event ID, CSR UID and full metadata message, recording any duplicate
copies under the at-least-once contract; credentials remain memory-only.
Only then can it retire the labelled custom-signer CSR with fresh UID and
resourceVersion DeleteOptions, requiring unchanged request hash and no
approval/issuance/owners/finalizers. An audit-only policy CAS requests a fresh
inventory without altering300-second/7-day policy or clearing DB/outbox.
Neither subscriber receipt nor this cleanup proves attended delivery.
The resumed sender's next real attempt also failed, advancing its existing
backoff to00:03:22Z with no ACK. Offline actual-profile/event/bounded-child
validation passed without network/publish. Fixed-code local-journal diagnostics
are now prepared for child/transport errors: only an allowlist code and phase,
never exception/backend text, endpoints or tokens; missing journal cannot
alter retry behavior. No retry reset, manual publish or completed network
qualification replay is part of this correction. Live diagnosis remains open.
The original600s ACK observer ended unacknowledged and did not perform its
post-ACK restart. Two new diagnostic tests passed (private-text withholding
and nonfatal journal loss). A separate one-script Ansible correction guards
the installed hash, stops only sender, installs fixed-code diagnostics and
resumes it; it does not replay staging/egress repair or change the outbox.
The next native attempt failed with fixed transport-unavailable/child-failed
codes, not an ACK; no OOM. A distinct non-publishing OPTIONS diagnostic using
the exact transport class/resource sandbox/original-destination rule completed
trusted TLS and HTTP401 (synthetic invalid credential), with no token read or
message publish; its separate cgroup/table ended normally. A read-only
subscriber-diagnose phase can now reconcile possible accepted-but-unacknowledged
messages before another retry, without allowing CSR retirement or altering DB.
The full child-entrypoint non-publishing diagnostic also completed trusted
connect/request/HTTP401 in2.399s under the same resource limits; its owned
diagnostic table was removed. Native subscriber found zero original-event
copies. To diagnose the actual intermittent failure rather than repeat probes,
the transport now attaches only allowlisted stage/kind to its existing fixed
error; journaling validates those fields independently. No timeout, network
permission, ACK contract or retry interval is changed.
Six focused checks passed for these changed sources: fixed-stage/private-text
diagnostics and real loopback TLS/ACK rejection. Test synthetic material was
removed. The scoped diagnostics play now guards both installed module hashes
and updates only transport/sender annotations; original one-file execution
receipts remain historical. The next actual due retry stays unmodified.
The original event was subsequently acknowledged on its normal00:36:26Z
retry; the retry row is absent, with no reset/manual send. Prior intermittent
transport failure cause remains unestablished and is not declared fixed.
Post-ACK sender restart is being qualified separately. After exact subscriber/
CSR cleanup, the continuation's read-only fresh-inventory phase requires the
same policy revision acknowledged, complete run/two fresh available sources,
actual operator UID/state parity and zero current CSRs; it makes no lifecycle
mutation and does not qualify the unreleased static UI delivery labels.

Actual monitor→durable outbox→host publisher→native subscriber path now passed.
Exactly one cached message matched event2621e9b0…/CSRUID41826f46…; no
attended receipt is claimed. Post-ACK actual sender restart retained the same
delivered row/SQLite inode3415914; first loop accepted0/failed0/pending0,
UID998/CapEff0/NoNewPrivs1 and128MiB/no swap/5%CPU/32tasks/no OOM matched.
Monitor and accepted credential timer invocation/bytes stayed unchanged.
The diagnostic CSR alone was deleted with fresh UID/resourceVersion guards,
no approval/issuance; audited same-policy refresh then matched actual15 healthy
Certificates/zero CSRs/zero pending notifications and two fresh available sources.
All10 Flux Kustomizations/36 HelmReleases and three nodes are Ready; ntfy's
writer/rotation are unchanged. Evidence is bound by
`monitor-host-activation/monitor-notification-delivery-acceptance.json`.

This bounded delivery/persistence result does not establish immediate/reliable
delivery under every path: creation→ACK took3972.298674s (about66.2min).
Six failures/retry history remain; later intermittent transport cause is not
established. Fixed safe diagnostics stay enabled. Watchdog identity/refresh/
live outages, attended subscriber/reader, node-reboot survival, UI status/release,
certificate lifecycle/retirement and remaining network phases remain open.
Next watchdog read-only preflight passed on node03: existing non-login UID997
publisher profile preserved; private root bootstrap/public CA/kubectl already
exist, no credential copy needed. Watchdog code/state/enrollment/services and
API identity are absent. Fresh observations/policy/node02-Lease UIDs captured.
Source now adds a fixed `watchdog` credential profile (two exact GET allows,
no monitor list/PATCH privilege) plus a separate node03 root broker that reuses
the bounded API/atomic-file primitives. Default monitor behavior is unchanged
in source; accepted installed node02 broker/module bytes are NOT updated.
Watchdog token publication requires authenticated own subject, effective RBAC,
fresh UID rechecks and exact pinned observations/policy/Lease reads; recreation
quarantines only its own runtime token. No installation/mint/publication yet.
Separate inactive watchdog credential unit/timer sources preserve the accepted
root-broker bounds (256MiB/no swap/10%CPU/64tasks, API-VIP-only, one-hour token/
twenty-minute refresh). No service is installed/enabled by these files.
Enrollment rejects malformed pins/private-bootstrap permissions before mint;
focused tests cover independent subject/two GETs, monitor-token or expanded
role rejection, recreated observations and unknown-profile/no-mint.
An external identity qualifier is prepared for the exact Flux-created UID:
one-hour TokenRequest, API-authenticated subject, two required/representative
deny reviews, two actual named GETs and seven actual Forbidden probes
(observations PATCH is server-dry-run only). Candidate config/token remain
in a private sealed memfd, never argv or disk; closing it is not revocation.
This is not host credential publication/periodic-service acceptance.
The first synthetic sealed-config smoke stopped before network/mint because
the retained Python lacks symbolic fcntl seal constants. The qualifier now
uses stable Linux UAPI values when names are absent and requires the kernel
to report all write/grow/shrink/seal bits; no unsealed fallback is allowed.
The interrupted synthetic FD closed normally and no disk payload existed.
Corrected sealed-config smoke passed real kubectl parsing, kernel seal15
readback and EPERM on attempted write; FD closed, no network/mint/disk payload.
Separate `certificate-watchdog-credential-host.yml` is preflight-by-default,
requires existing UID997/publisher file inodes/private bootstrap/tool/CA and
absent new targets, and stages only five broker sources/public enrollment/
CA/config/two inactive credential units after actual identity qualification.
It neither creates detector state nor starts/enables services or touches
notification credentials. Do not replay after partial staging.
Private identity7970fc1… is now exact44-test/Flux qualified, SAUID34e95231….
Actual independent authenticated subject and2 allow/30 deny reviews,2 named
reads/7 Forbidden checks passed with sealed RAM-only candidate, FD closed.
This proves effective scope, not host credential publication or timer/service
availability; monitor/sender/accepted node02 broker are untouched.
The existing bounded credential collector now has only two fixed qualification
profiles. Its node03 wrapper binds the staged hashes/public enrollment, requires
detector absent and first token absent, and retains live actual-Python/cgroup
sampling plus unknown-outcome refusal. The watchdog timer arm waits for a
genuinely new initial invocation before recording the next20min due; periodic
observation is read-only. This does not replay node02 checks or change its
installed broker/timer. Watchdog host results are not implied by wrapper source.
Actual node03 root broker qualification passed295 kernel samples, observed
memory maximum69,402,624 bytes/four tasks,256MiB/no swap/10%/64tasks. Actual
Python root context had NoNewPrivs1/CapEff+CapBnd9; the pre-exec executor's
broader initial context is retained separately, not misreported. Own2/30 scope
and exact observations/Lease reads passed; private root:997/0640 token exists.
Only its credential timer is now enabled; initial native timer invocation
passed and next20min due is being observed read-only, not yet periodic proof.
Detector/notifier remain absent.

While awaiting that periodic result, detector/notifier source now prepares
a separate volatile cache plus fixed node03/UID997 notifier firewall wrapper.
It reuses only the reviewed atomic original-VIP helper logic with a distinct
cgroup/table/owner and no destination CLI, token or broader network grant.
Default node02 helper semantics stay unchanged and installed bytes untouched.
These units/wrapper are not installed or activated by source preparation.
Runtime install then passed(ok13,changed3) after real periodic credential
acceptance: seven root-managed sources/public pinned enrollment plus two
inactive detector/notifier units; broker/timer unchanged by the play.
Detector healthy qualification passed: enabled actual UID997/CapEff0/
NoNewPrivs1 under128MiB/no swap/5%/32tasks, private0700 state/0600 SQLite,
healthy coverage/monitor heartbeat/node02 lease and zero pending events;
notifier remained inactive. Its first attempt stopped only in a read-only
SQLite inspection that raced the detector's write; the shipped qualifier now
retries read-only opens, and completion was read-only (no restart/re-enable).
Actual bounded node02 monitor outage/recovery is running; no result is claimed
yet.
Watchdog detector/outage delivery then PASSED. A real bounded node02 monitor
stop produced a durable `missed` event after181.13s (180s threshold) while the
node02 Lease stayed healthy; the node03 notifier delivered it with server ACK.
The monitor was restarted and a `recovered` event was likewise delivered, with
exactly one authenticated subscriber copy of each cached. Monitor DB
inode3415914/policy and its credential timer were preserved; detector,
notifier and credential timer are enabled; the notifier firewall owns only its
own cgroup table and diagnostic tables/runtime overrides are absent. This is
machine delivery, not attended receipt or full-cluster/node03-failure resilience.

Kubelet-serving CSR approval work has started with observation only. The
existing strict validator is now used by `kubelet_csr_controller.py`, which
records one verdict per CSR UID, refuses request changes under the same UID,
allows at most one approval per UID across restarts, and verifies a returned
certificate's SANs/usage/validity without claiming installation. Fifteen
focused checks passed (nine new controller cases plus six policy regressions).
Live observation ran read-only for node02: zero pending CSRs, zero mutation.
Private checkpointb81ba44… (44 tests/validator) added the observation-only
reader identity `bortus-csr-controller` (SA UID244f185e…, no automount,
get/list on CSRs and nodes only). With a sealed RAM token, CSR list and node
get were allowed while approval update, CSR update/create, signer sign, Secret
read, CSR watch and policy patch were denied by review and by actual403.
Approval mode exists but is not enabled; installed-certificate endpoint
verification and managed-host installation remain open.

Live positive/negative qualification has now passed with approval disabled.
Two genuine pending CSRs were created from node02's own kubelet credential
(`system:node:node02`, groups `system:nodes`): one with the enrolled identity
and one carrying an extra `node03` SAN. Observation returned `eligible` with no
reasons for the first and `sans_invalid` for the second; both were recorded
durably with neither approved nor issued, then deleted with UID/resourceVersion
preconditions, leaving zero CSRs. No private key left the generating process.
Served-endpoint verification is now a reusable check: it requires the presented
certificate to chain to the enrolled issuer, carry exactly the enrolled DNS/IP
identities, be currently valid and be usable for server auth. Applied to
node02's live kubelet endpoint (TLS1.3, `CN=system:node:node02,O=system:nodes`,
issuer `CN=kubernetes`) it passed and pinned fingerprint
`80a9e9fe…` (NotAfter 2027-11-16). Approval enablement still requires a real
renewal window and a managed-host installation; no approval has ever run.

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
Phase C plaintext inventory is underway and read-only. Node-IP listeners and
DNAT service paths were enumerated on all three nodes: 17 host-level surfaces
(8 plaintext incl. kube-proxy healthz/healthCheckNodePort, MetalLB gossip,
rpcbind, NFS/SMB-CSI, Cockpit on TLS with self-signed certs) plus 22
`externalIPs` service publications and three MetalLB VIPs. No firewall,
Service, port or certificate change was made; candidate restrictions are
recorded for separate review in `plaintext-inventory/phase-c-findings.json`.

 The CSR was then deleted with UID/resourceVersion guards and the
qualification key/certificate removed, leaving zero CSRs. Two failures are
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
Four changed-helper refusal/fixed-profile checks and two local unit verifies
passed. UID997 actually reads its managed token/config/CA and both pinned API
objects, cannot write them/broker/unit/profile or read root bootstrap/lock;
original publisher inodes remain. These checks do not substitute periodic proof.
The separate preflight-by-default runtime play preserves all seven accepted
broker source/unit hashes and active timer, refuses existing runtime state/
units/drop-ins, and can add seven runtime files/public UID arming/two inactive
units only after real periodic acceptance. It never starts/enables a detector/
sender or modifies notification/API credentials.

Runner-readiness corrections: CLI stdout/stderr limits are enforced while
draining the process pipes, not after unbounded buffering. Inventory reads allow
2 MiB, control reads 768 KiB and patch responses 16 KiB; stderr is capped at
16 KiB and never disclosed. Patch stdin is capped at 512 KiB. The 25-second
deadline includes pipe-holding descendants; only the invocation's own process
group is terminated on failure. Interrupted read-only scans are retried on the
next cycle after restart without waiting for the scan interval. Completed
scans whose snapshot publication failed retain their existing retry behavior.

`GET /api/certificates` now includes `controls`: requested policy, the runner's
acknowledged UID/revision, heartbeat, durable observations, latest run and pending
notification count. A heartbeat older than three minutes is offline; unacknowledged
policy is pending, and stale/unavailable source coverage is degraded. Paused
observations remain explicitly historical. The metadata-only
`PATCH /api/certificates/policy` requires fresh operator authorization, same
origin, a bounded body and policy UID/resourceVersion preconditions. It changes
only the fixed policy ConfigMap and records the last 50 operator changes.
Neither mode grants approval, renewal or retirement authority. Private Flux
bootstrap/scoped RBAC and rendered/deployed qualification remain unfinished.

An inactive private-charts candidate at `flux/certificate-monitoring` now defines
the two seeded ConfigMaps and separate UI/monitor metadata grants. It is not
referenced by active release composition and has not been published or applied.
Flux `IfNotPresent` preserves operator/runner-owned data; later schema changes
need explicit migration, not edits to seed data alone. The monitor can patch
observations only; BORTUS can patch policy only. Neither candidate role has
approval, Secret, token-minting or host-operation privileges.

Focused working-source verification:

- Frontend: `npm run test:certificates` from `k8s-rewrite/front-end` (uses Node's
  built-in test runner and type stripping; no dependency install is needed).
- CSR policy: `python3 -B -m unittest discover -s scripts/migration/tests -p test_kubelet_csr_policy.py -v`.
- Durable monitor: `python3 -B -m unittest discover -s scripts/migration/tests -p test_certificate_monitor.py -v`.
- Monitor control/acknowledgement: `python3 -B -m unittest discover -s scripts/migration/tests -p test_certificate_monitor_control.py -v`.
- Bounded runner transport: `python3 -B -m unittest discover -s scripts/migration/tests -p test_certificate_monitor_process.py -v`.

These checks use synthetic signed CSRs and in-memory SQLite, respectively.
Transport checks use task-owned local Python child processes, without output
files or production credentials.
They do not establish rendered UI, deployed RBAC, unattended scheduling,
notification delivery or production renewal acceptance.

The component/API interaction fixture is
`k8s-rewrite/front-end/tests/certificate-controls-fixture.mjs`. It reuses
explicitly supplied existing test dependencies, bundles only in memory, serves
loopback only and has no production credentials. Browser checks exercised
requested-versus-acknowledged policy, stale-write errors, readonly/direct-write
denial and stale heartbeat presentation. The fixture is not production styling,
the Next application build or actual screen-reader acceptance. Its dedicated
container and browser session were removed after the checks.

The complete certificate screen and controls subsequently passed a read-only
selected typecheck using the retained H security-qualification v8 tree's
TypeScript 5.9.3, React 18.3.1 and lucide-react 0.460.0 types, with zero
diagnostics and no emitted files. The historical full dependency tree differs
from the current lock/schema and has Windows native binaries; it is not a
qualified Linux application-build environment and must not be modified.

Linux qualification now uses the current lock's sole H dependency tree via
`scripts/migration/qualify-certificate-frontend.py`. Install, source-maintained
dependency preparation and Prisma generation passed with source/lock/index
unchanged; the stage measured about 1.304 GB before the first build attempt.
That attempt stopped in native prebuild because GCC's sanitized environment
could not use a writable `/tmp`. The correction binds H temp to the default
path without changing compiler pins; no completed install/generation is replayed.
These early attempts did not yet establish full build/rendered acceptance;
the subsequent successful build and desktop/API results are recorded below.
After H `/tmp` routing was corrected, native compilation passed its pinned
reproducibility checks and Next compilation caught a real certificate-page
defect: the server component awaited `getOperatorRole()` without an async
declaration. The page is now async, consistent with existing operator pages
and the official Next 15 Server Component contract. Earlier selected checks
did not cover that defect; the subsequent release-context build verifies it.
The next build compiled successfully, then correctly failed the mandatory
React-hook lint gate on policy synchronization. The effect now declares its
policy dependency and compares UID/revision before replacing the draft, so
heartbeat refreshes cannot silently erase an unsaved operator edit. Lint is
not disabled; the matching lint/build and application checks below passed.
The combined lint/type build then hit Node's default ~512-MB heap limit. The
qualification driver now supports separate full ESLint and matching-source
Next build/type gates inside the same two-CPU/1-GiB/no-swap cap. Serial Next
uses documented `--no-lint` only after the unfiltered lint command passed for
the identical source; the type worker receives a 768-MB heap within that cap.
No production config, memory limit or required check is relaxed.
Unfiltered `npm run lint` passed for all 993 bound source/config/test files.
Whole-checkout type discovery still exceeded the heap; the actual release
`.dockerignore` excludes `tests`. The context build now mirrors that existing
rule with a read-only empty mount (no test deletion/copy), retaining full
application/generated-route type validation and the matching full lint result.
Do not describe this as a passed whole-checkout test typecheck.

`tests/certificate-application-fixture.mjs` provides the application-level
check: the actual built Next server, current Prisma schema and real login/role
authorization, using synthetic accounts/state and a local fake kubectl. Its
loopback-only control listener changes synthetic acknowledgement/heartbeat and
operator privileges; it has no production credentials or cluster connection.
Unlike the earlier component fixture, it serves the built production assets.
Launch only against a matching successful build. Named driver attempts use
fresh fixture directories rather than overwriting retained synthetic metadata.

Release-context Linux build has now passed in 72.42 seconds, including full
application/generated-route type checks and native/worker packaging, paired
with the matching full-checkout ESLint pass. The stage peaked at 1,699,647,488
bytes under the 4,000,000,000-byte ceiling. Source/lock/index stayed unchanged.
The actual application fixture exited cleanly after its completed desktop/API
checks. Real login, keyboard save, pending → acknowledged pause, draft
preservation across same-revision refresh, readonly controls and offline/history
presentation passed. Real API denials passed: readonly/non-admin writer and
cross-origin 403, stale revision 409, oversized body 413, invalid policy 400;
operator revocation took effect on the existing session (403). Denials preserved
policy state. Production CSS and desktop rendering were inspected, with retained
screenshot and `application-browser-result.json`.

Phone-size acceptance was initially unverified: the attempted 390px popup
stayed 800px and was not mobile evidence. Actual viewport results follow;
attended screen-reader announcements remain unverified.
The supported browser CLI viewport command then established real 390px/320px
views and exposed unbroken resource metadata overflowing the monitoring panel
(404px page width). The panel now allows long text to wrap anywhere, preserving
content rather than clipping it. This source change needs fresh matching lint,
release-context build and phone rendering; previous desktop/API evidence is
retained, not silently rebound to changed source.
The wrapping correction passed named full lint/release-context build and actual
320px/390px rendering (page widths exactly 320/390; expanded observations fit).
The subsequent axe 4.12.1 audit found CSR timestamp contrast 4.11:1 and a
non-focusable horizontal table. Timestamps now use zinc-400; the table's
scroll region has a name, tab stop and visible focus ring. These corrections
were verified by the subsequent `phone-a11y` matching full lint/build (70.82s),
real 320px/390px layout and keyboard scrolling. Current source fingerprint is
`561826437128d627d2b59fff280749902700db4d40c1673caf77da8a04f87dea`;
build ID `1Z4OrQk6ue0Sv4szH1jFe`. Arrow keys moved the named table's scrollLeft
to 48px after Tab focus, with a visible 2px outline. Axe 4.12.1 reports zero
violations at 320px (five offscreen contrast observations incomplete), and zero
violations/incomplete checks at 1280px with those cells visible. Phone page and
panel widths fit; screenshots and `responsive-a11y-result.json` are retained.
Attended screen-reader announcements remain unaccepted; axe/DOM checks cannot
replace them. The fixtures/browser closed cleanly. Additional regenerated cache
and finished synthetic payload cleanup reclaimed 228,614,144 allocated bytes;
the current built runtime/dependencies remain for reader/release qualification.
No production deployment, scoped live RBAC or always-on runner is implied.
The fixture container/browser are closed; synthetic SQLite/kubeconfig/fake CLI
cleanup reclaimed 319,488 allocated bytes. Four public metadata JSON records
remain. Admitted package and Next caches were removed (461,807,616 allocated
bytes); the sole installed dependency tree and built runtime are retained for
remaining responsive/accessibility/release qualification without rebuilding.

A separate synthetic on-disk monitor check on the same H store survived closing
and reopening SQLite in two real Python processes with the same run ID, one
observation and one pending notification (no duplicate scan/outbox). A competing
process was refused by the held lock, then acquired it after release. This
qualifies durable-core file/lock behavior, not a scoped production identity,
notification delivery or an always-on service.

| Path | Trust anchor | Leaf lifetime / renewal | Verified |
| --- | --- | --- | --- |
| LAN HTTPS (`*.branconet.lan`, `*.branconet.local`) via Traefik VIP `192.168.0.252` | private name-constrained `branconet-local-root` (cert-manager, to 2031-10-25) | 90 days, cert-manager renews ~15 days early (next 2027-01-09) | 22 hostnames pass CA + hostname validation; a forced renewal of `whoami` issued revision 2 and Traefik served the new serial |
| Public `*.jtmb.cc` | Cloudflare edge certificates (Google Trust Services WE1 observed); origin reached through Cloudflare Tunnel | managed by Cloudflare | 6 public routes return their baseline status (200; media 307) |
| kubectl → API (`k8s-api.branconet.lan`, VIP `192.168.0.251`, node IPs) | Kubernetes cluster CA (to 2036-10-06) | kubeadm leaf, 1 year, **not auto-renewed** | CA-pinned TLS 1.3; expiry check below |
| API server → kubelet (logs, exec, attach, port-forward) | Kubernetes cluster CA | kubelet-serving CSR, 1 year, kubelet requests rotation | **new**: `--kubelet-certificate-authority` on all three API servers; 9/9 server×node log checks, exec and port-forward pass |
| Pod ↔ pod (enrolled namespaces) | istiod mesh CA (self-signed, to 2036-11-13), separate from both CAs above | 24 hours, automatic | see `docs/WORKLOAD-MESH.md` in the private charts repository |

## Kubelet serving certificates (2026-11-16)

Before: each kubelet served a self-signed `nodeNN-ca` certificate and the API
servers did not verify kubelets, so the API → kubelet hop of `kubectl logs/exec`
was unauthenticated. Changes, all through
`k8s-rewrite/ansible-playbook/playbooks/kubelet-serving-tls.yml` launched by
`scripts/migration/run-kubelet-serving-tls.py <phase> --work-dir <H dir>`:

1. `kubelet`: `serverTLSBootstrap: true` per node, serially; kubelet restart
   (pods are not restarted); `scripts/migration/approve-kubelet-serving-csr.py`
   approves only a recent Pending `kubernetes.io/kubelet-serving` CSR from
   `system:node:<node>` with exact subject/groups, valid PKCS#10 signature,
   approved key/hash types, exact node DNS/InternalIP SANs and serving-only
   usages. The shared `kubelet_csr_policy.py` uses Python `cryptography`, not
   OpenSSL display-text parsing. Node UID/address changes and unexpected
   extensions fail closed; approval uses CSR UID/resourceVersion/request
   preconditions. `--check-only` never approves. Future unattended callers must
   use a previously reviewed `--enrollment-file`, not self-enroll from the CSR.
   Manual `--node` invocation explicitly selects the current live node.
   After approval the kubelet must pass
   `openssl s_client -verify_ip` against the cluster CA and the node must be Ready.
2. `apiserver`: adds `--kubelet-certificate-authority=/etc/kubernetes/pki/ca.crt`
   to each static API server manifest serially, waits for `/readyz` on that
   server and proves logs from every node through it.
3. `kubeadm-config`: writes the same two settings into `kube-system/kubelet-config`
   and `kube-system/kubeadm-config` so `kubeadm upgrade` keeps them.

The API server manifests and `kubeadm-config` also carry the audit-logging
flags and mounts added on 2026-11-19; see `docs/API-AUDIT-LOGGING.md`.
`kube-apiserver.yaml.pre-kubelet-ca` predates that, so restoring it now also
removes audit logging. To undo only the kubelet CA flag, remove that one line
from the current manifest instead.

Originals are preserved on each node as `/var/lib/kubelet/config.yaml.pre-serving-tls`
and `/etc/kubernetes/kube-apiserver.yaml.pre-kubelet-ca` (outside the static
manifest directory). Rollback: restore the API server manifest first (serially,
waiting for readiness), then the kubelet config and restart kubelet, then remove
the two ConfigMap entries.

**Renewal:** kubelets request a new serving certificate at roughly 70–90 % of
its year. kube-controller-manager does not auto-approve kubelet-serving CSRs;
run `approve-kubelet-serving-csr.py --node <node>` for each node when the
expiry check reports less than 90 days or a CSR is Pending. If one lapses,
only logs/exec/port-forward to that node fail; workloads are unaffected.

## Control-plane certificate expiry check

`python3 -B scripts/migration/run-control-plane-cert-check.py` runs
`playbooks/control-plane-cert-expiry.yml` (read-only, become via the saved node
credential in memory). It fails if any kubeadm leaf or the kubelet serving
certificate has fewer than 90 days left, or the kubelet certificate is not
issued by the cluster CA. `super-admin.conf` exists only on the first control
plane; its absence on joined nodes is expected and reported separately.

2026-11-16 result: earliest leaf node01 327 days (2027-10-09; most node01
kubeadm certificates), node02/node03 356 days (2027-11-08); CAs 3,612 days;
kubelet serving certificates to 2027-11-16. **Run it before 2027-07-11.**

### Renewing kubeadm certificates (when the check fails)

One control-plane node at a time, after a fresh control-plane backup
(`run-control-plane-backup.py`) and a healthy etcd quorum:

1. `sudo kubeadm certs renew all` on the node.
2. Restart its static pods by moving `kube-apiserver.yaml`,
   `kube-controller-manager.yaml`, `kube-scheduler.yaml` and `etcd.yaml` out of
   `/etc/kubernetes/manifests` for ~20 seconds and back, then wait for the API
   server `/readyz` on that node and etcd member health.
3. Refresh operator kubeconfigs that embed `admin.conf` client certificates
   (`~/.local/share/branconet-migration/admin.conf`) from the renewed node.
4. Re-run the expiry check, then continue with the next node.

A `kubeadm upgrade` renews these certificates as part of the upgrade.

## Known residuals

- `wordpress/jtmb-cc` (Let's Encrypt HTTP-01, renewal due 2026-12-08) belongs to
  the retired WordPress stack: no workload or route uses `jtmb-cc-tls`, and the
  Cloudflare Tunnel has no `jtmb.cc` route, so its renewal is expected to fail
  harmlessly. It is left in place (pruning disabled; no data deletion implied).
- The reused local Chromium for the Agent Browser MCP is behind the current
  stable patch level (see the Veyra MCP README); unrelated to cluster TLS.
