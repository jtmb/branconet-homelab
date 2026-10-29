"""Finite kernel202 package gate, no package or runtime mutations."""
import json
import os
import platform
import re
import subprocess
import sys

VERSION = '5.15.0-202.212'
META = '5.15.0.202.174'


def packages(host):
    result = {n: META for n in ['linux-generic', 'linux-image-generic', 'linux-headers-generic']}
    result.update({n: VERSION for n in ['linux-image-5.15.0-202-generic',
        'linux-modules-5.15.0-202-generic', 'linux-modules-extra-5.15.0-202-generic',
        'linux-headers-5.15.0-202', 'linux-headers-5.15.0-202-generic']})
    if host == 'masternode':
        result.update({n: VERSION for n in ['linux-modules-nvidia-390-generic',
            'linux-modules-nvidia-390-5.15.0-202-generic',
            'linux-objects-nvidia-390-5.15.0-202-generic',
            'linux-signatures-nvidia-5.15.0-202-generic']})
    return result


def run(args):
    r = subprocess.run(args, capture_output=True, text=True, timeout=90)
    if r.returncode:
        raise ValueError('Kernel qualification command failed: ' + args[0])
    return r.stdout.strip()


def main():
    import apt
    host = platform.node()
    assert host in ['masternode', 'workernode1', 'workernode2']
    wanted = packages(host)
    cache = apt.Cache(memonly=True)
    assert cache['linux-image-5.15.0-198-generic'].is_installed, 'Preserve installed198 fallback'
    assert not run(['dpkg', '--audit']), 'Existing dpkg failure'
    if host == 'masternode':
        assert '390.157' in open('/proc/driver/nvidia/version').read(), 'Original active390 module changed'
    if sys.argv[1] == 'preflight':
        peak = 256 * 1024**2
        for name, version in wanted.items():
            matches = [v for v in cache[name].versions if v.version == version]
            assert len(matches) == 1 and any(o.trusted and o.origin == 'Ubuntu'
                and o.archive in ['jammy-updates', 'jammy-security'] for o in matches[0].origins), name
            if not cache[name].is_installed or cache[name].installed.version != version:
                peak += matches[0].size + matches[0].installed_size
        fs = os.statvfs('/')
        assert fs.f_bavail * fs.f_frsize >= 15 * 1024**3 + peak, 'Kernel peak must preserve15GiB usable'
        assert fs.f_bfree * fs.f_frsize >= fs.f_blocks * fs.f_frsize // 4 + 1 + 512 * 1024**2 + peak, 'Kernel peak must preserve25percent plus512MiB'
        plan = run(['apt-get', '--simulate', '--no-remove', 'install'] + [n + '=' + v for n, v in wanted.items()])
        assert not re.search(r'^Remv ', plan, re.M)
        for line in plan.splitlines():
            if line.startswith('Inst '):
                match = re.match(r'Inst (\S+)(?: \[[^\]]+\])? \((\S+) ', line)
                assert match and wanted.get(match[1]) == match[2], 'Unexpected dependency transaction'
            elif line.startswith('Conf '):
                assert line.split()[1] in wanted, 'Unexpected configured package'
    else:
        assert sys.argv[1] == 'verify'
        assert all(cache[n].is_installed and cache[n].installed.version == v for n, v in wanted.items())
        if host == 'masternode':
            assert run(['modinfo', '-k', '5.15.0-202-generic', '-F', 'version', 'nvidia']) == '390.157'
    print(json.dumps({'passed': True, 'host': host, 'mode': sys.argv[1],
                      'packages': [n + '=' + v for n, v in wanted.items()], 'fallback198Retained': True}))


if __name__ == '__main__':
    main()
