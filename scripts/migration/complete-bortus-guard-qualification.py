"""Reconcile completed live guard probes and retire only their recorded inert fixtures."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).parent
RUN=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/guard-probes-da37c4f713e8-publication-settle')
IMAGE='docker.io/jtmb92/bortus@sha256:ac261f9cc146171469dd9bd660acae39ae9563656a9a873e0fa251d4b2fda58b'
def load(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def need(v):
 if not v:raise RuntimeError('guard_completion_reconciliation_failed')
def main():
 op=load('guard_completion_operator','bortus-admission-operator.py');cred=load('guard_completion_credentials','bortus-operator-mtls.py')
 api=op.API(cred.OperatorMTLSOptions('/home/brajam/.local/share/branconet-migration/admin.conf'))
 raw=(RUN/'record.json').read_bytes();r=json.loads(raw);need(r['phase']=='refused' and r['failure']=='uncertain' and len(r['outcomes'])==42)
 need(r['operations']['Pod-delete']['failure_code']=='cleanup' and r['operations']['Pod-delete']['state']=='uncertain')
 publication=r['binding']['publication'];pins=publication['guard_pins'];until=time.monotonic()+60
 actual=[api.guard(p['kind'],p['name'],deadline=until) for p in pins]
 policy=next(o for o in actual if o['kind']==op.validator.POLICY)
 vars={v['name']:v['expression'] for v in policy['spec']['variables']}
 contract={'namespace':'bortus','guarded_service_account':'bortus-kv','protected_pvc_names':json.loads(vars['protectedClaims']),
 'protected_secret_names':json.loads(vars['protectedSecrets']),'approved_image_references':json.loads(vars['approvedImages'])}
 need(hashlib.sha256(op.validator.canonical(contract)).hexdigest()==r['binding']['contract_sha256'])
 result=op.validator.evaluate(op.validator.reviewed_renders(contract),actual,contract,r['outcomes'],pinned_guard_identities=[{k:p[k] for k in ('kind','name','uid')} for p in pins])
 need(len(result.case_ids)==42)
 state={'state':'pending','original_record_sha256':hashlib.sha256(raw).hexdigest(),'case_count':42,'guard_pins':pins,
 'owned_fixtures_absent':False,'production_changed':False,'deleted':[]}
 path=RUN/'completion-reconciliation.json';need(not path.exists())
 def save(first=False):
  fd=os.open(path,os.O_WRONLY|os.O_NOFOLLOW|(os.O_EXCL|os.O_CREAT if first else os.O_TRUNC),0o600)
  with os.fdopen(fd,'w') as f:json.dump(state,f);f.flush();os.fsync(f.fileno())
  fd=os.open(RUN,os.O_RDONLY|os.O_DIRECTORY)
  try:os.fsync(fd)
  finally:os.close(fd)
 save(True)
 for kind,suffix,ref in [('Pod','pod',None),('Deployment','deployment','bortus-restore-b473091bebef')]:
  name='bortus-admission-da37c4f713e8-'+suffix
  uid=r['operations'][kind+'-create']['returned_identity']['uid']
  code,obj=api.workload('GET',kind,name,deadline=until)
  if code==404:
   need(kind=='Pod');continue
  need(code==200 and obj['metadata']['uid']==uid and not obj['metadata'].get('ownerReferences'))
  proposal=op.object_for(kind,name,op.idle_spec(IMAGE,'node02',reference=ref,guarded=kind=='Pod'))
  need(obj['metadata'].get('labels')==proposal['metadata']['labels'])
  ident=op.fixture_matches(obj,proposal)
  need(kind!='Deployment' or obj['spec']['replicas']==0)
  body={'apiVersion':'v1','kind':'DeleteOptions','preconditions':{k:ident[k] for k in ('uid','resourceVersion')}}
  code,_=api.workload('DELETE',kind,name,body,deadline=until);need(code in (200,202))
  while time.monotonic()<until:
   code,obj=api.workload('GET',kind,name,deadline=until)
   if code==404:break
   need(code==200 and obj['metadata']['uid']==uid);time.sleep(.25)
  else:raise RuntimeError('owned_fixture_still_present')
  state['deleted'].append(ident);save()
 for kind,suffix in [('Pod','pod'),('Deployment','deployment')]:
  code,_=api.workload('GET',kind,'bortus-admission-da37c4f713e8-'+suffix,deadline=until);need(code==404)
 need((RUN/'record.json').read_bytes()==raw)
 state.update(state='completed',owned_fixtures_absent=True,actual_guard_probe_evidence_validated=True);save()
 print(json.dumps({'live_guard_cases_passed':42,'owned_fixtures_absent':True,'original_record_preserved':True,'production_changed':False}))
if __name__=='__main__':
 try:main()
 except Exception as e:
  frames=[];tb=e.__traceback__
  while tb:frames.append(Path(tb.tb_frame.f_code.co_filename).name+':'+str(tb.tb_lineno));tb=tb.tb_next
  print(json.dumps({'reconciliation_failed':type(e).__name__,'locations':frames}),file=sys.stderr);raise SystemExit(1)

