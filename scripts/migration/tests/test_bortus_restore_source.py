"""Pinned disposable journal and actual loopback TLS; no operator/live execution."""
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import ssl
import sys
import tempfile
import time
import unittest
from unittest import mock

import test_bortus_restore_metadata as transport
import test_bortus_independent_restore_preflight as original

spec = importlib.util.spec_from_file_location('restore_source_tests_module',
    pathlib.Path(__file__).resolve().parent.parent / 'bortus-restore-source.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        transport.MetadataTests.setUpClass()
        cls.cert, cls.key = transport.MetadataTests.cert, transport.MetadataTests.key

    @classmethod
    def tearDownClass(cls): transport.MetadataTests.tearDownClass()

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='bortus-source-fixture-', dir=pathlib.Path.home())
        os.chmod(self.folder.name, 0o700)
        self.path = pathlib.Path(self.folder.name) / 'checkpoint.json'
        client, self.record = original.prepared()
        self.path.write_bytes(json.dumps(self.record).encode()); os.chmod(self.path, 0o600)
        self.digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.fixture = transport.Fixture(self.cert, self.key)
        self.patch = mock.patch.object(module.metadata, 'APPROVED_ORIGIN', self.fixture.origin)
        self.patch.start(); self.calls = 0
        self.api = module.metadata.MetadataAPI(self.options, origin=self.fixture.origin)
        self.resources, self.source = {}, None
        aliases = {'pvc': 'claim', 'pv': 'pv', 'volumes.longhorn.io': 'volume',
            'deployment': 'deployment', 'helmrelease': 'helmrelease', 'kustomization': 'kustomization',
            'backuptargets.longhorn.io': 'backuptarget', 'replicaset': 'replicaset',
            'storageclass': 'storageclass', 'node': 'node'}
        for kind, resource in aliases.items(): self.add(resource, client.resources[kind])
        self.add('snapshot', client.owned[self.record['snapshot_name']])
        self.add('backup', client.owned[self.record['backup_name']])
        self.pods = [self.object('pod', pod) for pod in client.resources['pods']['items']]
        for resource, items in (('pv', [self.get_object('pv', 'pvc-fixture')]),
            ('pod', self.pods), ('claim', [self.get_object('claim', 'bortus-data')]),
            ('storageclass', [self.get_object('storageclass', 'longhorn')])):
            self.resources[module.metadata.RESOURCES[resource][0]] = self.page(resource, items)
        self.fixture.body = lambda path: copy.deepcopy(self.resources[path])

    def object(self, resource, obj):
        value = copy.deepcopy(obj)
        _, version, kind, namespace = module.metadata.RESOURCES[resource]
        value.update(apiVersion=version, kind=kind)
        if not namespace: value['metadata'].pop('namespace', None)
        return value

    def add(self, resource, obj):
        value = self.object(resource, obj)
        self.resources[module.metadata.RESOURCES[resource][0] + '/' + value['metadata']['name']] = value

    def get_object(self, resource, name):
        return self.resources[module.metadata.RESOURCES[resource][0] + '/' + name]

    def page(self, resource, items):
        value = transport.page(resource)
        value['items'] = items
        return value

    def options(self):
        self.calls += 1
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cafile=str(self.cert))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return context, {'Authorization': 'Bearer PUBLIC_ROTATION_' + str(self.calls)}

    def open(self):
        self.source = module.SourceFence(self.path, self.digest, original.IMAGE, 'other-node', self.api)
        return self.source

    def tearDown(self):
        if self.source: self.source.close()
        self.patch.stop(); self.fixture.close(); self.folder.cleanup()

    def refuse(self, action, expected=None):
        try: action()
        except module.SourceRefused as error:
            self.assertIsNone(error.__context__); self.assertIsNone(error.__cause__)
            self.assertNotIn('PRIVATE_SYNTHETIC', str(error))
            if expected: self.assertEqual(error.code, expected)
            return
        self.fail('Expected fixed source refusal')

    def test_actual_tls_prepare_and_repeat_selected_identity_fence(self):
        source = self.open()
        proposals = source.prepare(deadline=time.monotonic() + 5)
        proof = source.check(deadline=time.monotonic() + 5)
        self.assertEqual(proposals['checkpoint_run_id'], self.record['run_id'])
        self.assertEqual(proposals['source_node_name'], 'node-fixture')
        self.assertEqual(proof['checkpoint_journal_sha256'], self.digest)
        self.assertEqual(proof['claim']['uid'], self.record['baseline']['identities']['claim']['uid'])
        self.assertEqual(set(proof), {'checkpoint_journal_sha256', 'original_ciphertext_sha256',
            'claim', 'pv', 'volume', 'backup'})
        self.assertNotIn('not-for-report', json.dumps(proof))
        self.assertEqual(self.calls, len(self.fixture.requests))
        self.assertGreater(self.calls, 20)
        self.assertFalse(any('secrets' in path for path, _ in self.fixture.requests))

    def test_created_target_does_not_suppress_inventory_or_adopt_targets(self):
        source = self.open()
        name = 'bortus-restore-' + self.record['run_id']
        path = module.metadata.RESOURCES['storageclass'][0]
        self.resources[path]['items'].append(transport.item('storageclass', name, 'new-uid'))
        before = copy.deepcopy(self.resources)
        self.assertEqual(source.check(deadline=time.monotonic()+5)['backup']['uid'],
            self.record['backup_identity']['uid'])
        self.refuse(lambda: source.prepare(deadline=time.monotonic()+5), 'source')
        self.assertEqual(self.resources, before)

    def test_original_identity_and_completed_backup_drift_still_refuse(self):
        source = self.open()
        backup = self.get_object('backup', self.record['backup_name'])
        backup['status']['state'] = 'Error'
        self.refuse(lambda: source.check(deadline=time.monotonic()+5), 'source')
        backup['status']['state'] = 'Completed'
        self.get_object('claim', 'bortus-data')['metadata']['uid'] = 'foreign-uid'
        self.refuse(lambda: source.check(deadline=time.monotonic()+5), 'source')

    def test_complete_source_collections_required(self):
        source = self.open()
        self.resources[module.metadata.RESOURCES['pod'][0]]['metadata']['continue'] = 'next'
        self.refuse(lambda: source.check(deadline=time.monotonic()+5), 'transport')

    def test_additional_source_consumer_refuses(self):
        source = self.open()
        other = copy.deepcopy(self.pods[0])
        other['metadata'].update(name='other-consumer', uid='other-uid')
        self.resources[module.metadata.RESOURCES['pod'][0]]['items'].append(other)
        self.refuse(lambda: source.check(deadline=time.monotonic()+5), 'source')

    def test_checkpoint_content_or_inode_substitution_refuses_before_api(self):
        for change in ('content', 'inode'):
            with self.subTest(change=change):
                if self.source: self.source.close(); self.source = None
                self.path.write_bytes(json.dumps(self.record).encode()); os.chmod(self.path, 0o600)
                source = self.open()
                if change == 'content': self.path.write_bytes(b'PRIVATE_SYNTHETIC_JOURNAL')
                else:
                    replacement = self.path.with_name('replacement.json')
                    replacement.write_bytes(self.path.read_bytes()); os.chmod(replacement, 0o600)
                    os.replace(replacement, self.path)
                before = len(self.fixture.requests)
                self.refuse(lambda: source.check(deadline=time.monotonic()+5), 'ownership')
                self.assertEqual(len(self.fixture.requests), before)

    def test_checkpoint_change_during_reads_refuses_after_source_validation(self):
        source = self.open()
        original_body = self.fixture.body
        def response(path):
            if path.endswith('/other-node'): self.path.write_bytes(b'PRIVATE_SYNTHETIC_JOURNAL')
            return original_body(path)
        self.fixture.body = response
        self.refuse(lambda: source.check(deadline=time.monotonic()+5), 'ownership')

    def test_private_callback_failure_not_retained_in_public_error(self):
        source = self.open()
        with mock.patch.object(module.preflight, 'validate_source', side_effect=RuntimeError('PRIVATE_SYNTHETIC_SOURCE')):
            self.refuse(lambda: source.check(deadline=time.monotonic()+5), 'source')

    def test_deadline_and_scope_cannot_select_external_namespace_or_owner(self):
        source = self.open()
        self.refuse(lambda: source.check(deadline=time.monotonic()-1), 'deadline')
        client = module.ScopedClient(self.api, time.monotonic()+5)
        for kind, name, namespace in [('deployment', 'other', 'bortus'), ('pods', None, 'other'),
            ('helmrelease', 'bortus', 'other'), ('secrets', None, 'bortus')]:
            self.refuse(lambda: client.get(kind, name, namespace), 'scope')
        self.assertEqual(self.fixture.requests, [])

    def test_malformed_journal_and_wrong_digest_close_owned_descriptors(self):
        before = len(list(pathlib.Path('/proc/self/fd').iterdir()))
        self.refuse(lambda: module.SourceFence(self.path, '0'*64, original.IMAGE, 'other-node', self.api), 'checkpoint')
        self.assertEqual(len(list(pathlib.Path('/proc/self/fd').iterdir())), before)
        self.path.write_bytes(b'PRIVATE_SYNTHETIC_MALFORMED')
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.refuse(lambda: module.SourceFence(self.path, digest, original.IMAGE, 'other-node', self.api), 'ownership')
        self.assertEqual(len(list(pathlib.Path('/proc/self/fd').iterdir())), before)

    def test_journal_symlink_hardlink_modes_and_parent_write_refuse(self):
        before = len(list(pathlib.Path('/proc/self/fd').iterdir()))
        os.chmod(self.path, 0o644)
        self.refuse(self.open, 'ownership'); os.chmod(self.path, 0o600)
        os.link(self.path, self.path.with_name('linked'))
        self.refuse(self.open, 'ownership'); self.path.with_name('linked').unlink()
        target = self.path.with_name('target'); self.path.rename(target); self.path.symlink_to(target)
        self.refuse(self.open, 'ownership'); self.path.unlink(); target.rename(self.path)
        os.chmod(self.folder.name, 0o777)
        self.refuse(self.open, 'ownership'); os.chmod(self.folder.name, 0o700)
        self.assertEqual(len(list(pathlib.Path('/proc/self/fd').iterdir())), before)

    def test_source_close_owned_descriptors_and_refuses_reuse(self):
        before = len(list(pathlib.Path('/proc/self/fd').iterdir()))
        source = self.open()
        self.assertGreater(len(list(pathlib.Path('/proc/self/fd').iterdir())), before)
        source.close()
        self.assertEqual(len(list(pathlib.Path('/proc/self/fd').iterdir())), before)
        self.refuse(lambda: source.check(deadline=time.monotonic()+5), 'ownership')

    def test_directory_fstat_failure_closes_every_just_opened_descriptor(self):
        before = len(list(pathlib.Path('/proc/self/fd').iterdir()))
        original_fstat = os.fstat
        calls = 0
        def fault(fd):
            nonlocal calls
            calls += 1
            if calls == 2: raise OSError('PRIVATE_SYNTHETIC_DIRECTORY_FSTAT')
            return original_fstat(fd)
        with mock.patch.object(module.os, 'fstat', fault): self.refuse(self.open, 'ownership')
        self.assertEqual(len(list(pathlib.Path('/proc/self/fd').iterdir())), before)


if __name__ == '__main__': unittest.main()
