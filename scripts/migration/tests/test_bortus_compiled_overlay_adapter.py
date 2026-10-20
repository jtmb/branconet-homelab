"""Finite public mocked adapter controls. No daemon, SSH, sudo, app or old corpus."""
import copy
import importlib.util
import io
import json
import os
import pathlib
import shlex
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s = load('overlay_stage_public', HERE / 'stage-bortus-compiled-overlay.py')
fixture = load('overlay_public_archive_fixture', HERE / 'tests/test_bortus_compiled_overlay_contract.py')


class AdapterControls(unittest.TestCase):
    def setUp(self):
        for target in ('subprocess.Popen', 'subprocess.run', 'os.system'):
            guard = mock.patch(target, side_effect=AssertionError('external execution forbidden'))
            guard.start()
            self.addCleanup(guard.stop)
        # Only the existing public archive generator is used; no old test or
        # runtime/corpus helper is executed.
        self.f = fixture.OverlayControls()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.tmp = tempfile.TemporaryDirectory(prefix='overlay-public-', dir='/home/brajam/.cache')
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.contract = self.f.contract
        self.raw = s.C.encoded(self.contract)
        self.pin = s.IO.digest(self.raw)
        for module in (s.IO, s.N.IO):
            patch = mock.patch.object(module, 'CONTRACT_PIN', self.pin)
            patch.start()
            self.addCleanup(patch.stop)
        self.cp = self.write('contract.json', self.raw)
        self.tools = self.root / 'tools'
        self.tools.mkdir(mode=0o700)
        self.sources = {}
        for key, name in (('io', 'bortus-compiled-overlay-io.py'),
                          ('contract', 'bortus-compiled-overlay-contract.py'),
                          ('node', 'bortus-compiled-overlay-node.py')):
            data = (HERE / name).read_bytes()
            (self.tools / name).write_bytes(data)
            (self.tools / name).chmod(0o600)
            self.sources[key] = data
        patch = mock.patch.object(s, '__file__', str(self.tools / 'stage-bortus-compiled-overlay.py'))
        patch.start()
        self.addCleanup(patch.stop)
        self.calls = []

    def write(self, name, raw):
        path = self.root / name
        path.write_bytes(raw)
        path.chmod(0o600)
        return path

    def parent(self, name):
        path = self.root / name
        path.mkdir(mode=0o700)
        return path

    def record(self, parent, purpose):
        return json.loads((parent / ('bortus-compiled-overlay-' + purpose + '-'
                                    + self.contract['source_commit']) / 'record.json').read_bytes())

    def export_invoke(self, run, stage, argv, **kwargs):
        self.calls.append(stage)
        self.assertEqual(self.record(run.directory.parent, 'export')['phase'],
                         'pending' if stage in ('save', 'source-after') else 'validating')
        if stage == 'save':
            self.assertEqual(argv, ['docker', 'image', 'save', self.contract['image_tag']])
            kwargs['output'].write(self.f.archive_raw)
            return b''
        self.assertEqual(argv[:3], ['docker', 'image', 'inspect'])
        self.assertNotIn('Env', ' '.join(argv))
        return s.IO.encoded({'id': self.contract['local_image_id'], 'labels': self.contract['labels']})

    def exported(self, name='export'):
        parent = self.parent(name)
        result = s.export_image(self.cp, self.pin, parent, self.export_invoke)
        receipt = parent / ('bortus-compiled-overlay-export-' + self.contract['source_commit']) / 'record.json'
        return result, receipt, s.IO.digest(receipt.read_bytes())

    def request(self, ordinal=1):
        packaging = s.C.encoded(s.C.expected_export_record(self.contract))
        env = s.C.preload_envelopes(self.contract, packaging, s.IO.digest(packaging))[ordinal - 1]
        return dict(format=s.IO.FORMAT, purpose='node-preload', contract_raw=self.raw.decode(),
                    contract_sha256=self.pin, envelope=env, export_execution_sha256='a' * 64,
                    sudo_password='PUBLIC_STDIN_SENTINEL')

    def node_invoke(self, run, stage, argv, **kwargs):
        self.calls.append(stage)
        self.assertEqual(argv[:len(s.N.CTR)], s.N.CTR)
        if stage.startswith('images-'):
            return self.f.inventory() if stage == 'images-after' else b'REF TYPE DIGEST SIZE\n'
        if stage == 'import':
            self.assertEqual(self.record(run.directory.parent, 'node')['phase'], 'pending')
            self.assertEqual(argv[-3:], ['images', 'import', str(run.directory / 'image.tar')])
            return b''
        if stage == 'manifest':
            self.assertEqual(argv[-1], self.contract['manifest_digest'])
            return self.f.manifest
        if stage == 'config':
            self.assertEqual(argv[-1], self.contract['raw_config_digest'])
            return self.f.config
        self.fail('unexpected node command')

    def receive(self, request=None, invoke=None, data=None, parent=None, auth=None):
        request = request if request is not None else self.request()
        return s.N.receive(request, io.BytesIO(self.f.archive_raw if data is None else data),
            parent or self.parent('node'), s.C.HOSTS[0], invoke or self.node_invoke,
            auth or (lambda password: password == 'PUBLIC_STDIN_SENTINEL'))

    def test_01_export_positive_and_execution_shape(self):
        result, path, _ = self.exported()
        self.assertEqual(self.calls, ['source-before', 'save', 'source-after'])
        self.assertEqual(result['phase'], 'completed')
        self.assertEqual(s.execution_receipt(path.read_bytes(), self.contract, self.pin), result)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_02_export_source_drift_refuses_before_save(self):
        parent = self.parent('export')
        with self.assertRaises(RuntimeError):
            s.export_image(self.cp, self.pin, parent, lambda *a, **k: b'{}')
        self.assertEqual(self.record(parent, 'export')['phase'], 'refused')
        self.assertEqual(self.calls, [])

    def test_03_export_partial_save_is_uncertain_no_replay(self):
        parent = self.parent('export')
        def invoke(run, stage, argv, **kwargs):
            if stage == 'save':
                kwargs['output'].write(b'PARTIAL')
                raise TimeoutError('PUBLIC')
            return self.export_invoke(run, stage, argv, **kwargs)
        with self.assertRaises(RuntimeError):
            s.export_image(self.cp, self.pin, parent, invoke)
        self.assertEqual(self.record(parent, 'export')['phase'], 'uncertain')
        with self.assertRaises(FileExistsError):
            s.export_image(self.cp, self.pin, parent, self.export_invoke)

    def test_04_export_wrong_archive_and_postsave_drift_uncertain(self):
        for corrupt in (True, False):
            parent = self.parent('export-' + str(corrupt))
            def invoke(run, stage, argv, **kwargs):
                if stage == 'save' and corrupt:
                    kwargs['output'].write(b'BAD')
                    return b''
                if stage == 'source-after':
                    return b'{}'
                return self.export_invoke(run, stage, argv, **kwargs)
            with self.assertRaises(RuntimeError):
                s.export_image(self.cp, self.pin, parent, invoke)
            self.assertEqual(self.record(parent, 'export')['phase'], 'uncertain')

    def test_05_expected_packaging_is_not_execution_receipt(self):
        with self.assertRaises(RuntimeError):
            s.execution_receipt(s.C.encoded(s.C.expected_export_record(self.contract)), self.contract, self.pin)
        value, _, _ = self.exported()
        for key, changed in (('phase', 'pending'), ('purpose', 'preload'), ('save_exit_code', False),
                             ('runtime_qualified', True), ('contract_sha256', 'b' * 64),
                             ('source_commit', 'b' * 40), ('deployed', True)):
            altered = copy.deepcopy(value)
            altered[key] = changed
            with self.assertRaises(RuntimeError):
                s.execution_receipt(s.IO.encoded(altered), self.contract, self.pin)

    def test_06_preload_positive_fixed_sequence_and_no_credential_persistence(self):
        _, path, pin = self.exported()
        parent = self.parent('preload')
        hosts, requests = [], []
        def invoke(run, host, request, archive, sources):
            hosts.append(host)
            requests.append(request)
            self.assertEqual(self.record(parent, 'preload')['nodes'][-1]['phase'], 'pending')
            self.assertEqual(archive.read(), self.f.archive_raw)
            self.assertEqual(set(sources), {'io', 'contract', 'node'})
            self.assertEqual(request['sudo_password'], 'PUBLIC_STDIN_SENTINEL')
            return s.N.reply_for(self.contract, request['envelope'], pin)
        result = s.preload(self.cp, self.pin, path, pin, parent, 'PUBLIC_STDIN_SENTINEL', invoke)
        self.assertEqual(hosts, list(s.C.HOSTS))
        self.assertEqual(result['phase'], 'completed')
        self.assertTrue(all(r == {} for r in requests))
        for file in (parent / ('bortus-compiled-overlay-preload-' + self.contract['source_commit'])).iterdir():
            self.assertNotIn(b'PUBLIC_STDIN_SENTINEL', file.read_bytes())

    def test_07_preload_lost_second_reply_stops_third_and_preserves_first(self):
        _, path, pin = self.exported()
        parent, hosts = self.parent('preload'), []
        def invoke(run, host, request, archive, sources):
            hosts.append(host)
            if len(hosts) == 2:
                raise TimeoutError('PUBLIC_STDIN_SENTINEL')
            return s.N.reply_for(self.contract, request['envelope'], pin)
        with self.assertRaisesRegex(RuntimeError, '^preload_failed$'):
            s.preload(self.cp, self.pin, path, pin, parent, 'PUBLIC_STDIN_SENTINEL', invoke)
        record = self.record(parent, 'preload')
        self.assertEqual(hosts, list(s.C.HOSTS[:2]))
        self.assertEqual([n['phase'] for n in record['nodes']], ['completed', 'uncertain'])
        self.assertEqual(record['phase'], 'uncertain')
        self.assertNotIn('PUBLIC_STDIN_SENTINEL', json.dumps(record))
        with self.assertRaises(FileExistsError):
            s.preload(self.cp, self.pin, path, pin, parent, 'PUBLIC_STDIN_SENTINEL', invoke)

    def test_08_preload_bad_reply_stops_first(self):
        _, path, pin = self.exported()
        for key, value in (('ordinal', True), ('host', s.C.HOSTS[1]), ('import_exit_code', False),
                           ('raw_config_digest', self.contract['manifest_digest']), ('extra', 'bad')):
            parent, calls = self.parent('preload-' + key), []
            def invoke(run, host, request, archive, sources):
                calls.append(host)
                reply = s.N.reply_for(self.contract, request['envelope'], pin)
                reply[key] = value
                return reply
            with self.assertRaises(RuntimeError):
                s.preload(self.cp, self.pin, path, pin, parent, 'PUBLIC', invoke)
            self.assertEqual(calls, [s.C.HOSTS[0]])
            self.assertEqual(self.record(parent, 'preload')['phase'], 'uncertain')

    def test_09_preload_archive_hash_and_receipt_hash_drift_before_transport(self):
        result, path, pin = self.exported()
        invoke = mock.Mock(side_effect=AssertionError('transport forbidden'))
        with self.assertRaises(RuntimeError):
            s.preload(self.cp, self.pin, path, 'b' * 64, self.parent('bad-receipt'), 'PUBLIC', invoke)
        pathlib.Path(result['archive_path']).write_bytes(b'BAD')
        with self.assertRaises(RuntimeError):
            s.preload(self.cp, self.pin, path, pin, self.parent('bad-archive'), 'PUBLIC', invoke)
        invoke.assert_not_called()

    def test_10_node_positive_pending_content_and_redaction(self):
        parent, req = self.parent('node'), self.request()
        reply = self.receive(request=req, parent=parent)
        self.assertEqual(self.calls, ['images-before', 'images-preimport', 'import', 'images-after', 'manifest', 'config'])
        self.assertEqual(reply, s.N.reply_for(self.contract, req['envelope'], 'a' * 64))
        self.assertNotIn('sudo_password', req)
        record = self.record(parent, 'node')
        self.assertEqual(record['phase'], 'completed')
        self.assertNotIn('PUBLIC_STDIN_SENTINEL', json.dumps(record))
        self.assertNotIn('PUBLIC_ENV_SENTINEL', json.dumps(record))

    def test_11_node_protocol_refusal_before_auth(self):
        for key, value in (('format', s.C.FORMAT), ('purpose', 'export'), ('contract_sha256', 'f' * 64),
                           ('contract_raw', '{}'), ('export_execution_sha256', True), ('extra', 'bad')):
            req = self.request()
            req[key] = value
            auth = mock.Mock(side_effect=AssertionError('auth forbidden'))
            with self.assertRaises(RuntimeError):
                self.receive(request=req, parent=self.parent('node-' + key), auth=auth)
            auth.assert_not_called()
            self.assertNotIn('sudo_password', req)

    def test_12_node_host_ordinal_and_scope_refusal_before_auth(self):
        for key, value in (('host', s.C.HOSTS[1]), ('ordinal', True), ('runtime_qualified', True),
                           ('export_record_sha256', 'f' * 64)):
            req = self.request()
            req['envelope'][key] = value
            auth = mock.Mock()
            with self.assertRaises(RuntimeError):
                self.receive(request=req, parent=self.parent('node-' + key), auth=auth)
            auth.assert_not_called()

    def test_13_node_auth_failure_refused_no_commands(self):
        parent = self.parent('node')
        with self.assertRaises(RuntimeError):
            self.receive(parent=parent, auth=lambda _: False)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.record(parent, 'node')['phase'], 'refused')

    def test_14_node_both_tag_spellings_and_preimport_race_refuse(self):
        for index, spelling in enumerate((self.contract['image_tag'], self.contract['canonical_alias'])):
            for when in ('images-before', 'images-preimport'):
                parent = self.parent('node-' + str(index) + '-' + when)
                def invoke(run, stage, argv, **kwargs):
                    if stage == when:
                        return self.f.inventory(ref=spelling)
                    return self.node_invoke(run, stage, argv, **kwargs)
                with self.assertRaises(RuntimeError):
                    self.receive(parent=parent, invoke=invoke)
                self.assertEqual(self.record(parent, 'node')['phase'], 'refused')
                self.assertNotIn('import', self.calls)

    def test_15_node_truncated_extra_and_altered_archive_refuse(self):
        for i, raw in enumerate((self.f.archive_raw[:-1], self.f.archive_raw + b'x', b'BAD')):
            parent = self.parent('node-' + str(i))
            with self.assertRaises(RuntimeError):
                self.receive(parent=parent, data=raw)
            self.assertEqual(self.record(parent, 'node')['phase'], 'refused')
            self.assertNotIn('import', self.calls)

    def test_16_node_import_timeout_uncertain_and_existing_run_not_adopted(self):
        parent, auth = self.parent('node'), mock.Mock(return_value=True)
        def invoke(run, stage, argv, **kwargs):
            if stage == 'import':
                raise TimeoutError('PUBLIC')
            return self.node_invoke(run, stage, argv, **kwargs)
        with self.assertRaises(RuntimeError):
            self.receive(parent=parent, invoke=invoke, auth=auth)
        self.assertEqual(self.record(parent, 'node')['phase'], 'uncertain')
        with self.assertRaises(RuntimeError):
            self.receive(parent=parent, auth=auth)
        self.assertEqual(auth.call_count, 1)

    def test_17_node_manifest_config_inventory_drift_uncertain(self):
        for altered in ('manifest', 'config', 'images-after'):
            parent = self.parent('node-' + altered)
            def invoke(run, stage, argv, **kwargs):
                return b'{}' if stage == altered else self.node_invoke(run, stage, argv, **kwargs)
            with self.assertRaises(RuntimeError):
                self.receive(parent=parent, invoke=invoke)
            self.assertEqual(self.record(parent, 'node')['phase'], 'uncertain')

    def test_18_node_concurrent_archive_write_preimport_refuses(self):
        parent = self.parent('node')
        def invoke(run, stage, argv, **kwargs):
            if stage == 'images-preimport':
                with (run.directory / 'image.tar').open('ab') as out:
                    out.write(b'x')
            return self.node_invoke(run, stage, argv, **kwargs)
        with self.assertRaises(RuntimeError):
            self.receive(parent=parent, invoke=invoke)
        self.assertEqual(self.record(parent, 'node')['phase'], 'refused')
        self.assertNotIn('import', self.calls)

    def test_19_run_nofollow_singlelink_modes_and_parent_refusal(self):
        parent = self.parent('owned')
        run = s.IO.Run(parent, self.contract['source_commit'], 'export')
        try:
            bad = self.root / 'symlink'
            bad.symlink_to(self.cp)
            with self.assertRaises(OSError):
                run.copy(bad, 'bad', 100000)
            hard = self.root / 'hardlink'
            os.link(self.cp, hard)
            with self.assertRaises(RuntimeError):
                run.copy(hard, 'hard', 100000)
            hard.unlink()
            self.cp.chmod(0o666)
            with self.assertRaises(RuntimeError):
                run.copy(self.cp, 'mode', 100000)
            self.cp.chmod(0o600)
            for name in ('../escape', 'a/b', '.', '/absolute'):
                with self.assertRaises(RuntimeError):
                    run.create(name)
        finally:
            run.close()
        writable = self.parent('writable')
        writable.chmod(0o777)
        with self.assertRaises(RuntimeError):
            s.IO.Run(writable, self.contract['source_commit'], 'export')

    def test_20_inputs_replacement_and_record_tampering_detected(self):
        run = s.IO.Run(self.parent('owned'), self.contract['source_commit'], 'export')
        try:
            run.copy(self.cp, 'copy', 100000)
            (run.directory / 'copy').write_bytes(b'changed')
            with self.assertRaises(RuntimeError):
                with run.opened('copy', self.pin):
                    self.fail('changed copy opened')
            (run.directory / 'record.json').write_bytes(b'{}')
            with self.assertRaises(RuntimeError):
                run.save()
        finally:
            run.close()

    def test_21_protected_contract_and_exact_pin_before_dispatch(self):
        for pin in ('f' * 64, True):
            with self.assertRaises(RuntimeError):
                s.contract_input(self.cp, pin)
        link = self.root / 'link'
        link.symlink_to(self.cp)
        with self.assertRaises(OSError):
            s.contract_input(link, self.pin)
        self.cp.chmod(0o666)
        with self.assertRaises(RuntimeError):
            s.contract_input(self.cp, self.pin)

    def test_22_launcher_fixed_host_source_modules_no_credentials_or_legacy(self):
        run = s.IO.Run(self.parent('owned'), self.contract['source_commit'], 'preload')
        try:
            argv = s.launcher(run, s.C.HOSTS[0], self.sources)
            self.assertEqual(argv[:-2], s.SSH)
            self.assertEqual(argv[-2], 'james@192.168.0.4')
            self.assertNotIn('PUBLIC_STDIN_SENTINEL', str(argv))
            self.assertNotIn('StrictHostKeyChecking=no', str(argv))
            code = shlex.split(argv[-1])[2]
            # Load the fixed bundle in memory, replacing only its final entry
            # dispatch. This verifies imports without sudo/SSH/ctr or home writes.
            code = code[:code.rindex('raise SystemExit')]
            namespace = {}
            exec(compile(code, '<public-launcher-control>', 'exec'), namespace)
            self.assertEqual(namespace['node'].IO, namespace['io'])
            self.assertEqual(namespace['node'].CONTRACT, namespace['contract'])
            self.assertEqual(namespace['io'].CONTRACT_PIN,
                'a47ea88d868bc99e0007ca78af7f393a616db4cbbfd03fd59f62c69c4c397ca1')
            with self.assertRaises(RuntimeError):
                s.launcher(run, '192.168.0.7', self.sources)
        finally:
            run.close()

    def test_23_bad_credentials_bound_and_shape(self):
        for password in ('', 'x\ny', 'x\ry', 'x\0y', 'x' * 4097, None):
            with self.assertRaises(RuntimeError):
                s.N.password_ok(password)
        with self.assertRaises(RuntimeError):
            s.IO.decode(b'{"a":1,"a":2}')
        with self.assertRaises(RuntimeError):
            s.IO.decode(b'{"a":NaN}')

    def test_24_durability_failure_before_dispatch_refuses(self):
        parent = self.parent('node')
        real = s.N.IO.Run.save
        def save(run):
            if run.record['phase'] == 'pending':
                raise OSError('PUBLIC fsync failure')
            return real(run)
        with mock.patch.object(s.N.IO.Run, 'save', save):
            with self.assertRaises(RuntimeError):
                self.receive(parent=parent)
        self.assertEqual(self.record(parent, 'node')['phase'], 'refused')
        self.assertNotIn('import', self.calls)

    def test_25_durability_failure_after_import_leaves_uncertain(self):
        parent = self.parent('node')
        real = s.N.IO.Run.save
        def save(run):
            if run.record['phase'] == 'completed':
                raise OSError('PUBLIC fsync failure')
            return real(run)
        with mock.patch.object(s.N.IO.Run, 'save', save):
            with self.assertRaises(RuntimeError):
                self.receive(parent=parent)
        self.assertEqual(self.record(parent, 'node')['phase'], 'uncertain')

    def test_26_child_bounded_output_exit_and_timeout_only_fake_processes(self):
        run = s.IO.Run(self.parent('owned'), self.contract['source_commit'], 'export')
        class Process:
            def __init__(self, data=b'PUBLIC', code=0, timeout=False):
                self.stdout, self.stdin = io.BytesIO(data), io.BytesIO()
                self.code, self.timeout, self.killed, self.running = code, timeout, False, True
            def wait(self, timeout=None):
                if self.timeout:
                    self.timeout = False
                    raise subprocess.TimeoutExpired(['PUBLIC'], timeout)
                self.running = False
                return self.code
            def poll(self):
                return None if self.running else self.code
            def kill(self):
                self.killed = True
                self.code = -9
        try:
            for data, code, timeout, cap in ((b'PUBLIC', 0, False, 20), (b'OVERFLOW', 0, False, 1),
                                           (b'', 2, False, 20), (b'', 0, True, 20)):
                process = Process(data, code, timeout)
                with mock.patch.object(s.IO.subprocess, 'Popen', return_value=process) as popen:
                    if code == 0 and not timeout and cap == 20:
                        self.assertEqual(s.IO.child(run, 'fake', ['PUBLIC'], cap=cap), b'PUBLIC')
                    else:
                        with self.assertRaises((RuntimeError, subprocess.TimeoutExpired)):
                            s.IO.child(run, 'fake', ['PUBLIC'], cap=cap)
                    self.assertEqual(popen.call_args.kwargs['stderr'], subprocess.DEVNULL)
                    self.assertFalse(popen.call_args.kwargs['start_new_session'])
                    if timeout:
                        self.assertTrue(process.killed)
        finally:
            run.close()

    def test_27_legacy_node_refuses_new_protocol_before_authorization(self):
        auth = mock.Mock(side_effect=AssertionError('legacy authorization forbidden'))
        with self.assertRaises(RuntimeError):
            fixture.n.receive(self.request(), io.BytesIO(b''), self.root, authorize=auth)
        auth.assert_not_called()
        # Source-only legacy receipt refusal; no existing legacy control replay.
        run = type('LegacyRun', (), {'record': {'purpose': 'export'}, 'copy_input': mock.Mock(),
            'open_input': lambda *args: io.BytesIO(s.C.encoded(s.C.expected_export_record(self.contract)))})()
        with self.assertRaisesRegex(fixture.s.b.BuildRefused, 'build_receipt'):
            fixture.s.receipt(run, 'PUBLIC', 'a' * 64, self.contract['source_commit'], self.contract['local_image_id'])

    def test_28_transport_credential_only_stdin_and_reply_bound(self):
        req = self.request()
        run = s.IO.Run(self.parent('owned'), self.contract['source_commit'], 'preload')
        try:
            def child(run, stage, argv, **kwargs):
                self.assertNotIn('PUBLIC_STDIN_SENTINEL', str(argv))
                self.assertEqual(s.IO.decode(kwargs['prefix'][:-1]), req)
                self.assertEqual(kwargs['cap'], 65536)
                self.assertEqual(kwargs['timeout'], 1200)
                return b'{"PUBLIC":"reply"}'
            with mock.patch.object(s.IO, 'child', child):
                self.assertEqual(s.transport(run, s.C.HOSTS[0], req, io.BytesIO(b'PUBLIC'), self.sources),
                                 {'PUBLIC': 'reply'})
        finally:
            run.close()

    def test_29_concurrent_source_copy_write_refused(self):
        run = s.IO.Run(self.parent('owned'), self.contract['source_commit'], 'export')
        read = os.read
        changed = []
        def racing(fd, count):
            raw = read(fd, count)
            if not changed:
                changed.append(True)
                with self.cp.open('ab') as out:
                    out.write(b'x')
            return raw
        try:
            with mock.patch.object(os, 'read', racing):
                with self.assertRaises(RuntimeError):
                    run.copy(self.cp, 'copy', 100000)
        finally:
            run.close()

    def test_30_concurrent_import_archive_write_uncertain(self):
        parent = self.parent('node')
        def invoke(run, stage, argv, **kwargs):
            if stage == 'import':
                with (run.directory / 'image.tar').open('ab') as out:
                    out.write(b'x')
            return self.node_invoke(run, stage, argv, **kwargs)
        with self.assertRaises(RuntimeError):
            self.receive(parent=parent, invoke=invoke)
        self.assertEqual(self.record(parent, 'node')['phase'], 'uncertain')

    def test_31_run_directory_replacement_refuses_new_writes(self):
        run = s.IO.Run(self.parent('owned'), self.contract['source_commit'], 'export')
        try:
            run.directory.rename(run.directory.with_name('retained-original'))
            run.directory.mkdir(mode=0o700)
            with self.assertRaises(RuntimeError):
                run.create('forbidden')
            self.assertEqual(list(run.directory.iterdir()), [])
        finally:
            run.close()

    def test_32_export_final_metadata_archive_write_uncertain(self):
        parent = self.parent('export')
        def invoke(run, stage, argv, **kwargs):
            if stage == 'source-after':
                with (run.directory / 'image.tar').open('ab') as out:
                    out.write(b'x')
            return self.export_invoke(run, stage, argv, **kwargs)
        with self.assertRaises(RuntimeError):
            s.export_image(self.cp, self.pin, parent, invoke)
        self.assertEqual(self.record(parent, 'export')['phase'], 'uncertain')

    def test_33_node_final_metadata_archive_write_uncertain(self):
        parent = self.parent('node')
        def invoke(run, stage, argv, **kwargs):
            if stage == 'config':
                with (run.directory / 'image.tar').open('ab') as out:
                    out.write(b'x')
            return self.node_invoke(run, stage, argv, **kwargs)
        with self.assertRaises(RuntimeError):
            self.receive(parent=parent, invoke=invoke)
        self.assertEqual(self.record(parent, 'node')['phase'], 'uncertain')


if __name__ == '__main__':
    unittest.main()
