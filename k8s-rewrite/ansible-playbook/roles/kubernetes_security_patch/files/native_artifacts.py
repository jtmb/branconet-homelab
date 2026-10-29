"""Inventory/remove only proven task-generated native kubeadm/native-binary staging."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys


def fingerprint(p):
    s = p.lstat()
    assert stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1 and not p.is_symlink()
    return {'path': str(p), 'bytes': s.st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}


def native_inventory(base):
    assert re.fullmatch(r'/etc/kubernetes/tmp/kubernetes1372-[a-z0-9_]+', str(base))
    assert base.resolve() == base and base.is_dir() and base.stat().st_uid == 0
    expected = {'upgrade.yaml'}
    if platform.node() == 'masternode':
        expected |= {'patches/' + n + '+json.json' for n in ['kube-apiserver', 'kube-controller-manager', 'kube-scheduler']}
    actual = list(base.rglob('*'))
    assert all(not p.is_symlink() and p.stat().st_uid == 0 for p in actual)
    assert {str(p.relative_to(base)) for p in actual if p.is_file()} == expected
    assert {str(p.relative_to(base)) for p in actual if p.is_dir()} == {'patches'}
    return sorted([fingerprint(base / n) for n in expected], key=lambda r: r['path'])


def directory_identity(base):
    assert os.geteuid() == 0 and re.fullmatch(r'/etc/kubernetes/tmp/kubernetes1372-[a-z0-9_]+', str(base))
    assert base.resolve() == base and base.is_dir() and not base.is_symlink()
    s = base.lstat()
    assert s.st_uid == s.st_gid == 0 and stat.S_IMODE(s.st_mode) == 0o700
    return {'path': str(base), 'host': platform.node(), 'device': s.st_dev, 'inode': s.st_ino,
            'uid': s.st_uid, 'gid': s.st_gid, 'mode': stat.S_IMODE(s.st_mode), 'allocationName': base.name}


def verify_allocation(base, allocation):
    assert allocation['ownerTask'] == 'kubernetes1372-security-patch' and allocation['observedEmptyBeforeWrites'] is True
    assert allocation['directory'] == directory_identity(base), 'Native allocation identity changed or has no original proof'


def write_native(base, data):
    verify_allocation(base, data['allocation'])
    assert os.getegid() == 0
    relative = data['relativePath']
    allowed = {'upgrade.yaml'}
    if platform.node() == 'masternode':
        allowed |= {'patches/' + n + '+json.json' for n in ['kube-apiserver', 'kube-controller-manager', 'kube-scheduler']}
    assert relative in allowed
    target = base / relative
    assert target.parent.resolve() == target.parent and target.parent.is_dir()
    parent = target.parent.stat()
    assert parent.st_uid == parent.st_gid == 0 and stat.S_IMODE(parent.st_mode) == 0o700 and parent.st_dev == base.stat().st_dev
    content = data['content'].encode('utf-8')
    assert 0 < len(content) <= 2 * 1024**2
    if relative.startswith('patches/'):
        patches = json.loads(content)
        assert len(patches) == 2 and [p['path'] for p in patches] == ['/spec', '/metadata']
        assert all(set(p) == {'op', 'path', 'value'} and p['op'] == 'replace' and isinstance(p['value'], dict) for p in patches)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(content); stream.flush(); os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    verify_allocation(base, data['allocation'])
    result = fingerprint(target)
    assert result['bytes'] == len(content) and result['sha256'] == hashlib.sha256(content).hexdigest()
    return result


def unused(paths):
    # No raw process arguments/environment are read or emitted. A denied
    # process/reference check retains the exact target, never authorizes delete.
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            refs = [proc / 'cwd', proc / 'root'] + list((proc / 'fd').iterdir())
            for ref in refs:
                try:
                    target = os.readlink(ref)
                except FileNotFoundError:
                    continue
                assert not any(target == p or target.startswith(p + '/') for p in paths), 'Active process reference'
            for source in ['maps', 'mountinfo']:
                text = (proc / source).read_text()
                assert not any(p in text for p in paths), 'Active memory map or mount reference'
        except (FileNotFoundError, ProcessLookupError):
            continue


data = json.load(sys.stdin)
base = Path(data['nativeDirectory'])
if sys.argv[1] == 'allocation':
    identity = directory_identity(base)
    assert not any(base.iterdir()), 'Only a freshly empty allocation may establish ownership'
    print(json.dumps({'ownerTask': 'kubernetes1372-security-patch', 'directory': identity,
                      'observedEmptyBeforeWrites': True, 'observedCreationCtimeNs': base.stat().st_ctime_ns,
                      'regeneration': 'New Ansible tempfile allocation; never infer ownership from prefix'}))
elif sys.argv[1] == 'write':
    print(json.dumps(write_native(base, data)))
elif sys.argv[1] == 'record':
    verify_allocation(base, data['allocation'])
    print(json.dumps({'nativeDirectory': str(base), 'files': native_inventory(base),
                      'allocation': data['allocation'],
                      'regeneration': 'Re-render native JSON patches and UpgradeConfiguration from source and preserved pre-cordon controller receipt',
                      'lastConsumer': 'Successful native upgrade and exact host preservation verification'}))
else:
    assert sys.argv[1] == 'cleanup' and data['hostVerified'] is True
    removed, retained, absent = [], [], []
    try:
        assert 'allocation' in data['nativeInventory'], 'No pre-write allocation proof; retain exact directory as exception'
        verify_allocation(base, data['nativeInventory']['allocation'])
        assert native_inventory(base) == data['nativeInventory']['files'], 'Generated configuration changed'
        unused([str(base)])
        for row in data['nativeInventory']['files']:
            Path(row['path']).unlink(); removed.append(row)
        (base / 'patches').rmdir(); base.rmdir()
    except (AssertionError, OSError) as exc:
        retained.append({'path': str(base), 'reason': type(exc).__name__ + ': ' + str(exc)})
    for row in data['binaryStaging']:
        p = Path(row['path'])
        assert re.fullmatch(r'/usr/local/bin/\.kubernetes1372-(kubeadm|kubelet|kubectl)-[a-f0-9]{64}\.new', str(p))
        if not row['newlyCreated']:
            retained.append({'path': str(p), 'reason': 'Pre-existing native file; not owned disposable output'})
            continue
        if not p.exists() and not p.is_symlink():
            absent.append({'path': str(p), 'reason': 'Consumed by atomic native replacement; no filesystem recovery bytes claimed'})
            continue
        try:
            assert p.resolve() == p
            actual = fingerprint(p)
            assert actual == {k: row[k] for k in ['path', 'bytes', 'sha256']}, 'Staged native binary changed'
            unused([str(p)])
            p.unlink(); removed.append(actual)
        except (AssertionError, OSError) as exc:
            retained.append({'path': str(p), 'reason': type(exc).__name__ + ': ' + str(exc)})
    print(json.dumps({'removed': removed, 'removedBytes': sum(r['bytes'] for r in removed), 'retained': retained, 'absentAfterConsumer': absent,
                      'originalKubeadmBackupsTouched': False, 'windowsRecoveryClaimed': False}))
