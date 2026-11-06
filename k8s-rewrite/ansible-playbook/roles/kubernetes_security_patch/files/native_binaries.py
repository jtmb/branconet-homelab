"""Preserve native installation ownership; bounded same-filesystem atomic swaps."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys

NAMES = ['kubeadm', 'kubelet', 'kubectl']


def run(args):
    r = subprocess.run(args, capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise ValueError('Native binary qualification failed: ' + args[0])
    return r.stdout.strip()


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def metadata(path):
    s = path.lstat()
    assert path.resolve() == path and stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'Original native binary path/ownership changed'
    digest = file_sha(path)
    attrs = {n: os.getxattr(path, n).hex() for n in sorted(os.listxattr(path))}
    return {'path': str(path), 'sha256': digest, 'bytes': s.st_size, 'mode': stat.S_IMODE(s.st_mode),
            'uid': s.st_uid, 'gid': s.st_gid, 'mtimeNs': s.st_mtime_ns,
            'xattrsSHA256': hashlib.sha256(json.dumps(attrs, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}


def go_version(path):
    # Go1.18+ inline buildinfo: magic14, pointer-size1, flags1, header32,
    # then varint-length UTF-8 toolchain string. No compiler/runtime install.
    with path.open('rb') as f:
        data = f.read()
    offset = -1
    while True:
        offset = data.find(b'\xff Go buildinf:', offset + 1)
        assert offset >= 0, 'Modern native Go buildinfo missing'
        if offset % 16 or offset + 33 >= len(data) or data[offset + 14] != 8 or not data[offset + 15] & 2:
            continue
        pos = offset + 32; size = 0; shift = 0
        for _ in range(10):
            b = data[pos]; pos += 1; size |= (b & 127) << shift
            if b < 128:
                break
            shift += 7
        if 0 < size < 128 and data[pos:pos + size].startswith(b'go1.'):
            return data[pos:pos + size].decode()


def same_metadata(actual, original):
    return all(actual[k] == original[k] for k in ['mode', 'uid', 'gid', 'mtimeNs', 'xattrsSHA256'])


def check_state(plan, mode):
    host = platform.node()
    if mode == 'staged-kubeadm':
        assert host == 'masternode', 'Transfer resume is master-only'
    assert host in plan['nodeUIDs'] and os.geteuid() == 0
    assert Path('/usr/local/bin').resolve() == Path('/usr/local/bin')
    directory = Path('/usr/local/bin').stat()
    assert directory.st_uid == 0 and not stat.S_IMODE(directory.st_mode) & 0o022
    assert all(shutil.which(n) == '/usr/local/bin/' + n for n in NAMES), 'Native command resolution changed'
    assert run(['/opt/containerd-k8s/bin/containerd', '--version']).split()[2] == 'v2.4.2'
    holds = sorted(run(['apt-mark', 'showhold']).splitlines())
    # No package state changes, package ownership takeover, repo edits or deps.
    installed = subprocess.run(['dpkg-query', '-W', '-f=${binary:Package}\n', *NAMES], capture_output=True, text=True)
    assert not installed.stdout.strip(), 'Do not cross native/package ownership boundaries'
    current = {}; peak = 128 * 1024**2
    for name in NAMES:
        entry = plan['binaries'][name]; target = Path('/usr/local/bin') / name
        original = entry['originalByNode'][host]
        actual = metadata(target); current[name] = actual
        assert original['path'] == str(target) and same_metadata(actual, original)
        if mode == 'staged-kubeadm':
            allowed = [entry['sha256']] if name == 'kubeadm' else [original['sha256']]
        else:
            allowed = [original['sha256']] if mode == 'staged' else [original['sha256'], entry['sha256']]
        assert actual['sha256'] in allowed, 'Installed native bytes differ from original/qualified target'
        if mode == 'staged-kubeadm' and name == 'kubeadm':
            assert actual['sha256'] == entry['sha256'] and actual['bytes'] == entry['bytes']
            assert go_version(target) == 'go1.26.10'
            consumed = Path(entry['verifiedStaging'][host]['path'])
            assert str(consumed) == '/usr/local/bin/.kubernetes1372-kubeadm-' + entry['sha256'] + '.new'
            assert not consumed.exists() and not consumed.is_symlink(), 'Consumed kubeadm stage must be absent'
        if mode == 'verify':
            assert actual['sha256'] == entry['sha256'] and actual['bytes'] == entry['bytes']
            assert go_version(target) == 'go1.26.10'
        elif actual['sha256'] != entry['sha256']:
            stage = Path(entry['verifiedStaging'][host]['path'])
            assert str(stage) == '/usr/local/bin/.kubernetes1372-' + name + '-' + entry['sha256'] + '.new'
            staged = metadata(stage)
            assert staged['sha256'] == entry['sha256'] and staged['bytes'] == entry['bytes'] and same_metadata(staged, original)
            assert stage.stat().st_dev == target.stat().st_dev, 'Atomic replacement must stay on original filesystem'
            assert go_version(stage) == 'go1.26.10'
            peak += entry['bytes'] + original['bytes']
    st = os.statvfs('/usr/local/bin')
    assert st.f_bavail * st.f_frsize >= 15 * 1024**3 + peak, 'Preserve15GiB available plus native binary peak'
    assert st.f_bfree * st.f_frsize >= st.f_blocks * st.f_frsize // 4 + 1 + 512 * 1024**2 + peak, 'Preserve25percent plus512MiB and native peak'
    return host, holds, current


def main():
    mode = sys.argv[1]
    if mode == 'capture':
        print(json.dumps({'host': platform.node(), 'binaries': {n: metadata(Path('/usr/local/bin') / n) for n in NAMES},
                          'kubeletUnit': run(['systemctl', 'show', 'kubelet', '--property=FragmentPath', '--value']),
                          'holds': sorted(run(['apt-mark', 'showhold']).splitlines()), 'mutationPerformed': False}, indent=2))
        return
    assert mode in ['staged', 'staged-kubeadm', 'install-kubeadm', 'install-node', 'verify']
    plan = json.load(sys.stdin)
    host, holds, before = check_state(plan, mode)
    if mode.startswith('install-'):
        names = ['kubeadm'] if mode == 'install-kubeadm' else ['kubelet', 'kubectl']
        for name in names:
            entry = plan['binaries'][name]; target = Path('/usr/local/bin') / name
            # Independent controller authority has rehashed the original raw
            # backup. Recheck original live bytes immediately before rename.
            assert metadata(target) == before[name]
            if before[name]['sha256'] == entry['sha256']:
                continue
            assert before[name]['sha256'] == entry['originalByNode'][host]['sha256']
            stage = Path(entry['verifiedStaging'][host]['path'])
            staged = metadata(stage)
            assert staged['sha256'] == entry['sha256'] and staged['bytes'] == entry['bytes']
            assert same_metadata(staged, before[name])
            with stage.open('rb') as f:
                os.fsync(f.fileno())
            os.replace(stage, target)
            fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            after = metadata(target)
            assert after['sha256'] == entry['sha256'] and same_metadata(after, before[name])
    assert sorted(run(['apt-mark', 'showhold']).splitlines()) == holds
    if mode == 'verify':
        assert json.loads(run(['/usr/local/bin/kubeadm', 'version', '-o', 'json']))['clientVersion']['gitVersion'] == 'v1.37.2'
        assert run(['/usr/local/bin/kubelet', '--version']) == 'Kubernetes v1.37.2'
        assert json.loads(run(['/usr/local/bin/kubectl', 'version', '--client', '-o', 'json']))['clientVersion']['gitVersion'] == 'v1.37.2'
        pid = run(['systemctl', 'show', 'kubelet', '--property=MainPID', '--value'])
        assert pid.isdigit() and int(pid) > 1
        exe = Path('/proc') / pid / 'exe'
        assert os.readlink(exe) == '/usr/local/bin/kubelet', 'Running kubelet still uses an old/deleted executable'
        assert file_sha(exe) == plan['binaries']['kubelet']['sha256']
    print(json.dumps({'passed': True, 'mode': mode, 'host': host, 'holds': holds, 'before': before,
                      'ownership': 'unchanged-native-usr-local-bin', 'packageMutations': False}))


if __name__ == '__main__':
    main()
