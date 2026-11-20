#!/usr/bin/env python3
"""Exact-source contract and lossless serial producer handoffs.

This module does not claim a host compile is a Bookworm compile. It preserves
the pinned Dockerfile producer contracts, and provides compressed handoffs that
can be verified before an owned producer filesystem reaches its last consumer.
The existing full paired-storage/exclusive-platform admission remains required.
No compiler, package acquisition, image publication or deployment is implicit.
"""
import argparse
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys
import tarfile
import time

sys.dont_write_bytecode = True


def need(value, message):
    if not value:
        raise RuntimeError(message)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def existing_operator():
    path = Path(__file__).with_name('veyra-linux-build.py')
    spec = importlib.util.spec_from_file_location('veyra_original_serial_operator', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def instructions(path):
    result, pending = [], ''
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        pending += line[:-1] + ' ' if line.endswith('\\') else line
        if line.endswith('\\'):
            continue
        match = re.fullmatch(r'([A-Z]+)\s+(.*)', pending)
        need(match is not None, 'Unparsed Dockerfile instruction at ' + str(number))
        result.append({'instruction': match[1], 'value': match[2], 'endLine': number})
        pending = ''
    need(not pending, 'Incomplete Dockerfile continuation')
    return result


def contract(operator, report):
    stages, active = {}, None
    for row in instructions(operator.APP / 'Dockerfile'):
        if row['instruction'] == 'FROM':
            fields = shlex.split(row['value'])
            need(len(fields) == 3 and fields[1].upper() == 'AS', 'Named, fixed stages required')
            need(fields[2] not in stages, 'Duplicate producer stage')
            active = {'base': fields[0], 'instructions': []}
            stages[fields[2]] = active
        elif active is not None:
            active['instructions'].append(row)
    required = {'node-dependencies', 'swarm-budget-builder', 'swarm-rust-builder',
                'builder', 'vendor-security', 'computer-use', 'rust-api-builder',
                'runtime-base', 'veyra-node-artifact'}
    need(required <= set(stages), 'Original complete producer graph absent')
    need(stages['node-dependencies']['base'] == report['nodeBase'] and
         stages['runtime-base']['base'] == report['nodeBase'] and
         stages['swarm-rust-builder']['base'] == report['rustBase'] and
         stages['rust-api-builder']['base'] == report['rustBase'], 'Pinned compiler/runtime bases changed')
    exports = []
    for row in stages['veyra-node-artifact']['instructions']:
        need(row['instruction'] == 'COPY', 'Artifact target acquired another instruction')
        fields = shlex.split(row['value'])
        need(len(fields) == 3 and fields[0].startswith('--from='), 'Explicit one-source artifact export required')
        exports.append({'producer': fields[0][7:], 'source': fields[1], 'target': fields[2]})
    builder_exports = [row for row in exports if row['producer'] == 'builder']
    need(len(builder_exports) == 21 and {row['producer'] for row in exports} ==
         {'builder', 'vendor-security', 'computer-use'}, 'Original 21 builder exports plus vendor/computer-use must survive')
    run_programs = {name: [row['value'] for row in stage['instructions'] if row['instruction'] == 'RUN']
                    for name, stage in stages.items()}
    result = {'schemaVersion': 1, 'source': report['source'],
        'dockerfileSha256': digest(operator.APP / 'Dockerfile'),
        'npmLockSha256': report['npmLockSha256'],
        'linuxBuildLockSha256': report['linuxBuildLockSha256'],
        'cargo': report['cargo'], 'extension': report['extension'],
        'nodeCompilerAndRuntimeBase': report['nodeBase'], 'rustCompilerBase': report['rustBase'],
        'producerRunPrograms': run_programs, 'stages': stages, 'exports': exports,
        'builderExportCount': len(builder_exports),
        'serialOrder': ['budget', 'swarm', 'rust', 'node', 'image'],
        'hostNodeSubstitutionAllowed': False,
        'originalRuntimeRunProgramsRequired': True,
        'noBuildDownloadOrInstallStarted': True,
        'executionQualified': False,
        'remainingQualification': [
            'Pinned producer rootfs isolation and exact original RUN/COPY/ENV/ARG semantics',
            'Complete signed APT builder/runtime OS inputs and native ABI parity',
            'Full simultaneous per-stage physical peak including npm cache/install, Rust SDK/target, exports and OCI',
            'Fresh original paired-storage admission and released exclusive Linux lease',
            'All original final filesystem/security checks and runtime gates']}
    result['contractSha256'] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return result


def tree_rows(root):
    """Metadata and bytes, including hardlink topology; reject lost xattrs."""
    need(root.resolve() == root and root.is_dir(), 'Canonical real handoff directory required')
    root_info = root.stat()
    need(not os.listxattr(root, follow_symlinks=False), 'Root extended metadata is not represented')
    rows = [{'path': '.', 'type': 'directory', 'mode': root_info.st_mode & 0o7777,
             'uid': root_info.st_uid, 'gid': root_info.st_gid, 'mtimeNs': root_info.st_mtime_ns}]
    inodes = {}
    def fail(error):
        raise error
    for directory, names, files in os.walk(root, followlinks=False, onerror=fail):
        names.sort()
        files.sort()
        for name in sorted(names + files):
            path = Path(directory) / name
            info = path.lstat()
            need(info.st_dev == root.stat().st_dev, 'Handoff crossed a filesystem')
            need(not os.listxattr(path, follow_symlinks=False), 'Extended metadata needs explicit lossless representation: ' + str(path))
            row = {'path': path.relative_to(root).as_posix(), 'mode': info.st_mode & 0o7777,
                   'uid': info.st_uid, 'gid': info.st_gid, 'mtimeNs': info.st_mtime_ns}
            if stat.S_ISREG(info.st_mode):
                key = (info.st_dev, info.st_ino)
                if key in inodes:
                    row.update(type='hardlink', target=inodes[key])
                else:
                    inodes[key] = row['path']
                    row.update(type='file', bytes=info.st_size, sha256=digest(path))
            elif stat.S_ISDIR(info.st_mode):
                row['type'] = 'directory'
            else:
                need(stat.S_ISLNK(info.st_mode), 'Special handoff file requires separate handling: ' + str(path))
                row.update(type='symlink', target=os.readlink(path))
            rows.append(row)
    return sorted(rows, key=lambda row: row['path'])


def row_hash(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def pack(root, destination, maximum):
    """No retirement here: caller must use the original last-consumer checks."""
    need(maximum > 0 and not destination.exists(), 'Positive admitted output bound and exclusive destination required')
    need(destination.parent.resolve() == destination.parent and not destination.is_relative_to(root),
         'Archive must be outside the producer, with canonical parent')
    before = tree_rows(root)
    class LimitedWriter:
        def __init__(self, raw):
            self.raw = raw
        def write(self, body):
            need(self.raw.tell() + len(body) <= maximum,
                 'Compressed handoff would exceed admitted bound; retain partial original')
            return self.raw.write(body)
        def flush(self):
            return self.raw.flush()
    with destination.open('xb') as raw, gzip.GzipFile(
            filename='', fileobj=LimitedWriter(raw), mode='wb', mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as archive:
            for row in before:
                source = root / row['path']
                member = tarfile.TarInfo(row['path'])
                member.uid, member.gid, member.mode = row['uid'], row['gid'], row['mode']
                # Explicit integer nanoseconds avoid float/time normalization.
                member.pax_headers['veyra.mtime_ns'] = str(row['mtimeNs'])
                seconds, nanos = divmod(abs(row['mtimeNs']), 1_000_000_000)
                member.pax_headers['mtime'] = ('-' if row['mtimeNs'] < 0 else '') + f'{seconds}.{nanos:09d}'
                member.mtime = row['mtimeNs'] // 1_000_000_000
                if row['type'] == 'file':
                    member.size = row['bytes']
                    with source.open('rb') as stream:
                        archive.addfile(member, stream)
                elif row['type'] == 'directory':
                    member.type = tarfile.DIRTYPE
                    archive.addfile(member)
                else:
                    member.type = tarfile.SYMTYPE if row['type'] == 'symlink' else tarfile.LNKTYPE
                    member.linkname = row['target']
                    archive.addfile(member)
                need(raw.tell() <= maximum, 'Compressed handoff exceeded its admitted bound; retain partial original')
    need(destination.stat().st_size <= maximum, 'Final compressed handoff exceeded admitted bound')
    need(tree_rows(root) == before, 'Producer changed during handoff; retain both original views')
    result = {'archive': str(destination), 'bytes': destination.stat().st_size,
              'sha256': digest(destination), 'treeSha256': row_hash(before), 'entries': len(before),
              'regularFileBytes': sum(row.get('bytes', 0) for row in before),
              'source': str(root), 'retirementAuthorized': False}
    verify(root, destination, result)
    return result


def verify(root, archive_path, proof):
    need(digest(archive_path) == proof['sha256'] and archive_path.stat().st_size == proof['bytes'],
         'Compressed handoff identity changed')
    expected = tree_rows(root)
    actual, seen = [], set()
    with tarfile.open(archive_path, mode='r|gz') as archive:
        for member in archive:
            need(member.name not in seen and member.name not in ('', '..') and
                 not member.name.startswith('/') and '..' not in Path(member.name).parts,
                 'Handoff member path escaped or repeated')
            need(member.name != '.' or member.isdir(), 'Root handoff member must be a directory')
            seen.add(member.name)
            row = {'path': member.name.rstrip('/'), 'uid': member.uid, 'gid': member.gid,
                   'mode': member.mode, 'mtimeNs': int(member.pax_headers['veyra.mtime_ns'])}
            if member.isfile():
                h = hashlib.sha256()
                with archive.extractfile(member) as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        h.update(block)
                row.update(type='file', bytes=member.size, sha256=h.hexdigest())
            elif member.isdir():
                row['type'] = 'directory'
            else:
                need(member.issym() or member.islnk(), 'Unqualified handoff member kind')
                row.update(type='symlink' if member.issym() else 'hardlink', target=member.linkname)
            actual.append(row)
    actual.sort(key=lambda row: row['path'])
    need(actual == expected and row_hash(actual) == proof['treeSha256'], 'Lossless handoff projection differs')
    return {'verified': True, 'entries': len(actual), 'treeSha256': row_hash(actual),
            'originalProducerRetained': True}


def restore(destination, archive_path, proof, *, operator=None):
    """Restore into a NEW original-WORK child; never follow archived symlinks.

    The calling complete executor must first obtain the original fresh admission
    and reserve this actual output coexistence. This library operation never
    authorizes retirement or substitutes for original compiler/ABI provenance.
    """
    if operator is None:
        operator = existing_operator()
    need(os.getuid() == 0, 'Original root-owned isolated executor required')
    need(destination.parent.resolve() == destination.parent and
         destination.is_relative_to(operator.WORK) and not destination.exists(),
         'Exclusive original-WORK restoration destination required')
    need(archive_path.resolve() == archive_path and archive_path.is_relative_to(operator.WORK),
         'Only original owned compressed producer output may be restored')
    need(digest(archive_path) == proof['sha256'] and archive_path.stat().st_size == proof['bytes'],
         'Verified compressed handoff changed before restoration')
    destination.mkdir(mode=0o700)
    rows, seen, links = [], set(), []
    regular_bytes = 0

    def target(name):
        need(name == '.' or (not name.startswith('/') and '..' not in Path(name).parts and
             Path(name).as_posix() == name), 'Noncanonical restore member')
        path = destination if name == '.' else destination / name
        cursor = path.parent
        while cursor != destination.parent:
            need(cursor.is_dir() and not cursor.is_symlink(), 'Restore parent is not a real directory')
            cursor = cursor.parent
        return path

    with tarfile.open(archive_path, mode='r|gz') as archive:
        for member in archive:
            name = member.name.rstrip('/')
            need(name not in seen, 'Repeated restore member')
            seen.add(name)
            need(len(seen) <= proof['entries'], 'Restore exceeded verified entry count')
            path = target(name)
            row = {'path': name, 'uid': member.uid, 'gid': member.gid,
                   'mode': member.mode, 'mtimeNs': int(member.pax_headers['veyra.mtime_ns'])}
            if member.isdir():
                if name != '.':
                    path.mkdir(mode=0o700)
                row['type'] = 'directory'
            elif member.isfile():
                need(name != '.', 'Root cannot be a file')
                regular_bytes += member.size
                need(regular_bytes <= proof['regularFileBytes'], 'Restore exceeded verified logical output bound')
                h = hashlib.sha256()
                with archive.extractfile(member) as source, path.open('xb') as output:
                    for block in iter(lambda: source.read(1024 * 1024), b''):
                        h.update(block)
                        output.write(block)
                row.update(type='file', bytes=member.size, sha256=h.hexdigest())
            elif member.issym():
                need(name != '.', 'Root cannot be a link')
                path.symlink_to(member.linkname)
                row.update(type='symlink', target=member.linkname)
            else:
                need(member.islnk() and name != '.', 'Unrepresented special restore member')
                row.update(type='hardlink', target=member.linkname)
                links.append(row)
            rows.append(row)
    need('.' in seen and row_hash(sorted(rows, key=lambda row: row['path'])) == proof['treeSha256'],
         'Compressed producer projection differs; retain incomplete restore')
    for row in links:
        original, path = target(row['target']), target(row['path'])
        need(original.is_file() and not original.is_symlink(), 'Hardlink target is not an actual restored file')
        os.link(original, path, follow_symlinks=False)
    # Restore children first, then directories/root after all materialization.
    for row in sorted(rows, key=lambda row: len(Path(row['path']).parts), reverse=True):
        path = target(row['path'])
        os.chown(path, row['uid'], row['gid'], follow_symlinks=False)
        if row['type'] != 'symlink':
            os.chmod(path, row['mode'])
        os.utime(path, ns=(row['mtimeNs'], row['mtimeNs']), follow_symlinks=False)
    current = tree_rows(destination)
    need(row_hash(current) == proof['treeSha256'], 'Actual restored bytes/metadata/topology differ')
    return {'destination': str(destination), 'restoredTreeSha256': row_hash(current),
            'actualRestoredProjectionVerified': True, 'retirementAuthorized': False}


def qualify_bases(operator, report, lease_path):
    """Fully verify pinned base tar streams in RAM; acquire/install nothing.

    A purpose-specific fresh serial lease is necessary even though only a small
    summary is returned. This is NOT a smaller compiler-stage admission.
    """
    need(os.getuid() == 0, 'Use original resource-bounded root-owned executor')
    need(lease_path.resolve() == lease_path and lease_path.is_relative_to(operator.ROOT),
         'Original confined coordinator lease required')
    lease = json.loads(lease_path.read_text())
    age = time.time() - dt.datetime.fromisoformat(lease['at'].replace('Z', '+00:00')).timestamp()
    need(lease['owner'] == operator.OWNER and lease['platform'] == 'linux' and
         lease['exclusive'] is True and lease['nativeStageActive'] is False and
         lease['purpose'] == 'streamed-base-qualification' and 0 <= age < 180,
         'Fresh exclusive bounded-qualification lease required; Native must be released')
    need(lease['sourceRevision'] == report['source']['revision'] and
         lease['sourceSha256'] == report['source']['sourceSha256'] and
         lease['extensionSha256'] == report['extension']['sourceSha256'], 'Qualification source differs')
    need(type(lease['nativeBudgetBytes']) is int and lease['nativeBudgetBytes'] > 0 and
         lease['growthBytes'] == 32 * 1024**2, 'Complete bounded-summary allocation required')
    growth = lease['growthBytes']
    need(operator.task_allocated() + lease['nativeBudgetBytes'] + growth <= operator.CEILING and
         report['windowsFreeBytes'] - growth >= operator.FLOOR and
         report['destinationFreeBytes'] - growth >= operator.FLOOR, 'Original paired ceiling/floors not admitted')
    cgroup = next(row[3:] for row in Path('/proc/self/cgroup').read_text().splitlines() if row.startswith('0::'))
    group = Path('/sys/fs/cgroup') / cgroup.lstrip('/')
    memory = (group / 'memory.max').read_text().strip()
    cpu = (group / 'cpu.max').read_text().split()
    need(memory != 'max' and 0 < int(memory) <= 4 * operator.GIB and cpu[0] != 'max' and
         0 < int(cpu[0]) / int(cpu[1]) <= 1.5, 'Original 4GiB/1.5CPU isolation is not active')
    sys.path.insert(0, str(operator.APP / 'ops'))
    from registry_image_reader import RegistryImageReader
    from registry_layer_inventory import inventory_layer
    lock = json.loads((operator.APP / 'tools/veyra-release/linux-build.lock.json').read_text())
    result = {'source': report['source'], 'qualifiedAt': operator.now(),
        'purpose': lease['purpose'], 'payloadFilesCreated': 0, 'compilerOrInstallStarted': False,
        'compilerStageAdmitted': False, 'physicalUnpackedPeakQualified': False, 'bases': {}}
    for name, repository, key in [('node', 'library/node', 'base'), ('rust', 'library/rust', 'rust')]:
        reader = RegistryImageReader(repository)
        pin = lock[key]['manifestDigest']
        image = reader.image(pin)
        need(image['selectedDigest'] == pin and image['manifest']['config']['digest'] == lock[key]['configDigest'],
             'Pinned base/config manifest differs')
        layers = []
        for descriptor, diff in zip(image['manifest']['layers'], image['config']['rootfs']['diff_ids']):
            inventory = inventory_layer(reader, descriptor, diff)
            rows = inventory['rows']
            layers.append({**{field: inventory[field] for field in [
                'compressedDigest', 'compressedBytes', 'diffId', 'inflatedBytes',
                'entries', 'logicalFileBytes', 'metadataBytes', 'unresolvedHardlinks']},
                'roundedFileDataBytes': sum(((row['bytes'] + 4095) // 4096) * 4096
                                           for row in rows if row['type'] == 'file'),
                'entryManifestSha256': hashlib.sha256(json.dumps(rows, sort_keys=True,
                    separators=(',', ':')).encode()).hexdigest(),
                'whiteouts': sum(row['type'] == 'whiteout' for row in rows),
                'extendedMetadataEntries': sum('paxHeadersSha256' in row for row in rows)})
            # The original authenticated stream and diff verification completed;
            # do not retain layer bodies or cumulative large per-entry records.
            del rows, inventory
        result['bases'][name] = {'manifestDigest': pin, 'configDigest': lock[key]['configDigest'],
            'layers': layers, 'allCompressedAndUncompressedStreamsVerified': True,
            'logicalFileBytesIncludingSupersededLayers': sum(row['logicalFileBytes'] for row in layers),
            'roundedFileDataBytesIncludingSupersededLayers': sum(row['roundedFileDataBytes'] for row in layers),
            'completeExtractionOrFilesystemAccepted': False}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['inspect', 'qualify-bases'])
    parser.add_argument('--revision', required=True)
    parser.add_argument('--lease', type=Path)
    args = parser.parse_args()
    operator = existing_operator()
    _, _, report = operator.inspect(args.revision, operator.PHASE / 'windows-source/integrations/browser-extension')
    if args.mode == 'inspect':
        result = contract(operator, report)
    else:
        need(args.lease is not None, 'Explicit original-root coordinator qualification lease required')
        result = qualify_bases(operator, report, args.lease.absolute())
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
