# Longhorn compatible remediation proposal — 2026-10-25

**October27 source revalidation:** GitHub's latest stable release remains
[v1.13.0](https://github.com/longhorn/longhorn/releases/tag/v1.13.0); the newer
1.12.2-rc1 entry is a prerelease. The published manifest asset still matches
the retained243,976-byte SHA256d0f99488…0a1f.
[Exact dated API metadata](../evidence/longhorn-upstream-revalidation-20261027.json).
The [official V1 guide](https://longhorn.io/docs/1.13.0/deploy/upgrade/longhorn-manager/)
still supports1.12.x→1.13.0, requires volume backups and calls out schedulability
for the new global manager. This does not close capacity/recovery or owner-hold
gates. Counts below are the historical October25 observation, not current state.

The corrected delivery goal supersedes this historical review's bespoke rebuild
suggestions: consume maintained upstream releases; do not rebuild or maintain
third-party Longhorn images as private forks. Retain exact unresolved findings
where the compatible published vendor release does not fix them.

**A supported V1 upgrade path exists from the installed 1.12.1 to stable 1.13.0.**
The V2 requirement to start from 1.12.2 does not apply to this cluster's actual
topology. First restore replica health/capacity, preserve backups and review the
complete vendor manifest. The vendor upgrade is a candidate, not proof that all
current package vulnerabilities disappear. No upgrade, image acquisition, scan,
SDK execution, Secret read, data walk or cluster mutation occurred in this review.

## Observed ownership and complete topology

Strict known-host master SSH issued Kubernetes GETs at approximately 17:11–17:16
UTC. All 41 Longhorn volumes, 41 engines and 81 replicas explicitly declare V1.
V2 is disabled. All 41 volumes are encrypted RWO/blockdev with two replicas
desired. There are 30 attached volumes: 29 healthy and one degraded; 11 retained
volumes are detached/unknown, not automatically classified as failed/deletable.
Thirty engines and 59 replicas run; 11 engines and 22 replicas are stopped.
Three V1 instance managers and the engine-image DaemonSet use 1.12.1; the latter
is ready on all three nodes. Kubernetes 1.37.1 Nodes are Ready.

The manager DaemonSet, UI and driver-deployer Deployments are server-side
**`kubectl` Apply owned**, dated 2026-10-09; no Helm annotations or Flux HelmRelease
was found. Manager UID is `bbac48a6-44be-468a-a263-cd6e689aec65`.
The default BackupTarget is separately owned by Flux
`flux-system/migration-releases`, UID`999fe7cd-e073-4a52-ba62-87db1857f876`.
Keep this split: use the existing kubectl manifest/field-manager route; do not
introduce competing Helm ownership, force conflicts, or take over the BackupTarget.
The exact original deployment source file was not found in this checkout; live
managed-field ownership is established, not a guessed Helm release.

Automatic engine upgrades are disabled (`concurrent-automatic-engine-upgrade-per-node-limit=0`),
replica auto-balance is disabled, and degraded creation is allowed. Preserve
these settings. The 63 Backup CRs all report Completed; 32 BackupVolume CRs exist,
and the configured default target reports available. Twenty-nine attached
volumes have backup CRs; the new Ruckus claim does not. Older detached claims,
restore/proof claims and original Ruckus rollback PVC remain retained. Backup
metadata does not prove current data freshness, application consistency or a
successful restore; existing authenticated cold archives remain separate evidence.

## Actual capacity and Ruckus gate

All three Longhorn disk paths are `/var/lib/longhorn/`, on the same root ext4
filesystem as node application transfer artifacts. Observed Longhorn counters:

| Node | Maximum bytes | Available bytes | Reserved bytes | Scheduled bytes |25% minimum bytes | Disk scheduling |
|---|---:|---:|---:|---:|---:|---|
| masternode |115702075392|24956108800|34710622617|7516192768|28925518848|False: DiskPressure|
| workernode1 |249322430464|77175193600|31526778470|60129542144|62330607616|True|
| workernode2 |115702075392|24956108800|34710622617|60129542144|28925518848|False: DiskPressure|

The two pressured nodes are each 3969410048 bytes below the recorded minimum,
before any additional replica requirement. Over-provisioning is 100%; the
default reserve setting is 30%; node replica soft anti-affinity is false.
Do not reduce these thresholds or replica counts to manufacture health.

New Ruckus volume `pvc-0bf707c8-628e-4284-9aa0-35b711c8749b` is attached to
workernode2. Its only actual replica is
`pvc-0bf707c8-628e-4284-9aa0-35b711c8749b-r-2b0ef32e` on workernode1,
running/started/RW, healthyAt`2026-10-25T15:10:52Z`, empty failedAt. Two are
desired. Normal SQL/application acceptance does not establish storage redundancy.
Root can restore capacity using independently proven completed transfer
duplicates, then wait for a second healthy replica before storage upgrade work.

A later metadata-only inventory of
`/home/james/.local/share/branconet-migration/application-artifacts-20261023`
found 22 master files (2790555648 logical/2790662144 allocated bytes), 22 worker1
files (3337632768/3337723904), and 15 worker2 files (1497606656/1497669632).
All are UID/GID1000:1000 and0600 except worker1's older ytptube archive0400.
These totals are ceilings, **not deletion eligibility**; even the entire
directory cannot supply 4GiB on either pressured node. No content was read or
hashed. Exact names, modes, inode/link/age metadata and lsblk are in F receipts.
`df -B1` then reported available 19654057984/65968975872/19723513856 bytes on
master/worker1/worker2 respectively. Preserve the distinction between these
filesystem counters and earlier Longhorn status; reobserve after root's exact
retirement. No NAS/Gluster data, runtime image or volume was inspected for cleanup.
Existing lsblk shows both pressured nodes have120034123776-byte disks,
117883011072-byte PV partitions and117880913920-byte root LVs: only2097152
bytes separate the PV partition and LV. This is not a half-allocated Ubuntu VG.
Worker1 PV/LV sizes are253909532672/253906386944 bytes. No useful free extents
can be inferred; root may separately inspect vgs/lvs, without changing thresholds.

## Available vendor candidate and remaining package fixes

The official [manager upgrade guide](https://longhorn.io/docs/1.13.0/deploy/upgrade/longhorn-manager/)
supports1.12.x→1.13.0, including V1 live engine upgrade. The current
[release](https://github.com/longhorn/longhorn/releases/tag/v1.13.0) is stable,
publishedSeptember29;1.12.2-rc1 remains prerelease in the queried release list.
Do not select the RC as an unnecessary intermediate version.

The hash-bound vendor deployment manifests retained on F are:

- 1.12.1: 207054 bytes, SHA256`41648963af867ac1d0c85755fb53cf61cacd57c9bb22e1942e3fb0439eeb04fd`.
- 1.13.0: 243976 bytes, SHA256`d0f99488e7b2789312d45b0127ce7388df71a971e6fca2085e88635303cc0a1f`.

Public registry index/amd64 manifest/config metadata was read; no layer was
downloaded. The five 1.13.0 amd64 configs were built September 29, based on SUSE
15.7 metadata. Root candidate index digests:

| `docker.io/longhornio/` image |1.13.0 index SHA256 |
|---|---|
|longhorn-manager|`7372f3c59239e9a67c0017b3af32fabdf08c4dcc0631140161da9a47e3b142f0`|
|longhorn-engine|`b0cc5090889d57705acd69c5106492992e84560170ac3bec4a1cc8dd3fe83ca6`|
|longhorn-instance-manager|`fc9e1c15e81988b04c146866ce7010b6df3a70f88302809bf53e19b27d1658a3`|
|longhorn-share-manager|`53950f78b7af38b8a943c298cd3020622191a4661a13036f69d83c154cc8690d`|
|longhorn-ui|`f22fb0254ae50195c1635ce428dfae26375956b3d7bd39640fae8fe33a236023`|

The [official component list](https://raw.githubusercontent.com/longhorn/longhorn/v1.13.0/deploy/longhorn-images.txt)
updates attacher4.13, provisioner6.3, registrar2.18 and liveness2.20, while
resizer2.2.1 and snapshotter8.6 remain. Registry roots for the latter are
`63d0aef25114d4a682b25afa6d9623a3cfcc19aca910269124408476bbe2c6fd` and
`2bca9ac55170efa61dc50e5cc8d9550373db2e3e5161d82d3fdaac5c25150360`, exactly
matching live Pods. Their retained findings cannot be claimed fixed by the
Longhorn version change.

Source-level comparison with the retained fixed-package mapping:

| Component source 1.13.0 | Observed dependency/build choice | Implication |
|---|---|---|
|manager/engine/instance/share|gRPC1.83.2, x/text0.41|Meets those previously identified fixed-version targets; selected binaries still require verification.|
|same four|x/net0.58|Below retained0.60 security target; remains a concrete patch candidate.|
|manager|x/crypto0.56, compress1.19.1|Newer source dependencies; do not infer closure of unrelated advisories.|
|Go builds|Go1.26 build line; engine toolchain directive1.26.6|No binary buildinfo read; go.mod minimum is not compiler provenance. September binaries do not establish October Go1.26.10 remediation.|
|SUSE15.7 runtime|Vendor Dockerfiles run signed zypper refresh/update|Actual RPM inventory/fixed rows require exact image scan; rebuilding on signed same-branch updates is available.|

Sources: [manager go.mod](https://raw.githubusercontent.com/longhorn/longhorn-manager/v1.13.0/go.mod),
[manager Dockerfile](https://raw.githubusercontent.com/longhorn/longhorn-manager/v1.13.0/package/Dockerfile),
[engine go.mod](https://raw.githubusercontent.com/longhorn/longhorn-engine/v1.13.0/go.mod).
The UI is a static build served by SUSE nginx; its build-stage Node20 is not
proof of installed runtime Node. No dependency metadata was renamed or suppressed.

## Owner-preserving execution and recovery sequence for root

1. Restore capacity/redundancy first; refresh the41-volume inventory and wait for
   the new Ruckus volume to have both intended healthy replicas. Retain original
   cold PVCs, archived data and native encryption credentials. No prune, volume
   deletion, replica evacuation or reduced threshold is part of this proposal.
2. Preserve the live managed manifests/settings/CRDs, volume/PV/PVC/Secret
   identities, replica placement and exact current images in protected evidence.
   Make fresh application-consistent backups and a Longhorn system backup; verify
   the retained restoration path, including new Ruckus data. Existing Completed
   CRs alone are insufficient. Keep Secret values out of plaintext exports.
3. Review the entire official1.13.0 manifest against the current kubectl-owned
   deployment. Preserve existing settings, resource/security customizations,
   StorageClass/PV/PVCs and Flux BackupTarget. New global-manager scheduling,
   CSI service-account/RBAC, network-policy rules and provisioner6.3 integration
   require review; Kubernetes 1.37.1 satisfies the 1.34 minimum. Finish pinning and
   exact-scanning the complete candidate stack before applying it.
4. Use an opt-in Ansible task wrapping the existing server-side kubectl ownership,
   with UID/spec guards and reviewed diff; no forced ownership or Helm adoption.
   Upgrade control plane first while automatic engine upgrade remains0. Verify
   manager/global-manager/CSI health and existing data access before each next step.
5. Upgrade one healthy V1/blockdev volume at a time, verifying original UID,
   claims, encryption, replica health and application read/write/restart behavior.
   V1 live upgrade temporarily doubles replica processes. Degraded volumes need
   recovery first or a separately planned offline workload stop/detach. Retained
   detached volumes are handled deliberately; do not bulk attach/delete them.
   [Official V1 procedure](https://longhorn.io/docs/1.13.0/deploy/upgrade/upgrade-engine/).
6. Old V1 instance-manager Pods can remain after live engine upgrade while they
   host engines. Complete later workload-scoped detach/reattach cycles before
   claiming old vulnerable instances retired; never force-delete active managers.
   [Documented lifecycle](https://longhorn.io/docs/1.13.0/deploy/upgrade/instance-manager-pods-during-upgrade/).
7. If the upgrade is rejected before migration, restore the guarded previous
   deployment through the documented failure path. **After successful upgrade,
   downgrade is unsupported**; recovery is forward repair or validated backup
   restoration, not an assumed Helm rollback. Establish that recovery plan before
   applying. [Upgrade/downgrade policy](https://longhorn.io/docs/1.13.0/deploy/upgrade/).

For residual CVEs not closed by vendor1.13.0, a same-source supported-Go rebuild,
compatible module patch and signed SUSE15.7 updates remain available engineering
routes. Qualify the complete component/protocol/native ABI combination and exact
scan; do not swap individual CSI binaries or call available fixes impossible.
This review prepares no image build and promises no zero-finding outcome.

## Evidence

F root: `/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/longhorn-remediation-discovery-20261025`.
`live-topology.json` SHA256`18064f008be2b0311bb6d945eb476299b8f4b6427d8efab074a47e8fd59fb759`;
`field-ownership.json` SHA256`22ad3f52655fb02cda2a5a73892ac9d0b58ea22524334b3e9fc0f158b16ce042`;
`disk-and-ruckus.json` SHA256`890310980995e0b83a0cfa7060303f2af7be2208d8eb4363a99a3797b9e8b967`.
`volume-summary.json` covers all 41 volumes. Public source/registry proofs,
transfer metadata and their exact hashes are retained under the same root.
Observed state may change while root performs its independent work; recheck
immediately before any future action. No root PLAN/STATUS or existing recipe changed.
