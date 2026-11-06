"""Memory-only remote staging; never execute, install or delete a binary."""
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys

NAMES = ('kubeadm', 'kubelet', 'kubectl')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def metadata(path):
    before = path.lstat()
    assert path.resolve() == path and stat.S_ISREG(before.st_mode) and before.st_nlink == 1
    attrs = {n: os.getxattr(path, n).hex() for n in sorted(os.listxattr(path))}
    result = dict(path=str(path), sha256=digest(path), bytes=before.st_size,
                  mode=stat.S_IMODE(before.st_mode), uid=before.st_uid, gid=before.st_gid,
                  mtimeNs=before.st_mtime_ns,
                  xattrsSHA256=hashlib.sha256(json.dumps(attrs, sort_keys=True, separators=(',', ':')).encode()).hexdigest())
    after = path.lstat()
    assert (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    return result


def command(args):
    return subprocess.check_output(args, text=True, timeout=60).strip()


def observe(request):
    directory = Path('/usr/local/bin')
    assert directory.resolve() == directory and directory.stat().st_uid == 0
    assert not stat.S_IMODE(directory.stat().st_mode) & 0o022
    fs = os.statvfs(directory)
    originals = {n: metadata(directory / n) for n in NAMES}
    stages = {}
    for n in NAMES:
        path = directory / ('.kubernetes1372-' + n + '-' + request['binaries'][n]['sha256'] + '.new')
        stages[n] = metadata(path) if os.path.lexists(path) else None
    unit = command(['systemctl', 'show', 'kubelet', '--property=FragmentPath', '--value'])
    return dict(host=platform.node(), rootFSUUID=command(['findmnt', '-n', '-o', 'UUID', '/']),
                rootDevice=command(['findmnt', '-n', '-o', 'SOURCE', '/']),
                bootID=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                nativeDevice=directory.stat().st_dev, rootDeviceID=Path('/').stat().st_dev,
                runtime=command(['/opt/containerd-k8s/bin/containerd', '--version']),
                holds=sorted(command(['apt-mark', 'showhold']).splitlines()),
                kubeletUnit=unit, kubeletUnitSHA256=digest(Path(unit)), binaries=originals, stages=stages,
                capacity=fs.f_blocks * fs.f_frsize, free=fs.f_bfree * fs.f_frsize,
                available=fs.f_bavail * fs.f_frsize, blockSize=fs.f_frsize)


def identity(value):
    return {k: value[k] for k in ('host', 'rootFSUUID', 'rootDevice', 'bootID', 'nativeDevice',
                                 'rootDeviceID', 'runtime', 'holds', 'kubeletUnit', 'kubeletUnitSHA256', 'binaries')}


def budget(value, request):
    assert value['rootFSUUID'] and value['nativeDevice'] == value['rootDeviceID']
    assert value['runtime'].split()[2] == 'v2.4.2'
    swap = 128 * 1024**2 + sum(request['binaries'][n]['bytes'] + value['binaries'][n]['bytes'] for n in NAMES)
    block = value['blockSize']
    stage = sum(((request['binaries'][n]['bytes'] + block - 1) // block) * block for n in NAMES if value['stages'][n] is None)
    peak = swap + stage + 1024**2
    assert value['available'] >= 15 * 1024**3 + peak, '15GiB available plus staging and remaining swap peak'
    assert value['free'] >= value['capacity'] // 4 + 1 + 512 * 1024**2 + peak, '25percent plus512MiB and full staging/swap peak'
    return dict(stageBytes=stage, remainingSwapPeakBytes=swap, metadataMarginBytes=1024**2, peakBytes=peak)


def stage(request):
    assert os.geteuid() == 0
    before = observe(request)
    assert identity(before) == identity(request['before']), 'Live origin or identity changed'
    budget(before, request)
    name = request['name']; assert name in NAMES and before['stages'][name] is None
    original = Path('/usr/local/bin') / name
    old = before['binaries'][name]
    entry = request['binaries'][name]
    target = Path('/usr/local/bin') / ('.kubernetes1372-' + name + '-' + entry['sha256'] + '.new')
    attrs = {n: os.getxattr(original, n) for n in os.listxattr(original)}
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    # On failure leave the exclusive partial path and intent protected. Never replay/delete it.
    try:
        h = hashlib.sha256(); remaining = entry['bytes']
        while remaining:
            block = sys.stdin.buffer.read(min(1024 * 1024, remaining))
            assert block, 'Truncated native stage stream'
            h.update(block); remaining -= len(block)
            view = memoryview(block)
            while view:
                written = os.write(fd, view); assert written > 0
                view = view[written:]
        assert not sys.stdin.buffer.read(1), 'Oversized native stage stream'
        assert h.hexdigest() == entry['sha256'], 'Native stage SHA mismatch'
        assert metadata(original) == old, 'Original changed during stage'
        os.fchown(fd, old['uid'], old['gid']); os.fchmod(fd, old['mode'])
        for n in os.listxattr(fd):
            if n not in attrs:
                os.removexattr(fd, n)
        for n, value in attrs.items():
            os.setxattr(fd, n, value)
        os.utime(fd, ns=(old['mtimeNs'], old['mtimeNs'])); os.fsync(fd)
    finally:
        os.close(fd)
    parent = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)
    after = observe(request)
    assert identity(after) == identity(before)
    budget(after, request)
    return after
