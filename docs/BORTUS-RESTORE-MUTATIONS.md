# Scoped independent restore mutation transport

`scripts/migration/bortus-restore-mutations.py` exports `data`, `metadata` and
`MutationAPI(collector, options, proposals)`. Construct the Collector through this
exact `data.watch` interface. The constructor requires its actual live owned lease,
an empty durable journal, and the three closed reviewed proposals with the exact
journal-bound canonical JSON SHA. It reconstructs the encrypted v1 1Gi two-replica
StorageClass, retained PVC and inert read-only holder; additional fields, writable
mounts, namespace changes and boolean/integer substitutions refuse. The source URL
must match the Collector's exact credential-free NAS backup and original handle.
The separately reviewed image and alternate node remain coordinator prerequisites.

Use `collector.perform_create(action, callback, admitted_spec_validator)` with
`callback(intent) = api.create(action, intent, deadline=absolute_deadline)`. Only
StorageClass, PVC and holder POST endpoints are available. Before transport, the
adapter checks the actual running Collector, its durable authorization, and the
exact file/inode-bound pending journal intent. It marks that action dispatched in
memory before requesting fresh TLS options. A failed or ambiguous attempt never
retries, reopens, adopts a resource or overwrites a prior action. The journal
retains pending/uncertain ownership. Locks cover short ownership checks only;
the watch reader continues draining while TLS I/O is in progress.

Every HTTP request uses fresh verified TLS1.2+ options, hostname/CA verification
and the fixed approved origin. Only an optional Authorization header is accepted;
there are no credential caches, proxies, redirects, fallback or Secret endpoints.
The one absolute monotonic deadline is at most 300 seconds away. Socket timeouts
are refreshed from it with a 30-second per-read ceiling, including after connect
and before dispatch. Request JSON is at most 64KiB; complete identity-encoded JSON
responses are bounded to the read-only adapter's 8MiB cap and closed JSON limits.
Both owned response and connection closures are attempted independently.

POST requires HTTP201 and exact API/kind/name/namespace, UID/RV and owned run label.
Only the selected identity and run label are returned; status, annotations, source
URLs and raw errors are dropped. This projection does not prove the admitted spec.
The coordinator must make a fresh full-resource GET and enforce the reviewed spec,
source, image/admission and ownership fences before journal confirmation.

`api.delete(intent, deadline=absolute_deadline)` is only a callback for the existing
durable `holder_delete` transaction. It performs a fresh fixed Pod GET and requires
the exact current owned UID/RV from the pending preconditions, no deletion and the
owned run label. Only then does it send exact v1 DeleteOptions with those UID/RV
preconditions. HTTP200/202 must identify the matching Pod or a successful Status
with matching name/UID and core `pods` details. The result is `submitted=True`,
`deletion_observed=False`. The coordinator must subsequently observe that owned UID
absent before deletion acceptance; submission alone never establishes cleanup.
The core `pods` Status-details spelling follows the exact
[Kubernetes v1.37.1 generic store implementation](https://github.com/kubernetes/kubernetes/blob/v1.37.1/staging/src/k8s.io/apiserver/pkg/registry/generic/registry/store.go#L1371-L1378),
which uses the resource name in that field.

The actual live watch prerequisite is rechecked around transport. Watch/API
operations cannot be atomic: failure while a request is in flight can leave a
created or terminating object with unresolved ownership, which refuses replay.
This callable library has no CLI and importing it makes no API request. It does
not supply the full executor or establish restored-data, image, admission, runtime
or live acceptance. The coordinator owns the borrowed Collector's final closure.

Qualification uses disposable loopback HTTPS credentials, actual protected POSIX
journals and a real Collector thread with controlled watch callbacks. API requests
contact only the owned local fixture. No operator credentials, Kubernetes, Node,
Docker, SSH, application startup or data capture are involved. Synthetic callbacks
and fault injections cannot qualify a live restore or power-loss durability.

The coordinator verified the immutable native handoff `454d6c72`, all eight raw
Git blobs and modes, and 106 retained artifacts. Five new files were integrated;
the three existing documentation changes were merged into current root docs.
The import-only parent was excluded. Root's newer fixed metadata endpoint scope
and extracted source validator were qualified with the adapter: all 398 combined
local cases passed, without skips, on frozen source inputs. This includes 32
mutation transport cases. See the
[root integration receipt](../evidence/bortus-restore-mutations-integration-20261011.json).
Actual exec, source/image/admission checks, complete restore coordination and
live recovery remain open.
