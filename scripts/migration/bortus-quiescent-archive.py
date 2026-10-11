"""Single quiescent reader -> pinned age archive -> exclusive NAS ciphertext copy."""
import hashlib
import importlib.util
import json
import math
import os
import pathlib
import re
import shlex
import signal
import stat
import subprocess
import sys
import time


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module); return module


quiescent = load('quiescent_archive_source', 'bortus-quiescent-source.py')
reader = load('quiescent_archive_reader', 'bortus-restore-reader.py')
archive = load('quiescent_archive_crypto', 'bortus-sqlite-archive.py')
credentials = reader.credentials
RUNTIME = pathlib.Path.home() / '.local/share/branconet-migration'
NAS_ROOT = '/mnt/container-backups/k8s-migration-20261009'
spawn = subprocess.Popen
POPEN_TYPE = subprocess.Popen
CLEANUP_GRACE = .250


class Refused(RuntimeError):
    def __init__(self, code):
        self.code = code if code in ('configuration','deadline','ownership','holder','credential','archive','nas','cleanup','replay') else 'archive'
        super().__init__('Quiescent archive refused: ' + self.code)


def need(value, code):
    if not value: raise Refused(code)


def remaining(deadline):
    now = time.monotonic()
    need(type(deadline) in (int,float) and math.isfinite(deadline) and now < deadline <= now + 2100, 'deadline')
    return deadline - now


class Children:
    """One shared expiry and one total post-expiry reap margin; never unrelated groups."""
    def __init__(self, deadline):
        self.deadline, self.grace_until = deadline, None

    def __call__(self, child):
        if child is None: return
        need(type(child) is POPEN_TYPE, 'cleanup')
        if child.poll() is not None: return
        def send(sig):
            try:
                if os.getpgid(child.pid) == child.pid: os.killpg(child.pid, sig)
                else: os.kill(child.pid, sig)
            except ProcessLookupError: pass
        left = self.deadline - time.monotonic()
        if left > 0:
            send(signal.SIGTERM)
            try: child.wait(timeout=min(.1,left)); return
            except subprocess.TimeoutExpired: pass
        send(signal.SIGKILL)
        left = self.deadline - time.monotonic()
        if left <= 0:
            if self.grace_until is None: self.grace_until = time.monotonic() + CLEANUP_GRACE
            left = self.grace_until - time.monotonic()
        child.wait(timeout=max(0,left))


class Pin:
    def __init__(self, path, maximum, *, parent_mode=0o700):
        self.path, self.fds, self.anchors = pathlib.Path(path), [], []
        try:
            need(self.path.is_absolute() and '..' not in self.path.parts and len(self.path.parts)<=32,'ownership')
            fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC);self.fds.append(fd);place=pathlib.Path('/')
            for part in self.path.parts[1:-1]:
                fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd);self.fds.append(fd);place/=part
                i=os.fstat(fd);need(i.st_uid in (0,os.getuid()) and stat.S_IMODE(i.st_mode)&0o022==0,'ownership')
                self.anchors.append((place,fd,(i.st_dev,i.st_ino,i.st_uid,stat.S_IMODE(i.st_mode))))
            need(os.fstat(fd).st_uid==os.getuid() and stat.S_IMODE(os.fstat(fd).st_mode)==parent_mode,'ownership')
            self.fd=os.open(self.path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=fd);self.fds.append(self.fd)
            i=os.fstat(self.fd);need(stat.S_ISREG(i.st_mode) and i.st_uid==os.getuid() and stat.S_IMODE(i.st_mode)==0o600 and i.st_nlink==1 and 0<i.st_size<=maximum,'ownership')
            self.identity=reader.credentials.fingerprint(i);self.check()
        except Exception:
            self.close();raise

    def check(self): reader.check_pinned(self.path,self.fd,self.identity,self.anchors)
    @property
    def child_path(self): return '/proc/'+str(os.getpid())+'/fd/'+str(self.fd)
    def close(self):
        failed=False
        for fd in reversed(self.fds):
            try:os.close(fd)
            except Exception:failed=True
        self.fds=[];need(not failed,'cleanup')


# Public fixed remote program: only ciphertext and bounded metadata enter stdin.
NAS_PROGRAM = r"""
import hashlib,json,os,pathlib,stat,sys,time
root=pathlib.Path('/mnt/container-backups/k8s-migration-20261009');parent=target=None
try:
 header=sys.stdin.buffer.readline(1025)
 if len(header)>1024 or not header.endswith(b'\n'):raise ValueError()
 info=json.loads(header)
 if set(info)!={'name','bytes','sha256','seconds'}:raise ValueError()
 import re
 if not isinstance(info['name'],str) or not re.fullmatch('bortus-sqlite-[0-9a-f]{12}\.age',info['name']):raise ValueError()
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
  for v in (i,n):
   if not stat.S_ISREG(v.st_mode) or v.st_uid!=os.getuid() or stat.S_IMODE(v.st_mode)!=0o600 or v.st_nlink!=1:raise ValueError()
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
 print(json.dumps({'bytes':info['bytes'],'sha256':digest.hexdigest(),'fsynced':True,'same_inode_readback':True}),flush=True)
except Exception:sys.exit(1)
finally:
 for fd in(target,parent):
  if fd is not None:os.close(fd)
"""


def binary(name):
    path=RUNTIME/'bin'/name;place=pathlib.Path('/')
    for part in path.parts[1:-1]:
        place/=part;i=place.lstat()
        need(stat.S_ISDIR(i.st_mode) and i.st_uid in(0,os.getuid()) and stat.S_IMODE(i.st_mode)&0o022==0,'ownership')
    i=path.lstat();need(stat.S_ISREG(i.st_mode) and i.st_uid==os.getuid() and i.st_nlink==1 and
        stat.S_IMODE(i.st_mode)&0o022==0 and stat.S_IMODE(i.st_mode)&0o100,'ownership')
    return path


def copy_nas(cipher,run_id,expected_sha,deadline,children):
    child=None;pipes=[]
    try:
        cipher.check();size=os.fstat(cipher.fd).st_size;need(0<size<=archive.MAX_TOTAL+1048576,'nas')
        name='bortus-sqlite-'+run_id+'.age'
        args=[str(binary('ssh')),'-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ForwardAgent=no',
            '-o','ConnectTimeout='+str(max(1,min(30,int(remaining(deadline))))),'-p','2002','james@192.168.0.4',
            'python3 -c '+shlex.quote(NAS_PROGRAM)]
        child=spawn(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True,
            close_fds=True,env={'HOME':str(pathlib.Path.home()),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        writer=archive.Pipe(child.stdin,deadline,False);pipes.append(writer)
        writer.write(json.dumps({'name':name,'bytes':size,'sha256':expected_sha,'seconds':remaining(deadline)},separators=(',',':')).encode()+b'\n')
        os.lseek(cipher.fd,0,os.SEEK_SET);digest=hashlib.sha256()
        while True:
            remaining(deadline);block=os.read(cipher.fd,archive.CHUNK)
            if not block:break
            digest.update(block);writer.write(block)
        child.stdin.close();cipher.check();need(digest.hexdigest()==expected_sha,'nas')
        response=archive.Pipe(child.stdout,deadline,True);pipes.append(response);raw=bytearray()
        while len(raw)<=1024:
            block=response.read(min(1025-len(raw),1024))
            if not block:break
            raw.extend(block)
        need(len(raw)<=1024 and child.wait(timeout=remaining(deadline))==0,'nas')
        result=json.loads(raw);need(type(result)is dict and set(result)=={'bytes','sha256','fsynced','same_inode_readback'} and
            type(result['bytes'])is int and result['bytes']==size and result['sha256']==expected_sha and
            result['fsynced']is True and result['same_inode_readback']is True,'nas')
        cipher.check();remaining(deadline);return NAS_ROOT+'/'+name
    finally:
        failed=False
        for pipe in pipes:
            try:pipe.close()
            except Exception:failed=True
        try:children(child)
        except Exception:failed=True
        if child:
            for stream in(child.stdin,child.stdout,child.stderr):
                if stream and not stream.closed:
                    try:stream.close()
                    except Exception:failed=True
        need(not failed,'cleanup')


class QuiescentArchive:
    def __init__(self,options,kubeconfig_path,recipient_path,identity_path):
        need(type(options)is credentials.OperatorMTLSOptions and options.path==pathlib.Path(kubeconfig_path),'configuration')
        self.options,self.config=options,pathlib.Path(kubeconfig_path)
        self.recipient,self.identity=pathlib.Path(recipient_path),pathlib.Path(identity_path)
        self.attempted=False

    def _capture(self,operation,deadline):
        need(type(operation)is quiescent.QuiescentCheckpoint and deadline==operation.deadline and
            operation.r.get('sqlite_archive_state')=='pending' and not self.attempted,'configuration')
        remaining(deadline);self.attempted=True
        source=None;descriptors=[];pins=[];children=Children(deadline);failure=None;result=None
        try:
            def fresh():
                remaining(deadline);operation.source(stopped=True,holder=True)
                pod=operation.holder();reader.inert_holder(pod,operation.r['holder_proposal'])
                need(pod['metadata']['uid']==operation.r['holder_identity']['uid'] and
                    pod['metadata']['name']==operation.r['holder_identity']['name'] and
                    pod['metadata']['namespace']=='bortus','holder')
                remaining(deadline);return pod
            pod=fresh();holder={k:pod['metadata'][k]for k in('name','namespace','uid','resourceVersion')}
            for path in(self.recipient,self.identity):pins.append(Pin(path,65536))
            config_fd,descriptors,anchors,config_identity=reader.pin_config(self.config)
            context,headers=self.options();context=headers=None
            current=fresh();need(all(current['metadata'][k]==holder[k] for k in holder),'holder')
            reader.check_pinned(self.config,config_fd,config_identity,anchors)
            args=[str(binary('kubectl')),'--kubeconfig','/proc/self/fd/'+str(config_fd),
                '--request-timeout='+format(remaining(deadline),'.6f')+'s','-n','bortus','exec',holder['name'],'-c','holder','-i','--','node','-']
            source=spawn(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True,
                pass_fds=(config_fd,),close_fds=True,env={'HOME':str(pathlib.Path.home()),'PATH':str(RUNTIME/'bin')+':/usr/bin:/bin','LANG':'C.UTF-8'})
            need(type(source)is POPEN_TYPE and source.stdin is not None and source.stdout is not None and source.stderr is None,'archive')
            writer=None
            try:
                writer=archive.Pipe(source.stdin,deadline,False);writer.write(archive.NODE_READER.encode());source.stdin.close()
            finally:
                if writer:writer.close()
            run_id=operation.r['run_id'];need(type(run_id)is str and re.fullmatch('[0-9a-f]{12}',run_id),'ownership')
            operation.journal._owned()
            target=operation.journal.directory/'sqlite-files.age'
            result=archive.encrypt_source(source,target,binary('age'),pins[0].child_path,pins[1].child_path,deadline,
                directory_fd=operation.journal.directory_fd,cleanup=children)
            for pin in pins:pin.check()
            fresh();reader.check_pinned(self.config,config_fd,config_identity,anchors)
            cipher=Pin(target,archive.MAX_TOTAL+1048576);pins.append(cipher)
            result['nas_artifact']=copy_nas(cipher,run_id,result['ciphertext_sha256'],deadline,children)
            result['nas_ciphertext_equal']=True;fresh()
            for pin in pins:pin.check()
            remaining(deadline)
        except Refused as error:failure=error.code
        except Exception:failure='archive'
        finally:
            try:children(source)
            except Exception:failure='cleanup'
            if source:
                for stream in(source.stdin,source.stdout,source.stderr):
                    if stream and not stream.closed:
                        try:stream.close()
                        except Exception:failure='cleanup'
            for pin in reversed(pins):
                try:pin.close()
                except Exception:failure='cleanup'
            try:reader.close_descriptors(descriptors)
            except Exception:failure='cleanup'
        return (None if failure else result),failure

    def __call__(self,operation,deadline):
        result=failure=None
        try:result,failure=self._capture(operation,deadline)
        except Refused as error:failure=error.code
        except Exception:failure='archive'
        if failure:
            operation=deadline=result=None
            raise Refused(failure)
        return result
