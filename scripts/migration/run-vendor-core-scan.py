#!/usr/bin/env python3
"""Operate only the separately reviewed two-image vendor scan; sudo via stdin."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--phase', choices=['setup', 'scan', 'status'], default='status')
    parser.add_argument('--attempt', default='')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--syntax-check', action='store_true')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    ansible = repo / 'k8s-rewrite/ansible-playbook'
    runtime = Path('/home/brajam/.local/share/branconet-migration')
    env = dict(os.environ, ANSIBLE_CONFIG=str(ansible / 'ansible.cfg'), ANSIBLE_NOCOLOR='1')
    env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    cmd = [str(runtime / 'venv/bin/ansible-playbook'), 'playbooks/vendor-core-scan.yml', '--limit', 'workernode1']
    if args.syntax_check:
        return subprocess.run(cmd + ['--syntax-check'], cwd=ansible, env=env).returncode
    if args.phase == 'scan' and not args.attempt:
        args.attempt = uuid.uuid4().hex[:12]
    if args.apply and args.phase != 'setup' and not re.fullmatch('[0-9a-f]{12}', args.attempt):
        raise ValueError()
    settings = {'vendor_core_scan_apply': args.apply,
                'vendor_core_scan_phase': args.phase, 'vendor_core_scan_attempt': args.attempt}
    cmd += ['--extra-vars', json.dumps(settings)]
    if not args.apply:
        return subprocess.run(cmd, cwd=ansible, env=env, stdin=subprocess.DEVNULL).returncode
    output = args.output_dir
    if (output is None or not output.is_absolute() or output.resolve() != output
            or not str(output).startswith(str(runtime) + '/') or repo in output.parents):
        raise ValueError()
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = output.lstat()
    if output.is_symlink() or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError()
    raw = sys.stdin.buffer.read(65537)
    if len(raw) > 65536:
        raise ValueError()
    request = json.loads(raw)
    if set(request) != {'sudo_password'} or not isinstance(request['sudo_password'], str) or not request['sudo_password']:
        raise ValueError()
    env['BRANCONET_MIGRATION_SUDO_PASSWORD'] = request.pop('sudo_password')
    ident = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    log = output / ('vendor-core-' + ident + '.log')
    receipt = output / ('vendor-core-' + ident + '.json')
    record = {'sourceKind': 'upstream-registry', 'phase': args.phase, 'attempt': args.attempt,
              'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'operatorLog': str(log), 'scanComplete': False, 'securityAcceptance': False}
    with os.fdopen(os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        child = subprocess.Popen(cmd, cwd=ansible, env=env, stdin=subprocess.DEVNULL,
                                 stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
        record['ansiblePID'] = child.pid
        try:
            record['exitCode'] = child.wait(timeout=360)
            record['state'] = 'operator_phase_complete_review_remote_receipt'
        except subprocess.TimeoutExpired:
            record['state'] = 'still_running_observe_existing_process_do_not_replay'
    record['observedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with os.fdopen(os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(record, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({**record, 'receipt': str(receipt)}))
    return record.get('exitCode', 75)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('Official core vendor scan launcher refused; no credential diagnostics emitted')
