import copy
import contextlib
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


module = load('restore_preflight', HERE.parent / 'inspect-bortus-independent-restore.py')
cold_tests = load('cold_tests', HERE / 'test_bortus_cold_checkpoint.py')
IMAGE = cold_tests.IMAGE


def prepared():
    client, journal, operation = cold_tests.prepared()
    operation.capture()
    journal.record['sqlite_archive']['ciphertext_sha256'] = 'a' * 64
    client.resources['pvc']['spec']['resources'] = {'requests': {'storage': '1Gi'}}
    client.owned[journal.record['backup_name']]['status'].update(
        volumeName='pvc-fixture', volumeSize='1073741824',
        snapshotName=journal.record['snapshot_name'], backupTargetName='default')
    client.resources['storageclass'] = {
        'metadata': cold_tests.fixtures.metadata('longhorn', None),
        'provisioner': 'driver.longhorn.io', 'reclaimPolicy': 'Retain',
        'allowVolumeExpansion': True, 'volumeBindingMode': 'Immediate',
        'parameters': copy.deepcopy(module.PARAMETERS)}
    client.resources['node'] = {'metadata': cold_tests.fixtures.metadata('other-node', None),
        'spec': {}, 'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}}
    client.collections = {'storageclasses': {'items': []}, 'pvc': {'items': []}, 'pods': {'items': []}}
    original_get = client.get

    def get(kind, name=None, namespace=None):
        if name is None and kind in client.collections:
            return copy.deepcopy(client.collections[kind])
        return original_get(kind, name, namespace)

    client.get = get
    client.calls.clear()
    return client, journal.record


class RestorePreflightTests(unittest.TestCase):
    def test_complete_checkpoint_creates_only_independent_inert_proposals(self):
        client, record = prepared()
        before = copy.deepcopy(record)
        report = module.prepare(client, record, IMAGE, 'other-node')
        self.assertEqual(record, before)
        self.assertEqual(client.calls, [])
        sc, claim, holder = report['proposals']
        name = 'bortus-restore-123456abcdef'
        self.assertEqual(sc['parameters']['fromBackup'], record['backup_url'])
        self.assertEqual(sc['reclaimPolicy'], 'Retain')
        self.assertEqual(sc['parameters']['encrypted'], 'true')
        self.assertEqual(sc['parameters']['numberOfReplicas'], '2')
        self.assertEqual(claim['spec']['storageClassName'], name)
        self.assertNotIn('volumeName', claim['spec'])
        self.assertEqual(claim['metadata']['annotations']['helm.sh/resource-policy'], 'keep')
        self.assertEqual(holder['spec']['nodeName'], 'other-node')
        self.assertFalse(holder['spec']['automountServiceAccountToken'])
        self.assertEqual(holder['spec']['containers'][0]['command'], ['node', '-e', 'setInterval(()=>{},1000)'])
        self.assertEqual(holder['spec']['containers'][0]['image'], IMAGE)
        self.assertEqual(holder['spec']['containers'][0]['imagePullPolicy'], 'Never')
        self.assertNotIn('env', holder['spec']['containers'][0])
        self.assertEqual(holder['spec']['volumes'][0]['persistentVolumeClaim'],
                         {'claimName': name, 'readOnly': True})
        self.assertEqual(report['required_protected_claim_names'], ['bortus-data', name])
        for flag in ('independent_restore_proven', 'whole_row_preservation_proven',
                     'holder_image_qualification_proven', 'holder_preload_and_actual_admission_proven'):
            self.assertFalse(report[flag])
        self.assertEqual(report['database_or_secret_reads'], 0)

    def test_incomplete_ambiguous_or_wrong_checkpoint_refused(self):
        for field in ('cold_snapshot_ready', 'encrypted_nas_backup_complete', 'writer_resumed_ready',
                      'reconcile_flags_restored', 'owned_holder_removed', 'sqlite_archive_state',
                      'snapshot_create_state', 'backup_create_state', 'completed_at_utc', 'run_id'):
            client, record = prepared()
            record[field] = None
            with self.subTest(field=field), self.assertRaises(Exception):
                module.prepare(client, record, IMAGE, 'other-node')
            self.assertEqual(client.calls, [])
        for field in ('authenticated_decryption_equal', 'nas_ciphertext_equal', 'ciphertext_sha256'):
            client, record = prepared()
            record['sqlite_archive'][field] = None
            with self.subTest(field=field), self.assertRaises(Exception):
                module.prepare(client, record, IMAGE, 'other-node')
        client, record = prepared()
        record['sqlite_archive']['plaintext_persisted'] = True
        with self.assertRaises(Exception):
            module.prepare(client, record, IMAGE, 'other-node')

    def test_source_and_backup_recreation_or_mismatches_refused(self):
        for kind in ('pvc', 'pv', 'volumes.longhorn.io', 'deployment', 'helmrelease', 'kustomization'):
            client, record = prepared()
            client.resources[kind]['metadata']['uid'] = 'recreated'
            with self.subTest(kind=kind), self.assertRaises(Exception):
                module.prepare(client, record, IMAGE, 'other-node')
            self.assertEqual(client.calls, [])
        for resource in ('snapshot', 'backup'):
            client, record = prepared()
            client.owned[record[resource + '_name']]['metadata']['uid'] = 'recreated'
            with self.subTest(resource=resource), self.assertRaises(Exception):
                module.prepare(client, record, IMAGE, 'other-node')
        for field, value in (('state', 'Pending'), ('volumeName', 'other-volume'),
                             ('volumeSize', '2147483648'), ('backupTargetName', 'other'),
                             ('snapshotName', 'other-snapshot'), ('error', 'PRIVATE_VALUE')):
            client, record = prepared()
            client.owned[record['backup_name']]['status'][field] = value
            with self.subTest(field=field), self.assertRaises(Exception):
                module.prepare(client, record, IMAGE, 'other-node')

    def test_foreign_or_credential_bearing_urls_are_never_exported(self):
        client, record = prepared()
        original = record['backup_url']
        for bad in (original + '&backup=', original + '&volume=', original + '&token=',
                    original + '&token=PRIVATE_VALUE', original.replace('192.168.0.8', 'user:PRIVATE_VALUE@192.168.0.8'),
                    original.replace('192.168.0.8', '192.168.0.9'), original.replace('backup=', 'backup=other-'),
                    original + '#PRIVATE_VALUE', original.replace('/longhorn?', '/longhorn/../other?')):
            client, record = prepared()
            record['backup_url'] = bad
            client.owned[record['backup_name']]['status']['url'] = bad
            with self.subTest(url_class='invalid'), self.assertRaises(Exception):
                module.prepare(client, record, IMAGE, 'other-node')
            self.assertEqual(client.calls, [])

    def test_storage_parameters_capacity_and_alternate_node_drift_refused(self):
        changes = [('parameters', 'encrypted', 'false'), ('parameters', 'numberOfReplicas', '1'),
                   ('parameters', 'csi.storage.k8s.io/node-stage-secret-namespace', 'other'),
                   ('parameters', 'unreviewed', 'PRIVATE_VALUE'), (None, 'reclaimPolicy', 'Delete'),
                   (None, 'volumeBindingMode', 'WaitForFirstConsumer')]
        for parent, key, value in changes:
            client, record = prepared()
            target = client.resources['storageclass'][parent] if parent else client.resources['storageclass']
            target[key] = value
            with self.subTest(key=key), self.assertRaises(Exception):
                module.prepare(client, record, IMAGE, 'other-node')
        client, record = prepared()
        client.resources['pvc']['spec']['resources']['requests']['storage'] = '2Gi'
        with self.assertRaises(Exception):
            module.prepare(client, record, IMAGE, 'other-node')
        for change in ('unready', 'unschedulable', 'source-node'):
            client, record = prepared()
            node = client.resources['node']
            alternate = 'other-node'
            if change == 'unready':
                node['status']['conditions'][0]['status'] = 'False'
            elif change == 'unschedulable':
                node['spec']['unschedulable'] = True
            else:
                alternate = client.objects[4]['items'][0]['spec']['nodeName']
                node['metadata']['name'] = alternate
            with self.subTest(change=change), self.assertRaises(Exception):
                module.prepare(client, record, IMAGE, alternate)

    def test_target_collision_and_unbounded_collections_refused(self):
        for kind in ('storageclasses', 'pvc', 'pods'):
            client, record = prepared()
            client.collections[kind]['items'] = [{'metadata': {'name': 'bortus-restore-123456abcdef'}}]
            with self.subTest(kind=kind), self.assertRaises(Exception):
                module.prepare(client, record, IMAGE, 'other-node')
            self.assertEqual(client.calls, [])
        for items in (None, [None], [{}], [{}] * 10001):
            client, record = prepared()
            client.collections['pvc']['items'] = items
            with self.assertRaises(Exception):
                module.prepare(client, record, IMAGE, 'other-node')

    def test_private_unrelated_journal_fields_do_not_enter_report(self):
        client, record = prepared()
        record['private_unrelated'] = 'PRIVATE_SENTINEL'
        record['sqlite_archive']['artifact'] = '/private/PRIVATE_SENTINEL'
        report = module.prepare(client, record, IMAGE, 'other-node')
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(report))

    def test_cli_overwrite_and_api_failure_are_fixed_and_nonmutating(self):
        with tempfile.TemporaryDirectory() as folder:
            output = pathlib.Path(folder) / 'retained.json'
            output.write_text('retained')
            args = ['inspect', '--checkpoint-journal', str(pathlib.Path(folder) / 'missing'),
                    '--holder-image', IMAGE, '--alternate-node', 'other-node', '--output', str(output)]
            with (mock.patch.object(module.sys, 'argv', args), mock.patch.object(module.cold, 'Client') as client,
                  contextlib.redirect_stderr(io.StringIO()) as error):
                self.assertEqual(module.main(), 1)
                client.assert_not_called()
            self.assertEqual(output.read_text(), 'retained')
            self.assertNotIn('PRIVATE', error.getvalue())
            output.unlink()
            journal = pathlib.Path(folder) / 'journal.json'
            _, record = prepared()
            journal.write_text(json.dumps(record))
            args[2] = str(journal)
            with (mock.patch.object(module.sys, 'argv', args), mock.patch.object(module.cold, 'Client') as client,
                  contextlib.redirect_stderr(io.StringIO()) as error):
                client.return_value.inspect.side_effect = RuntimeError('PRIVATE_API_FAILURE')
                self.assertEqual(module.main(), 1)
            self.assertFalse(output.exists())
            self.assertNotIn('PRIVATE', error.getvalue())


if __name__ == '__main__':
    unittest.main()
