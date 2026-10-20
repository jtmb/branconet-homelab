#!/usr/bin/env python3
"""Owned POSIX persistence and bounded child I/O for the distinct overlay adapters."""
import contextlib
import hashlib
import json
import os
import pathlib
import re
import stat
import subprocess
import threading
import uuid

FORMAT = 'bortus-compiled-overlay-adapter/v1'
CONTRACT_PIN = 'a47ea88d868bc99e0007ca78af7f393a616db4cbbfd03fd59f62c69c4c397ca1'
MAX_METADATA = 8 * 1024 ** 2
MAX_ARCHIVE = 4 * 1024 ** 3


def require(ok, code):
    if not ok:
        raise RuntimeError(code)


def identity(info):
    return info.st_dev, info.st_ino, info.st_uid, info.st_mode


def stable(info):
    return (*identity(info), info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate_key')
        result[key] = value
    return result


def decode(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_METADATA, 'metadata_bound')
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: require(False, 'nonfinite_json'))


def component(name):
    require(type(name) is str and re.fullmatch('[A-Za-z0-9_.-]{1,128}', name)
            and name not in ('.', '..'), 'component')


def anchors_for(directory):
    """No symlink or writable ancestor; caller owns and closes every descriptor."""
    directory = pathlib.Path(directory)
    require(os.name == 'posix' and directory.is_absolute() and '..' not in directory.parts
            and len(directory.parts) <= 32, 'directory')
    anchors = []
    try:
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        anchors.append((pathlib.Path('/'), fd, identity(os.fstat(fd))))
        current = pathlib.Path('/')
        for part in directory.parts[1:]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            current /= part
            info = os.fstat(fd)
            anchors.append((current, fd, identity(info)))
            require(info.st_uid in (0, os.getuid()) and stat.S_IMODE(info.st_mode) & 0o022 == 0,
                    'directory_permissions')
        require(os.fstat(fd).st_uid == os.getuid(), 'directory_owner')
        return anchors
    except BaseException:
        for _, fd, _ in reversed(anchors):
            os.close(fd)
        raise


def check_anchors(anchors):
    require(all(identity(p.lstat()) == old and identity(os.fstat(fd)) == old
                for p, fd, old in anchors), 'directory_changed')


class Run:
    """Exclusive deterministic directories remain on all outcomes; never resume."""
    def __init__(self, parent, commit, purpose):
        require(type(commit) is str and re.fullmatch('[0-9a-f]{40}', commit)
                and purpose in ('export', 'preload', 'node'), 'run_identity')
        self.anchors, self.fd = [], None
        self.record_identity, self.inputs = None, {}
        self.name = 'bortus-compiled-overlay-' + purpose + '-' + commit
        self.directory = pathlib.Path(parent) / self.name
        try:
            self.anchors = anchors_for(parent)
            parent_fd = self.anchors[-1][1]
            check_anchors(self.anchors)
            os.mkdir(self.name, 0o700, dir_fd=parent_fd)
            os.fsync(parent_fd)
            self.fd = os.open(self.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                              dir_fd=parent_fd)
            self.run_identity = identity(os.fstat(self.fd))
            self.record = {'format': FORMAT, 'purpose': purpose, 'source_commit': commit,
                           'owner': str(uuid.uuid4()), 'phase': 'validating',
                           'runtime_qualified': False, 'deployed': False, 'nodes': []}
            self.save()
        except BaseException:
            self.close()
            raise

    def owned(self):
        check_anchors(self.anchors)
        require(self.fd is not None and identity(self.directory.lstat()) == self.run_identity
                and identity(os.fstat(self.fd)) == self.run_identity
                and stat.S_IMODE(self.run_identity[-1]) == 0o700, 'run_changed')
        if self.record_identity is not None:
            require(stable(os.stat('record.json', dir_fd=self.fd, follow_symlinks=False))
                    == self.record_identity, 'record_changed')

    def create(self, name):
        component(name)
        self.owned()
        return os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                       0o600, dir_fd=self.fd)

    def save(self):
        self.owned()
        name = 'record-' + uuid.uuid4().hex + '.next'
        fd = self.create(name)
        try:
            raw = encoded(self.record) + b'\n'
            require(len(raw) <= MAX_METADATA, 'record_bound')
            with os.fdopen(fd, 'wb', closefd=False) as out:
                out.write(raw)
                out.flush()
                os.fsync(fd)
            self.owned()
            os.replace(name, 'record.json', src_dir_fd=self.fd, dst_dir_fd=self.fd)
            os.fsync(self.fd)
            self.record_identity = stable(os.fstat(fd))
            self.owned()
        finally:
            os.close(fd)

    def copy(self, source, name, limit):
        source = pathlib.Path(source)
        anchors = anchors_for(source.parent)
        fd = None
        try:
            fd = os.open(source.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                         dir_fd=anchors[-1][1])
            initial = os.fstat(fd)
            require(stat.S_ISREG(initial.st_mode) and initial.st_uid == os.getuid()
                    and stat.S_IMODE(initial.st_mode) & 0o022 == 0 and initial.st_nlink == 1
                    and 0 < initial.st_size <= limit, 'input_permissions')
            with os.fdopen(self.create(name), 'wb') as out:
                total = 0
                while True:
                    raw = os.read(fd, min(65536, limit - total + 1))
                    if not raw:
                        break
                    total += len(raw)
                    require(total <= limit, 'input_bound')
                    out.write(raw)
                check_anchors(anchors)
                require(total == initial.st_size and stable(os.fstat(fd)) == stable(initial)
                        and stable(source.lstat()) == stable(initial), 'input_changed')
                out.flush()
                os.fsync(out.fileno())
                self.inputs[name] = stable(os.fstat(out.fileno()))
            os.fsync(self.fd)
        finally:
            if fd is not None:
                os.close(fd)
            for _, anchor, _ in reversed(anchors):
                os.close(anchor)

    def check(self, name, fd):
        self.owned()
        require(stable(os.fstat(fd)) == self.inputs[name]
                and stable(os.stat(name, dir_fd=self.fd, follow_symlinks=False)) == self.inputs[name],
                'input_changed')

    @contextlib.contextmanager
    def opened(self, name, pin):
        component(name)
        self.owned()
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=self.fd)
        with os.fdopen(fd, 'rb') as stream:
            self.check(name, fd)
            require(hashlib.file_digest(stream, 'sha256').hexdigest() == pin, 'input_hash')
            self.check(name, fd)
            stream.seek(0)
            yield stream
            self.check(name, fd)

    def close(self):
        descriptors = ([self.fd] if self.fd is not None else []) + [a[1] for a in reversed(self.anchors)]
        self.fd, self.anchors = None, []
        for fd in descriptors:
            os.close(fd)


def child(run, stage, argv, *, source=None, prefix=b'', output=None, cap=MAX_METADATA, timeout=30):
    """Only owned child PID; bounded in-memory metadata; raw stderr is never saved."""
    component(stage)
    run.owned()
    captured, failures = bytearray(), []
    process = subprocess.Popen(argv, stdin=subprocess.PIPE if source is not None else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=False)
    def read():
        try:
            total = 0
            for raw in iter(lambda: process.stdout.read(65536), b''):
                total += len(raw)
                require(total <= cap, 'child_output_bound')
                if output is None:
                    captured.extend(raw)
                else:
                    output.write(raw)
        except BaseException:
            failures.append(True)
            process.kill()
        finally:
            process.stdout.close()
    def write():
        try:
            process.stdin.write(prefix)
            total = 0
            for raw in iter(lambda: source.read(65536), b''):
                total += len(raw)
                require(total <= MAX_ARCHIVE, 'child_input_bound')
                process.stdin.write(raw)
            process.stdin.flush()
        except BaseException:
            failures.append(True)
            process.kill()
        finally:
            try:
                process.stdin.close()
            except BaseException:
                failures.append(True)
                process.kill()
    readers = [threading.Thread(target=read, daemon=True)]
    if source is not None:
        readers.append(threading.Thread(target=write, daemon=True))
    try:
        for thread in readers:
            thread.start()
        code = process.wait(timeout=timeout)
        run.record[stage + '_exit_code'] = code
        require(code == 0, 'child_exit')
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        for thread in readers:
            thread.join(timeout=5)
        require(not failures and not any(t.is_alive() for t in readers), 'child_stream')
    return bytes(captured)
