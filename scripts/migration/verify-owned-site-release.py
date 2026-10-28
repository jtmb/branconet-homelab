#!/usr/bin/env python3
"""Read-only exact owned-site content, wiring, TLS and independent-restart acceptance."""
import argparse,base64,datetime,hashlib,http.client,json,shlex,socket,ssl,subprocess
from pathlib import Path
ROOT=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT=ROOT/'owned-jtmb-dev-release-20261027';REPO=ROOT/'owned-application-sources-20261026/jtmb-dev'
COMMIT='5989a1491415532244ef9c67635e7c72437387ab'
OLD='docker.io/library/jtmb-dev-security-20261023@sha256:6432c71889d843c7efb381a4321e4fba07a52a0cfb50171921b6315bddf1b295'
NEW='docker.io/jtmb92/jtmb-dev:git-'+COMMIT+'@sha256:ac5cdc8d7e1bb7d6a5bcea08d4e379ea63f2ec1e7ae93a267258a9c97593d830'
HOST='jtmb-dev.branconet.local';NODES=['192.168.0.4','192.168.0.5','192.168.0.6']
PROGRAM=r"""import json,sys,subprocess,datetime,time,tarfile,io,hashlib
request=json.load(sys.stdin);expected=request['image'];previous=request.get('previousUID');ns='website-stack'
def get(kind,name=None):
 cmd=['kubectl','-n',ns,'get',kind]+([name]if name else[])+['-o','json'];return json.loads(subprocess.check_output(cmd,timeout=30))
def need(ok,why):
 if not ok:raise ValueError(why)
start=time.monotonic();found=None
while time.monotonic()-start<240:
 dep=get('deployment','jtmb-dev');pods=[x for x in get('pods')['items']if x['metadata'].get('labels',{}).get('app')=='jtmb-dev' and not x['metadata'].get('deletionTimestamp')]
 if len(pods)==1:
  p=pods[0];cs=p.get('status',{}).get('containerStatuses',[])
  if len(cs)==1 and cs[0]['ready'] and cs[0]['imageID'].endswith(expected.split('@')[1]) and(not previous or p['metadata']['uid']!=previous) and dep['status'].get('observedGeneration',0)>=dep['metadata']['generation'] and dep['status'].get('availableReplicas')==dep['status'].get('updatedReplicas')==1:found=(dep,p,cs[0]);break
 time.sleep(5)
need(found is not None,'bounded_distinct_ready_image_not_observed');dep,p,cs=found;need(cs['restartCount']==0,'unexpected_restart');need(dep['spec']['template']['spec']['containers'][0]['image']==expected,'deployment_image_not_exact')
need(not dep['spec']['template']['spec'].get('volumes') and not dep['spec']['template']['spec'].get('initContainers'),'unexpected_volume_or_init')
need(not any(c.get('env')or c.get('envFrom')for c in dep['spec']['template']['spec']['containers']),'unexpected_environment_binding')
name=p['metadata']['name'];raw=subprocess.check_output(['kubectl','-n',ns,'exec',name,'--','tar','-cf','-','-C','/usr/share/nginx/html','.'],timeout=30);need(len(raw)<4*1024**2,'site_bound');files={}
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:')as t:
 for m in t:
  if m.isdir():continue
  need(m.isfile()and not m.issym()and not m.islnk(),'nonregular_site_asset');path=m.name.removeprefix('./');need(path not in files and not path.startswith('/')and '..'not in path.split('/'),'site_path');files[path]={'bytes':m.size,'sha256':hashlib.sha256(t.extractfile(m).read()).hexdigest(),'uid':m.uid,'gid':m.gid,'mode':m.mode}
service=get('service','jtmb-dev');ingresses={n:{'uid':(x:=get('ingress',n))['metadata']['uid'],'spec':x['spec']}for n in ['jtmb-dev-ingress','jtmb-dev-https']}
secrets=[{'name':x['metadata']['name'],'uid':x['metadata']['uid'],'resourceVersion':x['metadata']['resourceVersion'],'type':x.get('type','Opaque')}for x in get('secrets')['items']if x.get('type')!='helm.sh/release.v1'];secrets.sort(key=lambda x:x['name'])
version=subprocess.run(['kubectl','-n',ns,'exec',name,'--','nginx','-v'],capture_output=True,timeout=25);need(version.returncode==0 and version.stderr.decode().strip()=='nginx version: nginx/1.30.6','nginx_version');check=subprocess.run(['kubectl','-n',ns,'exec',name,'--','nginx','-t'],capture_output=True,timeout=25);need(check.returncode==0,'nginx_config_test');conf=subprocess.check_output(['kubectl','-n',ns,'exec',name,'--','cat','/etc/nginx/conf.d/default.conf'],timeout=25)
hr=json.loads(subprocess.check_output(['kubectl','-n','flux-system','get','helmrelease','jtmb-dev','-o','json']));need(not hr['spec'].get('suspend')and any(c['type']=='Ready'and c['status']=='True'for c in hr.get('status',{}).get('conditions',[])),'release_not_ready')
print(json.dumps({'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'deployment':{'uid':dep['metadata']['uid'],'spec':dep['spec']},'service':{'uid':service['metadata']['uid'],'spec':service['spec']},'ingresses':ingresses,'nativeSecrets':secrets,'podUID':p['metadata']['uid'],'runtimeImageID':cs['imageID'],'files':files,'nginxVersion':'1.30.6','nginxConfigurationPassed':True,'nginxConfSHA256':hashlib.sha256(conf).hexdigest(),'helmReleaseUID':hr['metadata']['uid'],'helmRevision':hr['status']['lastAttemptedRevision'],'noApplicationPVCsOrSecretValues':True}))
"""
def need(ok,why):
 if not ok:raise ValueError(why)
def git_blob(name):return subprocess.check_output(['git','-c','safe.directory='+str(REPO),'-C',str(REPO),'cat-file','blob',COMMIT+':'+name])
class TLS(http.client.HTTPSConnection):
 def __init__(self,ip,ctx):super().__init__(HOST,443,timeout=15,context=ctx);self.ip=ip
 def connect(self):self.sock=self._context.wrap_socket(socket.create_connection((self.ip,443),15),server_hostname=HOST)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['baseline','production','restart']);a=p.parse_args();path=OUT/(a.phase+'-acceptance.json');need(not path.exists(),'immutable_receipt_required')
 before=json.loads((OUT/'baseline-acceptance.json').read_bytes())if a.phase!='baseline'else None;previous=json.loads((OUT/'production-acceptance.json').read_bytes())if a.phase=='restart'else before
 image=OLD if a.phase=='baseline'else NEW;req={'image':image,'previousUID':previous['podUID']if previous else None}
 ssh=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@192.168.0.4',shlex.join(['python3','-B','-c',PROGRAM])];r=subprocess.run(ssh,input=json.dumps(req).encode(),capture_output=True,timeout=300)
 need(r.returncode==0,'live_snapshot_failed:'+r.stderr.decode(errors='replace').splitlines()[-1][:160]if r.stderr else'live_snapshot_failed');observed=json.loads(r.stdout)
 if a.phase=='baseline':
  original=json.loads((OUT/'before.json').read_bytes());need(observed['deployment']==original['deployment']and observed['service']==original['service']and observed['ingresses']==original['ingresses'],'original_wiring_drift');expected=observed['files']
 else:
  need(observed['deployment']['uid']==before['deployment']['uid'],'deployment_uid');normalized=json.loads(json.dumps(observed['deployment']['spec']));normalized['template']['spec']['containers'][0]['image']=OLD;annotations=normalized['template']['metadata'].get('annotations',{});annotations.pop('branconet.io/owned-site-restart',None)
  if not annotations:normalized['template']['metadata'].pop('annotations',None)
  need(normalized==before['deployment']['spec'],'unreviewed_deployment_change')
  for key in ['service','ingresses','nativeSecrets','helmReleaseUID']:need(observed[key]==before[key],'changed_'+key)
  listing=subprocess.check_output(['git','-c','safe.directory='+str(REPO),'-C',str(REPO),'ls-tree','-r','--name-only',COMMIT,'--','static-site']).decode().splitlines();expected={}
  for name in listing:
   data=git_blob(name);expected[name.removeprefix('static-site/')]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'uid':0,'gid':0,'mode':0o644}
  need(observed['files']==expected,'exact_committed_site_assets');need(observed['nginxConfSHA256']==hashlib.sha256(git_blob('nginx/default.conf')).hexdigest(),'exact_committed_config')
  preserved=[n for n in before['files']if n not in ['index.html','dev/index.html','dev/js/jquery-2.1.4.js']];need(len(preserved)==6 and all(before['files'][n]==expected[n]for n in preserved),'original_content_or_metadata_changed');observed['unchangedOriginalAssetCount']=len(preserved)
 root=ROOT/'lan-tls-20261026/branconet-local-root.crt';pem=root.read_text();need(hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest()=='79b3cf11aed6c404885e555ceff33819ffa4ca534959f00f80b16e09927e2fab','root_pin');ctx=ssl.create_default_context(cafile=str(root));facts=[]
 paths={'/'+name:row for name,row in expected.items()};paths['/']=expected['index.html'];paths['/dev/']=expected['dev/index.html']
 for ip in NODES:
  for scheme in ['http','https']:
   for route,want in paths.items():
    conn=TLS(ip,ctx)if scheme=='https'else http.client.HTTPConnection(ip,80,timeout=15);conn.request('GET',route,headers={'Host':HOST,'Accept-Encoding':'identity'});res=conn.getresponse();body=res.read(2*1024**2+1);need(res.status==200 and len(body)==want['bytes']and hashlib.sha256(body).hexdigest()==want['sha256'],'route_content:'+ip+':'+scheme+':'+route);facts.append({'node':ip,'scheme':scheme,'path':route,'status':res.status,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()});conn.close()
   if a.phase!='baseline':
    for route,target in [('/dev/js/jquery-2.1.4.js','/dev/js/jquery-4.0.0.min.js'),('/js/modernizr.js','/dev/js/modernizr.js')]:
     conn=TLS(ip,ctx)if scheme=='https'else http.client.HTTPConnection(ip,80,timeout=15);conn.request('GET',route,headers={'Host':HOST});res=conn.getresponse();res.read(8193);need(res.status==308 and res.getheader('Location')==target,'safe_relative_compatibility_redirect');facts.append({'node':ip,'scheme':scheme,'path':route,'status':308,'location':target});conn.close()
 observed.update(passed=True,phase=a.phase,exactImage=image,sourceCommit=COMMIT if a.phase!='baseline'else None,HTTP=facts,strictTLS=True,independentRestart=a.phase=='restart',browserAcceptance=False,scriptSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
 with path.open('x')as f:json.dump(observed,f,indent=2);f.write('\n')
 print(json.dumps({'passed':True,'phase':a.phase,'podUID':observed['podUID'],'files':len(expected),'HTTPChecks':len(facts),'strictTLS':True,'browserAcceptance':False,'sourceCommit':observed['sourceCommit']}))
if __name__=='__main__':main()
