"""Public loopback TLS/config and actual controlled Python children; no kubectl or Node."""
import base64
import copy
import importlib.util
import json
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
import test_bortus_restore_mutations as fixtures

HERE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location('restore_reader_tests', HERE.parent / 'bortus-restore-reader.py')
m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m)


@unittest.skipUnless(os.name == 'posix' and hasattr(os, 'memfd_create'), 'Real POSIX/memfd required')
class ReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixtures.MutationTests.setUpClass()

    @classmethod
    def tearDownClass(cls): fixtures.MutationTests.tearDownClass()

    def setUp(self):
        self.children, self.patches = [], []
        self.base = None
        self.folder = tempfile.TemporaryDirectory(prefix='bortus-reader-public-', dir=pathlib.Path.home())
        self.addCleanup(self.cleanup)
        self.root = pathlib.Path(self.folder.name)
        self.root.chmod(0o755)
        patch = mock.patch.object(fixtures, 'm', m.mutations); patch.start(); self.patches.append(patch)
        self.base = fixtures.MutationTests(methodName='test_exact_delete_fresh_get_preconditions_and_submitted_only')
        self.base.setUp(); self.base.prepare_delete()
        self.path = self.root / 'fixture.yaml'
        encoded = lambda p: base64.b64encode(p.read_bytes()).decode()
        self.config = {'apiVersion': 'v1', 'kind': 'Config',
            'clusters': [{'name': 'public-cluster', 'cluster': {'server': self.base.fixture.origin,
                         'certificate-authority-data': encoded(self.base.cert)}}],
            'contexts': [{'name': 'operator@public-cluster',
                          'context': {'cluster': 'public-cluster', 'user': 'operator'}}],
            'current-context': 'operator@public-cluster',
            'users': [{'name': 'operator', 'user': {'client-certificate-data': encoded(self.base.cert),
                                                 'client-key-data': encoded(self.base.key)}}]}
        self.save()
        self.options = m.credentials.OperatorMTLSOptions(str(self.path))
        patch = mock.patch.object(m.credentials, 'APPROVED_ORIGIN', self.base.fixture.origin)
        patch.start(); self.patches.append(patch)
        self.runtime = self.root / 'runtime'
        (self.runtime / 'bin').mkdir(parents=True)
        self.binary = self.runtime / 'bin/kubectl'
        self.binary.write_text('PUBLIC NONEXECUTED PLACEHOLDER\n'); self.binary.chmod(0o755)
        patch = mock.patch.object(m, 'RUNTIME', self.runtime); patch.start(); self.patches.append(patch)
        pod = self.base.fixture.get_body
        pod['status'] = {'phase': 'Running', 'conditions': [{'type': 'Ready', 'status': 'True'}],
            'containerStatuses': [{'name': 'holder', 'ready': True, 'state': {'running': {}},
                                  'image': pod['spec']['containers'][0]['image'], 'restartCount': 0}]}
        self.holder = m.data.health.identity(pod, 'bortus')
        self.launcher = m.ReaderLauncher(self.base.api, str(self.path), self.options)
        self.commands = []
        patch = mock.patch.object(m, 'spawn', self.spawn); patch.start(); self.patches.append(patch)
        self.fd_before = set(os.listdir('/proc/self/fd'))

    def save(self):
        with self.path.open('wb') as out: out.write(yaml.safe_dump(self.config).encode())
        self.path.chmod(0o600)

    def spawn(self, args, **kwargs):
        self.commands.append((args, dict(kwargs)))
        fd = kwargs['pass_fds'][0]
        child = subprocess.Popen([sys.executable, '-B', '-c',
            'import os,sys; data=os.read(int(sys.argv[1]),65537); '
            'assert b"client-key-data" in data; os.close(int(sys.argv[1])); '
            'sys.stdout.buffer.write(sys.stdin.buffer.read())', str(fd)], **kwargs)
        self.children.append(child)
        return child

    def cleanup(self):
        for child in self.children:
            m.data.archive.stop_owned(child)
            for pipe in (child.stdin, child.stdout, child.stderr):
                if pipe is not None and not pipe.closed: pipe.close()
            self.assertIsNotNone(child.poll())
        if hasattr(self, 'fd_before'):
            until = time.monotonic() + 2
            while self.fd_before != set(os.listdir('/proc/self/fd')) and time.monotonic() < until:
                time.sleep(.005)
            self.assertEqual(self.fd_before, set(os.listdir('/proc/self/fd')))
        if self.base: self.base.doCleanups()
        for patch in reversed(self.patches): patch.stop()
        self.folder.cleanup()

    def launch(self, seconds=3, holder=None):
        return self.launcher.launch_reader(holder or self.holder, time.monotonic() + seconds)

    def refused(self, **kwargs):
        with self.assertRaises(m.ReaderRefused) as caught: self.launch(**kwargs)
        self.assertIsNone(caught.exception.__context__); self.assertIsNone(caught.exception.__cause__)
        self.assertNotIn('PRIVATE_SYNTHETIC', str(caught.exception))
        frame = caught.exception.__traceback__
        while frame:
            self.assertNotIn('raw', frame.tb_frame.f_locals)
            self.assertNotIn('pod', frame.tb_frame.f_locals)
            self.assertNotIn('context', frame.tb_frame.f_locals)
            frame = frame.tb_next
        return caught.exception.code

    def test_real_python_child_exact_fixed_command_fd_and_program_only_stdin(self):
        child = self.launch()
        self.assertIs(type(child), subprocess.Popen)
        args, kwargs = self.commands[0]
        self.assertEqual(args[0], str(self.binary))
        self.assertEqual(args[-10:], ['-n', 'bortus', 'exec', self.holder.name, '-c', 'holder', '-i', '--', 'node', '-'])
        self.assertRegex(args[2], r'^/proc/self/fd/[0-9]+$')
        self.assertTrue(kwargs['start_new_session']); self.assertTrue(kwargs['close_fds'])
        self.assertEqual(kwargs['stderr'], subprocess.DEVNULL)
        self.assertEqual(set(kwargs['env']), {'HOME', 'PATH', 'LANG'})
        self.assertNotIn(m.data.archive.NODE_READER, ' '.join(args))
        with self.assertRaises(OSError): os.fstat(kwargs['pass_fds'][0])
        program = m.data.archive.NODE_READER.encode()
        output, errors = child.communicate(program, timeout=3)
        self.assertEqual(output, program); self.assertIsNone(errors); self.assertEqual(child.returncode, 0)

    def test_actual_mtls_get_with_owned_0755_parent(self):
        context = self.base.fixture.server.socket.context
        context.load_verify_locations(cafile=str(self.base.cert)); context.verify_mode = ssl.CERT_REQUIRED
        child = self.launch(); child.communicate(b'PUBLIC', timeout=3)
        self.assertEqual(self.base.fixture.requests[0][0], 'GET')
        self.assertNotIn('secrets', self.base.fixture.requests[0][1])

    def test_supplied_uid_cannot_adopt_replacement(self):
        altered = self.holder._replace(uid=fixtures.tls.UID(88))
        self.refused(holder=altered); self.assertEqual(self.commands, [])

    def test_fresh_get_replaced_uid_refuses(self):
        self.base.fixture.get_body['metadata']['uid'] = fixtures.tls.UID(88)
        self.refused(); self.assertEqual(self.commands, [])

    def test_fresh_get_changed_rv_refuses(self):
        self.base.fixture.get_body['metadata']['resourceVersion'] = 'replacement-rv'
        self.refused(); self.assertEqual(self.commands, [])

    def test_deletion_refuses(self):
        self.base.fixture.get_body['metadata']['deletionTimestamp'] = 'now'
        self.refused(); self.assertEqual(self.commands, [])

    def test_image_drift_refuses(self):
        self.base.fixture.get_body['spec']['containers'][0]['image'] = 'public/image:mutable'
        self.refused(); self.assertEqual(self.commands, [])

    def test_node_drift_refuses(self):
        self.base.fixture.get_body['spec']['nodeName'] = 'foreign-node'
        self.refused(); self.assertEqual(self.commands, [])

    def test_readonly_drift_refuses(self):
        self.base.fixture.get_body['spec']['volumes'][0]['persistentVolumeClaim']['readOnly'] = False
        self.refused(); self.assertEqual(self.commands, [])

    def test_environment_or_owner_refuses(self):
        self.base.fixture.get_body['spec']['containers'][0]['env'] = [{'name': 'PRIVATE', 'value': 'PRIVATE_SYNTHETIC'}]
        self.refused(); self.assertEqual(self.commands, [])

    def test_ready_status_or_restart_refuses(self):
        self.base.fixture.get_body['status']['containerStatuses'][0]['restartCount'] = 1
        self.refused(); self.assertEqual(self.commands, [])

    def test_allowed_exact_api_defaults(self):
        pod = self.base.fixture.get_body
        pod['spec'].update(dnsPolicy='ClusterFirst', serviceAccountName='default', priority=0)
        pod['spec']['containers'][0]['terminationMessagePolicy'] = 'File'
        child = self.launch(); child.communicate(b'PUBLIC', timeout=3)

    def test_boolean_default_cannot_look_like_integer(self):
        self.base.fixture.get_body['spec']['priority'] = False
        self.refused(); self.assertEqual(self.commands, [])

    def test_expired_deadline_no_read_or_dispatch(self):
        self.refused(seconds=-1); self.assertEqual(self.commands, [])
        self.assertEqual(self.base.fixture.requests, [])

    def test_late_get_no_child_dispatch(self):
        self.base.fixture.delay = .1
        self.refused(seconds=.03); self.assertEqual(self.commands, [])

    def test_config_unknown_auth_plugin_refuses_before_get(self):
        self.config['users'][0]['user']['exec'] = {'command': 'PRIVATE_SYNTHETIC'}
        self.save(); self.refused(); self.assertEqual(self.commands, [])
        self.assertEqual(self.base.fixture.requests, [])

    def test_insecure_or_origin_changed_config_refuses(self):
        self.config['clusters'][0]['cluster']['insecure-skip-tls-verify'] = True
        self.save(); self.refused(); self.assertEqual(self.commands, [])

    def test_config_source_rotation_during_get_refuses(self):
        def request(method, body):
            replacement = self.path.with_suffix('.replacement')
            replacement.write_bytes(self.path.read_bytes()); replacement.chmod(0o600)
            os.replace(replacement, self.path)
        self.base.fixture.on_request = request
        self.refused(); self.assertEqual(self.commands, [])

    def test_options_source_path_drift_refuses(self):
        self.options.path = self.path.with_suffix('.foreign')
        self.refused(); self.assertEqual(self.commands, [])
        self.assertEqual(self.base.fixture.requests, [])

    def test_writable_parent_refuses(self):
        self.root.chmod(0o777)
        self.refused(); self.assertEqual(self.commands, [])

    def test_config_mode_and_symlink_refuse(self):
        self.path.chmod(0o644)
        self.refused(); self.assertEqual(self.commands, [])

    def test_binary_symlink_or_writable_refuses(self):
        self.binary.chmod(0o777)
        self.refused(); self.assertEqual(self.commands, [])

    def test_second_launch_refuses_no_replay(self):
        child = self.launch(); child.communicate(b'PUBLIC', timeout=3)
        self.assertEqual(self.refused(), 'no_replay')
        self.assertEqual(len(self.commands), 1)

    def test_failure_before_popen_has_fixed_private_boundary(self):
        def failed(*args, **kwargs): raise RuntimeError('PRIVATE_SYNTHETIC_LAUNCH')
        with mock.patch.object(m, 'spawn', failed): self.assertEqual(self.refused(), 'launch')
        self.assertEqual(self.children, [])

    def test_child_exit_before_return_closed(self):
        def early(args, **kwargs):
            child = subprocess.Popen([sys.executable, '-B', '-c', 'raise SystemExit(7)'], **kwargs)
            self.children.append(child); child.wait(timeout=3)
            return child
        with mock.patch.object(m, 'spawn', early): self.assertEqual(self.refused(), 'child_exit')
        self.assertTrue(self.children[0].stdin.closed); self.assertTrue(self.children[0].stdout.closed)

    def test_deadline_after_popen_stops_only_owned_child(self):
        real = self.spawn
        def late(args, **kwargs):
            child = real(args, **kwargs); time.sleep(.20); return child
        with mock.patch.object(m, 'spawn', late): self.refused(seconds=.15)
        self.assertEqual(len(self.children), 1)
        for child in self.children:
            self.assertIsNotNone(child.poll()); self.assertTrue(child.stdin.closed); self.assertTrue(child.stdout.closed)

    def test_watch_failure_after_spawn_stops_child(self):
        real = self.spawn
        def stopped(args, **kwargs):
            child = real(args, **kwargs)
            self.base.response.close()
            self.base.wait(lambda: self.base.collector.state['failure'] is not None)
            return child
        with mock.patch.object(m, 'spawn', stopped): self.refused()
        self.assertIsNotNone(self.children[0].poll())

    def test_descriptor_close_failure_cannot_return_child(self):
        real = m.close_descriptors
        calls = []
        def fail_once(descriptors):
            real(descriptors); calls.append(len(descriptors))
            if len(descriptors) > 2: raise RuntimeError('PRIVATE_SYNTHETIC_CLEANUP')
        with mock.patch.object(m, 'close_descriptors', fail_once): self.refused()
        for child in self.children: self.assertIsNotNone(child.poll())
        self.assertTrue(calls)

    def test_stop_error_still_closes_both_owned_pipes(self):
        real_spawn, real_stop = self.spawn, m.data.archive.stop_owned
        def failed_after_launch(args, **kwargs):
            child = real_spawn(args, **kwargs)
            self.base.response.close()
            self.base.wait(lambda: self.base.collector.state['failure'] is not None)
            return child
        def stop_error(child):
            real_stop(child)
            raise RuntimeError('PRIVATE_SYNTHETIC_STOP')
        with mock.patch.object(m, 'spawn', failed_after_launch), \
                mock.patch.object(m.data.archive, 'stop_owned', stop_error):
            self.assertEqual(self.refused(), 'cleanup')
        child = self.children[0]
        self.assertIsNotNone(child.poll()); self.assertTrue(child.stdin.closed); self.assertTrue(child.stdout.closed)


if __name__ == '__main__': unittest.main()
