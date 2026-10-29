"""Finite worker2 package cleanup program. Streamed over SSH; no node source file.
All outputs are JSON projections; configuration contents never leave the node.
"""
import base64, datetime, email.utils, fcntl, glob, hashlib, json, os, pathlib, re, shlex, stat, subprocess, sys, urllib.request
P=pathlib.Path
TARGETS={'linux-headers-5.15.0-157','linux-headers-5.15.0-157-generic','linux-image-5.15.0-157-generic','linux-modules-5.15.0-157-generic','linux-modules-extra-5.15.0-157-generic'}
VERSION='5.15.0-157.167'
def require(ok,why):
 if not ok: raise RuntimeError(why)
def run(args):
 r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env={**os.environ,'LC_ALL':'C','DEBIAN_FRONTEND':'noninteractive','NEEDRESTART_MODE':'l'})
 require(r.returncode==0,'command_failed:'+args[0]+':'+str(r.returncode))
 return r.stdout

def sha(path):
 d=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):d.update(b)
 return d.hexdigest()
def emit(phase,**data):
 print(json.dumps({'phase':phase,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),**data}),flush=True)
def inventory():
 rows={}
 for line in run(['dpkg-query','-W','-f=${binary:Package}\t${Version}\t${db:Status-Abbrev}\n']).splitlines():
  name,version,status=line.split('\t');rows[name]={'version':version,'status':status}
 return rows

def free():
 v=os.statvfs('/');return {'capacityBytes':v.f_blocks*v.f_frsize,'freeBytes':v.f_bfree*v.f_frsize,'availableBytes':v.f_bavail*v.f_frsize}
def snapshot():
 require(run(['hostname']).strip()=='workernode2','hostname')
 require(run(['findmnt','-n','-o','UUID','/']).strip()=='960bc2c7-2a7e-4bc2-b2c5-dbb6d71207f4','root_uuid')
 require(run(['uname','-r']).strip()=='5.15.0-202-generic','running_kernel')
 pkgs=inventory()
 for version in ['198','202']:
  for name in ['linux-headers-5.15.0-'+version,'linux-headers-5.15.0-'+version+'-generic','linux-image-5.15.0-'+version+'-generic','linux-modules-5.15.0-'+version+'-generic','linux-modules-extra-5.15.0-'+version+'-generic']:
   require(name in pkgs and pkgs[name]['status'].startswith('ii'),'fallback_current_package')
 holds=run(['apt-mark','showhold']).splitlines();require(not TARGETS.intersection(holds),'held_target')
 require(not run(['dpkg','--audit']).strip(),'dpkg_audit')
 files={}
 patterns=['/usr/local/bin/kubeadm','/usr/local/bin/kubelet','/usr/local/bin/kubectl','/etc/containerd*/config.toml','/etc/systemd/system/kubelet.service*','/etc/systemd/system/containerd*.service*','/etc/kubernetes/manifests/*','/var/lib/kubelet/config.yaml','/etc/default/grub','/boot/vmlinuz-5.15.0-198-generic','/boot/initrd.img-5.15.0-198-generic','/boot/vmlinuz-5.15.0-202-generic','/boot/initrd.img-5.15.0-202-generic','/lib/modules/5.15.0-198-generic/modules.dep','/lib/modules/5.15.0-202-generic/modules.dep']
 for pattern in patterns:
  for path in glob.glob(pattern):
   if P(path).is_dir():
    for child in P(path).rglob('*'):
     if child.is_file():files[str(child)]=sha(child)
   elif P(path).is_file():files[path]=sha(path)
 for version in ['198','202']:
  for prefix in ['vmlinuz','initrd.img']:require('/boot/'+prefix+'-5.15.0-'+version+'-generic' in files,'protected_boot_file_missing')
 services={}
 for unit in ['kubelet.service','containerd-k8s.service']:
  value=run(['systemctl','show',unit,'-p','LoadState','-p','ActiveState','-p','SubState','-p','MainPID','-p','ExecMainStartTimestampMonotonic'])
  require('LoadState=loaded' in value and 'ActiveState=active' in value,'runtime_service_not_active')
  services[unit]=value
 return {'packages':pkgs,'holds':holds,'files':files,'services':services,'bootID':P('/proc/sys/kernel/random/boot_id').read_text().strip(),'root':free()}
PACKAGE_LOCKS=['/var/lib/dpkg/lock-frontend','/var/lib/dpkg/lock','/var/cache/apt/archives/lock','/var/lib/apt/lists/lock']
SHUTDOWN_SCRIPT='/usr/share/unattended-upgrades/unattended-upgrade-shutdown'
SHUTDOWN_SHA='8fbf4e278c4ad457e82cc05586631b1a0550dd9d10892a70487ef74c623066e0'
def package_lock_holders():
 keys=set()
 for path in PACKAGE_LOCKS:
  st=os.stat(path);keys.add((os.major(st.st_dev),os.minor(st.st_dev),st.st_ino))
 found=[]
 for line in P('/proc/locks').read_text().splitlines():
  for token in line.split():
   match=re.fullmatch(r'([0-9a-fA-F]+):([0-9a-fA-F]+):([0-9]+)',token)
   if match and (int(match[1],16),int(match[2],16),int(match[3])) in keys:found.append(line)
 return found

def shutdown_wait_identity_ok(value):
 # Pure narrow classifier. No general sleeping-process or zombie exemption.
 return (value['comm']=='unattended-upgr' and value['state']=='S' and value['ppid']==1
  and value['argv']==['/usr/bin/python3',SHUTDOWN_SCRIPT,'--wait-for-signal']
  and value['exe']=='/usr/bin/python3.10' and value['pythonResolved']=='/usr/bin/python3.10'
  and value['scriptResolved']==SHUTDOWN_SCRIPT and value['scriptSHA256']==SHUTDOWN_SHA
  and value['packageOwner']=='unattended-upgrades: '+SHUTDOWN_SCRIPT
  and value['packageVersion']=='2.8ubuntu1' and value['packageStatus']=='ii '
  and value['unitMainPID']==value['pid'] and value['unitActive']=='active' and value['unitSub']=='running'
  and value['unitControlGroup']=='/system.slice/unattended-upgrades.service'
  and value['cgroup']==['0::/system.slice/unattended-upgrades.service']
  and value['startTicks']==value['startTicksAfter'] and value['stateAfter']=='S'
  and value['lockHolders']==[])

def observed_shutdown_waiter(proc):
 def proc_identity():
  raw=(proc/'stat').read_text();tail=raw[raw.rfind(')')+2:].split()
  return tail[0],int(tail[1]),tail[19]
 state,ppid,start=proc_identity()
 unit=dict(line.split('=',1) for line in run(['systemctl','show','unattended-upgrades.service','-p','MainPID','-p','ControlGroup','-p','ActiveState','-p','SubState']).splitlines())
 package=run(['dpkg-query','-W','-f=${Version}\t${db:Status-Abbrev}','unattended-upgrades']).split('\t')
 argv=(proc/'cmdline').read_bytes().split(b'\0');require(argv[-1]==b'','shutdown_argv_termination')
 state_after,ppid_after,start_after=proc_identity();require(ppid_after==ppid,'shutdown_process_race')
 value={'comm':(proc/'comm').read_text().strip(),'pid':int(proc.name),'state':state,'ppid':ppid,'startTicks':start,'startTicksAfter':start_after,'stateAfter':state_after,
 'argv':[a.decode('utf-8') for a in argv[:-1]],'exe':os.readlink(proc/'exe'),'pythonResolved':str(P('/usr/bin/python3').resolve()),'scriptResolved':str(P(SHUTDOWN_SCRIPT).resolve()),'scriptSHA256':sha(SHUTDOWN_SCRIPT),
 'packageOwner':run(['dpkg-query','-S',SHUTDOWN_SCRIPT]).strip(),'packageVersion':package[0],'packageStatus':package[1],
 'unitMainPID':int(unit['MainPID']),'unitActive':unit['ActiveState'],'unitSub':unit['SubState'],'unitControlGroup':unit['ControlGroup'],'cgroup':(proc/'cgroup').read_text().splitlines(),'lockHolders':package_lock_holders()}
 require(shutdown_wait_identity_ok(value),'concurrent_package_manager_shutdown_identity')
 return value

def no_apt_process():
 for p in P('/proc').glob('[0-9]*/comm'):
  try:name=p.read_text().strip()
  except FileNotFoundError:continue
  if name=='unattended-upgr':
   observed_shutdown_waiter(p.parent)
  else:require(name not in {'apt','apt-get','dpkg','packagekitd'},'concurrent_package_manager')
 for path in ['/var/lib/dpkg/lock-frontend','/var/lib/dpkg/lock','/var/cache/apt/archives/lock','/var/lib/apt/lists/lock']:
  fd=os.open(path,os.O_RDWR)
  try:fcntl.lockf(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.lockf(fd,fcntl.LOCK_UN)
  finally:os.close(fd)
def simulation():
 out=run(['apt-get','-s','remove','--no-auto-remove',*sorted(TARGETS)])
 removed=[line.split()[1] for line in out.splitlines() if line.startswith('Remv ')]
 require(len(removed)==5 and set(removed)==TARGETS,'simulation_removal_scope')
 require(not any(line.startswith(('Inst ','Conf ','Purg ')) for line in out.splitlines()),'simulation_other_actions')
 return out

def signed_stanzas(requests):
 # Exact approved main indexes only. Verify signature, complete index SHA/size,
 # then exact Package/Version/Architecture/Filename/SHA256/Size stanza.
 found={};proof=[]
 for release in sorted(glob.glob('/var/lib/apt/lists/ca.archive.ubuntu.com_ubuntu_dists_*InRelease')+glob.glob('/var/lib/apt/lists/security.ubuntu.com_ubuntu_dists_*InRelease')):
  run(['gpgv','--keyring','/usr/share/keyrings/ubuntu-archive-keyring.gpg',release]);text=P(release).read_text()
  if any(part in release for part in ['jammy-updates_','jammy-security_']):
   dates=[l[6:] for l in text.splitlines() if l.startswith('Date: ')];require(len(dates)==1,'release_date_missing')
   age=datetime.datetime.now(datetime.timezone.utc)-email.utils.parsedate_to_datetime(dates[0]);require(datetime.timedelta(0)<=age<=datetime.timedelta(hours=48),'release_stale')
  for index in glob.glob(release[:-len('InRelease')]+'main_binary-amd64_Packages*'):
   content=subprocess.check_output(['/usr/lib/apt/apt-helper','cat-file',index]);digest=hashlib.sha256(content).hexdigest()
   require(any(' '.join(l.split())==digest+' '+str(len(content))+' main/binary-amd64/Packages' for l in text.splitlines()),'signed_index_hash')
   for block in content.decode().split('\n\n'):
    fields=dict(line.split(': ',1) for line in block.splitlines() if ': ' in line and not line.startswith(' '))
    for key,wanted in requests.items():
     if all(fields.get(k)==v for k,v in wanted.items()):found[key]=fields
   proof.append({'release':release,'releaseSHA256':sha(release),'indexSHA256':digest})
 require(set(found)==set(requests),'signed_stanza_missing')
 for fields in found.values():
  url='https://archive.ubuntu.com/ubuntu/'+fields['Filename']
  with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=30) as response:
   require(response.status==200 and response.headers.get('Content-Length')==fields['Size'],'regeneration_unavailable')
 return proof

def archive_check(a,packages):
 path=P(a['path']);st=path.lstat()
 require(path.parent==P('/var/cache/apt/archives') and path.resolve()==path and stat.S_ISREG(st.st_mode) and st.st_nlink==1,'archive_path_type')
 require(st.st_size==a['bytes'] and sha(path)==a['sha256'],'archive_hash_size')
 fields=dict(line.split(': ',1) for line in run(['dpkg-deb','-f',str(path),'Package','Version','Architecture']).splitlines())
 require(fields==a['fields'] and 'nvidia' not in fields['Package'],'archive_identity')
 key=fields['Package'];qualified=key+':'+fields['Architecture']
 p=packages.get(qualified,packages.get(key))
 require(p and p['status'].startswith('ii') and p['version']==fields['Version'],'archive_installed_exact')
 # Full privileged process reference check; unreadable evidence fails closed.
 for proc in P('/proc').glob('[0-9]*'):
  try:
   for entry in [proc/'cwd',proc/'root',proc/'exe',*list((proc/'fd').iterdir())]:
    try:target=os.readlink(entry)
    except FileNotFoundError:continue
    require(target not in {str(path),str(path)+' (deleted)'},'archive_process_reference')
   require(str(path) not in (proc/'maps').read_text(),'archive_mapped_reference')
  except FileNotFoundError:continue
 mounts=P('/proc/self/mountinfo').read_text();require(str(path) not in mounts,'archive_mount_reference')
 return {'path':str(path),'sha256':a['sha256'],'bytes':st.st_size,'allocatedBytes':st.st_blocks*512,'device':st.st_dev,'inode':st.st_ino}

def main():
 require(os.geteuid()==0,'requires_root')
 request=json.loads(sys.stdin.readline());plan=request['plan'];require(plan['node']=='workernode2','plan_node')
 require(set(plan['kernelRemoval']['exactPackages'])==TARGETS,'plan_packages')
 archives=plan['completedInstalledArchives'];require(len(archives)==18 and len({a['path'] for a in archives})==18,'archive_allowlist')
 no_apt_process();before=snapshot()
 for name in TARGETS:require(before['packages'].get(name)=={'version':VERSION,'status':'ii '},'obsolete_package_changed')
 sim=simulation();requests={}
 for name,p in plan['kernelRemoval']['exactPackages'].items():
  fields=dict(l.split(': ',1) for l in p['metadata']);requests[name]={k:fields[k] for k in ['Package','Version','Filename','SHA256','Size']}
 for a in archives:
  fields=dict(l.split(': ',1) for l in a['repositoryMetadata']);requests[a['path']]={**a['fields'],**{k:fields[k] for k in ['Filename','SHA256','Size']}}
 signatures=signed_stanzas(requests)
 archive_before=[archive_check(a,before['packages']) for a in archives]
 owned=[];seen=set()
 for name in sorted(TARGETS):
  for path in run(['dpkg-query','-L',name]).splitlines():
   try:st=P(path).lstat()
   except FileNotFoundError:continue
   if stat.S_ISDIR(st.st_mode) or (st.st_dev,st.st_ino) in seen:continue
   seen.add((st.st_dev,st.st_ino));owned.append({'path':path,'allocatedBytes':st.st_blocks*512,'device':st.st_dev,'inode':st.st_ino})
 emit('preflight',before=before,simulation=sim,signedIndexes=signatures,archives=archive_before,kernelOwnedFiles=owned,kernelOwnedAllocatedBytes=sum(x['allocatedBytes'] for x in owned),nativeWriteScope=['/var/lib/dpkg','/var/log/apt','/var/log/dpkg.log','/var/cache/apt','/boot generated kernel157/grub metadata','exact dpkg-owned kernel157 files'])
 ack=sys.stdin.readline().strip()
 if ack=='OBSERVE_ONLY':emit('observed');return
 require(ack=='APPLY_EXACT_REVIEWED_PLAN','controller_intent_ack_missing')
 no_apt_process();fresh=snapshot()
 for key in ['packages','holds','files','services','bootID']:require(fresh[key]==before[key],'state_drift_after_intent_'+key)
 require(simulation()==sim,'simulation_drift')
 # APT obtains its own native locks. Its pre-invoke hook rejects any package
 # state race since the reviewed simulation, before dpkg performs a mutation.
 query=['dpkg-query','-W','-f=${binary:Package}\t${Version}\t${db:Status-Abbrev}\n']
 package_hash=hashlib.sha256(run(query).encode()).hexdigest()
 require(inventory()==before['packages'],'package_preinvoke_baseline_drift')
 hook="import hashlib,subprocess; assert hashlib.sha256(subprocess.check_output("+repr(query)+")).hexdigest()=="+repr(package_hash)+"; assert subprocess.check_output(['uname','-r']).strip()==b'5.15.0-202-generic'"
 hook_command='python3 -B -c '+shlex.quote(hook)
 # No purge/autoremove/download/upgrade. Native APT paths are declared above.
 r=subprocess.run(['apt-get','-y','--no-download','-o','DPkg::Pre-Invoke::='+hook_command,'remove','--no-auto-remove',*sorted(TARGETS)],capture_output=True,text=True,env={**os.environ,'LC_ALL':'C','DEBIAN_FRONTEND':'noninteractive','NEEDRESTART_MODE':'l'})
 emit('apt_result',exitCode=r.returncode,stdout=r.stdout,stderr=r.stderr)
 require(r.returncode==0,'apt_remove_failed_no_retry')
 after=snapshot();expected={k:v for k,v in before['packages'].items() if k not in TARGETS};actual={k:v for k,v in after['packages'].items() if k not in TARGETS}
 require(expected==actual,'other_package_changed')
 require(all(not after['packages'].get(k,{}).get('status','').startswith('ii') for k in TARGETS),'target_still_installed')
 for key in ['holds','files','services','bootID']:require(before[key]==after[key],'protected_'+key+'_changed')
 removed=[]
 archive_locks=[]
 try:
  for lock_path in ['/var/lib/dpkg/lock-frontend','/var/lib/dpkg/lock','/var/cache/apt/archives/lock']:
   fd=os.open(lock_path,os.O_RDWR);archive_locks.append(fd);fcntl.lockf(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  require(inventory()==after['packages'],'package_drift_before_archive_phase')
  for a in archives:
   evidence=archive_check(a,after['packages']);emit('archive_before_unlink',**evidence)
   st=P(a['path']).lstat();require((st.st_dev,st.st_ino)==(evidence['device'],evidence['inode']) and stat.S_ISREG(st.st_mode) and st.st_nlink==1,'archive_inode_drift')
   P(a['path']).unlink();require(not P(a['path']).exists(),'archive_unlink_failed');removed.append(evidence)
 finally:
  for fd in reversed(archive_locks):os.close(fd)
 final=snapshot()
 for key in ['packages','holds','files','services','bootID']:require(after[key]==final[key],'archive_phase_changed_'+key)
 remaining=[x for x in owned if P(x['path']).exists() or P(x['path']).is_symlink()]
 emit('completed',kernelOwnedFilesRemaining=remaining,kernelOwnedAllocatedBeforeBytes=sum(x['allocatedBytes'] for x in owned),kernelOwnedRemovedPathAllocatedBeforeBytes=sum(x['allocatedBytes'] for x in owned if x not in remaining),after=final,archivesRemoved=removed,removedArchiveAllocatedBytes=sum(x['allocatedBytes'] for x in removed),observedRootFreeDeltaBytes=final['root']['freeBytes']-before['root']['freeBytes'],limits='Root delta includes concurrent filesystem activity; installed-size estimate is not measured kernel recovery. Final cluster headroom is independently gated.')
if __name__=='__main__':
 try:main()
 except Exception as error:emit('failed',errorType=type(error).__name__,error=str(error));sys.exit(1)
