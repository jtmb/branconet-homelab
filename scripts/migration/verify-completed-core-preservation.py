"""Read-only post-install preservation gate; never a pre-install qualification substitute.
No artifact recreation, signature replay, output files, or cluster mutations.
"""
import copy
import contextlib
import datetime as dt
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys

F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028'
SUCCESS='kubernetes-maintenance-receipts/56f152a9adc044478db62e3cacc65288-result.json'
SUCCESS_SHA='583d6a0eece75e23940ff4d6f1a4a805dfe6b58148fc8a3d0f44a1d5a9736072'
AUTH_SHA='c21016a7c150f50f66c3f86b1433412363409f7e6ecbce913c3414afdbf03ba8'
VENDOR_SHA='bb96c82be216747db666b2ef9d10a927688df7e7119b6f3f2775605b6d5e9859'
CLEANUP_SHA='240af90755034e02318381f1e021bbb7de35b0afb6378da53328216624157a05'
CHECKPOINT_SHA='e9bb92c5a605ddd5622a2fdce033b3c577f7423792af55c8eead3d26c7797769'
PINS={
 'scripts/migration/reconcile-kubernetes-vendor.py':'095f8211fa3b46f48eefb4343711e288f62973da0a2dce709dc9410a033c3b7a',
 'k8s-rewrite/ansible-playbook/roles/security_maintenance/files/kernel_checkpoint.py':'b3c5140cb04adfa934f60206c2695bc2f6663148359ae55f0d8145247bcb1d65',
 'k8s-rewrite/ansible-playbook/roles/kubernetes_security_patch/files/checkpoint.py':'61c2975bcecad83e02e9a9fcd560f210e0d943a6c3fac9f1b530035551519233',
 'k8s-rewrite/ansible-playbook/roles/kubernetes_security_patch/files/native_binaries.py':'c16dda3a44793f8f97a26cf42b19bff4b44709a55136096918c040bcfc254b0d'}
COMPLETIONS={
 'masternode-v54gs332.json.completed.json':'3d58746069d685fc6cd6014b02504f3e4527731ed8de9a56af8acbf2a66546e2',
 'workernode1-e25jm_xx.json.completed.json':'40dd156486019f59342cc718764c79c3fe40b394cb8c1113835997ec42f89d80',
 'workernode2-fgdgsjrb.json.completed.json':'3db0be672882bb46df1679de33ac5cfbd21a8d92a352db74e4ffc6fb9a88c08f'}

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
 return h.hexdigest()

def bound(item):
 p=Path(item['path'])
 assert H in p.parents and p.resolve()==p and not p.is_symlink() and sha(p)==item['sha256']
 return p

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path)
 value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
 return value

def reviewed_transition(reference):
 assert reference['path']==str(H/'reviewed-controller-transition-1c6f.json') and reference['sha256']=='94198c86ebbbe303341ef6be5cc3a1666f938771083344848485824a3d6682e0'
 proof=json.loads(bound(reference).read_text())
 assert proof['schemaVersion']==1 and (proof['kind'],proof['namespace'],proof['name'],proof['uid'])==('Deployment','ingenium','ingenium','399abce7-cf4e-49d5-a743-a3e647390d9c')
 assert proof['chartsRevision']=='1c6f142493685676f9d8fee339400e0fe8d22ee5'
 before=json.loads(bound(proof['beforeSpec']).read_text());after=json.loads(bound(proof['afterSpec']).read_text());bound(proof['sourceValidation'])
 digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 assert digest(before)==proof['beforeSpecSHA256']=='5126c66d81b7111d52b72a09cab676fba71dc12d29d07bd0d403333b247ceb10'
 assert digest(after)==proof['afterSpecSHA256']=='d0b9b055f479414f910c2c2abec3499560787e60a1f9e51334a09753e19a0584'
 restored=copy.deepcopy(after)
 for field in ('containers','initContainers'):
  old=before['template']['spec'][field][0]['image'];new=after['template']['spec'][field][0]['image']
  assert old!=new and new=='docker.io/jtmb92/ingenium@sha256:1925d5695fba242f4990748473f72d847276c10ae721be13173e974dc404ec50'
  restored['template']['spec'][field][0]['image']=old
 key='checksum/lan-gateway'
 assert after['template']['metadata']['annotations'][key]=='709870aea1ea8c20d1762238c504c0fe90416e3f10dc82c7d05542443572dfce'
 assert before['template']['metadata']['annotations'][key]!=after['template']['metadata']['annotations'][key]
 restored['template']['metadata']['annotations'][key]=before['template']['metadata']['annotations'][key]
 assert restored==before,'Only the three reviewed fields may differ'
 return proof,before,after

def renewed_checkpoint(reference, parent):
 assert reference['path']==str(H/'post-core-cleanup-current58-manifest.json')
 original=json.loads(bound(parent).read_text());renewed=json.loads(bound(reference).read_text())
 assert parent['sha256']==CHECKPOINT_SHA
 evidence_path=H/'post-core-cleanup-recovery/renewal-proof.json'
 assert evidence_path.resolve()==evidence_path and not evidence_path.is_symlink()
 evidence=json.loads(evidence_path.read_text())
 assert evidence['schemaVersion']==1 and evidence['parent']==parent and evidence['renewed']==reference
 receipt_ref=evidence['storageCheckpoint']
 assert receipt_ref['path']==str(H/'post-core-cleanup-recovery/storage-checkpoint.json')
 receipt=json.loads(bound(receipt_ref).read_text())
 assert receipt['status']=='completed' and receipt['checkpoint_prefix']=='postcore-cleanup-20261029' and receipt['backup_target_name']=='default'
 assert receipt['consistency']=='crash-consistent-online' and receipt['application_cold_backup'] is False and receipt['restore_verified'] is False
 finished=dt.datetime.fromisoformat(json.loads(bound({'path':str(H/SUCCESS),'sha256':SUCCESS_SHA}).read_text())['finishedUTC'])
 timestamp=lambda text:dt.datetime.fromisoformat(text.replace('Z','+00:00'))
 assert finished<timestamp(receipt['completed_at'])<=timestamp(renewed['capturedAt'])<=dt.datetime.now(dt.timezone.utc)
 unchanged=copy.deepcopy(renewed)
 for key in ('capturedAt','nativeBackups'):unchanged[key]=original[key]
 assert unchanged==original,'Renewal may change only capturedAt and nativeBackups'
 active={row['name']:row['uid'] for row in original['identities'] if row['kind']=='Volume' and row['state']=='attached'}
 offline={row['name'] for row in original['identities'] if row['kind']=='Volume' and row['state']=='detached'}
 assert len(active)==28 and len(offline)==16 and set(receipt['excluded_unattached_volumes'])==offline
 assert len(receipt['volumes'])==len(renewed['nativeBackups'])==28
 entries={row['volume']:row for row in receipt['volumes']};backups={row['volume']:row for row in renewed['nativeBackups']}
 assert set(entries)==set(backups)==set(active)
 assert len({row['uid'] for row in backups.values()})==28
 for volume,uid in active.items():
  row=entries[volume];backup=backups[volume]
  suffix=hashlib.sha256(volume.encode()).hexdigest()[:10]
  assert row['volume_uid']==backup['volumeUID']==uid and row['state']=='Completed'
  assert row['backup']==backup['name']=='postcore-cleanup-20261029-b-'+suffix and row['backup_uid']==backup['uid']
  assert row['snapshot']=='postcore-cleanup-20261029-s-'+suffix and row['snapshot_uid']
  assert finished<timestamp(row['backup_created_at'])<=timestamp(receipt['completed_at'])
 return reference

def validate(repo, transition=None, recovery=None):
 repo=Path(repo).resolve()
 assert F.is_mount() and H.resolve()==H
 for name,digest in PINS.items():assert sha(repo/name)==digest, 'Preservation source changed: '+name
 reconcile=module('completed_vendor_readonly',repo/'scripts/migration/reconcile-kubernetes-vendor.py')
 plan,terminal=reconcile.terminal(H,F,SUCCESS,SUCCESS_SHA)
 assert terminal['authoritySHA256']==AUTH_SHA
 completion_dir=H/'kubernetes-recovery-56f152a9adc044478db62e3cacc65288'
 assert {p.name for p in completion_dir.glob('*.completed.json')}==set(COMPLETIONS)
 for name,digest in COMPLETIONS.items():bound({'path':str(completion_dir/name),'sha256':digest})
 vendor=json.loads(bound({'path':str(H/'kubernetes1372-binaries/authority.json'),'sha256':VENDOR_SHA}).read_text())
 cleanup=json.loads(bound({'path':str(H/'kubernetes1372-vendor-cleanup/receipt.json'),'sha256':CLEANUP_SHA}).read_text())
 cleanup_plan=json.loads(bound({'path':str(H/'kubernetes1372-vendor-cleanup/plan.json'),'sha256':cleanup['planSHA256']}).read_text())
 assert cleanup['status']=='completed' and cleanup['protectedUnchanged'] is True and cleanup['successSHA256']==SUCCESS_SHA
 assert cleanup_plan['successSHA256']==SUCCESS_SHA and cleanup_plan['vendorAuthoritySHA256']==VENDOR_SHA
 result=json.loads((H/SUCCESS).read_text())
 assert dt.datetime.fromisoformat(cleanup_plan['runtime']['capturedAt'])>dt.datetime.fromisoformat(result['finishedUTC'])
 expected_removed={vendor['binaries'][n]['blob']['path'] for n in ('kubeadm','kubelet','kubectl')}|{vendor['signatureTool']['path']}
 assert {x['path'] for x in cleanup['removed']}==expected_removed
 retained={}
 for name in ('kubeadm','kubelet','kubectl'):
  entry=vendor['binaries'][name];installed=plan['binaries'][name]
  assert entry['sha256']==installed['sha256'] and entry['bytes']==installed['bytes']
  for key in ('checksum','signature','certificate','signatureVerification','scan'):
   assert entry[key]==installed[key]
   p=bound(entry[key]);retained[str(p)]=entry[key]['sha256']
  assert bound(entry['checksum']).read_text().strip()==entry['sha256']
  signature=json.loads(bound(entry['signatureVerification']).read_text())
  assert signature['subjectSHA256']==entry['sha256'] and signature['exitCode']==0 and signature['bypassFlagsUsed'] is False
  assert signature['certificateIdentity']=='krel-staging@k8s-releng-prod.iam.gserviceaccount.com' and signature['certificateIssuer']=='https://accounts.google.com'
  scan=json.loads(bound(entry['scan']).read_text())
  assert scan['subjectSHA256']==entry['sha256'] and scan['exitCode']==0 and scan['scanComplete'] is True and scan['suppressionUsed'] is False and scan['inputHashesReverifiedAfterScan'] is True
  for key in ('report','originalScanReceipt'):
   p=bound(scan[key]);retained[str(p)]=scan[key]['sha256']
  for backup in installed['originalBackups'].values():
   p=bound(backup);retained[str(p)]=backup['sha256']
 live=reconcile.live(plan,repo)
 assert plan['checkpoint']['sha256']==CHECKPOINT_SHA
 bound(plan['checkpoint'])
 selected_checkpoint=renewed_checkpoint(recovery,plan['checkpoint']) if recovery is not None else plan['checkpoint']
 roles=repo/'k8s-rewrite/ansible-playbook/roles'
 guard=module('completed_original_kernel_checkpoint',roles/'security_maintenance/files/kernel_checkpoint.py')
 proxy=module('completed_original_proxy_normalizer',roles/'kubernetes_security_patch/files/checkpoint.py')
 original_project=guard.project
 reviewed=reviewed_transition(transition) if transition is not None else None
 def project(items):
  normalized=proxy.normalize_proxy(items,plan)
  if reviewed is not None:
   proof,before,after=reviewed
   matches=[o for o in normalized if (o['kind'],o['metadata'].get('namespace'),o['metadata']['name'])==('Deployment','ingenium','ingenium')]
   assert len(matches)==1 and matches[0]['metadata']['uid']==proof['uid'] and matches[0]['spec']==after
   matches[0]['spec']=copy.deepcopy(before)
  return original_project(normalized)
 argv=sys.argv;output=io.StringIO()
 try:
  guard.project=project
  sys.argv=['kernel_checkpoint.py','--manifest',selected_checkpoint['path'],'--sha256',selected_checkpoint['sha256']]
  with contextlib.redirect_stdout(output):guard.main()
 finally:
  sys.argv=argv;guard.project=original_project
 checkpoint=json.loads(output.getvalue())
 assert checkpoint['passed'] is True and checkpoint['claims']==58 and checkpoint['activeHealthy']==28 and checkpoint['retainedOffline']==16
 if transition is not None:reviewed_transition(transition)
 if recovery is not None:renewed_checkpoint(recovery,plan['checkpoint'])
 # Recheck all retained inputs and source pins after live reads; no changed evidence accepted.
 for path,digest in retained.items():assert sha(Path(path))==digest
 for name,digest in PINS.items():assert sha(repo/name)==digest
 return {'scope':'completed-installation-final-cleanup-only','passed':True,'capturedAt':live['capturedAt'],
         'terminal':terminal,'completionSHA256':COMPLETIONS,'vendorAuthoritySHA256':VENDOR_SHA,
         'vendorCleanupSHA256':CLEANUP_SHA,'retainedEvidenceSHA256':retained,'sourcePins':PINS,
         'installedNative':live,'checkpoint':checkpoint,'checkpointOutputSHA256':hashlib.sha256(output.getvalue().encode()).hexdigest(),
         'signatureReplayPerformed':False,'preinstallAdmission':False, 'reviewedControllerTransition':transition,'freshRecoveryCheckpoint':recovery}

full58=validate
if __name__=='__main__':print(json.dumps(validate(Path(__file__).resolve().parents[2])))
