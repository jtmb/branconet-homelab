"""Read-only drain inventory; refuse unowned pods and unreviewed emptyDir loss."""
import json
import subprocess
import sys


def inspect(items, node, allow_emptydir, allowlist):
    objects = {(o['kind'], o['metadata'].get('namespace', ''), o['metadata']['name']): o for o in items}
    approved, blocked, unmanaged = [], [], []
    for pod in items:
        if pod['kind'] != 'Pod' or pod['spec'].get('nodeName') != node:
            continue
        meta = pod['metadata']; ns = meta['namespace']; name = meta['name']
        if meta.get('annotations', {}).get('kubernetes.io/config.mirror') or pod.get('status', {}).get('phase') in ('Succeeded', 'Failed'):
            continue
        owner = next((o for o in meta.get('ownerReferences', []) if o.get('controller')), None)
        if not owner:
            unmanaged.append(ns + '/' + name)
            continue
        if owner['kind'] == 'DaemonSet':
            continue
        if owner['kind'] == 'ReplicaSet':
            rs = objects.get(('ReplicaSet', ns, owner['name']))
            if not rs or rs['metadata']['uid'] != owner['uid']:
                unmanaged.append(ns + '/' + name)
                continue
            owner = next((o for o in rs['metadata'].get('ownerReferences', []) if o.get('controller')), None)
        if not owner:
            unmanaged.append(ns + '/' + name)
            continue
        for volume in pod['spec'].get('volumes', []):
            if 'emptyDir' not in volume:
                continue
            paths = sorted({m['mountPath'] for c in pod['spec'].get('containers', []) + pod['spec'].get('initContainers', []) for m in c.get('volumeMounts', []) if m['name'] == volume['name']})
            identity = ns + '/' + owner['kind'] + '/' + owner['name'] + '/' + volume['name']
            entries = [identity + '@' + path for path in paths]
            if allow_emptydir and entries and all(e in allowlist for e in entries):
                approved.extend(entries)
            else:
                blocked.append({'pod': ns + '/' + name, 'identity': identity, 'mount_paths': paths})
    return {'node': node, 'approved_emptydirs': sorted(set(approved)), 'unapproved_emptydirs': blocked, 'unmanaged_pods': unmanaged}


def main():
    node, enabled, encoded = sys.argv[1:]
    result = subprocess.run(['kubectl', 'get', 'pods,replicasets', '-A', '-o', 'json'], capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise SystemExit('Read-only drain inventory failed; no raw API error is emitted')
    report = inspect(json.loads(result.stdout)['items'], node, enabled == 'true', set(json.loads(encoded)))
    print(json.dumps(report, sort_keys=True))
    return int(bool(report['unapproved_emptydirs'] or report['unmanaged_pods']))


if __name__ == '__main__':
    raise SystemExit(main())
