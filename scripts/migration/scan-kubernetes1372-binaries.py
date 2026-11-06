#!/usr/bin/env python3
"""Three official Kubernetes 1.37.2 bare binaries; bounded new profile derived from preserved scanner controls."""
import ast,datetime,hashlib,json,os,subprocess,sys,urllib.request
from pathlib import Path
ROOT=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT=ROOT/'platform-upstream-review-20261027/autonomous-hardening-20261028/kubernetes1372-binaries'
NAMES=['kubeadm','kubelet','kubectl']
PEAK=7516192768
GEN='kubernetes1372-native-r5'
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
 evidence=json.loads((OUT/'verified-binaries.json').read_bytes());assert set(evidence['binaries'])==set(NAMES)
 rows=[]
 for name in NAMES:
  row=evidence['binaries'][name];blob=Path(row['blob']['path']);assert blob.resolve()==blob and blob.is_relative_to(OUT/'binaries') and digest(blob)==row['sha256']
  signature=json.loads(Path(row['signatureVerification']['path']).read_bytes());assert signature['exitCode']==0 and not signature['bypassFlagsUsed'] and signature['subjectSHA256']==row['sha256']
  rows.append({'name':name,'reference':'dl.k8s.io/release/v1.37.2/bin/linux/amd64/'+name+'@sha256:'+row['sha256'],'binary':row})
 return {'images':rows,'verifiedBinariesSHA256':digest(OUT/'verified-binaries.json')}

def prepare():
 cap=capacity();assert OUT.is_dir() and not (OUT/'scan-ownership.json').exists()
 save(OUT/'scan-ownership.json',{'owner':'vendor_security_review','root':str(ROOT),'leaf':str(OUT),'physicalVolume':'F-backed WSL Ubuntu ext4.vhdx','capacity':cap,'peakComponents':{'vulnerabilityDB':2147483648,'javaDB':2147483648,'analysisScratch':2147483648,'metadataReportsReserve':268435456},'protected':'All pre-existing roots, frozen inputs/results, credentials, sources and other agent outputs. No retired target reused.','regeneration':'python3 -B scripts/migration/scan-kubernetes1372-security-20261028.py prepare; launch vulnerability; launch java; launch scan','generated':['ownership.json','profiles and hashes','new database/cache paths','three native binary results/receipts','bounded unit logs'],'cleanup':'After complete verified scan, retire exact inactive generated DB/cache directories with process/mount checks and preserve hashes/recipes/reports.'})
 metadata=resolve();save(OUT/'native-metadata.json',metadata)
 inventory={'inventoryUTC':cap['UTC'],'unresolved':[],'images':[{'reference':x['reference'],'owners':[{'purpose':'official Kubernetes 1.37.2 qualification only; no deployment'}]} for x in metadata['images']]}
 save(OUT/'fleet-r5-candidates.json',inventory);candidate_hash=digest(OUT/'fleet-r5-candidates.json')
 base=Path(__file__).resolve().parent;scanner=(base/'scan-maintained-apps.py').read_text();refresh=(base/'refresh-public-vulnerability-db.py').read_text()
 original={'scan-maintained-apps.py':hashlib.sha256(scanner.encode()).hexdigest(),'refresh-public-vulnerability-db.py':hashlib.sha256(refresh.encode()).hexdigest()}
 for sub in ['cache','docker-config','native-runtime','native-runtime/home','native-runtime/tmp','native-runtime/cache']:(OUT/sub).mkdir(mode=0o700)
 (OUT/'empty-config.yaml').write_text('{}\n');(OUT/'results.tpl').write_text('{{ toJson . }}\n');(OUT/'no-ignore').write_text('')
 old="OUT = ROOT / 'security-review-20261026'";new='OUT = Path('+repr(str(OUT))+')'
 refresh=replace(refresh,old,new)
 refresh=replace(refresh,"branconet-public-db-r5-20261028.service","branconet-kubernetes1372-native-vulnerability-20261028.service")
 refresh=replace(refresh,"branconet-public-java-db-r3-20261028.service","branconet-kubernetes1372-native-java-20261028.service")
 scanner=replace(scanner,old,new)
 # Only finite inventory/profile selection changes; all scanner/resource/feed assertions remain.
 start="need(len(sys.argv) == 2 and sys.argv[1] in [";a=scanner.index(start);b=scanner.index(", 'finite_scan_generation')",a)
 scanner=scanner[:a]+"need(len(sys.argv) == 2 and sys.argv[1] in ['kubernetes1372-native-r5']"+scanner[b:]
 scanner=scanner.replace("'fleet-current-r5'","'kubernetes1372-native-r5'")
 scanner=replace(scanner,"runtime = OUT / 'fleet-r5-runtime' if fleet else OUT","runtime = OUT / 'native-runtime' if fleet else OUT")
 scanner=replace(scanner,"8ffa19129baa4edeb7ad8978b101f571d78409e56fc19e1d477e6563fadd6db9",candidate_hash)
 scanner=replace(scanner,"(2 if vendor else 66)","(2 if vendor else 3)")
 scanner=replace(scanner,"(2 if vendor else 64)","(2 if vendor else 3)")
 # Strengthen explicit no-suppression configuration and input pinning.
 marker="pins = {TOOL: identity(TOOL)}\n    hashes = {TOOL: TOOL_SHA}"
 extra=marker+"\n    need((OUT / 'empty-config.yaml').read_text() == '{}\\n' and (OUT / 'no-ignore').read_bytes() == b'' and (OUT / 'results.tpl').read_text() == '{{ toJson . }}\\n', 'explicit_no_suppression_config')\n    for name in ['empty-config.yaml', 'no-ignore', 'results.tpl']:\n        p = OUT / name\n        pins[p] = identity(p)\n        hashes[p] = sha(p)"
 scanner=replace(scanner,marker,extra)
 # Bind actual bare binary bytes and publisher evidence before and after every fs scan.
 binary_rows=metadata['images']
 binding_text="\n    binary_paths = "+repr({r['reference']:str(Path(r['binary']['blob']['path']).parent) for r in binary_rows})+"\n"
 for row in binary_rows:
  for key in ['blob','checksum','signature','certificate','signatureVerification']:
   f=row['binary'][key];binding_text+="    p = Path("+repr(f['path'])+"); need(sha(p) == "+repr(f['sha256'])+", 'native_binary_publisher_input_digest'); pins[p] = identity(p); hashes[p] = "+repr(f['sha256'])+"\n"
 binding_text+="    need(sha(OUT / 'verified-binaries.json') == "+repr(metadata['verifiedBinariesSHA256'])+", 'native_publisher_authority'); pins[OUT / 'verified-binaries.json'] = identity(OUT / 'verified-binaries.json'); hashes[OUT / 'verified-binaries.json'] = "+repr(metadata['verifiedBinariesSHA256'])+"\n"
 scanner=replace(scanner,'    receipts = []',binding_text+'    receipts = []')
 scanner=replace(scanner,"[str(TOOL), 'image', '--image-src', 'remote', '--platform', 'linux/amd64',","[str(TOOL), 'filesystem',")
 scanner=replace(scanner,"str(output), image['reference']]","str(output), binary_paths[image['reference']]]")
 # Retain source authority and ensure every original named need() gate survives.
 def gates(s):
  return {n.args[1].value for n in ast.walk(ast.parse(s)) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='need' and len(n.args)>1 and isinstance(n.args[1],ast.Constant)}
 assert gates((base/'scan-maintained-apps.py').read_text())<=gates(scanner)
 assert gates((base/'refresh-public-vulnerability-db.py').read_text())<=gates(refresh)
 for name,text in [('scan-profile.py',scanner),('refresh-profile.py',refresh)]:
  ast.parse(text);(OUT/name).write_text(text)
 (OUT/'native-runtime/cache/db').symlink_to(OUT/'cache/db-r5',target_is_directory=True)
 (OUT/'native-runtime/cache/java-db').symlink_to(OUT/'cache/java-db-r3',target_is_directory=True)
 save(OUT/'profile-proof.json',{'sourceAuthority':original,'profiles':{n:digest(OUT/n) for n in ['scan-profile.py','refresh-profile.py']},'originalNamedAssertionsPreserved':True,'newInventorySHA256':candidate_hash,'targets':[x['reference'] for x in inventory['images']],'changes':['New output directory and isolated unit names','Finite three-binary filesystem inventory/hash/count','New runtime cache links','Additional empty config/template/ignore content and hash assertions'],'scanGeneration':GEN})
 print(json.dumps({'prepared':str(OUT),'capacity':cap}))
def launch(stage):
 assert stage in ['vulnerability','java','scan'];cap=capacity();proof=json.loads((OUT/'profile-proof.json').read_text())
 name='scan-profile.py' if stage=='scan' else 'refresh-profile.py';assert digest(OUT/name)==proof['profiles'][name]
 unit='branconet-apps-review-'+GEN+'-20261026.service' if stage=='scan' else 'branconet-kubernetes1372-native-'+stage+'-20261028.service'
 log=OUT/(stage+'-unit.log');assert not log.exists() and not (OUT/(stage+'-launch.json')).exists()
 props=['MemoryMax=1073741824','MemorySwapMax=0','TasksMax=128','CPUQuota=200%','Nice=10','RuntimeMaxSec=1200','TimeoutStopSec=30','KillMode=control-group','LimitFSIZE=2147483648','PrivateUsers=yes','PrivateDevices=yes','PrivateNetwork=no','NoNewPrivileges=yes','ProtectSystem=strict','ProtectHome=tmpfs','BindReadOnlyPaths='+str(ROOT),'BindPaths='+str(OUT),'ReadWritePaths='+str(OUT),'InaccessiblePaths=-/root -/mnt/c/Users -/run/docker.sock -/var/run/docker.sock -/run/containerd -/run/containerd-k8s /tmp /var/tmp','StandardOutput=append:'+str(log),'StandardError=append:'+str(log)]
 env=['PATH=/usr/bin:/bin','LANG=C','LC_ALL=C','HOME='+str(OUT/'native-runtime/home')]+[k+'='+str(OUT/'native-runtime/tmp') for k in ['TMPDIR','TMP','TEMP']]
 args=[GEN] if stage=='scan' else [str(OUT.stat().st_dev),'vulnerability' if stage=='vulnerability' else 'java-identification','r5' if stage=='vulnerability' else 'r3']
 command=['systemd-run','--user','--unit='+unit,'--service-type=exec']+['--property='+x for x in props]+['--','/usr/bin/env','-i']+env+['/usr/bin/python3','-I','-B',str(OUT/name)]+args
 p=subprocess.run(command,capture_output=True,text=True);save(OUT/(stage+'-launch.json'),{'command':command,'capacity':cap,'sourceSHA256':digest(OUT/name),'exitCode':p.returncode,'stderr':p.stderr});print(p.stderr);assert p.returncode==0
if __name__=='__main__':
 if sys.argv[1]=='prepare':prepare()
 elif sys.argv[1]=='launch':launch(sys.argv[2])
 else:raise ValueError('finite_action')
