#!/usr/bin/env python3
"""Authenticate the existing backup, then dispatch only the opt-in etcd patch."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile
import uuid

REPO = Path(__file__).resolve().parents[2]
BACKUP_SOURCE = REPO / 'k8s-rewrite/ansible-playbook/roles/control_plane_backup/files/control_plane_backup.py'
spec = importlib.util.spec_from_file_location('etcd_patch_archive_contract', BACKUP_SOURCE)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)
RUNTIME = Path('/home/brajam/.local/share/branconet-migration')
OLD = 'registry.k8s.io/etcd:3.7.0-0'
OLD_RUNTIME = 'registry.k8s.io/etcd@sha256:6ecefbe2510c4a30573a62a4d6dd175acf881ca67003fcd91849a16df7a724d5'


def need(ok):
    if not ok:
        raise ValueError('etcd_patch_controller_refused')


def sha(path):
    return backup.digest_file(path)


def drain(child):
    trailing = 0
    for block in iter(lambda: child.stdout.read(65536), b''):
        trailing += len(block)
        need(trailing <= 1024 ** 2 and not any(block))
    need(child.wait(timeout=30) == 0)


def authenticated_ticket(receipt_path, receipt_sha):
    need(re.fullmatch('[0-9a-f]{64}', receipt_sha))
    receipt_identity = backup.protected_file(receipt_path, private=True)
    need(receipt_path.stat().st_size <= 65536 and sha(receipt_path) == receipt_sha)
    receipt = json.loads(receipt_path.read_bytes())
    need(receipt.get('status') == 'completed' and receipt.get('scope') == 'cluster-maintenance-control-plane')
    need(all(receipt.get(k) is True for k in ['authenticated_archive_verified', 'snapshot_footer_verified',
                                            'snapshot_status_verified', 'off_node_operator_copy']))
    need(receipt.get('remote_plaintext_retained') is False and receipt['source']['image'] == OLD
         and receipt['source']['image_id'] == OLD_RUNTIME)
    completed = datetime.datetime.fromisoformat(receipt['completed_at'].replace('Z', '+00:00'))
    age = (datetime.datetime.now(datetime.timezone.utc) - completed).total_seconds()
    need(0 <= age <= 3600 and receipt['snapshot_status']['revision'] > 0)
    archive = Path(receipt['archive_path'])
    archive_identity = backup.protected_file(archive, private=True)
    need(0 < archive.stat().st_size == receipt['archive_bytes'] <= backup.MAX_ARCHIVE + 1024 ** 2
         and sha(archive) == receipt['archive_sha256'])
    age_tool = RUNTIME / 'bin/age'
    identity = Path('/home/brajam/.ssh/id_ed25519')
    pins = [(p, backup.protected_file(p, private=p == identity, executable=p == age_tool)) for p in [identity, age_tool]]
    need(sha(age_tool) == backup.AGE_SHA256)
    children = []
    def decrypt():
        child = subprocess.Popen([str(age_tool), '-d', '-i', str(identity), str(archive)],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        children.append(child)
        return child
    try:
        # Authenticate the whole first stream before trusting its public SHA map.
        child = decrypt()
        manifest = None
        count = total = 0
        with tarfile.open(fileobj=child.stdout, mode='r|') as bundle:
            for member in bundle:
                count += 1
                total += member.size
                need(count <= 258 and total <= backup.MAX_ARCHIVE and member.isfile())
                stream = bundle.extractfile(member)
                if count == 1:
                    need(member.name == 'manifest.json' and member.size <= 262144)
                    manifest = json.load(stream)
                else:
                    for block in iter(lambda: stream.read(1024 ** 2), b''):
                        pass
        drain(child)
        need(manifest is not None and manifest.get('schema_version') == 1)
        binding = manifest['snapshot']
        need(binding['sha256'] == receipt['snapshot_sha256'] and binding['bytes'] >= receipt['snapshot_status']['totalSize'])
        child = decrypt()
        config_count = backup.verify_archive(child.stdout, binding)
        drain(child)
        need(config_count == receipt['config_file_count'])
        for name in ['etc/kubernetes/manifests/etcd.yaml', 'etc/kubernetes/kubeadm-init.yaml']:
            need(name in manifest['files'])
        need(backup.protected_file(receipt_path, private=True) == receipt_identity and sha(receipt_path) == receipt_sha)
        need(backup.protected_file(archive, private=True) == archive_identity and sha(archive) == receipt['archive_sha256'])
        for path, before in pins:
            need(backup.protected_file(path, private=path == identity, executable=path == age_tool) == before)
        return {'schemaVersion': 1, 'scope': 'authenticated-etcd-static-patch', 'backupReceiptSHA256': receipt_sha,
                'archiveSHA256': receipt['archive_sha256'], 'snapshotSHA256': receipt['snapshot_sha256'],
                'snapshotRevision': receipt['snapshot_status']['revision'], 'backupCompletedUTC': receipt['completed_at'],
                'sourcePodUID': receipt['source']['uid'], 'authenticatedArchive': True, 'snapshotFooter': True,
                'snapshotStatus': True, 'configurationSHA256': {name: row['sha256'] for name, row in manifest['files'].items()},
                'verificationSourceSHA256': sha(Path(__file__)), 'backupContractSHA256': sha(BACKUP_SOURCE)}
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--phase', choices=['preload', 'review', 'apply', 'status'], default='review')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--review-id', default='')
    parser.add_argument('--review-sha256', default='')
    parser.add_argument('--backup-receipt', type=Path)
    parser.add_argument('--backup-receipt-sha256', default='')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--syntax-check', action='store_true')
    args = parser.parse_args()
    ansible = REPO / 'k8s-rewrite/ansible-playbook'
    env = dict(os.environ, ANSIBLE_CONFIG=str(ansible / 'ansible.cfg'), ANSIBLE_NOCOLOR='1')
    env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    cmd = [str(RUNTIME / 'venv/bin/ansible-playbook'), 'playbooks/etcd-static-patch.yml', '--limit', 'masternode']
    if args.syntax_check:
        return subprocess.run(cmd + ['--syntax-check'], cwd=ansible, env=env).returncode
    if not args.apply:
        return subprocess.run(cmd, cwd=ansible, env=env, stdin=subprocess.DEVNULL).returncode
    os.umask(0o077)
    need(args.output_dir is not None and args.output_dir.is_absolute() and args.output_dir.resolve() == args.output_dir
         and str(args.output_dir).startswith(str(RUNTIME) + '/') and REPO not in args.output_dir.parents)
    args.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = args.output_dir.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077)
    raw = sys.stdin.buffer.read(65537)
    need(len(raw) <= 65536)
    request = json.loads(raw)
    need(set(request) == {'sudo_password'} and isinstance(request['sudo_password'], str) and request['sudo_password'])
    if args.phase == 'status':
        need(re.fullmatch('[0-9a-f]{32}', args.run_id))
        ticket = {}
    else:
        need(args.backup_receipt is not None)
        ticket = authenticated_ticket(args.backup_receipt, args.backup_receipt_sha256)
        args.run_id = args.run_id or uuid.uuid4().hex
        need(re.fullmatch('[0-9a-f]{32}', args.run_id))
    if args.phase == 'apply':
        need(re.fullmatch('[0-9a-f]{32}', args.review_id) and re.fullmatch('[0-9a-f]{64}', args.review_sha256))
    settings = {'etcd_static_patch_apply': True, 'etcd_static_patch_phase': args.phase,
                'etcd_static_patch_run_id': args.run_id, 'etcd_static_patch_review_id': args.review_id,
                'etcd_static_patch_review_sha256': args.review_sha256, 'etcd_static_patch_verification_ticket': ticket}
    ident = uuid.uuid4().hex
    settings_path = args.output_dir / ('settings-' + ident + '.json')
    with settings_path.open('x') as stream:
        json.dump(settings, stream)
    log = args.output_dir / ('operator-' + ident + '.log')
    record = {'phase': args.phase, 'runID': args.run_id, 'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'operatorLog': str(log), 'fullGoalComplete': False, 'appliedOrAccepted': False}
    env['BRANCONET_MIGRATION_SUDO_PASSWORD'] = request.pop('sudo_password')
    with log.open('x') as stream:
        child = subprocess.Popen(cmd + ['--extra-vars', '@' + str(settings_path)], cwd=ansible, env=env,
                                 stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
        record['ansiblePID'] = child.pid
        try:
            record['exitCode'] = child.wait(timeout=720)
            record['state'] = 'phase_finished_review_exact_remote_receipt'
        except subprocess.TimeoutExpired:
            record['state'] = 'observation_timeout_inspect_same_process_no_replay'
    record['observedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    output = args.output_dir / ('controller-' + ident + '.json')
    with output.open('x') as stream:
        json.dump(record, stream, indent=2)
    print(json.dumps({**record, 'controllerReceipt': str(output)}))
    return record.get('exitCode', 75)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('Etcd patch controller refused; credentials, keys, configuration values and raw diagnostics withheld')
