"""Fixed API recovery proposals and pure metadata matcher. No dispatch authority.

Root must qualify defaulting, cached binaries and the ephemeral subresource before
using these exact proposals. Importing this file performs no operation.
"""
import copy
import re
import hashlib

NS = 'migration-system'
NODE_IMAGE = 'docker.io/library/bortus@sha256:068254f38c47f99fd35604185a806a92147d934010329638b32adb5c19802c90'
ETCD_IMAGE = 'registry.k8s.io/etcd@sha256:6ecefbe2510c4a30573a62a4d6dd175acf881ca67003fcd91849a16df7a724d5'
API_IMAGE = 'registry.k8s.io/kube-apiserver@sha256:e190f914a6cc21cab9268485d1ae7282fdeab1315ac64b668aa42d732fd1061d'
PROGRAM_SHA256 = '918f71713074bfa7bc7739bde2574932aa89655bb9d66aed4c0a535123279c9d'
PROGRAM_PATH = '/program/bortus-api-secret-proof.cjs'

SC = {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
      'capabilities': {'drop': ['ALL']}, 'runAsNonRoot': True,
      'runAsUser': 1000, 'runAsGroup': 1000,
      'seccompProfile': {'type': 'RuntimeDefault'}}

PREPARE_JS = "'use strict';const fs=require('node:fs');for(const p of ['/memory-proof/proof','/memory-tools/tools']){fs.mkdirSync(p,{mode:448});const s=fs.lstatSync(p);if(!s.isDirectory()||s.uid!==1000||(s.mode&511)!==448)process.exit(1)}"
IDLE_JS = "'use strict';setInterval(()=>{},1000)"

def proposals(run_id, exact_program_text):
    if not isinstance(run_id, str) or not re.fullmatch('[0-9a-f]{12}', run_id):
        raise ValueError('API recovery proposal refused')
    if not isinstance(exact_program_text, str) or not 0 < len(exact_program_text.encode()) <= 131072:
        raise ValueError('API recovery proposal refused')
    if hashlib.sha256(exact_program_text.encode('utf-8')).hexdigest() != PROGRAM_SHA256:
        raise ValueError('API recovery proposal refused')
    name = 'api-recovery-' + run_id
    labels = {'migration.etcd-run': run_id}
    metadata = {'name': name, 'namespace': NS, 'labels': labels}
    cm = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': copy.deepcopy(metadata),
          'immutable': True, 'data': {'bortus-api-secret-proof.cjs': exact_program_text}}
    policy = {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
              'metadata': copy.deepcopy(metadata), 'spec': {
                  'podSelector': {'matchLabels': labels}, 'policyTypes': ['Ingress', 'Egress']}}
    shared = [ {'name': 'proof', 'mountPath': '/proof', 'subPath': 'proof'},
               {'name': 'tools', 'mountPath': '/tools', 'subPath': 'tools'} ]
    pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': copy.deepcopy(metadata), 'spec': {
        'nodeName': 'masternode', 'automountServiceAccountToken': False,
        'enableServiceLinks': False, 'restartPolicy': 'Never',
        'terminationGracePeriodSeconds': 5,
        'securityContext': {'runAsNonRoot': True, 'runAsUser': 1000,
                            'runAsGroup': 1000, 'fsGroup': 1000,
                            'seccompProfile': {'type': 'RuntimeDefault'}},
        'initContainers': [{'name': 'memory-owner', 'image': NODE_IMAGE,
            'imagePullPolicy': 'Never', 'command': ['node', '-e', PREPARE_JS],
            'securityContext': copy.deepcopy(SC),
            'resources': {'requests': {'cpu': '10m', 'memory': '32Mi'},
                          'limits': {'cpu': '1', 'memory': '128Mi'}},
            'volumeMounts': [{'name': 'proof', 'mountPath': '/memory-proof'},
                             {'name': 'tools', 'mountPath': '/memory-tools'}]}],
        'containers': [
            {'name': 'utility', 'image': NODE_IMAGE, 'imagePullPolicy': 'Never',
             'command': ['node', '-e', IDLE_JS], 'securityContext': copy.deepcopy(SC),
             'resources': {'requests': {'cpu': '50m', 'memory': '128Mi'},
                           'limits': {'cpu': '1', 'memory': '512Mi'}},
             'volumeMounts': copy.deepcopy(shared) + [
                 {'name': 'program', 'mountPath': '/program', 'readOnly': True}]},
            {'name': 'etcd', 'image': ETCD_IMAGE, 'imagePullPolicy': 'Never',
             'command': ['etcd', '--name=empty', '--data-dir=/tools/empty',
                '--listen-client-urls=http://127.0.0.1:12379',
                '--advertise-client-urls=http://127.0.0.1:12379',
                '--listen-peer-urls=http://127.0.0.1:12380',
                '--initial-advertise-peer-urls=http://127.0.0.1:12380',
                '--initial-cluster=empty=http://127.0.0.1:12380',
                '--log-outputs=/dev/null'],
             'securityContext': copy.deepcopy(SC),
             'resources': {'requests': {'cpu': '100m', 'memory': '128Mi'},
                           'limits': {'cpu': '1', 'memory': '1Gi'}},
             'volumeMounts': copy.deepcopy(shared)}],
        'volumes': [{'name': 'proof', 'emptyDir': {'medium': 'Memory', 'sizeLimit': '1536Mi'}},
                    {'name': 'tools', 'emptyDir': {'medium': 'Memory', 'sizeLimit': '256Mi'}},
                    {'name': 'program', 'configMap': {'name': name, 'defaultMode': 292}}]}}
    api = api_container()
    return {'configmap': cm, 'policy': policy, 'pod': pod, 'ephemeral_api': api}

def api_container():
    return {'name': 'api', 'image': API_IMAGE, 'imagePullPolicy': 'Never',
           'securityContext': dict(copy.deepcopy(SC), capabilities={'drop': ['ALL'], 'add': ['NET_BIND_SERVICE']}),
           'volumeMounts': [{'name': 'proof', 'mountPath': '/memory-proof', 'readOnly': True}],
           'command': ['/go-runner', '--log-file=/dev/null', '--also-stdout=false',
               '--redirect-stderr=true', '/usr/local/bin/kube-apiserver',
               '--bind-address=127.0.0.1', '--advertise-address=127.0.0.1',
               '--secure-port=16443', '--etcd-servers=http://127.0.0.1:32379',
               '--etcd-compaction-interval=0s', '--endpoint-reconciler-type=none',
               '--authorization-mode=Node,RBAC', '--enable-admission-plugins=NodeRestriction',
               '--client-ca-file=/memory-proof/proof/ca.crt', '--tls-cert-file=/memory-proof/proof/apiserver.crt',
               '--tls-private-key-file=/memory-proof/proof/apiserver.key',
               '--service-account-issuer=https://kubernetes.default.svc.cluster.local',
               '--service-account-key-file=/memory-proof/proof/sa.pub',
               '--service-account-signing-key-file=/memory-proof/proof/sa.key',
               '--service-cluster-ip-range=10.96.0.0/12',
               '--encryption-provider-config=/memory-proof/proof/encryption-config.json', '--v=0']}

SNAPSHOT_STATUS = ['etcdutl', '--write-out=json', 'snapshot', 'status', '/proof/snapshot.db']
RESTORE = ['etcdutl', 'snapshot', 'restore', '/proof/snapshot.db',
           '--data-dir=/proof/restored', '--name=proof',
           '--initial-cluster=proof=http://127.0.0.1:32380',
           '--initial-advertise-peer-urls=http://127.0.0.1:32380',
           '--initial-cluster-token=bortus-isolated-api-proof']
RESTORED_ETCD = ['etcd', '--name=proof', '--data-dir=/proof/restored',
    '--listen-client-urls=http://127.0.0.1:32379',
    '--advertise-client-urls=http://127.0.0.1:32379',
    '--listen-peer-urls=http://127.0.0.1:32380',
    '--initial-advertise-peer-urls=http://127.0.0.1:32380',
    '--initial-cluster=proof=http://127.0.0.1:32380',
    '--initial-cluster-token=bortus-isolated-api-proof', '--log-outputs=/dev/null']
REGISTRY = ['etcdctl', '--endpoints=http://127.0.0.1:32379',
            '--write-out=json', 'get', '/registry/secrets/', '--prefix']

def _need(value):
    if not value:
        raise ValueError('API recovery resource refused')

def _exact(expected, actual, depth=0):
    if depth > 64 or type(expected) is not type(actual):
        return False
    if type(expected) is dict:
        return set(expected) == set(actual) and all(_exact(v, actual[k], depth + 1) for k, v in expected.items())
    if type(expected) is list:
        return len(expected) == len(actual) and all(_exact(a, b, depth + 1) for a, b in zip(expected, actual))
    return type(expected) in (str, int, bool, type(None)) and expected == actual

def _identity(obj):
    m = obj.get('metadata')
    _need(type(m) is dict and not m.get('deletionTimestamp'))
    result = {k: m.get(k) for k in ('name', 'namespace', 'uid', 'resourceVersion')}
    _need(all(type(result[k]) is str and re.fullmatch('[A-Za-z0-9_.:-]{1,253}', result[k])
              for k in ('name', 'uid', 'resourceVersion')) and result['namespace'] == NS)
    return result

def _known_absent_defaults(expected, actual, values):
    for key, value in values.items():
        if key not in expected and key in actual:
            _need(type(actual[key]) is type(value) and actual[key] == value)
            del actual[key]

def _container_defaults(expected, actual):
    _known_absent_defaults(expected, actual, {
        'terminationMessagePath': '/dev/termination-log', 'terminationMessagePolicy': 'File'})

def _pod_spec(expected, actual):
    _need(type(actual) is dict)
    actual = copy.deepcopy(actual)
    _known_absent_defaults(expected, actual, {
        'dnsPolicy': 'ClusterFirst', 'schedulerName': 'default-scheduler',
        'preemptionPolicy': 'PreemptLowerPriority', 'priority': 0,
        'serviceAccountName': 'default', 'serviceAccount': 'default',
        'hostNetwork': False, 'hostPID': False, 'hostIPC': False})
    tolerations = [
        {'key': 'node.kubernetes.io/not-ready', 'operator': 'Exists',
         'effect': 'NoExecute', 'tolerationSeconds': 300},
        {'key': 'node.kubernetes.io/unreachable', 'operator': 'Exists',
         'effect': 'NoExecute', 'tolerationSeconds': 300}]
    if 'tolerations' not in expected and 'tolerations' in actual:
        values = actual['tolerations']
        _need(type(values) is list and len(values) == 2 and
              all(type(v) is dict and type(v.get('tolerationSeconds')) is int for v in values) and
              (values == tolerations or values == list(reversed(tolerations))))
        del actual['tolerations']
    for key in ('initContainers', 'containers', 'ephemeralContainers'):
        if key not in expected:
            _need(key not in actual)
            continue
        _need(type(actual.get(key)) is list and len(actual[key]) == len(expected[key]))
        for wanted, observed in zip(expected[key], actual[key]):
            _need(type(observed) is dict)
            _container_defaults(wanted, observed)
            if key == 'ephemeralContainers':
                _known_absent_defaults(wanted, observed, {'resources': {}})
    _need(_exact(expected, actual))

def _status_matches(proposal, obj):
    status = obj.get('status')
    _need(type(status) is dict and status.get('phase') == 'Running')
    for source, field, completed in (
        ('initContainers', 'initContainerStatuses', True),
        ('containers', 'containerStatuses', False),
        ('ephemeralContainers', 'ephemeralContainerStatuses', False)):
        expected = proposal['spec'].get(source, [])
        observed = status.get(field, [])
        _need(type(observed) is list and len(observed) == len(expected))
        wanted = {v['name']: v for v in expected}
        seen = set()
        for current in observed:
            _need(type(current) is dict and current.get('name') in wanted and current['name'] not in seen)
            seen.add(current['name'])
            image = wanted[current['name']]['image']
            _need(current.get('imageID') == image and type(current.get('image')) is str and
                  0 < len(current['image']) <= 1024)
            _need(type(current.get('restartCount')) is int and current['restartCount'] == 0)
            state = current.get('state')
            _need(type(state) is dict and set(state) == ({'terminated'} if completed else {'running'}))
            if completed:
                _need(type(state['terminated']) is dict and
                      type(state['terminated'].get('exitCode')) is int and state['terminated']['exitCode'] == 0)
            else:
                _need(type(state['running']) is dict)
                if source == 'containers':
                    _need(current.get('ready') is True)

def _matches(proposal, obj, expected_uid, runtime):
    _need(type(proposal) is dict and type(obj) is dict and
          obj.get('apiVersion') == proposal.get('apiVersion') and obj.get('kind') == proposal.get('kind'))
    i = _identity(obj)
    m = obj['metadata']
    _need(i['name'] == proposal['metadata']['name'] and
          m.get('labels') == proposal['metadata']['labels'] and not m.get('ownerReferences'))
    if expected_uid is not None:
        _need(type(expected_uid) is str and i['uid'] == expected_uid)
    if proposal['kind'] == 'Pod':
        _pod_spec(proposal['spec'], obj.get('spec'))
        if runtime:
            _status_matches(proposal, obj)
    elif proposal['kind'] == 'NetworkPolicy':
        _need(_exact(proposal['spec'], obj.get('spec')) and runtime is False)
    elif proposal['kind'] == 'ConfigMap':
        _need(obj.get('immutable') is True and obj.get('data') == proposal['data'] and
              'binaryData' not in obj and runtime is False)
    else:
        _need(False)
    return i

def matches(proposal, obj, expected_uid=None, *, runtime=False):
    """Persistent full resource match; fresh RV opaque, UID never repinned.

    No dry-run absent-RV exception; raw arguments are dropped at public refusal.
    Only exact known absent API defaults normalize. This is local preparation,
    not evidence of current server defaulting or actual runtime/cache presence.
    """
    result = None
    failed = False
    try:
        _need(type(runtime) is bool)
        result = _matches(proposal, obj, expected_uid, runtime)
    except Exception:
        failed = True
    if failed:
        proposal = obj = expected_uid = result = None
        raise ValueError('API recovery resource refused') from None
    return result

def ephemeral_update(base_proposal, current, api, expected_uid):
    """Pure fixed PUT body; caller owns durable intent and actual CAS outcome."""
    identity = matches(base_proposal, current, expected_uid, runtime=True)
    _need(type(api) is dict and _exact(api_container(), api))
    body = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': identity,
            'spec': copy.deepcopy(current['spec'])}
    _need('ephemeralContainers' not in body['spec'])
    body['spec']['ephemeralContainers'] = [copy.deepcopy(api)]
    final = copy.deepcopy(base_proposal)
    final['spec']['ephemeralContainers'] = [copy.deepcopy(api)]
    path = '/api/v1/namespaces/migration-system/pods/' + identity['name'] + '/ephemeralcontainers'
    return path, body, final
