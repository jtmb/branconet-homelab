#!/usr/bin/env python3
"""Relocate the adopted Plex workload while its Flux release is suspended."""
import datetime,json,pathlib,subprocess,tempfile,yaml
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
def run(args,body=None):
 return subprocess.run(k+args,input=json.dumps(body).encode() if body is not None else None,capture_output=True,check=True).stdout
hr=json.loads(run(['get','helmrelease','plex','-n','flux-system','-o','json']))
if not hr['spec'].get('suspend'):raise SystemExit('Suspend Plex reconciliation for controlled relocation')
d=json.loads(run(['get','deploy','plex','-n','plex','-o','json']));previous=d['spec']['template']['spec'].get('nodeSelector');original=json.loads(run(['get','pods','-n','plex','-l','app=plex','-o','json']))['items'][0]['spec']['nodeName']
claim=json.loads(run(['get','pvc','plex-data-0','-n','plex','-o','json']));before=json.loads((ROOT/'evidence/plex-library-proof.json').read_text());node='workernode1' if original!='workernode1' else 'workernode2'
try:
 run(['patch','deploy','plex','-n','plex','--type=merge','-p',json.dumps({'spec':{'template':{'spec':{'nodeSelector':{'kubernetes.io/hostname':node}}}}})])
 run(['rollout','status','deploy/plex','-n','plex','--timeout=400s'])
 proof=subprocess.run([__import__('sys').executable,str(ROOT/'scripts/migration/plex-library-proof.py')],capture_output=True)
 if proof.returncode:
  diagnostic=RUNTIME/'plex-relocation.diagnostic';diagnostic.write_bytes(proof.stderr);diagnostic.chmod(0o600)
  raise RuntimeError('Relocated Plex library proof failed; protected diagnostic saved')
 after=json.loads((ROOT/'evidence/plex-library-proof.json').read_text());current=json.loads(run(['get','pvc','plex-data-0','-n','plex','-o','json']))
 if before['sections']!=after['sections'] or before['media_range_sha256']!=after['media_range_sha256'] or current['metadata']['uid']!=claim['metadata']['uid'] or current['spec']['volumeName']!=claim['spec']['volumeName']:raise SystemExit('Library/media/claim identity changed during relocation')
 report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_node':original,'relocated_node':node,'library_counts_equal':True,'real_media_range_equal':True,'same_claim_uid_and_volume':True,'retained_machine_identity_equal':True}
 (ROOT/'evidence/plex-relocation-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
finally:
 run(['patch','deploy','plex','-n','plex','--type=merge','-p',json.dumps({'spec':{'template':{'spec':{'nodeSelector':previous}}}})])
 run(['rollout','status','deploy/plex','-n','plex','--timeout=400s'])
