import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HERE = pathlib.Path(__file__).resolve().parent
module = load('cold_checkpoint', HERE.parent / 'checkpoint-bortus-volume.py')
fixtures = load('preflight_fixtures', HERE / 'test_bortus_checkpoint_preflight.py')
IMAGE = 'registry.example/bortus@sha256:' + 'a' * 64


class MemoryJournal:
    def __init__(self, record):
        self.record = record
        self.saved = []

    def save(self):
        self.saved.append(copy.deepcopy(self.record))


class FakeClient:
    def __init__(self):
        self.objects = fixtures.fixture()
        self.resources = dict(zip(('pvc', 'pv', 'volumes.longhorn.io', 'deployment', 'pods',
                                  'helmrelease', 'kustomization', 'backuptargets.longhorn.io', 'replicaset'),
                                 self.objects))
        self.owned = {}
        self.calls = []
        self.sequence = 2
        self.stop_reads = 0
        self.fail_change = None
        self.fail_snapshot = False
        self.foreign_after_stop = False
        self.backup_url = None

    def inspect(self, uid, image):
        return module.preflight.evaluate(copy.deepcopy(self.objects), uid, image)

    def get(self, kind, name=None, namespace=None):
        if kind == 'pod':
            return copy.deepcopy(next(p for p in self.resources['pods']['items']
                                      if p['metadata']['name'] == name))
        if kind in ('snapshots.longhorn.io', 'backups.longhorn.io'):
            return copy.deepcopy(self.owned[name])
        if kind == 'pods' and self.stop_reads:
            self.stop_reads -= 1
            if self.stop_reads == 0:
                self.resources['pods']['items'] = [p for p in self.resources['pods']['items']
                                                  if p['metadata']['uid'] != 'writer-fixture-uid']
        return copy.deepcopy(self.resources[kind])

    def change(self, kind, name, ns, patch):
        obj = self.resources[kind]
        for op in patch:
            parent = obj
            path = op['path'].strip('/').split('/')
            for part in path[:-1]:
                parent = parent[part]
            if op['op'] == 'test':
                assert type(parent[path[-1]]) is type(op['value']) and parent[path[-1]] == op['value']
        value = patch[-1]['value']
        self.calls.append(('change', kind, name, value))
        fail = self.fail_change if self.fail_change and kind == self.fail_change[0] else None
        self.fail_change = None if fail else self.fail_change
        if fail and fail[1] == 'before':
            raise RuntimeError('PRIVATE_SYNTHETIC_API_FAILURE')
        obj['spec'][patch[-1]['path'].split('/')[-1]] = value
        obj['metadata']['resourceVersion'] = str(self.sequence)
        self.sequence += 1
        if kind == 'deployment':
            if value == 0:
                self.stop_reads = 2
                self.resources['pods']['items'][0]['metadata']['deletionTimestamp'] = 'fixture'
                if self.foreign_after_stop:
                    other = copy.deepcopy(self.resources['pods']['items'][0])
                    other['metadata']['uid'] = 'foreign-writer-uid'
                    self.resources['pods']['items'].append(other)
            else:
                writer = copy.deepcopy(fixtures.fixture()[4]['items'][0])
                writer['metadata']['uid'] = 'resumed-writer-uid'
                writer['metadata']['name'] = 'resumed-writer'
                self.resources['pods']['items'] = [p for p in self.resources['pods']['items']
                    if p['metadata']['uid'] not in ('writer-fixture-uid', 'resumed-writer-uid')] + [writer]
                self.stop_reads = 0
        if fail:
            raise RuntimeError('PRIVATE_SYNTHETIC_LOST_MUTATION_REPLY')
        return copy.deepcopy(obj)

    def create(self, body, dry_run=False):
        self.calls.append(('create', body['kind'], dry_run))
        obj = copy.deepcopy(body)
        obj['metadata'].update(uid=body['metadata']['name'] + '-uid', resourceVersion='1')
        if dry_run:
            return obj
        if body['kind'] == 'Pod':
            obj['status'] = {'phase': 'Running', 'conditions': [{'type': 'Ready', 'status': 'True'}]}
            obj['spec']['containers'][0].update(terminationMessagePath='/dev/termination-log',
                                               terminationMessagePolicy='File')
            self.resources['pods']['items'].append(obj)
        elif body['kind'] == 'Snapshot':
            assert self.resources['deployment']['spec']['replicas'] == 0
            assert all(p['metadata']['name'].startswith('bortus-cold-')
                       for p in self.resources['pods']['items'])
            if self.fail_snapshot:
                raise RuntimeError('PRIVATE_SNAPSHOT_REPLY_FAILURE')
            obj['status'] = {'readyToUse': True}
            self.owned[body['metadata']['name']] = obj
        else:
            obj['spec']['labels']['longhorn.io/volume-access-mode'] = 'rwo'
            obj['spec']['backupBlockSize'] = '2097152'
            obj['spec']['syncRequestedAt'] = 'fixture'
            obj['status'] = {'state': 'Completed', 'url':
                'cifs://192.168.0.8/container_backups/k8s-migration-20261009/longhorn?backup=' +
                body['metadata']['name'] + '&volume=pvc-fixture'}
            if self.backup_url is not None:
                obj['status']['url'] = self.backup_url
            self.owned[body['metadata']['name']] = obj
        return copy.deepcopy(obj)

    def delete_holder(self, obj):
        self.calls.append(('delete-holder', obj['metadata']['uid']))
        self.resources['pods']['items'] = [p for p in self.resources['pods']['items']
                                          if p['metadata']['uid'] != obj['metadata']['uid']]
        return {'kind': 'Status', 'status': 'Success'}


def prepared(client=None):
    client = client or FakeClient()
    expected = module.preflight.evaluate(copy.deepcopy(client.objects), 'bortus-data-uid')
    record = module.prepare(client, expected, IMAGE, '123456abcdef')
    journal = MemoryJournal(record)
    clock = [0]

    def sleep(seconds):
        clock[0] += seconds

    def simulated_archive(operation):
        assert operation.cold()
        return {'authenticated_decryption_equal': True, 'nas_ciphertext_equal': True,
                'plaintext_persisted': False, 'files': ['bortus.db'], 'synthetic_fixture': True}

    return client, journal, module.Checkpoint(client, journal, sleep, lambda: clock[0], simulated_archive)


class ColdCheckpointTests(unittest.TestCase):
    def test_cold_backup_restores_original_flags_without_unrelated_mutations(self):
        for initially_suspended in (False, True):
            client = FakeClient()
            if initially_suspended:
                client.resources['helmrelease']['spec']['suspend'] = True
                client.resources['kustomization']['spec']['suspend'] = True
            client, journal, operation = prepared(client)
            operation.capture()
            report = journal.record
            self.assertTrue(report['cold_snapshot_ready'])
            self.assertTrue(report['encrypted_nas_backup_complete'])
            self.assertTrue(report['writer_resumed_ready'])
            self.assertTrue(report['owned_holder_removed'])
            self.assertFalse(report['independent_restore_proven'])
            self.assertFalse(report['sqlite_preservation_proven'])
            self.assertTrue(report['database_byte_reads'])
            self.assertEqual(report['database_or_secret_reads'], 1)
            self.assertEqual(report['native_secret_reads'], 0)
            self.assertEqual(client.resources['deployment']['spec']['replicas'], 1)
            self.assertEqual(client.resources['helmrelease']['spec'].get('suspend', False), initially_suspended)
            self.assertEqual(client.resources['kustomization']['spec'].get('suspend', False), initially_suspended)
            changes = [c for c in client.calls if c[0] == 'change']
            self.assertTrue(all(c[1] in ('deployment', 'helmrelease', 'kustomization') for c in changes))
            self.assertEqual([c[3] for c in changes if c[1] == 'deployment'], [0, 1])
            self.assertNotIn('not-for-report', json.dumps(report))

    def test_expected_claim_pv_longhorn_and_writer_recreation_refused_before_mutation(self):
        for which in ('claim', 'pv', 'longhorn_volume', 'writer'):
            client = FakeClient()
            expected = module.preflight.evaluate(copy.deepcopy(client.objects), 'bortus-data-uid')
            if which == 'writer':
                expected['writer']['uid'] = 'other'
            else:
                expected['identities'][which]['uid'] = 'other'
            with self.subTest(which=which), self.assertRaises(RuntimeError):
                module.prepare(client, expected, IMAGE, '123456abcdef')
            self.assertEqual(client.calls, [])

    def test_cas_patch_rejects_recreation_type_and_control_drift(self):
        obj = fixtures.fixture()[3]
        expected = module.identity(obj)
        patch = module.cas_patch(obj, expected, 'replicas', 1, 0)
        self.assertEqual(patch[:2], [
            {'op': 'test', 'path': '/metadata/uid', 'value': 'bortus-uid'},
            {'op': 'test', 'path': '/metadata/resourceVersion', 'value': '1'}])
        self.assertEqual(patch[2]['path'], '/spec/replicas')
        for value in (True, '1', 2):
            bad = copy.deepcopy(obj)
            bad['spec']['replicas'] = value
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                module.cas_patch(bad, expected, 'replicas', 1, 0)
        bad = copy.deepcopy(obj)
        bad['metadata']['uid'] = 'recreated'
        with self.assertRaises(RuntimeError):
            module.cas_patch(bad, expected, 'replicas', 1, 0)

    def test_lost_stop_reply_is_not_replayed_and_restores_conditionally(self):
        for outcome in ('before', 'after'):
            client, journal, operation = prepared()
            client.fail_change = ('deployment', outcome)
            with self.subTest(outcome=outcome), self.assertRaises(RuntimeError):
                operation.capture()
            self.assertEqual([c for c in client.calls if c[0] == 'change' and
                              c[1] == 'deployment' and c[3] == 0], [('change', 'deployment', 'bortus', 0)])
            self.assertEqual(client.resources['deployment']['spec']['replicas'], 1)
            self.assertTrue(journal.record['writer_resumed_ready'])
            self.assertFalse(journal.record['cold_snapshot_ready'])
            self.assertFalse(journal.record['encrypted_nas_backup_complete'])
            self.assertTrue(any(s['controls']['deployment'].get('intent', {}).get('state') == 'uncertain'
                                for s in journal.saved))

    def test_ambiguous_snapshot_retains_holder_and_resumes_without_backup_creation(self):
        client, journal, operation = prepared()
        client.fail_snapshot = True
        with self.assertRaises(RuntimeError):
            operation.capture()
        self.assertEqual(journal.record['snapshot_create_state'], 'uncertain')
        self.assertTrue(journal.record['writer_resumed_ready'])
        self.assertFalse(any(c[:2] == ('create', 'Backup') for c in client.calls))
        self.assertFalse(any(c[0] == 'delete-holder' for c in client.calls))

    def test_failed_encrypted_archive_resumes_writer_without_snapshot_or_backup(self):
        client, journal, operation = prepared()

        def fail_archive(checkpoint):
            self.assertTrue(checkpoint.cold())
            raise RuntimeError('PRIVATE_TRANSFER_FAILURE')

        operation.archive = fail_archive
        with self.assertRaises(RuntimeError):
            operation.capture()
        self.assertEqual(journal.record['sqlite_archive_state'], 'pending')
        self.assertTrue(journal.record['writer_resumed_ready'])
        self.assertFalse(journal.record['database_byte_reads'])
        self.assertTrue(journal.record['database_byte_read_attempted'])
        self.assertIsNone(journal.record['database_or_secret_reads'])
        self.assertFalse(any(c[:2] in (('create', 'Snapshot'), ('create', 'Backup')) for c in client.calls))
        self.assertNotIn('PRIVATE_TRANSFER_FAILURE', json.dumps(journal.record))

    def test_foreign_consumer_blocks_capture_and_unsafe_resume(self):
        client, journal, operation = prepared()
        client.foreign_after_stop = True
        with self.assertRaises(RuntimeError):
            operation.capture()
        self.assertEqual(client.resources['deployment']['spec']['replicas'], 0)
        self.assertFalse(journal.record['cold_snapshot_ready'])
        self.assertFalse(journal.record['writer_resumed_ready'])
        self.assertFalse(any(c[:2] == ('create', 'Snapshot') for c in client.calls))

    def test_holder_defaults_allowed_but_credentials_and_recreated_uid_refused(self):
        client, journal, operation = prepared()
        operation.create_owned('holder', journal.record['holder_proposal'])
        original = copy.deepcopy(client.resources['pods']['items'][-1])
        self.assertEqual(operation.holder()['metadata']['uid'], original['metadata']['uid'])
        for change in ('env', 'identity', 'writable', 'root', 'helper'):
            holder = copy.deepcopy(original)
            if change == 'env':
                holder['spec']['containers'][0]['env'] = [{'name': 'PRIVATE', 'value': 'never-report'}]
            elif change == 'identity':
                holder['metadata']['uid'] = 'recreated'
            elif change == 'writable':
                holder['spec']['volumeMounts'] = []
                holder['spec']['containers'][0]['volumeMounts'][0]['readOnly'] = False
            elif change == 'root':
                holder['spec']['securityContext']['runAsUser'] = 0
            else:
                holder['spec']['ephemeralContainers'] = [{'name': 'unexpected'}]
            client.resources['pods']['items'][-1] = holder
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                operation.holder()
        self.assertNotIn('never-report', json.dumps(journal.record))

    def test_resume_refuses_new_deployment_and_untouched_flag_drift(self):
        for key in ('deployment', 'helmrelease'):
            client, journal, operation = prepared()
            if key == 'deployment':
                client.resources[key]['metadata']['uid'] = 'replacement'
            else:
                client.resources[key]['spec']['suspend'] = True
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                operation.resume()
            self.assertEqual(client.calls, [])

    def test_tag_scheme_and_incomplete_digest_refused(self):
        self.assertTrue(module.valid_digest(IMAGE))
        self.assertTrue(module.valid_digest('localhost:5000/team/bortus@sha256:' + 'a' * 64))
        for image in ('https://' + IMAGE, 'bortus:latest@sha256:' + 'a' * 64,
                      'bortus@sha256:' + 'a' * 63, IMAGE + '\n'):
            with self.subTest(image=image):
                self.assertFalse(module.valid_digest(image))

    def test_foreign_or_credential_bearing_backup_url_never_recorded_or_cleaned_up(self):
        prefix = 'cifs://192.168.0.8/container_backups/k8s-migration-20261009/longhorn'
        for url in (prefix + '?backup=other&volume=pvc-fixture',
                    prefix + '?backup=backup-123456abcdef&volume=pvc-fixture&token=PRIVATE_QUERY',
                    prefix.replace('192.168.0.8', 'user:PRIVATE_PASSWORD@192.168.0.8') +
                    '?backup=backup-123456abcdef&volume=pvc-fixture'):
            client, journal, operation = prepared()
            client.backup_url = url
            with self.subTest(url_class='invalid'), self.assertRaises(RuntimeError):
                operation.capture()
            self.assertTrue(journal.record['writer_resumed_ready'])
            self.assertFalse(journal.record['encrypted_nas_backup_complete'])
            self.assertNotIn('backup_url', journal.record)
            self.assertNotIn('PRIVATE_', json.dumps(journal.record))
            self.assertFalse(any(c[0] == 'delete-holder' for c in client.calls))

    def test_conditional_patch_and_delete_bodies_use_stdin_not_argv(self):
        client = module.Client()
        result = mock.Mock(returncode=0, stdout=b'{"kind":"Status","status":"Success"}')
        obj = {'metadata': fixtures.metadata('bortus-cold-123456abcdef', 'bortus')}
        body = [{'op': 'test', 'path': '/metadata/uid', 'value': 'PRIVATE_SENTINEL'}]
        with mock.patch.object(module.subprocess, 'run', return_value=result) as run:
            client.change('deployment', 'bortus', 'bortus', body)
            argv = run.call_args.args[0]
            self.assertNotIn('PRIVATE_SENTINEL', json.dumps(argv))
            self.assertEqual(json.loads(run.call_args.kwargs['input']), body)
            self.assertIn('--patch-file=/dev/stdin', argv)
            client.delete_holder(obj)
            self.assertIn('--raw', run.call_args.args[0])
            sent = json.loads(run.call_args.kwargs['input'])
            self.assertEqual(sent['preconditions'], {'uid': obj['metadata']['uid'], 'resourceVersion': '1'})

    def test_existing_run_or_process_lock_never_overwrites_retained_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / 'existing'
            path.mkdir()
            journal = path / 'journal.json'
            journal.write_text('{"retained":true}', encoding='utf-8')
            lock = path / 'active.lock'
            lock.write_text('other-process\n', encoding='ascii')
            new = module.Journal(path, {'replacement': True})
            with self.assertRaises(FileExistsError):
                new.open(new=True)
            with self.assertRaises(RuntimeError):
                new.save()
            new.close()
            reopened = module.Journal(path)
            with self.assertRaises(FileExistsError):
                reopened.open(new=False)
            reopened.close()
            self.assertEqual(journal.read_text(encoding='utf-8'), '{"retained":true}')
            self.assertEqual(lock.read_text(encoding='ascii'), 'other-process\n')


if __name__ == '__main__':
    unittest.main()
