"""Retire only two source copies while verified canonical NAS files are locked.

Use the Windows operator holding read-only, deny-write/delete NAS handles.
No directory, queue database, other download, mount, image or volume is removed.
"""
import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import time

BASE = Path('/mnt/plex_smb_share')
ROOT = BASE / 'downloads'
UUID = '763cda3d-0777-4b03-a882-9d21060466e3'
SIZES = {3447044670, 2192493059}


def need(ok, category):
    if not ok:
        raise ValueError(category)


def identity(s):
    return {k: getattr(s, 'st_' + k) for k in ('dev', 'ino', 'size', 'mode', 'uid', 'gid', 'nlink', 'mtime_ns', 'ctime_ns', 'blocks')}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--proof-base64', required=True)
    p.add_argument('--safety-source', required=True)
    p.add_argument('--safety-sha256', required=True)
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    need(os.geteuid() == 0 and socket.gethostname() == 'masternode', 'fixed_master_scope')
    os.setpriority(os.PRIO_PROCESS, 0, 15)
    proof = json.loads(base64.b64decode(a.proof_base64, validate=True))
    need(proof['schema'] == 1 and proof['nasReadLocksHeld'] is True and proof['copyStatus'] == 'completed', 'verified_live_nas_operator_required')
    need(0 <= time.time() - proof['nasVerificationEpoch'] < 1200, 'fresh_nas_verification')
    files = proof['files']
    need(len(files) == 2 and {x['source']['identity']['size'] for x in files} == SIZES, 'exact_two_file_scope')
    safety = base64.b64decode(a.safety_source, validate=True)
    need(hashlib.sha256(safety).hexdigest() == a.safety_sha256, 'reviewed_reference_checker')
    common = {'__name__': 'legacy_reference_checks'}
    exec(compile(safety, '<reviewed-reference-checks>', 'exec'), common)
    common.update(BASE=BASE, ATTEMPTS=('downloads',))
    fs = json.loads(common['command']('findmnt', '--json', '--target', str(ROOT), '--output', 'UUID,SOURCE,FSTYPE'))['filesystems'][0]
    need(fs['uuid'] == UUID and fs['fstype'] == 'ext4', 'original_root_filesystem_not_smb')
    need(ROOT.resolve() == ROOT and ROOT.is_dir(), 'canonical_legacy_directory')
    need(not any((d / '.git').exists() or (d / '.git').is_symlink() for d in [ROOT, *ROOT.parents]), 'tracked_source_tree_refused')
    references = common['idle']()
    parent_identity = os.stat(ROOT)
    names = {x['source']['name'] for x in files}
    def other_identities():
        found = {}
        for parent, dirs, children in os.walk(ROOT, followlinks=False):
            for name in sorted(dirs + children):
                p = Path(parent) / name
                if p.parent == ROOT and name in names:
                    continue
                found[str(p.relative_to(ROOT))] = identity(p.lstat())
                need(len(found) <= 10000, 'preserved_entry_bound')
        return found
    preserved = other_identities()
    plan = []
    for item in files:
        source = item['source']
        name = source['name']
        need(Path(name).name == name and name.endswith('.mkv'), 'media_basename_scope')
        need(item['nasSHA256'] == source['sha256'] and item['nasBytes'] == source['identity']['size'], 'nas_byte_identity')
        path = ROOT / name
        need(path.resolve() == path and identity(path.lstat()) == source['identity'], 'original_source_changed')
        s = path.lstat()
        need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_dev == parent_identity.st_dev, 'regular_single_link_source')
        need(time.time_ns() - max(s.st_mtime_ns, s.st_ctime_ns) >= 72 * 3600 * 10**9, 'original_retention')
        h = hashlib.sha256()
        with path.open('rb') as inp:
            for block in iter(lambda: inp.read(1024**2), b''):
                h.update(block)
        need(identity(path.lstat()) == source['identity'] and h.hexdigest() == source['sha256'], 'original_full_sha256_changed')
        plan.append({'path': str(path), 'identity': source['identity'], 'sha256': source['sha256'], 'canonicalNASPath': item['nasPath']})
    common['idle']()
    before = os.statvfs('/')
    result = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'filesystem': fs, 'applied': a.apply,
              'proofSHA256': hashlib.sha256(base64.b64decode(a.proof_base64)).hexdigest(), 'references': references,
              'plan': plan, 'removed': [], 'removedAllocatedBytes': 0, 'otherDownloadsOrMetubeRemoved': False}
    try:
        if a.apply:
            fd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                need((os.fstat(fd).st_dev, os.fstat(fd).st_ino) == (parent_identity.st_dev, parent_identity.st_ino), 'opened_parent_identity')
                for item in plan:
                    name = Path(item['path']).name
                    need(identity(os.stat(name, dir_fd=fd, follow_symlinks=False)) == item['identity'], 'final_source_identity')
                    os.unlink(name, dir_fd=fd)
                    result['removed'].append(item)
                    result['removedAllocatedBytes'] += item['identity']['blocks'] * 512
            finally:
                os.close(fd)
            need(all(not Path(item['path']).exists() for item in plan), 'old_copy_remains')
            need(other_identities() == preserved, 'other_legacy_data_changed')
            result['otherLegacyDataIdentitiesPreserved'] = True
    finally:
        after = os.statvfs('/')
        result.update(availableBeforeBytes=before.f_bavail * before.f_frsize, availableAfterBytes=after.f_bavail * after.f_frsize)
        print(json.dumps(result))


if __name__ == '__main__':
    main()
