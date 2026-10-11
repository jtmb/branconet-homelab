import hashlib
import importlib.util
import io
import json
import os
import pathlib
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('sqlite_archive',
    pathlib.Path(__file__).resolve().parents[1] / 'bortus-sqlite-archive.py')
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


def header(obj):
    body = json.dumps(obj).encode()
    return struct.pack('>I', len(body)) + body


def framed(files):
    result = archive.MAGIC
    for name, body in files:
        result += header({'name': name, 'size': len(body)}) + body
    return result + header({'complete': True, 'files': [name for name, _ in files]})


DB = b'SQLite format 3\x00' + b'\0' * 496


class ArchiveTests(unittest.TestCase):
    def test_complete_database_and_sidecars_round_trip_without_public_plaintext_digest(self):
        data = framed([('bortus.db', DB), ('bortus.db-wal', b'PUBLIC_WAL_FIXTURE'),
                       ('bortus.db-shm', b''), ('bortus.db-journal', b'PUBLIC_JOURNAL_FIXTURE')])
        output = io.BytesIO()
        metadata, digest = archive.transfer(io.BytesIO(data), output)
        self.assertEqual(output.getvalue(), data)
        self.assertEqual(digest, hashlib.sha256(data).digest())
        self.assertEqual(metadata, {'files': list(archive.FILES),
                                   'total_bytes': len(DB) + len(b'PUBLIC_WAL_FIXTUREPUBLIC_JOURNAL_FIXTURE')})
        self.assertNotIn('digest', metadata)

    def test_path_traversal_duplicate_order_noninteger_and_excess_size_refused(self):
        good = archive.MAGIC + header({'name': 'bortus.db', 'size': len(DB)}) + DB
        bad_headers = [
            {'name': '../bortus.db', 'size': 512},
            {'name': 'bortus.db-wal', 'size': 512},
            {'name': 'bortus.db', 'size': True},
            {'name': 'bortus.db', 'size': '512'},
            {'name': 'bortus.db', 'size': archive.MAX_FILE + 1},
            {'name': 'bortus.db', 'size': -1},
            {'name': 'bortus.db', 'size': 511},
            {'name': 'bortus.db', 'size': 512, 'unexpected': True}]
        for obj in bad_headers:
            with self.subTest(case='invalid-header'), self.assertRaises(archive.ArchiveError):
                archive.transfer(io.BytesIO(archive.MAGIC + header(obj)), None)
        for suffix in (header({'name': 'bortus.db', 'size': 512}),
                       header({'name': 'bortus.db-journal', 'size': 0}) +
                       header({'name': 'bortus.db-wal', 'size': 0})):
            with self.assertRaises(archive.ArchiveError):
                archive.transfer(io.BytesIO(good + suffix), None)

    def test_missing_completion_truncated_body_wrong_signature_and_trailing_bytes_refused(self):
        data = framed([('bortus.db', DB)])
        for damaged in (data[:10], data[:-2], data + b'EXTRA',
                        framed([('bortus.db', b'INVALID_SQLITE' + b'\0' * 512)]),
                        archive.MAGIC + header({'complete': True, 'files': []}),
                        data.replace(b'"complete": true', b'"complete": 1')):
            with self.subTest(case='damaged-frame'), self.assertRaises(archive.ArchiveError):
                archive.transfer(io.BytesIO(damaged), None)

    def test_duplicate_header_keys_and_unbounded_header_refused(self):
        raw = b'{"name":"bortus.db","size":512,"size":1}'
        for data in (archive.MAGIC + struct.pack('>I', len(raw)) + raw,
                     archive.MAGIC + struct.pack('>I', 1025),
                     archive.MAGIC + struct.pack('>I', 0)):
            with self.assertRaises(archive.ArchiveError):
                archive.transfer(io.BytesIO(data), None)

    def test_aggregate_body_limit_refuses_before_accepting_excess_file(self):
        data = framed([('bortus.db', DB), ('bortus.db-wal', b'x' * 513)])
        with mock.patch.object(archive, 'MAX_FILE', 800), mock.patch.object(archive, 'MAX_TOTAL', 1024):
            with self.assertRaises(archive.ArchiveError):
                archive.transfer(io.BytesIO(data), None)

    @unittest.skipUnless(os.name == 'posix', 'Actual pipe/age qualification runs in WSL')
    def test_real_age_encryption_decryption_and_failed_source_cleanup(self):
        age = pathlib.Path.home() / '.local/share/branconet-migration/bin/age'
        self.assertTrue(age.is_file(), 'Operator age binary required; no synthetic crypto pass')
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            key = root / 'synthetic-identity'
            subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            db = root / 'synthetic.db'
            connection = sqlite3.connect(db)
            try:
                connection.execute('create table fixture(value text)')
                connection.execute('insert into fixture values (?)', ('PUBLIC_ARCHIVE_FIXTURE',))
                connection.commit()
            finally:
                connection.close()
            data = framed([('bortus.db', db.read_bytes()), ('bortus.db-wal', b'PUBLIC_WAL')])

            def source(exit_code=0):
                # Use a file-backed public fixture so producer stdin never blocks before transfer.
                fixture = root / 'public-frame'
                fixture.write_bytes(data)
                return subprocess.Popen([sys.executable, '-c',
                    'import pathlib,sys;sys.stdout.buffer.write(pathlib.Path(sys.argv[1]).read_bytes());'
                    'sys.stdout.buffer.flush();sys.exit(int(sys.argv[2]))', str(fixture), str(exit_code)],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

            producer = source()
            target = root / 'accepted.age'
            processes = []
            original_popen = subprocess.Popen

            def owned(*args, **kwargs):
                process = original_popen(*args, **kwargs)
                processes.append(process)
                return process

            with mock.patch.object(archive.subprocess, 'Popen', side_effect=owned):
                report = archive.encrypt_source(producer, target, age, pathlib.Path(str(key) + '.pub'),
                                                key, time.monotonic() + 30)
            self.assertEqual(len(processes), 2)
            self.assertTrue(all(process.poll() == 0 for process in processes))
            self.assertEqual(producer.poll(), 0)
            self.assertTrue(report['authenticated_decryption_equal'])
            self.assertFalse(report['plaintext_persisted'])
            self.assertFalse(report['sqlite_integrity_or_row_preservation_proven'])
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(report['ciphertext_sha256'], hashlib.sha256(target.read_bytes()).hexdigest())
            self.assertNotIn('PUBLIC_ARCHIVE_FIXTURE', json.dumps(report))
            self.assertNotIn(b'PUBLIC_ARCHIVE_FIXTURE', target.read_bytes())
            failed = source(7)
            rejected = root / 'rejected.age'
            with self.assertRaisesRegex(archive.ArchiveError, '^cold_sqlite_archive_failed$'):
                archive.encrypt_source(failed, rejected, age, pathlib.Path(str(key) + '.pub'),
                                       key, time.monotonic() + 30)
            self.assertIsNotNone(failed.poll())
            self.assertTrue(rejected.exists())
            self.assertEqual(rejected.stat().st_mode & 0o777, 0o600)
            existing = target.read_bytes()
            refused = source()
            with self.assertRaises(archive.ArchiveError):
                archive.encrypt_source(refused, target, age, pathlib.Path(str(key) + '.pub'),
                                       key, time.monotonic() + 30)
            self.assertEqual(target.read_bytes(), existing)
            self.assertIsNotNone(refused.poll())


if __name__ == '__main__':
    unittest.main()
