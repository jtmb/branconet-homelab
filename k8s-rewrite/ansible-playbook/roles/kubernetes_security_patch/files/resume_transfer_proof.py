"""One explicit transfer-failure resume proof; no live actions or weakened defaults."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re

H=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/platform-upstream-review-20261027/autonomous-hardening-20261028')
FAILURE='89c1dc34de834eb6863a4cc570f71442'
PINS={
 'failedResult':('kubernetes-maintenance-receipts/'+FAILURE+'-result.json','11f9c57a18f5d8de1f115203156b9a9f4d5269a3a286af5b2356d03a48a1f0ff'),
 'failedLog':('kubernetes1372-native-rolling-apply-cri-version-fixed.log','b5f42b4ea00238c2ea2bbff390f23f3d21f2f33f9e8ef3db4d590c45b34dc1a3'),
 'recovery':('kubernetes-recovery-'+FAILURE+'/masternode-b628vf3o.json','1a5c28fe7b13a5e32e0d6bf0aba9de9ad955438c86367146161bf0cd417593b2')}
FIELDS=['mode','uid','gid','mtimeNs','xattrsSHA256']

def read_bound(reference):
 path=Path(reference['path'])
 assert path.resolve()==path and H in path.parents and path.is_file(), 'Proof source outside owned root'
 data=path.read_bytes();assert hashlib.sha256(data).hexdigest()==reference['sha256'],'Proof source hash changed'
 return data

def validate(proof_path,proof_sha,manifest_path,manifest_sha):
 assert re.fullmatch('[a-f0-9]{64}',proof_sha) and re.fullmatch('[a-f0-9]{64}',manifest_sha)
 proof=json.loads(read_bound({'path':str(proof_path),'sha256':proof_sha}))
 plan=json.loads(read_bound({'path':str(manifest_path),'sha256':manifest_sha}))
 assert proof['schemaVersion']==1 and proof['resumeKind']=='master-kubeadm-only-after-transfer-failure'
 assert proof['authoritySHA256']==manifest_sha
 sources={}
 for key,(relative,sha) in PINS.items():
  assert proof[key]=={'path':str(H/relative),'sha256':sha},'Different failure source is not this finite resume'
  sources[key]=read_bound(proof[key])
 failure=json.loads(sources['failedResult']);recovery=json.loads(sources['recovery']);log=sources['failedLog'].decode()
 assert failure['exitCode']==4 and failure['settings']['kubernetes_security_patch_apply'] is True
 assert failure['settings']['kubernetes_security_patch_manifest_sha256']==manifest_sha==recovery['authoritySHA256']
 assert recovery['host']=='masternode' and recovery['nativeBinaries']['mode']=='staged' and recovery['nativeBinaries']['passed'] is True
 tasks=re.findall(r'^TASK \[([^\]]+)\]',log,re.M)
 assert any('Atomically replace only native kubeadm first' in t for t in tasks)
 assert any('Build exact spec and metadata preservation patches for kubeadm' in t for t in tasks)
 assert not any('Upgrade the native control-plane manifests' in t or 'Run supported native worker upgrade' in t or 'Atomically replace native kubelet and kubectl' in t for t in tasks),'Previous upgrade invocation is not eligible'
 assert 'fatal: [masternode]: UNREACHABLE!' in log and '"changed": false' in log,'Expected pre-upgrade unreachable failure absent'
 assert tasks[-3:] == ['kubernetes_security_patch : Build exact spec and metadata preservation patches for kubeadm','Gathering Facts','Require control-plane completion before worker mutation'],'Failure task boundary differs'
 # The frozen log censors transport details with no_log. Exact task ordering
 # proves no kubeadm upgrade task was invoked; no invented SFTP error string.
 observation=json.loads(read_bound(proof['observation']))
 captured=datetime.datetime.fromisoformat(observation['capturedUTC'].replace('Z','+00:00'))
 assert datetime.timedelta(0)<=datetime.datetime.now(datetime.timezone.utc)-captured<=datetime.timedelta(hours=2),'Resume observation stale'
 assert observation['apiVersion']=='v1.37.1'
 addon=proof.get('closedKubeadmAddonPreflight')
 if addon:
  assert validate_closed_kubeadm_addon_preflight(addon['previousResult'],addon['previousLog'],manifest_sha)==addon
  assert observation['noKubeadmUpgradeInvocation'] is False and observation['afterClosedKubeadmAddonPreflight']==addon
  assert captured>datetime.datetime.fromisoformat(addon['finishedUTC'])
  assert observation['immutable219IdentityRowsPreserved'] is True and observation['all28ActiveVolumesHealthy'] is True and not observation['temporaryDetachedVolumes']
  assert observation['fullCoreDNSGuard']['result']['passed'] is True
  assert observation['coreDNSDeclarationsPreserved'] is True and observation['qualifiedManualUncordon']['outcomeObservedReadOnly'] is True
  uncordon=observation['qualifiedManualUncordon'];intent=json.loads(read_bound(uncordon['intent']));before=json.loads(read_bound(uncordon['beforeQualification']))
  assert intent['closedFailure']==addon and intent['before']==uncordon['beforeQualification'] and intent['nodeUID']==plan['nodeUIDs']['masternode'] and intent['noUncertainReplay'] is True
  assert before['nodes']['masternode']['unschedulable'] is True and before['masterPreservation']==observation['masterPreservation']
  assert before['afterClosedKubeadmAddonPreflight']==addon and uncordon['mutationReplayed'] is False
 else:assert observation['noKubeadmUpgradeInvocation'] is True
 assert observation['masterPreservation']==recovery['preservation'],'Original host/static/config/certificate bytes changed'
 assert set(observation['nodes'])==set(plan['nodeUIDs'])=={'masternode','workernode1','workernode2'}
 for host,node in observation['nodes'].items():
  assert node['uid']==plan['nodeUIDs'][host] and node['ready'] is True and node['unschedulable'] is False
  assert node['kubeletVersion']=='v1.37.1'
  assert set(node['nativeBinaries'])==set(node['staging'])=={'kubeadm','kubelet','kubectl'}
  for name,entry in plan['binaries'].items():
   original=entry['originalByNode'][host];actual=node['nativeBinaries'][name]
   stage_authority=json.loads(read_bound(entry['prestage'][host]))
   assert stage_authority['sha256']==entry['sha256'] and stage_authority['bytes']==entry['bytes']
   assert stage_authority['path']=='/usr/local/bin/.kubernetes1372-'+name+'-'+entry['sha256']+'.new'
   assert all(actual[k]==original[k] for k in FIELDS) and actual['path']==original['path']=='/usr/local/bin/'+name
   if host=='masternode' and name=='kubeadm':
    assert actual['sha256']==entry['sha256'] and actual['bytes']==entry['bytes'] and node['staging'][name] is None
    assert recovery['nativeBinaries']['before'][name]==original
   else:
    assert actual==original,'Only master kubeadm may have changed'
    staged=node['staging'][name];assert staged is not None
    assert staged['path']==stage_authority['path']=='/usr/local/bin/.kubernetes1372-'+name+'-'+entry['sha256']+'.new'
    assert staged['sha256']==entry['sha256'] and staged['bytes']==entry['bytes'] and all(staged[k]==original[k] for k in FIELDS)
 return {'passed':True,'mode':'staged-kubeadm','host':'masternode','proofSHA256':proof_sha,'failureRun':FAILURE,'authoritySHA256':manifest_sha,'originalRecoverySHA256':PINS['recovery'][1],'observationSHA256':proof['observation']['sha256'],'observationCapturedUTC':observation['capturedUTC'],'mutationPerformed':False,'closedKubeadmAddonPreflight':addon}

def intent_for(run_id):
 assert re.fullmatch('[a-f0-9]{32}',run_id)
 found=[]
 for path in sorted((H/'kubernetes-maintenance-receipts').glob(FAILURE+'-transfer-resume*.json')):
  assert path.resolve()==path
  data=json.loads(path.read_text())
  if data.get('runID')==run_id:found.append((path,data))
 assert len(found)==1,'Exactly one immutable submission intent required'
 path,data=found[0]
 return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},data

READ_ONLY_TASKS={
 'Gathering Facts',
 'kubernetes_security_patch : Verify independently managed CoreDNS declarations instead of an unused addon migration',
 'Qualify all native payloads backups drain policy and host preservation before any host changes',
 'Require the full original three-host inventory',
 'kubernetes_security_patch : Freeze exact original cluster and addon configuration on the master',
 'kubernetes_security_patch : Freeze original volume and controller readiness using the existing recovery guard',
 'kubernetes_security_patch : Freeze protected host bytes and exact original static manifests without exposing contents',
 'kubernetes_security_patch : Load qualified public authority and unchanged original drain tuples',
 'kubernetes_security_patch : Preserve all original current58 and offline identities before maintenance',
 'kubernetes_security_patch : Read all node conditions and Longhorn drain policy',
 'kubernetes_security_patch : Refuse partial or malformed transfer-resume settings',
 'kubernetes_security_patch : Require all original nodes Ready uncordoned and without pressure',
 'kubernetes_security_patch : Require exact prestaged native binaries original bytes metadata and fresh disk floor checks',
 'kubernetes_security_patch : Require explicit hash-bound authority even for full read-only preflight',
 'kubernetes_security_patch : Require only exact reviewed ephemeral mount tuples before cordoning',
 'kubernetes_security_patch : Validate explicit transfer-resume proof before any host-specific preflight',
 'kubernetes_security_patch : Validate signed native artifacts scans original raw backups and all-node image prestaging',
 'kubernetes_security_patch : Verify every current58 identity and backup with only the reviewed proxy image transition'}

def validate_closed_preflight(result_ref,log_ref,manifest_sha):
 result=json.loads(read_bound(result_ref));log=read_bound(log_ref).decode()
 settings=result['settings'];run_id=settings['kubernetes_security_patch_resume_run_id']
 if run_id=='b9a592f785cb45c69382c0e24ff0c5cc':
  assert result_ref['sha256']=='8176127d3f11784fae5859ca88a90254688926251c4d72828a2d8d223439bb79' and log_ref['sha256']=='9efc3a6e1f3d860c0220d7989e4af8ad78f1ddc9f8bc8fb9bd8ae2b4d89465a4','First closed failure pair changed'
 else:
  headers=[json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith('KUBERNETES_PATCH_INVOCATION ')]
  assert headers==[{'runID':run_id,'authoritySHA256':manifest_sha,'resumeProofSHA256':settings['kubernetes_security_patch_resume_kubeadm_with_transfer_proof_sha256']}],'Log does not bind this submitted invocation'
 assert result_ref['path']==str(H/('kubernetes-maintenance-receipts/'+run_id+'-result.json'))
 intent_ref,intent=intent_for(run_id)
 assert result['exitCode'] is not None and isinstance(result['exitCode'],int) and result['exitCode']!=0,'A successful or unterminated submission cannot be continued'
 started=datetime.datetime.fromisoformat(result['startedUTC']);finished=datetime.datetime.fromisoformat(result['finishedUTC'])
 assert started<=finished<=datetime.datetime.now(datetime.timezone.utc)
 assert settings['kubernetes_security_patch_apply'] is True
 assert settings['kubernetes_security_patch_manifest_sha256']==manifest_sha==intent['authoritySHA256']
 assert intent['submitted'] is True and intent['noUncertainReplay'] is True and intent['failureRun']==FAILURE
 assert intent['proofSHA256']==settings['kubernetes_security_patch_resume_kubeadm_with_transfer_proof_sha256']
 assert result['resumeQualification']['passed'] is True and result['resumeQualification']['failureRun']==FAILURE
 plays=re.findall(r'^PLAY \[([^\]]+)\]',log,re.M)
 assert plays and set(plays)=={'Qualify all hosts before any native Kubernetes binary change'},'A mutation play was entered'
 tasks=re.findall(r'^TASK \[([^\]]+)\]',log,re.M)
 assert tasks and set(tasks)<=READ_ONLY_TASKS,'A task outside exact read-only preflight was invoked'
 assert log.count('PLAY RECAP ')==1,'Missing or ambiguous terminal recap'
 recap=log.split('PLAY RECAP ',1)[1]
 matches=re.findall(r'^([^\s:]+)\s+:\s+ok=(\d+)\s+changed=(\d+)\s+unreachable=(\d+)\s+failed=(\d+)\s+skipped=(\d+)\s+rescued=(\d+)\s+ignored=(\d+)\s*$',recap,re.M)
 assert matches and len({row[0] for row in matches})==len(matches)
 assert {row[0] for row in matches}<={'masternode','workernode1','workernode2'} and 'masternode' in {row[0] for row in matches},'Unknown or missing host recap'
 assert all(int(row[2])==int(row[3])==int(row[6])==int(row[7])==0 for row in matches),'Changed, unreachable or masked host result is not closed read-only proof'
 assert sum(int(row[4]) for row in matches)>0 and 'AssertionError' in recap
 assert not re.search(r'^changed: \[',log,re.M),'Changed task output contradicts recap'
 return {'previousRunID':run_id,'previousIntent':intent_ref,'previousResult':result_ref,'previousLog':log_ref,'previousOutcome':'closed-before-mutation','finishedUTC':result['finishedUTC'],'hostRecap':{row[0]:{'ok':int(row[1]),'changed':int(row[2]),'unreachable':int(row[3]),'failed':int(row[4])} for row in matches},'mutationTasksInvoked':False}


ADDON_RUN='b6816a54662f4fc2839969b1eeb4e787'
ADDON_PINS={
 'result':('kubernetes-maintenance-receipts/'+ADDON_RUN+'-result.json','b3e9d1e00ac5dfbcdeae4995c64851e0d72a466af99b85a876bb283801ed8535'),
 'log':('kubernetes1372-native-rolling-qbit-headroom-continuation.log','df29786a4c9a45bd9bc18e3fe5074557036cff3f4df36399547d382aba407872'),
 'diagnostic':('kubernetes1372-native-dryrun-diagnostic.json','e0f990fea07df303399d84c17f9d3969bff8f7f928266e02dc7186892570c040'),
 'dns':('kubernetes1372-coredns-preflight-preservation.json','76ff2b1444af600c5f49b34f8c6a80b51e3c840d14661fd9811c03bc3daa0a74')}

def validate_closed_kubeadm_addon_preflight(result_ref,log_ref,manifest_sha):
 for key,reference in [('result',result_ref),('log',log_ref)]:
  relative,digest=ADDON_PINS[key]
  assert reference=={'path':str(H/relative),'sha256':digest},'Only the exact addon-preflight failure is supported'
 result=json.loads(read_bound(result_ref));log=read_bound(log_ref).decode();settings=result['settings']
 assert result['exitCode']==2 and settings['kubernetes_security_patch_apply'] is True
 assert settings['kubernetes_security_patch_resume_run_id']==ADDON_RUN and settings['kubernetes_security_patch_manifest_sha256']==manifest_sha
 assert datetime.datetime.fromisoformat(result['startedUTC'])<datetime.datetime.fromisoformat(result['finishedUTC'])<=datetime.datetime.now(datetime.timezone.utc)
 headers=[json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith('KUBERNETES_PATCH_INVOCATION ')]
 assert headers==[{'runID':ADDON_RUN,'authoritySHA256':manifest_sha,'resumeProofSHA256':settings['kubernetes_security_patch_resume_kubeadm_with_transfer_proof_sha256']}]
 intent_ref,intent=intent_for(ADDON_RUN)
 assert intent['submitted'] is True and intent['noUncertainReplay'] is True and intent['failureRun']==FAILURE and intent['authoritySHA256']==manifest_sha
 assert intent['proofSHA256']==settings['kubernetes_security_patch_resume_kubeadm_with_transfer_proof_sha256']
 tasks=re.findall(r'^TASK \[([^\]]+)\]',log,re.M)
 boundary='kubernetes_security_patch : Upgrade the native control-plane manifests preserving etcd certificates and other addons'
 assert tasks.count(boundary)==1 and tasks[tasks.index(boundary):]==[boundary,'kubernetes_security_patch : Preserve failure isolation and original recovery evidence']
 assert log.count('PLAY RECAP ')==1 and 'fatal: [masternode]: FAILED!' in log
 diagnostic_ref={'path':str(H/ADDON_PINS['diagnostic'][0]),'sha256':ADDON_PINS['diagnostic'][1]}
 diagnostic=json.loads(read_bound(diagnostic_ref))
 assert diagnostic['exitCode']==1 and 'error execution phase preflight: preflight checks failed' in diagnostic['stderr']
 assert re.findall(r'\[ERROR ([^\]]+)\]',diagnostic['stderr'])==['CoreDNSUnsupportedPlugins','CoreDNSMigration']
 assert "start version '1.15.0' not supported" in diagnostic['stderr']
 dns_ref={'path':str(H/ADDON_PINS['dns'][0]),'sha256':ADDON_PINS['dns'][1]}
 dns=json.loads(read_bound(dns_ref));assert dns['failedRunID']==ADDON_RUN and dns['hostAndStaticBytesExactlyPreserved'] is True
 assert datetime.datetime.fromisoformat(dns['capturedUTC'])>datetime.datetime.fromisoformat(result['finishedUTC'])
 return {'previousRunID':ADDON_RUN,'previousIntent':intent_ref,'previousResult':result_ref,'previousLog':log_ref,'diagnostic':diagnostic_ref,'coreDNSBaseline':dns_ref,
  'previousOutcome':'kubeadm-invoked-addon-preflight-failure','finishedUTC':result['finishedUTC'],'kubeadmUpgradeInvoked':True,'requiresFreshOriginalBytesAndQualifiedUncordon':True}

def main():
 p=argparse.ArgumentParser();p.add_argument('--proof',required=True,type=Path);p.add_argument('--sha256',required=True);p.add_argument('--manifest',required=True,type=Path);p.add_argument('--manifest-sha256',required=True);p.add_argument('--run-id');a=p.parse_args()
 result=validate(a.proof,a.sha256,a.manifest,a.manifest_sha256)
 if a.run_id:
  assert re.fullmatch('[a-f0-9]{32}',a.run_id)
  _,intent=intent_for(a.run_id)
  base={'runID':a.run_id,'proofSHA256':a.sha256,'authoritySHA256':a.manifest_sha256,'failureRun':FAILURE,'submitted':True,'noUncertainReplay':True}
  assert all(intent.get(k)==v for k,v in base.items()),'Resume invocation intent differs'
  if 'closedKubeadmAddonPreflight' in intent:
   closed=intent['closedKubeadmAddonPreflight']
   assert validate_closed_kubeadm_addon_preflight(closed['previousResult'],closed['previousLog'],a.manifest_sha256)==closed
   assert intent['parentIntent']==closed['previousIntent'] and result['closedKubeadmAddonPreflight']==closed
  elif 'closedPreflight' in intent:
   closed=intent['closedPreflight']
   qualified=validate_closed_preflight(closed['previousResult'],closed['previousLog'],a.manifest_sha256)
   assert qualified==closed and intent['parentIntent']==closed['previousIntent']
   assert datetime.datetime.fromisoformat(result['observationCapturedUTC'].replace('Z','+00:00'))>datetime.datetime.fromisoformat(closed['finishedUTC']),'Fresh state proof must follow closed outcome'
  else:assert intent==base,'Unknown submission intent fields'
 print(json.dumps(result))
if __name__=='__main__':main()
