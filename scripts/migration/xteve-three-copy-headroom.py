"""Fixed xteve native three-copy rebalance after completed Kubernetes maintenance."""
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
# Fixed reviewed profile. The completed qbit source and receipts remain immutable.
QBIT_SOURCE_SHA256='9d98338bd15de1cbe5fd3c88241affc1e893d9eff6ed944ef53d961bb7ceaf34'
V='pvc-d40f1490-7254-4599-be82-2fad35abb88b';VU='bc2fc045-62a2-4266-a237-c9d37642acb2'
HOLD_NODE='workernode1';DEST_NODE='masternode';OLD_NODE='workernode2'
HOLD=V+'-r-27d468d0';OLD=V+'-r-10300ab4'
UIDS={HOLD:'a5bfe7c3-9f81-471d-a4d0-7b378eae6f62',OLD:'c1f392d6-a55e-494b-8b8f-7b8b061d13d8'}
ENGINE_UID='2a23f930-0bf2-4221-87d7-7458c079f10e'
def record(name):
 assert '/' not in name and name not in ('.','..')
 return R/('xteve-'+name)
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
 path=record(name)
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
 assert kube(['version','-o','json'])['serverVersion']['gitVersion'] =='v1.37.2','Second rebalance requires the completed patched API'
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
 assert engine['status']['currentState']=='running' and engine['spec']['nodeID'] in IPS and engine['metadata']['uid']==ENGINE_UID
 assert ':v1.13.0@sha256:' in engine['spec']['image'] and engine['status']['currentImage']==engine['spec']['image']
 assert not engine['status'].get('isExpanding') and not any(x.get('isRestoring') for x in (engine['status'].get('restoreStatus') or {}).values())
 modes=engine['status'].get('replicaModeMap',{})
 rw={name for name,r in replicas.items() if modes.get(name)=='RW' and r['status']['currentState']=='running' and r['spec'].get('active') and r['spec'].get('healthyAt') and not r['spec'].get('failedAt') and not r['metadata'].get('deletionTimestamp')}
 assert len(rw)>=2 and HOLD in rw and replicas[HOLD]['metadata']['uid']==UIDS[HOLD]
 for name in rw:
  assert engine['spec']['replicaAddressMap'].get(name)==engine['status']['currentReplicaAddressMap'].get(name) and engine['spec']['replicaAddressMap'].get(name)
 if OLD in replicas:assert replicas[OLD]['metadata']['uid']==UIDS[OLD] and replicas[OLD]['spec']['nodeID']==OLD_NODE
 assert replicas[HOLD]['spec']['nodeID']==HOLD_NODE
 assert all(name in (HOLD,OLD) or r['spec']['nodeID'] in ('',DEST_NODE) for name,r in replicas.items())
 nodes={x['metadata']['name']:x for x in kube(['get','nodes','-o','json'])['items']}
 assert {k:v['metadata']['uid'] for k,v in nodes.items()}==plan['nodeUIDs']
 assert all(n['status']['nodeInfo']['kubeletVersion']=='v1.37.2' and n['status']['nodeInfo']['containerRuntimeVersion']=='containerd://2.4.2' for n in nodes.values())
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
 guard=module('xteve_current58',roles/'security_maintenance/files/kernel_checkpoint.py')
 proxy=module('xteve_proxy',roles/'kubernetes_security_patch/files/checkpoint.py')
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
     assert allow_pending and item['status']['robustness']=='degraded' and HOLD in rw and (OLD in rw or any(replicas[n]['spec']['nodeID']==DEST_NODE for n in rw))
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
  assert engine['metadata']['uid']==baseline['engineUID'] and engine['spec']['image']==baseline['engineImage'] and engine['spec']['nodeID']==baseline['engineNode']
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
 d=state['disks'][DEST_NODE];copy_budget=max(2*1024**3,int(state['volume']['spec']['size']),int(state['volume']['status']['actualSize']))
 assert d['usable']-copy_budget>=15*1024**3
 assert d['free']-copy_budget>=d['capacity']//4+1+512*1024**2
 node=state['longhornNodes'][DEST_NODE];name=next(iter(node['spec']['disks']));spec=node['spec']['disks'][name];status=node['status']['diskStatus'][name]
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

def terminal(success_ref,authority_ref):
 result=load(success_ref);settings=result['settings']
 assert result['exitCode']==0 and result.get('finishedUTC') and settings['kubernetes_security_patch_apply'] is True
 assert {'path':settings['kubernetes_security_patch_manifest'],'sha256':settings['kubernetes_security_patch_manifest_sha256']}==authority_ref
 receipt_dir=Path(settings['kubernetes_security_patch_receipt_dir'])
 assert receipt_dir.resolve()==receipt_dir and H in receipt_dir.parents and receipt_dir.is_dir()
 completed=[load(ref(p)) for p in receipt_dir.glob('*.completed.json')]
 assert len(completed)==3 and {x['node'] for x in completed}==set(IPS)
 assert all(x['completed'] is True and x['nativeLastConsumerCompleted'] is True and x['authoritySHA256']==authority_ref['sha256'] for x in completed)

def final_margin(state,baseline,projected):
 # Before count reduction the third copy is already physically present.
 # Only the departing source may rely on its identity-bound allocated bytes.
 for host,d in state['disks'].items():
  recovery=0
  if projected and host==OLD_NODE:
   old=d['directory'];original=baseline['oldDirectoryIdentity']
   assert all(old[k]==original[k] for k in ('device','inode','uid','gid'))
   recovery=min(old['allocatedBytes'],original['allocatedBytes'])
  assert d['free']+recovery>=d['capacity']//4+1+512*1024**2+2*1024**3,'Final two-GiB margin is not proven'
  assert d['usable']>=15*1024**3

def main():
 global PASSWORD
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('phase',choices=['qualify','add-third','observe-third','reduce','observe-two','restore'])
 parser.add_argument('--kubernetes-success',type=Path,required=True);parser.add_argument('--kubernetes-success-sha256',required=True)
 parser.add_argument('--authority',type=Path,required=True);parser.add_argument('--authority-sha256',required=True)
 args=parser.parse_args();os.umask(0o077);assert F.is_mount() and os.getuid()==1000
 PASSWORD=sys.stdin.buffer.readline(130).removesuffix(b'\n')
 assert 0<len(PASSWORD)<=128 and not any(x in PASSWORD for x in (b'\r',b'\n',b'\0'))
 os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD',None)
 authority_ref={'path':str(args.authority),'sha256':args.authority_sha256};plan=load(authority_ref)
 success_ref={'path':str(args.kubernetes_success),'sha256':args.kubernetes_success_sha256}
 terminal(success_ref,authority_ref)
 qbit_ref=ref(R/'completed.json');qbit=load(qbit_ref)
 assert qbit['completed'] is True and qbit['originalVolumeSpecRestored'] is True and qbit['nativeOldReplicaRemoved'] is True
 assert sha(Path(__file__).with_name('qbit-three-copy-headroom.py'))==QBIT_SOURCE_SHA256
 baseline=None
 if args.phase!='qualify':
  assert R.resolve()==R and R.stat().st_uid==1000 and not R.stat().st_mode&0o077
  owner=json.loads((record('ownership.json')).read_text());assert owner['sourceSHA256']==sha(Path(__file__).resolve()) and owner['authority']==authority_ref
  assert owner['kubernetesSuccess']==success_ref and owner['qbitCompletion']==qbit_ref
  baseline=load(owner['baseline'])
 state=observe(plan,baseline,allow_pending=args.phase.startswith('observe'))
 if args.phase=='qualify':
  assert R.is_dir() and not record('ownership.json').exists() and set(state['replicas'])==set(UIDS) and set(state['rw'])==set(UIDS)
  assert state['volume']['spec']['numberOfReplicas']==2 and state['volume']['spec']['replicaAutoBalance']=='ignored'
  destination_budget(state);cleanup_choice(state)
  assert state['disks']['workernode2']['exists']
  assert R.resolve()==R and R.stat().st_uid==1000 and not R.stat().st_mode&0o077
  baseline={'volumeSpec':state['volume']['spec'],'volumeUID':VU,'engineUID':state['engine']['metadata']['uid'],'engineImage':state['engine']['spec']['image'],'engineNode':state['engine']['spec']['nodeID'],
   'settings':state['settings'],'longhornNodeSpecs':{k:{'uid':v['metadata']['uid'],'spec':v['spec']} for k,v in state['longhornNodes'].items()},
   'rootFSUUIDs':{host:d['rootFSUUID'] for host,d in state['disks'].items()},'oldDirectory':state['oldDirectory'],'oldDirectoryIdentity':state['disks']['workernode2']['directory'],
   'originalReplicaUIDs':UIDS,'qualification':state,'guardSources':state['guardSources']}
  baseline_ref=save('qualification.json',baseline)
  save('ownership.json',{'owner':'xteve-three-copy-headroom','root':str(R),'physicalVolume':str(F),'sourceSHA256':sha(Path(__file__).resolve()),'authority':authority_ref,'baseline':baseline_ref,'kubernetesSuccess':success_ref,'qbitCompletion':qbit_ref,'qbitSourceSHA256':QBIT_SOURCE_SHA256,
   'regeneration':'Read-only qualification snapshots; mutation intents never replayed','protected':'All original data, replicas, failure witnesses and source; no raw file/replica deletion','lastConsumer':'Exact original volume spec restoration after native two-copy completion'})
  print(json.dumps({'qualified':True,'receipt':baseline_ref}));return
 phase=args.phase;spec=state['volume']['spec'];replicas=state['replicas'];rw=set(state['rw'])
 new=[name for name,r in replicas.items() if r['spec']['nodeID']==DEST_NODE]
 third=(len(new)==1 and set(replicas)=={HOLD,OLD,new[0]} and rw==set(replicas) and state['volume']['status']['robustness']=='healthy' and not state['engine']['status'].get('rebuildStatus'))
 two=(len(new)==1 and set(replicas)=={HOLD,new[0]} and rw==set(replicas) and state['volume']['status']['robustness']=='healthy' and not state['disks']['workernode2']['exists'])
 if phase.startswith('observe'):
  action='add-third' if phase=='observe-third' else 'reduce';intent=record(action+'-intent.json')
  assert intent.is_file();frozen=json.loads(intent.read_text());assert frozen['volumeUID']==VU
  complete=third if phase=='observe-third' else two
  restored=(phase=='observe-two' and (record('restore-intent.json')).is_file() and spec==baseline['volumeSpec'])
  assert spec['numberOfReplicas']==(3 if phase=='observe-third' else 2) and (spec['replicaAutoBalance']=='best-effort' or restored)
  if complete and phase=='observe-two':final_margin(state,baseline,projected=False)
  if complete:
   name=phase+'-completed.json'
   if not record(name).exists():save(name,{'completed':True,'intent':ref(intent),'newReplica':{'name':new[0],'uid':replicas[new[0]]['metadata']['uid']},'observation':state})
   if restored and not (record('completed.json')).exists():
    save('completed.json',{'completed':True,'originalVolumeSpecRestored':True,'nativeOldReplicaRemoved':True,'restorationObservedAfterLostReply':True,
     'restoreIntent':ref(record('restore-intent.json')),'oldAllocatedBytesObservedBefore':baseline['oldDirectoryIdentity']['allocatedBytes'],
     'actualNodeFilesystems':state['disks'],'rawDeletesPerformed':False,'oldFailedWitnessesTouched':False,'WindowsRecoveryClaimed':False})
  print(json.dumps({'completed':complete,'phase':phase,'runningRW':state['rw'],'originalWorker2DirectoryAbsent':not state['disks']['workernode2']['exists']}));return
 assert state['volume']['status']['robustness']=='healthy'
 if phase=='add-third':
  assert spec==baseline['volumeSpec'] and set(replicas)==set(UIDS) and rw==set(UIDS)
  destination_budget(state);cleanup_choice(state)
  original=state['disks']['workernode2']['directory'];assert all(original[k]==baseline['oldDirectoryIdentity'][k] for k in ('device','inode','uid','gid'))
  replacements={'numberOfReplicas':3,'replicaAutoBalance':'best-effort'}
 elif phase=='reduce':
  assert third and (record('observe-third-completed.json')).is_file()
  proof=json.loads((record('observe-third-completed.json')).read_text());assert proof['newReplica']=={'name':new[0],'uid':replicas[new[0]]['metadata']['uid']}
  assert spec['numberOfReplicas']==3 and spec['replicaAutoBalance']=='best-effort'
  cleanup_choice(state);final_margin(state,baseline,projected=True)
  replacements={'numberOfReplicas':2}
 else:
  assert phase=='restore' and two and (record('observe-two-completed.json')).is_file()
  proof=json.loads((record('observe-two-completed.json')).read_text());assert proof['newReplica']=={'name':new[0],'uid':replicas[new[0]]['metadata']['uid']}
  assert spec['numberOfReplicas']==2 and spec['replicaAutoBalance']=='best-effort'
  final_margin(state,baseline,projected=False)
  replacements={'replicaAutoBalance':'ignored'}
 # No durable mutation intent exists for any earlier read-only refusal.
 assert not (record(phase+'-intent.json')).exists(),'Existing operation intent cannot be replayed'
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
  final_margin(final,baseline,projected=False)
  assert set(final['rw'])=={HOLD,new[0]} and not final['disks']['workernode2']['exists']
  save('completed.json',{'completed':True,'originalVolumeSpecRestored':True,'nativeOldReplicaRemoved':True,'oldAllocatedBytesObservedBefore':baseline['oldDirectoryIdentity']['allocatedBytes'],
   'actualNodeFilesystems':final['disks'],'rawDeletesPerformed':False,'oldFailedWitnessesTouched':False,'WindowsRecoveryClaimed':False})
 print(json.dumps({'phase':phase,'requestAccepted':True,'nextObservationRequired':phase!='restore'}))

if __name__=='__main__':main()
