"""Exact source-tested image-only JSON patch; preserve every other DS field."""
import json
import subprocess
import sys


def run(args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=90)
    if p.returncode:
        raise ValueError('Guarded proxy request failed; no raw API error emitted')
    return json.loads(p.stdout)


plan = json.load(sys.stdin)
obj = run(['kubectl', '-n', 'kube-system', 'get', 'daemonset', 'kube-proxy', '-o', 'json'])
cs = obj['spec']['template']['spec']['containers']
indexes = [i for i, c in enumerate(cs) if c['name'] == 'kube-proxy']
assert len(indexes) == 1
idx = indexes[0]; old = plan['proxyBeforeImage']; new = plan['images']['kube-proxy']['reference']
assert cs[idx]['image'] == old
path = '/spec/template/spec/containers/' + str(idx) + '/image'
patch = [{'op': 'test', 'path': '/metadata/resourceVersion', 'value': obj['metadata']['resourceVersion']},
         {'op': 'test', 'path': path, 'value': old}, {'op': 'replace', 'path': path, 'value': new}]
changed = run(['kubectl', '-n', 'kube-system', 'patch', 'daemonset', 'kube-proxy', '--type=json', '-p', json.dumps(patch), '-o', 'json'])
cs[idx]['image'] = new
assert changed['metadata']['uid'] == obj['metadata']['uid'] and changed['spec'] == obj['spec']
print(json.dumps({'passed': True, 'imageOnly': True}))
