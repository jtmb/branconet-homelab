"""Real disposable Git repositories; no application runtimes, credentials or API."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('release_context', HERE.parent / 'prepare-bortus-release-context.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ReleaseContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = pathlib.Path(self.tmp.name)
        self.repo = self.parent / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'core.autocrlf', 'false')
        for name in module.REQUIRED:
            self.write(name, ('committed fixture: ' + name + '\n').encode())
        self.write('src/plain.ts', b'export const publicFixture = 1;\n')
        self.write('prisma/migrations/fixture/migration.sql', b'SELECT 1;\n')
        self.git('add', '.')
        self.git('update-index', '--chmod=+x', module.PREFIX + 'docker-entrypoint.sh')
        self.commit = self.commit_tree()
        self.output = self.parent / 'context.tar.gz'
        self.evidence = self.parent / 'evidence.json'

    def git(self, *args, data=None):
        result = subprocess.run(['git', '-C', str(self.repo), *args], input=data,
                                capture_output=True, timeout=30)
        if result.returncode:
            self.fail('Disposable Git fixture operation failed')
        return result.stdout

    def write(self, name, data):
        path = self.repo / module.PREFIX / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def commit_tree(self):
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-q', '-m', 'Public release fixture')
        return self.git('rev-parse', 'HEAD').decode().strip()

    def prepare(self):
        return module.prepare(self.repo, self.commit, self.output, self.evidence)

    def test_raw_committed_bytes_ignore_dirty_and_untracked_working_tree(self):
        self.write('src/plain.ts', b'DIRTY PUBLIC FIXTURE\r\n')
        self.write('src/untracked.ts', b'UNTRACKED PUBLIC FIXTURE\n')
        record = self.prepare()
        with tarfile.open(self.output) as archive:
            self.assertEqual(b'export const publicFixture = 1;\n',
                             archive.extractfile('src/plain.ts').read())
            self.assertNotIn('src/untracked.ts', archive.getnames())
            for member in archive.getmembers():
                self.assertTrue(member.isfile())
                self.assertEqual((0, 0, 0), (member.uid, member.gid, member.mtime))
                self.assertEqual(0o755 if member.name == 'docker-entrypoint.sh' else 0o644, member.mode)
        self.assertFalse(record['working_tree_read'])
        self.assertFalse(record['image_built'])
        self.assertEqual(0, record['cluster_mutations'])
        self.assertEqual(self.commit, record['source_commit'])
        self.assertEqual(1, len(record['migrations']))
        for item in record['files']:
            raw = self.git('cat-file', 'blob', item['git_blob'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item['sha256'])

    def test_excluded_committed_payloads_are_never_read(self):
        names = ['.env', '.env.example', 'nested/.env.local', '.next/server.js',
                 'node_modules/pkg/index.js', 'tests/fixture.ts', 'coverage/report.json',
                 'bortus.db', 'bortus.db-wal', 'nested/state.sqlite3-journal', 'debug.log',
                 'private.pem', 'private.key', 'id_ed25519', 'admin.conf', 'kubeconfig']
        for index, name in enumerate(names):
            self.write(name, ('PUBLIC EXCLUSION FIXTURE ' + str(index)).encode())
        self.git('add', '.')
        self.commit = self.commit_tree()
        excluded_blobs = {self.git('rev-parse', self.commit + ':' + module.PREFIX + name).decode().strip()
                          for name in names}
        original = module.git
        with mock.patch.object(module, 'git', wraps=original) as calls:
            record = self.prepare()
        read_blobs = {call.args[1][2] for call in calls.call_args_list
                      if call.args[1][:2] == ['cat-file', 'blob']}
        self.assertFalse(excluded_blobs & read_blobs)
        self.assertEqual(len(names), record['excluded_entries'])
        self.assertFalse(record['excluded_payloads_read'])
        with tarfile.open(self.output) as archive:
            self.assertFalse(set(names) & set(archive.getnames()))

    def test_archive_is_deterministic_across_output_paths(self):
        first = self.prepare()
        second = module.prepare(self.repo, self.commit, self.parent / 'other.tar.gz',
                                self.parent / 'other.json')
        self.assertEqual(first['context_sha256'], second['context_sha256'])
        self.assertEqual(self.output.read_bytes(), (self.parent / 'other.tar.gz').read_bytes())

    def test_exact_existing_commit_required_before_artifacts(self):
        for commit in ('HEAD', self.commit[:12], self.commit.upper(), '0' * 40):
            with self.subTest(commit=commit), self.assertRaises(RuntimeError):
                module.prepare(self.repo, commit, self.output, self.evidence)
            self.assertFalse(self.output.exists())
            self.assertFalse(self.evidence.exists())

    def test_existing_output_or_evidence_is_preserved(self):
        for path in (self.output, self.evidence):
            path.write_bytes(b'EXISTING PUBLIC ARTIFACT')
            with self.assertRaises(RuntimeError):
                self.prepare()
            self.assertEqual(b'EXISTING PUBLIC ARTIFACT', path.read_bytes())
            self.assertFalse((self.evidence if path == self.output else self.output).exists())
            path.unlink()

    def test_missing_parent_same_path_and_inside_repo_refuse(self):
        for output, evidence in ((self.parent / 'missing' / 'out.tar.gz', self.evidence),
                                 (self.output, self.output),
                                 (self.repo / 'inside.tar.gz', self.evidence),
                                 (self.output, self.repo / 'inside.json')):
            with self.subTest(output=str(output)), self.assertRaises(RuntimeError):
                module.prepare(self.repo, self.commit, output, evidence)
            self.assertFalse(output.exists())
            self.assertFalse(evidence.exists())

    @unittest.skipUnless(os.name == 'posix', 'Actual POSIX dangling-symlink refusal')
    def test_dangling_output_symlink_is_not_followed(self):
        target = self.parent / 'absent'
        self.output.symlink_to(target)
        with self.assertRaises(RuntimeError):
            self.prepare()
        self.assertTrue(self.output.is_symlink())
        self.assertFalse(target.exists())
        self.assertFalse(self.evidence.exists())

    def test_real_git_symlink_and_submodule_entries_refuse(self):
        for mode, oid, name in [('120000', self.git('hash-object', '-w', '--stdin', data=b'outside').decode().strip(), 'link'),
                                ('160000', self.commit, 'submodule')]:
            path = module.PREFIX + name
            self.git('update-index', '--add', '--cacheinfo', mode + ',' + oid + ',' + path)
            self.commit = self.commit_tree()
            with self.subTest(mode=mode), self.assertRaises(RuntimeError):
                self.prepare()
            self.assertFalse(self.output.exists())
            self.git('update-index', '--force-remove', path)

    def test_missing_build_input_refuses(self):
        self.git('rm', '-q', module.PREFIX + 'Dockerfile')
        self.commit = self.commit_tree()
        with self.assertRaises(RuntimeError):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_real_tree_file_count_and_byte_bounds_refuse(self):
        for limit, value in [('MAX_FILES', 2), ('MAX_FILE_BYTES', 1), ('MAX_TOTAL_BYTES', 2)]:
            with self.subTest(limit=limit), mock.patch.object(module, limit, value), self.assertRaises(RuntimeError):
                self.prepare()
            self.assertFalse(self.output.exists())
            self.assertFalse(self.evidence.exists())

    def test_source_fault_retains_exclusive_unaccepted_artifact(self):
        original = module.git
        def query(repo, args, limit):
            if args[:2] == ['cat-file', 'blob']:
                raise RuntimeError('PUBLIC FAULT DETAIL MUST BE WITHHELD')
            return original(repo, args, limit)
        with mock.patch.object(module, 'git', side_effect=query), self.assertRaises(RuntimeError):
            self.prepare()
        before = self.output.read_bytes()
        self.assertFalse(self.evidence.exists())
        with self.assertRaises(RuntimeError):
            self.prepare()
        self.assertEqual(before, self.output.read_bytes())

    def test_flush_fault_retains_artifact_without_acceptance_record(self):
        with mock.patch.object(module.os, 'fsync', side_effect=OSError('PUBLIC FLUSH FAULT')), self.assertRaises(OSError):
            self.prepare()
        self.assertTrue(self.output.is_file())
        self.assertFalse(self.evidence.exists())

    def test_cli_failure_withholds_git_and_private_exception_output(self):
        args = ['prepare', '--source-repo', str(self.repo), '--source-commit', self.commit,
                '--output', str(self.output), '--evidence', str(self.evidence)]
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(module.sys, 'argv', args), mock.patch.object(module, 'prepare',
                side_effect=RuntimeError('PUBLIC PRIVATE-SOURCE FAULT')), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(1, module.main())
        self.assertEqual('', stdout.getvalue())
        self.assertNotIn('PUBLIC PRIVATE-SOURCE FAULT', stderr.getvalue())
        self.assertIn('Private source and Git output withheld', stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
