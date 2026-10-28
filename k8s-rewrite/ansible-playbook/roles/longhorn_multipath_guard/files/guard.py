"""Exclude verified Longhorn IET disks from multipath; release only idle maps.

No service stop, mounted-device unmap, forced removal, key read or data write.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import uuid

REMOTE = r'''
import errno,hashlib,json,os,pathlib,re,socket,stat,subprocess
request=json.load(__import__('sys').stdin);assert os.geteuid()==0 and socket.gethostname()==request['hostname']
apply=request['apply'];target=pathlib.Path('/etc/multipath/conf.d/90-branconet-longhorn.conf')
content=b'# Managed by Branconet longhorn_multipath_guard.\nblacklist {\n    device {\n        vendor "^IET$"\n        product "^VIRTUAL-DISK$"\n    }\n}\n'
def need(v,s):
 if not v:raise ValueError(s)
def cmd(a):
 p=subprocess.run(a,capture_output=True,timeout=30);need(len(p.stdout)<=2097152 and len(p.stderr)<=65536,'bounded_native_response');return p
def text(a):
 p=cmd(a);need(p.returncode==0,'native_inspection_failed_'+a[0]);return p.stdout.decode()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pid(service):return text(['systemctl','show',service,'--property=MainPID','--value']).strip()
def section(t,name):
 lines=t.splitlines();out=[];level=0;found=False
 for line in lines:
  if not found:
   if not re.fullmatch(re.escape(name)+r'\s*\{',line.strip()):continue
   found=True
  out.append(line);level+=line.count('{')-line.count('}')
  if found and level==0:return '\n'.join(out)
 return ''
before_boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip();runtime_pid=pid('containerd-k8s');mp_pid=pid('multipathd')
need(runtime_pid not in ['','0'] and mp_pid not in ['','0'],'original_live_runtime_and_multipath_daemon')
effective=text(['multipath','-t']);need(re.search(r'config_dir\s+"/etc/multipath/conf.d/?"',effective),'existing_expected_config_directory')
files=[pathlib.Path('/etc/multipath.conf'),*target.parent.glob('*.conf')];originals={str(p):sha(p)for p in files if p.is_file()and p!=target}
longhorn={};scsi={}
for p in pathlib.Path('/dev/longhorn').iterdir():
 if not re.fullmatch('pvc-[0-9a-f-]{36}',p.name):continue
 try:s=p.stat()
 except FileNotFoundError:continue
 need(stat.S_ISBLK(s.st_mode),'longhorn_paths_are_block_devices');longhorn[(os.major(s.st_rdev),os.minor(s.st_rdev))]=p.name
for p in pathlib.Path('/sys/class/block').iterdir():
 if not (p/'device/vendor').exists():continue
 vendor=(p/'device/vendor').read_text().strip();model=(p/'device/model').read_text().strip();number=tuple(map(int,(p/'dev').read_text().strip().split(':')))
 scsi[p.name]={'vendor':vendor,'model':model,'number':number,'longhornVolume':longhorn.get(number)}
 if vendor=='IET'and model=='VIRTUAL-DISK':need(number in longhorn,'unowned_IET_disk_preserved_'+p.name)
maps=[];protected_maps=[]
daemon_map_list=text(['multipathd','show','maps','raw','format','%n'])
# The daemon can answer "ok" for an empty map list. Enumerate actual kernel
# multipath UUIDs rather than treating protocol acknowledgements as map names.
names=[]
for d in pathlib.Path('/sys/class/block').glob('dm-*'):
 if (d/'dm/uuid').read_text().strip().startswith('mpath-'):
  names.append((d/'dm/name').read_text().strip())
for name in names:
 name=name.strip();need(re.fullmatch('[A-Za-z0-9_-]+',name),'bounded_map_name')
 raw=text(['dmsetup','info','-c','--noheadings','--separator','|','-o','name,major,minor,open,uuid',name]).strip().split('|')
 need(len(raw)==5,'native_map_identity');row={'name':raw[0].strip(),'major':int(raw[1]),'minor':int(raw[2]),'openCount':int(raw[3]),'uuid':raw[4].strip()}
 deps=text(['dmsetup','deps','-o','devname',name]);devices=re.findall(r'\(([^()]+)\)',deps)
 if devices and all(d in scsi and scsi[d]['vendor']=='IET'and scsi[d]['model']=='VIRTUAL-DISK'and scsi[d]['longhornVolume']for d in devices):
  need(row['openCount']==0 and row['uuid'].startswith('mpath-'),'only_unused_Longhorn_multipath_maps');row['devices']=devices;maps.append(row)
 else:protected_maps.append(row)
numbers={(m['major'],m['minor'])for m in maps};namespaces=set();refs=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  ns=os.readlink(p/'ns/mnt')
  if ns not in namespaces:
   namespaces.add(ns)
   for line in (p/'mountinfo').read_text().splitlines():
    a=line.split(' - ',1)[0].split()
    if tuple(map(int,a[2].split(':')))in numbers:refs.append({'pid':p.name,'namespace':ns,'target':a[4]})
  for fd in (p/'fd').iterdir():
   try:
    s=fd.stat()
    if stat.S_ISBLK(s.st_mode)and(os.major(s.st_rdev),os.minor(s.st_rdev))in numbers:refs.append({'pid':p.name,'fd':fd.name})
   except OSError as e:
    if e.errno not in [errno.ENOENT,errno.ESRCH,errno.ENXIO,errno.EBADF]:raise
 except (FileNotFoundError,ProcessLookupError):continue
need(not refs,'any_active_multipath_map_reference_preserved')
result={'hostname':socket.gethostname(),'apply':apply,'configurationPath':str(target),'configurationSHA256':hashlib.sha256(content).hexdigest(),
 'originalConfigurationHashes':originals,'ownedLonghornBlockDevices':len(longhorn),'matchedVirtualDevices':[dict(name=n,**s)for n,s in scsi.items()if s['vendor']=='IET'and s['model']=='VIRTUAL-DISK'],
 'unusedMaps':maps,'protectedOtherMaps':protected_maps,'kernelMapNames':names,'daemonMapList':daemon_map_list,'mapOpenCountsZero':True,'allMountNamespacesChecked':len(namespaces),'activeMapReferences':refs,
 'runtimePIDBefore':runtime_pid,'multipathPIDBefore':mp_pid,'bootID':before_boot,'configurationCreated':False,'mapsReleased':[],'dataOrEncryptionKeyChanged':False}
if apply:
 need(target.parent.parent.is_dir()and target.parent.parent.resolve()==target.parent.parent,'original_etc_multipath_parent')
 if not target.parent.exists():target.parent.mkdir(mode=0o755)
 need(target.parent.resolve()==target.parent and target.parent.stat().st_uid==0 and not target.parent.stat().st_mode&0o022,'root_owned_configuration_directory')
 if target.exists():need(target.resolve()==target and target.read_bytes()==content,'existing_configuration_not_overwritten')
 else:
  fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
  try:need(os.write(fd,content)==len(content),'complete_small_config_write');os.fchmod(fd,0o644);os.fsync(fd)
  finally:os.close(fd)
  result['configurationCreated']=True
 parsed=text(['multipath','-t']);bl=section(parsed,'blacklist')
 need('vendor "^IET$"'in bl and 'product "^VIRTUAL-DISK$"'in bl,'native_parser_accepted_only_targeted_device_rule')
 reload=cmd(['multipathd','reconfigure']);need(reload.returncode==0 and reload.stdout.strip()==b'ok','live_daemon_reconfigured_without_restart')
 live=text(['multipathd','show','config']);bl=section(live,'blacklist')
 need('vendor "^IET$"'in bl and 'product "^VIRTUAL-DISK$"'in bl,'live_daemon_targeted_blacklist')
 for row in maps:
  exists=cmd(['dmsetup','info',row['name']])
  if exists.returncode:
   result['mapsReleased'].append({'name':row['name'],'method':'daemon_cleanup_after_reconfigure'});continue
  current=text(['dmsetup','info','-c','--noheadings','--separator','|','-o','name,major,minor,open,uuid',row['name']]).strip().split('|')
  need([x.strip()for x in current]==[row['name'],str(row['major']),str(row['minor']),'0',row['uuid']],'same_idle_map_before_normal_flush')
  flushed=cmd(['multipath','-f',row['name']]);need(flushed.returncode==0,'normal_idle_map_flush_refused_preserve_device')
  result['mapsReleased'].append({'name':row['name'],'method':'normal_multipath_f_no_force'})
 need(all(sha(pathlib.Path(p))==v for p,v in originals.items()),'all_preexisting_configurations_preserved')
 need(sha(target)==result['configurationSHA256'],'managed_configuration_unchanged')
 result['effectiveConfigurationSHA256']=hashlib.sha256(parsed.encode()).hexdigest()
need(pid('containerd-k8s')==runtime_pid and pid('multipathd')==mp_pid and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==before_boot,'original_services_and_boot_not_restarted')
result['status']='targeted_rule_and_unused_map_release_completed'if apply else'qualified_read_only';print(json.dumps(result))
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=['inspect', 'apply'])
    p.add_argument('--node', choices=['workernode2', 'masternode', 'workernode1'], default='workernode2')
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[5]
    f = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
    h = f / 'platform-upstream-review-20261027/longhorn-runtime-retirement-20261028'
    assert f.is_mount() and os.geteuid() == 1000 and h.is_dir()
    for path in (f, Path('/mnt/c')):
        fs = os.statvfs(path)
        assert fs.f_bavail * fs.f_frsize >= 15 * 1024**3 + 1024**2
    if a.phase == 'apply':
        intent = h / ('multipath-' + a.node + '-configuration-intent-' + uuid.uuid4().hex + '.json')
        with intent.open('x') as out:
            json.dump({'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(f),
                'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b',
                'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'productionConfiguration': {'node': a.node, 'path': '/etc/multipath/conf.d/90-branconet-longhorn.conf'},
                'completeMetadataPeakBytes': 1024**2,
                'regeneration': 'This maintained Ansible guard verifies all IET disks belong to Longhorn, then creates only its exact targeted drop-in',
                'retainedConsumer': 'Required persistent host configuration for future encrypted Longhorn disk attachments',
                'protected': 'All preexisting configuration, active maps, data, native keys, services and boot'}, out, indent=2)
    lib = runpy.run_path(str(repo / 'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'), run_name='protected_privilege_input')
    password = lib['privilege_input']()
    try:
        ip = {'workernode2': '192.168.0.5', 'masternode': '192.168.0.4', 'workernode1': '192.168.0.6'}[a.node]
        cmd = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts',
            '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@' + ip,
            shlex.join(['sudo', '-S', '-k', '-p', '', '/usr/bin/python3', '-B', '-c', REMOTE])]
        request = {'hostname': a.node, 'apply': a.phase == 'apply'}
        run = subprocess.run(cmd, input=password + b'\n' + json.dumps(request).encode(), capture_output=True, timeout=180)
        result = json.loads(run.stdout) if run.returncode == 0 else {'status': 'refused_preserve_originals', 'exitCode': run.returncode,
            'diagnostic': run.stderr.decode(errors='replace')[-3000:]}
        result['sourceSHA256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        result['productionConfigurationTarget'] = '/etc/multipath/conf.d/90-branconet-longhorn.conf'
        result['generatedProductionConfiguration'] = result['productionConfigurationTarget'] if result.get('configurationCreated') else None
        out = h / ('multipath-' + a.node + '-' + a.phase + '-' + uuid.uuid4().hex + '.json')
        with out.open('x') as stream:
            json.dump(result, stream, indent=2)
        print(json.dumps(result))
        assert run.returncode == 0, 'native_guard_refused_inspect_saved_metadata'
    finally:
        password = None


if __name__ == '__main__':
    main()
