# Existing SMB Helm release: reviewed patch only

This workflow keeps `kube-system/csi-driver-smb` under its existing Helm owner.
It does not create a Flux HelmRelease, adopt resources, install/uninstall the
driver, create a PVC, change NAS data or force resource replacement. The opt-in
Ansible playbook is `k8s-rewrite/ansible-playbook/playbooks/smb-helm-patch.yml`;
its role is disabled by default and check mode never executes the helper.

## Measured baseline and exact inputs

Read-only discovery on 2026-10-25 found Helm `/usr/local/bin/helm`
`v4.3.0+gbec5b06`, chart `csi-driver-smb` 1.20.3 revision 1, with **no stored
nondefault values**. Effective Linux support is enabled. Windows support and
HostProcess containers are also enabled; preserve both, even though the cluster
has only three Linux nodes. Linux controller/node selectors remain Linux-only;
the Windows DaemonSet retains its Windows selector and zero desired nodes.

The actual controller strategy is **Recreate**, with one replica. Both official
1.20.3 and 1.20.4 templates hardcode it. Preserve that strategy: provisioning can
pause briefly while the controller restarts. Existing mounted NAS I/O uses the
node/mount path and still needs the sampled read-only root-stat and node readiness
checks. Node DaemonSets retain RollingUpdate with `maxUnavailable: 1`.

- Official [1.20.4 chart](https://raw.githubusercontent.com/kubernetes-csi/csi-driver-smb/master/charts/v1.20.4/csi-driver-smb-1.20.4.tgz): 6,899 bytes, SHA256 `27116d0a703d9b7dee87ae65a0ffc95d47dfa4092b0191f1bb7e7cab79abb7f0`.
- `image.smb.tag`: `v1.20.4@sha256:74e049de9d3203b4a968f26c8b73d4b3b15b9c4705688330cfa7281ae5f7b727`.
- Windows HostProcess image: `registry.k8s.io/sig-storage/smbplugin:v1.20.4-windows-hp@sha256:5b8202d29540c6a93f31de8fe881fa7628f0375e86b13bb8077c349c58fc5499`.
- `image.csiResizer.tag`: `v2.2.1@sha256:ea1d25e23479000c7e8eeb92d827df66258df4e482ca054c5e7ce3fc0f5c41a5`.

The repository names remain official `registry.k8s.io/sig-storage/smbplugin`
and `registry.k8s.io/sig-storage/csi-resizer`. All three pins were fetched as registry
manifest metadata and SHA256-verified, without layer pulls. SMB's pin is a
multi-platform manifest list including Linux and Windows amd64 (Windows OS
versions `10.0.17763.9376` and `10.0.20348.5761`); it is not a Linux-only child.
The resizer index is Linux multiarch, appropriate for the Linux-only controller.
The official Windows HostProcess template appends `-windows-hp` to the shared
SMB tag. A global digest tag therefore produces an invalid reference in that
UNMODIFIED template, even though the main SMB index supports Windows. The
HostProcess artifact is a separate Windows-amd64 index, pinned above. Other
sidecar images remain unchanged through `--reuse-values`.

### Exact reviewed compatibility transform

The helper validates the official 6,899-byte archive, then applies precisely one
in-memory template transform. `scripts/migration/smb-chart-compat.patch` is its
explicit diff; `smb-chart-compat-proof.json` records every member content hash and
numeric metadata before/after. No chart version, defaults, other template bytes,
member order/ownership/modes/timestamps, RBAC or strategy are changed. Archive
compression is regenerated deterministically, so the derived archive has its
own identity:

- Derived chart: 6,798 bytes; SHA256 `ded072737207b41fb166b40c8fb38324f402238c4e83a585463705e9bbb95b5b`.
- Only modified member: `csi-driver-smb/templates/csi-smb-node-windows-hostprocess.yaml`.
- Member preimage SHA256: `a804f51f8e74648cb3cfd63738c9a8b8a2f924fe5c677bb51c007e8b31e04ccf`.
- Member postimage SHA256: `40f1d1304a98f849b4bda58efe85bfca7d6bc7a34cfcf0a1fefa5459ddad058b`.

Exactly four tag-template occurrences (the two repository branches for both
HostProcess init/container images) become the separate pinned HP tag. Exactly
one newly introduced require-privacy argument block is omitted, retaining the
actual old Windows argument list. The new binary's
[upstream Go flag defaults to true](https://raw.githubusercontent.com/kubernetes-csi/csi-driver-smb/v1.20.4/cmd/smbplugin/main.go),
so this does not disable its privacy default. An existing explicit false value
would fail the guard; none exists in this release. The helper verifies exact
pre/post member hashes, replacement counts and derived archive SHA256 before
Helm sees it. There is no post-render plugin or controller-strategy patch.

Public inputs live only below the approved generated root:
`FBASE/public-inputs/csi-driver-smb/`, where FBASE is
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`.
Before the tiny chart download, measured free bytes were C: 140,204,789,760;
F destination 36,860,559,360; master `/home/james` 21,114,077,184. No build,
dependency installation or image download is part of this workflow.

## Read-only gate

Create an owner-only directory and a 32-byte random hex key in a mode-0600 file
under `FBASE/acceptance-smb-20261025`. Reuse that key for every receipt. Do not
place it in arguments or print it. Existing native Kubernetes credentials remain
authoritative. The helper reads native Secret values, Helm values and full
rendered manifests only in master RAM. It disables master core dumps and uses
stdin for its input. A public chart memfd avoids exporting Helm configuration to
temporary files. The controller persists only keyed fingerprints, resource
identities/counts, approved public image differences and readiness results.

```sh
python3 -B scripts/migration/patch-smb-helm.py \
  --chart "$FBASE/public-inputs/csi-driver-smb/csi-driver-smb-1.20.4.tgz" \
  --receipt "$FBASE/acceptance-smb-20261025/preflight-01.json" \
  < "$FBASE/acceptance-smb-20261025/hmac-key.hex"
```

The helper invokes Helm's `--dry-run=server` and captures output only in RAM.
It rejects any rendered resource addition/deletion/rename, hooks, Secret/PVC/PV
manifest, RBAC change, strategy/placement change, or any difference beyond the
three exact artifact replacements (five rendered image fields) and chart-version labels. No new RBAC is approved
by this workflow. Such a delta needs a separately reviewed source change.

It checks the original deployed revision, no competing Flux owner, all existing
release-resource UIDs, Helm ownership, all three Linux nodes Ready, controller
readiness, Linux DaemonSet 3/3 and Windows DaemonSet 0/0. It fingerprints all bound
SMB PVs/PVCs, their original specs/NAS references, StorageClasses, CSIDriver, and
referenced native Secrets including UID and complete data. Only keyed values are
exported. Up to six bounded attempts sample existing mount roots with `stat`;
there is no NAS tree walk or data write. Missing stat tooling is recorded as
reduced coverage, not invented successful I/O. Root-directory stat is a limited
availability sample, not a file-content or throughput test.

## Explicit apply and afterward

Only the coordinating operator may execute `--apply`, after reviewing a passed
preflight and its exact SHA256. The helper repeats preflight and requires the
same baseline/key/source hashes before writing. Example additions to the command
above, with a NEW receipt filename:

```sh
--apply --approved-preflight "$FBASE/acceptance-smb-20261025/preflight-01.json" \
--approved-sha256 REVIEWED_RECEIPT_SHA256
```

The role requires `smb_helm_patch_enabled=true`; applying additionally requires
`smb_helm_patch_apply=true`, `smb_helm_patch_approved_preflight` and
`smb_helm_patch_approved_sha256`. Set `smb_helm_patch_hmac_key_file` and a fresh
`smb_helm_patch_receipt`. It uses the existing strict SSH master identity and
marks all key-handling tasks `no_log`.

Actual local Helm 4 help confirms `--rollback-on-failure` and `--wait=watcher`;
do not substitute Helm 3's `--atomic`. The only writing command is the same
release's `helm upgrade`, with `--reuse-values`, the two public tag overrides,
`--rollback-on-failure --wait=watcher --timeout=10m`. No install/force/cleanup flag
is used. See [Helm upgrade documentation](https://helm.sh/docs/helm/helm_upgrade/).

Afterward the helper requires revision 2, exact image specs, preserved workload/
RBAC/service-account/CSIDriver UIDs and remaining specs, preserved native storage
objects/credentials, unchanged stored values except the two tag overrides, all
three node readiness and mount sample coverage. Original revision-1 Helm Secret
UID must survive; its status/data may legitimately change to superseded.
The normal creation of revision-2 Helm storage is not a new native credential.

If Helm or postchecks fail, preserve the receipt and investigate the retained
release history and node/mount state. Do not uninstall, reset native credentials,
delete claims, force-recreate objects, or claim automatic rollback proves NAS
availability. A failed transport after an attempted upgrade is an unknown outcome
requiring read-only reconciliation, not permission to retry blindly.

## Prepared read-only acceptance receipt

Final preflight `FBASE/acceptance-smb-20261025/preflight-03.json` **passed** without
an upgrade attempt. Receipt SHA256:
`23e7a9e1809ec6827c3bdb8193e4e618718de30409a7f9ff0ccbf1549e1338b0`.
Helper SHA256:
`833704ef0255544ebf6399404c86311506d5fd2043a1fa7a748508aebecc8d2e`.
Its 33 approved differences are 28 chart labels and 5 image fields only. All
12 release-resource UIDs, 14 SMB PVs, 14 PVCs, one referenced native Secret and
three Ready Linux nodes were captured. Storage/Secret fingerprints and resource
UIDs match the earlier pre-transform observation. Read-only existing mount-root
stat succeeded on masternode and workernode2; no suitable running SMB mount
sample was present on workernode1. The Linux node DaemonSet was Ready 3/3.
Retained `preflight-01.json` and `preflight-02.json` show the original fail-closed
Windows-template findings. No claim, driver or release was changed.

Ansible syntax validation passed using the existing venv, with explicit
`ANSIBLE_CONFIG` pointing at this checkout's ansible.cfg (WSL correctly ignores
implicit config discovery on a Windows world-writable mount). Controller and
embedded master Python AST checks passed. The existing protected HMAC key is
`FBASE/acceptance-smb-20261025/hmac-key.hex`; reuse it, never print it. Actual
upgrade and post-upgrade qualification remain the coordinating operator's work.
