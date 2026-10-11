"""Public archive/POSIX fixtures; Docker/SSH/sudo/ctr are mocked, never executed."""
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
import tarfile
import tempfile
import types
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE.parent / filename)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
s = load('release_stage', 'stage-bortus-release-image.py')
n = load('release_node', 'bortus-release-preload-node.py')


class StageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='bortus-stage-fixture-', dir=pathlib.Path.home()); self.addCleanup(self.tmp.cleanup)
        self.path = pathlib.Path(self.tmp.name); self.runtime = self.path / 'runtime'; self.runtime.mkdir(mode=0o755)
        self.commit = '1' * 40; self.tag = 'bortus:release-' + self.commit
        self.labels = dict(zip(s.b.LABEL_KEYS, [self.commit, '2' * 40, '3' * 64, '4' * 64, '50000000-0000-0000-0000-000000000001']))
        self.receipt_path = self.path / 'build.json'; self.exports = []; self.imports = []; self.node_calls = []
        self.save_code = 0; self.export_action = None; self.node_action = None; self.inspect_mutation = None
        self.existing_tag = None; self.raw_content_mutation = None; self.node_reply_mutation = None
        self.archive_bytes = self.archive(); self.prepare_receipt(); self.graph()

    def archive(self, compressed=False, config_change=None, manifest_change=None, extra=None, member_change=None):
        self.layer = b'PUBLIC OPAQUE LAYER FIXTURE\n' * 3
        config = {'os': 'linux', 'architecture': 'amd64', 'config': {'Labels': self.labels,
            'Env': ['PUBLIC_PRIVATE_ENV_SENTINEL=fixture']}, 'rootfs': {'type': 'layers', 'diff_ids': ['sha256:' + s.b.digest(self.layer)]}}
        if config_change: config_change(config)
        self.config_raw = json.dumps(config, sort_keys=True).encode(); self.config_id = 'sha256:' + s.b.digest(self.config_raw)
        self.layer_raw = gzip.compress(self.layer, mtime=0) if compressed else self.layer
        self.layer_digest = 'sha256:' + s.b.digest(self.layer_raw)
        config_name = 'blobs/sha256/' + self.config_id[7:]; layer_name = 'blobs/sha256/' + self.layer_digest[7:]
        manifest = [{'Config': config_name, 'RepoTags': [self.tag], 'Layers': [layer_name]}]
        if manifest_change: manifest_change(manifest)
        files = {config_name: self.config_raw, layer_name: self.layer_raw, 'manifest.json': json.dumps(manifest).encode()}
        if extra: files.update(extra)
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w', format=tarfile.PAX_FORMAT) as archive:
            for name, raw in files.items():
                item = tarfile.TarInfo(name); item.size = len(raw); item.mode = 0o644
                if member_change: member_change(item)
                archive.addfile(item, io.BytesIO(raw) if item.isfile() else None)
        return buffer.getvalue()

    def prepare_receipt(self):
        record = {'scope': 'Immutable BORTUS image build only; no runtime/deployment acceptance', 'phase': 'completed',
            'source_commit': self.commit, 'image_tag': self.tag, 'config_image_id': self.config_id,
            'build_exit_code': 0, 'inspect_exit_code': 0, 'tag-check_exit_code': 0, 'image_bytes': 12345,
            'application_tree': '2' * 40, 'context_sha256': '3' * 64, 'manifest_sha256': '4' * 64,
            'owner': self.labels[s.b.LABEL_KEYS[4]], 'labels': self.labels, 'deployed': False,
            'runtime_accepted': False, 'runtime_digest_qualified': False, 'image_manifest_digest': None}
        self.receipt_path.write_bytes(json.dumps(record).encode()); self.receipt_path.chmod(0o600)
        self.receipt_sha = s.b.digest(self.receipt_path.read_bytes())

    def graph(self, index=False):
        manifest = {'schemaVersion': 2, 'mediaType': 'application/vnd.oci.image.manifest.v1+json',
            'config': {'digest': self.config_id, 'size': len(self.config_raw)},
            'layers': [{'digest': self.layer_digest, 'size': len(self.layer_raw)}]}
        self.manifest_raw = json.dumps(manifest).encode(); self.selected_digest = 'sha256:' + s.b.digest(self.manifest_raw)
        root = {'schemaVersion': 2, 'mediaType': 'application/vnd.oci.image.index.v1+json', 'manifests': [
            {'digest': self.selected_digest, 'size': len(self.manifest_raw), 'platform': {'os': 'linux', 'architecture': 'amd64'}}]}
        self.root_raw = json.dumps(root).encode() if index else self.manifest_raw
        self.root_digest = 'sha256:' + s.b.digest(self.root_raw)
        self.contents = {self.root_digest: self.root_raw, self.selected_digest: self.manifest_raw, self.config_id: self.config_raw}

    def fake_export(self, run, stage, command, timeout, archive=None):
        self.exports.append(stage); self.assertEqual(s.b.SSH, command[:len(s.b.SSH)])
        if stage == 'save':
            self.assertEqual('pending', json.loads((run.directory / 'record.json').read_bytes())['phase'])
            self.assertIn('docker image save ' + self.tag, command[-1]); archive.write(self.archive_bytes)
        else:
            result = {'config_image_id': self.config_id, 'labels': self.labels}
            if self.inspect_mutation: self.inspect_mutation(result, stage)
            fd = run.create(stage + '.stdout')
            with os.fdopen(fd, 'wb') as out: out.write(json.dumps(result).encode())
        if self.export_action: self.export_action(run, stage)
        run.record[stage + '_exit_code'] = self.save_code if stage == 'save' else 0
        return self.save_code if stage == 'save' else 0

    def export(self):
        self.exported = s.export_image(self.receipt_path, self.receipt_sha, self.commit, self.config_id, self.runtime, self.fake_export)
        self.export_receipt = self.runtime / ('bortus-export-' + self.commit) / 'record.json'
        self.export_sha = s.b.digest(self.export_receipt.read_bytes()); return self.exported

    def request(self):
        return {'sudo_password': 'PUBLIC_SUDO_FIXTURE_INPUT', 'source_commit': self.commit, 'config_image_id': self.config_id,
            'labels': copy.deepcopy(self.labels), 'archive_bytes': len(self.archive_bytes), 'archive_sha256': s.b.digest(self.archive_bytes),
            'layer_blob_digests': [self.layer_digest], 'ordered_diff_ids': ['sha256:' + s.b.digest(self.layer)]}

    def fake_ctr(self, run, stage, argv, **kwargs):
        self.node_calls.append(stage); self.assertEqual(n.CTR, argv[:len(n.CTR)])
        self.assertNotIn('PUBLIC_SUDO_FIXTURE_INPUT', json.dumps(argv))
        header = b'REF TYPE DIGEST SIZE PLATFORMS LABELS\n'
        if self.node_action: self.node_action(run, stage)
        if stage in ('images-before', 'images-preimport'):
            tag = self.existing_tag
            return header + ((tag + ' type sha256:' + '6' * 64 + ' size linux/amd64 -\n').encode() if tag else b'')
        if stage == 'import':
            self.assertEqual('pending', json.loads((run.path / 'record.json').read_bytes())['phase'])
            self.assertEqual(self.archive_bytes, (run.path / 'image.tar').read_bytes())
            self.assertEqual(0o600, stat.S_IMODE((run.path / 'image.tar').stat().st_mode)); return b''
        if stage == 'images-after': return header + (self.tag + ' type ' + self.root_digest + ' size linux/amd64 -\n').encode()
        raw = self.contents[argv[-1]]
        if self.raw_content_mutation: raw = self.raw_content_mutation(stage, raw)
        return raw

    def fake_node(self, run, host, request, archive):
        self.imports.append(host)
        disk = json.loads((run.directory / 'record.json').read_bytes()); self.assertEqual('pending', disk['nodes'][-1]['phase'])
        self.assertEqual(host, disk['nodes'][-1]['host'])
        home = self.path / ('home-' + host); home.mkdir(mode=0o755)
        result = n.receive(copy.deepcopy(request), archive, home, self.fake_ctr,
            authorize=lambda password: password == 'PUBLIC_SUDO_FIXTURE_INPUT')
        if self.node_reply_mutation: self.node_reply_mutation(result, host)
        return result

    def preload(self):
        return s.preload(self.receipt_path, self.receipt_sha, self.export_receipt, self.export_sha, self.commit,
            self.config_id, self.runtime, 'PUBLIC_SUDO_FIXTURE_INPUT', self.fake_node)

    def test_export_and_three_sequential_imports_exact_identities_not_runtime_acceptance(self):
        before = set(os.listdir('/proc/self/fd')); exported = self.export(); result = self.preload()
        self.assertEqual(['source-before', 'save', 'source-after'], self.exports)
        self.assertEqual(list(s.HOSTS), self.imports); self.assertEqual('completed', result['phase'])
        self.assertFalse(result['runtime_qualified']); self.assertFalse(result['deployed'])
        self.assertEqual(s.b.digest(self.archive_bytes), exported['archive_sha256'])
        self.assertEqual(self.config_id, exported['config_image_id']); self.assertNotEqual(self.config_id, self.root_digest)
        self.assertTrue(all(node['runtime_manifest_digest'] == self.root_digest for node in result['nodes']))
        self.assertEqual(before, set(os.listdir('/proc/self/fd')))
        for root in [self.runtime, *[self.path / ('home-' + host) for host in s.HOSTS]]:
            for path in root.rglob('*'):
                if path.is_file():
                    self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
                    self.assertNotIn(b'PUBLIC_SUDO_FIXTURE_INPUT', path.read_bytes())
                    if path.name != 'image.tar': self.assertNotIn(b'PUBLIC_PRIVATE_ENV_SENTINEL', path.read_bytes())

    def test_compressed_layers_and_platform_index_resolve_distinct_digests(self):
        self.archive_bytes = self.archive(compressed=True); self.prepare_receipt(); self.graph(index=True)
        self.export(); result = self.preload()
        self.assertNotEqual(self.root_digest, self.selected_digest)
        self.assertEqual(self.selected_digest, result['nodes'][0]['selected_manifest_digest'])

    def test_build_receipt_hash_scope_and_source_label_fail_before_save(self):
        for change in (lambda r: r.update(phase='pending'), lambda r: r.update(config_image_id='sha256:' + '0' * 64),
                       lambda r: r.update(build_exit_code=True), lambda r: r['labels'].update(unexpected='public'),
                       lambda r: r.update(runtime_accepted=True)):
            self.runtime = self.path / ('invalid-' + str(len(list(self.path.iterdir())))); self.runtime.mkdir()
            self.prepare_receipt(); record = json.loads(self.receipt_path.read_bytes()); change(record)
            self.receipt_path.write_bytes(json.dumps(record).encode()); self.receipt_sha = s.b.digest(self.receipt_path.read_bytes())
            with self.assertRaises(s.b.BuildRefused): self.export()
            self.assertEqual([], self.exports)
        self.runtime = self.path / 'invalid-hash'; self.runtime.mkdir(); self.prepare_receipt(); self.receipt_sha = '0' * 64
        with self.assertRaises(s.b.BuildRefused): self.export()
        self.assertEqual([], self.exports)

    def test_source_tag_identity_change_refuses_before_or_after_save(self):
        for target in ('source-before', 'source-after'):
            self.runtime = self.path / target; self.runtime.mkdir()
            def mutate(result, stage):
                if stage == target: result['labels'] = {}
            self.inspect_mutation = mutate
            with self.assertRaises(s.b.BuildRefused): self.export()
            if target == 'source-before': self.assertNotIn('save', self.exports)
            else:
                disk = json.loads((self.runtime / ('bortus-export-' + self.commit) / 'record.json').read_bytes())
                self.assertEqual('uncertain', disk['phase'])
            self.exports.clear()

    def test_save_lost_reply_and_postreply_flush_uncertainty_never_replays(self):
        self.save_code = 255
        with self.assertRaises(s.b.BuildRefused): self.export()
        run = self.runtime / ('bortus-export-' + self.commit); self.assertEqual('uncertain', json.loads((run / 'record.json').read_bytes())['phase'])
        original = (run / 'image.tar').read_bytes(); self.exports.clear()
        with self.assertRaises(Exception): self.export()
        self.assertEqual([], self.exports); self.assertEqual(original, (run / 'image.tar').read_bytes())

    def test_export_pending_flush_failure_has_no_save_dispatch(self):
        original = s.OperationRun.save
        def save(run):
            if run.record['phase'] == 'pending': raise OSError('PUBLIC FSYNC FAULT')
            return original(run)
        with mock.patch.object(s.OperationRun, 'save', save), self.assertRaises(s.b.BuildRefused): self.export()
        self.assertEqual(['source-before'], self.exports)

    def test_wrong_archive_config_tag_diff_ids_or_platform_refuse(self):
        changes = [dict(config_change=lambda r: r.update(os='windows')),
            dict(config_change=lambda r: r['rootfs'].update(diff_ids=['sha256:' + '0' * 64])),
            dict(config_change=lambda r: r['config'].update(Labels={})),
            dict(manifest_change=lambda r: r[0].update(RepoTags=['unrelated:tag'])),
            dict(manifest_change=lambda r: r.append(copy.deepcopy(r[0])))]
        for change in changes:
            self.runtime = self.path / ('archive-' + str(len(list(self.path.iterdir())))); self.runtime.mkdir()
            self.archive_bytes = self.archive(**change); self.prepare_receipt()
            with self.assertRaises(s.b.BuildRefused): self.export()
            self.assertNotIn('source-after', self.exports); self.exports.clear()

    def test_unsafe_nonregular_duplicate_trailing_and_archive_bounds_refuse(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.GNUTYPE_LONGNAME, tarfile.XGLTYPE):
            raw = self.archive(member_change=lambda x: setattr(x, 'type', kind))
            path = self.path / 'bad.tar'; path.write_bytes(raw)
            with path.open('rb') as stream, self.subTest(kind=kind), self.assertRaises(Exception):
                s.archive_identity(stream, self.tag, self.config_id, self.labels)
        for raw in (self.archive(extra={'../escape': b'PUBLIC'}), self.archive() + b'NONZERO TRAILING',
                    self.archive()[:1024] + self.archive()):
            path = self.path / 'bad.tar'; path.write_bytes(raw)
            with path.open('rb') as stream, self.assertRaises(Exception): s.archive_identity(stream, self.tag, self.config_id, self.labels)
        path.write_bytes(self.archive())
        for target, size in [('MAX_ARCHIVE', 32), ('MAX_METADATA', 8), ('MAX_MEMBERS', 1)]:
            with mock.patch.object(s, target, size), path.open('rb') as stream, self.assertRaises(Exception):
                s.archive_identity(stream, self.tag, self.config_id, self.labels)

    def test_archive_bit_change_and_export_receipt_mismatch_prevent_any_node(self):
        self.export(); archive = pathlib.Path(self.exported['archive_path'])
        with archive.open('r+b') as out: out.write(b'ALTERED')
        with self.assertRaises(s.b.BuildRefused): self.preload()
        self.assertEqual([], self.imports)

    def test_lost_node_reply_stops_sequence_and_preserves_pending_no_retry(self):
        self.export()
        def lost(run, host, request, archive): self.imports.append(host); raise RuntimeError('PRIVATE ERROR WITHHELD')
        with self.assertRaises(s.b.BuildRefused) as failed:
            s.preload(self.receipt_path, self.receipt_sha, self.export_receipt, self.export_sha, self.commit,
                self.config_id, self.runtime, 'PUBLIC_SUDO_FIXTURE_INPUT', lost)
        self.assertIsNone(failed.exception.__context__); self.assertEqual([s.HOSTS[0]], self.imports)
        disk = json.loads((self.runtime / ('bortus-preload-' + self.commit) / 'record.json').read_bytes())
        self.assertEqual('uncertain', disk['phase']); self.assertEqual('uncertain', disk['nodes'][0]['phase'])
        self.imports.clear()
        with self.assertRaises(Exception): self.preload()
        self.assertEqual([], self.imports)

    def test_node_reply_identity_digest_disagreement_and_false_acceptance_stop(self):
        for field, value in [('config_image_id', 'sha256:' + '0' * 64), ('runtime_qualified', True), ('labels', {})]:
            self.runtime = self.path / ('reply-' + field); self.runtime.mkdir(); self.export()
            def mutate(result, host): result[field] = value
            self.node_reply_mutation = mutate
            with self.assertRaises(s.b.BuildRefused): self.preload()
            self.assertEqual([s.HOSTS[0]], self.imports); self.imports.clear()
            for home in self.path.glob('home-*'): home.rename(home.with_name(home.name + '-' + field))
        self.runtime = self.path / 'digest-disagreement'; self.runtime.mkdir(); self.export()
        def mutate(result, host):
            if host == s.HOSTS[1]: result['runtime_manifest_digest'] = 'sha256:' + '0' * 64
        self.node_reply_mutation = mutate
        with self.assertRaises(s.b.BuildRefused): self.preload()
        self.assertEqual(list(s.HOSTS[:2]), self.imports)

    def direct_node(self, **kwargs):
        home = self.path / ('node-' + str(len(list(self.path.iterdir())))); home.mkdir(mode=0o755)
        request = self.request(); source = io.BytesIO(self.archive_bytes)
        return n.receive(request, source, home, kwargs.get('invoke', self.fake_ctr), authorize=kwargs.get('authorize', lambda p: True))

    def test_existing_either_tag_spelling_and_malformed_inventory_refuse_no_import(self):
        for tag in (self.tag, 'docker.io/library/' + self.tag):
            self.existing_tag = tag
            with self.assertRaises(RuntimeError): self.direct_node()
            self.assertEqual(['images-before'], self.node_calls); self.node_calls.clear()
        for raw in (b'', b'WRONG HEADER\n', b'REF TYPE DIGEST\npublic type invalid\n'):
            with self.assertRaises(RuntimeError): self.direct_node(invoke=lambda *a, **k: raw)

    def test_unrelated_existing_images_do_not_block_import(self):
        self.existing_tag = 'unrelated:stable'; self.assertEqual('completed', self.direct_node()['phase'])

    def test_remote_authorization_malformed_request_and_archive_hash_refuse(self):
        with self.assertRaises(RuntimeError): self.direct_node(authorize=lambda p: False)
        self.assertEqual([], self.node_calls)
        request = self.request(); request['labels'] = {}
        with self.assertRaises(RuntimeError): n.receive(request, io.BytesIO(self.archive_bytes), self.path, self.fake_ctr, lambda p: True)
        request = self.request(); request['archive_sha256'] = '0' * 64
        home = self.path / 'hash-home'; home.mkdir()
        with self.assertRaises(RuntimeError): n.receive(request, io.BytesIO(self.archive_bytes), home, self.fake_ctr, lambda p: True)
        self.assertNotIn('import', self.node_calls)

    def test_remote_pending_flush_failure_has_no_import_callback(self):
        original = n.NodeRun.save
        def save(run):
            if run.record['phase'] == 'pending': raise OSError('PUBLIC FSYNC FAULT')
            return original(run)
        with mock.patch.object(n.NodeRun, 'save', save), self.assertRaises(RuntimeError): self.direct_node()
        self.assertNotIn('import', self.node_calls)

    def test_remote_archive_replacement_before_or_during_import_refuses_completion(self):
        for stage in ('images-preimport', 'import'):
            def action(run, called):
                if called == stage:
                    path = run.path / 'image.tar'; raw = path.read_bytes(); path.unlink(); path.write_bytes(raw); path.chmod(0o600)
            self.node_action = action
            with self.assertRaises(RuntimeError): self.direct_node()
            if stage == 'images-preimport': self.assertNotIn('import', self.node_calls)
            else: self.assertNotIn('images-after', self.node_calls)
            self.node_calls.clear()

    def test_remote_content_hash_platform_ambiguity_and_layer_drift_refuse(self):
        self.raw_content_mutation = lambda stage, raw: raw + b' ' if stage == 'runtime-config' else raw
        with self.assertRaises(RuntimeError): self.direct_node()
        self.raw_content_mutation = None; self.graph(index=True)
        root = json.loads(self.root_raw); root['manifests'].append(copy.deepcopy(root['manifests'][0]))
        self.root_raw = json.dumps(root).encode(); self.root_digest = 'sha256:' + s.b.digest(self.root_raw); self.contents[self.root_digest] = self.root_raw
        with self.assertRaises(RuntimeError): self.direct_node()
        self.graph(); manifest = json.loads(self.manifest_raw); manifest['layers'][0]['digest'] = 'sha256:' + '0' * 64
        self.root_raw = json.dumps(manifest).encode(); self.root_digest = 'sha256:' + s.b.digest(self.root_raw); self.contents[self.root_digest] = self.root_raw
        with self.assertRaises(RuntimeError): self.direct_node()

    def test_remote_parent_writable_symlink_and_existing_run_refuse(self):
        home = self.path / 'home'; home.mkdir(mode=0o777); home.chmod(0o777)
        with self.assertRaises(RuntimeError): n.NodeRun(home, self.commit)
        home.chmod(0o755); link = self.path / 'link'; link.symlink_to(home)
        with self.assertRaises(Exception): n.NodeRun(link, self.commit)
        first = n.NodeRun(home, self.commit); first.close()
        with self.assertRaises(FileExistsError): n.NodeRun(home, self.commit)

    def test_remote_metadata_capture_has_no_config_env_log_and_launch_fault_no_fd_leak(self):
        home = self.path / 'capture'; home.mkdir(); run = n.NodeRun(home, self.commit); self.addCleanup(run.close)
        config_raw = self.config_raw
        class Process:
            def __init__(self, *args, **kwargs): self.stdout = io.BytesIO(config_raw)
            def wait(self, timeout): return 0
            def kill(self): pass
        with mock.patch.object(n.subprocess, 'Popen', Process):
            self.assertEqual(self.config_raw, n.command(run, 'metadata', ['PUBLIC FIXTURE']))
        self.assertFalse((run.path / 'metadata.stdout').exists())
        before = set(os.listdir('/proc/self/fd'))
        with mock.patch.object(n.subprocess, 'Popen', side_effect=OSError('PUBLIC LAUNCH FAULT')), self.assertRaises(OSError):
            n.command(run, 'fault', ['PUBLIC FIXTURE'], capture=False)
        self.assertEqual(before, set(os.listdir('/proc/self/fd')))

    def test_actual_owned_local_python_export_stream_bound_timeout_and_closure(self):
        # Only a disposable local Python process, never SSH/Docker/ctr.
        import sys
        for purpose in ('ok', 'bound', 'timeout'):
            parent = self.path / ('child-' + purpose); parent.mkdir()
            run = s.OperationRun(parent, self.commit, 'export')
            before = set(os.listdir('/proc/self/fd'))
            fd = run.create('image.tar')
            with os.fdopen(fd, 'w+b') as archive:
                if purpose == 'timeout':
                    args = [sys.executable, '-B', '-c', 'import time; time.sleep(5)']
                    with self.assertRaises(s.b.BuildRefused): s.export_execute(run, 'save', args, 0.05, archive)
                else:
                    args = [sys.executable, '-B', '-c', 'import sys; sys.stdout.buffer.write(b"PUBLIC" * 100)']
                    if purpose == 'bound':
                        with mock.patch.object(s, 'MAX_ARCHIVE', 32), self.assertRaises(s.b.BuildRefused):
                            s.export_execute(run, 'save', args, 5, archive)
                    else:
                        self.assertEqual(0, s.export_execute(run, 'save', args, 5, archive)); archive.flush()
                        self.assertEqual(600, os.fstat(archive.fileno()).st_size)
            self.assertEqual(before, set(os.listdir('/proc/self/fd'))); run.close()

    def test_remote_metadata_overflow_and_timeout_close_owned_mock_process(self):
        home = self.path / 'bounded'; home.mkdir(); run = n.NodeRun(home, self.commit); self.addCleanup(run.close)
        instances = []
        class Process:
            def __init__(self, *args, **kwargs):
                self.stdout = io.BytesIO(b'PUBLIC' * 100); self.killed = False; instances.append(self)
            def wait(self, timeout): return 0
            def kill(self): self.killed = True
        with mock.patch.object(n.subprocess, 'Popen', Process), self.assertRaises(RuntimeError):
            n.command(run, 'overflow', ['PUBLIC FIXTURE'], cap=32)
        self.assertTrue(instances[-1].killed); self.assertTrue(instances[-1].stdout.closed)
        class TimeoutProcess(Process):
            def wait(self, timeout):
                if not self.killed: raise subprocess.TimeoutExpired('PUBLIC FIXTURE', timeout)
                return -9
        with mock.patch.object(n.subprocess, 'Popen', TimeoutProcess), self.assertRaises(RuntimeError):
            n.command(run, 'timeout', ['PUBLIC FIXTURE'])
        self.assertTrue(instances[-1].killed); self.assertTrue(instances[-1].stdout.closed)

    def test_password_is_only_sudo_stdin_not_args_stdout_stderr_or_records(self):
        def authorize(*args, **kwargs):
            self.assertEqual(['sudo', '-S', '-p', '', '-v'], args[0])
            self.assertEqual(b'PUBLIC_SUDO_FIXTURE_INPUT\n', kwargs['input'])
            self.assertEqual(subprocess.DEVNULL, kwargs['stdout']); self.assertEqual(subprocess.DEVNULL, kwargs['stderr'])
            return types.SimpleNamespace(returncode=0)
        home = self.path / 'sudo-home'; home.mkdir()
        with mock.patch.object(n.subprocess, 'run', side_effect=authorize):
            result = n.receive(self.request(), io.BytesIO(self.archive_bytes), home, self.fake_ctr)
        self.assertEqual('completed', result['phase'])
        for path in home.rglob('*'):
            if path.is_file(): self.assertNotIn(b'PUBLIC_SUDO_FIXTURE_INPUT', path.read_bytes())

    def test_sudo_fault_context_withheld_and_password_removed_from_request(self):
        request = self.request()
        with mock.patch.object(n.subprocess, 'run', side_effect=RuntimeError('PUBLIC PRIVATE FAULT DETAIL')):
            with self.assertRaises(RuntimeError) as failure: n.authenticate(request, None)
        self.assertNotIn('sudo_password', request); self.assertIsNone(failure.exception.__context__)
        self.assertEqual('authorization', str(failure.exception))

    def test_export_archive_flush_failure_preserves_pending_without_completion(self):
        original = os.fsync; dispatch = False
        def action(run, stage):
            nonlocal dispatch
            if stage == 'save': dispatch = True
        def flush(fd):
            if dispatch and stat.S_ISREG(os.fstat(fd).st_mode): raise OSError('PUBLIC ARCHIVE FLUSH FAULT')
            return original(fd)
        self.export_action = action
        with mock.patch.object(s.os, 'fsync', side_effect=flush), self.assertRaises(s.b.BuildRefused): self.export()
        disk = json.loads((self.runtime / ('bortus-export-' + self.commit) / 'record.json').read_bytes())
        self.assertEqual('pending', disk['phase']); self.assertNotIn('source-after', self.exports)

    def test_runtime_descriptor_declared_size_mismatch_refuses(self):
        self.graph(index=True); root = json.loads(self.root_raw); root['manifests'][0]['size'] += 1
        self.root_raw = json.dumps(root).encode(); self.root_digest = 'sha256:' + s.b.digest(self.root_raw)
        self.contents[self.root_digest] = self.root_raw
        with self.assertRaises(RuntimeError): self.direct_node()

    def test_export_receipt_scope_acceptance_claim_and_fractional_node_count_refuse(self):
        self.export(); exported = json.loads(self.export_receipt.read_bytes()); exported['runtime_qualified'] = True
        self.export_receipt.write_bytes(json.dumps(exported).encode()); self.export_sha = s.b.digest(self.export_receipt.read_bytes())
        with self.assertRaises(s.b.BuildRefused): self.preload()
        self.assertEqual([], self.imports)
        self.runtime = self.path / 'fractional'; self.runtime.mkdir(); self.export()
        self.node_reply_mutation = lambda result, host: result.update(archive_bytes=float(len(self.archive_bytes)))
        with self.assertRaises(s.b.BuildRefused): self.preload()
        self.assertEqual([s.HOSTS[0]], self.imports)


if __name__ == '__main__': unittest.main()
