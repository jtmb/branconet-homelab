"""Single-host generated APT metadata inventory/cleanup, streamed without installation."""
import datetime,errno,fcntl,hashlib,json,os,pathlib,re,select,stat,subprocess,sys,time
P=pathlib.Path
BINS=('/var/cache/apt/pkgcache.bin','/var/cache/apt/srcpkgcache.bin')
PATTERN=r'(ca\.archive\.ubuntu\.com|security\.ubuntu\.com)_ubuntu_dists_(jammy(?:-updates|-security|-backports)?)_(main|universe|restricted|multiverse)_binary-(amd64|i386)_Packages(?:\.lz4)?'

KERNEL_PACKAGES={n:'5.15.0.202.174' for n in ('linux-generic','linux-image-generic','linux-headers-generic')}
KERNEL_PACKAGES.update({n:'5.15.0-202.212' for n in ('linux-image-5.15.0-202-generic','linux-modules-5.15.0-202-generic',
 'linux-modules-extra-5.15.0-202-generic','linux-headers-5.15.0-202','linux-headers-5.15.0-202-generic',
 'linux-modules-nvidia-390-generic','linux-modules-nvidia-390-5.15.0-202-generic',
 'linux-objects-nvidia-390-5.15.0-202-generic','linux-signatures-nvidia-5.15.0-202-generic')})
INCLUDE_ARCHIVES=False
INDEX_CACHE={}
FORMAT_REPAIR=False
PUBLIC_STAGE="admission"
PUBLIC_REASON="admission_not_completed"
ALLOW_IDLE_PACKAGEKIT=False
PACKAGEKIT_BINDING=None

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def run(args):
 r=subprocess.run(args,capture_output=True,timeout=45);assert r.returncode==0,'Read-only native metadata command failed'
 return r.stdout

def identity(path):
 p=P(path);s=p.lstat()
 assert p.resolve()==p and stat.S_ISREG(s.st_mode) and s.st_uid==0 and s.st_nlink==1
 assert not os.listxattr(p),'Unknown cache xattrs retained'
 return {'path':str(p),'bytes':s.st_size,'allocatedBytes':s.st_blocks*512,'sha256':sha(p),'device':s.st_dev,'inode':s.st_ino,'mode':s.st_mode,'uid':s.st_uid,'gid':s.st_gid,'mtimeNs':s.st_mtime_ns,'ctimeNs':s.st_ctime_ns}

def protected():
 paths=[P('/var/lib/dpkg/status'),P('/var/lib/apt/extended_states')]
 paths += [p for p in P('/etc/apt').rglob('*') if p.is_file()]
 paths += [p for p in P('/usr/share/keyrings').glob('*.gpg') if p.is_file()]
 if INCLUDE_ARCHIVES:
  for version in ('198','202'):
   paths += [p for p in P('/boot').glob('*5.15.0-'+version+'*') if p.is_file()]
   modules=P('/lib/modules/5.15.0-'+version+'-generic');paths += [modules/'modules.dep',modules/'modules.alias']
  paths += [P('/proc/driver/nvidia/version')]
 paths += [p for p in P('/var/lib/apt/lists').iterdir() if p.is_file() and p.name.endswith(('InRelease','Release','Release.gpg'))]
 return {'files':{str(p):sha(p) for p in sorted(set(paths)) if p.exists()},'holdsSHA256':hashlib.sha256(run(['apt-mark','-o','Dir::Cache::pkgcache=','-o','Dir::Cache::srcpkgcache=','showhold'])).hexdigest(),
         'aptConfigSHA256':hashlib.sha256(run(['apt-config','dump'])).hexdigest(),'rootFSUUID':run(['findmnt','-n','-o','UUID','/']).decode().strip()}

def exited_process_without_references(proc):
 def state():
  raw=(proc/'stat').read_text();fields=raw[raw.rfind(')')+2:].split()
  assert fields[0] in ('Z','X') and int(fields[20])==0 and int(fields[21])==0,'Process still has live memory'
  return {'pid':int(proc.name),'state':fields[0],'startTicks':fields[19]}
 before=state();assert list((proc/'fd').iterdir())==[],'Exited process still has descriptors'
 assert (proc/'maps').read_text()=='','Exited process still has mappings'
 for name in ('exe','cwd','root','ns/mnt'):
  try:os.readlink(proc/name)
  except FileNotFoundError:pass
  else:raise AssertionError('Exited process still has executable/filesystem namespace')
 after=state();assert before==after,'Exited PID identity changed'
 return {**after,'noDescriptorsExeMemoryOrMountNamespace':True}

def index_mapping(path):
 p=P(path)
 assert p.parent==P('/var/lib/apt/lists')
 base=re.fullmatch(r'(ca\.archive\.ubuntu\.com|security\.ubuntu\.com)_ubuntu_dists_(jammy(?:-updates|-security|-backports)?)_(main|universe|restricted|multiverse)_(.+)',p.name)
 assert base,'Unknown metadata origin retained'
 host,suite,component,tail=base.groups()
 package=re.fullmatch(r'binary-(amd64|i386)_Packages(?:\.lz4)?',tail)
 if package:return host,suite,component,'binary-'+package[1]+'/Packages',True,False
 assert FORMAT_REPAIR,'Additional formats require bound successor inventory'
 rules=[(r'i18n_(Translation-en)(\.gz|\.xz|\.bz2|\.lz4)?','i18n/'),
        (r'dep11_(Components-(?:amd64|i386)\.yml)(\.gz|\.xz|\.lz4)?','dep11/'),
        (r'dep11_(icons-(?:48x48|64x64|64x64@2|128x128)\.tar)(\.gz|\.xz|\.lz4)?','dep11/'),
        (r'cnf_(Commands-(?:amd64|i386))(\.gz|\.xz|\.lz4)?','cnf/')]
 for expression,prefix in rules:
  m=re.fullmatch(expression,tail)
  if m:
   extension=m[2] or '';raw=extension not in ('','.lz4')
   return host,suite,component,prefix+m[1]+(extension if raw else ''),False,raw
 raise AssertionError('Unknown metadata target retained')

def metadata_paths():
 result=[]
 for p in P('/var/lib/apt/lists').iterdir():
  if not FORMAT_REPAIR:
   if p.name.endswith('_Packages.lz4'):result.append(str(p))
   continue
  try:index_mapping(str(p))
  except AssertionError:continue
  result.append(str(p))
 return sorted(result)

def unused(path):
 # Root, full process views; denied references fail closed. Private argv stays RAM-only.
 for proc in P('/proc').glob('[0-9]*'):
  try:
   for entry in [proc/'cwd',proc/'root',proc/'exe',*list((proc/'fd').iterdir())]:
    try:value=os.readlink(entry)
    except FileNotFoundError:continue
    assert value!=path and not value.startswith(path+'/'),'Active native reference'
   for name in ('maps','mountinfo'):
    try:text=(proc/name).read_text()
    except OSError as error:
     if FORMAT_REPAIR and name=='mountinfo' and error.errno==errno.EINVAL:
      exited_process_without_references(proc);continue
     raise
    assert path not in text,'Active map/mount reference'
  except (FileNotFoundError,ProcessLookupError):continue

def signed_index(path):
 p=P(path)
 if path in INDEX_CACHE:
  cached=INDEX_CACHE[path];assert identity(path)==cached['compressedIdentity'];return cached
 host,suite,component,relative_target,is_packages,raw_bytes=index_mapping(path)
 if not FORMAT_REPAIR:assert p.name.endswith('_Packages.lz4')
 compressed_before=identity(path)
 release=p.parent/(host+'_ubuntu_dists_'+suite+'_InRelease')
 assert release.resolve()==release and release.is_file() and release.stat().st_size<4*1024**2
 run(['gpgv','--keyring','/usr/share/keyrings/ubuntu-archive-keyring.gpg',str(release)])
 target=component+'/'+relative_target;lines=release.read_text().splitlines();inside=False;rows=[]
 for line in lines:
  if line=='SHA256:':inside=True;continue
  if inside and not line.startswith(' '):inside=False
  if inside:
   parts=line.split()
   if len(parts)==3 and parts[2]==target:rows.append(parts)
 assert len(rows)==1 and re.fullmatch('[a-f0-9]{64}',rows[0][0])
 expected=rows[0];limit=int(expected[1]);assert 0<limit<=512*1024**2
 child=subprocess.Popen((['/bin/cat','--',str(p)] if raw_bytes else ['/usr/lib/apt/apt-helper','cat-file',str(p)]),stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
 digest=hashlib.sha256();count=0;deadline=time.monotonic()+45
 carry=b'';stanzas=[]
 def consume(block):
  fields=dict(line.split(': ',1) for line in block.decode('utf-8').splitlines() if ': ' in line and not line.startswith(' '))
  if fields.get('Package') in KERNEL_PACKAGES and fields.get('Version')==KERNEL_PACKAGES[fields['Package']]:
   keys=('Package','Version','Architecture','Filename','SHA256','Size');assert all(k in fields for k in keys)
   stanzas.append({k:fields[k] for k in keys})
 try:
  while True:
   remaining=deadline-time.monotonic();assert remaining>0 and select.select([child.stdout],[],[],remaining)[0],'Index decompression timed out'
   chunk=os.read(child.stdout.fileno(),1048576)
   if not chunk:break
   count+=len(chunk);assert count<=limit;digest.update(chunk)
   if INCLUDE_ARCHIVES and is_packages:
    carry+=chunk;parts=carry.split(b'\n\n');carry=parts.pop();assert len(carry)<=4*1024**2
    for block in parts:consume(block)
  if INCLUDE_ARCHIVES and is_packages and carry:consume(carry)
  assert child.wait(timeout=2)==0 and count==limit and digest.hexdigest()==expected[0],'Signed Packages content differs'
 finally:
  if child.poll() is None:child.kill();child.wait()
 proof={'signedInRelease':str(release),'signedInReleaseSHA256':sha(release),'keyringSHA256':sha('/usr/share/keyrings/ubuntu-archive-keyring.gpg'),
         'target':target,'isPackages':is_packages,'hashesRawSignedBytes':raw_bytes,'uncompressedBytes':count,'uncompressedSHA256':digest.hexdigest(),'uri':'http://'+host+'/ubuntu/dists/'+suite+'/'+target,
         'regeneration':'apt-get update using preserved source configuration and signed InRelease; old exact hash is retained as authority evidence'}
 assert identity(path)==compressed_before,'Signed index changed during decompression'
 if INCLUDE_ARCHIVES:proof.update(packageStanzas=stanzas,indexPath=path,compressedIdentity=compressed_before)
 if INCLUDE_ARCHIVES:INDEX_CACHE[path]=proof
 return proof

def archive_signature(path,row):
 assert INCLUDE_ARCHIVES and P(path).parent==P('/var/cache/apt/archives')
 fields=dict(line.split(': ',1) for line in run(['dpkg-deb','-f',path,'Package','Version','Architecture']).decode().splitlines())
 assert fields.get('Package') in KERNEL_PACKAGES and fields['Version']==KERNEL_PACKAGES[fields['Package']]
 assert fields['Architecture'] in ('amd64','all')
 assert P(path).name==fields['Package']+'_'+fields['Version']+'_'+fields['Architecture']+'.deb'
 installed=run(['dpkg-query','-W','-f=${Package}\t${Version}\t${Architecture}\t${db:Status-Abbrev}',fields['Package']]).decode().split('\t')
 assert installed==[fields['Package'],fields['Version'],fields['Architecture'],'ii '],'Archive not exactly installed'
 matches=[]
 for index in [P(x) for x in metadata_paths()]:
  match=re.fullmatch(PATTERN,index.name)
  if not match or match[2] not in ('jammy-updates','jammy-security') or match[3] not in ('main','restricted') or match[4]!='amd64':continue
  try:proof=signed_index(str(index))
  except Exception:continue
  for stanza in proof['packageStanzas']:
   if all(stanza[k]==v for k,v in fields.items()) and stanza['SHA256']==row['sha256'] and int(stanza['Size'])==row['bytes']:
    filename=stanza['Filename'];assert filename.startswith('pool/'+match[3]+'/') and '..' not in P(filename).parts and P(filename).name==P(path).name
    matches.append({'signature':proof,'package':stanza,'downloadURI':'http://'+match[1]+'/ubuntu/'+filename})
 assert matches,'No matching gpgv-authorized Ubuntu Packages stanza; retain archive'
 return matches[0]


def qualify(path):
 row=identity(path);unused(path)
 if path in BINS:
  row['kind']='resolver-cache';row['regeneration']='apt-cache gencaches using retained/reacquired signed lists and unchanged dpkg status'
 elif P(path).parent==P('/var/cache/apt/archives'):
  proof=archive_signature(path,row);row.update(kind='installed-kernel202-archive',**proof,regeneration='Download only the bound Ubuntu package URI and verify retained SHA256/size; no package installation')
 else:
  proof=signed_index(path);row.update(kind='signed-derived-Packages-index' if proof['isPackages'] else 'signed-derived-Ubuntu-metadata',signature=proof)
 assert identity(path)=={k:v for k,v in row.items() if k not in ('kind','regeneration','signature','package','downloadURI')},'Cache changed during qualification'
 return row

def admission_need(value,reason):
 global PUBLIC_REASON
 if not value:PUBLIC_REASON=reason;raise AssertionError(reason)

def other_lock_holders(legacy):
 # Native POSIX locks held by this exact cleanup process are expected; no other
 # process or blocked contender may be mistaken for our own lock ownership.
 result=[]
 for line in legacy['package_lock_holders']():
  parts=line.split()
  if len(parts)<6 or parts[1]=='->' or parts[4]!=str(os.getpid()):result.append(line)
 return result

def idle_packagekit(proc,legacy):
 global PACKAGEKIT_BINDING
 def process():
  raw=(proc/'stat').read_text();tail=raw[raw.rfind(')')+2:].split()
  return {'state':tail[0],'ppid':int(tail[1]),'start':tail[19],
          'exe':os.readlink(proc/'exe'),'argv':(proc/'cmdline').read_bytes(),
          'cgroup':(proc/'cgroup').read_text().splitlines()}
 before=process();pid=int(proc.name)
 admission_need(before['state']=='S' and before['ppid']==1 and before['exe']=='/usr/libexec/packagekitd'
  and before['argv']==b'/usr/libexec/packagekitd\0' and before['cgroup']==['0::/system.slice/packagekit.service'],'packagekit_process_identity')
 path=P('/usr/libexec/packagekitd');st=path.stat()
 admission_need(path.resolve()==path and st.st_uid==0 and not st.st_mode&0o022
  and sha(path)=='02e76201f1a450a536c474e2d19d09109fa9c47298fb0d77245c153d08d7f360','packagekit_binary_identity')
 admission_need(run(['dpkg-query','-S',str(path)]).decode().strip()=='packagekit: /usr/libexec/packagekitd','packagekit_package_owner')
 admission_need(run(['dpkg-query','-W','-f=${Version}\t${db:Status-Abbrev}','packagekit']).decode()=='1.2.5-2ubuntu3.1\tii ','packagekit_package_version')
 def unit():
  return dict(line.split('=',1) for line in run(['systemctl','show','packagekit.service','-p','MainPID','-p','ActiveState','-p','SubState','-p','ControlGroup']).decode().splitlines())
 u=unit();admission_need(u=={'MainPID':str(pid),'ActiveState':'active','SubState':'running','ControlGroup':'/system.slice/packagekit.service'},'packagekit_unit_identity')
 # Read only; D-Bus transaction list must be exactly empty. No cancel/stop call.
 admission_need(run(['busctl','call','org.freedesktop.PackageKit','/org/freedesktop/PackageKit','org.freedesktop.PackageKit','GetTransactionList']).decode().strip()=='ao 0','packagekit_transaction_active')
 admission_need(not other_lock_holders(legacy),'packagekit_other_lock_holder')
 admission_need(process()==before and unit()==u,'packagekit_pid_or_unit_changed')
 binding={'pid':pid,'process':before,'unit':u}
 admission_need(PACKAGEKIT_BINDING is None or PACKAGEKIT_BINDING==binding,'packagekit_changed_since_admission')
 PACKAGEKIT_BINDING=binding
 return pid

def package_admission(legacy,held=False):
 if not ALLOW_IDLE_PACKAGEKIT and not held:
  global PUBLIC_REASON
  PUBLIC_REASON='concurrent_package_manager_or_lock'
  legacy['no_apt_process']()
  return
 admitted=[]
 for p in P('/proc').glob('[0-9]*/comm'):
  try:name=p.read_text().strip()
  except FileNotFoundError:continue
  if name=='packagekitd':
   admission_need(ALLOW_IDLE_PACKAGEKIT,'concurrent_package_manager');admitted.append(idle_packagekit(p.parent,legacy))
  elif name=='unattended-upgr':
   # Keep the exact original shutdown waiter classifier. Its lock observation
   # excludes only our own locks while the original four locks are held.
   original=legacy['package_lock_holders']
   try:
    legacy['package_lock_holders']=lambda: other_lock_holders({'package_lock_holders':original})
    legacy['observed_shutdown_waiter'](p.parent)
   finally:legacy['package_lock_holders']=original
  else:admission_need(name not in {'apt','apt-get','dpkg'},'concurrent_package_manager')
 admission_need(len(admitted)<=1,'multiple_packagekit_processes')
 state=run(['systemctl','show','packagekit.service','--property=ActiveState','--value']).decode().strip()
 admission_need((state in ('inactive','failed') and not admitted) or (state=='active' and len(admitted)==1),'packagekit_unbound_active_unit')
 admission_need(not other_lock_holders(legacy),'other_package_lock_holder')

def main():
 global INCLUDE_ARCHIVES,FORMAT_REPAIR,ALLOW_IDLE_PACKAGEKIT,PUBLIC_STAGE,PUBLIC_REASON
 assert os.geteuid()==0
 data=json.load(sys.stdin);assert data['host'] in ('masternode','workernode2') and run(['hostname']).decode().strip()==data['host']
 ALLOW_IDLE_PACKAGEKIT=data.get('allowObservedIdlePackagekit',False);assert isinstance(ALLOW_IDLE_PACKAGEKIT,bool)
 FORMAT_REPAIR=data.get('inventoryFormatRepair',False);assert isinstance(FORMAT_REPAIR,bool)
 INCLUDE_ARCHIVES=data.get('includeInstalledKernel202Archives',False)
 assert isinstance(INCLUDE_ARCHIVES,bool) and (not INCLUDE_ARCHIVES or data['host']=='masternode')
 if INCLUDE_ARCHIVES:
  assert run(['uname','-r']).decode().strip()=='5.15.0-202-generic'
  assert '390.157' in P('/proc/driver/nvidia/version').read_text()
  for version in ('198','202'):
   status=run(['dpkg-query','-W','-f=${db:Status-Abbrev}','linux-image-5.15.0-'+version+'-generic']).decode();assert status=='ii '
 legacy={ '__name__':'apt_metadata_legacy_guard' };exec(compile(data['legacySource'],'<existing-package-guard>','exec'),legacy)
 package_admission(legacy)
 for unit in (('apt-daily.service','apt-daily-upgrade.service') if ALLOW_IDLE_PACKAGEKIT else ('apt-daily.service','apt-daily-upgrade.service','packagekit.service')):
  state=run(['systemctl','show',unit,'--property=ActiveState','--value']).decode().strip();assert state in ('inactive','failed'),'Active APT unit'
 locks=[]
 try:
  # Hold the same native POSIX locks throughout qualification and unlink.
  for path in legacy['PACKAGE_LOCKS']:
   fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW);locks.append(fd);fcntl.lockf(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  package_admission(legacy,held=True)
  PUBLIC_STAGE="protected-state";PUBLIC_REASON="protected_state_check_failed"
  before=protected()
  assert not run(['dpkg','--audit']).strip()
  PUBLIC_STAGE='inventory' if data['mode']=='inventory' else 'target-qualification';PUBLIC_REASON='metadata_qualification_failed'
  if data['mode']=='inventory':
   format_proof=None
   if FORMAT_REPAIR:
    prior=data['priorFormatInventory'];assert prior['host']==data['host']
    assert not list(P('/var/lib/apt/lists').glob('*_Packages.lz4')),'Old lz4-only enumeration was not empty'
    plain=[x for x in metadata_paths() if x.endswith('_Packages')];assert plain,'No native plain Packages files to establish format correction'
    for row in prior['retained']:assert identity(row['path'])==row['identity'],'Original retained target changed'
    format_proof={'plainPackages':[identity(x) for x in plain],'oldLz4EnumerationEmpty':True,'previousRetainedIdentitiesUnchanged':True}
    if data['host']=='workernode2':
     assert P('/proc/796801').exists(),'Exact original exited-process witness must be freshly observed'
     proof=exited_process_without_references(P('/proc/796801'));assert proof['startTicks']=='1362263';format_proof['originalExitedPID']=proof
   paths=list(BINS)+metadata_paths()
   if INCLUDE_ARCHIVES:
    paths += [str(p) for p in P('/var/cache/apt/archives').glob('*.deb') if any(p.name.startswith(n+'_'+v+'_') for n,v in KERNEL_PACKAGES.items())]
   qualified=[];retained=[]
   for path in sorted(paths):
    if not P(path).exists():continue
    try:qualified.append(qualify(path))
    except Exception as error:
     item={'path':path,'reason':type(error).__name__+': '+str(error)[:160],'targetProtected':True}
     try:item['identity']=identity(path)
     except Exception:pass
     retained.append(item)
   authorities={}
   for row in qualified:
    if 'signature' in row:
     release=row['signature']['signedInRelease'];content=P(release).read_text()
     assert hashlib.sha256(content.encode()).hexdigest()==row['signature']['signedInReleaseSHA256']
     authorities[release]={'sha256':row['signature']['signedInReleaseSHA256'],'signedPublicContent':content}
   assert protected()==before
   print(json.dumps({'host':data['host'],'protected':before,'qualified':qualified,'retained':retained,'signedAuthorities':authorities,'formatRepairObservation':format_proof,'packagesChanged':False}));return
  assert data['mode']=='apply' and before==data['inventory']['protected']
  row=data['target'];assert row in data['inventory']['qualified'] and not any(r['path']==row['path'] for r in data['inventory']['retained'])
  assert qualify(row['path'])==row and protected()==before
  # Resolver mmap caches do not use a separate APT lock file; native global
  # locks, process inspection and full FD/maps references above protect them.
  assert identity(row['path'])=={k:v for k,v in row.items() if k not in ('kind','regeneration','signature','package','downloadURI')}
  unused(row['path'])
  PUBLIC_STAGE='pre-unlink-admission';PUBLIC_REASON='pre_unlink_admission_failed'
  package_admission(legacy,held=True)
  PUBLIC_STAGE='unlink';PUBLIC_REASON='unlink_or_postcheck_failed'
  P(row['path']).unlink();assert not P(row['path']).exists()
  assert protected()==before
  assert not P(row['path']).exists(),'Native read recreated the cache; removal is not accepted'
  print(json.dumps({'host':data['host'],'removed':row,'protectedUnchanged':True,'packagesChanged':False,'windowsRecoveryClaimed':False}))
 finally:
  for fd in reversed(locks):os.close(fd)

if __name__=='__main__':
 try:main()
 except Exception as error:
  print(json.dumps({'passed':False,'errorType':type(error).__name__,'stage':PUBLIC_STAGE,'reason':PUBLIC_REASON,'targetRetainedOrUncertain':True}));sys.exit(1)
