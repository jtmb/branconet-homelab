#!/usr/bin/env python3
"""Read-only Homepage configuration, Native Secret, PVC and HTTP before/after proof.

Execute on masternode with an existing32-byte hex HMAC key on stdin. Only counts,
file hashes/HMACs, resource identities and booleans enter a protected receipt.
Configuration/API responses never leave cluster-node RAM. Logs are mutable;
the independent cold archive includes them, this observer compares configuration.
"""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import resource
import socket
import subprocess
import sys
import urllib.request

NS = 'homepage'
DEP = '67484b9d-4971-4840-9385-5478fb0b6b32'
PVC = 'f1eb8c61-46dc-4743-b5e4-b7ce75110189'


def need(ok):
    if not ok:
        raise ValueError('Homepage qualification refused; raw details suppressed')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def kube(*args, data=None):
    p = subprocess.run(['kubectl', '--request-timeout=20s', '-n', NS, *args],
        input=data, capture_output=True, timeout=25)
    need(p.returncode == 0 and len(p.stdout) <= 4 * 1024**2)
    return p.stdout


def obj(kind, name):
    return json.loads(kube('get', kind, name, '-o', 'json'))


NODE = r"""
const fs=require('fs'),crypto=require('crypto'),path=require('path');
const key=Buffer.from(fs.readFileSync(0,'utf8').trim(),'hex');if(key.length!==32)throw Error();
const dir='/app/config';const result={};
for(const name of fs.readdirSync(dir)){
 if(!/\.(yaml|yml|js|css|json)$/.test(name))continue;
 const f=path.join(dir,name),s=fs.statSync(f);if(!s.isFile()||s.size>4194304)throw Error();
 result[name]={hmac:crypto.createHmac('sha256',key).update(fs.readFileSync(f)).digest('hex'),
   bytes:s.size,uid:s.uid,gid:s.gid,mode:s.mode&4095};
}
if(Object.keys(result).length<8||Object.keys(result).length>100)throw Error();
process.stdout.write(JSON.stringify(result));
"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['baseline', 'after'])
    p.add_argument('--image', required=True)
    p.add_argument('--runtime', required=True)
    p.add_argument('--baseline', type=Path)
    p.add_argument('--receipt', type=Path, required=True)
    a = p.parse_args()
    need(socket.gethostname().split('.')[0].lower() == 'masternode')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.umask(0o077)
    key = bytes.fromhex(sys.stdin.read(66).strip())
    need(len(key) == 32)
    mac = lambda v: hmac.new(key, canonical(v), hashlib.sha256).hexdigest()
    need(a.receipt.is_absolute() and not a.receipt.exists() and a.receipt.resolve() == a.receipt and
         not a.receipt.parent.stat().st_mode & 0o077)
    dep = obj('deployment', 'homepage')
    need(dep['metadata']['uid'] == DEP and dep['spec']['replicas'] == 1 and
         dep['status'].get('updatedReplicas') == 1 and dep['status'].get('readyReplicas') == 1)
    spec = dep['spec']['template']['spec']
    need(len(spec['containers']) == 1 and spec['containers'][0]['image'] == a.image)
    pods = json.loads(kube('get', 'pods', '-o', 'json'))['items']
    pods = [x for x in pods if x['metadata']['name'].startswith('homepage-') and not x['metadata'].get('deletionTimestamp')]
    need(len(pods) == 1)
    pod = pods[0]
    statuses = pod['status']['containerStatuses']
    need(pod['status']['phase'] == 'Running' and len(statuses) == 1 and statuses[0]['ready'] and
         pod['spec']['containers'][0]['image'] == a.image and statuses[0]['imageID'].rsplit('@', 1)[-1] == a.runtime)
    pvc = obj('pvc', 'homepage-data-1')
    need(pvc['metadata']['uid'] == PVC and pvc['status']['phase'] == 'Bound')
    resources = {}
    for volume in spec.get('volumes', []):
        if 'secret' in volume:
            name = volume['secret']['secretName']
            r = obj('secret', name)
            resources['secret/' + name] = {'uid': r['metadata']['uid'], 'rv': r['metadata']['resourceVersion'], 'content': mac(r.get('data', {}))}
        if 'configMap' in volume:
            name = volume['configMap']['name']
            r = obj('configmap', name)
            resources['configmap/' + name] = {'uid': r['metadata']['uid'], 'rv': r['metadata']['resourceVersion'], 'content': mac(r.get('data', {}))}
    for c in spec['containers']:
        names = {x['secretRef']['name'] for x in c.get('envFrom', []) if 'secretRef' in x}
        names |= {x['valueFrom']['secretKeyRef']['name'] for x in c.get('env', []) if 'secretKeyRef' in x.get('valueFrom', {})}
        for name in names:
            r = obj('secret', name)
            resources['secret/' + name] = {'uid': r['metadata']['uid'], 'rv': r['metadata']['resourceVersion'], 'content': mac(r.get('data', {}))}
    files = json.loads(kube('exec', '-i', pod['metadata']['name'], '--', 'node', '-e', NODE, data=key.hex().encode()))
    service = obj('service', 'homepage')
    ports = service['spec']['ports']
    need(len(ports) == 1)
    base = 'http://' + service['spec']['clusterIP'] + ':' + str(ports[0]['port'])
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    http = {}
    for path in ['/', '/api/healthcheck']:
        request = urllib.request.Request(base + path, headers={'Host': 'homepage.branconet.lan'})
        with client.open(request, timeout=15) as response:
            body = response.read(2 * 1024**2 + 1)
            need(response.status == 200 and len(body) <= 2 * 1024**2)
            http[path] = {'status': response.status, 'bytes': len(body)}
    normalized = json.loads(json.dumps(dep['spec']))
    normalized['template']['spec']['containers'][0]['image'] = '<maintenance-image>'
    stable = {'deployment': DEP, 'spec_hmac': mac(normalized), 'pvc': PVC, 'pvc_spec_hmac': mac(pvc['spec']),
              'resources': resources, 'files': files, 'service_uid': service['metadata']['uid'], 'service_spec_hmac': mac(service['spec'])}
    failures = []
    if a.mode == 'after':
        need(a.baseline and a.baseline.is_absolute() and not a.baseline.stat().st_mode & 0o077)
        old = json.loads(a.baseline.read_bytes())
        need(old['passed'] and old['mode'] == 'baseline' and old['key_binding'] == mac('homepage-v1'))
        failures = [k for k, v in old['stable'].items() if stable.get(k) != v]
    receipt = {'mode': a.mode, 'passed': not failures, 'failures': failures, 'stable': stable,
        'key_binding': mac('homepage-v1'), 'image': a.image, 'pod_uid': pod['metadata']['uid'],
        'restart_count': statuses[0]['restartCount'], 'configuration_file_count': len(files), 'http': http,
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'cold_copy_or_restore_claimed': False, 'browser_validation_complete': False}
    with os.fdopen(os.open(a.receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as f:
        json.dump(receipt, f, sort_keys=True, indent=2)
    print(json.dumps({'passed': not failures, 'failures': failures, 'config_files': len(files), 'http': http}))
    return 1 if failures else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print(json.dumps({'passed': False, 'raw_details_suppressed': True}))
        raise SystemExit(1)
