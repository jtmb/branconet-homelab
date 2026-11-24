#!/usr/bin/env python3
"""Fresh raw-etcd age checkpoint; exact authenticated bytes, bounded owned restore."""
import base64,copy,datetime,hashlib,importlib.util,json,math,os,pathlib,re,selectors,shlex,signal,stat,subprocess,sys,time,types,uuid


def load(name,file):
    spec=importlib.util.spec_from_file_location(name,pathlib.Path(__file__).with_name(file));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
q=load('etcd_owned_primitives','bortus-quiescent-archive.py')
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
MAX=512*1024*1024;MAX_REGISTRY=64*1024*1024;MAX_KEYS=10000;NS='migration-system'
SSH_IDENTITY=pathlib.Path.home()/'.ssh/id_ed25519'
SSH_BINARY=pathlib.Path('/usr/bin/ssh')
SSH=[str(SSH_BINARY),'-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','IdentitiesOnly=yes','-o','ForwardAgent=no','-o','ConnectTimeout=15','-i',str(SSH_IDENTITY),'-p','2002','james@192.168.0.4']
REQUIRED={'/etc/kubernetes/encryption-config.json','/etc/kubernetes/longhorn-crypto-key','/etc/kubernetes/pki/ca.crt','/etc/kubernetes/pki/ca.key','/etc/kubernetes/pki/sa.key','/etc/kubernetes/pki/sa.pub','/etc/kubernetes/pki/apiserver.crt','/etc/kubernetes/pki/apiserver.key','/etc/kubernetes/pki/etcd/ca.crt','/etc/kubernetes/pki/etcd/ca.key'}
CONFIG_PATHS=REQUIRED|{'/etc/kubernetes/'+n+'.conf'for n in('admin','kubelet','controller-manager','scheduler')}|{'/etc/kubernetes/manifests/'+n+'.yaml'for n in('etcd','kube-apiserver','kube-controller-manager','kube-scheduler')}
class Refused(RuntimeError):
    def __init__(self,code):
        self.code=code if code in {'input','deadline','child','cleanup','ownership','bound','json','identity','replay','keys','registry','snapshot','archive','resource','uncertain','nas','durability','operation'}else'operation'
        super().__init__('Etcd checkpoint refused: '+self.code)
def need(value,code='input'):
    if not value:raise Refused(code)
def left(deadline):
    now=time.monotonic();need(type(deadline)in(int,float)and math.isfinite(deadline)and now<deadline<=now+2100,'deadline');return deadline-now
def unique(pairs):
    result={}
    for k,v in pairs:need(k not in result,'json');result[k]=v
    return result
def decode(raw):return json.loads(raw,object_pairs_hook=unique)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def fp(i):return(i.st_dev,i.st_ino,i.st_uid,i.st_mode,i.st_size,i.st_mtime_ns,i.st_ctime_ns,i.st_nlink)
def identity(obj):
    m=obj.get('metadata',{});r={k:m.get(k)for k in('name','namespace','uid','resourceVersion')}
    need(all(type(r[k])is str and re.fullmatch('[A-Za-z0-9_.:-]{1,253}',r[k])for k in('name','uid','resourceVersion'))and not m.get('deletionTimestamp'),'identity');return r

class Ledger:
    def __init__(self,parent,run_id):
        self.fd=self.parent_fd=None;self.record_identity=None;need(re.fullmatch('[0-9a-f]{12}',run_id),'input');self.parent=pathlib.Path(parent);self.path=self.parent/('etcd-'+run_id)
        try:
            need(self.parent.is_absolute()and self.parent.resolve()==self.parent,'ownership');self.parent_fd=os.open(self.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            i=os.fstat(self.parent_fd);need(i.st_uid==os.getuid()and not i.st_mode&0o022,'ownership');self.parent_identity=(i.st_dev,i.st_ino)
            os.mkdir(self.path.name,0o700,dir_fd=self.parent_fd);os.fsync(self.parent_fd);self.fd=os.open(self.path.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=self.parent_fd)
            i=os.fstat(self.fd);self.directory_identity=(i.st_dev,i.st_ino);self.r={'abi':1,'run_id':run_id,'phase':'preparing','operations':{},'actual_production_checkpoint_accepted':False,'confirmation_requires_launcher_terminal0':True};self.save()
        except Exception:self.close();raise
    def owned(self):
        p=os.fstat(self.parent_fd);d=os.fstat(self.fd);a=self.parent.lstat();b=self.path.lstat()
        need(stat.S_ISDIR(a.st_mode)and stat.S_ISDIR(b.st_mode)and(p.st_dev,p.st_ino)==self.parent_identity==(a.st_dev,a.st_ino)and not p.st_mode&0o022 and(d.st_dev,d.st_ino)==self.directory_identity==(b.st_dev,b.st_ino)and stat.S_IMODE(d.st_mode)==0o700,'ownership')
        if self.record_identity:need(fp(os.stat('record.json',dir_fd=self.fd,follow_symlinks=False))==self.record_identity,'ownership')
    def save(self):
        self.owned();name='record-'+uuid.uuid4().hex+'.next';raw=(json.dumps(self.r,sort_keys=True,indent=2)+'\n').encode();need(len(raw)<=65536,'bound');fd=os.open(name,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600,dir_fd=self.fd)
        try:
            with os.fdopen(fd,'wb',closefd=False)as f:f.write(raw);f.flush();os.fsync(fd)
            self.owned();os.replace(name,'record.json',src_dir_fd=self.fd,dst_dir_fd=self.fd);self.record_identity=fp(os.fstat(fd));os.fsync(self.fd)
        finally:os.close(fd)
    def intent(self,action,details):
        need(action not in self.r['operations'],'replay');self.r['operations'][action]={'state':'pending','details':details};self.save()
    def confirm(self,action,result=None):
        need(self.r['operations'][action]['state']=='pending','replay');self.r['operations'][action].update(state='confirmed',result=result);self.save()
    def close(self):
        failed=False
        for name in('fd','parent_fd'):
            f=getattr(self,name,None)
            if f is not None:
                try:os.close(f)
                except Exception:failed=True
                setattr(self,name,None)
        need(not failed,'cleanup')

def collect(child,deadline,children,body=b'',maximum=65536):
    selector=None;raw=bytearray();failure=None
    try:
        selector=selectors.DefaultSelector();os.set_blocking(child.stdout.fileno(),False);selector.register(child.stdout,selectors.EVENT_READ);pending=memoryview(body)
        if child.stdin and not child.stdin.closed:
            os.set_blocking(child.stdin.fileno(),False)
            if pending:selector.register(child.stdin,selectors.EVENT_WRITE)
            else:child.stdin.close()
        else:need(not pending,'child')
        while selector.get_map():
            for key,_ in selector.select(min(.05,left(deadline))):
                if key.fileobj is child.stdin:
                    n=os.write(child.stdin.fileno(),pending[:65536]);pending=pending[n:]
                    if not pending:selector.unregister(child.stdin);child.stdin.close()
                else:
                    b=os.read(child.stdout.fileno(),min(65536,maximum-len(raw)+1));raw.extend(b);need(len(raw)<=maximum,'bound')
                    if not b:selector.unregister(child.stdout)
        need(child.wait(timeout=left(deadline))==0,'child')
    except Exception:failure='child'
    finally:
        try:children(child)
        except Exception:failure='cleanup'
        for f in(child.stdin,child.stdout,child.stderr):
            if f and not f.closed:
                try:f.close()
                except Exception:failure='cleanup'
        if selector:
            try:selector.close()
            except Exception:failure='cleanup'
    result=bytes(raw)if not failure else None;raw=body=pending=child=None
    if failure:raise Refused(failure)
    return result

# Fixed privileged program: only nonsecret mode/path/count/inode in argv.
# An unprivileged wrapper consumes the private line and pins a distinct body FIFO.
REMOTE=r"""
import os,pathlib,stat,json,sys,hashlib,time,base64,re
def unique(pairs):
 out={}
 for k,v in pairs:
  if k in out:raise ValueError()
  out[k]=v
 return out
r=json.loads(sys.argv[1],object_pairs_hook=unique);run=r['run_id'];mode=r['mode'];fds=[]
try:
 if not re.fullmatch('[0-9a-f]{12}',run):raise ValueError()
 body=None;header=None
 if mode=='receive':
  descriptor=r['body_pipe']
  if set(descriptor)!={'pid','fd','uid','start_ticks','pipe_dev','pipe_ino'} or any(type(descriptor[k])is not int or descriptor[k]<0 for k in descriptor):raise ValueError()
  process='/proc/'+str(descriptor['pid'])
  def owner():
   if os.stat(process).st_uid!=descriptor['uid'] or int(pathlib.Path(process+'/stat').read_text().rsplit(')',1)[1].split()[19])!=descriptor['start_ticks']:raise ValueError()
  owner()
  pipe=os.open('/proc/'+str(descriptor['pid'])+'/fd/'+str(descriptor['fd']),os.O_RDONLY|os.O_NONBLOCK);fds.append(pipe);pi=os.fstat(pipe)
  if not stat.S_ISFIFO(pi.st_mode) or pi.st_uid!=descriptor['uid'] or(pi.st_dev,pi.st_ino)!=(descriptor['pipe_dev'],descriptor['pipe_ino']):raise ValueError()
  owner()
  os.set_blocking(pipe,True);body=os.fdopen(pipe,'rb',closefd=False)
  line=body.readline(1025)
  if len(line)>1024 or not line.endswith(b'\n'):raise ValueError()
  header=json.loads(line,object_pairs_hook=unique)
  if set(header)!={'abi','mode','run_id','bytes','sha256'} or type(header['abi'])is not int or header['abi']!=1 or header['mode']!='receive' or header['run_id']!=run or type(header['bytes'])is not int or header['bytes']!=r['bytes'] or not re.fullmatch('[0-9a-f]{64}',header['sha256']):raise ValueError()
 if mode=='keys':
  out={}
  if len(r['paths'])>100:raise ValueError()
  for p in r['paths']:
   if p not in('/etc/kubernetes/encryption-config.json','/etc/kubernetes/longhorn-crypto-key',*('/etc/kubernetes/'+n+'.conf'for n in('admin','kubelet','controller-manager','scheduler')),*('/etc/kubernetes/manifests/'+n+'.yaml'for n in('etcd','kube-apiserver','kube-controller-manager','kube-scheduler')))and not p.startswith('/etc/kubernetes/pki/'):raise ValueError()
   if '..'in pathlib.Path(p).parts or pathlib.Path(p).resolve()!=pathlib.Path(p):raise ValueError()
   f=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);fds.append(f);i=os.fstat(f)
   if not stat.S_ISREG(i.st_mode)or i.st_uid!=0 or i.st_mode&0o022 or not 0<i.st_size<=1048576:raise ValueError()
   b=os.read(f,1048577);j=os.fstat(f);n=os.stat(p,follow_symlinks=False)
   if len(b)!=i.st_size or(i.st_dev,i.st_ino,i.st_size,i.st_mtime_ns,i.st_ctime_ns)!=(j.st_dev,j.st_ino,j.st_size,j.st_mtime_ns,j.st_ctime_ns)or(i.st_dev,i.st_ino)!=(n.st_dev,n.st_ino):raise ValueError()
   out[p]=base64.b64encode(b).decode()
  print(json.dumps(out));raise SystemExit(0)
 root=pathlib.Path('/dev/shm')if mode in('receive','proof','unlink')else pathlib.Path('/var/lib/etcd');parent=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);fds.append(parent);directory='migration-etcd-'+run
 if mode in('directory','receive'):os.mkdir(directory,0o700,dir_fd=parent);os.fsync(parent)
 d=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent);fds.append(d);di=os.fstat(d)
 if di.st_uid!=0 or stat.S_IMODE(di.st_mode)!=0o700:raise ValueError()
 if mode=='directory':print(json.dumps({'created':True}));raise SystemExit(0)
 f=os.open('snapshot.db',(os.O_RDWR|os.O_CREAT|os.O_EXCL if mode=='receive'else os.O_RDONLY)|os.O_NOFOLLOW|os.O_NONBLOCK,0o600,dir_fd=d);fds.append(f);i=os.fstat(f)
 if not stat.S_ISREG(i.st_mode)or i.st_uid!=0 or i.st_nlink!=1 or stat.S_IMODE(i.st_mode)!=0o600:raise ValueError()
 if mode=='receive':
  n=r['bytes'];end=time.monotonic()+r['seconds']
  if type(n)is not int or not 0<n<=536870912:raise ValueError()
  while n:
   if time.monotonic()>=end:raise ValueError()
   b=body.read(min(65536,n))
   if not b:raise ValueError()
   v=memoryview(b)
   while v:v=v[os.write(f,v):]
   n-=len(b)
  if body.read(1):raise ValueError()
  os.fsync(f);os.fsync(d);i=os.fstat(f)
 elif mode in('read','proof','unlink')and r['inode']!=[i.st_dev,i.st_ino,i.st_size,i.st_mtime_ns,i.st_ctime_ns]:raise ValueError()
 if not 0<i.st_size<=536870912:raise ValueError()
 h=hashlib.sha256();os.lseek(f,0,0)
 while True:
  b=os.read(f,65536)
  if not b:break
  h.update(b)
  if mode=='read':sys.stdout.buffer.write(b)
 j=os.fstat(f);n=os.stat('snapshot.db',dir_fd=d,follow_symlinks=False)
 if(i.st_dev,i.st_ino,i.st_size,i.st_mtime_ns,i.st_ctime_ns)!=(j.st_dev,j.st_ino,j.st_size,j.st_mtime_ns,j.st_ctime_ns)or(i.st_dev,i.st_ino)!=(n.st_dev,n.st_ino):raise ValueError()
 if mode=='unlink':os.unlink('snapshot.db',dir_fd=d);os.fsync(d)
 if mode=='receive' and h.hexdigest()!=header['sha256']:raise ValueError()
 if mode!='read':print(json.dumps({'inode':[i.st_dev,i.st_ino,i.st_size,i.st_mtime_ns,i.st_ctime_ns],'bytes':i.st_size,'digest':h.hexdigest()}))
except Exception:raise SystemExit(1)
finally:
 for f in reversed(fds):os.close(f)
"""

# Separate authentication and body channels, including NOPASSWD sudo. The wrapper
# consumes exactly one private line; root never uses sudo stdin for snapshot data.
PRIVILEGED_WRAPPER=r"""
import os,sys,json,time,select,subprocess,signal
request=json.loads(sys.argv[1]);program=sys.argv[2];child=None;read_fd=write_fd=None;password=None
def stopped(*unused):raise InterruptedError()
signal.signal(signal.SIGTERM,stopped);signal.signal(signal.SIGHUP,stopped)
try:
 password=bytearray()
 while len(password)<=256:
  b=os.read(0,1)
  if not b:raise ValueError()
  password.extend(b)
  if b==b'\n':break
 if not password.endswith(b'\n') or len(password)>257 or any(c in password[:-1]for c in(0,10,13)):raise ValueError()
 read_fd,write_fd=os.pipe();info=os.fstat(read_fd);ticks=int(open('/proc/self/stat').read().rsplit(')',1)[1].split()[19]);request['body_pipe']={'pid':os.getpid(),'fd':read_fd,'uid':os.getuid(),'start_ticks':ticks,'pipe_dev':info.st_dev,'pipe_ino':info.st_ino}
 end=time.monotonic()+request['seconds']
 child=subprocess.Popen(['sudo','-S','-k','-p','','python3','-c',program,json.dumps(request,separators=(',',':'))],stdin=subprocess.PIPE,stdout=sys.stdout,stderr=subprocess.DEVNULL,start_new_session=True)
 child.stdin.write(password);child.stdin.close();password=None
 os.set_blocking(0,False);os.set_blocking(write_fd,False);pending=b'';eof=False;total=0
 while child.poll()is None:
  remaining=end-time.monotonic()
  if remaining<=0:raise TimeoutError()
  readers=[0]if not eof and not pending else[];writers=[write_fd]if pending else[]
  r,w,_=select.select(readers,writers,[],min(.05,remaining))
  if r:
   block=os.read(0,65536);total+=len(block)
   if total>536872000:raise ValueError()
   if block:pending=block
   else:eof=True;os.close(write_fd);write_fd=None
  if w:
   n=os.write(write_fd,pending);pending=pending[n:]
 if child.returncode:raise ValueError()
 raise SystemExit(0)
except Exception:raise SystemExit(1)
finally:
 password=None
 for fd in(write_fd,read_fd):
  if fd is not None:
   try:os.close(fd)
   except OSError:pass
 if child:
  if child.poll()is None:
   try:os.killpg(child.pid,signal.SIGTERM)
   except OSError:pass
   try:child.wait(timeout=.02)
   except subprocess.TimeoutExpired:
    try:os.killpg(child.pid,signal.SIGKILL)
    except OSError:pass
    child.wait(timeout=.05)
  if child.stdin and not child.stdin.closed:child.stdin.close()
"""

class ToolPin:
    """Bind approved public executables; inherited FD prevents path replacement at exec."""
    def __init__(self,path,expected_sha,system=False):
        self.path=pathlib.Path(path);self.fds=[];self.anchors=[]
        try:
            need(self.path.is_absolute()and self.path.resolve()==self.path,'ownership')
            fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC);self.fds.append(fd);place=pathlib.Path('/')
            for part in self.path.parts[1:-1]:
                fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd);self.fds.append(fd);place/=part;i=os.fstat(fd)
                need(i.st_uid in(0,os.getuid())and not i.st_mode&0o022,'ownership');self.anchors.append((place,fd,(i.st_dev,i.st_ino,i.st_uid,i.st_mode)))
            self.fd=os.open(self.path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=fd);self.fds.append(self.fd);i=os.fstat(self.fd)
            need(stat.S_ISREG(i.st_mode)and i.st_uid in((0,os.getuid())if system else(os.getuid(),))and not i.st_mode&0o022 and i.st_mode&0o111 and i.st_nlink==1 and 0<i.st_size<=128*1024*1024,'ownership')
            self.identity=fp(i);h=hashlib.sha256()
            for b in iter(lambda:os.read(self.fd,65536),b''):h.update(b)
            self.sha256=h.hexdigest();need(expected_sha is None or self.sha256==expected_sha,'ownership');self.check()
        except Exception:self.close();raise
    def check(self):
        need(all((p.lstat().st_dev,p.lstat().st_ino,p.lstat().st_uid,p.lstat().st_mode)==i==(os.fstat(f).st_dev,os.fstat(f).st_ino,os.fstat(f).st_uid,os.fstat(f).st_mode)for p,f,i in self.anchors)and fp(os.fstat(self.fd))==self.identity==fp(self.path.lstat()),'ownership')
    def close(self):
        failed=False
        for fd in reversed(self.fds):
            try:os.close(fd)
            except Exception:failed=True
        self.fds=[];need(not failed,'cleanup')

class OwnedChildren(q.Children):
    """Permit fixed wrapper finally on cancellation, within one total reap margin."""
    def __call__(self,child):
        if child is None or child.poll()is not None:return
        need(type(child)is subprocess.Popen,'cleanup');now=time.monotonic()
        if now>=self.deadline and self.grace_until is None:self.grace_until=now+.250
        until=self.deadline if now<self.deadline else self.grace_until
        def send(sig):
            try:
                if os.getpgid(child.pid)==child.pid:os.killpg(child.pid,sig)
                else:os.kill(child.pid,sig)
            except ProcessLookupError:pass
        send(signal.SIGTERM)
        try:child.wait(timeout=max(0,min(.08,until-time.monotonic())));return
        except subprocess.TimeoutExpired:pass
        send(signal.SIGKILL);child.wait(timeout=max(0,until-time.monotonic()))

class Transport:
    def __init__(self,deadline,password_provider,tools):
        self.deadline,self.password_provider=deadline,password_provider;self.children=OwnedChildren(deadline);self.jobs=[];self.tool_pins={};self.ssh_pin=None;self.closed=False
        try:
            need(set(tools)in({'age','kubectl'},{'age','kubectl','ssh'}),'input');self.ssh_pin=q.Pin(SSH_IDENTITY,65536)
            for name in('age','kubectl'):self.tool_pins[name]=ToolPin(RUNTIME/'bin'/name,tools[name])
            self.tool_pins['ssh']=ToolPin(SSH_BINARY,tools.get('ssh'),system=True)
        except Exception:self.close();raise
    def check(self):
        need(not self.closed,'cleanup');left(self.deadline);self.ssh_pin.check()
        for pin in self.tool_pins.values():pin.check()
    def spawn(self,args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,pass_fds=()):
        self.check();name=next((n for n,pin in self.tool_pins.items()if str(pin.path)==args[0]),None);need(name is not None,'input')
        if name=='ssh':need(args[:len(SSH)]==SSH,'input')
        pin=self.tool_pins[name];fd_args=['/proc/self/fd/'+str(pin.fd),*args[1:]];inherited=tuple(set(pass_fds+(pin.fd,)))
        p=subprocess.Popen(fd_args,stdin=stdin,stdout=stdout,stderr=subprocess.DEVNULL,start_new_session=True,pass_fds=inherited,env={'HOME':str(pathlib.Path.home()),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        job={'pid':p.pid,'start_ticks':None,'process':p};self.jobs.append(job)
        try:job['start_ticks']=pathlib.Path('/proc/'+str(p.pid)+'/stat').read_text().split()[21]
        except Exception:self.children(p);raise Refused('child')from None
        return p
    def _kube(self,args,body=b'',maximum=65536,stream=False):
        fds=None
        try:
            fd,fds,anchors,i=q.reader.pin_config(RUNTIME/'admin.conf');context,headers=q.credentials.OperatorMTLSOptions(str(RUNTIME/'admin.conf'))();context=headers=None;q.reader.check_pinned(RUNTIME/'admin.conf',fd,i,anchors)
            child=self.spawn([str(RUNTIME/'bin/kubectl'),'--kubeconfig','/proc/self/fd/'+str(fd),'--request-timeout='+format(left(self.deadline),'.6f')+'s',*args],pass_fds=(fd,))
            if stream:child.stdin.close();return child
            result=collect(child,self.deadline,self.children,body,maximum);q.reader.check_pinned(RUNTIME/'admin.conf',fd,i,anchors);self.check();return result
        finally:
            if fds:q.reader.close_descriptors(fds)
    def kube(self,args,body=b'',maximum=65536,stream=False):
        result=failure=None
        try:result=self._kube(args,body,maximum,stream)
        except Refused as e:failure=e.code
        except Exception:failure='child'
        if failure:self=args=body=result=None;raise Refused(failure)
        return result
    def api(self,args,body=None,maximum=8*1024*1024):
        raw=result=failure=None
        try:
            raw=self.kube(args,b''if body is None else json.dumps(body,separators=(',',':')).encode(),maximum);result=decode(raw)if raw else None
        except Refused as e:failure=e.code
        except Exception:failure='child'
        if failure:self=args=body=raw=result=None;raise Refused(failure)
        return result
    def _remote_start(self,r):
        self.check();need(type(r)is dict and r.get('mode')in('keys','directory','metadata','read','receive','proof','unlink')and re.fullmatch('[0-9a-f]{12}',r.get('run_id','')),'input')
        fields={'mode','run_id'}|({'paths'}if r['mode']=='keys'else{'inode'}if r['mode']in('read','proof','unlink')else{'bytes','seconds'}if r['mode']=='receive'else set());need(set(r)==fields,'input')
        if 'paths'in r:need(type(r['paths'])is list and len(r['paths'])<=100 and len(set(r['paths']))==len(r['paths'])and all(type(p)is str and(p in CONFIG_PATHS or re.fullmatch('/etc/kubernetes/pki/[A-Za-z0-9_./-]{1,240}',p))and'..'not in pathlib.PurePosixPath(p).parts for p in r['paths']),'input')
        if 'inode'in r:need(type(r['inode'])is list and len(r['inode'])==5 and all(type(v)is int and v>=0 for v in r['inode'])and 0<r['inode'][2]<=MAX,'input')
        if 'bytes'in r:need(type(r['bytes'])is int and 0<r['bytes']<=MAX and type(r['seconds'])in(int,float)and math.isfinite(r['seconds'])and 0<r['seconds']<=2100,'input')
        password=p=pipe=None
        try:
            password=self.password_provider();need(type(password)is str and 0<len(password.encode())<=256 and not any(c in password for c in '\r\n\0'),'input');r=dict(r,seconds=min(r.get('seconds',2100),left(self.deadline)))
            p=self.spawn([*SSH,shlex.join(['python3','-c',PRIVILEGED_WRAPPER,json.dumps(r,separators=(',',':')),REMOTE])]);pipe=q.archive.Pipe(p.stdin,self.deadline,False);pipe.write(password.encode()+b'\n');self.check();return p
        except Exception:
            if p:self.children(p)
            raise
        finally:
            if pipe:pipe.close()
            password=None
    def remote_start(self,r):
        result=failure=None
        try:result=self._remote_start(r)
        except Refused as e:failure=e.code
        except Exception:failure='child'
        if failure:self=r=result=None;raise Refused(failure)
        return result
    def remote(self,r):
        raw=result=failure=None
        try:
            raw=collect(self.remote_start(r),self.deadline,self.children,maximum=8*1024*1024);result=decode(raw);self.check()
        except Refused as e:failure=e.code
        except Exception:failure='child'
        if failure:self=r=raw=result=None;raise Refused(failure)
        return result
    def close(self):
        if self.closed:return
        self.closed=True
        failure=False
        for job in self.jobs:
            if 'process'not in job:continue
            p=job['process']
            try:self.children(p)
            except Exception:failure=True
            for f in(p.stdin,p.stdout,p.stderr):
                if f and not f.closed:
                    try:f.close()
                    except Exception:failure=True
            job.update(actual_exit_code=p.poll(),reaped=p.poll()is not None);job.pop('process')
        for pin in reversed(list(self.tool_pins.values())+([self.ssh_pin]if self.ssh_pin else[])):
            try:pin.close()
            except Exception:failure=True
        self.password_provider=None;self.tool_pins={};self.ssh_pin=None
        need(not failure,'cleanup')

def keys(document):
    need(type(document)is dict and type(document.get('files'))is dict and REQUIRED<=set(document['files']),'keys')
    paths=sorted(p for p in document['files']if p in REQUIRED or p.startswith('/etc/kubernetes/pki/'));need(len(paths)<=100,'keys')
    result={p:base64.b64decode(document['files'][p],validate=True)for p in paths};need(all(0<len(v)<=1048576 for v in result.values()),'keys')
    config=decode(result['/etc/kubernetes/encryption-config.json']);need(config.get('kind')=='EncryptionConfiguration','keys');names=[]
    for r in config['resources']:
        if 'secrets'in r['resources']:
            for provider in r['providers']:
                for k in provider.get('aescbc',{}).get('keys',[]):need(re.fullmatch('[A-Za-z0-9_-]{1,128}',k['name'])and len(base64.b64decode(k['secret'],validate=True))==32,'keys');names.append(k['name'])
    need(names and len(set(names))==len(names),'keys');return result,names

def registry(obj,revision):
    need(type(obj)is dict and type(obj.get('kvs'))is list and len(obj['kvs'])<=MAX_KEYS and obj.get('more',False)is False and type(obj.get('count'))in(int,str)and str(obj.get('count'))==str(len(obj['kvs']))and type(obj.get('header'))is dict and type(obj['header'].get('revision'))in(int,str)and str(obj['header']['revision']).isdigit()and int(obj['header']['revision'])>=revision,'registry');out={}
    for r in obj['kvs']:
        k=base64.b64decode(r['key'],validate=True);v=base64.b64decode(r['value'],validate=True);need(k.startswith(b'/registry/secrets/')and k not in out and len(k)<=1024 and 0<len(v)<=2*1024*1024,'registry');out[k]=v
    return out

def snapshot_status(status,pin):
    need(type(status)is dict and set(status)=={'hash','revision','totalKey','totalSize','version'}and all(type(status[k])is int for k in('hash','revision','totalKey','totalSize'))and
        0<=status['hash']<=0xffffffff and status['revision']>0 and status['totalKey']>0 and 0<status['totalSize']<MAX and status['version']=='3.7.0','snapshot')
    # v3.7.0 Status.TotalSize is bbolt tx.Size(); Save appends SHA256 (32 bytes).
    need(type(pin)is dict and set(pin)=={'inode','bytes','digest'}and type(pin['bytes'])is int and pin['bytes']==status['totalSize']+32 and pin['bytes']%512==32 and
        type(pin['inode'])is list and len(pin['inode'])==5 and all(type(v)is int and v>=0 for v in pin['inode'])and pin['inode'][2]==pin['bytes']and
        type(pin['digest'])is str and re.fullmatch('[0-9a-f]{64}',pin['digest']),'snapshot')
    return status['revision']

def nas_writer():
    """Use the closed cipher-only factory with this graph's exact base program."""
    path=pathlib.Path(__file__).with_name('capture-kubernetes-recovery-config.py');before=sha(path.read_bytes());factory=load('etcd_cipher_nas_factory',path.name)
    program=factory.nas_program(types.SimpleNamespace(q=q),prefix='etcd');need(sha(path.read_bytes())==before,'ownership')
    return program,{'prefix':'etcd','writer_sha256':sha(program.encode()),'factory_source_sha256':before,'base_program_sha256':sha(q.NAS_PROGRAM.encode())}

def read_age(client,cipher,identity,deadline,maximum):
    cipher.check();os.lseek(cipher.fd,0,0)
    with os.fdopen(os.dup(cipher.fd),'rb')as source:
        child=client.spawn([str(RUNTIME/'bin/age'),'-d','-i',identity],stdin=source)
        raw=collect(child,deadline,client.children,maximum=maximum)
    cipher.check();return raw

def raw_archive(client,source,target,recipient,identity,deadline,directory_fd):
    fd=encryptor=None;failure=None;result=None;plain=None;h=hashlib.sha256();count=0
    try:
        fd=os.open(target.name,os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_NOFOLLOW,0o600,dir_fd=directory_fd)
        with os.fdopen(fd,'w+b',closefd=False)as out:
            encryptor=client.spawn([str(RUNTIME/'bin/age'),'-R',recipient],stdout=out);r=q.archive.Pipe(source.stdout,deadline,True);w=q.archive.Pipe(encryptor.stdin,deadline,False)
            try:
                while True:
                    b=r.read(65536)
                    if not b:break
                    count+=len(b);need(count<=MAX,'snapshot');h.update(b);w.write(b)
                encryptor.stdin.close()
            finally:r.close();w.close()
            need(count>0 and source.wait(timeout=left(deadline))==0 and encryptor.wait(timeout=left(deadline))==0,'archive');out.flush();os.fsync(fd);os.fsync(directory_fd)
        cipher=q.Pin(target,MAX+1048576)
        try:
            # Authenticate exact pinned ciphertext, bounded raw format (no SQLite framing).
            cipher.check();os.lseek(cipher.fd,0,0)
            with os.fdopen(os.dup(cipher.fd),'rb')as encrypted:
                decryptor=client.spawn([str(RUNTIME/'bin/age'),'-d','-i',identity],stdin=encrypted);r=q.archive.Pipe(decryptor.stdout,deadline,True);recovered=hashlib.sha256();n=0
                try:
                    while True:
                        b=r.read(65536)
                        if not b:break
                        n+=len(b);need(n<=count,'archive');recovered.update(b)
                finally:r.close()
                need(decryptor.wait(timeout=left(deadline))==0 and n==count and recovered.digest()==h.digest(),'archive')
            cipher.check();os.lseek(cipher.fd,0,0);digest=hashlib.sha256()
            for b in iter(lambda:os.read(cipher.fd,65536),b''):left(deadline);digest.update(b)
            cipher.check();need(fp(os.fstat(fd))==fp(os.fstat(cipher.fd))==fp(target.lstat()),'ownership');result={'snapshot_bytes':count,'cipher_bytes':os.fstat(cipher.fd).st_size,'ciphertext_sha256':digest.hexdigest(),'authenticated_decryption_equal':True};plain=h.digest()
        finally:cipher.close()
    except Exception:failure='archive'
    finally:
        for p in(source,encryptor):
            try:client.children(p)
            except Exception:failure='cleanup'
            if p:
                for f in(p.stdin,p.stdout,p.stderr):
                    if f and not f.closed:f.close()
        if fd is not None:os.close(fd)
    b=r=w=source=encryptor=None
    if failure:result=plain=None;raise Refused(failure)
    return result,plain

def absent(client,kind,name,uid):
    need(kind in('pod','networkpolicy'),'input')
    need(client.api(['get',kind,name,'-n',NS,'--ignore-not-found','-o','json'])is None,'resource')
    path='/api/v1/namespaces/migration-system/pods'if kind=='pod'else'/apis/networking.k8s.io/v1/namespaces/migration-system/networkpolicies'
    obj=client.api(['get','--raw',path]);need(obj['apiVersion']==('v1'if kind=='pod'else'networking.k8s.io/v1')and obj['kind']==('PodList'if kind=='pod'else'NetworkPolicyList')and type(obj['items'])is list and len(obj['items'])<=10000 and type(obj['metadata'].get('resourceVersion'))is str and obj['metadata']['resourceVersion']and type(obj['metadata'].get('continue',''))is str and obj['metadata'].get('continue','')==''and type(obj['metadata'].get('remainingItemCount',0))is int and obj['metadata'].get('remainingItemCount',0)==0,'resource');seen=set();uids=set()
    for item in obj['items']:
        i=identity(item);need(i['namespace']==NS and i['name']not in seen and i['uid']not in uids and i['name']!=name and i['uid']!=uid,'resource');seen.add(i['name']);uids.add(i['uid'])
def cleanup(client,ledger,kind,created,deadline):
    i=identity(created);obj=client.api(['get',kind,i['name'],'-n',NS,'-o','json']);j=identity(obj)
    need(all(i[k]==j[k]for k in('name','namespace','uid'))and obj['metadata'].get('labels',{}).get('migration.etcd-run')==ledger.r['run_id'],'resource');resource_matches(created,obj);action=kind+'-delete'
    ledger.intent(action,{'identity':j});body={'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':j['uid'],'resourceVersion':j['resourceVersion']}}
    path=('/api/v1/namespaces/'+NS+'/pods/'if kind=='pod'else'/apis/networking.k8s.io/v1/namespaces/'+NS+'/networkpolicies/')+i['name'];client.api(['delete','--raw',path,'-f','-'],body)
    while client.api(['get',kind,i['name'],'-n',NS,'--ignore-not-found','-o','json'])is not None:time.sleep(min(.1,left(deadline)))
    absent(client,kind,i['name'],i['uid']);ledger.confirm(action,{'absence_confirmed':True})
def proposals(run_id,image):
    name='etcd-recovery-'+run_id;labels={'migration.etcd-run':run_id}
    policy={'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':{'name':name,'namespace':NS,'labels':labels},'spec':{'podSelector':{'matchLabels':labels},'policyTypes':['Ingress','Egress']}}
    pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':NS,'labels':labels},'spec':{'automountServiceAccountToken':False,'restartPolicy':'Never','nodeName':'masternode','securityContext':{'runAsUser':0,'runAsGroup':0},'containers':[{'name':'etcd','image':image,'imagePullPolicy':'Never','command':['etcd','--name=empty','--data-dir=/proof/empty','--listen-client-urls=http://127.0.0.1:12379','--advertise-client-urls=http://127.0.0.1:12379','--listen-peer-urls=http://127.0.0.1:12380','--initial-advertise-peer-urls=http://127.0.0.1:12380','--initial-cluster=empty=http://127.0.0.1:12380'],'volumeMounts':[{'name':'proof','mountPath':'/proof'},{'name':'snapshot','mountPath':'/snapshot','readOnly':True}],'resources':{'requests':{'cpu':'100m','memory':'128Mi'},'limits':{'cpu':'1','memory':'2Gi'}}}],'volumes':[{'name':'proof','emptyDir':{'medium':'Memory','sizeLimit':'1536Mi'}},{'name':'snapshot','hostPath':{'path':'/dev/shm/migration-etcd-'+run_id+'/snapshot.db','type':'File'}}]}}
    return policy,pod

def resource_matches(proposal,obj,ready=False):
    """Exact requested isolation spec; only literal known absent defaults normalize."""
    need(type(obj)is dict and obj.get('apiVersion')==proposal['apiVersion']and obj.get('kind')==proposal['kind'],'resource')
    i=identity(obj);need(i['name']==proposal['metadata']['name']and i['namespace']==NS and obj['metadata'].get('labels')==proposal['metadata']['labels']and not obj['metadata'].get('ownerReferences'),'resource')
    actual=copy.deepcopy(obj.get('spec'));expected=proposal['spec'];need(type(actual)is dict,'resource')
    if proposal['kind']=='Pod':
        defaults={'dnsPolicy':'ClusterFirst','schedulerName':'default-scheduler','terminationGracePeriodSeconds':30,'enableServiceLinks':True,'preemptionPolicy':'PreemptLowerPriority','priority':0,'serviceAccountName':'default','serviceAccount':'default','hostNetwork':False,'hostPID':False,'hostIPC':False}
        for k,v in defaults.items():
            if k not in expected and k in actual:
                need(type(actual[k])is type(v)and actual[k]==v,'resource');actual.pop(k)
        tolerations=[{'key':'node.kubernetes.io/not-ready','operator':'Exists','effect':'NoExecute','tolerationSeconds':300},{'key':'node.kubernetes.io/unreachable','operator':'Exists','effect':'NoExecute','tolerationSeconds':300}]
        if 'tolerations'not in expected and 'tolerations'in actual:need(actual.pop('tolerations')==tolerations,'resource')
        need(type(actual.get('containers'))is list and len(actual['containers'])==1,'resource')
        container=actual['containers'][0]
        for k,v in {'terminationMessagePath':'/dev/termination-log','terminationMessagePolicy':'File'}.items():
            if k not in expected['containers'][0]and k in container:need(container.pop(k)==v,'resource')
        if ready:
            states=obj.get('status',{}).get('containerStatuses');need(type(states)is list and len(states)==1 and states[0]['name']=='etcd'and states[0]['ready']is True and set(states[0]['state'])=={'running'}and states[0]['imageID']==expected['containers'][0]['image'],'resource')
    need(actual==expected,'resource');return i

def finalize(ledger,deadline,failure,jobs):
    """Closed resources first; preserve incomplete confirmation if expiry/flush fails."""
    for entry in ledger.r['operations'].values():
        if entry['state']=='pending':entry['state']='uncertain'
    try:
        if not failure:left(deadline)
        ledger.r.update(phase='refused'if failure else'finalizing',failure=failure,actual_exit_code=1 if failure else None,owned_children=jobs)
        ledger.save()
        if not failure:left(deadline)
        ledger.r.update(phase='refused'if failure else'completed',actual_exit_code=1 if failure else 0,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        ledger.save()
        if not failure:left(deadline)
        return copy.deepcopy(ledger.r)
    except Exception as error:
        code=error.code if isinstance(error,Refused)else'durability'
        ledger.r.update(phase='refused',failure=code,actual_exit_code=1)
        try:ledger.save()
        except Exception:pass
    ledger=jobs=None
    raise Refused(code)

def _checkpoint(*,deadline,expected_source,config_bundle,recipient,identity_file,tools,password_provider,parent,run_id,client=None):
    left(deadline);need(set(expected_source)=={'uid','image','image_id','restore_image'}and all(type(v)is str and 0<len(v)<=512 for v in expected_source.values())and re.fullmatch(r'[^@\s]+@sha256:[0-9a-f]{64}',expected_source['restore_image']),'input');need(set(config_bundle)=={'path','sha256'}and re.fullmatch('[0-9a-f]{64}',config_bundle['sha256']),'input')
    ledger=Ledger(parent,run_id);c=client;pins=[];created=[];proof=None;failure=result=None
    try:
        c=c or Transport(deadline,password_provider,tools)
        def source():
            left(deadline);obj=c.api(['get','pod','etcd-masternode','-n','kube-system','-o','json']);i=identity(obj);containers=[v for v in obj['spec']['containers']if v['name']=='etcd'];statuses=[v for v in obj['status']['containerStatuses']if v['name']=='etcd']
            need(i['uid']==expected_source['uid']and obj['spec']['nodeName']=='masternode'and len(containers)==len(statuses)==1 and containers[0]['image']==expected_source['image']and statuses[0]['imageID']==expected_source['image_id']and statuses[0]['ready']is True,'snapshot');return i
        original=source();ledger.r.update(source=original,configuration_cipher_sha256=config_bundle['sha256'],restore_image=expected_source['restore_image']);ledger.save()
        for p in(recipient,identity_file,config_bundle['path']):pins.append(q.Pin(p,32*1024*1024))
        need(sha(os.pread(pins[2].fd,32*1024*1024,0))==config_bundle['sha256'],'keys');files,names=keys(decode(read_age(c,pins[2],pins[1].child_path,deadline,32*1024*1024)))
        def correspondence():
            got=c.remote({'mode':'keys','run_id':run_id,'paths':sorted(files)});need(set(got)==set(files)and all(base64.b64decode(got[k],validate=True)==v for k,v in files.items()),'keys')
            secret=c.api(['get','secret','longhorn-crypto','-n','longhorn-system','-o','json']);i=identity(secret);need(base64.b64decode(secret['data']['CRYPTO_KEY_VALUE'],validate=True)==files['/etc/kubernetes/longhorn-crypto-key'],'keys');return i
        key_identity=correspondence();prefix=['exec','-n','kube-system','etcd-masternode','-c','etcd','--'];base=prefix+['etcdctl','--endpoints=https://127.0.0.1:2379','--cacert=/etc/kubernetes/pki/etcd/ca.crt','--cert=/etc/kubernetes/pki/etcd/healthcheck-client.crt','--key=/etc/kubernetes/pki/etcd/healthcheck-client.key'];snapshot='/var/lib/etcd/migration-etcd-'+run_id+'/snapshot.db'
        ledger.intent('snapshot',{'source':original,'path':snapshot});need(c.remote({'mode':'directory','run_id':run_id})=={'created':True},'snapshot');c.kube(base+['snapshot','save',snapshot]);status=decode(c.kube(prefix+['etcdutl','snapshot','status',snapshot,'--write-out=json']));pin=c.remote({'mode':'metadata','run_id':run_id});revision=snapshot_status(status,pin);ledger.confirm('snapshot',{'revision':revision,'bytes':pin['bytes'],'inode':pin['inode']})
        expected=registry(decode(c.kube(base+['get','/registry/secrets/','--prefix','--rev='+str(revision),'--write-out=json'],maximum=MAX_REGISTRY)),revision)
        need(all(any(v.startswith(('k8s:enc:aescbc:v1:'+n+':').encode())for n in names)for v in expected.values()),'keys')
        for key in(b'/registry/secrets/longhorn-system/longhorn-crypto',b'/registry/secrets/bortus/bortus-runtime'):need(key in expected and any(expected[key].startswith(('k8s:enc:aescbc:v1:'+n+':').encode())for n in names),'keys')
        source();need(correspondence()==key_identity,'keys');ledger.intent('archive',{'snapshot_revision':revision});stream=c.remote_start({'mode':'read','run_id':run_id,'inode':pin['inode']});stream.stdin.close();archive,plain=raw_archive(c,stream,ledger.path/'snapshot.age',pins[0].child_path,pins[1].child_path,deadline,ledger.fd);need(plain.hex()==pin['digest'],'snapshot');ledger.confirm('archive',archive)
        cipher=q.Pin(ledger.path/'snapshot.age',MAX+1048576);pins.append(cipher);cipher.check();os.lseek(cipher.fd,0,0);name='etcd-'+run_id+'.age';program,writer_binding=nas_writer();ledger.intent('nas',{'name':name,'ciphertext_sha256':archive['ciphertext_sha256'],'writer_binding':writer_binding});nas=c.spawn([*SSH,shlex.join(['python3','-c',program])]);w=q.archive.Pipe(nas.stdin,deadline,False)
        try:
            w.write(json.dumps({'name':name,'bytes':archive['cipher_bytes'],'sha256':archive['ciphertext_sha256'],'seconds':left(deadline)}).encode()+b'\n')
            for b in iter(lambda:os.read(cipher.fd,65536),b''):w.write(b)
            nas.stdin.close()
        finally:w.close()
        reply=decode(collect(nas,deadline,c.children,maximum=1024));need(type(reply)is dict and set(reply)=={'bytes','sha256','fsynced','same_inode_readback','cipher_mode','cifs_mount'}and type(reply['bytes'])is int and reply['bytes']==archive['cipher_bytes']and reply['sha256']==archive['ciphertext_sha256']and reply['fsynced']is True and reply['same_inode_readback']is True and type(reply['cipher_mode'])is int and type(reply['cifs_mount'])is bool and(reply['cipher_mode']==0o600 or reply['cipher_mode']==0o755 and reply['cifs_mount']is True),'nas');cipher.check();left(deadline);ledger.confirm('nas',reply)
        ledger.intent('proof-bytes',{'snapshot_revision':revision});os.lseek(cipher.fd,0,0)
        with os.fdopen(os.dup(cipher.fd),'rb')as encrypted:
            decrypted=c.spawn([str(RUNTIME/'bin/age'),'-d','-i',pins[1].child_path],stdin=encrypted);receive=c.remote_start({'mode':'receive','run_id':run_id,'bytes':archive['snapshot_bytes'],'seconds':left(deadline)});r=q.archive.Pipe(decrypted.stdout,deadline,True);w=q.archive.Pipe(receive.stdin,deadline,False);count=0
            try:
                w.write(json.dumps({'abi':1,'mode':'receive','run_id':run_id,'bytes':archive['snapshot_bytes'],'sha256':plain.hex()},separators=(',',':')).encode()+b'\n')
                while True:
                    b=r.read(65536)
                    if not b:break
                    count+=len(b);need(count<=archive['snapshot_bytes'],'archive');w.write(b)
                receive.stdin.close()
            finally:r.close();w.close()
            need(decrypted.wait(timeout=left(deadline))==0 and count==archive['snapshot_bytes'],'archive');proof=decode(collect(receive,deadline,c.children,maximum=1024));need(proof['digest']==plain.hex(),'archive');cipher.check();ledger.confirm('proof-bytes',{'inode':proof['inode'],'bytes':proof['bytes']})
        policy,pod=proposals(run_id,expected_source['restore_image'])
        for kind,proposal in(('networkpolicy',policy),('pod',pod)):
            name=proposal['metadata']['name'];absent(c,kind,name,'not-owned');ledger.intent(kind+'-create',{'name':name,'proposal_sha256':sha(json.dumps(proposal,sort_keys=True,separators=(',',':')).encode())});obj=c.api(['create','-f','-','-o','json'],proposal);i=resource_matches(proposal,obj);created.append((kind,obj));ledger.confirm(kind+'-create',i)
        name=pod['metadata']['name'];c.kube(['wait','pod/'+name,'-n',NS,'--for=condition=Ready','--timeout='+format(left(deadline),'.6f')+'s']);fresh=c.api(['get','pod',name,'-n',NS,'-o','json']);need(resource_matches(pod,fresh,ready=True)['uid']==identity(created[-1][1])['uid'],'resource');prefix=['exec','-n',NS,name,'-c','etcd','--']
        need(decode(c.kube(prefix+['etcdutl','snapshot','status','/snapshot','--write-out=json']))==status,'snapshot');c.kube(prefix+['etcdutl','snapshot','restore','/snapshot','--data-dir=/proof/restored','--name=proof','--initial-cluster=proof=http://127.0.0.1:32380','--initial-advertise-peer-urls=http://127.0.0.1:32380']);server=c.kube(prefix+['etcd','--name=proof','--data-dir=/proof/restored','--listen-client-urls=http://127.0.0.1:32379','--advertise-client-urls=http://127.0.0.1:32379','--listen-peer-urls=http://127.0.0.1:32380','--initial-advertise-peer-urls=http://127.0.0.1:32380','--initial-cluster=proof=http://127.0.0.1:32380'],stream=True)
        actual=None
        while actual is None:
            left(deadline)
            try:actual=registry(decode(c.kube(prefix+['etcdctl','--endpoints=http://127.0.0.1:32379','--dial-timeout=1s','--command-timeout=2s','get','/registry/secrets/','--prefix','--write-out=json'],maximum=MAX_REGISTRY)),revision)
            except Refused as e:
                if e.code!='child':raise
                time.sleep(min(.1,left(deadline)))
        need(actual==expected,'registry');actual=expected=None;c.children(server);need(c.remote({'mode':'proof','run_id':run_id,'inode':proof['inode']})==proof,'snapshot');source();need(correspondence()==key_identity,'keys')
        for p in pins:p.check()
        ledger.r['phase']='verified';ledger.save()
    except Refused as e:failure=e.code
    except Exception:failure='operation'
    finally:
        if c:
            for kind,obj in reversed(created):
                try:
                    if kind=='networkpolicy'and ledger.r['operations'].get('pod-create',{}).get('state')=='pending':raise Refused('uncertain')
                    if kind=='networkpolicy'and ledger.r['operations'].get('pod-create',{}).get('state')=='confirmed':need(ledger.r['operations'].get('pod-delete',{}).get('state')=='confirmed','cleanup')
                    if kind=='networkpolicy'and 'pod-create'not in ledger.r['operations']:absent(c,'pod','etcd-recovery-'+run_id,'not-owned')
                    cleanup(c,ledger,kind,obj,deadline)
                except Exception:failure='cleanup'
            if proof and created and all(ledger.r['operations'].get(k+'-delete',{}).get('state')=='confirmed'for k,_ in created):
                try:ledger.intent('proof-unlink',{'inode':proof['inode']});c.remote({'mode':'unlink','run_id':run_id,'inode':proof['inode']});ledger.confirm('proof-unlink')
                except Exception:failure='cleanup'
            try:c.close()
            except Exception:failure='cleanup'
        for p in reversed(pins):
            try:p.close()
            except Exception:failure='cleanup'
        try:result=finalize(ledger,deadline,failure,[]if c is None else c.jobs)
        except Refused as e:failure=e.code;result=None
        except Exception:failure='durability';result=None
        try:ledger.close()
        except Exception:failure='cleanup';result=None
    c=client=ledger=pins=created=proof=files=original=source=correspondence=key_identity=expected=actual=plain=expected_source=config_bundle=recipient=identity_file=password_provider=None
    if failure:result=None;raise Refused(failure)
    return result

def checkpoint(*,deadline,expected_source,config_bundle,recipient,identity_file,tools,password_provider,parent,run_id,client=None):
    """Fixed public refusal drops private core/callback frames, including early failure."""
    result=failure=None
    try:result=_checkpoint(deadline=deadline,expected_source=expected_source,config_bundle=config_bundle,recipient=recipient,identity_file=identity_file,tools=tools,password_provider=password_provider,parent=parent,run_id=run_id,client=client)
    except Refused as e:failure=e.code
    except Exception:failure='operation'
    deadline=expected_source=config_bundle=recipient=identity_file=tools=password_provider=parent=run_id=client=None
    if failure:result=None;raise Refused(failure)
    return result

def main():
    request=result=None;failure=False
    try:
        raw=sys.stdin.buffer.read(65537);need(len(raw)<=65536);request=decode(raw);need(set(request)=={'deadline','source','configuration_archive','recipient_file','identity_file','tools','sudo_password','runtime_parent','run_id'})
        result=checkpoint(deadline=request['deadline'],expected_source=request['source'],config_bundle=request['configuration_archive'],recipient=request['recipient_file'],identity_file=request['identity_file'],tools=request['tools'],password_provider=lambda:request['sudo_password'],parent=request['runtime_parent'],run_id=request['run_id'])
    except Exception:failure=True
    request=raw=None
    if failure:print('Etcd checkpoint refused; inspect retained owned run without replay.',file=sys.stderr);return 1
    print(json.dumps({'run_id':result['run_id'],'phase':result['phase'],'actual_exit_code':result['actual_exit_code']}));return 0
if __name__=='__main__':raise SystemExit(main())
