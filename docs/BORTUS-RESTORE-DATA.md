# Independent restored-data composition

The separate [locally qualified callable coordinator](BORTUS-INDEPENDENT-RESTORE.md)
composes source validation, actual watch, durable creates, this
data step and independently observed holder deletion. It retains the separate
actual image/admission/live acceptance requirements.

`scripts/migration/bortus-restore-data.py` is a callable library with no CLI,
API, Kubernetes launcher or holder deletion. It composes the existing live
[Collector](BORTUS-RESTORE-WATCH.md),
[restored-consumer fence](BORTUS-RESTORED-CONSUMER-FENCE.md), pinned encrypted
archive writer, authenticated tmpfs normalizer and complete-row `recovery`
comparator. It does not perform an independent restore or qualify image,
admission, deployment, native Secret behavior or overall live acceptance.

The executor supplies the exact exposed Collector/WatchJournal interfaces, its
trusted closed health expectation, original checkpoint ciphertext and digest,
approved age/recipient/identity paths and three bounded callbacks. Source and
reader callbacks must use the same absolute monotonic deadline, unexpired and
at most 300 seconds away; this library cannot interrupt an arbitrary blocked
Python callback. It passes that one deadline through encryption, both
normalizations and comparison without granting a fresh budget. The outer
executor owns and closes the Collector after any separate UID/RV holder-delete
transaction. This step never closes the borrowed watch or deletes the holder.
The separate [scoped mutation adapter](BORTUS-RESTORE-MUTATIONS.md) supplies the
create/delete transport; submission never replaces admitted-spec or absence proof.

`source_fence(deadline)` must independently revalidate the cold checkpoint's
source/consumer/storage and completed backup fences, returning the immutable
`SourceSnapshot`: checkpoint-journal SHA, original ciphertext SHA and fresh
claim/PV/Volume/Backup identities. This is a trusted executor contract, not a
self-proving authorization boolean. The library binds that result to the
Collector's retained source and health expectation, exact checkpoint digest and
original ciphertext digest. `read_metadata(deadline)` returns the complete raw
bounded collections required by the health evaluator. The first successful
source and target identity tuple pins every name/namespace/UID, including Engine,
two Replicas, holder and alternate node. Later RVs may advance without sorting;
replacement UIDs or names refuse.

The coordinator's [source-fence adapter](BORTUS-OPERATOR-MTLS.md) now supplies
the repeated original checkpoint/source checks through pinned journal descriptors
and fresh scoped TLS reads, reusing the original preflight evaluator. It returns
selected metadata for conversion to this exact SourceSnapshot interface. Initial
target-absence preflight remains mandatory and cannot be bypassed or replaced by
the repeat-source result. Actual runtime/API exec, qualified image and final live
restore acceptance remain coordinator duties.

`launch_reader(holder_identity, deadline)` returns one newly owned `Popen` with
pipe stdin/stdout and suppressed private stderr. The library writes exactly
`bortus-sqlite-archive.NODE_READER`, through a bounded nonblocking pipe, without
an application entrypoint or any values in arguments. The actual executor must
qualify its API exec transport and owned-child contract; if a launcher fails
before returning a handle, that callback must close its own child. Local
callback success does not prove those gates. It captures directly into the exclusive
`restored-sqlite.age` in the pinned mode-0700 run directory, never fabricating an
original Checkpoint or using the original capture wrapper/NAS archive name.
The separate [reader launcher](BORTUS-RESTORE-READER.md) supplies the fixed exec
callback with fresh Pod UID/RV/spec checks and inherited protected kubeconfig FD.
Its GET/exec race requires the existing post-read identity/spec fence.

Before source launch, an exclusive mode-0600 `data.json` pending intent is
file/directory-fsynced under the WatchJournal's pinned owned directory. Any
existing data intent refuses replay, overwrite or adoption. This is a separate
closed ABI-1 sidecar; neither the journal nor ABI-2 watch schema gains fields.
Writers hold the watcher lock only for ownership checks and durable file writes,
not during callbacks, capture, normalization or comparison. The actual live
Collector prerequisite is checked before/after each long step and immediately
before final confirmation. Fresh source/health fences apply before/after capture
and again after comparison and successful cleanup. These reads and watch checks
are not atomic with subsequent operations.

Both exact archives are independently authenticated into separate owned `/dev/shm`
copies. The full recovery comparator preserves all rows and multiplicities,
schema, accounts, aliases and migration state. Both exact tmpfs cleanups are
attempted independently even if the first refuses. Owned source closure is also
attempted independently. Cleanup refusal, watch failure, identity drift,
deadline expiry, ciphertext substitution or durable-write failure cannot return
success. Failed pending/refused records and encrypted partials remain for
inspection; there is no automatic replay. Unexpected foreign tmpfs files or
identities remain for explicit review rather than recursive deletion.

Only selected resource identities, opaque RVs, public code/proposal/checkpoint
bindings, byte counts, cleanup outcomes and fixed failure codes are serialized.
No rows, condition messages, addresses, raw objects, key material, source URLs or
plaintext/ciphertext content digests enter this sidecar. Public fixed refusals are
raised outside internal exception handlers so private callback errors are not
retained in their exception context. A confirmed data result
means this invocation compared the two authenticated archives and cleaned its
exact owned copies under its supplied prerequisites; its overall live restore
and image/runtime/admission acceptance flags remain false. Fresh source/backup
provenance, actual restore execution, release image and admission, data-gate
coordination and separately durable holder deletion remain executor duties.

Local qualification uses disposable age identities, public SQLite fixtures and
actual private tmpfs normalization/cleanup. The real Collector thread and durable
proof/journal run against controlled transport callbacks; no TLS or Kubernetes
connection is made by this suite. A Python fixture accepts exactly the production
Node reader bytes but does not execute Node. Source/API/holder operations are
mocked, while encryption, authentication, complete-row comparison, owned-child
closure and POSIX file/directory fsync faults are real local operations. The
original final-directory-fsync failure is retained: the corrected writer pins its
newly owned replacement before flushing the directory, permitting only a refused
metadata outcome after a flush failure. This is fault injection, not power-loss
or live restore acceptance. Every pending/refused record still refuses replay.
