"""Exact singleton etcd patch; preserve existing state and never auto-roll back."""
import argparse
import copy
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
import time
import yaml

BASE = Path('/home/james/.local/share/branconet-migration')
ROOT = BASE / 'etcd-static-patch-20261024'
MANIFEST = Path('/etc/kubernetes/manifests/etcd.yaml')
INIT = Path('/etc/kubernetes/kubeadm-init.yaml')
OLD = 'registry.k8s.io/etcd:3.7.0-0'
OLD_RUNTIME = 'sha256:6ecefbe2510c4a30573a62a4d6dd175acf881ca67003fcd91849a16df7a724d5'
OLD_PINNED = OLD + '@' + OLD_RUNTIME
NEW_INDEX = 'sha256:0d27b9478551f431f82d1e0ddb6c87ad07ebae8b904c637f3a99213349523910'
NEW_AMD64 = 'sha256:b4a41c6864baf573f5213dce18b2a95e1002ec6c5a1a26ad900c2ea166ac6d0b'
NEW_CONFIG = 'sha256:380d0ce8f32cc05ce8a1ea99c74da03be90d6c1dad75c9a2ddb8d83162af7f70'
NEW_TAG = '3.7.3-0@' + NEW_INDEX
NEW = 'registry.k8s.io/etcd:' + NEW_TAG
CLUSTER_ID = 6018368537312584938
MEMBER_ID = 6539934570868142778
KUBE = ['/usr/bin/sudo', '-u', 'james', '-H', '/usr/local/bin/kubectl', '--request-timeout=15s']
# Reopening root's stdin pipe after sudo changes UID is denied by Linux.
# Use the identical existing kubeconfig for these stdin-only patch calls.
PATCH_KUBE = ['/usr/local/bin/kubectl', '--kubeconfig=/home/james/.kube/config', '--request-timeout=15s']
CTR = ['/opt/containerd-k8s/bin/ctr', '--address', '/run/containerd-k8s/containerd.sock', '--namespace', 'k8s.io']
START = time.monotonic()


def need(value, reason):
    if not value:
        raise ValueError(reason)
    if time.monotonic() - START > 600:
        raise ValueError('operation_deadline')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def identity(info):
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
            info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)]


def read(path, maximum=1024 ** 2):
    need(path.is_absolute() and path.resolve() == path, 'canonical_file')
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid == 0 and before.st_nlink == 1
         and not before.st_mode & 0o022 and before.st_size <= maximum, 'protected_file')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        need(identity(os.fstat(stream.fileno())) == identity(before), 'opened_file_changed')
        data = stream.read(maximum + 1)
        need(len(data) <= maximum and identity(os.fstat(stream.fileno())) == identity(path.lstat()) == identity(before), 'read_file_changed')
    return data, identity(before)


def protected_directory(path):
    need(path.is_absolute() and path.resolve() == path, 'canonical_operation_directory')
    info = path.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == info.st_gid == 0
         and stat.S_IMODE(info.st_mode) == 0o700, 'protected_operation_directory')


def write(path, value):
    protected_directory(path.parent)
    temp = path.with_name(path.name + '.next-' + str(time.monotonic_ns()))
    raw = json.dumps(value, sort_keys=True, indent=2).encode()
    with temp.open('xb') as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())
    os.chmod(temp, 0o600)
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def command(argv, body=None, timeout=30, maximum=4 * 1024 ** 2, pass_fds=()):
    p = subprocess.run(argv, input=body, capture_output=True, timeout=timeout, pass_fds=pass_fds,
                       env={'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C'})
    need(p.returncode == 0 and len(p.stdout) <= maximum, 'bounded_command_failed')
    return p.stdout


def kube(*args):
    return json.loads(command(KUBE + [*args, '-o', 'json']))


def ticket_check(ticket):
    need(ticket.get('schemaVersion') == 1 and ticket.get('scope') == 'authenticated-etcd-static-patch', 'ticket_scope')
    for field in ['backupReceiptSHA256', 'archiveSHA256', 'snapshotSHA256']:
        need(re.fullmatch('[0-9a-f]{64}', ticket.get(field, '')), 'ticket_digest')
    completed = datetime.datetime.fromisoformat(ticket['backupCompletedUTC'].replace('Z', '+00:00'))
    age = (datetime.datetime.now(datetime.timezone.utc) - completed).total_seconds()
    need(0 <= age <= 3600 and ticket.get('authenticatedArchive') is True
         and ticket.get('snapshotFooter') is True and ticket.get('snapshotStatus') is True, 'fresh_authenticated_backup')
    need(type(ticket.get('snapshotRevision')) is int and ticket['snapshotRevision'] > 0, 'snapshot_revision')
    files = ticket.get('configurationSHA256', {})
    need(0 < len(files) <= 256 and str(MANIFEST).lstrip('/') in files and str(INIT).lstrip('/') in files, 'configuration_backup_coverage')
    need(all(name.startswith('etc/kubernetes/') and '..' not in Path(name).parts
             and re.fullmatch('[0-9a-f]{64}', sha) for name, sha in files.items()), 'configuration_backup_paths')


def configuration(expected, overrides=None):
    overrides = overrides or {}
    current = {}
    for folder, dirs, files in os.walk('/etc/kubernetes', followlinks=False):
        for name in dirs:
            need(not (Path(folder) / name).is_symlink(), 'configuration_directory_alias')
        for name in files:
            path = Path(folder) / name
            data, _ = read(path)
            current[str(path).lstrip('/')] = digest(data)
            need(len(current) <= 256, 'configuration_file_count')
    wanted = dict(expected, **overrides)
    need(current == wanted, 'protected_configuration_changed')
    return digest(canonical(current))


def data_directories():
    result = {}
    for name in ['/var/lib/etcd', '/var/lib/etcd/member']:
        path = Path(name)
        need(path.resolve() == path, 'etcd_data_alias')
        info = path.lstat()
        need(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022, 'etcd_data_directory')
        result[name] = [info.st_dev, info.st_ino, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)]
    return result


def image_map():
    lines = command(CTR + ['images', 'list']).decode().splitlines()
    return {p[0]: p[2] for line in lines if len(p := line.split()) >= 3 and p[2].startswith('sha256:')}


def preload(run, run_id):
    before = image_map()
    need(before.get(OLD) == OLD_RUNTIME and (NEW not in before or before[NEW] == NEW_INDEX)
         and (OLD_PINNED not in before or before[OLD_PINNED] == OLD_RUNTIME), 'cache_alias_conflict')
    space = os.statvfs('/var/lib')
    floor = (15 * space.f_blocks * space.f_frsize + 99) // 100 + 1024 ** 3
    # Same existing cache-import floor, plus a bounded 2GiB working reservation.
    need(space.f_bavail * space.f_frsize >= floor + 2 * 1024 ** 3
         and space.f_favail >= max(250000, space.f_files // 10), 'cache_capacity')
    if NEW in before:
        try:
            return {'alreadyPresent': True, 'cache': cache(), 'runtimeUnitExecuted': False}
        except ValueError as exc:
            need(str(exc) == 'original_image_content_not_retained', 'unexpected_existing_cache_failure')
    references = [OLD_PINNED, NEW]
    home = run / 'empty-home'
    home.mkdir(mode=0o700)
    proof_path = run / 'preload-limits.json'
    unit = 'branconet-etcd-cache-' + run_id
    worker = """import pathlib,json,os,subprocess
group=pathlib.Path('/sys/fs/cgroup')/pathlib.Path('/proc/self/cgroup').read_text().strip().split('::',1)[1].lstrip('/')
proof={n:(group/n).read_text().strip() for n in ['memory.max','memory.swap.max','cpu.max','pids.max']}
assert proof['memory.max']=='1073741824' and proof['memory.swap.max']=='0' and proof['pids.max']=='128'
quota,period=map(int,proof['cpu.max'].split());assert quota==2*period and os.getpriority(os.PRIO_PROCESS,0)==10
with open(PROOF,'x') as out:json.dump(proof,out)
for reference in REFERENCES:
 subprocess.run(CTR+['images','pull','--local','--platform','linux/amd64','--max-concurrent-downloads','2','--label','io.cri-containerd.image=managed',reference],check=True,timeout=140)
""".replace('PROOF', repr(str(proof_path))).replace('CTR', repr(CTR)).replace('REFERENCES', repr(references))
    command(['systemd-run', '--unit=' + unit, '--wait', '--pipe',
             '--property=Type=exec', '--property=MemoryMax=1073741824', '--property=MemorySwapMax=0',
             '--property=CPUQuota=200%', '--property=TasksMax=128', '--property=Nice=10',
             '--property=RuntimeMaxSec=300', '--property=TimeoutStopSec=30', '--property=KillMode=control-group',
             '--property=UMask=0077', '--property=PrivateDevices=yes', '--property=PrivateTmp=yes',
             '--property=NoNewPrivileges=yes', '--property=CapabilityBoundingSet=',
             '--property=ProtectSystem=strict', '--property=ProtectHome=tmpfs',
             '--property=ProtectKernelTunables=yes', '--property=ProtectKernelModules=yes',
             '--property=ProtectKernelLogs=yes', '--property=ProtectControlGroups=yes',
             '--property=BindReadOnlyPaths=' + str(ROOT), '--property=BindPaths=' + str(run),
             '--property=ReadWritePaths=' + str(run), '--property=NoExecPaths=' + str(run),
             '--property=InaccessiblePaths=-/etc/kubernetes -/var/lib/kubelet -/var/lib/longhorn -/run/docker.sock',
             '--', '/usr/bin/env', '-i', 'PATH=/usr/local/bin:/usr/bin:/bin',
             'HOME=' + str(home), 'DOCKER_CONFIG=' + str(home), 'LANG=C', 'LC_ALL=C',
             '/usr/bin/python3', '-B', '-c', worker], timeout=345)
    proof = json.loads(read(proof_path)[0])
    after = image_map()
    need(all(after.get(k) == v for k, v in before.items())
         and set(after) - set(before) <= set(references), 'existing_image_alias_changed')
    need(os.statvfs('/var/lib').f_bavail * space.f_frsize >= floor, 'cache_post_capacity')
    return {'alreadyPresent': False, 'cache': cache(), 'runtimeUnitExecuted': True,
            'unit': unit, 'cgroupProof': proof, 'preservedEveryExistingImageAlias': True,
            'restoredExactOriginalRollbackImage': True,
            'applicationStarted': False, 'workloadChanged': False}


def cache():
    images = image_map()
    need(images.get(OLD) == OLD_RUNTIME and images.get(NEW) == NEW_INDEX, 'both_exact_images_must_be_preloaded')
    index = command(CTR + ['content', 'get', NEW_INDEX])
    need('sha256:' + digest(index) == NEW_INDEX, 'cached_index_digest')
    descriptor = [m for m in json.loads(index)['manifests'] if m.get('platform', {}).get('os') == 'linux'
                  and m.get('platform', {}).get('architecture') == 'amd64']
    need(len(descriptor) == 1 and descriptor[0]['digest'] == NEW_AMD64, 'cached_amd64_binding')
    raw = command(CTR + ['content', 'get', NEW_AMD64])
    need('sha256:' + digest(raw) == NEW_AMD64 and json.loads(raw)['config']['digest'] == NEW_CONFIG, 'cached_manifest_binding')
    old_raw = command(CTR + ['content', 'get', OLD_RUNTIME])
    need('sha256:' + digest(old_raw) == OLD_RUNTIME, 'retained_original_runtime_manifest')
    known = {line.split()[0] for line in command(CTR + ['content', 'list']).decode().splitlines() if line.split()}
    need({NEW_CONFIG, *(r['digest'] for r in json.loads(raw)['layers'])} <= known, 'new_image_content_incomplete')
    # The exact retained original runtime digest is a multi-platform index.
    # Follow only its one Linux/amd64 child, binding both levels by digest.
    old_index = json.loads(old_raw)
    old_children = [m for m in old_index['manifests'] if m.get('platform', {}).get('os') == 'linux'
                    and m.get('platform', {}).get('architecture') == 'amd64']
    need(len(old_children) == 1 and re.fullmatch('sha256:[0-9a-f]{64}', old_children[0]['digest']),
         'retained_original_amd64_binding')
    old_amd64 = old_children[0]['digest']
    old_child_raw = command(CTR + ['content', 'get', old_amd64])
    need('sha256:' + digest(old_child_raw) == old_amd64, 'retained_original_amd64_digest')
    old_manifest = json.loads(old_child_raw)
    need({old_manifest['config']['digest'], *(r['digest'] for r in old_manifest['layers'])} <= known,
         'original_image_content_not_retained')
    return {'originalAliasTarget': images[OLD], 'newAliasTarget': images[NEW], 'originalRuntime': OLD_RUNTIME,
            'originalAMD64Manifest': old_amd64, 'amd64Manifest': NEW_AMD64, 'configDigest': NEW_CONFIG}


def etcd(expected_image, expected_version, snapshot_revision, hash_revision=None):
    pod = kube('get', 'pod', 'etcd-masternode', '-n', 'kube-system')
    need(pod['metadata'].get('annotations', {}).get('kubernetes.io/config.source') == 'file'
         and not pod['metadata'].get('deletionTimestamp') and pod['spec']['nodeName'] == 'masternode', 'static_pod_source')
    c, statuses = pod['spec']['containers'], pod['status'].get('containerStatuses', [])
    need(len(c) == len(statuses) == 1 and c[0]['name'] == statuses[0]['name'] == 'etcd'
         and c[0]['image'] == expected_image and statuses[0]['ready'] and pod['status']['phase'] == 'Running', 'etcd_runtime_not_ready')
    runtime = statuses[0]['imageID'].rsplit('@', 1)[-1]
    need(runtime == OLD_RUNTIME if expected_image == OLD else runtime in [NEW_INDEX, NEW_AMD64], 'runtime_digest')
    args = c[0].get('command', []) + c[0].get('args', [])
    need('--data-dir=/var/lib/etcd' in args and not any(v.startswith('--force-new-cluster') or v.startswith('--unsafe-no-fsync') for v in args), 'supported_data_layout')
    paths = {v['name']: v['hostPath']['path'] for v in pod['spec']['volumes'] if 'hostPath' in v}
    need(any(v.get('mountPath') == '/var/lib/etcd' and paths.get(v['name']) == '/var/lib/etcd'
             and not v.get('readOnly', False) for v in c[0]['volumeMounts']), 'original_host_data_mount')
    prefix = KUBE + ['-n', 'kube-system', 'exec', 'etcd-masternode', '-c', 'etcd', '--', 'etcdctl',
                    '--endpoints=https://127.0.0.1:2379', '--cacert=/etc/kubernetes/pki/etcd/ca.crt',
                    '--cert=/etc/kubernetes/pki/etcd/healthcheck-client.crt',
                    '--key=/etc/kubernetes/pki/etcd/healthcheck-client.key', '--dial-timeout=5s', '--command-timeout=15s']
    call = lambda tail: json.loads(command(prefix + tail, maximum=131072))
    result = call(['endpoint', 'status', '--write-out=json'])
    need(len(result) == 1, 'single_endpoint_required')
    status = result[0]['Status']
    header = status['header']
    need(header['cluster_id'] == CLUSTER_ID and header['member_id'] == MEMBER_ID
         and status['leader'] == MEMBER_ID and not status.get('isLearner')
         and not status.get('errors') and status['version'] == expected_version
         and header['revision'] >= snapshot_revision, 'original_member_cluster_version_revision')
    members = call(['member', 'list', '--write-out=json'])['members']
    need(len(members) == 1 and members[0]['ID'] == MEMBER_ID and members[0]['name'] == 'masternode'
         and not members[0].get('isLearner') and members[0]['peerURLs'] == ['https://192.168.0.4:2380']
         and members[0]['clientURLs'] == ['https://192.168.0.4:2379'], 'singleton_membership')
    need(not call(['alarm', 'list', '--write-out=json']).get('alarms'), 'etcd_alarm')
    health = call(['endpoint', 'health', '--write-out=json'])
    need(len(health) == 1 and health[0].get('health') is True, 'etcd_endpoint_health')
    revision = header['revision'] if hash_revision is None else hash_revision
    value = call(['endpoint', 'hashkv', '--rev=' + str(revision), '--write-out=json'])
    need(len(value) == 1, 'hashkv_endpoint')
    value = value[0]['HashKV']
    need(value['header']['cluster_id'] == CLUSTER_ID and value['header']['member_id'] == MEMBER_ID
         and value['hash_revision'] == revision and value['compact_revision'] < revision, 'frozen_revision_unavailable')
    return {'podUID': pod['metadata']['uid'], 'image': expected_image, 'runtimeDigest': runtime,
            'clusterID': CLUSTER_ID, 'memberID': MEMBER_ID, 'revision': header['revision'],
            'raftTerm': status['raftTerm'], 'raftIndex': status['raftIndex'], 'raftAppliedIndex': status['raftAppliedIndex'],
            'hashRevision': revision, 'hashKV': value['hash'], 'compactRevision': value['compact_revision'],
            'dbSize': status['dbSize'], 'dbSizeInUse': status.get('dbSizeInUse'), 'endpointHealthy': True, 'alarmCount': 0}


def resources(contract, frozen=None):
    nodes = kube('get', 'nodes')['items']
    need({n['metadata']['name'] for n in nodes} == {'masternode', 'workernode1', 'workernode2'}, 'node_set')
    for n in nodes:
        need(not n['spec'].get('unschedulable') and any(c['type'] == 'Ready' and c['status'] == 'True' for c in n['status']['conditions'])
             and not any(c['type'] in ['DiskPressure', 'MemoryPressure', 'PIDPressure', 'NetworkUnavailable'] and c['status'] == 'True' for c in n['status']['conditions']), 'node_not_healthy')
    items = kube('get', 'deployments,statefulsets,daemonsets,volumes.longhorn.io', '-A')['items']
    original = contract.freeze(items) if frozen is None else frozen['controllersAndVolumes']
    need(original and any(v['kind'] == 'Volume' for v in original) and not contract.check(items, original), 'original_controller_or_volume_changed')
    for value in items:
        if value['kind'] == 'Volume':
            need(value['status'].get('state') == 'detached' or value['status'].get('robustness') == 'healthy', 'attached_volume_unhealthy')
    volume_uids = {v['metadata']['name']: v['metadata']['uid'] for v in items if v['kind'] == 'Volume'}
    controller_uids = {v['kind'] + '/' + v['metadata']['namespace'] + '/' + v['metadata']['name']: v['metadata']['uid']
                       for v in items if v['kind'] in ['Deployment', 'StatefulSet', 'DaemonSet']}
    claims = kube('get', 'pvc', '-A')['items']
    claim_uids = {p['metadata']['namespace'] + '/' + p['metadata']['name']: p['metadata']['uid'] for p in claims}
    pvs = kube('get', 'pv')['items']
    pv_uids = {p['metadata']['name']: p['metadata']['uid'] for p in pvs}
    drain = json.loads(command(KUBE + ['-n', 'longhorn-system', 'get', 'settings.longhorn.io', 'node-drain-policy', '-o', 'json']))['value']
    need(drain == 'block-if-contains-last-replica', 'drain_policy_changed')
    result = {'controllersAndVolumes': original, 'allControllerUIDs': controller_uids,
              'allVolumeUIDs': volume_uids, 'allPVCUIDs': claim_uids,
              'allPVUIDs': pv_uids, 'nodeUIDs': {n['metadata']['name']: n['metadata']['uid'] for n in nodes}, 'drainPolicy': drain}
    need(frozen is None or result == frozen, 'original_resource_uid_set_changed')
    return result


def render():
    raw, file_id = read(MANIFEST)
    old = yaml.safe_load(raw)
    need(old.get('kind') == 'Pod' and old['metadata']['name'] == 'etcd'
         and old['metadata'].get('namespace') == 'kube-system', 'supported_static_manifest')
    cs = old['spec']['containers']
    need(len(cs) == 1 and cs[0]['name'] == 'etcd' and cs[0]['image'] == OLD, 'supported_original_image')
    pattern = rb'(?m)^([ \t]*)image: registry\.k8s\.io/etcd:3\.7\.0-0(\r?)$'
    new_raw, count = re.subn(pattern, lambda m: m[1] + b'image: ' + NEW.encode() + m[2], raw)
    expected = copy.deepcopy(old)
    expected['spec']['containers'][0]['image'] = NEW
    need(count == 1 and yaml.safe_load(new_raw) == expected, 'image_only_manifest_patch')
    init_raw, init_id = read(INIT)
    documents = list(yaml.safe_load_all(init_raw))
    configs = [d for d in documents if isinstance(d, dict) and d.get('kind') == 'ClusterConfiguration']
    need(len(configs) == 1, 'single_local_kubeadm_configuration')
    configmap = kube('get', 'configmap', 'kubeadm-config', '-n', 'kube-system')
    cluster_raw = configmap['data']['ClusterConfiguration']
    cluster = yaml.safe_load(cluster_raw)
    def pin(config):
        need(config.get('apiVersion') == 'kubeadm.k8s.io/v1beta4' and config.get('kind') == 'ClusterConfiguration'
             and config.get('kubernetesVersion') == 'v1.37.1' and not config.get('etcd', {}).get('external'), 'supported_kubeadm_configuration')
        local = config.setdefault('etcd', {}).setdefault('local', {})
        need(local.get('dataDir', '/var/lib/etcd') == '/var/lib/etcd'
             and local.get('imageRepository', 'registry.k8s.io') in ['', 'registry.k8s.io']
             and local.get('imageTag', '3.7.0-0') in ['', '3.7.0-0'], 'supported_existing_kubeadm_etcd')
        local['imageRepository'], local['imageTag'] = 'registry.k8s.io', NEW_TAG
    pin(configs[0])
    pin(cluster)
    new_init = yaml.safe_dump_all(documents, sort_keys=False).encode()
    new_cluster = yaml.safe_dump(cluster, sort_keys=False)
    fd = os.memfd_create('reviewed-etcd-kubeadm', os.MFD_CLOEXEC)
    try:
        os.write(fd, new_init)
        images = command(['/usr/local/bin/kubeadm', 'config', 'images', 'list', '--config', '/proc/self/fd/' + str(fd)], pass_fds=(fd,)).decode().splitlines()
        need(images.count(NEW) == 1, 'kubeadm_exact_image_override_not_generated')
    finally:
        os.close(fd)
    probe = [{'op': 'test', 'path': '/metadata/uid', 'value': configmap['metadata']['uid']},
             {'op': 'test', 'path': '/metadata/resourceVersion', 'value': configmap['metadata']['resourceVersion']},
             {'op': 'replace', 'path': '/data/ClusterConfiguration', 'value': new_cluster}]
    command(PATCH_KUBE + ['-n', 'kube-system', 'patch', 'configmap', 'kubeadm-config', '--type=json',
                    '--patch-file=/dev/stdin', '--dry-run=server', '-o', 'name'], body=canonical(probe))
    return {'manifest': new_raw, 'init': new_init, 'clusterConfiguration': new_cluster,
            'configMapPatchServerDryRunPassed': True,
            'manifestBeforeSHA256': digest(raw), 'manifestAfterSHA256': digest(new_raw),
            'initBeforeSHA256': digest(init_raw), 'initAfterSHA256': digest(new_init),
            'clusterBeforeSHA256': digest(cluster_raw.encode()), 'clusterAfterSHA256': digest(new_cluster.encode()),
            'manifestIdentity': file_id, 'initIdentity': init_id,
            'configMapUID': configmap['metadata']['uid'], 'configMapResourceVersion': configmap['metadata']['resourceVersion']}


def atomic(path, data, expected_identity, expected_sha, run_id):
    current, info = read(path)
    need(info == expected_identity and digest(current) == expected_sha and not os.listxattr(path), 'atomic_original_changed_or_xattrs')
    parent = path.parent.parent if path == MANIFEST else path.parent
    need(parent.resolve() == parent and parent.stat().st_dev == path.stat().st_dev, 'atomic_filesystem')
    temp = parent / ('.etcd-static-patch-' + run_id + '-' + path.name + '.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, info[-1])
    try:
        os.fchown(fd, info[5], info[6])
        os.fchmod(fd, info[-1])
        with os.fdopen(os.dup(fd), 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        again, identity_again = read(path)
        need(identity_again == expected_identity and digest(again) == expected_sha, 'atomic_original_race')
        os.replace(temp, path)
        for folder in {parent, path.parent}:
            directory = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        os.close(fd)
    need(digest(read(path)[0]) == digest(data), 'atomic_result')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['preload', 'review', 'apply', 'status'])
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--review-id', default='')
    parser.add_argument('--review-sha256', default='')
    args = parser.parse_args()
    need(os.geteuid() == 0 and socket.gethostname() == 'masternode'
         and re.fullmatch('[0-9a-f]{32}', args.run_id), 'owned_master_operation')
    os.umask(0o077)
    source = Path(__file__).resolve()
    contract_path = source.with_name('recovery_contract.py')
    need(source.parent.name == digest(read(source)[0]) + '-' + digest(read(contract_path)[0]), 'content_addressed_source')
    for directory in [ROOT, ROOT / 'helpers', ROOT / 'runs', source.parent]:
        protected_directory(directory)
    spec = importlib.util.spec_from_file_location('etcd_recovery_contract', contract_path)
    contract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(contract)
    run = ROOT / 'runs' / args.run_id
    if args.phase == 'status':
        protected_directory(run)
        data, _ = read(run / 'receipt.json', 4 * 1024 ** 2)
        value = json.loads(data)
        result = {k: value.get(k) for k in ['phase', 'state', 'passed', 'failureCategory', 'manifestCommitted', 'automaticRollback']}
        print(json.dumps(dict(result, receiptSHA256=digest(data))))
        return
    raw = sys.stdin.buffer.read(512 * 1024 + 1)
    need(len(raw) <= 512 * 1024, 'ticket_size')
    ticket = json.loads(raw)
    ticket_check(ticket)
    run.mkdir(mode=0o700)  # Existing attempts cannot be replayed.
    protected_directory(run)
    receipt_path = run / 'receipt.json'
    record = {'phase': args.phase, 'state': 'started', 'startedUTC': utc(), 'passed': False,
              'sourceSHA256': digest(read(source)[0]), 'recoveryContractSHA256': digest(read(contract_path)[0]),
              'backupReceiptSHA256': ticket['backupReceiptSHA256'], 'archiveSHA256': ticket['archiveSHA256'],
              'manifestCommitted': False, 'dataWrittenOrDeleted': False, 'automaticRollback': False}
    def save(state):
        record.update(state=state, observedUTC=utc())
        write(receipt_path, record)
    save('validating')
    lock = ROOT / 'operation.lock'
    lock_fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, 'r+b') as held:
        lock_info = os.fstat(held.fileno())
        need(stat.S_ISREG(lock_info.st_mode) and lock_info.st_uid == lock_info.st_gid == 0
             and lock_info.st_nlink == 1 and stat.S_IMODE(lock_info.st_mode) == 0o600
             and identity(lock_info) == identity(lock.lstat()), 'protected_operation_lock')
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            if args.phase == 'preload':
                config_hash = configuration(ticket['configurationSHA256'])
                data_ids = data_directories()
                original = etcd(OLD, '3.7.0', ticket['snapshotRevision'])
                need(original['podUID'] == ticket['sourcePodUID'], 'backup_source_pod_changed')
                frozen = resources(contract)
                save('caching_exact_official_image_no_rollout')
                record['preload'] = preload(run, args.run_id)
                need(configuration(ticket['configurationSHA256']) == config_hash
                     and data_directories() == data_ids, 'configuration_or_data_identity_changed')
                resources(contract, frozen)
                etcd(OLD, '3.7.0', ticket['snapshotRevision'])
                record.update(passed=True, originalEtcd=original)
                save('preload_complete_no_configuration_changes')
                print(json.dumps({'phase': args.phase, 'passed': True, 'receipt': str(receipt_path),
                                  'receiptSHA256': digest(receipt_path.read_bytes()), 'manifestCommitted': False}))
                return
            review = None
            if args.phase == 'apply':
                need(re.fullmatch('[0-9a-f]{32}', args.review_id) and re.fullmatch('[0-9a-f]{64}', args.review_sha256), 'review_binding')
                protected_directory(ROOT / 'runs' / args.review_id)
                value, _ = read(ROOT / 'runs' / args.review_id / 'receipt.json', 4 * 1024 ** 2)
                need(digest(value) == args.review_sha256, 'review_receipt_sha256')
                review = json.loads(value)
                need(review.get('phase') == 'review' and review.get('passed') is True
                     and review['sourceSHA256'] == record['sourceSHA256']
                     and review['recoveryContractSHA256'] == record['recoveryContractSHA256']
                     and review['backupReceiptSHA256'] == ticket['backupReceiptSHA256'], 'matching_owned_review')
            config_hash = configuration(ticket['configurationSHA256'])
            data_ids = data_directories()
            cache_state = cache()
            original = etcd(OLD, '3.7.0', ticket['snapshotRevision'])
            need(original['podUID'] == ticket['sourcePodUID'], 'backup_source_pod_changed')
            frozen = resources(contract, review['resources'] if review else None)
            prepared = render()
            summary = {k: v for k, v in prepared.items() if k not in ['manifest', 'init', 'clusterConfiguration']}
            record.update(configurationBeforeSHA256=config_hash, dataDirectories=data_ids, cache=cache_state,
                          originalEtcd=original, resources=frozen, planned=summary)
            if review:
                need(review['dataDirectories'] == data_ids and review['cache'] == cache_state
                     and review['planned'] == summary, 'reviewed_source_or_configuration_changed')
            if args.phase == 'review':
                record['passed'] = True
                save('review_complete_no_configuration_changes')
            else:
                # Recheck immediately before the first mutation.
                ticket_check(ticket)
                configuration(ticket['configurationSHA256'])
                need(data_directories() == data_ids and cache() == cache_state, 'last_identity_fence')
                resources(contract, frozen)
                original = etcd(OLD, '3.7.0', ticket['snapshotRevision'])
                record['preCommitEtcd'] = original
                save('persisting_authoritative_kubeadm_override')
                patch = [{'op': 'test', 'path': '/metadata/uid', 'value': prepared['configMapUID']},
                         {'op': 'test', 'path': '/metadata/resourceVersion', 'value': prepared['configMapResourceVersion']},
                         {'op': 'replace', 'path': '/data/ClusterConfiguration', 'value': prepared['clusterConfiguration']}]
                command(PATCH_KUBE + ['-n', 'kube-system', 'patch', 'configmap', 'kubeadm-config', '--type=json', '--patch-file=/dev/stdin', '-o', 'name'], body=canonical(patch))
                save('kubeadm_configmap_pinned')
                atomic(INIT, prepared['init'], prepared['initIdentity'], prepared['initBeforeSHA256'], args.run_id)
                save('local_kubeadm_pinned')
                configuration(ticket['configurationSHA256'], {str(INIT).lstrip('/'): prepared['initAfterSHA256']})
                resources(contract, frozen)
                save('committing_static_image_only')
                atomic(MANIFEST, prepared['manifest'], prepared['manifestIdentity'], prepared['manifestBeforeSHA256'], args.run_id)
                record['manifestCommitted'] = True
                save('awaiting_existing_kubelet_restart')
                end = time.monotonic() + 300
                final = None
                while time.monotonic() < end:
                    try:
                        command(KUBE + ['get', '--raw=/readyz'], timeout=20, maximum=65536)
                        final = etcd(NEW, '3.7.3', original['revision'], original['hashRevision'])
                        break
                    except (ValueError, subprocess.TimeoutExpired):
                        time.sleep(3)
                need(final is not None and final['hashKV'] == original['hashKV']
                     and final['raftTerm'] >= original['raftTerm'] and final['raftIndex'] >= original['raftIndex']
                     and final['raftAppliedIndex'] >= original['raftAppliedIndex'], 'original_revision_data_or_health_not_verified')
                need(data_directories() == data_ids and cache() == cache_state, 'original_data_or_cache_identity_changed')
                resources(contract, frozen)
                record['configurationAfterSHA256'] = configuration(ticket['configurationSHA256'],
                    {str(INIT).lstrip('/'): prepared['initAfterSHA256'], str(MANIFEST).lstrip('/'): prepared['manifestAfterSHA256']})
                cm = kube('get', 'configmap', 'kubeadm-config', '-n', 'kube-system')
                need(cm['metadata']['uid'] == prepared['configMapUID']
                     and digest(cm['data']['ClusterConfiguration'].encode()) == prepared['clusterAfterSHA256'], 'authoritative_kubeadm_override_changed')
                record.update(passed=True, finalEtcd=final, sameFrozenRevisionHashKV=True)
                save('patch_complete_review_live_receipt')
        except Exception as exc:
            record['failureCategory'] = str(exc) if isinstance(exc, ValueError) and re.fullmatch('[a-z_]+', str(exc)) else 'operation_failed_diagnostics_withheld'
            save('failed_preserve_state_no_automatic_rollback')
            raise SystemExit(1)
    print(json.dumps({'phase': args.phase, 'passed': record['passed'], 'receipt': str(receipt_path),
                      'receiptSHA256': digest(receipt_path.read_bytes()), 'manifestCommitted': record['manifestCommitted'],
                      'automaticRollback': False}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Etcd patch prerequisite refused; configuration values and raw diagnostics withheld')
