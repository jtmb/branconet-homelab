# Migration and maintenance status

**October28 runtime canary accepted:** HTTP Echo is healthy on the new instance
manager after real Flux detach/reattach, with original data/image/template and
two actual RW replicas preserved. A targeted Ansible multipath guard repaired
its mount failure and now protects all three nodes without service restart.
The failed14,100-second readiness wait remains historical evidence. New validated
chart0.1.1 restored Ready release/Kustomization state at
`b5286ec8bf287ca4c248356ee59e860fccb43749`. All58claims,14NASbindings and three
Ready nodes survive; no desired Deployment/DaemonSet is unavailable. Removed
533,581,824Linux publisher scratch bytes, retaining original source and failures.
[Exact proof and remaining runtime/security/browser gates](docs/LONGHORN-RUNTIME-RETIREMENT-20261028.md).

**October 28, 01:56 UTC:** all 43 initialized V1 volume engines and the manager
are upgraded to v1.13.0. Every original volume/claim/NAS identity survives, with
28 healthy attached volumes/two actual RW replicas and 15 retained initialized
datasets still detached. App mounted-data reads and original Pod/image/restart
identities passed. Three old instance managers remain because live upgraded
engines are still hosted there; supported retirement needs controlled detach/
reattach. The unused WordPress volume keeps its old metadata reference.
[Acceptance, preserved failures and remaining runtime/security/browser work](docs/LONGHORN-UPGRADE-EXECUTION-20261028.md).
No full-goal completion or all-old-runtime-retirement claim is made.

**October 28 manager upgrade:** Longhorn manager v1.13.0 is deployed and its
rollout/identity/redundancy checks passed. Fresh encrypted NAS/offline checkpoint
and native configuration bundle are qualified. The 43 initialized V1 engines
have a serial plan; engine execution and final fleet/security/IAB gates remain.
Removed 213,721,088 allocated Linux scratch bytes; retained the exact 12,288-byte
root-owned packaging subtree after its Windows handle check failed.
[Actual execution, recovery and remaining work](docs/LONGHORN-UPGRADE-EXECUTION-20261028.md).

**October 28 staging complete:** all thirteen official pinned images are fully
verified on all three nodes. Actual runtime and all claim/volume/engine/replica/
NAS identity and health comparisons passed. Both empty controller scratch
directories were removed (8,192 allocated Linux bytes).
[Source, constraints and output ownership](docs/LONGHORN-PRODUCTION-STAGING-20261028.md).
Manager/engine upgrade and the full goal remain incomplete.

**October 28, 00:34 UTC:** the complete thirteen-image Longhorn candidate now
passes all three observed node budgets, retaining the measured host payload,
512 MiB margin and unchanged storage controls. Exact duplicate transfers and
inactive analysis-cache retirement recovered another 1,298,948,096 node bytes;
cumulative node cleanup is **27,757,309,952 bytes**. Original primary archives,
all reports/source and application data remain. Controller scratch is reconciled.
[Exact methods, paths, capacity and remaining execution](docs/LONGHORN-NATIVE-CAPACITY-GATE-20261028.md).
Production cache staging and manager/engine upgrades have not run. Full goal
active; final fleet/security/normal Seerr/YTPTube browser gates remain.

**October 28, 00:08 UTC:** current Ruckus and Ingenium native backups completed
without changing writer Pod/image/restart, Volume spec or original replica UIDs.
Eleven new datasets now have independent RAW verification, totaling 5,831 blocks.
Ingenium's complete native RAW backing passed every original check after its
optional RAW-copy timeout; the failed command remains failed and its partial
output is preserved losslessly by a 52-range recipe. Recovery scratch removal
totals **30,962,319,360 allocated controller Linux bytes**.
[Exact acceptance and limits](docs/CURRENT-WRITER-NATIVE-RECOVERY-20261027.md).
Fresh metadata covers all 43 initialized volumes with Completed native backups;
the unused WordPress destination remains separately qualified. All 58 original
claim bindings/44 volume UIDs, three Ready nodes, available workloads and
unsuspended Flux survive. No Windows disk recovery is inferred.

Ansible also retired 749,178,880 allocated master bytes of generated source
exports while preserving complete original source/locks/deltas and the unmatched
link. Cumulative node cleanup is **26,458,361,856 bytes**.
[Exact source proof and cleanup](docs/MASTER-SOURCE-EXPORT-RETIREMENT-20261027.md).
The full goal remains active: remaining server headroom, guarded Longhorn
manager/engine upgrade, final fleet/security exceptions and normal Seerr/YTPTube
IAB acceptance remain. Fresh cache measurements supersede old capacity assumptions.

**October 27, 22:05 UTC:** physical/source/UID checks proved the preserved unused
WordPress destination has no initialized payload. No attach, mount, data copy,
Secret read or deletion occurred. Its metadata remains recoverable; WordPress
stays retired. Two current-writer recovery gates remain: Ruckus and Ingenium.
Three missing native Backup CRs include this unused claim; no backup is falsely
claimed. [Exact lineage](docs/UNUSED-WORDPRESS-VOLUME-LINEAGE-20261027.md).
The production Longhorn upgrade and final fleet/security/IAB checks remain.
Full goal stays active.

**October 27, 22:03 UTC:** retained Ruckus recovery passed: original replica
preserved, existing desired two replicas restored by the normal manager, full
native NAS backup and independent 166-block encrypted raw restore, normal detach
and original Volume spec restored. Nine datasets total 542 verified blocks;
recovery scratch cleanup totals 1,886,146,560 allocated Linux bytes. Three native-
backup gaps remain. All 58 claim bindings/44 volume UIDs, three nodes, workloads
and unsuspended Flux survive. New HA data uses node space; refresh capacity
before platform pulls. [Exact proof](docs/DETACHED-VOLUME-NATIVE-RECOVERY-20261027.md).
The full goal remains active.

**October 27 native qualification:** actual unpacking passed for all thirteen
consumed official Longhorn candidate images using the exact production
containerd 2.4.2 binaries in an isolated controller instance. Every layer hash
and committed snapshot chain passed; no containers started or cluster resources
changed. The daemon exited normally and all 4,402,479,104 allocated scratch bytes
were removed. [Exact result, regeneration and limits](docs/LONGHORN-NATIVE-UNPACK-20261027.md).
Fresh production node capacity/cache/placement, remaining recovery and guarded
upgrade remain required. The full goal stays active.

**October 27, 21:47 UTC:** completed bounded controller cleanup recovered
27,804,061,696 allocated Linux bytes: 64 terminal publisher tool sets and six
stopped worker caches. Original source, recipes, OCI artifacts, failure receipts
and primary tools remain unchanged. Publisher cumulative cleanup is now
11,832,397,824 bytes. Native available space is 44,796,420,096 bytes; no Windows
recovery or node-space gain is inferred.
[Exact paths, retained exceptions and remaining work](docs/CONTROLLER-CLEANUP-20261027.md).
The full goal stays active.

**October 27, 21:24 UTC:** the eighth retained claim (`pihole/pihole-data-1`)
passed native NAS backup, independent stock-engine raw restore and normal
detach. All eight total 376 verified blocks; 1,261,604,864 allocated controller
Linux scratch bytes are reconciled. Four native-backup gaps remain. Three Ready
nodes, all 58 claim bindings/44 volume UIDs, workloads and unsuspended Flux
survive. [Exact recovery and limits](docs/DETACHED-VOLUME-NATIVE-RECOVERY-20261027.md).
No Windows disk recovery or completed platform upgrade is claimed. Full goal
active; current-writer recovery, supported upgrade and final IAB/fleet/security
acceptance remain.

**20:28 UTC:** qualified retirement of four old master build duplicates recovered
233,078,784 node Linux bytes, preserving all77,887 unselected source/failure/primary
entries plus a fully verified original compiled artifact on F. Cumulative node
cleanup is25,709,182,976 bytes. All58 claim bindings/44 volume identities, three
Ready nodes, workloads and unsuspended Flux remain healthy.
[Exact removal, retention and capacity](docs/MASTER-DUPLICATE-OUTPUT-RETIREMENT-20261027.md).

Ansible scratch is reconciled:20,480 controller Linux bytes removed. The latest
terminal Ingenium CI stage released149,778,432 further controller bytes; publisher
total2,246,676,480. No Windows recovery is inferred. The dated V1 image projection
clears its floor/margin by12,909,567 bytes; complete-profile placement, fresh native
cache/unpack, remaining recovery, supported upgrade and final security/fleet/IAB
acceptance remain. Full goal stays active.

**20:08 UTC:** seven retained claims now have full native NAS backups plus
independent stock Longhorn raw restores: all 303 blocks, unbacked zero regions,
complete encrypted sizes and headers verified. Original Volume specs and replica
UIDs survived normal detach. Fourteen Ansible prepare/apply invocations passed.
[Exact verification and limitations](docs/DETACHED-VOLUME-NATIVE-RECOVERY-20261027.md).

Removed 988,717,056 allocated controller Linux scratch bytes; no Windows/node
recovery inferred. Original NAS backups, source/failure witnesses and required
native tools remain. Five native-backup gaps remain, down from twelve. Fresh
health preserves all 58 claim bindings/44 volumes, three Ready nodes, available
workloads/unsuspended Flux and two actual RW replicas on all attached volumes.
Approved Windows public LAN root is present in CurrentUser/Root. Supported
Longhorn upgrade/capacity, remaining recovery and final IAB/fleet/security checks
are still open; full goal remains active.

**19:02 UTC:** the pinned Longhorn candidate passed Ansible and server dry-run
for 61 applicable resources with current `kubectl` ownership, no forced conflicts,
and all 51 existing UIDs/configurations unchanged. Encryption, two replicas,
`Retain`, resource settings and placement are preserved; namespace excluded.
No production upgrade occurred. [Evidence and remaining gates](docs/LONGHORN-UPGRADE-PREPARATION-20261027.md).

Including the mandatory share-manager pre-pull, the V1-node image projection
still lacks 196,805,633 master bytes. Full capacity/recovery and actual manager/
engine upgrade remain. Removed 12,288 controller scratch bytes and 299,556,864
bytes from two current successful publisher stages; cumulative publisher cleanup
is 2,096,898,048 bytes. All source/failure/data and older-copy exceptions remain.
The full goal remains active; final IAB/fleet acceptance is still required.

**18:47 UTC:** recovered another 561,950,720 allocated master Linux bytes after
NAS preservation and independent journal restore, plus full qualification of one
old public scanner duplicate. Cumulative qualified node cleanup is
25,476,104,192 bytes. All 58 claim bindings and 44 volume identities survive;
nodes/workloads/unsuspended Flux are Ready. Restore and Ansible scratch is
reconciled; all original source, reports, failures and required NAS archives
remain. [Exact paths, recovery and limitations](docs/MASTER-JOURNAL-AUDIT-CLEANUP-20261027.md).

The earlier core-image projection clears master's observed Longhorn floor by
91,642,879 bytes; complete-candidate headroom still lacks 1,412,084,737 bytes.
No fresh native unpack or platform upgrade is claimed. Recovery coverage,
component placement/capacity, owner hold, vendor/host exceptions and final normal
Seerr/YTPTube IAB/fleet acceptance remain. Full goal active.

**18:32 UTC storage check:** 3 Ready nodes without pressure, all 58 claim bindings
and 44 volume identities unchanged; all 28 attached volumes have two actual RW
replicas. Twelve claims still lack completed native Backup records; exact mapping
now distinguishes live writers, retained original sources and restore fixtures.
[Coverage and unresolved bindings](docs/LONGHORN-RECOVERY-COVERAGE-20261027.md).
This was read-only and does not claim completed application-data recovery.

**October 27, 18:15 UTC:** fresh encrypted backup, authenticated NAS copy and
actual independent offline etcd restore passed. All 2,801 keys and revision
10,442,118 retained the same logical key-history hash. Removed 213,725,184
allocated controller Linux bytes of raw recovery/Ansible scratch; retained
ciphertexts, source/failure evidence and one operational recovery tool.
[Exact evidence and limits](docs/FRESH-CONTROL-PLANE-RECOVERY-20261027.md).
Five more successful publisher stages released 748,892,160 controller Linux
bytes; cumulative publisher cleanup is 1,797,341,184 bytes. No Windows recovery
or node-space gain follows from these controller measurements.

Still required: application/detached-data coverage, master capacity and supported
Longhorn upgrade, security exceptions, final Seerr/YTPTube IAB and fleet
acceptance. No driver, image pull, placement or workload-limit change occurred
here. The full goal remains active.

**October27,16:51UTC checkpoint:** qualified master BuildKit retirement recovered
**258,555,904 allocated node Linux bytes**. All original contexts, locks, state,
logs, seals and failure evidence remain. All3 nodes,58 claim bindings and44
volume identities are healthy/preserved. Total qualified node cleanup is now
**24,914,153,472 bytes**. Ansible scratch is reconciled; unique source/refusal/
removal/health evidence remains. [Exact acceptance](docs/MASTER-BUILD-TOOLS-RETIREMENT-20261027.md).

Three additional successful CI stages released **449,335,296 controller Linux
bytes**, bringing publisher recovery to1,048,449,024 bytes. Source exports,
receipts, primary tools and the complete failed run remain. [Exact cleanup](docs/PUBLISHER-HEADROOM-20261027.md).

The dated image projection with the16:35 capacity observation still lacks
432,645,121 core-image bytes or1,936,372,737 complete-candidate bytes on master.
No driver, image import, floor or placement change occurred. Application/
detached-data coverage, fresh recovery, supported upgrade and final security/
Seerr/YTPTube IAB acceptance remain; full goal active.

**October27,16:05UTC cleanup checkpoint:** Ansible retired only the two qualified
master SDK copies and two old module-cache trees: **1,834,442,752 allocated node
Linux bytes**,112,961 verified entries. All77,881 protected source/archive/binary
entries retain original identities/hashes. Total qualified node cleanup is now
**24,655,597,568 allocated bytes**. All3 nodes,58 claim bindings,44 volume UIDs,
workload availability and unsuspended Flux readiness pass. Controller Ansible
scratch is reconciled:24,576 bytes removed; complete inventory, archived module
contracts and source/failure/removal evidence remain. [Exact checkpoint](docs/MASTER-GENERATED-INPUT-CLEANUP-20261027.md).

Separately, twelve terminal publisher tool exports and four empty directories
were removed: **599,113,728 allocated controller Linux bytes**. Sources, receipts,
primary tools and the entire failed publisher run survive; no retry was performed.
[Exact publisher reconciliation](docs/PUBLISHER-HEADROOM-20261027.md).

With fresh master capacity and the earlier dated image projection, core Longhorn
headroom still lacks642,360,321 bytes; the complete set lacks2,146,087,937 bytes.
This is not native unpack proof or a fresh cache inventory. Owner hold, recovery,
upgrade, vendor/host exceptions and final Seerr/YTPTube IAB/fleet gates remain.
The full goal remains active. No threshold, workload limit or placement change.

**October27 capacity audit:** complete authentication passed for all 14 reviewed
Longhorn images and 97 distinct layers. No payload was staged or imported.
Native cache/snapshot chains were read on all three nodes. The workers fit the
complete calculated image projection; master needs 2,529,797,121 more bytes for
core components or 4,033,524,737 for the complete set, preserving its existing
floors/reserve and margin. No upgrade, placement change or node deletion occurred.
One empty controller directory was reference-qualified and removed (4,096 Linux
bytes); 143 minimal source/input/failure/measurement paths remain. No Windows
recovery claim. [Exact audit](docs/LONGHORN-CAPACITY-AUDIT-20261027.md).

The next authorized step is qualification of exact old master SDK/module-cache
copies, not entire `_output` or source trees. Observed candidates total
1,834,442,752 allocated bytes; their complete provenance/reference/retention checks
and Ansible retirement have not run. Protected archives, historical binaries and
all runtime data remain. [Selection and safety contract](docs/MASTER-GENERATED-INPUT-CLEANUP-20261027.md).
Ingenium verification still holds driver and unrelated image/placement changes.
The full goal remains active; recovery coverage, upgrade implementation, vendor/
host exceptions and final Seerr/YTPTube IAB/fleet acceptance remain open.

**October27,13:04UTC:** recovered **10,936,221,696 allocated worker2 Linux bytes**
by retiring only two inactive legacy Plex trees after all 126,757 entries passed
independent restore/metadata checks and full NAS age authentication. The archive
was locked against writes/deletion throughout retirement. All unselected data,
original sources/failures, live claims, images, volumes, models and NAS media
remain. Restore and Ansible scratch is reconciled, including a qualified stale
listener cleanup; its original warning and corrected worker check remain.
Incremental 61-member recovery evidence passed complete authenticated NAS
readback. [Exact evidence and retained exceptions](docs/LEGACY-PLEX-PRESERVATION-20261027.md).

All 3 nodes are Ready without pressure, all 3 Longhorn disks schedulable, all 58
claims Bound and all 44 volume UIDs preserved. Attached engines have two RW
replicas. All deployments, daemonsets and Flux releases/kustomizations are Ready;
Ingenium is available under its separate owner. Worker2 Longhorn availability
is 35,546,726,400 bytes, with the 25% minimum unchanged. Total qualified node
cleanup is **22,821,154,816 allocated bytes**. No Windows recovery is inferred.

Windows public-root trust is confirmed. Longhorn remains 1.12.1. Fresh pre-upgrade
and application/detached-data recovery mapping, measured per-node image/unpack/
coexistence capacity, supported upgrade, vendor/host exceptions, final normal
Seerr/YTPTube IAB and final fleet reconciliation remain. Full goal stays active.

**October27,11:31UTC recovery checkpoint:** native Longhorn configuration backup
is Ready on the original NAS target. All 44 volume/PV/PVC chains are included;
complete readbacks/checksums/CRC and 20 parsed YAML documents pass. The dated
control-plane ciphertext also passed fresh NAS readback, full age authentication
and an actual isolated offline restore. The key-history hash, revision and all
2,568 keys match; all 46 original configuration files and required encryption
keys were checked in memory. No production restore, server start or application-
volume recovery is claimed. Both operations now have opt-in Ansible entry points.
Generated controller scratch/tool cleanup removed 305,160,192 allocated Linux
bytes; source, original archives and unique failed evidence remain.
[Exact acceptance, recovery inputs and limits](docs/LONGHORN-RECOVERY-QUALIFICATION-20261027.md).

Fresh cluster check: 3 Ready nodes without pressure, 58 Bound claims, all existing
deployments/daemonsets available and attached volumes healthy. Ingenium's owner
has copied data to the worker pair. Worker2 now reports Longhorn DiskPressure,
4,283,982,849 bytes below its unchanged scheduling minimum; this differs from
Kubernetes eviction pressure. No thresholds or replicas were reduced. Further
qualified cleanup must improve that headroom. Hold driver upgrades, new pulls
and volume changes during its initial app cutover. Longhorn remains 1.12.1;
fresh pre-upgrade/app/detached recovery, upgrade work, vendor/host exceptions,
final Seerr/YTPTube IAB and complete-goal acceptance remain open. Goal active.

**October27,10:21UTC checkpoint:** node cleanup is complete for the qualified
selection, recovering **11,884,933,120 allocated Linux node bytes** across four
operations. Tools/cache: 4,148,150,272 bytes; verified master media duplicates:
5,639,553,024 bytes; authenticated and independently restored worker2 closed
journals: 2,097,229,824 bytes. Required media now resides in the existing NAS
downloads path and was read by the unchanged live downloader pod. No images,
volumes, models, active journals, original Gluster/MySQL, other Plex data or
unique failure evidence were removed. No global floor/reservation/replica change.
[Exact media retirement](docs/LEGACY-MEDIA-RECOVERY-20261027.md),
[exact journal retirement](docs/ARCHIVED-JOURNAL-OFFLOAD-20261027.md),
[earlier tools/cache](docs/NODE-TOOL-CLEANUP-20261027.md).

All 3 nodes are Ready without pressure; all 57 claims are bound. All 43 original
Longhorn volume UIDs survive; the 27 attached volumes are healthy with two RW
replicas and 16 retained volumes remain detached. All 3 Longhorn disks now report
schedulable. Available kubelet filesystem bytes: master 24,755,986,432; worker1
109,987,729,408; worker2 27,218,767,872. Ingenium's owner corrected its measured
payload to 7,519,682,560 allocated bytes. Worker1 and worker2 clear that payload
plus 512 MiB filesystem overhead and 1 GiB operating margin above the unchanged
15% eviction floor; worker2's surplus beyond this budget is 733,161,267 bytes.
Master still does not qualify for this payload. Earlier larger payload estimates
are superseded. This is initial staging capacity, not a full-growth guarantee or
cluster-enforced reservation. Hold competing pulls/upgrade writes while its owner
checks actual two-node replica placement and consumption. Ingenium deployment
and application remain in their owner chat; BORTUS's hold is unchanged.

The matching Windows public root is installed in CurrentUser/Root following the
user's approval; no private key was imported. Full goal remains active:
Longhorn recovery/upgrade, final Seerr/YTPTube browser acceptance and final
security/source/data reconciliation remain. Known vendor/host exceptions persist.

**10:47UTC refresh:** Ingenium's owner has provisioned one new empty, detached
11 GiB volume. All original 43 volume UIDs remain, now 44 total and 58 bound
claims. Its stopped replicas are assigned to master and worker1, not the
qualified worker pair, and no application pod exists yet. The application owner
must verify corrected actual placement before copying; this chat changed no
volume, scheduling setting or application. All existing deployments/daemonsets
are available; 4 old failed diagnostic pods remain as evidence. The final
297,236-byte cleanup metadata packet passed full authenticated NAS readback
(SHA-256 `9fa00f5d92356716be0c9c826f85c7a59d63e198c2c965ce58e321c7d012e77d`).

**10:52UTC Longhorn preflight:** maintained Ansible inspection passes with zero
changes. All 28 attached volumes have two actual RW replicas; 16 volumes remain
detached. Twelve volumes lack a completed Backup CR in the current inventory,
ten of them detached, and no SystemBackup CR exists. This is a coverage gap to
reconcile with actual independent cold/NAS receipts, not proof that those
datasets were never backed up. No candidate image pulls, volume attachment or
upgrade mutations occurred. [Dataset map and remaining recovery gates](docs/LONGHORN-UPGRADE-DESIGN-20261027.md).

**October27,06:57UTC acceptance:** Unpackerr1.0 and restart pass original config/
native Secret/storage/integration checks, with the new web interface disabled.
Delivery's relay/account-drop fix is saved and applied. Charts main/validated/
live is `5b894f2491d0ca080d8e63cdb2a73050eb551878`; all33tests,30charts and31releases
pass.63/63runtime digests are audited; FlareSolverr's KEV and vendor/host exceptions
remain. All3nodes/57claims/31releases are healthy,27attached Longhorn volumes
have two RW replicas and16remain detached. Capacity/recovery/Longhorn upgrade and
final IAB are still open.579,760,128controller Linux bytes removed; cold backup
and4,220,116-byte metadata packet authenticated on NAS. No node/Windows recovery
is inferred. [Exact checkpoint](docs/UNPACKERR-V1-AND-DELIVERY-20261027.md).

**Latest checkpoint — October27,06:04UTC:** snapshot-controller8.7.0 is deployed
and verified, preserving all existing snapshots, storage, native Secrets and
unrelated workload/Flux/node identities. Two exact-digest replicas are Ready
with zero restarts;1Critical/46High→0Critical/2High on the unchanged feed.
Fresh read-only BORTUS coverage completes63/63runtime digest reports without
changing its held application. Windows public-root installation and idempotence
pass;60OS-store HTTPS checks pass in explicit request-only missing-CRL mode.
Default strict Schannel revocation still fails; final browser acceptance is open.

Cleanup removed1,679,360allocated Linux bytes with all unique/source/data/rollback
evidence retained. The3,861,620-byte encrypted checkpoint passed complete NAS
read-back authentication. Remaining: Longhorn capacity/recovery/upgrade,
Unpackerr1.0 compatibility, vendor/host exceptions and final reconciliation/IAB.
Goal remains active. [Exact checkpoint](docs/SNAPSHOT-AND-CLIENT-TRUST-20261027.md).

**Latest checkpoint — October27,04:43UTC:** the SMB sidecar patch is deployed
and separately verified. All14NAS bindings/credentials and12Helm resource UIDs
remain; seven new sidecars are Ready with exact IDs and zero restarts. Global
native Secrets, PVC/PVs, Flux and unrelated workloads match. Cleanup removed
270,336Linux bytes, retaining all unique source/data/recovery/failure evidence.
Fresh exact fleet coverage is62/63digests; BORTUS's held cached-image gap and
FlareSolverr's known-exploited Chromium finding remain explicit.

Snapshot-controller8.7is scanned but unapplied pending coordinated schemas/RBAC.
Longhorn still needs safe capacity and recovery prerequisites; replica relocation
alone cannot cover the measured shortfall. Client trust/final IAB and vendor
exception reconciliation remain open. The full goal stays active.
[Exact sidecar acceptance, capacity evidence and remaining work](docs/SMB-SIDECAR-UPSTREAM-PATCH-20261027.md).

**Latest checkpoint — October27,04:12UTC:** Flux2.10.0 is deployed and accepted.
Seven controllers are Ready/zero-restart, with exact image IDs; all protected
application, native Secret, claim/PV, Flux-specification and node identities match.
Fresh charts/source/Helm reconciliation passed, with BORTUS's hold preserved.
A fresh encrypted control-plane backup passed full NAS authentication.
Cleanup removed30,310,400Linux bytes; no Windows recovery is claimed.

The fresh fleet scan covers60of61runtime digests. BORTUS's cached image has
unknown current coverage; FlareSolverr's latest official image retains one known-
exploited Chromium CVE. Raw findings are not suppressed. Remaining platform/
sidecar remediation, vendor exception reconciliation, Longhorn capacity/recovery/
upgrade, client trust and final browser acceptance keep the full goal active.
[Exact acceptance and remaining limits](docs/FLUX-UPSTREAM-UPGRADE-20261027.md).

**Platform follow-up — October27,03:06UTC:** all14official Longhorn1.13.0
components are digest-bound and freshly scanned. Upgrade remains unapplied:
Longhorn's disk-scheduling floor fails on master and worker2, although all27
attached volumes remain healthy. Their respective shortfalls are3,969,410,049
and613,966,849bytes before any upgrade image pulls. No threshold/replica reduction,
image prune or data/source deletion was performed. Safe capacity recovery is next.
The candidate retains7Critical/215High package rows, with no CISA KEV matches;
raw results remain. Cleanup removed15,962,112Linux bytes and recovery metadata
passed complete authenticated NAS readback. The full goal remains active.

[Exact Longhorn candidate, live capacity constraint and retained evidence](docs/LONGHORN-UPSTREAM-REVIEW-20261027.md).

**Latest checkpoint — October27,02:50UTC:** Ruckus now runs from its owned
repository and existing Docker Hub route. Production and a distinct Flux restart
preserved all3,976original rows/accounts/native Secrets/storage and passed28routes
each,59source/configuration hashes, native bcrypt and real bot startup/SQL checks.
Private main/validated/live is `3a8de93a4034780519bac191bf4a02b4a4c96f96`.
All three migration-owned application image transitions are accepted; BORTUS's
intentional separate-owner production hold remains.

The exact image has0Critical,65High and no available fixed-version findings or
CISA KEV matches; all raw Debian residuals and the existing unauthenticated Ruckus
API finding remain explicit. This is not a clean-cluster assurance.
Cleanup removed3,585,335,296allocated Linux bytes, with exact paths/receipts and
authenticated NAS recovery retained. Three nodes,57claims, all30releases and all
Kustomizations are healthy;27Longhorn volumes attached healthy and16detached.
Remaining: platform security/reconciliation, Windows client trust, final IAB and
final fleet acceptance. The full goal stays active.

[Exact Ruckus source, security limits, data/restart checks and cleanup](docs/OWNED-RUCKUS-RELEASE-20261027.md).

**Latest checkpoint - October27, 01:15 UTC:** the personal site now runs from
its owned repository/existing Docker Hub route, on maintained Nginx1.30.6 and
jQuery4.0.0. Original site content and unrelated runtime/native Secret settings
are preserved. Production and a distinct Flux restart each passed84three-node
HTTP/trusted-TLS checks. Its22-package scan reported no CVEs. Private
main/validated/live is `1b66531bffd2fd7024a46d5e8686505d6ec8f137`.

Three nodes are Ready without pressure;57claims Bound, all30HelmReleases and
all Kustomizations Ready. There are43Longhorn volumes total:27attached healthy,
16detached. Earlier wording calling all43attached is corrected against the
stored snapshots. Four old failed diagnostic Pods remain intentionally preserved.

Cleanup removed418623488 allocated Linux bytes. Source/rollback/failure evidence,
runtime and minimal receipts remain; recovery metadata passed full authenticated
NAS read-back. Ruckus's owned release, remaining platform security, Windows client
trust and final IAB remain open. BORTUS's production hold remains separate.
The full goal stays active; this checkpoint is not full acceptance.

[Exact source, dependency fixes, runtime acceptance, cleanup and recovery](docs/OWNED-PERSONAL-SITE-20261027.md).

**Latest checkpoint - October27, 00:42 UTC:** the qBittorrent monitor now uses
its owned repository and existing Docker Hub publication route. Exact source,
remote digest/labels, all nine accepted script hashes, original native Secrets,
storage,12653notification bytes, real queue/VPN checks and a distinct Flux restart
passed. Its34-package scan reported no CVEs. Private main/validated/live is
`76d06d618bda73384ccb34e76aaf411db9b53192`; Actions was not used.

Worker1's available Brotli security fix is applied through the new finite Ansible
role. Actual rerun changed no installed packages or running services. All three
hosts report five Ubuntu Pro ESM Apps updates pending attachment; those remain
explicit exceptions. The fresh live cluster has three Ready/no-pressure nodes,
57Bound claims, all30HelmReleases/Kustomizations Ready,27healthy attached
Longhorn volumes and16detached volumes (43total). Four old failed diagnostic Pods remain preserved.

Cleanup removed391942144 allocated Linux bytes; original source, runtime,
backups/failure evidence and minimal receipts remain. Recovery metadata passed
full authenticated NAS read-back. Two owned releases (Ruckus and jtmb-dev),
remaining platform security, Windows client trust and final IAB remain open.
BORTUS's production hold remains with its separate owner. The full goal is active.

[Owned monitor, exact acceptance and cleanup](docs/OWNED-QBIT-MONITOR-20261027.md).
[Applied host fix and entitlement exceptions](docs/HOST-BROTLI-SECURITY-PATCH-20261027.md).

**Latest checkpoint - October27, 00:06 UTC:** server TLS now passes for all20
active migration-owned LAN hosts (60node/hostname checks), with18public checks
also passing. The stale Vault CICD/Portainer proxies and their unused generated
leaf certificate were retired by exact UID after verified NAS recovery; all
original definitions remain. Private main/validated/live is
`d79ee5f1b3935f87892bcfe5b4090ed3e31c5bbb`. Actions was not used.

Windows client trust remains unaccepted after an actual timeout; read-only
inspection passes and confirms the root is absent. Final-source Ansible
certificate verification and its zero-change rerun pass, excluding trust.
BORTUS's intentional release suspension remains; its prepared TLS binding was
passed to the separate owner without production authorization or an unsuspend.

Three nodes,57PVCs, all30releases and all Kustomizations are healthy. All attached
Longhorn volumes are healthy. Cleanup removed710791168 allocated Linux bytes /
3154paths; encrypted CA/unused-leaf recovery and metadata passed full NAS
authentication. Owned publication, platform/fleet security, client trust and
final IAB remain open. The full goal stays active.

[Exact server acceptance, exclusions, recovery and pending client work](docs/LAN-TLS-AND-LEGACY-PROXY-RETIREMENT-20261026.md).


**Previous checkpoint - October 26, 22:54 UTC:** Plex now runs the maintained
LinuxServer1.43.5.11079-ls330 image at the same application version. Original
accounts/watch state, all21 checked tables,3libraries, server identity, native
Secrets and storage passed production and distinct restart comparisons. All6
published routes passed. Fresh complete encrypted state and metadata passed
full authenticated NAS read-back. Private main/validated/live is
`929f182b15a7889ea21ae2382ca1caf2a9f28297`; Actions was not used.

Three nodes,57PVCs and all30releases are healthy. Cleanup removed534413312
allocated Linux bytes /2362paths. No third-party application derivative
transition remains;4High vendor Plex findings remain explicitly recorded.
Existing Docker Hub credentials were verified for the owned repositories,
resolving the earlier unverified-route assumption. Actual owned-source/image
publication, remaining platform/fleet security, trusted LAN TLS and final IAB
are still open. The full goal remains active.

[Exact Plex acceptance, recovery and exceptions](docs/UPSTREAM-PLEX-ADOPTION-20261026.md).


**Previous checkpoint - October 26, 22:29 UTC:** WordPress, its database,
Redis and phpMyAdmin are removed from the live stack and active charts at the
user's request. All four claims, eleven native Secrets, original data, backups
and the separately managed public certificate remain. The database/plugin
upgrade is canceled. Private main/validated/live is
`801f6b87cbc755454a5942a351c952fad9478155`; Actions stays disabled.

Three nodes, all 57 PVCs, all 30 releases and all attached Longhorn volumes are
healthy. Cleanup removed 533012480 allocated Linux bytes / 2348 paths. Recovery
metadata passed full authenticated NAS read-back. Plex, remaining platform/fleet
security, owned publication, trusted TLS and final IAB remain open; the full
goal is active. Historical checkpoints below describe their original scope.

[Retirement, preservation and evidence](docs/WORDPRESS-RETIREMENT-20261026.md).


**Cloudflare notice assessment — October 26, 21:42 UTC:** read-only inspection
identified no cloudflared connector in Kubernetes, on the three cluster hosts,
or in inspected Windows/WSL services/processes/Docker containers. Seven declared
public TLS chains use Let's Encrypt/ISRG; all21 public-host/node handshakes
verified. The69 LAN/local-host handshakes failed strict verification against
Traefik's existing self-signed default certificate. No observed chain named
eMudhra/emSign. Account-wide Tunnel versions/replicas, any NAS connector and
actual Tunnel-origin mappings remain unknown; local absence does not close that
assessment. No software, workload, certificate, credential or TLS policy changed.

[Scope, evidence and remaining access gap](docs/CLOUDFLARED-NOTICE-ASSESSMENT-20261026.md).

**Previous checkpoint — October 26, 21:30 UTC:** CoreDNS now runs official
1.15.0 / Go1.27.3. Both replicas passed TCP/UDP queries through the DNS Service
and each Pod, including exact Kubernetes and WordPress database Service answers.
The Corefile, Service, Deployment identity and resource settings are unchanged.
The actual Ansible playbook rerun passed with zero changes. Raw scanner findings
are retained; eleven old-version High matches were attributed using the actual
binary, upstream release tag and commit, explicitly as a version inference.

Three nodes, 56 PVCs, all releases and all attached Longhorn volumes are healthy.
CoreDNS recovery metadata passed full authenticated NAS read-back. Its cleanup
removed **278528 allocated Linux bytes /7 paths**; owned temporary probes were
retired after their complete evidence was preserved. App charts remain at
`4fb19f9ec5620b3605a28c126e07c897004a78a9`; Actions remains disabled.
Plex, WordPress MySQL/plugin updates, remaining platform/fleet and owned-source
publication, trusted TLS and final IAB are still open. The full goal is active.

[CoreDNS evidence, inference and recovery](docs/UPSTREAM-COREDNS-ADOPTION-20261026.md).

**Previous checkpoint — October 26, 21:06 UTC:** WordPress now runs the official
7.1.3 / PHP8.3.36 Apache image. Production and a distinct Flux restart preserved
all 5662 file entries, all 12 database tables, the existing user/permissions,
native Secrets, PVC/PV/Service identities and all 12 site/API routes. All 3338
checked core files match WordPress's published7.1.3 checksums. Fresh complete
file and application-SQL backups and recovery metadata passed full authenticated
NAS read-back. Main/validated/live is
`4fb19f9ec5620b3605a28c126e07c897004a78a9`.

Three nodes, 56 PVCs and all releases are healthy. Cleanup removed **535019520
allocated Linux bytes /2346 paths**, retaining originals, required backups,
unique failures and all prior exceptions. Plex is the remaining application
derivative transition. WordPress's MySQL5.7 database and plugin updates,
CoreDNS/platform/fleet work, owned publication, trusted TLS and final IAB remain
open. The official WordPress image retains2Critical/160High vendor scan rows,
including one fixable High. The full goal remains active; Actions stays off.

[Exact WordPress acceptance, recovery and limitations](docs/UPSTREAM-WORDPRESS-ADOPTION-20261026.md).

**Previous checkpoint — October 26, 20:38 UTC:** Ruckus now uses official
MySQL 8.4.13 on a separately restored Longhorn claim. All 3971 original rows,
original application accounts and native Secrets remain; the bot added one
normal record. A distinct database restart passed the same complete row check,
the bot's deployed MySQL client reconnected, and all 28 API/dashboard routes
passed again. Original and prior recovery claims remain intact. The fresh full
cold backup and final recovery metadata passed complete authenticated NAS
read-back. Private main/validated/live is
`7383784971f0e1a0839631cf0104f8792d62f9f4`.

Three nodes, 56 PVCs and all releases are healthy. There are 42 Longhorn volumes:
30 attached/healthy and 12 detached; earlier prose incorrectly described the
total volume count as attached. New publisher cleanup removed **1065930752
allocated Linux bytes / 4680 paths**, with exact retained exceptions recorded.
Two application derivative transitions remain: Plex and WordPress. WordPress's
database, platform/fleet updates, owned publication, trusted TLS and final IAB
also remain open. The official MySQL image still has two Critical and 33 High
vendor scan rows; the full goal remains active and GitHub Actions stays off.
[Source, proof and production sequence](docs/UPSTREAM-RUCKUSDB-MIGRATION-20261026.md).


**Previous checkpoint — October 26, 18:16 UTC:** maintained Threadfin 3.4.0 replaced
xTeVe through the private local-validation → validated → Flux pipeline. Complete
comparison passed in production and after a distinct restart: 108 original
mappings, 29 active channels, settings, authentication, tuner identity, native
Secret and existing PVC/PV/Service identities remain. All 27 published node
routes passed. Original state, both authenticated NAS cold backups and the
failed first trial remain intact; the corrected state uses a separate directory.
Private main/validated/live is `0de054992e5938543855d099efc1e484feee72be`.
Three nodes, 55 PVCs, all releases and 41 attached Longhorn volumes are healthy.
Cleanup removed **1065947136 allocated Linux bytes** across 4683 paths, preserving
source, unique failures, required backups and all earlier exceptions. Recovery
metadata also passed complete NAS read-back/authentication. Three application
derivative transitions remain: Plex, ruckus-db and WordPress. Eight High vendor
scan rows, platform/fleet security, owned publication, trusted TLS and final IAB
remain open. The full goal is active and GitHub Actions is disabled.

[Delivery, preservation and limits](docs/UPSTREAM-THREADFIN-ADOPTION-20261026.md),
[exact cleanup and retained exceptions](docs/TASK-OUTPUT-INVENTORY.md#threadfin-checkpoint-reconciliation-october-26-1816-utc).


**Previous checkpoint — October 26, 16:13 UTC:** maintained qBittorrent 5.3.0 /
libtorrent 2.1.2 passed complete 232-torrent / 455-file, preference, native
identity and authentication comparisons through an independent Flux restart.
The original disk queue default was restored with a guarded native API helper
and opt-in Ansible playbook; the monitor now checks forwarded ports every ten
seconds. All 20 UI/access-control routes passed, the client is connected and
uploading, and both recovery archives passed full NAS read-back/authentication.
Private main/validated/live revision is
`902dae6c51b25ed2f1dd313511ed1841c618c385`. Three nodes, 55 PVCs, all releases
and 41 attached Longhorn volumes remain healthy. Cleanup removed **710959104
allocated Linux bytes**, retaining exact source, original/rollback data and all
unique failures. Four application derivative transitions remain: Plex, ruckus-db,
WordPress and xTeVe. Two High vendor package rows, platform/fleet security,
owned publication, trusted TLS and final IAB remain open. The full goal remains
active and GitHub Actions is disabled.
[Verification, recovery and limits](docs/UPSTREAM-QBITTORRENT-ADOPTION-20261026.md),
[exact cleanup and retained exceptions](docs/TASK-OUTPUT-INVENTORY.md#qbittorrent-checkpoint-reconciliation-october-26-1613-utc).

**Previous checkpoint — October 26, 15:03 UTC:** official Pi-hole 2026.10.0 /
FTL v6.8 passed complete query/configuration/native-resource preservation,
authenticated API, 16 TCP/UDP DNS probes and 27 web routes through a distinct
Flux restart. Private main/validated/live revision is
`78e1d1f902178c0a1e64faa54599610aafd3a671`. All 9069270 original queries and
the first live checkpoint remain; the restarted database has 9069623 queries.
All 166 configuration values and original password/static data remain. One
expired session and one run-scoped RATE_LIMIT warning follow verified native
startup behavior; full originals remain in the authenticated backup. Both
recovery archives passed complete NAS read-back/authentication. Three nodes,
55 PVCs, all releases and 41 attached Longhorn volumes are healthy. Cleanup
removed 1408999424 allocated Linux bytes with exact paths and retained exceptions.
Five application derivative transitions remain. Pi-hole still has 13 High vendor
findings; platform/fleet security, owned publication, trusted TLS and final IAB
remain open. The full goal is active; GitHub Actions remains disabled.
[Acceptance and remaining limitations](docs/UPSTREAM-PIHOLE-ADOPTION-20261026.md),
[exact cleanup and exceptions](docs/TASK-OUTPUT-INVENTORY.md#pi-hole-checkpoint-reconciliation-october-26-1503-utc).

**Previous checkpoint — October 26, 14:00 UTC:** official Vaultwarden 1.37.4
Alpine passed complete same-release data/file/native-resource/route acceptance
and a distinct Flux restart at private main/validated/live revision
`aee71f041ad69e5bf16fb9e2f6f1c55dbebe6f55`. All 29 tables / 86 rows, the
existing account, 24 encrypted items, four devices, original RSA material and
file ownership remain. Both recovery archives passed complete NAS read-back
and authentication. Three nodes are Ready, 55 PVCs are Bound, all releases are
Ready and 41 attached Longhorn volumes are healthy. Cleanup removed 534106112
allocated Linux bytes; exact source, rollback, failures and recovery evidence
remain. Six application derivative transitions remain, alongside platform/fleet
security, owned publication and final IAB. The official artifact still has three
High package findings; personal Vaultwarden login/client sync and trusted TLS
are not credited. The full goal remains active and GitHub Actions stays disabled.
[Acceptance and limitations](docs/UPSTREAM-VAULTWARDEN-ADOPTION-20261026.md),
[exact cleanup paths/exceptions](docs/TASK-OUTPUT-INVENTORY.md#vaultwarden-checkpoint-reconciliation-october-26-1400-utc).

**Previous checkpoint — October 26, 13:16 UTC:** maintained Tautulli 2.18.2-ls249
passed data/API/routes and a distinct Flux restart at private main/validated/live
revision `be08b5035e5861320a98aea0a420711378baafa5`. All 16 accounts and every
original history/media/metadata row remain. A real playback completion added one
history record, which persists through restart; original custom choices and all
canonical configuration/credential values passed the declared source mappings.
Native Secrets, original storage/resource identities, Plex connectivity and 27
route checks passed. Both recovery archives passed full NAS read-back and
authentication. Current health has 3 Ready nodes, 55 Bound PVCs, 34 Ready releases
and 41 healthy attached Longhorn volumes; two old diagnostic failures are retained.
Cleanup removed 534061056 allocated Linux bytes; source, rollback, recovery and
unique failure evidence remain. Managed-command sentinels stay under the same
root because their exact regeneration and inactive-handle checks are unresolved.
[Acceptance and remaining findings](docs/UPSTREAM-TAUTULLI-ADOPTION-20261026.md),
[cleanup paths and exceptions](docs/TASK-OUTPUT-INVENTORY.md#tautulli-checkpoint-reconciliation-october-26-1313-utc).
Seven application derivative transitions remain. Tautulli still has 7 High vendor
findings; full fleet/platform security, owned publication and final IAB are open.
The complete goal is active. GitHub Actions is disabled; delivery remains local/Flux.

**Previous checkpoint — October 26, 05:00 UTC:** official Mealie 3.29.0 passed
backend/state/restart verification at private main/validated/live Flux
`271bfc5f40c7c8761f75c730eba3ea0732894185`. All original files/ownership, three
users and credential rows, 33 recipes, 330 ingredients, ratings, cookbook filters
and last-made history passed the declared vendor transformations. All 69 tables /
860 rows, native Secrets, storage/resource identities and nine routes matched on
a different Pod. Cold production state and distinct qualification/recovery
evidence passed complete NAS read-back/authentication. The legacy UID/GID is
preserved through direct vendor startup with only the needed file-access
capability; initial startup/observer failures remain recorded. Three nodes,
55 PVCs, 34 HelmReleases and 41 attached Longhorn volumes are healthy.
Eight third-party derivative transitions remain. Selected vendor findings are
8 Critical / 240 High / 336 Medium / 264 Low / 24 Unknown, including 35 fixable
Critical/High rows. Whole-fleet security, owned publication, existing TLS
limitations and final IAB remain open; the full goal is active and incomplete.
[Exact acceptance and remaining limitations](docs/UPSTREAM-MEALIE-ADOPTION-20261026.md).
Cleanup removed 2738618368 allocated Linux bytes; original data, source and
failure/recovery evidence remain. The new production session-signing file passed
separate authenticated NAS recovery. [Exact paths/exceptions](docs/TASK-OUTPUT-INVENTORY.md#mealie-checkpoint-reconciliation-october-26-0530-utc).
The private charts repository's Actions setting is directly verified disabled.

**Previous checkpoint — October 26, 03:47 UTC:** official Jackett 0.24.2910 passed
backend/state/restart verification at private main/validated/live Flux
`fd0b167de8923e46aeeccece5a783522e65fef90`. All 27 protected files, six indexers,
authenticated capabilities, nine routes, native Secrets and original storage/
resource identities passed. The original 1337x download preference survives
startup after a guarded, authenticated-backup-first repair. Both failed checks
and all original snapshots remain. Complete state, pre-repair configuration and
recovery metadata passed NAS read-back/authentication. Three nodes, 55 PVCs,
34 HelmReleases and 41 attached Longhorn volumes are healthy; the two earlier
failed Seerr diagnostic Pods remain protected evidence.
Nine third-party derivative transitions remain. Jackett's current vendor findings
are 2 High / 2 Medium / 44 Low, including two fixable High rows still in the image.
Cleanup removed 290816 allocated Linux bytes; no Windows recovery is claimed.
[Exact acceptance](docs/UPSTREAM-JACKETT-ADOPTION-20261026.md),
[cleanup and retained exceptions](docs/TASK-OUTPUT-INVENTORY.md#jackett-checkpoint-reconciliation-october-26-0347-utc).
Owned-image publication, whole-fleet security, trusted TLS and final IAB remain
open. The full goal and mandatory storage/delegation/cleanup contract are active.

**Previous checkpoint — October 26, 02:22 UTC:** Homepage 2.7.0 is accepted for
backend/state/restart behavior through private main/validated/live Flux
`fc13b77609f8f21ce63c93e5895c86237d8e04d7`. Configuration, native Secrets,
RBAC, original storage/resource identities and services/bookmarks/widgets API
results matched before/after/on a different Pod. Complete state and metadata
backups passed NAS authentication/read-back. Final checks found all three nodes,
55 PVCs, 34 HelmReleases and desired workloads healthy. Ten third-party derivative
transitions remain. Current revalidated scan: 6 High / 11 Medium / 1 Low,
five High package fixes absent from the vendor image. The original mismatching
advisory input is preserved; its verified replacement and final full hashes pass.
Existing generated self-signed TLS, owned-image publication, whole-fleet review
and final IAB remain open. Cleanup removed 1150976 allocated Linux bytes.
[Exact checkpoint](docs/UPSTREAM-HOMEPAGE-ADOPTION-20261026.md),
[removed paths and retained exceptions](docs/TASK-OUTPUT-INVENTORY.md#homepage-checkpoint-reconciliation-october-26-0222-utc).
The full goal remains **active and incomplete**.

**Previous checkpoint — October 26, 01:41 UTC:** the four static sites use official
Nginx 1.30.6 Alpine Slim at private charts main/validated/live Flux
`0ed2ad27ce0a32055c37c3e2d4d22026535a9b15`. All 480 files / 413835995 bytes,
complete configs, native Secrets, storage/resource identities and 70 route/asset
checks matched before, after and on different restart Pods. All four complete
cold backups and encrypted recovery metadata passed NAS authentication/read-back.
All three nodes, 55 PVCs, 34 HelmReleases and desired workloads are healthy;
attached Longhorn volumes are healthy. The image's fresh 21-OS-package scan had
no findings; whole-fleet security acceptance remains open. Eleven third-party
derivative transitions, owned-image publication and final IAB remain required.
Cleanup removed 954368 allocated Linux bytes; required evidence/data is retained.
[Exact acceptance and limitations](docs/UPSTREAM-STATIC-SITES-ADOPTION-20261026.md),
[exact cleanup and exclusions](docs/TASK-OUTPUT-INVENTORY.md#static-site-checkpoint-reconciliation-october-26-0143-utc).
The existing five-milestone goal is **active and incomplete**. Older dated
checkpoint states below remain historical, not current revision assertions.

October 26, 00:20 UTC: phpMyAdmin now runs the official 5.2.3 Apache image.
Native login/logout, all 3 published routes, the configured SQL account/grants
and all 12 WordPress tables matched before, after and on a different restart Pod.
The original MySQL Pod, credentials and data claim were unchanged. Encrypted
recovery metadata passed NAS full read-back and authentication.
[Exact acceptance and unresolved vendor findings](docs/UPSTREAM-PHPMYADMIN-ADOPTION-20261025.md).
Private charts main/validated/live Flux is
`4e792ea690e2cbda21168510051345f865c47421`. All 3 nodes, 55 PVCs, 34 HelmReleases
and desired workloads passed the 00:17 health check; attached Longhorn volumes
are healthy. There are 15 third-party derivative transitions remaining. The exact
phpMyAdmin vendor digest's prior scan reported 8 Critical/131 High finding rows,
including 11 with package fixes; its database is older than 24 hours now. This is
backend/ownership acceptance, not security acceptance. Fresh vendor vulnerability
review and final IAB remain open; no bespoke third-party patch was rebuilt.
Cleanup removed 4096 allocated Linux bytes from one empty scratch directory,
retaining all recovery originals, sources and failure evidence. The goal is active.

**October 25 scope correction:** use maintained upstream releases for third-party
services; no further bespoke derivative image maintenance. Owned image changes
require repository-backed provenance and an approved publication path. Existing
derivative deployments and archives remain preserved for safe transition and
recovery. Actions stays off. The owned-image publication path is unresolved.
[Revised objective and supported goal readback](docs/REVISED-GOAL-20261025.md).

**The revised full goal is saved and active.** Cleanup and verified SMB handling
passed the October 25 20:23 UTC health gate. The goal is not done.
[Supported tracker readback](evidence/revised-goal-readback-20261025.json).
This source checkpoint is isolated from BORTUS
application development. Facts below come from the retained public maintenance
receipt, latest recorded progress `2026-10-24T02:46:45.685374+00:00` and its later
acceptance blocks. Historical failed/pre-cutover fields in that chronological
receipt remain preserved; the accepted checkpoints below take precedence.
Later root-executed live checks are recorded in the dated acceptance blocks.
Early pending/failed entries remain historical and do not supersede those blocks.

## Verified checkpoints

- October 25: Ruckus same-image HA recovery passed fresh full-state, SQL,
  after/restart and existing two-replica checks. The bot is resumed through Flux
  `758ba4c`; both claims and all failed evidence remain. The newer bot candidate
  is undeployed. [Exact execution ledger](docs/RUCKUS-HA-RECOVERY.md).
- October 25 artifact cleanup: 47 controller-verified node OCI transfer copies
  removed, reclaiming 6,303,870,976 allocated bytes. All controller originals
  remain. Twenty-six recovery archives (11,155,870,024 bytes) now have full
  checksum/read-back/age-authentication proof on the dedicated SMB backup folder;
  encrypted companion metadata is also copied and verified. No NAS media or
  Kubernetes SMB CSI volume was removed. Further generated-state cleanup is
  recorded separately when complete.

- All three nodes recovered Ready/uncordoned without pressure, running kernel
  `5.15.0-198-generic` and independent containerd `2.4.2`. Original frozen recovery
  confirmed 30 Longhorn volume UIDs, 54 Deployment UIDs and seven DaemonSet UIDs.
  Later post-app health records 30 healthy attached volumes and zero unavailable
  Deployments/DaemonSets. No Longhorn threshold/failure-metadata bypass occurred.
- Encrypted control-plane/configuration backup authenticated in full; fresh
  online off-node Longhorn checkpoint retained. A full disaster-recovery restore has not been performed and is not implied by
  archive authentication; the separate BORTUS recovery goal is not resumed. Worker1 ext4 filesystem grew within the
  existing partition/LV; no partition/LV changes occurred.
- Traefik 2.11.60, FlareSolverr 3.5.2 and whoami 1.12.0 have prior functional/route
  evidence. Their remaining security findings are open. Flare derivative run `40055919730` initially failed; its corrected attempt 2
  succeeded at source `613f90f`, artifact `12545656757`. Both attempts remain
  preserved. Root owns reception/scanning; no clean scan or rollout is claimed.
- Radarr 6.4.4.10685 retained API movie/history/config fingerprints, original
  SQLite Users fields, restart persistence and routes. Sonarr 4.0.20.3014 retained
  155 series/14,728 episodes/5,319 episode files/13,099 history rows and Users.
  Bazarr's source-proven default cleanup has a separate normalization proof;
  its after/restart qualification passed. Their complete UI workflows remain
  separate acceptance rather than implied by backend checks.

## Seerr: production cutover and backend acceptance passed

Accepted CI run `40048938336`, source
`e970316ce8ba23d4b1f61f7f0a8b2126de6d3fb6`, runtime
`docker.io/library/seerr-security-20261023@sha256:7bf03e8c4433460c0d93f789da56db457e3484412c448997102885af185db93c`.
The exact image scan recorded 0 critical/1 high without an available fix in the
pinned snapshot. All-node preload and native runtime qualification passed.

All six original accounts' credential/permission fields and all eight history
tables survived. Original settings initially matched literally; two later
source-proven runtime scan-clock advances have an independently bound proof.
After-cutover and new-Pod restart preservation passed, with Arr tag proof retained.
Browser login/Plex/permission/history workflow acceptance is still open.

- After receipt SHA256: `f101f1357799b315e7a3950b4d59540f9112bf5234e0b8958898817740e17146`
- Restart receipt: `dd427a21312153443ed1dcd157cadf89d3837224ee8a56265f9e3734d1fc6375`
- Arr tag proof: `7c7caa6586b8bf49c90e0a7c12afade8e2877fbea2385fe5826300a3e0fd4ab4`

## YTPTube: real retrieval, legacy preservation and restart passed

Accepted private CI run `40052586445` at
`3959595f3a6b1136472edca816e93cfe2eb7edfb`; OCI runtime root
`sha256:7c637f7e9cadf6f7def2243b517ff6101354287e17f9aebed8b0aa386fd1b754`.
The exact scan recorded 1 critical/68 high, all without available fixes in the
pinned snapshot; the prior four fixable installer findings were removed by
removing complete install-only code, without suppressing the analyzer/SBOM.

The actual application retrieved a five-second YouTube sample, 110,645 bytes,
H.264/AAC at 144p. The same media/history persisted in a new Pod. Seven legacy
files totaling 618,241,982 bytes remained unchanged after reobservation. Original
PVCs/NAS files and cold backups remain; normal UI login/playback/download workflow
acceptance is still open.

- Sample receipt: `4ef85843a9368beda9442d98616c969a2cc816b9da19900e9192601915f5bb70`
- Media SHA256: `7e05e92ad9b008d22990cfdc69f18f7023f7fc9bc6e0583739ead1f7b6adc457`
- Restart receipt: `13fd97d6f485f7c98abdbdaf3580ecc63d2da8c14d481336582a2bddf2d5320d`
- Legacy reobservation: `3dd6c77cdc5a5573e98f1ae3e9c758114e2893affcdd7e1cc428bacbe4e2036d`

## Routes and remaining security work

Chart commit `22dd5a2c816c37cc73fb17508bb2ae98720cceb7`, validation run
`40055143704`, restored 12 tested routes through all three nodes. Media HTTPS
certificate verification passed; TLS verification was not disabled. Route proof:
`8d2e02f891098298ed86c92e524fe0a7552f45b10958aa32e0069e943e9fe38d`.

The original audit covered 67 runtime image digests. That coverage is not a
clean-cluster verdict or proof of absence of unknown zero-days. Remaining work:

| Scope | Concrete next work / unresolved gate |
|---|---|
| FlareSolverr 3.5.2 | Patched derivative adopted through Flux; exact scan and native browser/version/route checks passed, with 4 critical/193 high unfixed residual rows |
| Tautulli 2.18.2 candidate | 68 recorded fixable critical/high rows; Debian/Python attribution patch, complete cold config/SQLite backup and history/account/notifier compatibility |
| Vaultwarden 1.37.4 | Seven available OS fixes adopted; whole cold backup and complete SQL/file preservation passed before and after restart. Public route restoration in progress; personal login/client sync remain unverified. Existing2FA/org/Sends counts are zero. |
| Unpackerr 0.16.1 candidate | Five linked Go findings: reviewed same-source Go 1.27.3/x/net 0.60.0 rebuild and extraction-policy compatibility |
| Pi-hole | Prepared same-app OS derivative; DNS-critical config backup and UDP/TCP DNS/API/metrics checks before adoption |
| Plex | Resolve actual app/bootstrap/channel versus immutable image; 15 recorded OS high rows and machine-identity/library/transcoding preservation |
| Other inventory | Source/derivative review or major migration for Homepage, MySQL/WordPress, xTeVe/phpMyAdmin, nginx/Redis/exporter/Gluetun; coordinated infrastructure trains |
| Jammy kernel | Recorded CVE-2026-98260 remains unresolved; preserve official fix availability evidence and revisit supported patch when available |
| Jackett runtime candidate | Existing static artifact/dependency applicability review is distinct from a live adoption and unsuppressed exact scan result |
| BORTUS image/release | Separate source owner; this maintenance branch neither resumes nor publishes it |

Full browser acceptance, final complete-inventory residual disposition and final
cluster/application health review are required before completing the goal.
All repeatable source entrypoints are listed in the
[maintenance README](k8s-rewrite/ansible-playbook/README.md). Secret values,
private receipts/keys, encrypted archives, OCI artifacts and runtime binaries
are deliberately outside this branch.


## Prepared exact cert-manager security patch scan

Official1.21.3 is available within the running1.21 line; it fixes the published
Go/x/net/trust and next-private-key ownership issues. The exact five-image
upstream-registry scanner is prepared under the existing W1 resource bounds,
with no application/Secret/CRI/deployment access. Its setup, actual five scans,
residual review and existing-owner Flux patch are not yet accepted or executed
by this source-only change. The full goal remains active.


## FlareSolverr exact Python/OS artifact scan, 03:44 UTC

Run `40058492329` at private charts source `5968b8f9c2ae0b45495fde6539f976fbc71a5bc3`
built artifact `12546303370`. The authenticated OCI archive SHA256 is
`db6315339f46a96d02d80bac4687de6929b1b900b640d1c9a146e54570209a7e`;
runtime manifest is
`sha256:29a981aec497ec47ccc25d67309c404593992a465501632e115010282ef61ec7`.
Actual scan `flaresolverr-f85f4bc513b5` finished successfully with 4 critical,
193 high, 300 medium, 373 low, six unknown and zero fixable critical/high rows
in the frozen database. Results SHA256:
`1f1895c34b93774573fb598dc69ee6419f375551ed9c4f41a3f456e523902492`.

This supersedes the earlier pending-artifact entry only. Preload, rollout, real
browser request, route and restart acceptance are separate and still open.
The goal remains active.


## FlareSolverr production acceptance, 03:53 UTC

Private charts commit `e7aad9893d9823aae489483e8fdba0dc94418c65` passed
validation `40059981764` and reconciled through Flux. The same Deployment and
HelmRelease UIDs now run the scanned immutable derivative in new Pod
`910adb88-cce7-4101-a864-386d73c1b091`. Native LOG_LEVEL/TZ references and
25m/64Mi requests remain; inherited legacy envFrom is cleared.

`qualify-flaresolverr.py` passed on the actual master: nonroot UID1000, exact
Python package versions, Chromium/ChromeDriver both 156.0.8078.47, version3.5.2
through all three node routes, and a real browser `request.get` to
`https://example.com/` returning HTTP200 with the expected page. No cookies or
page contents are retained. Receipt SHA256:
`ddc96a6f0efe73e246ef2b07f02698aa95bc7d782c3113958dfdd1c625c3cf0f`.
The 4 critical/193 high residual rows remain explicitly unfixed in the retained
database; application acceptance is not a clean-cluster verdict.


## Cert-manager1.21.3 adopted through Flux

Charts commit `09a8d9f158eb4ce780915c3a4f33863afc03a2a2`, successful validation
`40063040565`, selected the reviewed official chart and five image pins. The
actual full scan batch completed with no critical/high findings and four
unfixed unknown `GO-2026-5932` rows; its earlier partial attempt is preserved.
All three controllers are Ready with exact runtime digest bindings.

All six original CRD UIDs/stored versions and all original CRD specs remain,
except the single reviewed additive Certificate ARI certID field. Certificate
and ClusterIssuer UIDs/specs/readiness remain; webhook UIDs/CA bundles match.
Server-side dry-run admission and unchanged verified HTTPS certificates across
all three nodes passed. Adoption receipt fingerprint (SHA256)

`17dbb82fbb54e6905ae4d623da7a8ee743201a86dcb1329a336194d6fadbd276`.

The maintenance source is now published as draft PR29 at commit `c0c19123`,
with all15 playbook syntax checks and the exact146-file credential scan passed.
It is source only; application Actions remain disabled and the separate BORTUS
release is excluded. This checkpoint does not complete the full goal.

## Goal tracking and Vaultwarden restart, 05:37 UTC

The tracker is active for the full Seerr/downloader/security/Ansible/Flux scope,
including final implementation and browser acceptance. No duplicate goal was
created and no checkpoint was marked complete.

Vaultwarden1.37.4 now runs the scanned immutable derivative. Its authenticated
whole cold archive is retained. Both initial-start and new-Pod restart comparisons
preserved all28original tables,24vault items, oneaccount/fourdevice records and
the original RSA file, permitting only four reviewed additive vendor migrations.
Restart receipt SHA256:
`997ab1c8964281cfb482d51b1f5e75e75b11cf1ab0d32b07951e929b8be12c5b`.

The new Pod also passed version1.37.4, alive/config/web-root200 and anonymous
sync/profile401 checks. Observation fingerprint (SHA256):
`a57d84b0398d63c16c9ec80e03e4458b06605928ac3efc3b402d56121b369549`.
Personal account login and client sync remain unverified; no account or key was
reset. Public route restoration passed private charts validation40067096633 at
commit `05e1c8a1debe35bf318b544f7808847d5fb0ba59` and reconciled through Flux.
All24HTTP checks (existing ingress and published service through each node)
passed, including the401 boundary. Route observation fingerprint (SHA256):
`7623ca34e37eb583c71d61dbfdc9607b8b416819a47e6a83bf90c67adc0945ec`.
These are HTTP checks; verified LAN TLS is not claimed. The original Deployment,
HelmRelease, PVC, native references and resources remain. The first documentation
wording caused a public receipt fingerprint to match the credential scanner;
that CI attempt refused safely. The wording was corrected without an exclusion
or change to the scanner, and the subsequent complete pipeline passed.

## Exact core scans and Tautulli image work, 05:50 UTC

The separate16th opt-in playbook completed exact official etcd3.7.3/CoreDNS1.14.7
scans using the already verified public input snapshot. Etcd has0critical/high
and5unknown rows; CoreDNS has22high,22medium,1low and3unknown. Available compiled
Go/module fixes and pseudo-version attribution require further CoreDNS work.
Neither live component has been changed. See[core scan evidence](docs/CORE-PATCH-SCANS.md).

The Tautulli build selector/receiver/stager/scanner/preloader now support the
seventh service without changing resource or publication bounds. The first
private build retained its original failure artifact: runtime linkage checking
incorrectly included the official ET_REL SDK link object. Its exact primary
digest/header were independently verified; the corrected source still checks
all81runtimeELFs and retains all82objects. A new build is running at source
`cea9327b74c30fd4e138cca54856befb8a63dcc3`; no Tautulli rollout is claimed.

## Local delivery replaces GitHub Actions

The user explicitly instructed “stop using github actions” and “stop asking
questions. finish the goal.” Private charts Actions was disabled and verified
`enabled:false` on October24. New builds and chart validation/promotion move to
the local workflow, preserving immutable artifacts, existing resource limits,
all validation checks and Flux deployment. Completed historical CI artifacts and
their original evidence remain valid and retained. No further billing action or
question is needed from the user. This supersedes earlier Actions instructions.


## Etcd3.7.3: live patch and post-backup accepted

The exact official digest, membership/frozen revision HashKV, original data
folders and original workload/PVC/PV/Longhorn identities passed the protected
patch receipt. A new encrypted snapshot plus all46 configuration files was fully
authenticated off-node at23:14UTC. All3 nodes,54 Deployments,7 DaemonSets and
attached Longhorn volumes were healthy in the fresh observation. Details and
receipt fingerprints are in [ETCD-STATIC-PATCH.md](docs/ETCD-STATIC-PATCH.md).
No independent restore or full-goal completion is claimed. The remaining
application work continues through local validation -> validated -> Flux;
GitHub Actions is disabled by the user's current instruction.

## October25: local delivery and application acceptance

The dedicated Windows local validation service is installed and running. Exact
new main commits have automatically passed all29 existing controls and the
unchanged33-chart/34-release validator, atomically advanced validated plus the
immutable commit tag, and reconciled through Flux. No new Actions requests are
used. The independent clean service clone preserves the dirty operator checkout.

Tautulli2.18.2/Python3.13.17 passed complete cold authentication, initial and
independent controlled-restart data preservation, eleven authenticated API/Plex
checks on both writers, and all six actual public HTTP routes. All16 users and
2,878 history/media/metadata rows remain. Its fresh scan reports0critical/48high,
with0available critical/high fixes. Exact receipts and narrow source-proven
avatar/log/cache changes are in [Tautulli acceptance](docs/TAUTULLI-ACCEPTANCE.md).
Final browser acceptance remains open.

Pi-hole's original two claims are fully archived off-cluster:84files,
1,082,838,955 plaintext bytes; encrypted archive SHA256
`ee490a2b19a2a8a302d72f82cde05fd7c3fad288159168c54a36ba49c48e1289`.
Original SQL baseline includes9,982,551 query rows and1,339,185 gravity rows.
The new official FTL6.8/Core6.5/Web6.6.1-based signed-OS-patched artifact passed
the fresh unsuppressed image scan with no findings and separate upstream advisory
review. It is preloaded on all3nodes; the older FTL6.5 derivative was never adopted.
Initial live schema/config/history preservation and six authenticated API reads
plus internal UDP/TCP DNS passed. Controlled-restart preservation and authenticated API checks passed. All three
external nodes passed UDP/TCP DNS and HTTP route checks. Only final browser
acceptance remains pending for this application.
Retention remains91days and the existing password hash is preserved.

Redis was patched within8.6 to8.6.7 after a complete authenticated cold RDB/PVC
archive. The same Longhorn claim and the exact original RDB SHA passed on the
new Ready writer, with PONG, actual8.6.7 and healthy persistence. Its exact image
scan has no reported findings. Normal cache expiration/writes are not claimed
as immutable cache-value equivalence. Public routing is restored through the same local validator and Flux; all three
external nodes returned PONG.

The signed Debian13/PHP8.3.36 WordPress and phpMyAdmin derivatives are adopted.
WordPress preserved its account, all12 tables,55 posts,227 comments and4,951
files; complete encrypted SQL and file backups were authenticated first. The
first empty SQL dump was rejected and corrected before deployment. phpMyAdmin
retains all58 production dependencies, MFA/PDF and database connectivity. Four
static sites passed complete per-file content, ownership, mode and file-timestamp
comparison after nginx patching. Directory mtimes are excluded from equality,
with individual private manifests retained. All45 HTTP/Redis route checks passed;
WordPress preserves its existing canonical HTTPS admin redirect. These artifacts
have no available fixes in the recorded scan; unfixed rows remain visible.
The full goal and whole-inventory residual review remain active.

CoreDNS now runs the reviewed1.14.7 security build on both original replicas.
The fresh exact scan has no Critical/High/Medium/Low findings (three Unknown
rows retained). All18 UDP/TCP DNS queries and four Pod health checks passed;
only the image changed. Original Corefile/Service/deployment identities remain.
See [CoreDNS evidence](docs/COREDNS-SECURITY-PATCH.md). Dedicated native F-drive
build storage was installed through Ansible without changing existing cluster
disks, old build guards or Strata. Jackett and Plex cutovers remain in progress;
this checkpoint does not complete the goal.

Jackett's complete cold archive, six-indexer/API/credential comparison, controlled
restart and six external routes now pass; see [acceptance](docs/JACKETT-ACCEPTANCE.md).
Plex's complete encrypted cold config is authenticated and its same-beta OS patch
is Ready through Flux. The first hot-baseline section-table mismatch is retained;
a whole-archive comparison proved every cold section row/column equals live, with
no excluded field. The corrected full qualifier passed; routes are being restored.
Unpackerr's pinned Go1.27.3/current signed-Alpine rebuild succeeded and exact scan
is running; Homepage's patched build is running. Neither is adopted yet.

Plex's six external identity/web checks now pass. Unpackerr's complete cold
config backup, real isolated ZIP/mock-import cleanup and live native bindings/
config/startup checks passed. http-echo's unchanged-source rebuild has zero scan
findings and identical Service/ingress replies and retained claim/spec. See
[Unpackerr](docs/UNPACKERR-ACCEPTANCE.md) and [http-echo](docs/HTTP-ECHO-SECURITY-PATCH.md).
Homepage1.13.2 now runs the exact patched runtime with zero scan findings. Its
complete cold archive is authenticated; all nine active configuration files,
Native Secret bindings, original PVC/spec and internal HTTP checks passed.
qBittorrent5.3.0/LT2.0.15 retained all231 Legacy torrents and454 file identities,
original credentials, paths, priorities and progress after full cold backup and
source-proven settings compatibility fixes. Its exact image has zero findings.
The shell monitor's204/cookie repair is now deployed through the same private
local-validation/Flux owner. Six real queue cycles, original notification-state
preservation, authentication and automatic VPN-port reconciliation passed; the
full231-torrent/454-file comparison passed again. All15 Homepage/qBittorrent
external route checks passed. Pi-hole exporter's same-source patch
and three real scrapes passed with zero findings. See
[Homepage](docs/HOMEPAGE-SECURITY-PATCH.md),
[qBittorrent](docs/QBITTORRENT-SECURITY-PATCH.md) and
[exporter](docs/PIHOLE-EXPORTER-SECURITY-PATCH.md). Mealie/xTeVe/Ruckus and the
remaining exact inventory continue; final browser and whole-inventory acceptance
remain open. This checkpoint does not finish the tracked goal.

October25 latest execution: Mealie, xTeVe and jtmb-dev after/restart checks passed.
Their images are respectively a3fc64d6…,0ab77160… and6432c718…. Mealie preserved
53 tables/847 rows,3 users and 33 recipes; xTeVe preserved accounts/credentials,
provider identities,108 mappings/29 active mappings and all claims, including
untouched SMB. xTeVe source-proven provider refresh/backup rotation is verified
explicitly; its configured FFmpeg media fixture passed, while failed VLC tests
remain recorded. The website preserved23 files and11 routes. Personal login and
final browser validation are not implied by these receipts.

Existing SMB release is now chart1.20.4/revision2, preserving all12 original
resource UIDs,14 PVs/14 PVCs and native credential fingerprints. A first postcheck
flagged only the two generated DaemonSet revision annotations; read-only exact
original-HMAC reconstruction passed without repeating the upgrade. Linux3/3,
controller1/1 and existing mount-root samples passed. NAS media remains on NAS.

Ruckus is deliberately paused through Flux for its complete encrypted cold
backup and isolated MySQL patch qualification. The authenticated cold archive
covers216,491,611 bytes; the original PVC and all user/system data remain intact.
The first isolated restore rejected the original external mysql.sock symlink
before any server start; only those recorded tmpfs fixture resources are being
retired, with failed receipts retained. The correction preserves that exact
socket-link metadata while using a separate private socket for cloned servers.
Bazarr's compatible security artifact is built and undergoing exact-image scan;
Radarr/Sonarr and remaining Go image fixes are source preparation, not adoption.
The tracked goal remains active and final inventory/browser acceptance is open.

Ruckus database cutover and declared restart now pass on the new retained-data
lineage, preserving all3,962 application rows/account/native Secret and original
source PVC. Bot384c86b restores one normal instance after bcrypt/Node22 checks;
readiness alone is not final dashboard/connection acceptance. Both workers'
USN8555 security37.2 package transactions passed strict package/runtime/kernel/
node continuity checks with zero failures. See
[database lineage](docs/RUCKUS-DATABASE-SECURITY-PATCH.md) and
[worker patch](docs/UBUNTU-PRO-SECURITY-PATCH-20261025.md).
Four exact security artifacts are ready for the remaining application cutovers;
raw scans and ImageSharp's per-advisory3.2 backport attribution remain separate.
Final inventory/browser gates are still open; this checkpoint is not completion.

October25 18:15 UTC checkpoint: Radarr, Sonarr, Bazarr and Whoami now run the
qualified exact security images through private local validation and Flux.
Fresh full cold backups and after/restart checks passed; Radarr/Sonarr's full
original Users rows and credentials passed again. External media HTTPS/browser
acceptance remains open. See [media receipts](scripts/migration/media-security-acceptance-20261025.md).
The cached live BORTUS image was fully audited:17 reachable blobs verified,
5C/99H/160M/154L/3U. Findings were handed to its separate owner; this chat did not
change its application. See [exact audit](docs/bortus-cached-runtime-audit.md).

Ruckus's current fresh DB claim is degraded with one healthy replica because two
nodes are below Longhorn's disk scheduling floor. SQL acceptance does not prove
storage redundancy. Read-only inspection reattached the retained original claim
with both existing replicas RW/healthy; every original file byte/metadata matches
the cold archive, with only top-level directory mtime drift recorded. A proposed
fresh-current-data sibling-directory recovery is source preparation only: no
original file is overwritten, no current data is replaced by the older archive,
and replica/space thresholds are not weakened. Do not describe HA recovery as done.

The four accepted services'12 redundant node transfer files were removed by
Ansible, recovering1,322,184,704 allocated Linux bytes while retaining complete
controller copies. A stopped successful Ruckus builder's reproducible state alone
was removed after source/artifact/reference checks, recovering2,384,879,616 Linux
bytes on F; its image, logs, recipe and all source/locks remain. Windows/VHDX
recovery is not inferred. Traefik's metadata cache is being completed under the
same bounded attempts; no incomplete build was adopted. Calico and Longhorn
compatible remediation proposals are concrete but remain unimplemented. Full
cluster security, HA recovery, final inventory/routes and final IAB remain open;
the tracked goal is active. This checkpoint is not completion.
