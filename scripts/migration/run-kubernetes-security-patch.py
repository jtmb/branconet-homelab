"""Finite native Kubernetes preflight/apply; protected input precedes children."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import uuid

F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028'

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--manifest',required=True,type=Path);p.add_argument('--manifest-sha256',required=True)
 p.add_argument('--apply',action='store_true',help='Explicitly run the guarded native upgrade; default is preflight')
 p.add_argument('--resume-kubeadm-with-transfer-proof',type=Path)
 p.add_argument('--resume-kubeadm-with-transfer-proof-sha256')
 p.add_argument('--closed-preflight-result',type=Path);p.add_argument('--closed-preflight-result-sha256')
 p.add_argument('--closed-preflight-log',type=Path);p.add_argument('--closed-preflight-log-sha256')
 p.add_argument('--closed-kubeadm-addon-preflight-result',type=Path);p.add_argument('--closed-kubeadm-addon-preflight-result-sha256')
 p.add_argument('--closed-kubeadm-addon-preflight-log',type=Path);p.add_argument('--closed-kubeadm-addon-preflight-log-sha256')
 a=p.parse_args();assert F.is_mount() and H.is_dir() and os.geteuid()==1000
 os.umask(0o077)
 raw=sys.stdin.buffer.readline(130).removesuffix(b'\n')
 assert 0<len(raw)<=128 and not any(x in raw for x in (b'\n',b'\r',b'\0'))
 password=raw.decode();raw=None
 assert a.manifest.resolve()==a.manifest and a.manifest.parent==H and a.manifest.is_file()
 assert hashlib.sha256(a.manifest.read_bytes()).hexdigest()==a.manifest_sha256
 assert bool(a.resume_kubeadm_with_transfer_proof)==bool(a.resume_kubeadm_with_transfer_proof_sha256),'Both explicit resume proof arguments are required'
 resume=None;closed=None;addon=None
 closed_values=[a.closed_preflight_result,a.closed_preflight_result_sha256,a.closed_preflight_log,a.closed_preflight_log_sha256]
 assert not any(closed_values) or all(closed_values),'All explicit closed-preflight result/log arguments are required'
 assert not any(closed_values) or a.resume_kubeadm_with_transfer_proof,'Closed preflight continuation requires fresh original transfer-resume proof'
 addon_values=[a.closed_kubeadm_addon_preflight_result,a.closed_kubeadm_addon_preflight_result_sha256,a.closed_kubeadm_addon_preflight_log,a.closed_kubeadm_addon_preflight_log_sha256]
 assert not any(addon_values) or (all(addon_values) and not any(closed_values) and a.resume_kubeadm_with_transfer_proof),'Addon continuation requires the complete unique failure pair and fresh proof'
 if a.resume_kubeadm_with_transfer_proof:
  assert a.apply,'Resume is an explicit apply path, never implicit default preflight'
  validator=Path(__file__).resolve().parents[2]/'k8s-rewrite/ansible-playbook/roles/kubernetes_security_patch/files/resume_transfer_proof.py'
  resume_module=runpy.run_path(str(validator))
  resume=resume_module['validate'](a.resume_kubeadm_with_transfer_proof,a.resume_kubeadm_with_transfer_proof_sha256,a.manifest,a.manifest_sha256)
  resume_intent=H/'kubernetes-maintenance-receipts/89c1dc34de834eb6863a4cc570f71442-transfer-resume-intent.json'
  if all(closed_values):
   closed=resume_module['validate_closed_preflight']({'path':str(a.closed_preflight_result),'sha256':a.closed_preflight_result_sha256},{'path':str(a.closed_preflight_log),'sha256':a.closed_preflight_log_sha256},a.manifest_sha256)
   assert datetime.datetime.fromisoformat(resume['observationCapturedUTC'].replace('Z','+00:00'))>datetime.datetime.fromisoformat(closed['finishedUTC']),'Fresh state observation must follow terminal preflight failure'
   resume_intent=H/('kubernetes-maintenance-receipts/89c1dc34de834eb6863a4cc570f71442-transfer-resume-after-'+closed['previousRunID']+'.json')
  if all(addon_values):
   addon=resume_module['validate_closed_kubeadm_addon_preflight']({'path':str(a.closed_kubeadm_addon_preflight_result),'sha256':a.closed_kubeadm_addon_preflight_result_sha256},{'path':str(a.closed_kubeadm_addon_preflight_log),'sha256':a.closed_kubeadm_addon_preflight_log_sha256},a.manifest_sha256)
   assert resume['closedKubeadmAddonPreflight']==addon
   resume_intent=H/('kubernetes-maintenance-receipts/89c1dc34de834eb6863a4cc570f71442-transfer-resume-after-addon-'+addon['previousRunID']+'.json')
  else:assert resume.get('closedKubeadmAddonPreflight') is None,'Addon proof requires its explicit failure pair'
  assert not resume_intent.exists(),'This submission already has an immutable continuation; no uncertain replay'
 for root in (F,Path('/mnt/c')):
  st=os.statvfs(root);assert st.f_bavail*st.f_frsize>=17*1024**3
 run_id=uuid.uuid4().hex
 scratch_root=H/'kubernetes-maintenance-scratch';receipts=H/'kubernetes-maintenance-receipts'
 for root in (scratch_root,receipts):
  root.mkdir(mode=0o700,exist_ok=True)
  assert root.resolve()==root and root.stat().st_uid==1000 and not root.stat().st_mode&0o077
 scratch=scratch_root/run_id;scratch.mkdir(mode=0o700)
 recovery=H/('kubernetes-recovery-'+run_id)
 ownership={'owner':'kubernetes1372-security-patch','physicalVolume':str(F),'scratch':str(scratch),'receipts':str(receipts),'recovery':str(recovery),
  'regeneration':'Run this controller with the same verified authority; apply is never an automatic retry',
  'lastConsumer':'Ansible process and exited multiprocessing children','protected':'Manifest, raw original binaries, native staging evidence, recovery records and result receipts',
  'scratchDisposition':'Defer only this invocation temporary files to terminal ownership-bound full Linux/Windows reconciliation after overall three-host success; never retry older failed retainedPath targets'}
 with (receipts/(run_id+'-ownership.json')).open('x') as out:json.dump(ownership,out,indent=2)
 fd0=os.open(scratch,os.O_RDONLY|os.O_DIRECTORY);fd=fcntl.fcntl(fd0,fcntl.F_DUPFD,200);os.close(fd0);os.set_inheritable(fd,True)
 alias='/proc/'+str(os.getpid())+'/fd/'+str(fd);assert Path(alias).resolve()==scratch
 repo=Path(__file__).resolve().parents[2];ansible=repo/'k8s-rewrite/ansible-playbook'
 os.environ.update(PYTHONDONTWRITEBYTECODE='1',ANSIBLE_CONFIG=str(ansible/'ansible.cfg'),ANSIBLE_ROLES_PATH=str(ansible/'roles'),ANSIBLE_HOME=str(scratch/'home'),ANSIBLE_LOCAL_TEMP=str(scratch/'local'),ANSIBLE_REMOTE_TEMP=str(scratch/'remote'),TMPDIR=alias,TMP=alias,TEMP=alias,ANSIBLE_SSH_CONTROL_PATH=alias+'/ssh-%%C',ANSIBLE_SSH_ARGS='-o ControlMaster=no -o ControlPersist=no')
 settings={'kubernetes_security_patch_apply':a.apply,'kubernetes_security_patch_manifest':str(a.manifest),'kubernetes_security_patch_manifest_sha256':a.manifest_sha256,'kubernetes_security_patch_receipt_dir':str(recovery),'ansible_ssh_private_key_file':'/home/brajam/.ssh/id_ed25519','ansible_ssh_common_args':'-o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/home/brajam/.ssh/known_hosts'}
 if resume:
  settings.update(kubernetes_security_patch_resume_run_id=run_id,kubernetes_security_patch_resume_kubeadm_with_transfer_proof=str(a.resume_kubeadm_with_transfer_proof),kubernetes_security_patch_resume_kubeadm_with_transfer_proof_sha256=a.resume_kubeadm_with_transfer_proof_sha256)
 result={'closedKubeadmAddonPreflightQualification':addon,'closedPreflightQualification':closed,'resumeQualification':resume,'startedUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'settings':settings,'sourceSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'exitCode':None}
 try:
  if resume:
   with resume_intent.open('x') as intent_out:
    submission={'runID':run_id,'proofSHA256':a.resume_kubeadm_with_transfer_proof_sha256,'authoritySHA256':a.manifest_sha256,'failureRun':resume['failureRun'],'submitted':True,'noUncertainReplay':True}
    if addon:submission.update(parentIntent=addon['previousIntent'],closedKubeadmAddonPreflight=addon)
    if closed:submission.update(parentIntent=closed['previousIntent'],closedPreflight=closed)
    json.dump(submission,intent_out,indent=2);intent_out.flush();os.fsync(intent_out.fileno())
   intent_parent=os.open(resume_intent.parent,os.O_RDONLY|os.O_DIRECTORY)
   try:os.fsync(intent_parent)
   finally:os.close(intent_parent)
  print('KUBERNETES_PATCH_INVOCATION '+json.dumps({'runID':run_id,'authoritySHA256':a.manifest_sha256,'resumeProofSHA256':a.resume_kubeadm_with_transfer_proof_sha256}),flush=True)
  os.environ['BRANCONET_MIGRATION_SUDO_PASSWORD']=password
  from ansible.cli.playbook import PlaybookCLI
  cli=PlaybookCLI(['ansible-playbook','-i',str(ansible/'inventory/production.ini'),str(ansible/'playbooks/kubernetes-security-patch.yml'),'-e',json.dumps(settings)])
  cli.ask_passwords=lambda:(None,password)
  result['exitCode']=cli.run();assert result['exitCode']==0
 finally:
  os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD',None);password=None
  from multiprocessing.util import _exit_function
  _exit_function();os.close(fd)
  result['finishedUTC']=datetime.datetime.now(datetime.timezone.utc).isoformat()
  # No non-root reference sweep or deletion here. Multiprocessing children have
  # exited above; the separate privileged full-Linux/Windows reconciler decides
  # whether this exact terminal-owned empty tree is eligible after final success.
  result['scratchCleanup']={'pendingReconciliationPath':str(scratch),'reason':'Deferred to full Linux-reference and Windows-exclusive-handle reconciliation after overall three-host native success','multiprocessingExitCompleted':True,'deletionAttempted':False}
  with (receipts/(run_id+'-result.json')).open('x') as out:json.dump(result,out,indent=2)

if __name__=='__main__':main()
