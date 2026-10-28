"""Read stable snapshotter metadata and verify exact cache filesystem ownership.

No snapshot view/mount or other native API mutation is used. This reader opens
the bounded snapshotter metadata file read-only, requires two identical reads
and valid bbolt transaction checksums, then cross-checks native API identities.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import uuid

REMOTE = r'''
import base64,collections,contextlib,hashlib,io,json,os,pathlib,stat,struct,sys
request=json.load(sys.stdin)
code=base64.b64decode(request['inventorySource'],validate=True)
assert hashlib.sha256(code).hexdigest()==request['inventorySHA256']
native={}
with contextlib.redirect_stdout(io.StringIO()):exec(compile(code,'<pinned-native-inventory>','exec'),native)
live=native['result'];cmd=native['cmd'];base=native['nsbase'];unvi=native['unvi']
root=pathlib.Path('/var/lib')/'containerd-k8s'/'io.containerd.snapshotter.v1.overlayfs'
database=root/'metadata.db'
assert root.resolve()==root and database.resolve()==database
s=database.stat();assert stat.S_ISREG(s.st_mode) and s.st_uid==0 and s.st_nlink==1 and 8192<=s.st_size<=8*1024**2
before=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
data=database.read_bytes();second=database.read_bytes();s=database.stat()
assert before==(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns) and data==second
second=None
pagesize=struct.unpack_from('<I',data,24)[0];assert pagesize in (4096,8192,16384,32768,65536)
valid=[]
for page in (0,1):
 off=page*pagesize;pid,flag,count,overflow=struct.unpack_from('<QHHI',data,off)
 magic,version,ps,flags=struct.unpack_from('<IIII',data,off+16)
 assert pid==page and flag==4 and magic==0xed0cdaed and version==2 and ps==pagesize
 fnv=14695981039346656037
 for byte in data[off+16:off+72]:fnv=((fnv^byte)*1099511628211)&((1<<64)-1)
 assert fnv==struct.unpack_from('<Q',data,off+72)[0]
 pgroot,sequence,free,hwm,txid=struct.unpack_from('<QQQQQ',data,off+32)
 assert 1<pgroot<hwm and hwm*pagesize<=len(data)
 valid.append((txid,pgroot))
txid,pgroot=max(valid);visited=set()
def entries(page=None,inline=None):
 if inline is None:
  assert page not in visited;visited.add(page);off=page*pagesize
  assert 0<=off<len(data);pid,flag,count,overflow=struct.unpack_from('<QHHI',data,off)
  assert pid==page and off+(overflow+1)*pagesize<=len(data);raw=data[off:off+(overflow+1)*pagesize]
 else:
  raw=inline;pid,flag,count,overflow=struct.unpack_from('<QHHI',raw,0);assert overflow==0
 assert flag in (1,2) and count<=65535 and 16+count*16<=len(raw)
 out=[]
 for i in range(count):
  pos=16+i*16
  if flag==1:
   rel,size,child=struct.unpack_from('<IIQ',raw,pos);assert pos+rel+size<=len(raw);out.extend(entries(page=child))
  else:
   typ,rel,ks,vs=struct.unpack_from('<IIII',raw,pos);start=pos+rel;assert start+ks+vs<=len(raw)
   out.append((raw[start:start+ks],typ,raw[start+ks:start+ks+vs]))
 assert len({x[0] for x in out})==len(out)
 return out
def bucket(value):
 assert len(value)>=16;pg,seq=struct.unpack_from('<QQ',value,0)
 return entries(page=pg) if pg else entries(inline=value[16:])
def child(rows,key):
 matches=[(t,v) for k,t,v in rows if k==key];assert len(matches)==1 and matches[0][0]==1
 return bucket(matches[0][1])
rows=child(child(entries(page=pgroot),b'v1'),b'snapshots');backend={}
for key,typ,val in rows:
 assert typ==1;values={k:v for k,t,v in bucket(val) if t==0}
 ident,end=unvi(values[b'id'],0);assert end==len(values[b'id']) and 0<ident<10000000
 backend[key.decode()]={'id':str(ident),'kind':values[b'kind'][0],'parent':values.get(b'parent',b'').decode()}
ids={x['id'] for x in backend.values()};assert len(ids)==len(backend)
actual={p.name for p in (root/'snapshots').iterdir() if p.is_dir()}
orphans=sorted(actual-ids);missing=sorted(ids-actual)
assert not missing
mapped=[]
for info in live['potentialSnapshotInfos']:
 key=info['Name'];matches=[(name,row) for name,row in backend.items() if name.startswith('k8s.io/') and name.endswith('/'+key)]
 assert len(matches)==1,('unambiguous_backend_mapping_required',key)
 name,row=matches[0];assert row['kind']==3
 if info.get('Parent'):assert row['parent'].endswith('/'+info['Parent']) and row['parent'] in backend
 else:assert row['parent']==''
 path=root/'snapshots'/row['id'];fs=path/'fs'
 assert path.resolve()==path and fs.resolve()==fs and fs.is_dir() and path.stat().st_uid==fs.stat().st_uid==0
 assert path.stat().st_dev==fs.stat().st_dev==database.stat().st_dev and not path.is_mount() and not fs.is_mount()
 blocks=0;count=0;seen=set();tree=hashlib.sha256()
 for parent,dirs,files in os.walk(path,followlinks=False):
  parent=pathlib.Path(parent);dirs.sort();files.sort()
  for entry in [parent,*[parent/n for n in files],*[parent/n for n in dirs if (parent/n).is_symlink()]]:
   st=entry.lstat();assert st.st_dev==s.st_dev;count+=1;assert count<=100000
   inode=(st.st_dev,st.st_ino)
   if inode not in seen:seen.add(inode);blocks+=st.st_blocks*512
   record=[str(entry.relative_to(path)),st.st_dev,st.st_ino,st.st_mode,st.st_uid,st.st_gid,st.st_nlink,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_blocks]
   if stat.S_ISLNK(st.st_mode):record.append(os.readlink(entry))
   tree.update(json.dumps(record,separators=(',',':')).encode())
 mapped.append({'key':key,'backendKey':name,'id':row['id'],'path':str(path),'fs':str(fs),
  'allocatedBytes':blocks,'entries':count,'treeIdentitySHA256':tree.hexdigest(),
  'directoryIdentity':{k:getattr(path.stat(),'st_'+k) for k in ('dev','ino','mode','uid','gid','size','mtime_ns','ctime_ns','blocks')}})
assert cmd(base+['snapshots','list']).decode()==native['snapraw'],'snapshot_api_state_changed_during_physical_mapping'
assert before==(database.stat().st_dev,database.stat().st_ino,database.stat().st_size,database.stat().st_mtime_ns,database.stat().st_ctime_ns)
result={'node':'workernode2','readOnly':True,'nativeInventory':live,'database':{'path':str(database),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'txid':txid,'pageSize':pagesize,'stableDoubleRead':True,'validTransactionChecksums':True},
 'backendSnapshotCount':len(backend),'allBackendIDs':sorted(ids,key=int),'orphanDirectories':orphans,'mappedCandidates':mapped,
 'actualCandidateAllocatedBytes':sum(x['allocatedBytes'] for x in mapped),
 'retirementAuthorizedByThisProfile':False,'mutationsPerformed':False}
print(json.dumps(result))
'''


def main():
    repo = Path(__file__).resolve().parents[5]
    f = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
    h = f / 'platform-upstream-review-20261027/longhorn-application-batch-20261028/native-cache-qualification'
    assert f.is_mount() and os.geteuid() == 1000 and (h / 'ownership.json').is_file()
    os.umask(0o077)
    inventory = runpy.run_path(str(Path(__file__).with_name('inventory.py')))['REMOTE'].encode()
    ident = uuid.uuid4().hex
    with (h / ('physical-ownership-' + ident + '.json')).open('x') as out:
        json.dump({'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(f), 'generatedPaths': [str(h)],
            'peakBytes': 64 * 1024**2, 'regeneration': 'Same stable read-only metadata/API/physical-inode projection',
            'protected': 'Every native metadata/image/blob/lease/snapshot, all workload/user data; no native objects created or removed',
            'endCondition': 'Precise physical cache mapping and orphan inventory; no deletion from this reader'}, out, indent=2)
    lib = runpy.run_path(str(repo / 'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'))
    password = lib['privilege_input']()
    try:
        request = {'inventorySource': base64.b64encode(inventory).decode(), 'inventorySHA256': hashlib.sha256(inventory).hexdigest()}
        p = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-i', '/home/brajam/.ssh/id_ed25519',
            '-p', '2002', 'james@192.168.0.5', shlex.join(['sudo', '-S', '-k', '-p', '', '/usr/bin/python3', '-B', '-c', REMOTE])],
            input=password + b'\n' + json.dumps(request).encode(), capture_output=True, timeout=300)
        with (h / ('physical-execution-' + ident + '.json')).open('x') as out:
            json.dump({'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'inventorySHA256': request['inventorySHA256'], 'exitCode': p.returncode,
                'stdoutSHA256': hashlib.sha256(p.stdout).hexdigest(), 'stderrSHA256': hashlib.sha256(p.stderr).hexdigest(),
                'stderr': p.stderr.decode()[-2000:] if p.returncode else '', 'readOnly': True}, out, indent=2)
        assert p.returncode == 0 and len(p.stdout) <= 4 * 1024**2, ('readonly_physical_qualification_failed', p.returncode, p.stderr.decode()[-1500:])
        value = json.loads(p.stdout)
        value['sourceSHA256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        with (h / ('physical-' + ident + '.json')).open('x') as out:
            json.dump(value, out, indent=2)
        print(json.dumps({'physicalCandidates': len(value['mappedCandidates']), 'allocatedBytes': value['actualCandidateAllocatedBytes'],
            'orphanDirectories': value['orphanDirectories'], 'metadataTransaction': value['database']['txid'], 'mutationsPerformed': False}))
    finally:
        password = None


if __name__ == '__main__':
    main()
