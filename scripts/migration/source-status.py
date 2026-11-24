#!/usr/bin/env python3
"""Record source readiness and narrowly filtered Pi-hole errors, never env values."""
import concurrent.futures
import datetime
import json
import pathlib
import subprocess

REMOTE=r'''
import json,subprocess,re
out={'services':[],'standalone':[],'pihole_errors':[]}
out['pihole_health']=[]
r=subprocess.run(['docker','service','ls','--format','{{json .}}'],capture_output=True,text=True)
for line in r.stdout.splitlines():
  s=json.loads(line);out['services'].append({'name':s['Name'],'replicas':s['Replicas']})
ids=subprocess.check_output(['docker','ps','-aq'],text=True).split()
cs=json.loads(subprocess.check_output(['docker','inspect',*ids],text=True)) if ids else []
for c in cs:
  labels=c['Config'].get('Labels') or {};state=c['State']
  if not labels.get('com.docker.swarm.service.name'):out['standalone'].append({'name':c['Name'].lstrip('/'),'status':state['Status'],'health':(state.get('Health') or {}).get('Status')})
  if labels.get('com.docker.swarm.service.name')=='pi_pihole':
    health=state.get('Health') or {}
    out['pihole_health'].append({'status':state['Status'],'health':health.get('Status'),'oom_killed':state.get('OOMKilled'),'exit_codes':[x.get('ExitCode') for x in health.get('Log',[])]})
    r=subprocess.run(['docker','logs','--tail','120',c['Id']],capture_output=True,text=True)
    safe=[l for l in (r.stdout+'\n'+r.stderr).splitlines() if re.search(r'error|warn|failed|fatal|denied',l,re.I) and not re.search(r'password|token|secret|authorization|api.?key|key=',l,re.I)]
    out['pihole_errors']+=safe[-12:]
if any(s['name']=='pi_pihole' and not s['replicas'].startswith('1/1') for s in out['services']):
  r=subprocess.run(['docker','service','logs','--tail','80','pi_pihole'],capture_output=True,text=True,timeout=15)
  safe=[l for l in (r.stdout+'\n'+r.stderr).splitlines() if re.search(r'error|warn|failed|fatal|denied|FTL|DNS|gravity|sqlite|database|health|refused|timed out|port',l,re.I) and not re.search(r'password|token|secret|authorization|api.?key|key=',l,re.I)]
  out['pihole_errors']+=safe[-20:]
print(json.dumps(out))
'''

def main():
 def get(host):
  r=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002',f'james@{host}','python3','-'],input=REMOTE,capture_output=True,text=True,timeout=30)
  if r.returncode:raise RuntimeError('Source readiness inspection failed on '+host)
  return host,json.loads(r.stdout)
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:report={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'nodes':dict(pool.map(get,['192.168.0.4','192.168.0.5','192.168.0.6']))}
 path=pathlib.Path(__file__).resolve().parents[2]/'evidence/source-readiness.json';path.write_text(json.dumps(report,indent=2)+'\n')
 primary=report['nodes']['192.168.0.4']
 outstanding=[s for s in primary['services'] if s['replicas'].split()[0].split('/')[0]!=s['replicas'].split()[0].split('/')[1]]
 print(json.dumps({'evidence':str(path),'captured_at':report['captured_at'],'services':len(primary['services']),'outstanding_services':outstanding,'standalone':{h:n['standalone'] for h,n in report['nodes'].items()},'pihole_health':{h:n['pihole_health'] for h,n in report['nodes'].items()}}))

if __name__=='__main__':main()
