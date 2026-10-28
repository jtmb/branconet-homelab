"""Read-only owner/image/route/data inventory; never request Secret objects."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
G = F / 'platform-upstream-review-20261027/final-fleet-20261028'


def get(kind):
    p = subprocess.run(['kubectl', 'get', kind, '-A', '-o', 'json'], capture_output=True, timeout=60)
    assert p.returncode == 0 and len(p.stdout) <= 32 * 1024**2
    return json.loads(p.stdout)['items']


def meta(v):
    m = v['metadata']
    return {k: m[k] for k in ('name', 'namespace', 'uid', 'resourceVersion') if k in m}


def remote():
    assert socket.gethostname() == 'masternode'
    rows = {}
    for kind in ('deployments', 'daemonsets', 'statefulsets', 'replicasets', 'jobs', 'cronjobs'):
        for v in get(kind):
            rows[v['metadata']['uid']] = {**meta(v), 'kind': v['kind'],
                'owners': v['metadata'].get('ownerReferences', []),
                'helmRelease': v['metadata'].get('annotations', {}).get('meta.helm.sh/release-name'),
                'replicasDesired': v['spec'].get('replicas'),
                'readyReplicas': v.get('status', {}).get('readyReplicas'),
                'numberReady': v.get('status', {}).get('numberReady'),
                'desiredNumberScheduled': v.get('status', {}).get('desiredNumberScheduled')}
    pods = []
    for v in get('pods'):
        record = {**meta(v), 'owners': v['metadata'].get('ownerReferences', []), 'node': v['spec'].get('nodeName'),
            'phase': v['status'].get('phase'), 'deleting': bool(v['metadata'].get('deletionTimestamp')), 'containers': []}
        for field, status, label in (('containers', 'containerStatuses', 'main'), ('initContainers', 'initContainerStatuses', 'init'),
                                      ('ephemeralContainers', 'ephemeralContainerStatuses', 'ephemeral')):
            statuses = {s['name']: s for s in v['status'].get(status, [])}
            for c in v['spec'].get(field, []):
                s = statuses.get(c['name'], {})
                record['containers'].append({'name': c['name'], 'kind': label, 'image': c['image'],
                    'imageID': s.get('imageID'), 'ready': s.get('ready'), 'restartCount': s.get('restartCount'),
                    'state': list(s.get('state', {})), 'waitingReason': s.get('state', {}).get('waiting', {}).get('reason')})
        pods.append(record)
    flux = {}
    for kind in ('helmreleases.helm.toolkit.fluxcd.io', 'kustomizations.kustomize.toolkit.fluxcd.io', 'gitrepositories.source.toolkit.fluxcd.io'):
        flux[kind] = [{**meta(v), 'suspend': v['spec'].get('suspend', False),
            'conditions': [{k: c.get(k) for k in ('type', 'status', 'reason')} for c in v.get('status', {}).get('conditions', [])],
            'chart': v['spec'].get('chart', {}).get('spec', {}).get('chart'),
            'targetNamespace': v['spec'].get('targetNamespace'), 'releaseName': v['spec'].get('releaseName'),
            'lastAppliedRevision': v.get('status', {}).get('lastAppliedRevision'),
            'artifactRevision': v.get('status', {}).get('artifact', {}).get('revision')} for v in get(kind)]
    claims = [{**meta(v), 'phase': v.get('status', {}).get('phase'), 'volumeName': v['spec'].get('volumeName'),
        'storageClassName': v['spec'].get('storageClassName')} for v in get('pvc')]
    pvs = [{**meta(v), 'driver': v['spec'].get('csi', {}).get('driver'),
        'handle': v['spec'].get('csi', {}).get('volumeHandle'), 'claimUID': v['spec'].get('claimRef', {}).get('uid'),
        'reclaimPolicy': v['spec'].get('persistentVolumeReclaimPolicy')} for v in get('pv')]
    ingress = [{**meta(v), 'rules': v['spec'].get('rules', []), 'tls': v['spec'].get('tls', [])} for v in get('ingresses')]
    nodes = [{**meta(v), 'conditions': [{k: c.get(k) for k in ('type', 'status', 'reason')} for c in v['status']['conditions']],
        'nodeInfo': v['status']['nodeInfo']} for v in get('nodes')]
    print(json.dumps({'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'mutationPerformed': False,
        'SecretObjectsRequested': False, 'nodes': nodes, 'controllers': list(rows.values()), 'pods': pods,
        'flux': flux, 'claims': claims, 'persistentVolumes': pvs, 'ingresses': ingress}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--remote', action='store_true')
    parser.add_argument('--generation', choices=['original', 'post-security'], default='original')
    a = parser.parse_args()
    if a.remote:
        remote()
        return
    global G
    if a.generation == 'post-security':
        G = F / 'platform-upstream-review-20261027/final-fleet-post-security-20261028'
    assert F.is_mount() and not G.exists() and os.geteuid() == 1000
    for p in (F, Path('/mnt/c')):
        st = os.statvfs(p)
        assert st.f_bavail * st.f_frsize >= 15 * 1024**3 + 32 * 1024**2
    os.umask(0o077)
    G.mkdir(mode=0o700)
    source = Path(__file__).resolve()
    with (G / 'ownership.json').open('x') as out:
        json.dump({'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
            'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b', 'generatedPaths': [str(G / 'inventory.json')],
            'sourceSHA256': hashlib.sha256(source.read_bytes()).hexdigest(), 'completePeakBytes': 32 * 1024**2,
            'regeneration': 'Same read-only projected kubectl inventory; no Secret objects or raw private configuration',
            'retention': 'Minimal final owner/image/data/route evidence for the migration security audit'}, out, indent=2)
    p = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
        '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-i', '/home/brajam/.ssh/id_ed25519',
        '-p', '2002', 'james@192.168.0.4', 'python3 -B - --remote'], input=source.read_bytes(), capture_output=True, timeout=240)
    assert p.returncode == 0 and len(p.stdout) <= 8 * 1024**2
    value = json.loads(p.stdout)
    with (G / 'inventory.json').open('x') as out:
        json.dump(value, out, indent=2)
    print(json.dumps({'status': 'captured', 'nodes': len(value['nodes']), 'claims': len(value['claims']),
        'runningPods': sum(p['phase'] == 'Running' for p in value['pods']),
        'runtimeImageIDs': len({c['imageID'] for p in value['pods'] if p['phase'] == 'Running' for c in p['containers'] if c['imageID']})}))


if __name__ == '__main__':
    main()
