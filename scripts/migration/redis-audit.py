#!/usr/bin/env python3
"""Inspect Redis persistence metadata and WordPress cache use without values."""
import json
import pathlib
import subprocess

REMOTE=r'''
import json,pathlib,subprocess
ids=subprocess.check_output(['docker','ps','--filter','label=com.docker.swarm.service.name=wordpress_redis-db','-q'],text=True).split()
if len(ids)!=1:raise SystemExit('Redis source task not uniquely running')
c=json.loads(subprocess.check_output(['docker','inspect',ids[0]],text=True))[0]
cmd=c['Config'].get('Cmd') or []
password=cmd[cmd.index('--requirepass')+1] if '--requirepass' in cmd else None
script=('AUTH '+json.dumps(password)+'\n') if password else ''
script+='CONFIG GET save appendonly dir dbfilename\nDBSIZE\nINFO keyspace\n'
r=subprocess.run(['docker','exec','-i',ids[0],'redis-cli','--raw'],input=script,text=True,capture_output=True)
if r.returncode or 'NOAUTH' in r.stdout or 'WRONGPASS' in r.stdout:raise SystemExit('Redis authenticated metadata query failed')
lines=r.stdout.splitlines()
if password and lines and lines[0]=='OK':lines=lines[1:]
configuration=dict(zip(lines[:8:2],lines[1:8:2]))
remaining=lines[8:]
database_size=next((int(v) for v in remaining if v.isdigit()),None)
plugins=pathlib.Path('/mnt/container-program-files/wordpress/wp-app/wp-content/plugins')
cache_plugins=[p.name for p in plugins.iterdir() if 'redis' in p.name.lower()] if plugins.exists() else []
wp=pathlib.Path('/mnt/container-program-files/wordpress/wp-app/wp-config.php')
text=wp.read_text(errors='replace') if wp.exists() else ''
print(json.dumps({'host':'192.168.0.4','source':'wordpress_redis-db','mounts':[{'type':m['Type'],'source':m['Source'],'destination':m['Destination']} for m in c['Mounts']],'persistence_configuration':configuration,'current_key_count':database_size,'keyspace_metadata':[v for v in remaining if v.startswith('db')],'wordpress_redis_plugins':cache_plugins,'wordpress_redis_config_present':'WP_REDIS' in text,'historical_state_preserved':False,'original_role_acceptance_pending':True}))
'''

def main():
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','python3','-'],input=REMOTE,capture_output=True,text=True,timeout=45)
    if result.returncode:raise SystemExit('Redis metadata inspection failed')
    report=json.loads(result.stdout)
    output=pathlib.Path(__file__).resolve().parents[2]/'evidence/redis-persistence.json'
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
