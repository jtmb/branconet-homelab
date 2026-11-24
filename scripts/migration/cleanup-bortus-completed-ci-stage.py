"""Retire the completed exact-commit CI export and duplicate tools, preserving receipts."""
import hashlib,json,os,shutil
from pathlib import Path
S=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/local-charts-publisher/local-charts-publish-5aaf249dd68d4150a1e6d8f92d068101')
T=Path('/home/brajam/.local/share/branconet-migration/bin')
def need(v):
 if not v:raise RuntimeError('completed_ci_stage_cleanup_check_failed')
def main():
 need(S.resolve(strict=True)==S and S.is_dir())
 p=json.loads((S/'prepare.json').read_bytes());c=json.loads((S/'check.json').read_bytes());pub=json.loads((S/'publish.json').read_bytes())
 need(p['sourceSHA']==c['sourceSHA']==pub['sourceSHA']=='eb3921c6fed7db8718d4256fb367d68da208ebac' and c['passed'] is True and pub['passed'] is True)
 targets=[S/'source',S/'home',S/'tmp'];need(all(x.exists() and not x.is_symlink() and x.resolve().parent==S for x in targets))
 files=[];allocated=logical=0
 for target in targets:
  for x in [target,*target.rglob('*')]:
   info=x.lstat();need(not x.is_symlink() and info.st_uid==1000);allocated+=info.st_blocks*512
   if x.is_file():files.append(x);logical+=info.st_size
 source=S/'source';need(not (source/'.git').exists());extra=[]
 for f in files:
  if not f.is_relative_to(source):raise RuntimeError('unexpected_nonempty_disposable_home_or_tmp')
  rel=f.relative_to(source).as_posix();entry=p['manifest'].get(rel);b=f.read_bytes()
  if entry:need(hashlib.sha1(('blob '+str(len(b))).encode()+b'\0'+b).hexdigest()==entry['oid'])
  elif rel.startswith('.tools/'):
   name=f.name;need(name in p['binariesSHA256'] and hashlib.sha256(b).hexdigest()==p['binariesSHA256'][name])
   with (T/name).open('rb') as stream:need(hashlib.file_digest(stream,'sha256').hexdigest()==p['binariesSHA256'][name])
  elif rel=='.validation/validation.json':extra.append(f)
  else:raise RuntimeError('unique_unrecognized_stage_file_retained')
 need(len(extra)==1)
 for proc in Path('/proc').iterdir():
  if not proc.name.isdecimal() or int(proc.name)==os.getpid():continue
  for item in [proc/'cwd',proc/'root',*(proc/'fd').glob('*')]:
   try:value=os.readlink(item)
   except FileNotFoundError:continue
   except PermissionError:raise RuntimeError('process_reference_check_incomplete')
   need(not any(value==str(t) or value.startswith(str(t)+'/') for t in targets))
  for name in ('cmdline','maps','mountinfo'):
   try:raw=(proc/name).read_bytes()
   except (FileNotFoundError,ProcessLookupError):continue
   except PermissionError:raise RuntimeError('process_reference_check_incomplete')
   need(not any(str(t).encode() in raw for t in targets))
 retained=S/'validation-result.json';need(not retained.exists());original=extra[0].read_bytes();extra[0].rename(retained);need(retained.read_bytes()==original)
 removed=[]
 for t in targets:
  need(t.resolve().parent==S);shutil.rmtree(t);need(not t.exists());removed.append(str(t))
 receipt={'state':'completed','removed_paths':removed,'removed_logical_bytes':logical-len(original),
 'removed_allocated_bytes':allocated-retained.stat().st_blocks*512,'retained_validation_result_sha256':hashlib.sha256(original).hexdigest(),
 'regeneration':'Existing private charts Git commit eb3921c6fed7db8718d4256fb367d68da208ebac exact export and the retained operator tools',
 'receipts_retained':['prepare.json','check.json','publish.json','validation-result.json'],'windows_disk_recovery_claimed':False}
 out=S/'cleanup.json';fd=os.open(out,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'w') as f:json.dump(receipt,f);f.flush();os.fsync(f.fileno())
 print(json.dumps(receipt))
if __name__=='__main__':main()
