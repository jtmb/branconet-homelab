"""One actual shared-class watch/archive graph; public local fixtures only."""
import base64,copy,hashlib,importlib.util,json,os,pathlib,shlex,sqlite3,struct,subprocess,sys,tempfile,time,unittest
from unittest import mock
import yaml
import test_bortus_quiescent_source as f
import test_bortus_quiescent_watch as wf
import test_bortus_quiescent_archive as af
m=af.m;w=wf.m

@unittest.skipUnless(os.name=='posix','actual POSIX/mTLS/age required')
class Combined(unittest.TestCase):
 def test_shared_graph_real_watch_archive_schema_and_closure(self):
  children=[];observer=server=journal=None
  with tempfile.TemporaryDirectory(prefix='quiescent-combined-',dir=pathlib.Path.home())as folder:
   root=pathlib.Path(folder);root.chmod(0o700);cert=root/'cert';key=root/'certkey'
   subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:192.168.0.4','-keyout',str(key),'-out',str(cert),'-days','1'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
   keys=root/'keys';keys.mkdir(mode=0o700);identity=keys/'identity'
   subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(identity)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
   public=pathlib.Path(str(identity)+'.pub');public.chmod(0o600)
   enc=lambda p:base64.b64encode(p.read_bytes()).decode()
   config=root/'config';config.write_text(yaml.safe_dump({'apiVersion':'v1','kind':'Config','clusters':[{'name':'public','cluster':{'server':m.credentials.APPROVED_ORIGIN,'certificate-authority-data':enc(cert)}}],'contexts':[{'name':'public','context':{'cluster':'public','user':'public'}}],'current-context':'public','users':[{'name':'public','user':{'client-certificate-data':enc(cert),'client-key-data':enc(key)}}]}));config.chmod(0o600)
   c,memory,old,_=f.prepare();c.trace=None
   objects={k:copy.deepcopy(c.resources[k])for k in w.SCOPES}
   for k,o in objects.items():o.update(apiVersion=w.SCOPES[k][0],kind=w.SCOPES[k][1])
   server=wf.Fixture(cert,key,objects);self.addCleanup(server.close)
   calls=[0]
   def options():
    import ssl
    calls[0]+=1;ctx=ssl.create_default_context(cafile=str(cert));ctx.minimum_version=ssl.TLSVersion.TLSv1_2;ctx.load_cert_chain(cert,key)
    return ctx,{'Authorization':'Bearer PUBLIC_ROTATION_'+str(calls[0])}
   deadline=time.monotonic()+20
   journal=w.ControlJournal(root/'run',copy.deepcopy(memory.record)).open(new=True);self.addCleanup(journal.close)
   observer=w.Observer(journal,old.pins,w.TLSControls(options,server.origin),deadline=deadline);self.addCleanup(observer.close);observer.start()
   callback=m.QuiescentArchive(m.credentials.OperatorMTLSOptions(str(config)),str(config),str(public),str(identity),quiescent_module=w.quiescent)
   op=w.quiescent.QuiescentCheckpoint(c,journal,observer.trace,old.qualify,callback,deadline=deadline)
   self.assertIs(type(op),callback.quiescent.QuiescentCheckpoint)
   # Default callers retain their strict graph and refuse this separately loaded class.
   default=m.QuiescentArchive(m.credentials.OperatorMTLSOptions(str(config)),str(config),str(public),str(identity))
   journal.record['sqlite_archive_state']='pending';journal.save()
   with self.assertRaises(m.Refused):default(op,deadline)
   self.assertFalse(default.attempted)
   op.create_owned('holder',op.r['holder_proposal'])
   original_change=c.change
   def change(kind,name,ns,patch):
    reply=original_change(kind,name,ns,patch);full=copy.deepcopy(reply);full.update(apiVersion=w.SCOPES[kind][0],kind=w.SCOPES[kind][1]);server.send(kind,full);return reply
   c.change=change
   for k in('kustomization','helmrelease','deployment'):
    oldvalue=op.r['controls'][k]['original']
    if oldvalue!=w.quiescent.TARGETS[k]:op.control(k,oldvalue,w.quiescent.TARGETS[k])
   c.get('pods');c.get('pods');op.source(stopped=True,holder=True)
   manifest=json.loads((pathlib.Path(__file__).parent.parent/'schema-current-writer-v1/migration-manifest.json').read_bytes());manifest['legacy_image']=f.LEGACY
   db=sqlite3.connect(':memory:')
   frontend=pathlib.Path(__file__).resolve().parents[3]/'k8s-rewrite/front-end/prisma/migrations'
   for item in manifest['migrations']:db.executescript((frontend/item['name']/'migration.sql').read_text())
   db.execute('CREATE TABLE _prisma_migrations(migration_name TEXT,checksum TEXT,finished_at TEXT,rolled_back_at TEXT)')
   db.executemany('INSERT INTO _prisma_migrations VALUES(?,?,?,?)',[(v['name'],v['checksum'],'PUBLIC COMPLETE',None)for v in manifest['migrations']]);db.commit();body=db.serialize();db.close()
   header=lambda v:struct.pack('>I',len(json.dumps(v).encode()))+json.dumps(v).encode()
   frame=m.archive.MAGIC+header({'name':'bortus.db','size':len(body)})+body+header({'complete':True,'files':['bortus.db']})
   public_frame=root/'public-frame';public_frame.write_bytes(frame);public_frame.chmod(0o600)
   nas=root/'nas';nas.mkdir(mode=0o700);runtime=root/'runtime';(runtime/'bin').mkdir(parents=True)
   import shutil
   shutil.copyfile(pathlib.Path.home()/'.local/share/branconet-migration/bin/age',runtime/'bin/age');(runtime/'bin/age').chmod(0o700)
   for n in('ssh','kubectl'):(runtime/'bin'/n).write_text('PUBLIC MOCK');(runtime/'bin'/n).chmod(0o700)
   def spawn(argv,**kwargs):
    if pathlib.Path(argv[0]).name=='kubectl':code='import sys; program=sys.stdin.buffer.read(); sys.stdout.buffer.write(open('+repr(str(public_frame))+',"rb").read())'
    else:code=shlex.split(argv[-1])[2].replace(m.NAS_ROOT,str(nas))
    child=subprocess.Popen([sys.executable,'-B','-c',code],**kwargs);children.append(child);return child
   try:
    with mock.patch.object(m,'RUNTIME',runtime),mock.patch.object(m,'spawn',spawn):
     result=callback(op,deadline)
     op.r['sqlite_archive']=result;op.r['sqlite_archive_state']='confirmed';journal.save()
     self.assertTrue(result['authenticated_decryption_equal']);self.assertTrue(result['nas_ciphertext_equal'])
     op.release_holder();op.source(stopped=True);op.r['quiescent']={'state':'captured-zero'};journal.save()
     mp=root/'manifest.json';mp.write_bytes(json.dumps(manifest).encode());mh=hashlib.sha256(mp.read_bytes()).hexdigest()
     schema=callback.schema_metadata(op,mp,mh,deadline=deadline)
     receipt=json.loads(pathlib.Path(schema['schema_receipt_path']).read_bytes())
     self.assertEqual(7,schema['schema_migrations']);self.assertTrue(receipt['tmpfs_cleaned']);self.assertFalse(receipt['whole_row_preservation_proven'])
     self.assertFalse(any(n['kind']=='Pod'for n in c.resources['pods']['items']))
     self.assertTrue(all(child.poll()is not None for child in children))
     # Exact checksum failure cannot produce another accepted schema receipt.
     manifest['migrations'][0]['checksum']='0'*64;mp.write_bytes(json.dumps(manifest).encode())
     with mock.patch.object(m.normalization,'cleanup',wraps=m.normalization.cleanup)as cleaned:
      with self.assertRaises(m.Refused):callback.schema_metadata(op,mp,hashlib.sha256(mp.read_bytes()).hexdigest(),deadline=deadline)
      self.assertEqual(1,cleaned.call_count);self.assertFalse(pathlib.Path(cleaned.call_args.args[0]).exists())
     with self.assertRaises(m.Refused):callback.schema_metadata(op,mp,mh,deadline=time.monotonic()-1)
     with self.assertRaises(m.Refused):m.QuiescentArchive(m.credentials.OperatorMTLSOptions(str(config)),str(config),str(public),str(identity),quiescent_module=wf)
     self.assertEqual(1,len(list(journal.directory.glob('quiescent-schema-*.json'))))
     fifo=root/'manifest-fifo';os.mkfifo(fifo,0o600)
     with self.assertRaises(m.Refused):callback.schema_metadata(op,fifo,mh,deadline=deadline)
     observer.prerequisite()
   finally:
    for child in children:
     m.Children(deadline)(child)
     for stream in(child.stdin,child.stdout,child.stderr):
      if stream and not stream.closed:stream.close()
    self.doCleanups()
   self.assertTrue(all(not t.is_alive()for t in observer.threads.values()))

if __name__=='__main__':unittest.main(verbosity=2)
