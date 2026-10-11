# Immutable image export and sequential preload

`stage-bortus-release-image.py` consumes the completed receipt from the
[immutable builder](BORTUS-RELEASE-IMAGE.md), pinned by its SHA-256, exact full
source commit and exact `sha256:` config image ID. Pending/failed receipts,
source-label mismatches and any runtime-accepted claim refuse. Export and
preload use separate deterministic, exclusive mode-0700 run directories under
the operator-owned runtime parent, which may be mode 0755 without group/world
write. Their files are exclusive mode 0600. Pinned nofollow directory/file
identities and file/directory/parent fsyncs precede dispatch. Existing runs are
never reopened, overwritten, adopted or replayed.

After manual inspection of a retained failed attempt, the migration owner may
explicitly authorize a fresh preload with `--attempt-id <unique-lowercase-12hex>`.
This optional preload-only ID appends `-attempt-<id>` to both the root run and
each remote stage, and is bound in the closed request, reply and receipts. It
does not change the immutable image/tag or bypass tag absence checks. Reusing
the same attempt, an existing stage or a destination release tag still refuses.
There is no automatic retry; the omitted-ID default paths remain unchanged.

Export first checks the exact Docker tag's config ID and all five source/owner
labels on `james@192.168.0.4:2002`. A durable pending receipt precedes Docker
save of that tag. Received archive chunks are bounded and written directly to
the new protected `image.tar`; export errors, timeouts or lost replies leave
an unaccepted partial and pending/uncertain outcome. The helper verifies the
complete regular-file/directory tar inventory, manifest's sole exact tag,
selected config hash/labels/Linux amd64 platform, and ordered layer diff IDs.
Opaque gzip layer bytes are streamed through bounded decompression to verify
their uncompressed diff IDs; raw blob digests are retained separately. Config
environment fields are never returned or put in metadata logs. It re-inspects
the source Docker identity after save before completing the export receipt.
No source tag creation or Docker image running is performed.

Archive bounds are 4 GiB compressed/plain total and aggregate expanded layers,
4,096 members, 1,024 selected layers, 8 MiB manifest/config metadata and 8 KiB
PAX path extensions. Paths, links, unsupported extensions, duplicate members,
unexpected metadata or nonzero trailing tar payload refuse. Selected-platform
resolution is limited to one Linux/amd64 manifest from at most 64 index
descriptors. Unsupported/ambiguous image formats fail closed. These are image
staging bounds, separate from native Secret request ceilings.

```sh
python3 scripts/migration/stage-bortus-release-image.py export \
  --build-receipt /approved/runtime/bortus-release-<commit>/record.json \
  --receipt-sha256 <pinned-build-receipt-sha256> \
  --source-commit <full-lowercase-40hex> \
  --config-image-id sha256:<exact-64hex-config-id> \
  --runtime-parent /home/brajam/.local/share/branconet-migration
```

For `preload`, additionally supply `--export-receipt` and its independently
pinned `--export-sha256`. The caller supplies only a bounded JSON line with
`sudo_password` through its existing protected stdin pipe; never place that
value in arguments, shell history, files, reports or logs. This tool does not
read operator credential files. The password passes only in memory through
SSH stdin to `sudo -S -p '' -v`; subsequent containerd commands use `sudo -n`.
Authorization and those commands share the remote Python session so sudo's
session-scoped timestamp remains usable. Timeouts kill only the newly owned
command PID; they never signal the shared session/process group. SSH's own
local process ownership remains separate. A successful authorization does not
prove that a later policy/expiry check will permit a command.
No interactive prompt or alternate auth fallback is offered. Python cannot
guarantee zeroization of immutable password objects; no such claim is made.

Preload copies and independently re-verifies the pinned export, then handles
only `james@192.168.0.4`, `.5`, `.6`, port 2002, strictly in that order. All SSH
uses BatchMode=yes, StrictHostKeyChecking=yes and ForwardAgent=no. Each node
creates a fresh `.bortus-release-preload-<fullcommit>` stage directly under its
verified owned home, mode 0700, with parent/anchor checks. Either exact tag
spelling (`bortus:release-<commit>` or `docker.io/library/…`) already present
refuses; unrelated images do not block it. The inventory is bounded and must
have the actual expected ctr header. It rechecks tag absence after receiving
the exclusive mode-0600 archive, verifies size/SHA, flushes the file/directory,
and saves a durable remote pending record before import. An existing remote
stage also refuses. No adoption or automatic retry is performed.

The fixed runtime command is `/opt/containerd-k8s/bin/ctr`, address
`/run/containerd-k8s/containerd.sock`, namespace `k8s.io`. After import, the
helper verifies actual root index/manifest content hashes, unique platform
selection, selected manifest's config and ordered raw layer digests, then the
config ID, labels and ordered diff IDs. Metadata captures are bounded in memory;
whole image config/Env objects are not saved as logs. Complete import stdout
and stderr remain separately protected on the node. Fixed reasons are returned
on failure. All three root runtime digests must agree; the config ID is retained
as a **different identity**, never substituted for a runtime/manifest digest.

Local intent precedes each SSH call; remote intent precedes import. Lost reply,
invalid/partial metadata, import error or a durability failure stops the
remaining nodes and retains pending/uncertain receipts. The coordinator must
inspect those outcomes explicitly; rerunning this tool cannot resolve them.
Successful earlier node imports are retained and are not undone. Each owned
SSH/import child is waited/reaped; query timeouts are 30 seconds and save/import
operations are limited to 1,200 seconds. A remote operation may outlive a lost
SSH reply. No remote cancellation or cleanup is attempted.

Docker and containerd tags provide no atomic compare-and-set. The coordinator
must hold exclusive source/tag and destination import ownership, exclude
concurrent writes to protected stages and inputs, and recheck source/controller
requirements at release. Checks around dispatch detect drift but do not make
these operations atomic. This tooling never runs an image, deploys a workload,
qualifies a holder, grants admission/RBAC, or proves application/data/migration
recovery. It records `runtime_qualified=false` and `deployed=false`. Historical
fixed-image distribution/recovery receipts remain historical.

Local fixtures exercise public archives and actual POSIX persistence with
mocked Docker, SSH, sudo and ctr responses. They establish tooling behavior,
not a real export/import, power-loss durability or runtime acceptance.

The first actual immutable holder preload stopped before transfer/import when
the old remote commands created new sessions after sudo authorization. Its
protected root/node refused or uncertain records remain retained. Local Python
child tests reproduce the session mismatch and qualify shared-session handling;
they do not execute sudo, SSH, ctr or an operator password. Actual new preload
and holder/runtime acceptance remain with the migration owner. The later actual
three-node result and its limited runtime scope are recorded below.

Root independently verifies selected native commit `15fb94ba`: seven exact raw
files/modes, 86 original artifacts, both unchanged dependencies and the final
26 focused/64 combined release cases. After integration, all 249 current
`test_bortus*.py` migration-helper cases pass under WSL without skips. Source
and test inputs remain unchanged through execution. The [integration receipt](../evidence/bortus-release-staging-integration-20261011.json)
records the exact scope; it grants no actual export, preload or runtime acceptance.

The actual `7e30b9b4` holder export completed at 09:19:37 UTC on 2026-10-11.
The protected 1,150,322,688-byte archive has verified config/source/layer bindings;
its [receipt](../evidence/bortus-holder-source-image-7e30-20261011.json) records
export separately from the later three-node preload and public-fixture runtime.
Admission and production-holder/data qualification remain pending.
A pinned Trivy 0.75.0 default image and image-config scan completed with zero
Secret findings and 346 vulnerability entries (67 High, one Critical). Scanner
exit 1 represents findings, not an accepted clean image. Four fixable High entries
are in bundled kubectl's Go/x/net dependencies. Its production remediation and
the inert Node-only holder reachability review remain open; no app entrypoint ran.

The fresh explicit preload completed on all three nodes at 10:03:40 UTC on
2026-10-11. The [actual staging/runtime receipt](../evidence/bortus-holder-preload-runtime-7e30-20261011.json)
binds every node to source/config/layers and the same OCI manifest. The first
public runtime probe exposed `ErrImageNeverPull`: ctr import had retained the
release tag without a digest image-name alias. Root separately created each
absent exact `docker.io/library/bortus@sha256:…` name, without force or changing
the source, and verified its target plus source/config/layers before and after.
This is a recorded operator cache correction, not a capability of the preload helper.

The actual kubelet Pod spec and status.imageID use that exact digest, while
status.image displays the verified source release tag. The failed strict display-name
comparison remains recorded. Current production-reader/consumer fencing still
needs a narrow immutable-imageID correction; a display name cannot replace digest proof.

The final public-fixture attempt completed at 10:21:15 UTC: Node 22.23.3,
Prisma 6.19.3, two public SQLite rows and integrity, plus the unchanged bounded
Node reader's 8,192-byte framing passed on every node. The image entrypoint was
overridden; token automount was disabled, root filesystem was read-only and
only an owned writable memory emptyDir held the fixture. Each Pod was deleted
with current UID/RV preconditions and complete-list absence; the original writer
UID/image remained unchanged. No production PVC/Secret data was read. This
qualifies that inert public runtime, not a read-only production PVC holder,
active admission, application startup, fresh checkpoint or independent recovery.

Three failed attempts remain retained. The third was a private launcher quoting
error: the WSL default shell expanded dollar-prefixed Prisma methods before SQL.
The final launcher used base64 plus `--exec` and verified decoded source SHA
before execution. Source/log/terminal identities and the exact cleanup of each
failed fixture remain in protected records. The image vulnerability findings
and final application performance acceptance stay separate and unresolved.

The [actual fresh BORTUS cold checkpoint](../evidence/bortus-cold-checkpoint-b473091bebef-20261011.json)
completed at 10:45:09 UTC on 2026-10-11. The immutable inert reader mounted the
original claim read-only; SQLite bytes went directly into authenticated age
ciphertext and the NAS copy matched. A cold snapshot and full encrypted 1 GiB
Longhorn NAS backup completed. Complete raw PodList name/UID checks prove reader
absence; the original writer is Ready on workernode2, its volume is healthy, and
Deployment/HelmRelease/Kustomization fields are restored. Capture exposed a
cross-node RWO resume-order defect; exact owned-reader removal and explicit
same-journal recovery completed without recapturing data or repeating creates.
All failed setup, transient-detach and controller-default-label attempts remain
recorded. A fresh read-only source preflight validates this closed checkpoint and
an absent masternode restore target. Complete SQLite row equality, independent
restoration, active admission and the final application release remain pending.

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

## c29fc three-node preload completed

The [single current preload receipt](../evidence/bortus-app-preload-c29fc-20261011.json)
records actual exit0 on 192.168.0.4/.5/.6, completed at12:37:08 UTC on
2026-10-11. All three nodes match the exact archive, config, five source labels
and OCI manifest `sha256:068254f38c47f99fd35604185a806a92147d934010329638b32adb5c19802c90`.
That manifest differs from the Docker config ID `sha256:b147db1da11fc66634954e12f15a4ef19fb3eb5e06b8b4e7d9676212caf39b4c`.
The original receipt and owned launcher terminal agree; root freshly verifies
launcher absence. This stages the image only. At this12:37 checkpoint, exact
digest-name cache aliases and public-fixture runtime were pending; their later
completed qualification is recorded below.
No new app Pod, admission guard, PVC consumer or production schema was deployed.


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


## Accepted legacy image digest-cache maintenance prerequisite

The [actual legacy cache receipt](../evidence/bortus-legacy-digest-cache-20261011.json)
binds the retained1438 archive/config and15 ordered layers to manifest3b076
on all three nodes. Source1438 is recorded historical provenance only; this
older build is not retroactively granted the new five-label qualification.
The first operation retained actual exit1 after its first node's tag succeeded:
a second verification reused an exclusive journal filename. Root inspected its
remote intent/source-after verification and local/remote wrapper closure;
the partial receipt was never adopted as three-node success or replayed.

A reviewed corrected wrapper used distinct source/alias stage names and a fresh
owner. Actual exit0 at13:28:52 UTC verified the first exact existing alias and
created the two absent aliases without force. Each source and alias retained
config/platform/layer identity. All four Linux identities and exact Windows
launcher are absent; all45 frozen preparation files were independently rehashed.
There was no import, application startup, production schema or Secret operation.

At the pre-rollout checkpoint, the original Ready writer reported literal
config imageIDa8f40 with a mutable tag. That is not normalized into the required repo@3b076 runtime proof. A
separate disposable public-fixture qualification is required before CI/Flux
pins the same accepted legacy bytes. This is a pre-schema maintenance step;
1438 cannot be a final KV rollback image and must leave every active allowlist
before a forward-schema entrypoint can touch the original claim. Full-row
production restoration, final image/performance/security and live acceptance
remain separate requirements.


## Accepted legacy digest inert runtime completed

The [actual legacy runtime receipt](../evidence/bortus-legacy-digest-runtime-20261011.json)
records one public-only Kubernetes qualification completed at13:33:19 UTC,
actual exit0. All three Pods used literal repo@3b076 spec and actual imageID;
Node22.23.3/Prisma6.19.3, two public SQLite rows, integrity and8192-byte reader
framing pass. It uses the same frozen fixture/reader contract with no token,
production PVC, native Secret value or application entrypoint. Exact cleanup
uses UID/resourceVersion deletion plus independently fresh complete PodList
absence. Root verifies all seven Linux processes/exact Windows launcher absent
and all27 helper inputs unchanged. The original Deployment/Ready writer's UIDs,
resourceVersions and mutable spec image remain identical before and after.

This is current accepted-artifact runtime proof for the proposed pre-schema
legacy digest pin. Historical source qualification and modern five-label
provenance remain distinct. At this13:33 checkpoint, CI/Flux publication and
observation of the replacement writer, storage/controller identities and
credential references were pending; the subsequent completed rollout is below. It is not production-row preservation, schema-forward, active
admission or final KV/performance/security acceptance.


## 2026-10-11 13:48 UTC: legacy digest CI→Flux rollout verified

The [actual rollout receipt](../evidence/bortus-legacy-digest-flux-rollout-20261011.json)
records PR #2 merged as `182eafd4da4cda56b2a846d0c5f067e527eb79c4`.
Its tree exactly equals reviewed head `f15f1e03`; main run `38144292988`
completed validation and promotion successfully. Flux source and migration
owner are Ready at that exact validated revision with prune/force false.
BORTUS HelmRelease is resumed, UpgradeSucceeded at generation9. Its sole Ready
writer is `bortus-5c55f6d5b5-67mnk` on workernode2, with literal spec and
actual imageID `docker.io/library/bortus@sha256:3b076fb9b7fb64fd760691c0120f29d4e363d4ccb9910a596ff211bfc3ea0879`.
The complete PodList shows the previous writer name and UID absent. This
supersedes the earlier mutable-tag/config-only writer observation.

Deployment, Flux owner/source, HelmRelease, PVC/PV and external principal UIDs
are preserved. The claim remains Bound, its PV Retain, and Longhorn is encrypted
and healthy with two running replicas. Existing credential references and the
legacy service account remain unchanged. The external `bortus-kv` principal
still has zero grants and automount false; all six guard objects remain absent.
All three nodes and the other33 releases are Ready with current observed
generations. No manual reconcile, native Secret value or production DB read was
used. This is accepted-artifact maintenance, not production-row restoration,
schema-forward, new KV adoption, final app security/performance or live auth/UI
acceptance. Next guard publication must separately resuspend BORTUS and retain
both accepted legacy and qualified inert images only for pre-schema restoration;
legacy must leave all allowlists before any forward-schema entrypoint.


## 2026-10-11: actual legacy schema metadata qualification

The [root live schema receipt](../evidence/bortus-current-legacy-schema-20261011.json)
passes against the sole Ready legacy digest writer. Seven migration names,
finished/non-rolled-back history and all thirteen application table column layouts
match; writer UID/RV, owner/template and claim/PV identities match before and after.
The fixed Node program opens SQLite read-only and selects only migration ledger
and schema metadata. It runs through stdin; no app entrypoint, application rows
or credential values are read. Separate reads and name-based exec are non-atomic.

The first actual check failed because raw Git SQL checksums differ from deployed
SQL file bytes. Actual ledger hashes match all seven files in the immutable legacy
image: six are exact Git LF-to-CRLF conversions; the seventh is exact Git LF. The
new manifest pins this exact mixed history. It does not accept arbitrary alternate
checksums. Original failure and diagnostic receipts remain retained. An earlier
local launcher used Windows CRLF reader bytes instead of the already qualified
embedded LF program; that failure and its non-causal negative checks are retained.

The [callable producer](../scripts/migration/schema-current-writer-v1/current-schema-producer.py)
is source-bound with its fixed reader, exact image migration manifest and controls.
Six actual disposable Node fixtures and sixteen local producer controls pass,
including identity/RV/storage drift, forward schema refusal, FIFO nonblocking open,
selector-constructor failure child reaping and bounded output/deadline cleanup.
The actual producer uses fresh verified mTLS metadata and an exclusive fsynced
0600 receipt in a 0700 directory. Receipt names match the phase-one callback ABI.
Invoke it fresh under the callback's shared deadline each time; this observed
receipt is historical evidence. Guard publication, actual admission probes,
independent whole-row restoration and final app/image/performance remain open.

## 2026-10-11: coordinator review and subagent ownership

Coordination now uses this migration coordinator and the two existing application
and native/recovery subagents. The seven old BORTUS chats are archived; no new
chats or chat messages are part of this orchestration. Application edits remain
in the isolated application worktree, and the recovery module in its own branch.

The [independent FIFO review](../evidence/bortus-account-fifo-root-review-20261011.json)
verifies 338 raw source Git blobs/modes, 16 raw qualification blobs/modes, 37
private originals, all 351 ZIP members, 337 executed source files and the 4,262
compiled hash inventory. The retained five stages have actual zero exits, with
235 unit tests and four original strict HTTP tests passing. The default scanner's
actual exit remains one: all 159 selected public checksum/prose byte spans were
independently rehashed; two historical provenance findings remain open. This
receipt covers a48601a/b6fde8d only, not the subsequent shell-error correction,
final image, live application acceptance or performance.

Automatic approval review rejected the combined guard chart push/PR command,
stating "blocked by policy", before execution. The
[rejection record](../evidence/bortus-phase1-publication-review-rejection-20261011.json)
leaves guard publication, live admission probes and independent whole-row restore
open. Existing source, storage, credentials and running writer are preserved.
The active goal remains incomplete; local recovery and app qualification continue.

## 2026-10-11: guards delivered through CI and Flux

[Charts PR #3](https://github.com/jtmb/branconet-charts/pull/3) merged the
reviewed guard chart. Main CI run 38150613416 passed validation and promotion;
Flux source and `migration-releases` both applied the exact validated merge
commit. All six Fail/Deny guard specs match their reviewed renders, and all
three policies report current-generation type checking with no warnings.

Fresh actual checks preserve the original controller/storage/principal identities,
sole Ready legacy writer, credential references, encrypted healthy two-replica
Longhorn volume, three Ready nodes and the other 33 Ready releases. The BORTUS
HelmRelease is suspended with the same legacy image; its running Deployment
remains at one replica. The external `bortus-kv` principal still has no grants.

The earlier combined-command approval rejection remains historical evidence.
Separate exact branch push, PR creation and reviewed-head merge commands succeeded.
No manual Flux reconciliation was used. The
[publication evidence](../evidence/bortus-phase1-guard-publication-20261011.json)
records actual publication and metadata checks. It does not prove the 43 admission
probes or independent whole-row restore: neither has run yet. Review identified
an additional typed collection item-header assumption in probe cleanup; its
qualified correction is required before fixture creation. No forward schema or
new application entrypoint has started. Two subagents and the migration coordinator
continue the active goal; the seven old BORTUS chats remain archived.
