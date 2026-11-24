"""Exercise the existing H mount boundary without API calls or permission changes."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('restore_h_boundary',
    Path(__file__).resolve().parents[1] / 'bortus-restore-source.py')
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)
PARENT = source.H_STORE / 'bortus-operator-recovery/test-temp'
IMAGE = 'docker.io/jtmb92/bortus@sha256:' + 'a' * 64


class HBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='source-h-boundary-', dir=PARENT)
        self.path = Path(self.folder.name) / 'checkpoint.json'
        self.path.write_bytes(b'{"public_fixture":true}')
        self.path.chmod(0o600)
        self.digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.api = source.metadata.MetadataAPI(lambda: None)
        self.fence = None

    def tearDown(self):
        if self.fence:
            self.fence.close()
        os.chmod(self.folder.name, 0o700)
        self.folder.cleanup()

    def open(self):
        self.fence = source.SourceFence(self.path, self.digest, IMAGE, 'node02', self.api)
        return self.fence

    def test_actual_existing_mount_and_private_journal_are_accepted(self):
        self.assertEqual(self.open()._read(), {'public_fixture': True})
        self.assertEqual(self.fence.h_mount_identity[0], source.H_STORE.stat().st_dev)

    def test_writable_private_directory_still_refuses(self):
        fence = self.open()
        os.chmod(self.folder.name, 0o777)
        with self.assertRaises(source.SourceRefused):
            fence._read()

    def test_wrong_filesystem_or_uuid_still_refuses(self):
        for filesystem, uuid in [('9p', source.H_UUID), ('ext4', 'foreign-volume')]:
            reply = {'filesystems': [{'target': str(source.H_STORE), 'fstype': filesystem, 'uuid': uuid}]}
            result = types.SimpleNamespace(returncode=0, stdout=json.dumps(reply).encode())
            with mock.patch.object(source.subprocess, 'run', return_value=result):
                with self.assertRaises(source.SourceRefused):
                    source.verified_h_boundary()

    def test_same_bytes_in_replacement_inode_still_refuse(self):
        fence = self.open()
        replacement = self.path.with_suffix('.replacement')
        replacement.write_bytes(self.path.read_bytes())
        replacement.chmod(0o600)
        replacement.replace(self.path)
        with self.assertRaises(source.SourceRefused):
            fence._read()


if __name__ == '__main__':
    unittest.main()
