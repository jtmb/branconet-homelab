"""Calculate image coexistence from authenticated layers and exact native cache.

This is a dated capacity calculation, not permission to pull or upgrade.
"""
import datetime
import hashlib
import json
from pathlib import Path

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
B = F / 'platform-upstream-review-20261027/longhorn-capacity-budget'
CORE = {'longhorn-manager', 'longhorn-engine', 'longhorn-instance-manager',
        'csi-node-driver-registrar', 'livenessprobe'}
MARGIN = 512 * 1024**2


def need(value, reason):
    if not value:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((B / name).read_text())


def blocks(value):
    return (value + 4095) // 4096 * 4096


def budget(images, node):
    cached = {x['digest'] for x in node['cachedCandidateBlobs'] if x['fullSHA256Verified']}
    snapshots = node['candidateSnapshots']
    content, chains = {}, {}
    metadata = 0
    for image in images:
        parent = ''
        for layer in image['layers']:
            need(layer['compressedHashVerified'] and layer['uncompressedHashVerified'], 'fully_measured_layer')
            if layer['digest'] not in cached:
                content[layer['digest']] = blocks(layer['compressedBytes'])
            key = layer['diffID'] if not parent else 'sha256:' + hashlib.sha256((parent + ' ' + layer['diffID']).encode()).hexdigest()
            if key in snapshots:
                info = snapshots[key]['nativeInfo']
                need(snapshots[key]['tableKind'] == 'committed' and info['Kind'] == 'Committed'
                     and info['Name'] == key and info.get('Parent', '') == parent
                     and (not parent or parent in snapshots), 'complete_committed_cached_parent_chain')
                labels = info.get('Labels', {})
                need(labels.get('containerd.io/snapshot/diff-id', layer['diffID']) == layer['diffID'], 'native_diff_id_identity')
            else:
                chains[key] = layer['projectedFilesystemBytes']
            parent = key
        component = image['reference'].split('/')[2].split(':')[0]
        retained = json.loads((B.parent / (component + '-metadata.json')).read_text())
        root_size_bound = 4 * 1024**2  # actual authenticated index reader's ceiling
        platform_size = next(m['size'] for m in retained['root']['manifests']
                             if m['digest'] == image['amd64ManifestDigest'])
        for digest, size in [(retained['rootDigest'], root_size_bound),
                             (image['amd64ManifestDigest'], platform_size),
                             (image['configurationDigest'], retained['manifest']['config']['size'])]:
            if digest not in cached:
                metadata += blocks(size)
    compressed, unpack = sum(content.values()), sum(chains.values())
    return {'components': [x['reference'].split('/')[2].split(':')[0] for x in images],
            'missingBlobCount': len(content), 'missingCompressedAllocatedProjectionBytes': compressed,
            'missingSnapshotCount': len(chains), 'missingSnapshotAllocatedProjectionBytes': unpack,
            'metadataAllocatedUpperBoundBytes': metadata, 'operatingMarginBytes': MARGIN,
            'additionalRequiredBytes': compressed + unpack + metadata + MARGIN,
            'cachedContentAndSnapshotsAreAlreadyInCurrentUsage': True,
            'noCreditForDeletionOrOldImagePruning': True}


def threshold(value, capacity):
    need(value.endswith('%'), 'observed_percentage_eviction_threshold')
    return capacity * int(value[:-1]) // 100


def main():
    need(F.is_mount(), 'existing_physical_output_root')
    measured, cache, live = (read(n) for n in ('measurement-result.json', 'node-cache-inventory.json', 'current-live.json'))
    need(measured['status'] == cache['status'] == 'completed' and measured['allLayersFullyAuthenticated'], 'complete_authenticated_inputs')
    need(read('measurement-terminal.json')['exitCode'] == 0
         and sha(B / 'measure-images-frozen.py') == measured['sourceSHA256']
         and sha(B / 'cache-inspection-frozen.py') == cache['sourceSHA256']
         and sha(B / 'measurement-result.json') == cache['measuredResultSHA256'], 'executed_source_and_measurement_bindings')
    percent = int(live['settings']['storage-minimal-available-percentage'])
    need(percent == 25 and live['settings']['concurrent-automatic-engine-upgrade-per-node-limit'] == '0', 'unchanged_storage_controls')
    result = {'schema': 1, 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'status': 'completed_dated_calculation', 'sourceSHA256': sha(Path(__file__)),
              'inputs': {n: sha(B / n) for n in ('measurement-result.json', 'node-cache-inventory.json', 'current-live.json')},
              'imageProjectionIsNativeUnpackMeasurement': False, 'longhornMinimalAvailablePercent': percent,
              'nodes': [], 'clusterMutated': False, 'pullOrUpgradeAuthorizedByCalculation': False,
              'replicaRecoveryBudgetIsSeparateFromImageBudget': True}
    for address, node in cache['nodes'].items():
        hostname = node['hostname']
        lh = next(n for n in live['longhornNodes'] if n['name'] == hostname)
        need(len(lh['disks']) == 1 and node['blockSize'] == 4096, 'observed_single_root_disk_projection')
        disk = next(iter(lh['disks'].values()))
        capacity = disk['storageMaximum']
        need(capacity == node['capacityBytes'], 'same_observed_runtime_and_longhorn_capacity')
        fs = live['filesystem'][hostname]
        kube = fs['runtimeFS']['imageFs']
        need(kube['capacityBytes'] == fs['nodeFS']['capacityBytes'] == capacity, 'same_observed_runtime_and_node_fs')
        available = min(node['availableBytes'], kube['availableBytes'], fs['nodeFS']['availableBytes'])
        lh_available = min(node['freeBytes'], disk['storageAvailable'])
        kube_floor = max(threshold(fs['evictionHard'][k], capacity) for k in ('imagefs.available', 'nodefs.available'))
        lh_floor = capacity * percent // 100 + 1
        entry = {'hostname': hostname, 'address': address, 'filesystemUUID': node['filesystem']['uuid'],
                 'runtimeCacheObservedUTC': node['UTC'], 'longhornObservedUTC': live['UTC'],
                 'kubeletAvailableBytes': available, 'kubeletEvictionFloorBytes': kube_floor,
                 'longhornAvailableBytes': lh_available, 'longhornSchedulingFloorBytes': lh_floor,
                 'longhornSchedulingReserveBytes': next(iter(lh['disks'].values()))['storageReserved'],
                 'cachedAuthenticatedCandidateBlobs': len(node['cachedCandidateBlobs']),
                 'cachedCommittedCandidateSnapshots': len(node['candidateSnapshots']), 'profiles': {}}
        for label, images in [('core_node', [x for x in measured['images'] if x['reference'].split('/')[2].split(':')[0] in CORE]),
                              ('complete_candidate', measured['images'])]:
            projected = budget(images, node)
            amount = projected['additionalRequiredBytes']
            projected.update(kubeletSurplusAfterProjectionBytes=available - kube_floor - amount,
                             longhornSurplusAfterProjectionBytes=lh_available - lh_floor - amount,
                             additionalHeadroomNeededBytes=max(0, kube_floor + amount - available, lh_floor + amount - lh_available))
            projected['fitsObservedFloorsAndMargin'] = projected['additionalHeadroomNeededBytes'] == 0
            entry['profiles'][label] = projected
        result['nodes'].append(entry)
    result['largestObservedVolumeActualSizeBytes'] = max(int(v['actualSize'] or 0) for v in live['volumes'])
    result['remainingGates'] = ['Fresh capacity/cache checks immediately before writes',
        'Exact component placement and any non-image host payload', 'Application and detached dataset recovery coverage',
        'Replica recovery placement/capacity', 'Separate Ingenium owner verification hold',
        'Reviewed existing-owner manifest, server dry-run and guarded Ansible upgrade']
    target = B / 'calculated-node-budgets.json'
    need(not target.exists(), 'preserve_prior_calculation')
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps([{'node': n['hostname'], 'coreNeeded': n['profiles']['core_node']['additionalRequiredBytes'],
                      'coreHeadroomMissing': n['profiles']['core_node']['additionalHeadroomNeededBytes'],
                      'completeNeeded': n['profiles']['complete_candidate']['additionalRequiredBytes'],
                      'completeHeadroomMissing': n['profiles']['complete_candidate']['additionalHeadroomNeededBytes']}
                     for n in result['nodes']], indent=2))


if __name__ == '__main__':
    main()
