"""Pure source-bound admission metadata/probe validator; no API or live acceptance."""
import hashlib
import json
import re
import uuid
from typing import NamedTuple

API = 'admissionregistration.k8s.io/v1'
POLICY = 'ValidatingAdmissionPolicy'
BINDING = 'ValidatingAdmissionPolicyBinding'
CHART_SOURCE = '710e5ecd9434fc869eac12b497e326a21752c55e'
VARIANTS = (
    ('pods', 'spec', [([''], ['pods', 'pods/ephemeralcontainers'])]),
    ('templates', 'spec.template.spec', [(['apps'], ['deployments', 'statefulsets', 'daemonsets', 'replicasets']),
        ([''], ['replicationcontrollers']), (['batch'], ['jobs'])]),
    ('cronjobs', 'spec.jobTemplate.spec.template.spec', [(['batch'], ['cronjobs'])]))
KINDS = {'Pod': 'pods', 'Deployment': 'templates', 'StatefulSet': 'templates',
    'DaemonSet': 'templates', 'ReplicaSet': 'templates', 'ReplicationController': 'templates',
    'Job': 'templates', 'CronJob': 'cronjobs'}
FAILURES = ('bounds', 'contract', 'render', 'identity', 'spec', 'typechecking', 'probes', 'attribution')


class AdmissionRefused(RuntimeError):
    def __init__(self, code):
        self.code = code if code in FAILURES else 'bounds'
        super().__init__('Admission qualification refused: ' + self.code)


class GuardIdentity(NamedTuple):
    kind: str
    name: str
    uid: str
    resource_version: str
    spec_sha256: str


class AdmissionMetadata(NamedTuple):
    guards: tuple
    case_ids: tuple
    coverage: tuple
    metadata_validated: bool = True
    actual_enforcement_accepted: bool = False
    overall_live_restore_acceptance: bool = False


def need(ok, code):
    if not ok: raise AdmissionRefused(code)


def bounded(value):
    nodes = 0
    def walk(v, depth):
        nonlocal nodes
        nodes += 1
        need(depth <= 24 and nodes <= 30000, 'bounds')
        if type(v) is dict:
            need(len(v) <= 128 and all(type(k) is str and len(k) <= 256 for k in v), 'bounds')
            for item in v.values(): walk(item, depth + 1)
        elif type(v) is list:
            need(len(v) <= 2048, 'bounds')
            for item in v: walk(item, depth + 1)
        elif type(v) is str: need(len(v) <= 65536, 'bounds')
        else: need(v is None or type(v) in (bool, int), 'bounds')
    walk(value, 0)
    need(len(canonical(value)) <= 1024 * 1024, 'bounds')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def canonical_spec(kind, value):
    # Kubernetes v1.37 defaults MatchResources selectors to empty match-all maps.
    # Normalize only those literal defaults; any narrowing selector remains drift.
    normalized = json.loads(canonical(value))
    if kind == POLICY and type(normalized) is dict:
        constraints = normalized.get('matchConstraints')
        if type(constraints) is dict:
            for key in ('namespaceSelector', 'objectSelector'):
                if key in constraints and type(constraints[key]) is dict and constraints[key] == {}:
                    constraints.pop(key)
    return canonical(normalized)


def name(value):
    return type(value) is str and len(value) <= 253 and re.fullmatch('[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', value)


def uid(value):
    try: return type(value) is str and str(uuid.UUID(value)) == value
    except (ValueError, AttributeError): return False


def contract_checked(contract):
    need(type(contract) is dict and set(contract) == {'namespace', 'guarded_service_account',
        'protected_pvc_names', 'protected_secret_names', 'approved_image_references'}, 'contract')
    need(contract['namespace'] == 'bortus' and contract['guarded_service_account'] == 'bortus-kv', 'contract')
    for key, required in (('protected_pvc_names', {'bortus-data'}),
                          ('protected_secret_names', {'bortus-runtime', 'bortus-operator-access'})):
        values = contract[key]
        need(type(values) is list and 1 <= len(values) <= 64 and all(name(v) for v in values) and
             len(set(values)) == len(values) and required <= set(values), 'contract')
    claims = contract['protected_pvc_names']
    need(len(claims) == 2 and claims[0] == 'bortus-data' and
         re.fullmatch('bortus-restore-[0-9a-f]{12}', claims[1]), 'contract')
    images = contract['approved_image_references']
    need(type(images) is list and 1 <= len(images) <= 8 and all(type(v) is str and len(v) <= 512 and
        re.fullmatch('[a-z0-9][a-z0-9._/:-]*@sha256:[0-9a-f]{64}', v) and
        ':' not in v.split('@')[0].rsplit('/', 1)[-1] for v in images) and len(set(images)) == len(images), 'contract')


def spec_expression(root, path):
    parts = path.split('.')
    checks = [f'has({root}.{".".join(parts[:i])})' for i in range(1, len(parts) + 1)]
    if root == 'oldObject': checks.insert(0, 'oldObject != null')
    return ' && '.join(checks) + f' ? {root}.{path} : null'


def protected_expression(spec, containers, contract):
    sa = json.dumps(contract['guarded_service_account'])
    checks = [f'(has({spec}.serviceAccountName) && {spec}.serviceAccountName == {sa})',
        f'(has({spec}.serviceAccount) && {spec}.serviceAccount == {sa})',
        f'(has({spec}.imagePullSecrets) && {spec}.imagePullSecrets.exists(s, has(s.name) && s.name in variables.protectedSecrets))',
        f'{containers}.exists(c, (has(c.env) && c.env.exists(e, has(e.valueFrom) && has(e.valueFrom.secretKeyRef) && has(e.valueFrom.secretKeyRef.name) && e.valueFrom.secretKeyRef.name in variables.protectedSecrets)) || (has(c.envFrom) && c.envFrom.exists(e, has(e.secretRef) && has(e.secretRef.name) && e.secretRef.name in variables.protectedSecrets)))']
    volumes = ['(has(v.persistentVolumeClaim) && has(v.persistentVolumeClaim.claimName) && v.persistentVolumeClaim.claimName in variables.protectedClaims)',
        '(has(v.secret) && has(v.secret.secretName) && v.secret.secretName in variables.protectedSecrets)',
        '(has(v.projected) && has(v.projected.sources) && v.projected.sources.exists(s, has(s.secret) && has(s.secret.name) && s.secret.name in variables.protectedSecrets))',
        '(has(v.azureFile) && has(v.azureFile.secretName) && v.azureFile.secretName in variables.protectedSecrets)']
    for parent, child in [('csi', 'nodePublishSecretRef'), ('flexVolume', 'secretRef'), ('cephfs', 'secretRef'),
        ('rbd', 'secretRef'), ('iscsi', 'secretRef'), ('scaleIO', 'secretRef'), ('storageos', 'secretRef')]:
        volumes.append(f'(has(v.{parent}) && has(v.{parent}.{child}) && has(v.{parent}.{child}.name) && v.{parent}.{child}.name in variables.protectedSecrets)')
    checks.append(f'(has({spec}.volumes) && {spec}.volumes.exists(v, ' + ' || '.join(volumes) + '))')
    return f'{spec} != null && (' + ' || '.join(checks) + ')'


def reviewed_renders(contract):
    """Pure literal specs equivalent to the pinned chart renderer/templates."""
    contract_checked(contract)
    objects = []
    for suffix, path, rules in VARIANTS:
        policy_name = 'bortus-kv-guard-' + suffix
        variables = [('approvedImages', json.dumps(contract['approved_image_references'])),
            ('protectedClaims', json.dumps(contract['protected_pvc_names'])),
            ('protectedSecrets', json.dumps(contract['protected_secret_names'])),
            ('podSpec', spec_expression('object', path)), ('oldPodSpec', spec_expression('oldObject', path))]
        for var, pod in [('containers', 'podSpec'), ('oldContainers', 'oldPodSpec')]:
            p = 'variables.' + pod
            variables.append((var, f'{p} == null ? [] : ((has({p}.containers) ? {p}.containers : []) + '
                f'(has({p}.initContainers) ? {p}.initContainers : []) + '
                f'(has({p}.ephemeralContainers) ? {p}.ephemeralContainers : []))'))
        variables.extend([('newProtected', protected_expression('variables.podSpec', 'variables.containers', contract)),
                          ('oldProtected', protected_expression('variables.oldPodSpec', 'variables.oldContainers', contract))])
        spec = {'failurePolicy': 'Fail', 'matchConstraints': {'matchPolicy': 'Equivalent', 'resourceRules': [
            {'apiGroups': groups, 'apiVersions': ['v1'], 'operations': ['CREATE', 'UPDATE'],
             'resources': resources, 'scope': 'Namespaced'} for groups, resources in rules]},
            'matchConditions': [{'name': 'exact-bortus-namespace', 'expression': 'request.namespace == "bortus"'}],
            'variables': [{'name': k, 'expression': v} for k, v in variables],
            'validations': [{'expression': "!(variables.newProtected || variables.oldProtected) || "
                "(size(variables.containers) > 0 && variables.containers.all(c, "
                "has(c.image) && c.image in variables.approvedImages && "
                "has(c.imagePullPolicy) && c.imagePullPolicy == 'Never'))",
                'message': 'BORTUS protected identity, metadata claim or credential references require approved compatible immutable images in every container with pullPolicy Never.',
                'reason': 'Forbidden'}]}
        for kind, value in ((POLICY, spec), (BINDING, {'policyName': policy_name, 'validationActions': ['Deny']})):
            objects.append({'apiVersion': API, 'kind': kind, 'metadata': {'name': policy_name}, 'spec': value})
    return objects


def probe_catalog(contract):
    """Metadata descriptors only; root must construct and prove actual requests."""
    contract_checked(contract)
    cases = []
    def add(kind, scenario, reference, allowed=False, operation='CREATE', subresource=''):
        case_id = ':'.join((kind, scenario, reference))
        cases.append({'case_id': case_id, 'kind': kind, 'namespace': 'bortus', 'operation': operation,
            'subresource': subresource, 'scenario': scenario, 'protected_reference': reference,
            'expected_outcome': 'allowed' if allowed else 'guard_denied'})
    original, restored = contract['protected_pvc_names']
    add('Pod', 'inert-readonly-approved', original, True)
    add('Pod', 'inert-readonly-approved', restored, True)
    for kind, scenario, reference in (
        ('Deployment', 'legacy-new-principal', original),
        ('StatefulSet', 'legacy-default-principal', restored),
        ('DaemonSet', 'mutable-tag-label', original),
        ('ReplicaSet', 'registry-alias', restored),
        ('ReplicationController', 'pullPolicy-Always', original),
        ('Job', 'legacy-init', restored),
        ('CronJob', 'deprecated-serviceAccount-alias', original)):
        add(kind, scenario, reference)
    add('Pod', 'legacy-ephemeral', 'bortus-kv', operation='UPDATE', subresource='ephemeralcontainers')
    for kind, reference in (('Deployment', original), ('Deployment', restored),
                           ('Deployment', 'bortus-runtime'), ('Deployment', 'bortus-operator-access')):
        add(kind, 'oldObject-reference-removal', reference, operation='UPDATE')
    for secret in ('bortus-runtime', 'bortus-operator-access'):
        for index, form in enumerate(('env', 'envFrom', 'volume', 'projected', 'imagePullSecret', 'azureFile',
                                     'csi', 'flexVolume', 'cephfs', 'rbd', 'iscsi', 'scaleIO', 'storageos')):
            add(tuple(KINDS)[index % len(KINDS)], 'legacy-default-secret-' + form, secret)
    need(len(cases) == 40, 'probes')
    return cases


def coverage_map(contract):
    """Joint live-case coverage; Cartesian CEL coverage comes from exact specs."""
    cases = probe_catalog(contract); coverage = {}
    for case in cases:
        categories = ['workload:' + case['kind'], 'reference:' + case['protected_reference'],
                      'scenario:' + case['scenario']]
        for category in categories: coverage.setdefault(category, []).append(case['case_id'])
    return {'maximum_cases': 40, 'categories': coverage,
        'structural_only_ephemeral_claim_names': list(contract['protected_pvc_names']),
        'structural_only_extra_secret_names': [n for n in contract['protected_secret_names']
            if n not in ('bortus-runtime', 'bortus-operator-access')]}


def _evaluate(expected_renders, actual_gets, contract, probe_outcomes, pinned_guard_identities):
    result, failure = None, None
    try:
        for value in (expected_renders, actual_gets, contract, probe_outcomes, pinned_guard_identities): bounded(value)
        reviewed = reviewed_renders(contract)
        need(type(expected_renders) is list and len(expected_renders) == 6 and
             canonical(expected_renders) == canonical(reviewed), 'render')
        need(type(actual_gets) is list and len(actual_gets) == 6 and
             type(pinned_guard_identities) is list and len(pinned_guard_identities) == 6, 'identity')
        pins = {}
        for pin in pinned_guard_identities:
            need(type(pin) is dict and set(pin) == {'kind', 'name', 'uid'} and uid(pin['uid']), 'identity')
            key = (pin['kind'], pin['name']); need(key not in pins, 'identity'); pins[key] = pin['uid']
        expected = {(o['kind'], o['metadata']['name']): o for o in reviewed}
        need(set(pins) == set(expected) and len(set(pins.values())) == 6, 'identity')
        guards = {}
        for obj in actual_gets:
            need(type(obj) is dict and obj.get('apiVersion') == API and type(obj.get('metadata')) is dict, 'identity')
            meta = obj['metadata']; key = (obj.get('kind'), meta.get('name'))
            rv = meta.get('resourceVersion')
            need(key in expected and key not in guards and not meta.get('namespace') and
                not meta.get('deletionTimestamp') and meta.get('uid') == pins[key] and
                type(rv) is str and 0 < len(rv) <= 256 and all(32 < ord(c) < 127 for c in rv), 'identity')
            need(canonical_spec(key[0], obj.get('spec')) == canonical_spec(key[0], expected[key]['spec']), 'spec')
            if key[0] == POLICY:
                status = obj.get('status'); generation = meta.get('generation')
                need(type(generation) is int and generation > 0 and type(status) is dict and
                    type(status.get('observedGeneration')) is int and status['observedGeneration'] == generation and
                    type(status.get('typeChecking')) is dict and set(status['typeChecking']) <= {'expressionWarnings'} and
                    status['typeChecking'].get('expressionWarnings', []) == [], 'typechecking')
            guards[key] = GuardIdentity(key[0], key[1], pins[key], rv, hashlib.sha256(canonical_spec(key[0], obj['spec'])).hexdigest())
        catalog = {c['case_id']: c for c in probe_catalog(contract)}
        need(type(probe_outcomes) is list and len(probe_outcomes) == len(catalog), 'probes')
        seen = set()
        for outcome in probe_outcomes:
            need(type(outcome) is dict and set(outcome) == {'case', 'result'}, 'probes')
            case, reply = outcome['case'], outcome['result']
            need(type(case) is dict and case.get('case_id') in catalog and case['case_id'] not in seen and
                canonical(case) == canonical(catalog[case['case_id']]), 'probes')
            seen.add(case['case_id'])
            need(type(reply) is dict and set(reply) == {'http_status', 'outcome', 'attribution', 'other_failure'} and
                type(reply['http_status']) is int and reply['outcome'] == case['expected_outcome'] and
                reply['other_failure'] is None, 'attribution')
            if case['expected_outcome'] == 'allowed':
                need(200 <= reply['http_status'] < 300 and reply['attribution'] is None, 'attribution')
            else:
                a = reply['attribution']; policy_name = 'bortus-kv-guard-' + KINDS[case['kind']]
                need(reply['http_status'] == 403 and type(a) is dict and set(a) == {'source', 'reason',
                    'policy_name', 'binding_name', 'policy_uid', 'binding_uid', 'validation_index'} and
                    a['source'] == 'api_guard_rejection' and a['reason'] == 'Forbidden' and
                    a['policy_name'] == a['binding_name'] == policy_name and
                    a['policy_uid'] == pins[(POLICY, policy_name)] and a['binding_uid'] == pins[(BINDING, policy_name)] and
                    type(a['validation_index']) is int and a['validation_index'] == 0, 'attribution')
        need(seen == set(catalog), 'probes')
        coverage = coverage_map(contract)
        result = AdmissionMetadata(tuple(guards[key] for key in sorted(guards)), tuple(sorted(seen)),
            tuple((key, tuple(value)) for key, value in sorted(coverage['categories'].items())))
    except AdmissionRefused as error: failure = error.code
    except Exception: failure = 'bounds'
    return result, failure


def evaluate(expected_renders, actual_gets, contract, probe_outcomes, *, pinned_guard_identities):
    """Metadata eligibility only; caller owns actual fresh GET and probe evidence."""
    result, failure = _evaluate(expected_renders, actual_gets, contract, probe_outcomes, pinned_guard_identities)
    if failure:
        expected_renders = actual_gets = contract = probe_outcomes = pinned_guard_identities = None
        result = None
        raise AdmissionRefused(failure)
    return result
