#!/usr/bin/env python3
"""RAM-only master guard/normal-auth observation; invoked by the recovery controller.

No resource mutation, SQL administration, file creation, or credential output.
"""
import copy
import hashlib
import importlib.util
import json
import resource
import sys

OBSERVER = '/home/james/.local/share/branconet-migration/acceptance-ruckus-20261025/copy-observer-3284b56f3d7e.py'
OBSERVER_SHA = '3284b56f3d7e7f0a570d84823a3a5b3a1c8067249156450bc061af2dadda3751'
IMAGE = 'docker.io/library/ruckusdb-security-20261023@sha256:2f0c391e6c04501862598bbc5446165f8ebba08025168451f6f6447352316349'
OLD = 'ruckus-db-data-0'
CURRENT = 'ruckus-db-data-0-security-20261025'
CHILD = 'security-data-20261025'
CLAIMS = {
    OLD: ('2f604004-b45f-4061-bdc4-43f5ca2f7fd8', 'ac9b38c6-ee0c-4e2b-bfc0-03a188e889d1', 'db76a18a-7b5e-4acc-a342-6d7908cc5f0d'),
    CURRENT: ('0bf707c8-628e-4284-9aa0-35b711c8749b', 'd6706cd4-91a7-449f-a41f-8434108f047e', 'e574f5cc-d66f-4ed8-9379-29ee155ce42f'),
}
REPLICAS = {
    'pvc-2f604004-b45f-4061-bdc4-43f5ca2f7fd8-r-58fd1121': ('91008363-9d86-490d-88c9-ef64b5265680', 'workernode2'),
    'pvc-2f604004-b45f-4061-bdc4-43f5ca2f7fd8-r-dcdb6543': ('1e878b44-87c5-405a-9246-2c2a277018f1', 'workernode1'),
}


def need(ok, code):
    if not ok:
        raise RuntimeError(code)


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def terminal(p):
    return p['status'].get('phase') in ('Failed', 'Succeeded') and not any(
        'running' in s.get('state', {}) for kind in ('containerStatuses', 'initContainerStatuses', 'ephemeralContainerStatuses')
        for s in p['status'].get(kind, []))


def subset(expected, actual):
    # Kubernetes defaults are allowed; every explicit plan field must be exact.
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and subset(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(subset(a, b) for a, b in zip(expected, actual))
    return expected == actual


def guard(q, x, key):
    live = x['phase'] in ('baseline', 'after', 'restart')
    recovered = x['phase'] in ('after', 'restart')
    expected_claim = OLD if recovered else CURRENT
    expected_subpath = CHILD + '/data-0' if recovered else 'data-0'
    identity = {'claims': {}}
    for name, (cuid, puid, luid) in CLAIMS.items():
        c = q.get('pvc', name); p = q.get('pv', c['spec']['volumeName'], None)
        need(c['metadata']['uid'] == cuid and p['metadata']['uid'] == puid, 'claim_pv_uids')
        need(not c['metadata'].get('deletionTimestamp') and not p['metadata'].get('deletionTimestamp'), 'claims_retained')
        need(c['status']['phase'] == 'Bound' and c['spec']['storageClassName'] == 'longhorn', 'claim_bound_longhorn')
        need(c['spec']['volumeName'] == 'pvc-' + cuid and p['spec']['claimRef']['uid'] == cuid, 'claim_binding')
        need(p['spec']['csi']['driver'] == 'driver.longhorn.io' and p['spec']['csi']['volumeHandle'] == 'pvc-' + cuid, 'volume_handle')
        need(p['spec']['persistentVolumeReclaimPolicy'] == 'Retain' and p['spec']['capacity']['storage'] == '1Gi', 'retain_capacity')
        v = q.get('volumes.longhorn.io', 'pvc-' + cuid, 'longhorn-system')
        need(v['metadata']['uid'] == luid and not v['metadata'].get('deletionTimestamp'), 'volume_uid')
        need(v['spec']['numberOfReplicas'] == 2 and str(v['spec']['size']) == '1073741824', 'replica_count_capacity')
        identity['claims'][name] = {'pvc_uid': cuid, 'pv_uid': puid, 'volume_uid': luid,
                                    'pvc_spec_sha256': sha(c['spec']), 'pv_spec_sha256': sha(p['spec'])}
    d, bot = q.get('deployment', 'ruckus-db'), q.get('deployment', 'ruckus-bot')
    hr, bhr = q.get('helmrelease', 'ruckus-db', 'flux-system'), q.get('helmrelease', 'ruckus-bot', 'flux-system')
    for obj, name in [(d, 'deployment'), (bot, 'bot'), (hr, 'release'), (bhr, 'bot_release')]:
        need(obj['metadata']['uid'] == q.IDS[name] and not obj['metadata'].get('deletionTimestamp'), 'workload_uid')
        need(obj['status'].get('observedGeneration', 0) >= obj['metadata']['generation'], 'observed_generation')
        identity[name + '_uid'] = obj['metadata']['uid']
    for dep, release, count in [(d, hr, int(live)), (bot, bhr, 0)]:
        need(dep['spec'].get('replicas', 1) == count and all(dep['status'].get(k, 0) == count for k in ('replicas', 'readyReplicas', 'updatedReplicas', 'availableReplicas')), 'writer_replica_fence')
        need(release['spec'].get('values', {}).get('replicaCount') == count and not release['spec'].get('suspend', False), 'flux_replica_fence')
        need(any(c['type'] == 'Ready' and c['status'] == 'True' for c in release['status'].get('conditions', [])), 'flux_ready')
    t = d['spec']['template']['spec']; c = t['containers'][0]
    need(len(t['containers']) == 1 and not t.get('initContainers') and not t.get('ephemeralContainers'), 'db_surface')
    need(c['name'] == 'ruckus-db' and c['image'] == IMAGE and not c.get('command') and not c.get('args'), 'same_normal_image')
    need(c.get('envFrom') == [{'secretRef': {'name': 'ruckus-db-runtime'}}], 'native_secret_reference')
    need('fsGroup' not in t.get('securityContext', {}), 'no_fsgroup')
    need(len(t['volumes']) == 1 and t['volumes'][0]['persistentVolumeClaim'] == {'claimName': expected_claim}, 'exact_db_claim')
    mounts = [{'name': t['volumes'][0]['name'], 'mountPath': '/var/lib/mysql', 'subPath': expected_subpath}]
    need(c.get('volumeMounts') == mounts, 'exact_db_subpath')
    normalized = copy.deepcopy(t)
    normalized['volumes'][0]['persistentVolumeClaim']['claimName'] = CURRENT
    normalized['containers'][0]['volumeMounts'][0]['subPath'] = 'data-0'
    identity['db_template_hmac'] = q.mac(key, 'ha-db-template', normalized)
    identity['bot_template_hmac'] = q.mac(key, 'ha-bot-template', bot['spec']['template'])
    service = q.get('service', 'ruckus-db')
    identity['service_uid'] = service['metadata']['uid']
    identity['service_spec_hmac'] = q.mac(key, 'ha-service', service['spec'])
    need(service['spec'].get('clusterIP') not in (None, '', 'None'), 'service_ip')
    values, native = q.native(key)
    identity['native_secret'] = native
    identity['key_id'] = q.mac(key, 'key-id', b'ruckusdb')
    if x.get('baseline_identity'):
        need(identity == x['baseline_identity'], 'all_preserved_native_identities')
    reader_uid = None
    if x.get('reader'):
        r = x['reader']; plan = r['plan']; policy_plan, pod_plan = plan['items']
        p = q.get('pod', pod_plan['metadata']['name']); policy = q.get('networkpolicy', policy_plan['metadata']['name'])
        need(p['metadata']['uid'] == r['pod_uid'] and policy['metadata']['uid'] == r['policy_uid'], 'reader_policy_uids')
        need(not p['metadata'].get('deletionTimestamp') and not policy['metadata'].get('deletionTimestamp'), 'reader_not_deleting')
        # The API omits empty ingress/egress slices. Restore ONLY these known
        # empty defaults; any real rule, selector, policy type or extra field
        # must still compare exactly with the deny-all plan.
        policy_spec = copy.deepcopy(policy['spec'])
        for direction in ('ingress', 'egress'):
            policy_spec.setdefault(direction, [])
        need(p['metadata'].get('labels', {}) == pod_plan['metadata']['labels'] and policy_spec == policy_plan['spec'], 'exact_deny_all')
        # These nonpointer Pod/PVC booleans default to false and are omitted
        # from JSON. Pointer booleans such as automountServiceAccountToken and
        # enableServiceLinks remain mandatory, because their defaults differ.
        reader_spec = copy.deepcopy(p['spec'])
        for field in ('hostNetwork', 'hostPID', 'hostIPC'):
            reader_spec.setdefault(field, False)
        for volume in reader_spec.get('volumes', []):
            if 'persistentVolumeClaim' in volume:
                volume['persistentVolumeClaim'].setdefault('readOnly', False)
        need(subset(pod_plan['spec'], reader_spec), 'reader_plan_fields')
        need(not p['spec'].get('initContainers') and not p['spec'].get('ephemeralContainers'), 'reader_no_extra_containers')
        need('fsGroup' not in p['spec'].get('securityContext', {}) and not p['spec'].get('securityContext', {}).get('supplementalGroups'), 'reader_no_group_rewrite')
        pc = p['spec']['containers'][0]
        need(not pc.get('env') and not pc.get('envFrom') and not pc.get('args') and not pc.get('lifecycle'), 'reader_no_injected_execution')
        need(not pc.get('securityContext', {}).get('privileged') and pc.get('securityContext', {}).get('procMount', 'Default') == 'Default', 'reader_no_extra_privilege')
        need(p['status']['phase'] == 'Running' and p['spec']['nodeName'] == 'workernode2', 'reader_node_running')
        sts = p['status']['containerStatuses']
        need(len(sts) == 1 and sts[0]['ready'] and sts[0]['imageID'] == pc['image'], 'exact_reader_runtime')
        reader_uid = p['metadata']['uid']
    dbpod = None
    for p in q.get('pods')['items']:
        if terminal(p):
            continue
        labels = p['metadata'].get('labels', {})
        need(not all(labels.get(k) == v for k, v in bot['spec']['selector']['matchLabels'].items()), 'bot_pods_absent')
        uses = {v.get('persistentVolumeClaim', {}).get('claimName') for v in p['spec'].get('volumes', [])}
        if not uses.intersection(CLAIMS):
            continue
        if p['metadata']['uid'] == reader_uid:
            continue
        need(live and expected_claim in uses and dbpod is None, 'no_foreign_claim_users')
        need(not p['metadata'].get('deletionTimestamp') and p['status']['phase'] == 'Running', 'db_running')
        ps = p['spec']; pc = ps['containers'][0]
        need(len(ps['containers']) == 1 and not ps.get('initContainers') and not ps.get('ephemeralContainers'), 'db_pod_surface')
        need(pc['name'] == c['name'] and pc['image'] == IMAGE and not pc.get('command') and not pc.get('args'), 'db_pod_launch')
        for field in ('env', 'envFrom', 'resources', 'securityContext'):
            need(pc.get(field) == c.get(field), 'db_pod_contract')
        need(ps.get('securityContext', {}) == t.get('securityContext', {}), 'db_pod_security')
        extras = [m for m in pc.get('volumeMounts', []) if m not in mounts]
        need(all(m in pc.get('volumeMounts', []) for m in mounts), 'db_pod_mount')
        need(all(m.get('mountPath') == '/var/run/secrets/kubernetes.io/serviceaccount' and m.get('readOnly') and not m.get('subPath') for m in extras), 'only_serviceaccount_extra')
        others = [v for v in ps.get('volumes', []) if v not in t['volumes']]
        need(all(v.get('projected') and v['name'] in {m['name'] for m in extras} for v in others), 'no_extra_data_mount')
        sts = p['status']['containerStatuses']; need(len(sts) == 1 and sts[0]['ready'] and sts[0]['imageID'] == IMAGE, 'db_ready_digest')
        owner = next(o for o in p['metadata']['ownerReferences'] if o.get('controller'))
        rs = q.get('replicaset', owner['name'])
        need(rs['metadata']['uid'] == owner['uid'] and any(o.get('controller') and o['uid'] == q.IDS['deployment'] for o in rs['metadata']['ownerReferences']), 'db_owner_chain')
        need(ps['nodeName'] == 'workernode2', 'reviewed_rwo_attachment_node')
        dbpod = p
    need((dbpod is not None) == live, 'exact_live_db_count')
    redundancy = None
    if x['phase'] != 'baseline':
        volume = 'pvc-' + CLAIMS[OLD][0]
        v = q.get('volumes.longhorn.io', volume, 'longhorn-system')
        need(v['status']['state'] == 'attached' and v['status']['robustness'] == 'healthy' and v['status']['currentNodeID'] == 'workernode2', 'original_attached_healthy')
        replicas = [r for r in q.get('replicas.longhorn.io', ns='longhorn-system')['items'] if r['spec']['volumeName'] == volume]
        need({r['metadata']['name'] for r in replicas} == set(REPLICAS), 'only_two_original_replicas')
        for r in replicas:
            uid, node = REPLICAS[r['metadata']['name']]
            need(r['metadata']['uid'] == uid and r['spec']['nodeID'] == node and not r['metadata'].get('deletionTimestamp'), 'original_replica_identity')
            need(r['spec'].get('active') is True and not r['spec'].get('failedAt') and not r['spec'].get('evictionRequested') and not r['spec'].get('salvageRequested'), 'nonfailed_original_replicas')
            need(r['status'].get('currentState') == 'running', 'replicas_running')
        engines = [e for e in q.get('engines.longhorn.io', ns='longhorn-system')['items'] if e['spec']['volumeName'] == volume and e['spec'].get('active')]
        need(len(engines) == 1 and engines[0]['status'].get('currentState') == 'running', 'one_running_engine')
        modes = engines[0]['status'].get('replicaModeMap', {})
        need(modes == {n: 'RW' for n in REPLICAS}, 'both_original_replicas_rw')
        redundancy = {'engine_uid': engines[0]['metadata']['uid'], 'replica_uids': {n: row[0] for n, row in REPLICAS.items()}, 'modes': modes}
    result = {'identity': identity, 'redundancy': redundancy}
    if dbpod:
        slices = json.loads(q.call(['-n', 'ruckus', 'get', 'endpointslices', '-l', 'kubernetes.io/service-name=ruckus-db', '-o', 'json']))['items']
        endpoints = [e for s in slices for e in s.get('endpoints', []) if e.get('conditions', {}).get('ready')]
        need(endpoints and all(e.get('targetRef', {}).get('uid') == dbpod['metadata']['uid'] for e in endpoints), 'only_db_service_endpoint')
        result['pod'] = {'uid': dbpod['metadata']['uid'], 'created_at': dbpod['metadata']['creationTimestamp']}
        if x.get('sql'):
            sql = q.SQL('ruckus', dbpod['metadata']['name'], 'ruckus-db', values, service['spec']['clusterIP'])
            state = q.snapshot(sql, key, administrative=False)
            need(state['server_version'] == '5.7.44' and state == q.snapshot(sql, key, administrative=False), 'stable_normal_auth_snapshot')
            result['state'] = state
    del values
    return result


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    need(hashlib.sha256(open(OBSERVER, 'rb').read()).hexdigest() == OBSERVER_SHA, 'observer_pin')
    spec = importlib.util.spec_from_file_location('q', OBSERVER); q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)
    x = json.load(sys.stdin); key = bytes.fromhex(x.pop('key_hex')); need(len(key) == 32, 'stdin_key')
    first = guard(q, x, key)
    if x.get('sql'):
        second = guard(q, dict(x, sql=False), key)
        need({k: v for k, v in first.items() if k != 'state'} == second, 'snapshot_identity_stability')
    print(json.dumps(first, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'guard_stage': str(error) if isinstance(error, RuntimeError) else 'guard_shape', 'error_type': type(error).__name__}))
        raise SystemExit(1)
