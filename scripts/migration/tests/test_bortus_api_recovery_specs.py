import copy
import importlib.util
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('api_recovery_specs', HERE / 'bortus-api-recovery-specs.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SOURCE = (HERE / 'bortus-api-secret-proof.cjs').read_bytes().decode('utf-8')
RUN = 'e0123456789a'
UID = '00000000-1111-2222-3333-444444444444'

def resource(proposal, defaults=False, runtime=False):
    obj = copy.deepcopy(proposal)
    obj['metadata'].update(uid=UID, resourceVersion='opaque:rv-1')
    if obj['kind'] == 'Pod':
        if defaults:
            obj['spec'].update(dnsPolicy='ClusterFirst', schedulerName='default-scheduler',
                serviceAccountName='default', serviceAccount='default', priority=0,
                preemptionPolicy='PreemptLowerPriority')
            obj['spec']['tolerations'] = [
                {'key': 'node.kubernetes.io/not-ready', 'operator': 'Exists',
                 'effect': 'NoExecute', 'tolerationSeconds': 300},
                {'key': 'node.kubernetes.io/unreachable', 'operator': 'Exists',
                 'effect': 'NoExecute', 'tolerationSeconds': 300}]
            for field in ('containers', 'initContainers', 'ephemeralContainers'):
                for c in obj['spec'].get(field, []):
                    c.update(terminationMessagePath='/dev/termination-log', terminationMessagePolicy='File')
        if runtime:
            obj['status'] = {'phase': 'Running'}
            for field, output in [('containers', 'containerStatuses'),
                ('initContainers', 'initContainerStatuses'), ('ephemeralContainers', 'ephemeralContainerStatuses')]:
                if field not in obj['spec']:
                    continue
                obj['status'][output] = [dict(name=c['name'], image='bounded:display-name',
                    imageID=c['image'], restartCount=0, ready=True,
                    state={'terminated': {'exitCode': 0}} if field == 'initContainers' else {'running': {}})
                    for c in obj['spec'][field]]
    return obj

class RecoverySpecs(unittest.TestCase):
    def setUp(self):
        self.p = m.proposals(RUN, SOURCE)
        self.pod = self.p['pod']

    def refuse(self, obj, proposal=None, runtime=False):
        with self.assertRaisesRegex(ValueError, '^API recovery resource refused$'):
            m.matches(proposal or self.pod, obj, UID, runtime=runtime)

    def test_source_hash_and_closed_owner(self):
        for source, run in [(SOURCE + '\n', RUN), (SOURCE, 'not-owner'), ('fixture', RUN)]:
            with self.subTest(run=run), self.assertRaises(ValueError):
                m.proposals(run, source)

    def test_no_production_mount_or_token_or_entrypoint(self):
        self.assertIs(self.pod['spec']['automountServiceAccountToken'], False)
        self.assertEqual(self.pod['spec']['nodeName'], 'masternode')
        self.assertTrue(all(set(v) <= {'name', 'emptyDir', 'configMap'} for v in self.pod['spec']['volumes']))
        self.assertEqual(self.pod['spec']['containers'][0]['command'][0], 'node')
        self.assertEqual(self.p['policy']['spec'], {'podSelector': {'matchLabels': {'migration.etcd-run': RUN}},
            'policyTypes': ['Ingress', 'Egress']})
        self.assertEqual(self.p['ephemeral_api']['securityContext']['capabilities'],
            {'drop': ['ALL'], 'add': ['NET_BIND_SERVICE']})

    def test_exact_defaulted_full_resource_passes_and_rv_can_advance(self):
        o = resource(self.pod, defaults=True)
        self.assertEqual(m.matches(self.pod, o, UID)['uid'], UID)
        o['metadata']['resourceVersion'] = 'older-looking:opaque-0'
        self.assertEqual(m.matches(self.pod, o, UID)['resourceVersion'], 'older-looking:opaque-0')

    def test_explicit_expected_defaults_remain_required(self):
        p = copy.deepcopy(self.pod)
        p['spec']['priority'] = 0
        p['spec']['containers'][0]['terminationMessagePolicy'] = 'File'
        o = resource(p, defaults=True)
        self.assertEqual(m.matches(p, o, UID)['uid'], UID)
        for mutate in [lambda x: x['spec'].pop('priority'),
                       lambda x: x['spec']['containers'][0].pop('terminationMessagePolicy')]:
            bad = copy.deepcopy(o); mutate(bad); self.refuse(bad, p)

    def test_wrong_defaults_unknown_mount_sidecar_or_token_refuse(self):
        mutations = [lambda x: x['spec'].update(priority=True),
            lambda x: x['spec'].update(hostNetwork=True),
            lambda x: x['spec'].update(automountServiceAccountToken=True),
            lambda x: x['spec']['containers'].append(copy.deepcopy(x['spec']['containers'][0])),
            lambda x: x['spec']['containers'][0]['volumeMounts'].append({'name': 'foreign', 'mountPath': '/extra'}),
            lambda x: x['spec']['initContainers'][0].update(terminationMessagePolicy='FallbackToLogsOnError'),
            lambda x: x['spec']['tolerations'][0].update(tolerationSeconds=True)]
        for mutate in mutations:
            bad = resource(self.pod, defaults=True); mutate(bad)
            with self.subTest(mutate=mutate): self.refuse(bad)

    def test_uid_headers_namespace_and_missing_rv_refuse(self):
        for field, value in [('uid', 'replacement'), ('resourceVersion', None), ('namespace', 'kube-system')]:
            o = resource(self.pod); o['metadata'][field] = value; self.refuse(o)
        o = resource(self.pod); del o['metadata']['resourceVersion']; self.refuse(o)
        o = resource(self.pod); o['apiVersion'] = None; self.refuse(o)
        o = resource(self.pod); o['metadata']['ownerReferences'] = [{'uid': 'foreign'}]; self.refuse(o)

    def test_runtime_literal_imageid_and_complete_states(self):
        o = resource(self.pod, defaults=True, runtime=True)
        self.assertEqual(m.matches(self.pod, o, UID, runtime=True)['uid'], UID)
        for mutate in [lambda x: x['status']['containerStatuses'][0].update(imageID='sha256:config'),
            lambda x: x['status']['containerStatuses'][0].update(imageID='docker-pullable://' + m.NODE_IMAGE),
            lambda x: x['status']['containerStatuses'][0]['state'].update(waiting={}),
            lambda x: x['status']['initContainerStatuses'][0]['state']['terminated'].update(exitCode=True),
            lambda x: x['status']['containerStatuses'][0].update(restartCount=1),
            lambda x: x['status']['containerStatuses'].pop()]:
            bad = copy.deepcopy(o); mutate(bad); self.refuse(bad, runtime=True)

    def test_ephemeral_body_preserves_current_spec_and_exact_uid_rv(self):
        current = resource(self.pod, defaults=True, runtime=True)
        path, body, final = m.ephemeral_update(self.pod, current, self.p['ephemeral_api'], UID)
        self.assertTrue(path.endswith('/' + self.pod['metadata']['name'] + '/ephemeralcontainers'))
        self.assertEqual(body['metadata'], {k: current['metadata'][k] for k in ('name', 'namespace', 'uid', 'resourceVersion')})
        added = body['spec'].pop('ephemeralContainers')
        self.assertEqual(body['spec'], current['spec'])
        self.assertEqual(added, [self.p['ephemeral_api']])
        actual = resource(final, defaults=True, runtime=True)
        self.assertEqual(m.matches(final, actual, UID, runtime=True)['uid'], UID)
        with self.assertRaises(ValueError): m.ephemeral_update(final, actual, self.p['ephemeral_api'], UID)

    def test_modified_api_program_and_invalid_reply_refuse(self):
        current = resource(self.pod, runtime=True)
        api = copy.deepcopy(self.p['ephemeral_api']); api['command'].append('--anonymous-auth=true')
        with self.assertRaises(ValueError): m.ephemeral_update(self.pod, current, api, UID)
        final = copy.deepcopy(self.pod); final['spec']['ephemeralContainers'] = [self.p['ephemeral_api']]
        o = resource(final, runtime=True)
        o['spec']['ephemeralContainers'][0]['volumeMounts'][0]['subPath'] = 'foreign'
        self.refuse(o, final)

    def test_public_refusal_locals_drop_raw_resource(self):
        o = resource(self.pod); o['spec']['private_raw_reply'] = 'PUBLIC_FIXTURE_NEEDLE'
        try: m.matches(self.pod, o, UID)
        except ValueError as e:
            tb = e.__traceback__
            while tb and tb.tb_frame.f_code.co_name != 'matches': tb = tb.tb_next
            self.assertIsNotNone(tb)
            for name in ('proposal', 'obj', 'expected_uid', 'result'):
                self.assertIsNone(tb.tb_frame.f_locals[name])
            self.assertIsNone(e.__context__)
        else: self.fail('expected refusal')

    def test_policy_and_configmap_exact_no_secret_payload(self):
        for name in ('policy', 'configmap'):
            p = self.p[name]; o = resource(p)
            self.assertEqual(m.matches(p, o, UID)['uid'], UID)
            if name == 'policy': o['spec']['ingress'] = [{'from': [{}]}]
            else: o['data']['extra'] = 'fixture'
            self.refuse(o, p)

    def test_explicit_bool_integer_substitution_refuses(self):
        for mutate in [lambda x: x['spec'].update(automountServiceAccountToken=0),
                       lambda x: x['spec']['containers'][0]['securityContext'].update(allowPrivilegeEscalation=0)]:
            o = resource(self.pod); mutate(o); self.refuse(o)

if __name__ == '__main__': unittest.main()
