# Immutable BORTUS release image builder

`scripts/migration/build-bortus-release-image.py` consumes the archive and manifest
produced by `prepare-bortus-release-context.py`. Supply the exact lowercase
40-character commit and independently pinned SHA-256 hashes of both artifacts.
The helper verifies the closed manifest, complete regular tar inventory, paths,
modes, raw Git blob IDs and SHA-256 hashes, required Docker/package/schema files,
migration inventory and the producer's exclusions before any SSH request.
Limits are 2,000 included plus excluded entries, 16 MiB per source file, 128 MiB
source total, 144 MiB compressed/decompressed archive and 4 MiB manifest.
PAX path headers are supported within 8 KiB; links, global/other extensions,
unexpected metadata and nonzero payload after tar EOF refuse. Nothing is extracted.

Run under Linux/WSL as the approved operator. Source inputs must be bounded,
regular, operator-owned and not group/world writable. Each is copied fresh with
nofollow/nonblocking reads, stable inode/content timestamps before and after,
and a protected copy hash/identity check immediately before streaming. The
protected copy pins ctime/mtime and link count as well as inode, avoiding
acceptance of a replaced file whose inode was reused. A post-stream check
refuses completion if the copy changes during dispatch; it cannot undo remote
work already dispatched. The coordinator must exclude concurrent writes by
the operator to the owned run and supplied source inputs.
The
operator runtime parent may be owned mode 0755; all ancestors must be owned by
root or the operator and not group/world writable. The final parent is pinned
and operator-owned. A new, deterministic `bortus-release-<fullcommit>` directory
is created mode 0700 and its parent entry is fsynced. Run files are mode 0600.
Any existing run refuses; the helper never reopens, adopts, overwrites or retries
an earlier intent, including failed validation or an uncertain outcome.

```sh
python3 scripts/migration/build-bortus-release-image.py \
  --context /approved/runtime/release-input/context.tar.gz \
  --manifest /approved/runtime/release-input/context.json \
  --source-commit <exact-lowercase-40hex-commit> \
  --context-sha256 <independently-pinned-64hex> \
  --manifest-sha256 <independently-pinned-64hex> \
  --runtime-parent /home/brajam/.local/share/branconet-migration
```

The sole destination is `james@192.168.0.4`, SSH port 2002, BatchMode=yes,
StrictHostKeyChecking=yes and ForwardAgent=no. No sudo, password, forwarded
agent, operator kubeconfig or runtime Secret is supplied. The sole build arg is
the approved nonsecret `KUBECTL_VERSION=v1.37.1`. Docker receives the verified
archive on stdin and the exact tag `bortus:release-<fullcommit>`. Existing tags
refuse both during the initial query and immediately before the remote build.
Docker provides no atomic tag compare-and-set: the release coordinator must
hold exclusive builder/tag ownership throughout this operation. The helper
does not claim to exclude an unrelated concurrent Docker writer.

A file-and-directory-fsynced pending record exists before build dispatch.
Complete build stdout/stderr are retained separately in the protected run,
hashed by streaming reads rather than buffered as a whole. SSH query/inspection
timeouts are 30 seconds; build timeout is 2,400 seconds, with a 15-second SSH
connection timeout. The local SSH child is waited/reaped by subprocess.run.
Timeout/lost reply (SSH exit 255), failed metadata inspection and post-dispatch
durability failures leave an uncertain intent or the prior pending record.
The remote Docker build may still run after a lost reply; no automatic retry,
remote cleanup, cancellation or image adoption is attempted. A received normal
nonzero build exit is failed; the remote pre-build tag guard exit 73 is refused.
Flush failures never grant success. This is fault injection qualification, not
power-loss testing. Protected logs may contain complete build diagnostics and
must not be copied indiscriminately into Git or public reports.

After build exit zero, the helper inspects only image config ID, positive image
size and five exact labels: source commit, application tree, context hash,
manifest hash and unique build owner. It never inspects environment values or
full image configuration. The `sha256:` config image ID is **not** an OCI
manifest or runtime digest. Successful completion records no qualified runtime
digest and `deployed=false`, `runtime_accepted=false`. This helper has no run,
deploy, export or preload API. Image scanning, runtime/migration/data acceptance,
admission, distribution and release are separate coordinator gates.
The separate [export/preload helper](BORTUS-RELEASE-STAGING.md) consumes this
exact completed receipt and retains its own independent staging intents.

The prior `build-bortus-image.py` binds a historical fixed image/source checkpoint;
its evidence remains historical. This generic helper does not reinterpret that
record. The separately qualified operator mTLS adapter has a scoped live TLS 1.3
Volume LIST/HTTP 200 watch-handshake receipt; it supplies no build input and is
not full independent restore or restored-data acceptance. See
[restore watch prerequisites](BORTUS-RESTORE-WATCH.md).

The local tests use public disposable source archives, actual POSIX file/dir
flushes and injected filesystem/subprocess faults. They do not contact the
builder, read operator credentials, run Docker, build an image or deploy.

Root selected immutable `7e30b9b4` for an inert recovery holder after independently
verifying its raw/working sources, 687 compiled files, original Windows and Linux
functional artifacts. The actual immutable build completed at 09:14:59 UTC on
2026-10-11. Exact source/context/build/config bindings are in the
[holder receipt](../evidence/bortus-holder-source-image-7e30-20261011.json).
This build does not qualify application performance, image runtime or deployment.

## Exact c29fc application image qualification

The [c29fc image receipt](../evidence/bortus-app-source-image-c29fc-20261011.json)
records the single source-bound build (12:06:21 UTC) and export (12:10:33 UTC)
on 2026-10-11. Its 265 production entries match independently verified raw Git
sources and the tested build context. The Docker config ID is
`sha256:b147db1da11fc66634954e12f15a4ef19fb3eb5e06b8b4e7d9676212caf39b4c`;
this is not a qualified OCI manifest or runtime digest. The archive's ordered
layers/config/labels match the completed receipt. Exact child owners are closed.

A fresh pinned Trivy 0.75.0 default image and image-config scan completed at
12:11:00 UTC with exit 1: zero Secret findings, 346 vulnerability entries
(125 Low, 142 Medium, 67 High, 11 Unknown, one Critical). Nineteen fixable entries
are in bundled kubectl, including four High. The Critical zlib finding has
scanner status `will_not_fix`; no suppression or application reachability
acceptance follows from that status. The earlier inert-holder assessment cannot
qualify the application image. At that scan checkpoint, runtime/schema fixtures were pending; the later
disposable fixture below records their scoped result. Kubectl remediation and
security review, A07/A21 performance, three-node runtime qualification, active guards,
independent complete-row recovery and final live acceptance stay open.
This qualification dispatched no application rollout, cluster mutation or
production data read; the original writer and data remain preserved.

## Disposable c29fc image runtime and synthetic forward migration

The [runtime receipt](../evidence/bortus-app-disposable-runtime-c29fc-20261011.json)
records one reviewed run completed at 12:18:51 UTC on 2026-10-11. Exact config
and five source labels matched before execution. Three disposable stages ran
with no network, read-only root, UID/GID1000, 2CPU/1GiB/128PID limits and bounded
tmpfs mounts: package inventory, fresh schema/restart and legacy1438 forward
migration/restart. Liveness returned200; native-unavailable readiness returned503.
All11 migrations completed with zero schema drift and the expected account lock,
legacy principal and write/admin versus readonly/nonadmin policy bridge.

The legacy fixture uses the exact historical schema and seven raw migrations,
with every original application table populated. The unchanged comparator
checked all14 original tables, all original columns and complete row multisets:
21 source rows survived unchanged, including both users and the alias with an
underscored key. Added migration rows are separately recorded. SQLite integrity,
foreign keys, terminal migration state and new sessionVersion default0 passed.
These are synthetic rows; the fixture's arbitrary hashes do not establish login
behavior, and this is not production preservation or independent storage recovery.

Root freshly checked absence of all20 owned Linux process identities, the exact
Windows launcher and the complete owner-labelled Docker container list. Fixture
database frames remained in memory/tmpfs and cleanup completed. No production
PVC/database/native credentials, Kubernetes operation, image preload or rollout
was used. Application security, A07/A21, full-row production recovery, admission,
actual auth/UI/consumer acceptance and final live release remain separate gates.

## c29fc selected MiniZip package/file review

The [single bounded metadata probe](../evidence/bortus-app-minizip-metadata-c29fc-20261011.json)
completed at12:27:50 UTC with actual exit0 on the exact config/source image.
Installed package selection finds zlib1g from source zlib; nine selected regular
files totaling242,823,089 bytes were read with no symlink following. No selected
MiniZip-owned pathname, positive ELF token or linked MiniZip library was found.
The sole positive text reference was zlib's copyright notice. Scope is limited
to selected package-owned files and fixed Node/kubectl/curl/openssl/Prisma binaries;
stripped, inlined, compressed or obfuscated code is not excluded. It is not an
all-image inventory, reachability proof or application security pass.

Root freshly verified eight Linux process identities, the Windows launcher and
complete owner-labelled container-list absence. No app entrypoint, native
credential or production mount was used. The original default Trivy exit1,
346 vulnerability entries, Critical finding and kubectl remediation remain
unsuppressed. The [separate preload receipt](../evidence/bortus-app-preload-c29fc-20261011.json)
confirms image staging on all three nodes. The later inert Kubernetes runtime
is recorded below; active guards, independent production recovery and final
live acceptance remain open.


## c29fc digest aliases and inert Kubernetes runtime completed

The [actual three-node runtime receipt](../evidence/bortus-app-three-node-runtime-c29fc-20261011.json)
records the separate alias-only operation at12:55:18 UTC and inert public
runtime at12:56:45 UTC on2026-10-11, both actual exit0. Each node verifies the
same config, five source labels, ordered layers and OCI manifest068254f3;
absent digest cache names were created without force or image replacement.
The image is referenced by its manifest digest, never its Docker config ID.

All three nodes ran Node22.23.3/Prisma6.19.3 against two public SQLite rows in
an8-MiB memory volume, with integrity and an8192-byte reader frame checked.
Pods used UID1000, read-only root, dropped capabilities and no service-account
token, production PVC or application entrypoint. Six owned execs completed.
UID/resourceVersion-preconditioned deletion and a fresh complete PodList prove
all three probe names/UIDs and the owner label absent. Root independently
verified all seven runtime process identities and the exact Windows launcher
absent, plus all24 frozen helper hashes unchanged. The original Deployment and
Ready writer retain their exact UIDs, resourceVersions and1438 image.

This qualifies c29fc as an inert public-fixture runtime only. The newer ab8d
application source needs its own final image qualification. No production-row
restore, active admission, original PVC schema migration, app rollout, security,
performance or live auth/UI/consumer acceptance follows from these probes.

The fresh [4ae9 Linux functional qualification](../evidence/bortus-functional-4ae9-root-20261011.json) passed its production build, 262 unit tests without skips, whole-source lint, fresh type checking and six existing HTTP/process controls. Root independently rehashed 344 executed sources, 77 test/helpers, 4,262 compiled files and all five original stage logs against the final 345 raw Git frontend bindings. All observed owned processes and containers are absent. The first read-only root count assertion accidentally included 22 doc rows; the corrected frontend-only check passed without rerunning qualification. Browser lifecycle, universal action, paired performance, immutable final image and live release gates remain separate and pending. Production remains unchanged.


The [actual immutable 4ae9 image receipt](../evidence/bortus-app-source-image-4ae9-20261011.json) records build0 at18:28:26 UTC, export0, exact five source labels, complete independently verified linux/amd64 archive/config/ordered-layer hashes and observed owned-process closure. Default Trivy0.75 scanning completed with exit1:346 findings (1critical,67high), including four fixable high findings in kubectl, and zero secrets. The critical zlib1g finding is individually classified using Debian's Bookworm binary-package assessment and actual archive package/library contents; its original count remains retained. This does not accept the entire image. No application/image runtime or deployment occurred. Patched CLI selection, remaining security/performance, latest-data capture and final schema/admission/principal/live/rollback gates remain open.


## 2026-10-12: final4ae9 performance execution closed, regression gate failed

The [independent root comparison review](../evidence/bortus-performance-4ae9-root-20261012.json) verifies40 originals,424 raw Git blobs/modes and actual immutable baseline157/candidate267-file tar bytes. The unchanged original runner completed six unique alternating observations, three per source, with all assertions. Root recomputed330 workflow/HTTP summary distributions, confirms all six native metadata profiles returned the complete expected inventory, and observed supervisor/runner absence. Execution success does not establish A07/A21 acceptance: native HTTP latency regresses at200/1000objects and large-value cases; some warm1000-object tails improve. The10,000-Pod baseline false-empty cases remain ineligible for equivalent latency claims; native metadata comparisons independently remain valid. The first root read placed the native phase oracle on its request entry; correction used the actual phase field without rerunning measurement. Original limits/oracles/source remain unchanged. Safe performance remediation, final runtime/security, latest-data migration and live/rollback acceptance stay open.


## 2026-10-12: primary package triage and pinned custom-build inputs

The [primary remediation receipt](../evidence/bortus-image-remediation-research-20261012.json) retains all20 unique Debian High/Critical IDs from the default4ae9 scan and current Debian release tables. All20 primary requests succeeded. Debian13 contains fixes for some Bookworm findings (for example [util-linux target-path redirection](https://security-tracker.debian.org/tracker/CVE-2026-53613) and [OpenSSL DTLS retransmission](https://security-tracker.debian.org/tracker/CVE-2026-84782)); several other findings remain vulnerable there. A base upgrade alone cannot establish security acceptance. No suppression or change to original346 findings is applied.

Root downloaded the exact upstream Kubernetes1.37.1 source42196261bytes and Go1.26.9 Linuxamd64 toolchain66935201bytes onto the separate build host, then independently rehashed both and observed the downloader absent. The source checksum remainsd58492a0… and Go42d158b4…; full bindings are in the receipt. Actual source layout is flat with two file and three directory symlinks, unlike the draft fixture; those cases are corrected before compilation. Inputs are public archives, no cluster or credential mount is involved. Custom compilation, vendor diff review, binary scan, final source/image injection and runtime acceptance remain pending.


The separate [custom kubectl security build contract](BORTUS-KUBECTL-SECURITY-BUILD.md)
consumes pinned upstream1.37.1 source and Go1.26.9 archives, with reviewed
x/net0.60.0 and transitive pins. It is a local-only candidate for a custom
binary, not an upstream1.37.2 release or image security pass. Existing Dockerfile
and release-builder defaults remain unchanged pending separately qualified
source-linked injection and actual image/runtime acceptance.


Custom kubectl build receipts keep detailed source/cache diffs in a bounded,
protected fsynced metadata sidecar and full before/after ZIP; only count/SHA/path
stay in the1MiB ownership record. Public archive modes are preserved inside the
private run. The first actual attempt failed before compiler dispatch at the
record bound; earlier fixtures did not qualify its cache scale. Existing image
contracts and defaults remain unchanged; see [custom build](BORTUS-KUBECTL-SECURITY-BUILD.md).


Root [integrated helper qualification](../evidence/bortus-kubectl-security-build-root-20261012.json) verifies all9 selected raw native files and84 retained originals, then passes18 controls without skips against the current checkout. Actual unittest time1.805s/root wall1.891s; frozen source hashes stay unchanged. These are controlled Python/bash child/archive/version fixtures, not actual Go compiler acceptance. Default image builder remains unchanged. Root separately dispatched the exact helper on the existing build host with two-core affinity, pinned public archives, fresh HOME/module/cache and one2400s budget. Supervisor/helper PID/start identities were observed live in preparation; no final binary, scan, image injection or cluster deployment is yet accepted.


### Actual custom-build preparation failure, retained without replay

The [actual build receipt](../evidence/bortus-kubectl-actual-preparation-failed-20261012.json) records terminal1 before the compiler stage. Actual Go1.26.9 version/offline module ABI, five dependency pins, upstream vendor regeneration and the full module query passed. Full source diff ZIP275523080bytes/43022members is CRC-valid. The detailed37388-path list would make the main record3757314bytes, above its unchanged1MiB bound; a later failure save also remains bounded, leaving the prior5960-byte pending record. All observed commands and supervisor are absent.

31730 newly inventoried paths are upstream module cache under `_output`;5465 changes are mode-only. The original full diff/archives/logs stay intact and this owner is never reopened, adopted or replayed. The next source correction stores detailed diff metadata separately under a finite bound and retains compact count/SHA identity in the main record. Local18-control success did not cover this real source size. No compiler, final binary, image injection or cluster change is accepted.


Root [bounded-diff correction qualification](../evidence/bortus-kubectl-diff-metadata-root-20261012.json) verifies8 raw native files/37 original artifacts and passes21 causal controls without skips in2.097s (2.187s wall). The >1MiB path-list fixture retains all18k paths outside the bounded main record and proves small failure receipts remain writable; public archive modes are preserved under the private root. Detailed sidecar is finite64MiB, main record remains1MiB, and no source/vendor/cache path is dropped. Frozen sources remain unchanged. A documentation-only apply check refused because newer root sections follow the native EOF; exact native insertions were merged with those sections preserved, before source changes/tests. This local result does not establish a corrected actual build or image.

## 2026-10-12 05:31 UTC: actual custom kubectl build and component scan

The [actual root receipt](../evidence/bortus-kubectl-actual-build-root-20261012.json) records all12 build stages with exit0, completed at05:18:10UTC. The 61,960,354-byte binary is a custom `v1.37.1-bortus.security.1-dirty`, built with Go1.26.9 and x/net0.60.0; SHA-256 `a3c4741294f061550b30bd2e3f357197ffbac37eefc5a45d686fe9cd29032b75`. All observed build command, helper and supervisor PIDs are absent.

Root independently verifies34 transferred originals, complete CRC-valid original/diff ZIPs and32,084 changed-file byte identities. All31,916 paths remain retained, including31,723 generated cache paths; faithful archive modes eliminate artificial mode-only changes. The detailed sidecar is12,741,184bytes while the main completion record is8,902bytes. Source changes outside generated cache are module records and x/* vendor files, including upstream-selected sync/tools/mod transitives.

Default Trivy0.75 component scan returns0 with zero vulnerability or secret findings and explicitly analyzes the kubectl Go binary and90 packages. The first protected copy had mode600 and yielded no Go analysis; that report is retained and rejected. A new owned scan uses the unchanged binary with its original0755 mode inside a private directory, confirms Go1.26.9/x/net0.60.0, retains all severities and uses no suppressions. The original image scan remains346 findings (1Critical/67High). This component result does not accept a final image, deployment, performance, schema migration or live engine. Source-linked image injection, full image/runtime gates and the latest-data cutover remain open.


A separate [patched ELF image adapter](BORTUS-PATCHED-KUBECTL-IMAGE.md) can bind a
completed custom kubectl receipt and exact ELF to a named BuildKit context while
keeping the raw Git source tar and five source labels. Its protected injection
sidecar is required for root qualification; existing export/preload alone does
not qualify the patch. Default builder and frontend Dockerfile stay unchanged;
actual binary/image/security/runtime acceptance remains separately required.

## 2026-10-12: integrated patched-binary image adapter

The [root qualification](../evidence/bortus-patched-kubectl-image-root-20261012.json) independently verifies all10 raw native files,50 retained originals and1,879 CRC-valid ZIP members. Three source/test files and the dedicated image-adapter doc are integrated; later root build/scan sections are preserved. All21 POSIX orchestration controls pass without skips in2.510s (2.620s wall), with seven original sources unchanged and the owned test child reaped. The first root freeze check incorrectly counted newly generated test-fixture copies as original sources; that failed harness result remains retained, and no source/test behavior was altered.

Root separately validates all six actual compiled artifacts in3.138s: complete247,076,441-byte source diff ZIP,12,741,184-byte metadata sidecar/all31,916 paths, ELF, completed build receipt, actual version and Go build metadata. Their identities and bytes remain unchanged. These checks call no build, transfer, SSH or Docker operation. The default builder/export/five-label contracts and frontend Dockerfile remain unchanged.

A future source-linked build must carry both completed image and injection receipts, exact owner/config/context identities and actual launcher terminal0. The adapter supplies the separately verified kubectl through a named BuildKit context and checks its SHA in the image consumer; interrupted or mismatched outcomes cannot qualify. Actual consumer/source image construction, full image/runtime/performance, latest-data and live schema/RBAC/admission/rollback gates remain open.

## 2026-10-12: actual e50 source-bound image build completed

The [root build receipt](../evidence/bortus-patched-app-build-e50-root-20261012.json) records actual helper exit 0 in 307.112 seconds. The canonical e50 source context includes the approved named-context kubectl consumer and pinned Trixie runtime base. Completed build and injection sidecars bind the same source, owner, context, manifest and config image ID. Root verifies all eight stage-log hashes, exact five-label inspection and absence of the owned supervisor/helper/observed children. Inputs remain unchanged.

The config image ID is `sha256:db6a14d34ee75d8477e03d7efd0323100ca8b85941b6a46f96edda80d3e86bbc`; it is not a qualified OCI/runtime digest. The sidecar binds the separately reviewed kubectl ELF SHA `a3c4741294f061550b30bd2e3f357197ffbac37eefc5a45d686fe9cd29032b75`. Actual archive/layer contents, full image security, runtime and deployment acceptance remain pending. Performance evaluation is separate; this image retains the eight-request production cap.
## 2026-10-12: independent Debian advisory triage

The [root triage receipt](../evidence/bortus-debian-high-triage-root-20261012.json) binds the unchanged default report to26 retained originals and15 Debian primary-source snapshots. Its43 HIGH rows match installed binary/source versions and group into8 CVEs/5 source families. All eight current Trixie CVE tables mark the source versions vulnerable;42 rows carry `no-dsa` and one `postponed`. These policy notes grant no not-affected or fixed status. All162 default findings remain retained.

The audit's A20 validation requires compatible updates and complete functional/image qualification; residual exceptions require precise execution-boundary rationale and expiry. Universal zero-HIGH was not the original acceptance clause. This triage accepts no exception, package purge, unsupported mixed-suite upgrade, final runtime image or deployment. The isolated runtime-rootfs prototype must retain complete scanner package visibility and pass the existing Node/native/Prisma/operator/migration contracts before adoption.

The [isolated rootfs preparation review](../evidence/bortus-chisel-rootfs-preparation-root-20261012.json) verifies1200 originals,1082 canonical Git blobs/all200 trees,169 file objects and the separate archive root. Root independently verifies the three Ubuntu archive signatures and binds six complete indexes and17 deb/control records to those releases. This prototype contains62 slices; its patched libtinfo is `6.4+20240113-1ubuntu2.2`. It has no application, Node or custom kubectl copy and no binary execution. Scanner metadata is a proposed partial-package view outside the rootfs; its later inclusion and complete image visibility remain unqualified. The archive's UID/GID1000/root0700 is preparation metadata, not final container traversal acceptance. Missing `sed` and unusable Perl-based `c_rehash` are explicitly recorded tool-presence differences; the actual requirements are clarified below.

Actual requirements must come from source, documented workflows and portable acceptance checks. Exact e50 uses `sed` only for Docker build-time CRLF normalization; no frontend call or Markdown promise requires `c_rehash`/`update-ca-certificates`. Historical scanner inventories list those files without establishing a command contract. Their presence/absence needs a truthful assembly decision, but universal equivalence with every inherited Debian utility is not an acceptance gate. Node/native/Prisma, actual shell/filesystem/kubectl behavior, trust/OpenSSL dependencies and complete recovery/data checks remain mandatory.


The [root runtime tool selection](../evidence/bortus-runtime-tool-license-selection-root-20261012.json) binds the exact 61,960,354-byte patched kubectl ELF to its completed build/injection receipts and provides a separate executable named context. The cached Node image is identified by its actual OCI manifest descriptor and resident repository digest. A read-only filesystem copy from a unique container that was never started verifies `/usr/local/LICENSE`, 145,485 bytes, SHA256 `c738ae413cf561f174e34f6961f8ca458aae2369a73640dda6234c629b98bcc4`. All seven owned CLI identities are freshly absent, and removal plus a fresh successful query proves the inspector container absent. No image execution, pull, prototype build or source adoption occurs. These inputs resolve preparation prerequisites only; the complete assembled image still requires dependency/runtime/data-preservation qualification and its own durable full default security scan.

## 2026-10-12: component build success with preserved wrapper failures

The [root partial-artifact review](../evidence/bortus-runtime-build-partial-root-20261012.json) retains install wrapper1 (case-sensitive absence guard), then compile/prune wrapper1 (post-prune lock equality). Actual npm install/build/prune commands exited0, and the native module loaded successfully. The latter lock changes remove30 `libc` metadata fields only: all584 package entries, versions, integrity and dependency fields otherwise match. All312 removed installed packages are development dependencies; all189 retained package graphs match the input lock. Root independently verified4,263 compiled and27,749 pruned regular files and53 absent owned identities. These partial artifacts may be selected by a separate COPY-only packaging owner with both locks declared; neither original failure is relabelled0, and no component is replayed. Runtime compatibility, scanner and image acceptance remain open.

## 2026-10-12: JWT/alias candidate functional composition

Source9fd434e has [verified composite functional evidence](../evidence/bortus-jwt-alias-functional-composite-root-20261012.json): original environment/build/native-load0, followed by a corrected source-unchanged280-unit and8 strict HTTP/process continuation0 with no skips. It is not an uninterrupted five-stage pass. The original one-unit failure and subsequent diagnostic wrapper failures remain. The [causal control](../evidence/bortus-tmpfs-execution-cause-root-20261012.json) proves the local runner introduced noexec/tmp, unlike original CI; only disposable compiler fixtures gain exec, and output reads use0755 inside a private0700 owner. All358 source files,4,263 compiled files and40,635 dependency objects remain unchanged. No install/build replay, timing acceptance, final runtime image qualification or deployment follows.
