#!/usr/bin/env python3
"""Launch only the isolated worker1 application builder; sudo credential on stdin only."""
import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['setup', 'runtime', 'status', 'stop'], default='status')
    parser.add_argument('--service', choices=['seerr', 'ytptube', 'jackett', 'pihole'], required=True)
    parser.add_argument('--attempt', default='initial')
    parser.add_argument('--seerr-lock-path', type=pathlib.Path)
    parser.add_argument('--context-dir', type=pathlib.Path)
    parser.add_argument('--output-dir', type=pathlib.Path)
    parser.add_argument('--syntax-check', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'initial|r[1-9][0-9]{0,2}', args.attempt):
        raise ValueError('invalid attempt identity')
    repo = pathlib.Path(__file__).resolve().parents[2]
    ansible = repo / 'k8s-rewrite/ansible-playbook'
    command = [str(pathlib.Path.home() / '.local/share/branconet-migration/venv/bin/ansible-playbook'), 'playbooks/worker1-image-build.yml']
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
    settings = {'worker1_image_build_apply': True, 'worker1_image_build_phase': args.phase, 'worker1_image_build_service': args.service, 'worker1_image_build_attempt': args.attempt}
    if args.context_dir:
        settings['worker1_image_build_context_dir'] = str(args.context_dir)
    if args.seerr_lock_path:
        if not args.seerr_lock_path.is_absolute():
            raise ValueError('absolute staged Seerr lock required')
        settings['worker1_image_build_seerr_lock_path'] = str(args.seerr_lock_path)
    command += ['--limit', 'workernode1', '--extra-vars', json.dumps(settings)]
    output = args.output_dir.resolve()
    if output == repo or repo in output.parents:
        raise ValueError('operational evidence must remain outside Git')
    output.mkdir(mode=0o700, parents=True, exist_ok=True); os.chmod(output, 0o700)
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    log = output / ('worker1-' + args.service + '-build-' + args.phase + '-' + run_id + '.log')
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with os.fdopen(os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, cwd=ansible, env=env)
        env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
        code = process.wait()
    record = {'run_id': run_id, 'phase': args.phase, 'service': args.service, 'started_at': started, 'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'launcher_exit_code': code, 'operator_log': str(log), 'build_success': False, 'note': 'Runtime launch is asynchronous; inspect retained remote phase completion metadata.'}
    record['attempt'] = args.attempt
    path = output / ('worker1-' + args.service + '-build-' + args.phase + '-' + run_id + '.json')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(record, stream, indent=2); stream.write('\n')
    print(json.dumps(record), flush=True)
    return code


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (ValueError, OSError, KeyError, json.JSONDecodeError):
        raise SystemExit('Worker1 image build launcher refused invalid inputs or an unavailable local prerequisite')
