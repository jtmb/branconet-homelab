# Quiescent phase qualification

`bortus-quiescent-phase.py` supplies the existing nine-field qualification packet;
it does not grant image, admission enforcement, forward migration or live acceptance.
Construct the graph from its `interval` export (or inject that exact source module),
including its Observer, IntervalClient, QuiescentCheckpoint and QuiescentArchive.
The archive must receive that graph's quiescent module. Default callers are unchanged.

Construct `PhaseQualifier(observer, archive_callback, legacy_binding, verify_binding,
ready_directory=..., reader_path=..., manifest_path=..., interval_module=...)`, then
pass it as QuiescentCheckpoint's qualify callback and call `bind(operation)` once.
The exact six-field binding contains phase, selected image, source SHA256,
qualification receipt SHA256, admission contract and all three policy/binding pins.
The contract is the existing canonical full workload/ref/digest contract; pins contain
the exact UID, opaque RV and canonical spec SHA for both objects. Legacy must be
allowed in the first phase and absent in the forward phase. Explicit
`authorize_forward(binding)` installs the later published phase exactly once while
guard-transition-open; it cannot replace policies/bindings, adopt drift or repin.

Root's `verify_binding(binding, deadline)` must rehash its pinned actual source,
image/preload/runtime and publication receipts, freshly verify the approved image
cache contract and return that exact closed binding. Boolean success or a bare
receipt pointer is insufficient. This is external trusted authority; the producer
does not itself establish those image or publication facts. Static actual probe
transcripts remain historical enforcement proof, never newly observed outcomes.

The producer itself freshly GETs only the fixed six admission objects through
verified TLS before and after schema checks. Exact UID/RV/spec, current generation,
warning-free typechecking, Fail/Deny, full namespace/resource/reference coverage
and canonical tagless approved images must match. The borrowed live three-control
observer prerequisite surrounds IO. It remains necessary even if the root callback
returns valid metadata. No callback, schema flag or fixture can replace live continuity.

Before stopping Deployment, the unchanged Ready schema producer creates a fresh
exclusive schema receipt during each invocation. Its subprocess/API budget is
`min(original absolute lease, invocation + 300s)`, without extending the whole lease.
Only the pinned legacy-image reader and migration manifest are accepted. Once the
latest authenticated capture is confirmed and captured-zero, the archive adapter
authenticates it once, validates seven migrations/public topology, cleans tmpfs and
emits a separate schema receipt. The qualifier pins that receipt and the exact
ciphertext inode/hash and revalidates those identities plus fresh zero-writer,
storage/control UID and watch fences on every later callback. This is **static
authenticated archive schema proof with fresh zero-writer fences**, not a fresh
Ready-writer read. It preserves the identical two forward packets, including the
schema SHA, across the entrypoint-pending pre-dispatch check.
The final packet also requires a fresh unchanged Ready-writer snapshot before
stop, or a fresh complete zero-writer/source fence after the remaining long IO.
Captured-schema state cannot regress to the Ready branch; missing confirmation
or drift refuses. GETs and exec/watch checks remain non-atomic observations.

An exclusive protected `phase-qualification.json` sidecar binds the two explicit
phase configurations and scoped schema receipts; short updates check inode/hash and
fsync file and directory. No lock covers transport or schema IO. Refusal is sticky;
there is no replay/adoption, automatic controller resume or cleanup mutation.
`close()` independently closes only retained schema/cipher descriptors. The outer
coordinator independently closes the producer, client, observer and journal.
QuiescentArchive has no close method; it closes each invocation’s resources
internally. Root also closes any separately owned pins. Source files, keys,
plaintext, raw API errors and whole objects never enter this sidecar. Real qualification
still requires root's current source/image/publication callback and final forward
entrypoint/whole-row recovery/compatible rollback gates. Local controls are separate
from live production acceptance.

[Root integration](../evidence/bortus-quiescent-phase-root-20261012.json) verifies
eight raw files, nine unchanged dependencies and18 originals. All19 local
controls pass on176 unchanged private files with owned-process closure.
Actual image/publication callbacks, latest-data capture and forward acceptance
remain pending.
