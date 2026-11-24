#!/usr/bin/env python3
"""Inspect the isolated licensed Sonarr/Unpackerr fixture; secret values stay in RAM."""
import base64,datetime,hashlib,json,pathlib,re,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
r=pathlib.Path.home()/'.local/share/branconet-migration';state=json.loads((r/'recovery/sonarr-fixture-state.json').read_text())
if state.get('cleanup_complete'):
 print(json.dumps({'fixture_already_cleaned_up':True,'no_new_live_import_check_performed':True}));raise SystemExit(0)
k=[str(r/'bin/kubectl'),'--kubeconfig',str(r/'admin.conf')]
secret=json.loads(subprocess.check_output(k+['get','secret','unpackerr-runtime','-n','plex','-o','json']))
service=json.loads(subprocess.check_output(k+['get','service','sonarr','-n','plex','-o','json']))
base='http://'+service['spec']['clusterIP']+':'+str(service['spec']['ports'][0]['port']);key=base64.b64decode(secret['data']['UN_SONARR_0_API_KEY']).decode()
code=r'''
import hashlib,json,urllib.request
state=__STATE__;base=__BASE__;headers={'X-Api-Key':__KEY__}
def get(path):
 with urllib.request.urlopen(urllib.request.Request(base+'/api/v3/'+path,headers=headers),timeout=30) as response:return json.loads(response.read())
series=get('series');own=get('series/'+str(state['sonarr_series_id']))
if own['tvdbId']!=state['tvdb_id'] or own['path']!=state['library_series_directory']:raise RuntimeError('Series ownership guard failed')
original=[s for s in series if s['id']!=state['sonarr_series_id']];fields=['id','tvdbId','path','qualityProfileId','monitored','seasonFolder']
digest=hashlib.sha256(json.dumps([{k:s.get(k) for k in fields} for s in sorted(original,key=lambda s:s['id'])],sort_keys=True).encode()).hexdigest()
episodes=get('episode?seriesId='+str(own['id']));episode=next(e for e in episodes if e['tvdbId']==state['tvdb_episode_id'] and e['seasonNumber']==1 and e['episodeNumber']==2)
files=get('episodefile?seriesId='+str(own['id']));f=next((f for f in files if f['id']==episode.get('episodeFileId')),{})
history=get('history/series?seriesId='+str(own['id']))
queue=get('queue?page=1&pageSize=100');owned=[q for q in queue.get('records',[]) if q.get('seriesId')==own['id'] or str(q.get('downloadId','')).lower()==state['fixture_torrent_hash']]
print(json.dumps({'series_id':own['id'],'episode_id':episode['id'],'has_file':episode.get('hasFile'),'episode_file_id':episode.get('episodeFileId'),'episode_file':{k:f.get(k) for k in ['id','path','relativePath','size','quality','dateAdded']},'original_series_count':len(original),'original_series_metadata_sha256':digest,'original_series_metadata_equal':digest==state['baseline_series_metadata_sha256'],'history':[{'date':h.get('date'),'eventType':h.get('eventType'),'episodeId':h.get('episodeId'),'downloadId_matches':str(h.get('downloadId') or (h.get('data') or {}).get('downloadId','')).lower()==state['fixture_torrent_hash']} for h in history],'queue':[{'title':q.get('title'),'downloadId_matches':str(q.get('downloadId','')).lower()==state['fixture_torrent_hash'],'status':q.get('status'),'trackedDownloadStatus':q.get('trackedDownloadStatus'),'trackedDownloadState':q.get('trackedDownloadState'),'statusMessages':q.get('statusMessages')} for q in owned]}))
'''.replace('__STATE__',repr(state)).replace('__BASE__',repr(base)).replace('__KEY__',repr(key))
result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','python3','-'],input=code.encode(),capture_output=True,timeout=90)
if result.returncode:raise RuntimeError('Owned Sonarr fixture API check failed; diagnostics withheld')
arr=json.loads(result.stdout)
code=r'''
import hashlib,http.cookiejar,json,os,pathlib,urllib.parse,urllib.request
state=__STATE__;base='http://127.0.0.1:8112';opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def call(path,data=None):
 if isinstance(data,dict):data=urllib.parse.urlencode(data).encode()
 with opener.open(urllib.request.Request(base+'/api/v2/'+path,data=data,headers={'Referer':base}),timeout=30) as response:return response.read()
if call('auth/login',{'username':os.environ['QBITTORRENT_USERNAME'],'password':os.environ['QBITTORRENT_PASSWORD']})!=b'Ok.':raise RuntimeError('Authentication failed')
queue=json.loads(call('torrents/info'));own=[t for t in queue if t['hash']==state['fixture_torrent_hash']]
if len(own)!=1 or own[0]['save_path']!=state['download_directory'] or own[0]['tags']!=state['token'].lstrip('.'):raise RuntimeError('Torrent ownership guard failed')
original=[t for t in queue if t['hash']!=state['fixture_torrent_hash']];digest=hashlib.sha256('\n'.join(sorted(t['hash'] for t in original)).encode()).hexdigest();files=[];root=pathlib.Path(state['download_directory']).resolve()
if state.get('torrent_folder_name'):
 root=root/state['torrent_folder_name']
 if not root.exists():root=pathlib.Path(state['incomplete_directory'])/state['torrent_folder_name']
for p in root.rglob('*'):
 if not p.is_file() or p.name not in [state['archive_name'],state['episode_name']]:continue
 if not p.resolve().is_relative_to(root):raise RuntimeError('Owned download file escapes directory')
 h=hashlib.sha256()
 with p.open('rb') as stream:
  for b in iter(lambda:stream.read(1048576),b''):h.update(b)
 files.append({'relative_path':str(p.relative_to(root)),'size':p.stat().st_size,'sha256':h.hexdigest()})
print(json.dumps({'torrent':{k:own[0].get(k) for k in ['name','state','progress','size','downloaded','completion_on','save_path','content_path','category']},'original_queue_count':len(original),'original_torrent_ids_equal':digest==state['baseline_torrent_ids_sha256'],'files':files}))
'''.replace('__STATE__',repr(state))
result=subprocess.run(k+['exec','-i','-n','plex','deployment/qbittorrent','-c','qbittorrent','--','python3','-'],input=code.encode(),capture_output=True,timeout=90)
if result.returncode:raise RuntimeError('Owned download check failed; diagnostics withheld')
qb=json.loads(result.stdout)
logs=subprocess.check_output(k+['logs','-n','plex','deployment/unpackerr','--since-time',state['torrent_started_at'],'--tail=3000'],timeout=30).decode()
deployment=json.loads(subprocess.check_output(k+['get','deployment','unpackerr','-n','plex','-o','json']))
unpackerr_images=[c['image'] for c in deployment['spec']['template']['spec']['containers']]
owned_logs=[line for line in logs.splitlines() if state['archive_name'].removesuffix('.zip').lower() in line.lower() or state['token'] in line]
log_events=[{'application_local_timestamp':(re.search(r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}',line).group(0) if re.search(r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}',line) else None),'extraction_completed':'extract' in line.lower() and any(w in line.lower() for w in ['complete','finished','success']),'extraction_started':'extract' in line.lower() and any(w in line.lower() for w in ['start','queue']),'error':'error' in line.lower(),'fixture_attribution_collision':'ATTRIBUTION.txt' in line and 'refusing to overwrite existing file' in line} for line in owned_logs]
report={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'fixture':state,'sonarr':arr,'qbittorrent':qb,'production_unpackerr_images':unpackerr_images,'unpackerr_owned_log_events':log_events,'automatic_import_observed':bool(arr['has_file'] and any(h['downloadId_matches'] and 'import' in str(h['eventType']).lower() for h in arr['history'])),'scope':{'temporary_loopback_seed':True,'external_peer_or_indexer_test':False,'manual_import_requested':False,'notifications_sent':False,'original_library_overwrite_requested':False,'original_episode_baseline_is_metadata_only':True}}
report['archive_download_passed']=any(f['sha256']==state['archive_sha256'] and f['size']==state['archive_bytes'] for f in qb['files']) and qb['torrent']['progress']==1
report['extracted_episode_bytes_equal']=any(f['sha256']==state['episode_sha256'] and f['size']==state['episode_bytes'] for f in qb['files'])
report['production_unpackerr_extraction_observed']=any(e['extraction_completed'] for e in log_events)
if report['automatic_import_observed']:
 path=arr['episode_file'].get('path') or state['library_series_directory']+'/'+arr['episode_file']['relativePath']
 command=k+['exec','-n','plex','deployment/sonarr','--'];resolved=subprocess.check_output(command+['readlink','-f','--',path],timeout=30).decode().strip()
 if not pathlib.PurePosixPath(resolved).is_relative_to(pathlib.PurePosixPath(state['library_series_directory'])):raise RuntimeError('Import escapes fixture library')
 digest=subprocess.check_output(command+['sha256sum','--',resolved],timeout=90).decode().split()[0];size=int(subprocess.check_output(command+['stat','-c','%s','--',resolved],timeout=30))
 report['imported_episode']={'path':resolved,'sha256':digest,'size':size,'matches_publisher_episode':digest==state['episode_sha256'] and size==state['episode_bytes']}
if report.get('imported_episode'):
 host='/mnt/plex_smb_share/tv/'+state['token']+'/Blender Shorts/'+arr['episode_file']['relativePath']
 hostcode="import hashlib,json,pathlib\np=pathlib.Path("+repr(host)+");root=pathlib.Path("+repr('/mnt/plex_smb_share/tv/'+state['token'])+").resolve()\nif not p.resolve().is_relative_to(root):raise RuntimeError('Host file containment failed')\nh=hashlib.sha256()\nwith p.open('rb') as f:\n for b in iter(lambda:f.read(1048576),b''):h.update(b)\nprint(json.dumps({'sha256':h.hexdigest(),'size':p.stat().st_size}))"
 result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','python3','-'],input=hostcode.encode(),capture_output=True,timeout=90)
 if result.returncode:raise RuntimeError('Owned original SMB import check failed; diagnostics withheld')
 hostproof=json.loads(result.stdout);hostproof['matches_publisher_episode']=hostproof['sha256']==state['episode_sha256'] and hostproof['size']==state['episode_bytes'];report['original_smb_imported_episode']=hostproof
report['unexpected_extraction_errors']=[e for e in log_events if e['error'] and not e['fixture_attribution_collision']]
report['chain_passed']=all([not report['unexpected_extraction_errors'],report['archive_download_passed'],report['extracted_episode_bytes_equal'],report['production_unpackerr_extraction_observed'],report['automatic_import_observed'],report.get('imported_episode',{}).get('matches_publisher_episode'),arr['original_series_metadata_equal'],qb['original_torrent_ids_equal'],report.get('original_smb_imported_episode',{}).get('matches_publisher_episode')])
(ROOT/'evidence/sonarr-archive-import-proof.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'progress':qb['torrent']['progress'],'archive_download_passed':report['archive_download_passed'],'production_unpackerr_extraction_observed':report['production_unpackerr_extraction_observed'],'automatic_import_observed':report['automatic_import_observed'],'chain_passed':report['chain_passed'],'queue':arr['queue'],'unpackerr_events':log_events}))
