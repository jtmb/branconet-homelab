#!/usr/bin/env python3
"""Observe the exact Ruckus upstream rollout with native auth and original rows."""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import os
import re
import shlex
import subprocess

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
O = F / 'upstream-ruckusdb-20261026'
S = F / 'control-source/upstream-ruckusdb-20261026'

NODE = r'''
import json,sys,types,copy,hashlib,collections,datetime,traceback,resource,signal,re
resource.setrlimit(resource.RLIMIT_CORE,(0,0));signal.alarm(300);r=json.load(sys.stdin);key=bytes.fromhex(r['key']);q=types.ModuleType('reviewed_sql');exec(compile(r['sqlSource'],'<reviewed-sql>','exec'),q.__dict__);exec(r['snapshotSource']);out={'passed':False,'phase':r['phase']}
def ready(x):return any(c['type']=='Ready'and c['status']=='True'for c in x.get('status',{}).get('conditions',[]))
def fence():
 identity={'workloads':{},'claims':{},'services':{},'secrets':{}};writers={}
 for name,duid,huid in [('ruckus-db',q.IDS['deployment'],q.IDS['release']),('ruckus-bot',q.IDS['bot'],q.IDS['bot_release'])]:
  d=q.get('deployment',name);h=q.get('helmrelease',name,'flux-system');assert d['metadata']['uid']==duid and h['metadata']['uid']==huid and ready(h)
  wanted=0 if r['phase']=='native-baseline'else(1 if name=='ruckus-db'else r['botReplicas']);assert d['spec']['replicas']==h['spec']['values']['replicaCount']==wanted
  assert d['status'].get('observedGeneration')==d['metadata']['generation']and all(d['status'].get(k,0)==wanted for k in['replicas','readyReplicas','availableReplicas','updatedReplicas'])
  spec=copy.deepcopy(d['spec']);spec['replicas']=0;spec['template']['metadata'].get('annotations',{}).pop('maintenance.branconet.lan/restart-proof',None);hs=copy.deepcopy(h['spec']);hs['values']['replicaCount']=0
  if name=='ruckus-db':
   cs=spec['template']['spec']['containers'];assert len(cs)==1;main=cs[0];assert main['envFrom']==[{'secretRef':{'name':'ruckus-db-runtime'}}]
   assert main['image']==(r['oldImage']if r['phase']=='native-baseline'else r['newImage']);main['image']='<reviewed-upstream-image>'
   if r['phase']!='native-baseline':
    assert main['args']==r['productionArgs'];main.pop('args');assert main['volumeMounts'][0]['subPath']=='data-0/security-data-20261025/data-0';main['volumeMounts'][0]['subPath']='security-data-20261025/data-0';assert spec['template']['spec']['volumes'][0]['persistentVolumeClaim']=={'claimName':'ruckus-db-upstream-20261026'};spec['template']['spec']['volumes'][0]['persistentVolumeClaim']['claimName']='ruckus-db-data-0'
   else:assert not main.get('args')and spec['template']['spec']['volumes'][0]['persistentVolumeClaim']=={'claimName':'ruckus-db-data-0'}
  identity['workloads'][name]={'uid':duid,'releaseUID':huid,'deploymentSpec':q.mac(key,'deployment-spec',spec),'releaseSpec':q.mac(key,'release-spec',hs)}
  pods=[p for p in q.get('pods')['items']if p['metadata'].get('labels',{}).get('app')==name and not p['metadata'].get('deletionTimestamp')];assert len(pods)==wanted
  if wanted:
   p=pods[0];statuses=p['status']['containerStatuses'];assert p['status']['phase']=='Running'and all(c['ready']for c in statuses);writers[name]={'podName':p['metadata']['name'],'podUID':p['metadata']['uid'],'imageIDs':[c['imageID']for c in statuses],'restarts':[c['restartCount']for c in statuses]}
   if name=='ruckus-db':assert statuses[0]['imageID'].rsplit('@',1)[-1]in[r['newImage'].rsplit('@',1)[-1],r['amd64']]
 for name,uid in [('ruckus-db-data-0',q.IDS['pvc']),('ruckus-db-upstream-20261026',r['destinationUID'])]:
  c=q.get('pvc',name);pv=q.get('pv',c['spec']['volumeName'],None);assert c['metadata']['uid']==uid and c['status']['phase']=='Bound'and pv['spec']['claimRef']['uid']==uid and pv['spec']['csi']['driver']=='driver.longhorn.io';identity['claims'][name]={'uid':uid,'pvUID':pv['metadata']['uid'],'claimSpec':q.mac(key,'pvc-spec',c['spec']),'pvSpec':q.mac(key,'pv-spec',pv['spec'])}
 for name in ['ruckus-db','ruckus-db-published','ruckus-bot','ruckus-bot-published']:
  s=q.get('service',name);identity['services'][name]={'uid':s['metadata']['uid'],'spec':q.mac(key,'service-spec',s['spec'])}
 for name,uid in r['secretUIDs'].items():
  s=q.get('secret',name);assert s['metadata']['uid']==uid;identity['secrets'][name]={'uid':uid,'data':q.mac(key,'secret-data',{k:s.get(k)for k in['type','data','immutable']})}
 if r['phase']!='native-baseline':
  source=q.get('gitrepository','branconet-charts','flux-system');assert source['status']['artifact']['revision']=='validated@sha1:'+r['revision']
  assert all(q.get('helmrelease',n,'flux-system')['status']['lastAttemptedRevision'].endswith('+'+r['revision'][:12])for n in['ruckus-db','ruckus-bot'])
 return identity,writers
try:
 before,writers=fence();result={'identity':before,'writers':writers}
 if r['phase']!='native-baseline':
  assert before==r['nativeBaseline']['identity'];values,secret=q.native(key);sql=q.SQL('ruckus',writers['ruckus-db']['podName'],'ruckus-db',values,q.get('service','ruckus-db')['spec']['clusterIP']);current=snapshot(sql,key);baseline=r['dataBaseline']['snapshot'];assert current['version']=='8.4.13'and current['serverUUID']==baseline['serverUUID'];assert set(current['schemas'])==set(baseline['schemas']);added=0
  for schema,original in baseline['schemas'].items():
   now=current['schemas'][schema];assert now['ddl']==original['ddl']and now['objects']==original['objects']and set(now['tables'])==set(original['tables'])
   for table,old in original['tables'].items():
    new=now['tables'][table];assert {k:v for k,v in new.items()if k not in['rows','data','rowHMACs']}=={k:v for k,v in old.items()if k not in['rows','data','rowHMACs']}
    assert collections.Counter(new.get('rowHMACs',[]))>=collections.Counter(old.get('rowHMACs',[]));assert len(old.get('rowHMACs',[]))==old.get('rows',0);added+=new.get('rows',0)-old.get('rows',0)
    if r['botReplicas']==0:assert new==old
  expected=dict(r['liveSettings']);expected['sql_mode']=','.join(v for v in expected['sql_mode'].split(',')if v!='NO_AUTO_CREATE_USER');assert current['settings']==expected
  if r['phase']=='restart':assert writers['ruckus-db']['podUID']!=r['previous']['writers']['ruckus-db']['podUID']
  assert sql.query('SELECT 1').strip()==b'1';result.update(snapshot=current,nativeAuthentication=True,nativeSecret=secret,allOriginalRowsPreserved=True,additionalRows=added)
 after,writers2=fence();assert(before,writers)==(after,writers2);out.update(result,passed=True,UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),personalLoginClaimed=False,fullGoalComplete=False)
except Exception as e:out.update(passed=False,errorType=type(e).__name__,sourceLines=[f.lineno for f in traceback.extract_tb(e.__traceback__)if f.filename in['<string>','<reviewed-sql>']],rawDetailsSuppressed=True)
print(json.dumps(out))
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=['native-baseline', 'after', 'after-bot', 'restart'])
    p.add_argument('--receipt', type=Path, required=True)
    p.add_argument('--revision')
    p.add_argument('--previous', type=Path)
    a = p.parse_args()
    assert F.is_mount() and os.getuid() == 1000 and a.receipt.parent == O and not a.receipt.exists()
    os.umask(0o077)
    spec = importlib.util.spec_from_file_location('fresh_snapshot', S / 'upgrade-ruckus-upstream-destination-r3.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    source = m.snapshot_source()
    source = source[:source.index(" for table in ['user','db'")] + "\n result['settings']={name:sql.query('SELECT @@'+name).decode().strip()for name in ['sql_mode','character_set_server','collation_server','lower_case_table_names','innodb_page_size','innodb_file_per_table','log_bin','gtid_mode','event_scheduler']}\n result['serverUUID']=q.mac(key,'server-uuid',sql.query('SELECT @@server_uuid'))\n return result\n"
    ast.parse(source)
    claim = json.loads((O / 'reconciled-0b5f6506e40b08955fdb3984650effc056e9d246.json').read_text())['destinationClaimUID']
    secrets = {x['name']: x['uid'] for x in json.loads((O / 'prerequisites.json').read_text())['nativeSecretMetadata']}
    settings = json.loads((O / 'final-live-server-settings.json').read_text())['settings']
    modes = ','.join(v for v in settings['sql_mode'].split(',') if v != 'NO_AUTO_CREATE_USER')
    args = ['--mysql-native-password=ON', '--character-set-server=latin1', '--collation-server=latin1_swedish_ci',
            '--lower-case-table-names=0', '--innodb-file-per-table=ON', '--skip-log-bin', '--gtid-mode=OFF',
            '--sql-mode=' + modes, '--event-scheduler=OFF']
    request = {'phase': a.phase, 'key': m.key(), 'sqlSource': m.SQL_SOURCE.read_text(), 'snapshotSource': source,
               'destinationUID': claim, 'secretUIDs': secrets, 'oldImage': m.trial.OLD, 'newImage': m.trial.NEW,
               'amd64': 'sha256:2068651a18ac6048578647ea57b940ca2daed3f504ebe7fba6a93beeb39aaa1f',
               'liveSettings': settings, 'productionArgs': args, 'botReplicas': int(a.phase in ['after-bot', 'restart'])}
    if a.phase != 'native-baseline':
        assert a.revision and re.fullmatch('[a-f0-9]{40}', a.revision)
        request.update(revision=a.revision, nativeBaseline=json.loads((O / 'final-native-baseline.json').read_text()),
                       dataBaseline=json.loads((O / 'final-old-admin-baseline-01.json').read_text()))
        assert json.loads((O / 'final-copy-acceptance.json').read_text())['passed']
    if a.phase == 'restart':
        assert a.previous and a.previous.parent == O
        request['previous'] = json.loads(a.previous.read_text())
        assert request['previous']['passed']
    proc = subprocess.run(m.trial.SSH + [shlex.join(['python3', '-B', '-c', NODE])],
                          input=json.dumps(request).encode(), capture_output=True, timeout=360)
    try:
        result = json.loads(proc.stdout)
    except Exception:
        result = {'passed': False, 'exitCode': proc.returncode, 'rawDetailsSuppressed': True}
    result['controllerSHA256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result.get(k) for k in ['passed', 'phase', 'errorType', 'sourceLines', 'allOriginalRowsPreserved', 'additionalRows']}))
    return int(proc.returncode != 0 or not result['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
