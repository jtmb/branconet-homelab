# Longhorn upstream review — October27,2026

The complete official1.13.0 candidate is now digest-bound and freshly scanned.
**It has not been applied.** A live storage-capacity guard fails on the master
and worker2. Existing volumes, data, engine versions, settings, replica counts,
backup ownership and Kubernetes workloads were not changed by this review.

The [official upgrade path](https://longhorn.io/docs/1.13.0/deploy/upgrade/longhorn-manager/)
supports1.12.x→1.13.0 for this cluster's V1 volumes. All43volumes currently declare
V1, with27attached healthy and16detached. Kubernetes1.37.1 meets the new1.34minimum.
The V2-specific1.12.2 prerequisite does not apply. The existing kubectl/server-side
ownership remains authoritative; this review does not introduce competing Helm
ownership or take over Flux's existing BackupTarget.

## Completed candidate checks

The fresh official1.13.0 deployment manifest matches the earlier independently
retained SHA256`d0f99488e7b2789312d45b0127ce7388df71a971e6fca2085e88635303cc0a1f`.
All14official component references were bound to registry index, amd64 manifest,
configuration and layer descriptors. This includes manager, engine, instance/share/
backing-image managers, UI, CLI, six CSI components and support-bundle kit.
No candidate image was imported onto a cluster node.

All14exact images completed isolated remote scans with pinned Trivy, the verified
October27,01:25UTC public vulnerability feed, Java identification index and current
CISA catalog. Inputs were hash-verified before/after; no suppression was used.
Across all components, results contain **7Critical,215High,270Medium,29Low and
22Unknown package/target rows**, representing62unique CVEs, with no CISA KEV match.
The official release retains listed dependency/RPM fixes; it is not a fully
patched-image claim. Older1.12.1 scans are not a matched fresh baseline, so no
numerical reduction is inferred from comparing their counts with this scan.
No bespoke third-party rebuild is proposed under the current goal.

## Concrete storage constraint

Live Longhorn disk scheduling reports:

| Node | Available bytes reported by Longhorn |25% minimum bytes| Shortfall to exceed minimum, before image pulls |
| --- | ---: | ---: | ---: |
| masternode |24956108800|28925518848|3969410049|
| workernode2 |28311552000|28925518848|613966849|
| workernode1 |125409689600|62330607616|0|

Both smaller nodes report `Schedulable=False`, reason `DiskPressure`, in Longhorn.
Kubernetes Nodes remain Ready without Kubernetes pressure and attached volumes
remain healthy; these are different health conditions. The upgrade needs capacity
beyond the minimum for its image pulls and continued replica recovery. Thresholds
and replica counts were not reduced to manufacture an upgrade pass.

Separate unprivileged filesystem measurements report19,724,242,944available bytes
on master,23,036,325,888on worker2,114,205,478,912on worker1. Those `f_bavail` figures
are retained separately from Longhorn's counters; they are not interchangeable.

Read-only artifact inspection found no remaining transfers in the exact legacy
application-artifacts directory on any node. Master still has two retired custom
kubectl source/output trees and original audit material; worker2 has a BORTUS audit
tree belonging to the separate owner. Partial unprivileged directory observations
are not deletion eligibility. No original source, failed evidence, BORTUS artifact,
runtime image, volume or user data was removed. Exact creator/regeneration,
72-hour inactivity, source/lock retention and full process/mount proofs remain
required before reclaiming any older generated copy.

The next storage step is to establish safe capacity recovery, then fresh protected
backup/system-recovery prerequisites and a guarded owner-preserving Ansible
upgrade. Fresh complete-system backup, restore qualification and upgrade are not
claimed by this read-only review. No shutdown, drain, destructive reset or storage
reconfiguration occurred.

## Evidence and reconciliation

Evidence remains under the existing single F-backed task root, in
`platform-upstream-review-20261027` and the14
`security-review-20261026/apps-longhorn-1.13-current-r4-*` directories.
`candidate-outcome.json` binds registry/scan identities, residuals and live capacity.
`live-upgrade-safety.json`, `upgrade-safety-summary.json` and
`node-owned-artifact-capacity.json` preserve the actual observations and limits.

Cleanup removed **15,962,112allocated Linux bytes**: the inactive
`security-review-20261026/cache-r4/fanal/fanal.db`, its empty directory, empty
`security-review-20261026/{tmp,home}`, and14reproducible progress JSONs under the
review directory. Exact paths/bytes/inodes/hashes, regeneration and protected
source/result checks are in
`operator-control/longhorn-upstream-review-scratch-{plan,reconciliation}.json`.
Current public inputs and cache links remain required for pending fleet work.
The prior unresolved command-line sentinels remain retained; no Windows recovery
is inferred from Linux allocation measurements.

New minimal recovery metadata is12,772,596bytes, SHA256
`35bd86f3b7cb486b029ea4ef3d8d827b2b18bec1a39543ba6bc2d07738bf9e61`.
Every member and the complete NAS ciphertext readback authenticated using the
existing protected recovery-key backup. Prior ciphertexts, cumulative metadata
archives and scanner database bytes were not duplicated into it.

The full migration/security goal remains active. This completed candidate review
does not resolve storage capacity, remaining platform remediation, Windows client
trust, final IAB or final fleet acceptance.
