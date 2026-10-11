"""Disposable TLS/POSIX/watch/age/SQLite composition; no operator or Node execution."""
import base64
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import yaml

import test_bortus_restore_mutations as transport
import test_bortus_independent_restore_preflight as cold
import test_bortus_restore_data as framing
import test_bortus_restored_consumer_fence as healthy

HERE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location('independent_coordinator_tests', HERE.parent / 'bortus-independent-restore.py')
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
RUN = '123456abcdef'
NAME = 'bortus-restore-' + RUN


@unittest.skipUnless(os.name == 'posix', 'Real POSIX descriptors, age and tmpfs required')
class CoordinatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        transport.MutationTests.setUpClass()
        cls.cert, cls.key = transport.MutationTests.cert, transport.MutationTests.key

    @classmethod
    def tearDownClass(cls):
        transport.MutationTests.tearDownClass()

    def setUp(self):
        self.root_temp = tempfile.TemporaryDirectory(prefix='bortus-coordinator-public-', dir=pathlib.Path.home())
        self.root = pathlib.Path(self.root_temp.name)
        self.root.chmod(0o755)
        self.patches, self.children, self.commands = [], [], []
        self.addCleanup(self.cleanup)
        self.tmpfs_before = set(pathlib.Path('/dev/shm').glob('bortus-sqlite-*'))
        self.client, self.record = cold.prepared()
        # Public legacy fake IDs become valid UUIDs, preserving every reference.
        ids = {}
        def remap(value):
            if type(value) is dict:
                return {k: ids.setdefault(v, transport.tls.UID(100 + len(ids))) if k == 'uid' and type(v) is str
                        else remap(v) for k, v in value.items()}
            if type(value) is list: return [remap(v) for v in value]
            return value
        self.record = remap(self.record)
        self.resources, self.owned = remap(self.client.resources), remap(self.client.owned)
        # The older cold fixture uses a name-derived UID for both PV and Volume.
        # Actual API UIDs are distinct; retain their independently mapped source chain.
        self.record['baseline']['identities']['longhorn_volume']['uid'] = transport.tls.UID(500)
        self.resources['volumes.longhorn.io']['metadata']['uid'] = transport.tls.UID(500)
        self.expected, self.objects = healthy.fixture()
        e, o = self.expected, self.objects
        for key, old in (('original_claim', 'claim'), ('original_pv', 'pv'), ('original_volume', 'longhorn_volume')):
            e[key] = m.selected(self.record['baseline']['identities'][old])
        backup = self.owned[self.record['backup_name']]
        e['backup'] = m.selected(backup['metadata'])
        e['backup_url'] = self.record['backup_url']
        e['original_node'] = 'node-fixture'
        e['claim']['name'] = e['holder']['name'] = NAME
        e['node'] = m.selected(self.resources['node']['metadata'])
        o['node'] = copy.deepcopy(self.resources['node'])
        o['claim']['metadata']['name'] = NAME
        o['claim']['spec']['storageClassName'] = NAME
        o['pv']['spec']['claimRef']['name'] = NAME
        o['volume']['spec'].update(fromBackup=e['backup_url'], nodeID='other-node')
        o['volume']['status']['currentNodeID'] = 'other-node'
        o['engines']['items'][0]['spec']['nodeID'] = 'other-node'
        pod = o['pods']['items'][0]
        pod['metadata']['name'] = NAME
        pod['spec'] = m.health.holder_spec(e['holder_image'], NAME, 'other-node')
        o['backup'] = copy.deepcopy(backup)
        o['pvs']['items'][0] = copy.deepcopy(o['pv'])
        self.response = transport.WatchResponse()
        def read_watch(cap):
            # Match the real transport's 30s idle read bound, not the older tiny
            # five-second standalone mutation fixture queue timeout.
            result = self.response.frames.get(timeout=30)
            self.assertLessEqual(len(result), cap)
            return result
        self.response.readline = read_watch
        self.fixture = transport.TLSFixture(self.cert, self.key)
        self.fixture.override = self.respond
        self.fixture.get_body = {}
        self.requests = self.fixture.requests
        for module in (m.reader.metadata, m.source.metadata, m.reader.credentials):
            self.patch(module, 'APPROVED_ORIGIN', self.fixture.origin)
        encoded = lambda p: base64.b64encode(p.read_bytes()).decode()
        self.config_path = self.root / 'public-config.yaml'
        self.config_path.write_text(yaml.safe_dump({'apiVersion': 'v1', 'kind': 'Config',
            'clusters': [{'name': 'cluster', 'cluster': {'server': self.fixture.origin,
                         'certificate-authority-data': encoded(self.cert)}}],
            'contexts': [{'name': 'operator@cluster', 'context': {'cluster': 'cluster', 'user': 'operator'}}],
            'current-context': 'operator@cluster', 'users': [{'name': 'operator', 'user': {
                'client-certificate-data': encoded(self.cert), 'client-key-data': encoded(self.key)}}]}))
        self.config_path.chmod(0o600)
        self.options = m.reader.credentials.OperatorMTLSOptions(str(self.config_path))
        self.runtime = self.root / 'runtime'
        (self.runtime / 'bin').mkdir(parents=True)
        binary = self.runtime / 'bin/kubectl'
        binary.write_text('PUBLIC NONEXECUTED PLACEHOLDER\n'); binary.chmod(0o755)
        self.patch(m.reader, 'RUNTIME', self.runtime)
        self.patch(m.reader, 'spawn', self.spawn)
        self.patch(m.watch.TLSAPI, 'list_page', self.list_page)
        self.patch(m.watch.TLSAPI, 'open_watch', lambda *_: (self.response, self.response))
        start = m.watch.Collector.start
        def remember(collector):
            self.collector = collector
            return start(collector)
        self.patch(m.watch.Collector, 'start', remember)
        self.database = self.root / 'public.db'
        framing.databases.database(self.database)
        self.frames = self.root / 'public.frames'
        self.frames.write_bytes(framing.frame(self.database.read_bytes()))
        self.node_program = self.root / 'public-reader-program.txt'
        self.node_program.write_bytes(m.data.archive.NODE_READER.encode())
        self.age_identity = self.root / 'disposable-age'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(self.age_identity)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        self.age = pathlib.Path.home() / '.local/share/branconet-migration/bin/age'
        self.original = self.root / 'original.age'
        with self.original.open('wb') as out:
            subprocess.run([str(self.age), '-R', str(self.age_identity) + '.pub'], input=self.frames.read_bytes(),
                stdout=out, stderr=subprocess.DEVNULL, check=True, timeout=5)
        self.original.chmod(0o600)
        self.record['sqlite_archive']['ciphertext_sha256'] = hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.checkpoint = self.root / 'checkpoint.json'
        self.checkpoint.write_text(json.dumps(self.record)); self.checkpoint.chmod(0o600)
        self.checkpoint_sha = hashlib.sha256(self.checkpoint.read_bytes()).hexdigest()
        self.runs = self.root / 'runs'; self.runs.mkdir(mode=0o700)
        self.run = self.runs / RUN
        self.proof = {'holder_image': e['holder_image'], 'source_commit': 'a' * 40,
            'config_image_id': 'sha256:' + 'b' * 64, 'node_names': ['node-fixture', 'other-node', 'third-node'],
            'protected_claim_names': ['bortus-data', NAME], 'qualification_receipt_sha256': 'c' * 64,
            'admission_receipt_sha256': 'd' * 64, 'current_validation': True}
        self.qualifications = 0
        self.send_initial = self.send_completion = True
        self.suppress_watch = self.drop_create = self.spec_drift = self.keep_holder = False

    def patch(self, obj, name, value):
        patch = mock.patch.object(obj, name, value); patch.start(); self.patches.append(patch)

    def object(self, resource, obj):
        obj = copy.deepcopy(obj)
        _, version, kind, ns = m.reader.metadata.RESOURCES[resource]
        obj.update(apiVersion=version, kind=kind)
        if ns: obj['metadata']['namespace'] = ns
        else: obj['metadata'].pop('namespace', None)
        return obj

    def page(self, resource, items):
        _, version, kind, _ = m.reader.metadata.RESOURCES[resource]
        return {'apiVersion': version, 'kind': kind + 'List',
                'metadata': {'resourceVersion': 'opaque-list-' + resource, 'continue': ''},
                'items': [self.object(resource, obj) for obj in items]}

    def list_page(self, *_):
        volume = self.object('volume', self.resources['volumes.longhorn.io'])
        return {'apiVersion': m.health.API, 'kind': 'VolumeList',
                'metadata': {'resourceVersion': 'pre-create-rv', 'continue': ''}, 'items': [volume]}, 1024

    def respond(self, reply):
        method, path, body, _ = self.requests[-1]
        if method == 'POST':
            if self.drop_create: raise OSError('PUBLIC_PRIVATE_SENTINEL')
            resource = {'StorageClass': 'storageclass', 'PersistentVolumeClaim': 'claim', 'Pod': 'pod'}[body['kind']]
            created = copy.deepcopy(body)
            n = {'storageclass': 99, 'claim': 4, 'pod': 8}[resource]
            created['metadata'].update(uid=transport.tls.UID(n), resourceVersion='created-' + resource)
            if resource == 'claim':
                created['spec']['volumeName'] = 'pv'; created['status'] = {'phase': 'Bound'}
                if self.send_initial:
                    first = copy.deepcopy(self.objects['volume'])
                    first['metadata']['resourceVersion'] = 'z-initial'
                    first['status']['restoreRequired'] = True
                    self.response.send(first)
                if self.send_completion: self.response.send(self.objects['volume'])
            if resource == 'pod': created['status'] = copy.deepcopy(self.objects['pods']['items'][0]['status'])
            self.resources[resource + '-target'] = created
            return created
        if method == 'DELETE':
            if not self.keep_holder: self.resources.pop('pod-target', None)
            return reply
        plain = path.split('?', 1)[0]
        for resource, (base, _, _, _) in m.reader.metadata.RESOURCES.items():
            if plain == base:
                items = {'pv': [self.resources['pv']] + ([self.objects['pv']] if 'claim-target' in self.resources else []),
                    'pod': self.resources['pods']['items'] + ([self.resources['pod-target']] if 'pod-target' in self.resources else []),
                    'claim': [self.resources['pvc']] + ([self.resources['claim-target']] if 'claim-target' in self.resources else []),
                    'storageclass': [self.resources['storageclass']] + ([self.resources['storageclass-target']] if 'storageclass-target' in self.resources else []),
                    'engine': self.objects['engines']['items'], 'replica': self.objects['replicas']['items']}[resource]
                return self.page(resource, items)
            if plain.startswith(base + '/'):
                name = plain[len(base) + 1:]
                if name == NAME:
                    result = self.resources[resource + '-target']
                    if self.spec_drift and resource == 'storageclass':
                        result = dict(result, reclaimPolicy='Delete')
                    return self.object(resource, result)
                if resource == 'pv' and name == 'pv': return self.object(resource, self.objects['pv'])
                if resource == 'volume' and name == 'volume': return self.object(resource, self.objects['volume'])
                if resource == 'snapshot': return self.object(resource, self.owned[name])
                if resource == 'backup': return self.object(resource, self.owned[name])
                aliases = {'claim': 'pvc', 'volume': 'volumes.longhorn.io', 'backuptarget': 'backuptargets.longhorn.io'}
                return self.object(resource, self.resources[aliases.get(resource, resource)])
        raise AssertionError('Unknown public fixture path')

    def spawn(self, args, **kwargs):
        self.commands.append(args)
        fd = kwargs['pass_fds'][0]
        program = ('import os,pathlib,sys; os.close(int(sys.argv[1])); '
            'assert sys.stdin.buffer.read()==pathlib.Path(sys.argv[2]).read_bytes(); '
            'sys.stdout.buffer.write(pathlib.Path(sys.argv[3]).read_bytes())')
        child = subprocess.Popen([sys.executable, '-B', '-c', program, str(fd),
            str(self.node_program), str(self.frames)], **kwargs)
        self.children.append(child)
        return child

    def qualify(self, *_):
        self.qualifications += 1
        return copy.deepcopy(self.proof)

    def execute(self, seconds=30):
        return m.restore(self.run, self.checkpoint, self.checkpoint_sha, self.original,
            self.expected['holder_image'], 'other-node', str(self.config_path), self.options, self.qualify,
            age=self.age, recipient_file=str(self.age_identity) + '.pub', identity_file=self.age_identity,
            deadline=time.monotonic() + seconds)

    def cleanup(self):
        if hasattr(self, 'response'): self.response.close()
        for child in self.children:
            m.data.archive.stop_owned(child)
            for pipe in (child.stdin, child.stdout, child.stderr):
                if pipe and not pipe.closed: pipe.close()
            self.assertIsNotNone(child.poll())
        if hasattr(self, 'fixture'): self.fixture.close()
        if hasattr(self, 'collector') and self.collector.thread:
            self.collector.thread.join(2)
            self.assertFalse(self.collector.thread.is_alive())
            self.assertIsNone(self.collector.journal.fd)
        for patch in reversed(self.patches): patch.stop()
        self.assertEqual(self.tmpfs_before, set(pathlib.Path('/dev/shm').glob('bortus-sqlite-*')))
        self.root_temp.cleanup()

    def refused(self, code=None, **kwargs):
        try: self.execute(**kwargs)
        except m.RestoreRefused as error:
            self.assertIsNone(error.__context__); self.assertIsNone(error.__cause__)
            if code: self.assertEqual(error.code, code)
            tb = error.__traceback__
            while tb:
                if tb.tb_frame.f_code.co_filename.endswith('bortus-independent-restore.py'):
                    self.assertNotIn('PUBLIC_PRIVATE_SENTINEL', repr(tb.tb_frame.f_locals))
                tb = tb.tb_next
            return error.code
        self.fail('Expected coordinator refusal')

    def test_full_tls_watch_reader_age_sqlite_and_absence_without_acceptance(self):
        result = self.execute()
        self.assertTrue(result.coordinator_completed)
        self.assertFalse(result.overall_live_restore_acceptance or result.image_runtime_admission_acceptance)
        self.assertEqual(len(self.children), 1)
        self.assertGreaterEqual(self.qualifications, 6)
        self.assertTrue(self.response.closed)
        self.assertFalse((self.run / 'active.lock').exists())
        state = json.loads((self.run / 'restore-receipt.json').read_text())
        self.assertEqual(state['state'], 'completed')
        self.assertTrue(state['whole_rows_equal'] and state['holder_absent'] and state['resources_closed'])
        self.assertFalse(state['overall_live_restore_acceptance'])
        self.assertEqual([r[0] for r in self.requests if r[0] != 'GET'], ['POST', 'POST', 'POST', 'DELETE'])
        self.assertEqual(self.commands[0][-10:], ['-n', 'bortus', 'exec', NAME, '-c', 'holder', '-i', '--', 'node', '-'])

    def test_bare_qualification_and_wrong_protected_claims_refuse_before_mutation(self):
        self.proof = True
        self.refused('qualification')
        self.assertFalse(any(r[0] != 'GET' for r in self.requests))

    def test_admitted_drift_retains_uncertain_intent_and_never_creates_claim(self):
        self.spec_drift = True
        self.refused('create')
        journal = json.loads((self.run / 'journal.json').read_text())
        self.assertEqual(journal['operations']['storageclass_create']['state'], 'uncertain')
        self.assertNotIn('claim_create', journal['operations'])
        self.assertFalse(any(r[0] == 'DELETE' for r in self.requests))

    def test_initial_false_only_cannot_seal_or_create_holder(self):
        self.send_initial = False
        self.refused('binding')
        journal = json.loads((self.run / 'journal.json').read_text())
        self.assertEqual(journal['operations']['claim_create']['state'], 'confirmed')
        self.assertNotIn('holder_create', journal['operations'])
        self.assertFalse(any(r[0] == 'DELETE' for r in self.requests))

    def test_completed_run_refuses_replay_without_second_mutation(self):
        self.execute()
        before = [r for r in self.requests if r[0] != 'GET']
        # Retained SC/PVC collision is refused by fresh preparation even before
        # the exclusive run-directory collision check; no second mutation occurs.
        self.refused('source')
        self.assertEqual(before, [r for r in self.requests if r[0] != 'GET'])

    def test_closed_qualification_wrong_claims_and_boolean_lookalike(self):
        self.proof['protected_claim_names'] = [NAME]
        self.refused('qualification')
        self.proof['protected_claim_names'] = ['bortus-data', NAME]
        self.proof['current_validation'] = 1
        self.refused('qualification')
        self.assertFalse(any(r[0] != 'GET' for r in self.requests))

    def test_qualification_change_stops_next_mutation(self):
        original = self.qualify
        def changed(*args):
            proof = original(*args)
            if self.qualifications >= 3: proof['admission_receipt_sha256'] = 'e' * 64
            return proof
        self.qualify = changed
        self.refused('qualification')
        self.assertEqual([r[0] for r in self.requests if r[0] != 'GET'], ['POST'])
        journal = json.loads((self.run / 'journal.json').read_text())
        self.assertEqual(journal['operations']['storageclass_create']['state'], 'confirmed')
        self.assertNotIn('claim_create', journal['operations'])

    def test_watch_error_never_permits_mutation_or_cleanup_mutation(self):
        original = self.qualify
        def fail_watch(*args):
            proof = original(*args)
            if self.qualifications == 2:
                self.response.frames.put(json.dumps({'type': 'ERROR',
                    'object': {'kind': 'Status', 'message': 'PUBLIC_PRIVATE_SENTINEL'}}).encode() + b'\n')
                until = time.monotonic() + 2
                while self.collector.state['failure'] is None and time.monotonic() < until: time.sleep(.005)
                self.assertEqual(self.collector.state['failure'], 'watch_error')
            return proof
        self.qualify = fail_watch
        self.refused('create')
        self.assertFalse(any(r[0] != 'GET' for r in self.requests))

    def test_existing_run_cannot_be_overwritten_or_adopted(self):
        self.run.mkdir(mode=0o700)
        marker = self.run / 'public-marker'; marker.write_text('original')
        self.refused('ownership')
        self.assertEqual(marker.read_text(), 'original')
        self.assertFalse(any(r[0] != 'GET' for r in self.requests))

    def test_pending_intent_file_flush_failure_prevents_first_mutation(self):
        original = m.os.fsync
        def fail_intent(fd):
            if pathlib.Path('/proc/self/fd/' + str(fd)).resolve().name == 'restore-intent.json':
                raise OSError('PUBLIC_PRIVATE_SENTINEL')
            return original(fd)
        self.patch(m.os, 'fsync', fail_intent)
        self.refused('ownership')
        self.assertFalse(any(r[0] != 'GET' for r in self.requests))
        self.assertEqual(json.loads((self.run / 'journal.json').read_text())['operations'], {})

    def test_source_cleanup_failure_cannot_grant_acceptance(self):
        original = m.source.SourceFence.close
        def fail_close(fence):
            original(fence)
            raise OSError('PUBLIC_PRIVATE_SENTINEL')
        self.patch(m.source.SourceFence, 'close', fail_close)
        self.proof = True
        self.refused('cleanup')
        self.assertFalse(any(r[0] != 'GET' for r in self.requests))

    def test_actual_row_mismatch_cleans_both_tmpfs_and_retains_holder(self):
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE added_public_fixture(n INTEGER)')
            db.execute('INSERT INTO added_public_fixture VALUES(7)')
        self.frames.write_bytes(framing.frame(self.database.read_bytes()))
        self.refused('data')
        self.assertFalse(any(r[0] == 'DELETE' for r in self.requests))
        self.assertIn('pod-target', self.resources)
        state = json.loads((self.run / 'data.json').read_text())
        self.assertEqual(state['state'], 'refused')
        self.assertEqual(state['tmpfs_cleanup'], [True, True])
        self.assertFalse(state['recovery_rows_equal'])
