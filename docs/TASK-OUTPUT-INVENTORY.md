# Maintenance output ownership and reconciliation

## Ruckus upstream qualification reconciliation, October 26 18:54 UTC

Owner: `01a12045-bf7e-73b3-8557-752d17c72ffd`. All new local outputs reused
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`,
ext4 UUID `3c792469-ea0e-4a2c-98e8-1185b141607b`, backed by
`F:\branconet-build-storage\native-build-20261025.ext4`.
This was historical-copy qualification, not a production database cutover.
[Exact comparison, recovery and next production steps](UPSTREAM-RUCKUSDB-MIGRATION-20261026.md).

The terminal scan service was inactive/dead with Result success and exit 0.
Resolved containment, ownership/inode, file hash, protected source survival,
regeneration and process/FD/map/mount checks passed. Cleanup removed exactly
**6393856 allocated Linux bytes**:

| Exact path relative to the authorized root | Allocated bytes |
| --- | ---: |
| `security-review-20261026/cache/fanal/fanal.db` | 6381568 |
| `security-review-20261026/cache/fanal` | 4096 |
| `security-review-20261026/tmp` | 4096 |
| `security-review-20261026/home` | 4096 |

Exact pre/post hashes, inodes and regeneration are retained in
`operator-control/ruckusdb-review-scratch-{plan,reconciliation}.json`.
The cache can be regenerated only with the recorded immutable-image scan,
unchanged pinned scanner/feed inputs, resource bounds and a new result filename.
Original results and failures must not be overwritten or rescanned as cleanup.

The dedicated trial namespace `ruckusdb-upstream-6b6dacf17d6c`, its qualifier
Pod and deny policy were retired with UID preconditions after accepted state/
account/authentication comparisons and observed clean shutdown. Kubernetes
teardown removed its RAM-backed copies: **720482304 allocated RAM bytes**, 783
paths. RAM teardown is separate from Linux disk removal and Windows free space.
Exact resource UIDs and measurements are in
`upstream-ruckusdb-20261026/trial-retirement.json`. No production claim was
mounted in the trial and no production workload was stopped.

Retained exceptions:

- `upstream-ruckusdb-20261026`: unique original/failed/corrected observations,
  account/grant/data proofs, UID receipts and encrypted complete engine logs.
- `control-source/upstream-ruckusdb-20261026`: all executed source generations,
  exact restore and SQL inputs, reviewed Ansible profile and tagged vendor SQL.
- `security-review-20261026/apps-ruckusdb-current-r3-0`: exact vendor findings,
  trusted-input verification and scan source; public databases remain intact.
- `operator-control/ruckusdb-upstream-recovery-metadata.tar.age`: required
  1813124-byte recovery archive, SHA-256
  `274d5a34c26436571d8507206632046fcc8a6b5ca35b6d17e117e0e2db23f263`,
  complete local member verification and authenticated complete NAS read-back.
- `ruckus-ha-recovery-20261025` and every earlier cold/failed/rollback source:
  historical authenticated source and original data remain protected in place.
- `operator-control/tmp/system-commandline-sentinel-files` and its parent:
  creator/regeneration and complete inactive Windows-handle proof remain
  unavailable; no deletion attempted. The parent contains this exception.
- Existing controller evidence on
  `F:\branconet-migration-artifacts\maintenance-storage-20261025` and all
  earlier inventory exceptions remain; no cumulative source/cache tree copied.

No build, dependency installation, GitHub Actions, new image publisher,
filesystem migration, Windows shutdown or VHDX compaction ran. Cached node
images and runtime PVC/NAS data were not pruned. No Windows disk recovery is
claimed.

## Threadfin checkpoint reconciliation, October 26 18:16 UTC

Owner: `01a12045-bf7e-73b3-8557-752d17c72ffd`. Reused the single authorized
root `/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`,
ext4 UUID `3c792469-ea0e-4a2c-98e8-1185b141607b`, backed by
`F:\branconet-build-storage\native-build-20261025.ext4`. No build, dependency
installation, second output root, shutdown or compaction ran.
[Delivery and retained recovery data](UPSTREAM-THREADFIN-ADOPTION-20261026.md).

Removed **1065947136 allocated Linux bytes** across **4683 paths**. Six terminal
publisher stages account for 1065934848 bytes / 4680 paths. Original reachable
Git blobs, source/lockfiles and pinned primary tools survived. Every generated
export matched its immutable manifest; all 24 unique prepare/check/publish and
validation receipts still match. Exclusive operation locks, resolved containment,
ownership/inode, regular-file/no-link, regeneration and process/FD/map/mount
checks passed before deletion. The running publisher was not stopped or replayed.

Paths below are relative to `local-charts-publisher/`. The source column includes
only verified generated exports, copied tools and empty descendants; each stage
retains `source/.validation/validation.json` and its three phase receipts.
Every individual path/inode/byte count and exact regeneration procedure is in
`operator-control/threadfin-upstream-publisher-scratch-{plan,reconciliation}.json`.

| Exact stage | Removed source exports/tools | Removed `home` | Removed `tmp` |
| --- | ---: | ---: | ---: |
| `local-charts-publish-80b94ee99a8a48c38544f89c8a59f82d` | 177647616 | 4096 | 4096 |
| `local-charts-publish-62022e3b40044edfbf964d72fa3b2b62` | 177647616 | 4096 | 4096 |
| `local-charts-publish-bfb7393b71f244dd9396e1b8f7408b80` | 177647616 | 4096 | 4096 |
| `local-charts-publish-22b688cfe0c54889a09ce72f81d20be7` | 177647616 | 4096 | 4096 |
| `local-charts-publish-35d9582991564314a95ebcefb1024955` | 177647616 | 4096 | 4096 |
| `local-charts-publish-81736099d0ad48a08109c6bec6792785` | 177647616 | 4096 | 4096 |

Other exact removed paths, relative to the same authorized root, with their
safety checks and regeneration in `operator-control/threadfin-upstream-scratch-reconciliation.json`:

| Removed empty directory | Allocated bytes |
| --- | ---: |
| `operator-control/tmp/ansible-home/local` | 4096 |
| `operator-control/tmp/ansible-home` | 4096 |
| `operator-control/tmp/ansible-local` | 4096 |

Retained exceptions, all within the declared root unless explicitly stated:

- `upstream-xteve-20261026`: complete required encrypted cold archives, original
  and current baselines, copy proofs, canary/production/restart results and all
  unique failures. Both cold archives have authenticated complete NAS copies.
- `control-source/upstream-xteve-20261026`: exact observer generations,
  compatible-state helper, cold-backup controls and pinned vendor sources.
- `security-review-20261026/apps-threadfin-current-r3-0`: exact vendor scan and
  verified feed receipts. The earlier review's 1658880-byte cache cleanup remains
  separately recorded; it is not counted again in this checkpoint total.
- `operator-control/threadfin-upstream-recovery-metadata.tar.age`: required
  9751060-byte archive, full local member verification and authenticated complete
  NAS read-back. Original key-backup evidence remains unchanged.
- All six stage roots above: unique receipts and validation reports retained.
- `operator-control/tmp/system-commandline-sentinel-files` and its `tmp` parent:
  creator/regeneration and complete inactive Windows-handle proof remain
  unavailable. No deletion was attempted; the parent contains that exception.
- Existing controller evidence at
  `F:\branconet-migration-artifacts\maintenance-storage-20261025`: earlier
  authorized unique execution evidence remains in place, with no copied tree.
- Original xTeVe PVC root, active corrected prefix
  `threadfin-20261026-0a4e4fd891c1`, failed prefix
  `threadfin-20261026-d19cde2b3889`, original config, native Secrets, SMB/NAS media
  and all prior rollback/failed data remain required runtime or recovery data.
- Kubernetes failed diagnostic Pods `plex/threadfin-guide-51bd5b564a52` and
  `plex/threadfin-compatible-0a4e4fd891c1`, with their diagnostic resources, remain
  unique failure evidence; both have expired and are not running. The two older
  failed Seerr diagnostic Pods also remain. The successful canary's Pod,
  ConfigMap and NetworkPolicy were deleted with exact UID preconditions.

The previous inventory and every earlier retained exception survive. Linux
allocated-byte removal does not establish Windows free-space recovery; no VHDX
compaction or Windows recovery is claimed. No images, PVCs, models, original
chats, quarantines or user data were pruned.

## qBittorrent checkpoint reconciliation, October 26 16:13 UTC

Owner: `01a12045-bf7e-73b3-8557-752d17c72ffd`. Reused only the existing
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`,
physical ext4 UUID `3c792469-ea0e-4a2c-98e8-1185b141607b`, backing file
`F:\branconet-build-storage\native-build-20261025.ext4`. No image build,
dependency install, second root, shutdown or compaction ran.
[Exact deployment, preservation and remaining limits](UPSTREAM-QBITTORRENT-ADOPTION-20261026.md).

Cleanup removed **710959104 allocated Linux bytes** after complete containment,
ownership/inode, source/lockfile survival, regeneration, exclusive operation-lock
and process/FD/map/mount checks. The scan service was terminal inactive/dead,
Result success, exit 0. Four successful current publisher stages account for
710590464 bytes and 3116 exact removed paths; original Git blobs/commits and
pinned tools survive, with all 16 unique stage receipts/reports matching after
cleanup. The running publisher was neither stopped nor replayed.

The table paths are relative to `local-charts-publisher/`. Source totals include
generated exports, copied tools and empty descendants. Each stage retains its
`source/.validation/validation.json` and prepare/check/publish receipts. Every
individual removed path, inode and byte count is preserved in
`operator-control/qbittorrent-upstream-publisher-scratch-reconciliation.json`;
the exact regeneration command and full source manifest remain in its plan.

| Completed stage | Removed source exports/tools | Removed `home` | Removed `tmp` |
| --- | ---: | ---: | ---: |
| `local-charts-publish-2271f3fcea9b485cb4390fdba1aee9df` | 177639424 | 4096 | 4096 |
| `local-charts-publish-08dcbc67cd9043e8a58a7ef643aebeb9` | 177639424 | 4096 | 4096 |
| `local-charts-publish-1148a20aea6a45f480da7c6838b89db5` | 177639424 | 4096 | 4096 |
| `local-charts-publish-6b9a5e476b8c485f8d54678031ac9ea7` | 177639424 | 4096 | 4096 |

Other removed paths, relative to the declared root; exact protected hashes and
regeneration are in `operator-control/qbittorrent-upstream-scratch-reconciliation.json`:

| Exact path | Allocated bytes |
| --- | ---: |
| `security-review-20261026/cache/fanal/fanal.db` | 348160 |
| `security-review-20261026/cache/fanal` | 4096 |
| `security-review-20261026/tmp` | 4096 |
| `security-review-20261026/home` | 4096 |
| `operator-control/tmp/ansible-home/local` | 4096 |
| `operator-control/tmp/ansible-home` | 4096 |

Retained current-stage exceptions:

- `upstream-qbittorrent-20261026`: required complete cold archive, observation
  key, baseline/after/restart comparisons, default repair and all unique failures.
- `control-source/upstream-qbittorrent-20261026`: exact executed observer
  generations, cold controls, repair helper and Ansible sources/manifests.
- `operator-control/qbittorrent-upstream-recovery-metadata.tar.age`: required
  distinct encrypted source/verification evidence; complete NAS authentication passed.
- `security-review-20261026`: verified advisory inputs, exact public image scan
  results and original integrity-failure evidence; only the reproducible fanal
  analysis cache and empty scratch were removed.
- All four publisher stage receipt/report subtrees listed above: unique exact
  validation/publication evidence, with reachable primary Git source objects.
- `operator-control/tmp/system-commandline-sentinel-files`: creator/regeneration
  and complete inactive Windows handle proof remain unresolved. No deletion attempted.
- `operator-control/tmp`: retained parent contains those unresolved sentinels.

All earlier failures, safety exceptions, rollback/recovery sources and other
owners remain protected. No images, volumes, NAS media or user data were pruned.
The current private inventory is `operator-control/storage-inventory-current.json`;
the compact checkpoint is `operator-control/qbittorrent-upstream-checkpoint-summary.json`.
At 16:12:53 UTC, C: free was 96949673984 bytes, F: free 21642555392 bytes,
and native ext4 free 21627191296 bytes. These are separate measurements;
Linux cleanup does not establish Windows disk recovery. Recreate the explicitly
configured private scratch paths before the next Ansible/encryption stage.

## Pi-hole checkpoint reconciliation, October 26 15:03 UTC

Owner: `01a12045-bf7e-73b3-8557-752d17c72ffd`. This checkpoint reused only
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`,
physical ext4 UUID `3c792469-ea0e-4a2c-98e8-1185b141607b`, backed by
`F:\branconet-build-storage\native-build-20261025.ext4`. No image build,
dependency installation, second output root, shutdown or compaction ran.
[Exact data/DNS/API/restart acceptance and recovery](UPSTREAM-PIHOLE-ADOPTION-20261026.md).

Cleanup removed **1408999424 allocated Linux bytes**: 532934656 from the three
successful current publisher stages and 876064768 from exact reproduced scan/
Ansible scratch and the authenticated temporary original DB projection.
Complete containment, ownership/inode, source/lockfile survival, regeneration,
exclusive operation-lock and process/FD/map/mount checks passed. Every original
private Git blob and commit remained reachable, original pinned tool hashes
matched, and all 12 unique stage receipts/reports matched afterward. The live
publisher/watcher remained running. No historical publication was replayed.

The following paths are relative to `local-charts-publisher/`. Source totals
include regenerated Git exports, copied tools and empty descendants. Each stage
retains `source/.validation/validation.json` and immutable prepare/check/publish
receipts. Exact 2337 removed paths/inodes/bytes and source manifests are in
`operator-control/pihole-upstream-publisher-scratch-reconciliation.json` and its plan.

| Completed stage | Removed source exports/tools | Removed `home` | Removed `tmp` |
| --- | ---: | ---: | ---: |
| `local-charts-publish-02b099e7ced743279f27ed7aaa7cfbc5` | 177639424 | 4096 | 4096 |
| `local-charts-publish-c96ed6d418154e6d8e5ec15eaff0cac3` | 177639424 | 4096 | 4096 |
| `local-charts-publish-6f4bf34e7c334cf2a4c2f0885bf90010` | 177631232 | 4096 | 4096 |

Other removed paths relative to the declared root:

| Exact path | Allocated bytes |
| --- | ---: |
| `security-review-20261026/cache/fanal/fanal.db` | 364544 |
| `upstream-pihole-20261026/cold-runtime-source/pihole-FTL.db` | 875642880 |
| `upstream-pihole-20261026/cold-runtime-source/pihole-FTL.db-wal` | 0 |
| `upstream-pihole-20261026/cold-runtime-source/pihole-FTL.db-shm` | 32768 |
| `security-review-20261026/cache/fanal` | 4096 |
| `security-review-20261026/tmp` | 4096 |
| `security-review-20261026/home` | 4096 |
| `upstream-pihole-20261026/cold-runtime-source` | 4096 |
| `operator-control/tmp/ansible-home` | 4096 |
| `operator-control/tmp/ansible-local` | 4096 |

The first scratch check retained all targets because read-only SQLite access had
created sidecars beside the regenerated input. The exact failed check remains in
`operator-control/pihole-upstream-scratch-failed-safety-r1.json`. Reconciliation
then verified an empty WAL, a 32768-byte transient shared index, an unchanged full
original DB SHA256, authenticated backups and no active references. The bounded
revised plan removed only those explicitly identified reproduced paths. Exact
before/after protected hashes and removed bytes are in
`operator-control/pihole-upstream-scratch-reconciliation.json`.

Regenerate original source input with the source-pinned
`operator-control/regenerate-pihole-runtime-source.py` after fresh C:/native
capacity checks. It authenticates the unchanged complete archive, extracts only
the hash-bound original DB and preserves all original proof receipts. Read-only
SQLite WAL-mode access regenerates its empty WAL/shared index when needed.
Recreate scan analysis cache only from the retained exact immutable-image argv,
pinned tool/feeds and bounded credential-hidden execution, using a new report
filename. Recreate configured empty Ansible/scratch paths. Recreate publisher
exports from their exact reachable Git SHAs and original exporter/pinned tools;
preserve unique reports and never replay historical publication.

Retained exceptions:

- `operator-control/tmp/system-commandline-sentinel-files`: exact creator/
  regeneration and complete inactive Windows-handle proof remain unresolved.
  No deletion was attempted; its nonempty parent `operator-control/tmp` remains.
- `upstream-pihole-20261026`: complete original authenticated archive, encrypted
  SQL verification key, native observation key, original/after/restart typed
  data/config/DNS/API/route receipts and every failed observation.
- `control-source/upstream-pihole-20261026`: all exact executed generations,
  current/full schema contracts, shared reader inputs and immutable manifests.
- `operator-control/pihole-upstream-recovery-metadata.tar.age`: distinct encrypted
  source/acceptance/failure recovery evidence with complete NAS authentication
  and read-back. Original cold ciphertext/feed binaries/decoded DB were not duplicated.
- The three publisher roots: unique receipts, manifests and validation reports;
  primary original Git objects, source and `.tools` remain required runtime inputs.
- `security-review-20261026`: current advisory/Java inputs, complete unsuppressed
  vendor report and original integrity/failure evidence.
- Original failure/safety inventories, vendor source hashes, typed startup-record
  proofs and bounded failed-reader diagnostics remain. Only owned temporary
  reader Pods were UID-deleted after evidence capture; no production claim was deleted.
- All earlier owner, failed-safety, failure, rollback and runtime exceptions
  remain. No older artifacts, PVCs, NAS media, images, volumes, models or chats
  were pruned.

At 15:03 UTC native free space was **21665275904 bytes**. Separately measured
Windows C: free space was **97343467520 bytes** and F: **22599274496 bytes**.
Linux recovery does not establish Windows recovery; none is claimed. Exact
space receipt: `operator-control/pihole-upstream-final-space.json`. The current
228-entry storage inventory records this checkpoint and retains all prior exceptions.

## Vaultwarden checkpoint reconciliation, October 26 14:00 UTC

Owner: `01a12045-bf7e-73b3-8557-752d17c72ffd`. This checkpoint reused only
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`,
physical ext4 UUID `3c792469-ea0e-4a2c-98e8-1185b141607b`, backed by
`F:\branconet-build-storage\native-build-20261025.ext4`. No application image
build, dependency installation, output-root migration, shutdown or compaction ran.
[Runtime/data acceptance and recovery](UPSTREAM-VAULTWARDEN-ADOPTION-20261026.md).

Cleanup removed **534106112 allocated Linux bytes**: 532934656 from the three
successful publisher stages and 1171456 from exact scan/Ansible scratch paths.
The original private Git commits and every exported blob were verified reachable;
original validator binaries and the live watcher remain. All 12 unique stage
receipts/reports and protected recovery/data/key hashes matched afterward.
Exclusive operation locks and ownership/inode/containment/process/FD/map/mount
checks passed before deletion. No historical publication was replayed.

Paths below are relative to `local-charts-publisher/`. Source totals include
reproducible exported Git files, copied tools and empty descendants. The stage
`source/.validation/validation.json` and immutable prepare/check/publish receipts
remain. The exact 2337 removed paths/inodes/bytes are recorded in
`operator-control/vaultwarden-publisher-scratch-reconciliation.json` and its plan.

| Completed stage | Removed source exports/tools | Removed `home` | Removed `tmp` |
| --- | ---: | ---: | ---: |
| `local-charts-publish-0a762cf947874cbbb444c1e225ea0458` | 177639424 | 4096 | 4096 |
| `local-charts-publish-de496125a8b041e09638fa76987500b6` | 177631232 | 4096 | 4096 |
| `local-charts-publish-e0a824e0395c4cbbb63f2d94d2ef07ab` | 177639424 | 4096 | 4096 |

Other removed paths relative to the declared root:

| Exact path | Allocated bytes |
| --- | ---: |
| `security-review-20261026/cache/fanal/fanal.db` | 1150976 |
| `security-review-20261026/cache/fanal` | 4096 |
| `security-review-20261026/tmp` | 4096 |
| `security-review-20261026/home` | 4096 |
| `operator-control/tmp/ansible-home` | 4096 |
| `operator-control/tmp/ansible-local` | 4096 |

Exact scratch safety checks and protected hashes are in
`operator-control/vaultwarden-scratch-reconciliation.json`. Regenerate exports
from each successful stage's original Git SHA using the retained publisher
exporter and unchanged original pinned tools; preserve unique validation files.
Regenerate the public Trivy analysis cache only from the unchanged exact-image
scan argv, pinned tool/feeds and original bounded credential-hidden execution;
use a new report filename. Recreate only configured empty Ansible/scratch paths.

Retained exceptions:

- `operator-control/tmp/system-commandline-sentinel-files`: creator/regeneration
  and complete inactive Windows-handle proof are unresolved. No deletion was
  attempted; its nonempty parent `operator-control/tmp` remains.
- `upstream-vaultwarden-20261026`: original authenticated cold archive, original
  decoded `state/cold-sql` input, verification key and unique complete cold/live/
  restart SQL/file/native/route observations. They are protected recovery evidence.
- `control-source/upstream-vaultwarden-20261026`: exact executed controller,
  observer, shared reader inputs and source manifest.
- `operator-control/vaultwarden-recovery-metadata.tar.age`: distinct encrypted
  acceptance/recovery evidence with authenticated NAS read-back. The ancestor
  cold ciphertext and public feed database binaries were not duplicated.
- The three publisher roots: unique receipts, original source manifests and
  validation reports remain; original Git objects and `.tools` are runtime inputs.
- `security-review-20261026`: current verified advisory/Java inputs, complete
  unsuppressed Debian/Alpine reports and earlier integrity/failure evidence.
- All earlier owner, failed-safety, failure, rollback and runtime exceptions
  remain. No older artifacts, PVCs, NAS media, images, volumes, models or chats
  were pruned.

At 14:00 UTC native free space was **22755106816 bytes**. Separately measured
Windows C: free space was **97714040832 bytes** and F: **22606925824 bytes**.
Linux cleanup does not establish Windows recovery; none is claimed. Exact
space receipt: `operator-control/vaultwarden-final-space.json`. The current
storage inventory reconciles this checkpoint and retains all prior exceptions.

## Tautulli checkpoint reconciliation, October 26 13:13 UTC

Owner: `01a12045-bf7e-73b3-8557-752d17c72ffd`. This stage reused the existing
F:-backed ext4 root
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`,
UUID `3c792469-ea0e-4a2c-98e8-1185b141607b`, backing file
`F:\branconet-build-storage\native-build-20261025.ext4`. No image build,
dependency installation, second disposable-output root, compaction or WSL
shutdown ran. [Exact acceptance and recovery](UPSTREAM-TAUTULLI-ADOPTION-20261026.md).

Cleanup removed **534061056 allocated Linux bytes**: 532926464 from the three
completed current publisher stages and 1134592 from named scan/render/scratch
outputs. All stages passed prepare/check/publish; exclusive operation locks,
ownership/inode/containment, complete process/FD/map/mount and regeneration
checks passed. Original Git commits and every exported blob were independently
verified reachable in the existing publisher repository before removing copies.
No tracked original source or lockfile was deleted. Original pinned validator
binaries and the active watcher remain. All 12 unique stage receipt/validation
files matched their hashes afterward; the data/key/recovery protected hashes
also matched. Historical publications were never replayed.

The following paths are relative to `local-charts-publisher/`. Source totals
include generated Git exports, copied tools and emptied descendant directories;
`source` itself and its unique `.validation/validation.json` remain. Exact 2337
removed paths, allocated sizes and inode checks are in
`operator-control/tautulli-publisher-scratch-reconciliation.json` and its plan.

| Completed stage | Removed source exports/tools | Removed `home` | Removed `tmp` |
| --- | ---: | ---: | ---: |
| `local-charts-publish-c90f64d507714f2b896f75992f5b5072` | 177639424 | 4096 | 4096 |
| `local-charts-publish-71d90673cd7143e78c9bda312d985f31` | 177631232 | 4096 | 4096 |
| `local-charts-publish-e40ec5d1ae2d4da8ab50f391924402ab` | 177631232 | 4096 | 4096 |

Other removed paths relative to the declared root:

| Exact path | Allocated bytes |
| --- | ---: |
| `security-review-20261026/cache/fanal/fanal.db` | 1105920 |
| `upstream-tautulli-20261026/tmp/effective-release-values.json` | 4096 |
| `security-review-20261026/cache/fanal` | 4096 |
| `security-review-20261026/tmp` | 4096 |
| `security-review-20261026/home` | 4096 |
| `upstream-tautulli-20261026/tmp` | 4096 |
| `operator-control/tmp/ansible-home` | 4096 |
| `operator-control/tmp/ansible-local` | 4096 |

Their exact plan/receipt is `operator-control/tautulli-scratch-reconciliation.json`.
The public analysis cache is reproducible from the immutable image, pinned tool,
unchanged verified feeds and bounded argv in its retained scan receipt; select a
new report filename to preserve existing reports. Recreate configured empty
scratch before its consumers. The render-values JSON exactly matches the
reviewed release values. Exported source is reproducible with the exact preserved
Git commit/archive and original publisher exporter; copy only the retained
SHA-pinned tools, preserve unique validation reports, and never replay publication.

Retained exceptions:

- `operator-control/tmp/system-commandline-sentinel-files`: creator/regeneration
  and complete inactive Windows-handle proof remain unestablished. No deletion
  was attempted. Its nonempty parent `operator-control/tmp` is therefore retained.
- `upstream-tautulli-20261026`: original complete archive, verification key,
  authenticated cold SQL/runtime inputs, unique current/restart SQL snapshots,
  native/file/API/route/mapped checks and all distinct failed diagnostics.
- `control-source/upstream-tautulli-20261026`: frozen original and accepted source
  generations, shared reader/controller inputs and exact source manifests.
- `operator-control/tautulli-recovery-metadata.tar.age`: required encrypted
  acceptance/recovery evidence with authenticated NAS read-back. The ancestor
  complete cold archive and public advisory DB binaries were not duplicated.
- The three publisher stage roots: immutable prepare/check/publish receipts,
  original Git manifests and unique validation reports remain. Primary Git source
  and the existing original `.tools` are required publisher runtime inputs.
- `security-review-20261026`: verified current advisory/Java inputs, both complete
  vendor comparison reports and original integrity/failure evidence remain.
- Every earlier owner, failure, rollback, runtime and failed-safety exception
  remains. No older artifact, PVC, NAS media, image, volume, model or chat was pruned.

At 13:13 UTC, native free space was **22763294720 bytes**. Separately measured
Windows C: free space was **97827590144 bytes**, and F: was **22610788352 bytes**.
Linux cleanup does not establish Windows recovery; none is claimed. Raw space
evidence is `operator-control/tautulli-final-space.json`.

## Mealie checkpoint reconciliation, October 26 05:30 UTC

This stage reused the same declared F:-backed root and physical ext4 UUID.
The official filesystem export was a temporary controller qualification input;
the cluster consumes the vendor registry digest. No application image was built
or published, dependency installation performed, or second output root created.
[Exact migration, recovery and remaining findings](UPSTREAM-MEALIE-ADOPTION-20261026.md).

The first check retained everything because the tar's `.` root header was
counted as an additional descendant. The inventory comparison found no added
files and only that separately tracked root header missing from descendants.
Corrected accounting kept the root's own inode/ownership check and verified all
31561 descendants against the pinned export, including contents, types, modes,
hardlinks and symlink targets. This was a local accounting failure, not an
automatic approval-review rejection. Its original source and zero-deletion
receipt remain. All subsequent ownership/inode/containment, source/lockfile,
process FD/map/mount, regeneration, NAS and before/after protected-hash checks
passed. The 808 symlinks were unlinked by parent descriptor without dereferencing.

| Removed path relative to declared root | Main lifecycle allocated bytes | Session-backup lifecycle allocated bytes |
| --- | ---: | ---: |
| `upstream-mealie-20261026/vendor-rootfs` | 1083977728 | — |
| `upstream-mealie-20261026/vendor-rootfs.tar` | 1025556480 | — |
| `upstream-mealie-20261026/go-containerregistry-v0.22.1.tar.gz` | 16498688 | — |
| `upstream-mealie-20261026/crane` | 11874304 | — |
| `security-review-20261026/cache/fanal/fanal.db` | 1511424 | — |
| `upstream-mealie-20261026/docker-config/config.json` | 4096 | — |
| `operator-control/tmp/ansible-home` | 4096 | — |
| `operator-control/tmp/ansible-local` | 4096 | — |
| `operator-control/tmp` | 4096 | 4096 |
| `security-review-20261026/tmp` | 4096 | — |
| `security-review-20261026/home` | 4096 | — |
| `security-review-20261026/cache/fanal` | 4096 | — |
| `upstream-mealie-20261026/tmp` | 4096 | — |
| `upstream-mealie-20261026/home` | 4096 | — |
| `upstream-mealie-20261026/docker-config` | 4096 | — |
| `upstream-mealie-20261026/migration-tmp` | 4096 | — |
| `upstream-mealie-20261026/session-backup-tmp` | — | 4096 |

Total: **2139471872 allocated Linux bytes** (2139463680 + 8192). The two
`operator-control/tmp` entries are separately created/deleted lifecycles, not
duplicate recovery claims. Exact receipts are
`operator-control/mealie-scratch-reconciliation-r2.json` and
`operator-control/mealie-session-scratch-reconciliation.json`. No Windows disk
recovery is claimed. Cleanup required no compaction or WSL shutdown; service
quiescence belonged to the preceding cold-backup/cutover operation.

The subsequent publisher reconciliation removed **599146496 allocated Linux
bytes**, bringing this checkpoint's total to **2738618368 bytes**. All four
prepare/check/publish operations were terminal and successful; the existing
watcher remained live at PID 25976. Its same-revision idle branch does not reuse
completed stages. Exclusive operation locks and complete root-visible process,
FD/map/mount checks passed. Original pinned binaries remain in the publisher
checkout; all 2612 protected source/lockfile/receipt hashes matched afterward.

Paths below are relative to `local-charts-publisher/`. Each `.tools` directory
contained only the SHA-verified helm, kubectl and gitleaks copies; `home` and
`tmp` were empty. Exact per-file paths, allocated sizes and regeneration commands
are retained in `operator-control/mealie-publisher-scratch-plan*.json` and
`mealie-publisher-scratch-reconciliation*.json`.

| Exact completed stage | Removed `source/.tools` bytes | Removed `home` bytes | Removed `tmp` bytes |
| --- | ---: | ---: | ---: |
| `local-charts-publish-43385e5c3f6d4de78a30bddffcb5942b` | 149778432 | 4096 | 4096 |
| `local-charts-publish-288f85b5e5754a8986a7c1819de745d8` | 149778432 | 4096 | 4096 |
| `local-charts-publish-fffe63e236684079a6175db4b53b3e50` | 149778432 | 4096 | 4096 |
| `local-charts-publish-c968b5b7f0e248378e782d9ddb578bd9` | 149778432 | 4096 | 4096 |

The first publisher reconciliation removed three verified files, then its
directory timestamp check detected the changes caused by those same unlinks.
The corrected generation preserves that partial receipt, checks directory
device/inode/mode/owner and emptiness, and keeps the regular-file size/mtime/hash
checks unchanged. Both generations survive; this was a local accounting failure,
not an automatic approval-review rejection. Each stage retains its exact reviewed
source export, original prepare/check/publish receipts and unique validation
report. The watcher, its persistent state and original tools remain required
runtime inputs. No historical publication was replayed or publisher restarted.
At 05:48 UTC, native free space was 23029043200 bytes; Windows C: free space was
98167619584 bytes and F: free space was 22607757312 bytes. These are separate
readings, with no Windows recovery claim.

Regenerate the public runtime inputs from the exact official image and crane
release/SHAs in `upstream-mealie-20261026/prepare.json`, using the retained
bounded export/extract commands after fresh capacity checks. Recreate private
empty TEMP/HOME/config directories before their recorded consumers. Rebuild
analysis cache using the exact immutable-image command and verified input
receipts, selecting a new output path to preserve original reports. All
reconciliation sources and regeneration commands remain under `operator-control`.

Retained exceptions, relative to the same root:

| Exact retained path | Required retention reason |
| --- | --- |
| `upstream-mealie-20261026/db-copy` | Original transactional SQL snapshot, authenticated cipher, private comparison key and source observations |
| `upstream-mealie-20261026/migration-data` | Unique isolated migration state and its runtime keys, including failed-fixture provenance |
| `upstream-mealie-20261026/cold-sql` | Authenticated original cold SQL used to bind live and isolated baselines |
| `upstream-mealie-20261026/production` | Unique baseline/after/restart SQL snapshots, complete file observations, mapped audits and diagnostic logs |
| `upstream-mealie-20261026/cold` | Original complete production archive and receipt, required for data-compatible rollback; NAS authentication passed |
| Remaining direct files in `upstream-mealie-20261026` | Distinct unit, migration and observer failure/qualification evidence; reproducible public runtime inputs alone were removed |
| `control-source/upstream-mealie-20261026` | Every executed frozen generation and twelve independently matched vendor mapping sources |
| `operator-control/mealie-recovery-metadata.tar.age` | Required distinct recovery evidence, fully authenticated on NAS; ancestor cold archive and public DB binaries were not duplicated |
| `operator-control/mealie-session-secret.age` and its receipts | New production session-signing value, encrypted directly from RAM, matched to restart proof and fully authenticated on NAS |
| `security-review-20261026/cache/db` and `cache/java-db` | Verified immutable advisory/Java inputs needed for the remaining fleet review; before/after hashes match |
| `security-review-20261026/cache/db-integrity-failure-20261026` | Unique original checksum-mismatch evidence; cause unestablished; no deletion authorized |
| `security-review-20261026/docker-config` | Earlier isolated scanner configuration; exact creation provenance not separately reconciled |
| `security-review-20261026/nginx-0` | Original unique scanner failure evidence |
| `operator-control/mealie-*`, `smb-mealie-*` and exact related control sources | Minimal distinct rollout, scan, original failure, repair, backup and cleanup receipts/sources |

All earlier ownership/failure/rollback exclusions, active publisher state and
other owners' artifacts remain protected. No PVC/NAS data, Docker image, volume,
model, user source, original chat or older artifact was pruned.

## Jackett checkpoint reconciliation, October 26 03:47 UTC

The existing declared F:-backed root, physical UUID and owner remain unchanged.
All new observations, frozen controls and archives use `upstream-jackett-20261026`,
`control-source/upstream-jackett-20261026`, `operator-control` and the existing
`security-review-20261026`. No build, dependency installation or new output root
was introduced. Regeneration and protected data are recorded in
[the exact stage contract](UPSTREAM-JACKETT-ADOPTION-20261026.md).

After the helper Pod was deleted by exact UID and all producers/copies/scans
finished, root-visible ownership, inode, containment, source/lock, process FD/map/
mount, regeneration and protected-input hash checks passed. Exact reconciliation:
`operator-control/jackett-scratch-reconciliation.json`.

| Removed path relative to declared root | Allocated Linux bytes |
| --- | ---: |
| `security-review-20261026/cache/fanal/fanal.db` | 266240 |
| `operator-control/tmp/ansible-home` | 4096 |
| `operator-control/tmp/ansible-local` | 4096 |
| `operator-control/tmp` | 4096 |
| `security-review-20261026/tmp` | 4096 |
| `security-review-20261026/home` | 4096 |
| `security-review-20261026/cache/fanal` | 4096 |

Total: **290816 allocated Linux bytes**. No Windows disk recovery is claimed.
Regenerate image-analysis cache with the immutable-image scanner command in the
receipt, using a new result path to preserve unique reports. Recreate the private
empty TMP/HOME directories before the recorded Ansible/encryption/scan commands.

Retained exceptions, relative to the same root:

| Exact retained path | Reason |
| --- | --- |
| `security-review-20261026/cache/db-integrity-failure-20261026` | Unique original checksum-mismatching DB; cause unestablished; no deletion authorized |
| `security-review-20261026/cache/db` | Verified advisory DB required for remaining fleet review; full before/after hashes match |
| `security-review-20261026/cache/java-db` | Verified Java identification index required for remaining fleet review; full before/after hashes match |
| `security-review-20261026/docker-config` | Isolated scanner configuration; exact creation provenance not separately reconciled |
| `security-review-20261026/nginx-0` | Unique original scanner failure evidence |
| `security-review-20261026/apps-jackett-current-r3-0` and `scan-maintained-apps-jackett-current-r3.py` | Exact current vendor findings, execution receipt and frozen scanner source |
| `control-source/upstream-jackett-20261026` | All frozen backup/observer/repair sources and generations, including failed observations |
| `upstream-jackett-20261026` | Original complete state backup, private comparison key, before/after/restart observations, failures and captured pre-repair file; required recovery data |
| `operator-control/jackett-recovery-metadata.tar.age` | Required authenticated recovery metadata, verified on NAS; originals retained |
| `operator-control/jackett-*`, `operator-control/smb-jackett-*` and exact related control sources | Minimal distinct execution, repair, publication, scan, recovery and cleanup evidence |

All earlier exclusions, active publisher state, other owners' artifacts and
rollback/source inventories remain retained. No PVC/NAS data, image, volume,
model, unrelated source or older artifact was pruned. Native Secrets remain
authoritative and original failed observations were not rewritten as passes.

## Homepage checkpoint reconciliation, October 26 02:22 UTC

Both cleanup lifecycles used the same declared F:-backed root and exact
ownership/inode/path, source/lock preservation, regeneration and root-visible
process FD/map/mount checks. The first removed the listed analysis/empty scratch
paths but failed the final protected-DB comparison. The mismatching DB was
retained, not deleted or re-baselined. After a verified official replacement and
read-only rescan, the second lifecycle passed all protected file hashes, recording
the actual before/after digests. No runtime image, user data, source, failed
evidence or required recovery artifact was pruned.

| Exact path relative to declared root | First lifecycle bytes | Final lifecycle bytes |
| --- | ---: | ---: |
| `security-review-20261026/cache/fanal/fanal.db` | 774144 | 335872 |
| `operator-control/tmp/ansible-home` | 4096 | 0 |
| `operator-control/tmp/ansible-local` | 4096 | 0 |
| `operator-control/tmp` | 4096 | 4096 |
| `security-review-20261026/tmp` | 4096 | 4096 |
| `security-review-20261026/home` | 4096 | 4096 |
| `security-review-20261026/cache/fanal` | 4096 | 4096 |

The second column and third column refer to separately recreated lifecycles,
not duplicate recovery claims. Total removed: **1150976 allocated Linux bytes**
(798720 + 352256). No Windows disk recovery or compaction is claimed. Exact
receipts are `operator-control/homepage-scratch-reconciliation.json` and
`homepage-final-scratch-reconciliation.json`. Recreate only the recorded private
empty directories when needed. Regenerate image-analysis cache with the exact
recorded immutable-image command and verified inputs, selecting a new report
output path so original results survive.

Retained exceptions, relative to the same root:

| Exact retained path | Reason |
| --- | --- |
| `security-review-20261026/cache/db-integrity-failure-20261026` | Original checksum-mismatching DB/metadata, identical retained inode/size/SHA after bounded inactive same-root rename; cause unestablished; no deletion authorized |
| `security-review-20261026/cache/db` | New verified official advisory input, required for remaining fleet review; two stored-file read-backs and post-scan/post-cleanup hashes match |
| `security-review-20261026/cache/java-db` | Verified immutable Java identification index required for remaining fleet review |
| `security-review-20261026/docker-config` | Isolated scanner config; exact creation provenance not separately reconciled |
| `security-review-20261026/nginx-0` and original public/Java input receipts | Original unique failure/historical evidence |
| `control-source/upstream-homepage-20261026` | Complete frozen backup source and all observer generations/manifests, including failed assumptions |
| `upstream-homepage-20261026` | Required original encrypted complete state, private HMAC key, separate baseline/adoption/restart observations and diagnostic failures |
| `operator-control/homepage-recovery-metadata.tar.age` | Fully authenticated parent recovery metadata, also verified on NAS |
| `operator-control/homepage-audit-supplement.tar.age` | Distinct authenticated integrity/revalidated-scan supplement, also verified on NAS; no ancestor/database duplication |
| `operator-control/homepage-*-reconciliation.json`, `homepage-protected-input-recheck.json`, `public-db-integrity-preservation.json` and their control sources | Exact initial failure, preservation and final successful cleanup evidence |

All earlier exclusions, other owners' artifacts, active publisher state and
rollback/source inventories remain retained. No old copy was removed by name or
age inference. [Deployment, recovery and security limitations](UPSTREAM-HOMEPAGE-ADOPTION-20261026.md).

## Same-root capacity extension, October 26 01:46 UTC

The same owned raw ext4 backing file grew online from 144 GiB to 152 GiB;
UUID, mount point, loop device and backing-file inode remain unchanged. Before
the additive 8 GiB operation, C: had 103071784960 bytes available and F: passed
the 15 GiB retained-space floor after the full growth estimate. Exact physical
measurements and commands are in `operator-control/native-filesystem-grow-8g-`
`{preflight,receipt}.json`. Native available space changed from 17824870400 to
26280062976 bytes. This is increased Linux capacity, not reclaimed Windows
space. No VHDX compaction, shutdown, workload stop, output move or extra root
was involved. The same file `F:\branconet-build-storage\native-build-20261025.ext4`
continues to own all generated paths below. Source and original recovery data
were not moved or modified.

The Homepage stage is owned by the same maintenance chat and uses only
`upstream-homepage-20261026`, `control-source/upstream-homepage-20261026`,
`operator-control` and the existing `security-review-20261026`. Its exact
regeneration and preservation contract is recorded in
[the stage plan](UPSTREAM-HOMEPAGE-ADOPTION-20261026.md). Scanner analysis scratch
has been recreated for the new finite vendor scans and will be reconciled at
this checkpoint; prior cleanup receipts describe their earlier lifecycle.

## Static-site checkpoint reconciliation, October 26 01:43 UTC

This checkpoint reused the same F:-backed root below. New required children are
`security-review-20261026`, `upstream-static-sites-20261026` and
`control-source/upstream-static-sites-20261026`; controls and receipts reuse
`operator-control`. No build, dependency installation or additional output root
was introduced. [Exact adoption and authenticated recovery](UPSTREAM-STATIC-SITES-ADOPTION-20261026.md).

The first cleanup check failed closed because Linux Git could not interpret the
Windows worktree's Git pointer. The second exposed the app-visible charts path's
Windows redirection. Neither attempt deleted anything. Native Windows Git
verification established the canonical repositories, tracked sources and lockfile
hashes; the corrected check verified those same files from WSL. Both original
failure receipts and all source versions remain. These were local safety-check
failures, not automatic approval-review rejections.

After all scanner/backup/copy processes were terminal, root-visible process FD,
map and mount checks, exact ownership/inode/path checks, source/lock preservation
and protected tool/database/report hashes passed. Only these inactive,
reproducible current-stage paths were removed, relative to the declared root:

| Exact removed path | Allocated Linux bytes |
| --- | ---: |
| `security-review-20261026/cache/fanal/fanal.db` | 929792 |
| `operator-control/tmp/ansible-home` | 4096 |
| `operator-control/tmp/ansible-local` | 4096 |
| `operator-control/tmp` | 4096 |
| `security-review-20261026/tmp` | 4096 |
| `security-review-20261026/home` | 4096 |
| `security-review-20261026/cache/fanal` | 4096 |

Total: **954368 allocated Linux bytes**. This is not a Windows disk-recovery
claim; no shutdown or compaction ran. The exact receipt and regeneration command
are `operator-control/static-sites-scratch-reconciliation-r3.json`. Recreating
the analysis cache uses the recorded immutable-image scanner command and retained
inputs with a new output report path, preserving the original result. Empty
private TMP/HOME directories are recreated explicitly only when needed.

Retained exceptions, relative to the same root:

| Exact retained path | Reason |
| --- | --- |
| `security-review-20261026/cache/db` | Current immutable advisory DB required for remaining fleet review |
| `security-review-20261026/cache/java-db` | Current immutable Java identification index required for remaining fleet review |
| `security-review-20261026/docker-config` | Isolated scanner configuration; exact creation provenance not separately reconciled |
| `security-review-20261026/nginx-0` | Unique initial scanner failure evidence |
| `security-review-20261026/java-inputs-receipt.json` | Original bounded pre-download failure evidence |
| `control-source/upstream-static-sites-20261026` | Original and corrected observers/backup sources, manifests and recovery provenance |
| `upstream-static-sites-20261026` | Complete original encrypted backups, private key and distinct baseline/adoption/restart/failure observations |
| `operator-control/static-sites-recovery-metadata.tar.age` | Required fully authenticated recovery metadata, also verified on NAS |
| `operator-control/static-sites-scratch-reconciliation*.json` and corresponding control sources | Unique initial failed checks and successful cleanup proof |

The refreshed `operator-control/storage-inventory-current.json` classifies all
222 current top-level paths. All older source/failure/rollback exceptions, other
owner artifacts and active publisher state below remain preserved. The new
public DB inputs are required current security-review state, not orphaned copies.

The existing authorized generated-output root is retained:

`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`

Windows accesses that same filesystem through
`\\wsl.localhost\Ubuntu\home\brajam\.local\share\branconet-migration\local-image-build-offload-20261025`.
It is ext4 UUID `3c792469-ea0e-4a2c-98e8-1185b141607b`, backed by
`F:\branconet-build-storage\native-build-20261025.ext4`. The owner of this
maintenance work is chat `01a12045-bf7e-73b3-8557-752d17c72ffd` and branch
`codex/cluster-maintenance-ansible`. All new operator scratch and receipts use
the existing `operator-control` directory inside this root. No new build,
dependency copy or scanner-cache root is created on C:, D: or another volume.

The earlier `F:\branconet-migration-artifacts\maintenance-storage-20261025`
contains protected execution/source evidence and the already-running local
charts publisher's persistent state. Preserve those existing owners and active
paths; do not migrate or duplicate them. New disposable work uses the declared
ext4 root. Existing application/source repositories, Kubernetes runtime data,
NAS media, encrypted backups and rollback archives remain protected.

The private, current hierarchical inventory is
`operator-control/storage-inventory-current.json`. It enumerates current
top-level paths and retains descendants with an explicit owner/reason or failed
safety check. BORTUS application work belongs to its separate owner. Source and
execution snapshots without an established regeneration manifest, unreadable
builder state, and paths without proved ownership/inactive references remain
retained. Their names alone never authorize deletion. A broad allocation walk
encountered unreadable builder directories; its result is incomplete and is not
a filesystem or Windows recovery claim. The inventory is a reconciliation record,
not a claim that every historical generated artifact has been cleaned.

At October25 22:12 UTC, a root-visible process/FD/map/mount check and exact
empty-directory checks allowed removal of these four owned scratch directories:

| Path relative to the declared root | Allocated bytes removed |
| --- | ---: |
| `operator-control/ansible-local` | 4096 |
| `operator-control/cache` | 4096 |
| `operator-control/home` | 4096 |
| `operator-control/tmp` | 4096 |

Total Linux filesystem recovery was **16,384 allocated bytes**. No Windows disk
recovery is attributed to this operation. Exact checks and per-path regeneration
commands are retained in `operator-control/empty-scratch-cleanup-20261025.json`.
The source and lockfile repositories survive; no tracked files, dependencies,
runtime artifact or unique evidence was removed. This small reconciliation is
separate from the earlier 55,587,958,784-byte verified node cleanup.

No local build or large controller download is part of the current stateless
upstream transition. Before the remote runtime pulls, measured C: free space was
113,524,342,784 bytes, the native output filesystem had 22,173,327,360 bytes
available, and every node could retain 15 GiB after a 2 GiB runtime-stage bound.
The actual measurements remain in `operator-control/stateless-capacity-preflight.json`.
Future build stages must configure compiler/cache/temp paths in the declared
root, and npm must receive process-scoped cache/log/AppData paths before launch.
No npm build was invoked here. Recreate required empty temporary directories
explicitly before a stage; reconcile them again afterward.

## Successful primary compiler-cache cleanup, 22:23 UTC

The three successful primary local builders for http-echo, Whoami and Unpackerr
passed complete OCI archive/blob checks, source/recipe hashes, retained Git
commit checks, live Docker/process/map/mount inspection and exact-path/inode
checks. Six generated cache directories were removed with fd-relative,
symlink-resistant deletion. No older copied cache, failed state or other chat's
builder was included. A final full comparison proved every protected recipe,
source file, log, metadata file and OCI archive unchanged.

| Path relative to the declared root | Allocated bytes removed |
| --- | ---: |
| `http-echo-ff0892f93064-79c5c595f699/state/runc-overlayfs/content/blobs` | 47149056 |
| `http-echo-ff0892f93064-79c5c595f699/state/runc-overlayfs/snapshots/snapshots` | 592498688 |
| `whoami-d3adf8da75b5-b61a99ebb346/state/runc-overlayfs/content/blobs` | 53489664 |
| `whoami-d3adf8da75b5-b61a99ebb346/state/runc-overlayfs/snapshots/snapshots` | 957849600 |
| `unpackerr-e91ac1375ec9-8948f8318133/state/runc-overlayfs/content/blobs` | 72339456 |
| `unpackerr-e91ac1375ec9-8948f8318133/state/runc-overlayfs/snapshots/snapshots` | 1180573696 |

Generated-layer removal totaled **2,903,900,160 allocated Linux bytes**;
including the four empty directories, this checkpoint removed **2,903,916,544
allocated bytes**. Native available space was observed changing from
21,994,999,808 to 24,898,752,512 bytes during the larger operation; concurrent
filesystem activity means that difference is reported separately from the
measured deleted allocations. No Windows recovery or compaction is claimed.

[Exact public deletion receipt](../evidence/controller-generated-cleanup-20261025.json).
The private cleanup plan includes protected-file hashes and exact historical
regeneration commands. Those commands document reproducibility; they do not
authorize new third-party derivative builds. All other existing root paths
remain classified in the current private inventory, with retained evidence or
concrete unfulfilled safety/ownership checks. No data, runtime image, source
repository, encrypted backup or recovery artifact was pruned.

## Media checkpoint scratch reconciliation, 23:27 UTC

No compiler or dependency caches were created. Backup archives, their distinct
API/SQL observations, frozen sources, keys and encrypted NAS metadata remain
required recovery/acceptance evidence under the declared root. Raw new receipts
are retained there; repository documentation records concise results/pointers.
After the Ansible syntax check and all copy/observation processes finished, the
empty generated scratch tree passed complete process/map/mount and inode checks:

| Removed path relative to declared root | Allocated bytes |
| --- | ---: |
| `operator-control/tmp/ansible-home` | 4096 |
| `operator-control/tmp/ansible-local` | 4096 |
| `operator-control/tmp` | 4096 |

This new lifecycle removed **12,288 allocated Linux bytes**, with no Windows
recovery claim. The original sources, all archives and prior cleanup receipts
remain. Exact proof is `operator-control/media-scratch-reconciliation.json`.
Recreate the configured empty paths explicitly before a future Ansible stage.
The current private inventory includes the new protected media acceptance/
backup subtree; every earlier retained exception keeps its documented reason.

## Unpackerr checkpoint reconciliation, 23:54 UTC

All paths below are relative to the declared F:-backed ext4 root. Exact proof:
`operator-control/unpackerr-scratch-reconciliation.json`. After source/hash,
ownership, inode and complete process/map/mount checks, these current-stage
reproducible binary/payload files and empty scratch directories were removed.
No build or dependency cache was created.

| Removed path | Allocated bytes |
| --- | ---: |
| `upstream-unpackerr-20261025/vendor-unpackerr` | 19034112 |
| `unpackerr-fixture-y0n8j8as/unpackerr` | 19034112 |
| `unpackerr-fixture-y0n8j8as/downloads/Branconet.Unpackerr.Disposable.Fixture/fixture.zip` | 8192 |
| `unpackerr-fixture-y0n8j8as/downloads/Branconet.Unpackerr.Disposable.Fixture/original-download.nfo` | 4096 |
| `unpackerr-fixture-y0n8j8as/outside-sentinel.txt` | 4096 |
| `unpackerr-fixture-y0n8j8as/mock-library/Subs/fixture.srt` | 4096 |
| `unpackerr-fixture-y0n8j8as/mock-library/movie.mkv` | 4096 |
| `unpackerr-fixture-y0n8j8as/mock-library/Subs` | 4096 |
| `operator-control/tmp/ansible-home` | 4096 |
| `unpackerr-fixture-y0n8j8as/downloads/Branconet.Unpackerr.Disposable.Fixture` | 4096 |
| `operator-control/tmp/ansible-local` | 4096 |
| `operator-control/tmp` | 4096 |
| `unpackerr-fixture-y0n8j8as/mock-library` | 4096 |
| `unpackerr-fixture-y0n8j8as/tmp` | 4096 |
| `unpackerr-fixture-y0n8j8as/downloads` | 4096 |

Total: **38,125,568 allocated Linux bytes**. No Windows disk recovery is claimed.
The exact source/command and required failed-fixture binary survive for
regeneration; use the command in the private reconciliation receipt under the
same bounded isolated user scope. Config/source manifests, keys, all encrypted
archives, NAS copies and unique observations/logs remain protected.

Retained current-stage exceptions:

- `unpackerr-fixture-7zb5sjyf`: Preserve the complete failed toolchain-guard fixture and its exact binary input; no failed-state cleanup authorized.
- `unpackerr-fixture-y0n8j8as`: Unique passing result, execution logs and exact runtime fixture config retained; reproducible binary/payload copies removed.
- `upstream-unpackerr-20261025`: Required configuration backup, native verification key, before/after/restart receipts and distinct failure evidence retained.

All previous retained exceptions remain unchanged. No older artifacts, runtime
images/volumes, NAS media, source repositories or other owners were pruned.
Explicitly recreate configured operator scratch before a future Ansible stage.

## phpMyAdmin checkpoint reconciliation, October26 00:20 UTC

No build, dependency install, source-tree dependency copy or local image export
ran. All new controls, private observations and distinct recovery archives are
inside the declared F:-backed ext4 root. The SQL/HTTP checks kept account data,
credentials, cookies and response bodies in memory. Exact current receipt:
`operator-control/phpmyadmin-upstream-adoption.json`.

After every producer and NAS copy completed, the empty scratch directory passed
ownership, inode, process/FD/map/mount and root containment checks:

| Removed path relative to declared root | Allocated bytes |
| --- | ---: |
| `operator-control/tmp` | 4096 |

Exact proof: `operator-control/phpmyadmin-scratch-reconciliation.json`.
This is **4096 allocated Linux bytes**, with no Windows disk recovery claim.
Regenerate by explicitly creating the private operator-control/tmp directory
before the recorded metadata encryption/copy commands.

Retained current-stage exceptions:

- `upstream-phpmyadmin-20261025`: required verification key and unique original,
  after/restart SQL/login observations, including failed verification evidence.
- `control-source/upstream-phpmyadmin-20261025`: exact executed source versions
  needed to reproduce both the failed checks and accepted behavior.
- `operator-control/phpmyadmin-before-recovery-metadata.tar.age` and
  `operator-control/phpmyadmin-final-recovery-metadata.tar.age`: required distinct
  authenticated recovery evidence with verified NAS copies; final archive does
  not duplicate the baseline/key/source ancestor bundle.
- `operator-control/phpmyadmin-existing-vendor-findings.json`: required exact
  package/advisory rows and original prior-scan bindings; current security review
  is incomplete. Original scanner inputs/reports and rollback images survive.

Existing publisher state and every earlier retained ownership, safety-check,
failed-state and runtime exception remain unchanged. No PVC/NAS data, source
repository, model, image, volume, other project or older artifact was pruned.
