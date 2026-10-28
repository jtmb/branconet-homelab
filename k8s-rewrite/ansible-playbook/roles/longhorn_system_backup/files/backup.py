"""Create one native configuration-only SystemBackup; never back up volumes."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import urllib.parse
import uuid

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
REVIEW = ROOT / 'platform-upstream-review-20261027'
TARGET_UID = '999fe7cd-e073-4a52-ba62-87db1857f876'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def command(args, value=None):
    run = subprocess.run(SSH + [shlex.join(['kubectl', *args])],
                         input=None if value is None else json.dumps(value).encode(),
                         capture_output=True, timeout=90)
    need(run.returncode == 0, 'kubernetes_operation_failed_no_credential_output')
    need(len(run.stdout) <= 16 * 1024**2, 'bounded_response')
    return json.loads(run.stdout) if run.stdout.strip() else None


def get(kind, name=None):
    return command(['-n', 'longhorn-system', 'get', kind, *([name] if name else []), '-o', 'json'])


def scope():
    target = get('backuptargets.longhorn.io', 'default')
    need(target['metadata']['uid'] == TARGET_UID and target['status'].get('available'), 'original_available_nas_target')
    url = urllib.parse.urlsplit(target['spec']['backupTargetURL'])
    need(url.scheme == 'cifs' and url.hostname == '192.168.0.8' and not url.username
         and not url.password, 'existing_nas_only')
    need(get('settings.longhorn.io', 'current-longhorn-version')['value'] == 'v1.12.1', 'reviewed_longhorn_version')
    need(get('settings.longhorn.io', 'concurrent-automatic-engine-upgrade-per-node-limit')['value'] == '0', 'no_automatic_engine_upgrade')
    need(not get('backingimages.longhorn.io')['items'], 'no_backing_image_backup_side_effect')
    need(all(b.get('status', {}).get('state') in ['Ready', 'Error']
             for b in get('systembackups.longhorn.io')['items']), 'no_concurrent_system_backup')
    volumes = get('volumes.longhorn.io')['items']
    need(all(v['spec'].get('numberOfReplicas') == 2 and v['spec'].get('dataEngine') == 'v1'
             and (v['status'].get('state') != 'attached' or v['status'].get('robustness') == 'healthy')
             for v in volumes), 'preserved_v1_redundancy_health')
    nodes = command(['get', 'nodes', '-o', 'json'])['items']
    need(len(nodes) == 3, 'original_three_node_cluster')
    free = {}
    for node in nodes:
        name = node['metadata']['name']
        need(any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions'])
             and not any(c['type'].endswith('Pressure') and c['status'] == 'True'
                         for c in node['status']['conditions']), 'ready_nodes_without_pressure')
        stats = command(['get', '--raw', '/api/v1/nodes/' + name + '/proxy/stats/summary'])['node']
        imagefs = stats['runtime']['imageFs']
        need(imagefs['availableBytes'] * 100 >= imagefs['capacityBytes'] * 15 + 64 * 1024**2 * 100,
             'retain_staging_headroom_and_64mib_metadata_budget')
        free[name] = imagefs['availableBytes']
    return {'backupTargetUID': TARGET_UID, 'nasScheme': url.scheme, 'nasHost': url.hostname,
            'nasPath': url.path, 'volumes': {v['metadata']['name']: {'uid': v['metadata']['uid'],
                'encrypted': v['spec'].get('encrypted'), 'replicas': v['spec']['numberOfReplicas'],
                'engineImage': v['spec'].get('engineImage')} for v in volumes}, 'availableBytes': free}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'create', 'observe'])
    parser.add_argument('--name', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    a = parser.parse_args()
    need(ROOT.is_mount() and a.output_dir.resolve() == a.output_dir and a.output_dir.parent == REVIEW
         and a.output_dir.name in ('longhorn-system-backup', 'longhorn-system-backup-20261028'), 'declared_output_root')
    need(re.fullmatch('preupgrade-2026102[78]-[0-9a-f]{8}', a.name), 'bounded_unique_backup_identity')
    os.umask(0o077)
    spec = {'apiVersion': 'longhorn.io/v1beta2', 'kind': 'SystemBackup',
            'metadata': {'name': a.name, 'namespace': 'longhorn-system',
                         'labels': {'branconet-operation': 'configuration-only-preupgrade'}},
            'spec': {'volumeBackupPolicy': 'disabled'}}
    if a.mode == 'prepare':
        need(not a.output_dir.exists(), 'prior_plan_preserved')
        for path in (ROOT, Path('/mnt/c')):
            fs = os.statvfs(path)
            need(fs.f_bavail * fs.f_frsize >= 15 * 1024**3 + 16 * 1024**2, 'controller_space_floor')
        observed = scope()
        need(not command(['-n', 'longhorn-system', 'get', 'systembackups.longhorn.io', a.name,
                          '--ignore-not-found', '-o', 'json']), 'backup_name_not_reused')
        dry = command(['create', '--dry-run=server', '-f', '-', '-o', 'json'], spec)
        need(dry['spec']['volumeBackupPolicy'] == 'disabled', 'server_accepted_configuration_only_policy')
        a.output_dir.mkdir(mode=0o700)
        plan = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'manifest': spec,
                'observed': observed, 'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'volumeBackupRequested': False, 'snapshotRequested': False, 'applicationConsistencyClaimed': False}
        (a.output_dir / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
        print(json.dumps({'phase': 'prepared', 'name': a.name, 'volumeBackupPolicy': 'disabled'}))
        return
    plan = json.loads((a.output_dir / 'plan.json').read_text())
    need(plan['manifest'] == spec, 'prepared_manifest_unchanged')
    if a.mode == 'create':
        need(plan['sourceSHA256'] == hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'prepared_mutating_source_unchanged')
        need(not (a.output_dir / 'create-intent.json').exists(), 'no_blind_resubmission')
        now = scope()
        need(all(now['volumes'].get(name) == row for name, row in plan['observed']['volumes'].items()),
             'prepared_volume_identities_preserved')
        intent = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'name': a.name,
                  'planSHA256': hashlib.sha256((a.output_dir / 'plan.json').read_bytes()).hexdigest()}
        (a.output_dir / 'create-intent.json').write_text(json.dumps(intent, indent=2) + '\n')
        result = command(['create', '-f', '-', '-o', 'json'], spec)
        record = {'name': a.name, 'uid': result['metadata']['uid'], 'volumeBackupPolicy': result['spec']['volumeBackupPolicy']}
        (a.output_dir / 'submission.json').write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps(record))
        return
    result = get('systembackups.longhorn.io', a.name)
    need(result['spec']['volumeBackupPolicy'] == 'disabled' and result['metadata'].get('labels', {}).get(
        'branconet-operation') == 'configuration-only-preupgrade', 'original_configuration_only_object')
    if (a.output_dir / 'submission.json').exists():
        need(result['metadata']['uid'] == json.loads((a.output_dir / 'submission.json').read_text())['uid'], 'same_submitted_uid')
    status = result.get('status', {})
    record = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'name': a.name,
              'uid': result['metadata']['uid'], 'state': status.get('state'), 'version': status.get('version'),
              'createdAt': status.get('createdAt'), 'managerImage': status.get('managerImage'),
              'errorConditionPresent': any(c.get('type') == 'Error' and c.get('status') == 'True'
                                          for c in (status.get('conditions') or [])),
              'volumeBackupPolicy': 'disabled', 'applicationDataBackupClaimed': False,
              'restoreVerified': False,
              'preparedSourceSHA256': plan['sourceSHA256'],
              'observerSourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (a.output_dir / ('observation-' + uuid.uuid4().hex + '.json')).write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
