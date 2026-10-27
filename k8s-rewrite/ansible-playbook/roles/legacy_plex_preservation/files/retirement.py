"""Run the exact retirement playbook while the Windows NAS guard holds locks."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
R = F / 'node-cleanup-20261027/worker2-legacy-plex-preservation'
REPO = Path('/mnt/c/Users/james/.codex/worktrees/cluster-maintenance-ansible/kubernetes migration')
PYTHON = '/home/brajam/.local/share/branconet-migration/venv/bin/python3.12'


def main():
    if sys.version_info[:2] != (3, 12):
        os.execv(PYTHON, [PYTHON, '-B', *sys.argv])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proof', type=Path, required=True)
    parser.add_argument('--remote-helper', type=Path, required=True)
    parser.add_argument('--safety-source', type=Path, required=True)
    parser.add_argument('--tree-profile', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--syntax-only', action='store_true')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    assert sum((args.apply, args.syntax_only, args.check_only)) == 1 and args.tree_profile == R / 'profile.json' and F.is_mount()
    for path in (args.proof, args.remote_helper, args.safety_source):
        assert path.resolve() == path and path.is_relative_to(R) and path.is_file()
    assert args.syntax_only or args.check_only or not (R / 'retirement-result.json').exists()
    os.umask(0o077)
    mode = 'syntax' if args.syntax_only else 'check' if args.check_only else 'ansible'
    scratch = R / ('retirement-' + mode + '-scratch')
    assert not scratch.exists()
    scratch.mkdir(mode=0o700)
    descriptor = os.open(scratch, os.O_RDONLY | os.O_DIRECTORY)
    fd = fcntl.fcntl(descriptor, fcntl.F_DUPFD, 200)
    os.close(descriptor)
    os.set_inheritable(fd, True)
    alias = '/proc/' + str(os.getpid()) + '/fd/' + str(fd)
    assert Path(alias).resolve() == scratch
    source = REPO / 'k8s-rewrite/ansible-playbook'
    os.environ.update(PYTHONDONTWRITEBYTECODE='1', ANSIBLE_CONFIG=str(source / 'ansible.cfg'),
                      ANSIBLE_ROLES_PATH=str(source / 'roles'), ANSIBLE_ACTION_PLUGINS=str(source / 'action_plugins'),
                      ANSIBLE_HOME=str(scratch / 'home'), ANSIBLE_LOCAL_TEMP=str(scratch / 'local'),
                      ANSIBLE_REMOTE_TEMP=str(scratch / 'remote'), TMPDIR=alias, TMP=alias, TEMP=alias,
                      ANSIBLE_SSH_CONTROL_PATH=alias + '/ssh-%%C',
                      ANSIBLE_SSH_ARGS='-o ControlMaster=no -o ControlPersist=no')
    primitives = {'__name__': 'retirement_privilege_input'}
    exec(compile((source / 'roles/legacy_plex_preservation/files/controller.py').read_bytes(), '<privilege-input>', 'exec'), primitives)
    from ansible.cli.playbook import PlaybookCLI
    password = None if args.syntax_only or args.check_only else primitives['privilege_input']().decode()
    variables = {'legacy_plex_live_proof': str(args.proof), 'legacy_plex_retire_helper': str(args.remote_helper),
                 'legacy_plex_retire_safety': str(args.safety_source), 'legacy_plex_retire_apply': True,
                 'ansible_ssh_private_key_file': '/home/brajam/.ssh/id_ed25519',
                 'ansible_ssh_common_args': '-o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/home/brajam/.ssh/known_hosts'}
    flags = ['--syntax-check'] if args.syntax_only else ['--check'] if args.check_only else []
    cli = PlaybookCLI(['ansible-playbook', *flags, '-i', str(source / 'inventory/production.ini'),
                       str(source / 'playbooks/legacy-plex-retirement.yml'), '-e', json.dumps(variables)])
    cli.ask_passwords = lambda: (None, password)
    result = {'status': 'started', 'removedEmptyDirectories': [], 'retained': []}
    try:
        result['exitCode'] = cli.run()
        result['status'] = 'completed' if result['exitCode'] == 0 else 'failed'
    finally:
        password = None
        # Ansible's multiprocessing listeners retain the inherited short path
        # until their finalizers run. Keep its descriptor alive through teardown.
        from multiprocessing.util import _exit_function
        _exit_function()
        os.close(fd)
        # Only empty directories created by this invocation qualify here.
        # Nonempty files are retained for full reference/provenance checks.
        for parent, dirs, files in os.walk(scratch, topdown=False):
            path = Path(parent)
            assert path.resolve() == path and path.is_relative_to(R)
            if files or any(path.iterdir()):
                result['retained'].append({'path': str(path), 'reason': 'nonempty Ansible output requires reconciliation'})
            else:
                allocated = path.stat().st_blocks * 512
                path.rmdir()
                result['removedEmptyDirectories'].append({'path': str(path), 'allocatedBytes': allocated})
        name = 'retirement-syntax-result.json' if args.syntax_only else 'retirement-check-result.json' if args.check_only else 'retirement-operator-result.json'
        with (R / name).open('x') as out:
            json.dump(result, out, indent=2)
    raise SystemExit(result['exitCode'])


if __name__ == '__main__':
    main()
