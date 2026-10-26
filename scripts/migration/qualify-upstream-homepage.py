#!/usr/bin/env python3
"""Observe original Homepage state/routes on old, adopted and restart Pods.

Configuration and API bodies stay in RAM; only keyed hashes/counts are saved in
the existing private F-backed output root. No cluster objects or app data change.
"""
import argparse
import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import shlex
import subprocess

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
OLD = 'docker.io/library/homepage-security-20261023@sha256:7f91e85fa5d394b4be0f60686e40bf93e28e7ca0074c60754f3f02a1caa66bd4'
NEW = 'ghcr.io/gethomepage/homepage:v2.7.0@sha256:19c5c09184458a41b7b5915e71463a39f36cd33540f41bdbed008791b8182d5f'
CHILD = 'sha256:f1c9e802a0b9de6f64ef8d3e3d3aac4283f250e0a8ff5ebd170d791811431c99'

NODE = r'''
const fs=require('fs'),crypto=require('crypto'),path=require('path');
const key=Buffer.from(fs.readFileSync(0,'utf8').trim(),'hex');if(key.length!==32)throw Error();
const entries={};let bytes=0;const root='/app/config';
function walk(rel){
 for(const name of fs.readdirSync(path.join(root,rel))){
  const n=path.posix.join(rel,name);if(n==='logs'||n.startsWith('logs/'))continue;
  if(Object.keys(entries).length>=4096)throw Error();
  const f=path.join(root,n),s=fs.lstatSync(f),row={uid:s.uid,gid:s.gid,mode:s.mode&4095};
  if(s.isSymbolicLink()){row.kind='symlink';row.targetHMAC=crypto.createHmac('sha256',key).update(fs.readlinkSync(f)).digest('hex');}
  else if(s.isDirectory()){row.kind='directory';entries[n]=row;walk(n);continue;}
  else{
   if(!s.isFile()||s.size>134217728)throw Error();bytes+=s.size;if(bytes>134217728)throw Error();
   row.kind='file';row.bytes=s.size;row.hmac=crypto.createHmac('sha256',key).update(fs.readFileSync(f)).digest('hex');
  }
  entries[n]=row;
 }
}
walk('');if(Object.keys(entries).length<8)throw Error();
process.stdout.write(JSON.stringify({entries,bytes,nodeVersion:process.version,
 authEnabled:process.env.HOMEPAGE_AUTH_ENABLED==='true',mcpEnabled:process.env.HOMEPAGE_MCP_ENABLED==='true'}));
'''

# Executed on the existing master; no remote files, keys or receipts are written.
REMOTE_HTTP = r'''
import sys,json,urllib.request,http.client,ssl,hashlib,hmac
p=json.loads(sys.stdin.buffer.read(1048576));key=bytes.fromhex(p['key']);assert len(key)==32
def mac(v):return hmac.new(key,json.dumps(v,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()
rows={};apis={};certs={};client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
for name in ['services','bookmarks','widgets']:
 with client.open(urllib.request.Request('http://'+p['serviceIP']+':3000/api/'+name,headers={'Host':'homepage.branconet.lan'}),timeout=20)as r:
  b=r.read(2097153);assert r.status==200 and len(b)<=2097152;v=json.loads(b);assert isinstance(v,list)and v
  apis[name]={'count':len(v),'contentHMAC':mac(v)}
for ip in ['192.168.0.4','192.168.0.5','192.168.0.6']:
 for host in p['hosts']:
  for port,secure in [(80,False),(443,True)]:
   if secure and host not in p['tlsHosts']:continue
   c=http.client.HTTPConnection(ip,port,timeout=20);trusted=None;error=None
   try:
    if secure:
     try:c.connect();c.sock=ssl.create_default_context().wrap_socket(c.sock,server_hostname=host);trusted=True
     except ssl.SSLCertVerificationError as e:
      error=e.verify_code;c.close();c=http.client.HTTPConnection(ip,port,timeout=20);c.connect()
      context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
      c.sock=context.wrap_socket(c.sock,server_hostname=host);trusted=False
     fingerprint=hashlib.sha256(c.sock.getpeercert(binary_form=True)).hexdigest()
     identity=ip+':'+host;certs[identity]={'sha256':fingerprint,'trustedHostnameAndChain':trusted,'verificationErrorCode':error}
     if p.get('baselineCertificates'):assert certs[identity]==p['baselineCertificates'][identity]
    for path in ['/','/api/healthcheck']:
     c.request('GET',path,headers={'Host':host,'Accept-Encoding':'identity'});r=c.getresponse();b=r.read(2097153)
     assert r.status==200 and len(b)<=2097152
     if path=='/':assert b'__NEXT_DATA__'in b or b'/_next/'in b
     else:assert b==b'up'
     rows[ip+':'+str(port)+':'+host+path]={'status':r.status,'bytes':len(b),'htmlApp':path=='/'}
   finally:c.close()
print(json.dumps({'routes':rows,'api':apis,'certificates':certs}))
'''


def need(ok, why):
    if not ok:
        raise ValueError(why)


def call(args, data=None):
    p = subprocess.run(SSH + [shlex.join(args)], input=data, capture_output=True, timeout=120)
    need(p.returncode == 0 and len(p.stdout) <= 8 * 1024**2, 'bounded_readonly_cluster_operation')
    return p.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['baseline', 'after', 'restart'])
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--expected-revision', required=True)
    a = parser.parse_args()
    os.umask(0o077)
    need(a.output_dir.resolve() == a.output_dir and ROOT in a.output_dir.parents
         and len(a.expected_revision) == 40, 'private_existing_root_and_exact_revision')
    a.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = a.output_dir / (a.phase + '.json')
    need(not target.exists(), 'immutable_observation')
    kp = a.output_dir / 'observation.key'
    if not kp.exists():
        need(a.phase == 'baseline', 'baseline_key_required')
        with kp.open('xb') as f:
            f.write(os.urandom(32))
    key = kp.read_bytes()
    need(len(key) == 32 and not kp.stat().st_mode & 0o077, 'protected_key')
    mac = lambda v: hmac.new(key, json.dumps(v, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()
    def get(kind, name, ns='homepage'):
        return json.loads(call(['kubectl', '-n', ns, 'get', kind, name, '-o', 'json']))
    dep = get('deployment', 'homepage')
    hr = get('helmrelease', 'homepage', 'flux-system')
    pvc = get('pvc', 'homepage-data-1')
    need(dep['metadata']['uid'] == '67484b9d-4971-4840-9385-5478fb0b6b32'
         and hr['metadata']['uid'] == '0abccce8-85f7-49df-baea-7825262a258e'
         and pvc['metadata']['uid'] == 'f1eb8c61-46dc-4743-b5e4-b7ce75110189'
         and pvc['status']['phase'] == 'Bound', 'original_controller_release_claim')
    need(dep['spec']['replicas'] == 1 and dep['status'].get('observedGeneration') == dep['metadata']['generation']
         and all(dep['status'].get(k) == 1 for k in ['replicas', 'updatedReplicas', 'readyReplicas', 'availableReplicas'])
         and hr['status'].get('observedGeneration') == hr['metadata']['generation']
         and any(c['type'] == 'Ready' and c['status'] == 'True' for c in hr['status'].get('conditions', [])), 'ready_owned_workload')
    source = get('gitrepository', 'branconet-charts', 'flux-system')
    need(source['status']['artifact']['revision'] == 'validated@sha1:' + a.expected_revision
         and hr['status']['lastAttemptedRevision'].endswith(a.expected_revision[:12]), 'exact_flux_revision')
    pods = json.loads(call(['kubectl', '-n', 'homepage', 'get', 'pods', '-l', 'app=homepage', '-o', 'json']))['items']
    need(len(pods) == 1 and not pods[0]['metadata'].get('deletionTimestamp'), 'one_current_pod')
    pod = pods[0]
    image = OLD if a.phase == 'baseline' else NEW
    cs = pod['status']['containerStatuses'][0]
    need(pod['status']['phase'] == 'Running' and cs['ready'] and pod['spec']['containers'][0]['image'] == image
         and cs['imageID'].rsplit('@', 1)[-1] in [image.rsplit('@', 1)[-1], CHILD if a.phase != 'baseline' else image.rsplit('@', 1)[-1]], 'exact_image_and_platform')
    spec = json.loads(json.dumps(dep['spec']))
    spec['template']['spec']['containers'][0]['image'] = '<maintained-image>'
    annotations = spec['template']['metadata'].get('annotations', {})
    annotations.pop('branconet.lan/security-restart', None)
    if not annotations:
        spec['template']['metadata'].pop('annotations', None)
    pv = get('pv', pvc['spec']['volumeName'])
    need(pv['spec']['csi']['driver'] == 'driver.longhorn.io' and pv['spec']['claimRef']['uid'] == pvc['metadata']['uid'], 'same_longhorn_claim')
    service = get('service', 'homepage')
    stable = {'deploymentUID': dep['metadata']['uid'], 'releaseUID': hr['metadata']['uid'], 'specHMAC': mac(spec),
              'pvcUID': pvc['metadata']['uid'], 'pvcSpecHMAC': mac(pvc['spec']), 'pvUID': pv['metadata']['uid'],
              'pvSpecHMAC': mac(pv['spec']), 'serviceUID': service['metadata']['uid'], 'serviceSpecHMAC': mac(service['spec'])}
    stable['secrets'] = {}
    for name in ['homepage-runtime', 'homepage-rendered-config']:
        secret = get('secret', name)
        stable['secrets'][name] = {'uid': secret['metadata']['uid'], 'rv': secret['metadata']['resourceVersion'],
                                 'type': secret['type'], 'dataHMAC': mac(secret.get('data', {}))}
    stable['rbac'] = {}
    for kind, name in [('serviceaccount', 'homepage'), ('clusterrole', 'homepage-read'), ('clusterrolebinding', 'homepage-read')]:
        r = get(kind, name)
        stable['rbac'][kind + '/' + name] = {'uid': r['metadata']['uid'],
            'bodyHMAC': mac({k: v for k, v in r.items() if k not in ['metadata', 'status', 'apiVersion', 'kind']})}
    ingresses = [get('ingress', 'homepage-' + suffix) for suffix in ['http', 'https']]
    stable['ingresses'] = {r['metadata']['name']: {'uid': r['metadata']['uid'], 'specHMAC': mac(r['spec']),
        'annotationsHMAC': mac(r['metadata'].get('annotations', {}))} for r in ingresses}
    hosts = sorted({r['host'] for i in ingresses for r in i['spec']['rules']})
    tls_hosts = sorted({h for i in ingresses for t in i['spec'].get('tls', []) for h in t.get('hosts', [])})
    tls_hosts = sorted(set(tls_hosts) | {rule['host'] for i in ingresses
        if i['metadata'].get('annotations', {}).get('traefik.ingress.kubernetes.io/router.tls') == 'true'
        for rule in i['spec']['rules']})
    need(hosts and tls_hosts, 'existing_http_and_tls_routes')
    config = json.loads(call(['kubectl', '-n', 'homepage', 'exec', '-i', pod['metadata']['name'], '--', 'node', '-e', NODE], key.hex().encode()))
    stable.update(configEntries=config['entries'], authEnabled=config['authEnabled'], mcpEnabled=config['mcpEnabled'])
    baseline_certificates = None
    if a.phase != 'baseline':
        baseline_certificates = json.loads((a.output_dir / 'baseline.json').read_bytes())['stable']['certificates']
    observed = json.loads(call(['python3', '-c', REMOTE_HTTP], json.dumps({'key': key.hex(), 'serviceIP': service['spec']['clusterIP'],
        'hosts': hosts, 'tlsHosts': tls_hosts, 'baselineCertificates': baseline_certificates}).encode()))
    stable['api'] = observed['api']
    stable['certificates'] = observed['certificates']
    mismatches = []
    if a.phase != 'baseline':
        before = json.loads((a.output_dir / 'baseline.json').read_bytes())
        need(before['passed'] and before['keyBinding'] == mac('homepage-upstream-v1'), 'exact_original_baseline')
        mismatches = [k for k, v in before['stable'].items() if stable.get(k) != v]
        need(pod['metadata']['uid'] != before['podUID'], 'new_adoption_pod')
        if a.phase == 'restart':
            prior = json.loads((a.output_dir / 'after.json').read_bytes())
            need(prior['passed'] and prior['podUID'] != pod['metadata']['uid'], 'different_restart_pod')
    need(get('deployment', 'homepage')['metadata']['resourceVersion'] == dep['metadata']['resourceVersion'], 'stable_observation_generation')
    result = {'phase': a.phase, 'passed': not mismatches, 'mismatches': mismatches, 'stable': stable,
              'keyBinding': mac('homepage-upstream-v1'), 'podUID': pod['metadata']['uid'], 'image': image,
              'imageID': cs['imageID'], 'restartCount': cs['restartCount'], 'configBytes': config['bytes'],
              'configEntries': len(config['entries']), 'nodeVersion': config['nodeVersion'], 'routes': observed['routes'],
              'fluxRevision': source['status']['artifact']['revision'], 'browserAccepted': False,
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with target.open('xb') as f:
        f.write((json.dumps(result, sort_keys=True, indent=2) + '\n').encode())
    print(json.dumps({k: v for k, v in result.items() if k not in ['stable', 'keyBinding', 'routes']}))
    return int(bool(mismatches))


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'passed': False, 'errorCategory': str(error) if type(error) is ValueError else type(error).__name__, 'rawDetailsSuppressed': True}))
        raise SystemExit(1)
