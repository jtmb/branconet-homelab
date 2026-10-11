import copy
import importlib.util
import pathlib
import unittest

path = pathlib.Path(__file__).parents[1] / 'bortus-restored-consumer-fence.py'
spec = importlib.util.spec_from_file_location('consumer_fence', path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def meta(name, n, ns=None):
    result = {'name': name, 'uid': '00000000-0000-0000-0000-' + str(n).zfill(12),
              'resourceVersion': 'opaque-' + str(n)}
    if ns:
        result['namespace'] = ns
    return result


def obj(kind, name, n, ns=None, spec=None, status=None):
    return {'apiVersion': m.API if kind in ('Volume', 'Backup', 'Engine', 'Replica') else 'v1',
            'kind': kind, 'metadata': meta(name, n, ns), 'spec': spec or {}, 'status': status or {}}


def inventory(kind, items, ns=None):
    return {'apiVersion': m.API if kind in ('Engine', 'Replica') else 'v1', 'kind': kind + 'List',
            'metadata': {'resourceVersion': 'list-' + kind}, 'items': items}


def fixture():
    expected = {}
    for key, n, ns in [('original_claim', 1, 'bortus'), ('original_pv', 2, None),
            ('original_volume', 3, 'longhorn-system'), ('claim', 4, 'bortus'),
            ('pv', 5, None), ('volume', 6, 'longhorn-system'), ('backup', 7, 'longhorn-system'),
            ('holder', 8, 'bortus'), ('node', 9, None)]:
        name = key.replace('_', '-')
        expected[key] = {k: v for k, v in meta(name, n, ns).items() if k != 'resourceVersion'}
        expected[key]['namespace'] = ns
    expected.update(original_node='source-node', longhorn_version='1.12.1',
        holder_image='registry/bortus@sha256:' + 'a' * 64,
        backup_url='cifs://192.168.0.8/container_backups/k8s-migration-20261009/longhorn?backup=backup&volume=original-volume')
    claim = obj('PersistentVolumeClaim', 'claim', 4, 'bortus',
        {'volumeName': 'pv', 'accessModes': ['ReadWriteOnce'], 'resources': {'requests': {'storage': '1Gi'}}},
        {'phase': 'Bound'})
    pv = obj('PersistentVolume', 'pv', 5, spec={'claimRef': expected['claim'],
        'capacity': {'storage': '1Gi'}, 'persistentVolumeReclaimPolicy': 'Retain',
        'csi': {'driver': 'driver.longhorn.io', 'volumeHandle': 'volume'}}, status={'phase': 'Bound'})
    volume = obj('Volume', 'volume', 6, 'longhorn-system',
        {'encrypted': True, 'numberOfReplicas': 2, 'size': m.SIZE, 'dataEngine': 'v1',
         'Standby': False, 'fromBackup': expected['backup_url'], 'nodeID': 'node'},
        {'state': 'attached', 'robustness': 'healthy', 'currentNodeID': 'node',
         'currentImage': m.ENGINE_IMAGE, 'isStandby': False,
         'restoreInitiated': True, 'restoreRequired': False})
    backup = obj('Backup', 'backup', 7, 'longhorn-system', status={'state': 'Completed',
        'url': expected['backup_url'], 'volumeName': 'original-volume', 'volumeSize': m.SIZE,
        'backupTargetName': 'default'})
    node = obj('Node', 'node', 9, status={'conditions': [{'type': 'Ready', 'status': 'True'}]})
    owner = [{'apiVersion': m.API, 'kind': 'Volume', 'name': 'volume', 'uid': expected['volume']['uid']}]
    instance_spec = {'active': True, 'nodeID': 'node', 'volumeName': 'volume', 'volumeSize': m.SIZE,
                     'dataEngine': 'v1', 'image': m.ENGINE_IMAGE}
    instance_status = {'currentState': 'running', 'currentImage': m.ENGINE_IMAGE, 'started': True}
    engine = obj('Engine', 'engine', 10, 'longhorn-system', copy.deepcopy(instance_spec),
                 copy.deepcopy(instance_status))
    engine['metadata']['ownerReferences'] = copy.deepcopy(owner)
    replicas = []
    addresses = {}
    for n in (11, 12):
        replica = obj('Replica', 'replica-' + str(n), n, 'longhorn-system',
                      dict(instance_spec, engineName='engine', failedAt='', healthyAt='2026-10-11T00:00:00Z'),
                      dict(instance_status, ip='192.0.2.' + str(n), storageIP='192.0.2.' + str(n), port=10000))
        replica['metadata']['ownerReferences'] = copy.deepcopy(owner)
        replicas.append(replica)
        addresses[replica['metadata']['name']] = '192.0.2.' + str(n) + ':10000'
    engine['spec']['replicaAddressMap'] = copy.deepcopy(addresses)
    engine['status'].update(currentReplicaAddressMap=copy.deepcopy(addresses),
                            replicaModeMap={k: 'RW' for k in addresses})
    holder = obj('Pod', 'holder', 8, 'bortus', m.holder_spec(expected['holder_image'], 'claim', 'node'),
        {'phase': 'Running', 'conditions': [{'type': 'Ready', 'status': 'True'}],
         'containerStatuses': [{'name': 'holder', 'image': expected['holder_image'],
                                'imageID': expected['holder_image'], 'ready': True,
                                'restartCount': 0, 'state': {'running': {'startedAt': 'public'}}}]})
    return expected, dict(claim=claim, pv=pv, volume=volume, backup=backup, node=node,
        pvs=inventory('PersistentVolume', [copy.deepcopy(pv)]), pods=inventory('Pod', [holder]),
        engines=inventory('Engine', [engine]), replicas=inventory('Replica', replicas))


class FenceTests(unittest.TestCase):
    def setUp(self):
        self.e, self.o = fixture()

    def reject(self, action):
        action(self.e, self.o)
        with self.assertRaises(m.Refused) as caught:
            m.evaluate(self.e, self.o)
        self.assertNotIn('PRIVATE', str(caught.exception))

    def test_complete_metadata_not_data_or_runtime(self):
        result = m.evaluate(self.e, self.o)
        self.assertTrue(result.metadata_eligible)
        self.assertFalse(result.data_acceptance or result.runtime_acceptance or result.atomic_snapshot)
        self.assertEqual([r.name for r in result.replicas], ['replica-11', 'replica-12'])
        self.assertNotIn('192.0.2.', str(result))
        with self.assertRaises(AttributeError):
            result.metadata_eligible = False

    def test_uid_source_and_mapping_faults(self):
        paths = [('claim', 'metadata', 'uid'), ('pv', 'spec', 'claimRef', 'uid'),
                 ('pv', 'spec', 'csi', 'volumeHandle'), ('volume', 'spec', 'fromBackup'),
                 ('backup', 'status', 'url')]
        for path in paths:
            with self.subTest(path=path):
                self.setUp()
                target = self.o
                for key in path[:-1]: target = target[key]
                self.reject(lambda e, o: target.__setitem__(path[-1], 'PRIVATE'))

    def test_not_independent(self):
        self.reject(lambda e, o: e['original_volume'].update(uid=e['volume']['uid']))

    def test_backup_url_empty_duplicates_and_unknown(self):
        for extra in ('&backup=', '&unknown=', '&volume=', '#', '&unknown=x'):
            self.setUp()
            self.reject(lambda e, o: e.update(backup_url=e['backup_url'] + extra))

    def test_volume_faults_and_literal_flags(self):
        cases = [('spec', 'Standby', True), ('spec', 'encrypted', 1), ('spec', 'numberOfReplicas', True),
                 ('spec', 'dataEngine', 'v2'), ('spec', 'size', '2147483648'),
                 ('status', 'isStandby', True), ('status', 'robustness', 'faulted'),
                 ('status', 'state', 'detached'), ('status', 'restoreRequired', True),
                 ('status', 'restoreInitiated', False), ('spec', 'standby', False)]
        for section, key, value in cases:
            self.setUp()
            with self.subTest(key=key): self.reject(lambda e, o: o['volume'][section].update({key: value}))

    def test_restore_failure_private_message(self):
        self.reject(lambda e, o: o['volume']['status'].update(conditions=[
            {'type': 'Restore', 'status': 'False', 'reason': 'RestoreFailure', 'message': 'PRIVATE'}]))

    def test_complete_collection_fences(self):
        for key in ('pvs', 'pods', 'engines', 'replicas'):
            for addition in ({'continue': 'PRIVATE'}, {'remainingItemCount': 1}, {'resourceVersion': ''}):
                self.setUp()
                with self.subTest(key=key, field=next(iter(addition))):
                    self.reject(lambda e, o: o[key]['metadata'].update(addition))

    def test_alias_even_inactive(self):
        alias = copy.deepcopy(self.o['pv'])
        alias['metadata'] = meta('alias', 50)
        alias['status']['phase'] = 'Released'
        self.reject(lambda e, o: o['pvs']['items'].append(alias))

    def test_duplicate_inventory_identity_and_bound(self):
        self.reject(lambda e, o: o['replicas']['items'].append(copy.deepcopy(o['replicas']['items'][0])))
        self.setUp()
        self.reject(lambda e, o: o['pvs'].update(items=[{}] * (m.MAX_ITEMS + 1)))

    def test_engine_identity_owner_image_and_running(self):
        for section, key, value in [('spec', 'active', False), ('spec', 'nodeID', 'source-node'),
                ('spec', 'image', 'unqualified'), ('status', 'currentState', 'error'),
                ('status', 'currentImage', 'unqualified'), ('status', 'started', False)]:
            self.setUp()
            with self.subTest(key=key):
                self.reject(lambda e, o: o['engines']['items'][0][section].update({key: value}))
        self.setUp()
        self.reject(lambda e, o: o['engines']['items'][0]['metadata']['ownerReferences'][0].update(uid=e['original_volume']['uid']))

    def test_cross_resource_uid_alias(self):
        self.reject(lambda e, o: o['engines']['items'][0]['metadata'].update(uid=e['volume']['uid']))
        self.setUp()
        self.reject(lambda e, o: o['replicas']['items'][0]['metadata'].update(uid=e['original_volume']['uid']))

    def test_replica_owner_failure_active_and_running(self):
        for section, key, value in [('spec', 'engineName', 'foreign'), ('spec', 'failedAt', 'PRIVATE'),
                ('spec', 'healthyAt', ''), ('spec', 'active', False),
                ('status', 'currentState', 'stopped'), ('status', 'port', True)]:
            self.setUp()
            with self.subTest(key=key):
                self.reject(lambda e, o: o['replicas']['items'][0][section].update({key: value}))

    def test_map_requires_names_both_rw_and_actual_addresses(self):
        for section, key in [('spec', 'replicaAddressMap'), ('status', 'currentReplicaAddressMap'),
                             ('status', 'replicaModeMap')]:
            self.setUp()
            self.reject(lambda e, o: o['engines']['items'][0][section].update({key: {'PRIVATE': 'RW'}}))
        self.setUp()
        self.reject(lambda e, o: o['engines']['items'][0]['status']['replicaModeMap'].update({'replica-11': 'WO'}))
        self.setUp()
        self.reject(lambda e, o: o['replicas']['items'][0]['status'].update(storageIP='192.0.2.99'))

    def test_ipv6_join_host_port(self):
        r = self.o['replicas']['items'][0]
        r['status'].update(ip='2001:db8::1', storageIP='2001:db8::1')
        for section, key in [('spec', 'replicaAddressMap'), ('status', 'currentReplicaAddressMap')]:
            self.o['engines']['items'][0][section][key]['replica-11'] = '[2001:db8::1]:10000'
        m.evaluate(self.e, self.o)

    def test_deleting_objects_and_extra_instances(self):
        for key in ('claim', 'pv', 'volume', 'backup', 'node'):
            self.setUp()
            self.reject(lambda e, o: o[key]['metadata'].update(deletionTimestamp='PRIVATE'))
        for key in ('engines', 'replicas', 'pods'):
            self.setUp()
            self.reject(lambda e, o: o[key]['items'][0]['metadata'].update(deletionTimestamp='PRIVATE'))
        self.setUp()
        extra = copy.deepcopy(self.o['engines']['items'][0]); extra['metadata'].update(meta('extra', 99, 'longhorn-system'))
        self.reject(lambda e, o: o['engines']['items'].append(extra))

    def test_holder_no_credentials_writes_or_entrypoint(self):
        cases = [('env', [{'name': 'PRIVATE', 'value': 'PRIVATE'}]), ('args', ['PRIVATE']),
                 ('command', ['application']), ('imagePullPolicy', 'Always')]
        for key, value in cases:
            self.setUp()
            self.reject(lambda e, o: o['pods']['items'][0]['spec']['containers'][0].update({key: value}))
        self.setUp()
        self.reject(lambda e, o: o['pods']['items'][0]['spec']['containers'][0]['volumeMounts'][0].update(readOnly=1))
        self.setUp()
        self.reject(lambda e, o: o['pods']['items'][0]['spec'].update(automountServiceAccountToken=True))

    def test_other_active_consumer_not_terminal_consumers(self):
        foreign = copy.deepcopy(self.o['pods']['items'][0]); foreign['metadata'] = meta('foreign', 70, 'bortus')
        self.reject(lambda e, o: o['pods']['items'].append(foreign))
        self.setUp(); foreign['status']['phase'] = 'Succeeded'
        self.o['pods']['items'].append(foreign)
        m.evaluate(self.e, self.o)

    def test_holder_not_ready_owner_restart_or_alternate(self):
        for status in ({'phase': 'Pending'}, {'conditions': [{'type': 'Ready', 'status': 'False'}]}):
            self.setUp()
            self.reject(lambda e, o: o['pods']['items'][0]['status'].update(status))
        self.setUp()
        self.reject(lambda e, o: o['pods']['items'][0]['metadata'].update(ownerReferences=[{'uid': 'PRIVATE'}]))
        self.setUp()
        self.reject(lambda e, o: e.update(original_node='node'))
        self.setUp()
        self.reject(lambda e, o: o['pods']['items'][0]['status']['containerStatuses'][0].update(restartCount=1))

    def test_ready_duplicate_and_node_unschedulable(self):
        self.reject(lambda e, o: o['node']['status']['conditions'].append({'type': 'Ready', 'status': 'False'}))
        self.setUp()
        self.reject(lambda e, o: o['node']['spec'].update(unschedulable=True))

    def test_defaulted_inert_spec(self):
        spec = self.o['pods']['items'][0]['spec']
        spec.update(dnsPolicy='ClusterFirst', serviceAccountName='default', priority=0)
        spec['containers'][0].update(terminationMessagePath='/dev/termination-log', terminationMessagePolicy='File')
        m.evaluate(self.e, self.o)

    def test_malformed_fixed_errors_and_custom_objects(self):
        for value in (None, [], 'PRIVATE', 1):
            self.setUp()
            self.reject(lambda e, o: o['volume'].update(status=value))
        class Evil(dict):
            def items(self): raise AssertionError('must not invoke accessor')
        with self.assertRaises(m.Refused): m.evaluate(self.e, Evil(self.o))

    def test_opaque_rvs_preserved_not_sorted(self):
        self.o['volume']['metadata']['resourceVersion'] = 'rv-z-before-a'
        result = m.evaluate(self.e, self.o)
        self.assertEqual(result.volume.resource_version, 'rv-z-before-a')


if __name__ == '__main__':
    unittest.main()
