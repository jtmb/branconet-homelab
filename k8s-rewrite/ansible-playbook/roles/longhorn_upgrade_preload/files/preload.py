"""Stage only the thirteen pinned upstream Longhorn images; never start containers."""
import base64
import contextlib
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

CTR = ['/opt/containerd-k8s/bin/ctr', '--address', '/run/containerd-k8s/containerd.sock',
       '--namespace', 'k8s.io', '--timeout', '10m']
CONTENT = Path('/var/lib/containerd-k8s/io.containerd.content.v1.content/blobs/sha256')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024**2), b''):
            h.update(b)
    return h.hexdigest()


def call(args, timeout=45):
    p = subprocess.run(args, capture_output=True, timeout=timeout)
    need(p.returncode == 0 and len(p.stdout) <= 4 * 1024**2, 'bounded_native_command_' + args[-1])
    return p.stdout


def main():
    r = json.load(sys.stdin)
    p = r['profile']
    need(os.geteuid() == 0 and socket.gethostname() == p['hostname'], 'exact_node_root')
    group = Path('/proc/self/cgroup').read_text().strip().split('::', 1)[1].lstrip('/')
    cg = Path('/sys/fs/cgroup') / group
    need(cg.name == 'branconet-longhorn-prestage-' + p['hostname'] + '-20261028.service', 'exact_bounded_job')
    limits = {k: (cg / k).read_text().strip() for k in ['memory.max', 'memory.swap.max', 'cpu.max', 'pids.max']}
    quota, period = limits['cpu.max'].split()
    need(limits['memory.max'] == '536870912' and limits['memory.swap.max'] == '0'
         and limits['pids.max'] == '96' and quota != 'max' and int(quota) <= int(period), 'actual_preload_limits')
    need(sha(Path(CTR[0])) == 'bcf0357ed9f17b8851ccde2486321c8fa2d0bcfb0ea71c267da6a1155c7f4743', 'exact_qualified_native_client')
    need(CONTENT.resolve() == CONTENT, 'original_runtime_content_path')
    raw = base64.b64decode(r['inspectionSource'], validate=True)
    need(hashlib.sha256(raw).hexdigest() == r['inspectionSHA256'], 'original_hash_bound_readonly_cache_inspector')
    library = {'__name__': 'existing_readonly_native_inspection'}
    exec(compile(raw, '<existing-readonly-native-inspection>', 'exec'), library)

    def inspect():
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            library['remote'](p['cacheProfile'])
        return json.loads(out.getvalue())

    current = p['current']
    now = datetime.datetime.now(datetime.timezone.utc)
    need(0 <= (now - datetime.datetime.fromisoformat(current['UTC'])).total_seconds() <= 120, 'fresh_actual_node_kubelet_longhorn_observation')
    before = inspect()
    need(before['filesystem']['uuid'] == p['filesystemUUID'] and before['filesystem']['fstype'] == 'ext4'
         and before['blockSize'] == 4096 and before['capacityBytes'] == current['capacityBytes'], 'qualified_original_filesystem')
    need(p['marginBytes'] == 512 * 1024**2 and p['hostPayloadBudgetBytes'] == 64 * 1024**2
         and current['minimalAvailablePercent'] == 25 and current['automaticEngineUpgradeLimit'] == '0', 'unchanged_floors_margin_and_manual_engine_control')
    chain_parents = p['cacheProfile']['chains']
    credited = 0
    for key, row in before['candidateSnapshots'].items():
        info = row['nativeInfo']
        need(row['tableKind'] == 'committed' and info['Kind'] == 'Committed' and info['Name'] == key
             and info.get('Parent', '') == chain_parents[key]
             and (not chain_parents[key] or chain_parents[key] in before['candidateSnapshots']), 'complete_committed_cached_chain')
        table = [x.split() for x in row['nativeUsageBytesRaw'].splitlines() if x.strip()]
        need(len(table) == 2 and table[0] == ['KEY', 'SIZE', 'INODES'] and table[1][0] == key, 'native_allocated_usage_bytes')
        credited += int(table[1][1])
    layer_keys = set(p['layerBlobKeys'])
    credited_blobs = sum(x['allocatedBytes'] for x in before['cachedCandidateBlobs'] if x['digest'] in layer_keys)
    payload = p['completeNativeAllocatedBytes'] - credited - credited_blobs
    required = payload + p['marginBytes'] + p['hostPayloadBudgetBytes']
    capacity = before['capacityBytes']
    floor = capacity // 4 + 1
    fs_floor = max(capacity * int(v[:-1]) // 100 for v in current['evictionHard'].values())
    available = min(before['availableBytes'], current['nodeAvailableBytes'], current['imageAvailableBytes'])
    free = min(before['freeBytes'], current['longhornAvailableBytes'])
    need(free >= floor + required and available >= fs_floor + required, 'fresh_complete_coexistence_budget_before_any_write')
    containers_before = call(CTR + ['containers', 'list', '--quiet']).decode().splitlines()
    pod_sandboxes_before = call(CTR + ['tasks', 'list']).decode()
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    result = {'status': 'started', 'node': p['hostname'], 'sourceSHA256': r['sourceSHA256'],
              'resourceLimits': limits, 'nativeBefore': before, 'controllerObservation': current,
              'additionalBudgetBytes': required, 'payloadBudgetBytes': payload,
              'images': [], 'containersStartedByOperator': False, 'workloadOrVolumePatched': False,
              'registryTLSVerificationEnabled': True, 'oldImagesPruned': False,
              'requiredRuntimeConsumer': 'Supported pinned Longhorn 1.13 manager/engine rollout; preserve these runtime artifacts',
              'bootID': boot}
    try:
        listing = call(CTR + ['images', 'list']).decode().splitlines()
        aliases = {cells[0]: cells[2] for line in listing if len(cells := line.split()) >= 3 and cells[2].startswith('sha256:')}
        cached_blobs = {x['digest'] for x in before['cachedCandidateBlobs']}
        cached_chains = set(before['candidateSnapshots'])
        need(len(p['images']) == 13, 'entire_reviewed_consumed_candidate')
        for image in p['images']:
            ref, digest = image['reference'], image['rootDigest']
            need(ref.startswith('docker.io/longhornio/') and ref.endswith('@' + digest), 'exact_public_pinned_reference')
            result['currentImage'] = ref
            need(ref not in aliases or aliases[ref] == digest, 'never_overwrite_conflicting_existing_alias')
            space = os.statvfs(CONTENT)
            need(space.f_bfree * space.f_frsize >= floor + p['marginBytes'] + p['hostPayloadBudgetBytes']
                 and space.f_bavail * space.f_frsize >= fs_floor + p['marginBytes'], 'actual_floor_and_margin_before_each_image')
            complete_cache = set(image['requiredBlobs']) <= cached_blobs and image['chains'][-1]['chainID'] in cached_chains
            sources = sorted(k for k, v in aliases.items() if v == digest and k.startswith('docker.io/longhornio/'))
            if complete_cache and sources:
                if ref not in aliases:
                    call(CTR + ['images', 'tag', sources[0], ref])
                method = 'verified_existing_official_cache'
                log = b''
            else:
                q = subprocess.run(CTR + ['images', 'pull', '--local', '--platform', 'linux/amd64',
                    '--snapshotter', 'overlayfs', '--skip-metadata', '--max-concurrent-downloads', '1',
                    '--label', 'io.cri-containerd.image=managed', ref], capture_output=True, timeout=600)
                log = q.stdout + q.stderr
                result['lastPull'] = {'reference': ref, 'exitCode': q.returncode,
                                      'logSHA256': hashlib.sha256(log).hexdigest(), 'tail': log[-32768:].decode(errors='replace')}
                need(q.returncode == 0 and len(log) <= 4 * 1024**2, 'actual_serial_native_pull_' + ref)
                method = 'official_registry_pull_and_unpack'
            canonical = ref.split('@')[0].rsplit(':', 1)[0] + '@' + digest
            for target in dict.fromkeys([ref, canonical]):
                need(target not in aliases or aliases[target] == digest, 'canonical_alias_preserves_existing_target')
                if target != ref and target not in aliases:
                    call(CTR + ['images', 'tag', ref, target])
                call(CTR + ['images', 'label', target, 'io.cri-containerd.image=managed'])
                aliases[target] = digest
            fresh_listing = call(CTR + ['images', 'list']).decode().splitlines()
            fresh_aliases = {cells[0]: cells[2] for line in fresh_listing
                             if len(cells := line.split()) >= 3 and cells[2].startswith('sha256:')}
            need(fresh_aliases.get(ref) == fresh_aliases.get(canonical) == digest, 'actual_pinned_and_canonical_alias_target_digests')
            for chain in image['chains']:
                info = json.loads(call(CTR + ['snapshots', '--snapshotter', 'overlayfs', 'info', chain['chainID']]))
                need(info['Name'] == chain['chainID'] and info.get('Parent', '') == chain['parent']
                     and info['Kind'] == 'Committed', 'each_actual_complete_unpacked_chain')
            space = os.statvfs(CONTENT)
            need(space.f_bfree * space.f_frsize >= floor + p['marginBytes'] + p['hostPayloadBudgetBytes'], 'actual_floor_and_margin_after_each_image')
            result['images'].append({'reference': ref, 'canonicalReference': canonical, 'method': method,
                                     'logSHA256': hashlib.sha256(log).hexdigest(), 'freeBytesAfter': space.f_bfree * space.f_frsize})
        after = inspect()
        need(before['runtime'] == after['runtime'] and Path('/proc/sys/kernel/random/boot_id').read_text().strip() == boot,
             'existing_runtime_and_boot_preserved')
        need(sha(Path(CTR[0])) == 'bcf0357ed9f17b8851ccde2486321c8fa2d0bcfb0ea71c267da6a1155c7f4743', 'original_native_client_preserved')
        need(set(p['cacheProfile']['blobs']) <= {x['digest'] for x in after['cachedCandidateBlobs']}
             and set(chain_parents) <= set(after['candidateSnapshots']), 'all_reviewed_public_content_and_chains_fully_verified')
        need(all(row['tableKind'] == 'committed' and row['nativeInfo']['Kind'] == 'Committed'
                 for row in after['candidateSnapshots'].values()), 'all_final_chains_committed')
        actual_delta = max(0, before['freeBytes'] - after['freeBytes'])
        need(actual_delta <= payload and after['freeBytes'] >= floor + p['marginBytes'] + p['hostPayloadBudgetBytes'],
             'actual_native_allocation_within_complete_budget')
        result.update(status='all_thirteen_production_images_staged_and_verified', nativeAfter=after,
                      actualFilesystemFreeDeltaBytes=actual_delta, completedUTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      containersBefore=len(containers_before), tasksBeforeSHA256=hashlib.sha256(pod_sandboxes_before.encode()).hexdigest())
        result.pop('currentImage', None)
        result.pop('lastPull', None)
    except Exception as e:
        result.update(status='failed_preserve_runtime_and_receipts', errorType=type(e).__name__,
                      failedCheck=str(e) if isinstance(e, ValueError) else type(e).__name__)
        raise
    finally:
        print(json.dumps(result))


if __name__ == '__main__':
    main()
