"""Pure archive/POSIX/fault fixtures; SSH and Docker are never executed."""
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import stat
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('release_image', HERE.parent / 'build-bortus-release-image.py')
m = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(m)


class ReleaseImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='bortus-build-fixture-', dir=pathlib.Path.home())
        self.addCleanup(self.tmp.cleanup)
        self.directory = pathlib.Path(self.tmp.name)
        self.parent = self.directory / 'runtime'; self.parent.mkdir(mode=0o755)
        self.context = self.directory / 'context.tar.gz'; self.manifest = self.directory / 'manifest.json'
        self.commit = '1' * 40
        self.payloads = {name: ('PUBLIC SOURCE FIXTURE ' + name + '\n').encode() for name in m.producer.REQUIRED}
        self.payloads['prisma/migrations/public/migration.sql'] = b'SELECT 1;\n'
        self.calls = []; self.stage_codes = {}; self.stage_action = None; self.inspect_change = None
        self.tag_output = b''
        self.prepare()

    def prepare(self, member_change=None, manifest_change=None, tar_change=None):
        entries = []; buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w', format=tarfile.PAX_FORMAT) as archive:
            for name, raw in sorted(self.payloads.items()):
                mode = '100755' if name == 'docker-entrypoint.sh' else '100644'
                entries.append({'path': name, 'mode': mode, 'bytes': len(raw), 'sha256': m.digest(raw),
                    'git_blob': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()})
                member = tarfile.TarInfo(name); member.size = len(raw); member.mode = 0o755 if mode == '100755' else 0o644
                if member_change: member_change(member)
                archive.addfile(member, io.BytesIO(raw) if member.isfile() else None)
        tar = buffer.getvalue()
        if tar_change: tar = tar_change(tar)
        raw_context = gzip.compress(tar, mtime=0)
        record = {'scope': 'Immutable raw-Git build context only; no image or release acceptance',
            'source_commit': self.commit, 'application_tree': '2' * 40, 'source_prefix': m.producer.PREFIX,
            'started_at_utc': '2026-10-11T00:00:00+00:00', 'completed_at_utc': '2026-10-11T00:00:01+00:00',
            'context_sha256': m.digest(raw_context), 'context_bytes': len(raw_context),
            'source_bytes': sum(e['bytes'] for e in entries), 'included_files': len(entries), 'excluded_entries': 0,
            'files': entries, 'migrations': [e for e in entries if e['path'].endswith('/migration.sql')],
            'working_tree_read': False, 'excluded_payloads_read': False, 'dependencies_installed': False,
            'image_built': False, 'cluster_mutations': 0, 'live_acceptance': False}
        if manifest_change: manifest_change(record)
        self.context.write_bytes(raw_context); self.context.chmod(0o600)
        self.manifest.write_bytes((json.dumps(record) + '\n').encode()); self.manifest.chmod(0o600)
        self.context_sha = m.digest(raw_context); self.manifest_sha = m.digest(self.manifest.read_bytes())
        return record

    def record(self): return json.loads((self.parent / ('bortus-release-' + self.commit) / 'record.json').read_bytes())

    def fake(self, run, stage, command, timeout, stdin=None):
        self.calls.append(stage)
        self.assertEqual(m.SSH, command[:len(m.SSH)])
        self.assertNotIn('sudo', command[-1]); self.assertNotIn('--password', command[-1])
        if stage == 'build':
            disk = json.loads((run.directory / 'record.json').read_bytes())
            self.assertEqual('pending', disk['phase']); self.assertEqual(run.record['owner'], disk['owner'])
            self.assertEqual(self.context.read_bytes(), stdin.read()); stdin.seek(0)
            self.assertIn('--build-arg KUBECTL_VERSION=v1.37.1', command[-1])
            self.assertIn('test -z "$existing" || exit 73', command[-1])
            self.assertIn('bortus:release-' + self.commit, command[-1])
        result = {'config_image_id': 'sha256:' + '3' * 64, 'image_bytes': 12345, 'labels': run.record.get('labels')}
        if self.inspect_change: self.inspect_change(result)
        raw = self.tag_output if stage == 'tag-check' else json.dumps(result).encode() if stage == 'inspect' else b'PUBLIC COMPLETE BUILD OUTPUT\n'
        def child(*args, **kwargs):
            self.assertTrue(kwargs['start_new_session']); self.assertFalse(kwargs['check'])
            kwargs['stdout'].write(raw); kwargs['stderr'].write(b'PUBLIC SEPARATE STDERR\n')
            if self.stage_action: self.stage_action(run, stage)
            return types.SimpleNamespace(returncode=self.stage_codes.get(stage, 0))
        with mock.patch.object(m.subprocess, 'run', side_effect=child):
            return m.execute(run, stage, command, timeout, stdin)

    def build(self, **kwargs):
        args = dict(context=self.context, manifest=self.manifest, commit=self.commit, context_sha=self.context_sha,
            manifest_sha=self.manifest_sha, runtime_parent=self.parent, invoke=self.fake)
        args.update(kwargs); return m.build(**args)

    def refuses_before_ssh(self):
        with self.assertRaises(Exception): self.build()
        self.assertEqual([], self.calls)

    def test_complete_fixed_build_source_labels_protected_logs_and_no_runtime_claim(self):
        result = self.build()
        self.assertEqual(['tag-check', 'build', 'inspect'], self.calls)
        self.assertEqual('completed', result['phase']); self.assertEqual(0, result['build_exit_code'])
        self.assertFalse(result['deployed']); self.assertFalse(result['runtime_accepted'])
        self.assertFalse(result['runtime_digest_qualified']); self.assertIsNone(result['image_manifest_digest'])
        self.assertEqual('sha256:' + '3' * 64, result['config_image_id'])
        directory = self.parent / ('bortus-release-' + self.commit)
        self.assertEqual(0o700, stat.S_IMODE(directory.stat().st_mode))
        for path in directory.iterdir():
            self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
        for stage in self.calls:
            for suffix in ('stdout', 'stderr'):
                self.assertEqual(m.digest((directory / (stage + '.' + suffix)).read_bytes()), result[stage + '_' + suffix + '_sha256'])
        self.assertEqual(result, self.record())
        self.assertEqual(self.context_sha, result['labels'][m.LABEL_KEYS[2]])
        self.assertEqual(self.manifest_sha, result['labels'][m.LABEL_KEYS[3]])

    def test_actual_raw_git_producer_archive_is_supported(self):
        spec = importlib.util.spec_from_file_location('context_fixture', HERE / 'test_bortus_release_context.py')
        fixture_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture_module)
        fixture = fixture_module.ReleaseContextTests('test_archive_is_deterministic_across_output_paths')
        fixture.setUp()
        try:
            record = fixture.prepare()
            with fixture.output.open('rb') as archive:
                self.assertEqual(record, m.verify(archive, fixture.evidence.read_bytes(), fixture.commit,
                    record['context_sha256'], m.digest(fixture.evidence.read_bytes())))
        finally: fixture.doCleanups()

    def test_long_non_ascii_pax_path_is_supported(self):
        self.payloads['src/' + 'long-public-name-' * 12 + '\u00e9.ts'] = b'PUBLIC PAX SOURCE\n'
        self.prepare(); self.assertEqual('completed', self.build()['phase'])

    def test_exact_input_hash_commit_and_closed_manifest(self):
        for key, value in [('commit', 'HEAD'), ('commit', 'A' * 40), ('context_sha', '0' * 64), ('manifest_sha', '0' * 64)]:
            with self.subTest(key=key), self.assertRaises(Exception): self.build(**{key: value})
            self.assertEqual([], self.calls)
            # Different disposable run per refusal; never replay the retained directory.
            if any(self.parent.iterdir()): self.parent = self.directory / ('runtime-' + key + value[:4]); self.parent.mkdir()
        for change in [lambda r: r.update(unexpected=True), lambda r: r.update(included_files=True),
                       lambda r: r.update(excluded_entries=2000), lambda r: r.update(started_at_utc={}),
                       lambda r: r.update(working_tree_read=True), lambda r: r.update(application_tree='bad'),
                       lambda r: r.update(migrations=[]), lambda r: r['files'].append(r['files'][0])]:
            self.prepare(manifest_change=change)
            self.parent = self.directory / ('manifest-' + str(len(list(self.directory.iterdir())))); self.parent.mkdir()
            self.refuses_before_ssh()

    def test_json_duplicate_keys_refuse_even_with_pinned_hash(self):
        raw = self.manifest.read_bytes().replace(b'"source_commit":', b'"source_commit":"' + self.commit.encode() + b'", "source_commit":', 1)
        self.manifest.write_bytes(raw); self.manifest_sha = m.digest(raw); self.refuses_before_ssh()

    def test_missing_required_and_excluded_paths_refuse(self):
        self.payloads.pop('Dockerfile'); self.prepare(); self.refuses_before_ssh()
        self.parent = self.directory / 'other'; self.parent.mkdir()
        self.payloads['Dockerfile'] = b'PUBLIC'; self.payloads['nested/.env.fixture'] = b'PUBLIC'; self.prepare(); self.refuses_before_ssh()

    def test_unsafe_member_paths_and_nonregular_types_refuse(self):
        for name in ('../escape', '/absolute', 'src//empty', 'src/./dot', 'a\\b', 'a:b'):
            with self.subTest(name=name):
                buffer = io.BytesIO(); raw = self.context.read_bytes()
                with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as source, tarfile.open(fileobj=buffer, mode='w') as out:
                    for member in source:
                        member.name = name; out.addfile(member, source.extractfile(member))
                changed = gzip.compress(buffer.getvalue(), mtime=0)
                record = json.loads(self.manifest.read_bytes()); record.update(context_sha256=m.digest(changed), context_bytes=len(changed))
                with self.assertRaises(Exception): m.verify(io.BytesIO(changed), json.dumps(record).encode(), self.commit,
                    m.digest(changed), m.digest(json.dumps(record).encode()))
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.DIRTYPE, tarfile.FIFOTYPE, tarfile.GNUTYPE_LONGNAME, tarfile.XGLTYPE):
            self.prepare(member_change=lambda x: setattr(x, 'type', kind))
            with self.subTest(kind=kind), self.assertRaises(Exception):
                m.verify(io.BytesIO(self.context.read_bytes()), self.manifest.read_bytes(), self.commit, self.context_sha, self.manifest_sha)

    def test_member_mode_owner_hash_duplicate_and_hidden_trailing_refuse(self):
        changes = [lambda x: setattr(x, 'mode', 0o600), lambda x: setattr(x, 'uid', 1),
                   lambda x: setattr(x, 'mtime', 1), lambda x: setattr(x, 'uname', 'public'),
                   lambda x: x.pax_headers.update(comment='not-producer')]
        for change in changes:
            self.prepare(member_change=change)
            with self.subTest(change=change), self.assertRaises(Exception):
                m.verify(io.BytesIO(self.context.read_bytes()), self.manifest.read_bytes(), self.commit, self.context_sha, self.manifest_sha)
        self.prepare(manifest_change=lambda r: r['files'][0].update(git_blob='0' * 40))
        self.refuses_before_ssh()
        self.prepare(tar_change=lambda raw: raw + b'PUBLIC HIDDEN PAYLOAD')
        with self.assertRaises(Exception): m.verify(io.BytesIO(self.context.read_bytes()), self.manifest.read_bytes(), self.commit, self.context_sha, self.manifest_sha)
        self.prepare(tar_change=lambda raw: raw.replace(b'PUBLIC SOURCE FIXTURE', b'ALTERED SOURCE FIXTUR', 1))
        with self.assertRaises(Exception): m.verify(io.BytesIO(self.context.read_bytes()), self.manifest.read_bytes(), self.commit, self.context_sha, self.manifest_sha)

    def test_tar_header_size_and_decompressed_bounds_refuse(self):
        self.prepare()
        for bound, value in [('MAX_ARCHIVE_BYTES', 20), ('MAX_MANIFEST_BYTES', 20)]:
            with mock.patch.object(m, bound, value), self.assertRaises(Exception):
                m.verify(io.BytesIO(self.context.read_bytes()), self.manifest.read_bytes(), self.commit, self.context_sha, self.manifest_sha)
        with mock.patch.object(m.producer, 'MAX_FILE_BYTES', 1), self.assertRaises(Exception):
            m.verify(io.BytesIO(self.context.read_bytes()), self.manifest.read_bytes(), self.commit, self.context_sha, self.manifest_sha)
        info = tarfile.TarInfo('public'); info.type = tarfile.XHDTYPE; info.size = 8193
        archive = gzip.compress(info.tobuf() + b'\0' * 10240, mtime=0)
        record = json.loads(self.manifest.read_bytes()); record.update(context_bytes=len(archive), context_sha256=m.digest(archive))
        with self.assertRaises(m.BuildRefused): m.verify(io.BytesIO(archive), json.dumps(record).encode(), self.commit, m.digest(archive), m.digest(json.dumps(record).encode()))

    def test_complete_tar_inventory_duplicate_missing_and_gzip_expansion_refuse(self):
        raw = gzip.decompress(self.context.read_bytes())
        for altered in (raw[:1024] + raw, raw[1024:]):
            archive = gzip.compress(altered, mtime=0)
            record = json.loads(self.manifest.read_bytes()); record.update(context_sha256=m.digest(archive), context_bytes=len(archive))
            manifest = json.dumps(record).encode()
            with self.assertRaises(Exception): m.verify(io.BytesIO(archive), manifest, self.commit, m.digest(archive), m.digest(manifest))
        with mock.patch.object(m, 'MAX_ARCHIVE_BYTES', len(self.context.read_bytes()) + 1024), self.assertRaises(m.BuildRefused):
            m.verify(io.BytesIO(self.context.read_bytes()), self.manifest.read_bytes(), self.commit, self.context_sha, self.manifest_sha)

    def test_mutated_record_or_midstream_context_never_grants_completion(self):
        for target in ('record', 'stream'):
            self.parent = self.directory / ('mutate-' + target); self.parent.mkdir()
            def action(run, stage):
                if stage != ('tag-check' if target == 'record' else 'build'): return
                path = run.directory / ('record.json' if target == 'record' else 'context.tar.gz')
                with path.open('r+b') as stream: stream.write(b'ALTERED')
            self.stage_action = action
            with self.subTest(target=target), self.assertRaises(m.BuildRefused): self.build()
            self.assertNotIn('inspect', self.calls)
            if target == 'record': self.assertNotIn('build', self.calls)
            else: self.assertEqual('uncertain', self.record()['phase'])
            self.calls.clear()

    def test_descriptor_close_failure_still_closes_other_owned_handles(self):
        run = m.Run(self.parent, self.commit); count = 0; original = os.close
        expected = len(run.anchors) + 1
        def close(fd):
            nonlocal count
            count += 1; original(fd)
            if count == 1: raise OSError('PUBLIC CLOSE FAULT AFTER CLOSE')
        with mock.patch.object(m.os, 'close', side_effect=close), self.assertRaises(m.BuildRefused): run.close()
        self.assertEqual(expected, count)

    def test_symlink_fifo_writable_and_changed_input_refuse_without_ssh(self):
        self.context.unlink(); self.context.symlink_to(self.manifest); self.refuses_before_ssh()
        self.context.unlink(); os.mkfifo(self.context)
        self.parent = self.directory / 'fifo'; self.parent.mkdir(); self.refuses_before_ssh()
        self.context.unlink(); self.prepare(); self.context.chmod(0o666)
        self.parent = self.directory / 'writable'; self.parent.mkdir(); self.refuses_before_ssh()
        self.context.chmod(0o600); self.parent = self.directory / 'changed'; self.parent.mkdir()
        original = os.read; changed = False
        def read(fd, amount):
            nonlocal changed
            raw = original(fd, amount)
            if raw and not changed:
                changed = True; self.manifest.write_bytes(self.manifest.read_bytes() + b' ')
            return raw
        with mock.patch.object(m.os, 'read', side_effect=read): self.refuses_before_ssh()

    def test_parent_write_permissions_and_symlink_refuse(self):
        for mode in (0o775, 0o777):
            self.parent.chmod(mode); self.refuses_before_ssh()
        self.parent.chmod(0o755); link = self.directory / 'linked'; link.symlink_to(self.parent)
        with self.assertRaises(Exception): self.build(runtime_parent=link)
        self.assertEqual([], self.calls)

    def test_existing_run_refuses_without_replay_or_overwrite(self):
        result = self.build(); before = self.record(); self.calls.clear()
        with self.assertRaises(Exception): self.build()
        self.assertEqual([], self.calls); self.assertEqual(before, self.record()); self.assertEqual('completed', result['phase'])

    def test_parent_file_and_directory_fsync_failure_prevents_dispatch(self):
        original = os.fsync
        for target in ('parent', 'file', 'run'):
            self.parent = self.directory / ('flush-' + target); self.parent.mkdir()
            def flush(fd):
                info = os.fstat(fd)
                selected = (target == 'parent' and info.st_ino == self.parent.stat().st_ino) or \
                    (target == 'file' and stat.S_ISREG(info.st_mode)) or \
                    (target == 'run' and stat.S_ISDIR(info.st_mode) and info.st_ino != self.parent.stat().st_ino)
                if selected: raise OSError('PUBLIC FLUSH FAULT')
                return original(fd)
            with mock.patch.object(m.os, 'fsync', side_effect=flush): self.refuses_before_ssh()

    def test_pending_save_failure_never_dispatches_build(self):
        original = m.Run.save
        def save(run):
            if run.record['phase'] == 'pending': raise OSError('PUBLIC PENDING FAULT')
            return original(run)
        with mock.patch.object(m.Run, 'save', save), self.assertRaises(m.BuildRefused): self.build()
        self.assertEqual(['tag-check'], self.calls)

    def test_ownership_and_context_tampering_after_tag_check_prevents_build(self):
        for target in ('context-replace', 'context-edit', 'manifest-edit', 'parent-replace'):
            self.parent = self.directory / target; self.parent.mkdir()
            def action(run, stage):
                if stage != 'tag-check': return
                path = run.directory / ('manifest.json' if target == 'manifest-edit' else 'context.tar.gz')
                if target == 'parent-replace':
                    run.parent.rename(run.parent.with_name(run.parent.name + '-old')); run.parent.mkdir()
                elif target == 'context-replace':
                    raw = path.read_bytes(); path.unlink(); path.write_bytes(raw); path.chmod(0o600)
                else:
                    with path.open('r+b') as out: out.write(b'ALTERED')
            self.stage_action = action
            with self.subTest(target=target), self.assertRaises(Exception): self.build()
            self.assertNotIn('build', self.calls); self.calls.clear()

    def test_existing_tag_or_failed_tag_query_does_not_build(self):
        for output, code in [(b'public-existing-image\n', 0), (b'', 255), (b'', 1)]:
            self.parent = self.directory / ('tag-' + str(code) + str(len(output))); self.parent.mkdir()
            self.tag_output = output; self.stage_codes['tag-check'] = code
            with self.assertRaises(m.BuildRefused): self.build()
            self.assertEqual(['tag-check'], self.calls); self.assertEqual('refused', self.record()['phase']); self.calls.clear()

    def test_build_known_failure_guard_refusal_and_lost_reply_are_distinct(self):
        for code, phase in [(1, 'failed'), (73, 'refused'), (255, 'uncertain')]:
            self.parent = self.directory / ('build-' + str(code)); self.parent.mkdir()
            self.stage_codes['build'] = code
            with self.assertRaises(m.BuildRefused): self.build()
            self.assertEqual(['tag-check', 'build'], self.calls); self.calls.clear()
            self.assertEqual(phase, self.record()['phase']); self.assertEqual(code, self.record()['build_exit_code'])

    def test_timeout_and_arbitrary_lost_reply_retain_uncertain_fixed_failure(self):
        for error in (subprocess.TimeoutExpired('public-fixture', 1), RuntimeError('PRIVATE FAULT MUST NOT ESCAPE')):
            self.parent = self.directory / ('lost-' + str(len(list(self.directory.iterdir())))); self.parent.mkdir()
            def action(run, stage):
                if stage == 'build': raise error
            self.stage_action = action
            with self.assertRaises(m.BuildRefused) as failure: self.build()
            self.assertIsNone(failure.exception.__context__)
            self.assertNotIn('PRIVATE FAULT', str(failure.exception)); self.assertEqual('uncertain', self.record()['phase'])
            self.assertNotIn('inspect', self.calls); self.calls.clear()

    def test_postreply_save_failure_leaves_prior_pending_and_no_replay(self):
        original = m.Run.save
        def save(run):
            if 'build_exit_code' in run.record: raise OSError('PUBLIC POSTREPLY SAVE FAULT')
            return original(run)
        with mock.patch.object(m.Run, 'save', save), self.assertRaises(m.BuildRefused): self.build()
        self.assertEqual('pending', self.record()['phase']); self.assertEqual(['tag-check', 'build'], self.calls)
        self.calls.clear()
        with self.assertRaises(Exception): self.build()
        self.assertEqual([], self.calls)

    def test_image_label_config_id_size_and_inspect_error_refuse_acceptance(self):
        for change in (lambda r: r.update(config_image_id='manifest:wrong'), lambda r: r.update(image_bytes=True),
                       lambda r: r.update(image_bytes=0), lambda r: r.update(labels={}), lambda r: r.update(extra='public')):
            self.parent = self.directory / ('inspect-' + str(len(list(self.directory.iterdir())))); self.parent.mkdir()
            self.inspect_change = change
            with self.assertRaises(m.BuildRefused): self.build()
            self.assertEqual('uncertain', self.record()['phase']); self.assertEqual(['tag-check', 'build', 'inspect'], self.calls); self.calls.clear()
        self.inspect_change = None; self.stage_codes['inspect'] = 1
        self.parent = self.directory / 'inspect-exit'; self.parent.mkdir()
        with self.assertRaises(m.BuildRefused): self.build()
        self.assertEqual('uncertain', self.record()['phase'])

    def test_descriptors_closed_on_success_failure_and_partial_log_creation(self):
        before = set(os.listdir('/proc/self/fd')); self.build()
        self.assertEqual(before, set(os.listdir('/proc/self/fd')))
        self.parent = self.directory / 'log-failure'; self.parent.mkdir()
        original = m.Run.create
        def create(run, name):
            if name == 'tag-check.stderr': raise OSError('PUBLIC LOG CREATE FAULT')
            return original(run, name)
        with mock.patch.object(m.Run, 'create', create), self.assertRaises(m.BuildRefused): self.build()
        self.assertEqual(before, set(os.listdir('/proc/self/fd')))

    def test_log_flush_failure_after_dispatch_is_uncertain(self):
        original = os.fsync; active = False
        def action(run, stage):
            nonlocal active
            if stage == 'build': active = True
        def flush(fd):
            if active and stat.S_ISREG(os.fstat(fd).st_mode): raise OSError('PUBLIC LOG FLUSH FAULT')
            return original(fd)
        self.stage_action = action
        with mock.patch.object(m.os, 'fsync', side_effect=flush), self.assertRaises(m.BuildRefused): self.build()
        self.assertEqual('pending', self.record()['phase']); self.assertNotIn('inspect', self.calls)


if __name__ == '__main__': unittest.main()
