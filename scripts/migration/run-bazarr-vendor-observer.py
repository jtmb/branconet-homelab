#!/usr/bin/env python3
"""Controller-only receipts; exact Bazarr observer sources and existing HMAC key travel in SSH stdin RAM."""
import argparse,ast,base64,datetime,hashlib,json,os,re,shlex,stat,subprocess,sys,types
from pathlib import Path
ROOT=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT=ROOT/'platform-upstream-review-20261027/autonomous-hardening-20261028/bazarr-observation'
QUALIFIER_SHA='c6f264ff1a38663edd46af2918715dfce8e116ac51e0ae3dcfecf300e37e7ba7'
OBSERVER_SHA='b010865bc00cf909bb74a9bfbb18625f5a5aae632eade28385360addd7ce8728'
OLD='ghcr.io/hotio/bazarr:latest@sha256:32204ef90d4dcb54ad5fb019810f4ef805ced9c54853ae552cf09a41c056b14b'
NEW='ghcr.io/hotio/bazarr:latest@sha256:86b76c5c66a839ca6f6dd15ddb16b43f074dc71d41907b720e176bdede4b6562'
OLD_RUNTIME='sha256:8696d2b429f88dcb8049357be3d24c12e6c79a3aaa9c063ac7107d59914434e5'
NEW_RUNTIME='sha256:ff7b10937c15036b011b33b1d524b92ead2415564bf1ab5415268b915d4b71f9'
MAX_REPLY=64*1024**2
SSH=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile=/home/brajam/.ssh/known_hosts','-o','IdentitiesOnly=yes','-o','ForwardAgent=no','-o','ConnectTimeout=15','-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@192.168.0.4']
def need(ok,reason):
 if not ok:raise ValueError(reason)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def file_identity(p):
 x=p.stat();return (x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode,x.st_uid)
def configure(q):
 q.update(OLD=OLD,NEW=NEW,NEW_RUNTIME=NEW_RUNTIME,SECURITY_BASELINE_RUNTIME=OLD_RUNTIME,SECURITY_PATCH=True)
def load_sources():
 p=Path(__file__).resolve().with_name('qualify-bazarr.py');reader=p.with_name('bazarr-sqlite-observer.py')
 need(p.resolve()==p and reader.resolve()==reader,'exact_local_source_paths')
 a=p.read_bytes();b=reader.read_bytes()
 need(len(a)<=65536 and len(b)<=65536 and hashlib.sha256(a).hexdigest()==QUALIFIER_SHA and hashlib.sha256(b).hexdigest()==OBSERVER_SHA,'exact_qualifier_and_reader_source')
 q={'__name__':'bazarr_controller_qualifier','__file__':str(p)};exec(compile(a,str(p),'exec'),q);configure(q)
 return p,reader,a,b,q

def original_main_helpers(source,q):
 """Compile unchanged main guard/receipt AST statements; no protected-file override."""
 main=next(x for x in ast.parse(source).body if isinstance(x,ast.FunctionDef) and x.name=='main')
 reasons={'modern_same_app_profile_required','vendor_refresh_same_app_scope','stdin_requires_32_byte_hex_key','baseline_argument','restart_argument','normalization_proof_argument'}
 selected=[]
 for n in main.body:
  if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='need' and len(n.value.args)>1 and isinstance(n.value.args[1],ast.Constant) and n.value.args[1].value in reasons:selected.append(n)
 need(len(selected)==len(reasons),'all_original_argument_guards_selected')
 validation=ast.parse('def validate_carrier_arguments(args, raw):\n pass').body[0];validation.body=selected
 start=next(i for i,n in enumerate(main.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='checks' for t in n.targets))
 end=next(i for i,n in enumerate(main.body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='write_new')
 need(start<end,'original_receipt_block_bounds')
 finalizer=ast.parse('def finalize_carrier_receipt(args, start, observation, key):\n pass').body[0]
 finalizer.body=main.body[start:end]+[ast.Return(value=ast.Name(id='receipt',ctx=ast.Load()))]
 module=ast.fix_missing_locations(ast.Module(body=[validation,finalizer],type_ignores=[]));exec(compile(module,'<unchanged-bazarr-main-blocks>','exec'),q)
 return q['validate_carrier_arguments'],q['finalize_carrier_receipt']

def receiver_source():
 # Only public fixed code in remote argv. Key and public module bytes are stdin-only.
 text=r"""import base64,hashlib,json,re,sys
try:
 packet=sys.stdin.buffer.read(262145)
 if len(packet)>262144:raise ValueError('bounded_transport_request')
 request=json.loads(packet)
 qa=base64.b64decode(request['qualifier'],validate=True);ob=base64.b64decode(request['observer'],validate=True)
 if len(qa)>65536 or len(ob)>65536 or hashlib.sha256(qa).hexdigest()!=QUALIFIER_SHA or hashlib.sha256(ob).hexdigest()!=OBSERVER_SHA:raise ValueError('exact_transported_sources')
 raw=request['key'].encode('ascii')
 if re.fullmatch(b'[0-9a-f]{64}\n?',raw) is None:raise ValueError('stdin_requires_32_byte_hex_key')
 if request['mode'] not in ['baseline','after','restart']:raise ValueError('finite_observer_mode')
 q={'__name__':'bazarr_ram_qualifier','__file__':'<bazarr-qualifier-in-ram>'};exec(compile(qa,'<bazarr-qualifier-in-ram>','exec'),q)
 q.update(OLD=OLD,NEW=NEW,NEW_RUNTIME=NEW_RUNTIME,SECURITY_BASELINE_RUNTIME=OLD_RUNTIME,SECURITY_PATCH=True)
 start=q['identity'](request['mode']);observation=q['observe_pod'](start,request['mode'],raw,reader_source=ob);finish=q['identity'](request['mode'])
 q['need'](start==finish,'runtime_changed_during_observation')
 q['need'](hashlib.sha256(qa).hexdigest()==QUALIFIER_SHA and hashlib.sha256(ob).hexdigest()==OBSERVER_SHA,'transport_sources_immutable_after_observation')
 safe={k:v for k,v in start.items() if k not in ['pod_name','cluster_ip']}
 reply={'status':'observed','mode':request['mode'],'identity':safe,'observation':observation,'identityStable':True,'qualifierSHA256':QUALIFIER_SHA,'observerSHA256':OBSERVER_SHA,'nodeFilesWritten':False}
 output=json.dumps(reply)
 if len(output.encode())>67108864:raise ValueError('bounded_transport_response')
 request['key']=None;raw=None
 print(output)
except BaseException as error:
 reason=str(error) if type(error).__name__ in ['Refused','ValueError'] and re.fullmatch(r'[a-z0-9_]{1,160}',str(error)) else 'observer_transport_failed_raw_details_suppressed'
 print(json.dumps({'status':'refused','reason':reason}));sys.exit(1)
"""
 bindings='\n'.join(k+'='+repr(v) for k,v in [('QUALIFIER_SHA',QUALIFIER_SHA),('OBSERVER_SHA',OBSERVER_SHA),('OLD',OLD),('NEW',NEW),('OLD_RUNTIME',OLD_RUNTIME),('NEW_RUNTIME',NEW_RUNTIME)])
 return bindings+'\n'+text

def read_key(args):
 if args.key_file is not None:
  p=args.key_file;need(p.is_absolute() and p.resolve()==p and not p.is_symlink(),'protected_key_path')
  before=p.lstat();need(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and stat.S_IMODE(before.st_mode)==0o600 and before.st_size<=65,'existing_owner600_key_file')
  fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
  try:
   same=os.fstat(fd);need((same.st_dev,same.st_ino)==(before.st_dev,before.st_ino),'key_file_identity')
   raw=os.read(fd,66);after=os.fstat(fd);need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'key_file_unchanged')
  finally:os.close(fd)
 else:
  need(not sys.stdin.isatty(),'protected_key_stdin_required');s=os.fstat(sys.stdin.fileno())
  need(stat.S_ISFIFO(s.st_mode) or (stat.S_ISREG(s.st_mode) and s.st_uid==os.getuid() and stat.S_IMODE(s.st_mode)==0o600),'protected_key_stdin_permissions');raw=sys.stdin.buffer.read(66)
 need(re.fullmatch(b'[0-9a-f]{64}\n?',raw) is not None,'stdin_requires_32_byte_hex_key');return raw

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--mode',required=True,choices=['baseline','after','restart']);parser.add_argument('--baseline',type=Path);parser.add_argument('--prior-receipt',type=Path);parser.add_argument('--receipt',required=True,type=Path)
 key=parser.add_mutually_exclusive_group(required=True);key.add_argument('--key-file',type=Path);key.add_argument('--key-stdin',action='store_true');args=parser.parse_args()
 args.security_patch=True;args.upstream_adoption=False;args.vendor_security_refresh_20261028=True;args.vendor_normalization_proof=None
 os.umask(0o077);need(ROOT.resolve()==ROOT and OUT.resolve()==OUT and OUT.is_dir() and OUT.stat().st_uid==os.getuid() and stat.S_IMODE(OUT.stat().st_mode)==0o700,'existing_private_F_output')
 need(args.receipt.is_absolute() and args.receipt.resolve()==args.receipt and args.receipt.is_relative_to(OUT) and not args.receipt.exists(),'new_protected_F_receipt')
 need(os.statvfs(OUT).f_bavail*os.statvfs(OUT).f_frsize>=15*1024**3+MAX_REPLY,'receipt_capacity_floor')
 p,reader,qa,ob,q=load_sources();validate,finalize=original_main_helpers(qa,q);inputs={}
 # Actual controller filesystem validation through the unchanged protected_file.
 for path in [args.baseline,args.prior_receipt]:
  if path is None:continue
  need(path.is_relative_to(ROOT),'protected_prior_receipt_in_existing_F_root');q['protected_file'](path);inputs[path]=(file_identity(path),sha(path))
 raw=read_key(args)
 try:
  validate(args,raw);packet=json.dumps({'mode':args.mode,'qualifier':base64.b64encode(qa).decode(),'observer':base64.b64encode(ob).decode(),'key':raw.decode()}).encode();need(len(packet)<=262144,'bounded_transport_request')
  code=receiver_source();child=subprocess.run(SSH+[shlex.join(['/usr/bin/python3','-I','-B','-c',code])],input=packet,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=600);packet=None
  need(0<len(child.stdout)<=MAX_REPLY,'bounded_transport_response');reply=json.loads(child.stdout)
  if child.returncode!=0 or reply.get('status')!='observed':
   reason=reply.get('reason','observer_transport_failed');need(False,reason if re.fullmatch(r'[a-z0-9_]{1,160}',reason) else 'observer_transport_failed_raw_details_suppressed')
  need(reply['mode']==args.mode and reply['identityStable'] is True and reply['qualifierSHA256']==QUALIFIER_SHA and reply['observerSHA256']==OBSERVER_SHA,'bound_remote_observation')
  need(reply['observation']['observer_sha256']==OBSERVER_SHA and reply['observation']['quick_check_passed'] is True,'exact_real_sql_api_observer')
  need(not any(k in reply['identity'] for k in ['pod_name','cluster_ip']),'sanitized_remote_identity')
  need(sha(p)==QUALIFIER_SHA and sha(reader)==OBSERVER_SHA,'local_source_bytes_unchanged')
  need(all(file_identity(path)==identity and sha(path)==digest for path,(identity,digest) in inputs.items()),'protected_inputs_unchanged_during_remote_observation')
  receipt=finalize(args,reply['identity'],reply['observation'],bytes.fromhex(raw.decode().strip()))
  need(all(file_identity(path)==identity and sha(path)==digest for path,(identity,digest) in inputs.items()),'protected_inputs_unchanged_after_original_checks')
  receipt['controller_transport']={'source_sha256':sha(Path(__file__).resolve()),'receiver_sha256':hashlib.sha256(code.encode()).hexdigest(),'qualifier_sha256':QUALIFIER_SHA,'observer_sha256':OBSERVER_SHA,'node_source_or_receipt_files_written':False,'authenticated_ssh_stdin_only':True,'original_main_checks_reused':True,'original_protected_files_checked_on_controller':True}
  need(len(json.dumps(receipt).encode())<=MAX_REPLY,'bounded_controller_receipt');q['write_new'](args.receipt,receipt)
  print(json.dumps({'status':'observed','mode':args.mode,'receipt':str(args.receipt),'version':receipt['observation']['application']['version'],'counts':receipt['observation']['counts'],'subtitle_count':receipt['observation']['subtitle_count'],'data_preservation_passed':receipt['data_preservation_passed'],'full_acceptance_complete':False}))
 finally:raw=None
if __name__=='__main__':
 try:main()
 except BaseException as error:
  if isinstance(error,SystemExit):raise
  reason=str(error) if type(error).__name__ in ['Refused','ValueError'] and re.fullmatch(r'[a-z0-9_]{1,160}',str(error)) else 'controller_observer_failed_raw_details_suppressed'
  print(json.dumps({'status':'refused','reason':reason}));raise SystemExit(1)
