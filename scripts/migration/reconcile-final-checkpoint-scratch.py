"""Reconcile only the authenticated final checkpoint's reproducible scratch."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

BASE = '/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025'
REL = 'platform-upstream-review-20261027/final-control-plane-checkpoint-20261028'
PREFIX = 'cleanup-r2-'


def sha(p):
    with p.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identity(p):
    s = p.lstat()
    return {k: getattr(s, 'st_' + k) for k in ['dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks']}


def main():
    mode = sys.argv[1]
    if mode == 'windows':
        import ctypes
        from ctypes import wintypes
        root = Path(r'\\?\UNC\wsl.localhost\Ubuntu' + BASE.replace('/', '\\'))
        q = root / REL
        plan = json.loads((q / (PREFIX + 'plan.json')).read_text())
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        k.CreateFileW.restype = wintypes.HANDLE
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        handles = []
        try:
            for row in plan['targets']:
                p = root / row['relative']
                h = k.CreateFileW(str(p), 0x80000000, 0, None, 3,
                    0x02000000 if row['kind'] == 'directory' else 0, None)
                assert h not in (None, ctypes.c_void_p(-1).value), ('exclusive_handle_failed', str(p), ctypes.get_last_error())
                handles.append(h)
        finally:
            for h in handles:
                k.CloseHandle(h)
        with (q / (PREFIX + 'windows-exclusion.json')).open('x') as out:
            json.dump({'allTargetHandlesExclusiveAndClosed': True, 'targets': len(handles),
                'planSHA256': sha(q / (PREFIX + 'plan.json'))}, out, indent=2)
        print(json.dumps({'exclusiveHandlesClosed': len(handles)}))
        return
    assert mode in ('inventory', 'apply')
    import re
    import subprocess
    root = Path(BASE)
    q, e = root / REL, root / 'platform-upstream-review-20261027/etcd-restore-qualification'
    assert os.geteuid() == 0 and root.is_mount() and q.resolve() == q
    fs = json.loads(subprocess.check_output(['findmnt', '-J', '-T', str(root), '-o', 'UUID']))['filesystems'][0]
    assert fs['uuid'] == '3c792469-ea0e-4a2c-98e8-1185b141607b'
    op = json.loads((q / 'operator.json').read_text())
    pre = 'cp-' + op['runID'] + '-'
    restore = json.loads((e / (pre + 'restore-result.json')).read_text())
    rop = json.loads((e / (pre + 'operator-result.json')).read_text())
    assert op['status'] == rop['status'] == restore['status'] == 'completed'
    assert op['sourcesUnchanged'] and rop['sourceUnchanged'] and op['exitCode'] == rop['exitCode'] == 0
    assert restore['completeAgeAuthentication'] and restore['verifiedConfigurationFiles'] == 46
    assert restore['offlineSnapshotRestoreExecuted'] and restore['keyValueHistoryHashUnchanged']
    assert restore['logicalHistoryBefore'] == restore['logicalHistoryAfter']
    assert restore['snapshotBefore']['revision'] == restore['restoredDatabaseAfter']['revision']
    assert restore['snapshotBefore']['totalKey'] == restore['restoredDatabaseAfter']['totalKey']
    assert restore['sourceArchiveSHA256'] == op['archiveSHA256']
    backup = Path(op['backupPath'])
    assert sha(backup / 'receipt.json') == op['receiptSHA256'] and sha(backup / 'control-plane.tar.age') == op['archiveSHA256']
    proof = json.loads((e / (pre + 'nas-proof.json')).read_text())
    assert proof['fullNASReadback'] and proof['sha256'] == op['archiveSHA256']
    state = subprocess.check_output(['systemctl', 'show', 'branconet-cp-restore-' + op['runID'] + '.service',
        '--property=ActiveState,MainPID']).decode()
    assert 'MainPID=0' in state and ('ActiveState=inactive' in state or 'ActiveState=failed' in state)
    work = e / (pre + 'scratch')
    # The earlier Windows access failure protects the exact root-owned packaging
    # subtree. Do not change its permissions, retry its deletion or inspect it
    # through another deletion route. Reconcile the independent eligible roots.
    exception = json.loads((q / 'cleanup-preservation-exception.json').read_text())
    assert exception['retained'] and exception['path'] == str(q / 'restore-ansible-scratch')
    targets = [q / 'ansible-scratch', work]
    assert all(p.exists() and p.resolve() == p and p.is_relative_to(root) for p in targets)
    guard = root / 'node-cleanup-20261027/master-generated-cleanup/reference-full-properties.py'
    assert sha(guard) == '3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87'
    library = {'__name__': 'final_checkpoint_inactive_reference_guard'}
    exec(compile(guard.read_bytes(), str(guard), 'exec'), library)
    library.update(BASE=root, ATTEMPTS=tuple(str(p.relative_to(root)) for p in targets))
    refs = library['idle']()
    rows = []
    for target in targets:
        for p in [target, *target.rglob('*')]:
            info = identity(p)
            assert p.resolve() == p and not p.is_symlink() and not p.is_mount()
            assert info['dev'] == root.stat().st_dev and info['uid'] in (0, 1000) and not os.listxattr(p)
            kind = 'directory' if stat.S_ISDIR(info['mode']) else 'file'
            if kind == 'file':
                rel = str(p.relative_to(work))
                assert p.is_relative_to(work) and stat.S_ISREG(info['mode']) and info['nlink'] == 1
                assert rel in ('snapshot.db', 'restored/member/snap/db') or re.fullmatch(r'restored/member/(snap/[0-9a-f]{16}-[0-9a-f]{16}\.snap|wal/[0-9a-f]{16}-[0-9a-f]{16}\.wal)', rel)
            rows.append({'relative': str(p.relative_to(root)), 'kind': kind, 'identity': info,
                **({'sha256': sha(p)} if kind == 'file' else {})})
    if mode == 'inventory':
        protected = {}
        for base in (q, e, backup):
            for parent, dirs, files in os.walk(base):
                parent = Path(parent)
                dirs[:] = [d for d in dirs if not any((parent / d).is_relative_to(t) for t in targets)]
                for name in files:
                    p = parent / name
                    assert p.resolve() == p and p.is_file()
                    protected[str(p.relative_to(root))] = sha(p)
        with (q / (PREFIX + 'plan.json')).open('x') as out:
            json.dump({'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': BASE,
                'targets': rows, 'protected': protected, 'references': refs,
                'regeneration': 'Authenticated existing age archive, pinned stock etcdutl and maintained private-network offline restore; packaging directories are empty'}, out, indent=2)
        print(json.dumps({'targets': len(rows), 'allocatedBytes': sum(r['identity']['blocks'] * 512 for r in rows)}))
        return
    plan = json.loads((q / (PREFIX + 'plan.json')).read_text())
    win = json.loads((q / (PREFIX + 'windows-exclusion.json')).read_text())
    assert win['allTargetHandlesExclusiveAndClosed']
    assert win['targets'] == len(rows) and win['planSHA256'] == sha(q / (PREFIX + 'plan.json'))
    assert rows == plan['targets'] and all(sha(root / p) == v for p, v in plan['protected'].items())
    removed = []
    for row in sorted(rows, key=lambda r: (r['kind'] == 'directory', -len(Path(r['relative']).parts))):
        p = root / row['relative']
        now = identity(p)
        keys = list(now) if row['kind'] == 'file' else ['dev', 'ino', 'mode', 'uid', 'gid']
        assert all(now[k] == row['identity'][k] for k in keys)
        if row['kind'] == 'file':
            assert sha(p) == row['sha256']
            p.unlink()
        else:
            assert not any(p.iterdir())
            p.rmdir()
        removed.append({'path': str(p), 'allocatedBytes': now['blocks'] * 512})
    assert all(sha(root / p) == v for p, v in plan['protected'].items())
    result = {'status': 'completed', 'removed': removed, 'removedAllocatedLinuxBytes': sum(r['allocatedBytes'] for r in removed),
        'protectedFilesUnchanged': len(plan['protected']), 'WindowsRecoveryClaimed': False,
        'retained': [exception, {'path': str(e / 'tools/etcdutl'), 'remainingConsumer': 'Supported Longhorn upgrade failure recovery window; reconcile when closed'},
            {'path': str(backup), 'remainingConsumer': 'Final encrypted pre-upgrade recovery checkpoint, with independent NAS copy'}]}
    with (q / (PREFIX + 'receipt.json')).open('x') as out:
        json.dump(result, out, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != 'removed'}))


if __name__ == '__main__':
    main()
