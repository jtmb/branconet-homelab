"""Run one fixed detached-claim checkpoint phase through maintained Ansible."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
R = F / 'platform-upstream-review-20261027/detached-volume-backups-20261027'
S = Path('/mnt/c/Users/james/.codex/worktrees/cluster-maintenance-ansible/kubernetes migration/k8s-rewrite/ansible-playbook')
PYTHON = '/home/brajam/.local/share/branconet-migration/venv/bin/python3.12'


def main():
    if sys.version_info[:2] != (3, 12):
        os.execv(PYTHON, [PYTHON, '-B', *sys.argv])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['prepare', 'apply', 'observe'], required=True)
    parser.add_argument('--volume', choices=['storage-proof', 'storage-restored', 'nas-bortus-restore',
                        'bortus-restore', 'pihole-old-0', 'pihole-old-1', 'gluetun-old', 'qbittorrent-old',
                        'ruckus-old', 'wordpress-unused'], required=True)
    args = parser.parse_args()
    assert os.geteuid() == 1000 and F.is_mount() and R.resolve() == R
    bindings = json.loads((R / 'source-binding.json').read_text())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in bindings['sources'].items())
    for path in (F, Path('/mnt/c')):
        s = os.statvfs(path)
        assert s.f_bavail * s.f_frsize >= 15 * 1024**3 + 64 * 1024**2
    prefix = 'ansible-' + args.volume + '-' + args.phase
    receipt, scratch = R / (prefix + '.json'), R / (prefix + '-scratch')
    assert not receipt.exists() and not scratch.exists()
    os.umask(0o077)
    scratch.mkdir(mode=0o700)
    descriptor = os.open(scratch, os.O_RDONLY | os.O_DIRECTORY)
    fd = fcntl.fcntl(descriptor, fcntl.F_DUPFD, 200)
    os.close(descriptor)
    os.set_inheritable(fd, True)
    alias = '/proc/' + str(os.getpid()) + '/fd/' + str(fd)
    assert Path(alias).resolve() == scratch
    os.environ.update(PYTHONDONTWRITEBYTECODE='1', ANSIBLE_CONFIG=str(S / 'ansible.cfg'),
                      ANSIBLE_ROLES_PATH=str(S / 'roles'), ANSIBLE_ACTION_PLUGINS=str(S / 'action_plugins'),
                      ANSIBLE_HOME=str(scratch / 'home'), ANSIBLE_LOCAL_TEMP=str(scratch / 'local'),
                      ANSIBLE_REMOTE_TEMP=str(scratch / 'remote'), TMPDIR=alias, TMP=alias, TEMP=alias,
                      ANSIBLE_SSH_CONTROL_PATH=alias + '/ssh-%%C', ANSIBLE_SSH_ARGS='-o ControlMaster=no -o ControlPersist=no')
    from ansible.cli.playbook import PlaybookCLI
    cli = PlaybookCLI(['ansible-playbook', '-i', str(S / 'inventory/production.ini'),
                       str(S / 'playbooks/detached-storage-checkpoint.yml'), '-e', json.dumps({
                           'detached_storage_checkpoint_enabled': True,
                           'detached_storage_checkpoint_phase': args.phase,
                           'detached_storage_checkpoint_volume': args.volume})])
    result = {'status': 'started', 'phase': args.phase, 'volume': args.volume,
              'sources': bindings['sources'], 'scratchRequiresIndependentInactiveReconciliation': str(scratch)}
    try:
        result['exitCode'] = cli.run()
        result['status'] = 'completed' if result['exitCode'] == 0 else 'failed'
    finally:
        from multiprocessing.util import _exit_function
        _exit_function()
        os.close(fd)
        result['sourceUnchanged'] = all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in bindings['sources'].items())
        with receipt.open('x') as out:
            json.dump(result, out, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != 'sources'}))
    raise SystemExit(result['exitCode'])


if __name__ == '__main__':
    main()
