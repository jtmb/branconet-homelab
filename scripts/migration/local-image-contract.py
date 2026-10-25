"""Local operator proof contract shared as reviewed source by staging/scanning."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import stat
import tarfile

LOCAL_GIB = 1024 ** 3
OFFLOAD_STORAGE = {'kind': 'dedicated-f-drive-ext4-loop',
                   'filesystem_uuid': '3c792469-ea0e-4a2c-98e8-1185b141607b',
                   'backing_file': r'F:\branconet-build-storage\native-build-20261025.ext4',
                   'backing_file_bytes': 96 * LOCAL_GIB,
                   'docker_root_filesystem_uuid': 'de6eee3d-80cf-41dc-bf4c-91ee606d02da',
                   'docker_mutable_budget_bytes': 64 * 1024 ** 2,
                   'docker_physical_reserve_bytes': 2 * LOCAL_GIB}
# Historical receipts retain the size actually used by their build.
# Only these two reviewed generations share the pinned file/UUID and bounds.
OFFLOAD_STORAGE_GROWN = {**OFFLOAD_STORAGE, 'backing_file_bytes': 128 * LOCAL_GIB}
OFFLOAD_STORAGE_PROFILES = (OFFLOAD_STORAGE, OFFLOAD_STORAGE_GROWN)
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
    offloaded = service in ['coredns', 'jackett', 'plex', 'unpackerr', 'homepage', 'http-echo', 'qbittorrent-current', 'pihole-exporter', 'mealie', 'qbit-monitor', 'xteve', 'ruckusdb', 'jtmb-dev', 'ruckus-bot'] and result.get('storage_contract') in OFFLOAD_STORAGE_PROFILES
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
                             and physical.get('backing_file_bytes') == result['storage_contract']['backing_file_bytes']) if offloaded else (
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
