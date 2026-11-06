"""Restore scheduling after the exact pre-upgrade transfer failure, not an upgrade retry."""
import argparse
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import runpy
import re
import shlex
import subprocess
import sys

F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028'
AUTH='c21016a7c150f50f66c3f86b1433412363409f7e6ecbce913c3414afdbf03ba8'
SSH=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile=/home/brajam/.ssh/known_hosts','-i','/home/brajam/.ssh/id_ed25519','-p','2002']

def ref(path):return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
def save(path,value):
 with path.open('x') as stream:
  json.dump(value,stream,indent=2);stream.flush();os.fsync(stream.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 return ref(path)
def kube(args):
 r=subprocess.run(SSH+['james@192.168.0.4',shlex.join(['kubectl']+args)],capture_output=True,timeout=60)
 assert r.returncode==0,'Kubernetes recovery request failed'
 return json.loads(r.stdout)

def main():
 os.umask(0o077)
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--observe-completed-uncordon',action='store_true')
 parser.add_argument('--post-preflight',action='store_true')
 parser.add_argument('--after-closed-preflight')
 parser.add_argument('--closed-kubeadm-addon-preflight-result',type=Path);parser.add_argument('--closed-kubeadm-addon-preflight-result-sha256')
 parser.add_argument('--closed-kubeadm-addon-preflight-log',type=Path);parser.add_argument('--closed-kubeadm-addon-preflight-log-sha256')
 parser.add_argument('--uncordon-qualified-addon-preflight',action='store_true',help='Explicit single UID/resourceVersion-tested scheduling restoration; default addon mode is read-only')
 args=parser.parse_args();post_preflight=args.post_preflight;observe_only=args.observe_completed_uncordon
 addon_values=[args.closed_kubeadm_addon_preflight_result,args.closed_kubeadm_addon_preflight_result_sha256,args.closed_kubeadm_addon_preflight_log,args.closed_kubeadm_addon_preflight_log_sha256]
 addon_mode=any(addon_values)
 assert not addon_mode or (all(addon_values) and not post_preflight and not args.after_closed_preflight)
 assert not args.uncordon_qualified_addon_preflight or (addon_mode and not observe_only)
 assert not post_preflight or observe_only
 assert not args.after_closed_preflight or (observe_only and not post_preflight and re.fullmatch('[a-f0-9]{32}',args.after_closed_preflight))
 suffix=('-after-closed-preflight-'+args.after_closed_preflight) if args.after_closed_preflight else ('-after-readonly-preflight' if post_preflight else '')
 if addon_mode:suffix='-after-addon-preflight-b6816a54662f4fc2839969b1eeb4e787'
 observation_path=H/('kubernetes1372-after-manual-uncordon-qualified'+suffix+'.json')
 proof_path=H/('kubernetes1372-master-kubeadm-transfer-proof'+suffix+'.json')
 assert not observation_path.exists() and not proof_path.exists(),'Preserve existing observation/proof; never reuse outputs'
 closed=None;addon=None
 if addon_mode:
  validator=Path(__file__).resolve().parents[2]/'k8s-rewrite/ansible-playbook/roles/kubernetes_security_patch/files/resume_transfer_proof.py'
  addon=runpy.run_path(str(validator))['validate_closed_kubeadm_addon_preflight']({'path':str(args.closed_kubeadm_addon_preflight_result),'sha256':args.closed_kubeadm_addon_preflight_result_sha256},{'path':str(args.closed_kubeadm_addon_preflight_log),'sha256':args.closed_kubeadm_addon_preflight_log_sha256},AUTH)
 if args.after_closed_preflight:
  result_path=H/('kubernetes-maintenance-receipts/'+args.after_closed_preflight+'-result.json')
  assert result_path.is_file()
  matching=[]
  for candidate in H.glob('kubernetes1372-native-rolling*.log'):
   for line in candidate.read_text().splitlines():
    if line.startswith('KUBERNETES_PATCH_INVOCATION ') and json.loads(line.split(' ',1)[1]).get('runID')==args.after_closed_preflight:matching.append(candidate)
  if args.after_closed_preflight=='b9a592f785cb45c69382c0e24ff0c5cc':matching=[H/'kubernetes1372-native-rolling-transfer-resume.log']
  assert len(matching)==1,'Exact terminal run log required'
  validator=Path(__file__).resolve().parents[2]/'k8s-rewrite/ansible-playbook/roles/kubernetes_security_patch/files/resume_transfer_proof.py'
  closed=runpy.run_path(str(validator))['validate_closed_preflight'](ref(result_path),ref(matching[0]),AUTH)
 password=sys.stdin.buffer.readline(130).removesuffix(b'\n')
 assert 0<len(password)<=128 and not any(x in password for x in (b'\r',b'\n',b'\0'))
 repo=Path(__file__).resolve().parents[2];role=repo/'k8s-rewrite/ansible-playbook/roles/kubernetes_security_patch/files'
 authority=H/'kubernetes1372-native-authority.json';assert ref(authority)['sha256']==AUTH
 plan=json.loads(authority.read_text())
 recovery=H/'kubernetes-recovery-89c1dc34de834eb6863a4cc570f71442/masternode-b628vf3o.json';before=json.loads(recovery.read_text())
 failed=H/'kubernetes-maintenance-receipts/89c1dc34de834eb6863a4cc570f71442-result.json'
 failure=json.loads(failed.read_text());assert failure['exitCode']!=0 and failure['settings']['kubernetes_security_patch_manifest_sha256']==AUTH
 log=H/'kubernetes1372-native-rolling-apply-cri-version-fixed.log';text=log.read_text()
 assert 'Failed to create temporary directory' in text and 'Build exact spec and metadata preservation patches for kubeadm' in text
 assert 'TASK [kubernetes_security_patch : Upgrade the native control-plane' not in text
 assert 'TASK [kubernetes_security_patch : Atomically replace native kubelet' not in text
 assert kube(['version','-o','json'])['serverVersion']['gitVersion']=='v1.37.1'
 nodes={n['metadata']['name']:n for n in kube(['get','nodes','-o','json'])['items']}
 assert {k:n['metadata']['uid'] for k,n in nodes.items()}==plan['nodeUIDs']
 source=(role/'native_binaries.py').read_text()+'\n'+(role/'preservation.py').read_text()+"""
value=dict(nativeBinaries={n:metadata(Path('/usr/local/bin')/n) for n in NAMES},staging={},holds=sorted(run(['apt-mark','showhold']).splitlines()),runningKubeletSHA256=file_sha(Path('/proc')/run(['systemctl','show','kubelet','--property=MainPID','--value'])/'exe'))
for n,e in ENTRY.items():
 p=Path('/usr/local/bin/.kubernetes1372-'+n+'-'+e['sha256']+'.new');value['staging'][n]=metadata(p) if os.path.lexists(p) else None
if platform.node()=='masternode':value['masterPreservation']=snapshot()
print(json.dumps(value))
"""
 observed={}
 for name,ip in [('masternode','192.168.0.4'),('workernode2','192.168.0.5'),('workernode1','192.168.0.6')]:
  code='ENTRY='+repr(plan['binaries'])+'\n'+source
  command="exec(compile("+repr(code)+",'<qualified-preupgrade-recovery>','exec'),{'__name__':'qualified_preupgrade_recovery'})"
  result=subprocess.run(SSH+['james@'+ip,shlex.join(['sudo','-k','-S','-p','','python3','-B','-c',command])],input=password+b'\n',capture_output=True,timeout=90)
  assert result.returncode==0,'Native recovery read failed'
  value=json.loads(result.stdout);node=nodes[name]
  assert any(c['type']=='Ready' and c['status']=='True' for c in node['status']['conditions'])
  assert not any(c['type'].endswith('Pressure') and c['status']=='True' for c in node['status']['conditions'])
  assert node['status']['nodeInfo']['kubeletVersion']=='v1.37.1'
  assert value['runningKubeletSHA256']==plan['binaries']['kubelet']['originalByNode'][name]['sha256']
  for binary,entry in plan['binaries'].items():
   expected=copy.deepcopy(entry['originalByNode'][name]);new=name=='masternode' and binary=='kubeadm'
   if new:expected.update(sha256=entry['sha256'],bytes=entry['bytes'])
   assert value['nativeBinaries'][binary]==expected
   staged=value['staging'][binary]
   if new:assert staged is None
   else:assert staged['sha256']==entry['sha256'] and staged['bytes']==entry['bytes']
  if name=='masternode':
   assert value['masterPreservation']==before['preservation']
   if addon:
    dns=json.loads(Path(addon['coreDNSBaseline']['path']).read_text())
    latest=json.loads(Path(dns['originalRecovery']).read_text())
    assert latest['authoritySHA256']==AUTH and value['masterPreservation']==latest['preservation']
   assert node['spec'].get('unschedulable',False) is (not observe_only)
   assert value['holds']==before['nativeBinaries']['holds']
  else:assert not node['spec'].get('unschedulable',False)
  observed[name]={'uid':node['metadata']['uid'],'ready':True,'unschedulable':node['spec'].get('unschedulable',False),'kubeletVersion':'v1.37.1',**value}
 password=None
 guard=runpy.run_path(str(role.parents[1]/'security_maintenance/files/kernel_checkpoint.py'))
 current=guard['project'](guard['get']('persistentvolumeclaims,persistentvolumes,volumes.longhorn.io,deployments,statefulsets,daemonsets'))
 original=json.loads(Path(plan['checkpoint']['path']).read_text())
 key=lambda x:(x['kind'],x['namespace'],x['name'],x['uid'])
 old={key(x):x for x in original['identities']};now={key(x):x for x in current};assert old.keys()==now.keys() and len(old)==219
 detached={'pvc-29f9332d-c2a6-4f24-a83f-210620046cd2','pvc-999128b4-0ae2-4396-a8e4-eebace5d26f0','pvc-cdfd60f4-e76a-4037-827b-02459d1ac3ff'}
 transitions=[]
 for ident,prior in old.items():
  actual=now[ident]
  if actual==prior:continue
  assert prior['kind']=='Volume' and prior['name'] in detached and prior['state']=='attached' and prior['robustness']=='healthy'
  assert actual['state']=='detached' and actual['robustness']=='unknown'
  stable={k:v for k,v in actual.items() if k not in ('state','robustness')}
  assert stable=={k:v for k,v in prior.items() if k not in ('state','robustness')}
  transitions.append({'name':prior['name'],'beforeState':'attached/healthy','duringOwnedCordon':'detached/unknown'})
 assert guard['ephemeral_sources']()==original['ephemeralSources']
 replicas=guard['get']('replicas.longhorn.io')
 for volume in detached:
  pair=[r for r in replicas if r['spec']['volumeName']==volume and not r['metadata'].get('deletionTimestamp')]
  assert len(pair)==2 and all(not r['spec'].get('failedAt') and r['spec'].get('healthyAt') for r in pair)
 observation={'capturedUTC':dt.datetime.now(dt.timezone.utc).isoformat(),'apiVersion':'v1.37.1','nodes':observed,'masterPreservation':observed['masternode']['masterPreservation'],
  'noKubeadmUpgradeInvocation':not bool(addon),'immutable219IdentityRowsPreserved':True,'temporaryDetachedVolumes':transitions,'acceptanceStillRequiresAll28Healthy':True}
 if addon:
  assert dt.datetime.fromisoformat(observation['capturedUTC'])>dt.datetime.fromisoformat(addon['finishedUTC'])
  observation['afterClosedKubeadmAddonPreflight']=addon
  # This is an explicitly post-failure baseline for the next invocation, not
  # invented evidence of pre-failure ConfigMap bytes.
  dns_module=runpy.run_path(str(role/'coredns_preservation.py'))
  dns=json.loads(Path(addon['coreDNSBaseline']['path']).read_text())
  for kind in ('deployment','configmap','service','serviceaccount','poddisruptionbudget'):
   cmd=['kubectl','-n','kube-system','get',kind,'coredns','--ignore-not-found','-o','json']
   r=subprocess.run(SSH+['james@192.168.0.4',shlex.join(cmd)],capture_output=True,timeout=45);assert r.returncode==0
   obj=json.loads(r.stdout) if r.stdout.strip() else None
   expected=dns['coredns'].get(kind)
   assert (obj is None and expected is None) or (obj is not None and expected is not None and dns_module['project'](obj)==dns_module['project'](expected))
  observation['coreDNSDeclarationsPreserved']=True
  prefix=H/('kubernetes1372-addon-preflight-'+addon['previousRunID'])
  before_path=Path(str(prefix)+'-before-uncordon.json');intent_path=Path(str(prefix)+'-uncordon-intent.json');after_path=Path(str(prefix)+'-uncordon-after.json')
  if not observe_only:
   if not args.uncordon_qualified_addon_preflight:
    print(json.dumps({'readOnlyQualified':True,'masterStillCordoned':True,'observation':save(Path(str(prefix)+'-cordoned-qualified.json'),observation)}));return
   assert not before_path.exists() and not intent_path.exists() and not after_path.exists(),'Existing uncordon intent cannot be replayed'
   before_ref=save(before_path,observation)
   node=kube(['get','node','masternode','-o','json']);assert node['metadata']['uid']==plan['nodeUIDs']['masternode'] and node['spec'].get('unschedulable') is True
   patch=[{'op':'test','path':'/metadata/uid','value':node['metadata']['uid']},{'op':'test','path':'/metadata/resourceVersion','value':node['metadata']['resourceVersion']},{'op':'test','path':'/spec/unschedulable','value':True},{'op':'replace','path':'/spec/unschedulable','value':False}]
   intent_ref=save(intent_path,{'closedFailure':addon,'before':before_ref,'nodeUID':node['metadata']['uid'],'patch':patch,'noUncertainReplay':True})
   after=kube(['patch','node','masternode','--type=json','-p',json.dumps(patch),'-o','json'])
   assert after['metadata']['uid']==node['metadata']['uid'] and after['spec'].get('unschedulable',False) is False
   print(json.dumps({'uncordonAccepted':True,'freshReadOnlyQualificationRequired':True,'receipt':save(after_path,{'intent':intent_ref,'nodeUID':after['metadata']['uid'],'resourceVersion':after['metadata']['resourceVersion']})}));return
  assert intent_path.is_file() and before_path.is_file()
  intent=json.loads(intent_path.read_text());frozen=json.loads(before_path.read_text())
  assert intent['closedFailure']==addon and intent['before']==ref(before_path) and intent['nodeUID']==plan['nodeUIDs']['masternode'] and intent['noUncertainReplay'] is True
  assert frozen['nodes']['masternode']['unschedulable'] is True and frozen['masterPreservation']==observation['masterPreservation']
  assert not transitions and old==now,'Continuation requires every original volume healthy and all identity rows exact'
  assert sum(x['kind']=='Volume' and x.get('state')=='attached' and x.get('robustness')=='healthy' for x in current)==28
  observation['all28ActiveVolumesHealthy']=True
  dns_guard=role/'coredns_preservation.py'
  dns_check=subprocess.run([sys.executable,'-B',str(dns_guard)],capture_output=True,timeout=60)
  assert dns_check.returncode==0,'Full independently managed DNS successor guard must pass'
  dns_result=json.loads(dns_check.stdout);assert dns_result['passed'] is True
  observation['fullCoreDNSGuard']={'sourceSHA256':ref(dns_guard)['sha256'],'result':dns_result}
  observation['qualifiedManualUncordon']={'beforeQualification':ref(before_path),'intent':ref(intent_path),'outcomeObservedReadOnly':True,'mutationReplayed':False}
  # Repeat the unchanged complete backup and identity gates after scheduling settles.
  command=[sys.executable,'-B',str(role.parents[1]/'security_maintenance/files/kernel_checkpoint.py'),'--manifest',plan['checkpoint']['path'],'--sha256',plan['checkpoint']['sha256']]
  r=subprocess.run(command,capture_output=True,timeout=60);assert r.returncode==0,'Full current58 backup/identity gate must pass after uncordon'
 elif observe_only:
  prior=H/'kubernetes1372-before-manual-uncordon-qualified.json'
  frozen=json.loads(prior.read_text())
  assert frozen['nodes']['masternode']['unschedulable'] is True and frozen['masterPreservation']==observation['masterPreservation']
  observation['qualifiedManualUncordon']={'beforeQualification':ref(prior),'outcomeObservedReadOnly':True,'mutationReplayed':False,'responseParsingCorrection':'Kubernetes omits false unschedulable; omission is false.'}
 else:
  save(H/'kubernetes1372-before-manual-uncordon-qualified.json',observation)
  node=kube(['get','node','masternode','-o','json']);assert node['metadata']['uid']==plan['nodeUIDs']['masternode'] and node['spec'].get('unschedulable') is True
  patch=[{'op':'test','path':'/metadata/uid','value':node['metadata']['uid']},{'op':'test','path':'/metadata/resourceVersion','value':node['metadata']['resourceVersion']},{'op':'test','path':'/spec/unschedulable','value':True},{'op':'replace','path':'/spec/unschedulable','value':False}]
  after=kube(['patch','node','masternode','--type=json','-p',json.dumps(patch),'-o','json']);assert after['metadata']['uid']==node['metadata']['uid'] and after['spec'].get('unschedulable',False) is False
  observation['qualifiedManualUncordon']={'beforeResourceVersion':node['metadata']['resourceVersion'],'afterResourceVersion':after['metadata']['resourceVersion'],'onlySchedulabilityChanged':True}
 fresh=kube(['get','nodes','-o','json'])['items'];assert all(not n['spec'].get('unschedulable',False) for n in fresh)
 observation['nodes']['masternode']['unschedulable']=False;observation['capturedUTC']=dt.datetime.now(dt.timezone.utc).isoformat()
 if closed:
  assert dt.datetime.fromisoformat(observation['capturedUTC'])>dt.datetime.fromisoformat(closed['finishedUTC'])
  observation['afterClosedPreflight']=closed
 result=save(observation_path,observation)
 proof={'schemaVersion':1,'resumeKind':'master-kubeadm-only-after-transfer-failure','authoritySHA256':AUTH,'failedResult':ref(failed),'failedLog':ref(log),'recovery':ref(recovery),'observation':result}
 if addon:proof['closedKubeadmAddonPreflight']=addon
 print(json.dumps(save(proof_path,proof)))

if __name__=='__main__':
 try:main()
 except Exception as error:print('Qualified recovery stopped:',type(error).__name__,str(error)[:300]);sys.exit(1)
