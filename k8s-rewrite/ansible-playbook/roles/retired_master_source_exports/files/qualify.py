"""Qualify generated source exports against preserved originals and exact deltas.

Default is read-only. Explicit retirement requires the complete original
qualification and repeats every archive, identity and reference check.
Original archives and all unmatched/unique files survive.
"""
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import socket
import subprocess
import sys
import time
import zipfile

OPERATION_RESULT = None


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(stream):
    h = hashlib.sha256()
    for b in iter(lambda: stream.read(1024**2), b''):
        h.update(b)
    return h.hexdigest()


def sha(path):
    with path.open('rb') as f:
        return digest(f)


def main():
    global OPERATION_RESULT
    request = json.load(sys.stdin)
    base = Path('/home/james/.local/share/branconet-migration')
    need(os.geteuid() == 0 and socket.gethostname() == 'masternode', 'exact_master_full_root_reference_visibility')
    filesystem = json.loads(subprocess.check_output(['findmnt', '-J', '-T', str(base), '-o', 'UUID,FSTYPE'], timeout=30))['filesystems'][0]
    need(filesystem['uuid'] == '763cda3d-0777-4b03-a882-9d21060466e3' and filesystem['fstype'] == 'ext4', 'original_master_filesystem')
    raw = base64.b64decode(request['guardSource'], validate=True)
    need(hashlib.sha256(raw).hexdigest() == '3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87', 'original_guard')
    guard = {'__name__': 'source_export_reference_guard'}
    exec(compile(raw, '<original-reference-guard>', 'exec'), guard)
    attempts = ('root-custom-kubectl-build-20261012-b5d6d1/kubectl-security-a4cc69125f81',
                'root-custom-kubectl-build-20261012-f73dc0/kubectl-security-53c90b1e408a')
    guard.update(BASE=base, ATTEMPTS=attempts)
    refs = guard['idle']()
    bindings = request['archiveBindings']['sources']
    for name, value in bindings.items():
        need(sha(base / name) == value['sha256'], 'original_preexisting_preservation_archive_unchanged')
    out = []
    for attempt in attempts:
        root = base / attempt
        tree = root / 'kubernetes'
        need(tree.resolve() == tree and not tree.is_mount() and not (tree / '.git').exists(), 'generated_nonrepository_export')
        with zipfile.ZipFile(root / 'source-original.zip') as original, zipfile.ZipFile(root / 'source-diff.zip') as difference:
            for z in (original, difference):
                names = z.namelist()
                need(len(names) == len(set(names)) < 100000, 'unique_bounded_archive_members')
                need(all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in names), 'safe_relative_archive_members')
            before = json.loads(original.read('source-inventory.json'))
            diff = json.loads(difference.read('diff.json'))
            expected = dict(before)
            for name, versions in diff.items():
                if versions['after'] is None:
                    expected.pop(name, None)
                else:
                    expected[name] = versions['after']
            authenticated = {}
            for name, contract in expected.items():
                need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'relative_source_contract')
                if 'link' in contract:
                    authenticated[name] = contract
                    continue
                need(set(('sha256', 'bytes', 'mode')).issubset(contract), 'complete_original_file_contract')
                z, member = (difference, 'after/' + name) if name in diff else (original, name)
                info = z.getinfo(member)
                need(info.file_size == contract['bytes'], 'full_archived_member_size')
                with z.open(info) as f:
                    need(digest(f) == contract['sha256'], 'full_archived_member_hash')
                authenticated[name] = contract
            rows = []
            for parent, dirs, files in os.walk(tree, followlinks=False):
                parent = Path(parent)
                need('.git' not in dirs and not ((parent / 'HEAD').exists() and (parent / 'objects').is_dir()), 'nested_repository_refused')
                paths = [parent, *[parent / n for n in files]]
                for name in list(dirs):
                    if (parent / name).is_symlink():
                        dirs.remove(name)
                        paths.append(parent / name)
                for p in paths:
                    s = p.lstat()
                    name = str(p.relative_to(tree))
                    c = authenticated.get(name)
                    row = {'relative': str(p.relative_to(base)), 'allocatedBytes': s.st_blocks * 512,
                           'identity': {k: getattr(s, 'st_' + k) for k in ['dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks']},
                           'eligible': False}
                    need(p.parent.resolve() == p.parent and s.st_dev == tree.stat().st_dev, 'exact_source_export_filesystem')
                    if stat.S_ISREG(s.st_mode):
                        row['sha256'] = sha(p)
                        row['eligible'] = bool(c and c.get('sha256') == row['sha256'] and c.get('bytes') == s.st_size
                                               and c.get('mode') == stat.S_IMODE(s.st_mode) and s.st_nlink == 1)
                    elif stat.S_ISLNK(s.st_mode):
                        row['link'] = os.readlink(p)
                        row['eligible'] = bool(c and c.get('link') == row['link'] and s.st_nlink == 1)
                    elif stat.S_ISDIR(s.st_mode):
                        row['directory'] = True
                    else:
                        row['reason'] = 'unsupported type retained'
                    if os.listxattr(p, follow_symlinks=False):
                        row.update(eligible=False, reason='extended attributes not represented by preserved source contract')
                    if s.st_uid not in (0, 1000) or time.time_ns() - max(s.st_ctime_ns, s.st_mtime_ns) < 72 * 3600 * 10**9:
                        row.update(eligible=False, reason='owner or older-copy inactivity requirement failed')
                    if not row['eligible'] and not row.get('directory'):
                        row.setdefault('reason', 'not fully represented by preserved original source and exact delta')
                    current = p.lstat()
                    need(all(getattr(current, 'st_' + k) == v for k, v in row['identity'].items()), 'source_export_unchanged_during_hash')
                    rows.append(row)
            out.append({'attempt': attempt, 'archivedSourceMembersVerified': len(authenticated),
                        'rows': rows, 'eligibleAllocatedBytes': sum(x['allocatedBytes'] for x in rows if x['eligible']),
                        'regeneration': 'Preserved source-original.zip and source-inventory.json, overlaid by source-diff.zip/diff.json after entries; preserve modes and link targets; verify every original contract. Never replay the old build.'})
    guard['idle']()
    need(all(sha(base / n) == v['sha256'] for n, v in bindings.items()), 'original_archives_unchanged_after_inspection')
    result = {'status': 'read_only_qualified', 'clusterChanged': False, 'deleted': [],
              'references': refs, 'archives': bindings, 'exports': out}
    if request.get('mode') == 'retire':
        original = request['qualification']
        need(original['status'] == 'read_only_qualified' and original['archives'] == bindings
             and original['exports'] == out, 'complete_original_qualification_unchanged')
        guard['idle']()
        before_space = os.statvfs(base)
        OPERATION_RESULT = result
        retained = [r for e in out for r in e['rows'] if not r['eligible'] and not r.get('directory')]
        # The original independent qualification remains on the controller,
        # including all source hashes, modes, directory identities and links.
        for export in out:
            for row in export['rows']:
                if not row['eligible']:
                    continue
                p = base / row['relative']
                need(p.parent.resolve() == p.parent and p.is_relative_to(base), 'canonical_qualified_file')
                fd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    current = os.stat(p.name, dir_fd=fd, follow_symlinks=False)
                    need(all(getattr(current, 'st_' + k) == v for k, v in row['identity'].items()), 'final_exact_file_identity')
                    os.unlink(p.name, dir_fd=fd)
                finally:
                    os.close(fd)
                result['deleted'].append({'path': str(p), 'allocatedBytes': row['allocatedBytes']})
            dirs = sorted([r for r in export['rows'] if r.get('directory')], key=lambda r: len(Path(r['relative']).parts), reverse=True)
            for row in dirs:
                p = base / row['relative']
                need(p.resolve() == p and not p.is_mount(), 'canonical_original_directory')
                current = p.lstat()
                need(all(getattr(current, 'st_' + k) == row['identity'][k] for k in ['dev', 'ino', 'mode', 'uid', 'gid']), 'original_directory_identity')
                if any(p.iterdir()):
                    continue
                amount = current.st_blocks * 512
                p.rmdir()
                result['deleted'].append({'path': str(p), 'allocatedBytes': amount, 'directory': True})
        for row in retained:
            p = base / row['relative']
            s = p.lstat()
            need(all(getattr(s, 'st_' + k) == v for k, v in row['identity'].items()), 'all_unqualified_files_preserved')
            need(not row.get('link') or os.readlink(p) == row['link'], 'unique_original_link_preserved')
            need(not row.get('sha256') or sha(p) == row['sha256'], 'unique_original_file_preserved')
        need(all(sha(base / n) == v['sha256'] for n, v in bindings.items()), 'original_source_archives_and_records_survive_retirement')
        after_space = os.statvfs(base)
        result.update(status='qualified_generated_source_exports_retired', clusterChanged=True,
                      removedAllocatedLinuxBytes=sum(x['allocatedBytes'] for x in result['deleted']),
                      beforeBavail=before_space.f_bavail * before_space.f_frsize,
                      afterBavail=after_space.f_bavail * after_space.f_frsize,
                      retained=retained, WindowsRecoveryClaimed=False,
                      UTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
        # Do not duplicate the original complete source inventory in this receipt.
        result.pop('exports')
    else:
        need(request.get('mode', 'inventory') == 'inventory', 'explicit_known_operation')
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        if OPERATION_RESULT is not None:
            OPERATION_RESULT.update(status='failed_preserve_remaining_exports', errorType=type(error).__name__)
            OPERATION_RESULT.pop('exports', None)
            print(json.dumps(OPERATION_RESULT))
        raise
