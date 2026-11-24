#!/usr/bin/env python3
"""Compressed exact-COPY producer exports; consume directly into owned rootfs.

This is internal transport, not an accepted/published image. It never deletes
producers, admits a build, changes resource limits, or selects old artifacts.
"""
import base64
from decimal import Decimal
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import posixpath
import stat
import tarfile


def need(value, message):
    if not value:
        raise RuntimeError(message)


def module(name):
    path = Path(__file__).with_name(name + '.py')
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


class BoundedArchive:
    """Cap every actual archive write, including headers, backfills and EOF."""
    def __init__(self, stream, maximum):
        self.stream, self.maximum = stream, maximum
    def __getattr__(self, name):
        return getattr(self.stream, name)
    def write(self, body):
        need(self.stream.tell() + len(body) <= self.maximum,
             'Whole compressed handoff archive exceeded its admitted bound')
        return self.stream.write(body)


def export(producer, declarations, archive_path, maximum_layer_bytes, source_date_epoch,
           required_copies=(), maximum_archive_bytes=None):
    """The exact original artifact COPY declarations are the export authority."""
    chunks = module('veyra-linux-oci-chunks')
    producer.guard()
    need(archive_path.parent.resolve() == archive_path.parent and
         archive_path.is_relative_to(producer.operator.WORK), 'Original confined exclusive handoff path required')
    records = []
    need(maximum_archive_bytes is None or type(maximum_archive_bytes) is int and maximum_archive_bytes > 0,
         'Positive explicit whole archive bound required')
    with archive_path.open('x+b') as stream:
        archive = stream if maximum_archive_bytes is None else BoundedArchive(stream, maximum_archive_bytes)
        for number, declaration in enumerate(declarations):
            source_name = posixpath.normpath(declaration['source'])
            target_name = declaration.get('target', declaration.get('destination'))
            need(isinstance(target_name, str) and
                 ('target' not in declaration or 'destination' not in declaration or
                  declaration['target'] == declaration['destination']) and
                 source_name.startswith('/') and declaration['source'].rstrip('/') == target_name.rstrip('/'),
                 'Original one-to-one artifact export mapping required')
            source = producer.path(source_name)
            need(source.exists() and not source.is_symlink(), 'Original artifact source absent or unexpected root alias')
            if source.is_dir():
                root, rows, kind = source, chunks.snapshot(source), 'directory'
            else:
                info = source.lstat()
                need(stat.S_ISREG(info.st_mode), 'Original file export is not regular')
                root, kind = source.parent, 'file'
                rows = [{'path': source.name, 'type': 'file', 'bytes': info.st_size,
                    'sha256': sha(source), 'mode': info.st_mode & 0o7777,
                    'uid': info.st_uid, 'gid': info.st_gid, 'mtimeNs': info.st_mtime_ns,
                    'xattrs': {key: base64.b64encode(os.getxattr(source, key, follow_symlinks=False)).decode()
                               for key in sorted(os.listxattr(source, follow_symlinks=False))}}]
            log_path = producer.operator.WORK / ('handoff-' + producer.stage + '-' + str(number) + '.log')
            with log_path.open('xb') as log:
                layer = chunks.append_layer(archive, root, rows, maximum_layer_bytes, source_date_epoch, log)
            records.append({'declaration': declaration, 'kind': kind, 'fileName': source.name,
                'treeSha256': hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                'layer': layer})
            producer.guard()
        archive.write(bytes(1024))
        archive.flush()
        os.fsync(archive.fileno())
    # Index required child COPY roots against the SAME closed producer blob;
    # never duplicate its body or extract a second dependency tree.
    original_records = list(records)
    for required in required_copies:
        source_name = posixpath.normpath(required['source'])
        if any(row['declaration']['producer'] == required['producer'] and
               posixpath.normpath(row['declaration']['source']) == source_name for row in records):
            continue
        candidates = [row for row in original_records if row['kind'] == 'directory' and
            row['declaration']['producer'] == required['producer'] and
            source_name.startswith(posixpath.normpath(row['declaration']['source']).rstrip('/') + '/')]
        need(candidates, 'Required original COPY is outside the declared artifact closure')
        parent = max(candidates, key=lambda row: len(row['declaration']['source']))
        source = producer.path(source_name)
        need(source.exists() and not source.is_symlink(), 'Required child COPY source is absent or unqualified alias')
        if source.is_dir():
            rows, kind = chunks.snapshot(source), 'directory'
        else:
            rows = chunks.snapshot(source.parent, selected=[source.name])
            kind = 'file'
        records.append({'declaration': {**required, 'target': required['source']}, 'kind': kind,
            'fileName': source.name,
            'selector': posixpath.relpath(source_name, posixpath.normpath(parent['declaration']['source'])),
            'treeSha256': hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            'selectedEntries': len(rows), 'layer': parent['layer']})
    result = {'kind': 'verified-compressed-copy-handoffs', 'path': str(archive_path),
        'sha256': sha(archive_path), 'bytes': archive_path.stat().st_size,
        'revision': producer.report['source']['revision'],
        'sourceSha256': producer.report['source']['sourceSha256'], 'stage': producer.stage,
        'records': records, 'maximumArchiveBytes': maximum_archive_bytes,
        'retirementAuthorized': False}
    producer.proof['compressedExports'] = result
    producer.record()
    return result


def consume(producer, proof, original_stage, source_name, destination_name, chown='root:root', chmod=None):
    """Materialize ONE original COPY without an intermediate extracted tree."""
    chunks = module('veyra-linux-oci-chunks')
    producer.guard()
    need(proof['kind'] == 'verified-compressed-copy-handoffs' and
         proof['revision'] == producer.report['source']['revision'] and
         proof['sourceSha256'] == producer.report['source']['sourceSha256'], 'Actual current producer identity differs')
    archive_path = Path(proof['path'])
    need(archive_path.resolve() == archive_path and archive_path.is_relative_to(producer.operator.WORK) and
         archive_path.stat().st_size == proof['bytes'] and sha(archive_path) == proof['sha256'],
         'Actual immutable handoff archive differs')
    source_name = posixpath.normpath(source_name)
    choices = [row for row in proof['records'] if row['declaration']['producer'] == original_stage and
               posixpath.normpath(row['declaration']['source']) == source_name]
    need(len(choices) == 1 and chown == 'root:root', 'Exactly one original current COPY export required')
    record = choices[0]
    selector = record.get('selector', '.' if record['kind'] == 'directory' else record['fileName'])
    destination = producer.path(destination_name)
    if record['kind'] == 'file' and (destination_name.endswith('/') or destination.is_dir()):
        destination = destination / record['fileName']
    def attributes(path):
        return {key: base64.b64encode(os.getxattr(path, key, follow_symlinks=False)).decode()
                for key in sorted(os.listxattr(path, follow_symlinks=False))}
    def ensure_directory(path):
        if path.exists():
            need(path.is_dir() and not path.is_symlink() and path.resolve().is_relative_to(producer.root),
                 'COPY existing directory alias needs qualified namespace resolution')
            return
        need(path.parent.resolve().is_relative_to(producer.root), 'COPY new parent escaped')
        ensure_directory(path.parent)
        path.mkdir(mode=int(chmod, 8) if chmod is not None else 0o755)
        os.chown(path, 0, 0)
        os.chmod(path, int(chmod, 8) if chmod is not None else 0o755)
    ensure_directory(destination.parent)
    top_metadata = None
    if record['kind'] == 'directory':
        ensure_directory(destination)
        info = destination.lstat()
        top_metadata = {'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid,
                        'gid': info.st_gid, 'xattrs': attributes(destination)}
    before_rows, after_rows, seen, links = [], [], set(), []

    def slot(name):
        need(name == '.' or (not name.startswith('/') and '..' not in Path(name).parts and
             Path(name).as_posix() == name), 'COPY archive member escaped')
        path = destination / name if record['kind'] == 'directory' else destination
        need(record['kind'] != 'file' or name == record['fileName'], 'File export contained another member')
        need(path.parent.resolve().is_relative_to(producer.root), 'Existing COPY destination parent alias escaped')
        if path.is_dir():
            need(path.resolve().is_relative_to(producer.root), 'Existing COPY directory alias escaped')
        return path

    with archive_path.open('rb') as archive:
        layer = record['layer']
        # The closed archive range was independently compared to the actual
        # producer before export, and the whole archive identity above is fixed.
        compressed = chunks.Slice(archive.fileno(), layer['archiveBodyOffset'], layer['size'])
        with gzip.GzipFile(fileobj=compressed, mode='rb') as zipped:
            with tarfile.open(fileobj=zipped, mode='r|', encoding='utf-8', errors='surrogateescape') as tar:
                while True:
                    member = tar.next()
                    if member is None:
                        break
                    original_name = posixpath.normpath(member.name)
                    selected = selector == '.' or original_name == selector or original_name.startswith(selector.rstrip('/') + '/')
                    if not selected:
                        tar.members.clear()
                        continue
                    name = (record['fileName'] if record['kind'] == 'file' else
                            posixpath.relpath(original_name, selector) if selector != '.' else original_name)
                    need(name not in seen, 'Repeated original COPY member')
                    seen.add(name)
                    path = slot(name)
                    value = Decimal(member.pax_headers.get('mtime', str(member.mtime))) * 1_000_000_000
                    need(value == value.to_integral_value(), 'COPY timestamp lost nanoseconds')
                    row = {'path': name, 'mode': member.mode, 'uid': member.uid,
                        'gid': member.gid, 'mtimeNs': int(value), 'xattrs': {
                            key[len('SCHILY.xattr.'):]: base64.b64encode(val.encode('utf-8', 'surrogateescape')).decode()
                            for key, val in member.pax_headers.items() if key.startswith('SCHILY.xattr.')}}
                    prior_directory_attrs = attributes(path) if path.is_dir() and not path.is_symlink() else {}
                    if member.isdir():
                        need(not path.is_symlink(), 'COPY directory alias needs qualified namespace resolution')
                        path.mkdir(mode=0o700, exist_ok=True)
                        row['type'] = 'directory'
                    elif member.isfile():
                        temporary = path.with_name('.veyra-copy-' + path.name)
                        need(not temporary.exists() and not temporary.is_symlink(), 'Unresolved original COPY temporary')
                        h = hashlib.sha256()
                        with tar.extractfile(member) as source, temporary.open('xb') as output:
                            for block in iter(lambda: source.read(1024 * 1024), b''):
                                h.update(block)
                                output.write(block)
                        os.replace(temporary, path)
                        row.update(type='file', bytes=member.size, sha256=h.hexdigest())
                    elif member.issym():
                        if path.exists() or path.is_symlink():
                            need(not path.is_dir() or path.is_symlink(), 'COPY cannot replace a real directory with a link')
                            path.unlink()
                        path.symlink_to(member.linkname)
                        row.update(type='symlink', target=member.linkname)
                    else:
                        need(member.islnk(), 'Original COPY special member is unrepresented')
                        linked = posixpath.normpath(member.linkname)
                        need(selector == '.' or linked == selector or linked.startswith(selector.rstrip('/') + '/'),
                             'Cross-subtree original hardlink needs actual source-byte reconstruction')
                        row.update(type='hardlink', target=posixpath.relpath(linked, selector) if selector != '.' else linked)
                        targets = [item for item in before_rows if item['path'] == row['target']]
                        need(len(targets) == 1 and targets[0]['type'] == 'file',
                             'COPY hardlink target is not a preceding regular inode')
                        target = targets[0]
                        need(all(row[key] == target[key] for key in ('mode', 'uid', 'gid', 'mtimeNs')) and
                             (not row['xattrs'] or row['xattrs'] == target['xattrs']),
                             'COPY hardlink header conflicts with its inode')
                        row['xattrs'] = dict(target['xattrs'])
                        links.append(row)
                    before_rows.append(row)
                    expected = {**row, 'uid': 0, 'gid': 0}
                    if row['type'] == 'directory':
                        prior_directory_attrs.pop('security.capability', None)
                        expected['xattrs'] = {**prior_directory_attrs, **row['xattrs']}
                    if name == '.' and row['type'] == 'directory':
                        expected.update(top_metadata)
                    elif chmod is not None and row['type'] != 'symlink':
                        expected['mode'] = int(chmod, 8)
                    after_rows.append(expected)
                    tar.members.clear()
                while tail := tar.fileobj.read(65536):
                    need(not any(tail), 'Unexpected original COPY tar tail')
    need(len(before_rows) == record.get('selectedEntries', record['layer']['entries']) and hashlib.sha256(json.dumps(
        sorted(before_rows, key=lambda row: row['path']), sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        == record['treeSha256'], 'Actual decompressed COPY projection differs')
    for row in links:
        source, target = slot(row['target']), slot(row['path'])
        need(source.is_file() and not source.is_symlink(), 'COPY hardlink target is not a restored actual file')
        if target.exists() or target.is_symlink():
            need(not target.is_dir(), 'COPY hardlink cannot replace a directory')
            target.unlink()
        os.link(source, target, follow_symlinks=False)
    for row in sorted(after_rows, key=lambda row: len(Path(row['path']).parts), reverse=True):
        path = slot(row['path'])
        if not (record['kind'] == 'directory' and row['path'] == '.'):
            os.chown(path, row['uid'], row['gid'], follow_symlinks=False)
            if row['type'] != 'symlink':
                os.chmod(path, row['mode'])
            for key, val in row['xattrs'].items():
                os.setxattr(path, key, base64.b64decode(val), follow_symlinks=False)
        os.utime(path, ns=(row['mtimeNs'], row['mtimeNs']), follow_symlinks=False)
    if record['kind'] == 'directory':
        # Only selected COPY members are compared: other earlier original COPY
        # members in a merge destination are retained, not silently removed.
        actual = {row['path']: row for row in chunks.snapshot(destination, selected=[row['path'] for row in after_rows])}
        need(all(actual.get(row['path']) == row for row in after_rows), 'Actual restored COPY metadata/bytes differ')
    else:
        info = destination.lstat()
        expected = after_rows[0]
        need(info.st_uid == 0 and info.st_gid == 0 and info.st_mode & 0o7777 == expected['mode'] and
             info.st_mtime_ns == expected['mtimeNs'] and sha(destination) == expected['sha256'] and
             {key: base64.b64encode(os.getxattr(destination, key, follow_symlinks=False)).decode()
              for key in sorted(os.listxattr(destination, follow_symlinks=False))} == expected['xattrs'],
             'Actual restored COPY file differs')
    producer.proof.setdefault('consumedExports', []).append({'producer': original_stage,
        'source': source_name, 'destination': destination_name, 'actualProjectionVerified': True,
        'archiveSha256': proof['sha256'], 'treeSha256': record['treeSha256']})
    producer.guard()
    producer.record()
