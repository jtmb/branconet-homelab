"""Offline exact-OCI vulnerability scanning; never execute/import an application image."""
import argparse
import collections
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import signal
import socket
import stat
import subprocess
import tarfile
import time

BASE = Path('/home/james/.local/share/branconet-migration')
ROOT = BASE / 'worker1-oci-scan-20261023'
HELPER_ROOT = Path(__file__).resolve().parent
SEAL = HELPER_ROOT / 'inputs.json'
BUILDS = BASE / 'worker1-image-build-20261023'
CI_ARTIFACTS = BASE / 'ci-image-artifacts-20261024'
SERVICES = ['seerr', 'ytptube', 'jackett', 'pihole', 'flaresolverr', 'vaultwarden', 'tautulli']
SEERR_CI_LOCK_SHA = '9665b245267e7c864210bdf85f1098c0891f30946c64b3781f44077fff0b7811'
TOOL_SHA = 'd1dfca6ae10a1ad4540bb94e64f0510077c47008920a9b554986b39dca573d83'
DB_FILES = {
    'db/trivy.db': (1628737536, '6fd7f9c44ff3120e0d15d5b5b2234e1ff1c9e7a6b56b4e776041f93faf1f6f17'),
    'db/metadata.json': (150, 'd2caf386c5ec60a3fc13376aebe5cd9a236f4c20940e3eec361d4c51c544bce9'),
    'java-db/trivy-java.db': (1560596480, '728fa5500d93bb1a592f8477b8a2c9494c712bcfe6b603c9fef5386d5433cc3d'),
    'java-db/metadata.json': (153, '0f5c76eb37d3cee66cb7da09f8238dd5bab2b0d0eb5f05cf37006af7a4234957'),
}
INDEX = {'application/vnd.oci.image.index.v1+json', 'application/vnd.docker.distribution.manifest.list.v2+json'}
MANIFEST = {'application/vnd.oci.image.manifest.v1+json', 'application/vnd.docker.distribution.manifest.v2+json'}
OWNER = pwd.getpwnam('james')


def require(value, category):
    if not value:
        raise ValueError(category)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for b in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def protected(path, directory=False):
    require(path.is_absolute() and path.resolve() == path and not path.is_symlink(), 'input_path_identity')
    s = path.stat()
    require(s.st_uid in [0, OWNER.pw_uid] and not stat.S_IMODE(s.st_mode) & 0o077, 'input_permissions')
    require(stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode), 'input_type')


def publish(path):
    os.chmod(path, 0o600)
    os.chown(path, OWNER.pw_uid, OWNER.pw_gid)


def save(path, data):
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w') as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    publish(temp)
    temp.replace(path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def reserve(extra=0):
    v = os.statvfs(ROOT)
    capacity = v.f_frsize * v.f_blocks
    available = v.f_frsize * v.f_bavail
    floor = capacity // 4 + 8 * 1024 ** 3
    require(available >= floor + extra, 'filesystem_reserve_below_25percent_plus_8GiB')
    require(v.f_favail >= max(250000, v.f_files // 10), 'inode_reserve')
    return {'capacityBytes': capacity, 'nonrootAvailableBytes': available,
            'requiredAvailableBytes': floor, 'freeInodes': v.f_favail}


def inputs():
    protected(ROOT, True)
    protected(HELPER_ROOT, True)
    protected(Path(__file__))
    require(HELPER_ROOT == ROOT / 'helpers' / digest(Path(__file__)), 'content_addressed_helper_identity')
    require(HELPER_ROOT.stat().st_uid == 0 and Path(__file__).stat().st_uid == 0, 'root_owned_helper_version')
    protected(ROOT / 'bin/trivy')
    require(digest(ROOT / 'bin/trivy') == TOOL_SHA, 'tool_sha256')
    for relative, (size, sha) in DB_FILES.items():
        p = ROOT / 'cache' / relative
        protected(p)
        require(p.stat().st_size == size and digest(p) == sha, 'database_identity')
    require((ROOT / 'no-ignore').read_bytes() == b'', 'ignore_file_must_be_empty')
    require((ROOT / 'trivy-empty.yaml').read_bytes() == b'{}\n', 'scanner_configuration')
    require((ROOT / 'results.tpl').read_text().strip() == '{{ toJson . }}', 'results_only_template')
    return {'trivyVersion': '0.76.1', 'trivySHA256': TOOL_SHA,
            'release': 'https://github.com/aquasecurity/trivy/releases/tag/v0.76.1',
            'files': {name: {'bytes': value[0], 'sha256': value[1]} for name, value in DB_FILES.items()},
            'vulnerabilityDB': json.loads((ROOT / 'cache/db/metadata.json').read_text()),
            'javaDB': json.loads((ROOT / 'cache/java-db/metadata.json').read_text()),
            'helperSHA256': digest(Path(__file__)), 'templateSHA256': digest(ROOT / 'results.tpl')}


def age_hours(metadata):
    value = re.sub(r'(\.\d{6})\d+(?=[+-]|$)', r'\1', metadata['UpdatedAt'].replace('Z', '+00:00'))
    updated = datetime.datetime.fromisoformat(value)
    return (datetime.datetime.now(datetime.timezone.utc) - updated).total_seconds() / 3600


def unit_state(unit):
    p = subprocess.run(['systemctl', 'show', unit, '-p', 'ActiveState', '-p', 'SubState', '-p', 'Result',
                        '-p', 'MainPID', '-p', 'ControlGroup', '-p', 'MemoryMax', '-p', 'MemorySwapMax',
                        '-p', 'CPUQuotaPerSecUSec', '-p', 'TasksMax', '-p', 'PrivateNetwork', '-p', 'NoNewPrivileges'],
                       capture_output=True, text=True, timeout=15)
    require(p.returncode == 0, 'unit_metadata')
    return dict(line.split('=', 1) for line in p.stdout.splitlines() if '=' in line)


def limits(unit):
    state = unit_state(unit)
    cg = state.get('ControlGroup', '')
    require(cg == '/system.slice/' + unit, 'owned_cgroup')
    require(Path('/proc/self/cgroup').read_text().strip() == '0::' + cg, 'actual_process_cgroup')
    base = Path('/sys/fs/cgroup') / cg.lstrip('/')
    observed = {name: (base / name).read_text().strip()
                for name in ['memory.max', 'memory.swap.max', 'cpu.max', 'pids.max']}
    require(observed['memory.max'] == '1073741824' and observed['memory.swap.max'] == '0', 'memory_cgroup')
    quota, period = observed['cpu.max'].split()
    require(quota != 'max' and int(quota) <= 2 * int(period), 'cpu_cgroup')
    require(observed['pids.max'] == '128', 'tasks_cgroup')
    require(state['PrivateNetwork'] == 'yes' and state['NoNewPrivileges'] == 'yes', 'unit_isolation')
    require(os.environ.get('GOMAXPROCS') == '2' and os.environ.get('GOMEMLIMIT') == '512MiB', 'go_limits')
    require(os.getpriority(os.PRIO_PROCESS, 0) == 10, 'nice_limit')
    return {'unit': state, 'cgroupFiles': observed,
            'memoryEvents': (base / 'memory.events').read_text().strip()}


def selected_layout(archive, root_digest, output):
    """Materialize validated OCI blobs, never unpack an image layer filesystem."""
    with tarfile.open(archive, mode='r:') as bundle:
        members = bundle.getmembers()
        require(len(members) <= 65536 and len({m.name for m in members}) == len(members), 'ambiguous_oci_members')
        for m in members:
            require(m.isdir() or m.isfile(), 'oci_links_or_special_files')
            require(m.name in ['oci-layout', 'index.json', 'blobs', 'blobs/sha256'] or
                    re.fullmatch(r'blobs/sha256/[0-9a-f]{64}', m.name), 'unexpected_oci_member')
        def small(name):
            m = bundle.getmember(name)
            require(m.isfile() and m.size <= 4 * 1024 * 1024, 'oci_metadata_size')
            return bundle.extractfile(m).read()
        require(json.loads(small('oci-layout')).get('imageLayoutVersion') == '1.0.0', 'oci_layout')
        roots = json.loads(small('index.json')).get('manifests', [])
        require(len(roots) == 1 and roots[0].get('digest') == root_digest, 'exact_unique_root_descriptor_required')
        seen = set()
        runtime = []
        def verify_blob(desc):
            d = desc.get('digest', '')
            require(re.fullmatch(r'sha256:[0-9a-f]{64}', d), 'descriptor_digest')
            m = bundle.getmember('blobs/sha256/' + d[7:])
            require(m.isfile() and m.size == desc.get('size'), 'descriptor_size')
            if d not in seen:
                h = hashlib.sha256()
                with bundle.extractfile(m) as stream:
                    for b in iter(lambda: stream.read(1024 * 1024), b''):
                        h.update(b)
                require('sha256:' + h.hexdigest() == d, 'descriptor_content_sha256')
                seen.add(d)
            return m
        def walk(desc, depth=0):
            require(depth <= 8, 'oci_index_depth')
            verify_blob(desc)
            media = desc.get('mediaType')
            require(media in INDEX | MANIFEST, 'unsupported_root_or_manifest_media_type')
            obj = json.loads(small('blobs/sha256/' + desc['digest'][7:]))
            if media in INDEX:
                for child in obj.get('manifests', []):
                    walk(child, depth + 1)
            else:
                config = obj['config']
                verify_blob(config)
                cfg = json.loads(small('blobs/sha256/' + config['digest'][7:]))
                for layer in obj.get('layers', []):
                    verify_blob(layer)
                attestation = desc.get('annotations', {}).get('vnd.docker.reference.type') == 'attestation-manifest'
                if cfg.get('os') == 'linux' and cfg.get('architecture') == 'amd64' and not attestation:
                    runtime.append((desc, obj, {'architecture': 'amd64', 'os': 'linux'}))
        walk(roots[0])
        require(len(runtime) == 1, 'one_linux_amd64_runtime_manifest_required')
        desc, manifest, metadata = runtime[0]
        clean_desc = {k: desc[k] for k in ['mediaType', 'digest', 'size']}
        clean_desc['platform'] = {'os': 'linux', 'architecture': 'amd64'}
        index = {'schemaVersion': 2, 'manifests': [clean_desc]}
        keep = {d['digest'] for d in [desc, manifest['config'], *manifest.get('layers', [])]}
        output.mkdir(mode=0o700)
        (output / 'blobs').mkdir(mode=0o700)
        (output / 'blobs/sha256').mkdir(mode=0o700)
        for name, data in [('oci-layout', b'{"imageLayoutVersion":"1.0.0"}'),
                           ('index.json', json.dumps(index, separators=(',', ':')).encode())]:
            path = output / name
            with path.open('xb') as destination:
                destination.write(data)
            publish(path)
        for d in sorted(keep):
            member = bundle.getmember('blobs/sha256/' + d[7:])
            path = output / member.name
            with bundle.extractfile(member) as source, path.open('xb') as destination:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    destination.write(chunk)
            publish(path)
            require(path.stat().st_size == member.size and 'sha256:' + digest(path) == d, 'materialized_blob_identity')
        return {'originalRootDescriptor': {k: roots[0][k] for k in ['mediaType', 'digest', 'size']}, 'selectedRuntimeManifest': clean_desc,
                'selectedConfigDigest': manifest['config']['digest'], 'platform': 'linux/amd64',
                'selectedMetadata': metadata, 'allRootReachableBlobsVerified': len(seen),
                'scannedRuntimeBlobCount': len(keep), 'selectedLayoutDirectory': str(output),
                'selectedIndexSHA256': digest(output / 'index.json'), 'selectedLayoutSHA256': digest(output / 'oci-layout'),
                'scope': 'Only the exact selected linux/amd64 runtime image; other platform images/attestations are identity-verified but not vulnerability-scanned.'}


def builder_receipts(root, args, size):
    suffix = '' if args.build_attempt == 'initial' else '-' + args.build_attempt
    prefix = 'bortus-worker1-' + args.service + '-build-20261023' + suffix
    data = {}
    hashes = {}
    for name in ['build-inputs.json', 'runtime-started.json', 'runtime-finished.json', 'runtime-build-metadata.json']:
        path = root / name
        protected(path)
        require(path.stat().st_size <= 4 * 1024 ** 2, 'builder_receipt_size')
        data[name] = json.loads(path.read_text())
        hashes[name] = digest(path)
    seal, started, finished, metadata = [data[n] for n in data]
    require(seal.get('root') == str(root) and seal.get('service') == args.service and
            seal.get('attempt', 'initial') == args.build_attempt and seal.get('unit_prefix') == prefix,
            'builder_seal_scope')
    require(started.get('service') == args.service and started.get('phase') == 'runtime' and
            started.get('cgroup') == '/system.slice/' + prefix + '-runtime.service', 'builder_started_scope')
    require(finished.get('service') == args.service and finished.get('phase') == 'runtime' and
            finished.get('exit_code') == 0 and not finished.get('error_type') and
            not finished.get('capacity_abort') and finished.get('oci_sha256') == args.archive_sha256 and
            finished.get('oci_bytes') == size and finished.get('completed_at'), 'successful_exact_builder_receipt_required')
    require(metadata.get('containerimage.digest') == args.root_descriptor, 'builder_root_descriptor_mismatch')
    return {'buildAttempt': args.build_attempt, 'root': str(root), 'unit': prefix + '-runtime.service',
            'receiptSHA256': hashes, 'completedUTC': finished['completed_at'],
            'rootDescriptor': metadata['containerimage.digest']}


def ci_root(args):
    require(type(args.ci_run_id) is int and 0 < args.ci_run_id < 2 ** 63 and
            type(args.ci_artifact_id) is int and 0 < args.ci_artifact_id < 2 ** 63,
            'ci_positive_run_and_artifact_ids_required')
    require(re.fullmatch('[0-9a-f]{64}', args.ci_provenance_sha256), 'ci_provenance_sha256_required')
    require(args.build_attempt == 'initial', 'ci_source_has_no_local_build_attempt')
    return CI_ARTIFACTS / (str(args.ci_run_id) + '-' + str(args.ci_artifact_id))


def ci_owned(path, directory=False):
    protected(path, directory)
    info = path.stat()
    require(info.st_uid == 0 and stat.S_IMODE(info.st_mode) == (0o700 if directory else 0o400),
            'ci_inputs_must_be_root_owned_0700_directories_or_0400_files')
    require(directory or info.st_nlink == 1, 'ci_input_hardlinks_forbidden')
    return info


def ci_receipts(root, args, size):
    """Validate original CI proof files; never synthesize local builder receipts."""
    require(root == ci_root(args), 'fixed_ci_artifact_root')
    ci_owned(CI_ARTIFACTS, True)
    ci_owned(root, True)
    provenance_path = root / 'provenance.json'
    ci_owned(provenance_path)
    require(provenance_path.stat().st_size <= 4 * 1024 ** 2 and
            digest(provenance_path) == args.ci_provenance_sha256, 'ci_provenance_identity')
    proof = json.loads(provenance_path.read_text())
    require(proof.get('schemaVersion') == 1 and proof.get('sourceKind') == 'github-actions', 'ci_provenance_schema')
    github = proof['github']
    repository, workflow, run_data, job, artifact = [github[k] for k in ['repository', 'workflow', 'run', 'job', 'artifact']]
    require(repository.get('full_name') == 'jtmb/branconet-charts' and repository.get('private') is True,
            'private_charts_repository_required')
    require(workflow.get('path') == '.github/workflows/build-security-images.yml', 'ci_workflow_path')
    head = run_data.get('head_sha', '')
    run_attempt = run_data.get('run_attempt')
    require(re.fullmatch('[0-9a-f]{40}', head) and type(run_attempt) is int and run_attempt > 0,
            'ci_head_and_run_attempt')
    require(run_data.get('id') == args.ci_run_id and run_data.get('event') == 'workflow_dispatch' and
            run_data.get('status') == 'completed' and run_data.get('conclusion') == 'success', 'successful_ci_run_required')
    require(type(job.get('id')) is int and job['id'] > 0 and job.get('run_id') == args.ci_run_id and
            job.get('head_sha') == head and job.get('name') == 'build' and
            job.get('status') == 'completed' and job.get('conclusion') == 'success', 'successful_matching_ci_job_required')
    zip_proof = proof['outerZip']
    zip_sha = zip_proof.get('sha256', '')
    require(re.fullmatch('[0-9a-f]{64}', zip_sha) and type(zip_proof.get('bytes')) is int and
            0 < zip_proof['bytes'] <= 8 * 1024 ** 3, 'outer_zip_identity')
    require(artifact.get('id') == args.ci_artifact_id and artifact.get('expired') is False and
            artifact.get('name') == 'security-' + args.service + '-' + head + '-' + str(args.ci_run_id) + '-' + str(run_attempt) and
            artifact.get('size_in_bytes') == zip_proof['bytes'] and artifact.get('digest') == 'sha256:' + zip_sha and
            artifact.get('workflow_run', {}).get('id') == args.ci_run_id and
            artifact.get('workflow_run', {}).get('head_sha') == head, 'matching_ci_artifact_required')
    caps = {name: 4 * 1024 ** 2 for name in ['result.json', 'preflight.json', 'builder-host-limits.json',
                                           'builder-limits.json', 'runtime-inputs-sha256.json']}
    archive_name = args.service + '.oci.tar'
    caps[archive_name] = 4 * 1024 ** 3
    if args.service == 'seerr':
        caps['pnpm-lock.yaml'] = 16 * 1024 ** 2
    files = proof['files']
    require(isinstance(files, dict) and set(files) == set(caps), 'ci_proof_file_allowlist')
    data = {}
    for name, cap in caps.items():
        path = root / name
        info = ci_owned(path)
        expected = files[name]
        require(type(expected.get('bytes')) is int and 0 < info.st_size == expected['bytes'] <= cap and
                re.fullmatch('[0-9a-f]{64}', expected.get('sha256', '')), 'ci_proof_file_size_or_digest')
        if name == archive_name:
            # The common scan path independently hashes every archive byte.
            require(info.st_size == size and expected['sha256'] == args.archive_sha256, 'ci_archive_binding')
        else:
            require(digest(path) == expected['sha256'], 'original_uploaded_ci_file_sha256')
            if name.endswith('.json'):
                data[name] = json.loads(path.read_text())
    result = data['result.json']
    require(result.get('state') == 'artifact-built-not-qualified-not-deployed' and
            result.get('source_commit') == head and result.get('service') == args.service and
            result.get('archive_sha256') == args.archive_sha256 and result.get('archive_bytes') == size,
            'successful_exact_uploaded_result_required')
    roots = result.get('oci_index', {}).get('manifests', [])
    require(len(roots) == 1 and roots[0].get('digest') == args.root_descriptor, 'ci_result_root_descriptor')
    runtime_inputs = data['runtime-inputs-sha256.json']
    require(isinstance(runtime_inputs, dict) and 0 < len(runtime_inputs) <= 256 and 'Dockerfile' in runtime_inputs,
            'ci_runtime_input_manifest')
    require(all(isinstance(name, str) and name and not name.startswith('/') and
                '..' not in Path(name).parts and '\x00' not in name and
                isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value)
                for name, value in runtime_inputs.items()), 'ci_runtime_input_manifest_entries')
    if args.service == 'seerr':
        require(result.get('frozen_lock_sha256') == SEERR_CI_LOCK_SHA and
                files['pnpm-lock.yaml']['sha256'] == SEERR_CI_LOCK_SHA and
                runtime_inputs.get('pnpm-lock.yaml') == SEERR_CI_LOCK_SHA, 'reviewed_ci_seerr_frozen_lock')
    else:
        require(result.get('frozen_lock_sha256') is None, 'unexpected_ci_lock_contract')
    container = 'buildx_buildkit_security-' + str(args.ci_run_id) + '-' + str(run_attempt) + '0'
    expected_limits = {'Memory': 3 * 1024 ** 3, 'MemorySwap': 3 * 1024 ** 3,
                       'CpuPeriod': 100000, 'CpuQuota': 150000, 'CpusetCpus': '0-1', 'PidsLimit': 512}
    host_limits = data['builder-host-limits.json']
    effective = data['builder-limits.json']
    require(host_limits.get('container') == container and host_limits.get('expected') == expected_limits and
            host_limits.get('actual') == expected_limits, 'ci_actual_builder_host_limits')
    require(effective.get('container') == container and effective.get('host_config') == expected_limits and
            effective.get('effective_cgroup_v2') == ['3221225472', '0', '150000 100000', '0-1', '512'],
            'ci_actual_effective_cgroup_limits')
    preflight = data['preflight.json']
    require(preflight.get('source_commit') == head and preflight.get('service') == args.service and
            str(preflight.get('run_id')) == str(args.ci_run_id) and str(preflight.get('run_attempt')) == str(run_attempt) and
            preflight.get('reserve_bytes') == 2 * 1024 ** 3 and preflight.get('build_budget_bytes') == 12 * 1024 ** 3 and
            preflight.get('max_oci_bytes') == 4 * 1024 ** 3, 'ci_source_and_build_capacity_contract')
    capacity = preflight.get('capacity', [])
    require(len(capacity) == 2 and all(c.get('available_bytes', 0) >= 18 * 1024 ** 3 and
            c.get('free_inode_fraction', 0) >= .10 for c in capacity), 'ci_original_capacity_preflight')
    docker = preflight.get('docker_storage', {})
    require(docker.get('free', 0) >= 18 * 1024 ** 3 and docker.get('inodes', 0) >= .10,
            'ci_original_docker_capacity_preflight')
    archive_info = (root / archive_name).stat()
    return {'sourceKind': 'github-actions', 'repository': 'jtmb/branconet-charts', 'private': True,
            'workflowPath': workflow['path'], 'runID': args.ci_run_id, 'runAttempt': run_attempt,
            'jobID': job['id'], 'headSHA': head, 'conclusion': 'success',
            'artifactID': args.ci_artifact_id, 'artifactName': artifact['name'],
            'outerZipSHA256': zip_sha, 'outerZipBytes': zip_proof['bytes'],
            'provenanceSHA256': args.ci_provenance_sha256, 'uploadedFiles': files,
            'rootDescriptor': args.root_descriptor, 'frozenLockSHA256': result.get('frozen_lock_sha256'),
            'actualBuildHostLimits': expected_limits, 'effectiveBuildCgroup': effective['effective_cgroup_v2'],
            'archiveIdentity': [archive_info.st_dev, archive_info.st_ino, archive_info.st_size,
                                archive_info.st_mtime_ns, archive_info.st_ctime_ns],
            'verificationBoundary': 'Operator verified authenticated GitHub API metadata and outer ZIP bytes; this offline scanner independently verifies staged proof files and OCI contents.'}


def run(args):
    require(re.fullmatch('[0-9a-f]{12}', args.attempt), 'attempt_identity')
    unit = 'bortus-worker1-oci-scan-' + args.service + '-' + args.attempt + '.service'
    attempt = ROOT / 'attempts' / (args.service + '-' + args.attempt)
    attempt.mkdir(mode=0o700)
    os.chown(attempt, OWNER.pw_uid, OWNER.pw_gid)
    record = {'state': 'verifying', 'startedUTC': utc(), 'service': args.service,
              'attempt': args.attempt, 'unit': unit, 'runnerPID': os.getpid(), 'sourceKind': args.source_kind,
              'applicationExecuted': False, 'imageImported': False, 'secretScannerEnabled': False,
              'securityAcceptance': False}
    receipt = attempt / 'status.json'
    save(receipt, record)
    scanner = None
    try:
        with (ROOT / 'scan.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            record['resourceLimits'] = limits(unit)
            record['inputs'] = inputs()
            db_age = age_hours(record['inputs']['vulnerabilityDB'])
            record['databaseAgeHours'] = db_age
            require(0 <= db_age <= 24, 'pinned_vulnerability_database_older_than_24_hours')
            if args.source_kind == 'github-actions':
                build_root = ci_root(args)
                archive = build_root / (args.service + '.oci.tar')
            else:
                require(not args.ci_run_id and not args.ci_artifact_id and not args.ci_provenance_sha256,
                        'worker_source_does_not_accept_ci_identity')
                require(re.fullmatch(r'initial|r[1-9][0-9]{0,2}', args.build_attempt), 'build_attempt_identity')
                build_root = BUILDS / (args.service + ('' if args.build_attempt == 'initial' else '-' + args.build_attempt))
                archive = build_root / (args.service + '-security-20261023.oci.tar')
            protected(archive)
            protected(archive.parent, True)
            require(re.fullmatch('[0-9a-f]{64}', args.archive_sha256), 'archive_sha256_required')
            require(re.fullmatch('sha256:[0-9a-f]{64}', args.root_descriptor), 'root_descriptor_required')
            initial = archive.stat()
            require(0 < initial.st_size <= 4 * 1024 ** 3, 'archive_size_limit')
            if args.source_kind == 'github-actions':
                record['ciProvenance'] = ci_receipts(build_root, args, initial.st_size)
            else:
                record['builder'] = builder_receipts(build_root, args, initial.st_size)
            record['filesystemBefore'] = reserve(initial.st_size * 2)
            require(digest(archive) == args.archive_sha256, 'original_archive_sha256')
            record.update(originalArchive=str(archive), originalArchiveBytes=initial.st_size,
                          originalArchiveSHA256=args.archive_sha256)
            derived = attempt / 'selected-runtime.oci'
            record['ociIdentity'] = selected_layout(archive, args.root_descriptor, derived)
            final = archive.stat()
            require((initial.st_ino, initial.st_size, initial.st_mtime_ns) ==
                    (final.st_ino, final.st_size, final.st_mtime_ns), 'archive_changed_during_verification')
            if args.source_kind == 'github-actions':
                require(ci_receipts(build_root, args, initial.st_size) == record['ciProvenance'], 'ci_provenance_changed')
            else:
                require(builder_receipts(build_root, args, initial.st_size) == record['builder'], 'builder_receipts_changed')
            reserve()
            for p in Path('/proc').iterdir():
                if p.name.isdigit():
                    try:
                        require((p / 'comm').read_text().strip() != 'trivy', 'another_scanner_is_running')
                    except (FileNotFoundError, ProcessLookupError):
                        pass
            output = attempt / 'results.json'
            stderr = attempt / 'scanner.stderr'
            cmd = [str(ROOT / 'bin/trivy'), 'image', '--input', str(derived), '--platform', 'linux/amd64',
                   '--config', str(ROOT / 'trivy-empty.yaml'), '--cache-dir', str(ROOT / 'cache'),
                   '--scanners', 'vuln', '--offline-scan', '--skip-db-update', '--skip-java-db-update',
                   '--ignorefile', str(ROOT / 'no-ignore'), '--timeout', '7m', '--parallel', '2',
                   '--quiet', '--no-progress', '--format', 'template', '--template', '@' + str(ROOT / 'results.tpl'),
                   '--output', str(output)]
            env = {'PATH': '/usr/bin:/bin', 'HOME': str(ROOT / 'home'), 'DOCKER_CONFIG': str(ROOT / 'docker-config'),
                   'TMPDIR': str(ROOT / 'tmp'), 'XDG_CACHE_HOME': str(ROOT / 'cache'),
                   'GOMAXPROCS': '2', 'GOMEMLIMIT': '512MiB', 'LANG': 'C', 'LC_ALL': 'C'}
            with stderr.open('xb') as errors:
                scanner = subprocess.Popen(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.DEVNULL, stderr=errors, start_new_session=True)
                record.update(state='scanning', scannerPID=scanner.pid, scannerCommand=cmd,
                              reportRedaction='Template receives Results only; full image config, Env, command/history and arbitrary labels are never serialized into the structured scanner report.')
                save(receipt, record)
                started = time.monotonic()
                while scanner.poll() is None:
                    try:
                        reserve()
                        require(time.monotonic() - started < 480, 'scanner_480_second_timeout')
                    except Exception:
                        os.killpg(scanner.pid, signal.SIGTERM)
                        try:
                            scanner.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            os.killpg(scanner.pid, signal.SIGKILL)
                            scanner.wait()
                        raise
                    time.sleep(2)
            record['scannerExitCode'] = scanner.returncode
            publish(stderr)
            require(scanner.returncode == 0, 'scanner_failed_not_clean')
            publish(output)
            results = json.loads(output.read_text())
            require(isinstance(results, list) and results, 'no_component_coverage_not_clean')
            rows = []
            for target in results:
                require(not target.get('Secrets') and not target.get('Misconfigurations'), 'scanner_scope_violation')
                for v in target.get('Vulnerabilities') or []:
                    rows.append({'target': target.get('Target'), 'type': target.get('Type'),
                                 **{k: v.get(k) for k in ['VulnerabilityID', 'PkgName', 'PkgPath', 'InstalledVersion',
                                                        'FixedVersion', 'Severity', 'Status', 'PrimaryURL']}})
            record.update(state='scan_complete', endedUTC=utc(), resultFile=str(output), resultSHA256=digest(output),
                          resultTypes=sorted({x.get('Type', '') for x in results}),
                          severityCounts=dict(collections.Counter(x['Severity'] for x in rows)),
                          vulnerabilityRows=len(rows),
                          fixedCriticalHighRows=sum(x['Severity'] in ['CRITICAL', 'HIGH'] and bool(x['FixedVersion']) for x in rows),
                          unfixedCriticalHighRows=sum(x['Severity'] in ['CRITICAL', 'HIGH'] and not x['FixedVersion'] for x in rows),
                          filesystemAfter=reserve())
            save(attempt / 'vulnerabilities.json', {'archiveSHA256': args.archive_sha256,
                                                  'manifestDigest': record['ociIdentity']['selectedRuntimeManifest']['digest'],
                                                  'database': record['inputs']['vulnerabilityDB'], 'rows': rows})
            require(inputs() == record['inputs'], 'sealed_scanner_inputs_changed')
            if args.source_kind == 'github-actions':
                require(ci_receipts(build_root, args, initial.st_size) == record['ciProvenance'], 'ci_provenance_changed_during_scan')
            record['resourceLimitsAfter'] = limits(unit)
            save(receipt, record)
    except Exception as error:
        if scanner is not None and scanner.poll() is None:
            os.killpg(scanner.pid, signal.SIGTERM)
            try:
                scanner.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(scanner.pid, signal.SIGKILL)
                scanner.wait()
        record.update(state='scan_failed_not_clean', endedUTC=utc(), errorCategory=str(error) if isinstance(error, ValueError) else type(error).__name__)
        try:
            record['resourceLimitsAfter'] = limits(unit)
        except Exception:
            pass
        save(receipt, record)
        raise
    print(json.dumps({'state': record['state'], 'receipt': str(receipt), 'unit': unit,
                      'severityCounts': record.get('severityCounts'), 'securityAcceptance': False}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=['setup', 'run', 'status'])
    p.add_argument('--service', choices=SERVICES)
    p.add_argument('--attempt', default='')
    p.add_argument('--build-attempt', default='initial')
    p.add_argument('--source-kind', choices=['worker1', 'github-actions'], default='worker1')
    p.add_argument('--ci-run-id', type=int, default=0)
    p.add_argument('--ci-artifact-id', type=int, default=0)
    p.add_argument('--ci-provenance-sha256', default='')
    p.add_argument('--archive-sha256', default='')
    p.add_argument('--root-descriptor', default='')
    args = p.parse_args()
    require(socket.gethostname() == 'workernode1' and os.geteuid() == 0, 'worker1_privileged_operator_only')
    os.umask(0o077)
    if args.phase == 'setup':
        seal = inputs()
        destination = SEAL
        if destination.exists():
            protected(destination)
            require(json.loads(destination.read_text()) == seal, 'preserve_differing_setup_seal')
        else:
            save(destination, seal)
            os.chown(destination, 0, 0)
            os.chmod(destination, 0o400)
        print(json.dumps({'state': 'setup_verified', 'seal': str(destination), 'database': seal['vulnerabilityDB'], 'scannerExecuted': False}))
    elif args.phase == 'run':
        require(args.service in SERVICES, 'service_required')
        protected(SEAL)
        require(json.loads(SEAL.read_text()) == inputs(), 'setup_seal_required')
        run(args)
    else:
        if args.service and args.attempt:
            require(re.fullmatch('[0-9a-f]{12}', args.attempt), 'attempt_identity')
            status = ROOT / 'attempts' / (args.service + '-' + args.attempt) / 'status.json'
            data = json.loads(status.read_text())
            summary = {k: data.get(k) for k in ['state', 'sourceKind', 'unit', 'scannerPID', 'severityCounts', 'scannerExitCode', 'errorCategory', 'endedUTC']}
            summary.update(receipt=str(status), currentUnit=unit_state(data['unit']))
            print(json.dumps(summary))
        else:
            print(json.dumps({'setupPresent': SEAL.is_file(), 'helperVersion': HELPER_ROOT.name, 'scannerExecuted': False}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'state': 'refused_or_failed', 'category': str(error) if isinstance(error, ValueError) else type(error).__name__, 'securityAcceptance': False}))
        raise SystemExit(1)
