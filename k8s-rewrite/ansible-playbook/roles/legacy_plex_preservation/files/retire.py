"""Retire only the fixed fully recovered tree copies under a live NAS guard."""
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def main():
    os.setpriority(os.PRIO_PROCESS, 0, 15)
    request = json.load(sys.stdin)
    profile, proof = request['profile'], request['proof']
    need(profile['schema'] == 1 and profile['roots'] == ['plex2/config', 'plex2/config.old']
         and 0 < len(profile['rows']) <= 150000 and profile['fileBytes'] <= 16 * 1024**3, 'fixed_bounded_profile')
    need(proof['schema'] == 1 and proof['nasReadLocksHeld'] and proof['independentRestoreVerified']
         and 0 <= time.time() - proof['nasVerificationEpoch'] < 1200, 'fresh_locked_nas_recovery')
    digest = hashlib.sha256(canonical(profile)).hexdigest()
    backup = proof['treeBackup']
    need(proof['treeCanonicalProfileSHA256'] == digest == backup['sourceCanonicalProfileSHA256'], 'independent_profile_identity')
    need(backup['status'] == 'completed' and backup['completeNASReadbackAuthenticated']
         and backup['everyEntryIndependentlyRestored'] and backup['counts'] == profile['counts'], 'complete_all_entry_recovery')
    need(len(proof['files']) == 1 and proof['files'][0]['nasSHA256'] == backup['archiveSHA256']
         and proof['files'][0]['nasBytes'] == backup['archiveBytes'], 'exact_locked_ciphertext')
    source = base64.b64decode(request['archiveSource'], validate=True)
    need(hashlib.sha256(source).hexdigest() == request['archiveSHA256'] == backup['helperSHA256'], 'reviewed_archive_source_binding')
    library = {'__name__': 'legacy_plex_archive_primitives'}
    exec(compile(source, '<reviewed-preservation-primitives>', 'exec'), library)
    filesystem = library['scope'](True)
    base, roots = library['BASE'], library['ROOTS']
    common = library['reference_checker'](request['safetySource'], request['safetySHA256'], base, roots)
    reference_before = common['idle']()
    identity, attrs, sha, paths = (library[k] for k in ('identity', 'attrs', 'sha', 'paths'))
    expected = {row['relative']: row['identity'] for row in profile['rows']}
    need(len(expected) == len(profile['rows']) and {str(p.relative_to(base)): identity(p) for p in paths()} == expected,
         'complete_original_tree_identities')
    for row in profile['rows']:
        p = base / row['relative']
        need(p.parent.resolve() == p.parent and attrs(p) == row['xattrs'], 'canonical_original_and_extended_attributes')
        if row['kind'] == 'file':
            need(stat.S_ISREG(p.lstat().st_mode) and p.lstat().st_nlink == 1 and sha(p) == row['sha256'], 'original_full_file_hash')
            need(time.time_ns() - max(p.stat().st_mtime_ns, p.stat().st_ctime_ns) >= 72 * 3600 * 10**9, 'original_retention_age')
        elif row['kind'] == 'symlink':
            need(p.is_symlink() and os.readlink(p) == row['linkTarget'], 'original_symlink_identity')
        else:
            need(p.resolve() == p and p.is_dir(), 'original_directory_identity')
        need(identity(p) == row['identity'], 'source_changed_during_final_hashes')
    parents = [base, base / 'plex2']
    parents_before = {str(p): identity(p) for p in parents}

    def outside():
        result = {}
        for parent, dirs, files in os.walk(base, followlinks=False):
            dirs[:] = [d for d in dirs if str((Path(parent) / d).relative_to(base)) not in roots]
            for name in dirs + files:
                p = Path(parent) / name
                if p not in parents:
                    result[str(p.relative_to(base))] = identity(p)
        return result

    preserved = outside()
    need({str(p.relative_to(base)): identity(p) for p in paths()} == expected, 'final_tree_set_unchanged')
    refs = common['idle']()
    need(0 <= time.time() - proof['nasVerificationEpoch'] < 1200, 'live_nas_proof_fresh_before_retirement')
    before = os.statvfs('/')
    result = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'filesystem': filesystem,
              'applied': bool(request['apply']), 'sourceCanonicalProfileSHA256': digest,
              'archiveSHA256': backup['archiveSHA256'], 'referencesBefore': reference_before, 'referencesFinal': refs,
              'base': str(base), 'removed': [], 'removedAllocatedBytes': 0, 'sourceOutsideSelectedTreesRemoved': False}
    try:
        if request['apply']:
            for row in [r for r in profile['rows'] if r['kind'] != 'directory']:
                p = base / row['relative']
                need(p.parent.resolve() == p.parent and identity(p) == row['identity'], 'final_original_member_identity')
                fd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    current = os.stat(p.name, dir_fd=fd, follow_symlinks=False)
                    need((current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns, current.st_ctime_ns) ==
                         tuple(row['identity'][k] for k in ('dev', 'ino', 'size', 'mtime_ns', 'ctime_ns')), 'opened_parent_member_identity')
                    os.unlink(p.name, dir_fd=fd)
                finally:
                    os.close(fd)
                result['removed'].append({'relative': row['relative'], 'kind': row['kind'],
                                          'allocatedBytes': row['identity']['blocks'] * 512})
                result['removedAllocatedBytes'] += row['identity']['blocks'] * 512
            for row in sorted((r for r in profile['rows'] if r['kind'] == 'directory'),
                              key=lambda r: len(Path(r['relative']).parts), reverse=True):
                p = base / row['relative']
                s = p.lstat()
                need(p.resolve() == p and not any(p.iterdir()) and
                     (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid) ==
                     tuple(row['identity'][k] for k in ('dev', 'ino', 'mode', 'uid', 'gid')), 'exact_empty_original_directory')
                p.rmdir()
                result['removed'].append({'relative': row['relative'], 'kind': 'directory',
                                          'allocatedBytes': row['identity']['blocks'] * 512})
                result['removedAllocatedBytes'] += row['identity']['blocks'] * 512
            need(all(not (base / root).exists() for root in roots) and outside() == preserved, 'unselected_legacy_state_preserved')
            result['unselectedIdentitiesPreserved'] = True
        result['parentMetadataBefore'] = parents_before
        result['parentMetadataAfter'] = {str(p): identity(p) for p in parents}
        for p in parents:
            need(all(identity(p)[k] == parents_before[str(p)][k] for k in ('dev', 'ino', 'mode', 'uid', 'gid')), 'retained_parent_owner_mode_identity')
    finally:
        after = os.statvfs('/')
        result.update(availableBeforeBytes=before.f_bavail * before.f_frsize, availableAfterBytes=after.f_bavail * after.f_frsize)
        print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('legacy_plex_retirement_refused:' + (str(error) if isinstance(error, ValueError) else type(error).__name__), file=sys.stderr)
        raise SystemExit(1)
