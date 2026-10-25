#!/usr/bin/env python3
"""Explicit same-application upstream adoption checks; no deployment or secrets output."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import uuid

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
REMOTE = r'''
import json,sys,subprocess,urllib.request,urllib.error,copy,hashlib,datetime,re,ipaddress
r=json.load(sys.stdin);phase=r['phase'];opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
TEXT=b'Hello from Branconet http-echo on Kubernetes + Longhorn!'
def get(ns,kind,name=None):
 args=['kubectl','-n',ns,'get',kind]+([name]if name else [])+['-o','json']
 p=subprocess.run(args,capture_output=True,timeout=35);assert p.returncode==0,('api_read_failed',kind)
 assert len(p.stdout)<16*1024**2;return json.loads(p.stdout)
def ready(o):return any(c['type']=='Ready'and c['status']=='True'for c in o.get('status',{}).get('conditions',[]))
def request(url,body=None,headers={},method=None):
 req=urllib.request.Request(url,data=body,headers=headers,method=method)
 with opener.open(req,timeout=75)as response:
  raw=response.read(1024**2+1);assert len(raw)<=1024**2
  return response.status,raw,dict(response.headers)
def api(url,payload):
 status,raw,_=request(url,json.dumps(payload).encode(),{'Content-Type':'application/json'});assert status==200
 return json.loads(raw)
out={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':phase,'services':{},'actionsUsed':False,'imagesBuilt':False}
for name,ns in [('http-echo','http-echo'),('flaresolverr','plex')]:
 d=get(ns,'deployment',name);assert d['spec']['replicas']==1 and d['status'].get('availableReplicas')==1
 pods=[p for p in get(ns,'pods')['items']if any(o.get('controller')and o['kind']=='ReplicaSet'for o in p['metadata'].get('ownerReferences',[]))and p['metadata'].get('labels',{}).get('app')==name and p['status'].get('phase')not in ['Failed','Succeeded']]
 assert len(pods)==1;pod=pods[0];assert not pod['metadata'].get('deletionTimestamp')and ready(pod)
 owner=next(o for o in pod['metadata']['ownerReferences']if o.get('controller'));rs=get(ns,'replicaset',owner['name']);assert rs['metadata']['uid']==owner['uid']and any(o.get('controller')and o['uid']==d['metadata']['uid']for o in rs['metadata'].get('ownerReferences',[]))
 assert len(pod['spec']['containers'])==1;container=pod['spec']['containers'][0];status=pod['status']['containerStatuses'][0];expected=r['images'][name]
 assert container['image']==expected and status['ready']and status['imageID'].endswith('@'+expected.split('@')[1])
 services={o['metadata']['name']:{'uid':o['metadata']['uid'],'spec':o['spec']}for o in get(ns,'services')['items']if o['spec'].get('selector',{}).get('app')==name}
 ingresses={o['metadata']['name']:{'uid':o['metadata']['uid'],'spec':o['spec'],'annotations':o['metadata'].get('annotations',{})}for o in get(ns,'ingresses')['items']if any(path['backend']['service']['name']==name for rule in o['spec'].get('rules',[])for path in rule.get('http',{}).get('paths',[]))}
 claims={}
 for v in pod['spec'].get('volumes',[]):
  if 'persistentVolumeClaim'not in v:continue
  p=get(ns,'pvc',v['persistentVolumeClaim']['claimName']);assert p['status']['phase']=='Bound';claims[p['metadata']['name']]={'uid':p['metadata']['uid'],'volume':p['spec']['volumeName'],'spec':p['spec']}
 refs={e['valueFrom']['secretKeyRef']['name']for e in container.get('env',[])if 'secretKeyRef'in e.get('valueFrom',{})}
 assert not container.get('envFrom');secrets={}
 for name_ in refs:
  s=get(ns,'secret',name_);secrets[name_]={'uid':s['metadata']['uid'],'resourceVersion':s['metadata']['resourceVersion']};s.clear()
 row={'namespace':ns,'deploymentUID':d['metadata']['uid'],'spec':d['spec'],'podUID':pod['metadata']['uid'],'image':container['image'],'imageID':status['imageID'],'restartCount':status['restartCount'],'services':services,'ingresses':ingresses,'claims':claims,'nativeSecretMetadata':secrets}
 service=get(ns,'service',name);address=ipaddress.ip_address(service['spec']['clusterIP']);assert address.is_private;base='http://'+str(address)+(''if name=='http-echo'else':8191')
 if name=='http-echo':
  checks=[]
  for path,method,body in [('/','GET',None),('/','POST',b'branconet-upstream-echo-check'),('/health','GET',None)]:
   code,raw,headers=request(base+path,body,method=method);assert code==200
   if path=='/':assert raw.strip()==TEXT
   checks.append({'path':path,'method':method,'status':code,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'contentType':headers.get('Content-Type')})
  routes=[]
  for ip in ['192.168.0.4','192.168.0.5','192.168.0.6']:
   code,raw,_=request('http://'+ip+'/',headers={'Host':'http-echo.branconet.local'});assert code==200 and raw.strip()==TEXT;routes.append({'node':ip,'status':code,'expectedBody':True})
  row.update(httpChecks=checks,ingressChecks=routes);echoURL=base+'/'
 else:
  code,raw,_=request(base+'/');info=json.loads(raw);assert code==200 and info['version'].removeprefix('v')=='3.5.2'
  sessions=api(base+'/v1',{'cmd':'sessions.list'});assert sessions.get('status')=='ok'and sessions.get('sessions')==[]
  result=api(base+'/v1',{'cmd':'request.get','url':echoURL,'maxTimeout':60000});assert result['status']=='ok'and result['version'].removeprefix('v')=='3.5.2'and result['solution']['status']==200 and TEXT.decode()in result['solution']['response']
  versions=re.findall(r'Chrome/([0-9.]+)',result['solution'].get('userAgent',''))
  sessions=api(base+'/v1',{'cmd':'sessions.list'});assert sessions.get('status')=='ok'and sessions.get('sessions')==[]
  row.update(applicationVersion=info['version'],browserRetrieval={'ownClusterEchoRetrieved':True,'status':200,'temporarySessionCleaned':True,'browserVersions':versions})
  result.clear();sessions.clear()
 if phase=='after':
  prior=r['before']['services'][name];spec=copy.deepcopy(prior['spec']);spec['template']['spec']['containers'][0].update(image=expected,imagePullPolicy='IfNotPresent')
  assert row['spec']==spec and row['podUID']!=prior['podUID']
  for key in ['deploymentUID','services','ingresses','claims','nativeSecretMetadata']:assert row[key]==prior[key],('identity_or_configuration_changed',name,key)
  if name=='http-echo':assert row['httpChecks']==prior['httpChecks']and row['ingressChecks']==prior['ingressChecks']
  h=get('flux-system','helmrelease',name);assert ready(h)and r['chartsRevision'][:12]in h['status']['lastAttemptedRevision'];row['helmRevision']=h['status']['lastAttemptedRevision']
 out['services'][name]=row
if phase=='after':
 g=get('flux-system','gitrepository','branconet-charts');assert ready(g)and g['status']['artifact']['revision']=='validated@sha1:'+r['chartsRevision'];out['fluxRevision']=g['status']['artifact']['revision']
out['passed']=True;print(json.dumps(out))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['before','after']);p.add_argument('--charts-revision');args=p.parse_args()
    os.umask(0o077);control=ROOT/'operator-control'
    os.environ.update(TMPDIR=str(control/'tmp'),TMP=str(control/'tmp'),TEMP=str(control/'tmp'),PYTHONDONTWRITEBYTECODE='1')
    output=control/('stateless-upstream-'+args.phase+'.json');assert not output.exists()
    images={'http-echo':'docker.io/library/http-echo-security-20261023@sha256:451c628e3f7587cfa4469131c7429e7b960bb1131b63a4d72e7622cc9284372a','flaresolverr':'docker.io/library/flaresolverr-security-20261023@sha256:29a981aec497ec47ccc25d67309c404593992a465501632e115010282ef61ec7'}
    request={'phase':args.phase,'images':images}
    if args.phase=='after':
        assert args.charts_revision and len(args.charts_revision)==40
        request.update(before=json.loads((control/'stateless-upstream-before.json').read_text()),chartsRevision=args.charts_revision)
        request['images']={x['service']:x['image']['reference']for x in json.loads((control/'upstream-service-catalog.json').read_text())}
    wrapper='import json,traceback\ntry:\n exec(compile('+repr(REMOTE)+',"stateless-upstream","exec"))\nexcept Exception as e:\n print(json.dumps({"errorType":type(e).__name__,"line":traceback.extract_tb(e.__traceback__)[-1].lineno}));raise SystemExit(1)\n'
    result=subprocess.run(SSH+[shlex.join(['python3','-B','-c',wrapper])],input=json.dumps(request).encode(),capture_output=True,timeout=240)
    if result.returncode:
        error={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':args.phase,'passed':False,'transportExit':result.returncode,'category':'qualified_operation_refused','stderrSuppressed':bool(result.stderr)}
        if result.stdout:
            diagnostic=json.loads(result.stdout);error.update({k:diagnostic[k]for k in ['errorType','line']if k in diagnostic})
        (control/('stateless-upstream-'+args.phase+'-failure-'+uuid.uuid4().hex+'.json')).write_text(json.dumps(error,indent=2)+'\n');print(json.dumps(error));return 1
    out=json.loads(result.stdout);assert out['passed'];out['controllerSourceSHA256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with output.open('x')as f:json.dump(out,f,indent=2);f.write('\n')
    print(json.dumps({'phase':args.phase,'passed':True,'receipt':str(output),'pods':{k:v['podUID']for k,v in out['services'].items()}}));return 0


if __name__=='__main__':
    raise SystemExit(main())
