#!/usr/bin/env python3
"""Read-only source/consumer inventory; never authorizes or performs retirement."""
import concurrent.futures
import datetime
import json
import pathlib
import shlex
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNTIME = pathlib.Path.home()/'.local/share/branconet-migration'
HOSTS = ('192.168.0.4', '192.168.0.5', '192.168.0.6')
PREFIXES = ('/gluster/volumes', '/mnt/container-program-files', '/mnt/migration-gluster-read')
REMOTE = r'''
import json,pathlib,subprocess,xml.etree.ElementTree as ET
def run(args):
    return subprocess.run(args,capture_output=True,text=True,timeout=25)
def flatten(items):
    for item in items:
        yield item
        yield from flatten(item.get('children',[]))
mounts=json.loads(run(['findmnt','-J','-o','TARGET,SOURCE,FSTYPE']).stdout)['filesystems']
mounts=[{k:m[k] for k in ('target','source','fstype')} for m in flatten(mounts) if m.get('fstype')=='fuse.glusterfs']
ids=run(['docker','ps','-q']).stdout.split()
containers=json.loads(run(['docker','inspect',*ids]).stdout) if ids else []
consumers=[]
for m in mounts:
    p=run(['fuser','-m',m['target']])
    if p.returncode not in (0,1):raise RuntimeError('Open-file inventory failed')
    holders=[]
    for pid in p.stdout.split():
        if pid.isdigit():
            name=pathlib.Path('/proc')/pid/'comm'
            try:holders.append({'pid':int(pid),'process':name.read_text().strip()})
            except FileNotFoundError:pass
    consumers.append({'target':m['target'],'holders':holders})
info=run(['gluster','volume','info','staging-gfs','--xml'])
if info.returncode:raise RuntimeError('Gluster volume metadata unavailable')
tree=ET.fromstring(info.stdout)
volume=tree.find('.//volume')
if volume is None:raise RuntimeError('Gluster volume metadata missing')
print(json.dumps({'gluster_mounts':mounts,'brick_directory_retained':pathlib.Path('/gluster/volumes').is_dir(),
 'running_source_containers':[{'name':c['Name'].lstrip('/'),'service':(c['Config'].get('Labels') or {}).get('com.docker.swarm.service.name'),'mounted_sources':[m['Source'] for m in c['Mounts']]} for c in containers],
 'mount_open_file_inventory':consumers,'glusterd_active':run(['systemctl','is-active','glusterd']).stdout.strip(),
 'glusterd_enabled':run(['systemctl','is-enabled','glusterd']).stdout.strip(),
 'gluster_volume':{key:volume.findtext(key) for key in ('name','statusStr','typeStr','replicaCount','brickCount')}}))
'''

def main():
    request=json.load(sys.stdin)
    password=request['sudo_password']
    def inspect(host):
        command=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8',
                 '-i',str(pathlib.Path.home()/'.ssh/id_ed25519'),'-p','2002','james@'+host,
                 'sudo -S -p '+shlex.quote('')+' python3 -c '+shlex.quote(REMOTE)]
        result=subprocess.run(command,input=password+'\n',text=True,capture_output=True,timeout=100)
        if result.returncode:raise RuntimeError('Read-only source audit failed on '+host)
        return host,json.loads(result.stdout)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        nodes=dict(pool.map(inspect,HOSTS))
    kube=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
    def native(kind):
        return json.loads(subprocess.check_output(kube+['get',kind,'-A','-o','json'],timeout=30))['items']
    def source_path(path):
        return any(path==p or path.startswith(p+'/') for p in PREFIXES)
    volumes=[]
    for obj in native('pv'):
        spec=obj['spec'];path=spec.get('hostPath',{}).get('path',spec.get('local',{}).get('path',''))
        if 'glusterfs' in spec or source_path(path):volumes.append(obj['metadata']['name'])
    paths=[]
    for obj in native('pods'):
        if obj['status'].get('phase') in ('Succeeded','Failed'):continue
        for volume in obj['spec'].get('volumes',[]):
            path=volume.get('hostPath',{}).get('path','')
            if source_path(path):paths.append({'namespace':obj['metadata']['namespace'],'pod':obj['metadata']['name'],'path':path})
    previous=json.loads((ROOT/'evidence/retirement-readiness.json').read_text())
    report={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'nodes':nodes,
            'discovered_gluster_host_path_prefixes':list(PREFIXES),
            'native_gluster_persistent_volumes':volumes,'active_native_pod_gluster_host_paths':paths,
            'user_retirement_confirmation_received':previous.get('user_retirement_confirmation_received',False),
            'historical_redis_exception_resolved':True,'historical_redis_exception_evidence':'evidence/user-scope-update.json',
            'authenticated_bortus_operator_bootstrap_passed':True,
            'legacy_traefik_authenticated_login_untested':True,
            'consumer_inventory_scope':'Host fuser mount inventory and Docker mounts; recheck after stopping approved source services, including any mount-namespace holders.',
            'retirement_ready':False,'source_actions_performed':False}
    (ROOT/'evidence/retirement-readiness.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'source_containers':sum(len(n['running_source_containers']) for n in nodes.values()),
                      'gluster_mounts':sum(len(n['gluster_mounts']) for n in nodes.values()),
                      'native_gluster_consumers':len(volumes)+len(paths),'source_actions_performed':False}))

if __name__=='__main__':main()
