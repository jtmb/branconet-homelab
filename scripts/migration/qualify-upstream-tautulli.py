#!/usr/bin/env python3
"""Read-only complete state, API and route proof for the official Tautulli image."""
import argparse
import ast
import datetime
import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import re
import shlex
import socket
import ssl
import subprocess
import uuid

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'upstream-tautulli-20261026'
OLD = 'docker.io/library/tautulli-security-20261023@sha256:769aa67e07e35bdfe714a486591eb1a34c9ad9bd6cf2da89da130dcdab9de05a'
NEW = 'ghcr.io/linuxserver/tautulli:v2.18.2-ls249@sha256:c6a48416d16b26f254b000133d2d844c1905ee58ed0f44aad9bda66598d39988'
CHILD = 'sha256:88cb2fd7ab5b356e58b73a07b2ed1e44819e933e4982b7de4096e52406853823'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']

SQL = r'''
import base64,hashlib,hmac,json,time,sqlite3
from pathlib import Path
def compact(v):return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
def mac(key,value):return hmac.new(key,compact(['tautulli-upstream-v1',value]),hashlib.sha256).hexdigest()
def cell(v):
 if v is None:return ['null']
 if isinstance(v,bytes):return ['blob',base64.b64encode(v).decode()]
 if isinstance(v,str):return ['text',v]
 if isinstance(v,int):return ['int',str(v)]
 if isinstance(v,float):return ['float',v.hex()]
 raise ValueError('unsupported-sql-value')
def sql_state(path,key):
 global CURRENT_SESSIONS
 CURRENT_SESSIONS=[]
 assert path.is_file() and not path.is_symlink() and path.stat().st_size<=128*1024**2
 end=time.monotonic()+90;db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=5,isolation_level=None)
 try:
  db.execute('PRAGMA query_only=ON');db.execute('PRAGMA temp_store=MEMORY');db.execute('BEGIN')
  db.set_progress_handler(lambda:int(time.monotonic()>end),10000)
  assert db.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
  assert db.execute('PRAGMA foreign_key_check').fetchone() is None
  schema=db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').fetchall()
  names=[r[1] for r in schema if r[0]=='table'];assert {'users','session_history','notifiers','version_info'}<=set(names) and len(names)<=128
  assert db.execute("SELECT value FROM version_info WHERE key='version'").fetchall()==[('v2.18.2',)]
  tables={};count=0;size=0;session_fields={}
  for name in names:
   quoted='"'+name.replace('"','""')+'"';columns=db.execute('PRAGMA table_xinfo('+quoted+')').fetchall();rows=[]
   for row in db.execute('SELECT * FROM '+quoted):
    encoded=[cell(v)for v in row];size+=len(compact(encoded));count+=1
    assert count<=250000 and size<=32*1024**2 and time.monotonic()<=end
    rows.append(mac(key,['row',name,encoded]))
    if name=='sessions':
     values=dict(zip([c[1]for c in columns],row));identity=str(values['id']);CURRENT_SESSIONS.append(values)
     session_fields[identity]={column:mac(key,['session-cell',identity,column,cell(value)])for column,value in values.items()}
   tables[name]={'rows':len(rows),'columns':mac(key,['columns',name,columns]),'content':mac(key,['table',name,sorted(rows)])}
  return {'schema':mac(key,['schema',[[cell(v)for v in r]for r in schema]]),'tables':tables,'totalRows':count,'integrityOK':True,'foreignKeysOK':True,'applicationID':db.execute('PRAGMA application_id').fetchone()[0],'userVersion':db.execute('PRAGMA user_version').fetchone()[0],'sessionFields':session_fields}
 finally:db.close()
'''

OBSERVER = r'''
import sys,os,stat,configparser,resource,urllib.request,urllib.parse,re
resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
if os.geteuid()==0:os.setgroups([]);os.setgid(1000);os.setuid(1000)
assert os.geteuid()==os.getegid()==1000 and not os.getgroups()
request=json.loads(sys.stdin.buffer.read(1024*1024));key=bytes.fromhex(request['key']);assert len(key)==32
assert os.environ['PUID']==os.environ['PGID']=='1000' and os.environ['TAUTULLI_DOCKER']=='True'
root=Path('/config');entries={};total=0
def meta(p):
 s=p.lstat();return {'uid':s.st_uid,'gid':s.st_gid,'mode':stat.S_IMODE(s.st_mode)}
root_meta=meta(root)
for parent,dirs,files in os.walk(root,followlinks=False):
 for name in sorted(set(dirs+files)):
  p=Path(parent)/name;n=str(p.relative_to(root));r=meta(p);assert len(entries)<4096
  if p.is_symlink():r.update(kind='link',targetHMAC=mac(key,['link',n,os.readlink(p)]))
  elif p.is_dir():r['kind']='directory'
  else:
   s=p.lstat();assert stat.S_ISREG(s.st_mode) and s.st_size<=128*1024**2
   r.update(kind='file',bytes=s.st_size)
   if n not in {'tautulli.db','tautulli.db-wal','tautulli.db-shm'}:
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:
     before=os.fstat(fd);digest=hashlib.sha256();copied=0
     while True:
      b=os.read(fd,1024*1024)
      if not b:break
      copied+=len(b);total+=len(b);assert copied<=128*1024**2 and total<=512*1024**2;digest.update(b)
     after=os.fstat(fd);assert(before.st_dev,before.st_ino)==(after.st_dev,after.st_ino)
     if not n.startswith('logs/'):assert(before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
     r.update(bytes=copied,hmac=mac(key,['file',n,digest.hexdigest()]))
    finally:os.close(fd)
  entries[n]=r
prefix={};rotations={};anchors=request.get('logAnchors',{});rotating=set()
def log_matches(candidate,original,anchor,append=False):
 p=root/candidate
 if not p.exists()or p.is_symlink():return False
 s=p.lstat()
 if not stat.S_ISREG(s.st_mode)or[s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode)]!=[anchor[k]for k in ['uid','gid','mode']]:return False
 if append:
  if not anchor['bytes']<=s.st_size<=anchor['bytes']+16*1024**2:return False
 elif s.st_size!=anchor['bytes']:return False
 with p.open('rb')as f:
  digest=hashlib.sha256();remaining=anchor['bytes']
  while remaining:
   b=f.read(min(remaining,1024*1024))
   if not b:return False
   remaining-=len(b);digest.update(b)
 return mac(key,['file',original,digest.hexdigest()])==anchor['hmac']
for base in ['logs/plex_websocket.log','logs/tautulli.log','logs/tautulli_api.log']:
 if base not in anchors:continue
 family=[base]+[base+'.'+str(i)for i in range(1,6)];rotating.update(family)
 logger=Path(request['applicationDir'])/'plexpy/logger.py'
 assert hashlib.sha256(logger.read_bytes()).hexdigest()=='d021055900d76a04c8855760f7e741c2f4f9fafab3af46a754624d3fbbaa3555'
 count=None
 for number in range(6):
  if not log_matches(family[number],base,anchors[base],True):continue
  if any(not log_matches(family[i+number],family[i],anchors[family[i]])for i in range(1,6-number)if family[i]in anchors):continue
  if any(entries[family[i]]['bytes']>5000000 for i in range(number)if family[i]in entries):continue
  count=number;break
 assert count is not None,'source-verified-log-rotation:'+base
 rotations[base]={'rotations':count,'backupsReplacedByNativeRetention':count,'allOriginalLogsInAuthenticatedColdArchive':True,'loggerSHA256':'d021055900d76a04c8855760f7e741c2f4f9fafab3af46a754624d3fbbaa3555'}
for n,anchor in anchors.items():
 if n in rotating:continue
 assert n.startswith('logs/') and '..' not in Path(n).parts
 p=root/n;s=p.lstat();assert stat.S_ISREG(s.st_mode) and not p.is_symlink()
 assert [s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode)]==[anchor[k]for k in ['uid','gid','mode']]
 assert anchor['bytes']<=s.st_size<=anchor['bytes']+16*1024**2
 with p.open('rb')as f:
  digest=hashlib.sha256();remaining=anchor['bytes']
  while remaining:
   b=f.read(min(remaining,1024*1024));assert b;remaining-=len(b);digest.update(b)
 prefix[n]=mac(key,['file',n,digest.hexdigest()]);assert prefix[n]==anchor['hmac']
cfg=configparser.ConfigParser(interpolation=None,strict=True,empty_lines_in_values=False)
cfg.read_string((root/'config.ini').read_text(encoding='utf-8-sig'))
config={section:{k:v for k,v in cfg.items(section,raw=True)}for section in cfg.sections()}
sql=sql_state(root/'tautulli.db',key);runtime=[]
if request.get('verifyLivePlayback'):
 def setting(section,name,default=''):
  value=cfg.get(section,name,fallback=default).strip()
  return value[1:-1]if len(value)>=2 and value[0]==value[-1] and value[0]in ['\"',"'"]else value
 port=int(setting('General','http_port','8181'));api_key=setting('General','api_key');http_root=setting('General','http_root').strip('/')
 assert 0<port<65536 and len(api_key)==32 and all(c.isalnum()or c in '_/-'for c in http_root)
 url='http://127.0.0.1:'+str(port)+'/'+(http_root+'/'if http_root else'')+'api/v2?cmd=get_activity&out_type=json'
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 with opener.open(urllib.request.Request(url,headers={'X-Api-Key':api_key}),timeout=30)as response:
  raw=response.read(4*1024**2+1);assert response.status==200 and len(raw)<=4*1024**2
 activity=json.loads(raw)['response'];assert activity['result']=='success';streams=activity['data']['sessions']
 for row in CURRENT_SESSIONS:
  matches=[s for s in streams if all(str(s.get(k))==str(row[k])for k in ['session_key','rating_key','user_id'])];assert len(matches)==1
  live=matches[0];assert live['state']==row['state'] and row['state']in ['playing','paused','buffering']
  assert abs(int(live['view_offset'])-int(row['view_offset']))<=10000 and 0<=int(row['view_offset'])<=int(row['duration'])
  assert 0<=time.time()-int(row['stopped'])<=300
  runtime.append({'sessionIdentityHMAC':mac(key,['runtime-identity',[row[k]for k in ['session_key','rating_key','user_id']]]),'liveStateAndOffsetMatch':True,'heartbeatFresh':True})
print(json.dumps({'root':root_meta,'entries':entries,'fileCount':len(entries),'observedNonDatabaseBytes':total,'canonicalConfigHMAC':mac(key,['config',config]),'sql':sql,'logPrefixes':prefix,'logRotations':rotations,'livePlayback':runtime}))
'''


def mac(key, value):
    return hmac.new(key, json.dumps(value, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()


def call(args, payload=None):
    result = subprocess.run(SSH + [shlex.join(args)], input=payload, capture_output=True, timeout=240)
    if result.returncode != 0:
        failure = OUT / ('failed-read-' + uuid.uuid4().hex)
        if 'exec' in args:
            for suffix, data in [('stdout', result.stdout), ('stderr', result.stderr)]:
                with Path(str(failure) + '.' + suffix).open('xb') as stream:stream.write(data)
        else:
            with failure.with_suffix('.json').open('x') as stream:
                json.dump({'exitCode': result.returncode, 'metadataResponseNotPersisted': True}, stream)
    assert result.returncode == 0 and len(result.stdout) <= 8 * 1024**2
    return result.stdout


def get(kind, name, namespace='plex'):
    return json.loads(call(['kubectl', '-n', namespace, 'get', kind, name, '-o', 'json']))


def fence(image, revision, key):
    d, h, pvc = get('deployment', 'tautulli'), get('helmrelease', 'tautulli', 'flux-system'), get('pvc', 'tautulli-data-0')
    assert d['metadata']['uid'] == '9db52ebb-23c8-47c6-82c8-ebde3b0a2775'
    assert h['metadata']['uid'] == 'e5aa088f-22a3-4f47-b7c4-094be5354bf4'
    assert pvc['metadata']['uid'] == '97eb095e-37ec-4185-80ed-4d8f3c19f486' and pvc['status']['phase'] == 'Bound'
    assert d['spec']['replicas'] == 1 and all(d['status'].get(k) == 1 for k in ['replicas', 'updatedReplicas', 'availableReplicas', 'readyReplicas'])
    assert d['status']['observedGeneration'] == d['metadata']['generation']
    assert h['status']['observedGeneration'] == h['metadata']['generation'] and h['spec']['values']['replicaCount'] == 1
    assert any(c['type'] == 'Ready' and c['status'] == 'True' for c in h['status']['conditions'])
    source = get('gitrepository', 'branconet-charts', 'flux-system')
    assert source['status']['artifact']['revision'] == 'validated@sha1:' + revision
    assert h['status']['lastAttemptedRevision'].endswith('+' + revision[:12])
    spec = json.loads(json.dumps(d['spec']));containers = spec['template']['spec']['containers']
    assert len(containers) == 1 and containers[0]['image'] == image
    assert containers[0]['envFrom'] == [{'secretRef': {'name': 'tautulli-runtime'}}]
    assert containers[0]['resources'] == {'requests': {'cpu': '25m', 'memory': '64Mi'}}
    containers[0]['image'] = '<maintained-image>'
    spec['template']['metadata']['annotations'].pop('branconet.lan/security-restart', None)
    pods = get('pods', '-l=app=tautulli')['items'];assert len(pods) == 1
    pod = pods[0];assert not pod['metadata'].get('deletionTimestamp') and pod['status']['phase'] == 'Running'
    cs = pod['status']['containerStatuses'][0];assert cs['ready'] and cs.get('restartCount', 0) == 0
    assert pod['spec']['containers'][0]['image'] == image
    assert cs['imageID'].rsplit('@', 1)[-1] in [image.rsplit('@', 1)[-1], CHILD if image == NEW else image.rsplit('@', 1)[-1]]
    owners = [r for r in pod['metadata']['ownerReferences'] if r.get('controller')];assert len(owners) == 1 and owners[0]['kind'] == 'ReplicaSet'
    rs = get('replicaset', owners[0]['name']);assert rs['metadata']['uid'] == owners[0]['uid']
    assert any(r.get('controller') and r['uid'] == d['metadata']['uid'] for r in rs['metadata']['ownerReferences'])
    secret, pv = get('secret', 'tautulli-runtime'), get('pv', pvc['spec']['volumeName'])
    assert pv['spec']['claimRef']['uid'] == pvc['metadata']['uid'] and pv['spec']['csi']['driver'] == 'driver.longhorn.io'
    stable = {'deployment': mac(key, spec), 'pvc': mac(key, pvc['spec']), 'pvUID': pv['metadata']['uid'], 'pv': mac(key, pv['spec']),
              'secretUID': secret['metadata']['uid'], 'secretRV': secret['metadata']['resourceVersion'],
              'secret': mac(key, {'type': secret['type'], 'data': secret.get('data', {})})}
    for kind, names in [('service', ['tautulli', 'tautulli-published']), ('ingress', ['tautulli-http', 'tautulli-https'])]:
        for name in names:
            r = get(kind, name);stable[kind + '/' + name] = {'uid': r['metadata']['uid'], 'spec': mac(key, r['spec']), 'annotations': mac(key, r['metadata'].get('annotations', {}))}
    return {'pod': pod['metadata']['name'], 'podUID': pod['metadata']['uid'], 'imageID': cs['imageID'], 'stable': stable}


def request(host, port, path):
    tls = port == 443;trusted = True;fingerprint = None
    if tls:
        try:
            with socket.create_connection((host, port), timeout=5) as raw:
                with ssl.create_default_context().wrap_socket(raw, server_hostname='tautulli.branconet.lan'):pass
            context = ssl.create_default_context()
        except ssl.SSLCertVerificationError as error:
            assert error.verify_code == 18;trusted = False;context = ssl._create_unverified_context()
            with socket.create_connection((host, port), timeout=5) as raw:
                with context.wrap_socket(raw, server_hostname='tautulli.branconet.lan') as stream:der = stream.getpeercert(binary_form=True)
            cert = subprocess.run(['openssl', 'x509', '-inform', 'DER', '-noout', '-subject', '-issuer', '-nameopt', 'RFC2253'], input=der, capture_output=True, timeout=10)
            assert cert.returncode == 0 and cert.stdout.decode().splitlines() == ['subject=CN=TRAEFIK DEFAULT CERT', 'issuer=CN=TRAEFIK DEFAULT CERT']
            fingerprint = hashlib.sha256(der).hexdigest()
        connection = http.client.HTTPSConnection(host, port, context=context, timeout=15)
    else:connection = http.client.HTTPConnection(host, port, timeout=15)
    try:
        connection.request('GET', path, headers={'Host': 'tautulli.branconet.lan'})
        response = connection.getresponse();body = response.read(1024**2 + 1);assert len(body) <= 1024**2
        if path == '/status':assert response.status == 200 and json.loads(body) == {'result': 'success', 'message': 'Ok'}
        elif path == '/auth/login':assert response.status == 200 and b'Tautulli' in body
        else:assert response.status in [302, 303] and any(p in response.getheader('Location', '') for p in ['/auth/login', '/auth/logout'])
        return {'status': response.status, 'authenticatedTLS': trusted if tls else None, 'certificateSHA256': fingerprint}
    finally:connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['baseline', 'after', 'restart'], required=True)
    parser.add_argument('--revision', required=True)
    a = parser.parse_args();assert os.getuid() == 1000 and len(a.revision) == 40;os.umask(0o077)
    key = (OUT / 'observation.key').read_bytes();assert len(key) == 32
    path = OUT / (a.phase + '.json');assert not path.exists()
    baseline = json.loads((OUT / 'baseline.json').read_text()) if a.phase != 'baseline' else None
    image = OLD if baseline is None else NEW;before = fence(image, a.revision, key)
    source = ast.parse(Path(__file__).with_name('qualify-tautulli.py').read_bytes())
    api = next(ast.literal_eval(n.value) for n in source.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'POD_PROGRAM' for t in n.targets))
    assert api.count("info['tautulli_python_version']=='3.13.17'") == 1
    api = api.replace("info['tautulli_python_version']=='3.13.17'", "info['tautulli_python_version']=='.'.join(map(str,sys.version_info[:3]))")
    api = api.replace("'python_version':'3.13.17'", "'python_version':info['tautulli_python_version']")
    if image == NEW:
        assert api.count("Path('/app/plexpy')") == 1
        api = api.replace("Path('/app/plexpy')", "Path('/app/tautulli/plexpy')")
    api = 'import sys\n' + api
    functional = json.loads(call(['kubectl', '-n', 'plex', 'exec', before['pod'], '-c', 'tautulli', '--', 'python3', '-B', '-c', api]))
    assert functional['passed'] and functional['configured_and_actual_plex_identity_match']
    cold = json.loads((OUT / 'cold-file-reference.json').read_text()) if baseline else None
    assert not cold or cold['coldArchiveFullyAuthenticated'] and cold['onlineCanonicalConfigurationMatchesCold']
    anchors = {n:r for n,r in cold['entries'].items() if n.startswith('logs/') and r['kind'] == 'file'} if cold else {}
    observation = json.loads(call(['kubectl', '-n', 'plex', 'exec', '-i', before['pod'], '-c', 'tautulli', '--', 'python3', '-B', '-c', SQL + OBSERVER], json.dumps({'key': key.hex(), 'logAnchors': anchors, 'verifyLivePlayback': False, 'applicationDir': '/app/tautulli' if image == NEW else '/app'}).encode()))
    observation_path = OUT / (a.phase + '-observation-' + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12] + '.json')
    with observation_path.open('x') as stream:json.dump({'writer': before, 'observation': observation, 'functional': functional}, stream, indent=2)
    assert observation['root']['uid'] == observation['root']['gid'] == 1000
    assert all(r['uid'] == r['gid'] == 1000 for r in observation['entries'].values()), 'vendor-entrypoint-ownership-precondition'
    if baseline:
        assert before['stable'] == baseline['writer']['stable'], 'native-resource-identities-and-complete-specs'
        original = cold;assert observation['root'] == original['root']
        assert observation['canonicalConfigHMAC'] == original['canonicalConfigHMAC'], 'complete-canonical-configuration'
        data = json.loads((OUT / (a.phase + '-data-audit.json')).read_text())
        caches = json.loads((OUT / (a.phase + '-cache-proof.json')).read_text())
        for proof in [data, caches]:
            assert proof['passed'] and proof['revision'] == a.revision and proof['writer'] == before
        assert data['sourceSHA256'] == hashlib.sha256(Path(__file__).with_name('audit-upstream-tautulli-data.py').read_bytes()).hexdigest()
        assert caches['sourceSHA256'] == hashlib.sha256(Path(__file__).with_name('verify-upstream-tautulli-caches.py').read_bytes()).hexdigest()
        assert data['databaseCopiesUnchanged'] and data['completeSchemaEqual'] and data['optimizerStatsMatchSourceAnalyze']
        for name, sha in data['databaseSHA256'].items():
            assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == sha
        sql_scope = {};exec(SQL, sql_scope)
        expected_version_hashes = {sql_scope['mac'](key, ['file', 'version.lock', hashlib.sha256(value).hexdigest()]) for value in [b'v2.18.2', b'v2.18.2\n']}
        left, right = original['entries'], observation['entries']
        sidecars = {'tautulli.db-wal', 'tautulli.db-shm'}
        assert set(left) - set(right) <= sidecars | set(data['completedSessionCachePaths']), 'original-file-set'
        for name, row in left.items():
            if name not in right:continue
            current = right[name]
            if name in ['tautulli.db', 'tautulli.db-wal', 'tautulli.db-shm']:
                assert {k:v for k,v in row.items() if k != 'bytes'} == {k:v for k,v in current.items() if k != 'bytes'}
            elif name.startswith('logs/') and row['kind'] == 'file':
                family = re.sub(r'\.[1-5]$', '', name)
                if family in observation['logRotations']:
                    assert all(current[k] == row[k] for k in ['uid', 'gid', 'mode', 'kind'])
                else:assert observation['logPrefixes'][name] == row['hmac']
            elif name == 'config.ini':assert all(current[k] == row[k] for k in ['uid', 'gid', 'mode', 'kind'])
            elif name == 'version.lock':
                assert current['hmac'] in expected_version_hashes
                assert all(current[k] == row[k] for k in ['uid', 'gid', 'mode', 'kind'])
            elif name in caches['files']:
                assert current['hmac'] == caches['files'][name]['hmac'] and caches['files'][name]['completeDataVerified']
                assert all(current[k] == row[k] for k in ['uid', 'gid', 'mode', 'kind'])
            else:assert current == row, 'original-file:' + name
        if a.phase == 'restart':
            previous = json.loads((OUT / 'after.json').read_text());assert previous['writer']['podUID'] != before['podUID']
    routes = {host + ':' + str(port) + path:request(host, port, path) for host in ['192.168.0.4', '192.168.0.5', '192.168.0.6'] for port in [9119, 80, 443] for path in ['/status', '/', '/auth/login']}
    assert fence(image, a.revision, key) == before
    result = {'passed': True, 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'phase': a.phase, 'revision': a.revision,
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'writer': before, 'observation': observation, 'functional': functional,
              'routes': routes, 'personalLoginVerified': False, 'rawSQLOrCredentialsReturned': False, 'applicationModifiedByObserver': False}
    with path.open('x') as stream:json.dump(result, stream, indent=2);stream.write('\n')
    print(json.dumps({'passed': True, 'receipt': str(path), 'podUID': before['podUID'], 'fileCount': observation['fileCount'], 'tables': len(observation['sql']['tables']),
                      'sqlRows': observation['sql']['totalRows'], 'users': observation['sql']['tables']['users']['rows'], 'history': observation['sql']['tables']['session_history']['rows'], 'routes': len(routes)}))


if __name__ == '__main__':main()
