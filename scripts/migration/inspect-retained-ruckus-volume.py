#!/usr/bin/env python3
"""One retained Ruckus claim: read-only inventory and two-replica health only."""
import argparse,datetime,hashlib,importlib.util,json,os,pathlib,re,shlex,subprocess,time,uuid
REPO=pathlib.Path(__file__).resolve().parents[2]
BASE=pathlib.Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
SHARED=REPO/'k8s-rewrite/ansible-playbook/roles/metube_state_backup/files'
CLAIM='ruckus-db-data-0';UID='2f604004-b45f-4061-bdc4-43f5ca2f7fd8';VOL='pvc-'+UID
LABEL='branconet.net/ruckus-original-ro'
REPLICAS={'pvc-'+UID+'-r-58fd1121':'91008363-9d86-490d-88c9-ef64b5265680','pvc-'+UID+'-r-dcdb6543':'1e878b44-87c5-405a-9246-2c2a277018f1'}
OLD_RECEIPT=BASE/'ruckus-cold-20261025/ruckus-db-cold-15c183ff106b46048a1f77c17ae0e266/receipt.json'
def need(x,code):
 if not x:raise ValueError(code)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args();os.umask(0o077)
 need(a.apply and os.getuid()==1000 and BASE.is_mount(),'explicit_private_controller')
 spec=importlib.util.spec_from_file_location('shared',SHARED/'metube_state_backup.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
 need(sha(s.AGE)==s.AGE_SHA256,'pinned_age')
 old=json.loads(OLD_RECEIPT.read_bytes());need(old['status']=='completed' and old['cold_archive_verified'] and old['claim_uid']==UID,'original_cold_receipt')
 cipher=pathlib.Path(old['archive_path']);need(sha(cipher)==old['archive_sha256']=='d9055b97e35af0afc9b2d6a9379697dd8b889e1633c27d5822e840e726cf86e0','original_cipher')
 runid=uuid.uuid4().hex[:12];run=BASE/'ruckus-original-ro-inspection-20261025'/runid;run.mkdir(mode=0o700,parents=True)
 for name in ['tmp','home','cache']:(run/name).mkdir(mode=0o700)
 os.environ.update(TMPDIR=str(run/'tmp'),TEMP=str(run/'tmp'),TMP=str(run/'tmp'),XDG_CACHE_HOME=str(run/'cache'),PYTHONDONTWRITEBYTECODE='1')
 def remote(argv,body=None,timeout=60):
  r=subprocess.run(s.SSH+[shlex.join(argv)],input=body,capture_output=True,timeout=timeout)
  need(r.returncode==0 and len(r.stdout)<=8*1024**2,'bounded_remote_command');return r.stdout
 def kub(*argv,ns='ruckus',body=None,timeout=60):return remote(['kubectl','--request-timeout=30s','-n',ns,*argv],body,timeout)
 def get(kind,name=None,ns='ruckus'):return json.loads(kub('get',kind,*([name] if name else []),'-o','json',ns=ns))
 def source_guard(own_uid=None,require_running=False):
  c=get('pvc',CLAIM);need(c['metadata']['uid']==UID and c['status']['phase']=='Bound' and not c['metadata'].get('deletionTimestamp'),'source_claim')
  v=get('volumes.longhorn.io',VOL,'longhorn-system');need(v['spec']['numberOfReplicas']==2 and v['spec'].get('dataEngine','v1')=='v1','two_V1_replicas')
  rs=[r for r in get('replicas.longhorn.io',ns='longhorn-system')['items'] if r['spec']['volumeName']==VOL]
  need({r['metadata']['name']:r['metadata']['uid'] for r in rs}==REPLICAS,'exact_original_replica_UIDs')
  for r in rs:need(not r['spec'].get('failedAt') and r['spec'].get('active') is True and r['spec'].get('healthyAt'),'nonfailed_source_replicas')
  for pod in get('pods')['items']:
   if any(x.get('persistentVolumeClaim',{}).get('claimName')==CLAIM for x in pod['spec'].get('volumes',[])):
    active=pod['status'].get('phase') not in ['Failed','Succeeded']
    need(not active or pod['metadata']['uid']==own_uid,'no_other_original_mounter')
  if require_running:
   need(v['status']['state']=='attached' and v['status']['robustness']=='healthy','attached_original_volume_healthy')
   es=[e for e in get('engines.longhorn.io',ns='longhorn-system')['items'] if e['spec']['volumeName']==VOL]
   need(len(es)==1 and es[0]['status']['currentState']=='running','original_engine_running')
   modes=es[0]['status'].get('replicaModeMap',{});need(len(modes)==2 and set(modes.values())=={'RW'},'both_existing_replicas_RW')
  return {'pvcUID':UID,'volumeUID':v['metadata']['uid'],'volumeState':v['status']['state'],'volumeRobustness':v['status']['robustness'],'replicaUIDs':REPLICAS}
 objects=None;owned={};result={'status':'started','readOnly':True,'sourceDataWritePerformed':False,'fsGroupSupplied':False,'runID':runid,'originalArchiveRetained':True}
 def save():
  p=run/'receipt.json';t=run/'receipt.tmp';t.write_text(json.dumps(result,indent=2)+'\n');os.replace(t,p)
 def delete_owned(kind,name,uid):
  x=get(kind,name);need(x['metadata']['uid']==uid,'cleanup_UID')
  url='/api/v1/namespaces/ruckus/pods/'+name if kind=='pod' else '/apis/networking.k8s.io/v1/namespaces/ruckus/networkpolicies/'+name
  body={'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':uid,'resourceVersion':x['metadata']['resourceVersion']},'propagationPolicy':'Foreground'}
  kub('delete','--raw',url,'-f','-',body=json.dumps(body).encode())
 try:
  result['before']=source_guard();save()
  dec=subprocess.Popen([str(s.AGE),'-d','-i',str(s.IDENTITY),str(cipher)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
  try:expected=s.verify_archive(dec.stdout);tail=dec.stdout.read(1024**2+1);need(len(tail)<=1024**2 and not any(tail) and dec.wait(timeout=30)==0,'full_original_age_authentication')
  finally:
   if dec.poll() is None:dec.kill();dec.wait()
  need(hashlib.sha256(s.canonical(expected)).hexdigest()==old['manifest_sha256'],'original_manifest_binding')
  name='ruckus-original-ro-'+runid;labels={LABEL:runid}
  policy={'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':{'name':name,'namespace':'ruckus','labels':labels},'spec':{'podSelector':{'matchLabels':labels},'policyTypes':['Ingress','Egress'],'ingress':[],'egress':[]}}
  pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'ruckus','labels':labels},'spec':{'nodeSelector':{'kubernetes.io/hostname':'workernode2'},'restartPolicy':'Never','activeDeadlineSeconds':900,'automountServiceAccountToken':False,'enableServiceLinks':False,'hostNetwork':False,'hostPID':False,'hostIPC':False,'securityContext':{'supplementalGroupsPolicy':'Strict','seccompProfile':{'type':'RuntimeDefault'}},'containers':[{'name':'reader','image':s.OLD,'imagePullPolicy':'Never','command':['python3','-B','-c','import time;time.sleep(900)'],'securityContext':{'runAsUser':0,'runAsGroup':0,'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL'],'add':['DAC_OVERRIDE']}},'resources':{'requests':{'cpu':'25m','memory':'32Mi'},'limits':{'cpu':'500m','memory':'512Mi'}},'volumeMounts':[{'name':'original','mountPath':'/source','readOnly':True}]}],'volumes':[{'name':'original','persistentVolumeClaim':{'claimName':CLAIM,'readOnly':True}}]}}
  objects={'apiVersion':'v1','kind':'List','items':[policy,pod]};(run/'plan.json').write_text(json.dumps(objects,indent=2)+'\n')
  for kind,obj in [('networkpolicy',policy),('pod',pod)]:
   created=json.loads(kub('create','-f','-','-o','json',body=json.dumps(obj).encode()));owned[kind]=created['metadata']['uid'];result['ownedResources']=dict(owned);save()
  for _ in range(90):
   got=get('pod',name);need(got['metadata']['uid']==owned['pod'],'reader_UID')
   if got['status'].get('phase')=='Running' and all(x.get('ready') for x in got['status'].get('containerStatuses',[])):break
   need(got['status'].get('phase') not in ['Failed','Succeeded'],'reader_phase');time.sleep(2)
  else:raise ValueError('reader_ready_deadline')
  source_guard(owned['pod'],True)
  need(not got['spec']['securityContext'].get('fsGroup') and got['spec']['volumes'][0]['persistentVolumeClaim']['readOnly'] is True and got['spec']['containers'][0]['volumeMounts'][0]['readOnly'] is True,'no_original_write_mount_or_recursive_group_change')
  need(got['status']['containerStatuses'][0]['imageID']==s.OLD,'pinned_reader_runtime')
  program="__name__='inspection'\n"+(SHARED/'pod_reader.py').read_text()+"\nROOTS={'data-0':'/source'}\nEXCLUDED=set()\nMAX_BYTES=384*1024**2\nm=inventory(False)\nv=os.statvfs('/source')\nprint(json.dumps({'manifest':m,'freeBytes':v.f_bavail*v.f_frsize,'rootChildren':sorted(p.name for p in pathlib.Path('/source').iterdir())},sort_keys=True))\n"
  actual=json.loads(kub('exec',name,'-c','reader','--','python3','-B','-c',program,timeout=180))
  (run/'original-readonly-inventory.json').write_text(json.dumps(actual,indent=2)+'\n')
  view=lambda m:{**m,'entries':{n:{k:v for k,v in row.items() if k!='fingerprint'} for n,row in m['entries'].items()}}
  need(view(actual['manifest'])==view(expected),'every_original_byte_and_metadata_unchanged')
  result.update(status='completed',originalManifestSHA256=old['manifest_sha256'],originalFileBytes=actual['manifest']['total_file_bytes'],guestFreeBytes=actual['freeBytes'],rootChildren=actual['rootChildren'],bothExistingReplicasRW=True,allOriginalBytesAndMetadataEqual=True,after=source_guard(owned['pod'],True));save()
 except Exception as e:
  result.update(status='failed',errorType=type(e).__name__,code=str(e) if isinstance(e,ValueError) and re.fullmatch('[A-Za-z0-9_]+',str(e)) else 'details-withheld');save()
 finally:
  if objects:
   for kind in ['pod','networkpolicy']:
    if kind in owned:
     try:delete_owned(kind,objects['items'][1]['metadata']['name'],owned[kind]);result[kind+'Deleted']=True
     except Exception:result[kind+'CleanupRefused']=True
  save()
 print(json.dumps({'status':result['status'],'receipt':str(run/'receipt.json'),'code':result.get('code'),'guestFreeBytes':result.get('guestFreeBytes'),'bothExistingReplicasRW':result.get('bothExistingReplicasRW')}))
 return 0 if result['status']=='completed' and result.get('podDeleted') and result.get('networkpolicyDeleted') else 1
if __name__=='__main__':raise SystemExit(main())
