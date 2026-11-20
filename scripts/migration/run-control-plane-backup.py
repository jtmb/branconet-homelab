#!/usr/bin/env python3
"""Launch only the separate maintenance control-plane backup; sudo JSON on stdin."""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings-file', type=pathlib.Path)
    parser.add_argument('--syntax-check', action='store_true')
    args = parser.parse_args()
    repo = pathlib.Path(__file__).resolve().parents[2]
    ansible = repo / 'k8s-rewrite/ansible-playbook'
    runtime = pathlib.Path('/home/brajam/.local/share/branconet-migration')
    env = dict(os.environ, ANSIBLE_CONFIG=str(ansible / 'ansible.cfg'), ANSIBLE_NOCOLOR='1')
    env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    command = [str(runtime / 'venv/bin/ansible-playbook'), 'playbooks/control-plane-backup.yml']
    if args.syntax_check:
        return subprocess.run(command + ['--syntax-check'], cwd=ansible, env=env).returncode
    if not args.settings_file or args.settings_file.stat().st_size > 65536:
        raise ValueError()
    settings = json.loads(args.settings_file.read_text())
    allowed = {'control_plane_backup_apply', 'control_plane_backup_output_dir', 'control_plane_backup_recipient_file', 'control_plane_backup_identity_file', 'control_plane_backup_age_binary', 'control_plane_backup_etcd_image', 'control_plane_backup_etcd_digest'}
    if not isinstance(settings, dict) or set(settings) - allowed or settings.get('control_plane_backup_apply') is not True:
        raise ValueError()
    output = pathlib.Path(settings.get('control_plane_backup_output_dir', ''))
    if not output.is_absolute() or not str(output).startswith('/home/brajam/') or output.resolve() != output or output == repo or repo in output.parents:
        raise ValueError()
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = output.lstat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError()
    request = json.loads(sys.stdin.buffer.read(65537))
    if not isinstance(request, dict) or set(request) != {'sudo_password'} or not isinstance(request['sudo_password'], str) or not request['sudo_password']:
        raise ValueError()
    env['BRANCONET_MIGRATION_SUDO_PASSWORD'] = request.pop('sudo_password')
    log = output / ('control-plane-launch-' + uuid.uuid4().hex + '.log')
    command += ['--extra-vars', json.dumps(settings)]
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        child = subprocess.Popen(command, cwd=ansible, env=env, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
        env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
        code = child.wait()
    print(json.dumps({'exit_code': code, 'operator_log': str(log), 'backup_parent': str(output)}))
    return code


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('Control-plane backup launcher refused invalid inputs; no request or credential diagnostics are emitted')