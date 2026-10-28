#!/usr/bin/env python3
"""Copy authenticated cold xTeVe state into one new directory on its same PVC."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import resource
from pathlib import Path
import shlex
import subprocess

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'upstream-xteve-20261026'
HELPER = 'docker.io/library/python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1'

COPY = r'''
import json,sys,os,stat,hashlib,shutil,re,resource
from pathlib import Path,PurePosixPath
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
request=json.loads(sys.stdin.buffer.read(8*1024**2+1));manifest=request['manifest'];prefix=request['prefix']
assert re.fullmatch(r'threadfin-20261026-[a-f0-9]{12}',prefix)
source=Path('/source');target=Path('/target')/prefix
assert source.is_dir()and source.resolve()==source and not target.exists()and not target.is_symlink()
rows={}
for name,row in manifest['entries'].items():
 assert name=='data-0'or name.startswith('data-0/');rel=name[7:]if name.startswith('data-0/')else''
 assert not PurePosixPath(rel).is_absolute()and'..'not in PurePosixPath(rel).parts and rel not in rows
 assert row['kind']in['file','directory'];rows[rel]=row
assert ''in rows and len(rows)<=4096 and manifest['total_file_bytes']<=4*1024**3
def digest(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def verify(p,row,content=True):
 s=p.lstat();assert p.resolve()==p and not p.is_symlink()
 assert [s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode)]==[row['uid'],row['gid'],row['mode']]
 assert stat.S_ISDIR(s.st_mode)if row['kind']=='directory'else stat.S_ISREG(s.st_mode)and s.st_nlink==1 and s.st_size==row['bytes']
 if content and row['kind']=='file':assert digest(p)==row['sha256']
 return s
for rel,row in rows.items():verify(source/rel,row)
assert {str(p.relative_to(source))for p in source.rglob('*')}==set(rows)-{''}
space=os.statvfs('/target');assert space.f_bavail*space.f_frsize>=manifest['total_file_bytes']+64*1024**2
target.mkdir(mode=0o700)
for rel,row in sorted(rows.items(),key=lambda x:(len(PurePosixPath(x[0]).parts),x[0])):
 if not rel:continue
 dst=target/rel;src=source/rel;assert dst.is_relative_to(target)and dst.resolve()==dst
 if row['kind']=='directory':dst.mkdir(mode=0o700)
 else:
  before=verify(src,row);fd=os.open(src,os.O_RDONLY|os.O_NOFOLLOW)
  try:
   opened=os.fstat(fd);assert(opened.st_dev,opened.st_ino)==(before.st_dev,before.st_ino)
   with os.fdopen(fd,'rb',closefd=False)as inp,dst.open('xb')as out:shutil.copyfileobj(inp,out,1024**2);out.flush();os.fsync(out.fileno())
  finally:os.close(fd)
  assert digest(dst)==row['sha256'];verify(src,row)
for rel,row in sorted(rows.items(),key=lambda x:len(PurePosixPath(x[0]).parts),reverse=True):
 p=target/rel;os.chown(p,row['uid'],row['gid']);os.chmod(p,row['mode']);verify(p,row)
assert {str(p.relative_to(target))for p in target.rglob('*')}==set(rows)-{''}
settings=target/'settings.json';original=settings.read_bytes();settings_stat=settings.stat();value=json.loads(original);assert value['xteveAutoUpdate']is False
updated=dict(value,ThreadfinAutoUpdate=False);raw=(json.dumps(updated,ensure_ascii=False,indent=2)+'\n').encode();fd=os.open(settings,os.O_WRONLY|os.O_TRUNC|os.O_NOFOLLOW)
try:
 with os.fdopen(fd,'wb',closefd=False)as f:f.write(raw);f.flush();os.fsync(f.fileno())
finally:os.close(fd)
assert json.loads(settings.read_bytes())==updated and json.loads((source/'settings.json').read_bytes())==value
after=settings.stat();assert(after.st_uid,after.st_gid,after.st_mode)==(settings_stat.st_uid,settings_stat.st_gid,settings_stat.st_mode)
for rel,row in rows.items():
 verify(source/rel,row)
 if rel!='settings.json':verify(target/rel,row)
assert {str(p.relative_to(source))for p in source.rglob('*')if p!=source/prefix and source/prefix not in p.parents}==set(rows)-{''}
print(json.dumps({'passed':True,'subPath':prefix,'files':sum(r['kind']=='file'for r in rows.values()),'copiedBytes':manifest['total_file_bytes'],'originalFilesAndMetadataUnchanged':True,'allCopiedFilesVerified':True,'onlyCopiedSettingAdded':'ThreadfinAutoUpdate=false','originalSettingsSHA256':hashlib.sha256(original).hexdigest(),'copiedSettingsSHA256':hashlib.sha256(raw).hexdigest(),'originalAuthenticationSHA256':digest(source/'authentication.json'),'copiedAuthenticationSHA256':digest(target/'authentication.json')}))
'''

NODE = r'''
import json,sys,subprocess,uuid,shlex,time,datetime,socket
assert socket.gethostname().split('.')[0].lower()=='masternode'
request=json.loads(sys.stdin.buffer.read(8*1024**2+1));run=uuid.uuid4().hex;name='threadfin-state-'+run[:12];prefix='threadfin-20261026-'+run[:12];created=[];result={'passed':False,'originalStateDeleted':False,'temporaryResources':[]};pod=None
def call(args,data=None):return subprocess.check_output(['kubectl','--request-timeout=30s','-n','plex',*args],input=data,stderr=subprocess.DEVNULL,timeout=100)
def get(kind,n,ns='plex'):return json.loads(subprocess.check_output(['kubectl','--request-timeout=30s','-n',ns,'get',kind,n,'-o','json'],stderr=subprocess.DEVNULL,timeout=40))
def fence():
 d=get('deployment','xteve');h=get('helmrelease','xteve','flux-system')
 assert d['metadata']['uid']=='52adec00-5c42-4cd2-8fb0-9428828ca368'and h['metadata']['uid']=='ace99a34-343b-40cd-b1b3-6ef2f324a8b0'
 for x in[d,h]:assert x['status'].get('observedGeneration')==x['metadata']['generation']and not x['metadata'].get('deletionTimestamp')
 assert d['spec']['replicas']==0 and all(d['status'].get(k,0)==0 for k in['replicas','readyReplicas','availableReplicas','updatedReplicas'])
 assert d['spec']['template']['spec']['containers'][0]['image']=='docker.io/library/xteve-security-20261023@sha256:0ab77160ccccaf9235dcb3864624440551d6dd63c771cfaf97094db869a28656'
 assert h['spec']['values']['replicaCount']==0 and not h['spec'].get('suspend',False)and any(c['type']=='Ready'and c['status']=='True'for c in h['status'].get('conditions',[]))
 for claim,uid in [('xteve-data-0','d40f1490-7254-4599-be82-2fad35abb88b'),('xteve-data-1','b7207fe9-3768-4ad5-9ca0-ee4429137b33')]:
  p=get('pvc',claim);assert p['metadata']['uid']==uid and p['status']['phase']=='Bound';pv=get('pv',p['spec']['volumeName']);assert pv['spec']['claimRef']['uid']==uid and pv['spec']['csi']['driver']=='driver.longhorn.io'
 for p in json.loads(call(['get','pods','-o','json']))['items']:
  if not any(v.get('persistentVolumeClaim',{}).get('claimName')in['xteve-data-0','xteve-data-1']for v in p['spec'].get('volumes',[])):continue
  if pod and p['metadata']['uid']==pod['metadata']['uid']:continue
  assert p['status']['phase']in['Succeeded','Failed']and not any('running'in s.get('state',{})for k in['containerStatuses','initContainerStatuses','ephemeralContainerStatuses']for s in p['status'].get(k,[]))
 return {'deploymentGeneration':d['metadata']['generation'],'releaseGeneration':h['metadata']['generation']}
def create(obj):
 r=json.loads(call(['create','-f','-','-o','json'],json.dumps(obj).encode()));created.append((r['kind'],r['metadata']['name'],r['metadata']['uid']));return r
try:
 original=fence();node=get('node','workernode2');assert node['metadata']['uid']=='eda66e65-f388-4b97-b64f-a709cda81894'and any(c['type']=='Ready'and c['status']=='True'for c in node['status']['conditions'])
 label={'threadfin-state-copy':run};create({'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':{'name':name,'namespace':'plex'},'spec':{'podSelector':{'matchLabels':label},'policyTypes':['Ingress','Egress'],'ingress':[],'egress':[]}})
 pod=create({'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'plex','labels':label},'spec':{'nodeName':'workernode2','restartPolicy':'Never','activeDeadlineSeconds':600,'automountServiceAccountToken':False,'securityContext':{'runAsUser':0,'runAsGroup':0,'seccompProfile':{'type':'RuntimeDefault'}},'containers':[{'name':'copy','image':request['helperImage'],'imagePullPolicy':'IfNotPresent','command':['python3','-B','-c','import time;time.sleep(600)'],'resources':{'requests':{'cpu':'10m','memory':'32Mi'},'limits':{'cpu':'500m','memory':'256Mi'}},'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL'],'add':['CHOWN','DAC_OVERRIDE','FOWNER']}},'volumeMounts':[{'name':'state','mountPath':'/source','readOnly':True},{'name':'state','mountPath':'/target'}]}],'volumes':[{'name':'state','persistentVolumeClaim':{'claimName':'xteve-data-0'}}]}})
 call(['wait','pod/'+name,'--for=condition=Ready','--timeout=80s']);assert fence()==original
 live=get('pod',name);assert live['metadata']['uid']==pod['metadata']['uid']and live['spec']['containers'][0]['image']==request['helperImage']and live['status']['containerStatuses'][0]['ready']
 output=call(['exec','-i',name,'-c','copy','--','python3','-B','-c',request['copyCode']],json.dumps({'manifest':request['manifest'],'prefix':prefix}).encode());assert len(output)<=65536;result.update(json.loads(output));assert result['passed']and fence()==original;result.update(writerFence=original,podUID=pod['metadata']['uid'])
except Exception as e:result.update(passed=False,errorType=type(e).__name__,failedStateRetained=True,subPath=prefix)
finally:
 result['createdResources']=[{'kind':kind,'name':n,'uid':uid}for kind,n,uid in created]
 if result['passed']:
  for kind,n,uid in reversed(created):
   try:
    current=get(kind,n);assert current['metadata']['uid']==uid
    options={'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':uid},'propagationPolicy':'Foreground'};resource='pods'if kind=='Pod'else'networkpolicies';group='/api/v1'if kind=='Pod'else'/apis/networking.k8s.io/v1';call(['delete','--raw',group+'/namespaces/plex/'+resource+'/'+n,'-f','-'],json.dumps(options).encode());call(['wait',kind+'/'+n,'--for=delete','--timeout=45s']);result['temporaryResources'].append({'kind':kind,'name':n,'uid':uid,'deleted':True})
   except Exception as e:result.update(passed=False,cleanupErrorType=type(e).__name__);break
 print(json.dumps(result))
'''


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--state-receipt', type=Path, required=True)
    p.add_argument('--receipt', type=Path, required=True)
    a = p.parse_args()
    assert a.apply and os.getuid() == 1000 and ROOT.is_mount()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.umask(0o077)
    assert a.receipt.parent == OUT and not a.receipt.exists()
    cold = json.loads(a.state_receipt.read_text())
    assert cold['application'] == 'xteve' and cold['generation'] == 'upstream-xteve-20261026'
    assert cold['status'] == 'completed' and cold['cold_archive_verified'] and cold['temporary_pod_deleted']
    cipher = Path(cold['archive_path'])
    assert cipher.is_relative_to(OUT) and cipher.resolve() == cipher and sha(cipher) == cold['archive_sha256']
    location = Path(__file__).resolve().parents[2] / 'k8s-rewrite/ansible-playbook/roles/metube_state_backup/files/metube_state_backup.py'
    spec = importlib.util.spec_from_file_location('archive_primitives', location)
    shared = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared)
    assert shared.file_hash(shared.AGE) == shared.AGE_SHA256
    child = subprocess.Popen([str(shared.AGE), '-d', '-i', str(shared.IDENTITY), str(cipher)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        manifest = shared.verify_archive(child.stdout)
        assert not any(child.stdout.read(1024**2)) and child.wait(timeout=30) == 0
        assert hashlib.sha256(shared.canonical(manifest)).hexdigest() == cold['manifest_sha256']
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=10)
    request = {'manifest': manifest, 'helperImage': HELPER, 'copyCode': COPY}
    proc = subprocess.run(shared.SSH + [shlex.join(['python3', '-B', '-c', NODE])], input=json.dumps(request).encode(), capture_output=True, timeout=360)
    try:
        result = json.loads(proc.stdout)
    except Exception:
        result = {'passed': False, 'rawDetailsSuppressed': True, 'exitCode': proc.returncode}
    result.update(UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(), sourceSHA256=sha(Path(__file__)), coldReceiptSHA256=sha(a.state_receipt), coldArchiveSHA256=cold['archive_sha256'])
    with a.receipt.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps(result))
    return int(proc.returncode != 0 or not result['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
