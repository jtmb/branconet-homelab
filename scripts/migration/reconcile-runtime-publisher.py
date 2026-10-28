"""Retire exact completed publisher exports with Git, Linux and Windows proof."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

BASE = '/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025'
HREL = 'platform-upstream-review-20261027/longhorn-runtime-retirement-20261028'
EXPECTED = {'helm': '57ce7fc4ea77b28ee6fa91ae071abcade74d3f524e80c9decff5877a5ac8eda4',
    'kubectl': '65691ff77eb6fa44c908b77a1082c9f092c3b9733b5cefabec0d1104890e21a8',
    'gitleaks': '88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509'}


def sha(p):
    with p.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identity(p):
    s = p.lstat()
    return {k: getattr(s, 'st_' + k) for k in ('dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks')}


def save(p, value):
    with p.open('x') as out:
        json.dump(value, out, indent=2)
    if os.name != 'nt':
        os.chown(p, 1000, 1000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['inventory', 'windows', 'apply'])
    parser.add_argument('--stage', action='append', required=True)
    a = parser.parse_args()
    assert 1 <= len(a.stage) <= 8 and all(re.fullmatch('[0-9a-f]{32}:[0-9a-f]{40}', s) for s in a.stage)
    selected = dict(s.split(':') for s in a.stage)
    assert len(selected) == len(a.stage)
    token = hashlib.sha256(json.dumps(selected, sort_keys=True).encode()).hexdigest()[:16]
    root = Path(r'\\?\UNC\wsl.localhost\Ubuntu' + BASE.replace('/', '\\')) if os.name == 'nt' else Path(BASE)
    r = root / HREL / ('publisher-cleanup-' + token)
    if a.mode == 'windows':
        assert os.name == 'nt'
        import ctypes
        from ctypes import wintypes
        plan = json.loads((r / 'plan.json').read_text())
        assert plan['selected'] == selected and plan['sourceSHA256'] == sha(Path(__file__))
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        k.CreateFileW.restype = wintypes.HANDLE
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        handles = []
        try:
            for row in plan['targets']:
                p = root / row['relative']
                handle = k.CreateFileW(str(p), 0x80000000, 0, None, 3,
                    0x02000000 if row['kind'] == 'directory' else 0, None)
                assert handle not in (None, ctypes.c_void_p(-1).value), ('exclusive_target_handle_failed', str(p), ctypes.get_last_error())
                handles.append(handle)
                if row['kind'] == 'file':
                    # The exclusive original handle remains held. Reopening the
                    # same file would self-conflict; content is hashed in Linux
                    # before and after this independent Windows exclusion.
                    assert p.stat().st_size == row['identity']['size']
            assert all(sha(root / p) == h for p, h in plan['protected'].items())
        finally:
            for handle in handles:
                k.CloseHandle(handle)
        save(r / 'windows-proof.json', {'allTargetHandlesExclusiveAndClosed': True, 'targets': len(handles),
            'planSHA256': sha(r / 'plan.json'), 'protectedHashesUnchanged': True})
        print(json.dumps({'key': token, 'exclusiveHandlesClosed': len(handles)}))
        return
    assert os.geteuid() == 0 and root.is_mount() and r.parent.resolve() == r.parent
    import fcntl
    fs = json.loads(subprocess.check_output(['findmnt', '-J', '-T', str(root), '-o', 'UUID']))['filesystems'][0]
    assert fs['uuid'] == '3c792469-ea0e-4a2c-98e8-1185b141607b'
    git = '/mnt/c/Program Files/Git/cmd/git.exe'
    repo = 'C:/Users/james/.codex/local-ci/branconet-charts-local-ci'
    tools = Path('/mnt/c/Users/james/.codex/local-ci/branconet-charts-local-ci/.tools')
    assert all(sha(tools / name) == digest for name, digest in EXPECTED.items())
    if a.mode == 'inventory':
        assert not r.exists()
        r.mkdir(mode=0o700)
        os.chown(r, 1000, 1000)
        save(r / 'ownership.json', {'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': BASE,
            'physicalFilesystemUUID': fs['uuid'], 'generatedPaths': [str(r)], 'completePeakBytes': 4 * 1024**2,
            'regeneration': 'Exact reachable Git commits/blobs and retained original pinned publisher tools; never replay completed publication',
            'protected': 'All original repositories/source/locks, minimal validation/publication reports and all failed/unselected stages'})
    locks, rows, protected, roots = [], [], {}, []
    try:
        for ident, revision in selected.items():
            stage = root / 'local-charts-publisher' / ('local-charts-publish-' + ident)
            assert stage.resolve() == stage and stage.stat().st_dev == root.stat().st_dev
            lock = (stage / 'operation.lock').open('r+b')
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locks.append(lock)
            docs = {phase: json.loads((stage / (phase + '.json')).read_text()) for phase in ['prepare', 'check', 'publish']}
            assert all(d['passed'] is True and d['sourceSHA'] == revision for d in docs.values())
            assert docs['prepare']['binariesSHA256'] == EXPECTED and docs['publish']['publicationPerformed']
            assert docs['publish']['actionsUsed'] is False and docs['publish']['checkReceiptSHA256'] == sha(stage / 'check.json')
            assert docs['check']['prepareReceiptSHA256'] == sha(stage / 'prepare.json')
            assert docs['check']['validationReportSHA256'] == sha(stage / 'source/.validation/validation.json')
            raw = subprocess.check_output([git, '-C', repo, 'ls-tree', '-r', '-z', revision])
            manifest = {}
            for line in raw.split(b'\0'):
                if not line:
                    continue
                header, name = line.split(b'\t', 1)
                mode, kind, oid = header.decode().split()
                assert kind == 'blob'
                manifest[name.decode()] = {'mode': mode, 'oid': oid}
            assert manifest == docs['prepare']['manifest']
            assert subprocess.run([git, '-C', repo, 'merge-base', '--is-ancestor', revision, 'HEAD'], capture_output=True).returncode == 0
            source = stage / 'source'
            assert not (source / '.git').exists()
            expected = set(manifest) | {'.tools/' + n for n in EXPECTED} | {'.validation/validation.json'}
            assert {str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()} == expected
            files = [source / name for name in manifest] + [source / '.tools' / name for name in EXPECTED]
            for p in files:
                info = identity(p)
                assert p.resolve() == p and p.is_relative_to(root) and stat.S_ISREG(info['mode'])
                assert info['dev'] == root.stat().st_dev and info['uid'] == 1000 and info['nlink'] == 1 and not os.listxattr(p)
                data = p.read_bytes()
                rel = str(p.relative_to(source))
                if rel in manifest:
                    assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == manifest[rel]['oid']
                else:
                    assert hashlib.sha256(data).hexdigest() == EXPECTED[p.name]
                rows.append({'relative': str(p.relative_to(root)), 'kind': 'file', 'identity': info, 'sha256': hashlib.sha256(data).hexdigest()})
            dirs = {p for f in files for p in f.parents if source in p.parents}
            dirs.update([stage / 'home', stage / 'tmp'])
            for p in dirs:
                info = identity(p)
                assert p.resolve() == p and p.is_dir() and not p.is_mount() and info['dev'] == root.stat().st_dev
                assert info['uid'] == 1000 and not os.listxattr(p)
                if p in (stage / 'home', stage / 'tmp'):
                    assert not any(p.iterdir())
                rows.append({'relative': str(p.relative_to(root)), 'kind': 'directory', 'identity': info})
            for p in [stage / n for n in ('prepare.json', 'check.json', 'publish.json', 'operation.lock', 'source/.validation/validation.json')]:
                protected[str(p.relative_to(root))] = sha(p)
            roots.extend([str(source.relative_to(root)), str((stage / 'home').relative_to(root)), str((stage / 'tmp').relative_to(root))])
        rows.sort(key=lambda row: row['relative'])
        guard = root / 'node-cleanup-20261027/master-generated-cleanup/reference-full-properties.py'
        assert sha(guard) == '3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87'
        lib = {'__name__': 'complete_publisher_export_reference_guard'}
        exec(compile(guard.read_bytes(), str(guard), 'exec'), lib)
        lib.update(BASE=root, ATTEMPTS=tuple(roots))
        refs = lib['idle']()
        if a.mode == 'inventory':
            save(r / 'plan.json', {'selected': selected, 'sourceSHA256': sha(Path(__file__)), 'targets': rows,
                'protected': protected, 'references': refs, 'regeneration': 'Exact reachable Git archive/manifests plus retained original checksum-pinned publisher .tools; preserve unique .validation report'})
            print(json.dumps({'key': token, 'targets': len(rows), 'allocatedBytes': sum(x['identity']['blocks'] * 512 for x in rows)}))
            return
        plan = json.loads((r / 'plan.json').read_text())
        proof = json.loads((r / 'windows-proof.json').read_text())
        assert plan['selected'] == selected and plan['sourceSHA256'] == sha(Path(__file__))
        assert rows == plan['targets'] and protected == plan['protected']
        assert proof['allTargetHandlesExclusiveAndClosed'] and proof['targets'] == len(rows)
        assert proof['planSHA256'] == sha(r / 'plan.json') and proof['protectedHashesUnchanged']
        removed = []
        for row in sorted(rows, key=lambda row: (row['kind'] == 'directory', -len(Path(row['relative']).parts))):
            p = root / row['relative']
            info = identity(p)
            keys = list(info) if row['kind'] == 'file' else ['dev', 'ino', 'mode', 'uid', 'gid']
            assert all(info[k] == row['identity'][k] for k in keys)
            if row['kind'] == 'file':
                assert sha(p) == row['sha256']
                p.unlink()
            else:
                assert not any(p.iterdir())
                p.rmdir()
            removed.append({'path': str(p), 'allocatedBytes': info['blocks'] * 512})
        assert all(sha(root / p) == digest for p, digest in protected.items())
        assert all(sha(tools / name) == digest for name, digest in EXPECTED.items())
        result = {'status': 'completed', 'removed': removed, 'removedAllocatedLinuxBytes': sum(v['allocatedBytes'] for v in removed),
            'originalGitSourceAndToolsPreserved': True, 'protectedFilesUnchanged': len(protected), 'WindowsRecoveryClaimed': False,
            'retained': ['Each exact stage prepare/check/publish/lock and source/.validation/validation.json',
                'All unselected/failed stages', 'Required active isolated source worktree for remaining runtime maintenance']}
        save(r / 'receipt.json', result)
        print(json.dumps({k: v for k, v in result.items() if k != 'removed'}))
    finally:
        for lock in locks:
            lock.close()


if __name__ == '__main__':
    main()
