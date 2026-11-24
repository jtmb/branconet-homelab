#!/usr/bin/env python3
"""Read-only privileged Gluster diagnostics; credentials arrive over stdin."""
import concurrent.futures
import datetime
import json
import pathlib
import subprocess
import sys

ROOT_SCRIPT=r'''
import json,pathlib,subprocess
out={}
out['anonymous_source_paths']=[]
for path in ANONYMOUS_PATHS:
  p=pathlib.Path(path)
  item={'path':path,'exists':p.exists()}
  if p.exists():item['entries']=len(list(p.iterdir()))
  out['anonymous_source_paths'].append(item)
for suffix in [('heal','staging-gfs','info','summary'),('heal','staging-gfs','info','split-brain'),('heal','staging-gfs','info')]:
  result=subprocess.run(['gluster','volume',*suffix],capture_output=True,text=True,timeout=60)
  out[' '.join(suffix)]={'exit_code':result.returncode,'output':result.stdout,'diagnostic':result.stderr[-1000:]}
paths=['jackett/Jackett/Indexers/eztv.json','jackett/Jackett/Indexers/1337x.json.bak','plex/config/Library/Application Support/Plex Media Server/Logs','pihole/gravity.db','pihole/pihole-FTL.db','pihole/setupVars.conf']
out['source_path_checks']=[]
for path in paths:
  item={'relative_path':path}
  for kind,base in [('logical','/mnt/container-program-files'),('brick','/gluster/volumes')]:
    p=pathlib.Path(base)/path
    try:
      s=p.stat();item[kind]={'exists':True,'size':s.st_size,'mtime_ns':s.st_mtime_ns,'is_directory':p.is_dir()}
    except OSError as e:item[kind]={'errno':e.errno,'error':type(e).__name__}
  out['source_path_checks'].append(item)
print(json.dumps(out))
'''

def main():
  request=json.load(sys.stdin)
  baseline=json.loads((pathlib.Path(request['evidence_output']).parent/'live-inventory.json').read_text())
  def inspect(host):
    anonymous=sorted(set(m['Source'] for c in baseline['nodes'][host]['containers'] for m in c['mounts'] if m['Type']=='volume'))
    root='ANONYMOUS_PATHS='+repr(anonymous)+'\n'+ROOT_SCRIPT
    wrapper="import subprocess,sys\nr=subprocess.run("+repr(['sudo','-S','-p','','python3','-c',root])+",input="+repr(request['sudo_password']+'\n')+",capture_output=True,text=True,timeout=180)\nif r.returncode:sys.exit(r.returncode)\nsys.stdout.write(r.stdout)\n"
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-i',str(pathlib.Path.home()/'.ssh/id_ed25519'),'-p','2002',f'james@{host}','python3','-'],input=wrapper,capture_output=True,text=True,timeout=190)
    if result.returncode:raise RuntimeError('Privileged audit failed on '+host)
    return host,json.loads(result.stdout)
  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    report={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'nodes':dict(pool.map(inspect,['192.168.0.4','192.168.0.5','192.168.0.6']))}
  path=pathlib.Path(request['evidence_output']);path.write_text(json.dumps(report,indent=2)+'\n')
  print(json.dumps({'evidence':str(path),'nodes':len(report['nodes'])}))

if __name__=='__main__':main()
