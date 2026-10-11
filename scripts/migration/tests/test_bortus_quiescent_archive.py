"""Disposable age/SQLite/filesystem and controlled Python children; no live transport."""
import base64
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import shlex
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import yaml
import test_bortus_quiescent_source as fixtures

HERE=pathlib.Path(__file__).parent
s=importlib.util.spec_from_file_location('quiescent_archive_tests',HERE.parent/'bortus-quiescent-archive.py')
m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)


def frame():
    db=sqlite3.connect(':memory:');db.execute('create table public_rows(id integer primary key,value text)')
    db.executemany('insert into public_rows values(?,?)',[(1,'PUBLIC ONE'),(2,'PUBLIC TWO')]);body=db.serialize();db.close()
    def header(obj):
        raw=json.dumps(obj).encode();return struct.pack('>I',len(raw))+raw
    return m.archive.MAGIC+header({'name':'bortus.db','size':len(body)})+body+header({'complete':True,'files':['bortus.db']})


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cert_folder=tempfile.TemporaryDirectory(prefix='quiescent-public-certs-',dir=pathlib.Path.home())
        root=pathlib.Path(cls.cert_folder.name);cls.cert=root/'cert.pem';cls.certkey=root/'key.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-subj','/CN=public-fixture',
            '-addext','subjectAltName=IP:192.168.0.4','-keyout',str(cls.certkey),'-out',str(cls.cert),'-days','1'],
            check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
    @classmethod
    def tearDownClass(cls):cls.cert_folder.cleanup()
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(prefix='quiescent-archive-public-',dir=pathlib.Path.home());self.root=pathlib.Path(self.folder.name)
        self.root.chmod(0o700);self.children=[];self.commands=[];self.patches=[];self.journal=None
        self.addCleanup(self.cleanup)
        original=pathlib.Path.home()/'.local/share/branconet-migration/bin/age'
        self.runtime=self.root/'runtime';(self.runtime/'bin').mkdir(parents=True)
        shutil.copyfile(original,self.runtime/'bin/age');(self.runtime/'bin/age').chmod(0o700)
        for name in('kubectl','ssh'):(self.runtime/'bin'/name).write_text('PUBLIC PLACEHOLDER');(self.runtime/'bin'/name).chmod(0o700)
        self.keys=self.root/'keys';self.keys.mkdir(mode=0o700);self.key=self.keys/'identity'
        subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(self.key)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
        self.pub=pathlib.Path(str(self.key)+'.pub');self.pub.chmod(0o600)
        encoded=lambda p:base64.b64encode(p.read_bytes()).decode()
        self.config=self.root/'fixture.yaml'
        value={'apiVersion':'v1','kind':'Config','clusters':[{'name':'public','cluster':{'server':m.credentials.APPROVED_ORIGIN,'certificate-authority-data':encoded(self.cert)}}],
            'contexts':[{'name':'operator@public','context':{'cluster':'public','user':'operator'}}],'current-context':'operator@public',
            'users':[{'name':'operator','user':{'client-certificate-data':encoded(self.cert),'client-key-data':encoded(self.certkey)}}]}
        self.config.write_text(yaml.safe_dump(value));self.config.chmod(0o600)
        patch=mock.patch.object(fixtures,'m',m.quiescent);patch.start();self.patches.append(patch)
        self.client,self.memory,self.op,_=fixtures.prepare()
        self.op.deadline=time.monotonic()+20;self.op.monotonic=time.monotonic
        self.journal=m.quiescent.cold.Journal(self.root/'capture-run',record=self.memory.record).open(new=True);self.op.journal=self.journal;self.op.r=self.journal.record
        self.op.create_owned('holder',self.op.r['holder_proposal'])
        self.op.r['sqlite_archive_state']='pending';self.journal.save()
        for key in m.quiescent.CONTROL_KEYS:self.client.resources[key]['spec'][m.quiescent.cold.RESOURCES[key][3]]=m.quiescent.TARGETS[key]
        holder=self.client.resources['pods']['items'][-1];self.client.resources['pods']['items']=[holder]
        self.nas=self.root/'nas';self.nas.mkdir(mode=0o700)
        self.frame=frame();self.source_mode='normal';self.nas_mode='normal'
        for obj,key,val in((m,'RUNTIME',self.runtime),(m,'spawn',self.spawn)):
            patch=mock.patch.object(obj,key,val);patch.start();self.patches.append(patch)
        self.callback=m.QuiescentArchive(m.credentials.OperatorMTLSOptions(str(self.config)),str(self.config),str(self.pub),str(self.key))
        self.fd_before=set(os.listdir('/proc/self/fd'))
    def spawn(self,args,**kwargs):
        self.commands.append((list(args),dict(kwargs)))
        if pathlib.Path(args[0]).name=='kubectl':
            self.assertIn('/proc/self/fd/',args[args.index('--kubeconfig')+1]);self.assertEqual(('-c','holder','-i','--','node','-'),tuple(args[-6:]))
            code='import base64,sys,time; program=sys.stdin.buffer.read(); '
            code+='time.sleep(30)'if self.source_mode=='hang'else'sys.stdout.buffer.write(base64.b64decode('+repr(base64.b64encode(self.frame).decode())+'))'
        else:
            self.assertEqual('ssh',pathlib.Path(args[0]).name);self.assertIn('ForwardAgent=no',args)
            public=shlex.split(args[-1]);self.assertEqual(['python3','-c'],public[:2]);code=public[2]
            code=code.replace(repr(m.NAS_ROOT),repr(str(self.nas)))
            if self.nas_mode=='fsync-fail':code=code.replace('os.fsync(target);','raise OSError();os.fsync(target);')
            elif self.nas_mode=='hang':code='import time;time.sleep(30)'
        child=subprocess.Popen([sys.executable,'-B','-c',code],**kwargs);self.children.append(child);return child
    def cleanup(self):
        failed=[]
        for child in self.children:
            try:m.Children(time.monotonic()+1)(child)
            except Exception:failed.append(True)
            for stream in(child.stdin,child.stdout,child.stderr):
                if stream and not stream.closed:stream.close()
        for patch in reversed(self.patches):patch.stop()
        if self.journal:self.journal.close()
        self.folder.cleanup();self.assertFalse(failed)
        self.assertTrue(all(c.poll()is not None for c in self.children))
    def execute(self):return self.callback(self.op,self.op.deadline)
    def test_actual_age_authenticated_public_sqlite_and_exclusive_same_inode_nas(self):
        result=self.execute();self.assertEqual({'artifact','ciphertext_sha256','files','plaintext_bytes','authenticated_decryption_equal','plaintext_persisted','sqlite_integrity_or_row_preservation_proven','nas_artifact','nas_ciphertext_equal'},set(result))
        self.assertTrue(result['authenticated_decryption_equal']);self.assertTrue(result['nas_ciphertext_equal']);self.assertFalse(result['plaintext_persisted'])
        local=pathlib.Path(result['artifact']);remote=self.nas/pathlib.Path(result['nas_artifact']).name
        self.assertEqual(local.read_bytes(),remote.read_bytes());self.assertEqual(result['ciphertext_sha256'],hashlib.sha256(remote.read_bytes()).hexdigest())
        self.assertEqual(0o600,remote.stat().st_mode&0o777);self.assertTrue(all(c.poll()is not None for c in self.children))
        self.assertEqual(self.fd_before,set(os.listdir('/proc/self/fd')))
        for args,kwargs in self.commands:
            self.assertNotIn(m.archive.NODE_READER,args);self.assertNotIn(self.key.read_text(),repr(args));self.assertEqual(subprocess.DEVNULL,kwargs['stderr'])
    def test_same_callback_never_retries(self):
        self.execute();count=len(self.commands)
        with self.assertRaises(m.Refused):self.execute()
        self.assertEqual(count,len(self.commands))
    def test_expired_deadline_before_any_child(self):
        self.op.deadline=time.monotonic()-1
        with self.assertRaises(m.Refused):self.execute()
        self.assertFalse(self.commands)
    def test_reader_deadline_reaps_owned_child_no_nas(self):
        self.source_mode='hang';self.op.deadline=time.monotonic()+.3;start=time.monotonic()
        with self.assertRaises(m.Refused):self.execute()
        self.assertLess(time.monotonic()-start,.65);self.assertEqual(1,len(self.commands));self.assertTrue(all(c.poll()is not None for c in self.children))
    def test_nas_deadline_refuses_retains_cipher_and_reaps(self):
        self.nas_mode='hang';self.op.deadline=time.monotonic()+.4;start=time.monotonic()
        with self.assertRaises(m.Refused):self.execute()
        self.assertLess(time.monotonic()-start,.75);self.assertTrue((self.journal.directory/'sqlite-files.age').exists());self.assertTrue(all(c.poll()is not None for c in self.children))
    def test_nas_existing_file_never_overwritten(self):
        target=self.nas/('bortus-sqlite-'+self.op.r['run_id']+'.age');target.write_bytes(b'PUBLIC PREEXISTING CIPHER');target.chmod(0o600)
        with self.assertRaises(m.Refused):self.execute()
        self.assertEqual(b'PUBLIC PREEXISTING CIPHER',target.read_bytes())
    def test_nas_fsync_failure_never_confirms(self):
        self.nas_mode='fsync-fail'
        with self.assertRaises(m.Refused):self.execute()
        self.assertEqual('pending',self.op.r['sqlite_archive_state']);self.assertTrue(list(self.nas.iterdir()))
    def test_holder_imageid_drift_no_dispatch(self):
        self.client.resources['pods']['items'][0]['status']['containerStatuses'][0]['imageID']='sha256:config-is-not-runtime'
        with self.assertRaises(m.Refused):self.execute()
        self.assertFalse(self.commands)
    def test_holder_uid_replacement_no_dispatch(self):
        self.client.resources['pods']['items'][0]['metadata']['uid']='replacement'
        with self.assertRaises(m.Refused):self.execute()
        self.assertFalse(self.commands)
    def test_post_reader_source_failure_no_nas(self):
        original=self.op.source;calls=[]
        def drift(**kwargs):
            calls.append(1)
            if len(calls)>=3:raise RuntimeError('PRIVATE_SOURCE_VALUE')
            return original(**kwargs)
        self.op.source=drift
        with self.assertRaises(m.Refused)as caught:self.execute()
        self.assertNotIn('PRIVATE_SOURCE_VALUE',str(caught.exception));self.assertEqual(1,len(self.commands));self.assertTrue(all(c.poll()is not None for c in self.children))
    def test_unsafe_key_mode_and_symlink_no_dispatch(self):
        self.pub.chmod(0o644)
        with self.assertRaises(m.Refused):self.execute()
        self.assertFalse(self.commands)
    def test_key_inode_replacement_during_encryption_refuses_before_nas(self):
        original=m.archive.encrypt_source
        def replaced(*args,**kwargs):
            result=original(*args,**kwargs);replacement=self.keys/'replacement';replacement.write_bytes(self.pub.read_bytes());replacement.chmod(0o600);os.replace(replacement,self.pub);return result
        with mock.patch.object(m.archive,'encrypt_source',side_effect=replaced),self.assertRaises(m.Refused):self.execute()
        self.assertEqual(1,len(self.commands))
    def test_cipher_inode_replacement_during_copy_refuses(self):
        original=m.copy_nas
        def replaced(cipher,*args):
            result=original(cipher,*args);p=cipher.path.with_name('replacement.age');p.write_bytes(cipher.path.read_bytes());p.chmod(0o600);os.replace(p,cipher.path);return result
        with mock.patch.object(m,'copy_nas',side_effect=replaced),self.assertRaises(m.Refused):self.execute()
    def test_cleanup_callback_on_success_and_error_all_owned_handles(self):
        original=m.archive.encrypt_source;seen=[]
        def controlled(*args,**kwargs):
            cb=kwargs['cleanup']
            def observe(child):
                if child:seen.append(child)
                cb(child)
            kwargs['cleanup']=observe;return original(*args,**kwargs)
        with mock.patch.object(m.archive,'encrypt_source',side_effect=controlled):self.execute()
        self.assertEqual(3,len(seen));self.assertTrue(all(c.poll()is not None for c in seen))
    def test_optional_cleanup_error_still_closes_other_crypto_children(self):
        original=m.archive.encrypt_source;seen=[]
        def controlled(*args,**kwargs):
            cb=kwargs['cleanup']
            def fault(child):
                if child:seen.append(child)
                cb(child)
                if child is args[0]:raise OSError('PUBLIC_CLEANUP_FAULT')
            kwargs['cleanup']=fault;return original(*args,**kwargs)
        with mock.patch.object(m.archive,'encrypt_source',side_effect=controlled),self.assertRaises(m.Refused):self.execute()
        self.assertEqual(3,len(seen));self.assertTrue(all(c.poll()is not None for c in seen));self.assertEqual(1,len(self.commands))
    def test_expired_cleanup_only_owned_session_not_unrelated_child(self):
        owned=subprocess.Popen([sys.executable,'-B','-c','import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)'],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        other=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(30)'],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.children.extend([owned,other]);start=time.monotonic();m.Children(time.monotonic()-.001)(owned)
        self.assertLess(time.monotonic()-start,.3);self.assertIsNotNone(owned.poll());self.assertIsNone(other.poll())
    def test_fifo_and_group_writable_key_parent_refuse(self):
        fifo=self.keys/'fifo';os.mkfifo(fifo,0o600)
        with self.assertRaises(m.Refused):m.Pin(fifo,65536)
        self.keys.chmod(0o770)
        with self.assertRaises(m.Refused):m.Pin(self.pub,65536)
    def test_optional_callback_error_path_invoked_and_child_reaped(self):
        self.frame=b'INVALID_FRAME';seen=[];original=m.archive.encrypt_source
        def controlled(*args,**kwargs):
            cb=kwargs['cleanup']
            def observe(child):
                if child:seen.append(child)
                cb(child)
            kwargs['cleanup']=observe;return original(*args,**kwargs)
        with mock.patch.object(m.archive,'encrypt_source',side_effect=controlled),self.assertRaises(m.Refused):self.execute()
        self.assertGreaterEqual(len(seen),1);self.assertTrue(all(c.poll()is not None for c in seen));self.assertEqual(1,len(self.commands))

if __name__=='__main__':unittest.main(verbosity=2)
