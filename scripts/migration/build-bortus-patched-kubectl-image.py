"""Separate source-bound custom ELF BuildKit context; default builder ABI untouched."""
import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shlex
import signal
import subprocess
import stat
import tarfile
import uuid
import zipfile
import time


def load(name,file):
    spec=importlib.util.spec_from_file_location(name,pathlib.Path(__file__).with_name(file))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


b=load('patched_base_builder','build-bortus-release-image.py')
s=load('patched_security_contract','build-bortus-kubectl-security.py')
require=b.require
REMOTE=pathlib.Path(__file__).with_name('bortus-kubectl-image-remote.py')
CONSUMER=(b'COPY --from=bortus_kubectl /kubectl /usr/local/bin/kubectl\n'
          b'ARG BORTUS_KUBECTL_SHA256\n'
          b'RUN echo "${BORTUS_KUBECTL_SHA256}  /usr/local/bin/kubectl" | sha256sum --check && chmod 755 /usr/local/bin/kubectl\n')


def execute(run,stage,command,timeout,stdin=None):
    run.owned();child=None;failure=None;code=None
    out_fd=run.create(stage+'.stdout')
    try:err_fd=run.create(stage+'.stderr')
    except Exception:os.close(out_fd);raise
    with os.fdopen(out_fd,'wb')as out,os.fdopen(err_fd,'wb')as err:
        try:
            child=subprocess.Popen(command,stdin=stdin or subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
            end=time.monotonic()+timeout
            while child.poll()is None:
                require(os.fstat(out.fileno()).st_size<=128*1024*1024 and os.fstat(err.fileno()).st_size<=128*1024*1024,'log_bound')
                left=end-time.monotonic()
                if left<=0:raise subprocess.TimeoutExpired(command,timeout)
                try:child.wait(timeout=min(.05,left))
                except subprocess.TimeoutExpired:pass
            require(os.fstat(out.fileno()).st_size<=128*1024*1024 and os.fstat(err.fileno()).st_size<=128*1024*1024,'log_bound')
            code=child.returncode;run.record[stage+'_exit_code']=code
        except subprocess.TimeoutExpired:
            failure='subprocess_timeout';run.record[stage+'_exit_code']=None;run.record[stage+'_timed_out']=True
        except Exception:failure='subprocess'
        finally:
            if child:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                except Exception:failure='cleanup'
                try:child.wait(timeout=.25)
                except Exception:failure='cleanup'
            out.flush();err.flush();os.fsync(out.fileno());os.fsync(err.fileno())
            for suffix in('stdout','stderr'):
                with(run.directory/(stage+'.'+suffix)).open('rb')as log:run.record[stage+'_'+suffix+'_sha256']=b.stream_hash(log)
    child=command=stdin=None
    if failure:raise b.BuildRefused(failure)
    return code


class Binding:
    def __init__(self,run,values):
        self.run=run;self.record=values;self.identity=self.digest=None;self.save()
    def owned(self):
        self.run.owned()
        if self.identity:
            fd=os.open('injection-binding.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=self.run.fd)
            try:
                i=os.fstat(fd);raw=os.read(fd,65537)
                require(b.input_identity(i)==self.identity and len(raw)<=65536 and hashlib.sha256(raw).hexdigest()==self.digest and
                        b.input_identity(os.fstat(fd))==self.identity==b.input_identity(os.stat('injection-binding.json',dir_fd=self.run.fd,follow_symlinks=False)),'binding_ownership')
            finally:os.close(fd)
    def save(self):
        self.owned();name='binding-'+uuid.uuid4().hex+'.next';fd=self.run.create(name)
        try:
            raw=(json.dumps(self.record,sort_keys=True,indent=2)+'\n').encode();require(len(raw)<=65536,'binding_bound')
            with os.fdopen(fd,'wb',closefd=False)as out:out.write(raw);out.flush();os.fsync(fd)
            self.owned()
            if self.identity is None:
                # Link rather than replace prevents first-save adoption of an existing sidecar.
                os.link(name,'injection-binding.json',src_dir_fd=self.run.fd,dst_dir_fd=self.run.fd,follow_symlinks=False)
                os.unlink(name,dir_fd=self.run.fd)
            else:os.replace(name,'injection-binding.json',src_dir_fd=self.run.fd,dst_dir_fd=self.run.fd)
            os.fsync(self.run.fd);self.identity=b.input_identity(os.fstat(fd));self.digest=hashlib.sha256(raw).hexdigest()
        finally:os.close(fd)


def read_json(run,name,digest,maximum):
    with run.open_input(name,digest)as stream:
        raw=stream.read(maximum+1);require(len(raw)<=maximum,'metadata_bound')
        return json.loads(raw,object_pairs_hook=b.unique)


def security(run,receipt_sha):
    record=read_json(run,'security-receipt.json',receipt_sha,b.MAX_MANIFEST_BYTES)
    expected={'abi','run_id','phase','source_tag','source_commit','source_tag_object','source_sha256','go_archive_sha256',
        'toolchain','pins','deadline','custom_version','commands','security_accepted','image_injected',
        'original_source_inventory_sha256','source_diff_sha256','changed_paths_count','source_diff_metadata_sha256',
        'source_diff_metadata_path','binary_path','binary_sha256','binary_bytes',
        'version_sha256','build_info_sha256','completed_utc'}
    require(type(record)is dict and set(record)==expected and type(record['abi'])is int and record['abi']==1 and
        record['phase']=='completed'and re.fullmatch('[0-9a-f]{12}',record['run_id'])and record['source_tag']=='v1.37.1'and
        record['source_commit']==s.SOURCE_COMMIT and record['source_tag_object']==s.SOURCE_TAG_OBJECT and
        record['source_sha256']==s.SOURCE_SHA and record['go_archive_sha256']==s.GO_SHA and record['toolchain']==s.GO_VERSION and
        record['pins']==s.PINS and record['custom_version']==s.CUSTOM_VERSION and record['security_accepted']is False and
        record['image_injected']is False and type(record['binary_bytes'])is int and 64<=record['binary_bytes']<=s.MAX_FILE,'security_receipt')
    require(all(b.hexid(record[k],64)for k in('original_source_inventory_sha256','source_diff_sha256','source_diff_metadata_sha256','binary_sha256','version_sha256','build_info_sha256')),'security_hashes')
    pointer=pathlib.PurePosixPath(record['source_diff_metadata_path']);base=pointer.parent
    require(pointer.is_absolute()and str(pointer)==record['source_diff_metadata_path']and len(pointer.parts)<=32 and pointer.name=='source-diff-metadata.json'and
        base.name=='kubectl-security-'+record['run_id']and all(p not in('.','..')for p in pointer.parts[1:])and
        record['binary_path']==str(base/'kubernetes/_output/local/bin/linux/amd64/kubectl')and
        type(record['changed_paths_count'])is int and 0<=record['changed_paths_count']<=s.MAX_MEMBERS,'security_pointer')
    names=['go-version','go-module-abi']+['pin-'+str(n)for n in range(5)]+['vendor','modules','build','kubectl-version','build-info']
    require(type(record['commands'])is list and [c.get('name')for c in record['commands']]==names and
        all(c.get('state')=='confirmed'and type(c.get('actual_exit_code'))is int and c['actual_exit_code']==0 and
            all(b.hexid(c.get(k),64)for k in('stdout_sha256','stderr_sha256'))for c in record['commands']),'security_commands')
    for name,key in(('kubectl','binary_sha256'),('version.json','version_sha256'),('build-info.txt','build_info_sha256'),('source-diff.zip','source_diff_sha256')):
        with run.open_input(name,record[key])as stream:
            if name=='kubectl':
                header=stream.read(64);require(os.fstat(stream.fileno()).st_size==record['binary_bytes']and
                    header[:6]==b'\x7fELF\x02\x01'and int.from_bytes(header[18:20],'little')==62,'binary_elf')
    version=read_json(run,'version.json',record['version_sha256'],65536)['clientVersion']
    require(version.get('goVersion')==s.GO_VERSION and version.get('gitVersion')==s.CUSTOM_VERSION+'-dirty'and
        version.get('gitCommit')==s.SOURCE_COMMIT and version.get('gitTreeState')=='dirty'and version.get('platform')=='linux/amd64','binary_version')
    with run.open_input('build-info.txt',record['build_info_sha256'])as stream:info=stream.read(1024*1024+1).decode()
    require(len(info)<=1024*1024 and s.GO_VERSION in info.splitlines()[0],'build_info')
    pins={}
    for line in info.splitlines():
        parts=line.strip().split()
        if len(parts)>=3 and parts[0]=='dep'and parts[1]in s.PINS:
            require(parts[1]not in pins,'build_info');pins[parts[1]]=parts[2]
    require(pins.get('golang.org/x/net')==s.PINS['golang.org/x/net']and all(pins.get(k,v)==v for k,v in s.PINS.items()),'build_info')
    verify_diff(run,record)
    return record


def verify_diff(run,record):
    metadata=read_json(run,'source-diff-metadata.json',record['source_diff_metadata_sha256'],s.MAX_DIFF_METADATA)
    require(type(metadata)is dict and set(metadata)=={'abi','changed_paths','entries'}and type(metadata['abi'])is int and
        metadata['abi']==1 and type(metadata['changed_paths'])is list and type(metadata['entries'])is dict,'diff_metadata')
    names=metadata['changed_paths'];entries=metadata['entries']
    require(len(names)==record['changed_paths_count']and names==sorted(set(names))and set(entries)==set(names),'diff_inventory')
    wanted={};total=0
    for name in names:
        s.relative(name);pair=entries[name]
        require(type(pair)is dict and set(pair)=={'before','after'}and pair['before']!=pair['after'],'diff_entry')
        for phase,item in pair.items():
            if item is None:continue
            require(type(item)is dict,'diff_entry')
            if set(item)=={'link'}:
                require(type(item['link'])is str and 0<len(item['link'].encode())<=4096 and
                    not any(ord(c)<32 or ord(c)==127 for c in item['link']),'diff_link') # Metadata only; never resolve/follow.
            else:
                require(set(item)=={'sha256','bytes','mode'}and b.hexid(item['sha256'],64)and type(item['bytes'])is int and
                    0<=item['bytes']<=s.MAX_FILE and type(item['mode'])is int and 0<=item['mode']<=0o777,'diff_entry')
                wanted[phase+'/'+name]=item;total+=item['bytes'];require(total<=2*s.MAX_TREE,'diff_bound')
    with run.open_input('source-diff.zip',record['source_diff_sha256'])as stream,zipfile.ZipFile(stream)as archive:
        members=archive.infolist();require(len(members)<=2*s.MAX_MEMBERS+1,'diff_bound');seen=set();diff=None
        for info in members:
            name=info.filename;s.relative(name)
            mode=(info.external_attr>>16)&0o170000
            require(name not in seen and not info.is_dir()and mode in(0,stat.S_IFREG)and not info.flag_bits&1 and
                info.compress_type in(zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED),'diff_zip');seen.add(name)
            expected=wanted.get(name);require(name=='diff.json'or expected is not None,'diff_inventory')
            maximum=s.MAX_DIFF_METADATA if name=='diff.json'else expected['bytes']
            require(0<=info.file_size<=maximum,'diff_bound');h=hashlib.sha256();count=0;raw_metadata=bytearray()
            with archive.open(info)as source:
                while True:
                    raw=source.read(65536)
                    if not raw:break
                    count+=len(raw);require(count<=maximum,'diff_bound');h.update(raw)
                    if name=='diff.json':raw_metadata.extend(raw)
            require(count==info.file_size,'diff_zip') # Reading to EOF independently checks member CRC.
            if name=='diff.json':diff=json.loads(raw_metadata,object_pairs_hook=b.unique)
            else:require(count==expected['bytes']and h.hexdigest()==expected['sha256'],'diff_content')
        require(seen==set(wanted)|{'diff.json'}and diff==entries,'diff_inventory')


def consumer(run,context_sha):
    with run.open_input('context.tar.gz',context_sha)as stream,tarfile.open(fileobj=stream,mode='r:gz')as tar:
        member=tar.getmember('Dockerfile');require(member.isfile()and member.size<=16*1024*1024,'consumer')
        raw=tar.extractfile(member).read();require(CONSUMER in raw and raw.count(b'COPY --from=bortus_kubectl ')==1 and
            b'dl.k8s.io'not in raw and not re.search(rb'^FROM[^\n]+\sAS\s+bortus_kubectl\s*$',raw,re.M|re.I),'consumer')
    return hashlib.sha256(raw).hexdigest()


def bridge(run,request,remote_sha):
    with run.open_input('remote.py',remote_sha)as stream:source=stream.read(128*1024+1).decode()
    require(len(source)<=128*1024,'remote_source')
    return b.SSH+[shlex.join(['python3','-c',source,json.dumps(request,sort_keys=True,separators=(',',':'))])]


def build(context,manifest,commit,context_sha,manifest_sha,security_receipt,receipt_sha,binary,version,build_info,vendor_diff,diff_metadata,runtime_parent,invoke=execute):
    require(b.hexid(commit,40)and all(b.hexid(v,64)for v in(context_sha,manifest_sha,receipt_sha)),'exact_input')
    run=b.Run(runtime_parent,commit);binding=None;dispatched=False;build_exit=None;failure=None;result=None
    try:
        for path,name,maximum in((context,'context.tar.gz',b.MAX_ARCHIVE_BYTES),(manifest,'manifest.json',b.MAX_MANIFEST_BYTES),
            (security_receipt,'security-receipt.json',b.MAX_MANIFEST_BYTES),(binary,'kubectl',s.MAX_FILE),
            (version,'version.json',65536),(build_info,'build-info.txt',1024*1024),(vendor_diff,'source-diff.zip',s.MAX_TREE),
            (diff_metadata,'source-diff-metadata.json',s.MAX_DIFF_METADATA),(REMOTE,'remote.py',128*1024)):
            run.copy_input(path,name,maximum)
        with run.open_input('manifest.json',manifest_sha)as ms,run.open_input('context.tar.gz',context_sha)as stream:
            manifest_data=b.verify(stream,ms.read(),commit,context_sha,manifest_sha)
        dockerfile_sha=consumer(run,context_sha);secured=security(run,receipt_sha)
        with(run.directory/'remote.py').open('rb')as stream:remote_sha=b.stream_hash(stream)
        labels=dict(zip(b.LABEL_KEYS,[commit,manifest_data['application_tree'],context_sha,manifest_sha,run.record['owner']]))
        run.record.update(context_sha256=context_sha,manifest_sha256=manifest_sha,application_tree=manifest_data['application_tree'],
            labels=labels,included_files=manifest_data['included_files'],phase='validated');run.save()
        values={'abi':1,'phase':'validated','source_commit':commit,'context_sha256':context_sha,'manifest_sha256':manifest_sha,
            'owner':run.record['owner'],'labels':labels,'dockerfile_sha256':dockerfile_sha,'security_receipt_sha256':receipt_sha,
            'elf_sha256':secured['binary_sha256'],'elf_bytes':secured['binary_bytes'],'source_archive_sha256':secured['source_sha256'],
            'source_commit_base':secured['source_commit'],'vendor_diff_sha256':secured['source_diff_sha256'],
            'diff_metadata_sha256':secured['source_diff_metadata_sha256'],'changed_paths_count':secured['changed_paths_count'],
            'version_sha256':secured['version_sha256'],'build_info_sha256':secured['build_info_sha256'],'remote_source_sha256':remote_sha,
            'config_image_id':None,'security_accepted':False,'runtime_accepted':False,'deployed':False}
        binding=Binding(run,values)
        code=invoke(run,'tag-check',b.remote(['docker','image','ls','--quiet','--filter','reference='+run.record['image_tag']]),30)
        require(code==0 and(run.directory/'tag-check.stdout').stat().st_size==0,'tag_exists')
        request={'mode':'transfer','commit':commit,'owner':run.record['owner'],'binary_sha256':secured['binary_sha256'],
            'binary_bytes':secured['binary_bytes'],'security_receipt_sha256':receipt_sha,'context_sha256':context_sha,'labels':labels,'tag':run.record['image_tag']}
        binding.record['phase']='pending-transfer';binding.save()
        with run.open_input('kubectl',secured['binary_sha256'])as stream:
            code=invoke(run,'binary-transfer',bridge(run,request,remote_sha),120,stdin=stream);run.check_input('kubectl',stream.fileno())
        require(code==0 and(run.directory/'binary-transfer.stdout').stat().st_size<=65536,'transfer')
        reply=json.loads((run.directory/'binary-transfer.stdout').read_bytes(),object_pairs_hook=b.unique)
        require(reply=={'owner':request['owner'],'binary_sha256':request['binary_sha256'],'binary_bytes':request['binary_bytes'],'phase':'ready'},'transfer_identity')
        run.record.update(phase='pending',pending_at_utc=b.now());run.save();binding.record['phase']='pending-build';binding.save()
        request['mode']='build'
        with run.open_input('context.tar.gz',context_sha)as stream,run.open_input('kubectl',secured['binary_sha256']):
            binding.owned();dispatched=True;code=invoke(run,'build',bridge(run,request,remote_sha),2400,stdin=stream);build_exit=code;run.check_input('context.tar.gz',stream.fileno())
        run.record.update(build_exit_code=code,phase='uncertain'if code in(0,255)else'failed',completed_at_utc=b.now());run.save();require(code==0,'build_exit')
        projection='{"config_image_id":{{json .Id}},"image_bytes":{{json .Size}},"labels":{'+','.join(
            json.dumps(k)+':{{json (index .Config.Labels '+json.dumps(k)+')}}'for k in b.LABEL_KEYS)+'}}'
        code=invoke(run,'inspect',b.remote(['docker','image','inspect','--format',projection,run.record['image_tag']]),30)
        require(code==0 and(run.directory/'inspect.stdout').stat().st_size<=65536,'image_inspect')
        image=json.loads((run.directory/'inspect.stdout').read_bytes(),object_pairs_hook=b.unique)
        require(type(image)is dict and set(image)=={'config_image_id','image_bytes','labels'}and
            re.fullmatch('sha256:[0-9a-f]{64}',image['config_image_id'])and type(image['image_bytes'])is int and
            image['image_bytes']>0 and image['labels']==labels,'image_identity')
        # Leave binding pending until the base completion has durably flushed.
        run.record.update(image,phase='completed',completed_at_utc=b.now(),image_manifest_digest=None,runtime_digest_qualified=False);run.save()
        binding.record.update(phase='completed',config_image_id=image['config_image_id']);binding.save();result=dict(run.record)
    except Exception as error:
        failure=error.code if isinstance(error,b.BuildRefused)else'operation_failed'
        phase='refused'if not dispatched else'failed'if build_exit not in(None,0,255)else'uncertain'
        run.record.update(phase=phase,failure=failure,completed_at_utc=b.now())
        try:run.save()
        except Exception:pass
        if binding:
            binding.record.update(phase=phase,failure=failure)
            try:binding.save()
            except Exception:pass
    finally:run.close()
    secured=manifest_data=reply=request=image=version=build_info=context=manifest=security_receipt=binary=vendor_diff=diff_metadata=None
    if failure:result=None;raise b.BuildRefused(failure)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for key in('context','manifest','commit','context-sha','manifest-sha','security-receipt','receipt-sha','binary','version','build-info','vendor-diff','diff-metadata','runtime-parent'):
        parser.add_argument('--'+key,required=True)
    args=parser.parse_args()
    try:
        result=build(args.context,args.manifest,args.commit,args.context_sha,args.manifest_sha,args.security_receipt,args.receipt_sha,
            args.binary,args.version,args.build_info,args.vendor_diff,args.diff_metadata,args.runtime_parent)
        print(json.dumps({k:result[k]for k in('phase','source_commit','config_image_id','deployed','runtime_accepted')}))
    except Exception:print('Patched image build refused; inspect retained owned run without replay.',file=__import__('sys').stderr);raise SystemExit(1)
