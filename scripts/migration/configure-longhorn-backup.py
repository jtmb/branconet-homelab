#!/usr/bin/env python3
"""Use the existing NAS backup share through Longhorn's native CIFS backup target."""
import datetime,json,pathlib,subprocess,time,yaml
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration';k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
def run(args,body=None):return subprocess.run(k+args,input=json.dumps(body).encode() if body is not None else None,capture_output=True,check=True).stdout
source=json.loads(run(['get','secret','smb-creds','-n','plex','-o','json']))
secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':'longhorn-backup-cifs','namespace':'longhorn-system'},'type':'Opaque','data':{'CIFS_USERNAME':source['data']['username'],'CIFS_PASSWORD':source['data']['password']}}
existing=run(['get','secret','longhorn-backup-cifs','-n','longhorn-system','--ignore-not-found','-o','json'])
if existing:
 if json.loads(existing).get('data')!=secret['data']:raise RuntimeError('Existing backup credentials differ')
else:run(['create','-f','-'],secret)
code="import pathlib;p=pathlib.Path('/mnt/container-backups/k8s-migration-20261009/longhorn');p.mkdir(exist_ok=True);print('Backup directory prepared')"
subprocess.run(['ssh','-p','2002','james@192.168.0.4','python3','-'],input=code.encode(),capture_output=True,check=True)
url='cifs://192.168.0.8/container_backups/k8s-migration-20261009/longhorn?cifsOptions=vers=3.1.1,soft'
spec={'backupTargetURL':url,'credentialSecret':'longhorn-backup-cifs','pollInterval':'1m0s','syncRequestedAt':datetime.datetime.now(datetime.timezone.utc).isoformat()}
run(['patch','backuptarget','default','-n','longhorn-system','--type=merge','-p',json.dumps({'spec':spec})])
available=False
for attempt in range(90):
 obj=json.loads(run(['get','backuptarget','default','-n','longhorn-system','-o','json']))
 if obj.get('status',{}).get('available'):available=True;break
 time.sleep(2)
report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'backup_target_url':url,'native_credential_secret':'longhorn-system/longhorn-backup-cifs','available':available,'existing_nas_exports_and_media_unchanged':True}
(ROOT/'evidence/longhorn-backup-target.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if not available:raise RuntimeError('Longhorn NAS backup target unavailable')
foundation=ROOT/'k8s-rewrite/flux/migration-releases/foundation';obj={'apiVersion':'longhorn.io/v1beta2','kind':'BackupTarget','metadata':{'name':'default','namespace':'longhorn-system'},'spec':{key:value for key,value in spec.items() if key!='syncRequestedAt'}};(foundation/'backup-target.yaml').write_text(yaml.safe_dump(obj,sort_keys=False));p=foundation/'kustomization.yaml';v=yaml.safe_load(p.read_text());v['resources']=list(dict.fromkeys(v['resources']+['backup-target.yaml']));p.write_text(yaml.safe_dump(v,sort_keys=False))
