#!/usr/bin/env python3
"""Remove only the verified, owned migration fixture after successful import/byte checks."""
import base64,datetime,json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
r=pathlib.Path.home()/'.local/share/branconet-migration'
state_path=r/'recovery/media-fixture-state.json';state=json.loads(state_path.read_text())
report_path=ROOT/'evidence/media-download-import-proof.json';report=json.loads(report_path.read_text())
if not report.get('download_import_data_passed'):raise RuntimeError('Full fixture download/import/hash proof is required before cleanup')
if report['fixture']['fixture_torrent_hash']!=state['fixture_torrent_hash'] or report['fixture']['radarr_movie_id']!=state['radarr_movie_id']:raise RuntimeError('Fixture evidence identity mismatch')
k=[str(r/'bin/kubectl'),'--kubeconfig',str(r/'admin.conf')]
s=json.loads(subprocess.check_output(k+['get','secret','unpackerr-runtime','-n','plex','-o','json']))
service=json.loads(subprocess.check_output(k+['get','service','radarr','-n','plex','-o','json']))
base='http://'+service['spec']['clusterIP']+':'+str(service['spec']['ports'][0]['port'])
key=base64.b64decode(s['data']['UN_RADARR_0_API_KEY']).decode()
code=r'''
import hashlib,json,urllib.request,urllib.error
state=STATE;base=BASE;headers={'X-Api-Key':KEY}
def get(path):
 with urllib.request.urlopen(urllib.request.Request(base+'/api/v3/'+path,headers=headers),timeout=30) as response:return json.loads(response.read())
movie=get('movie/'+str(state['radarr_movie_id']))
if movie['tmdbId']!=state['tmdb_id'] or movie['path']!=state['library_path']:raise RuntimeError('Fixture movie identity/path guard failed')
with urllib.request.urlopen(urllib.request.Request(base+'/api/v3/movie/'+str(state['radarr_movie_id'])+'?deleteFiles=false&addImportExclusion=false',headers=headers,method='DELETE'),timeout=30) as response:response.read()
movies=get('movie')
fields=['id','tmdbId','path','movieFileId','qualityProfileId','monitored']
digest=hashlib.sha256(json.dumps([{k:m.get(k) for k in fields} for m in sorted(movies,key=lambda m:m['id'])],sort_keys=True).encode()).hexdigest()
print(json.dumps({'owned_movie_removed':not any(m['id']==state['radarr_movie_id'] for m in movies),'original_movie_count':len(movies),'original_movie_metadata_equal':digest==state['radarr_baseline_metadata_sha256'],'media_delete_requested_to_api':False,'import_exclusion_requested':False}))
'''.replace('STATE',repr(state)).replace('BASE',repr(base)).replace('KEY',repr(key))
result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','python3','-'],input=code.encode(),capture_output=True,timeout=90)
if result.returncode:raise RuntimeError('Fixture movie removal failed; private diagnostics withheld')
cleanup={'radarr':json.loads(result.stdout)}
code=r'''
import hashlib,http.cookiejar,json,os,urllib.parse,urllib.request
state=STATE;base='http://127.0.0.1:8112';opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def call(path,data=None):
 if isinstance(data,dict):data=urllib.parse.urlencode(data).encode()
 with opener.open(urllib.request.Request(base+'/api/v2/'+path,data=data,headers={'Referer':base}),timeout=30) as response:return response.read()
if call('auth/login',{'username':os.environ['QBITTORRENT_USERNAME'],'password':os.environ['QBITTORRENT_PASSWORD']})!=b'Ok.':raise RuntimeError('Authentication failed')
queue=json.loads(call('torrents/info'));owned=[t for t in queue if t['hash']==state['fixture_torrent_hash']]
if len(owned)!=1 or owned[0]['save_path']!=state['download_directory'] or owned[0]['tags']!='migration-acceptance':raise RuntimeError('Fixture torrent identity/path guard failed')
call('torrents/stop',{'hashes':state['fixture_torrent_hash']})
call('torrents/delete',{'hashes':state['fixture_torrent_hash'],'deleteFiles':'false'})
import time
for attempt in range(30):
 queue=json.loads(call('torrents/info'))
 if not any(t['hash']==state['fixture_torrent_hash'] for t in queue):break
 time.sleep(0.2)
digest=hashlib.sha256('\n'.join(sorted(t['hash'] for t in queue)).encode()).hexdigest()
print(json.dumps({'owned_torrent_removed':not any(t['hash']==state['fixture_torrent_hash'] for t in queue),'original_queue_count':len(queue),'original_torrent_ids_equal':digest==state['baseline_torrent_hashes_sha256'],'torrent_file_delete_requested_to_api':False}))
'''.replace('STATE',repr(state))
result=subprocess.run(k+['exec','-i','-n','plex','deployment/qbittorrent','-c','qbittorrent','--','python3','-'],input=code.encode(),capture_output=True,timeout=90)
if result.returncode:raise RuntimeError('Owned torrent removal failed; private diagnostics withheld')
cleanup['qbittorrent']=json.loads(result.stdout)
code=r'''
import datetime,json,pathlib,shutil,subprocess
state=STATE;share=pathlib.Path('/mnt/plex_smb_share')
mount=json.loads(subprocess.check_output(['findmnt','-J','-T',str(share)]))['filesystems'][0]
if mount['source']!='//192.168.0.8/plex_smb_share' or mount['fstype']!='cifs':raise RuntimeError('Original SMB mount identity differs')
token=pathlib.PurePosixPath(state['download_directory']).name
if token!='.migration-acceptance-f3851e58f220457facc7ed7279c15a63':raise RuntimeError('Owned fixture token differs')
targets=[share/'downloads'/token,share/'movies'/token]
for p in targets:
 if p.resolve()!=p or not p.resolve().is_relative_to(share.resolve()) or p.is_symlink():raise RuntimeError('Unsafe fixture cleanup path')
 if not p.is_dir():raise RuntimeError('Owned fixture directory missing')
 if any(child.is_symlink() for child in p.rglob('*')):raise RuntimeError('Unexpected symlink in owned fixture')
 if p==targets[0] and not (p/'ATTRIBUTION.txt').is_file():raise RuntimeError('Owned fixture attribution marker missing')
 birth=subprocess.check_output(['stat','-c','%W','--',str(p)]).decode().strip()
 if int(birth)<=0 or int(birth)<int(datetime.datetime.fromisoformat(state['started_at']).timestamp())-120:raise RuntimeError('Directory predates the owned fixture')
for p in targets:shutil.rmtree(p)
print(json.dumps({'removed_owned_paths':[str(p) for p in targets],'all_owned_paths_absent':all(not p.exists() for p in targets),'share_retained':share.is_mount(),'source':'//192.168.0.8/plex_smb_share'}))
'''.replace('STATE',repr(state))
result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','python3','-'],input=code.encode(),capture_output=True,timeout=100)
if result.returncode:raise RuntimeError('Owned fixture file cleanup failed; private diagnostics withheld')
cleanup['filesystem']=json.loads(result.stdout);cleanup['completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
cleanup['passed']=all([cleanup['radarr']['owned_movie_removed'],cleanup['radarr']['original_movie_metadata_equal'],cleanup['qbittorrent']['owned_torrent_removed'],cleanup['qbittorrent']['original_torrent_ids_equal'],cleanup['filesystem']['all_owned_paths_absent'],cleanup['filesystem']['share_retained']])
report['cleanup']=cleanup;report['scope']['cleanup_complete']=cleanup['passed']
report_path.write_text(json.dumps(report,indent=2)+'\n')
state['cleanup_complete']=cleanup['passed'];state['cleanup_completed_at']=cleanup['completed_at'];state_path.write_text(json.dumps(state,indent=2)+'\n')
print(json.dumps(cleanup))
