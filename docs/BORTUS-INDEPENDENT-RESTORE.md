# Callable independent restore coordinator

`scripts/migration/bortus-independent-restore.py` is locally qualified as a callable
composition over immutable root `8f69b51`, with no CLI. Its exported reader is
loaded once and supplies the exact MutationAPI/Collector/data/credentials classes.
SourceFence constructs its own exact read-only MetadataAPI. Validated typed lists
infer only absent item type headers; named reads and conflicting explicit headers
remain strict. The original live preflight refused headerless PodList items before
any mutation. Current-source qualification is recorded below. Use
`restore(run_directory, checkpoint_journal, checkpoint_sha256, original_archive,
holder_image, alternate_node, kubeconfig_path, options, qualify_image, *, age,
recipient_file, identity_file, deadline)` with one absolute monotonic deadline at
most 300 seconds ahead; no phase resets it.

Root's `qualify_image(image, target_name, deadline)` returns exactly holder_image,
source_commit, config_image_id, sorted three node_names, protected_claim_names
(`bortus-data`, exact target), qualification_receipt_sha256,
admission_receipt_sha256 and literal current_validation=true. This is trusted
caller metadata, not evidence by itself. Root must separately wire actual current
source/image/three-preload/runtime/guard checks. Boolean shortcuts refuse; the
binding is rechecked before later mutations/data/delete and cannot change. A
config image ID is not a registry manifest digest.

The separate [admission validator and callable probe collector](BORTUS-ADMISSION-QUALIFICATION.md)
check six-object identity/spec/type-check metadata and forty actual dry-run
outcomes. Root publishes through the existing Flux owner after a fresh completed
cold checkpoint and resumed Ready writer, then supplies current revision/pin
verification to the bounded collector. Disposable inert Pod and replicas-zero
Deployment fixture mutations have durable ownership and complete-list absence
checks. Local HTTPS fixtures and returned metadata cannot grant the restore
callback's live admission acceptance; separate actual root receipts are required.

Exclusive fsynced intent/journal bind checkpoint, qualification and helper source
hashes before mutation. The actual Collector starts before creates. SC/PVC/holder
creates require durable pending intent and fresh full admitted-spec GET validation
before confirmation. Binding waits for real same-UID watch observations. Sealing
waits for true/true to true/false and exact latest watched GET RV; missing history
never causes a relist or speculative irreversible seal. Current full health must
prove the sole inert read-only Running/Ready holder and exact engine/two RW replicas.

ReaderLauncher returns the exact owned exec child; only data.execute sends the
fixed reader via stdin. It directly encrypts, authenticates both archives,
normalizes in tmpfs, compares complete recovery rows and independently cleans both
copies/child under the shared deadline. Source/image/watch/health fences surround
the read. Fresh UID/RV durable holder deletion must be followed by complete LIST
absence of both owned UID and name; replacements refuse. There is no failed-watch
cleanup mutation, retry, replay, adoption or target/cipher removal.

Collector, SourceFence and journal close independently. A duplicated pinned run
directory FD supports exclusive file+directory-fsynced final receipt after closure.
Failures retain intent, journals, targets and ciphertext for review. Receipts and
results always leave overall live restore and image/runtime/admission acceptance
false. Separate reads and name-based exec are non-atomic. Callback fixtures cannot
open actual release gates; fault injection is not power-loss proof.

Twelve controlled local cases pass against the retained exact source: fresh
loopback TLS source/admitted-resource requests, durable watch and journal
composition, Python child execution in place of Node, disposable age encryption,
SQLite/tmpfs whole-row matching and mismatch, target collision/replay refusal,
watch ERROR, qualification drift, fsync failure and independent closure. The
watch response is controlled in this composition fixture; standalone collector
TLS qualification remains separate. All first failures are retained. No operator
credentials, Kubernetes APIs, Node, Docker or live restore were used.

Related: [watch](BORTUS-RESTORE-WATCH.md), [mutations](BORTUS-RESTORE-MUTATIONS.md),
[consumer](BORTUS-RESTORED-CONSUMER-FENCE.md), [reader](BORTUS-RESTORE-READER.md),
[data](BORTUS-RESTORE-DATA.md).

Root selected integration independently verifies the seven raw files, 25 retained
artifacts and 16 unchanged dependencies. The [scoped integrated suite](../evidence/bortus-independent-restore-integration-20261011.json)
passes 423 `test_bortus*.py` cases with no skips or changed source. Five differently
named modules are outside this run; no live restore is established.

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

Root integrated the selected admission collector, exact runtime imageID checks
and cold holder-release ordering fix through immutable handoffs, preserving the
actual earlier checkpoint evidence. The [combined local receipt](../evidence/bortus-admission-cold-helper-integration-20261011.json)
records 474 passing current test_bortus*.py cases, zero failures/errors/skips,
144 frozen Python source files and reaped exact process owners. This discovery
scope excludes differently named test modules. Loopback/fake API and disposable
local data checks do not prove live guard enforcement or independent recovery.
The corrected helper has not recaptured live data; the completed checkpoint
remains bound to its original executed source and explicit recovery journal.

The [root maintenance/preflight review](../evidence/bortus-maintenance-preflight-review-20261011.json)
verifies 37 offline proposal payloads, 20 raw committed source blobs/modes, six
exact canonical guard renders, the grant-free externally Flux-owned bortus-kv
ServiceAccount and the BORTUS-only declarative suspension. The actual 11:15 UTC
metadata-only preflight using the corrected helpers passed against the unchanged
completed checkpoint: original writer/storage are healthy, the target remains
absent and masternode is the alternate. It reads no database or native Secret
values and makes no mutation. Neither offline renders nor this preflight prove
admission, independent restoration or application acceptance.

Keep Deny activation held until a qualified compatible app image permits the
planned recovery route. An inert-only allowlist would deny legacy writer
replacement even with its HelmRelease suspended. With prune:false, removing
guard files/references does not remove live Deny bindings. The reviewed
pre-adoption withdrawal alternative explicitly changes all three existing
bindings to Audit through validated Flux, requires fresh observation and owned
holder absence, then resumes the unchanged legacy release through another
validated revision. Audit is not enforcement acceptance. That withdrawal path
is forbidden after forward schema/principal migration or KV adoption; retain
guards and recover with an approved compatible image and current accepted data.
Actual invocation still needs the root's current image/runtime and admission
proof callback; complete probes before creating the isolated restore target.


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

The current reader passes 57 scoped metadata/source/checkpoint preflight tests
with frozen inputs and an actual reaped child. Fresh actual SourceFence.prepare
also passes using the same metadata bytes: original storage/controller identities,
completed backup and unused restore target are confirmed. This is read-only
preflight evidence; admission publication, actual probes and whole-row restoration
remain open. The earlier metadata_shape refusal is retained. See the
[typed-collection evidence](../evidence/bortus-typed-collection-preflight-20261011.json).
