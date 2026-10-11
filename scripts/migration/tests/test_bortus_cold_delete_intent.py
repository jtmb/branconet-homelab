"""Actual POSIX journal faults around the owned holder's preconditioned deletion."""
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
spec = importlib.util.spec_from_file_location('cold_delete_fixtures', HERE / 'test_bortus_cold_checkpoint.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
module = fixtures.module
RUN = '123456abcdef'


@unittest.skipUnless(os.name == 'posix', 'Actual POSIX file/directory flush semantics required')
class ColdDeleteIntentTests(unittest.TestCase):
    def open_run(self, parent):
        client, memory, _ = fixtures.prepared()
        holder = client.create(memory.record['holder_proposal'])
        memory.record['holder_identity'] = module.identity(holder)
        directory = pathlib.Path(parent) / RUN
        journal = module.Journal(directory, copy.deepcopy(memory.record)).open(new=True)
        return client, journal, module.Checkpoint(client, journal), directory

    def test_pending_exact_identity_flushes_before_delete_and_confirmation_is_durable(self):
        with tempfile.TemporaryDirectory() as parent:
            client, journal, operation, directory = self.open_run(parent)
            original = os.fsync
            flushed = []

            def fsync(fd):
                info = os.fstat(fd)
                flushed.append((info.st_ino, stat.S_ISDIR(info.st_mode)))
                return original(fd)

            delete = client.delete_holder

            def callback(holder):
                disk = json.loads((directory / 'journal.json').read_text())
                self.assertEqual({'identity': module.identity(holder), 'state': 'pending'}, disk['holder_delete_intent'])
                self.assertIn((directory.stat().st_ino, True), flushed)
                self.assertTrue(any(not is_directory for _, is_directory in flushed))
                return delete(holder)

            try:
                with mock.patch.object(module.os, 'fsync', side_effect=fsync), mock.patch.object(client, 'delete_holder', side_effect=callback):
                    operation.delete_owned_holder()
                disk = json.loads((directory / 'journal.json').read_text())
                self.assertEqual('confirmed', disk['holder_delete_intent']['state'])
                self.assertTrue(disk['holder_delete_accepted'])
                with self.assertRaises(RuntimeError):
                    operation.delete_owned_holder()
                self.assertEqual(1, sum(c[0] == 'delete-holder' for c in client.calls))
            finally:
                journal.close()

    def test_pending_flush_failure_suppresses_delete(self):
        for fail_directory in (False, True):
            with self.subTest(directory=fail_directory), tempfile.TemporaryDirectory() as parent:
                client, journal, operation, _ = self.open_run(parent)
                original = os.fsync

                def fsync(fd):
                    if stat.S_ISDIR(os.fstat(fd).st_mode) is fail_directory:
                        raise OSError('public pending flush fault')
                    return original(fd)

                try:
                    with mock.patch.object(module.os, 'fsync', side_effect=fsync), mock.patch.object(client, 'delete_holder', wraps=client.delete_holder) as callback:
                        with self.assertRaises(OSError):
                            operation.delete_owned_holder()
                        callback.assert_not_called()
                    with self.assertRaises(RuntimeError):
                        operation.delete_owned_holder()
                finally:
                    journal.close()

    def test_lost_reply_before_or_after_delete_remains_uncertain_and_resume_never_replays(self):
        for applied in (False, True):
            with self.subTest(applied=applied), tempfile.TemporaryDirectory() as parent:
                client, journal, operation, directory = self.open_run(parent)
                delete = client.delete_holder

                def callback(holder):
                    if applied:
                        delete(holder)
                    raise RuntimeError('PRIVATE_SYNTHETIC_DELETE_RESPONSE')

                try:
                    with mock.patch.object(client, 'delete_holder', side_effect=callback) as called:
                        with self.assertRaises(RuntimeError):
                            operation.delete_owned_holder()
                        called.assert_called_once()
                    disk = json.loads((directory / 'journal.json').read_text())
                    self.assertEqual('uncertain', disk['holder_delete_intent']['state'])
                    self.assertNotIn('PRIVATE_SYNTHETIC', (directory / 'journal.json').read_text())
                finally:
                    journal.close()
                reopened = module.Journal(directory).open(new=False)
                try:
                    resumed = module.Checkpoint(client, reopened)
                    with mock.patch.object(client, 'delete_holder', wraps=client.delete_holder) as called:
                        with self.assertRaises(RuntimeError):
                            resumed.delete_owned_holder()
                        resumed.resume()
                        called.assert_not_called()
                    self.assertEqual('uncertain', reopened.record['holder_delete_intent']['state'])
                finally:
                    reopened.close()

    def test_confirmation_flush_failure_retains_pending_and_never_replays(self):
        with tempfile.TemporaryDirectory() as parent:
            client, journal, operation, directory = self.open_run(parent)
            original = os.fsync
            delete = client.delete_holder
            submitted = [False]

            def callback(holder):
                result = delete(holder)
                submitted[0] = True
                return result

            def fsync(fd):
                if submitted[0]:
                    raise OSError('public confirmation flush fault')
                return original(fd)

            try:
                with mock.patch.object(client, 'delete_holder', side_effect=callback), mock.patch.object(module.os, 'fsync', side_effect=fsync):
                    with self.assertRaises(OSError):
                        operation.delete_owned_holder()
                self.assertEqual('pending', json.loads((directory / 'journal.json').read_text())['holder_delete_intent']['state'])
            finally:
                journal.close()
            reopened = module.Journal(directory).open(new=False)
            try:
                with self.assertRaises(RuntimeError):
                    module.Checkpoint(client, reopened).delete_owned_holder()
                self.assertEqual(1, sum(c[0] == 'delete-holder' for c in client.calls))
            finally:
                reopened.close()

    def test_holder_recreation_refused_before_pending_or_delete(self):
        with tempfile.TemporaryDirectory() as parent:
            client, journal, operation, _ = self.open_run(parent)
            client.resources['pods']['items'][-1]['metadata']['uid'] = 'foreign-holder-uid'
            try:
                with mock.patch.object(client, 'delete_holder', wraps=client.delete_holder) as called:
                    with self.assertRaises(RuntimeError):
                        operation.delete_owned_holder()
                    called.assert_not_called()
                self.assertNotIn('holder_delete_intent', journal.record)
            finally:
                journal.close()

    def test_uncertainty_flush_failure_keeps_pending_and_suppresses_retry(self):
        with tempfile.TemporaryDirectory() as parent:
            client, journal, operation, directory = self.open_run(parent)
            original = os.fsync
            attempted = [False]

            def callback(holder):
                attempted[0] = True
                raise RuntimeError('PRIVATE_SYNTHETIC_AMBIGUOUS_DELETE')

            def fsync(fd):
                if attempted[0]:
                    raise OSError('public uncertainty flush fault')
                return original(fd)

            try:
                with mock.patch.object(client, 'delete_holder', side_effect=callback) as called, mock.patch.object(module.os, 'fsync', side_effect=fsync):
                    with self.assertRaises(OSError):
                        operation.delete_owned_holder()
                    called.assert_called_once()
                self.assertEqual('pending', json.loads((directory / 'journal.json').read_text())['holder_delete_intent']['state'])
                self.assertNotIn('PRIVATE_SYNTHETIC', (directory / 'journal.json').read_text())
            finally:
                journal.close()
            reopened = module.Journal(directory).open(new=False)
            try:
                with mock.patch.object(client, 'delete_holder', wraps=client.delete_holder) as called:
                    with self.assertRaises(RuntimeError):
                        module.Checkpoint(client, reopened).delete_owned_holder()
                    called.assert_not_called()
            finally:
                reopened.close()


if __name__ == '__main__':
    unittest.main()
