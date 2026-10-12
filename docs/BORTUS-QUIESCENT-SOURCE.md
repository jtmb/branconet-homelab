# Quiescent source before forward migration

`scripts/migration/bortus-quiescent-source.py` is a separate callable composition.
It never weakens ReadySourceFence or changes the existing completed cold capture.
Existing capture resumes the writer before full backup completion; it cannot
prove a continuous zero-writer interval for forward migration.

Construct an exclusive existing cold Journal/prepare record with additional
`baseline.legacy_image`, complete original protected claim names, and
`baseline.quiescent_storage_pins` binding the PVC/PV/StorageClass UIDs and exact
spec hashes. Fresh checks enforce unchanged credential-reference/storage specs,
1Gi claim capacity, encrypted two-replica Longhorn v1 and literal spec.Standby=false.
The PVC/PV pin identities must match the original baseline, and the StorageClass
pin must name exactly longhorn; pins for another healthy claim cannot substitute.
No credential or application values are accessed. Supply those pins through the
trusted initial source inspection, not reconstructed from a later stopped state.
The initial exact source writer and sole legacy container image are revalidated.
Also supply three exact control spec pins (only the controlled replicas/suspend
field excluded) and ControlTrace. The trusted root watch producer
must establish verified TLS readiness from complete LIST RVs before stopping,
durably record bounded projected events, and mark ERROR/410/EOF/gap/overflow/fsync
failure sticky. ControlTrace validates those projections; it is not a collector
and its readiness record is not independent actual watch proof. Opaque RVs must
equal the latest observed event. Separate GET/watch/mutation calls are non-atomic.

`capture_quiescent()` qualifies the legacy-approved image/guards/schema, creates
the exact read-only inert holder, suspends the existing controllers conditionally,
stops the original Deployment using its UID/RV intent, and captures authenticated
current SQLite plus cold snapshot/full NAS backup while the writer stays stopped.
It removes its owned holder once with the existing durable deletion primitive and
requires complete name/UID absence and no active original-claim consumers. It
does not resume controllers or mark a resumed checkpoint completed.

After full backup and complete holder absence, explicitly invoke
`open_guard_transition()`. It durably records a once-only UID/RV intent and resumes
only migration-releases, while the HelmRelease remains suspended and Deployment
remains zero. This lets validated Flux apply the legacy-image withdrawal; keeping
that owner suspended would prevent the guard change. The trace authorizes only
this reviewed true-to-false owner transition, never an HR or Deployment resume.
Any ambiguous owner reply is retained and cannot be retried or adopted. The HR
image/spec stays pinned until the root's durable forward launcher publishes and
resumes a compatible image through CI/Flux. Pre-dispatch proof requires this
explicit guard-transition phase. Final image launch is outside the cold interval.

The deadline-aware archive callback must use the actual fixed reader and existing
pinned encrypted archive machinery, authenticate the NAS copy, close owned
children and honor the supplied absolute deadline. The old archive.capture resets
its timeout and is not an appropriate callback. This library owns no transport,
watch thread, credential provider or reader child. Their outer owner closes them
independently. The cold capture interval is bounded to at most 2100 seconds; waits
and callback calls share that absolute deadline rather than resetting it.

Before `dispatch_entrypoint(launch)`, a fresh trusted root qualification callback
must verify all three same-UID policies/bindings against exact canonical specs,
active Deny, legacy digest absent everywhere, approved compatible image/source,
current schema seven and actual image/preload/runtime/admission receipts. Its
closed metadata packet is trusted caller input, not actual qualification itself.
The module rechecks source, live trace and qualification immediately before a
durable once-only entrypoint intent. The root launcher is responsible for the
actual admitted forward workload; a returned receipt does not prove migration,
row preservation, principal/RBAC adoption, security, performance or rollback.

Failures retain ciphertext, targets, control intents and pending/uncertain launch
state. There is no automatic resume, repeat launch, adoption or cleanup mutation.
The same in-process owner must retain the interval; a reopened captured journal
cannot construct a new operation or adopt the prior watch. A malformed or late
launch reply is uncertain even if a caller may already have started the workload.
After legacy removal or forward entrypoint ambiguity, restoration must use a
separately qualified compatible eleven-migration image. The old pre-KV Audit
withdrawal route cannot be used after forward migration or principal adoption.
Public errors contain fixed codes; raw callback/API frames are not propagated.

This preparation has no CLI and grants no live authorization. Root still must
wire and qualify the actual durable control-watch producer, schema-only inert
reader, image/guard validation and final forward/rollback execution.

The separate [continuous control observer](BORTUS-QUIESCENT-WATCH.md) supplies
the borrowed trace through actual verified TLS streams and fsynced metadata.
Its controlled local fixtures remain separate from live source continuity.


The [quiescent archive adapter](BORTUS-QUIESCENT-ARCHIVE.md) is now available
with a [root composition receipt](../evidence/bortus-quiescent-archive-root-20261011.json):
45 scoped local controls pass against current dependencies. It supplies the
encrypted, authenticated SQLite stream and exclusive fsynced NAS ciphertext
copy under the original quiescent deadline; existing archive callers retain
their default behavior. No live capture was dispatched. Actual schema/image/
admission producers and independent restore still precede forward execution.


The combined composition supplies `quiescent_module=observer_module.quiescent`
when constructing QuiescentArchive. Its default graph remains unchanged; the
explicit injection binds the archive's strict operation identity to the observer's
exported source classes without global module reassignment. Construct the operation
from that same module and use the observer's actual trace and ControlJournal.

After captured-zero, `archive_callback.schema_metadata(operation, manifest_path,
manifest_sha256, deadline=operation.deadline)` authenticates the exact newly
captured ciphertext into private tmpfs, checks the pinned actual legacy-image
seven-migration ledger and public topology, independently cleans tmpfs and repeats
zero-writer/source/watch fences before returning a new protected schema receipt.
It does not use or weaken the Ready-writer producer. This source-bound archive
receipt supports stopped-schema qualification while continuous zero writers and
same physical storage remain established. It does not prove original rows,
live Ready status, forward execution or recovery acceptance. The trusted root
phase callback must independently bind image, guards and the actual receipt.


Root independently qualified the integrated shared graph on `1daea8f`: [65 scoped controls passed](../evidence/bortus-quiescent-composition-root-20261011.json) without skips in 14.251 seconds. Frozen working sources remain unchanged, and the test supervisor is absent. Actual local TLS/age/SQLite fixtures use mocked kubectl/SSH; this is local composition acceptance and does not authorize or prove live latest-data capture or forward migration.

The separate [lease-bound interval client](BORTUS-QUIESCENT-INTERVAL.md) now supplies
fixed inherited reads and once-only conditional dispatches under the actual borrowed
Observer and original absolute lease. Construct the graph from its exported watch/
quiescent modules; Ready/default clients are unchanged. This transport is separate
from root-owned source/image/schema/guard phase qualification and live acceptance.

A [fresh actual Ready-writer schema check](../evidence/bortus-current-schema-20261012.json) exits0 in0.776s: unchanged legacy3b076 writerUID, seven complete original migrations/checksums and all13 public table topologies match. No credential/application rows or application entrypoint were read/run. The bound producer closes/waits its exec; an independent childPID was not recorded, so that stronger absence claim is not made. This is current metadata, not latest whole-row data recovery or forward-schema acceptance.

The default quiescent NAS transport prerequisite was missing: runtime/bin/ssh did not exist. Root [exclusively copied the public system executable](../evidence/bortus-sqlite-nas-tool-20261012.json), boundSHA c6942676b14478f22ccad4b62c40033d18fae3212b5777fd6941aa6e4db1e183, owned0700 with file/directory fsync. SystemSSH stays byte-identical; no connection or private key read/hash occurred. The separate opt-in CIFS SQLite-cipher writer remains in qualification; no current-data capture or writer stop has begun.
