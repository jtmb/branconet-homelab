#!/usr/bin/env python3
"""Authenticate retained archives without claiming the backup set is complete."""
import concurrent.futures
import datetime
import importlib.util
import json
import pathlib
import subprocess

def main():
 spec=importlib.util.spec_from_file_location('cold_backup',pathlib.Path(__file__).with_name('backup-data.py'))
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 repo=pathlib.Path(__file__).resolve().parents[2]
 initial=json.loads((repo/'evidence/data-backups-initial.json').read_text())
 entries=[a for a in initial['archives'] if a.get('ok')]
 stamp='20261009T151756Z'
 for prefix in ['gluster-brick','gluster-logical']:
  host='192.168.0.5';path=module.NAS+'/'+prefix+'-'+host+'-'+stamp+'.tar.gz.age'
  check=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002',f'james@{host}','sha256sum',path],text=True,capture_output=True,check=True)
  entries.append({'ok':True,'host':host,'kind':prefix,'archive':path,'ciphertext_sha256':check.stdout.split()[0],'source_paths':['/gluster/volumes'] if prefix=='gluster-brick' else ['/mnt/container-program-files'],'excluded_paths':[] if prefix=='gluster-brick' else ['/mnt/container-program-files/plex/config/Library/Application Support/Plex Media Server/Logs']})
 report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'complete_backup_set':False,'reason':'Master clean backup and all-brick coverage remain incomplete; original anonymous paths are missing. These checks authenticate individual retained archives only.','archives':[]}
 path=repo/'evidence/archive-verification.json'
 def save():path.write_text(json.dumps(report,indent=2)+'\n')
 save()
 print(json.dumps({'event':'archive_verification_start','archives':len(entries)}),flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  futures={pool.submit(module.verify,item):item for item in entries}
  for future in concurrent.futures.as_completed(futures):
   try:item=future.result()
   except Exception as error:item={**futures[future],'authenticated_decryption_verified':False,'error':type(error).__name__}
   report['archives'].append(item);save()
   print(json.dumps({'event':'archive_authenticated','host':item['host'],'kind':item.get('kind','cold'),'verified':item['authenticated_decryption_verified'],'tar_entries':item.get('tar_entries')}),flush=True)
 report['completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
 print(json.dumps({'event':'individual_archive_verification_finished','evidence':str(path),'complete_backup_set':False}),flush=True)

if __name__=='__main__':main()
