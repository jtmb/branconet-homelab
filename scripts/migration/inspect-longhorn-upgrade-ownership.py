"""Read existing objects named by the pinned vendor manifest; never apply it."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import yaml

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
O = F / 'platform-upstream-review-20261027'
R = O / 'longhorn-owner-review'
MANIFEST_SHA = 'd0f99488e7b2789312d45b0127ce7388df71a971e6fca2085e88635303cc0a1f'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def write(name, obj):
    with (R / name).open('x') as out:
        json.dump(obj, out, indent=2)
        out.write('\n')


def key(obj):
    meta = obj['metadata']
    return obj['apiVersion'], obj['kind'], meta.get('namespace', ''), meta['name']


def workload(obj):
    spec = obj['spec']
    pod = spec['template']['spec']
    return {'replicas': spec.get('replicas'), 'strategy': spec.get('strategy', spec.get('updateStrategy')),
            'nodeSelector': pod.get('nodeSelector'), 'affinity': pod.get('affinity'),
            'tolerations': pod.get('tolerations'), 'serviceAccountName': pod.get('serviceAccountName'),
            'priorityClassName': pod.get('priorityClassName'), 'hostNetwork': pod.get('hostNetwork'),
            'containers': [{k: c[k] for k in ('name', 'image', 'command', 'args', 'resources', 'volumeMounts', 'securityContext') if k in c}
                           for c in pod.get('containers', [])],
            'initContainers': [{k: c[k] for k in ('name', 'image', 'command', 'args', 'resources') if k in c}
                               for c in pod.get('initContainers', [])],
            'volumes': pod.get('volumes')}


def main():
    global R
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=R)
    args = parser.parse_args()
    need(args.output_dir.parent == O and re.fullmatch('longhorn-owner-review[a-z0-9-]*', args.output_dir.name), 'bounded_review_directory')
    R = args.output_dir
    need(F.is_mount() and not R.exists(), 'owned_new_review_scope')
    for path in (F, Path('/mnt/c')):
        s = os.statvfs(path)
        need(s.f_bavail * s.f_frsize >= 15 * 1024**3 + 16 * 1024**2, 'metadata_capacity_guard')
    raw = (O / 'longhorn-v1.13.0.yaml').read_bytes()
    need(hashlib.sha256(raw).hexdigest() == MANIFEST_SHA, 'exact_official_manifest')
    docs = [d for d in yaml.safe_load_all(raw) if d]
    allowed = {'Namespace', 'PriorityClass', 'NetworkPolicy', 'ServiceAccount', 'ClusterRole',
               'ClusterRoleBinding', 'Role', 'RoleBinding', 'CustomResourceDefinition',
               'ConfigMap', 'Service', 'DaemonSet', 'Deployment'}
    need(1 <= len(docs) <= 128 and all(d['kind'] in allowed for d in docs), 'bounded_nonsecret_vendor_resources')
    need(len({key(d) for d in docs}) == len(docs), 'unique_vendor_resources')
    need(all(d['metadata'].get('namespace', '') in ('', 'longhorn-system') for d in docs), 'fixed_storage_namespace')
    os.umask(0o077)
    R.mkdir(mode=0o700)
    write('ownership.json', {'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
          'physicalVolume': 'F: ext4 3c792469-ea0e-4a2c-98e8-1185b141607b',
          'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'outputs': ['ownership.json', 'live-nonsecret-objects.json', 'review.json'],
          'maximumResponseBytes': 16 * 1024**2, 'clusterMutation': False, 'secretValuesRequested': False,
          'regeneration': 'same pinned read-only owner/resource inspection into a new evidence namespace',
          'protected': 'every live object, workload, volume, Secret, original source and previous evidence'})
    query = {'apiVersion': 'v1', 'kind': 'List', 'items': [
        {'apiVersion': d['apiVersion'], 'kind': d['kind'], 'metadata': {
            k: d['metadata'][k] for k in ('name', 'namespace') if k in d['metadata']}} for d in docs]}
    child = subprocess.run(SSH + ['kubectl', 'get', '-f', '-', '--ignore-not-found=true', '--show-managed-fields=true', '-o', 'json'],
                           input=json.dumps(query).encode(), capture_output=True, timeout=180)
    need(child.returncode == 0 and len(child.stdout) <= 16 * 1024**2, 'bounded_live_owner_read')
    live = json.loads(child.stdout)['items']
    need(all(key(v) in {key(d) for d in docs} for v in live), 'only_named_public_resources')
    redactions = []
    for obj in live:
        if obj['kind'] not in ('Deployment', 'DaemonSet'):
            continue
        for container in obj['spec']['template']['spec'].get('containers', []):
            for env in container.get('env', []):
                if 'value' in env and re.search('password|token|secret|private.?key', env['name'], re.I):
                    redactions.append({'object': list(key(obj)), 'container': container['name'], 'environment': env['name']})
                    env['value'] = '<redacted; exact source cannot be rendered from this review>'
    write('live-nonsecret-objects.json', {'apiVersion': 'v1', 'kind': 'List', 'items': live})
    by_key = {key(v): v for v in live}
    rows = []
    for doc in docs:
        old = by_key.get(key(doc))
        row = {'object': list(key(doc)), 'exists': old is not None}
        if old:
            row.update(uid=old['metadata']['uid'], resourceVersion=old['metadata']['resourceVersion'],
                       fieldManagers=[{k: m.get(k) for k in ('manager', 'operation', 'apiVersion', 'subresource')}
                                      for m in old['metadata'].get('managedFields', [])])
        if doc['kind'] in ('Deployment', 'DaemonSet'):
            row['vendorWorkload'] = workload(doc)
            row['liveWorkload'] = workload(old) if old else None
        if doc['kind'] in ('ClusterRole', 'Role'):
            row['vendorRules'] = doc.get('rules', [])
            row['liveRules'] = old.get('rules', []) if old else None
        if doc['kind'] == 'ConfigMap':
            row['vendorDataKeys'] = sorted(doc.get('data', {}))
            row['liveDataKeys'] = sorted(old.get('data', {})) if old else None
        rows.append(row)
    write('review.json', {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'status': 'completed_read_only', 'vendorManifestSHA256': MANIFEST_SHA, 'resources': rows,
          'directSensitiveEnvironmentRedactions': redactions, 'clusterMutation': False,
          'fieldManagersExplicitlyCollected': True,
          'candidateRendered': False, 'serverDryRunExecuted': False, 'upgradeQualified': False})
    print(json.dumps({'status': 'completed_read_only', 'vendorResources': len(docs),
                      'existingResources': len(live), 'newResources': [r['object'][1:] for r in rows if not r['exists']],
                      'workloads': [r['object'][3] for r in rows if 'vendorWorkload' in r],
                      'sensitiveEnvironmentsRedacted': len(redactions)}))


if __name__ == '__main__':
    main()
