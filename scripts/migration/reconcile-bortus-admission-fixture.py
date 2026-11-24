"""Reconcile the observed inert Pod from the failed default-normalization probe.

Never replay its uncertain create or rewrite the original probe record.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).parent
RUN = Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/guard-probes-da37c4f713e8')
NAME = 'bortus-admission-da37c4f713e8-pod'
UID = '42b1b503-52c8-41e0-8ce7-eef30ea7f765'
IMAGE = 'docker.io/jtmb92/bortus@sha256:ac261f9cc146171469dd9bd660acae39ae9563656a9a873e0fa251d4b2fda58b'


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def need(ok):
    if not ok:
        raise RuntimeError('owned_fixture_reconciliation_failed')


def reconcile_secret_default(operator, api, probe_failure=False, publication_transition=False):
    run = RUN.with_name(RUN.name + ('-secret-default-fix' if probe_failure else '-default-fix'))
    if publication_transition:
        run = RUN.with_name(RUN.name + '-diagnostic-fix')
    raw = (run / 'record.json').read_bytes()
    record = json.loads(raw)
    operations = record['operations']
    if publication_transition:
        need(record['phase'] == 'refused' and record['failure'] == 'uncertain' and len(record['outcomes']) == 0
             and set(operations) == {'Pod-create','Deployment-create'} and operations['Deployment-create']['state'] == 'uncertain')
    elif probe_failure:
        need(record['phase'] == 'refused' and record['failure'] == 'probe'
             and len(record['outcomes']) == 7 and set(operations) == {'Pod-create', 'Deployment-create'})
    else:
        need(record['phase'] == 'refused' and record['failure'] == 'uncertain'
             and len(record['outcomes']) == 12 and operations['Deployment-switch-12']['state'] == 'uncertain')
    expected = {}
    for kind, suffix, reference in [('Pod', 'pod', None), ('Deployment', 'deployment', 'bortus-data' if probe_failure or publication_transition else 'bortus-runtime')]:
        entry = operations[kind + '-create']
        need((entry['state'] == 'confirmed' and entry['identity']['uid'] == entry['returned_identity']['uid'])
             or (publication_transition and kind == 'Deployment' and entry['state'] == 'uncertain' and entry['returned_identity']['uid']))
        name = 'bortus-admission-da37c4f713e8-' + suffix
        proposal = operator.object_for(kind, name,
            operator.idle_spec(IMAGE, 'node02', reference=reference, guarded=kind == 'Pod'))
        expected[kind] = (entry['returned_identity']['uid'], name, proposal)
    if not probe_failure and not publication_transition:
        need(operations['Deployment-switch-12']['returned_identity']['uid'] == expected['Deployment'][0])
    deadline = time.monotonic() + 60
    def current(kind):
        uid, name, proposal = expected[kind]
        code, value = api.workload('GET', kind, name, deadline=deadline)
        need(code == 200 and value['metadata']['uid'] == uid and not value['metadata'].get('ownerReferences')
             and value['metadata'].get('labels') == proposal['metadata']['labels'])
        identity = operator.fixture_matches(value, proposal)
        if kind == 'Deployment':
            need(value['spec']['replicas'] == 0)
        else:
            need(not value['spec'].get('volumes') and value['spec']['automountServiceAccountToken'] is False)
        return identity
    identities = {kind: current(kind) for kind in expected}
    path = run / 'reconciliation.json'
    need(not path.exists())
    state = {'scope': 'Only recorded inert fixtures; no uncertain create/update is replayed',
             'original_record_sha256': hashlib.sha256(raw).hexdigest(), 'observed_identities': identities,
             'reason': ('Failed dry-run probe; confirmed inert fixtures only' if probe_failure else 'Only server-added Secret defaultMode0644 differed'), 'original_record_preserved': True,
             'state': 'delete-pending', 'deleted': []}
    def save(first=False):
        flags = os.O_WRONLY | os.O_NOFOLLOW | (os.O_CREAT | os.O_EXCL if first else os.O_TRUNC)
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, 'w') as out:
            json.dump(state, out, indent=2); out.write('\n'); out.flush(); os.fsync(out.fileno())
        fd = os.open(run, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(fd)
        finally: os.close(fd)
    save(first=True)
    try:
        for kind in ('Deployment', 'Pod'):
            identity = current(kind)
            body = {'apiVersion': 'v1', 'kind': 'DeleteOptions',
                    'preconditions': {k: identity[k] for k in ('uid', 'resourceVersion')}}
            code, _ = api.workload('DELETE', kind, identity['name'], body, deadline=deadline)
            need(code in (200, 202))
            while time.monotonic() < deadline:
                code, value = api.workload('GET', kind, identity['name'], deadline=deadline)
                if code == 404: break
                need(code == 200 and value['metadata']['uid'] == identity['uid'])
                time.sleep(0.25)
            else: raise RuntimeError('owned_fixture_deletion_not_observed')
            state['deleted'].append(identity)
            save()
        need((run / 'record.json').read_bytes() == raw)
        state.update(state='completed', owned_pod_absence_verified=True, owned_deployment_absence_verified=True)
        save()
        print(json.dumps({'owned_fixtures_removed': 2, 'original_uncertain_record_preserved': True,
                          'production_changed': False}))
    except Exception:
        state['state'] = 'uncertain-inspect-before-any-retry'
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cleanup', action='store_true', required=True)
    parser.add_argument('--after-secret-default', action='store_true')
    parser.add_argument('--after-probe-failure', action='store_true')
    parser.add_argument('--after-publication-transition', action='store_true')
    args = parser.parse_args()
    operator = load('reconcile_owned_guard_operator', 'bortus-admission-operator.py')
    credentials = load('reconcile_owned_guard_credentials', 'bortus-operator-mtls.py')
    options = credentials.OperatorMTLSOptions('/home/brajam/.local/share/branconet-migration/admin.conf')
    api = operator.API(options)
    if args.after_secret_default or args.after_probe_failure or args.after_publication_transition:
        reconcile_secret_default(operator, api, args.after_probe_failure, args.after_publication_transition)
        return
    raw = (RUN / 'record.json').read_bytes()
    record = json.loads(raw)
    need(record['phase'] == 'refused' and record['failure'] == 'uncertain'
         and set(record['operations']) == {'Pod-create'}
         and record['operations']['Pod-create']['state'] == 'uncertain')
    proposal = operator.object_for('Pod', NAME, operator.idle_spec(IMAGE, 'node02'))
    need(hashlib.sha256(operator.validator.canonical(proposal)).hexdigest() ==
         record['operations']['Pod-create']['proposal_sha256'])
    deadline = time.monotonic() + 60
    code, pod = api.workload('GET', 'Pod', NAME, deadline=deadline)
    need(code == 200 and pod['metadata']['uid'] == UID and not pod['metadata'].get('ownerReferences')
         and pod['metadata'].get('labels') == proposal['metadata']['labels']
         and pod['metadata']['creationTimestamp'] == '2026-11-15T01:52:37Z')
    identity = operator.fixture_matches(pod, proposal)
    need(identity['uid'] == UID and not pod['spec'].get('volumes')
         and pod['spec']['automountServiceAccountToken'] is False)
    path = RUN / 'reconciliation.json'
    need(not path.exists())
    state = {'scope': 'Exact observed inert diagnostic Pod only; original uncertain create is not replayed',
             'original_record_sha256': hashlib.sha256(raw).hexdigest(), 'observed_identity': identity,
             'reason': 'Only standard Kubernetes priority0 and two300s node-failure tolerations differed',
             'payload_matches_original_intent': True, 'original_record_preserved': True, 'state': 'delete-pending'}
    def save(first=False):
        flags = os.O_WRONLY | os.O_NOFOLLOW | (os.O_CREAT | os.O_EXCL if first else os.O_TRUNC)
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, 'w') as out:
            json.dump(state, out, indent=2); out.write('\n'); out.flush(); os.fsync(out.fileno())
        fd = os.open(RUN, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    save(first=True)
    try:
        body = {'apiVersion': 'v1', 'kind': 'DeleteOptions',
                'preconditions': {k: identity[k] for k in ('uid', 'resourceVersion')}}
        code, _ = api.workload('DELETE', 'Pod', NAME, body, deadline=deadline)
        need(code in (200, 202))
        while time.monotonic() < deadline:
            code, current = api.workload('GET', 'Pod', NAME, deadline=deadline)
            if code == 404:
                break
            need(code == 200 and current['metadata']['uid'] == UID)
            time.sleep(0.25)
        else:
            raise RuntimeError('owned_fixture_deletion_not_observed')
        need((RUN / 'record.json').read_bytes() == raw)
        state.update(state='completed', owned_pod_absence_verified=True)
        save()
        print(json.dumps({'owned_pod_removed': True, 'uid': UID,
                          'original_uncertain_record_preserved': True, 'production_changed': False}))
    except Exception:
        state['state'] = 'uncertain-inspect-before-any-retry'
        save()
        raise


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('owned_fixture_reconciliation_failed; ' + type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
