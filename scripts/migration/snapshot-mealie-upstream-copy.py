#!/usr/bin/env python3
"""Read-only transactional Mealie snapshot for one isolated vendor migration."""
import ast
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import sqlite3
import subprocess
import sys

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'upstream-mealie-20261026'
IMAGE = 'docker.io/library/mealie-security-20261023@sha256:a3fc64d6777e22de915a97d3dbb77e1edc5d5998be683b4a1bed8968a26b2bb9'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'IdentitiesOnly=yes',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
MASTER = r'''
import subprocess,json,sys,hashlib,hmac,resource
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
request=json.loads(sys.stdin.buffer.read(131072));key=bytes.fromhex(request['key'])
def get(kind,name,ns='mealie'):
 p=subprocess.run(['kubectl','-n',ns,'get',kind,name,'-o','json'],capture_output=True,timeout=30)
 assert p.returncode==0 and len(p.stdout)<=4*1024**2
 return json.loads(p.stdout)
def fence():
 d=get('deployment','mealie');h=get('helmrelease','mealie','flux-system');v=get('pvc','mealie-data-0');s=get('secret','mealie-runtime')
 assert d['metadata']['uid']=='f0dddcf0-0d07-4b56-a3ec-0cd59d484b93'and h['metadata']['uid']=='2d878107-ff9f-46f6-9260-2e8f3a94e38c'
 assert v['metadata']['uid']=='d015a16d-5098-4253-ade1-72d80af87f18'and v['status']['phase']=='Bound'and v['spec']['storageClassName']=='longhorn'
 assert s['metadata']['uid']=='8142b20f-d201-44ff-97b8-f72c93d15557'
 assert d['spec']['replicas']==1 and all(d['status'].get(k)==1 for k in ['replicas','readyReplicas','updatedReplicas','availableReplicas'])
 assert d['spec']['template']['spec']['containers'][0]['image']==request['image']and h['spec']['values']['replicaCount']==1
 assert any(c['type']=='Ready'and c['status']=='True'for c in h['status']['conditions'])
 p=subprocess.run(['kubectl','-n','mealie','get','pods','-l','app=mealie','-o','json'],capture_output=True,timeout=30);assert p.returncode==0
 pods=json.loads(p.stdout)['items'];assert len(pods)==1;pod=pods[0]
 assert pod['status']['phase']=='Running'and not pod['metadata'].get('deletionTimestamp')and pod['status']['containerStatuses'][0]['ready']and pod['spec']['containers'][0]['image']==request['image']
 stable={'deploymentSpec':d['spec'],'releaseUID':h['metadata']['uid'],'claim':v['spec'],'secretUID':s['metadata']['uid'],'secretRV':s['metadata']['resourceVersion'],'secretType':s['type'],'secretData':s.get('data',{})}
 return pod['metadata']['name'],pod['metadata']['uid'],hmac.new(key,json.dumps(stable,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()
before=fence();p=subprocess.run(['kubectl','-n','mealie','exec','-i',before[0],'--','python','-I','-B','-c',request['observer']],input=json.dumps({'key':request['key']}).encode(),capture_output=True,timeout=120)
assert p.returncode==0 and len(p.stdout)<=128*1024**2 and fence()==before
packet=json.loads(p.stdout);packet['sourceBinding']={'pod':before[0],'podUID':before[1],'nativeObjectsHMAC':before[2],'image':request['image']};sys.stdout.buffer.write(json.dumps(packet).encode())
'''


def main():
    assert sys.argv[1:] == ['--apply'] and os.getuid() == 1000
    assert OUT.is_dir() and OUT.resolve() == OUT and not OUT.stat().st_mode & 0o077
    os.umask(0o077)
    os.environ.update(TMPDIR=str(OUT / 'tmp'), TMP=str(OUT / 'tmp'), TEMP=str(OUT / 'tmp'))
    source = Path(__file__).with_name('qualify-mealie.py')
    tree = ast.parse(source.read_bytes())
    program = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'STATE_SOURCE' for t in n.targets))
    scope = {}
    exec(program, scope)
    directory = OUT / 'db-copy'
    directory.mkdir(mode=0o700)
    key = os.urandom(32)
    (directory / 'observation.key').write_bytes(key)
    observer = program + r'''
import sys,resource
resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
if os.geteuid()==0:os.setgroups([]);os.setgid(1000);os.setuid(1000)
assert os.geteuid()==1000
request=json.loads(sys.stdin.buffer.read(4096));key=bytes.fromhex(request['key']);path=Path('/app/data/mealie.db')
db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=5);db.execute('PRAGMA query_only=ON');db.execute('BEGIN');db.execute('SELECT count(*)FROM sqlite_master').fetchone()
memory=sqlite3.connect(':memory:');db.backup(memory);db.close()
assert memory.execute('PRAGMA integrity_check').fetchall()==[('ok',)]and memory.execute('PRAGMA foreign_key_check').fetchone()is None
if hasattr(memory,'serialize'):kind='serialized';data=memory.serialize()
else:kind='sql-dump';data=('\n'.join(memory.iterdump())+'\n').encode()
assert len(data)<=64*1024**2
print(json.dumps({'format':kind,'snapshot':base64.b64encode(data).decode(),'snapshotSHA256':hashlib.sha256(data).hexdigest(),'applicationID':memory.execute('PRAGMA application_id').fetchone()[0],'userVersion':memory.execute('PRAGMA user_version').fetchone()[0]}))
memory.close()
'''
    payload = {'key': key.hex(), 'image': IMAGE, 'observer': observer}
    p = subprocess.run(SSH + [shlex.join(['python3', '-B', '-c', MASTER])], input=json.dumps(payload).encode(),
                       capture_output=True, timeout=180)
    assert p.returncode == 0 and len(p.stdout) <= 128 * 1024**2
    packet = json.loads(p.stdout)
    data = base64.b64decode(packet.pop('snapshot'), validate=True)
    assert len(data) <= 64 * 1024**2 and hashlib.sha256(data).hexdigest() == packet['snapshotSHA256']
    age = ROOT.parent / 'bin/age'
    assert hashlib.sha256(age.read_bytes()).hexdigest() == 'eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c'
    cipher = directory / 'transactional-snapshot.age'
    with cipher.open('xb') as stream:
        subprocess.run([str(age), '-R', '/home/brajam/.ssh/id_ed25519.pub'], input=data,
                       stdout=stream, stderr=subprocess.DEVNULL, check=True, timeout=30)
    recovered = subprocess.run([str(age), '-d', '-i', '/home/brajam/.ssh/id_ed25519', str(cipher)],
                               capture_output=True, check=True, timeout=30)
    assert recovered.stdout == data
    for name in ['sqlite-original.db', 'sqlite-migration.db']:
        path = directory / name
        connection = sqlite3.connect(path)
        try:
            if packet['format'] == 'serialized':
                memory = sqlite3.connect(':memory:')
                try:
                    memory.deserialize(data)
                    memory.backup(connection)
                finally:
                    memory.close()
            else:
                connection.executescript(data.decode())
            connection.execute('PRAGMA application_id=' + str(int(packet['applicationID'])))
            connection.execute('PRAGMA user_version=' + str(int(packet['userVersion'])))
        finally:
            connection.close()
    original = scope['sql_state'](directory / 'sqlite-original.db', key)
    assert original == scope['sql_state'](directory / 'sqlite-migration.db', key)
    report = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'passed': True,
              'sourceBinding': packet['sourceBinding'], 'transactional': True, 'productionChanged': False,
              'allCopiesInsideDeclaredRoot': True, 'encryptedArchive': str(cipher),
              'archiveSHA256': hashlib.sha256(cipher.read_bytes()).hexdigest(), 'archiveBytes': cipher.stat().st_size,
              'fullAgeAuthentication': True, 'snapshotFormat': packet['format'], 'state': original,
              'stateObserverSHA256': hashlib.sha256(program.encode()).hexdigest()}
    with (directory / 'source.json').open('x') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != 'state'}))
    print(json.dumps({'tables': len(original['tables']), 'rows': original['total_rows'], 'criticalCounts': original['critical_counts']}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'passed': False, 'failureCategory': type(error).__name__, 'rawDetailsSuppressed': True}))
        raise SystemExit(1)
