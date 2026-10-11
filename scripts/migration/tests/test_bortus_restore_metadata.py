"""Disposable loopback TLS metadata; no operator credentials or live API."""
import copy
import http.server
import importlib.util
import json
import pathlib
import ssl
import sys
import threading
import time
import unittest
from unittest import mock

import test_bortus_restore_watch as fixtures

spec = importlib.util.spec_from_file_location('restore_metadata_tests_module',
    pathlib.Path(__file__).resolve().parent.parent / 'bortus-restore-metadata.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def item(resource='pv', name='fixture', uid='opaque-uid'):
    _, version, kind, namespace = module.RESOURCES[resource]
    return {'apiVersion': version, 'kind': kind, 'metadata': {
        'name': name, 'uid': uid, 'resourceVersion': 'opaque-rv', **(
            {'namespace': namespace} if namespace else {})}}


def page(resource='pv', items=None):
    obj = item(resource)
    return {'apiVersion': obj['apiVersion'], 'kind': obj['kind'] + 'List',
        'metadata': {'resourceVersion': 'opaque-list'}, 'items': items or []}


class Fixture:
    def __init__(self, cert, key):
        self.body = item()
        self.status = 200
        self.headers = {}
        self.delay = 0
        self.trickle = False
        self.requests = []
        self.errors = 0
        fixture = self
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *_): pass
            def handle(self):
                try: super().handle()
                except (ConnectionResetError, BrokenPipeError, ssl.SSLError): pass
            def do_GET(self):
                fixture.requests.append((self.path, self.headers.get('Authorization')))
                body = fixture.body
                body = body if type(body) is bytes else json.dumps(body).encode()
                self.send_response(fixture.status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                for key, value in fixture.headers.items(): self.send_header(key, value)
                self.end_headers()
                try:
                    if fixture.trickle:
                        for byte in body:
                            self.wfile.write(bytes([byte])); self.wfile.flush()
                            time.sleep(fixture.delay)
                    else:
                        time.sleep(fixture.delay)
                        self.wfile.write(body)
                except (OSError, ssl.SSLError): pass
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


class MetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.RestoreWatchTests.setUpClass()
        cls.cert, cls.key = fixtures.RestoreWatchTests.cert, fixtures.RestoreWatchTests.key

    @classmethod
    def tearDownClass(cls): fixtures.RestoreWatchTests.tearDownClass()

    def setUp(self):
        self.fixture = Fixture(self.cert, self.key)
        self.calls = 0
        self.origin_patch = mock.patch.object(module, 'APPROVED_ORIGIN', self.fixture.origin)
        self.origin_patch.start()
        self.api = module.MetadataAPI(self.options, origin=self.fixture.origin)

    def tearDown(self):
        self.origin_patch.stop(); self.fixture.close()

    def options(self):
        self.calls += 1
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cafile=str(self.cert))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return context, {'Authorization': 'Bearer PUBLIC_ROTATION_' + str(self.calls)}

    def get(self, resource='pv', name='fixture', seconds=3):
        return self.api.get(resource, name, deadline=time.monotonic() + seconds)

    def list(self, resource='pv'):
        return self.api.list(resource, deadline=time.monotonic() + 3)

    def refuse(self, action, expected=None):
        try: action()
        except module.MetadataRefused as error:
            self.assertIsNone(error.__context__)
            self.assertIsNone(error.__cause__)
            self.assertNotIn('PRIVATE_SYNTHETIC', str(error))
            if expected: self.assertEqual(error.code, expected)
            return
        self.fail('Expected fixed refusal')

    def test_named_get_all_scoped_resources(self):
        for resource, (path, _, _, _) in module.RESOURCES.items():
            self.fixture.body = item(resource)
            self.assertEqual(self.get(resource), self.fixture.body)
            self.assertEqual(self.fixture.requests[-1][0], path + '/fixture')

    def test_lists_complete_and_fresh_credentials(self):
        for resource in module.LISTABLE:
            self.fixture.body = page(resource, [item(resource)])
            self.assertEqual(self.list(resource), self.fixture.body)
        self.assertEqual(self.calls, 4)
        self.assertEqual([auth for _, auth in self.fixture.requests],
            ['Bearer PUBLIC_ROTATION_' + str(n) for n in range(1, 5)])

    def test_scope_rejected_before_credentials(self):
        for name in ('../secret', 'a/b', 'a?x=y', 'a..b', '-a', 'a-', 'A', 'a' * 64):
            self.refuse(lambda: self.get(name=name), 'request_scope')
        for resource in ('secret', '/api/v1/secrets', None, []):
            self.refuse(lambda: self.get(resource), 'request_scope')
        self.refuse(lambda: self.list('node'), 'request_scope')
        self.assertEqual(self.calls, 0); self.assertEqual(self.fixture.requests, [])

    def test_configuration_closed(self):
        for origin in (None, [], 'http://localhost', 'https://[malformed', self.fixture.origin + '/x'):
            self.refuse(lambda: module.MetadataAPI(self.options, origin=origin), 'configuration')

    def test_deadlines_reject_before_credentials(self):
        for deadline in (True, float('nan'), float('inf'), time.monotonic()-1, time.monotonic()+400):
            self.refuse(lambda: self.api.get('pv', 'fixture', deadline=deadline), 'deadline')
        self.assertEqual(self.calls, 0)

    def test_tls_must_verify_host_and_peer(self):
        for check in ('hostname', 'peer', 'minimum'):
            context, headers = self.options()
            if check == 'hostname': context.check_hostname = False
            if check == 'peer':
                context.check_hostname = False; context.verify_mode = ssl.CERT_NONE
            if check == 'minimum': context.minimum_version = ssl.TLSVersion.TLSv1
            with mock.patch.object(self.api, 'options', return_value=(context, headers)):
                self.refuse(self.get, 'tls_configuration')
        self.assertEqual(self.fixture.requests, [])

    def test_revoked_provider_never_uses_previous_context(self):
        self.get()
        with mock.patch.object(self.api, 'options', side_effect=ValueError('PRIVATE_SYNTHETIC_CREDENTIAL')):
            self.refuse(self.get, 'metadata_json')
        self.assertEqual(len(self.fixture.requests), 1)

    def test_malformed_json_fixed_without_body_chain(self):
        for raw in (b'PRIVATE_SYNTHETIC_BODY', b'\xff', b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'):
            self.fixture.body = raw
            self.refuse(self.get, 'metadata_json')

    def test_tree_bounds(self):
        for raw in (json.dumps({'x': 'x' * 65537}).encode(), b'[' * 34 + b'0' + b']' * 34):
            self.fixture.body = raw
            self.refuse(self.get, 'metadata_bound')

    def test_body_bound(self):
        self.fixture.body = b'x' * 128
        with mock.patch.object(module, 'MAX_BYTES', 64):
            self.refuse(self.get, 'metadata_bound')

    def test_redirect_compression_and_status_refuse(self):
        for status in (301, 403, 404, 500):
            self.fixture.status = status
            self.refuse(self.get, 'metadata_response')
        self.fixture.status = 200
        self.fixture.headers = {'Content-Encoding': 'gzip'}
        self.refuse(self.get, 'metadata_response')

    def test_identity_and_shape(self):
        mutations = [('apiVersion', 'bad'), ('kind', 'Secret')]
        for key, value in mutations:
            self.fixture.body = item(); self.fixture.body[key] = value
            self.refuse(self.get, 'metadata_shape')
        for key, value in (('name', 'other'), ('uid', ''), ('resourceVersion', ''), ('namespace', 'other')):
            self.fixture.body = item(); self.fixture.body['metadata'][key] = value
            self.refuse(self.get, 'metadata_identity')

    def test_paginated_or_malformed_list(self):
        for key, value in (('continue', 'more'), ('remainingItemCount', 1),
                           ('remainingItemCount', False), ('resourceVersion', '')):
            self.fixture.body = page(); self.fixture.body['metadata'][key] = value
            self.refuse(self.list, 'metadata_incomplete')
        self.fixture.body = page(); self.fixture.body['kind'] = 'SecretList'
        self.refuse(self.list, 'metadata_incomplete')

    def test_duplicate_list_names_and_uids(self):
        for second in (item(name='fixture', uid='other'), item(name='other')):
            self.fixture.body = page(items=[item(), second])
            self.refuse(self.list, 'metadata_identity')
        self.fixture.body = page(items=[item(name='bad..name')])
        self.refuse(self.list, 'metadata_identity')

    def test_collection_bound(self):
        self.fixture.body = page(items=[item(), item(name='other', uid='other')])
        with mock.patch.object(module, 'MAX_ITEMS', 1):
            self.refuse(self.list, 'metadata_incomplete')

    def test_slow_trickle_absolute_deadline(self):
        self.fixture.trickle = True; self.fixture.delay = .025
        start = time.monotonic()
        self.refuse(lambda: self.get(seconds=.08))
        self.assertLess(time.monotonic() - start, .5)

    def test_owned_closure_even_when_response_close_fails(self):
        context, headers = self.options()
        response = mock.Mock(status=200)
        response.getheader.side_effect = lambda key, default=None: {
            'Content-Type': 'application/json', 'Content-Length': '0'}.get(key, default)
        response.read1.return_value = b''
        response.close.side_effect = OSError('PRIVATE_SYNTHETIC_CLOSE')
        sock = mock.Mock(spec=ssl.SSLSocket)
        sock.getpeercert.return_value = {'subject': 'fixture'}
        sock.version.return_value = 'TLSv1.3'
        connection = mock.Mock(sock=sock)
        connection.getresponse.return_value = response
        with mock.patch.object(module.http.client, 'HTTPSConnection', return_value=connection):
            self.refuse(self.get, 'metadata_transport')
        response.close.assert_called_once(); connection.close.assert_called_once()

    def test_closure_failure_drops_successful_response_before_public_error(self):
        original = module.http.client.HTTPResponse.close
        def failing_close(response):
            original(response)
            raise OSError('PRIVATE_SYNTHETIC_CLOSE')
        with mock.patch.object(module.http.client.HTTPResponse, 'close', failing_close):
            try: self.get()
            except module.MetadataRefused as error:
                self.assertEqual(error.code, 'metadata_transport')
                traceback = error.__traceback__
                while traceback:
                    if traceback.tb_frame.f_code.co_name == 'get' and 'value' in traceback.tb_frame.f_locals:
                        self.assertIsNone(traceback.tb_frame.f_locals['value'])
                    traceback = traceback.tb_next
            else: self.fail('Expected closure refusal')

    def test_connect_expiration_sends_no_get(self):
        sock = mock.Mock(spec=ssl.SSLSocket)
        sock.getpeercert.return_value = {'subject': 'fixture'}
        sock.version.return_value = 'TLSv1.3'
        connection = mock.Mock(sock=sock)
        def slow_connect(): time.sleep(.06)
        connection.connect.side_effect = slow_connect
        with mock.patch.object(module.http.client, 'HTTPSConnection', return_value=connection):
            self.refuse(lambda: self.get(seconds=.02), 'deadline')
        connection.request.assert_not_called(); connection.close.assert_called_once()


if __name__ == '__main__': unittest.main()
