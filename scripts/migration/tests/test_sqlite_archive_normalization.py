import hashlib
import importlib.util
import io
import json
import os
import pathlib
import sqlite3
import struct
import subprocess
import tempfile
import time
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('sqlite_normalization',
    pathlib.Path(__file__).resolve().parents[1] / 'normalize-bortus-sqlite-archive.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)
archive = recovery.archive


def frame(files):
    def header(obj):
        raw = json.dumps(obj).encode()
        return struct.pack('>I', len(raw)) + raw
    return archive.MAGIC + b''.join(header({'name': n, 'size': len(b)}) + b for n, b in files) + \
        header({'complete': True, 'files': [n for n, _ in files]})


@unittest.skipUnless(os.name == 'posix', 'Actual authenticated tmpfs recovery requires WSL')
class NormalizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.age = pathlib.Path.home() / '.local/share/branconet-migration/bin/age'
        self.key = self.root / 'synthetic-key'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(self.key)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.before = set(pathlib.Path('/dev/shm').glob('bortus-sqlite-*'))

    def encrypt(self, data):
        target = self.root / ('fixture-' + str(len(list(self.root.glob('fixture-*')))) + '.age')
        with target.open('wb') as out:
            subprocess.run([str(self.age), '-R', str(self.key) + '.pub'], input=data,
                stdout=out, stderr=subprocess.DEVNULL, check=True, timeout=5)
        return target

    def database_files(self, *, wal=False, foreign_key_error=False):
        path = self.root / ('source-' + str(len(list(self.root.glob('source-*')))) + '.db')
        db = sqlite3.connect(path)
        try:
            db.execute('create table fixture(value text)')
            if foreign_key_error:
                db.execute('create table parent(id integer primary key)')
                db.execute('create table child(parent_id integer references parent(id))')
                db.execute('insert into child values (123)')
            db.commit()
            if wal:
                self.assertEqual(db.execute('PRAGMA journal_mode=WAL').fetchone()[0], 'wal')
                db.execute('PRAGMA wal_autocheckpoint=0')
            db.execute('insert into fixture values (?)', ('PUBLIC_NORMALIZATION_FIXTURE',))
            db.commit()
            files = [('bortus.db', path.read_bytes())]
            for suffix in ('-wal', '-shm', '-journal'):
                item = pathlib.Path(str(path) + suffix)
                if item.exists():
                    files.append(('bortus.db' + suffix, item.read_bytes()))
            return files
        finally:
            db.close()

    def restore(self, target, **kwargs):
        return recovery.normalize(target, hashlib.sha256(target.read_bytes()).hexdigest(),
                                  self.key, age=self.age, **kwargs)

    def cleaned(self):
        self.assertEqual(set(pathlib.Path('/dev/shm').glob('bortus-sqlite-*')), self.before)

    def test_actual_age_wal_replay_preserves_committed_row_and_cleans_only_memory_copy(self):
        files = self.database_files(wal=True)
        original = self.root / 'public-precheckpoint.db'
        original.write_bytes(files[0][1])
        db = sqlite3.connect(original.as_uri() + '?immutable=1', uri=True)
        try:
            self.assertEqual(db.execute('select count(*) from fixture').fetchone()[0], 0)
        finally:
            db.close()
        target = self.encrypt(frame(files))
        processes = []
        original_popen = subprocess.Popen
        def owned(*args, **kwargs):
            process = original_popen(*args, **kwargs)
            processes.append(process)
            return process
        with mock.patch.object(recovery.subprocess, 'Popen', side_effect=owned):
            report = self.restore(target)
        try:
            self.assertEqual(len(processes), 1)
            self.assertEqual(processes[0].poll(), 0)
            self.assertTrue(report['authenticated_decryption'] and report['sqlite_checkpointed'])
            self.assertFalse(report['persistent_plaintext_written'] or report['whole_row_preservation_proven'])
            self.assertNotIn('PUBLIC_NORMALIZATION_FIXTURE', json.dumps(report))
            database = pathlib.Path(report['database_path'])
            self.assertEqual(database.stat().st_mode & 0o777, 0o600)
            db = sqlite3.connect(database.as_uri() + '?immutable=1', uri=True)
            try:
                self.assertEqual(db.execute('select value from fixture').fetchall(), [('PUBLIC_NORMALIZATION_FIXTURE',)])
            finally:
                db.close()
            self.assertEqual(original.read_bytes(), files[0][1])
        finally:
            recovery.cleanup(report['temporary_directory'], report['temporary_directory_identity'])
        self.cleaned()

    def test_hash_mismatch_unsafe_parent_symlink_and_expired_budget_refuse_without_tmpfs_writes(self):
        target = self.encrypt(frame(self.database_files()))
        with self.assertRaisesRegex(recovery.RecoveryError, '^sqlite_archive_normalization_failed$'):
            recovery.normalize(target, '0' * 64, self.key, age=self.age)
        for parent in ('/tmp', '/dev/shm/../shm'):
            with self.assertRaises(recovery.RecoveryError):
                self.restore(target, parent=parent)
        link = self.root / 'symlink.age'
        link.symlink_to(target)
        with self.assertRaises(recovery.RecoveryError):
            self.restore(link)
        with self.assertRaises(recovery.RecoveryError):
            self.restore(target, seconds=0)
        self.cleaned()

    def test_authenticated_but_bad_framing_and_invalid_database_never_leave_plaintext(self):
        files = self.database_files()
        for data in (frame(files) + b'EXTRA', frame(files)[:-3],
                     frame([('../outside.db', files[0][1])]),
                     frame([('bortus.db', b'SQLite format 3\0' + b'\0' * 496)])):
            with self.subTest(case='bad-archive'), self.assertRaises(recovery.RecoveryError):
                self.restore(self.encrypt(data))
            self.cleaned()

    def test_truncated_age_authentication_and_foreign_key_violation_refuse_and_close_process(self):
        target = self.encrypt(frame(self.database_files(wal=True)))
        target.write_bytes(target.read_bytes()[:-16])
        processes = []
        original_popen = subprocess.Popen
        def owned(*args, **kwargs):
            process = original_popen(*args, **kwargs)
            processes.append(process)
            return process
        with mock.patch.object(recovery.subprocess, 'Popen', side_effect=owned), self.assertRaises(recovery.RecoveryError):
            self.restore(target)
        self.assertTrue(processes and all(p.poll() is not None for p in processes))
        self.cleaned()
        with self.assertRaises(recovery.RecoveryError):
            self.restore(self.encrypt(frame(self.database_files(foreign_key_error=True))))
        self.cleaned()

    def test_damaged_current_wal_checksum_or_partial_frame_refuses_instead_of_silent_row_loss(self):
        files = self.database_files(wal=True)
        wal = dict(files)['bortus.db-wal']
        for modified in (wal[:-1], wal[:24] + bytes([wal[24] ^ 1]) + wal[25:],
                         wal[:60] + bytes([wal[60] ^ 1]) + wal[61:]):
            changed = [(n, modified if n == 'bortus.db-wal' else b) for n, b in files]
            with self.assertRaises(recovery.RecoveryError):
                self.restore(self.encrypt(frame(changed)))
            self.cleaned()

    def test_cleanup_identity_and_foreign_file_refusal_preserve_owned_copy_until_review(self):
        report = self.restore(self.encrypt(frame(self.database_files())))
        folder = pathlib.Path(report['temporary_directory'])
        with self.assertRaises(recovery.RecoveryError):
            recovery.cleanup(folder, [0, 0, 0])
        foreign = folder / 'unrelated'
        foreign.write_bytes(b'PUBLIC_UNRELATED')
        with self.assertRaises(recovery.RecoveryError):
            recovery.cleanup(folder, report['temporary_directory_identity'])
        self.assertTrue((folder / 'bortus.db').is_file() and foreign.exists())
        foreign.unlink()
        cleanup_report = self.root / 'public-cleanup-report.json'
        cleanup_report.write_text(json.dumps(report))
        subprocess.run([os.sys.executable, '-B', str(pathlib.Path(recovery.__file__)),
            '--cleanup-report', str(cleanup_report)], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=5)
        self.cleaned()

    def test_legitimate_reset_wal_with_old_salt_tail_preserves_both_committed_rows(self):
        path = self.root / 'reset.db'
        db = sqlite3.connect(path)
        try:
            db.execute('create table fixture(value text)')
            db.commit()
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA wal_autocheckpoint=0')
            db.execute('insert into fixture values (?)', ('PUBLIC_LONG_' * 3000,))
            db.commit()
            self.assertEqual(db.execute('PRAGMA wal_checkpoint(PASSIVE)').fetchone()[0], 0)
            db.execute('insert into fixture values (?)', ('PUBLIC_AFTER_RESET',))
            db.commit()
            files = [('bortus.db' + suffix, pathlib.Path(str(path) + suffix).read_bytes())
                     for suffix in ('', '-wal', '-shm')]
        finally:
            db.close()
        wal = dict(files)['bortus.db-wal']
        page_size = int.from_bytes(wal[8:12], 'big')
        self.assertTrue(any(wal[i + 8:i + 16] != wal[16:24]
            for i in range(32, len(wal), 24 + page_size)))
        report = self.restore(self.encrypt(frame(files)))
        try:
            normalized = sqlite3.connect(pathlib.Path(report['database_path']).as_uri() + '?immutable=1', uri=True)
            try:
                self.assertEqual(normalized.execute('select count(*) from fixture').fetchone()[0], 2)
                self.assertEqual(normalized.execute('select value from fixture where rowid=2').fetchone()[0], 'PUBLIC_AFTER_RESET')
            finally:
                normalized.close()
        finally:
            recovery.cleanup(report['temporary_directory'], report['temporary_directory_identity'])
        self.cleaned()

    def test_big_endian_wal_checksum_dialect_is_accepted_by_actual_sqlite(self):
        files = self.database_files(wal=True)
        wal = bytearray(dict(files)['bortus.db-wal'])
        wal[:4] = bytes.fromhex('377f0683')
        def reference_checksum(body, state):
            a, b = state
            for i in range(0, len(body), 8):
                a = (a + int.from_bytes(body[i:i + 4], 'big') + b) % (2 ** 32)
                b = (b + int.from_bytes(body[i + 4:i + 8], 'big') + a) % (2 ** 32)
            return a, b
        running = reference_checksum(wal[:24], (0, 0))
        wal[24:32] = struct.pack('>II', *running)
        page_size = int.from_bytes(wal[8:12], 'big')
        for i in range(32, len(wal), 24 + page_size):
            running = reference_checksum(wal[i:i + 8] + wal[i + 24:i + 24 + page_size], running)
            wal[i + 16:i + 24] = struct.pack('>II', *running)
        changed = [(n, bytes(wal) if n == 'bortus.db-wal' else b) for n, b in files]
        report = self.restore(self.encrypt(frame(changed)))
        try:
            normalized = sqlite3.connect(pathlib.Path(report['database_path']).as_uri() + '?immutable=1', uri=True)
            try:
                self.assertEqual(normalized.execute('select value from fixture').fetchall(), [('PUBLIC_NORMALIZATION_FIXTURE',)])
            finally:
                normalized.close()
        finally:
            recovery.cleanup(report['temporary_directory'], report['temporary_directory_identity'])
        self.cleaned()


if __name__ == '__main__':
    unittest.main()
