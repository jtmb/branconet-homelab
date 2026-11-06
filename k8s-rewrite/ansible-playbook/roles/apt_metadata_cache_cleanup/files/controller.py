"""Finite per-host APT metadata cleanup; individual refused targets remain protected."""
import argparse,contextlib,datetime,hashlib,importlib.util,io,json,os,runpy,shlex,subprocess,sys
from pathlib import Path
F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028';OUT=H/'apt-metadata-cache-cleanup'
SUCCESS='kubernetes-maintenance-receipts/56f152a9adc044478db62e3cacc65288-result.json'
SUCCESS_SHA='583d6a0eece75e23940ff4d6f1a4a805dfe6b58148fc8a3d0f44a1d5a9736072'
COMPLETED_CORE_SHA='0e0be0645a4f4077a3bbdad577db05d6498874954c33ec1c98291a3fd8670bc4'
LEGACY_SHA='e1e1f4bbd6037823b06f390dcdae660e81dbd801acda885ed2a6f380169bd707'
KERNEL_COMPLETE='kernel-maintenance-complete-master-2f51538a0f9c4cd8808bc53ca0528231.json'
KERNEL_COMPLETE_SHA='1f2cd07b0b8221538ae76e21df33e4e72313e3164a6273b6d9c4d837a653937c'
REFRESH='kernel-maintenance-refresh-3679b3e5f4bb43e2b4afbf47d80c437c.json'
REFRESH_SHA='8bd93b6ce036ebaa07bb1cdb69045e6aaf8b9c86fb9cb7fa14819262becf7f6c'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):
 with path.open('x') as stream:json.dump(value,stream,indent=2);stream.flush();os.fsync(stream.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 return {'path':str(path),'sha256':sha(path)}
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['inventory','apply'],nargs='?',default='inventory')
 parser.add_argument('--host',choices=['masternode','workernode2'],required=True);parser.add_argument('--target',help='Exact qualified absolute file; required only for apply')
 parser.add_argument('--include-installed-kernel202-archives',action='store_true')
 parser.add_argument('--allow-observed-idle-packagekit',action='store_true')
 parser.add_argument('--after-closed-admission-failure',type=Path)
 parser.add_argument('--after-closed-admission-failure-sha256')
 parser.add_argument('--after-closed-transport-failure',type=Path)
 parser.add_argument('--after-closed-transport-failure-sha256')
 parser.add_argument('--after-inventory-format-repair',type=Path)
 parser.add_argument('--after-inventory-format-repair-sha256')
 parser.add_argument('--reviewed-controller-transition',type=Path)
 parser.add_argument('--reviewed-controller-transition-sha256')
 parser.add_argument('--fresh-recovery-checkpoint',type=Path)
 parser.add_argument('--fresh-recovery-checkpoint-sha256')
 a=parser.parse_args();assert (a.mode=='apply')==bool(a.target)
 assert bool(a.fresh_recovery_checkpoint)==bool(a.fresh_recovery_checkpoint_sha256)
 recovery={'path':str(a.fresh_recovery_checkpoint),'sha256':a.fresh_recovery_checkpoint_sha256} if a.fresh_recovery_checkpoint else None
 assert recovery is None or (a.mode=='apply' and a.reviewed_controller_transition)
 assert bool(a.reviewed_controller_transition)==bool(a.reviewed_controller_transition_sha256)
 transition={'path':str(a.reviewed_controller_transition),'sha256':a.reviewed_controller_transition_sha256} if a.reviewed_controller_transition else None
 assert transition is None or a.mode=='apply'
 assert bool(a.after_inventory_format_repair)==bool(a.after_inventory_format_repair_sha256)
 assert not a.after_inventory_format_repair or not (a.after_closed_transport_failure or a.after_closed_admission_failure)
 assert bool(a.after_closed_transport_failure)==bool(a.after_closed_transport_failure_sha256)
 assert not (a.after_closed_transport_failure and a.after_closed_admission_failure)
 assert not a.after_closed_transport_failure or (a.mode=='inventory' and a.target is None)
 assert bool(a.after_closed_admission_failure)==bool(a.after_closed_admission_failure_sha256)
 assert not a.after_closed_admission_failure or (a.mode=='inventory' and a.target is None)
 assert not a.include_installed_kernel202_archives or a.host=='masternode','Archive opt-in is master-only'
 password=sys.stdin.buffer.readline(130).removesuffix(b'\n');assert 0<len(password)<=128 and not any(x in password for x in (b'\n',b'\r',b'\0'))
 os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD',None);os.umask(0o077)
 assert os.getuid()==1000 and F.is_mount() and H.resolve()==H
 assert subprocess.check_output(['findmnt','-n','-o','UUID','--target',str(F)],text=True).strip()=='3c792469-ea0e-4a2c-98e8-1185b141607b'
 repo=Path(__file__).resolve().parents[5];roles=repo/'k8s-rewrite/ansible-playbook/roles'
 support=runpy.run_path(str(repo/'scripts/migration/reconcile-kubernetes-vendor.py'))
 plan,success=support['terminal'](H,F,SUCCESS,SUCCESS_SHA)
 core_source=repo/'scripts/migration/verify-completed-core-preservation.py'
 assert sha(core_source)==COMPLETED_CORE_SHA
 core=module('apt_completed_core',core_source)
 live=core.validate(repo, transition=transition, recovery=recovery)
 refresh=H/REFRESH;assert sha(refresh)==REFRESH_SHA
 refresh_data=json.loads(refresh.read_text());assert refresh_data['mode']=='refresh' and refresh_data['exitCode']==0 and refresh_data['finishedUTC']
 kernel_completion=None
 if a.include_installed_kernel202_archives:
  path=H/KERNEL_COMPLETE;assert sha(path)==KERNEL_COMPLETE_SHA
  completed=json.loads(path.read_text());assert completed['mode']=='complete-master' and completed['exitCode']==0 and completed['settings']['kernel_maintenance_apply'] is True and completed['settings']['kernel_maintenance_reboot'] is True
  assert datetime.datetime.fromisoformat(completed['finishedUTC'])<datetime.datetime.fromisoformat(json.loads(Path(success['path']).read_text())['finishedUTC'])
  kernel_completion={'path':str(path),'sha256':KERNEL_COMPLETE_SHA}
 legacy=roles/'worker2_obsolete_kernel_cleanup/files/remote.py';assert sha(legacy)==LEGACY_SHA
 remote=Path(__file__).with_name('remote.py')
 OUT.mkdir(mode=0o700,exist_ok=True);assert OUT.resolve()==OUT and OUT.stat().st_uid==1000 and not OUT.stat().st_mode&0o077
 inventory_path=OUT/(a.host+'-inventory.json')
 format_closure=None;prior_format_inventory=None
 if a.after_inventory_format_repair:
  pins={'masternode':'c7b43c8e62faa20bff041cba36d872596b1b669a1bd54364fd5a6e04afd94305','workernode2':'e5276481293ad3ec0358303cd77495cae8cf471bfab575576cc23a55c8203c10'}
  prior=a.after_inventory_format_repair;assert prior==inventory_path and prior.resolve()==prior and sha(prior)==a.after_inventory_format_repair_sha256==pins[a.host]
  previous=json.loads(prior.read_text());assert previous['host']==a.host and previous['sourceSHA256']=='9427e6694605c948d18babff54e4975cfc6c56a6cbd0ed9c69704dfc01126ada' and previous['remoteSHA256']=='b6f4caf50a4369e6dd55f52e6ec2879318c2da30dac94d84a57b8160282e8e7f'
  assert previous['includeInstalledKernel202Archives']==a.include_installed_kernel202_archives and previous['allowObservedIdlePackagekit']==a.allow_observed_idle_packagekit
  observation=previous['observation'];assert observation['packagesChanged'] is False and not any(x['kind'].startswith('signed-derived-') for x in observation['qualified']) and observation['signedAuthorities']=={}
  if a.host=='masternode':
   assert len(observation['retained'])==12 and all(x['reason']=='AssertionError: No matching gpgv-authorized Ubuntu Packages stanza; retain archive' and x['path'].startswith('/var/cache/apt/archives/') for x in observation['retained'])
  else:
   assert len(observation['retained'])==2 and {x['path'] for x in observation['retained']}=={'/var/cache/apt/pkgcache.bin','/var/cache/apt/srcpkgcache.bin'}
   assert all(x['reason']=="OSError: [Errno 22] Invalid argument: '/proc/796801/mountinfo'" for x in observation['retained'])
  witnesses={}
  for name,digest in {'pre-format-controller.py':previous['sourceSHA256'],'pre-format-remote.py':previous['remoteSHA256']}.items():
   path=OUT/name;assert sha(path)==digest;witnesses[name]={'path':str(path),'sha256':digest}
  old_remote=(OUT/'pre-format-remote.py').read_text();assert "glob('*_Packages.lz4')" in old_remote and "p.name.endswith('_Packages.lz4')" in old_remote
  if a.mode=='inventory':assert not list(OUT.glob(a.host+'-*-intent.json')) and not list(OUT.glob(a.host+'-*-result.json')),'Existing submitted cleanup cannot enter a new format generation'
  prior_format_inventory=observation
  format_closure={'originalInventory':{'path':str(prior),'sha256':pins[a.host]},'sourceWitnesses':witnesses,'scope':'native-plain-signed-index-and-proven-exited-mountinfo-format-only','priorTargetSafetyChecksBypassed':False,'freshFullQualificationRequired':True}
  inventory_path=OUT/(a.host+'-inventory-format-repair.json')
 closure=None
 if a.allow_observed_idle_packagekit:
  diagnostic=H/'packagekit-idle-readonly-observation.json'
  assert sha(diagnostic)=='a256467b11afe59c748db71542dfb9c0a3389a9f72760fcaa060392ed23319aa'
 if a.after_closed_admission_failure:
  prior=a.after_closed_admission_failure
  assert prior==OUT/'masternode-b11a85b296a90afc46043043-failure.json' and a.host=='masternode'
  assert prior.resolve()==prior and sha(prior)==a.after_closed_admission_failure_sha256=='ab2646f365ff658bb51b8c14e27ea62f2a5ee28425fc7ed221d6f6f24afa4e0c'
  failed=json.loads(prior.read_text());assert failed['target'] is None and failed['host']==a.host and failed['reason']=='AssertionError'
  assert not inventory_path.exists() and not list(OUT.glob(a.host+'-*-intent.json')) and not list(OUT.glob(a.host+'-*-result.json'))
  witnesses={}
  for name,digest in {'pre-idle-admission-controller.py':'8d579fe5eda40ce19df45db9048b745410eed4a1a098a865961762df84ff91ed','pre-idle-admission-remote.py':'b5303a7dad89693de62ea6141ad95e0b8d6521425b6ae5050f496bd5c33d25cb'}.items():
   path=OUT/name;assert path.resolve()==path and sha(path)==digest;witnesses[name]={'path':str(path),'sha256':digest}
  closure={'phase':'inventory','target':None,'priorFailure':{'path':str(prior),'sha256':sha(prior)},'sourceWitnesses':witnesses,
   'basis':'Exact failed pre-target process admission; no inventory saved, no target intent/result. Does not clear any target-specific refusal.',
   'priorOutcome':'closed-before-target-qualification','diagnostic':{'path':str(H/'packagekit-idle-readonly-observation.json'),'sha256':'a256467b11afe59c748db71542dfb9c0a3389a9f72760fcaa060392ed23319aa'}}
 transport_closure=None
 if a.after_closed_transport_failure:
  allowed={'masternode':('masternode-bc02404e583aa0bd587a36a7-failure.json','a5e93b07ea1eaa6027ddd8cea57d9a080c958d80faaf3d406f7e37429012c0a7'),
   'workernode2':('workernode2-b11a85b296a90afc46043043-failure.json','789dca0547de21e172c7f2a3421ea60d0d2274a25d191951cc97f78ba25f9e1e')}
  name,digest=allowed[a.host];prior=a.after_closed_transport_failure
  assert prior==OUT/name and prior.resolve()==prior and sha(prior)==a.after_closed_transport_failure_sha256==digest
  failed=json.loads(prior.read_text());assert failed['host']==a.host and failed['target'] is None and failed['phase']=='inventory'
  assert not inventory_path.exists() and not list(OUT.glob(a.host+'-*-intent.json')) and not list(OUT.glob(a.host+'-*-result.json'))
  old_controller=OUT/'pre-transport-controller.py';old_remote=OUT/'pre-transport-remote.py'
  assert sha(old_controller)=='76c6d5ed935082a5c430c6a51a4756ce3edbc31add8f54cb86b2da4e90d0bff8'
  assert sha(old_remote)=='b6f4caf50a4369e6dd55f52e6ec2879318c2da30dac94d84a57b8160282e8e7f'
  assert failed['sourceSHA256']==sha(old_controller) and failed['remoteSHA256']==sha(old_remote)
  diagnostic=H/'apt-definitions-only-transport-diagnostic.json'
  assert sha(diagnostic)=='32fb45beab10ae647b0027c758609d5ef2460715322663342494d5996896b068'
  diag=json.loads(diagnostic.read_text());assert diag['rc']==1 and diag['cacheTargetsReadOrChanged'] is False and 'unterminated string literal (detected at line 5)' in diag['stderrTail']
  import ast
  tree=ast.parse(old_controller.read_text())
  assignments=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='carrier' for t in n.targets)]
  assert len(assignments)==1
  expression=assignments[0].value
  assert isinstance(expression,ast.Call) and isinstance(expression.func,ast.Attribute) and expression.func.attr=='replace'
  old_carrier=ast.literal_eval(expression.func.value).replace('COMMAND',repr(['sudo','-n','python3','-B','-c',old_remote.read_text()]))
  try:compile(old_carrier,'<prior-transport-carrier>','exec')
  except SyntaxError as error:assert error.lineno==5 and 'unterminated string literal' in error.msg
  else:raise AssertionError('Prior carrier was not the bound pre-execution syntax failure')
  transport_closure={'priorFailure':{'path':str(prior),'sha256':digest},'sourceWitnesses':{'controller':{'path':str(old_controller),'sha256':sha(old_controller)},'remote':{'path':str(old_remote),'sha256':sha(old_remote)}},
   'diagnostic':{'path':str(diagnostic),'sha256':sha(diagnostic)},'phase':'inventory','target':None,'priorOutcome':'closed-before-carrier-execution',
   'priorAdmissionContinuation':failed.get('closedAdmissionContinuation'),'generatedCarrierSyntaxErrorLine':5,'targetSpecificRefusalsCleared':False}
  if a.host=='masternode':
   chain=transport_closure['priorAdmissionContinuation'];assert chain['priorFailure']['sha256']=='ab2646f365ff658bb51b8c14e27ea62f2a5ee28425fc7ed221d6f6f24afa4e0c'
   assert sha(Path(chain['priorFailure']['path']))==chain['priorFailure']['sha256']
 token=hashlib.sha256((a.target or 'inventory').encode()).hexdigest()[:24]
 if format_closure and a.mode=='inventory':token=hashlib.sha256(('inventory-format-repair:'+format_closure['originalInventory']['sha256']).encode()).hexdigest()[:24]
 if transport_closure:token=hashlib.sha256(('inventory-after-transport:'+transport_closure['priorFailure']['sha256']).encode()).hexdigest()[:24]
 if closure:token=hashlib.sha256(('inventory-after-closed:'+closure['priorFailure']['sha256']).encode()).hexdigest()[:24]
 intent=OUT/(a.host+'-'+token+'-intent.json');result_path=OUT/(a.host+'-'+token+'-result.json');failure=OUT/(a.host+'-'+token+'-failure.json')
 assert not intent.exists() and not result_path.exists() and not failure.exists(),'Existing exact-target attempt/refusal cannot be retried'
 data={'mode':a.mode,'host':a.host,'legacySource':legacy.read_text(),'includeInstalledKernel202Archives':a.include_installed_kernel202_archives,'allowObservedIdlePackagekit':a.allow_observed_idle_packagekit,'inventoryFormatRepair':bool(format_closure),'priorFormatInventory':prior_format_inventory}
 ownership={'owner':'apt-metadata-cache-cleanup','physicalVolume':str(F),'physicalUUID':'3c792469-ea0e-4a2c-98e8-1185b141607b','host':a.host,
  'freshRecoveryCheckpoint':recovery,'reviewedControllerTransition':transition,'inventoryFormatRepair':format_closure,'allowObservedIdlePackagekit':a.allow_observed_idle_packagekit,'closedAdmissionContinuation':closure,'closedTransportContinuation':transport_closure,
  'sourceSHA256':sha(Path(__file__)),'completedCoreVerifierSHA256':COMPLETED_CORE_SHA,'remoteSHA256':sha(remote),'legacyGuardSHA256':LEGACY_SHA,'success':success,'live':live,
  'includeInstalledKernel202Archives':a.include_installed_kernel202_archives,'completedKernel202':kernel_completion,
  'signedRefresh':{'path':str(refresh),'sha256':REFRESH_SHA},'checkpoint':plan['checkpoint'],
  'protected':'dpkg status/holds/config/native runtimes/data/signed InRelease/keyrings/original receipts; all unqualified archives and unknown indexes excluded',
  'lastConsumer':'Completed kernel APT transaction followed by successful native three-host patch and current58 recovery',
  'regeneration':'apt-get update from preserved configured signed origins, then apt-cache gencaches; no refresh/download during cleanup'}
 command=['sudo','-n','python3','-B','-c',remote.read_text()]
 carrier=r"""import os,subprocess,sys
password=b''
while True:
 b=os.read(0,1)
 if b==b'\n':break
 assert b and len(password)<128
 password+=b
assert subprocess.run(['sudo','-k'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE).returncode==0
assert subprocess.run(['sudo','-S','-p','','-v'],input=password+b'\n',stdout=subprocess.DEVNULL,stderr=subprocess.PIPE).returncode==0
password=None
sys.exit(subprocess.run(COMMAND,stdin=0).returncode)
""".replace('COMMAND',repr(command))
 compile(carrier,'<apt-metadata-carrier>','exec')
 if a.mode=='apply':
  inventory=json.loads(inventory_path.read_text())
  prior_source='a3f1472aedad04e2e750835deb6c19a08925a9e943eae9255e083cd4487589f2'
  if transition is not None and inventory['sourceSHA256']==prior_source:
   pins={'masternode':'d15f603522d8ed305a3127f8aefa1618360e7714e6305b96ccd5700f0428b956','workernode2':'c4fe6ce400751013ad222a72827cee5f772878906ffcf941703e5920a14d64e1'}
   assert inventory_path==OUT/(a.host+'-inventory-format-repair.json') and sha(inventory_path)==pins[a.host]
   assert inventory['completedCoreVerifierSHA256']=='52210124219d6b7f0781d217e1d246a59902148235c2b65b5d51bc2754dee512'
   for name,digest in {'pre-controller-transition-core.py':inventory['completedCoreVerifierSHA256'],'pre-controller-transition-controller.py':prior_source,'pre-controller-transition-remote.py':'3de89b0c90ff17c1f4b24bd26b3aba3262bb2c0e00e55c3c8c3dc15e5a6a7719'}.items():assert sha(OUT/name)==digest
   ownership['priorQualifiedInventory']={'path':str(inventory_path),'sha256':pins[a.host]}
  else:assert inventory['sourceSHA256']==ownership['sourceSHA256']
  assert inventory['remoteSHA256']==ownership['remoteSHA256']=='3de89b0c90ff17c1f4b24bd26b3aba3262bb2c0e00e55c3c8c3dc15e5a6a7719'
  assert inventory['allowObservedIdlePackagekit']==a.allow_observed_idle_packagekit
  assert inventory.get('inventoryFormatRepair')==format_closure
  assert inventory['success']==success and inventory['host']==a.host and inventory['includeInstalledKernel202Archives']==a.include_installed_kernel202_archives
  candidates=[x for x in inventory['observation']['qualified'] if x['path']==a.target];assert len(candidates)==1
  assert not any(x['path']==a.target for x in inventory['observation']['retained']),'Inventory refusal permanently protects this target'
  if candidates[0]['kind'].startswith('signed-derived-') and a.include_installed_kernel202_archives:
   for archive in inventory['observation']['qualified']:
    if archive['kind']!='installed-kernel202-archive':continue
    archive_token=hashlib.sha256(archive['path'].encode()).hexdigest()[:24]
    archive_result=OUT/(a.host+'-'+archive_token+'-result.json')
    assert archive_result.is_file(),'Keep signed indexes until every qualified archive is consumed'
    prior=json.loads(archive_result.read_text())
    accepted_prior_sources={prior_source:'52210124219d6b7f0781d217e1d246a59902148235c2b65b5d51bc2754dee512'}
    if recovery is not None:
     assert sha(OUT/'pre-recovery-renewal-controller.py')=='c32bad1982966ad7dff926fa1a12e3fc6fb108bac5482511747424cbf90823ec' and sha(OUT/'pre-recovery-renewal-core.py')=='c470662acc2121be66990f149ea0d662ae0e43799e758ce4db6ffd0af9e00a51'
     accepted_prior_sources['c32bad1982966ad7dff926fa1a12e3fc6fb108bac5482511747424cbf90823ec']='c470662acc2121be66990f149ea0d662ae0e43799e758ce4db6ffd0af9e00a51'
    if transition is not None and prior['sourceSHA256'] in accepted_prior_sources:
     archived_intent=OUT/(a.host+'-'+archive_token+'-intent.json');submitted=json.loads(archived_intent.read_text())
     assert submitted['sourceSHA256']==prior['sourceSHA256'] and submitted['remoteSHA256']==prior['remoteSHA256']==ownership['remoteSHA256']
     assert submitted['success']==success and submitted['target']==prior['target']==archive and submitted['host']==prior['host']==a.host
     assert submitted['completedCoreVerifierSHA256']==prior['completedCoreVerifierSHA256']==accepted_prior_sources[prior['sourceSHA256']]
     if prior['sourceSHA256']!=prior_source:assert submitted['reviewedControllerTransition']==prior['reviewedControllerTransition']==transition
     ownership.setdefault('priorArchiveOperations',[]).append({'intent':{'path':str(archived_intent),'sha256':sha(archived_intent)},'result':{'path':str(archive_result),'sha256':sha(archive_result)}})
    else:assert prior['sourceSHA256']==ownership['sourceSHA256']
    assert prior['success']==success and prior['observation']['removed']==archive and prior['observation']['protectedUnchanged'] is True
  data.update(inventory=inventory['observation'],target=candidates[0]);ownership['target']=candidates[0]
  save(intent,ownership)
  assert sha(core_source)==COMPLETED_CORE_SHA
  ownership['postIntentCorePreservation']=core.validate(repo, transition=transition, recovery=recovery)
 else:
  assert not inventory_path.exists(),'Do not replace an existing per-host inventory or its refusals'
  if closure:save(OUT/(a.host+'-'+token+'-closed-admission.json'),ownership)
  if transport_closure:save(OUT/(a.host+'-'+token+'-closed-transport.json'),ownership)
 public_error=None;response=None
 try:
  ip={'masternode':'192.168.0.4','workernode2':'192.168.0.5'}[a.host]
  response=subprocess.run(support['SSH']+['james@'+ip,'exec '+shlex.join(['python3','-B','-c',carrier])],input=password+b'\n'+json.dumps(data).encode(),capture_output=True,timeout=360)
  password=None
  if response.returncode!=0 and len(response.stdout)<4*1024**2:
   try:
    value=json.loads(response.stdout)
    public_error={k:value[k] for k in ('passed','errorType','stage','reason','targetRetainedOrUncertain') if k in value}
   except (ValueError,TypeError):public_error={'stage':'transport','reason':'no_structured_remote_diagnostic'}
  assert response.returncode==0 and len(response.stdout)<4*1024**2,'Metadata phase failed; preserve exact target'
  observation=json.loads(response.stdout);ownership['observation']=observation
  if a.mode=='apply':assert observation['protectedUnchanged'] is True and observation['packagesChanged'] is False
  print(json.dumps(save(inventory_path if a.mode=='inventory' else result_path,ownership)))
 except Exception as error:
  if not failure.exists():save(failure,{'host':a.host,'target':a.target,'reason':type(error).__name__,'phase':a.mode,'sourceSHA256':ownership['sourceSHA256'],'remoteSHA256':ownership['remoteSHA256'],'closedAdmissionContinuation':closure,'closedTransportContinuation':transport_closure,'publicRemoteError':public_error,'exitCode':None if response is None else response.returncode,'retryProhibited':True,'otherIndependentlyQualifiedTargetsNotExcluded':True})
  raise
 finally:password=None

if __name__=='__main__':main()
