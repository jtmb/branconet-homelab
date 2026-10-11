"""Actual Linux Node reader qualification using only disposable public fixtures."""
import importlib.util
import io
import json
import os
import pathlib
import sqlite3
import subprocess
import tempfile
import unittest
import uuid

spec = importlib.util.spec_from_file_location('sqlite_archive',
    pathlib.Path(__file__).resolve().parents[1] / 'bortus-sqlite-archive.py')
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)
IMAGE = 'sha256:f628f5688b3fafb391d8d99c9b16aee4d9162aa5aaa121c3ae340f5bc8c2a678'


@unittest.skipUnless(os.name == 'posix', 'Linux O_NOFOLLOW qualification requires WSL')
class NodeReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Inspect the already installed image. Never pull or build during this test.
        result = subprocess.run(['docker', 'image', 'inspect', IMAGE],
            capture_output=True, timeout=5, check=True)
        image = json.loads(result.stdout)[0]
        assert image['Id'] == IMAGE and image['Os'] == 'linux'

    def read_fixture(self, folder):
        name = 'bortus-reader-fixture-' + uuid.uuid4().hex[:12]
        process = subprocess.Popen(['docker', 'run', '--rm', '-i', '--name', name,
            '--label', 'bortus.reader-fixture=' + name, '--network', 'none', '--read-only',
            '--memory', '128m', '--cpus', '1', '--pids-limit', '64',
            '--user', str(os.getuid()) + ':' + str(os.getgid()),
            '--mount', 'type=bind,src=' + str(folder) + ',dst=/data,readonly',
            '--entrypoint', 'node', IMAGE, '-'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            output, error = process.communicate(archive.NODE_READER.encode(), timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=3)
            # Only remove the container owned by this exact test, if it still exists.
            found = subprocess.run(['docker', 'inspect', name], capture_output=True, timeout=5)
            if found.returncode == 0:
                container = json.loads(found.stdout)[0]
                self.assertEqual(container['Config']['Labels'].get('bortus.reader-fixture'), name)
                subprocess.run(['docker', 'rm', '-f', name], check=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            raise
        finally:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream and not stream.closed:
                    stream.close()
        self.assertIsNotNone(process.poll())
        remaining = subprocess.run(['docker', 'ps', '-aq', '--filter', 'name=^/' + name + '$'],
            capture_output=True, check=True, timeout=5)
        self.assertEqual(remaining.stdout.strip(), b'')
        return process.returncode, output, error

    def database(self, folder):
        connection = sqlite3.connect(folder / 'bortus.db')
        try:
            connection.execute('create table public_fixture(value text)')
            connection.execute('insert into public_fixture values (?)', ('PUBLIC_NODE_FIXTURE',))
            connection.commit()
        finally:
            connection.close()

    def test_actual_reader_complete_database_and_optional_sidecars(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            self.database(folder)
            code, output, error = self.read_fixture(folder)
            self.assertEqual((code, error), (0, b''))
            metadata, _ = archive.transfer(io.BytesIO(output), None)
            self.assertEqual(metadata['files'], ['bortus.db'])
            for name, body in [('bortus.db-wal', b'PUBLIC_WAL' * 30000),
                               ('bortus.db-shm', b''), ('bortus.db-journal', b'PUBLIC_JOURNAL')]:
                (folder / name).write_bytes(body)
            code, output, error = self.read_fixture(folder)
            self.assertEqual((code, error), (0, b''))
            restored = io.BytesIO()
            metadata, _ = archive.transfer(io.BytesIO(output), restored)
            self.assertEqual(metadata['files'], list(archive.FILES))
            self.assertEqual(metadata['total_bytes'], sum((folder / n).stat().st_size for n in archive.FILES))
            self.assertEqual(restored.getvalue(), output)

    def test_actual_reader_missing_database_symlink_nonfile_and_oversize_refused(self):
        for case in ('missing', 'symlink-database', 'symlink-sidecar', 'nonfile', 'oversize'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                folder = pathlib.Path(temp)
                if case != 'missing':
                    self.database(folder)
                if case == 'symlink-database':
                    (folder / 'bortus.db').rename(folder / 'public.db')
                    (folder / 'bortus.db').symlink_to('public.db')
                elif case == 'symlink-sidecar':
                    (folder / 'public.wal').write_bytes(b'PUBLIC_WAL')
                    (folder / 'bortus.db-wal').symlink_to('public.wal')
                elif case == 'nonfile':
                    (folder / 'bortus.db-wal').mkdir()
                elif case == 'oversize':
                    with (folder / 'bortus.db-wal').open('wb') as stream:
                        stream.truncate(archive.MAX_FILE + 1)
                code, output, error = self.read_fixture(folder)
                self.assertEqual((code, error), (1, b'Cold SQLite read failed\n'))
                with self.assertRaises(archive.ArchiveError):
                    archive.transfer(io.BytesIO(output), None)


if __name__ == '__main__':
    unittest.main()
