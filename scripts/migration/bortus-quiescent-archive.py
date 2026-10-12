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
import types
import sqlite3
import uuid


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module); return module


quiescent = load('quiescent_archive_source', 'bortus-quiescent-source.py')
reader = load('quiescent_archive_reader', 'bortus-restore-reader.py')
archive = load('quiescent_archive_crypto', 'bortus-sqlite-archive.py')
credentials = reader.credentials
normalization = load('quiescent_schema_normalization', 'normalize-bortus-sqlite-archive.py')
RUNTIME = pathlib.Path.home() / '.local/share/branconet-migration'
NAS_ROOT = '/mnt/container-backups/k8s-migration-20261009'
spawn = subprocess.Popen
POPEN_TYPE = subprocess.Popen
CLEANUP_GRACE = .250
SSH_IDENTITY = pathlib.Path.home() / '.ssh/id_ed25519'


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


class NasToolPin:
    """Fixed public SSH executable; private identity bytes are never read here."""
    def __init__(self, expected_sha):
        self.path=binary('ssh');self.fds=[];self.anchors=[]
        try:
            need(type(expected_sha)is str and re.fullmatch('[0-9a-f]{64}',expected_sha),'configuration')
            fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC);self.fds.append(fd);place=pathlib.Path('/')
            for part in self.path.parts[1:-1]:
                fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd);self.fds.append(fd);place/=part;i=os.fstat(fd)
                need(i.st_uid in(0,os.getuid())and not i.st_mode&0o022,'ownership');self.anchors.append((place,fd,(i.st_dev,i.st_ino,i.st_uid,stat.S_IMODE(i.st_mode))))
            self.fd=os.open(self.path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=fd);self.fds.append(self.fd);i=os.fstat(self.fd)
            need(stat.S_ISREG(i.st_mode)and i.st_uid==os.getuid()and i.st_nlink==1 and stat.S_IMODE(i.st_mode)==0o700 and 0<i.st_size<=4*1024*1024,'ownership')
            raw=os.pread(self.fd,i.st_size+1,0);need(len(raw)==i.st_size and hashlib.sha256(raw).hexdigest()==expected_sha,'ownership');self.identity=credentials.fingerprint(i);self.check()
        except Exception:self.close();raise
    def check(self):reader.check_pinned(self.path,self.fd,self.identity,self.anchors)
    def close(self):reader.close_descriptors(self.fds);self.fds=[]


class NasIntent:
    """One closed exclusive sidecar; its confirmation also requires callback/launcher0."""
    def __init__(self,operation,binding,name,size,digest):
        self.journal=operation.journal;self.identity=None
        self.data={'abi':1,'scope':'quiescent SQLite ciphertext NAS only','run_id':operation.r['run_id'],
            'state':'pending','writer_binding':binding,'name':name,'cipher_bytes':size,'ciphertext_sha256':digest,
            'requires_return_and_launcher_terminal0':True,'result':None}
        self.save(new=True)
    def save(self,new=False):
        self.journal._owned();fd=None;name='sqlite-nas.json'if new else'sqlite-nas-'+uuid.uuid4().hex+'.next'
        if not new:
            current=os.stat('sqlite-nas.json',dir_fd=self.journal.directory_fd,follow_symlinks=False)
            need(credentials.fingerprint(current)==self.identity,'ownership')
        try:
            raw=json.dumps(self.data,sort_keys=True,separators=(',',':')).encode()+b'\n';need(len(raw)<=4096,'ownership')
            fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=self.journal.directory_fd)
            with os.fdopen(fd,'wb',closefd=False)as stream:stream.write(raw);stream.flush();os.fsync(fd)
            self.journal._owned()
            if not new:
                need(credentials.fingerprint(os.stat('sqlite-nas.json',dir_fd=self.journal.directory_fd,follow_symlinks=False))==self.identity,'ownership')
                os.replace(name,'sqlite-nas.json',src_dir_fd=self.journal.directory_fd,dst_dir_fd=self.journal.directory_fd)
            self.identity=credentials.fingerprint(os.fstat(fd));os.fsync(self.journal.directory_fd)
        finally:
            if fd is not None:os.close(fd)
    def finish(self,state,result=None):self.data.update(state=state,result=result);self.save()


def sqlite_cipher_writer(ssh_sha256):
    path=pathlib.Path(__file__).with_name('capture-kubernetes-recovery-config.py');before=hashlib.sha256(path.read_bytes()).hexdigest()
    factory=load('quiescent_cipher_nas_factory',path.name)
    program=factory.nas_program(types.SimpleNamespace(q=sys.modules[__name__]),prefix='bortus-sqlite')
    need(hashlib.sha256(path.read_bytes()).hexdigest()==before,'ownership')
    return program,{'prefix':'bortus-sqlite','factory_source_sha256':before,'base_program_sha256':hashlib.sha256(NAS_PROGRAM.encode()).hexdigest(),
        'writer_sha256':hashlib.sha256(program.encode()).hexdigest(),'ssh_sha256':ssh_sha256}


def _copy_nas_default(cipher,run_id,expected_sha,deadline,children):
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


def copy_nas(cipher,run_id,expected_sha,deadline,children,*,cifs_ciphertext=False,operation=None,ssh_sha256=None):
    need(type(cifs_ciphertext)is bool,'configuration')
    if not cifs_ciphertext:return _copy_nas_default(cipher,run_id,expected_sha,deadline,children)
    return _copy_nas_cipher(cipher,run_id,expected_sha,deadline,children,cifs_ciphertext=True,operation=operation,ssh_sha256=ssh_sha256)


def _copy_nas_cipher(cipher,run_id,expected_sha,deadline,children,*,cifs_ciphertext=False,operation=None,ssh_sha256=None):
    child=None;pipes=[];pins=[];intent=None;failure=None;result=None
    try:
        need(type(cifs_ciphertext)is bool,'configuration')
        cipher.check();size=os.fstat(cipher.fd).st_size;need(0<size<=archive.MAX_TOTAL+1048576,'nas')
        name='bortus-sqlite-'+run_id+'.age'
        program=NAS_PROGRAM;extra=[];pass_fds=()
        if cifs_ciphertext:
            need(operation is not None and operation.deadline==deadline and operation.r['run_id']==run_id and operation.r.get('sqlite_archive_state')=='pending','configuration')
            need(type(run_id)is str and re.fullmatch('[0-9a-f]{12}',run_id)and type(expected_sha)is str and re.fullmatch('[0-9a-f]{64}',expected_sha),'configuration')
            key=Pin(SSH_IDENTITY,65536);pins.append(key);tool=NasToolPin(ssh_sha256);pins.append(tool)
            program,binding=sqlite_cipher_writer(ssh_sha256);intent=NasIntent(operation,binding,name,size,expected_sha)
            extra=['-o','IdentitiesOnly=yes','-o','IdentityAgent=none','-i',str(SSH_IDENTITY)];pass_fds=(tool.fd,)
            for pin in pins:pin.check()
        args=[str(binary('ssh')),'-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ForwardAgent=no',
            *extra,'-o','ConnectTimeout='+str(max(1,min(30,int(remaining(deadline))))),'-p','2002','james@192.168.0.4',
            'python3 -c '+shlex.quote(program)]
        if cifs_ciphertext:args[0]='/proc/self/fd/'+str(tool.fd)
        child=spawn(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True,
            close_fds=True,**({'pass_fds':pass_fds}if cifs_ciphertext else{}),env={'HOME':str(pathlib.Path.home()),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
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
        def unique(pairs):
            value={}
            for key,item in pairs:need(key not in value,'nas');value[key]=item
            return value
        result=json.loads(raw,**({'object_pairs_hook':unique}if cifs_ciphertext else{}));fields={'bytes','sha256','fsynced','same_inode_readback'}|({'cipher_mode','cifs_mount'}if cifs_ciphertext else set())
        need(type(result)is dict and set(result)==fields and
            type(result['bytes'])is int and result['bytes']==size and result['sha256']==expected_sha and
            result['fsynced']is True and result['same_inode_readback']is True,'nas')
        if cifs_ciphertext:need(type(result['cipher_mode'])is int and type(result['cifs_mount'])is bool and(result['cipher_mode']==0o600 or result['cipher_mode']==0o755 and result['cifs_mount']is True),'nas')
        cipher.check();remaining(deadline)
        for pin in pins:pin.check()
    except Refused as error:failure=error.code
    except Exception:failure='nas'
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
        for pin in reversed(pins):
            try:pin.close()
            except Exception:failed=True
        if failed:failure='cleanup'
        if intent:
            try:
                if not failure:remaining(deadline)
                intent.finish('uncertain'if failure else'confirmed',None if failure else result)
                if not failure:remaining(deadline)
            except Exception:failure='nas'
    cipher=operation=child=pins=pipes=intent=None
    if failure:raise Refused(failure)
    return NAS_ROOT+'/'+name


class QuiescentArchive:
    def __init__(self,options,kubeconfig_path,recipient_path,identity_path,*,quiescent_module=None,cifs_ciphertext_nas=False,ssh_sha256=None):
        need(type(options)is credentials.OperatorMTLSOptions and options.path==pathlib.Path(kubeconfig_path),'configuration')
        selected=quiescent if quiescent_module is None else quiescent_module
        need(type(selected)is types.ModuleType and pathlib.Path(selected.__file__).resolve()==
            pathlib.Path(quiescent.__file__).resolve() and
            selected.QuiescentCheckpoint.__module__==selected.__name__,'configuration')
        self.quiescent=selected
        self.options,self.config=options,pathlib.Path(kubeconfig_path)
        self.recipient,self.identity=pathlib.Path(recipient_path),pathlib.Path(identity_path)
        need(type(cifs_ciphertext_nas)is bool and(not cifs_ciphertext_nas or type(ssh_sha256)is str and re.fullmatch('[0-9a-f]{64}',ssh_sha256)),'configuration')
        self.cifs_ciphertext_nas,self.ssh_sha256=cifs_ciphertext_nas,ssh_sha256
        self.attempted=False

    def _capture(self,operation,deadline):
        need(type(operation)is self.quiescent.QuiescentCheckpoint and deadline==operation.deadline and
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
            result['nas_artifact']=copy_nas(cipher,run_id,result['ciphertext_sha256'],deadline,children,
                **({'cifs_ciphertext':True,'operation':operation,'ssh_sha256':self.ssh_sha256}if self.cifs_ciphertext_nas else{}))
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


    def _schema_metadata(self,operation,manifest_path,manifest_sha256,deadline):
        temporary=connection=key=None;failure=result=None
        try:
            need(type(operation)is self.quiescent.QuiescentCheckpoint and deadline==operation.deadline and
                operation.r.get('quiescent',{}).get('state')in('captured-zero','guard-transition-open') and
                operation.r.get('sqlite_archive_state')=='confirmed','configuration')
            remaining(deadline);before=operation.source(stopped=True)
            need(type(manifest_sha256)is str and re.fullmatch('[0-9a-f]{64}',manifest_sha256),'configuration')
            fd=os.open(manifest_path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            try:
                info=os.fstat(fd);need(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and
                    info.st_nlink==1 and info.st_mode&0o022==0 and 0<info.st_size<=65536,'configuration')
                raw=os.read(fd,65537);after_info=os.fstat(fd);path_info=os.stat(manifest_path,follow_symlinks=False)
                need(len(raw)==info.st_size and all(getattr(info,k)==getattr(after_info,k)==getattr(path_info,k)
                    for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_uid','st_nlink')) and
                    hashlib.sha256(raw).hexdigest()==manifest_sha256,'configuration')
            finally:os.close(fd)
            manifest=json.loads(raw);expected=manifest['migrations'];topology=manifest['public_table_columns']
            need(manifest['legacy_image']==operation.r['baseline']['legacy_image'] and len(expected)==7 and
                len(topology)==13 and all(re.fullmatch('[a-z_]+',n)for n in topology),'configuration')
            cipher=operation.r['sqlite_archive'];need(cipher['artifact']==str(operation.journal.directory/'sqlite-files.age'),'ownership')
            key=Pin(self.identity,65536)
            # A bounded subordinate budget never extends the existing whole lease.
            limit=min(deadline,time.monotonic()+300)
            temporary=normalization.normalize(cipher['artifact'],cipher['ciphertext_sha256'],key.child_path,
                age=binary('age'),seconds=300,deadline=limit)
            connection=sqlite3.connect('file:'+temporary['database_path']+'?mode=ro',uri=True,timeout=1)
            connection.set_progress_handler(lambda:int(time.monotonic()>=limit),1000)
            connection.execute('PRAGMA trusted_schema=OFF');connection.execute('BEGIN')
            rows=connection.execute('SELECT migration_name,checksum,finished_at,rolled_back_at FROM _prisma_migrations ORDER BY migration_name LIMIT 33').fetchall()
            need(len(rows)==7 and all(row[0]==e['name'] and row[1]==e['checksum'] and row[2]is not None and
                row[3]is None for row,e in zip(rows,expected)),'archive')
            names=[row[0]for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name!='_prisma_migrations' ORDER BY name LIMIT 65")]
            need(names==sorted(topology),'archive')
            for name in names:
                remaining(limit)
                actual=[list(row[1:6])for row in connection.execute('PRAGMA table_info('+name+')')]
                need(actual==topology[name],'archive')
            connection.execute('COMMIT');connection.close();connection=None
            normalization.cleanup(temporary['temporary_directory'],temporary['temporary_directory_identity']);temporary=None
            key.check();after=operation.source(stopped=True)
            need(all(before[k]['uid']==after[k]['uid']for k in before),'ownership');remaining(deadline)
            receipt={'abi':1,'scope':'authenticated latest quiescent archive schema metadata only',
                'run_id':operation.r['run_id'],'ciphertext_sha256':cipher['ciphertext_sha256'],
                'manifest_sha256':manifest_sha256,'source_identities':after,'schema_migrations':7,
                'migration_checksums_match':True,'migrations_complete':True,'tables_and_columns_match':True,
                'tmpfs_cleaned':True,'live_ready_writer_proven':False,'whole_row_preservation_proven':False,
                'forward_acceptance':False,'producer_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}
            operation.journal._owned();name='quiescent-schema-'+uuid.uuid4().hex[:12]+'.json'
            payload=json.dumps(receipt,sort_keys=True,separators=(',',':')).encode()+b'\n'
            fd=os.open(name,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600,dir_fd=operation.journal.directory_fd)
            try:
                with os.fdopen(fd,'wb')as stream:stream.write(payload);stream.flush();os.fsync(stream.fileno())
                os.fsync(operation.journal.directory_fd)
            except Exception:raise Refused('archive')from None
            operation.source(stopped=True);remaining(deadline)
            result={'schema_receipt_path':str(operation.journal.directory/name),
                'schema_receipt_sha256':hashlib.sha256(payload).hexdigest(),'schema_migrations':7}
        except Refused as error:failure=error.code
        except Exception:failure='archive'
        finally:
            if connection:
                try:connection.close()
                except Exception:failure='cleanup'
            if temporary:
                try:normalization.cleanup(temporary['temporary_directory'],temporary['temporary_directory_identity'])
                except Exception:failure='cleanup'
            if key:
                try:key.close()
                except Exception:failure='cleanup'
        return(None if failure else result),failure

    def schema_metadata(self,operation,manifest_path,manifest_sha256,*,deadline):
        result,failure=self._schema_metadata(operation,manifest_path,manifest_sha256,deadline)
        operation=manifest_path=manifest_sha256=deadline=None
        if failure:raise Refused(failure)
        return result
