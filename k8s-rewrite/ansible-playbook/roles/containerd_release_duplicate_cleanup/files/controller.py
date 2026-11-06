"""Finite duplicate release cleanup; passwords consumed before any child."""
import argparse,base64,hashlib,json,os,pathlib,runpy,shlex,subprocess,sys,datetime,select,time
P=pathlib.Path
F=P('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028'
OUT=H/'containerd-release-duplicate-cleanup'
SUCCESS=H/'kubernetes-maintenance-receipts/56f152a9adc044478db62e3cacc65288-result.json'
SUCCESS_SHA='583d6a0eece75e23940ff4d6f1a4a805dfe6b58148fc8a3d0f44a1d5a9736072'
PINS={'scripts/migration/verify-completed-core-preservation.py': '52210124219d6b7f0781d217e1d246a59902148235c2b65b5d51bc2754dee512', 'k8s-rewrite/ansible-playbook/roles/containerd_release_duplicate_cleanup/files/remote.py': '714cc4dc0939d216d767f92d5e2d815b127de7233fec9e02a6b2bf4814b60d2b', 'k8s-rewrite/ansible-playbook/roles/node_headroom_cache/files/controller.py': '9581507bd473b8c060b699ece6c756c8a229cfec89114b1780dc23c515cb989b', 'k8s-rewrite/ansible-playbook/roles/kubernetes_security_patch/files/checkpoint.py': '61c2975bcecad83e02e9a9fcd560f210e0d943a6c3fac9f1b530035551519233'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
 with p.open('x')as f:json.dump(v,f,indent=2);f.flush();os.fsync(f.fileno())
def main():
 a=argparse.ArgumentParser();a.add_argument('mode',choices=['qualify','apply']);a.add_argument('--node',required=True,choices=['masternode','workernode2']);a.add_argument('--password-stdin',action='store_true');args=a.parse_args()
 if args.password_stdin:
  raw=sys.stdin.buffer.readline(130);assert raw.endswith(b'\n')and len(raw)<=129
  password=raw[:-1]
 else:
  value=os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD',None);assert value is not None;password=value.encode();value=None
 assert 0<len(password)<=128 and not any(c in password for c in [b'\r',b'\n',b'\0'])
 assert os.geteuid()==1000 and F.is_mount()and H.resolve()==H
 repo=P(__file__).resolve().parents[5]
 assert all(sha(repo/n)==v for n,v in PINS.items())
 cache=runpy.run_path(str(repo/'k8s-rewrite/ansible-playbook/roles/node_headroom_cache/files/controller.py'))
 class Admission:pass
 admission=Admission();admission.kubernetes_success=SUCCESS;admission.kubernetes_success_sha256=SUCCESS_SHA
 _,binding=cache['kubernetes1371_profile'](admission,repo)
 cache['current_image_inventory'](repo)
 completed_guard=runpy.run_path(str(repo/'scripts/migration/verify-completed-core-preservation.py'))
 def full58():
  proof=completed_guard['validate'](repo)
  return hashlib.sha256(json.dumps(proof,sort_keys=True).encode()).hexdigest()
 checkpoint_hash=full58()
 OUT.mkdir(mode=0o700,exist_ok=True);assert OUT.resolve()==OUT
 prefix=OUT/args.node
 qualification=P(str(prefix)+'-qualification.json');qualify_intent=P(str(prefix)+'-qualify-intent.json');apply_intent=P(str(prefix)+'-apply-intent.json')
 if args.mode=='qualify':assert not qualify_intent.exists()and not apply_intent.exists(),'Prior qualification/attempt target retained; no retry'
 else:
  assert qualification.is_file()and qualify_intent.is_file()and not apply_intent.exists(),'No qualification or prior apply target retained'
  q=json.loads(qualification.read_text());assert q['binding']==binding and q['sourcePins']==PINS and q['controllerSHA256']==sha(P(__file__))and q['result']['status']=='qualified'
 source=repo/'k8s-rewrite/ansible-playbook/roles/containerd_release_duplicate_cleanup/files/remote.py'
 guard=F/'node-cleanup-20261027/master-generated-cleanup/reference-full-properties.py';assert sha(guard)=='3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87'
 intent=qualify_intent if args.mode=='qualify'else apply_intent
 save(intent,{'owner':'vendor_security_review','physicalRoot':str(F),'node':args.node,'mode':args.mode,'target':'/opt/containerd-k8s/releases/v2.4.2','peakBytes':128*1024**2,'binding':binding,'sourcePins':PINS,'controllerSHA256':sha(P(__file__)),'checkpointOutputSHA256':checkpoint_hash,'regeneration':'Official containerd-static-2.4.2-linux-amd64.tar.gz SHA256 da656542e754c699a0f438eab925e6ffdbd6346a4428e659f83dc058f04dcffe; download into one future owned leaf, verify checksum, extract only four bin members; never reinstall or restart as cleanup','protected':'Installed binaries/configuration/CNI/data and all prior failed targets','createdUTC':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 packet={'mode':args.mode,'node':args.node,'guardSource':base64.b64encode(guard.read_bytes()).decode()}
 if args.mode=='apply':packet['qualification']=q['result']
 ip={'masternode':'192.168.0.4','workernode2':'192.168.0.5'}[args.node]
 ssh=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile=/home/brajam/.ssh/known_hosts','-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@'+ip]
 events=P(str(prefix)+'-'+args.mode+'-events.jsonl');errors=P(str(prefix)+'-'+args.mode+'-stderr.txt')
 last=None
 with events.open('x')as journal,errors.open('xb')as err:
  child=subprocess.Popen(ssh+[shlex.join(['sudo','-S','-k','-p','','python3','-B','-c',source.read_text()])],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,bufsize=0)
  try:
   child.stdin.write(password+b'\n'+json.dumps(packet).encode()+b'\n');child.stdin.flush();password=None
   deadline=time.monotonic()+900
   while True:
    remaining=deadline-time.monotonic();assert remaining>0,'Bounded cleanup transport deadline'
    readable,_,_=select.select([child.stdout],[],[],remaining);assert readable,'Bounded cleanup transport timeout'
    raw=child.stdout.readline(2*1024**2+1)
    if not raw:break
    assert len(raw)<2*1024**2
    row=json.loads(raw);journal.write(json.dumps(row)+'\n');journal.flush();os.fsync(journal.fileno());last=row
    ack=None
    if row.get('status')=='ready':ack=b'ACK-EXACT-FIVE-FILES\n'
    elif 'intent'in row:ack=b'ACK-UNLINK\n'if row['intent'].endswith(('/containerd.tar.gz','/containerd','/containerd-shim-runc-v2','/containerd-stress','/ctr'))else b'ACK-RMDIR\n'
    if ack:child.stdin.write(ack);child.stdin.flush()
   rc=child.wait(timeout=900)
  finally:
   password=None
   if child.stdin:child.stdin.close()
   if child.poll() is None:
    child.terminate();child.wait(timeout=15)
 save(P(str(prefix)+'-'+args.mode+'-result.json'),{'exitCode':rc,'lastEvent':last,'binding':binding,'sourcePins':PINS,'controllerSHA256':sha(P(__file__)),'finishedUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stderrSHA256':sha(errors),'eventsSHA256':sha(events)})
 assert rc==0 and last is not None
 if args.mode=='qualify':
  assert last['status']=='qualified';save(qualification,{'binding':binding,'sourcePins':PINS,'controllerSHA256':sha(P(__file__)),'result':last})
 else:
  assert last['status']=='completed';post=full58();cache['current_image_inventory'](repo)
  save(P(str(prefix)+'-accepted.json'),{'completed':True,'full58OutputSHA256':post,'nativeResultSHA256':sha(P(str(prefix)+'-apply-result.json')),'WindowsRecoveryClaimed':False})
 print(json.dumps({'node':args.node,'mode':args.mode,'status':last['status'],'output':str(OUT)}))
if __name__=='__main__':os.umask(0o077);main()
