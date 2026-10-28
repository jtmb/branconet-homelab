#!/usr/bin/env python3
"""Observe real Pi-hole6 export scrapes without exporting DNS labels or secrets."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import uuid

BASE = Path('/home/brajam/.local/share/branconet-migration')
OLD = 'ekofr/pihole-exporter:latest@sha256:36dab68a7e4b2750802e2326d9340201dc498ac429cbd89cdfb45cbab3fef081'
SSH = ['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10',
       '-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@192.168.0.4']
CODE = r'''
import subprocess,json,http.client,re,time,math
get=lambda k,n,ns='pihole':json.loads(subprocess.check_output(['kubectl','-n',ns,'get',k]+([n]if n else [])+['-o','json']))
d=get('deploy','pihole-exporter');h=get('helmrelease','pihole-exporter','flux-system');s=get('service','pihole-exporter')
pods=get('pods','')['items'];pods=[p for p in pods if p['metadata'].get('labels',{}).get('app')=='pihole-exporter'and not p['metadata'].get('deletionTimestamp')];assert len(pods)==1
p=pods[0];assert p['status']['containerStatuses'][0]['ready'] and h['status']['observedGeneration']>=h['metadata']['generation'] and any(x['type']=='Ready'and x['status']=='True'for x in h['status']['conditions'])
spec=d['spec'];c=spec['template']['spec']['containers'][0];assert len(spec['template']['spec']['containers'])==1 and not c.get('env');image=c.pop('image')
assert p['status']['containerStatuses'][0]['imageID'].endswith(image.split('@')[-1])
secret=get('secret','pihole-exporter-runtime');assert c['envFrom']==[{'secretRef':{'name':'pihole-exporter-runtime'}}]
def request(path):
 conn=http.client.HTTPConnection(s['spec']['clusterIP'],9617,timeout=20);conn.request('GET',path);r=conn.getresponse();body=r.read(1024**2+1);assert r.status==200 and len(body)<=1024**2;conn.close();return body.decode()
request('/readiness');request('/liveness');scrapes=[]
for i in range(3):
 text=request('/metrics');names=set();status=[];domains=[]
 for line in text.splitlines():
  if line.startswith('#')or not line:continue
  m=re.fullmatch(r'([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{.*\})?\s+([^ ]+)(?:\s+\d+)?',line)
  if not m:continue
  name,value=m.groups()
  if not name.startswith('pihole_'):continue
  names.add(name);number=float(value);assert math.isfinite(number)
  if name=='pihole_status':status.append(number)
  if name=='pihole_domains_being_blocked':domains.append(number)
 assert len(names)>=10 and status and all(v==1 for v in status)and domains and all(v>0 for v in domains)
 scrapes.append({'metricNames':sorted(names),'healthyStatusSeries':len(status),'positiveGravitySeries':len(domains),'responseBytes':len(text.encode())})
 if i<2:time.sleep(1)
print(json.dumps({'deploymentUID':d['metadata']['uid'],'releaseUID':h['metadata']['uid'],'serviceUID':s['metadata']['uid'],'serviceSpec':s['spec'],'specWithoutImage':spec,'secret':{'uid':secret['metadata']['uid'],'resourceVersion':secret['metadata']['resourceVersion']},'image':image,'imageID':p['status']['containerStatuses'][0]['imageID'],'podUID':p['metadata']['uid'],'restartCount':p['status']['containerStatuses'][0]['restartCount'],'scrapes':scrapes,'readiness':True,'liveness':True,'privateDNSLabelsExported':False}))
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--baseline',type=Path);p.add_argument('--image',default=OLD);a=p.parse_args()
    assert a.output_dir.resolve()==a.output_dir and BASE in a.output_dir.parents
    a.output_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
    r=subprocess.run(SSH+[shlex.join(['python3','-B','-c',CODE])],capture_output=True,timeout=100)
    assert r.returncode==0 and len(r.stdout)<=1024**2,'bounded_exporter_observation_failed'
    d=json.loads(r.stdout);assert d['image']==a.image,'exact_exporter_image'
    if a.baseline:
        assert a.baseline.parent==a.output_dir;b=json.loads(a.baseline.read_bytes());assert b['passed']
        assert all(d[k]==b[k]for k in ['deploymentUID','releaseUID','serviceUID','serviceSpec','specWithoutImage','secret']),'original_exporter_wiring_changed'
        assert d['podUID']!=b['podUID'] and all(x['metricNames']==b['scrapes'][0]['metricNames']for x in d['scrapes']),'original_metrics_or_pod_not_preserved'
    d.update(passed=True,observedUTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),sourceSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    out=a.output_dir/('exporter-'+uuid.uuid4().hex+'.json')
    with out.open('x')as f:json.dump(d,f,indent=2,sort_keys=True)
    out.chmod(0o600);print(json.dumps({'passed':True,'receipt':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'realScrapes':len(d['scrapes'])}))


if __name__=='__main__':main()
