import copy
import contextlib
import importlib.util
import io
import pathlib
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('checkpoint_preflight',
    pathlib.Path(__file__).resolve().parents[1] / 'inspect-bortus-checkpoint.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def metadata(name, namespace=None):
    return {'name': name, 'uid': name + '-uid', 'resourceVersion': '1', 'namespace': namespace}


def fixture():
    claim = {'metadata': metadata('bortus-data', 'bortus') | {
        'annotations': {'helm.sh/resource-policy': 'keep'}},
        'spec': {'volumeName': 'pvc-fixture', 'storageClassName': 'longhorn'},
        'status': {'phase': 'Bound'}}
    pv = {'metadata': metadata('pvc-fixture'), 'spec': {
        'claimRef': {'uid': 'bortus-data-uid', 'namespace': 'bortus', 'name': 'bortus-data'},
        'csi': {'driver': 'driver.longhorn.io', 'volumeHandle': 'pvc-fixture'},
        'persistentVolumeReclaimPolicy': 'Retain'}}
    volume = {'metadata': metadata('pvc-fixture', 'longhorn-system'),
        'spec': {'encrypted': True, 'numberOfReplicas': 2}, 'status': {'robustness': 'healthy'}}
    podspec = {'nodeName': 'node-fixture', 'volumes': [
        {'name': 'data', 'persistentVolumeClaim': {'claimName': 'bortus-data'}}],
        'containers': [{'name': 'app', 'env': [{'name': 'FIXTURE_PRIVATE', 'value': 'not-for-report'}]}]}
    deployment = {'metadata': metadata('bortus', 'bortus'),
        'spec': {'replicas': 1, 'strategy': {'type': 'Recreate'}, 'template': {'spec': podspec}}}
    pod = {'metadata': metadata('writer-fixture', 'bortus') | {'ownerReferences': [
        {'kind': 'ReplicaSet', 'controller': True, 'name': 'rs-fixture', 'uid': 'rs-fixture-uid'}]}, 'spec': podspec,
        'status': {'phase': 'Running', 'conditions': [{'type': 'Ready', 'status': 'True'}]}}
    release = {'metadata': metadata('bortus', 'flux-system'), 'spec': {
        'releaseName': 'bortus', 'targetNamespace': 'bortus', 'storageNamespace': 'bortus',
        'chart': {'spec': {'chart': './charts/bortus', 'sourceRef': {'name': 'branconet-charts'}}}}}
    owner = {'metadata': metadata('migration-releases', 'flux-system'), 'spec': {
        'sourceRef': {'name': 'branconet-charts'}, 'path': './flux/releases', 'prune': False}}
    target = {'metadata': metadata('default', 'longhorn-system'), 'status': {'available': True}}
    rs = {'metadata': metadata('rs-fixture', 'bortus') | {'ownerReferences': [
        {'kind': 'Deployment', 'controller': True, 'name': 'bortus', 'uid': 'bortus-uid'}]}}
    return [claim, pv, volume, deployment, {'items': [pod]}, release, owner, target, rs]


class CheckpointPreflight(unittest.TestCase):
    def test_metadata_only_and_no_acceptance_overclaim(self):
        import json
        report = module.evaluate(fixture(), 'bortus-data-uid')
        self.assertTrue(report['checks_passed'])
        self.assertEqual(report['mutations'], 0)
        self.assertFalse(report['cold_capture_proven'])
        self.assertNotIn('not-for-report', json.dumps(report))
        self.assertNotIn('holder_proposal', report)

    def test_recreated_or_remapped_storage_refused(self):
        for index, path, value in [(0, ('metadata', 'uid'), 'replacement'),
                                  (1, ('spec', 'claimRef', 'uid'), 'replacement'),
                                  (1, ('spec', 'csi', 'volumeHandle'), 'replacement'),
                                  (2, ('metadata', 'name'), 'replacement')]:
            objects = fixture()
            node = objects[index]
            for key in path[:-1]:
                node = node[key]
            node[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                module.evaluate(objects, 'bortus-data-uid')

    def test_storage_safety_drift_refused(self):
        for index, path, value in [(0, ('status', 'phase'), 'Pending'),
                (0, ('metadata', 'annotations', 'helm.sh/resource-policy'), 'delete'),
                (1, ('spec', 'persistentVolumeReclaimPolicy'), 'Delete'),
                (2, ('spec', 'encrypted'), False),
                (2, ('spec', 'numberOfReplicas'), True),
                (2, ('status', 'robustness'), 'degraded'),
                (7, ('status', 'available'), False)]:
            objects = fixture()
            node = objects[index]
            for key in path[:-1]:
                node = node[key]
            node[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                module.evaluate(objects, 'bortus-data-uid')

    def test_additional_terminating_or_unready_consumer_refused(self):
        for change in ('extra', 'terminating', 'unready', 'not-controller'):
            objects = fixture()
            pod = objects[4]['items'][0]
            if change == 'extra':
                objects[4]['items'].append(copy.deepcopy(pod))
            elif change == 'terminating':
                pod['metadata']['deletionTimestamp'] = 'fixture'
            elif change == 'unready':
                pod['status']['conditions'][0]['status'] = 'False'
            else:
                pod['metadata']['ownerReferences'] = []
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                module.evaluate(objects, 'bortus-data-uid')

    def test_writer_and_flux_owner_drift_refused(self):
        for index, path, value in [(3, ('spec', 'replicas'), 2),
                (3, ('spec', 'strategy', 'type'), 'RollingUpdate'),
                (5, ('spec', 'targetNamespace'), 'replacement'),
                (6, ('spec', 'prune'), True), (6, ('spec', 'force'), True),
                (6, ('spec', 'sourceRef', 'name'), 'old-source')]:
            objects = fixture()
            node = objects[index]
            for key in path[:-1]:
                node = node[key]
            node[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                module.evaluate(objects, 'bortus-data-uid')

    def test_holder_is_inert_readonly_and_unqualified(self):
        image = 'registry.example/bortus@sha256:' + 'a' * 64
        report = module.evaluate(fixture(), 'bortus-data-uid', image)
        pod = report['holder_proposal']['spec']
        self.assertFalse(pod['automountServiceAccountToken'])
        self.assertEqual(len(pod['containers']), 1)
        self.assertEqual(pod['containers'][0]['imagePullPolicy'], 'Never')
        self.assertTrue(pod['containers'][0]['volumeMounts'][0]['readOnly'])
        self.assertTrue(pod['volumes'][0]['persistentVolumeClaim']['readOnly'])
        self.assertNotIn('env', pod['containers'][0])
        self.assertFalse(report['holder_image_qualification_proven'])
        for bad in ('bortus:latest', 'bortus:v1@sha256:' + 'a' * 64,
                    'bortus@sha256:' + 'a' * 63):
            with self.subTest(image=bad), self.assertRaises(RuntimeError):
                module.evaluate(fixture(), 'bortus-data-uid', bad)

    def test_other_deployments_consumer_cannot_be_stopped_as_bortus(self):
        for change in ('pod-owner', 'rs-owner', 'rs-namespace'):
            objects = fixture()
            if change == 'pod-owner':
                objects[4]['items'][0]['metadata']['ownerReferences'][0]['uid'] = 'other'
            elif change == 'rs-owner':
                objects[8]['metadata']['ownerReferences'][0]['uid'] = 'other'
            else:
                objects[8]['metadata']['namespace'] = 'other'
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                module.evaluate(objects, 'bortus-data-uid')

    def test_cli_refuses_evidence_overwrite_before_api_reads(self):
        with tempfile.TemporaryDirectory() as folder:
            output = pathlib.Path(folder) / 'evidence.json'
            output.write_text('retained evidence', encoding='utf-8')
            with mock.patch.object(module.sys, 'argv', ['inspector', '--expected-claim-uid',
                    'bortus-data-uid', '--output', str(output)]), mock.patch.object(module, 'Client') as client, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(module.main(), 1)
                client.assert_not_called()
            self.assertEqual(output.read_text(encoding='utf-8'), 'retained evidence')

    def test_cli_api_failures_never_report_response_or_error_values(self):
        with tempfile.TemporaryDirectory() as folder:
            output = pathlib.Path(folder) / 'evidence.json'
            stderr = io.StringIO()
            with mock.patch.object(module.sys, 'argv', ['inspector', '--expected-claim-uid',
                    'bortus-data-uid', '--output', str(output)]), mock.patch.object(module, 'Client') as client, \
                    contextlib.redirect_stderr(stderr):
                client.return_value.inspect.side_effect = RuntimeError('private-fixture-sentinel')
                self.assertEqual(module.main(), 1)
            self.assertNotIn('private-fixture-sentinel', stderr.getvalue())
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
