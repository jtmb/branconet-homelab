# Durable BORTUS restore LIST/watch collector

`scripts/migration/bortus-restore-watch.py` provides a callable library, with no
production CLI. The separate [embedded mTLS adapter](BORTUS-OPERATOR-MTLS.md)
implements the reviewed kubeconfig shape. The coordinator's scoped 06:33 UTC
probe passed the complete live Longhorn LIST and TLS1.3 watch HTTP handshake,
with fresh options for both requests; no frames were consumed and no durable
live restore lease or data acceptance is established by that probe. See the
[operator qualification](../evidence/bortus-operator-mtls-integration-20261011.json).
The collector implements actual TLS-verified HTTP200
LIST/watch readiness and durably binds that prerequisite before guarded create
callbacks. It does not establish image/admission qualification, current source or
consumer fences, restore health, authenticated independent data equality or live
acceptance. No production request is made by importing it.

The dependency snapshot is exact root `689c83486ebb2722d81ff89bc5b67dda089d3d06`.
The original ownership journal remains unchanged. The pure transition evaluator
now uses the installed schema's canonical `Standby` field, as described below.
Use `WatchJournal`, a subclass that serializes the original journal's file/inode
replacement with concurrent sidecar checks. It does not hold that lock during
slow API callbacks; the reader continues draining while a create reply is pending.
The collector refuses a journal with prior operations or a prior watch sidecar.
A reopened durable ready record is never a live ready attestation.

`TLSAPI(approved_origin, options)` accepts one reviewed HTTPS origin and a fresh
options callable returning a verified SSLContext and optional Authorization
header for each request. It requires certificate/hostname verification and TLS1.2+
and rejects redirects, non-200, non-JSON and encoded bodies. It does not consult
proxy environment variables, write credentials, cache auth, log response bodies,
or parse kubeconfig/exec plugins. The separate embedded-only adapter supplies
fresh options; the future executor must qualify actual approved operator access.
Unsupported behavior must refuse.

`Collector.start()` takes a complete most-recent Longhorn Volume LIST (at most 32
pages / 4,096 initial objects / 8 MiB body), preserving the opaque collection RV across
continuations, then opens watch from that exact RV. Actual accepted TLS/HTTP200
and a running owned reader precede a fsynced ready record. A PID, readiness boolean,
BOOKMARK or arbitrary caller-supplied proof cannot replace those checks. This is
the classic LIST/watch path described in the current official
[Kubernetes v1.37 API concepts](https://kubernetes.io/docs/reference/using-api/api-concepts/).
It uses no initial-event/sharded-watch feature and no numerical RV sorting.

The watch has a 2,100 second whole lease and a separate 30 second socket read
timeout. A quiet socket can therefore refuse before the whole lease expires.
Limits are 1 MiB per newline-delimited JSON frame, 8 MiB watch bytes, 4,096 frames,
32 JSON nesting levels, 256 bound target observations and 8 MiB persisted proof. Duplicate JSON
keys, malformed UTF8/JSON, header errors, HTTP410/watchERROR, EOF, deadline, count/
byte overflow, filesystem ownership or fsync failure stickily refuse. There is
no automatic reconnect, relist, adoption or mutation replay. Cancellation closes
and joins only the collector's owned stream/thread; caller-owned transport/server
and unrelated operations remain separate.

All body bytes actually consumed are charged before decoding or projection,
including rejected LIST prefixes (at most one byte beyond the total LIST cap)
and oversized watch frames. Rejected HTTP responses explicitly close both the
owned response and connection. Only scalar byte counts survive rejection, including HTTP truncated-body partial bytes.
A frame returned after the whole deadline is charged and rejected before projection.

Early dynamic-CSI events are drained before the final Volume name is known. The
sidecar retains only bounded identities, source/spec-match booleans, literal
restore flags and fixed status-valid/deletion/restore-failure booleans. ABI 2
checks the installed spec's exact `Standby` spelling and literal false and refuses
lowercase aliases. Its status-valid projection preserves refusal of faulted,
deleting, standby and unsupported state/robustness values; raw status text is not
retained. The original ABI 1 fixtures used an incorrect lowercase spec spelling
and dropped these status checks; their historical receipts do not qualify this
corrected source. Raw condition text,
addresses, source URLs, headers, auth, errors and whole objects never enter it.

The corrected tests cover canonical/missing/aliased/nonboolean spec flags and
status types/enums. Owned real HTTPS streams also reproduce a faulted or standby
event after metadata completion and verify sticky refusal before holder dispatch.
These remain synthetic API fixtures; they do not create a production restore.
The closed metadata schema is checked before each save. The ownership journal's
pinned run/lock protection and separate sidecar inode/hash checks precede atomic
replacement and file/directory fsync. Retained files cannot grant readiness after
process restart; failures preserve prior artifacts for inspection.

`perform_create(action, mutate, validate)` durably binds a prerequisite reference,
uses the original journal's pending intent/save before callback, and rechecks the
actual live lease at dispatch and after reply. StorageClass confirmation precedes
PVC create; a confirmed bound target and sealed transition precede holder create.
`prerequisite()` returns an informational immutable reference; it is not accepted
as authorization input. Callers must use the guarded API rather than bypass it
with a bare journal callback. The callback must separately enforce the reviewed
proposal and fresh source/admission/image fences. TLS/API callback execution for
mutations is supplied by the future executor, not this observer.

`bind_target(claim,pv,volume)` requires the confirmed create UID (with the fresh
claim RV allowed to advance), exact new PVC/PV/Longhorn mapping, supported driver,
Retain, distinct original claim/PV/Volume UIDs/handle and absence from the complete
initial list. Earlier matching-name/UID observations must agree with that exact
source/spec. Lost create replies never authorize adoption of a later matching name.
`seal(fresh_volume)` requires the current GET's exact RV/flags to exist in durable
observations and evaluates the same-UID true/true to true/false trace. It returns only
metadata eligibility with `data_acceptance=False`. Drift/deletion/flag regression
continues to refuse while the lease is running.

A watch and remote mutation cannot be atomic. Failure after authorization or
while a request is in flight refuses acceptance and leaves pending/uncertain
mutation ownership. Even an eligible metadata trace must be followed by fresh
healthy2RW, sole compatible readonly consumer, exact source/image/admission fences,
and complete independently authenticated archive/normalized row equality, checked
before/after streaming. Cleanup needs its separate fresh UID/RV and durable intent.
This library does not supply that remaining coordinator or data acceptance.

The separate pure [restored-consumer fence](BORTUS-RESTORED-CONSUMER-FENCE.md)
checks current mapping, complete physical-PV alias inventory, exact owned running
Engine/two RW Replicas and the sole inert read-only holder. Its metadata result
does not replace this watch's actual same-UID completion provenance. Repeat both
contracts before and after the bounded data read; preserve owned UID continuity
while allowing current resourceVersions to advance.

The local suite uses a freshly generated disposable localhost certificate and
owned loopback HTTPS server, real POSIX files/fsync plus synthetic API callbacks.
It does not contact Kubernetes or read databases/Secrets, launch Node/browser/
containers, install tools or run performance fixtures. Qualification evidence
records actual source/test bytes, first failures, terminal exits and cleanup;
synthetic fault injection is not a power-loss or live restore test.

The disposable HTTPS fixture explicitly sets `context.minimum_version = TLSv1_2`;
its first default-context failure is retained. The policy is not relaxed when
Python reports a MINIMUM_SUPPORTED sentinel. Actual mutual TLS success/missing
client certificate refusal and fresh context security withdrawal are covered.

The separate [restored-data composition](BORTUS-RESTORE-DATA.md) borrows this
Collector and checks its live prerequisite throughout capture, normalization,
comparison and exact cleanup. It never closes the borrowed watcher; the executor
must retain it through separately durable UID/RV holder deletion and close it in
its outer finally. Local composition tests do not establish a production watch.
