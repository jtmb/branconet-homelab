#!/usr/bin/env python3
"""Fixed remote staging program; request credentials enter protected stdin only."""
import hashlib
import contextlib
import json
import os
import pathlib
import re
import stat
import subprocess
import sys
import threading
import uuid

MAX_ARCHIVE = 4 * 1024 ** 3
MAX_METADATA = 8 * 1024 ** 2
CTR = ['sudo', '-n', '/opt/containerd-k8s/bin/ctr', '--address', '/run/containerd-k8s/containerd.sock', '--namespace', 'k8s.io']
INDEX = {'application/vnd.oci.image.index.v1+json', 'application/vnd.docker.distribution.manifest.list.v2+json'}
MANIFEST = {'application/vnd.oci.image.manifest.v1+json', 'application/vnd.docker.distribution.manifest.v2+json'}


def require(ok, code):
    if not ok: raise RuntimeError(code)
def digest(raw): return hashlib.sha256(raw).hexdigest()
def sha(value): return type(value) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', value) is not None
def identity(info): return info.st_dev, info.st_ino, info.st_uid, info.st_mode
def file_identity(info): return (*identity(info), info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)
def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate'); result[key] = value
    return result


class NodeRun:
    def __init__(self, home, commit, attempt_id=None):
        require(attempt_id is None or (type(attempt_id) is str and re.fullmatch('[0-9a-f]{12}', attempt_id)), 'attempt')
        self.home = pathlib.Path(home); self.fd = None; self.anchors = []
        self.name = '.bortus-release-preload-' + commit + (('-attempt-' + attempt_id) if attempt_id is not None else '')
        self.path = self.home / self.name
        try:
            require(self.home.is_absolute() and '..' not in self.home.parts and len(self.home.parts) <= 32, 'home')
            fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            self.anchors.append((pathlib.Path('/'), fd, identity(os.fstat(fd))))
            path = pathlib.Path('/')
            for part in self.home.parts[1:]:
                fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                path /= part; info = os.fstat(fd); self.anchors.append((path, fd, identity(info)))
                require(info.st_uid in (0, os.getuid()) and stat.S_IMODE(info.st_mode) & 0o022 == 0, 'home')
            require(os.fstat(fd).st_uid == os.getuid(), 'home')
            os.mkdir(self.name, 0o700, dir_fd=fd); os.fsync(fd)
            self.fd = os.open(self.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            self.owned_identity = identity(os.fstat(self.fd)); self.record_identity = None
            self.record = {'phase': 'receiving', 'source_commit': commit,
                'owner': str(uuid.uuid4()), 'runtime_qualified': False}
            if attempt_id is not None: self.record['attempt_id'] = attempt_id
            self.save()
        except Exception: self.close(); raise

    def owned(self):
        require(self.fd is not None and all(identity(path.lstat()) == old and identity(os.fstat(fd)) == old
            for path, fd, old in self.anchors) and identity(self.path.lstat()) == self.owned_identity and
            identity(os.fstat(self.fd)) == self.owned_identity, 'ownership')
        if self.record_identity is not None:
            require(file_identity(os.stat('record.json', dir_fd=self.fd, follow_symlinks=False)) == self.record_identity, 'record_ownership')
    def create(self, name):
        self.owned(); return os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.fd)
    def save(self):
        self.owned(); name = 'record-' + uuid.uuid4().hex + '.next'; fd = self.create(name)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as out:
                raw = (json.dumps(self.record) + '\n').encode(); require(len(raw) <= MAX_METADATA, 'record_bound')
                out.write(raw); out.flush(); os.fsync(fd)
            self.owned(); os.replace(name, 'record.json', src_dir_fd=self.fd, dst_dir_fd=self.fd); os.fsync(self.fd)
            self.record_identity = file_identity(os.fstat(fd)); self.owned()
        finally: os.close(fd)
    def close(self):
        descriptors = ([self.fd] if self.fd is not None else []) + [fd for _, fd, _ in reversed(self.anchors)]
        self.fd = None; self.anchors = []; failed = False
        for fd in descriptors:
            try: os.close(fd)
            except OSError: failed = True
        require(not failed, 'close')


def command(run, stage, argv, cap=MAX_METADATA, timeout=30, capture=True):
    # Metadata (especially image config.Env) stays bounded in memory, never a raw log.
    out_fd = run.create(stage + '.stdout') if not capture else None
    try: err_fd = run.create(stage + '.stderr')
    except Exception:
        if out_fd is not None: os.close(out_fd)
        raise
    captured = bytearray()
    with contextlib.ExitStack() as stack:
        out = stack.enter_context(os.fdopen(out_fd, 'wb')) if out_fd is not None else None
        err = stack.enter_context(os.fdopen(err_fd, 'wb'))
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE if capture else out,
            stderr=err, start_new_session=False)
        # sudo -n must share sudo -S -v's session timestamp context. Cancellation
        # targets only this owned PID; never signal the shared process group.
        failed = []; reader = None
        if capture:
            def receive():
                try:
                    total = 0
                    for chunk in iter(lambda: process.stdout.read(65536), b''):
                        total += len(chunk); require(total <= cap, 'metadata_bound'); captured.extend(chunk)
                except Exception: failed.append(True); process.kill()
                finally: process.stdout.close()
            reader = threading.Thread(target=receive, daemon=True); reader.start()
        try:
            code = process.wait(timeout=timeout); run.record[stage + '_exit_code'] = code
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=10); raise RuntimeError('command_timeout') from None
        finally:
            if reader: reader.join(timeout=5)
            if out: out.flush(); os.fsync(out.fileno())
            err.flush(); os.fsync(err.fileno())
        require(not failed and (reader is None or not reader.is_alive()), 'metadata_stream')
    require(code == 0, 'command_exit')
    return bytes(captured) if capture else b''


def content(run, stage, expected, invoke, expected_size=None):
    require(sha(expected), 'content_digest')
    raw = invoke(run, stage, CTR + ['content', 'get', expected])
    require(len(raw) <= MAX_METADATA and (expected_size is None or len(raw) == expected_size) and
        'sha256:' + digest(raw) == expected, 'content_identity')
    value = json.loads(raw, object_pairs_hook=unique); require(type(value) is dict, 'content_shape'); return value


def runtime_image(run, tag, request, invoke):
    raw = invoke(run, 'images-after', CTR + ['images', 'list'], cap=1024 * 1024)
    rows = [row for row in image_rows(raw) if row[0] in (tag, 'docker.io/library/' + tag)]
    require(len(rows) == 1 and len(rows[0]) >= 3 and sha(rows[0][2]), 'runtime_tag')
    root_digest = rows[0][2]; root = content(run, 'runtime-root', root_digest, invoke)
    require(type(root.get('schemaVersion')) is int and root['schemaVersion'] == 2, 'runtime_schema')
    media = root.get('mediaType'); selected = root_digest
    if media in INDEX:
        require(type(root.get('manifests')) is list and len(root['manifests']) <= 64, 'runtime_index')
        candidates = []
        for item in root['manifests']:
            require(type(item) is dict and sha(item.get('digest')) and type(item.get('size')) is int and
                0 < item['size'] <= MAX_METADATA and not item.get('urls'), 'runtime_descriptor')
            platform = item.get('platform')
            require(type(platform) is dict, 'runtime_platform')
            if platform.get('os') == 'linux' and platform.get('architecture') == 'amd64' and platform.get('variant') in (None, ''):
                candidates.append(item)
        require(len(candidates) == 1, 'runtime_platform_ambiguity'); selected = candidates[0]['digest']
        root = content(run, 'runtime-selected', selected, invoke, candidates[0]['size']); media = root.get('mediaType')
    require(media in MANIFEST and type(root.get('schemaVersion')) is int and root['schemaVersion'] == 2 and type(root.get('config')) is dict and
        root['config'].get('digest') == request['config_image_id'] and not root['config'].get('urls') and
        type(root['config'].get('size')) is int and 0 < root['config']['size'] <= MAX_METADATA and
        type(root.get('layers')) is list and len(root['layers']) <= 1024, 'runtime_manifest')
    require(all(type(e) is dict and sha(e.get('digest')) and type(e.get('size')) is int and 0 <= e['size'] <= MAX_ARCHIVE and
        not e.get('urls') for e in root['layers']) and
        [e['digest'] for e in root['layers']] == request['layer_blob_digests'], 'runtime_layers')
    config = content(run, 'runtime-config', request['config_image_id'], invoke, root['config']['size'])
    require(config.get('os') == 'linux' and config.get('architecture') == 'amd64' and type(config.get('config')) is dict and
        all(config['config'].get('Labels', {}).get(k) == v for k, v in request['labels'].items()) and
        type(config.get('rootfs')) is dict and config['rootfs'].get('type') == 'layers' and
        config['rootfs'].get('diff_ids') == request['ordered_diff_ids'], 'runtime_config')
    return root_digest, selected


def image_rows(raw):
    require(type(raw) is bytes and len(raw) <= 1024 * 1024, 'runtime_inventory_bound')
    lines = raw.decode('utf-8').splitlines()
    require(lines and lines[0].split()[:3] == ['REF', 'TYPE', 'DIGEST'] and len(lines) <= 16385, 'runtime_inventory')
    rows = [line.split() for line in lines[1:] if line.split()]
    require(all(len(row) >= 3 and sha(row[2]) for row in rows), 'runtime_inventory')
    return rows


def authenticate(request, authorize):
    password = request.pop('sudo_password'); failure = False; authorized = None
    try:
        require(type(password) is str and 0 < len(password.encode()) <= 4096 and not any(c in password for c in '\0\r\n'), 'authorization')
        if authorize is None:
            authorized = subprocess.run(['sudo', '-S', '-p', '', '-v'], input=password.encode() + b'\n',
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False, start_new_session=False)
            require(authorized.returncode == 0, 'authorization')
        else: require(authorize(password), 'authorization')
    except Exception: failure = True
    finally: password = None; authorized = None
    if failure: raise RuntimeError('authorization')


def receive(request, source, home, invoke=command, authorize=None):
    fields = {'sudo_password', 'source_commit', 'config_image_id', 'labels',
        'archive_sha256', 'archive_bytes', 'layer_blob_digests', 'ordered_diff_ids'}
    require(type(request) is dict and set(request) in (fields, fields | {'attempt_id'}) and
        ('attempt_id' not in request or (type(request['attempt_id']) is str and re.fullmatch('[0-9a-f]{12}', request['attempt_id']))) and
        type(request['source_commit']) is str and re.fullmatch(r'[0-9a-f]{40}', request['source_commit']) and
        sha(request['config_image_id']) and type(request['archive_bytes']) is int and 0 < request['archive_bytes'] <= MAX_ARCHIVE and
        type(request['archive_sha256']) is str and re.fullmatch(r'[0-9a-f]{64}', request['archive_sha256']) and
        type(request['labels']) is dict and set(request['labels']) == {'org.opencontainers.image.revision',
            'io.branconet.bortus.source-tree', 'io.branconet.bortus.context-sha256',
            'io.branconet.bortus.manifest-sha256', 'io.branconet.bortus.build-owner'} and
        request['labels']['org.opencontainers.image.revision'] == request['source_commit'] and
        type(request['labels']['io.branconet.bortus.source-tree']) is str and
        re.fullmatch(r'[0-9a-f]{40}', request['labels']['io.branconet.bortus.source-tree']) and
        all(type(request['labels'][key]) is str and re.fullmatch(r'[0-9a-f]{64}', request['labels'][key]) for key in
            ('io.branconet.bortus.context-sha256', 'io.branconet.bortus.manifest-sha256')) and
        all(type(request[k]) is list and len(request[k]) <= 1024 and all(sha(e) for e in request[k])
            for k in ('layer_blob_digests', 'ordered_diff_ids')) and
        len(request['layer_blob_digests']) == len(request['ordered_diff_ids']), 'request')
    try: owner = str(uuid.UUID(request['labels']['io.branconet.bortus.build-owner']))
    except (ValueError, TypeError, AttributeError): owner = None
    require(owner == request['labels']['io.branconet.bortus.build-owner'] and owner is not None, 'request_owner')
    authenticate(request, authorize)
    run = NodeRun(home, request['source_commit'], request.get('attempt_id')); dispatched = False; failure = None
    try:
        run.record.update(request); run.save(); tag = 'bortus:release-' + request['source_commit']
        existing = invoke(run, 'images-before', CTR + ['images', 'list'], cap=1024 * 1024)
        rows = image_rows(existing)
        require(not any(row[0] in (tag, 'docker.io/library/' + tag) for row in rows), 'existing_tag')
        fd = run.create('image.tar'); hashed = hashlib.sha256(); count = 0
        with os.fdopen(fd, 'w+b') as archive:
            while True:
                chunk = source.read(min(65536, request['archive_bytes'] - count + 1))
                if not chunk: break
                count += len(chunk); require(count <= request['archive_bytes'], 'archive_bound'); archive.write(chunk); hashed.update(chunk)
            require(count == request['archive_bytes'] and hashed.hexdigest() == request['archive_sha256'], 'archive_identity')
            archive.flush(); os.fsync(archive.fileno()); os.fsync(run.fd)
            pinned = file_identity(os.fstat(archive.fileno()))
            second = image_rows(invoke(run, 'images-preimport', CTR + ['images', 'list'], cap=1024 * 1024))
            require(not any(row[0] in (tag, 'docker.io/library/' + tag) for row in second), 'existing_tag')
            run.record['phase'] = 'pending'; run.save(); run.owned()
            require(file_identity(os.fstat(archive.fileno())) == pinned and
                file_identity(os.stat('image.tar', dir_fd=run.fd, follow_symlinks=False)) == pinned, 'archive_changed')
            dispatched = True
            invoke(run, 'import', CTR + ['images', 'import', str(run.path / 'image.tar')], timeout=1200, capture=False)
            require(file_identity(os.fstat(archive.fileno())) == pinned and
                file_identity(os.stat('image.tar', dir_fd=run.fd, follow_symlinks=False)) == pinned, 'archive_changed')
        run.record['import_exit_code'] = 0
        root, selected = runtime_image(run, tag, request, invoke)
        result = {k: request[k] for k in ('source_commit', 'config_image_id', 'archive_sha256', 'archive_bytes', 'labels')}
        if 'attempt_id' in request: result['attempt_id'] = request['attempt_id']
        result.update(phase='completed', runtime_manifest_digest=root, selected_manifest_digest=selected,
                      import_exit_code=0, runtime_qualified=False)
        run.record.update(result); run.save()
    except Exception:
        failure = True; run.record.update(phase='uncertain' if dispatched else 'refused', failure='node_staging_failed')
        try: run.save()
        except Exception: pass
    finally: run.close()
    if failure: raise RuntimeError('node_staging_failed')
    return result


def main():
    try:
        raw = sys.stdin.buffer.readline(256 * 1024 + 1)
        require(0 < len(raw) <= 256 * 1024 and raw.endswith(b'\n'), 'request_bound')
        request = json.loads(raw, object_pairs_hook=unique); raw = None
        result = receive(request, sys.stdin.buffer, pathlib.Path.home()); print(json.dumps(result), flush=True); return 0
    except Exception:
        print('Node image staging refused or uncertain; inspect protected receipt.', file=sys.stderr); return 1


if __name__ == '__main__': raise SystemExit(main())
