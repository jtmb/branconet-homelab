#!/usr/bin/env python3
"""Pure Longhorn v1 restored-consumer metadata fence; no IO or data acceptance."""
import ipaddress
import re
import urllib.parse
from typing import NamedTuple

API = 'longhorn.io/v1beta2'
ENGINE_IMAGE = 'docker.io/longhornio/longhorn-engine:v1.12.1'
SIZE = '1073741824'
MAX_ITEMS = 10000
MAX_NODES = 400000
MAX_TEXT = 16 * 1024 * 1024


class Refused(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__('Restored consumer metadata refused: ' + code)


def need(ok, code):
    if not ok:
        raise Refused(code)


def bounded(value):
    """Built-in JSON trees only; bound traversal before inspecting private fields."""
    nodes = chars = 0
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        nodes += 1
        need(nodes <= MAX_NODES and depth <= 24, 'input_bound')
        t = type(item)
        if t is str:
            chars += len(item)
            need(len(item) <= 65536 and chars <= MAX_TEXT, 'input_bound')
        elif t is dict:
            need(len(item) <= MAX_ITEMS, 'input_bound')
            for key, val in item.items():
                need(type(key) is str, 'input_shape')
                stack.append((key, depth + 1))
                stack.append((val, depth + 1))
        elif t is list:
            need(len(item) <= MAX_ITEMS, 'input_bound')
            stack.extend((val, depth + 1) for val in item)
        else:
            need(t in (int, bool, type(None)) and (t is not int or abs(item) < 2**64),
                 'input_shape')


def text(value, cap=256):
    need(type(value) is str and 0 < len(value) <= cap and
         all(32 < ord(c) < 127 for c in value), 'identity')
    return value


def name(value):
    text(value, 253)
    need(re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', value) is not None, 'identity')
    return value


class Identity(NamedTuple):
    name: str
    uid: str
    namespace: str | None
    resource_version: str


class Eligibility(NamedTuple):
    claim: Identity
    pv: Identity
    volume: Identity
    backup: Identity
    holder: Identity
    engine: Identity
    replicas: tuple[Identity, Identity]
    node: Identity
    collection_resource_versions: tuple[str, str, str, str]
    metadata_eligible: bool = True
    runtime_acceptance: bool = False
    data_acceptance: bool = False
    atomic_snapshot: bool = False


def identity(obj, namespace):
    need(type(obj) is dict and type(obj.get('metadata')) is dict, 'identity')
    meta = obj['metadata']
    need(meta.get('namespace') in ((None, '') if namespace is None else (namespace,)), 'identity')
    need(not meta.get('deletionTimestamp'), 'deleting')
    uid = text(meta.get('uid'), 36)
    need(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', uid) is not None, 'identity')
    return Identity(name(meta.get('name')), uid, namespace, text(meta.get('resourceVersion')))


def expected_id(value, namespace):
    need(type(value) is dict and set(value) == {'name', 'uid', 'namespace'}, 'expectation')
    return identity({'metadata': dict(value, resourceVersion='expected')}, namespace)


def matches(actual, expected):
    need(actual[:3] == expected[:3], 'identity_drift')


def collection(value, api, kind, namespace):
    need(type(value) is dict and value.get('apiVersion') == api and
         value.get('kind') == kind + 'List' and type(value.get('metadata')) is dict,
         'collection')
    meta = value['metadata']
    rv = text(meta.get('resourceVersion'))
    need(meta.get('continue', '') == '' and
         ('remainingItemCount' not in meta or
          type(meta['remainingItemCount']) is int and meta['remainingItemCount'] == 0), 'incomplete')
    items = value.get('items')
    need(type(items) is list and len(items) <= MAX_ITEMS, 'collection')
    names, uids = set(), set()
    for obj in items:
        need(type(obj) is dict and obj.get('apiVersion', api) == api and
             obj.get('kind', kind) == kind, 'collection')
        # Deleting unrelated objects still count as possible aliases/consumers.
        meta_obj = obj.get('metadata')
        need(type(meta_obj) is dict, 'collection')
        ident = identity({'metadata': {k: v for k, v in meta_obj.items()
                                     if k != 'deletionTimestamp'}}, namespace)
        need(ident.name not in names and ident.uid not in uids and
             type(obj.get('spec')) is dict, 'collection')
        names.add(ident.name)
        uids.add(ident.uid)
    return items, rv


def owner(obj, volume):
    refs = obj['metadata'].get('ownerReferences')
    need(type(refs) is list and len(refs) == 1 and type(refs[0]) is dict, 'owner')
    ref = refs[0]
    need(ref.get('apiVersion') == API and ref.get('kind') == 'Volume' and
         ref.get('name') == volume.name and ref.get('uid') == volume.uid, 'owner')


def instance(obj, kind, volume):
    ident = identity(obj, 'longhorn-system')
    need(obj.get('apiVersion') == API and obj.get('kind') == kind, 'instance')
    owner(obj, volume)
    spec, status = obj.get('spec', {}), obj.get('status', {})
    need(spec.get('active') is True and spec.get('volumeName') == volume.name and
         spec.get('volumeSize') == SIZE and spec.get('dataEngine') == 'v1' and
         spec.get('image') == ENGINE_IMAGE and status.get('currentState') == 'running' and
         status.get('currentImage') == ENGINE_IMAGE and status.get('started') is True,
         'instance')
    need(not spec.get('failedAt'), 'instance')
    conditions_ok(status)
    name(spec.get('nodeID'))
    return ident


def relevant(items, volume):
    result = []
    for obj in items:
        refs = obj['metadata'].get('ownerReferences', [])
        need(type(refs) is list and len(refs) <= 8 and all(type(r) is dict for r in refs), 'owner')
        if obj['spec'].get('volumeName') == volume.name or any(
                r.get('uid') == volume.uid for r in refs):
            result.append(obj)
    return result


def holder_spec(image, claim, node):
    """Exact inert proposal: approved metadata only, no application entrypoint."""
    return {'nodeName': node, 'automountServiceAccountToken': False, 'restartPolicy': 'Never',
        'securityContext': {'runAsNonRoot': True, 'runAsUser': 1000, 'runAsGroup': 1000,
                            'seccompProfile': {'type': 'RuntimeDefault'}},
        'containers': [{'name': 'holder', 'image': image, 'imagePullPolicy': 'Never',
            'command': ['node', '-e', 'setInterval(()=>{},1000)'],
            'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                                'capabilities': {'drop': ['ALL']}},
            'resources': {'requests': {'cpu': '5m', 'memory': '32Mi'},
                          'limits': {'cpu': '100m', 'memory': '128Mi'}},
            'volumeMounts': [{'name': 'data', 'mountPath': '/data', 'readOnly': True}]}],
        'volumes': [{'name': 'data', 'persistentVolumeClaim': {'claimName': claim, 'readOnly': True}}]}


def strict_equal(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return a.keys() == b.keys() and all(strict_equal(a[k], b[k]) for k in a)
    if type(a) is list:
        return len(a) == len(b) and all(strict_equal(x, y) for x, y in zip(a, b))
    return a == b


def ready(status):
    conditions = status.get('conditions')
    need(type(conditions) is list and len(conditions) <= 32 and
         all(type(c) is dict for c in conditions), 'readiness')
    selected = [c for c in conditions if c.get('type') == 'Ready']
    return len(selected) == 1 and selected[0].get('status') == 'True'


def conditions_ok(status):
    conditions = status.get('conditions', [])
    if conditions is None:
        conditions = []
    need(type(conditions) is list and len(conditions) <= 32, 'conditions')
    seen = set()
    for c in conditions:
        need(type(c) is dict and type(c.get('type')) is str and
             0 < len(c['type']) <= 128 and c['type'] not in seen and
             c.get('status') in ('True', 'False', 'Unknown'), 'conditions')
        seen.add(c['type'])
        need(not (c['type'] == 'Restore' and c.get('reason') == 'RestoreFailure'), 'restore_failure')


def holder_matches(pod, image, claim, node, require_ready=True):
    """Pure exact inert spec; readiness is separately mandatory before any reader."""
    failure = None
    value = None
    try:
        bounded(pod)
        need(type(require_ready) is bool and type(pod) is dict and
             pod.get('apiVersion') == 'v1' and pod.get('kind') == 'Pod' and
             type(pod.get('spec')) is dict, 'holder')
        identity(pod, 'bortus')
        text(image, 512)
        need(re.fullmatch(r'[A-Za-z0-9.:/_-]+@sha256:[0-9a-f]{64}', image) is not None and
             ':' not in image.split('@')[0].rsplit('/', 1)[-1] and '://' not in image, 'holder')
        name(claim)
        name(node)
        value = _holder_matches(pod, image, claim, node, require_ready)
    except Refused as error:
        failure = error.code
    except Exception:
        failure = 'holder'
    if failure:
        raise Refused(failure)
    return value


def _holder_matches(pod, image, claim, node, require_ready):
    # API defaulted benign fields are allowed only with their exact inert defaults.
    import copy
    spec = copy.deepcopy(pod['spec'])
    for key, value in {'dnsPolicy': 'ClusterFirst', 'schedulerName': 'default-scheduler',
        'terminationGracePeriodSeconds': 30, 'enableServiceLinks': True,
        'serviceAccountName': 'default', 'serviceAccount': 'default',
        'preemptionPolicy': 'PreemptLowerPriority', 'priority': 0}.items():
        if key in spec:
            need(type(spec[key]) is type(value) and spec.pop(key) == value, 'holder')
    if 'tolerations' in spec:
        need(strict_equal(spec.pop('tolerations'), [
            {'key': 'node.kubernetes.io/not-ready', 'operator': 'Exists',
             'effect': 'NoExecute', 'tolerationSeconds': 300},
            {'key': 'node.kubernetes.io/unreachable', 'operator': 'Exists',
             'effect': 'NoExecute', 'tolerationSeconds': 300}]), 'holder')
    for container in spec.get('containers', []):
        for key, value in {'terminationMessagePath': '/dev/termination-log',
                           'terminationMessagePolicy': 'File'}.items():
            if key in container:
                need(container.pop(key) == value, 'holder')
    need(strict_equal(spec, holder_spec(image, claim, node)), 'holder')
    need(not pod['metadata'].get('ownerReferences'), 'holder')
    if not require_ready:
        return identity(pod, 'bortus')
    status = pod.get('status', {})
    need(status.get('phase') == 'Running' and ready(status), 'holder')
    cs = status.get('containerStatuses')
    need(type(cs) is list and len(cs) == 1 and cs[0].get('name') == 'holder' and
         cs[0].get('ready') is True and type(cs[0].get('state', {}).get('running')) is dict and
         cs[0].get('image') == image and type(cs[0].get('restartCount')) is int and
         cs[0]['restartCount'] == 0, 'holder')
    return identity(pod, 'bortus')


def evaluate(expected, objects):
    try:
        return _evaluate(expected, objects)
    except (KeyError, TypeError, AttributeError, IndexError):
        raise Refused('input_shape') from None


def _evaluate(expected, objects):
    """Expected identities/source/image must be independently trusted by the caller."""
    bounded(expected)
    bounded(objects)
    need(type(expected) is dict and set(expected) == {'original_claim', 'original_pv',
        'original_volume', 'claim', 'pv', 'volume', 'backup', 'backup_url', 'holder',
        'holder_image', 'original_node', 'node', 'longhorn_version'}, 'expectation')
    need(expected['longhorn_version'] == '1.12.1', 'compatibility')
    need(type(objects) is dict and set(objects) == {'claim', 'pv', 'volume', 'backup',
        'node', 'pvs', 'pods', 'engines', 'replicas'}, 'input_shape')
    ids = {k: expected_id(expected[k], ns) for k, ns in (
        ('original_claim', 'bortus'), ('original_pv', None), ('original_volume', 'longhorn-system'),
        ('claim', 'bortus'), ('pv', None), ('volume', 'longhorn-system'),
        ('backup', 'longhorn-system'), ('holder', 'bortus'), ('node', None))}
    for key in ('claim', 'pv', 'volume'):
        need(ids[key].uid != ids['original_' + key].uid and
             ids[key].name != ids['original_' + key].name, 'not_independent')
    need(len({i.uid for i in ids.values()}) == len(ids), 'identity')
    need(ids['node'].name != name(expected['original_node']), 'placement')
    image = text(expected['holder_image'], 512)
    need(re.fullmatch(r'[A-Za-z0-9.:/_-]+@sha256:[0-9a-f]{64}', image) is not None and
         ':' not in image.split('@')[0].rsplit('/', 1)[-1] and '://' not in image, 'holder')
    url = text(expected['backup_url'], 1024)
    try:
        parts = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qs(parts.query, strict_parsing=True,
                                     keep_blank_values=True, max_num_fields=2)
    except ValueError:
        raise Refused('source') from None
    need(parts.scheme == 'cifs' and parts.netloc == '192.168.0.8' and not parts.fragment and
         '#' not in url and parts.path == '/container_backups/k8s-migration-20261009/longhorn' and
         query == {'backup': [ids['backup'].name], 'volume': [ids['original_volume'].name]}, 'source')
    actual = {k: identity(objects[k], ids[k].namespace) for k in
              ('claim', 'pv', 'volume', 'backup', 'node')}
    for key, ident in actual.items():
        matches(ident, ids[key])
    claim, pv, vol, backup, node = (objects[k] for k in ('claim', 'pv', 'volume', 'backup', 'node'))
    need(claim.get('apiVersion') == 'v1' and claim.get('kind') == 'PersistentVolumeClaim' and
         claim.get('status', {}).get('phase') == 'Bound' and
         claim['spec'].get('volumeName') == actual['pv'].name and
         claim['spec'].get('accessModes') == ['ReadWriteOnce'] and
         claim['spec'].get('resources', {}).get('requests', {}).get('storage') == '1Gi', 'mapping')
    ps = pv.get('spec', {})
    ref, csi = ps.get('claimRef', {}), ps.get('csi', {})
    need(pv.get('apiVersion') == 'v1' and pv.get('kind') == 'PersistentVolume' and
         pv.get('status', {}).get('phase') == 'Bound' and ps.get('capacity', {}).get('storage') == '1Gi' and
         ps.get('persistentVolumeReclaimPolicy') == 'Retain' and
         all(ref.get(k) == v for k, v in zip(('name', 'uid', 'namespace'), actual['claim'][:3])) and
         csi.get('driver') == 'driver.longhorn.io' and csi.get('volumeHandle') == actual['volume'].name,
         'mapping')
    vs, st = vol.get('spec', {}), vol.get('status', {})
    conditions_ok(st)
    need(vol.get('apiVersion') == API and vol.get('kind') == 'Volume' and
         vs.get('fromBackup') == url and vs.get('encrypted') is True and
         type(vs.get('numberOfReplicas')) is int and vs['numberOfReplicas'] == 2 and
         vs.get('size') == SIZE and vs.get('dataEngine') == 'v1' and
         vs.get('Standby') is False and 'standby' not in vs and
         st.get('isStandby') is False and st.get('state') == 'attached' and
         st.get('robustness') == 'healthy' and st.get('currentImage') == ENGINE_IMAGE and
         st.get('restoreInitiated') is True and st.get('restoreRequired') is False and
         vs.get('nodeID') == st.get('currentNodeID') == actual['node'].name, 'volume')
    bs = backup.get('status', {})
    need(backup.get('apiVersion') == API and backup.get('kind') == 'Backup' and
         bs.get('state') == 'Completed' and not bs.get('error') and bs.get('url') == url and
         bs.get('volumeName') == ids['original_volume'].name and bs.get('volumeSize') == SIZE and
         bs.get('backupTargetName') == 'default', 'source')
    need(node.get('apiVersion') == 'v1' and node.get('kind') == 'Node' and
         node.get('spec', {}).get('unschedulable', False) is False and
         ready(node.get('status', {})), 'placement')
    pvs, prv = collection(objects['pvs'], 'v1', 'PersistentVolume', None)
    aliases = []
    for obj in pvs:
        cs = obj['spec'].get('csi')
        if cs is not None:
            need(type(cs) is dict, 'collection')
            text(cs.get('driver'), 253)
            text(cs.get('volumeHandle'), 253)
            if cs['driver'] == 'driver.longhorn.io' and cs['volumeHandle'] == actual['volume'].name:
                aliases.append(obj)
    need(len(aliases) == 1 and identity(aliases[0], None) == actual['pv'], 'pv_alias')
    engines, erv = collection(objects['engines'], API, 'Engine', 'longhorn-system')
    replicas, rrv = collection(objects['replicas'], API, 'Replica', 'longhorn-system')
    engines, replicas = relevant(engines, actual['volume']), relevant(replicas, actual['volume'])
    need(len(engines) == 1 and len(replicas) == 2, 'instances')
    engine = engines[0]
    eid = instance(engine, 'Engine', actual['volume'])
    need(eid.uid not in {i.uid for i in ids.values()}, 'identity')
    need(engine['spec']['nodeID'] == actual['node'].name, 'placement')
    replica_ids, addresses = [], {}
    for obj in replicas:
        rid = instance(obj, 'Replica', actual['volume'])
        rs, rst = obj['spec'], obj['status']
        need(rs.get('engineName') == eid.name and rs.get('failedAt') == '' and
             type(rs.get('healthyAt')) is str and 0 < len(rs['healthyAt']) <= 64, 'replica')
        try:
            ipaddress.ip_address(text(rst.get('ip'), 45))
            host = text(rst.get('storageIP'), 45)
            ipaddress.ip_address(host)
        except ValueError:
            raise Refused('replica_address') from None
        port = rst.get('port')
        need(type(port) is int and 0 < port <= 65535, 'replica_address')
        addresses[rid.name] = ('[' + host + ']' if ':' in host else host) + ':' + str(port)
        replica_ids.append(rid)
    need(len({eid.uid, *(r.uid for r in replica_ids)}) == 3 and
         all(r.uid not in {i.uid for i in ids.values()} for r in replica_ids), 'identity')
    need(len(set(addresses.values())) == 2 and
         engine['spec'].get('replicaAddressMap') == addresses and
         engine['status'].get('currentReplicaAddressMap') == addresses and
         engine['status'].get('replicaModeMap') == {key: 'RW' for key in addresses}, 'replica_map')
    pods, porv = collection(objects['pods'], 'v1', 'Pod', 'bortus')
    consumers = []
    for pod in pods:
        volumes = pod['spec'].get('volumes', [])
        need(type(volumes) is list and all(type(v) is dict for v in volumes), 'consumer')
        if any(type(v.get('persistentVolumeClaim')) is dict and
               v['persistentVolumeClaim'].get('claimName') == actual['claim'].name for v in volumes):
            if pod.get('status', {}).get('phase') not in ('Succeeded', 'Failed'):
                consumers.append(pod)
    need(len(consumers) == 1, 'consumer')
    pod = consumers[0]
    hid = identity(pod, 'bortus')
    matches(hid, ids['holder'])
    holder_matches(pod, image, actual['claim'].name, actual['node'].name)
    return Eligibility(actual['claim'], actual['pv'], actual['volume'], actual['backup'], hid,
        eid, tuple(sorted(replica_ids)), actual['node'], (prv, porv, erv, rrv))
