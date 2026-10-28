#!/usr/bin/env python3
"""Launch only worker1 filesystem inspection/growth; sudo JSON via protected stdin."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings-file', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--syntax-check', action='store_true')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    ansible = repo / 'k8s-rewrite/ansible-playbook'
    runtime = Path('/home/brajam/.local/share/branconet-migration')
    env = dict(os.environ, ANSIBLE_CONFIG=str(ansible / 'ansible.cfg'), ANSIBLE_NOCOLOR='1')
    env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    cmd = [str(runtime / 'venv/bin/ansible-playbook'), 'playbooks/filesystem-growth.yml']
    if args.syntax_check:
        return subprocess.run(cmd + ['--syntax-check'], cwd=ansible, env=env).returncode
    if not args.settings_file or args.settings_file.stat().st_size > 65536 or not args.output_dir:
        raise ValueError()
    settings = json.loads(args.settings_file.read_text())
    allowed = {'filesystem_growth_apply', 'filesystem_growth_reviewed_preflight',
               'filesystem_growth_reviewed_preflight_sha256'}
    if not isinstance(settings, dict) or set(settings) - allowed:
        raise ValueError()
    if type(settings.get('filesystem_growth_apply', False)) is not bool:
        raise ValueError()
    out = args.output_dir
    if not out.is_absolute() or out.resolve() != out or not str(out).startswith(str(runtime) + '/'):
        raise ValueError()
    if out == repo or repo in out.parents:
        raise ValueError()
    out.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = out.lstat()
    if st.st_uid != os.getuid() or st.st_mode & 0o077 or out.is_symlink():
        raise ValueError()
    request = json.loads(sys.stdin.buffer.read(65537))
    if not isinstance(request, dict) or set(request) != {'sudo_password'} or not isinstance(request['sudo_password'], str) or not request['sudo_password']:
        raise ValueError()
    env['BRANCONET_MIGRATION_SUDO_PASSWORD'] = request.pop('sudo_password')
    ident = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    log = out / ('filesystem-growth-' + ident + '.log')
    record_path = out / ('filesystem-growth-' + ident + '.json')
    cmd += ['--extra-vars', json.dumps(settings)]
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    record = {'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'applyRequested': settings.get('filesystem_growth_apply', False),
              'operatorLog': str(log), 'playbook': 'filesystem-growth.yml'}
    with os.fdopen(fd, 'w') as stream:
        child = subprocess.Popen(cmd, cwd=ansible, env=env, stdin=subprocess.DEVNULL,
                                 stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
        record['ansiblePID'] = child.pid
        try:
            record['exitCode'] = child.wait(timeout=360)
            record['state'] = 'complete'
        except subprocess.TimeoutExpired:
            # Observation timeout must never kill an online filesystem resize.
            record['state'] = 'still_running_observe_existing_process_do_not_replay'
    record['observedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with os.fdopen(os.open(record_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as f:
        json.dump(record, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    dfd = os.open(out, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    print(json.dumps({**record, 'receipt': str(record_path)}), flush=True)
    return record.get('exitCode', 75)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('Filesystem launcher refused invalid input or unavailable prerequisite; no credential diagnostics emitted')
