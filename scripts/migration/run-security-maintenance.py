#!/usr/bin/env python3
"""Launch only the reviewed maintenance/checkpoint playbooks; credentials via stdin."""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import signal
import subprocess
import sys
import uuid

ALLOWED_SETTINGS = {
    'security-maintenance': {
        'security_maintenance_apply', 'security_maintenance_backup_verified',
        'security_maintenance_backup_reference', 'security_maintenance_reboot',
        'security_maintenance_expected_kernel', 'security_maintenance_ubuntu_packages',
        'security_maintenance_extra_packages', 'security_maintenance_extra_packages_by_host',
        'security_maintenance_allow_reviewed_emptydir', 'security_maintenance_emptydir_allowlist',
        'security_maintenance_retire_unused_containerd',
    },
    'storage-checkpoint': {
        'storage_checkpoint_apply', 'storage_checkpoint_prefix',
        'storage_checkpoint_receipt_path', 'storage_checkpoint_backup_target',
    },
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_settings(path, playbook):
    if path.stat().st_size > 65536:
        raise ValueError('Settings file is too large')
    settings = json.loads(path.read_text())
    if not isinstance(settings, dict) or set(settings) - ALLOWED_SETTINGS[playbook]:
        raise ValueError('Only documented nonsecret settings for the chosen playbook are accepted')
    for key, value in settings.items():
        if key.endswith(('_apply', '_verified', '_reboot', '_emptydir', '_containerd')) and type(value) is not bool:
            raise ValueError('Boolean settings must be JSON booleans')
    return settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--playbook', choices=sorted(ALLOWED_SETTINGS), default='security-maintenance')
    parser.add_argument('--settings-file', type=pathlib.Path)
    parser.add_argument('--output-dir', type=pathlib.Path)
    parser.add_argument('--backup-sha256', help='Independently reviewed nonsecret backup receipt digest')
    parser.add_argument('--limit', choices=['workernode2', 'workernode1', 'masternode'])
    parser.add_argument('--syntax-check', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    repo = pathlib.Path(__file__).resolve().parents[2]
    ansible = repo / 'k8s-rewrite/ansible-playbook'
    runtime = pathlib.Path.home() / '.local/share/branconet-migration'
    command = [str(runtime / 'venv/bin/ansible-playbook'), 'playbooks/' + args.playbook + '.yml']
    env = dict(os.environ, ANSIBLE_CONFIG=str(ansible / 'ansible.cfg'), ANSIBLE_NOCOLOR='1')
    # Do not retain an unrelated caller credential for the read-only/checkpoint mode.
    env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    if args.syntax_check:
        return subprocess.run(command + ['--syntax-check'], cwd=ansible, env=env, check=False).returncode
    if not args.settings_file or not args.output_dir or not args.output_dir.is_absolute():
        raise ValueError('A nonsecret settings file and absolute protected output directory are required')
    settings = load_settings(args.settings_file, args.playbook)
    if args.playbook == 'security-maintenance':
        if settings.get('security_maintenance_apply') is not True or settings.get('security_maintenance_backup_verified') is not True:
            raise ValueError('Explicit apply and reviewed backup inputs are required')
        reference = pathlib.Path(settings.get('security_maintenance_backup_reference', ''))
        if not reference.is_absolute() or not reference.is_file() or not args.backup_sha256 or sha256(reference) != args.backup_sha256:
            raise ValueError('Reviewed backup receipt path or independently supplied SHA-256 does not match')
        # The launcher does not turn controller completion into restore proof.
        receipt = json.loads(reference.read_text())
        completed = datetime.datetime.fromisoformat(receipt.get('completed_at', '').replace('Z', '+00:00'))
        age = (datetime.datetime.now(datetime.timezone.utc) - completed).total_seconds()
        if receipt.get('status') != 'completed' or receipt.get('consistency') != 'crash-consistent-online' or not receipt.get('volumes') or not 0 <= age <= 86400:
            raise ValueError('A completed online storage checkpoint less than 24 hours old is required; other recovery evidence still needs review')
        request = json.loads(sys.stdin.buffer.read(65537))
        if not isinstance(request, dict) or set(request) != {'sudo_password'} or not isinstance(request['sudo_password'], str) or not request['sudo_password']:
            raise ValueError('Stdin must contain only the nonempty sudo_password JSON field')
        env['BRANCONET_MIGRATION_SUDO_PASSWORD'] = request.pop('sudo_password')
    elif settings.get('storage_checkpoint_apply') is not True:
        raise ValueError('Explicit checkpoint apply input is required')
    if args.limit:
        if args.playbook != 'security-maintenance':
            raise ValueError('The checkpoint always inventories all attached volumes through master')
        command += ['--limit', args.limit]
    if args.check:
        command.append('--check')
    output = args.output_dir.resolve()
    if output == repo or repo in output.parents:
        raise ValueError('Operational logs and receipts must remain outside the source repository')
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(output, 0o700)
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    recovery_dir = None
    if args.playbook == 'security-maintenance':
        recovery_dir = output / ('security-maintenance-' + run_id + '-recovery')
        recovery_dir.mkdir(mode=0o700)
        settings['security_maintenance_recovery_receipt_dir'] = str(recovery_dir)
    command += ['--extra-vars', json.dumps(settings)]
    log = output / (args.playbook + '-' + run_id + '.log')
    record_path = output / (args.playbook + '-' + run_id + '.json')
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'w') as stream:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, cwd=ansible, env=env, start_new_session=True)
        # The password exists only in the launched child's environment and this process's memory.
        env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
        try:
            code = process.wait()
        except KeyboardInterrupt:
            os.killpg(process.pid, signal.SIGINT)
            try:
                code = process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                code = process.wait(timeout=30)
    record = {'run_id': run_id, 'playbook': args.playbook, 'started_at': started,
              'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'exit_code': code, 'operator_log': str(log), 'settings_sha256': sha256(args.settings_file),
              'backup_receipt_sha256': args.backup_sha256, 'check_mode': args.check, 'limit': args.limit,
              'recovery_receipt_directory': str(recovery_dir) if recovery_dir else None}
    with os.fdopen(os.open(record_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(record, stream, indent=2); stream.write('\n')
    print(json.dumps(record), flush=True)
    return code


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, json.JSONDecodeError):
        # Never print request data, credentials, target URLs or raw library exceptions.
        raise SystemExit('Maintenance launcher refused invalid inputs or an unavailable local prerequisite')
