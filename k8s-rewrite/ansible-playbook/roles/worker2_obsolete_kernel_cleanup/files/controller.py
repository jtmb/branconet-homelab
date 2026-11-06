"""Source-only prepared worker2 cleanup controller; explicit --apply required.
A fixed exclusive durable intent prevents retries, including after failed/unknown runs.
"""
import argparse, base64, hashlib, json, os, pathlib, shlex, subprocess, sys, uuid
P=pathlib.Path
H=P('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/platform-upstream-review-20261027/autonomous-hardening-20261028')
PLAN_SHA='5e48833067b8e1f38ad01b7a7928deb749f836619e134592ee515365837064ae'
REMOTE_SHA='e1e1f4bbd6037823b06f390dcdae660e81dbd801acda885ed2a6f380169bd707'
OUT=H/'worker2-obsolete-kernel-cleanup'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,why):
 if not ok:raise RuntimeError(why)
def durable(path,value):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 try:
  with os.fdopen(fd,'w') as out:json.dump(value,out,indent=2);out.write('\n');out.flush();os.fsync(out.fileno())
 finally:
  parent=os.open(path.parent,os.O_DIRECTORY)
  try:os.fsync(parent)
  finally:os.close(parent)
def password(stdin):
 # Consume before any SSH invocation, bounded RAM only. Never argv/file/env transport.
 if stdin:
  raw=sys.stdin.buffer.readline(4098)
  require(raw.endswith(b'\n') and len(raw)<=4097 and b'\x00' not in raw and b'\r' not in raw,'bounded_privilege_input')
  require(b'\n' not in raw[:-1] and len(raw)>1,'privilege_input_shape')
  return raw[:-1].decode('utf-8')
 raw=os.environ.pop('ANSIBLE_BECOME_PASSWORD',None)
 require(raw is not None and 0<len(raw.encode())<=4096 and not any(c in raw for c in '\r\n\x00'),'protected_environment_input')
 return raw

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');ap.add_argument('--password-stdin',action='store_true');args=ap.parse_args()
 secret=password(args.password_stdin)
 # Remove inherited credential variables even when stdin was selected.
 for key in ['ANSIBLE_BECOME_PASSWORD','BRANCONET_SUDO_PASSWORD']:os.environ.pop(key,None)
 require(H.is_dir() and H.resolve()==H,'owned_output_root')
 source=P(__file__).with_name('remote.py');require(digest(source)==REMOTE_SHA,'remote_source_hash')
 path=H/'obsolete-kernel-cache-cleanup-proposal.json';require(digest(path)==PLAN_SHA,'proposal_hash')
 plan=json.loads(path.read_text());require(plan['owner']=='vendor_security_review','proposal_owner')
 for name,sha in plan['inputs'].items():require(P(name).name==name and digest(H/name)==sha,'proposal_input_hash')
 node=next(x for x in plan['nodes'] if x['node']=='workernode2');require(node['ip']=='192.168.0.5','ip')
 OUT.mkdir(mode=0o700,exist_ok=True);require(OUT.resolve()==OUT,'output_alias');os.chmod(OUT,0o700)
 intent=OUT/'worker2-kernel157-and-18-archives.intent.json'
 if args.apply:require(not intent.exists(),'prior_submitted_intent_no_replay')
 invocation=uuid.uuid4().hex
 journal=OUT/('events-'+invocation+'.jsonl');log=open(journal,'x',encoding='utf-8');os.chmod(journal,0o600)
 def event(value):log.write(json.dumps(value)+'\n');log.flush();os.fsync(log.fileno())
 event({'phase':'controller_start','owner':'vendor_security_review','scope':'worker2 exact five157 packages and18 completed installed archives','sourceSHA256':digest(P(__file__)),'remoteSHA256':REMOTE_SHA,'proposalSHA256':PLAN_SHA,'mode':'apply' if args.apply else 'observe','outputRoot':str(OUT),'completeOutputPeakBytes':8*1024**2,'nodeNativeWriteScope':'APT/dpkg native bookkeeping, generated boot metadata, exact obsolete157 package files, exact18 archive paths; no source copied to node'})
 code='import base64;exec(compile(base64.b64decode('+repr(base64.b64encode(source.read_bytes()).decode())+'),"<verified-worker2-cleanup>","exec"))'
 command='sudo -k -S -p '+shlex.quote('')+' -- python3 -B -c '+shlex.quote(code)
 ssh=['ssh','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile=/home/brajam/.ssh/known_hosts','-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@192.168.0.5',command]
 process=None;completed=False;preflight=False
 try:
  process=subprocess.Popen(ssh,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=os.environ.copy())
  process.stdin.write(secret+'\n'+json.dumps({'plan':node})+'\n');process.stdin.flush();secret=None
  for line in process.stdout:
   require(len(line)<6*1024**2,'remote_record_size')
   value=json.loads(line);event(value)
   if value['phase']=='preflight':
    require(not preflight,'duplicate_preflight');preflight=True
    if args.apply:
     # This file is intentionally never removed or overwritten by this helper.
     durable(intent,{'phase':'submitted','invocation':invocation,'node':'workernode2','ip':'192.168.0.5','rootUUID':node['rootUUID'],'proposalSHA256':PLAN_SHA,'remoteSHA256':REMOTE_SHA,'controllerSHA256':digest(P(__file__)),'journal':str(journal),'preflightSHA256':hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest(),'packages':sorted(node['kernelRemoval']['exactPackages']),'archives':[{'path':a['path'],'sha256':a['sha256']} for a in node['completedInstalledArchives']],'noUncertainRetry':True})
     process.stdin.write('APPLY_EXACT_REVIEWED_PLAN\n')
    else:process.stdin.write('OBSERVE_ONLY\n')
    process.stdin.flush();process.stdin.close()
   if value['phase'] in ['completed','observed']:completed=True
  stderr=process.stderr.read(131073);rc=process.wait();require(len(stderr)<=131072,'stderr_size')
  event({'phase':'transport_result','exitCode':rc,'stderr':stderr})
  require(rc==0 and preflight and completed,'operation_incomplete_no_retry')
 finally:
  secret=None
  if process is not None and process.poll() is None:
   # Do not kill or retry the remote package manager. Retain submitted intent.
   event({'phase':'transport_unresolved','pid':process.pid,'noRetry':True})
  log.close()
 print(json.dumps({'journal':str(journal),'completed':completed,'intent':str(intent) if args.apply else None}))
if __name__=='__main__':main()
