"""Run one fixed-node closed-journal Ansible operation with protected TTY input."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
REPOSITORY = Path('/mnt/c/Users/james/.codex/worktrees/cluster-maintenance-ansible/kubernetes migration')
PYTHON = '/home/brajam/.local/share/branconet-migration/venv/bin/python3.12'


def main():
    if sys.version_info[:2] != (3, 12):
        os.execv(PYTHON, [PYTHON, '-B', *sys.argv])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', choices=['masternode', 'workernode2'], default='masternode')
    parser.add_argument('--syntax-only', action='store_true')
    parser.add_argument('--proof', type=Path)
    parser.add_argument('--journal-profile', type=Path)
    parser.add_argument('--remote-helper', type=Path, required=True)
    parser.add_argument('--safety-source', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.journal_profile:
        node = json.loads(args.journal_profile.read_text()).get('node', 'workernode2')
        assert node in ('masternode', 'workernode2')
    else:
        node = args.node
    run = F / 'node-cleanup-20261027' / (('master' if node == 'masternode' else 'worker2') + '-journal-offload-20261027')
    assert F.is_mount() and run.resolve() == run and run.is_dir()
    for path in (F, Path('/mnt/c')):
        space = os.statvfs(path)
        assert space.f_bavail * space.f_frsize >= 15 * 1024**3 + 32 * 1024**2
    source = REPOSITORY / 'k8s-rewrite/ansible-playbook'
    helper = source / 'roles/archived_journal_offload/files/journal.py'
    safety = source / 'roles/retired_master_build_tools/files/retire.py'
    assert args.remote_helper.resolve() == run / 'journal-frozen.py'
    assert args.safety_source.resolve() == run / 'safety-frozen.py'
    assert helper.read_bytes() == args.remote_helper.read_bytes()
    assert safety.read_bytes() == args.safety_source.read_bytes()
    retirement = bool(args.proof)
    assert not args.apply or retirement
    if retirement:
        assert not args.syntax_only and args.journal_profile == run / 'profile.json'
        assert args.proof.parent == run and re.fullmatch('nas-retirement-proof-[0-9a-f]{32}[.]json', args.proof.name)
        proof = json.loads(args.proof.read_text())
        assert proof['nasReadLocksHeld'] and proof['independentRestoreVerified']
        assert proof['nativePID'] > 0
        token = proof['token']
        assert re.fullmatch('[0-9a-f]{32}', token)
        phase = 'retirement-' + token
    else:
        assert args.journal_profile is None
        phase = 'syntax' if args.syntax_only else 'inventory'
    receipt = run / (phase + '-operator.json')
    returned = run / ('retirement-result-' + token + '.json' if retirement else 'inventory-result.json')
    scratch = run / (phase + '-ansible-scratch')
    assert not receipt.exists() and not scratch.exists() and (args.syntax_only or not returned.exists())
    os.umask(0o077)
    scratch.mkdir(mode=0o700)
    descriptor = os.open(scratch, os.O_RDONLY | os.O_DIRECTORY)
    fd = fcntl.fcntl(descriptor, fcntl.F_DUPFD, 200)
    os.close(descriptor)
    os.set_inheritable(fd, True)
    alias = '/proc/' + str(os.getpid()) + '/fd/' + str(fd)
    assert Path(alias).resolve() == scratch
    os.environ.update(PYTHONDONTWRITEBYTECODE='1', ANSIBLE_CONFIG=str(source / 'ansible.cfg'),
                      ANSIBLE_ROLES_PATH=str(source / 'roles'), ANSIBLE_HOME=str(scratch / 'home'),
                      ANSIBLE_LOCAL_TEMP=str(scratch / 'local'), ANSIBLE_REMOTE_TEMP=str(scratch / 'remote'),
                      TMPDIR=alias, TMP=alias, TEMP=alias, ANSIBLE_SSH_CONTROL_PATH=alias + '/ssh-%%C',
                      ANSIBLE_SSH_ARGS='-o ControlMaster=no -o ControlPersist=no')
    from ansible.cli.playbook import PlaybookCLI
    primitives = {'__name__': 'protected_journal_privilege_input'}
    exec(compile((source / 'roles/legacy_plex_preservation/files/controller.py').read_bytes(),
                 '<protected-privilege-input>', 'exec'), primitives)
    password = None if args.syntax_only else primitives['privilege_input']().decode()
    variables = {'archived_journal_offload_node': node,
                 'archived_journal_offload_mode': 'retire' if retirement else 'inventory',
                 'archived_journal_offload_apply': args.apply,
                 'archived_journal_offload_operator_holds_nas_lock': retirement,
                 'archived_journal_offload_selection_file': str(run / 'selection.json'),
                 'archived_journal_offload_profile_file': str(run / 'profile.json'),
                 'archived_journal_offload_proof_file': str(args.proof) if retirement else '',
                 'archived_journal_offload_result_file': str(returned),
                 'ansible_ssh_private_key_file': '/home/brajam/.ssh/id_ed25519',
                 'ansible_ssh_common_args': '-o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/home/brajam/.ssh/known_hosts'}
    cli = PlaybookCLI(['ansible-playbook', *(['--syntax-check'] if args.syntax_only else []),
                       '-i', str(source / 'inventory/production.ini'),
                       str(source / 'playbooks/archived-journal-offload.yml'), '-e', json.dumps(variables)])
    cli.ask_passwords = lambda: (None, password)
    result = {'status': 'started', 'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'helperSHA256': hashlib.sha256(helper.read_bytes()).hexdigest(),
              'safetySHA256': hashlib.sha256(safety.read_bytes()).hexdigest(),
              'scratchRequiresInactiveReconciliation': str(scratch)}
    try:
        result['exitCode'] = cli.run()
        result['status'] = 'completed' if result['exitCode'] == 0 else 'failed'
    finally:
        password = None
        from multiprocessing.util import _exit_function
        _exit_function()
        os.close(fd)
        with receipt.open('x') as out:
            json.dump(result, out, indent=2)
    raise SystemExit(result['exitCode'])


if __name__ == '__main__':
    main()
