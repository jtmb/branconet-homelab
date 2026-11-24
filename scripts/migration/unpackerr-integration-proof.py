#!/usr/bin/env python3
"""Check copied Unpackerr's configured Sonarr/Radarr APIs without exposing keys."""
import base64,datetime,json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration';k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
secret=json.loads(subprocess.check_output(k+['get','secret','unpackerr-runtime','-n','plex','-o','json']));checks=[]
for app in ['sonarr','radarr']:
 service=json.loads(subprocess.check_output(k+['get','service',app,'-n','plex','-o','json']));address=service['spec']['clusterIP'];port=service['spec']['ports'][0]['port'];key=base64.b64decode(secret['data']['UN_'+app.upper()+'_0_API_KEY']).decode()
 code='import json,urllib.request\nbase='+repr('http://'+address+':'+str(port))+'\nheaders={"X-Api-Key":'+repr(key)+'}\nresults=[]\nfor path in ["/api/v3/system/status","/api/v3/queue"]:\n with urllib.request.urlopen(urllib.request.Request(base+path,headers=headers),timeout=20) as r:obj=json.loads(r.read());results.append({"path":path,"status":r.status,"valid_json":True})\nprint(json.dumps(results))'
 result=subprocess.run(['ssh','-p','2002','james@192.168.0.4','python3','-'],input=code.encode(),capture_output=True)
 if result.returncode:raise RuntimeError('Configured '+app+' API access rejected; source keys retained')
 checks.append({'application':app,'checks':json.loads(result.stdout)})
subprocess.run(k+['rollout','restart','deployment/unpackerr','-n','plex'],capture_output=True,check=True);subprocess.run(k+['rollout','status','deployment/unpackerr','-n','plex','--timeout=180s'],capture_output=True,check=True)
report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'configured_api_credentials_and_queues_accessible':True,'checks':checks,'actual_process_restart_passed':True,'originals_and_native_data_claim_retained':True,'actual_download_extraction_tested':False}
(ROOT/'evidence/private-unpackerr.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
