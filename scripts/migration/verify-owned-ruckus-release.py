#!/usr/bin/env python3
"""Read-only exact-image, original-row and native-configuration rollout witness.

Uses the already reviewed SQL snapshot implementation, sending credentials and
the existing keyed comparison material only through SSH stdin and process memory.
No accounts, passwords, Discord messages or database rows are created by this tool.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import subprocess

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
O = F / 'owned-ruckus-release-20261027'
S = F / 'control-source/upstream-ruckusdb-20261026'
OLD = 'docker.io/library/ruckus-bot-security-20261023@sha256:5da497fc6680b06cc26f7ee94aa2d46cccfdddfbfe26ce71676be518a182262a'
DB = 'docker.io/library/mysql:8.4@sha256:76f0358884cb92d9a086d24e5671c38048d3fef40f2588703d73eb55392d6b69'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
NODE = r'''
import json,sys,types,copy,hashlib,collections,datetime,traceback,resource,signal,re,urllib.request,urllib.error
resource.setrlimit(resource.RLIMIT_CORE,(0,0));signal.alarm(300)
r=json.load(sys.stdin);key=bytes.fromhex(r['key']);q=types.ModuleType('reviewed_sql');exec(compile(r['sqlSource'],'<reviewed-sql>','exec'),q.__dict__);exec(r['snapshotSource']);out={'passed':False,'phase':r['phase']}
def ready(x):return any(c['type']=='Ready'and c['status']=='True'for c in x.get('status',{}).get('conditions',[]))
def fence():
 result={'workloads':{},'claims':{},'services':{},'ingresses':{},'secrets':{}};writers={}
 for name,duid,huid,image in [('ruckus-db',q.IDS['deployment'],q.IDS['release'],r['dbImage']),('ruckus-bot',q.IDS['bot'],q.IDS['bot_release'],r['image'])]:
  d=q.get('deployment',name);h=q.get('helmrelease',name,'flux-system');assert d['metadata']['uid']==duid and h['metadata']['uid']==huid and ready(h) and not h['spec'].get('suspend')
  assert d['spec']['replicas']==h['spec']['values']['replicaCount']==1
  assert d['status'].get('observedGeneration')==d['metadata']['generation']and all(d['status'].get(k,0)==1 for k in ['replicas','readyReplicas','availableReplicas','updatedReplicas'])
  spec=copy.deepcopy(d['spec']);hs=copy.deepcopy(h['spec']);cs=spec['template']['spec']['containers'];assert len(cs)==1 and cs[0]['image']==image
  if name=='ruckus-bot':
   cs[0]['image']='<accepted-image>'
   spec['template']['metadata'].get('annotations',{}).pop('maintenance.branconet.lan/restart-proof',None)
   if 'image'in hs.get('values',{}):assert hs['values'].pop('image')==image
   hs.get('values',{}).get('podAnnotations',{}).pop('maintenance.branconet.lan/restart-proof',None)
  result['workloads'][name]={'uid':duid,'releaseUID':huid,'deploymentSpec':q.mac(key,'deployment-spec',spec),'releaseSpec':q.mac(key,'release-spec',hs)}
  pods=[p for p in q.get('pods')['items']if p['metadata'].get('labels',{}).get('app')==name and not p['metadata'].get('deletionTimestamp')];assert len(pods)==1
  p=pods[0];ss=p['status']['containerStatuses'];assert p['status']['phase']=='Running'and all(c['ready']for c in ss)
  assert all(c['imageID'].rsplit('@',1)[-1]in r['acceptedImageIDs'][name]for c in ss)
  writers[name]={'podName':p['metadata']['name'],'podUID':p['metadata']['uid'],'imageIDs':[c['imageID']for c in ss],'restarts':[c['restartCount']for c in ss]}
 for c in q.get('pvc')['items']:
  assert c['status']['phase']=='Bound';pv=q.get('pv',c['spec']['volumeName'],None);assert pv['spec']['claimRef']['uid']==c['metadata']['uid']
  result['claims'][c['metadata']['name']]={'uid':c['metadata']['uid'],'pvUID':pv['metadata']['uid'],'spec':q.mac(key,'claim',{'claim':c['spec'],'pv':pv['spec']})}
 for kind,keyname in [('service','services'),('ingress','ingresses')]:
  for x in q.get(kind)['items']:result[keyname][x['metadata']['name']]={'uid':x['metadata']['uid'],'spec':q.mac(key,kind,x['spec'])}
 for name in ['ruckus-db-runtime','ruckus-bot-runtime']:
  x=q.get('secret',name);result['secrets'][name]={'uid':x['metadata']['uid'],'content':q.mac(key,'native-secret',{k:x.get(k)for k in ['type','data','immutable']})}
 source=q.get('gitrepository','branconet-charts','flux-system');assert source['status']['artifact']['revision']=='validated@sha1:'+r['revision']
 assert all(q.get('helmrelease',n,'flux-system')['status']['lastAttemptedRevision'].endswith('+'+r['revision'][:12])for n in ['ruckus-db','ruckus-bot'])
 return result,writers
try:
 identity,writers=fence();values,secret=q.native(key);sql=q.SQL('ruckus',writers['ruckus-db']['podName'],'ruckus-db',values,q.get('service','ruckus-db')['spec']['clusterIP']);current=snapshot(sql,key);assert current['version']=='8.4.13'
 added=0
 if r.get('baseline'):
  base=r['baseline'];assert identity==base['identity'];original=base['snapshot'];assert current['serverUUID']==original['serverUUID']and current['settings']==original['settings']and set(current['schemas'])==set(original['schemas'])
  for schema,old in original['schemas'].items():
   now=current['schemas'][schema];assert now['ddl']==old['ddl']and now['objects']==old['objects']and set(now['tables'])==set(old['tables'])
   for table,previous in old['tables'].items():
    new=now['tables'][table];assert {k:v for k,v in new.items()if k not in ['rows','data','rowHMACs']}=={k:v for k,v in previous.items()if k not in ['rows','data','rowHMACs']}
    assert len(previous.get('rowHMACs',[]))==previous['rows']and collections.Counter(new.get('rowHMACs',[]))>=collections.Counter(previous['rowHMACs']);added+=new['rows']-previous['rows']
  assert writers['ruckus-db']==base['writers']['ruckus-db']
  assert writers['ruckus-bot']['podUID']!=base['writers']['ruckus-bot']['podUID']
 if r.get('previous'):assert writers['ruckus-bot']['podUID']!=r['previous']['writers']['ruckus-bot']['podUID']
 client=urllib.request.build_opener(urllib.request.ProxyHandler({}));routes=[]
 for host,apiport,uiport in [(q.get('service','ruckus-bot')['spec']['clusterIP'],3003,8080),('192.168.0.4',3003,8088),('192.168.0.5',3003,8088),('192.168.0.6',3003,8088)]:
  for port,path in [(apiport,'/users'),(apiport,'/bot/logs'),(apiport,'/bot/logins'),(apiport,'/bot/interactions'),(apiport,'/bot/count'),(apiport,'/bot/login_count'),(uiport,'/')]:
   try:response=client.open('http://'+host+':'+str(port)+path,timeout=15)
   except urllib.error.HTTPError as e:response=e
   with response:body=response.read(2*1024**2+1);status=response.code
   assert len(body)<=2*1024**2 and status==200
   routes.append({'host':host,'port':port,'path':path,'status':status,'bytes':len(body),'bodyHMAC':q.mac(key,'route-body',body)})
 runtime=None
 if r.get('runtimeSource'):
  runtime=json.loads(q.call(['-n','ruckus','exec','-i',writers['ruckus-bot']['podName'],'--','/usr/local/bin/node','-e',r['runtimeSource']],json.dumps({'files':r['sourceFiles']}).encode()))
  assert runtime['passed']
  state=q.call(['-n','ruckus','exec',writers['ruckus-bot']['podName'],'--','supervisorctl','status']).decode().splitlines()
  assert len(state)==3 and {x.split()[0]for x in state}=={'api','dashboard','bot_run'}and all(x.split()[1]=='RUNNING'for x in state)
  logs=q.call(['-n','ruckus','logs',writers['ruckus-bot']['podName'],'--tail=5000','--limit-bytes=2000000']).decode(errors='replace')
  assert 'Bot is Online'in logs and 'Log inserted successfully'in logs
  runtime.update(supervisorPrograms=['api','dashboard','bot_run'],allSupervisorProgramsRunning=True,realGatewayReadyObserved=True,normalBotLoginSQLObserved=True,rawLogsSaved=False)
 after,writers2=fence();assert(identity,writers)==(after,writers2)
 out.update(passed=True,UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),identity=identity,writers=writers,snapshot=current,nativeAuthentication=True,nativeSecret=secret,allOriginalRowsPreserved=bool(r.get('baseline')),additionalRows=added,routes=routes,routeCount=len(routes),runtime=runtime,dataChangingSQLExecuted=False,DiscordTestMessageSent=False,personalLoginClaimed=False)
except Exception as e:out.update(errorType=type(e).__name__,sourceLines=[f.lineno for f in traceback.extract_tb(e.__traceback__)if f.filename in ['<string>','<reviewed-sql>']],rawDetailsSuppressed=True)
print(json.dumps(out))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=['baseline','production','restart'])
    p.add_argument('--revision',required=True)
    p.add_argument('--image',default=OLD)
    p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--previous',type=Path)
    a=p.parse_args()
    assert re.fullmatch('[a-f0-9]{40}',a.revision) and a.receipt.parent==O and not a.receipt.exists()
    assert a.image.startswith(('docker.io/library/ruckus-bot-security-20261023@sha256:','docker.io/jtmb92/ruckus-bot:git-')) and re.fullmatch('[a-f0-9]{64}',a.image.rsplit('sha256:',1)[-1])
    spec=importlib.util.spec_from_file_location('snapshot_source',S/'upgrade-ruckus-upstream-destination-r3.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    source=m.snapshot_source();source=source[:source.index(" for table in ['user','db'")]+"\n result['settings']={name:sql.query('SELECT @@'+name).decode().strip()for name in ['sql_mode','character_set_server','collation_server','lower_case_table_names','innodb_page_size','innodb_file_per_table','log_bin','gtid_mode','event_scheduler']}\n result['serverUUID']=q.mac(key,'server-uuid',sql.query('SELECT @@server_uuid'))\n return result\n"
    ast.parse(source);ast.parse(NODE)
    r={'phase':a.phase,'key':m.key(),'sqlSource':m.SQL_SOURCE.read_text(),'snapshotSource':source,'image':a.image,'dbImage':DB,'revision':a.revision,'acceptedImageIDs':{'ruckus-db':[DB.rsplit('@',1)[-1],'sha256:2068651a18ac6048578647ea57b940ca2daed3f504ebe7fba6a93beeb39aaa1f'],'ruckus-bot':[a.image.rsplit('@',1)[-1]]}}
    if a.phase!='baseline':
        r['baseline']=json.loads((O/'baseline.json').read_text());assert r['baseline']['passed']
        release=json.loads((O/'qualified-publication.json').read_text())
        assert release['published_reference']==a.image
        exported=release['source']['files']
        r['sourceFiles']={('/app/'+x['path']):x['sha256']for x in exported if x['path'].startswith(('api/','bot/','dashboard/'))}
        config=next(x['sha256']for x in exported if x['path']=='config/supervisord.conf')
        r['sourceFiles'].update({'/etc/supervisor/supervisord.conf':config,'/etc/supervisor/conf.d/supervisord.conf':config})
        r['runtimeSource']=r'''const fs=require('fs'),crypto=require('crypto');const r=JSON.parse(fs.readFileSync(0,'utf8'));const need=(v)=>{if(!v)throw new Error('runtime_contract');};need(process.version==='v22.23.4');for(const [name,version]of Object.entries({'/app/api/node_modules/bcrypt/package.json':'6.0.0','/app/api/node_modules/mysql2/package.json':'3.24.6','/app/api/node_modules/proxy-addr/package.json':'2.0.8','/app/bot/node_modules/mysql2/package.json':'3.24.6','/app/bot/node_modules/discord.js/package.json':'14.27.0','/app/dashboard/node_modules/next/package.json':'16.4.3'}))need(require(name).version===version);for(const name of ['/usr/local/bin/npm','/usr/local/bin/npx','/usr/local/lib/node_modules/npm','/usr/local/bin/nodemon'])need(!fs.existsSync(name));for(const [name,hash]of Object.entries(r.files))need(crypto.createHash('sha256').update(fs.readFileSync(name)).digest('hex')===hash);const b=require('/app/api/node_modules/bcrypt'),h=b.hashSync('isolated-runtime-compatibility',10);need(b.compareSync('isolated-runtime-compatibility',h)&&!b.compareSync('different',h));console.log(JSON.stringify({passed:true,Node:process.version,sourceFilesChecked:Object.keys(r.files).length,bcryptNativeCompatibility:true,unusedDevelopmentLaunchersAbsent:true}));'''
    if a.previous:
        assert a.previous.parent==O;r['previous']=json.loads(a.previous.read_text());assert r['previous']['passed']
    proc=subprocess.run(SSH+[shlex.join(['python3','-B','-c',NODE])],input=json.dumps(r).encode(),capture_output=True,timeout=330)
    try:result=json.loads(proc.stdout)
    except Exception:result={'passed':False,'exitCode':proc.returncode,'rawDetailsSuppressed':True}
    result['controllerSHA256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result.get(k)for k in ['passed','phase','UTC','errorType','sourceLines','routeCount','allOriginalRowsPreserved','additionalRows']}))
    return int(proc.returncode!=0 or not result['passed'])


if __name__=='__main__':raise SystemExit(main())
