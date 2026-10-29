"""Capture a separate post-core cleanup recovery generation; no cluster mutations.
Retains the parent checkpoint and permits only capturedAt/nativeBackups renewal.
"""
import argparse
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028'
OUT=H/'post-core-cleanup-recovery'
PREFIX='postcore-cleanup-20261029'
CORE_SHA='0e0be0645a4f4077a3bbdad577db05d6498874954c33ec1c98291a3fd8670bc4'
TRANSITION={'path':str(H/'reviewed-controller-transition-1c6f.json'),'sha256':'94198c86ebbbe303341ef6be5cc3a1666f938771083344848485824a3d6682e0'}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

def save(path,value):
 data=(json.dumps(value,indent=2)+'\n').encode()
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 return {'path':str(path),'sha256':sha(path)}

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--storage-checkpoint',type=Path,required=True)
 parser.add_argument('--storage-checkpoint-sha256',required=True)
 a=parser.parse_args();os.umask(0o077)
 assert os.getuid()==1000 and F.is_mount() and H.resolve()==H and OUT.resolve()==OUT and OUT.is_dir()
 assert subprocess.check_output(['findmnt','-n','-o','UUID','--target',str(F)],text=True).strip()=='3c792469-ea0e-4a2c-98e8-1185b141607b'
 assert a.storage_checkpoint==OUT/'storage-checkpoint.json'
 destinations=[H/'post-core-cleanup-current58-manifest.json',OUT/'renewal-proof.json',OUT/'renewal-validation.json']
 assert all(not p.exists() and not p.is_symlink() for p in destinations),'Retain an existing generation; never overwrite or replay it'
 repo=Path(__file__).resolve().parents[2]
 core_path=repo/'scripts/migration/verify-completed-core-preservation.py';assert sha(core_path)==CORE_SHA
 core=module('renew_completed_core',core_path)
 for name,digest in core.PINS.items():assert sha(repo/name)==digest
 receipt_ref={'path':str(a.storage_checkpoint),'sha256':a.storage_checkpoint_sha256}
 receipt=json.loads(core.bound(receipt_ref).read_text())
 assert receipt['status']=='completed' and receipt['checkpoint_prefix']==PREFIX and len(receipt['volumes'])==28
 reconcile=module('renew_terminal',repo/'scripts/migration/reconcile-kubernetes-vendor.py')
 plan,terminal=reconcile.terminal(H,F,core.SUCCESS,core.SUCCESS_SHA)
 assert terminal['authoritySHA256']==core.AUTH_SHA and plan['checkpoint']['sha256']==core.CHECKPOINT_SHA
 parent=plan['checkpoint'];original=json.loads(core.bound(parent).read_text())
 roles=repo/'k8s-rewrite/ansible-playbook/roles'
 guard=module('renew_original_guard',roles/'security_maintenance/files/kernel_checkpoint.py')
 proxy=module('renew_proxy',roles/'kubernetes_security_patch/files/checkpoint.py')
 proof,before,after=core.reviewed_transition(TRANSITION)
 items=proxy.normalize_proxy(guard.get('persistentvolumeclaims,persistentvolumes,volumes.longhorn.io,deployments,statefulsets,daemonsets'),plan)
 matches=[o for o in items if (o['kind'],o['metadata'].get('namespace'),o['metadata']['name'])==('Deployment','ingenium','ingenium')]
 assert len(matches)==1 and matches[0]['metadata']['uid']==proof['uid'] and matches[0]['spec']==after
 matches[0]['spec']=copy.deepcopy(before)
 rows=guard.project(items);guard.validate_inventory(rows)
 assert len(rows)==219 and rows==original['identities']
 assert {o['metadata']['name']:o['metadata']['uid'] for o in guard.get('nodes')}==original['clusterNodes']
 assert guard.ephemeral_sources()==original['ephemeralSources']
 active={row['name']:row['uid'] for row in rows if row['kind']=='Volume' and row['state']=='attached'}
 entries={row['volume']:row for row in receipt['volumes']};assert len(entries)==28 and set(entries)==set(active)
 backups=[b for b in guard.get('backups.longhorn.io') if b['metadata'].get('labels',{}).get('security-maintenance-checkpoint')==PREFIX]
 snapshots={o['metadata']['name']:o for o in guard.get('snapshots.longhorn.io') if o['metadata'].get('labels',{}).get('security-maintenance-checkpoint')==PREFIX}
 assert len(backups)==len(snapshots)==28 and {b['status']['volumeName'] for b in backups}==set(active)
 renewed=copy.deepcopy(original);renewed['capturedAt']=dt.datetime.now(dt.timezone.utc).isoformat();renewed['nativeBackups']=[]
 for b in sorted(backups,key=lambda item:item['metadata']['name']):
  metadata,status=b['metadata'],b['status'];volume=status['volumeName'];entry=entries[volume]
  assert not metadata.get('deletionTimestamp') and status['state']=='Completed' and not status.get('error')
  assert entry['backup']==metadata['name'] and entry['backup_uid']==metadata['uid'] and entry['volume_uid']==active[volume]
  assert entry['snapshot']==status['snapshotName']==b['spec']['snapshotName'] and status['backupTargetName']=='default'
  assert entry['backup_created_at']==status['backupCreatedAt']
  snapshot=snapshots[entry['snapshot']]
  assert snapshot['metadata']['uid']==entry['snapshot_uid'] and not snapshot['metadata'].get('deletionTimestamp')
  assert snapshot['spec']['volume']==volume and snapshot['status']['readyToUse'] is True and not snapshot['status'].get('error')
  guard.fresh(status['backupCreatedAt']);guard.fresh(status['snapshotCreatedAt'])
  renewed['nativeBackups'].append({'name':metadata['name'],'uid':metadata['uid'],'volume':volume,'volumeUID':active[volume],'statusSHA256':guard.digest(guard.backup_identity(status))})
 assert sha(core_path)==CORE_SHA and sha(a.storage_checkpoint)==a.storage_checkpoint_sha256
 reference=save(destinations[0],renewed)
 save(destinations[1],{'schemaVersion':1,'owner':'post-core-cleanup-recovery','physicalRoot':str(F),'physicalUUID':'3c792469-ea0e-4a2c-98e8-1185b141607b',
  'parent':parent,'renewed':reference,'storageCheckpoint':receipt_ref,'terminal':terminal,'sourceSHA256':sha(Path(__file__)),
  'permittedChangedFields':['capturedAt','nativeBackups'],'reviewedControllerTransition':TRANSITION,
  'clusterMutationsPerformed':False,'retention':'Unique parent/backup binding and validation evidence; original parent and authority remain unchanged',
  'regeneration':'Read-only capture from the exact completed storage checkpoint; never resubmit the native backup prefix',
  'fullValidationPending':True})
 # Every original freshness/CP/NAS/identity gate runs after capture. Failure retains
 # the unique candidate and proof; absence of validation is never a success claim.
 validation=core.validate(repo,transition=TRANSITION,recovery=reference)
 save(destinations[2],{'passed':True,'manifest':reference,'proofSHA256':sha(destinations[1]),'validation':validation})
 print(json.dumps({'manifest':reference,'validation':{'path':str(destinations[2]),'sha256':sha(destinations[2])},'clusterMutationsPerformed':False}))

if __name__=='__main__':main()
