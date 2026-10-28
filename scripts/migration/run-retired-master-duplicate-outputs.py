"""Run fixed old master duplicate qualification through the existing Ansible path."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
N = F / 'node-cleanup-20261027/master-generated-cleanup'
PYTHON = '/home/brajam/.local/share/branconet-migration/venv/bin/python3.12'


def sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def main():
    if sys.version_info[:2] != (3, 12):
        os.execv(PYTHON, [PYTHON, '-B', *sys.argv])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--syntax-only', action='store_true')
    mode.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    assert os.geteuid() == 1000 and F.is_mount() and N.resolve() == N
    for path in (F, Path('/mnt/c')):
        s = os.statvfs(path)
        assert s.f_bavail * s.f_frsize >= 15 * 1024**3 + 128 * 1024**2
    source = args.repository / 'k8s-rewrite/ansible-playbook'
    binding = json.loads((N / 'custom-kubectl-duplicate-source-binding.json').read_text())
    assert all(sha(Path(p)) == h for p, h in binding['sources'].items())
    helper = source / 'roles/retired_master_duplicate_outputs/files/retire.py'
    assert helper.read_bytes() == (N / 'custom-kubectl-duplicate-retire-frozen.py').read_bytes()
    proof = json.loads((N / 'custom-kubectl-duplicate-rollback-proof.json').read_text())
    assert proof['fullIndependentReadbackPassed'] and proof['primary']['path'] == str(N / 'rollback-custom-kubectl.elf')
    assert sha(N / 'rollback-custom-kubectl.elf') == proof['primary']['sha256']
    mode = 'syntax' if args.syntax_only else 'apply' if args.apply else 'inspect'
    receipt = N / ('custom-kubectl-duplicate-' + mode + '-operator.json')
    scratch = N / ('custom-kubectl-duplicate-' + mode + '-scratch')
    assert not receipt.exists() and not scratch.exists()
    os.umask(0o077)
    scratch.mkdir(mode=0o700)
    descriptor = os.open(scratch, os.O_RDONLY | os.O_DIRECTORY)
    fd = fcntl.fcntl(descriptor, fcntl.F_DUPFD, 200)
    os.close(descriptor)
    os.set_inheritable(fd, True)
    alias = '/proc/' + str(os.getpid()) + '/fd/' + str(fd)
    assert Path(alias).resolve() == scratch
    os.environ.update(PYTHONDONTWRITEBYTECODE='1', ANSIBLE_CONFIG=str(source / 'ansible.cfg'),
                      ANSIBLE_ACTION_PLUGINS=str(source / 'action_plugins'), ANSIBLE_ROLES_PATH=str(source / 'roles'),
                      ANSIBLE_HOME=str(scratch / 'home'), ANSIBLE_LOCAL_TEMP=str(scratch / 'local'),
                      ANSIBLE_REMOTE_TEMP=str(scratch / 'remote'), TMPDIR=alias, TMP=alias, TEMP=alias,
                      ANSIBLE_SSH_CONTROL_PATH=alias + '/ssh-%%C', ANSIBLE_SSH_ARGS='-o ControlMaster=no -o ControlPersist=no')
    primitives = {'__name__': 'existing_privilege_input'}
    exec(compile((source / 'roles/legacy_plex_preservation/files/controller.py').read_bytes(),
                 '<protected-privilege-input>', 'exec'), primitives)
    password = None if args.syntax_only else primitives['privilege_input']().decode()
    from ansible.cli.playbook import PlaybookCLI
    flags = ['--syntax-check'] if args.syntax_only else []
    variables = {'retired_master_duplicate_outputs_apply': args.apply,
                 'ansible_ssh_private_key_file': '/home/brajam/.ssh/id_ed25519',
                 'ansible_ssh_common_args': '-o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/home/brajam/.ssh/known_hosts'}
    cli = PlaybookCLI(['ansible-playbook', *flags, '-i', str(source / 'inventory/production.ini'),
                       str(source / 'playbooks/retired-master-duplicate-outputs.yml'), '-e', json.dumps(variables)])
    cli.ask_passwords = lambda: (None, password)
    result = {'status': 'started', 'sourceBinding': binding, 'scratch': str(scratch),
              'scratchRequiresIndependentInactiveReferenceReconciliation': True}
    try:
        result['exitCode'] = cli.run()
        result['status'] = 'completed' if result['exitCode'] == 0 else 'failed'
    finally:
        password = None
        from multiprocessing.util import _exit_function
        _exit_function()
        os.close(fd)
        result['sourceUnchanged'] = all(sha(Path(p)) == h for p, h in binding['sources'].items())
        with receipt.open('x') as out:
            json.dump(result, out, indent=2)
    raise SystemExit(result['exitCode'])


if __name__ == '__main__':
    main()
