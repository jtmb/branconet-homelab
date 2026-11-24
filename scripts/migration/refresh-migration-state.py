#!/usr/bin/env python3
"""Refresh private-release ownership and service evidence without resetting sources."""
import datetime
import json
import pathlib
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
register_path = ROOT/'evidence/service-register.json'
register = json.loads(register_path.read_text())
for chart in (ROOT/'k8s-rewrite/charts').rglob('values.yaml'):
    values = yaml.safe_load(chart.read_text())
    changed = False
    for obj in values.get('resources', []):
        if obj['kind'] not in {'Deployment', 'StatefulSet', 'DaemonSet'}: continue
        pod = obj['spec']['template']['spec']
        for container in pod.get('containers', []) + pod.get('initContainers', []):
            image = container.get('image', '')
            pinned = '@sha256:' in image or ('.Values.image' in image and '@sha256:' in values.get('image', ''))
            if pinned and container.get('imagePullPolicy') != 'Never':
                if container.get('imagePullPolicy') != 'IfNotPresent':
                    container['imagePullPolicy'] = 'IfNotPresent'; changed = True
    if changed: chart.write_text(yaml.safe_dump(values, sort_keys=False))

rows = []
for path in sorted((ROOT/'k8s-rewrite/flux/migration-releases').glob('*.yaml')):
    if path.name in {'kustomization.yaml', 'namespaces.yaml'}: continue
    release = yaml.safe_load(path.read_text())
    name = release['metadata']['name']
    private = ROOT/'evidence'/('private-'+name+'.json')
    copy = ROOT/'evidence'/('copy-'+name+'.json')
    accepted = private.exists()
    if name == 'bortus':
        accepted = (ROOT/'evidence/bortus-live-proof.json').exists() and (ROOT/'evidence/bortus-dashboard-proof.json').exists()
    release['spec']['suspend'] = not accepted
    if accepted and not release.get('spec',{}).get('values',{}).get('migration',{}).get('verified'):
        review = release.get('spec',{}).get('values',{}).get('migration',{}).get('routingReviewed',False)
        release['spec']['values'] = {'enabled': True, 'replicaCount': 1, 'migration': {'staging': True,'routingReviewed':review}}
    path.write_text(yaml.safe_dump(release, sort_keys=False))
    status = 'Private checks passed; production routing pending' if accepted else ('Copied; application checks pending' if copy.exists() else 'Pending')
    for entry in register['entries']:
        if (entry.get('chart') or '').rsplit('/', 1)[-1] == name:
            entry['migration_status'] = status
            entry['copy_evidence'] = str(copy.relative_to(ROOT)) if copy.exists() else None
            entry['private_evidence'] = str(private.relative_to(ROOT)) if private.exists() else None
            entry['production_routing_accepted'] = False
    rows.append({'release': name, 'private_accepted': accepted, 'flux_suspended': not accepted, 'status': status})
register['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
register_path.write_text(json.dumps(register, indent=2)+'\n')
(ROOT/'evidence/release-state.json').write_text(json.dumps(rows, indent=2)+'\n')
print(json.dumps({'private_releases': sum(r['private_accepted'] for r in rows), 'suspended_releases':sum(r['flux_suspended'] for r in rows)}))
