"""Callable bounded guard observation and owned probes; permanent guards stay Flux-owned."""
import copy
import hashlib
import http.client
import importlib.util
import json
import math
import os
import pathlib
import re
import ssl
import stat
import sys
import time
import uuid
from typing import NamedTuple


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module); return module


validator = load('operator_admission_validator', 'bortus-admission-qualification.py')
source = load('operator_admission_source', 'bortus-restore-source.py')
metadata = source.metadata
APPROVED_ORIGIN = metadata.APPROVED_ORIGIN
MAX_BODY = 1024 * 1024
MAX_RESPONSE = 8 * 1024 * 1024
MESSAGE = 'BORTUS protected identity, metadata claim or credential references require approved compatible immutable images in every container with pullPolicy Never.'
WORKLOADS = {'Pod': ('v1', '/api/v1/namespaces/bortus/pods'),
    'Deployment': ('apps/v1', '/apis/apps/v1/namespaces/bortus/deployments'),
    'StatefulSet': ('apps/v1', '/apis/apps/v1/namespaces/bortus/statefulsets'),
    'DaemonSet': ('apps/v1', '/apis/apps/v1/namespaces/bortus/daemonsets'),
    'ReplicaSet': ('apps/v1', '/apis/apps/v1/namespaces/bortus/replicasets'),
    'ReplicationController': ('v1', '/api/v1/namespaces/bortus/replicationcontrollers'),
    'Job': ('batch/v1', '/apis/batch/v1/namespaces/bortus/jobs'),
    'CronJob': ('batch/v1', '/apis/batch/v1/namespaces/bortus/cronjobs')}
GUARDS = {validator.POLICY: '/apis/admissionregistration.k8s.io/v1/validatingadmissionpolicies',
          validator.BINDING: '/apis/admissionregistration.k8s.io/v1/validatingadmissionpolicybindings'}
FAILURES = ('configuration', 'deadline', 'source', 'publication', 'guard', 'ownership',
    'transport', 'response', 'probe', 'attribution', 'fixture', 'uncertain', 'cleanup')


class OperatorRefused(RuntimeError):
    def __init__(self, code):
        self.code = code if type(code) is str and code in FAILURES else 'configuration'
        super().__init__('Admission operator refused: ' + self.code)


def need(value, code):
    if not value: raise OperatorRefused(code)


def alive(deadline):
    now = time.monotonic()
    need(type(deadline) in (int, float) and math.isfinite(deadline) and now < deadline <= now + 300, 'deadline')


def selected(obj, *, allow_deleting=False):
    m = obj.get('metadata') if type(obj) is dict else None
    need(type(m) is dict and metadata.valid_name(m.get('name')) and validator.uid(m.get('uid')) and
        metadata.text(m.get('resourceVersion')) and m.get('namespace') == 'bortus' and
        (allow_deleting or not m.get('deletionTimestamp')), 'fixture')
    return {k: m[k] for k in ('name', 'namespace', 'uid', 'resourceVersion')}


class API:
    """Fixed BORTUS workload and guard routes, fresh TLS, no retries or Secret paths."""
    def __init__(self, options, *, origin=APPROVED_ORIGIN):
        from urllib.parse import urlsplit
        need(origin == APPROVED_ORIGIN and callable(options), 'configuration')
        p = urlsplit(origin); need(p.scheme == 'https', 'configuration')
        self.host, self.port, self.options = p.hostname, p.port or 443, options

    def _exchange(self, method, path, body, deadline):
        connection = response = socket = headers = raw = obj = None
        result, failure = None, None
        try:
            alive(deadline)
            context, headers = self.options()
            need(type(context) is ssl.SSLContext and context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED and
                context.minimum_version >= ssl.TLSVersion.TLSv1_2 and type(headers) is dict and set(headers) <= {'Authorization'} and
                all(metadata.text(v, 16384) and all(32 <= ord(c) < 127 for c in v) for v in headers.values()), 'transport')
            encoded = None if body is None else validator.canonical(body)
            need(encoded is None or len(encoded) <= MAX_BODY, 'probe')
            connection = http.client.HTTPSConnection(self.host, self.port, context=context, timeout=min(30, deadline - time.monotonic()))
            connection.connect(); socket = connection.sock
            need(isinstance(socket, ssl.SSLSocket) and socket.getpeercert() and socket.version() in ('TLSv1.2', 'TLSv1.3'), 'transport')
            alive(deadline); socket.settimeout(min(30, deadline - time.monotonic()))
            connection.request(method, path, body=encoded, headers={'Accept': 'application/json', 'Accept-Encoding': 'identity',
                'Content-Type': 'application/json', **headers}); headers = None
            alive(deadline); socket.settimeout(min(30, deadline - time.monotonic())); response = connection.getresponse()
            need(response.getheader('Content-Type', '').split(';', 1)[0].strip() == 'application/json' and
                response.getheader('Content-Encoding', 'identity') == 'identity', 'response')
            declared = response.getheader('Content-Length')
            need(declared is None or (declared.isascii() and declared.isdecimal() and int(declared) <= MAX_RESPONSE), 'response')
            parts, count = [], 0
            while True:
                alive(deadline); socket.settimeout(min(30, deadline - time.monotonic()))
                block = response.read1(min(65536, MAX_RESPONSE - count + 1)); count += len(block)
                alive(deadline); need(count <= MAX_RESPONSE, 'response')
                if not block: break
                parts.append(block)
                if response.isclosed(): break
            need(declared is None or count == int(declared), 'response')
            raw = b''.join(parts); obj = metadata.bounded_json(raw); alive(deadline)
            result = (response.status, obj)
        except OperatorRefused as error: failure = error.code
        except Exception: failure = 'transport'
        finally:
            for owned in (response, connection):
                if owned is not None:
                    try: owned.close()
                    except Exception: failure = 'cleanup'
            headers = raw = obj = None
        return (None if failure else result), failure

    def _call(self, method, path, body, deadline):
        result, failure = self._exchange(method, path, body, deadline)
        if failure:
            method = path = body = deadline = result = None
            raise OperatorRefused(failure)
        return result

    def _guard(self, kind, name, *, deadline):
        need(kind in GUARDS and name in {'bortus-kv-guard-' + v[0] for v in validator.VARIANTS}, 'guard')
        code, value = self._call('GET', GUARDS[kind] + '/' + name, None, deadline)
        need(code == 200, 'guard'); return value

    def _workload(self, method, kind, name=None, body=None, *, deadline, dry_run=False, subresource=''):
        need(kind in WORKLOADS and method in ('GET', 'POST', 'PUT', 'DELETE') and type(dry_run) is bool, 'probe')
        need(name is None or (metadata.valid_name(name) and re.fullmatch('bortus-admission-[0-9a-f]{12}-(?:pod|deployment|case-[0-9]+)', name)), 'probe')
        need(subresource == '' or (kind == 'Pod' and method == 'PUT' and subresource == 'ephemeralcontainers' and dry_run), 'probe')
        need(dry_run or kind in ('Pod', 'Deployment'), 'probe')
        need((method == 'POST' and name is None) or method != 'POST', 'probe')
        need(method != 'DELETE' or (not dry_run and name is not None and type(body) is dict and
            set(body) == {'apiVersion', 'kind', 'preconditions'} and body['apiVersion'] == 'v1' and body['kind'] == 'DeleteOptions' and
            type(body['preconditions']) is dict and set(body['preconditions']) == {'uid', 'resourceVersion'} and
            validator.uid(body['preconditions']['uid']) and metadata.text(body['preconditions']['resourceVersion'])), 'probe')
        if method in ('POST', 'PUT'):
            need(type(body) is dict and body.get('apiVersion') == WORKLOADS[kind][0] and body.get('kind') == kind and
                type(body.get('metadata')) is dict and body['metadata'].get('namespace') == 'bortus' and
                (name is None or body['metadata'].get('name') == name) and
                re.fullmatch('bortus-admission-[0-9a-f]{12}-(?:pod|deployment|case-[0-9]+)', body['metadata'].get('name', '')), 'probe')
        path = WORKLOADS[kind][1] + (('/' + name) if name else '') + (('/' + subresource) if subresource else '')
        if dry_run: path += '?dryRun=All&fieldValidation=Strict'
        return self._call(method, path, body, deadline)

    def guard(self, kind, name, *, deadline):
        result, failure = None, None
        try: result = self._guard(kind, name, deadline=deadline)
        except OperatorRefused as error: failure = error.code
        except Exception: failure = 'guard'
        if failure:
            kind = name = deadline = result = None
            raise OperatorRefused(failure)
        return result

    def workload(self, method, kind, name=None, body=None, *, deadline, dry_run=False, subresource=''):
        result, failure = None, None
        try: result = self._workload(method, kind, name, body, deadline=deadline,
                                    dry_run=dry_run, subresource=subresource)
        except OperatorRefused as error: failure = error.code
        except Exception: failure = 'probe'
        if failure:
            method = kind = name = body = deadline = result = None
            raise OperatorRefused(failure)
        return result


def idle_spec(image, node, *, reference=None, guarded=True):
    spec = {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
        'serviceAccountName': 'bortus-kv' if guarded else 'default', 'nodeName': node,
        'enableServiceLinks': False, 'terminationGracePeriodSeconds': 1,
        'containers': [{'name': 'holder', 'image': image, 'imagePullPolicy': 'Never',
            'command': ['node', '-e', 'setInterval(()=>{},1000)'],
            'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                'capabilities': {'drop': ['ALL']}}}],
        'securityContext': {'runAsNonRoot': True, 'runAsUser': 1001, 'runAsGroup': 1001,
                            'seccompProfile': {'type': 'RuntimeDefault'}}}
    if reference is not None:
        volume = {'persistentVolumeClaim': {'claimName': reference, 'readOnly': True}} if reference.startswith('bortus-') and reference not in ('bortus-runtime', 'bortus-operator-access') else {'secret': {'secretName': reference}}
        spec['volumes'] = [{'name': 'protected', **volume}]
    return spec


def object_for(kind, name, podspec):
    label = {'bortus-admission-probe': name}
    meta = {'name': name, 'namespace': 'bortus', 'labels': label}
    template = {'metadata': {'labels': label}, 'spec': copy.deepcopy(podspec)}
    if kind == 'Pod': spec = copy.deepcopy(podspec)
    elif kind == 'CronJob': spec = {'schedule': '0 0 * * *', 'jobTemplate': {'spec': {'template': template}}}
    elif kind == 'Job': spec = {'template': template}
    else:
        template['spec']['restartPolicy'] = 'Always'
        spec = {'selector': label if kind == 'ReplicationController' else {'matchLabels': label}, 'template': template}
        if kind != 'DaemonSet': spec['replicas'] = 0
        if kind == 'StatefulSet': spec['serviceName'] = name
    return {'apiVersion': WORKLOADS[kind][0], 'kind': kind, 'metadata': meta, 'spec': spec}


def secret_form(spec, form, secret):
    container = spec['containers'][0]
    if form == 'env': container['env'] = [{'name': 'FIXTURE_REFERENCE', 'valueFrom': {'secretKeyRef': {'name': secret, 'key': 'fixture-key'}}}]
    elif form == 'envFrom': container['envFrom'] = [{'secretRef': {'name': secret}}]
    elif form == 'imagePullSecret': spec['imagePullSecrets'] = [{'name': secret}]
    else:
        volume = {'secret': {'secretName': secret}} if form == 'volume' else (
            {'projected': {'sources': [{'secret': {'name': secret}}]}} if form == 'projected' else None)
        examples = {'azureFile': {'secretName': secret, 'shareName': 'fixture', 'readOnly': True},
            'csi': {'driver': 'fixture.invalid', 'nodePublishSecretRef': {'name': secret}},
            'flexVolume': {'driver': 'fixture/driver', 'secretRef': {'name': secret}},
            'cephfs': {'monitors': ['127.0.0.1:6789'], 'secretRef': {'name': secret}},
            'rbd': {'monitors': ['127.0.0.1:6789'], 'image': 'fixture', 'secretRef': {'name': secret}},
            'iscsi': {'targetPortal': '127.0.0.1:3260', 'iqn': 'iqn.2026-10.invalid:fixture', 'lun': 0, 'secretRef': {'name': secret}},
            'scaleIO': {'gateway': 'https://fixture.invalid', 'system': 'fixture', 'volumeName': 'fixture', 'secretRef': {'name': secret}},
            'storageos': {'volumeName': 'fixture', 'secretRef': {'name': secret}}}
        need(volume is not None or form in examples, 'probe')
        spec['volumes'] = [{'name': 'protected', **(volume if volume is not None else {form: examples[form]})}]


def probe_object(case, name, image, node, contract):
    scenario, reference = case['scenario'], case['protected_reference']
    positive = case['expected_outcome'] == 'allowed'
    spec = idle_spec(image, node, guarded=scenario == 'legacy-new-principal')
    bad = 'fixture.invalid/bortus:unapproved-probe'
    if not positive: spec['containers'][0]['image'] = bad
    if reference in contract['protected_pvc_names']:
        spec['volumes'] = [{'name': 'protected', 'persistentVolumeClaim': {'claimName': reference, 'readOnly': True}}]
    if scenario.startswith('legacy-default-secret-'): secret_form(spec, scenario.removeprefix('legacy-default-secret-'), reference)
    if scenario == 'registry-alias': spec['containers'][0]['image'] = 'alias.invalid/bortus@' + image.split('@', 1)[1]
    if scenario == 'pullPolicy-Always': spec['containers'][0].update(image=image, imagePullPolicy='Always')
    if scenario == 'legacy-init':
        spec['containers'][0]['image'] = image; spec['initContainers'] = [dict(spec['containers'][0], name='old-init', image=bad)]
    if scenario == 'deprecated-serviceAccount-alias':
        spec.pop('serviceAccountName'); spec['serviceAccount'] = 'bortus-kv'
    obj = object_for(case['kind'], name, spec)
    if scenario == 'mutable-tag-label': obj['metadata']['labels'].update({'kv-compatible': 'true', 'guard-exempt': 'true'})
    return obj


def _attributed(code, obj, case, pins):
    """Accept only the exact known validation message in actual v1 Status causes."""
    if case['expected_outcome'] == 'allowed':
        need(200 <= code < 300 and type(obj) is dict and obj.get('kind') == case['kind'] and
            type(obj.get('metadata')) is dict and obj['metadata'].get('namespace') == 'bortus', 'probe')
        return {'http_status': code, 'outcome': 'allowed', 'attribution': None, 'other_failure': None}
    name = 'bortus-kv-guard-' + validator.KINDS[case['kind']]
    message = f"ValidatingAdmissionPolicy '{name}' with binding '{name}' denied request: {MESSAGE}"
    need(code == 403 and type(obj) is dict and obj.get('apiVersion') == 'v1' and obj.get('kind') == 'Status' and
        obj.get('status') == 'Failure' and obj.get('reason') == 'Forbidden' and type(obj.get('code')) is int and obj['code'] == 403 and
        type(obj.get('details')) is dict and type(obj['details'].get('causes')) is list and
        len(obj['details']['causes']) == 1 and type(obj['details']['causes'][0]) is dict and obj['details']['causes'][0].get('message') == message and
        type(obj.get('message')) is str and obj['message'].endswith(message), 'attribution')
    return {'http_status': code, 'outcome': 'guard_denied', 'other_failure': None,
        'attribution': {'source': 'api_guard_rejection', 'reason': 'Forbidden', 'policy_name': name, 'binding_name': name,
            'policy_uid': pins[(validator.POLICY, name)], 'binding_uid': pins[(validator.BINDING, name)], 'validation_index': 0}}


def attributed(code, obj, case, pins):
    result, failure = None, None
    try: result = _attributed(code, obj, case, pins)
    except OperatorRefused as error: failure = error.code
    except Exception: failure = 'attribution'
    if failure:
        code = obj = case = pins = result = None
        raise OperatorRefused(failure)
    return result


class ProbeRun:
    """Exclusive protected durable fixture intents; never reopen or replay."""
    def __init__(self, directory, binding):
        self.path = pathlib.Path(directory); self.fd = self.parent = None
        self.lock_inode = self.record_inode = self.record_bytes = None
        try:
            self.parent = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            p = os.fstat(self.parent)
            need(p.st_uid == os.getuid() and stat.S_IMODE(p.st_mode) == 0o700, 'ownership')
            self.parent_inode = (p.st_dev, p.st_ino)
            os.mkdir(self.path.name, 0o700, dir_fd=self.parent); os.fsync(self.parent)
            self.fd = os.open(self.path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.parent)
            i = os.fstat(self.fd); self.directory_inode = (i.st_dev, i.st_ino)
            fd = self.create('active.lock')
            try:
                self.lock_value = uuid.uuid4().hex.encode(); need(os.write(fd, self.lock_value) == len(self.lock_value), 'ownership'); os.fsync(fd)
                i = os.fstat(fd); self.lock_inode = (i.st_dev, i.st_ino)
            finally: os.close(fd)
            os.fsync(self.fd)
            self.record = {'abi': 1, 'phase': 'pending', 'binding': binding, 'operations': {}, 'outcomes': [],
                'actual_enforcement_accepted': False, 'overall_live_restore_acceptance': False}
            self.save()
        except Exception:
            self.close(); raise

    def check(self):
        need(self.fd is not None and self.parent is not None, 'ownership')
        for path, fd, inode in ((self.path.parent, self.parent, self.parent_inode), (self.path, self.fd, self.directory_inode)):
            a, b = path.lstat(), os.fstat(fd)
            need(stat.S_ISDIR(a.st_mode) and a.st_uid == os.getuid() and stat.S_IMODE(a.st_mode) == 0o700 and
                (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino) == inode, 'ownership')
        for name, expected in (('active.lock', self.lock_inode), ('record.json', self.record_inode)):
            if expected is not None:
                i = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
                need(stat.S_ISREG(i.st_mode) and i.st_uid == os.getuid() and stat.S_IMODE(i.st_mode) == 0o600 and
                    (i.st_dev, i.st_ino) == expected and i.st_nlink == 1, 'ownership')
        if self.lock_inode is not None:
            fd = os.open('active.lock', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd)
            try: need(os.read(fd, 64) == self.lock_value, 'ownership')
            finally: os.close(fd)
        if self.record_inode is not None:
            fd = os.open('record.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd)
            try:
                before = source.stable_file(os.fstat(fd))
                raw = bytearray()
                while len(raw) <= len(self.record_bytes):
                    block = os.read(fd, min(65536, len(self.record_bytes) - len(raw) + 1))
                    if not block: break
                    raw.extend(block)
                need(bytes(raw) == self.record_bytes and before == source.stable_file(os.fstat(fd)), 'ownership')
            finally: os.close(fd)

    def create(self, name):
        return os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.fd)

    def save(self):
        self.check(); validator.bounded(self.record); raw = validator.canonical(self.record)
        filename = 'record-' + uuid.uuid4().hex + '.next'; fd = self.create(filename)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as stream:
                stream.write(raw); stream.flush(); os.fsync(fd)
            i = os.fstat(fd); self.check()
            os.replace(filename, 'record.json', src_dir_fd=self.fd, dst_dir_fd=self.fd); os.fsync(self.fd)
            self.record_inode = (i.st_dev, i.st_ino); self.record_bytes = raw; self.check()
        finally: os.close(fd)

    def perform(self, action, body, dispatch, validate):
        need(action not in self.record['operations'] and len(self.record['operations']) < 16, 'ownership')
        entry = {'state': 'pending', 'proposal_sha256': hashlib.sha256(validator.canonical(body)).hexdigest(), 'identity': None}
        self.record['operations'][action] = entry; self.save()
        failure = False
        try:
            reply = dispatch(); identity = validate(reply)
            entry.update(state='confirmed', identity=identity); self.save()
            return reply
        except Exception:
            failure = True
            entry['state'] = 'uncertain'
            try: self.save()
            except Exception: pass
        if failure:
            body = dispatch = validate = reply = identity = None
            raise OperatorRefused('uncertain')

    def close(self):
        failed = False
        if self.fd is not None and self.lock_inode is not None:
            try:
                self.check(); os.unlink('active.lock', dir_fd=self.fd); os.fsync(self.fd)
            except Exception: failed = True
        for fd in (self.fd, self.parent):
            if fd is not None:
                try: os.close(fd)
                except Exception: failed = True
        self.fd = self.parent = None
        need(not failed, 'cleanup')


def fixture_matches(obj, proposal):
    identity = selected(obj)
    need(obj.get('kind') == proposal['kind'] and obj.get('apiVersion') == proposal['apiVersion'] and
        identity['name'] == proposal['metadata']['name'], 'fixture')
    value = copy.deepcopy(obj.get('spec')); expected = copy.deepcopy(proposal['spec'])
    pod = value if obj['kind'] == 'Pod' else value.get('template', {}).get('spec') if type(value) is dict else None
    expected_pod = expected if obj['kind'] == 'Pod' else expected['template']['spec']
    need(type(pod) is dict, 'fixture')
    for key, default in (('dnsPolicy', 'ClusterFirst'), ('schedulerName', 'default-scheduler'), ('preemptionPolicy', 'PreemptLowerPriority')):
        if key in pod: need(pod.pop(key) == default, 'fixture')
    if 'serviceAccount' in pod: need(pod.pop('serviceAccount') == expected_pod['serviceAccountName'], 'fixture')
    for c in pod.get('containers', []):
        for key, default in (('resources', {}), ('terminationMessagePath', '/dev/termination-log'), ('terminationMessagePolicy', 'File')):
            if key in c: need(c.pop(key) == default, 'fixture')
    if obj['kind'] == 'Deployment':
        for key, default in (('revisionHistoryLimit', 10), ('progressDeadlineSeconds', 600),
            ('strategy', {'type': 'RollingUpdate', 'rollingUpdate': {'maxUnavailable': '25%', 'maxSurge': '25%'}})):
            if key in value: need(value.pop(key) == default, 'fixture')
    need(validator.canonical(value) == validator.canonical(expected), 'fixture')
    return identity


class ProbeResult(NamedTuple):
    receipt_basename: str
    guard_bindings: tuple
    collected_cases: int = 40
    actual_enforcement_accepted: bool = False
    overall_live_restore_acceptance: bool = False


class AdmissionOperator:
    """Publication is a prior Flux prerequisite; this callback only verifies it fresh."""
    def __init__(self, source_fence, options, contract, renders, expected_chart_commit, verify_publication):
        failure = None
        try: self._initialize(source_fence, options, contract, renders, expected_chart_commit, verify_publication)
        except OperatorRefused as error: failure = error.code
        except Exception: failure = 'configuration'
        if failure:
            source_fence = options = contract = renders = expected_chart_commit = verify_publication = None
            raise OperatorRefused(failure)

    def _initialize(self, source_fence, options, contract, renders, expected_chart_commit, verify_publication):
        need(type(source_fence) is source.SourceFence and callable(verify_publication) and
            type(expected_chart_commit) is str and re.fullmatch('[0-9a-f]{40}', expected_chart_commit), 'configuration')
        validator.bounded(contract); validator.bounded(renders)
        need(validator.canonical(renders) == validator.canonical(validator.reviewed_renders(contract)), 'guard')
        self.fence, self.contract, self.renders = source_fence, copy.deepcopy(contract), copy.deepcopy(renders)
        self.commit, self.publication = expected_chart_commit, verify_publication
        self.api = API(options, origin=APPROVED_ORIGIN)

    def _publication(self, prepared, deadline):
        value = self.publication(deadline); validator.bounded(value)
        need(type(value) is dict and set(value) == {'chart_commit', 'validated_revision', 'flux_revision',
            'ci_success', 'flux_ready', 'flux_owner', 'guard_pins', 'publication_receipt_sha256'} and
            value['chart_commit'] == value['validated_revision'] == value['flux_revision'] == self.commit and
            value['ci_success'] is True and value['flux_ready'] is True and
            type(value['publication_receipt_sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['publication_receipt_sha256']), 'publication')
        owner = value['flux_owner']; original = prepared['source_identities']['kustomization']
        need(type(owner) is dict and set(owner) == {'kind', 'name', 'namespace', 'uid', 'resourceVersion'} and
            owner['kind'] == 'Kustomization' and all(owner[k] == original[k] for k in ('name', 'namespace', 'uid')) and
            metadata.text(owner['resourceVersion']), 'publication')
        need(type(value['guard_pins']) is list and len(value['guard_pins']) == 6, 'publication')
        pins = []
        expected = {(o['kind'], o['metadata']['name']): o for o in self.renders}
        for pin in value['guard_pins']:
            need(type(pin) is dict and set(pin) == {'kind', 'name', 'uid', 'resourceVersion', 'spec_sha256'} and
                (pin['kind'], pin['name']) in expected and validator.uid(pin['uid']) and metadata.text(pin['resourceVersion']) and
                pin['spec_sha256'] == hashlib.sha256(validator.canonical_spec(pin['kind'], expected[(pin['kind'],pin['name'])]['spec'])).hexdigest(), 'publication')
            pins.append({k: pin[k] for k in ('kind', 'name', 'uid')})
        actual = [self.api.guard(o['kind'], o['metadata']['name'], deadline=deadline) for o in self.renders]
        for obj in actual:
            matches = [p for p in value['guard_pins'] if p['kind'] == obj['kind'] and p['name'] == obj['metadata']['name']]
            need(len(matches) == 1 and all(obj['metadata'][k] == matches[0][k] for k in ('uid', 'resourceVersion')), 'publication')
        return value, pins, actual

    def _qualify(self, directory, deadline):
        run, result, failure = None, None, None
        try:
            alive(deadline); prepared = self.fence.prepare(deadline=deadline)
            target = prepared['restore_target_name']; seed = prepared['checkpoint_run_id']
            need(self.contract['protected_pvc_names'] == ['bortus-data', target] and
                type(seed) is str and re.fullmatch('[0-9a-f]{12}',seed), 'source')
            publication, pins, guards = self._publication(prepared, deadline)
            stable_publication = {k:v for k,v in publication.items() if k not in ('guard_pins','flux_owner')}
            original_uid_pins = {(p['kind'],p['name']):p['uid'] for p in pins}
            # Validate current specs/type checking before any fixture; no fabricated probe pass.
            self._guards_only(guards, pins)
            run = ProbeRun(directory, {'publication':publication, 'checkpoint_sha256':self.fence.checkpoint_sha256,
                'contract_sha256':hashlib.sha256(validator.canonical(self.contract)).hexdigest()})
            def fresh():
                alive(deadline); current = self.fence.check(deadline=deadline)
                need(current['checkpoint_journal_sha256'] == self.fence.checkpoint_sha256, 'source')
                p, newpins, liveguards = self._publication(prepared, deadline)
                need({k:v for k,v in p.items() if k not in ('guard_pins','flux_owner')} == stable_publication and
                    {(x['kind'],x['name']):x['uid'] for x in newpins} == original_uid_pins, 'publication')
                self._guards_only(liveguards,newpins); alive(deadline)
                return liveguards
            node = prepared['alternate_node_identity']['name']; image = self.contract['approved_image_references'][0]
            names = {'Pod':'bortus-admission-' + seed + '-pod', 'Deployment':'bortus-admission-' + seed + '-deployment'}
            proposals = {'Pod':object_for('Pod',names['Pod'],idle_spec(image,node)),
                'Deployment':object_for('Deployment',names['Deployment'],idle_spec(image,node,reference='bortus-data',guarded=False))}
            fixtures = {}
            def get(kind):
                code,obj=self.api.workload('GET',kind,names[kind],deadline=deadline)
                need(code==200,'fixture'); return obj
            def admitted(kind, reply):
                code,obj=reply;need(code==201,'fixture'); identity=selected(obj)
                actual=get(kind);current=fixture_matches(actual,proposals[kind])
                need(current['uid']==identity['uid'],'fixture');fresh();return current
            for kind in ('Pod','Deployment'):
                fresh()
                reply=run.perform(kind+'-create',proposals[kind],
                    lambda k=kind:self.api.workload('POST',k,body=proposals[k],deadline=deadline),
                    lambda reply,k=kind:admitted(k,reply))
                fixtures[kind]=selected(reply[1])
            for index,case in enumerate(validator.probe_catalog(self.contract)):
                fresh();kind=case['kind'];scenario=case['scenario'];name='bortus-admission-'+seed+'-case-'+str(index)
                if scenario=='oldObject-reference-removal':
                    current=get('Deployment');old=fixture_matches(current,proposals['Deployment'])
                    need(old['uid']==fixtures['Deployment']['uid'],'fixture')
                    changed=object_for('Deployment',names['Deployment'],idle_spec(image,node,reference=case['protected_reference'],guarded=False))
                    changed['metadata'].update(uid=old['uid'],resourceVersion=old['resourceVersion'])
                    proposals['Deployment']=copy.deepcopy(changed);proposals['Deployment']['metadata'].pop('uid');proposals['Deployment']['metadata'].pop('resourceVersion')
                    fresh()
                    run.perform('Deployment-switch-'+str(index),changed,
                        lambda:self.api.workload('PUT','Deployment',names['Deployment'],changed,deadline=deadline),
                        lambda reply:admitted_update(reply,get,proposals,fixtures,fresh))
                    current=get('Deployment');old=fixture_matches(current,proposals['Deployment'])
                    body=object_for('Deployment',names['Deployment'],idle_spec('fixture.invalid/bortus:unapproved-probe',node,guarded=False))
                    body['metadata'].update(uid=old['uid'],resourceVersion=old['resourceVersion']);name=names['Deployment']
                    code,obj=self.api.workload('PUT',kind,name,body,deadline=deadline,dry_run=True)
                elif scenario=='legacy-ephemeral':
                    current=get('Pod');old=fixture_matches(current,proposals['Pod']);need(old['uid']==fixtures['Pod']['uid'],'fixture')
                    body=copy.deepcopy(current);body.pop('status',None)
                    body['spec']['ephemeralContainers']=[{'name':'unapproved-probe','image':'fixture.invalid/bortus:unapproved-probe',
                        'imagePullPolicy':'Never','command':['node','-e','setInterval(()=>{},1000)'],'targetContainerName':'holder'}]
                    code,obj=self.api.workload('PUT',kind,names['Pod'],body,deadline=deadline,dry_run=True,subresource='ephemeralcontainers')
                else:
                    body=probe_object(case,name,image,node,self.contract)
                    code,obj=self.api.workload('POST',kind,body=body,deadline=deadline,dry_run=True)
                outcome=attributed(code,obj,case,original_uid_pins);obj=body=None
                fresh();run.record['outcomes'].append({'case':case,'result':outcome});run.save()
            final=validator.evaluate(self.renders,fresh(),self.contract,run.record['outcomes'],pinned_guard_identities=pins)
            for kind in ('Pod','Deployment'):
                fresh();current=get(kind);identity=fixture_matches(current,proposals[kind]);need(identity['uid']==fixtures[kind]['uid'],'fixture')
                body={'apiVersion':'v1','kind':'DeleteOptions','preconditions':{k:identity[k] for k in ('uid','resourceVersion')}}
                run.perform(kind+'-delete',body,lambda k=kind:self.api.workload('DELETE',k,names[k],body,deadline=deadline),
                    lambda reply,k=kind:deleted(reply,self.api,k,names[k],identity,deadline,fresh))
            fresh();run.record['phase']='completed';run.save()
            result=ProbeResult('record.json',final.guards)
        except OperatorRefused as error:failure=error.code
        except Exception:failure='probe'
        finally:
            if run is not None:
                if failure:
                    try:run.record['phase']='refused';run.record['failure']=failure;run.save()
                    except Exception:pass
                try:run.close()
                except Exception:failure='cleanup';result=None
        return (None if failure else result),failure

    def _guards_only(self, objects, pins):
        # The pure validator owns this exact schema; probes are not substituted here.
        expected={(o['kind'],o['metadata']['name']):o for o in self.renders}
        need(len(objects)==6 and len(pins)==6,'guard')
        pinmap={(p['kind'],p['name']):p['uid'] for p in pins}; seen=set()
        need(set(pinmap)==set(expected) and len(set(pinmap.values()))==6,'guard')
        for obj in objects:
            key=(obj.get('kind'),obj.get('metadata',{}).get('name'));need(key in expected,'guard')
            meta=obj.get('metadata',{})
            need(key not in seen and obj.get('apiVersion')==validator.API and not meta.get('namespace') and
                not meta.get('deletionTimestamp') and meta.get('uid')==pinmap[key] and metadata.text(meta.get('resourceVersion')),'guard')
            seen.add(key)
            need(validator.canonical_spec(key[0],obj.get('spec'))==validator.canonical_spec(key[0],expected[key]['spec']),'guard')
            if key[0]==validator.POLICY:
                status=obj.get('status',{});tc=status.get('typeChecking');generation=obj['metadata'].get('generation')
                need(type(generation)is int and generation>0 and type(status.get('observedGeneration'))is int and
                    status['observedGeneration']==generation and type(tc)is dict and set(tc)<={'expressionWarnings'} and tc.get('expressionWarnings',[])==[],'guard')

    def qualify(self,directory,*,deadline):
        result,failure=self._qualify(directory,deadline)
        if failure:
            directory=deadline=result=None
            raise OperatorRefused(failure)
        return result


def admitted_update(reply,get,proposals,fixtures,fresh):
    code,obj=reply;need(code==200,'fixture');identity=fixture_matches(get('Deployment'),proposals['Deployment'])
    need(selected(obj)['uid']==identity['uid']==fixtures['Deployment']['uid'],'fixture');fresh();return identity


def deleted(reply,api,kind,name,identity,deadline,fresh):
    code,obj=reply;need(code in(200,202) and type(obj)is dict,'cleanup')
    if obj.get('kind')=='Status':
        details=obj.get('details')
        need(obj.get('apiVersion')=='v1' and obj.get('status')=='Success' and type(details)is dict and
            details.get('name')==name and details.get('uid')==identity['uid'] and
            details.get('kind')==WORKLOADS[kind][1].rsplit('/',1)[1],'cleanup')
    else:
        need(obj.get('apiVersion')==WORKLOADS[kind][0] and obj.get('kind')==kind and
            selected(obj,allow_deleting=True)['uid']==identity['uid'] and obj['metadata']['name']==name,'cleanup')
    while True:
        fresh();code,page=api.workload('GET',kind,deadline=deadline)
        meta=page.get('metadata')if type(page)is dict else None;items=page.get('items')if type(page)is dict else None
        need(code==200 and page.get('apiVersion')==WORKLOADS[kind][0] and page.get('kind')==kind+'List' and
            type(meta)is dict and metadata.text(meta.get('resourceVersion'))and meta.get('continue','')=='' and
            ('remainingItemCount'not in meta or type(meta['remainingItemCount'])is int and meta['remainingItemCount']==0)and
            type(items)is list and len(items)<=10000,'cleanup')
        need(all(type(item)is dict and item.get('kind')==kind and item.get('apiVersion')==WORKLOADS[kind][0] for item in items),'cleanup')
        ids=[selected(item,allow_deleting=True)for item in items]
        need(len({i['name']for i in ids})==len(ids)and len({i['uid']for i in ids})==len(ids),'cleanup')
        need(not any(i['name']==name and i['uid']!=identity['uid']for i in ids),'cleanup')
        if not any(i['name']==name or i['uid']==identity['uid']for i in ids):fresh();return identity
        alive(deadline);time.sleep(min(.05,deadline-time.monotonic()))
