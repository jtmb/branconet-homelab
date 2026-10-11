"""Real local TLS observer and owned public Python children; no kubectl/API dispatch."""
import base64
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import ssl
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import yaml
import test_bortus_quiescent_source as f
import test_bortus_quiescent_watch as wf

spec=importlib.util.spec_from_file_location('interval_test',pathlib.Path(__file__).parents[1]/'bortus-quiescent-interval.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
w=m.watch


@unittest.skipUnless(os.name=='posix','actual POSIX/TLS/owned children required')
class IntervalTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.certificates=tempfile.TemporaryDirectory(prefix='interval-public-',dir=pathlib.Path.home())
  cls.certroot=pathlib.Path(cls.certificates.name);cls.certroot.chmod(0o700)
  cls.cert=cls.certroot/'cert';cls.key=cls.certroot/'key'
  subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=localhost',
   '-addext','subjectAltName=DNS:localhost,IP:192.168.0.4','-keyout',str(cls.key),'-out',str(cls.cert)],
   check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
 @classmethod
 def tearDownClass(cls):cls.certificates.cleanup()
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory(prefix='interval-owned-',dir=pathlib.Path.home())
  self.root=pathlib.Path(self.folder.name);self.root.chmod(0o700)
  self.fixture_client,memory,old,_=f.prepare();self.record=copy.deepcopy(memory.record)
  self.objects={k:copy.deepcopy(self.fixture_client.resources[k])for k in w.SCOPES}
  for k,o in self.objects.items():o.update(apiVersion=w.SCOPES[k][0],kind=w.SCOPES[k][1])
  self.fixture=wf.Fixture(self.cert,self.key,self.objects)
  self.journal=w.ControlJournal(self.root/'run',self.record).open(new=True)
  self.deadline=time.monotonic()+(.75 if 'hang_' in self._testMethodName or 'descendant_' in self._testMethodName else 5)
  def options():
   context=ssl.create_default_context(cafile=str(self.cert));context.minimum_version=ssl.TLSVersion.TLSv1_2
   context.load_cert_chain(self.cert,self.key);return context,{}
  self.observer=w.Observer(self.journal,old.pins,w.TLSControls(options,self.fixture.origin),deadline=self.deadline)
  self.observer.start();self.client=m.IntervalClient(self.observer,deadline=self.deadline)
  self.runtime=self.root/'runtime';(self.runtime/'bin').mkdir(parents=True,mode=0o700)
  self.runtime.chmod(0o755);(self.runtime/'bin/kubectl').write_text('PUBLIC MOCK')
  enc=lambda p:base64.b64encode(p.read_bytes()).decode()
  config={'apiVersion':'v1','kind':'Config','clusters':[{'name':'public','cluster':{'server':'https://192.168.0.4:6443','certificate-authority-data':enc(self.cert)}}],
   'contexts':[{'name':'public','context':{'cluster':'public','user':'public'}}],'current-context':'public',
   'users':[{'name':'public','user':{'client-certificate-data':enc(self.cert),'client-key-data':enc(self.key)}}]}
  (self.runtime/'admin.conf').write_text(yaml.safe_dump(config));(self.runtime/'admin.conf').chmod(0o600)
  self.children=[];self.dispatches=[];self.reply=self.objects['deployment'];self.mode='normal';self.after_spawn=None;self.auto_reply=False
  self.patch_runtime=mock.patch.object(m,'RUNTIME',self.runtime);self.patch_runtime.start()
  self.patch_spawn=mock.patch.object(m,'spawn',self.spawn);self.patch_spawn.start()
 def tearDown(self):
  self.patch_spawn.stop();self.patch_runtime.stop()
  self.client.close();self.observer.close();self.fixture.close();self.journal.close()
  self.assertTrue(all(p.poll()is not None for p in self.children));self.folder.cleanup()
 def spawn(self,argv,**kw):
  self.dispatches.append((argv,kw.copy(),copy.deepcopy(self.client.state)))
  if self.auto_reply:
   args=argv[4:]
   if args[1]=='--raw':kind='pvs' if 'persistentvolumes' in args[2] else 'pods';name=None;ns=None if kind=='pvs' else 'bortus'
   else:kind,name=args[1:3];ns=args[args.index('-n')+1]if '-n'in args else None
   self.reply=copy.deepcopy(self.fixture_client.get(kind,name,ns))
   if kind in self.objects:self.reply=copy.deepcopy(self.objects[kind])
  replyfile=self.root/('reply-'+str(len(self.dispatches))+'.json');replyfile.write_text(json.dumps(self.reply))
  if self.mode=='hang':code='import time;time.sleep(30)'
  elif self.mode=='overflow':code='import sys;sys.stdin.buffer.read();sys.stdout.buffer.write(b"x"*(8*1024*1024+1))'
  elif self.mode=='exit':code='import sys;sys.exit(2)'
  elif self.mode=='descendant':
   code='import subprocess,sys;subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);sys.exit(0)'
  else:code='import sys;sys.stdin.buffer.read();sys.stdout.buffer.write(open('+repr(str(replyfile))+',"rb").read())'
  p=subprocess.Popen([sys.executable,'-B','-c',code],**kw);self.children.append(p)
  if self.after_spawn:self.after_spawn()
  return p
 def pending_change(self):
  r=self.journal.record;old=copy.deepcopy(self.objects['deployment'])
  rv=old['metadata']['resourceVersion'];r['controls']['deployment']['intent']={'state':'pending','from':1,'to':0,'resourceVersion':rv};self.journal.save()
  patch=m.cold.cas_patch(old,r['controls']['deployment']['identity'],'replicas',1,0)
  self.reply=copy.deepcopy(old);self.reply['spec']['replicas']=0;self.reply['metadata']['resourceVersion']='opaque-later'
  self.after_spawn=lambda:self.fixture.send('deployment',self.reply)
  return patch
 def test_real_graph_bounded_get_and_stdin_cas(self):
  self.assertIsInstance(self.client,w.quiescent.cold.Client)
  self.assertEqual(self.objects['deployment'],self.client.get('deployment','bortus','bortus'))
  patch=self.pending_change();self.assertEqual(0,self.client.change('deployment','bortus','bortus',patch)['spec']['replicas'])
  argv,kw,state=self.dispatches[-1]
  self.assertEqual('pending',state['dispatches'][-1]['state'])
  disk=json.loads((self.journal.directory/'interval-client.json').read_bytes())
  self.assertEqual('confirmed',disk['dispatches'][-1]['state'])
  self.assertTrue(kw['start_new_session']);self.assertEqual(subprocess.DEVNULL,kw['stderr'])
  self.assertEqual(subprocess.PIPE,kw['stdin']);self.assertNotIn(json.dumps(patch),repr(argv))
  fd=int(argv[argv.index('--kubeconfig')+1].split('/')[-1]);self.assertIn(fd,kw['pass_fds'])
  with self.assertRaises(OSError):os.fstat(fd)
  with self.assertRaises(m.Refused):self.client.change('deployment','bortus','bortus',patch)
  self.assertEqual(2,len(self.dispatches))
  # Changing the pending RV/proposal cannot replay the already dispatched stop.
  r=self.journal.record;r['controls']['deployment']['intent']['resourceVersion']='opaque-later';self.journal.save()
  patch[1]['value']='opaque-later'
  with self.assertRaises(m.Refused):self.client.change('deployment','bortus','bortus',patch)
  self.assertEqual(2,len(self.dispatches))
 def test_deadline_mismatch_and_scope_refuse_without_dispatch(self):
  with self.assertRaises(m.Refused):m.IntervalClient(self.observer,deadline=self.deadline+1)
  for args in [('secrets','private','bortus'),('pods',None,'other'),('deployment','foreign','bortus')]:
   with self.assertRaises(m.Refused):self.client.get(*args)
  with self.assertRaises(m.Refused):self.client.request(['arbitrary'],{'PRIVATE':'VALUE'})
  self.assertFalse(self.dispatches)
 def test_missing_pending_and_bad_cas_refuse(self):
  with self.assertRaises(m.Refused):self.client.change('deployment','bortus','bortus',[])
  patch=self.pending_change();patch[1]['value']='changed'
  with self.assertRaises(m.Refused):self.client.change('deployment','bortus','bortus',patch)
  self.assertFalse(self.dispatches)
  patch=self.pending_change();patch[-1]['value']=False
  with self.assertRaises(m.Refused):self.client.change('deployment','bortus','bortus',patch)
  self.assertFalse(self.dispatches)
 def test_owned_pending_fsync_failure_prevents_child(self):
  patch=self.pending_change()
  with mock.patch.object(m.os,'fsync',side_effect=OSError('PRIVATE')):
   with self.assertRaises(m.Refused):self.client.change('deployment','bortus','bortus',patch)
  self.assertFalse(self.dispatches)
 def test_live_failure_before_dispatch_and_after_reply(self):
  patch=self.pending_change();self.after_spawn=lambda:self.observer._fail('fixture_failure')
  with self.assertRaises(m.Refused):self.client.change('deployment','bortus','bortus',patch)
  self.assertEqual('uncertain',json.loads((self.journal.directory/'interval-client.json').read_bytes())['dispatches'][-1]['state'])
  with self.assertRaises(m.Refused):self.client.get('deployment','bortus','bortus')
  self.assertEqual(1,len(self.dispatches))
 def test_actual_hang_uses_original_lease_and_reaps_group(self):
  self.mode='hang'
  start=time.monotonic()
  with self.assertRaises(m.Refused):self.client.get('deployment','bortus','bortus')
  self.assertLess(time.monotonic()-start,1);self.assertIsNotNone(self.children[0].poll())
 def test_exited_parent_descendant_pipe_is_bounded_owned_closed(self):
  self.mode='descendant'
  with self.assertRaises(m.Refused):self.client.get('deployment','bortus','bortus')
  self.assertIsNotNone(self.children[0].poll())
  with self.assertRaises(ProcessLookupError):os.killpg(self.children[0].pid,0)
 def test_output_bound_and_early_exit_close(self):
  for mode in ('overflow','exit'):
   self.mode=mode
   with self.assertRaises(m.Refused):self.client.get('deployment','bortus','bortus')
   self.assertIsNotNone(self.children[-1].poll())
 def test_sidecar_reopen_replacement_and_closed_client_refuse(self):
  with self.assertRaises(m.Refused):m.IntervalClient(self.observer,deadline=self.deadline)
  (self.journal.directory/'interval-client.json').write_text('{}')
  with self.assertRaises(m.Refused):self.client.get('deployment','bortus','bortus')
  self.client.close()
  with self.assertRaises(m.Refused):self.client.get('deployment','bortus','bortus')
  self.assertFalse(self.dispatches)
 def test_holder_fresh_rv_and_delete_intent(self):
  holder=copy.deepcopy(self.journal.record['holder_proposal']);holder['metadata'].update(uid='holder-public',resourceVersion='fresh-rv')
  self.reply=holder;self.journal.record['holder_identity']=m.cold.identity(holder)|{'resourceVersion':'creation-rv'}
  self.journal.record['holder_delete_intent']={'identity':m.cold.identity(holder),'state':'pending'};self.journal.save()
  self.assertEqual(holder,self.client.delete_holder(holder));self.assertEqual(2,len(self.dispatches))
  with self.assertRaises(m.Refused):self.client.delete_holder(holder)
  self.assertEqual(3,len(self.dispatches)) # Fresh read allowed; delete never repeats.
 def test_create_owned_proposal_and_bad_reply_uncertain(self):
  r=self.journal.record;r['holder_create_state']='pending';self.journal.save()
  self.reply=copy.deepcopy(r['holder_proposal']);self.reply['metadata'].update(uid='owned-public',resourceVersion='rv')
  self.assertEqual(self.reply,self.client.create(r['holder_proposal']))
  with self.assertRaises(m.Refused):self.client.create(r['holder_proposal'])
  self.assertEqual(1,len(self.dispatches))
 def test_rotation_wrong_permissions_refuses_before_child(self):
  (self.runtime/'admin.conf').chmod(0o644)
  with self.assertRaises(m.Refused):self.client.get('deployment','bortus','bortus')
  self.assertFalse(self.dispatches)
 def test_inherited_ready_inspect_uses_bounded_reads_only_before_stop(self):
  self.auto_reply=True
  report=self.client.inspect('bortus-data-uid')
  self.assertTrue(report['checks_passed']);self.assertEqual(10,len(self.dispatches))
  self.assertTrue(all(e['action']=='read'and e['state']=='confirmed'for e in self.client.state['dispatches']))
 def test_changed_create_reply_keeps_uncertainty(self):
  r=self.journal.record;r['holder_create_state']='pending';self.journal.save()
  self.reply=copy.deepcopy(r['holder_proposal']);self.reply['metadata'].update(name='foreign',uid='public',resourceVersion='rv')
  with self.assertRaises(m.Refused):self.client.create(r['holder_proposal'])
  self.assertEqual('uncertain',self.client.state['dispatches'][-1]['state'])
  with self.assertRaises(m.Refused):self.client.create(r['holder_proposal'])
  self.assertEqual(1,len(self.dispatches))
 def test_absolute_lease_cannot_be_renewed(self):
  self.client.deadline=self.observer.deadline=self.deadline+10
  with self.assertRaises(m.Refused):self.client.get('deployment','bortus','bortus')
  self.assertFalse(self.dispatches)
 def test_in_memory_pending_is_not_durable_authority(self):
  r=self.journal.record;old=self.objects['deployment']
  r['controls']['deployment']['intent']={'state':'pending','from':1,'to':0,'resourceVersion':old['metadata']['resourceVersion']}
  patch=m.cold.cas_patch(old,r['controls']['deployment']['identity'],'replicas',1,0)
  with self.assertRaises(m.Refused):self.client.change('deployment','bortus','bortus',patch)
  self.assertFalse(self.dispatches)


if __name__=='__main__':unittest.main()
