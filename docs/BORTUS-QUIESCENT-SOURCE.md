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
