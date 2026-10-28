#!/usr/bin/env python3
"""Finite digest-only MySQL then YTPTube native prestager; observe by default."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import selectors
import shlex
import socket
import stat
import subprocess
import sys
import urllib.parse
import uuid

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
O = F / 'platform-upstream-review-20261027'
H = O / 'upstream-security-prestage-20261028'
B = O / 'upstream-native-size-20261028'
VOLUME = '3c792469-ea0e-4a2c-98e8-1185b141607b'
CTR_SHA = 'bcf0357ed9f17b8851ccde2486321c8fa2d0bcfb0ea71c267da6a1155c7f4743'
MEASURE_SOURCE_SHA = '911e8f1586150d2cd2ebda875005286b586ac32fb501c93508207a1fbfb207b5'
HTTP_HELPER_SHA = '6f2af1e8931cf9cd86be7f9dfcfd246fe3b584f71b49ddc6d75916cfcdc963a3'
METADATA_SHA = '068348639fed49cadb197b43be929e32e5c1213c8f40aebf4a57b67f03fc41a7'
PINS = {
    'mysql': {'repository': 'docker.io/library/mysql',
              'root': 'sha256:a0225d1ea6631c8bc2385dc4c2faba17bbf1834ecf369e1659a9a382bd8d5dd7',
              'measurementSHA256': '1ea5a3847bf9365a6ad605baff1e160982e46a02587967418dbb454b57dd7c38',
              'wholePeak': 1344196430, 'layers': 10},
    'ytptube': {'repository': 'ghcr.io/arabcoders/ytptube',
                'root': 'sha256:a5b648c6c20d877cf90715415b1b31565dda9399020d80f186000fdd76474f86',
                'measurementSHA256': '900f419bb4a22371b53030d265e87ec5b045a29f1783484e3798a9e9843ccf1c',
                'wholePeak': 1879576367, 'layers': 27},
}
NODES = {
    'master': {'name': 'masternode', 'ip': '192.168.0.4', 'rootUUID': '763cda3d-0777-4b03-a882-9d21060466e3', 'uid': 'f2df6169-4592-4544-b62c-74d89f598648'},
    'worker2': {'name': 'workernode2', 'ip': '192.168.0.5', 'rootUUID': '960bc2c7-2a7e-4bc2-b2c5-dbb6d71207f4', 'uid': 'eda66e65-f388-4b97-b64f-a709cda81894'},
    'worker1': {'name': 'workernode1', 'ip': '192.168.0.6', 'rootUUID': '5f1fd363-f7b7-44db-ace5-ad81a25a2926', 'uid': 'e8d4555f-7cea-445f-b84f-6416964045a9'},
}
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts',
       '-o', 'IdentitiesOnly=yes', '-o', 'ForwardAgent=no', '-o', 'ConnectTimeout=15', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002']
CTR = ['/opt/containerd-k8s/bin/ctr', '--address', '/run/containerd-k8s/containerd.sock', '--namespace', 'k8s.io']
CONTENT = Path('/var/lib/containerd-k8s/io.containerd.content.v1.content/blobs/sha256')
MARGIN = 512 * 1024**2
METADATA_ALLOWANCE = 16 * 1024**2
AVAILABLE_FLOOR = 15 * 1024**3


def need(value, reason):
    if not value:
        raise ValueError(reason)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            digest.update(block)
    return digest.hexdigest()


def read(args, timeout=90):
    p = subprocess.run(args, capture_output=True, timeout=timeout)
    need(p.returncode == 0, 'read_failed:' + args[0])
    need(len(p.stdout) <= 8 * 1024**2, 'metadata_output_bound')
    return p.stdout


def native(args):
    return read(CTR + args)


def measurement(service, live_registry=True):
    pin = PINS[service]
    path = B / (service + '-r2-measurement.json')
    need(path.resolve() == path and sha(path) == pin['measurementSHA256'], 'pinned_r2_measurement')
    need(sha(B / 'inspect-upstream-native-size-r2.py') == MEASURE_SOURCE_SHA, 'original_measurement_source')
    m = json.loads(path.read_bytes())
    need(m['sourceSHA256'] == MEASURE_SOURCE_SHA and m['status'] == 'completed'
         and m['accountingRevision'] == 'r2' and m['originalMeasurementsReproduced'] is True
         and m['payloadSavedBytes'] == 0 and len(m['layers']) == pin['layers']
         and m['image'] == pin['repository'] + '@' + pin['root'], 'complete_authenticated_measurement')
    previous = ''
    layers = []
    for i, row in enumerate(m['layers']):
        need(row['index'] == i and row['hashesVerified'] is True, 'all_original_layer_hashes_verified')
        chain = row['diffID'] if not previous else 'sha256:' + hashlib.sha256((previous + ' ' + row['diffID']).encode()).hexdigest()
        need(chain == row['chainID'] and row['revisedUnpackedUpperBytes'] > 0, 'measured_chain_and_revised_upper')
        layers.append({'digest': row['digest'], 'compressedBytes': row['compressedBytes'], 'diffID': row['diffID'],
                       'chainID': chain, 'parent': previous, 'unpackedUpperBytes': row['revisedUnpackedUpperBytes']})
        previous = chain
    need(sum(x['compressedBytes'] + x['unpackedUpperBytes'] for x in layers) + METADATA_ALLOWANCE
         == m['revisedWholeImageStagingUpperBytes'] == pin['wholePeak'], 'unchanged_full_peak_accounting')
    metadata_path = F / 'security-review-20261026/vendor-r5-refresh-metadata.json'
    need(sha(metadata_path) == METADATA_SHA, 'approved_registry_metadata')
    item = next(x for x in json.loads(metadata_path.read_bytes())['images'] if x['repository'] == pin['repository'])
    approved = next(x for x in item['manifests'] if x['rootDigest'] == pin['root'])
    need(approved['amd64ManifestDigest'] == m['amd64ManifestDigest']
         and approved['configurationDigest'] == m['configurationDigest'], 'measurement_metadata_binding')
    need([(x['digest'], x['size']) for x in approved['amd64Manifest']['layers']]
         == [(x['digest'], x['compressedBytes']) for x in layers], 'exact_all_layer_descriptors')
    if live_registry:
        need(sha(B / 'stream-helper.py') == HTTP_HELPER_SHA, 'pinned_public_https_helper')
        http_helper = runpy.run_path(str(B / 'stream-helper.py'))
        small = http_helper['small']
        host, repository = pin['repository'].split('/', 1)
        registry = 'registry-1.docker.io' if host == 'docker.io' else 'ghcr.io'
        token_host = 'auth.docker.io' if host == 'docker.io' else 'ghcr.io'
        token_service = 'registry.docker.io' if host == 'docker.io' else 'ghcr.io'
        token = small('https://' + token_host + '/token?' + urllib.parse.urlencode({'service': token_service, 'scope': 'repository:' + repository + ':pull'}))['token']
        headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.oci.image.index.v1+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.docker.distribution.manifest.v2+json'}
        base = 'https://' + registry + '/v2/' + repository
        metadata_blobs = []
        def public_metadata(route, digest):
            with http_helper['request'](base + route + digest, headers) as response:
                raw = response.read(1024**2 + 1)
            need(len(raw) <= 1024**2 and 'sha256:' + hashlib.sha256(raw).hexdigest() == digest, 'bounded_pinned_metadata_bytes')
            metadata_blobs.append({'digest': digest, 'compressedBytes': len(raw)})
            return json.loads(raw)
        root = public_metadata('/manifests/', pin['root'])
        manifest = public_metadata('/manifests/', m['amd64ManifestDigest'])
        config = public_metadata('/blobs/', m['configurationDigest'])
        need(root == approved['rootManifest'] and manifest == approved['amd64Manifest'], 'live_immutable_registry_metadata')
        need(config['architecture'] == 'amd64' and config['os'] == 'linux'
             and config['rootfs']['diff_ids'] == [x['diffID'] for x in layers], 'live_config_diff_ids')
        token = headers = None
        need(sum(x['compressedBytes'] for x in metadata_blobs) <= 1024**2, 'metadata_inside_fixed_allowance')
    else:
        raise ValueError('live_registry_binding_required')
    return {'service': service, 'image': m['image'], 'root': pin['root'], 'manifest': m['amd64ManifestDigest'],
            'config': m['configurationDigest'], 'layers': layers, 'measurementSHA256': pin['measurementSHA256'],
            'measurementSourceSHA256': MEASURE_SOURCE_SHA, 'metadataSHA256': METADATA_SHA,
            'registryMetadataVerified': live_registry, 'metadataBlobs': metadata_blobs, 'wholePeakBytes': pin['wholePeak']}


def cluster():
    def kube(words):
        p = read(SSH + ['james@192.168.0.4', shlex.join(['kubectl', *words])])
        return json.loads(p)
    actual = kube(['get', 'nodes', '-o', 'json', '--request-timeout=20s'])['items']
    need(len(actual) == 3, 'three_original_nodes')
    result = {'nodes': {}, 'disks': {}, 'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    for alias, pin in NODES.items():
        rows = [n for n in actual if n['metadata']['name'] == pin['name']]
        need(len(rows) == 1 and rows[0]['metadata']['uid'] == pin['uid'], 'original_node_uid')
        n = rows[0]; conditions = {c['type']: c['status'] for c in n['status']['conditions']}
        need(conditions.get('Ready') == 'True' and all(conditions.get(k) == 'False' for k in ['MemoryPressure', 'DiskPressure', 'PIDPressure'])
             and conditions.get('NetworkUnavailable', 'False') == 'False' and not n['spec'].get('unschedulable', False), 'ready_no_pressure_no_cordon:' + alias)
        need(n['status']['nodeInfo']['kernelVersion'] == '5.15.0-198-generic'
             and n['status']['nodeInfo']['containerRuntimeVersion'] == 'containerd://2.4.2', 'original_kernel_and_runtime')
        stats = kube(['get', '--raw', '/api/v1/nodes/' + pin['name'] + '/proxy/stats/summary'])['node']
        cfg = kube(['get', '--raw', '/api/v1/nodes/' + pin['name'] + '/proxy/configz'])['kubeletconfig']
        result['nodes'][alias] = {'uid': pin['uid'], 'conditions': conditions,
            'nodeInfo': n['status']['nodeInfo'], 'nodeFS': stats['fs'], 'imageFS': stats['runtime']['imageFs'],
            'evictionHard': cfg.get('evictionHard'), 'imageGCHighThresholdPercent': cfg.get('imageGCHighThresholdPercent'),
            'imageGCLowThresholdPercent': cfg.get('imageGCLowThresholdPercent')}
    settings = kube(['-n', 'longhorn-system', 'get', 'settings.longhorn.io', 'storage-minimal-available-percentage', '-o', 'json'])
    need(settings['value'] == '25', 'original_longhorn_25_percent_floor')
    lh = kube(['-n', 'longhorn-system', 'get', 'nodes.longhorn.io', '-o', 'json'])['items']
    for alias, pin in NODES.items():
        row = next(n for n in lh if n['metadata']['name'] == pin['name'])
        disks = []
        for key, disk in row['status']['diskStatus'].items():
            need(disk['storageAvailable'] >= disk['storageMaximum'] // 4 + 1 + MARGIN, 'current_longhorn_floor_margin:' + alias)
            disks.append({'key': key, 'path': row['spec']['disks'][key]['path'], 'capacity': disk['storageMaximum'], 'available': disk['storageAvailable']})
        need(disks, 'longhorn_disks_present')
        result['disks'][alias] = disks
    return result


def controller_space():
    values = {}
    for name, path in [('windowsC', Path('/mnt/c')), ('windowsF', Path('/mnt/f')), ('nativeF', F)]:
        fs = os.statvfs(path); values[name] = fs.f_bavail * fs.f_frsize
        need(values[name] >= AVAILABLE_FLOOR + METADATA_ALLOWANCE, 'controller_space_floor:' + name)
    return values


def continuity():
    services = {}
    for name in ['containerd-k8s', 'kubelet', 'ssh']:
        values = dict(line.split('=', 1) for line in read(['systemctl', 'show', name, '--property=MainPID,ActiveState,SubState,ExecMainStartTimestampMonotonic,NRestarts']).decode().splitlines())
        need(values['ActiveState'] == 'active' and int(values['MainPID']) > 0, 'active_service:' + name)
        services[name] = values
    return {'bootID': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'kernel': os.uname().release, 'services': services,
            'hashes': {p: sha(p) for p in ['/etc/containerd-k8s/config.toml', '/var/lib/kubelet/config.yaml', CTR[0]]}}


def native_inventory():
    images = {}
    lines = native(['images', 'list']).decode().splitlines()
    for line in lines[1:]:
        cells = line.split()
        need(len(cells) >= 3 and re.fullmatch('sha256:[a-f0-9]{64}', cells[2]), 'native_image_listing_schema')
        labels = sorted(cells[-1].split(','))
        images[cells[0]] = {'digest': cells[2], 'labels': labels, 'managed': 'io.cri-containerd.image=managed' in labels}
    content = set()
    for line in native(['content', 'list']).decode().splitlines()[1:]:
        cells = line.split()
        if cells:
            need(re.fullmatch('sha256:[a-f0-9]{64}', cells[0]), 'native_content_listing_schema')
            content.add(cells[0])
    leases = {line.split()[0] for line in native(['leases', 'list']).decode().splitlines()[1:] if line.split()}
    snapshots = {line.split()[0] for line in native(['snapshots', '--snapshotter', 'overlayfs', 'list']).decode().splitlines()[1:] if line.split()}
    return {'images': images, 'content': sorted(content), 'leases': sorted(leases), 'snapshots': sorted(snapshots)}


def verified_blob(layer):
    path = CONTENT / layer['digest'].split(':')[1]
    if not path.exists():
        need(not path.is_symlink(), 'dangling_native_blob_refuse')
        return {'cached': False}
    need(path.resolve() == path and all(p.resolve() == p and not p.is_symlink() for p in path.parents), 'native_blob_original_ancestry')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == 0
             and before.st_size == layer['compressedBytes'], 'present_blob_identity_or_size_refuse_no_overwrite')
        digest = hashlib.sha256()
        while True:
            chunk = os.read(fd, 1024**2)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(fd)
        fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        need(fields(before) == fields(after) == fields(path.stat()), 'blob_changed_while_hashing')
        need('sha256:' + digest.hexdigest() == layer['digest'], 'corrupt_present_blob_refuse_no_overwrite')
        return {'cached': True, 'bytes': before.st_size, 'allocatedBytes': before.st_blocks * 512, 'inode': before.st_ino, 'sha256': digest.hexdigest()}
    finally:
        os.close(fd)


def node_observe(request):
    alias = request['node']; pin = NODES[alias]; plan = request['plan']; live = request['cluster']
    need(os.geteuid() == 0 and socket.gethostname() == pin['name'], 'exact_privileged_node')
    need(read(['findmnt', '-n', '-o', 'UUID', '/']).decode().strip() == pin['rootUUID'], 'exact_root_uuid')
    need(sha(CTR[0]) == CTR_SHA, 'original_native_ctr_binary')
    need(plan['image'] == PINS[plan['service']]['repository'] + '@' + PINS[plan['service']]['root'], 'only_two_approved_images')
    need(CONTENT.resolve() == CONTENT and CONTENT.is_dir(), 'original_native_content_root')
    root_device = Path('/').stat().st_dev
    paths = [Path('/'), Path('/var/lib/containerd-k8s'), CONTENT] + [Path(d['path']) for d in live['disks'][alias]]
    need(all(p.resolve() == p and p.stat().st_dev == root_device for p in paths), 'same_actual_root_image_and_longhorn_device')
    fs = os.statvfs(CONTENT); capacity = fs.f_blocks * fs.f_frsize
    need(fs.f_frsize == 4096 and live['nodes'][alias]['nodeFS']['capacityBytes'] == capacity
         and live['nodes'][alias]['imageFS']['capacityBytes'] == capacity
         and all(d['capacity'] == capacity for d in live['disks'][alias]), 'same_kubelet_imagefs_longhorn_capacity')
    memory = {line.split(':')[0]: int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:', 'MemAvailable:'))}
    need(memory['MemAvailable'] >= 1024**3, 'one_gib_current_available_memory')
    preserved = continuity(); inv = native_inventory()
    image = inv['images'].get(plan['image'])
    need(image is None or image['digest'] == plan['root'], 'never_overwrite_existing_canonical_digest')
    need(image is None or image['managed'], 'existing_canonical_record_label_preserved')
    verified_chains = {''}; layers = []; missing_compressed = missing_unpacked = 0
    metadata_blobs = [{'digest': row['digest'], **verified_blob(row)} for row in plan['metadataBlobs']]
    for layer in plan['layers']:
        blob = verified_blob(layer)
        committed = False; info = None
        if layer['chainID'] in inv['snapshots']:
            info = json.loads(native(['snapshots', '--snapshotter', 'overlayfs', 'info', layer['chainID']]))
            committed = (info['Name'] == layer['chainID'] and info['Kind'] == 'Committed'
                         and info.get('Parent', '') == layer['parent'] and layer['parent'] in verified_chains)
        if committed:
            verified_chains.add(layer['chainID'])
        missing_compressed += 0 if blob['cached'] else layer['compressedBytes']
        missing_unpacked += 0 if committed else layer['unpackedUpperBytes']
        layers.append({'digest': layer['digest'], 'chainID': layer['chainID'], 'parent': layer['parent'],
                       'blob': blob, 'committedCorrectParent': committed,
                       'missingCompressedBytes': 0 if blob['cached'] else layer['compressedBytes'],
                       'missingUnpackedUpperBytes': 0 if committed else layer['unpackedUpperBytes']})
    peak = missing_compressed + missing_unpacked + METADATA_ALLOWANCE
    ready = set(native(['images', 'check', '--quiet', '--snapshotter', 'overlayfs']).decode().splitlines())
    fs = os.statvfs(CONTENT)
    free = fs.f_bfree * fs.f_frsize; available = fs.f_bavail * fs.f_frsize
    floor = capacity // 4 + 1 + MARGIN
    return {'node': alias, 'hostname': pin['name'], 'rootUUID': pin['rootUUID'], 'rootDevice': root_device,
            'image': plan['image'], 'fullyCached': image is not None and plan['image'] in ready and missing_compressed == missing_unpacked == 0
                and all(row['cached'] for row in metadata_blobs), 'metadataBlobs': metadata_blobs,
            'layers': layers, 'missingCompressedBytes': missing_compressed, 'missingUnpackedUpperBytes': missing_unpacked,
            'metadataAllowanceBytes': METADATA_ALLOWANCE, 'missingPeakBytes': peak, 'freeBytes': free,
            'availableBytes': available, 'capacityBytes': capacity, 'floorAndMarginBytes': floor,
            'fits': free >= floor + peak and available >= AVAILABLE_FLOOR + peak,
            'memory': memory, 'continuity': preserved, 'inventory': inv}


def collect_pull(command):
    """Drain bounded chunks; retain hashes/counts only, never HTTP traces or log files."""
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    selector = selectors.DefaultSelector()
    streams = {'stdout': child.stdout, 'stderr': child.stderr}
    hashes = {k: hashlib.sha256() for k in streams}; sizes = {k: 0 for k in streams}
    for name, stream in streams.items():
        selector.register(stream, selectors.EVENT_READ, name)
    while selector.get_map():
        for key, _ in selector.select(timeout=5):
            block = os.read(key.fileobj.fileno(), 65536)
            if block:
                hashes[key.data].update(block); sizes[key.data] += len(block)
            else:
                selector.unregister(key.fileobj); key.fileobj.close()
    selector.close()
    code = child.wait()
    return {'exitCode': code, 'streams': {k: {'bytes': sizes[k], 'sha256': hashes[k].hexdigest()} for k in streams},
            'outputWithinBound': sum(sizes.values()) <= 8 * 1024**2}


def public_profile(profile):
    """Keep exact layer proofs, but only counts/hashes of unrelated prior records."""
    value = dict(profile)
    inventory = value.pop('inventory')
    value['nativeInventorySummary'] = {name: {'count': len(rows),
        'sha256': hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
        for name, rows in inventory.items()}
    return value


def node_stage(request):
    result = {'pullStarted': False, 'accepted': False, 'errors': []}
    before = None
    try:
        before = node_observe(request)
        result['before'] = before
        need(before['fits'], 'fresh_complete_missing_peak_does_not_fit_no_pull')
        need(before['rootUUID'] == request['qualified']['rootUUID']
             and before['continuity'] == request['qualified']['continuity'], 'qualified_node_continuity')
        if before['fullyCached']:
            result['method'] = 'already_complete_no_pull'
        else:
            result['pullStarted'] = True
            result['pull'] = collect_pull(CTR + ['--timeout', '15m', 'images', 'pull', '--local', '--platform', 'linux/amd64',
                '--snapshotter', 'overlayfs', '--skip-metadata', '--label', 'io.cri-containerd.image=managed',
                '--max-concurrent-downloads', '1', request['plan']['image']])
            need(result['pull']['exitCode'] == 0 and result['pull']['outputWithinBound'], 'native_pull_failed_no_replay')
            result['method'] = 'canonical_public_digest_pull'
    except Exception as exc:
        result['errors'].append(str(exc) if isinstance(exc, ValueError) else type(exc).__name__)
    finally:
        try:
            after = node_observe(request); result['after'] = after
            if before is not None:
                old, new = before['inventory'], after['inventory']
                result['priorNativeRecordDifferences'] = {
                    'images': {ref: {'before': value, 'after': new['images'].get(ref)}
                               for ref, value in old['images'].items() if new['images'].get(ref) != value},
                    **{k: sorted(set(old[k]) - set(new[k])) for k in ['content', 'leases', 'snapshots']}}
                preserved = (all(new['images'].get(ref) == value for ref, value in old['images'].items())
                             and all(set(old[k]) <= set(new[k]) for k in ['content', 'leases', 'snapshots']))
                result['priorNativeRecordsPreserved'] = preserved
                result['runtimeAndBootPreserved'] = before['continuity'] == after['continuity']
                result['actualFilesystemAllocatedDeltaBytes'] = before['freeBytes'] - after['freeBytes']
                result['actualBudgetRespected'] = max(0, result['actualFilesystemAllocatedDeltaBytes']) <= before['missingPeakBytes']
                result['floorsPreserved'] = after['freeBytes'] >= after['floorAndMarginBytes'] and after['availableBytes'] >= AVAILABLE_FLOOR
                result['accepted'] = (not result['errors'] and after['fullyCached'] and preserved
                    and result['runtimeAndBootPreserved'] and result['actualBudgetRespected'] and result['floorsPreserved'])
        except Exception as exc:
            result['errors'].append('after:' + (str(exc) if isinstance(exc, ValueError) else type(exc).__name__))
    for key in ['before', 'after']:
        if key in result:
            result[key] = public_profile(result[key])
    return result


def dispatch(source, alias, phase, request, password):
    expression = 'public_profile(node_observe(json.load(sys.stdin)))' if phase == 'observe' else 'node_stage(json.load(sys.stdin))'
    code = source + '\ntry:\n print(json.dumps(' + expression + '))\nexcept Exception as exc:\n print(json.dumps({"remoteFailure":str(exc) if isinstance(exc,ValueError) else type(exc).__name__}))\n'
    wrapped = 'exec(compile(' + repr(code) + ", '<official-vendor-memory>', 'exec'), {'__name__':'official_vendor_memory'})"
    argv = ['sudo', '-S', '-p', '', '--', 'python3', '-B', '-c', wrapped]
    p = subprocess.run(SSH + ['james@' + NODES[alias]['ip'], shlex.join(argv)], input=password + b'\n' + json.dumps(request).encode(), capture_output=True,
                       timeout=None if phase == 'stage' else 600)
    need(p.returncode == 0, 'remote_' + phase + '_exit_' + str(p.returncode))
    need(len(p.stdout) <= 8 * 1024**2, 'bounded_remote_metadata')
    value = json.loads(p.stdout)
    need('remoteFailure' not in value, 'remote_' + phase + ':' + value.get('remoteFailure', ''))
    return value


def save(name, value):
    need(re.fullmatch('[a-zA-Z0-9_.-]+', name), 'metadata_filename')
    with os.fdopen(os.open(H / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def same_controls(a, b):
    fields = ['uid', 'conditions', 'nodeInfo', 'evictionHard', 'imageGCHighThresholdPercent', 'imageGCLowThresholdPercent']
    return all(all(a['nodes'][n][k] == b['nodes'][n][k] for k in fields) for n in NODES)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', default='observe', choices=['observe', 'stage'])
    parser.add_argument('--service', required=True, choices=list(PINS))
    parser.add_argument('--node', choices=[*NODES, 'all'], default='all')
    args = parser.parse_args()
    path = Path(__file__).resolve(); repository = path.parents[5]; source = path.read_text(); source_sha = sha(path)
    need(os.geteuid() == 1000 and F.is_mount() and read(['findmnt', '-n', '-o', 'UUID', '-T', str(F)]).decode().strip() == VOLUME, 'existing_owned_F_volume')
    H.mkdir(mode=0o700, parents=True, exist_ok=True)
    need(H.resolve() == H and H.stat().st_uid == os.getuid() and not H.stat().st_mode & 0o077, 'private_declared_output_root')
    if not (H / 'ownership.json').exists():
        save('ownership.json', {'owner': 'official_vendor_preload', 'root': str(H), 'physicalVolumeUUID': VOLUME,
             'generated': 'metadata only here; exact new native image/content/committed snapshot runtime artifacts on original node filesystems',
             'controllerPeakBytes': METADATA_ALLOWANCE, 'nodePeak': 'Only measured missing compressed plus missing revised per-layer unpacked upper plus16MiB; unchanged floors and512MiB margin',
             'protected': 'Every prior image/content/lease/snapshot, runtime configs, Pods, PVCs, NAS, credentials and BORTUS holds',
             'runtimeConsumer': 'Two explicitly approved official image deployments; preserve native caches until deployment/rollback retention is separately reviewed',
             'regenerate': 'Digest-pinned official ctr pull; no archives, dependency trees, extracts or scratch directories'})
    record = {'mode': args.mode, 'service': args.service, 'selectedNode': args.node, 'controllerSHA256': source_sha,
              'startedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'status': 'started', 'nodes': {}}
    name = args.mode + '-' + args.service + '-' + uuid.uuid4().hex + '.json'
    password = None
    try:
        record['controllerSpace'] = controller_space()
        plan = measurement(args.service); record['plan'] = plan
        live = cluster(); record['clusterBefore'] = live
        helper = repository / 'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'
        record['privilegeHelperSHA256'] = sha(helper)
        password = runpy.run_path(str(helper))['privilege_input']()
        if args.mode == 'stage' and args.service == 'ytptube':
            mysql = measurement('mysql')
            previous = {}
            for alias in NODES:
                previous[alias] = dispatch(source, alias, 'observe', {'node': alias, 'plan': mysql, 'cluster': live}, password)
                need(previous[alias]['fullyCached'], 'mysql_first_complete_on_all_nodes_before_ytptube')
            record['mysqlAlreadyCompleteFreshObservation'] = previous
            # Actual free-byte and cache observations, never ratios or old estimates.
            live = cluster()
        # Every stage qualifies ALL THREE nodes before any pull, even --node selects one.
        targets = list(NODES) if args.mode == 'stage' or args.node == 'all' else [args.node]
        for alias in targets:
            record['nodes'][alias] = dispatch(source, alias, 'observe', {'node': alias, 'plan': plan, 'cluster': live}, password)
        if args.mode == 'observe':
            record['status'] = 'observed_read_only'
        else:
            need(all(v['fits'] for v in record['nodes'].values()), 'all_three_nodes_complete_peak_required_before_first_pull')
            qualify_name = 'qualification-' + args.service + '-' + uuid.uuid4().hex + '.json'
            save(qualify_name, {'controllerSHA256': source_sha, 'plan': plan, 'cluster': live, 'nodes': record['nodes']})
            record['qualificationReceipt'] = qualify_name
            record['nodes'] = {alias: {k: v[k] for k in ['fullyCached', 'fits', 'missingPeakBytes', 'rootUUID']}
                               for alias, v in record['nodes'].items()}
            selected = list(NODES) if args.node == 'all' else [args.node]
            record['stageResults'] = {}
            for alias in selected:
                intent_name = args.service + '-' + alias + '-intent.json'
                result_name = args.service + '-' + alias + '-result.json'
                if (H / intent_name).exists() or (H / result_name).exists():
                    need((H / result_name).is_file(), 'intent_without_result_observe_only:' + alias)
                    completed = json.loads((H / result_name).read_bytes())
                    need(completed['controllerSHA256'] == source_sha and completed['accepted'] is True
                         and record['nodes'][alias]['fullyCached'], 'prior_incomplete_or_changed_stage_observe_only:' + alias)
                    record['stageResults'][alias] = {'state': 'verified_completed_no_repull', 'resultSHA256': sha(H / result_name)}
                    continue
                record['controllerSpaceBefore_' + alias] = controller_space()
                fresh_live = cluster()
                need(same_controls(live, fresh_live), 'three_node_controls_stable_before_pull')
                fresh = dispatch(source, alias, 'observe', {'node': alias, 'plan': plan, 'cluster': fresh_live}, password)
                need(fresh['fits'], 'fresh_node_peak_required')
                if fresh['fullyCached']:
                    result = {'controllerSHA256': source_sha, 'measurementSHA256': plan['measurementSHA256'],
                              'accepted': True, 'pullStarted': False, 'after': fresh, 'method': 'verified_existing_complete_canonical'}
                else:
                    packet = {'node': alias, 'plan': plan, 'cluster': fresh_live, 'qualified': fresh}
                    record['controllerSpaceAtDispatch_' + alias] = controller_space()
                    save(intent_name, {'controllerSHA256': source_sha, 'measurementSHA256': plan['measurementSHA256'],
                         'qualificationReceipt': qualify_name, 'node': alias, 'image': plan['image'],
                         'missingPeakBytes': fresh['missingPeakBytes'], 'rootUUID': fresh['rootUUID'],
                         'noUncertainReplay': True, 'startedAt': datetime.datetime.now(datetime.timezone.utc).isoformat()})
                    result = dispatch(source, alias, 'stage', packet, password)
                    result['controllerSHA256'] = source_sha; result['measurementSHA256'] = plan['measurementSHA256']
                save(result_name, result); record['stageResults'][alias] = {'accepted': result['accepted'], 'resultSHA256': sha(H / result_name)}
                need(result['accepted'], 'native_stage_not_accepted_observe_only:' + alias)
            record['clusterAfter'] = cluster()
            need(same_controls(live, record['clusterAfter']), 'original_cluster_controls_preserved')
            record['status'] = 'selected_nodes_staged'
    except BaseException as exc:
        record['status'] = 'failed_or_uncertain_observe_only'
        record['error'] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
    finally:
        password = None
        record['finishedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        record['cleanup'] = {'scratchCreated': False, 'removed': [], 'retained': 'Minimal receipts and required native runtime images only; prior records protected, no pruning'}
        save(name, record)
    print(json.dumps({'status': record['status'], 'receipt': str(H / name), 'error': record.get('error')}))
    return 0 if record['status'] in ['observed_read_only', 'selected_nodes_staged'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
