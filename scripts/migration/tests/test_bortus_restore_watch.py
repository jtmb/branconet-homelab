"""Owned local HTTPS and POSIX faults only; no production/API/container/data calls."""
import copy
import http.server
import importlib.util
import json
import os
import pathlib
import queue
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('restore_watch_tests_module', HERE.parent / 'bortus-restore-watch.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
UID = lambda n: '00000000-0000-0000-0000-' + str(n).zfill(12)
NAME = 'bortus-restore-123456abcdef'


def volume(rv='opaque-1', flags=(True, True), uid=None, name='fresh-volume'):
    status = {'conditions': [{'type': 'Ready', 'status': 'True',
                             'message': 'PRIVATE_SYNTHETIC_CONDITION_VALUE'}]}
    if flags is not None:
        status.update(restoreInitiated=flags[0], restoreRequired=flags[1])
    return {'apiVersion': module.completion.API_VERSION, 'kind': 'Volume',
        'metadata': {'name': name, 'namespace': 'longhorn-system', 'uid': uid or UID(5),
                     'resourceVersion': rv},
        'spec': {'fromBackup': 'cifs://192.168.0.8/container_backups/k8s-migration-20261009/longhorn?backup=backup-fixture&volume=original-volume',
                 'encrypted': True, 'numberOfReplicas': 2, 'size': '1073741824', 'dataEngine': 'v1', 'standby': False},
        'status': status}


def source():
    return module.Source(volume()['spec']['fromBackup'],
        module.completion.BackupIdentity('backup-fixture', 'longhorn-system', UID(1), 'backup-rv'),
        UID(2), 'original-volume', UID(3), UID(4))


def page(items=None, rv='opaque-list', continuation=''):
    return {'apiVersion': module.completion.API_VERSION, 'kind': 'VolumeList',
            'metadata': {'resourceVersion': rv, 'continue': continuation}, 'items': items or []}


class Fixture:
    def __init__(self, cert, key, pages=None, watch_status=200, require_client=False):
        self.pages = list(pages or [page()])
        self.watch_status = watch_status
        self.frames = queue.Queue()
        self.closed = threading.Event()
        self.stop = threading.Event()
        self.requests = []
        self.auth_is_fresh = []
        self.unexpected_errors = 0
        fixture = self
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *_): pass
            def handle(self):
                try: super().handle()
                except (ConnectionResetError, BrokenPipeError, ssl.SSLError):
                    pass  # Expected owned cancellation; no peer address or traceback logging.
            def do_GET(self):
                parts = urlsplit(self.path); query = parse_qs(parts.query)
                fixture.requests.append((parts.path, query))
                fixture.auth_is_fresh.append(self.headers.get('Authorization') ==
                    'Bearer PUBLIC_ROTATION_' + str(len(fixture.requests)))
                if query.get('watch') != ['true']:
                    body = fixture.pages.pop(0)
                    body = body if type(body) is bytes else json.dumps(body).encode()
                    self.send_response(200); self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body))); self.end_headers()
                    self.wfile.write(body); return
                self.send_response(fixture.watch_status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Transfer-Encoding', 'chunked'); self.end_headers()
                if fixture.watch_status != 200:
                    self.wfile.write(b'0\r\n\r\n'); return
                try:
                    while not fixture.stop.is_set():
                        try: raw = fixture.frames.get(timeout=.02)
                        except queue.Empty: continue
                        if raw is None:
                            self.wfile.write(b'0\r\n\r\n'); return
                        self.wfile.write(format(len(raw), 'x').encode() + b'\r\n' + raw + b'\r\n')
                        self.wfile.flush()
                except (OSError, ssl.SSLError):
                    pass
                finally:
                    fixture.closed.set()
        class Server(http.server.ThreadingHTTPServer):
            def handle_error(self, *_):
                fixture.unexpected_errors += 1  # Fixed scalar; unexpected errors still fail teardown.
        self.server = Server(('127.0.0.1', 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.load_cert_chain(cert, key)
        if require_client:
            context.load_verify_locations(cafile=str(cert)); context.verify_mode = ssl.CERT_REQUIRED
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01})
        self.thread.start()

    @property
    def origin(self): return 'https://localhost:' + str(self.server.server_port)

    def send(self, obj=None, kind='MODIFIED', raw=None):
        self.frames.put(raw if raw is not None else json.dumps({'type': kind, 'object': obj}).encode() + b'\n')

    def close(self):
        self.stop.set(); self.server.shutdown(); self.server.server_close(); self.thread.join(2)
        if self.requests and any(q.get('watch') == ['true'] for _, q in self.requests):
            if self.watch_status == 200: assert self.closed.wait(2)
        assert not self.thread.is_alive()
        assert self.unexpected_errors == 0


@unittest.skipUnless(os.name == 'posix', 'Actual owned POSIX directory/HTTPS fixture required')
class RestoreWatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.certificates = tempfile.TemporaryDirectory(prefix='bortus-watch-public-fixture-')
        folder = pathlib.Path(cls.certificates.name)
        cls.cert, cls.key = folder / 'certificate.pem', folder / 'synthetic-key.pem'
        before = os.umask(0o077)
        try:
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost',
                '-keyout', str(cls.key), '-out', str(cls.cert)], check=True, capture_output=True, timeout=10)
        finally:
            os.umask(before)

    @classmethod
    def tearDownClass(cls): cls.certificates.cleanup()

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='bortus-watch-owned-fixture-')
        self.journal = module.WatchJournal(pathlib.Path(self.folder.name) / 'run').open(
            module.ownership.seed('123456abcdef', 'a' * 64, 'b' * 64))
        self.fixture = None; self.collector = None; self.option_calls = 0

    def tearDown(self):
        if self.collector: self.collector.close()
        if self.fixture: self.fixture.close()
        self.journal.close(); self.folder.cleanup()

    def options(self):
        self.option_calls += 1
        context = ssl.create_default_context(cafile=str(self.cert))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return context, {'Authorization': 'Bearer PUBLIC_FIXTURE_ONLY'}

    def create(self, pages=None, watch_status=200, options=None, origin=None):
        self.fixture = Fixture(self.cert, self.key, pages, watch_status)
        transport = module.TLSAPI(origin or self.fixture.origin, options or self.options)
        self.collector = module.Collector(self.journal, transport, source())
        return self.collector

    def wait(self, predicate):
        end = time.monotonic() + 2
        while not predicate():
            if time.monotonic() > end: self.fail('Owned fixture observation timeout')
            time.sleep(.005)

    def mutation(self, kind, uid):
        return lambda _: {'kind': kind, 'metadata': {'name': NAME, 'namespace':
            None if kind == 'StorageClass' else 'bortus', 'uid': uid, 'resourceVersion': 'created-rv',
            'labels': {'bortus-restore': '123456abcdef'}}}

    def claim(self):
        self.collector.perform_create('storageclass_create', self.mutation('StorageClass', UID(8)), lambda _: None)
        self.collector.perform_create('claim_create', self.mutation('PersistentVolumeClaim', UID(6)), lambda _: None)
        claim = self.mutation('PersistentVolumeClaim', UID(6))(None)
        claim['metadata']['resourceVersion'] = 'new-bound-rv'
        claim.update(spec={'storageClassName': NAME, 'volumeName': 'fresh-pv'}, status={'phase': 'Bound'})
        pv = {'metadata': {'name': 'fresh-pv', 'uid': UID(7), 'resourceVersion': 'pv-rv'}, 'spec': {
            'persistentVolumeReclaimPolicy': 'Retain', 'claimRef': {'name': NAME, 'namespace': 'bortus', 'uid': UID(6)},
            'csi': {'driver': 'driver.longhorn.io', 'volumeHandle': 'fresh-volume'}}}
        return claim, pv

    def test_actual_tls_ready_fsynced_before_mutation_and_early_transition_binds(self):
        c = self.create().start()
        proof = c.prerequisite()
        self.assertIsInstance(proof, module.Prerequisite)
        self.assertFalse(proof.data_acceptance)
        def mutate(intent):
            disk = json.loads((self.journal.directory / 'watch.json').read_text())
            self.assertEqual('ready', disk['phase'])
            pending = json.loads((self.journal.directory / 'journal.json').read_text())
            self.assertEqual('pending', pending['operations']['storageclass_create']['state'])
            self.fixture.send(volume('z-rv'))
            self.wait(lambda: c.state['sequence'] >= 1)
            return self.mutation('StorageClass', UID(8))(intent)
        # This confirms draining during a delayed API callback, without a lock across I/O.
        c.perform_create('storageclass_create', mutate, lambda _: None)
        c.perform_create('claim_create', self.mutation('PersistentVolumeClaim', UID(6)), lambda _: None)
        claim = self.mutation('PersistentVolumeClaim', UID(6))(None)
        claim['metadata']['resourceVersion'] = 'bound-rv'
        claim.update(spec={'storageClassName': NAME, 'volumeName': 'fresh-pv'}, status={'phase': 'Bound'})
        pv = {'metadata': {'name': 'fresh-pv', 'uid': UID(7), 'resourceVersion': 'pv-rv'}, 'spec': {
            'persistentVolumeReclaimPolicy': 'Retain', 'claimRef': {'name': NAME, 'namespace': 'bortus', 'uid': UID(6)},
            'csi': {'driver': 'driver.longhorn.io', 'volumeHandle': 'fresh-volume'}}}
        self.fixture.send(volume('a-rv', (True, False))); self.wait(lambda: c.state['sequence'] >= 2)
        c.bind_target(claim, pv, volume('a-rv', (True, False)))
        result = c.seal(volume('a-rv', (True, False)))
        self.assertTrue(result.metadata_transition_eligible); self.assertFalse(result.data_acceptance)
        self.assertEqual(('z-rv', 'a-rv'), (result.initialized_resource_version, result.completed_resource_version))
        raw = (self.journal.directory / 'watch.json').read_text()
        self.assertNotIn('PRIVATE_SYNTHETIC', raw); self.assertNotIn('Bearer', raw)
        self.assertNotIn('cifs://', raw); self.assertNotIn('192.168.0.8', raw)
        self.assertEqual(2, self.option_calls)
        self.assertEqual(['opaque-list'], self.fixture.requests[-1][1]['resourceVersion'])

    def test_complete_paginated_list_uses_collection_not_item_rv(self):
        initial = volume('item-only', uid=UID(20), name='already-present')
        c = self.create([page([initial], continuation='opaque-token'), page()]).start()
        self.assertEqual('opaque-list', c.state['collection_rv'])
        self.assertEqual(['opaque-token'], self.fixture.requests[1][1]['continue'])
        self.assertEqual(3, self.option_calls)

    def test_initial_volume_cannot_be_adopted_as_new(self):
        c = self.create([page([volume()])]).start(); claim, pv = self.claim()
        self.fixture.send(volume()); self.wait(lambda: c.state['sequence'] == 1)
        with self.assertRaises(module.WatchRefused): c.bind_target(claim, pv, volume())

    def test_unready_boolean_or_reopened_sidecar_cannot_authorize(self):
        c = self.create()
        with self.assertRaises(module.WatchRefused): c.before_create('storageclass_create')
        with self.assertRaises(module.WatchRefused): module.Collector(self.journal, c.transport, source())
        self.assertEqual({}, self.journal.record['operations'])

    def test_invalid_tls_and_wrong_hostname_never_authorize(self):
        def insecure():
            return ssl._create_unverified_context(), {}
        with self.assertRaises(module.WatchRefused): self.create(options=insecure).start()
        self.assertEqual({}, self.journal.record['operations'])

    def test_wrong_hostname_verification_is_real(self):
        self.fixture = Fixture(self.cert, self.key)
        self.collector = module.Collector(self.journal, module.TLSAPI(
            'https://127.0.0.1:' + str(self.fixture.server.server_port), self.options), source())
        with self.assertRaises(module.WatchRefused): self.collector.start()

    def test_http410_is_sticky_and_has_no_relist(self):
        c = self.create(watch_status=410)
        with self.assertRaises(module.WatchRefused): c.start()
        self.assertEqual('history_gap', c.state['failure']); self.assertEqual(2, len(self.fixture.requests))

    def test_watch_error_eof_and_malformed_frames_refuse(self):
        c = self.create().start(); self.fixture.send({'message': 'PRIVATE_API_ERROR'}, 'ERROR')
        self.wait(lambda: c.state['failure'] is not None)
        self.assertEqual('watch_error', c.state['failure'])
        with self.assertRaises(module.WatchRefused): c.before_create('storageclass_create')
        self.assertNotIn('PRIVATE_API_ERROR', (self.journal.directory / 'watch.json').read_text())

    def test_eof_is_not_success(self):
        c = self.create().start(); self.fixture.frames.put(None)
        self.wait(lambda: c.state['failure'] is not None); self.assertEqual('watch_eof', c.state['failure'])

    def test_duplicate_json_key_frame_is_rejected_before_projection(self):
        c = self.create().start()
        self.fixture.send(raw=b'{"type":"BOOKMARK","type":"MODIFIED","object":{}}\n')
        self.wait(lambda: c.state['failure'] is not None)
        self.assertEqual('json_duplicate', c.state['failure'])

    def test_bookmark_is_not_initialization_or_completion(self):
        c = self.create().start(); claim, pv = self.claim()
        self.fixture.send({'apiVersion': module.completion.API_VERSION, 'kind': 'Volume',
                           'metadata': {'resourceVersion': 'bookmark-rv'}}, 'BOOKMARK')
        self.wait(lambda: c.state['sequence'] == 1)
        self.assertEqual([], c.state['observations'])
        with self.assertRaises(module.WatchRefused): c.bind_target(claim, pv, volume())

    def test_alias_uid_or_source_drift_before_binding_refuses(self):
        c = self.create().start(); claim, pv = self.claim()
        first = volume(); first['spec']['fromBackup'] = 'PRIVATE_UNAPPROVED_SOURCE'
        self.fixture.send(first); self.wait(lambda: c.state['sequence'] == 1)
        with self.assertRaises(module.WatchRefused): c.bind_target(claim, pv, volume())
        self.assertNotIn('PRIVATE_UNAPPROVED_SOURCE', (self.journal.directory / 'watch.json').read_text())

    def test_confirmed_pvc_uid_chain_required(self):
        c = self.create().start(); claim, pv = self.claim()
        self.fixture.send(volume()); self.wait(lambda: c.state['sequence'] == 1)
        claim['metadata']['uid'] = UID(99)
        with self.assertRaises(module.WatchRefused): c.bind_target(claim, pv, volume())

    def test_lost_create_reply_is_not_adopted_or_replayed(self):
        c = self.create().start()
        def lost(_): raise RuntimeError('PRIVATE_LOST_REPLY')
        with self.assertRaises(RuntimeError): c.perform_create('storageclass_create', lost, lambda _: None)
        self.assertEqual('uncertain', self.journal.record['operations']['storageclass_create']['state'])
        callback = mock.Mock()
        with self.assertRaises(module.WatchRefused): c.perform_create('storageclass_create', callback, lambda _: None)
        callback.assert_not_called()
        self.assertNotIn('PRIVATE_LOST_REPLY', (self.journal.directory / 'watch.json').read_text())

    def test_ready_fsync_failure_prevents_mutation(self):
        c = self.create()
        with mock.patch.object(module.os, 'fsync', side_effect=OSError('PRIVATE_FSYNC')):
            with self.assertRaises(module.WatchRefused): c.start()
        self.assertEqual({}, self.journal.record['operations'])

    def test_event_fsync_failure_is_sticky(self):
        c = self.create().start()
        with mock.patch.object(module.os, 'fsync', side_effect=OSError('PRIVATE_FSYNC')):
            self.fixture.send(volume()); self.wait(lambda: c.state['failure'] is not None)
        callback = mock.Mock()
        with self.assertRaises(module.WatchRefused): c.perform_create('storageclass_create', callback, lambda _: None)
        callback.assert_not_called()

    def test_replaced_sidecar_refuses_and_preserves_foreign_bytes(self):
        c = self.create().start(); path = self.journal.directory / 'watch.json'
        path.rename(self.journal.directory / 'old-watch.json'); path.write_text('foreign', encoding='utf-8'); path.chmod(0o600)
        with self.assertRaises(module.WatchRefused): c.before_create('storageclass_create')
        self.assertEqual('foreign', path.read_text())

    def test_caller_private_field_cannot_enter_closed_schema(self):
        c = self.create().start(); c.state['private_unrecognized'] = 'PRIVATE_VALUE'
        with self.assertRaises(module.WatchRefused): c.before_create('storageclass_create')
        self.assertNotIn('PRIVATE_VALUE', (self.journal.directory / 'watch.json').read_text())

    def test_bound_regression_deletion_and_current_get_rv_fail(self):
        c = self.create().start(); claim, pv = self.claim()
        self.fixture.send(volume()); self.wait(lambda: c.state['sequence'] == 1)
        c.bind_target(claim, pv, volume())
        self.fixture.send(volume('finish-rv', (True, False))); self.wait(lambda: c.state['sequence'] == 2)
        with self.assertRaises(module.WatchRefused): c.seal(volume('unobserved-get-rv', (True, False)))

    def test_target_regression_after_completed_observation_is_sticky(self):
        c = self.create().start(); claim, pv = self.claim()
        self.fixture.send(volume()); self.wait(lambda: c.state['sequence'] == 1)
        c.bind_target(claim, pv, volume())
        self.fixture.send(volume('finish-rv', (True, False))); self.wait(lambda: c.state['sequence'] == 2)
        c.seal(volume('finish-rv', (True, False)))
        self.fixture.send(volume('regressed-rv', (True, True)))
        self.wait(lambda: c.state['failure'] is not None)
        self.assertFalse(c.state['metadata_eligible'])

    def test_cancel_closes_reader_and_preserves_unrelated_server(self):
        c = self.create().start(); c.close()
        self.assertFalse(c.thread.is_alive())
        with self.assertRaises(module.WatchRefused): c.before_create('storageclass_create')
        self.assertTrue(self.fixture.thread.is_alive())

    def test_list_continuation_rv_drift_refuses_no_watch(self):
        c = self.create([page(continuation='token'), page(rv='different-rv')])
        with self.assertRaises(module.WatchRefused): c.start()
        self.assertEqual('list_rv', c.state['failure'])
        self.assertFalse(any(q.get('watch') == ['true'] for _, q in self.fixture.requests))

    def test_fresh_options_security_withdrawal_refuses_watch(self):
        def changing():
            context, headers = self.options()
            if self.option_calls == 2:
                context.check_hostname = False
            return context, headers
        c = self.create(options=changing)
        with self.assertRaises(module.WatchRefused): c.start()
        self.assertEqual(2, self.option_calls)
        self.assertEqual(1, len(self.fixture.requests))

    def test_actual_mutual_tls_context_per_connection(self):
        self.fixture = Fixture(self.cert, self.key, require_client=True)
        def mutual():
            context, headers = self.options(); context.load_cert_chain(self.cert, self.key)
            return context, headers
        self.collector = module.Collector(self.journal, module.TLSAPI(self.fixture.origin, mutual), source())
        self.collector.start()
        self.assertEqual(2, self.option_calls)

    def test_missing_mutual_tls_client_certificate_refuses(self):
        self.fixture = Fixture(self.cert, self.key, require_client=True)
        self.collector = module.Collector(self.journal, module.TLSAPI(self.fixture.origin, self.options), source())
        with self.assertRaises(module.WatchRefused): self.collector.start()

    def test_target_deletion_is_sticky(self):
        c = self.create().start(); claim, pv = self.claim()
        self.fixture.send(volume()); self.wait(lambda: c.state['sequence'] == 1)
        c.bind_target(claim, pv, volume())
        self.fixture.send(volume('deleted-rv'), 'DELETED')
        self.wait(lambda: c.state['failure'] is not None)
        self.assertEqual('target_drift', c.state['failure'])

    def test_frame_byte_overflow_charges_prefix_without_projection(self):
        c = self.create().start()
        self.fixture.send(raw=b'x' * (module.MAX_FRAME_BYTES + 1))
        self.wait(lambda: c.state['failure'] is not None)
        self.assertEqual('watch_byte_bound', c.state['failure'])
        self.assertEqual(module.MAX_FRAME_BYTES + 1, c.state['watch_bytes'])
        self.assertEqual([], c.state['observations'])

    def test_invalid_utf8_is_refused_without_private_error(self):
        c = self.create().start(); self.fixture.send(raw=b'{"type":"\xff"}\n')
        self.wait(lambda: c.state['failure'] is not None)
        self.assertEqual('json_shape', c.state['failure'])

    def test_bounded_json_depth_handles_quoted_escapes(self):
        expected = {'a': '[\\"{'}
        self.assertEqual(expected, module.decode(json.dumps(expected).encode()))
        with self.assertRaises(module.WatchRefused):
            module.decode(b'{"a":' + b'[' * 33 + b'0' + b']' * 33 + b'}')

    def test_list_item_and_page_bounds_are_mandatory(self):
        initial = [volume(uid=UID(100 + n), name='old-' + str(n)) for n in range(3)]
        c = self.create([page(initial)])
        with mock.patch.object(module, 'MAX_LIST_ITEMS', 2):
            with self.assertRaises(module.WatchRefused): c.start()
        self.assertEqual('list_item_bound', c.state['failure'])

    def test_list_byte_bound_refuses_no_watch(self):
        c = self.create([b'x' * 65])
        with mock.patch.object(module, 'MAX_LIST_BYTES', 64):
            with self.assertRaises(module.WatchRefused): c.start()
        self.assertEqual('list_byte_bound', c.state['failure'])
        self.assertEqual(65, c.state['list_bytes'])
        self.assertEqual([], c.state['baseline'])
        self.assertFalse(any(q.get('watch') == ['true'] for _, q in self.fixture.requests))

    def test_list_page_bound_and_repeated_continuation_refuse(self):
        c = self.create([page(continuation='first'), page(continuation='second')])
        with mock.patch.object(module, 'MAX_LIST_PAGES', 2):
            with self.assertRaises(module.WatchRefused): c.start()
        self.assertEqual('list_page_bound', c.state['failure'])

    def test_frame_count_bound_refuses_even_bookmarks(self):
        c = self.create().start()
        with mock.patch.object(module, 'MAX_WATCH_FRAMES', 1):
            for rv in ('bookmark-a', 'bookmark-b'):
                self.fixture.send({'apiVersion': module.completion.API_VERSION, 'kind': 'Volume',
                                   'metadata': {'resourceVersion': rv}}, 'BOOKMARK')
            self.wait(lambda: c.state['failure'] is not None)
        self.assertEqual('watch_frame_bound', c.state['failure'])

    def test_expired_deadline_cannot_dispatch(self):
        c = self.create().start(); c.deadline = time.monotonic() - 1
        callback = mock.Mock()
        with self.assertRaises(module.WatchRefused): c.perform_create('storageclass_create', callback, lambda _: None)
        callback.assert_not_called()

    def test_ready_directory_flush_failure_refuses_before_any_create(self):
        c = self.create(); original = os.fsync
        def fsync(fd):
            import stat
            if stat.S_ISDIR(os.fstat(fd).st_mode): raise OSError('PUBLIC_DIRECTORY_FAULT')
            return original(fd)
        with mock.patch.object(module.os, 'fsync', side_effect=fsync):
            with self.assertRaises(module.WatchRefused): c.start()
        self.assertEqual({}, self.journal.record['operations'])

    def test_rotating_authorization_is_fresh_per_connection_not_persisted(self):
        def rotating():
            context, _ = self.options()
            return context, {'Authorization': 'Bearer PUBLIC_ROTATION_' + str(self.option_calls)}
        c = self.create(options=rotating).start()
        self.assertEqual([True, True], self.fixture.auth_is_fresh)
        self.assertNotIn('PUBLIC_ROTATION', (self.journal.directory / 'watch.json').read_text())

    def test_total_watch_byte_bound_charges_frame_without_projection(self):
        c = self.create().start()
        raw = json.dumps({'type': 'MODIFIED', 'object': volume()}).encode() + b'\n'
        with mock.patch.object(module, 'MAX_WATCH_BYTES', len(raw) - 1):
            self.fixture.send(raw=raw); self.wait(lambda: c.state['failure'] is not None)
        self.assertEqual('watch_byte_bound', c.state['failure'])
        self.assertEqual(len(raw), c.state['watch_bytes'])
        self.assertEqual([], c.state['observations'])

    def test_target_event_bound_is_sticky(self):
        c = self.create().start(); claim, pv = self.claim()
        self.fixture.send(volume()); self.wait(lambda: c.state['sequence'] == 1)
        c.bind_target(claim, pv, volume())
        with mock.patch.object(module.completion, 'MAX_EVENTS', 2):
            self.fixture.send(volume('second')); self.wait(lambda: c.state['sequence'] == 2)
            self.fixture.send(volume('third')); self.wait(lambda: c.state['failure'] is not None)
        self.assertEqual('target_event_bound', c.state['failure'])

    def test_missing_initialized_flag_is_not_completion(self):
        c = self.create().start(); claim, pv = self.claim()
        self.fixture.send(volume()); self.wait(lambda: c.state['sequence'] == 1)
        c.bind_target(claim, pv, volume())
        partial = volume('partial'); del partial['status']['restoreInitiated']
        self.fixture.send(partial); self.wait(lambda: c.state['failure'] is not None)
        self.assertEqual('target_drift', c.state['failure'])
        self.assertFalse(c.state['metadata_eligible'])

    def test_lost_claim_reply_cannot_adopt_complete_matching_events(self):
        c = self.create().start()
        c.perform_create('storageclass_create', self.mutation('StorageClass', UID(8)), lambda _: None)
        def lost(_):
            self.fixture.send(volume()); self.fixture.send(volume('finish', (True, False)))
            self.wait(lambda: c.state['sequence'] == 2)
            raise RuntimeError('PRIVATE_LOST_CLAIM_REPLY')
        with self.assertRaises(RuntimeError): c.perform_create('claim_create', lost, lambda _: None)
        claim = self.mutation('PersistentVolumeClaim', UID(6))(None)
        with self.assertRaises(module.WatchRefused): c.bind_target(claim, {}, volume('finish', (True, False)))
        self.assertEqual('uncertain', self.journal.record['operations']['claim_create']['state'])
        self.assertIsNone(c.expected)

    def test_stream_failure_during_mutation_leaves_uncertain_without_replay(self):
        c = self.create().start()
        def mutation(intent):
            self.fixture.send({'message': 'PRIVATE_REMOTE_ERROR'}, 'ERROR')
            self.wait(lambda: c.state['failure'] is not None)
            return self.mutation('StorageClass', UID(8))(intent)
        with self.assertRaises(RuntimeError): c.perform_create('storageclass_create', mutation, lambda _: None)
        self.assertEqual('uncertain', self.journal.record['operations']['storageclass_create']['state'])
        callback = mock.Mock()
        with self.assertRaises(module.WatchRefused): c.perform_create('storageclass_create', callback, lambda _: None)
        callback.assert_not_called()

    def test_list_duplicate_identity_refuses_before_watch(self):
        c = self.create([page([volume(), volume()])])
        with self.assertRaises(module.WatchRefused): c.start()
        self.assertEqual('list_item_bound', c.state['failure'])
        self.assertEqual(1, len(self.fixture.requests))

    def test_list_remaining_items_without_continuation_refuses(self):
        incomplete = page(); incomplete['metadata']['remainingItemCount'] = 1
        c = self.create([incomplete])
        with self.assertRaises(module.WatchRefused): c.start()
        self.assertEqual('list_incomplete', c.state['failure'])

    def test_repeated_list_continuation_refuses(self):
        c = self.create([page(continuation='token'), page(continuation='token')])
        with self.assertRaises(module.WatchRefused): c.start()
        self.assertEqual('list_incomplete', c.state['failure'])

    def test_reopened_journal_sidecar_is_not_live_readiness(self):
        c = self.create().start(); c.close(); self.journal.close()
        self.journal = module.WatchJournal(self.journal.directory).open()
        with self.assertRaises(module.WatchRefused): module.Collector(self.journal, c.transport, source())
        self.assertEqual({}, self.journal.record['operations'])

    def test_fifo_replacement_refuses_without_blocking_or_overwriting(self):
        c = self.create().start(); path = self.journal.directory / 'watch.json'
        path.rename(self.journal.directory / 'original-watch.json'); os.mkfifo(path, 0o600)
        callback = mock.Mock()
        with self.assertRaises(module.WatchRefused): c.perform_create('storageclass_create', callback, lambda _: None)
        callback.assert_not_called()
        import stat
        self.assertTrue(stat.S_ISFIFO(path.lstat().st_mode))

    def test_partial_list_body_failure_charges_consumed_bytes_and_closes_both(self):
        c = self.create(); connection, response = mock.Mock(), mock.Mock()
        response.read.side_effect = module.http.client.IncompleteRead(b'private-truncated-prefix')
        with mock.patch.object(c.transport, '_request', return_value=(connection, response)):
            with self.assertRaises(module.WatchRefused): c.start()
        self.assertEqual(len(b'private-truncated-prefix'), c.state['list_bytes'])
        self.assertEqual('list_read', c.state['failure'])
        response.close.assert_called_once(); connection.close.assert_called_once()
        self.assertNotIn('private-truncated-prefix', (self.journal.directory / 'watch.json').read_text())

    def test_partial_watch_body_failure_charges_without_projection(self):
        c = self.create()
        response = mock.Mock(); response.readline.side_effect = module.http.client.IncompleteRead(b'private-prefix')
        c.response = response; c.connection = mock.Mock()
        c._read()
        self.assertEqual(len(b'private-prefix'), c.state['watch_bytes'])
        self.assertEqual('watch_read', c.state['failure'])
        self.assertEqual([], c.state['observations'])
        self.assertNotIn('private-prefix', (self.journal.directory / 'watch.json').read_text())

    def test_frame_returned_after_deadline_is_charged_not_projected(self):
        c = self.create()
        def late_frame(_):
            c.deadline = time.monotonic() - 1
            return json.dumps({'type': 'MODIFIED', 'object': volume()}).encode() + b'\n'
        c.response = mock.Mock(); c.response.readline.side_effect = late_frame
        c.connection = mock.Mock(); c._read()
        self.assertEqual('deadline', c.state['failure'])
        self.assertGreater(c.state['watch_bytes'], 0)
        self.assertEqual([], c.state['observations'])


if __name__ == '__main__': unittest.main()
