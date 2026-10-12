"""Public stub ELF + real POSIX receiver; all SSH/Docker image calls are fixtures."""
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import signal
import stat
import subprocess
import tempfile
import types
import unittest
import zipfile
import tarfile
from unittest import mock

HERE=pathlib.Path(__file__).parent
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
m=load('patched_image',HERE.parent/'build-bortus-patched-kubectl-image.py')
r=load('patched_remote',HERE.parent/'bortus-kubectl-image-remote.py')
staging=load('patched_export_compatibility',HERE.parent/'stage-bortus-release-image.py')


class Tests(unittest.TestCase):
    def setUp(self):
        base=HERE/'public-injection-fixtures';base.mkdir(mode=0o700,exist_ok=True)
        self.root=pathlib.Path(tempfile.mkdtemp(dir=base));self.root.chmod(0o700)
        self.runtime=self.root/'runtime';self.runtime.mkdir(mode=0o755);self.home=self.root/'remote-home';self.home.mkdir(mode=0o755)
        self.commit='1'*40;self.calls=[];self.remote_calls=[];self.tag=b'';self.fail_stage=None;self.transfer_change=None
        header=bytearray(64);header[:6]=b'\x7fELF\x02\x01';header[18:20]=(62).to_bytes(2,'little')
        self.binary=self.root/'kubectl';self.binary.write_bytes(bytes(header)+b'PUBLIC STUB ELF, NEVER EXECUTED')
        self.version=self.root/'version.json';self.version.write_text(json.dumps({'clientVersion':{'goVersion':m.s.GO_VERSION,
            'gitVersion':m.s.CUSTOM_VERSION+'-dirty','gitCommit':m.s.SOURCE_COMMIT,'gitTreeState':'dirty','platform':'linux/amd64'}}))
        self.info=self.root/'build-info.txt';self.info.write_text('/qualified/kubectl: '+m.s.GO_VERSION+'\n'+''.join('\tdep\t'+k+'\t'+v+'\n'for k,v in m.s.PINS.items()))
        self.diff=self.root/'source-diff.zip';self.metadata=self.root/'source-diff-metadata.json';self.receipt=self.root/'security-receipt.json'
        self.entries={'vendor/public.go':{'before':None,'after':{'sha256':m.s.sha(b'public'),'bytes':6,'mode':0o644}}}
        self.write_diff();self.write_receipt();self.context=self.root/'context.tar.gz';self.manifest=self.root/'manifest.json';self.write_context()
        for p in(self.binary,self.version,self.info,self.diff,self.metadata,self.receipt,self.context,self.manifest):p.chmod(0o600)
    def digest(self,p):return m.s.sha(p.read_bytes())
    def write_diff(self,change=None):
        data={'abi':1,'changed_paths':sorted(self.entries),'entries':self.entries}
        if change:change(data)
        self.metadata.write_text(json.dumps(data))
        with zipfile.ZipFile(self.diff,'w',zipfile.ZIP_DEFLATED)as z:
            z.writestr('after/vendor/public.go',b'public');z.writestr('diff.json',json.dumps(self.entries))
    def write_receipt(self,change=None):
        names=['go-version','go-module-abi']+['pin-'+str(n)for n in range(5)]+['vendor','modules','build','kubectl-version','build-info']
        parent='/qualified/kubectl-security-0123456789ab'
        value={'abi':1,'run_id':'0123456789ab','phase':'completed','source_tag':'v1.37.1','source_commit':m.s.SOURCE_COMMIT,
            'source_tag_object':m.s.SOURCE_TAG_OBJECT,'source_sha256':m.s.SOURCE_SHA,'go_archive_sha256':m.s.GO_SHA,
            'toolchain':m.s.GO_VERSION,'pins':m.s.PINS,'deadline':1000.0,'custom_version':m.s.CUSTOM_VERSION,
            'commands':[{'name':name,'state':'confirmed','actual_exit_code':0,'stdout_sha256':'2'*64,'stderr_sha256':'3'*64}for name in names],
            'security_accepted':False,'image_injected':False,'original_source_inventory_sha256':'4'*64,
            'source_diff_sha256':self.digest(self.diff),'changed_paths_count':len(self.entries),'source_diff_metadata_sha256':self.digest(self.metadata),
            'source_diff_metadata_path':parent+'/source-diff-metadata.json','binary_path':parent+'/kubernetes/_output/local/bin/linux/amd64/kubectl',
            'binary_sha256':self.digest(self.binary),'binary_bytes':self.binary.stat().st_size,'version_sha256':self.digest(self.version),
            'build_info_sha256':self.digest(self.info),'completed_utc':'2026-10-12T00:00:00+00:00'}
        if change:change(value)
        self.receipt.write_text(json.dumps(value));self.receipt_sha=self.digest(self.receipt)
    def write_context(self,consumer=None):
        payloads={name:('PUBLIC SOURCE '+name+'\n').encode()for name in m.b.producer.REQUIRED}
        payloads['Dockerfile']=b'FROM public-base AS base\n'+(m.CONSUMER if consumer is None else consumer)
        payloads['prisma/migrations/public/migration.sql']=b'SELECT 1;\n';entries=[];buffer=io.BytesIO()
        with tarfile.open(fileobj=buffer,mode='w')as tar:
            for name,raw in sorted(payloads.items()):
                mode='100755'if name=='docker-entrypoint.sh'else'100644'
                entries.append({'path':name,'mode':mode,'bytes':len(raw),'sha256':m.s.sha(raw),'git_blob':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()})
                item=tarfile.TarInfo(name);item.size=len(raw);item.mode=0o755 if mode=='100755'else 0o644;tar.addfile(item,io.BytesIO(raw))
        data=gzip.compress(buffer.getvalue(),mtime=0);self.context.write_bytes(data);self.context_sha=self.digest(self.context)
        record={'scope':'Immutable raw-Git build context only; no image or release acceptance','source_commit':self.commit,
            'application_tree':'2'*40,'source_prefix':m.b.producer.PREFIX,'started_at_utc':'2026-10-12T00:00:00+00:00',
            'completed_at_utc':'2026-10-12T00:00:01+00:00','context_sha256':self.context_sha,'context_bytes':len(data),
            'source_bytes':sum(v['bytes']for v in entries),'included_files':len(entries),'excluded_entries':0,'files':entries,
            'migrations':[v for v in entries if v['path'].endswith('/migration.sql')],'working_tree_read':False,
            'excluded_payloads_read':False,'dependencies_installed':False,'image_built':False,'cluster_mutations':0,'live_acceptance':False}
        self.manifest.write_text(json.dumps(record));self.manifest_sha=self.digest(self.manifest)
    def request(self,run,mode):
        return {'mode':mode,'commit':self.commit,'owner':run.record['owner'],'binary_sha256':self.digest(self.binary),
            'binary_bytes':self.binary.stat().st_size,'security_receipt_sha256':self.receipt_sha,'context_sha256':self.context_sha,
            'labels':run.record['labels'],'tag':run.record['image_tag']}
    def fake(self,run,stage,command,timeout,stdin=None):
        self.assertEqual(m.b.SSH,command[:len(m.b.SSH)]);self.calls.append(stage)
        self.assertNotIn('sudo',command[-1]);self.assertNotIn('--password',command[-1])
        code=0;raw=b''
        if stage=='tag-check':raw=self.tag
        elif stage=='binary-transfer':
            request=self.request(run,'transfer');owned=r.Stage(request,self.home,True)
            try:reply=owned.transfer(stdin)
            finally:owned.close()
            if self.transfer_change:self.transfer_change(reply)
            raw=json.dumps(reply).encode()
        elif stage=='build':
            self.assertEqual('pending',json.loads((run.directory/'record.json').read_text())['phase'])
            self.assertEqual('pending-build',json.loads((run.directory/'injection-binding.json').read_text())['phase'])
            owned=r.Stage(self.request(run,'build'),self.home,False)
            def docker(args,**kw):
                self.remote_calls.append(args)
                if args[:3]==['docker','image','ls']:return types.SimpleNamespace(returncode=0,stdout=b'')
                self.assertEqual('pending-build',json.loads((owned.path/'record.json').read_text())['phase'])
                self.assertEqual(self.context.read_bytes(),kw['stdin'].read());self.assertIn('--build-context',args)
                self.assertIn('BORTUS_KUBECTL_SHA256='+self.digest(self.binary),args);self.assertEqual('1',kw['env']['DOCKER_BUILDKIT'])
                self.assertEqual([],list(pathlib.Path(kw['env']['DOCKER_CONFIG']).iterdir()))
                return types.SimpleNamespace(returncode=0)
            try:code=owned.build(stdin,invoke=docker)
            finally:owned.close()
        elif stage=='inspect':raw=json.dumps({'config_image_id':'sha256:'+'3'*64,'image_bytes':12345,'labels':run.record['labels']}).encode()
        else:self.fail('Unknown dispatch')
        if stage==self.fail_stage:raise m.b.BuildRefused('public_lost_reply')
        for suffix,data in(('stdout',raw),('stderr',b'')):
            fd=run.create(stage+'.'+suffix)
            with os.fdopen(fd,'wb')as out:out.write(data);out.flush();os.fsync(out.fileno())
            run.record[stage+'_'+suffix+'_sha256']=m.s.sha(data)
        run.record[stage+'_exit_code']=code;return code
    def build(self,**extra):
        args=dict(context=self.context,manifest=self.manifest,commit=self.commit,context_sha=self.context_sha,manifest_sha=self.manifest_sha,
            security_receipt=self.receipt,receipt_sha=self.receipt_sha,binary=self.binary,version=self.version,build_info=self.info,
            vendor_diff=self.diff,diff_metadata=self.metadata,runtime_parent=self.runtime,invoke=self.fake);args.update(extra);return m.build(**args)
    def refuses(self):
        with self.assertRaises(m.b.BuildRefused):self.build()
        self.assertEqual([],self.calls)
    def test_complete_actual_receiver_and_existing_export_receipt_abi(self):
        result=self.build();self.assertEqual(['tag-check','binary-transfer','build','inspect'],self.calls)
        self.assertEqual('completed',result['phase']);self.assertFalse(result['deployed']);self.assertFalse(result['runtime_accepted'])
        local=self.runtime/('bortus-release-'+self.commit);binding=json.loads((local/'injection-binding.json').read_text())
        self.assertEqual('completed',binding['phase']);self.assertEqual(result['config_image_id'],binding['config_image_id'])
        self.assertEqual(self.digest(self.binary),binding['elf_sha256']);self.assertEqual(self.digest(self.metadata),binding['diff_metadata_sha256'])
        self.assertEqual(0o600,stat.S_IMODE((local/'injection-binding.json').stat().st_mode))
        export_root=self.root/'export-runtime';export_root.mkdir(mode=0o755)
        export=staging.OperationRun(export_root,self.commit,'export')
        try:read=staging.receipt(export,local/'record.json',self.digest(local/'record.json'),self.commit,result['config_image_id']);self.assertEqual(result,read)
        finally:export.close()
        with self.assertRaises(Exception):self.build()
        self.assertEqual(4,len(self.calls))
    def test_binary_substitution_refuses_before_remote(self):
        self.binary.write_bytes(self.binary.read_bytes()+b'foreign');self.refuses()
    def test_compact_metadata_sha_count_pointer_and_source_pins_refuse(self):
        self.write_receipt(lambda v:v.update(changed_paths_count=True));self.refuses()
    def test_wrong_origin_pointer_refuses(self):
        self.write_receipt(lambda v:v.update(source_diff_metadata_path='/foreign/source-diff-metadata.json'));self.refuses()
    def test_version_or_dependency_metadata_drift_refuses(self):
        self.info.write_text('/qualified/kubectl: go1.26.8\n');self.write_receipt();self.refuses()
    def test_incomplete_actual_build_commands_refuse(self):
        self.write_receipt(lambda v:v['commands'][-1].update(state='pending'));self.refuses()
    def test_consumer_must_copy_and_check_exact_named_context(self):
        self.write_context(m.CONSUMER.replace(b'sha256sum --check',b'true'));self.refuses()
    def test_zip_inventory_extra_or_wrong_bytes_refuse(self):
        with zipfile.ZipFile(self.diff,'a')as archive:archive.writestr('../foreign',b'public')
        self.write_receipt();self.refuses()
    def test_zip_crc_failure_is_not_hidden_by_outer_sha(self):
        with zipfile.ZipFile(self.diff,'w',zipfile.ZIP_STORED)as archive:
            archive.writestr('after/vendor/public.go',b'public');archive.writestr('diff.json',json.dumps(self.entries))
        raw=self.diff.read_bytes();self.diff.write_bytes(raw.replace(b'public',b'pUblic',1));self.write_receipt();self.refuses()
    def test_remote_reply_mismatch_does_not_dispatch_docker(self):
        self.transfer_change=lambda v:v.update(binary_sha256='9'*64)
        with self.assertRaises(m.b.BuildRefused):self.build()
        self.assertEqual(['tag-check','binary-transfer'],self.calls);self.assertEqual([],self.remote_calls)
    def test_lost_docker_reply_retains_uncertain_and_never_replays(self):
        self.fail_stage='build'
        with self.assertRaises(m.b.BuildRefused):self.build()
        run=self.runtime/('bortus-release-'+self.commit);self.assertEqual('uncertain',json.loads((run/'record.json').read_text())['phase'])
        with self.assertRaises(Exception):self.build()
        self.assertEqual(['tag-check','binary-transfer','build'],self.calls)
    def test_local_pending_flush_failure_prevents_docker(self):
        original=m.Binding.save
        def fail(binding):
            if binding.record['phase']=='pending-build':raise OSError('public flush failure')
            return original(binding)
        with mock.patch.object(m.Binding,'save',fail):
            with self.assertRaises(m.b.BuildRefused):self.build()
        self.assertEqual(['tag-check','binary-transfer'],self.calls);self.assertEqual([],self.remote_calls)
    def test_final_record_directory_flush_failure_cannot_complete_pair(self):
        original=m.b.Run.save;fsync=os.fsync;failed=False
        def save(run):
            def fault(fd):
                nonlocal failed
                if fd==run.fd and run.record['phase']=='completed'and not failed:
                    failed=True;raise OSError('public final record directory flush failure')
                return fsync(fd)
            with mock.patch.object(m.b.os,'fsync',fault):return original(run)
        with mock.patch.object(m.b.Run,'save',save):
            with self.assertRaises(m.b.BuildRefused):self.build()
        self.assertTrue(failed)
        local=self.runtime/('bortus-release-'+self.commit)
        records=[json.loads((local/name).read_text())for name in('record.json','injection-binding.json')]
        self.assertFalse(all(v['phase']=='completed'for v in records))
        with self.assertRaises(Exception):self.build()
        self.assertEqual(['tag-check','binary-transfer','build','inspect'],self.calls)
    def test_final_binding_flush_failure_durably_refuses_base(self):
        original=m.Binding.save
        def save(binding):
            if binding.record['phase']=='completed':raise OSError('public final binding flush failure')
            return original(binding)
        with mock.patch.object(m.Binding,'save',save):
            with self.assertRaises(m.b.BuildRefused):self.build()
        local=self.runtime/('bortus-release-'+self.commit)
        self.assertEqual('uncertain',json.loads((local/'record.json').read_text())['phase'])
        self.assertNotEqual('completed',json.loads((local/'injection-binding.json').read_text())['phase'])
    def test_remote_fresh_hash_extra_file_and_existing_stage_refuse(self):
        run=m.b.Run(self.runtime,self.commit)
        try:
            run.record['labels']=dict(zip(m.b.LABEL_KEYS,[self.commit,'2'*40,self.context_sha,'4'*64,run.record['owner']]))
            request=self.request(run,'transfer');owned=r.Stage(request,self.home,True)
            try:owned.transfer(io.BytesIO(self.binary.read_bytes()))
            finally:owned.close()
            with self.assertRaises(FileExistsError):r.Stage(request,self.home,True)
            stage=self.home/('.bortus-kubectl-image-'+self.commit);binary=stage/'bortus_kubectl/kubectl';binary.write_bytes(b'foreign')
            owned=r.Stage(dict(request,mode='build'),self.home,False)
            try:
                with mock.patch.object(r,'command')as command:
                    with self.assertRaises(r.Refused):owned.build(io.BytesIO(b'context'),invoke=command)
                    command.assert_not_called()
            finally:owned.close()
        finally:run.close()
    def test_actual_owned_child_timeout_and_stdin_privacy(self):
        child=None;original=subprocess.Popen
        def capture(*args,**kwargs):
            nonlocal child;child=original(*args,**kwargs);return child
        with mock.patch.object(r.subprocess,'Popen',capture):
            with self.assertRaises(subprocess.TimeoutExpired):r.command(['/usr/bin/python3','-B','-c','import time;time.sleep(30)'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=.1,env={})
        self.assertIsNotNone(child.poll())
        self.assertTrue(child.stdout.closed)
    def test_source_module_pins_are_not_optional(self):
        self.write_receipt(lambda v:v.update(pins=dict(m.s.PINS,**{'golang.org/x/net':'v0.57.0'})));self.refuses()
    def test_reap_fault_still_closes_owned_pipe_and_selector(self):
        child=None;original=subprocess.Popen
        def capture(*args,**kwargs):
            nonlocal child;child=original(*args,**kwargs);wait=child.wait
            def fail(*a,**kw):wait(*a,**kw);raise OSError('public reap reporting fault')
            child.wait=fail;return child
        with mock.patch.object(r.subprocess,'Popen',capture):
            with self.assertRaises(r.Refused):r.command(['/usr/bin/python3','-B','-c','import time;time.sleep(30)'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=.1,env={})
        self.assertIsNotNone(child.poll());self.assertTrue(child.stdout.closed)
    def test_context_extra_file_refuses_before_any_docker_call(self):
        run=m.b.Run(self.runtime,self.commit)
        try:
            run.record['labels']=dict(zip(m.b.LABEL_KEYS,[self.commit,'2'*40,self.context_sha,'4'*64,run.record['owner']]))
            request=self.request(run,'transfer');owned=r.Stage(request,self.home,True)
            try:owned.transfer(io.BytesIO(self.binary.read_bytes()))
            finally:owned.close()
            path=self.home/('.bortus-kubectl-image-'+self.commit);(path/'bortus_kubectl/foreign').write_text('public')
            owned=r.Stage(dict(request,mode='build'),self.home,False)
            try:
                with mock.patch.object(r,'command')as command:
                    with self.assertRaises(r.Refused):owned.build(io.BytesIO(b'context'),invoke=command)
                    command.assert_not_called()
            finally:owned.close()
        finally:run.close()
    def test_remote_pending_fsync_failure_does_not_start_docker_build(self):
        run=m.b.Run(self.runtime,self.commit)
        try:
            run.record['labels']=dict(zip(m.b.LABEL_KEYS,[self.commit,'2'*40,self.context_sha,'4'*64,run.record['owner']]))
            request=self.request(run,'transfer');owned=r.Stage(request,self.home,True)
            try:owned.transfer(io.BytesIO(self.binary.read_bytes()))
            finally:owned.close()
            owned=r.Stage(dict(request,mode='build'),self.home,False);calls=[];original=os.fsync
            def fail(fd):
                if fd==owned.fd:raise OSError('public injected directory flush failure')
                return original(fd)
            def docker(args,**kwargs):calls.append(args);return types.SimpleNamespace(returncode=0,stdout=b'')
            try:
                with mock.patch.object(r.os,'fsync',fail):
                    with self.assertRaises(OSError):owned.build(io.BytesIO(b'context'),invoke=docker)
                self.assertEqual(1,len(calls));self.assertEqual(['docker','image','ls'],calls[0][:3])
                self.assertEqual('pending-build',json.loads((owned.path/'record.json').read_text())['phase'])
            finally:owned.close()
        finally:run.close()
    def test_raw_source_contains_no_binary_and_five_labels_unchanged(self):
        result=self.build();self.assertEqual(set(m.b.LABEL_KEYS),set(result['labels']))
        with tarfile.open(self.context,'r:gz')as archive:self.assertFalse(any(item.name.endswith('/kubectl')for item in archive))


if __name__=='__main__':unittest.main()
