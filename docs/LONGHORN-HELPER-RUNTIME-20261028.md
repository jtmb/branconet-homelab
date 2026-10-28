# Homepage and Unpackerr use the new Longhorn runtime

Both original applications completed normal detach/reattach through private
charts main, unchanged local validation, `validated`, and Flux. Stop commit
`0cc968b16914b3d09fece1ead79c3e1cacd03f91` and restore commit
`bf739c36dc0676f1d8a0e29fd95f40b78bcdb224` changed only their existing release
replica counts. No direct scale, controller suspension, forced detach, application
image change or storage rebinding occurred.

Their original Deployment/release/template identities, all three claim/PV
bindings and both Longhorn volume identities/replica directories survived.
Nine Homepage configuration files, including its existing mounted native
configuration, and the complete Unpackerr configuration have identical hashes.
Homepage's changing logs were retained untouched and excluded from the stable
configuration comparison. Each new Pod has zero restarts and the same original
immutable upstream application image; each volume has two actual healthy RW
replicas on the pinned v1.13.0 instance manager.

Homepage returned 200 through its normal LAN HTTPS route with default Windows
certificate trust. Unpackerr 1.0.0 retrieved Radarr/Sonarr queue information in its
bounded new-Pod log window without observed authentication/ERROR/FATAL lines.
Raw logs and configuration values were not written. This checks existing
integration startup; it does not claim a new real Arr import or extraction.
The original NAS download directory is readable; its corpus was neither walked
nor copied. All 58 claims, 14 NAS bindings, three Ready nodes and desired workload
availability survive. Flux's migration Kustomization is Ready at the restore SHA.

The opt-in `longhorn-app-runtime.yml` Ansible playbook accepts explicit
`longhorn_app_runtime_apply=true` and
`longhorn_app_runtime_phase=prepare|stop|observe|detached|resume|verify`.
Its fixed cohort worker binds the prepared sources, native backups, original
data identities and configurations. Incomplete submissions must be inspected,
not blindly replayed. The independent integration observer has native and
Windows HTTPS modes; neither performs cluster mutations or browser acceptance.

Output stays in the existing F-backed task root, physical filesystem UUID
`3c792469-ea0e-4a2c-98e8-1185b141607b`, under
`platform-upstream-review-20261027/longhorn-helper-runtime-20261028`.
Ownership/peak/regeneration were recorded before the plan and stop.
[Exact acceptance and receipt index](../evidence/longhorn-helper-runtime-20261028.json).

Cleanup removed **355,721,216 allocated Linux bytes / 1,612 paths** from the two
consumed terminal publisher exports. Complete Linux reference checks and all
1,612 exclusive Windows handles passed. Ten protected report/lock/publication
files, original Git blobs and pinned tools remain unchanged. The exact per-path
ledger is `longhorn-runtime-retirement-20261028/publisher-cleanup-b1f41fb43486faef/receipt.json`
under the existing platform review root. Retain 13 unique current metadata files,
440,947 logical bytes excluding the inventory index, for data/runtime/integration
acceptance and the remaining owner map. No build, dependency cache or nonpublisher
scratch was generated. Required tracked charts source and operational recovery
tools still serve the remaining stateful cycles. Earlier protected safety-check
and rollback exceptions remain. Independent Windows free observations are
C:56,589,983,744 and F:193,644,859,392 bytes; no Windows recovery is inferred
from Linux removal.

A fresh read-only engine-to-Pod/Deployment/HelmRelease inventory now identifies
**21 old-runtime engines across 17 Deployments**. BORTUS is the sole suspended
release and remains held under its separate application owner. Pi-hole and
Ingenium remain individually scoped maintenance. The other 14 Deployments cover
17 engines, including the shared qBittorrent/monitor volume, and can be reviewed
as one maintenance batch while Pi-hole keeps DNS/publication available. This is
an inventory and next execution scope, not a completed cycle for those services.
Remaining cycles, final exact-image/security reconciliation, normal Seerr/YTPTube
IAB acceptance and final cleanup keep the full goal active.
