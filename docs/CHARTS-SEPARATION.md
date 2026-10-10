# Separate charts repository and Flux delivery

Completed live cutover/canary verification on 2026-10-10. Historical extraction
checkpoint: `373a1e513e1bfb8b13ed5212ccc1b0f57a5ff301` from branconet-homelab.
Private repository: https://github.com/jtmb/branconet-charts.

| Gate | Observed result |
|---|---|
| Inventory and exact extraction | 33 tracked application packages, own values; no app source/history copied |
| Rendered equivalence | All application objects and 64-resource Flux/foundation composition equal to original, except source/path remapping |
| Credential scan and validation | Gitleaks + structural scan; Helm lint, activation/private gates, effective renders and 4 guard tests passed |
| Initial real GitHub CI | 38056843293 passed for d12cc3bdb6d807e7da070cbadd935bc0b242e7d8 |
| Read-only source authentication | Repository-only deploy key 166012451; native flux-system/branconet-charts-readonly; GitHub host keys verified via TLS meta API |
| Source cutover | Ready new source; same Kustomization UID f3757d64-04bd-46db-8b40-ae666999449c; 34 unchanged release identities |
| Canary | CI 38057003120, commit bd6a76896596bf9a4d9519415ba2c42e26f0a51c; source/Kustomization/HR observed exact revision, actual replacement Pod |
| Rollback | CI 38057072051, commit b5978a2414fda51957dd195e065d58470e8920b0; annotation removed, second actual replacement Pod |
| No Chart.yaml bump required | Chart version remained 0.1.0; reconcileStrategy Revision consumed both content changes |
| Data and runtime preservation | 53 claims, 53 PVs, 39 Longhorn volumes, 61 workload specifications/images/Secret refs, 294 RBAC objects unchanged |
| Health | 34 Ready HelmReleases, 3 Ready nodes, all desired workload replicas available; 90/90 HTTPS route probes across 30 hosts and 3 addresses passed |
| Ownership | One active Kustomization; all 33 Git-backed application release sources are branconet-charts; cert-manager retains its original OCI digest |
| Old source | Retained, suspended and pinned to 373a1e513e1bfb8b13ed5212ccc1b0f57a5ff301 |

The HTTP echo claim UID, volume, Deployment UID, image digest and response SHA256
were identical before canary, after rollout and after rollback. The three observed
Pod UIDs are recorded in evidence/canary.json. Only the Pod annotation changed.

Application/TLS limits: route probes verify public-domain certificate chains;
existing LAN .lan/.local default certificates are explicitly unverified.
Unauthenticated route status verifies reachability and expected login/challenge,
not every application's authenticated functionality. Existing application/data
acceptance and final source retirement remain the migration owner's contract.

The original chart publisher is removed from the old migration workflow; its
remaining archival validation cannot promote a deployment source. Recovery
Ansible defaults require the new native source Secret and target the new source;
syntax check passed without host reprovisioning. Final publication/revisions and
old workflow deactivation are recorded in evidence/publication.json after push.

Current BORTUS remains bortus:migration-1438b27 with pullNever, one Recreate
replica, unchanged native Secrets/RBAC and Longhorn SQLite claim. The separately
developed BORTUS image/engine is not rolled out by this setup. Native Secret values,
private keys, kubeconfigs and databases are absent from both repositories and all
reports. Swarm/Gluster/data/claim/encryption/backup recovery sources remain intact.

Detailed nonsecret evidence is in evidence/charts-separation.json and the charts repository evidence directory.
