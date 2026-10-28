#!/usr/bin/env python3
"""Exact native identities, complete live files/SQL and public routes for Mealie."""
import argparse
import ast
import base64
import datetime
import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import shlex
import socket
import sqlite3
import ssl
import subprocess
import traceback
import uuid

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'upstream-mealie-20261026'
OLD = 'docker.io/library/mealie-security-20261023@sha256:a3fc64d6777e22de915a97d3dbb77e1edc5d5998be683b4a1bed8968a26b2bb9'
NEW = 'ghcr.io/mealie-recipes/mealie:v3.29.0@sha256:78eb28b8776d0bad40c5e605c72b3f4f5976793e491558c7dcbdfc04c835d4bc'
CHILD = 'sha256:243e33ea66e71b2094cb1f9c9167af24452405a33fc899a1dc7359dc210506f8'
STATIC = '/opt/mealie/lib/python3.14/site-packages/mealie/frontend'
RUNTIME_PATH = '/opt/mealie/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
CONTEXT = {'runAsUser': 0, 'runAsGroup': 999, 'runAsNonRoot': False,
           'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL'], 'add': ['DAC_OVERRIDE']}}
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'IdentitiesOnly=yes',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
OBSERVER = r'''
import sys,stat,resource
resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
request=json.loads(sys.stdin.buffer.read(16384))
if request.get('originalOwnerReadOnly'):
 assert os.geteuid()==0 and os.getegid()==999
 status=Path('/proc/self/status').read_text().splitlines();fields=dict(x.split(':',1)for x in status if ':'in x)
 assert int(fields['CapEff'].strip(),16)==2 and fields['NoNewPrivs'].strip()=='1'
else:
 if os.geteuid()==0:os.setgroups([]);os.setgid(1000);os.setuid(1000)
 assert os.geteuid()==1000
key=bytes.fromhex(request['key']);root=Path('/app/data');entries={};total=0
def info(p):
 s=p.lstat();return {'uid':s.st_uid,'gid':s.st_gid,'mode':stat.S_IMODE(s.st_mode)}
for parent,dirs,files in os.walk(root,followlinks=False):
 for name in sorted(set(dirs+files)):
  p=Path(parent)/name;n=str(p.relative_to(root));r=info(p)
  if p.is_symlink():r.update(kind='link',target=p.readlink().as_posix())
  elif p.is_dir():r['kind']='directory'
  else:
   assert stat.S_ISREG(p.lstat().st_mode)
   if n in ['mealie.db','mealie.db-wal','mealie.db-shm']:
    if n=='mealie.db':entries[n]={'kind':'sqlite',**r}
    continue
   h=hashlib.sha256();count=0
   with p.open('rb')as stream:
    for b in iter(lambda:stream.read(1024**2),b''):h.update(b);count+=len(b);assert count<=1024**3
   total+=count;assert total<=1024**3
   r.update(kind='file',bytes=count,contentHMAC=hmac.new(key,(n+'\0'+h.hexdigest()).encode(),hashlib.sha256).hexdigest())
  entries[n]=r;assert len(entries)<=4096
entries['.']={'kind':'directory',**info(root)}
anchor=request.get('logAnchor');prefix=None
if anchor:
 p=root/'mealie.log';assert p.is_file()and not p.is_symlink();assert anchor['bytes']<=p.stat().st_size<=anchor['bytes']+16*1024**2
 with p.open('rb')as stream:
  h=hashlib.sha256();left=anchor['bytes']
  while left:b=stream.read(min(left,1024**2));assert b;h.update(b);left-=len(b)
 prefix=hmac.new(key,('mealie.log\0'+h.hexdigest()).encode(),hashlib.sha256).hexdigest()
path=root/'mealie.db';state=sql_state(path,key)
db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=5);db.execute('PRAGMA query_only=ON');memory=sqlite3.connect(':memory:');db.backup(memory);db.close()
if hasattr(memory,'serialize'):kind='serialized';data=memory.serialize()
else:kind='sql-dump';data=('\n'.join(memory.iterdump())+'\n').encode()
assert len(data)<=64*1024**2
print(json.dumps({'files':entries,'fileCount':len(entries),'observedNonDatabaseBytes':total,'logPrefixHMAC':prefix,'state':state,'format':kind,'snapshot':base64.b64encode(data).decode(),'applicationID':memory.execute('PRAGMA application_id').fetchone()[0],'userVersion':memory.execute('PRAGMA user_version').fetchone()[0]}));memory.close()
'''


def mac(key, value):
    return hmac.new(key, json.dumps(value, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()


def call(args, payload=None):
    p = subprocess.run(SSH + [shlex.join(args)], input=payload, capture_output=True, timeout=150)
    assert p.returncode == 0 and len(p.stdout) <= 128 * 1024**2
    return p.stdout


def get(kind, name, namespace='mealie'):
    return json.loads(call(['kubectl', '-n', namespace, 'get', kind, name, '-o', 'json']))


def fence(image, revision, key):
    d, h, pvc = get('deployment', 'mealie'), get('helmrelease', 'mealie', 'flux-system'), get('pvc', 'mealie-data-0')
    assert d['metadata']['uid'] == 'f0dddcf0-0d07-4b56-a3ec-0cd59d484b93'
    assert h['metadata']['uid'] == '2d878107-ff9f-46f6-9260-2e8f3a94e38c'
    assert pvc['metadata']['uid'] == 'd015a16d-5098-4253-ade1-72d80af87f18' and pvc['status']['phase'] == 'Bound'
    assert d['spec']['replicas'] == 1 and all(d['status'].get(k) == 1 for k in ['replicas', 'updatedReplicas', 'availableReplicas', 'readyReplicas'])
    assert d['status']['observedGeneration'] == d['metadata']['generation']
    assert h['status']['observedGeneration'] == h['metadata']['generation'] and h['spec']['values']['replicaCount'] == 1
    assert any(c['type'] == 'Ready' and c['status'] == 'True' for c in h['status']['conditions'])
    source = get('gitrepository', 'branconet-charts', 'flux-system')
    assert source['status']['artifact']['revision'] == 'validated@sha1:' + revision
    assert h['status']['lastAttemptedRevision'].endswith('+' + revision[:12])
    spec = json.loads(json.dumps(d['spec']))
    c = spec['template']['spec']['containers'][0]
    assert len(spec['template']['spec']['containers']) == 1 and c['image'] == image
    assert c['envFrom'] == [{'secretRef': {'name': 'mealie-runtime'}}]
    if image == NEW:
        assert c['env'] == [{'name': 'STATIC_FILES', 'value': STATIC}, {'name': 'PATH', 'value': RUNTIME_PATH}] and c['securityContext'] == CONTEXT
        assert c['command'] == ['/opt/mealie/bin/mealie'] and c['workingDir'] == '/app'
        c['env'] = []
        c.pop('securityContext')
        c.pop('command')
        c.pop('workingDir')
    else:
        assert image == OLD and not c.get('env') and not c.get('securityContext')
        c['env'] = []
    c['image'] = '<maintained-image>'
    spec['template']['metadata'].get('annotations', {}).pop('branconet.lan/security-restart', None)
    pod_list = json.loads(call(['kubectl', '-n', 'mealie', 'get', 'pods', '-l', 'app=mealie', '-o', 'json']))['items']
    assert len(pod_list) == 1
    pod = pod_list[0]
    assert not pod['metadata'].get('deletionTimestamp') and pod['status']['phase'] == 'Running'
    cs = pod['status']['containerStatuses'][0]
    assert cs['ready'] and pod['spec']['containers'][0]['image'] == image
    if image == NEW:
        assert pod['spec']['containers'][0]['securityContext'] == CONTEXT
    assert cs['imageID'].rsplit('@', 1)[-1] in [image.rsplit('@', 1)[-1], CHILD if image == NEW else image.rsplit('@', 1)[-1]]
    owners = [x for x in pod['metadata']['ownerReferences'] if x.get('controller')]
    assert len(owners) == 1 and owners[0]['kind'] == 'ReplicaSet'
    rs = get('replicaset', owners[0]['name'])
    assert rs['metadata']['uid'] == owners[0]['uid'] and any(x.get('controller') and x['uid'] == d['metadata']['uid'] for x in rs['metadata']['ownerReferences'])
    secret, pv = get('secret', 'mealie-runtime'), get('pv', pvc['spec']['volumeName'])
    assert secret['metadata']['uid'] == '8142b20f-d201-44ff-97b8-f72c93d15557'
    assert pv['metadata']['uid'] == '402d45ec-840b-4a57-9c7e-0cede840539d' and pv['spec']['claimRef']['uid'] == pvc['metadata']['uid']
    assert pv['spec']['csi']['driver'] == 'driver.longhorn.io'
    stable = {'deployment': mac(key, spec), 'pvc': mac(key, pvc['spec']), 'pv': mac(key, pv['spec']),
              'secretUID': secret['metadata']['uid'], 'secretRV': secret['metadata']['resourceVersion'],
              'secret': mac(key, {'type': secret['type'], 'data': secret.get('data', {})})}
    for kind, names in [('service', ['mealie', 'mealie-published']), ('ingress', ['mealie-http', 'mealie-https'])]:
        for name in names:
            r = get(kind, name)
            stable[kind + '/' + name] = {'uid': r['metadata']['uid'], 'spec': mac(key, r['spec']),
                                       'annotations': mac(key, r['metadata'].get('annotations', {}))}
    return {'pod': pod['metadata']['name'], 'podUID': pod['metadata']['uid'], 'imageID': cs['imageID'], 'stable': stable}


def request(host, port, path='/', tls=False):
    trusted = True
    fingerprint = None
    if tls:
        try:
            with socket.create_connection((host, port), timeout=5) as raw:
                with ssl.create_default_context().wrap_socket(raw, server_hostname='mealie.branconet.lan'):
                    pass
            context = ssl.create_default_context()
        except ssl.SSLCertVerificationError as error:
            assert error.verify_code == 18
            trusted = False
            context = ssl._create_unverified_context()
            with socket.create_connection((host, port), timeout=5) as raw:
                with context.wrap_socket(raw, server_hostname='mealie.branconet.lan') as stream:
                    der = stream.getpeercert(binary_form=True)
            certificate = subprocess.run(['openssl', 'x509', '-inform', 'DER', '-noout', '-subject', '-issuer', '-nameopt', 'RFC2253'], input=der, capture_output=True, timeout=10)
            assert certificate.returncode == 0 and certificate.stdout.decode().splitlines() == ['subject=CN=TRAEFIK DEFAULT CERT', 'issuer=CN=TRAEFIK DEFAULT CERT']
            fingerprint = hashlib.sha256(der).hexdigest()
        connection = http.client.HTTPSConnection(host, port, context=context, timeout=15)
    else:
        connection = http.client.HTTPConnection(host, port, timeout=15)
    try:
        connection.request('GET', path, headers={'Host': 'mealie.branconet.lan'})
        response = connection.getresponse()
        body = response.read(8 * 1024**2 + 1)
        assert response.status == 200 and len(body) <= 8 * 1024**2
        return body, {'status': response.status, 'authenticatedTLS': trusted if tls else None, 'certificateSHA256': fingerprint}
    finally:
        connection.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', choices=['baseline', 'after', 'restart'], required=True)
    p.add_argument('--revision', required=True)
    a = p.parse_args()
    assert os.getuid() == 1000 and len(a.revision) == 40
    os.umask(0o077)
    work = OUT / 'production'
    work.mkdir(mode=0o700, exist_ok=True)
    target = work / (a.phase + '.json')
    assert not target.exists()
    image = OLD if a.phase == 'baseline' else NEW
    key = (OUT / 'db-copy/observation.key').read_bytes()
    source_tree = ast.parse(Path(__file__).with_name('qualify-mealie.py').read_bytes())
    program = next(ast.literal_eval(n.value) for n in source_tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'STATE_SOURCE' for t in n.targets))
    state_module = {}
    exec(program, state_module)
    baseline = json.loads((work / 'baseline.json').read_text()) if a.phase != 'baseline' else None
    payload = {'key': key.hex(), 'originalOwnerReadOnly': image == NEW}
    if baseline and 'mealie.log' in baseline['observation']['files']:
        payload['logAnchor'] = baseline['observation']['files']['mealie.log']
    start = fence(image, a.revision, key)
    interpreter = '/opt/mealie/bin/python' if image == NEW else 'python'
    body = call(['kubectl', '-n', 'mealie', 'exec', '-i', start['pod'], '--', interpreter, '-I', '-B', '-c', program + OBSERVER], json.dumps(payload).encode())
    observation = json.loads(body)
    snapshot = base64.b64decode(observation.pop('snapshot'), validate=True)
    db = work / (a.phase + '.db')
    if db.exists():
        # Reuse an unchanged snapshot after an observer-only route failure;
        # never open a retained database for writing or replace failed evidence.
        assert state_module['sql_state'](db, key) == observation['state']
    else:
        connection = sqlite3.connect(db)
        try:
            if observation['format'] == 'serialized':
                memory = sqlite3.connect(':memory:')
                try:
                    memory.deserialize(snapshot)
                    memory.backup(connection)
                finally:
                    memory.close()
            else:
                connection.executescript(snapshot.decode())
            connection.execute('PRAGMA application_id=' + str(observation['applicationID']))
            connection.execute('PRAGMA user_version=' + str(observation['userVersion']))
        finally:
            connection.close()
    assert state_module['sql_state'](db, key) == observation['state']
    with (work / (a.phase + '-observation-' + uuid.uuid4().hex + '.json')).open('x') as stream:
        json.dump({'passed': False, 'scope': 'Observation captured before acceptance checks', 'writer': start, 'observation': observation}, stream)
    if a.phase == 'baseline':
        assert observation['state'] == json.loads((OUT / 'db-copy/source.json').read_text())['state'], 'original-qualification-state-still-current'
    else:
        assert start['stable'] == baseline['writer']['stable'] and start['podUID'] != baseline['writer']['podUID']
        left, right = dict(baseline['observation']['files']), dict(observation['files'])
        if 'mealie.log' in left:
            anchor = left.pop('mealie.log')
            live_log = right.pop('mealie.log')
            assert observation['logPrefixHMAC'] == anchor['contentHMAC']
            assert all(live_log[k] == anchor[k] for k in ['uid', 'gid', 'mode', 'kind'])
        if '.session_secret' not in left:
            session = right.pop('.session_secret')
            assert session['kind'] == 'file' and (session['uid'], session['gid']) in [(1000, 1000), (0, 999)] and session['bytes'] == 64 and session['mode'] in [0o600, 0o644]
        assert left == right, 'complete-original-files-and-metadata'
        if a.phase == 'restart':
            previous = json.loads((work / 'after.json').read_text())
            assert start['podUID'] != previous['writer']['podUID']
            assert observation['state'] == previous['observation']['state'], 'restart-full-SQL'
            assert observation['files'].get('.session_secret') == previous['observation']['files'].get('.session_secret'), 'restart-session-key'
    routes = {}
    for host in ['192.168.0.4', '192.168.0.5', '192.168.0.6']:
        for port in [8089, 80, 443]:
            html, route = request(host, port, tls=port == 443)
            assert b'<html' in html.lower()
            routes[host + ':' + str(port)] = route
    about, _ = request('192.168.0.4', 8089, '/api/app/about')
    version = json.loads(about)['version']
    assert version.removeprefix('v') == ('1.0.0-RC1.1' if image == OLD else '3.29.0')
    schema, _ = request('192.168.0.4', 8089, '/openapi.json')
    paths = json.loads(schema)['paths']
    assert len(paths) >= 100 and '/api/users/self' in paths and '/api/recipes' in paths
    assert fence(image, a.revision, key) == start
    report = {'passed': True, 'phase': a.phase, 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'revision': a.revision, 'writer': start, 'observation': observation, 'routes': routes,
              'version': version, 'apiPathCount': len(paths), 'databaseCopy': str(db),
              'personalLoginVerified': False, 'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with target.open('x') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({'passed': True, 'phase': a.phase, 'files': observation['fileCount'],
                      'tables': len(observation['state']['tables']), 'rows': observation['state']['total_rows'],
                      'counts': observation['state']['critical_counts'], 'version': version, 'routes': len(routes)}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        failed = OUT / ('qualification-failed-' + uuid.uuid4().hex + '.json')
        with failed.open('x') as stream:
            json.dump({'passed': False, 'errorType': type(error).__name__, 'tracebackWithoutLocals': traceback.format_exc()}, stream)
        print(json.dumps({'passed': False, 'errorType': type(error).__name__, 'failureReceipt': str(failed), 'rawDetailsSuppressed': True}))
        raise SystemExit(1)
