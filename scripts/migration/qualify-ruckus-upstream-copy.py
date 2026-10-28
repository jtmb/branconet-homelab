#!/usr/bin/env python3
"""Qualify a cold Ruckus copy through upstream MySQL 8.0 and 8.4 in isolated RAM.

No production claim is mounted or scaled. The historical trial is never a
cutover source: a fresh quiesced backup is required for final delivery.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import tarfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = F / 'upstream-ruckusdb-20261026'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-i',
       '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
OLD = 'docker.io/library/ruckusdb-security-20261023@sha256:2f0c391e6c04501862598bbc5446165f8ebba08025168451f6f6447352316349'
MID = 'docker.io/library/mysql:8.0@sha256:7dcddc01f13bab2f15cde676d44d01f61fc9f99fe7785e86196dfc07d358ae2b'
NEW = 'docker.io/library/mysql:8.4@sha256:76f0358884cb92d9a086d24e5671c38048d3fef40f2588703d73eb55392d6b69'
READER = 'docker.io/library/python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1'
HISTORICAL = F / 'ruckus-ha-recovery-20261025/cold-455be8afe1d7491fa9d787dbd6b85efa/receipt.json'

SNAPSHOT = r'''
def snapshot(sql,key,grant_columns=None):
 version=sql.query('SELECT VERSION()').decode().strip();assert version in ['5.7.44','8.0.46','8.4.13']
 def normalized(raw):
  s=raw.decode();s=re.sub(r'\b(tinyint|smallint|mediumint|int|bigint)\(\d+\)',r'\1',s,flags=re.I)
  s=re.sub(r'\butf8(_[a-z0-9_]+)?\b',lambda m:'utf8mb3'+(m.group(1)or''),s)
  s=re.sub(r' /\*!80016 DEFAULT ENCRYPTION=\x27N\x27 \*/','',s)
  return s.encode()
 result={'version':version,'schemas':{},'grantColumns':{},'grants':{},'accounts':{},'accountFields':{},'vendorAccounts':{},'timeZones':{}}
 schemas=[bytes.fromhex(x.decode()).decode()for x in sql.query("SELECT HEX(SCHEMA_NAME) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME NOT IN ('mysql','sys','information_schema','performance_schema') ORDER BY SCHEMA_NAME").splitlines()]
 assert schemas and len(schemas)<=16
 def table_rows(schema,name,columns=None):
  target=q.ident(schema)+'.'+q.ident(name)
  if columns is None:columns=[bytes.fromhex(x.decode()).decode()for x in sql.query('SELECT HEX(COLUMN_NAME) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='+q.literal(schema)+' AND TABLE_NAME='+q.literal(name)+' ORDER BY ORDINAL_POSITION').splitlines()]
  count=int(sql.query('SELECT COUNT(*) FROM '+target));assert count<=200000
  expressions=["IF("+q.ident(c)+" IS NULL,'N',CONCAT('V',HEX(CAST("+q.ident(c)+' AS BINARY))))'for c in columns]
  raw=sql.query('START TRANSACTION WITH CONSISTENT SNAPSHOT; SELECT '+','.join(expressions)+' FROM '+target+'; COMMIT');rows=raw.splitlines();assert len(rows)==count==int(sql.query('SELECT COUNT(*) FROM '+target))
  return columns,rows
 for schema in schemas:
  tables={};raw=sql.query('SELECT HEX(TABLE_NAME),TABLE_TYPE FROM information_schema.TABLES WHERE TABLE_SCHEMA='+q.literal(schema)+' ORDER BY TABLE_NAME')
  for line in raw.splitlines():
   namehex,kind=line.decode().split('\t');name=bytes.fromhex(namehex).decode();target=q.ident(schema)+'.'+q.ident(name);entry={'kind':kind,'ddl':q.mac(key,'ddl',normalized(sql.query('SHOW CREATE TABLE '+target)))}
   if kind=='BASE TABLE':
    columns,rows=table_rows(schema,name);entry.update(columns=q.mac(key,'columns',columns),rows=len(rows),data=q.mac(key,'row-multiset',b''.join(sorted(bytes.fromhex(q.mac(key,'row',row))for row in rows))))
   tables[q.mac(key,'table-name',(schema+'\0'+name).encode())]=entry
  objects={}
  for category,query in {'routines':'SELECT HEX(ROUTINE_NAME),ROUTINE_TYPE,HEX(ROUTINE_DEFINITION),HEX(DEFINER),SQL_MODE,SECURITY_TYPE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=','triggers':'SELECT HEX(TRIGGER_NAME),HEX(ACTION_STATEMENT),HEX(DEFINER),ACTION_TIMING,EVENT_MANIPULATION,HEX(EVENT_OBJECT_TABLE) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=','events':'SELECT HEX(EVENT_NAME),HEX(EVENT_DEFINITION),HEX(DEFINER),EVENT_TYPE,HEX(EXECUTE_AT),HEX(INTERVAL_VALUE),INTERVAL_FIELD,STATUS,ON_COMPLETION FROM information_schema.EVENTS WHERE EVENT_SCHEMA='}.items():
   raw=sql.query(query+q.literal(schema));assert not raw,'stored_objects_require_explicit_upgrade_review';objects[category]=0
  result['schemas'][q.mac(key,'schema-name',schema.encode())]={'ddl':q.mac(key,'database-ddl',normalized(sql.query('SHOW CREATE DATABASE '+q.ident(schema)))),'tables':tables,'objects':objects}
 for table in ['user','db','tables_priv','columns_priv','procs_priv','proxies_priv']:
  columns,rows=table_rows('mysql',table,grant_columns[table]if grant_columns else None);result['grantColumns'][table]=columns
  result['grants'][table]={'rows':len(rows),'data':q.mac(key,'grant-rows',b'\n'.join(sorted(rows)))}
  if table=='user':
   for row in rows:
    cells=row.split(b'\t');identity=b'\0'.join(cells[columns.index(k)]for k in ['User','Host']);aid=q.mac(key,'account',identity);result['accounts'][aid]=q.mac(key,'account-fields',row);result['accountFields'][aid]={name:q.mac(key,'account-field-'+name,cells[i])for i,name in enumerate(columns)}
    decode=lambda name:bytes.fromhex(cells[columns.index(name)][1:].decode()).decode()
    if decode('User')in['mysql.sys','mysql.session','mysql.infoschema']and decode('Host')=='localhost':result['vendorAccounts'][aid]={'name':decode('User'),'locked':decode('account_locked')=='Y'}
 for table in ['time_zone','time_zone_name','time_zone_transition','time_zone_transition_type','time_zone_leap_second']:
  columns,rows=table_rows('mysql',table);result['timeZones'][table]={'columns':q.mac(key,'columns',columns),'rows':len(rows),'data':q.mac(key,'timezone-rows',b'\n'.join(sorted(rows)))}
 result['settings']={name:sql.query('SELECT @@'+name).decode().strip()for name in ['sql_mode','character_set_server','collation_server','lower_case_table_names','innodb_page_size','innodb_file_per_table','log_bin','gtid_mode','event_scheduler']}
 result['serverUUID']=q.mac(key,'server-uuid',sql.query('SELECT @@server_uuid'))
 return result
'''

NODE = r'''
import json,sys,subprocess,time,datetime,resource,traceback,re,types,hashlib
resource.setrlimit(resource.RLIMIT_CORE,(0,0));r=json.load(sys.stdin);state=r['state'];ns=state['namespace'];key=bytes.fromhex(r['key']);q=types.ModuleType('reviewed_original_sql');exec(compile(r['sqlSource'],'<reviewed-sql>','exec'),q.__dict__);exec(r['snapshotSource']);out={'passed':False,'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'action':r['action']}
def call(a,data=None,timeout=150):return subprocess.check_output(['kubectl','--request-timeout=30s','-n',ns,*a],input=data,stderr=subprocess.DEVNULL,timeout=timeout)
def guard():
 p=json.loads(call(['get','pod','qualifier','-o','json']));assert p['metadata']['uid']==state['podUID']and p['status']['phase']=='Running'and not p['metadata'].get('deletionTimestamp');assert not any('persistentVolumeClaim'in v or'hostPath'in v for v in p['spec']['volumes']);assert p['spec']['automountServiceAccountToken']is False;assert hashlib.sha256(json.dumps(p['spec'],sort_keys=True).encode()).hexdigest()==state['podSpecSHA256']
 policies=json.loads(call(['get','networkpolicies','-o','json']))['items'];assert len(policies)==1 and policies[0]['metadata']['uid']==state['owned'][1]['uid'];policy=policies[0]['spec'];assert {**policy,'ingress':policy.get('ingress',[]),'egress':policy.get('egress',[])}=={'podSelector':{},'policyTypes':['Ingress','Egress'],'ingress':[],'egress':[]}
 n=json.loads(call(['get','namespace',ns,'-o','json']));assert n['metadata']['uid']==state['namespaceUID'];return p
try:
 p=guard();side=r.get('side');container=side if side else None
 if r['action']=='start':
  assert side in ['old','mid','new'];datadir='/copy/'+('data-0/data-0'if side=='old'else'slow-copy/data-0/data-0');flags=['mysqld','--datadir='+datadir,'--socket=/run/qual/mysql.sock','--pid-file=/run/qual/mysqld.pid','--tmpdir=/run/qual','--log-error=/run/qual/error.log','--skip-networking','--event-scheduler=OFF','--innodb-fast-shutdown=0']
  if side!='old':
   settings=r['serverSettings'];assert settings['log_bin']=='0'and settings['gtid_mode']=='OFF'and settings['event_scheduler']=='OFF'and settings['lower_case_table_names']=='0'and settings['innodb_page_size']=='16384'and settings['innodb_file_per_table']=='1'
   assert settings['character_set_server']=='latin1'and settings['collation_server']=='latin1_swedish_ci'
   modes=settings['sql_mode'].split(',');assert 'NO_AUTO_CREATE_USER'in modes;modes.remove('NO_AUTO_CREATE_USER')
   flags+=['--character-set-server=latin1','--collation-server=latin1_swedish_ci','--lower-case-table-names=0','--innodb-file-per-table=ON','--skip-log-bin','--gtid-mode=OFF','--sql-mode='+','.join(modes)]
  if side=='new':flags+=['--mysql-native-password=ON']
  if r.get('admin',True):flags+=['--skip-grant-tables']
  # Only one server can use the candidate volume. The next stage requires an
  # observed clean shutdown, and a stopped container has no mysqld process.
  other=['old']if side=='old'else['mid','new']
  for c in other:
   raw=call(['exec','qualifier','-c',c,'--','/bin/sh','-c','test ! -e /run/qual/launch.pid']);assert raw==b''
  import shlex
  script='set -eu; test -s '+datadir+'/ibdata1; test ! -e /run/qual/launch.pid; nohup '+shlex.join(flags)+' >/run/qual/stdout.log 2>&1 </dev/null & echo $! >/run/qual/launch.pid'
  call(['exec','qualifier','-c',side,'--','/bin/sh','-c',script]);out.update(passed=True,flags=flags,startupIsNotReadiness=True)
 elif r['action']=='stop':
  script='set -eu; p=$(cat /run/qual/launch.pid); case "$p" in ""|*[!0-9]*) exit 1;; esac; test "$(basename "$(readlink /proc/$p/exe)")" = mysqld; kill -TERM "$p"; i=0; while test -e /proc/$p/exe; do i=$((i+1)); test "$i" -lt 120; sleep 1; done; test ! -e /run/qual/mysqld.pid; rm /run/qual/launch.pid'
  call(['exec','qualifier','-c',side,'--','/bin/sh','-c',script],timeout=150);out.update(passed=True,cleanShutdownObserved=True)
 elif r['action']=='copy-slow':
  for c in ['old','mid','new']:call(['exec','qualifier','-c',c,'--','/bin/sh','-c','test ! -e /run/qual/launch.pid'])
  code="""import pathlib,json,os,stat,shutil,hashlib
src=pathlib.Path('/copies/old');dst=pathlib.Path('/copies/new/slow-copy');assert not dst.exists()and not dst.is_symlink()
def inventory(root):
 rows=[];total=0
 for p in[root,*sorted(root.rglob('*'))]:
  s=p.lstat();rel=str(p.relative_to(root));row=[rel,s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode),s.st_mtime_ns]
  if stat.S_ISREG(s.st_mode):total+=s.st_size;row+=['file',s.st_size,hashlib.file_digest(p.open('rb'),'sha256').hexdigest()]
  elif stat.S_ISDIR(s.st_mode):row+=['directory']
  else:assert stat.S_ISLNK(s.st_mode);link=os.readlink(p);assert rel=='data-0/data-0/mysql.sock'and link=='/var/run/mysqld/mysqld.sock';row+=['symlink',link]
  rows.append(row);assert len(rows)<=4096 and total<=384*1024**2
 return rows,total
before,total=inventory(src);shutil.copytree(src,dst,symlinks=True)
for row in reversed(before):
 p=dst/row[0];os.chown(p,row[1],row[2],follow_symlinks=False)
 if row[5]!='symlink':os.chmod(p,row[3])
 os.utime(p,ns=(row[4],row[4]),follow_symlinks=False)
after,after_total=inventory(dst);assert before==after and total==after_total and inventory(src)==(before,total)
print(json.dumps({'passed':True,'entries':len(before),'bytes':total,'sourceAndDestinationFullMetadataMatch':True,'sourceUnchanged':True,'manifestSHA256':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),'originalUnstartedCandidatePreserved':True}))
"""
  out.update(json.loads(call(['exec','-i','qualifier','-c','reader','--','python3','-B','-c',code],timeout=180)))
 elif r['action']in ['ready','snapshot']:
  values,_=q.native(key);sql=q.SQL(ns,'qualifier',side,None if r.get('admin',True)else values);start=time.monotonic()
  while True:
   try:
    version=sql.query('SELECT VERSION()').decode().strip();assert version=={'old':'5.7.44','mid':'8.0.46','new':'8.4.13'}[side];assert sql.query('SELECT @@skip_networking').strip()==b'1';break
   except Exception:
    if time.monotonic()-start>120:raise
    time.sleep(3)
  out.update(passed=True,version=version,admin=r.get('admin',True))
  if not r.get('admin',True):
   actual=call(['exec','qualifier','-c',side,'--','/bin/sh','-c','p=$(cat /run/qual/launch.pid); cat /proc/$p/cmdline'])
   assert actual.split(b'\0')==[v.encode()for v in r['normalStartupFlags']]+[b'']and'--skip-grant-tables'not in r['normalStartupFlags']
   wrong=dict(values);wrong['MYSQL_PASSWORD']=values['MYSQL_PASSWORD']+'-isolated-negative-control';bad=q.SQL(ns,'qualifier',side,wrong)
   denied=subprocess.run(['kubectl','--request-timeout=30s','-n',ns,'exec','-i','qualifier','-c',side,'--','/bin/bash','-c',q.CLIENT],input=bad.config+b'\0SELECT 1;\n',capture_output=True,timeout=45)
   assert denied.returncode!=0 and b'ERROR 1045'in denied.stderr and not denied.stdout
   assert sql.query('SELECT 1').strip()==b'1';out.update(authenticationEnabled=True,wrongPasswordRejectedWith1045=True,currentUserHMAC=q.mac(key,'current-user',sql.query('SELECT CURRENT_USER()')),nativeSecret=q.native(key)[1])
  if r['action']=='snapshot':out['snapshot']=snapshot(sql,key,r.get('grantColumns'));out['nativeSecret']=q.native(key)[1]
 elif r['action']=='inspect':out.update(passed=True,exactIsolatedPodAndPolicy=True)
 elif r['action']=='diagnose':
  raw=call(['exec','qualifier','-c',side,'--','cat','/run/qual/error.log']);out.update(passed=True,errorLogHMAC=q.mac(key,'error-log',raw),codes=sorted(set(re.findall(rb'MY-[0-9]+',raw))),rawLogReturned=False)
  out['codes']=[s.decode()for s in out['codes']]
 else:raise ValueError('unsupported_action')
 guard()
except Exception as e:out.update(passed=False,errorType=type(e).__name__,sourceLines=[f.lineno for f in traceback.extract_tb(e.__traceback__)if f.filename in['<string>','<reviewed-sql>']])
print(json.dumps(out))
'''


def remote(program, request, timeout=360):
    proc = subprocess.run(SSH + [shlex.join(['python3', '-B', '-c', program])],
                          input=json.dumps(request).encode(), capture_output=True, timeout=timeout)
    assert proc.returncode == 0, 'remote_control_failed_raw_details_suppressed'
    return json.loads(proc.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'start', 'stop', 'ready', 'snapshot', 'diagnose', 'copy-slow'])
    parser.add_argument('--side', choices=['old', 'mid', 'new'])
    parser.add_argument('--normal-auth', action='store_true')
    parser.add_argument('--label', required=True)
    parser.add_argument('--grant-baseline', type=Path)
    parser.add_argument('--resume-empty-restore', action='store_true')
    args = parser.parse_args()
    assert os.getuid() == 1000 and F.is_mount()
    os.umask(0o077)
    import re
    assert re.fullmatch('[a-z0-9-]{1,64}', args.label)
    receipt = OUT / (args.label + '.json')
    assert not receipt.exists()
    if args.action == 'prepare':
        assert not (OUT / 'trial-state.json').exists() or args.resume_empty_restore
        run = uuid.uuid4().hex[:12]
        ns = 'ruckusdb-upstream-' + run
        containers = []
        for name, image in [('old', OLD), ('mid', MID), ('new', NEW), ('reader', READER)]:
            reader = name == 'reader'
            mounts = ([{'name': x, 'mountPath': '/copies/' + x} for x in ['old', 'new']] if reader else
                      [{'name': 'old' if name == 'old' else 'new', 'mountPath': '/copy'},
                       {'name': name + '-run', 'mountPath': '/run/qual'}])
            containers.append({'name': name, 'image': image, 'imagePullPolicy': 'IfNotPresent',
                'command': ['python3', '-B', '-c', 'import time;time.sleep(3600)'] if reader else ['/bin/sh', '-c', 'exec sleep 3600'],
                'resources': {'requests': {'cpu': '25m', 'memory': '32Mi'}, 'limits': {'cpu': '1000m', 'memory': '2048Mi' if reader else '1536Mi'}},
                'securityContext': {'runAsUser': 0 if reader else 999, 'runAsGroup': 0 if reader else 65534,
                    'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                    'capabilities': {'drop': ['ALL'], **({'add': ['CHOWN', 'FOWNER', 'DAC_OVERRIDE']} if reader else {})}},
                'volumeMounts': mounts})
        docs = [{'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': ns}},
                {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy', 'metadata': {'name': 'deny-all', 'namespace': ns},
                 'spec': {'podSelector': {}, 'policyTypes': ['Ingress', 'Egress'], 'ingress': [], 'egress': []}},
                {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': 'qualifier', 'namespace': ns},
                 'spec': {'nodeName': 'workernode2', 'restartPolicy': 'Never', 'activeDeadlineSeconds': 3600,
                          'automountServiceAccountToken': False, 'enableServiceLinks': False,
                          'securityContext': {'fsGroup': 65534, 'supplementalGroupsPolicy': 'Strict', 'seccompProfile': {'type': 'RuntimeDefault'}}, 'containers': containers,
                          'volumes': [{'name': name, 'emptyDir': {'medium': 'Memory', 'sizeLimit': size}}
                                      for name, size in [('old', '384Mi'), ('new', '2Gi'), ('old-run', '64Mi'), ('mid-run', '64Mi'), ('new-run', '64Mi')]]}}]
        # Resource creation receipts are persisted before any archive transfer.
        program = """import json,sys,subprocess,hashlib
docs=json.load(sys.stdin);out=[]
for d in docs:
 p=json.loads(subprocess.check_output(['kubectl','create','-f','-','-o','json'],input=json.dumps(d).encode(),stderr=subprocess.DEVNULL,timeout=60));out.append({'kind':p['kind'],'name':p['metadata']['name'],'uid':p['metadata']['uid'],**({'specSHA256':hashlib.sha256(json.dumps(p['spec'],sort_keys=True).encode()).hexdigest()}if p['kind']=='Pod'else{})})
print(json.dumps(out))
"""
        if args.resume_empty_restore:
            state = json.loads((OUT / 'trial-state.json').read_text())
            diagnosis = json.loads((OUT / 'trial-restore-diagnostic-01.json').read_text())
            assert diagnosis['readOnly'] and all(v['entries'] == 0 for v in diagnosis['restoredCopyInventory'].values())
            ns = state['namespace']
            assert remote(NODE, {'state': state, 'action': 'inspect', 'key': (F / 'acceptance-ruckus-20261025/hmac-key.hex').read_text().strip(),
                                 'sqlSource': (ROOT / 'scripts/migration/qualify-ruckusdb.py').read_text(), 'snapshotSource': SNAPSHOT})['passed']
        else:
            owned = remote(program, docs)
            state = {'namespace': ns, 'namespaceUID': owned[0]['uid'], 'podUID': owned[2]['uid'], 'podSpecSHA256': owned[2]['specSHA256'], 'owned': owned,
                     'productionClaimsMounted': False, 'trialOnly': True, 'historicalReceipt': str(HISTORICAL)}
            (OUT / 'trial-state.json').write_text(json.dumps(state, indent=2) + '\n')
        subprocess.run(SSH + [shlex.join(['kubectl', '-n', ns, 'wait', 'pod/qualifier', '--for=condition=Ready', '--timeout=180s'])],
                       check=True, capture_output=True, timeout=200)
        spec = importlib.util.spec_from_file_location('original_restore', ROOT / 'scripts/migration/qualify-ruckusdb-copies.py')
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        restore_code = old.RESTORE.replace("name=='data-0/mysql.sock'", "name=='data-0/data-0/mysql.sock'")
        restore_source = F / ('control-source/upstream-ruckusdb-20261026/trial-restore-r2.py' if args.resume_empty_restore else 'control-source/upstream-ruckusdb-20261026/trial-restore.py')
        assert not restore_source.exists() or restore_source.read_text() == restore_code
        if not restore_source.exists():
            restore_source.write_text(restore_code)
        historical = json.loads(HISTORICAL.read_text())
        archive = Path(historical['archive_path'])
        assert historical['status'] == 'passed' and historical['fully_authenticated']
        assert hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() == historical['archive_sha256'] == '4b34b6920825b3e860a63e346e0dbd32fce792ffc89e30c997d10a2f63e4442c'
        # The historical receipt hashes its pretty JSON manifest file, whereas
        # the tar stores canonical JSON. Bind both complete objects, then use
        # the embedded bytes' digest; do not substitute the file digest.
        manifest_reader = subprocess.Popen(['/home/brajam/.local/share/branconet-migration/bin/age', '-d', '-i', '/home/brajam/.ssh/id_ed25519', str(archive)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            with tarfile.open(fileobj=manifest_reader.stdout, mode='r|') as stream:
                member = stream.next()
                assert member.name == 'manifest.json' and member.size <= 8 * 1024**2
                embedded = stream.extractfile(member).read()
                manifest_file = Path(historical['manifest_path'])
                assert hashlib.sha256(manifest_file.read_bytes()).hexdigest() == historical['manifest_sha256']
                assert json.loads(embedded) == json.loads(manifest_file.read_bytes())
                embedded_digest = hashlib.sha256(embedded).hexdigest()
        finally:
            manifest_reader.stdout.close()
            if manifest_reader.poll() is None:
                manifest_reader.terminate()
            manifest_reader.wait(timeout=20)
        results = []
        for side in ['old', 'new']:
            age = subprocess.Popen(['/home/brajam/.local/share/branconet-migration/bin/age', '-d', '-i', '/home/brajam/.ssh/id_ed25519', str(archive)],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=dict(os.environ, GOMAXPROCS='1', GOMEMLIMIT='64MiB'))
            target = subprocess.Popen(SSH + [shlex.join(['kubectl', '-n', ns, 'exec', '-i', 'qualifier', '-c', 'reader', '--',
                                       'python3', '-B', '-c', restore_code, side])], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            try:
                target.stdin.write((embedded_digest + '\n').encode())
                for block in iter(lambda: age.stdout.read(1024**2), b''):
                    target.stdin.write(block)
                target.stdin.close()
                raw = target.stdout.read(65537)
                assert age.wait(timeout=30) == target.wait(timeout=30) == 0
                result = json.loads(raw)
                assert result['restored'] and result['file_bytes'] == 213330203
                results.append(result)
            finally:
                for child in [age, target]:
                    if child.poll() is None:
                        child.terminate()
                        child.wait(timeout=15)
        result = {'passed': True, 'state': state, 'restores': results, 'historicalTrialOnly': True, 'productionClaimsMounted': False,
                  'manifestObjectsExactlyEqual': True, 'embeddedManifestSHA256': embedded_digest,
                  'manifestFileSHA256': historical['manifest_sha256'], 'completeCiphertextSHA256': historical['archive_sha256']}
    else:
        state = json.loads((OUT / 'trial-state.json').read_text())
        if args.action == 'copy-slow':
            stopped = json.loads((OUT / 'old-stop-01.json').read_text())
            assert stopped['passed'] and stopped['cleanShutdownObserved']
        request = {'state': state, 'action': args.action, 'side': args.side, 'admin': not args.normal_auth,
                   'key': (F / 'acceptance-ruckus-20261025/hmac-key.hex').read_text().strip(),
                   'sqlSource': (ROOT / 'scripts/migration/qualify-ruckusdb.py').read_text(), 'snapshotSource': SNAPSHOT}
        if args.action == 'start' and args.side != 'old':
            settings = json.loads((OUT / 'live-server-settings.json').read_text())
            assert settings['passed'] and settings['version'] == '5.7.44'
            request['serverSettings'] = settings['settings']
        if args.action in ['ready', 'snapshot'] and args.normal_auth:
            started = json.loads((OUT / 'new-normal-start-03.json').read_text())
            assert started['passed'] and '--skip-grant-tables' not in started['flags']
            request['normalStartupFlags'] = started['flags']
        if args.grant_baseline:
            baseline = json.loads(args.grant_baseline.read_text())
            assert baseline['passed']
            request['grantColumns'] = baseline['snapshot']['grantColumns']
        result = remote(NODE, request)
    result['controllerSHA256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result['remoteProgramSHA256'] = hashlib.sha256(NODE.encode()).hexdigest()
    result['snapshotSourceSHA256'] = hashlib.sha256(SNAPSHOT.encode()).hexdigest()
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': result['passed'], 'action': args.action, 'receipt': str(receipt),
                      'errorType': result.get('errorType'), 'sourceLines': result.get('sourceLines')}))
    return int(not result['passed'])


if __name__ == '__main__':
    import sys
    import traceback
    try:
        raise SystemExit(main())
    except Exception as error:
        label = sys.argv[sys.argv.index('--label') + 1] if '--label' in sys.argv else ''
        import re
        if re.fullmatch('[a-z0-9-]{1,64}', label):
            path = OUT / (label + '.json')
            if not path.exists():
                path.write_text(json.dumps({'passed': False, 'errorType': type(error).__name__,
                    'sourceLines': [f.lineno for f in traceback.extract_tb(error.__traceback__) if f.filename == __file__],
                    'failedTrialRetained': True, 'rawDetailsSuppressed': True}, indent=2) + '\n')
        print(json.dumps({'passed': False, 'errorType': type(error).__name__, 'rawDetailsSuppressed': True}))
        raise SystemExit(1)
