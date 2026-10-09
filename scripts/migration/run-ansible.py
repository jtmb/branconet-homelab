#!/usr/bin/env python3
"""Run staged Ansible with verified backup gate and credentials on stdin only."""
import argparse
import datetime
import json
import os
import pathlib
import subprocess
import sys

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tags',default='bootstrap,kubernetes,network,dns')
    parser.add_argument('--syntax-check',action='store_true')
    parser.add_argument('--recovery-bootstrap',action='store_true',help='Keep public ports, native DNS dependency and Flux activation gated during recovery')
    args=parser.parse_args()
    repo=pathlib.Path(__file__).resolve().parents[2]
    ansible=repo/'k8s-rewrite/ansible-playbook'
    runtime=pathlib.Path.home()/'.local/share/branconet-migration'
    env={**os.environ,'ANSIBLE_CONFIG':str(ansible/'ansible.cfg'),'ANSIBLE_NOCOLOR':'1'}
    command=[str(runtime/'venv/bin/ansible-playbook'),'playbooks/site.yml','--tags',args.tags]
    if args.recovery_bootstrap:
        command+=['--extra-vars',json.dumps({'migration_network_cutover_complete':False,'migration_native_dns_enabled':False,'flux_activation_enabled':False})]
    if args.syntax_check:
        raise SystemExit(subprocess.run([*command,'--syntax-check'],cwd=ansible,env=env).returncode)
    request=json.load(sys.stdin)
    env['BRANCONET_MIGRATION_SUDO_PASSWORD']=request['sudo_password']
    backups=json.loads((repo/'evidence/data-backups.json').read_text())
    if not backups.get('completed_at') or {a.get('host') for a in backups.get('archives',[])}!={'192.168.0.4','192.168.0.5','192.168.0.6'}:
        raise SystemExit('Provisioning blocked: completed data archives covering all three hosts required')
    if not all(a.get('ok') and a.get('authenticated_decryption_verified') for a in backups['archives']):
        raise SystemExit('Provisioning blocked: authenticated data recovery required')
    if backups.get('recovery_strategy'):
        bricks={a.get('host') for a in backups['archives'] if a.get('kind')=='gluster-brick'}
        if bricks!={'192.168.0.4','192.168.0.5','192.168.0.6'} or not any(a.get('kind')=='gluster-logical' for a in backups['archives']) or not any(a.get('kind')=='cold-primary' for a in backups['archives']):
            raise SystemExit('Provisioning blocked: complete Gluster recovery coverage required')
    restore=backups.get('restoration') or {}
    if restore.get('swarm')!=0 or any(c!=0 for c in restore.get('standalone',{}).values()):
        raise SystemExit('Provisioning blocked: source restoration must succeed')
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    log=runtime/('ansible-'+args.tags.replace(',','-')+'.log')
    fd=os.open(log,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    os.chmod(log,0o600)
    with os.fdopen(fd,'w') as output:
        process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,text=True,cwd=ansible,env=env)
        process.wait()
    result=process
    record={'started_at':started,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tags':args.tags,'exit_code':result.returncode,'operator_log':str(log)}
    path=repo/'evidence'/('ansible-'+args.tags.replace(',','-')+'.json')
    path.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record),flush=True)
    raise SystemExit(result.returncode)

if __name__=='__main__':main()
