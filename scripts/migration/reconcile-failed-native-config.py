"""Reconcile one allocation-proven failed native configuration after full core success."""
import argparse
import ast
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import sys

F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028'
RUN='b6816a54662f4fc2839969b1eeb4e787'
TARGET='/etc/kubernetes/tmp/kubernetes1372-5q_tc2oa'
AUTH='c21016a7c150f50f66c3f86b1433412363409f7e6ecbce913c3414afdbf03ba8'
HELPER_SHA='c30caeb5a7679f9ec9d4251bc9619004d7f8d4ea2dfd990cc9c18b864a56fe4b'
RECOVERY='kubernetes-recovery-'+RUN+'/masternode-q5ovnmhr.json'
PINS={RECOVERY:'2720615a8b50367b02964fec516e96ed21764cf02d897bad9a7e4ccd2bee9b13',
 RECOVERY+'.allocation.json':'c4ba284ebe1086cc8632c5ec2f9fb69cfda455bf56982202200d66ceb8f0959e',
 RECOVERY+'.native.json':'9d9870e12cf52931b83fada9f00b6dde42949085f7ad6ce306e0eb18efd8014e',
 'kubernetes-maintenance-receipts/'+RUN+'-result.json':'b3e9d1e00ac5dfbcdeae4995c64851e0d72a466af99b85a876bb283801ed8535'}
PREFIX=H/('kubernetes1372-failed-native-config-'+RUN)

OUTPUT_PREFIX=PREFIX
OLD_SOURCE_SHA='2c072c7e698ae1994adac0b70e7cecbee43004494cd5fe4b9d1f425aef31195c'
CLOSED_FAILURE_SHA='2ba61f30788d745dd17be27bcefb8ef49420046c831e2d4822b0660950d2ec07'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def output(suffix):return Path(str(OUTPUT_PREFIX)+'-'+suffix+'.json')
def save(path,value):
 with path.open('x') as stream:
  json.dump(value,stream,indent=2);stream.flush();os.fsync(stream.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 return {'path':str(path),'sha256':sha(path)}

def close_transport_failure(path,digest):
 expected=Path(str(PREFIX)+'-failure.json')
 assert path==expected and path.resolve()==path and digest==CLOSED_FAILURE_SHA and sha(path)==digest
 failure=json.loads(path.read_text())
 assert failure=={'targetRetainedOrPartiallyRemoved':TARGET,'reason':'AssertionError','retryProhibited':True,'intentPresent':False,'noOtherTargetsAuthorized':True}
 assert all(not Path(str(PREFIX)+'-'+name+'.json').exists() for name in ('inventory','intent','result')),'A submitted or observed native operation cannot be reclassified'
 witness=Path(str(PREFIX)+'-original-controller.py');assert witness.resolve()==witness and sha(witness)==OLD_SOURCE_SHA
 tree=ast.parse(witness.read_bytes())
 assignments=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='carrier' for t in n.targets)]
 assert len(assignments)==1
 expression=assignments[0].value
 assert isinstance(expression,ast.Call) and isinstance(expression.func,ast.Attribute) and expression.func.attr=='replace'
 carrier=ast.literal_eval(expression.func.value).replace('COMMAND',repr(['python3','-B','-c','pass']))
 try:compile(carrier,'<closed-original-native-carrier>','exec')
 except SyntaxError as error:assert error.lineno==5
 else:raise AssertionError('Original carrier must fail before any native code can execute')
 return {'originalFailure':{'path':str(path),'sha256':digest},'originalSource':{'path':str(witness),'sha256':OLD_SOURCE_SHA},
  'deterministicCarrierError':'SyntaxError','errorLine':5,'nativeGuardInvoked':False,'originalIntentPresent':False,
  'disposition':'closed-transport-syntax-before-native-execution','differentOutputNamespace':True}

def regenerate(original,plan):
 files=[]
 for name in ('kube-apiserver','kube-controller-manager','kube-scheduler'):
  old=original['preservation']['staticPods'][name];spec=copy.deepcopy(old['spec'])
  assert len(spec['containers'])==1
  spec['containers'][0]['image']=plan['images'][name]['reference']
  content=json.dumps([{'op':'replace','path':'/spec','value':spec},{'op':'replace','path':'/metadata','value':old['metadata']}]).encode()
  files.append({'path':TARGET+'/patches/'+name+'+json.json','bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
 # Exact original 447-byte profile, before the separately reviewed DNS change.
 content=("apiVersion: kubeadm.k8s.io/v1beta4\nkind: UpgradeConfiguration\napply:\n"
  "  kubernetesVersion: v1.37.2\n  etcdUpgrade: false\n  certificateRenewal: false\n  imagePullPolicy: Never\n"
  "  patches:\n    directory: "+TARGET+"/patches\n"
  "  skipPhases: [addon, kubelet-config, kubeconfig, bootstrap-token]\nnode:\n"
  "  etcdUpgrade: false\n  certificateRenewal: false\n  imagePullPolicy: Never\n"
  "  skipPhases: [addon, kubelet-config, kubeconfig]\n").encode()
 assert len(content)==447 and hashlib.sha256(content).hexdigest()=='96834131ac34f63cbbdcb41040a1aa0cd957a41574a3ba25005bcbd731377616'
 files.append({'path':TARGET+'/upgrade.yaml','bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
 return sorted(files,key=lambda x:x['path'])

def main():
 global OUTPUT_PREFIX
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('mode',choices=['inventory','apply'],nargs='?',default='inventory')
 parser.add_argument('--success',required=True,help='Exact terminal runner result relative to H')
 parser.add_argument('--success-sha256',required=True)
 parser.add_argument('--authority',type=Path,required=True);parser.add_argument('--authority-sha256',required=True)
 parser.add_argument('--after-closed-transport-failure',type=Path);parser.add_argument('--after-closed-transport-failure-sha256')
 args=parser.parse_args();os.umask(0o077)
 password=sys.stdin.buffer.readline(130).removesuffix(b'\n')
 assert 0<len(password)<=128 and not any(x in password for x in (b'\n',b'\r',b'\0'))
 os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD',None)
 assert bool(args.after_closed_transport_failure)==bool(args.after_closed_transport_failure_sha256)
 closed=None
 if args.after_closed_transport_failure:
  closed=close_transport_failure(args.after_closed_transport_failure,args.after_closed_transport_failure_sha256)
  OUTPUT_PREFIX=Path(str(PREFIX)+'-transport-repair')
 assert F.is_mount() and H.resolve()==H and os.getuid()==1000
 volume=subprocess.run(['findmnt','-n','-o','UUID','--target',str(F)],capture_output=True,text=True,timeout=10)
 assert volume.returncode==0 and volume.stdout.strip()=='3c792469-ea0e-4a2c-98e8-1185b141607b'
 assert not output('intent').exists() and not output('result').exists() and not output('failure').exists(),'Existing attempt or safety refusal protects this exact target; no retry'
 repo=Path(__file__).resolve().parents[2]
 support=runpy.run_path(str(repo/'scripts/migration/reconcile-kubernetes-vendor.py'))
 plan,success=support['terminal'](H,F,args.success,args.success_sha256)
 assert args.authority.resolve()==args.authority and args.authority.parent==H and sha(args.authority)==args.authority_sha256==AUTH==success['authoritySHA256']
 assert json.loads(args.authority.read_text())==plan
 originals={}
 for relative,digest in PINS.items():
  path=H/relative;assert path.resolve()==path and path.is_file() and sha(path)==digest
  originals[relative]=json.loads(path.read_text())
 failure=originals['kubernetes-maintenance-receipts/'+RUN+'-result.json']
 assert failure['exitCode']==2 and failure['finishedUTC'] and failure['settings']['kubernetes_security_patch_manifest_sha256']==AUTH
 terminal=json.loads(Path(success['path']).read_text())
 assert dt.datetime.fromisoformat(terminal['finishedUTC'])>dt.datetime.fromisoformat(failure['finishedUTC'])
 original=originals[RECOVERY];allocation=originals[RECOVERY+'.allocation.json'];native=originals[RECOVERY+'.native.json']
 assert original['host']==allocation['host']=='masternode' and original['authoritySHA256']==allocation['authoritySHA256']==AUTH
 assert allocation['recoveryReceipt']==str(H/RECOVERY) and allocation['allocation']==native['allocation']
 assert native['nativeDirectory']==TARGET and native['allocation']['directory']['path']==TARGET
 assert native['files']==regenerate(original,plan),'Regenerated bytes must match the exact failed config before cleanup'
 # Real live hashes, Go builds, native versions, node UIDs, Ready and runtime.
 live=support['live'](plan,repo)
 helper=repo/'k8s-rewrite/ansible-playbook/roles/kubernetes_security_patch/files/native_artifacts.py'
 assert sha(helper)==HELPER_SHA,'Use the unchanged qualified full Linux reference guard'
 recipe={'owner':'kubernetes1372-failed-native-config','host':'masternode','target':TARGET,'authority':{'path':str(args.authority),'sha256':AUTH},
  'success':success,'closedTransportFailure':closed,'sourceSHA256':sha(Path(__file__)),'nativeHelperSHA256':HELPER_SHA,'protectedSources':PINS,
  'regeneration':'regenerate() using original b681 preservation + exact authority images and original 447-byte UpgradeConfiguration; all hashes must match native receipt',
  'lastConsumer':'Failed b681 kubeadm invocation terminated; full successor three-host upgrade completed and live hashes verified',
  'excluded':'Original89 directory without allocation; all prior cleanup refusals; dryrun2913256334; raw originals; binary staging; all other paths',
  'physicalControllerVolume':str(F),'physicalControllerUUID':volume.stdout.strip(),'nativeAllocation':native['allocation'],'files':native['files'],'live':live}
 payload={'nativeDirectory':TARGET,'allocation':native['allocation']} if args.mode=='inventory' else {'nativeDirectory':TARGET,'nativeInventory':native,'binaryStaging':[],'hostVerified':True}
 if args.mode=='apply':
  prior=json.loads(output('inventory').read_text())
  assert prior['sourceSHA256']==recipe['sourceSHA256'] and prior['authority']==recipe['authority'] and prior['success']==success and prior['nativeInventory']==native
 # Read the credential before launching children; isolated validation pipe avoids
 # the closed sudo -k -v cache bug. Payload JSON remains on the original fd0.
 command=['sudo','-n','python3','-B','-c',helper.read_text(),'record' if args.mode=='inventory' else 'cleanup']
 carrier=r"""import os,subprocess,sys
password=b''
while True:
 b=os.read(0,1)
 if b==b'\n':break
 assert b and len(password)<128
 password+=b
reset=subprocess.run(['sudo','-k'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
assert reset.returncode==0
check=subprocess.run(['sudo','-S','-p','','-v'],input=password+b'\n',stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
password=None
assert check.returncode==0,'Protected authentication failed'
sys.exit(subprocess.run(COMMAND,stdin=0).returncode)
""".replace('COMMAND',repr(command))
 compile(carrier,'<native-config-auth-carrier>','exec')
 if args.mode=='apply':save(output('intent'),recipe)
 try:
  run=subprocess.run(support['SSH']+['james@192.168.0.4',shlex.join(['python3','-B','-c',carrier])],input=password+b'\n'+json.dumps(payload).encode(),capture_output=True,timeout=60)
  password=None
  assert run.returncode==0 and len(run.stdout)<128*1024,'Exact native configuration observation/cleanup failed'
  result=json.loads(run.stdout)
  if args.mode=='inventory':
   assert result==native
   recipe['nativeInventory']=result
   print(json.dumps(save(output('inventory'),recipe)))
  else:
   recipe['cleanup']=result
   assert result['originalKubeadmBackupsTouched'] is False and result['windowsRecoveryClaimed'] is False
   receipt=save(output('result'),recipe)
   print(json.dumps(receipt));assert not result['retained'],'Exact target retained; no retry or alternate cleanup'
 except Exception as error:
  if not output('failure').exists():save(output('failure'),{'targetRetainedOrPartiallyRemoved':TARGET,'reason':type(error).__name__,'retryProhibited':True,'intentPresent':output('intent').exists(),'noOtherTargetsAuthorized':True})
  raise
 finally:password=None

if __name__=='__main__':
 try:main()
 except Exception as error:
  if H.is_dir() and not output('failure').exists():
   save(output('failure'),{'targetRetainedOrPartiallyRemoved':TARGET,'reason':type(error).__name__,'retryProhibited':True,'intentPresent':output('intent').exists(),'noOtherTargetsAuthorized':True})
  raise
