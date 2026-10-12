
import hashlib,json,os,pathlib,stat,sys,time
root=pathlib.Path('/mnt/container-backups/k8s-migration-20261009');parent=target=None

def mount_identity():
 with open('/proc/self/mountinfo',encoding='utf-8')as stream:
  raw=stream.read(1048577)
 if len(raw)>1048576:raise ValueError()
 selected=None
 import re
 for line in raw.splitlines():
  fields=line.split();cut=fields.index('-')
  mount=re.sub(r'\\([0-7]{3})',lambda m:chr(int(m[1],8)),fields[4])
  if str(root)==mount or str(root).startswith(mount.rstrip('/')+'/'):
   if selected is None or len(mount)>len(selected[0]):
    selected=(mount,tuple(fields[:6]),tuple(fields[cut+1:]))
 if selected is None:raise ValueError()
 return selected

try:
 mount_before=mount_identity()
 header=sys.stdin.buffer.readline(1025)
 if len(header)>1024 or not header.endswith(b'\n'):raise ValueError()
 info=json.loads(header)
 if set(info)!={'name','bytes','sha256','seconds'}:raise ValueError()
 import re
 if not isinstance(info['name'],str) or not re.fullmatch('config-[0-9a-f]{12}\.age',info['name']):raise ValueError()
 if type(info['bytes'])is not int or not 0<info['bytes']<=537919488:raise ValueError()
 if not isinstance(info['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',info['sha256']):raise ValueError()
 if type(info['seconds'])not in(int,float) or not 0<info['seconds']<=2100:raise ValueError()
 deadline=time.monotonic()+info['seconds']
 parent=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 d=os.fstat(parent)
 if d.st_uid not in (0,os.getuid()) or stat.S_IMODE(d.st_mode)&0o022:raise ValueError()
 def check(i):
  n=os.stat(info['name'],dir_fd=parent,follow_symlinks=False);a=root.lstat();p=os.fstat(parent)
  if (a.st_dev,a.st_ino,a.st_uid)!=(d.st_dev,d.st_ino,d.st_uid) or (p.st_dev,p.st_ino,p.st_uid)!=(d.st_dev,d.st_ino,d.st_uid):raise ValueError()
  if mount_identity()!=mount_before:raise ValueError()
  for v in (i,n):
   if not stat.S_ISREG(v.st_mode) or v.st_uid!=os.getuid() or (stat.S_IMODE(v.st_mode)!=0o600 and not (stat.S_IMODE(v.st_mode)==0o755 and mount_before[0]=="/mnt/container-backups" and mount_before[2][0]=="cifs")) or v.st_nlink!=1:raise ValueError()
  if tuple(getattr(i,k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))!=tuple(getattr(n,k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')):raise ValueError()
 target=os.open(info['name'],os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK,0o600,dir_fd=parent)
 digest=hashlib.sha256();left=info['bytes']
 while left:
  if time.monotonic()>=deadline:raise ValueError()
  block=sys.stdin.buffer.read(min(65536,left))
  if not block:raise ValueError()
  pending=memoryview(block)
  while pending:
   n=os.write(target,pending)
   if n<=0:raise ValueError()
   pending=pending[n:]
  digest.update(block);left-=len(block)
 if sys.stdin.buffer.read(1) or digest.hexdigest()!=info['sha256']:raise ValueError()
 os.fsync(target);os.fsync(parent);before=os.fstat(target);check(before)
 os.close(target);target=os.open(info['name'],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
 if tuple(getattr(before,k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))!=tuple(getattr(os.fstat(target),k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')):raise ValueError()
 digest=hashlib.sha256()
 while True:
  if time.monotonic()>=deadline:raise ValueError()
  block=os.read(target,65536)
  if not block:break
  digest.update(block)
 check(os.fstat(target))
 if os.fstat(target).st_size!=info['bytes'] or digest.hexdigest()!=info['sha256']:raise ValueError()
 print(json.dumps({'bytes':info['bytes'],'sha256':digest.hexdigest(),'fsynced':True,'same_inode_readback':True,'cipher_mode':stat.S_IMODE(os.fstat(target).st_mode),'cifs_mount':mount_before[0]=='/mnt/container-backups' and mount_before[2][0]=='cifs'}),flush=True)
except Exception:sys.exit(1)
finally:
 for fd in(target,parent):
  if fd is not None:os.close(fd)
