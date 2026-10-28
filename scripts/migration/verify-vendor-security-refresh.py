#!/usr/bin/env python3
"""Read-only before/after checks for the two exact official security refreshes."""
import argparse
import collections
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H = F / 'platform-upstream-review-20261027/upstream-security-refresh-20261028'
MYSQL = ['docker.io/library/mysql:8.4@sha256:76f0358884cb92d9a086d24e5671c38048d3fef40f2588703d73eb55392d6b69',
         'docker.io/library/mysql:8.4@sha256:a0225d1ea6631c8bc2385dc4c2faba17bbf1834ecf369e1659a9a382bd8d5dd7']
YTP = ['ghcr.io/arabcoders/ytptube:v2.7.5@sha256:3ba09ac58f0b541aa7182feb9198b44d3c62158a7749ec00d26de1abad7ca8d7',
       'ghcr.io/arabcoders/ytptube:v2.7.6@sha256:a5b648c6c20d877cf90715415b1b31565dda9399020d80f186000fdd76474f86']
REMOTE = r'''
import json,sys,types,copy,re,hashlib,collections,traceback
r=json.load(sys.stdin);q=types.ModuleType('reviewed_sql');exec(compile(r['sqlSource'],'<reviewed-sql>','exec'),q.__dict__);exec(r['snapshotSource']);key=bytes.fromhex(r['key'])
def fence():
 d=q.get('deployment','ruckus-db');h=q.get('helmrelease','ruckus-db','flux-system')
 assert d['metadata']['uid']==q.IDS['deployment'] and h['metadata']['uid']==q.IDS['release'] and not h['spec'].get('suspend')
 assert any(c['type']=='Ready'and c['status']=='True'for c in h['status']['conditions'])
 assert d['spec']['replicas']==1 and d['status']['readyReplicas']==d['status']['updatedReplicas']==d['status']['availableReplicas']==1
 pods=[p for p in q.get('pods')['items'] if all(p['metadata'].get('labels',{}).get(k)==v for k,v in d['spec']['selector']['matchLabels'].items()) and not p['metadata'].get('deletionTimestamp')]
 assert len(pods)==1;p=pods[0];c=p['status']['containerStatuses'][0];assert c['ready'] and p['spec']['containers'][0]['image']==r['image'] and c['imageID'].split('@')[-1] in r['imageDigests']
 spec=copy.deepcopy(d['spec']);assert spec['template']['spec']['containers'][0]['image']==r['image'];spec['template']['spec']['containers'][0]['image']='<approved-image>'
 claims={}
 for v in d['spec']['template']['spec']['volumes']:
  if 'persistentVolumeClaim' not in v:continue
  name=v['persistentVolumeClaim']['claimName'];cl=q.get('pvc',name);pv=q.get('pv',cl['spec']['volumeName'],None)
  assert cl['status']['phase']=='Bound'and pv['spec']['claimRef']['uid']==cl['metadata']['uid'];claims[name]={'uid':cl['metadata']['uid'],'pvUID':pv['metadata']['uid'],'spec':q.mac(key,'claim',cl['spec']),'pvSpec':q.mac(key,'pv',pv['spec'])}
 values,secret=q.native(key)
 return {'deploymentUID':d['metadata']['uid'],'template':q.mac(key,'deployment',spec),'claims':claims,'nativeSecret':{'uid':secret['uid'],'dataHMAC':secret['data_hmac']}},{'name':p['metadata']['name'],'uid':p['metadata']['uid'],'imageID':c['imageID'],'restartCount':c['restartCount']},values
try:
 identity,pod,values=fence();sql=q.SQL('ruckus',pod['name'],'ruckus-db',values,q.get('service','ruckus-db')['spec']['clusterIP']);state=snapshot(sql,key)
 assert state['version']=='8.4.13' and sql.query('SELECT 1').strip()==b'1'
 identity2,pod2,_=fence();assert(identity,pod)==(identity2,pod2)
 print(json.dumps({'passed':True,'identity':identity,'pod':pod,'state':state,'nativeAuthentication':True}))
except Exception as e:
 print(json.dumps({'passed':False,'errorType':type(e).__name__,'sourceLines':[x.lineno for x in traceback.extract_tb(e.__traceback__)if x.filename in ['<string>','<reviewed-sql>']]}))
'''

def mysql(phase):
    spec = importlib.util.spec_from_file_location('reviewed_snapshot', F / 'control-source/upstream-ruckusdb-20261026/upgrade-ruckus-upstream-destination-r3.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    source = m.snapshot_source()
    source = source[:source.index(" for table in ['user','db'")] + "\n result['settings']={name:sql.query('SELECT @@'+name).decode().strip()for name in ['sql_mode','character_set_server','collation_server','lower_case_table_names','innodb_page_size','innodb_file_per_table','log_bin','gtid_mode','event_scheduler']}\n result['serverUUID']=q.mac(key,'server-uuid',sql.query('SELECT @@server_uuid'))\n return result\n"
    index = int(phase == 'after')
    digests = [MYSQL[index].split('@')[-1], ['sha256:2068651a18ac6048578647ea57b940ca2daed3f504ebe7fba6a93beeb39aaa1f','sha256:5cf1e1293ea42e077e6a22114e6773b9aae3bb8f9933a2acd5a9721518ff8f5b'][index]]
    request = {'key':m.key(),'sqlSource':m.SQL_SOURCE.read_text(),'snapshotSource':source,'image':MYSQL[index],'imageDigests':digests}
    proc = subprocess.run(m.trial.SSH + [shlex.join(['python3','-B','-c',REMOTE])], input=json.dumps(request).encode(),capture_output=True,timeout=360)
    assert proc.returncode == 0 and len(proc.stdout) < 8*1024**2
    data = json.loads(proc.stdout); assert data['passed'], data
    if phase == 'after':
        old = json.loads((H/'mysql-before.json').read_bytes())
        assert data['identity'] == old['identity'] and data['pod']['uid'] != old['pod']['uid']
        a,b=old['state'],data['state'];assert a['version']==b['version'] and a['settings']==b['settings'] and a['serverUUID']==b['serverUUID'] and set(a['schemas'])==set(b['schemas'])
        for name, schema in a['schemas'].items():
            now=b['schemas'][name];assert schema['ddl']==now['ddl'] and schema['objects']==now['objects'] and set(schema['tables'])==set(now['tables'])
            for t,prior in schema['tables'].items():
                current=now['tables'][t]
                assert {k:v for k,v in prior.items() if k not in ['rows','data','rowHMACs']}=={k:v for k,v in current.items() if k not in ['rows','data','rowHMACs']}
                assert collections.Counter(current['rowHMACs'])>=collections.Counter(prior['rowHMACs'])
        data['allBeforeRowsPreserved']=True
    data['sourceSHA256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (H/('mysql-'+phase+'.json')).open('x') as out:json.dump(data,out,indent=2)
    print(json.dumps({'passed':True,'service':'mysql','phase':phase,'podUID':data['pod']['uid']}))

def ytptube(phase):
    spec=importlib.util.spec_from_file_location('stored_state',REPO/'scripts/migration/qualify-ytptube-state.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    remote=runpy.run_path(str(REPO/'scripts/migration/verify-final-media-history.py'))['remote']
    m.operator.kubectl=lambda *args,body=None,timeout=30:remote(['kubectl','-n','plex',*args],body)
    m.operator.UPSTREAM_IMAGE=YTP[int(phase=='after')]
    name='ytptube-'+phase+'.json'
    # The unchanged after comparison is used for BOTH observations against the
    # original migration baseline. No account/history/table exclusion is added.
    baseline=F/'upstream-ytptube-20261025/state-baseline-master-receipt.json'
    sys.argv=[str(Path(__file__)),'after','--receipt',str(H/name),'--baseline',str(baseline)]
    m.main()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('service',choices=['mysql','ytptube']);p.add_argument('phase',choices=['before','after']);a=p.parse_args()
    assert os.getuid()==1000 and F.is_mount();os.umask(0o077)
    assert all(os.statvfs(x).f_bavail*os.statvfs(x).f_frsize>=15*1024**3+8*1024**2 for x in [F,Path('/mnt/c')])
    H.mkdir(mode=0o700,exist_ok=True)
    if not (H/'ownership.json').exists():
        with (H/'ownership.json').open('x') as f:json.dump({'owner':'01a12045-bf7e-73b3-8557-752d17c72ffd','root':str(F),'volumeUUID':'3c792469-ea0e-4a2c-98e8-1185b141607b','generated':[str(H)],'peakBytes':8*1024**2,'retention':'Minimal unique before/after hash receipts; no files, build caches, extracts or dependencies','regenerate':'Run this read-only observer against a qualified exact image; original observations remain unique'},f,indent=2)
    (mysql if a.service=='mysql' else ytptube)(a.phase)

if __name__=='__main__':main()
