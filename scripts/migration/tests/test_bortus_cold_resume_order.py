"""Public cross-node RWO regression; all Kubernetes operations are synthetic."""
import copy
import importlib.util
import pathlib
import json
from unittest import mock
import unittest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('cold_order_fixtures', HERE / 'test_bortus_cold_checkpoint.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
module = fixtures.module


class CrossNodeClient(fixtures.FakeClient):
    def change(self, kind, name, ns, patch):
        result = super().change(kind, name, ns, patch)
        if kind == 'deployment' and patch[-1]['value'] == 1:
            writer = self.resources['pods']['items'][-1]
            writer['spec']['nodeName'] = 'alternate-fixture'
            holder_live = any(p['metadata']['name'].startswith('bortus-cold-')
                              for p in self.resources['pods']['items'])
            if holder_live:
                writer['status'] = {'phase': 'Pending', 'conditions': []}
        return result


class ColdResumeOrderTests(unittest.TestCase):
    def test_cross_node_writer_resume_releases_holder_first(self):
        client, journal, operation = fixtures.prepared(CrossNodeClient())
        operation.capture()
        deletion = next(i for i, c in enumerate(client.calls) if c[0] == 'delete-holder')
        resumed = next(i for i, c in enumerate(client.calls) if c == ('change', 'deployment', 'bortus', 1))
        self.assertLess(deletion, resumed)
        self.assertTrue(journal.record['writer_resumed_ready'])
        self.assertTrue(journal.record['encrypted_nas_backup_complete'])
        self.assertEqual('alternate-fixture', client.resources['pods']['items'][0]['spec']['nodeName'])

    def test_normal_detach_is_resume_only_and_waits_until_healthy(self):
        for state in ('detached', 'detaching', 'attaching'):
            client, journal, operation = fixtures.prepared()
            operation.control('deployment', 1, 0)
            client.get('pods', namespace='bortus'); client.get('pods', namespace='bortus')
            volume = client.resources['volumes.longhorn.io']
            volume['status'].update(state=state, robustness='unknown')
            self.assertFalse(operation.storage(resuming=True))
            with self.assertRaises(RuntimeError):
                operation.storage()
            original_change = client.change
            original_get = client.get
            resumed, reads = [False], [0]

            def change(kind, name, ns, patch):
                if kind == 'deployment' and patch[-1]['value'] == 1:
                    self.assertEqual('unknown', volume['status']['robustness'])
                    self.assertFalse(journal.record['writer_resumed_ready'])
                    resumed[0] = True
                return original_change(kind, name, ns, patch)

            def get(kind, name=None, namespace=None):
                if kind == 'volumes.longhorn.io' and resumed[0]:
                    reads[0] += 1
                    self.assertFalse(journal.record['writer_resumed_ready'])
                    if reads[0] >= 3:
                        volume['status'].update(state='attached', robustness='healthy')
                return original_get(kind, name, namespace)

            with mock.patch.object(client, 'get', side_effect=get), mock.patch.object(client, 'change', side_effect=change):
                operation.resume()
            self.assertGreaterEqual(reads[0], 3)
            self.assertTrue(journal.record['writer_resumed_ready'])
            self.assertEqual('healthy', volume['status']['robustness'])

    def test_faulted_deleting_drifting_or_foreign_storage_blocks_resume(self):
        for change in ('faulted', 'attached-unknown', 'error-unknown', 'missing-state',
                       'claim-delete', 'pv-delete', 'volume-delete', 'uid', 'mapping', 'alias'):
            client, journal, operation = fixtures.prepared()
            volume = client.resources['volumes.longhorn.io']
            volume['status'].update(state='detached', robustness='unknown')
            if change == 'faulted': volume['status']['robustness'] = 'faulted'
            elif change == 'attached-unknown': volume['status']['state'] = 'attached'
            elif change == 'error-unknown': volume['status']['state'] = 'error'
            elif change == 'missing-state': del volume['status']['state']
            elif change.endswith('-delete'):
                key = {'claim-delete':'pvc', 'pv-delete':'pv', 'volume-delete':'volumes.longhorn.io'}[change]
                client.resources[key]['metadata']['deletionTimestamp'] = 'public-fixture'
            elif change == 'uid': volume['metadata']['uid'] = 'replacement'
            elif change == 'mapping': client.resources['pv']['spec']['claimRef']['uid'] = 'other'
            else:
                foreign = copy.deepcopy(client.resources['pvs']['items'][0])
                foreign['metadata'].update(name='foreign-pv', uid='foreign-pv-uid')
                client.resources['pvs']['items'].append(foreign)
            with self.subTest(change=change), self.assertRaises(RuntimeError): operation.resume()
            self.assertEqual([], client.calls)
            self.assertFalse(journal.record['writer_resumed_ready'])

    def test_unknown_storage_never_qualifies_ready_or_backup(self):
        client, journal, operation = fixtures.prepared()
        client.resources['volumes.longhorn.io']['status'].update(state='detached', robustness='unknown')
        self.assertFalse(operation.writer_ready())
        with self.assertRaises(RuntimeError): operation.resume()
        self.assertFalse(journal.record['writer_resumed_ready'])
        client, journal, operation = fixtures.prepared()
        original = client.create
        def create(body, dry_run=False):
            obj = original(body, dry_run)
            if body['kind'] == 'Backup':
                client.resources['volumes.longhorn.io']['status'].update(state='detaching', robustness='unknown')
            return obj
        with mock.patch.object(client, 'create', side_effect=create), self.assertRaises(RuntimeError): operation.capture()
        self.assertFalse(journal.record['encrypted_nas_backup_complete'])
        self.assertNotIn('completed_at_utc', journal.record)

    def test_holder_runtime_digest_and_running_state_refusals(self):
        client, journal, operation = fixtures.prepared()
        operation.create_owned('holder', journal.record['holder_proposal'])
        original = copy.deepcopy(client.resources['pods']['items'][-1])
        self.assertEqual('registry.example/bortus:release-fixture', operation.holder()['status']['containerStatuses'][0]['image'])
        for change in ('missing', 'wrong', 'config', 'pullable', 'alias', 'restart', 'mixed-state', 'ready', 'extra'):
            pod = copy.deepcopy(original); status = pod['status']['containerStatuses'][0]
            if change == 'missing': status.pop('imageID')
            elif change == 'wrong': status['imageID'] = fixtures.IMAGE[:-1] + 'b'
            elif change == 'config': status['imageID'] = 'sha256:' + 'a'*64
            elif change == 'pullable': status['imageID'] = 'docker-pullable://' + fixtures.IMAGE
            elif change == 'alias': status['imageID'] = fixtures.IMAGE.replace('registry.example','other.example')
            elif change == 'restart': status['restartCount'] = 1
            elif change == 'mixed-state': status['state']['terminated'] = {}
            elif change == 'ready': status['ready'] = False
            else: pod['status']['containerStatuses'].append(copy.deepcopy(status))
            client.resources['pods']['items'][-1] = pod
            with self.subTest(change=change), self.assertRaises(RuntimeError): operation.holder()

    def test_absence_requires_both_name_and_uid_in_complete_list(self):
        for same in ('name', 'uid', 'incomplete'):
            client, journal, operation = fixtures.prepared()
            operation.create_owned('holder', journal.record['holder_proposal'])
            original = client.delete_holder
            def delete(holder):
                result = original(holder)
                if same == 'incomplete': client.resources['pods']['metadata']['continue'] = 'opaque-next'
                else:
                    foreign = copy.deepcopy(holder)
                    foreign['spec']['volumes'] = []
                    foreign['status']['phase'] = 'Succeeded'
                    foreign['metadata'].update(name='other-pod' if same == 'uid' else holder['metadata']['name'],
                                               uid='other-uid' if same == 'name' else holder['metadata']['uid'])
                    client.resources['pods']['items'].append(foreign)
                return result
            with mock.patch.object(client, 'delete_holder', side_effect=delete), self.assertRaises(RuntimeError): operation.release_holder()
            self.assertNotIn('owned_holder_removed', journal.record)
            self.assertEqual('confirmed', journal.record['holder_delete_intent']['state'])
            with self.assertRaises(RuntimeError): operation.release_holder()
            self.assertEqual(1, sum(c[0] == 'delete-holder' for c in client.calls))

    def test_ambiguous_delete_and_capture_are_never_replayed(self):
        client, journal, operation = fixtures.prepared(CrossNodeClient())
        original = client.delete_holder
        def delete(holder):
            original(holder)
            raise RuntimeError('private-delete-fixture')
        with mock.patch.object(client, 'delete_holder', side_effect=delete), self.assertRaises(RuntimeError): operation.capture()
        self.assertTrue(journal.record['writer_resumed_ready'])
        self.assertEqual('uncertain', journal.record['holder_delete_intent']['state'])
        self.assertFalse(journal.record['encrypted_nas_backup_complete'])
        self.assertNotIn('private-delete-fixture', json.dumps(journal.record))
        calls = copy.deepcopy(client.calls)
        with self.assertRaises(RuntimeError): operation.capture()
        self.assertEqual(calls, client.calls)
        with self.assertRaises(RuntimeError): operation.delete_owned_holder()
        self.assertEqual(calls, client.calls)

    def test_archive_failure_still_releases_before_cross_node_restoration(self):
        client, journal, operation = fixtures.prepared(CrossNodeClient())
        def archive(_): raise RuntimeError('public synthetic archive refusal')
        operation.archive = archive
        with self.assertRaises(RuntimeError): operation.capture()
        self.assertTrue(journal.record['writer_resumed_ready'])
        self.assertTrue(journal.record['owned_holder_removed'])
        self.assertFalse(journal.record['cold_snapshot_ready'])
        self.assertFalse(any(c[:2] == ('create','Backup') for c in client.calls))

    def test_complete_pod_inventory_refuses_truncation_malformed_and_duplicates(self):
        original = fixtures.fixtures.fixture()[4]
        self.assertEqual(1, len(module.preflight.complete_pods(copy.deepcopy(original))))
        empty = copy.deepcopy(original); empty['items'] = []
        self.assertEqual([], module.preflight.complete_pods(empty))
        for change in ('api', 'kind', 'metadata', 'rv', 'cursor', 'remaining', 'missing-items', 'overbound',
                       'duplicate-name', 'duplicate-uid', 'foreign-namespace', 'bad-kind', 'bad-phase', 'bad-pvc'):
            obj = copy.deepcopy(original)
            if change == 'api': obj['apiVersion'] = 'other'
            elif change == 'kind': obj['kind'] = 'List'
            elif change == 'metadata': del obj['metadata']
            elif change == 'rv': obj['metadata']['resourceVersion'] = ''
            elif change == 'cursor': obj['metadata']['continue'] = 'more'
            elif change == 'remaining': obj['metadata']['remainingItemCount'] = 1
            elif change == 'missing-items': del obj['items']
            elif change == 'overbound': obj['items'] = obj['items'] * (module.preflight.MAX_POD_ITEMS + 1)
            elif change.startswith('duplicate'):
                other = copy.deepcopy(obj['items'][0])
                other['metadata']['uid' if change == 'duplicate-name' else 'name'] = 'different'
                obj['items'].append(other)
            elif change == 'foreign-namespace': obj['items'][0]['metadata']['namespace'] = 'other'
            elif change == 'bad-kind': obj['items'][0]['kind'] = 'Secret'
            elif change == 'bad-phase': del obj['items'][0]['status']['phase']
            else: obj['items'][0]['spec']['volumes'][0]['persistentVolumeClaim'] = False
            with self.subTest(change=change), self.assertRaises(RuntimeError): module.preflight.complete_pods(obj)

    def test_raw_pod_list_client_preserves_collection_and_refuses_incomplete(self):
        inventory = fixtures.fixtures.fixture()[4]
        result = mock.Mock(returncode=0, stdout=json.dumps(inventory).encode())
        client = module.preflight.Client()
        with mock.patch.object(module.preflight.subprocess, 'run', return_value=result) as called:
            self.assertEqual(inventory, client.get('pods', namespace='bortus'))
            argv = called.call_args.args[0]
            self.assertEqual(['--raw', '/api/v1/namespaces/bortus/pods?limit=10001'], argv[-2:])
            self.assertNotIn('-o', argv)
            for ns in ('other', None):
                with self.assertRaises(RuntimeError): client.get('pods', namespace=ns)
            inventory['metadata']['continue'] = 'opaque'
            result.stdout = json.dumps(inventory).encode()
            with self.assertRaises(RuntimeError): client.get('pods', namespace='bortus')
            result.stdout = b' ' * (8 * 1024 * 1024 + 1)
            with self.assertRaises(RuntimeError): client.get('pods', namespace='bortus')


    def test_exact_pod_bound_and_embedded_typemeta_omission(self):
        original = fixtures.fixtures.fixture()[4]
        pod = original['items'][0]
        pod.pop('apiVersion'); pod.pop('kind')
        self.assertEqual([pod], module.preflight.complete_pods(original))
        original['items'] = []
        for index in range(module.preflight.MAX_POD_ITEMS):
            item = copy.deepcopy(pod)
            item['metadata'].update(name='pod-' + str(index), uid='uid-' + str(index))
            original['items'].append(item)
        self.assertEqual(module.preflight.MAX_POD_ITEMS, len(module.preflight.complete_pods(original)))
        original['items'].append(copy.deepcopy(pod))
        with self.assertRaises(RuntimeError): module.preflight.complete_pods(original)
        for key in ('uid', 'name', 'resourceVersion'):
            obj = fixtures.fixtures.fixture()[4]
            obj['items'][0]['metadata'][key] = ''
            with self.subTest(key=key), self.assertRaises(RuntimeError): module.preflight.complete_pods(obj)


if __name__ == '__main__':
    unittest.main()
