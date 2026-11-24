import importlib.util
import json
import os
import pathlib
import stat
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('restore_journal', HERE.parent / 'bortus-restore-journal.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
RUN = '123456abcdef'
NAME = 'bortus-restore-' + RUN


def result(kind='Pod', rv='12'):
    return {'kind': kind, 'metadata': {'name': NAME,
            'namespace': None if kind == 'StorageClass' else 'bortus',
            'uid': 'public-owned-uid', 'resourceVersion': rv,
            'labels': {'bortus-restore': RUN}}, 'data': {'private': 'PRIVATE_API_VALUE'}}


def seed():
    return module.seed(RUN, 'a' * 64, 'b' * 64)


@unittest.skipUnless(os.name == 'posix', 'Production journal requires POSIX inode/no-follow semantics')
class RestoreJournalTests(unittest.TestCase):
    def test_pending_durable_before_api_metadata_only_confirmed_and_no_replay(self):
        with tempfile.TemporaryDirectory() as parent:
            directory = pathlib.Path(parent) / RUN
            journal = module.Journal(directory).open(seed())
            original_fsync = os.fsync
            synced = []

            def fsync(fd):
                synced.append(stat.S_ISDIR(os.fstat(fd).st_mode))
                return original_fsync(fd)

            def mutate(intent):
                disk = json.loads((directory / 'journal.json').read_text())
                self.assertEqual(disk['operations']['holder_create']['state'], 'pending')
                self.assertIn(False, synced)
                self.assertIn(True, synced)
                self.assertNotIn('identity', intent)
                return result()

            try:
                with mock.patch.object(module.os, 'fsync', side_effect=fsync):
                    entry = journal.perform('holder_create', mutate, lambda reply: None)
                self.assertEqual(entry['identity']['uid'], 'public-owned-uid')
                self.assertEqual(entry['state'], 'confirmed')
                self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE((directory / 'journal.json').stat().st_mode), 0o600)
                self.assertNotIn('PRIVATE_', (directory / 'journal.json').read_text())
                self.assertFalse(journal.record['independent_restore_proven'])
            finally:
                journal.close()
            reopened = module.Journal(directory).open()
            try:
                mutate = mock.Mock()
                with self.assertRaises(RuntimeError):
                    reopened.perform('holder_create', mutate, lambda reply: None)
                mutate.assert_not_called()
            finally:
                reopened.close()

    def test_lost_reply_persisted_uncertain_and_cannot_adopt_same_name(self):
        with tempfile.TemporaryDirectory() as parent:
            directory = pathlib.Path(parent) / RUN
            journal = module.Journal(directory).open(seed())
            calls = []

            def applied_then_lost(intent):
                calls.append(intent['name'])
                raise TimeoutError('PRIVATE_API_VALUE')

            try:
                with self.assertRaisesRegex(RuntimeError, 'outcome unresolved') as error:
                    journal.perform('claim_create', applied_then_lost, lambda reply: None)
                self.assertNotIn('PRIVATE_', str(error.exception))
                disk = json.loads((directory / 'journal.json').read_text())
                self.assertEqual(disk['operations']['claim_create']['state'], 'uncertain')
                self.assertNotIn('identity', disk['operations']['claim_create'])
            finally:
                journal.close()
            reopened = module.Journal(directory).open()
            try:
                with self.assertRaises(RuntimeError):
                    reopened.perform('claim_create', applied_then_lost, lambda reply: None)
                self.assertEqual(calls, [NAME])
            finally:
                reopened.close()

    def test_pending_save_failure_makes_no_api_call(self):
        with tempfile.TemporaryDirectory() as parent:
            journal = module.Journal(pathlib.Path(parent) / RUN).open(seed())
            mutate = mock.Mock()
            try:
                with mock.patch.object(module.os, 'fsync', side_effect=OSError('public failure')):
                    with self.assertRaises(OSError):
                        journal.perform('storageclass_create', mutate, lambda reply: None)
                mutate.assert_not_called()
            finally:
                journal.close()

    def test_new_parent_entry_fsync_failure_refuses_initialization_before_api(self):
        with tempfile.TemporaryDirectory() as parent:
            directory = pathlib.Path(parent) / RUN
            parent_inode = (pathlib.Path(parent).stat().st_dev, pathlib.Path(parent).stat().st_ino)
            original = os.fsync
            calls = []

            def fsync(fd):
                info = os.fstat(fd)
                if (info.st_dev, info.st_ino) == parent_inode:
                    calls.append('parent')
                    raise OSError('public parent sync fault')
                calls.append('other')
                return original(fd)

            journal = module.Journal(directory)
            mutate = mock.Mock()
            with mock.patch.object(module.os, 'fsync', side_effect=fsync):
                with self.assertRaisesRegex(RuntimeError, 'journal unavailable'):
                    journal.open(seed()).perform('claim_create', mutate, lambda reply: None)
            self.assertEqual(calls, ['parent'])
            mutate.assert_not_called()
            self.assertIsNone(journal.fd)
            self.assertIsNone(journal.parent_fd)
            self.assertTrue(directory.is_dir())  # Keep the failed owned run for inspection.
            self.assertFalse((directory / 'journal.json').exists())
            self.assertFalse((directory / 'active.lock').exists())

    def test_confirmation_save_failure_retains_pending_and_never_replays(self):
        with tempfile.TemporaryDirectory() as parent:
            directory = pathlib.Path(parent) / RUN
            journal = module.Journal(directory).open(seed())
            real_save = journal.save
            saves = []

            def failing_save():
                saves.append(True)
                if len(saves) > 1:
                    raise OSError('public disk fault')
                return real_save()

            try:
                with mock.patch.object(journal, 'save', side_effect=failing_save):
                    with self.assertRaises(RuntimeError):
                        journal.perform('holder_create', lambda intent: result(), lambda reply: None)
                disk = json.loads((directory / 'journal.json').read_text())
                self.assertEqual(disk['operations']['holder_create']['state'], 'pending')
            finally:
                journal.close()
            reopened = module.Journal(directory).open()
            try:
                mutate = mock.Mock()
                with self.assertRaises(RuntimeError):
                    reopened.perform('holder_create', mutate, lambda reply: None)
                mutate.assert_not_called()
            finally:
                reopened.close()

    def test_foreign_reply_or_failed_spec_validation_never_records_ownership(self):
        for drift in ('kind', 'name', 'namespace', 'label', 'spec'):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as parent:
                journal = module.Journal(pathlib.Path(parent) / RUN).open(seed())
                reply = result()
                if drift == 'kind':
                    reply['kind'] = 'Secret'
                elif drift == 'label':
                    reply['metadata']['labels']['bortus-restore'] = 'foreign'
                elif drift != 'spec':
                    reply['metadata'][drift] = 'foreign'

                def validate(reply):
                    if drift == 'spec':
                        raise RuntimeError('PRIVATE_RESPONSE_DETAIL')

                try:
                    with self.assertRaises(RuntimeError):
                        journal.perform('holder_create', lambda intent: reply, validate)
                    self.assertEqual(journal.record['operations']['holder_create']['state'], 'uncertain')
                    self.assertNotIn('identity', journal.record['operations']['holder_create'])
                    self.assertNotIn('PRIVATE_', json.dumps(journal.record))
                finally:
                    journal.close()

    def test_delete_requires_confirmed_same_uid_and_fresh_supplied_rv(self):
        with tempfile.TemporaryDirectory() as parent:
            journal = module.Journal(pathlib.Path(parent) / RUN).open(seed())
            try:
                mutate = mock.Mock()
                with self.assertRaises(RuntimeError):
                    journal.perform('holder_delete', mutate, lambda reply: None)
                mutate.assert_not_called()
                journal.perform('holder_create', lambda intent: result(), lambda reply: None)
                fresh = module.identity(result(rv='99'))
                for bad in (None, dict(fresh, uid='foreign'), dict(fresh, namespace='foreign')):
                    with self.assertRaises(RuntimeError):
                        journal.perform('holder_delete', mutate, lambda reply: None, bad)
                mutate.assert_not_called()
                self.assertNotIn('holder_delete', journal.record['operations'])

                def delete(intent):
                    self.assertEqual(intent['preconditions']['resourceVersion'], '99')
                    self.assertEqual(intent['preconditions']['uid'], 'public-owned-uid')
                    return {'kind': 'Status'}

                journal.perform('holder_delete', delete, lambda reply: None, fresh)
                self.assertEqual(journal.record['operations']['holder_delete']['state'], 'confirmed')
            finally:
                journal.close()

    def test_existing_run_active_lock_and_symlink_refused_without_replacement(self):
        with tempfile.TemporaryDirectory() as parent:
            directory = pathlib.Path(parent) / RUN
            journal = module.Journal(directory).open(seed())
            original = (directory / 'journal.json').read_bytes()
            try:
                with self.assertRaises(RuntimeError):
                    module.Journal(directory).open(seed())
                with self.assertRaises(RuntimeError):
                    module.Journal(directory).open()
                self.assertEqual((directory / 'journal.json').read_bytes(), original)
                link = pathlib.Path(parent) / 'symlink'
                link.symlink_to(directory, target_is_directory=True)
                with self.assertRaises(RuntimeError):
                    module.Journal(link).open()
            finally:
                journal.close()
            foreign = pathlib.Path(parent) / 'foreign'
            foreign.write_text('foreign')
            (directory / 'active.lock').symlink_to(foreign)
            with self.assertRaises(RuntimeError):
                module.Journal(directory).open()
            self.assertEqual(foreign.read_text(), 'foreign')
            self.assertTrue((directory / 'active.lock').is_symlink())

    def test_replaced_lock_journal_or_directory_refuses_save_and_keeps_foreign(self):
        for drift in ('lock', 'journal', 'directory'):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as parent:
                directory = pathlib.Path(parent) / RUN
                journal = module.Journal(directory).open(seed())
                if drift == 'directory':
                    directory.rename(pathlib.Path(parent) / 'retained-original')
                    directory.mkdir(mode=0o700)
                    (directory / 'active.lock').write_text('foreign')
                else:
                    name = 'active.lock' if drift == 'lock' else 'journal.json'
                    path = directory / name
                    raw = path.read_bytes()
                    replacement = directory / 'foreign-copy'
                    replacement.write_bytes(raw)
                    replacement.chmod(0o600)
                    replacement.replace(path)
                mutate = mock.Mock()
                try:
                    with self.assertRaises(RuntimeError):
                        journal.perform('claim_create', mutate, lambda reply: None)
                    mutate.assert_not_called()
                finally:
                    journal.close()
                if drift in ('lock', 'directory'):
                    self.assertTrue((directory / 'active.lock').exists())

    def test_reopen_rejects_extra_fields_duplicate_keys_permissions_and_nonfiles(self):
        for drift in ('extra', 'duplicate', 'permissions', 'symlink', 'fifo'):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as parent:
                directory = pathlib.Path(parent) / RUN
                journal = module.Journal(directory).open(seed())
                journal.close()
                path = directory / 'journal.json'
                if drift == 'extra':
                    record = json.loads(path.read_text())
                    record['private'] = 'PRIVATE_VALUE'
                    path.write_text(json.dumps(record))
                elif drift == 'duplicate':
                    path.write_text(path.read_text().replace('{', '{"run_id":"foreign",', 1))
                elif drift == 'permissions':
                    path.chmod(0o644)
                else:
                    path.unlink()
                    if drift == 'symlink':
                        path.symlink_to(pathlib.Path(parent) / 'missing')
                    else:
                        os.mkfifo(path, 0o600)
                with self.assertRaisesRegex(RuntimeError, 'journal unavailable') as error:
                    module.Journal(directory).open()
                self.assertNotIn('PRIVATE_', str(error.exception))
                self.assertFalse((directory / 'active.lock').exists())


if __name__ == '__main__':
    unittest.main()
