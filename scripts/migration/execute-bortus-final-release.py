"""Authorized final BORTUS-only checkpoint, guard transition and private Flux promotion."""
import argparse,copy,hashlib,importlib.util,json,os,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).parent
A=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery')
R=Path('/home/brajam/.local/share/branconet-migration')
CHARTS=Path('/mnt/c/Users/james/AppData/Local/BORTUS/repos/branconet-charts')
WGIT='/mnt/c/Program Files/Git/cmd/git.exe';WIN_CHARTS='C:/Users/james/AppData/Local/BORTUS/repos/branconet-charts'
IMAGE='docker.io/jtmb92/bortus@sha256:ac261f9cc146171469dd9bd660acae39ae9563656a9a873e0fa251d4b2fda58b'
LEGACY='docker.io/library/bortus@sha256:3b076fb9b7fb64fd760691c0120f29d4e363d4ccb9910a596ff211bfc3ea0879'
STATUS=Path('/mnt/f/branconet-migration-artifacts/maintenance-storage-20261025/branconet-charts-local-ci-state/status.json')
def need(v):
 if not v:raise RuntimeError('final_bortus_release_precondition_failed')
def load(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def git(*args):
 p=subprocess.run([WGIT,'-C',WIN_CHARTS,*args],capture_output=True,timeout=60);need(p.returncode==0);return p.stdout.decode().strip()
def write_once(path,obj):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'w') as f:json.dump(obj,f);f.flush();os.fsync(f.fileno())
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
 att=json.loads((A/'actual-reader-acceptance-20261115.json').read_bytes());need(att['passed'] is True and att['announced_text']=='Configuration saved.')
 proof=json.loads((A/'qualified-node-imports.json').read_bytes());need(proof['image']==IMAGE)
 schema_rehearsal=json.loads((A/'schema-rehearsal-da37c4f713e8/state.json').read_bytes());need(schema_rehearsal['state']=='completed' and schema_rehearsal['forward_preservation_passed'] is True)
 ph=load('final_live_phase','bortus-quiescent-phase.py');g=ph.interval;q=g.quiescent;cold=q.cold
 opt=g.archive.credentials.OperatorMTLSOptions(str(R/'admin.conf'))
 verify_image=load('final_runtime_observer','verify-bortus-current-node-image.py')
 deadline=time.monotonic()+2000
 verify_image.verify(min(deadline,time.monotonic()+120))
 base=cold.Client();initial=base.inspect('19cc4b60-4536-4d80-8789-e27b5ad48b79',IMAGE)
 run_id=uuid.uuid4().hex[:12];record=cold.prepare(base,initial,IMAGE,run_id)
 controls={k:base.get(cold.RESOURCES[k][0],cold.RESOURCES[k][1],cold.RESOURCES[k][2]) for k in q.CONTROL_KEYS}
 pins={k:cold.identity(obj)|{'spec_sha256':q.control_spec(obj,k),'original':obj['spec'].get(cold.RESOURCES[k][3],False)} for k,obj in controls.items()}
 record['baseline'].update(legacy_image=LEGACY,quiescent_storage_pins={})
 for kind in ('pvc','pv','storageclass'):
  obj=base.get(kind,'longhorn' if kind=='storageclass' else initial['identities']['claim' if kind=='pvc' else 'pv']['name'],'bortus' if kind=='pvc' else None)
  body=obj['spec'] if kind!='storageclass' else {k:v for k,v in obj.items() if k not in ('apiVersion','kind','metadata')}
  record['baseline']['quiescent_storage_pins'][kind]={k:obj['metadata'].get(k) for k in ('name','namespace','uid')}|{'spec_sha256':q.sha(body)}
 api=ph.admission.API(opt)
 files=['flux/releases/bortus-restore-maintenance/bortus-kv-guard-'+x+'-policy.json' for x in ('pods','templates','cronjobs')]
 def current_binding(phase):
  actual=[];policy_pins={}
  for variant in ('pods','templates','cronjobs'):
   name='bortus-kv-guard-'+variant;pair={}
   for kind in (ph.validator.POLICY,ph.validator.BINDING):
    obj=api.guard(kind,name,deadline=min(deadline,time.monotonic()+290));actual.append(obj);prefix='' if kind==ph.validator.POLICY else 'binding_'
    pair.update({prefix+'uid':obj['metadata']['uid'],('resourceVersion' if not prefix else 'binding_resourceVersion'):obj['metadata']['resourceVersion'],prefix+'spec_sha256':hashlib.sha256(ph.validator.canonical_spec(kind,obj['spec'])).hexdigest()})
   policy_pins[name]=pair
  policy=next(x for x in actual if x['kind']==ph.validator.POLICY);v={x['name']:x['expression'] for x in policy['spec']['variables']}
  contract={'namespace':'bortus','guarded_service_account':'bortus-kv','protected_pvc_names':json.loads(v['protectedClaims']),'protected_secret_names':json.loads(v['protectedSecrets']),'approved_image_references':json.loads(v['approvedImages'])}
  binding={'phase':phase,'image':IMAGE,'source_sha256':hashlib.sha256((ROOT/'bortus-qualified-preload-node.py').read_bytes()).hexdigest(),
           'qualification_receipt_sha256':hashlib.sha256((A/'qualified-node-imports.json').read_bytes()).hexdigest(),'contract':contract,'policy_pins':policy_pins}
  ph.binding_checked(binding)
  need((LEGACY in contract['approved_image_references'])==(phase=='legacy-approved'))
  return binding
 legacy=current_binding('legacy-approved');record['baseline']['protected_claim_names']=legacy['contract']['protected_pvc_names']
 source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'bortus-qualified-preload-node.py',ROOT/'verify-bortus-current-node-image.py',ROOT/'saved-node-credential.py']}
 if not args.execute:
  print(json.dumps({'final_preflight_passed':True,'three_node_image_verified':True,'attended_reader_passed':True,'production_changes':0}));return
 parent=A/'recovery/bortus-checkpoints';need(parent.is_dir() and parent.stat().st_uid==os.getuid() and parent.stat().st_mode&0o777==0o700)
 directory=parent/run_id;journal=observer=client=qualifier=None
 def get(kind,name,ns='flux-system'):
  result=subprocess.run([str(R/'bin/kubectl'),'--kubeconfig',str(R/'admin.conf'),'--request-timeout=15s','get',kind,name,'-n',ns,'-o','json'],capture_output=True,timeout=20);need(result.returncode==0);return json.loads(result.stdout)
 def publish(paths,message):
  need(not git('diff','--cached','--name-only'))
  head=git('rev-parse','HEAD');remote=git('ls-remote','origin','refs/heads/main').split()[0];need(head==remote)
  git('diff','--check','--',*paths);git('add','--',*paths);git('commit','--only','-m',message,'--',*paths)
  commit=git('rev-parse','HEAD');git('push','origin','HEAD:refs/heads/main');need(git('ls-remote','origin','refs/heads/main').split()[0]==commit)
  write_once(directory/('publication-'+commit[:12]+'.json'),{'commit':commit,'paths':paths,'private_pipeline':True,'actions_used':False})
  until=min(deadline,time.monotonic()+650)
  while time.monotonic()<until:
   status=json.loads(STATUS.read_bytes())
   if status.get('sourceSHA')==commit and status.get('passed') is False and status.get('phase') in ('failed','check_failed','publish_failed'):raise RuntimeError('singleton_validation_failed')
   repo=get('gitrepository','branconet-charts');owner=get('kustomization','migration-releases')
   rev='validated@sha1:'+commit
   if (status.get('sourceSHA')==commit and status.get('passed') is True and status.get('actionsUsed') is False
       and repo.get('status',{}).get('artifact',{}).get('revision')==rev and owner.get('status',{}).get('lastAppliedRevision')==rev
       and any(x['type']=='Ready' and x['status']=='True' for x in owner.get('status',{}).get('conditions',[]))):return commit
   time.sleep(3)
  raise RuntimeError('validated_flux_publication_not_observed')
 try:
  journal=g.watch.ControlJournal(directory,record).open(new=True)
  observer=g.watch.Observer(journal,pins,g.watch.TLSControls(opt),deadline=deadline);observer.start()
  client=g.IntervalClient(observer,deadline=deadline)
  archive=g.archive.QuiescentArchive(opt,str(R/'admin.conf'),str(Path.home()/'.ssh/id_ed25519.pub'),str(Path.home()/'.ssh/id_ed25519'),quiescent_module=q,windows_ciphertext_nas=True)
  def verify(binding,until):
   need(all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value for name,value in source_hashes.items()))
   verify_image.verify(until)
   actual=current_binding(binding['phase']);need(ph.validator.canonical(actual)==ph.validator.canonical(binding))
   return copy.deepcopy(binding)
  old_inputs=R/'schema-current-writer-66f5c84fa205'
  qualifier=ph.PhaseQualifier(observer,archive,legacy,verify,ready_directory=A,reader_path=old_inputs/'schema-reader.cjs',manifest_path=old_inputs/'migration-manifest.json',interval_module=g)
  operation=q.QuiescentCheckpoint(client,journal,observer.trace,qualifier,archive,deadline=deadline);qualifier.bind(operation)
  write_once(directory/'release-intent.json',{'scope':'BORTUS-only final authorized promotion','image':IMAGE,'original_image':LEGACY,'attended_reader_accepted':True,'new_credentials_created':False})
  operation.capture_quiescent();print(json.dumps({'run_id':run_id,'latest_backup_confirmed':True,'original_writer_zero':True}),flush=True)
  operation.open_guard_transition()
  for rel in files:
   path=CHARTS/rel;obj=json.loads(path.read_bytes());variable=next(v for v in obj['spec']['variables'] if v['name']=='approvedImages')
   images=json.loads(variable['expression']);need(LEGACY in images and IMAGE in images);variable['expression']=json.dumps([i for i in images if i!=LEGACY])
   path.write_text(json.dumps(obj,indent=2)+'\n')
  guard_commit=publish(files,'Withdraw pre-migration BORTUS image before the native release')
  forward=current_binding('forward-compatible');qualifier.authorize_forward(forward)
  print(json.dumps({'run_id':run_id,'guard_withdrawal_revision':guard_commit,'original_writer_zero':True}),flush=True)
  def launch(binding,until):
   import yaml
   rel='flux/releases/bortus.yaml';path=CHARTS/rel;hr=yaml.safe_load(path.read_text());need(hr['spec']['values']['image']==IMAGE and hr['spec']['values']['nativeKv']['guardedAdoption'] is False and hr['spec']['suspend'] is True)
   text=path.read_text();need(text.count('  suspend: true')==1);path.write_text(text.replace('  suspend: true','  suspend: false'))
   commit=publish([rel],'Deploy qualified BORTUS native profile with adoption held off')
   result={'revision':commit,'image':IMAGE,'guarded_adoption':False,'prior_writer_quiesced':True,'schema_rehearsal_passed':True}
   write_once(directory/'entrypoint-publication.json',result)
   return {'dispatch_receipt_sha256':hashlib.sha256((directory/'entrypoint-publication.json').read_bytes()).hexdigest()}
  operation.dispatch_entrypoint(launch)
  print(json.dumps({'run_id':run_id,'entrypoint_submitted':True,'production_acceptance_pending':True}),flush=True)
 except Exception as error:
  if journal is not None:write_once(directory/'final-release-failure.json',{'error_type':type(error).__name__,'code':getattr(error,'code',None),'scope':'Inspect exact journals before any replay; no automatic legacy resume after guard withdrawal'})
  raise
 finally:
  for item in (qualifier,client,observer,journal):
   if item is not None:item.close()
if __name__=='__main__':
 try:main()
 except Exception as error:
  import traceback
  print(json.dumps({'final_release_failed':type(error).__name__,'code':getattr(error,'code',None),'locations':[Path(f.filename).name+':'+str(f.lineno) for f in traceback.extract_tb(error.__traceback__)]}),file=sys.stderr);raise SystemExit(1)
