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


## 2026-10-13: Node core advisory coverage remains open

The [root primary review](../evidence/bortus-node-core-primary-review-root-20261013.json) verifies21 packet files/22 CRC-valid members, current original bindings, the inspection process birth absent and six current ELF-header/needed-name comparisons totaling15520 bytes. Node22.23.3 bundles OpenSSL3.5.8; its ELF has no direct libssl/libcrypto dependency, while Prisma's query engine needs both shared libraries. These bounded linkage observations do not prove every dynamic-load/caller path or replace the existing full-byte image authority.

The [September OpenSSL advisory](https://openssl-library.org/news/secadv/20260929.txt) includes HIGH CVE-2026-84782 in the3.5.8 range. The exact Node built-in TLS selector cannot select its required DTLS operation; that source rationale does not waive the whole ELF/addon boundary. LOW CVE-2026-35189 concerns ordinary peer-certificate processing and remains unresolved for the native HTTPS client. The original default Trivy exit1/five MEDIUM/zero reported HIGH remains unchanged; its npm target did not assess Node core. No exception or security pass is accepted. Source-only remedies compare a custom Node22/full OpenSSL3.5.9 update with official Node26.11.1 and a fresh coherent qualification profile. Neither changes runtime, benchmark acceptance, source image or deployment.

## 2026-10-13: upstream source signatures authenticated

The [root signature receipt](../evidence/bortus-node-source-signatures-root-20261013.json) records the bounded source-authentication result. Root authenticated the signed Node22.23.3 checksum list and Node/OpenSSL3.5.9 tag signatures using the published primary keys. All three actual GPG checks exit0. The original wrapper exits1 on non-ASCII public signer display text; a distinct read-only post exits0 after parsing only machine status fields. Independent root checks verify all22 current input rows and all five original/post process births absent. The wrapper failure is retained, and no cryptographic check is replayed. This authenticates the existing small public signatures only; source archive bytes, OpenSSL archive signature, exact Node22 regeneration/build, ABI/Prisma/TLS and final image security/performance remain unqualified. No runtime or deployment changes.

## 2026-10-13: source archives authenticated and cached builder inspected

The [archive receipt](../evidence/bortus-node-source-archives-root-20261013.json) records two successful fixed acquisitions: Node22.23.3 source50,447,060 bytes and OpenSSL3.5.9 source53,279,637 bytes. The Node archive matches the authenticated signed checksum list; the OpenSSL detached archive signature passes once against the expected primary key. Independent read-only checks verify archive/source/keyring/tool bytes and four original process births absent, followed by the reader itself. No download or crypto check is replayed. The original source scan retains two public-receipt-digest findings; clearer checksum naming passes the unchanged default scan without suppressions. Archives remain unextracted/unpatched/uncompiled.

The [builder receipt](../evidence/bortus-node-builder-inspection-root-20261013.json) records corrected inspection0 and independent post0 against the fixed cached image. It retains the prior pre-create missing-Labels refusal and started inspection refusal. The actual corrected reader observes Perl with two legitimate hard links, GCC/G++12.2, binutils2.40, make4.3 and Python3.11.2. NASM is absent; the exact OpenSSL regeneration helper invokes it even on Linux. The18657-byte default config is retained separately from process.config. Root verifies8 source files/228 records,43 original host births absent, four exact container ID/name queries and five later reader/query births absent. Container tool coordinates are never treated as host PIDs. Isolated authenticated tooling, safe source projection, generation/build, ABI/Prisma/TLS, final image/security and recovery/live qualification remain open.

## 2026-10-13: source-copy controls pass; real-archive preparation refuses

The [source-preparation receipt](../evidence/bortus-node-source-projection-root-20261013.json) records 14 passing synthetic controls, including real regular/executable/symlink/materialized-hardlink copying and the exact 106 modified, six added and 33 removed path operation. Existing-copy refusal preserves the copied bytes. Independent checks verify all three input files, actual suite exit and two distinct process births absent. The selected source and runner pass their default scans without findings or suppressions.

The subsequent authenticated-archive attempt exits 1 during stage-one validation, with no source trees created. Independent read-only checks confirm the actor birth absent, all three source files and four authority records unchanged, and both authenticated archives retaining their original full hashes and fingerprints. The numeric refusal does not establish its cause; a bounded read-only diagnosis is next. The failed attempt remains preserved. No extraction, generation, compilation, production adoption or deployment has occurred.

Root also revalidates the 178 immutable originals and archive CRC for the completed two-reader original three-pair benchmark. Its six observations finish successfully, but A07/A21 remain failed/open; no benchmark is replayed or candidate adopted. The goal stays active with no pending user decision. Original Gluster/Vault/Consul data and backups remain protected.

## 2026-10-13: read-only archive diagnosis identifies a representation mismatch

The [updated source-preparation receipt](../evidence/bortus-node-source-projection-root-20261013.json) records diagnostic exit 0 and independent read-only post 0. The unchanged Node parser returns all 32,585 logical objects and 553,575,480 expanded regular bytes. For OpenSSL, the first root header carries a bounded `comment` PAX field and mode 0775; the current parser rejects the PAX allowlist at source line 258, before admitting any OpenSSL object. This is a new current-parser witness, not a retroactive assertion about the original caught exception.

The diagnostic process is absent and all three bound inputs plus both archives retain their original bytes and fingerprints. No extraction, crypto replay, network, generation or compilation occurs. A scoped correction is being prepared for the fixed signed OpenSSL distribution: retain bounded inert metadata, preserve bytes and Git execute modes, and remove group/other write bits only from newly created copies. Node guards, path/link/sparse/special-file checks and original archives remain protected. That correction was unexecuted at this checkpoint; the later V5 result below supersedes source-preparation status. Build, security, performance and live acceptance remain open.

## 2026-10-13: authenticated signed-release source projection completes

The [updated source receipt](../evidence/bortus-node-source-projection-root-20261013.json) records three passing scoped SSL distribution controls and six exact release-mapping controls. The retained V4 attempt refuses before tree creation. A complete current comparison checks all 145 paths: all 138 present Node preimages match old blobs/modes, all 112 SSL postimages match new blobs/modes, and all 33 removals are absent from SSL. Only `deps/openssl/openssl/doc/build.info` is absent from the signed Node release. V5 maps that exact path, old/new blobs and modes from Git-modified to release-added, preserving every other byte/mode/removal guard. Git counts remain 106 modified/six added/33 removed; measured release counts are 105 modified/seven added/33 removed. No export-policy intention is claimed.

The once-only V5 actor exits zero. Independent read-only verification binds all six manifests and all three current physical source trees, all three source files/four authority records, the original actor birth absence and both unchanged archive hashes/fingerprints. Finalizers are empty. Newly copied SSL files clear group/other write bits while preserving content/execute modes; original files remain unchanged. The six-control supervisor has disclosed LF/CRLF byte differences with equal normalized text/AST; archive/source content is never normalized. No generated main-branch files, Git context, generator, compiler, custom runtime or production deployment follows this source-preparation result. NASM/tool compatibility, Node build/security, original performance and private recovery/live gates remain open.

## 2026-10-13: NASM parser controls pass; signed-index acquisition refuses

The [NASM prerequisite receipt](../evidence/bortus-nasm-prerequisite-root-20261013.json) records eight passing public parser controls and an independent current-source/process check. Public packet/protocol/index/tar fixtures do not establish actual GPG or Debian provenance; the sparse case models the parsed TarInfo boundary. Original source scanning retains two public primary-fingerprint findings. The corrected runtime files pass their three-file default scan, while the complete eight-file packet still exits one for the historical removed line in its diff. Both findings remain reported, with no suppression/filter or overall eight-file pass. The standalone five-file acquisition packet passes its default scan.

The actual once-only acquisition exits one at stage four. All seven completed commands exit zero, including the original Release signature command; six public downloads remain retained, with no NASM download/tool tree. A separate read-only witness confirms all eight original births absent, current source/artifact hashes and both complete compressed/plain index hashes. The exact current parser rejects an index line over its 16KiB field bound. The longest signed-index line is 75,649 bytes and stanza 76,338 bytes; the NASM stanza still matches the fixed 2.16.01-1/amd64/405,156-byte package digest. This is a current parser witness, not a retrospective original exception assertion. A secondary generic diagnostic also refused before publication and remains retained. No network, crypto or download is replayed for the successful witness. A narrowly scoped package-index correction is being prepared; real package projection, compatibility, generation/build and security remain open. Production and original data/backups remain protected.

## 2026-10-13: scoped index correction qualifies; continuation refuses before download

The [updated NASM receipt](../evidence/bortus-nasm-prerequisite-root-20261013.json) records two passing focused controls. Only package-index lines/stanzas use 128KiB; Release/deb-control fields keep 16KiB, with full size/hash/uniqueness/package checks unchanged. Seven source files pass the default scan; independent verification confirms all three runtime files and two original births absent. The earlier eight controls are not replayed.

The separate continuation exits one at stage one before downloading NASM. Its two source files and all 24 original public records remain current, with the actor birth absent and empty finalizers. A new typed read-only witness finds all seven original terminal identities equal to their started identity fields but with the sole added `same_identity_absent: true` cleanup annotation. The new exact whole-dictionary comparison is therefore false; every original job is zero/reaped/no-refusal and currently absent. This is a current predicate witness, not retrospective exception reconstruction. The correction will admit only that affirmative annotation while preserving every recorded identity field and fresh absence check. No crypto, prior download, package execution or build is replayed. Actual tool compatibility and build/security/performance/live gates remain open.


## 2026-10-14: authenticated NASM projection and builder compatibility verified

[The updated NASM receipt](../evidence/bortus-nasm-prerequisite-root-20261013.json) records two passing identity-annotation controls. The corrected guard preserves all six recorded identity fields and admits only the affirmative cleanup annotation. The new continuation exits zero, downloads only the fixed 405,156-byte NASM 2.16.01-1/amd64 package, verifies its digest against the retained signed complete index, and projects only the executable and copyright. Root independently verifies 24 original records, six artifacts, full index selection, tool hashes/modes/fingerprints, and all ten original/new host births absent. Prior crypto and downloads are not replayed; prior refused actors remain recorded. The signed Release has date 2026-07-11 and no Valid-Until field. The three disclosed NASM advisories remain recorded with no security exception; this is build-only tooling, with no host installation or final runtime inclusion.

The separate fixed-c4 builder compatibility actor exits zero. Readelf dynamic/symbol inspections and the actual version command all exit zero; NASM reports 2.16.01 and requires libc.so.6 through GLIBC_2.34. Independent verification binds four runtime source files, six acquisition records and both unchanged tools, confirms 18 recorded host births and fresh exact container ID/name absence, then separately confirms five later reader/query births absent. The initial independent post refused because absent formatted Docker inspect emits one LF; a new exact-LF post passes without replaying the compatibility workload. Three tool coordinates belong to the container namespace and are not host PIDs.

This qualifies loader/startup/version only. Node regeneration, compilation, default upstream tests, runtime ABI/Prisma/TLS, final-image security, original performance, private recovery and guarded live acceptance remain open. The first long-build proposal is source-only and unrun; review requested explicit private PID namespace identity, compiler temporary files on the new private output filesystem, and durable closure records under the original deadline. No production adoption, deployment or retirement follows.


## 2026-10-14: isolated Node generator refuses; independent cleanup verified

[The literal build receipt](../evidence/bortus-node22-build-root-20261014.json) records actual exit one with empty finalizers and the exact container removed. New-copy Git initialization, add and commit exit zero. The unchanged all-target OpenSSL generator exits two on its first aix64-gcc-as Configure: embedded test/build.info is absent and no Makefile is produced. Configure, compilation, upstream tests and the new-Node probe never start. The fixed three-hour lease, 60-second closure reserve, 2CPU/8GiB/no-swap/PID512, no network and new private compiler temporary directory remain unchanged. Actual resource checks pass; distinct PID and IPC namespace identities are recorded before worker release. The eleven-file source default scan and scanner absence pass. Earlier source-only V1/V2/V3 drafts remain unrun.

The separate outcome-honest post exits zero while preserving the original actor failure. It verifies 83 current records, five runtime sources/authority records, the original working tree, tool fingerprints and both unchanged archive hashes/fingerprints; all 14 recorded host births, fresh exact container ID/name absence and three later post/query births are absent. Four phase coordinates are container identities, never host PIDs; unsampled descendants close through the verified private namespace and removed exact container. No source-generation, build, runtime or security pass follows. Source review now checks the full authenticated OpenSSL distribution for required auxiliary inputs while preserving embedded projected bytes and the exact generator/test recipe. No production mutation or data retirement occurred.


## 2026-10-14: synchronous HS256 primitive controls qualify; integration held

[The isolated authentication receipt](../evidence/bortus-sync-hs256-controls-root-20261014.json) records ten passing control sections and 175 untrimmed comparisons against unchanged public JOSE6.2.12 verification, including accepted/refused outcomes and exact payload/header equality. Actual nonextractable-key HMAC, an independent RFC4231 vector and real key-slot cold/warm/rotation/no-overlap/zeroing controls pass. The candidate authenticates original HS256 compact bytes before using public JOSE claims validation; external unsigned tokens remain rejected. This is finite corpus evidence, not universal verifier equivalence or whole-operation constant-time proof.

Root exact and fresh posts verify all 370 source files, 18 inputs, 5,382 compiled objects and 40,635 dependency objects unchanged, all 16 original process births and fresh exact container ID/name absence, then three later reader/query births absent. Nineteen control-source files and six post-source files pass default scans and fresh scanner absence. The original 300-second/60-second closure, 150-second child/180-second attach, 2CPU/1GiB/no-swap limits remain unchanged; actual private PID namespace, UID1000, read-only/network-none/cap-drop/no-new-privileges checks pass. Original thirteen authorization outcomes, compiled application, typed integration, performance and adoption remain explicitly unproven. Application source and production remain unchanged. A typed isolated integration proposal is being reviewed; the frozen original warm-performance gate remains failed/open.


## 2026-10-14: typed signing-path checks pass; full preparations interrupted

[The typed candidate receipt](../evidence/bortus-sync-hs256-typed-root-20261014.json) records actual exit zero for types, the original ten-section/175-case differential corpus using the real typed export, original thirteen authorization/four key-slot cases (eighteen TAP entries including the parent), and lint. Independent checks bind371 raw source files,394 inputs,40,635 dependency objects and5,382 unchanged old compiler-context objects; the latter are not candidate compiled proof. All64 recorded original births, eight exact container ID/name queries and nine later reader/query births are absent. Source/post default scans pass without suppression, and scanner birth absence is verified. The earlier four public-digest metadata findings remain retained; conventional relative/sha256 rows clear the new source packet without changing code or fixtures. The earlier V4 OCI mountpoint failure remains exit one with no child checks run; its cleanup passed. V5 adds only two empty mountpoint directories in a new source copy. Full production build, original322-unit/eight-integration checks, compiled authorization, performance and deployment acceptance remain open.

[The complement receipt](../evidence/bortus-node22-complement-root-20261014.json) retains the initial11/12 public copy-control result: an existing destination-parent symlink caused44 new objects in a disposable protected fixture sibling before late rejection. No original data was involved. Verifying the entire original destination and source before any new effect makes the unchanged12 cases pass. Further Configure source review shows that22 missing build.info files alone cannot establish generator readiness. The complete complement is exactly6,077 authenticated full-distribution objects minus2,712 existing embedded objects:3,365 additions, comprising128 directories and3,237 files/96,299,821 bytes. Existing embedded bytes and modes remain authoritative even where the full distribution differs.

All15 distinct complete-protocol controls pass, including exact actual-manifest derivation, source/destination symlink refusal, no overwrite, full union checks, mode/type/hash/path refusals, hard-SHA tampering and expiry. Independent current checks bind seven inputs and both original births absent, then the later reader absent. These public fixtures do not authenticate source archives or prove generator readiness. The new actor uses the already authenticated read-only full source, one consumed source FD at a time, with original-tree/full-tree checks before and after. Link and special input types are refused; no atomic privileged-race claim follows. Its ten-file default scan and current scanner absence pass.

The isolated complete-complement build and fresh application dependency preparation were interrupted by a WSL kernel restart. Both WSL invocations return exit one with empty diagnostics; no Python exception or OOM cause is inferred. Current kernel uptime68.43 seconds contrasts with the old actor start tick923435 (about9,234 seconds), and the new boot ID is recorded. The retained complete-complement receipt reports3,365 objects/3,237 files/128 directories/96,299,821 bytes and git-init exits zero, but no generator, compiler or upstream tests start and neither actor nor worker terminal exists. The exact owned build container is observed exited255 with matching image/owner/source, then removed; fresh exact ID/name queries report not found. The application has all371 source files but an incomplete dependency copy, no completion receipt and no dispatched full suite. Independent current-input/authority checks are pending; partial outputs will not be reused. The unchanged Node10800/60 and application900/60 recipes remain separate new-owner work, to be run sequentially. No source-generation, build, runtime, performance, security or deployment acceptance follows the interruption. The earlier failures remain retained. No original data or retirement changed.


## 2026-10-14: fresh full and compiled authorization qualification pass

[The qualification receipt](../evidence/bortus-sync-hs256-functional-compiled-root-20261014.json) records a fresh dependency copy from the unchanged40,635-object authority, production build/native load/lint/types, all322 original units and eight original integrations with no failures or skips. Independent checks bind371 raw source files,400 inputs,5,382 actual compiled objects and40,635 installed objects; all185 recorded births, eight exact container ID/name queries and nine later post/query births are absent. Four standalone worker/core/receipt/schema bindings and the actual8dde native ELF load pass. The original900/60-second full recipe and commands remain unchanged.

The separate compiled fixture and independent numeric join checks pass ten exact HTTP statuses/full-body assertions, twelve fresh SQL calls (five session three-column and seven write five-column projections), thirteen attempt/settlement/worker joins and stable reports through actual server exit. One database and two prepared statement owners are observed. Current371 raw files plus four separately declared generated runtime extras make375 checked objects; this is not375 raw Git files. All34 inputs and the current compiled/installed graphs remain unchanged. All18 recorded births, exact container ID/name absence and three later post/query births pass. Original300/60/180/150 bounds and observer/fixture/oracles remain unchanged. Source and post default scans and scanner birth absence pass.

The interrupted V2 preparation remains exit one and never dispatched. A separate post-restart witness verifies371 source files and the full40,635 authority before/after. Its partial36,721-object copy has3,914 missing and33,442 mismatched complete metadata rows; individual corruption fields and restart cause are not inferred. That partial copy is retained and never reused. The fresh V3 run above uses a new dependency copy.

[The updated runtime-source receipt](../evidence/bortus-node22-complement-root-20261014.json) preserves V6 outer exit one, missing terminals and the observed exited255 container. Its independent incomplete post passes47 current records, all six projection manifests/three original trees/archives/tool authorities, the physical original-plus3,365 complement union excluding only new Git metadata, and exact removed container ID/name absence. Nine recorded host coordinates predate that post's boot; no namespace continuity across restart is claimed. Three post/query births and the later reader are absent, with differing boot IDs recorded without cause attribution. No generator, compiler, upstream tests or runtime/security acceptance follows. Fresh V7 changes only owner/path/labels; its five other runtime files, phases and10800/60 resource contract remain identical and its source scan passes.

The unchanged original three-alternating-pair/six-profile comparison is now running against baseline51e8 and candidate4df4, with all five benchmark files, exporter, fixtures, warmup, oracles and limits fixed. Node V7 is held for this exclusive measurement window. Performance, final image/security, private recovery and live acceptance remain open. No production deployment, original-data change or retirement occurred.


## 2026-10-14: original HS256 comparison complete; warm gate fails

The [original comparison receipt](../evidence/bortus-sync-hs256-paired-root-20261014.json) supersedes the running/held status in the preceding checkpoint. The original three alternating pairs and six profiles complete with actor exit zero and every native inventory present. Root independently recomputes 1,386 distributions / 4,158 numeric values and verifies all 438 exported tar members against raw Git blob IDs, bytes and modes (281 candidate, 157 baseline). All 66 frozen inputs remain unchanged. Exact and fresh posts pass: ten recorded births and eight exact container names are absent. There are no retained container IDs; dispatcher absence is PID-only. Eight later query births are absent. These scopes are not expanded into stronger ownership claims.

The no-warm-regression gate fails five of ten comparable cases. Serial warm p95 medians in milliseconds rise from 6.82 to 8.26 for 200 Pods, 9.99 to 24.14 for 1,000, 7.31 to 8.49 for the 25-large fixture and 7.27 to 7.32 for the three-largest fixture. Audit-small concurrent warm p95 rises from 51.09 to 55.69. Other warm cases improve, but do not cancel failures. The baseline 10,000-Pod false-empty result remains ineligible for equivalently successful latency. No fixtures, driver, warmup, timing windows, limits or tolerance are changed; the benchmark is retained without replay. Functional/compiled qualification remains valid and separate from failed performance acceptance. Candidate 4df4d32 remains isolated and unadopted.

Source review finds the current route already caches redacted Pod rows and their JSON string for the exact cached items array. A further serialization cache is not justified. A held 1,000-Pod diagnostic will reuse the qualified Next collector, worker observer and gate, preserving 13 requests, 41 SQL checks and 26 spans; only the public fixture count and matching exact full-body oracle change. It will run after the isolated Node build's exclusive resource window and will report middleware, route and emission wall windows with instrumentation/overlap limits. It does not authorize adoption or relax acceptance.

Fresh Node V7 is now dispatched once and its exact generator phase has started. No terminal build/test result or new ELF/image/security pass exists yet. Final image, TLS, private recovery and live acceptance remain open. Production, original data and retirement state are unchanged.


## 2026-10-14: V7 header dependency refusal and 1,000-Pod causal trace

[The updated Node receipt](../evidence/bortus-node22-complement-root-20261014.json) supersedes the running status: actor exit one, generator exit two, complete retained failure and exact container removal. The final error is missing Text/Template.pm at generate_headers.pl line 6; compilation and default tests never start. The independent post exits zero, verifies 84 current records, all six original manifests/three physical source trees/archives, four phase terminals, 14 recorded host births and exact container ID/name absence. Three post/query births and the later fresh reader are absent. No generated-manifest, ELF, license/config, runtime or security acceptance follows. The original generator command/platforms/options/tests/deadlines remain fixed; a generator-only search-path correction using authenticated existing module bytes is being prepared in a fresh owner.

[The 1,000-Pod trace receipt](../evidence/bortus-sync-hs256-warm1000-trace-root-20261014.json) records actual actor/exact/fresh/later checks at exit zero. One cold seed and twelve serial warm requests return every exact expected row, with 41 fresh SQL checks and 26 qualified Next middleware/route spans. Memoization has twelve hits/one miss and zero warm CLI calls. The 371 raw source files plus four generated extras, 29 inputs, 5,382 compiled objects and 40,635 installed objects remain current. Nineteen original births, exact container ID/name and three later post/query births are absent. Thirty source files and four post files pass default scans with scanner birth absence; only new source directories/files receive private modes. The qualified observers/gate/lifecycle bounds are retained; only the public fixture count and matching complete-body oracle change.

The numeric windows are instrumented wall observations with nested spans, framework/client scheduling and full-field fixture validation sharing the fixed cgroup. They cannot be summed as independent CPU costs or substituted for the unchanged original benchmark. Causal source analysis continues. The five-of-ten warm performance failure remains; no candidate adoption, production mutation or data retirement occurs.


## 2026-10-14: fresh generator dependency-path attempt dispatched

Fresh V8 starts once after V7 independent cleanup and the completed quiet trace. Root verifies the actor has only fresh owner/path/label and worker-hash changes; all old non-main worker functions and the nested phase implementation remain unchanged. The only worker change binds the authenticated Text::Template subtree (four rows, two files, 72,212 bytes), verifies its signed full-distribution and new-work copies before/after, and supplies PERL5LIB only to generator descendants. It removes the variable before configure/build/tests. No install, download, overwrite, platform/options/test change or partial-work reuse occurs. The same 10,800-second whole/60-second closure and phase/resource bounds remain fixed. Twelve source files pass the default scan and fresh scanner birth absence. V8 is running; no terminal, new ELF or security/runtime acceptance is claimed. V7's failed source/log/terminal/post evidence remains preserved.

The completed 1,000-Pod trace has ordinary warm medians of 7.1405 ms client, 1.4645 ms middleware, 1.578 ms middleware-to-route transition and 0.7175 ms route module. Its twelve timed complete-body reads total 105.967 ms; the whole loop takes 147.012 ms, leaving 41.045 ms for fixture parsing/full-field assertions, inter-request work and overhead outside those timers. Nested medians are not additive CPU costs. The largest warm request includes both an IPC delivery window and a route window; this does not identify SQL, GC, compression or allocation as a cause. Existing row/JSON memoization and bare successful middleware continuation are already present. No source remedy follows from this correlation. A separate source-only proposal will add supported thread/process CPU and GC/scheduling observations with bounded numeric output; the original benchmark, fixtures, permission/freshness limits and failed acceptance remain unchanged. No production mutation or retirement occurs.

## 2026-10-14: CPU helper qualification and pre-operation receipt refusal

[Current root receipt](../evidence/bortus-current-checkpoint-root-20261014.json) records seven new CPU/GC helper controls passing, plus exact, fresh and later cleanup checks. These tests qualify bounded numeric sampling and forwarding behavior only. They do not rerun prior controls or the original performance benchmark. The prepared 13-HTTP/41-SQL/26-Next-span trace remains held until Node V8 and its post checks close; GC delivery coverage remains explicitly incomplete.

Node V8 header generation and configuration exit zero; compilation is running. There is no actual terminal or qualified new ELF. Original build commands, platform, tests, resource and deadline bounds remain unchanged.

The public TCP attempt exits 1 before creating its operation directory. Its generic caller failure does not retain an exception. A separate bounded read-only diagnostic reproduces the first current refusal at the cache prerequisite's `completed_monotonic <= time.monotonic()` predicate. The retained receipt predates the WSL boot; its monotonic timestamp is ahead of the current clock. The diagnostic constructs no transport and issues no API command, creates no resources and accesses no credentials. Four recorded process births are absent on a fresh observation; the operation directory remains absent. This identifies a current prerequisite failure, not the historical exception. Preserve the failed attempt and predicate; obtain a fresh actual cache attestation before binding a new attempt. Public isolation proof would still not authorize delivery into a different private holder.

The read-only 03:30 UTC snapshot shows 3 Ready nodes, 97 Pods, 54 Bound PVCs and 33 current Ready active Helm releases. BORTUS is Ready with zero restarts on its existing immutable image; its Helm release remains suspended. All 40 Longhorn volumes are encrypted with two replicas: 30 attached/healthy and 10 detached/unknown. Both Git sources and the release Kustomization are Ready. This is metadata evidence, not a push/rollout, restore or acceptance claim. Performance, final image/security, TLS, private recovery and guarded live acceptance remain open. No user decision is pending; original data/backups stay preserved.
