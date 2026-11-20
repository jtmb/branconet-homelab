"""Retire only the verified readonly recovery derivative before corrected-version rehearsal."""
import argparse,hashlib,json,os,subprocess,time
from pathlib import Path
A=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery')
R=A/'independent-restore-da37c4f713e8';K=['/home/brajam/.local/share/branconet-migration/bin/kubectl','--kubeconfig','/home/brajam/.local/share/branconet-migration/admin.conf','--request-timeout=15s']
def need(v):
 if not v:raise RuntimeError('owned_restore_derivative_retirement_failed')
def call(args,body=None):
 r=subprocess.run(K+args,input=body,capture_output=True,timeout=20);need(r.returncode==0);return json.loads(r.stdout)
def get(resource,name,ns=None):return call(['get',resource,name]+(['-n',ns] if ns else [])+['-o','json'])
def main():
 global R
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--after-tool-path',action='store_true');args=parser.parse_args()
 if args.after_tool_path:R=R.with_name(R.name+'-lh113')
 receipt=json.loads((R/'restore-receipt.json').read_bytes());raw=(R/'journal.json').read_bytes();j=json.loads(raw)
 need(receipt['failure']==('data' if args.after_tool_path else 'health') and receipt['completion_observed'] is True and receipt['whole_rows_equal'] is False and receipt['resources_closed'] is True)
 checkpoint=A/'recovery/bortus-checkpoints/da37c4f713e8/journal.json';craw=checkpoint.read_bytes();need(hashlib.sha256(craw).hexdigest()==receipt['checkpoint_journal_sha256']);c=json.loads(craw)
 archive=Path(c['sqlite_archive']['artifact']);need(hashlib.sha256(archive.read_bytes()).hexdigest()==c['sqlite_archive']['ciphertext_sha256'])
 name=j['target_name'];pod=get('pod',name,'bortus');claim=get('pvc',name,'bortus');pv=get('pv',claim['spec']['volumeName']);vol=get('volumes.longhorn.io',pv['spec']['csi']['volumeHandle'],'longhorn-system');sc=get('storageclass',name)
 for key,obj in [('holder_create',pod),('claim_create',claim),('storageclass_create',sc)]:
  need(j['operations'][key]['state']=='confirmed' and obj['metadata']['uid']==j['operations'][key]['identity']['uid'])
 need(pod['spec']['volumes']==[{'name':'data','persistentVolumeClaim':{'claimName':name,'readOnly':True}}]
      and pod['spec']['containers'][0]['volumeMounts']==[{'mountPath':'/data','name':'data','readOnly':True}]
      and pod['spec']['containers'][0]['command']==['node','-e','setInterval(()=>{},1000)'] and not pod['metadata'].get('ownerReferences'))
 need(pv['spec']['claimRef']['uid']==claim['metadata']['uid'] and pv['spec']['persistentVolumeReclaimPolicy']=='Retain'
      and pv['metadata']['uid']!=c['baseline']['identities']['pv']['uid']
      and vol['metadata']['uid']!=c['baseline']['identities']['longhorn_volume']['uid']
      and vol['spec']['fromBackup']==get('backups.longhorn.io','backup-da37c4f713e8','longhorn-system')['status']['url'])
 state={'state':'pending','regeneration':'Restore authenticated completed backup-da37c4f713e8 through exact source-bound CSI rehearsal',
 'original_journal_sha256':hashlib.sha256(raw).hexdigest(),'unique_source_archive_preserved':True,'removed':[],
 'derivative_volume_actual_size':vol['status'].get('actualSize'),'original_resources_changed':False}
 out=R/'version-rehearsal-retirement.json';need(not out.exists())
 def save(first=False):
  fd=os.open(out,os.O_WRONLY|os.O_NOFOLLOW|(os.O_CREAT|os.O_EXCL if first else os.O_TRUNC),0o600)
  with os.fdopen(fd,'w') as f:json.dump(state,f);f.flush();os.fsync(f.fileno())
 save(True)
 items=[('pod',pod,'/api/v1/namespaces/bortus/pods/'),('pvc',claim,'/api/v1/namespaces/bortus/persistentvolumeclaims/'),
 ('pv',pv,'/api/v1/persistentvolumes/'),('volumes.longhorn.io',vol,'/apis/longhorn.io/v1beta2/namespaces/longhorn-system/volumes/'),('storageclass',sc,'/apis/storage.k8s.io/v1/storageclasses/')]
 for resource,obj,route in items:
  ns=obj['metadata'].get('namespace');current=get(resource,obj['metadata']['name'],ns);need(current['metadata']['uid']==obj['metadata']['uid'])
  pre={k:current['metadata'][k] for k in ('uid','resourceVersion')}
  call(['delete','--raw',route+obj['metadata']['name'],'-f','-'],json.dumps({'apiVersion':'v1','kind':'DeleteOptions','preconditions':pre}).encode())
  until=time.monotonic()+90
  while time.monotonic()<until:
   result=subprocess.run(K+['get',resource,obj['metadata']['name']]+(['-n',ns] if ns else [])+['--ignore-not-found','-o','json'],capture_output=True,timeout=20)
   need(result.returncode==0)
   if not result.stdout.strip():break
   need(json.loads(result.stdout)['metadata']['uid']==pre['uid']);time.sleep(.5)
  else:raise RuntimeError('owned_derivative_deletion_not_observed')
  state['removed'].append({'kind':obj['kind'],'name':obj['metadata']['name'],'uid':pre['uid']});save()
 need((R/'journal.json').read_bytes()==raw)
 state['state']='completed';save();print(json.dumps({'owned_restore_derivative_retired':len(state['removed']),'original_application_and_backup_unchanged':True}))
if __name__=='__main__':
 try:main()
 except Exception as e:
  import sys,traceback
  print(json.dumps({'retirement_failed':type(e).__name__,'locations':[Path(f.filename).name+':'+str(f.lineno) for f in traceback.extract_tb(e.__traceback__)]}),file=sys.stderr);raise SystemExit(1)
