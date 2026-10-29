"""Reclaim qualified caches of superseded apps and retired maintenance rebuilds.

Original images, OCI blobs, containers, leases, data and failed targets survive.
Uses the established physical mapping, regeneration and full reference guards.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shlex
import subprocess
import uuid

F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028'
NODES={'masternode':'192.168.0.4','workernode2':'192.168.0.5'}
# Explicit superseded upstream roots. Selection never includes the live image.
ROOTS={
 # Superseded CSI helper and application roots from the fresh native inventory.
 'sha256:a814aa4784197116983ea13e376fc691e000a390de9d0b9fca2bc4a2fb7c4a1f',
 'sha256:29f7cfd519008fe8f8dff5e79db43f70d65c43a89c08f1bafbb199ca90df79f0',
 'sha256:1bbb7b11d8087130e722e3249f364d0ab49ee3545e847c2f299e87b7e1ce5c4f',
 'sha256:d0cb76b565ba9d36da0dc2b38e2b6a49a0ae4fe067b03086110682f32c600318',
 'sha256:f9de845b170155199f2a2a3f9531cf13d78e31235e9db6b6582a8b0db0a50dad',
 'sha256:06da0d5b8908072f2e4522692aee8dc119fba7247a9658497e1153992cd777e9',
 'sha256:74ca61ab13e978f03cf0f336a607281d15f04cda0a38a881306365473b28a3d8',
 'sha256:406586865431b40b29353d899fb75a788f5384743f7f381444db5fe55d206914',
 # Superseded platform roots; live/desired graph ancestry is always excluded.
 'sha256:9b1b720b56df6612c9589cbc156acbca6419fa61de818d05db7226b0722f2868',
 'sha256:b255f3279dd9d830ea153e9369928646dee519fd853036388926dddb5c66094b',
 'sha256:83b79f57043fe1405e68bc0d4c7987accbc6bb512def3e0db12b31966c070801',
 'sha256:efaf47aeb4e8615e312f0880df860bf2e5b9fa53006fe075f057c6dd4089f47d',
 'sha256:03a3ce6673df6e948c261fe978a695adaa8fb190d68bfe5c358af8ee3d3fbef5',
 'sha256:c83ce5c06fed9ebb308cd5165bd144ee934c720f6b47e0da2180869092063c82',
 'sha256:840f318265ee26f0d2c48a158bf7896b22aa4e998e320a18646309f0e40b15da',
 # Retired pre-upstream maintenance rebuilds; preserve original OCI payloads.
 'sha256:1b3470b85eb38360c5b242f7cfbc7d45accc429704f725a8610137861db00397',
 'sha256:7bf03e8c4433460c0d93f789da56db457e3484412c448997102885af185db93c',
 'sha256:a3fc64d6777e22de915a97d3dbb77e1edc5d5998be683b4a1bed8968a26b2bb9',
 # Additional superseded image roots observed in the original native inventory.
 # Their original OCI graphs remain intact; all historical keys stay protected.
 'sha256:7885f2759c0da3c5f2c72b2e45ba4b602bdd7d6f04cc6abba201091f11c93a95',
 'sha256:36dab68a7e4b2750802e2326d9340201dc498ac429cbd89cdfb45cbab3fef081',
 'sha256:4ec141eeb0cb2f971d7c92f21cc40b0d2d50d7920eb7a0557443cca52270c0b0',
 'sha256:dec7a90bd0973b076832dc56933fe876bc014929e14b4ec49923951405370112',
 'sha256:a6e718e8f84d4e45282a53a8e7338ab74372abac3ff78f9261a015bc8b45be95',
 'sha256:570aeb63bdedcb5f9dd2500bd8f0a75581ba07c518c05cabbef0cfeb15451b3f',
 'sha256:29a981aec497ec47ccc25d67309c404593992a465501632e115010282ef61ec7',
 # Previous official Bazarr build, superseded by the qualified October28 build.
 'sha256:32204ef90d4dcb54ad5fb019810f4ef805ced9c54853ae552cf09a41c056b14b',
 'sha256:afd3fa2b229e3e6d4c8750618fe148af33a1f70b32af4441ecbd2d08f29d8221',
 'sha256:3ba09ac58f0b541aa7182feb9198b44d3c62158a7749ec00d26de1abad7ca8d7',
 'sha256:7962759d99d7e125e108e0f5e7f3cdbcd36161776d058d1d9b7153b92ef1af9e',
 'sha256:53a1b839ffa81f139e1552840772bff8a5d13f5c78a69cce22458b9a6cd0844d',
 'sha256:ca43905eaf2dd11425efdcfe184892e43806b1ae0a830440c825cecbc2629cfb',
 'sha256:fc0ae3c50f8128b97e84381903ec8d6845c3a569641cb7117c124376cccb57c1',
 'sha256:76414c033f290d3c9f1f9dfad71150abe71d92592369a3377a5903d579e6e2b2',
 'sha256:889dcc58c6aea859033985894b519b2e6b1e55d92527ed123f9f52e42ae7c97b',
 'sha256:b129cb0f674bd6d204e215bde2c2fc3f11d6ad0e82f6d20007cf80f74e1acbb1',
 'sha256:ee348529cea9601df86ad94d62a39cad26117e1eac9e82d8876aa0ec7fe1ba27',
 'sha256:c63aa057947400abded2583f7027d6ac1f8d70a8130401c36d5a244ef5999466',
 'sha256:6df1e795f17af43f082146e471113315487b5f0882f2ee7553d469034d929af1',
 'sha256:4bc6bc963e6d8443453676cae56536f4b8156d78bae03c0145cbe47c2aad73bb',
 'sha256:76f0358884cb92d9a086d24e5671c38048d3fef40f2588703d73eb55392d6b69',
 'sha256:7dcddc01f13bab2f15cde676d44d01f61fc9f99fe7785e86196dfc07d358ae2b',
}

def sha(raw):return hashlib.sha256(raw).hexdigest()
def save(path,value):
 with path.open('x') as out:json.dump(value,out,indent=2)

def current_image_inventory(repo):
 """Read image references during low-space remediation, without an upgrade.

 The engine-upgrade helper's payload-capacity precondition must still protect
 every upgrade/prestage consumer. It cannot precede a read-only cache inventory
 whose purpose is to restore that margin. This operation adds no node payload;
 native exclusive-cache, provenance and complete reference guards remain below.
 """
 lib=runpy.run_path(str(repo/'k8s-rewrite/ansible-playbook/roles/longhorn_engine_upgrade/files/upgrade.py'))
 get=lib['get'];settings={s['metadata']['name']:s.get('value') for s in get('settings.longhorn.io')}
 assert settings['storage-minimal-available-percentage']=='25' and settings['concurrent-automatic-engine-upgrade-per-node-limit']=='0'
 assert settings['current-longhorn-version']=='v1.13.0' and settings['default-engine-image']==lib['IMAGE']
 nodes=get('nodes',namespace=None);assert {n['metadata']['name'] for n in nodes}=={'masternode','workernode1','workernode2'}
 assert all(any(c['type']=='Ready' and c['status']=='True' for c in n['status']['conditions']) and not any(c['type'].endswith('Pressure') and c['status']=='True' for c in n['status']['conditions']) for n in nodes)
 engine=[v for v in get('engineimages.longhorn.io') if v['spec']['image']==lib['IMAGE']]
 assert len(engine)==1 and engine[0]['status']['state']=='deployed' and set(engine[0]['status']['nodeDeploymentMap'])=={n['metadata']['name'] for n in nodes} and all(engine[0]['status']['nodeDeploymentMap'].values())
 volumes=get('volumes.longhorn.io');assert len(volumes)==44 and all(v['spec']['encrypted'] and v['spec']['numberOfReplicas']==2 for v in volumes)
 assert sum(v['status'].get('state')=='attached' and v['status'].get('robustness')=='healthy' for v in volumes)==28
 assert sum(v['status'].get('state')=='detached' for v in volumes)==16
 refs=set();roots={'sha256:a0225d1ea6631c8bc2385dc4c2faba17bbf1834ecf369e1659a9a382bd8d5dd7','sha256:a5b648c6c20d877cf90715415b1b31565dda9399020d80f186000fdd76474f86'}
 def take(spec):refs.update(c['image'] for c in spec.get('initContainers',[])+spec.get('containers',[]))
 for pod in get('pods',namespace=None):
  if pod['status'].get('phase') in ['Running','Pending'] and not pod['metadata'].get('deletionTimestamp'):
   take(pod['spec'])
   for c in pod['status'].get('containerStatuses',[])+pod['status'].get('initContainerStatuses',[]):
    digest=c.get('imageID','').split('@')[-1]
    if re.fullmatch('sha256:[0-9a-f]{64}',digest):roots.add(digest)
 for kind in ['deployments','statefulsets','daemonsets']:
  for obj in get(kind,namespace=None):
   if kind=='daemonsets' or obj['spec'].get('replicas',1)>0:take(obj['spec']['template']['spec'])
 for ref in refs:
  if '@' in ref:
   digest=ref.split('@')[-1];assert re.fullmatch('sha256:[0-9a-f]{64}',digest);roots.add(digest)
 return {'roots':sorted(roots),'references':sorted(refs)}


def kubernetes1371_profile(args, repo):
 """Explicit post-success cache scope; no image records or payloads retired."""
 assert args.kubernetes_success and re.fullmatch('[a-f0-9]{64}', args.kubernetes_success_sha256 or '')
 def owned(path):
  path=Path(path);assert path.is_absolute() and path.resolve()==path and path.is_relative_to(H) and path.is_file()
  return path
 success=owned(args.kubernetes_success);assert sha(success.read_bytes())==args.kubernetes_success_sha256
 terminal=json.loads(success.read_text());settings=terminal['settings']
 assert terminal['exitCode']==0 and terminal.get('finishedUTC') and settings['kubernetes_security_patch_apply'] is True
 native=owned(settings['kubernetes_security_patch_manifest']);assert sha(native.read_bytes())==settings['kubernetes_security_patch_manifest_sha256']
 plan=json.loads(native.read_text());recovery=Path(settings['kubernetes_security_patch_receipt_dir'])
 assert recovery.resolve()==recovery and recovery.is_relative_to(H) and recovery.is_dir()
 completed_paths=sorted(recovery.glob('*.completed.json'));completed=[json.loads(x.read_text()) for x in completed_paths]
 assert len(completed)==3 and {x['node'] for x in completed}=={'masternode','workernode1','workernode2'}
 assert all(x['completed'] is True and x['nativeLastConsumerCompleted'] is True and x['authoritySHA256']==settings['kubernetes_security_patch_manifest_sha256'] for x in completed)
 authority_path=owned(H/'kubernetes1371-superseded-cache-root-authority.json')
 assert sha(authority_path.read_bytes())=='7b7b4b897aed967857b60b551f0983d0c6c6b2311fb8f13c8d39650b6596e565'
 authority=json.loads(authority_path.read_text());assert set(authority['images'])=={'kube-apiserver','kube-controller-manager','kube-scheduler','kube-proxy'}
 roots=set()
 for name,row in authority['images'].items():
  index=row['index'];manifest=row['amd64']
  assert index['url']=='https://registry.k8s.io/v2/'+name+'/manifests/v1.37.1'
  assert index['digest']=='sha256:'+index['responseSHA256'] and manifest['digest']=='sha256:'+manifest['responseSHA256']
  members=[x for x in index['json']['manifests'] if x.get('platform',{}).get('architecture')=='amd64' and x.get('platform',{}).get('os')=='linux']
  assert len(members)==1 and members[0]['digest']==manifest['digest']
  assert manifest['url']=='https://registry.k8s.io/v2/'+name+'/manifests/'+manifest['digest']
  roots.update([index['digest'],manifest['digest']])
 assert len(roots)==8
 lib=runpy.run_path(str(repo/'k8s-rewrite/ansible-playbook/roles/longhorn_engine_upgrade/files/upgrade.py'))
 nodes=lib['get']('nodes',namespace=None)
 assert {n['metadata']['name']:n['metadata']['uid'] for n in nodes}==plan['nodeUIDs']
 assert all(n['status']['nodeInfo']['kubeletVersion']=='v1.37.2' and n['status']['nodeInfo']['containerRuntimeVersion']=='containerd://2.4.2' and not n['spec'].get('unschedulable',False) and any(c['type']=='Ready' and c['status']=='True' for c in n['status']['conditions']) for n in nodes)
 response=lib['call'](['version','-o','json']);assert response.returncode==0
 assert json.loads(response.stdout)['serverVersion']['gitVersion']=='v1.37.2'
 return roots, {'name':'superseded-kubernetes1371','rootAuthoritySHA256':sha(authority_path.read_bytes()),'terminalSuccessPath':str(success),'terminalSuccessSHA256':sha(success.read_bytes()),'nativeAuthoritySHA256':sha(native.read_bytes()),'completedReceipts':{str(x):sha(x.read_bytes()) for x in completed_paths},'addedRoots':sorted(roots)}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('phase',choices=['inventory','qualify','retire'])
 p.add_argument('--node',choices=sorted(NODES),required=True)
 p.add_argument('--qualification',type=Path)
 p.add_argument('--superseded-kubernetes1371',action='store_true')
 p.add_argument('--kubernetes-success',type=Path)
 p.add_argument('--kubernetes-success-sha256')
 a=p.parse_args()
 assert os.geteuid()==1000 and F.is_mount() and H.is_dir()
 here=Path(__file__).resolve();repo=here.parents[5];libdir=here.parents[2]/'retired_native_unpack_cache/files'
 access=runpy.run_path(str(repo/'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'))
 supplied=os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD',None)
 password=supplied.encode() if supplied is not None else access['privilege_input']()
 assert password and len(password)<=128 and not any(x in password for x in (b'\n',b'\r',b'\0'))
 supplied=None
 sources={n:(libdir/n).read_bytes() for n in ('inventory.py','physical.py','retire.py')}
 # Immutable input authority is the original accepted maintenance checkpoint.
 expected={'inventory.py':'308b68818394da1af2617c807285f7b3fb76e47d9021443b448f2788c2f7e88b','physical.py':'7a7ad7477f2a769a9e0bcb8c330aeb50d019764674531edd1b8cfe5865265178','retire.py':'e5acdb14c459242a7089995f61dd769025a33b8491c7fb52615fd894ebe18725'}
 assert {k:sha(v) for k,v in sources.items()}==expected
 versions={n:runpy.run_path(str(libdir/n))['REMOTE'] for n in sources}
 profile={'name':'default'};extra=set()
 if a.superseded_kubernetes1371:extra,profile=kubernetes1371_profile(a,repo)
 else:assert a.kubernetes_success is None and a.kubernetes_success_sha256 is None
 current=current_image_inventory(repo)
 targets=(ROOTS|extra)-set(current['roots'])
 assert targets and not targets.intersection(current['roots'])
 inv=versions['inventory.py'];start=inv.index('targets={');end=inv.index('def cmd(',start)
 assert inv.count('assert targets<=set(image_rows)')==1
 inv=inv[:start]+'targets=set('+repr(sorted(targets))+')\n\n'+inv[end:]
 inv=inv.replace('assert targets<=set(image_rows)','targets &= set(image_rows);assert targets')
 # Every previously submitted key is permanently protected, including failures.
 history={};excluded=set()
 for parent in (F/'node-cleanup-20261027',F/'platform-upstream-review-20261027'):
  for path in parent.rglob('*.jsonl'):
   # Snapshot keys repeat across hosts. This leaf's journals are node-prefixed;
   # another node's successful operation must not change this node's binding.
   if path.parent==H and not path.name.startswith(a.node+'-'):continue
   if path.stat().st_size>8*1024**2:continue
   raw=path.read_bytes();found=False
   for line in raw.splitlines():
    try:row=json.loads(line)
    except (ValueError,UnicodeError):continue
    key=row.get('intent')
    if isinstance(key,str) and key.startswith('sha256:'):
     excluded.add(key);found=True
   if found:history[str(path.relative_to(F))]=sha(raw)
 marker='protected=ancestors(protected)'
 assert inv.count(marker)==1
 inv=inv.replace(marker,'protected.update('+repr(sorted(excluded))+');'+marker)
 inv=inv.replace('workernode2',a.node)
 physical=versions['physical.py'].replace('workernode2',a.node)
 remote=versions['retire.py'].replace('workernode2',a.node)
 guard=(F/'node-cleanup-20261027/master-generated-cleanup/reference-full-properties.py').read_bytes()
 assert sha(guard)=='3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87'
 packet={'inventorySource':base64.b64encode(inv.encode()).decode(),'inventorySHA256':sha(inv.encode()),
  'physicalSource':base64.b64encode(physical.encode()).decode(),'physicalSHA256':sha(physical.encode()),
  'guardSource':base64.b64encode(guard).decode(),'excludedPreviouslyAttemptedKeys':sorted(excluded),'priorOutputHashes':history}
 if a.phase=='inventory':program=inv
 else:
  program=remote;packet['mode']=a.phase
  if a.phase=='retire':
   assert a.qualification and a.qualification.resolve().parent==H
   q=json.loads(a.qualification.read_text());assert q['controllerSHA256']==sha(here.read_bytes()) and q['node']==a.node
   assert q.get('cacheProfile')==profile,'Qualification belongs to a different explicit cache profile or success authority'
   packet['qualification']=q
  else:assert a.qualification is None
 ident=uuid.uuid4().hex;prefix=a.node+'-'+a.phase+'-'+ident
 save(H/(prefix+'-ownership.json'),{'owner':'01a18518-24e7-7ce3-b620-f9ca775bfd1c','root':str(F),'node':a.node,'peakBytes':128*1024**2,'generatedPaths':[str(H/(prefix+'.jsonl')),str(H/(prefix+'.json'))],'authorityHashes':expected,'controllerSHA256':sha(here.read_bytes()),'programSHA256':sha(program.encode()),'regeneration':'Original hash-verified OCI blobs, exact uncompressed diffIDs and native offline unpack; no registry dependency','protected':'Every image/content/lease/container/data volume, non-target snapshot parent and all historical attempted keys','history':history,'cacheProfile':profile})
 try:
  out=H/(prefix+'.jsonl')
  with out.open('xb') as stream:
   child=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile=/home/brajam/.ssh/known_hosts','-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@'+NODES[a.node],shlex.join(['sudo','-S','-k','-p','','python3','-B','-c',program])],stdin=subprocess.PIPE,stdout=stream,stderr=subprocess.PIPE)
   _,errors=child.communicate(password+b'\n'+(json.dumps(packet).encode() if a.phase!='inventory' else b''),timeout=900)
  execution={'node':a.node,'phase':a.phase,'exitCode':child.returncode,'stdoutSHA256':sha(out.read_bytes()),'stderrSHA256':sha(errors),'stderr':errors.decode()[-2500:] if child.returncode else ''}
  save(H/(prefix+'-execution.json'),execution)
  assert child.returncode==0,execution
  value=json.loads(out.read_bytes().splitlines()[-1]);value.update(controllerSHA256=sha(here.read_bytes()),cacheProfile=profile)
  result=H/(prefix+'.json');save(result,value)
  print(json.dumps({'node':a.node,'phase':a.phase,'receipt':str(result),'status':value.get('status'),'candidateSnapshots':len(value.get('potentialExclusiveRetiredImageFilesystemCaches',value.get('profile',{}).get('mappedCandidates',[]))),'candidateBytes':value.get('potentialAllocatedBytes',value.get('profile',{}).get('actualCandidateAllocatedBytes')),'removedBytes':value.get('removedAllocatedLinuxBytes',0)}))
 finally:password=None

if __name__=='__main__':
 os.umask(0o077)
 main()
