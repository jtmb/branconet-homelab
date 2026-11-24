#!/usr/bin/env python3
"""Publish nonsecret setup evidence and update the reviewed acceptance records."""
import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[2]
CHARTS = ROOT.parent/'branconet-charts'
OUT = pathlib.Path.home()/'.local/share/branconet-migration/charts-separation'
final = json.loads((OUT/'final.json').read_text())
canary = json.loads((OUT/'canary.json').read_text())
if not final['passed'] or not canary['passed']:
    raise RuntimeError('Actual acceptance must pass before documenting completion')
for name in ['before', 'after', 'cutover', 'canary', 'final']:
    shutil.copyfile(OUT/f'{name}.json', CHARTS/'evidence'/f'{name}.json')
shutil.copyfile(CHARTS/'.validation/validation.json', CHARTS/'evidence/validation.json')
credential = {'repository': 'jtmb/branconet-charts', 'deploy_key_id': 166012451,
              'read_only': True, 'native_secret': 'flux-system/branconet-charts-readonly',
              'known_hosts_source': 'TLS-verified GitHub meta API', 'values_recorded': False}
(CHARTS/'evidence/credential-metadata.json').write_text(json.dumps(credential, indent=2)+'\n')
phases = {p['phase']: p for p in canary['phases']}
acceptance = f'''# Charts separation acceptance

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
| Canary | CI {phases['canary']['ci_run']}, commit {phases['canary']['commit']}; source/Kustomization/HR observed exact revision, actual replacement Pod |
| Rollback | CI {phases['rollback']['ci_run']}, commit {phases['rollback']['commit']}; annotation removed, second actual replacement Pod |
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
'''
(CHARTS/'docs/ACCEPTANCE.md').write_text(acceptance)
summary = {'repository': 'https://github.com/jtmb/branconet-charts', 'private': True,
           'authoring_branch': 'main', 'validated_branch': 'validated',
           'gitrepository': 'flux-system/branconet-charts', 'kustomization': 'flux-system/migration-releases',
           'composition_path': './flux/releases', 'bortus_chart': 'charts/bortus',
           'initial_ci': 38056843293, 'canary': phases['canary'], 'rollback': phases['rollback'],
           'preservation': final['preservation'], 'route_hosts': final['hostnames'],
           'route_probes_passed': final['route_probes_passed'], 'credential': credential,
           'old_source_suspended_pinned': True, 'original_sources_retained': True}
(ROOT/'evidence/charts-separation.json').write_text(json.dumps(summary, indent=2)+'\n')
# Update the old illustrative hierarchy without implying changes to the API shape.
api = ROOT/'docs/API-USAGE.md'
text = api.read_text()
section = text.index('### `GET /api/flux/hierarchy`')
start = text.index('**Response:**', section)
end = text.index('**Node kinds:**', start)
example = {'trees': [{'id': 'cluster-branconet-charts', 'name': 'branconet-charts', 'kind': 'GitRepository',
                     'url': 'ssh://git@github.com/jtmb/branconet-charts.git', 'branch': 'validated',
                     'namespace': 'flux-system', 'ready': True, 'status': 'Ready',
                     'children': [{'id': 'ks-migration-releases', 'name': 'migration-releases',
                                   'kind': 'Kustomization', 'path': './flux/releases', 'namespace': 'flux-system',
                                   'ready': True, 'status': 'Ready', 'children': []}]}]}
text = text[:start]+'**Response (abridged production topology; dynamic metadata omitted):**\n\n```json\n'+json.dumps(example, indent=2)+'\n```\n\n'+text[end:]
api.write_text(text)
(ROOT/'docs/CHARTS-SEPARATION.md').write_text(acceptance.replace('# Charts separation acceptance', '# Separate charts repository and Flux delivery')+
    '\nDetailed nonsecret evidence is in evidence/charts-separation.json and the charts repository evidence directory.\n')
print(json.dumps({'evidence_written': True, 'private_values_copied': False, 'acceptance_passed': True}))
