#!/usr/bin/env python3
"""Operator-only exporter adoption: real authenticated metrics, no credential output."""
import argparse,json,os,hashlib,subprocess,shlex,traceback,uuid
from pathlib import Path
C=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/operator-control')
PROGRAM=r'''
import json,sys,subprocess,urllib.request,copy,re,datetime,hashlib,ipaddress
r=json.load(sys.stdin);phase=r['phase'];name='pihole-exporter';ns='pihole'
def get(kind,name=None):
 p=subprocess.run(['kubectl','-n',ns,'get',kind,*([name]if name else []),'-o','json'],capture_output=True,timeout=40);assert p.returncode==0;return json.loads(p.stdout)
d=get('deployment',name);assert d['spec']['replicas']==1 and d['status'].get('availableReplicas')==1
pods=[p for p in get('pods')['items']if p['metadata'].get('labels',{}).get('app')==name and p['status']['phase']not in ['Failed','Succeeded']];assert len(pods)==1;p=pods[0]
assert not p['metadata'].get('deletionTimestamp')and p['status']['containerStatuses'][0]['ready'];c=p['spec']['containers'][0];status=p['status']['containerStatuses'][0]
assert c['image']==r['image']and status['imageID'].endswith('@'+r['image'].split('@')[1])
owner=next(x for x in p['metadata']['ownerReferences']if x.get('controller'));rs=get('replicaset',owner['name']);assert rs['metadata']['uid']==owner['uid']and any(x.get('controller')and x['uid']==d['metadata']['uid']for x in rs['metadata']['ownerReferences'])
assert not any('persistentVolumeClaim'in v for v in p['spec'].get('volumes',[]))
s=get('secret','pihole-exporter-runtime');secret={'uid':s['metadata']['uid'],'resourceVersion':s['metadata']['resourceVersion'],'type':s['type'],'keys':sorted(s.get('data',{}))};s.clear()
services={x['metadata']['name']:{'uid':x['metadata']['uid'],'spec':x['spec']}for x in get('services')['items']if x['spec'].get('selector',{}).get('app')==name}
service=get('service',name);address=ipaddress.ip_address(service['spec']['clusterIP']);assert address.is_private;opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def request(base,path):
 with opener.open(base+path,timeout=40)as response:
  raw=response.read(2*1024**2+1);assert len(raw)<=2*1024**2 and response.status==200;return raw
base='http://'+str(address)+':9617';checks={path:{'status':200,'bytes':len(request(base,path))}for path in ['/readiness','/liveness']}
raw=request(base,'/metrics');text=raw.decode();families=sorted(set(re.findall(r'^# TYPE ([a-zA-Z_:][a-zA-Z0-9_:]*) ',text,re.M)));pi=[x for x in families if x.startswith('pihole_')];assert len(pi)>=10
samples={}
for metric in ['pihole_dns_queries_today','pihole_domains_being_blocked','pihole_status']:
 values=re.findall(r'^'+metric+r'(?:\{[^\n]*\})?\s+([0-9.eE+-]+)$',text,re.M)
 if values:samples[metric]=[float(x)for x in values]
assert samples.get('pihole_dns_queries_today')and any(x>0 for x in samples['pihole_dns_queries_today'])
routes=[]
for ip in ['192.168.0.4','192.168.0.5','192.168.0.6']:
 body=request('http://'+ip+':9617','/metrics');assert b'pihole_dns_queries_today'in body;routes.append({'node':ip,'status':200,'piholeMetricsPresent':True})
out={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':phase,'deploymentUID':d['metadata']['uid'],'spec':d['spec'],'podUID':p['metadata']['uid'],'image':c['image'],'imageID':status['imageID'],'restartCount':status['restartCount'],'nativeSecretMetadata':secret,'services':services,'healthChecks':checks,'metricFamilies':families,'piholeMetricFamilies':pi,'aggregateSamples':samples,'publishedRoutes':routes,'metricsBodyStored':False}
if phase=='after':
 before=r['before'];expected=copy.deepcopy(before['spec']);expected['template']['spec']['containers'][0]['image']=r['image'];assert out['spec']==expected and out['podUID']!=before['podUID']
 for key in ['deploymentUID','nativeSecretMetadata','services']:assert out[key]==before[key],key
 assert set(before['piholeMetricFamilies'])<=set(pi)
 h=json.loads(subprocess.check_output(['kubectl','-n','flux-system','get','helmrelease',name,'-o','json']));assert any(c['type']=='Ready'and c['status']=='True'for c in h['status']['conditions'])and r['revision'][:12]in h['status']['lastAttemptedRevision'];out['helmRevision']=h['status']['lastAttemptedRevision']
 g=json.loads(subprocess.check_output(['kubectl','-n','flux-system','get','gitrepository','branconet-charts','-o','json']));assert g['status']['artifact']['revision']=='validated@sha1:'+r['revision'];out['fluxRevision']=g['status']['artifact']['revision']
out['passed']=True;print(json.dumps(out))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['before','after']);p.add_argument('--charts-revision');a=p.parse_args();os.umask(0o077)
 os.environ.update(TMPDIR=str(C/'tmp'),TMP=str(C/'tmp'),TEMP=str(C/'tmp'),PYTHONDONTWRITEBYTECODE='1')
 out=C/('exporter-upstream-'+a.phase+'.json');assert not out.exists()
 request={'phase':a.phase,'image':'docker.io/library/pihole-exporter-security-20261023@sha256:b5f1f7deeafa7a2649f983ac6a719eceaf07508fef0adf1bd3c06573a0d78431'}
 if a.phase=='after':
  assert a.charts_revision and len(a.charts_revision)==40;request.update(before=json.loads((C/'exporter-upstream-before.json').read_text()),image=json.loads((C/'pihole-exporter-upstream.json').read_text())['image']['reference'],revision=a.charts_revision)
 code='import json,traceback\ntry:\n exec(compile('+repr(PROGRAM)+',"exporter-qualification","exec"))\nexcept Exception as e:\n print(json.dumps({"errorType":type(e).__name__,"line":traceback.extract_tb(e.__traceback__)[-1].lineno}));raise SystemExit(1)\n'
 result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@192.168.0.4',shlex.join(['python3','-B','-c',code])],input=json.dumps(request).encode(),capture_output=True,timeout=240)
 if result.returncode:
  error={'passed':False,'phase':a.phase,'exitCode':result.returncode,'stderrSuppressed':bool(result.stderr)}
  if result.stdout:error['diagnostic']=json.loads(result.stdout)
  (C/('exporter-failure-'+uuid.uuid4().hex+'.json')).write_text(json.dumps(error,indent=2));print(json.dumps(error));return 1
 r=json.loads(result.stdout);r['sourceSHA256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'passed':True,'phase':a.phase,'podUID':r['podUID'],'piholeMetricFamilies':len(r['piholeMetricFamilies'])}));return 0
if __name__=='__main__':raise SystemExit(main())
