# Embedded operator mTLS adapter

`scripts/migration/bortus-operator-mtls.py` supplies fresh TLS options to the
[durable restore watcher](BORTUS-RESTORE-WATCH.md). It has no CLI and makes no
network request by itself. Only the reviewed embedded mTLS kubeconfig shape is
supported: one named cluster/context/user, current context referencing that pair,
embedded certificate authority, client certificate and unencrypted client key.
Named identifiers accept ASCII letters, digits, `_`, `.`, `-` and `@`, including
kubeadm's `user@cluster` context convention; references must still match exactly.
The server must exactly equal `https://192.168.0.4:6443`. Token, exec, auth-provider,
proxy, credential paths, TLS overrides, namespaces and unknown fields refuse.

The executor supplies an explicitly reviewed absolute source path to
`OperatorMTLSOptions(path)`. The object retains only that path. Every options call
opens each parent without following symlinks and reads the credential file afresh.
Parents must be root/operator owned with no group/world write; the final parent
must be operator owned. Owned 0755 parents are supported. The source must be an
operator-owned, single-link, regular 0600 file. Reads are nonblocking, bounded to
64 KiB, and require stable pinned file and parent identities before/after reading.
Atomic replacement between calls is allowed; replacement or modification during
a read refuses. No old credentials are used as fallback.

Strict UTF8 YAML uses the existing PyYAML 6.0.3 dependency. Before construction,
the adapter bounds parsing to 4,096 events and 12 nesting levels and refuses
anchors, aliases, explicit tags and multiple documents. Duplicate/non-string
mapping keys, malformed or unsupported shapes refuse. Embedded data must be
canonical base64 and at most 16 KiB per decoded certificate authority, client
certificate or private key. Only PEM certificate blocks and unencrypted PKCS8,
RSA or EC private-key blocks are supported. Encrypted-key formats refuse; the
TLS password callback always raises a fixed failure and cannot prompt.

A fresh `SSLContext(PROTOCOL_TLS_CLIENT)` loads only the embedded CA, verifies
certificate/hostname, and requires TLS 1.2 or newer. Direct construction avoids
environment-driven SSL key logging. Client material is loaded from owned Linux
memfds, 0600 and close-on-exec, sealed against write/grow/shrink, referenced only
through `/proc/self/fd`. All owned descriptors close before return or refusal.
There is no disk plaintext export, credential cache, response logging or raw
YAML/TLS/filesystem error propagation. The returned context necessarily contains
in-memory client authentication for its owned request; it must not be reused as
a cross-request credential cache. The collector invokes the options provider
for every connection.

The public callable raises a fresh fixed failure outside exception handlers,
dropping underlying parser/TLS exception chains and releasing plaintext locals
before the public traceback exists. Merely suppressing exception display would
still retain YAML input buffers in parser marks. This is reference release and
bounded transient handling, not a claim of Python heap zeroization.

The local fixtures use disposable certificates/config files and owned loopback
HTTPS/mTLS only; they override the expected origin solely in test scope. They
never inspect the operator credential file or contact Kubernetes. Local adapter
qualification does not establish approved live operator access, fresh source or
consumer fences, executable restoration, image/admission checks, authenticated
archive/whole-row equality or migration acceptance. Root owns those live gates.

Primary interface references are [Python 3.14 SSL](https://docs.python.org/3.14/library/ssl.html),
[Python 3.14 memfd support](https://docs.python.org/3.14/library/os.html#os.memfd_create),
and [PyYAML 6.0.3 constructors](https://github.com/yaml/pyyaml/blob/6.0.3/lib/yaml/constructor.py).

## Coordinator integration and scoped live access

The separate `bortus-restore-metadata.py` read-only adapter uses the same fresh
options provider for each TLS connection. Its fixed scope is named BORTUS PVC/Pod,
cluster StorageClass/PV/Node and Longhorn Volume/Backup/Engine/Replica GETs, plus complete PV,
BORTUS Pod and Longhorn Engine/Replica lists. The source-fence revision also adds
fixed BORTUS Deployment/ReplicaSet, Flux-system HelmRelease/Kustomization and
Longhorn Snapshot/BackupTarget GETs, plus complete StorageClass and BORTUS PVC
lists for the original preflight's target-absence checks. It exposes no Secret endpoint,
mutation, proxy, redirect, retry, connection pool or credential fallback.
Reads have an absolute finite deadline of at most 300 seconds, a 30-second socket
timeout and an 8-MiB body cap; late reads refuse. Strict UTF8 JSON rejects duplicate
keys/nonfinite constants and bounds tree depth/nodes/strings. Lists require the
correct API/kind, opaque collection resourceVersion, no continuation/remaining
items, at most 10,000 objects and unique names/UIDs with the expected namespace.
Public errors contain fixed codes, with underlying response/parser frames dropped.
These are fresh individual reads, not an atomic source or health snapshot. The
executor must pass them through the full identity/consumer/restore fences.
Nineteen original disposable loopback TLS tests pass, including credential freshness,
revocation, fixed scope, malformed/oversized/incomplete replies, a slow trickle,
late-connect refusal before dispatch and independent owned closure. A closure
failure drops even a successfully parsed response before the public refusal.
The first run's three expected-cancellation fixture teardown failures remain in
the actual tool record; the corrected fixture suppresses only expected peer
cancellation, without weakening production assertions. Actual executor/live use
remains pending.

The subsequent fixed named StorageClass read allows the executor to independently
check the admitted restore class after POST. Its separate twentieth regression covers the
exact storage API path/kind and rejects namespace escapes. This scoped
extension passes all 20 focused tests with frozen inputs and an actual zero exit;
the earlier 19/350 receipts remain bound to their original sources. See the
[extension evidence](../evidence/bortus-restore-metadata-storageclass-20261011.json).

The later source-fence extension retains strict complete-list limits for the two
additional inventories, with no continuation or partial acceptance. Earlier
receipts describe their original, narrower scopes; current source qualification
is required before executor use.

`bortus-restore-source.py` owns nofollow read-only descriptors for a reviewed
mode-0600 checkpoint journal under pinned nonwritable directory anchors. Each
invocation checks the exact file identity and SHA before and after fresh scoped
TLS reads. It reuses the original preflight evaluator with the same absolute
deadline and independently validates the original source/consumer, completed
cold snapshot/full backup, class and alternate node. `prepare` additionally
checks complete target-absence inventories; `check` repeats source fences after
target creation without hiding or adopting target resources. Only selected
identities and checkpoint/ciphertext bindings cross the check boundary. Fixed
refusals drop private parser/response frames. Descriptor cleanup is explicit.
This library has no CLI, mutation, database/Secret read or restore acceptance;
local qualification passes 12 actual loopback TLS/ownership/privacy cases and
365 combined root cases without skips on frozen inputs. The target-absence
preflight and repeat-source checks remain separate; neither authorizes an image,
mutation or restore by itself. See the
[source-fence integration evidence](../evidence/bortus-restore-source-integration-20261011.json).

Native review subsequently found a just-opened directory FD could escape cleanup
if the following `fstat` failed before anchor registration. The retained actual
13-case regression run reproduced one leaked descriptor. Directory descriptors
are now registered immediately after `open`, before any fallible identity check;
anchor validation remains separate. All 13 corrected source-fence tests pass on
frozen inputs with an actual zero exit. The original 12/365 receipts continue to
describe their earlier sources; see the
[constructor correction evidence](../evidence/bortus-restore-source-init-correction-20261011.json).

The native immutable handoff at `6e4e9668` passes 30 focused and 179 combined
cases. Its default scanner exits 1 for one individually reviewed invalid public
PEM fixture, not zero findings; original errors and review remain retained.
Root verified the selected files and unchanged dependencies, then reproduced a
real operator compatibility refusal: the kubeadm context contained `@`. The
identifier correction and actual local mTLS regression pass in all 193 current
root helper cases. The original failed live probe is retained and sent no API
request.

At 06:33 UTC, the corrected adapter performed a complete bounded live Longhorn
LIST (39 objects, 213,701 bytes, one page) followed by an HTTP200 watch handshake
at the exact collection resourceVersion, using TLS1.3 and two fresh options
calls. Both owned connections/responses closed. No watch frames were consumed,
no Secrets read and no cluster mutation performed. This proves scoped operator
transport access only: durable live history, restoration and data/image release
acceptance remain open. Exact hashes, test terminals, the initial refusals and
scope limits are in [integration evidence](../evidence/bortus-operator-mtls-integration-20261011.json).
