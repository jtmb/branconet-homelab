"""Explicit transport repair after proven sudo denial before any native stage write."""
import argparse
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
import threading

OLD_SHA='9ef6a287adadc82852b633a9ff282a065c80c01b9c4b60686a62dc9458a73c41'
REMOTE_SHA='c124d58ae18b02ceb02ca835dab8aa283a4a52b840c8426168c6de290e9d1378'
PROOFS={
 'kubernetes1372-stage-sudo-journal-projection.json':'f6f53d9395b839175abb6894e85b8c0edcc3e1b2c77c3d990cfd866b8e3014e5',
 'kubernetes1372-native-stage-after-transport-failure.json':'7b25f7b4d1a6fd7dfb3a27412de41dfd47df8fc93a32c228a8794c2a95a618b2',
 'kubernetes1372-native-auth-carrier-comparison.json':'a21f3b32760c62877b2c651febe694009c8cbcac64f7d8b9843e973b540c5e27'}
INTENT_SHA='65bfc39c3ca371c7c1c5c926be33caee979c615677221bb407d4ce27ef312741'

def corrected_invoke(base,host,request,password,blob):
 code=base['SOURCE']+'\nprint(json.dumps(stage('+repr(request)+')))\n'
 argv=['sudo','-n','--','python3','-B','-c',code]
 wrapper=('import os,subprocess,sys\nsecret=bytearray()\n'
  'while True:\n'
  ' b=os.read(0,1)\n'
  ' if b==b"\\n": break\n'
  ' assert b and len(secret)<128\n'
  ' secret.extend(b)\n'
  'reset=subprocess.run(["sudo","-k"],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n'
  'assert reset.returncode==0,"Timestamp reset failed"\n'
  'auth=subprocess.run(["sudo","-S","-p","","-v"],input=bytes(secret)+b"\\n",stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n'
  'secret[:]=b"\\0"*len(secret)\n'
  'assert auth.returncode==0,"Privilege authentication failed"\n'
  'sys.exit(subprocess.call('+repr(argv)+',stdin=0))\n')
 process=subprocess.Popen(base['shell'](host,shlex.join(['python3','-B','-c',wrapper])),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 errors=process.stderr;process.stderr=None
 diagnostic={'stderrBytes':0,'stderrComplete':False};error_hash=hashlib.sha256()
 def drain_errors():
  try:
   for block in iter(lambda:errors.read(65536),b''):
    error_hash.update(block);diagnostic['stderrBytes']+=len(block)
  finally:
   errors.close();diagnostic['stderrSHA256']=error_hash.hexdigest();diagnostic['stderrComplete']=True
 reader=threading.Thread(target=drain_errors,daemon=True);reader.start()
 try:
  process.stdin.write(password+b'\n')
  with blob.open('rb') as stream:
   for block in iter(lambda:stream.read(1024**2),b''):process.stdin.write(block)
  process.stdin.close();process.stdin=None
  output,_=process.communicate(timeout=600);reader.join(timeout=5)
  diagnostic['exitCode']=process.returncode
  assert process.returncode==0,'Repair transport failed; retain exact intent/target, no replay'
  assert len(output)<1024**2
  result=json.loads(output);result['carrier']=dict(diagnostic);return result
 except Exception as error:
  diagnostic['exitCode']=process.poll()
  error.carrier_diagnostic=dict(diagnostic)
  raise
 finally:
  if process.stdin is not None:
   try:process.stdin.close()
   except BrokenPipeError:pass
  # Never terminate/replay an uncertain remote process or overwrite its file.

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('mode',choices=['stage','observe'])
 args=parser.parse_args();password=None
 if args.mode=='stage':
  line=sys.stdin.buffer.readline(130)
  assert line.endswith(b'\n') and 1<len(line)<=129 and not any(x in line[:-1] for x in (b'\r',b'\n',b'\0'))
  password=line[:-1];line=None
 # Protected input is consumed before any SSH, and only the carrier changes.
 os.umask(0o077)
 repo=Path(__file__).resolve().parents[2]
 source=repo/'k8s-rewrite/ansible-playbook/roles/kubernetes_security_patch/files/staging.py'
 remote=source.with_name('stage_remote.py')
 digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 assert digest(source)==OLD_SHA and digest(remote)==REMOTE_SHA
 base=runpy.run_path(str(source));R=base['R'];H=base['H'];T=R/'transport-repair'
 assert os.getuid()==1000 and base['F'].is_mount() and R.resolve()==R
 assert R.stat().st_uid==1000 and not R.stat().st_mode&0o077
 assert base['sha'](base['VENDOR'])==base['VENDOR_SHA']
 vendor=json.loads(base['VENDOR'].read_text());names=base['NAMES'];nodes=base['NODES']
 ownership=json.loads((R/'ownership.json').read_text())
 assert ownership['controllerSHA256']==OLD_SHA and ownership['sourceSHA256']==REMOTE_SHA
 assert ownership['vendor']==base['ref'](base['VENDOR'])
 checkpoint=base['load_ref'](ownership['checkpoint'])
 capture=json.loads((R/'capture.json').read_text());base['fresh'](capture['capturedAt'])
 assert checkpoint['clusterNodes']==capture['nodeUIDs']
 old_intent=R/'masternode-kubeadm-intent.json'
 assert digest(old_intent)==INTENT_SHA and not (R/'masternode-kubeadm-after.json').exists()
 assert not (R/'binary-evidence.json').exists()
 for host in nodes:
  for name in names:
   if (host,name)!=('masternode','kubeadm'):
    assert not (R/(host+'-'+name+'-intent.json')).exists() and not (R/(host+'-'+name+'-after.json')).exists()
 old=json.loads(old_intent.read_text());assert old['sourceSHA256']==REMOTE_SHA and old['nodeUID']==capture['nodeUIDs']['masternode']
 assert base['remote'].identity(old['before'])==base['remote'].identity(capture['nodes']['masternode'])
 proofs={}
 for name,value in PROOFS.items():
  path=H/name;assert digest(path)==value
  proofs[name]=json.loads(path.read_text())
 journal=proofs['kubernetes1372-stage-sudo-journal-projection.json']
 assert journal['exitCode']==0 and not any(e['sessionOpened'] for e in journal['events'])
 denial=[e for e in journal['events'] if e['passwordRequired'] and e['commandLogged']]
 assert len(denial)==1 and denial[0]['timestamp']=='1793251564835373' and denial[0]['messageSHA256']=='7d4f72ffee41534a70f9435fd909fe28089a5cb3f4ba741f91453bec73240b90'
 assert any(e['stagePayloadCommand'] for e in journal['events'])
 intent_time=dt.datetime.fromisoformat(old['capturedAt']).timestamp()
 assert 0<=int(denial[0]['timestamp'])/1000000-intent_time<5,'Denial does not belong to original stage intent'
 absence=proofs['kubernetes1372-native-stage-after-transport-failure.json']
 assert set(absence)==set(nodes.values()) and all(set(v)==set(names) and all(x is None for x in v.values()) for v in absence.values())
 comparison=proofs['kubernetes1372-native-auth-carrier-comparison.json']
 assert comparison['harmlessReadOnlyPayload'] is True
 assert comparison['original']['authenticationExit']==0 and comparison['original']['payloadExit']==1 and comparison['original']['passwordRequired'] is True
 corrected=comparison['corrected']
 assert corrected['authenticationExit']==corrected['payloadExit']==0 and corrected['passwordRequired'] is False
 assert json.loads(corrected['stdout'])=={'uid':0,'payload':'PUBLIC-BINARY-STREAM-PROBE'}
 assert corrected['stderrSHA256']==hashlib.sha256(b'').hexdigest()
 backups=json.loads((R/'backups.json').read_text())
 for name in names:
  entry=vendor['binaries'][name];blob=Path(entry['blob']['path'])
  assert base['ref'](blob)['sha256']==entry['sha256'] and blob.stat().st_size==entry['bytes']
  original=Path(backups[name]['path'])
  assert base['ref'](original)==backups[name] and backups[name]['sha256']==base['OLD'][name]
  assert original.stat().st_size==capture['nodes']['masternode']['binaries'][name]['bytes']
 all_nodes=base['global_observe'](vendor,capture)
 if args.mode=='stage':
  assert not T.exists(),'Repair operation already has an owner; no repeated write submission'
  assert all(value is None for node in all_nodes['nodes'].values() for value in node['stages'].values()),'Existing partial/authored target is permanently protected'
  budgets={host:base['remote'].budget(value,vendor) for host,value in all_nodes['nodes'].items()}
  T.mkdir(mode=0o700)
  base['save'](T/'ownership.json',{'owner':'kubernetes1372-security-patch-transport-repair','root':str(T),'physicalVolume':str(base['F']),
   'repairSourceSHA256':digest(Path(__file__).resolve()),'originalControllerSHA256':OLD_SHA,'immutableRemoteSHA256':REMOTE_SHA,
   'originalCapture':base['ref'](R/'capture.json'),'originalOwnership':base['ref'](R/'ownership.json'),'originalBackups':base['ref'](R/'backups.json'),
   'proofs':{name:base['ref'](H/name) for name in PROOFS},'generated':'Original source copy; disposition; new before/intent/after/stage receipts and binary-evidence.json',
   'regeneration':'Same qualified original vendor blobs, original remote helper. This repair is one-shot, not an uncertain retry.',
   'lastConsumer':'Native role atomic install after complete new authority preflight','protected':'All original ownership/intent/failure records, originals and unique repair evidence'})
  with (T/'original-staging.py').open('xb') as stream:
   stream.write(source.read_bytes());stream.flush();os.fsync(stream.fileno())
  assert digest(T/'original-staging.py')==OLD_SHA
  base['save'](T/'original-intent-disposition.json',{'disposition':'closed-auth-before-exec','originalIntent':base['ref'](old_intent),
   'denialTimestamp':denial[0]['timestamp'],'denialMessageSHA256':denial[0]['messageSHA256'],
   'proofs':{name:base['ref'](H/name) for name in PROOFS},'freshAllNinePathsAbsent':True,'originalRemoteExecuted':False,
   'originalIntentModified':False,'originalFailureEvidenceRemoved':False})
  base['save'](T/'stage-global-before.json',{'capturedAt':base['now'](),'observation':all_nodes,'budgets':budgets})
  for host in nodes:
   for name in names:
    entry=vendor['binaries'][name];before=base['invoke'](host,vendor)
    assert base['remote'].identity(before)==base['remote'].identity(capture['nodes'][host])
    base['remote'].budget(before,vendor);assert before['stages'][name] is None
    path=T/(host+'-'+name+'-intent.json')
    base['save'](path,{'capturedAt':base['now'](),'nodeUID':capture['nodeUIDs'][host],'before':before,'binary':entry,
     'sourceSHA256':REMOTE_SHA,'repairSourceSHA256':digest(Path(__file__).resolve()),'ownerTask':'kubernetes1372-security-patch',
     'path':'/usr/local/bin/.kubernetes1372-'+name+'-'+entry['sha256']+'.new','originalDisposition':base['ref'](T/'original-intent-disposition.json')})
    try:
     after=corrected_invoke(base,host,{'binaries':vendor['binaries'],'before':before,'name':name},password,Path(entry['blob']['path']))
    except Exception as error:
     base['save'](T/(host+'-'+name+'-failure.json'),{'capturedAt':base['now'](),'intent':base['ref'](path),'errorType':type(error).__name__,'carrier':getattr(error,'carrier_diagnostic',{}),'outcome':'uncertain; no replay or target removal','preserved':True})
     raise
    base['save'](T/(host+'-'+name+'-after.json'),{'capturedAt':base['now'](),'intent':base['ref'](path),'after':after})
  password=None
 assert T.resolve()==T and T.stat().st_uid==1000 and not T.stat().st_mode&0o077
 repair_owner=json.loads((T/'ownership.json').read_text())
 assert repair_owner['repairSourceSHA256']==digest(Path(__file__).resolve()) and digest(T/'original-staging.py')==OLD_SHA
 assert repair_owner['originalCapture']==base['ref'](R/'capture.json') and repair_owner['originalOwnership']==base['ref'](R/'ownership.json') and repair_owner['originalBackups']==base['ref'](R/'backups.json')
 final=base['global_observe'](vendor,capture)
 result={'binaries':copy.deepcopy(vendor['binaries']),'signatureTool':vendor['signatureTool'],'immutableVendorAuthority':base['ref'](base['VENDOR']),
         'transportRepair':{'ownership':base['ref'](T/'ownership.json'),'originalDisposition':base['ref'](T/'original-intent-disposition.json')}}
 for name,entry in result['binaries'].items():
  entry['originalByNode']={host:capture['nodes'][host]['binaries'][name] for host in nodes}
  entry['originalBackups']={host:backups[name] for host in nodes};entry['prestage']={}
  for host in nodes:
   actual=final['nodes'][host]['stages'][name];original=capture['nodes'][host]['binaries'][name]
   assert actual and actual['sha256']==entry['sha256'] and actual['bytes']==entry['bytes']
   assert actual['path']=='/usr/local/bin/.kubernetes1372-'+name+'-'+entry['sha256']+'.new'
   assert all(actual[k]==original[k] for k in ('uid','gid','mode','mtimeNs','xattrsSHA256'))
   intent=T/(host+'-'+name+'-intent.json');frozen=json.loads(intent.read_text())
   assert frozen['nodeUID']==capture['nodeUIDs'][host] and frozen['binary']==vendor['binaries'][name]
   assert frozen['sourceSHA256']==REMOTE_SHA and frozen['before']['stages'][name] is None
   assert base['remote'].identity(frozen['before'])==base['remote'].identity(final['nodes'][host])
   stage=T/(host+'-'+name+'-stage.json')
   value={'capturedAt':base['now'](),'node':host,'nodeUID':capture['nodeUIDs'][host],'path':actual['path'],'sha256':entry['sha256'],'bytes':entry['bytes'],
          'ownerTask':'kubernetes1372-security-patch','newlyCreated':True,'intent':base['ref'](intent),'observed':final['nodes'][host],'installPerformed':False}
   if stage.exists():
    previous=json.loads(stage.read_text());base['fresh'](previous['capturedAt'])
    assert all(previous[k]==value[k] for k in ('node','nodeUID','path','sha256','bytes','intent'))
   else:base['save'](stage,value)
   entry['prestage'][host]=base['ref'](stage)
 destination=T/'binary-evidence.json'
 if destination.exists():assert json.loads(destination.read_text())==result
 else:base['save'](destination,result)
 print(json.dumps(base['ref'](destination)))

if __name__=='__main__':main()
