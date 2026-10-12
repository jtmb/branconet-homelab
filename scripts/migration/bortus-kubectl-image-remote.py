"""Fixed public-ELF receiver/BuildKit dispatcher; invoked only by reviewed adapter."""
import hashlib
import json
import os
import pathlib
import re
import signal
import selectors
import stat
import subprocess
import sys
import uuid
import types
import time

KEYS=['org.opencontainers.image.revision','io.branconet.bortus.source-tree',
      'io.branconet.bortus.context-sha256','io.branconet.bortus.manifest-sha256','io.branconet.bortus.build-owner']


class Refused(RuntimeError): pass
def need(ok):
    if not ok:raise Refused('Remote injection refused')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def ident(i):return(i.st_dev,i.st_ino,i.st_uid,i.st_mode,i.st_nlink,i.st_size,i.st_mtime_ns,i.st_ctime_ns)


def command(argv,*,stdin,stdout,stderr,timeout,env,check=False,**ignored):
    child=selector=None;end=time.monotonic()+timeout;output=bytearray()
    try:
        child=subprocess.Popen(argv,stdin=stdin,stdout=stdout,stderr=stderr,env=env,start_new_session=True)
        if stdout==subprocess.PIPE:
            selector=selectors.DefaultSelector();os.set_blocking(child.stdout.fileno(),False);selector.register(child.stdout,selectors.EVENT_READ)
            while selector.get_map():
                left=end-time.monotonic()
                if left<=0:raise subprocess.TimeoutExpired(argv,timeout)
                for key,_ in selector.select(min(.05,left)):
                    raw=os.read(key.fileobj.fileno(),min(65536,65537-len(output)));output.extend(raw);need(len(output)<=65536)
                    if not raw:selector.unregister(key.fileobj)
        child.wait(timeout=max(0,end-time.monotonic()))
        return types.SimpleNamespace(returncode=child.returncode,stdout=bytes(output)if stdout==subprocess.PIPE else None)
    finally:
        failure=False
        if child:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            except Exception:failure=True
            try:child.wait(timeout=.25)
            except Exception:failure=True
            for stream in(child.stdin,child.stdout,child.stderr):
                if stream:
                    try:stream.close()
                    except Exception:failure=True
        if selector:
            try:selector.close()
            except Exception:failure=True
        if failure:raise Refused('Owned remote child cleanup refused')from None


def validate(request):
    need(type(request)is dict and set(request)=={'mode','commit','owner','binary_sha256','binary_bytes',
        'security_receipt_sha256','context_sha256','labels','tag'})
    need(request['mode']in('transfer','build')and re.fullmatch('[0-9a-f]{40}',request['commit'])is not None and
         str(uuid.UUID(request['owner']))==request['owner']and type(request['binary_bytes'])is int and
         64<=request['binary_bytes']<=128*1024*1024)
    need(all(type(request[k])is str and re.fullmatch('[0-9a-f]{64}',request[k])for k in('binary_sha256','security_receipt_sha256','context_sha256')))
    need(request['tag']=='bortus:release-'+request['commit']and type(request['labels'])is dict and set(request['labels'])==set(KEYS))
    values=request['labels'];need(values[KEYS[0]]==request['commit']and values[KEYS[2]]==request['context_sha256']and
        values[KEYS[4]]==request['owner']and re.fullmatch('[0-9a-f]{40}',values[KEYS[1]])and re.fullmatch('[0-9a-f]{64}',values[KEYS[3]]))


class Stage:
    def __init__(self,request,home,create):
        validate(request);self.request=request;self.home=pathlib.Path(home);self.parent_fd=self.fd=None
        self.path=self.home/('.bortus-kubectl-image-'+request['commit'])
        try:
            need(self.home.is_absolute()and self.home.resolve()==self.home)
            self.parent_fd=os.open(self.home,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            i=os.fstat(self.parent_fd);need(i.st_uid==os.getuid()and i.st_mode&0o022==0);self.parent=(i.st_dev,i.st_ino)
            if create:os.mkdir(self.path.name,0o700,dir_fd=self.parent_fd);os.fsync(self.parent_fd)
            self.fd=os.open(self.path.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=self.parent_fd)
            i=os.fstat(self.fd);need(i.st_uid==os.getuid()and stat.S_IMODE(i.st_mode)==0o700);self.anchor=(i.st_dev,i.st_ino)
            self.record=None;self.record_identity=None
            if create:self.record={'abi':1,'request':dict(request,mode='transfer'),'phase':'pending-transfer'};self.save()
            else:
                fd=os.open('record.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=self.fd)
                try:
                    i=os.fstat(fd);need(stat.S_ISREG(i.st_mode)and i.st_uid==os.getuid()and stat.S_IMODE(i.st_mode)==0o600 and i.st_nlink==1 and i.st_size<=65536)
                    raw=os.read(fd,65537);need(ident(i)==ident(os.fstat(fd))==ident(os.stat('record.json',dir_fd=self.fd,follow_symlinks=False)))
                    self.record=json.loads(raw);self.record_identity=ident(i)
                finally:os.close(fd)
                need(set(self.record)=={'abi','request','phase'}and self.record['abi']==1 and self.record['phase']=='ready'and
                     self.record['request']==dict(request,mode='transfer'))
        except Exception:self.close();raise

    def owned(self):
        a=os.fstat(self.parent_fd);b=os.fstat(self.fd)
        need(stat.S_ISDIR(self.home.lstat().st_mode)and
             (a.st_dev,a.st_ino)==self.parent==(self.home.lstat().st_dev,self.home.lstat().st_ino)and a.st_mode&0o022==0 and
             (b.st_dev,b.st_ino)==self.anchor==(self.path.lstat().st_dev,self.path.lstat().st_ino)and stat.S_IMODE(b.st_mode)==0o700)
        if self.record_identity:need(ident(os.stat('record.json',dir_fd=self.fd,follow_symlinks=False))==self.record_identity)

    def save(self):
        self.owned();name='record-'+uuid.uuid4().hex+'.next'
        fd=os.open(name,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600,dir_fd=self.fd)
        try:
            with os.fdopen(fd,'wb',closefd=False)as out:out.write((json.dumps(self.record,sort_keys=True)+'\n').encode());out.flush();os.fsync(fd)
            self.owned();os.replace(name,'record.json',src_dir_fd=self.fd,dst_dir_fd=self.fd);os.fsync(self.fd);self.record_identity=ident(os.fstat(fd))
        finally:os.close(fd)

    def binary(self):
        self.owned();directory=self.path/'bortus_kubectl';i=directory.lstat()
        need(stat.S_ISDIR(i.st_mode)and i.st_uid==os.getuid()and stat.S_IMODE(i.st_mode)==0o700 and sorted(p.name for p in directory.iterdir())==['kubectl'])
        fd=os.open(directory/'kubectl',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            i=os.fstat(fd);need(stat.S_ISREG(i.st_mode)and i.st_uid==os.getuid()and stat.S_IMODE(i.st_mode)==0o600 and i.st_nlink==1 and i.st_size==self.request['binary_bytes'])
            h=hashlib.sha256();count=0;header=b''
            while True:
                raw=os.read(fd,65536)
                if not raw:break
                if not header:header=raw[:64]
                count+=len(raw);need(count<=self.request['binary_bytes']);h.update(raw)
            need(count==i.st_size and h.hexdigest()==self.request['binary_sha256']and header[:6]==b'\x7fELF\x02\x01'and
                 int.from_bytes(header[18:20],'little')==62 and ident(i)==ident(os.fstat(fd))==ident((directory/'kubectl').lstat()))
            self.owned()
        finally:os.close(fd)
        return directory

    def transfer(self,stream):
        self.owned();directory=self.path/'bortus_kubectl';directory.mkdir(mode=0o700)
        fd=os.open(directory/'kubectl',os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,'wb',closefd=False)as out:
                count=0
                while True:
                    raw=stream.read(min(65536,self.request['binary_bytes']-count+1))
                    if not raw:break
                    count+=len(raw);need(count<=self.request['binary_bytes']);out.write(raw)
                need(count==self.request['binary_bytes']);out.flush();os.fsync(fd)
        finally:os.close(fd)
        d=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(d)
        finally:os.close(d)
        self.binary();self.record['phase']='ready';self.save()
        return {'owner':self.request['owner'],'binary_sha256':self.request['binary_sha256'],'binary_bytes':self.request['binary_bytes'],'phase':'ready'}

    def build(self,stream,invoke=command):
        context=self.binary();empty=self.path/'docker-config';empty.mkdir(mode=0o700)
        env={'PATH':'/usr/bin:/bin','HOME':str(self.home),'DOCKER_CONFIG':str(empty),'DOCKER_BUILDKIT':'1'}
        query=['docker','image','ls','--quiet','--filter','reference='+self.request['tag']]
        found=invoke(query,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=30,env=env,check=False)
        need(found.returncode==0 and found.stdout==b'');self.binary()
        self.record['phase']='pending-build';self.save()
        argv=['docker','build','--build-context','bortus_kubectl='+str(context),'--build-arg',
              'BORTUS_KUBECTL_SHA256='+self.request['binary_sha256'],'-t',self.request['tag']]
        for key,value in self.request['labels'].items():argv+=['--label',key+'='+value]
        argv+=['-'];self.binary();child=None;failure=False
        try:
            # Root owns builder/tag exclusivity; Docker offers no atomic tag CAS.
            child=invoke(argv,stdin=stream,stdout=None,stderr=None,timeout=2400,env=env,check=False,start_new_session=True)
            self.binary();self.record.update(phase='built'if child.returncode==0 else'failed',actual_build_exit_code=child.returncode);self.save()
            return child.returncode
        except Exception:
            self.record['phase']='uncertain'
            try:self.save()
            except Exception:pass
            raise Refused('Remote build uncertain')from None

    def close(self):
        for name in('fd','parent_fd'):
            fd=getattr(self,name,None)
            if fd is not None:os.close(fd);setattr(self,name,None)


if __name__=='__main__':
    stage=None;code=1
    try:
        request=json.loads(sys.argv[1]);stage=Stage(request,pathlib.Path.home(),request['mode']=='transfer')
        if request['mode']=='transfer':print(json.dumps(stage.transfer(sys.stdin.buffer)));code=0
        else:code=stage.build(sys.stdin.buffer)
    except Exception:print('Remote injection refused or uncertain',file=sys.stderr)
    finally:
        if stage:stage.close()
    raise SystemExit(code)
