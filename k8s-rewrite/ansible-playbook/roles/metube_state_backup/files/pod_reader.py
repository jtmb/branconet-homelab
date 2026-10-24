"""Injected into the pinned read-only MeTube reader; never starts its application."""
import hashlib
import io
import json
import os
import pathlib
import stat
import sys
import tarfile

ROOTS = {'data-0': '/state', 'data-1': '/tmp_dir'}
EXCLUDED = {'data-0/ytptube-config', 'data-1/ytptube-deno', 'data-1/ytptube-cache'}
MAX_BYTES = 4 * 1024**3
MAX_ENTRIES = 4096
CHUNK = 1024 * 1024


def need(value):
    if not value:
        raise ValueError('state reader refused')


def fingerprint(info):
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def ignored(name):
    return any(name == base or name.startswith(base + '/') for base in EXCLUDED)


def inventory(exclude=False, hash_files=True):
    result = {}
    total = 0
    for alias, base in ROOTS.items():
        root = pathlib.Path(base)
        need(root.is_dir() and not root.is_symlink())
        pending = [(alias, root)]
        while pending:
            name, path = pending.pop()
            if exclude and ignored(name):
                continue
            info = path.lstat()
            row = {'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid, 'mtime_ns': info.st_mtime_ns, 'fingerprint': fingerprint(info)}
            if stat.S_ISDIR(info.st_mode):
                row['kind'] = 'directory'
                pending += [(name + '/' + child.name, child) for child in sorted(path.iterdir(), key=lambda p: p.name)]
            elif stat.S_ISLNK(info.st_mode):
                row.update(kind='symlink', link=os.readlink(path))
            else:
                need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
                row.update(kind='file', bytes=info.st_size)
                total += info.st_size
                need(total <= MAX_BYTES)
                if hash_files:
                    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                    try:
                        need(fingerprint(os.fstat(fd)) == row['fingerprint'])
                        digest = hashlib.sha256()
                        with os.fdopen(os.dup(fd), 'rb') as source:
                            for block in iter(lambda: source.read(CHUNK), b''):
                                digest.update(block)
                        need(fingerprint(os.fstat(fd)) == fingerprint(path.lstat()) == row['fingerprint'])
                        row['sha256'] = digest.hexdigest()
                    finally:
                        os.close(fd)
            result[name] = row
            need(len(result) <= MAX_ENTRIES)
    return {'schema_version': 1, 'entries': result, 'total_file_bytes': total, 'excluded_new_paths': sorted(EXCLUDED) if exclude else []}


class CheckedReader:
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()

    def read(self, size):
        data = self.stream.read(min(size, CHUNK))
        self.digest.update(data)
        return data


def archive(expected):
    need(expected['schema_version'] == 1 and not expected['excluded_new_paths'])
    need(inventory(False, False) == without_hashes(expected))
    raw = json.dumps(expected, sort_keys=True, separators=(',', ':')).encode()
    need(len(raw) <= 8 * 1024 * 1024)
    with tarfile.open(fileobj=sys.stdout.buffer, mode='w|', format=tarfile.PAX_FORMAT) as output:
        info = tarfile.TarInfo('manifest.json'); info.mode = 0o600; info.size = len(raw)
        output.addfile(info, io.BytesIO(raw))
        for name, row in sorted(expected['entries'].items()):
            alias, _, relative = name.partition('/')
            path = pathlib.Path(ROOTS[alias]) / relative
            need(fingerprint(path.lstat()) == row['fingerprint'])
            info = tarfile.TarInfo(name); info.mode = row['mode']; info.uid = row['uid']; info.gid = row['gid']; info.mtime = row['mtime_ns'] // 1000000000
            if row['kind'] == 'directory':
                info.type = tarfile.DIRTYPE; output.addfile(info)
            elif row['kind'] == 'symlink':
                info.type = tarfile.SYMTYPE; info.linkname = row['link']; output.addfile(info)
            else:
                info.size = row['bytes']
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                try:
                    need(fingerprint(os.fstat(fd)) == row['fingerprint'])
                    with os.fdopen(os.dup(fd), 'rb') as source:
                        reader = CheckedReader(source); output.addfile(info, reader)
                        need(reader.digest.hexdigest() == row['sha256'])
                    need(fingerprint(os.fstat(fd)) == fingerprint(path.lstat()) == row['fingerprint'])
                finally:
                    os.close(fd)
    need(inventory(False, False) == without_hashes(expected))


def without_hashes(manifest):
    return dict(manifest, entries={name: {k: v for k, v in row.items() if k != 'sha256'} for name, row in manifest['entries'].items()})


if __name__ == '__main__':
    try:
        mode = sys.argv[1]
        if mode == 'archive':
            raw = sys.stdin.buffer.read(8 * 1024 * 1024 + 1); need(len(raw) <= 8 * 1024 * 1024)
            archive(json.loads(raw))
        else:
            need(mode in ['inventory', 'reobserve'])
            print(json.dumps(inventory(mode == 'reobserve'), sort_keys=True))
    except Exception:
        raise SystemExit(1)