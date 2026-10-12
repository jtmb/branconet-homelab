"""Public age fixtures and owned local NAS child; SSH/sudo/live reads are mocked."""
import base64
import copy
import importlib.util
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


HERE = pathlib.Path(__file__).parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load('recovery_config_tests', HERE.parent / 'capture-kubernetes-recovery-config.py')
# Public source-location override supports source-bound qualification of a pending
# transport handoff; it never changes product lookup or loads private credentials.
e = load('recovery_config_test_checkpoint', pathlib.Path(os.environ.get(
    'BORTUS_TEST_CHECKPOINT_SOURCE', str(HERE.parent / 'backup-etcd.py'))))


class Client:
    def __init__(self, root, files):
        self.deadline = time.monotonic() + 20
        self.children = e.q.Children(self.deadline)
        self.jobs = []
        self.files = files
        self.reads = 0
        self.drift = False
        self.lost_reply = False
        self.nas_mode = 0o600
        self.cifs = False
        self.root = root

    def check(self):
        e.left(self.deadline)

    def remote(self, request):
        self.check()
        assert request == {'mode': 'keys', 'run_id': '123456789abc',
                           'paths': list(m.FILES)}
        self.reads += 1
        files = copy.deepcopy(self.files)
        if self.drift and self.reads > 1:
            files[m.FILES[0]] = base64.b64encode(b'PUBLIC DRIFT').decode()
        return files

    def spawn(self, args, **kwargs):
        self.check()
        if args[:len(e.SSH)] == e.SSH:
            command = shlex.split(args[-1])
            assert command[:2] == ['python3', '-c']
            expected = m.nas_program(e)
            assert command[2] == expected
            code = expected.replace(repr(e.q.NAS_ROOT), repr(str(self.root / 'nas')))
            if self.cifs:
                code = code.replace('try:\n mount_before=mount_identity()',
                    "def mount_identity():return ('/mnt/container-backups',('PUBLIC MOUNT ID',),('cifs','PUBLIC SOURCE','rw'))\ntry:\n mount_before=mount_identity()")
            if self.nas_mode != 0o600:
                literal = ' digest=hashlib.sha256();left=info[\'bytes\']'
                assert code.count(literal) == 1
                code = code.replace(literal,
                    ' os.fchmod(target,' + str(self.nas_mode) + ')\n' + literal)
            if self.lost_reply:
                code = code.replace("print(json.dumps({'bytes':", "sys.exit(1); print(json.dumps({'bytes':")
            args = [sys.executable, '-B', '-c', code]
        child = subprocess.Popen(args, stdin=kwargs.pop('stdin', subprocess.PIPE),
                                 stdout=kwargs.pop('stdout', subprocess.PIPE),
                                 stderr=subprocess.DEVNULL, start_new_session=True,
                                 **kwargs)
        self.jobs.append(child)
        return child

    def close(self):
        for child in self.jobs:
            self.children(child)
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream and not stream.closed:
                    stream.close()
            assert child.poll() is not None


class Tests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='public-config-capture-',
                                                   dir=pathlib.Path.home())
        self.root = pathlib.Path(self.folder.name)
        self.root.chmod(0o700)
        self.parent = self.root / 'config-captures'
        self.parent.mkdir(mode=0o700)
        self.nas = self.root / 'nas'
        self.nas.mkdir(mode=0o700)
        self.runtime = self.root / 'runtime'
        (self.runtime / 'bin').mkdir(parents=True, mode=0o700)
        age = pathlib.Path.home() / '.local/share/branconet-migration/bin/age'
        shutil.copyfile(age, self.runtime / 'bin/age')
        (self.runtime / 'bin/age').chmod(0o700)
        keys = self.root / 'keys'
        keys.mkdir(mode=0o700)
        self.key = keys / 'identity'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(self.key)],
                       check=True, timeout=5, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        self.pub = pathlib.Path(str(self.key) + '.pub')
        self.pub.chmod(0o600)
        self.files = {name: base64.b64encode(('PUBLIC FIXTURE ' + name).encode()).decode()
                      for name in m.FILES}
        encryption = {'kind': 'EncryptionConfiguration', 'resources': [{
            'resources': ['secrets'], 'providers': [{'aescbc': {'keys': [{
                'name': 'public', 'secret': base64.b64encode(b'P' * 32).decode()
            }]}}]
        }]}
        self.files['/etc/kubernetes/encryption-config.json'] = base64.b64encode(
            json.dumps(encryption).encode()).decode()
        self.files['/etc/kubernetes/longhorn-crypto-key'] = base64.b64encode(b'L' * 32).decode()
        self.client = Client(self.root, self.files)
        self.patch = mock.patch.object(e, 'RUNTIME', self.runtime)
        self.patch.start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.client.close()
        self.patch.stop()
        self.folder.cleanup()

    def capture(self):
        return m.capture(client=self.client, checkpoint=e, parent=self.parent,
                         run_id='123456789abc', recipient_file=self.pub,
                         identity_file=self.key)

    def record(self):
        return json.loads((self.parent / 'etcd-123456789abc/record.json').read_text())

    def test_authenticated_complete_capture_and_ciphertext_only_nas(self):
        result = self.capture()
        self.assertEqual(32, result['file_count'])
        cipher = pathlib.Path(result['path'])
        remote = self.nas / 'config-123456789abc.age'
        self.assertEqual(cipher.read_bytes(), remote.read_bytes())
        self.assertNotIn(b'PUBLIC FIXTURE', remote.read_bytes())
        for path in (cipher, remote):
            self.assertEqual(0o600, path.stat().st_mode & 0o777)
        plain = subprocess.run([str(self.runtime / 'bin/age'), '-d', '-i', str(self.key),
                                str(cipher)], capture_output=True, check=True, timeout=5).stdout
        self.assertEqual({'files': self.files}, json.loads(plain))
        record = self.record()
        self.assertEqual('completed', record['phase'])
        self.assertFalse(record['actual_production_checkpoint_accepted'])
        self.assertTrue(record['confirmation_requires_launcher_terminal0'])
        self.assertFalse(record['continuous_file_watch'])
        self.assertFalse(record['api_decryption_restored'])
        self.assertFalse(record['longhorn_restore_proved'])
        self.assertNotIn('PUBLIC FIXTURE', json.dumps(record))
        self.assertEqual(2, self.client.reads)

    def test_second_capture_refuses_existing_owner_before_read(self):
        self.capture()
        before = (self.parent / 'etcd-123456789abc/record.json').read_bytes()
        reads = self.client.reads
        with self.assertRaises(m.Refused):
            self.capture()
        self.assertEqual(reads, self.client.reads)
        self.assertEqual(before, (self.parent / 'etcd-123456789abc/record.json').read_bytes())

    def test_missing_file_refuses_before_encryption(self):
        self.client.files.pop(m.FILES[0])
        with self.assertRaises(m.Refused):
            self.capture()
        self.assertEqual([], self.client.jobs)
        self.assertEqual([], list(self.nas.iterdir()))
        self.assertEqual('refused', self.record()['phase'])

    def test_noncanonical_base64_refuses(self):
        self.client.files[m.FILES[0]] = 'cHVibGlj\n'
        with self.assertRaises(m.Refused):
            self.capture()
        self.assertEqual([], self.client.jobs)

    def test_drift_retains_ciphers_without_acceptance(self):
        self.client.drift = True
        with self.assertRaises(m.Refused) as error:
            self.capture()
        self.assertEqual('drift', error.exception.code)
        self.assertTrue((self.nas / 'config-123456789abc.age').exists())
        self.assertEqual('refused', self.record()['phase'])

    def test_lost_nas_reply_retains_output_without_retry(self):
        self.client.lost_reply = True
        with self.assertRaises(m.Refused):
            self.capture()
        self.assertTrue((self.nas / 'config-123456789abc.age').exists())
        self.assertEqual(1, self.client.reads)
        self.assertEqual('pending', self.record()['operations']['publish_configuration']['state'])
        self.assertEqual('refused', self.record()['phase'])

    def test_authenticated_mismatch_refuses_before_nas(self):
        with mock.patch.object(e, 'read_age', return_value=b'PUBLIC WRONG BYTES'):
            with self.assertRaises(m.Refused):
                self.capture()
        self.assertEqual([], list(self.nas.iterdir()))

    def test_expired_lease_does_not_create_owner(self):
        self.client.deadline = time.monotonic() - 1
        with self.assertRaises(m.Refused):
            self.capture()
        self.assertEqual([], list(self.parent.iterdir()))

    def test_mount_forced0755_cipher_only_on_exact_cifs(self):
        self.client.nas_mode = 0o755
        self.client.cifs = True
        result = self.capture()
        self.assertEqual(0o755, result['nas_cipher_mode'])
        self.assertTrue(result['nas_cifs_mount'])
        self.assertEqual(0o600, pathlib.Path(result['path']).stat().st_mode & 0o777)
        self.assertEqual(pathlib.Path(result['path']).read_bytes(),
                         (self.nas / 'config-123456789abc.age').read_bytes())

    def test0755_cipher_on_non_cifs_refuses(self):
        self.client.nas_mode = 0o755
        with self.assertRaises(m.Refused):
            self.capture()
        self.assertEqual('pending', self.record()['operations']['publish_configuration']['state'])

    def test_world_writable_cipher_on_cifs_refuses(self):
        self.client.nas_mode = 0o777
        self.client.cifs = True
        with self.assertRaises(m.Refused):
            self.capture()
        self.assertEqual('pending', self.record()['operations']['publish_configuration']['state'])

    def test_writer_factory_etcd_prefix_preserves_shared_default(self):
        before = e.q.NAS_PROGRAM
        default = m.nas_program(e)
        etcd = m.nas_program(e, prefix='etcd')
        self.assertEqual(default.replace('config-', 'etcd-'), etcd)
        self.assertEqual(before, e.q.NAS_PROGRAM)

    def test_writer_factory_rejects_unknown_or_untyped_prefix(self):
        for prefix in ('bortus', '../config', '', None, 1, True):
            with self.subTest(prefix=prefix), self.assertRaises(m.Refused):
                m.nas_program(e, prefix=prefix)

    def test_completion_directory_fsync_failure_refuses_visible_success(self):
        original_save = e.Ledger.save
        original_fsync = os.fsync
        faulted = False

        def save(ledger):
            def fsync(fd):
                nonlocal faulted
                if ledger.r.get('phase') == 'completed' and fd == ledger.fd and not faulted:
                    faulted = True
                    raise OSError('PUBLIC DIRECTORY FLUSH FAULT')
                return original_fsync(fd)
            with mock.patch.object(e.os, 'fsync', fsync):
                return original_save(ledger)

        with mock.patch.object(e.Ledger, 'save', save):
            with self.assertRaises(m.Refused):
                self.capture()
        self.assertTrue(faulted)
        self.assertEqual('refused', self.record()['phase'])
        self.assertFalse(self.record()['actual_production_checkpoint_accepted'])


if __name__ == '__main__':
    unittest.main()
