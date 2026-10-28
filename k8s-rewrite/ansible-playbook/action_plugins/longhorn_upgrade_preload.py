"""Fresh per-node capacity fencing and serial, source-bound upstream staging."""
import base64
import datetime
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
from ansible.plugins.action import ActionBase

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
O = F / 'platform-upstream-review-20261027'
B = O / 'longhorn-capacity-budget'
U = O / 'longhorn-production-prestage-20261028'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def get(args):
    p = subprocess.run(SSH + ['kubectl', *args], stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
    need(p.returncode == 0 and len(p.stdout) <= 4 * 1024**2, 'bounded_live_api_read')
    return json.loads(p.stdout)


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        if self._task.check_mode:
            return dict(result, skipped=True, changed=False)
        name = task_vars['inventory_hostname']
        need(name in ('masternode', 'workernode2', 'workernode1') and F.is_mount(), 'fixed_cluster_and_output_mount')
        target = U / ('node-' + name + '-result.json')
        intent = U / ('node-' + name + '-intent.json')
        need(U.is_dir() and not target.exists() and not intent.exists(), 'preserve_prior_operation_or_live_job')
        source = Path(self._loader.get_basedir()).parent / 'roles/longhorn_upgrade_preload/files/preload.py'
        binding = json.loads((U / 'source-binding.json').read_text())
        need(all(sha(Path(p)) == h for p, h in binding['sources'].items()), 'unchanged_reviewed_operator_sources')
        raw = source.read_bytes()
        native = json.loads((B / 'native-unpack-20261027/native-result.json').read_text())
        candidate = json.loads((O / 'longhorn-prepared-v1.13.0/receipt.json').read_text())
        host = json.loads((B / 'host-engine-payload-result.json').read_text())
        gate = json.loads((B / 'post-analysis-cache-native-budgets.json').read_text())
        inspection = B / 'cache-refresh-post-analysis-cache-cleanup.py'
        cache = json.loads((B / 'node-cache-post-analysis-cache-cleanup.json').read_text())
        need(native['status'] == 'all_thirteen_native_unpacks_verified' and native['privateDaemonExitCode'] == 0
             and gate['allThreeFitObservedFloorsAndMargin'] and cache['sourceSHA256'] == sha(inspection)
             and host['status'] == 'host_engine_payload_authenticated', 'complete_actual_native_and_recovery_preparation')
        need(sorted(x['reference'] for x in native['images']) == sorted(candidate['consumedPinnedReferences'])
             and len(native['images']) == 13, 'exact_full_consumed_pinned_candidate')
        images, blobs, chains = [], {}, {}
        for row in native['images']:
            component = row['reference'].split('/')[2].split(':')[0]
            metadata = json.loads((O / (component + '-metadata.json')).read_text())
            image_blobs = {metadata['rootDigest']: None, row['amd64ManifestDigest']: None,
                           metadata['manifest']['config']['digest']: metadata['manifest']['config']['size']}
            for layer in metadata['manifest']['layers']:
                image_blobs[layer['digest']] = layer['size']
            blobs.update(image_blobs)
            for chain in row['chains']:
                need(chain['chainID'] not in chains or chains[chain['chainID']] == chain['parent'], 'unique_chain_parent')
                chains[chain['chainID']] = chain['parent']
            images.append({'reference': row['reference'], 'rootDigest': metadata['rootDigest'],
                           'requiredBlobs': sorted(image_blobs), 'chains': row['chains']})
        node = get(['get', 'node', name, '-o', 'json'])
        need(any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions'])
             and not any(c['type'].endswith('Pressure') and c['status'] == 'True' for c in node['status']['conditions']), 'actual_ready_node_without_pressure')
        lh = get(['get', 'nodes.longhorn.io', name, '-n', 'longhorn-system', '-o', 'json'])
        need(lh['spec']['allowScheduling'] and len(lh['status']['diskStatus']) == 1, 'unchanged_scheduling_and_single_original_disk')
        disk = next(iter(lh['status']['diskStatus'].values()))
        need(all(any(c['type'] == kind and c['status'] == 'True' for c in disk['conditions'])
                 for kind in ('Ready', 'Schedulable')), 'healthy_schedulable_disk')
        settings = {k: get(['get', 'settings.longhorn.io', k, '-n', 'longhorn-system', '-o', 'json'])['value']
                    for k in ['current-longhorn-version', 'storage-minimal-available-percentage',
                              'concurrent-automatic-engine-upgrade-per-node-limit']}
        need(settings['current-longhorn-version'] == 'v1.12.1' and settings['storage-minimal-available-percentage'] == '25'
             and settings['concurrent-automatic-engine-upgrade-per-node-limit'] == '0', 'no_unexpected_upgrade_or_control_change')
        stats = get(['get', '--raw', '/api/v1/nodes/' + name + '/proxy/stats/summary'])['node']
        config = get(['get', '--raw', '/api/v1/nodes/' + name + '/proxy/configz'])['kubeletconfig']
        eviction = {k: config['evictionHard'][k] for k in ('imagefs.available', 'nodefs.available')}
        need(all(v.endswith('%') and v[:-1].isdigit() for v in eviction.values()), 'actual_percentage_eviction_controls')
        capacity = disk['storageMaximum']
        need(capacity == stats['fs']['capacityBytes'] == stats['runtime']['imageFs']['capacityBytes'], 'same_actual_runtime_kubelet_longhorn_filesystem')
        current = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'nodeUID': node['metadata']['uid'],
                   'longhornNodeUID': lh['metadata']['uid'], 'diskUUID': disk['diskUUID'], 'capacityBytes': capacity,
                   'longhornAvailableBytes': disk['storageAvailable'], 'nodeAvailableBytes': stats['fs']['availableBytes'],
                   'imageAvailableBytes': stats['runtime']['imageFs']['availableBytes'], 'evictionHard': eviction,
                   'minimalAvailablePercent': 25, 'automaticEngineUpgradeLimit': '0'}
        baseline = next(v for v in cache['nodes'].values() if v['hostname'] == name)
        profile = {'hostname': name, 'filesystemUUID': baseline['filesystem']['uuid'],
                   'cacheProfile': {'hostname': name, 'blobs': blobs, 'chains': chains},
                   'layerBlobKeys': sorted({c['blobSHA256'] for x in native['images'] for c in x['chains']}),
                   'completeNativeAllocatedBytes': native['actualAllocatedBytes'], 'marginBytes': 512 * 1024**2,
                   'hostPayloadBudgetBytes': host['hostAllocationBudgetBytes'], 'images': images, 'current': current}
        payload = {'profile': profile, 'inspectionSource': base64.b64encode(inspection.read_bytes()).decode(),
                   'inspectionSHA256': sha(inspection), 'sourceSHA256': hashlib.sha256(raw).hexdigest()}
        with intent.open('x') as out:
            json.dump({'profile': profile, 'sourceSHA256': payload['sourceSHA256'], 'sourceBindingSHA256': sha(U / 'source-binding.json'),
                       'runtimeConsumer': 'Reviewed official Longhorn 1.13 manager/engine rollout', 'containersToStart': 0}, out, indent=2)
        command = ['systemd-run', '--quiet', '--wait', '--pipe', '--collect',
                   '--unit=branconet-longhorn-prestage-' + name + '-20261028',
                   '--description=Branconet guarded pinned upstream Longhorn image staging',
                   '--property=MemoryMax=536870912', '--property=MemorySwapMax=0',
                   '--property=CPUQuota=100%', '--property=TasksMax=96', '--property=Nice=10',
                   '--property=RuntimeMaxSec=2100', '--property=NoNewPrivileges=yes',
                   '--property=ProtectSystem=strict', '--property=ProtectHome=read-only',
                   '--property=InaccessiblePaths=-/root/.docker -/home/james/.docker',
                   '/usr/bin/python3', '-B', '-c', raw.decode()]
        record = {'status': 'observation_started', 'sourceSHA256': payload['sourceSHA256'], 'intentSHA256': sha(intent)}
        try:
            response = self._low_level_execute_command(shlex.join(command), sudoable=True, in_data=json.dumps(payload).encode())
            record.update(rc=response['rc'], stderr=response.get('stderr', ''))
            try:
                record['result'] = json.loads(response.get('stdout', ''))
            except (ValueError, TypeError):
                record['unparsedStdout'] = response.get('stdout', '')
            record['status'] = 'completed' if response['rc'] == 0 else 'failed_preserve_runtime_and_receipts'
        finally:
            record['sourcesUnchanged'] = all(sha(Path(p)) == h for p, h in binding['sources'].items())
            with target.open('x') as out:
                json.dump(record, out)
        ok = record.get('rc') == 0 and record.get('result', {}).get('status') == 'all_thirteen_production_images_staged_and_verified' and record['sourcesUnchanged']
        return dict(result, changed=bool(record.get('result', {}).get('images')), failed=not ok, receipt=str(target))
