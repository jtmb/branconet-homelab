#!/usr/bin/env python3
"""Run only the independent retired artifact role; sudo credential via RAM stdin."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings-file', type=Path)
    parser.add_argument('--syntax-check', action='store_true')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    ansible = repo / 'k8s-rewrite/ansible-playbook'
    env = dict(os.environ, ANSIBLE_CONFIG=str(ansible / 'ansible.cfg'), ANSIBLE_NOCOLOR='1')
    env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    argv = ['/home/brajam/.local/share/branconet-migration/venv/bin/ansible-playbook', 'playbooks/retired-build-offload.yml', '--limit', 'masternode']
    if args.syntax_check:
        return subprocess.run(argv + ['--syntax-check'], cwd=ansible, env=env).returncode
    if not args.settings_file or args.settings_file.stat().st_size > 65536:
        raise ValueError()
    settings = json.loads(args.settings_file.read_text())
    allowed = {'retired_build_offload_' + name for name in ('apply', 'mode', 'output_dir', 'additional_units',
               'selected_caches', 'verified_receipt', 'reviewed_receipt_sha256')}
    if not isinstance(settings, dict) or set(settings) - allowed or settings.get('retired_build_offload_apply') is not True:
        raise ValueError()
    output = Path(settings.get('retired_build_offload_output_dir', ''))
    if not output.is_absolute() or output.resolve() != output or not output.is_relative_to(Path('/home/brajam/.local/share/branconet-migration')):
        raise ValueError()
    if any((p / '.git').exists() for p in [output, *output.parents]):
        raise ValueError()
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    if output.stat().st_uid != os.getuid() or output.stat().st_mode & 0o077:
        raise ValueError()
    request = json.loads(sys.stdin.buffer.read(65537))
    if not isinstance(request, dict) or set(request) != {'sudo_password'} or not isinstance(request['sudo_password'], str) or not request['sudo_password']:
        raise ValueError()
    env['BRANCONET_MIGRATION_SUDO_PASSWORD'] = request.pop('sudo_password')
    log = output / ('launcher-' + uuid.uuid4().hex + '.log')
    with os.fdopen(os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        child = subprocess.Popen(argv + ['--extra-vars', json.dumps(settings)], cwd=ansible, env=env,
                                 stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
        env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
        result = child.wait()
    print(json.dumps({'exit_code': result, 'operator_log': str(log)}))
    return result


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('Retired build offload launcher refused invalid inputs; no credential diagnostics are emitted')
