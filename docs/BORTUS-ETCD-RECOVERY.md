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

## 2026-10-13: corrected recovery helper controls and bounded identity evidence

The [root local-controls receipt](../evidence/bortus-sync-fence-recovery-controls-root-20261013.json) preserves the original public27 exit1 and absent final count; its whole-run refusal cause remains unproved. The separate one-case diagnostic identifies only the fixture method shadowing by a Path. The corrected fixture renames that accessor, fixes the closed-stdin age-exit assertion, and adds two once-only replay refusals; material production remains unchanged.

Nine identity-publication controls pass, covering boundary counts, exclusive publication, partial writes, changed input/hash and manifest collision. The separate corrected29-case suite exits0 with zero errors/failures in43.260s. After actual child shutdown/reaping/absence checks, it publishes1172 observed identities across five hash-bound shards; root reads every shard and freshly confirms1173 identities including the supervisor absent and207 source files unchanged. Only this fixture's evidence capacity increases512→4096; operation, output and90-second/closure limits stay unchanged. Root verifies240 archived originals plus21 pure-control and21 diagnostic originals by bytes/hashes/CRC. The first partial copy refusal is preserved; its unrecorded Windows stat difference has unknown cause, and Windows stat is not Linux metadata authority.

These controls prove real local FD/child/pin and publication behavior using modeled age output and API/TCP replies. They establish neither actual age cryptography nor live network denial, accepted private-material delivery or Kubernetes API plaintext recovery. Actual public TCP isolation is the next independent gate, before private recovery parts. Final image/security, latest backups, guarded rollout and full recovery remain open; Gluster/Vault/Consul originals remain retained.

## 2026-10-13: fresh read-only utility cache attestation

The [root current-cache receipt](../evidence/bortus-current-utility-cache-root-20261013.json) completes a new once-only inspection with actual caller/outer exit0 in25.012s. The literal c29 utility digest reference already exists, with exact linux/amd64 manifest/config hashes, five source labels and16 ordered layer descriptors/content names. Exactly four read-only CTR jobs exit0 and are reaped; no alias, import, pull, export or image/server operation occurs. Layer bodies are not rehashed. Root verifies17 source/authority files unchanged after execution, independently confirms eight remote and four local process identities absent, and verifies87 archived originals plus85 current-original byte matches. The credential used only the qualified private stdin/controlling TTY route; foreground identity and disabled echo were independently checked before input. No credential file, argv value or input log is created.

The four-source default scan retains literal exit1/one generic-api-key finding. Root binds that finding to the exact public inspector source checksum without suppressing, altering or replaying the scan. This accepts sampled current utility-cache metadata and closure only. It proves neither continuous cache residency, layer-body integrity, original API-server recovery, live network enforcement nor private-material delivery. Actual bidirectional TCP denial remains required before nine private recovery parts. Original Gluster/Vault/Consul data and accepted backups stay retained.

### Public TCP attempt refused; independent failure inspection (2026-10-13)

The [root failure receipt](../evidence/bortus-public-tcp-refusal-root-20261013.json) preserves both attempts. The first attempt stopped before operation setup; a separate filesystem witness found a missing external path. Its original caught exception remains unknown. Root verifies all229 immutable originals. Corrected external paths pass a six-file protected preflight before a fresh200-file stage and second attempt.

The fresh e983 attempt exits1 after14.411 seconds. Both public utility Pods are confirmed; policy creation remains pending with its observed UID. No accepted TCP result or cleanup follows. An independent30-second read-only post exits0: all200 source bytes are unchanged, all198 observed and197 registered jobs (199 unique identities including supervisor) are freshly absent, and five queries confirm the three exact-owned resources remain present with full matching specs. Root separately confirms the post reader and its five jobs absent.

The current typed NetworkPolicyList item omits apiVersion/kind. Its unchanged strict matcher refuses the item; a copy adding only the missing envelope-derived headers passes the full matcher. This identifies a current semantic defect consistent with the last durable boundary, without claiming a recorded historical exception. Cleanup must use exact UID/current resourceVersion preconditions, remove both Pods before their policy and verify complete typed absence. Cleanup is pending at this checkpoint.

Default corrected-source scanning retains literal exit1 and two public checksum-constant findings, with no suppression or overall scan pass. Performance observer V3 and its14-control preparation remain unrun after source review identifies explicit connection-attribution and late-publication gaps. No benchmark replay, limit change, private material, source adoption or original data retirement follows. A07/A21, final image/security, fresh recovery and guarded rollout remain open.

### Exact-owned public utility cleanup completed (2026-10-13)

Separate cleanup787848d38638 exits0 in1.980 seconds under its original30-second deadline, with an early recorded child gate and the same inherited deadline. Fresh full specs and fixed UIDs precede each once-only DELETE with current resourceVersion preconditions. Both utility Pods are verified absent before withdrawing their policy. All three actions and the five final read-only checks pass. Root freshly verifies the recorded supervisor, child and24 CLI jobs absent; original refused ledgers remain byte-identical. The two selected cleanup sources pass default scanning with zero findings and fresh scanner absence. This root outer is not claimed as a generally qualified failure-closure controller.

A separate five-query read-only observer exits0 and independently confirms all three names/UIDs absent from complete typed collections, all200 source files unchanged, and its reader/five jobs freshly absent. The original TCP actor remains exit1 and its gate remains open. No private material, benchmark replay, live app adoption or original data retirement follows. The [root receipt](../evidence/bortus-public-tcp-refusal-root-20261013.json) includes both failure and cleanup scopes.


### TCP acknowledgement and interrupted proof — 2026-10-13

The [root acknowledgement review](../evidence/bortus-tcp-delete-ack-root-20261013.json) preserves dda81 actor outer/caller1 separately from readonly0, guarded cleanup0 and typed absence0. The original target DELETE was not repeated; peer/policy used fresh UID/RV preconditions. The281 immutable originals distinguish executed Linux bytes from Windows CRLF copies and preserve the earlier packaging refusal.

Kubernetes [Pod storage](https://github.com/kubernetes/kubernetes/blob/v1.37.1/pkg/registry/core/pod/storage/storage.go#L72-L83) permits a returned Pod on deletion. Twelve pure acknowledgement controls pass: exact original Status or Pod-role v1/Pod/full original spec/name/namespace/UID/valid RV, with only a bounded deletion timestamp removed on a copy. Body, grace, deadline, wait, typed absence and confirmation remain unchanged. Historical reply/exception is unretained.

The new6de44 actor remains failed: outer1/caller-15, no caller terminal or registered-job terminal evidence, all three creates confirmed and no deletion intent. The incomplete `source_unchanged:false` flag does not prove drift: root freshly verifies200 staged files unchanged and281 recorded births absent. An uncaught `/proc` ProcessLookupError is a possible source boundary, not a proven exception. Five readonly full-spec/UID checks precede three separate guarded deletions;26 cleanup births and six independent reader births are freshly absent. Named and complete typed lists confirm all three owned identities gone. No success-only reader replay, public TCP acceptance, private holder authority/private recovery execution or original-data retirement follows. Supervisor qualification, final image/security/latest backups/guarded rollout remain open.

## 2026-10-14: private attempt fails before prompt; five resources independently removed

The [9df outcome receipt](../evidence/bortus-private-recovery-9df-outcome-root-20261014.json) preserves tool/outer/caller exit1 and stage6 ValueError before same-holder proof or password prompt. Both control creates are confirmed, but the retained wrapper does not identify the failing inner predicate. The sole registered -15 row is not a proved cause. No password or backup material was supplied. A separate cleanup exits zero after five UID/current-resourceVersion guarded, once-only deletes, with all three Pods absent before ConfigMap/policy deletion. A distinct observer exits zero after eight GETs, all five names/UIDs absent and1748 union host births absent; its own/eight query births are later absent. Six unrelated Pods and one ConfigMap remain. All247 source files are current. Default source scanning literally exits1 with four findings: three public source hashes and an invalid AAAA PEM fixture; each is reviewed without exclusions or scanner replay. Sixteen new input directories were restricted after their own byte/UID checks; original source permissions are unchanged. This proves cleanup, not private recovery, and authorizes no production/data retirement.

## 2026-10-14: public snapshot diagnostic identifies a failed guard and closes

The [b85 diagnostic receipt](../evidence/bortus-stage6-b85-diagnostic-root-20261014.json) preserves stage6/ValueError/exit1. Nine local recorder controls pass; the live trace captures the original need(ids==expected) at same-live-holder-gates.py253 as its first failed predicate,1369 events/23529 bytes within4096/64KiB. It does not retain the differing kind/field, nor prove the earlier9df cause. The first observed exception is separately labelled and is not a proved cause. Gate, graph, fullspec, UID/RV and sample rules remain unchanged; the caller physically ends before private prompting/material/restore. Independent pre-cleanup0 verifies current246 sources and public observations. Separate cleanup0 removes all five confirmed resources with UID/current-RV guards and typed Pod absence before ConfigMap/policy deletion. Independent eight-GET post0 verifies all names/UIDs absent,168 cleanup jobs and1243 union host births absent; nine reader/query births are later absent. No private or production recovery is accepted, and no original data is retired.

## 2026-10-14: snapshot equality recorder controls pass

[Five local projection controls](../evidence/bortus-snapshot-projection-controls-root-20261014.json) pass for the failure-only twelve-bit kind/identity-field equality recorder, including malformed-input refusal and the exact original snapshot guard context. Five source files remain current; original supervisor/suite coordinates are freshly absent. The six-source default scan exits0 without findings. These controls make no transport/API call, replace no guard, and do not identify the historical differing field or prove live/private recovery. A fresh public diagnostic remains separately held.

## 2026-10-14: snapshot diagnostic identifies Pod version drift; cleanup verified

The [6c public diagnostic receipt](../evidence/bortus-snapshot-6c-outcome-root-20261014.json) retains actor/caller1 at the original snapshot guard253. Its1147-event/19533-byte trace records twelve equality bits: only Pod resourceVersion differs; all name/namespace/UID fields and all ConfigMap/policy fields match. ExpectedPodRV is the first gate snapshot before later public setup, not the creation-journal RV. No writer/raw status delta or historicalb85/9df cause is proved. The guard is unchanged and no private branch is reachable.936 historical job rows include index883 exit-15; no role or all-zero claim is invented. Independent post0 verifies current246 sources and937 current-absent coordinates. Separate UID/current-RV cleanup0 removes the five confirmed resources once. Independent eight-GET post0 verifies all names/UIDs absent,172 cleanup jobs and1110 union coordinates absent; nine later reader/query coordinates are absent. A source-only candidate proposes one explicit public-staging checkpoint before real TCP proof, with strict version checks afterward; no live guard change or private acceptance follows.

## 2026-10-14: public checkpoint local controls pass

The [checkpoint controls receipt](../evidence/bortus-public-checkpoint-controls-root-20261014.json) records13 passing tests: nine actual-function controls and four unchanged API-transition regressions. It exercises one exclusive durable checkpoint after public setup, immutable creation journals, full-spec/runtime/source/metadata checks, fixed ConfigMap/policy versions, duplicate failure latching, postcommit identity/version refusal, private-before-proof refusal and the original network/API-transition oracles through scripted public I/O.188 current control sources and supervisor/suite absence are verified. Default scan literal1/one private-key finding is the exact unchanged malformedAAAA rejection fixture; unresolved0 with no suppression/exclusion/replay. A staging finalizer syntax refusal occurred before controls and was corrected in a separate metadata helper. These local controls do not instantiate live transport or prove live/private recovery; a separate public-only candidate packet is in source preparation.

## 2026-10-14: one public-only checkpoint qualification dispatched

The [843 dispatch receipt](../evidence/bortus-public-843-dispatch-root-20261014.json) records one actual600-second/no-TTY/no-input public diagnostic with the13-control-qualified checkpoint gate. The new246-source package preserves242 runtime rows and the183-row graph used by those controls; four necessary gate/composition/caller/outer sources change. Root verifies the closed255-row/256-member packet, exact actual-control receipts/current boot and exclusive247-file stage. Default scan literal1/four findings is independently classified as three unchanged public dependency hashes and the unchanged malformedAAAA fixture; unresolved0 without suppression or replay. The actor physically stops after public proof and cannot prompt/project/deliver private material. Actual completion and subsequent observed-UID cleanup remain pending; no proof, recovery, production guard/image or original-data retirement is accepted.

## 2026-10-14: public checkpoint diagnostic hits tracer bound; all five resources removed

The [843 outcome receipt](../evidence/bortus-public-843-outcome-root-20261014.json) preserves actor/caller1 after232seconds under the unchanged600-second lease. A1977-byte checkpoint is present with proved:false; no complete public proof/scoped result exists. The optional tracer reaches65524bytes/3701 valid events and refuses its next event at the original65536-byte ceiling; no closed summary/firstfalse is saved. Six partial TCP returns are retained (five positive/one blocked), not the complete seven-check proof. Caller finalizers2/5 and2356 jobs/ten shards are preserved without an all-zero claim. Independent eight-GET post0 verifies current246 sources and2357 current-absent coordinates. Separate cleanup0 uses the actual five UIDs/current versions, removes three Pods before ConfigMap/policy and uses no force/grace override/repeated DELETE. Independent eight-GET cleanup post0 verifies all five names/UIDs absent,172 cleanup jobs and2530 union coordinates absent; both pre/post later reader/query groups of nine are absent. The source default scan retains four exact previously reviewed public findings; the three cleanup sources scan0 without findings. No live/private recovery, production guard/image change or original-data retirement is accepted. A distinct source-only functional qualification will omit optional numeric tracing while retaining the same checkpoint gate, full source/CNI/spec/version guards, actual network oracles and600-second limits. The original diagnostic and its64KiB/4096-event bounds remain unchanged.

## 2026-10-14: failed diagnostic checkpoint metadata corresponds to immutable journals

The [843 receipt](../evidence/bortus-public-843-outcome-root-20261014.json) now includes a separate outcome-honest metadata reader0. It verifies current246 source rows and the retained unproved checkpoint against original creation identities/versions, creation-fixed ConfigMap/policy versions, proposal digests, source bindings, original raw journal SHA and two control journals/recorded observer identities. The literal actor1 and complete-public-proof:false remain unchanged. The reader makes zero API calls/children; its source passes the default scan without findings and its own birth is freshly absent. Its IP evidence is the canonical recorded IPv4 plus pinned gate sampling semantics; original GET bodies did not retain a second independent IP observation. Metadata correspondence does not establish live CNI enforcement or private-material authority. All five temporary resources remain independently confirmed absent.

## 2026-10-14: public functional checkpoint fails; exact cleanup verified

The [145 outcome receipt](../evidence/bortus-public-145-outcome-root-20261014.json) retains the uninstrumented public actor1 after112.88seconds under its original600-second lease. The checkpoint remains unproved; the exact refusing predicate is unknown. There is no complete public proof or private continuation, and no guard or network oracle was weakened. Before-cleanup observer0 confirms current246 sources and1561 absent coordinates. Exact-UID cleanup0 removes the three Pods before ConfigMap/policy, with184 complete cleanup jobs. The first cleanup observer1 stops before API queries because it expects the old numeric-diagnostic mode. A distinct observer corrects only that literal and its two exclusive coordinates; all helpers and original30-second/eight-GET bounds remain unchanged. Corrected observer0 confirms all five names/UIDs absent,1746 union coordinates absent and current246 runtime/two cleanup sources; a later check confirms its own birth and eight query births absent. The failed observer and original actor remain recorded. Production, private recovery, originals and backups are unchanged. Failure-only bounded context collection and new-ELF ABI checks remain separate work.

## 2026-10-14: bounded context identifies the current public guard failure

The [c7 outcome receipt](../evidence/bortus-public-c7-outcome-root-20261014.json) retains public actor1 after116.42seconds under the unchanged600-second budget, with an unproved checkpoint and no private continuation. The tested failure-only recorder writes687bytes within its4KiB bound and records the actual exception chain: gate snapshot line274 is called by the pre-exec fence of the cross-control connector list. Only the holder Pod resourceVersion differs; the other eleven identity fields match. This does not identify the list iteration, writer/status delta or causes of earlier attempts. No guard, oracle or checkpoint refresh was introduced. Independent pre-cleanup observer0 verifies current246 sources/1621 absent coordinates and the bounded context. Exact-UID cleanup0 removes all five resources using183 complete cleanup jobs; independent eight-GET post0 verifies all five names/UIDs absent,1805 union coordinates absent and current246/two cleanup sources. Both later reader/query groups of nine are absent. Source scan retains the same four exact public findings with unresolved0; cleanup three-source scan0 has no findings. Production and original data are unchanged; private recovery remains unproved.

## 2026-10-14: finite resource-accounting controls pass locally

The [pure validator controls](../evidence/bortus-resource-accounting-controls-root-20261014.json) pass eight focused groups using the actual pinned public Pod producer. Independent checks verify the six current inputs, actual eight-test/no-skip/reaped result and both original process births absent; a later check confirms the reader absent. The candidate checks exact finite resource quantities, unchanged identity/spec/non-accounting status and restricted managedFields structure, rejecting unsupported maps, callbacks, malformed quantities and unrelated changes. Its possible 130m/150m CPU reports are a source-derived finite model, not observed values or proof of the failed 804 diagnostic cause. Every candidate result explicitly requires the original final security/source/runtime fences and grants no private authority. The original strict resourceVersion gate and 27 test oracles remain unchanged; no live calls, gate integration, checkpoint replacement, replay of those oracles or recovery acceptance occurs. The default source scan retains two public c9b562 source-hash references with zero unresolved findings and no suppression or replay; the one-file independent-reader scan passes. Observation-only collection of actual accounting and managedFields structure remains separate.

## 2026-10-14: accounting observations qualify without changing the recovery guard

The [observation-only controls](../evidence/bortus-accounting-observation-controls-root-20261014.json) pass all eighteen selected cases: fourteen unchanged helper/writer methods and four new actual checkpoint/failed-frame cases. Independent checks verify the 195 current inputs, literal no-skip/reaped result and original births absent; the reader is subsequently confirmed absent. The helper can project six bounded rational resource rows and thirteen managedFields structural path classes from the immutable baseline and already-failed frame. It returns no raw strings, field names, writer identities or private values and makes no extra API or guard calls. The single failure receipt remains capped at 4KiB. The exact strict57d0 resourceVersion gate, original setup/deadline/network/security checks and checkpoint remain unchanged; nineteen prior gate/baseline methods are preserved and not replayed. No transition acceptance, live recovery or production change follows. The 204-file default scan retains the exact unchanged malformed AAAA fixture with zero unresolved findings and no suppression/replay; the independent-reader source passes its combined scan. The subsequent precheckpoint readiness qualification is documented below; this observation-only result grants no readiness authority.

## 2026-10-14: Public accounting-observation diagnostic dispatched

The [855 dispatch](../evidence/bortus-public-855-dispatch-root-20261014.json) starts one public-only diagnostic after eighteen qualified observation controls and independent closure. Closed source review verifies 258 packet rows, 246 runtime sources, 244 unchanged rows and the exact strict57d0 gate; the original 600-second budget, seven real TCP oracles, one immutable checkpoint and physical stop before private material remain unchanged. The bounded helper adds actual numeric accounting and managedFields path observations only. No readiness condition or RV-transition acceptance is introduced. The source scan retains four byte-identical previously classified 804 fixture/public hashes with zero unresolved and no suppression/replay. Actual outcome and exact-UID cleanup verification are pending; temporary diagnostic resources are not yet claimed absent. Original data and production image are unchanged.

## 2026-10-14: 855 failed outcome and verified cleanup

The [855 outcome and cleanup](../evidence/bortus-public-855-outcome-cleanup-root-20261014.json) retain the failed public diagnostic as exit1. Its failed-frame sample observes Pod requested CPU150m→130m while allocated CPU150m, memory and limits remain unchanged; only the managedFields timestamp class changes. This is an observation, not authenticated writer evidence, a cause claim for804, or permission to accept an RV change. Exact-UID cleanup succeeds, the independent eight-GET observer confirms all five names and UIDs absent, and a later no-child check verifies246 original sources, two cleanup sources and nine observer/query births absent. Its own reader is subsequently confirmed absent. The actor’s incomplete registry is retained honestly; private recovery remains unproved.

## 2026-10-14: precheckpoint readiness qualifies locally

The [precheckpoint readiness controls](../evidence/bortus-precheckpoint-readback-controls-root-20261014.json) pass all41 tests, retaining all33 original test methods byte-for-byte and adding eight actual-gate groups. Before the single checkpoint, the candidate waits within the existing deadline for the exact observed accounting state: allocated150m/requested130m CPU,256Mi memory,2CPU/1536Mi limits. The final guarded commit snapshot must still satisfy it before the exclusive receipt is written. Each snapshot captures only the bounded fixed accounting maps and binds them to that same UID/RV/IP; oversized unrelated status may still omit the optional full observation. After checkpoint, any RV difference continues to refuse at the unchanged line274 predicate. No cursor, baseline refresh, second commit, new lease, cgroup/writer inference or private authority is added. Fixture changes only add the exact ready maps and update source-hash bindings; original assertions remain unchanged. Independent proof verifies195 current inputs, literal41/no-skip/reaped results and both original births absent; the reader is subsequently absent. Default source scanning retains one unchanged malformed rejection fixture with zero unresolved findings and no suppression/replay. This is local qualification of an isolated candidate, not live recovery or a production guard change.

## 2026-10-14: public readiness diagnostic dispatched

The [851 public-only dispatch](../evidence/bortus-public-851-dispatch-root-20261014.json) starts one fresh diagnostic after the actual41 readiness controls and separate18 accounting-observation controls qualify independently. Closed review verifies261 packet rows,246 runtime sources,242 unchanged versus855 and the same183-source graph. Only the qualified readiness gate, composition binding, explicit qualification records/caller and coordinates change. The original600-second budget, seven real TCP assertions, one checkpoint, strict postcommit RV check and physical stop before private material remain. The source scan retains four exact old malformed-fixture/public-hash lines with zero unresolved and no suppression/replay. Outcome and exact-UID cleanup verification are pending; this dispatch grants no private recovery or production acceptance.

## 2026-10-14: Public851 final comparison and cleanup

The [851 diagnostic outcome and cleanup](../evidence/bortus-public-851-outcome-cleanup-root-20261014.json) retain actor exit1 after179.738seconds. The checkpoint is written and the seven real TCP network checks validate; the final compound snapshot/control identity comparison at gate line424 refuses. The failed-frame receipt contains no nested failed snapshot and does not establish which operand differs. No cause, postcommit RV exception, full live-holder proof or private recovery is inferred. Separate exact-UID cleanup exits0; the eight-GET independent observer confirms all five names/UIDs absent and2747 original/cleanup principal births absent. A no-child later check verifies246 original and two cleanup sources plus nine observer/query births absent; its own reader is subsequently absent. The first later reader1 is retained: two inherited855 counts were corrected to the actual8512747/179 in a distinct reader, with no actor, API or cleanup replay. Original data and production image remain unchanged.

## 2026-10-14: failed-sample diagnostics qualify locally

The [failed-sample observation controls](../evidence/bortus-sample-equality-controls-root-20261014.json) pass47 groups with all41 original test methods byte-identical. The gate’s only change binds the three existing return values inside the same final line424 comparison; removing those bindings restores the exact previous gate bytes. Call order, short-circuit behavior, seven TCP checks, strict line274 predicate, deadline, checkpoint and private stop remain unchanged. Failure-only diagnostics derive three operand equality results and13/5/5 numeric field bits from those already returned builtin tuples; skipped operands are explicit null, and no raw names, identities, RVs or addresses are emitted. Top-level key subclasses are rejected before lookup; malformed/oversized data is omitted within the existing single4KiB receipt. There are no extra API or guard calls. Independent proof checks196 current sources, the literal47/no-skip/reaped result and both original process births absent; its reader is subsequently absent. The source scan retains one exact malformed rejection fixture with zero unresolved and no suppression/replay. Earlier V1.1/V1.2 source-only variants remain unrun. This local qualification does not explain the historical851 operand failure or grant live recovery acceptance.

## 2026-10-14: public final-comparison diagnostic dispatched

The [836 public-only dispatch](../evidence/bortus-public-836-dispatch-root-20261014.json) starts one fresh diagnostic after all47 integral controls pass, including the41 preserved controls. Closed review verifies260 packet rows,246 runtime sources,242 unchanged versus851 and the same183-source graph. The final comparison only captures the same returned operands for failure-only numeric observations; its call order, short circuit and acceptance predicate remain unchanged. The original600-second budget, seven real TCP assertions, readiness wait, one checkpoint, strict postcommit RV check and physical stop before private material remain. The default scan retains four accounted unchanged malformed-fixture/public-hash lines, with zero unresolved and no suppression/replay. Outcome and exact-UID cleanup verification are pending; this dispatch grants no private recovery, performance, security or production acceptance.

## 2026-10-14: Public836 comparison and cleanup

The [836 diagnostic outcome and cleanup](../evidence/bortus-public-836-outcome-cleanup-root-20261014.json) retain actor exit1 after181.087seconds. Its checkpoint and seven real TCP assertions complete, then the final comparison refuses: all13 holder fields match; control0 retains its name/namespace/UID/address but its RV differs; control1 is skipped by the original short circuit. The bounded999-byte failure receipt establishes that comparison only, not allocation changes, a writer/cause or the historical851 cause. Strict RV acceptance is unchanged. Separate exact-UID cleanup exits0; eight independent GETs confirm all five names/UIDs absent and2690 original/cleanup principal births absent. The later no-child check verifies246 original sources, two cleanup sources and nine observer/query births absent; its own reader is subsequently absent. The original2506-job incomplete registry remains honest. No private recovery, production image change or original-data retirement follows.

## 2026-10-14: Control accounting qualifies locally

The [control accounting diagnostics](../evidence/bortus-control-accounting-controls-root-20261014.json) pass55 local controls: all47 existing methods/assertions remain byte-identical, with eight new groups. The same already-guarded control GETs supply bounded immutable allocation/request/limit samples. Their checkpoint baseline becomes available only after the original successful commit; failure-only output distinguishes baseline, sample entry and evaluated end, with skipped controls explicit. No extra GET, guard execution, status readiness policy, guessed resource target, acceptance waiver or raw identity/value output is added. Both physical strict274 and424 comparison lines, all seven TCP checks, one checkpoint and original600-second lease remain exact. The single4KiB failure receipt drops new optional observations first when full. Independent qualification verifies197 current sources, literal55/no-skip/reaped results and the original two process births absent; its reader is subsequently absent. The208-file default scan retains one unchanged malformed rejection fixture with zero unresolved findings and no suppression/replay. This does not establish the allocation/writer cause of836 or grant live recovery acceptance.

## 2026-10-14: public final-comparison diagnostic dispatched

The [a729 public-only dispatch](../evidence/bortus-public-a729-dispatch-root-20261014.json) starts one fresh diagnostic after all55 integral controls pass, including the47 preserved controls. Closed review verifies261 packet rows,246 runtime sources,242 unchanged versus836 and the same183-source graph. The existing guarded control samples now provide failure-only finite allocation/request/limit observations across checkpoint, sample entry and evaluated end. No extra GET, control readiness policy, guessed accounting target or guard change is added. Call order, short circuit and acceptance predicates remain unchanged. The original600-second budget, seven real TCP assertions, readiness wait, one checkpoint, strict postcommit RV check and physical stop before private material remain. The default scan retains four accounted unchanged malformed-fixture/public-hash lines, with zero unresolved and no suppression/replay. Outcome and exact-UID cleanup verification are pending; this dispatch grants no private recovery, performance, security or production acceptance.

## 2026-10-14: a729 field observation and cleanup

The [a729 outcome and cleanup](../evidence/bortus-public-a729-outcome-cleanup-root-20261014.json) retain actor exit1 after178.748seconds. The checkpoint and seven TCP assertions complete. All13 holder fields still match; control0 RV differs and control1 final comparison is skipped. Already-guarded control0 samples report requested CPU10m at checkpoint/entry, then that status field is absent; allocated10m CPU,32Mi memory and1000m/128Mi limits stay unchanged. This establishes the reported field difference, not a writer, cgroup explanation, historical836 cause or RV exception. Exact-UID cleanup exits0. Eight independent GETs confirm all five names/UIDs absent;2666 original/cleanup principal births are absent. The later no-child check verifies246 original sources, two cleanup sources,24 record pins and nine observer/query births; its own reader is subsequently absent. The original2475-job incomplete registry remains honest. Original data and production image are unchanged; private recovery remains unproved.

## 2026-10-14: stronger control-readiness qualification fails one new test

The [failed63-control receipt](../evidence/bortus-control-readiness-failed63-root-20261014.json) retains wrapper/test1 with62 passes and one new test failure. The candidate waits before the once-only checkpoint for the exact accounting shape observed after the prior live transition; missing requested-CPU status remains distinct from numeric0. The47 original core methods and entire strict sample remain raw-identical; the previously observation-only test36 explicitly changes two baseline expected rows, with fixture maps disclosed. New test49 incorrectly changes a control RV before a new sample and expects refusal; the existing guard compares control versions within each seven-TCP sample. This establishes an incorrect new-test setup, not a gate regression. A distinct correction will inject the change during that sample without altering the gate. Independent and later readers verify198 current sources, actual63/one failed and both original process births absent; the later reader is subsequently absent. No live candidate or private recovery follows this failed qualification. Production and original data remain unchanged.

## 2026-10-14: stronger control readiness passes63 local cases

The [corrected63-control qualification](../evidence/bortus-control-readiness-qualified63-root-20261014.json) passes all63/no skips under the original30/2/+1-second control lifecycle. Only new test49 changes relative to the failed candidate: its simulated RV change now occurs during the seven-TCP sample; its assertions remain identical, as do the other62 methods and the entire gate/helper bytes. The47 original core controls remain raw-identical; the stronger readiness fixture and test36 two baseline expectation changes remain explicitly disclosed. The gate waits before its one checkpoint for the exact observed control resource-status shape, with absent requested CPU distinct from numeric0; it adds no GET per existing readiness iteration. Strict holder274, the entire network sample424, all seven assertions, source/security fences and600-second live lease remain unchanged. Independent/later checks verify198 current sources and original actor/suite/post-reader absence; the later reader is subsequently absent. This qualifies local controls only. A fresh public-only functional test is being prepared; private recovery and production acceptance remain open.

## 2026-10-14: public control-readiness qualification dispatched

The [d7ae public-only dispatch](../evidence/bortus-public-d7ae-dispatch-root-20261014.json) starts one fresh qualification after63 integral local controls and independent/later closure pass. Closed review verifies264 packet rows,246 runtime sources,242 unchanged versus a729 and the same183-source graph. The exact qualified gate waits before its once-only checkpoint for the observed control accounting shape. The47 original core methods remain exact; the stronger fixture/test36 two expected-row changes and new test49 timing correction remain disclosed. The entire strict sample, seven real TCP assertions, full source/security fences,600-second lease and physical stop before private material remain unchanged. The default scan retains four accounted unchanged malformed-fixture/public-hash lines, with zero unresolved and no suppression/replay. Actual outcome and exact-UID cleanup are pending. This dispatch grants no private recovery, performance, security or production acceptance.

## 2026-10-14: public control-readiness qualification passes; cleanup verified

The [d7ae public qualification and cleanup](../evidence/bortus-public-d7ae-outcome-cleanup-root-20261014.json) complete with actor/caller0 after230.785seconds under the unchanged600-second lease. All seven real TCP assertions pass against the same already-denied holder and separately reachable controls, with one immutable checkpoint and the strict version/sample guards intact. The exact63-control-qualified gate waits for the observed control accounting shape before committing. The3470 original registered jobs across14 shards are all0/reaped/absent with a complete registry; expected job UID remains execution context, not a recorded UID claim. Matched outcome0 confirms the finite public proof and explicit no-private scoped result. Separate exact-UID cleanup0 deletes three Pods before ConfigMap/policy without force or repeated DELETE; its180 jobs are complete. Eight independent GETs confirm all five names/UIDs absent and3652 original/cleanup principal births absent. Later no-child validation0 verifies246 original sources, two cleanup sources,24 record pins and nine observer/query births, followed by its own reader absence. The source scan retains four exact previously classified public findings with zero unresolved; cleanup11-file and later5-file scans are zero. This passes the public isolation qualification only: continuous enforcement, private Secret-map recovery, performance, security and production rollout remain unaccepted. Original data and backups remain intact.

## 2026-10-14: private caller seam qualification exposes missing imports

The [first eight-group local seam evaluation](../evidence/bortus-private63-seam-failure-root-20261014.json) retains wrapper/test exit1. Two groups fail before their selected prompt checks, producing five AttributeError subcase errors: the prepared caller restores the original private phase but retains the public base imports, omitting getpass and warnings. This is a candidate composition defect; it must be fixed in the actual module, without injecting missing globals into tests or relaxing the gate. The other assertions and historical packets remain retained. No live recovery actor, private prompt, credential, backup read or production operation occurs.

Independent and later checks pass while preserving controlsQualified:false, tests_run8 and tests_passed:null; subcase errors are not subtracted to invent a passed-group count. They verify205 declared source leaves plus the CONTROL manifest, all seven actual records and the actor/suite births absent, followed by reader absence. The default212-file source scan stays literal1 for one exact unchanged malformed public rejection fixture, independently classified with zero unresolved and no suppression/replay. Both two-file post scans are zero. A fresh import-corrected candidate and focused evaluation remain necessary; the successful public d7ae qualification does not grant private recovery acceptance.

## 2026-10-14: corrected private caller passes eight focused seams

The [corrected eight-group local qualification](../evidence/bortus-private63-seam-qualified8-root-20261014.json) passes8/no skips after restoring the actual caller getpass/warnings imports from the original private source and correcting its misleading public-only docstring. Every caller function and the restored private phase remain byte-identical. Test01 now checks those actual module dependencies; its old assertions and the other seven methods remain unchanged, with no injected missing globals. The failed predecessor remains failed.

The finite cases exercise selected exact caller AST and actual gate, API admission/readiness and reader functions with public fixtures. They cover pre-prompt refusal, post-input gate checks, deferred private Pin boundary, API status/journal preservation, reconstructed checkpoint/admission hashes, closed oracle schema and honest partial outcomes. They do not execute the complete actor, real credential input, cryptography, network or restore, and do not rerun the unchanged63 suite. Independent and later checks pass for205 declared source leaves plus CONTROL, all seven actual records and both actor/suite births absent, followed by reader absence. The214-file source scan remains literal1 for the exact unchanged malformed rejection fixture, zero unresolved and no suppression/replay; both two-file reader scans are zero. Actual private retained-snapshot recovery and production acceptance remain open.

## 2026-10-15: numeric failure controls and maintained source bodies qualify

The [numeric diagnostic evaluation](../evidence/bortus-private-material-diagnostic-qualified6-root-20261015.json) passes six local public groups after a [retained fixture failure](../evidence/bortus-private-material-diagnostic-failed6-root-20261015.json) in test06: the selected reader fixture omitted its actual outcome variable. The correction adds that public fixture only; every assertion and the other five methods remain unchanged. The original material projection, gate, private phase, cleanup and 600-second live lease remain exact. Failure-only capture retains at most 32 code nodes/eight numeric frames in one optional 4KiB record, without exception text, arguments, locals, operator paths or value digests. Controls exercise freshness, subtype/canary exclusion, bounds, exclusive writes, cleanup and the original gate/reader seams. Both failed and passing evaluations have independent, later and final reader-absence checks. Their 207 sources plus CONTROL remain current. Default scans remain literal1 for the exact unchanged malformed public rejection fixture, zero unresolved and no suppression/replay. No private input, network or actual recovery executes here.

## 2026-10-15: finite sorting and fresh source composition; recovery binding refusal

The [new private attempt](../evidence/bortus-private76-stage1-refusal-root-20261015.json) stops at stage1 with actual tool/outer/caller1 after 0.301 seconds, before same-holder proof or credential input. The unchanged all-183-old-source correspondence check currently rejects the diagnostic material row even though that row matches the qualified six-control source; 182 other rows and the gate match. This current witness does not identify the historical first exception. No guard is waived. Eight independent read-only GETs confirm all five names absent; the principal birth and nine later observer/query births are absent, followed by the later reader. All 247 sources plus manifest remain current. Actual private recovery remains open.

## 2026-10-15: exact two-authority source correspondence qualifies

The [six source-correspondence controls](../evidence/bortus-checkpoint-material-correspondence6-root-20261015.json) pass actual, independent, later and final reader-absence checks. The caller now requires the exact 182 unchanged original63 rows and gate, plus the one exact diagnostic material row through its completed six-control proof and 207-source manifest. All other 24 caller functions, private phase, cleanup and original 600-second lease remain unchanged. The new finite tests execute the actual qualification functions with public fixtures: the old whole-graph check refuses the diagnostic row; exact two-authority correspondence passes; unrelated graph/gate/material/proof changes and original deadline/pin faults refuse. The public unit FD adapter does not replace runtime Pins. No old63/eight/material6 suite is replayed. Current 236 sources plus CONTROL and original actor/suite/post-reader absence are verified. The default492-file scan retains five exact unchanged public checksum/malformed-fixture findings with zero unresolved; post12-file and later1-file scans are zero. This qualifies the correction locally; a new private attempt remains unrun.

## 2026-10-15: fresh candidate build verified; corrected private source prepared

The [corrected private source preparation](../evidence/bortus-private-dfe-source-prepared-root-20261015.json) passes source-only generation and closed-packet review with 247 runtime leaves plus manifest. The two actual-function-qualified correspondence functions remain raw-identical; only three public run coordinates change inside run_once. The native snapshot verifies 500 fixed public files under the unchanged 512-file, 16MiB raw, 32MiB envelope and 30-second limits, preserving all original455 paths and adding 14 proof records plus31 source/control rows. Its native process is reaped and subsequently absent. Full new236-path currentness remains the prior root post/later proof, distinct from the fresh selected-path native snapshot. The original AST warning is retained. The new runtime source is not staged and no private actor, credential or restore has run. A separate Linux prelaunch review remains required; no recovery acceptance is granted.


## 2026-10-15: interactive recovery831 fails; exact cleanup verified

The [recovery outcome and cleanup](../evidence/bortus-private831-failure-cleanup-root-20261015.json) retain tool/outer/caller exit1 after491.318 seconds under the original600-second limit. Same-holder and independent prompt checks pass, and authorized input is actually delivered through the verified foreground, echo-off channel. Private inputs may have been read. Material validation stops at stage8/type2, with no optional material note; no exact inner cause, restore, API startup or recovered Secret-map acceptance is claimed. All6,854 registered jobs are typed/reaped/absent:6,853 exit0 and one exit1; its ordinal does not identify the command.

Separate exact-UID cleanup0 removes only the three Pods, ConfigMap and policy, with186 jobs all0/reaped/absent. Eight independent GETs verify all five names/UIDs absent. The first final verifier remains exit1 due to three stale checksum constants; a separate corrected verifier keeps all14 function bodies and guards unchanged and returns0. Final closure verifies57 public records,247 original runtime leaves plus manifest,11 staged sources,7,042 actor/cleanup births and both nine-birth observer/query groups absent, followed by its own reader absence. Original data/backups remain preserved. A failure-only caller diagnostic is being qualified locally before another private attempt; recovery remains open.


## 2026-10-15: focused diagnostic controls qualify

The [two new local suites](../evidence/bortus-focused-diagnostic-controls-root-20261015.json) pass six caller-boundary cases and five profiling-helper cases, followed by independent, later and final reader-absence checks. Caller capture runs only after a failed material operation lacking an existing producer note; it preserves the original refusal/cleanup and emits at most one optional4KiB numeric record. No normal-path instrumentation or private recovery acceptance is introduced. The five helper cases exercise actual thread-CPU counters, forwarding, bounds and sample partitions in a separate restricted container. Its application/compiled/dependency inventories are explicitly empty; no compiled app or performance qualification is claimed. All16 recorded test births and the exact container ID/name are absent. Eighty-seven source/output pins and three observer/query births remain current/absent, followed by the final reader. Old test suites and the original benchmark are not replayed. Actual forwarding adapters and measured application graphs remain unqualified.


The [three historical-proof boot controls](../evidence/bortus-recovery-proof-boot-bridge-root-20261015.json) pass with independent, later and final current-file/process checks. Completed proofs remain pinned to their original boot; active execution must match the current launch boot. All260 current pins and14 historical boundary-proof records verify without querying historical PIDs or replaying the old63/six suites. Only two qualification functions change; the private phase,600-second lease,same-holder and TCP gates remain exact. This is public control qualification, with no network/private input or actual recovery pass. The earlier private831 stage8/type2 cause remains unknown.

The [subsequent2b attempt](../evidence/bortus-private2b-failure-cleanup-root-20261015.json) uses the qualified bridge and actual current-source preflight, but refuses at public setup stage2/type2 after0.504 seconds, with tool/caller exit1, unchanged source, zero registered subprocesses and no sudo prompt/material projection. The independent eight-GET observer returns0 and confirms all five target names absent; it does not qualify recovery. Later/final checks verify269 current pins,11 absent recorded births and final reader absence. Source inspection establishes another required current-boot guard: `CurrentCacheReceiptCheck` loads a fixed36-row cache receipt bound to boot7f, then requires that boot to equal the active boot19d. Those values differ. This is a definite blocker, while the exact first throwing stage2 predicate is not retained. Refresh the cache receipt through its original75/60-second procedure; do not relabel the old receipt or remove its freshness check. Actual private recovery remains unproved. The Transport constructor may pin the SSH identity before this refusal; absence of a prompt does not prove every private file was unopened.


The [fresh389 cache prerequisite](../evidence/bortus-cache-currentboot-refresh-root-20261015.json) now passes its original read-only75/60-second procedure on current boot19d. Three focused boot controls and their independent closure pass. Exact metadata-only postchecking confirms eight remote and four local identities absent, with a separate final SSH absence check. Native current-byte/full-fingerprint assessment verifies19 initial sources and35 source/output records; frozen custody derives38 rows including three root records. The original cache guard still requires the active boot to match this fresh receipt; the old7f receipt is untouched. Runtime source rebinding is the next step; no successful private recovery or restore is inferred.


The subsequenta57 current-boot attempt returns tool/outer/caller1 after453.2249 seconds under the original600-second limit. Its bounded failure-only numeric record maps caller825 to `SameLiveHolder.require`443/445, `_sample`417 and `need`15: the listener-liveness predicate refused during the pre-projection Pin loop. No material projector/recovered Secret-map acceptance follows; credentials were delivered and private files may have been opened before refusal. The record does not distinguish a missing listener from an exited listener or prove a termination cause. Public source caps the listener timer at300000ms even under a600-second private lease; this is a structural mismatch, not proof of the historical831 failure.

The first separate cleanup refuses before transport because its source manifest count still expects247 rather than249. It issues no deletion and remains retained. A distinct corrected helper changes that count and output coordinates only, preserves all ten helper bodies and the full natural-delete UID/resourceVersion sequence, and returns0. Its175 registered jobs are complete; the new independent eight-GET observer confirms all three Pod names/UIDs, ConfigMap and policy absent, with actor/caller1 still preserved. [Final current-file/process closure](../evidence/bortus-privatea57-failure-cleanup-root-20261015.json) passes332 current FD/path/hash pins and5985 absent recorded births. The final own reader returns0; no recursive self-absence claim is added. No new private retry or original-data retirement has run.


## 2026-10-15: listener lifetime correction locally qualified

The [two focused public suites](../evidence/bortus-listener-budget-public-controls-root-20261015.json) each pass three control groups with no skips. Construction checks preserve timers up to300 seconds, use the original remaining time for longer private leases, and reject expiry. Integration checks require exact inversion of the single300000→600000 cap change to the entire old qualified gate; altered source/proof records and expired deadlines refuse. The original63-test authority,198 expected rows,183-file graph and600-second private deadline remain unchanged. Current-file/process checks pass12 and28 pins and two recorded actor births each. These are public source controls, not a600-second wall-clock run or successful private recovery. No new private runtime was frozen or retried at this checkpoint; the earlier failure and verified cleanup remain retained.
