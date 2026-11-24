#!/usr/bin/env python3
"""Run the scoped DHCP play with controller output confined to the owned H run."""
import argparse
import datetime
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['syntax', 'stage', 'activate', 'verify', 'rollback'])
parser.add_argument('--router-disabled', action='store_true',
                    help='Operator has read back router DHCP disabled before activation')
args = parser.parse_args()
if args.action == 'activate' and not args.router_disabled:
    parser.error('Read back router DHCP disabled before using --router-disabled')

repo = Path(__file__).resolve().parents[2]
ansible = repo / 'k8s-rewrite/ansible-playbook'
if args.action == 'activate':
    router = json.loads(subprocess.check_output([
        sys.executable, '-B', str(repo / 'scripts/migration/xr500-dhcp-setting.py'), 'read']))
    if router['enabled']:
        raise SystemExit('Router DHCP still enabled; replacement activation refused')
root = Path('/mnt/h/AgentArtifacts/projects/branconet/runs/branconet-wsl-stage-20261113T215208Z')
if not root.is_dir() or root.resolve() != root:
    raise SystemExit('Existing H output root is unavailable or redirected')
temp = root / 'temp/SWARM-dhcp'
logs = root / 'logs'
temp.mkdir(parents=True, exist_ok=True)
logs.mkdir(exist_ok=True)
log = logs / ('SWARM-dhcp-' + args.action + '.log')
env = dict(os.environ, ANSIBLE_CONFIG=str(ansible / 'ansible.cfg'),
           ANSIBLE_LOCAL_TEMP=str(temp), TMPDIR=str(temp), TEMP=str(temp), TMP=str(temp),
           ANSIBLE_SSH_ARGS='-o ControlMaster=no -o ControlPersist=no',
           ANSIBLE_NOCOLOR='1', PYTHONDONTWRITEBYTECODE='1')
if args.action != 'syntax':
    env['BRANCONET_MIGRATION_SUDO_PASSWORD'] = getpass.getpass('Sudo password (hidden): ')

# NTFS cannot hold Unix filesystem sockets. Use Python's supported abstract
# Unix address form for Ansible's controller RPC, without filesystem scratch.
bootstrap = """import multiprocessing.connection as c,secrets
original=c.arbitrary_address
c.arbitrary_address=lambda family: ('\\0branconet-dhcp-'+secrets.token_hex(16)) if family=='AF_UNIX' else original(family)
from ansible.cli.playbook import main
main()
"""
python = '/home/brajam/.local/share/branconet-migration/venv/bin/python'
variables = {'dhcp_lan_action': 'stage' if args.action == 'syntax' else args.action,
             'dhcp_lan_router_disabled': args.router_disabled}
command = [python, '-B', '-c', bootstrap, 'playbooks/lan-dhcp-handoff.yml',
           '--limit', 'workernode2', '-e', json.dumps(variables)]
if args.action == 'syntax':
    command.append('--syntax-check')
try:
    log_start = log.stat().st_size if log.exists() else 0
    with log.open('a') as output:
        output.write('\nRun ' + datetime.datetime.now(datetime.timezone.utc).isoformat() + '\n')
        output.flush()
        result = subprocess.run(command, cwd=ansible, env=env,
                                stdout=output, stderr=subprocess.STDOUT)
    with log.open('rb') as output:
        output.seek(log_start)
        print(output.read().decode(errors='replace')[-9000:])
    print(json.dumps({'action': args.action, 'rc': result.returncode, 'log': str(log)}))
    sys.exit(result.returncode)
finally:
    env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
