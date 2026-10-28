"""Qualify/retire only exclusive retired image filesystem caches via native API.

Images, original compressed OCI content, leases, containers and all workload data
are preserved. No raw directory deletion or global image/snapshot pruning.
"""
import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import uuid

REMOTE = r'''
import base64,collections,contextlib,gzip,hashlib,io,json,os,pathlib,re,stat,subprocess,sys,time
request=json.load(sys.stdin);mode=request['mode'];assert mode in ('qualify','retire')
program=base64.b64decode(request['physicalSource'],validate=True)
assert hashlib.sha256(program).hexdigest()==request['physicalSHA256']
physical={};packet={'inventorySource':request['inventorySource'],'inventorySHA256':request['inventorySHA256']}
original_stdin=sys.stdin
try:
 sys.stdin=io.StringIO(json.dumps(packet))
 with contextlib.redirect_stdout(io.StringIO()):exec(compile(program,'<pinned-physical-qualification>','exec'),physical)
finally:sys.stdin=original_stdin
profile=physical['result'];native=physical['native'];cmd=native['cmd'];base=native['nsbase']
assert not profile['orphanDirectories'],'unselected_orphan_directories_protect_native_remove_scope'
candidates=profile['mappedCandidates'];assert 1<=len(candidates)<=71
keys={x['key'] for x in candidates};root=physical['root'];bykey={x['key']:x for x in candidates}
assert not keys.intersection(request['excludedPreviouslyAttemptedKeys']),'previously_submitted_or_failed_key_is_permanently_protected'
assert profile['actualCandidateAllocatedBytes']>0
blobs=pathlib.Path('/var/lib')/'containerd-k8s'/'io.containerd.content.v1.content'/'blobs'/'sha256'
def ident(p):
 s=p.lstat();return {k:getattr(s,'st_'+k) for k in ('dev','ino','mode','uid','gid','nlink','size','mtime_ns','ctime_ns','blocks')}
def filehash(p):
 h=hashlib.sha256()
 with p.open('rb') as inp:
  for b in iter(lambda:inp.read(1048576),b''):h.update(b)
 return h.hexdigest()
def verify_blob(digest,size=None,diff=None):
 assert re.fullmatch('sha256:[a-f0-9]{64}',digest)
 p=blobs/digest[7:];assert p.resolve()==p
 before=ident(p);assert stat.S_ISREG(before['mode']) and before['uid']==0 and before['nlink']==1
 if size is not None:assert before['size']==size
 assert filehash(p)==digest[7:],'complete_original_OCI_blob_hash_required'
 record={'path':str(p),'digest':digest,'identity':before}
 if diff:
  raw=hashlib.sha256();count=0
  with gzip.open(p,'rb') as inp:
   for b in iter(lambda:inp.read(1048576),b''):
    count+=len(b);assert count<=4*1024**3;raw.update(b)
  assert 'sha256:'+raw.hexdigest()==diff,'complete_uncompressed_diffID_required'
  record.update(diffID=diff,uncompressedBytes=count)
 assert ident(p)==before
 return record
def xattr_and_links():
 links=collections.Counter();nlinks={};locations={};attrs={}
 for row in candidates:
  p=pathlib.Path(row['path']);h=hashlib.sha256()
  for parent,dirs,files in os.walk(p,followlinks=False):
   dirs.sort();files.sort();parent=pathlib.Path(parent)
   for entry in [parent,*[parent/n for n in files],*[parent/n for n in dirs if (parent/n).is_symlink()]]:
    s=entry.lstat();inode=(s.st_dev,s.st_ino)
    if not stat.S_ISDIR(s.st_mode):
     links[inode]+=1;nlinks[inode]=s.st_nlink;locations.setdefault(inode,set()).add(row['key'])
    values=[(n,hashlib.sha256(os.getxattr(entry,n,follow_symlinks=False)).hexdigest()) for n in sorted(os.listxattr(entry,follow_symlinks=False))]
    h.update(json.dumps([str(entry.relative_to(p)),values],separators=(',',':')).encode())
  attrs[row['key']]=h.hexdigest()
 assert all(links[k]==n and len(locations[k])==1 for k,n in nlinks.items()),'no_hardlinks_to_any_preserved_or_other_cache_tree'
 return attrs
def references():
 raw=base64.b64decode(request['guardSource'],validate=True)
 assert hashlib.sha256(raw).hexdigest()=='3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87'
 guard={'__name__':'unchanged_complete_reference_guard'};exec(compile(raw,'<full-reference-guard>','exec'),guard)
 # Exact fs/work paths avoid numeric-ID prefix collisions while retaining the
 # original complete unit/process/FD/map/mount checks for all cache contents.
 guard.update(BASE=root/'snapshots',ATTEMPTS=tuple(row['id']+'/'+leaf for row in candidates for leaf in ('fs','work')))
 result=guard['idle']()
 roots=[row['path'].encode() for row in candidates]
 def mentioned(raw):
  for path in roots:
   start=0
   while True:
    pos=raw.find(path,start)
    if pos<0:break
    end=pos+len(path)
    if end==len(raw) or raw[end:end+1] in b'/\x00\t\r\n :;,\'"}])':return True
    start=end
  return False
 units=cmd(['systemctl','list-units','--all','--state=active,activating,deactivating','--plain','--no-legend','--no-pager']).decode().splitlines()
 names=sorted({x.split()[0] for x in units if x.strip()});assert names
 props=cmd(['systemctl','show','--no-pager','--',*names],limit=64*1024**2)
 assert not mentioned(props),'configured_cache_root_reference'
 namespaces=set();processes=0
 for proc in pathlib.Path('/proc').iterdir():
  if not proc.name.isdigit() or int(proc.name)==os.getpid():continue
  try:
   processes+=1;assert not mentioned((proc/'cmdline').read_bytes()),'process_cache_root_argument'
   for path in [proc/'cwd',proc/'root',proc/'exe',*(proc/'fd').iterdir()]:
    try:
     value=os.readlink(path).removesuffix(' (deleted)').encode()
     assert not any(value==r or value.startswith(r+b'/') for r in roots),'open_cache_root_reference'
    except FileNotFoundError:continue
   ns=os.readlink(proc/'ns/mnt')
   if ns not in namespaces:
    namespaces.add(ns);text=(proc/'mountinfo').read_bytes()
    decoded=re.sub(br'\\([0-7]{3})',lambda m:bytes([int(m[1],8)]),text)
    assert not mentioned(decoded),'mounted_cache_root_reference'
  except (FileNotFoundError,ProcessLookupError):continue
 result.update(exactRootProcesses=processes,exactRootMountNamespaces=len(namespaces),allUnitPropertiesSHA256=hashlib.sha256(props).hexdigest())
 return result
attributes=xattr_and_links()
if mode=='qualify':
 verified={}
 for graph in profile['nativeInventory']['retiredImages']:
  for digest in (graph['rootDigest'],graph['manifestDigest'],graph['configDigest']):
   if digest not in verified:verified[digest]=verify_blob(digest)
  config=native['blob'](graph['configDigest']);diffs=config['rootfs']['diff_ids']
  assert len(diffs)==len(graph['layers'])
  for layer,diff in zip(graph['layers'],diffs):
   if layer['digest'] not in verified:verified[layer['digest']]=verify_blob(layer['digest'],layer['bytes'],diff)
   else:assert verified[layer['digest']]['diffID']==diff
 refs=references()
 assert cmd(base+['images','list']).decode()==native['imagesraw'],'original_image_records_changed'
 assert cmd(base+['snapshots','list']).decode()==native['snapraw'],'snapshot_state_changed_during_qualification'
 print(json.dumps({'status':'exclusive_cache_payload_and_reference_qualification_passed','node':'workernode2',
  'profile':profile,'verifiedOriginalBlobs':list(verified.values()),'xattrsSHA256':attributes,'references':refs,
  'regenerationCommands':[base+['snapshots','unpack',g['rootDigest']] for g in profile['nativeInventory']['retiredImages']],
  'regeneration':'Complete preserved root/config/layer hashes and every uncompressed diffID verified; pinned native offline unpack applies exactly these original OCI payloads without a registry or rebuild',
  'excludedPreviouslyAttemptedKeys':request['excludedPreviouslyAttemptedKeys'],'priorOutputHashes':request['priorOutputHashes'],
  'nativeImagesDeleted':False,'OCIContentDeleted':False,'snapshotsDeleted':False,'mutationsPerformed':False}))
 sys.exit(0)
expected=request['qualification'];assert expected['status']=='exclusive_cache_payload_and_reference_qualification_passed'
assert expected['excludedPreviouslyAttemptedKeys']==request['excludedPreviouslyAttemptedKeys'] and expected['priorOutputHashes']==request['priorOutputHashes']
assert candidates==expected['profile']['mappedCandidates'] and attributes==expected['xattrsSHA256'],'exact_cache_physical_identity_changed'
assert profile['nativeInventory']['imageRecordsSHA256']==expected['profile']['nativeInventory']['imageRecordsSHA256']
for blob in expected['verifiedOriginalBlobs']:assert ident(pathlib.Path(blob['path']))==blob['identity'],'original_image_blob_changed'
refs=references();snapshots=native['snapshots']
def depth(key):
 n=0
 while snapshots[key]['parent']:
  key=snapshots[key]['parent'];n+=1;assert n<200
 return n
order=sorted(keys,key=lambda k:(-depth(k),k));remaining=set(keys);removed=[];processed=set();api_errors=[];already_absent=[]
before_free=os.statvfs('/').f_bavail*os.statvfs('/').f_frsize
print(json.dumps({'status':'qualified_native_cache_retirement_started','keys':order,'expectedAllocatedBytes':sum(r['allocatedBytes'] for r in candidates)}),flush=True)
for key in order:
 assert not any(snapshots[k]['parent']==key for k in snapshots if k not in processed),'no_remaining_children_before_native_remove'
 info=subprocess.run(base+['snapshots','info',key],capture_output=True,timeout=30)
 if info.returncode:
  assert b'not found' in info.stderr.lower(),('native_info_failed_no_submission',key)
  already_absent.append(key);processed.add(key);remaining.remove(key)
  print(json.dumps({'alreadyAbsentNoDeleteSubmitted':key}),flush=True);continue
 row=bykey[key];now=ident(pathlib.Path(row['path']))
 assert {k:now[k] for k in row['directoryIdentity']}==row['directoryIdentity']
 print(json.dumps({'intent':key,'path':row['path'],'allocatedBytes':row['allocatedBytes']}),flush=True)
 p=subprocess.run(base+['snapshots','remove',key],capture_output=True,timeout=45)
 if p.returncode:
  failure={'status':'native_remove_failed_no_retry','key':key,'returncode':p.returncode,'stderr':p.stderr.decode()[:2000]}
  print(json.dumps(failure),flush=True)
  if b'not found' not in p.stderr.lower():sys.exit(1)
  api_errors.append(failure);processed.add(key);remaining.remove(key);continue
 removed.append({'key':key,'path':row['path'],'allocatedBytes':row['allocatedBytes']});remaining.remove(key);processed.add(key)
 print(json.dumps({'removed':key,'nativeRemoveCompleted':True}),flush=True)
deadline=time.monotonic()+60
while any(pathlib.Path(row['path']).exists() for row in candidates) and time.monotonic()<deadline:time.sleep(1)
assert all(not pathlib.Path(row['path']).exists() for row in candidates),'native_filesystem_cleanup_still_pending_no_raw_delete'
assert cmd(base+['images','list']).decode()==native['imagesraw'],'all_original_image_records_must_survive'
for blob in expected['verifiedOriginalBlobs']:
 p=pathlib.Path(blob['path']);assert ident(p)==blob['identity'] and filehash(p)==blob['digest'][7:],'every_original_image_blob_retained_and_complete'
after_free=os.statvfs('/').f_bavail*os.statvfs('/').f_frsize
print(json.dumps({'status':'qualified_cache_paths_absent_images_and_original_payloads_preserved',
 'removed':[{k:r[k] for k in ('key','path','allocatedBytes')} for r in candidates],
 'removedAllocatedLinuxBytes':sum(r['allocatedBytes'] for r in candidates),
 'directNativeRemoveAcknowledgements':removed,'alreadyAbsentWithoutRemovalSubmission':already_absent,'nativeRemoveErrorsNotRetried':api_errors,
 'rootAvailableBefore':before_free,'rootAvailableAfter':after_free,'rootAvailableDelta':after_free-before_free,
 'imagesDeleted':False,'originalOCIContentDeleted':False,'leasesDeleted':False,'containersDeleted':False,
 'volumesOrWorkloadDataChanged':False,'globalPruneUsed':False,'rawFilesystemDeletionUsed':False,'references':refs}),flush=True)
'''


def work():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['qualify', 'retire'])
    p.add_argument('--qualification', type=Path)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[5]
    f = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
    h = f / 'platform-upstream-review-20261027/longhorn-application-batch-20261028/native-cache-qualification'
    assert f.is_mount() and os.geteuid() == 1000 and (h / 'ownership.json').is_file()
    os.umask(0o077)
    physical = runpy.run_path(str(Path(__file__).with_name('physical.py')))['REMOTE'].encode()
    inventory = runpy.run_path(str(Path(__file__).with_name('inventory.py')))['REMOTE'].encode()
    guard = (f / 'node-cleanup-20261027/master-generated-cleanup/reference-full-properties.py').read_bytes()
    assert hashlib.sha256(guard).hexdigest() == '3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87'
    ident = uuid.uuid4().hex
    source = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    request = {'mode': a.mode, 'physicalSource': base64.b64encode(physical).decode(), 'physicalSHA256': hashlib.sha256(physical).hexdigest(),
        'inventorySource': base64.b64encode(inventory).decode(), 'inventorySHA256': hashlib.sha256(inventory).hexdigest(),
        'guardSource': base64.b64encode(guard).decode()}
    excluded = set()
    history = {}
    for old in sorted(h.glob('retire-output-*.jsonl')):
        raw = old.read_bytes()
        history[old.name] = hashlib.sha256(raw).hexdigest()
        for line in raw.splitlines():
            row = json.loads(line)
            if 'intent' in row:
                key = row['intent']
                assert isinstance(key, str) and key.startswith('sha256:') and len(key) == 71
                excluded.add(key)
    request.update(excludedPreviouslyAttemptedKeys=sorted(excluded), priorOutputHashes=history)
    if a.mode == 'retire':
        assert a.qualification and a.qualification.resolve() == a.qualification and a.qualification.parent == h
        q = json.loads(a.qualification.read_text())
        assert q['controllerSourceSHA256'] == source and q['physicalSHA256'] == request['physicalSHA256'] and q['inventorySHA256'] == request['inventorySHA256']
        request['qualification'] = q
    else:
        assert a.qualification is None
    with (h / (a.mode + '-intent-' + ident + '.json')).open('x') as out:
        json.dump({'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd', 'root': str(f), 'generatedPaths': [str(h)],
            'sourceSHA256': source, 'mode': a.mode, 'peakBytes': 128 * 1024**2,
            'physicalSHA256': request['physicalSHA256'], 'inventorySHA256': request['inventorySHA256'],
            'qualificationSHA256': hashlib.sha256(a.qualification.read_bytes()).hexdigest() if a.qualification else None,
            'excludedPreviouslyAttemptedKeys': request['excludedPreviouslyAttemptedKeys'], 'priorOutputHashes': history,
            'protected': 'Every image, original OCI blob, lease, container, volume, live runtime and user data',
            'regeneration': 'Pinned native offline snapshots unpack with verified preserved OCI payloads; never replay uncertain retirement'}, out, indent=2)
    lib = runpy.run_path(str(repo / 'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'))
    password = lib['privilege_input']()
    args = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts',
        '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.5',
        shlex.join(['sudo', '-S', '-k', '-p', '', '/usr/bin/python3', '-B', '-c', REMOTE])]
    try:
        with (h / (a.mode + '-output-' + ident + '.jsonl')).open('xb') as output:
            child = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.PIPE)
            _, errors = child.communicate(password + b'\n' + json.dumps(request).encode(), timeout=900)
        path = h / (a.mode + '-output-' + ident + '.jsonl')
        assert path.stat().st_size <= 4 * 1024**2
        with (h / (a.mode + '-execution-' + ident + '.json')).open('x') as out:
            json.dump({'controllerSourceSHA256': source, 'exitCode': child.returncode,
                'outputSHA256': hashlib.sha256(path.read_bytes()).hexdigest(), 'stderrSHA256': hashlib.sha256(errors).hexdigest(),
                'stderr': errors.decode()[-2500:] if child.returncode else ''}, out, indent=2)
        assert child.returncode == 0, ('native_cache_operation_failed_no_automatic_retry', child.returncode, errors.decode()[-2000:])
        rows = [json.loads(line) for line in path.read_bytes().splitlines()]
        final = rows[-1]
        final.update(controllerSourceSHA256=source, physicalSHA256=request['physicalSHA256'], inventorySHA256=request['inventorySHA256'])
        receipt = h / (a.mode + '-' + ident + '.json')
        with receipt.open('x') as out:
            json.dump(final, out, indent=2)
        print(json.dumps({'status': final['status'], 'receipt': str(receipt),
            'removedAllocatedLinuxBytes': final.get('removedAllocatedLinuxBytes', 0),
            'verifiedOriginalBlobs': len(final.get('verifiedOriginalBlobs', []))}))
    finally:
        password = None


def main():
    h = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/platform-upstream-review-20261027/longhorn-application-batch-20261028/native-cache-qualification')
    os.umask(0o077)
    with (h / 'operation.lock').open('a+b') as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        work()


if __name__ == '__main__':
    main()
