"""Finite native v1 snapshot GC; no snapshot-delete, raw files, policy or replica changes."""
import argparse,datetime,hashlib,importlib.util,json,os,shlex,subprocess,time,uuid,urllib.request
from pathlib import Path
REPO=Path('/mnt/c/Users/james/.codex/worktrees/cluster-headroom-security-tls/kubernetes migration')
F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028'
R=H/'longhorn-snapshot-gc'
CORE_SHA='0e0be0645a4f4077a3bbdad577db05d6498874954c33ec1c98291a3fd8670bc4'
DISCOVERY_SHA='f1a166bddfb3bed7241961fc9ff4cc991fccf4b7ede1c7507be40d33a3cb8f4c'
IMAGE='docker.io/longhornio/longhorn-engine:v1.13.0@sha256:b0cc5090889d57705acd69c5106492992e84560170ac3bec4a1cc8dd3fe83ca6'
CATALOG={'sonarr':('pvc-ff5158b3-cecf-46f9-b85e-ad8566cb9068','20cf8a05-5e44-4f02-a2a0-8c321f009b33'),'ingenium':('pvc-1005b62c-b731-4c76-a68c-f635ef74c378','56ae32a5-0f39-4509-b81d-b9fe82e5a376'),'radarr-data-0':('pvc-7f07da4f-a34e-4bd0-a4a0-90b94f5a0fec','e9c3b3a3-a39b-481d-858a-46f4cd2b6391'),'xteve-data-0':('pvc-d40f1490-7254-4599-be82-2fad35abb88b','72da15a8-b7da-4bc4-bb61-f111818977d0'),'ruckus-db-upstream-20261026':('pvc-3d587252-21b5-4982-b70a-4cfee6ae49bd','dd63fa21-6801-4f0e-81d4-95817ef944a1')}
IPS={'masternode':'192.168.0.4','workernode1':'192.168.0.6','workernode2':'192.168.0.5'}
SSH=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10','-i','/home/brajam/.ssh/id_ed25519','-p','2002']
UPSTREAM={'https://raw.githubusercontent.com/longhorn/longhorn-engine/v1.13.0/pkg/replica/replica.go': 'c00b101a498021102a8690de15d652d86a2b9e4d4a429427dc07a3bb772bff65', 'https://raw.githubusercontent.com/longhorn/longhorn-engine/v1.13.0/pkg/util/util.go': '30e64d08bb55b79df14beb3938332a0b2485bf5618f11c36b4472781b426e07f', 'https://raw.githubusercontent.com/longhorn/longhorn-engine/v1.13.0/pkg/sync/rpc/server.go': '3f978989f137a904883a17ab4d6a2733f90ad6571abcfa41993c0cf919305316', 'https://raw.githubusercontent.com/longhorn/longhorn-manager/v1.13.0/api/snapshot.go': '9ee520db71fe9fff5d5d67e80a7315cea527e217f34fbd297dcc2da9017cf488'}

BACKUP_STATUS_FORMAT_REPAIR=False

def need(ok,why):
 if not ok:raise ValueError(why)
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
 need(p.parent.resolve()==p.parent and R in p.parents,'owned_receipt_path')
 fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'w')as f:json.dump(x,f,indent=2);f.flush();os.fsync(f.fileno())
 fd=os.open(p.parent,os.O_DIRECTORY|os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)
def loadmodule(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def call(host,args,timeout=25):
 p=subprocess.run(SSH+['james@'+IPS[host],shlex.join(args)],stdin=subprocess.DEVNULL,capture_output=True,timeout=timeout)
 need(p.returncode==0 and len(p.stdout)<16*1024**2,'bounded_native_request_failed:'+str(p.returncode)+':'+p.stderr.decode(errors='replace')[-1200:])
 return json.loads(p.stdout)
def kube(args):return call('masternode',['kubectl','--request-timeout=15s']+args)
def items(kind):return kube(['-n','longhorn-system','get',kind,'-o','json'])['items']
def core():
 p=REPO/'scripts/migration/verify-completed-core-preservation.py';need(sha(p)==CORE_SHA,'core_source')
 return loadmodule('completed_core',p).validate(REPO,transition={'path':str(H/'reviewed-controller-transition-1c6f.json'),'sha256':'94198c86ebbbe303341ef6be5cc3a1666f938771083344848485824a3d6682e0'},recovery={'path':str(H/'post-core-cleanup-current58-manifest.json'),'sha256':'974c53fee4aeed789918fb0373a59bff22447a3e140d45fd3d22fb7c1973f455'})
def sources():
 for url,pin in UPSTREAM.items():
  raw=urllib.request.urlopen(url,timeout=20).read(1024**2+1);need(len(raw)<=1024**2 and hashlib.sha256(raw).hexdigest()==pin,'exact_upstream_source')
 return UPSTREAM

def manager():
 service=kube(['-n','longhorn-system','get','service','longhorn-backend','-o','json'])
 need(service['spec']['selector']=={'app':'longhorn-manager'} and service['spec']['ports']==[{'name':'manager','port':9500,'protocol':'TCP','targetPort':'manager'}],'native_service_identity')
 pods=[p for p in items('pods')if p['metadata'].get('labels',{}).get('app')=='longhorn-manager' and p['spec']['nodeName']=='masternode']
 need(len(pods)==1,'one_manager');p=pods[0]
 need(not p['metadata'].get('deletionTimestamp') and any(c['type']=='Ready'and c['status']=='True'for c in p['status']['conditions']),'manager_ready')
 image=next(c['image']for c in p['spec']['containers']if c['name']=='longhorn-manager');need('longhorn-manager:v1.13.0@sha256:'in image,'manager_version')
 return {'name':p['metadata']['name'],'uid':p['metadata']['uid'],'ip':p['status']['podIP'],'image':image,'serviceUID':service['metadata']['uid']}
def api(m,volume,action=None):
 need(action in (None,'snapshotList','snapshotPurge'),'finite_native_actions')
 url='http://'+m['ip']+':9500/v1/volumes/'+volume
 args=['-n','longhorn-system','exec',m['name'],'-c','longhorn-manager','--','curl','--noproxy','*','--fail','--silent','--show-error','--max-time','12']
 if action:args+=['-X','POST','-H','Content-Type: application/json','--data','{}'];url+='?action='+action
 return kube(args+[url])
def disks():
 code="import os,json,subprocess;s=os.statvfs('/');print(json.dumps({'capacity':s.f_blocks*s.f_frsize,'free':s.f_bfree*s.f_frsize,'usable':s.f_bavail*s.f_frsize,'uuid':subprocess.check_output(['findmnt','-n','-o','UUID','/'],text=True).strip()}))"
 out={n:call(n,['python3','-B','-c',code])for n in ('workernode1','workernode2')}
 for n,d in out.items():d['hardFloor']=d['capacity']//4+1+512*1024**2;d['finalTarget']=d['hardFloor']+2*1024**3
 return out

def completed_backup_history(engine,history):
 need(not engine,'no_busy_engine_backup')
 need(isinstance(history,list),'native_backup_history_list')
 for row in history:
  need(isinstance(row,dict) and row.get('state')=='Completed' and type(row.get('progress')) is int and row['progress']==100 and row.get('error')=='','no_busy_or_failed_backup_history')

def closed_backup_format(a):
 path=a.after_closed_backup_status_format_failure;pin=a.after_closed_backup_status_format_failure_sha256
 need(bool(path)==bool(pin),'paired_format_closure_arguments')
 if not path:return None
 expected=R/'sonarr/qualification-failure.json'
 need(path==expected and path.resolve()==path and pin=='55b83450fb8199eedd477a0a702ed6e7888621fff5ab47994033ecc261a479b0' and sha(path)==pin,'exact_original_format_failure')
 failure=json.loads(path.read_text());need(failure=={'error':'no_busy_backup','runtimeMutationsPerformed':False,'retryProhibited':True},'closed_readonly_format_failure')
 old=R/'sonarr/backup-status0.py';diag=R/'sonarr/backup-status-observation.json'
 need(sha(old)=='f544a511461dff41e1bd83347aba9709c109d1bd790ec81f420a5bf715957c3e' and sha(diag)=='2e2641067bbc897cd5db0adc583fc06c6c490c98ef188946727dd48b1b07bc18','preserved_source_and_diagnostic')
 need(not any((R/'sonarr'/n).exists()for n in ('qualification.json','intent.json','result.json','apply-admission-failure.json')),'no_original_submitted_action')
 if a.candidate!='sonarr':need(not any((R/a.candidate/n).exists()for n in ('qualification.json','intent.json','result.json','qualification-failure.json','apply-admission-failure.json','ownership.json')),'no_other_candidate_original_attempt')
 observation=json.loads(diag.read_text());need(observation['readOnly'] is True,'diagnostic_readonly');completed_backup_history(observation['engineBackupStatus'],observation['nativeAPIBackupStatus'])
 return {'scope':'completed-backup-history-format-only','failure':{'path':str(path),'sha256':pin},'source':{'path':str(old),'sha256':sha(old)},'diagnostic':{'path':str(diag),'sha256':sha(diag)},'candidate':a.candidate,'originalFailurePreserved':True,'nativeGuardDenialBypassed':False,'freshCompleteQualificationRequired':True}

def observe(name,discovery,baseline=None,post=False):
 volume,target=CATALOG[name];m=manager();api_volume=api(m,volume);data=api(m,volume,'snapshotList')['data'];g={s['name']:{k:s[k]for k in ('name','created','usercreated','removed','children','parent','size','labels')}for s in data}
 need(len(g)==len(data) and 'volume-head'in g,'native_graph_unique')
 v=kube(['-n','longhorn-system','get','volumes.longhorn.io',volume,'-o','json'])
 engines=[e for e in items('engines.longhorn.io')if e['spec']['volumeName']==volume];need(len(engines)==1,'single_engine');e=engines[0];st=e['status']
 need(v['metadata']['uid']==discovery['volumeUID'] and e['metadata']['uid']==discovery['engineUID'],'exact_volume_engine_UID')
 need(v['spec']==discovery['volumeSpec'] and e['spec']==discovery['engineSpec'],'unchanged_volume_engine_spec')
 need(not v['metadata'].get('deletionTimestamp') and not e['metadata'].get('deletionTimestamp'),'no_deleting_volume_engine')
 need(v['status']['robustness']=='healthy' and v['status']['state']=='attached' and v['spec']['numberOfReplicas']==2 and v['spec']['dataEngine']=='v1','healthy_two_v1')
 need(e['spec']['image']==st['currentImage']==IMAGE and st['currentState']=='running' and not st.get('snapshotsError'),'native_engine_image')
 need(not st.get('isExpanding') and not e['spec'].get('upgradedReplicaAddressMap') and not v['status'].get('restoreRequired') and not v['status'].get('restoreInitiated'),'no_expansion_upgrade_restore')
 for field,flag in (('restoreStatus','isRestoring'),('rebuildStatus','isRebuilding'),('cloneStatus','isCloning')):
  need(all(not x.get(flag) and not x.get('error')for x in (st.get(field)or{}).values()),'no_busy_'+field)
 if BACKUP_STATUS_FORMAT_REPAIR:completed_backup_history(st.get('backupStatus'),api_volume.get('backupStatus'))
 else:need(not st.get('backupStatus') and not api_volume.get('backupStatus'),'no_busy_backup')
 need(not v['status'].get('isStandby') and not v['spec'].get('migrationNodeID') and not v['status'].get('currentMigrationNodeID'),'no_standby_migration')
 purges=st.get('purgeStatus')or{};need(all(not x.get('error')for x in purges.values()),'native_purge_error')
 if not post:need(all(not x.get('isPurging')for x in purges.values()),'no_concurrent_purge')
 reps=[r for r in items('replicas.longhorn.io')if r['spec']['volumeName']==volume]
 need(len(reps)==2 and {r['spec']['nodeID']for r in reps}=={'workernode1','workernode2'},'exact_W1_W2')
 need(set(st['replicaModeMap'])=={r['metadata']['name']for r in reps} and set(st['replicaModeMap'].values())=={'RW'},'two_RW')
 for r in reps:need(r['spec']['active'] and r['status']['currentState']=='running' and r['spec'].get('healthyAt') and not r['spec'].get('failedAt') and not r['metadata'].get('deletionTimestamp') and not r['spec'].get('evictionRequested'),'healthy_original_replicas')
 need(st['currentReplicaAddressMap']==e['spec']['replicaAddressMap'],'stable_replica_addresses')
 need(api_volume['id']==volume and api_volume['state']=='attached' and api_volume['robustness']=='healthy','native_volume_agreement')
 native_system={n for n,s in g.items()if n!='volume-head' and not s['usercreated']}
 need(native_system in ({target},set()) if post else native_system=={target},'exact_one_system_candidate')
 need({n for n,s in g.items()if s['removed']}==native_system,'no_removed_user_snapshots')
 crs=[s for s in items('snapshots.longhorn.io')if s['spec']['volume']==volume]
 if target in g:
  c=[c for c in crs if c['metadata']['name']==target];need(len(c)==1,'candidate_CR')
  c=c[0];expected=next(c for c in discovery['removedSnapshotCRs']if c['metadata']['name']==target)
  need(c['metadata']['uid']==expected['metadata']['uid'] and c['spec']['createSnapshot'] is False and c['status']['markRemoved'] is True and c['status']['userCreated'] is False,'already_removed_system_CR')
  need(g[target]['removed'] and len(g[target]['children'])==1 and 'volume-head'not in g[target]['children'],'non_head_single_child')
  need(g[target]['created']==discovery['engineGraph'][target]['created'],'original_system_creation')
 user={s['metadata']['name']:{'uid':s['metadata']['uid'],'createdAt':s['metadata']['creationTimestamp'],'spec':s['spec'],'logicalCreated':s['status']['creationTime'],'userCreated':s['status']['userCreated'],'markRemoved':s['status']['markRemoved']}for s in crs if s['status'].get('userCreated')}
 need(set(user)=={n for n,s in g.items()if s['usercreated']} and all(not s['markRemoved']for s in user.values()),'complete_user_snapshot_CR_preservation')
 checkpoint=REPO/'k8s-rewrite/ansible-playbook/roles/security_maintenance/files/kernel_checkpoint.py';need(sha(checkpoint)=='b3c5140cb04adfa934f60206c2695bc2f6663148359ae55f0d8145247bcb1d65','backup_identity_source');cp=loadmodule('backup_identity_source',checkpoint)
 backups=items('backups.longhorn.io');need(not any(b.get('spec',{}).get('snapshotName')==target or b.get('status',{}).get('snapshotName')==target for b in backups),'no_backup_reference_to_candidate')
 identities={b['metadata']['name']:{'uid':b['metadata']['uid'],'spec':b['spec'],'durable_backup_identity':cp.backup_identity(b.get('status',{}))}for b in backups}
 replica_identity={r['metadata']['name']:{'uid':r['metadata']['uid'],'spec':r['spec']}for r in reps}
 result={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'manager':m,'volumeUID':v['metadata']['uid'],'engineUID':e['metadata']['uid'],'graph':g,'userSnapshots':user,'allBackupIdentities':identities,'allBackupIdentitySHA256':digest(identities),'replicas':replica_identity,'purgeStatus':purges,'candidateCRPresent':any(c['metadata']['name']==target for c in crs),'disks':disks()}
 if baseline:
  if not post:need({n:v for n,v in g.items()if n!='volume-head'}=={n:v for n,v in baseline['graph'].items()if n!='volume-head'},'unchanged_pre_submission_graph')
  for field in ('userSnapshots','allBackupIdentities','replicas','manager'):need(result[field]==baseline[field],'preservation_'+field)
  original={n:s for n,s in baseline['graph'].items()if n!='volume-head'};current={n:s for n,s in g.items()if n!='volume-head'}
  for n,s in current.items():
   need(n in original,'no_new_snapshot')
   for k in ('name','created','usercreated','removed','labels'):need(s[k]==original[n][k],'snapshot_logical_metadata')
  need(set(current)==set(original) or (post and set(current)==set(original)-{target}),'only_candidate_absence')
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--candidate',choices=CATALOG,default='sonarr');p.add_argument('--mode',choices=['qualify','apply','observe'],default='qualify');p.add_argument('--qualification-sha256');p.add_argument('--after-closed-backup-status-format-failure',type=Path);p.add_argument('--after-closed-backup-status-format-failure-sha256');a=p.parse_args()
 closure=closed_backup_format(a)
 global BACKUP_STATUS_FORMAT_REPAIR
 BACKUP_STATUS_FORMAT_REPAIR=closure is not None
 prefix='backup-status-repair-' if closure else ''
 dpath=H/'post-fresh-backup-system-snapshot-gc-readonly.json';need(sha(dpath)==DISCOVERY_SHA,'discovery_authority');discovery=next(x for x in json.loads(dpath.read_text())['candidates']if x['volume']==CATALOG[a.candidate][0])
 need(F.is_mount() and H.resolve()==H,'sole_F_root')
 physical_uuid=subprocess.check_output(['findmnt','-n','-o','UUID','--target',str(F)],text=True).strip()
 need(physical_uuid=='3c792469-ea0e-4a2c-98e8-1185b141607b','original_physical_F_volume')
 R.mkdir(mode=0o700,exist_ok=True);run=R/a.candidate;run.mkdir(mode=0o700,exist_ok=True);need(run.resolve()==run,'canonical_run')
 q=run/(prefix+'qualification.json');intent=run/(prefix+'intent.json');result=run/(prefix+'result.json');failure=run/(prefix+'qualification-failure.json')
 closure_path=run/(prefix+'closure.json')
 if closure and a.mode!='qualify':need(closure_path.is_file() and json.loads(closure_path.read_text())==closure,'immutable_format_closure')
 if a.mode=='qualify':
  need(not any(x.exists()for x in (q,intent,result,failure)),'prior_qualification_or_attempt_protected')
  if closure:write(closure_path,closure)
  write(run/(prefix+'ownership.json'),{'owner':'01a18518-24e7-7ce3-b620-f9ca775bfd1c','root':str(F),'leaf':str(run),'physicalUUID':physical_uuid,
   'physicalBacking':'F:/branconet-build-storage/native-build-20261025.ext4','sourceSHA256':sha(Path(__file__)),
   'formatClosure':closure,'generatedPaths':[prefix+n for n in ['qualification.json','qualification-failure.json','intent.json','result.json','apply-admission-failure.json','observation-*.json']],
   'controllerPeakEstimatedBytes':64*1024**2,'lastConsumer':'One explicitly qualified native GC action and independent final preservation observation',
   'regeneration':'Re-read the exact native API and pinned upstream sources; never replay a submitted or failed operation',
   'protected':'All user-created snapshots, original NAS backups and data, original source and all earlier failure/intent receipts; only already-removed system garbage is eligible'})
  try:
   upstream=sources();before=core();ob=observe(a.candidate,discovery);peak=int(ob['graph'][CATALOG[a.candidate][1]]['size'])+128*1024**2
   for disk in ob['disks'].values():need(disk['free']-peak>=disk['hardFloor'] and disk['usable']-peak>=15*1024**3,'native_coalesce_complete_peak')
   write(q,{'owner':'longhorn_snapshot_gc','formatClosure':closure,'sourceSHA256':sha(Path(__file__)),'discoverySHA256':DISCOVERY_SHA,'upstream':upstream,'candidate':a.candidate,'core':before,'observation':ob,'additionalPeakEachReplicaBytes':peak,'runtimeMutationsPerformed':False});print(json.dumps({'qualification':str(q),'sha256':sha(q),'peak':peak}))
  except Exception as err:write(failure,{'error':str(err),'runtimeMutationsPerformed':False,'retryProhibited':True});raise
  return
 need(q.is_file() and sha(q)==a.qualification_sha256,'explicit_qualification_hash');qualified=json.loads(q.read_text());need(qualified['sourceSHA256']==sha(Path(__file__)) and qualified['candidate']==a.candidate and qualified.get('formatClosure')==closure,'frozen_qualified_source');baseline=qualified['observation']
 if a.mode=='observe':
  ob=observe(a.candidate,discovery,baseline,post=True);out=run/(prefix+'observation-'+uuid.uuid4().hex+'.json');write(out,ob);print(json.dumps({'path':str(out),'sha256':sha(out)}));return
 admission=run/(prefix+'apply-admission-failure.json')
 need(not any(x.exists()for x in (intent,result,failure,admission)),'no_uncertain_submission_replay')
 try:
  before=core();ob=observe(a.candidate,discovery,baseline);peak=int(ob['graph'][CATALOG[a.candidate][1]]['size'])+128*1024**2
  need(peak==qualified['additionalPeakEachReplicaBytes'],'same_physical_parent_bound')
  for n,disk in ob['disks'].items():need(disk['uuid']==baseline['disks'][n]['uuid'] and disk['capacity']==baseline['disks'][n]['capacity'] and disk['free']-peak>=disk['hardFloor'] and disk['usable']-peak>=15*1024**3,'fresh_native_budget')
 except Exception as err:write(admission,{'error':str(err),'runtimeMutationsPerformed':False,'retryProhibited':True});raise
 write(intent,{'candidate':a.candidate,'qualificationSHA256':sha(q),'sourceSHA256':sha(Path(__file__)),'before':ob,'core':before,'action':'snapshotPurge','singleSubmission':True})
 outcome={'status':'submitted-or-uncertain','intentSHA256':sha(intent),'candidate':a.candidate,'polls':[]}
 try:
  # Exactly one mutating call. Never retry a transport error or timeout.
  response=api(ob['manager'],CATALOG[a.candidate][0],'snapshotPurge');outcome['nativeResponseSHA256']=digest(response)
  deadline=time.monotonic()+180
  while time.monotonic()<deadline:
   latest=observe(a.candidate,discovery,baseline,post=True);outcome['polls'].append({'UTC':latest['UTC'],'purgeStatus':latest['purgeStatus'],'candidatePresent':CATALOG[a.candidate][1]in latest['graph']})
   if CATALOG[a.candidate][1]not in latest['graph'] and all(not s.get('isPurging') and s.get('state')=='complete'for s in latest['purgeStatus'].values()):break
   time.sleep(min(5,max(0,deadline-time.monotonic())))
  else:raise ValueError('bounded_native_purge_timeout_no_retry')
  outcome.update(status='completed',after=latest,coreAfter=core(),measuredRootFreeDelta={n:latest['disks'][n]['free']-ob['disks'][n]['free']for n in latest['disks']},finalMarginSatisfied={n:latest['disks'][n]['free']>=latest['disks'][n]['finalTarget'] and latest['disks'][n]['usable']>=15*1024**3 for n in latest['disks']})
 except Exception as err:outcome.update(status='failed-or-uncertain',error=str(err),retryProhibited=True);raise
 finally:write(result,outcome);print(json.dumps({'result':str(result),'sha256':sha(result),'status':outcome['status']}))
if __name__=='__main__':main()
