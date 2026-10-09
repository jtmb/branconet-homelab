#!/usr/bin/env python3
"""Cold snapshot active native state, resume workloads, then send backups to NAS."""
import concurrent.futures,datetime,hashlib,json,pathlib,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration';k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
def run(args,body=None):return subprocess.run(k+args,input=json.dumps(body).encode() if body is not None else None,capture_output=True,check=True,timeout=400).stdout
def get(kind,name=None,ns=None):return json.loads(run(['get',kind]+([name] if name else [])+(['-n',ns] if ns else ['-A'])+['-o','json']))
def apply(obj):run(['create','-f','-'],obj)
def patch(kind,name,ns,obj):run(['patch',kind,name,'-n',ns,'--type=merge','-p',json.dumps(obj)])
target=get('backuptarget','default','longhorn-system')
if not target.get('status',{}).get('available'):raise RuntimeError('Available off-cluster target required')
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S');path=ROOT/'evidence/native-volume-backups.json'
if path.exists():raise RuntimeError('Inspect existing backup run before repeating')
claims={(p['metadata']['namespace'],p['metadata']['name']):p for p in get('pvc')['items'] if p['spec'].get('storageClassName')=='longhorn'};deployments=[];volumes={};holders=[]
for deployment in get('deploy')['items']:
 ns=deployment['metadata']['namespace'];name=deployment['metadata']['name'];count=deployment['spec'].get('replicas',0)
 mounted=[(ns,v['persistentVolumeClaim']['claimName']) for v in deployment['spec']['template']['spec'].get('volumes',[]) if 'persistentVolumeClaim' in v and (ns,v['persistentVolumeClaim']['claimName']) in claims]
 if not count or not mounted:continue
 pods=get('pods',ns=ns)['items'];pods=[p for p in pods if p['metadata'].get('labels',{}).get('app')==name and not p['metadata'].get('deletionTimestamp')]
 if len(pods)!=1:raise RuntimeError('Exactly one active writer required for '+name)
 deployments.append({'namespace':ns,'name':name,'replicas':count});holder='backup-holder-'+name+'-'+stamp[-6:];holders.append({'namespace':ns,'name':holder})
 mounts=[];podvols=[]
 for index,key in enumerate(mounted):
  p=claims[key];volume=p['spec']['volumeName'];namevol='data-'+str(index);mounts.append({'name':namevol,'mountPath':'/claims/'+key[1],'readOnly':True});podvols.append({'name':namevol,'persistentVolumeClaim':{'claimName':key[1],'readOnly':True}})
  volumes[volume]={'namespace':ns,'claim':key[1],'volume':volume,'holder':holder,'snapshot':'migration-cold-'+stamp+'-'+hashlib.sha256(volume.encode()).hexdigest()[:12],'backup':'backup-'+hashlib.sha256((stamp+volume).encode()).hexdigest()[:16]}
 apply({'apiVersion':'v1','kind':'Pod','metadata':{'name':holder,'namespace':ns,'labels':{'migration-backup-holder':stamp}},'spec':{'nodeName':pods[0]['spec']['nodeName'],'automountServiceAccountToken':False,'restartPolicy':'Never','containers':[{'name':'holder','image':'python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1','command':['python3','-c','import time;time.sleep(3600)'],'volumeMounts':mounts,'resources':{'requests':{'cpu':'5m','memory':'16Mi'},'limits':{'memory':'128Mi'}}}],'volumes':podvols}})
for holder in holders:run(['wait','pod/'+holder['name'],'-n',holder['namespace'],'--for=condition=Ready','--timeout=180s'])
hr=get('helmrelease',ns='flux-system')['items'];previous={obj['metadata']['name']:obj['spec'].get('suspend',False) for obj in hr};kust=get('kustomization','migration-releases','flux-system')['spec'].get('suspend',False)
report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stamp':stamp,'volumes':list(volumes.values()),'holders':holders,'source_data_retained':True,'workloads_resumed':False,'snapshots_consistent':False,'nas_backups_complete':False}
def save():path.write_text(json.dumps(report,indent=2)+'\n')
save();stopped=False
try:
 patch('kustomization','migration-releases','flux-system',{'spec':{'suspend':True}})
 for name in previous:patch('helmrelease',name,'flux-system',{'spec':{'suspend':True}})
 stopped=True
 def stop(d):
  run(['scale','deployment/'+d['name'],'-n',d['namespace'],'--replicas=0']);run(['wait','pod','-n',d['namespace'],'-l','app='+d['name'],'--for=delete','--timeout=180s'])
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(stop,deployments))
 # Holders keep each read-only volume attached after all actual writers exit.
 for obj in volumes.values():apply({'apiVersion':'longhorn.io/v1beta2','kind':'Snapshot','metadata':{'name':obj['snapshot'],'namespace':'longhorn-system','labels':{'migration-checkpoint':stamp}},'spec':{'volume':obj['volume'],'createSnapshot':True,'labels':{'migration-consistency':'cold-writers-stopped'}}})
 for attempt in range(90):
  snapshots=get('snapshots.longhorn.io',ns='longhorn-system')['items'];ready={o['metadata']['name'] for o in snapshots if o.get('status',{}).get('readyToUse')}
  if all(o['snapshot'] in ready for o in volumes.values()):break
  time.sleep(2)
 else:raise RuntimeError('Cold snapshots did not become ready')
 report['snapshots_consistent']=True
 # Capture BORTUS metadata only while the database is quiescent.
 bortus=next(o for o in volumes.values() if o['namespace']=='bortus');code="import sqlite3,json,hashlib,pathlib;p=pathlib.Path('/claims/"+bortus['claim']+"/bortus.db');db=sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True);tables=[r[0] for r in db.execute(\"select name from sqlite_master where type='table' and name not like 'sqlite_%'\")];print(json.dumps({'database_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'integrity':db.execute('PRAGMA integrity_check').fetchone()[0],'table_counts':{name:db.execute('select count(*) from '+chr(34)+name+chr(34)).fetchone()[0] for name in tables}}))"
 result=run(['exec','-n','bortus',bortus['holder'],'--','python3','-c',code]);report['bortus_cold_database']=json.loads(result);save()
finally:
 if stopped:
  for d in deployments:run(['scale','deployment/'+d['name'],'-n',d['namespace'],'--replicas='+str(d['replicas'])])
  report['workloads_resumed']=True
 for name,suspended in previous.items():patch('helmrelease',name,'flux-system',{'spec':{'suspend':suspended}})
 patch('kustomization','migration-releases','flux-system',{'spec':{'suspend':kust}});save()
if not report['snapshots_consistent']:raise RuntimeError('No accepted cold checkpoint')
for obj in volumes.values():
 apply({'apiVersion':'longhorn.io/v1beta2','kind':'Backup','metadata':{'name':obj['backup'],'namespace':'longhorn-system','labels':{'backup-volume':obj['volume'],'backup-target':'default','migration-checkpoint':stamp}},'spec':{'snapshotName':obj['snapshot'],'backupMode':'full','labels':{'migration-consistency':'cold-writers-stopped'}}})
print(json.dumps({'cold_snapshots':len(volumes),'writers_resumed':True,'native_nas_backups_started':True}),flush=True)
for attempt in range(900):
 backups=get('backups.longhorn.io',ns='longhorn-system')['items'];byname={o['metadata']['name']:o for o in backups}
 complete=0
 for obj in report['volumes']:
  status=byname.get(obj['backup'],{}).get('status',{});obj['backup_state']=status.get('state');obj['progress']=status.get('progress');obj['url']=status.get('url');obj['error_present']=bool(status.get('error'))
  if status.get('state')=='Completed':complete+=1
 if attempt%10==0:save();print(json.dumps({'complete_backups':complete,'total':len(volumes)}),flush=True)
 if complete==len(volumes):report['nas_backups_complete']=True;break
 if any(o['error_present'] for o in report['volumes']):save();raise RuntimeError('Native backup error; inspect retained controller state')
 time.sleep(2)
report['completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
if not report['nas_backups_complete']:raise RuntimeError('Native backups not complete')
print(json.dumps({'complete_backups':len(volumes),'nas_backups_complete':True,'restore_proof_pending':True}))
