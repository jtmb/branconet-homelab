#!/usr/bin/env python3
"""Retire only the completed Mealie controller transfer; retain both full artifacts."""
import argparse,hashlib,json,os,pathlib,stat,subprocess
B=pathlib.Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
TARGET=B/'application-artifacts-20261023/mealie-security-20261023-r2.oci.tar'
RETAIN=[B/'mealie-c692b307681c-540ac3a24c60/artifacts/mealie.oci.tar',B/'local-image-artifacts-20261025/mealie-540ac3a24c6049549703ee367fc275bf/mealie.oci.tar']
SHA='bd04589000b777dea02d7967669d332fdbdffb2ad9d0c0783e544e6e76d63cfe';SIZE=627191296

def check(p):
 assert p.resolve()==p and not any((x/'.git').exists()for x in [p.parent,*p.parents]);s=p.lstat();assert stat.S_ISREG(s.st_mode)and s.st_uid==1000 and s.st_nlink==1 and s.st_size==SIZE and not stat.S_IMODE(s.st_mode)&0o077
 with p.open('rb')as f:assert hashlib.file_digest(f,'sha256').hexdigest()==SHA
 assert p.lstat()==s;return s

def main():
 a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');a.add_argument('--receipt',type=pathlib.Path,required=True);x=a.parse_args();assert os.geteuid()==0 and B.is_mount();assert subprocess.check_output(['findmnt','-n','-o','UUID,FSTYPE','--target',str(B)]).decode().split()==['3c792469-ea0e-4a2c-98e8-1185b141607b','ext4'];assert not x.receipt.exists()and x.receipt.parent==B/'control-logs';os.umask(0o077)
 kept=[check(p)for p in RETAIN];before=check(TARGET);assert len({(s.st_dev,s.st_ino)for s in [*kept,before]})==3
 for proc in pathlib.Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:fds=list((proc/'fd').iterdir())
  except(FileNotFoundError,ProcessLookupError):continue
  for fd in fds:
   try:s=fd.stat()
   except(FileNotFoundError,ProcessLookupError):continue
   assert(s.st_dev,s.st_ino)!=(before.st_dev,before.st_ino)
 assert str(TARGET)not in pathlib.Path('/proc/self/mountinfo').read_text()
 for p in pathlib.Path('/sys/block').glob('loop*/loop/backing_file'):assert p.read_text().strip()!=str(TARGET)
 v=os.statvfs(B);out={'target':str(TARGET),'logical_bytes':SIZE,'allocated_bytes':before.st_blocks*512,'sha256':SHA,'retained_full_archives':[str(p)for p in RETAIN],'free_before':v.f_bavail*v.f_frsize,'changed':False,'compiler_caches_removed':False,'runtime_data_changed':False,'regeneration':'copy the exact retained SHA256-verified build artifact back to the target path'}
 if x.apply:
  assert TARGET.lstat()==before;parent=os.open(TARGET.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
  try:assert os.stat(TARGET.name,dir_fd=parent,follow_symlinks=False)==before;os.unlink(TARGET.name,dir_fd=parent);os.fsync(parent)
  finally:os.close(parent)
  out['changed']=True
 assert[check(p)for p in RETAIN]==kept;v=os.statvfs(B);out['free_after']=v.f_bavail*v.f_frsize
 with x.receipt.open('x')as f:json.dump(out,f,sort_keys=True,indent=2)
 os.chown(x.receipt,1000,1000);print(json.dumps(out))
if __name__=='__main__':main()
