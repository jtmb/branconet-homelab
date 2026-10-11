"""Actual loopback TLS plus owned POSIX journal; no production or operator reads."""
import copy
import hashlib
import http.server
import importlib.util
import json
import os
import pathlib
import queue
import ssl
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

import test_bortus_restore_watch as tls

HERE = pathlib.Path(__file__).parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


m = load('restore_mutation_tests', HERE.parent / 'bortus-restore-mutations.py')
fixtures = load('restore_mutation_health_fixtures', HERE / 'test_bortus_restored_consumer_fence.py')
RUN = '123456abcdef'
NAME = 'bortus-restore-' + RUN


class WatchResponse:
    def __init__(self):
        self.frames, self.closed = queue.Queue(), False

    def readline(self, cap):
        result = self.frames.get(timeout=5)
        assert len(result) <= cap
        return result

    def send(self, obj):
        self.frames.put(json.dumps({'type': 'MODIFIED', 'object': obj}).encode() + b'\n')

    def close(self):
        if not self.closed:
            self.closed = True
            self.frames.put(b'')


class TLSFixture:
    def __init__(self, cert, key):
        self.requests, self.errors = [], 0
        self.status = self.override = self.on_request = None
        self.delay = 0
        self.headers = {}
        self.drop = False
        self.get_body = None
        fixture = self
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *_): pass
            def handle(self):
                try: super().handle()
                except (OSError, ssl.SSLError): pass
            def dispatch(self):
                raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                body = json.loads(raw) if raw else None
                fixture.requests.append((self.command, self.path, body,
                                         self.headers.get('Authorization')))
                if fixture.on_request: fixture.on_request(self.command, body)
                if fixture.drop:
                    self.close_connection = True
                    return
                if self.command == 'GET':
                    result = fixture.get_body
                elif self.command == 'POST':
                    result = copy.deepcopy(body)
                    resource = {'StorageClass': 99, 'PersistentVolumeClaim': 4, 'Pod': 8}[body['kind']]
                    result['metadata'].update(uid=tls.UID(resource), resourceVersion='create-rv')
                    result['status'] = {'message': 'PRIVATE_SYNTHETIC_VALUE'}
                    result['metadata']['annotations'] = {'private': 'PRIVATE_SYNTHETIC_VALUE'}
                else:
                    result = {'apiVersion': 'v1', 'kind': 'Status', 'status': 'Success',
                        'details': {'name': NAME, 'uid': tls.UID(8), 'kind': 'pods', 'group': ''},
                        'message': 'PRIVATE_SYNTHETIC_VALUE'}
                if fixture.override is not None:
                    result = fixture.override(result) if callable(fixture.override) else fixture.override
                raw = result if type(result) is bytes else json.dumps(result).encode()
                self.send_response(fixture.status or (201 if self.command == 'POST' else 200))
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                for key, value in fixture.headers.items(): self.send_header(key, value)
                self.end_headers()
                try:
                    time.sleep(fixture.delay)
                    self.wfile.write(raw)
                except (OSError, ssl.SSLError): pass
            do_POST = do_DELETE = do_GET = dispatch
        class Server(http.server.ThreadingHTTPServer):
            daemon_threads = False
            def handle_error(self, *_): fixture.errors += 1
        self.server = Server(('127.0.0.1', 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01})
        self.thread.start()
        self.origin = 'https://localhost:' + str(self.server.server_port)

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)
        assert not self.thread.is_alive() and self.errors == 0


@unittest.skipUnless(os.name == 'posix', 'Owned real POSIX journals required')
class MutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tls.RestoreWatchTests.setUpClass()
        cls.cert, cls.key = tls.RestoreWatchTests.cert, tls.RestoreWatchTests.key

    @classmethod
    def tearDownClass(cls): tls.RestoreWatchTests.tearDownClass()

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='bortus-mutation-public-')
        self.addCleanup(self.cleanup)
        self.expected, self.objects = fixtures.fixture()
        e, o = self.expected, self.objects
        e['claim']['name'] = e['holder']['name'] = NAME
        o['claim']['metadata']['name'] = NAME
        o['claim']['spec']['storageClassName'] = NAME
        o['pv']['spec']['claimRef']['name'] = NAME
        labels = {'bortus-restore': RUN}
        self.proposals = [
            {'apiVersion': 'storage.k8s.io/v1', 'kind': 'StorageClass',
             'metadata': {'name': NAME, 'labels': labels}, 'provisioner': 'driver.longhorn.io',
             'reclaimPolicy': 'Retain', 'volumeBindingMode': 'Immediate', 'allowVolumeExpansion': True,
             'parameters': dict(m.preflight.PARAMETERS, fromBackup=e['backup_url'])},
            {'apiVersion': 'v1', 'kind': 'PersistentVolumeClaim', 'metadata': {'name': NAME,
             'namespace': 'bortus', 'labels': labels, 'annotations': {'helm.sh/resource-policy': 'keep'}},
             'spec': {'storageClassName': NAME, 'accessModes': ['ReadWriteOnce'],
                      'resources': {'requests': {'storage': '1Gi'}}}},
            {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': NAME, 'namespace': 'bortus',
             'labels': labels}, 'spec': m.data.health.holder_spec(e['holder_image'], NAME, e['node']['name'])}]
        digest = hashlib.sha256(m.canonical(self.proposals)).hexdigest()
        self.journal = m.data.watch.WatchJournal(pathlib.Path(self.folder.name) / 'run').open(
            m.data.watch.ownership.seed(RUN, 'a' * 64, digest))
        source = m.data.watch.Source(e['backup_url'], m.data.watch.completion.BackupIdentity(
            'backup', 'longhorn-system', e['backup']['uid'], 'backup-rv'),
            e['original_volume']['uid'], 'original-volume', e['original_pv']['uid'], e['original_claim']['uid'])
        self.response = WatchResponse()
        transport = m.data.watch.TLSAPI('https://localhost:6443', lambda: None)
        transport.list_page = lambda *_: ({'apiVersion': m.data.health.API, 'kind': 'VolumeList',
            'metadata': {'resourceVersion': 'opaque/list:rv', 'continue': ''}, 'items': []}, 128)
        transport.open_watch = lambda *_: (self.response, self.response)
        self.collector = m.data.watch.Collector(self.journal, transport, source).start()
        self.fixture = TLSFixture(self.cert, self.key)
        self.calls = 0
        self.patch = mock.patch.object(m.metadata, 'APPROVED_ORIGIN', self.fixture.origin)
        self.patch.start()
        self.api = m.MutationAPI(self.collector, self.options, self.proposals)

    def cleanup(self):
        if hasattr(self, 'patch'): self.patch.stop()
        if hasattr(self, 'collector'):
            self.collector.close()
            self.assertFalse(self.collector.thread.is_alive())
            self.assertTrue(self.response.closed)
        if hasattr(self, 'journal'): self.journal.close()
        if hasattr(self, 'fixture'): self.fixture.close()
        self.folder.cleanup()

    def options(self):
        self.calls += 1
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_verify_locations(cafile=str(self.cert))
        return context, {'Authorization': 'Bearer PUBLIC_ROTATION_' + str(self.calls)}

    def create(self, action='storageclass_create', seconds=3, validate=lambda _: None):
        return self.collector.perform_create(action,
            lambda intent: self.api.create(action, intent, deadline=time.monotonic() + seconds), validate)

    def wait(self, predicate):
        until = time.monotonic() + 2
        while not predicate():
            if time.monotonic() >= until: self.fail('Controlled watch timed out')
            time.sleep(.005)

    def prepare_delete(self):
        self.create(); self.create('claim_create')
        start = copy.deepcopy(self.objects['volume'])
        start['metadata']['resourceVersion'] = 'before-rv'
        start['status']['restoreRequired'] = True
        self.response.send(start); self.response.send(self.objects['volume'])
        self.wait(lambda: self.collector.state['sequence'] == 2)
        self.collector.bind_target(self.objects['claim'], self.objects['pv'], self.objects['volume'])
        self.collector.seal(self.objects['volume'])
        self.create('holder_create')
        pod = copy.deepcopy(self.proposals[2])
        pod['metadata'].update(uid=tls.UID(8), resourceVersion='fresh-rv')
        self.fixture.get_body = pod
        self.current = m.data.watch.ownership.identity(pod)
        self.fixture.requests.clear()

    def delete(self):
        acknowledgments = []
        result = self.journal.perform('holder_delete',
            lambda intent: self.api.delete(intent, deadline=time.monotonic() + 3),
            acknowledgments.append, delete_identity=self.current)
        return result, acknowledgments[0]

    def test_all_exact_create_bodies_pending_before_request_and_fresh_tls(self):
        seen = []
        def pending(method, body):
            disk = json.loads((self.journal.directory / 'journal.json').read_text())
            action = next(k for k in m.CREATE if self.api.proposals[k]['kind'] == body['kind'])
            self.assertEqual(disk['operations'][action]['state'], 'pending')
            self.assertEqual(body, self.api.proposals[action])
        self.fixture.on_request = pending
        self.create(validate=seen.append)
        self.assertNotIn('PRIVATE_SYNTHETIC_VALUE', json.dumps(seen))
        self.prepare_delete_creates_remaining()
        self.assertEqual(self.calls, 3)
        self.assertEqual([r[1] for r in self.fixture.requests],
            [m.metadata.RESOURCES[k][0] for k in ('storageclass', 'claim', 'pod')])
        self.assertEqual([r[3] for r in self.fixture.requests],
            ['Bearer PUBLIC_ROTATION_' + str(n) for n in (1, 2, 3)])

    def prepare_delete_creates_remaining(self):
        self.create('claim_create')
        start = copy.deepcopy(self.objects['volume']); start['status']['restoreRequired'] = True
        start['metadata']['resourceVersion'] = 'before-rv'
        self.response.send(start); self.response.send(self.objects['volume'])
        self.wait(lambda: self.collector.state['sequence'] == 2)
        self.collector.bind_target(self.objects['claim'], self.objects['pv'], self.objects['volume'])
        self.collector.seal(self.objects['volume'])
        self.create('holder_create')

    def test_proposal_copy_cannot_change_dispatched_body(self):
        self.proposals[0]['parameters']['encrypted'] = 'false'
        self.create()
        self.assertEqual(self.fixture.requests[0][2]['parameters']['encrypted'], 'true')

    def test_boolean_integer_and_extra_proposals_refuse_even_with_reviewed_digest(self):
        for change in (lambda p: p[0].update(allowVolumeExpansion=1),
                       lambda p: p[2]['spec'].update(automountServiceAccountToken=True),
                       lambda p: p[2]['spec']['containers'][0].update(env=[]),
                       lambda p: p[1]['metadata'].update(namespace='default'),
                       lambda p: p[0]['parameters'].update(encrypted='false')):
            with self.subTest(change=change):
                p = copy.deepcopy(self.proposals); change(p)
                original = self.journal.record['reviewed_proposal_sha256']
                self.journal.record['reviewed_proposal_sha256'] = hashlib.sha256(m.canonical(p)).hexdigest()
                self.collector.state['proposal_sha256'] = self.journal.record['reviewed_proposal_sha256']
                with self.collector.lock:
                    self.journal.save(); self.collector._save()
                with self.assertRaises(m.MutationRefused): m.MutationAPI(self.collector, self.options, p)
                self.journal.record['reviewed_proposal_sha256'] = original
                self.collector.state['proposal_sha256'] = original
                with self.collector.lock:
                    self.journal.save(); self.collector._save()
        self.assertEqual(self.calls, 0)

    def test_oversized_or_custom_proposal_refuses_before_serialization(self):
        with self.assertRaises(m.MutationRefused):
            m.MutationAPI(self.collector, self.options, [{'x': 'x' * 65537}])
        class Private:
            def __iter__(self): raise RuntimeError('PRIVATE_SYNTHETIC_VALUE')
        with self.assertRaises(m.MutationRefused):
            m.MutationAPI(self.collector, self.options, Private())
        self.assertEqual(self.calls, 0)

    def test_no_reopen_adoption_or_duplicate_dispatch_after_lost_reply(self):
        self.fixture.drop = True
        with self.assertRaises(RuntimeError): self.create()
        self.assertEqual(self.journal.record['operations']['storageclass_create']['state'], 'uncertain')
        self.assertEqual(len(self.fixture.requests), 1)
        with self.assertRaises(m.MutationRefused): m.MutationAPI(self.collector, self.options, self.proposals)
        with self.assertRaises(RuntimeError): self.create()
        self.assertEqual(len(self.fixture.requests), 1)

    def test_bare_callback_without_durable_pending_refuses_before_options(self):
        with self.assertRaises(m.MutationRefused) as caught:
            self.api.create('storageclass_create', {}, deadline=time.monotonic() + 2)
        self.assertIsNone(caught.exception.__context__)
        self.assertEqual(self.calls, 0)

    def test_journal_tamper_refuses_before_tls_dispatch(self):
        def callback(intent):
            path = self.journal.directory / 'journal.json'
            obj = json.loads(path.read_text()); obj['operations']['storageclass_create']['started_at_utc'] = \
                '2020-01-01T00:00:00+00:00'
            path.write_text(json.dumps(obj))
            return self.api.create('storageclass_create', intent, deadline=time.monotonic() + 2)
        with self.assertRaises(RuntimeError):
            self.collector.perform_create('storageclass_create', callback, lambda _: None)
        self.assertEqual(self.calls, 0)

    def test_watch_drains_during_http_callback_without_lock(self):
        def request(*_):
            self.response.send(self.objects['volume'])
            self.wait(lambda: self.collector.state['sequence'] == 1)
        self.fixture.on_request = request
        self.create()
        self.assertEqual(self.collector.state['sequence'], 1)

    def test_watch_failure_after_post_leaves_uncertain(self):
        def request(*_):
            self.response.close()
            self.wait(lambda: self.collector.state['failure'] is not None)
        self.fixture.on_request = request
        with self.assertRaises(RuntimeError): self.create()
        self.assertEqual(self.journal.record['operations']['storageclass_create']['state'], 'uncertain')

    def test_exact_delete_fresh_get_preconditions_and_submitted_only(self):
        self.prepare_delete()
        _, ack = self.delete()
        self.assertEqual([r[0] for r in self.fixture.requests], ['GET', 'DELETE'])
        self.assertEqual(self.fixture.requests[1][2], {'apiVersion': 'v1', 'kind': 'DeleteOptions',
            'preconditions': {'uid': tls.UID(8), 'resourceVersion': 'fresh-rv'}})
        self.assertEqual(ack, {'submitted': True, 'name': NAME, 'namespace': 'bortus',
            'uid': tls.UID(8), 'deletion_observed': False})
        self.assertEqual(self.calls, 5)

    def test_replaced_uid_before_delete_refuses_no_delete(self):
        self.prepare_delete(); self.fixture.get_body['metadata']['uid'] = tls.UID(88)
        with self.assertRaises(RuntimeError): self.delete()
        self.assertEqual([r[0] for r in self.fixture.requests], ['GET'])

    def test_changed_rv_before_delete_refuses_no_delete(self):
        self.prepare_delete(); self.fixture.get_body['metadata']['resourceVersion'] = 'changed-rv'
        with self.assertRaises(RuntimeError): self.delete()
        self.assertEqual([r[0] for r in self.fixture.requests], ['GET'])

    def test_deleting_holder_before_delete_refuses(self):
        self.prepare_delete(); self.fixture.get_body['metadata']['deletionTimestamp'] = 'now'
        with self.assertRaises(RuntimeError): self.delete()
        self.assertEqual([r[0] for r in self.fixture.requests], ['GET'])

    def test_foreign_run_before_delete_refuses(self):
        self.prepare_delete(); self.fixture.get_body['metadata']['labels'] = {'bortus-restore': 'foreign'}
        with self.assertRaises(RuntimeError): self.delete()
        self.assertEqual([r[0] for r in self.fixture.requests], ['GET'])

    def test_matching_pod_delete_ack_rv_may_advance(self):
        self.prepare_delete()
        def response(obj):
            if obj.get('kind') == 'Status':
                pod = copy.deepcopy(self.fixture.get_body)
                pod['metadata']['resourceVersion'] = 'after-rv'
                pod['metadata']['deletionTimestamp'] = 'now'
                return pod
            return obj
        self.fixture.override = response
        self.assertFalse(self.delete()[1]['deletion_observed'])

    def test_wrong_delete_status_uid_refuses_submission(self):
        self.prepare_delete()
        def response(obj):
            if obj.get('kind') == 'Status': obj['details']['uid'] = tls.UID(88)
            return obj
        self.fixture.override = response
        with self.assertRaises(RuntimeError): self.delete()
        self.assertEqual(self.journal.record['operations']['holder_delete']['state'], 'uncertain')

    def test_wrong_create_identity_refuses_and_drops_private_body(self):
        self.fixture.override = lambda obj: dict(obj, metadata=dict(obj['metadata'], uid=tls.UID(99),
            labels={'bortus-restore': 'foreign'}))
        observed = []
        def callback(intent):
            try: self.api.create('storageclass_create', intent, deadline=time.monotonic() + 2)
            except m.MutationRefused as error:
                self.assertIsNone(error.__context__); self.assertIsNone(error.__cause__)
                self.assertNotIn('PRIVATE_SYNTHETIC_VALUE', str(error)); observed.append(error.code)
                raise
        with self.assertRaises(RuntimeError):
            self.collector.perform_create('storageclass_create', callback, lambda _: None)
        self.assertTrue(observed)

    def test_duplicate_json_refuses(self):
        self.fixture.override = b'{"apiVersion":"v1","apiVersion":"PRIVATE_SYNTHETIC_VALUE"}'
        with self.assertRaises(RuntimeError): self.create()

    def test_redirect_refuses_no_retry(self):
        self.fixture.status = 307
        with self.assertRaises(RuntimeError): self.create()
        self.assertEqual(len(self.fixture.requests), 1)

    def test_encoded_reply_refuses(self):
        self.fixture.headers = {'Content-Encoding': 'gzip'}
        with self.assertRaises(RuntimeError): self.create()

    def test_response_bound_refuses(self):
        with mock.patch.object(m.metadata, 'MAX_BYTES', 128):
            with self.assertRaises(RuntimeError): self.create()

    def test_deadline_during_body_refuses_and_closes_owned_request(self):
        self.fixture.delay = .15
        with self.assertRaises(RuntimeError): self.create(seconds=.03)
        self.assertEqual(self.journal.record['operations']['storageclass_create']['state'], 'uncertain')

    def test_expired_deadline_no_options(self):
        with self.assertRaises(RuntimeError): self.create(seconds=-1)
        self.assertEqual(self.calls, 0)

    def test_fresh_auth_withdrawal_no_dispatch(self):
        def options(): raise RuntimeError('PRIVATE_SYNTHETIC_VALUE')
        self.api.options = options
        with self.assertRaises(RuntimeError): self.create()
        self.assertEqual(self.fixture.requests, [])

    def test_insecure_context_refuses_no_http(self):
        self.api.options = lambda: (ssl._create_unverified_context(), {})
        with self.assertRaises(RuntimeError): self.create()
        self.assertEqual(self.fixture.requests, [])

    def test_unknown_ca_refuses_no_http(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        self.api.options = lambda: (context, {})
        with self.assertRaises(RuntimeError): self.create()
        self.assertEqual(self.fixture.requests, [])

    def test_actual_mutual_tls_with_fresh_context(self):
        self.fixture.server.socket.context.load_verify_locations(cafile=str(self.cert))
        self.fixture.server.socket.context.verify_mode = ssl.CERT_REQUIRED
        def options():
            context, headers = self.options()
            context.load_cert_chain(self.cert, self.key)
            return context, headers
        self.api.options = options
        self.create(); self.create('claim_create')
        self.assertEqual(self.calls, 2)

    def test_actual_mutual_tls_missing_client_certificate_refuses(self):
        self.fixture.server.socket.context.load_verify_locations(cafile=str(self.cert))
        self.fixture.server.socket.context.verify_mode = ssl.CERT_REQUIRED
        with self.assertRaises(RuntimeError): self.create()
        self.assertEqual(self.fixture.requests, [])

    def test_late_connect_cannot_dispatch_after_deadline(self):
        real_connect = m.http.client.HTTPSConnection.connect
        def connect(connection):
            real_connect(connection); time.sleep(.05)
        with mock.patch.object(m.http.client.HTTPSConnection, 'connect', connect):
            with self.assertRaises(RuntimeError): self.create(seconds=.025)
        self.assertEqual(self.fixture.requests, [])

    def test_response_close_failure_drops_value_and_closes_connection(self):
        real_response = m.http.client.HTTPSConnection.getresponse
        real_close = m.http.client.HTTPSConnection.close
        closed = []
        def response(connection):
            result = real_response(connection); original = result.close
            def badclose():
                original(); closed.append('response')
                raise RuntimeError('PRIVATE_SYNTHETIC_VALUE')
            result.close = badclose
            return result
        def connectionclose(connection):
            closed.append('connection')
            try: real_close(connection)
            finally: self.assertIsNone(connection.sock)
        observed = []
        def callback(intent):
            try: return self.api.create('storageclass_create', intent, deadline=time.monotonic() + 3)
            except m.MutationRefused as error:
                self.assertIsNone(error.__context__); self.assertIsNone(error.__cause__)
                frame = error.__traceback__
                while frame:
                    self.assertNotIn('raw', frame.tb_frame.f_locals)
                    self.assertNotIn('response', frame.tb_frame.f_locals)
                    frame = frame.tb_next
                observed.append(error.code)
                raise
        with mock.patch.object(m.http.client.HTTPSConnection, 'getresponse', response), \
                mock.patch.object(m.http.client.HTTPSConnection, 'close', connectionclose):
            with self.assertRaises(RuntimeError):
                self.collector.perform_create('storageclass_create', callback, lambda _: None)
        self.assertTrue(observed)
        self.assertIn('response', closed); self.assertIn('connection', closed)

    def test_options_deadline_consumption_no_connect(self):
        def options(): time.sleep(.05); return self.options()
        self.api.options = options
        with self.assertRaises(RuntimeError): self.create(seconds=.02)
        self.assertEqual(self.fixture.requests, [])

    def test_secret_or_arbitrary_action_refuses(self):
        with self.assertRaises(m.MutationRefused):
            self.api.create('secret_create', {}, deadline=time.monotonic() + 1)
        self.assertEqual(self.calls, 0)


if __name__ == '__main__': unittest.main()
