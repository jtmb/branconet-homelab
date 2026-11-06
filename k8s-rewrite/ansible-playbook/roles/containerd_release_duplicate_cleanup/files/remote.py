"""Exact vendor release-copy qualification/unlink; no runtime state changes."""
import base64,errno,hashlib,json,os,pathlib,re,socket,stat,subprocess,sys,tarfile,time
P=pathlib.Path
ARCHIVE='da656542e754c699a0f438eab925e6ffdbd6346a4428e659f83dc058f04dcffe'
MEMBERS={'containerd':'4c8ea02ec7b01b1763910c82343e7b5fc39da4f356eb97645ec1baf3367a7fe2','containerd-shim-runc-v2':'0d15b33e4566dda8f3463af1f4a551076abaaf19f1880619a808312e15d2739b','containerd-stress':'95c052b06aaeb0e6baa1afea911fde5a054a29ec85856696eadaa0d80b63e5f1','ctr':'bcf0357ed9f17b8851ccde2486321c8fa2d0bcfb0ea71c267da6a1155c7f4743'}
def digest(f):
 h=hashlib.sha256()
 for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def sha(p):
 with p.open('rb') as f:return digest(f)
def command(a):return subprocess.check_output(a,timeout=60).decode().strip()
def event(x):print(json.dumps(x),flush=True)
def ident(p):
 s=p.lstat();return {k:getattr(s,'st_'+k) for k in ['dev','ino','mode','uid','gid','nlink','size','mtime_ns','ctime_ns','blocks']}
def main():
 request=json.loads(sys.stdin.readline());assert request['mode'] in ['qualify','apply']
 assert os.geteuid()==0 and socket.gethostname()==request['node']
 root=P('/opt')/'containerd-k8s'/'releases'/'v2.4.2';installed=root.parents[1]/'bin'
 assert root.resolve()==root and root.is_dir() and not root.is_mount()
 assert command(['uname','-r'])=='5.15.0-202-generic'
 raw=base64.b64decode(request['guardSource'],validate=True)
 assert hashlib.sha256(raw).hexdigest()=='3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87'
 guard={'__name__':'original_readonly_reference_guard'};exec(compile(raw,'<original-reference-guard>','exec'),guard)
 guard.update(BASE=root.parent,ATTEMPTS=(root.name,))
 def refs():
  result=guard['idle']()
  # Original guard plus ALL unit properties and process environment; no values emitted.
  names=sorted({x.split()[0] for x in command(['systemctl','list-units','--all','--plain','--no-legend','--no-pager']).splitlines() if x.strip()})
  assert names and all(re.fullmatch(r'[A-Za-z0-9_.@:\\-]+',n)for n in names)
  ids=command(['systemctl','show','--property=Id','--value','--',*names]).splitlines();assert set(filter(None,ids))==set(names)
  props=command(['systemctl','show','--all','--no-pager','--',*names]);assert str(root)not in props,'unit_property_reference'
  for proc in P('/proc').iterdir():
   if not proc.name.isdigit()or int(proc.name)==os.getpid():continue
   try:assert str(root).encode()not in (proc/'environ').read_bytes(),'process_environment_reference'
   except OSError as e:
    if e.errno not in (errno.ENOENT,errno.ESRCH):raise
  result['allUnitPropertiesSHA256']=hashlib.sha256(props.encode()).hexdigest();return result
 def protected():
  out={}
  paths=[P('/etc')/'containerd-k8s'/'config.toml',P('/var/lib/kubelet/config.yaml'),P('/var/lib/kubelet/kubeadm-flags.env')]
  for unit in ['containerd-k8s','kubelet']:
   fragment=command(['systemctl','show',unit,'--property=FragmentPath','--value']);drops=command(['systemctl','show',unit,'--property=DropInPaths','--value'])
   assert fragment.startswith('/') and not drops
   paths.append(P(fragment));out[unit]={'fragment':fragment,'execStart':command(['systemctl','show',unit,'--property=ExecStart','--value'])}
  assert str(installed/'containerd') in out['containerd-k8s']['execStart'] and str(root)not in out['containerd-k8s']['execStart']
  for n in ['containerd','containerd-shim-runc-v2','ctr']:assert sha(installed/n)==MEMBERS[n]
  paths+=sorted(p for p in installed.iterdir() if p.is_file())
  paths+=sorted(p for p in (P('/opt')/'cni'/'bin').iterdir() if p.is_file())
  for p in paths:out[str(p)]={'identity':ident(p),'sha256':sha(p),'xattrs':{n:os.getxattr(p,n).hex()for n in os.listxattr(p)}}
  return out
 before=protected();references=refs()
 expected={'containerd.tar.gz':ARCHIVE,**{'bin/'+n:v for n,v in MEMBERS.items()}}
 actual={str(p.relative_to(root))for p in root.rglob('*')if not p.is_dir()};assert actual==set(expected)
 rows=[]
 for relative,want in expected.items():
  p=root/relative;s=ident(p)
  assert p.resolve()==p and stat.S_ISREG(s['mode'])and s['nlink']==1 and s['uid']==0 and s['dev']==root.stat().st_dev
  assert time.time_ns()-max(s['mtime_ns'],s['ctime_ns'])>=72*3600*10**9
  assert sha(p)==want and not os.listxattr(p)
  rows.append({'path':str(p),'relative':relative,'identity':s,'sha256':want,'allocatedBytes':s['blocks']*512})
 with tarfile.open(root/'containerd.tar.gz','r:gz')as archive:
  files=[m for m in archive.getmembers()if m.isfile()]
  assert {m.name for m in files}=={'bin/'+n for n in MEMBERS}and len(files)==4
  assert all(m.isfile()or m.isdir()for m in archive.getmembers())
  for m in files:
   assert digest(archive.extractfile(m))==MEMBERS[m.name[4:]]
 profile={'node':request['node'],'root':str(root),'rootIdentity':ident(root),'binIdentity':ident(root/'bin'),'files':rows,'protectedSHA256':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),'archiveSHA256':ARCHIVE}
 if request['mode']=='qualify':
  event({'status':'qualified','profile':profile,'references':references,'mutationsPerformed':False});return
 assert profile==request['qualification']['profile'],'qualified_file_or_runtime_state_changed'
 event({'status':'ready','profile':profile});assert sys.stdin.readline().strip()=='ACK-EXACT-FIVE-FILES'
 removed=[];free_before=os.statvfs('/')
 for row in rows:
  refs();assert protected()==before
  p=P(row['path']);assert ident(p)==row['identity']and sha(p)==row['sha256']
  event({'intent':str(p),'allocatedBytes':row['allocatedBytes']});assert sys.stdin.readline().strip()=='ACK-UNLINK'
  p.unlink();removed.append({'path':str(p),'allocatedBytes':row['allocatedBytes']});event({'removed':str(p)})
 assert protected()==before
 directories=[]
 for p in [root/'bin',root]:
  assert p.resolve()==p and not p.is_mount()and not any(p.iterdir())
  refs();size=p.stat().st_blocks*512;event({'intent':str(p),'allocatedBytes':size});assert sys.stdin.readline().strip()=='ACK-RMDIR'
  p.rmdir();directories.append({'path':str(p),'allocatedBytes':size})
 fs=os.statvfs('/');event({'status':'completed','removed':removed,'emptyDirectoriesRemoved':directories,'removedAllocatedLinuxBytes':sum(r['allocatedBytes']for r in removed+directories),'rootFreeBefore':free_before.f_bfree*free_before.f_frsize,'rootFreeAfter':fs.f_bfree*fs.f_frsize,'WindowsRecoveryClaimed':False,'installedConfigurationAndCNIUnchanged':True})
if __name__=='__main__':main()
