"""Actual local process/FD controls; public shims never execute SSH/sudo/kubectl."""
import base64,copy,hashlib,importlib.util,json,os,pathlib,shlex,signal,subprocess,sys,tempfile,time,unittest
from unittest import mock
HERE=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('etcd_transport',HERE.parent/'backup-etcd.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=HERE/'public-transport-fixtures';cls.base.mkdir(mode=0o700,exist_ok=True)
        cls.cert=cls.base/'certificate.pem';cls.key=cls.base/'key.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=public-fixture','-keyout',str(cls.key),'-out',str(cls.cert)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
    def setUp(self):
        self.root=pathlib.Path(tempfile.mkdtemp(dir=self.base));self.root.chmod(0o700)
        self.runtime=self.root/'runtime';self.runtime.mkdir(mode=0o755);self.bin=self.runtime/'bin';self.bin.mkdir(mode=0o700)
        self.keys=self.root/'keys';self.keys.mkdir(mode=0o700);self.identity=self.keys/'id_ed25519';self.identity.write_bytes(b'PUBLIC PINNED KEY FIXTURE');self.identity.chmod(0o600)
        self.proof=self.root/'proof';self.proof.mkdir(mode=0o700);self.state=self.root/'state.json';self.state.write_text(json.dumps({'sudo':'consume','kube':'normal'}))
        self.sources={};self.tools={};self.deadline=time.monotonic()+8;self.transports=[]
        self.write_tool('age','import sys;sys.stdin.buffer.read();print("PUBLIC AGE SHIM")')
        self.write_tool('kubectl',f'''import sys,json,os,time,pathlib
state=json.loads(pathlib.Path({str(self.state)!r}).read_text());args=sys.argv[1:]
path=args[args.index('--kubeconfig')+1];fd=os.open(path,os.O_RDONLY);raw=os.read(fd,65537);os.close(fd)
assert raw and len(raw)<=65536 and '--request-timeout=' in str(args)
if state['kube']=='hang':time.sleep(30)
if state['kube']=='malformed':print('not JSON');raise SystemExit(0)
body=sys.stdin.buffer.read();print(json.dumps({{'pinned_config':True,'body_bytes':len(body)}}))''')
        sudo=self.bin/'sudo-shim'
        sudo.write_text('#!/usr/bin/python3\n'+f'''import sys,os,json,pathlib,time
pathlib.Path({str(self.root/'sudo-job.json')!r}).write_text(json.dumps({{'pid':os.getpid(),'start_ticks':pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]}}))
state=json.loads(pathlib.Path({str(self.state)!r}).read_text());assert sys.argv[1:5]==['-S','-k','-p','']
if state['sudo']=='consume':
 line=bytearray()
 while not line.endswith(b'\\n'):line.extend(os.read(0,1))
 assert line==b'PUBLIC_SUDO_SENTINEL\\n';line=None
if state['sudo']=='exit':raise SystemExit(1)
if state['sudo']=='hang':time.sleep(30)
os.execv('/usr/bin/python3',['python3',*sys.argv[6:]])
''');sudo.chmod(0o700)
        # Exact production literals are asserted before the declared public-path/UID substitutions.
        remote=m.REMOTE.replace("pathlib.Path('/dev/shm')",f'pathlib.Path({str(self.proof)!r})').replace("pathlib.Path('/var/lib/etcd')",f'pathlib.Path({str(self.proof)!r})').replace('i.st_uid!=0','i.st_uid!=os.getuid()').replace('di.st_uid!=0','di.st_uid!=os.getuid()')
        wrapper=m.PRIVILEGED_WRAPPER.replace("['sudo','-S'",repr([str(sudo),'-S'])[:-1])
        self.ssh=self.bin/'ssh'
        sshcode=f'''import sys,os,shlex,json
args=sys.argv[1:];assert args[:12]==['-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','IdentitiesOnly=yes','-o','ForwardAgent=no','-o','ConnectTimeout=15','-i',{str(self.identity)!r}]
assert args[12:15]==['-p','2002','james@192.168.0.4'];v=shlex.split(args[15]);assert v[:2]==['python3','-c'] and v[2]=={m.PRIVILEGED_WRAPPER!r} and v[4]=={m.REMOTE!r}
request=json.loads(v[3]);state=json.loads(open({str(self.state)!r}).read());program={remote!r}
if state.get('remote')=='malformed':program=program.replace('print(json.dumps(out))',"print('PUBLIC_PRIVATE_REPLY')")
if state.get('pipe_fault'):
 program=program.replace("descriptor=r['body_pipe']","descriptor=r['body_pipe'];descriptor["+repr(state['pipe_fault'])+"]+=1")
assert 'PUBLIC_SUDO_SENTINEL' not in str(args)
os.execv('/usr/bin/python3',['python3','-c',{wrapper!r},v[3],program])'''
        self.ssh.write_text('#!/usr/bin/python3\n'+sshcode);self.ssh.chmod(0o700);self.tools['ssh']=m.sha(self.ssh.read_bytes())
        config={'apiVersion':'v1','kind':'Config','clusters':[{'name':'public','cluster':{'server':'https://192.168.0.4:6443','certificate-authority-data':base64.b64encode(self.cert.read_bytes()).decode()}}],'users':[{'name':'public','user':{'client-certificate-data':base64.b64encode(self.cert.read_bytes()).decode(),'client-key-data':base64.b64encode(self.key.read_bytes()).decode()}}],'contexts':[{'name':'operator@public','context':{'cluster':'public','user':'public'}}],'current-context':'operator@public'}
        self.config=self.runtime/'admin.conf';self.config.write_text(json.dumps(config));self.config.chmod(0o600)
        self.patches=[mock.patch.object(m,'RUNTIME',self.runtime),mock.patch.object(m,'SSH_BINARY',self.ssh),mock.patch.object(m,'SSH_IDENTITY',self.identity),mock.patch.object(m,'SSH',[str(self.ssh),*m.SSH[1:]])]
        self.patches[-1]=mock.patch.object(m,'SSH',[str(self.ssh),'-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','IdentitiesOnly=yes','-o','ForwardAgent=no','-o','ConnectTimeout=15','-i',str(self.identity),'-p','2002','james@192.168.0.4'])
        for p in self.patches:p.start();self.addCleanup(p.stop)
        self.addCleanup(self.close)
    def write_tool(self,name,code):
        p=self.bin/name;p.write_text('#!/usr/bin/python3\n'+code);p.chmod(0o700);self.tools[name]=m.sha(p.read_bytes());return p
    def transport(self):
        t=m.Transport(self.deadline,lambda:'PUBLIC_SUDO_SENTINEL',self.tools);self.transports.append(t);return t
    def close(self):
        handle=self.root/'sudo-job.json'
        if handle.exists():
            job=json.loads(handle.read_text());stat=pathlib.Path('/proc/'+str(job['pid'])+'/stat')
            if stat.exists() and stat.read_text().rsplit(')',1)[1].split()[19]==job['start_ticks']:
                try:os.killpg(job['pid'],signal.SIGKILL)
                except ProcessLookupError:pass
        for t in self.transports:
            t.close();t.close();self.assertTrue(all(j['reaped']for j in t.jobs));self.assertTrue(all('process'not in j for j in t.jobs))
    def state_mode(self,**kw):
        obj=json.loads(self.state.read_text());obj.update(kw);self.state.write_text(json.dumps(obj))
    def send(self,t,run='123456789abc',header=None,payload=b'PUBLIC RAW SNAPSHOT\0'*1024):
        r={'mode':'receive','run_id':run,'bytes':len(payload),'seconds':m.left(self.deadline)}
        p=t.remote_start(r);h={'abi':1,'mode':'receive','run_id':run,'bytes':len(payload),'sha256':m.sha(payload)}if header is None else header
        body=(h if type(h)is bytes else json.dumps(h,separators=(',',':')).encode()+b'\n')+payload
        result=m.collect(p,self.deadline,t.children,body=body);return m.decode(result),self.proof/('migration-etcd-'+run)/'snapshot.db'
    def test_consuming_and_nopasswd_have_exact_body_no_credential_prefix(self):
        t=self.transport()
        for run,mode in [('123456789abc','consume'),('abcdef123456','nopasswd')]:
            self.state_mode(sudo=mode);reply,p=self.send(t,run);self.assertEqual(b'PUBLIC RAW SNAPSHOT\0'*1024,p.read_bytes());self.assertEqual(p.stat().st_size,reply['bytes']);self.assertNotIn(b'PUBLIC_SUDO_SENTINEL',p.read_bytes())
    def test_invalid_closed_header_refuses_before_any_directory_or_file(self):
        t=self.transport();payload=b'PUBLIC RAW SNAPSHOT\0'*1024;good={'abi':1,'mode':'receive','run_id':'123456789abc','bytes':len(payload),'sha256':m.sha(payload)}
        for mode in('consume','nopasswd'):
            self.state_mode(sudo=mode)
            for key,value in [('abi',True),('run_id','abcdef123456'),('bytes',True),('extra','PUBLIC')]:
                h=dict(good);h[key]=value
                with self.assertRaises(m.Refused):self.send(t,header=h)
                self.assertEqual([],list(self.proof.iterdir()))
    def test_default_kube_fresh_real_mtls_and_inherited_config_fd(self):
        t=self.transport();obj=t.api(['get','public','-o','json'],body={'public':'body'});self.assertTrue(obj['pinned_config']);self.assertEqual(len(b'{"public":"body"}'),obj['body_bytes'])
        config=json.loads(self.config.read_text());config['clusters'][0]['cluster']['server']='https://unapproved.invalid';self.config.write_text(json.dumps(config));self.config.chmod(0o600);jobs=len(t.jobs)
        with self.assertRaises(m.Refused):t.kube(['get','public'])
        self.assertEqual(jobs,len(t.jobs))
    def test_default_kube_hang_original_lease_reaps_and_closes(self):
        self.deadline=time.monotonic()+.25;t=self.transport();self.state_mode(kube='hang')
        with self.assertRaises(m.Refused):t.kube(['get','public'])
        self.assertIsNotNone(t.jobs[0]['process'].poll());self.assertTrue(t.jobs[0]['process'].stdout.closed)
    def test_key_and_tool_inode_or_bytes_drift_no_dispatch(self):
        for kind in('key','tool'):
            t=self.transport();p=self.identity if kind=='key'else self.bin/'kubectl';original=p.read_bytes();p.write_bytes(original+b'PUBLIC DRIFT')
            with self.assertRaises(Exception):t.remote_start({'mode':'keys','run_id':'123456789abc','paths':[]})
            self.assertEqual([],t.jobs);p.write_bytes(original)
    def test_partial_constructor_failure_closes_all_owned_fds(self):
        before=len(os.listdir('/proc/self/fd'))
        with self.assertRaises(Exception):m.Transport(self.deadline,lambda:'PUBLIC',dict(self.tools,kubectl='0'*64))
        self.assertEqual(before,len(os.listdir('/proc/self/fd')))
    def test_remote_exit_and_lost_reply_cannot_qualify_body(self):
        t=self.transport();self.state_mode(sudo='exit')
        with self.assertRaises(m.Refused):self.send(t)
        self.assertEqual([],list(self.proof.iterdir()))
    def test_malformed_privileged_reply_drops_private_internal_frames(self):
        t=self.transport();self.state_mode(remote='malformed')
        try:t.remote({'mode':'keys','run_id':'123456789abc','paths':[]})
        except m.Refused as e:
            self.assertIsNone(e.__context__);tb=e.__traceback__
            while tb:
                if tb.tb_frame.f_code.co_filename==m.__file__:
                    self.assertNotIn('PUBLIC_PRIVATE_REPLY',repr(tb.tb_frame.f_locals))
                tb=tb.tb_next
        else:self.fail('Expected fixed refusal')
    def test_remote_default_keys_closed_scope_and_duplicates(self):
        t=self.transport();self.assertEqual({},t.remote({'mode':'keys','run_id':'123456789abc','paths':[]}));jobs=len(t.jobs)
        for paths in [['/etc/shadow'],['/etc/kubernetes/pki/a','/etc/kubernetes/pki/a'],['/etc/kubernetes/pki/../admin.conf']]:
            with self.assertRaises(m.Refused):t.remote_start({'mode':'keys','run_id':'123456789abc','paths':paths})
        self.assertEqual(jobs,len(t.jobs))
    def test_expired_transport_and_unbound_executable_never_dispatch(self):
        t=self.transport()
        with self.assertRaises(m.Refused):t.spawn(['/usr/bin/printf','PUBLIC'])
        t.deadline=time.monotonic()-1
        with self.assertRaises(m.Refused):t.remote_start({'mode':'keys','run_id':'123456789abc','paths':[]})
        self.assertEqual([],t.jobs)
    def test_pipe_pid_start_uid_and_fifo_identity_drift_refuse_before_effects(self):
        t=self.transport()
        for field in('pid','uid','start_ticks','pipe_dev','pipe_ino','fd'):
            self.state_mode(pipe_fault=field)
            with self.assertRaises(m.Refused):self.send(t)
            self.assertEqual([],list(self.proof.iterdir()))
    def test_duplicate_oversized_and_unterminated_headers_refuse_without_effects(self):
        t=self.transport()
        for header in(b'{"abi":1,"abi":1}\n',b'A'*1025+b'\n',b'PUBLIC NO HEADER'):
            with self.assertRaises(m.Refused):self.send(t,header=header)
            self.assertEqual([],list(self.proof.iterdir()))
    def test_atomic_key_replacement_refuses_and_never_adopts(self):
        t=self.transport();replacement=self.identity.with_name('replacement');replacement.write_bytes(b'PUBLIC NEW KEY');replacement.chmod(0o600);os.replace(replacement,self.identity)
        with self.assertRaises(Exception):t.remote_start({'mode':'keys','run_id':'123456789abc','paths':[]})
        self.assertEqual([],t.jobs)
    def test_malformed_api_reply_is_fixed_no_body_or_provider_frames(self):
        t=self.transport();self.state_mode(kube='malformed')
        try:t.api(['get','public'],body={'marker':'PUBLIC_PRIVATE_BODY'})
        except m.Refused as e:
            tb=e.__traceback__
            while tb:
                if tb.tb_frame.f_code.co_filename==m.__file__:
                    self.assertNotIn('PUBLIC_PRIVATE_BODY',repr(tb.tb_frame.f_locals))
                tb=tb.tb_next
        else:self.fail('Expected fixed refusal')
    def test_remote_hanging_sudo_original_deadline_closes_local_owned_session(self):
        self.deadline=time.monotonic()+.35;t=self.transport();self.state_mode(sudo='hang')
        with self.assertRaises(m.Refused):self.send(t)
        self.assertIsNotNone(t.jobs[0]['process'].poll());self.assertEqual([],list(self.proof.iterdir()))
        job=json.loads((self.root/'sudo-job.json').read_text());time.sleep(.05);path=pathlib.Path('/proc/'+str(job['pid'])+'/stat');self.assertFalse(path.exists()and path.read_text().rsplit(')',1)[1].split()[19]==job['start_ticks'],'Owned sudo descendant must be reaped, not merely local SSH shim')
    def test_finalization_success_has_actual_terminal_requirement_and_no_replay(self):
        ledger=m.Ledger(self.root,'123456789abc');self.addCleanup(ledger.close);ledger.intent('public',{});ledger.confirm('public')
        result=m.finalize(ledger,self.deadline,None,[]);self.assertEqual('completed',result['phase']);self.assertTrue(result['confirmation_requires_launcher_terminal0']);before=(ledger.path/'record.json').read_bytes()
        with self.assertRaises(FileExistsError):m.Ledger(self.root,'123456789abc')
        self.assertEqual(before,(ledger.path/'record.json').read_bytes())
    def test_finalization_original_expiry_is_durably_refused(self):
        ledger=m.Ledger(self.root,'123456789abc');self.addCleanup(ledger.close)
        with self.assertRaises(m.Refused):m.finalize(ledger,time.monotonic()-1,None,[])
        self.assertEqual('refused',json.loads((ledger.path/'record.json').read_text())['phase'])
    def test_finalization_postsave_expiry_requires_actual_terminal_one(self):
        ledger=m.Ledger(self.root,'123456789abc');self.addCleanup(ledger.close);deadline=time.monotonic()+1;original=ledger.save
        def save():
            original()
            if ledger.r['phase']=='completed':time.sleep(1.01)
        with mock.patch.object(ledger,'save',save):
            with self.assertRaises(m.Refused):m.finalize(ledger,deadline,None,[])
        r=json.loads((ledger.path/'record.json').read_text());self.assertEqual(1,r['actual_exit_code']);self.assertTrue(r['confirmation_requires_launcher_terminal0'])
    def test_finalization_dirflush_failure_cannot_return_completed(self):
        ledger=m.Ledger(self.root,'123456789abc');self.addCleanup(ledger.close);original=os.fsync
        def fsync(fd):
            if fd==ledger.fd and ledger.r['phase']=='completed':raise OSError('PUBLIC FSYNC FAILURE')
            return original(fd)
        with mock.patch.object(m.os,'fsync',fsync):
            with self.assertRaises(m.Refused):m.finalize(ledger,self.deadline,None,[])
        self.assertEqual(1,json.loads((ledger.path/'record.json').read_text())['actual_exit_code'])


if __name__=='__main__':unittest.main()
