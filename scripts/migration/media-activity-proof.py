#!/usr/bin/env python3
"""Inspect existing media activity and original/native path visibility; never import or modify files.

Credentials, torrent hashes, filenames and response bodies remain in memory.
Queue/path existence alone does not prove a completed download/import or file integrity.
"""
import base64,collections,datetime,json,pathlib,subprocess
r=pathlib.Path.home()/'.local/share/branconet-migration';k=[str(r/'bin/kubectl'),'--kubeconfig',str(r/'admin.conf')]
s=json.loads(subprocess.check_output(k+['get','secret','unpackerr-runtime','-n','plex','-o','json']))
checks=[]
for app in ['sonarr','radarr']:
 service=json.loads(subprocess.check_output(k+['get','service',app,'-n','plex','-o','json']))
 base='http://'+service['spec']['clusterIP']+':'+str(service['spec']['ports'][0]['port'])
 key=base64.b64decode(s['data']['UN_'+app.upper()+'_0_API_KEY']).decode()
 code='''import collections,json,urllib.request
base=BASE
headers={'X-Api-Key':KEY}
def get(path):
 with urllib.request.urlopen(urllib.request.Request(base+path,headers=headers),timeout=20) as response:return json.loads(response.read())
history=get('/api/v3/history?page=1&pageSize=1000&sortKey=date&sortDirection=descending')
records=history.get('records',[]);recent=[r for r in records if r.get('date','')>='2026-10-09T18:27:00Z']
queue=get('/api/v3/queue?page=1&pageSize=100&includeUnknownSeriesItems=true&includeUnknownMovieItems=true')
report={'history_total':history.get('totalRecords'),'history_records_inspected':len(records),'recent_events_by_type':dict(collections.Counter(str(r.get('eventType')) for r in recent)),'recent_imports':[{'date':r.get('date'),'history_id':r['id'],'event_type':r.get('eventType'),'data_keys':sorted(r.get('data',{}))} for r in recent if 'import' in str(r.get('eventType','')).lower()],'queue_statuses':dict(collections.Counter(str(r.get('trackedDownloadStatus')) for r in queue.get('records',[]))),'queue_states':dict(collections.Counter(str(r.get('trackedDownloadState')) for r in queue.get('records',[]))),'most_recent_event':records[0].get('date') if records else None}
print(json.dumps(report))
'''.replace('BASE',repr(base)).replace('KEY',repr(key))
 result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','python3','-'],input=code.encode(),capture_output=True,timeout=90)
 if result.returncode:raise RuntimeError('Read-only history inspection failed for '+app+'; raw response withheld')
 checks.append({'application':app,**json.loads(result.stdout)})
code='''import collections,datetime,http.cookiejar,json,os,urllib.parse,urllib.request
base='http://127.0.0.1:8112';opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
payload=urllib.parse.urlencode({'username':os.environ['QBITTORRENT_USERNAME'],'password':os.environ['QBITTORRENT_PASSWORD']}).encode()
with opener.open(urllib.request.Request(base+'/api/v2/auth/login',data=payload,headers={'Referer':base}),timeout=20) as response:
 if response.read()!=b'Ok.':raise RuntimeError('Authentication failed')
with opener.open(urllib.request.Request(base+'/api/v2/torrents/info',headers={'Referer':base}),timeout=20) as response:records=json.loads(response.read())
threshold=int(datetime.datetime(2026,10,9,18,27,tzinfo=datetime.timezone.utc).timestamp())
print(json.dumps({'queue_count':len(records),'states':dict(collections.Counter(r.get('state') for r in records)),'completed_since_native_cutover':sum(r.get('completion_on',0)>=threshold for r in records),'added_since_native_cutover':sum(r.get('added_on',0)>=threshold for r in records)}))
'''
result=subprocess.run(k+['exec','-i','-n','plex','deployment/qbittorrent','-c','qbittorrent','--','python3','-'],input=code.encode(),capture_output=True,timeout=90)
if result.returncode:raise RuntimeError('qBittorrent activity inspection failed; details withheld')
activity_report={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cutover_threshold':'2026-10-09T18:27:00Z','arr':checks,'qbittorrent':json.loads(result.stdout),'read_only':True}

import base64,json,pathlib,shlex,subprocess
r=pathlib.Path.home()/'.local/share/branconet-migration';k=[str(r/'bin/kubectl'),'--kubeconfig',str(r/'admin.conf')]
s=json.loads(subprocess.check_output(k+['get','secret','unpackerr-runtime','-n','plex','-o','json']))
apps={}
for app in ['sonarr','radarr']:
 service=json.loads(subprocess.check_output(k+['get','service',app,'-n','plex','-o','json']))
 base='http://'+service['spec']['clusterIP']+':'+str(service['spec']['ports'][0]['port'])
 key=base64.b64decode(s['data']['UN_'+app.upper()+'_0_API_KEY']).decode()
 code='import json,urllib.request\nheaders={"X-Api-Key":'+repr(key)+'}\nbase='+repr(base)+'\nreport={}\nfor path in ["queue?page=1&pageSize=100&includeUnknownSeriesItems=true&includeUnknownMovieItems=true","remotepathmapping"]:\n with urllib.request.urlopen(urllib.request.Request(base+"/api/v3/"+path,headers=headers),timeout=20) as response:report[path]=json.loads(response.read())\nprint(json.dumps(report))'
 result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','python3','-'],input=code.encode(),capture_output=True,timeout=50)
 if result.returncode:raise RuntimeError('Arr path query failed; output withheld')
 apps[app]=json.loads(result.stdout)
code='''import http.cookiejar,json,os,urllib.parse,urllib.request
base='http://127.0.0.1:8112';opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
payload=urllib.parse.urlencode({'username':os.environ['QBITTORRENT_USERNAME'],'password':os.environ['QBITTORRENT_PASSWORD']}).encode()
with opener.open(urllib.request.Request(base+'/api/v2/auth/login',data=payload,headers={'Referer':base}),timeout=20) as response:
 if response.read()!=b'Ok.':raise RuntimeError('Authentication failed')
with opener.open(urllib.request.Request(base+'/api/v2/torrents/info',headers={'Referer':base}),timeout=20) as response:torrents=json.loads(response.read())
print(json.dumps({r['hash'].lower():{'content_path':r.get('content_path'),'save_path':r.get('save_path'),'path_exists':os.path.exists(r.get('content_path',''))} for r in torrents}))
'''
result=subprocess.run(k+['exec','-i','-n','plex','deployment/qbittorrent','-c','qbittorrent','--','python3','-'],input=code.encode(),capture_output=True,timeout=50)
if result.returncode:raise RuntimeError('qBittorrent path query failed; output withheld')
torrents=json.loads(result.stdout);report=[]
source_mount=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','findmnt','-n','-o','SOURCE,FSTYPE','-T','/mnt/plex_smb_share/downloads'],capture_output=True,timeout=20)
if source_mount.returncode or source_mount.stdout.decode().split()!=['//192.168.0.8/plex_smb_share','cifs']:
 raise RuntimeError('Original SMB mount is not the expected live share; path checks blocked')
for app,data in apps.items():
 queue=next(v for key,v in data.items() if key.startswith('queue'))['records'];checks=[]
 for item in queue:
  path=item.get('outputPath','');torrent=torrents.get(str(item.get('downloadId','')).lower(),{});content=torrent.get('content_path','')
  shell='test -e '+shlex.quote(path)+'; p=$?; test -e '+shlex.quote(content)+'; q=$?; printf "%s %s" "$p" "$q"'
  result=subprocess.run(k+['exec','-i','-n','plex','deployment/'+app,'--','sh','-s'],input=shell.encode(),capture_output=True,timeout=25)
  if result.returncode:raise RuntimeError('Read-only pod path check failed; raw path withheld')
  flags=result.stdout.decode().split()
  if len(flags)!=2:raise RuntimeError('Unexpected path-test response; raw path withheld')
  if not path.startswith('/downloads/') or '..' in pathlib.PurePosixPath(path).parts:
   raise RuntimeError('Queue path is outside the verified downloads mount; path withheld')
  original='/mnt/plex_smb_share/downloads/'+path[len('/downloads/'):]
  source_code='import json,os\npath='+repr(original)+'\ntry:\n os.stat(path);result={"exists":True,"error":None}\nexcept FileNotFoundError:result={"exists":False,"error":"not_found"}\nexcept PermissionError:result={"exists":None,"error":"permission"}\nprint(json.dumps(result))'
  source_result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','python3','-'],input=source_code.encode(),capture_output=True,timeout=20)
  if source_result.returncode:raise RuntimeError('Original SMB path check failed; raw path withheld')
  original_state=json.loads(source_result.stdout)
  checks.append({'original_host_smb_exists':original_state['exists'],'original_host_smb_error':original_state['error'],'queue_id':item['id'],'arr_output_path_exists':flags[0]=='0','qbit_content_path_exists_in_arr':flags[1]=='0','torrent_matched':bool(torrent),'qbit_content_path_exists_in_qbit':torrent.get('path_exists'),'arr_output_equals_qbit_content':path==content,'tracked_state':item.get('trackedDownloadState')})
 report.append({'application':app,'remote_path_mappings':len(data['remotepathmapping']),'checks':checks})
visibility_report={'read_only':True,'checks':report,'original_smb_source_verified':True,'file_paths_and_titles_reported':False}

report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'activity':activity_report,'path_visibility':visibility_report,'libraries_configuration_or_downloads_changed':False,'actual_download_import_proven':False,'original_smb_file_integrity_proven':False}
root=pathlib.Path(__file__).resolve().parents[2]
(root/'evidence/media-activity-proof.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
