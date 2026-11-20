"""Metadata-only recovery gate for the original volumes and active controllers."""
import json
import subprocess
import sys


def identity(obj):
    meta = obj['metadata']
    return (obj['kind'], meta.get('namespace', ''), meta['name'])


def freeze(items):
    frozen = []
    for obj in items:
        kind = obj['kind']; spec = obj.get('spec', {}); status = obj.get('status', {})
        if kind == 'Volume' and status.get('state') != 'attached':
            continue
        if kind in ('Deployment', 'StatefulSet') and spec.get('replicas', 1) <= 0:
            continue
        if kind not in ('Volume', 'Deployment', 'StatefulSet', 'DaemonSet'):
            continue
        meta = obj['metadata']
        frozen.append({'kind': kind, 'namespace': meta.get('namespace', ''), 'name': meta['name'],
                       'uid': meta['uid'], 'replicas': status.get('desiredNumberScheduled', 0) if kind == 'DaemonSet' else spec.get('replicas', 1),
                       'generation': meta.get('generation', 0),
                       'ready_replicas_before': status.get('readyReplicas', 0)})
    return frozen


def check(items, frozen):
    current = {identity(obj): obj for obj in items}
    errors = []
    for expected in frozen:
        key = (expected['kind'], expected['namespace'], expected['name'])
        obj = current.get(key)
        reason = None
        if not obj or obj['metadata']['uid'] != expected['uid']:
            reason = 'original resource missing or replaced'
        elif expected['kind'] == 'Volume':
            status = obj.get('status', {})
            if status.get('state') != 'attached' or status.get('robustness') != 'healthy':
                reason = 'original attached volume is not attached and healthy'
        elif expected['kind'] == 'DaemonSet':
            status = obj.get('status', {}); desired = expected['replicas']
            if status.get('desiredNumberScheduled', 0) != desired:
                reason = 'original daemonset scheduling count changed'
            elif status.get('observedGeneration', 0) < obj['metadata'].get('generation', 0):
                reason = 'daemonset has not observed its current generation'
            elif any(status.get(key, 0) < desired for key in ('numberReady', 'numberAvailable', 'updatedNumberScheduled')):
                reason = 'original daemonset readiness or update incomplete'
        else:
            spec = obj.get('spec', {}); status = obj.get('status', {}); desired = expected['replicas']
            if spec.get('replicas', 1) != desired:
                reason = 'original desired replica count changed'
            elif status.get('observedGeneration', 0) < obj['metadata'].get('generation', 0):
                reason = 'controller has not observed its current generation'
            elif status.get('readyReplicas', 0) < desired:
                reason = 'original active controller has insufficient Ready replicas'
            elif expected['kind'] == 'Deployment' and (status.get('availableReplicas', 0) < desired or status.get('updatedReplicas', 0) < desired):
                reason = 'deployment availability or updated replicas incomplete'
        if reason:
            errors.append({'kind': key[0], 'namespace': key[1], 'name': key[2], 'reason': reason})
    return errors


def main():
    mode = sys.argv[1]
    result = subprocess.run(['kubectl', 'get', 'deployments,statefulsets,daemonsets,volumes.longhorn.io', '-A', '-o', 'json'], capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise SystemExit('Read-only recovery inventory failed; no raw API error is emitted')
    items = json.loads(result.stdout)['items']
    frozen = freeze(items) if mode == 'freeze' else json.loads(sys.argv[2])
    if not frozen or not any(o['kind'] == 'Volume' for o in frozen):
        raise SystemExit('Original attached volume inventory is empty; refuse maintenance')
    errors = check(items, frozen)
    report = {'ready': not errors, 'errors': errors}
    if mode == 'freeze':
        report['frozen'] = frozen
    print(json.dumps(report, sort_keys=True))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
