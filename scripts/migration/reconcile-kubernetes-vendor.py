"""Terminal-only cleanup of four authority-listed vendor files and recognized TUF cache."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess

BASE='/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025'
REL='platform-upstream-review-20261027/autonomous-hardening-20261028'
UUID='3c792469-ea0e-4a2c-98e8-1185b141607b'
AUTH='bb96c82be216747db666b2ef9d10a927688df7e7119b6f3f2775605b6d5e9859'
GUARD='3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87'
COSIGN='424e2c97d0b45fd7a6b608a87f090f35633f4c23ece5f092d48bba11aaf4bbfa'
NODES={'masternode':'192.168.0.4','workernode2':'192.168.0.5','workernode1':'192.168.0.6'}
SSH=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile=/home/brajam/.ssh/known_hosts','-i','/home/brajam/.ssh/id_ed25519','-p','2002']

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
 return h.hexdigest()

def save(path,value):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as stream:
  json.dump(value,stream,indent=2);stream.flush();os.fsync(stream.fileno())
 if os.name!='nt':os.chown(path,1000,1000)

def identity(path):
 s=path.lstat()
 assert not path.is_symlink() and not path.is_mount()
 if stat.S_ISREG(s.st_mode):assert s.st_nlink==1
 assert stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)
 assert s.st_uid in (0,1000) and not os.listxattr(path)
 return {key:getattr(s,'st_'+key) for key in ('dev','ino','mode','uid','gid','size','mtime_ns','ctime_ns','blocks')}

def terminal(h,root,relative,digest):
 rel=Path(relative);assert not rel.is_absolute() and '..' not in rel.parts
 path=h/rel;assert path.is_file() and not path.is_symlink() and sha(path)==digest
 result=json.loads(path.read_text());settings=result['settings']
 assert result['exitCode']==0 and result.get('finishedUTC') and settings['kubernetes_security_patch_apply'] is True
 def translated(value):
  assert value.startswith(BASE+'/'+REL+'/') and '..' not in Path(value[len(BASE)+1:]).parts
  return root/value[len(BASE)+1:]
 authority=translated(settings['kubernetes_security_patch_manifest'])
 assert sha(authority)==settings['kubernetes_security_patch_manifest_sha256']
 data=json.loads(authority.read_text())
 recovery=translated(settings['kubernetes_security_patch_receipt_dir'])
 completed=[json.loads(p.read_text()) for p in recovery.glob('*.completed.json')]
 assert len(completed)==3 and {x['node'] for x in completed}==set(NODES)
 assert all(x['completed'] is True and x['nativeLastConsumerCompleted'] is True and x['authoritySHA256']==settings['kubernetes_security_patch_manifest_sha256'] for x in completed)
 return data,{'path':str(path),'sha256':digest,'authoritySHA256':settings['kubernetes_security_patch_manifest_sha256']}

def live(authority,repo):
 # Reuse the native role's exact buildinfo and stable metadata readers only.
 helper=repo/'k8s-rewrite/ansible-playbook/roles/kubernetes_security_patch/files/native_binaries.py'
 code=helper.read_text()+"\nprint(json.dumps({'host':platform.node(),'binaries':{n:{'metadata':metadata(Path('/usr/local/bin')/n),'go':go_version(Path('/usr/local/bin')/n)} for n in NAMES},'versions':{'kubeadm':json.loads(run(['/usr/local/bin/kubeadm','version','-o','json']))['clientVersion']['gitVersion'],'kubelet':run(['/usr/local/bin/kubelet','--version']),'kubectl':json.loads(run(['/usr/local/bin/kubectl','version','--client','-o','json']))['clientVersion']['gitVersion']}}))\n"
 command="exec(compile("+repr(code)+",'<native-terminal-readonly>','exec'),{'__name__':'native_terminal_readonly'})"
 observed={}
 for node,ip in NODES.items():
  result=subprocess.run(SSH+['james@'+ip,shlex.join(['python3','-B','-c',command])],capture_output=True,timeout=60)
  assert result.returncode==0 and len(result.stdout)<128*1024,'Read-only native terminal qualification failed'
  value=json.loads(result.stdout);assert value['host']==node
  assert value['versions']=={'kubeadm':'v1.37.2','kubelet':'Kubernetes v1.37.2','kubectl':'v1.37.2'}
  for name,item in value['binaries'].items():
   expected=authority['binaries'][name];actual=item['metadata'];original=expected['originalByNode'][node]
   assert item['go']=='go1.26.10' and actual['sha256']==expected['sha256'] and actual['bytes']==expected['bytes']
   assert all(actual[k]==original[k] for k in ('path','uid','gid','mode','mtimeNs','xattrsSHA256'))
  observed[node]=value
 result=subprocess.run(SSH+['james@192.168.0.4','kubectl get nodes -o json'],capture_output=True,timeout=45);assert result.returncode==0
 nodes=json.loads(result.stdout)['items'];assert {n['metadata']['name']:n['metadata']['uid'] for n in nodes}==authority['nodeUIDs']
 assert all(n['status']['nodeInfo']['kubeletVersion']=='v1.37.2' and n['status']['nodeInfo']['containerRuntimeVersion']=='containerd://2.4.2' and any(c['type']=='Ready' and c['status']=='True' for c in n['status']['conditions']) for n in nodes)
 return {'capturedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'nativeHelperSHA256':sha(helper),'nodes':observed,'originalNodeUIDs':authority['nodeUIDs'],'liveKubeletsReady':True}

def cache_paths(cache):
 # Unknown content is retained as an exception, never reclassified by filename.
 dirs={'','data','tmp','cache','home','config','tuf','tuf/tuf-repo-cdn.sigstore.dev','tuf/tuf-repo-cdn.sigstore.dev/targets'}
 files={'tuf/tuf-repo-cdn.sigstore.dev.json','tuf/tuf-repo-cdn.sigstore.dev/root.json','tuf/tuf-repo-cdn.sigstore.dev/timestamp.json','tuf/tuf-repo-cdn.sigstore.dev/snapshot.json','tuf/tuf-repo-cdn.sigstore.dev/targets.json','tuf/tuf-repo-cdn.sigstore.dev/targets/trusted_root.json'}
 paths=[cache,*cache.rglob('*')]
 assert {str(p.relative_to(cache)) if p!=cache else '' for p in paths if p.is_dir()}==dirs,'Unrecognized trust-cache directory; retain entire cache'
 assert {str(p.relative_to(cache)) for p in paths if p.is_file()}==files,'Unrecognized trust-cache file or unique evidence; retain entire cache'
 assert all(not p.is_symlink() and (p.is_file() or p.is_dir()) for p in paths)
 prefix=cache/'tuf/tuf-repo-cdn.sigstore.dev'
 for name in ('root','timestamp','snapshot','targets'):
  p=prefix/(name+'.json');assert p.stat().st_size<=128*1024
  value=json.loads(p.read_text());assert set(value)=={'signed','signatures'} and value['signed']['_type']==name and value['signatures']
 target=prefix/'targets/trusted_root.json';bound=json.loads((prefix/'targets.json').read_text())['signed']['targets']['trusted_root.json']
 assert sha(target)==bound['hashes']['sha256'] and target.stat().st_size==bound['length']
 trust=json.loads(target.read_text());assert set(trust)=={'mediaType','tlogs','certificateAuthorities','ctlogs','timestampAuthorities'}
 marker=json.loads((cache/'tuf/tuf-repo-cdn.sigstore.dev.json').read_text());assert set(marker)=={'lastTimestamp'}
 return paths

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('mode',choices=['inventory','windows','apply'],nargs='?',default='inventory')
 parser.add_argument('--success',required=True,help='Relative H terminal native runner result')
 parser.add_argument('--success-sha256',required=True);args=parser.parse_args()
 root=Path(r'\\?\UNC\wsl.localhost\Ubuntu'+BASE.replace('/','\\')) if os.name=='nt' else Path(BASE)
 h=root/REL;out=h/'kubernetes1372-vendor-cleanup';vendor=h/'kubernetes1372-binaries';planpath=out/'plan.json'
 os.umask(0o077)
 authority,success=terminal(h,root,args.success,args.success_sha256)
 original=vendor/'authority.json';assert sha(original)==AUTH
 manifest=json.loads(original.read_text())
 if out.is_dir():
  assert not any(out.glob('*failure.json')),'Prior safety failure protects its exact targets; no replay or alternate path'
  assert not (out/'apply-intent.json').exists(),'Existing apply intent is not replayable; retain recorded outcome'
 if args.mode=='windows':
  assert os.name=='nt'
  plan=json.loads(planpath.read_text());assert plan['sourceSHA256']==sha(Path(__file__)) and plan['successSHA256']==args.success_sha256
  import ctypes
  from ctypes import wintypes
  api=ctypes.WinDLL('kernel32',use_last_error=True)
  api.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE];api.CreateFileW.restype=wintypes.HANDLE;api.CloseHandle.argtypes=[wintypes.HANDLE]
  handles=[]
  try:
   for row in plan['targets']:
    handle=api.CreateFileW(str(root/row['relative']),0x80000000,0,None,3,0x02000000 if row['directory'] else 0,None)
    if handle in (None,ctypes.c_void_p(-1).value):
     save(out/'windows-failure.json',{'retainedExactTarget':row['relative'],'error':ctypes.get_last_error(),'retryProhibited':True});raise ValueError('Exclusive handle denied; exact target protected')
    handles.append(handle)
   assert all(sha(h/rel)==value for rel,value in plan['protected'].items())
  finally:
   for handle in handles:api.CloseHandle(handle)
  save(out/'windows.json',{'planSHA256':sha(planpath),'exclusiveHandlesClosed':len(handles),'protectedUnchanged':True});return
 assert os.geteuid()==0 and root.is_mount() and h.resolve()==h
 assert subprocess.check_output(['findmnt','-n','-o','UUID','-T',str(root)],text=True).strip()==UUID
 repo=Path(__file__).resolve().parents[2]
 runtime=live(authority,repo) # Mandatory before inventory AND apply, never a frozen success replay.
 if args.mode=='inventory':
  out.mkdir(mode=0o700);os.chown(out,1000,1000)
  save(out/'ownership.json',{'owner':'kubernetes1372-security-patch','root':str(out),'physicalVolumeUUID':UUID,'sourceSHA256':sha(Path(__file__)),'protected':'All raw original backups, signatures, certificates, checksums, reports, receipts, source and failed witnesses','lastConsumer':'Successful all-three-node native apply and fresh live native version/Go/hash verification','regeneration':'Exact retained official binary/tool URLs/checksums/signatures; recognized Sigstore TUF metadata rebuilt online by the same verified cosign command'})
 else:
  assert out.is_dir() and out.resolve()==out
 tool=manifest['signatureTool'];assert tool['sha256']==COSIGN and tool['version']=='v3.1.4'
 checks=Path(tool['checksums']['path']);assert sha(checks)==tool['checksums']['sha256']
 assert any(line.split()==[COSIGN,'cosign-linux-amd64'] for line in checks.read_text().splitlines())
 selected=[];recipes=[];exceptions=[]
 for name in ('kubeadm','kubelet','kubectl'):
  entry=manifest['binaries'][name];target=Path(entry['blob']['path'])
  assert target==vendor/'binaries'/name/name and entry['url']=='https://dl.k8s.io/release/v1.37.2/bin/linux/amd64/'+name
  assert sha(target)==entry['sha256'] and target.stat().st_size==entry['bytes']
  retained={}
  for kind in ('checksum','signature','certificate','signatureVerification','scan'):
   item=entry[kind];path=Path(item['path']);assert vendor in path.parents and path.resolve()==path and sha(path)==item['sha256'];retained[kind]=item
  assert Path(entry['checksum']['path']).read_text().strip()==entry['sha256']
  assert authority['binaries'][name]['sha256']==entry['sha256']
  selected.append(target);recipes.append({'path':str(target),'url':entry['url'],'sha256':entry['sha256'],'retainedVerification':retained})
 target=Path(tool['path']);assert target==vendor/'tools/cosign' and sha(target)==COSIGN
 selected.append(target);recipes.append({'path':str(target),'url':'https://github.com/sigstore/cosign/releases/download/v3.1.4/cosign-linux-amd64','sha256':COSIGN,'checksums':tool['checksums']})
 cache=Path(tool['cacheDirectory']);assert cache==vendor/'signature-cache'
 try:
  cached=cache_paths(cache);selected.extend(cached)
  recipes.append({'path':str(cache),'publicMetadataBase':'https://tuf-repo-cdn.sigstore.dev','regeneration':'Verify a freshly checksum-bound official blob using pinned cosign, retained detached signature/certificate, exact krel-staging@k8s-releng-prod.iam.gserviceaccount.com identity and https://accounts.google.com issuer; HOME/XDG/TUF/TMP all bound to this cache. No bypass flags. Online TUF updates are derivative cache, not original scan evidence.'})
 except (AssertionError,OSError,ValueError,KeyError) as error:
  exceptions.append({'path':str(cache),'reason':str(error),'retainedEntireCache':True})
 assert all(p.resolve()==p and vendor in p.parents and p.stat().st_dev==root.stat().st_dev for p in selected)
 guard=root/'node-cleanup-20261027/master-generated-cleanup/reference-full-properties.py';assert sha(guard)==GUARD
 lib={'__name__':'unchanged_vendor_reference_guard'};exec(compile(guard.read_bytes(),str(guard),'exec'),lib)
 lib.update(BASE=root,ATTEMPTS=(str(vendor.relative_to(root)),))
 try:references=lib['idle']()
 except Exception as error:
  save(out/'linux-reference-failure.json',{'retainedExactTargets':[str(p) for p in selected],'reason':type(error).__name__+':'+str(error),'retryProhibited':True});raise
 rows=sorted([{'relative':str(p.relative_to(root)),'directory':p.is_dir(),'identity':identity(p),'sha256':None if p.is_dir() else sha(p)} for p in selected],key=lambda x:x['relative'])
 if args.mode=='inventory':
  protected={str(p.relative_to(h)):sha(p) for p in h.rglob('*') if p.is_file() and p not in selected and out not in p.parents}
  save(planpath,{'owner':'kubernetes1372-security-patch','physicalVolumeUUID':UUID,'sourceSHA256':sha(Path(__file__)),'vendorAuthoritySHA256':AUTH,'successSHA256':args.success_sha256,'terminal':success,'runtime':runtime,'references':references,'targets':rows,'protected':protected,'regeneration':recipes,'retainedExceptions':exceptions,'originalRollbackConsumer':'Preserve raw original installed binaries until next accepted security patch/recovery generation','logicalBytes':sum(r['identity']['size'] for r in rows if not r['directory']),'allocatedBytes':sum(r['identity']['blocks']*512 for r in rows)})
  print(json.dumps({'plan':str(planpath),'sha256':sha(planpath),'targets':len(rows),'retainedExceptions':exceptions}));return
 plan=json.loads(planpath.read_text());win=json.loads((out/'windows.json').read_text())
 assert plan['sourceSHA256']==sha(Path(__file__)) and plan['successSHA256']==args.success_sha256 and rows==plan['targets'] and exceptions==plan['retainedExceptions']
 assert win=={'planSHA256':sha(planpath),'exclusiveHandlesClosed':len(rows),'protectedUnchanged':True}
 assert all(sha(h/rel)==value for rel,value in plan['protected'].items())
 save(out/'apply-intent.json',{'planSHA256':sha(planpath),'freshLive':runtime,'references':references,'targets':rows})
 removed=[]
 try:
  for row in sorted(rows,key=lambda x:(x['directory'],-len(Path(x['relative']).parts))):
   path=root/row['relative'];current=identity(path)
   if row['directory']:
    assert all(current[k]==row['identity'][k] for k in ('dev','ino','mode','uid','gid')) and not any(path.iterdir())
    path.rmdir()
   else:
    assert current==row['identity'] and sha(path)==row['sha256'];path.unlink()
   removed.append({'path':str(path),'allocatedBytes':current['blocks']*512,'logicalBytes':0 if row['directory'] else current['size']})
  assert all(sha(h/rel)==value for rel,value in plan['protected'].items())
 except Exception as error:
  save(out/'apply-failure.json',{'removed':removed,'retainedExactTarget':str(path),'reason':type(error).__name__+':'+str(error),'retryProhibited':True});raise
 save(out/'receipt.json',{'status':'completed','planSHA256':sha(planpath),'successSHA256':args.success_sha256,'removed':removed,'removedAllocatedLinuxBytes':sum(x['allocatedBytes'] for x in removed),'protectedUnchanged':True,'retainedExceptions':exceptions,'WindowsRecoveryClaimed':False})
 print(json.dumps({'receipt':str(out/'receipt.json'),'sha256':sha(out/'receipt.json')}))

if __name__=='__main__':main()
