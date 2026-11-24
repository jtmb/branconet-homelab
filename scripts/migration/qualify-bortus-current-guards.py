"""Verify the current private publication and run the bounded existing guard probes."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).parent
ANCHOR = Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery')
RUNTIME = Path('/home/brajam/.local/share/branconet-migration')
COMMIT = 'eb3921c6fed7db8718d4256fb367d68da208ebac'
STAGE = Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/local-charts-publisher/local-charts-publish-5aaf249dd68d4150a1e6d8f92d068101')
STATUS = Path('/mnt/f/branconet-migration-artifacts/maintenance-storage-20261025/branconet-charts-local-ci-state/status.json')
CHARTS = 'C:/Users/james/AppData/Local/BORTUS/repos/branconet-charts'
GIT = '/mnt/c/Program Files/Git/cmd/git.exe'
JOURNAL = ANCHOR / 'recovery/bortus-checkpoints/da37c4f713e8/journal.json'
JOURNAL_SHA = '19736598e98c98f481d2f974a23e98af366b92b5354954cfae50aa034276ba88'
IMAGE = 'docker.io/jtmb92/bortus@sha256:ac261f9cc146171469dd9bd660acae39ae9563656a9a873e0fa251d4b2fda58b'


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def need(ok):
    if not ok:
        raise RuntimeError('current_guard_proof_failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--qualify', action='store_true')
    retry = parser.add_mutually_exclusive_group()
    retry.add_argument('--after-default-fix', action='store_true',
                        help='Fresh probe after exact original fixture reconciliation; never reuse its record')
    retry.add_argument('--after-secret-default-fix', action='store_true')
    retry.add_argument('--after-probe-reconciliation', action='store_true')
    retry.add_argument('--after-publication-transition', action='store_true')
    parser.add_argument('--diagnose-init', action='store_true', help='Read-only dry-run of the init-container denial case')
    parser.add_argument('--diagnose-fixtures', action='store_true')
    parser.add_argument('--diagnose-stability', action='store_true')
    args = parser.parse_args()
    operator = load('current_live_guard_operator', 'bortus-admission-operator.py')
    credentials = load('current_live_guard_credentials', 'bortus-operator-mtls.py')
    options = credentials.OperatorMTLSOptions(str(RUNTIME / 'admin.conf'))
    api = operator.API(options)
    metadata_api = operator.source.metadata.MetadataAPI(options)
    deadline = time.monotonic() + 300
    renders = []
    for suffix in ('pods', 'templates', 'cronjobs'):
        for form in ('policy', 'binding'):
            path = 'flux/releases/bortus-restore-maintenance/bortus-kv-guard-' + suffix + '-' + form + '.json'
            result = subprocess.run([GIT, '-C', CHARTS, 'show', COMMIT + ':' + path],
                                    capture_output=True, timeout=20)
            need(result.returncode == 0 and len(result.stdout) <= 65536)
            renders.append(json.loads(result.stdout))
    first = next(o for o in renders if o['kind'] == operator.validator.POLICY)
    variables = {v['name']: v['expression'] for v in first['spec']['variables']}
    contract = {'namespace': 'bortus', 'guarded_service_account': 'bortus-kv',
                'protected_pvc_names': json.loads(variables['protectedClaims']),
                'protected_secret_names': json.loads(variables['protectedSecrets']),
                'approved_image_references': json.loads(variables['approvedImages'])}
    need(contract['approved_image_references'][0] == IMAGE and
         operator.validator.canonical(renders) == operator.validator.canonical(operator.validator.reviewed_renders(contract)))

    def get(kind, name, namespace):
        remaining = deadline - time.monotonic()
        need(remaining > 0)
        result = subprocess.run([str(RUNTIME / 'bin/kubectl'), '--kubeconfig', str(RUNTIME / 'admin.conf'),
            '--request-timeout=15s', 'get', kind, name, '-n', namespace, '-o', 'json'],
            capture_output=True, timeout=min(20, remaining))
        need(result.returncode == 0 and len(result.stdout) <= 8 * 1024**2)
        return json.loads(result.stdout)

    def publication(until):
        need(time.monotonic() < until)
        status = json.loads(STATUS.read_text())
        need(status['sourceSHA'] == COMMIT and status['passed'] is True and status['actionsUsed'] is False
             and status['phase'] == 'published_await_flux' and status['stage'] == str(STAGE))
        for field, filename in [('check', 'check.json'), ('publish', 'publish.json')]:
            raw = (STAGE / filename).read_bytes()
            need(status[field]['receipt'] == str(STAGE / filename) and
                 hashlib.sha256(raw).hexdigest() == status[field]['receiptSHA256'])
            value = json.loads(raw)
            need(value['sourceSHA'] == COMMIT and value['passed'] is True)
            if field == 'check':
                need(all(check['exitCode'] == 0 for check in value['checks']))
            else:
                need(value['actionsUsed'] is False and value['publicationPerformed'] is True
                     and value['remoteRefsAfter']['refs/heads/validated'] == COMMIT)
                publication_sha = hashlib.sha256(raw).hexdigest()
        repository = get('gitrepository', 'branconet-charts', 'flux-system')
        owner = get('kustomization', 'migration-releases', 'flux-system')
        expected_revision = 'validated@sha1:' + COMMIT
        need(repository['spec']['url'] == 'ssh://git@github.com/jtmb/branconet-charts.git'
             and repository['spec']['ref']['branch'] == 'validated'
             and repository['status']['artifact']['revision'] == expected_revision
             and owner['status']['lastAppliedRevision'] == expected_revision)
        for obj in (repository, owner):
            settle_until = min(until, time.monotonic() + 20)
            while not (obj['status']['observedGeneration'] == obj['metadata']['generation'] and
                       any(c['type'] == 'Ready' and c['status'] == 'True' for c in obj['status']['conditions'])):
                # Flux briefly marks Ready false during an ordinary reconcile.
                # Wait only for that explicit transition; never accept a failed revision.
                conditions = obj['status']['conditions']
                need(any(c['type'] == 'Reconciling' and c['status'] == 'True' for c in conditions)
                     and not any(c['type'] == 'Stalled' and c['status'] == 'True' for c in conditions)
                     and time.monotonic() < settle_until)
                time.sleep(0.25)
                obj = get(obj['kind'].lower(), obj['metadata']['name'], 'flux-system')
                need((obj['status'].get('artifact', {}).get('revision') if obj['kind'] == 'GitRepository'
                      else obj['status'].get('lastAppliedRevision')) == expected_revision)
        pins = []
        for obj in renders:
            actual = api.guard(obj['kind'], obj['metadata']['name'], deadline=until)
            spec = operator.validator.canonical_spec(obj['kind'], actual['spec'])
            need(spec == operator.validator.canonical_spec(obj['kind'], obj['spec']))
            pins.append({'kind': obj['kind'], 'name': obj['metadata']['name'],
                         'uid': actual['metadata']['uid'], 'resourceVersion': actual['metadata']['resourceVersion'],
                         'spec_sha256': hashlib.sha256(spec).hexdigest()})
        return {'chart_commit': COMMIT, 'validated_revision': COMMIT, 'flux_revision': COMMIT,
                'ci_success': True, 'flux_ready': True,
                'flux_owner': {'kind': 'Kustomization', **{k: owner['metadata'][k]
                                  for k in ('name', 'namespace', 'uid', 'resourceVersion')}},
                'guard_pins': pins, 'publication_receipt_sha256': publication_sha}

    fence = operator.source.SourceFence(JOURNAL, JOURNAL_SHA, IMAGE, 'node02', metadata_api)
    try:
        probe = operator.AdmissionOperator(fence, options, contract, renders, COMMIT, publication)
        if args.check:
            prepared = fence.prepare(deadline=deadline)
            proof, pins, guards = probe._publication(prepared, deadline)
            probe._guards_only(guards, pins)
            if args.diagnose_stability:
                for i in range(20):
                    stage='source'
                    try:
                        fence.check(deadline=deadline)
                        stage='publication'
                        probe._publication(prepared,deadline)
                    except Exception as error:
                        print(json.dumps({'iteration':i,'stage':stage,'type':type(error).__name__,'code':getattr(error,'code',None),'locations':operator.failure_locations(error)}))
                        return
                print(json.dumps({'stable_source_publication_checks':20}))
                return
            if args.diagnose_fixtures:
                for kind, suffix, ref in [('Pod','pod',None),('Deployment','deployment','bortus-data')]:
                    code, obj = api.workload('GET',kind,'bortus-admission-da37c4f713e8-'+suffix,deadline=deadline)
                    proposal=operator.object_for(kind,'bortus-admission-da37c4f713e8-'+suffix,operator.idle_spec(IMAGE,'node02',reference=ref,guarded=kind=='Pod'))
                    try:
                        identity=operator.fixture_matches(obj,proposal)
                        print(json.dumps({'kind':kind,'fixture_matches':True,'identity':identity}))
                    except Exception as error:
                        print(json.dumps({'kind':kind,'fixture_matches':False,'locations':operator.failure_locations(error),'actual_spec':obj.get('spec'),'expected_spec':proposal['spec']}))
                return
            if args.diagnose_init:
                case = operator.validator.probe_catalog(contract)[7]
                body = operator.probe_object(case, 'bortus-admission-da37c4f713e8-case-7', IMAGE, 'node02', contract)
                code, obj = api.workload('POST', case['kind'], body=body, deadline=deadline, dry_run=True)
                pin_map = {(p['kind'], p['name']): p['uid'] for p in pins}
                outcome = operator.attributed(code, obj, case, pin_map)
                print(json.dumps({'init_container_denial_probe': outcome, 'mutations': 0}))
                return
            print(json.dumps({'private_ci_flux_guard_source_check_passed': True,
                              'guard_objects': len(guards), 'planned_live_cases': len(operator.validator.probe_catalog(contract)),
                              'mutations': 0}))
        else:
            folder = ANCHOR / 'guard-probes-da37c4f713e8'
            if args.after_default_fix or args.after_secret_default_fix or args.after_probe_reconciliation or args.after_publication_transition:
                original = folder if args.after_default_fix else folder.with_name(folder.name + '-default-fix')
                if args.after_probe_reconciliation:
                    original = ANCHOR / 'guard-probes-da37c4f713e8-secret-default-fix'
                if args.after_publication_transition:
                    original = ANCHOR / 'guard-probes-da37c4f713e8-diagnostic-fix'
                reconciled = json.loads((original / 'reconciliation.json').read_text())
                need(reconciled['state'] == 'completed' and reconciled['owned_pod_absence_verified'] is True
                     and reconciled['original_record_sha256'] == hashlib.sha256((original / 'record.json').read_bytes()).hexdigest())
                for kind, suffix in [('Pod', 'pod'), ('Deployment', 'deployment')]:
                    code, _ = api.workload('GET', kind, 'bortus-admission-da37c4f713e8-' + suffix, deadline=deadline)
                    need(code == 404)
                if args.after_secret_default_fix or args.after_probe_reconciliation or args.after_publication_transition:
                    need(reconciled['owned_deployment_absence_verified'] is True)
                folder = ANCHOR / ('guard-probes-da37c4f713e8-' +
                                   ('publication-settle' if args.after_publication_transition else ('diagnostic-fix' if args.after_probe_reconciliation else ('default-fix' if args.after_default_fix else 'secret-default-fix'))))
            result = probe.qualify(folder, deadline=deadline)
            print(json.dumps({'bounded_guard_probes_completed': True, 'cases': result.collected_cases,
                              'receipt': str(folder / result.receipt_basename),
                              'independent_restore_proven': False, 'application_deployed': False}))
    finally:
        fence.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        frames = []
        tb = error.__traceback__
        while tb:
            frames.append(Path(tb.tb_frame.f_code.co_filename).name + ':' + str(tb.tb_lineno))
            tb = tb.tb_next
        print('current_guard_proof_failed; ' + type(error).__name__ + '; ' + ','.join(frames)
              + '; locations=' + json.dumps(getattr(error, 'locations', [])), file=sys.stderr)
        raise SystemExit(1)
