"""Read-only legacy writer schema and three exact-template transition dry-runs."""
import copy,hashlib,importlib.util,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).parent
A=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery')
R=Path('/home/brajam/.local/share/branconet-migration')
OLD=R/'schema-current-writer-66f5c84fa205'
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def need(v):
 if not v:raise RuntimeError('current_legacy_transition_check_failed')
def main():
 producer=load('current_schema_producer',ROOT/'schema-current-writer-v1/current-schema-producer.py')
 credentials=load('current_legacy_credentials',ROOT/'bortus-operator-mtls.py')
 options=credentials.OperatorMTLSOptions(str(R/'admin.conf'));api=producer.VerifiedAPI(options)
 deadline=time.monotonic()+180;started=time.monotonic_ns()
 schema=producer.collect(A,OLD/'schema-reader.cjs',OLD/'migration-manifest.json',deadline,started,api.get)
 before=producer.snapshot(api.get,deadline)
 dep=api.get('/apis/apps/v1/namespaces/bortus/deployments/bortus',deadline)
 guard=load('current_legacy_guard_operator',ROOT/'bortus-admission-operator.py')
 gapi=guard.API(options)
 original=json.loads((A/'guard-probes-da37c4f713e8-publication-settle/record.json').read_bytes())
 pins=original['binding']['publication']['guard_pins']
 def check_guards():
  for p in pins:
   obj=gapi.guard(p['kind'],p['name'],deadline=deadline)
   need(obj['metadata']['uid']==p['uid'] and hashlib.sha256(guard.validator.canonical_spec(p['kind'],obj['spec'])).hexdigest()==p['spec_sha256'])
 check_guards()
 update=copy.deepcopy(dep);update.pop('status',None);update['metadata'].pop('managedFields',None);update['spec']['replicas']=0
 rs={'apiVersion':'apps/v1','kind':'ReplicaSet','metadata':{'name':'bortus-admission-da37c4f713e8-case-43','namespace':'bortus'},'spec':{'replicas':0,'selector':copy.deepcopy(dep['spec']['selector']),'template':copy.deepcopy(dep['spec']['template'])}}
 pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':'bortus-admission-da37c4f713e8-case-44','namespace':'bortus',**copy.deepcopy(dep['spec']['template'].get('metadata',{}))},'spec':copy.deepcopy(dep['spec']['template']['spec'])}
 # Names/namespace cannot be replaced by template metadata.
 pod['metadata'].update(name='bortus-admission-da37c4f713e8-case-44',namespace='bortus')
 outcomes=[]
 for action,body in [('replace',update),('create',rs),('create',pod)]:
  check_guards();need(producer.snapshot(api.get,deadline)==before)
  result=subprocess.run([str(R/'bin/kubectl'),'--kubeconfig',str(R/'admin.conf'),'--request-timeout=30s',action,'--dry-run=server','-f','-','-o','json'],input=json.dumps(body).encode(),capture_output=True,timeout=35)
  need(result.returncode==0)
  obj=json.loads(result.stdout);need(obj['kind']==body['kind'] and obj['metadata']['name']==body['metadata']['name'])
  outcomes.append({'kind':body['kind'],'operation':action,'submitted_body_sha256':hashlib.sha256(guard.validator.canonical(body)).hexdigest(),'server_allowed':True,'dry_run':True})
 check_guards();need(producer.snapshot(api.get,deadline)==before)
 state={'state':'completed','schema_metadata_path':schema['path'],'schema_metadata_sha256':schema['sha256'],
 'production_writer_unchanged':True,'current_writer_template_sha256':before['template_sha256'],'legacy_template_outcomes':outcomes,'production_changed':False}
 out=A/'legacy-template-transition-dry-runs.json';fd=os.open(out,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'w') as f:json.dump(state,f);f.flush();os.fsync(f.fileno())
 print(json.dumps({'legacy_schema_migrations':7,'schema_metadata_only':True,'full_template_transition_dry_runs_passed':3,'production_unchanged':True}))
if __name__=='__main__':
 try:main()
 except Exception as e:
  import traceback
  print(json.dumps({'legacy_transition_failed':type(e).__name__,'locations':[Path(f.filename).name+':'+str(f.lineno) for f in traceback.extract_tb(e.__traceback__)]}),file=sys.stderr);raise SystemExit(1)
