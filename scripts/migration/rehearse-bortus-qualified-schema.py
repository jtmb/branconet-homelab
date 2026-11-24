"""Rehearse the exact release Prisma migrations on the verified recovery derivative only."""
import hashlib,importlib.util,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).parent
ANCHOR=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery')
RECOVERY=ANCHOR/'independent-restore-da37c4f713e8-lh113-h-tool'
RUN=ANCHOR/'schema-rehearsal-da37c4f713e8'
IMAGE='docker.io/jtmb92/bortus@sha256:ac261f9cc146171469dd9bd660acae39ae9563656a9a873e0fa251d4b2fda58b'
NAME='bortus-schema-da37c4f713e8';CLAIM='bortus-restore-da37c4f713e8'
RUNTIME=Path('/home/brajam/.local/share/branconet-migration')
K=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf'),'--request-timeout=30s']
def need(v):
 if not v:raise RuntimeError('schema_rehearsal_verification_failed')
def load(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def main():
 record=json.loads((RECOVERY/'restore-receipt.json').read_bytes())
 need(record['state']=='completed' and record['whole_rows_equal'] is True and record['holder_absent'] is True and record['resources_closed'] is True)
 journal=json.loads((RECOVERY/'journal.json').read_bytes());claim_uid=journal['operations']['claim_create']['identity']['uid']
 need(not RUN.exists());RUN.mkdir(mode=0o700)
 state={'state':'starting','image':IMAGE,'claim':CLAIM,'claim_uid':claim_uid,'pod_uid':None,'migration_applied':False,'forward_preservation_passed':False,'holder_absent':False,'production_changed':False}
 def save():
  p=RUN/'state.json';fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'w') as f:json.dump(state,f);f.flush();os.fsync(f.fileno())
  fd=os.open(RUN,os.O_DIRECTORY|os.O_RDONLY)
  try:os.fsync(fd)
  finally:os.close(fd)
 def command(args,body=None,seconds=40):
  r=subprocess.run(K+args,input=body,capture_output=True,timeout=seconds)
  need(r.returncode==0 and len(r.stdout)<=8*1024**2);return json.loads(r.stdout)
 def get(kind,name,namespace='bortus'):
  return command(['get',kind,name]+(['-n',namespace] if namespace else [])+['-o','json'])
 def source_check():
  claim=get('pvc',CLAIM);need(claim['metadata']['uid']==claim_uid)
  pods=command(['get','pods','-n','bortus','-o','json'])['items']
  consumers=[p for p in pods if p.get('status',{}).get('phase') not in ('Succeeded','Failed') and any(v.get('persistentVolumeClaim',{}).get('claimName')==CLAIM for v in p['spec'].get('volumes',[]))]
  need(all(p['metadata']['name']==NAME and state['pod_uid']==p['metadata']['uid'] for p in consumers))
  original=get('deployment','bortus');need(original['metadata']['uid']=='4deedc67-038a-4f82-a2d4-a83af316f2f6' and original['spec']['replicas']==1 and original['status'].get('readyReplicas')==1
   and original['spec']['template']['spec']['containers'][0]['image']=='docker.io/library/bortus@sha256:3b076fb9b7fb64fd760691c0120f29d4e363d4ccb9910a596ff211bfc3ea0879')
 def holder():
  p=get('pod',NAME);need(p['metadata']['uid']==state['pod_uid'] and not p['metadata'].get('ownerReferences')
   and p['spec']['automountServiceAccountToken'] is False and p['spec']['nodeName']=='node02'
   and p['spec']['containers'][0]['image']==IMAGE and p['spec']['containers'][0]['command']==['node','-e','setInterval(()=>{},1000)']
   and p['spec']['volumes']==[{'name':'data','persistentVolumeClaim':{'claimName':CLAIM}}])
  return p
 normalized=[];child=None;save()
 try:
  source_check()
  spec={'apiVersion':'v1','kind':'Pod','metadata':{'name':NAME,'namespace':'bortus','labels':{'bortus-schema-rehearsal':'da37c4f713e8'}},'spec':{
    'nodeName':'node02','restartPolicy':'Never','automountServiceAccountToken':False,
    'securityContext':{'runAsNonRoot':True,'runAsUser':1000,'runAsGroup':1000,'seccompProfile':{'type':'RuntimeDefault'}},
    'containers':[{'name':'holder','image':IMAGE,'imagePullPolicy':'Never','workingDir':'/app',
     'command':['node','-e','setInterval(()=>{},1000)'],'env':[{'name':'DATABASE_URL','value':'file:/data/bortus.db'},{'name':'BORTUS_KV_GUARDED_ADOPTION','value':'false'}],
     'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}},
     'resources':{'requests':{'cpu':'5m','memory':'64Mi'},'limits':{'cpu':'1','memory':'512Mi'}},
     'volumeMounts':[{'name':'data','mountPath':'/data'}]}],
    'volumes':[{'name':'data','persistentVolumeClaim':{'claimName':CLAIM}}]}}
  state['state']='creating';state['proposal_sha256']=hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest();save()
  created=command(['create','-f','-','-o','json'],json.dumps(spec).encode());state['pod_uid']=created['metadata']['uid'];state['state']='created';save()
  until=time.monotonic()+90
  while time.monotonic()<until:
   p=holder()
   if p.get('status',{}).get('phase')=='Running' and any(c['type']=='Ready' and c['status']=='True' for c in p['status'].get('conditions',[])):break
   need(p.get('status',{}).get('phase') not in ('Failed','Succeeded'));time.sleep(.5)
  else:raise RuntimeError('schema_holder_not_ready')
  source_check();state['state']='migrating';save()
  result=subprocess.run(K+['-n','bortus','exec',NAME,'-c','holder','--','./node_modules/.bin/prisma','migrate','deploy'],capture_output=True,timeout=90)
  fd=os.open(RUN/'migration.log',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
  with os.fdopen(fd,'wb') as f:f.write(result.stdout+result.stderr);f.flush();os.fsync(f.fileno())
  need(result.returncode==0);state['migration_applied']=True;state['state']='migrated';save()
  holder();source_check()
  archive=load('schema_archive','bortus-sqlite-archive.py');norm=load('schema_normalization','normalize-bortus-sqlite-archive.py');compare=load('schema_comparison','compare-bortus-databases.py')
  deadline=time.monotonic()+120
  child=subprocess.Popen(K+['-n','bortus','exec',NAME,'-c','holder','-i','--','node','-'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True)
  writer=archive.Pipe(child.stdin,deadline,False)
  try:writer.write(archive.NODE_READER.encode());child.stdin.close()
  finally:writer.close()
  cipher=archive.encrypt_source(child,RUN/'migrated-sqlite.age',RUNTIME/'bin/age',Path('/home/brajam/.ssh/id_ed25519.pub'),Path('/home/brajam/.ssh/id_ed25519'),deadline)
  holder();source_check();state['state']='captured';save()
  original=json.loads((ANCHOR/'recovery/bortus-checkpoints/da37c4f713e8/journal.json').read_bytes())['sqlite_archive']
  for path,digest in [(Path(original['artifact']),original['ciphertext_sha256']),(RUN/'migrated-sqlite.age',cipher['ciphertext_sha256'])]:
   normalized.append(norm.normalize(path,digest,Path('/home/brajam/.ssh/id_ed25519'),age=RUNTIME/'bin/age',seconds=120,deadline=deadline))
  compared=compare.compare(Path(normalized[0]['database_path']),Path(normalized[1]['database_path']),'forward',deadline=deadline)
  need(compared['passed'] is True)
  state['forward_preservation_passed']=True;state['comparison']=compared;state['state']='compared';save()
 finally:
  cleanup_failed=False
  for item in normalized:
   try:norm.cleanup(item['temporary_directory'],item['temporary_directory_identity'])
   except Exception:cleanup_failed=True
  if child is not None:
   archive.stop_owned(child)
   for stream in [child.stdin,child.stdout]:
    if stream is not None and not stream.closed:stream.close()
  if state['pod_uid']:
   p=holder();identity={k:p['metadata'][k] for k in ('uid','resourceVersion')}
   command(['delete','--raw','/api/v1/namespaces/bortus/pods/'+NAME,'-f','-'],json.dumps({'apiVersion':'v1','kind':'DeleteOptions','preconditions':identity}).encode())
   until=time.monotonic()+60
   while time.monotonic()<until:
    r=subprocess.run(K+['get','pod',NAME,'-n','bortus','--ignore-not-found','-o','json'],capture_output=True,timeout=35);need(r.returncode==0)
    if not r.stdout.strip():state['holder_absent']=True;break
    need(json.loads(r.stdout)['metadata']['uid']==state['pod_uid']);time.sleep(.5)
   need(state['holder_absent'])
  state['plaintext_copies_cleaned']=not cleanup_failed;state['state']='completed' if state['forward_preservation_passed'] and not cleanup_failed else 'failed';save()
 need(state['state']=='completed');source_check()
 print(json.dumps({'schema_rehearsal_passed':True,'all_original_rows_preserved':True,'plaintext_copies_cleaned':True,'owned_holder_absent':True,'production_changed':False}))
if __name__=='__main__':
 try:main()
 except Exception as e:
  import traceback
  print(json.dumps({'schema_rehearsal_failed':type(e).__name__,'locations':[Path(f.filename).name+':'+str(f.lineno) for f in traceback.extract_tb(e.__traceback__)]}),file=sys.stderr);raise SystemExit(1)
