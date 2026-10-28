"""Run exact master BuildKit inventory/retirement through bounded Ansible."""
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


def main():
    if sys.version_info[:2] != (3, 12):
        os.execv(PYTHON, [PYTHON, '-B', *sys.argv])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    phase = parser.add_mutually_exclusive_group(required=True)
    phase.add_argument('--syntax-only', action='store_true')
    phase.add_argument('--apply', action='store_true')
    phase.add_argument('--inventory', action='store_true')
    args = parser.parse_args()
    assert F.is_mount() and N.resolve() == N
    space = lambda p: os.statvfs(p).f_bavail * os.statvfs(p).f_frsize
    assert space('/mnt/c') >= 15 * 1024**3 and space(F) >= 15 * 1024**3 + 64 * 1024**2
    source = args.repository / 'k8s-rewrite/ansible-playbook'
    assert source.is_dir()
    helper = source / 'roles/retired_master_build_tools/files/retire.py'
    frozen = N / 'master-build-tools-retire.py'
    assert helper.read_bytes() == frozen.read_bytes()
    assert hashlib.sha256(helper.read_bytes()).hexdigest() == '09fbe87185c078f7e31e3501e502ae4600a00da77b892b940d09c3903250a92c'
    proof = json.loads((N / 'master-build-tools-controller-proof.json').read_text())
    for row in proof['primaryTools']:
        with Path(row['path']).open('rb') as original:
            digest = hashlib.sha256()
            for chunk in iter(lambda: original.read(1024**2), b''):
                digest.update(chunk)
        assert digest.hexdigest() == row['sha256']
    if args.apply:
        previous = json.loads((N / 'master-build-tools-inventory.json').read_text())
        assert previous['rc'] == 0 and not json.loads(previous['stdout'])['applied']
    mode = 'syntax' if args.syntax_only else 'inventory' if args.inventory else 'ansible'
    receipt = N / ('build-tools-' + mode + '-operator.json')
    scratch = N / ('build-tools-' + mode + '-scratch')
    assert not receipt.exists() and not scratch.exists()
    if args.apply:
        assert not (N / 'master-build-tools-retirement.json').exists()
    os.umask(0o077)
    scratch.mkdir(mode=0o700)
    descriptor = os.open(scratch, os.O_RDONLY | os.O_DIRECTORY)
    fd = fcntl.fcntl(descriptor, fcntl.F_DUPFD, 200)
    os.close(descriptor)
    os.set_inheritable(fd, True)
    alias = '/proc/' + str(os.getpid()) + '/fd/' + str(fd)
    assert Path(alias).resolve() == scratch
    os.environ.update(PYTHONDONTWRITEBYTECODE='1', ANSIBLE_CONFIG=str(source / 'ansible.cfg'),
                      ANSIBLE_ACTION_PLUGINS=str(source / 'action_plugins'),
                      ANSIBLE_ROLES_PATH=str(source / 'roles'), ANSIBLE_HOME=str(scratch / 'home'),
                      ANSIBLE_LOCAL_TEMP=str(scratch / 'local'), ANSIBLE_REMOTE_TEMP=str(scratch / 'remote'),
                      TMPDIR=alias, TMP=alias, TEMP=alias, ANSIBLE_SSH_CONTROL_PATH=alias + '/ssh-%%C',
                      ANSIBLE_SSH_ARGS='-o ControlMaster=no -o ControlPersist=no')
    primitives = {'__name__': 'master_retirement_privilege_input'}
    exec(compile((source / 'roles/legacy_plex_preservation/files/controller.py').read_bytes(),
                 '<protected-privilege-input>', 'exec'), primitives)
    from ansible.cli.playbook import PlaybookCLI
    password = None if args.syntax_only else primitives['privilege_input']().decode()
    variables = {'retired_master_build_tools_apply': args.apply,
                 'retired_master_build_tools_receipt': str(N / ('master-build-tools-' + ('retirement' if args.apply else 'inventory') + '.json')),
                 'ansible_ssh_private_key_file': '/home/brajam/.ssh/id_ed25519',
                 'ansible_ssh_common_args': '-o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/home/brajam/.ssh/known_hosts'}
    flags = ['--syntax-check'] if args.syntax_only else []
    cli = PlaybookCLI(['ansible-playbook', *flags, '-i', str(source / 'inventory/production.ini'),
                       str(source / 'playbooks/retired-master-build-tools.yml'), '-e', json.dumps(variables)])
    cli.ask_passwords = lambda: (None, password)
    result = {'status': 'started', 'removedEmptyDirectories': [], 'retained': [],
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    try:
        result['exitCode'] = cli.run()
        result['status'] = 'completed' if result['exitCode'] == 0 else 'failed'
    finally:
        password = None
        from multiprocessing.util import _exit_function
        _exit_function()
        os.close(fd)
        for parent, dirs, files in os.walk(scratch, topdown=False):
            path = Path(parent)
            assert path.resolve() == path and path.is_relative_to(N)
            if files or any(path.iterdir()):
                result['retained'].append({'path': str(path), 'reason': 'nonempty owned output requires qualification'})
            else:
                allocated = path.stat().st_blocks * 512
                path.rmdir()
                result['removedEmptyDirectories'].append({'path': str(path), 'allocatedBytes': allocated})
        with receipt.open('x') as out:
            json.dump(result, out, indent=2)
    raise SystemExit(result['exitCode'])


if __name__ == '__main__':
    main()
