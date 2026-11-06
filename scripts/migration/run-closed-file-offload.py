"""Finite closed-file Ansible inventory/retirement with RAM-only stdin credentials."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028'
REPOSITORY=Path('/mnt/c/Users/james/.codex/worktrees/cluster-headroom-security-tls/kubernetes migration')
CORE_SHA='0e0be0645a4f4077a3bbdad577db05d6498874954c33ec1c98291a3fd8670bc4'
SOURCE_PINS={'k8s-rewrite/ansible-playbook/roles/closed_file_offload/files/offload.py': '4442d412cc2d07728f90f7b85c364c444608b28c24caa6c97dd0e7b20a8da278', 'k8s-rewrite/ansible-playbook/roles/closed_file_offload/files/record.py': 'b6da9960d4470142213a35631a822254b233301436836887d92be218bdbd44c3', 'k8s-rewrite/ansible-playbook/roles/closed_file_offload/tasks/main.yml': 'a0a188f8968e4b3cdbd0bac1b0dbc01af49d76def26d899c0660e39c5afbbacb', 'k8s-rewrite/ansible-playbook/roles/closed_file_offload/tasks/retire-one.yml': '94743acce522afa9be828b121d2a41a26157fb3b1ae3ea2abd4c66f081ff9aa9', 'k8s-rewrite/ansible-playbook/roles/closed_file_offload/defaults/main.yml': 'e22e6e349652059f95e7d3c87d25040324754abe0d6f4f085b8a62e04288f0d7', 'k8s-rewrite/ansible-playbook/playbooks/closed-file-offload.yml': '81f71922acbec0d581a33356a2d167646c47535b495b23cd895abcc083b442de', 'k8s-rewrite/ansible-playbook/roles/retired_master_build_tools/files/retire.py': '09fbe87185c078f7e31e3501e502ae4600a00da77b892b940d09c3903250a92c'}
PS='/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):
 with path.open('x') as stream:json.dump(value,stream,indent=2);stream.flush();os.fsync(stream.fileno())

def check_lock(proof):
 assert proof['scope']=='closed-file-offload' and proof['nasReadLocksHeld'] and proof['independentRestoreVerified']
 assert 0<=time.time()-proof['nasVerificationEpoch']<1200
 endpoint=proof['lockEndpoint'];assert endpoint['host']=='127.0.0.1' and 1024<=endpoint['port']<=65535
 assert re.fullmatch('[0-9a-f]{32}',proof['token']) and isinstance(proof['nativePID'],int) and proof['nativePID']>0
 nonce=uuid.uuid4().hex
 request=json.dumps({'token':proof['token'],'nonce':nonce},separators=(',',':'))
 # Native Windows loopback reaches the Windows lock owner independently of WSL
 # NAT/mirrored networking. Only public proof data is passed to this client.
 code="$ErrorActionPreference='Stop'; $p=Get-Process -Id "+str(proof['nativePID'])+"; $c=[Net.Sockets.TcpClient]::new(); $c.Connect('127.0.0.1',"+str(endpoint['port'])+"); $s=$c.GetStream(); $s.ReadTimeout=5000; $s.WriteTimeout=5000; $w=[IO.StreamWriter]::new($s); $w.AutoFlush=$true; $w.WriteLine('"+request+"'); $b=New-Object byte[] 4096; $m=[IO.MemoryStream]::new(); while(($n=$s.Read($b,0,$b.Length)) -gt 0){$m.Write($b,0,$n); if($m.Length -gt 8192){throw 'bounded response'}}; [Console]::Out.Write([Text.Encoding]::UTF8.GetString($m.ToArray())); $m.Dispose(); $c.Dispose()"
 observed=subprocess.run([PS,'-NoLogo','-NoProfile','-NonInteractive','-Command',code],capture_output=True,timeout=15)
 assert observed.returncode==0 and 0<len(observed.stdout)<=8192,'Native NAS lock owner unavailable'
 answer=json.loads(observed.stdout.decode('utf-8-sig'))
 assert answer['nonce']==nonce and answer['nativePID']==proof['nativePID'] and answer['token']==proof['token'] and answer['active'] is True
 assert answer['identities']==[item['nativeIdentity'] for item in proof['files']]
 assert abs(time.time()-answer['epoch'])<10
 return {'nativePID':answer['nativePID'],'epoch':answer['epoch'],'identities':answer['identities'],'socketChallengeVerified':True}

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--node',choices=['masternode','workernode2'],default='workernode2')
 parser.add_argument('--proof',type=Path);parser.add_argument('--file-profile',type=Path)
 parser.add_argument('--remote-helper',type=Path,required=True);parser.add_argument('--safety-source',type=Path,required=True)
 parser.add_argument('--reviewed-controller-transition',type=Path,required=True);parser.add_argument('--reviewed-controller-transition-sha256',required=True)
 parser.add_argument('--fresh-recovery-checkpoint',type=Path,required=True);parser.add_argument('--fresh-recovery-checkpoint-sha256',required=True)
 parser.add_argument('--apply',action='store_true');a=parser.parse_args()
 password=sys.stdin.buffer.readline(130).removesuffix(b'\n')
 assert 0<len(password)<=128 and not any(x in password for x in (b'\n',b'\r',b'\0'))
 assert sys.version_info[:2]==(3,12),'Invoke with the existing venv Python 3.12; no subprocess credential handoff'
 assert os.getuid()==1000 and F.is_mount();os.umask(0o077)
 assert subprocess.check_output(['findmnt','-n','-o','UUID','--target',str(F)],text=True).strip()=='3c792469-ea0e-4a2c-98e8-1185b141607b'
 run=H/'closed-file-offload'/a.node
 assert run.resolve()==run and run.is_dir()
 for path in (F,Path('/mnt/c')):
  space=os.statvfs(path);assert space.f_bavail*space.f_frsize>=15*1024**3+384*1024**2
 for name,digest in SOURCE_PINS.items():assert sha(REPOSITORY/name)==digest,'Frozen operation source changed: '+name
 source=REPOSITORY/'k8s-rewrite/ansible-playbook'
 helper=source/'roles/closed_file_offload/files/offload.py';safety=source/'roles/retired_master_build_tools/files/retire.py'
 assert a.remote_helper==run/'offload-frozen.py' and a.safety_source==run/'safety-frozen.py'
 assert a.remote_helper.resolve()==a.remote_helper and a.safety_source.resolve()==a.safety_source
 assert helper.read_bytes()==a.remote_helper.read_bytes() and safety.read_bytes()==a.safety_source.read_bytes()
 retirement=bool(a.proof);assert not a.apply or retirement
 assert bool(a.file_profile)==retirement
 proof=None
 if retirement:
  assert a.file_profile==run/'profile.json' and a.proof.parent==run and a.proof.resolve()==a.proof
  assert re.fullmatch('nas-retirement-proof-[0-9a-f]{32}[.]json',a.proof.name)
  proof=json.loads(a.proof.read_text());assert proof['node']==a.node
  profile=json.loads(a.file_profile.read_text());assert profile['node']==a.node and profile['scope']=='closed-file-offload'
  assert hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',',':')).encode()).hexdigest()==proof['journalCanonicalProfileSHA256']
  phase='retirement-'+proof['token'];lock_before=check_lock(proof)
 else:phase='inventory';lock_before=None
 receipt=run/(phase+'-operator.json');returned=run/('retirement-result-'+proof['token']+'.json' if retirement else 'inventory-result.json')
 scratch=run/(phase+'-ansible-scratch')
 assert not receipt.exists() and not returned.exists() and not scratch.exists(),'Existing operation or refusal retained'
 corepath=REPOSITORY/'scripts/migration/verify-completed-core-preservation.py';assert sha(corepath)==CORE_SHA
 spec=importlib.util.spec_from_file_location('closed_file_core',corepath);core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
 transition={'path':str(a.reviewed_controller_transition),'sha256':a.reviewed_controller_transition_sha256}
 recovery={'path':str(a.fresh_recovery_checkpoint),'sha256':a.fresh_recovery_checkpoint_sha256}
 before=core.validate(REPOSITORY,transition=transition,recovery=recovery)
 ownership=run/(phase+'-ownership.json')
 assert not ownership.exists()
 save(ownership,{'owner':'closed-file-offload','node':a.node,'root':str(run),'physicalUUID':'3c792469-ea0e-4a2c-98e8-1185b141607b',
  'sourceSHA256':sha(Path(__file__)),'helperSHA256':sha(helper),'safetySHA256':sha(safety),'coreSHA256':CORE_SHA,'transition':transition,'recovery':recovery,
  'scratch':str(scratch),'receipt':str(receipt),'returned':str(returned),'peakBytes':384*1024**2,
  'regeneration':'Repeatable Ansible scratch only; original phase receipts and all failed file attempts are immutable and never replayed',
  'lastConsumer':'This single Ansible invocation; reconcile inactive scratch after its terminal outcome','protected':'NAS ciphertext/key, original profiles, per-file intents/results/refusals, recovery source and evidence',
  'before':before,'nativeLock':lock_before})
 scratch.mkdir(mode=0o700)
 descriptor=os.open(scratch,os.O_RDONLY|os.O_DIRECTORY);fd=fcntl.fcntl(descriptor,fcntl.F_DUPFD,200);os.close(descriptor);os.set_inheritable(fd,True)
 alias='/proc/'+str(os.getpid())+'/fd/'+str(fd);assert Path(alias).resolve()==scratch
 os.environ.update(PYTHONDONTWRITEBYTECODE='1',ANSIBLE_CONFIG=str(source/'ansible.cfg'),ANSIBLE_ROLES_PATH=str(source/'roles'),ANSIBLE_HOME=str(scratch/'home'),ANSIBLE_LOCAL_TEMP=str(scratch/'local'),ANSIBLE_REMOTE_TEMP=str(scratch/'remote'),TMPDIR=alias,TMP=alias,TEMP=alias,ANSIBLE_SSH_CONTROL_PATH=alias+'/ssh-%%C',ANSIBLE_SSH_ARGS='-o ControlMaster=no -o ControlPersist=no')
 from ansible.cli.playbook import PlaybookCLI
 variables={'closed_file_offload_node':a.node,'closed_file_offload_mode':'retire' if retirement else 'inventory','closed_file_offload_apply':a.apply,
  'closed_file_offload_operator_holds_nas_lock':retirement,'closed_file_offload_profile_file':str(run/'profile.json'),
  'closed_file_offload_proof_file':str(a.proof) if retirement else '', 'closed_file_offload_result_file':str(returned),
  'ansible_ssh_private_key_file':'/home/brajam/.ssh/id_ed25519','ansible_ssh_common_args':'-o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/home/brajam/.ssh/known_hosts'}
 cli=PlaybookCLI(['ansible-playbook','-i',str(source/'inventory/production.ini'),str(source/'playbooks/closed-file-offload.yml'),'-e',json.dumps(variables)])
 cli.ask_passwords=lambda:(None,password.decode())
 result={'status':'started','sourceSHA256':sha(Path(__file__)),'ownershipSHA256':sha(ownership),'scratchRequiresInactiveReconciliation':str(scratch)}
 try:
  if retirement:result['immediatePreAnsibleLock']=check_lock(proof)
  assert sha(corepath)==CORE_SHA
  for name,digest in SOURCE_PINS.items():assert sha(REPOSITORY/name)==digest
  result['exitCode']=cli.run()
  for name,digest in SOURCE_PINS.items():assert sha(REPOSITORY/name)==digest
  result['after']=core.validate(REPOSITORY,transition=transition,recovery=recovery)
  if retirement:result['postAnsibleLock']=check_lock(proof)
  if result['exitCode']==0 and not retirement:
   observation=json.loads(returned.read_text());assert observation['rc']==0
   profile=json.loads(observation['stdout']);assert profile['node']==a.node and profile['schema']==1 and profile['scope']=='closed-file-offload'
   save(run/'profile.json',profile);result['profileSHA256']=sha(run/'profile.json')
  result['status']='completed' if result['exitCode']==0 else 'failed'
 except Exception as error:
  result.update(status='failed',errorCategory=type(error).__name__)
  raise
 finally:
  password=None
  from multiprocessing.util import _exit_function
  _exit_function();os.close(fd);save(receipt,result)
 raise SystemExit(result['exitCode'])

if __name__=='__main__':main()
