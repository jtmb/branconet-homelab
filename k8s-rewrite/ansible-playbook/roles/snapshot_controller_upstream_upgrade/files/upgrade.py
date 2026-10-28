"""Opt-in existing-owner snapshot upgrade with encrypted recovery and live guards.

The inherited kubectl reader/HMAC primitives are hash-pinned. Native values stay
on the master; only metadata/HMACs and encrypted original definitions leave it.
"""
import argparse
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

import yaml

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
CORE_SHA = '19cbeccbaffd6dbc392042cce3279827cb5f43427f8c9eb00c2cac9d7efa193c'
AGE_SHA = 'eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c'
IMAGE = 'registry.k8s.io/sig-storage/snapshot-controller:v8.7.0@sha256:8511f417d0072efcd937aedd7cc79a937d5066e64ee17beb6097301c92742f19'
SUFFIX = r'''
def snapshot_state():
 out=[]
 for resource in ['volumesnapshotclasses.snapshot.storage.k8s.io','volumesnapshotcontents.snapshot.storage.k8s.io','volumesnapshots.snapshot.storage.k8s.io']:
  for x in get(resource):
   body=clean(x);ready=x.get('status',{}).get('readyToUse')
   if x['kind']!='VolumeSnapshotClass':assert ready is True,'existing_snapshot_not_ready'
   out.append({'id':ident(x),'uid':x['metadata']['uid'],'definitionHMAC':mac(body),'readyToUse':ready})
 return sorted(out,key=lambda x:x['id'])
def snapshot_protected():
 state,ready=protected();state['originalSnapshots']=snapshot_state();return state,ready
vendor=r['vendor'];desired={};old={};new=[];crd_versions=[]
for v in vendor:
 kind=v['kind'];ns=v['metadata'].get('namespace');name=v['metadata']['name'];i=ident(v)
 raw=run(['get',kind,name,*(['-n',ns]if ns else[]),'-o','json','--show-managed-fields','--ignore-not-found']);live=json.loads(raw)if raw.strip()else None
 if live is None:
  assert kind=='CustomResourceDefinition'and name.endswith('.groupsnapshot.storage.k8s.io'),'unexpected_new_resource'
  new.append(i);d=copy.deepcopy(v);old[i]=None
 else:
  assert any(x.get('manager')=='kubectl'and x.get('operation')=='Apply'for x in live['metadata'].get('managedFields',[])),'unreviewed_owner:'+i
  o=clean(live);old[i]=o;d=copy.deepcopy(v);d['metadata']['uid']=o['metadata']['uid']
  for meta_field in ['labels','annotations']:d['metadata'][meta_field]={**o['metadata'].get(meta_field,{}),**d['metadata'].get(meta_field,{})}
  if kind=='Deployment':
   assert name=='snapshot-controller'and ns=='kube-system'and o['spec']['replicas']==2,'existing_controller_shape'
   containers=o['spec']['template']['spec']['containers'];assert len(containers)==1 and containers[0]['name']=='snapshot-controller'
   assert containers[0].get('args')==['--v=5','--leader-election=true'],'launch_changed'
   assert containers[0]['image']in ['registry.k8s.io/sig-storage/snapshot-controller:v8.5.0',r['image']['reference']],'unreviewed_baseline_image'
   d=copy.deepcopy(o);d['spec']['template']['spec']['containers'][0]['image']=r['image']['reference']
   d['metadata'].get('annotations',{}).pop('deployment.kubernetes.io/revision',None)
  if kind=='CustomResourceDefinition':
   versions={x['name']:x for x in d['spec']['versions']}
   assert all(x in versions for x in live['status'].get('storedVersions',[])),'stored_version_removed'
   assert all(x['name']in versions and versions[x['name']]['served']for x in live['spec']['versions']if x['served']),'served_version_removed'
  if kind=='ClusterRole':assert o['rules']==d['rules'],'unexpected_rbac_change'
 if kind=='CustomResourceDefinition':crd_versions.append({'name':name,'new':live is None,'versions':[{'name':x['name'],'served':x['served'],'storage':x['storage']}for x in d['spec']['versions']],'storedVersions':None if live is None else live['status'].get('storedVersions',[])})
 desired[i]=d
assert len(desired)==8 and len(crd_versions)==6
baseline,readiness=snapshot_protected();assert len(baseline['originalSnapshots'])==3 and all(x['ready']or x['suspended']for x in readiness),'existing_state_unhealthy'
deployment_id='Deployment/kube-system/snapshot-controller';revision_key='deployment.kubernetes.io/revision'
def dryrun():return json.loads(run(['apply','--server-side','--field-manager=kubectl','--dry-run=server','-f','-','-o','json'],{'apiVersion':'v1','kind':'List','items':list(desired.values())},timeout=180))['items']
def runtime():
 d=json.loads(run(['get','deployment','snapshot-controller','-n','kube-system','-o','json']));assert d['spec']==desired[deployment_id]['spec'],'controller_spec_changed'
 selector=d['spec']['selector']['matchLabels']
 ps=[p for p in get('pods','kube-system')if all(p['metadata'].get('labels',{}).get(k)==v for k,v in selector.items())and not p['metadata'].get('deletionTimestamp')]
 assert len(ps)==2,'expected_two_controller_pods';out=[]
 for p in ps:
  ss=p['status']['containerStatuses'];assert len(ss)==1 and ss[0]['ready']and ss[0]['restartCount']==0
  assert p['spec']['containers'][0]['image']==r['image']['reference']and ss[0]['imageID'].split('@')[-1]in [r['image']['reference'].split('@')[-1],r['image']['amd64ManifestDigest']],'runtime_image_mismatch'
  out.append({'podUID':p['metadata']['uid'],'node':p['spec']['nodeName'],'image':p['spec']['containers'][0]['image'],'imageID':ss[0]['imageID'],'ready':True,'restarts':0})
 return out
if action=='prepare':
 assert len(new)==3
 result=dryrun();reviews=[]
 for x in result:
  i=ident(x);o=old[i];reviews.append({'id':i,'uid':None if o is None else o['metadata']['uid'],'beforeHMAC':None if o is None else mac(semantic(o)),'desiredHMAC':mac(semantic(desired[i])),'serverDryRunHMAC':mac(semantic(x)),'changedPaths':['CREATE']if o is None else paths(semantic(o),semantic(x))})
 print(json.dumps({'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'protected':baseline,'readiness':readiness,'reviews':reviews,'crdVersions':crd_versions,'originalControllerRevision':int(old[deployment_id]['metadata']['annotations'][revision_key]),'rollback':[x for x in old.values()if x is not None],'fieldManager':'kubectl','forceConflicts':False}))
elif action=='apply':
 plan=r['plan'];assert baseline==plan['protected']and len(new)==3,'protected_baseline_changed'
 for x in plan['reviews']:
  i=x['id'];o=old[i];assert (None if o is None else mac(semantic(o)))==x['beforeHMAC']and mac(semantic(desired[i]))==x['desiredHMAC'],'prepared_resource_changed:'+i
 preview=dryrun();expected={x['id']:x['serverDryRunHMAC']for x in plan['reviews']};assert all(mac(semantic(x))==expected[ident(x)]for x in preview),'preview_changed'
 supporting=[x for x in desired.values()if x['kind']!='Deployment'];run(['apply','--server-side','--field-manager=kubectl','-f','-'],{'apiVersion':'v1','kind':'List','items':supporting},timeout=180)
 print(json.dumps({'phase':'supporting_objects_applied','count':len(supporting),'newCRDs':new}),flush=True)
 for x in supporting:
  if x['kind']=='CustomResourceDefinition':run(['wait','--for=condition=Established','crd/'+x['metadata']['name'],'--timeout=90s'],timeout=100)
 run(['apply','--server-side','--field-manager=kubectl','-f','-'],desired[deployment_id])
 try:run(['-n','kube-system','rollout','status','deployment/snapshot-controller','--timeout=240s'],timeout=260)
 except BaseException:
  current=json.loads(run(['get','deployment','snapshot-controller','-n','kube-system','-o','json']))
  if current['metadata']['uid']==old[deployment_id]['metadata']['uid']and current['spec']==desired[deployment_id]['spec']:
   rollback=copy.deepcopy(old[deployment_id]);rollback['metadata'].get('annotations',{}).pop(revision_key,None)
   run(['apply','--server-side','--field-manager=kubectl','-f','-'],rollback);run(['-n','kube-system','rollout','status','deployment/snapshot-controller','--timeout=240s'],timeout=260)
   print(json.dumps({'phase':'failed_controller_rolled_back','CRDsNotDowngraded':True}),flush=True)
  raise
 actual=runtime();after,ready=snapshot_protected();assert after==baseline and all(x['ready']or x['suspended']for x in ready),'post_upgrade_state_changed'
 print(json.dumps({'phase':'upgrade_accepted','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runtime':actual,'protectedStateUnchanged':True,'readiness':ready}),flush=True)
elif action=='verify':
 assert not new and baseline==r['plan']['protected'],'post_upgrade_protected_state_changed'
 expected={x['id']:x for x in r['plan']['reviews']};objects=[]
 for i,o in old.items():
  row=expected[i];body=semantic(o)
  if i==deployment_id:
   now=int(body['metadata']['annotations'][revision_key]);assert now==r['plan']['originalControllerRevision']+1,'unexpected_revision'
   body['metadata']['annotations'][revision_key]=str(r['plan']['originalControllerRevision'])
  assert mac(body)==row['serverDryRunHMAC'],'reviewed_server_result_changed:'+i
  if row['uid']:assert row['uid']==o['metadata']['uid'],'original_resource_replaced'
  objects.append({'id':i,'uid':o['metadata']['uid'],'matchesReviewedServerResult':True,'originalUIDPreserved':row['uid']is not None})
 print(json.dumps({'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runtime':runtime(),'objects':objects,'protectedStateUnchanged':True,'readiness':readiness,'crdVersions':crd_versions,'controllerRevisionIncrement':1}))
else:raise RuntimeError('unknown_action')
'''

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['prepare', 'apply', 'verify'])
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--approved-sha256', default='')
    a = ap.parse_args()
    os.umask(0o077)
    assert ROOT.is_mount() and a.output_dir.resolve().is_relative_to(ROOT) and not a.output_dir.is_symlink()
    assert shutil.disk_usage('/mnt/c').free >= 15 * 1024**3 and shutil.disk_usage(ROOT).free >= 15 * 1024**3 + 64 * 1024**2
    core = Path(__file__).resolve().parents[2] / 'flux_upstream_upgrade/files/upgrade.py'
    assert sha(core) == CORE_SHA
    tree = ast.parse(core.read_text())
    remote = next(ast.literal_eval(x.value) for x in tree.body if isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'REMOTE' for t in x.targets))
    nodes = next(ast.literal_eval(x.value) for x in tree.body if isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'NODES' for t in x.targets))
    remote = remote[:remote.index("vendor=r['vendor']")]
    needle = "if x['metadata'].get('namespace')!='flux-system']"
    assert remote.count(needle) == 1
    remote = remote.replace(needle, "if x['metadata'].get('namespace')!='flux-system'and ident(x)!='Deployment/kube-system/snapshot-controller']") + SUFFIX
    pins_path = Path(__file__).with_name('pins-v8.7.0.json')
    pins = json.loads(pins_path.read_text())
    public = ROOT / 'platform-upstream-review-20261027/snapshot-v8.7-public-inputs'
    objects = []
    for item in pins['files']:
        p = public / item['name']
        assert p.resolve().is_relative_to(ROOT) and not p.is_symlink() and sha(p) == item['SHA256']
        objects.extend(x for x in yaml.safe_load_all(p.read_text()) if x)
    vendor = [x for x in objects if x['kind'] == 'CustomResourceDefinition' or (x['kind'] == 'ClusterRole' and x['metadata']['name'] == 'snapshot-controller-runner') or x['kind'] == 'Deployment']
    assert len(vendor) == 8 and pins['image']['reference'] == IMAGE
    a.output_dir.mkdir(mode=0o700, exist_ok=True)
    target = a.output_dir / (a.mode + '.json')
    assert not target.exists(), 'single_use_receipt_exists'
    request = {'key': (ROOT / 'acceptance-ruckus-20261025/hmac-key.hex').read_text().strip(),
               'action': a.mode, 'vendor': vendor, 'image': pins['image'], 'nodes': nodes}
    if a.mode != 'prepare':
        p = a.output_dir / 'prepare.json'
        assert sha(p) == a.approved_sha256
        request['plan'] = json.loads(p.read_text())
        assert request['plan']['exitCode'] == 0 and request['plan']['sourceSHA256'] == sha(Path(__file__)) and request['plan']['pinsSHA256'] == sha(pins_path)
        if a.mode == 'apply':
            with (a.output_dir / 'apply-started.json').open('x') as f:
                json.dump({'sourceSHA256': sha(Path(__file__)), 'prepareSHA256': a.approved_sha256}, f)
    cmd = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
           '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4', shlex.join(['python3', '-B', '-c', remote])]
    try:
        p = subprocess.run(cmd, input=json.dumps(request).encode(), capture_output=True, timeout=1000)
    except subprocess.TimeoutExpired as e:
        target.write_text(json.dumps({'mode': a.mode, 'sourceSHA256': sha(Path(__file__)),
                                     'errorCategory': 'ssh_deadline_expired_observe_cluster_before_any_retry',
                                     'stdoutSHA256': hashlib.sha256(e.stdout or b'').hexdigest(),
                                     'stderrSHA256': hashlib.sha256(e.stderr or b'').hexdigest()}, indent=2) + '\n')
        raise RuntimeError('deadline_expired_no_apply_replay')
    receipt = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'mode': a.mode, 'exitCode': p.returncode,
               'sourceSHA256': sha(Path(__file__)), 'pinsSHA256': sha(pins_path), 'coreSourceSHA256': CORE_SHA,
               'stderrSHA256': hashlib.sha256(p.stderr).hexdigest(), 'plaintextSnapshotsStored': False}
    if p.returncode:
        receipt['errorCategory'] = p.stderr.decode(errors='replace').splitlines()[-1][:240] if p.stderr else 'remote_failed'
        receipt['events'] = [json.loads(line) for line in p.stdout.splitlines()]
        target.write_text(json.dumps(receipt, indent=2) + '\n')
        raise RuntimeError('snapshot_phase_failed_inspect_metadata_do_not_replay_apply')
    if a.mode == 'prepare':
        d = json.loads(p.stdout)
        originals = d.pop('rollback')
        age = ROOT.parent / 'bin/age'
        assert sha(age) == AGE_SHA
        encrypted = subprocess.run([str(age), '-R', '/home/brajam/.ssh/id_ed25519.pub'], input=json.dumps(originals).encode(), capture_output=True, timeout=60)
        assert encrypted.returncode == 0
        cipher = a.output_dir / 'original-resources.json.age'
        with cipher.open('xb') as f:
            f.write(encrypted.stdout)
        checked = subprocess.run([str(age), '-d', '-i', '/home/brajam/.ssh/id_ed25519', str(cipher)], capture_output=True, timeout=60)
        assert checked.returncode == 0 and json.loads(checked.stdout) == originals
        receipt.update(d)
        receipt['encryptedOriginals'] = {'bytes': cipher.stat().st_size, 'SHA256': sha(cipher), 'authenticated': True}
    elif a.mode == 'apply':
        receipt['events'] = [json.loads(line) for line in p.stdout.splitlines()]
        assert receipt['events'][-1]['phase'] == 'upgrade_accepted'
    else:
        receipt.update(json.loads(p.stdout))
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'mode': a.mode, 'exitCode': 0, 'receipt': str(target)}))

if __name__ == '__main__':
    main()
