#!/usr/bin/env python3
"""Private HTTP/restart checks for copied applications; full acceptance stays separate."""
import concurrent.futures
import json
import pathlib
import subprocess
import sys
import time

ROOT=pathlib.Path(__file__).resolve().parents[2]
CHECKS=[
 ('apps/mealie',9000,'/api/app/about'),
 ('media-stack/jackett',9117,'/UI/Login'),
 ('media-stack/bazarr',6767,'/'),
 ('media-stack/tautulli',8181,'/'),
 ('media-stack/radarr',7878,'/login'),
 ('media-stack/sonarr',8989,'/login'),
 ('media-stack/ytdl',8081,'/'),
 ('apps/xteve',34400,'/web/'),
 ('media-stack/plex',32400,'/identity'),
 ('apps/pihole',80,'/admin/login'),
]
def prove(check):
 chart,port,path=check;name=chart.rsplit('/',1)[-1]
 report=ROOT/'evidence'/('private-'+name+'.json')
 if report.exists():return {'chart':chart,'private_passed':True,'existing':True}
 for _ in range(240):
  if (ROOT/'evidence'/('copy-'+name+'.json')).exists():break
  time.sleep(5)
 else:return {'chart':chart,'private_passed':False,'reason':'Copy not accepted'}
 result=subprocess.run([sys.executable,str(ROOT/'scripts/migration/private-app-proof.py'),'--chart',chart,'--port',str(port),'--path',path],capture_output=True,text=True)
 item={'chart':chart,'private_passed':result.returncode==0,'exit':result.returncode}
 if result.returncode:item['diagnostic']=result.stderr[-2000:]
 print(json.dumps(item),flush=True);return item
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(prove,CHECKS))
 (ROOT/'evidence/application-private-wave.json').write_text(json.dumps(results,indent=2)+'\n')
 raise SystemExit(0 if all(r['private_passed'] for r in results) else 1)
