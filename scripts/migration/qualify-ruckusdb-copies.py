#!/usr/bin/env python3
"""Restore a verified full cold archive into fresh isolated tmpfs MySQL copies.

No production claim is mounted. Original encrypted backups are retained. Run
prepare only once after the existing cold backup and cache preload complete.
Other actions run the separately reviewed SQL qualifier against recorded UIDs.
"""
import argparse,hashlib,importlib.util,json,os,pathlib,shlex,subprocess,time,uuid
ROOT=pathlib.Path(__file__).resolve().parents[2]
BASE=pathlib.Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
PRIVATE=BASE/'acceptance-ruckus-20261025'
SSH=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','IdentitiesOnly=yes','-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@192.168.0.4']
MASTER='/home/james/.local/share/branconet-migration/acceptance-ruckus-20261025'
HELPER=ROOT/'scripts/migration/qualify-ruckusdb.py'
RESTORE=r'''import hashlib,json,os,pathlib,stat,sys,tarfile
import traceback
def safe_error(kind,value,tb):
 print(json.dumps({'restored':False,'error_type':kind.__name__,'source_lines':[f.lineno for f in traceback.extract_tb(tb) if f.filename=='<string>']}))
sys.excepthook=safe_error
expected=sys.stdin.buffer.readline().decode().strip();side=sys.argv[1];assert side in ['old','new']
root=pathlib.Path('/copies')/side;assert root.is_dir() and not root.is_symlink() and not list(root.iterdir())
seen=set();manifest=None;dirs=[];total=0
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|')as archive:
 for m in archive:
  name=m.name.rstrip('/');assert name not in seen and not name.startswith('/') and '..'not in pathlib.PurePosixPath(name).parts
  seen.add(name);assert len(seen)<=4097
  if name=='manifest.json':
   assert len(seen)==1 and m.isfile() and m.size<=8*1024**2
   raw=archive.extractfile(m).read();assert hashlib.sha256(raw).hexdigest()==expected;manifest=json.loads(raw)
   assert manifest['schema_version']==1 and not manifest['excluded_new_paths'];continue
  assert manifest is not None and name in manifest['entries'] and name.split('/')[0]=='data-0'
  row=manifest['entries'][name];assert m.mode==row['mode'] and m.uid==row['uid'] and m.gid==row['gid']
  target=root/name;assert target.parent.resolve().is_relative_to(root.resolve())
  if row['kind']=='directory':
   assert m.isdir();target.mkdir(mode=0o700);dirs.append((target,row))
  elif row['kind']=='symlink':
   assert m.issym() and m.linkname==row['link']
   socket_link=name=='data-0/mysql.sock' and m.linkname=='/var/run/mysqld/mysqld.sock'
   assert socket_link or not pathlib.PurePosixPath(m.linkname).is_absolute()
   os.symlink(m.linkname,target);assert socket_link or target.resolve().is_relative_to(root.resolve())
   os.chown(target,row['uid'],row['gid'],follow_symlinks=False);os.utime(target,ns=(row['mtime_ns'],row['mtime_ns']),follow_symlinks=False)
  else:
   assert row['kind']=='file' and m.isfile() and m.size==row['bytes'];total+=m.size;assert total<=384*1024**2
   fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);h=hashlib.sha256();count=0
   with os.fdopen(fd,'wb')as dst:
    src=archive.extractfile(m)
    for block in iter(lambda:src.read(1024**2),b''):dst.write(block);h.update(block);count+=len(block)
    assert count==m.size and h.hexdigest()==row['sha256']
    os.fchown(dst.fileno(),row['uid'],row['gid']);os.fchmod(dst.fileno(),row['mode'])
   os.utime(target,ns=(row['mtime_ns'],row['mtime_ns']))
assert manifest is not None and seen=={'manifest.json'}|set(manifest['entries']) and total==manifest['total_file_bytes']
trailing=0
for block in iter(lambda:sys.stdin.buffer.read(65536),b''):trailing+=len(block);assert trailing<=1024**2 and not any(block)
for target,row in reversed(dirs):os.chown(target,row['uid'],row['gid']);os.chmod(target,row['mode']);os.utime(target,ns=(row['mtime_ns'],row['mtime_ns']))
print(json.dumps({'side':side,'full_manifest_sha256':expected,'entries':len(manifest['entries']),'file_bytes':total,'restored':True}))
'''

def need(ok,msg):
 if not ok:raise RuntimeError(msg)
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def remote(args,data=None,timeout=180):
 p=subprocess.run(SSH+[shlex.join(args)],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
 need(p.returncode==0,'master command failed; private stderr withheld');return p.stdout
def kube(args,data=None,timeout=180):return remote(['kubectl','--request-timeout=30s',*args],data,timeout)
def save(path,data):
 with path.open('x')as f:json.dump(data,f,sort_keys=True,indent=2);f.write('\n')
def observer(state,action,label,container=None,normal=False,baseline=None,second=None):
 key=(PRIVATE/'hmac-key.hex').read_bytes();receipt=MASTER+'/'+label+'.json'
 args=['python3','-B',MASTER+'/copy-observer-3284b56f3d7e.py',action,'--receipt',receipt]
 if action not in ['compare','observe-live']:args+=['--namespace',state['namespace'],'--pod-uid',state['pod_uid']]
 if container:args+=['--container',container]
 if normal:args+=['--normal-auth']
 if action=='start-copy':args+=['--restore-proof',MASTER+'/physical-01.json']
 if baseline:args+=['--baseline',MASTER+'/'+baseline+'.json']
 if second:args+=['--restore-proof',MASTER+'/'+second+'.json']
 result=subprocess.run(SSH+[shlex.join(args)],input=key,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=600)
 data=json.loads(remote(['cat',receipt]));save(PRIVATE/(label+'.json'),data)
 need(data['status']=='passed',label+': '+data.get('error','failed'));print(json.dumps({'label':label,'status':'passed'}),flush=True)
 return data

def main():
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['prepare','observe','start','stop','upgrade','compare']);ap.add_argument('--container',choices=['old','new']);ap.add_argument('--normal-auth',action='store_true');ap.add_argument('--label');ap.add_argument('--baseline');ap.add_argument('--second');a=ap.parse_args();os.umask(0o077)
 statefile=PRIVATE/'copy-run.json'
 if a.action=='prepare':
  need(not statefile.exists(),'existing copy run retained')
  need(sha(HELPER)=='3284b56f3d7e7f0a570d84823a3a5b3a1c8067249156450bc061af2dadda3751','reviewed SQL helper')
  backups=[p for p in (BASE/'ruckus-cold-20261025').glob('*/receipt.json') if json.loads(p.read_bytes()).get('status')=='completed'];need(len(backups)==1,'one completed cold source; failed receipts retained');cold=json.loads(backups[0].read_bytes())
  need(cold['status']=='completed' and cold['cold_archive_verified'] and cold['temporary_pod_deleted'],'cold backup complete')
  cipher=pathlib.Path(cold['archive_path']);need(sha(cipher)==cold['archive_sha256'],'cold archive hash')
  shared_path=ROOT/'k8s-rewrite/ansible-playbook/roles/metube_state_backup/files/metube_state_backup.py'
  spec=importlib.util.spec_from_file_location('archive',shared_path);shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)
  child=subprocess.Popen([str(shared.AGE),'-d','-i',str(shared.IDENTITY),str(cipher)],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
  manifest=shared.verify_archive(child.stdout);trail=child.stdout.read();need(not any(trail) and len(trail)<=1024**2 and child.wait()==0,'fully authenticated original')
  need(hashlib.sha256(shared.canonical(manifest)).hexdigest()==cold['manifest_sha256'] and manifest['total_file_bytes']<=384*1024**2,'full manifest identity and fixture bound')
  source=HELPER.read_bytes();upload="import pathlib,sys,hashlib; p=pathlib.Path("+repr(MASTER+'/copy-observer-3284b56f3d7e.py')+"); b=sys.stdin.buffer.read(); assert hashlib.sha256(b).hexdigest()=='3284b56f3d7e7f0a570d84823a3a5b3a1c8067249156450bc061af2dadda3751'; assert not p.exists(); p.write_bytes(b); p.chmod(0o400)"
  remote(['python3','-B','-c',upload],source)
  run=uuid.uuid4().hex[:12];plan=json.loads(remote(['python3','-B',MASTER+'/copy-observer-3284b56f3d7e.py','plan','--run-id',run]));state={'namespace':'ruckusdb-copy-'+run,'backup_receipt_sha256':sha(backups[0]),'archive_sha256':cold['archive_sha256'],'manifest_sha256':cold['manifest_sha256'],'owned':[]}
  for obj in plan['items']:
   actual=json.loads(kube(['create','-f','-','-o','json'],json.dumps(obj).encode()));state['owned'].append({'kind':actual['kind'],'name':actual['metadata']['name'],'uid':actual['metadata']['uid']})
   if actual['kind']=='Pod':state['pod_uid']=actual['metadata']['uid']
  save(statefile,state);kube(['-n',state['namespace'],'wait','pod/qualifier','--for=condition=Ready','--timeout=180s'],timeout=210)
  for side in ['old','new']:
   command=['kubectl','-n',state['namespace'],'exec','-i','qualifier','-c','reader','--','python3','-B','-c',RESTORE,side]
   receiver=subprocess.Popen(SSH+[shlex.join(command)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   receiver.stdin.write((cold['manifest_sha256']+'\n').encode());receiver.stdin.flush()
   dec=subprocess.Popen([str(shared.AGE),'-d','-i',str(shared.IDENTITY),str(cipher)],stdout=receiver.stdin,stderr=subprocess.DEVNULL);receiver.stdin.close()
   decrypted=dec.wait(timeout=300);out=receiver.stdout.read();err=receiver.stderr.read();exitcode=receiver.wait(timeout=30)
   if out:save(PRIVATE/('restore-'+side+'-result.json'),json.loads(out))
   need(decrypted==0 and exitcode==0,'memory-only authenticated restore refused; filtered result retained')
   proof=json.loads(out);need(proof['restored'] and proof['full_manifest_sha256']==cold['manifest_sha256'],'complete restore proof');save(PRIVATE/('restore-'+side+'.json'),proof)
  observer(state,'physical-copy','physical-01')
 else:
  state=json.loads(statefile.read_bytes());need(a.label,'new private receipt label')
  observer(state,{'observe':'observe-copy','start':'start-copy','stop':'stop-copy','upgrade':'upgrade-copy','compare':'compare'}[a.action],a.label,a.container,a.normal_auth,a.baseline,a.second)
if __name__=='__main__':main()
