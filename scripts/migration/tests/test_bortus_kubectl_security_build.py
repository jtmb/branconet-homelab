import importlib.util
import io
import json
import os
import pathlib
import signal
import stat
import subprocess
import tarfile
import tempfile
import time
import unittest
from unittest import mock

spec=importlib.util.spec_from_file_location('security_build',pathlib.Path(__file__).parents[1]/'build-bortus-kubectl-security.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def archive(path, prefix, files, extra=()):
    with tarfile.open(path,'w:gz')as tar:
        if prefix:
            root=tarfile.TarInfo(prefix);root.type=tarfile.DIRTYPE;root.mode=0o755;tar.addfile(root)
        for name,raw in files.items():
            item=tarfile.TarInfo(prefix+'/'+name if prefix else name);item.mode=0o755 if name.endswith('.sh')or name.startswith('bin/')else 0o644
            item.size=len(raw);tar.addfile(item,io.BytesIO(raw))
        for member,raw in extra:tar.addfile(member,io.BytesIO(raw)if raw else None)
    path.chmod(0o600);return m.hash_file(path,m.MAX_ARCHIVE)[0]


class Tests(unittest.TestCase):
    def setUp(self):
        base=pathlib.Path(__file__).parent/'public-fixture-runs';base.mkdir(mode=0o700,exist_ok=True)
        self.root=pathlib.Path(tempfile.mkdtemp(dir=base));self.root.chmod(0o700)
        self.children=[]
    def tearDown(self):
        for child in self.children:
            self.assertIsNotNone(child.poll())
        # Retain exact controlled fixture commands/archives/logs on failure and success.
    def run_owned(self,lease=5):return m.Run(self.root,'0123456789ab',time.monotonic()+lease)
    def fake_archives(self,wrong_binary=False):
        pins='\n'.join(k+' '+v for k,v in m.PINS.items())+'\n'
        go_script="""#!/usr/bin/python3
import sys,pathlib,json
args=sys.argv[1:]
if args==['version']:print('go version go1.26.9 linux/amd64')
elif args==['list','-mod=mod','-m','all']:
 if pathlib.Path.cwd().name=='main':
  assert pathlib.Path('vendor/modules.txt').is_file()
  print('example.com/security-fixture');print('example.com/dependency v1.0.0 => ../dep')
 else:pathlib.Path('go.sum').write_text('public module-query fixture\\n');print(PINS,end='')
elif args[:2]==['version','-m']:print(args[2]+': go1.26.9');print(INFO)
else:raise SystemExit(9)
""".replace('PINS',repr(pins)).replace('INFO',repr('\n'.join('\tdep\t'+k+'\t'+('v0.57.0'if wrong_binary and k=='golang.org/x/net'else v)for k,v in m.PINS.items())))
        binary="#!/usr/bin/python3\nimport json\nprint(json.dumps("+repr({'clientVersion':{'goVersion':m.GO_VERSION,'gitVersion':m.CUSTOM_VERSION+'-dirty','gitCommit':m.SOURCE_COMMIT,'gitTreeState':'dirty','platform':'linux/amd64'}})+"))\n"
        make="all:\n\tmkdir -p _output/local/bin/linux/amd64\n\tcp fixture-kubectl _output/local/bin/linux/amd64/kubectl\n\tchmod 700 _output/local/bin/linux/amd64/kubectl\n"
        source=self.root/'source.tar.gz';tool=self.root/'go.tar.gz'
        a=archive(source,None,{'go.mod':b'module k8s.io/kubernetes\n','hack/pin-dependency.sh':b'#!/bin/bash\nset -eu\nprintf "%s %s\\n" "$1" "$2" >> pins.txt\n',
            'hack/update-vendor.sh':b'#!/bin/bash\nset -eu\nmkdir vendor\nprintf "public patched fixture\\n" > vendor/public.go\n',
            'hack/make-rules/build.sh':b'#!/bin/bash\nset -eu\ntest "$1" = cmd/kubectl\nmkdir -p _output/local/bin/linux/amd64\ncp fixture-kubectl _output/local/bin/linux/amd64/kubectl\nchmod 700 _output/local/bin/linux/amd64/kubectl\n','cmd/kubectl/kubectl.go':b'package main\n','Makefile':make.encode(),'fixture-kubectl':binary.encode()})
        b=archive(tool,'go',{'VERSION':b'go1.26.9\n','bin/go':go_script.encode()})
        return source,tool,a,b
    def build_fixture(self,wrong_binary=False):
        source,tool,a,b=self.fake_archives(wrong_binary)
        with mock.patch.object(m,'SOURCE_SHA',a),mock.patch.object(m,'GO_SHA',b):
            return m.build(source,tool,self.root,'0123456789ab',deadline=time.monotonic()+20)
    def test_complete_actual_public_child_contract_no_go_compile(self):
        with mock.patch.dict(os.environ,{'AWS_SECRET_ACCESS_KEY':'PRIVATE-FIXTURE','KUBECONFIG':'/private/fixture','SSH_AUTH_SOCK':'/private/agent'}):
            result=self.build_fixture()
        self.assertEqual('completed',result['phase']);self.assertFalse(result['security_accepted']);self.assertFalse(result['image_injected'])
        self.assertEqual(12,len(result['commands']));self.assertTrue(all(c['state']=='confirmed'for c in result['commands']))
        self.assertEqual(['list','-mod=mod','-m','all'],result['commands'][1]['argv'][1:])
        run=self.root/'kubectl-security-0123456789ab';metadata=json.loads((run/'source-diff-metadata.json').read_text())
        self.assertIn('vendor/public.go',metadata['changed_paths']);self.assertIn('go.sum',metadata['changed_paths'])
        self.assertEqual(len(metadata['changed_paths']),result['changed_paths_count']);self.assertNotIn('changed_paths',result)
        self.assertEqual(m.hash_file(run/'source-diff-metadata.json',m.MAX_DIFF_METADATA)[0],result['source_diff_metadata_sha256'])
        self.assertTrue((run/'source-diff.zip').is_file());self.assertTrue((run/'source-original.zip').is_file())
        self.assertTrue(all(stat.S_IMODE(p.stat().st_mode)==0o600 for p in run.glob('*.stdout')))
        before=len(list(pathlib.Path('/proc/self/fd').iterdir()))
        with self.assertRaises(FileExistsError):m.Run(self.root,'0123456789ab',time.monotonic()+5)
        self.assertEqual(before,len(list(pathlib.Path('/proc/self/fd').iterdir())))
    def test_patched_binary_metadata_is_required_not_source_pins_only(self):
        with self.assertRaises(m.Refused)as context:self.build_fixture(True)
        self.assertEqual('binary_dependencies',context.exception.code)
        self.assertEqual('refused',json.loads((self.root/'kubectl-security-0123456789ab/record.json').read_text())['phase'])
    def test_isolated_environment_drops_every_ambient_value(self):
        run=self.run_owned()
        try:
            with mock.patch.dict(os.environ,{'PRIVATE':'fixture','HTTP_PROXY':'http://private','GIT_CONFIG_COUNT':'1'}):env=m.environment(run,self.root/'go')
            self.assertNotIn('PRIVATE',env);self.assertNotIn('HTTP_PROXY',env);self.assertNotIn('GIT_CONFIG_COUNT',env)
            self.assertEqual('local',env['GOTOOLCHAIN']);self.assertEqual('https://proxy.golang.org',env['GOPROXY'])
            self.assertEqual('/dev/null',env['GIT_CONFIG_GLOBAL']);self.assertEqual('off',env['GOENV'])
            self.assertEqual('2',env['GOMAXPROCS']);self.assertEqual('-p=2',env['GOFLAGS']);self.assertEqual('4GiB',env['GOMEMLIMIT'])
        finally:run.close()
    def test_pending_is_actual_disk_before_spawn(self):
        run=self.run_owned();observed=[]
        original=m.spawn
        def capture(args,**kwargs):
            disk=json.loads((run.path/'record.json').read_text());self.assertEqual('pending',disk['commands'][-1]['state']);observed.append(True)
            self.assertEqual(subprocess.DEVNULL,kwargs['stdin']);self.assertTrue(kwargs['start_new_session'])
            child=original(args,**kwargs);self.children.append(child);return child
        try:
            with mock.patch.object(m,'spawn',capture):run.command('fixture',['/usr/bin/python3','-B','-c','print("public")'],{'PATH':'/usr/bin:/bin'},run.path)
            self.assertEqual([True],observed)
        finally:run.close()
    def test_pre_dispatch_directory_fsync_failure_no_child(self):
        run=self.run_owned();original=os.fsync
        def fail(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):raise OSError('public injected failure')
            return original(fd)
        try:
            with mock.patch.object(m.os,'fsync',fail),mock.patch.object(m,'spawn')as spawn:
                with self.assertRaises(OSError):run.command('fixture',['false'],{},run.path)
                spawn.assert_not_called()
        finally:run.close()
    def test_after_reply_confirmation_failure_keeps_pending_no_replay(self):
        run=self.run_owned(30);original=run.save
        def fail(*args,**kwargs):
            if run.record['commands']and 'actual_exit_code'in run.record['commands'][-1]:raise OSError('public injected failure')
            return original(*args,**kwargs)
        try:
            with mock.patch.object(run,'save',fail):
                with self.assertRaises(m.Refused):run.command('fixture',['/usr/bin/python3','-B','-c','print("public")'],{},run.path)
            self.assertEqual(0,run.record['commands'][-1]['actual_exit_code'])
            disk=json.loads((run.path/'record.json').read_text());self.assertEqual('pending',disk['commands'][-1]['state'])
            with self.assertRaises(m.Refused):run.command('fixture',['false'],{},run.path)
        finally:run.close()
    def test_deadline_stops_only_owned_session_and_reaps(self):
        run=self.run_owned(.15);original=m.spawn
        def capture(*args,**kwargs):child=original(*args,**kwargs);self.children.append(child);return child
        try:
            with mock.patch.object(m,'spawn',capture):
                with self.assertRaises(m.Refused)as context:run.command('fixture',['/usr/bin/python3','-B','-c','import time;time.sleep(30)'],{},run.path)
            self.assertEqual('deadline',context.exception.code);self.assertIsNotNone(self.children[0].poll())
            self.assertEqual('uncertain',json.loads((run.path/'record.json').read_text())['commands'][0]['state'])
        finally:run.close()
    def test_fast_log_overflow_refuses_before_success(self):
        run=self.run_owned()
        try:
            with mock.patch.object(m,'MAX_LOG',64):
                with self.assertRaises(m.Refused)as context:run.command('fixture',['/usr/bin/python3','-B','-c','print("x"*1000)'],{},run.path)
            self.assertEqual('log_bound',context.exception.code)
        finally:run.close()
    def test_source_hash_or_symlink_refuses_before_any_dispatch(self):
        source,tool,a,b=self.fake_archives()
        with mock.patch.object(m,'spawn')as child:
            with self.assertRaises(m.Refused):m.build(source,tool,self.root,'0123456789ab',deadline=time.monotonic()+5)
            child.assert_not_called()
        link=self.root/'input-link';link.symlink_to(source)
        run=m.Run(self.root,'123456789abc',time.monotonic()+5)
        try:
            with self.assertRaises(OSError):m.copy_input(link,run,'copy',a)
        finally:run.close()
    def test_replaced_record_and_parent_are_not_adopted(self):
        run=self.run_owned()
        try:
            (run.path/'record.json').rename(run.path/'old.json');(run.path/'record.json').write_text('{}');(run.path/'record.json').chmod(0o600)
            with self.assertRaises(m.Refused):run.owned()
        finally:run.close()
    def test_archive_traversal_duplicate_special_and_oversize_refuse_without_files(self):
        cases=[]
        for name,kind in [('kubernetes/../escape',tarfile.REGTYPE),('kubernetes/duplicate',tarfile.REGTYPE),('kubernetes/fifo',tarfile.FIFOTYPE)]:
            item=tarfile.TarInfo(name);item.mode=0o644;item.type=kind;item.size=0;cases.append((item,b''))
        for index,case in enumerate(cases):
            path=self.root/('bad'+str(index));dest=self.root/('dest'+str(index));dest.mkdir()
            archive(path,'kubernetes',{'duplicate':b'public'},[case])
            with self.assertRaises(m.Refused):m.extract(path,dest,'kubernetes')
            self.assertEqual([],list(dest.iterdir()))
        path=self.root/'over';archive(path,'kubernetes',{'file':b'public'})
        with mock.patch.object(m,'MAX_TREE',1):
            with self.assertRaises(m.Refused):m.extract(path,self.root,'kubernetes')
    def test_safe_makefile_link_and_escape_link_parent(self):
        path=self.root/'good';item=tarfile.TarInfo('kubernetes/Makefile');item.type=tarfile.SYMTYPE;item.linkname='build/root/Makefile';item.mode=0o777
        archive(path,'kubernetes',{'build/root/Makefile':b'public'},[(item,b'')]);dest=self.root/'dest';dest.mkdir()
        source=m.extract(path,dest,'kubernetes');self.assertEqual(b'public',(source/'Makefile').read_bytes())
        bad=self.root/'bad';item.linkname='../../escape';archive(bad,'kubernetes',{},[(item,b'')]);other=self.root/'other';other.mkdir()
        with self.assertRaises(m.Refused):m.extract(bad,other,'kubernetes')
        self.assertEqual([],list(other.iterdir()))
    def test_writable_parent_and_renewed_invalid_lease_refuse(self):
        self.root.chmod(0o777)
        with self.assertRaises(m.Refused):self.run_owned()
        self.root.chmod(0o700)
        with self.assertRaises(m.Refused):m.Run(self.root,'0123456789ab',time.monotonic()+4000)
    def test_primary_version_file_override_survives_archive_inference(self):
        run=self.run_owned()
        try:
            env=m.environment(run,self.root/'go')
            fixture=pathlib.Path(__file__).parent/'fixtures/kubectl-security-version.sh'
            self.assertEqual('b230c4b4906613899248bde9696fedf157396baf74ea804ab3bc48810ff075a5',m.sha(fixture.read_bytes()))
            reply=subprocess.run(['/bin/bash','-c','source "$1"; kube::version::get_version_vars; printf "%s\\n%s\\n%s\\n" "$KUBE_GIT_COMMIT" "$KUBE_GIT_TREE_STATE" "$KUBE_GIT_VERSION"','fixture',str(fixture)],env=env,capture_output=True,check=True)
            self.assertEqual([m.SOURCE_COMMIT,'dirty',m.CUSTOM_VERSION+'-dirty'],reply.stdout.decode().splitlines())
        finally:run.close()
    def test_expiry_during_pending_flush_prevents_dispatch_and_lease_renewal(self):
        run=self.run_owned(.05);original=run.save
        def slow(*args,**kwargs):original(*args,**kwargs);time.sleep(.06)
        try:
            with mock.patch.object(run,'save',slow),mock.patch.object(m,'spawn')as child:
                with self.assertRaises(m.Refused):run.command('fixture',['false'],{},run.path)
                child.assert_not_called()
            run.deadline+=10
            with self.assertRaises(m.Refused):run.owned()
        finally:run.close()
    def test_initial_parent_flush_failure_closes_all_descriptors(self):
        before=len(list(pathlib.Path('/proc/self/fd').iterdir()))
        with mock.patch.object(m.os,'fsync',side_effect=OSError('public injected failure')):
            with self.assertRaises(OSError):self.run_owned()
        self.assertEqual(before,len(list(pathlib.Path('/proc/self/fd').iterdir())))
    def test_actual_flat_packaging_synthetic_root_and_wrapped_refusal(self):
        path=self.root/'flat';archive(path,None,{'.generated_files':b'public','go.mod':b'public','build/root/Makefile':b'public'})
        dest=self.root/'flat-output';dest.mkdir();source=m.extract(path,dest,'kubernetes',flat=True)
        self.assertEqual(b'public',(source/'.generated_files').read_bytes());self.assertEqual(['kubernetes'],[p.name for p in dest.iterdir()])
        wrapped=self.root/'wrapped';archive(wrapped,'kubernetes',{'go.mod':b'public'});bad=self.root/'wrapped-output';bad.mkdir()
        with self.assertRaises(m.Refused):m.extract(wrapped,bad,'kubernetes',flat=True)
        self.assertEqual([],list(bad.iterdir()))
    def test_terminal_directory_symlink_retained_but_chain_refuses(self):
        directory=tarfile.TarInfo('cluster/gce/gci');directory.type=tarfile.DIRTYPE;directory.mode=0o755
        link=tarfile.TarInfo('cluster/gce/cos');link.type=tarfile.SYMTYPE;link.linkname='gci';link.mode=0o777
        path=self.root/'dir-links';archive(path,None,{'cluster/gce/gci/public.txt':b'public'},[(directory,b''),(link,b'')])
        dest=self.root/'dir-output';dest.mkdir();source=m.extract(path,dest,'kubernetes',flat=True)
        self.assertEqual('gci',os.readlink(source/'cluster/gce/cos'));self.assertEqual(b'public',(source/'cluster/gce/cos/public.txt').read_bytes())
        chain=tarfile.TarInfo('cluster/gce/ubuntu');chain.type=tarfile.SYMTYPE;chain.linkname='cos';chain.mode=0o777
        bad=self.root/'chain';archive(bad,None,{},[(directory,b''),(link,b''),(chain,b'')]);other=self.root/'chain-output';other.mkdir()
        with self.assertRaises(m.Refused):m.extract(bad,other,'kubernetes',flat=True)
        self.assertEqual([],list(other.iterdir()))
    def test_archive_public_file_modes_are_preserved_inside_private_root(self):
        path=self.root/'mode-input';archive(path,None,{'data':b'public','public.sh':b'#!/bin/bash\n'})
        dest=self.root/'mode-output';dest.mkdir(mode=0o700);source=m.extract(path,dest,'kubernetes',flat=True)
        self.assertEqual(0o700,stat.S_IMODE(source.stat().st_mode))
        self.assertEqual(0o644,stat.S_IMODE((source/'data').stat().st_mode));self.assertEqual(0o755,stat.S_IMODE((source/'public.sh').stat().st_mode))
    def test_over_one_mib_paths_sidecar_preserves_bounded_failure_receipt(self):
        run=self.run_owned(30)
        try:
            names=sorted('vendor/public/'+str(n).zfill(6)+'/'+('p'*72)for n in range(18000))
            self.assertGreater(len(json.dumps(names).encode()),1024*1024)
            before={};after={p:{'sha256':'1'*64,'bytes':1,'mode':0o644}for p in names}
            summary=m.save_diff_metadata(run,names,before,after);run.record.update(summary,phase='refused',failure='public_fixture');run.save()
            disk=json.loads((run.path/'record.json').read_text());self.assertLess((run.path/'record.json').stat().st_size,16384)
            self.assertEqual(18000,disk['changed_paths_count']);self.assertEqual('refused',disk['phase']);self.assertNotIn('changed_paths',disk)
            metadata=json.loads((run.path/'source-diff-metadata.json').read_text());self.assertEqual(names,metadata['changed_paths'])
            self.assertEqual(after,{p:v['after']for p,v in metadata['entries'].items()})
            self.assertEqual(0o600,stat.S_IMODE((run.path/'source-diff-metadata.json').stat().st_mode))
            with self.assertRaises(FileExistsError):m.save_diff_metadata(run,names,before,after)
        finally:run.close()
    def test_diff_metadata_flush_failure_retains_bounded_inspect_only_record(self):
        run=self.run_owned();original=os.fsync
        def fail(fd):
            if os.readlink('/proc/self/fd/'+str(fd)).endswith('/source-diff-metadata.json'):raise OSError('public injected fault')
            return original(fd)
        try:
            with mock.patch.object(m.os,'fsync',fail):
                with self.assertRaises(OSError):m.save_diff_metadata(run,['vendor/public'],{},{'vendor/public':{'link':'public'}})
            run.record.update(phase='refused',failure='public_fixture');run.save()
            self.assertEqual('refused',json.loads((run.path/'record.json').read_text())['phase'])
            self.assertNotIn('source_diff_metadata_sha256',json.loads((run.path/'record.json').read_text()))
            self.assertTrue((run.path/'source-diff-metadata.json').is_file())
        finally:run.close()


if __name__=='__main__':unittest.main()
