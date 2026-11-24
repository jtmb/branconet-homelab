"""kube-apiserver audit logging: policy, manifest transform, log check (audit A1).

The policy tests evaluate the shipped policy with the documented first-match
semantics, so a future rule placed above the credential rule cannot silently
start recording Secret values or issued tokens.
"""
import importlib.util
import json
import pathlib
import subprocess
import sys
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[3]
MIGRATION = ROOT / 'scripts/migration'
PLAYBOOK = ROOT / 'k8s-rewrite/ansible-playbook/playbooks/apiserver-audit-logging.yml'
POLICY = ROOT / 'k8s-rewrite/ansible-playbook/playbooks/files/kube-apiserver-audit-policy.yaml'


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, MIGRATION / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = load('apiserver_audit', 'apiserver_audit.py')
CHECK = load('apiserver_audit_log_check', 'apiserver_audit_log_check.py')

MANIFEST = """\
apiVersion: v1
kind: Pod
metadata:
  annotations:
    kubeadm.kubernetes.io/kube-apiserver.advertise-address.endpoint: 192.168.0.6:6443
  creationTimestamp: null
  labels:
    component: kube-apiserver
    tier: control-plane
  name: kube-apiserver
  namespace: kube-system
spec:
  containers:
  - command:
    - kube-apiserver
    - --advertise-address=192.168.0.6
    - --authorization-mode=Node,RBAC
    - --kubelet-client-key=/etc/kubernetes/pki/apiserver-kubelet-client.key
    - --kubelet-certificate-authority=/etc/kubernetes/pki/ca.crt
    - --tls-private-key-file=/etc/kubernetes/pki/apiserver.key
    - --encryption-provider-config=/etc/kubernetes/encryption-config.json
    image: registry.k8s.io/kube-apiserver:v1.37.2
    imagePullPolicy: IfNotPresent
    livenessProbe:
      failureThreshold: 8
      httpGet:
        host: 192.168.0.6
        path: /livez
        port: probe-port
        scheme: HTTPS
      initialDelaySeconds: 10
    name: kube-apiserver
    ports:
    - containerPort: 6443
      name: probe-port
      protocol: TCP
    resources:
      requests:
        cpu: 250m
    volumeMounts:
    - mountPath: /etc/ssl/certs
      name: ca-certs
      readOnly: true
    - mountPath: /etc/kubernetes/encryption-config.json
      name: encryption-config
      readOnly: true
    - mountPath: /etc/kubernetes/pki
      name: k8s-certs
      readOnly: true
  hostNetwork: true
  priority: 2000001000
  priorityClassName: system-node-critical
  securityContext:
    seccompProfile:
      type: RuntimeDefault
  volumes:
  - hostPath:
      path: /etc/ssl/certs
      type: DirectoryOrCreate
    name: ca-certs
  - hostPath:
      path: /etc/kubernetes/encryption-config.json
      type: File
    name: encryption-config
  - hostPath:
      path: /etc/kubernetes/pki
      type: DirectoryOrCreate
    name: k8s-certs
status: {}
"""

# The live kube-system/kubeadm-config ClusterConfiguration, 2026-11-18.
CLUSTER_CONFIGURATION = """\
apiServer:
  certSANs:
  - k8s-api.branconet.lan
  - 192.168.0.251
  extraArgs:
  - name: kubelet-certificate-authority
    value: /etc/kubernetes/pki/ca.crt
  - name: encryption-provider-config
    value: /etc/kubernetes/encryption-config.json
  extraVolumes:
  - hostPath: /etc/kubernetes/encryption-config.json
    mountPath: /etc/kubernetes/encryption-config.json
    name: encryption-config
    pathType: File
    readOnly: true
apiVersion: kubeadm.k8s.io/v1beta4
certificatesDir: /etc/kubernetes/pki
clusterName: branconet-k8s
controlPlaneEndpoint: k8s-api.branconet.lan:6443
etcd:
  local:
    dataDir: /var/lib/etcd
    imageRepository: registry.k8s.io
    imageTag: 3.7.3-0@sha256:0d27b9478551f431f82d1e0ddb6c87ad07ebae8b904c637f3a99213349523910
imageRepository: registry.k8s.io
kind: ClusterConfiguration
kubernetesVersion: v1.37.2
networking:
  dnsDomain: cluster.local
  podSubnet: 10.244.0.0/16
  serviceSubnet: 10.96.0.0/12
"""


def _pattern(pattern, value):
    return pattern == '*' or pattern == value or (pattern.endswith('*') and value.startswith(pattern[:-1]))


def level_for(policy, *, verb, user='kubernetes-admin', groups=('system:authenticated',),
              group=None, resource=None, subresource='', path=None):
    """First-match evaluation as documented for audit.k8s.io/v1 Policy."""
    for rule in policy['rules']:
        if 'users' in rule and user not in rule['users']:
            continue
        if 'userGroups' in rule and not set(groups) & set(rule['userGroups']):
            continue
        if 'verbs' in rule and verb not in rule['verbs']:
            continue
        if 'resources' in rule:
            if resource is None:
                continue
            name = resource + ('/' + subresource if subresource else '')
            if not any(entry.get('group', '') == group and
                       any(_pattern(item, name) for item in entry.get('resources', ['*']))
                       for entry in rule['resources']):
                continue
        if 'nonResourceURLs' in rule:
            if path is None or not any(_pattern(item, path) for item in rule['nonResourceURLs']):
                continue
        return rule['level']
    return 'None'


class PolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = yaml.safe_load(POLICY.read_text())

    def level(self, **request):
        return level_for(self.policy, **request)

    def test_policy_shape(self):
        self.assertEqual((self.policy['apiVersion'], self.policy['kind']), ('audit.k8s.io/v1', 'Policy'))
        self.assertEqual(self.policy['omitStages'], ['RequestReceived'])
        self.assertIs(self.policy['omitManagedFields'], True)
        self.assertEqual(self.policy['rules'][-1], {'level': 'Metadata'})
        for rule in self.policy['rules']:
            self.assertIn(rule['level'], ('None', 'Metadata', 'Request', 'RequestResponse'))
            for url in rule.get('nonResourceURLs', []):
                self.assertNotIn('*', url[:-1], url)

    def test_credential_bodies_are_never_recorded(self):
        for verb in ('get', 'list', 'watch', 'create', 'update', 'patch', 'delete', 'deletecollection'):
            for resource in ('secrets', 'configmaps'):
                for user, groups in (('kubernetes-admin', ('system:masters',)),
                                     ('system:serviceaccount:flux-system:helm-controller',
                                      ('system:serviceaccounts',)),
                                     ('system:node:node01', ('system:nodes',))):
                    with self.subTest(verb=verb, resource=resource, user=user):
                        self.assertEqual(self.level(verb=verb, user=user, groups=groups,
                                                    group='', resource=resource), 'Metadata')
        self.assertEqual(self.level(verb='create', group='', resource='serviceaccounts',
                                    subresource='token'), 'Metadata')
        self.assertEqual(self.level(verb='create', group='authentication.k8s.io',
                                    resource='tokenreviews'), 'Metadata')

    def test_only_rbac_changes_record_bodies(self):
        body_rules = [r for r in self.policy['rules'] if r['level'] in ('Request', 'RequestResponse')]
        self.assertEqual(len(body_rules), 1)
        self.assertEqual([e['group'] for e in body_rules[0]['resources']], ['rbac.authorization.k8s.io'])
        for resource in ('roles', 'rolebindings', 'clusterroles', 'clusterrolebindings'):
            self.assertEqual(self.level(verb='patch', group='rbac.authorization.k8s.io', resource=resource),
                             'RequestResponse')
            self.assertEqual(self.level(verb='get', group='rbac.authorization.k8s.io', resource=resource),
                             'Metadata')

    def test_noise_is_dropped_and_the_rest_is_metadata(self):
        self.assertEqual(self.level(verb='get', path='/readyz'), 'None')
        self.assertEqual(self.level(verb='get', path='/livez'), 'None')
        self.assertEqual(self.level(verb='get', path='/openapi/v3'), 'None')
        self.assertEqual(self.level(verb='get', path='/metrics'), 'Metadata')
        self.assertEqual(self.level(verb='update', group='coordination.k8s.io', resource='leases'), 'None')
        self.assertEqual(self.level(verb='delete', group='coordination.k8s.io', resource='leases'), 'Metadata')
        self.assertEqual(self.level(verb='watch', user='system:kube-proxy', group='discovery.k8s.io',
                                    resource='endpointslices'), 'None')
        self.assertEqual(self.level(verb='watch', group='discovery.k8s.io', resource='endpointslices'),
                         'Metadata')
        self.assertEqual(self.level(verb='create', group='', resource='pods', subresource='exec'), 'Metadata')
        self.assertEqual(self.level(verb='patch', group='apps', resource='deployments'), 'Metadata')


class ManifestTest(unittest.TestCase):
    def test_enable_appends_exactly_and_preserves_everything_else(self):
        original = yaml.safe_load(MANIFEST)
        result = AUDIT.manifest_transform(MANIFEST)
        self.assertEqual((result['state'], result['changed']), ('absent', True))
        enabled = yaml.safe_load(result['manifest'])
        container, before = enabled['spec']['containers'][0], original['spec']['containers'][0]
        self.assertEqual(container['command'][:len(before['command'])], before['command'])
        self.assertEqual(container['command'][len(before['command']):], [
            '--audit-policy-file=/etc/kubernetes/audit-policy.yaml',
            '--audit-log-path=/var/log/kubernetes/audit/audit.log',
            '--audit-log-maxage=30', '--audit-log-maxbackup=30', '--audit-log-maxsize=100',
            '--audit-log-compress=true'])
        self.assertEqual(container['volumeMounts'][:3], before['volumeMounts'])
        self.assertEqual(enabled['spec']['volumes'][:3], original['spec']['volumes'])
        self.assertEqual(container['volumeMounts'][3:], [dict(m) for m in AUDIT.MOUNTS])
        self.assertEqual(enabled['spec']['volumes'][3:], list(AUDIT.VOLUMES))
        for key in ('command', 'volumeMounts'):
            before.pop(key), container.pop(key)
        original['spec'].pop('volumes'), enabled['spec'].pop('volumes')
        self.assertEqual(enabled, original)

    def test_enable_is_idempotent_and_byte_stable(self):
        first = AUDIT.manifest_transform(MANIFEST)['manifest']
        second = AUDIT.manifest_transform(first)
        self.assertEqual((second['state'], second['changed']), ('enabled', False))
        self.assertEqual(second['manifest'], first)
        self.assertEqual(second['sha256_before'], second['sha256_after'])

    def test_kubeadm_rendered_mount_without_readonly_counts_as_enabled(self):
        pod = yaml.safe_load(AUDIT.manifest_transform(MANIFEST)['manifest'])
        pod['spec']['containers'][0]['volumeMounts'][-1]['readOnly'] = False
        self.assertEqual(AUDIT.manifest_state(pod), 'enabled')

    def test_partial_or_different_settings_are_refused(self):
        enabled = yaml.safe_load(AUDIT.manifest_transform(MANIFEST)['manifest'])
        cases = {}
        pod = yaml.safe_load(MANIFEST)
        pod['spec']['containers'][0]['command'].append('--audit-log-path=/tmp/audit.log')
        cases['different path'] = pod
        pod = yaml.safe_load(yaml.safe_dump(enabled))
        pod['spec']['volumes'] = pod['spec']['volumes'][:3]
        cases['flags without volumes'] = pod
        pod = yaml.safe_load(yaml.safe_dump(enabled))
        pod['spec']['containers'][0]['command'].append('--audit-log-maxage=7')
        cases['duplicate flag'] = pod
        pod = yaml.safe_load(yaml.safe_dump(enabled))
        pod['spec']['containers'][0]['volumeMounts'][-1]['readOnly'] = True
        cases['read-only log mount'] = pod
        pod = yaml.safe_load(MANIFEST)
        pod['spec']['containers'][0]['volumeMounts'].append(
            {'name': 'other', 'mountPath': '/var/log/kubernetes/audit'})
        cases['path already mounted'] = pod
        for name, pod in cases.items():
            with self.subTest(name):
                with self.assertRaises(AUDIT.AuditConfigError):
                    AUDIT.enable_manifest(pod)

    def test_only_the_kubeadm_api_server_pod_is_accepted(self):
        for change in (lambda p: p['metadata'].update(name='etcd'),
                       lambda p: p.update(kind='Deployment'),
                       lambda p: p['spec']['containers'].append({'name': 'sidecar'}),
                       lambda p: p['spec']['containers'][0]['command'].__setitem__(0, 'sh')):
            pod = yaml.safe_load(MANIFEST)
            change(pod)
            with self.assertRaises(AUDIT.AuditConfigError):
                AUDIT.enable_manifest(pod)

    def test_cli_contract_used_by_the_play(self):
        ok = subprocess.run([sys.executable, '-B', str(MIGRATION / 'apiserver_audit.py'), 'manifest'],
                            input=MANIFEST, capture_output=True, text=True, check=True)
        result = json.loads(ok.stdout)
        self.assertEqual(set(result), {'state', 'changed', 'manifest', 'sha256_before', 'sha256_after'})
        bad = subprocess.run([sys.executable, '-B', str(MIGRATION / 'apiserver_audit.py'), 'manifest'],
                             input=MANIFEST.replace('name: kube-apiserver\n  namespace', 'name: x\n  namespace'),
                             capture_output=True, text=True)
        self.assertEqual((bad.returncode, json.loads(bad.stdout)), (2, {'error': 'not_kube_apiserver'}))


class ClusterConfigurationTest(unittest.TestCase):
    def test_enable_appends_flags_and_volumes(self):
        text, changed = AUDIT.enable_cluster_configuration(CLUSTER_CONFIGURATION)
        self.assertTrue(changed)
        original, result = yaml.safe_load(CLUSTER_CONFIGURATION), yaml.safe_load(text)
        api = result['apiServer']
        self.assertEqual(api['extraArgs'][:2], original['apiServer']['extraArgs'])
        self.assertEqual(api['extraArgs'][2:], [{'name': n, 'value': v} for n, v in AUDIT.FLAGS])
        self.assertEqual(api['extraVolumes'][:1], original['apiServer']['extraVolumes'])
        self.assertEqual(api['extraVolumes'][1:], list(AUDIT.KUBEADM_VOLUMES))
        for key in ('extraArgs', 'extraVolumes'):
            api.pop(key), original['apiServer'].pop(key)
        self.assertEqual(result, original)
        self.assertEqual(AUDIT.enable_cluster_configuration(text), (text, False))

    def test_different_settings_and_versions_are_refused(self):
        config = yaml.safe_load(CLUSTER_CONFIGURATION)
        config['apiServer']['extraArgs'].append({'name': 'audit-log-path', 'value': '/tmp/a.log'})
        with self.assertRaises(AUDIT.AuditConfigError):
            AUDIT.enable_cluster_configuration(yaml.safe_dump(config))
        with self.assertRaises(AUDIT.AuditConfigError):
            AUDIT.enable_cluster_configuration(CLUSTER_CONFIGURATION.replace('v1beta4', 'v1beta3'))

    def test_kubeadm_volumes_match_the_manifest_volumes(self):
        mounts = {m['name']: m for m in AUDIT.MOUNTS}
        volumes = {v['name']: v for v in AUDIT.VOLUMES}
        for item in AUDIT.KUBEADM_VOLUMES:
            self.assertEqual(item['mountPath'], mounts[item['name']]['mountPath'])
            self.assertEqual(bool(item.get('readOnly')), bool(mounts[item['name']].get('readOnly')))
            self.assertEqual({'path': item['hostPath'], 'type': item['pathType']},
                             volumes[item['name']]['hostPath'])


class PlaybookAgreementTest(unittest.TestCase):
    def test_playbook_paths_match_the_transform(self):
        variables = yaml.safe_load(PLAYBOOK.read_text())[0]['vars']
        self.assertEqual(variables['policy_path'], AUDIT.POLICY_PATH)
        self.assertEqual(variables['log_dir'], AUDIT.LOG_DIR)
        self.assertEqual(variables['log_path'], AUDIT.LOG_PATH)
        self.assertEqual(variables['manifest_path'], '/etc/kubernetes/manifests/kube-apiserver.yaml')
        self.assertFalse(variables['backup_path'].startswith('/etc/kubernetes/manifests/'))


class LogCheckTest(unittest.TestCase):
    def event(self, resource, name='x', level='Metadata', stage='ResponseComplete', subresource=None, **extra):
        reference = {'resource': resource, 'namespace': 'kube-system', 'name': name, 'apiVersion': 'v1'}
        if subresource:
            reference['subresource'] = subresource
        return json.dumps(dict({'kind': 'Event', 'apiVersion': 'audit.k8s.io/v1', 'level': level,
                                'stage': stage, 'verb': 'get', 'objectRef': reference,
                                'responseStatus': {'code': 404}}, **extra)).encode() + b'\n'

    def test_probe_found_and_credential_bodies_counted(self):
        lines = [self.event('configmaps', 'audit-probe-a', stage='ResponseStarted'),
                 self.event('configmaps', 'audit-probe-a'),
                 self.event('secrets'),
                 self.event('serviceaccounts', subresource='token', requestObject={'spec': {}}),
                 self.event('deployments', requestObject={}),
                 self.event('rolebindings', level='RequestResponse', requestObject={'kind': 'RoleBinding'}),
                 b'not json\n', b'\n']
        lines[-3] = lines[-3].replace(b'"apiVersion": "v1"}', b'"apiVersion": "v1", "apiGroup": "rbac.authorization.k8s.io"}')
        summary = CHECK.summarize(lines, 'audit-probe-a')
        self.assertEqual(summary['events'], 6)
        self.assertEqual(summary['levels'], {'Metadata': 5, 'RequestResponse': 1})
        self.assertEqual(summary['rbac_changes_with_body'], 1)
        self.assertEqual(summary['unparsed_lines'], 1)
        self.assertEqual(summary['credential_events'], 4)  # two probe ConfigMap reads, Secret, token
        self.assertEqual(summary['credential_bodies'], 1)
        self.assertEqual(summary['probe'], {'level': 'Metadata', 'verb': 'get', 'code': 404, 'has_body': False})
        self.assertIsNone(CHECK.summarize(lines, 'audit-probe-b')['probe'])


if __name__ == '__main__':
    unittest.main()
