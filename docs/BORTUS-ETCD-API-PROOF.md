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


The [root current utility cache read](../evidence/bortus-utility-cache-current-root-20261012.json) completes authenticated fixed CTR discovery with actual exit0 and proves the frozen `docker.io/library/bortus@sha256:068254f38c47f99fd35604185a806a92147d934010329638b32adb5c19802c90` reference absent on the master. This BORTUS image is used solely as the inert Node utility; it is not an official Node image. The earlier unprivileged permission refusal does not establish absence. Root independently verifies two local identities and the remote CTR identity absent. No pull/export/tag/import, Pod, policy, ephemeral container or version probe is dispatched. Original-image compatibility therefore remains open until an exact verified resident reference is established; tracing existing artifact/alias provenance is preparation only. The private no-echo credential bridge is unchanged, and the retained staging/validator failures grant no cache claim.


The [root cache refusal review](../evidence/bortus-utility-cache-refusal-root-20261012.json) retains the single actual cache-name attempt with exit1 and its independent read-only journal observation with exit0. The durable journal records a refusal after one successful read-only CTR job, with no alias intent or alias job; that remote identity and all four local actor/observer identities are freshly absent. The actor is not replayed. This establishes no new cache-name state or original-image execution acceptance. A separate bounded read-only discriminator must distinguish image-list parsing from the exact resident source-name prerequisite before further cache work; no Pod, policy, ephemeral container or image version execution follows from this refusal.


The [root fixed cache discriminator](../evidence/bortus-utility-cache-discriminator-root-20261012.json) completes one read-only images-list command with actual controller/SSH/CTR exit0 and owned-child reaping. The45,570-byte table is parsed by the unchanged actor parser as104 images; both exact c29 source tags and the frozen068 utility digest reference are absent in this current sample. Only bounded fixed-name flags and public hashes are retained, and both local process identities are independently absent. This distinct read cannot retrospectively prove the earlier unretained table or original refusal cause. No import, alias, pull or image/resource execution occurs. Exact retained artifact provenance and a separately reviewed once-only preload are required before original-image compatibility testing; no profile or utility substitution is approved.

The [root retained-master preload controls](../evidence/bortus-retained-master-preload-controls-root-20261012.json) verify26 selected raw artifacts,58 closed archive members (57 originals plus exact manifest) and14 current executed source hashes. All11 public POSIX controls pass once in0.393 seconds; the gated supervisor exits0 in0.589 seconds under its original30-second bound. Default17-file scan exits0 with no findings, and fresh root checks prove all five test/supervisor/shim/scanner identities absent. V3 changes the fixture socket binding only; production helper/composer stay exactV2. The setup bootstrap and packaging failures and syntax warning remain visible. These controls exercise validators and actual public Python child/file primitives, not full privileged root_entry or image postconditions. The current retained server archive remains unobserved; a separate fixed-master caller and independent journal reader must qualify before server-side inspection/import. No image/import/Pod/policy operation is accepted here.

## 2026-10-12: current retained master archive inspection

The [root inspection](../evidence/bortus-retained-master-inspection-root-20261012.json) completed once in43.147s with actual caller/outer/inspection/reader exits0. Both remote readers and local owned identities are independently absent. The retained c29 archive is1,150,326,784 bytes with a current stable nofollow fingerprint and validated historical preload record. `full_archive_verified` remains false: no complete tar hash, import, alias, image execution or version resource was dispatched. A distinct fixed-master importer must bind this current inspection, verify the full archive before one durable import intent, and retain a separate strict import journal/closure reader. The original public scanner exit1/public SHA-context finding is retained and classified without source or rule changes.

## 2026-10-12: retained master archive imported

The [root import proof](../evidence/bortus-retained-master-import-root-20261012.json) verifies the current retained1,150,326,784-byte archive hash,67 members and16 ordered layers before one held-FD import. Actual outer/caller and six image-command exits are0; root independently observed ten remote and four local identities absent. Source tag/config/manifest match fixed c29 metadata; no digest alias, version resource or API recovery was performed. The earlier cheap-inspection flag remains false as historical evidence; separate full archive validation proves this later stage. A fresh alias-only owner and subsequent current isolation/version/API material checks remain required.

## 2026-10-12: current master digest alias completed

The [root alias proof](../evidence/bortus-current-master-alias-root-20261012.json) follows the separately verified current archive import. One no-force alias succeeds with all 13 image commands successful and reaped, fixed metadata before and after, and independently absent 17 remote and four local identities. Caller and outer exits are zero in 20.04 seconds within the original 75-second local/60-second remote bounds. The [public controls](../evidence/bortus-current-master-alias-controls-root-20261012.json) qualify source, receipt and lifecycle refusal handling; actual privileged evidence comes from this distinct owner. This utility image is c29 BORTUS, not the original kube-apiserver image. Current CNI, isolation, material and version prerequisites and API decryption recovery remain unaccepted. No original data or application writer changed.

## 2026-10-12: held original-image version launcher controls

The [root receipt](../evidence/bortus-version-launcher-controls-root-20261012.json) retain the first fixture-copy setup failure and a distinct corrected input-only run: all 13 public controls pass in 0.567 seconds, with actual outer exit zero. Production launcher and assertions are unchanged. Root verifies all 310 files and 311 unique ZIP members by bytes, hashes and CRC, reads the complete launcher/original runner, and independently observes all 14 preflight/control/scanner PID-start identities absent. The selected ten-file default scan exits zero with no findings. These controls import the original default source graph and validate receipt drift, expiry and refusal; they do not construct a Transport or make a cluster request.

The actual version probe is still held at this checkpoint. Its scope is an inert temporary utility Pod plus the original API image's version command under the original 120-second deadline, without snapshot material or server startup. Historical TCP-denial evidence and current exact Calico correspondence do not establish new or continuous enforcement. Actual outer success, source stability, child closure and complete typed Pod/policy absence are still required; plaintext API recovery and overall acceptance remain open.

## 2026-10-12: original version probe refused; separate cleanup verified

The [root receipt](../evidence/bortus-version-refusal-cleanup-root-20261012.json) records the once-only 4c version probe as an actual failure. Its 111 kubectl jobs exit zero and are reaped, but the semantic probe refuses after only the policy and inert Pod creates are confirmed; API-add never occurs. A later read-only observation finds the same Pod RunningReady with the correct original utility image and full spec. That does not reveal which original predicate failed. No API container, server or snapshot material was used, and no version success is accepted.

A separately reviewed d829 cleanup then completes with actual outer/caller/supervisor exits zero and 48 reaped successful CLI jobs. Fresh UID/resourceVersion delete intents remove only that owned Pod, prove complete typed name/UID absence, then remove its policy. Root independently verifies named404 and complete typed lists (six other Pods, zero policies), 50 cleanup process identities absent, and a further 171 distinct local PID/start identities absent across failure, cleanup and readers. The original refused journal stays byte-for-byte unchanged. Root verifies the 40-file/41-member immutable package by bytes/hashes/CRC, including 38 reread retained originals and two derived documents. Cleanup grants no version or API recovery acceptance. A source-only predicate trace is the next investigation; the original matcher, 120-second deadline and once-only dispatch remain fixed. Gluster/Vault/Consul originals and backups remain preserved.

## 2026-10-13: trace binding diagnosed and modeled controls qualified

The [root trace review](../evidence/bortus-version-trace-controls-root-20261013.json) preserves the earlier zero-test and original 18-control failures. A separate 46-function source diagnostic completes with actual exit zero while the original binding still refuses before and after comparison. Three slots have equal typed code content despite different marshal serialization; five proposal functions differ because the original loader compiles selected FunctionDef AST bodies while the old verifier compiled the whole module. The corrected wrapper follows the original AST construction and checks exact typed recursive code fields, constants and slices. Original probe, matchers, constructor authority, resource permissions and 120-second lease remain unchanged. This diagnoses the wrapper; it does not identify the original live probe's refusing predicate.

All 24 modeled controls then pass once with test exit zero in 5.216 seconds. Default scanning exits 1 for one generic-api-key finding on the fixed public spec-source SHA declaration; supervisor and root outer exit 1 are preserved. Root independently binds the declaration to the retained public source bytes, without suppression, representation edits or test/scan replay. Separate metadata verification exits zero and freshly proves supervisor, test, scanner and reader identities absent. Root verifies all 108 package files and 109 ZIP members by bytes, hashes and CRC, including 78 reread actual-stage originals. These are scoped modeled/source controls, not a successful combined supervisor run or actual constructor/runtime proof.

A source-only traced caller adds bounded, closed observations around the unchanged original execute call. The actual new version probe remains held at this checkpoint; no material or API server starts, and version, plaintext API recovery, full-image security and overall acceptance remain open. The original failed probe and successful separate cleanup retain their independent outcomes.

## 2026-10-13: traced refusal, current dry-run default and owned cleanup

The [root receipt](../evidence/bortus-version-dryrun-cleanup-root-20261013.json) preserves the original a726 failure: 87 successful CLI jobs and 47 trace events identify refusal at dryrun_match, before API-add. The full original reply was not retained, so its exact rejecting predicate remains unproved. Root verifies 102 archived files, 103 ZIP members and 99 current originals; the original failure is not upgraded.

A distinct current dryRun-only request succeeds with 23 reaped CLI jobs. The original matcher rejects the response, which contains exactly an extra empty resources object; removing only that field from a disposable in-memory comparison makes the unchanged matcher pass. Same Pod/policy UID and resourceVersion, source and CNI checks pass before and after. No persistent API-add, server or materials are dispatched. This identifies current default normalization only. The metadata reader exits zero, and root freshly verifies all 26 recorded identities absent.

A separate c931 cleanup succeeds with 48 reaped CLI jobs, deleting only the owned Pod with fresh UID/resourceVersion preconditions, proving complete absence, then deleting its policy. Independent typed reads confirm both names and UIDs absent (six other Pods, zero policies); root freshly verifies all 56 cleanup/reader identities absent. The original refused record is unchanged. Version/API recovery remain unaccepted; Gluster, Vault/Consul originals and accepted backups stay preserved. A minimal exact-empty-default correction remains a distinct source proposal.

## 2026-10-13: exact-empty ephemeral resource default controls

The [root pure-control receipt](../evidence/bortus-empty-ephemeral-resources-controls-root-20261013.json) records a distinct two-line proposal that uses existing strict default normalization only for ephemeralContainers. Absent expected resources may match exactly an observed empty object; nonempty resources, wrong types, command/security/unknown-field drift, ordinary containers and explicit expected resources retain their original checks. All16 pure controls pass, including original request-body/input immutability and UID/resourceVersion fences. The first launcher executes zero tests and exits5 because it uses a detached module namespace; that failure is preserved. A distinct launcher changes execution to the real main module and completes the controls with actual exit0 in0.156s. Both test identities are freshly absent. The default scan of changed source/tests/review exits0 with no findings.

These controls make no Transport construction or API request. Original f080 source and accepted graphs remain immutable; new source5e47 is only a separately pinned proposal for a fresh held version procedure. The current empty-default observation does not reconstruct the original failed reply. Actual version, API recovery, final image/security and live adoption remain unaccepted.

## 2026-10-13: original-image version branch and independent cleanup verified

The [root version receipt](../evidence/bortus-original-image-version-root-20261013.json) binds the separately qualified exact-empty ephemeral resources normalization to a fresh version-only run. Caller/supervisor/actual outer exit0, all five operations are confirmed and155 CLI jobs are reaped. The independent reader adds ten successful read-only jobs, proves named and complete typed Pod/policy absence, and verifies source/CNI correspondence. Root freshly verifies169 PID/start/UID identities absent and118 archived files. Original e190 image spec/status match and its version branch exits0; version stdout was not observed and no server or recovery material started. The eight-source default scan retains exit1/one finding, independently identified as the public spec SHA, without suppression or upgrading its scanner result. The original a726 failure/cause remain unchanged. API plaintext recovery, final image/security and live acceptance remain open.

## 2026-10-13: source scans pass; performance comparison dispatched; recovery controls refuse

The [root checkpoint receipt](../evidence/bortus-qualification-checkpoint-root-20261013.json) records separate default scans of seven tested observer/lifecycle sources and eight raw documentation files: both exit0 with zero findings, unchanged selected bytes and freshly absent scanner identities; all44 retained originals are independently verified. The original paired comparison passes its66-input preflight and starts once against baseline51e8 and candidate8cf, using the unchanged five fixtures, exporter, driver, limits and three alternating pairs. Measurement and acceptance are pending.

The first public27 recovery-helper run exits1 with a late-durability/closure/deadline classification under its90-second supervisor. Its exact final refusal cause is unproved. Partial stderr contains material and TCP errors; there is no final test count, stdout or terminal journal, so no suite pass is claimed. Root independently proves the two recorded PID/start/UID identities absent and observes no members of either owned process session in a fresh97-process census. Public fixtures model age output and TCP/API replies; actual cryptography, network enforcement and recovery material are not accepted. Original failed inputs/output remain preserved. No live deployment, limit adoption or source-data retirement occurs.

A separate one-case diagnostic against the unchanged TCP helper/test captures child exit1 and one TypeError at test line232: inherited `self.state` is a PosixPath and hides the TCP fixture’s `state()` method. The diagnostic supervisor/actual outer exit0 means capture and cleanup only. Root freshly verifies13 PID/start/UID identities absent and all204 source bytes/modes/UID/link counts unchanged. This proves the selected assertion’s fixture failure, not the other original errors, a full-suite pass, actual age authentication or live TCP denial. A distinct source-only fixture correction remains pending.

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


## 2026-10-14: pure ephemeral volume controls

The [six-control receipt](../evidence/bortus-ephemeral-volume-controls-root-20261014.json) verifies the source proposal to mount the proof volume read-only as a whole, with six API file paths under its proof directory. Ordinary utility/init/etcd mounts and security settings remain unchanged. The tests use no API, Docker or private material and do not prove admission or the historical dry-run refusal cause. The first independent reader remains failed; the distinct corrected reader and later closure pass. A fresh owned holder/current UID and resourceVersion/new immutable intent plus one dry-run are still required before any private recovery.

## 2026-10-14: latest isolated qualification outcome

The [public admission receipt](../evidence/bortus-public-admission-qualified-root-20261014.json) records one direct-TLS ephemeral-container PUT with dryRun=All returningHTTP200 against a fresh owned holder and immutable UID/resourceVersion intent. The whole proof volume is mounted read-only; all six API file flags point beneath its proof directory. Before/after persistent payloads and UID/RVs match. Independent reads verify244 current source files and415 original births absent. UID/fresh-RV cleanup naturally deletes Pod,ConfigMap,policy in order; a separate six-GET observer confirms every name/recorded UID absent, other6 Pods/1 ConfigMap/0 policies preserved, and88 cleanup/reader/query births absent. The source scanner literally exits1 with seven independently reviewed public findings: six checksums and one invalid public test PEM fixture; no suppression or green relabel occurs. No private password/backup material is released. This is current public admission proof, not private restore/API recovery acceptance; prior failed attempts remain failed.

## 2026-10-14: recovery API mount integration

The migration source now integrates the exact API spec used by the [successful public admission dry-run](../evidence/bortus-public-admission-qualified-root-20261014.json). Only the ephemeral API mounts the complete proof volume read-only at `/memory-proof`; its six certificate/key/encryption file flags use `/memory-proof/proof/`. The ordinary init, utility and etcd mounts retain their existing writable subdirectory paths. Kubernetes forbids ephemeral-container `subPath`/`subPathExpr`; neither field is proposed. The matcher also permits only the literal empty `resources: {}` default on ephemeral containers; nonempty, null or mistyped resource objects remain rejected. This two-line matcher normalization was already present in the frozen diagnostic source, but absent from the migration repo. The integrated spec is byte-identical to that qualified diagnostic. Fifteen pure regression tests pass, including unsupported mounts, old file paths, writable access and resource-default drift. The added tests first fail against the old repo spec. See the [integration receipt](../evidence/bortus-api-volume-integration-root-20261014.json). No frozen old actor is repinned or rerun; a fresh private-recovery actor still needs current authorities and separate complete execution.

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

## 2026-10-14: bounded local qualification controls

The [local controls receipt](../evidence/bortus-local-control-outcomes-root-20261014.json) records eight passing actual failure-context/caller-handler/exclusive-writer controls. They verify a single failure-only4KiB numeric receipt, no values or guard/API reevaluation, bounded exception/frame chains, no overwrite and preservation of failure/finalizer semantics. Original30-second/closure limits are retained; seven current sources and both recorded births are independently checked. These local tests do not prove a live guard or recovery. A fresh public-only run is source preparation only.

## 2026-10-14: bounded context identifies the current public guard failure

The [c7 outcome receipt](../evidence/bortus-public-c7-outcome-root-20261014.json) retains public actor1 after116.42seconds under the unchanged600-second budget, with an unproved checkpoint and no private continuation. The tested failure-only recorder writes687bytes within its4KiB bound and records the actual exception chain: gate snapshot line274 is called by the pre-exec fence of the cross-control connector list. Only the holder Pod resourceVersion differs; the other eleven identity fields match. This does not identify the list iteration, writer/status delta or causes of earlier attempts. No guard, oracle or checkpoint refresh was introduced. Independent pre-cleanup observer0 verifies current246 sources/1621 absent coordinates and the bounded context. Exact-UID cleanup0 removes all five resources using183 complete cleanup jobs; independent eight-GET post0 verifies all five names/UIDs absent,1805 union coordinates absent and current246/two cleanup sources. Both later reader/query groups of nine are absent. Source scan retains the same four exact public findings with unresolved0; cleanup three-source scan0 has no findings. Production and original data are unchanged; private recovery remains unproved.

## 2026-10-14: qualified preparation for the next isolated gates

The [metadata/IP recorder controls](../evidence/bortus-failure-context-metadata-controls-root-20261014.json) pass all14 cases with unchanged original eight oracles, strict84d25 gate,30-second/closure bounds and physical4KiB exclusive receipt. Six cases cover complete typed metadata equality, fixed-field deltas, unknown-key changes, string-only IP comparison and malformed/subtype/budget/no-callback boundaries. The first fixture run fails six setup cases; the corrected fixture run passes9 but fails5 because actual Python3.14 function locals are a FrameLocalsProxy. One fixed-site shallow dict conversion makes all14 pass without relaxing helper input checks or changing assertions. Both failed runs and their independent source/birth closure are retained. Seven current sources and both recorded births are independently checked. No new API, guard call, status baseline or checkpoint refresh is added. These are local recorder controls, not live recovery proof. A fresh public-only metadata diagnostic is separate.

## 2026-10-14: metadata/IP observations narrow the current public failure

The [CE1 outcome](../evidence/bortus-public-ce1-outcome-root-20261014.json) preserves actor/caller1 after108.12seconds,1499 jobs/six shards and finalizer2. The unchanged strict gate fails at frozen Pod resourceVersion line274 before cross-control execution. The14-control-qualified recorder emits1009bytes inside its4KiB bound: all twelve metadata observations and Pod IP match, with no unknown metadata delta; the actual later metadata/IP guards did not execute. This does not establish a status-only change, writer or historical cause. One read-only Exact collection request for the checkpoint version returns Expired; no historical baseline is accepted and it is not retried. Before-cleanup observer0 verifies1500 absent coordinates. Exact-UID cleanup0 removes three Pods then ConfigMap/policy using179 complete jobs; independent eight-GET post0 confirms all five names/UIDs absent and1680 absent coordinates. Both later reader/query groups of nine are absent. The first extended later verifier1 incorrectly rejects a qualified zero-byte stderr row; its distinct two-change correction permits zero bytes and uses a new output, preserving all mode/hash/identity checks and the original failure. Current246 runtime/two cleanup sources remain checked. Production and original data are unchanged; private recovery is open.

## 2026-10-14: immutable public status observations qualify locally

The [33-control receipt](../evidence/bortus-checkpoint-observation-controls-root-20261014.json) passes the original14 helper and13 gate/API methods byte-for-byte plus six new actual constructor/checkpoint/writer/delta cases. Candidate gate57d0 changes three methods to retain immutable bounded status/managedFields observations only after the final strict checkpoint snapshot succeeds; helperf076 reports fixed numeric equality/unknown-field flags from an existing failing frame. The original strict resourceVersion predicate at274 remains exact, with no new API/watch, guard callback, checkpoint refresh, transition authorization, writer inference or private continuation. The original30/2+1-second and4KiB receipt limits remain fixed. Root independently verifies current194 sources and both recorded births absent. Source scan1 retains one exact unchanged malformedAAAA fixture with unresolved0/no suppression/replay. Earlier source-only V1/V1-1 drafts remain unrun. This qualifies local observation code, not live recovery or a status-only explanation. Any public actor must bind new gate/helper hashes and these actual controls explicitly; old84d25 is historical source authority.

## 2026-10-14: actual immutable status observations identify a narrower failure surface

The [804 outcome](../evidence/bortus-public-804-outcome-root-20261014.json) preserves actor/caller1 after94.53seconds under the unchanged600-second budget,1316 jobs/six shards and finalizer2. Gate snapshot274 refuses at _sample entry414; the sample iteration is not established. The bounded failure receipt binds the immutable original checkpoint: metadata/IP and all20 enumerated status fields match, while unknown status content and managedFields differ. A separate one-request exact-UID current status-keys read finds allocatedResources/resources outside that enumeration; it returns no values and cannot identify which changed at the failure. Fresh /version confirms actual serverv1.37.1. No writer, status-only exception or private recovery is established. Pre-cleanup observer0 checks1317 absent coordinates; exact cleanup0 removes all five resources using190 complete jobs, then independent eight-GET post0 checks all five names/UIDs absent and1508 coordinates absent. Both later reader/query groups of nine and the final checker PID are absent, current246/two cleanup sources are checked, and its post-execution source scan0 is labelled as such. The strict RV predicate remains unchanged; a typed resource-accounting proposal is source-only and requires precise schema/model/delta evidence plus controls before any adoption. Production and original data are unchanged.

## 2026-10-14: finite resource-accounting controls pass locally

The [pure validator controls](../evidence/bortus-resource-accounting-controls-root-20261014.json) pass eight focused groups using the actual pinned public Pod producer. Independent checks verify the six current inputs, actual eight-test/no-skip/reaped result and both original process births absent; a later check confirms the reader absent. The candidate checks exact finite resource quantities, unchanged identity/spec/non-accounting status and restricted managedFields structure, rejecting unsupported maps, callbacks, malformed quantities and unrelated changes. Its possible 130m/150m CPU reports are a source-derived finite model, not observed values or proof of the failed 804 diagnostic cause. Every candidate result explicitly requires the original final security/source/runtime fences and grants no private authority. The original strict resourceVersion gate and 27 test oracles remain unchanged; no live calls, gate integration, checkpoint replacement, replay of those oracles or recovery acceptance occurs. The default source scan retains two public c9b562 source-hash references with zero unresolved findings and no suppression or replay; the one-file independent-reader scan passes. Observation-only collection of actual accounting and managedFields structure remains separate.

## 2026-10-14: accounting observations qualify without changing the recovery guard

The [observation-only controls](../evidence/bortus-accounting-observation-controls-root-20261014.json) pass all eighteen selected cases: fourteen unchanged helper/writer methods and four new actual checkpoint/failed-frame cases. Independent checks verify the 195 current inputs, literal no-skip/reaped result and original births absent; the reader is subsequently confirmed absent. The helper can project six bounded rational resource rows and thirteen managedFields structural path classes from the immutable baseline and already-failed frame. It returns no raw strings, field names, writer identities or private values and makes no extra API or guard calls. The single failure receipt remains capped at 4KiB. The exact strict57d0 resourceVersion gate, original setup/deadline/network/security checks and checkpoint remain unchanged; nineteen prior gate/baseline methods are preserved and not replayed. No transition acceptance, live recovery or production change follows. The 204-file default scan retains the exact unchanged malformed AAAA fixture with zero unresolved findings and no suppression/replay; the independent-reader source passes its combined scan. The subsequent precheckpoint readiness qualification is documented below; this observation-only result grants no readiness authority.

## 2026-10-14: precheckpoint readiness qualifies locally

The [precheckpoint readiness controls](../evidence/bortus-precheckpoint-readback-controls-root-20261014.json) pass all41 tests, retaining all33 original test methods byte-for-byte and adding eight actual-gate groups. Before the single checkpoint, the candidate waits within the existing deadline for the exact observed accounting state: allocated150m/requested130m CPU,256Mi memory,2CPU/1536Mi limits. The final guarded commit snapshot must still satisfy it before the exclusive receipt is written. Each snapshot captures only the bounded fixed accounting maps and binds them to that same UID/RV/IP; oversized unrelated status may still omit the optional full observation. After checkpoint, any RV difference continues to refuse at the unchanged line274 predicate. No cursor, baseline refresh, second commit, new lease, cgroup/writer inference or private authority is added. Fixture changes only add the exact ready maps and update source-hash bindings; original assertions remain unchanged. Independent proof verifies195 current inputs, literal41/no-skip/reaped results and both original births absent; the reader is subsequently absent. Default source scanning retains one unchanged malformed rejection fixture with zero unresolved findings and no suppression/replay. This is local qualification of an isolated candidate, not live recovery or a production guard change.

## 2026-10-14: Public851 final comparison and cleanup

The [851 diagnostic outcome and cleanup](../evidence/bortus-public-851-outcome-cleanup-root-20261014.json) retain actor exit1 after179.738seconds. The checkpoint is written and the seven real TCP network checks validate; the final compound snapshot/control identity comparison at gate line424 refuses. The failed-frame receipt contains no nested failed snapshot and does not establish which operand differs. No cause, postcommit RV exception, full live-holder proof or private recovery is inferred. Separate exact-UID cleanup exits0; the eight-GET independent observer confirms all five names/UIDs absent and2747 original/cleanup principal births absent. A no-child later check verifies246 original and two cleanup sources plus nine observer/query births absent; its own reader is subsequently absent. The first later reader1 is retained: two inherited855 counts were corrected to the actual8512747/179 in a distinct reader, with no actor, API or cleanup replay. Original data and production image remain unchanged.

## 2026-10-14: failed-sample diagnostics qualify locally

The [failed-sample observation controls](../evidence/bortus-sample-equality-controls-root-20261014.json) pass47 groups with all41 original test methods byte-identical. The gate’s only change binds the three existing return values inside the same final line424 comparison; removing those bindings restores the exact previous gate bytes. Call order, short-circuit behavior, seven TCP checks, strict line274 predicate, deadline, checkpoint and private stop remain unchanged. Failure-only diagnostics derive three operand equality results and13/5/5 numeric field bits from those already returned builtin tuples; skipped operands are explicit null, and no raw names, identities, RVs or addresses are emitted. Top-level key subclasses are rejected before lookup; malformed/oversized data is omitted within the existing single4KiB receipt. There are no extra API or guard calls. Independent proof checks196 current sources, the literal47/no-skip/reaped result and both original process births absent; its reader is subsequently absent. The source scan retains one exact malformed rejection fixture with zero unresolved and no suppression/replay. Earlier V1.1/V1.2 source-only variants remain unrun. This local qualification does not explain the historical851 operand failure or grant live recovery acceptance.

## 2026-10-14: Public836 comparison and cleanup

The [836 diagnostic outcome and cleanup](../evidence/bortus-public-836-outcome-cleanup-root-20261014.json) retain actor exit1 after181.087seconds. Its checkpoint and seven real TCP assertions complete, then the final comparison refuses: all13 holder fields match; control0 retains its name/namespace/UID/address but its RV differs; control1 is skipped by the original short circuit. The bounded999-byte failure receipt establishes that comparison only, not allocation changes, a writer/cause or the historical851 cause. Strict RV acceptance is unchanged. Separate exact-UID cleanup exits0; eight independent GETs confirm all five names/UIDs absent and2690 original/cleanup principal births absent. The later no-child check verifies246 original sources, two cleanup sources and nine observer/query births absent; its own reader is subsequently absent. The original2506-job incomplete registry remains honest. No private recovery, production image change or original-data retirement follows.

## 2026-10-14: Control accounting qualifies locally

The [control accounting diagnostics](../evidence/bortus-control-accounting-controls-root-20261014.json) pass55 local controls: all47 existing methods/assertions remain byte-identical, with eight new groups. The same already-guarded control GETs supply bounded immutable allocation/request/limit samples. Their checkpoint baseline becomes available only after the original successful commit; failure-only output distinguishes baseline, sample entry and evaluated end, with skipped controls explicit. No extra GET, guard execution, status readiness policy, guessed resource target, acceptance waiver or raw identity/value output is added. Both physical strict274 and424 comparison lines, all seven TCP checks, one checkpoint and original600-second lease remain exact. The single4KiB failure receipt drops new optional observations first when full. Independent qualification verifies197 current sources, literal55/no-skip/reaped results and the original two process births absent; its reader is subsequently absent. The208-file default scan retains one unchanged malformed rejection fixture with zero unresolved findings and no suppression/replay. This does not establish the allocation/writer cause of836 or grant live recovery acceptance.

## 2026-10-14: a729 field observation and cleanup

The [a729 outcome and cleanup](../evidence/bortus-public-a729-outcome-cleanup-root-20261014.json) retain actor exit1 after178.748seconds. The checkpoint and seven TCP assertions complete. All13 holder fields still match; control0 RV differs and control1 final comparison is skipped. Already-guarded control0 samples report requested CPU10m at checkpoint/entry, then that status field is absent; allocated10m CPU,32Mi memory and1000m/128Mi limits stay unchanged. This establishes the reported field difference, not a writer, cgroup explanation, historical836 cause or RV exception. Exact-UID cleanup exits0. Eight independent GETs confirm all five names/UIDs absent;2666 original/cleanup principal births are absent. The later no-child check verifies246 original sources, two cleanup sources,24 record pins and nine observer/query births; its own reader is subsequently absent. The original2475-job incomplete registry remains honest. Original data and production image are unchanged; private recovery remains unproved.

## 2026-10-14: stronger control-readiness qualification fails one new test

The [failed63-control receipt](../evidence/bortus-control-readiness-failed63-root-20261014.json) retains wrapper/test1 with62 passes and one new test failure. The candidate waits before the once-only checkpoint for the exact accounting shape observed after the prior live transition; missing requested-CPU status remains distinct from numeric0. The47 original core methods and entire strict sample remain raw-identical; the previously observation-only test36 explicitly changes two baseline expected rows, with fixture maps disclosed. New test49 incorrectly changes a control RV before a new sample and expects refusal; the existing guard compares control versions within each seven-TCP sample. This establishes an incorrect new-test setup, not a gate regression. A distinct correction will inject the change during that sample without altering the gate. Independent and later readers verify198 current sources, actual63/one failed and both original process births absent; the later reader is subsequently absent. No live candidate or private recovery follows this failed qualification. Production and original data remain unchanged.

## 2026-10-14: stronger control readiness passes63 local cases

The [corrected63-control qualification](../evidence/bortus-control-readiness-qualified63-root-20261014.json) passes all63/no skips under the original30/2/+1-second control lifecycle. Only new test49 changes relative to the failed candidate: its simulated RV change now occurs during the seven-TCP sample; its assertions remain identical, as do the other62 methods and the entire gate/helper bytes. The47 original core controls remain raw-identical; the stronger readiness fixture and test36 two baseline expectation changes remain explicitly disclosed. The gate waits before its one checkpoint for the exact observed control resource-status shape, with absent requested CPU distinct from numeric0; it adds no GET per existing readiness iteration. Strict holder274, the entire network sample424, all seven assertions, source/security fences and600-second live lease remain unchanged. Independent/later checks verify198 current sources and original actor/suite/post-reader absence; the later reader is subsequently absent. This qualifies local controls only. A fresh public-only functional test is being prepared; private recovery and production acceptance remain open.

## 2026-10-14: public control-readiness qualification passes; cleanup verified

The [d7ae public qualification and cleanup](../evidence/bortus-public-d7ae-outcome-cleanup-root-20261014.json) complete with actor/caller0 after230.785seconds under the unchanged600-second lease. All seven real TCP assertions pass against the same already-denied holder and separately reachable controls, with one immutable checkpoint and the strict version/sample guards intact. The exact63-control-qualified gate waits for the observed control accounting shape before committing. The3470 original registered jobs across14 shards are all0/reaped/absent with a complete registry; expected job UID remains execution context, not a recorded UID claim. Matched outcome0 confirms the finite public proof and explicit no-private scoped result. Separate exact-UID cleanup0 deletes three Pods before ConfigMap/policy without force or repeated DELETE; its180 jobs are complete. Eight independent GETs confirm all five names/UIDs absent and3652 original/cleanup principal births absent. Later no-child validation0 verifies246 original sources, two cleanup sources,24 record pins and nine observer/query births, followed by its own reader absence. The source scan retains four exact previously classified public findings with zero unresolved; cleanup11-file and later5-file scans are zero. This passes the public isolation qualification only: continuous enforcement, private Secret-map recovery, performance, security and production rollout remain unaccepted. Original data and backups remain intact.
