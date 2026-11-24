# Local WSL Docker storage on H

Owner: BORTUS Delivery and Cluster Operations. This is local development and
review infrastructure, separate from the production Kubernetes runtimes.

## Physical storage

The existing approved Linux filesystem is mounted at
`/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files`.
Its backing file is
`H:\AgentArtifacts\projects\branconet\builds\wsl-artifact-store\branconet-artifacts.ext4`.
Docker and containerd must both use this filesystem; changing only Docker CLI
caches, logs or environment variables does not relocate image content.

The initial migration exhausted this store's 81,920 inodes while byte space
remained available. Its existing filesystem was expanded online from 160 GiB to
384 GiB, giving 196,608 inodes, without a new mount or WSL interruption. The NTFS
extension allocated approximately 240.5 GB physically; the backing file is now
marked sparse for subsequent allocation. Online discard is unsupported on this
loop/DrvFS path, so the physical reservation has not been reclaimed. Preserve the
live backing file and active jobs; do not punch guessed ranges or claim that
virtual free space is host free space. Check both host space and free inodes
before admitting another stage. This shared filesystem capacity does not enlarge
any repository's artifact allowance.

The same sparse file was subsequently grown online to 2.5 TiB logical capacity
to address the unusually low inode density without a new disk or mount. It now
has 1,310,720 inodes; 1,178,788 were free at acceptance. The verified sparse EOF
extension itself allocated zero data bytes, and ext4 metadata growth added
102,170,624 physical bytes. Host free space must still be checked independently;
the sparse logical size is neither physical free space nor repository allowance.
`scripts/migration/expand-shared-h-artifact-inodes.py` preserves the existing
UUID and verifies actual loop capacity before resizing. Its recorded correction
avoids Windows Python's zero-filling `truncate` behavior by using native EOF.

The shared runtime directories beneath that mount are:

- `shared-docker-runtime/docker`: Docker metadata, build cache and container state.
- `shared-docker-runtime/containerd`: image content, metadata and snapshots.
- `shared-docker-runtime/configuration-backup`: preserved original service configuration.
- `shared-docker-runtime/migration.json`: actual migration state and admission evidence.
- `shared-docker-runtime/source-retirement.json`: exact old paths removed and measured Linux recovery.

These are shared runtime storage, not another source checkout or a per-chat
artifact allowance. Attribute images and containers to their projects; the
current allowance is 100 GB = 100,000,000,000 bytes per repository, approved by
James during this work. The 15 GiB free-space floor and per-project accounting
still apply. No filesystem quota is claimed. Repository jobs need actual write
access to their admitted H output directories; private Docker internals and
credentials must not be made world-writable to provide that access.

## Migration and startup protection

`scripts/migration/migrate-local-docker-to-h.py` requires an idle local Docker
runtime, verifies the H backing file, preserves existing images and configuration,
and copies both stores with metadata and checksum verification. It updates
Docker's `data-root`, containerd's `root`, and both systemd units' dependencies
on the existing H mount. Startup checks fail if that ext4 mount is unavailable;
the runtime must not silently create a replacement cache on C.

The script stops only the idle local Docker/containerd services, not WSL,
Windows applications, models or production nodes. Activation failure restores
the original configuration and services while preserving the copied state.
Existing destination state must be reconciled rather than overwritten.

After successful activation,
`scripts/migration/retire-local-docker-c-source.py` verifies the live H roots
and absence of consumers before retiring exactly `/var/lib/docker` and
`/var/lib/containerd`. It preserves the H runtime and configuration backups.
It uses no forced or lazy unmount and performs no image or volume prune.
Linux space recovery is recorded separately from Windows C free space; this
operation does not compact or shut down WSL.

## BORTUS review lifecycle

Reuse the already-qualified image for the local review. Do not rebuild the image
or copy dependency trees. Keep the review endpoint on loopback, with separate
synthetic state and no production credentials. Deploy only after the established
review and release requirements pass. After production deployment and verification,
remove the exact review container and its exclusively owned local image copy,
checking for other consumers first. Preserve necessary source and minimal records.

See [the current BORTUS handoff](handoffs/current-bortus.md) for source, image
identity, current ownership and remaining release acceptance.

## Certificates & Trust build admission — 2026-11-16

**Decision: new dependency/build bulk is not admitted.** This is separate from
the completed 2026-11-15 release. The old existing-image review exception does
not cover the certificate feature's install/build/runner qualification.

| Retained scope | Evidence / attribution | Measurement and disposition |
| --- | --- | --- |
| H `projects/bortus` | Packaged BORTUS source/security history plus the mixed homelab recovery capsule | 88,017,201,245 path-summed logical bytes; no enumeration errors, two reparse entries skipped. Not allocation/hardlink deduplication. |
| `native-build-20261025.restic`, included above | `SWARM-native-image-restic.json`: BORTUS/cluster operations owns full mixed-member recovery until replacements/regeneration are established | 53,920,129,364 bytes in the preservation receipt. Charge the held capsule once conservatively; do not exempt it or add the retired 163,208,757,248-byte raw image again. No new mount or raw restoration is authorized. |
| Legacy physical `next-security-01a1740e` | BORTUS application security inputs and protected runtime/failure evidence; separate from its H-linked siblings | 12,233,007,104 readable allocated bytes; private subtrees have measurement gaps. Retain exact refusals/protected inputs. |
| Legacy physical `bortus-delivery` | BORTUS application delivery source/recipes/history | 4,350,091,264 allocated bytes. Prior generated-child cleanup remains completed; no blanket retirement of source/history. |
| Legacy physical runtime, all direct children | Mixed cluster/application producers; no-follow measurement excludes H targets behind aliases | 48,362,647,552 readable allocated bytes at root. The two preceding rows are included, not additive. Eight inaccessible subtrees prevent a complete measurement. |
| H `projects/branconet/runs` | Mixed coordinator records and cross-project migration receipts | 5,065,832,821 logical bytes after exact archive retirements, derived from the complete enumeration and exact deletion sizes. Not automatically all chargeable to this repository. |
| Mounted shared store | Homelab history, charts publisher, Veyra tools and shared Docker | Producer-specific accounting required; backing sparse-file allocation is not additive payload. No shared image/cache/volume deletion based on location or reclaimability. |

The two newly retired outer staging archives reclaimed 4,979,916,800
logical/allocated bytes. Their payloads, compatibility aliases and original
verification receipts remain. V2–v8 failed-run dependency inputs remain
protected by the existing v9 cleanup disposition; they are not a free pool
for deleting old dependencies. No new quota or compliant total is claimed.

The current frontend lock has 580 package entries; the conservative
Linux/x64/glibc selection has 504 install locations / 495 distinct manifests,
including optional candidates. Registry version/integrity checks matched.
472 manifests supplied unpacked sizes; 23 old packages lacking that field
were bounded, integrity-checked and inspected in memory (170,479 compressed
bytes; none saved/extracted). The selected logical unpacked sum is
834,617,149 bytes, not a measured installed tree or complete peak estimate.

A proposed **4,000,000,000-byte incremental qualification ceiling** would
reserve 1.4 GB for the sole current-lock dependency/generated-client tree,
1.0 GB for package cache/install temporaries, 1.4 GB for Next/native/worker
output, and 0.2 GB for synthetic state/logs/runner checks. Reuse the authoritative
source and existing H roots; no new checkout or dependency copy. Refuse a
substage that cannot fit its remaining reserve. This is a proposed bounded
stage, not an observed peak, filesystem quota, permission to spill elsewhere,
or authorization. It requires either verified normal admission or a **fresh
explicit exception** while protected legacy attribution is reconciled.
Deployment, production data, credential/admission changes and later renewal
operations remain outside this proposed stage.

An input probe mistakenly omitted `--pull=never` when a previously listed Node
tag became unavailable; Docker began fetching it and the CLI timed out. The
runtime remained on the existing H root. The eventual image identity is the
same `c4d55230…` listed before the probe; no distinct exclusively task-owned image
ID was established, so a shared image was not deleted to conceal the event.
Incremental physical growth is unmeasured, not claimed zero. Its concrete
consumer is the pending pinned Linux qualification build; reconcile consumers
before eventual retirement. No build/dependency install ran. A subsequent
read-only, network-disabled, `--pull=never` check of that exact ID verified all
10 pinned Node/compiler/subtool/header hashes (Node 22.23.3, zero mismatches).
The probe container was removed; no shared services were stopped.

### H retry: transport/filesystem fault, not free-space exhaustion

James requested retrying H after the bounded-stage question. The retry retained
the proposed 4,000,000,000-byte ceiling and did not start an install/build.
Windows reports H available with 390,930,190,336 free bytes, and native Windows
`Get-Item` can read both the existing sparse backing-file metadata and the
existing coordinator `temp` directory.

WSL's existing `/mnt/h` is still a 9p/DrvFS mount of `H:`, but accessing those
same ordinary paths returns `ENODEV` (19, No such device). The nested existing
`files` mount remains `/dev/loop0` ext4. Its cached `statvfs` reports apparent
capacity, but accessing its `branconet-history` and `bortus-operator-recovery`
directories returns `EIO` (5). Kernel logs show loop0 read/write errors,
`Aborting journal on device loop0-8`, lost journal-superblock writes and
`EXT4-fs ... I/O error while writing superblock`. Free bytes alone therefore
do not establish a usable build destination. No data-loss conclusion is made.

Do not write there, run fsck against a mounted filesystem, detach the backing
device, restart WSL, or restart shared services as an exclusively task-owned
tool repair. `dockerd` PID 372 and `containerd` PID 243 are shared root-owned
services; the process snapshot showed no containerd shims, but that is not an
authorization to interrupt another owner's work. A coordinated maintenance
decision is required to establish idle consumers, refresh the **existing**
H transport/mount and inspect the **existing** store offline before deciding
whether filesystem repair is necessary. Preserve the backing file, source,
credentials, all retained evidence and other workloads. Do not add a new disk,
mount location, checkout or alternate output root to hide the fault.

### Post-restart recovery and bounded retry

The later server restart also restarted WSL externally; this agent did not
stop services or perform mount/filesystem repair. In boot
`e72801ac-8c43-458f-86b4-5e74f9c4a756`, H/backing-file/store metadata reads work,
loop0 reports zero errors/zero first/last error times, and JBD2 reports
committing transactions. A 65,536-byte exclusive file write, fsync, readback,
unlink and directory-fsync passed under the existing store; the probe is gone.
This supersedes the immediate availability hold, not the incident record or
legacy accounting. James's directed retry remains bounded by the 4 GB stage
described in the question; no global allowance or deployment change is inferred.

`scripts/migration/qualify-certificate-frontend.py` implements that retry in
the existing `bortus-operator-recovery/certificates-qualification-20261116`
child. It reuses the exact local Node image with pull disabled; source is
read-only, the sole dependency tree and generated output are H bind mounts,
and package/index hashes must remain unchanged. Empty ignored source
directories are routing mountpoints, not copied source or dependency trees.
The native C and worker inputs are read-only file mounts, not H source copies.
It refuses existing step evidence instead of replaying it and checks a
substage reserve, total stage allocation, 15-GiB free-space floor and store
errors. Each container has 2 CPUs, 1 GiB/no swap, PID256, no capabilities and
no production credentials. The ceiling uses measured guard checks, not a
claimed filesystem quota; review logs/results and clean eligible output at
each checkpoint. No full application or runner acceptance is implied by setup.
Before launch, each step saves a source/config fingerprint and started record;
completion must match that fingerprint as well as the lock/index. Interrupted
steps are reconciled from their existing container/logs rather than replayed.
The first prebuild attempt exposed the pinned compiler's sanitized environment:
with `/tmp` read-only, GCC refused its temporary files even though the Node
driver's TMPDIR was on H. The driver now binds the same H temp directory to
container `/tmp`, preserving compiler pins/environment. Named `--attempt`
corrections retain earlier failed logs/results and reuse the same dependencies
and stage ceiling; do not rerun completed install/generation for this correction.
After real page/lint corrections, combined Next lint/type workers hit Node's
default ~512-MB heap. The container remains limited to 1 GiB/no swap and two
CPUs. The supported serial path runs unfiltered `npm run lint` first and
refuses `build-serial` unless that result passed on the exact same source
fingerprint. Only then does Next use its documented `--no-lint` option,
retaining type validation, with a 768-MB process heap inside the unchanged
cgroup. This splits mandatory gates; it does not waive lint, change production
configuration, raise the container limit or claim that default `npm run build`
passed. All failed combined-worker logs remain.
The serial whole-checkout type worker also exhausted 768 MB. Inspection found
the actual release `.dockerignore` already excludes `tests`, whereas the
in-place checkout exposed that entire corpus to Next's `**/*.ts` discovery.
`build-context` therefore mounts an empty read-only H directory over `/work/tests`
only for the build, after verifying that exact existing ignore rule and binding
its hash. It changes/deletes no test source and adds no new exclusion to the
product. Full-checkout ESLint remains a required matching-source pass; Next
still validates application/generated-route types. This is release-context
build qualification, not a claim that whole-checkout test typechecking passed.
`fixture` requires a matching successful context-build receipt and exposes
only loopback listeners for the real Next application/synthetic authorization
fixture. Its state remains in the same capped H stage.
Named fixture attempts now select fresh application-state directories, retaining
prior synthetic metadata/results and the identical built frontend. After the
first clean fixture shutdown, exact synthetic payload cleanup reclaimed 319,488
allocated bytes. Separately admitted `npm` and `next/cache` cleanup completed:
234,057,728 + 227,749,888 = 461,807,616 allocated bytes removed. The stage
remeasured 1,218,887,680 bytes before its small receipt. Installed dependencies,
built runtime and unique logs/results/screenshot remain for outstanding
responsive/accessibility/release checks. No new global allowance is inferred.
The actual phone viewport exposed metadata text overflow, requiring a focused
styling correction and new matching lint/build. Explicit `--lint-attempt` and
`--build-attempt` select named immutable receipts for corrected source; previous
successes/failures remain intact and cannot substitute for a matching hash.
The same dependency tree, stage ceiling and resource limits remain in force.
The later phone-a11y lint/build passed on the new source, with a
1,446,993,920-byte observed build stage peak. Phone fixture shutdown was clean.
After checking all task containers/mount consumers absent, exact regenerated
`next/cache` and three attempts' nine synthetic SQLite/kubeconfig/CLI files were
removed: 228,614,144 allocated bytes. `responsive-cleanup-result.json` records
the targets and retained stage measurement of 1,219,219,456 bytes before its
small receipt. Source routing directories/link were removed. Current built
output/dependencies remain for attended-reader/release qualification; unique
logs/results/screenshots/public metadata remain. No global allowance changes.

Independent-runner qualification also stays in that same capped stage: source
and unit/playbook remain in the authoritative repository, tests use temporary
H-only synthetic state with automatic teardown, and no dependency copy/install
was made. The candidate result binds seven source paths; 18 tests passed.
Two empty test/syntax temp directories were removed (8,192 allocated bytes).
The new actual Ansible preflight's first local RPC startup failed before tasks
under the long H temp path. Reusing the repository's abstract multiprocessing
Unix-address pattern corrected it without moving outputs off H. Read-only
node02 preflight passed (changed=0/failed=0), then its empty controller temp was
removed (4,096 bytes). Logs and both failure/success records remain. Stage usage
was 1,219,252,224 bytes before the small preflight receipt. No shared service,
mount, runtime configuration, token or production file was changed.

## Existing charts watcher output repair

The existing `Branconet Charts Local CI` scheduled task retains its registered
wrapper and protected control state at
`F:/branconet-migration-artifacts/maintenance-storage-20261025/branconet-charts-local-ci-state`.
Its `owner.json`, status, historical attempts and kernel singleton lock stay in
place; this repair does not move or reset live state. The dedicated source
checkout remains `C:/Users/james/.codex/local-ci/branconet-charts-local-ci`.

The maintained wrapper source is
`scripts/migration/charts-local-ci-watch-with-wsl.ps1`. New stdout/stderr and
Windows temporary output use `logs/charts-local-ci` and `temp/charts-local-ci`
inside the existing H coordinator run
`H:/AgentArtifacts/projects/branconet/runs/branconet-wsl-stage-20261113T215208Z`.
Native Linux stages use `local-charts-publisher` beneath the existing ext4
`files` mount described above: same UUID, private mode0700 and brajam ownership.
This directory's producer is `jtmb/branconet-charts`; its path does not give it
a second budget or exempt mixed artifacts from accounting.

Run the registered wrapper with `-ValidateOnly` for a no-launch configuration
check. It checks the exact H volume, retained free-space floors, original owner
and installed `--stage-root` capability. It starts no keeper, publisher or task.
The normal path refuses before launch while the old F-only scripts remain
installed. The two committed CI scripts must first receive the reviewed explicit
H configuration and reach this same clean automated checkout; do not monkey-patch
their globals, bypass their committed-source checks or remount retired storage.

The wrapper repair alone does not publish a chart or image, start another
publisher, unsuspend a release or establish Flux acceptance. Keep the original
atomic current-main validation/promotion and no-same-SHA-retry rules. The repair
receipt and original wrapper backup are in the same H run. No scheduled-task
registration, credentials, Actions setting or application manifest is changed.

### Current publisher observation during credential qualification

The earlier source-install hold is now superseded by current read-only evidence:
the installed watcher supports `--stage-root`, the existing scheduled task is
Running, and it successfully validated/published private source
`7e1c6c9eab42ead78f77c374a5a1cc555196bfd3` from H. This credential step did not
restart/reconfigure the task or repeat its installation. Its 35 tests/full
validator and publication receipts were hash-checked before Flux acceptance.

Credential qualification reused the same H frontend stage, with synthetic
tokens/tests and fresh private live diagnostic children. All real candidate/
active diagnostic token files, temporary kubeconfigs and public CA files were
removed after each terminal attempt; only metadata receipts remain. Two empty
test/syntax directories were separately removed (8,192 allocated bytes).
The frontend qualification stage measured 1,219,338,240 bytes, and this
current charts publisher stage measured 180,113,408 bytes: conservatively
1,399,451,648 bytes combined, still below 4 GB without a new root/checkout or
dependency tree. This is not normal global storage attribution or a new quota.
The chart stage remains the current exact-source publication/Flux-proof
consumer; review its generated payload after that checkpoint is superseded,
preserving the source-bound receipts and existing publisher ownership.

Node02 broker qualification reused the existing stage and installed host
runtime only; no image/dependency build or new checkout occurred. Completed
initial staging's empty controller directory
`certificates-qualification-20261116/node02-staging-temp` was verified empty,
owned and without an active Ansible controller, then removed: 4,096 allocated
bytes. All staging logs, original failed collector receipts and corrected
resource/boundary receipts remain. Stage usage was 1,219,440,640 bytes before
its small cleanup receipt. Installed `/run` token is the current credential
timer's consumer, not disposable diagnostic data; do not remove it while
qualifying periodic refresh. The read-only journal observer subsequently
completed successfully; only its small metadata result/hash-bound summary were
added. It retained no token copies or temporary credential files. The installed
runtime token remains the enabled credential timer's consumer.

Monitor/notification preparation used only the same H stage and existing
Python/OpenSSL tools. Eight tests created synthetic SQLite, credentials and
an ephemeral loopback TLS certificate/key, all removed after their exact test
consumer exited. The admitted empty `notification-prep-tests` directory was
then removed (4,096 allocated bytes). Logs/source-bound metadata remain;
qualification plus current publisher stages measured 1,399,603,200 bytes before
the small preparation receipt. No dependency/build copy, new artifact root,
ntfy installation, host update or live alert occurred. The proposed volatile
monitor cache is a source-only unit change, not a new mounted store or an
increase in the existing allowance.

The next inactive ntfy/watchdog preparation reused the same H stage and
checksum-matched Helm/kubectl/Gitleaks binaries from the retained current
publisher stage; no new binary/image/dependency copy or checkout was made.
Temporary private-checkout `.tools`/`.validation` links routed tool access and
validator reports to H, then were removed exactly. Full validation reports,
selected tests and the upstream token-contract correction log remain. Synthetic
test keys/credentials/DBs are gone. Six verified empty test/validator temp/cache
directories were removed (24,576 allocated bytes). Combined current stages
measured 1,399,656,448 bytes before the small result receipt. The proposed
1 GiB Longhorn claim and runtime volumes are manifest-only; nothing was
allocated, mounted or applied, and no normal-global-accounting claim follows.

### Isolated real ntfy runtime qualification

The user next authorized actual pinned-server TLS/ACL qualification. Initial
registry metadata verified about 36,983,490 compressed layer bytes. One exact
amd64 image was acquired on the existing H daemon/containerd; later corrected
attempts reused it with pull-never. A conservative **1 GB complete incremental
runtime/image reserve**, including expansion/metadata/test peak, was admitted
inside the same 4 GB stage above its 1,399,672,832-byte baseline. Host H free
space was 382,681,219,072 bytes and loop0 error count zero. No new root, mount,
checkout or dependency tree was introduced.

Direct stat of protected Docker internals returned permission denied; no
permissions were weakened or alternate privileged read attempted. The public
daemon and containerd configurations independently point at the existing H
store; Docker API supplies only public image/runtime metadata here. No complete
physical/private-root attribution or physical quota enforcement is claimed.

The first two collector/environment failures (manifest-vs-config image ID,
internal-network host publish unsupported) remain. Real TLS/ACL/subscriber/
restart checks passed in the separately recorded loopback-byte-forwarder run,
without external network access or TLS termination at that forwarder.
All exact containers/networks/forwarders are gone. Fourteen admitted synthetic
TLS/auth/cache/env/config targets were removed: **643,072 allocated bytes**.
Source stage measured 1,219,633,152 bytes before its cleanup receipt; minimal
results/sanitized logs remain.

Retain only the exact ntfy child
`sha256:6ceb27333175e3ce7d021bb883658858f2b8b883db316a73d0755dfa0b306fc4`
for the outstanding exact-image vulnerability qualification before rollout.
Its reported 36,988,086 content bytes are not unpacked/physical allocation;
continue charging the conservative 1 GB reserve until that image's local
security/authorized consumers finish, then review/retire the exact reference.
No broad prune, deletion of shared layers or second image copy is authorized.

### ntfy secret scan and fresh advisory DB admission

The approved existing worker scanner was reused from its preserved H alias.
The exact retained image was exported once (36,996,608 bytes) and all original
manifest/config/layer bytes verified, without image execution or another pull.
The export and scanner workspace were charged inside the unchanged 1 GB
runtime reserve. Secret-only qualification passed, without an advisory DB.
Retain the exact image **and that verified export** only for the pending CVE
consumer; do not recreate them or replay the passed fixture/secret scan.

Six separately admitted obsolete targets were removed: prior
`certificates-qualification-20261116/tmp/node-compile-cache` and
`ntfy-security-secrets/{cache,tmp,home,docker-config,redaction-input.json}`.
Measured reclamation: **16,052,224 allocated bytes**. Finished task service,
container mounts and visible FDs were checked; other-UID proc visibility gaps
remain disclosed. Source/lock/index, current app dependencies/build, publisher
checkpoint, unique metadata/results/logs and immutable old DB are preserved.

Current conservative calculation after that cleanup:

| Component | Bytes |
| --- | ---: |
| Retained qualification + current publisher (includes export) | 1,420,963,840 |
| Full carried image/runtime reserve (unchanged) | 1,000,000,000 |
| Proposed fresh uncompressed DB | 1,773,903,872 |
| Charged total before further small receipts | 4,194,867,712 |
| Excess above authorized 4 GB stage | 194,867,712 |

This is conservative admission accounting, not measured protected-Docker
physical allocation. Fresh DB is **not admitted or downloaded**. The old DB
cannot establish current CVE approval and cannot be overwritten. A proposed
**4,250,000,000-byte one-stage exception** would permit full-layer-hashed
streamed extraction with no retained compressed carrier, preserving the same
1 GB reserve. It requires James's explicit decision; no exception/global
increase/new root/mount/checkout was inferred. The small pinned public manifest
and exact not-admitted calculation are retained in
`ntfy-security-secrets/fresh-db-admission.json`. Current app/publisher input
consumers are concrete retained dependencies, not cleanup failures to bypass.

James subsequently selected **Approve 4.25 GB stage** in the explicit budget
question. `ntfy-security-vuln-approval.json` records this one-stage exception:
4,250,000,000 bytes, full existing 1 GB image/runtime reserve preserved, no
global allowance increase, new root or production activation. The earlier
not-admitted receipt stays historical. Reuse the exact existing export/scanner.
Stream/hash the pinned DB layer without retaining its compressed carrier and
verify complete database/metadata bytes before scanning. No earlier passing
checks need replay. Actual DB/scan outcomes are still pending at this checkpoint.

The subsequent DB phase exceeded the foreground120s tool limit before its
terminal integrity receipt. Its expected-size pending files were preserved,
then a distinct17.82s full-origin comparison verified all compressed/member
bytes without writing a second DB. The original timeout remains recorded.
The exact-export vulnerability scan completed, with one unsuppressed Medium
zlib finding; the candidate is on HOLD, not security-approved.

The unchanged1GB reserve was tracked explicitly as500MB conservative existing
image/metadata plus500MB additional scan workspace, not silently reduced.
Already measured workspace was not double-charged. Full reserved plan:
4,194,884,096 bytes; sampled retained-stage peak3,195,072,512, or3,695,072,512
including the conservative existing-image allowance. All remain under the
approved4.25GB stage. These figures do not claim private-runtime allocation.

After completed assessment, exact
`ntfy-security-vuln/{cache,tmp,home,docker-config}` and
`ntfy-security-secrets/exact-image.tar` were admitted and removed:
**1,811,103,744 allocated file bytes**. Fresh DB/cache/export consumers ended.
Source/lock/index, current app dependencies/build, publisher, approved tool/
immutable October snapshot, all raw reports/logs/advisory/component review and
complete regeneration hashes remain.

Only the exact originally task-acquired ntfy child reference6ceb2733… was
retired with ordinary `docker image rm`, no force/prune. No ancestor containers
or other image aliases existed. A preliminary no-tags check stopped: Docker
represented the SAME owned digest as a RepoTags entry. The failed check and
exact identity correction are saved; no permission/refusal bypass occurred.
Docker confirmed removal and absence afterward. Physical runtime reclamation
is **unmeasured**; do not equate content size or the ended1GB reserve with
freed disk. Stage retained1,204,023,296 bytes and publisher180,113,408 before
the small cleanup receipt. The reserve's local consumer has ended; any fixed
candidate needs its own admission, not an inferred new/global allowance.

### Fixed-zlib ntfy candidate admission

James explicitly requested preparing/qualifying a vendor-fixed candidate with
production inactive. The original base must be reacquired as a NEW derivative
input; no old-digest scans or fixtures are replayed. The single signed Alpine
package is56,761 bytes under existing `ntfy-zlib-fixed/`. Current retained
baseline1,384,148,992 +1,773,903,872 pinned fresh DB + unchanged1GB reserve
+50MB export/report margin =4,208,052,864, inside the approved4.25GB stage.
No new H root, mount, checkout, builder/dependency copy or global allowance.

The actual build uses one constrained offline install container and commit,
not an unbounded shared BuildKit job/new builder. The original install's
CLI-format collector failed after upgrade and its reproducible layer was
discarded; separately named corrected install finished successfully and its
stopped layer was retained through finalization instead of reinstalled.
Later finalizer metadata-path/omitted-Cmd collector failures are preserved,
with package/unchanged-binary/hook checks and committed identity reused rather
than replayed. Final local candidatee26ace78… has one37,076,480-byte verified
export, not a copied source/dependency environment. Deterministic read-only
resource/default-user audit passed; this is not a retroactive install sample.

Fresh DB reconstruction and changed-image TLS/ACL/cache fixture are now
separate owned consumers of that candidate within the same reservation.
Retain package/candidate/export/DB only through their named qualification/
authorized delivery consumers, then review exact obsolete targets. Do not
discard the uniquely committed candidate before its export/consumer handoff
is preserved. No private registry image publication or production allocation
is implied.
The new fixed imagee26ace78… subsequently passed combined security
(zero vulnerabilities/secrets) and changed-image TLS/ACL/cache qualification.
Full reserved plan4,195,260,928 and charged sampled peak3,695,736,064 stayed
within4.25GB with the full1GB reserve. Configured fast-install caps and the
separate deterministic read-only actual kernel audit are distinguished.
All prior collector/fixture failures remain; installed/committed state was
reused rather than reinstalled/recommitted.

Eighteen admitted exact DB/cache/temp/synthetic targets were removed:
**1,774,649,344 allocated file bytes**. All helpers/containers/networks/proxies
ended. Original base reference6ceb2733… retired without force/prune; physical
runtime savings unmeasured and candidate/shared required layers preserved.
Retain the unique local fixed image,37,076,480-byte verified export,
56,761-byte signed package and minimal evidence. Concrete consumers: immutable
private-image handoff and remaining production-like TLS/route/policy/storage
qualification; retirement after verified publication/consumer transfer or
explicit rejection. Do not rebuild/copy this digest or discard its only
verified export before handoff. Stage retained1,241,448,448 and publisher
180,113,408 bytes before small receipt. Source/index, app build/dependencies,
old immutable inputs and unique failure/pass reports remain. No new root/
checkout, image publication or production allocation occurred.

### ntfy integration preparation — no new runtime/build inputs

Retained fixed image/export and publisher tools were reused without rebuild,
pull, dependency copy or completed-image-test replay. Initial measured retained
stage/publisher1,421,574,144 + full carried1GB reserve +10MB new preparation
peak was admitted within the existing4.25GB stage. Read-only metadata, synthetic
tests, in-memory Kustomize renders and the unchanged full validator created
only small H logs/results and ephemeral overrides, not another source tree.
Tool binaries were checked against the retained publisher's checksum receipt.
Private `.tools`/`.validation` links were exact temporary routing links and
are gone; retained publisher/tools were not changed.

The exact empty finished
`certificates-qualification-20261116/ntfy-integration-preparation/validator-tmp`
was removed:4,096 allocated bytes. Preserve preflight/test/validator/source
bindings and the small validation report for separate integration review.
Combined stage/publisher measured1,421,742,080 bytes before the small cleanup
receipt; preparation directory167,936 bytes then. Candidate/export, vendor
package, app build/dependencies, unique evidence and publisher consumers are
unchanged. No new images, cluster volumes, host credentials or production
allocation. Full physical/global attribution remains outside this stage claim.

### Settled-plan private delivery and cluster qualification

James directed execution without repeated approval prompts. Existing qualified
ntfy image/export were published unchanged to the existing verified private
repository; no new build/export/tree. Tiny credential-helper client contained
no secret values and was removed. Full four-layer readback streamed without a
second disk carrier. Exact sealed-memory preload to node01/node02 reserved
250MB import per node above existing free-space floors; both passed. This is
product delivery, not output moved elsewhere to evade H limits.

To preserve Longhorn's25% floor for a new1Gi test claim, six eligible closed
node01 journals were encrypted on H and fully recovered/compared before exact
retirement:536,895,488 allocated bytes removed on node01. Retained encrypted
history89,137,747 bytes, SHA595a2a15…, under the same current stage's
`ntfy-node01-journal-preservation/`, has a concrete historical recovery consumer.
No plaintext carrier, unknown deletion, active log/volume change or threshold
reduction. Maximum650MB was charged with the full1GB runtime reserve;
the existing4.25GB ceiling remains unchanged.

Actual isolated staging now has a new retained1Gi Longhorn claim/two healthy
encrypted replicas and verifies both replica destinations' scheduling margin.
Existing production claims remain separate. Diagnostic API evidence/native
synthetic material is small H output; standalone Pod resources/time are bounded.
First rejected ReplicaSet deadline field created no workload; completed
namespaces/PKI/auth/claim/config were reused by UID. Do not remove claim or
synthetic native material under blanket namespace cleanup.
Path/state qualification finished. All six exact owned diagnostic Pods and
forwards ended; local synthetic client token and empty temp reclaimed8,192
allocated bytes, new empty validator temp4,096 bytes. Fixture PKI/native auth/
config/claim remain for scoped unattended rotation-controller live acceptance,
then exact retirement review, not indefinite generic evidence. No test load
or DB snapshots persisted: cap-refusal copies were memory-only.

An OpenCode server restart required reconciliation, not repeated publication/
preload/cluster tests. Same boot/store, all terminal receipts and no task driver/
client token verified. Rotation policy/adapter tests used fresh synthetic
certificate keys only in owned H temp directories; all those keys/directories
were removed after tests. No dependency, image, tree or build copy.
Closing measured stage/publisher1,511,256,064 bytes before small receipts, plus
full1GB runtime reserve inside4.25GB. The89,137,747-byte encrypted node01 history
remains a unique recovery consumer; source/index/app/publisher inputs preserved.

Rotation-controller live qualification reuses that retained fixture and the
already cached qualified Node runtime. Initial measured retained1,511,276,544
plus full1GB reserve/10MB new output peak fits4.25GB; no new tool, dependency,
image, build or disk carrier. Current small H `ntfy-controller-qualification/`
contains source hashes, create intents/UIDs, public enrollment and sanitized
Job output only.600s credentials remain projected in diagnostic pods, not H.
The initial silent projected-symlink Job and helper-arity failure are preserved;
only unfinished observation/renewal portions resumed, no image/old path replay.
Existing synthetic claim/PKI/auth remain the concrete live controller consumer
until reviewed completion/retirement, not an indefinite evidence allocation.
Controller qualification is now complete: real renewal, interruption recovery
and two native scheduled runs passed; all exact new diagnostic objects/grants
were removed, zero Pods remain. Small sanitized results/source bindings only
were added to H, with no build/dependency/image copy or synthetic local keys.
Retained stage/publisher measured1,511,534,592 bytes plus full1GB reserve within
4.25GB before the small acceptance receipt.

The original synthetic PVC/PKI/auth/config/namespaces were outside controller
teardown. Their consumer has ended, so exact retirement review is the next
cleanup action, not an indefinite evidence/rollback label. Original claim/
volume UIDs still match; Longhorn is detached/robustness unknown after teardown.
Review references, cascade ownership and exact snapshot/volume identity before
any deletion; no blanket namespace/PVC deletion or production-data retirement.
Application dependencies/build remain for reader/release qualification;
fixed ntfy image/export remain pending immutable-delivery/local-consumer
retirement review. Encrypted node01 journals remain unique recovery history.

Separate fixture retirement then completed:15 reviewed exact objects including
synthetic retained PVC/PV/Longhorn volume; normal finalizers, no attached users,
snapshots or backups. Replicas and generated requests disappeared. Physical
cluster savings are unmeasured; namespace objects/injected trust metadata were
preserved rather than swept.

The ended local fixed-image refs were removed with ordinary exact Docker
image rm (no force/prune), after complete container-reference inspection and
verified private-registry/node consumer transfer. Registry/node images remain.
Local `ntfy-zlib-fixed/candidate-image.tar` is **retained**,37,076,992 allocated
bytes: no visible open FD, but process-FD visibility was incomplete. This is
a failed safety check, not a new generic consumer; no deletion/alternate-route
retry was attempted. Minimal hashes/recipes and the failure are in
`local-retirement-review.json`/`local-image-retirement-result.json`.

Production staging reserves a conservative additional256MB H publisher peak
alongside the current stage, prior retained publisher and full1GB reserve,
still within4.25GB. Local44-test/full-validator/renders used existing tools via
temporary routing links; links and the finished empty H temp were removed.
The publisher now hard-links the existing checksum-pinned H tool inodes into
its exact Git export, with no copy/download fallback or chmod of shared tools.
Source exports remain required release artifacts, not a new checkout/environment.
Old/new publisher du totals may count shared inodes conservatively; do not claim
double-counted physical savings. Preserve current tool consumers and app inputs.
Exact staged publication/Flux and production identity qualification then passed.
New publisher02ebe242… shares the prior H tool inodes;44-test/check receipts
remain. Its empty finished `tmp` was removed4096 allocated bytes; diagnostic
ConfigMap/Job and all Pods are gone, no local production token was saved.
Conservative retained stage+two publisher trees measured1,691,987,968 plus
full1GB reserve under4.25GB (tool links may count twice across separate du calls).
Current source/export/tool consumers remain for staged live integration;
37,076,992-byte candidate export stays explicitly safety-check-retained, not
silently retried or described as deleted.

Serving integration reuses all existing dependencies/images/tools with a
256MB conservative new publisher allowance plus full1GB reserve inside4.25GB.
Auth generation used retained bcryptjs through stdin/memory; plaintext
passwords were discarded and tokens persisted only in the native Secret, not
H. Public certificate/metadata and sanitized results remain. API default-mode
and pre-existing dashboard self-signed failures are retained, not replayed as
acceptance. Finished local check temp/routing links were removed4096 allocated
bytes. Issuance/edge integration precedes writer start in separate source
checkpoints; publisher tools remain same-inode links, not copies. Pending
new-name DNS delivery is not hidden by explicit-address TLS verification.
Serving, actual enrollment/observe and native schedule now passed. Three exact
finished publisher tmp directories from1f0b3554…/26647121…/7ca44f47… removed
12,288 allocated bytes after terminal consumers. No private local credential
payload was created; two native metadata messages remain in the production
server's24h cache, not arbitrary disposable fixture data. Normal bounded
production CronJob history is retained. Do not remove native auth/PVC/server/
schedule under fixture cleanup.

Conservative retained current stage+five publisher trees2,232,958,976 plus
full1GB runtime reserve remain under4.25GB before the small closing receipts.
Separate tree du totals can double-count same-inode tools; this is not measured
physical growth/savings. App build/dependencies and source/evidence/tool inputs
remain needed for reader/release and next live integration. The37,076,992-byte
export remains an explicit failed-safety-check retention, not silently retried.
DNS continuation reserves two256MB publisher peaks plus the unchanged full1GB
runtime reserve: preflight2,232,963,072 retained bytes remains within4.25GB.
The first local validator reused pinned H tools through temporary routing links;
links and its empty temp were removed4096 allocated bytes. No dependency/image/
filtering DB copy. New source exports are exact publisher inputs, not checkouts.
Standalone records refresh preserves its existing82,882,560-byte filtering DB,
credentials and query state; only public DNS configuration is staged.
Both serial DNS checkpoints and independent records/runtime/client acceptance
are complete. Stage plus seven publisher trees measured2,593,718,272 bytes
conservatively before final small receipts, plus full1GB reserve within4.25GB.
No image/dependency/filter DB copy; unchanged publisher tools remain linked.

The completed controller/publisher empty-temp cleanup did NOT delete six
targets (24,576 allocated bytes): strict PID absence first failed because
finished wrappers remained zombies; FD inspection then returnedEACCES for
/proc/1746577/fd. No elevated/alternate route or process stop. Exact paths/
sizes and failed check are retained in ntfy-dns-delivery/temp-cleanup-result.json.
They remain until normal reaping and later authorized ownership/consumer review,
not generic evidence/rollback bulk. Preserve unique logs/results/source and
the earlier failed-safety-check image export; do not retry either via an alias.

Monitor transport-diagnostics continuation measured2,774,392,832 conservative
stage/eight-publisher bytes plus the unchanged full1GB reserve, under4.25GB.
No new image, dependency tree, publisher export or source checkout was made.
Two new non-publishing transport diagnostics used memory-only code and separate
transient units/cgroup-scoped nft tables; both ended with tables absent.
Six changed-source tests removed their synthetic TLS/token material and exact
empty test root4096 allocated bytes. Three current controller temp directories
remain12,288 allocated bytes with process-FD visibility not established:
`monitor-host-activation/{sender-diagnostics-temp,sender-diagnostics-copy-temp,transport-annotations-install-temp}`.
They are separately named in transport-annotations-continuation-boundary.json;
retain until normal harness reaping/authorized consumer review. Earlier six
DNS temp paths and candidate-export safety retentions were not retried.

Watchdog continuation added no image, dependency tree, publisher export or
checkout: identity-only private checkpoint and broker/runtime staging reused
the existing publisher tools same-inode, and two inactive units plus source are
plain files. Its four Ansible/identity temp directories were admitted only
after empty-content/symlink/mount/open-writer checks passed with no live
consumer, then removed:4 x 4,096 = 16,384 allocated bytes. Synthetic credential
test payloads and the empty test root were removed earlier in the same step.
Actual broker/runtime state now retained is production/qualification data
(root:997/0640 token,0700 state DB, public enrollment), not disposable bulk.
Stage boundary remains under the4.25GB ceiling with the full1GB reserve.
