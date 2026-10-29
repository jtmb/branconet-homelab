"""Run existing backup playbooks before the finite kernel maintenance profile.

One existing F-backed root; credential consumed before child SSH/RPC creation.
No credential file/environment, plaintext archive or direct application write.
"""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import uuid

F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028'

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['volumes','control-plane']);p.add_argument('--prefix',default='k202-20261028');p.add_argument('--generation',choices=['kernel','concurrent-ingenium','kubernetes1372','kubernetes1372-current-ingenium'],default='kernel');a=p.parse_args()
 assert re.fullmatch('[a-z][a-z0-9-]{5,39}',a.prefix)
 assert F.is_mount() and H.is_dir() and os.geteuid()==1000
 for root in (F,Path('/mnt/c')):
  st=os.statvfs(root);assert st.f_bavail*st.f_frsize>=17*1024**3
 os.umask(0o077)
 password=None
 if a.phase=='control-plane':
  raw=sys.stdin.buffer.readline(130).removesuffix(b'\n');assert 0<len(raw)<=128 and b'\n' not in raw and b'\r' not in raw and b'\0' not in raw
  password=raw.decode();raw=None
 repo=Path(__file__).resolve().parents[2];ansible=repo/'k8s-rewrite/ansible-playbook'
 scratch=H/'kernel-checkpoint-scratch';scratch.mkdir(mode=0o700,exist_ok=True)
 assert scratch.resolve()==scratch and scratch.stat().st_uid==1000 and not scratch.stat().st_mode&0o077
 fd0=os.open(scratch,os.O_RDONLY|os.O_DIRECTORY);fd=fcntl.fcntl(fd0,fcntl.F_DUPFD,200);os.close(fd0);os.set_inheritable(fd,True)
 alias='/proc/'+str(os.getpid())+'/fd/'+str(fd);assert Path(alias).resolve()==scratch
 os.environ.update(PYTHONDONTWRITEBYTECODE='1',ANSIBLE_CONFIG=str(ansible/'ansible.cfg'),ANSIBLE_ROLES_PATH=str(ansible/'roles'),ANSIBLE_ACTION_PLUGINS=str(ansible/'action_plugins'),ANSIBLE_HOME=str(scratch/'home'),ANSIBLE_LOCAL_TEMP=str(scratch/'local'),ANSIBLE_REMOTE_TEMP=str(scratch/'remote'),TMPDIR=alias,TMP=alias,TEMP=alias,ANSIBLE_SSH_CONTROL_PATH=alias+'/ssh-%%C',ANSIBLE_SSH_ARGS='-o ControlMaster=no -o ControlPersist=no')
 for name in ('BRANCONET_MIGRATION_SUDO_PASSWORD','ANSIBLE_BECOME_PASSWORD','BAZARR_PRELOAD_SUDO_PASSWORD'):os.environ.pop(name,None)
 from ansible.cli.playbook import PlaybookCLI
 if a.phase=='volumes':
  assert a.generation=='kernel'
  receipt=H/'kernel-active-volume-checkpoint.json';assert not receipt.exists()
  settings={'storage_checkpoint_apply':True,'storage_checkpoint_prefix':a.prefix,'storage_checkpoint_receipt_path':str(receipt),
   'longhorn_backup_target':'cifs://192.168.0.8/container_backups/k8s-migration-20261009/longhorn?cifsOptions=vers=3.1.1,soft'}
  playbook='storage-checkpoint.yml'
 else:
  output=H/(a.generation+'-control-plane-backup');assert not output.exists()
  settings=json.loads((F/'platform-upstream-review-20261027/flux-control-plane-backup-settings.json').read_text())
  settings.update(control_plane_backup_output_dir=str(output),control_plane_backup_run_id=uuid.uuid4().hex)
  playbook='control-plane-backup.yml'
 settings.update(ansible_ssh_private_key_file='/home/brajam/.ssh/id_ed25519',ansible_ssh_common_args='-o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/home/brajam/.ssh/known_hosts')
 cli=PlaybookCLI(['ansible-playbook','-i',str(ansible/'inventory/production.ini'),str(ansible/'playbooks'/playbook),'-e',json.dumps(settings)])
 if password is not None:cli.ask_passwords=lambda:(None,password)
 result={'phase':a.phase,'startedUTC':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  result['exitCode']=cli.run();assert result['exitCode']==0
 finally:
  password=None
  from multiprocessing.util import _exit_function
  _exit_function();os.close(fd)
  with (H/('kernel-checkpoint-'+a.phase+'-'+uuid.uuid4().hex+'.json')).open('x') as out:json.dump(result,out,indent=2)

if __name__=='__main__':main()
