#!/usr/bin/env python3
"""Vaultwarden complete cold archive versus exact migrated SQL and non-DB tree."""
import argparse
import base64
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import tarfile
import tempfile
import uuid

REPO = Path(__file__).resolve().parents[2]
SHARED = REPO / 'k8s-rewrite/ansible-playbook/roles/metube_state_backup/files/metube_state_backup.py'
spec = importlib.util.spec_from_file_location('arr_archive_primitives', SHARED)
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
MAX_SQLITE = 128 * 1024 ** 2
TARGETS = {
    'vaultwarden': {
        'deployment_uid': '668bb3cd-e382-48b0-910f-7440351bc7d1',
        'release_uid': '3022a586-c52e-4dcd-850b-149f6b38b603',
        'claim_uid': '0fb0e918-ea61-43f5-af95-662c12f8ffe8',
        'old': 'vaultwarden/server:latest@sha256:43498a94b22f9563f2a94b53760ab3e710eefc0d0cac2efda4b12b9eb8690664',
        'new': 'docker.io/library/vaultwarden-security-20261023@sha256:c6a9b959228bf484038fe502bc0697e5ca5d2d10a515de47969c2611d36cdb0d',
        'runtime': 'sha256:c6a9b959228bf484038fe502bc0697e5ca5d2d10a515de47969c2611d36cdb0d',
    },
}
OBSERVER = Path(__file__).with_name('vaultwarden-state-observer.py')
SQLITE_SOURCE = OBSERVER.read_text(encoding='utf-8')



def need(value):
    shared.need(value)


def protected(path):
    shared.protected(path, True)
    need(not any((p / '.git').exists() for p in [path.parent, *path.parent.parents]))


def decrypt(archive, children):
    child = subprocess.Popen([str(shared.AGE), '-d', '-i', str(shared.IDENTITY), str(archive)],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    children.append(child)
    return child


def finish_decrypt(child):
    trailing = 0
    for block in iter(lambda: child.stdout.read(65536), b''):
        trailing += len(block)
        need(trailing <= 1024 * 1024 and not any(block))
    need(child.wait(timeout=30) == 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('application', choices=sorted(TARGETS))
    parser.add_argument('--cold-receipt', type=Path, required=True)
    parser.add_argument('--cold-receipt-sha256', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--cold-only', action='store_true', help='Run the destructive-migration preflight before adopting the new writer')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    need(args.apply and os.name == 'posix')
    os.umask(0o077)
    key = sys.stdin.buffer.read(4097).rstrip(b'\r\n')
    need(32 <= len(key) <= 4096 and b'\n' not in key and b'\r' not in key)
    need(any(line.split()[1:3] == ['/dev/shm', 'tmpfs'] for line in Path('/proc/mounts').read_text().splitlines()))
    protected(args.cold_receipt)
    need(shared.file_hash(args.cold_receipt) == args.cold_receipt_sha256 and args.cold_receipt.stat().st_size <= 65536)
    cold = json.loads(args.cold_receipt.read_bytes())
    target = TARGETS[args.application]
    claim = args.application + '-data-0'
    need(cold['status'] == 'completed' and cold['application'] == args.application and cold['cold_archive_verified'] is True)
    for name in ('deployment_uid', 'claim_uid', 'helmrelease_uid', 'original_image'):
        expected = target[{'helmrelease_uid': 'release_uid', 'original_image': 'old'}.get(name, name)]
        need(cold[name] == expected)
    need(cold['namespace'] == 'vaultwarden' and cold['claim'] == claim and cold['volume'] == 'pvc-' + target['claim_uid'])
    archive = Path(cold['archive_path']); protected(archive)
    archive_identity = shared.protected(archive, True)
    need(archive.stat().st_size == cold['archive_bytes'] and shared.file_hash(archive) == cold['archive_sha256'])
    pins = [(p, shared.protected(p, p == shared.IDENTITY)) for p in [shared.AGE, shared.IDENTITY]]
    need(shared.file_hash(shared.AGE) == shared.AGE_SHA256 and os.access(shared.AGE, os.X_OK))
    output = args.output_dir
    need(output.is_absolute() and output.resolve() == output and str(output).startswith('/home/brajam/') and output != REPO and REPO not in output.parents)
    need(not any((p / '.git').exists() for p in [output, *output.parents]))
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = output.lstat(); need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077)
    run_id = uuid.uuid4().hex
    run = output / (args.application + '-sqlite-' + run_id); run.mkdir(mode=0o700)
    receipt = {'schema_version': 1, 'application': args.application, 'status': 'started',
               'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'cold_receipt_sha256': args.cold_receipt_sha256, 'archive_sha256': cold['archive_sha256'],
               'writer_scaled': False, 'nas_or_secrets_mounted': False, 'login_2fa_or_client_sync_accepted': False, 'temporary_pod_deleted': False,
               'full_application_accepted': False, 'zero_shm_metadata_effect_claimed': False}
    source_hashes = {str(p): shared.file_hash(p) for p in [Path(__file__).resolve(), SHARED, OBSERVER]}
    receipt['source_sha256'] = source_hashes
    children = []; reader = None

    def save():
        tmp = run / ('receipt-' + uuid.uuid4().hex + '.tmp')
        with tmp.open('x') as stream:
            json.dump(receipt, stream, sort_keys=True, indent=2); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, run / 'receipt.json')

    def call(argv, body=None, timeout=60):
        child = subprocess.Popen(shared.SSH + [shlex.join(argv)], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        children.append(child)
        data, _ = child.communicate(body, timeout=timeout)
        need(child.returncode == 0 and len(data) <= shared.MAX_METADATA)
        return data

    def kube(*argv, body=None, timeout=60):
        return call(['kubectl', '--request-timeout=30s', '-n', 'vaultwarden', *argv], body, timeout)

    def get(kind, name=None, namespace='vaultwarden'):
        return json.loads(call(['kubectl', '--request-timeout=30s', '-n', namespace, 'get', kind,
                                *([name] if name else []), '-o', 'json']))

    def fence():
        dep = get('deployment', args.application); pvc = get('pvc', claim)
        release = get('helmrelease', args.application, 'flux-system')
        need(release['metadata']['uid'] == target['release_uid'] and not release['metadata'].get('deletionTimestamp'))
        need(not release['spec'].get('suspend', False) and release['spec'].get('releaseName') == args.application and release['spec'].get('targetNamespace') == 'vaultwarden')
        need(release['spec'].get('values', {}).get('replicaCount') == 1 and release['status'].get('observedGeneration', 0) >= release['metadata']['generation'])
        need(any(c['type'] == 'Ready' and c['status'] == 'True' for c in release['status'].get('conditions', [])))
        need(dep['metadata']['uid'] == target['deployment_uid'] and not dep['metadata'].get('deletionTimestamp'))
        need(dep['spec'].get('replicas', 1) == 1 and dep['status'].get('observedGeneration', 0) >= dep['metadata']['generation'])
        need(all(dep['status'].get(k, 0) == 1 for k in ['replicas', 'updatedReplicas', 'readyReplicas', 'availableReplicas']))
        container = dep['spec']['template']['spec']['containers']; need(len(container) == 1 and container[0]['name'] == args.application and container[0]['image'] == target['new'])
        need(any(m['name'] == 'data-0' and m['mountPath'] == '/data' and not m.get('subPath') and not m.get('subPathExpr') and not m.get('readOnly', False) for m in container[0]['volumeMounts']))
        need(any(v['name'] == 'data-0' and v.get('persistentVolumeClaim', {}).get('claimName') == claim for v in dep['spec']['template']['spec']['volumes']))
        need(pvc['metadata']['uid'] == target['claim_uid'] and not pvc['metadata'].get('deletionTimestamp') and pvc['status']['phase'] == 'Bound')
        need(pvc['spec'].get('storageClassName') == 'longhorn' and pvc['spec']['volumeName'] == 'pvc-' + target['claim_uid'])
        active = []
        for pod in get('pods')['items']:
            if reader and pod['metadata']['uid'] == reader['uid']: continue
            if not any(v.get('persistentVolumeClaim', {}).get('claimName') == claim for v in pod['spec'].get('volumes', [])): continue
            running = any('running' in s.get('state', {}) for k in ['containerStatuses', 'initContainerStatuses', 'ephemeralContainerStatuses'] for s in pod['status'].get(k, []))
            if pod['status'].get('phase') not in ['Failed', 'Succeeded'] or running: active.append(pod)
        need(len(active) == 1)
        writer = active[0]; need(not writer['metadata'].get('deletionTimestamp') and writer['status']['phase'] == 'Running')
        need(any(c['type'] == 'Ready' and c['status'] == 'True' for c in writer['status'].get('conditions', [])))
        owner = [o for o in writer['metadata'].get('ownerReferences', []) if o.get('controller')]; need(len(owner) == 1 and owner[0]['kind'] == 'ReplicaSet')
        rs = get('replicaset', owner[0]['name']); need(rs['metadata']['uid'] == owner[0]['uid'])
        need(any(o.get('controller') and o['kind'] == 'Deployment' and o['uid'] == target['deployment_uid'] for o in rs['metadata'].get('ownerReferences', [])))
        wc = writer['spec']['containers']; ws = writer['status'].get('containerStatuses', [])
        need(len(wc) == len(ws) == 1 and wc[0]['name'] == ws[0]['name'] == args.application and wc[0]['image'] == target['new'] and ws[0]['ready'])
        runtime = ws[0].get('imageID', '').rsplit('@', 1)[-1]
        need(runtime in [target['runtime'], target['new'].rsplit('@', 1)[-1]])
        need(any(m['name'] == 'data-0' and m['mountPath'] == '/data' and not m.get('subPath') and not m.get('subPathExpr') for m in wc[0]['volumeMounts']))
        need(any(v['name'] == 'data-0' and v.get('persistentVolumeClaim', {}).get('claimName') == claim for v in writer['spec']['volumes']))
        node = get('node', writer['spec']['nodeName'])
        need(not node['spec'].get('unschedulable', False) and any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions']))
        need(not any(c['type'] in ['DiskPressure', 'MemoryPressure', 'PIDPressure', 'NetworkUnavailable'] and c['status'] == 'True' for c in node['status']['conditions']))
        return {'deployment_uid': target['deployment_uid'], 'generation': dep['metadata']['generation'],
                'helmrelease_uid': target['release_uid'], 'helmrelease_generation': release['metadata']['generation'],
                'pvc_uid': target['claim_uid'], 'pod_uid': writer['metadata']['uid'], 'pod_name': writer['metadata']['name'],
                'image': target['new'], 'runtime_digest': runtime, 'restart_count': ws[0].get('restartCount', 0),
                'node': writer['spec']['nodeName'], 'node_uid': node['metadata']['uid']}

    save()
    try:
        receipt['operation'] = 'full_authenticated_archive_verification'; save()
        child = decrypt(archive, children)
        manifest = shared.verify_archive(child.stdout); finish_decrypt(child)
        need(hashlib.sha256(shared.canonical(manifest)).hexdigest() == cold['manifest_sha256'])
        names = {'data-0/db.sqlite3' + suffix for suffix in ['', '-wal', '-shm']}
        selected = {name: row for name, row in manifest['entries'].items() if name in names}
        need('data-0/db.sqlite3' in selected and all(row['kind'] == 'file' for row in selected.values()))
        need(sum(row['bytes'] for row in selected.values()) <= MAX_SQLITE)
        need(os.statvfs('/dev/shm').f_bavail * os.statvfs('/dev/shm').f_frsize >= MAX_SQLITE + 16 * 1024 ** 2)
        namespace = {'__name__': 'vaultwarden_state_observer'}; exec(SQLITE_SOURCE, namespace)
        domain = {'application': args.application, 'deployment_uid': target['deployment_uid'], 'pvc_uid': target['claim_uid']}
        receipt['operation'] = 'cold_sqlite_tmpfs_observation'; save()
        with tempfile.TemporaryDirectory(prefix=args.application + '-sqlite-', dir='/dev/shm') as folder:
            folder = Path(folder); folder.chmod(0o700)
            child = decrypt(archive, children); seen = set(); total = 0
            with tarfile.open(fileobj=child.stdout, mode='r|') as bundle:
                for member in bundle:
                    name = member.name.rstrip('/')
                    if name not in selected:
                        if member.isfile():
                            source = bundle.extractfile(member)
                            for block in iter(lambda: source.read(shared.CHUNK), b''): pass
                        continue
                    need(name not in seen and member.isfile() and member.size == selected[name]['bytes'])
                    seen.add(name); total += member.size; need(total <= MAX_SQLITE)
                    destination = folder / Path(name).name; digest = hashlib.sha256()
                    source = bundle.extractfile(member)
                    with destination.open('xb') as out:
                        for block in iter(lambda: source.read(shared.CHUNK), b''):
                            out.write(block); digest.update(block)
                    need(digest.hexdigest() == selected[name]['sha256'])
            finish_decrypt(child); need(seen == set(selected))
            baseline = namespace['fingerprint'](folder / 'db.sqlite3', key, domain)
        receipt['cold'] = baseline
        cold_files = namespace['files_from_manifest'](manifest, key, domain)
        receipt['cold_non_database_files'] = cold_files
        if args.cold_only:
            need(shared.protected(archive, True) == archive_identity and shared.file_hash(archive) == cold['archive_sha256'])
            need(shared.file_hash(args.cold_receipt) == args.cold_receipt_sha256)
            for path, digest in source_hashes.items(): need(shared.file_hash(Path(path)) == digest)
            for path, identity in pins: need(shared.protected(path, path == shared.IDENTITY) == identity)
            receipt.update(status='cold-preflight-completed', operation='cold-preflight-completed',
                           original_archive_schema_safe_for_four_known_migrations=True,
                           live_reader_created=False, completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
            save()
            print(json.dumps({'status': 'cold-preflight-completed', 'application': args.application,
                              'receipt': str(run / 'receipt.json')}))
            return 0
        receipt['operation'] = 'ready_writer_identity_fence'; save()
        before = fence(); receipt['writer'] = before
        name = 'sqlite-' + args.application + '-' + run_id[:12]
        pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name, 'namespace': 'vaultwarden', 'labels': {'migration-task': 'vaultwarden-state-read', 'preservation-run': run_id}},
               'spec': {'nodeName': before['node'], 'restartPolicy': 'Never', 'activeDeadlineSeconds': 600, 'automountServiceAccountToken': False,
                        'securityContext': {'runAsUser': 1000, 'runAsGroup': 1000, 'runAsNonRoot': True, 'seccompProfile': {'type': 'RuntimeDefault'}},
                        'containers': [{'name': 'reader', 'image': shared.OLD, 'imagePullPolicy': 'IfNotPresent', 'command': ['python3', '-B', '-c', 'import time;time.sleep(600)'],
                                        'resources': {'requests': {'cpu': '10m', 'memory': '32Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}},
                                        'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}},
                                        'volumeMounts': [{'name': 'state', 'mountPath': '/source', 'readOnly': True}]}],
                        'volumes': [{'name': 'state', 'persistentVolumeClaim': {'claimName': claim, 'readOnly': True}}]}}
        receipt['operation'] = 'create_owned_readonly_reader'; save()
        created = json.loads(kube('create', '-f', '-', '-o', 'json', body=shared.canonical(pod)))
        reader = {'name': name, 'uid': created['metadata']['uid']}; receipt['temporary_pod'] = reader; save()
        kube('wait', 'pod/' + name, '--for=condition=Ready', '--timeout=180s', timeout=200)
        def check_reader():
            current = get('pod', name); need(current['metadata']['uid'] == reader['uid'] and not current['metadata'].get('deletionTimestamp'))
            ps = current['spec']; c = ps['containers']; cs = current['status'].get('containerStatuses', [])
            need(current['status']['phase'] == 'Running' and ps['nodeName'] == before['node'] and ps.get('automountServiceAccountToken') is False and not ps.get('initContainers') and not ps.get('ephemeralContainers'))
            need(ps['securityContext'] == pod['spec']['securityContext'] and ps['volumes'] == pod['spec']['volumes'])
            need(len(c) == len(cs) == 1 and c[0]['image'] == shared.OLD and cs[0].get('imageID') == shared.OLD and cs[0]['ready'])
            for field in ['command', 'securityContext', 'volumeMounts', 'resources']:
                need(c[0][field] == pod['spec']['containers'][0][field])
            need(not c[0].get('env') and not c[0].get('envFrom'))
        check_reader(); need(fence() == before)
        receipt['operation'] = 'live_readonly_wal_snapshot_to_ram'; save()
        program = SQLITE_SOURCE + """
try:
 import sys
 raw=sys.stdin.buffer.read(4*1024*1024+1); check(len(raw)<=4*1024*1024); request=json.loads(raw)
 key=base64.b64decode(request['key'],validate=True); check(32<=len(key)<=4096)
 result=fingerprint(Path('/source/db.sqlite3'),key,request['domain'],request['baseline'],True)
 files=live_files('/source',key,request['domain'])
 print(json.dumps({'database':result,'non_database_files':files},sort_keys=True))
except Exception: raise SystemExit(1)
"""
        payload = shared.canonical({'key': base64.b64encode(key).decode(), 'domain': domain, 'baseline': baseline})
        need(len(payload) <= 4 * 1024 ** 2)
        observed = json.loads(kube('exec', '-i', name, '-c', 'reader', '--', 'python3', '-B', '-c', program,
                                   body=payload, timeout=250))
        live = observed['database']
        for field in ['quick_check', 'tables', 'migration_versions', 'key_binding']:
            need(live[field] == baseline[field])
        need(live['four_exact_additive_migrations'] is True)
        need(observed['non_database_files'] == cold_files)
        check_reader(); need(fence() == before)
        need(shared.protected(archive, True) == archive_identity and shared.file_hash(archive) == cold['archive_sha256'])
        need(shared.file_hash(args.cold_receipt) == args.cold_receipt_sha256)
        for path, digest in source_hashes.items(): need(shared.file_hash(Path(path)) == digest)
        for path, identity in pins: need(shared.protected(path, path == shared.IDENTITY) == identity)
        receipt.update(live=live, sqlite_integrity_passed=True,
                       all_original_tables_rows_columns_preserved=True,
                       four_exact_additive_migrations_verified=True,
                       non_database_files_preserved=True,
                       live_non_database_files=observed['non_database_files'])
        receipt['operation'] = 'delete_only_verified_reader'; save()
        options = {'apiVersion': 'v1', 'kind': 'DeleteOptions', 'preconditions': {'uid': reader['uid']}, 'propagationPolicy': 'Foreground'}
        kube('delete', '--raw', '/api/v1/namespaces/vaultwarden/pods/' + name, '-f', '-', body=shared.canonical(options))
        kube('wait', 'pod/' + name, '--for=delete', '--timeout=120s', timeout=140)
        receipt.update(status='completed', operation='completed', temporary_pod_deleted=True,
                       completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()); save()
        print(json.dumps({'status': 'completed', 'application': args.application, 'receipt': str(run / 'receipt.json')})); return 0
    except Exception as error:
        receipt.update(status='failed', error_type=type(error).__name__, completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()); save()
        print(json.dumps({'status': 'failed', 'operation': receipt.get('operation'), 'receipt': str(run / 'receipt.json'), 'error_type': type(error).__name__})); return 1
    finally:
        key = None
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=10)
                except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=10)


if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception: raise SystemExit('Vaultwarden state observation refused; raw values and diagnostics are suppressed')
