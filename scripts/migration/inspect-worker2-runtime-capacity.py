"""Read-only worker2 storage/runtime inventory after application rescheduling."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import uuid

REMOTE = r'''
import hashlib,json,os,pathlib,socket,subprocess
assert os.geteuid()==0 and socket.gethostname()=='workernode2'
def cmd(args):
 p=subprocess.run(args,capture_output=True,timeout=90)
 assert p.returncode==0 and len(p.stdout)<=262144
 return p.stdout.decode()
fs=os.statvfs('/')
result={'hostname':socket.gethostname(),'readOnly':True,'rootAvailableBytes':fs.f_bavail*fs.f_frsize,
 'taskDirectories':cmd(['du','-x','-B1','--max-depth=3','/home/james/.local/share/branconet-migration']),
 'logDirectories':cmd(['du','-x','-B1','--max-depth=2','/var/log']),
 'journalUsage':cmd(['journalctl','--disk-usage']),
 'rootFilesystem':json.loads(cmd(['findmnt','-J','-T','/','-o','UUID,SOURCE,FSTYPE'])),
 'volumeGroups':json.loads(cmd(['vgs','--reportformat','json','--units','b','--nosuffix','-o','vg_name,vg_uuid,vg_size,vg_free,vg_extent_size'])),
 'logicalVolumes':json.loads(cmd(['lvs','--reportformat','json','--units','b','--nosuffix','-o','lv_path,lv_uuid,lv_size,lv_attr,vg_name'])),
 'physicalVolumes':json.loads(cmd(['pvs','--reportformat','json','--units','b','--nosuffix','-o','pv_name,pv_uuid,pv_size,pv_free,vg_name'])),
 'aptCache':cmd(['du','-x','-B1','--max-depth=1','/var/cache/apt/archives'])}
ctr=pathlib.Path('/opt/containerd-k8s/bin/ctr')
assert hashlib.sha256(ctr.read_bytes()).hexdigest()=='bcf0357ed9f17b8851ccde2486321c8fa2d0bcfb0ea71c267da6a1155c7f4743'
result['nativeImages']=cmd([str(ctr),'--address','/run/containerd-k8s/containerd.sock','--namespace','k8s.io','images','list'])
base=[str(ctr),'--address','/run/containerd-k8s/containerd.sock','--namespace','k8s.io']
result['nativeSnapshotHelp']=cmd(base+['snapshots','--help'])
result['nativeSnapshots']=cmd(base+['snapshots','list'])
result['nativeContainers']=cmd(base+['containers','list'])
result['nativeLeases']=cmd(base+['leases','list'])
print(json.dumps(result))
'''


def main():
    repo = Path(__file__).resolve().parents[2]
    f = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
    h = f / 'platform-upstream-review-20261027/longhorn-application-batch-20261028'
    assert f.is_mount() and os.geteuid() == 1000 and h.is_dir()
    lib = runpy.run_path(str(repo / 'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'))
    password = lib['privilege_input']()
    try:
        args = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-i', '/home/brajam/.ssh/id_ed25519',
            '-p', '2002', 'james@192.168.0.5', shlex.join(['sudo', '-S', '-k', '-p', '', '/usr/bin/python3', '-B', '-c', REMOTE])]
        p = subprocess.run(args, input=password + b'\n', capture_output=True, timeout=180)
        assert p.returncode == 0 and len(p.stdout) <= 1024**2, ('read_only_capacity_inventory_failed', p.returncode)
        value = json.loads(p.stdout)
        value['sourceSHA256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        path = h / ('worker2-capacity-' + uuid.uuid4().hex + '.json')
        with path.open('x') as out:
            json.dump(value, out, indent=2)
        print(json.dumps({'receipt': str(path), 'rootAvailableBytes': value['rootAvailableBytes'],
            'readOnly': True, 'nativeSnapshotHelp': value['nativeSnapshotHelp']}))
    finally:
        password = None


if __name__ == '__main__':
    main()
