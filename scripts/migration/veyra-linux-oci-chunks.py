#!/usr/bin/env python3
"""Write bounded filesystem layers directly into ONE seekable OCI TAR.

No whole layer scratch/archive copy is created. This library neither admits a
build nor deletes a producer. The complete executor must preserve the original
source/OS/ABI/security gates and perform actual last-consumer/reference checks.
"""
import base64
from decimal import Decimal
import gzip
import hashlib
import io
import os
from pathlib import Path
import posixpath
import stat
import subprocess
import tarfile
import threading


def need(value, message):
    if not value:
        raise RuntimeError(message)


def snapshot(root, selected=None):
    """One full final-filesystem inventory, including Linux security xattrs."""
    need(root.resolve() == root and root.is_dir(), 'Canonical inactive owned filesystem required')
    rows, groups = [], {}
    paths = [root] if selected is None else [root / name for name in selected]
    def fail(error):
        raise error
    if selected is None:
        for directory, names, files in os.walk(root, followlinks=False, onerror=fail):
            names.sort()
            files.sort()
            paths.extend(Path(directory) / name for name in names + files)
    else:
        need(all(name == '.' or (not name.startswith('/') and '..' not in Path(name).parts)
                 for name in selected), 'Selected snapshot path escaped')
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        info = path.lstat()
        need(info.st_dev == root.stat().st_dev, 'Final filesystem crossed an unqualified mount')
        row = {'path': path.relative_to(root).as_posix(), 'mode': info.st_mode & 0o7777,
               'uid': info.st_uid, 'gid': info.st_gid, 'mtimeNs': info.st_mtime_ns,
               'xattrs': {key: base64.b64encode(os.getxattr(path, key, follow_symlinks=False)).decode()
                         for key in sorted(os.listxattr(path, follow_symlinks=False))}}
        if stat.S_ISREG(info.st_mode):
            key = (info.st_dev, info.st_ino)
            if key in groups:
                row.update(type='hardlink', target=groups[key])
            else:
                h = hashlib.sha256()
                with path.open('rb') as source:
                    for block in iter(lambda: source.read(1024 * 1024), b''):
                        h.update(block)
                row.update(type='file', bytes=info.st_size, sha256=h.hexdigest())
                groups[key] = row['path']
        elif stat.S_ISDIR(info.st_mode):
            row['type'] = 'directory'
        else:
            need(stat.S_ISLNK(info.st_mode), 'Special final entry requires explicit OCI representation: ' + str(path))
            row.update(type='symlink', target=os.readlink(path))
        rows.append(row)
    return rows


def groups(rows, logical_limit):
    """Keep every hardlink group together; emit each path exactly once."""
    need(logical_limit > 0, 'Positive admitted chunk target required')
    buckets = {}
    for row in rows:
        owner = row['target'] if row['type'] == 'hardlink' else row['path']
        buckets.setdefault(owner, []).append(row)
    result, batch, total = [], [], 0
    for members in buckets.values():
        weight = sum(row.get('bytes', 0) for row in members)
        if batch and total + weight > logical_limit:
            result.append(sorted(batch, key=lambda row: row['path']))
            batch, total = [], 0
        batch.extend(members)
        total += weight
    if batch:
        result.append(sorted(batch, key=lambda row: row['path']))
    need(sum(map(len, result)) == len(rows), 'Chunk membership is incomplete')
    return result


class Slice(io.RawIOBase):
    """Independent pread cursor over exactly one already-written OCI blob."""
    def __init__(self, fd, start, size):
        self.fd, self.start, self.size, self.position = fd, start, size, 0
    def readable(self):
        return True
    def read(self, size=-1):
        size = self.size - self.position if size < 0 else min(size, self.size - self.position)
        body = os.pread(self.fd, size, self.start + self.position)
        self.position += len(body)
        return body
    def readinto(self, buffer):
        body = self.read(len(buffer))
        buffer[:len(body)] = body
        return len(body)


def inspect_blob(archive, offset, size, expected):
    rows, seen = [], set()
    compressed = hashlib.sha256()
    view = Slice(archive.fileno(), offset, size)
    for block in iter(lambda: view.read(1024 * 1024), b''):
        compressed.update(block)
    need(view.position == size, 'Closed OCI blob is truncated')
    raw_hash = hashlib.sha256()
    class Inflated(io.RawIOBase):
        def __init__(self, stream):
            self.stream = stream
        def readable(self):
            return True
        def read(self, count=-1):
            need(0 <= count <= 1024 * 1024, 'Unbounded layer verification read')
            body = self.stream.read(count)
            raw_hash.update(body)
            return body
    with gzip.GzipFile(fileobj=Slice(archive.fileno(), offset, size), mode='rb') as zipped:
        raw = Inflated(zipped)
        with tarfile.open(fileobj=raw, mode='r|', encoding='utf-8', errors='surrogateescape') as tar:
            while True:
                member = tar.next()
                if member is None:
                    break
                name = posixpath.normpath(member.name)
                need(name not in seen and not name.startswith('/') and '..' not in Path(name).parts,
                     'Duplicate or escaped final layer path')
                seen.add(name)
                value = member.pax_headers.get('mtime', str(member.mtime))
                ns = Decimal(value) * 1_000_000_000
                need(ns == ns.to_integral_value(), 'Nonintegral nanosecond image time')
                row = {'path': name, 'mode': member.mode, 'uid': member.uid,
                       'gid': member.gid, 'mtimeNs': int(ns),
                       'xattrs': {key[len('SCHILY.xattr.'):]: base64.b64encode(
                           value.encode('utf-8', 'surrogateescape')).decode()
                           for key, value in member.pax_headers.items() if key.startswith('SCHILY.xattr.')}}
                if member.isfile():
                    h = hashlib.sha256()
                    with tar.extractfile(member) as stream:
                        for block in iter(lambda: stream.read(1024 * 1024), b''):
                            h.update(block)
                    row.update(type='file', bytes=member.size, sha256=h.hexdigest())
                elif member.isdir():
                    row['type'] = 'directory'
                else:
                    need(member.issym() or member.islnk(), 'Unrepresented OCI member type')
                    row.update(type='symlink' if member.issym() else 'hardlink',
                               target=member.linkname if member.issym() else posixpath.normpath(member.linkname))
                if row['type'] == 'hardlink':
                    targets = [item for item in rows if item['path'] == row['target']]
                    need(len(targets) == 1 and targets[0]['type'] == 'file',
                         'Hardlink target is not a preceding regular inode')
                    target = targets[0]
                    need(all(row[key] == target[key] for key in ('mode', 'uid', 'gid', 'mtimeNs')),
                         'Hardlink header metadata differs from its inode')
                    # GNU tar emits inode xattrs on the data-bearing member.
                    # Resolve the actual hardlink projection before comparing
                    # against lstat/getxattr: both paths name that same inode.
                    need(not row['xattrs'] or row['xattrs'] == target['xattrs'],
                         'Hardlink header xattrs conflict with its inode')
                    row['xattrs'] = dict(target['xattrs'])
                rows.append(row)
                tar.members.clear()
            while tail := tar.fileobj.read(65536):
                need(not any(tail), 'Unexpected final layer trailing data')
    need(sorted(rows, key=lambda row: row['path']) == expected,
         'Final layer bytes/metadata/xattrs/hardlinks differ from original producer')
    return {'digest': 'sha256:' + compressed.hexdigest(), 'size': size,
            'diffId': 'sha256:' + raw_hash.hexdigest(), 'entries': len(rows),
            'closedArchiveProjectionVerified': True, 'retirementAuthorized': False}


def append_layer(archive, root, rows, maximum_compressed_bytes, epoch, log):
    """Append, backfill TAR header and independently verify one actual layer.

    archive must be the original exclusively-created seekable WORK OCI output.
    Caller must reserve the complete observed stage and max chunk coexistence;
    deletion and admission are deliberately not authorized by this function.
    """
    need(root.resolve() == root and maximum_compressed_bytes > 0, 'Canonical original root and positive bound required')
    need(archive.readable() and archive.writable() and archive.seekable(),
         'Original exclusive OCI output must be opened x+b for independent pread verification')
    rows = sorted(rows, key=lambda row: row['path'])
    need(len({row['path'] for row in rows}) == len(rows), 'Repeated requested layer member')
    header = archive.tell()
    need(header % 512 == 0, 'OCI TAR output lost block alignment')
    archive.write(bytes(512))
    start = archive.tell()
    process = subprocess.Popen(['/usr/bin/tar', '--create', '--format=pax', '--numeric-owner',
        '--xattrs', '--xattrs-include=*', '--acls', '--selinux',
        '--pax-option=delete=atime,delete=ctime', '--no-recursion', '--directory', str(root),
        '--null', '--verbatim-files-from', '--files-from=-'], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=log, start_new_session=True)
    input_errors = []
    def feed():
        try:
            for row in rows:
                need(row['path'] == '.' or ('..' not in Path(row['path']).parts and
                     not row['path'].startswith('/')), 'Requested tar source escaped root')
                process.stdin.write(os.fsencode('./' + row['path']) + b'\0')
            process.stdin.close()
        except BaseException as error:
            input_errors.append(error)
    feeder = threading.Thread(target=feed, daemon=True)
    feeder.start()
    class BoundedOutput:
        def write(self, body):
            need(archive.tell() - start + len(body) <= maximum_compressed_bytes,
                 'Actual OCI chunk exceeded complete admitted bound; preserve partial output')
            return archive.write(body)
        def flush(self):
            return archive.flush()
    try:
        with gzip.GzipFile(filename='', fileobj=BoundedOutput(), mode='wb', mtime=0) as compressed:
            for block in iter(lambda: process.stdout.read(1024 * 1024), b''):
                compressed.write(block)
        process.stdout.close()
        feeder.join(timeout=10)
        need(not feeder.is_alive() and not input_errors, 'Actual tar member input did not complete')
        need(process.wait(timeout=10) == 0, 'Actual tar producer failed; retain original log and files')
        size = archive.tell() - start
        archive.flush()
        proof = inspect_blob(archive, start, size, rows)
        member = tarfile.TarInfo('blobs/sha256/' + proof['digest'][7:])
        member.size, member.mode, member.mtime = size, 0o444, epoch
        archive.seek(header)
        archive.write(member.tobuf(format=tarfile.USTAR_FORMAT))
        archive.seek(start + size)
        archive.write(bytes((-size) % 512))
        archive.flush()
        os.fsync(archive.fileno())
        proof.update(archiveHeaderOffset=header, archiveBodyOffset=start,
                     mediaType='application/vnd.oci.image.layer.v1.tar+gzip')
        return proof
    finally:
        # Only this actual Popen child is signalled, never a shared builder.
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                raise RuntimeError('Owned tar child did not stop; retain all output and do not advance')
        if process.stdout:
            process.stdout.close()
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        feeder.join(timeout=2)
