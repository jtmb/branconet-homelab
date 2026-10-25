#!/usr/bin/env python3
"""One Radarr/Sonarr cold-archive versus live SQLite Users comparison."""
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
    'radarr': {
        'deployment_uid': '3e2719e0-f7f5-4cf5-8ba9-9d94a68302f0',
        'release_uid': 'bbd87da8-8746-4e3e-8c11-d8ae3a5d1504',
        'claim_uid': '7f07da4f-a34e-4bd0-a4a0-90b94f5a0fec',
        'old': 'linuxserver/radarr:latest@sha256:ca43905eaf2dd11425efdcfe184892e43806b1ae0a830440c825cecbc2629cfb',
        'new': 'docker.io/linuxserver/radarr:latest@sha256:fc0ae3c50f8128b97e84381903ec8d6845c3a569641cb7117c124376cccb57c1',
        'runtime': 'sha256:a466ac12c33425ec22ec4bb0d71c3edb79fd5e5f845bba0e2901c1a6aa59b075',
    },
    'sonarr': {
        'deployment_uid': '30d19648-2af7-48cd-9d72-e9d41f4ecb20',
        'release_uid': '8568f6b9-f6a8-4ed2-9720-ce84c3a592e0',
        'claim_uid': 'ff5158b3-cecf-46f9-b85e-ad8566cb9068',
        'old': 'linuxserver/sonarr:latest@sha256:76414c033f290d3c9f1f9dfad71150abe71d92592369a3377a5903d579e6e2b2',
        'new': 'docker.io/linuxserver/sonarr:latest@sha256:889dcc58c6aea859033985894b519b2e6b1e55d92527ed123f9f52e42ae7c97b',
        'runtime': 'sha256:c5a8178dc6d1f2e2c34b5e254716230d9769af34b4090e61cc116dc055a3083f',
    },
}

# Closed security overlays retain every original resource UID and the Users code.
# Cold source is the already-adopted vendor image; final target is one exact local image.
SECURITY_IMAGES = {
    'radarr': 'docker.io/library/radarr-security-20261023@sha256:b79e4e0e3bec790e4f8a48cca83fd5b34e1267f672e27496cf1b95e732fed83c',
    'sonarr': 'docker.io/library/sonarr-security-20261023@sha256:7d297bbadfd74dd2c346b48d32530d6fa632bc902739d4f7aaadbd898375f593',
}

# Identical fingerprint code runs on tmpfs cold files and in the RO reader.
# It never logs values. Only the live path uses the SQLite backup API, into RAM.
SQLITE_SOURCE = r'''
import base64,hashlib,hmac,json,sqlite3,time
from pathlib import Path
def check(value):
    if not value: raise ValueError('sqlite-observation-refused')
def compact(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def quoted(value):
    return '"'+value.replace('"','""')+'"'
def cell(value):
    if value is None: return ['null']
    if isinstance(value,int): return ['int',str(value)]
    if isinstance(value,float): return ['float',value.hex()]
    if isinstance(value,str):
        check(len(value.encode())<=1024*1024); return ['text',value]
    if isinstance(value,bytes):
        check(len(value)<=1024*1024); return ['blob',base64.b64encode(value).decode()]
    raise ValueError('sqlite-value-domain')
def fingerprint(path,key,domain,selected=None,live=False):
    deadline=time.monotonic()+90
    source=sqlite3.connect(Path(path).as_uri()+'?mode=ro',uri=True,timeout=5,isolation_level=None)
    memory=None
    try:
        source.execute('PRAGMA query_only=ON')
        source.execute('PRAGMA busy_timeout=5000')
        source.execute('PRAGMA temp_store=MEMORY')
        source.execute('BEGIN')
        source.execute('SELECT count(*) FROM sqlite_master').fetchone()
        page_size=source.execute('PRAGMA page_size').fetchone()[0]
        pages=source.execute('PRAGMA page_count').fetchone()[0]
        check(page_size*pages<=128*1024*1024)
        connection=source
        if live:
            memory=sqlite3.connect(':memory:',isolation_level=None)
            def progress(status,remaining,total):
                check(time.monotonic()<deadline and total*page_size<=128*1024*1024)
            source.backup(memory,pages=64,progress=progress,sleep=0.05)
            source.rollback(); source.close(); source=None
            connection=memory
            connection.execute('PRAGMA query_only=ON')
            connection.execute('PRAGMA temp_store=MEMORY')
            connection.execute('BEGIN')
        connection.set_progress_handler(lambda: 1 if time.monotonic()>=deadline else 0,10000)
        check(connection.execute('PRAGMA quick_check').fetchall()==[('ok',)])
        tables=connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND lower(name)='users'").fetchall()
        check(len(tables)==1)
        table=tables[0][0]
        info=connection.execute('PRAGMA table_xinfo('+quoted(table)+')').fetchall()
        all_columns=[r[1] for r in info]
        check(0<len(all_columns)<=64 and len(set(all_columns))==len(all_columns))
        ids=[r[1] for r in info if r[1].lower()=='id' and r[5]==1]
        check(len(ids)==1 and len([r for r in info if r[5]])==1)
        id_column=ids[0]
        columns=all_columns if selected is None else selected
        check(isinstance(columns,list) and len(set(columns))==len(columns) and set(columns)<=set(all_columns) and id_column in columns)
        rows=connection.execute('SELECT '+','.join(quoted(c) for c in columns)+' FROM '+quoted(table)+' ORDER BY '+quoted(id_column)).fetchmany(1001)
        check(len(rows)<=1000)
        id_index=columns.index(id_column)
        identifiers=[r[id_index] for r in rows]
        check(all(isinstance(value,int) for value in identifiers) and len(set(identifiers))==len(identifiers))
        values=[[cell(v) for v in row] for row in rows]
        check(sum(len(compact(v)) for row in values for v in row)<=8*1024*1024)
        def mac(value): return hmac.new(key,compact(['arr-sqlite-v1',domain,value]),hashlib.sha256).hexdigest()
        result={'quick_check':'ok','table':table,'columns':columns,'all_current_columns':all_columns,'ids':identifiers,'count':len(rows),
            'key_binding':mac('key-binding'),'all_rows_hmac':mac(['all-rows',columns,values]),
            'per_column':{c:mac(['column',c,[[identifiers[i],row[j]] for i,row in enumerate(values)]]) for j,c in enumerate(columns)},
            'per_row_fields':{str(identifiers[i]):{c:mac(['field',identifiers[i],c,row[j]]) for j,c in enumerate(columns)} for i,row in enumerate(values)},
            'snapshot_page_count':pages,'snapshot_page_size':page_size,'sqlite_version':sqlite3.sqlite_version,'live_backup_to_memory':live}
        check(len(compact(result))<=8*1024*1024)
        return result
    finally:
        if source is not None: source.close()
        if memory is not None: memory.close()
'''


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
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--security-patch', action='store_true', help='Finite same-app local image profile; requires media-security-20261025 cold receipt')
    args = parser.parse_args()
    need(args.apply and os.name == 'posix')
    os.umask(0o077)
    key = sys.stdin.buffer.read(4097).rstrip(b'\r\n')
    need(32 <= len(key) <= 4096 and b'\n' not in key and b'\r' not in key)
    need(any(line.split()[1:3] == ['/dev/shm', 'tmpfs'] for line in Path('/proc/mounts').read_text().splitlines()))
    protected(args.cold_receipt)
    need(shared.file_hash(args.cold_receipt) == args.cold_receipt_sha256 and args.cold_receipt.stat().st_size <= 65536)
    cold = json.loads(args.cold_receipt.read_bytes())
    target = dict(TARGETS[args.application])
    if args.security_patch:
        target['old'] = target['new']
        target['new'] = SECURITY_IMAGES[args.application]
        target['runtime'] = target['new'].rsplit('@', 1)[1]
        need(cold.get('generation') == 'media-security-20261025')
    claim = args.application + '-data-0'
    need(cold['status'] == 'completed' and cold['application'] == args.application and cold['cold_archive_verified'] is True)
    for name in ('deployment_uid', 'claim_uid', 'helmrelease_uid', 'original_image'):
        expected = target[{'helmrelease_uid': 'release_uid', 'original_image': 'old'}.get(name, name)]
        need(cold[name] == expected)
    need(cold['namespace'] == 'plex' and cold['claim'] == claim and cold['volume'] == 'pvc-' + target['claim_uid'])
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
    receipt = {'schema_version': 1, 'application': args.application, 'security_patch': args.security_patch, 'status': 'started',
               'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'cold_receipt_sha256': args.cold_receipt_sha256, 'archive_sha256': cold['archive_sha256'],
               'writer_scaled': False, 'nas_or_secrets_mounted': False, 'temporary_pod_deleted': False,
               'full_application_accepted': False, 'zero_shm_metadata_effect_claimed': False}
    source_hashes = {str(p): shared.file_hash(p) for p in [Path(__file__).resolve(), SHARED]}
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
        return call(['kubectl', '--request-timeout=30s', '-n', 'plex', *argv], body, timeout)

    def get(kind, name=None, namespace='plex'):
        return json.loads(call(['kubectl', '--request-timeout=30s', '-n', namespace, 'get', kind,
                                *([name] if name else []), '-o', 'json']))

    def fence():
        dep = get('deployment', args.application); pvc = get('pvc', claim)
        release = get('helmrelease', args.application, 'flux-system')
        need(release['metadata']['uid'] == target['release_uid'] and not release['metadata'].get('deletionTimestamp'))
        need(not release['spec'].get('suspend', False) and release['spec'].get('releaseName') == args.application and release['spec'].get('targetNamespace') == 'plex')
        need(release['spec'].get('values', {}).get('replicaCount') == 1 and release['status'].get('observedGeneration', 0) >= release['metadata']['generation'])
        need(any(c['type'] == 'Ready' and c['status'] == 'True' for c in release['status'].get('conditions', [])))
        need(dep['metadata']['uid'] == target['deployment_uid'] and not dep['metadata'].get('deletionTimestamp'))
        need(dep['spec'].get('replicas', 1) == 1 and dep['status'].get('observedGeneration', 0) >= dep['metadata']['generation'])
        need(all(dep['status'].get(k, 0) == 1 for k in ['replicas', 'updatedReplicas', 'readyReplicas', 'availableReplicas']))
        container = dep['spec']['template']['spec']['containers']; need(len(container) == 1 and container[0]['name'] == args.application and container[0]['image'] == target['new'])
        need(any(m['name'] == 'data-0' and m['mountPath'] == '/config' and not m.get('subPath') and not m.get('subPathExpr') and not m.get('readOnly', False) for m in container[0]['volumeMounts']))
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
        need(any(m['name'] == 'data-0' and m['mountPath'] == '/config' and not m.get('subPath') and not m.get('subPathExpr') for m in wc[0]['volumeMounts']))
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
        names = {'data-0/' + args.application + '.db' + suffix for suffix in ['', '-wal', '-shm']}
        selected = {name: row for name, row in manifest['entries'].items() if name in names}
        need('data-0/' + args.application + '.db' in selected and all(row['kind'] == 'file' for row in selected.values()))
        need(sum(row['bytes'] for row in selected.values()) <= MAX_SQLITE)
        need(os.statvfs('/dev/shm').f_bavail * os.statvfs('/dev/shm').f_frsize >= MAX_SQLITE + 16 * 1024 ** 2)
        namespace = {}; exec(SQLITE_SOURCE, namespace)
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
            baseline = namespace['fingerprint'](folder / (args.application + '.db'), key, domain)
        receipt['cold'] = baseline
        receipt['operation'] = 'ready_writer_identity_fence'; save()
        before = fence(); receipt['writer'] = before
        name = 'sqlite-' + args.application + '-' + run_id[:12]
        pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name, 'namespace': 'plex', 'labels': {'migration-task': 'arr-sqlite-read', 'preservation-run': run_id}},
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
        program = SQLITE_SOURCE + '''
try:
 import sys
 raw=sys.stdin.buffer.read(16385); check(len(raw)<=16384); request=json.loads(raw)
 key=base64.b64decode(request['key'],validate=True); check(32<=len(key)<=4096)
 app=request['application']; check(app in ['radarr','sonarr'])
 result=fingerprint(Path('/source')/(app+'.db'),key,request['domain'],request['columns'],True)
 print(json.dumps(result,sort_keys=True))
except Exception: raise SystemExit(1)
'''
        live = json.loads(kube('exec', '-i', name, '-c', 'reader', '--', 'python3', '-B', '-c', program,
                               body=shared.canonical({'key': base64.b64encode(key).decode(), 'application': args.application, 'domain': domain, 'columns': baseline['columns']}), timeout=120))
        for field in ['quick_check', 'table', 'columns', 'ids', 'count', 'key_binding', 'all_rows_hmac', 'per_column', 'per_row_fields']:
            need(live[field] == baseline[field])
        if args.security_patch:
            # Same application version: no legacy schema-addition allowance is needed.
            need(live['all_current_columns'] == baseline['all_current_columns'])
        check_reader(); need(fence() == before)
        need(shared.protected(archive, True) == archive_identity and shared.file_hash(archive) == cold['archive_sha256'])
        need(shared.file_hash(args.cold_receipt) == args.cold_receipt_sha256)
        for path, digest in source_hashes.items(): need(shared.file_hash(Path(path)) == digest)
        for path, identity in pins: need(shared.protected(path, path == shared.IDENTITY) == identity)
        receipt.update(live=live, sqlite_integrity_passed=True, users_all_original_columns_preserved=True,
                       original_column_count=len(baseline['columns']), additional_current_columns=sorted(set(live['all_current_columns']) - set(baseline['columns'])))
        receipt['operation'] = 'delete_only_verified_reader'; save()
        options = {'apiVersion': 'v1', 'kind': 'DeleteOptions', 'preconditions': {'uid': reader['uid']}, 'propagationPolicy': 'Foreground'}
        kube('delete', '--raw', '/api/v1/namespaces/plex/pods/' + name, '-f', '-', body=shared.canonical(options))
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
    except Exception: raise SystemExit('Arr SQLite observation refused; raw values and diagnostics are suppressed')
