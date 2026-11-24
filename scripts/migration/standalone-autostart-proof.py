#!/usr/bin/env python3
"""Read sudo password from stdin; audit retained standalone containers and startup metadata.

Never print container environment, raw startup commands, or credentials. No mutations.
No actual reboot or guarantee against arbitrary external startup commands is claimed.
"""
import concurrent.futures,json,shlex,subprocess,sys,datetime
password=sys.stdin.readline().rstrip('\r\n')
expected={'192.168.0.4':['qbittorrent','GlueTun-proton','plex-plex-1'],'192.168.0.5':['plex-plex-1'],'192.168.0.6':['ets2-server','plex-plex-1']}
remote=r'''
import hashlib,json,pathlib,re,subprocess
roots=['/etc/systemd/system','/home/james/.config/systemd/user','/root/.config/systemd/user','/etc/cron.d','/etc/cron.daily','/etc/cron.hourly','/etc/cron.weekly','/etc/cron.monthly','/var/spool/cron/crontabs','/etc/init.d']
special=['/etc/crontab','/etc/rc.local']
files=set()
for root in roots:
 p=pathlib.Path(root)
 if p.exists():
  for f in p.rglob('*'):
   if f.is_file() and f.stat().st_size<262144:files.add(f)
for f in special:
 p=pathlib.Path(f)
 if p.is_file():files.add(p)
patterns={'docker_start':r'\bdocker\s+(?:container\s+)?(?:start|restart|run)\b','compose_up':r'\b(?:docker[- ]compose|docker\s+compose)\b.*\b(?:up|start|restart)\b','standalone_name':r'qbittorrent|GlueTun-proton|plex-plex-1|ets2-server','generic_docker_reference':r'\bdocker\b|docker-compose','startup_wrapper':r'(?m)^\s*(?:ExecStart|ExecStartPre|ExecStartPost)\s*=.*(?:/home/|/opt/|/usr/local/|\.sh\b)'}
matches=[]
for f in sorted(files):
 try:data=f.read_bytes();content=data.decode('utf8','replace')
 except OSError:continue
 kinds=[name for name,pattern in patterns.items() if re.search(pattern,content,re.I)]
 if kinds:matches.append({'path':str(f),'resolved_path':str(f.resolve()),'sha256':hashlib.sha256(data).hexdigest(),'match_categories':kinds})
containers=[]
for name in names:
 result=subprocess.run(['docker','inspect',name],capture_output=True,check=True)
 container=json.loads(result.stdout)[0]
 if (container.get('Config',{}).get('Labels') or {}).get('com.docker.swarm.service.name'):raise RuntimeError('Expected standalone container is a Swarm task')
 containers.append({'name':name,'id':container['Id'],'running':container['State']['Running'],'status':container['State']['Status'],'restart_policy':container['HostConfig']['RestartPolicy']})
cron_entries=[]
for p in files:
 if '/cron' not in str(p):continue
 try:lines=p.read_text().splitlines()
 except (OSError,UnicodeError):continue
 for number,line in enumerate(lines,1):
  if line.lstrip().startswith('#') or 'docker' not in line.lower():continue
  cron_entries.append({'path':str(p),'line':number,'sha256':hashlib.sha256(line.encode()).hexdigest(),'docker_operations':re.findall(r'\bdocker(?:\s+container|\s+system|\s+volume|\s+image|\s+service|\s+stack)?\s+[a-z-]+|docker-compose\s+[a-z-]+',line,re.I),'reboot_trigger':line.lstrip().startswith('@reboot')})
enabled=subprocess.run(['systemctl','list-unit-files','--state=enabled','--no-legend','--no-pager'],capture_output=True,text=True,check=True).stdout
print(json.dumps({'containers':containers,'active_docker_cron_entries':cron_entries,'files_scanned':len(files),'matches':matches,'enabled_units':[line.split()[0] for line in enabled.splitlines() if line.strip()],'changes_performed':False}))
'''
def audit(host):
 r=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@'+host,'sudo -S -p "" python3 -c '+shlex.quote('names='+repr(expected[host])+'\n'+remote)],input=(password+'\n').encode(),capture_output=True,timeout=40)
 if r.returncode:raise RuntimeError('Startup audit failed on '+host+'; private diagnostics withheld')
 return {'host':host,**json.loads(r.stdout)}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:report=list(pool.map(audit,['192.168.0.4','192.168.0.5','192.168.0.6']))
evidence={'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'nodes':report,'source_changes_performed':False,'scope':{'actual_reboot_performed':False,'arbitrary_external_start_commands_excluded':False,'startup_files':'Host systemd overrides/enabled symlinks; james/root user systemd; cron; init.d; rc.local','docker_policy_reference':'https://docs.docker.com/engine/containers/start-containers-automatically/'}}
import pathlib
path=pathlib.Path('evidence/standalone-autostart-proof.json')
path.write_text(json.dumps(evidence,indent=2)+'\n')
print(json.dumps({'evidence':str(path),'nodes':len(report),'containers':sum(len(n['containers']) for n in report),'all_stopped':all(not c['running'] for n in report for c in n['containers']),'always_restart_policies':sum(c['restart_policy']['Name']=='always' for n in report for c in n['containers']),'active_docker_cron_entries':sum(len(n['active_docker_cron_entries']) for n in report),'source_changes_performed':False}))
