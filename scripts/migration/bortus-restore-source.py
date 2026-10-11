"""Pinned checkpoint plus fresh bounded source fences; no mutation or data reads."""
import hashlib
import importlib.util
import json
import math
import os
import pathlib
import re
import stat
import sys
import time


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


metadata = load('restore_source_metadata', 'bortus-restore-metadata.py')
preflight = load('restore_source_preflight', 'inspect-bortus-independent-restore.py')
MAX_JOURNAL = 1024 * 1024


class SourceRefused(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__('Restore source refused: ' + code)


def need(condition, code):
    if not condition:
        raise SourceRefused(code)


def deadline_valid(deadline):
    now = time.monotonic()
    need(type(deadline) in (int, float) and math.isfinite(deadline) and now < deadline <= now + 300,
         'deadline')


class ScopedClient(preflight.cold.preflight.Client):
    """Existing source evaluator with fixed TLS reads rather than kubectl subprocesses."""
    NAMED = {
        'pvc': ('claim', 'bortus', None), 'pv': ('pv', None, None),
        'volumes.longhorn.io': ('volume', 'longhorn-system', None),
        'deployment': ('deployment', 'bortus', 'bortus'),
        'helmrelease': ('helmrelease', 'flux-system', 'bortus'),
        'kustomization': ('kustomization', 'flux-system', 'migration-releases'),
        'backuptargets.longhorn.io': ('backuptarget', 'longhorn-system', 'default'),
        'replicaset': ('replicaset', 'bortus', None),
        'snapshots.longhorn.io': ('snapshot', 'longhorn-system', None),
        'backups.longhorn.io': ('backup', 'longhorn-system', None),
        'storageclass': ('storageclass', None, 'longhorn'), 'node': ('node', None, None)}
    LISTS = {'pvs': ('pv', None), 'pods': ('pod', 'bortus'),
             'pvc': ('claim', 'bortus'), 'storageclasses': ('storageclass', None)}

    def __init__(self, api, deadline):
        need(type(api) is metadata.MetadataAPI, 'configuration')
        self.api, self.deadline = api, deadline

    def get(self, kind, name=None, namespace=None):
        deadline_valid(self.deadline)
        if name is None:
            need(type(kind) is str and kind in self.LISTS, 'scope')
            resource, expected_namespace = self.LISTS[kind]
            need(namespace == expected_namespace, 'scope')
            return self.api.list(resource, deadline=self.deadline)
        need(type(kind) is str and kind in self.NAMED, 'scope')
        resource, expected_namespace, fixed_name = self.NAMED[kind]
        need(namespace == expected_namespace and (fixed_name is None or name == fixed_name), 'scope')
        return self.api.get(resource, name, deadline=self.deadline)


def stable_file(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
            info.st_uid, info.st_mode, info.st_nlink)


class SourceFence:
    """Own pinned read-only descriptors; repeat the live fences on every invocation."""
    def __init__(self, path, checkpoint_sha256, image, alternate_node, api):
        self.fd = None
        self.anchors = []
        self.directory_fds = []
        failure = None
        try:
            need(os.name == 'posix' and type(checkpoint_sha256) is str and
                 re.fullmatch('[0-9a-f]{64}', checkpoint_sha256) and
                 preflight.cold.valid_digest(image) and metadata.valid_name(alternate_node) and
                 type(api) is metadata.MetadataAPI, 'configuration')
            self.path = pathlib.Path(path)
            need(self.path.is_absolute() and '..' not in self.path.parts and
                 1 < len(self.path.parts) <= 32, 'ownership')
            fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            self.directory_fds.append(fd)  # Register before any fallible identity check.
            current = pathlib.Path('/')
            self.anchors.append((current, fd, os.fstat(fd)))
            for part in self.path.parts[1:-1]:
                fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                self.directory_fds.append(fd)
                current /= part
                info = os.fstat(fd)
                self.anchors.append((current, fd, info))
                need(info.st_uid in (0, os.getuid()) and stat.S_IMODE(info.st_mode) & 0o022 == 0,
                     'ownership')
            need(os.fstat(fd).st_uid == os.getuid(), 'ownership')
            self.fd = os.open(self.path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                              dir_fd=fd)
            info = os.fstat(self.fd)
            need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
                 stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1 and
                 0 < info.st_size <= MAX_JOURNAL, 'ownership')
            self.file_identity = stable_file(info)
            self.checkpoint_sha256, self.image, self.alternate_node, self.api = (
                checkpoint_sha256, image, alternate_node, api)
            self._read()
        except SourceRefused as error:
            failure = error.code
        except Exception:
            failure = 'ownership'
        if failure:
            self.close()
            raise SourceRefused(failure)

    def _read(self):
        need(self.fd is not None, 'ownership')
        for path, fd, original in self.anchors:
            actual, opened = path.lstat(), os.fstat(fd)
            need(stat.S_ISDIR(actual.st_mode) and (actual.st_dev, actual.st_ino) ==
                 (opened.st_dev, opened.st_ino) == (original.st_dev, original.st_ino) and
                 actual.st_uid == original.st_uid and stat.S_IMODE(actual.st_mode) & 0o022 == 0,
                 'ownership')
        need(stable_file(self.path.lstat()) == self.file_identity == stable_file(os.fstat(self.fd)), 'ownership')
        os.lseek(self.fd, 0, os.SEEK_SET)
        raw = bytearray()
        while len(raw) <= MAX_JOURNAL:
            block = os.read(self.fd, min(65536, MAX_JOURNAL - len(raw) + 1))
            if not block: break
            raw.extend(block)
        need(len(raw) <= MAX_JOURNAL and hashlib.sha256(raw).hexdigest() == self.checkpoint_sha256 and
             stable_file(os.fstat(self.fd)) == stable_file(self.path.lstat()) == self.file_identity,
             'checkpoint')
        return metadata.bounded_json(raw)

    def _validate(self, deadline, proposals):
        value, failure = None, None
        try:
            deadline_valid(deadline)
            record = self._read()
            client = ScopedClient(self.api, deadline)
            if proposals:
                value = preflight.prepare(client, record, self.image, self.alternate_node)
            else:
                fresh, _, backup, _, _ = preflight.validate_source(
                    client, record, self.image, self.alternate_node)
                ids = fresh['identities']
                value = {'checkpoint_journal_sha256': self.checkpoint_sha256,
                    'original_ciphertext_sha256': record['sqlite_archive']['ciphertext_sha256'],
                    'claim': ids['claim'], 'pv': ids['pv'], 'volume': ids['longhorn_volume'],
                    'backup': preflight.identity(backup)}
            self._read()
            deadline_valid(deadline)
        except SourceRefused as error:
            failure = error.code
        except metadata.MetadataRefused:
            failure = 'transport'
        except Exception:
            failure = 'source'
        # No raw record/response/callback error leaves this internal frame on refusal.
        return (None if failure else value), failure

    def prepare(self, *, deadline):
        value, failure = self._validate(deadline, True)
        if failure: raise SourceRefused(failure)
        return value

    def check(self, *, deadline):
        value, failure = self._validate(deadline, False)
        if failure: raise SourceRefused(failure)
        return value

    def close(self):
        failure = False
        for fd in ([self.fd] if self.fd is not None else []) + list(reversed(self.directory_fds)):
            try: os.close(fd)
            except OSError: failure = True
        self.fd = None
        self.anchors = []
        self.directory_fds = []
        if failure: raise SourceRefused('cleanup')
