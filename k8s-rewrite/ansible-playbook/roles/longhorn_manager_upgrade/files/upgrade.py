"""Apply the reviewed official candidate through its existing kubectl SSA owner.

Never force conflicts, adopt Helm ownership, change replica/storage controls,
delete/rebind data, or attempt an unsupported downgrade after schema migration.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
O = F / 'platform-upstream-review-20261027'
M = O / 'longhorn-manager-upgrade-20261028'
P = O / 'longhorn-prepared-v1.13.0'
Q = O / 'final-control-plane-checkpoint-20261028'
U = O / 'longhorn-production-prestage-20261028'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, obj):
    with (M / name).open('x') as out:
        json.dump(obj, out, indent=2)


def call(args, data=None, timeout=240):
    child = subprocess.run(SSH + ['kubectl', *args], input=None if data is None else json.dumps(data).encode(),
        capture_output=True, timeout=timeout)
    need(len(child.stdout) <= 16 * 1024**2 and len(child.stderr) <= 1024**2, 'bounded_native_response')
    return child


def get(args):
    p = call(['get', *args, '-o', 'json'])
    need(p.returncode == 0, 'native_nonsecret_read_failed')
    return json.loads(p.stdout)


def capture(source):
    p = subprocess.run(SSH + ['python3 -B - --remote'], input=source.read_bytes(), capture_output=True, timeout=180)
    need(p.returncode == 0 and len(p.stdout) <= 4 * 1024**2, 'fresh_original_cluster_capture')
    return json.loads(p.stdout)


def recovery():
    cp = json.loads((Q / 'operator.json').read_text())
    need(cp['status'] == 'completed' and cp['sourcesUnchanged'] and cp['exitCode'] == 0, 'authenticated_final_checkpoint')
    b = Path(cp['backupPath'])
    need(sha(b / 'receipt.json') == cp['receiptSHA256'] and sha(b / 'control-plane.tar.age') == cp['archiveSHA256'], 'unaltered_checkpoint')
    prefix = 'cp-' + cp['runID'] + '-'
    e = O / 'etcd-restore-qualification'
    restore = json.loads((e / (prefix + 'restore-result.json')).read_text())
    nas = json.loads((e / (prefix + 'nas-proof.json')).read_text())
    need(restore['status'] == 'completed' and restore['completeAgeAuthentication']
         and restore['offlineSnapshotRestoreExecuted'] and restore['keyValueHistoryHashUnchanged']
         and restore['verifiedConfigurationFiles'] == 46 and restore['sourceArchiveSHA256'] == cp['archiveSHA256']
         and nas['fullNASReadback'] and nas['sha256'] == cp['archiveSHA256'], 'independent_NAS_and_actual_offline_restore')
    cfg = O / 'longhorn-system-backup-20261028'
    bundle = json.loads((cfg / 'nas-contents-qualification.json').read_text())
    need(bundle['fullNASReadbacks'] == 2 and bundle['zipCRCAllMembersPassed']
         and bundle['independentBundleQualification']['completeBindingChains'] == 44, 'qualified_native_configuration_bundle')
    sb = get(['systembackups.longhorn.io', '-n', 'longhorn-system', bundle['name']])
    need(sb['metadata']['uid'] == bundle['nativeSystemBackupUID'] and sb['status']['state'] == 'Ready'
         and sb['spec']['volumeBackupPolicy'] == 'disabled', 'same_completed_configuration_only_backup')
    return {'controlPlaneRunID': cp['runID'], 'archiveSHA256': cp['archiveSHA256'],
        'controlPlaneRestoreReceiptSHA256': sha(e / (prefix + 'restore-result.json')),
        'systemBackup': bundle['name'], 'systemBackupUID': bundle['nativeSystemBackupUID'],
        'systemBundleQualificationSHA256': sha(cfg / 'nas-contents-qualification.json')}


def headroom(live):
    result = {}
    for n in live['longhornNodes']:
        name = n['name']
        fs = live['filesystem'][name]
        image = fs['runtimeFS']['imageFs']
        node = fs['nodeFS']
        need(min(node['availableBytes'], image['availableBytes']) >=
             max(node['capacityBytes'], image['capacityBytes']) * 15 // 100 + 512 * 1024**2 + 64 * 1024**2,
             'unchanged_kubelet_floor_and_complete_margin')
        for d in n['disks'].values():
            floor = d['storageMaximum'] // 4 + 1
            need(d['storageAvailable'] >= floor + 512 * 1024**2 + 64 * 1024**2,
                 'unchanged_longhorn_floor_operating_margin_and_host_copy_budget')
            result[name] = {'availableBytes': d['storageAvailable'], 'floorBytes': floor,
                'retainedMarginBytes': 512 * 1024**2, 'hostPayloadBudgetBytes': 64 * 1024**2}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'apply', 'observe'])
    a = parser.parse_args()
    repo = Path(__file__).resolve().parents[5]
    s = repo / 'k8s-rewrite/ansible-playbook'
    need(os.geteuid() == 1000 and F.is_mount(), 'existing_unprivileged_controller_and_F_storage')
    for path in (F, Path('/mnt/c')):
        st = os.statvfs(path)
        need(st.f_bavail * st.f_frsize >= 15 * 1024**3 + 64 * 1024**2, 'complete_metadata_peak_and_original_floors')
    os.umask(0o077)
    prep = runpy.run_path(str(s / 'roles/longhorn_upgrade_prepare/files/prepare.py'), run_name='reviewed_prepare_library')
    stage = runpy.run_path(str(repo / 'scripts/migration/run-longhorn-upgrade-preload.py'), run_name='reviewed_staging_fences')
    check = s / 'roles/longhorn_upgrade_preflight/files/check.py'
    candidate = json.loads((P / 'candidate.json').read_text())
    prepared = json.loads((P / 'receipt.json').read_text())
    need(prepared['status'] == 'completed_server_dry_run'
         and sha(P / 'candidate.json') == prepared['candidateSHA256']
         == '4e9e85f106dc5cb11a2283956a2278a482b372e0061daccd6af0f0c9d64a8ac5', 'unchanged_reviewed_official_candidate')
    need(len(candidate['items']) == 61 and all(x['kind'] != 'Secret' and x['kind'] != 'Namespace' for x in candidate['items']), 'original_public_apply_scope')
    baseline = {prep['key'](v): v for v in json.loads((O / 'longhorn-owner-review-r2/live-nonsecret-objects.json').read_text())['items']}
    query = {'apiVersion': 'v1', 'kind': 'List', 'items': [{'apiVersion': v['apiVersion'], 'kind': v['kind'],
        'metadata': {k: v['metadata'][k] for k in ('name', 'namespace') if k in v['metadata']}} for v in baseline.values()]}
    if a.mode == 'prepare':
        need(not M.exists(), 'prior_operation_must_survive')
        M.mkdir(mode=0o700)
        sources = {str(p): sha(p) for p in [Path(__file__), check, s / 'roles/longhorn_upgrade_prepare/files/prepare.py',
            repo / 'scripts/migration/run-longhorn-upgrade-preload.py', P / 'candidate.json']}
        save('ownership.json', {'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
            'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b', 'sources': sources,
            'generatedPaths': [str(M)], 'completePeakBytes': 64 * 1024**2,
            'regeneration': 'Original candidate, source pins, recovery checkpoints and original kubectl SSA owner; never replay submitted apply blindly',
            'endCondition': 'Manager rollout observed, original identities/redundancy preserved; only minimal metadata retained',
            'recovery': 'Forward repair or qualified original recovery; no unsupported v1.13 to v1.12 manifest downgrade',
            'protected': 'All original data, native Secret keys, claims, replicas, NAS, runtime rollback images and other projects'})
        staged = json.loads((U / 'ansible-operator.json').read_text())
        need(staged['status'] == 'completed' and staged['sourcesUnchanged'] and staged['exitCode'] == 0, 'all_three_images_staged')
        current = prep['get'](query)
        need(set(current) == set(baseline) and all(prep['configuration'](current[k]) == prep['configuration'](v)
             for k, v in baseline.items()), 'existing_owner_UIDs_and_reviewed_configuration_unchanged')
        live = capture(check)
        stage['fence'](live)
        need(stage['stable'](live) == stage['stable'](json.loads((U / 'postflight.json').read_text())), 'all_original_data_bindings_unchanged')
        save('before.json', live)
        rec = recovery()
        space = headroom(live)
        dry = call(['apply', '--server-side', '--dry-run=server', '--field-manager=kubectl', '--validate=strict', '-f', '-', '-o', 'json'], candidate)
        need(dry.returncode == 0 and len(json.loads(dry.stdout)['items']) == 61, 'fresh_strict_server_dry_run_without_conflict_force')
        save('server-dry-run.json', json.loads(dry.stdout))
        save('prepared.json', {'status': 'prepared', 'sources': sources, 'recovery': rec, 'headroom': space,
            'existingObjects': len(current), 'candidateSHA256': sha(P / 'candidate.json'), 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat()})
        print(json.dumps({'status': 'prepared', 'existingObjects': len(current), 'resources': 61}))
        return
    plan = json.loads((M / 'prepared.json').read_text())
    need(all(sha(Path(p)) == h for p, h in plan['sources'].items()), 'prepared_source_and_candidate_unchanged')
    if a.mode == 'apply':
        need(not (M / 'apply-intent.json').exists(), 'no_blind_resubmission')
        need(recovery() == plan['recovery'], 'same_qualified_recovery_checkpoints')
        current = prep['get'](query)
        need(set(current) == set(baseline) and all(prep['configuration'](current[k]) == prep['configuration'](v)
             for k, v in baseline.items()), 'owner_and_configuration_unchanged_before_apply')
        live = capture(check)
        stage['fence'](live)
        need(stage['stable'](live) == stage['stable'](json.loads((M / 'before.json').read_text())), 'unchanged_data_before_apply')
        space = headroom(live)
        save('apply-intent.json', {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'candidateSHA256': sha(P / 'candidate.json'), 'fieldManager': 'kubectl', 'forceConflicts': False,
            'recovery': plan['recovery'], 'headroom': space, 'automaticEngineUpgradeLimit': '0'})
        result = {'status': 'started', 'candidateSHA256': sha(P / 'candidate.json')}
        try:
            p = call(['apply', '--server-side', '--field-manager=kubectl', '--validate=strict', '-f', '-', '-o', 'json'], candidate)
            result.update(exitCode=p.returncode, diagnosticsSHA256=hashlib.sha256(p.stderr).hexdigest())
            need(p.returncode == 0, 'partial_apply_possible_preserve_receipts_and_inspect_no_downgrade')
            response = json.loads(p.stdout)
            need(len(response['items']) == 61, 'every_resource_apply_returned')
            save('apply-response.json', response)
            result.update(status='submitted', resources=61)
        except Exception as error:
            result.update(status='failed_inspect_actual_state_no_replay', errorType=type(error).__name__)
            raise
        finally:
            save('apply-result.json', result)
        print(json.dumps(result))
        return
    need(json.loads((M / 'apply-result.json').read_text())['status'] == 'submitted', 'submitted_existing_operation_required')
    outcomes = []
    for doc in candidate['items']:
        if doc['kind'] not in ('Deployment', 'DaemonSet'):
            continue
        name = doc['kind'].lower() + '/' + doc['metadata']['name']
        p = call(['-n', 'longhorn-system', 'rollout', 'status', name, '--timeout=300s'], timeout=330)
        outcomes.append({'resource': name, 'exitCode': p.returncode, 'diagnosticsSHA256': hashlib.sha256(p.stdout + p.stderr).hexdigest()})
        if p.returncode:
            save('rollout-failure.json', {'outcomes': outcomes, 'resource': name})
            raise ValueError('rollout_failed_inspect_actual_state_no_replay')
    after = capture(check)
    save('after.json', after)
    need(after['settings']['current-longhorn-version'] == 'v1.13.0'
         and after['settings']['concurrent-automatic-engine-upgrade-per-node-limit'] == '0'
         and after['settings']['storage-minimal-available-percentage'] == '25', 'new_manager_and_unchanged_storage_manual_upgrade_controls')
    before = json.loads((M / 'before.json').read_text())
    stable_before, stable_after = stage['stable'](before), stage['stable'](after)
    for k in ('claims', 'volumes', 'replicas', 'engines', 'NASBindings'):
        need(stable_before[k] == stable_after[k], 'original_' + k + '_preserved_during_manager_rollout')
    for v in after['volumes']:
        if v['state'] == 'attached':
            need(v['robustness'] == 'healthy' and len(v['engines']) == 1
                 and list(v['engines'][0]['replicaModes'].values()).count('RW') == 2
                 and len({r['node'] for r in v['replicas'] if r['state'] == 'running' and not r['failedAt']}) == 2,
                 'every_attached_volume_retains_two_actual_RW_replicas')
    pods = get(['pods', '-n', 'longhorn-system'])['items']
    records = [{k: p['metadata'].get(k) for k in ('name', 'uid')} | {'node': p['spec'].get('nodeName'),
        'phase': p['status'].get('phase'), 'containers': [{k: c.get(k) for k in ('name', 'ready', 'restartCount', 'image', 'imageID')}
            for c in p['status'].get('containerStatuses', [])]} for p in pods]
    save('pod-image-identities.json', records)
    save('manager-acceptance.json', {'status': 'manager_rollout_completed', 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'outcomes': outcomes, 'originalDataIdentitiesPreserved': True, 'twoActualRWOnEveryAttachedVolume': True,
        'version': 'v1.13.0', 'automaticEngineUpgradeLimit': 0, 'engineUpgradeExecuted': False,
        'fullGoalComplete': False, 'beforeSHA256': sha(M / 'before.json'), 'afterSHA256': sha(M / 'after.json')})
    print(json.dumps({'status': 'manager_rollout_completed', 'version': 'v1.13.0', 'engineUpgradeExecuted': False}))


if __name__ == '__main__':
    main()
