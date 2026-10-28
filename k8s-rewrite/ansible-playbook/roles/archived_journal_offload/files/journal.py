"""Preserve selected closed journals on NAS and qualify complete file recovery."""
import argparse
import base64
import datetime
import decimal
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import socket
import stat
import subprocess
import sys
import tarfile
import time

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
ROOT = Path('/var') / 'log' / 'journal'
UUID = '960bc2c7-2a7e-4bc2-b2c5-dbb6d71207f4'
NODES = {
    'workernode2': ('192.168.0.5', UUID),
    'masternode': ('192.168.0.4', '763cda3d-0777-4b03-a882-9d21060466e3'),
}
AGE = Path('/home/brajam/.local/share/branconet-migration/bin/age')
AGE_SHA = 'eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c'
FLOOR = 15 * 1024**3


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def ident(s):
    return {k: getattr(s, 'st_' + k) for k in ('dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks')}


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as inp:
        for block in iter(lambda: inp.read(1024**2), b''):
            value.update(block)
    return value.hexdigest()


def xattrs(path):
    return {k: base64.b64encode(os.getxattr(path, k)).decode() for k in sorted(os.listxattr(path))}


def checker(a, base, attempts):
    code = base64.b64decode(a.safety_source, validate=True)
    need(hashlib.sha256(code).hexdigest() == a.safety_sha256, 'reference_source_hash')
    common = {'__name__': 'journal_reference_checks'}
    exec(compile(code, '<reviewed-reference-checks>', 'exec'), common)
    common.update(BASE=base, ATTEMPTS=attempts)
    return common


def profile_node(profile):
    matches = [node for node, (_, uuid) in NODES.items() if uuid == profile['filesystem']['uuid']]
    need(len(matches) == 1, 'known_profile_filesystem')
    node = matches[0]
    need(profile.get('node', node) == node, 'profile_node_filesystem_binding')
    return node


def node_scope(node, require_root=True):
    need(node in NODES and (not require_root or os.geteuid() == 0)
         and socket.gethostname() == node, 'fixed_known_node_root_scope')
    fs = json.loads(subprocess.check_output(['findmnt', '--json', '--target', str(ROOT), '--output', 'UUID,SOURCE,FSTYPE'], timeout=30))['filesystems'][0]
    need(fs['uuid'] == NODES[node][1] and fs['fstype'] == 'ext4', 'original_node_root_filesystem')
    need(not any(ROOT.glob('*/fss')), 'sealing_key_requires_separate_recovery')
    return fs


def inventory(a):
    fs = node_scope(a.node)
    selected = json.loads(base64.b64decode(a.selection_base64, validate=True))['paths']
    need(1 <= len(selected) <= 32 and len(set(selected)) == len(selected), 'bounded_unique_journals')
    rows = []
    for value in sorted(selected):
        p = Path(value)
        need(p.resolve() == p and p.is_relative_to(ROOT), 'canonical_journal_path')
        rel = p.relative_to(ROOT)
        need(len(rel.parts) == 2 and re.fullmatch('[a-f0-9]{32}', rel.parts[0]) and '@' in p.name and p.name.endswith('.journal'), 'closed_journal_name')
        s = p.lstat()
        need(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1 and s.st_dev == os.stat('/').st_dev, 'regular_owned_single_link_journal')
        need(0 < s.st_size <= 128 * 1024**2 and time.time_ns() - max(s.st_mtime_ns, s.st_ctime_ns) >= 72 * 3600 * 10**9, 'journal_size_and_72_hour_retention')
        original = ident(s)
        h = sha(p)
        attrs = xattrs(p)
        need(ident(p.lstat()) == original, 'journal_changed_during_inventory')
        rows.append({'path': str(p), 'relative': str(rel), 'archiveName': 'journals/' + str(rel),
                     'identity': original, 'sha256': h, 'xattrs': attrs})
    need(sum(r['identity']['size'] for r in rows) <= 3 * 1024**3, 'archive_byte_bound')
    common = checker(a, ROOT, tuple(r['relative'] for r in rows))
    refs = common['idle']()
    out = {'schema': 1, 'node': a.node, 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'filesystem': fs,
           'files': rows, 'fileBytes': sum(r['identity']['size'] for r in rows),
           'allocatedBytes': sum(r['identity']['blocks'] * 512 for r in rows), 'references': refs, 'fssKeyPresent': False}
    print(json.dumps(out))


def header(row):
    s = row['identity']
    info = tarfile.TarInfo(row['archiveName'])
    info.size, info.uid, info.gid, info.mode = s['size'], s['uid'], s['gid'], stat.S_IMODE(s['mode'])
    info.mtime = s['mtime_ns'] // 10**9
    info.pax_headers['mtime'] = f"{s['mtime_ns'] // 10**9}.{s['mtime_ns'] % 10**9:09d}"
    for name, value in row['xattrs'].items():
        info.pax_headers['SCHILY.xattr.' + name] = base64.b64decode(value).decode('utf8', 'surrogateescape')
    return info


def stream(profile):
    node_scope(profile_node(profile), require_root=False)
    with tarfile.open(fileobj=sys.stdout.buffer, mode='w|', format=tarfile.PAX_FORMAT, encoding='utf8', errors='surrogateescape') as out:
        raw = canonical(profile)
        info = tarfile.TarInfo('manifest.json')
        info.size, info.mode = len(raw), 0o600
        out.addfile(info, io.BytesIO(raw))
        for row in profile['files']:
            p = Path(row['path'])
            need(p.resolve() == p and ident(p.lstat()) == row['identity'], 'source_before_archive')
            with p.open('rb') as inp:
                need(ident(os.fstat(inp.fileno())) == row['identity'], 'opened_source_identity')
                out.addfile(header(row), inp)
            need(ident(p.lstat()) == row['identity'] and sha(p) == row['sha256'], 'source_after_archive')


def encrypt(a, profile):
    need(F.is_mount() and sha(AGE) == AGE_SHA, 'owned_mount_and_age_identity')
    own = Path(__file__).read_text()
    args = ['journal', '--mode', 'stream', '--profile-base64', base64.b64encode(canonical(profile)).decode()]
    remote = 'import sys;sys.argv=' + repr(args) + '\n' + own
    ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
           '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts',
           '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@' + NODES[profile_node(profile)][0], shlex.join(['python3', '-B', '-c', remote])]
    producer = subprocess.Popen(ssh, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    crypt = None
    try:
        env = dict(os.environ, TMPDIR=str(F / 'operator-control/tmp'), TMP=str(F / 'operator-control/tmp'), TEMP=str(F / 'operator-control/tmp'), GOMEMLIMIT='32MiB', GOMAXPROCS='1')
        crypt = subprocess.Popen([str(AGE), '-R', '/home/brajam/.ssh/id_ed25519.pub'], stdin=producer.stdout, stdout=sys.stdout.buffer, stderr=subprocess.DEVNULL, env=env)
        producer.stdout.close()
        need(crypt.wait(timeout=1200) == 0 and producer.wait(timeout=60) == 0, 'complete_encrypted_source_stream')
    finally:
        for child in (crypt, producer):
            if child is not None and child.poll() is None:
                child.terminate()
                child.wait(timeout=30)


def verify(a, profile):
    need(os.geteuid() == 0 and F.is_mount() and sha(AGE) == AGE_SHA, 'root_restore_and_pinned_age')
    run = a.profile.parent
    need(run.resolve() == run and run.is_relative_to(F / 'node-cleanup-20261027'), 'owned_restore_root')
    work = run / 'restore-scratch'
    need(not work.exists(), 'prior_restore_preserved')
    need(os.statvfs(F).f_bavail * os.statvfs(F).f_frsize >= FLOOR + 256 * 1024**2, 'restore_space_floor')
    work.mkdir(mode=0o700)
    target = work / 'restored.journal'
    common = checker(a, run, ('restore-scratch',))
    result = {'status': 'started', 'restoredFiles': [], 'scratchRemovedAllocatedBytes': 0, 'sourceOriginalsDeleted': False}
    receipt = run / 'restore-receipt.json'
    need(not receipt.exists(), 'prior_restore_receipt_preserved')
    env = dict(os.environ, TMPDIR=str(F / 'operator-control/tmp'), TMP=str(F / 'operator-control/tmp'), TEMP=str(F / 'operator-control/tmp'), GOMEMLIMIT='32MiB', GOMAXPROCS='1')
    crypt = subprocess.Popen([str(AGE), '-d', '-i', '/home/brajam/.ssh/id_ed25519'], stdin=sys.stdin.buffer, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
    seen = set()
    rows = {r['archiveName']: r for r in profile['files']}
    try:
        with tarfile.open(fileobj=crypt.stdout, mode='r|', encoding='utf8', errors='surrogateescape') as archive:
            for member in archive:
                need(member.isfile() and member.name not in seen and len(seen) <= 32, 'archive_member_type_or_duplicate')
                seen.add(member.name)
                inp = archive.extractfile(member)
                if member.name == 'manifest.json':
                    need(len(seen) == 1 and member.size == len(canonical(profile)) and inp.read() == canonical(profile), 'exact_archive_manifest')
                    continue
                need(member.name in rows, 'unexpected_archive_member')
                row = rows[member.name]
                s = row['identity']
                need(member.size == s['size'] and member.uid == s['uid'] and member.gid == s['gid'] and member.mode == stat.S_IMODE(s['mode']), 'archive_numeric_metadata')
                need(int(decimal.Decimal(member.pax_headers['mtime']) * 10**9) == s['mtime_ns'], 'archive_mtime_precision')
                recovered_attrs = {k[len('SCHILY.xattr.'):]: base64.b64encode(v.encode('utf8', 'surrogateescape')).decode() for k, v in member.pax_headers.items() if k.startswith('SCHILY.xattr.')}
                need(recovered_attrs == row['xattrs'], 'archive_xattrs')
                need(not target.exists() and os.statvfs(F).f_bavail * os.statvfs(F).f_frsize >= FLOOR + s['size'] + 128 * 1024**2, 'one_file_restore_floor')
                with target.open('xb') as out:
                    count = 0
                    for block in iter(lambda: inp.read(1024**2), b''):
                        count += len(block)
                        need(count <= s['size'], 'restored_byte_bound')
                        out.write(block)
                    out.flush()
                    os.fsync(out.fileno())
                    os.fchown(out.fileno(), s['uid'], s['gid'])
                    os.fchmod(out.fileno(), stat.S_IMODE(s['mode']))
                for name, value in row['xattrs'].items():
                    os.setxattr(target, name, base64.b64decode(value))
                os.utime(target, ns=(s['mtime_ns'], s['mtime_ns']))
                restored = target.stat()
                need(count == s['size'] and sha(target) == row['sha256'] and xattrs(target) == row['xattrs'], 'restored_full_data_and_xattrs')
                need((restored.st_uid, restored.st_gid, stat.S_IMODE(restored.st_mode), restored.st_mtime_ns) == (s['uid'], s['gid'], stat.S_IMODE(s['mode']), s['mtime_ns']), 'restored_ownership_permissions_mtime')
                check = subprocess.run(['journalctl', '--verify', '--quiet', '--file', str(target)], capture_output=True, timeout=60)
                need(check.returncode == 0, 'restored_journal_structure')
                before = ident(target.lstat())
                common['idle']()
                need(ident(target.lstat()) == before and before['nlink'] == 1, 'inactive_restored_file_identity')
                target.unlink()
                result['scratchRemovedAllocatedBytes'] += before['blocks'] * 512
                result['restoredFiles'].append({'archiveName': member.name, 'bytes': count, 'sha256': row['sha256'], 'numericMetadataVerified': True, 'xattrsVerified': True, 'journalStructureVerified': True})
        need(seen == set(rows) | {'manifest.json'}, 'complete_member_set')
        trailing = crypt.stdout.read(1024**2 + 1)
        need(len(trailing) <= 1024**2 and not any(trailing) and crypt.wait(timeout=60) == 0, 'complete_age_authentication')
        common['idle']()
        need(not any(work.iterdir()), 'empty_restore_scratch')
        result['scratchRemovedAllocatedBytes'] += work.stat().st_blocks * 512
        work.rmdir()
        result.update(status='completed', completeAgeAuthentication=True, everyFileIndependentlyRestored=True, scratchReconciled=True)
    except Exception as error:
        result.update(status='failed', errorCategory=str(error) if isinstance(error, ValueError) else type(error).__name__, retainedScratch=str(work), retentionReason='restore or safety qualification incomplete')
        raise
    finally:
        if crypt.poll() is None:
            crypt.terminate()
            crypt.wait(timeout=30)
        with receipt.open('x') as out:
            json.dump(result, out, indent=2)
            out.write('\n')
        os.chown(receipt, 1000, 1000)
        print(json.dumps({k: v for k, v in result.items() if k != 'restoredFiles'}))


def retire(a, profile):
    fs = node_scope(profile_node(profile))
    need(a.node == profile_node(profile), 'selected_profile_node')
    proof = json.loads(base64.b64decode(a.backup_proof, validate=True))
    need(proof['schema'] == 1 and proof['nasReadLocksHeld'] and proof['independentRestoreVerified'], 'live_verified_archive_guard')
    need(0 <= time.time() - proof['nasVerificationEpoch'] < 1200, 'fresh_nas_guard')
    need(proof['journalCanonicalProfileSHA256'] == hashlib.sha256(canonical(profile)).hexdigest(), 'restored_profile_identity')
    backup = proof['journalBackup']
    need(len(proof['files']) == 1 and proof['files'][0]['nasSHA256'] == backup['archiveSHA256'] and proof['files'][0]['nasBytes'] == backup['archiveBytes'], 'locked_archive_identity')
    need(backup['status'] == 'completed' and backup['completeNASReadbackAuthenticated'] and backup['everyJournalIndependentlyRestored'], 'qualified_recovery_required')
    need(backup['restoredFiles'] == len(profile['files']) and backup['restoreReceiptSHA256'], 'all_journals_restored')
    need(not any((d / '.git').exists() or (d / '.git').is_symlink() for d in [ROOT, *ROOT.parents]), 'git_source_tree_refused')
    common = checker(a, ROOT, tuple(r['relative'] for r in profile['files']))
    refs = common['idle']()
    for row in profile['files']:
        p = Path(row['path'])
        need(p.resolve() == p and p.is_relative_to(ROOT) and '@' in p.name and p.name.endswith('.journal'), 'closed_journal_scope')
        need(ident(p.lstat()) == row['identity'] and p.stat().st_nlink == 1, 'original_journal_identity')
        need(time.time_ns() - max(p.stat().st_mtime_ns, p.stat().st_ctime_ns) >= 72 * 3600 * 10**9, 'retention_age')
        need(sha(p) == row['sha256'] and xattrs(p) == row['xattrs'] and ident(p.lstat()) == row['identity'], 'original_journal_full_data')
    common['idle']()
    before = os.statvfs('/')
    result = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'filesystem': fs, 'references': refs,
              'applied': a.apply, 'removed': [], 'removedAllocatedBytes': 0, 'activeJournalRemoved': False,
              'sourceProfileSHA256': hashlib.sha256(canonical(profile)).hexdigest(), 'archiveSHA256': backup['archiveSHA256']}
    try:
        if a.apply:
            for row in profile['files']:
                p = Path(row['path'])
                need(ident(p.lstat()) == row['identity'], 'final_journal_identity')
                fd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    need(ident(os.stat(p.name, dir_fd=fd, follow_symlinks=False)) == row['identity'], 'opened_journal_identity')
                    os.unlink(p.name, dir_fd=fd)
                finally:
                    os.close(fd)
                result['removed'].append({'path': str(p), 'sha256': row['sha256'], 'allocatedBytes': row['identity']['blocks'] * 512})
                result['removedAllocatedBytes'] += row['identity']['blocks'] * 512
    finally:
        after = os.statvfs('/')
        result.update(availableBeforeBytes=before.f_bavail * before.f_frsize, availableAfterBytes=after.f_bavail * after.f_frsize)
        print(json.dumps(result))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['inventory', 'stream', 'encrypt', 'verify', 'retire'], required=True)
    p.add_argument('--node', choices=sorted(NODES), default='workernode2')
    p.add_argument('--selection-base64')
    p.add_argument('--profile-base64')
    p.add_argument('--profile', type=Path)
    p.add_argument('--safety-source', default='')
    p.add_argument('--safety-sha256', default='')
    p.add_argument('--backup-proof')
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    os.setpriority(os.PRIO_PROCESS, 0, 15)
    if a.mode == 'inventory':
        inventory(a)
        return
    profile = json.loads(base64.b64decode(a.profile_base64)) if a.profile_base64 else json.loads(a.profile.read_text())
    need(profile['schema'] == 1 and len(profile['files']) <= 32 and profile['fileBytes'] <= 3 * 1024**3, 'bounded_profile')
    if a.mode == 'stream':
        stream(profile)
    elif a.mode == 'encrypt':
        encrypt(a, profile)
    elif a.mode == 'retire':
        retire(a, profile)
    else:
        verify(a, profile)


if __name__ == '__main__':
    main()
