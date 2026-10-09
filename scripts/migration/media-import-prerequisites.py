#!/usr/bin/env python3
"""Read real Arr root-folder/client/health metadata without changing libraries.

This proves import prerequisites only. It never claims a completed download/import.
API keys and response details remain in memory; paths and counts are nonsecret.
"""
import base64,datetime,json,pathlib,subprocess

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
K=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
secret=json.loads(subprocess.check_output(K+['get','secret','unpackerr-runtime','-n','plex','-o','json']))
checks=[]
for app in ['sonarr','radarr']:
    service=json.loads(subprocess.check_output(K+['get','service',app,'-n','plex','-o','json']))
    base='http://'+service['spec']['clusterIP']+':'+str(service['spec']['ports'][0]['port'])
    key=base64.b64decode(secret['data']['UN_'+app.upper()+'_0_API_KEY']).decode()
    code='import json,urllib.request\nbase='+repr(base)+'\nheaders={"X-Api-Key":'+repr(key)+'}\nresults={}\nfor path in ["rootfolder","health","downloadclient","queue"]:\n with urllib.request.urlopen(urllib.request.Request(base+"/api/v3/"+path,headers=headers),timeout=20) as response:results[path]=json.loads(response.read())\nreport={"root_folders":[{"path":r.get("path"),"accessible":r.get("accessible"),"free_space_reported":r.get("freeSpace") is not None} for r in results["rootfolder"]],"health_types":[{"type":h.get("type"),"source":h.get("source")} for h in results["health"]],"download_clients":[{"implementation":c.get("implementation"),"enabled":c.get("enable")} for c in results["downloadclient"]],"queue_records":results["queue"].get("totalRecords")}\nprint(json.dumps(report))'
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','python3','-'],input=code.encode(),capture_output=True,timeout=100)
    if result.returncode:raise RuntimeError('Unable to inspect '+app+' import prerequisites')
    checks.append({'application':app,**json.loads(result.stdout)})
report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'libraries_or_configuration_changed':False,'actual_download_import_tested':False,'values_reported':False}
(ROOT/'evidence/media-import-prerequisites.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
