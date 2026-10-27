"""Pinned upstream Flux upgrade; encrypted rollback, reviewed SSA and bounded rollout.

No plaintext snapshots or inline environment values are written. Existing kubectl
field ownership is retained. Application reconciliation is observed, not bypassed.
The evidence directory is a single-use operation, not a replayable deployment queue.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import yaml

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
VENDOR_SHA = 'a8c838ccd9be5d30eba9df87cd229b7c4eb80c0049fba1bc3b9840829f267f28'
AGE_SHA = 'eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c'
BACKUP_SHA = 'de348e280924bfaa4637aaeb4f94cef4396612be973eda0732209fa5516ee268'
NODES = {'masternode': 'f2df6169-4592-4544-b62c-74d89f598648',
         'workernode1': 'e8d4555f-7cea-445f-b84f-6416964045a9',
         'workernode2': 'eda66e65-f388-4b97-b64f-a709cda81894'}

# Runs without temporary files on the master. All kubectl stdout/stderr remains
# in memory; only explicitly classified metadata is returned to the controller.
REMOTE = r'''
import copy,datetime,hashlib,hmac,json,subprocess,sys,time
r=json.load(sys.stdin); key=bytes.fromhex(r['key']); action=r['action']
def mac(x):return hmac.new(key,json.dumps(x,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()
def run(args,data=None,timeout=90):
 p=subprocess.run(['kubectl','--request-timeout=45s',*args],input=None if data is None else json.dumps(data).encode(),capture_output=True,timeout=timeout)
 if p.returncode:raise RuntimeError('kubectl_failed:'+args[0]+':'+str(p.returncode)+':diagnosticSHA256='+hashlib.sha256(p.stderr).hexdigest())
 assert len(p.stdout)<=32*1024**2,'response_too_large'
 return p.stdout
def get(kind,ns=None):return json.loads(run(['get',kind,*(['-n',ns]if ns else ['-A']),'-o','json','--show-managed-fields']))['items']
def ident(x):return x['kind']+'/'+x['metadata'].get('namespace','')+'/'+x['metadata']['name']
def clean(x):
 d={k:copy.deepcopy(v) for k,v in x.items() if k not in ['metadata','status']}
 d['metadata']={k:copy.deepcopy(v) for k,v in x['metadata'].items() if k in ['name','namespace','uid','labels','annotations']}
 return d
def semantic(x):
 d=clean(x);d['metadata'].pop('uid',None);return d
def paths(a,b,p=''):
 if type(a)!=type(b):return [p]
 if isinstance(a,dict):
  out=[]
  for k in sorted(set(a)|set(b)):out.extend([p+'/'+k] if k not in a or k not in b else paths(a[k],b[k],p+'/'+k))
  return out
 if isinstance(a,list):
  if len(a)!=len(b):return [p]
  return [v for i,(aa,bb) in enumerate(zip(a,b)) for v in paths(aa,bb,p+'/'+str(i))]
 return [] if a==b else [p]
def protected():
 ns=get('nodes');assert {x['metadata']['name']:x['metadata']['uid'] for x in ns}==r['nodes'],'node_identity_changed'
 assert all(any(c['type']=='Ready' and c['status']=='True' for c in x['status']['conditions']) for x in ns),'node_not_ready'
 assert all(not any(c['type'] in ['DiskPressure','MemoryPressure','PIDPressure'] and c['status']=='True' for c in x['status']['conditions']) for x in ns),'node_pressure'
 resources=sorted(x for x in run(['api-resources','--verbs=list','-o','name']).decode().splitlines() if x.endswith(('.toolkit.fluxcd.io','.source.extensions.fluxcd.io')))
 objects=[]; readiness=[]
 for resource in resources:
  for x in get(resource):
   s=x.get('spec',{});n=ident(x)
   assert not s.get('serviceAccountName') and not s.get('kubeConfig',{}).get('configMapRef'),'unreviewed_workload_identity'
   assert not(x['kind']=='Alert' and 'summary' in s) and not(x['kind']=='Provider' and ('interval' in s or s.get('secretRef'))),'unreviewed_notification_conversion'
   objects.append({'id':n,'uid':x['metadata']['uid'],'specHMAC':mac(s)})
   if x['kind'] in ['GitRepository','HelmRelease','Kustomization','OCIRepository']:
    readiness.append({'id':n,'suspended':s.get('suspend',False),'ready':any(c['type']=='Ready' and c['status']=='True' for c in x.get('status',{}).get('conditions',[])), 'revision':x.get('status',{}).get('artifact',{}).get('revision') or x.get('status',{}).get('lastAppliedRevision')})
   if x['kind']=='HelmRelease' and x['metadata']['name']=='bortus':assert s.get('suspend') is True,'bortus_hold_changed'
 claims=[{'id':ident(x),'uid':x['metadata']['uid'],'specHMAC':mac(x['spec'])} for x in get('persistentvolumeclaims')]
 volumes=[{'id':ident(x),'uid':x['metadata']['uid'],'specHMAC':mac(x['spec'])} for x in get('persistentvolumes')]
 workloads=[{'id':ident(x),'uid':x['metadata']['uid'],'specHMAC':mac(x['spec'])} for x in get('deployments,statefulsets,daemonsets,cronjobs') if x['metadata'].get('namespace')!='flux-system']
 secrets=[{'id':ident(x),'uid':x['metadata']['uid'],'contentHMAC':mac({k:x.get(k) for k in ['data','type','immutable']})} for x in get('secrets') if x.get('type')!='helm.sh/release.v1']
 result={k:sorted(v,key=lambda x:x['id']) for k,v in [('fluxSpecs',objects),('claims',claims),('volumes',volumes),('applicationWorkloads',workloads),('nativeSecrets',secrets)]}
 result['nodes']=sorted([{'id':x['metadata']['name'],'uid':x['metadata']['uid'],'bootID':x['status']['nodeInfo']['bootID']} for x in ns],key=lambda x:x['id'])
 return result,readiness
vendor=r['vendor']; desired={};old={};crds=[];images={x['name']:x for x in r['images']}
for v in vendor:
 kind=v['kind'];ns=v['metadata'].get('namespace');name=v['metadata']['name']
 found=json.loads(run(['get',kind,name,*(['-n',ns]if ns else []),'-o','json','--show-managed-fields','--ignore-not-found']))
 assert found and ident(found)==ident(v),'missing_original_resource'
 assert any(x.get('manager')=='kubectl' and x.get('operation')=='Apply' for x in found['metadata'].get('managedFields',[])),'unreviewed_field_owner:'+ident(v)
 o=clean(found);d=copy.deepcopy(v);d['metadata']['uid']=o['metadata']['uid']
 for f in ['labels','annotations']:
  d['metadata'][f]={**o['metadata'].get(f,{}),**d['metadata'].get(f,{})}
 if kind=='Deployment':
  assert len(o['spec']['template']['spec']['containers'])==1 and name in images,'unexpected_controller_shape'
  c=o['spec']['template']['spec']['containers'][0];vc=v['spec']['template']['spec']['containers'][0]
  assert c.get('args')==vc.get('args') and c.get('ports')==vc.get('ports'),'unreviewed_launch_change:'+name
  d['spec']=copy.deepcopy(o['spec']);d['spec']['template']['spec']['containers'][0]['image']=images[name]['reference']
 if kind=='CustomResourceDefinition':
  versions={x['name']:x for x in d['spec']['versions']}
  assert all(x in versions for x in found['status'].get('storedVersions',[])),'stored_version_removal'
  assert all(x['name'] in versions and versions[x['name']]['served'] for x in found['spec']['versions'] if x['served']),'served_version_removal'
  crds.append({'name':name,'storedVersions':found['status'].get('storedVersions',[]),'targetStorage':[x['name']for x in d['spec']['versions']if x['storage']]})
 old[ident(v)]=o;desired[ident(v)]=d
assert len(desired)==43 and len(images)==7 and len(crds)==15,'vendor_inventory_changed'
baseline,readiness=protected()
assert all(x['suspended'] or x['ready'] for x in readiness),'existing_flux_reconciliation_failure'
if action=='prepare':
 result=json.loads(run(['apply','--server-side','--field-manager=kubectl','--dry-run=server','-f','-','-o','json'],{'apiVersion':'v1','kind':'List','items':list(desired.values())},timeout=180))
 reviewed=[]
 for x in result['items']:
  i=ident(x);p=paths(semantic(old[i]),semantic(x));reviewed.append({'id':i,'uid':old[i]['metadata']['uid'],'beforeHMAC':mac(semantic(old[i])),'desiredHMAC':mac(semantic(desired[i])),'serverDryRunHMAC':mac(semantic(x)),'changedPaths':p})
 print(json.dumps({'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'action':action,'fieldManager':'kubectl','forceConflicts':False,'protected':baseline,'readiness':readiness,'review':reviewed,'crdVersions':crds,'rollback':list(old.values())}))
elif action=='apply':
 plan=r['plan'];assert baseline==plan['protected'],'protected_baseline_changed'
 for x in plan['review']:
  i=x['id'];assert old[i]['metadata']['uid']==x['uid'] and mac(semantic(old[i]))==x['beforeHMAC'] and mac(semantic(desired[i]))==x['desiredHMAC'],'prepared_resource_changed:'+i
 # Re-run server validation immediately before the first mutation. No force.
 preview=json.loads(run(['apply','--server-side','--field-manager=kubectl','--dry-run=server','-f','-','-o','json'],{'apiVersion':'v1','kind':'List','items':list(desired.values())},timeout=180))
 expected={x['id']:x['serverDryRunHMAC']for x in plan['review']}
 assert all(mac(semantic(x))==expected[ident(x)] for x in preview['items']),'server_preview_changed'
 noncontrollers=[x for x in desired.values()if x['kind']!='Deployment']
 run(['apply','--server-side','--field-manager=kubectl','-f','-'],{'apiVersion':'v1','kind':'List','items':noncontrollers},timeout=180)
 print(json.dumps({'phase':'supporting_objects_applied','count':len(noncontrollers)}),flush=True)
 for name in ['notification-controller','source-controller','source-watcher','kustomize-controller','helm-controller','image-reflector-controller','image-automation-controller']:
  i='Deployment/flux-system/'+name;d=desired[i]
  run(['apply','--server-side','--field-manager=kubectl','-f','-'],d)
  try:
   run(['-n','flux-system','rollout','status','deployment/'+name,'--timeout=240s'],timeout=260)
   pods=get('pods','flux-system');matches=[p for p in pods if p['metadata'].get('labels',{}).get('app')==name and not p['metadata'].get('deletionTimestamp')]
   assert len(matches)==1 and matches[0]['spec']['containers'][0]['image']==images[name]['reference'],'unexpected_replacement_pod'
   p=matches[0];st=p['status']['containerStatuses'];assert len(st)==1 and st[0]['ready'] and st[0]['restartCount']==0,'controller_not_stable'
   actual=st[0]['imageID'].split('@')[-1];assert actual in [images[name]['amd64ManifestDigest'],images[name]['reference'].split('@')[-1]],'runtime_digest_mismatch'
   print(json.dumps({'phase':'controller_ready','name':name,'podUID':p['metadata']['uid'],'imageID':st[0]['imageID']}),flush=True)
  except BaseException:
   # Do not downgrade CRDs or overwrite changes made by another owner.
   current=json.loads(run(['get','deployment',name,'-n','flux-system','-o','json']))
   if current['metadata']['uid']==d['metadata']['uid'] and current['spec']==d['spec']:
    run(['apply','--server-side','--field-manager=kubectl','-f','-'],old[i])
    run(['-n','flux-system','rollout','status','deployment/'+name,'--timeout=240s'],timeout=260)
    print(json.dumps({'phase':'failed_controller_rolled_back','name':name,'crdsNotDowngraded':True}),flush=True)
   raise
 after,ready=protected();assert after==baseline,'post_upgrade_protected_state_changed'
 assert all(x['suspended']or x['ready']for x in ready),'post_upgrade_reconciliation_failure'
 print(json.dumps({'phase':'upgrade_accepted','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'protectedStateUnchanged':True,'readiness':ready}),flush=True)
elif action=='verify':
 assert baseline==r['plan']['protected'],'protected_state_changed'
 pods=get('pods','flux-system');controllers=[]
 for name,img in sorted(images.items()):
  d=desired['Deployment/flux-system/'+name];live=old['Deployment/flux-system/'+name]
  assert live['spec']==d['spec'],'image_not_adopted'
  ps=[p for p in pods if p['metadata'].get('labels',{}).get('app')==name and not p['metadata'].get('deletionTimestamp')];assert len(ps)==1
  p=ps[0];st=p['status']['containerStatuses'];assert len(st)==1 and st[0]['ready']and st[0]['restartCount']==0
  assert st[0]['imageID'].split('@')[-1]in [img['amd64ManifestDigest'],img['reference'].split('@')[-1]]
  controllers.append({'name':name,'deploymentUID':live['metadata']['uid'],'podUID':p['metadata']['uid'],'image':img['reference'],'imageID':st[0]['imageID'],'ready':True,'restarts':0})
 print(json.dumps({'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'action':action,'protectedStateUnchanged':True,'controllers':controllers,'readiness':readiness,'crdVersions':crds}))
else:raise RuntimeError('unknown_action')
'''

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['prepare', 'apply', 'verify'])
    for field in ['output-dir', 'vendor-manifest', 'candidates', 'backup-receipt']:
        ap.add_argument('--' + field, required=True, type=Path)
    a = ap.parse_args()
    os.umask(0o077)
    assert ROOT.is_mount() and ROOT.resolve() == ROOT
    for p in [a.output_dir, a.vendor_manifest, a.candidates, a.backup_receipt]:
        assert p.resolve().is_relative_to(ROOT) and not p.is_symlink(), 'outside_owned_root'
    assert shutil.disk_usage('/mnt/c').free >= 15 * 1024**3
    assert shutil.disk_usage(ROOT).free >= 15 * 1024**3 + 128 * 1024**2
    assert digest(a.vendor_manifest) == VENDOR_SHA
    backup = json.loads(a.backup_receipt.read_text())
    assert backup['phase'] == 'ciphertexts_copied' and len(backup['files']) == 1
    assert backup['files'][0]['completeAgeAuthentication'] and backup['files'][0]['destinationSHA256'] == BACKUP_SHA
    age = ROOT.parent / 'bin/age'
    assert digest(age) == AGE_SHA
    vendor = list(yaml.safe_load_all(a.vendor_manifest.read_text()))
    images = json.loads(a.candidates.read_text())['images']
    assert all('@sha256:' in x['reference'] for x in images)
    a.output_dir.mkdir(mode=0o700, exist_ok=True)
    source_sha = digest(Path(__file__))
    target = a.output_dir / (a.mode + '.json')
    assert not target.exists(), 'single_use_phase_receipt_exists'
    request = {'action': a.mode, 'key': (ROOT / 'acceptance-ruckus-20261025/hmac-key.hex').read_text().strip(),
               'vendor': vendor, 'images': images, 'nodes': NODES}
    if a.mode != 'prepare':
        request['plan'] = json.loads((a.output_dir / 'prepare.json').read_text())
        approved = json.loads((a.output_dir / 'review-approval.json').read_text())
        assert approved['prepareSHA256'] == digest(a.output_dir / 'prepare.json')
        assert approved['sourceSHA256'] == source_sha and approved['reviewed'] is True
    ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
           '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4',
           shlex.join(['python3', '-B', '-c', REMOTE])]
    if a.mode == 'apply':
        # Exclusive durable marker prevents replays after interrupted/partial apply.
        with (a.output_dir / 'apply-started.json').open('x') as f:
            json.dump({'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'sourceSHA256': source_sha}, f)
    child = subprocess.Popen(ssh, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout, stderr = child.communicate(json.dumps(request).encode(), timeout=2300 if a.mode == 'apply' else 420)
    except subprocess.TimeoutExpired:
        child.kill()
        stdout, stderr = child.communicate()
        target.write_text(json.dumps({'mode': a.mode, 'sourceSHA256': source_sha,
                                     'errorCategory': 'ssh_deadline_expired_observe_cluster_before_any_retry',
                                     'stdoutSHA256': hashlib.sha256(stdout).hexdigest(),
                                     'stderrSHA256': hashlib.sha256(stderr).hexdigest()}, indent=2) + '\n')
        raise RuntimeError('deadline_expired_no_replay_authorized')
    receipt = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'mode': a.mode,
               'sourceSHA256': source_sha, 'vendorSHA256': VENDOR_SHA, 'exitCode': child.returncode,
               'stderrSHA256': hashlib.sha256(stderr).hexdigest(), 'plaintextSnapshotsStored': False}
    if child.returncode:
        # Only our invariant names and Python trace locations, never API output.
        receipt['errorCategory'] = stderr.decode(errors='replace').splitlines()[-1][:240] if stderr else 'remote_failed'
        receipt['events'] = [json.loads(line) for line in stdout.splitlines()]
        target.write_text(json.dumps(receipt, indent=2) + '\n')
        raise RuntimeError('flux_phase_failed_inspect_metadata_receipt')
    if a.mode == 'prepare':
        data = json.loads(stdout)
        rollback = data.pop('rollback')
        encrypted = subprocess.run([str(age), '-R', '/home/brajam/.ssh/id_ed25519.pub'],
                                   input=json.dumps({'objects': rollback, 'UTC': data['UTC']}).encode(),
                                   capture_output=True, timeout=60)
        assert encrypted.returncode == 0
        cipher = a.output_dir / 'original-objects.json.age'
        with cipher.open('xb') as f:
            f.write(encrypted.stdout)
        check = subprocess.run([str(age), '-d', '-i', '/home/brajam/.ssh/id_ed25519', str(cipher)], capture_output=True, timeout=60)
        assert check.returncode == 0 and json.loads(check.stdout)['objects'] == rollback
        receipt.update(data)
        receipt['rollbackCiphertext'] = {'path': str(cipher), 'bytes': cipher.stat().st_size, 'SHA256': digest(cipher), 'authenticated': True}
    elif a.mode == 'apply':
        receipt['events'] = [json.loads(line) for line in stdout.splitlines()]
        assert receipt['events'][-1]['phase'] == 'upgrade_accepted'
    else:
        receipt.update(json.loads(stdout))
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'mode': a.mode, 'exitCode': 0, 'receipt': str(target), 'sourceSHA256': source_sha}))

if __name__ == '__main__':
    main()
