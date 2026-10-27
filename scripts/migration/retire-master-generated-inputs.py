"""Qualify and retire only four exact old master SDK/module-cache copies."""
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tarfile
import time
import zipfile

BASE = Path('/home/james/.local/share/branconet-migration')
ATTEMPTS = ('root-custom-kubectl-build-20261012-b5d6d1/kubectl-security-a4cc69125f81',
            'root-custom-kubectl-build-20261012-f73dc0/kubectl-security-53c90b1e408a')
RELATIVES = ('go', 'kubernetes/_output/local/go/cache/mod')
ROOTS = tuple(a + '/' + r for a in ATTEMPTS for r in RELATIVES)
UUID = '763cda3d-0777-4b03-a882-9d21060466e3'
GO_SHA = '42d158b4d8f7b61ac0a830567c940a86098fb7aac52e467a5ebec03ef5cc2f8d'


def need(value, reason):
    if not value:
        raise ValueError(reason)


def identity(path):
    s = path.lstat()
    return {k: getattr(s, 'st_' + k) for k in ('dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks')}


def hash_stream(source):
    h = hashlib.sha256()
    for block in iter(lambda: source.read(1024**2), b''):
        h.update(block)
    return h.hexdigest()


def sha(path):
    before = identity(path)
    need(stat.S_ISREG(before['mode']), 'regular_hash_input')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as source:
        actual = os.fstat(source.fileno())
        need((actual.st_dev, actual.st_ino) == (before['dev'], before['ino']), 'opened_hash_input_identity')
        value = hash_stream(source)
    need(identity(path) == before, 'file_changed_during_hash')
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def safety(request):
    raw = base64.b64decode(request['safetySource'], validate=True)
    need(hashlib.sha256(raw).hexdigest() == request['safetySHA256'] ==
         '3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87', 'reviewed_reference_source')
    library = {'__name__': 'master_reference_checks'}
    exec(compile(raw, '<reviewed-reference-checks>', 'exec'), library)
    library.update(BASE=BASE, ATTEMPTS=ATTEMPTS)
    return library


def scope():
    need(os.geteuid() == 0 and socket.gethostname() == 'masternode', 'original_master_root_required')
    fs = json.loads(subprocess.check_output(['findmnt', '-J', '-T', str(BASE), '-o', 'UUID,FSTYPE'], timeout=30))['filesystems'][0]
    need(fs['uuid'] == UUID and fs['fstype'] == 'ext4', 'original_master_filesystem')
    for rel in ROOTS:
        p = BASE / rel
        need(p.resolve() == p and p.is_dir(), 'exact_existing_selected_root')
        need(not any((parent / '.git').exists() for parent in (p, *p.parents)), 'git_ancestor_refused')
    return fs


def protected():
    """Hash every other file; directory structural timestamps can change only
    on ancestors of the exact selected roots during their eventual removal.
    """
    values = {}
    ancestors = {str(parent) for rel in ROOTS for parent in (BASE / rel).parents}
    for attempt in ATTEMPTS:
        root = BASE / attempt
        for parent, dirs, files in os.walk(root, followlinks=False):
            parent = Path(parent)
            dirs[:] = sorted(d for d in dirs if str((parent / d).relative_to(BASE)) not in ROOTS)
            for path in [parent, *[parent / name for name in sorted(files)],
                         *[parent / name for name in dirs if (parent / name).is_symlink()]]:
                info = identity(path)
                need(info['dev'] == BASE.stat().st_dev, 'protected_source_filesystem')
                if stat.S_ISDIR(info['mode']):
                    if str(path) in ancestors:
                        info = {k: info[k] for k in ('dev', 'ino', 'mode', 'uid', 'gid')}
                    value = {'identity': info}
                elif stat.S_ISREG(info['mode']):
                    value = {'identity': info, 'sha256': sha(path)}
                elif stat.S_ISLNK(info['mode']):
                    value = {'identity': info, 'linkTarget': os.readlink(path)}
                else:
                    raise ValueError('unknown_protected_source_type')
                values[str(path.relative_to(BASE))] = value
        # Original failed supervisor/helper/terminal records remain outside
        # the inner run directory and are separately bound here.
        for name in ('helper.py', 'supervisor.py', 'record.json', 'terminal.json'):
            path = root.parent / name
            need(path.is_file() and not path.is_symlink(), 'original_parent_source_records')
            values[str(path.relative_to(BASE))] = {'identity': identity(path), 'sha256': sha(path)}
    return values


def archive_members(root, relative, record):
    if relative == 'go':
        path = root / 'go1.26.9.tar.gz'
        need(record['go_archive_sha256'] == GO_SHA and sha(path) == GO_SHA, 'retained_pinned_sdk_archive')
        expected = {}
        with tarfile.open(path, mode='r:gz') as archive:
            for member in archive:
                need(member.name == 'go' or member.name.startswith('go/'), 'original_sdk_member_prefix')
                name = member.name[3:] if member.name.startswith('go/') else ''
                if member.isfile():
                    expected[name] = {'kind': 'file', 'sha256': hash_stream(archive.extractfile(member))}
                elif member.issym():
                    expected[name] = {'kind': 'symlink', 'linkTarget': member.linkname}
                else:
                    need(member.isdir(), 'sdk_archive_regular_directory_or_link')
        return expected, {'path': str(path), 'sha256': GO_SHA, 'originalRecordHashPresent': True}
    path = root / 'source-diff.zip'
    before = sha(path)
    recorded = record.get('source_diff_sha256')
    need(recorded is None or recorded == before, 'recorded_source_difference_archive')
    prefix = 'after/_output/local/go/cache/mod/'
    expected, contracts = {}, []
    with zipfile.ZipFile(path) as archive:
        names = [m for m in archive.infolist() if m.filename.startswith(prefix) and not m.is_dir()]
        need(0 < len(names) <= 100000 and len({m.filename for m in names}) == len(names), 'bounded_unique_archived_cache_members')
        for member in names:
            name = member.filename[len(prefix):]
            need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'archived_cache_relative_name')
            with archive.open(member) as source:
                expected[name] = {'kind': 'file', 'sha256': hash_stream(source)}
            if '/@v/' in name and name.endswith(('.info', '.mod', '.ziphash')):
                contract = {'member': name, 'sha256': expected[name]['sha256']}
                if name.endswith(('.info', '.ziphash')):
                    need(member.file_size <= 16384, 'bounded_module_version_checksum_contract')
                    value = archive.read(member).decode()
                    if name.endswith('.info'):
                        contract['versionInformation'] = json.loads(value)
                        need(isinstance(contract['versionInformation'].get('Version'), str), 'actual_module_version')
                    else:
                        need(value.strip().startswith('h1:'), 'actual_module_checksum')
                        contract['moduleChecksum'] = value.strip()
                contracts.append(contract)
    need(contracts and any('moduleChecksum' in c for c in contracts), 'retained_module_contracts')
    need(sha(path) == before, 'archive_unchanged_during_full_member_read')
    return expected, {'path': str(path), 'sha256': before, 'originalRecordHashPresent': recorded is not None,
                      'missingOriginalRecordHashIsNotHistoricalAuthentication': recorded is None,
                      'moduleContracts': contracts}


def snapshot():
    rows, provenance = [], []
    for attempt in ATTEMPTS:
        root = BASE / attempt
        record = json.loads((root / 'record.json').read_text())
        need(record['source_tag'] == 'v1.37.1' and record['toolchain'] == 'go1.26.9', 'original_build_generation')
        for relative in RELATIVES:
            selected = root / relative
            expected, archive = archive_members(root, relative, record)
            provenance.append({'root': str(selected.relative_to(BASE)), 'archive': archive,
                               'recordSHA256': sha(root / 'record.json'),
                               'regeneration': 'Use the preserved pinned SDK archive or exact recorded module versions/checksums in a fresh owned module cache; never replay the old build'})
            for parent, dirs, files in os.walk(selected, followlinks=False):
                parent = Path(parent)
                need('.git' not in dirs and not ((parent / 'HEAD').is_file() and (parent / 'objects').is_dir()
                     and (parent / 'config').is_file()), 'nested_git_repository_refused')
                dirs.sort()
                paths = [parent, *[parent / n for n in sorted(files)]]
                for name in list(dirs):
                    if (parent / name).is_symlink():
                        dirs.remove(name)
                        paths.append(parent / name)
                for path in paths:
                    need(len(rows) < 150000 and path.parent.resolve() == path.parent, 'bounded_canonical_selected_tree')
                    info = identity(path)
                    need(info['dev'] == BASE.stat().st_dev, 'selected_original_root_device')
                    kind = 'directory' if stat.S_ISDIR(info['mode']) else 'file' if stat.S_ISREG(info['mode']) else 'symlink' if stat.S_ISLNK(info['mode']) else 'special'
                    row = {'relative': str(path.relative_to(BASE)), 'kind': kind, 'identity': info,
                           'eligible': False, 'retentionReason': ''}
                    row['extendedAttributeNames'] = sorted(os.listxattr(path, follow_symlinks=False))
                    old = time.time_ns() - max(info['mtime_ns'], info['ctime_ns']) >= 72 * 3600 * 10**9
                    match = expected.get(str(path.relative_to(selected)))
                    if kind == 'directory':
                        row['eligible'] = old and info['uid'] in (0, 1000)
                        row['retentionReason'] = '' if row['eligible'] else 'directory retention/owner not qualified'
                    elif kind == 'file':
                        row['sha256'] = sha(path)
                        row['eligible'] = bool(old and info['nlink'] == 1 and info['uid'] in (0, 1000)
                                               and match and match['kind'] == kind and match['sha256'] == row['sha256'])
                        row['retentionReason'] = '' if row['eligible'] else 'not fully age/owner/single-link/archive qualified'
                    elif kind == 'symlink':
                        row['linkTarget'] = os.readlink(path)
                        row['eligible'] = bool(old and info['uid'] in (0, 1000) and info['nlink'] == 1
                                               and match and match['kind'] == kind and match['linkTarget'] == row['linkTarget'])
                        row['retentionReason'] = '' if row['eligible'] else 'unqualified archived link or retention'
                    else:
                        row['retentionReason'] = 'unsupported type retained'
                    if row['extendedAttributeNames']:
                        row.update(eligible=False, retentionReason='extended attributes not represented by archive retained')
                    need(identity(path) == info, 'selected_member_changed_during_inventory')
                    rows.append(row)
    return {'schema': 1, 'roots': list(ROOTS), 'rows': rows, 'provenance': provenance,
            'protected': protected()}


def selected_identities():
    values = {}
    for rel in ROOTS:
        root = BASE / rel
        for parent, dirs, files in os.walk(root, followlinks=False):
            parent = Path(parent)
            paths = [parent, *[parent / n for n in files]]
            for name in list(dirs):
                if (parent / name).is_symlink():
                    dirs.remove(name)
                    paths.append(parent / name)
            for path in paths:
                values[str(path.relative_to(BASE))] = identity(path)
    return values


def main():
    os.setpriority(os.PRIO_PROCESS, 0, 15)
    request = globals().get('_MASTER_INPUT_REQUEST') or json.load(sys.stdin)
    fs = scope()
    common = safety(request)
    refs = common['idle']()
    current = snapshot()
    common['idle']()
    need(selected_identities() == {r['relative']: r['identity'] for r in current['rows']},
         'complete_selected_tree_stable_after_inspection')
    if request['mode'] == 'inventory':
        result = dict(current, filesystem=fs, UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      referencesBefore=refs, applied=False)
        raw = json.dumps(result).encode()
        need(len(raw) <= 128 * 1024**2, 'bounded_metadata_profile')
        sys.stdout.buffer.write(raw)
        return
    need(request['mode'] == 'apply' and request['apply'] is True, 'explicit_reviewed_apply_phase')
    original = request['profile']
    need(all(current[k] == original[k] for k in ('schema', 'roots', 'rows', 'provenance', 'protected')), 'complete_qualified_profile_unchanged')
    rows = current['rows']
    result = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'applied': True,
              'filesystem': fs, 'referencesBefore': refs, 'removed': [], 'removedAllocatedBytes': 0,
              'retained': [r for r in rows if not r['eligible']]}
    try:
        for row in [r for r in rows if r['eligible'] and r['kind'] != 'directory']:
            path = BASE / row['relative']
            need(identity(path) == row['identity'] and path.parent.resolve() == path.parent, 'final_qualified_file_identity')
            fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                current_file = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
                need(all(getattr(current_file, 'st_' + k) == row['identity'][k]
                         for k in ('dev', 'ino', 'mode', 'size', 'mtime_ns', 'ctime_ns')), 'opened_parent_final_identity')
                os.unlink(path.name, dir_fd=fd)
            finally:
                os.close(fd)
            result['removed'].append({'relative': row['relative'], 'allocatedBytes': row['identity']['blocks'] * 512})
            result['removedAllocatedBytes'] += row['identity']['blocks'] * 512
        for row in sorted((r for r in rows if r['eligible'] and r['kind'] == 'directory'),
                          key=lambda r: len(Path(r['relative']).parts), reverse=True):
            path = BASE / row['relative']
            if any(path.iterdir()):
                result['retained'].append({'relative': row['relative'], 'retentionReason': 'retained descendants'})
                continue
            info = identity(path)
            need(all(info[k] == row['identity'][k] for k in ('dev', 'ino', 'mode', 'uid', 'gid'))
                 and path.resolve() == path, 'empty_original_selected_directory')
            path.rmdir()
            result['removed'].append({'relative': row['relative'], 'allocatedBytes': info['blocks'] * 512})
            result['removedAllocatedBytes'] += info['blocks'] * 512
        need(protected() == current['protected'], 'all_outside_source_lock_archive_binary_preserved')
        result['allProtectedIdentitiesAndHashesPreserved'] = True
    finally:
        space = os.statvfs(BASE)
        result['availableAfterBytes'] = space.f_bavail * space.f_frsize
        print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('master_input_retirement_refused:' + (str(error) if isinstance(error, ValueError) else type(error).__name__), file=sys.stderr)
        raise SystemExit(1)
