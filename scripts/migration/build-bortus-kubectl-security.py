#!/usr/bin/env python3
"""Once-only isolated custom kubectl security build; no image or live API interface."""
import argparse
import datetime
import gzip
import hashlib
import json
import math
import os
import pathlib
import re
import signal
import stat
import subprocess
import tarfile
import time
import zipfile

SOURCE_SHA = 'd58492a058ac7cb1db0829a9e12317024f48d4bcbf56344b32b11276f9bdc2cf'
SOURCE_COMMIT = 'f78e722310e50bcaca9276be22276d9e91d91308'
SOURCE_TAG_OBJECT = 'd2b770f4c94636a992534a8d3156b6b2d8e82ac3'
GO_SHA = '42d158b4d8f7b61ac0a830567c940a86098fb7aac52e467a5ebec03ef5cc2f8d'
GO_VERSION = 'go1.26.9'
CUSTOM_VERSION = 'v1.37.1-bortus.security.1'
PINS = {'golang.org/x/net': 'v0.60.0', 'golang.org/x/crypto': 'v0.57.0',
        'golang.org/x/sys': 'v0.48.0', 'golang.org/x/term': 'v0.46.0',
        'golang.org/x/text': 'v0.42.0'}
MAX_ARCHIVE = 512 * 1024 * 1024
MAX_TREE = 2 * 1024 * 1024 * 1024
MAX_FILE = 128 * 1024 * 1024
MAX_MEMBERS = 100000
MAX_LOG = 128 * 1024 * 1024
MAX_DIFF_METADATA = 64 * 1024 * 1024
spawn = subprocess.Popen


class Refused(RuntimeError):
    def __init__(self, code):
        self.code = code; super().__init__('Custom kubectl build refused: ' + code)


def need(ok, code):
    if not ok: raise Refused(code)


def sha(raw): return hashlib.sha256(raw).hexdigest()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def ident(i): return (i.st_dev, i.st_ino, i.st_mode, i.st_uid, i.st_nlink, i.st_size, i.st_mtime_ns, i.st_ctime_ns)


def hash_file(path, maximum=MAX_FILE, single_link=True):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        i = os.fstat(fd)
        need(stat.S_ISREG(i.st_mode) and 0 <= i.st_size <= maximum and (not single_link or i.st_nlink == 1), 'file')
        h = hashlib.sha256(); count = 0
        while True:
            raw = os.read(fd, 65536)
            if not raw: break
            count += len(raw); need(count <= maximum, 'bound'); h.update(raw)
        need(count == i.st_size and ident(i) == ident(os.fstat(fd)) == ident(os.stat(path, follow_symlinks=False)), 'file_changed')
        return h.hexdigest(), count
    finally: os.close(fd)


def relative(name):
    need(type(name) is str and 0 < len(name.encode()) <= 4096 and '\\' not in name and
         ':' not in name and not name.startswith('/') and
         all(p not in ('', '.', '..') for p in name.split('/')) and
         not any(ord(c) < 32 or ord(c) == 127 for c in name), 'archive_path')
    return pathlib.PurePosixPath(name)


def extract(archive, destination, prefix, deadline=None, *, flat=False):
    """Validate all headers/links first; never traverse an archive-created link."""
    # Count decompressed bytes even while tar skips unselected member payloads.
    class Bounded:
        def __init__(self, stream): self.stream=stream;self.count=0
        def read(self, n=-1):
            need(n>=0,'archive_bound');raw=self.stream.read(n);self.count+=len(raw)
            need(self.count<=MAX_TREE+MAX_MEMBERS*1024+16*1024*1024,'archive_bound');return raw
    with gzip.open(archive,'rb')as compressed, tarfile.open(fileobj=Bounded(compressed),mode='r|')as tar:
        members = []; nodes = {}; total = 0
        for member in tar:
            need(deadline is None or time.monotonic()<deadline,'deadline')
            need(len(members) < MAX_MEMBERS, 'archive_bound')
            name = relative(member.name.rstrip('/')).as_posix()
            need(flat or name == prefix or name.startswith(prefix+'/'), 'archive_root')
            need(name not in nodes and member.mode & ~0o777 == 0 and
                 member.size <= MAX_FILE and member.size >= 0 and
                 (member.isdir() or member.isfile() or member.issym() or member.islnk()), 'archive_type')
            total += member.size; need(total <= MAX_TREE, 'archive_bound')
            nodes[name] = member; members.append((name, member))
        need((flat and prefix not in nodes) or (not flat and prefix in nodes and nodes[prefix].isdir()), 'archive_root')
        links = {}
        # Extraction is a second verified-input pass, after the complete shape check.
    with tarfile.open(archive,'r:gz')as tar:
        for name, member in members:
            for parent in pathlib.PurePosixPath(name).parents:
                if parent.as_posix() == '.': break
                need(parent.as_posix() not in nodes or nodes[parent.as_posix()].isdir(), 'archive_parent')
            if member.issym() or member.islnk():
                raw = member.linkname
                need(raw and not raw.startswith('/') and '\\' not in raw and ':' not in raw and
                     not any(ord(c) < 32 or ord(c) == 127 for c in raw), 'archive_link')
                parts = list(pathlib.PurePosixPath(name).parent.parts) if member.issym() else []
                for part in raw.split('/'):
                    if part == '..': need(len(parts) > (0 if flat else 1), 'archive_link'); parts.pop()
                    elif part not in ('', '.'): parts.append(part)
                target = '/'.join(parts)
                need(target in nodes and (nodes[target].isfile() or member.issym() and nodes[target].isdir()) and
                     (flat or target.startswith(prefix+'/')), 'archive_link')
                links[name] = target
        output=destination/prefix if flat else destination
        if flat:output.mkdir(mode=0o700)
        for name, member in members:
            if member.issym() or member.islnk(): continue
            path = output/name; path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if member.isdir(): path.mkdir(mode=0o700, exist_ok=True); continue
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            try:
                with tar.extractfile(member) as source, os.fdopen(fd, 'wb', closefd=False) as out:
                    count = 0
                    while True:
                        need(deadline is None or time.monotonic()<deadline,'deadline')
                        raw = source.read(65536)
                        if not raw: break
                        count += len(raw); need(count <= member.size, 'archive_size'); out.write(raw)
                    need(count == member.size, 'archive_size'); out.flush(); os.fsync(fd)
                # Public pinned archive modes are source input, not credentials.
                # The entire run/synthetic root remains inaccessible behind0700.
                os.fchmod(fd, member.mode)
            finally: os.close(fd)
        for name, target in links.items():
            path = output/name; path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if nodes[name].islnk(): os.link(output/target, path, follow_symlinks=False)
            else: os.symlink(nodes[name].linkname, path)
    return destination/prefix


def inventory(tree, deadline):
    entries = {}; total = 0
    for path in sorted(tree.rglob('*')):
        need(time.monotonic() < deadline and len(entries) < MAX_MEMBERS, 'deadline')
        i = path.lstat(); name = path.relative_to(tree).as_posix()
        if stat.S_ISDIR(i.st_mode): continue
        if stat.S_ISLNK(i.st_mode): entries[name] = {'link':os.readlink(path)}; continue
        need(stat.S_ISREG(i.st_mode), 'tree')
        digest, size = hash_file(path,single_link=False); total += size; need(total <= MAX_TREE, 'tree_bound')
        entries[name] = {'sha256':digest, 'bytes':size, 'mode':stat.S_IMODE(i.st_mode)}
    return entries


class Run:
    def __init__(self, parent, run_id, deadline):
        self.parent_fd = self.directory_fd = None; self.inode = self.digest = None
        need(re.fullmatch('[0-9a-f]{12}', run_id) is not None and type(deadline) in (int,float) and
             math.isfinite(deadline) and time.monotonic() < deadline <= time.monotonic()+3600, 'configuration')
        self.deadline = self._lease = deadline; self.path = pathlib.Path(parent)/('kubectl-security-'+run_id)
        try:
            self.parent_fd = os.open(parent, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            i = os.fstat(self.parent_fd)
            need(i.st_uid == os.getuid() and stat.S_IMODE(i.st_mode)&0o022 == 0, 'parent')
            self.parent_identity = (i.st_dev,i.st_ino)
            os.mkdir(self.path.name, 0o700, dir_fd=self.parent_fd); os.fsync(self.parent_fd)
            self.directory_fd = os.open(self.path.name, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW, dir_fd=self.parent_fd)
            i = os.fstat(self.directory_fd); self.directory_identity = (i.st_dev,i.st_ino)
            self.record = {'abi':1,'run_id':run_id,'phase':'preparing','source_tag':'v1.37.1',
                'source_commit':SOURCE_COMMIT,'source_tag_object':SOURCE_TAG_OBJECT,'source_sha256':SOURCE_SHA,
                'go_archive_sha256':GO_SHA,'toolchain':GO_VERSION,'pins':PINS,'deadline':deadline,
                'custom_version':CUSTOM_VERSION,'commands':[],'security_accepted':False,'image_injected':False}
            self.save(initial=True)
        except Exception:
            self.close(); raise

    def owned(self):
        need(self.deadline==self._lease,'deadline')
        a = os.fstat(self.parent_fd); b = os.fstat(self.directory_fd)
        parent_named=os.stat(self.path.parent,follow_symlinks=False)
        named = os.stat(self.path.name,dir_fd=self.parent_fd,follow_symlinks=False)
        need((a.st_dev,a.st_ino)==self.parent_identity==(parent_named.st_dev,parent_named.st_ino) and a.st_uid==os.getuid() and a.st_mode&0o022==0 and
             (b.st_dev,b.st_ino)==self.directory_identity==(named.st_dev,named.st_ino) and
             b.st_uid==os.getuid() and stat.S_IMODE(b.st_mode)==0o700, 'ownership')
        if self.inode:
            fd=os.open('record.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=self.directory_fd)
            try:
                i=os.fstat(fd);raw=os.read(fd,1024*1024+1)
                need(stat.S_ISREG(i.st_mode) and stat.S_IMODE(i.st_mode)==0o600 and i.st_uid==os.getuid() and
                     i.st_nlink==1 and (i.st_dev,i.st_ino)==self.inode and len(raw)<=1024*1024 and
                     ident(i)==ident(os.fstat(fd))==ident(os.stat('record.json',dir_fd=self.directory_fd,follow_symlinks=False)) and
                     sha(raw)==self.digest, 'ownership')
            finally:os.close(fd)

    def save(self, initial=False):
        self.owned();raw=(json.dumps(self.record,sort_keys=True,indent=2)+'\n').encode();need(len(raw)<=1024*1024,'record_bound')
        name='record.json'if initial else'record-next.json'
        fd=os.open(name,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600,dir_fd=self.directory_fd)
        try:
            with os.fdopen(fd,'wb',closefd=False)as out:out.write(raw);out.flush();os.fsync(fd)
            i=os.fstat(fd)
        finally:os.close(fd)
        if not initial:self.owned();os.replace(name,'record.json',src_dir_fd=self.directory_fd,dst_dir_fd=self.directory_fd)
        self.inode=(i.st_dev,i.st_ino);self.digest=sha(raw);os.fsync(self.directory_fd)

    def command(self, name, argv, env, cwd):
        self.owned();need(time.monotonic()<self.deadline and not any(c['name']==name for c in self.record['commands']),'replay')
        entry={'name':name,'state':'pending','started_utc':now(),'argv':argv};self.record['commands'].append(entry);self.save()
        child=None;failure=None
        try:
            with open(self.path/(name+'.stdout'),'xb')as out,open(self.path/(name+'.stderr'),'xb')as err:
                os.chmod(out.name,0o600);os.chmod(err.name,0o600)
                self.owned();need(time.monotonic()<self._lease,'deadline')
                child=spawn(argv,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
                entry.update(pid=child.pid);self.save()
                while child.poll()is None:
                    self.owned();need(time.monotonic()<self.deadline,'deadline')
                    need(os.fstat(out.fileno()).st_size<=MAX_LOG and os.fstat(err.fileno()).st_size<=MAX_LOG,'log_bound')
                    try:child.wait(timeout=min(.05,self.deadline-time.monotonic()))
                    except subprocess.TimeoutExpired:pass
                need(os.fstat(out.fileno()).st_size<=MAX_LOG and os.fstat(err.fileno()).st_size<=MAX_LOG,'log_bound')
                os.fsync(out.fileno());os.fsync(err.fileno())
                entry.update(actual_exit_code=child.returncode,state='confirmed'if child.returncode==0 else'refused',completed_utc=now(),
                             stdout_sha256=hash_file(out.name,MAX_LOG)[0],stderr_sha256=hash_file(err.name,MAX_LOG)[0])
                need(time.monotonic()<self.deadline,'deadline');self.save();need(child.returncode==0,'command_exit')
        except Refused as error:failure=error.code
        except Exception:failure='command'
        finally:
            if child:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                except Exception:failure='cleanup'
                try:child.wait(timeout=.25)
                except Exception:failure='cleanup'
            if failure:
                if entry['state']!='refused':entry['state']='uncertain'
                entry['failure']=failure
                try:self.save()
                except Exception:pass # Prior durable pending remains authoritative.
        child=argv=env=None
        if failure:raise Refused(failure)
        return self.path/(name+'.stdout')

    def close(self):
        for key in ('directory_fd','parent_fd'):
            fd=getattr(self,key,None)
            if fd is not None:os.close(fd);setattr(self,key,None)


def copy_input(source, run, name, expected):
    fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        i=os.fstat(fd);need(stat.S_ISREG(i.st_mode) and i.st_uid==os.getuid() and i.st_nlink==1 and
                            i.st_mode&0o022==0 and 0<i.st_size<=MAX_ARCHIVE,'input')
        h=hashlib.sha256();count=0;target=run.path/name
        with open(target,'xb')as out:
            os.chmod(target,0o600)
            while True:
                need(time.monotonic()<run.deadline,'deadline');raw=os.read(fd,65536)
                if not raw:break
                count+=len(raw);need(count<=MAX_ARCHIVE,'input_bound');h.update(raw);out.write(raw)
            out.flush();os.fsync(out.fileno())
        need(count==i.st_size and h.hexdigest()==expected and
             ident(i)==ident(os.fstat(fd))==ident(os.stat(source,follow_symlinks=False)),'input_sha')
        os.fsync(run.directory_fd);return target
    finally:os.close(fd)


def environment(run, go):
    for name in ('home','gopath','cache','tmp'):(run.path/name).mkdir(mode=0o700)
    version=run.path/'custom-version.sh'
    with open(version,'x')as out:
        os.chmod(version,0o600)
        out.write("KUBE_GIT_COMMIT='"+SOURCE_COMMIT+"'\nKUBE_GIT_TREE_STATE='dirty'\nKUBE_GIT_VERSION='"+
                  CUSTOM_VERSION+"-dirty'\nKUBE_GIT_MAJOR='1'\nKUBE_GIT_MINOR='37+'\n");out.flush();os.fsync(out.fileno())
    os.fsync(run.directory_fd)
    return {'PATH':str(go/'bin')+':/usr/bin:/bin','HOME':str(run.path/'home'),'GOPATH':str(run.path/'gopath'),
        'GOCACHE':str(run.path/'cache'),'TMPDIR':str(run.path/'tmp'),'LANG':'C','LC_ALL':'C','TZ':'UTC',
        'GOENV':'off','GOTOOLCHAIN':'local','GO_VERSION':'1.26.9','GOWORK':'off','GOPROXY':'https://proxy.golang.org',
        'GOSUMDB':'sum.golang.org','GOPRIVATE':'','GONOPROXY':'','GONOSUMDB':'','GOINSECURE':'',
        'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_TERMINAL_PROMPT':'0',
        'CGO_ENABLED':'0','GOOS':'linux','GOARCH':'amd64','KUBE_BUILD_PLATFORMS':'linux/amd64',
        'GOMAXPROCS':'2','GOFLAGS':'-p=2','GOMEMLIMIT':'4GiB','SOURCE_DATE_EPOCH':'1790183182',
        'KUBE_GIT_VERSION_FILE':str(version)}


def save_diff_metadata(run, changed, before, after):
    """Detailed public tree metadata stays outside the bounded ownership receipt."""
    need(len(changed)<=MAX_MEMBERS and changed==sorted(set(changed)),'diff_paths')
    data={'abi':1,'changed_paths':changed,'entries':{p:{'before':before.get(p),'after':after.get(p)}for p in changed}}
    run.owned();name='source-diff-metadata.json'
    fd=os.open(name,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600,dir_fd=run.directory_fd)
    try:
        count=0;h=hashlib.sha256()
        with os.fdopen(fd,'wb',closefd=False)as out:
            for text in json.JSONEncoder(sort_keys=True,indent=2).iterencode(data):
                need(time.monotonic()<run.deadline,'deadline');raw=text.encode();count+=len(raw)
                need(count<=MAX_DIFF_METADATA,'diff_metadata_bound');out.write(raw);h.update(raw)
            out.flush();os.fsync(fd)
        run.owned();os.fsync(run.directory_fd)
    finally:os.close(fd)
    return {'changed_paths_count':len(changed),'source_diff_metadata_sha256':h.hexdigest(),
            'source_diff_metadata_path':str(run.path/name)}


def retain_diff(run, source, before):
    after=inventory(source,run.deadline);changed=[p for p in sorted(set(before)|set(after))if before.get(p)!=after.get(p)]
    # Original bytes were pinned in source-original.zip before dependency mutation.
    with zipfile.ZipFile(run.path/'source-diff.zip','x',zipfile.ZIP_DEFLATED)as out:
        with zipfile.ZipFile(run.path/'source-original.zip')as original:
            for name in changed:
                if name in before and 'sha256'in before[name]:out.writestr('before/'+name,original.read(name))
                if name in after and 'sha256'in after[name]:out.write(source/name,'after/'+name)
        out.writestr('diff.json',json.dumps({p:{'before':before.get(p),'after':after.get(p)}for p in changed},indent=2))
    os.chmod(run.path/'source-diff.zip',0o600)
    with open(run.path/'source-diff.zip','rb')as fd:os.fsync(fd.fileno())
    metadata=save_diff_metadata(run,changed,before,after)
    run.record.update(source_diff_sha256=hash_file(run.path/'source-diff.zip',MAX_TREE)[0],**metadata)
    run.save()


def verify_module_abi(run, go, env):
    """Actual supplied Go, no compile/network: explicit mod mode with vendor present."""
    base=run.path/'module-abi';main=base/'main';dep=base/'dep'
    main.mkdir(mode=0o700,parents=True);dep.mkdir(mode=0o700);(main/'vendor').mkdir(mode=0o700)
    files={main/'go.mod':'module example.com/security-fixture\n\ngo 1.20\n\nrequire example.com/dependency v1.0.0\nreplace example.com/dependency => ../dep\n',
           dep/'go.mod':'module example.com/dependency\n\ngo 1.20\n',
           main/'vendor/modules.txt':'# example.com/dependency v1.0.0 => ../dep\n## explicit; go 1.20\n# example.com/dependency => ../dep\n'}
    for path,text in files.items():
        with open(path,'x')as out:os.chmod(path,0o600);out.write(text);out.flush();os.fsync(out.fileno())
    offline=dict(env,GOPROXY='off',GOSUMDB='off')
    result=run.command('go-module-abi',[str(go/'bin/go'),'list','-mod=mod','-m','all'],offline,main)
    need(result.read_text().splitlines()==['example.com/security-fixture','example.com/dependency v1.0.0 => ../dep'],'module_abi')


def build(source_archive, go_archive, parent, run_id, *, deadline):
    run=None;failure=None;receipt=None
    try:
        run=Run(parent,run_id,deadline)
        src=copy_input(source_archive,run,'kubernetes-src.tar.gz',SOURCE_SHA)
        tool=copy_input(go_archive,run,'go1.26.9.tar.gz',GO_SHA)
        source=extract(src,run.path,'kubernetes',deadline,flat=True);go=extract(tool,run.path,'go',deadline)
        for path in ('go.mod','hack/pin-dependency.sh','hack/update-vendor.sh','hack/make-rules/build.sh','cmd/kubectl/kubectl.go'):
            need((source/path).is_file(),'source_shape')
        need((go/'VERSION').read_text().splitlines()[0]==GO_VERSION and (go/'bin/go').is_file(),'toolchain')
        before=inventory(source,deadline)
        with zipfile.ZipFile(run.path/'source-original.zip','x',zipfile.ZIP_DEFLATED)as out:
            for path,item in before.items():
                if 'sha256'in item:out.write(source/path,path)
            out.writestr('source-inventory.json',json.dumps(before,indent=2))
        os.chmod(run.path/'source-original.zip',0o600)
        with open(run.path/'source-original.zip','rb')as saved:os.fsync(saved.fileno())
        os.fsync(run.directory_fd)
        run.record['original_source_inventory_sha256']=sha(json.dumps(before,sort_keys=True).encode())
        env=environment(run,go);run.record['phase']='pending';run.save()
        result=run.command('go-version',[str(go/'bin/go'),'version'],env,source)
        need(result.read_text().strip()=='go version '+GO_VERSION+' linux/amd64','toolchain')
        verify_module_abi(run,go,env)
        for n,(module,version)in enumerate(PINS.items()):
            run.command('pin-'+str(n),['/bin/bash','hack/pin-dependency.sh',module,version],env,source)
        run.command('vendor',['/bin/bash','hack/update-vendor.sh'],env,source)
        modules=run.command('modules',[str(go/'bin/go'),'list','-mod=mod','-m','all'],env,source).read_text()
        actual={}
        for line in modules.splitlines():
            parts=line.split()
            if parts and parts[0]in PINS:
                need(len(parts)==2 and parts[0]not in actual,'dependency_pins');actual[parts[0]]=parts[1]
        need(all(actual.get(k)==v for k,v in PINS.items()),'dependency_pins')
        retain_diff(run,source,before) # Include any go.mod/go.sum updates by explicit module mode.
        run.command('build',['/bin/bash','hack/make-rules/build.sh','cmd/kubectl'],env,source)
        binary=source/'_output/local/bin/linux/amd64/kubectl'
        binary_sha,binary_size=hash_file(binary);need(binary_size>0,'binary')
        version=run.command('kubectl-version',[str(binary),'version','--client=true','-o','json'],env,source)
        data=json.loads(version.read_text());client=data['clientVersion']
        need(client['goVersion']==GO_VERSION and client['gitVersion']==CUSTOM_VERSION+'-dirty'and
             client['gitCommit']==SOURCE_COMMIT and client['gitTreeState']=='dirty'and client['platform']=='linux/amd64','binary_version')
        info=run.command('build-info',[str(go/'bin/go'),'version','-m',str(binary)],env,source).read_text()
        deps={v[1]:v[2]for line in info.splitlines()if len(v:=line.strip().split())>=3 and v[0]=='dep'}
        need(GO_VERSION in info.splitlines()[0] and deps.get('golang.org/x/net')==PINS['golang.org/x/net']and
             all(deps.get(k,v)==v for k,v in PINS.items()),'binary_dependencies')
        need(hash_file(binary)==(binary_sha,binary_size),'binary_changed')
        run.record.update(phase='completed',binary_path=str(binary),binary_sha256=binary_sha,binary_bytes=binary_size,
                          version_sha256=hash_file(version)[0],build_info_sha256=sha(info.encode()),completed_utc=now())
        run.save();receipt=dict(run.record)
    except Refused as error:failure=error.code
    except Exception:failure='operation'
    finally:
        if run:
            if failure:
                run.record.update(phase='refused',failure=failure)
                if any(c['state']in('pending','uncertain')for c in run.record['commands']):run.record['phase']='uncertain'
                try:run.save()
                except Exception:pass
            run.close()
    source_archive=go_archive=env=data=client=modules=info=source=go=None
    if failure:receipt=None;raise Refused(failure)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source-archive',required=True);parser.add_argument('--go-archive',required=True)
    parser.add_argument('--runtime-parent',required=True);parser.add_argument('--run-id',required=True);parser.add_argument('--timeout',type=int,default=2400)
    args=parser.parse_args()
    try:
        need(1<=args.timeout<=3600,'deadline')
        record=build(args.source_archive,args.go_archive,args.runtime_parent,args.run_id,deadline=time.monotonic()+args.timeout)
        print(json.dumps({'phase':record['phase'],'binary_sha256':record['binary_sha256'],'security_accepted':False}))
    except Refused as error:print(json.dumps({'phase':'refused','code':error.code}));raise SystemExit(1)
