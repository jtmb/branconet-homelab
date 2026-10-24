#!/usr/bin/env python3
"""Launch only the isolated master YTPTube builder; sudo credential on stdin only."""
import argparse
import datetime
import json
import os
import pathlib
import subprocess
import sys
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['setup', 'runtime', 'status', 'stop'], default='status')
    parser.add_argument('--context-dir', type=pathlib.Path)
    parser.add_argument('--output-dir', type=pathlib.Path)
    parser.add_argument('--syntax-check', action='store_true')
    args = parser.parse_args()
    repo = pathlib.Path(__file__).resolve().parents[2]
    ansible = repo / 'k8s-rewrite/ansible-playbook'
    command = [str(pathlib.Path.home() / '.local/share/branconet-migration/venv/bin/ansible-playbook'), 'playbooks/ytptube-image-build.yml']
    env = dict(os.environ, ANSIBLE_CONFIG=str(ansible / 'ansible.cfg'), ANSIBLE_NOCOLOR='1')
    env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    if args.syntax_check:
        return subprocess.run(command + ['--syntax-check'], cwd=ansible, env=env, check=False).returncode
    if not args.output_dir or not args.output_dir.is_absolute():
        raise ValueError('absolute protected output directory required')
    if args.phase == 'setup' and (not args.context_dir or not args.context_dir.is_absolute()):
        raise ValueError('setup requires the explicitly staged controller context')
    request = json.loads(sys.stdin.buffer.read(65537))
    if not isinstance(request, dict) or set(request) != {'sudo_password'} or not isinstance(request['sudo_password'], str) or not request['sudo_password']:
        raise ValueError('stdin must contain only the sudo_password JSON field')
    env['BRANCONET_MIGRATION_SUDO_PASSWORD'] = request.pop('sudo_password')
    settings = {'ytptube_build_apply': True, 'ytptube_build_phase': args.phase}
    if args.context_dir:
        settings['ytptube_build_context_dir'] = str(args.context_dir)
    command += ['--extra-vars', json.dumps(settings)]
    output = args.output_dir.resolve()
    if output == repo or repo in output.parents:
        raise ValueError('operational evidence must remain outside Git')
    output.mkdir(mode=0o700, parents=True, exist_ok=True); os.chmod(output, 0o700)
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    log = output / ('ytptube-build-' + args.phase + '-' + run_id + '.log')
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with os.fdopen(os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, cwd=ansible, env=env)
        env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
        code = process.wait()
    record = {'run_id': run_id, 'phase': args.phase, 'started_at': started, 'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'launcher_exit_code': code, 'operator_log': str(log), 'build_success': False, 'note': 'Runtime launch is asynchronous; inspect retained remote phase completion metadata.'}
    path = output / ('ytptube-build-' + args.phase + '-' + run_id + '.json')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(record, stream, indent=2); stream.write('\n')
    print(json.dumps(record), flush=True)
    return code


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (ValueError, OSError, KeyError, json.JSONDecodeError):
        raise SystemExit('YTPTube build launcher refused invalid inputs or an unavailable local prerequisite')
