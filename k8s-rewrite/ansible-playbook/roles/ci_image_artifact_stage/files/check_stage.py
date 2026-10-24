"""Verify fixed public CI artifact copies; never execute, import or scan an image."""
import argparse
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import sys

CONTROLLER = Path('/home/brajam/.local/share/branconet-migration/ci-image-artifacts-20261024')
NODE = Path('/home/james/.local/share/branconet-migration/ci-image-artifacts-20261024')
SERVICES = ['seerr', 'ytptube', 'jackett', 'pihole', 'flaresolverr', 'vaultwarden', 'tautulli']


class StageRefused(ValueError):
    pass


def need(value, category):
    if not value:
        raise StageRefused(category)


def fingerprint(info):
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def directory(path, owner):
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink(), 'directory_path')
    info = path.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == owner and stat.S_IMODE(info.st_mode) == 0o700,
         'protected_directory_owner_or_mode')


def file_identity(path, owner, expected_sha, cap, expected_bytes=None):
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink(), 'file_path')
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid == owner and before.st_nlink == 1 and
         stat.S_IMODE(before.st_mode) == 0o400, 'protected_regular_file_owner_mode_or_link')
    need(0 < before.st_size <= cap and (expected_bytes is None or before.st_size == expected_bytes), 'file_size')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        need(fingerprint(os.fstat(fd)) == fingerprint(before), 'opened_file_identity')
        digest = hashlib.sha256()
        count = 0
        with os.fdopen(os.dup(fd), 'rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                count += len(block)
                need(count <= cap, 'stream_size')
                digest.update(block)
        need(count == before.st_size and digest.hexdigest() == expected_sha, 'file_sha256')
        need(fingerprint(os.fstat(fd)) == fingerprint(path.lstat()) == fingerprint(before), 'file_changed_during_hash')
    finally:
        os.close(fd)
    return {'bytes': count, 'sha256': expected_sha, 'fingerprint': fingerprint(before)}


def caps(service):
    result = {name: 4 * 1024 ** 2 for name in ['result.json', 'preflight.json', 'builder-host-limits.json',
                                             'builder-limits.json', 'runtime-inputs-sha256.json']}
    result[service + '.oci.tar'] = 4 * 1024 ** 3
    if service == 'seerr':
        result['pnpm-lock.yaml'] = 16 * 1024 ** 2
    return result


def validate_entries(entries, limits):
    need(isinstance(entries, dict) and set(entries) == set(limits), 'exact_selected_file_allowlist')
    for name, value in entries.items():
        need(isinstance(value, dict) and type(value.get('bytes')) is int and 0 < value['bytes'] <= limits[name] and
             isinstance(value.get('sha256'), str) and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'manifest_entry')


def controller(args, root, owner):
    directory(CONTROLLER, owner)
    directory(root, owner)
    source_dir_before = fingerprint(root.stat())
    proof_path = root / 'provenance.json'
    proof_identity = file_identity(proof_path, owner, args.provenance_sha256, 4 * 1024 ** 2)
    proof = json.loads(proof_path.read_text())
    need(proof.get('schemaVersion') == 1 and proof.get('sourceKind') == 'github-actions', 'provenance_schema')
    github = proof['github']
    run_data, artifact = github['run'], github['artifact']
    need(github['repository'].get('full_name') == 'jtmb/branconet-charts' and
         github['repository'].get('private') is True and
         github['workflow'].get('path') == '.github/workflows/build-security-images.yml', 'private_ci_scope')
    need(run_data.get('id') == args.run_id and artifact.get('id') == args.artifact_id and
         run_data.get('status') == 'completed' and run_data.get('conclusion') == 'success' and
         run_data.get('event') == 'workflow_dispatch', 'successful_matching_ci_run')
    head = run_data.get('head_sha', '')
    attempt = run_data.get('run_attempt')
    need(isinstance(head, str) and re.fullmatch('[0-9a-f]{40}', head) and type(attempt) is int and attempt > 0,
         'ci_head_or_attempt')
    need(artifact.get('name') == 'security-' + args.service + '-' + head + '-' + str(args.run_id) + '-' + str(attempt) and
         artifact.get('expired') is False and artifact.get('workflow_run', {}).get('id') == args.run_id and
         artifact.get('workflow_run', {}).get('head_sha') == head, 'matching_ci_artifact')
    limits = caps(args.service)
    entries = proof['files']
    validate_entries(entries, limits)
    identities = {name: file_identity(root / name, owner, item['sha256'], limits[name], item['bytes'])
                  for name, item in entries.items()}
    result = json.loads((root / 'result.json').read_text())
    archive = identities[args.service + '.oci.tar']
    need(result.get('state') == 'artifact-built-not-qualified-not-deployed' and result.get('service') == args.service and
         result.get('source_commit') == head and result.get('archive_sha256') == archive['sha256'] and
         result.get('archive_bytes') == archive['bytes'], 'uploaded_result_archive_binding')
    # Repeat the proof read fence after all large-file reads. No contents are printed.
    need(file_identity(proof_path, owner, args.provenance_sha256, 4 * 1024 ** 2) == proof_identity,
         'provenance_changed_during_controller_reads')
    need(fingerprint(root.stat()) == source_dir_before, 'source_directory_changed')
    identities['provenance.json'] = proof_identity
    return {'schemaVersion': 1, 'service': args.service, 'runID': args.run_id, 'artifactID': args.artifact_id,
            'provenanceSHA256': args.provenance_sha256, 'controllerRoot': str(root),
            'files': identities, 'sourceDirectoryFingerprint': source_dir_before}


def node(args, root):
    need(socket.gethostname() == 'workernode1' and os.geteuid() == 0, 'worker1_privileged_staging_only')
    raw = sys.stdin.buffer.read(65537)
    need(len(raw) <= 65536, 'controller_manifest_size')
    manifest = json.loads(raw)
    need(manifest.get('schemaVersion') == 1 and manifest.get('service') == args.service and
         manifest.get('runID') == args.run_id and manifest.get('artifactID') == args.artifact_id and
         manifest.get('provenanceSHA256') == args.provenance_sha256 and
         manifest.get('controllerRoot') == str(CONTROLLER / root.name), 'controller_manifest_scope')
    limits = caps(args.service)
    limits['provenance.json'] = 4 * 1024 ** 2
    expected = manifest['files']
    validate_entries(expected, limits)
    need(expected['provenance.json']['sha256'] == args.provenance_sha256, 'manifest_provenance_binding')
    need(NODE.resolve() == NODE and root.resolve() == root and not NODE.is_symlink() and not root.is_symlink(),
         'fixed_destination_path')
    base_exists = NODE.exists()
    root_exists = root.exists()
    if base_exists:
        directory(NODE, 0)
    else:
        need(not root_exists and args.phase == 'node-before', 'destination_parent_missing')
        parent = NODE.parent
        need(parent.resolve() == parent and not parent.is_symlink(), 'existing_operator_parent_path')
        info = parent.lstat()
        operator = pwd.getpwnam('james')
        mode = stat.S_IMODE(info.st_mode)
        need(stat.S_ISDIR(info.st_mode) and info.st_uid in [0, operator.pw_uid] and
             not mode & 0o002, 'existing_operator_parent_permissions')
        if mode & 0o020:
            group = grp.getgrgid(info.st_gid)
            members = set(group.gr_mem) | {u.pw_name for u in pwd.getpwall() if u.pw_gid == info.st_gid}
            need(info.st_uid == operator.pw_uid and info.st_gid == operator.pw_gid and
                 group.gr_name == operator.pw_name and members == {operator.pw_name},
                 'shared_parent_write_must_be_same_operator_only')
    if root_exists:
        directory(root, 0)
        need({p.name for p in root.iterdir()} <= set(expected), 'unselected_existing_destination_entry')
    else:
        need(args.phase == 'node-before', 'destination_directory_missing')
    existing, missing = {}, []
    for name, item in expected.items():
        path = root / name
        need(not path.is_symlink(), 'destination_symlink')
        if path.exists():
            existing[name] = file_identity(path, 0, item['sha256'], limits[name], item['bytes'])
        else:
            need(args.phase == 'node-before', 'selected_destination_file_missing')
            missing.append(name)
    output = {'phase': args.phase, 'service': args.service, 'runID': args.run_id, 'artifactID': args.artifact_id,
              'root': str(root), 'baseExists': base_exists, 'rootExists': root_exists,
              'existingFiles': sorted(existing), 'missingFiles': missing,
              'verifiedFiles': existing, 'provenanceSHA256': args.provenance_sha256,
              'imageImported': False, 'imageExecuted': False, 'scannerExecuted': False}
    if args.phase == 'node-before':
        filesystem = os.statvfs(root if root_exists else NODE if base_exists else NODE.parent)
        capacity = filesystem.f_blocks * filesystem.f_frsize
        floor = capacity // 4 + 8 * 1024 ** 3
        pending = sum(expected[name]['bytes'] for name in missing)
        required = floor + pending + 2 * expected[args.service + '.oci.tar']['bytes']
        available = filesystem.f_bavail * filesystem.f_frsize
        need(available >= required and filesystem.f_favail >= max(250000, filesystem.f_files // 10),
             'staging_and_existing_scanner_reserve')
        output['capacity'] = {'availableBytes': available, 'requiredBytes': required,
                              'pendingCopyBytes': pending, 'existingScannerReserveBytes': floor}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['controller', 'node-before', 'node-after'])
    parser.add_argument('--service', choices=SERVICES, required=True)
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('--artifact-id', type=int, required=True)
    parser.add_argument('--provenance-sha256', required=True)
    args = parser.parse_args()
    need(os.name == 'posix' and 0 < args.run_id < 2 ** 63 and 0 < args.artifact_id < 2 ** 63 and
         re.fullmatch('[0-9a-f]{64}', args.provenance_sha256), 'explicit_fixed_artifact_identity')
    suffix = str(args.run_id) + '-' + str(args.artifact_id)
    if args.phase == 'controller':
        owner = pwd.getpwnam('brajam').pw_uid
        need(os.geteuid() == owner, 'native_controller_operator_only')
        output = controller(args, CONTROLLER / suffix, owner)
    else:
        output = node(args, NODE / suffix)
    print(json.dumps(output, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'state': 'refused', 'category': str(error) if isinstance(error, StageRefused) else type(error).__name__,
                          'imageImported': False, 'imageExecuted': False, 'scannerExecuted': False}))
        raise SystemExit(1)
