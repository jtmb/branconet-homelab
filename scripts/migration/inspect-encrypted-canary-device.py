"""Read-only exact canary device/mapping/mount-namespace diagnosis; never keys."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import uuid

REMOTE = r'''
import errno,hashlib,json,os,pathlib,socket,stat,subprocess
assert os.geteuid()==0 and socket.gethostname()=='workernode2'
name='pvc-9edde4e3-5a0c-4c0c-b317-47b045ee199e'
def command(args):
 p=subprocess.run(args,capture_output=True,timeout=20);assert len(p.stdout)<1048576 and len(p.stderr)<65536
 return {'exit':p.returncode,'stdout':p.stdout.decode(errors='replace'),'stderr':p.stderr.decode(errors='replace')}
paths=['/dev/longhorn/'+name,'/dev/mapper/'+name];devices={};numbers=set()
for path in paths:
 try:
  s=os.stat(path);assert stat.S_ISBLK(s.st_mode);n=(os.major(s.st_rdev),os.minor(s.st_rdev));numbers.add(n)
  sys=pathlib.Path('/sys/dev/block')/(str(n[0])+':'+str(n[1]))
  attrs={}
  for key in ['vendor','model','wwid']:
   q=sys/'device'/key
   attrs[key]=q.read_text().strip() if q.exists() else None
  devices[path]={'realpath':os.path.realpath(path),'major':n[0],'minor':n[1],'sysfs':attrs,
   'holders':[x.name for x in (sys/'holders').iterdir()]}
 except FileNotFoundError:devices[path]={'absent':True}
result={'hostname':socket.gethostname(),'volume':name,'readOnly':True,'devices':devices,
 'cryptsetupStatus':command(['cryptsetup','status',name]),
 'dmInfo':command(['dmsetup','info','-c','--noheadings','-o','name,major,minor,open,segments,uuid',name]),
 'dmDependencies':command(['dmsetup','deps','-o','devname',name]),
 'lsblk':command(['lsblk','--json','--paths','-o','NAME,KNAME,MAJ:MIN,TYPE,MOUNTPOINTS','/dev/longhorn/'+name]),
 'matchingMounts':[],'blockDescriptors':[],'namespaces':[]}
effective=command(['multipath','-t']);text=effective['stdout']
result['multipathConfig']={'exit':effective['exit'],'effectiveSHA256':hashlib.sha256(text.encode()).hexdigest(),
 'selectedSettings':[x.strip() for x in text.splitlines() if any(x.strip().startswith(k+' ')for k in ['config_dir','find_multipaths','user_friendly_names','reassign_maps'])],
 'files':[]}
for p in [pathlib.Path('/etc/multipath.conf'),*pathlib.Path('/etc/multipath/conf.d').glob('*.conf')]:
 if p.is_file():result['multipathConfig']['files'].append({'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
result['multipathMaps']=command(['multipathd','show','maps','raw','format','%n %w %d'])
result['scsiDevices']=[]
for p in pathlib.Path('/sys/class/block').iterdir():
 if not p.name.startswith('sd') or not (p/'device/vendor').exists():continue
 result['scsiDevices'].append({'name':p.name,'majorMinor':(p/'dev').read_text().strip(),
  'vendor':(p/'device/vendor').read_text().strip(),'model':(p/'device/model').read_text().strip(),
  'wwid':(p/'device/wwid').read_text().strip() if (p/'device/wwid').exists() else None})
seen=set();processes=0
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit():continue
 processes+=1;assert processes<=20000
 try:
  ns=os.readlink(p/'ns/mnt');comm=(p/'comm').read_text().strip()
  if ns not in seen:
   seen.add(ns);text=(p/'mountinfo').read_text();assert len(text)<=4*1024**2
   result['namespaces'].append({'mountNamespace':ns,'representativePID':int(p.name),'comm':comm})
   for line in text.splitlines():
    left,right=line.split(' - ',1);a,b=left.split(),right.split();number=tuple(map(int,a[2].split(':')))
    if name in line or number in numbers:
     result['matchingMounts'].append({'pid':int(p.name),'comm':comm,'namespace':ns,'mountID':a[0],
      'majorMinor':a[2],'root':a[3],'target':a[4],'filesystem':b[0],'source':b[1]})
  for fd in (p/'fd').iterdir():
   try:
    s=fd.stat()
    if stat.S_ISBLK(s.st_mode) and (os.major(s.st_rdev),os.minor(s.st_rdev))in numbers:
     result['blockDescriptors'].append({'pid':int(p.name),'comm':comm,'fd':fd.name,'target':os.readlink(fd),
      'major':os.major(s.st_rdev),'minor':os.minor(s.st_rdev)})
   except OSError as e:
    if e.errno not in [errno.ENOENT,errno.ESRCH,errno.ENXIO,errno.EBADF]:raise
 except (FileNotFoundError,ProcessLookupError):continue
result.update(processes=processes,mountNamespaces=len(seen));print(json.dumps(result))
'''


def main():
    repo = Path(__file__).resolve().parents[2]
    f = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
    h = f / 'platform-upstream-review-20261027/longhorn-runtime-retirement-20261028'
    assert f.is_mount() and os.geteuid() == 1000 and h.is_dir()
    lib = runpy.run_path(str(repo / 'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'), run_name='protected_privilege_input')
    password = lib['privilege_input']()
    try:
        args = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts',
            '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.5',
            shlex.join(['sudo', '-S', '-k', '-p', '', '/usr/bin/python3', '-B', '-c', REMOTE])]
        p = subprocess.run(args, input=password + b'\n', capture_output=True, timeout=120)
        assert p.returncode == 0 and len(p.stdout) <= 128 * 1024, ('readonly_inspection_failed', p.returncode, p.stderr.decode()[:2000])
        value = json.loads(p.stdout)
        value['sourceSHA256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        path = h / ('encrypted-device-inspection-' + uuid.uuid4().hex + '.json')
        with path.open('x') as out:
            json.dump(value, out, indent=2)
        print(json.dumps({k: v for k, v in value.items() if k != 'namespaces'}))
    finally:
        password = None


if __name__ == '__main__':
    main()
