"""One detached V1 claim: UID-guarded ticket, cold snapshot/backup, normal detach."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
O = F / 'platform-upstream-review-20261027'
R = O / 'detached-volume-backups-20261027'
LH = 'longhorn-system'
IMAGE = 'docker.io/longhornio/longhorn-engine:v1.12.1'
VOLUMES = {
    'storage-proof': 'pvc-9317472a-a68f-4a2b-ad93-5d02e91492b0',
    'storage-restored': 'pvc-8e780ab5-6f6d-4c93-8b2b-4410da2e841f',
    'nas-bortus-restore': 'pvc-ba85233b-81d5-4061-9f7b-feff295071e0',
    'bortus-restore': 'pvc-42bafa5c-bf7a-4751-8fc3-ba3104a76784',
    'pihole-old-0': 'pvc-224e40cf-cfd1-488a-bab6-545568c8e4f7',
    'pihole-old-1': 'pvc-bd9d5442-8665-4328-9a62-53d03d704ca7',
    'gluetun-old': 'pvc-2d2591cd-8809-4957-b56a-2f4d405bd9e2',
    'qbittorrent-old': 'pvc-6aa3aaa5-f609-4f74-88f0-b5c15e846703',
    'ruckus-old': 'pvc-0bf707c8-628e-4284-9aa0-35b711c8749b',
    'wordpress-unused': 'pvc-49df631b-614f-4180-b6e5-f719db4bfe2c',
}
READS = {'volumes.longhorn.io', 'volumeattachments.longhorn.io', 'replicas.longhorn.io',
         'engines.longhorn.io', 'engineimages.longhorn.io', 'instancemanagers.longhorn.io',
         'settings.longhorn.io', 'backuptargets.longhorn.io', 'nodes.longhorn.io',
         'backups.longhorn.io', 'snapshots.longhorn.io', 'pods', 'pvc', 'pv', 'nodes'}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def timestamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def remote():
    request = json.load(sys.stdin)
    verb = request['verb']
    if verb == 'get':
        need(request['kind'] in READS, 'metadata_resource_allowlist')
        cmd = ['kubectl', 'get', request['kind']]
        if request.get('name'):
            cmd.append(request['name'])
        if request.get('allNamespaces'):
            cmd.append('-A')
        elif request.get('namespace'):
            cmd.extend(['-n', request['namespace']])
        cmd.extend(['-o', 'json'])
        data = None
    elif verb == 'patch':
        need(request['volume'] in VOLUMES.values() and request['kind'] in
             ('volumeattachments.longhorn.io', 'volumes.longhorn.io'), 'fixed_checkpoint_patch_scope')
        for op in request['patch']:
            path = op['path']
            need(op['op'] == 'test' or
                 (request['kind'] == 'volumeattachments.longhorn.io' and
                  re.fullmatch('/spec/attachmentTickets/migration-preserve-[0-9a-f]{12}', path) and op['op'] in ('add', 'remove')) or
                 (request['kind'] == 'volumes.longhorn.io' and op['op'] == 'replace'
                  and path in ('/spec/disableFrontend', '/spec/lastAttachedBy')), 'only_owned_ticket_or_original_flag_restore')
        cmd = ['kubectl', 'patch', request['kind'], request['volume'], '-n', LH,
               '--type=json', '-p', json.dumps(request['patch']), '-o', 'json']
        if request.get('dryRun'):
            cmd.append('--dry-run=server')
        data = None
    else:
        need(verb == 'create' and request['object']['kind'] in ('Snapshot', 'Backup')
             and request['object']['apiVersion'] == 'longhorn.io/v1beta2'
             and request['object']['metadata']['namespace'] == LH
             and re.fullmatch('migration-preserve-[0-9a-f]{12}(-backup)?', request['object']['metadata']['name']), 'owned_snapshot_backup_only')
        cmd = ['kubectl', 'create', '-f', '-', '-o', 'json']
        if request.get('dryRun'):
            cmd.append('--dry-run=server')
        data = json.dumps(request['object']).encode()
    child = subprocess.run(cmd, input=data, capture_output=True, timeout=45)
    need(len(child.stdout) <= 16 * 1024**2 and len(child.stderr) <= 1024**2, 'bounded_native_response')
    print(json.dumps({'rc': child.returncode, 'stdout': child.stdout.decode(), 'stderr': child.stderr.decode()}))


def call(request):
    source = 'import sys;sys.argv=["checkpoint","--remote"]\n' + Path(__file__).read_text()
    cmd = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
           '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-o', 'ConnectTimeout=10',
           '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4',
           shlex.join(['python3', '-B', '-c', source])]
    child = subprocess.run(cmd, input=json.dumps(request).encode(), capture_output=True, timeout=60)
    need(child.returncode == 0 and len(child.stdout) < 20 * 1024**2, 'strict_ssh_native_transport')
    result = json.loads(child.stdout)
    need(result['rc'] == 0, 'native_' + request['verb'] + '_refused')
    return json.loads(result['stdout'])


def get(kind, name=None, namespace=LH, all_ns=False):
    return call({'verb': 'get', 'kind': kind, 'name': name, 'namespace': namespace, 'allNamespaces': all_ns})


def items(kind, namespace=LH, all_ns=False):
    values = get(kind, namespace=namespace, all_ns=all_ns)['items']
    need(len(values) < 10000, 'bounded_native_objects')
    return values


def meta(obj):
    return {k: obj['metadata'][k] for k in ('name', 'namespace', 'uid', 'resourceVersion') if k in obj['metadata']}


def save(run, name, data):
    with (run / name).open('x') as out:
        json.dump(data, out, indent=2)
        out.write('\n')


def no_consumer(claim):
    readers = []
    for pod in items('pods', namespace=claim['metadata']['namespace']):
        if any(v.get('persistentVolumeClaim', {}).get('claimName') == claim['metadata']['name'] for v in pod['spec'].get('volumes', [])):
            states = [c['state'] for c in pod.get('status', {}).get('containerStatuses', [])]
            need(pod['status'].get('phase') in ('Failed', 'Succeeded') and states
                 and all('terminated' in s for s in states), 'claim_has_live_or_unresolved_consumer')
            readers.append(meta(pod))
    return readers


def bound_state(profile):
    volume = get('volumes.longhorn.io', profile['volume']['metadata']['name'])
    claim = get('pvc', profile['claim']['metadata']['name'], profile['claim']['metadata']['namespace'])
    pv = get('pv', claim['spec']['volumeName'], namespace=None)
    need(volume['metadata']['uid'] == profile['volume']['metadata']['uid']
         and claim['metadata']['uid'] == profile['claim']['metadata']['uid']
         and pv['metadata']['uid'] == profile['pv']['metadata']['uid']
         and claim['status']['phase'] == 'Bound' and pv['spec']['csi']['volumeHandle'] == volume['metadata']['name']
         and pv['spec']['claimRef']['uid'] == claim['metadata']['uid'], 'original_claim_pv_volume_chain')
    no_consumer(claim)
    need(volume['spec']['image'] == IMAGE and volume['status']['currentImage'] == IMAGE
         and volume['spec']['numberOfReplicas'] == 2 and volume['spec']['encrypted']
         and volume['spec']['dataEngine'] == 'v1' and not volume['spec'].get('migrationNodeID')
         and not volume['status'].get('restoreRequired'), 'unchanged_original_v1_volume')
    replicas = [r for r in items('replicas.longhorn.io') if r['spec']['volumeName'] == volume['metadata']['name']]
    missing_original = profile.get('allowOriginalMissingReplica', False)
    need(not missing_original or (volume['metadata']['name'] == VOLUMES['ruckus-old']
         and len(profile['replicas']) == 1), 'only_exact_retained_ruckus_missing_replica')
    need({r['metadata']['uid'] for r in replicas} == {r['metadata']['uid'] for r in profile['replicas']}
         and len(replicas) == (1 if missing_original else 2)
         and not any(r['spec'].get('failedAt') for r in replicas), 'exact_prepared_replicas_without_failure')
    return volume, replicas


def ticket_patch(profile, remove=False):
    name = profile['volume']['metadata']['name']
    va = get('volumeattachments.longhorn.io', name)
    need(va['metadata']['uid'] == profile['attachment']['metadata']['uid'] and va['spec']['volume'] == name, 'original_attachment_identity')
    tickets = va['spec'].get('attachmentTickets') or {}
    if remove:
        need(tickets.get(profile['token']) == profile['ticket'], 'owned_ticket_exact_match')
        operations = [{'op': 'test', 'path': '/spec/attachmentTickets/' + profile['token'], 'value': profile['ticket']},
                      {'op': 'remove', 'path': '/spec/attachmentTickets/' + profile['token']}]
    else:
        need(not tickets, 'no_prior_attachment_tickets')
        operations = [{'op': 'test', 'path': '/spec/attachmentTickets', 'value': {}},
                      {'op': 'add', 'path': '/spec/attachmentTickets/' + profile['token'], 'value': profile['ticket']}]
    return {'verb': 'patch', 'kind': 'volumeattachments.longhorn.io', 'volume': name,
            'patch': [{'op': 'test', 'path': '/metadata/uid', 'value': va['metadata']['uid']},
                      {'op': 'test', 'path': '/metadata/resourceVersion', 'value': va['metadata']['resourceVersion']}, *operations]}


def prepare(run, name):
    baseline = json.loads((O / 'longhorn-preflight-recovery-mapping/live.json').read_text())
    previous = next(v for v in baseline['volumes'] if v['name'] == name)
    volume = get('volumes.longhorn.io', name)
    need(volume['metadata']['uid'] == previous['uid'] and volume['status']['state'] == 'detached'
         and not volume['spec']['nodeID'], 'original_detached_volume_required')
    claim = next(c for c in items('pvc', namespace=None, all_ns=True) if c['spec'].get('volumeName') == name)
    pv = get('pv', name, namespace=None)
    replicas = [r for r in items('replicas.longhorn.io') if r['spec']['volumeName'] == name]
    repair_missing = name == VOLUMES['ruckus-old'] and len(replicas) == 1
    need((len(replicas) == 2 or repair_missing) and all(r['status']['currentState'] == 'stopped'
         and not r['spec'].get('failedAt') and r['spec'].get('healthyAt') for r in replicas), 'two_previously_healthy_stopped_replicas_required')
    if repair_missing:
        need(volume['spec']['numberOfReplicas'] == 2, 'existing_two_replica_intent_never_reduced')
        nodes = items('nodes.longhorn.io')
        need(len(nodes) == 3 and all(d['storageAvailable'] > d['storageMaximum'] // 4
             + int(volume['spec']['size']) + 512 * 1024**2
             for n in nodes for d in n['status']['diskStatus'].values()), 'all_possible_rebuild_nodes_keep_floor_full_volume_and_margin')
    backup_node = 'workernode2' if name == VOLUMES['pihole-old-1'] else 'workernode1'
    need(backup_node in {r['spec']['nodeID'] for r in replicas}, 'existing_selected_replica_node_required')
    node = get('nodes.longhorn.io', backup_node)
    need(any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions']), 'existing_backup_node_ready')
    disk = next(iter(node['status']['diskStatus'].values()))
    need(disk['storageAvailable'] > disk['storageMaximum'] // 4 + 512 * 1024**2, 'unchanged_node_floor_plus_backup_margin')
    target = get('backuptargets.longhorn.io', 'default')
    need(target['status']['available'] and not target['status'].get('error'), 'existing_available_backup_target')
    images = items('engineimages.longhorn.io')
    need(any(i['spec']['image'] == IMAGE and i['status']['nodeDeploymentMap'].get(backup_node) for i in images), 'existing_deployed_engine_image')
    need(get('settings.longhorn.io', 'concurrent-automatic-engine-upgrade-per-node-limit')['value'] == '0', 'automatic_engine_upgrade_remains_disabled')
    need(get('settings.longhorn.io', 'current-longhorn-version')['value'] in ('v1.12.1', '1.12.1')
         and get('settings.longhorn.io', 'default-engine-image')['value'] == IMAGE, 'installed_engine_generation_unchanged')
    token = 'migration-preserve-' + uuid.uuid4().hex[:12]
    profile = {'volume': volume, 'claim': claim, 'pv': pv, 'replicas': replicas,
               'allowOriginalMissingReplica': repair_missing,
               'attachment': get('volumeattachments.longhorn.io', name), 'target': target, 'node': meta(node),
               'token': token, 'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'ticket': {'id': token, 'generation': 0, 'type': 'longhorn-api', 'nodeID': backup_node,
                          'parameters': {'disableFrontend': 'true', 'lastAttachedBy': token}}}
    bound_state(profile)
    patch = ticket_patch(profile)
    patch['dryRun'] = True
    dry = call(patch)
    need(dry['spec']['attachmentTickets'][token] == profile['ticket'], 'native_ticket_defaults_match_reviewed_ticket')
    save(run, 'profile.json', profile)
    save(run, 'prepare-result.json', {'status': 'prepared', 'volume': name, 'backupNode': backup_node, 'frontendWillBeDisabled': True,
                                    'attachmentPatchServerDryRunPassed': True, 'clusterMutation': False})


def apply(run, profile, observe=False):
    name, token = profile['volume']['metadata']['name'], profile['token']
    need(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == profile['sourceSHA256'], 'exact_prepared_source')
    receipt = 'observe-result.json' if observe else 'apply-result.json'
    need(not (run / receipt).exists(), 'earlier_attempt_receipt_preserved')
    result = {'status': 'started', 'volume': name, 'volumeUID': profile['volume']['metadata']['uid'],
              'backupNode': profile['ticket']['nodeID'],
              'token': token, 'snapshot': token, 'backup': token + '-backup', 'forceDetach': False,
              'sourceSHA256': profile['sourceSHA256'], 'independentRestoreVerified': False}
    backup_done = False
    original_replica_uids = {r['metadata']['uid'] for r in profile['replicas']}
    def adopt_repaired_replicas(proof):
        need(proof['token'] == token and proof['sourceSHA256'] == profile['sourceSHA256']
             and proof['originalProfileSHA256'] == hashlib.sha256((run / 'profile.json').read_bytes()).hexdigest()
             and set(proof['originalReplicaUIDs']) == original_replica_uids
             and len(proof['replicas']) == 2
             and original_replica_uids < {r['metadata']['uid'] for r in proof['replicas']}, 'exact_owned_normal_rebuild_proof')
        profile['replicas'] = proof['replicas']
        profile['allowOriginalMissingReplica'] = False
        result['normalRebuildCreatedReplicaUIDs'] = sorted({r['metadata']['uid'] for r in proof['replicas']} - original_replica_uids)
        result['desiredReplicaCountChanged'] = False
    if profile.get('allowOriginalMissingReplica') and observe and (run / 'normal-rebuild-proof.json').exists():
        adopt_repaired_replicas(json.loads((run / 'normal-rebuild-proof.json').read_text()))
    def event(phase, **values):
        with (run / 'events.jsonl').open('a') as out:
            out.write(json.dumps({'UTC': timestamp(), 'phase': phase, **values}) + '\n')
        result['phase'] = phase
    def wait(kind, resource, predicate, seconds):
        deadline = time.monotonic() + seconds
        while True:
            obj = get(kind, resource)
            need(not obj.get('status', {}).get('error'), 'native_' + kind.split('.')[0] + '_error')
            if predicate(obj):
                return obj
            need(time.monotonic() < deadline, 'native_observation_deadline_' + kind.split('.')[0])
            time.sleep(3)
    try:
        volume, _ = bound_state(profile)
        need(get('settings.longhorn.io', 'current-longhorn-version')['value'] in ('v1.12.1', '1.12.1')
             and get('settings.longhorn.io', 'default-engine-image')['value'] == IMAGE, 'installed_engine_generation_unchanged')
        if not observe:
            need(volume['status']['state'] == 'detached' and not volume['spec']['nodeID'], 'still_detached_before_owned_ticket')
            save(run, 'apply-intent.json', result)
            event('add_owned_frontend_disabled_ticket')
            call(ticket_patch(profile))
            event('wait_original_engine_and_two_rw_replicas')
            wait('volumes.longhorn.io', name, lambda v: v['status']['state'] == 'attached' and v['status']['robustness'] == 'healthy' and v['status']['frontendDisabled'], 180)
            if profile.get('allowOriginalMissingReplica'):
                repaired = [r for r in items('replicas.longhorn.io') if r['spec']['volumeName'] == name]
                need(len(repaired) == 2 and original_replica_uids < {r['metadata']['uid'] for r in repaired}
                     and len({r['spec']['nodeID'] for r in repaired}) == 2
                     and all(r['status']['currentState'] == 'running' and r['spec'].get('healthyAt')
                             and not r['spec'].get('failedAt') for r in repaired), 'normal_manager_rebuild_two_healthy_distinct_nodes')
                for replica in repaired:
                    if replica['metadata']['uid'] not in original_replica_uids:
                        need(any(o['uid'] == profile['volume']['metadata']['uid'] for o in replica['metadata'].get('ownerReferences', [])), 'new_replica_owned_by_original_volume')
                proof = {'token': token, 'sourceSHA256': profile['sourceSHA256'],
                         'originalProfileSHA256': hashlib.sha256((run / 'profile.json').read_bytes()).hexdigest(),
                         'originalReplicaUIDs': sorted(original_replica_uids), 'replicas': repaired,
                         'createdByExistingManagerDesiredReplicaReconciliation': True}
                save(run, 'normal-rebuild-proof.json', proof)
                adopt_repaired_replicas(proof)
            volume, replicas = bound_state(profile)
            engines = [e for e in items('engines.longhorn.io') if e['spec']['volumeName'] == name]
            need(len(engines) == 1 and engines[0]['status']['currentState'] == 'running'
                 and list(engines[0]['status']['replicaModeMap'].values()).count('RW') == 2
                 and len(engines[0]['status']['replicaModeMap']) == 2
                 and all(r['status']['currentState'] == 'running' for r in replicas), 'two_actual_rw_replicas_before_snapshot')
            save(run, 'attached-proof.json', {'volume': volume, 'replicas': replicas, 'engine': engines[0]})
            snapshot = {'apiVersion': 'longhorn.io/v1beta2', 'kind': 'Snapshot',
                        'metadata': {'name': token, 'namespace': LH, 'labels': {'migration-preservation': token}},
                        'spec': {'volume': name, 'createSnapshot': True, 'labels': {'consistency': 'cold-detached-no-frontend'}}}
            event('create_owned_snapshot')
            created = call({'verb': 'create', 'object': snapshot})
            result['snapshotUID'] = created['metadata']['uid']
            wait('snapshots.longhorn.io', token, lambda s: s.get('status', {}).get('readyToUse'), 180)
            bound_state(profile)
            backup = {'apiVersion': 'longhorn.io/v1beta2', 'kind': 'Backup',
                      'metadata': {'name': token + '-backup', 'namespace': LH,
                                   'labels': {'backup-target': 'default', 'backup-volume': name, 'migration-preservation': token}},
                      'spec': {'snapshotName': token, 'backupMode': 'full',
                               'labels': {'consistency': 'cold-detached-no-frontend'}}}
            event('create_owned_full_backup')
            created = call({'verb': 'create', 'object': backup})
            result['backupUID'] = created['metadata']['uid']
        event('observe_exact_backup_completion')
        backup = wait('backups.longhorn.io', token + '-backup', lambda b: b.get('status', {}).get('state') == 'Completed', 900)
        need(backup['status']['volumeName'] == name and backup['status']['snapshotName'] == token
             and backup['status']['backupTargetName'] == 'default', 'exact_backup_snapshot_volume_target')
        backup_done = True
        save(run, 'completed-backup.json' if not observe else 'completed-backup-observed.json', backup)
        result.update(backupUID=backup['metadata']['uid'], backupState='Completed', backupURL=backup['status'].get('url'),
                      coldNoFrontendNoConsumer=True)
        event('remove_only_owned_ticket')
        bound_state(profile)
        call(ticket_patch(profile, remove=True))
        wait('volumes.longhorn.io', name, lambda v: v['status']['state'] == 'detached' and not v['spec']['nodeID'], 180)
        volume, _ = bound_state(profile)
        va = get('volumeattachments.longhorn.io', name)
        need(not va['spec'].get('attachmentTickets'), 'all_tickets_released_normally')
        patch = [{'op': 'test', 'path': '/metadata/uid', 'value': volume['metadata']['uid']},
                 {'op': 'test', 'path': '/metadata/resourceVersion', 'value': volume['metadata']['resourceVersion']},
                 {'op': 'test', 'path': '/spec/nodeID', 'value': ''},
                 {'op': 'test', 'path': '/status/state', 'value': 'detached'}]
        for field in ('disableFrontend', 'lastAttachedBy'):
            if volume['spec'].get(field) != profile['volume']['spec'].get(field):
                patch.append({'op': 'replace', 'path': '/spec/' + field, 'value': profile['volume']['spec'][field]})
        if len(patch) > 4:
            call({'verb': 'patch', 'kind': 'volumes.longhorn.io', 'volume': name, 'patch': patch})
        volume, replicas = bound_state(profile)
        need(volume['spec'] == profile['volume']['spec'] and all(r['status']['currentState'] == 'stopped' for r in replicas), 'original_volume_spec_and_stopped_replicas_restored')
        save(run, 'detached-proof.json' if not observe else 'detached-proof-observed.json', {'volume': volume, 'replicas': replicas, 'attachment': va})
        result.update(status='completed_native_backup_and_detach', originalVolumeSpecRestored=True,
                      originalReplicaUIDsPreserved=True, detachedAgain=True, completedUTC=timestamp())
        event('completed_native_backup_and_normal_detach')
    except Exception as error:
        result.update(status='failed', errorCategory=str(error) if isinstance(error, ValueError) else type(error).__name__,
                      backupCompletionObserved=backup_done, retentionReason='retain source/objects and any owned attachment for exact-state diagnosis; never force detach or recreate backup')
        raise
    finally:
        save(run, receipt, result)
        print(json.dumps({k: result.get(k) for k in ('status', 'phase', 'volume', 'backupState', 'detachedAgain', 'errorCategory')}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--remote', action='store_true')
    p.add_argument('--phase', choices=['prepare', 'apply', 'observe'])
    p.add_argument('--volume', choices=sorted(VOLUMES))
    args = p.parse_args()
    if args.remote:
        remote()
        return
    need(args.phase and args.volume and os.geteuid() == 1000 and F.is_mount() and R.resolve() == R, 'owned_checkpoint_scope')
    os.umask(0o077)
    for path in (F, Path('/mnt/c')):
        s = os.statvfs(path)
        need(s.f_bavail * s.f_frsize >= 15 * 1024**3 + 32 * 1024**2, 'controller_metadata_capacity_floor')
    descriptor = os.open(R / 'operation.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run = R / args.volume
        if args.phase == 'prepare':
            need(not run.exists(), 'original_preparation_preserved')
            run.mkdir(mode=0o700)
            try:
                prepare(run, VOLUMES[args.volume])
            except Exception as error:
                save(run, 'prepare-failure.json', {'status': 'failed_before_mutation',
                     'errorCategory': str(error) if isinstance(error, ValueError) else type(error).__name__})
                raise
        else:
            profile = json.loads((run / 'profile.json').read_text())
            apply(run, profile, observe=args.phase == 'observe')
    finally:
        os.close(descriptor)


if __name__ == '__main__':
    main()
