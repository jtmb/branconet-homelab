#!/usr/bin/env python3
"""Bounded controller-only official native binary download/signature qualification."""
import datetime,hashlib,json,os,re,subprocess,sys,urllib.request
from pathlib import Path
ROOT=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT=ROOT/'platform-upstream-review-20261027/autonomous-hardening-20261028/kubernetes1372-binaries'
PEAK=7*1024**3
COSIGN_SHA='424e2c97d0b45fd7a6b608a87f090f35633f4c23ece5f092d48bba11aaf4bbfa'
CHECKSUMS_SHA='e70e59b328d52949b3a9ae3e0d04721ea8f380c4e91c28197aa91df02afbf4c0'
NAMES=['kubeadm','kubelet','kubectl']
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(name,d):
 with (OUT/name).open('x') as f:json.dump(d,f,indent=2);f.write('\n')
def capacity():
 win=json.loads(subprocess.check_output(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-Command','Get-PSDrive C,F | Select-Object Name,Free | ConvertTo-Json -Compress'],text=True));free=os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize
 assert all(x['Free']>=15*1024**3+(PEAK if x['Name']=='F' else 0) for x in win) and free>=15*1024**3+PEAK
 return {'Windows':win,'nativeFreeBytes':free,'peakBytes':PEAK}
def download(url,path,maximum,expected=None):
 count=0;h=hashlib.sha256()
 with urllib.request.urlopen(url,timeout=45) as response,path.open('xb') as f:
  for b in iter(lambda:response.read(1024**2),b''):
   count+=len(b);assert count<=maximum;h.update(b);f.write(b)
  f.flush();os.fsync(f.fileno())
 assert count>0 and (expected is None or h.hexdigest()==expected) and sha(path)==h.hexdigest()
 return {'path':str(path),'sha256':h.hexdigest(),'bytes':count,'url':url}
def work():
 os.umask(0o077);assert not Path('/home/brajam/.ssh').exists() and not os.access('/mnt/c/Users',os.R_OK|os.X_OK)
 cg=Path('/proc/self/cgroup').read_text().strip().removeprefix('0::');assert cg.endswith('/branconet-kubernetes1372-binary-verify.service');group=Path('/sys/fs/cgroup')/cg.lstrip('/')
 assert (group/'memory.max').read_text().strip()==str(1024**3) and (group/'memory.swap.max').read_text().strip()=='0' and (group/'pids.max').read_text().strip()=='128'
 for d in ['tools','binaries','signature-cache','signature-cache/home','signature-cache/tmp','signature-cache/cache','signature-cache/config','signature-cache/data','signature-cache/tuf']:(OUT/d).mkdir(mode=0o700)
 checks=download('https://github.com/sigstore/cosign/releases/download/v3.1.4/cosign_checksums.txt',OUT/'tools/cosign_checksums.txt',65536,CHECKSUMS_SHA)
 lines=(OUT/'tools/cosign_checksums.txt').read_text().splitlines();assert any(line.split()==[COSIGN_SHA,'cosign-linux-amd64'] for line in lines)
 tool=download('https://github.com/sigstore/cosign/releases/download/v3.1.4/cosign-linux-amd64',OUT/'tools/cosign',200*1024**2,COSIGN_SHA);(OUT/'tools/cosign').chmod(0o500)
 env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C','HOME':str(OUT/'signature-cache/home'),'XDG_CACHE_HOME':str(OUT/'signature-cache/cache'),'XDG_CONFIG_HOME':str(OUT/'signature-cache/config'),'XDG_DATA_HOME':str(OUT/'signature-cache/data'),'TUF_ROOT':str(OUT/'signature-cache/tuf'),'TMPDIR':str(OUT/'signature-cache/tmp'),'TMP':str(OUT/'signature-cache/tmp'),'TEMP':str(OUT/'signature-cache/tmp'),'GOMAXPROCS':'2','GOMEMLIMIT':'512MiB'}
 artifacts={}
 for name in NAMES:
  folder=OUT/'binaries'/name;folder.mkdir(mode=0o700);url='https://dl.k8s.io/release/v1.37.2/bin/linux/amd64/'+name
  checksum=download(url+'.sha256',folder/(name+'.sha256'),1024);expected=(folder/(name+'.sha256')).read_text().strip();assert re.fullmatch('[0-9a-f]{64}',expected)
  blob=download(url,folder/name,200*1024**2,expected);signature=download(url+'.sig',folder/(name+'.sig'),65536);certificate=download(url+'.cert',folder/(name+'.cert'),65536)
  data=(folder/name).open('rb').read(20);assert data[:6]==b'\x7fELF\x02\x01' and data[18:20]==b'\x3e\x00'
  cmd=[str(OUT/'tools/cosign'),'verify-blob',str(folder/name),'--signature',str(folder/(name+'.sig')),'--certificate',str(folder/(name+'.cert')),'--certificate-identity','krel-staging@k8s-releng-prod.iam.gserviceaccount.com','--certificate-oidc-issuer','https://accounts.google.com']
  result=subprocess.run(cmd,env=env,cwd=OUT,capture_output=True,timeout=180)
  assert len(result.stdout)+len(result.stderr)<=1024**2
  receipt={'subjectSHA256':expected,'exitCode':result.returncode,'completedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'certificateIdentity':'krel-staging@k8s-releng-prod.iam.gserviceaccount.com','certificateIssuer':'https://accounts.google.com','bypassFlagsUsed':False,'command':cmd,'cosignSHA256':COSIGN_SHA,'stdout':result.stdout.decode(errors='replace'),'stderr':result.stderr.decode(errors='replace'),'sourceSHA256':sha(Path(__file__))}
  save(name+'-signature.json',receipt);assert result.returncode==0,'publisher_signature_verification_failed_'+name
  assert sha(folder/name)==expected;artifacts[name]={'url':url,'sha256':expected,'bytes':blob['bytes'],'blob':blob,'checksum':checksum,'signature':signature,'certificate':certificate,'signatureVerification':{'path':str(OUT/(name+'-signature.json')),'sha256':sha(OUT/(name+'-signature.json'))}}
 save('verified-binaries.json',{'version':'v1.37.2','platform':'linux/amd64','signatureTool':{'path':str(OUT/'tools/cosign'),'sha256':COSIGN_SHA,'version':'v3.1.4','checksums':checks,'cacheDirectory':str(OUT/'signature-cache')},'binaries':artifacts})
def launch():
 cap=capacity();save('download-admission.json',cap)
 props=['MemoryMax=1073741824','MemorySwapMax=0','TasksMax=128','CPUQuota=200%','Nice=10','RuntimeMaxSec=1200','TimeoutStopSec=30','KillMode=control-group','LimitFSIZE=2147483648','PrivateUsers=yes','PrivateDevices=yes','PrivateNetwork=no','NoNewPrivileges=yes','ProtectSystem=strict','ProtectHome=tmpfs','BindReadOnlyPaths='+str(ROOT),'BindPaths='+str(OUT),'ReadWritePaths='+str(OUT),'InaccessiblePaths=-/root -/mnt/c/Users -/run/docker.sock -/var/run/docker.sock -/run/containerd -/run/containerd-k8s /tmp /var/tmp','StandardOutput=append:'+str(OUT/'download-unit.log'),'StandardError=append:'+str(OUT/'download-unit.log')]
 source=OUT/'qualify-source.py';source.write_bytes(Path(__file__).read_bytes());cmd=['systemd-run','--user','--unit=branconet-kubernetes1372-binary-verify.service','--service-type=exec']+['--property='+x for x in props]+['--','/usr/bin/env','-i','PATH=/usr/bin:/bin','LANG=C','HOME='+str(OUT),'/usr/bin/python3','-I','-B',str(source),'work'];p=subprocess.run(cmd,capture_output=True,text=True);save('download-launch.json',{'command':cmd,'sourceSHA256':sha(source),'exitCode':p.returncode,'stderr':p.stderr});print(p.stderr);assert p.returncode==0
if __name__=='__main__':
 if sys.argv[1]=='launch':launch()
 elif sys.argv[1]=='work':work()
 else:raise ValueError('finite_action')
