"""Retire only empty completed staging scratch with Linux and Windows exclusion."""
import hashlib
import json
import os
from pathlib import Path
import sys

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
REL = 'platform-upstream-review-20261027/longhorn-production-prestage-20261028'
U = F / REL
S = U / 'ansible-scratch'


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def identity(p):
    s = p.lstat()
    return {k: getattr(s, 'st_' + k) for k in ['dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks']}


def save(name, value):
    with (U / name).open('x') as f:
        json.dump(value, f, indent=2)
    os.chown(U / name, 1000, 1000)


def windows():
    import ctypes
    from ctypes import wintypes
    base = Path(r'\\?\UNC\wsl.localhost\Ubuntu\home\brajam\.local\share\branconet-migration\local-image-build-offload-20261025')
    u = base / REL
    plan = json.loads((u / 'scratch-cleanup-plan.json').read_text())
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    k.CreateFileW.restype = wintypes.HANDLE
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    handles = []
    try:
        for row in plan['directories']:
            p = base / row['relative']
            h = k.CreateFileW(str(p), 0x80000000, 0, None, 3, 0x02000000, None)
            assert h not in (None, ctypes.c_void_p(-1).value), ('exclusive_directory_handle', ctypes.get_last_error())
            handles.append(h)
        assert all(sha(u / rel) == digest for rel, digest in plan['protectedFiles'].items())
    finally:
        for h in handles:
            k.CloseHandle(h)
    with (u / 'scratch-windows-exclusion.json').open('x') as f:
        json.dump({'allDirectoryHandlesExclusiveAndClosed': True, 'directories': len(handles),
                   'allProtectedSourceHashesPassed': True, 'planSHA256': sha(u / 'scratch-cleanup-plan.json')}, f, indent=2)
    print(json.dumps({'exclusiveDirectoriesClosed': len(handles), 'protectedFiles': len(plan['protectedFiles'])}))


def linux(apply):
    import fcntl
    assert os.geteuid() == 0 and F.is_mount() and U.resolve() == U and S.resolve() == S
    operator = json.loads((U / 'ansible-operator.json').read_text())
    assert operator['status'] == 'completed' and operator['exitCode'] == 0 and operator['sourcesUnchanged']
    assert all(sha(Path(p)) == h for p, h in operator['sources'].items())
    guard = F / 'node-cleanup-20261027/master-generated-cleanup/reference-full-properties.py'
    assert sha(guard) == '3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87'
    scope = {'__name__': 'completed_scratch_reference_guard'}
    exec(compile(guard.read_bytes(), str(guard), 'exec'), scope)
    scope.update(BASE=F, ATTEMPTS=(str(S.relative_to(F)),))
    with (U / 'scratch-cleanup.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        refs = scope['idle']()
        directories = [S, *S.rglob('*')]
        assert all(p.is_dir() and not p.is_symlink() and not p.is_mount() and p.resolve() == p
                   and p.stat().st_dev == F.stat().st_dev and p.stat().st_uid in (0, 1000) for p in directories)
        if not apply:
            protected = {str(p.relative_to(U)): sha(p) for p in U.rglob('*') if p.is_file()
                         and not p.is_relative_to(S) and p.name != 'scratch-cleanup.lock'}
            save('scratch-cleanup-plan.json', {'directories': [{'relative': str(p.relative_to(F)), 'identity': identity(p)} for p in directories],
                'protectedFiles': protected, 'references': refs,
                'regeneration': 'Recreate these empty Ansible home/local directories with their recorded owner/mode; no completed cluster operation needs replay.'})
            print(json.dumps({'emptyDirectories': len(directories), 'allocatedBytes': sum(p.stat().st_blocks * 512 for p in directories)}))
            return
        plan = json.loads((U / 'scratch-cleanup-plan.json').read_text())
        win = json.loads((U / 'scratch-windows-exclusion.json').read_text())
        assert win['allDirectoryHandlesExclusiveAndClosed'] and win['allProtectedSourceHashesPassed']
        assert win['planSHA256'] == sha(U / 'scratch-cleanup-plan.json') and win['directories'] == len(directories)
        assert {str(p.relative_to(F)): identity(p) for p in directories} == {r['relative']: r['identity'] for r in plan['directories']}
        assert all(sha(U / p) == h for p, h in plan['protectedFiles'].items())
        removed = []
        for row in sorted(plan['directories'], key=lambda r: len(Path(r['relative']).parts), reverse=True):
            p = F / row['relative']
            s = identity(p)
            assert all(s[k] == row['identity'][k] for k in ['dev', 'ino', 'mode', 'uid', 'gid']) and not any(p.iterdir())
            p.rmdir()
            removed.append({'path': str(p), 'allocatedBytes': s['blocks'] * 512})
        assert all(sha(U / p) == h for p, h in plan['protectedFiles'].items())
        save('scratch-cleanup-receipt.json', {'status': 'completed', 'removed': removed,
            'removedAllocatedLinuxBytes': sum(r['allocatedBytes'] for r in removed),
            'protectedFilesUnchanged': len(plan['protectedFiles']), 'references': refs, 'WindowsRecoveryClaimed': False})
        print(json.dumps({'removedDirectories': len(removed), 'removedAllocatedLinuxBytes': sum(r['allocatedBytes'] for r in removed)}))


if __name__ == '__main__':
    if sys.argv[1] == 'windows':
        windows()
    else:
        linux(sys.argv[1] == 'apply')
