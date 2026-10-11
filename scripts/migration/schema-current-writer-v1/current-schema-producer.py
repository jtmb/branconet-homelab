"""Root-owned schema-only qualification; callable, no implicit execution."""
import hashlib
import http.client
import json
import math
import os
import pathlib
import re
import selectors
import signal
import ssl
import stat
import subprocess
import time
import uuid

READER_SHA = '89bbb896513122baac84ac8051d30c5a8c7ff90c2b8ecad64414cfb0527d4212'
MANIFEST_SHA = 'ce535e9fc40e692a5badf673aa965cf37d9447a410ed6579feb253c2434f25f7'
IMAGE = 'docker.io/library/bortus@sha256:3b076fb9b7fb64fd760691c0120f29d4e363d4ccb9910a596ff211bfc3ea0879'
DEPLOYMENT_UID = '4deedc67-038a-4f82-a2d4-a83af316f2f6'
CLAIM_UID = '19cc4b60-4536-4d80-8789-e27b5ad48b79'
PV_UID = '89b8b6ec-c932-4686-9890-26df90a5c799'
VOLUME = 'pvc-' + CLAIM_UID
RUNTIME = pathlib.Path('/home/brajam/.local/share/branconet-migration')


class Refused(RuntimeError):
    def __init__(self):
        super().__init__('Current writer schema qualification refused')


def need(ok):
    if not ok:
        raise Refused()


def left(deadline):
    need(type(deadline) in (int, float) and math.isfinite(deadline))
    value = deadline - time.monotonic()
    need(0 < value <= 300)
    return value


def read_owned(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
             and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == 0o600
             and 0 < before.st_size <= limit)
        raw = os.read(fd, limit + 1)
        need(len(raw) == before.st_size and os.read(fd, 1) == b'')
        after = os.fstat(fd)
        named = os.stat(path, follow_symlinks=False)
        fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        need(fields(before) == fields(after) == fields(named))
        return raw
    finally:
        os.close(fd)


class VerifiedAPI:
    def __init__(self, options):
        need(callable(options))
        self.options = options

    def get(self, path, deadline):
        context, headers = self.options()
        need(isinstance(context, ssl.SSLContext) and context.check_hostname
             and context.verify_mode == ssl.CERT_REQUIRED and headers == {})
        conn = http.client.HTTPSConnection('192.168.0.4', 6443,
                                          context=context, timeout=min(10, left(deadline)))
        try:
            conn.connect()
            need(isinstance(conn.sock, ssl.SSLSocket) and bool(conn.sock.getpeercert()))
            conn.sock.settimeout(min(10, left(deadline)))
            conn.request('GET', path, headers={'Accept': 'application/json',
                                               'Accept-Encoding': 'identity'})
            result = conn.getresponse()
            need(result.status == 200 and result.getheader('Content-Encoding', 'identity') == 'identity')
            parts = []
            size = 0
            while True:
                conn.sock.settimeout(min(10, left(deadline)))
                raw = result.read1(min(65536, 8388609 - size))
                if not raw:
                    break
                parts.append(raw)
                size += len(raw)
                need(size <= 8388608)
            value = json.loads(b''.join(parts))
            need(type(value) is dict)
            left(deadline)
            return value
        finally:
            conn.close()


def identity(obj):
    m = obj['metadata']
    need(not m.get('deletionTimestamp'))
    value = {key: m[key] for key in ('name', 'namespace', 'uid', 'resourceVersion')}
    need(all(type(v) is str and v for v in value.values()))
    return value


def snapshot(get, deadline):
    dep = get('/apis/apps/v1/namespaces/bortus/deployments/bortus', deadline)
    claim = get('/api/v1/namespaces/bortus/persistentvolumeclaims/bortus-data', deadline)
    pv = get('/api/v1/persistentvolumes/' + VOLUME, deadline)
    pods = get('/api/v1/namespaces/bortus/pods', deadline)
    need(dep['metadata']['uid'] == DEPLOYMENT_UID and claim['metadata']['uid'] == CLAIM_UID
         and pv['metadata']['uid'] == PV_UID)
    need(not any(x['metadata'].get('deletionTimestamp') for x in (dep, claim, pv)))
    need(claim['status']['phase'] == 'Bound' and claim['spec']['volumeName'] == VOLUME
         and pv['spec']['claimRef']['uid'] == CLAIM_UID
         and pv['spec']['persistentVolumeReclaimPolicy'] == 'Retain'
         and pv['spec']['csi']['driver'] == 'driver.longhorn.io'
         and pv['spec']['csi']['volumeHandle'] == VOLUME)
    need(dep['spec']['replicas'] == dep['status']['readyReplicas'] == dep['status']['availableReplicas'] == 1
         and dep['status']['observedGeneration'] == dep['metadata']['generation']
         and dep['spec']['strategy']['type'] == 'Recreate')
    need(pods['apiVersion'] == 'v1' and pods['kind'] == 'PodList'
         and type(pods['items']) is list and len(pods['items']) <= 10000
         and type(pods['metadata'].get('resourceVersion')) is str
         and bool(pods['metadata']['resourceVersion'])
         and not pods['metadata'].get('continue') and not pods['metadata'].get('remainingItemCount', 0))
    consumers = [p for p in pods['items'] if any(
        v.get('persistentVolumeClaim', {}).get('claimName') == 'bortus-data'
        for v in p['spec'].get('volumes', []))]
    need(len(consumers) == 1)
    pod = consumers[0]
    public = identity(pod)
    need(public['namespace'] == 'bortus' and re.fullmatch(r'bortus-[a-z0-9-]+', public['name']))
    need(pod['status']['phase'] == 'Running' and any(
        c.get('type') == 'Ready' and c.get('status') == 'True'
        for c in pod['status'].get('conditions', [])))
    spec = pod['spec']
    need(len(spec['containers']) == len(dep['spec']['template']['spec']['containers']) == 1)
    container = spec['containers'][0]
    need(container['image'] == dep['spec']['template']['spec']['containers'][0]['image'] == IMAGE)
    statuses = pod['status']['containerStatuses']
    need(len(statuses) == 1 and statuses[0]['name'] == container['name']
         and statuses[0]['imageID'] == IMAGE and statuses[0]['ready'] is True
         and set(statuses[0]['state']) == {'running'})
    owners = [o for o in pod['metadata'].get('ownerReferences', []) if o.get('controller') is True]
    need(len(owners) == 1 and owners[0]['kind'] == 'ReplicaSet'
         and re.fullmatch(r'bortus-[a-z0-9-]+', owners[0]['name']))
    rs = get('/apis/apps/v1/namespaces/bortus/replicasets/' + owners[0]['name'], deadline)
    parents = [o for o in rs['metadata'].get('ownerReferences', []) if o.get('controller') is True]
    need(rs['metadata']['uid'] == owners[0]['uid'] and not rs['metadata'].get('deletionTimestamp')
         and len(parents) == 1 and parents[0]['kind'] == 'Deployment'
         and parents[0]['name'] == 'bortus' and parents[0]['uid'] == DEPLOYMENT_UID)
    mounts = [m for m in container.get('volumeMounts', []) if m.get('mountPath') == '/data']
    need(len(mounts) == 1 and any(v.get('name') == mounts[0]['name']
         and v.get('persistentVolumeClaim', {}).get('claimName') == 'bortus-data'
         for v in spec.get('volumes', [])))
    public['image'] = IMAGE
    stable = {
        'writer': public, 'container': container['name'], 'node': spec['nodeName'],
        'restart_count': statuses[0]['restartCount'],
        'deployment_uid': DEPLOYMENT_UID,
        'template_sha256': hashlib.sha256(json.dumps(dep['spec']['template'], sort_keys=True,
            separators=(',', ':')).encode()).hexdigest(),
        'claim_uid': CLAIM_UID, 'pv_uid': PV_UID,
        'replicaset_uid': rs['metadata']['uid']}
    left(deadline)
    return stable


def node_exec(writer, container, reader, deadline):
    # Fixed public names and code only. Credentials remain in the protected kubeconfig.
    argv = [str(RUNTIME / 'bin/kubectl'), '--kubeconfig', str(RUNTIME / 'admin.conf'),
            '--request-timeout=' + str(max(1, math.floor(left(deadline)))) + 's',
            'exec', '-n', 'bortus', writer['name'], '-c', container, '-i', '--',
            'node', '--no-warnings', '-']
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    selector = None
    output = bytearray()
    errsize = 0
    sent = 0
    try:
        selector = selectors.DefaultSelector()
        for stream, label, event in ((process.stdin, 'stdin', selectors.EVENT_WRITE),
                                    (process.stdout, 'stdout', selectors.EVENT_READ),
                                    (process.stderr, 'stderr', selectors.EVENT_READ)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, event, label)
        while selector.get_map():
            events = selector.select(min(.1, left(deadline)))
            for key, _ in events:
                if key.data == 'stdin':
                    count = os.write(key.fd, reader[sent:sent+4096])
                    sent += count
                    if sent == len(reader):
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                else:
                    raw = os.read(key.fd, 4097)
                    if not raw:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    elif key.data == 'stdout':
                        output.extend(raw)
                        need(len(output) <= 4096)
                    else:
                        # Never retain transport stderr or untrusted error text.
                        errsize += len(raw)
                        need(errsize <= 4096)
        need(process.wait(timeout=left(deadline)) == 0 and errsize == 0 and sent == len(reader))
        return bytes(output)
    finally:
        if selector is not None:
            selector.close()
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
        for stream in (process.stdin, process.stdout, process.stderr):
            if not stream.closed:
                stream.close()


def collect(directory, reader_path, manifest_path, deadline, invocation_started_ns, get, execute=node_exec):
    """Fresh receipt for this invocation only. Tests inject controlled metadata/exec."""
    left(deadline)
    need(type(invocation_started_ns) is int and 0 < invocation_started_ns <= time.monotonic_ns())
    reader = read_owned(reader_path, 65536)
    manifest = read_owned(manifest_path, 65536)
    need(hashlib.sha256(reader).hexdigest() == READER_SHA
         and hashlib.sha256(manifest).hexdigest() == MANIFEST_SHA)
    root = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        initial = os.fstat(root)
        need(initial.st_uid == os.getuid() and stat.S_IMODE(initial.st_mode) == 0o700)
        before = snapshot(get, deadline)
        raw = execute(before['writer'], before['container'], reader, deadline)
        expected = {'abi': 1, 'node_version': 'v22.23.3', 'read_only_requested': True,
                    'schema_migration_count': 7, 'expected_legacy_migrations': True,
                    'migration_checksums_match': True, 'migrations_complete': True,
                    'tables_and_columns_match': True, 'original_table_count': 13,
                    'credential_or_application_rows_read': False}
        need(type(raw) is bytes and len(raw) <= 4096)
        parsed = json.loads(raw)
        need(parsed == expected and all(type(parsed[k]) is type(v) for k, v in expected.items()))
        after = snapshot(get, deadline)
        need(before == after)
        left(deadline)
        receipt = {'abi': 1, 'scope': 'actual-current-writer-schema-metadata-only',
                   'writer': before['writer'], 'migration_count': 7,
                   'unfinished_migration_count': 0, 'rolled_back_migration_count': 0,
                   'historical_migrations_match': True, 'topology_match': True,
                   'writer_unchanged': True, 'collector_source_sha256': READER_SHA,
                   'migration_manifest_sha256': MANIFEST_SHA,
                   'observed_monotonic_ns': time.monotonic_ns(), 'metadata_only': True}
        payload = (json.dumps(receipt, sort_keys=True, separators=(',', ':')) + '\n').encode()
        name = 'schema-metadata-' + uuid.uuid4().hex[:12] + '.json'
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                     | os.O_CLOEXEC, 0o600, dir_fd=root)
        try:
            need(os.write(fd, payload) == len(payload))
            os.fsync(fd)
            created = os.fstat(fd)
        finally:
            os.close(fd)
        os.fsync(root)
        named_root = os.stat(directory, follow_symlinks=False)
        named_file = os.stat(name, dir_fd=root, follow_symlinks=False)
        need((initial.st_dev, initial.st_ino) == (named_root.st_dev, named_root.st_ino)
             and (created.st_dev, created.st_ino) == (named_file.st_dev, named_file.st_ino))
        left(deadline)
        return {'path': str(pathlib.Path(directory) / name),
                'sha256': hashlib.sha256(payload).hexdigest(), 'receipt': receipt}
    finally:
        os.close(root)
