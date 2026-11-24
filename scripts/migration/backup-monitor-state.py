#!/usr/bin/env python3
"""Cold NAS checkpoint for the newly introduced repository-only monitor claim."""
import datetime,json,pathlib,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration';k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
path=ROOT/'evidence/monitor-state-backup.json'
if path.exists():raise RuntimeError('Inspect retained monitor checkpoint before repetition')
def run(args,body=None):return subprocess.check_output(k+args,input=json.dumps(body).encode() if body is not None else None)
def get(kind,name,ns):return json.loads(run(['get',kind,name,'-n',ns,'-o','json']))
def patch(kind,name,ns,body):run(['patch',kind,name,'-n',ns,'--type=merge','-p',json.dumps(body)])
claim=get('pvc','qbit-monitor-state','plex');volume=claim['spec']['volumeName'];pods=json.loads(run(['get','pods','-n','plex','-l','app=qbit-monitor','-o','json']))['items'];writer=next(p for p in pods if not p['metadata'].get('deletionTimestamp'))
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S');holder='monitor-checkpoint-'+stamp;labels={'migration-monitor-checkpoint':stamp}
pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':holder,'namespace':'plex','labels':labels},'spec':{'nodeName':writer['spec']['nodeName'],'automountServiceAccountToken':False,'restartPolicy':'Never','containers':[{'name':'holder','image':'busybox@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662','command':['sh','-c','sleep 600'],'volumeMounts':[{'name':'state','mountPath':'/state','readOnly':True}],'resources':{'requests':{'cpu':'5m','memory':'16Mi'},'limits':{'memory':'64Mi'}}}],'volumes':[{'name':'state','persistentVolumeClaim':{'claimName':'qbit-monitor-state','readOnly':True}}]}}
run(['create','-f','-'],pod);run(['wait','pod/'+holder,'-n','plex','--for=condition=Ready','--timeout=90s']);kust=get('kustomization','migration-releases','flux-system')['spec'].get('suspend',False);hr=get('helmrelease','qbit-monitor','flux-system')['spec'].get('suspend',False)
snapshot='monitor-cold-'+stamp;backup='backup-monitor-'+stamp;report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'namespace':'plex','claim':'qbit-monitor-state','volume':volume,'snapshot':snapshot,'backup':backup,'source_data_retained':True,'cold_snapshot_ready':False}
try:
 patch('kustomization','migration-releases','flux-system',{'spec':{'suspend':True}});patch('helmrelease','qbit-monitor','flux-system',{'spec':{'suspend':True}})
 run(['scale','deployment/qbit-monitor','-n','plex','--replicas=0']);run(['wait','pod','-n','plex','-l','app=qbit-monitor','--for=delete','--timeout=90s'])
 run(['create','-f','-'],{'apiVersion':'longhorn.io/v1beta2','kind':'Snapshot','metadata':{'name':snapshot,'namespace':'longhorn-system'},'spec':{'volume':volume,'createSnapshot':True,'labels':{'migration-consistency':'cold-writer-stopped'}}})
 for _ in range(60):
  if get('snapshot',snapshot,'longhorn-system').get('status',{}).get('readyToUse'):report['cold_snapshot_ready']=True;break
  time.sleep(1)
 if not report['cold_snapshot_ready']:raise RuntimeError('Monitor cold snapshot not ready')
finally:
 run(['scale','deployment/qbit-monitor','-n','plex','--replicas=1']);patch('helmrelease','qbit-monitor','flux-system',{'spec':{'suspend':hr}});patch('kustomization','migration-releases','flux-system',{'spec':{'suspend':kust}});path.write_text(json.dumps(report,indent=2)+'\n')
run(['create','-f','-'],{'apiVersion':'longhorn.io/v1beta2','kind':'Backup','metadata':{'name':backup,'namespace':'longhorn-system','labels':{'backup-volume':volume,'backup-target':'default'}},'spec':{'snapshotName':snapshot,'backupMode':'full','labels':{'migration-consistency':'cold-writer-stopped'}}})
for _ in range(120):
 status=get('backup',backup,'longhorn-system').get('status',{})
 if status.get('error'):raise RuntimeError('Monitor NAS backup failed; retained holder requires inspection')
 if status.get('state')=='Completed':report.update({'nas_backup_completed':True,'backup_url':status['url']});break
 time.sleep(2)
if not report.get('nas_backup_completed'):raise RuntimeError('Monitor NAS backup timed out')
run(['delete','pod',holder,'-n','plex','--wait=true','--timeout=90s']);run(['rollout','status','deployment/qbit-monitor','-n','plex','--timeout=120s']);report['completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();report['holder_removed']=True;path.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
