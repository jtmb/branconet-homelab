"""Preserve fixed inactive legacy Plex trees; no source deletion in this helper."""
import argparse
import base64
import datetime
import decimal
import hashlib
import io
import json
import os
from pathlib import Path, PureWindowsPath
import shlex
import socket
import stat
import subprocess
import sys
import tarfile
import time

BASE = Path('/var') / 'plex-stack'
ROOTS = ('plex2/config', 'plex2/config.old')
NODE_UUID = '960bc2c7-2a7e-4bc2-b2c5-dbb6d71207f4'
F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
R = F / 'node-cleanup-20261027/worker2-legacy-plex-preservation'
AGE = Path('/home/brajam/.local/share/branconet-migration/bin/age')
AGE_SHA = 'eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c'
FLOOR = 15 * 1024**3


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def identity(path):
    s = path.lstat()
    return {k: getattr(s, 'st_' + k) for k in ('dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks')}


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024**2), b''):
            value.update(block)
    return value.hexdigest()


def attrs(path):
    return {k: base64.b64encode(os.getxattr(path, k, follow_symlinks=False)).decode()
            for k in sorted(os.listxattr(path, follow_symlinks=False))}


def scope(root_required=False):
    need(socket.gethostname() == 'workernode2' and (not root_required or os.geteuid() == 0), 'fixed_original_worker2')
    fs = json.loads(subprocess.check_output(['findmnt', '-J', '-T', str(BASE), '-o', 'UUID,SOURCE,FSTYPE'], timeout=30))['filesystems'][0]
    need(fs['uuid'] == NODE_UUID and fs['fstype'] == 'ext4', 'original_root_not_network_or_volume')
    for rel in ROOTS:
        p = BASE / rel
        need(p.resolve() == p and p.is_dir(), 'canonical_original_tree')
        need(not any((d / '.git').exists() for d in [p, *p.parents]), 'git_source_refused')
    return fs


def paths():
    for rel in ROOTS:
        root = BASE / rel
        for parent, dirs, files in os.walk(root, followlinks=False):
            parent = Path(parent)
            yield parent
            dirs.sort()
            for name in list(dirs):
                p = parent / name
                if p.is_symlink():
                    dirs.remove(name)
                    yield p
            for name in sorted(files):
                yield parent / name


def reference_checker(source, digest, base, roots):
    raw = base64.b64decode(source, validate=True)
    need(hashlib.sha256(raw).hexdigest() == digest, 'reviewed_reference_source')
    common = {'__name__': 'legacy_plex_reference_checks'}
    exec(compile(raw, '<reviewed-reference-checks>', 'exec'), common)
    common.update(BASE=base, ATTEMPTS=roots)
    return common


def inventory(a):
    fs = scope(True)
    common = reference_checker(a.safety_source, a.safety_sha256, BASE, ROOTS)
    before_refs = common['idle']()
    rows = []
    regular = 0
    device = os.stat('/').st_dev
    for p in paths():
        need(len(rows) < 150000 and p.name != '.git' and p.parent.resolve() == p.parent, 'bounded_tree_without_git_or_alias')
        s = p.lstat()
        info = identity(p)
        need(s.st_dev == device and (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode) or stat.S_ISLNK(s.st_mode)), 'regular_directory_or_link_on_root')
        kind = 'file' if stat.S_ISREG(s.st_mode) else 'directory' if stat.S_ISDIR(s.st_mode) else 'symlink'
        row = {'relative': str(p.relative_to(BASE)), 'kind': kind, 'identity': info,
               'atimeNS': s.st_atime_ns, 'xattrs': attrs(p)}
        if kind == 'file':
            need(s.st_nlink == 1 and s.st_size <= 512 * 1024**2, 'single_link_bounded_file')
            need(time.time_ns() - max(s.st_mtime_ns, s.st_ctime_ns) >= 72 * 3600 * 10**9, 'file_retention_age')
            row['sha256'] = sha(p)
            regular += s.st_size
            need(regular <= 16 * 1024**3, 'total_legacy_state_bound')
        elif kind == 'symlink':
            row['linkTarget'] = os.readlink(p)
        need(identity(p) == info, 'source_changed_during_inventory')
        rows.append(row)
    expected = {row['relative']: row['identity'] for row in rows}
    need({str(p.relative_to(BASE)): identity(p) for p in paths()} == expected, 'complete_stable_source_tree')
    after_refs = common['idle']()
    result = {'schema': 1, 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'filesystem': fs,
              'roots': list(ROOTS), 'rows': rows, 'fileBytes': regular,
              'allocatedFileBytes': sum(row['identity']['blocks'] * 512 for row in rows if row['kind'] == 'file'),
              'maxFileBytes': max(row['identity']['size'] for row in rows if row['kind'] == 'file'),
              'counts': {kind: sum(row['kind'] == kind for row in rows) for kind in ('file', 'directory', 'symlink')},
              'referencesBefore': before_refs, 'referencesAfter': after_refs, 'sourceDeleted': False}
    need(len(canonical(result)) <= 192 * 1024**2, 'bounded_profile')
    print(json.dumps(result))


def header(row):
    s = row['identity']
    info = tarfile.TarInfo('tree/' + row['relative'])
    info.uid, info.gid, info.mode = s['uid'], s['gid'], stat.S_IMODE(s['mode'])
    info.type = {'file': tarfile.REGTYPE, 'directory': tarfile.DIRTYPE, 'symlink': tarfile.SYMTYPE}[row['kind']]
    info.size = s['size'] if row['kind'] == 'file' else 0
    info.mtime = s['mtime_ns'] // 10**9
    for key, value in [('mtime', s['mtime_ns']), ('atime', row['atimeNS'])]:
        info.pax_headers[key] = f'{value // 10**9}.{value % 10**9:09d}'
    for name, value in row['xattrs'].items():
        info.pax_headers['SCHILY.xattr.' + name] = base64.b64decode(value).decode('utf8', 'surrogateescape')
    if row['kind'] == 'symlink':
        info.linkname = row['linkTarget']
    return info


class HashedReader:
    def __init__(self, source):
        self.source, self.digest, self.count = source, hashlib.sha256(), 0

    def read(self, count):
        block = self.source.read(count)
        self.digest.update(block)
        self.count += len(block)
        return block


def stream(profile):
    scope()
    need(profile['roots'] == list(ROOTS), 'fixed_profile_roots')
    expected = {row['relative']: row['identity'] for row in profile['rows']}
    need({str(p.relative_to(BASE)): identity(p) for p in paths()} == expected, 'source_before_archive')
    with tarfile.open(fileobj=sys.stdout.buffer, mode='w|', format=tarfile.PAX_FORMAT,
                      encoding='utf8', errors='surrogateescape') as archive:
        raw = canonical(profile)
        first = tarfile.TarInfo('manifest.json')
        first.size, first.mode = len(raw), 0o600
        archive.addfile(first, io.BytesIO(raw))
        for row in profile['rows']:
            p = BASE / row['relative']
            need(identity(p) == row['identity'] and attrs(p) == row['xattrs'], 'source_before_member')
            if row['kind'] == 'file':
                fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(fd, 'rb') as source:
                    actual = os.fstat(source.fileno())
                    need((actual.st_dev, actual.st_ino, actual.st_size) ==
                         (row['identity']['dev'], row['identity']['ino'], row['identity']['size']), 'opened_original_inode')
                    reader = HashedReader(source)
                    archive.addfile(header(row), reader)
                    need(reader.count == row['identity']['size'] and reader.digest.hexdigest() == row['sha256'], 'source_full_archive_sha256')
            else:
                if row['kind'] == 'symlink':
                    need(os.readlink(p) == row['linkTarget'], 'source_link_changed')
                archive.addfile(header(row))
            need(identity(p) == row['identity'], 'source_after_member')
    need({str(p.relative_to(BASE)): identity(p) for p in paths()} == expected, 'complete_source_after_archive')


def encrypt(profile):
    need(F.is_mount() and sha(AGE) == AGE_SHA, 'owned_mount_and_age_identity')
    remote = 'import sys;sys.argv=["legacy", "stream"]\n' + Path(__file__).read_text()
    command = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
               '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.5',
               shlex.join(['python3', '-B', '-c', remote])]
    producer = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    crypt = None
    try:
        env = dict(os.environ, GOMAXPROCS='1', GOMEMLIMIT='64MiB', TMPDIR=str(R), TMP=str(R), TEMP=str(R))
        crypt = subprocess.Popen([str(AGE), '-R', '/home/brajam/.ssh/id_ed25519.pub'], stdin=producer.stdout,
                                 stdout=sys.stdout.buffer, stderr=subprocess.DEVNULL, env=env)
        producer.stdout.close()
        producer.stdin.write(canonical(profile))
        producer.stdin.close()
        need(crypt.wait(timeout=3600) == 0 and producer.wait(timeout=60) == 0, 'complete_encrypted_tree_stream')
    finally:
        for child in (crypt, producer):
            if child is not None and child.poll() is None:
                child.terminate()
                child.wait(timeout=30)


def restored_metadata(path, row):
    s = row['identity']
    os.chown(path, s['uid'], s['gid'], follow_symlinks=False)
    if row['kind'] != 'symlink':
        os.chmod(path, stat.S_IMODE(s['mode']))
    for name, value in row['xattrs'].items():
        os.setxattr(path, name, base64.b64decode(value), follow_symlinks=False)
    os.utime(path, ns=(row['atimeNS'], s['mtime_ns']), follow_symlinks=False)
    current = path.lstat()
    need((current.st_uid, current.st_gid, stat.S_IMODE(current.st_mode), current.st_mtime_ns, current.st_atime_ns) ==
         (s['uid'], s['gid'], stat.S_IMODE(s['mode']), s['mtime_ns'], row['atimeNS']) and attrs(path) == row['xattrs'],
         'independent_restored_numeric_metadata_and_xattrs')


def restore_budget(profile):
    largest = max(row['identity']['size'] for row in profile['rows'] if row['kind'] == 'file')
    need(largest == profile['maxFileBytes'], 'measured_largest_member')
    # Only ancestors and one 500-object batch survive between purges.
    depth = max(len(Path(row['relative']).parts) for row in profile['rows'])
    return (503 + depth) * 4096 + max(256 * 1024**2, largest) + 64 * 1024**2


def reconcile(a, profile):
    """Remove only reproducible, inactive scratch from the failed restoration."""
    need(os.geteuid() == 0 and F.is_mount(), 'owned_root_reconciliation')
    fs = json.loads(subprocess.check_output(['findmnt', '-J', '-T', str(F), '-o', 'UUID,FSTYPE'], timeout=30))['filesystems'][0]
    need(fs['uuid'] == '3c792469-ea0e-4a2c-98e8-1185b141607b' and fs['fstype'] == 'ext4', 'original_owned_output_volume')
    work = R / 'restore-batch'
    failed = json.loads((R / 'restore-receipt.json').read_text())
    backup = json.loads((R / 'backup-receipt.json').read_text())
    need(failed['status'] == 'failed' and failed['errorCategory'] == 'per_member_restore_floor'
         and failed['sourceDeleted'] is False and backup['sourceOriginalsDeleted'] is False,
         'preserved_exact_space_failure')
    need(backup['profileSHA256'] == sha(a.profile) and backup['archiveBytes'] > 0
         and PureWindowsPath(backup['archive']).name == 'sha256-' + backup['archiveSHA256'] + '.age',
         'original_profile_and_completed_regenerator')
    frozen = R / 'archive-frozen.py'
    need(sha(frozen) == backup['helperSHA256'], 'original_restore_regeneration_source')
    common = reference_checker(a.safety_source, a.safety_sha256, R, ('restore-batch',))
    before_refs = common['idle']()
    expected = {'tree/' + row['relative']: row for row in profile['rows']}
    records = []
    wrappers = {'.', 'tree', 'tree/plex2'}
    need(work.resolve() == work and work.is_dir(), 'exact_owned_scratch')
    for p in [work, *work.rglob('*')]:
        rel = str(p.relative_to(work))
        info = identity(p)
        need(info['dev'] == work.stat().st_dev and p.parent.resolve() == p.parent, 'scratch_same_filesystem_no_alias')
        if stat.S_ISDIR(info['mode']):
            need((rel in wrappers or expected.get(rel, {}).get('kind') == 'directory')
                 and info['uid'] == 0 and stat.S_IMODE(info['mode']) == 0o700, 'generated_directory_identity')
        else:
            need(rel in expected, 'only_profile_scratch_entries')
            row = expected[rel]
            if row['kind'] == 'file':
                need(stat.S_ISREG(info['mode']) and info['nlink'] == 1
                     and info['size'] == row['identity']['size'] and sha(p) == row['sha256'], 'reproducible_scratch_full_hash')
            else:
                need(row['kind'] == 'symlink' and stat.S_ISLNK(info['mode'])
                     and os.readlink(p) == row['linkTarget'], 'reproducible_scratch_link')
            source = row['identity']
            need((info['uid'], info['gid'], info['mode'], info['mtime_ns']) ==
                 (source['uid'], source['gid'], source['mode'], source['mtime_ns'])
                 and attrs(p) == row['xattrs'], 'preserved_verified_member_metadata')
        need(identity(p) == info, 'scratch_changed_during_qualification')
        records.append({'relative': rel, 'identity': info})
    common['idle']()
    need({str(p.relative_to(work)) for p in [work, *work.rglob('*')]} ==
         {item['relative'] for item in records}, 'complete_exact_scratch_set')
    result = {'status': 'started', 'sourceDeleted': False, 'regenerationArchive': backup['archive'],
              'regenerationSHA256': backup['archiveSHA256'], 'referencesBefore': before_refs,
              'records': records, 'removedAllocatedBytes': 0, 'removedEntries': 0}
    try:
        for item in sorted(records, key=lambda item: 0 if item['relative'] == '.' else len(Path(item['relative']).parts), reverse=True):
            path = work / item['relative']
            original = item['identity']
            current = identity(path)
            if stat.S_ISDIR(original['mode']):
                need((current['dev'], current['ino'], current['mode'], current['uid'], current['gid']) ==
                     tuple(original[k] for k in ('dev', 'ino', 'mode', 'uid', 'gid'))
                     and not any(path.iterdir()), 'empty_original_scratch_directory')
                path.rmdir()
            else:
                need(current == original, 'qualified_scratch_member_unchanged')
                path.unlink()
            result['removedAllocatedBytes'] += current['blocks'] * 512
            result['removedEntries'] += 1
        result['status'] = 'completed'
    finally:
        with (R / 'failed-restore-scratch-reconciliation.json').open('x') as out:
            json.dump(result, out)
        os.chown(R / 'failed-restore-scratch-reconciliation.json', 1000, 1000)
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}))


def verify(a, profile):
    need(os.geteuid() == 0 and F.is_mount() and sha(AGE) == AGE_SHA, 'bounded_root_restore')
    need(a.profile.resolve() == R / 'profile.json', 'fixed_profile_location')
    work = R / 'restore-batch'
    need(not work.exists() and not (R / 'restore-receipt.json').exists(), 'prior_restore_preserved')
    need(os.statvfs(F).f_frsize == 4096, 'measured_restore_block_size')
    budget = restore_budget(profile)
    need(os.statvfs(F).f_bavail * os.statvfs(F).f_frsize >= FLOOR + budget, 'initial_measured_restore_floor')
    work.mkdir(mode=0o700)
    (work / 'tree').mkdir(mode=0o700)
    (work / 'tree/plex2').mkdir(mode=0o700)
    common = reference_checker(a.safety_source, a.safety_sha256, R, ('restore-batch',))
    expected = {'tree/' + row['relative']: row for row in profile['rows']}
    need(len(expected) == len(profile['rows']), 'unique_profile_paths')
    pending, directories, completed, seen, verified = [], [], [], set(), {}
    result = {'status': 'started', 'counts': {'file': 0, 'directory': 0, 'symlink': 0},
              'scratchRemovedAllocatedBytes': 0, 'sourceDeleted': False, 'restoreWorkingBudgetBytes': budget}

    def signature(row):
        return hashlib.sha256(canonical(row)).hexdigest()

    def purge():
        common['idle']()
        for path, original in pending:
            need(identity(path) == original, 'inactive_restored_member_identity')
            path.unlink()
            result['scratchRemovedAllocatedBytes'] += original['blocks'] * 512
        pending.clear()
        for path, row in completed:
            need(path.resolve() == path and not any(path.iterdir()), 'empty_owned_restored_directory')
            restored_metadata(path, row)
            verified['tree/' + row['relative']] = signature(row)
            result['counts']['directory'] += 1
            allocated = path.stat().st_blocks * 512
            path.rmdir()
            result['scratchRemovedAllocatedBytes'] += allocated
        completed.clear()

    env = dict(os.environ, GOMAXPROCS='1', GOMEMLIMIT='64MiB', TMPDIR=str(work), TMP=str(work), TEMP=str(work))
    crypt = subprocess.Popen([str(AGE), '-d', '-i', '/home/brajam/.ssh/id_ed25519'], stdin=sys.stdin.buffer,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
    try:
        with tarfile.open(fileobj=crypt.stdout, mode='r|', encoding='utf8', errors='surrogateescape') as archive:
            pending_bytes = 0
            for member in archive:
                need(member.name not in seen and len(seen) <= 150000, 'bounded_unique_member_set')
                seen.add(member.name)
                if member.name == 'manifest.json':
                    need(len(seen) == 1 and member.isfile() and member.size == len(canonical(profile)), 'exact_first_manifest')
                    need(archive.extractfile(member).read() == canonical(profile), 'full_profile_manifest_match')
                    continue
                need(member.name in expected, 'unexpected_member_refused')
                row = expected[member.name]
                # The producer walks each directory depth first. Close only
                # subtrees left by the next member; parents remain available.
                while directories and not member.name.startswith('tree/' + directories[-1][1]['relative'] + '/'):
                    completed.append(directories.pop())
                if len(pending) + len(completed) >= 500:
                    purge()
                    pending_bytes = 0
                s = row['identity']
                need(member.uid == s['uid'] and member.gid == s['gid'] and member.mode == stat.S_IMODE(s['mode']), 'archive_owner_mode')
                for key, ns in [('mtime', s['mtime_ns']), ('atime', row['atimeNS'])]:
                    need(int(decimal.Decimal(member.pax_headers[key]) * 10**9) == ns, 'archive_time_precision')
                packed = {key[len('SCHILY.xattr.'):]: base64.b64encode(value.encode('utf8', 'surrogateescape')).decode()
                          for key, value in member.pax_headers.items() if key.startswith('SCHILY.xattr.')}
                need(packed == row['xattrs'], 'archive_extended_attributes')
                path = work / member.name
                need(path.parent.resolve() == path.parent and path.is_relative_to(work), 'safe_restored_parent')
                if row['kind'] == 'directory':
                    need(member.isdir(), 'directory_type')
                    path.mkdir(mode=0o700)
                    directories.append((path, row))
                    continue
                if pending and (len(pending) >= 500 or pending_bytes + member.size > 256 * 1024**2):
                    purge()
                    pending_bytes = 0
                fs = os.statvfs(F)
                if pending and fs.f_bavail * fs.f_frsize < FLOOR + member.size + 64 * 1024**2:
                    purge()
                    pending_bytes = 0
                    fs = os.statvfs(F)
                need(fs.f_bavail * fs.f_frsize >= FLOOR + member.size + 64 * 1024**2, 'per_member_restore_floor')
                if row['kind'] == 'file':
                    need(member.isfile() and member.size == s['size'] <= 512 * 1024**2, 'bounded_file_member')
                    source = archive.extractfile(member)
                    with path.open('xb') as out:
                        count = 0
                        for block in iter(lambda: source.read(1024**2), b''):
                            count += len(block)
                            need(count <= member.size, 'member_byte_bound')
                            out.write(block)
                        out.flush()
                        os.fsync(out.fileno())
                    need(count == member.size and sha(path) == row['sha256'], 'independent_full_file_readback')
                else:
                    need(member.issym() and member.linkname == row['linkTarget'], 'exact_symlink_target')
                    os.symlink(member.linkname, path)
                    need(os.readlink(path) == row['linkTarget'], 'restored_symlink_target')
                restored_metadata(path, row)
                verified[member.name] = signature(row)
                result['counts'][row['kind']] += 1
                pending.append((path, identity(path)))
                pending_bytes += path.lstat().st_blocks * 512
            while directories:
                completed.append(directories.pop())
            purge()
        need(seen == set(expected) | {'manifest.json'}, 'every_archive_member_seen')
        trailing = crypt.stdout.read(1024**2 + 1)
        need(len(trailing) <= 1024**2 and not any(trailing) and crypt.wait(timeout=60) == 0, 'complete_nas_age_authentication')
        common['idle']()
        for path in [work / 'tree/plex2', work / 'tree', work]:
            need(path.resolve() == path and not any(path.iterdir()), 'empty_owned_wrapper')
            allocated = path.stat().st_blocks * 512
            path.rmdir()
            result['scratchRemovedAllocatedBytes'] += allocated
        need(result['counts'] == profile['counts'] and verified == {name: signature(row) for name, row in expected.items()}, 'all_entry_verification_counts_and_signatures')
        result.update(status='completed', completeAgeAuthentication=True, everyEntryIndependentlyRestored=True,
                      verifiedEntryDigest=hashlib.sha256(canonical(verified)).hexdigest(),
                      sourceProfileSHA256=hashlib.sha256(canonical(profile)).hexdigest(), scratchReconciled=True)
    except Exception as error:
        result.update(status='failed', errorCategory=str(error) if isinstance(error, ValueError) else type(error).__name__,
                      retainedScratch=str(work), retentionReason='restore or preservation proof incomplete')
        raise
    finally:
        if crypt.poll() is None:
            crypt.terminate()
            crypt.wait(timeout=30)
        receipt = R / 'restore-receipt.json'
        with receipt.open('x') as out:
            json.dump(result, out, indent=2)
            out.write('\n')
        os.chown(receipt, 1000, 1000)
        print(json.dumps(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['inventory', 'stream', 'encrypt', 'verify', 'reconcile'])
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--safety-source', default='')
    parser.add_argument('--safety-sha256', default='')
    a = parser.parse_args()
    os.setpriority(os.PRIO_PROCESS, 0, 15)
    if a.mode == 'inventory':
        inventory(a)
        return
    profile = json.load(sys.stdin) if a.mode == 'stream' else json.loads(a.profile.read_text())
    need(profile['schema'] == 1 and profile['roots'] == list(ROOTS) and 0 < len(profile['rows']) <= 150000
         and profile['fileBytes'] <= 16 * 1024**3, 'bounded_fixed_profile')
    if a.mode == 'stream':
        stream(profile)
    elif a.mode == 'encrypt':
        encrypt(profile)
    elif a.mode == 'reconcile':
        reconcile(a, profile)
    else:
        verify(a, profile)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('legacy_plex_preservation_refused:' + (str(error) if isinstance(error, ValueError) else type(error).__name__), file=sys.stderr)
        raise SystemExit(1)
