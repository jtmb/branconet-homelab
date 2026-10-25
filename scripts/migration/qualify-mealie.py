#!/usr/bin/env python3
"""Read-only Mealie cold/live preservation proof; never scales or restarts anything.

Run on the WSL controller. Supply one persistent 32-byte hex HMAC key on stdin.
Raw SQLite/Secret/API values stay in process memory or private verified tmpfs.
All output receipts must be private and outside a Git checkout.
"""
import argparse
import base64
import datetime
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import tarfile
import tempfile

REPO = Path(__file__).resolve().parents[2]
SHARED = REPO / 'k8s-rewrite/ansible-playbook/roles/metube_state_backup/files/metube_state_backup.py'
READER = SHARED.with_name('pod_reader.py')
OLD = 'ghcr.io/mealie-recipes/mealie:v1.0.0-RC1.1@sha256:6df1e795f17af43f082146e471113315487b5f0882f2ee7553d469034d929af1'
IDS = {
    'deployment': 'f0dddcf0-0d07-4b56-a3ec-0cd59d484b93',
    'helmrelease': '2d878107-ff9f-46f6-9260-2e8f3a94e38c',
    'pvc': 'd015a16d-5098-4253-ade1-72d80af87f18',
    'pv': '402d45ec-840b-4a57-9c7e-0cede840539d',
    'node': 'e8d4555f-7cea-445f-b84f-6416964045a9',
    'secret': '8142b20f-d201-44ff-97b8-f72c93d15557',
    'service': '33270f41-30e7-4338-a0b6-4a663ae797e7',
}
MAX_SQL = 128 * 1024**2
HISTORICAL_OBSERVER_SHA256 = '07c6af0a223a994dc49abe26fbcfa1f638dc35094e18922e3fbc743efb9fc9a7'
KNOWN_NODES = {
    'masternode': 'f2df6169-4592-4544-b62c-74d89f598648',
    'workernode1': 'e8d4555f-7cea-445f-b84f-6416964045a9',
    'workernode2': 'eda66e65-f388-4b97-b64f-a709cda81894',
}

# This identical code runs against the authenticated cold copy and the live DB.
# Every table/column/row is included, including sqlite_sequence and credentials.
STATE_SOURCE = r'''
import base64, hashlib, hmac, json, os, sqlite3, time
from pathlib import Path

def need(ok):
    if not ok: raise ValueError('Mealie observation refused')

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()

def mac(key, domain, value):
    return hmac.new(key, canonical(['mealie-preservation-v1', domain, value]), hashlib.sha256).hexdigest()

def cell(value):
    if value is None: return ['null']
    if isinstance(value, bytes): return ['blob', base64.b64encode(value).decode()]
    if isinstance(value, str): return ['text', value]
    if isinstance(value, int): return ['integer', str(value)]
    if isinstance(value, float): return ['real', value.hex()]
    raise ValueError('unsupported SQLite value')

def sql_state(path, key):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 128 * 1024**2)
    end = time.monotonic() + 90
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)
    db.set_progress_handler(lambda: int(time.monotonic() > end), 10000)
    try:
        db.execute('PRAGMA query_only=ON'); db.execute('BEGIN')
        need(db.execute('PRAGMA integrity_check').fetchall() == [('ok',)])
        need(db.execute('PRAGMA foreign_key_check').fetchone() is None)
        schema = db.execute('SELECT type,name,tbl_name,rootpage,sql FROM sqlite_master ORDER BY type,name').fetchall()
        # rootpage is physical allocation, not application schema.
        schema_rows = [[cell(v) for v in row[:3] + row[4:]] for row in schema]
        tables = {}; count = 0; size = 0; critical = {}
        names = [row[1] for row in schema if row[0] == 'table']
        need({'users', 'groups', 'recipes'} <= set(names) and len(names) <= 512)
        for name in names:
            quoted = '"' + name.replace('"', '""') + '"'
            columns = db.execute('PRAGMA table_xinfo(' + quoted + ')').fetchall()
            cursor = db.execute('SELECT * FROM ' + quoted)
            rows = []
            for row in cursor:
                encoded = [cell(v) for v in row]
                size += len(canonical(encoded)); count += 1
                need(count <= 1000000 and size <= 128 * 1024**2 and time.monotonic() <= end)
                rows.append(mac(key, ['row', name], encoded))
            tables[mac(key, 'table-name', name)] = {
                'rows': len(rows), 'columns': mac(key, ['columns', name], columns),
                'content': mac(key, ['table', name], sorted(rows)),
            }
            if name in ['users', 'groups', 'recipes']: critical[name] = len(rows)
        return {'schema': mac(key, 'sqlite-schema', schema_rows), 'tables': tables,
                'critical_counts': critical, 'user_version': db.execute('PRAGMA user_version').fetchone()[0],
                'application_id': db.execute('PRAGMA application_id').fetchone()[0],
                'integrity_ok': True, 'foreign_keys_ok': True, 'total_rows': count}
    finally: db.close()

DB_NAMES = {'data-0/mealie.db', 'data-0/mealie.db-wal', 'data-0/mealie.db-shm'}
LOG_NAME = 'data-0/mealie.log'
MAX_LOG_APPEND = 16 * 1024**2
LOGGER_SHA256 = '0af03695170c7ae0d03083bbbfd81456bdd63a8402057fc0f822c9e0630831ed'

def log_anchor(row, key):
    need(row['kind'] == 'file')
    return {**{k: row[k] for k in ['kind', 'uid', 'gid', 'mode', 'bytes']},
            'name_hmac': mac(key, 'file-name', LOG_NAME),
            'content_hmac': mac(key, ['file-content', LOG_NAME], row['sha256'])}

def log_proofs(path, anchors, key):
    # FileHandler opens in append mode. The pinned implementation has no rotation.
    import stat
    need(len(anchors) <= 3 and not path.is_symlink())
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    result = {}
    try:
        info = os.fstat(fd); need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
        for anchor in anchors:
            need(anchor['name_hmac'] == mac(key, 'file-name', LOG_NAME))
            need([info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)] == [anchor[k] for k in ['uid', 'gid', 'mode']])
            need(anchor['bytes'] <= info.st_size <= anchor['bytes'] + MAX_LOG_APPEND)
            os.lseek(fd, 0, os.SEEK_SET); remaining = anchor['bytes']; digest = hashlib.sha256()
            while remaining:
                block = os.read(fd, min(remaining, 1024**2)); need(block)
                digest.update(block); remaining -= len(block)
            need(mac(key, ['file-content', LOG_NAME], digest.hexdigest()) == anchor['content_hmac'])
            result[mac(key, 'log-anchor', anchor)] = True
        after = os.fstat(fd); current = path.lstat()
        need((after.st_dev, after.st_ino) == (current.st_dev, current.st_ino) == (info.st_dev, info.st_ino))
        need(after.st_size >= info.st_size and current.st_size >= after.st_size)
        for anchor in anchors: need(current.st_size <= anchor['bytes'] + MAX_LOG_APPEND)
        need((after.st_uid, after.st_gid, after.st_mode) == (current.st_uid, current.st_gid, current.st_mode) == (info.st_uid, info.st_gid, info.st_mode))
        return result
    finally: os.close(fd)

def file_state(manifest, key):
    need(not manifest.get('excluded_new_paths') and 'data-0/mealie.db' in manifest['entries'])
    all_files = {}; non_database = {}; database_metadata = {}
    for name, row in manifest['entries'].items():
        need(name == 'data-0' or name.startswith('data-0/'))
        token = mac(key, 'file-name', name)
        metadata = {k: row[k] for k in ['kind', 'uid', 'gid', 'mode']}
        value = dict(metadata)
        for k in ['sha256', 'bytes', 'link']:
            if k in row: value[k] = row[k]
        all_files[token] = mac(key, ['file', name], value)
        if name not in DB_NAMES: non_database[token] = all_files[token]
        elif name == 'data-0/mealie.db': database_metadata[token] = metadata
    return {'all_files': all_files, 'non_database': non_database,
            'database_metadata': database_metadata, 'entries': len(all_files),
            'bytes': manifest['total_file_bytes'],
            'log': log_anchor(manifest['entries'][LOG_NAME], key) if LOG_NAME in manifest['entries'] else None}
'''

# Runs on masternode; Secret values and API bodies never leave node RAM.
MASTER_SOURCE = r'''
import copy, ipaddress, re, resource, socket, subprocess, sys, urllib.request
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
need(socket.gethostname().split('.')[0].lower() == 'masternode')
request = json.loads(sys.stdin.buffer.read(4 * 1024**2 + 1))
key = bytes.fromhex(request['key']); need(len(key) == 32)
ids = request['ids']; image = request['image']; runtime = request['runtime']

def kube(*args, body=None):
    child = subprocess.run(['kubectl', '--request-timeout=25s', '-n', 'mealie', *args],
                           input=body, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=140)
    need(child.returncode == 0 and len(child.stdout) <= 8 * 1024**2)
    return json.loads(child.stdout)

def obj(kind, name, namespace=None):
    return kube(*(['-n', namespace] if namespace else []), 'get', kind, name, '-o', 'json')

def identity(obj, kind):
    need(obj['metadata']['uid'] == ids[kind] and not obj['metadata'].get('deletionTimestamp'))

def ready(obj):
    need(obj['status'].get('observedGeneration', 0) >= obj['metadata']['generation'])

def fence():
    dep = obj('deployment', 'mealie'); identity(dep, 'deployment'); ready(dep)
    need(dep['spec'].get('replicas') == 1)
    need(all(dep['status'].get(k) == 1 for k in ['replicas', 'readyReplicas', 'availableReplicas', 'updatedReplicas']))
    hr = obj('helmrelease', 'mealie', 'flux-system'); identity(hr, 'helmrelease'); ready(hr)
    need(not hr['spec'].get('suspend', False) and hr['spec'].get('values', {}).get('replicaCount') == 1)
    need(hr['spec'].get('targetNamespace') == 'mealie' and hr['spec'].get('releaseName') == 'mealie')
    need(any(c['type'] == 'Ready' and c['status'] == 'True' for c in hr['status'].get('conditions', [])))
    spec = dep['spec']['template']['spec']; containers = spec['containers']
    need(len(containers) == 1 and containers[0]['name'] == 'mealie' and containers[0]['image'] == image)
    c = containers[0]
    need(c.get('envFrom') == [{'secretRef': {'name': 'mealie-runtime'}}] and not c.get('env'))
    need(c['volumeMounts'] == [{'name': 'data-0', 'mountPath': '/app/data'}])
    need(spec['volumes'] == [{'name': 'data-0', 'persistentVolumeClaim': {'claimName': 'mealie-data-0'}}])
    pvc = obj('pvc', 'mealie-data-0'); identity(pvc, 'pvc')
    need(pvc['status']['phase'] == 'Bound' and pvc['spec']['storageClassName'] == 'longhorn')
    volume = 'pvc-' + ids['pvc']; need(pvc['spec']['volumeName'] == volume)
    pv = obj('pv', volume); identity(pv, 'pv')
    need(pv['spec']['claimRef']['uid'] == ids['pvc'] and pv['spec']['csi']['driver'] == 'driver.longhorn.io')
    need(pv['spec']['csi']['volumeHandle'] == volume and pv['spec']['csi']['fsType'] == 'ext4')
    active = []
    for p in kube('get', 'pods', '-o', 'json')['items']:
        if not any(v.get('persistentVolumeClaim', {}).get('claimName') == 'mealie-data-0' for v in p['spec'].get('volumes', [])): continue
        running = any('running' in s.get('state', {}) for k in ['containerStatuses', 'initContainerStatuses', 'ephemeralContainerStatuses'] for s in p['status'].get(k, []))
        if p['status'].get('phase') not in ['Succeeded', 'Failed'] or running: active.append(p)
    need(len(active) == 1); pod = active[0]
    need(not pod['metadata'].get('deletionTimestamp') and pod['status']['phase'] == 'Running')
    need(any(c['type'] == 'Ready' and c['status'] == 'True' for c in pod['status'].get('conditions', [])))
    owner = [o for o in pod['metadata'].get('ownerReferences', []) if o.get('controller')]
    need(len(owner) == 1 and owner[0]['kind'] == 'ReplicaSet')
    rs = obj('replicaset', owner[0]['name']); need(rs['metadata']['uid'] == owner[0]['uid'])
    need(any(o.get('controller') and o['kind'] == 'Deployment' and o['uid'] == ids['deployment'] for o in rs['metadata'].get('ownerReferences', [])))
    cs = pod['status'].get('containerStatuses', []); pc = pod['spec']['containers']
    need(len(cs) == len(pc) == 1 and cs[0]['name'] == pc[0]['name'] == 'mealie' and cs[0]['ready'])
    need(pc[0]['image'] == image and cs[0]['imageID'].rsplit('@', 1)[-1] == runtime)
    # Kubernetes admission adds its standard service-account projection. Verify
    # its complete shape before removing only that mount from the comparison.
    admitted = [v for v in pod['spec']['volumes'] if v['name'].startswith('kube-api-access-')]
    need(len(admitted) == 1 and re.fullmatch(r'kube-api-access-[a-z0-9]{5}', admitted[0]['name']))
    access_name = admitted[0]['name']
    need(admitted[0] == {'name': access_name, 'projected': {'defaultMode': 420, 'sources': [
        {'serviceAccountToken': {'expirationSeconds': 3607, 'path': 'token'}},
        {'configMap': {'items': [{'key': 'ca.crt', 'path': 'ca.crt'}], 'name': 'kube-root-ca.crt'}},
        {'downwardAPI': {'items': [{'fieldRef': {'apiVersion': 'v1', 'fieldPath': 'metadata.namespace'}, 'path': 'namespace'}]}}
    ]}})
    need(pod['spec'].get('serviceAccountName') == 'default')
    need([v for v in pod['spec']['volumes'] if v['name'] != access_name] == spec['volumes'])
    access_mount = {'mountPath': '/var/run/secrets/kubernetes.io/serviceaccount', 'name': access_name, 'readOnly': True}
    need(pc[0]['volumeMounts'] == c['volumeMounts'] + [access_mount] and pc[0].get('envFrom') == c['envFrom'] and not pc[0].get('env'))
    node_name = pod['spec']['nodeName']
    allowed_nodes = request['known_nodes'] if request['mode'] in ['after', 'restart'] else {'workernode1': ids['node']}
    need(node_name in allowed_nodes and not pod['spec'].get('ephemeralContainers') and not pod['spec'].get('initContainers'))
    original_node = obj('node', 'workernode1'); identity(original_node, 'node')
    node = original_node if node_name == 'workernode1' else obj('node', node_name)
    need(node['metadata']['uid'] == allowed_nodes[node_name] and not node['metadata'].get('deletionTimestamp'))
    need(any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions']))
    need(not any(c['status'] == 'True' and c['type'] in ['DiskPressure', 'MemoryPressure', 'PIDPressure', 'NetworkUnavailable'] for c in node['status']['conditions']))
    secret = obj('secret', 'mealie-runtime'); identity(secret, 'secret')
    service = obj('service', 'mealie'); identity(service, 'service')
    ports = service['spec']['ports']
    need(len(ports) == 1 and ports[0]['port'] == ports[0]['targetPort'] == 9000 and ports[0]['protocol'] == 'TCP')
    need(service['spec']['selector'] == {'app': 'mealie'})
    ipaddress.ip_address(service['spec']['clusterIP'])
    normalized = copy.deepcopy(dep['spec']); normalized['template']['spec']['containers'][0]['image'] = '<maintenance-image>'
    # The only annotation allowed to differ is the operator's controlled restart marker.
    annotations = normalized['template'].get('metadata', {}).get('annotations', {})
    annotations.pop('kubectl.kubernetes.io/restartedAt', None)
    if not annotations: normalized['template'].get('metadata', {}).pop('annotations', None)
    release = copy.deepcopy(hr['spec'])
    # This release currently inherits the image from chart values. Preserve its
    # exact spec; only normalize an explicit image override when one exists.
    if 'image' in release['values']:
        img = release['values']['image']
        need(isinstance(img, dict) and set(img) <= {'repository', 'tag', 'digest', 'pullPolicy'})
        release['values']['image'] = {'maintenance_image': True, 'pullPolicy': img.get('pullPolicy')}
    stable = {'deployment': mac(key, 'deployment-spec', normalized), 'helmrelease': mac(key, 'release-spec', release),
              'pvc': mac(key, 'pvc-spec', pvc['spec']), 'pv': mac(key, 'pv-spec', pv['spec']),
              'service': mac(key, 'service-spec', service['spec']), 'identities': ids,
              'secret': mac(key, 'native-secret', {k: secret.get(k) for k in ['type', 'immutable', 'data']})}
    writer = {'pod_uid': pod['metadata']['uid'], 'restart_count': cs[0].get('restartCount', 0),
              'image': image, 'runtime': runtime, 'node': pod['spec']['nodeName'], 'node_uid': node['metadata']['uid']}
    return stable, writer, pod['metadata']['name'], service['spec']['clusterIP']

before, writer, pod_name, address = fence()
state = kube('exec', '-i', pod_name, '-c', 'mealie', '--', 'python', '-B', '-c', request['pod_source'],
             body=canonical({'key': request['key'], 'log_anchors': request['log_anchors']}))
# Read-only public routes only. No login, bootstrap user or fabricated credentials.
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None
client = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
http = {}; routes = None; version = None
for path in ['/', '/api/app/about', '/openapi.json']:
    with client.open('http://' + address + ':9000' + path, timeout=15) as response:
        body = response.read(2 * 1024**2 + 1); need(response.status == 200 and len(body) <= 2 * 1024**2)
        http[path] = {'status': 200, 'bytes': len(body), 'body_hmac': mac(key, ['http', path], base64.b64encode(body).decode())}
        if path == '/api/app/about':
            about = json.loads(body); version = about['version']; need(isinstance(version, str) and 0 < len(version) < 100)
        elif path == '/openapi.json':
            api = json.loads(body)
            pairs = sorted([p, method] for p, methods in api['paths'].items() for method in methods if method.lower() in ['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace'])
            need(len(pairs) > 20); routes = {'count': len(pairs), 'hmac': mac(key, 'api-routes', pairs)}
after, after_writer, after_name, after_address = fence()
need(before == after and writer == after_writer and pod_name == after_name and address == after_address)
print(json.dumps({'stable': before, 'writer': writer, 'state': state, 'http': http,
                  'version_hmac': mac(key, 'application-version', version), 'routes': routes}, sort_keys=True))
'''

exec(STATE_SOURCE)


def load_shared():
    spec = importlib.util.spec_from_file_location('mealie_archive_primitives', SHARED)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def private_path(path, existing=True):
    need(path.is_absolute() and path.resolve() == path)
    need(not any((p / '.git').exists() for p in [path.parent, *path.parent.parents]))
    parent = path.parent.stat()
    need(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid() and not parent.st_mode & 0o077)
    if existing:
        info = path.lstat()
        need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077 and info.st_nlink == 1)
    else: need(not path.exists() and not path.is_symlink())


def read_receipt(path, key, mode):
    private_path(path); need(path.stat().st_size <= 8 * 1024**2)
    result = json.loads(path.read_bytes()); signature = result.pop('receipt_hmac')
    need(hmac.compare_digest(signature, mac(key, 'receipt', result)))
    need(result['mode'] == mode and result['passed'] and result['key_binding'] == mac(key, 'key-binding', IDS))
    return result


def pod_source():
    # Reuse the exact full archive walker, with no exclusions and no app imports.
    reader = READER.read_text(encoding='utf-8').split("if __name__ == '__main__':", 1)[0]
    return STATE_SOURCE + '\n' + reader + r'''
import resource
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
request = json.loads(sys.stdin.buffer.read(4096)); key = bytes.fromhex(request['key']); need(len(key) == 32)
from dotenv import dotenv_values
settings = dict(dotenv_values('/app/.env')); settings.update(os.environ)
need(str(settings.get('PRODUCTION', 'true')).lower() in ['true', '1'])
need(str(settings.get('TESTING', 'false')).lower() in ['false', '0'])
need(settings.get('DB_ENGINE', 'sqlite') == 'sqlite')
need(settings.get('DATA_DIR') in [None, '', '/app/data'])
ROOTS = {'data-0': '/app/data'}; EXCLUDED = set()
logger_source = Path('/app/mealie/core/root_logger.py')
need(logger_source.is_file() and not logger_source.is_symlink() and logger_source.stat().st_size < 65536)
need(hashlib.sha256(logger_source.read_bytes()).hexdigest() == LOGGER_SHA256)
first = inventory(False, True)
database = sql_state(Path('/app/data/mealie.db'), key)
last = inventory(False, False)
# Only SQLite physical state and the source-proven append log may move during the read.
need({n:r for n,r in without_hashes(first)['entries'].items() if n not in DB_NAMES | {LOG_NAME}} ==
     {n:r for n,r in last['entries'].items() if n not in DB_NAMES | {LOG_NAME}})
need(LOG_NAME in first['entries'] and LOG_NAME in last['entries'])
files = file_state(first, key)
proofs = log_proofs(Path('/app/data/mealie.log'), request['log_anchors'] + [files['log']], key)
envfile = Path('/app/.env')
environment = mac(key, 'effective-environment', dict(os.environ))
need(not envfile.exists() or (envfile.is_file() and not envfile.is_symlink() and envfile.stat().st_size <= 1024**2))
envbytes = mac(key, 'dotenv-file', base64.b64encode(envfile.read_bytes()).decode()) if envfile.exists() else None
print(json.dumps({'database': database, 'files': files, 'log_prefix_proofs': proofs,
                  'logger_source_sha256': LOGGER_SHA256, 'dotenv': envbytes, 'environment': environment}, sort_keys=True))
'''


def cold_state(args, key, shared):
    private_path(args.cold_receipt)
    need(shared.file_hash(args.cold_receipt) == args.cold_receipt_sha256 and args.cold_receipt.stat().st_size <= 65536)
    cold = json.loads(args.cold_receipt.read_bytes())
    need(cold['status'] == 'completed' and cold['application'] == cold['namespace'] == 'mealie' and cold['cold_archive_verified'] is True)
    for field, expected in {'deployment_uid': IDS['deployment'], 'helmrelease_uid': IDS['helmrelease'], 'claim_uid': IDS['pvc'],
                            'claim': 'mealie-data-0', 'volume': 'pvc-' + IDS['pvc'], 'original_image': OLD}.items():
        need(cold[field] == expected)
    archive = Path(cold['archive_path']); private_path(archive)
    need(archive.stat().st_size == cold['archive_bytes'] and shared.file_hash(archive) == cold['archive_sha256'])
    pins = [(p, shared.protected(p, p == shared.IDENTITY)) for p in [shared.AGE, shared.IDENTITY]]
    need(shared.file_hash(shared.AGE) == shared.AGE_SHA256 and os.access(shared.AGE, os.X_OK))
    need(any(line.split()[1:3] == ['/dev/shm', 'tmpfs'] for line in Path('/proc/mounts').read_text().splitlines()))
    need(os.statvfs('/dev/shm').f_bavail * os.statvfs('/dev/shm').f_frsize >= MAX_SQL + 16 * 1024**2)

    def decrypt():
        return subprocess.Popen([str(shared.AGE), '-d', '-i', str(shared.IDENTITY), str(archive)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def finish(child):
        trailing = 0
        for block in iter(lambda: child.stdout.read(65536), b''):
            trailing += len(block); need(trailing <= 1024**2 and not any(block))
        need(child.wait(timeout=30) == 0)

    child = decrypt()
    try:
        manifest = shared.verify_archive(child.stdout); finish(child)
    finally:
        if child.poll() is None: child.kill(); child.wait()
    need(hashlib.sha256(shared.canonical(manifest)).hexdigest() == cold['manifest_sha256'])
    selected = {n:r for n,r in manifest['entries'].items() if n in DB_NAMES}
    need('data-0/mealie.db' in selected and all(r['kind'] == 'file' for r in selected.values()))
    need(sum(r['bytes'] for r in selected.values()) <= MAX_SQL)
    with tempfile.TemporaryDirectory(prefix='mealie-acceptance-', dir='/dev/shm') as folder:
        folder = Path(folder); folder.chmod(0o700); seen = set(); child = decrypt()
        try:
            with tarfile.open(fileobj=child.stdout, mode='r|') as bundle:
                for member in bundle:
                    name = member.name.rstrip('/')
                    if name not in selected:
                        if member.isfile():
                            source = bundle.extractfile(member)
                            for block in iter(lambda: source.read(1024**2), b''): pass
                        continue
                    need(name not in seen and member.isfile() and member.size == selected[name]['bytes']); seen.add(name)
                    digest = hashlib.sha256(); source = bundle.extractfile(member)
                    with (folder / Path(name).name).open('xb') as destination:
                        for block in iter(lambda: source.read(1024**2), b''):
                            destination.write(block); digest.update(block)
                    need(digest.hexdigest() == selected[name]['sha256'])
            finish(child); need(seen == set(selected))
            database = sql_state(folder / 'mealie.db', key)
        finally:
            if child.poll() is None: child.kill(); child.wait()
    need(shared.file_hash(archive) == cold['archive_sha256'] and shared.file_hash(args.cold_receipt) == args.cold_receipt_sha256)
    for path, identity in pins: need(shared.protected(path, path == shared.IDENTITY) == identity)
    return {'database': database, 'files': file_state(manifest, key),
            'archive_sha256': cold['archive_sha256'], 'cold_receipt_sha256': args.cold_receipt_sha256}


def files_preserved(old, observed, key):
    new = observed['files']; left = dict(old['non_database']); right = dict(new['non_database'])
    anchor = old.get('log'); current = new.get('log')
    if anchor is not None and current is not None:
        if anchor['name_hmac'] not in left or current['name_hmac'] not in right: return False
        if any(anchor[k] != current[k] for k in ['name_hmac', 'kind', 'uid', 'gid', 'mode']): return False
        if not anchor['bytes'] <= current['bytes'] <= anchor['bytes'] + MAX_LOG_APPEND: return False
        if observed.get('log_prefix_proofs', {}).get(mac(key, 'log-anchor', anchor)) is not True: return False
        left.pop(anchor['name_hmac'], None); right.pop(current['name_hmac'], None)
    return left == right


def compare(cold, baseline, current, key, previous=None):
    failures = []
    for label, left, right in [
        ('native-identities-and-specs', baseline['stable'], current['stable']),
        ('version', baseline['version_hmac'], current['version_hmac']),
        ('API-routes', baseline['routes'], current['routes']),
        ('frontend-root', baseline['http']['/']['body_hmac'], current['http']['/']['body_hmac']),
        ('all-SQLite-tables', cold['database'], current['state']['database']),
        ('database-owner-mode', cold['files']['database_metadata'], current['state']['files']['database_metadata']),
        ('dotenv', baseline['state']['dotenv'], current['state']['dotenv']),
    ]:
        if left != right: failures.append(label)
    if not files_preserved(cold['files'], current['state'], key): failures.append('all-non-database-files')
    if previous:
        old, new = previous['writer'], current['writer']
        if old['image'] != new['image'] or old['runtime'] != new['runtime']: failures.append('restart-image')
        if old['pod_uid'] == new['pod_uid'] and new['restart_count'] <= old['restart_count']: failures.append('restart-not-observed')
        if previous['state']['database'] != current['state']['database']: failures.append('restart-SQLite')
        if not files_preserved(previous['state']['files'], current['state'], key): failures.append('restart-files')
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['baseline', 'cold', 'after', 'restart'])
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--image'); parser.add_argument('--runtime')
    parser.add_argument('--baseline', type=Path); parser.add_argument('--cold', type=Path)
    parser.add_argument('--previous-after', type=Path)
    parser.add_argument('--cold-receipt', type=Path); parser.add_argument('--cold-receipt-sha256')
    args = parser.parse_args(); need(os.name == 'posix')
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); os.umask(0o077)
    raw = sys.stdin.buffer.read(67).strip(); need(re.fullmatch(b'[0-9a-fA-F]{64}', raw) is not None)
    key = bytes.fromhex(raw.decode()); private_path(args.receipt, False)
    source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), SHARED, READER]}
    receipt = {'schema_version': 1, 'mode': args.mode, 'passed': False, 'failures': [],
               'key_binding': mac(key, 'key-binding', IDS), 'sources': source_hashes,
               'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'personal_login_verified': False, 'external_route_verified': False,
               'browser_verified': False, 'restore_executed': False, 'restart_executed_by_helper': False,
               'zero_SQLite_shm_effect_claimed': False}
    try:
        shared = load_shared()
        if args.mode == 'cold':
            need(args.cold_receipt is not None and re.fullmatch('[0-9a-f]{64}', args.cold_receipt_sha256 or ''))
            receipt['state'] = cold_state(args, key, shared)
        else:
            need(re.fullmatch(r'[^\s]+@sha256:[0-9a-f]{64}', args.image or '') is not None)
            need(re.fullmatch(r'sha256:[0-9a-f]{64}', args.runtime or '') is not None)
            if args.mode == 'baseline': need(args.image == OLD and args.runtime == OLD.rsplit('@', 1)[1])
            baseline = cold = previous = None; anchors = []
            if args.mode in ['after', 'restart']:
                need(args.baseline is not None and args.cold is not None)
                if args.mode == 'restart': need(args.previous_after is not None)
                baseline = read_receipt(args.baseline, key, 'baseline'); cold = read_receipt(args.cold, key, 'cold')
                previous = read_receipt(args.previous_after, key, 'after') if args.mode == 'restart' else None
                # Only this exact earlier observer revision may anchor original
                # baseline/cold receipts; both shared readers remain exact.
                expected_sources = dict(source_hashes)
                if baseline['sources'].get('qualify-mealie.py') == HISTORICAL_OBSERVER_SHA256:
                    expected_sources['qualify-mealie.py'] = HISTORICAL_OBSERVER_SHA256
                need(baseline['sources'] == cold['sources'] == expected_sources)
                if previous: need(previous['sources'] == source_hashes)
                anchors = [r['files']['log'] for r in [cold['state'], *([previous['observation']['state']] if previous else [])] if r['files'].get('log') is not None]
            payload = canonical({'key': key.hex(), 'ids': IDS, 'image': args.image, 'runtime': args.runtime, 'pod_source': pod_source(), 'log_anchors': anchors,
                                 'mode': args.mode, 'known_nodes': KNOWN_NODES})
            command = STATE_SOURCE + '\n' + MASTER_SOURCE
            child = subprocess.run(shared.SSH + [shlex.join(['python3', '-B', '-c', command])], input=payload,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=240)
            need(child.returncode == 0 and len(child.stdout) <= 8 * 1024**2)
            receipt['observation'] = json.loads(child.stdout)
            if args.mode in ['after', 'restart']:
                receipt['failures'] = compare(cold['state'], baseline['observation'], receipt['observation'], key, previous['observation'] if previous else None)
                receipt['anchors'] = {'baseline': hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
                                      'cold': hashlib.sha256(args.cold.read_bytes()).hexdigest()}
                if previous:
                    need(previous['anchors']['baseline'] == receipt['anchors']['baseline'] and previous['anchors']['cold'] == receipt['anchors']['cold'])
                    receipt['anchors']['previous_after'] = hashlib.sha256(args.previous_after.read_bytes()).hexdigest()
        need(source_hashes == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), SHARED, READER]})
        receipt['passed'] = not receipt['failures']
    except Exception as error:
        receipt['error_type'] = type(error).__name__; receipt['failures'].append('observation-refused')
    receipt['completed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    receipt['receipt_hmac'] = mac(key, 'receipt', receipt)
    with os.fdopen(os.open(args.receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({'passed': receipt['passed'], 'mode': args.mode, 'failures': receipt['failures']}))
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception: raise SystemExit('Mealie qualification refused; raw details suppressed')
