"""Read-only live acceptance of headroom and targeted chart hardening.

Default behavior asserts the original disk thresholds before further checks.
Explicit --report-open-headroom collects disk shortfalls, continues the existing
independent data/runtime checks, then saves a failing receipt and exits nonzero.
Those independent passes never close headroom acceptance. Other unexpected
failures still assert immediately without writing a completion receipt.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess

F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028'
SSH=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile=/home/brajam/.ssh/known_hosts','-i','/home/brajam/.ssh/id_ed25519','-p','2002']

def ssh(address,command,body=None,timeout=45):
 p=subprocess.run(SSH+['james@'+address,shlex.join(command)],input=body,capture_output=True,timeout=timeout)
 assert p.returncode==0 and len(p.stdout)<8*1024**2,('bounded_remote_observation_failed',p.returncode)
 return p.stdout

def kube(args,body=None):return json.loads(ssh('192.168.0.4',['kubectl']+args,body))

def flare_security_spec(spec):
 expected={'runAsNonRoot':True,'runAsUser':1000,'runAsGroup':1000,'seccompProfile':{'type':'RuntimeDefault'}}
 assert all(spec.get('securityContext',{}).get(k)==v for k,v in expected.items()),'Flare Pod security context differs'
 assert spec.get('automountServiceAccountToken') is False
 assert not any('serviceAccountToken' in s for v in spec.get('volumes',[]) for s in v.get('projected',{}).get('sources',[]))
 assert len(spec['containers'])==1 and spec['containers'][0]['name']=='flaresolverr'
 context=spec['containers'][0].get('securityContext',{})
 assert context.get('allowPrivilegeEscalation') is False and context.get('privileged',False) is False
 assert context.get('capabilities',{}).get('drop')==['ALL'] and not context.get('capabilities',{}).get('add')
 assert all(context.get(k,v)==v for k,v in expected.items()),'Container overrides Pod security context'

def flare_process_status(value):
 assert value['tokenAbsent'] is True
 status=value['status']
 assert status['Uid'].split()==['1000']*4 and status['Gid'].split()==['1000']*4
 assert int(status['CapEff'],16)==0 and status['NoNewPrivs']=='1' and status['Seccomp']=='2'

def verify_flare_least_privilege(pod,revision):
 release=kube(['-n','flux-system','get','helmrelease','flaresolverr','-o','json'])
 assert release['status']['observedGeneration']==release['metadata']['generation']
 assert any(c['type']=='Ready' and c['status']=='True' for c in release['status']['conditions'])
 current=release['status']['history'][0]
 assert len(revision)==40 and all(c in '0123456789abcdef' for c in revision)
 expected_version='0.1.3+'+revision[:12]
 assert current['chartVersion']==expected_version and current['status']=='deployed','Require deployed Flare chart0.1.3 bound to exact revision'
 deployment=kube(['-n','plex','get','deployment','flaresolverr','-o','json'])
 assert deployment['status']['observedGeneration']==deployment['metadata']['generation']
 flare_security_spec(deployment['spec']['template']['spec']);flare_security_spec(pod['spec'])
 replica=kube(['-n','plex','get','replicaset',next(o['name'] for o in pod['metadata']['ownerReferences'] if o.get('controller')),'-o','json'])
 assert any(o.get('controller') and o['uid']==deployment['metadata']['uid'] for o in replica['metadata']['ownerReferences'])
 assert any(o.get('controller') and o['uid']==replica['metadata']['uid'] for o in pod['metadata']['ownerReferences'])
 flare_security_spec(replica['spec']['template']['spec'])
 code="import json,os;wanted={'Uid','Gid','CapEff','NoNewPrivs','Seccomp'};status={k:v.strip() for k,v in (line.split(':',1) for line in open('/proc/1/status')) if k in wanted};print(json.dumps({'status':status,'tokenAbsent':not os.path.lexists('/var/run/secrets/kubernetes.io/serviceaccount/token')}))"
 observed=json.loads(ssh('192.168.0.4',['kubectl','-n','plex','exec',pod['metadata']['name'],'-c','flaresolverr','--','python3','-B','-c',code]))
 flare_process_status(observed)
 after=kube(['-n','plex','get','pod',pod['metadata']['name'],'-o','json'])
 assert after['metadata']['uid']==pod['metadata']['uid'] and not after['metadata'].get('deletionTimestamp')
 states=lambda p:[(s['name'],s['containerID'],s['restartCount'],s['ready']) for s in p['status']['containerStatuses']]
 assert states(after)==states(pod),'Flare restarted during process observation'
 return {'chartVersion':expected_version,'deploymentUID':deployment['metadata']['uid'],'podUID':pod['metadata']['uid'],'process1':observed,'browserCompatibilityVerified':False}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--revision',required=True);p.add_argument('--receipt',required=True,type=Path);p.add_argument('--flare-least-privilege',action='store_true');p.add_argument('--report-open-headroom',action='store_true',help='Record unmet original disk thresholds after independent checks; still exit nonzero');a=p.parse_args()
 assert F.is_mount() and a.receipt.parent.resolve()==H and not a.receipt.exists()
 repo=Path(__file__).resolve().parents[2]
 lib=runpy.run_path(str(repo/'k8s-rewrite/ansible-playbook/roles/longhorn_engine_upgrade/files/upgrade.py'))
 lib['controls']()
 claims=kube(['get','pvc','-A','-o','json'])['items']
 baseline=F/'platform-upstream-review-20261027/final-fleet-post-security-20261028/inventory.json'
 old=json.loads(baseline.read_text())
 keys=lambda x:(x['metadata']['namespace'],x['metadata']['name'],x['metadata']['uid'],x['spec']['volumeName'])
 assert {keys(x) for x in claims}=={(x['namespace'],x['name'],x['uid'],x['volumeName']) for x in old['claims']}
 assert len(claims)==58 and all(x['status']['phase']=='Bound' for x in claims)
 pv=kube(['get','pv','-o','json'])['items'];assert sum(v['spec'].get('csi',{}).get('driver')=='smb.csi.k8s.io' for v in pv)==14
 disks=[]
 for name,ip in [('masternode','192.168.0.4'),('workernode2','192.168.0.5')]:
  fs=json.loads(ssh(ip,['python3','-B','-c',"import os,json;s=os.statvfs('/');print(json.dumps({'capacity':s.f_blocks*s.f_frsize,'free':s.f_bfree*s.f_frsize,'usable':s.f_bavail*s.f_frsize}))"]))
  fs['node']=name;fs['headroomAboveGuard']=fs['free']-(fs['capacity']//4+1+512*1024**2)
  if a.report_open_headroom:
   fs['requiredHeadroomAboveGuardBytes']=2*1024**3
   fs['requiredUsableBytes']=15*1024**3
   fs['guardBytes']=fs['capacity']//4+1+512*1024**2
   fs['headroomShortfallBytes']=max(0,2*1024**3-fs['headroomAboveGuard'])
   fs['usableShortfallBytes']=max(0,15*1024**3-fs['usable'])
   fs['headroomAcceptancePassed']=fs['headroomAboveGuard']>=2*1024**3 and fs['usable']>=15*1024**3
  else:
   assert fs['headroomAboveGuard']>=2*1024**3 and fs['usable']>=15*1024**3
  disks.append(fs)
 flux=kube(['-n','flux-system','get','kustomization','migration-releases','-o','json']);assert flux['status']['lastAppliedRevision']=='validated@sha1:'+a.revision
 assert any(x['type']=='Ready' and x['status']=='True' for x in flux['status']['conditions'])
 assert kube(['-n','flux-system','get','helmrelease','bortus','-o','json'])['spec']['suspend'] is True
 pods=kube(['get','pods','-A','-o','json'])['items'];solver=[v for v in pods if v['metadata']['namespace']=='plex' and v['metadata'].get('labels',{}).get('app')=='flaresolverr' and not v['metadata'].get('deletionTimestamp')]
 assert len(solver)==1;solver=solver[0];assert solver['spec']['automountServiceAccountToken'] is False
 assert not any('serviceAccountToken' in s for v in solver['spec'].get('volumes',[]) for s in v.get('projected',{}).get('sources',[]))
 assert all(x.get('ready') for x in solver['status']['containerStatuses'])
 flare_least_privilege=verify_flare_least_privilege(solver,a.revision) if a.flare_least_privilege else None
 policy=kube(['-n','plex','get','networkpolicy','flaresolverr-ingress','-o','json'])
 assert policy['spec']=={'podSelector':{'matchLabels':{'app':'flaresolverr'}},'policyTypes':['Ingress'],'ingress':[{'from':[{'podSelector':{}}],'ports':[{'protocol':'TCP','port':8191}]}]}
 namespace_checks=[]
 for ns in ('whoami','http-echo'):
  namespace=kube(['get','namespace',ns,'-o','json']);labels=namespace['metadata']['labels'];assert labels['pod-security.kubernetes.io/enforce']=='baseline' and labels['pod-security.kubernetes.io/enforce-version']=='v1.37'
  dep=kube(['-n',ns,'get','deployment',ns,'-o','json']);template=dep['spec']['template'];probe={'apiVersion':'v1','kind':'Pod','metadata':{'generateName':'hardening-admission-check-','namespace':ns,'labels':template['metadata'].get('labels',{})},'spec':template['spec']}
  accepted=kube(['create','--dry-run=server','-f','-','-o','json'],json.dumps(probe).encode())
  # Admission may assign a synthetic UID during server dry-run. Check persistence
  # directly instead of treating that response metadata as a created Pod.
  name=accepted['metadata']['name'];assert name.startswith('hardening-admission-check-')
  absent=ssh('192.168.0.4',['kubectl','-n',ns,'get','pod',name,'--ignore-not-found','-o','json']);assert not absent.strip()
  namespace_checks.append({'namespace':ns,'baselineVersion':'v1.37','actualWorkloadTemplateServerDryRunPassed':True,'PodCreated':False})
 failures=[]
 for kind in ('deployments','statefulsets','daemonsets'):
  for v in kube(['get',kind,'-A','-o','json'])['items']:
   desired=v['status'].get('desiredNumberScheduled',0) if kind=='daemonsets' else v['spec'].get('replicas',1)
   ready=v['status'].get('numberReady',0) if kind=='daemonsets' else v['status'].get('readyReplicas',0)
   if ready<desired:failures.append(v['metadata']['namespace']+'/'+v['metadata']['name'])
 assert not failures
 report={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':True,'sourceSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'chartsRevision':a.revision,'claimBaselineSHA256':hashlib.sha256(baseline.read_bytes()).hexdigest(),'original58BoundClaimBindingsPreserved':True,'SMBVolumes':14,'disks':disks,'solverPodUID':solver['metadata']['uid'],'solverTokenProjectionAbsent':True,'solverNamespaceIngressPolicyVerified':True,'baselineAdmission':namespace_checks,'allDesiredControllersAvailable':True,'BORTUSReleaseHeld':True,'runtimeMutationsPerformed':False,'onlyServerDryRunRequests':True}
 if a.flare_least_privilege:
  report['flareLeastPrivilege']=flare_least_privilege
  report['readOnlyPodExecPerformed']=True
  report['onlyServerDryRunRequests']=False
 if a.report_open_headroom:
  headroom_passed=all(d['headroomAcceptancePassed'] for d in disks)
  report['headroomAcceptancePassed']=headroom_passed
  report['independentRuntimeAndDataChecksPassed']=True
  report['passed']=headroom_passed
  report['overallPassed']=headroom_passed
  report['openAcceptanceGates']=[] if headroom_passed else ['headroom']
 with a.receipt.open('x') as out:json.dump(report,out,indent=2)
 print(json.dumps({'passed':report['passed'],'receipt':str(a.receipt),'disks':disks}))
 if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
