"""One-volume native three-copy rebalance; no replica/file deletion or forced placement."""
import argparse
import contextlib
import copy
import datetime as dt
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028';R=H/'qbit-three-copy-headroom'
V='pvc-999128b4-0ae2-4396-a8e4-eebace5d26f0';VU='6f21d4fc-3a0a-4e82-a468-98792639f2ed'
MASTER=V+'-r-4d021a64';OLD=V+'-r-e1f9805b'
UIDS={MASTER:'6cf45d01-9d4b-4ca0-ae5d-48431460904f',OLD:'a7a8c98f-a469-4628-b307-e333028d957a'}
IPS={'masternode':'192.168.0.4','workernode2':'192.168.0.5','workernode1':'192.168.0.6'}
SSH=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-i','/home/brajam/.ssh/id_ed25519','-p','2002']
PASSWORD=None

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
 return h.hexdigest()

def ref(path):
 assert path.resolve()==path and H in path.parents and path.is_file()
 return {'path':str(path),'sha256':sha(path)}

def load(reference):
 p=Path(reference['path']);assert ref(p)==reference;return json.loads(p.read_text())

def save(name,value):
 path=R/name
 with path.open('x') as stream:
  json.dump(value,stream,indent=2);stream.flush();os.fsync(stream.fileno())
 fd=os.open(R,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 return ref(path)

def call(host,args,body=None):
 p=subprocess.run(SSH+['james@'+IPS[host],shlex.join(args)],input=body,capture_output=True,timeout=55)
 assert p.returncode==0 and len(p.stdout)<16*1024**2,'Bounded cluster observation/request failed'
 return json.loads(p.stdout)

def kube(args,body=None):return call('masternode',['kubectl']+args,body)
def all_lh(kind):return kube(['-n','longhorn-system','get',kind,'-o','json'])['items']
def ready(conditions,kind):return any(c['type']==kind and c['status']=='True' for c in conditions)

def no_upgrade():
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or p.name==str(os.getpid()):continue
  try:text=(p/'cmdline').read_bytes()
  except (FileNotFoundError,ProcessLookupError):continue
  assert not any(v in text for v in (b'run-kubernetes-security-patch.py',b'kubernetes-security-patch.yml')),'Concurrent native upgrade consumer; no storage mutation'

def disk(host,directory=None):
 # Directory observation uses metadata only, no content reads or deletes.
 code="""import os,json,stat
from pathlib import Path
p=Path('/');s=os.statvfs(p)
r={'capacity':s.f_blocks*s.f_frsize,'free':s.f_bfree*s.f_frsize,'usable':s.f_bavail*s.f_frsize}
import subprocess
r['rootFSUUID']=subprocess.check_output(['findmnt','-n','-o','UUID','/'],text=True).strip()
directory=REPLICA_PATH
if directory:
 p=Path(directory);parent=p.parent
 assert parent==Path('/var/lib/longhorn/replicas') and parent.resolve()==parent
 names={x.name for x in parent.iterdir()}
 r['replicaPath']=directory;r['exists']=p.name in names
 if r['exists']:
  root=p.lstat();assert stat.S_ISDIR(root.st_mode) and not p.is_symlink()
  seen=set();total=0
  def failed(error):raise error
  for base,dirs,files in os.walk(p,followlinks=False,onerror=failed):
   for q in [Path(base),*(Path(base)/x for x in files)]:
    st=q.lstat();assert not q.is_symlink() and st.st_dev==root.st_dev and (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode))
    if (st.st_dev,st.st_ino) not in seen:total+=st.st_blocks*512;seen.add((st.st_dev,st.st_ino))
   assert all(not (Path(base)/x).is_symlink() for x in dirs)
  end=p.lstat();assert (root.st_dev,root.st_ino)==(end.st_dev,end.st_ino)
  r['directory']={'device':root.st_dev,'inode':root.st_ino,'uid':root.st_uid,'gid':root.st_gid,'allocatedBytes':total}
print(json.dumps(r))
""".replace('REPLICA_PATH',repr(directory))
 # Only replica-directory metadata needs privilege. No contents are read or
 # deleted; consume the protected credential before any child process starts.
 return call(host,['sudo','-k','-S','-p','','python3','-B','-c',code],PASSWORD+b'\n')

def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def observe(plan,baseline=None,allow_pending=False):
 no_upgrade()
 assert kube(['version','-o','json'])['serverVersion']['gitVersion'] in ('v1.37.1','v1.37.2'),'Only the original or authorized patched API is admitted'
 volume=kube(['-n','longhorn-system','get','volumes.longhorn.io',V,'-o','json'])
 assert volume['metadata']['uid']==VU and not volume['metadata'].get('deletionTimestamp')
 spec=volume['spec'];assert spec['encrypted'] is True and spec['dataEngine']=='v1' and spec['dataLocality']=='disabled'
 assert not spec['nodeSelector'] and not spec['diskSelector'] and not spec.get('fromBackup') and not spec.get('cloneMode')
 assert spec['numberOfReplicas'] in (2,3) and spec['replicaAutoBalance'] in ('ignored','best-effort')
 all_replicas=all_lh('replicas.longhorn.io');replicas={x['metadata']['name']:x for x in all_replicas if x['spec']['volumeName']==V}
 assert 2<=len(replicas)<=3 and not any(x['spec'].get('evictionRequested') for x in replicas.values())
 assert not any(x['spec'].get('linkedCloneSrcReplicaName') in replicas for x in all_replicas)
 assert not any(x['metadata'].get('labels',{}).get('longhorn.io/linked-clone-src-replica') in replicas for x in all_replicas)
 engines=[x for x in all_lh('engines.longhorn.io') if x['spec']['volumeName']==V]
 assert len(engines)==1;engine=engines[0]
 assert engine['status']['currentState']=='running' and engine['spec']['nodeID']=='masternode'
 assert ':v1.13.0@sha256:' in engine['spec']['image'] and engine['status']['currentImage']==engine['spec']['image']
 assert not engine['status'].get('isExpanding') and not any(x.get('isRestoring') for x in (engine['status'].get('restoreStatus') or {}).values())
 modes=engine['status'].get('replicaModeMap',{})
 rw={name for name,r in replicas.items() if modes.get(name)=='RW' and r['status']['currentState']=='running' and r['spec'].get('active') and r['spec'].get('healthyAt') and not r['spec'].get('failedAt') and not r['metadata'].get('deletionTimestamp')}
 assert len(rw)>=2 and MASTER in rw and replicas[MASTER]['metadata']['uid']==UIDS[MASTER]
 for name in rw:
  assert engine['spec']['replicaAddressMap'].get(name)==engine['status']['currentReplicaAddressMap'].get(name) and engine['spec']['replicaAddressMap'].get(name)
 if OLD in replicas:assert replicas[OLD]['metadata']['uid']==UIDS[OLD]
 assert replicas[MASTER]['spec']['nodeID']=='masternode'
 assert all(name in (MASTER,OLD) or r['spec']['nodeID'] in ('','workernode1') for name,r in replicas.items())
 nodes={x['metadata']['name']:x for x in kube(['get','nodes','-o','json'])['items']}
 assert {k:v['metadata']['uid'] for k,v in nodes.items()}==plan['nodeUIDs']
 assert all(not n['spec'].get('unschedulable',False) and ready(n['status']['conditions'],'Ready') for n in nodes.values())
 lh={x['metadata']['name']:x for x in all_lh('nodes.longhorn.io')}
 assert set(lh)==set(IPS)
 for node in lh.values():
  assert node['spec']['allowScheduling'] and not node['spec'].get('evictionRequested') and ready(node['status']['conditions'],'Ready')
  assert len(node['spec']['disks'])==1
  for name,d in node['spec']['disks'].items():
   status=node['status']['diskStatus'][name]
   assert d['allowScheduling'] and not d['evictionRequested'] and ready(status['conditions'],'Ready') and ready(status['conditions'],'Schedulable')
 settings={x['metadata']['name']:{'uid':x['metadata']['uid'],'value':x['value']} for x in all_lh('settings.longhorn.io')}
 assert settings['replica-auto-balance']['value']=='disabled' and settings['replica-soft-anti-affinity']['value']=='false'
 assert settings['storage-minimal-available-percentage']['value']=='25' and spec['replicaSoftAntiAffinity']=='ignored'
 managers={x['metadata']['name']:x for x in all_lh('instancemanagers.longhorn.io')}
 for name in rw:assert managers[replicas[name]['status']['instanceManagerName']]['status']['currentState']=='running'
 for host in IPS:assert any(m['spec']['nodeID']==host and m['status']['currentState']=='running' for m in managers.values())
 assert len({r['spec']['nodeID'] for r in replicas.values() if r['spec']['nodeID']})==len([r for r in replicas.values() if r['spec']['nodeID']])
 original=baseline['volumeSpec'] if baseline else copy.deepcopy(spec)
 for key in ('numberOfReplicas','replicaAutoBalance'):assert original[key] in (2,'ignored')
 normalized=copy.deepcopy(spec);normalized.update(numberOfReplicas=2,replicaAutoBalance='ignored');assert normalized==original
 repo=Path(__file__).resolve().parents[2];roles=repo/'k8s-rewrite/ansible-playbook/roles'
 guard=module('qbit_current58',roles/'security_maintenance/files/kernel_checkpoint.py')
 proxy=module('qbit_proxy',roles/'kubernetes_security_patch/files/checkpoint.py')
 guard_sources={'checkpoint':sha(Path(guard.__file__)),'proxyNormalizer':sha(Path(proxy.__file__))}
 if baseline:assert guard_sources==baseline['guardSources']
 actual_project=guard.project
 def project(items):
  items=proxy.normalize_proxy(items,plan)
  for item in items:
   if item['kind']=='Volume' and item['metadata']['name']==V:
    assert item['metadata']['uid']==VU
    item['spec']=copy.deepcopy(original)
    if item['status']['robustness']!='healthy':
     assert allow_pending and item['status']['robustness']=='degraded' and MASTER in rw and (OLD in rw or any(replicas[n]['spec']['nodeID']=='workernode1' for n in rw))
     item['status']['robustness']='healthy'
  return actual_project(items)
 guard.project=project
 argv=sys.argv
 try:
  sys.argv=['kernel_checkpoint.py','--manifest',plan['checkpoint']['path'],'--sha256',plan['checkpoint']['sha256']]
  with contextlib.redirect_stdout(io.StringIO()):guard.main()
 finally:sys.argv=argv
 if baseline:
  assert settings==baseline['settings'] and {k:{'uid':v['metadata']['uid'],'spec':v['spec']} for k,v in lh.items()}==baseline['longhornNodeSpecs']
  assert engine['metadata']['uid']==baseline['engineUID'] and engine['spec']['image']==baseline['engineImage']
 path=(baseline or {}).get('oldDirectory')
 if not path:
  old=replicas[OLD];assert old['spec']['diskPath']=='/var/lib/longhorn/'
  path='/var/lib/longhorn/replicas/'+old['spec']['dataDirectoryName']
  assert old['spec']['dataDirectoryName'].startswith(V+'-') and '/' not in old['spec']['dataDirectoryName']
 disks={host:disk(host,path if host=='workernode2' else None) for host in IPS}
 assert all(d['rootFSUUID'] and d['usable']>=15*1024**3 and d['free']>=d['capacity']//4+1+512*1024**2 for d in disks.values()),'Original filesystem floors remain mandatory'
 if baseline:assert {host:d['rootFSUUID'] for host,d in disks.items()}==baseline['rootFSUUIDs']
 return {'capturedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'volume':volume,'replicas':replicas,'rw':sorted(rw),'engine':engine,'nodes':nodes,'longhornNodes':lh,'settings':settings,'disks':disks,'oldDirectory':path,'guardSources':guard_sources}

def destination_budget(state):
 d=state['disks']['workernode1'];copy_budget=max(2*1024**3,int(state['volume']['spec']['size']),int(state['volume']['status']['actualSize']))
 assert d['usable']-copy_budget>=15*1024**3
 assert d['free']-copy_budget>=d['capacity']//4+1+512*1024**2+2*1024**3
 node=state['longhornNodes']['workernode1'];name=next(iter(node['spec']['disks']));spec=node['spec']['disks'][name];status=node['status']['diskStatus'][name]
 assert status['storageAvailable']-copy_budget>status['storageMaximum']//4
 limit=(status['storageMaximum']-spec['storageReserved'])*int(state['settings']['storage-over-provisioning-percentage']['value'])//100
 assert status['storageScheduled']+int(state['volume']['spec']['size'])<=limit

def cleanup_choice(state):
 # Match cleanup precedence before relying on raw-space ordering. No time
 # passage alone resets the unstable heuristic; compare actual Ready times.
 replicas=state['replicas'];assert all(not r['spec'].get('evictionRequested') for r in replicas.values())
 times=[]
 for host in {r['spec']['nodeID'] for r in replicas.values() if r['spec']['nodeID']}:
  condition=next(c for c in state['nodes'][host]['status']['conditions'] if c['type']=='Ready')
  times.append((dt.datetime.fromisoformat(condition['lastTransitionTime'].replace('Z','+00:00')),host))
 times.sort();latest,second=times[-1],times[-2]
 if (latest[0]-second[0]).total_seconds()>1800:
  for name,r in replicas.items():
   if r['spec']['nodeID']==latest[1]:
    healthy=dt.datetime.fromisoformat(r['spec']['healthyAt'].replace('Z','+00:00'))
    assert healthy>=latest[0],'Unstable-node cleanup would precede free-space choice'
 assert len({n['status'].get('zone','') for n in state['longhornNodes'].values()})==1
 available={host:next(iter(node['status']['diskStatus'].values()))['storageAvailable'] for host,node in state['longhornNodes'].items()}
 assert all(len(str(v))==11 for v in available.values())
 assert available['workernode2']<available['masternode']<available['workernode1']
 assert state['disks']['workernode2']['free']<state['disks']['masternode']['free']<state['disks']['workernode1']['free']
 return available

def main():
 global PASSWORD
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('phase',choices=['qualify','add-third','observe-third','reduce','observe-two','restore'])
 parser.add_argument('--authority',type=Path,required=True);parser.add_argument('--authority-sha256',required=True)
 args=parser.parse_args();os.umask(0o077);assert F.is_mount() and os.getuid()==1000
 PASSWORD=sys.stdin.buffer.readline(130).removesuffix(b'\n')
 assert 0<len(PASSWORD)<=128 and not any(x in PASSWORD for x in (b'\r',b'\n',b'\0'))
 authority_ref={'path':str(args.authority),'sha256':args.authority_sha256};plan=load(authority_ref)
 baseline=None
 if args.phase!='qualify':
  assert R.resolve()==R and R.stat().st_uid==1000 and not R.stat().st_mode&0o077
  owner=json.loads((R/'ownership.json').read_text());assert owner['sourceSHA256']==sha(Path(__file__).resolve()) and owner['authority']==authority_ref
  baseline=load(owner['baseline'])
 state=observe(plan,baseline,allow_pending=args.phase.startswith('observe'))
 if args.phase=='qualify':
  assert not R.exists() and set(state['replicas'])==set(UIDS) and set(state['rw'])==set(UIDS)
  assert state['volume']['spec']['numberOfReplicas']==2 and state['volume']['spec']['replicaAutoBalance']=='ignored'
  destination_budget(state);cleanup_choice(state)
  assert state['disks']['workernode2']['exists']
  R.mkdir(mode=0o700)
  baseline={'volumeSpec':state['volume']['spec'],'volumeUID':VU,'engineUID':state['engine']['metadata']['uid'],'engineImage':state['engine']['spec']['image'],
   'settings':state['settings'],'longhornNodeSpecs':{k:{'uid':v['metadata']['uid'],'spec':v['spec']} for k,v in state['longhornNodes'].items()},
   'rootFSUUIDs':{host:d['rootFSUUID'] for host,d in state['disks'].items()},'oldDirectory':state['oldDirectory'],'oldDirectoryIdentity':state['disks']['workernode2']['directory'],
   'originalReplicaUIDs':UIDS,'qualification':state,'guardSources':state['guardSources']}
  baseline_ref=save('qualification.json',baseline)
  save('ownership.json',{'owner':'qbit-three-copy-headroom','root':str(R),'physicalVolume':str(F),'sourceSHA256':sha(Path(__file__).resolve()),'authority':authority_ref,'baseline':baseline_ref,
   'regeneration':'Read-only qualification snapshots; mutation intents never replayed','protected':'All original data, replicas, failure witnesses and source; no raw file/replica deletion','lastConsumer':'Exact original volume spec restoration after native two-copy completion'})
  print(json.dumps({'qualified':True,'receipt':baseline_ref}));return
 phase=args.phase;spec=state['volume']['spec'];replicas=state['replicas'];rw=set(state['rw'])
 new=[name for name,r in replicas.items() if r['spec']['nodeID']=='workernode1']
 third=(len(new)==1 and set(replicas)=={MASTER,OLD,new[0]} and rw==set(replicas) and state['volume']['status']['robustness']=='healthy' and not state['engine']['status'].get('rebuildStatus'))
 two=(len(new)==1 and set(replicas)=={MASTER,new[0]} and rw==set(replicas) and state['volume']['status']['robustness']=='healthy' and not state['disks']['workernode2']['exists'])
 if phase.startswith('observe'):
  action='add-third' if phase=='observe-third' else 'reduce';intent=R/(action+'-intent.json')
  assert intent.is_file();frozen=json.loads(intent.read_text());assert frozen['volumeUID']==VU
  complete=third if phase=='observe-third' else two
  restored=(phase=='observe-two' and (R/'restore-intent.json').is_file() and spec==baseline['volumeSpec'])
  assert spec['numberOfReplicas']==(3 if phase=='observe-third' else 2) and (spec['replicaAutoBalance']=='best-effort' or restored)
  if complete:
   name=phase+'-completed.json'
   if not (R/name).exists():save(name,{'completed':True,'intent':ref(intent),'newReplica':{'name':new[0],'uid':replicas[new[0]]['metadata']['uid']},'observation':state})
   if restored and not (R/'completed.json').exists():
    save('completed.json',{'completed':True,'originalVolumeSpecRestored':True,'nativeOldReplicaRemoved':True,'restorationObservedAfterLostReply':True,
     'restoreIntent':ref(R/'restore-intent.json'),'oldAllocatedBytesObservedBefore':baseline['oldDirectoryIdentity']['allocatedBytes'],
     'actualNodeFilesystems':state['disks'],'rawDeletesPerformed':False,'oldFailedWitnessesTouched':False,'WindowsRecoveryClaimed':False})
  print(json.dumps({'completed':complete,'phase':phase,'runningRW':state['rw'],'originalWorker2DirectoryAbsent':not state['disks']['workernode2']['exists']}));return
 assert state['volume']['status']['robustness']=='healthy'
 if phase=='add-third':
  assert spec==baseline['volumeSpec'] and set(replicas)==set(UIDS) and rw==set(UIDS)
  destination_budget(state);cleanup_choice(state)
  original=state['disks']['workernode2']['directory'];assert all(original[k]==baseline['oldDirectoryIdentity'][k] for k in ('device','inode','uid','gid'))
  replacements={'numberOfReplicas':3,'replicaAutoBalance':'best-effort'}
 elif phase=='reduce':
  assert third and (R/'observe-third-completed.json').is_file()
  proof=json.loads((R/'observe-third-completed.json').read_text());assert proof['newReplica']=={'name':new[0],'uid':replicas[new[0]]['metadata']['uid']}
  assert spec['numberOfReplicas']==3 and spec['replicaAutoBalance']=='best-effort'
  cleanup_choice(state);destination_budget(state)
  replacements={'numberOfReplicas':2}
 else:
  assert phase=='restore' and two and (R/'observe-two-completed.json').is_file()
  proof=json.loads((R/'observe-two-completed.json').read_text());assert proof['newReplica']=={'name':new[0],'uid':replicas[new[0]]['metadata']['uid']}
  assert spec['numberOfReplicas']==2 and spec['replicaAutoBalance']=='best-effort'
  replacements={'replicaAutoBalance':'ignored'}
 # No durable mutation intent exists for any earlier read-only refusal.
 assert not (R/(phase+'-intent.json')).exists(),'Existing operation intent cannot be replayed'
 no_upgrade()
 current=kube(['-n','longhorn-system','get','volumes.longhorn.io',V,'-o','json'])
 assert current['metadata']['uid']==VU and current['spec']==spec and current['status']['robustness']=='healthy'
 state['volume']=current
 before_ref=save(phase+'-before.json',state)
 patches=[{'op':'test','path':'/metadata/uid','value':VU},{'op':'test','path':'/metadata/resourceVersion','value':state['volume']['metadata']['resourceVersion']},{'op':'test','path':'/spec','value':spec}]
 patches += [{'op':'replace','path':'/spec/'+key,'value':value} for key,value in replacements.items()]
 save(phase+'-intent.json',{'volumeUID':VU,'before':before_ref,'patch':patches,'originalSpecSHA256':hashlib.sha256(json.dumps(baseline['volumeSpec'],sort_keys=True,separators=(',',':')).encode()).hexdigest()})
 after=kube(['-n','longhorn-system','patch','volumes.longhorn.io',V,'--type=json','-p',json.dumps(patches),'-o','json'])
 expected=copy.deepcopy(spec);expected.update(replacements)
 assert after['metadata']['uid']==VU and after['spec']==expected
 save(phase+'-after.json',{'volumeUID':VU,'spec':after['spec'],'resourceVersion':after['metadata']['resourceVersion'],'requestAccepted':True})
 if phase=='restore':
  final=observe(plan,baseline);assert final['volume']['spec']==baseline['volumeSpec']
  assert set(final['rw'])=={MASTER,new[0]} and not final['disks']['workernode2']['exists']
  save('completed.json',{'completed':True,'originalVolumeSpecRestored':True,'nativeOldReplicaRemoved':True,'oldAllocatedBytesObservedBefore':baseline['oldDirectoryIdentity']['allocatedBytes'],
   'actualNodeFilesystems':final['disks'],'rawDeletesPerformed':False,'oldFailedWitnessesTouched':False,'WindowsRecoveryClaimed':False})
 print(json.dumps({'phase':phase,'requestAccepted':True,'nextObservationRequired':phase!='restore'}))

if __name__=='__main__':main()
