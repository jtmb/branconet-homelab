"""Read-only current-58 checkpoint gate. Runs on the existing WSL controller."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-i',
       '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']


def need(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def backup_identity(status):
    # Controller ownership, replica address and lastSyncedAt can change on drain.
    # Bind durable backup content/source fields, not transient reconciler state.
    keys = ['backupCreatedAt', 'backupTargetName', 'compressionMethod', 'labels',
            'size', 'snapshotCreatedAt', 'snapshotName', 'state', 'url',
            'volumeBackingImageName', 'volumeCreated', 'volumeName', 'volumeSize']
    return {key: status[key] for key in keys if key in status}


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def owned_file(value):
    p = Path(value)
    need(p.is_absolute() and p.resolve() == p and ROOT in p.parents and p.is_file(), 'Evidence must stay in existing task root')
    return p


def fresh(value):
    age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    need(dt.timedelta(0) <= age <= dt.timedelta(hours=6), 'Checkpoint or backup exceeds six-hour freshness bound')


def get(kind):
    r = subprocess.run(SSH + [shlex.join(['kubectl', 'get', kind, '-A', '-o', 'json'])],
                       capture_output=True, text=True, timeout=60)
    need(r.returncode == 0, 'Read-only cluster inventory unavailable')
    return json.loads(r.stdout)['items']


def public_object(kind, namespace, name):
    r = subprocess.run(SSH + [shlex.join(['kubectl', '-n', namespace, 'get', kind, name, '-o', 'json'])],
                       capture_output=True, text=True, timeout=60)
    need(r.returncode == 0, 'Read-only source verification unavailable')
    return json.loads(r.stdout)


def ephemeral_sources():
    sources = []
    for namespace, name in [('ingenium', 'ingenium-bootstrap-installer'), ('plex', 'xteve-threadfin-compatibility')]:
        cm = public_object('configmap', namespace, name)
        sources.append({'namespace': namespace, 'name': name, 'uid': cm['metadata']['uid'],
                        'dataSHA256': digest(cm.get('data', {}))})
    need([s['dataSHA256'] for s in sources] == [
        '4421464289a4a9cdcb9ed3a417c4ac2ec3cfd89d4ea8c4145eae619c28a413ac',
        '1bd191142714ae69f376fecb060f1742f263aedbf41b2aeec8964ebcf08253a1'],
        'Ephemeral regeneration source differs from inspected current source')
    for namespace, name, volumes in [
            ('ingenium', 'ingenium', {
                'runtime-secrets': ('128Mi', {'/run/ingenium-secrets', '/runtime-secrets-owned'}),
                'shared-memory': ('256Mi', {'/dev/shm'}),
                'bootstrap-owned': ('1Mi', {'/bootstrap-owned', '/run/ingenium-bootstrap/api-token',
                    '/run/ingenium-bootstrap/learning-credential', '/run/ingenium-bootstrap/opencode-server-password',
                    '/run/ingenium-bootstrap/email-encryption-key'})}),
            ('plex', 'xteve', {'guide-gateway-temp': ('16Mi', {'/proxy-tmp', '/tmp'})})]:
        spec = public_object('deployment', namespace, name)['spec']['template']['spec']
        for volume, (size, paths) in volumes.items():
            obj = [v for v in spec['volumes'] if v['name'] == volume]
            need(len(obj) == 1 and obj[0].get('emptyDir') == {'medium': 'Memory', 'sizeLimit': size}, 'Unreviewed ephemeral volume definition')
            actual = {m['mountPath'] for c in spec['containers'] + spec.get('initContainers', [])
                      for m in c.get('volumeMounts', []) if m['name'] == volume}
            need(actual == paths, 'Unreviewed ephemeral mount path')
        if name == 'ingenium':
            init = next(c for c in spec['initContainers'] if c['name'] == 'prepare-bootstrap-ownership')
            need(init['command'] == ['python3', '-B', '/bootstrap-installer/install-bootstrap.py'], 'Bootstrap regeneration command changed')
            need(next(v for v in spec['volumes'] if v['name'] == 'bootstrap')['secret']['secretName'] == 'ingenium-bootstrap', 'Native bootstrap source changed')
    return sources


def project(items):
    rows = []
    for o in items:
        m, s = o['metadata'], o.get('status', {})
        row = {'kind': o['kind'], 'namespace': m.get('namespace', ''), 'name': m['name'],
               'uid': m['uid'], 'specSHA256': digest(o.get('spec', {}))}
        if o['kind'] in ('PersistentVolume', 'PersistentVolumeClaim'):
            row['phase'] = s.get('phase')
        if o['kind'] == 'Volume':
            # Attachment node is deliberately not pinned: ordinary drain relocates it.
            spec = dict(o['spec'])
            spec.pop('nodeID', None)
            row['specSHA256'] = digest(spec)
            row.update(state=s.get('state'), robustness=s.get('robustness'))
        rows.append(row)
    return sorted(rows, key=lambda r: (r['kind'], r['namespace'], r['name']))


def validate_inventory(rows):
    for kind, count in [('PersistentVolumeClaim', 58), ('PersistentVolume', 58), ('Volume', 44)]:
        selected = [r for r in rows if r['kind'] == kind]
        need(len(selected) == count and len({r['uid'] for r in selected}) == count, 'Current accepted identity count mismatch: ' + kind)
        if kind != 'Volume':
            need(all(r['phase'] == 'Bound' for r in selected), 'Claim/PV binding changed')
    volumes = [r for r in rows if r['kind'] == 'Volume']
    need(sum(r['state'] == 'attached' and r['robustness'] == 'healthy' for r in volumes) == 28, 'Require all 28 active volumes healthy')
    need(sum(r['state'] == 'detached' for r in volumes) == 16, 'Require 16 retained offline volumes')


def validate(manifest, rows, backups, control):
    need(manifest['schema'] == 'kernel202-current58-v1', 'Unknown checkpoint schema')
    fresh(manifest['capturedAt'])
    validate_inventory(rows)
    need(rows == manifest['identities'], 'Original claim/PV/volume/controller identity or specification changed')
    active = {r['name']: r for r in rows if r['kind'] == 'Volume' and r['state'] == 'attached'}
    supplied = manifest['nativeBackups']
    need(len(supplied) == 28 and {r['volume'] for r in supplied} == set(active), 'Require exactly one native backup for each active volume')
    current = {b['metadata']['name']: b for b in backups}
    for expected in supplied:
        b = current.get(expected['name'])
        need(b is not None and b['metadata']['uid'] == expected['uid'], 'Native backup identity missing')
        status = b['status']
        need(status.get('state') == 'Completed' and not status.get('error') and status.get('volumeName') == expected['volume'], 'Native backup not completed for original volume')
        need(expected['volumeUID'] == active[expected['volume']]['uid'], 'Backup volume binding changed')
        need(digest(backup_identity(status)) == expected['statusSHA256'], 'Native backup durable metadata changed')
        fresh(status['backupCreatedAt'])
        fresh(status['snapshotCreatedAt'])
    need(control['status'] == 'completed' and control['scope'] == 'cluster-maintenance-control-plane', 'Control-plane backup incomplete')
    for key in ['authenticated_archive_verified', 'snapshot_footer_verified', 'snapshot_status_verified', 'off_node_operator_copy']:
        need(control.get(key) is True, 'Control-plane backup verification missing: ' + key)
    need(control.get('remote_plaintext_retained') is False, 'Control-plane plaintext cleanup incomplete')
    fresh(control['completed_at'])
    need(manifest['controlPlane']['archiveSHA256'] == control['archive_sha256'], 'Control-plane archive binding mismatch')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture', action='store_true', help='Print identity draft only; not backup qualification')
    p.add_argument('--manifest')
    p.add_argument('--sha256')
    a = p.parse_args()
    kinds = 'persistentvolumeclaims,persistentvolumes,volumes.longhorn.io,deployments,statefulsets,daemonsets'
    rows = project(get(kinds))
    validate_inventory(rows)
    node_uids = {n['metadata']['name']: n['metadata']['uid'] for n in get('nodes')}
    sources = ephemeral_sources()
    if a.capture:
        print(json.dumps({'schema': 'kernel202-current58-v1', 'capturedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
                          'identities': rows, 'clusterNodes': node_uids, 'ephemeralSources': sources,
                          'nativeBackups': [], 'controlPlane': {}}, indent=2))
        return
    path = owned_file(a.manifest)
    need(file_hash(path) == a.sha256, 'Checkpoint SHA256 differs from reviewed authority')
    manifest = json.loads(path.read_text())
    need(manifest['clusterNodes'] == node_uids, 'Original cluster node identities changed')
    need(manifest['ephemeralSources'] == sources, 'Reviewed ephemeral regeneration source changed')
    cp = manifest['controlPlane']
    receipt = owned_file(cp['receipt'])
    need(file_hash(receipt) == cp['receiptSHA256'], 'Control-plane receipt SHA256 mismatch')
    control = json.loads(receipt.read_text())
    nas_file = owned_file(cp['nasProof'])
    need(file_hash(nas_file) == cp['nasProofSHA256'], 'NAS readback receipt changed')
    nas = json.loads(nas_file.read_text())
    need(nas['fullIndependentReadback'] is True and nas['ciphertextMatchesAuthenticatedProducer'] is True
         and nas['sourceUnchanged'] is True and nas['plaintextWritten'] is False
         and nas['sourceReceiptSHA256'] == cp['receiptSHA256']
         and nas['archiveSHA256'] == control['archive_sha256']
         and nas['bytes'] == control['archive_bytes'], 'Independent NAS ciphertext binding missing')
    fresh(nas['UTC'])
    need(control['source'] == cp['source'], 'Control-plane backup source binding changed')
    etcd = public_object('pod', 'kube-system', 'etcd-masternode')
    container = next(c for c in etcd['spec']['containers'] if c['name'] == 'etcd')
    status = next(c for c in etcd['status']['containerStatuses'] if c['name'] == 'etcd')
    need(container['image'] == cp['source']['image'] and status['imageID'] == cp['source']['image_id']
         and status['ready'] is True and etcd['spec']['nodeName'] == 'masternode', 'Control-plane backup image/source no longer matches')
    archive = owned_file(control['archive_path'])
    need(archive.stat().st_size == control['archive_bytes'] and file_hash(archive) == control['archive_sha256'], 'Control-plane encrypted archive missing or changed')
    validate(manifest, rows, get('backups.longhorn.io'), control)
    print(json.dumps({'passed': True, 'checkpointSHA256': a.sha256, 'claims': 58, 'volumes': 44,
                      'activeHealthy': 28, 'retainedOffline': 16, 'nativeSecretValuesRead': False}))


if __name__ == '__main__':
    main()
