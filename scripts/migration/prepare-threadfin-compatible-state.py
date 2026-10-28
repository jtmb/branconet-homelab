#!/usr/bin/env python3
"""Preserve original user choices while adopting vendor-parsed channel metadata."""
import argparse
import ast
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'upstream-xteve-20261026'

INVENTORY = r'''
def inventory_source():
 root=Path('/source');entries={};total=0
 for p in [root,*sorted(root.rglob('*'))]:
  s=p.lstat();assert p.resolve()==p and not p.is_symlink();name='data-0'+('/'+str(p.relative_to(root))if p!=root else'');row={'uid':s.st_uid,'gid':s.st_gid,'mode':stat.S_IMODE(s.st_mode)}
  if stat.S_ISDIR(s.st_mode):row['kind']='directory'
  else:
   assert stat.S_ISREG(s.st_mode)and s.st_nlink==1;total+=s.st_size;assert total<=4*1024**3;row.update(kind='file',bytes=s.st_size)
   with p.open('rb')as f:row['sha256']=hashlib.file_digest(f,'sha256').hexdigest()
  entries[name]=row;assert len(entries)<=4096
 return {'entries':entries,'total_file_bytes':total}
'''

MIGRATE = r'''
import copy,hmac
key=bytes.fromhex(request['key']);assert len(key)==32
def mac(value):return hmac.new(key,json.dumps(value,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()
original=Path('/original');assert source.samefile(original/request['sourcePrefix']);assert target.samefile(original/prefix)
core={name:(original/name).read_bytes()for name in ['settings.json','authentication.json','xepg.json']}
assert all(len(b)<=16*1024**2 for b in core.values());legacy=json.loads(core['settings.json']);reference=json.loads((source/'settings.json').read_bytes());oldmap=json.loads(core['xepg.json']);refmap=json.loads((source/'xepg.json').read_bytes());auth=json.loads(core['authentication.json'])
assert legacy['version']=='2.1.0'and legacy['xteveAutoUpdate']is False and reference['version']=='0.5.0'and reference['ThreadfinAutoUpdate']is False
settings=copy.deepcopy(legacy);settings.update(version='0.5.0',ThreadfinAutoUpdate=False);providers=0
assert set(legacy['files'])==set(reference['files'])
for kind,group in settings['files'].items():
 assert set(group)==set(reference['files'][kind])
 for ident,row in group.items():
  ref=reference['files'][kind][ident];providers+=1
  for field,value in row.items():
   if field not in ['compatibility','last.update','counter.download','counter.error','provider.availability']:assert ref.get(field)==value
  assert isinstance(row['file.xteve'],str);row['file.threadfin']=row['file.xteve'];row['compatibility']=copy.deepcopy(ref.get('compatibility',row.get('compatibility',{})))
  for field in ['http_proxy.ip','http_proxy.port']:
   assert ref.get(field,'')=='' and field not in row;row[field]=''
def signature(row):return(row['url'],row['_file.m3u.id'])
index={signature(row):row for row in refmap.values()};assert len(index)==len(refmap)==len(oldmap)==108 and len({signature(row)for row in oldmap.values()})==len(oldmap)
desired=copy.deepcopy(oldmap);derived=['tvg-id','_uuid.key','_uuid.value','_values'];changes={}
for ident,row in desired.items():
 ref=index[signature(row)]
 for field in derived:
  if field in ref:row[field]=copy.deepcopy(ref[field])
 if row.get('x-xmltv-file')=='xTeVe Dummy':row['x-xmltv-file']='Threadfin Dummy'
 difference={field:mac(value)for field,value in row.items()if oldmap[ident].get(field)!=value};assert set(difference)<=set(derived+['x-xmltv-file'])
 if difference:changes[mac(ident)]=difference
assert sum(row.get('x-active')is True for row in desired.values())==29
def write(name,body,owner):
 p=target/name;fd=os.open(p,os.O_WRONLY|os.O_TRUNC|os.O_NOFOLLOW)
 try:
  with os.fdopen(fd,'wb',closefd=False)as f:f.write(body);f.flush();os.fsync(f.fileno())
  os.fchown(fd,owner.st_uid,owner.st_gid);os.fchmod(fd,stat.S_IMODE(owner.st_mode))
 finally:os.close(fd)
for name,value in [('settings.json',settings),('xepg.json',desired)]:write(name,(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode(),(original/name).stat())
write('authentication.json',core['authentication.json'],(original/'authentication.json').stat())
for name,body in core.items():assert(original/name).read_bytes()==body
for rel,row in rows.items():verify(source/rel,row)
def project(value,new):
 v=copy.deepcopy(value);v['version']='2.1.0';v.pop('xteveAutoUpdate',None);v.pop('ThreadfinAutoUpdate',None)
 for group in v['files'].values():
  for provider in group.values():
   if new:
    assert provider.pop('file.threadfin')==provider['file.xteve']
    for field in ['http_proxy.ip','http_proxy.port']:assert provider.pop(field)==''
   for field in ['last.update','counter.download','counter.error','provider.availability']:provider.pop(field,None)
   compat=provider.get('compatibility',{});compat.pop('xmltv.channels',None);compat.pop('xmltv.programs',None)
 return {field:mac(v)for field,v in v.items()}
for user in auth.get('users',{}).values():user['data'].setdefault('authentication.config',False)
fingerprints=lambda data:{mac(ident):{field:mac(value)for field,value in row.items()}for ident,row in data.items()}
print(json.dumps({'passed':True,'subPath':prefix,'referencePrefix':request['sourcePrefix'],'referenceFilesUnchanged':True,'primaryCoreFilesUnchanged':True,'originalRootNeverOpenedForWrite':True,'providersPreserved':providers,'originalSettings':project(legacy,False),'expectedSettings':project(settings,True),'originalMappings':fingerprints(oldmap),'expectedMappings':fingerprints(desired),'expectedAuthentication':mac(auth),'accountCount':len(auth.get('users',{})),'mappingCount':len(desired),'activeMappings':29,'sourceDerivedFields':derived+['x-xmltv-file'],'expectedMappingChanges':changes,'referenceManifestSHA256':hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'primaryCoreSHA256':{n:hashlib.sha256(b).hexdigest()for n,b in core.items()},'copiedBytes':manifest['total_file_bytes']}))
'''

NODE = r'''
import json,sys,subprocess,uuid,time,resource
resource.setrlimit(resource.RLIMIT_CORE,(0,0));r=json.loads(sys.stdin.buffer.read(1048576));run=uuid.uuid4().hex;prefix=r.get('resumePrefix')or'threadfin-20261026-'+run[:12];name='threadfin-compatible-'+run[:12];created=[];pod=None;out={'passed':False}
def call(a,data=None):return subprocess.check_output(['kubectl','--request-timeout=30s','-n','plex',*a],input=data,stderr=subprocess.DEVNULL,timeout=180)
def get(k,n):return json.loads(call(['get',k,n,'-o','json']))
def fence():
 d=get('deployment','xteve');assert d['metadata']['uid']=='52adec00-5c42-4cd2-8fb0-9428828ca368'and d['spec']['replicas']==1 and all(d['status'].get(k)==1 for k in ['replicas','readyReplicas','availableReplicas','updatedReplicas']);assert d['spec']['template']['spec']['containers'][0]['image']=='docker.io/library/xteve-security-20261023@sha256:0ab77160ccccaf9235dcb3864624440551d6dd63c771cfaf97094db869a28656'
 pvc=get('pvc','xteve-data-0');assert pvc['metadata']['uid']=='d40f1490-7254-4599-be82-2fad35abb88b'and pvc['status']['phase']=='Bound';writers=[]
 for p in json.loads(call(['get','pods','-o','json']))['items']:
  if not any(v.get('persistentVolumeClaim',{}).get('claimName')=='xteve-data-0'for v in p['spec'].get('volumes',[])):continue
  if pod and p['metadata']['uid']==pod['metadata']['uid']:continue
  if p['status']['phase']in['Succeeded','Failed']:continue
  assert p['metadata'].get('labels',{}).get('app')=='xteve'and p['spec']['nodeName']=='workernode2'and p['spec']['containers'][0]['image']==d['spec']['template']['spec']['containers'][0]['image'];rs=get('replicaset',p['metadata']['ownerReferences'][0]['name']);assert any(o['uid']==d['metadata']['uid']for o in rs['metadata']['ownerReferences']);writers.append(p['metadata']['uid'])
 assert len(writers)==1;return(d['metadata']['generation'],writers)
def create(obj):
 p=json.loads(call(['create','-f','-','-o','json'],json.dumps(obj).encode()));created.append((p['kind'],p['metadata']['name'],p['metadata']['uid']));return p
try:
 before=fence();labels={'threadfin-compatible-copy':run};create({'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':{'name':name,'namespace':'plex'},'spec':{'podSelector':{'matchLabels':labels},'policyTypes':['Ingress','Egress'],'ingress':[],'egress':[]}})
 pod=create({'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'plex','labels':labels},'spec':{'nodeName':'workernode2','restartPolicy':'Never','activeDeadlineSeconds':600,'automountServiceAccountToken':False,'securityContext':{'runAsUser':0,'runAsGroup':0,'seccompProfile':{'type':'RuntimeDefault'}},'containers':[{'name':'copy','image':'docker.io/library/python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1','imagePullPolicy':'IfNotPresent','command':['python3','-B','-c','import time;time.sleep(600)'],'resources':{'requests':{'cpu':'10m','memory':'32Mi'},'limits':{'cpu':'500m','memory':'256Mi'}},'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL'],'add':['CHOWN','DAC_OVERRIDE','FOWNER']}},'volumeMounts':[{'name':'state','mountPath':'/source','subPath':r['sourcePrefix'],'readOnly':True},{'name':'state','mountPath':'/original','readOnly':True},{'name':'state','mountPath':'/target'}]}],'volumes':[{'name':'state','persistentVolumeClaim':{'claimName':'xteve-data-0'}}]}});call(['wait','pod/'+name,'--for=condition=Ready','--timeout=60s']);assert fence()==before;out.update(json.loads(call(['exec','-i',name,'--','python3','-B','-c',r['copyCode']],json.dumps({'prefix':prefix,'sourcePrefix':r['sourcePrefix'],'key':r['key'],'resume':bool(r.get('resumePrefix'))}).encode())));assert out['passed']and fence()==before
except Exception as e:
 out.update(passed=False,errorType=type(e).__name__,failedCandidatePrefix=prefix)
 if isinstance(e,subprocess.CalledProcessError):
  try:out['innerDiagnostic']=json.loads(e.output)
  except Exception:pass
finally:
 out['createdResources']=[{'kind':k,'name':n,'uid':u}for k,n,u in created];out['deletedResources']=[]
 if out['passed']:
  for k,n,u in reversed(created):
   p=get(k,n);assert p['metadata']['uid']==u;group='/api/v1'if k=='Pod'else'/apis/networking.k8s.io/v1';kind='pods'if k=='Pod'else'networkpolicies';call(['delete','--raw',group+'/namespaces/plex/'+kind+'/'+n,'-f','-'],json.dumps({'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':u}}).encode());call(['wait',k+'/'+n,'--for=delete','--timeout=45s']);out['deletedResources'].append({'kind':k,'name':n,'uid':u})
 print(json.dumps(out))
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--resume-verified-copy', action='store_true')
    a = p.parse_args()
    assert a.apply and os.getuid() == 1000 and ROOT.is_mount()
    os.umask(0o077)
    target = OUT / ('compatible-state-copy-r2.json' if a.resume_verified_copy else 'compatible-state-copy.json')
    assert not target.exists()
    for scope in ['state', 'config']:
        s = json.loads((ROOT / 'operator-control' / ('smb-xteve-upstream-' + scope + '-copy-status.json')).read_text())
        assert all(row['phase'] == 'verified' and row['completeAgeAuthentication'] for row in s['files'])
    source = Path(__file__).with_name('prepare-threadfin-state-copy.py')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == '6626c7b54e9c7f6065f795a84300872f54ba846e930a7c92cd8ccbb9551f7068'
    spec = importlib.util.spec_from_file_location('exact_copy_primitives', source)
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    code = base.COPY[:base.COPY.index("settings=target/'settings.json'")]
    code = code.replace("request=json.loads", INVENTORY + '\nrequest=json.loads').replace("manifest=request['manifest']", 'manifest=inventory_source()') + MIGRATE
    if a.resume_verified_copy:
        prior = json.loads((OUT / 'compatible-state-copy.json').read_text())
        diagnosis = json.loads((OUT / 'compatible-copy-readonly-diagnosis.json').read_text())
        assert not prior['passed'] and prior['errorType'] == 'CalledProcessError'
        assert diagnosis['passed'] and diagnosis['diagnosis']['readOnly'] and diagnosis['diagnosis']['stage'] == 'channel_correspondence'
        code = code.replace("and not target.exists()and not target.is_symlink()", "and target.exists()and not target.is_symlink()")
        start = code.index('target.mkdir(mode=0o700)')
        finish = code.index('\nimport copy,hmac', start)
        code = code[:start] + "assert {str(p.relative_to(target))for p in target.rglob('*')}==set(rows)-{''}\nfor rel,row in rows.items():verify(target/rel,row)\n" + code[finish:]
    ast.parse(code)
    import textwrap
    code = 'import json,traceback\ntry:\n' + textwrap.indent(code, ' ') + "\nexcept Exception as e:\n print(json.dumps({'passed':False,'errorType':type(e).__name__,'sourceLines':[f.lineno for f in traceback.extract_tb(e.__traceback__)]}))\n raise SystemExit(1)\n"
    ast.parse(code)
    request = {'copyCode': code, 'sourcePrefix': json.loads((OUT / 'prepared-state-copy.json').read_text())['subPath'], 'key': (ROOT / 'acceptance-xteve-20261025/hmac-key').read_text().strip()}
    if a.resume_verified_copy:
        request['resumePrefix'] = prior['failedCandidatePrefix']
    ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
    child = subprocess.run(ssh + [shlex.join(['python3', '-B', '-c', NODE])], input=json.dumps(request).encode(), capture_output=True, timeout=450)
    try:
        result = json.loads(child.stdout)
    except Exception:
        result = {'passed': False, 'rawDetailsSuppressed': True, 'exitCode': child.returncode}
    result.update(UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(), sourceSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), copyPrimitivesSHA256=hashlib.sha256(source.read_bytes()).hexdigest())
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result.get(k) for k in ['passed', 'subPath', 'mappingCount', 'activeMappings', 'providersPreserved', 'errorType', 'failedCandidatePrefix']}))
    return int(child.returncode != 0 or not result['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
