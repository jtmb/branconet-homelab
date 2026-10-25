#!/usr/bin/env python3
"""Launch only the separate MeTube preservation playbook; no credentials required."""
import argparse
import json
import os
import pathlib
import subprocess
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings-file', type=pathlib.Path)
    parser.add_argument('--syntax-check', action='store_true')
    args = parser.parse_args()
    repo = pathlib.Path(__file__).resolve().parents[2]; ansible = repo / 'k8s-rewrite/ansible-playbook'
    env = dict(os.environ, ANSIBLE_CONFIG=str(ansible / 'ansible.cfg'), ANSIBLE_NOCOLOR='1')
    env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    command = ['/home/brajam/.local/share/branconet-migration/venv/bin/ansible-playbook', 'playbooks/metube-state-backup.yml']
    if args.syntax_check:
        return subprocess.run(command + ['--syntax-check'], cwd=ansible, env=env).returncode
    if not args.settings_file or args.settings_file.stat().st_size > 65536:
        raise ValueError()
    settings = json.loads(args.settings_file.read_text())
    allowed = {'metube_state_apply', 'metube_state_phase', 'metube_state_snapshot_profile', 'metube_state_output_dir', 'metube_state_baseline_receipt', 'metube_state_baseline_sha256', 'metube_state_expected_writer_image', 'metube_state_backup_node'}
    if not isinstance(settings, dict) or set(settings) - allowed or settings.get('metube_state_apply') is not True:
        raise ValueError()
    output = pathlib.Path(settings.get('metube_state_output_dir', ''))
    if not output.is_absolute() or not str(output).startswith('/home/brajam/') or output.resolve() != output or output == repo or repo in output.parents:
        raise ValueError()
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = output.lstat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError()
    log = output / ('metube-preservation-launch-' + uuid.uuid4().hex + '.log')
    command += ['--extra-vars', json.dumps(settings)]
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        result = subprocess.run(command, cwd=ansible, env=env, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
    print(json.dumps({'exit_code': result.returncode, 'operator_log': str(log), 'output_parent': str(output)}))
    return result.returncode


if __name__ == '__main__':
    try:raise SystemExit(main())
    except Exception:raise SystemExit('MeTube preservation launcher refused invalid inputs; no settings or credentials are emitted')
