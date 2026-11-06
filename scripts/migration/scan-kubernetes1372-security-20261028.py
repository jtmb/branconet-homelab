#!/usr/bin/env python3
"""Four official Kubernetes 1.37.2 digests; bounded new profile derived from preserved scanner controls."""
import ast,datetime,hashlib,json,os,subprocess,sys,urllib.request
from pathlib import Path
ROOT=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT=ROOT/'platform-upstream-review-20261027/autonomous-hardening-20261028/kubernetes1372-full-scan'
NAMES=['kube-apiserver','kube-controller-manager','kube-scheduler','kube-proxy']
PEAK=6710886400
GEN='kubernetes1372-current-r5'
def digest(p):return hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def save(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')
def replace(s,a,b,count=1):
 assert s.count(a)==count,(a,s.count(a),count)
 return s.replace(a,b)
def capacity():
 out=subprocess.check_output(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-Command',"Get-PSDrive C,F | Select-Object Name,Free | ConvertTo-Json -Compress"],text=True)
 win={x['Name']:x['Free'] for x in json.loads(out)};free=os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize
 assert win['C']>=15*1024**3 and win['F']>=15*1024**3+PEAK and free>=15*1024**3+PEAK
 return {'windowsFreeBytes':win,'nativeFreeBytes':free,'peakBytes':PEAK,'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat()}

def resolve():
 headers={'Accept':'application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json'}
 def get(url,expected=None):
  with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=45) as r:
   b=r.read(4*1024**2+1);advertised=r.headers.get('Docker-Content-Digest')
  assert len(b)<=4*1024**2
  d='sha256:'+hashlib.sha256(b).hexdigest();assert expected is None or d==expected;assert not advertised or advertised==d
  return json.loads(b),d
 rows=[]
 for name in NAMES:
  base='https://registry.k8s.io/v2/'+name
  index,root=get(base+'/manifests/v1.37.2')
  candidates=[x for x in index['manifests'] if x.get('platform',{}).get('os')=='linux' and x.get('platform',{}).get('architecture')=='amd64'];assert len(candidates)==1
  manifest,amd64=get(base+'/manifests/'+candidates[0]['digest'],candidates[0]['digest'])
  config,configdigest=get(base+'/blobs/'+manifest['config']['digest'],manifest['config']['digest'])
  assert config['architecture']=='amd64' and config['os']=='linux' and len(manifest['layers'])==len(config['rootfs']['diff_ids'])
  assert sum(x['size'] for x in manifest['layers'])<512*1024**2
  rows.append({'name':name,'tag':'v1.37.2','reference':'registry.k8s.io/'+name+'@'+root,'rootDigest':root,'amd64Digest':amd64,'configDigest':configdigest,'index':index,'manifest':manifest,'config':config})
 return {'registry':'registry.k8s.io','images':rows}

def prepare():
 cap=capacity();assert not OUT.exists();OUT.mkdir(mode=0o700)
 save(OUT/'ownership.json',{'owner':'vendor_security_review','root':str(ROOT),'leaf':str(OUT),'physicalVolume':'F-backed WSL Ubuntu ext4.vhdx','capacity':cap,'peakComponents':{'vulnerabilityDB':2147483648,'javaDB':2147483648,'analysisScratch':2147483648,'metadataReportsReserve':268435456},'protected':'All pre-existing roots, frozen inputs/results, credentials, sources and other agent outputs. No retired target reused.','regeneration':'python3 -B scripts/migration/scan-kubernetes1372-security-20261028.py prepare; launch vulnerability; launch java; launch scan','generated':['ownership.json','profiles and hashes','new database/cache paths','four candidate results/receipts','bounded unit logs'],'cleanup':'After complete verified scan, retire exact inactive generated DB/cache directories with process/mount checks and preserve hashes/recipes/reports.'})
 metadata=resolve();save(OUT/'oci-metadata.json',metadata)
 inventory={'inventoryUTC':cap['UTC'],'unresolved':[],'images':[{'reference':x['reference'],'owners':[{'purpose':'official Kubernetes 1.37.2 qualification only; no deployment'}]} for x in metadata['images']]}
 save(OUT/'fleet-r5-candidates.json',inventory);candidate_hash=digest(OUT/'fleet-r5-candidates.json')
 base=Path(__file__).resolve().parent;scanner=(base/'scan-maintained-apps.py').read_text();refresh=(base/'refresh-public-vulnerability-db.py').read_text()
 original={'scan-maintained-apps.py':hashlib.sha256(scanner.encode()).hexdigest(),'refresh-public-vulnerability-db.py':hashlib.sha256(refresh.encode()).hexdigest()}
 for sub in ['cache','docker-config','kubernetes1372-runtime','kubernetes1372-runtime/home','kubernetes1372-runtime/tmp','kubernetes1372-runtime/cache']:(OUT/sub).mkdir(mode=0o700)
 (OUT/'empty-config.yaml').write_text('{}\n');(OUT/'results.tpl').write_text('{{ toJson . }}\n');(OUT/'no-ignore').write_text('')
 old="OUT = ROOT / 'security-review-20261026'";new='OUT = Path('+repr(str(OUT))+')'
 refresh=replace(refresh,old,new)
 refresh=replace(refresh,"branconet-public-db-r5-20261028.service","branconet-kubernetes1372-vulnerability-20261028.service")
 refresh=replace(refresh,"branconet-public-java-db-r3-20261028.service","branconet-kubernetes1372-java-20261028.service")
 scanner=replace(scanner,old,new)
 # Only finite inventory/profile selection changes; all scanner/resource/feed assertions remain.
 start="need(len(sys.argv) == 2 and sys.argv[1] in [";a=scanner.index(start);b=scanner.index(", 'finite_scan_generation')",a)
 scanner=scanner[:a]+"need(len(sys.argv) == 2 and sys.argv[1] in ['kubernetes1372-current-r5']"+scanner[b:]
 scanner=scanner.replace("'fleet-current-r5'","'kubernetes1372-current-r5'")
 scanner=replace(scanner,"runtime = OUT / 'fleet-r5-runtime' if fleet else OUT","runtime = OUT / 'kubernetes1372-runtime' if fleet else OUT")
 scanner=replace(scanner,"8ffa19129baa4edeb7ad8978b101f571d78409e56fc19e1d477e6563fadd6db9",candidate_hash)
 scanner=replace(scanner,"(2 if vendor else 66)","(2 if vendor else 4)")
 scanner=replace(scanner,"(2 if vendor else 64)","(2 if vendor else 4)")
 # Strengthen explicit no-suppression configuration and input pinning.
 marker="pins = {TOOL: identity(TOOL)}\n    hashes = {TOOL: TOOL_SHA}"
 extra=marker+"\n    need((OUT / 'empty-config.yaml').read_text() == '{}\\n' and (OUT / 'no-ignore').read_bytes() == b'' and (OUT / 'results.tpl').read_text() == '{{ toJson . }}\\n', 'explicit_no_suppression_config')\n    for name in ['empty-config.yaml', 'no-ignore', 'results.tpl']:\n        p = OUT / name\n        pins[p] = identity(p)\n        hashes[p] = sha(p)"
 scanner=replace(scanner,marker,extra)
 # Retain source authority and ensure every original named need() gate survives.
 def gates(s):
  return {n.args[1].value for n in ast.walk(ast.parse(s)) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='need' and len(n.args)>1 and isinstance(n.args[1],ast.Constant)}
 assert gates((base/'scan-maintained-apps.py').read_text())<=gates(scanner)
 assert gates((base/'refresh-public-vulnerability-db.py').read_text())<=gates(refresh)
 for name,text in [('scan-profile.py',scanner),('refresh-profile.py',refresh)]:
  ast.parse(text);(OUT/name).write_text(text)
 (OUT/'kubernetes1372-runtime/cache/db').symlink_to(OUT/'cache/db-r5',target_is_directory=True)
 (OUT/'kubernetes1372-runtime/cache/java-db').symlink_to(OUT/'cache/java-db-r3',target_is_directory=True)
 save(OUT/'profile-proof.json',{'sourceAuthority':original,'profiles':{n:digest(OUT/n) for n in ['scan-profile.py','refresh-profile.py']},'originalNamedAssertionsPreserved':True,'newInventorySHA256':candidate_hash,'targets':[x['reference'] for x in inventory['images']],'changes':['New output directory and isolated unit names','Finite four-image inventory/hash/count','New runtime cache links','Additional empty config/template/ignore content and hash assertions'],'scanGeneration':GEN})
 print(json.dumps({'prepared':str(OUT),'capacity':cap}))
def launch(stage):
 assert stage in ['vulnerability','java','scan'];cap=capacity();proof=json.loads((OUT/'profile-proof.json').read_text())
 name='scan-profile.py' if stage=='scan' else 'refresh-profile.py';assert digest(OUT/name)==proof['profiles'][name]
 unit='branconet-apps-review-'+GEN+'-20261026.service' if stage=='scan' else 'branconet-kubernetes1372-'+stage+'-20261028.service'
 log=OUT/(stage+'-unit.log');assert not log.exists() and not (OUT/(stage+'-launch.json')).exists()
 props=['MemoryMax=1073741824','MemorySwapMax=0','TasksMax=128','CPUQuota=200%','Nice=10','RuntimeMaxSec=1200','TimeoutStopSec=30','KillMode=control-group','LimitFSIZE=2147483648','PrivateUsers=yes','PrivateDevices=yes','PrivateNetwork=no','NoNewPrivileges=yes','ProtectSystem=strict','ProtectHome=tmpfs','BindReadOnlyPaths='+str(ROOT),'BindPaths='+str(OUT),'ReadWritePaths='+str(OUT),'InaccessiblePaths=-/root -/mnt/c/Users -/run/docker.sock -/var/run/docker.sock -/run/containerd -/run/containerd-k8s /tmp /var/tmp','StandardOutput=append:'+str(log),'StandardError=append:'+str(log)]
 env=['PATH=/usr/bin:/bin','LANG=C','LC_ALL=C','HOME='+str(OUT/'kubernetes1372-runtime/home')]+[k+'='+str(OUT/'kubernetes1372-runtime/tmp') for k in ['TMPDIR','TMP','TEMP']]
 args=[GEN] if stage=='scan' else [str(OUT.stat().st_dev),'vulnerability' if stage=='vulnerability' else 'java-identification','r5' if stage=='vulnerability' else 'r3']
 command=['systemd-run','--user','--unit='+unit,'--service-type=exec']+['--property='+x for x in props]+['--','/usr/bin/env','-i']+env+['/usr/bin/python3','-I','-B',str(OUT/name)]+args
 p=subprocess.run(command,capture_output=True,text=True);save(OUT/(stage+'-launch.json'),{'command':command,'capacity':cap,'sourceSHA256':digest(OUT/name),'exitCode':p.returncode,'stderr':p.stderr});print(p.stderr);assert p.returncode==0
if __name__=='__main__':
 if sys.argv[1]=='prepare':prepare()
 elif sys.argv[1]=='launch':launch(sys.argv[2])
 else:raise ValueError('finite_action')
