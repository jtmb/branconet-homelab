# Native Kubernetes1.37.2 security patch

This source targets the actual existing `/usr/local/bin` installation. It does
not add Kubernetes APT packages/repositories, change package holds, shadow old
binaries, or modify the active kernel maintenance source. Complete kernel202
and its recovery gates before this separate operation.

Read-only discovery on all three original nodes found native kubeadm/kubelet/
kubectl, root:root0755, regular files with one link, and no corresponding dpkg
packages or APT candidates. Their original bytes match across nodes:

| Binary | Original SHA256 | Bytes |
| --- | --- | ---: |
| kubeadm | 087b6340dcea496f2cde2b3888ecd414354c08a0aceabd6b7ca195cccb66ecd3 | 74576034 |
| kubelet | cee008c1640c3b41820ef31d35b3cffc132b0c4b78c288be2b8022ebc7aa8293 | 61243657 |
| kubectl | 65691ff77eb6fa44c908b77a1082c9f092c3b9733b5cefabec0d1104890e21a8 | 61886626 |

Kubelet's current unit fragment is `/etc/systemd/system/kubelet.service` on all
nodes. The rejected APT-only draft's exact helper is retained as
H/kubernetes1372-apt-draft.patch; its original source/check controls remain in
H/kubernetes1372-source-review.json. It was never applied.

## Rationale and native kubeadm semantics

Kubernetes1.37.2 was released2026-10-28T04:37:53Z. It updates the official Go
build from1.26.8 to1.26.10, including crypto/x509 Certificate.Verify mitigation
for CVE-2026-111943 / GO-2026-6809. Exploitability depends on trust chains; this
is a relevant same-minor security patch, not a clean vulnerability verdict.

- https://github.com/kubernetes/kubernetes/releases/tag/v1.37.2
- https://github.com/kubernetes/kubernetes/blob/master/CHANGELOG/CHANGELOG-1.37.md#v1372
- https://github.com/kubernetes/kubernetes/pull/143204
- https://pkg.go.dev/vuln/GO-2026-6809
- https://go.dev/doc/devel/release#go1.26.10

Upstream1.37.2 rejects mixing `--config` with the etcd/certificate/patch CLI
flags. The role therefore uses their explicit supported v1beta4 config
 equivalents: `etcdUpgrade: false`, `certificateRenewal: false`,
`imagePullPolicy: Never`. No force or ignored-preflight option is used.
The source reads these fields through ValueFromFlagsOrConfig; staticpods.go
conditions etcd upgrade and certificate renewal on them.

The actual first native invocation stopped in preflight: the bundled CoreDNS
migration table does not recognize the independently patched CoreDNS1.15.0.
Kubeadm1.37.2 targets the older1.14.6. The addon phase stays skipped; the supported
`apply.ignorePreflightErrors` names only `CoreDNSUnsupportedPlugins` and
`CoreDNSMigration`. Every other native check remains fatal. A separate maintained
guard compares the exact current DNS declarations, UIDs, image, ConfigMap and
`kube-dns` Service against the preserved public baseline before and after every
host, and requires the original desired DNS replicas Ready. Actual in-Pod
internal/external DNS lookup also passed. This exception prevents an unused
migration check from proposing a DNS downgrade; it is not a general compatibility
certification. The protected original failure and dry-run diagnosis remain intact.

`upload-config/kubelet` is separately skipped as well as `kubelet-config`:
upstream implements ConfigMap upload and local-file rewriting in distinct phases.
The kubeadm configuration's Kubernetes version record can change; the original
kubelet ConfigMap, local files and all other addon data remain protected.

- https://github.com/kubernetes/kubernetes/blob/v1.37.2/cmd/kubeadm/app/cmd/phases/upgrade/apply/preflight.go
- https://github.com/kubernetes/kubernetes/blob/v1.37.2/cmd/kubeadm/app/cmd/phases/upgrade/apply/uploadconfig.go
- https://github.com/kubernetes/kubernetes/blob/v1.37.2/vendor/github.com/coredns/corefile-migration/migration/migrate.go

- https://github.com/kubernetes/kubernetes/blob/v1.37.2/cmd/kubeadm/app/apis/kubeadm/validation/validation.go
- https://github.com/kubernetes/kubernetes/blob/v1.37.2/cmd/kubeadm/app/apis/kubeadm/v1beta4/types.go
- https://github.com/kubernetes/kubernetes/blob/v1.37.2/cmd/kubeadm/app/cmd/upgrade/apply.go
- https://github.com/kubernetes/kubernetes/blob/v1.37.2/cmd/kubeadm/app/cmd/upgrade/node.go
- https://github.com/kubernetes/kubernetes/blob/v1.37.2/cmd/kubeadm/app/phases/upgrade/staticpods.go

## Finite execution and preservation

The new `playbooks/kubernetes-security-patch.yml` first qualifies ALL THREE
hosts. The master runs first; worker2 and worker1 follow serially only after
master recovery. Default apply is false. Native binary installation is never
performed by capture/qualification. Check mode never applies.

The coordinating operator stages official standalone binaries, their checksum,
.sig and .cert files under the one existing F-backed task root. The controller
rehashes actual blobs and reruns cosign verify-blob with the exact publisher
identity `krel-staging@k8s-releng-prod.iam.gserviceaccount.com` and issuer
`https://accounts.google.com`; no bypass flags are accepted. Cosign's executable
SHA256 and bounded existing cache directory are authority fields. Its local
cache stays in H; no tooling/dependency install is part of this role.

Official procedure:
https://kubernetes.io/docs/tasks/administer-cluster/verify-signed-artifacts/

Before ANY replacement, preserve the raw bytes of every installed native binary
in H, deduplicated by original SHA256. The authority rehashes these backups and
binds each original node's path/size/owner/group/mode/mtime/xattr hash. Retain
these original backups as required rollback inputs; no cleanup path deletes
them. Inode/ctime necessarily change during atomic replacement; ownership,
mode, mtime, xattrs and original raw bytes remain independently protected.

Each node stages only these same-filesystem paths, where SHA is the qualified
new artifact SHA256:

- `/usr/local/bin/.kubernetes1372-kubeadm-SHA.new`
- `/usr/local/bin/.kubernetes1372-kubelet-SHA.new`
- `/usr/local/bin/.kubernetes1372-kubectl-SHA.new`

Owner is this cluster security task, native owner root:root. Set each stage's
mode, mtime and xattrs to that node's recorded original metadata. Originals
must be single-link regular files, without path/symlink redirection. The stage
must be newly created by this task; never overwrite an existing unexplained
path. Before each mutation the helper rechecks exact installed/staged hashes,
metadata and filesystem, fsyncs the new file, performs os.replace at the
original path, fsyncs the parent directory and verifies the result. Kubeadm is
replaced first; kubelet/kubectl only after native cluster/node upgrade, followed
by explicit kubelet restart. Actual /proc/MainPID/exe bytes, binary versions and
Go1.26.10 buildinfo are checked after restart. Package state/holds are untouched.

Fresh native filesystem gates preserve15GiB available AND25percent free plus
512MiB. The conservative remaining peak adds128MiB plus original+new sizes of
every remaining swap, without discount for already allocated staging. Parent
must budget stage copies before writing them and retain these same floors.

Kubeadm regeneration is constrained by JSON patches from each original static
Pod's exact spec and metadata, changing only its approved native image digest.
The etcd manifest, certificates, kubeconfigs, kubelet configuration/flags,
independent containerd config and kubelet/containerd-k8s unit fragments/drop-ins
are checked by bytes and metadata. Unit enablement properties remain identical.
No private key bytes are printed or stored in these receipts.

Addon/kubelet-config/kubeconfig phases are skipped; bootstrap-token is also
skipped on master. Existing CoreDNS and kubelet config stay intact. Kube-proxy
receives only a resourceVersion-tested image JSON patch. Its UID and every other
spec field are compared. API server version/Go toolchain, actual Ready native
image IDs, ConfigMap UIDs/data and only the expected kubeadm version-record
change are checked after every host recovers.

Original recovery_guard/pod_guard and exact existing emptyDir tuples are reused.
Normal eviction preserves every PDB and block-if-contains-last-replica. No force
eviction, automatic rollback or forced uncordon exists. The unchanged current58
checkpoint still enforces original58claims/PVs,44volumes (28healthy active and
16original offline), controller specs, regeneration source hashes, native backup
identity/freshness, authenticated encrypted control-plane archive and NAS proof.
The adapter normalizes ONLY the exact authorized kube-proxy image transition.
Publish the approved FlareSolverr change BEFORE capturing a NEW current58
manifest; never edit the earlier kernel checkpoint in place.

## Authority schema and operator inputs

Top-level schema is `kubernetes1372-native-authority-v1`:

- capturedAt: UTC ISO timestamp; nodeUIDs: original three-node name→UID map.
- checkpoint: {path,sha256} for the NEW accepted current58 manifest.
- proxyBeforeImage: exact currently installed original1.37.1 image reference.
- signatureTool: {path,sha256,cacheDirectory}; existing verifier and existing
  task-owned local cache, with no user HOME/cache fallback.
- vendorScan: {summary:{path,sha256},controllerSHA256}, binding the existing
  kubernetes1372_vendor_preload/files/controller.py and its original summary.
- binaries: exactly kubeadm,kubelet,kubectl, with entries described below.
- images: exactly kube-apiserver,kube-controller-manager,kube-scheduler,kube-proxy.

Every binary entry has:

```json
{
  "url": "https://dl.k8s.io/release/v1.37.2/bin/linux/amd64/NAME",
  "sha256": "64 hex", "bytes": 123,
  "blob": {"path": "actual controller binary", "sha256": "same64hex"},
  "checksum": {"path": "official .sha256", "sha256": "file hash"},
  "signature": {"path": "official .sig", "sha256": "file hash"},
  "certificate": {"path": "official .cert", "sha256": "file hash"},
  "signatureVerification": {"path": "actual verifier receipt", "sha256": "file hash"},
  "scan": {"path": "actual native binary scan receipt", "sha256": "file hash"},
  "reviewedVulnerabilityIDs": [],
  "originalByNode": {"masternode": {"path": "/usr/local/bin/NAME", "sha256": "old64hex", "bytes": 123, "uid": 0, "gid": 0, "mode": 493, "mtimeNs": 123, "xattrsSHA256": "64hex"}},
  "originalBackups": {"masternode": {"path": "deduplicated raw old binary", "sha256": "old64hex"}},
  "prestage": {"masternode": {"path": "actual native staging receipt", "sha256": "file hash"}}
}
```

Include ALL THREE nodes in originalByNode/originalBackups/prestage. Path/hash
objects resolve without symlink redirection inside the existing F root; original
backups can share one file for identical bytes. Signature receipts contain
subjectSHA256,exitCode0,completedAt,exact certificateIdentity/certificateIssuer,
and bypassFlagsUsed:false. The role independently re-verifies them cryptographically.

Native binary scan receipts contain scanner:trivy,subjectSHA256,exitCode0,
completedAt,scanComplete:true,suppressionUsed:false,
inputHashesReverifiedAfterScan:true,knownExploitedCVEs:[], and
report:{path,sha256}. Report can be original full Trivy schema2 JSON or its
original complete results array. At least one actual stdlib package must show
v1.26.10; targetCVE111943 must be absent. Every remaining HIGH/CRITICAL ID needs
an explicit reviewedVulnerabilityIDs entry; this never means zero exposure.

Binary staging receipts contain capturedAt,node,nodeUID,exact native stage path,
sha256,bytes,ownerTask:kubernetes1372-security-patch,newlyCreated:true. These
metadata attestations are followed by actual root-owned file/metadata/hash
checks on each node before mutation.

Each image entry has reference `registry.k8s.io/NAME:v1.37.2@sha256:AMD64`,
rootDigest,amd64Digest,configDigest, and prestage node→{path,sha256}. Each image
stage receipt contains capturedAt,node,nodeUID,runtimeEndpoint
`unix:///run/containerd-k8s/containerd.sock`,amd64Digest,configDigest,
tag `registry.k8s.io/NAME:v1.37.2`,present:true. Existing aliases.py establishes
these12 exact aliases after protected native staging. The role reads CRI tags,
config IDs and repo digests again. Kubeadm's pull policy is Never.

Image qualification directly reuses the existing vendor measurement function:
original scan/result/source hashes, complete diffID budgets, live registry
metadata and exact residual21High/zeroKEV remain bound. No duplicate OCI data
or fabricated scan wrapper is needed. Authority/scans/staging and checkpoint
retain their six-hour freshness bounds.

## Concrete source capture and invocation

All local outputs remain under the existing H on F. For each original host,
this command reads public binary metadata only, without sudo or any writes:

```sh
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes \
  -i /home/brajam/.ssh/id_ed25519 -p2002 james@192.168.0.4 \
  /usr/bin/python3 -B - capture < "$P/native_binaries.py"
# Repeat192.168.0.5 and.6; save each unique metadata receipt under H.
```

After the coordinating operator has preserved raw originals, completed native
binary/image staging and fresh checkpoint evidence, assemble these existing
inputs: binary-evidence.json with {binaries,signatureTool}; image-staging.json
with {images:{component:{node:{path,sha256}}}}. Then:

```sh
R='/mnt/c/Users/james/.codex/worktrees/cluster-headroom-security-tls/kubernetes migration'
F='/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025'
H="$F/platform-upstream-review-20261027/autonomous-hardening-20261028"
P="$R/k8s-rewrite/ansible-playbook/roles/kubernetes_security_patch/files"
PY='/home/brajam/.local/share/branconet-migration/venv/bin/python'
set -C # refuse to overwrite an existing/running authority
"$PY" -B "$P/capture.py" \
  --checkpoint "$H/kubernetes1372-current58.json" --checkpoint-sha256 REVIEWED_CHECKPOINT_SHA \
  --binary-evidence "$H/kubernetes1372-binary-evidence.json" --binary-evidence-sha256 REVIEWED_BINARY_EVIDENCE_SHA \
  --image-staging "$H/kubernetes1372-image-staging.json" --image-staging-sha256 REVIEWED_STAGE_SHA \
  > "$H/kubernetes1372-authority.json"
# Review the concrete bytes and record their hash, then use that exact value:
"$PY" -B "$P/authority.py" --manifest "$H/kubernetes1372-authority.json" --sha256 REVIEWED_AUTHORITY_SHA
"$PY" -B "$P/checkpoint.py" --manifest "$H/kubernetes1372-authority.json" --sha256 REVIEWED_AUTHORITY_SHA
```

The existing protected Ansible launcher supplies these public variables to
playbooks/kubernetes-security-patch.yml:

```yaml
kubernetes_security_patch_apply: false # complete qualification first
kubernetes_security_patch_manifest: ABSOLUTE_H/kubernetes1372-authority.json
kubernetes_security_patch_manifest_sha256: REVIEWED_64_HEX_SHA
kubernetes_security_patch_receipt_dir: ABSOLUTE_H/kubernetes1372-recovery-unique
ansible_ssh_private_key_file: /home/brajam/.ssh/id_ed25519
ansible_ssh_common_args: -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/home/brajam/.ssh/known_hosts
```

Receipt suffix uses lowercase letters/digits/hyphens. Configure all Ansible
local temp/HOME and TMP/TEMP/TMPDIR under the declared H root before invoking;
privilege input stays in the established RAM-only launcher. Set apply true only
after the same authority's full preflight passes. No signature bypass, weaker
floor or version substitution is supported.

## Outputs, cleanup and acceptance

Controller recovery receipts retain original static specs/metadata, file hashes,
unit/config identity, holds and exact raw-binary backup references. No Secret
values or certificate/key contents enter these receipts. Native kubeadm needs a
unique root0700 directory under `/etc/kubernetes/tmp`, outside watched manifests.
Its exact inventory/hash and regeneration recipe are saved before use. After
successful host/runtime checks, only that generated directory is removed after
hash, owner, exact path and process/fd/map/mount checks. Failures retain the
exact target and reason, without stopping workloads or bypassing a denial.
Original kubeadm recovery backups are never touched.

Native stage files are consumed by atomic rename; this is NOT a claim of freed
filesystem bytes. Any remaining task-created stage is reconciled only after
proof of exact ownership/hash and absence of active references. Pre-existing
files and original raw backups stay protected. Receipts distinguish measured
removals, consumed stages and retained exceptions; no Windows recovery is
inferred from Linux bytes. Local syntax scratch is removed after its child exits.

Source controls/syntax are not signature verification, actual staged-byte
acceptance or live rollout. Failure after a replacement can leave a partially
upgraded host; stop there with preserved original receipts/bytes and normal
isolation. No automatic rollback, force eviction or next-host continuation is
attempted. The one-shot original master capture deliberately rejects a partial
rerun rather than silently accepting changed source authority.
# Native controller staging (source only until explicitly executed)

## Finite native maintenance runner and successor checkpoint

### Accepted concurrent Ingenium successor

The backup runner, Windows ciphertext-copy helper and checkpoint capture now
accept the additive generation `kubernetes1372-current-ingenium`. Existing
generation behavior and original manifests remain unchanged. The new paths are:

- `H/kubernetes1372-current-ingenium-control-plane-backup`
- `H/kubernetes1372-current-ingenium-control-plane-nas-proof.json`
- `H/kubernetes1372-current-ingenium-current58-manifest.json`

Use `run-kernel-checkpoint.py control-plane --generation
kubernetes1372-current-ingenium`, then the Windows copy helper with that same
generation. Capture additionally requires `--ingenium-transition-evidence PATH`
and `--ingenium-transition-evidence-sha256 SHA256`. All new files are exclusive;
old encrypted backups, NAS proof and original binary ownership bindings remain
protected. No source preparation step executes those commands.

The evidence schema is `kubernetes1372-current-ingenium-spec-transition-v1`, with:

- `identity`: kind `Deployment`, namespace/name `ingenium`, UID
  `399abce7-cf4e-49d5-a743-a3e647390d9c`.
- `beforeSpec`, `afterSpec`: `{path, sha256}` references to complete Deployment
  spec JSON objects inside H.
- `chartEvidence`: `{path, sha256}` reference to the coordinator's actual
  chart/pipeline comparison JSON; `chartsRevision`: its complete 40-hex commit.
- `expectedImage`:
  `docker.io/jtmb92/ingenium@sha256:b9484ea1ee956dd776200b8251886464364a6083b403b5d63447d736c94c5c64`.
- `expectedChecksumAnnotations`: the exact `checksum/bootstrap-installer` and
  `checksum/lan-gateway` SHA256 values from that reviewed chart.
- Optional `reviewedCommands`: entries keyed only by `containers/ingenium` or
  `initContainers/prepare-bootstrap-ownership`, each with exact `before` and
  `after` command arrays. Omit it if commands did not change. Existing ephemeral
  regeneration verification still independently enforces its original command.

The predecessor is the immutable `kubernetes1372-current58-manifest.json`, SHA256
`7de0db518a9d913ff4efd9b4fc36bc9667956daaeba7f07417e21ea870a99902`. Ingenium's exact
old/new spec hashes are pinned to
`5ede791bee9db31642cf0e2c8d011eeba8412cadc4890bfd1f3a804dd6fb403e` and
`5126c66d81b7111d52b72a09cab676fba71dc12d29d07bd0d403333b247ceb10`.
Only the two existing container images, named checksum annotations and explicitly
reviewed commands can change. Full structural comparison protects everything
else, including arguments, principals, mounts, resources, node selection and
environment references. All other 218 rows, all original node identities and
ephemeral source identities remain exact; backup freshness and native/NAS
validation remain mandatory.

`scripts/migration/run-kubernetes-security-patch.py --manifest ABSOLUTE_H_AUTHORITY
--manifest-sha256 SHA256` runs the existing complete native preflight by default.
Only explicit `--apply` enables its existing guarded control-plane-first and
serial-worker upgrade. Both modes consume the existing protected password line
from stdin before children. Neither package sources nor alternate installation
paths are introduced. The manifest must be an exact file directly under H with
the supplied SHA256. F and Windows C each retain the existing 17 GiB controller
launch guard; node data/replica/disk gates remain in the role.

The runner declares per-run ownership before Ansible starts. Temporary state is
under `H/kubernetes-maintenance-scratch/RUN_ID`, durable ownership/results under
`H/kubernetes-maintenance-receipts`, and protected role recovery records under
`H/kubernetes-recovery-RUN_ID`. A short `/proc/PID/fd/FD` alias keeps AF_UNIX
socket paths short while every temporary byte stays under the original F root.
The credential remains RAM/environment-only for the short-lived Ansible process
and is removed in `finally`. After multiprocessing children exit, cleanup removes
only that invocation's scratch if containment, no symlinks, no mount and process
reference checks pass; otherwise its exact path/reason is retained in the result.
Raw binaries, authority, recovery and result receipts are never scratch.

`capture-kernel-checkpoint.py` still defaults to its original kernel behavior.
Its additive `--generation kubernetes1372` uses
`H/kubernetes1372-control-plane-backup`,
`H/kubernetes1372-control-plane-nas-proof.json`, and exclusively creates
`H/kubernetes1372-current58-manifest.json`. It preserves all original native
backup prefix/count/freshness assertions and the current58 validator schema.

The new generation requires `--flare-transition-evidence PATH` and
`--flare-transition-evidence-sha256 SHA256`. This evidence must be inside H:

```json
{
  "schema": "kubernetes1372-flare-spec-transition-v1",
  "identity": {
    "kind": "Deployment", "namespace": "plex", "name": "flaresolverr",
    "uid": "7a6239d9-8a48-40ec-9480-dd4e8667f695"
  },
  "beforeSpec": {"path": "ABSOLUTE_H_SPEC_JSON", "sha256": "SHA256"},
  "afterSpec": {"path": "ABSOLUTE_H_SPEC_JSON", "sha256": "SHA256"}
}
```

Both referenced JSON files contain complete Deployment **spec objects**. Their
canonical digests must match the immutable predecessor and current live rows.
The predecessor is `kernel-current58-manifest-concurrent-ingenium.json`, pinned
to SHA256 `d7003cd81b0fcf7ee0596d2abb603775cb52fb19ef1ab08da976e4ff022c1d22`.
Independent structural comparison allows only the exact reviewed Flare Pod and
container security contexts. Its UID and all other 218 projected rows remain
identical, including original node, PVC, PV, Longhorn and controller identities,
volume states and every other spec hash. Ephemeral source identities also remain
exact. The old manifest is never rewritten. These source additions were parsed
only; no checkpoint capture, maintenance run or host write was performed.

`k8s-rewrite/ansible-playbook/roles/kubernetes_security_patch/files/staging.py`
provides four finite controller phases: `capture`, `backup`, `stage`, and
`observe`. Every invocation requires `--checkpoint ABSOLUTE_F_PATH` and
`--checkpoint-sha256 SHA256` for the new current58 checkpoint. Capture binds its
original node UIDs to the three live nodes, strict known SSH host keys, root
filesystem UUID/device, boot ID, native original bytes/metadata, kubelet unit
hash, hold selections, and native containerd version. Capture refuses existing
stage paths. A boot or protected origin change requires investigation; it does
not silently refresh the baseline.

All generated controller files belong to `kubernetes1372-security-patch` under
`H/kubernetes1372-native-stage` on the existing F mount. Capture creates that
directory exclusively. It writes the ownership/regeneration/consumer record
before observations. The immutable vendor authority is
`H/kubernetes1372-binaries/authority.json`, SHA256
`bb96c82be216747db666b2ef9d10a927688df7e7119b6f3f2775605b6d5e9859`.
It is never rewritten, and its pending vulnerability review remains pending.

Run the controller with the existing venv Python and `-B`, in this order:

```text
python -B staging.py capture --checkpoint /absolute/F/checkpoint.json --checkpoint-sha256 SHA256
python -B staging.py backup --checkpoint /absolute/F/checkpoint.json --checkpoint-sha256 SHA256
python -B staging.py stage --checkpoint /absolute/F/checkpoint.json --checkpoint-sha256 SHA256
python -B staging.py observe --checkpoint /absolute/F/checkpoint.json --checkpoint-sha256 SHA256
```

Only `stage` consumes an existing protected password line on stdin, before any
SSH. Do not put that password in argv, shell history, environment, files, or
receipts. Its remote memory-only launcher separately authenticates sudo with
only the password line, then uses `sudo -n` for the payload. Cached sudo and
NOPASSWD cannot leak an unconsumed password into the binary stream. No binary is
executed and no service, installation path, package, runtime, or hold is changed.
The optional `playbooks/kubernetes-native-stage.yml` exposes the same phases via
`kubernetes_native_stage_phase`, `kubernetes_native_stage_checkpoint`,
`kubernetes_native_stage_checkpoint_sha256`, and the existing RAM-protected
`kubernetes_native_stage_password` variable (stage task has `no_log`).

Backup captures all three sources before and after each bounded download,
deduplicating their identical installed SHA256 bytes into three
`original-SHA256` files (197,706,317 bytes total). It checks Windows C free space
and F free space before download. These are required original rollback sources,
not disposable builds. A failed backup retains its partial file and intent;
no code deletes or replays it. Existing unrelated originals remain untouched.

Before its first node write, stage freezes all three node observations and all
three passing budgets. Each host reserves block-rounded missing stage bytes,
1 MiB metadata, and the native role's conservative remaining replacement peak
(128 MiB plus all original and new file sizes). Both the 15 GiB available-space
floor and 25% capacity plus 512 MiB free-space margin remain mandatory. Each
individual write repeats its host's identity/original/budget checks.

The only node outputs are the nine exact paths
`/usr/local/bin/.kubernetes1372-NAME-SHA256.new`, for the three named binaries on
the three original nodes. Each inherits its source UID/GID/mode/mtime/xattrs and
is created with O_EXCL/O_NOFOLLOW, bounded streaming SHA256 verification, file
fsync and directory fsync. Its last consumer is `native_binaries.py`'s guarded
atomic replacement. Regeneration is from the retained qualified vendor blob,
but an uncertain recorded write is never retried or overwritten. The original
path is rehashed before and after the write. A controller intent is durable
before SSH; a separate after receipt follows successful completion.

`observe` performs no remote writes. It can qualify all nine exact completed
authored paths even if an SSH completion reply was lost. Missing or partial
files refuse export; the stage phase cannot be rerun after its global intent.
Preserve those exact paths and receipts for bounded reconciliation, never
delete them to make a retry pass. On complete observation it writes new
`binary-evidence.json` with the actual raw original backups and per-node
prestaging receipts. It preserves the vendor's signature and scan references
and empty `reviewedVulnerabilityIDs`; the coordinator must provide its explicit
reviewed acceptance separately before the full authority can pass. Existing
source-only checks do not establish any node staging or upgrade success.
