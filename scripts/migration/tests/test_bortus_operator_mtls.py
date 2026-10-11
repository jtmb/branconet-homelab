"""Disposable local credentials only; no operator config, live API or data reads."""
import base64
import copy
import importlib.util
import os
import pathlib
import ssl
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import yaml
import test_bortus_restore_watch as watch_tests

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('operator_mtls_tests_module', HERE.parent / 'bortus-operator-mtls.py')
module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
watch = watch_tests.module


@unittest.skipUnless(os.name == 'posix' and hasattr(os, 'memfd_create'), 'Actual Linux memfd fixture required')
class OperatorMTLSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        watch_tests.RestoreWatchTests.setUpClass()
        cls.cert = watch_tests.RestoreWatchTests.cert
        cls.key = watch_tests.RestoreWatchTests.key
        cls.encrypted_key = cls.key.with_name('synthetic-encrypted-key.pem')
        subprocess.run(['openssl', 'pkey', '-in', str(cls.key), '-aes-256-cbc',
            '-passout', 'fd:0', '-out', str(cls.encrypted_key)],
            input=os.urandom(24).hex().encode() + b'\n', capture_output=True, check=True, timeout=10)

    @classmethod
    def tearDownClass(cls): watch_tests.RestoreWatchTests.tearDownClass()

    def setUp(self):
        # Avoid writable /tmp ancestry: this is an owned disposable home directory.
        self.folder = tempfile.TemporaryDirectory(prefix='bortus-adapter-fixture-', dir=pathlib.Path.home())
        self.directory = pathlib.Path(self.folder.name)
        self.path = self.directory / 'fixture-kubeconfig.yaml'
        self.fixture = None; self.collector = None; self.journal = None
        encoded = lambda p: base64.b64encode(p.read_bytes()).decode()
        self.config = {'apiVersion': 'v1', 'kind': 'Config',
            'clusters': [{'name': 'approved-cluster', 'cluster': {
                'server': module.APPROVED_ORIGIN, 'certificate-authority-data': encoded(self.cert)}}],
            'contexts': [{'name': 'approved-context', 'context': {'cluster': 'approved-cluster', 'user': 'operator'}}],
            'current-context': 'approved-context',
            'users': [{'name': 'operator', 'user': {'client-certificate-data': encoded(self.cert),
                                                'client-key-data': encoded(self.key)}}]}
        self.save()
        self.adapter = module.OperatorMTLSOptions(str(self.path))

    def tearDown(self):
        if self.collector: self.collector.close()
        if self.journal: self.journal.close()
        if self.fixture: self.fixture.close()
        self.folder.cleanup()
        self.assertFalse(self.directory.exists())

    def save(self, raw=None):
        if raw is None: raw = yaml.safe_dump(self.config).encode()
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'wb') as stream: stream.write(raw)

    def refuse(self):
        before = self.fds()
        with self.assertRaises(module.AdapterRefused) as error: self.adapter()
        self.assertNotIn('PRIVATE', str(error.exception))
        self.assertEqual(before, self.fds())
        return error.exception.code

    def fds(self): return set(os.listdir('/proc/self/fd'))

    def test_fresh_context_memfds_closed_and_only_path_retained(self):
        before = self.fds()
        context, headers = self.adapter()
        other, _ = self.adapter()
        self.assertIsNot(context, other)
        self.assertEqual({}, headers); self.assertEqual(before, self.fds())
        self.assertEqual({'path'}, set(self.adapter.__dict__))
        self.assertTrue(context.check_hostname); self.assertEqual(ssl.CERT_REQUIRED, context.verify_mode)
        self.assertEqual(ssl.TLSVersion.TLSv1_2, context.minimum_version)
        self.assertIsNone(context.keylog_filename)
        self.assertEqual({'fixture-kubeconfig.yaml'}, {p.name for p in self.directory.iterdir()})

    def test_actual_owned_0755_parent_and_mtls_list_watch(self):
        self.directory.chmod(0o755)
        self.fixture = watch_tests.Fixture(self.cert, self.key, require_client=True)
        self.config['clusters'][0]['cluster']['server'] = self.fixture.origin; self.save()
        run_parent = self.directory / 'run-parent'; run_parent.mkdir(mode=0o700)
        self.journal = watch.WatchJournal(run_parent / 'run').open(watch.ownership.seed('123456abcdef', 'a'*64, 'b'*64))
        with mock.patch.object(module, 'APPROVED_ORIGIN', self.fixture.origin):
            self.collector = watch.Collector(self.journal, watch.TLSAPI(self.fixture.origin, self.adapter), watch_tests.source()).start()
        self.assertEqual(2, len(self.fixture.requests))
        self.assertEqual('ready', self.collector.state['phase'])
        self.assertNotIn('PRIVATE KEY', (self.journal.directory / 'watch.json').read_text())

    def test_actual_kubeadm_context_identifier_mtls(self):
        self.config['contexts'][0]['name'] = 'kubernetes-admin@approved-cluster'
        self.config['current-context'] = self.config['contexts'][0]['name']
        self.fixture = watch_tests.Fixture(self.cert, self.key, require_client=True)
        self.config['clusters'][0]['cluster']['server'] = self.fixture.origin
        self.save()
        with mock.patch.object(module, 'APPROVED_ORIGIN', self.fixture.origin):
            api = watch.TLSAPI(self.fixture.origin, self.adapter)
            obj, _ = api.list_page(None, watch.MAX_LIST_BYTES, time.monotonic() + 10)
        self.assertEqual('VolumeList', obj['kind'])
        self.assertEqual(1, len(self.fixture.requests))
        # Context still has to reference the selected named entry exactly.
        self.config['current-context'] = 'other@approved-cluster'
        self.save()
        self.assertEqual('context_shape', self.refuse())

    def test_atomic_rotation_between_calls_is_fresh_and_security_withdrawal_refuses(self):
        self.adapter()
        replacement = self.directory / 'replacement'; self.path.rename(replacement)
        self.config['users'][0]['user'] = {'token': 'PRIVATE_UNSUPPORTED_TOKEN'}; self.save()
        self.assertEqual('user_shape', self.refuse())
        self.assertTrue(replacement.exists())

    def test_mode_0644_refuses(self):
        self.path.chmod(0o644); self.assertEqual('source_file', self.refuse())

    def test_group_and_world_writable_parent_refuse(self):
        for mode in (0o775, 0o757):
            with self.subTest(mode=mode):
                self.directory.chmod(mode); self.assertEqual('source_parent', self.refuse())
        self.directory.chmod(0o700)

    def test_symlink_source_refuses(self):
        target = self.directory / 'original'; self.path.rename(target); self.path.symlink_to(target)
        self.refuse(); self.assertTrue(self.path.is_symlink())

    def test_symlink_parent_refuses(self):
        target = self.directory / 'protected'; target.mkdir(mode=0o700)
        moved = target / self.path.name; self.path.rename(moved)
        link = self.directory / 'link'; link.symlink_to(target, target_is_directory=True)
        self.adapter = module.OperatorMTLSOptions(str(link / moved.name)); self.refuse()

    def test_fifo_nonblocking_refuses(self):
        self.path.unlink(); os.mkfifo(self.path, 0o600); self.assertEqual('source_file', self.refuse())

    def test_hardlink_source_refuses(self):
        os.link(self.path, self.directory / 'alias'); self.assertEqual('source_file', self.refuse())

    def test_oversize_file_refuses_before_read(self):
        self.save(b'x' * (module.MAX_CONFIG_BYTES + 1))
        with mock.patch.object(module.os, 'read') as read:
            self.assertEqual('source_file', self.refuse()); read.assert_not_called()

    def test_midread_atomic_replacement_refuses(self):
        original = os.read; replaced = False
        def change(fd, count):
            nonlocal replaced
            result = original(fd, count)
            if not replaced:
                replaced = True; self.path.rename(self.directory / 'previous'); self.save()
            return result
        with mock.patch.object(module.os, 'read', side_effect=change):
            self.assertEqual('source_changed', self.refuse())

    def test_midread_same_inode_write_refuses(self):
        original = os.read; changed = False
        def change(fd, count):
            nonlocal changed
            result = original(fd, count)
            if not changed:
                changed = True
                with self.path.open('ab') as stream: stream.write(b'\n')
            return result
        with mock.patch.object(module.os, 'read', side_effect=change):
            self.assertEqual('source_changed', self.refuse())

    def test_unsupported_auth_paths_exec_plugins_tokens_proxy_insecure(self):
        original = copy.deepcopy(self.config)
        for where, field, value in [('user', 'exec', {'command': 'PRIVATE'}), ('user', 'token', 'PRIVATE'),
                ('user', 'auth-provider', {}), ('user', 'client-key', '/PRIVATE'),
                ('user', 'client-certificate', '/PRIVATE'), ('cluster', 'certificate-authority', '/PRIVATE'),
                ('cluster', 'proxy-url', 'http://PRIVATE'), ('cluster', 'insecure-skip-tls-verify', True),
                ('cluster', 'tls-server-name', 'PRIVATE')]:
            with self.subTest(field=field):
                self.config = copy.deepcopy(original)
                self.config['users' if where == 'user' else 'clusters'][0][where][field] = value
                self.save(); self.refuse()

    def test_origin_context_names_and_unknown_top_fields_refuse(self):
        original = copy.deepcopy(self.config)
        variants = [lambda c: c['clusters'][0]['cluster'].update(server='https://unapproved.example:6443'),
            lambda c: c.update(preferences={}), lambda c: c.update({'current-context': 'missing'}),
            lambda c: c['contexts'][0]['context'].update(namespace='bortus'),
            lambda c: c['contexts'][0]['context'].update(user='missing'),
            lambda c: c['users'].append(copy.deepcopy(c['users'][0]))]
        for change in variants:
            self.config = copy.deepcopy(original); change(self.config); self.save(); self.refuse()

    def test_duplicate_yaml_keys_and_aliases_anchors_tags_multidocument_refuse(self):
        for raw in [b'apiVersion: v1\napiVersion: PRIVATE\n', b'a: &ref PRIVATE\nb: *ref\n',
                    b'a: &ref PRIVATE\n', b'a: !!str PRIVATE\n', b'a: 1\n---\nb: 2\n', b'\xff', b'{']:
            with self.subTest(case=len(raw)):
                self.save(raw); self.refuse()

    def test_yaml_depth_and_event_bounds(self):
        self.save(('a: ' + '[' * 13 + '0' + ']' * 13).encode()); self.assertEqual('yaml_bound', self.refuse())
        self.save(b'a: [1, 2, 3]\n')
        with mock.patch.object(module, 'MAX_YAML_EVENTS', 4): self.assertEqual('yaml_bound', self.refuse())

    def test_bad_base64_encrypted_key_and_bad_certificates_refuse(self):
        original = copy.deepcopy(self.config)
        for value in ['PRIVATE_NOT_BASE64', base64.b64encode(b'PRIVATE').decode(),
                      base64.b64encode(b'-----BEGIN ENCRYPTED PRIVATE KEY-----\nAAAA\n-----END ENCRYPTED PRIVATE KEY-----').decode()]:
            self.config = copy.deepcopy(original)
            self.config['users'][0]['user']['client-key-data'] = value; self.save(); self.refuse()
        self.config = original
        self.config['clusters'][0]['cluster']['certificate-authority-data'] = base64.b64encode(
            b'-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----').decode()
        self.save(); self.assertEqual('tls_material', self.refuse())

    def test_decoded_key_bound(self):
        self.config['users'][0]['user']['client-key-data'] = base64.b64encode(b'x' * (module.MAX_PEM_BYTES + 1)).decode()
        self.save(); self.assertEqual('pem_bound', self.refuse())

    def test_memfd_fault_closes_prior_owned_descriptor(self):
        original = os.memfd_create; calls = 0
        def failure(*args):
            nonlocal calls
            calls += 1
            if calls == 2: raise OSError('PRIVATE_MEMFD_FAULT')
            return original(*args)
        with mock.patch.object(module.os, 'memfd_create', side_effect=failure):
            self.assertEqual('tls_material', self.refuse())

    def test_memfd_write_and_seal_fault_close_descriptor(self):
        for target in ('write',):
            with mock.patch.object(module.os, target, side_effect=OSError('PRIVATE_MEMFD_WRITE')):
                self.assertEqual('tls_material', self.refuse())
        with mock.patch.object(module.fcntl, 'fcntl', side_effect=OSError('PRIVATE_MEMFD_SEAL')):
            self.assertEqual('tls_material', self.refuse())

    def test_wrong_client_key_tls_error_is_fixed_and_descriptors_closed(self):
        # Valid PEM envelope but invalid key DER exercises load_cert_chain cleanup.
        self.config['users'][0]['user']['client-key-data'] = base64.b64encode(
            b'-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n').decode()
        self.save(); self.assertEqual('tls_material', self.refuse())

    def test_encrypted_password_callback_is_noninteractive_fixed_failure(self):
        with self.assertRaises(module.AdapterRefused) as error: module.no_password()
        self.assertEqual('key_encrypted', error.exception.code)

    def test_memfd_is_cloexec_0600_and_sealed(self):
        fd = module.memory_file(b'public synthetic bytes')
        try:
            self.assertFalse(os.get_inheritable(fd)); self.assertEqual(0o600, os.fstat(fd).st_mode & 0o777)
            with self.assertRaises(OSError): os.write(fd, b'change')
            with self.assertRaises(OSError): os.ftruncate(fd, 0)
        finally: os.close(fd)

    def test_actual_encrypted_fixture_key_refuses_before_memfd_or_prompt(self):
        self.config['users'][0]['user']['client-key-data'] = base64.b64encode(self.encrypted_key.read_bytes()).decode()
        self.save()
        with mock.patch.object(module, 'memory_file') as memory:
            self.assertEqual('key_format', self.refuse()); memory.assert_not_called()

    def test_environment_keylog_request_is_ignored(self):
        keylog = self.directory / 'must-not-exist'
        with mock.patch.dict(os.environ, {'SSLKEYLOGFILE': str(keylog)}):
            context, _ = self.adapter()
        self.assertIsNone(context.keylog_filename); self.assertFalse(keylog.exists())

    def test_midread_parent_replacement_refuses_pinned_chain(self):
        parent = self.directory / 'source-parent'; parent.mkdir(mode=0o755)
        self.path.rename(parent / self.path.name); self.path = parent / self.path.name
        self.adapter = module.OperatorMTLSOptions(str(self.path))
        original = os.read; changed = False
        def change(fd, count):
            nonlocal changed
            result = original(fd, count)
            if not changed:
                changed = True
                parent.rename(self.directory / 'prior-parent'); parent.mkdir(mode=0o755); self.save()
            return result
        with mock.patch.object(module.os, 'read', side_effect=change):
            self.assertEqual('source_changed', self.refuse())

    def test_foreign_file_uid_refuses_before_read(self):
        original = os.fstat
        def foreign(fd):
            info = original(fd)
            import stat
            if stat.S_ISREG(info.st_mode):
                from types import SimpleNamespace
                return SimpleNamespace(st_mode=info.st_mode, st_uid=info.st_uid + 10000)
            return info
        with mock.patch.object(module.os, 'fstat', side_effect=foreign), mock.patch.object(module.os, 'read') as read:
            self.assertEqual('source_file', self.refuse()); read.assert_not_called()

    def test_actual_hostname_failure_closes_tls_without_http_dispatch(self):
        self.fixture = watch_tests.Fixture(self.cert, self.key, require_client=True)
        origin = 'https://127.0.0.1:' + str(self.fixture.server.server_port)
        self.config['clusters'][0]['cluster']['server'] = origin; self.save()
        with mock.patch.object(module, 'APPROVED_ORIGIN', origin):
            transport = watch.TLSAPI(origin, self.adapter)
            with self.assertRaises(watch.WatchRefused): transport.list_page(None, 65536, time.monotonic() + 5)
        self.assertEqual([], self.fixture.requests)

    def test_public_failure_drops_underlying_parser_context_and_tls_material_locals(self):
        self.save(b'client-key-data: [PRIVATE_SYNTHETIC_VALUE\n')
        with self.assertRaises(module.AdapterRefused) as error: self.adapter()
        self.assertIsNone(error.exception.__context__)
        self.config['users'][0]['user']['client-key-data'] = base64.b64encode(
            b'-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n').decode()
        self.save()
        try:
            self.adapter()
        except module.AdapterRefused as error:
            self.assertIsNone(error.__context__)
            tb = error.__traceback__
            while tb:
                if tb.tb_frame.f_code.co_name == '__call__':
                    for key in ('ca', 'certificate', 'key', 'raw', 'context'):
                        self.assertIsNone(tb.tb_frame.f_locals.get(key))
                tb = tb.tb_next
        else: self.fail('Invalid fixture key was accepted')

    def test_close_fault_refuses_and_still_closes_all_other_owned_fds(self):
        original = os.close; faulted = False
        def close(fd):
            nonlocal faulted
            original(fd)
            if not faulted:
                faulted = True
                raise OSError('PRIVATE_SYNTHETIC_CLOSE_FAULT')
        with mock.patch.object(module.os, 'close', side_effect=close):
            self.assertEqual('descriptor_cleanup', self.refuse())


if __name__ == '__main__': unittest.main()
