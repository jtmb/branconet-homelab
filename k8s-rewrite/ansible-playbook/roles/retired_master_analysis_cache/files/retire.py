"""Retire one inactive generated Trivy analysis cache; preserve every other file."""
import base64
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys

BASE = Path('/home/james/.local/share/branconet-migration')
AUDIT = 'audit20261023-20261023T203418Z'
ROOT = BASE / AUDIT
CACHE = ROOT / 'cache/fanal/fanal.db'
RESULT = None


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def ident(p):
    s = p.lstat()
    return {k: getattr(s, 'st_' + k) for k in ['dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks']}


def sha(p):
    before = ident(p)
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024**2), b''):
            h.update(b)
    need(ident(p) == before, 'file_stable_during_full_hash')
    return h.hexdigest()


def protected():
    out = {}
    for p in ROOT.rglob('*'):
        if p == CACHE:
            continue
        if p.is_symlink():
            out[str(p.relative_to(ROOT))] = {'identity': ident(p), 'link': os.readlink(p)}
        elif p.is_file():
            out[str(p.relative_to(ROOT))] = {'identity': ident(p), 'sha256': sha(p)}
    return out


def main():
    global RESULT
    r = json.load(sys.stdin)
    need(os.geteuid() == 0 and socket.gethostname() == 'masternode', 'original_master_root')
    fs = json.loads(subprocess.check_output(['findmnt', '-J', '-T', str(ROOT), '-o', 'UUID,FSTYPE'], timeout=30))['filesystems'][0]
    need(fs['uuid'] == '763cda3d-0777-4b03-a882-9d21060466e3' and fs['fstype'] == 'ext4', 'original_master_filesystem')
    need(CACHE.resolve() == CACHE and CACHE.is_file() and not any((p / '.git').exists() for p in CACHE.parents), 'exact_nonrepository_cache')
    raw = base64.b64decode(r['guardSource'], validate=True)
    need(hashlib.sha256(raw).hexdigest() == '3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87', 'unchanged_complete_reference_guard')
    guard = {'__name__': 'inactive_analysis_cache_guard'}
    exec(compile(raw, '<original-reference-guard>', 'exec'), guard)
    guard.update(BASE=BASE, ATTEMPTS=(AUDIT,))
    refs = guard['idle']()
    source = (ROOT / 'run-remote-image-audit.py').read_text()
    need("'--cache-dir',str(ROOT/'cache')" in source and "'image'" in source
         and 'Version: 0.76.1' in (ROOT / 'tool-versions.txt').read_text(), 'actual_recorded_trivy_cache_producer')
    need((ROOT / 'live-inventory.json').is_file() and (ROOT / 'tool-provenance.json').is_file()
         and (ROOT / 'reports').is_dir(), 'original_regeneration_inputs_and_reports')
    original = ident(CACHE)
    need(stat.S_ISREG(original['mode']) and original['uid'] == 1000 and original['nlink'] == 1
         and not os.listxattr(CACHE), 'original_single_link_generated_cache')
    fd = os.open(CACHE, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        snapshot = {'path': str(CACHE), 'identity': original, 'sha256': sha(CACHE),
                    'protected': protected(), 'filesystem': fs,
                    'regeneration': 'Use pinned Trivy 0.76.1 from tool-provenance.json with the preserved run-remote-image-audit.py image --cache-dir configuration and exact image digests in live-inventory.json. Recompute package analysis from the preserved/public image sources. Do not replay deployment or credential changes.',
                    'requiredRuntimeConsumer': None, 'originalReportsAndSourceRetained': True}
        guard['idle']()
        result = {'status': 'qualified_inactive_generated_analysis_cache', 'profile': snapshot,
                  'references': refs, 'removed': [], 'applicationDataChanged': False, 'imagesPruned': False}
        if r['mode'] == 'retire':
            need(snapshot == r['qualification']['profile'], 'complete_original_qualification_unchanged')
            RESULT = result
            need(ident(CACHE) == original, 'final_cache_identity')
            parentfd = os.open(CACHE.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                s = os.stat(CACHE.name, dir_fd=parentfd, follow_symlinks=False)
                need(all(getattr(s, 'st_' + k) == v for k, v in original.items()), 'opened_parent_exact_inode')
                os.unlink(CACHE.name, dir_fd=parentfd)
                os.fsync(parentfd)
            finally:
                os.close(parentfd)
            result['removed'].append({'path': str(CACHE), 'allocatedBytes': original['blocks'] * 512})
            for relative in ['cache/fanal', 'cache/db', 'cache/java-db', 'cache']:
                p = ROOT / relative
                if p.exists() and p.is_dir() and p.resolve() == p and not p.is_mount() and not any(p.iterdir()):
                    s = p.lstat()
                    need(s.st_uid in (0, 1000) and s.st_dev == original['dev'], 'owned_empty_cache_directory')
                    p.rmdir()
                    result['removed'].append({'path': str(p), 'allocatedBytes': s.st_blocks * 512, 'directory': True})
            need(protected() == snapshot['protected'], 'every_original_source_report_input_and_other_file_unchanged')
            result.update(status='inactive_generated_analysis_cache_retired',
                          removedAllocatedLinuxBytes=sum(x['allocatedBytes'] for x in result['removed']),
                          WindowsRecoveryClaimed=False, UTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
            result.pop('profile')
        else:
            need(r['mode'] == 'inventory', 'known_explicit_mode')
        print(json.dumps(result))
    finally:
        os.close(fd)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        if RESULT is not None:
            RESULT.update(status='failed_preserve_remaining', errorType=type(e).__name__)
            RESULT.pop('profile', None)
            print(json.dumps(RESULT))
        raise
