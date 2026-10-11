"""POSIX fault tests for durable intent before cold-checkpoint API callbacks."""
import copy
import importlib.util
import json
import os
import pathlib
import stat
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('cold_journal_fixtures', HERE / 'test_bortus_cold_checkpoint.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
module = fixtures.module
RUN = '123456abcdef'


def inode(path):
    info = path.stat()
    return info.st_dev, info.st_ino


@unittest.skipUnless(os.name == 'posix', 'Actual owned POSIX directory flush semantics required')
class ColdJournalTests(unittest.TestCase):
    def test_pending_file_and_directory_flush_precede_control_callback(self):
        client, memory, _ = fixtures.prepared()
        with tempfile.TemporaryDirectory() as parent:
            directory = pathlib.Path(parent) / RUN
            journal = module.Journal(directory, copy.deepcopy(memory.record)).open(new=True)
            original = os.fsync
            synced = []
            change = client.change

            def fsync(fd):
                info = os.fstat(fd)
                synced.append(((info.st_dev, info.st_ino), stat.S_ISDIR(info.st_mode)))
                return original(fd)

            def callback(*args):
                disk = json.loads((directory / 'journal.json').read_text())
                self.assertEqual('pending', disk['controls']['helmrelease']['intent']['state'])
                self.assertIn((inode(directory), True), synced)
                self.assertTrue(any(not is_directory for _, is_directory in synced))
                return change(*args)

            try:
                with mock.patch.object(module.os, 'fsync', side_effect=fsync), mock.patch.object(client, 'change', side_effect=callback):
                    module.Checkpoint(client, journal).control('helmrelease', False, True)
                self.assertEqual('confirmed', json.loads((directory / 'journal.json').read_text())['controls']['helmrelease']['intent']['state'])
                self.assertEqual(0o700, stat.S_IMODE(directory.stat().st_mode))
                self.assertEqual(0o600, stat.S_IMODE((directory / 'journal.json').stat().st_mode))
            finally:
                journal.close()

    def test_pending_directory_flush_failure_suppresses_api_callback(self):
        client, memory, _ = fixtures.prepared()
        with tempfile.TemporaryDirectory() as parent:
            directory = pathlib.Path(parent) / RUN
            journal = module.Journal(directory, copy.deepcopy(memory.record)).open(new=True)
            original = os.fsync

            def fsync(fd):
                info = os.fstat(fd)
                if (info.st_dev, info.st_ino) == inode(directory):
                    raise OSError('public directory fault')
                return original(fd)

            try:
                with mock.patch.object(module.os, 'fsync', side_effect=fsync), mock.patch.object(client, 'change', wraps=client.change) as callback:
                    with self.assertRaises(OSError):
                        module.Checkpoint(client, journal).control('helmrelease', False, True)
                    callback.assert_not_called()
                self.assertEqual('pending', json.loads((directory / 'journal.json').read_text())['controls']['helmrelease']['intent']['state'])
            finally:
                journal.close()

    def test_parent_entry_flush_failure_refuses_initialization_and_closes_handles(self):
        _, memory, _ = fixtures.prepared()
        with tempfile.TemporaryDirectory() as parent:
            directory = pathlib.Path(parent) / RUN
            journal = module.Journal(directory, copy.deepcopy(memory.record))
            parent_inode = inode(pathlib.Path(parent))
            original = os.fsync
            calls = []

            def fsync(fd):
                info = os.fstat(fd)
                if (info.st_dev, info.st_ino) == parent_inode:
                    calls.append('parent')
                    raise OSError('public parent fault')
                return original(fd)

            try:
                with mock.patch.object(module.os, 'fsync', side_effect=fsync):
                    with self.assertRaises(RuntimeError):
                        journal.open(new=True)
                self.assertEqual(['parent'], calls)
                self.assertFalse(journal.opened)
                self.assertIsNone(journal.directory_fd)
                self.assertIsNone(journal.parent_fd)
                self.assertTrue(directory.is_dir())
                self.assertFalse((directory / 'journal.json').exists())
                self.assertFalse((directory / 'active.lock').exists())
            finally:
                journal.close()

    def test_file_flush_failure_suppresses_api_callback(self):
        client, memory, _ = fixtures.prepared()
        with tempfile.TemporaryDirectory() as parent:
            journal = module.Journal(pathlib.Path(parent) / RUN, copy.deepcopy(memory.record)).open(new=True)
            try:
                with mock.patch.object(module.os, 'fsync', side_effect=OSError('public file fault')), mock.patch.object(client, 'change', wraps=client.change) as callback:
                    with self.assertRaises(OSError):
                        module.Checkpoint(client, journal).control('helmrelease', False, True)
                    callback.assert_not_called()
            finally:
                journal.close()

    def test_lost_reply_keeps_actual_uncertain_intent_for_resume_inspection(self):
        client, memory, _ = fixtures.prepared()
        with tempfile.TemporaryDirectory() as parent:
            directory = pathlib.Path(parent) / RUN
            journal = module.Journal(directory, copy.deepcopy(memory.record)).open(new=True)
            client.fail_change = ('helmrelease', 'after')
            try:
                with self.assertRaises(RuntimeError):
                    module.Checkpoint(client, journal).control('helmrelease', False, True)
                self.assertEqual('uncertain', json.loads((directory / 'journal.json').read_text())['controls']['helmrelease']['intent']['state'])
                self.assertEqual(1, len(client.calls))
            finally:
                journal.close()
            reopened = module.Journal(directory).open(new=False)
            try:
                self.assertEqual('uncertain', reopened.record['controls']['helmrelease']['intent']['state'])
                self.assertEqual(1, len(client.calls))  # Reopening performs no API operation.
                self.assertNotIn('PRIVATE_SYNTHETIC', (directory / 'journal.json').read_text())
            finally:
                reopened.close()

    def test_protected_parent_chain_entries_flush_and_refuse_fault_or_symlink(self):
        original = os.fsync
        with tempfile.TemporaryDirectory() as parent:
            runtime = pathlib.Path(parent)
            flushed = []

            def fsync(fd):
                info = os.fstat(fd)
                flushed.append((info.st_dev, info.st_ino))
                return original(fd)

            with mock.patch.object(module, 'RUNTIME', runtime), mock.patch.object(module.os, 'fsync', side_effect=fsync):
                directory = module.checkpoint_directory()
            self.assertEqual(runtime / 'recovery/bortus-checkpoints', directory)
            self.assertIn(inode(runtime), flushed)
            self.assertIn(inode(runtime / 'recovery'), flushed)
            self.assertEqual(0o700, stat.S_IMODE(directory.stat().st_mode))
        with tempfile.TemporaryDirectory() as parent:
            with mock.patch.object(module, 'RUNTIME', pathlib.Path(parent)), mock.patch.object(module.os, 'fsync', side_effect=OSError('public fault')):
                with self.assertRaises(OSError):
                    module.checkpoint_directory()
        with tempfile.TemporaryDirectory() as parent, tempfile.TemporaryDirectory() as foreign:
            runtime = pathlib.Path(parent)
            (runtime / 'recovery').symlink_to(foreign, target_is_directory=True)
            with mock.patch.object(module, 'RUNTIME', runtime):
                with self.assertRaises(OSError):
                    module.checkpoint_directory()
            self.assertEqual([], list(pathlib.Path(foreign).iterdir()))

    def test_replaced_lock_and_journal_are_preserved_before_callback(self):
        for name in ('active.lock', 'journal.json'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as parent:
                client, memory, _ = fixtures.prepared()
                directory = pathlib.Path(parent) / RUN
                journal = module.Journal(directory, copy.deepcopy(memory.record)).open(new=True)
                replacement = directory / 'foreign-file'
                replacement.write_bytes((directory / name).read_bytes())
                replacement.chmod(0o600)
                replacement.replace(directory / name)
                foreign_inode = inode(directory / name)
                with mock.patch.object(client, 'change', wraps=client.change) as callback:
                    with self.assertRaises(RuntimeError):
                        module.Checkpoint(client, journal).control('helmrelease', False, True)
                    callback.assert_not_called()
                journal.close()
                self.assertEqual(foreign_inode, inode(directory / name))

    def test_replaced_run_directory_preserves_foreign_lock_and_closes_handles(self):
        _, memory, _ = fixtures.prepared()
        with tempfile.TemporaryDirectory() as parent:
            directory = pathlib.Path(parent) / RUN
            journal = module.Journal(directory, copy.deepcopy(memory.record)).open(new=True)
            renamed = pathlib.Path(parent) / 'retained-owned-run'
            directory.rename(renamed)
            directory.mkdir(mode=0o700)
            foreign_lock = directory / 'active.lock'
            foreign_lock.write_text('foreign-process\n')
            foreign_lock.chmod(0o600)
            with self.assertRaises(RuntimeError):
                journal.save()
            journal.close()
            self.assertEqual('foreign-process\n', foreign_lock.read_text())
            self.assertTrue((renamed / 'journal.json').is_file())
            self.assertIsNone(journal.directory_fd)
            self.assertIsNone(journal.parent_fd)

    def test_invalid_parent_mode_and_nonfile_records_refuse_without_blocking(self):
        _, memory, _ = fixtures.prepared()
        with tempfile.TemporaryDirectory() as parent:
            directory = pathlib.Path(parent) / RUN
            pathlib.Path(parent).chmod(0o755)
            journal = module.Journal(directory, copy.deepcopy(memory.record))
            with self.assertRaises(RuntimeError):
                journal.open(new=True)
            self.assertFalse(directory.exists())
            self.assertIsNone(journal.parent_fd)
        for kind in ('symlink', 'fifo'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as parent:
                directory = pathlib.Path(parent) / RUN
                journal = module.Journal(directory, copy.deepcopy(memory.record)).open(new=True)
                journal.close()
                path = directory / 'journal.json'
                saved = directory / 'saved-journal.json'
                path.rename(saved)
                if kind == 'symlink':
                    path.symlink_to(saved)
                else:
                    os.mkfifo(path, 0o600)
                reopened = module.Journal(directory)
                with self.assertRaises(RuntimeError):
                    reopened.open(new=False)
                self.assertIsNone(reopened.directory_fd)
                self.assertIsNone(reopened.parent_fd)
                self.assertTrue(saved.is_file())
                self.assertFalse((directory / 'active.lock').exists())


if __name__ == '__main__':
    unittest.main()
