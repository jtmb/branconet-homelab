# Longhorn restore-transition metadata library

`scripts/migration/bortus-restore-completion.py` is a pure local library for the
reviewed Longhorn **1.12.1**, `longhorn.io/v1beta2`, v1 data-engine contract. It
does not call Kubernetes, create resources, watch a cluster, persist a journal,
read credentials or data, or authorize deployment. Synthetic tests qualify its
local decisions only. Fresh independent restore, admission, image, consumer and
data qualification remain pending.

## Source and completion meaning

The source scope is longhorn-manager commit
`8320238242e8c804325d9588ec1db10feb9f36b8`. In
[checkAndInitVolumeRestore](https://github.com/longhorn/longhorn-manager/blob/8320238242e8c804325d9588ec1db10feb9f36b8/controller/volume_controller.go#L4881),
the controller initializes both restore flags to true after inspecting the backup.
[checkAndFinishVolumeRestore](https://github.com/longhorn/longhorn-manager/blob/8320238242e8c804325d9588ec1db10feb9f36b8/controller/volume_controller.go#L4935)
sets restoreRequired to false after checking the requested backup against the
running Engine's last-restored backup, purge state, standby and replica/health
conditions. The controller can permit degraded availability under a setting;
the library does not infer healthy two-replica acceptance from this transition.
[VolumeStatus](https://github.com/longhorn/longhorn-manager/blob/8320238242e8c804325d9588ec1db10feb9f36b8/k8s/pkg/apis/longhorn/v1beta2/volume.go)
has bool fields without `omitempty`: zero status can contain false/false before
initialization. Both absent or false/false are non-evidence before true/true.

Eligibility requires an observed **true/true → true/false** pair on the same
owned UID and exact fromBackup. RestoreInitiated stays true. False-only traces,
missing/nonboolean individual flags, flags disappearing after initialization,
regression after completion, deletion, watch errors or gaps refuse eligibility.
Detached or Ready alone never proves completion. This path does not demand
post-reattachment Engine restore history: Longhorn stops/reset its monitors and
replica sync-agent restore history is in memory, so that later history may
legitimately be empty. This library observes the Volume controller transition;
it does not claim independently observed Engine consensus.

## Input and caller obligations

`RestoreExpectation` and `BackupIdentity` are frozen identity records: restore
Volume name/UID/namespace, the exact accepted source URL, source Backup
name/namespace/UID/resourceVersion, original Volume UID/handle, and source size
`1073741824`. Restore name/UID must differ from the original handle/UID.
The source URL must use canonical `cifs://192.168.0.8`, path
`/container_backups/k8s-migration-20261009/longhorn`, and exactly one `backup` and
one `volume` query matching the source identities. There is no userinfo, port,
fragment or ignored blank/duplicate/extra query. Query parsing uses strict
parsing, keeps blank values and caps fields at two. fromBackup must equal these
accepted URL bytes on every Volume event. Backup identity is a caller-recorded
fence, not a fresh Backup API lookup by this library.

Call `evaluate_restore_transition(expected, events,
watch_started_before_create=True, longhorn_version="1.12.1",
api_version="longhorn.io/v1beta2")`. The prerequisite flag is **external evidence
the caller must prove**; it cannot attest its own truth. Before mutation, a future
executor must durably bind actual watch/list resourceVersion, handle readiness,
source/schema identity and bounded continuous capture to the owned journal. It
must refuse overflow, truncation, reconnect without proven continuity, decode
ambiguity and API ERROR/DELETED/gap events. It must enforce transport/decode
size, time and nesting bounds before invoking this library. Ordered events are
not sorted: resourceVersions are bounded opaque identities, not numeric clocks.
Duplicate Volume resourceVersions are refused; BOOKMARKs provide no transition
evidence. The library does not prove that no event was omitted by a caller.

The collector's API semantics are now reviewed against the official current
[Kubernetes v1.37 API concepts](https://kubernetes.io/docs/reference/using-api/api-concepts/#efficient-detection-of-changes),
matching the installed cluster major/minor. A complete most-recent LIST supplies
the collection resourceVersion; item resourceVersions do not replace it. A watch
from that exact nonzero version reports subsequent changes. The restore-specific
design inference is to refuse eligibility permanently after an ERROR/410, EOF,
overflow or unproven reconnect: relisting can establish a new current state but
cannot recover a transient initialization/completion transition already lost.
The executor still has to prove actual TLS-verified HTTP readiness and durable
capture before creation, retain early events until the new claim/PV/Volume UID
chain is confirmed, and bind its final GET identity/resourceVersion to an event
durably observed before sealing. This is source review, not an implemented or
executed collector.

The input ABI is a **closed metadata projection** of watch events in their
original arrival order, preserving all Volume events and their flag absence:

- At most 256 plain dict ADDED/MODIFIED/BOOKMARK events, each with `type` and
  `object`. The object requires apiVersion, kind `Volume` and metadata.
- Volume metadata: name, namespace, uid, resourceVersion; optional
  deletionTimestamp must be null. Spec: fromBackup, encrypted literal true,
  numberOfReplicas integer 2, size string `1073741824`, dataEngine `v1` and
  standby literal false. Other spec/metadata fields must be removed by the
  collector after independent source/ownership validation.
- Status may omit both initial restore flags or be absent initially. Once either
  flag exists, both must be literal booleans. Optional state, robustness and
  isStandby are checked; deleting/faulted/error states and standby refuse.
  Conditions may be absent/null or an array of at most 32 distinct condition
  types with type/status, and optional bounded reason/message/time strings.
  RestoreFailure refuses, including after a completed transition. Conditions
  and their raw messages are never copied into a result or failure.
- BOOKMARK object metadata contains only resourceVersion. A bookmark does not
  replace a missing final Volume witness. Unknown fields/types and oversized
  identities, conditions, strings or event sequences refuse with fixed codes.

This is not a whole-object watch logger. The collector must preserve continuity
and reject duplicate JSON keys before projection; the library cannot recover
ambiguity already lost by JSON decoding. Its limits are ABI limits, not evidence
of network limits. Failures contain a fixed code and bounded event index only;
callers must not log exception tracebacks with input locals or raw payloads.

## Result and remaining gates

The immutable result includes selected expected identities and the initialized,
completed and last observed Volume RVs. It returns
`metadata_transition_eligible=True`, **`data_acceptance=False`**. It returns no
source URL, condition messages, controller errors, addresses or whole events.

Before and after any independent restore read, the future coordinator must
recheck original/source Backup and restore Volume UID/source fences, exact
PVC/PV/Volume mapping, current healthy two RW replicas, sole qualified readonly
consumer, unchanged image/admission/source and resource identities. It must
perform full authenticated independent archives and normalized SQLite row
multiset comparison with the original cold checkpoint. Durable ownership,
uncertain outcomes, teardown and resumable coordinator execution are separate
requirements. This library alone establishes none of those gates and cannot
grant live restore or migration acceptance.

Run the pure synthetic suite with
`python -B -m unittest discover -s scripts/migration/tests -p test_bortus_restore_completion.py -v`.
No native performance fixture, driver, runner, summarizer or acceptance gate is
changed by this library.

The source inspection and repeated cold storage checks also require the complete cluster PV inventory in [BORTUS-PHYSICAL-VOLUME-FENCE.md](BORTUS-PHYSICAL-VOLUME-FENCE.md); any other Longhorn PV using the original handle refuses regardless of claim namespace or inactive state. This closes a scoped inventory gap and does not establish an atomic consumer/admission barrier or restored-data acceptance.
