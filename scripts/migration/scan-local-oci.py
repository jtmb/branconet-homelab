"""Opt-in WSL local exact-OCI scanner; preserved proof checks, no cluster contact."""
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

BASE = Path('/home/brajam/.local/share/branconet-migration')
ROOT = BASE / 'local-oci-scan-20261024'
FRESH_SOURCE = BASE / 'trivy-db-generation-20261024-e06eced058164f38a7a36670fd89e986/cache'
TOOL_SOURCE = BASE / 'audit20261023-20261023T203418Z/bin/trivy'
HELPER_ROOT = Path(__file__).resolve().parent
OFFLOAD_SCAN_ROOT = BASE / 'local-image-build-offload-20261025/local-oci-scan'
OFFLOADED_SCAN = HELPER_ROOT.parent.parent == OFFLOAD_SCAN_ROOT
if OFFLOADED_SCAN:
    ROOT = OFFLOAD_SCAN_ROOT
SEAL = HELPER_ROOT / 'inputs.json'
BUILDS = BASE / 'worker1-image-build-20261023'
CI_ARTIFACTS = BASE / 'ci-image-artifacts-20261024'
LOCAL_ARTIFACTS = BASE / 'local-image-artifacts-20261024'
SERVICES = ['seerr', 'ytptube', 'jackett', 'pihole', 'flaresolverr', 'vaultwarden', 'tautulli', 'wordpress', 'nginx', 'phpmyadmin', 'coredns', 'plex', 'unpackerr', 'homepage', 'http-echo', 'qbittorrent-current', 'pihole-exporter', 'mealie', 'qbit-monitor', 'xteve', 'ruckusdb', 'jtmb-dev', 'ruckus-bot']
SEERR_CI_LOCK_SHA = '9665b245267e7c864210bdf85f1098c0891f30946c64b3781f44077fff0b7811'
TOOL_SHA = 'd1dfca6ae10a1ad4540bb94e64f0510077c47008920a9b554986b39dca573d83'
DB_FILES = {
    'db/trivy.db': (1634058240, '6a8ba595e91f70580d9badfb6101da1dfeba5c697d28a644244a196034d41540'),
    'db/metadata.json': (143, '18343c6b7ac061a2a3e9544304392c5b2f5c86d1a618494f0b8cf8f9820abc86'),
    'java-db/trivy-java.db': (1561686016, '9c17cf958a0fc2c74d5457ac33d2eb3ef71b170b49cadf9c465ecb9de7d66924'),
    'java-db/metadata.json': (143, 'd7d1bf1706b7e7e658d42db2e83ae966102aa8952dfbb76288ad47532a7a3b6e'),
}
INDEX = {'application/vnd.oci.image.index.v1+json', 'application/vnd.docker.distribution.manifest.list.v2+json'}
MANIFEST = {'application/vnd.oci.image.manifest.v1+json', 'application/vnd.docker.distribution.manifest.v2+json'}
OWNER = pwd.getpwnam('brajam')
_INPUT_HASH_CACHE = {}


def require(value, category):
    if not value:
        raise ValueError(category)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(path):
    # The dedicated loop filesystem otherwise caches both its backing file and
    # each multi-GiB database under the same 1 GiB cgroup. Hash the complete fixed
    # input once per process/identity; later checks retain strict inode, size,
    # mode and nanosecond change-time fences. Legacy profiles are unchanged.
    cacheable = OFFLOADED_SCAN and path in ({ROOT / 'bin/trivy'} | {ROOT / 'cache' / name for name in DB_FILES})
    before = path.stat()
    identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns,
                before.st_mode, before.st_uid, before.st_nlink)
    if cacheable and _INPUT_HASH_CACHE.get(str(path), (None,))[0] == identity:
        return _INPUT_HASH_CACHE[str(path)][1]
    h = hashlib.sha256()
    with path.open('rb') as stream:
        consumed = 0
        for b in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(b)
            consumed += len(b)
            if cacheable and consumed % (16 * 1024**2) == 0:
                os.posix_fadvise(stream.fileno(), consumed - 16 * 1024**2, 16 * 1024**2, os.POSIX_FADV_DONTNEED)
        if cacheable:
            os.posix_fadvise(stream.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
    after = path.stat()
    require((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns,
             after.st_mode, after.st_uid, after.st_nlink) == identity and consumed == before.st_size, 'complete_hash_stable_file_identity')
    result = h.hexdigest()
    if cacheable:
        _INPUT_HASH_CACHE[str(path)] = (identity, result)
    return result


def protected(path, directory=False):
    require(path.is_absolute() and path.resolve() == path and not path.is_symlink(), 'input_path_identity')
    s = path.stat()
    require(s.st_uid == OWNER.pw_uid and not stat.S_IMODE(s.st_mode) & 0o077, 'input_permissions')
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
    physical = os.statvfs('/mnt/f' if OFFLOADED_SCAN else '/mnt/c')
    physical_free = physical.f_bavail*physical.f_frsize
    require(physical_free >= 8*1024**3 + extra, 'physical_backing_drive_scanner_reserve')
    allocated = 0
    for folder, dirs, files in os.walk(ROOT):
        for name in files:
            st = (Path(folder)/name).lstat()
            require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, 'owned_scanner_special_file')
            allocated += st.st_blocks*512
    require(allocated <= 8*1024**3, 'fresh_local_scanner_8GiB_working_budget')
    if OFFLOADED_SCAN:
        mount = ROOT.parent
        require(mount.is_mount() and (mount / 'local-oci-scan').stat().st_dev == mount.stat().st_dev
                and mount.stat().st_dev != os.stat('/').st_dev, 'dedicated_scan_mount')
        return {'capacityBytes': capacity, 'nonrootAvailableBytes': available, 'requiredAvailableBytes': floor,
                'physicalFAvailableBytes': physical_free, 'physicalFReserveBytes': 8*1024**3,
                'freshAllocatedBytes': allocated, 'freeInodes': v.f_favail, 'storageProfile': 'offloaded'}
    return {'capacityBytes': capacity, 'nonrootAvailableBytes': available,
            'requiredAvailableBytes': floor, 'physicalCAvailableBytes': physical_free,
            'physicalCReserveBytes': 8*1024**3, 'freshAllocatedBytes': allocated, 'freeInodes': v.f_favail}


def inputs():
    protected(ROOT, True)
    protected(HELPER_ROOT, True)
    protected(Path(__file__))
    require(HELPER_ROOT == ROOT / 'helpers' / digest(Path(__file__)), 'content_addressed_helper_identity')
    require(HELPER_ROOT.stat().st_uid == OWNER.pw_uid and Path(__file__).stat().st_uid == OWNER.pw_uid, 'operator_owned_frozen_helper_version')
    protected(ROOT / 'bin/trivy')
    require(digest(ROOT / 'bin/trivy') == TOOL_SHA, 'tool_sha256')
    for relative, (size, sha) in DB_FILES.items():
        p = ROOT / 'cache' / relative
        protected(p)
        require(p.stat().st_size == size and digest(p) == sha, 'database_identity')
    require((ROOT / 'no-ignore').read_bytes() == b'', 'ignore_file_must_be_empty')
    require((ROOT / 'trivy-empty.yaml').read_bytes() == b'{}\n', 'scanner_configuration')
    require((ROOT / 'results.tpl').read_text().strip() == '{{ toJson . }}', 'results_only_template')
    proof = {'trivyVersion': '0.76.1', 'trivySHA256': TOOL_SHA,
            'release': 'https://github.com/aquasecurity/trivy/releases/tag/v0.76.1',
            'files': {name: {'bytes': value[0], 'sha256': value[1]} for name, value in DB_FILES.items()},
            'vulnerabilityDB': json.loads((ROOT / 'cache/db/metadata.json').read_text()),
            'javaDB': json.loads((ROOT / 'cache/java-db/metadata.json').read_text()),
            'helperSHA256': digest(Path(__file__)), 'templateSHA256': digest(ROOT / 'results.tpl')}
    if OFFLOADED_SCAN:
        proof['inputHashPolicy'] = 'Complete SHA256 once per process and unchanged inode/size/mode/mtime/ctime identity; private read-only input bindings; page-cache release after complete chunks.'
    return proof


def setup_cache():
    sources = {ROOT/'bin/trivy': (TOOL_SOURCE,176029856,TOOL_SHA,0o500)}
    sources.update({ROOT/'cache'/name:(FRESH_SOURCE/name,size,sha,0o400) for name,(size,sha) in DB_FILES.items()})
    # Existing inputs are fully rehashed by inputs() immediately after this call.
    # Avoid repeatedly reading both original and copy of the multi-GiB databases
    # whenever a new content-addressed helper uses this same immutable cache.
    if all(p.exists() for p in sources) and all((ROOT/n).exists() for n in ['no-ignore', 'trivy-empty.yaml', 'results.tpl']):
        return
    reserve(2*sum(row[1] for row in sources.values()))
    for target,(source,size,expected,mode) in sources.items():
        protected(source)
        require(source.stat().st_size == size and digest(source) == expected, 'fresh_source_DB_or_tool_identity')
        if target.exists():
            protected(target)
            require(target.stat().st_size == size and digest(target) == expected, 'preserve_conflicting_local_input')
        else:
            with source.open('rb') as old, target.open('xb') as new:
                total=0;last=time.monotonic()
                for block in iter(lambda:old.read(1024**2),b''):
                    total+=len(block);require(total<=size,'source_changed_during_copy');new.write(block)
                    if time.monotonic()-last>2:reserve();last=time.monotonic()
                new.flush();os.fsync(new.fileno())
            os.chmod(target,mode)
            require(total==size and digest(target)==expected,'fresh_input_copy_SHA256')
        require(digest(source)==expected,'fresh_source_changed_during_copy')
    for name,content in [('no-ignore',b''),('trivy-empty.yaml',b'{}\n'),('results.tpl',b'{{ toJson . }}\n')]:
        target=ROOT/name
        if not target.exists():
            with target.open('xb') as f:f.write(content)
            target.chmod(0o400)
        require(target.read_bytes()==content,'retain_conflicting_configuration')


def age_hours(metadata):
    value = re.sub(r'(\.\d{6})\d+(?=[+-]|$)', r'\1', metadata['UpdatedAt'].replace('Z', '+00:00'))
    updated = datetime.datetime.fromisoformat(value)
    return (datetime.datetime.now(datetime.timezone.utc) - updated).total_seconds() / 3600


def unit_state(unit):
    p = subprocess.run(['systemctl', '--user', 'show', unit, '-p', 'ActiveState', '-p', 'SubState', '-p', 'Result',
                        '-p', 'MainPID', '-p', 'ControlGroup', '-p', 'MemoryMax', '-p', 'MemorySwapMax',
                        '-p', 'CPUQuotaPerSecUSec', '-p', 'TasksMax', '-p', 'PrivateNetwork', '-p', 'NoNewPrivileges'],
                       capture_output=True, text=True, timeout=15)
    require(p.returncode == 0, 'unit_metadata')
    return dict(line.split('=', 1) for line in p.stdout.splitlines() if '=' in line)


def limits(unit):
    state = unit_state(unit)
    cg = state.get('ControlGroup', '')
    require(cg.startswith('/user.slice/user-1000.slice/user@1000.service/') and cg.endswith('/' + unit), 'owned_user_unit_cgroup')
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
    require(info.st_uid == OWNER.pw_uid and stat.S_IMODE(info.st_mode) == (0o700 if directory else 0o400),
            'native_inputs_must_be_operator_owned_0700_directories_or_0400_files')
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


# BEGIN reviewed local-image-contract.py
LOCAL_GIB = 1024 ** 3
OFFLOAD_STORAGE = {'kind': 'dedicated-f-drive-ext4-loop',
                   'filesystem_uuid': '3c792469-ea0e-4a2c-98e8-1185b141607b',
                   'backing_file': r'F:\branconet-build-storage\native-build-20261025.ext4',
                   'backing_file_bytes': 96 * LOCAL_GIB,
                   'docker_root_filesystem_uuid': 'de6eee3d-80cf-41dc-bf4c-91ee606d02da',
                   'docker_mutable_budget_bytes': 64 * 1024 ** 2,
                   'docker_physical_reserve_bytes': 2 * LOCAL_GIB}
LOCAL_CAPS = {
    'local-operator-provenance.json': 16 * 1024 ** 2,
    'source-export.json': 4 * 1024 ** 2,
    'recipe-sha256.json': 4 * 1024 ** 2,
    'runtime-metadata.json': 4 * 1024 ** 2,
    'builder-worker.json': 4 * 1024 ** 2,
    'local-build-security-image.py': 256 * 1024,
    'recipe.tar': 64 * 1024 ** 2,
}


def local_need(value, reason):
    if not value:
        raise ValueError('local_operator_' + reason)


def local_identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_mode, info.st_uid, info.st_nlink)


def local_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 ** 2), b''):
            digest.update(block)
    return digest.hexdigest()


def local_verify(root, service, run_id, proof_sha, owner, mode=0o400,
                 archive_sha=None, root_descriptor=None, hash_archive=True):
    """Rehash original operator evidence. No network, code/image execution or imports."""
    local_need(re.fullmatch('[0-9a-f]{32}', run_id) and
               re.fullmatch('[0-9a-f]{64}', proof_sha), 'identity')
    local_need(root.resolve() == root and not root.is_symlink(), 'root_path')
    directory = root.stat()
    local_need(stat.S_ISDIR(directory.st_mode) and directory.st_uid == owner and
               stat.S_IMODE(directory.st_mode) == 0o700, 'root_owner_mode')
    def read(name, expected_sha, cap, expected_bytes=None):
        path = root / name
        before = path.lstat()
        local_need(path.resolve() == path and stat.S_ISREG(before.st_mode) and
                   before.st_uid == owner and before.st_nlink == 1 and
                   stat.S_IMODE(before.st_mode) == mode and 0 < before.st_size <= cap and
                   (expected_bytes is None or before.st_size == expected_bytes), 'file_identity')
        local_need((name == service + '.oci.tar' and not hash_archive or
                    local_hash(path) == expected_sha) and local_identity(path.stat()) == local_identity(before), 'file_hash_or_race')
        return path
    proof_path = read('provenance.json', proof_sha, 4 * 1024 ** 2)
    proof = json.loads(proof_path.read_bytes())
    local_need(proof.get('schemaVersion') == 1 and proof.get('sourceKind') == 'local-operator' and
               proof.get('runID') == run_id and proof.get('service') == service and
               proof.get('repository') == 'jtmb/branconet-charts' and
               proof.get('githubActionsIdentityClaimed') is False, 'provenance_scope')
    files = proof['files']; caps = dict(LOCAL_CAPS, **{service + '.oci.tar': 4 * LOCAL_GIB})
    local_need(isinstance(files, dict) and set(files) == set(caps), 'file_allowlist')
    data = {}
    for name, cap in caps.items():
        row = files[name]
        local_need(isinstance(row, dict) and type(row.get('bytes')) is int and
                   re.fullmatch('[0-9a-f]{64}', row.get('sha256', '')), 'file_manifest')
        path = read(name, row['sha256'], cap, row['bytes'])
        if name.endswith('.json'):
            data[name] = json.loads(path.read_bytes())
    result = data['local-operator-provenance.json']
    image = files[service + '.oci.tar']
    head = result.get('source_commit', '')
    local_need(re.fullmatch('[0-9a-f]{40}', head) and result.get('schema_version') == 1 and
               result.get('source_kind') == 'local-operator' and result.get('run_id') == run_id and
               result.get('service') == service and result.get('state') == 'artifact-built-not-qualified-not-deployed' and
               result.get('github_actions_or_workflow_identity_claimed') is False and
               result.get('imported_scanned_pushed_or_deployed') is False and
               result.get('existing_daemon_builder_or_strata_changed') is False and
               all(result.get(k) is True for k in ['new_builder_stopped', 'helper_unchanged',
                         'source_manifest_unchanged', 'builder_config_unchanged']) and
               result.get('archive_sha256') == image['sha256'] and result.get('archive_bytes') == image['bytes'] and
               result.get('helper_sha256') == files['local-build-security-image.py']['sha256'], 'successful_result')
    descriptor = result['root_descriptor']
    local_need(re.fullmatch('sha256:[0-9a-f]{64}', descriptor.get('digest', '')) and
               descriptor.get('mediaType') == 'application/vnd.oci.image.manifest.v1+json' and
               (archive_sha is None or archive_sha == image['sha256']) and
               (root_descriptor is None or root_descriptor == descriptor['digest']), 'archive_root_binding')
    metadata = data['runtime-metadata.json']
    local_need(metadata.get('containerimage.descriptor') == descriptor and
               metadata.get('containerimage.digest') == descriptor['digest'] and
               metadata.get('containerimage.config.digest') == result['oci_proof']['config_descriptor']['digest'] and
               result['oci_proof']['platform'] == 'linux/amd64' and
               result['oci_proof']['all_blob_bytes_verified'] is True, 'runtime_metadata')
    expected = {'memory_bytes': 3 * LOCAL_GIB, 'swap_bytes': 0, 'cpu_quota': 150000,
        'cpu_period': 100000, 'cpuset': '0-1', 'pids': 512, 'max_parallelism': 2,
        'cache_bytes': 8 * LOCAL_GIB, 'build_budget_bytes': 12 * LOCAL_GIB,
        'reserve_bytes': 2 * LOCAL_GIB, 'max_oci_bytes': 4 * LOCAL_GIB,
        'observation_seconds': 6300, 'whole_seconds': 7200}
    measured_profile = result.get('resource_contract', {})
    offloaded = service in ['coredns', 'jackett', 'plex', 'unpackerr', 'homepage', 'http-echo', 'qbittorrent-current', 'pihole-exporter', 'mealie', 'qbit-monitor', 'xteve', 'ruckusdb', 'jtmb-dev', 'ruckus-bot'] and result.get('storage_contract') == OFFLOAD_STORAGE
    local_need(not result.get('storage_contract') or offloaded, 'finite_offloaded_storage_scope')
    local_need(service != 'coredns' or offloaded, 'coredns_requires_dedicated_storage_proof')
    if service in ['wordpress', 'nginx', 'phpmyadmin'] and measured_profile.get('build_budget_bytes') == 4 * LOCAL_GIB:
        expected.update(build_budget_bytes=4 * LOCAL_GIB, max_oci_bytes=LOCAL_GIB)
    local_need(measured_profile == expected and image['bytes'] <= expected['max_oci_bytes'], 'resource_contract')
    host = {'Memory': 3 * LOCAL_GIB, 'MemorySwap': 3 * LOCAL_GIB, 'CpuPeriod': 100000,
            'CpuQuota': 150000, 'CpusetCpus': '0-1', 'PidsLimit': 512,
            'CgroupnsMode': 'private', 'Privileged': True}
    samples = result['cgroup_samples']
    local_need(isinstance(samples, list) and 2 <= len(samples) <= 4000, 'cgroup_sample_count')
    container = samples[0]['container_id']
    local_need(re.fullmatch('[0-9a-f]{64}', container), 'builder_id')
    for sample in samples:
        local_need(sample.get('expected') == host and sample.get('effective_cgroup_v2') ==
                   ['3221225472', '0', '150000 100000', '0-1', '512'] and
                   sample.get('container_id') == container and sample.get('image_id') == result['builder_image_config_digest'] and
                   sample.get('ancestor') == '/system.slice/docker-' + container + '.scope' and
                   0 < sample.get('observed_process_count', 0) <= 512 and
                   0 <= sample['elapsed_seconds'] <= 6300, 'effective_limits')
    capacity = result['capacity_samples']
    local_need(isinstance(capacity, list) and 2 <= len(capacity) <= 4000, 'capacity_samples')
    for index, sample in enumerate(capacity):
        fs, physical = sample['logical'], sample['physical']
        floor = sum(expected[k] for k in ['build_budget_bytes', 'max_oci_bytes', 'reserve_bytes']) if index == 0 else expected['reserve_bytes']
        memory = 3 * LOCAL_GIB + 512 * 1024 ** 2 if index == 0 else 512 * 1024 ** 2
        logical_uuid = OFFLOAD_STORAGE['filesystem_uuid'] if offloaded else 'de6eee3d-80cf-41dc-bf4c-91ee606d02da'
        physical_identity = (physical.get('backing_drive') == 'F:\\'
                             and physical.get('backing_file_path') == OFFLOAD_STORAGE['backing_file']
                             and physical.get('backing_file_bytes') == OFFLOAD_STORAGE['backing_file_bytes']) if offloaded else (
                                 physical.get('backing_drive') == 'C:\\' and re.fullmatch(r'C:\\Users\\james\\AppData\\Local\\wsl\\\{bcb924f4-59dd-4c02-9b01-9541c545b756\}\\ext4\.vhdx', physical.get('vhd_path', ''), re.I))
        local_need(fs.get('uuid') == logical_uuid and
                   fs.get('filesystem') == 'ext4' and fs.get('available_bytes', 0) >= floor and
                   fs.get('free_inode_fraction', 0) >= .10 and
                   fs.get('fresh_build_allocated_bytes', 0) <= expected['build_budget_bytes'] and
                   physical.get('distribution') == 'Ubuntu' and physical_identity and
                   physical.get('backing_available_bytes', 0) >= floor and
                   physical.get('physical_available_bytes', 0) >= memory and
                   0 <= sample['elapsed_seconds'] <= 6300, 'logical_physical_capacity')
        if offloaded:
            local_need(fs.get('docker_root_filesystem_uuid') == OFFLOAD_STORAGE['docker_root_filesystem_uuid']
                       and 0 <= fs.get('docker_mutable_bytes', -1) <= OFFLOAD_STORAGE['docker_mutable_budget_bytes']
                       and physical.get('docker_backing_available_bytes', 0) >= OFFLOAD_STORAGE['docker_physical_reserve_bytes']
                       + (OFFLOAD_STORAGE['docker_mutable_budget_bytes'] if index == 0 else 0), 'separate_docker_bootstrap_capacity')
    started = datetime.datetime.fromisoformat(result['started_at'])
    ended = datetime.datetime.fromisoformat(result['completed_at'])
    local_need(started.tzinfo is not None and ended.tzinfo is not None and
               0 <= (ended - started).total_seconds() <= 7200, 'whole_deadline')
    source = data['source-export.json']; recipe = data['recipe-sha256.json']
    local_need(source == result['source'] and source.get('commit') == head and
               re.fullmatch('[0-9a-f]{40}', source.get('recipe_tree', '')) and
               isinstance(recipe, dict) and 0 < len(recipe) <= 512 and 'Dockerfile' in recipe,
               'source_export')
    rows = source['files']; names = {row['path'] for row in rows}
    local_need(len(names) == len(rows) == len(recipe), 'recipe_count')
    for row in rows:
        name = row['path']; item = recipe[name]
        local_need(name and not name.startswith('/') and '..' not in Path(name).parts and
                   '\\' not in name and re.fullmatch('[0-9a-f]{40}', row['git_blob']) and
                   row['git_mode'] in ['100644', '100755'] and
                   item == {'sha256': row['sha256'], 'bytes': row['bytes'],
                            'mode': 0o755 if row['git_mode'] == '100755' else 0o644}, 'recipe_manifest')
    seen = set()
    with tarfile.open(root / 'recipe.tar', 'r:') as bundle:
        members = bundle.getmembers()
        local_need(len(members) <= 1024, 'recipe_tar_count')
        for member in members:
            local_need(member.name == service or member.name.startswith(service + '/'), 'recipe_tar_prefix')
            local_need(not member.issym() and not member.islnk() and (member.isdir() or member.isfile()), 'recipe_tar_special')
            if member.isdir():
                continue
            name = member.name[len(service) + 1:]
            local_need(name in recipe and name not in seen and member.size == recipe[name]['bytes'] and
                       member.mode == recipe[name]['mode'], 'recipe_tar_file')
            seen.add(name); content = bundle.extractfile(member).read()
            row = next(r for r in rows if r['path'] == name)
            local_need(hashlib.sha256(content).hexdigest() == row['sha256'] and
                       hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest() == row['git_blob'], 'recipe_git_blob')
    local_need(seen == names, 'recipe_tar_complete')
    if service == 'seerr':
        local_need(recipe.get('pnpm-lock.yaml', {}).get('sha256') ==
                   '9665b245267e7c864210bdf85f1098c0891f30946c64b3781f44077fff0b7811', 'frozen_lock')
    local_need(local_hash(proof_path) == proof_sha and local_identity(root.stat()) == local_identity(directory), 'proof_race')
    return {'sourceKind': 'local-operator', 'runID': run_id, 'service': service,
            'headSHA': head, 'provenanceSHA256': proof_sha, 'files': files,
            'rootDescriptor': descriptor['digest'], 'archiveSHA256': image['sha256'],
            'archiveBytes': image['bytes'], 'githubActionsIdentityClaimed': False,
            'verificationBoundary': 'Trusted local operator observations and exact source/artifact bytes; no GitHub job, scan, runtime or deployment acceptance claimed.'}


def local_root(args):
    require(re.fullmatch('[0-9a-f]{32}', args.local_run_id) and re.fullmatch('[0-9a-f]{64}', args.local_provenance_sha256), 'local_operator_identity')
    require(args.ci_run_id == args.ci_artifact_id == 0 and not args.ci_provenance_sha256 and args.build_attempt == 'initial', 'local_operator_has_no_ci_or_worker_identity')
    parent = (BASE / 'local-image-build-offload-20261025/local-image-artifacts-20261025'
              if args.service in ['unpackerr', 'homepage', 'http-echo', 'qbittorrent-current', 'pihole-exporter', 'mealie', 'qbit-monitor', 'xteve', 'ruckusdb', 'jtmb-dev', 'ruckus-bot'] else LOCAL_ARTIFACTS)
    if args.service in ['unpackerr', 'homepage', 'http-echo', 'qbittorrent-current', 'pihole-exporter', 'mealie', 'qbit-monitor', 'xteve', 'ruckusdb', 'jtmb-dev', 'ruckus-bot']:
        require(OFFLOADED_SCAN and parent.parent.is_mount(), 'dedicated_receiver_mount')
    return parent / (args.service + '-' + args.local_run_id)


def local_receipts(root, args, size):
    require(root == local_root(args), 'local_operator_fixed_root')
    ci_owned(root.parent, True)
    ci_owned(root, True)
    proof = local_verify(root, args.service, args.local_run_id, args.local_provenance_sha256, OWNER.pw_uid,
                         archive_sha=args.archive_sha256, root_descriptor=args.root_descriptor,
                         hash_archive=False)
    require(proof['archiveBytes'] == size, 'local_operator_archive_size')
    return proof


def run(args):
    require(re.fullmatch('[0-9a-f]{12}', args.attempt), 'attempt_identity')
    unit = 'branconet-local-oci-scan-' + args.service + '-' + args.attempt + '.service'
    attempt = ROOT / 'attempts' / (args.service + '-' + args.attempt)
    attempt.mkdir(mode=0o700)
    os.chown(attempt, OWNER.pw_uid, OWNER.pw_gid)
    record = {'state': 'verifying', 'startedUTC': utc(), 'service': args.service,
              'attempt': args.attempt, 'unit': unit, 'runnerPID': os.getpid(), 'sourceKind': args.source_kind,
              'applicationExecuted': False, 'imageImported': False, 'secretScannerEnabled': False,
              'securityAcceptance': False, 'executionHostKind': 'wsl-local-operator', 'executionHostname': socket.gethostname()}
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
            elif args.source_kind == 'local-operator':
                build_root = local_root(args)
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
            elif args.source_kind == 'local-operator':
                record['localProvenance'] = local_receipts(build_root, args, initial.st_size)
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
            elif args.source_kind == 'local-operator':
                require(local_receipts(build_root, args, initial.st_size) == record['localProvenance'], 'local_provenance_changed')
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
            elif args.source_kind == 'local-operator':
                require(local_receipts(build_root, args, initial.st_size) == record['localProvenance'], 'local_provenance_changed_during_scan')
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
    p.add_argument('--apply', action='store_true')
    p.add_argument('--unit', default='')
    p.add_argument('--service', choices=SERVICES)
    p.add_argument('--attempt', default='')
    p.add_argument('--build-attempt', default='initial')
    p.add_argument('--source-kind', choices=['github-actions', 'local-operator'], default='local-operator')
    p.add_argument('--local-run-id', default='')
    p.add_argument('--local-provenance-sha256', default='')
    p.add_argument('--ci-run-id', type=int, default=0)
    p.add_argument('--ci-artifact-id', type=int, default=0)
    p.add_argument('--ci-provenance-sha256', default='')
    p.add_argument('--archive-sha256', default='')
    p.add_argument('--root-descriptor', default='')
    args = p.parse_args()
    require(os.geteuid() == OWNER.pw_uid == 1000 and 'microsoft' in Path('/proc/sys/kernel/osrelease').read_text().lower(), 'native_WSL_operator_only')
    os.umask(0o077)
    if args.phase == 'setup':
        require(args.apply and re.fullmatch('branconet-local-oci-setup-[0-9a-f]{12}[.]service', args.unit), 'explicit_setup_unit')
        limits(args.unit)
        setup_cache()
        seal = inputs()
        destination = SEAL
        if destination.exists():
            protected(destination)
            require(json.loads(destination.read_text()) == seal, 'preserve_differing_setup_seal')
        else:
            save(destination, seal)
            os.chown(destination, OWNER.pw_uid, OWNER.pw_gid)
            os.chmod(destination, 0o400)
        print(json.dumps({'state': 'setup_verified', 'seal': str(destination), 'database': seal['vulnerabilityDB'], 'scannerExecuted': False}))
    elif args.phase == 'run':
        require(args.apply, 'explicit_scan_required')
        require(args.service in SERVICES, 'service_required')
        require(not OFFLOADED_SCAN or (args.service in ['coredns', 'jackett', 'plex', 'unpackerr', 'homepage', 'http-echo', 'qbittorrent-current', 'pihole-exporter', 'mealie', 'qbit-monitor', 'xteve', 'ruckusdb', 'jtmb-dev', 'ruckus-bot'] and args.source_kind == 'local-operator')
                or (args.service == 'jackett' and args.source_kind == 'github-actions'), 'finite_offloaded_scan_scope')
        require(args.source_kind == 'local-operator' or not (args.local_run_id or args.local_provenance_sha256), 'nonlocal_source_has_no_local_identity')
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
