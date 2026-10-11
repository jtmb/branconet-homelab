"""Pure full-resource admission/absence oracles; no network or operator reads."""
import copy
import importlib.util
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


m = load('admitted_test_module', HERE.parent / 'bortus-restore-admitted.py')
fixtures = load('admitted_public_fixture', HERE / 'test_bortus_restored_consumer_fence.py')
preflight = load('admitted_preflight_fixture', HERE.parent / 'inspect-bortus-independent-restore.py')
NAME = 'bortus-restore-123456abcdef'
RUN = '123456abcdef'


class AdmittedTests(unittest.TestCase):
    def setUp(self):
        self.e, self.o = fixtures.fixture()
        meta = {'name': NAME, 'labels': {'bortus-restore': RUN}}
        self.p = {
            'storageclass': {'apiVersion': 'storage.k8s.io/v1', 'kind': 'StorageClass',
                'metadata': copy.deepcopy(meta), 'provisioner': 'driver.longhorn.io',
                'reclaimPolicy': 'Retain', 'volumeBindingMode': 'Immediate',
                'allowVolumeExpansion': True,
                'parameters': dict(preflight.PARAMETERS, fromBackup=self.e['backup_url'])},
            'claim': {'apiVersion': 'v1', 'kind': 'PersistentVolumeClaim',
                'metadata': dict(copy.deepcopy(meta), namespace='bortus',
                                 annotations={'helm.sh/resource-policy': 'keep'}),
                'spec': {'storageClassName': NAME, 'accessModes': ['ReadWriteOnce'],
                         'resources': {'requests': {'storage': '1Gi'}}}},
            'pod': {'apiVersion': 'v1', 'kind': 'Pod',
                'metadata': dict(copy.deepcopy(meta), namespace='bortus'),
                'spec': m.health.holder_spec(self.e['holder_image'], NAME, 'node')}}
        self.current = copy.deepcopy(self.p)
        self.reply = {}
        for n, (resource, obj) in enumerate(self.current.items(), 100):
            obj['metadata'].update(uid=fixtures.meta(NAME, n)['uid'], resourceVersion='fresh-z')
            self.reply[resource] = {k: copy.deepcopy(obj[k]) for k in ('apiVersion', 'kind', 'metadata')}
            self.reply[resource]['metadata']['resourceVersion'] = 'created-a'
        self.current['pod']['status'] = copy.deepcopy(self.o['pods']['items'][0]['status'])

    def validate(self, resource, ready=False):
        return m.validate(resource, self.p[resource], self.reply[resource], self.current[resource],
                          require_ready=ready)

    def refuse(self, action):
        with self.assertRaises(m.AdmittedRefused) as caught:
            action()
        self.assertNotIn('PRIVATE', str(caught.exception))
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)

    def test_exact_spec_current_uid_opaque_rv(self):
        for resource in self.p:
            with self.subTest(resource=resource):
                before = copy.deepcopy((self.p, self.reply, self.current))
                result = self.validate(resource)
                self.assertEqual(result.resource_version, 'fresh-z')
                self.assertEqual((self.p, self.reply, self.current), before)
        self.validate('pod', True)

    def test_created_identity_replacement_label_namespace_and_kind(self):
        for resource in self.p:
            for path, value in [('uid', fixtures.meta('replacement', 999)['uid']),
                                ('name', 'foreign'), ('namespace', 'foreign'),
                                ('labels', {'bortus-restore': 'foreign'}),
                                ('deletionTimestamp', 'PRIVATE'),
                                ('ownerReferences', [{'uid': 'PRIVATE'}])]:
                with self.subTest(resource=resource, path=path):
                    self.setUp()
                    self.current[resource]['metadata'][path] = value
                    self.refuse(lambda: self.validate(resource))
        self.setUp()
        self.current['claim']['kind'] = 'Pod'
        self.refuse(lambda: self.validate('claim'))

    def test_sc_unknown_fields_secret_references_replica_policy_and_boolean(self):
        for path, value in [('provisioner', 'foreign'), ('reclaimPolicy', 'Delete'),
                            ('volumeBindingMode', 'WaitForFirstConsumer'),
                            ('allowVolumeExpansion', 1), ('mountOptions', ['PRIVATE'])]:
            with self.subTest(path=path):
                self.setUp()
                self.current['storageclass'][path] = value
                self.refuse(lambda: self.validate('storageclass'))
        for key in preflight.PARAMETERS:
            self.setUp()
            self.current['storageclass']['parameters'][key] = 'PRIVATE'
            self.refuse(lambda: self.validate('storageclass'))

    def test_claim_only_filesystem_default_and_fenced_binding_name(self):
        self.current['claim']['spec'].update(volumeMode='Filesystem', volumeName='pv')
        self.current['claim']['status'] = {'phase': 'Bound'}
        self.validate('claim')
        for key, value in [('volumeMode', 'Block'), ('volumeName', '../PRIVATE'),
                            ('dataSource', {'name': 'PRIVATE'}),
                            ('selector', {'matchLabels': {'private': 'PRIVATE'}}),
                            ('storageClassName', 'longhorn'), ('accessModes', ['ReadWriteMany'])]:
            with self.subTest(key=key):
                self.setUp()
                self.current['claim']['spec'][key] = value
                self.refuse(lambda: self.validate('claim'))
        self.setUp()
        self.current['claim']['metadata']['annotations'] = {}
        self.refuse(lambda: self.validate('claim'))

    def test_pending_holder_spec_validation_cannot_qualify_reader(self):
        self.current['pod']['status'] = {'phase': 'Pending'}
        self.validate('pod')
        self.refuse(lambda: self.validate('pod', True))
        self.setUp()
        self.current['pod']['status']['containerStatuses'][0]['restartCount'] = 1
        self.refuse(lambda: self.validate('pod', True))

    def test_holder_extra_credentials_writes_helpers_and_unknowns(self):
        for key, value in [('automountServiceAccountToken', True),
                            ('initContainers', [{'name': 'PRIVATE'}]),
                            ('ephemeralContainers', [{'name': 'PRIVATE'}]),
                            ('nodeName', 'source-node'), ('hostNetwork', True)]:
            self.setUp()
            self.current['pod']['spec'][key] = value
            self.refuse(lambda: self.validate('pod'))
        for key, value in [('env', [{'name': 'PRIVATE', 'value': 'PRIVATE'}]),
                            ('args', ['PRIVATE']), ('image', 'foreign'),
                            ('imagePullPolicy', 'Always')]:
            self.setUp()
            self.current['pod']['spec']['containers'][0][key] = value
            self.refuse(lambda: self.validate('pod'))
        self.setUp()
        self.current['pod']['spec']['containers'][0]['volumeMounts'][0]['readOnly'] = 1
        self.refuse(lambda: self.validate('pod'))

    def test_exact_benign_defaults_in_shared_holder_predicate(self):
        spec = self.current['pod']['spec']
        spec.update(dnsPolicy='ClusterFirst', schedulerName='default-scheduler', priority=0,
                    serviceAccountName='default', serviceAccount='default', enableServiceLinks=True,
                    terminationGracePeriodSeconds=30, preemptionPolicy='PreemptLowerPriority')
        spec['containers'][0].update(terminationMessagePath='/dev/termination-log',
                                     terminationMessagePolicy='File')
        self.validate('pod', True)
        spec['priority'] = False
        self.refuse(lambda: self.validate('pod'))

    def test_malformed_custom_inputs_and_unknown_scope(self):
        for obj in (None, [], 'PRIVATE', {'metadata': []}):
            self.refuse(lambda: m.validate('pod', self.p['pod'], self.reply['pod'], obj))
        self.refuse(lambda: m.validate('unknown', self.p['pod'], self.reply['pod'], self.current['pod']))
        class Evil(dict):
            def items(self): raise AssertionError('PRIVATE accessor')
        self.refuse(lambda: m.validate('pod', self.p['pod'], self.reply['pod'], Evil(self.current['pod'])))
        self.refuse(lambda: self.validate('pod', 1))

    def test_absence_requires_name_and_owned_uid_gone(self):
        owned = dict(self.current['pod']['metadata'])
        owned.pop('labels')
        empty = fixtures.inventory('Pod', [])
        self.assertEqual(m.holder_absent(empty, owned), 'list-Pod')
        pod = copy.deepcopy(self.current['pod'])
        for modification in ({}, {'deletionTimestamp': 'PRIVATE'},
                             {'uid': fixtures.meta('replacement', 500)['uid']}, {'name': 'foreign'}):
            pod['metadata'] = dict(self.current['pod']['metadata'], **modification)
            self.refuse(lambda: m.holder_absent(fixtures.inventory('Pod', [pod]), owned))

    def test_absence_incomplete_collection_and_duplicates(self):
        owned = {k: self.current['pod']['metadata'][k] for k in ('name', 'namespace', 'uid', 'resourceVersion')}
        for change in ({'continue': 'PRIVATE'}, {'remainingItemCount': 1},
                       {'remainingItemCount': False}, {'resourceVersion': ''}):
            collection = fixtures.inventory('Pod', [])
            collection['metadata'].update(change)
            self.refuse(lambda: m.holder_absent(collection, owned))
        foreign = copy.deepcopy(self.current['pod'])
        foreign['metadata'].update(name='foreign', uid=fixtures.meta('foreign', 600)['uid'])
        self.refuse(lambda: m.holder_absent(fixtures.inventory('Pod', [foreign, foreign]), owned))


if __name__ == '__main__':
    unittest.main()
