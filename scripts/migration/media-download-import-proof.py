#!/usr/bin/env python3
"""Inspect the owned licensed download/import fixture; credentials remain in memory."""
import base64,datetime,json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
r=pathlib.Path.home()/'.local/share/branconet-migration'
state=json.loads((r/'recovery'/'media-fixture-state.json').read_text())
if state.get('cleanup_complete'):
 print(json.dumps({'fixture_already_cleaned_up':True,'retained_evidence':'evidence/media-download-import-proof.json','no_new_live_import_check_performed':True}));raise SystemExit(0)
k=[str(r/'bin/kubectl'),'--kubeconfig',str(r/'admin.conf')]
s=json.loads(subprocess.check_output(k+['get','secret','unpackerr-runtime','-n','plex','-o','json']))
service=json.loads(subprocess.check_output(k+['get','service','radarr','-n','plex','-o','json']))
base='http://'+service['spec']['clusterIP']+':'+str(service['spec']['ports'][0]['port'])
key=base64.b64decode(s['data']['UN_RADARR_0_API_KEY']).decode()
code=r'''
import hashlib,json,urllib.request
base=BASE;headers={'X-Api-Key':KEY};state=STATE
def get(path):
 with urllib.request.urlopen(urllib.request.Request(base+'/api/v3/'+path,headers=headers),timeout=30) as response:return json.loads(response.read())
movies=get('movie');original=[m for m in movies if m['id']!=state['radarr_movie_id']]
fields=['id','tmdbId','path','movieFileId','qualityProfileId','monitored']
fingerprint=hashlib.sha256(json.dumps([{k:m.get(k) for k in fields} for m in sorted(original,key=lambda m:m['id'])],sort_keys=True).encode()).hexdigest()
movie=get('movie/'+str(state['radarr_movie_id']))
if movie['tmdbId']!=state['tmdb_id'] or movie['path']!=state['library_path']:raise RuntimeError('Fixture movie identity changed')
queue=get('queue?page=1&pageSize=100')
owned_queue=[q for q in queue.get('records',[]) if q.get('movieId')==state['radarr_movie_id'] or str(q.get('downloadId','')).lower()==state['fixture_torrent_hash']]
history=get('history/movie?movieId='+str(state['radarr_movie_id']))
moviefile=movie.get('movieFile') or {}
print(json.dumps({'movie_id':movie['id'],'has_file':movie.get('hasFile'),'movie_file_id':movie.get('movieFileId'),'original_movie_count':len(original),'original_movie_metadata_sha256':fingerprint,'original_movie_metadata_equal':fingerprint==state['radarr_baseline_metadata_sha256'],'queue':[{'status':q.get('status'),'trackedDownloadStatus':q.get('trackedDownloadStatus'),'trackedDownloadState':q.get('trackedDownloadState'),'statusMessages':q.get('statusMessages'),'outputPath':q.get('outputPath')} for q in owned_queue],'history':[{'date':h.get('date'),'eventType':h.get('eventType'),'movieId':h.get('movieId'),'downloadId_matches':str(h.get('downloadId') or (h.get('data') or {}).get('downloadId','')).lower()==state['fixture_torrent_hash']} for h in history],'movie_file':{k:v for k,v in moviefile.items() if k in ['id','path','relativePath','size','quality','mediaInfo','dateAdded']}}))
'''.replace('BASE',repr(base)).replace('KEY',repr(key)).replace('STATE',repr(state))
result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','python3','-'],input=code.encode(),capture_output=True,timeout=90)
if result.returncode:raise RuntimeError('Owned Radarr fixture inspection failed; private diagnostics withheld')
arr=json.loads(result.stdout)
code=r'''
import hashlib,http.cookiejar,json,os,pathlib,urllib.parse,urllib.request
state=STATE;base='http://127.0.0.1:8112';opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def call(path,data=None):
 if isinstance(data,dict):data=urllib.parse.urlencode(data).encode()
 with opener.open(urllib.request.Request(base+'/api/v2/'+path,data=data,headers={'Referer':base}),timeout=30) as response:return response.read()
if call('auth/login',{'username':os.environ['QBITTORRENT_USERNAME'],'password':os.environ['QBITTORRENT_PASSWORD']})!=b'Ok.':raise RuntimeError('Authentication failed')
queue=json.loads(call('torrents/info'));own=[t for t in queue if t['hash']==state['fixture_torrent_hash']]
if len(own)!=1 or own[0]['save_path']!=state['download_directory'] or own[0]['tags']!='migration-acceptance':raise RuntimeError('Fixture torrent identity/path changed')
original=[t for t in queue if t['hash']!=state['fixture_torrent_hash']]
fingerprint=hashlib.sha256('\n'.join(sorted(t['hash'] for t in original)).encode()).hexdigest()
torrent=own[0];files=[]
logs=json.loads(call('log/main?normal=true&info=true&warning=true&critical=true&last_known_id=-1'))
bans=[{'id':log['id'],'timestamp':log.get('timestamp'),'peer_banned':True} for log in logs if 'big buck bunny' in log.get('message','').lower() and 'peer banned' in log.get('message','').lower()]
if torrent.get('progress')==1:
 root=pathlib.Path(state['download_directory']).resolve()
 for p in sorted(root.rglob('*')):
  if not p.is_file():continue
  if not p.resolve().is_relative_to(root):raise RuntimeError('Fixture file escapes owned directory')
  digest=hashlib.sha256()
  with p.open('rb') as f:
   for data in iter(lambda:f.read(1048576),b''):digest.update(data)
  files.append({'relative_path':str(p.relative_to(root)),'size':p.stat().st_size,'sha256':digest.hexdigest()})
print(json.dumps({'torrent':{k:torrent.get(k) for k in ['state','progress','size','downloaded','dlspeed','num_seeds','completion_on','added_on','content_path','save_path','category']},'owned_seed_ban_events':bans,'original_queue_count':len(original),'original_torrent_ids_sha256':fingerprint,'original_torrent_ids_equal':fingerprint==state['baseline_torrent_hashes_sha256'],'download_files':files}))
'''.replace('STATE',repr(state))
result=subprocess.run(k+['exec','-i','-n','plex','deployment/qbittorrent','-c','qbittorrent','--','python3','-'],input=code.encode(),capture_output=True,timeout=100)
if result.returncode:raise RuntimeError('Owned qBittorrent fixture inspection failed; private diagnostics withheld')
qb=json.loads(result.stdout)
report={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'fixture':state,'radarr':arr,'qbittorrent':qb,'sources':{'license':'https://peach.blender.org/about/','torrent_catalog':'https://github.com/webtorrent/webtorrent/blob/master/docs/free-torrents.md','torrent':'https://webtorrent.io/torrents/big-buck-bunny.torrent'},'automatic_import_observed':bool(arr.get('has_file') and arr.get('movie_file_id') and any('import' in str(h.get('eventType','')).lower() and h['downloadId_matches'] for h in arr['history'])),'scope':{'indexer_search_triggered':False,'notification_sent':False,'manual_import_triggered':False,'original_library_overwrite_requested':False,'cleanup_complete':False}}

if report['automatic_import_observed']:
 imported=arr['movie_file'].get('path')
 if not imported:raise RuntimeError('Imported fixture path is missing')
 root=state['library_path']
 file_code="""import hashlib,json,pathlib
path=pathlib.Path(PATH);root=pathlib.Path(ROOT).resolve()
if not path.resolve().is_relative_to(root):raise RuntimeError('Imported file escapes owned fixture directory')
digest=hashlib.sha256()
with path.open('rb') as f:
 for data in iter(lambda:f.read(1048576),b''):digest.update(data)
print(json.dumps({'path':str(path),'size':path.stat().st_size,'sha256':digest.hexdigest()}))
""".replace('PATH',repr(imported)).replace('ROOT',repr(root))
 exec_base=k+['exec','-n','plex','deployment/radarr','--']
 resolved=subprocess.check_output(exec_base+['readlink','-f','--',imported],timeout=30).decode().strip()
 if not pathlib.PurePosixPath(resolved).is_relative_to(pathlib.PurePosixPath(root)):raise RuntimeError('Imported file escapes owned fixture directory')
 digest=subprocess.check_output(exec_base+['sha256sum','--',resolved],timeout=100).decode().split()[0]
 if len(digest)!=64:raise RuntimeError('Invalid imported-file digest')
 size=int(subprocess.check_output(exec_base+['stat','-c','%s','--',resolved],timeout=30))
 native={'path':resolved,'size':size,'sha256':digest}
 downloaded=next(f for f in qb['download_files'] if f['relative_path'].endswith('Big Buck Bunny.mp4'))
 report['imported_file_proof']={**native,'matches_download_sha256':native['sha256']==downloaded['sha256'],'matches_download_size':native['size']==downloaded['size']}
 host_path='/mnt/plex_smb_share/downloads/'+pathlib.Path(state['download_directory']).name+'/'+downloaded['relative_path']
 source_code=file_code.replace(repr(imported),repr(host_path)).replace(repr(root),repr('/mnt/plex_smb_share/downloads/'+pathlib.Path(state['download_directory']).name))
 result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','python3','-'],input=source_code.encode(),capture_output=True,timeout=100)
 if result.returncode:raise RuntimeError('Original SMB fixture hash check failed; private diagnostics withheld')
 original=json.loads(result.stdout)
 report['original_smb_fixture_proof']={**original,'matches_download_sha256':original['sha256']==downloaded['sha256'],'matches_download_size':original['size']==downloaded['size']}
 report['download_import_data_passed']=all([report['imported_file_proof']['matches_download_sha256'],report['imported_file_proof']['matches_download_size'],report['original_smb_fixture_proof']['matches_download_sha256'],report['original_smb_fixture_proof']['matches_download_size'],qb['original_torrent_ids_equal'],arr['original_movie_metadata_equal']])

path=ROOT/'evidence/media-download-import-proof.json';path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'evidence':str(path),'torrent_state':qb['torrent']['state'],'download_progress':qb['torrent']['progress'],'automatic_import_observed':report['automatic_import_observed'],'original_torrent_ids_equal':qb['original_torrent_ids_equal'],'original_movie_metadata_equal':arr['original_movie_metadata_equal'],'fixture_queue':arr['queue']}))
