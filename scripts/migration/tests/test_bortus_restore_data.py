"""Real disposable age/SQLite/tmpfs; only controlled API and Python reader callbacks."""
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import queue
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


m = load('restore_data_test_module', HERE.parent / 'bortus-restore-data.py')
fixtures = load('restore_data_metadata_fixture', HERE / 'test_bortus_restored_consumer_fence.py')
databases = load('restore_data_database_fixture', HERE / 'test_database_preservation.py')


class ControlledResponse:
    """No sockets/TLS proof: exercise the real Collector thread, proof and journal."""
    def __init__(self):
        self.frames = queue.Queue()
        self.closed = False

    def readline(self, cap):
        raw = self.frames.get(timeout=5)
        assert len(raw) <= cap
        return raw

    def close(self):
        if not self.closed:
            self.closed = True
            self.frames.put(b'')

    def send(self, obj, kind='MODIFIED'):
        self.frames.put(json.dumps({'type': kind, 'object': obj}).encode() + b'\n')


def frame(raw):
    def header(obj):
        data = json.dumps(obj).encode()
        return struct.pack('>I', len(data)) + data
    return m.archive.MAGIC + header({'name': 'bortus.db', 'size': len(raw)}) + raw + \
        header({'complete': True, 'files': ['bortus.db']})


@unittest.skipUnless(os.name == 'posix', 'Actual POSIX ownership, age and tmpfs required')
class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys = tempfile.TemporaryDirectory(prefix='bortus-data-public-key-')
        cls.key = pathlib.Path(cls.keys.name) / 'disposable-identity'
        cls.age = pathlib.Path.home() / '.local/share/branconet-migration/bin/age'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(cls.key)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)

    @classmethod
    def tearDownClass(cls):
        cls.keys.cleanup()

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='bortus-data-public-fixture-')
        self.root = pathlib.Path(self.folder.name)
        self.tmpfs_before = set(pathlib.Path('/dev/shm').glob('bortus-sqlite-*'))
        self.children = []
        self.cleanup_reports = []
        self.e, self.o = fixtures.fixture()
        self.name = 'bortus-restore-123456abcdef'
        self.e['claim']['name'] = self.e['holder']['name'] = self.name
        self.o['claim']['metadata']['name'] = self.name
        self.o['claim']['spec']['storageClassName'] = self.name
        self.o['pv']['spec']['claimRef']['name'] = self.name
        self.o['pvs']['items'][0] = copy.deepcopy(self.o['pv'])
        pod = self.o['pods']['items'][0]
        pod['metadata']['name'] = self.name
        pod['spec']['volumes'][0]['persistentVolumeClaim']['claimName'] = self.name
        self.journal = m.watch.WatchJournal(self.root / 'run').open(
            m.watch.ownership.seed('123456abcdef', 'a' * 64, 'b' * 64))
        src = m.watch.Source(self.e['backup_url'], m.watch.completion.BackupIdentity(
            'backup', 'longhorn-system', self.e['backup']['uid'], 'backup-rv'),
            self.e['original_volume']['uid'], 'original-volume', self.e['original_pv']['uid'],
            self.e['original_claim']['uid'])
        self.response = ControlledResponse()
        api = m.watch.TLSAPI('https://localhost:6443', lambda: None)
        api.list_page = lambda *_: ({'apiVersion': m.health.API, 'kind': 'VolumeList',
            'metadata': {'resourceVersion': 'opaque/list:rv', 'continue': ''}, 'items': []}, 128)
        api.open_watch = lambda *_: (self.response, self.response)
        self.collector = m.watch.Collector(self.journal, api, src).start()

        def mutation(kind, expected):
            def callback(_):
                return {'kind': kind, 'metadata': dict(expected, resourceVersion='create-rv',
                    labels={'bortus-restore': '123456abcdef'})}
            return callback
        self.collector.perform_create('storageclass_create', mutation('StorageClass',
            dict(name=self.name, namespace=None, uid=fixtures.meta('sc', 99)['uid'])), lambda _: None)
        self.collector.perform_create('claim_create', mutation('PersistentVolumeClaim', self.e['claim']), lambda _: None)
        start = copy.deepcopy(self.o['volume'])
        start['metadata']['resourceVersion'] = 'z-first'
        start['status']['restoreRequired'] = True
        self.response.send(start)
        self.response.send(self.o['volume'])
        self.wait(lambda: self.collector.state['sequence'] == 2)
        self.collector.bind_target(self.o['claim'], self.o['pv'], self.o['volume'])
        self.collector.seal(self.o['volume'])
        self.collector.perform_create('holder_create', mutation('Pod', self.e['holder']), lambda _: None)
        self.db = self.root / 'public-fixture.db'
        databases.database(self.db)
        self.frames = self.root / 'public-framing.bin'
        self.frames.write_bytes(frame(self.db.read_bytes()))
        self.original = self.root / 'original.age'
        with self.original.open('wb') as out:
            subprocess.run([str(self.age), '-R', str(self.key) + '.pub'], input=self.frames.read_bytes(),
                stdout=out, stderr=subprocess.DEVNULL, check=True, timeout=5)
        self.original.chmod(0o600)
        self.digest = hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.producer = self.root / 'public-reader-fixture.py'
        self.producer.write_text('''import pathlib,sys
expected = pathlib.Path(sys.argv[1]).read_bytes()
if sys.stdin.buffer.read() != expected: sys.exit(7)
sys.stdout.buffer.write(pathlib.Path(sys.argv[2]).read_bytes())
''')
        self.reader = self.root / 'exact-node-reader.txt'
        self.reader.write_bytes(m.archive.NODE_READER.encode())
        self.deadline = time.monotonic() + 30

    def tearDown(self):
        # A test that deliberately refused cleanup retains the copy until this exact cleanup.
        for report in self.cleanup_reports:
            if pathlib.Path(report['temporary_directory']).exists():
                m.normalization.cleanup(report['temporary_directory'], report['temporary_directory_identity'])
        for child in self.children:
            m.archive.stop_owned(child)
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream and not stream.closed:
                    stream.close()
            self.assertIsNotNone(child.poll())
        self.collector.close()
        self.assertFalse(self.collector.thread.is_alive())
        self.assertTrue(self.response.closed)
        self.journal.close()
        self.folder.cleanup()
        self.assertEqual(self.tmpfs_before, set(pathlib.Path('/dev/shm').glob('bortus-sqlite-*')))

    def wait(self, predicate):
        until = time.monotonic() + 2
        while not predicate():
            if time.monotonic() >= until:
                self.fail('Controlled collector timeout')
            time.sleep(.005)

    def source_fence(self, deadline):
        self.assertEqual(deadline, self.deadline)
        ids = [m.health.Identity(**dict(self.e[k], resource_version='fresh/source:rv'))
               for k in ('original_claim', 'original_pv', 'original_volume', 'backup')]
        return m.SourceSnapshot('a' * 64, self.digest, *ids)

    def read_metadata(self, deadline):
        self.assertEqual(deadline, self.deadline)
        return copy.deepcopy(self.o)

    def launch(self, identity, deadline):
        self.assertEqual(identity.name, self.name)
        self.assertEqual(deadline, self.deadline)
        disk = json.loads((self.journal.directory / 'data.json').read_text())
        self.assertEqual(disk['state'], 'pending')
        self.assertIsNotNone(disk['source_before'])
        child = subprocess.Popen([sys.executable, '-B', str(self.producer), str(self.reader), str(self.frames)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.children.append(child)
        return child

    def run_step(self, **changes):
        options = dict(age=self.age, recipient_file=str(self.key) + '.pub', identity_file=self.key,
            source_fence=self.source_fence, read_metadata=self.read_metadata,
            launch_reader=self.launch, deadline=self.deadline)
        options.update(changes)
        return m.execute(self.collector, self.e, self.original, self.digest, **options)

    def disk(self):
        return json.loads((self.journal.directory / 'data.json').read_text())

    def refused(self, **changes):
        with self.assertRaises(m.DataRefused) as caught:
            self.run_step(**changes)
        self.assertNotIn('PRIVATE', str(caught.exception))
        if (self.journal.directory / 'data.json').stat().st_size:
            self.assertNotEqual(self.disk()['state'], 'confirmed')
        return caught.exception.code

    def test_real_encryption_both_auth_normalizations_full_rows_and_independent_cleanup(self):
        calls = []
        original_normalize = m.normalization.normalize
        original_compare = m.comparison.compare
        original_encrypt = m.archive.encrypt_source
        stop = m.archive.stop_owned
        normalization_stop = m.normalization.archive.stop_owned
        owned = []
        def closed(process):
            if process is not None:
                owned.append(process)
            return stop(process)
        def normalized_closed(process):
            if process is not None:
                owned.append(process)
            return normalization_stop(process)
        def normalize(*args, **kwargs):
            calls.append(('normalize', kwargs['deadline']))
            return original_normalize(*args, **kwargs)
        def compare(*args, **kwargs):
            calls.append(('compare', kwargs['deadline'], args[2]))
            return original_compare(*args, **kwargs)
        def encrypt(*args, **kwargs):
            calls.append(('capture', args[-1], kwargs['directory_fd']))
            return original_encrypt(*args, **kwargs)
        with mock.patch.object(m.normalization, 'normalize', side_effect=normalize), \
                mock.patch.object(m.comparison, 'compare', side_effect=compare), \
                mock.patch.object(m.archive, 'encrypt_source', side_effect=encrypt), \
                mock.patch.object(m.archive, 'stop_owned', side_effect=closed), \
                mock.patch.object(m.normalization.archive, 'stop_owned', side_effect=normalized_closed):
            result = self.run_step()
        self.assertTrue(result.recovery_rows_equal and result.exact_tmpfs_copies_cleaned)
        self.assertFalse(result.overall_live_restore_acceptance or result.image_runtime_admission_acceptance)
        self.assertEqual(calls, [('capture', self.deadline, self.journal.fd),
            ('normalize', self.deadline), ('normalize', self.deadline), ('compare', self.deadline, 'recovery')])
        self.assertEqual(self.disk()['tmpfs_cleanup'], [True, True])
        self.assertEqual(self.disk()['state'], 'confirmed')
        raw = (self.journal.directory / 'data.json').read_text()
        for private in (databases.PRIVATE, self.digest, 'cifs://', '192.0.2.', '/dev/shm', 'passwordHash'):
            self.assertNotIn(private, raw)
        self.assertEqual({'storageclass_create', 'claim_create', 'holder_create'},
            set(self.journal.record['operations']))
        self.assertTrue(self.collector.thread.is_alive())
        self.collector.prerequisite()  # Borrowed watch remains available for later deletion.
        self.assertTrue(all(p.poll() == 0 and p.stdin.closed and p.stdout.closed for p in self.children))
        self.assertEqual(len({p.pid for p in owned}), 5)
        self.assertTrue(all(p.poll() == 0 and all(s is None or s.closed
            for s in (p.stdin, p.stdout, p.stderr)) for p in owned))

    def test_full_row_multiplicity_difference_refuses_after_both_cleanups(self):
        with sqlite3.connect(self.db) as db:
            db.execute('DELETE FROM variables WHERE rowid=(SELECT min(rowid) FROM variables)')
        self.frames.write_bytes(frame(self.db.read_bytes()))
        self.assertEqual(self.refused(), 'comparison')
        self.assertEqual(self.disk()['tmpfs_cleanup'], [True, True])

    def test_invalid_boolean_source_callback_refuses_before_reader(self):
        launch = mock.Mock()
        self.assertEqual(self.refused(source_fence=lambda _: True, launch_reader=launch), 'source')
        launch.assert_not_called()

    def test_checkpoint_ciphertext_and_source_uid_bindings_refuse(self):
        snapshot = self.source_fence(self.deadline)._replace(original_ciphertext_sha256='0' * 64)
        self.assertEqual(self.refused(source_fence=lambda _: snapshot), 'source')
        self.assertEqual(len(self.children), 0)

    def test_wrong_checkpoint_journal_binding_refuses_before_capture(self):
        snapshot = self.source_fence(self.deadline)._replace(checkpoint_journal_sha256='0' * 64)
        self.assertEqual(self.refused(source_fence=lambda _: snapshot), 'source')
        self.assertEqual(self.children, [])

    def test_source_uid_drift_after_capture_refuses_and_keeps_holder(self):
        count = 0
        def source(deadline):
            nonlocal count
            count += 1
            result = self.source_fence(deadline)
            return result if count == 1 else result._replace(volume=result.volume._replace(uid=fixtures.meta('x', 88)['uid']))
        self.assertEqual(self.refused(source_fence=source), 'source')
        self.assertEqual(self.disk()['tmpfs_cleanup'], [])
        self.assertNotIn('holder_delete', self.journal.record['operations'])

    def test_valid_health_engine_identity_change_is_not_adopted(self):
        count = 0
        def metadata(deadline):
            nonlocal count
            count += 1
            objects = self.read_metadata(deadline)
            if count > 1:
                objects['engines']['items'][0]['metadata']['uid'] = fixtures.meta('x', 80)['uid']
            return objects
        self.assertEqual(self.refused(read_metadata=metadata), 'identity_drift')

    def test_watch_drain_continues_during_long_launch_callback(self):
        def launch(identity, deadline):
            prior = self.collector.state['sequence']
            self.response.send({'apiVersion': m.health.API, 'kind': 'Volume',
                'metadata': {'resourceVersion': 'bookmark-forward'}}, 'BOOKMARK')
            self.wait(lambda: self.collector.state['sequence'] > prior)
            return self.launch(identity, deadline)
        self.run_step(launch_reader=launch)
        self.assertEqual(self.disk()['watch_after']['sequence'], 3)

    def test_watch_error_after_capture_refuses_fixed_metadata_and_closes_source(self):
        original = m.archive.encrypt_source
        def captured(*args, **kwargs):
            result = original(*args, **kwargs)
            self.response.send({'message': 'PRIVATE_CONTROLLER_ERROR'}, 'ERROR')
            self.wait(lambda: self.collector.state['failure'] is not None)
            return result
        with mock.patch.object(m.archive, 'encrypt_source', side_effect=captured):
            self.refused()
        self.assertEqual(self.disk()['tmpfs_cleanup'], [])
        self.assertNotIn('PRIVATE_CONTROLLER_ERROR', json.dumps(self.disk()))
        self.assertIsNotNone(self.children[0].poll())

    def test_watch_eof_after_comparison_refuses_after_both_cleanups(self):
        original = m.comparison.compare
        def compared(*args, **kwargs):
            result = original(*args, **kwargs)
            self.response.close()
            self.wait(lambda: self.collector.state['failure'] is not None)
            return result
        with mock.patch.object(m.comparison, 'compare', side_effect=compared):
            self.refused()
        self.assertEqual(self.disk()['tmpfs_cleanup'], [True, True])

    def test_second_normalization_failure_cleans_first_successful_copy(self):
        original = m.normalization.normalize
        calls = 0
        def normalize(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError('PRIVATE_FAILURE')
            return original(*args, **kwargs)
        with mock.patch.object(m.normalization, 'normalize', side_effect=normalize):
            self.assertEqual(self.refused(), 'normalization')
        self.assertEqual(self.disk()['tmpfs_cleanup'], [True])

    def test_actual_age_authentication_failure_refuses_without_plaintext_leak(self):
        self.original.write_bytes(self.original.read_bytes()[:-16])
        self.digest = hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.assertEqual(self.refused(), 'normalization')
        self.assertEqual(self.disk()['tmpfs_cleanup'], [])

    def test_incomplete_reader_frame_closes_owned_source_and_retains_partial(self):
        self.frames.write_bytes(self.frames.read_bytes()[:-3])
        self.assertEqual(self.refused(), 'capture')
        self.assertIsNotNone(self.children[0].poll())
        self.assertTrue(self.children[0].stdout.closed and self.children[0].stdin.closed)
        self.assertTrue((self.journal.directory / m.ARCHIVE_NAME).is_file())
        self.assertEqual(self.disk()['tmpfs_cleanup'], [])

    def test_nonzero_source_exit_refuses_even_complete_frame(self):
        self.producer.write_text(self.producer.read_text() + '\nsys.exit(7)\n')
        self.assertEqual(self.refused(), 'capture')
        self.assertEqual(self.children[0].poll(), 7)
        self.assertEqual(self.disk()['tmpfs_cleanup'], [])

    def test_first_cleanup_refusal_still_attempts_exact_second_cleanup(self):
        original = m.normalization.normalize
        cleanup = m.normalization.cleanup
        calls = []
        def normalize(*args, **kwargs):
            report = original(*args, **kwargs)
            self.cleanup_reports.append(report)
            return report
        def clean(folder, identity):
            calls.append(folder)
            if len(calls) == 1:
                raise RuntimeError('PRIVATE_CLEANUP_ERROR')
            return cleanup(folder, identity)
        with mock.patch.object(m.normalization, 'normalize', side_effect=normalize), \
                mock.patch.object(m.normalization, 'cleanup', side_effect=clean):
            self.assertEqual(self.refused(), 'cleanup')
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.disk()['tmpfs_cleanup'], [False, True])
        self.assertTrue(pathlib.Path(calls[0]).exists())
        self.assertFalse(pathlib.Path(calls[1]).exists())

    def test_fresh_source_checked_again_after_cleanup_before_confirmation(self):
        original = m.normalization.cleanup
        cleaned = 0
        def cleanup(*args):
            nonlocal cleaned
            result = original(*args)
            cleaned += 1
            return result
        def source(deadline):
            result = self.source_fence(deadline)
            return result if cleaned < 2 else result._replace(checkpoint_journal_sha256='c' * 64)
        with mock.patch.object(m.normalization, 'cleanup', side_effect=cleanup):
            self.assertEqual(self.refused(source_fence=source), 'source')
        self.assertEqual(self.disk()['tmpfs_cleanup'], [True, True])

    def test_actual_collector_failure_during_cleanup_prevents_confirmation(self):
        original = m.normalization.cleanup
        count = 0
        def cleanup(*args):
            nonlocal count
            result = original(*args)
            count += 1
            if count == 2:
                self.response.close()
                self.wait(lambda: self.collector.state['failure'] is not None)
            return result
        with mock.patch.object(m.normalization, 'cleanup', side_effect=cleanup):
            self.assertEqual(self.refused(), 'prerequisite')
        self.assertEqual(self.disk()['tmpfs_cleanup'], [True, True])

    def test_private_final_callback_error_has_no_public_exception_context(self):
        original = m.normalization.cleanup
        count = 0
        def cleanup(*args):
            nonlocal count
            result = original(*args)
            count += 1
            return result
        def source(deadline):
            if count == 2:
                raise RuntimeError('PRIVATE_FINAL_CALLBACK_VALUE')
            return self.source_fence(deadline)
        with mock.patch.object(m.normalization, 'cleanup', side_effect=cleanup):
            try:
                self.run_step(source_fence=source)
            except m.DataRefused as error:
                self.assertEqual(error.code, 'source')
                self.assertIsNone(error.__context__)
                self.assertIsNone(error.__cause__)
                self.assertNotIn('PRIVATE_FINAL_CALLBACK_VALUE', str(error))
            else:
                self.fail('Expected fixed final callback refusal')
        self.assertEqual(self.disk()['state'], 'refused')
        self.assertEqual(self.disk()['tmpfs_cleanup'], [True, True])

    def test_expired_deadline_and_false_collector_never_launch(self):
        launch = mock.Mock()
        with self.assertRaises(m.DataRefused):
            self.run_step(deadline=time.monotonic() - 1, launch_reader=launch)
        launch.assert_not_called()
        self.assertFalse((self.journal.directory / 'data.json').exists())
        with self.assertRaises(m.DataRefused):
            m.execute(True, self.e, self.original, self.digest, age=self.age,
                recipient_file=self.key, identity_file=self.key, source_fence=lambda _: True,
                read_metadata=lambda _: {}, launch_reader=launch, deadline=self.deadline)

    def test_existing_sidecar_refuses_replay_without_launch(self):
        self.run_step()
        before = (self.journal.directory / 'data.json').read_bytes()
        launch = mock.Mock()
        with self.assertRaises(m.DataRefused):
            self.run_step(launch_reader=launch)
        launch.assert_not_called()
        self.assertEqual(before, (self.journal.directory / 'data.json').read_bytes())

    def test_pending_flush_failure_prevents_reader_launch_and_keeps_unaccepted_record(self):
        fsync = os.fsync
        calls = 0
        def fail(fd):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError('PRIVATE_FSYNC')
            return fsync(fd)
        launch = mock.Mock()
        with mock.patch.object(m.os, 'fsync', side_effect=fail), self.assertRaises(m.DataRefused):
            self.run_step(launch_reader=launch)
        launch.assert_not_called()
        self.assertTrue((self.journal.directory / 'data.json').exists())

    def test_pending_directory_flush_failure_refuses_before_reader(self):
        fsync = os.fsync
        launch = mock.Mock()
        def fail(fd):
            if fd == self.journal.fd:
                raise OSError('PRIVATE_DIRECTORY_FSYNC')
            return fsync(fd)
        with mock.patch.object(m.os, 'fsync', side_effect=fail), self.assertRaises(m.DataRefused):
            self.run_step(launch_reader=launch)
        launch.assert_not_called()
        self.assertEqual(self.disk()['state'], 'pending')

    def test_final_actual_file_flush_fault_refuses_after_both_cleanups(self):
        fsync = os.fsync
        def fail(fd):
            if os.fstat(fd).st_mode & 0o170000 == 0o100000:
                raw = pathlib.Path('/proc/self/fd/' + str(fd)).read_bytes()
                if b'"state":"confirmed"' in raw:
                    raise OSError('PRIVATE_FINAL_FSYNC')
            return fsync(fd)
        with mock.patch.object(m.os, 'fsync', side_effect=fail):
            self.assertEqual(self.refused(), 'durability')
        self.assertEqual(self.disk()['tmpfs_cleanup'], [True, True])

    def test_final_directory_flush_failure_retains_refused_identity_not_confirmed(self):
        fsync = os.fsync
        def fail(fd):
            if fd == self.journal.fd and self.disk()['state'] == 'confirmed':
                raise OSError('PRIVATE_FINAL_DIRECTORY_FSYNC')
            return fsync(fd)
        with mock.patch.object(m.os, 'fsync', side_effect=fail), self.assertRaises(m.DataRefused):
            self.run_step()
        self.assertEqual(self.disk()['state'], 'refused')
        self.assertIs(self.disk()['recovery_rows_equal'], False)
        self.assertEqual(self.disk()['tmpfs_cleanup'], [True, True])

    def test_final_save_failure_cannot_return_acceptance(self):
        save = m.Sidecar.save
        def fail(sidecar):
            if sidecar.state['state'] == 'confirmed':
                raise OSError('PRIVATE_FINAL_FLUSH')
            return save(sidecar)
        with mock.patch.object(m.Sidecar, 'save', fail):
            self.assertEqual(self.refused(), 'durability')
        self.assertEqual(self.disk()['tmpfs_cleanup'], [True, True])

    def test_sidecar_inode_substitution_refuses_without_adopting_replacement(self):
        def metadata(deadline):
            objects = self.read_metadata(deadline)
            target = self.journal.directory / 'data.json'
            target.rename(self.journal.directory / 'retained-original-data.json')
            target.write_bytes(b'PUBLIC_FOREIGN_RECORD')
            target.chmod(0o600)
            return objects
        with self.assertRaises(m.DataRefused):
            self.run_step(read_metadata=metadata)
        self.assertEqual((self.journal.directory / 'data.json').read_bytes(), b'PUBLIC_FOREIGN_RECORD')
        self.assertEqual(self.children, [])

    def test_ciphertext_replacement_after_comparison_cannot_confirm(self):
        original = m.comparison.compare
        def replace(*args, **kwargs):
            result = original(*args, **kwargs)
            target = self.journal.directory / m.ARCHIVE_NAME
            target.rename(self.journal.directory / 'retained-restored.age')
            target.write_bytes(b'PUBLIC_SUBSTITUTION')
            target.chmod(0o600)
            return result
        with mock.patch.object(m.comparison, 'compare', side_effect=replace):
            self.assertEqual(self.refused(), 'ownership')
        self.assertEqual(self.disk()['tmpfs_cleanup'], [True, True])

    def test_sidecar_closed_schema_refuses_extra_private_fields(self):
        sidecar = m.Sidecar(self.collector)
        sidecar.state['raw'] = 'PRIVATE_RAW_BODY'
        with self.assertRaises(m.DataRefused):
            sidecar.save()
        self.assertNotIn('PRIVATE_RAW_BODY', json.dumps(self.disk()))


if __name__ == '__main__':
    unittest.main()
