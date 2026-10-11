#!/usr/bin/env python3
"""Verify an immutable release context and build only on the fixed existing builder."""
import argparse
import datetime
import gzip
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shlex
import stat
import subprocess
import tarfile
import uuid

spec = importlib.util.spec_from_file_location('bortus_release_context_contract',
    pathlib.Path(__file__).with_name('prepare-bortus-release-context.py'))
producer = importlib.util.module_from_spec(spec); spec.loader.exec_module(producer)
MAX_ARCHIVE_BYTES = producer.MAX_TOTAL_BYTES + 16 * 1024 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ForwardAgent=no',
       '-o', 'ConnectTimeout=15', '-p', '2002', 'james@192.168.0.4']
LABEL_KEYS = ['org.opencontainers.image.revision', 'io.branconet.bortus.source-tree',
              'io.branconet.bortus.context-sha256', 'io.branconet.bortus.manifest-sha256',
              'io.branconet.bortus.build-owner']


class BuildRefused(RuntimeError):
    def __init__(self, code):
        self.code = code; super().__init__('Release image operation refused: ' + code)


def require(ok, code):
    if not ok: raise BuildRefused(code)


def digest(raw): return hashlib.sha256(raw).hexdigest()
def stream_hash(stream):
    hashed = hashlib.sha256()
    for chunk in iter(lambda: stream.read(65536), b''): hashed.update(chunk)
    return hashed.hexdigest()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def hexid(value, count): return type(value) is str and re.fullmatch('[0-9a-f]{' + str(count) + '}', value) is not None
def identity(info): return info.st_dev, info.st_ino, info.st_uid, info.st_mode
def input_identity(info):
    return (*identity(info), info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'json_duplicate'); result[key] = value
    return result


def valid_path(name):
    require(type(name) is str and 0 < len(name.encode('utf-8')) <= 4096 and not name.startswith('/') and
        '\\' not in name and ':' not in name and all(p not in ('', '.', '..') for p in name.split('/')) and
        not any(ord(c) < 32 or ord(c) == 127 for c in name) and not producer.excluded(name), 'context_path')


class BoundedReader:
    def __init__(self, stream): self.stream, self.count = stream, 0
    def read(self, amount):
        require(0 <= amount <= 65536, 'tar_read_bound')
        raw = self.stream.read(amount); self.count += len(raw)
        require(self.count <= MAX_ARCHIVE_BYTES, 'tar_total_bound')
        return raw


class ContextTarInfo(tarfile.TarInfo):
    def _proc_member(self, archive):
        require(self.type in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.XHDTYPE), 'tar_type')
        require(0 <= self.size <= (8192 if self.type == tarfile.XHDTYPE else producer.MAX_FILE_BYTES), 'tar_size')
        return super()._proc_member(archive)


def verify(context, manifest_raw, commit, context_sha, manifest_sha):
    require(hexid(commit, 40) and hexid(context_sha, 64) and hexid(manifest_sha, 64), 'exact_input')
    require(len(manifest_raw) <= MAX_MANIFEST_BYTES and digest(manifest_raw) == manifest_sha, 'manifest_hash')
    m = json.loads(manifest_raw, object_pairs_hook=unique)
    require(type(m) is dict and set(m) == {'scope', 'source_commit', 'application_tree', 'source_prefix',
        'started_at_utc', 'completed_at_utc', 'context_sha256', 'context_bytes', 'source_bytes', 'included_files',
        'excluded_entries', 'files', 'migrations', 'working_tree_read', 'excluded_payloads_read',
        'dependencies_installed', 'image_built', 'cluster_mutations', 'live_acceptance'}, 'manifest_shape')
    require(all(type(m[k]) is str and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?\+00:00', m[k])
        for k in ('started_at_utc', 'completed_at_utc')), 'manifest_timestamp')
    require(m['scope'] == 'Immutable raw-Git build context only; no image or release acceptance' and
        m['source_commit'] == commit and hexid(m['application_tree'], 40) and m['source_prefix'] == producer.PREFIX and
        m['context_sha256'] == context_sha and all(m[k] is False for k in
        ('working_tree_read', 'excluded_payloads_read', 'dependencies_installed', 'image_built', 'live_acceptance')) and
        type(m['cluster_mutations']) is int and m['cluster_mutations'] == 0, 'manifest_identity')
    require(all(type(m[k]) is int and 0 <= m[k] <= limit for k, limit in
        [('context_bytes', MAX_ARCHIVE_BYTES), ('source_bytes', producer.MAX_TOTAL_BYTES),
         ('included_files', producer.MAX_FILES), ('excluded_entries', producer.MAX_FILES)]) and
        m['included_files'] + m['excluded_entries'] <= producer.MAX_FILES and type(m['files']) is list and
        len(m['files']) == m['included_files'], 'manifest_bound')
    entries, total = {}, 0
    for e in m['files']:
        require(type(e) is dict and set(e) == {'path', 'mode', 'git_blob', 'bytes', 'sha256'}, 'manifest_entry')
        valid_path(e['path'])
        require(e['path'] not in entries and e['mode'] in ('100644', '100755') and hexid(e['git_blob'], 40) and
            hexid(e['sha256'], 64) and type(e['bytes']) is int and 0 <= e['bytes'] <= producer.MAX_FILE_BYTES, 'manifest_entry')
        entries[e['path']] = e; total += e['bytes']
    require(total == m['source_bytes'] and producer.REQUIRED <= set(entries) and
        m['migrations'] == [e for e in m['files'] if e['path'].startswith('prisma/migrations/') and
                            e['path'].endswith('/migration.sql')], 'manifest_inventory')
    context.seek(0); count = 0; hashed = hashlib.sha256()
    while True:
        raw = context.read(65536)
        if not raw: break
        count += len(raw); require(count <= MAX_ARCHIVE_BYTES, 'archive_bound'); hashed.update(raw)
    require(count == m['context_bytes'] and hashed.hexdigest() == context_sha, 'context_hash')
    context.seek(0); seen = set()
    with gzip.GzipFile(fileobj=context, mode='rb') as compressed:
        bounded = BoundedReader(compressed)
        with tarfile.open(fileobj=bounded, mode='r|', tarinfo=ContextTarInfo) as archive:
            for member in archive:
                valid_path(member.name)
                require(member.isfile() and member.name in entries and member.name not in seen and
                    len(seen) < producer.MAX_FILES and member.uid == member.gid == member.mtime == 0 and
                    member.uname == member.gname == '' and not member.linkname and
                    set(member.pax_headers) <= {'path'}, 'tar_member')
                e = entries[member.name]
                require(member.size == e['bytes'] and member.mode == (0o755 if e['mode'] == '100755' else 0o644), 'tar_metadata')
                body = archive.extractfile(member); blob = hashlib.sha1(b'blob ' + str(member.size).encode() + b'\0')
                file_sha = hashlib.sha256(); received = 0
                while True:
                    raw = body.read(65536)
                    if not raw: break
                    received += len(raw); require(received <= member.size, 'tar_size'); blob.update(raw); file_sha.update(raw)
                body.close()
                require(received == member.size and blob.hexdigest() == e['git_blob'] and
                    file_sha.hexdigest() == e['sha256'], 'tar_blob')
                seen.add(member.name)
            # Tar EOF is not permission to ignore hidden members/trailing payload.
            while True:
                raw = archive.fileobj.read(65536)
                if not raw: break
                require(not any(raw), 'tar_trailing')
    require(seen == set(entries), 'tar_inventory')
    context.seek(0)
    return m


class Run:
    """One deterministic per-commit directory; no reopening, overwrite or replay."""
    def __init__(self, parent, commit):
        require(os.name == 'posix' and hexid(commit, 40), 'runtime')
        self.parent, self.name = pathlib.Path(parent), 'bortus-release-' + commit
        self.directory = self.parent / self.name; self.parent_fd = self.fd = None; self.anchors = []
        try:
            require(self.parent.is_absolute() and len(self.parent.parts) <= 32 and
                all(p not in ('.', '..') for p in self.parent.parts[1:]), 'runtime_parent')
            fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            self.anchors.append((pathlib.Path('/'), fd, identity(os.fstat(fd))))
            path = pathlib.Path('/')
            for part in self.parent.parts[1:]:
                fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                path /= part; info = os.fstat(fd); self.anchors.append((path, fd, identity(info)))
                require(info.st_uid in (0, os.getuid()) and stat.S_IMODE(info.st_mode) & 0o022 == 0, 'runtime_parent')
            self.parent_fd = fd
            require(os.fstat(fd).st_uid == os.getuid(), 'runtime_parent')
            os.mkdir(self.name, 0o700, dir_fd=fd); os.fsync(fd)
            self.fd = os.open(self.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            self.run_identity = identity(os.fstat(self.fd)); self.record_identity = None; self.inputs = {}
            self.record = {'scope': 'Immutable BORTUS image build only; no runtime/deployment acceptance',
                'owner': str(uuid.uuid4()), 'source_commit': commit, 'image_tag': 'bortus:release-' + commit,
                'phase': 'validating', 'started_at_utc': now(), 'deployed': False, 'runtime_accepted': False}
            self.save()
        except Exception:
            self.close(); raise

    def owned(self):
        require(self.fd is not None and all(identity(p.lstat()) == info and identity(os.fstat(fd)) == info
            for p, fd, info in self.anchors) and identity(self.directory.lstat()) == self.run_identity and
            identity(os.fstat(self.fd)) == self.run_identity and self.run_identity[-1] & 0o777 == 0o700, 'runtime_ownership')
        if self.record_identity is not None:
            require(input_identity(os.stat('record.json', dir_fd=self.fd, follow_symlinks=False)) == self.record_identity, 'record_ownership')

    def create(self, name):
        self.owned(); return os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.fd)

    def save(self):
        self.owned(); name = 'record-' + uuid.uuid4().hex + '.next'; fd = self.create(name)
        try:
            raw = (json.dumps(self.record, indent=2) + '\n').encode(); require(len(raw) <= MAX_MANIFEST_BYTES, 'record_bound')
            with os.fdopen(fd, 'wb', closefd=False) as stream: stream.write(raw); stream.flush(); os.fsync(fd)
            self.owned()
            os.replace(name, 'record.json', src_dir_fd=self.fd, dst_dir_fd=self.fd); os.fsync(self.fd)
            self.record_identity = input_identity(os.fstat(fd)); self.owned()
        finally: os.close(fd)

    def copy_input(self, source, name, limit):
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        try:
            initial = os.fstat(fd)
            require(stat.S_ISREG(initial.st_mode) and initial.st_uid == os.getuid() and
                stat.S_IMODE(initial.st_mode) & 0o022 == 0 and 0 < initial.st_size <= limit, 'input_file')
            target = self.create(name)
            with os.fdopen(target, 'w+b') as output:
                received = 0
                while True:
                    raw = os.read(fd, min(65536, limit - received + 1))
                    if not raw: break
                    received += len(raw); require(received <= limit, 'input_bound'); output.write(raw)
                latest = os.fstat(fd); current = os.stat(source, follow_symlinks=False)
                require(received == initial.st_size and all((x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns,
                    x.st_uid, x.st_mode) == (initial.st_dev, initial.st_ino, initial.st_size, initial.st_mtime_ns,
                    initial.st_ctime_ns, initial.st_uid, initial.st_mode) for x in (latest, current)), 'input_changed')
                output.flush(); os.fsync(output.fileno())
            os.fsync(self.fd)
            info = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            self.inputs[name] = input_identity(info)
        finally: os.close(fd)

    def open_input(self, name, expected_sha):
        self.owned()
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=self.fd)
        try:
            info = os.fstat(fd)
            require(input_identity(info) == self.inputs[name] and
                input_identity(os.stat(name, dir_fd=self.fd, follow_symlinks=False)) == self.inputs[name], 'input_ownership')
            stream = os.fdopen(fd, 'rb', closefd=False)
            try: require(stream_hash(stream) == expected_sha, 'input_changed')
            finally: stream.close()
            self.check_input(name, fd)
            os.lseek(fd, 0, os.SEEK_SET)
            return os.fdopen(fd, 'rb')
        except Exception:
            os.close(fd); raise

    def check_input(self, name, fd):
        self.owned()
        require(input_identity(os.fstat(fd)) == self.inputs[name] and
            input_identity(os.stat(name, dir_fd=self.fd, follow_symlinks=False)) == self.inputs[name], 'input_changed')

    def close(self):
        descriptors = ([self.fd] if self.fd is not None else []) + [fd for _, fd, _ in reversed(self.anchors)]
        self.fd = None
        self.anchors = []; self.parent_fd = None
        failure = False
        for fd in descriptors:
            try: os.close(fd)
            except OSError: failure = True
        require(not failure, 'descriptor_close')


def execute(run, stage, command, timeout, stdin=None):
    """Only owned SSH child; complete separate logs, actual exit and no automatic retry."""
    run.owned(); out_fd = run.create(stage + '.stdout')
    try: err_fd = run.create(stage + '.stderr')
    except Exception: os.close(out_fd); raise
    result = None
    with os.fdopen(out_fd, 'wb') as out, os.fdopen(err_fd, 'wb') as err:
        try:
            result = subprocess.run(command, stdin=stdin or subprocess.DEVNULL, stdout=out, stderr=err,
                timeout=timeout, check=False, start_new_session=True)
            run.record[stage + '_exit_code'] = result.returncode
        except subprocess.TimeoutExpired:
            run.record[stage + '_exit_code'] = None; run.record[stage + '_timed_out'] = True
            raise BuildRefused('subprocess_timeout') from None
        finally:
            out.flush(); err.flush(); os.fsync(out.fileno()); os.fsync(err.fileno())
            for suffix in ('stdout', 'stderr'):
                with (run.directory / (stage + '.' + suffix)).open('rb') as log:
                    run.record[stage + '_' + suffix + '_sha256'] = stream_hash(log)
    return result.returncode


def remote(argv): return SSH + [shlex.join(argv)]


def build(context, manifest, commit, context_sha, manifest_sha, runtime_parent, invoke=execute):
    require(hexid(commit, 40) and hexid(context_sha, 64) and hexid(manifest_sha, 64), 'exact_input')
    run = Run(runtime_parent, commit)
    dispatched = False; build_exit = None; failure_code = None
    try:
        run.copy_input(manifest, 'manifest.json', MAX_MANIFEST_BYTES)
        run.copy_input(context, 'context.tar.gz', MAX_ARCHIVE_BYTES)
        with run.open_input('manifest.json', manifest_sha) as manifest_stream, run.open_input('context.tar.gz', context_sha) as archive:
            m = verify(archive, manifest_stream.read(), commit, context_sha, manifest_sha)
        labels = dict(zip(LABEL_KEYS, [commit, m['application_tree'], context_sha, manifest_sha, run.record['owner']]))
        run.record.update(context_sha256=context_sha, manifest_sha256=manifest_sha, application_tree=m['application_tree'],
                          labels=labels, included_files=m['included_files'], phase='validated'); run.save()
        query = remote(['docker', 'image', 'ls', '--quiet', '--filter', 'reference=' + run.record['image_tag']])
        code = invoke(run, 'tag-check', query, 30)
        require(code == 0, 'tag_query'); require((run.directory / 'tag-check.stdout').stat().st_size == 0, 'tag_exists')
        run.record.update(phase='pending', pending_at_utc=now()); run.save()  # Durable before any build dispatch.
        args = ['docker', 'build', '--build-arg', 'KUBECTL_VERSION=v1.37.1', '-t', run.record['image_tag']]
        for key, value in labels.items(): args += ['--label', key + '=' + value]
        args += ['-']
        # Second tag absence check immediately before exec; Docker itself offers no tag CAS.
        shell = 'set -eu; existing=$(' + shlex.join(
            ['docker', 'image', 'ls', '--quiet', '--filter', 'reference=' + run.record['image_tag']]) + \
            '); test -z "$existing" || exit 73; exec ' + shlex.join(args)
        with run.open_input('manifest.json', manifest_sha), run.open_input('context.tar.gz', context_sha) as stream:
            dispatched = True; code = invoke(run, 'build', SSH + [shell], 2400, stdin=stream); build_exit = code
            run.check_input('context.tar.gz', stream.fileno())
        run.record.update(build_exit_code=code, phase='uncertain' if code in (0, 255) else 'failed', completed_at_utc=now()); run.save()
        require(code == 0, 'build_exit')
        projection = '{"config_image_id":{{json .Id}},"image_bytes":{{json .Size}},"labels":{' + ','.join(
            json.dumps(key) + ':{{json (index .Config.Labels ' + json.dumps(key) + ')}}' for key in LABEL_KEYS) + '}}'
        code = invoke(run, 'inspect', remote(['docker', 'image', 'inspect', '--format', projection, run.record['image_tag']]), 30)
        require(code == 0 and (run.directory / 'inspect.stdout').stat().st_size <= 65536, 'image_inspect')
        image = json.loads((run.directory / 'inspect.stdout').read_bytes(), object_pairs_hook=unique)
        require(type(image) is dict and set(image) == {'config_image_id', 'image_bytes', 'labels'} and
            type(image['config_image_id']) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', image['config_image_id']) and
            type(image['image_bytes']) is int and image['image_bytes'] > 0 and image['labels'] == labels, 'image_identity')
        run.record.update(image, phase='completed', completed_at_utc=now(), image_manifest_digest=None,
                          runtime_digest_qualified=False); run.save()
        result = dict(run.record)
    except Exception as error:
        failure_code = error.code if isinstance(error, BuildRefused) else 'operation_failed'
        phase = 'refused' if not dispatched or build_exit == 73 else 'failed' if build_exit not in (None, 0, 255) else 'uncertain'
        run.record.update(phase=phase, failure=failure_code, completed_at_utc=now())
        try: run.save()
        except Exception: pass  # Prior pending still prevents replay if outcome cannot be flushed.
    finally: run.close()
    # Raise outside the handler: no arbitrary source/parser/SSH exception context.
    if failure_code is not None: raise BuildRefused(failure_code)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('context', 'manifest', 'source-commit', 'context-sha256', 'manifest-sha256', 'runtime-parent'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        result = build(args.context, args.manifest, args.source_commit, args.context_sha256,
                       args.manifest_sha256, args.runtime_parent)
        print(json.dumps({key: result[key] for key in ('phase', 'source_commit', 'image_tag',
            'config_image_id', 'image_bytes', 'deployed', 'runtime_accepted')})); return 0
    except Exception:
        print('Release image operation failed; inspect the retained protected run without replay.', file=__import__('sys').stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
