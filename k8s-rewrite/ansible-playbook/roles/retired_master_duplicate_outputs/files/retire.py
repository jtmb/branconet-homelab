"""Four fixed old successful-build duplicates; preserve original bytes and failures."""
import argparse
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
import time

BASE = Path('/home/james/.local/share/branconet-migration')
GOOD = 'root-custom-kubectl-build-20261012-f73dc0'
FAILED = 'root-custom-kubectl-build-20261012-b5d6d1'
A = BASE / GOOD / 'kubectl-security-53c90b1e408a'
B = BASE / FAILED / 'kubectl-security-a4cc69125f81'
BIN_SHA = 'a3c4741294f061550b30bd2e3f357197ffbac37eefc5a45d686fe9cd29032b75'
GO_SHA = '42d158b4d8f7b61ac0a830567c940a86098fb7aac52e467a5ebec03ef5cc2f8d'
SRC_SHA = 'd58492a058ac7cb1db0829a9e12317024f48d4bcbf56344b32b11276f9bdc2cf'
TARGETS = {
    A / 'kubernetes/_output/local/go/bin/kubectl': (BIN_SHA, 61960354),
    A / 'kubernetes/_output/local/bin/linux/amd64/kubectl': (BIN_SHA, 61960354),
    A / 'go1.26.9.tar.gz': (GO_SHA, 66935201),
    A / 'kubernetes-src.tar.gz': (SRC_SHA, 42196261),
}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def ident(path):
    s = path.lstat()
    return {k: getattr(s, 'st_' + k) for k in ('dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks')}


def sha(path):
    before = ident(path)
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024**2), b''):
            h.update(block)
    need(ident(path) == before, 'file_changed_during_hash')
    return h.hexdigest()


def protected():
    result = {}
    changed_parents = {p.parent for p in TARGETS}
    for root in (BASE / GOOD, BASE / FAILED):
        for parent, dirs, files in os.walk(root, followlinks=False):
            parent = Path(parent)
            paths = [parent, *[parent / n for n in files]]
            for name in list(dirs):
                if (parent / name).is_symlink():
                    dirs.remove(name)
                    paths.append(parent / name)
            for path in paths:
                if path in TARGETS:
                    continue
                info = ident(path)
                need(info['dev'] == os.stat('/').st_dev and len(result) < 200000, 'bounded_original_source_filesystem')
                row = {'identity': {k: info[k] for k in ('dev', 'ino', 'mode', 'uid', 'gid')} if path in changed_parents else info}
                if stat.S_ISREG(info['mode']):
                    row['sha256'] = sha(path)
                elif stat.S_ISLNK(info['mode']):
                    row['link'] = os.readlink(path)
                else:
                    need(stat.S_ISDIR(info['mode']), 'unknown_protected_source_type')
                result[str(path)] = row
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--safety-source', required=True)
    parser.add_argument('--safety-sha256', required=True)
    parser.add_argument('--primary-proof', required=True)
    args = parser.parse_args()
    need(os.geteuid() == 0 and socket.gethostname() == 'masternode', 'original_master_root_required')
    fs = json.loads(subprocess.check_output(['findmnt', '-J', '-T', '/', '-o', 'UUID,FSTYPE'], timeout=30))['filesystems'][0]
    need(fs['uuid'] == '763cda3d-0777-4b03-a882-9d21060466e3' and fs['fstype'] == 'ext4', 'original_master_filesystem')
    for root in (BASE / GOOD, BASE / FAILED):
        need(root.resolve() == root and root.is_dir() and not root.is_mount(), 'canonical_original_attempt')
        need(not any((p / '.git').exists() or (p / '.git').is_symlink() for p in (root, *root.parents)), 'git_checkout_refused')
    proof = json.loads(base64.b64decode(args.primary_proof, validate=True))
    need(proof['fullIndependentReadbackPassed'] and proof['primary']['path'] ==
         '/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/node-cleanup-20261027/master-generated-cleanup/rollback-custom-kubectl.elf'
         and proof['primary']['sha256'] == BIN_SHA and proof['primary']['bytes'] == 61960354
         and proof['primary']['executed'] is False, 'original_artifact_preserved_off_node')
    terminal = json.loads((BASE / GOOD / 'terminal.json').read_text())
    need(terminal['phase'] == 'completed' and terminal['actualExit'] == 0 and terminal['compileOnly']
         and not terminal['imageInjected'] and not terminal['clusterChanged'], 'completed_compile_only_provenance')
    record = json.loads((A / 'record.json').read_text())
    failed_record = json.loads((B / 'record.json').read_text())
    need(record['phase'] == 'completed' and record['binary_sha256'] == BIN_SHA and record['binary_bytes'] == 61960354,
         'original_compiled_artifact_pin')
    need(record['go_archive_sha256'] == failed_record['go_archive_sha256'] == GO_SHA
         and record['source_sha256'] == failed_record['source_sha256'] == SRC_SHA, 'identical_original_public_archive_pins')
    primaries = {B / 'go1.26.9.tar.gz': GO_SHA, B / 'kubernetes-src.tar.gz': SRC_SHA}
    need(all(sha(p) == h for p, h in primaries.items()), 'retained_native_primary_archive_hashes')
    locks = []
    try:
        for path in (BASE / 'host-build.lock', BASE / GOOD / 'phase.lock', BASE / FAILED / 'phase.lock'):
            if path.exists():
                need(path.is_file() and not path.is_symlink(), 'original_lock_type')
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                locks.append(fd)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        selected = []
        for path, (digest, size) in TARGETS.items():
            info = ident(path)
            need(not any((p / '.git').exists() or (p / '.git').is_symlink() for p in path.parents), 'tracked_source_scope_refused')
            need(path.resolve() == path and path.is_relative_to(A) and stat.S_ISREG(info['mode'])
                 and info['dev'] == os.stat('/').st_dev and info['uid'] == info['gid'] == 1000
                 and info['nlink'] == 1 and info['size'] == size and not os.listxattr(path), 'exact_original_single_link_file')
            need(time.time_ns() - max(info['mtime_ns'], info['ctime_ns']) >= 72 * 3600 * 10**9, '72_hour_retention')
            need(sha(path) == digest, 'original_selected_full_hash')
            selected.append({'path': str(path), 'identity': info, 'sha256': digest})
        code = base64.b64decode(args.safety_source, validate=True)
        need(hashlib.sha256(code).hexdigest() == args.safety_sha256, 'reviewed_full_reference_guard')
        common = {'__name__': 'duplicate_output_reference_guard'}
        exec(compile(code, '<reviewed-reference-checks>', 'exec'), common)
        common.update(BASE=BASE, ATTEMPTS=(GOOD, FAILED))
        refs = common['idle']()
        preserved = protected()
        need(all(ident(Path(x['path'])) == x['identity'] and sha(Path(x['path'])) == x['sha256'] for x in selected), 'final_original_selected_identity')
        common['idle']()
        before = os.statvfs('/')
        result = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'applied': args.apply,
                  'filesystem': fs, 'selected': selected, 'references': refs, 'removed': [], 'removedAllocatedBytes': 0,
                  'protectedEntryCount': len(preserved),
                  'protectedManifestSHA256': hashlib.sha256(json.dumps(preserved, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                  'allSourceFailureAndPrimaryBytesPreserved': False, 'rollbackPrimary': proof['primary'],
                  'regeneration': proof['regeneration']}
        try:
            if args.apply:
                for row in selected:
                    path = Path(row['path'])
                    need(ident(path) == row['identity'] and sha(path) == row['sha256'], 'immediate_selected_identity')
                    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                    try:
                        opened = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
                        need((opened.st_dev, opened.st_ino) == (row['identity']['dev'], row['identity']['ino']), 'opened_selected_identity')
                        os.unlink(path.name, dir_fd=fd)
                    finally:
                        os.close(fd)
                    result['removed'].append({'path': str(path), 'allocatedBytes': row['identity']['blocks'] * 512})
                    result['removedAllocatedBytes'] += row['identity']['blocks'] * 512
            need(protected() == preserved, 'unselected_source_failure_or_primary_changed')
            need(all(sha(p) == h for p, h in primaries.items()), 'final_retained_native_primaries')
            result['allSourceFailureAndPrimaryBytesPreserved'] = True
        finally:
            after = os.statvfs('/')
            result.update(availableBeforeBytes=before.f_bavail * before.f_frsize, availableAfterBytes=after.f_bavail * after.f_frsize)
            print(json.dumps(result))
    finally:
        for fd in locks:
            os.close(fd)


if __name__ == '__main__':
    main()
