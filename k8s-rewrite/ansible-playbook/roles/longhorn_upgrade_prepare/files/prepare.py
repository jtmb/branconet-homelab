"""Prepare a pinned existing-owner upgrade and execute server dry-run only."""
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import yaml

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
O = F / 'platform-upstream-review-20261027'
R = O / 'longhorn-owner-review-r2'
P = O / 'longhorn-prepared-v1.13.0'
MANIFEST_SHA = 'd0f99488e7b2789312d45b0127ce7388df71a971e6fca2085e88635303cc0a1f'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, obj):
    with (P / name).open('x') as out:
        json.dump(obj, out, indent=2)
        out.write('\n')


def key(obj):
    m = obj['metadata']
    return obj['apiVersion'], obj['kind'], m.get('namespace', ''), m['name']


def configuration(obj):
    return {'uid': obj['metadata']['uid'], 'labels': obj['metadata'].get('labels', {}),
            'annotations': obj['metadata'].get('annotations', {}),
            **{k: obj.get(k) for k in ('spec', 'rules', 'roleRef', 'subjects', 'data', 'binaryData')}}


def call(args, data):
    run = subprocess.run(SSH + ['kubectl', *args], input=json.dumps(data).encode(),
                         capture_output=True, timeout=240)
    need(len(run.stdout) <= 16 * 1024**2 and len(run.stderr) <= 1024**2, 'bounded_server_response')
    return run


def get(query):
    run = call(['get', '-f', '-', '--ignore-not-found=true', '--show-managed-fields=true', '-o', 'json'], query)
    need(run.returncode == 0, 'live_nonsecret_resource_read')
    return {key(v): v for v in json.loads(run.stdout)['items']}


def pin(value, images):
    if isinstance(value, str):
        for tag, digest in images.items():
            value = value.replace(tag, digest)
        return value
    if isinstance(value, list):
        return [pin(v, images) for v in value]
    if isinstance(value, dict):
        return {k: pin(v, images) for k, v in value.items()}
    return value


def normalized_command(value):
    return [re.sub(r'docker[.]io/longhornio/([a-z0-9.-]+):[A-Za-z0-9_.-]+(?:@sha256:[0-9a-f]{64})?',
                   r'docker.io/longhornio/\1:<version>', v) for v in value or []]


def preserve_workload(doc, old):
    before, after = old['spec'], doc['spec']
    for field in ('replicas', 'strategy', 'updateStrategy'):
        if field in before:
            after[field] = copy.deepcopy(before[field])
    before, after = before['template']['spec'], after['template']['spec']
    for field in ('nodeSelector', 'affinity', 'tolerations', 'imagePullSecrets', 'securityContext',
                  'priorityClassName', 'hostNetwork', 'dnsPolicy', 'schedulerName', 'runtimeClassName'):
        if field in before:
            after[field] = copy.deepcopy(before[field])
        else:
            after.pop(field, None)
    for field in ('containers', 'initContainers'):
        existing = {c['name']: c for c in before.get(field, [])}
        need(set(existing) <= {c['name'] for c in after.get(field, [])}, 'no_existing_container_removed')
        for c in after.get(field, []):
            old_c = existing.get(c['name'])
            if old_c is None:
                continue
            need(normalized_command(old_c.get('command')) == normalized_command(c.get('command'))
                 and normalized_command(old_c.get('args')) == normalized_command(c.get('args')), 'review_custom_command_before_upgrade')
            c['resources'] = copy.deepcopy(old_c.get('resources', {}))
            if 'imagePullPolicy' in old_c:
                c['imagePullPolicy'] = old_c['imagePullPolicy']
            extras = [e for e in old_c.get('env', []) if e['name'] not in {v['name'] for v in c.get('env', [])}]
            c.setdefault('env', []).extend(copy.deepcopy(extras))


def main():
    need(F.is_mount() and not P.exists(), 'new_prepared_namespace_required')
    for path in (F, Path('/mnt/c')):
        s = os.statvfs(path)
        need(s.f_bavail * s.f_frsize >= 15 * 1024**3 + 32 * 1024**2, 'metadata_capacity_floor')
    review = json.loads((R / 'review.json').read_text())
    need(review['status'] == 'completed_read_only' and review['fieldManagersExplicitlyCollected']
         and not review['directSensitiveEnvironmentRedactions'], 'explicit_nonsecret_owner_review_required')
    raw = (O / 'longhorn-v1.13.0.yaml').read_bytes()
    need(hashlib.sha256(raw).hexdigest() == MANIFEST_SHA, 'official_vendor_manifest')
    docs = [d for d in yaml.safe_load_all(raw) if d]
    need(len(docs) == 62 and all(d['kind'] != 'Secret' for d in docs), 'reviewed_public_resource_set')
    baseline = {key(v): v for v in json.loads((R / 'live-nonsecret-objects.json').read_text())['items']}
    query = {'apiVersion': 'v1', 'kind': 'List', 'items': [{'apiVersion': d['apiVersion'], 'kind': d['kind'],
             'metadata': {k: d['metadata'][k] for k in ('name', 'namespace') if k in d['metadata']}} for d in docs]}
    current = get(query)
    need(set(current) == set(baseline) and all(configuration(current[k]) == configuration(v)
         for k, v in baseline.items()), 'reviewed_object_identities_and_configuration_unchanged')
    candidates = json.loads((O / 'longhorn-1.13.0-candidates.json').read_text())['images']
    images = {v['reference'].split('@')[0]: v['reference'] for v in candidates}
    need(len(images) == 14 and all(re.fullmatch(r'docker[.]io/longhornio/[a-z0-9.-]+:[A-Za-z0-9_.-]+@sha256:[0-9a-f]{64}', v)
                                 for v in images.values()), 'fourteen_reviewed_digest_pins')
    prepared = pin(docs, images)
    preserved_maps, preserved_workloads = [], []
    for doc in prepared:
        old = current.get(key(doc))
        if not old:
            continue
        if doc['kind'] == 'Namespace':
            continue  # Existing prerequisite owned by before-first-apply, not this upgrade.
        need(any(m.get('manager') == 'kubectl' and m.get('operation') == 'Apply'
                 for m in old['metadata'].get('managedFields', [])), 'existing_kubectl_apply_owner_required')
        if doc['kind'] == 'ConfigMap':
            doc['data'] = copy.deepcopy(old.get('data', {}))
            preserved_maps.append(doc['metadata']['name'])
        if doc['kind'] in ('Deployment', 'DaemonSet'):
            preserve_workload(doc, old)
            preserved_workloads.append(doc['metadata']['name'])
        if doc['kind'] == 'Service':
            for field in ('type', 'ports', 'clusterIP', 'clusterIPs', 'ipFamilies', 'ipFamilyPolicy',
                          'sessionAffinity', 'sessionAffinityConfig', 'externalIPs', 'externalTrafficPolicy',
                          'internalTrafficPolicy', 'loadBalancerIP', 'loadBalancerSourceRanges',
                          'allocateLoadBalancerNodePorts', 'loadBalancerClass'):
                if field in old['spec']:
                    doc['spec'][field] = copy.deepcopy(old['spec'][field])
    prepared = [d for d in prepared if d['kind'] != 'Namespace']
    storage = next(d for d in prepared if d['kind'] == 'ConfigMap' and d['metadata']['name'] == 'longhorn-storageclass')
    sc = yaml.safe_load(storage['data']['storageclass.yaml'])
    need(sc['reclaimPolicy'] == 'Retain' and sc['parameters']['encrypted'] == 'true'
         and sc['parameters']['numberOfReplicas'] == '2', 'existing_encrypted_two_replica_retain_class_preserved')
    payload = {'apiVersion': 'v1', 'kind': 'List', 'items': prepared}
    strings = json.dumps(payload)
    references = re.findall(r'docker[.]io/longhornio/[a-z0-9.-]+:[A-Za-z0-9_.-]+(?:@sha256:[0-9a-f]{64})?', strings)
    need(references and all(v in images.values() for v in references), 'every_consumed_vendor_image_digest_pinned')
    os.umask(0o077)
    P.mkdir(mode=0o700)
    write('ownership.json', {'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
          'physicalVolume': 'F: ext4 3c792469-ea0e-4a2c-98e8-1185b141607b', 'sourceSHA256': sha(Path(__file__)),
          'outputs': ['candidate.json', 'server-dry-run.json', 'receipt.json', 'ownership.json'],
          'regeneration': 'same reviewed source and input hashes; a new evidence namespace; never actual apply',
          'protected': 'all existing objects, data, claims, Secrets, sources, original failures and backups'})
    write('candidate.json', payload)
    result = {'status': 'started', 'sourceSHA256': sha(Path(__file__)), 'vendorManifestSHA256': MANIFEST_SHA,
              'reviewSHA256': sha(R / 'review.json'), 'candidateSHA256': sha(P / 'candidate.json'),
              'fieldManager': 'kubectl', 'forceConflicts': False, 'serverDryRunOnly': True,
              'productionApplyExecuted': False, 'upgradeQualified': False, 'preservedConfigMaps': preserved_maps,
              'reviewedVendorResources': 62, 'existingNamespaceExcludedFromApply': True,
              'preservedWorkloads': preserved_workloads, 'consumedPinnedReferences': sorted(set(references)),
              'unusedCandidateReferences': sorted(set(images.values()) - set(references))}
    try:
        dry = call(['apply', '--server-side', '--dry-run=server', '--field-manager=kubectl',
                    '--validate=strict', '-f', '-', '-o', 'json'], payload)
        result.update(serverExitCode=dry.returncode, diagnosticsSHA256=hashlib.sha256(dry.stderr).hexdigest())
        if dry.returncode:
            (P / 'server-dry-run-error.log').write_bytes(dry.stderr)
        need(dry.returncode == 0, 'server_dry_run_failed_no_production_apply')
        response = json.loads(dry.stdout)
        need(len(response['items']) == len(prepared) == 61, 'every_applicable_vendor_resource_dry_run_returned')
        write('server-dry-run.json', response)
        after = get(query)
        need(set(after) == set(current) and all(configuration(after[k]) == configuration(v)
             for k, v in current.items()), 'all_original_objects_unchanged_after_dry_run')
        result.update(status='completed_server_dry_run', resources=61, existingObjectsPreserved=len(current),
                      completedUTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      allExistingUIDsAndConfigurationUnchanged=True)
    except Exception as error:
        result.update(status='failed', errorCategory=str(error) if isinstance(error, ValueError) else type(error).__name__)
        raise
    finally:
        write('receipt.json', result)
        print(json.dumps({k: result[k] for k in ('status', 'serverDryRunOnly', 'productionApplyExecuted', 'upgradeQualified')}))


if __name__ == '__main__':
    main()
