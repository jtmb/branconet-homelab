import pathlib,runpy,subprocess,shlex,json,os,base64,hashlib,sys
F=pathlib.Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025');S=F/'control-source/upstream-tautulli-20261026';O=F/'upstream-tautulli-20261026';phase,revision=sys.argv[1:];assert phase in ['after','restart'];os.umask(0o077);scope=runpy.run_path(str(S/'scripts/migration/qualify-upstream-tautulli-r3.py'));key=(O/'observation.key').read_bytes();before=scope['fence'](scope['NEW'],revision,key)
program=r'''
import sys,os,json,sqlite3,resource,base64,hashlib,hmac,configparser,urllib.request,xml.etree.ElementTree as ET,ctypes
from pathlib import Path
resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
if os.geteuid()==0:os.setgroups([]);os.setgid(1000);os.setuid(1000)
assert ctypes.CDLL(None).prctl(38,1,0,0,0)==0 and os.geteuid()==os.getegid()==1000
key=bytes.fromhex(sys.stdin.read(4096).strip());assert len(key)==32
pins={'users.py':'3477e714d83e366220a095c27f90ed3f818bf06949bb702cb5172baf3e67dbf3','__init__.py':'4a1f3dc5a8776400a65759ea994838ebf616d165c71b8b05fa45b219fdda9e58','activity_processor.py':'5784537c44bad975114cbcd9cce5bd3a71844b673f07ddcdb448ed1ddce48d14'}
for name,wanted in pins.items():assert hashlib.sha256((Path('/app/tautulli/plexpy')/name).read_bytes()).hexdigest()==wanted
c=configparser.ConfigParser(interpolation=None,strict=True);c.read('/config/config.ini',encoding='utf-8-sig');token=c.get('PMS','pms_token').strip().strip('"\'');assert token and '\n'not in token and '\r'not in token
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect());avatars={};https=[]
for endpoint,tag in [('/users/account','user'),('/api/users','User')]:
 with opener.open(urllib.request.Request('https://plex.tv'+endpoint,headers={'X-Plex-Token':token}),timeout=20)as r:
  raw=r.read(4*1024**2+1);assert r.status==200 and len(raw)<=4*1024**2
 root=ET.fromstring(raw);elements=[root]if root.tag==tag else list(root.iter(tag));assert len(elements)<=1000
 for user in elements:
  uid=user.get('id','');thumb=user.get('thumb','');assert uid.isdigit() and len(thumb.encode())<=8192
  value=hmac.new(key,json.dumps(['plex-avatar',int(uid),thumb],separators=(',',':')).encode(),hashlib.sha256).hexdigest();assert uid not in avatars or avatars[uid]==value;avatars[uid]=value
 https.append({'endpoint':endpoint,'tlsVerified':True,'users':len(elements)})
source=sqlite3.connect('file:/config/tautulli.db?mode=ro',uri=True,timeout=5,isolation_level=None);source.execute('PRAGMA query_only=ON');source.execute('BEGIN');assert source.execute('PRAGMA page_count').fetchone()[0]*source.execute('PRAGMA page_size').fetchone()[0]<=64*1024**2
memory=sqlite3.connect(':memory:');source.backup(memory,pages=64);source.close();assert memory.execute('PRAGMA integrity_check').fetchall()==[('ok',)];assert memory.execute('PRAGMA foreign_key_check').fetchone()is None;data=memory.serialize();assert len(data)<=64*1024**2;memory.close();print(json.dumps({'snapshot':base64.b64encode(data).decode(),'snapshotBytes':len(data),'snapshotSHA256':hashlib.sha256(data).hexdigest(),'sqliteVersion':sqlite3.sqlite_version,'avatars':avatars,'avatarHTTPS':https,'sourcePins':pins,'productionDatabaseModified':False}))
'''
p=subprocess.run(scope['SSH']+[shlex.join(['kubectl','-n','plex','exec','-i',before['pod'],'-c','tautulli','--','python3','-B','-c',program])],input=key.hex().encode(),capture_output=True,timeout=180)
if p.returncode!=0:
 (O/(phase+'-snapshot-failure.stderr')).write_bytes(p.stderr);raise ValueError('snapshot_failed_private_diagnostic_saved')
assert len(p.stdout)<=96*1024**2;d=json.loads(p.stdout);data=base64.b64decode(d.pop('snapshot'),validate=True);assert len(data)==d['snapshotBytes'] and hashlib.sha256(data).hexdigest()==d['snapshotSHA256'];db=O/(phase+'-current.db');assert not db.exists();db.write_bytes(data);assert scope['fence'](scope['NEW'],revision,key)==before;d.update(writer=before,revision=revision,sourceSHA256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest());out=O/(phase+'-database-source.json');assert not out.exists();out.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'phase':phase,'snapshotBytes':len(data),'snapshotSHA256':d['snapshotSHA256'],'avatarSourcesTLSVerified':len(d['avatarHTTPS']),'podUID':before['podUID']}))