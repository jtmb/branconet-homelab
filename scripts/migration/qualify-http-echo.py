#!/usr/bin/env python3
"""Observe exact http-echo deployment/bindings and real Service/ingress replies."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import uuid

BASE = Path('/home/brajam/.local/share/branconet-migration')
OLD = 'hashicorp/http-echo@sha256:fcb75f691c8b0414d670ae570240cbf95502cc18a9ba57e982ecac589760a186'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
OBSERVE = r'''
import subprocess,json,hashlib,http.client
get=lambda k,n,ns='http-echo':json.loads(subprocess.check_output(['kubectl','-n',ns,'get',k]+([n]if n else [])+['-o','json']))
d=get('deploy','http-echo');h=get('helmrelease','http-echo','flux-system');c=get('pvc','http-echo-data-pvc');v=get('pv',c['spec']['volumeName']);s=get('service','http-echo')
pods=get('pods','')['items'];pods=[x for x in pods if x['metadata'].get('labels',{}).get('app')=='http-echo' and not x['metadata'].get('deletionTimestamp')]
assert len(pods)==1 and pods[0]['status']['containerStatuses'][0]['ready']
assert d['metadata']['uid']=='77539818-3671-450c-ae58-154a63a41493' and h['metadata']['uid']=='7cd0399f-8856-422d-9b02-4a14264a65c7'
assert not h['spec'].get('suspend',False) and h['status']['observedGeneration']>=h['metadata']['generation'] and any(x['type']=='Ready' and x['status']=='True' for x in h['status']['conditions'])
spec=d['spec'];container=spec['template']['spec']['containers'][0];assert len(spec['template']['spec']['containers'])==1 and not container.get('env') and not container.get('envFrom')
image=container.pop('image');status=pods[0]['status']['containerStatuses'][0];assert status['imageID'].endswith(image.split('@')[-1])
def response(host,port,virtual_host=None):
 connection=http.client.HTTPConnection(host,port,timeout=10);connection.request('GET','/',headers={'Host':virtual_host}if virtual_host else {})
 r=connection.getresponse();raw=r.read(16385);assert len(raw)<=16384 and r.status in [200,301,302,307,308];out={'status':r.status,'bodySHA256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'version':r.getheader('X-App-Version'),'location':r.getheader('Location')};connection.close();return out
internal=response(s['spec']['clusterIP'],80);assert internal['status']==200
ing=get('ingress','')['items'];ingress={x['metadata']['name']:{'uid':x['metadata']['uid'],'spec':x['spec']}for x in ing}
hosts=sorted({r['host']for x in ing for r in x['spec'].get('rules',[])})
assert hosts and all(x=='http-echo.branconet.local' for x in hosts)
routes={ip+'/'+host:response(ip,80,host)for ip in ['192.168.0.4','192.168.0.5','192.168.0.6']for host in hosts}
print(json.dumps({'deploymentUID':d['metadata']['uid'],'releaseUID':h['metadata']['uid'],'claimUID':c['metadata']['uid'],'pvUID':v['metadata']['uid'],'serviceUID':s['metadata']['uid'],'serviceSpec':s['spec'],'specWithoutImage':spec,'ingress':ingress,'image':image,'imageID':status['imageID'],'podUID':pods[0]['metadata']['uid'],'secretReferences':[],'serviceReply':internal,'ingressReplies':routes,'tlsAcceptanceClaimed':False}))
'''


def main():
    p = argparse.ArgumentParser(); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--image', default=OLD); p.add_argument('--baseline', type=Path); a = p.parse_args()
    assert a.output_dir.resolve() == a.output_dir and BASE in a.output_dir.parents
    a.output_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    result = subprocess.run(SSH + [shlex.join(['python3', '-B', '-c', OBSERVE])],
                            capture_output=True, timeout=90)
    assert result.returncode == 0 and len(result.stdout) <= 1024**2, 'bounded_remote_observation'
    report = json.loads(result.stdout); assert report['image'] == a.image, 'exact_image'
    report['passed'] = False
    if a.baseline:
        assert a.baseline.parent == a.output_dir
        before = json.loads(a.baseline.read_bytes()); assert before['passed']
        fields = ['deploymentUID','releaseUID','claimUID','pvUID','serviceUID','serviceSpec',
                  'specWithoutImage','ingress','secretReferences','serviceReply','ingressReplies']
        assert all(before[k] == report[k] for k in fields), 'original_bindings_spec_and_http_replies'
        assert before['podUID'] != report['podUID'], 'new_ready_pod'
    report.update(passed=True, observedUTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  sourceSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    out = a.output_dir / ('http-echo-' + uuid.uuid4().hex + '.json')
    with out.open('x') as stream: json.dump(report, stream, indent=2, sort_keys=True)
    out.chmod(0o600)
    print(json.dumps({'passed': True, 'receipt': str(out), 'sha256': hashlib.sha256(out.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
