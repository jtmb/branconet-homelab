"""Focused rejection and interrupted-transfer checks; no network or runtime writes."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock


def load(name, filename):
    path = Path(__file__).resolve().parents[1] / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


receiver = load('qualified_receiver_test', 'bortus-qualified-preload-node.py')
coordinator = load('qualified_coordinator_test', 'preload-qualified-bortus-image.py')
PARENT = Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/test-temp')


class QualifiedPreloadTests(unittest.TestCase):
    def test_bad_archive_closes_memory_file_before_runtime(self):
        before = len(list(Path('/proc/self/fd').iterdir()))
        with mock.patch.object(receiver, 'metadata') as runtime:
            with self.assertRaises(RuntimeError):
                receiver.receive_archive(io.BytesIO(b'wrong image'))
            runtime.assert_not_called()
        self.assertEqual(before, len(list(Path('/proc/self/fd').iterdir())))

    def test_reference_with_wrong_manifest_is_rejected(self):
        with mock.patch.object(receiver, 'image_digest', return_value='sha256:' + '0' * 64), \
             mock.patch.object(receiver, 'content') as content:
            with self.assertRaises(RuntimeError):
                receiver.verify_runtime()
            content.assert_not_called()

    def test_wrong_config_is_rejected_before_layer_reads(self):
        manifest = {'schemaVersion': 2, 'config': {'digest': 'sha256:' + '0' * 64},
                    'layers': [{}] * 9}
        with mock.patch.object(receiver, 'image_digest', return_value=receiver.MANIFEST), \
             mock.patch.object(receiver, 'content', return_value=manifest) as content:
            with self.assertRaises(RuntimeError):
                receiver.verify_runtime()
            self.assertEqual(content.call_count, 1)

    def test_uncertain_second_node_prevents_third_dispatch(self):
        with tempfile.TemporaryDirectory(prefix='preload-test-', dir=PARENT) as directory:
            root = Path(directory)
            archive = root / 'fixture.oci'
            archive.write_bytes(b'public test fixture')
            stdin = types.SimpleNamespace(buffer=io.BytesIO(b'{"sudo_password":"public-test-value"}'))
            with mock.patch.object(coordinator, 'ROOT', root), \
                 mock.patch.object(coordinator, 'RECEIPT', root / 'preload.json'), \
                 mock.patch.object(coordinator, 'ARCHIVE', archive), \
                 mock.patch.object(coordinator, 'check', return_value=('public',)), \
                 mock.patch.object(coordinator, 'transfer', side_effect=[{'checked': True}, RuntimeError('lost reply')]) as transfer, \
                 mock.patch.object(coordinator.sys, 'argv', ['preload', '--preload']), \
                 mock.patch.object(coordinator.sys, 'stdin', stdin):
                with self.assertRaises(RuntimeError):
                    coordinator.main()
            record = json.loads((root / 'preload.json').read_text())
            self.assertEqual(transfer.call_count, 2)
            self.assertEqual([row['state'] for row in record['nodes']],
                             ['verified', 'uncertain-inspect-before-retry'])
            self.assertEqual(record['state'], 'stopped')
            self.assertNotIn('public-test-value', (root / 'preload.json').read_text())

    def test_image_without_ready_unpacked_state_is_rejected(self):
        manifest = {'schemaVersion': 2, 'config': {'digest': receiver.CONFIG}, 'layers': [{}] * 9}
        config = {'os': 'linux', 'architecture': 'amd64',
                  'config': {'Labels': {'org.opencontainers.image.revision': receiver.SOURCE}}}
        with mock.patch.object(receiver, 'image_digest', return_value=receiver.MANIFEST), \
             mock.patch.object(receiver, 'content', side_effect=[manifest, config]), \
             mock.patch.object(receiver, 'metadata', return_value=b''), \
             mock.patch.object(receiver.subprocess, 'Popen') as process:
            with self.assertRaises(RuntimeError):
                receiver.verify_runtime()
            process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
