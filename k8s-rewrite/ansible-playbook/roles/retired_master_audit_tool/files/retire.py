"""Retire one original public scanner copy; preserve every report and input."""
import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import time

BASE = Path('/home/james/.local/share/branconet-migration')
NAME = 'audit20261023-20261023T203418Z'
ROOT = BASE / NAME
SHA = 'd1dfca6ae10a1ad4540bb94e64f0510077c47008920a9b554986b39dca573d83'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def ident(path):
    s = path.lstat()
    return {k: getattr(s, 'st_' + k) for k in ('dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks')}


def sha(path):
    before = ident(path)
    h = hashlib.sha256()
    with path.open('rb') as inp:
        for chunk in iter(lambda: inp.read(1024**2), b''):
            h.update(chunk)
    need(ident(path) == before, 'changed_during_hash')
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--safety-source', required=True)
    parser.add_argument('--safety-sha256', required=True)
    parser.add_argument('--primary-proof', required=True)
    args = parser.parse_args()
    need(os.geteuid() == 0 and socket.gethostname() == 'masternode', 'original_master_root_required')
    fs = json.loads(subprocess.check_output(['findmnt', '-J', '-T', str(ROOT), '-o', 'UUID,FSTYPE'], timeout=30))['filesystems'][0]
    need(fs['uuid'] == '763cda3d-0777-4b03-a882-9d21060466e3' and fs['fstype'] == 'ext4', 'original_master_filesystem')
    need(ROOT.resolve() == ROOT and ROOT.is_dir() and not ROOT.is_mount(), 'canonical_original_root')
    need(not any((p / '.git').exists() or (p / '.git').is_symlink() for p in [ROOT, *ROOT.parents]), 'git_source_refused')
    proof = json.loads(base64.b64decode(args.primary_proof, validate=True))
    need(proof['primary'] == {
        'path': '/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/local-oci-scan/bin/trivy',
        'bytes': 176029856, 'sha256': SHA}, 'retained_identical_primary_required')
    original_provenance = json.loads((ROOT / 'tool-provenance.json').read_text())
    need(original_provenance == proof['originalProvenance'], 'original_provenance_changed')
    records = [r for r in original_provenance if r['repo'] == 'aquasecurity/trivy']
    need(len(records) == 1 and records[0]['tag'] == 'v0.76.1'
         and records[0]['binarySha256'] == SHA and records[0]['officialChecksumMatched'], 'original_public_source_binding')
    binary = ROOT / 'bin/trivy'
    directory = binary.parent
    need(binary.resolve() == binary and directory.resolve() == directory
         and set(p.name for p in directory.iterdir()) == {'trivy'}, 'exact_one_tool_directory')
    selected = [{'path': str(binary), 'identity': ident(binary)}, {'path': str(directory), 'identity': ident(directory)}]
    info = selected[0]['identity']
    need(stat.S_ISREG(info['mode']) and info['uid'] == 1000 and info['gid'] == 1000
         and info['nlink'] == 1 and info['dev'] == os.stat('/').st_dev
         and info['size'] == 176029856 and not info['mode'] & 0o077, 'original_protected_single_link_binary')
    need(time.time_ns() - max(info['mtime_ns'], info['ctime_ns']) >= 72 * 3600 * 10**9, '72_hour_retention')
    need(not os.listxattr(binary) and not os.listxattr(directory) and sha(binary) == SHA, 'exact_public_binary')
    preserved = {}
    for parent, dirs, files in os.walk(ROOT, followlinks=False):
        parent = Path(parent)
        for p in [parent, *[parent / d for d in dirs if (parent / d).is_symlink()], *[parent / f for f in files]]:
            if p in (binary, directory):
                continue
            s = ident(p)
            need(s['dev'] == info['dev'] and len(preserved) < 20000, 'bounded_same_filesystem_evidence')
            entry = {'identity': s}
            if stat.S_ISREG(s['mode']):
                entry['sha256'] = sha(p)
            elif stat.S_ISLNK(s['mode']):
                entry['link'] = os.readlink(p)
            else:
                need(stat.S_ISDIR(s['mode']), 'unknown_evidence_type')
            preserved[str(p)] = entry
    code = base64.b64decode(args.safety_source, validate=True)
    need(hashlib.sha256(code).hexdigest() == args.safety_sha256, 'reviewed_reference_source')
    common = {'__name__': 'master_audit_tool_reference_checks'}
    exec(compile(code, '<reviewed-reference-checks>', 'exec'), common)
    common.update(BASE=BASE, ATTEMPTS=(NAME,))
    references = common['idle']()
    need(all(ident(Path(r['path'])) == r['identity'] for r in selected) and sha(binary) == SHA, 'final_original_identity')
    common['idle']()
    before = os.statvfs('/')
    result = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'filesystem': fs,
              'applied': args.apply, 'selected': selected, 'references': references,
              'sha256': SHA, 'preserved': preserved, 'removed': [], 'removedAllocatedBytes': 0,
              'regeneration': proof['regeneration'], 'sourceReportsAndFailuresPreserved': False}
    try:
        if args.apply:
            for row in selected:
                p = Path(row['path'])
                s = ident(p)
                keys = list(s) if p == binary else ['dev', 'ino', 'uid', 'gid', 'mode']
                need(all(s[k] == row['identity'][k] for k in keys), 'final_selected_identity')
                if p == binary:
                    need(sha(p) == SHA, 'final_binary_hash')
                else:
                    need(not any(p.iterdir()), 'directory_must_be_empty')
                fd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    opened = os.stat(p.name, dir_fd=fd, follow_symlinks=False)
                    need((opened.st_dev, opened.st_ino) == (s['dev'], s['ino']), 'opened_identity')
                    (os.unlink if p == binary else os.rmdir)(p.name, dir_fd=fd)
                finally:
                    os.close(fd)
                result['removed'].append({'path': str(p), 'allocatedBytes': s['blocks'] * 512})
                result['removedAllocatedBytes'] += s['blocks'] * 512
        for name, row in preserved.items():
            p = Path(name)
            current = ident(p)
            keys = ('dev', 'ino', 'mode', 'uid', 'gid') if p == ROOT else tuple(current)
            need(all(current[k] == row['identity'][k] for k in keys), 'original_evidence_identity_changed')
            if 'sha256' in row:
                need(sha(p) == row['sha256'], 'original_evidence_bytes_changed')
            if 'link' in row:
                need(os.readlink(p) == row['link'], 'original_evidence_link_changed')
        result['sourceReportsAndFailuresPreserved'] = True
    finally:
        after = os.statvfs('/')
        result.update(availableBeforeBytes=before.f_bavail * before.f_frsize,
                      availableAfterBytes=after.f_bavail * after.f_frsize)
        print(json.dumps(result))


if __name__ == '__main__':
    main()
