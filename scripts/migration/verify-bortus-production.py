"""Real production HTTP/auth/RBAC checks through an exclusively owned API tunnel."""
import base64,contextlib,http.client,importlib.util,json,os,signal,subprocess,time,urllib.error,urllib.request
from pathlib import Path
A=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery');R=Path('/home/brajam/.local/share/branconet-migration')
IMAGE='docker.io/jtmb92/bortus@sha256:ac261f9cc146171469dd9bd660acae39ae9563656a9a873e0fa251d4b2fda58b'
QUALIFIED=A/'qualified-final-image.json'
if QUALIFIED.exists():
 _qualified=json.loads(QUALIFIED.read_bytes())
 if _qualified.get('source')!='34b8fa18c34576721ff4fb064923f1499598481d' or _qualified.get('all_three_nodes_verified') is not True or _qualified.get('current_unfiltered_security_scan_passed') is not True:raise RuntimeError('final_image_qualification_invalid')
 IMAGE=_qualified['image']
 if not IMAGE.startswith('docker.io/jtmb92/bortus@sha256:') or len(IMAGE.split('sha256:')[1])!=64:raise RuntimeError('final_image_reference_invalid')
K=[str(R/'bin/kubectl'),'--kubeconfig',str(R/'admin.conf'),'--cache-dir',str(A/'kubectl-cache'),'--request-timeout=20s']
_identity_spec=importlib.util.spec_from_file_location('production_runtime_identity',Path(__file__).with_name('bortus-runtime-image-identity.py'));_runtime_identity=importlib.util.module_from_spec(_identity_spec);_identity_spec.loader.exec_module(_runtime_identity)
def need(value):
 if not value:raise RuntimeError('production_acceptance_check_failed')
def kube(*args):
 p=subprocess.run(K+list(args),capture_output=True,timeout=30);need(p.returncode==0);return json.loads(p.stdout)
class API:
 def __init__(self,cookie=''):self.cookie=cookie
 def call(self,method,path,body=None,expected=(200,),authenticated=True):
  raw=None if body is None else json.dumps(body).encode();headers={'Content-Type':'application/json','Origin':'http://127.0.0.1:21088'}
  if authenticated and self.cookie:headers['Cookie']=self.cookie
  request=urllib.request.Request('http://127.0.0.1:21088'+path,data=raw,headers=headers,method=method)
  try:reply=urllib.request.urlopen(request,timeout=20)
  except urllib.error.HTTPError as error:reply=error
  with reply:
   status=reply.status;data=reply.read(1024**2+1);need(len(data)<=1024**2)
   if status not in expected:raise RuntimeError('production_http_status_'+str(status)+'_'+method+'_'+path.split('?')[0])
   if path=='/api/auth/login' and status==200:
    cookie=reply.headers.get('Set-Cookie','');need(cookie and ';' in cookie);self.cookie=cookie.split(';',1)[0]
   return json.loads(data) if data else None
@contextlib.contextmanager
def production(mode):
 need(QUALIFIED.exists())
 dep=kube('get','deployment','bortus','-n','bortus','-o','json');need(dep['metadata']['uid']=='4deedc67-038a-4f82-a2d4-a83af316f2f6' and dep['spec']['template']['spec']['containers'][0]['image']==IMAGE and dep['status'].get('readyReplicas')==1 and dep['status']['observedGeneration']==dep['metadata']['generation'])
 pods=kube('get','pods','-n','bortus','-o','json')['items'];live=[p for p in pods if p['status'].get('phase')=='Running' and p['spec']['containers'][0]['image']==IMAGE];need(len(live)==1 and live[0]['spec']['serviceAccountName']=='bortus-kv' and _runtime_identity.matches(live[0]['status']['containerStatuses'][0]['imageID'],IMAGE))
 logpath=A/('port-forward-'+mode+'.log');fd=os.open(logpath,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as log:
  child=subprocess.Popen(K+['-n','bortus','port-forward','service/bortus','21088:4000','--address=127.0.0.1'],stdout=log,stderr=log,start_new_session=True)
  try:
   api=API();until=time.monotonic()+30
   while time.monotonic()<until:
    need(child.poll() is None)
    try:api.call('GET','/api/health/live');break
    except (OSError,urllib.error.URLError):time.sleep(.2)
   else:raise RuntimeError('owned_api_tunnel_not_ready')
   secret=kube('get','secret','bortus-operator-access','-n','bortus','-o','json')
   username=base64.b64decode(secret['data']['username']).decode();password=base64.b64decode(secret['data']['password']).decode()
   identity=api.call('POST','/api/auth/login',{'username':username,'password':password});password=None;secret=None
   yield api,identity
  finally:
   if child.poll() is None:
    need(os.getpgid(child.pid)==child.pid);os.killpg(child.pid,signal.SIGTERM)
   try:child.wait(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
def save(name,value):
 fd=os.open(A/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())
def initial():
 with production('initial') as (api,identity):
  need(api.call('GET','/api/health/ready')['status']=='ready')
  session=api.call('GET','/api/auth/session');need(session['authenticated'] is True and session['role']=='write' and session['engineAdmin'] is True)
  need('items' in api.call('GET','/api/kv/mounts'))
  api.call('GET','/api/vars',expected=(401,),authenticated=False)
  api.call('POST','/api/kv/paths/00000000-0000-4000-8000-000000000000/data',{'resourceVersion':'absent','expectedHead':0,'pathRevision':1,'fields':[]},expected=(403,))
  checks=[]
  for verb,namespace,wanted in [('get','bortus-secrets',True),('list','bortus-secrets',True),('create','bortus-secrets',True),('update','bortus-secrets',True),('delete','bortus-secrets',False),('get','bortus-history',True),('create','bortus-history',True),('update','bortus-history',True),('delete','bortus-history',True)]:
   p=subprocess.run(K+['auth','can-i',verb,'secrets','-n',namespace,'--as=system:serviceaccount:bortus:bortus-kv'],capture_output=True,timeout=30)
   allowed=p.returncode==0 and p.stdout.decode().strip()=='yes';need(allowed==wanted);checks.append({'verb':verb,'namespace':namespace,'allowed':allowed})
  for suffix in ('pods','templates','cronjobs'):
   p=kube('get','validatingadmissionpolicy','bortus-kv-guard-'+suffix,'-o','json');images=json.loads(next(v['expression'] for v in p['spec']['variables'] if v['name']=='approvedImages'))
   need(IMAGE in images and not any('3b076fb9b7fb64fd' in i for i in images))
  pvc=kube('get','pvc','bortus-data','-n','bortus','-o','json');need(pvc['metadata']['uid']=='19cc4b60-4536-4d80-8789-e27b5ad48b79')
  save('production-initial-acceptance.json',{'state':'completed','actual_operator_login':True,'existing_operator_role_preserved':True,'engine_admin_migration':True,'health_and_readiness':True,'unauthenticated_denied':True,'guarded_adoption_still_denies_value_writes':True,'effective_rbac':checks,'legacy_image_withdrawn':True,'original_pvc_preserved':True,'image':IMAGE,'native_value_acceptance_pending':True})
  print(json.dumps({'production_initial_acceptance_passed':True,'effective_rbac_checks':len(checks),'native_value_writes_still_held':True}))
if __name__=='__main__':initial()
