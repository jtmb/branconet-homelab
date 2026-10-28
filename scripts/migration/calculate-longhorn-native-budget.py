"""Dated full-candidate capacity gate using exact native unpack and cache usage.

No pull, upgrade, placement or replica change is performed or authorized here.
Keep the complete measured operator overhead, all old images, the existing
512 MiB operating margin and unchanged kubelet/Longhorn floors in the budget.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
O = F / 'platform-upstream-review-20261027'
B = O / 'longhorn-capacity-budget'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observation', choices=['post-transfer', 'post-analysis-cache'], default='post-transfer')
    observation = parser.parse_args().observation
    paths = {'native': B / 'native-unpack-20261027/native-result.json',
             'cache': B / ('node-cache-' + observation + '-cleanup.json'),
             'live': B / (observation + '-current-live.json'),
             'host': B / 'host-engine-payload-result.json',
             'prepared': O / 'longhorn-prepared-v1.13.0/receipt.json'}
    values = {k: json.loads(p.read_text()) for k, p in paths.items()}
    n, c, live, host, prepared = (values[k] for k in ['native', 'cache', 'live', 'host', 'prepared'])
    need(F.is_mount() and n['status'] == 'all_thirteen_native_unpacks_verified'
         and c['status'] == 'completed' and n['privateDaemonExitCode'] == 0,
         'actual_completed_native_measurement_and_fresh_cache')
    need(c['sourceSHA256'] == sha(B / ('cache-refresh-' + observation + '-cleanup.py'))
         and c['measuredResultSHA256'] == sha(B / 'measurement-result.json'), 'fresh_hash_bound_native_cache')
    need(host['status'] == 'host_engine_payload_authenticated' and host['hostEngine']['bytes'] == 47761336
         and host['hostAllocationBudgetBytes'] == 64 * 1024**2
         and host['sourceSHA256'] == sha(B / 'host-engine-payload-frozen.py'), 'exact_authenticated_host_payload')
    refs = sorted(x['reference'] for x in n['images'])
    need(len(refs) == 13 and refs == sorted(prepared['consumedPinnedReferences']), 'entire_exact_consumed_candidate_not_core_only')
    need(live['settings']['storage-minimal-available-percentage'] == '25'
         and live['settings']['concurrent-automatic-engine-upgrade-per-node-limit'] == '0', 'unchanged_storage_controls')
    chains, blobs = {}, set()
    for image in n['images']:
        parent = ''
        for row in image['chains']:
            need(row['parent'] == parent, 'complete_native_parent_order')
            need(row['chainID'] not in chains or chains[row['chainID']] == parent, 'unique_committed_chain_parent')
            chains[row['chainID']] = parent
            blobs.add(row['blobSHA256'])
            parent = row['chainID']
    out = {'status': 'completed_dated_capacity_gate', 'sourceSHA256': sha(Path(__file__)),
           'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'inputSHA256': {k: sha(p) for k, p in paths.items()}, 'consumedPinnedReferences': refs,
           'completeNativeAllocatedBytesIncludingOperatorOverhead': n['actualAllocatedBytes'],
           'operatingMarginBytes': 512 * 1024**2, 'additionalHostPayloadBudgetBytes': host['hostAllocationBudgetBytes'],
           'oldImageOrReplicaDeletionCredited': False, 'productionNodeUnpackClaimed': False,
           'clusterMutated': False, 'upgradeAuthorizedByCalculation': False, 'nodes': []}
    for address, node in c['nodes'].items():
        need(node['blockSize'] == 4096 and node['filesystem']['fstype'] == 'ext4', 'observed_native_filesystem_geometry')
        cached = [x for x in node['cachedCandidateBlobs'] if x['digest'] in blobs]
        need(all(x['fullSHA256Verified'] for x in cached), 'full_cached_compressed_hashes')
        credit_snapshots = 0
        credited_keys = []
        for key, row in node['candidateSnapshots'].items():
            if key not in chains:
                continue
            info = row['nativeInfo']
            parent = chains[key]
            need(row['tableKind'] == 'committed' and info['Kind'] == 'Committed' and info['Name'] == key
                 and info.get('Parent', '') == parent and (not parent or parent in node['candidateSnapshots']), 'exact_committed_cached_parent_chain')
            table = [x.split() for x in row['nativeUsageBytesRaw'].splitlines() if x.strip()]
            need(len(table) == 2 and table[0] == ['KEY', 'SIZE', 'INODES'] and len(table[1]) == 3
                 and table[1][0] == key and table[1][1].isdigit() and table[1][2].isdigit(), 'actual_native_byte_usage_output')
            credit_snapshots += int(table[1][1])
            credited_keys.append(key)
        credit_blobs = sum(x['allocatedBytes'] for x in cached)
        required = n['actualAllocatedBytes'] - credit_blobs - credit_snapshots + out['operatingMarginBytes'] + out['additionalHostPayloadBudgetBytes']
        lh = next(x for x in live['longhornNodes'] if x['name'] == node['hostname'])
        need(len(lh['disks']) == 1, 'same_single_root_disk')
        disk = next(iter(lh['disks'].values()))
        fs = live['filesystem'][node['hostname']]
        capacity = node['capacityBytes']
        need(disk['storageMaximum'] == fs['runtimeFS']['imageFs']['capacityBytes'] == fs['nodeFS']['capacityBytes'] == capacity,
             'same_actual_kubelet_longhorn_runtime_filesystem')
        available = min(node['availableBytes'], fs['runtimeFS']['imageFs']['availableBytes'], fs['nodeFS']['availableBytes'])
        free = min(node['freeBytes'], disk['storageAvailable'])
        floors = [fs['evictionHard'][k] for k in ['imagefs.available', 'nodefs.available']]
        need(all(x.endswith('%') and x[:-1].isdigit() for x in floors), 'actual_unchanged_percentage_kubelet_floors')
        kube_floor = max(capacity * int(x[:-1]) // 100 for x in floors)
        lh_floor = capacity // 4 + 1
        kube_surplus, lh_surplus = available - kube_floor - required, free - lh_floor - required
        out['nodes'].append({'hostname': node['hostname'], 'address': address, 'filesystemUUID': node['filesystem']['uuid'],
                             'cacheObservedUTC': node['UTC'], 'longhornObservedUTC': live['UTC'],
                             'cachedFullHashBlobCreditBytes': credit_blobs, 'cachedCommittedSnapshotCreditBytes': credit_snapshots,
                             'creditedSnapshotKeys': credited_keys, 'additionalRequiredBytes': required,
                             'kubeletAvailableBytes': available, 'kubeletFloorBytes': kube_floor,
                             'longhornAvailableBytes': free, 'longhornFloorBytes': lh_floor,
                             'kubeletSurplusAfterProjectionBytes': kube_surplus,
                             'longhornSurplusAfterProjectionBytes': lh_surplus,
                             'fitsObservedFloorsAndMargin': min(kube_surplus, lh_surplus) >= 0})
    out['allThreeFitObservedFloorsAndMargin'] = len(out['nodes']) == 3 and all(x['fitsObservedFloorsAndMargin'] for x in out['nodes'])
    with (B / (observation + '-native-budgets.json')).open('x') as f:
        json.dump(out, f, indent=2)
    print(json.dumps({'allThreeFit': out['allThreeFitObservedFloorsAndMargin'], 'nodes': [
        {k: n[k] for k in ['hostname', 'additionalRequiredBytes', 'longhornSurplusAfterProjectionBytes']} for n in out['nodes']]}))


if __name__ == '__main__':
    main()
