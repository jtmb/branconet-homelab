"""Inspect actual Longhorn ownership, data coverage and upgrade prerequisites.

This entry point has no mutation mode. It never reads Kubernetes Secret values,
attaches volumes, fetches images, creates backups or alters scheduling settings.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
REVIEW = ROOT / 'platform-upstream-review-20261027'
MANIFEST_SHA = 'd0f99488e7b2789312d45b0127ce7388df71a971e6fca2085e88635303cc0a1f'


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def kubectl(*args):
    child = subprocess.run(['kubectl', *args], capture_output=True, timeout=60)
    need(child.returncode == 0, 'kubernetes_read_failed')
    need(len(child.stdout) <= 32 * 1024**2, 'bounded_kubernetes_response')
    return json.loads(child.stdout)


def items(kind, namespace=None):
    args = ['get', kind, '-n', namespace] if namespace else ['get', kind, '-A']
    result = kubectl(*args, '-o', 'json')['items']
    need(len(result) <= 10000, 'bounded_object_count')
    return result


def identity(obj):
    meta = obj['metadata']
    return {k: meta[k] for k in ('name', 'namespace', 'uid', 'resourceVersion') if k in meta}


def ready(obj):
    return any(c.get('type') == 'Ready' and c.get('status') == 'True'
               for c in obj.get('status', {}).get('conditions', []))


def remote():
    need(socket.gethostname() == 'masternode', 'original_master_required')
    kinds = ('volumes', 'engines', 'replicas', 'engineimages', 'instancemanagers',
             'backingimages', 'backups', 'systembackups', 'backuptargets', 'nodes', 'settings')
    data = {k: items(k + '.longhorn.io', 'longhorn-system') for k in kinds}
    claims, pvs, nodes = items('pvc'), items('pv'), items('nodes')
    version = kubectl('version', '-o', 'json')['serverVersion']['gitVersion']
    settings = {x['metadata']['name']: x.get('value') for x in data['settings']}
    engines = data['engines']
    replicas = data['replicas']
    backups = data['backups']
    volumes = []
    for v in data['volumes']:
        name, spec, status = v['metadata']['name'], v['spec'], v.get('status', {})
        actual_engines = [e for e in engines if e['spec'].get('volumeName') == name]
        actual_replicas = [r for r in replicas if r['spec'].get('volumeName') == name]
        completed = [b for b in backups if b.get('status', {}).get('volumeName') == name
                     and b.get('status', {}).get('state') == 'Completed'
                     and not b.get('status', {}).get('error')]
        volumes.append({**identity(v), 'state': status.get('state'),
                        'robustness': status.get('robustness'), 'dataEngine': spec.get('dataEngine', 'v1'),
                        'encrypted': spec.get('encrypted'), 'size': spec.get('size'),
                        'actualSize': status.get('actualSize'), 'replicasDesired': spec.get('numberOfReplicas'),
                        'nodeSelector': spec.get('nodeSelector', []), 'engineImage': spec.get('engineImage'),
                        'currentImage': status.get('currentImage'), 'lastBackup': status.get('lastBackup'),
                        'lastBackupAt': status.get('lastBackupAt'),
                        'engines': [{**identity(e), 'state': e.get('status', {}).get('currentState'),
                                     'currentImage': e.get('status', {}).get('currentImage'),
                                     'replicaModes': e.get('status', {}).get('replicaModeMap') or {}}
                                    for e in actual_engines],
                        'replicas': [{**identity(r), 'node': r['spec'].get('nodeID'),
                                      'state': r.get('status', {}).get('currentState'),
                                      'failedAt': r['spec'].get('failedAt'),
                                      'rebuildRetryCount': r['spec'].get('rebuildRetryCount')}
                                     for r in actual_replicas],
                        'completedBackupCount': len(completed),
                        'completedBackups': [{**identity(b), **{k: b.get('status', {}).get(k)
                                             for k in ('backupCreatedAt', 'snapshotName', 'volumeName', 'size')}}
                                            for b in completed]})
    filesystem = {}
    for n in nodes:
        name = n['metadata']['name']
        stats = kubectl('get', '--raw', '/api/v1/nodes/' + name + '/proxy/stats/summary')['node']
        cfg = kubectl('get', '--raw', '/api/v1/nodes/' + name + '/proxy/configz')['kubeletconfig']
        filesystem[name] = {'nodeFS': stats.get('fs'), 'runtimeFS': stats.get('runtime'),
                            'evictionHard': cfg.get('evictionHard'),
                            'imageGCHighThresholdPercent': cfg.get('imageGCHighThresholdPercent'),
                            'imageGCLowThresholdPercent': cfg.get('imageGCLowThresholdPercent')}
    result = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'serverVersion': version,
              'nodes': [{**identity(n), 'ready': ready(n),
                         'pressure': [c['type'] for c in n['status'].get('conditions', [])
                                      if c['type'].endswith('Pressure') and c['status'] == 'True']}
                        for n in nodes], 'filesystem': filesystem, 'volumes': volumes,
              'claims': [{**identity(c), 'phase': c.get('status', {}).get('phase'),
                          'volumeName': c['spec'].get('volumeName'),
                          'storageClassName': c['spec'].get('storageClassName')} for c in claims],
              'persistentVolumes': [{**identity(p), 'driver': p['spec'].get('csi', {}).get('driver'),
                                     'volumeHandle': p['spec'].get('csi', {}).get('volumeHandle'),
                                     'reclaimPolicy': p['spec'].get('persistentVolumeReclaimPolicy'),
                                     'claimRef': {k: p['spec'].get('claimRef', {}).get(k)
                                                  for k in ('namespace', 'name', 'uid')}} for p in pvs],
              'longhornNodes': [{**identity(n), 'tags': n['spec'].get('tags', []),
                                  'allowScheduling': n['spec'].get('allowScheduling'),
                                  'disks': {k: {'diskUUID': d.get('diskUUID'),
                                                'storageAvailable': d.get('storageAvailable'),
                                                'storageMaximum': d.get('storageMaximum'),
                                                'storageScheduled': d.get('storageScheduled'),
                                                'storageReserved': n['spec']['disks'][k].get('storageReserved'),
                                                'conditions': [{q: c.get(q) for q in ('type', 'status', 'reason')}
                                                               for c in d.get('conditions', [])]}
                                            for k, d in n.get('status', {}).get('diskStatus', {}).items()}}
                                 for n in data['nodes']],
              'settings': {k: settings.get(k) for k in ('current-longhorn-version', 'default-engine-image',
                            'concurrent-automatic-engine-upgrade-per-node-limit', 'storage-minimal-available-percentage',
                            'storage-over-provisioning-percentage', 'replica-soft-anti-affinity',
                            'allow-empty-node-selector-volume')},
              'systemBackups': [{**identity(b), 'state': b.get('status', {}).get('state'),
                                 'createdAt': b['metadata'].get('creationTimestamp'),
                                 'errorPresent': bool(b.get('status', {}).get('error'))}
                                for b in data['systembackups']],
              'backupTargets': [{**identity(b), 'available': b.get('status', {}).get('available'),
                                  'errorPresent': bool(b.get('status', {}).get('error'))}
                                 for b in data['backuptargets']],
              'backingImages': [{**identity(b), 'disks': {k: v.get('state') for k, v in
                                    b.get('status', {}).get('diskFileStatusMap', {}).items()}}
                                for b in data['backingimages']],
              'engineImages': [{**identity(e), 'image': e['spec'].get('image'),
                                 'state': e.get('status', {}).get('state'),
                                 'nodeDeploymentMap': e.get('status', {}).get('nodeDeploymentMap')}
                                for e in data['engineimages']],
              'instanceManagers': [{**identity(i), 'image': i['spec'].get('image'),
                                     'nodeID': i['spec'].get('nodeID'),
                                     'state': i.get('status', {}).get('currentState')}
                                    for i in data['instancemanagers']]}
    print(json.dumps(result))


def controller(a):
    need(ROOT.is_mount(), 'declared_output_mount_required')
    need(a.output_dir.resolve() == a.output_dir and a.output_dir.parent == REVIEW
         and re.fullmatch('longhorn-preflight[a-z0-9-]*', a.output_dir.name), 'owned_output_scope')
    need(not a.output_dir.exists(), 'earlier_evidence_must_survive')
    need(a.vendor_manifest.resolve() == REVIEW / 'longhorn-v1.13.0.yaml', 'fixed_vendor_source')
    need(a.candidates.resolve() == REVIEW / 'longhorn-1.13.0-candidates.json', 'fixed_candidate_source')
    vendor = a.vendor_manifest.read_bytes()
    need(hashlib.sha256(vendor).hexdigest() == MANIFEST_SHA, 'reviewed_manifest_identity')
    candidate_bytes = a.candidates.read_bytes()
    images = json.loads(candidate_bytes)['images']
    need(len(images) == 14 and len({i['reference'] for i in images}) == 14
         and all(re.fullmatch(r'docker[.]io/longhornio/[a-z0-9.-]+:[A-Za-z0-9._-]+@sha256:[0-9a-f]{64}',
                              i['reference']) for i in images), 'fourteen_digest_bound_vendor_images')
    for fs in (ROOT, Path('/mnt/c')):
        stat = os.statvfs(fs)
        need(stat.f_bavail * stat.f_frsize >= 15 * 1024**3 + 16 * 1024**2, 'controller_free_space_floor')
    os.umask(0o077)
    a.output_dir.mkdir(mode=0o700)
    receipt = {'status': 'started', 'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd',
               'vendorManifestSHA256': MANIFEST_SHA,
               'candidateInventorySHA256': hashlib.sha256(candidate_bytes).hexdigest(),
               'candidateCompressedLayerBytes': sum(i['compressedLayerBytes'] for i in images),
               'candidateImages': [i['reference'] for i in images],
               'compressedSizeIsNotUnpackedBudget': True, 'mutationPerformed': False,
               'secretValuesRead': False, 'upgradeReady': False}
    try:
        command = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                   '-o', 'ConnectTimeout=10', '-i', '/home/brajam/.ssh/id_ed25519',
                   '-p', '2002', 'james@192.168.0.4', 'python3 -B - --remote']
        run = subprocess.run(command, input=Path(__file__).read_bytes(), capture_output=True, timeout=900)
        need(run.returncode == 0, 'live_read_failed_no_mutation')
        need(len(run.stdout) <= 32 * 1024**2, 'bounded_live_receipt')
        live = json.loads(run.stdout)
        (a.output_dir / 'live.json').write_text(json.dumps(live, indent=2) + '\n')
        attached = [v for v in live['volumes'] if v['state'] == 'attached']
        detached = [v for v in live['volumes'] if v['state'] == 'detached']
        actual_rw = lambda v: len(v['engines']) == 1 and v['engines'][0]['state'] == 'running' and list(
            v['engines'][0]['replicaModes'].values()).count('RW') == 2 and len(
                v['engines'][0]['replicaModes']) == 2 and len({r['node'] for r in v['replicas']
                    if r['state'] == 'running' and not r['failedAt']}) == 2
        receipt.update(status='completed', observedUTC=live['UTC'],
                       volumes=len(live['volumes']), claims=len(live['claims']),
                       attachedVolumes=len(attached), detachedVolumes=len(detached),
                       attachedWithoutTwoActualRW=[v['name'] for v in attached if v['replicasDesired'] != 2
                                                  or v['robustness'] != 'healthy' or not actual_rw(v)],
                       volumesWithoutCompletedBackup=[v['name'] for v in live['volumes']
                                                      if not v['completedBackupCount']],
                       detachedWithoutCompletedBackup=[v['name'] for v in detached
                                                       if not v['completedBackupCount']],
                       systemBackupCount=len(live['systemBackups']),
                       requiredUnprovedGates=['Per-node pull/unpack/coexistence budget after concurrent staging',
                         'Current app-consistent and deliberate detached-dataset recovery coverage',
                         'Authenticated off-node readback and independent restore coverage',
                         'Native Secret and volume-encryption-key recovery',
                         'Current completed system backup and qualified forward-recovery procedure'],
                       liveReceiptSHA256=hashlib.sha256((a.output_dir / 'live.json').read_bytes()).hexdigest())
    except Exception as error:
        receipt.update(status='failed', errorCategory=str(error) if isinstance(error, ValueError) else type(error).__name__)
        raise
    finally:
        with (a.output_dir / 'receipt.json').open('x') as out:
            json.dump(receipt, out, indent=2)
            out.write('\n')
        print(json.dumps({k: v for k, v in receipt.items() if k != 'candidateImages'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--remote', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--vendor-manifest', type=Path)
    parser.add_argument('--candidates', type=Path)
    args = parser.parse_args()
    if args.remote:
        remote()
    else:
        need(args.output_dir and args.vendor_manifest and args.candidates, 'controller_paths_required')
        controller(args)
