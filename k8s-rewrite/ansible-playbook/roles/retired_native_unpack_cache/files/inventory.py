"""Read-only qualification of retired image filesystem caches; never prune images.

All image records and OCI content remain protected. This inventory does not
create a native snapshot/view/mount, change a lease or delete anything.
"""
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import uuid

REMOTE = r'''
import hashlib,json,os,pathlib,re,socket,struct,subprocess
assert os.geteuid()==0 and socket.gethostname()=='workernode2'
ctr=pathlib.Path('/opt/containerd-k8s/bin/ctr')
assert hashlib.sha256(ctr.read_bytes()).hexdigest()=='bcf0357ed9f17b8851ccde2486321c8fa2d0bcfb0ea71c267da6a1155c7f4743'
base=[str(ctr),'--address','/run/containerd-k8s/containerd.sock']
nsbase=base+['--namespace','k8s.io']
targets={
 'sha256:014e9ae348d5dcf3ed5451a5490a29bb6e51477f5b3291e31804c74fe6b557d9',
 'sha256:6432c71889d843c7efb381a4321e4fba07a52a0cfb50171921b6315bddf1b295',
 'sha256:1b3470b85eb38360c5b242f7cfbc7d45accc429704f725a8610137861db00397',
 'sha256:5da497fc6680b06cc26f7ee94aa2d46cccfdddfbfe26ce71676be518a182262a',
 'sha256:2f0c391e6c04501862598bbc5446165f8ebba08025168451f6f6447352316349',
 'sha256:0ab77160ccccaf9235dcb3864624440551d6dd63c771cfaf97094db869a28656'}
def cmd(args,limit=4194304):
 p=subprocess.run(args,capture_output=True,timeout=45)
 assert p.returncode==0 and len(p.stdout)<=limit,('bounded_native_read_failed',args[-2:],p.returncode)
 return p.stdout
def vi(n):
 b=bytearray()
 while n>127:b.append((n&127)|128);n>>=7
 b.append(n);return bytes(b)
def unvi(b,p):
 n=0;s=0
 while True:
  assert p<len(b) and s<64;x=b[p];p+=1;n|=(x&127)<<s
  if x<128:return n,p
  s+=7
def fields(b):
 out=[];p=0
 while p<len(b):
  tag,p=unvi(b,p);assert tag&7==2
  n,p=unvi(b,p);assert p+n<=len(b);out.append((tag>>3,b[p:p+n]));p+=n
 return out
def lease_resources(ident):
 raw=ident.encode();msg=b'\x0a'+vi(len(raw))+raw;request=b'\x00'+struct.pack('>I',len(msg))+msg
 p=subprocess.run(['curl','--silent','--show-error','--fail','--max-time','8','--http2-prior-knowledge',
  '--unix-socket','/run/containerd-k8s/containerd.sock','--dump-header','/dev/stderr',
  '-H','Content-Type: application/grpc','-H','TE: trailers','-H','containerd-namespace: k8s.io',
  '--data-binary','@-','http://localhost/containerd.services.leases.v1.Leases/ListResources'],
  input=request,capture_output=True,timeout=10)
 assert p.returncode==0 and b'HTTP/2 200' in p.stderr and re.search(br'grpc-status:\s*0(?:\s|$)',p.stderr,re.I),('readonly_lease_RPC_failed',p.returncode)
 assert len(p.stdout)<=1048576 and len(p.stdout)>=5 and p.stdout[0]==0
 size=struct.unpack('>I',p.stdout[1:5])[0];assert size==len(p.stdout)-5
 out=[]
 for field,b in fields(p.stdout[5:]):
  assert field==1;v=dict(fields(b));assert set(v)=={1,2}
  out.append({'id':v[1].decode(),'type':v[2].decode()})
 return out
namespaces=cmd(base+['namespaces','list','-q']).decode().splitlines();assert 'k8s.io' in namespaces
snapraw=cmd(nsbase+['snapshots','list']).decode();snapshots={}
for row in snapraw.splitlines()[1:]:
 parts=row.split();assert len(parts) in (2,3)
 snapshots[parts[0]]={'parent':parts[1] if len(parts)==3 else '', 'kind':parts[-1]}
imagesraw=cmd(nsbase+['images','list']).decode();image_rows={}
for row in imagesraw.splitlines()[1:]:
 parts=row.split();assert len(parts)>=4 and re.fullmatch('sha256:[0-9a-f]{64}',parts[2]);image_rows.setdefault(parts[2],[]).append(parts[0])
assert targets<=set(image_rows)
blob_cache={}
def blob(digest):
 assert re.fullmatch('sha256:[0-9a-f]{64}',digest)
 if digest not in blob_cache:
  raw=cmd(nsbase+['content','get',digest]);assert 'sha256:'+hashlib.sha256(raw).hexdigest()==digest;blob_cache[digest]=json.loads(raw)
 return blob_cache[digest]
def image_graph(digest):
 root=blob(digest);manifest=root;selected=digest
 if 'manifests' in root:
  entries=[x for x in root['manifests'] if x.get('platform',{}).get('os')=='linux' and x.get('platform',{}).get('architecture')=='amd64']
  assert len(entries)==1;selected=entries[0]['digest'];manifest=blob(selected)
 cfg=blob(manifest['config']['digest']);diffs=cfg['rootfs']['diff_ids'];assert 1<=len(diffs)<=128 and len(diffs)==len(manifest['layers'])
 chain=[];prior=None
 for diff in diffs:
  assert re.fullmatch('sha256:[0-9a-f]{64}',diff)
  prior=diff if prior is None else 'sha256:'+hashlib.sha256((prior+' '+diff).encode()).hexdigest();chain.append(prior)
 return {'rootDigest':digest,'manifestDigest':selected,'configDigest':manifest['config']['digest'],'chainIDs':chain,
  'layers':[{'digest':x['digest'],'bytes':x['size']} for x in manifest['layers']]}
graphs={};unresolved=[]
for digest in image_rows:
 try:graphs[digest]=image_graph(digest)
 except Exception as error:unresolved.append({'digest':digest,'category':type(error).__name__})
assert not unresolved,('unresolved_image_graphs_preserve_all_caches',unresolved)
protected=set();container_keys=[];foreign=[]
for ns in namespaces:
 prefix=base+['--namespace',ns]
 if ns!='k8s.io':
  lines=cmd(prefix+['snapshots','list']).decode().splitlines()[1:]
  foreign.extend({'namespace':ns,'snapshot':x.split()[0]} for x in lines);protected.update(x.split()[0] for x in lines)
 ids=cmd(prefix+['containers','list','-q']).decode().splitlines()
 for ident in ids:
  v=json.loads(cmd(prefix+['containers','info',ident]));key=v.get('SnapshotKey',v.get('snapshot_key',''))
  assert isinstance(key,str)
  if key:protected.add(key);container_keys.append({'namespace':ns,'containerID':ident,'snapshot':key})
leases=[]
for row in cmd(nsbase+['leases','list']).decode().splitlines()[1:]:
 ident=row.split()[0];resources=lease_resources(ident);leases.append({'leaseID':ident,'resources':resources})
 protected.update(x['id'] for x in resources if x['type'].startswith(('snapshots/','snapshotter/')))
for digest,g in graphs.items():
 if digest not in targets:protected.update(g['chainIDs'])
def ancestors(keys):
 out=set(keys)
 for key in list(keys):
  seen=set()
  while key in snapshots and snapshots[key]['parent']:
   assert key not in seen;seen.add(key);key=snapshots[key]['parent'];out.add(key)
 return out
protected=ancestors(protected)
potential=set().union(*(set(graphs[x]['chainIDs']) for x in targets)) & set(snapshots)-protected
while True:
 remove={info['parent'] for key,info in snapshots.items() if key not in potential and info['parent'] in potential}
 if not remove:break
 potential-=remove
assert all(snapshots[k]['kind'].lower()=='committed' for k in potential)
usage={}
if potential:
 raw=cmd(nsbase+['snapshots','usage','-b',*sorted(potential)]).decode()
 for row in raw.splitlines()[1:]:
  key,size,inodes=row.split();usage[key]={'allocatedBytes':int(size),'inodes':int(inodes)}
 assert set(usage)==potential
fs=os.statvfs('/')
result={'node':'workernode2','readOnly':True,'imageRecordsSHA256':hashlib.sha256(imagesraw.encode()).hexdigest(),
 'snapshotMetadataSHA256':hashlib.sha256(snapraw.encode()).hexdigest(),'snapshotCount':len(snapshots),
 'allImageGraphsResolved':len(graphs),'retiredImages':[{'references':image_rows[x],**graphs[x]} for x in sorted(targets)],
 'containers':container_keys,'leases':leases,'foreignNamespaceSnapshots':foreign,
 'potentialExclusiveRetiredImageFilesystemCaches':[{'key':key,**snapshots[key],**usage[key]} for key in sorted(potential)],
 'potentialAllocatedBytes':sum(x['allocatedBytes'] for x in usage.values()),'rootAvailableBytes':fs.f_bavail*fs.f_frsize,
 'potentialSnapshotInfos':[json.loads(cmd(nsbase+['snapshots','info',key])) for key in sorted(potential)],
 'retirementAuthorizedByThisInventory':False,'remainingQualification':'Complete OCI blob regeneration proof and exact physical file/mount/process exclusion; retain every image/content/lease and all user data',
 'mutationsPerformed':False}
print(json.dumps(result))
'''


def main():
    repo = Path(__file__).resolve().parents[5]
    f = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
    h = f / 'platform-upstream-review-20261027/longhorn-application-batch-20261028/native-cache-qualification'
    assert f.is_mount() and os.geteuid() == 1000 and h.resolve() == h
    os.umask(0o077)
    source = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if not h.exists():
        h.mkdir(mode=0o700)
        with (h / 'ownership.json').open('x') as out:
            json.dump({'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(f),
                'physicalFilesystemUUID': '3c792469-ea0e-4a2c-98e8-1185b141607b', 'generatedPaths': [str(h)],
                'peakBytes': 16 * 1024**2, 'regeneration': 'Same bounded native metadata reads using pinned ctr and read-only lease API',
                'protected': 'Every image record, OCI blob, lease, native container, active filesystem, volume and original source/data',
                'endCondition': 'Precisely establish candidate derived cache bytes and all preservation prerequisites; no deletion in this reader'}, out, indent=2)
    lib = runpy.run_path(str(repo / 'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'))
    password = lib['privilege_input']()
    ident = uuid.uuid4().hex
    try:
        p = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-i', '/home/brajam/.ssh/id_ed25519',
            '-p', '2002', 'james@192.168.0.5', shlex.join(['sudo', '-S', '-k', '-p', '', '/usr/bin/python3', '-B', '-c', REMOTE])],
            input=password + b'\n', capture_output=True, timeout=240)
        with (h / ('execution-' + ident + '.json')).open('x') as out:
            json.dump({'sourceSHA256': source, 'exitCode': p.returncode,
                'stdoutSHA256': hashlib.sha256(p.stdout).hexdigest(), 'stderrSHA256': hashlib.sha256(p.stderr).hexdigest(),
                'readOnly': True}, out, indent=2)
        assert p.returncode == 0 and len(p.stdout) <= 4 * 1024**2, ('native_read_only_qualification_failed', p.returncode, p.stderr.decode()[-1500:])
        value = json.loads(p.stdout)
        value['sourceSHA256'] = source
        with (h / ('inventory-' + ident + '.json')).open('x') as out:
            json.dump(value, out, indent=2)
        print(json.dumps({'potentialAllocatedBytes': value['potentialAllocatedBytes'],
            'potentialSnapshots': len(value['potentialExclusiveRetiredImageFilesystemCaches']),
            'containerReferencesChecked': len(value['containers']), 'leasesChecked': len(value['leases']),
            'mutationsPerformed': False, 'retirementAuthorizedByThisInventory': False}))
    finally:
        password = None


if __name__ == '__main__':
    main()
