# Restored consumer metadata fence

`scripts/migration/bortus-restored-consumer-fence.py` is a pure evaluator. It
performs no filesystem, API, database, credential or network operations. The
caller supplies independently trusted original and newly owned PVC/PV/Volume
identities, completed source Backup identity and exact credential-free NAS URL,
holder identity and separately qualified tagless image reference, original node
and owned alternate node. A version string or image reference is a compatibility
constraint, not proof that an image was scanned, preloaded, admitted or run.

The input contains current PVC, PV, Volume, Backup and Node objects and complete
bounded PV, namespace Pod, Longhorn Engine and Replica collections. Collection
API/kind, opaque resourceVersion, no continuation/remaining items, unique names
and UIDs and at most 10,000 items are mandatory. A built-in JSON tree traversal
is bounded to 400,000 nodes, depth 24, 16 MiB of string characters and 65,536
characters per string; custom containers/accessors refuse. This limits already
supplied metadata, not transport bytes. The executor must separately bound and
authenticate the complete API delivery. ResourceVersions are preserved as opaque
identities and are never numerically sorted.

The target identities and names must differ from the retained original source.
The bound claim maps through its exact PV claimRef UID and Longhorn CSI handle to
the restored Volume; a complete cluster PV list must contain exactly that one PV
using the restored handle, including inactive or deleting aliases. The Volume
requires encrypted v1, exact 1 GiB size, two integer replicas, exact capitalized
`spec.Standby=false`, `status.isStandby=false`, the accepted source URL, attached
healthy status and placement on the alternate node. Current restore flags must
be literal true/false. These flags alone do not prove the earlier restore
transition; the independent [durable watch contract](BORTUS-RESTORE-WATCH.md) and
[completion evaluator](BORTUS-RESTORE-COMPLETION.md) remain prerequisites.

Exactly one target Engine and two target Replicas must be active and actually
running, with exact Volume owner UID references, v1, source size and pinned
`docker.io/longhornio/longhorn-engine:v1.12.1` desired/current images. Replicas
require the owned engineName, nonempty healthyAt, empty failedAt and no deletion.
Both Engine address maps must equal the two actual replica-name-keyed
`status.storageIP`/integer port endpoints; `replicaModeMap` must contain exactly
those two names with RW modes. IPv6 uses bracketed host/port formatting. No
addresses, controller condition messages or whole objects enter the result.

The sole active claim consumer must have the exact owned holder UID, be Running
and Ready on the alternate Ready schedulable node, and match the inert proposal:
`node -e setInterval(()=>{},1000)`, pullNever, no service-account token, no
environment or arguments, one read-only claim mount, nonroot runtime defaults,
read-only root filesystem, no capabilities or privilege escalation and bounded
resources. Only explicit benign API defaults are accepted; extra init/sidecar
containers, projected credentials, mounts or writable changes refuse. Actual
container status must be running/ready with no restarts. This metadata comparison
does not prove entrypoint/runtime behavior or admission acceptance.

The same pure `holder_matches(pod, image, claim, node, require_ready=True)`
predicate now supplies the holder checks to the whole-consumer evaluator and
the coordinator's admitted-spec validation. Passing `require_ready=False` checks
the complete inert spec and current identity only, allowing the initial create
reply to be validated before scheduling. Reader/data acceptance always requires
the default true readiness check and the complete consumer/storage fence. A
metadata match cannot substitute for fresh API delivery or qualified images.

Success returns an immutable tuple of selected resource identities, engine and
replica identities and collection RVs, with metadata eligibility true and runtime,
data and atomic-snapshot acceptance false. Failures contain fixed codes only.
The executor must repeat fresh source, consumer and health checks before and after
streaming, compare owned UID chains across observations, and enforce its durable
mutation journal/watch provenance. Separate reads can race. Authenticated
independent encrypted archives, complete database row equality, actual image,
preload, admission and restore execution acceptance remain separate pending gates.

Schema evidence is the retained installed Longhorn CRDs and scoped original-volume
metadata, not a newly restored volume. The retained manager tag reference binds
v1.12.1 to commit `8320238242e8c804325d9588ec1db10feb9f36b8`; dependency development
names do not establish a version mismatch. The pinned
[volume controller](https://github.com/longhorn/longhorn-manager/blob/8320238242e8c804325d9588ec1db10feb9f36b8/controller/volume_controller.go#L4737-L4766)
constructs replica addresses from storageIP and port; its
[health predicate](https://github.com/longhorn/longhorn-manager/blob/8320238242e8c804325d9588ec1db10feb9f36b8/controller/volume_controller.go#L1112-L1128)
checks failedAt, healthyAt, active and deletion. The pinned
[instance-manager GetURL helper](https://github.com/longhorn/longhorn-instance-manager/blob/2b5d65ffe205/pkg/util/util.go#L74-L76)
uses `net.JoinHostPort`. The local qualification exercises synthetic metadata only.
