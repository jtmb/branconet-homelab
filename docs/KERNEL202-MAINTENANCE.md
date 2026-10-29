# Finite kernel202 maintenance profile

`playbooks/kernel-security-maintenance.yml` in `k8s-rewrite/ansible-playbook`
adds an opt-in `current58-kernel202` profile. Default `security_maintenance`
behavior remains `legacy30`, including its original thirty-volume checkpoint
and attached/healthy requirements. This source preparation is not rollout or
kernel vulnerability closure. Existing indexes were last observed October27.

The separate `kernel_maintenance_mode=refresh` updates signed APT indexes only
on all three nodes. Default mode `preflight` only qualifies the exact package
transaction. `apply` requires `kernel_maintenance_apply=true`, existing
`security_maintenance_backup_verified=true`, a reviewed manifest path and its
`security_maintenance_checkpoint_sha256`, and the existing task-owned
`security_maintenance_recovery_receipt_dir`. Reboot requires the separate
`kernel_maintenance_reboot=true`; otherwise installation is not kernel activation.
Supply these through the existing protected Ansible launcher. Never put a sudo
password, native Secret value or private backup key into arguments or source.

Workers run serially in inventory order; master runs last and requires both
workers to have completed recovery in the same invocation. Partial host limits
are refused. The profile preserves ordinary eviction/PDB handling and Longhorn's
`block-if-contains-last-replica`; it never forces deletion or relaxes replicas.
Existing rescue retains the cordon/failure state rather than automatically
uncordoning. Zero kubelet shutdown grace is not a substitute for a clean drain.

## Exact transaction

The profile clears the broad Ubuntu package list, disables stock-runtime
retirement, requires already-active containerd2.4.2 and uses the existing exact
optional-package install step. Only three metas (`linux-generic`,
`linux-image-generic`, `linux-headers-generic`) at `5.15.0.202.174` and five202
image/modules/modules-extra/headers packages at `5.15.0-202.212` are accepted.
Master additionally installs the390 module/meta/objects/signatures packages for
202 at `5.15.0-202.212`. Its observed active390.157 module is preserved and
`modinfo -k 5.15.0-202-generic` must confirm390.157 before reboot. No driver
branch/license change, Pro attachment, Docker/containerd package upgrade,
autoremove or old-kernel deletion is included. Installed198 remains required.
The exact simulated transaction must add/configure nothing outside this set.

## Current accepted checkpoint

Run `roles/security_maintenance/files/kernel_checkpoint.py --capture` with the
existing controller Python and redirect the metadata draft only into the existing
F-backed task root. Capture is read-only and intentionally supplies empty backup
fields; it is not a qualified checkpoint. Before hashing the final JSON, review
the original identities against the accepted current baseline and fill:

- `nativeBackups`: exactly28 objects with `volume`, `volumeUID`, backup `name`,
  backup `uid`, and `statusSHA256`. Use the guard's `backup_identity(status)`
  projection, then SHA256 over JSON encoded using
  `sort_keys=True,separators=(',', ':')`. It pins the durable backup URL, volume,
  snapshot, size, dates, target, compression, labels and completion state.
  Transient reconciler owner/replica address/lastSyncedAt are intentionally not
  pinned because normal node maintenance can change them.
- `controlPlane`: `receipt`, `receiptSHA256`, `archiveSHA256`, and exact `source`
  object from the completed existing `control_plane_backup` receipt, plus
  `nasProof` and `nasProofSHA256` for the completed independent ciphertext readback.

All local evidence paths must resolve inside
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`.
The manifest and control-plane receipt hashes bind the reviewed authority; the
encrypted archive is rehashed and its size checked. Control-plane receipt must
report completed authentication, snapshot-footer/status verification, off-node
copy and no retained remote plaintext. Its source image/imageID must match live
Ready etcd. Original cluster node UIDs remain pinned.

Manifest capture, each native backup/snapshot and control-plane completion must
be no more than six hours old. All58 Bound PVCs and58 Bound PVs retain exact
name/UID/spec hashes. All44 Longhorn volumes retain original name/UID/spec/state:
28 attached/healthy and16 retained offline. Only Longhorn's requested attachment
node is excluded from the spec hash to permit normal relocation. Offline states
and robustness stay exactly pinned; no offline backup/data deletion is implied.
Every active volume requires its own completed current native backup with exact
UID/volume binding and unchanged durable status hash. These are crash-consistent native
backups, not an assertion of application-quiesced or independent restore proof.

Every Deployment/StatefulSet/DaemonSet spec is hash-pinned, preserving images,
storage, principals, resources and desired replicas. The unchanged dynamic
`recovery_guard` additionally waits for all original active controllers and
attached volumes to recover. The complete current checkpoint is reverified
after each node; a concurrent deployment or expired backup stops further nodes.

## Exact additional ephemeral mounts

The profile adds only the inspected Ingenium runtime-secrets, bootstrap-owned,
shared-memory and xTeve guide-gateway-temp controller/volume/mount tuples.
The original emptyDir guard checks the exact tuples again before and after
cordoning. A separate check verifies Memory medium, exact size128Mi/1Mi/256Mi/
16Mi and mount sets. It pins the two public regeneration ConfigMaps by UID/data
hash along with the immutable application controller spec.

Inspected chart `charts/ingenium/files/install-bootstrap.py` stages unchanged
native `ingenium-bootstrap` Secret bytes into bootstrap-owned with ownership
checks, and recreates the image's runtime-secrets directory layout. The existing
init command and native Secret reference are required verbatim; secret values
are never included. The shared-memory mount is `/dev/shm`. xTeve's existing
`threadfin-compatibility.yaml` uses `/tmp` for nginx PID/client/proxy temporary
files, while its init container sets permissions at `/proxy-tmp`. Both mount
the same16Mi memory volume. No persistent claim or original source is treated
as disposable. This does not broaden generic namespace or emptyDir allowances.

Before actual execution, retain fresh backup/restore evidence, review changed
current identities against authorized retirements, finish concurrent chart
rollouts, and validate scheduling headroom plus Longhorn redundant placement.
Existing instance-manager PDBs have zero disruptions available until Longhorn's
normal drain prerequisites are met; do not disable them. Actual boot into202,
node/runtime/storage recovery and application checks are still required.

## Maintained controller entry points

Use `scripts/migration/run-kernel-checkpoint.py control-plane` with protected
operator input, then `copy-kernel-control-plane-backup.py` from the existing
Windows NAS session. The copy helper reads back every byte and binds the NAS
ciphertext to the authenticated original. An interrupted target is preserved;
`--qualify-existing` only accepts the exact full size/hash before writing a new
proof. It never overwrites partial bytes. This is not a new independent restore.

Run the volume phase after chart rollouts settle, using a new explicit `--prefix`;
never replay a prefix containing resources. `capture-kernel-checkpoint.py` binds
the completed current checkpoint, original58 claim bindings, full identity set
and NAS proof to a new private manifest. `run-kernel-maintenance.py refresh`,
`preflight`, then `apply --manifest ... --manifest-sha256 ...` uses the existing
protected input and FD socket alias, with full rolling gates. Before each install,
the exact download plus installed-size upper bound and256MiB reserve must retain
15GiB usable and the unchanged25%+512MiB guard. No automatic storage-floor change.

Only after the terminal rollout and final verification consumers, reconcile the
empty Ansible directories using `reconcile-hardening-scratch.py inventory`,
`windows`, then `apply`. It refuses files, unexpected ownership, active references
or failed exclusive handles; source, ciphertext and actual receipts stay intact.

The first live rolling invocation completed both workers, then stopped before
master cordon because fresh package peak no longer fitted the unchanged disk
guard after workload relocation. Root retained that failed receipt and reclaimed
additional verified inactive cache. `kernel-master-completion.yml` rechecks both
workers' actual202 packages, retained198, running kernel and preserved services
before invoking the unchanged complete master role. The launcher exposes
`complete-master` with the same hash-bound original manifest. It preserves both
original serial-drain safety and the first playbook's same-invocation guards,
without unnecessarily draining completed workers again.
