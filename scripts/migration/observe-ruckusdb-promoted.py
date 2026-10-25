#!/usr/bin/env python3
"""Master-only normal-auth acceptance of the reviewed fresh Ruckus DB claim.

No SQL executes on import. Runtime actions reuse the exact reviewed observer's
SQL/snapshot implementation, never its main or administrative-copy actions.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import sys
import traceback

MASTER = Path('/home/james/.local/share/branconet-migration/acceptance-ruckus-20261025')
OBSERVER = MASTER / 'copy-observer-3284b56f3d7e.py'
OBSERVER_SHA = '3284b56f3d7e7f0a570d84823a3a5b3a1c8067249156450bc061af2dadda3751'
BASELINE = MASTER / 'live-before-01.json'
BASELINE_SHA = '8a24bba03818d874f32ba18b705a2678e314c78d4d4f62f7839d2fa4d7f103a8'
ARCHIVE_SHA = '0181fa8442048910a51972a2294274aefb48dca41d98db4c8e38251e805ca30c'
CLAIM = 'ruckus-db-data-0-security-20261025'
ORIGINAL_CLAIM = 'ruckus-db-data-0'
NEW_IMAGE = 'docker.io/library/ruckusdb-security-20261023@sha256:2f0c391e6c04501862598bbc5446165f8ebba08025168451f6f6447352316349'


def need(ok, code):
    if not ok:
        raise RuntimeError(code)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def spec_sha(obj):
    # Same serialization as the fresh-claim restore's original/fresh spec proof.
    return hashlib.sha256(json.dumps(obj['spec'], sort_keys=True).encode()).hexdigest()


def instant(value):
    return datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))


def load_receipt(path, expected):
    need(path.is_absolute() and path.resolve().parent == MASTER and not path.is_symlink(), 'private_receipt_location')
    need(re.fullmatch('[a-f0-9]{64}', expected) and sha(path) == expected, 'receipt_sha256')
    return json.loads(path.read_bytes())


def original_retained(q, baseline, restore):
    pvc = q.get('pvc', ORIGINAL_CLAIM)
    need(pvc['metadata']['uid'] == q.IDS['pvc'] == baseline['identity']['pvc_uid'], 'original_pvc_uid')
    need(not pvc['metadata'].get('deletionTimestamp') and pvc['status']['phase'] == 'Bound', 'original_pvc_retained_bound')
    need(pvc['spec'].get('storageClassName') == 'longhorn', 'original_storage_class')
    pv = q.get('pv', pvc['spec']['volumeName'], None)
    need(pv['metadata']['uid'] == baseline['identity']['pv_uid'] == restore['before']['source_pv_uid'], 'original_pv_uid')
    need(not pv['metadata'].get('deletionTimestamp') and pv['spec']['claimRef']['uid'] == q.IDS['pvc'], 'original_pv_retained')
    need(pv['spec']['csi']['driver'] == 'driver.longhorn.io', 'original_longhorn')
    need(spec_sha(pvc) == restore['before']['source_pvc_spec_sha256'] and spec_sha(pv) == restore['before']['source_pv_spec_sha256'], 'original_storage_specs_unchanged')
    return pvc, pv


def guard(q, args, baseline, archive, restore):
    original, original_pv = original_retained(q, baseline, restore)
    pvc = q.get('pvc', CLAIM)
    need(pvc['metadata']['uid'] == args.claim_uid == restore['new_claim_uid'] != q.IDS['pvc'], 'new_claim_uid')
    need(not pvc['metadata'].get('deletionTimestamp') and pvc['status']['phase'] == 'Bound' and pvc['spec'].get('storageClassName') == 'longhorn', 'new_claim_bound')
    need(not pvc['spec'].get('dataSource') and not pvc['spec'].get('dataSourceRef'), 'fresh_not_clone_reference')
    need(instant(pvc['metadata']['creationTimestamp']) > instant(archive['started_at']), 'fresh_claim_after_archive')
    need(spec_sha(pvc) == restore['before']['fresh_pvc_spec_sha256'], 'restored_claim_spec_unchanged')
    pv = q.get('pv', pvc['spec']['volumeName'], None)
    need(pv['metadata']['uid'] == args.pv_uid == restore['before']['fresh_pv_uid'] != original_pv['metadata']['uid'], 'new_pv_uid')
    need(not pv['metadata'].get('deletionTimestamp') and pv['spec']['claimRef']['uid'] == args.claim_uid, 'new_pv_binding')
    need(pv['spec']['csi']['driver'] == 'driver.longhorn.io' and pv['spec']['csi']['volumeHandle'] != original_pv['spec']['csi']['volumeHandle'], 'distinct_new_longhorn_volume')

    d, bot = q.get('deployment', 'ruckus-db'), q.get('deployment', 'ruckus-bot')
    hr, bhr = q.get('helmrelease', 'ruckus-db', 'flux-system'), q.get('helmrelease', 'ruckus-bot', 'flux-system')
    for obj, key in [(d, 'deployment'), (bot, 'bot'), (hr, 'release'), (bhr, 'bot_release')]:
        need(obj['metadata']['uid'] == q.IDS[key] and not obj['metadata'].get('deletionTimestamp'), 'original_workload_' + key)
        need(obj['status'].get('observedGeneration', 0) >= obj['metadata']['generation'], 'observed_generation_' + key)
    for dep, release, wanted in [(d, hr, 1), (bot, bhr, 0)]:
        need(dep['spec'].get('replicas', 1) == wanted and all(dep['status'].get(k, 0) == wanted for k in ('replicas', 'readyReplicas', 'updatedReplicas', 'availableReplicas')), 'db_one_bot_zero')
        need(release['spec'].get('values', {}).get('replicaCount') == wanted and not release['spec'].get('suspend', False), 'flux_db_one_bot_zero')
        need(any(c['type'] == 'Ready' and c['status'] == 'True' for c in release['status'].get('conditions', [])), 'flux_release_ready')
    template = d['spec']['template']['spec']
    need(len(template['containers']) == 1 and not template.get('initContainers') and not template.get('ephemeralContainers'), 'normal_db_container_only')
    c = template['containers'][0]
    need(c['name'] == 'ruckus-db' and c['image'] == NEW_IMAGE and not c.get('command') and not c.get('args'), 'normal_candidate_launch')
    need(c.get('envFrom') == [{'secretRef': {'name': 'ruckus-db-runtime'}}] and c.get('resources', {}) == baseline['identity']['resources'], 'native_env_and_original_budget')
    volumes = template.get('volumes', [])
    need(len(volumes) == 1 and volumes[0].get('persistentVolumeClaim') == {'claimName': CLAIM}, 'only_reviewed_claim')
    mounts = c.get('volumeMounts', [])
    need(mounts == [{'name': volumes[0]['name'], 'mountPath': '/var/lib/mysql', 'subPath': 'data-0'}], 'exact_reviewed_subpath')
    pods = q.get('pods')['items']; live = []
    for pod in pods:
        running = any('running' in s.get('state', {}) for k in ('containerStatuses', 'initContainerStatuses', 'ephemeralContainerStatuses') for s in pod['status'].get(k, []))
        terminal = pod['status'].get('phase') in ('Failed', 'Succeeded') and not running
        if all(pod['metadata'].get('labels', {}).get(k) == v for k, v in bot['spec']['selector']['matchLabels'].items()):
            need(terminal, 'bot_pod_must_remain_quiesced')
        uses = [v.get('persistentVolumeClaim', {}).get('claimName') for v in pod['spec'].get('volumes', [])]
        if ORIGINAL_CLAIM in uses:
            need(terminal, 'original_claim_no_active_mounts')
        if CLAIM in uses and not terminal:
            live.append(pod)
    need(len(live) == 1, 'one_promoted_claim_user')
    pod = live[0]; ps = pod['spec']
    need(not pod['metadata'].get('deletionTimestamp') and pod['status']['phase'] == 'Running', 'promoted_pod_running')
    need(len(ps['containers']) == 1 and not ps.get('initContainers') and not ps.get('ephemeralContainers'), 'promoted_surface')
    pc = ps['containers'][0]
    need(pc['name'] == c['name'] and pc['image'] == NEW_IMAGE and not pc.get('command') and not pc.get('args'), 'promoted_normal_launch')
    need(pc.get('envFrom') == c.get('envFrom') and pc.get('env') == c.get('env') and pc.get('resources', {}) == c.get('resources', {}), 'pod_env_resources_match_template')
    need(all(m in pc.get('volumeMounts', []) for m in mounts), 'promoted_data_mount')
    extras = [m for m in pc.get('volumeMounts', []) if m not in mounts]
    need(all(m['mountPath'] == '/var/run/secrets/kubernetes.io/serviceaccount' and m.get('readOnly') is True and not m.get('subPath') for m in extras), 'only_normal_serviceaccount_extra_mount')
    other_volumes = [v for v in ps.get('volumes', []) if v not in volumes]
    need(all(v.get('projected') and v['name'] in {m['name'] for m in extras} for v in other_volumes), 'no_extra_data_volumes')
    statuses = pod['status']['containerStatuses']
    need(len(statuses) == 1 and statuses[0]['ready'] and statuses[0]['imageID'] == NEW_IMAGE, 'exact_ready_candidate')
    owner = next(o for o in pod['metadata']['ownerReferences'] if o.get('controller'))
    rs = q.get('replicaset', owner['name'])
    need(rs['metadata']['uid'] == owner['uid'] and any(o.get('controller') and o['uid'] == q.IDS['deployment'] for o in rs['metadata']['ownerReferences']), 'original_deployment_owner_chain')
    service = q.get('service', 'ruckus-db')
    need(service['spec'].get('clusterIP') not in (None, '', 'None'), 'existing_service_ip')
    selector = service['spec'].get('selector', {})
    need(selector and all(pod['metadata'].get('labels', {}).get(k) == v for k, v in selector.items()), 'service_selects_promoted_pod')
    slices = json.loads(q.call(['-n', 'ruckus', 'get', 'endpointslices', '-l', 'kubernetes.io/service-name=ruckus-db', '-o', 'json']))['items']
    endpoints = [e for sl in slices for e in sl.get('endpoints', []) if e.get('conditions', {}).get('ready')]
    need(endpoints and all(e.get('targetRef', {}).get('uid') == pod['metadata']['uid'] for e in endpoints), 'service_only_promoted_endpoint')
    identity = {'deployment_uid': d['metadata']['uid'], 'release_uid': hr['metadata']['uid'],
                'writer_uid': bot['metadata']['uid'], 'writer_release_uid': bhr['metadata']['uid'],
                'original_pvc_uid': original['metadata']['uid'], 'original_pv_uid': original_pv['metadata']['uid'],
                'original_pvc_spec_sha256': spec_sha(original), 'original_pv_spec_sha256': spec_sha(original_pv),
                'pvc_name': CLAIM, 'pvc_uid': args.claim_uid, 'pv_uid': args.pv_uid,
                'pvc_spec_sha256': spec_sha(pvc), 'pv_spec_sha256': spec_sha(pv),
                'image': NEW_IMAGE, 'image_id': statuses[0]['imageID'], 'resources': c.get('resources', {}),
                'mount_metadata': [{'mountPath': '/var/lib/mysql', 'subPath': 'data-0'}],
                'pod_uid': pod['metadata']['uid'], 'pod_created_at': pod['metadata']['creationTimestamp'],
                'service_uid': service['metadata']['uid'], 'service_ip': service['spec']['clusterIP']}
    return identity, (pod['metadata']['name'], pc['name'], service['spec']['clusterIP'])


def compare_state(q, original, observed):
    need(original['administrative'] is False and observed['administrative'] is False, 'app_auth_scope_only')
    fields = ('schemas', 'grant_tables', 'settings_hmac', 'authenticated_account_hmac', 'administrative')
    equal = {name: original[name] == observed[name] for name in fields}
    need(all(equal.values()), 'original_rows_schema_account_or_settings_changed')
    rows = sum(t.get('rows', 0) for s in observed['schemas'].values() for t in s['tables'].values())
    need(rows == 3962 and len(observed['schemas']) == 1 and sum(len(s['tables']) for s in observed['schemas'].values()) == 2, 'original_inventory_3962_rows_two_tables')
    return equal | {'rows': rows, 'tables': 2, 'schemas_count': 1}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['observe-promoted', 'observe-restart'])
    ap.add_argument('--claim-uid', required=True); ap.add_argument('--pv-uid', required=True)
    ap.add_argument('--archive-receipt', type=Path, required=True)
    ap.add_argument('--restore-receipt', type=Path, required=True); ap.add_argument('--restore-receipt-sha256', required=True)
    ap.add_argument('--previous', type=Path); ap.add_argument('--previous-sha256')
    ap.add_argument('--receipt', type=Path, required=True)
    a = ap.parse_args(); resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); os.umask(0o077)
    need(os.name == 'posix' and a.receipt.is_absolute() and a.receipt.resolve().parent == MASTER and not a.receipt.exists(), 'new_private_master_receipt')
    need(re.fullmatch('[a-z0-9-]+[.]json', a.receipt.name), 'simple_receipt_name')
    need(sha(OBSERVER) == OBSERVER_SHA and sha(BASELINE) == BASELINE_SHA, 'observer_and_original_baseline_pins')
    spec = importlib.util.spec_from_file_location('exact_original_observer', OBSERVER)
    q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)
    key = bytes.fromhex(sys.stdin.readline().strip()); need(len(key) == 32, 'stdin_key_only')
    result = {'status': 'failed', 'action': a.action, 'helper_sha256': sha(Path(__file__)),
              'sql_snapshot_helper_sha256': OBSERVER_SHA, 'key_id': q.mac(key, 'key-id', b'ruckusdb'),
              'baseline_sha256': BASELINE_SHA, 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        baseline = json.loads(BASELINE.read_bytes()); archive = load_receipt(a.archive_receipt, ARCHIVE_SHA)
        restore = load_receipt(a.restore_receipt, a.restore_receipt_sha256)
        need(baseline['status'] == 'passed' and baseline['key_id'] == result['key_id'] and baseline['state']['server_version'] == '5.7.41', 'original_keyed_baseline')
        need(archive['status'] == 'completed' and archive['cold_archive_verified'] and archive['complete_inventory_unchanged'], 'qualified_archive_proof')
        need(restore['status'] == 'completed' and restore['full_file_metadata_equal'] and restore['source_claim_never_mounted'], 'full_restore_proof')
        need(restore['archive_receipt_sha256'] == ARCHIVE_SHA and restore['restored_manifest_sha256'] == archive['manifest_sha256'], 'exact_archive_restore_chain')
        need(restore['new_claim'] == CLAIM and restore['new_claim_uid'] == a.claim_uid and restore['before']['fresh_pv_uid'] == a.pv_uid, 'reviewed_fresh_target_identity')
        before, target = guard(q, a, baseline, archive, restore)
        need(before['pod_uid'] != baseline['identity']['pod_uid'], 'promoted_pod_differs_from_original')
        values, secret = q.native(key)
        need(secret['uid'] == baseline['native_secret']['uid'] and secret['data_hmac'] == baseline['native_secret']['data_hmac'], 'original_native_secret_unchanged')
        previous = None
        if a.action == 'observe-restart':
            need(a.previous and a.previous_sha256, 'declared_restart_previous_required')
            previous = load_receipt(a.previous, a.previous_sha256)
            need(previous['status'] == 'passed' and previous['key_id'] == result['key_id'] and previous['helper_sha256'] == result['helper_sha256'], 'matching_prior_promoted_observation')
            need(previous['action'] in ('observe-promoted', 'observe-restart') and previous['baseline_sha256'] == BASELINE_SHA, 'prior_baseline_lineage')
            need(previous['archive_receipt_sha256'] == ARCHIVE_SHA and previous['restore_receipt_sha256'] == a.restore_receipt_sha256, 'prior_restore_lineage')
            need(before['pod_uid'] != previous['identity']['pod_uid'] and instant(before['pod_created_at']) > instant(previous['finished_at']), 'actual_new_pod_after_declared_restart')
            keep = lambda identity: {k: v for k, v in identity.items() if k not in ('pod_uid', 'pod_created_at')}
            need(keep(before) == keep(previous['identity']), 'restart_preserves_all_nonpod_identities')
        else:
            need(not a.previous and not a.previous_sha256, 'previous_only_for_declared_restart')
        # The original reviewed class is called only with native application
        # credentials and the guarded Service IP. No administrative=True path.
        sql = q.SQL('ruckus', target[0], target[1], values, target[2]); del values
        state = q.snapshot(sql, key, administrative=False)
        need(state['server_version'] == '5.7.44', 'candidate_server_version')
        need(state == q.snapshot(sql, key, administrative=False), 'stable_repeat_snapshot')
        comparison = compare_state(q, baseline['state'], state)
        if previous:
            need(state == previous['state'], 'restart_state_exactly_preserved')
        after, _ = guard(q, a, baseline, archive, restore); unused, secret_after = q.native(key); del unused
        need(before == after and secret == secret_after, 'identities_stable_during_snapshot')
        need(sha(BASELINE) == BASELINE_SHA and sha(OBSERVER) == OBSERVER_SHA and sha(a.archive_receipt) == ARCHIVE_SHA and sha(a.restore_receipt) == a.restore_receipt_sha256, 'proof_inputs_stable')
        result.update(status='passed', identity=before, native_secret=secret, state=state, comparison=comparison,
                      archive_receipt_sha256=ARCHIVE_SHA, restore_receipt_sha256=a.restore_receipt_sha256,
                      previous_sha256=a.previous_sha256, declared_restart_verified=previous is not None,
                      finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    except Exception as error:
        result.update(error=str(error) if isinstance(error, RuntimeError) else type(error).__name__,
                      error_source_lines=[f.lineno for f in traceback.extract_tb(error.__traceback__) if f.filename == __file__])
    with a.receipt.open('x') as stream:
        json.dump(result, stream, sort_keys=True, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({'status': result['status'], 'receipt': str(a.receipt)}))
    if result['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
