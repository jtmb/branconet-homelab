#!/usr/bin/env python3
"""Authenticate to retained qBittorrent configuration without reporting credentials."""
import datetime,json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration';k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
code=r'''
import http.cookiejar,json,os,urllib.parse,urllib.request
base='http://127.0.0.1:8112';opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
payload=urllib.parse.urlencode({'username':os.environ['QBITTORRENT_USERNAME'],'password':os.environ['QBITTORRENT_PASSWORD']}).encode()
request=urllib.request.Request(base+'/api/v2/auth/login',data=payload,headers={'Referer':base})
with opener.open(request,timeout=20) as response:body=response.read()
if body!=b'Ok.':raise RuntimeError('Retained qBittorrent credentials rejected')
def get(path):
 with opener.open(urllib.request.Request(base+path,headers={'Referer':base}),timeout=20) as response:return response.read()
prefs=json.loads(get('/api/v2/app/preferences'));torrents=json.loads(get('/api/v2/torrents/info'))
print(json.dumps({'native_credentials_authenticated':True,'preferences_readable':True,'torrent_queue_count':len(torrents),'listen_port':prefs['listen_port'],'download_save_path':prefs.get('save_path'),'version':get('/api/v2/app/version').decode()}))
'''
result=subprocess.run(k+['exec','-i','-n','plex','deployment/qbittorrent','-c','qbittorrent','--','python3','-'],input=code.encode(),capture_output=True)
if result.returncode:
 p=RUNTIME/'qbittorrent-api.diagnostic';p.write_bytes(result.stderr);p.chmod(0o600);raise RuntimeError('qBittorrent API check failed; protected diagnostic saved')
report=json.loads(result.stdout);report['completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();(ROOT/'evidence/qbittorrent-api-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
