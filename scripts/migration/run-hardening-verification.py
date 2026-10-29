"""Run the maintained TLS verifier through Ansible in the existing F root.

An fd path keeps AF_UNIX socket names short without moving temporary output.
No privilege input, trust installation or workload write is used.
The explicit final-run opt-in reconciles only the public native redirect key.
"""
import fcntl
import argparse
import json
import os
from pathlib import Path
import sys
import subprocess
import uuid

F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028'

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--flare-least-privilege',action='store_true',help='After TLS checks run the full cluster verifier with explicit Flare security checks')
 parser.add_argument('--revision');parser.add_argument('--receipt',type=Path)
 args=parser.parse_args()
 if args.flare_least_privilege:
  if not (args.revision and args.receipt):parser.error('--revision and --receipt are required with --flare-least-privilege')
 elif args.revision or args.receipt:parser.error('--revision/--receipt require --flare-least-privilege')
 assert os.geteuid()==1000 and F.is_mount() and H.is_dir()
 os.umask(0o077)
 repo=Path(__file__).resolve().parents[2];ansible=repo/'k8s-rewrite/ansible-playbook'
 scratch=H/'ansible-verification-scratch';scratch.mkdir(mode=0o700,exist_ok=True)
 assert scratch.resolve()==scratch and scratch.stat().st_uid==1000 and not scratch.stat().st_mode&0o077
 fd0=os.open(scratch,os.O_RDONLY|os.O_DIRECTORY);fd=fcntl.fcntl(fd0,fcntl.F_DUPFD,200);os.close(fd0);os.set_inheritable(fd,True)
 alias='/proc/'+str(os.getpid())+'/fd/'+str(fd)
 assert Path(alias).resolve()==scratch
 os.environ.update(PYTHONDONTWRITEBYTECODE='1',ANSIBLE_CONFIG=str(ansible/'ansible.cfg'),ANSIBLE_ROLES_PATH=str(ansible/'roles'),ANSIBLE_HOME=str(scratch/'home'),ANSIBLE_LOCAL_TEMP=str(scratch/'local'),ANSIBLE_REMOTE_TEMP=str(scratch/'remote'),TMPDIR=alias,TMP=alias,TEMP=alias,ANSIBLE_SSH_CONTROL_PATH=alias+'/ssh-%%C',ANSIBLE_SSH_ARGS='-o ControlMaster=no -o ControlPersist=no')
 os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD',None)
 from ansible.cli.playbook import PlaybookCLI
 settings={'lan_tls_output_dir':str(H/'tls-verification'),'lan_tls_verify_bortus_https':True,'lan_tls_verify_bortus_http_redirect':True,'lan_tls_apply_bortus_http_redirect':True,'lan_tls_renew_missing_leaf_usage':True,'lan_tls_apply':False,'lan_tls_install_windows_trust':False}
 cli=PlaybookCLI(['ansible-playbook','-i',str(ansible/'inventory/production.ini'),str(ansible/'playbooks/lan-tls.yml'),'-e',json.dumps(settings)])
 result={}
 try:
  result['exitCode']=cli.run()
  assert result['exitCode']==0
  if args.flare_least_privilege:
   check=subprocess.run([sys.executable,'-B',str(repo/'scripts/migration/verify-cluster-hardening.py'),'--revision',args.revision,'--receipt',str(args.receipt),'--flare-least-privilege'],check=False)
   result['flareLeastPrivilegeExitCode']=check.returncode
   assert check.returncode==0
 finally:
  from multiprocessing.util import _exit_function
  _exit_function();os.close(fd)
  with (H/('tls-ansible-fd-result-'+uuid.uuid4().hex+'.json')).open('x') as out:json.dump(result,out,indent=2)

if __name__=='__main__':main()
