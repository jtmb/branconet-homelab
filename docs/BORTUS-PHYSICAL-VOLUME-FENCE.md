# Physical Longhorn PV alias fence

The BORTUS cold checkpoint and read-only checkpoint preflight require a complete
cluster-scoped PersistentVolume inventory. A second PV using
`driver.longhorn.io` with the original Longhorn `volumeHandle` refuses the
operation even when unbound, inactive, failed or deleting, and even when its
claim belongs to another namespace. Only the original PV name and UID may
reference that physical Longhorn volume. A recreated PV, duplicate name/UID,
missing original entry or unsupported original driver also refuses.

The client uses one fixed raw API collection request,
`/api/v1/persistentvolumes?limit=10001`, through the existing kubeconfig transport.
It accepts at most 10,000 items; any continuation or nonzero remaining count
refuses, with no pagination bypass or partial success. This preserves API list
resourceVersion/continuation metadata rather than relying on kubectl's flattened
output. The list must be v1/PersistentVolumeList with a nonempty opaque RV, valid
PV items (omitted embedded TypeMeta is valid; supplied types must be v1/PersistentVolume),
bounded unique names/UIDs/RVs, cluster scope, a spec
object, and valid driver/handle strings on every CSI entry. Other storage drivers
and other Longhorn handles are allowed. This is a scoped identity/CSI check,
not a replacement for API schema validation of unrelated PV fields.

Identity/driver/handle strings are limited to 253 characters and RVs to 256.
The existing client still refuses output above 8 MiB, unsuccessful reads,
invalid JSON, a 20-second API request or a 25-second subprocess timeout. Its
8 MiB check is after subprocess capture and is not a hard allocation or RSS cap.
The summary retains only item count, opaque collection RV and a boolean; it
never saves foreign PV identities, addresses, conditions or whole objects.
Errors use fixed messages with output withheld. The request has no Secret or
database read, mutation, credentials in arguments, or optional bypass.

The preflight `evaluate` input now includes the mandatory tenth collection,
`pvs`; the real client fetches it cluster-wide. The independent restore
preflight inherits this fence through its fresh source inspection. The cold
checkpoint re-fetches it on every `storage()` check. The existing archive helper
calls `cold()` before streaming, after authenticated encrypted verification and
after NAS copy, so alias drift at those checks refuses further progress. Resume
storage checks also refuse a newly observed alias. Claim/PV/Longhorn UID, mapping,
Retain/keep, encryption/two replicas, journal, archive and UID/RV mutation
contracts remain in force.

These reads are not atomic and cannot prevent an alias created after an accepted
inventory. Existing checks and forthcoming coordination/consumer fences must be
repeated at execution; no watch, admission barrier, live absence of aliases,
cold capture, independent restore or performance acceptance is established by
this patch. The separately qualified holder-delete intent remains in the coordinator source;
durable restore-watch execution remains pending. The current namespace-local claim-consumer checks remain necessary; this
fence closes the separate PV physical-handle alias case.

The pure tests cover inactive/deleting aliases, UID/name drift, missing or
malformed lists, continuation/count/byte bounds, exact count boundary, raw
collection request, repeated before/after-stream refusal, and inherited restore
refusal. They use synthetic metadata and callbacks, without Kubernetes, data
reads, encryption processes or runtime containers. See the immutable
qualification evidence for actual execution and source hashes.

The raw request mechanism is documented by the official
[kubectl get reference](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_get/).

Kubernetes v0.34.0 represents the collection as typed `[]PersistentVolume` and
marks embedded TypeMeta fields optional. An absent item kind/apiVersion is thus
compatible with the typed list, while an explicit inconsistent type is refused.
See the versioned [PV/list source](https://github.com/kubernetes/api/blob/v0.34.0/core/v1/types.go)
and [TypeMeta source](https://github.com/kubernetes/apimachinery/blob/v0.34.0/pkg/apis/meta/v1/types.go).
The retained first failing synthetic regression records the over-strict initial
item type check; the corrected suite is a distinct qualification.

The coordinator subsequently integrates this fence with its durable delete intent. [Integration qualification](../evidence/bortus-physical-volume-fence-integration-qualification-20261011.json) binds all 100 passing combined pure BORTUS tests and an unchanged live read-only preflight: 53 complete PV entries, with only the original PV UID using its Longhorn handle. The report is metadata-only; separate reads are not atomic and must be repeated during guarded execution. Initial generic CLI failures are retained; a traced same-source attempt identifies a missing Windows-only output parent. The existing WSL operator runtime resolves that output issue without a validator change. No holder image, cold capture, independent restore or full-data acceptance is established.
