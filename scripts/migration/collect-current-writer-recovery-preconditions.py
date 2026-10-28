"""Read-only current Ruckus/Ingenium recovery metadata and Ruckus lock capability.

Does not acquire a lock, stop a writer, request a snapshot or change credentials.
Native credential values remain in remote RAM/stdin and never enter output.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
R = F / 'platform-upstream-review-20261027/current-writer-recovery-20261027'
SOURCE = Path(__file__).with_name('qualify-ruckusdb.py')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
NODE = r'''
import json,sys,types,hashlib,traceback
r=json.load(sys.stdin);q=types.ModuleType('reviewed_sql');exec(compile(r['source'],'<reviewed-sql>','exec'),q.__dict__)
key=bytes.fromhex(r.pop('key'));out={'status':'started','clusterChanged':False,'locksAcquired':False,'rawDetailsSuppressed':True}
try:
 datasets=[]
 for ns,claimName,volumeName in [('ruckus','ruckus-db-upstream-20261026','pvc-3d587252-21b5-4982-b70a-4cfee6ae49bd'),('ingenium','ingenium-state','pvc-1005b62c-b731-4c76-a68c-f635ef74c378')]:
  claim=q.get('pvc',claimName,ns);pv=q.get('pv',claim['spec']['volumeName'],None);v=q.get('volumes.longhorn.io',volumeName,'longhorn-system')
  assert claim['status']['phase']=='Bound'and claim['spec']['volumeName']==volumeName and pv['spec']['claimRef']['uid']==claim['metadata']['uid']and pv['spec']['csi']['volumeHandle']==volumeName
  assert v['spec']['encrypted']and v['spec']['numberOfReplicas']==2 and v['status']['state']=='attached'and v['status']['robustness']=='healthy'
  engines=[e for e in q.get('engines.longhorn.io',ns='longhorn-system')['items']if e['spec']['volumeName']==volumeName]
  assert len(engines)==1 and list(engines[0]['status']['replicaModeMap'].values()).count('RW')==2 and len(engines[0]['status']['replicaModeMap'])==2
  datasets.append({'namespace':ns,'claim':claimName,'claimUID':claim['metadata']['uid'],'pvUID':pv['metadata']['uid'],'volume':volumeName,'volumeUID':v['metadata']['uid'],'bytes':int(v['spec']['size']),'actualSizeBytes':int(v['status'].get('actualSize',0)),'node':v['spec']['nodeID'],'twoActualRWReplicas':True,'engineUID':engines[0]['metadata']['uid']})
 d=q.get('deployment','ruckus-db');assert d['metadata']['uid']==q.IDS['deployment']and d['spec']['replicas']==d['status']['availableReplicas']==1
 assert d['spec']['template']['spec']['containers'][0]['envFrom']==[{'secretRef':{'name':'ruckus-db-runtime'}}]
 image=d['spec']['template']['spec']['containers'][0]['image'];assert image=='docker.io/library/mysql:8.4@sha256:76f0358884cb92d9a086d24e5671c38048d3fef40f2588703d73eb55392d6b69'
 pods=[p for p in q.get('pods')['items']if p['metadata'].get('labels',{}).get('app')=='ruckus-db'and not p['metadata'].get('deletionTimestamp')and p['status'].get('phase')=='Running'];assert len(pods)==1
 p=pods[0];values,secret=q.native(key);sql=q.SQL('ruckus',p['metadata']['name'],'ruckus-db',values,q.get('service','ruckus-db')['spec']['clusterIP'])
 assert sql.query('SELECT VERSION()').decode().strip()=='8.4.13'
 grants=sql.query('SHOW GRANTS FOR CURRENT_USER()').decode();can_lock=any(('ALL PRIVILEGES ON *.*'in g or 'RELOAD'in g or 'FLUSH_TABLES'in g)for g in grants.splitlines())
 out.update(status='readonly_current_writer_preconditions_collected',datasets=datasets,ruckus={'deploymentUID':d['metadata']['uid'],'podUID':p['metadata']['uid'],'podName':p['metadata']['name'],'image':image,'imageID':p['status']['containerStatuses'][0]['imageID'],'nativeSecret':secret,'authenticated':True,'globalReadLockCapabilityAdvertised':can_lock,'grantsHMAC':q.mac(key,'backup-capability-grants',grants.encode()),'noLockAttempted':True})
except Exception as e:out.update(status='failed_preserve_all',errorType=type(e).__name__,sourceLines=[f.lineno for f in traceback.extract_tb(e.__traceback__)if f.filename in['<string>','<reviewed-sql>']])
print(json.dumps(out))
'''


def main():
    assert os.geteuid() == 1000 and F.is_mount() and not R.exists()
    os.umask(0o077)
    R.mkdir(mode=0o700)
    source = SOURCE.read_text()
    with (R / 'ownership.json').open('x') as out:
        json.dump({'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(F),
            'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b',
            'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'reviewedSQLSourceSHA256': hashlib.sha256(source.encode()).hexdigest(),
            'generatedPaths': [str(R / 'ownership.json'), str(R / 'preconditions.json')],
            'peakMetadataBytes': 1024**2, 'endCondition': 'read-only recovery method selection; retain only exact identity/capability metadata',
            'protected': 'all current writers, native credentials, jobs, original PVC/data, backups and other projects',
            'regeneration': 'same maintained metadata observer and original reviewed SQL source'}, out, indent=2)
    key = (F / 'acceptance-ruckus-20261025/hmac-key.hex').read_text().strip()
    try:
        body = json.dumps({'key': key, 'source': source}).encode()
        p = subprocess.run(SSH + [shlex.join(['python3', '-B', '-c', NODE])], input=body,
                           capture_output=True, timeout=180)
        assert p.returncode == 0 and len(p.stdout) < 1024**2
        result = json.loads(p.stdout)
        result['observedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (R / 'preconditions.json').open('x') as out:
            json.dump(result, out, indent=2)
        print(json.dumps(result))
        assert result['status'] == 'readonly_current_writer_preconditions_collected'
    finally:
        key, body = None, None


if __name__ == '__main__':
    main()
