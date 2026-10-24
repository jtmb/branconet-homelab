"""Retire only seven reproducible successful-scan OCI materializations."""
import argparse
import collections
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import subprocess
import sys
import tarfile
import time
from types import SimpleNamespace

BASE = Path('/home/james/.local/share/branconet-migration')
SCANS = BASE / 'worker1-oci-scan-20261023'
ROOT = BASE / 'derived-oci-retirement-20261024'
CI = BASE / 'ci-image-artifacts-20261024'
BUILDS = BASE / 'worker1-image-build-20261023'
JAMES = pwd.getpwnam('james').pw_uid
ALLOWED = {
    'ytptube-509186afea86': ('github-actions', 461125668),
    'flaresolverr-0fd1978123c4': ('github-actions', 477513846),
    'jackett-9ddb8e84b115': ('github-actions', 137821014),
    'seerr-1d801203b95b': ('github-actions', 319818688),
    'flaresolverr-f85f4bc513b5': ('github-actions', 478830068),
    'ytptube-4fa5cf15748a': ('worker1', 448995467),
    'ytptube-13027814b784': ('worker1', 446233597),
}
INDEX = {'application/vnd.oci.image.index.v1+json', 'application/vnd.docker.distribution.manifest.list.v2+json'}
MANIFEST = {'application/vnd.oci.image.manifest.v1+json', 'application/vnd.docker.distribution.manifest.v2+json'}
START = time.monotonic()


def need(ok, category):
    if not ok:
        raise ValueError(category)
    if time.monotonic() - START > 1800:
        raise ValueError('operation_deadline')


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def identity(info):
    return {k: getattr(info, 'st_' + k) for k in ['dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks']}


def regular(path):
    need(path.is_absolute() and path.resolve() == path, 'canonical_file_path')
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid in [0, JAMES]
         and not info.st_mode & 0o077, 'protected_regular_single_link_file')
    return identity(info)


def digest(path):
    before = regular(path)
    value = hashlib.sha256()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        need(identity(os.fstat(stream.fileno())) == before, 'opened_file_identity')
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            need(True, 'operation_deadline')
            value.update(block)
    need(regular(path) == before, 'file_changed_while_hashing')
    return value.hexdigest()


def document(path, cap=64 * 1024 ** 2):
    info = regular(path)
    need(0 < info['size'] <= cap, 'document_size')
    data = path.read_bytes()
    need(regular(path) == info, 'document_changed')
    return json.loads(data), {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'identity': info}


def directory(path):
    need(path.resolve() == path, 'canonical_directory_path')
    info = path.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid in [0, JAMES] and not info.st_mode & 0o077, 'protected_directory')
    return identity(info)


def mounts():
    def unescape(value):
        return re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), value)
    return {unescape(line.split()[4]) for line in Path('/proc/self/mountinfo').read_text().splitlines()}


def no_mount_or_refs(path):
    prefix = str(path) + '/'
    need(not any(m == str(path) or m.startswith(prefix) for m in mounts()), 'derived_mount_refused')
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            need((proc / 'comm').read_text().strip() != 'trivy', 'active_scanner_refused')
            for fd in (proc / 'fd').iterdir():
                try:
                    link = os.readlink(fd).removesuffix(' (deleted)')
                    need(link != str(path) and not link.startswith(prefix), 'derived_open_reference_refused')
                except (FileNotFoundError, ProcessLookupError):
                    pass
        except (FileNotFoundError, ProcessLookupError):
            pass


def terminal(unit):
    need(re.fullmatch(r'bortus-worker1-[a-z0-9-]+\.service', unit), 'fixed_owned_unit')
    proc = subprocess.run(['systemctl', 'show', unit, '-p', 'LoadState', '-p', 'ActiveState', '-p', 'SubState',
                           '-p', 'Result', '-p', 'MainPID', '-p', 'ExecMainStatus', '-p', 'ControlGroup'],
                          capture_output=True, text=True, timeout=20)
    values = dict(line.split('=', 1) for line in proc.stdout.splitlines() if '=' in line)
    need(proc.returncode in [0, 4] and values.get('LoadState') in ['loaded', 'not-found'], 'unit_observation')
    need(values.get('ActiveState') == 'inactive' and values.get('MainPID', '0') == '0'
         and values.get('ControlGroup', '') == '' and values.get('ExecMainStatus', '0') == '0'
         and values.get('Result', 'success') == 'success', 'unit_not_successfully_terminal')
    return values


def load_contract():
    path = Path(__file__).resolve().parent / 'scan_contract.py'
    need(regular(path)['uid'] == 0, 'root_owned_contract')
    code_sha, contract_sha = digest(Path(__file__).resolve()), digest(path)
    need(path.parent == ROOT / 'helpers' / (code_sha + '-' + contract_sha), 'content_addressed_sources')
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('retirement_scan_contract', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, {'cleanupSHA256': code_sha, 'contractSHA256': contract_sha}


def original_proof(contract, scan):
    archive = Path(scan['originalArchive'])
    info = regular(archive)
    need(info['size'] == scan['originalArchiveBytes'] and 0 < info['size'] <= 4 * 1024 ** 3, 'original_archive_size')
    expected = scan['originalArchiveSHA256']
    need(re.fullmatch('[0-9a-f]{64}', expected) and digest(archive) == expected, 'whole_original_archive_sha256')
    service = scan['service']
    root = scan['ociIdentity']['originalRootDescriptor']['digest']
    need(re.fullmatch('sha256:[0-9a-f]{64}', root), 'original_root_descriptor')
    kind = scan.get('sourceKind', 'worker1')
    if kind == 'github-actions':
        prior = scan['ciProvenance']
        args = SimpleNamespace(service=service, ci_run_id=prior['runID'], ci_artifact_id=prior['artifactID'],
                               ci_provenance_sha256=prior['provenanceSHA256'], build_attempt='initial',
                               archive_sha256=expected, root_descriptor=root)
        parent = CI / (str(args.ci_run_id) + '-' + str(args.ci_artifact_id))
        need(archive == parent / (service + '.oci.tar'), 'fixed_ci_original_path')
        proof = contract.ci_receipts(parent, args, info['size'])
        need(proof == prior, 'original_ci_proof_changed')
    else:
        need(kind == 'worker1' and service == 'ytptube', 'fixed_worker_source')
        name = archive.parent.name
        need(re.fullmatch(r'ytptube(?:-r[1-9][0-9]{0,2})?', name), 'worker_attempt_path')
        build_attempt = 'initial' if name == 'ytptube' else name[len('ytptube-'):]
        parent = BUILDS / name
        need(archive == parent / 'ytptube-security-20261023.oci.tar', 'fixed_worker_original_path')
        args = SimpleNamespace(service=service, build_attempt=build_attempt,
                               archive_sha256=expected, root_descriptor=root)
        proof = contract.builder_receipts(parent, args, info['size'])
        for key, value in scan.get('builder', {}).items():
            need(key in proof and proof[key] == value, 'original_worker_proof_changed')
        terminal(proof['unit'])
    return {'archive': str(archive), 'archiveSHA256': expected, 'archiveIdentity': info,
            'sourceKind': kind, 'sourceProof': proof}


def reproducible(archive, scan):
    expected = {}
    with tarfile.open(archive, 'r:') as bundle:
        members = bundle.getmembers()
        need(len(members) <= 65536 and len({m.name for m in members}) == len(members), 'oci_member_count_or_duplicate')
        for m in members:
            need((m.isdir() or m.isfile()) and m.name in ['oci-layout', 'index.json', 'blobs', 'blobs/sha256']
                 or m.isfile() and re.fullmatch('blobs/sha256/[0-9a-f]{64}', m.name), 'oci_member_type_or_path')
        def small(name):
            item = bundle.getmember(name)
            need(item.isfile() and item.size <= 4 * 1024 ** 2, 'oci_metadata_size')
            return bundle.extractfile(item).read()
        need(json.loads(small('oci-layout')).get('imageLayoutVersion') == '1.0.0', 'original_layout')
        roots = json.loads(small('index.json')).get('manifests', [])
        need(len(roots) == 1 and {k: roots[0][k] for k in ['mediaType', 'digest', 'size']} ==
             scan['ociIdentity']['originalRootDescriptor'], 'original_index_root')
        verified, runtime = set(), []
        def blob(desc):
            value = desc.get('digest', '')
            need(re.fullmatch('sha256:[0-9a-f]{64}', value), 'blob_descriptor')
            member = bundle.getmember('blobs/sha256/' + value[7:])
            need(member.isfile() and member.size == desc['size'], 'original_blob_size')
            if value not in verified:
                hashed = hashlib.sha256()
                with bundle.extractfile(member) as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        need(True, 'operation_deadline')
                        hashed.update(block)
                need('sha256:' + hashed.hexdigest() == value, 'original_blob_sha256')
                verified.add(value)
            return value
        def walk(desc, depth=0):
            need(depth <= 8 and desc.get('mediaType') in INDEX | MANIFEST, 'oci_graph')
            blob(desc)
            obj = json.loads(small('blobs/sha256/' + desc['digest'][7:]))
            if desc['mediaType'] in INDEX:
                for child in obj.get('manifests', []):
                    walk(child, depth + 1)
            else:
                blob(obj['config'])
                for layer in obj.get('layers', []):
                    blob(layer)
                config = json.loads(small('blobs/sha256/' + obj['config']['digest'][7:]))
                if (config.get('os'), config.get('architecture')) == ('linux', 'amd64') and desc.get('annotations', {}).get('vnd.docker.reference.type') != 'attestation-manifest':
                    runtime.append((desc, obj))
        walk(roots[0])
        need(len(runtime) == 1, 'one_selected_runtime')
        desc, manifest = runtime[0]
        selected = {k: desc[k] for k in ['mediaType', 'digest', 'size']}
        selected['platform'] = {'os': 'linux', 'architecture': 'amd64'}
        need(selected == scan['ociIdentity']['selectedRuntimeManifest'], 'selected_runtime_identity')
        for descriptor in [desc, manifest['config'], *manifest.get('layers', [])]:
            expected['blobs/sha256/' + descriptor['digest'][7:]] = {'sha256': descriptor['digest'][7:], 'bytes': descriptor['size']}
        for name, data in [('oci-layout', b'{"imageLayoutVersion":"1.0.0"}'),
                           ('index.json', json.dumps({'schemaVersion': 2, 'manifests': [selected]}, separators=(',', ':')).encode())]:
            expected[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        need(expected['index.json']['sha256'] == scan['ociIdentity']['selectedIndexSHA256'] and
             expected['oci-layout']['sha256'] == scan['ociIdentity']['selectedLayoutSHA256'], 'reproduced_layout_metadata')
    return expected


def tree(path, expected):
    info = directory(path)
    no_mount_or_refs(path)
    files, dirs = {}, {}
    for base, names, filenames in os.walk(path, followlinks=False):
        for name in names:
            child = Path(base) / name
            relative = str(child.relative_to(path)).replace(os.sep, '/')
            need(relative in ['blobs', 'blobs/sha256'], 'unexpected_derived_directory')
            dirs[relative] = directory(child)
            need(dirs[relative]['dev'] == info['dev'], 'derived_cross_device')
        for name in filenames:
            child = Path(base) / name
            relative = str(child.relative_to(path)).replace(os.sep, '/')
            need(relative in expected, 'unexpected_derived_file')
            item = regular(child)
            need(item['dev'] == info['dev'] and item['size'] == expected[relative]['bytes']
                 and digest(child) == expected[relative]['sha256'], 'derived_reproduction_mismatch')
            files[relative] = {**expected[relative], 'identity': item}
    need(set(files) == set(expected) and set(dirs) == {'blobs', 'blobs/sha256'}, 'exact_derived_blobset')
    return {'root': info, 'directories': dirs, 'files': files,
            'logicalBytes': sum(v['bytes'] for v in files.values()),
            'allocatedBytes': sum(v['identity']['blocks'] * 512 for v in files.values())}


def preflight(contract, name):
    kind, size = ALLOWED[name]
    parent = SCANS / 'attempts' / name
    parent_info = directory(parent)
    scan, status_file = document(parent / 'status.json')
    service, attempt = name.rsplit('-', 1)
    need(scan.get('state') == 'scan_complete' and scan.get('scannerExitCode') == 0 and scan.get('endedUTC')
         and scan.get('service') == service and scan.get('attempt') == attempt
         and scan.get('sourceKind', 'worker1') == kind, 'successful_fixed_scan_required')
    unit = 'bortus-worker1-oci-scan-' + name + '.service'
    need(scan.get('unit') == unit, 'scan_unit_binding')
    unit_state = terminal(unit)
    results, result_file = document(parent / 'results.json', 128 * 1024 ** 2)
    need(scan.get('resultFile') == str(parent / 'results.json') and result_file['sha256'] == scan.get('resultSHA256')
         and isinstance(results, list) and results, 'completed_results_binding')
    report, report_file = document(parent / 'vulnerabilities.json', 128 * 1024 ** 2)
    rows = [v for item in results for v in item.get('Vulnerabilities') or []]
    need(scan.get('severityCounts') == dict(collections.Counter(v['Severity'] for v in rows))
         and scan.get('vulnerabilityRows') == len(rows) and len(report.get('rows', [])) == len(rows), 'result_counts')
    reconstructed = [{'target': item.get('Target'), 'type': item.get('Type'), **v}
                     for item in results for v in item.get('Vulnerabilities') or []]
    projection = {'target', 'type', 'VulnerabilityID', 'PkgName', 'PkgPath',
                  'InstalledVersion', 'FixedVersion', 'Severity', 'Status', 'PrimaryURL'}
    for retained, source in zip(report['rows'], reconstructed):
        # scan_oci.py deliberately uses v.get() for every projected field:
        # absent optional upstream fields are retained as JSON null.
        need(set(retained) == projection
             and all(source.get(key) == value for key, value in retained.items()), 'retained_vulnerability_rows_changed')
    need(report.get('archiveSHA256') == scan['originalArchiveSHA256'] and
         report.get('manifestDigest') == scan['ociIdentity']['selectedRuntimeManifest']['digest'] and
         report.get('database') == scan['inputs']['vulnerabilityDB'], 'preserved_vulnerability_report_binding')
    original = original_proof(contract, scan)
    expected = reproducible(original['archive'], scan)
    path = parent / 'selected-runtime.oci'
    need(scan['ociIdentity']['selectedLayoutDirectory'] == str(path), 'fixed_derived_path')
    materialized = tree(path, expected)
    need(materialized['logicalBytes'] == size, 'fixed_derived_byte_count')
    return {'name': name, 'parent': str(parent), 'parentIdentity': parent_info, 'path': str(path),
            'scanUnit': unit_state, 'scan': scan, 'retained': [status_file, result_file, report_file],
            'original': original, 'reproduction': expected, 'derived': materialized}


def save(run_fd, name, value):
    temporary = name + '.next-' + str(time.monotonic_ns())
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=run_fd)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, name, src_dir_fd=run_fd, dst_dir_fd=run_fd)
    os.fsync(run_fd)


def retained_unchanged(item):
    for proof in item['retained']:
        path = Path(proof['path'])
        need(regular(path) == proof['identity'] and digest(path) == proof['sha256'], 'retained_report_changed')
    original = item['original']
    path = Path(original['archive'])
    need(regular(path) == original['archiveIdentity'] and digest(path) == original['archiveSHA256'], 'retained_original_changed')


def delete_quarantined(path, plan, run_fd, record):
    checked = tree(path, plan['reproduction'])
    need(checked['files'] == plan['derived']['files'] and checked['directories'] == plan['derived']['directories']
         and all(checked['root'][k] == plan['derived']['root'][k] for k in ['dev', 'ino', 'mode', 'uid', 'gid']), 'quarantined_identity_changed')
    root_fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for relative, proof in sorted(checked['files'].items()):
            parent_name, filename = os.path.split(relative)
            parent_fd = os.open(parent_name or '.', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
            try:
                need(identity(os.stat(filename, dir_fd=parent_fd, follow_symlinks=False)) == proof['identity'], 'pre_unlink_identity')
                os.unlink(filename, dir_fd=parent_fd)
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
            record['removedFiles'].append({'attempt': plan['name'], 'relative': relative, **proof})
            save(run_fd, 'status.json', record)
        blobs_fd = os.open('blobs', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        try:
            os.rmdir('sha256', dir_fd=blobs_fd)
            os.fsync(blobs_fd)
        finally:
            os.close(blobs_fd)
        os.rmdir('blobs', dir_fd=root_fd)
        os.fsync(root_fd)
    finally:
        os.close(root_fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['review', 'retire', 'status'])
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    need(os.geteuid() == 0 and socket.gethostname() == 'workernode1', 'worker1_root_operator_only')
    need(re.fullmatch('[0-9a-f]{12}', args.run_id), 'run_identity')
    os.umask(0o077)
    os.nice(10)
    subprocess.run(['ionice', '-c', '3', '-p', str(os.getpid())], check=True, capture_output=True, timeout=10)
    contract, sources = load_contract()
    directory(ROOT)
    run = ROOT / 'runs' / args.run_id
    if args.phase == 'status':
        value, proof = document(run / 'status.json')
        print(json.dumps({'state': value['state'], 'receipt': proof['path'], 'receiptSHA256': proof['sha256'],
                          'removedFiles': len(value.get('removedFiles', [])), 'removedLogicalBytes': value.get('removedLogicalBytes', 0)}))
        return
    run.mkdir(mode=0o700)
    run_fd = os.open(run, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    record = {'state': 'preflight', 'startedUTC': utc(), 'phase': args.phase, 'sourceHashes': sources,
              'cleanupPID': os.getpid(),
              'fixedAttempts': list(ALLOWED), 'removedFiles': [], 'removedLogicalBytes': 0}
    save(run_fd, 'status.json', record)
    try:
        lock_fd = os.open(SCANS / 'scan.lock', os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(lock_fd, 'rb') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            plans = []
            for name in ALLOWED:
                record['checkingAttempt'] = name
                save(run_fd, 'status.json', record)
                plans.append(preflight(contract, name))
            save(run_fd, 'preflight.json', {'verifiedUTC': utc(), 'plans': plans, 'sourceHashes': sources})
            record.update(state='all_verified', eligibleLogicalBytes=sum(p['derived']['logicalBytes'] for p in plans),
                          eligibleAllocatedBytes=sum(p['derived']['allocatedBytes'] for p in plans),
                          filesystemBefore=dict(zip(['blocks', 'bavail', 'frsize'], [os.statvfs(ROOT).f_blocks, os.statvfs(ROOT).f_bavail, os.statvfs(ROOT).f_frsize])))
            save(run_fd, 'status.json', record)
            if args.phase == 'retire':
                os.mkdir('quarantine', 0o700, dir_fd=run_fd)
                quarantine_fd = os.open('quarantine', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=run_fd)
                try:
                    for plan in plans:
                        record.update(state='retiring', checkingAttempt=plan['name'])
                        retained_unchanged(plan)
                        terminal('bortus-worker1-oci-scan-' + plan['name'] + '.service')
                        path = Path(plan['path'])
                        need(directory(path) == plan['derived']['root'], 'pre_rename_directory_changed')
                        no_mount_or_refs(path)
                        parent_fd = os.open(plan['parent'], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                        try:
                            need(all(identity(os.fstat(parent_fd))[k] == plan['parentIdentity'][k] for k in ['dev', 'ino', 'mode', 'uid', 'gid']), 'attempt_parent_identity')
                            need(os.fstat(parent_fd).st_dev == os.fstat(quarantine_fd).st_dev, 'same_filesystem_quarantine')
                            os.rename('selected-runtime.oci', plan['name'], src_dir_fd=parent_fd, dst_dir_fd=quarantine_fd)
                            os.fsync(parent_fd)
                            os.fsync(quarantine_fd)
                        finally:
                            os.close(parent_fd)
                        record['quarantinedAttempt'] = plan['name']
                        save(run_fd, 'status.json', record)
                        destination = run / 'quarantine' / plan['name']
                        delete_quarantined(destination, plan, run_fd, record)
                        os.rmdir(plan['name'], dir_fd=quarantine_fd)
                        os.fsync(quarantine_fd)
                        record['removedLogicalBytes'] += plan['derived']['logicalBytes']
                        retained_unchanged(plan)
                        save(run_fd, 'status.json', record)
                finally:
                    os.close(quarantine_fd)
            record.update(state='retired' if args.phase == 'retire' else 'reviewed_no_deletion', endedUTC=utc(),
                          filesystemAfter=dict(zip(['blocks', 'bavail', 'frsize'], [os.statvfs(ROOT).f_blocks, os.statvfs(ROOT).f_bavail, os.statvfs(ROOT).f_frsize])))
            save(run_fd, 'status.json', record)
    except Exception as error:
        category = str(error) if isinstance(error, ValueError) and re.fullmatch('[a-z0-9_]+', str(error)) else 'retirement_refused_or_interrupted'
        record.update(state='refused_or_partial_preserved', endedUTC=utc(), failureCategory=category)
        save(run_fd, 'status.json', record)
        raise SystemExit(1)
    finally:
        os.close(run_fd)
    print(json.dumps({'state': record['state'], 'runID': args.run_id, 'receipt': str(run / 'status.json'),
                      'receiptSHA256': digest(run / 'status.json'), 'removedLogicalBytes': record['removedLogicalBytes']}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Derived OCI retirement refused; preserved receipt contains fixed-category diagnostics')
