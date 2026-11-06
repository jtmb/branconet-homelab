"""Remove only this follow-up's empty terminal Ansible directories.

All files, source, unique receipts, archives and prior failed targets survive.
Requires original complete Linux reference checks and Windows exclusive handles.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import subprocess

BASE='/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025'
REL='platform-upstream-review-20261027/autonomous-hardening-20261028'
NAMES=('ansible-tmp','ansible-verification-scratch','kernel-checkpoint-scratch','kernel-maintenance-scratch')
GUARD='3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87'

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def ident(p):
 s=p.lstat();return {k:getattr(s,'st_'+k) for k in ('dev','ino','mode','uid','gid','size','mtime_ns','ctime_ns','blocks')}

def save(p,v):
 with p.open('x') as f:json.dump(v,f,indent=2)
 if os.name!='nt':os.chown(p,1000,1000)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['inventory','windows','apply'])
 p.add_argument('--scope',choices=['existing','kubernetes-empty','post-core-recovery-empty','closed-file-empty'],default='existing')
 p.add_argument('--kubernetes-success',help='Terminal native runner result, relative to H')
 p.add_argument('--kubernetes-success-sha256');a=p.parse_args()
 root=Path(r'\\?\UNC\wsl.localhost\Ubuntu'+BASE.replace('/','\\')) if os.name=='nt' else Path(BASE)
 h=root/REL
 stem={'kubernetes-empty':'kubernetes-scratch-reconciliation','post-core-recovery-empty':'post-core-recovery-scratch-reconciliation','closed-file-empty':'closed-file-scratch-reconciliation'}.get(a.scope,'scratch-reconciliation')
 planfile=h/(stem+'-plan.json');names=('kubernetes-maintenance-scratch',) if a.scope=='kubernetes-empty' else NAMES
 if a.scope=='kubernetes-empty':
  assert a.kubernetes_success and a.kubernetes_success_sha256
  relative=Path(a.kubernetes_success);assert not relative.is_absolute() and '..' not in relative.parts
  success=h/relative;assert success.is_file() and sha(success)==a.kubernetes_success_sha256
  terminal=json.loads(success.read_text());settings=terminal['settings']
  assert terminal['exitCode']==0 and terminal.get('finishedUTC') and settings['kubernetes_security_patch_apply'] is True
  # Translate only exact Linux task-root paths for the Windows handle pass.
  def owned_linux(value):
   assert value.startswith(BASE+'/'+REL+'/')
   suffix=value[len(BASE)+1:];assert '..' not in Path(suffix).parts
   return root/suffix
  authority=owned_linux(settings['kubernetes_security_patch_manifest'])
  assert sha(authority)==settings['kubernetes_security_patch_manifest_sha256']
  recovery=owned_linux(settings['kubernetes_security_patch_receipt_dir'])
  completed=[json.loads(x.read_text()) for x in recovery.glob('*.completed.json')]
  assert len(completed)==3 and {x['node'] for x in completed}=={'masternode','workernode1','workernode2'}
  assert all(x['completed'] is True and x['nativeLastConsumerCompleted'] is True and x['authoritySHA256']==settings['kubernetes_security_patch_manifest_sha256'] for x in completed)
 else:assert a.kubernetes_success is None and a.kubernetes_success_sha256 is None
 retained_exceptions=[];pending_evidence={};excluded_trees=[];selected_targets=None
 if a.scope=='kubernetes-empty':
  scratch_parent=h/'kubernetes-maintenance-scratch'
  expected_linux=BASE+'/'+REL+'/kubernetes-maintenance-scratch/'
  terminal_results=sorted((h/'kubernetes-maintenance-receipts').glob('*-result.json'))
  # First collect every original failed deletion target. Never inspect, sweep,
  # select or retry its contents through the privileged reconciler.
  for result_path in terminal_results:
   value=json.loads(result_path.read_text());cleanup=value.get('scratchCleanup',{})
   if 'retainedPath' in cleanup:
    target=owned_linux(cleanup['retainedPath']);excluded_trees.append(target)
    retained_exceptions.append({'path':cleanup['retainedPath'],'reason':'Original cleanup refusal remains protected: '+cleanup.get('reason','unspecified original safety refusal'),'sourceResult':str(result_path.relative_to(h)),'sourceSHA256':sha(result_path)})
  selected_targets=[]
  for result_path in terminal_results:
   value=json.loads(result_path.read_text());cleanup=value.get('scratchCleanup',{})
   if 'pendingReconciliationPath' not in cleanup:continue
   run_id=result_path.name.removesuffix('-result.json');assert re.fullmatch('[a-f0-9]{32}',run_id)
   target_linux=cleanup['pendingReconciliationPath'];assert target_linux==expected_linux+run_id
   target=owned_linux(target_linux)
   if any(target==old or old in target.parents or target in old.parents for old in excluded_trees):
    retained_exceptions.append({'path':target_linux,'reason':'Pending target overlaps an original retainedPath refusal; not evaluated'});continue
   ownership_path=result_path.with_name(run_id+'-ownership.json');assert ownership_path.is_file()
   owner=json.loads(ownership_path.read_text())
   assert owner['owner']=='kubernetes1372-security-patch' and owner['physicalVolume']==BASE
   assert owner['scratch']==target_linux and owner['receipts']==BASE+'/'+REL+'/kubernetes-maintenance-receipts'
   assert owner['recovery']==BASE+'/'+REL+'/kubernetes-recovery-'+run_id
   assert value.get('finishedUTC') and isinstance(value.get('exitCode'),int) and value['exitCode']>=0,'Pending cleanup requires terminal runner result'
   assert cleanup.get('multiprocessingExitCompleted') is True and cleanup.get('deletionAttempted') is False,'Only deferred, never-attempted scratch qualifies'
   assert value['settings']['kubernetes_security_patch_receipt_dir']==owner['recovery']
   assert target.is_dir(),'Pending directory disappeared without a reconciliation receipt'
   selected_targets.append(target)
   pending_evidence[run_id]={'result':str(result_path.relative_to(h)),'resultSHA256':sha(result_path),'ownership':str(ownership_path.relative_to(h)),'ownershipSHA256':sha(ownership_path)}
  assert len(set(selected_targets))==len(selected_targets)
  # A parent containing even one protected/unselected child remains in place.
  if scratch_parent.is_dir():
   unselected=[child for child in scratch_parent.iterdir() if child not in selected_targets]
   if unselected or excluded_trees:
    retained_exceptions.append({'path':BASE+'/'+REL+'/kubernetes-maintenance-scratch','reason':'Parent retained because protected or unselected children exist','children':[str(x.relative_to(h)) for x in unselected]})
   elif selected_targets:selected_targets=[scratch_parent]
 if a.scope=='post-core-recovery-empty':
  recovery=h/'post-core-cleanup-recovery'
  terminal_path=recovery/'operator-result.json';owner_path=recovery/'ownership.json'
  terminal=json.loads(terminal_path.read_text());owner=json.loads(owner_path.read_text())
  assert terminal['status']=='completed' and terminal['exitCode']==0 and terminal['finishedUTC']
  assert owner['owner']=='01a18518-24e7-7ce3-b620-f9ca775bfd1c' and owner['root']==BASE
  assert owner['physicalUUID']=='3c792469-ea0e-4a2c-98e8-1185b141607b'
  assert owner['settings']['storage_checkpoint_prefix']=='postcore-cleanup-20261029'
  assert owner['settings']['storage_checkpoint_receipt_path']==BASE+'/'+REL+'/post-core-cleanup-recovery/storage-checkpoint.json'
  checkpoint_path=recovery/'storage-checkpoint.json';checkpoint=json.loads(checkpoint_path.read_text())
  assert checkpoint['status']=='completed' and checkpoint['checkpoint_prefix']=='postcore-cleanup-20261029'
  assert len(checkpoint['volumes'])==28 and all(x['state']=='Completed' for x in checkpoint['volumes'])
  selected_targets=[recovery/'scratch']
  assert owner['generatedPaths'].count(BASE+'/'+REL+'/post-core-cleanup-recovery/scratch')==1
  pending_evidence={'post-core-cleanup-recovery':{'terminalSHA256':sha(terminal_path),'ownershipSHA256':sha(owner_path),'checkpointSHA256':sha(checkpoint_path)}}
  # The original permission-denied invocations are outside this new finite
  # scope. Do not traverse or retry them during the protected-file inventory.
  excluded_trees=[h/'kubernetes-maintenance-scratch']
  retained_exceptions=[{'path':BASE+'/'+REL+'/kubernetes-maintenance-scratch','reason':'Original failed invocation scopes remain excluded; this operation selects only the new terminal backup scratch'}]
 if a.scope=='closed-file-empty':
  selected_targets=[]
  for node in ('masternode','workernode2'):
   run=h/'closed-file-offload'/node
   if not run.is_dir():continue
   for terminal_path in [run/'inventory-operator.json',*sorted(run.glob('retirement-*-operator.json'))]:
    if not terminal_path.exists():continue
    phase=terminal_path.name.removesuffix('-operator.json')
    assert phase=='inventory' or re.fullmatch('retirement-[0-9a-f]{32}',phase)
    owner_path=run/(phase+'-ownership.json');owner=json.loads(owner_path.read_text());terminal=json.loads(terminal_path.read_text())
    target=run/(phase+'-ansible-scratch')
    expected=BASE+'/'+REL+'/closed-file-offload/'+node+'/'+phase+'-ansible-scratch'
    assert owner['owner']=='closed-file-offload' and owner['node']==node and owner['scratch']==expected
    assert owner['physicalUUID']=='3c792469-ea0e-4a2c-98e8-1185b141607b'
    assert terminal['ownershipSHA256']==sha(owner_path) and terminal['sourceSHA256']==owner['sourceSHA256']
    assert terminal['scratchRequiresInactiveReconciliation']==expected
    if terminal['status']!='completed' or terminal.get('exitCode')!=0:
     retained_exceptions.append({'path':expected,'reason':'Non-successful phase scratch remains protected','terminalSHA256':sha(terminal_path)})
     excluded_trees.append(target);continue
    assert target.is_dir(),'Terminal scratch requires an explicit reconciliation receipt'
    selected_targets.append(target)
    pending_evidence[node+'/'+phase]={'terminalSHA256':sha(terminal_path),'ownershipSHA256':sha(owner_path)}
  assert selected_targets and len(selected_targets)==len(set(selected_targets))
  excluded_trees.append(h/'kubernetes-maintenance-scratch')
  retained_exceptions.append({'path':BASE+'/'+REL+'/kubernetes-maintenance-scratch','reason':'Original failed invocation scopes remain excluded from this finite scratch-only operation'})
 if a.mode=='windows':
  assert os.name=='nt'
  import ctypes
  from ctypes import wintypes
  plan=json.loads(planfile.read_text());assert plan['sourceSHA256']==sha(Path(__file__))
  k=ctypes.WinDLL('kernel32',use_last_error=True)
  k.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE];k.CreateFileW.restype=wintypes.HANDLE;k.CloseHandle.argtypes=[wintypes.HANDLE]
  handles=[]
  try:
   for row in plan['directories']:
    handle=k.CreateFileW(str(root/row['relative']),0x80000000,0,None,3,0x02000000,None)
    assert handle not in (None,ctypes.c_void_p(-1).value),('Protect exact failed directory',row['relative'],ctypes.get_last_error())
    handles.append(handle)
   assert all(sha(h/rel)==digest for rel,digest in plan['protected'].items())
  finally:
   for handle in handles:k.CloseHandle(handle)
  save(h/(stem+'-windows.json'),{'planSHA256':sha(planfile),'exclusiveHandlesClosed':len(handles),'protectedUnchanged':True});print(json.dumps({'exclusiveHandlesClosed':len(handles)}));return
 assert os.geteuid()==0 and root.is_mount() and h.resolve()==h
 assert subprocess.check_output(['findmnt','-n','-o','UUID','-T',str(root)]).decode().strip()=='3c792469-ea0e-4a2c-98e8-1185b141607b'
 # Terminal operation evidence is checked before evaluating any target.
 successful_kernel=[x for mode in ['apply','complete-master'] for x in h.glob('kernel-maintenance-'+mode+'-*.json') if json.loads(x.read_text())['exitCode']==0]
 assert successful_kernel
 assert any(json.loads(x.read_text()).get('exitCode')==0 for x in h.glob('tls-ansible-fd-result-*.json'))
 targets=selected_targets if selected_targets is not None else [h/n for n in names];assert all(x.is_dir() and x.resolve()==x for x in targets)
 paths=[p for target in targets for p in [target,*target.rglob('*')]]
 assert all(p.is_dir() and not p.is_symlink() and not p.is_mount() and p.resolve()==p and p.stat().st_dev==root.stat().st_dev and p.stat().st_uid in (0,1000) and not os.listxattr(p) for p in paths), 'Unexpected file or unique evidence protects its exact path'
 guard=root/'node-cleanup-20261027/master-generated-cleanup/reference-full-properties.py';assert sha(guard)==GUARD
 lib={'__name__':'unchanged_complete_scratch_reference_guard'};exec(compile(guard.read_bytes(),str(guard),'exec'),lib)
 lib.update(BASE=root,ATTEMPTS=tuple(str(p.relative_to(root)) for p in targets));refs=lib['idle']()
 rows=sorted([{'relative':str(p.relative_to(root)),'identity':ident(p)} for p in paths],key=lambda x:x['relative'])
 if a.mode=='inventory':
  if a.scope in ('kubernetes-empty','post-core-recovery-empty','closed-file-empty'):
   protected={}
   for directory,dirs,files in os.walk(h,followlinks=False):
    base=Path(directory)
    dirs[:]=[name for name in dirs if not any((base/name)==t or t in (base/name).parents for t in [*targets,*excluded_trees])]
    for name in files:
     candidate=base/name
     if candidate.is_file():protected[str(candidate.relative_to(h))]=sha(candidate)
  else:protected={str(p.relative_to(h)):sha(p) for p in h.rglob('*') if p.is_file() and not any(p.is_relative_to(t) for t in targets)}
  save(planfile,{'sourceSHA256':sha(Path(__file__)),'directories':rows,'references':refs,'protected':protected,'pendingEvidence':pending_evidence,'retainedExceptions':retained_exceptions,'regeneration':'Recreate only the recorded empty directories with identical ownership/modes. No cluster or completed workload needs replay; original retainedPath refusals are never retried.'})
  print(json.dumps({'directories':len(rows),'allocatedBytes':sum(x['identity']['blocks']*512 for x in rows),'retainedExceptions':retained_exceptions}));return
 plan=json.loads(planfile.read_text());win=json.loads((h/(stem+'-windows.json')).read_text())
 assert rows==plan['directories'] and plan['sourceSHA256']==sha(Path(__file__))
 assert pending_evidence==plan.get('pendingEvidence',{}) and retained_exceptions==plan.get('retainedExceptions',[]),'Terminal ownership or protected exceptions changed'
 assert win=={'planSHA256':sha(planfile),'exclusiveHandlesClosed':len(rows),'protectedUnchanged':True}
 assert all(sha(h/rel)==digest for rel,digest in plan['protected'].items())
 removed=[]
 for row in sorted(rows,key=lambda x:len(Path(x['relative']).parts),reverse=True):
  p=root/row['relative'];now=ident(p);assert all(now[k]==row['identity'][k] for k in ('dev','ino','mode','uid','gid')) and not any(p.iterdir())
  p.rmdir();removed.append({'path':str(p),'allocatedBytes':now['blocks']*512})
 assert all(sha(h/rel)==digest for rel,digest in plan['protected'].items())
 save(h/(stem+'-receipt.json'),{'status':'completed','removed':removed,'removedAllocatedLinuxBytes':sum(x['allocatedBytes'] for x in removed),'protectedUnchanged':True,'retainedExceptions':retained_exceptions,'WindowsRecoveryClaimed':False})
 print(json.dumps({'removedDirectories':len(removed),'removedAllocatedLinuxBytes':sum(x['allocatedBytes'] for x in removed)}))

if __name__=='__main__':main()
