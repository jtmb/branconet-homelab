#!/usr/bin/env python3
"""Read-only BORTUS cold-checkpoint prerequisites; never read database or Secrets."""
import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys

RUNTIME = pathlib.Path.home() / '.local/share/branconet-migration'
APP = 'bortus'
CLAIM = 'bortus-data'
MAX_PV_ITEMS = 10000
MAX_POD_ITEMS = 10000
MAX_PV_IDENTITY = 253
MAX_PV_RESOURCE_VERSION = 256


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def identity(obj):
    meta = obj.get('metadata', {})
    require(all(isinstance(meta.get(key), str) and meta[key]
                for key in ('name', 'uid', 'resourceVersion')), 'Incomplete resource identity')
    return {key: meta[key] for key in ('name', 'uid', 'resourceVersion')} | {
        'namespace': meta.get('namespace')}


def uses_claim(pod):
    return any(v.get('persistentVolumeClaim', {}).get('claimName') == CLAIM
               for v in pod.get('spec', {}).get('volumes', []))


def complete_pods(inventory):
    """Return only a bounded complete namespace collection, including inactive Pods."""
    failure = 'Complete bounded BORTUS Pod inventory required; output withheld'
    require(isinstance(inventory, dict) and inventory.get('apiVersion') == 'v1' and
            inventory.get('kind') == 'PodList', failure)
    meta = inventory.get('metadata')
    require(isinstance(meta, dict) and isinstance(meta.get('resourceVersion'), str) and
            0 < len(meta['resourceVersion']) <= MAX_PV_RESOURCE_VERSION and
            ('continue' not in meta or meta['continue'] == '') and
            ('remainingItemCount' not in meta or
             (type(meta['remainingItemCount']) is int and meta['remainingItemCount'] == 0)), failure)
    items = inventory.get('items')
    require(isinstance(items, list) and len(items) <= MAX_POD_ITEMS, failure)
    names, uids = set(), set()
    for pod in items:
        require(isinstance(pod, dict) and
                ('apiVersion' not in pod or pod['apiVersion'] == 'v1') and
                ('kind' not in pod or pod['kind'] == 'Pod'), failure)
        pm, spec, status = pod.get('metadata'), pod.get('spec'), pod.get('status')
        require(isinstance(pm, dict) and isinstance(spec, dict) and isinstance(status, dict) and
                pm.get('namespace') == APP and all(isinstance(pm.get(k), str) and
                0 < len(pm[k]) <= limit for k, limit in [('name', MAX_PV_IDENTITY),
                ('uid', MAX_PV_IDENTITY), ('resourceVersion', MAX_PV_RESOURCE_VERSION)]) and
                status.get('phase') in ('Pending', 'Running', 'Succeeded', 'Failed', 'Unknown'), failure)
        require(pm['name'] not in names and pm['uid'] not in uids, failure)
        names.add(pm['name'])
        uids.add(pm['uid'])
        volumes = spec.get('volumes', [])
        require(isinstance(volumes, list) and all(isinstance(v, dict) for v in volumes), failure)
        for volume in volumes:
            if 'persistentVolumeClaim' in volume:
                pvc = volume['persistentVolumeClaim']
                require(isinstance(pvc, dict) and isinstance(pvc.get('claimName'), str) and
                        0 < len(pvc['claimName']) <= MAX_PV_IDENTITY, failure)
    return items


def sole_longhorn_pv(inventory, expected, handle):
    """Require a complete bounded cluster PV list; aliases count even when inactive."""
    failure = 'Complete sole original Longhorn PV inventory required; output withheld'
    require(isinstance(inventory, dict) and inventory.get('apiVersion') == 'v1' and
            inventory.get('kind') == 'PersistentVolumeList', failure)
    meta = inventory.get('metadata')
    require(isinstance(meta, dict) and isinstance(meta.get('resourceVersion'), str) and
            0 < len(meta['resourceVersion']) <= MAX_PV_RESOURCE_VERSION, failure)
    require('continue' not in meta or meta['continue'] == '', failure)
    require('remainingItemCount' not in meta or
            (type(meta['remainingItemCount']) is int and meta['remainingItemCount'] == 0), failure)
    require(expected.get('namespace') in (None, '') and
            isinstance(handle, str) and 0 < len(handle) <= MAX_PV_IDENTITY, failure)
    items = inventory.get('items')
    require(isinstance(items, list) and 0 < len(items) <= MAX_PV_ITEMS, failure)
    names, uids, matches = set(), set(), []
    for item in items:
        require(isinstance(item, dict) and
                ('apiVersion' not in item or item['apiVersion'] == 'v1') and
                ('kind' not in item or item['kind'] == 'PersistentVolume'), failure)
        imeta, spec = item.get('metadata'), item.get('spec')
        require(isinstance(imeta, dict) and isinstance(spec, dict), failure)
        require(all(isinstance(imeta.get(k), str) and 0 < len(imeta[k]) <= limit
                    for k, limit in [('name', MAX_PV_IDENTITY), ('uid', MAX_PV_IDENTITY),
                                     ('resourceVersion', MAX_PV_RESOURCE_VERSION)]) and
                imeta.get('namespace') in (None, ''), failure)
        require(imeta['name'] not in names and imeta['uid'] not in uids, failure)
        names.add(imeta['name'])
        uids.add(imeta['uid'])
        csi = spec.get('csi')
        if 'csi' in spec:
            require(isinstance(csi, dict) and all(isinstance(csi.get(k), str) and
                    0 < len(csi[k]) <= MAX_PV_IDENTITY for k in ('driver', 'volumeHandle')), failure)
            if csi['driver'] == 'driver.longhorn.io' and csi['volumeHandle'] == handle:
                matches.append(imeta)
    require(len(matches) == 1 and matches[0]['name'] == expected['name'] and
            matches[0]['uid'] == expected['uid'] and not matches[0].get('deletionTimestamp'), failure)
    return {'items': len(items), 'resourceVersion': meta['resourceVersion'],
            'sole_original_longhorn_pv': True}


def evaluate(objects, expected_claim_uid, holder_image=None):
    require(isinstance(objects, (tuple, list)) and len(objects) == 10,
            'Complete checkpoint input inventory required')
    claim, pv, volume, deployment, pods, release, owner, target, replica_set, pvs = objects
    ids = {key: identity(obj) for key, obj in zip(
        ('claim', 'pv', 'longhorn_volume', 'deployment', 'helmrelease', 'kustomization', 'backup_target'),
        (claim, pv, volume, deployment, release, owner, target))}
    ids['replica_set'] = identity(replica_set)
    require(ids['claim']['uid'] == expected_claim_uid, 'Original claim identity differs')
    require(ids['claim']['name'] == CLAIM and ids['claim']['namespace'] == APP,
            'Unexpected claim identity')
    require(claim.get('status', {}).get('phase') == 'Bound', 'Claim is not Bound')
    require(claim.get('spec', {}).get('storageClassName') == 'longhorn', 'Unexpected storage class')
    require(claim['spec'].get('volumeName') == ids['pv']['name'] == ids['longhorn_volume']['name'],
            'Claim/PV/Longhorn mapping differs')
    ref = pv.get('spec', {}).get('claimRef', {})
    require(ref.get('uid') == expected_claim_uid and ref.get('name') == CLAIM and
            ref.get('namespace') == APP, 'PV belongs to a different claim')
    csi = pv.get('spec', {}).get('csi', {})
    require(csi.get('driver') == 'driver.longhorn.io' and
            csi.get('volumeHandle') == ids['longhorn_volume']['name'], 'PV driver or handle differs')
    pv_inventory = sole_longhorn_pv(pvs, ids['pv'], ids['longhorn_volume']['name'])
    require(pv['spec'].get('persistentVolumeReclaimPolicy') == 'Retain', 'PV Retain policy missing')
    require(claim.get('metadata', {}).get('annotations', {}).get('helm.sh/resource-policy') == 'keep',
            'Claim keep policy missing')
    require(volume.get('spec', {}).get('encrypted') is True and
            type(volume['spec'].get('numberOfReplicas')) is int and
            volume['spec']['numberOfReplicas'] == 2, 'Longhorn encryption/replicas differ')
    require(all(not obj['metadata'].get('deletionTimestamp') for obj in (claim, pv, volume)),
            'Original storage is deleting')
    require(volume.get('status', {}).get('robustness') == 'healthy', 'Longhorn volume is not healthy')
    require(ids['deployment']['name'] == APP and ids['deployment']['namespace'] == APP,
            'Unexpected Deployment identity')
    spec = deployment.get('spec', {})
    require(type(spec.get('replicas')) is int and spec['replicas'] == 1,
            'Exactly one configured BORTUS writer is required')
    require(spec.get('strategy', {}).get('type') == 'Recreate', 'Recreate strategy required')
    require(uses_claim(spec.get('template', {})), 'Deployment does not mount original claim')
    active = [p for p in complete_pods(pods) if uses_claim(p) and
              p.get('status', {}).get('phase') not in ('Succeeded', 'Failed')]
    require(len(active) == 1, 'Unexpected additional or missing claim consumer')
    writer = active[0]
    require(not writer.get('metadata', {}).get('deletionTimestamp'), 'Writer is terminating')
    require(writer.get('status', {}).get('phase') == 'Running' and
            any(c.get('type') == 'Ready' and c.get('status') == 'True'
                for c in writer['status'].get('conditions', [])), 'Writer is not Ready')
    writer_id = identity(writer)
    node_name = writer.get('spec', {}).get('nodeName')
    require(writer_id['namespace'] == APP and type(node_name) is str and
            0 < len(node_name) <= 253 and all(len(label) <= 63 and
                re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?', label)
                for label in node_name.split('.')),
            'Writer placement is incomplete')
    owners = [o for o in writer.get('metadata', {}).get('ownerReferences', []) if o.get('controller') is True]
    require(len(owners) == 1 and owners[0].get('kind') == 'ReplicaSet' and
            owners[0].get('name') == ids['replica_set']['name'] and
            owners[0].get('uid') == ids['replica_set']['uid'],
            'Writer controller is not a ReplicaSet')
    parents = [o for o in replica_set.get('metadata', {}).get('ownerReferences', [])
               if o.get('controller') is True]
    require(ids['replica_set']['namespace'] == APP and len(parents) == 1 and
            parents[0].get('kind') == 'Deployment' and parents[0].get('name') == APP and
            parents[0].get('uid') == ids['deployment']['uid'], 'Writer is not owned by BORTUS Deployment')
    require(ids['helmrelease']['name'] == APP and ids['helmrelease']['namespace'] == 'flux-system',
            'Unexpected HelmRelease identity')
    rspec = release.get('spec', {})
    require(all(rspec.get(key) == APP for key in ('releaseName', 'targetNamespace', 'storageNamespace')),
            'Helm release namespaces differ')
    source = rspec.get('chart', {}).get('spec', {})
    require(source.get('chart') == './charts/bortus' and
            source.get('sourceRef', {}).get('name') == 'branconet-charts', 'Unexpected chart source')
    require(ids['kustomization']['name'] == 'migration-releases' and
            ids['kustomization']['namespace'] == 'flux-system', 'Unexpected Flux owner')
    ospec = owner.get('spec', {})
    require(ospec.get('sourceRef', {}).get('name') == 'branconet-charts' and
            ospec.get('path') == './flux/releases' and ospec.get('prune') is False and
            ospec.get('force', False) is False, 'Unexpected Flux owner contract')
    require(ids['backup_target']['name'] == 'default' and
            ids['backup_target']['namespace'] == 'longhorn-system' and
            target.get('status', {}).get('available') is True, 'Available backup target required')
    report = {
        'scope': 'Read-only BORTUS checkpoint prerequisites; no capture or recovery acceptance',
        'identities': ids, 'writer': writer_id | {'nodeName': writer['spec']['nodeName']},
        'physical_volume_pv_inventory': pv_inventory,
        'checks_passed': True, 'active_claim_consumers': 1, 'encrypted_replicas': 2,
        'preserve_reconcile_state': {
            'helmrelease_suspend': rspec.get('suspend', False),
            'kustomization_suspend': ospec.get('suspend', False)},
        'mutations': 0, 'database_or_secret_reads': 0,
        'cold_capture_proven': False, 'independent_restore_proven': False,
        'separate_resource_reads_are_atomic': False}
    if holder_image is not None:
        require(bool(re.fullmatch(r'[^\s@]+@sha256:[0-9a-f]{64}', holder_image)) and
                ':' not in holder_image.rsplit('/', 1)[-1].split('@', 1)[0],
                'Holder requires an exact tagless digest reference')
        report['holder_proposal'] = {
            'apiVersion': 'v1', 'kind': 'Pod',
            'metadata': {'namespace': APP, 'generateName': 'bortus-checkpoint-'},
            'spec': {
                'nodeName': writer['spec']['nodeName'], 'automountServiceAccountToken': False,
                'restartPolicy': 'Never', 'securityContext': {'runAsNonRoot': True,
                    'runAsUser': 1000, 'runAsGroup': 1000, 'seccompProfile': {'type': 'RuntimeDefault'}},
                'containers': [{'name': 'holder', 'image': holder_image, 'imagePullPolicy': 'Never',
                    'command': ['node', '-e', 'setInterval(()=>{},1000)'],
                    'securityContext': {'allowPrivilegeEscalation': False,
                        'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}},
                    'resources': {'requests': {'cpu': '5m', 'memory': '32Mi'},
                        'limits': {'cpu': '100m', 'memory': '128Mi'}},
                    'volumeMounts': [{'name': 'data', 'mountPath': '/data', 'readOnly': True}]}],
                'volumes': [{'name': 'data', 'persistentVolumeClaim': {
                    'claimName': CLAIM, 'readOnly': True}}]}}
        report['holder_image_qualification_proven'] = False
        report['holder_preload_and_admission_proven'] = False
    return report


class Client:
    def get(self, kind, name=None, namespace=None):
        argv = [str(RUNTIME / 'bin/kubectl'), '--kubeconfig', str(RUNTIME / 'admin.conf'),
                '--request-timeout=20s', 'get']
        if kind == 'pvs':
            require(name is None and namespace is None, 'Cluster PV collection required')
            # Raw collection preserves its RV/continuation instead of kubectl flattening it.
            # One extra item detects the count bound; continuation never means success.
            argv.extend(['--raw', '/api/v1/persistentvolumes?limit=' + str(MAX_PV_ITEMS + 1)])
        elif kind == 'pods':
            require(name is None and namespace == APP, 'BORTUS Pod collection required')
            argv.extend(['--raw', '/api/v1/namespaces/bortus/pods?limit=' + str(MAX_POD_ITEMS + 1)])
        else:
            argv.append(kind)
            if name:
                argv.append(name)
            if namespace:
                argv.extend(['-n', namespace])
            argv.extend(['-o', 'json'])
        result = subprocess.run(argv, capture_output=True, timeout=25)
        require(result.returncode == 0 and len(result.stdout) <= 8 * 1024 * 1024,
                'Bounded read-only API query failed; output withheld')
        try:
            obj = json.loads(result.stdout)
        except (ValueError, UnicodeError):
            raise RuntimeError('Invalid API JSON; output withheld') from None
        require(isinstance(obj, dict), 'Invalid API object')
        if kind == 'pods':
            complete_pods(obj)
        return obj

    def inspect(self, expected_claim_uid, holder_image=None):
        claim = self.get('pvc', CLAIM, APP)
        volume_name = claim.get('spec', {}).get('volumeName')
        require(isinstance(volume_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9.-]*', volume_name),
                'Invalid volume identity')
        pods = self.get('pods', namespace=APP)
        active = [p for p in complete_pods(pods) if uses_claim(p) and
                  p.get('status', {}).get('phase') not in ('Succeeded', 'Failed')]
        require(len(active) == 1, 'Unexpected additional or missing claim consumer')
        controllers = [o for o in active[0].get('metadata', {}).get('ownerReferences', [])
                       if o.get('controller') is True and o.get('kind') == 'ReplicaSet']
        require(len(controllers) == 1 and isinstance(controllers[0].get('name'), str) and
                re.fullmatch(r'[a-z0-9][a-z0-9.-]*', controllers[0]['name']), 'Invalid writer controller')
        return evaluate((claim, self.get('pv', volume_name),
            self.get('volumes.longhorn.io', volume_name, 'longhorn-system'),
            self.get('deployment', APP, APP), pods,
            self.get('helmrelease', APP, 'flux-system'),
            self.get('kustomization', 'migration-releases', 'flux-system'),
            self.get('backuptargets.longhorn.io', 'default', 'longhorn-system'),
            self.get('replicaset', controllers[0]['name'], APP), self.get('pvs')),
            expected_claim_uid, holder_image)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-claim-uid', required=True)
    parser.add_argument('--holder-image')
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        require(not os.path.lexists(args.output), 'Evidence output already exists')
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report = Client().inspect(args.expected_claim_uid, args.holder_image)
        report['collection_started_at_utc'] = started
        report['collection_completed_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(report, out, indent=2)
            out.write('\n')
        print(json.dumps({'checkpoint_preflight_passed': True, 'mutations': 0,
                          'capture_and_restore_pending': True}))
        return 0
    except Exception:
        print('BORTUS checkpoint preflight failed; API output withheld and no mutation performed',
              file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
