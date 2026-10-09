#!/usr/bin/env python3
"""Match retained helper credentials to the unchanged application password hash."""
import base64,datetime,hashlib,json,pathlib,re,subprocess,urllib.parse
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration';k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
def execute(container,args,body=None):return subprocess.check_output(k+['exec','-i','-n','plex','deployment/qbittorrent','-c',container,'--']+args,input=body)
code=r'''
import configparser,json,pathlib
p=configparser.ConfigParser(interpolation=None,strict=False);p.read('/config/qBittorrent/qBittorrent.conf');section=p['Preferences']
print(json.dumps({'username':section.get('WebUI\\Username','admin'),'hash':section.get('WebUI\\Password_PBKDF2')}))
'''
current=json.loads(execute('qbittorrent',['python3','-'],code.encode()));script=execute('gluetun',['cat','/tmp/gluetun/setPortForeward.sh']).decode()
secret=json.loads(subprocess.check_output(k+['get','secret','qbittorrent-runtime','-n','plex','-o','json']));candidates=[(base64.b64decode(secret['data']['QBITTORRENT_USERNAME']).decode(),base64.b64decode(secret['data']['QBITTORRENT_PASSWORD']).decode())]
for match in re.finditer(r'username=([^&\s\x22\x27]+)&password=([^&\s\x22\x27]+)',script):candidates.append(tuple(urllib.parse.unquote_plus(v) for v in match.groups()))
stored=(current['hash'] or '').strip('"');current['username']=current['username'].strip('"')
if not stored or not stored.startswith('@ByteArray('):raise RuntimeError('Retained PBKDF2 password required')
salt,digest=stored[len('@ByteArray('):-1].split(':',1);salt=base64.b64decode(salt);digest=base64.b64decode(digest)
all_secrets=json.loads(subprocess.check_output(k+['get','secret','-A','-o','json']))
passwords=set()
for obj in all_secrets['items']:
 for key,value in obj.get('data',{}).items():
  if re.search('password|pass$|^value$',key,re.I):
   try:
    decoded=base64.b64decode(value).decode()
    if 1<len(decoded)<512:passwords.add(decoded)
   except UnicodeDecodeError:pass
candidates += [(current['username'],password) for password in passwords]
for app in ['sonarr','radarr']:
 code="import sqlite3,json;db=sqlite3.connect('file:/config/"+app+".db?mode=ro',uri=True);print(json.dumps([json.loads(row[0]) for row in db.execute('SELECT Settings FROM DownloadClients')]))"
 result=subprocess.run(k+['exec','-i','-n','plex','deployment/'+app,'--','python3','-'],input=code.encode(),capture_output=True)
 if not result.returncode:
  for client in json.loads(result.stdout):
   user=client.get('username');password=client.get('password')
   if user and password:candidates.append((user,password))
matched=next(((user,password) for user,password in candidates if user==current['username'] and hashlib.pbkdf2_hmac('sha512',password.encode(),salt,100000)==digest),None)
if not matched:raise RuntimeError('No retained credentials match unchanged application hash')
data={'QBITTORRENT_USERNAME':base64.b64encode(matched[0].encode()).decode(),'QBITTORRENT_PASSWORD':base64.b64encode(matched[1].encode()).decode()}
changed=any(secret['data'][key]!=value for key,value in data.items())
if changed:
 secret['data'].update(data)
 subprocess.run(k+['replace','-f','-'],input=json.dumps(secret).encode(),capture_output=True,check=True)
report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'unchanged_application_pbkdf2_hash_matched':True,'native_consumer_credentials_corrected':changed,'application_password_not_reset':True,'credential_values_reported':False}
(ROOT/'evidence/qbittorrent-credential-review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
