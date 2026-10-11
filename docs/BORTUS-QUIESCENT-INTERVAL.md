# Lease-bound quiescent client

`scripts/migration/bortus-quiescent-interval.py` exports `watch`, `quiescent`
and `cold` once. Build the actual Observer and ControlJournal from its `watch`
export, construct `IntervalClient(observer, deadline=observer.deadline)`, and
construct QuiescentCheckpoint from its `quiescent` export. Inject that same
quiescent module into QuiescentArchive. The existing Ready/cold clients and
default archive callers remain unchanged.

The adapter overrides the inherited GET/mutation transports, including the GETs
used by inherited `inspect()`. Only fixed original storage/control/backup names,
the recorded writer ReplicaSet, owned holder, and complete bounded Pod/PV LISTs
are permitted. There are no Secret endpoints. Every command uses the fixed
operator runtime kubectl and a freshly validated, pinned existing admin.conf FD;
no plaintext credential export or credential argument is created. Bodies travel
through stdin, private stderr is discarded, and stdout is bounded to8MiB.

Each dispatch checks the actual live Observer prerequisite before and after IO.
Named control replies also require unchanged identity/spec and exact agreement
with the latest durably watched opaque RV, with at most3s wait under the same
lease. Quiet streams use the existing observer's absolute expiry. A failure
between the prerequisite check and API dispatch is still a non-atomic boundary.
The adapter cannot make kubectl mutations and watch failure atomic.

Commands receive at most20s or the original remaining absolute lease; stdin,
stdout, process completion and owned closure share that budget. The adapter
creates an owned session and kills only that session on closure, including
descendants holding stdout after their direct parent exited. After absolute
expiry a bounded250ms reap margin is closure only, not additional dispatch time.
It never resets the at-most2100s quiescent interval.

`interval-client.json` is an exclusive protected600 sidecar in the pinned run
directory. Short saves use the ControlJournal lock, check its inode/digest and
file+directory fsync before child creation. No lock spans subprocess IO.
Persistent mutations also require the existing cold journal's exact pending
create/control/delete intent, proposal equality or UID/RV JSON Patch tests.
The complete in-memory journal must equal its pinned durable JSON bytes; an
unsaved pending intent cannot authorize dispatch. The pending identity is checked
again after fresh credential validation immediately before child creation.
Only stopping controls and the explicitly authorized owner-only resume are
permitted. Fresh holder GET must match the deletion intent's current UID/RV;
the original creation RV may legitimately have advanced. The adapter records
pending then transport-confirmed/uncertain metadata, never raw responses or
submitted templates. Core admitted-spec checks and complete holder absence
remain necessary before higher-level acceptance.

The same controlled target transition or owned create/delete cannot dispatch twice,
even with a changed pending RV/proposal after lost reply. Proposal comparison
preserves exact JSON scalar types; false cannot substitute for replicas zero.
Existing sidecars refuse initialization, so reopening, adoption and automatic
replay are unavailable. A failed durable confirmation can leave disk pending;
that remains inspect-only. There is no automatic resume/cleanup mutation.
`close()` closes only the adapter; observer and journal are borrowed and must
be closed independently by their outer owner.

This adapter does not produce phase qualification. Actual source/image/schema,
same-policy guard withdrawal, latest-data preservation, forward execution and
compatible rollback remain separate root-owned producers and acceptance gates.
Controlled local children and TLS observers qualify the transport contract only;
they do not authorize live capture or prove production continuity.


The [root integrated interval-client qualification](../evidence/bortus-quiescent-interval-root-20261011.json) verifies all eight raw native files and52 original artifacts, then passes81 scoped controls without skips in20.074 seconds against current frozen root dependencies. Durable pending intents, bounded IO/owned child closure, observer prerequisites, exact UID/RV controls and no replay are enforced by the new separate adapter; inherited Ready/default clients remain unchanged. Actual local TLS observers and public controlled children qualify composition only. Root observed the supervisor absent and all source hashes unchanged. No live capture/forward entrypoint was dispatched; actual phase-specific image/schema/guard production, CI/Flux dispatch and latest-data/live/rollback acceptance remain open.
