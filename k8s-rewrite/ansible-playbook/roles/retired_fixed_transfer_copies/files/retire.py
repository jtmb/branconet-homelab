"""Remove three fixed redundant transfer files; preserve exact original primaries."""
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
import time

BASE = Path('/home/james/.local/share/branconet-migration')
FAILED = 'root-custom-kubectl-build-20261012-b5d6d1/kubectl-security-a4cc69125f81/'
INPUTS = 'root-kubectl-inputs-20261012-c3927a/'
AUDIT = 'bortus-cached-runtime-audit-20261025/attempts/3da0b68becea/'
PROFILES = {
    'masternode': ('763cda3d-0777-4b03-a882-9d21060466e3', [
        (INPUTS + 'go1.26.9.linux-amd64.tar.gz', FAILED + 'go1.26.9.tar.gz',
         '42d158b4d8f7b61ac0a830567c940a86098fb7aac52e467a5ebec03ef5cc2f8d', 66935201),
        (INPUTS + 'kubernetes-src.tar.gz', FAILED + 'kubernetes-src.tar.gz',
         'd58492a058ac7cb1db0829a9e12317024f48d4bcbf56344b32b11276f9bdc2cf', 42196261)]),
    'workernode2': ('960bc2c7-2a7e-4bc2-b2c5-dbb6d71207f4', [
        (AUDIT + 'runtime.oci.tar', None,
         'fa7df63ec2a22c2eedff17a16e5d1e7b555d6b93802b5c470aafdccad90731d4', 1149327360)])}
RESULT = None


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def ident(p):
    s = p.lstat()
    return {k: getattr(s, 'st_' + k) for k in
            ['dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks']}


def sha(p):
    before = ident(p)
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024**2), b''):
            h.update(b)
    need(ident(p) == before, 'stable_full_file_hash')
    return h.hexdigest()


def main():
    global RESULT
    request = json.load(sys.stdin)
    name = socket.gethostname()
    need(os.geteuid() == 0 and name in PROFILES and name == request['hostname'], 'exact_original_node_root')
    uuid, files = PROFILES[name]
    fs = json.loads(subprocess.check_output(['findmnt', '-J', '-T', str(BASE), '-o', 'UUID,FSTYPE'], timeout=30))['filesystems'][0]
    need(fs['uuid'] == uuid and fs['fstype'] == 'ext4', 'original_node_filesystem')
    raw = base64.b64decode(request['guardSource'], validate=True)
    need(hashlib.sha256(raw).hexdigest() == '3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87', 'original_complete_reference_guard')
    guard = {'__name__': 'fixed_transfer_reference_guard'}
    exec(compile(raw, '<original-reference-guard>', 'exec'), guard)
    guard.update(BASE=BASE, ATTEMPTS=tuple(sorted({str(Path(x[0]).parent) for x in files})))
    refs = guard['idle']()
    rows, primaries = [], {}
    for relative, primary, expected, size in files:
        p = BASE / relative
        need(p.resolve() == p and p.is_file() and not any((x / '.git').exists() for x in p.parents), 'exact_nonrepository_duplicate')
        s = ident(p)
        need(s['dev'] == BASE.stat().st_dev and s['uid'] in (0, 1000) and s['nlink'] == 1
             and stat.S_ISREG(s['mode']) and s['size'] == size and not os.listxattr(p), 'original_single_link_transfer')
        if name == 'masternode':
            need(time.time_ns() - max(s['mtime_ns'], s['ctime_ns']) >= 72 * 3600 * 10**9, 'older_copy_inactivity')
        need(sha(p) == expected, 'full_original_transfer_hash')
        if primary:
            q = BASE / primary
            need(q.resolve() == q and q.is_file() and sha(q) == expected and q.stat().st_size == size, 'exact_retained_original_primary')
            primaries[str(q)] = {'identity': ident(q), 'sha256': expected}
        else:
            proof = request['controllerArchiveProof']
            need(proof['fullHashVerified'] and proof['sha256'] == expected and proof['bytes'] == size
                 and proof['originalExportAndTransferCompleted'], 'retained_exact_controller_archive')
        rows.append({'path': str(p), 'identity': s, 'sha256': expected, 'allocatedBytes': s['blocks'] * 512,
                     'parentIdentity': ident(p.parent),
                     'primary': str(BASE / primary) if primary else request['controllerArchiveProof']['path']})
    guard['idle']()
    result = {'status': 'qualified', 'node': name, 'filesystem': fs, 'references': refs,
              'targets': rows, 'primaries': primaries, 'removed': [], 'imagesPruned': False,
              'volumesChanged': False, 'regeneration': 'Copy the exact retained original primary to its original transfer path and verify the recorded SHA256.'}
    if request['mode'] == 'retire':
        need(request['qualification']['targets'] == rows and request['qualification']['primaries'] == primaries,
             'complete_original_qualification_unchanged')
        RESULT = result
        before = os.statvfs(BASE)
        for row in rows:
            p = Path(row['path'])
            fd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                s = os.stat(p.name, dir_fd=fd, follow_symlinks=False)
                need(all(getattr(s, 'st_' + k) == v for k, v in row['identity'].items()), 'final_original_file_identity')
                os.unlink(p.name, dir_fd=fd)
                os.fsync(fd)
            finally:
                os.close(fd)
            result['removed'].append({'path': str(p), 'allocatedBytes': row['allocatedBytes']})
        for parent in sorted({str(Path(r['path']).parent) for r in rows}):
            p = Path(parent)
            original = next(r['parentIdentity'] for r in rows if str(Path(r['path']).parent) == parent)
            current = ident(p)
            need(p.resolve() == p and not p.is_mount() and all(current[k] == original[k]
                 for k in ['dev', 'ino', 'mode', 'uid', 'gid']), 'original_parent_directory')
            if not any(p.iterdir()):
                amount = current['blocks'] * 512
                p.rmdir()
                result['removed'].append({'path': str(p), 'allocatedBytes': amount, 'directory': True})
        need(all(ident(Path(p)) == v['identity'] and sha(Path(p)) == v['sha256'] for p, v in primaries.items()), 'all_original_primaries_preserved')
        after = os.statvfs(BASE)
        result.update(status='retired_exact_transfer_duplicates',
                      removedAllocatedLinuxBytes=sum(x['allocatedBytes'] for x in result['removed']),
                      beforeBavail=before.f_bavail * before.f_frsize, afterBavail=after.f_bavail * after.f_frsize,
                      WindowsRecoveryClaimed=False, UTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
    else:
        need(request['mode'] == 'inventory', 'known_explicit_mode')
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        if RESULT is not None:
            RESULT.update(status='failed_preserve_remaining', errorType=type(e).__name__)
            print(json.dumps(RESULT))
        raise
