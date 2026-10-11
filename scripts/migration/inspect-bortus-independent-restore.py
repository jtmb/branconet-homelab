#!/usr/bin/env python3
"""Read-only fresh-checkpoint restore prerequisites and inert proposals; never create."""
import argparse
import copy
import importlib.util
import json
import os
import pathlib
import re
import sys
import urllib.parse

loader = importlib.util.spec_from_file_location('cold_checkpoint',
    pathlib.Path(__file__).with_name('checkpoint-bortus-volume.py'))
cold = importlib.util.module_from_spec(loader)
loader.loader.exec_module(cold)
require, identity = cold.require, cold.identity

PARAMETERS = {
    'backupTargetName': 'default', 'dataEngine': 'v1', 'dataLocality': 'disabled',
    'disableRevisionCounter': 'true', 'encrypted': 'true', 'fromBackup': '',
    'fsType': 'ext4', 'numberOfReplicas': '2', 'staleReplicaTimeout': '30',
    'unmapMarkSnapChainRemoved': 'ignored'}
for operation in ('provisioner', 'node-publish', 'node-stage', 'node-expand'):
    PARAMETERS['csi.storage.k8s.io/' + operation + '-secret-name'] = 'longhorn-crypto'
    PARAMETERS['csi.storage.k8s.io/' + operation + '-secret-namespace'] = 'longhorn-system'


def valid_name(name):
    return isinstance(name, str) and len(name) <= 253 and bool(
        re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', name))


def url_matches(url, backup_name, volume_name):
    require(isinstance(url, str), 'Backup URL missing')
    parts = urllib.parse.urlsplit(url)
    try:
        query = urllib.parse.parse_qs(parts.query, strict_parsing=True,
                                     keep_blank_values=True, max_num_fields=2)
    except ValueError:
        raise RuntimeError('Exact credential-free source NAS backup required') from None
    require(parts.scheme == 'cifs' and parts.hostname == '192.168.0.8' and
            parts.username is None and parts.password is None and parts.port is None and
            not parts.fragment and
            parts.path == '/container_backups/k8s-migration-20261009/longhorn' and
            query == {
                'backup': [backup_name], 'volume': [volume_name]},
            'Exact credential-free source NAS backup required')


def validate_source(client, record, image, alternate_node):
    """Repeat original checkpoint/source fences without adopting restore targets."""
    require(cold.valid_digest(image) and valid_name(alternate_node), 'Invalid holder input')
    run_id = record.get('run_id')
    require(isinstance(run_id, str) and re.fullmatch(r'[0-9a-f]{12}', run_id),
            'Invalid checkpoint identity')
    for flag in ('cold_snapshot_ready', 'encrypted_nas_backup_complete',
                 'writer_resumed_ready', 'reconcile_flags_restored', 'owned_holder_removed'):
        require(record.get(flag) is True, 'Complete fresh checkpoint required')
    require(record.get('sqlite_archive_state') == 'confirmed' and
            record.get('snapshot_create_state') == 'confirmed' and
            record.get('backup_create_state') == 'confirmed' and
            isinstance(record.get('completed_at_utc'), str), 'Unresolved checkpoint result')
    archive = record.get('sqlite_archive', {})
    require(archive.get('authenticated_decryption_equal') is True and
            archive.get('nas_ciphertext_equal') is True and archive.get('plaintext_persisted') is False and
            isinstance(archive.get('ciphertext_sha256'), str) and
            re.fullmatch(r'[0-9a-f]{64}', archive['ciphertext_sha256']), 'Authenticated archive required')
    expected = record['baseline']['identities']
    fresh = client.inspect(expected['claim']['uid'], image)
    for key in ('claim', 'pv', 'longhorn_volume', 'deployment', 'helmrelease', 'kustomization'):
        require(cold.same_id({'metadata': fresh['identities'][key]}, expected[key]),
                'Original resource identity changed')
    volume_name = expected['longhorn_volume']['name']
    require(valid_name(volume_name), 'Invalid source volume')
    snapshot_name, backup_name = 'bortus-cold-' + run_id, 'backup-' + run_id
    require(record.get('snapshot_name') == snapshot_name and record.get('backup_name') == backup_name,
            'Checkpoint resource names differ')
    snapshot = client.get('snapshots.longhorn.io', snapshot_name, 'longhorn-system')
    backup = client.get('backups.longhorn.io', backup_name, 'longhorn-system')
    for obj, label in ((snapshot, 'snapshot'), (backup, 'backup')):
        require(cold.same_id(obj, record[label + '_identity']) and
                obj['metadata'].get('labels', {}).get('bortus-checkpoint') == run_id and
                not obj['metadata'].get('deletionTimestamp'), 'Checkpoint resource recreated or changed')
    sspec, sstatus = snapshot.get('spec', {}), snapshot.get('status', {})
    require(sspec.get('volume') == volume_name and sspec.get('createSnapshot') is True and
            sspec.get('labels', {}).get('bortus-consistency') == 'cold-writer-stopped' and
            sstatus.get('readyToUse') is True and not sstatus.get('error'), 'Cold snapshot unavailable')
    bspec, bstatus = backup.get('spec', {}), backup.get('status', {})
    require(bspec.get('snapshotName') == snapshot_name and bspec.get('backupMode') == 'full' and
            bspec.get('labels', {}).get('bortus-consistency') == 'cold-writer-stopped' and
            bstatus.get('state') == 'Completed' and not bstatus.get('error') and
            bstatus.get('volumeName') == volume_name and bstatus.get('snapshotName') == snapshot_name and
            bstatus.get('backupTargetName') == 'default' and bstatus.get('volumeSize') == '1073741824',
            'Completed exact full source backup unavailable')
    require(bstatus.get('url') == record.get('backup_url'), 'Completed NAS URL changed')
    url_matches(bstatus['url'], backup_name, volume_name)
    source = client.get('pvc', 'bortus-data', 'bortus')
    require(cold.same_id(source, expected['claim']) and
            source.get('spec', {}).get('resources', {}).get('requests', {}).get('storage') == '1Gi',
            'Reviewed source capacity changed')
    sc = client.get('storageclass', 'longhorn')
    require(sc.get('provisioner') == 'driver.longhorn.io' and sc.get('reclaimPolicy') == 'Retain' and
            sc.get('volumeBindingMode') == 'Immediate' and sc.get('allowVolumeExpansion') is True and
            sc.get('parameters') == PARAMETERS and not sc['metadata'].get('deletionTimestamp'),
            'Reviewed encrypted StorageClass contract changed')
    node = client.get('node', alternate_node)
    require(identity(node)['name'] == alternate_node and not node['metadata'].get('deletionTimestamp') and
            alternate_node != fresh['writer']['nodeName'] and not node.get('spec', {}).get('unschedulable') and
            any(c.get('type') == 'Ready' and c.get('status') == 'True'
                for c in node.get('status', {}).get('conditions', [])), 'Alternate Ready node required')
    return fresh, snapshot, backup, sc, node


def prepare(client, record, image, alternate_node):
    """Qualify source plus absent targets; proposals never prove admission or restore."""
    fresh, snapshot, backup, sc, node = validate_source(client, record, image, alternate_node)
    run_id = record['run_id']
    archive = record['sqlite_archive']
    bstatus = backup['status']
    name = 'bortus-restore-' + run_id
    for kind, namespace in (('storageclasses', None), ('pvc', 'bortus'), ('pods', 'bortus')):
        collection = client.get(kind, namespace=namespace)
        items = collection.get('items')
        require(isinstance(items, list) and len(items) <= 10000 and
                all(isinstance(x, dict) and valid_name(x.get('metadata', {}).get('name')) for x in items) and
                all(x.get('metadata', {}).get('name') != name for x in items),
                'Prior restore target exists; inspect rather than replay')
    labels = {'bortus-restore': run_id}
    parameters = dict(PARAMETERS, fromBackup=bstatus['url'])
    storage_class = {'apiVersion': 'storage.k8s.io/v1', 'kind': 'StorageClass',
        'metadata': {'name': name, 'labels': labels}, 'provisioner': 'driver.longhorn.io',
        'reclaimPolicy': 'Retain', 'volumeBindingMode': 'Immediate',
        'allowVolumeExpansion': True, 'parameters': parameters}
    claim = {'apiVersion': 'v1', 'kind': 'PersistentVolumeClaim',
        'metadata': {'name': name, 'namespace': 'bortus', 'labels': labels,
                     'annotations': {'helm.sh/resource-policy': 'keep'}},
        'spec': {'storageClassName': name, 'accessModes': ['ReadWriteOnce'],
                 'resources': {'requests': {'storage': '1Gi'}}}}
    holder = copy.deepcopy(fresh['holder_proposal'])
    holder['metadata'] = {'name': name, 'namespace': 'bortus', 'labels': labels}
    holder['spec']['nodeName'] = alternate_node
    holder['spec']['volumes'][0]['persistentVolumeClaim']['claimName'] = name
    return {'scope': 'Read-only fresh BORTUS restore prerequisites; no restore or data read',
        'checkpoint_run_id': run_id, 'source_identities': fresh['identities'],
        'snapshot_identity': identity(snapshot), 'backup_identity': identity(backup),
        'storageclass_identity': identity(sc), 'alternate_node_identity': identity(node),
        'original_ciphertext_sha256': archive['ciphertext_sha256'],
        'checks_passed': True, 'mutations': 0, 'database_or_secret_reads': 0,
        'separate_resource_reads_are_atomic': False,
        'restore_target_name': name, 'proposals': [storage_class, claim, holder],
        'required_protected_claim_names': ['bortus-data', name],
        'required_qualified_holder_image': image, 'holder_image_qualification_proven': False,
        'holder_preload_and_actual_admission_proven': False,
        'independent_restore_proven': False, 'whole_row_preservation_proven': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint-journal', type=pathlib.Path, required=True)
    parser.add_argument('--holder-image', required=True)
    parser.add_argument('--alternate-node', required=True)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        require(os.name == 'posix' and not os.path.lexists(args.output), 'Invalid output or runtime')
        require(args.checkpoint_journal.is_file() and not args.checkpoint_journal.is_symlink() and
                args.checkpoint_journal.stat().st_size <= 1024 * 1024, 'Invalid journal')
        report = prepare(cold.Client(), json.loads(args.checkpoint_journal.read_text()),
                         args.holder_image, args.alternate_node)
        report['collected_at_utc'] = cold.now()
        fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(report, out, indent=2)
            out.write('\n')
        print(json.dumps({'restore_preflight_passed': True, 'mutations': 0, 'restore_pending': True}))
        return 0
    except Exception:
        print('BORTUS restore preflight failed; private output withheld and no mutation performed',
              file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
