"""Pure fixtures: no Kubernetes, encryption, data reads or runtime containers."""
import copy
import subprocess
import unittest
from unittest import mock

from test_bortus_cold_checkpoint import FakeClient, fixtures, prepared
from test_bortus_independent_restore_preflight import prepared as restored
from test_bortus_independent_restore_preflight import module as restore

preflight = fixtures.module


def alias(inventory):
    obj = copy.deepcopy(inventory['items'][0])
    obj['metadata'].update(name='foreign-pv', uid='foreign-uid')
    obj['spec']['claimRef'].update(namespace='foreign-namespace', name='foreign-claim', uid='foreign-claim-uid')
    return obj


class PhysicalVolumeFence(unittest.TestCase):
    def test_complete_list_keeps_only_bounded_public_summary(self):
        objects = fixtures.fixture()
        objects[9]['metadata'].update({'continue': '', 'remainingItemCount': 0})
        other = alias(objects[9])
        other['spec']['csi']['volumeHandle'] = 'different-volume'
        objects[9]['items'].append(other)
        report = preflight.evaluate(objects, 'bortus-data-uid')
        self.assertEqual(report['physical_volume_pv_inventory'], {
            'items': 2, 'resourceVersion': 'opaque-list-rv', 'sole_original_longhorn_pv': True})
        self.assertNotIn('foreign-pv', str(report))
        # A different CSI driver has a different handle namespace, not a Longhorn alias.
        other['spec']['csi'].update(driver='different.csi.example', volumeHandle='pvc-fixture')
        preflight.evaluate(objects, 'bortus-data-uid')

    def test_typed_raw_collection_items_may_omit_embedded_type_meta(self):
        objects = fixtures.fixture()
        for item in objects[9]['items']:
            item.pop('apiVersion'); item.pop('kind')
        preflight.evaluate(objects, 'bortus-data-uid')

    def test_alias_is_refused_even_unbound_failed_or_deleting(self):
        for phase in ('Available', 'Released', 'Failed', 'Bound'):
            for deleting in (False, True):
                objects = fixtures.fixture()
                obj = alias(objects[9]); obj['status'] = {'phase': phase}
                if deleting:
                    obj['metadata']['deletionTimestamp'] = 'fixture'
                objects[9]['items'].append(obj)
                with self.subTest(phase=phase, deleting=deleting), self.assertRaises(RuntimeError):
                    preflight.evaluate(objects, 'bortus-data-uid')

    def test_missing_foreign_recreated_remapped_and_duplicate_entries_refuse(self):
        for change in ('empty', 'foreign', 'recreated', 'remapped', 'driver', 'duplicate-name',
                       'duplicate-uid', 'deleting'):
            objects = fixtures.fixture(); inventory = objects[9]; item = inventory['items'][0]
            if change == 'empty': inventory['items'] = []
            elif change == 'foreign': inventory['items'] = [alias(inventory)]
            elif change == 'recreated': item['metadata']['uid'] = 'recreated-uid'
            elif change == 'remapped': item['spec']['csi']['volumeHandle'] = 'other'
            elif change == 'driver': item['spec']['csi']['driver'] = 'unsupported.example'
            elif change == 'deleting': item['metadata']['deletionTimestamp'] = 'fixture'
            else:
                duplicate = alias(inventory); duplicate['spec']['csi']['volumeHandle'] = 'other'
                duplicate['metadata']['name' if change == 'duplicate-name' else 'uid'] = item['metadata']['name' if change == 'duplicate-name' else 'uid']
                inventory['items'].append(duplicate)
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                preflight.evaluate(objects, 'bortus-data-uid')

    def test_incomplete_malformed_missing_and_overbound_lists_refuse(self):
        for change in ('missing', 'null', 'wrong-kind', 'wrong-version', 'missing-rv', 'long-rv',
                       'continue', 'null-continue', 'remaining', 'bool-remaining', 'items-null',
                       'item-null', 'item-kind', 'metadata-null', 'spec-null', 'csi-null', 'missing-handle',
                       'missing-uid', 'long-uid', 'namespaced', 'overbound'):
            objects = fixtures.fixture(); inventory = objects[9]; item = inventory['items'][0]
            if change == 'missing': objects.pop()
            elif change == 'null': objects[9] = None
            elif change == 'wrong-kind': inventory['kind'] = 'List'
            elif change == 'wrong-version': inventory['apiVersion'] = 'v2'
            elif change == 'missing-rv': inventory['metadata'].pop('resourceVersion')
            elif change == 'long-rv': inventory['metadata']['resourceVersion'] = 'x' * 257
            elif change == 'continue': inventory['metadata']['continue'] = 'fixture-continuation'
            elif change == 'null-continue': inventory['metadata']['continue'] = None
            elif change == 'remaining': inventory['metadata']['remainingItemCount'] = 1
            elif change == 'bool-remaining': inventory['metadata']['remainingItemCount'] = False
            elif change == 'items-null': inventory['items'] = None
            elif change == 'item-null': inventory['items'][0] = None
            elif change == 'item-kind': item['kind'] = 'Pod'
            elif change == 'metadata-null': item['metadata'] = None
            elif change == 'spec-null': item['spec'] = None
            elif change == 'csi-null': item['spec']['csi'] = None
            elif change == 'missing-handle': item['spec']['csi'].pop('volumeHandle')
            elif change == 'missing-uid': item['metadata'].pop('uid')
            elif change == 'long-uid': item['metadata']['uid'] = 'x' * 254
            elif change == 'namespaced': item['metadata']['namespace'] = 'foreign'
            elif change == 'overbound': inventory['items'] *= preflight.MAX_PV_ITEMS + 1
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                preflight.evaluate(objects, 'bortus-data-uid')

    def test_exact_item_bound_and_opaque_rv_observation(self):
        objects = fixtures.fixture(); inventory = objects[9]
        for n in range(preflight.MAX_PV_ITEMS - 1):
            inventory['items'].append({'apiVersion': 'v1', 'kind': 'PersistentVolume',
                                       'metadata': fixtures.metadata('other-' + str(n)),
                                       'spec': {'nfs': {'server': 'public-fixture', 'path': '/'}}})
        inventory['metadata']['resourceVersion'] = 'not-numeric:0/rv'
        report = preflight.evaluate(objects, 'bortus-data-uid')
        self.assertEqual(report['physical_volume_pv_inventory']['items'], preflight.MAX_PV_ITEMS)

    def test_real_preflight_client_requires_cluster_list_and_bounded_wire(self):
        fake = FakeClient()
        client = preflight.Client()
        with mock.patch.object(client, 'get', side_effect=fake.get) as reads:
            client.inspect('bortus-data-uid')
            self.assertIn(mock.call('pvs'), reads.call_args_list)
        result = subprocess.CompletedProcess([], 0, b'x' * (8 * 1024 * 1024 + 1), b'private')
        with mock.patch.object(preflight.subprocess, 'run', return_value=result), self.assertRaises(RuntimeError) as error:
            client.get('pvs')
        self.assertNotIn('private', str(error.exception))
        result = subprocess.CompletedProcess([], 0, b'{}', b'')
        with mock.patch.object(preflight.subprocess, 'run', return_value=result) as request:
            client.get('pvs')
        argv = request.call_args.args[0]
        self.assertEqual(argv[-2:], ['--raw', '/api/v1/persistentvolumes?limit=10001'])
        self.assertNotIn('-o', argv)
        with mock.patch.object(preflight.subprocess, 'run') as request:
            with self.assertRaises(RuntimeError): client.get('pvs', namespace='bortus')
            request.assert_not_called()

    def test_prepare_alias_refuses_before_any_mutation(self):
        fake = FakeClient(); fake.resources['pvs']['items'].append(alias(fake.resources['pvs']))
        with self.assertRaises(RuntimeError): prepared(fake)
        self.assertEqual(fake.calls, [])

    def test_cold_storage_checks_before_and_after_archive_stream(self):
        fake, journal, operation = prepared()
        original = fake.get
        pvs_reads = []
        def get(kind, name=None, namespace=None):
            if kind == 'pvs': pvs_reads.append(len(pvs_reads))
            return original(kind, name, namespace)
        fake.get = get
        def stream(checkpoint):
            self.assertTrue(checkpoint.cold())  # before encrypted streaming
            fake.resources['pvs']['items'].append(alias(fake.resources['pvs']))
            with self.assertRaises(RuntimeError): checkpoint.cold()  # after streaming
            raise RuntimeError('synthetic stream fenced')
        operation.archive = stream
        with self.assertRaises(RuntimeError): operation.capture()
        self.assertGreaterEqual(len(pvs_reads), 4)
        self.assertFalse(any(call[:2] == ('create', 'Snapshot') for call in fake.calls))
        self.assertFalse(journal.record.get('cold_snapshot_ready', False))
        self.assertFalse(journal.record.get('writer_resumed_ready', False))

    def test_storage_rechecks_refuse_each_current_list_failure(self):
        for change in ('alias', 'incomplete', 'recreated', 'missing'):
            fake, _, operation = prepared()
            inventory = fake.resources['pvs']
            if change == 'alias': inventory['items'].append(alias(inventory))
            elif change == 'incomplete': inventory['metadata']['continue'] = 'continuation'
            elif change == 'recreated': inventory['items'][0]['metadata']['uid'] = 'replacement'
            else: inventory['items'] = []
            with self.subTest(change=change), self.assertRaises(RuntimeError): operation.storage()
            self.assertEqual(fake.calls, [])

    def test_independent_restore_inherits_alias_and_incomplete_refusal(self):
        for change in ('alias', 'incomplete', 'missing'):
            client, record = restored()
            inventory = client.resources['pvs']
            if change == 'alias': inventory['items'].append(alias(inventory))
            elif change == 'incomplete': inventory['metadata']['continue'] = 'continuation'
            else: inventory['items'] = []
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                restore.prepare(client, record, 'registry.example/bortus@sha256:' + 'a' * 64, 'other-node')
            self.assertEqual(client.calls, [])


if __name__ == '__main__':
    unittest.main()
