# Continuous quiescent controls

`scripts/migration/bortus-quiescent-watch.py` implements the separate read-only
observer for the [quiescent capture/control composition](BORTUS-QUIESCENT-SOURCE.md).
It exports quiescent and credentials once; construct the operation from those
exact exports and its ControlJournal to serialize short journal/sidecar saves.
It does not change ReadySourceFence, restore-watch, metadata or admission code.

TLSControls uses fresh verified options for every connection. Production origin
is exactly https://192.168.0.4:6443; an explicit localhost/127.0.0.1 origin supports
controlled fixtures only. Scope is fixed to the BORTUS apps/v1 Deployment,
Flux HelmRelease v2 and migration-releases Kustomization v1. Named complete typed
LISTs use fieldSelector metadata.name and limit2, refuse missing/extra/continued
items, and retain exact collection RVs separately from item RVs. Each watch starts
at its exact LIST collection RV. Per-item omitted kind/API fields are accepted
only under the correct complete typed LIST header. Watch objects must identify
the exact kind/name/namespace/UID and unchanged spec hash excluding only the one
controlled field. Raw templates, conditions, addresses and error bodies are not
stored; projections contain bounded identities, hashes and replicas/suspend.

The [current Kubernetes API contract](https://kubernetes.io/docs/reference/using-api/api-concepts/)
specifies complete-LIST collection RV to exact watch continuity and opaque RVs.
This migration observer refuses HTTP410, ERROR, EOF, invalid frames, deletion,
UID/spec drift, overflow, fsync failure and deadline expiry permanently. It never
relists, reconnects, numerically sorts RVs, adopts previous observations or grants
permission from a caller readiness Boolean. Connect and HTTP readiness use at
most30s or remaining budget; watch reads use only the remaining absolute
at-most2100s whole lease. Bookmarks have no guaranteed interval, so quiet streams
do not face an extra30s idle requirement. Lease expiry is retained failure, never
a refreshed deadline. Remaining socket timeouts are refreshed before every
watch line, each initial LIST chunk and HTTP response readiness, so a valid late
event does not renew the original quiet-read lease. The existing
independent-restore watch is unchanged.

Observer.start opens all three verified HTTP200 streams, starts concurrent owned
readers immediately to retain early events, and fsyncs bounded metadata before
returning. Existing protected journal anchors/lock and a separate exclusive
control-watch.json inode are checked on each save/prerequisite. The borrowed
ControlTrace check verifies actual live readers, owned durable state and exact
GET RV observations under the caller deadline. Watch-lag waiting is bounded3s;
it cannot reinterpret older or missing events. Changed control values require the
same owned journal's pending/confirmed conditional intent; an external stop or
resume is refused. IO and API callbacks never run
while holding the proof lock. Per-event fsync faults are actual fault injections,
not evidence of power-loss survival.

After verified zero-writer capture/full backup/owned holder absence, only the
explicit pending owner-resume operation may authorize migration-releases
true-to-false. HR stays suspended and Deployment stays zero. The active owner
can apply validated all-three-policy legacy withdrawal; the final HR image/resume
belongs to the separate durable forward launcher. Closing or failing the observer
invalidates the borrowed trace, and independent socket/thread closure is required.
Root's mutation transport must check the actual prerequisite immediately before
and after each dispatch; inherited cold primitives do not establish watch
readiness themselves. A failure between a check and API dispatch remains a
non-atomic boundary and must retain uncertainty rather than replay or resume.
The journal remains owned by the outer caller and is closed separately.

TLS fixture acceptance is local transport/durability evidence only. Root must
wire the qualified operator adapter, actual complete source/guard/image/schema
proofs and live cold/forward execution. A returned proof object is informational;
neither it nor a continuously observed zero writer proves full-row preservation,
actual forward migration, principal adoption or final compatible rollback.


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
