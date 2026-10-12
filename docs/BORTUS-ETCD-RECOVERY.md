# Fresh etcd/native Secret recovery checkpoint

Current scope: the [fresh raw checkpoint and complete encrypted Secret-registry restore](../evidence/bortus-etcd-actual-recovery-root-20261012.json) are accepted. API plaintext decryption, Longhorn/LUKS restore and full control-plane disaster recovery remain open. Earlier local and failed-run sections below are retained historical evidence.

The separate [isolated API recovery preparation](BORTUS-ETCD-API-PROOF.md) supplies
fixed memory-only bundle framing and an independent AES-CBC/protobuf-to-API oracle.
It grants no live decryption acceptance or changes to this raw checkpoint.
Its separate callable API transport has a new closed recovery journal and fixed
ConfigMap/ephemeral-container/stdin methods; it does not widen this checkpoint's
accepted default transport or adopt its historical journals. Actual API resource
dispatch remains root-owned and unqualified until the documented prerequisites.

Scoped cleanup compares a confirmed API-defaulted create reply with its fresh
owned GET. Known Pod tolerations and container termination-message defaults are
removed only when absent from the expected spec. Fields already present in the
expected spec remain subject to exact equality; altered defaults, unknown
fields, UID replacement and incomplete absence inventories still refuse.
The current public TCP/cache probe retained its initial pre-delete mismatch and
uses a separate explicit owned cleanup receipt, never replaying the failed run.

`backup-etcd.py` replaces the historical unbounded snapshot orchestration. It is
separate from BORTUS SQLite framing. Local fixtures do not qualify a current
production snapshot, API decryption, Longhorn unlock or full disaster rebuild.
Existing historical `evidence/etcd-recovery.json` and configuration receipts stay
unchanged. Successful new runs retain exclusive metadata outside Git.

The callable `checkpoint` takes one caller monotonic absolute `deadline` (at
most 2100 seconds remaining), exact etcd Pod UID/spec-image/status-imageID and an
independently approved immutable restore-image digest, current configuration
archive path/SHA, protected age recipient/identity paths, pinned tool hashes,
transient password provider, existing protected runtime parent and unique12hex
run ID. CLI request fields are explicit; its former unbound password-only input
is intentionally refused. No caller Boolean grants recovery acceptance.

Only fixed operator kubectl and .4 SSH transports run. SSH selects the owned
`~/.ssh/id_ed25519` explicitly with `IdentitiesOnly=yes`, strict host checking
and no forwarded agent. Its inode and protected ancestors are pinned; private
key bytes are never hashed or reported. Public age/kubectl/SSH executables are
bound to immutable inherited descriptors and rechecked before/after dispatch.
An unprivileged fixed wrapper consumes exactly one private credential line.
Sudo receives only that line; snapshot bytes use a different anonymous FIFO
bound to the wrapper PID/start ticks/UID/device/inode. Thus consuming-password
and NOPASSWD paths cannot prefix credentials into the snapshot. A closed bounded
run/count/hash header is validated before any proof directory/file effects.
Credentials and body never enter code/argv/environment/logs. Owned child pipes,
sessions and terminal exits remain bounded by the caller's original deadline.
Configuration and age identities are pinned regular600 files under owned700
parents. The existing operator runtime parent may be owned755 and not writable
by others. Required API encryption config, original PKI and Longhorn key files
must exist in an authenticated archive and equal fresh source files; missing or
changed material refuses. Existing keys are never generated or replaced.

A fresh exclusive0700 root snapshot directory receives one etcdctl snapshot.
Snapshot status binds revision and size; pinned etcd3.7.0 status uses bbolt
transaction size while snapshot save appends a32-byte integrity checksum. The
file must have exactly that trailer/size relation before authentication. expected Secrets are read at that
revision, with complete bounded inventory/duplicate checks and compaction
refusal. A new pinned600 age file receives raw bytes directly. Complete age
authentication compares the exact source bytes privately. Only encrypted bytes
are streamed into an exclusive NAS file with SHA/size/readback and file/dirfsync.

The authenticated cipher is decrypted directly into an exclusive root-only
`/dev/shm` proof snapshot. This volatile plaintext is never an operator export.
The isolated Pod mounts only that authenticated proof snapshot read-only and
uses a separate memory data directory. NetworkPolicy denies both directions;
there is no service-account token or production etcd mount. etcdutl checks the
snapshot integrity; skip-hash-check is forbidden. Every source Secret must use a retained configured AES-CBC key prefix.
Restored complete registry
key/value maps must exactly equal the source snapshot revision in memory.
AES prefix/key names plus original key-file/API correspondence have distinct
scope from actual storage decryption; do not claim full API or Longhorn
restoration merely because raw etcd serves its ciphertext.

Durable intents precede snapshot/output/NAS/proof/resource dispatch. No run is
reopened, adopted or automatically retried. Lost create replies retain unknown
resources for explicit inspection. Confirmed isolation resources alone permit
once-only cleanup: fresh owned UID/RV DeleteOptions then named absence and a
bounded complete typed LIST proving both name and UID absent. Child closure and confirmed resource cleanup are attempted independently. The
isolation policy stays retained whenever Pod creation is uncertain or owned Pod
absence is unconfirmed; cleanup must never remove that unknown Pod's protection.
The full requested spec and literal runtime imageID fence are checked before reads
and before scoped deletion. The volatile proof file may be
unlinked only after owned Pod absence; original snapshots and encrypted artifacts
remain retained. A failure cannot overwrite historical evidence or mark overall
production acceptance. Root must separately verify actual terminal0/current
source/keys/NAS/resource absence and retain the source-bound receipt.

Before any actual execution root must qualify current matching etcd image/cache,
required current config archive and tools, protected credential paths, actual
snapshot/API shapes and isolation admission/network enforcement. Kubernetes
full control-plane disaster restore additionally needs reviewed member/revision
handling; see [official etcd3.7 recovery](https://etcd.io/docs/v3.7/op-guide/recovery/).

Local controls use actual disposable age/SSH fixture keys and controlled Python
children, plus mocked API/etcd replies. They cover complete equality, key/UID
drift, checksum-trailer sizes, isolation/runtime states, lost create/delete
replies, durable pending failures, NAS collisions and deadline cleanup. They do
not run real etcd, API, sudo or SSH; root must separately qualify those actual
transports and the real snapshot before relying on a fresh checkpoint.

The duplex reply collector accepts a stream whose stdin has already been closed
by a completed bounded sender. It must still drain bounded stdout and reap the
owned child; attempting to register that closed stdin was retained as an initial
local failure and receives its own causal control.

Public callable refusals clear all argument/provider references and discard
private internal exception frames, including pre-ledger expiry/shape failures.
Ciphertext tampering is refused by actual age authentication before NAS/restore;
actual POSIX directory-fsync fault controls distinguish pending durability from
a source callback permission.

## Retained local qualification and pending transport binding

The19 focused controls passed locally with real disposable age authentication
and owned Python child closure. Initial closed-stdin failures and the later
FileExistsError test-oracle mismatch are retained. Actual etcd, sudo, SSH, API
and production key files were never used. That historical qualification did not exercise the default transport.
The later transport delta binds the explicit approved SSH identity and separates
credential/body framing; its own retained local-shim results must be reviewed
before live use. Root also needs
a fresh authenticated configuration bundle (required key/PKI paths), protected
600 recipient/identity files, exact current source/cache/tool bindings and
actual isolation/defaulting/restore/absence proof. No current production
checkpoint or full disaster recovery acceptance is claimed.

The existing `keys` mode permits bounded explicit PKI paths, encryption config,
Longhorn key, the four admin/kubelet/controller-manager/scheduler kubeconfigs,
and the four etcd/kube-apiserver/kube-controller-manager/kube-scheduler static
manifests only. It does not discover a complete PKI tree; the producer must bind
its complete reviewed required inventory. Correspondence checks apply per read,
not continuous history. API decryption and LUKS recovery require separate proof.

Final success checks the same absolute lease before and after durable completion.
Every receipt requires the matching actual launcher terminal0: an expiry or
final fsync refusal cannot qualify a visible completed record alone. A best-effort
refused record preserves pending/uncertain identities without automatic replay.

A replaced record inode is pinned immediately before its directory flush. A
flush failure can therefore write a durable refused record through that same
owned inode rather than attempting to adopt an unknown record. If subsequent
failure persistence also fails, the external actual terminal refusal remains
mandatory. The original directory-fsync failure control is retained separately.

The remote wrapper handles owned TERM/HUP cancellation through its cleanup
path and reaps its separately owned sudo session. A causal local descendant
check reproduced the initial missing signal-handler leak; both that failure
and the corrected source/control are retained. Local SSH-process exit alone is
not proof that the privileged descendant closed.

The default transport's owned-child closer gives TERM a bounded 80ms opportunity
for wrapper cleanup, then KILL, inside one total post-expiry 250ms reap margin.
It never renews the operation lease or grants success after expiry. An immediate
post-expiry KILL in the inherited SQLite closer bypassed wrapper finally; its
causal failed control is retained before this explicit transport-only correction.

The privileged key reply has an 8MiB transport ceiling (independent of the
configuration archive's larger bound), and each file read must equal its pinned
size. A malformed privileged JSON reply drops raw bytes/internal error frames
at the same public boundary as malformed kubectl replies. It cannot return a
partial configuration document.

The separate transport qualification passes 38 local controls: 19 existing
raw-etcd orchestration controls plus 19 default-transport/finalization controls.
It uses actual controlled Python shim processes, inherited protected file
handles, OpenSSL fixture certificate loading, disposable age authentication and
POSIX faults. No real SSH, sudo, Kubernetes, etcd or operator credentials were
used. Consuming-password and NOPASSWD shims preserve exact public payload bytes;
all recorded test/checkpoint/sudo-shim PID/start identities are absent after
qualification. Initial directory-flush and separately owned descendant failures
remain retained alongside their corrections. This qualifies source/local
orchestration only; actual remote behavior, snapshot equality, API decryption
and LUKS recovery remain root live prerequisites.


## Root integration qualification

[Root integration](../evidence/bortus-etcd-config-root-integration-20261012.json)
verifies five raw Git inputs,85 retained originals and the complete CRC-valid
handoff ZIP. The38 checkpoint/transport controls plus nine configuration controls
pass under default integrated imports:47/0/noskips in7.992s (8.338s wall), with164
original files unchanged in an exact private POSIX copy. The test child and eight
recorded sudo-shim identities are absent. The original Windows-mounted fixture
run correctly refused unsafe ancestry and remains retained. No ownership check
was weakened. Real SSH/sudo/API/etcd and production credentials remain unexecuted.

Current server-side dry runs on Kubernetes v1.37.1 found that the API omits empty
NetworkPolicy ingress/egress arrays. The separate canonical proposal now omits
those fields and retains both explicit Ingress/Egress policyTypes and the exact
owned-run selector. No generic admission normalization is added: any supplied
nonempty/null/unexpected rule field or selector/policyTypes drift refuses. The
original serialization mismatch and dry-run replies remain retained. Dry-run
CREATE has no resourceVersion and never grants persistent ownership; named
absence and original source identity remain checked separately. Actual CNI
isolation and authenticated etcd restoration remain unqualified by dry run.

The canonical-policy variant passed 41 local controls and one current server-side
dry run with exact admitted/proposed policy specs and named absence. The same
read-only preparation found a separate dispatch blocker: kubectl's collection
JSON is generic v1/List, while the cleanup fence requires typed PodList or
NetworkPolicyList. Fixed native raw LIST endpoints are required before actual
checkpoint dispatch; no generic collection-schema relaxation is authorized by
the canonical proposal change. Current complete raw policy inventory has zero
items; this metadata read does not prove actual CNI isolation.

The scoped follow-up uses only the two fixed native raw LIST endpoints for Pod
and NetworkPolicy in migration-system. The complete typed API/kind/RV,
continuation/item-count/10,000-item bounds and exact name/UID absence checks
remain unchanged; generic CLI v1/List is never reinterpreted. Unknown resource
kinds refuse before dispatch. The original collection-shape blocker remains
historical evidence rather than an accepted inventory.

The combined canonical-policy/typed-list variant passes 44 local controls with
unchanged executable inputs. Its read-only current native collections are typed
complete PodList (six identities) and NetworkPolicyList (zero identities). The
single prior canonical-policy dry run remains unchanged rather than repeated.
These results qualify the two scoped source corrections; actual snapshot,
persistent resource runtime/CNI isolation and authenticated registry equality
remain pending. The original generic CLI collection refusal remains retained.

The etcd NAS streaming consumer now uses the separately qualified closed
`nas_program(e,prefix='etcd')` cipher-only factory from the recovery-config
producer. The shared quiescent NAS program stays unchanged. The etcd
512MiB snapshot/cipher headroom and original lease remain unchanged; the smaller
config copy ceiling is not reused. Base-program, factory-source and derived
writer hashes are saved in the pending NAS intent before dispatch. Confirmation
retains exactly six reply fields (count, ciphertext SHA, fsync/readback and
literal mode/CIFS flags). Operator ciphertext remains pinned0600; remote0755
is accepted only for authenticated ciphertext on the exact pinned CIFS
`/mnt/container-backups` mount. POSIX files remain600-only; writable modes,
non-CIFS755, malformed fields and identity/mount drift refuse. No plaintext key,
config or proof file receives this exception. Mount checks give correspondence
at observation points, not continuous mount history. Local qualification and
root actual publication remain separate; prior failed exclusive outputs are
retained and never adopted/reopened/replayed.

The streaming/factory composition passed 51 local controls (the prior 44 plus
seven CIFS-mode/closed-reply cases) with unchanged executable/factory bytes.
Actual public age encryption/authentication and redirected owned NAS-program
children were used; CIFS mount identity and forced file modes are controlled
fixture substitutions, not an actual CIFS transport qualification. Recorded
owned process identities are absent. Root retains actual NAS/config execution
ownership; no etcd snapshot or live restore was performed by this qualification.

One new encrypted PUBLIC NAS fixture retained a strict e210 writer refusal at
creator-close/reopen: mtime and ctime each advanced 3,717,800ns while device,
inode, UID, mode0755, link count1, size243, FD/path correspondence and full
mount identity stayed equal. The original failed writer/probes remain retained.
The scoped factory correction permits only that timestamp boundary on the exact
CIFS `/mnt/container-backups` mount. Device/inode/UID/mode/link-count/size must
remain equal; POSIX requires the full timestamp fingerprint across close.
Immediate reopened FD/path/mount correspondence establishes a full fingerprint
including timestamps. Each readback chunk and final check must keep it stable;
complete ciphertext SHA/count remain mandatory. No lease, ceiling, six-field
reply, source-key/plaintext-proof or shared quiescent-program behavior changes.
A close-boundary observation does not authorize arbitrary later timestamp or
mount drift, nor does it prove continuous history or actual recovery acceptance.

The boundary correction passed 75 combined local controls: 51 existing etcd /
transport controls plus 24 config-factory controls (14 original and ten causal
boundary cases). Public age ciphers and owned local redirected writer processes
were used; CIFS mount identity and the observed timestamp pattern are controlled
fixture substitutions. The exact prior writer fixture is pinned to its actual
1b65 source hash and still refuses. Shared quiescent code and etcd source /
transport / size / deadline contracts stay unchanged. Actual NAS requalification
and current configuration/etcd recovery belong to root; fixture success does not
grant live acceptance or authorize old-run replay.

Root independently ran the integrated streaming consumer and corrected factory: all75 controls pass, no skips or resource warnings, actual launcher0 in17.958s. All165 frozen source files remain unchanged and the owned test child is reaped. The [root receipt](../evidence/bortus-cifs-close-root-20261012.json) distinguishes this local qualification from a fresh actual configuration capture and etcd restore, which remain pending. The two refused actual archives and original PUBLIC fixture failures remain retained and cannot be adopted or replayed.

The [fresh actual configuration receipt](../evidence/bortus-kubernetes-config-actual-20261012.json) records run62333f4abb52, launcher0 in3.399s, all32 files read twice with exact private-byte equality and authenticated age plaintext equality. The83615-byte ciphertext SHA is `f939cc28e3e79878ea3164cd5bc823cb0ce8cba988fd9a6ef6d78caabf3eb6b7`; operator mode600 and actual CIFS NAS mode755 are independently checked with full SHA/size readback. All five transport children exited0, were reaped and are absent; transport is closed and source identities unchanged. All journal operations are confirmed. This accepts only current configuration capture/publication, not continuous configuration history, etcd recovery, API decryption, Longhorn restore or full disaster recovery. Both prior refused run outputs remain retained without replay/adoption.

The [root isolation/default-spec receipt](../evidence/bortus-current-isolation-root-20261012.json) verifies4 raw source files and28 retained originals. All77 integrated controls pass with unchanged165 source inputs, no skips/resource warnings and actual launcher0. The first source freeze incorrectly counted regenerated disposable TLS fixtures; that failure and a later preparation type error remain retained. The current disposable probe verifies fresh TCP reachability both directions before deny, fresh refusal both directions after deny, positive loopback listeners, Calico3/3Ready and exact etcd digest/PullNever version-only exit0. Its initial cleanup mismatch retains terminal1; a separate explicit once-only owned cleanup exits0, proves all3 Pods and policy absent, and removes policy after target absence. All449 recorded exec children are reaped/absent. The explicit cleanup code was retained in its tool invocation rather than independently saved before dispatch; durable identities/proposals/source/records remain hash-bound. These are sampled enforcement/cache and cleanup proofs, not continuous isolation or a production snapshot/restore.

The [fresh actual etcd checkpoint receipt](../evidence/bortus-etcd-actual-recovery-root-20261012.json) records runf9b0b76c5880, actual launcher0 in20.824s and snapshot revision1604085. Its37,613,600 raw bytes authenticate exactly through age;37,622,980 ciphertext bytes have matching operator/NAS SHA and complete readback. Operator archive and retained original root snapshot are600 under protected700 parents; NAS755 is ciphertext only on the verified CIFS mount. The isolated exact-digest etcd restore serves a complete encrypted Secret-registry map equal to the snapshot revision. Fresh source/config/Longhorn key correspondence is checked before/after, without generating/replacing keys. Both scoped resources have UID/RV deletion plus named404/complete typed absence; independent root rechecks confirm absence and the volatile proof snapshot is physically absent. All50 owned children are reaped/absent; the streaming restored server is intentionally terminated before owned Pod deletion (its child exit-15 is recorded, other exits0). This accepts only the authenticated raw checkpoint and complete encrypted-registry restore. Kubernetes API decryption, Longhorn restore, full control-plane disaster recovery, latest SQLite/PVC data and final application rollout remain separate open gates. Gluster/Vault/Consul and original snapshots stay retained.

Independent source/receipt review confirms terminal.result equals the exact durable journal, all9 operations confirmed and complete `/registry/secrets/` ciphertext-map equality, not all registry resources. The original launcher wrote terminal.json without exclusive creation or fsync; that historical file stays unchanged. Root retains8 separately exclusive600 metadata files in a new700 owner, with full byte/hash verification and file/parent-directory fsync. This durable assessment binds the actual external launcher0 and original journal/terminal/source/inspection receipts without re-running or adopting the checkpoint.

## 2026-10-12: root integrated API transport and TLS readiness qualified locally

The [root qualification](../evidence/bortus-api-transport-readiness-root-20261012.json) verifies eleven native raw blobs/modes and 564 retained artifacts, then integrates the separate recovery journal/transport and fixed readiness operation. All 14 root Python transport controls and 15 actual pinned Node22 TLS controls pass, with 176 inputs unchanged and a fresh successful query proving the owned Node container absent. The first root supervisor refused during a transport run; unchanged inputs and observed child closure are retained, but its exact supervisory predicate is unproven. Successful tool output is retained by the execution tools; receipt fields are explicit transcriptions rather than claims of original stdout files.

The default checkpoint transport and CJS oracle remain unchanged. The new API journal/adapter requires actual external source/material/cache/CNI receipt authority and original absolute deadlines. Verified TLS readiness precedes the once-only oracle; pending/uncertain mutations cannot replay or adopt. These public/shim/TLS controls grant no cached-binary, live API decryption, Longhorn or complete recovery acceptance. No live resource or credential delivery occurred.
