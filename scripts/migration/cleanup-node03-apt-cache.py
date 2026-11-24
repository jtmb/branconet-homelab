"""Remove only checked, reproducible inactive apt binary caches to admit the release."""
import argparse,importlib.util,json,os,shlex,subprocess
from pathlib import Path
S=Path(__file__).parent;O=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/empty-list-fix')
PROGRAM='''import hashlib,json,os,pathlib,stat,sys
request=json.loads(sys.stdin.readline());targets=[pathlib.Path('/var/cache/apt/pkgcache.bin'),pathlib.Path('/var/cache/apt/srcpkgcache.bin')];rows=[]
assert pathlib.Path('/usr/bin/apt-cache').is_file() and any(pathlib.Path('/var/lib/apt/lists').glob('*Packages*'))
for p in targets:
 if not p.exists():continue
 s=p.lstat();assert stat.S_ISREG(s.st_mode) and s.st_nlink==1 and p.resolve()==p
 for directory in pathlib.Path('/proc').glob('[0-9]*/fd'):
  try:refs=list(directory.iterdir())
  except FileNotFoundError:continue
  for ref in refs:
   try:assert os.readlink(ref)!=str(p)
   except FileNotFoundError:pass
 digest=hashlib.sha256()
 with p.open('rb')as f:
  for block in iter(lambda:f.read(1024*1024),b''):digest.update(block)
 d=digest.hexdigest()
 rows.append({'path':str(p),'device':s.st_dev,'inode':s.st_ino,'bytes':s.st_size,'allocated_bytes':s.st_blocks*512,'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns,'sha256':d})
assert rows
if request['remove']:
 assert rows==request['checked']['files']
 for row in rows:pathlib.Path(row['path']).unlink()
print(json.dumps({'files':rows,'regenerate':'apt-cache gencaches (existing /var/lib/apt/lists inputs retained)','removed':request['remove'],'removed_allocated_bytes':sum(r['allocated_bytes']for r in rows)if request['remove']else 0,'free_after':os.statvfs('/var/cache/apt').f_bavail*os.statvfs('/var/cache/apt').f_frsize,'windows_recovery_claimed':False}))
'''
def main():
 compile(PROGRAM,'node_apt_cache_check','exec')
 parser=argparse.ArgumentParser();parser.add_argument('--remove',action='store_true');args=parser.parse_args();s=importlib.util.spec_from_file_location('cache_saved_credential',S/'saved-node-credential.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);password=m.existing_password();request={'remove':args.remove}
 if args.remove:request['checked']=json.loads((O/'node03-apt-cache-check.json').read_bytes())
 # sudo authenticates from its own bounded stdin; the checked request is a nonsecret code literal.
 code='import io,sys;sys.stdin=io.StringIO('+repr(json.dumps(request)+'\n')+');exec('+repr(PROGRAM)+')'
 try:
  p=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile=/home/brajam/.ssh/known_hosts','-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@192.168.0.5','sudo -S -k -p '+shlex.quote('')+' python3 -c '+shlex.quote(code)],input=(password+'\n').encode(),capture_output=True,timeout=60)
  if p.returncode:raise RuntimeError('apt_cache_safety_check_failed:'+p.stderr.decode(errors='replace')[-1000:])
  d=json.loads(p.stdout);path=O/('node03-apt-cache-cleanup.json'if args.remove else'node03-apt-cache-check.json')
  with path.open('x')as f:json.dump(d,f)
  print(json.dumps(d))
 finally:password=None
if __name__=='__main__':main()
