"""Run the finite kernel playbook in the existing F-backed task root.

See docs/KERNEL202-MAINTENANCE.md. Operator input is consumed before child
processes; only a short-lived Ansible environment carries the existing sudo
credential. Public settings and actual results are retained, never the input.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028'

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('mode',choices=['refresh','preflight','apply','complete-master'])
 p.add_argument('--manifest',type=Path);p.add_argument('--manifest-sha256')
 a=p.parse_args();assert F.is_mount() and H.is_dir() and os.geteuid()==1000
 os.umask(0o077)
 raw=sys.stdin.buffer.readline(130).removesuffix(b'\n')
 assert 0<len(raw)<=128 and not any(x in raw for x in (b'\n',b'\r',b'\0'))
 password=raw.decode();raw=None
 for root in (F,Path('/mnt/c')):
  st=os.statvfs(root);assert st.f_bavail*st.f_frsize>=17*1024**3
 run_id=uuid.uuid4().hex
 scratch=H/'kernel-maintenance-scratch';scratch.mkdir(mode=0o700,exist_ok=True)
 assert scratch.resolve()==scratch and scratch.stat().st_uid==1000 and not scratch.stat().st_mode&0o077
 fd0=os.open(scratch,os.O_RDONLY|os.O_DIRECTORY);fd=fcntl.fcntl(fd0,fcntl.F_DUPFD,200);os.close(fd0);os.set_inheritable(fd,True)
 alias='/proc/'+str(os.getpid())+'/fd/'+str(fd);assert Path(alias).resolve()==scratch
 repo=Path(__file__).resolve().parents[2];ansible=repo/'k8s-rewrite/ansible-playbook'
 os.environ.update(PYTHONDONTWRITEBYTECODE='1',ANSIBLE_CONFIG=str(ansible/'ansible.cfg'),ANSIBLE_ROLES_PATH=str(ansible/'roles'),ANSIBLE_HOME=str(scratch/'home'),ANSIBLE_LOCAL_TEMP=str(scratch/'local'),ANSIBLE_REMOTE_TEMP=str(scratch/'remote'),TMPDIR=alias,TMP=alias,TEMP=alias,ANSIBLE_SSH_CONTROL_PATH=alias+'/ssh-%%C',ANSIBLE_SSH_ARGS='-o ControlMaster=no -o ControlPersist=no')
 settings={'kernel_maintenance_mode':'apply' if a.mode=='complete-master' else a.mode,'ansible_ssh_private_key_file':'/home/brajam/.ssh/id_ed25519','ansible_ssh_common_args':'-o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/home/brajam/.ssh/known_hosts'}
 if a.mode in ['apply','complete-master']:
  assert a.manifest and a.manifest.is_file() and a.manifest.resolve()==a.manifest and H in a.manifest.parents
  assert hashlib.sha256(a.manifest.read_bytes()).hexdigest()==a.manifest_sha256
  settings.update(kernel_maintenance_apply=True,kernel_maintenance_reboot=True,security_maintenance_backup_verified=True,security_maintenance_backup_reference=str(a.manifest),security_maintenance_checkpoint_sha256=a.manifest_sha256,security_maintenance_recovery_receipt_dir=str(H/('kernel-recovery-'+run_id)))
 else:assert a.manifest is None and a.manifest_sha256 is None
 result={'mode':a.mode,'startedUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'settings':settings,'sourceSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'exitCode':None}
 try:
  os.environ['BRANCONET_MIGRATION_SUDO_PASSWORD']=password
  from ansible.cli.playbook import PlaybookCLI
  playbook='kernel-master-completion.yml' if a.mode=='complete-master' else 'kernel-security-maintenance.yml'
  cli=PlaybookCLI(['ansible-playbook','-i',str(ansible/'inventory/production.ini'),str(ansible/'playbooks'/playbook),'-e',json.dumps(settings)])
  cli.ask_passwords=lambda:(None,password)
  result['exitCode']=cli.run();assert result['exitCode']==0
 finally:
  os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD',None);password=None
  from multiprocessing.util import _exit_function
  _exit_function();os.close(fd)
  result['finishedUTC']=datetime.datetime.now(datetime.timezone.utc).isoformat()
  with (H/('kernel-maintenance-'+a.mode+'-'+run_id+'.json')).open('x') as out:json.dump(result,out,indent=2)

if __name__=='__main__':main()
