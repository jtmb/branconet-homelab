#!/usr/bin/env python3
"""Dispatch only the separate worker1 offline OCI scanner; credential via stdin/env."""
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
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--phase', choices=['setup', 'helper', 'scan', 'status'], default='status')
    p.add_argument('--service', choices=['seerr', 'ytptube', 'jackett', 'pihole', 'flaresolverr', 'vaultwarden'])
    p.add_argument('--attempt', default='')
    p.add_argument('--build-attempt', default='initial')
    p.add_argument('--source-kind', choices=['worker1', 'github-actions'], default='worker1')
    p.add_argument('--ci-run-id', type=int, default=0)
    p.add_argument('--ci-artifact-id', type=int, default=0)
    p.add_argument('--ci-provenance-sha256', default='')
    p.add_argument('--archive-sha256', default='')
    p.add_argument('--root-descriptor', default='')
    p.add_argument('--output-dir', type=Path)
    p.add_argument('--syntax-check', action='store_true')
    args = p.parse_args()
    if not re.fullmatch(r'initial|r[1-9][0-9]{0,2}', args.build_attempt):
        raise ValueError()
    repo = Path(__file__).resolve().parents[2]
    ansible = repo / 'k8s-rewrite/ansible-playbook'
    runtime = Path('/home/brajam/.local/share/branconet-migration')
    env = dict(os.environ, ANSIBLE_CONFIG=str(ansible / 'ansible.cfg'), ANSIBLE_NOCOLOR='1')
    env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    cmd = [str(runtime / 'venv/bin/ansible-playbook'), 'playbooks/worker1-oci-scan.yml', '--limit', 'workernode1']
    if args.syntax_check:
        return subprocess.run(cmd + ['--syntax-check'], cwd=ansible, env=env).returncode
    if args.phase == 'scan':
        if not args.service or not re.fullmatch('[0-9a-f]{64}', args.archive_sha256) or not re.fullmatch('sha256:[0-9a-f]{64}', args.root_descriptor):
            raise ValueError()
        if args.source_kind == 'github-actions':
            if not (0 < args.ci_run_id < 2 ** 63 and 0 < args.ci_artifact_id < 2 ** 63) or not re.fullmatch('[0-9a-f]{64}', args.ci_provenance_sha256) or args.build_attempt != 'initial':
                raise ValueError()
        elif args.ci_run_id or args.ci_artifact_id or args.ci_provenance_sha256:
            raise ValueError()
        args.attempt = args.attempt or uuid.uuid4().hex[:12]
    if args.attempt and (not args.service or not re.fullmatch('[0-9a-f]{12}', args.attempt)):
        raise ValueError()
    if args.apply and not args.output_dir:
        raise ValueError()
    settings = {'worker1_oci_scan_apply': args.apply, 'worker1_oci_scan_phase': args.phase,
                'worker1_oci_scan_service': args.service or '', 'worker1_oci_scan_attempt': args.attempt,
                'worker1_oci_scan_build_attempt': args.build_attempt,
                'worker1_oci_scan_source_kind': args.source_kind,
                'worker1_oci_scan_ci_run_id': args.ci_run_id,
                'worker1_oci_scan_ci_artifact_id': args.ci_artifact_id,
                'worker1_oci_scan_ci_provenance_sha256': args.ci_provenance_sha256,
                'worker1_oci_scan_archive_sha256': args.archive_sha256,
                'worker1_oci_scan_root_descriptor': args.root_descriptor}
    cmd += ['--extra-vars', json.dumps(settings)]
    if not args.apply:
        return subprocess.run(cmd, cwd=ansible, env=env, stdin=subprocess.DEVNULL).returncode
    out = args.output_dir
    if not out.is_absolute() or out.resolve() != out or not str(out).startswith(str(runtime) + '/') or repo in out.parents:
        raise ValueError()
    out.mkdir(mode=0o700, parents=True, exist_ok=True)
    s = out.lstat()
    if out.is_symlink() or s.st_uid != os.getuid() or s.st_mode & 0o077:
        raise ValueError()
    request = json.loads(sys.stdin.buffer.read(65537))
    if not isinstance(request, dict) or set(request) != {'sudo_password'} or not isinstance(request['sudo_password'], str) or not request['sudo_password']:
        raise ValueError()
    env['BRANCONET_MIGRATION_SUDO_PASSWORD'] = request.pop('sudo_password')
    ident = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    log = out / ('worker1-oci-scan-' + ident + '.log')
    receipt = out / ('worker1-oci-scan-' + ident + '.json')
    record = {'phase': args.phase, 'service': args.service, 'attempt': args.attempt,
              'buildAttempt': args.build_attempt if args.source_kind == 'worker1' else None,
              'sourceKind': args.source_kind, 'ciRunID': args.ci_run_id or None,
              'ciArtifactID': args.ci_artifact_id or None, 'ciProvenanceSHA256': args.ci_provenance_sha256 or None,
              'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'operatorLog': str(log), 'scanComplete': False, 'securityAcceptance': False}
    with os.fdopen(os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as f:
        child = subprocess.Popen(cmd, cwd=ansible, env=env, stdin=subprocess.DEVNULL,
                                 stdout=f, stderr=subprocess.STDOUT, start_new_session=True)
        env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
        record['ansiblePID'] = child.pid
        try:
            record['exitCode'] = child.wait(timeout=360)
            record['state'] = 'ansible_complete_scan_requires_remote_receipt'
        except subprocess.TimeoutExpired:
            record['state'] = 'still_running_observe_existing_process_do_not_replay'
    record['observedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with os.fdopen(os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as f:
        json.dump(record, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    fd = os.open(out, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    print(json.dumps({**record, 'receipt': str(receipt)}), flush=True)
    return record.get('exitCode', 75)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('Worker1 OCI launcher refused invalid input or unavailable prerequisite; no credential diagnostics emitted')
