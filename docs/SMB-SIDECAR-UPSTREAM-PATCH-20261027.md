# SMB upstream sidecars — accepted October27

The existing `kube-system/csi-driver-smb` Helm release now runs pinned official
node-driver-registrar2.18.0 and livenessprobe2.20.0. Actual apply and a separate
read-only verification passed. All seven running replacement sidecars are Ready,
zero-restart and match their exact registry image identities. The SMB driver and
chart stay1.20.4; release revision advances2→3. No Flux adoption or competing
publisher, NAS-data migration, storage-policy change or new credential occurred.

Repeatable execution is in the opt-in
[Ansible playbook](../k8s-rewrite/ansible-playbook/playbooks/smb-sidecar-upstream-patch.yml)
and [source](../k8s-rewrite/ansible-playbook/roles/smb_sidecar_upstream_patch/files/patch.py).
The role defaults disabled and supports preflight/apply/verify. Apply requires the
exact reviewed preflight hash and refuses a pre-existing apply marker. The helper
reuses the hash-pinned existing SMB chart/compatibility/native-storage readers,
keeping Helm values, rendered manifests and native Secret values only in master
RAM. The public chart memfd never becomes a plaintext configuration file.
No install/uninstall/force flag or chart/owner replacement is used.

## Exact change and live preservation

- Registrar: `registry.k8s.io/sig-storage/csi-node-driver-registrar:v2.18.0@sha256:b7fefd08651f00ac4df1a196ed4c621c2451fbb899297fe9fad9e36c667af0c0`.
- Liveness: `registry.k8s.io/sig-storage/livenessprobe:v2.20.0@sha256:19f2cf2f40e1987c7943945deca5f65cd4e4bf5cc0657fc78a5df131861578e8`.

Both official multi-platform indexes retain Windows amd64 entries. The Windows
DaemonSet retains its selector and zero desired nodes; Windows execution is not
claimed. Helm's server dry-run proves **four rendered image fields only** change:
one Windows registrar, two Linux-node sidecars and the controller liveness image.
The first guard expected five before inspecting the Windows HostProcess shape;
it refused before mutation. The original failed receipt/source stay retained.
The corrected four-field preflight and exact baseline were reviewed before apply.

All12release-resource UIDs and unrelated settings remain: existing RBAC,
service accounts, CSI driver, controller Recreate/one replica, node RollingUpdate/
maxUnavailable1, platforms, selectors, resources and remaining images. All14SMB
PVs/PVCs and the referenced native credential retain full keyed fingerprints.
The original Helm revision1 Secret UID survives, with normal Helm history retained.
Only the two new tag overrides are added to the original stored values.
Generated Deployment revision and both DaemonSet template-generation counters
advance exactly once; no unrelated spec/metadata field is excluded by that proof.

The controller is1/1, Linux node driver3/3, Windows0/0. Actual mount-root `stat`
checks pass on master and worker2, matching the two-node preflight coverage.
This is a bounded availability sample, not a NAS content or throughput audit.
No mounted NAS file/tree was rewritten or walked.

Fresh global comparison after the patch preserves63Flux specifications,57claims,
57PVs,184native Secrets and all3node/boot identities. Of50application/infra
workload specifications, only the three exact SMB workloads differ; their UIDs
remain. Every unrelated workload specification matches. All releases remain Ready
with BORTUS's hold unchanged. Charts main/validated/live remains
`3a8de93a4034780519bac191bf4a02b4a4c96f96`; Actions was not used.

## Security and remaining platform work

The two exact official images were scanned with unchanged tool/feed/limits and
input hash verification before/after, with no suppression or CISA KEV match.
Each has5High/13Medium/1Low/1Unknown package rows. The previous two runtime
artifacts each had25High rows on that same feed: the combined SMB sidecar
comparison improves50→10High. Remaining listed fixes are vendor residuals, not a
clean-image claim. Old Longhorn sidecars still use their older artifacts, so
their findings do not disappear from the cluster inventory.

The fresh fleet now has63distinct running image digests,62complete same-feed
reports and one BORTUS registry-coverage gap. Raw package rows are85Critical,
2774High,3488Medium,1954Low and1424Unknown;2363unique CVEs. The distinct-artifact
sum gains two newly separate official artifacts while the old shared Longhorn
artifacts remain; it is not a before/after count of exploitable paths. The known
FlareSolverr Chromium/CISA match remains explicitly unresolved.

The snapshot-controller8.7.0 candidate was also fully scanned:2High/4Medium/
2Unknown, versus47High in the current8.5 runtime. **It is not applied.** Its
new group-snapshot GA behavior needs a coordinated CRD/RBAC review. Current
snapshot/controller/class UIDs, existing Ready snapshot/content and original
schemas remain unchanged. Official source file URLs/Git blob hashes and the
filtered live ownership/API inventory are retained for that next operation.

Longhorn still has43V1volumes,27attached healthy and16detached, target2replicas.
Its25%disk floor remains unchanged. At04:41UTC, master is4,493,698,049bytes and
worker2 is1,452,827,649bytes below the minimum before upgrade image pulls.
Both nodes have no spare VG extents. Read-only runtime allocation is32,229,359,616B
on master and22,801,596,416B on worker2, plus protected legacy Docker data.
Those totals are not unused/deletable bytes. No images, containers, snapshots,
volumes, source or original data were pruned. The first read-only runtime
inventory encountered absent `crictl`; it was corrected to use installed `ctr`
read-only image/container/task metadata, without installing another tool.

Replica relocation was inspected without mutation. Only two master-held volumes
lack an existing worker1 replica; their reported data totals1,233,690,624B,
less than the master's current shortfall. Moving the other volumes to worker1
would colocate existing copies. No eviction, replica reduction, anti-affinity
change, volume attachment or data move was attempted to manufacture capacity.

Remaining: snapshot-controller schema/RBAC-compatible adoption; Longhorn safe
capacity/recovery prerequisites and upgrade; vendor/host-entitlement security
exception reconciliation; Windows LAN client trust; final Seerr/YTPTube IAB and
whole-fleet acceptance. BORTUS application development/adoption remains separate.
The full tracked goal stays active.

## Evidence and reconciliation

Under the existing single F-backed root:
`platform-upstream-review-20261027/smb-sidecar-upgrade/{preflight,review-approval,
apply,verify,global-after}.json`, actual Ansible logs/source bindings, compact
`control-source/csi-upstream-20261027`, three complete
`security-review-20261026/apps-platform-csi-upstream-current-r4-*` reports,
registry/source metadata and `fleet-after-smb-security-summary.json`.
All raw findings, original/failure/source/rollback/data evidence remain.

Cleanup removed270,336allocated Linux bytes: scanner
`security-review-20261026/cache-r4/fanal/fanal.db`237,568B, its empty directory,
scanner `tmp`/`home`, and the five empty reused Ansible scratch directories32,768B.
Exact resolved paths, creator/source/regeneration/inode/FD/maps/mount proofs and
protected before/after hashes are in
`operator-control/csi-upstream-scratch-{plan,reconciliation}.json`.
The earlier `operator-control/tmp/system-commandline-sentinel-files` and parent
remain for the recorded creator/regeneration/Windows-handle proof gap. No Windows
disk recovery is inferred from the Linux allocation measurement.

The new evidence-only encrypted package is2,233,076bytes, SHA256
`c7fa2d15b4c2e5a9e98544c993bd930c039d2b3e5c3dc1ec5ad7a931e7571611`.
Every member/source hash and full age authentication passed, followed by full
NAS hash/read-back authentication. Existing recovery archives and scanner DBs
were not copied inside it. Local/NAS proofs are
`operator-control/csi-upstream-metadata-receipt.json` and
`smb-csi-upstream-metadata-copy-status.json`; originals remain.
