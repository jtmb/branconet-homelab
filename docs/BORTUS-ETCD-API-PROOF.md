# Isolated retained-snapshot API Secret recovery

The accepted [raw checkpoint](BORTUS-ETCD-RECOVERY.md) authenticates exact etcd
snapshot bytes and the complete encrypted Secret registry. It is not API plaintext
decryption proof. `bortus-api-secret-proof.cjs` is separate source preparation;
it creates no isolation resources and dispatches no live operations.

Root must authenticate the accepted snapshot/config archives, privately extract
the original embedded admin client certificate/key, pin source identities and own
one absolute lease, exclusive journals, exact approved image/cache, deny-all CNI
proof and every resource UID/RV/cleanup. None is established by this Node program.
The actual API digest remains a separate cache/runtime prerequisite:
`registry.k8s.io/kube-apiserver@sha256:e190f914a6cc21cab9268485d1ae7282fdeab1315ac64b668aa42d732fd1061d`.

Mount exact public source read-only through an owned ConfigMap or equivalent
pinned file. Invoke `node <fixed-source-path> --bundle`, with material only on
stdin. `node -` consumes program stdin and cannot also receive binary frames;
never concatenate keys/data into JavaScript, argv, environment or logs. Writer,
etcd and API may share explicit UID1000 and the memory volume. Production `/proof`
must be owned0700 on actual tmpfs and initially empty. Nine fixed files are created
exclusive400 with no symlink, hardlink or overwrite. Library directory injection
is a public-fixture seam; the CLI accepts no path/endpoint input.

Frames are ASCII `BORTUS-API-PROOF` plus NUL, uint32BE remaining milliseconds
(1..300000), nine ordered slot headers (uint8 ID1..9, uint32BE byte length), exact
bytes, one zero byte and EOF. Slots are encryption config, CA certificate, original
serving cert/key, original SA key/public key, original admin client cert/key and
snapshot. Config files are1MiB each, snapshot512MiB; chunk/buffer64KiB plus header.
No CA private key, Longhorn key, kubeconfig, arbitrary path or source-program slot
is accepted. Missing/duplicate/reordered/oversized/extra/late framing refuses.
Complete output follows file/directory flush and identity checks. Failed partial
files remain solely in the owned memory Pod for explicit root cleanup.

The remote timing header narrows a deadline measured from Node process start.
Node/WSL clocks need not share a boot origin. It is additional protection, never
authority to renew root's original absolute lease. Each header is bounded by the
actual remaining root lease and300000ms. Root must supervise every
send/read/child and check its original lease before acceptance. Header narrowing
also moves the input idle timer; quiet input cannot extend the remaining budget.

After exact etcd restore/isolated API startup, `--oracle` receives only the timing
header and EOF. Fixed HTTP127.0.0.1:32379 `/v3/kv/range` reads `/registry/secrets/`;
verified HTTPS127.0.0.1:16443 lists `/api/v1/secrets` with bounded continuation and
same collection RV. Original CA/admin identity, rejectUnauthorized=true, empty
SNI and explicit original192.168.0.4 certificate hostname verification are
mandatory, with TLS1.2 minimum explicitly fixed. No insecure fallback, production
endpoint, token or mutable host exists. A partial quiet HTTP response must expire
under the original deadline and close its owned socket without returning a map.

Independent Node built-in crypto accepts original32-byte aescbc keys, exact
`k8s:enc:aescbc:v1:<name>:` framing,16-byte IV, complete CBC blocks and strict PKCS7.
Unsupported providers/storage formats refuse. CBC is not authenticated encryption;
prior age-authenticated snapshot/config inputs remain indispensable. The oracle
compares complete namespace/name/UID/type/optional immutable state and binary key
maps, including empty values and prototype-looking names. Registry ciphertext
maps must match before/after API reads. It never reads current production values.
Validated typed SecretList items may omit API/kind; only absent fields inherit
collection type. Explicit null/wrong headers refuse.

Pinned v1.37.1 sources: [Unknown/TypeMeta](https://github.com/kubernetes/kubernetes/blob/v1.37.1/staging/src/k8s.io/apimachinery/pkg/runtime/generated.proto),
[Secret](https://github.com/kubernetes/kubernetes/blob/v1.37.1/staging/src/k8s.io/api/core/v1/generated.proto),
[ObjectMeta](https://github.com/kubernetes/kubernetes/blob/v1.37.1/staging/src/k8s.io/apimachinery/pkg/apis/meta/v1/generated.proto),
[protobuf framing](https://github.com/kubernetes/kubernetes/blob/v1.37.1/staging/src/k8s.io/apimachinery/pkg/runtime/serializer/protobuf/protobuf.go),
[CBC/padding](https://github.com/kubernetes/kubernetes/blob/v1.37.1/staging/src/k8s.io/apiserver/pkg/storage/value/encrypt/aes/aes.go)
and [prefixes](https://github.com/kubernetes/kubernetes/blob/v1.37.1/staging/src/k8s.io/apiserver/pkg/server/options/encryptionconfig/config.go).
Exact [public bytes/hash evidence](implementation-evidence/api-secret-proof-primary-sources.json)
is retained. Decoder refuses unknown schema
fields, groups, duplicate singleton/data keys, malformed lengths/varints,
unsupported compression/content type and invalidUTF8. Other metadata is wire
bounded but outside the selected identity/data equality scope.

Replies are8MiB each; registry reads share64MiB received/decoded bounds, API pages
share64MiB, inventory10000 and Secret data1MiB. Caps refuse the whole proof. Sockets
share one unrenewed Node deadline and close on success/refusal. Configuration
descriptors and exact file/parent identities remain pinned through completion.
Only counts/flags leave the oracle: no plaintext values/names/keys/raw errors or
plaintext digests. Buffer clearing is best-effort; JavaScript cannot guarantee
erasure of strings/allocator copies. Root must explicitly remove the owned memory
Pod and confirm complete name/UID absence, even after failure.

Original encryption/signing/serving keys are not replaced. Kubernetes may create
an [internal ephemeral loopback signer](https://github.com/kubernetes/kubernetes/blob/v1.37.1/staging/src/k8s.io/apiserver/pkg/server/options/serving_with_loopback.go)
in memory; this is not regeneration of
original keys. No controllers/scheduler/application startup is needed. Local
fixtures and API equality do not prove Longhorn/LUKS recovery, continuous current
values or full control-plane disaster recovery. Overall acceptance stays false
pending root's actual scoped procedure. Before invoking the oracle, root must
verify exact restored snapshot status/revision and accepted authenticated archive
bindings; private oracle equality alone cannot identify which archive was loaded.
Etcd/API launch stdout/stderr must be discarded before startup, without audit or
raw API/error logging. Exact public source, original key correspondence and all
owned processes/resources still need before/after checks and actual terminal0.

Root [integration qualification](../evidence/bortus-etcd-api-helper-root-20261012.json)
verifies seven raw files,27 originals and seven primary references, then passes
all25 unchanged controls using the pinned Linux Node22 image and actual tmpfs/
loopback mTLS fixtures. Source bytes remain unchanged and owned processes/container
are absent. Public source checksum metadata is represented explicitly as path/SHA
records; original metadata remains retained. This is local helper qualification,
not execution against accepted archives or live API recovery.

The separate `bortus-api-recovery-specs.py` contains fixed proposal generation
and a pure persistent-resource matcher. It dispatches nothing. It preserves exact
image digests, nonroot UID1000, denied network, no token/production mounts and
initially empty owned `/proof`. A nonroot init creates owned subdirectories in
memory volumes, mounted through fixed subPaths; actual server defaulting and
volume permissions remain live prerequisites. Known absent defaults normalize
only exact literal values, for each ordinary/init/ephemeral container. Explicit
values, added containers/mounts and changed UID still refuse. Persistent RV is
mandatory and opaque. Runtime matching requires exact spec digest and literal
status.imageID; bounded status.image is display only.

The proposed order is bundle, exact snapshot status/integrity restore, restored
loopback etcd, complete ciphertext map in private RAM, then a once-only API
ephemeral-container update with fresh Pod UID/RV. Root must compare that baseline
after API startup and again after the oracle, because the oracle alone covers
only its own read interval. The update body preserves the complete current Pod
spec and adds only the fixed API container; actual subresource CAS semantics,
admission/defaulting and cleanup are not established by pure controls.

Pinned [v1.37.1 image source](https://github.com/kubernetes/kubernetes/blob/v1.37.1/build/server-image/kube-apiserver/Dockerfile)
copies `/go-runner` and `/usr/local/bin/kube-apiserver`, and assigns the latter
`cap_net_bind_service=+ep`. This source evidence is not the actual e190 cached ELF
or xattr proof. The draft gives only the API container NET_BIND_SERVICE in its
bounding capabilities, with no privilege escalation, to avoid excluding the
file capability; its actual nonroot runtime compatibility remains unqualified.
The [pinned runner](https://github.com/kubernetes/kubernetes/blob/v1.37.1/staging/src/k8s.io/component-base/logs/kube-log-runner/kube-log-runner.go)
redirects child streams to `/dev/null` before launch. Restore commands instead
use owned exec streams with supervised discard and actual exit0. There is no
assumed shell in distroless images, wrapper transfer, mutable pull or copied key.

Root still owns the missing narrowly scoped launcher bindings: authenticated
accepted config/snapshot pins and fresh original material correspondence,
server dry-run/default matching, cached executable proof, streaming exec stdin,
ephemeral PUT once-only intent, TLS readiness and independent conditional cleanup.
No API recovery procedure or resource has been executed by this source proposal.
The [12-control qualification](implementation-evidence/api-recovery-proposal-qualification.json)
is pure Windows/public preparation. It retains the original11-control pass and
the actual followup refusal-test failure where Python compared integer0 equal to
explicit Booleanfalse. Type-strict recursive matching now refuses that
substitution; original source/results stay preserved. There is no actual API,
cache, TLS transport or ephemeral-update acceptance in these controls.

`bortus-api-recovery-transport.py` is a separate callable adapter, not an extension
of the accepted raw checkpoint transport API. Construct the exact exported
`backup.Transport` and a fresh empty `backup.Ledger`, wrap the latter with
`RecoveryJournal`, then construct `APIRecoveryTransport(transport, journal,
programme_text, prerequisite)`. The new closed ABI2 journal uses the existing
exclusive/fsynced durability backend but cannot adopt a prior etcd record. Its
operations contain only action, state, public proposal hash and scoped UID/RV;
material bytes, ciphertext inventories and plaintext digests never enter it.
Both default backup record/API and all existing callers remain unchanged.

The trusted root `prerequisite(action, deadline)` must establish actual current
source/material/cache/isolation proof and return exactly those four receipt SHA
bindings. They persist before dispatch, remain stable and are checked before and
after every operation. This callback is external authority; four supplied hashes
are not themselves proof. Root still owns authenticated archive/material delivery,
server dry-run/defaulting, current source/key continuity, cached executable ABI,
CNI enforcement and the complete baseline ciphertext map before API addition.

The adapter supplies fixed create/ephemeral PUT, nine-slot duplex stdin, status,
restore, restored-etcd exec, private registry read, oracle and conditional deletion
methods. Original absolute lease is at most600 seconds and never renewed; remote
Node headers additionally narrow it to at most300 seconds. Every mutation has a
durable once-only intent. Ambiguous replies or late prerequisite/flush failures
retain pending/uncertain identity and cannot be retried or adopted. Exec uses the
exact protected inherited kubeconfig inode validated for embedded mTLS/approved
origin; pins stay owned until child closure. No material is copied into argv,
environment, a credential file or public output. Streams are bounded and owned;
restore/API/etcd output is discarded before it can become a container log.

Create confirmations are full admitted-spec metadata checks. Ephemeral PUT uses
fresh owned Pod UID/RV and preserves its full spec; confirmation proves admitted
submission only. Runtime/imageID is checked separately before data reads. Local
name-based exec is not atomic with a preceding GET's UID/RV; fresh full-spec/UID
checks before and after each read remain required and cannot erase that race.
Running ephemeral status does not prove a listening verified-TLS API; root must
qualify a separate bounded readiness read before the once-only oracle.
exec closure does not prove remote process death: root must confirm Pod name/UID
absence. Policy/ConfigMap deletion refuses until Pod deletion plus complete typed
absence is durable. Explicit cleanup is once-only, never automatic failed-run
adoption. Adapter close attempts all its own child closures independently and
leaves borrowed Transport/Ledger closure to root. Root must also independently
confirm the complete cipher map after API startup and after oracle, the original
source/key fences, terminal0 and actual resource absence. Overall acceptance
remains false; no default transport extension or actual recovery is implied.

The [14-control qualification](implementation-evidence/api-recovery-transport-qualification.json)
uses real local Python child/pipe/session ownership, inherited descriptors and
disposable embedded-mTLS files, with public kubectl replies/exec shims. It exercises
duplex framed delivery, pending-before-child fsync, ambiguous reply/no replay,
UID/spec/binding drift, original expiry, private refusal frames and conditional
typed cleanup. It does not contact Kubernetes or perform a TLS handshake, restore
an etcd database, start an API or execute the Node AES oracle. The first run's13
passes/one fixture KeyError remain retained; the distinct corrected run passes14,
with176 unchanged inputs and both actual supervisor/test PIDs absent. Verified-TLS
readiness remains a separately requested follow-up and is not covered by this run.

A distinct readiness delta adds `wait_tls_ready()` before `oracle_once()`. It
executes only fixed public Node source, reads pinned original CA/admin material
inside owned `/proof`, and sends verified HTTPS `/readyz` to loopback16443 with
empty SNI and explicit original192.168.0.4 certificate identity. The unchanged
CJS helper has no new CLI mode or input slot. Exact200, text/plain and literal
`ok` are required, matching the [pinned v1.37.1 readiness handler](https://github.com/kubernetes/kubernetes/blob/v1.37.1/staging/src/k8s.io/apiserver/pkg/server/healthz/healthz.go).
Only connection-refused/reset/timeout and500/503 permit bounded startup polling;
certificate/auth/redirect/encoding/body faults refuse. One socket at a time,
4096-byte reply,1MiB aggregate,4096 attempts and the original narrowed absolute
lease bound the operation. No response body/material/error leaves the child;
key buffers are cleared best-effort. The durable readiness intent confirms only
after actual200 plus before/after owned Pod/prerequisite checks. It is separate
source preparation requiring actual root qualification/dispatch; the earlier14
controls do not establish these new semantics.

The [separate readiness qualification](implementation-evidence/api-recovery-readiness-qualification.json)
now records15 actual Node22.23.3 public TLS controls and14 updated Python
transport controls, both exit0. The fixed readiness literal and177 sources stay
unchanged; actual supervisor/stage PIDs and the owner-filtered container inventory
are absent. Wrong CA/SAN,401, redirect, nonliteral200 body, encoding/length/chunk
bounds, partial quiet/repeated503 expiry, extra input and credential-file drift
all refuse. Verified mTLS200, two503 startup replies and a delayed listener pass.
These use disposable keys and a network-none cached Node image, not the actual
e190 API or operator material. The original immutable14 qualification/failure
remain unchanged. Live cached ABI/defaulting/API recovery and root fences are
still required; fixture success never grants overall acceptance.

## 2026-10-12: root integrated API transport and TLS readiness qualified locally

The [root qualification](../evidence/bortus-api-transport-readiness-root-20261012.json) verifies eleven native raw blobs/modes and 564 retained artifacts, then integrates the separate recovery journal/transport and fixed readiness operation. All 14 root Python transport controls and 15 actual pinned Node22 TLS controls pass, with 176 inputs unchanged and a fresh successful query proving the owned Node container absent. The first root supervisor refused during a transport run; unchanged inputs and observed child closure are retained, but its exact supervisory predicate is unproven. Successful tool output is retained by the execution tools; receipt fields are explicit transcriptions rather than claims of original stdout files.

The default checkpoint transport and CJS oracle remain unchanged. The new API journal/adapter requires actual external source/material/cache/CNI receipt authority and original absolute deadlines. Verified TLS readiness precedes the once-only oracle; pending/uncertain mutations cannot replay or adopt. These public/shim/TLS controls grant no cached-binary, live API decryption, Longhorn or complete recovery acceptance. No live resource or credential delivery occurred.

## 2026-10-12: protected direct-home cache prerequisites verified

The [root cache preflight review](../evidence/bortus-api-cache-preflight-root-20261012.json) verifies five V5 source files,15 original local-control artifacts and13 original actual preflight artifacts. All19 public controls pass; the single read-only SSH preflight completes with exit0. `/home/james` is UID/GID1000, mode0750 with stable nofollow directory pins; available disk is26,876,416,000 bytes and available memory10,854,596,608 bytes. Root independently observes the five recorded local process identities absent.

The existing group-writable `.local` directory is unchanged. The actual inspector will use a fresh exclusive root-owned0700 `.bortus-api-cache-<12hex>` leaf directly under the verified home. No leaf, cached-image export, privileged operation or public ELF execution occurs in this preflight. Actual fixed-digest archive/platform/capability/ABI inspection and current isolation/material authority remain separate live prerequisites.

## 2026-10-12: actual fixed-cache and copied helper ABI verified

The [actual root cache receipt](../evidence/bortus-api-cache-actual-root-20261012.json) records one successful fixed-digest export and copied public ELF help/version inspection. Target e190 selects Linux/amd64 manifest `1f207ab...`; the retained31,203,840-byte archive hashes to `9da36b45...`. The static runner and API binary match validated OCI blobs; runner flags and literal Kubernetes v1.37.1 pass as UID1000. Actual API-file metadata has effective NET_BIND_SERVICE only. The existing approved ephemeral API security context already adds NET_BIND_SERVICE after dropping ALL; this receipt changes no profile.

A distinct authenticated read-only review hashes14 completed JSON records and the archive, cross-binds the completed journal to the returned result and freshly proves all five recorded remote identities absent. The sudo-n authentication refusal remains separately retained; no export/helper execution is replayed. Source pins remain unchanged and both private credential deliveries have independently observed waiting-TTY echo disabled. Original-image execution through CRI, current isolation/material authority, accepted-material API decryption and UID/RV-fenced resource cleanup remain unqualified. No API server or container started.
