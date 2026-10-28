"""Temporary GitHub resolution in the dedicated charts publisher only.

Windows Python entrypoint. Keep Windows/global DNS, credentials, TLS trust and
the original shared chart checkout unchanged. Restore the exact dedicated-clone
config after Pi-hole's normal resolver is healthy again.
"""
import argparse
import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import subprocess

GIT = 'C:/Program Files/Git/cmd/git.exe'
CI = Path('C:/Users/james/.codex/local-ci/branconet-charts-local-ci')
OUT = Path('//wsl.localhost/Ubuntu/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/platform-upstream-review-20261027/longhorn-remaining-runtime-20261028')
ORIGIN = 'https://github.com/jtmb/branconet-charts.git'


def git(*args):
    env = {k: v for k, v in os.environ.items() if not k.startswith(('GIT_', 'GH_', 'GITHUB_'))}
    env.update(GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
    p = subprocess.run([GIT, '-C', str(CI), *args], capture_output=True, env=env, timeout=45)
    assert p.returncode == 0 and len(p.stdout) <= 1048576, ('scoped_git_operation_failed', p.returncode)
    return p.stdout


def save(name, value):
    with (OUT / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['begin', 'end'])
    phase = parser.parse_args().phase
    assert os.name == 'nt' and (OUT / 'ownership.json').is_file()
    assert git('remote', 'get-url', 'origin').decode().strip() == ORIGIN
    assert git('branch', '--show-current').decode().strip() == 'main'
    assert not git('status', '--porcelain')
    cfg = CI / '.git/config'
    assert cfg.is_file() and not cfg.is_symlink()
    if phase == 'begin':
        assert not (OUT / 'dns-window-intent.json').exists()
        keys = set(git('config', '--local', '--name-only', '--list').decode().splitlines())
        assert keys <= {'core.repositoryformatversion', 'core.filemode', 'core.bare', 'core.logallrefupdates',
            'core.symlinks', 'core.ignorecase', 'remote.origin.url', 'remote.origin.fetch',
            'branch.main.remote', 'branch.main.merge'}, 'nonpublic_or_unreviewed_local_config'
        original = cfg.read_bytes()
        ips = sorted({x[4][0] for x in socket.getaddrinfo('github.com', 443, socket.AF_INET)})
        assert ips and all(ipaddress.ip_address(x).is_global for x in ips)
        resolution = 'github.com:443:' + ','.join(ips)
        # Qualify the hostname-specific override with normal TLS and the existing
        # credential helper; neither its credentials nor protocol trace is saved.
        remote = git('-c', 'http.sslVerify=true', '-c', 'http.curloptResolve=' + resolution,
            'ls-remote', 'origin', 'refs/heads/main', 'refs/heads/validated').decode().splitlines()
        intent = {'resolution': resolution, 'originalConfigBase64': base64.b64encode(original).decode(),
            'originalConfigSHA256': hashlib.sha256(original).hexdigest(), 'originalKeys': sorted(keys),
            'origin': ORIGIN, 'remoteRefs': remote, 'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'globalWindowsDNSChanged': False, 'credentialsOrTLSVerificationRelaxed': False}
        save('dns-window-intent.json', intent)
        git('config', '--local', '--add', 'http.curloptResolve', resolution)
        git('config', '--local', 'http.sslVerify', 'true')
        assert git('config', '--local', '--get-all', 'http.curloptResolve').decode().strip() == resolution
        assert git('config', '--local', '--get', 'http.sslVerify').decode().strip() == 'true'
        intent.update(installed=True, installedConfigSHA256=hashlib.sha256(cfg.read_bytes()).hexdigest())
        save('dns-window.json', intent)
        print(json.dumps({'installed': True, 'scope': str(CI), 'resolution': resolution, 'TLSVerification': True}))
        return
    state = json.loads((OUT / 'dns-window.json').read_text())
    assert not (OUT / 'dns-window-restored.json').exists()
    # Restore only after the workload cycle and the original DNS resolver work.
    assert (OUT / 'acceptance.json').is_file()
    assert socket.getaddrinfo('github.com', 443) and socket.getaddrinfo('homepage.branconet.lan', 443)
    assert hashlib.sha256(cfg.read_bytes()).hexdigest() == state['installedConfigSHA256'], 'concurrent_config_change_preserve'
    original = base64.b64decode(state['originalConfigBase64'], validate=True)
    assert hashlib.sha256(original).hexdigest() == state['originalConfigSHA256']
    assert cfg.write_bytes(original) == len(original)
    assert cfg.read_bytes() == original
    refs = git('ls-remote', 'origin', 'refs/heads/main', 'refs/heads/validated').decode().splitlines()
    save('dns-window-restored.json', {'exactOriginalConfigRestored': True, 'normalResolverGitVerified': True,
        'remoteRefs': refs, 'WindowsOrGlobalDNSChanged': False, 'credentialsChanged': False})
    print(json.dumps({'exactOriginalConfigRestored': True, 'normalResolverGitVerified': True}))


if __name__ == '__main__':
    main()
