"""Real local Python kubectl shim + disposable mTLS files, no live operations."""
import copy
import importlib.util
import json
import os
import pathlib
import sys
import time
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location('api_transport', HERE.parent / 'bortus-api-recovery-transport.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
spec = importlib.util.spec_from_file_location('api_transport_fixtures', HERE / 'test_etcd_transport.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
# Reuse the exact public tool/credential fixture construction, through the
# adapter's real exported class graph. No pin/spawn/collect methods are mocked.
fixtures.m = m.backup

SHIM = r'''
import sys,json,os,pathlib,time,base64
ROOT=pathlib.Path(__ROOT__);state_path=ROOT/'api-state.json'
state=json.loads(state_path.read_text());args=sys.argv[1:]
config=args[args.index('--kubeconfig')+1];fd=os.open(config,os.O_RDONLY);raw=os.read(fd,65537);os.close(fd)
assert raw and '--request-timeout=' in str(args)
args=args[3:];records=state.setdefault('argv',[]);records.append(args)
state_path.write_text(json.dumps(state));body=sys.stdin.buffer.read()
mode=state.get('mode','normal')
if mode=='hang':time.sleep(30)
if mode=='exit':raise SystemExit(1)
def emit(obj):print(json.dumps(obj,separators=(',',':')))
def save():state_path.write_text(json.dumps(state))
def statuses(obj):
 if obj['kind']!='Pod':return
 obj['status']={'phase':'Running'}
 for src,key in [('initContainers','initContainerStatuses'),('containers','containerStatuses'),('ephemeralContainers','ephemeralContainerStatuses')]:
  obj['status'][key]=[{'name':c['name'],'image':c['image'],'imageID':c['image'],'restartCount':0,'ready':True,'state':({'terminated':{'exitCode':0}}if src=='initContainers'else{'running':{}})}for c in obj['spec'].get(src,[])]
if args[0]=='exec':
 command=args[args.index('--')+1:]
 if '--bundle' in command:
  import struct
  assert body[:17]==b'BORTUS-API-PROOF\0' and len(body)>21
  pos=21;lengths=[]
  for i in range(9):
   n,length=struct.unpack('>BI',body[pos:pos+5]);pos+=5;assert n==i+1
   lengths.append(length);assert body[pos:pos+length]==bytes([65+i])*length;pos+=length
  assert body[pos:]==b'\0';state['lengths']=lengths;save()
  emit({'abi':1,'scope':'isolated memory bundle only','files':9,'complete':True,'plaintext_persisted_outside_memory':False,'overall_acceptance':False})
 elif '--oracle' in command:
  assert body[:17]==b'BORTUS-API-PROOF\0' and len(body)==21
  emit({'abi':1,'scope':'isolated retained-snapshot API Secret recovery only','secret_count':1,'complete_ciphertext_map_unchanged':True,'independent_aescbc_protobuf_api_map_equal':True,'tls_verified':True,'plaintext_or_plaintext_hash_returned':False,'production_current_values_read':False,'full_control_plane_or_longhorn_recovery':False,'overall_acceptance':False})
 elif command[:2]==['node','-e']:
  assert body[:17]==b'BORTUS-API-PROOF\0' and len(body)==21
  emit({'abi':1,'ready':True,'tls_verified':True,'whole_operation_lease_renewed':False,'overall_acceptance':False})
 elif command[0]=='etcdutl' and 'status' in command:
  emit({'hash':3,'revision':7,'totalKey':1,'totalSize':state['lengths'][8]-32,'version':'3.7.0'})
 elif command[0]=='etcdutl':
  print('PUBLIC PRIVATE RESTORE OUTPUT')
 elif command[0]=='etcd':time.sleep(30)
 elif command[0]=='etcdctl':
  emit({'header':{'revision':'7'},'count':'1','more':False,'kvs':[{'key':base64.b64encode(b'/registry/secrets/public/public').decode(),'value':base64.b64encode(b'PUBLIC CIPHER').decode()}]})
 else:raise SystemExit(1)
else:
 resources=state.setdefault('resources',{})
 if args[0]=='create':
  obj=json.loads(body);kind=obj['kind'];assert kind not in resources
  obj['metadata'].update(uid='uid-'+kind,resourceVersion='rv-1');statuses(obj);resources[kind]=obj;save()
  if mode=='lost':raise SystemExit(1)
  emit(obj)
 elif args[0]=='replace':
  obj=json.loads(body);old=resources['Pod'];assert obj['metadata']['uid']==old['metadata']['uid'] and obj['metadata']['resourceVersion']==old['metadata']['resourceVersion']
  assert args[2].endswith('/ephemeralcontainers');obj['metadata']['labels']=old['metadata']['labels'];obj['metadata']['resourceVersion']='rv-2';statuses(obj);resources['Pod']=obj;save();emit(obj)
 elif args[0]=='delete':
  obj=json.loads(body);path=args[2];kind=('Pod'if '/pods/'in path else'ConfigMap'if '/configmaps/'in path else'NetworkPolicy');old=resources[kind]
  assert obj['preconditions']=={k:old['metadata'][k]for k in('uid','resourceVersion')};del resources[kind];save();emit({'apiVersion':'v1','kind':'Status','status':'Success','details':{'name':old['metadata']['name'],'uid':old['metadata']['uid'],'kind':path.rsplit('/',2)[1]}})
 elif args[0]=='get':
  if '--raw'in args:
   path=args[2];kind=('Pod'if '/pods'in path else'ConfigMap'if '/configmaps'in path else'NetworkPolicy')
   if path.endswith(('pods','configmaps','networkpolicies')):
    emit({'apiVersion':'networking.k8s.io/v1'if kind=='NetworkPolicy'else'v1','kind':kind+'List','metadata':{'resourceVersion':'opaque:list'},'items':list(resources.values())if state.get('badlist')else[resources[kind]]if kind in resources else[]})
   else:emit(resources[kind])
  else:
   kind={'pod':'Pod','networkpolicy':'NetworkPolicy','configmap':'ConfigMap'}[args[1]]
   if kind in resources:emit(resources[kind])
 else:raise SystemExit(1)
'''


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.Tests.setUpClass.__func__(cls)

    write_tool = fixtures.Tests.write_tool
    state_mode = fixtures.Tests.state_mode
    transport = fixtures.Tests.transport

    def setUp(self):
        fixtures.Tests.setUp(self)
        self.api_state = self.root / 'api-state.json'
        self.api_state.write_text(json.dumps({'mode': 'normal'}))
        self.write_tool('kubectl', SHIM.replace('__ROOT__', repr(str(self.root))))
        self.t = self.transport()
        self.backend = m.backup.Ledger(self.runtime, '123456789abc')
        self.addCleanup(self.backend.close)
        self.journal = m.RecoveryJournal(self.backend)
        self.binding = {k: 'a' * 64 for k in m.BINDINGS}
        programme = (HERE.parent / 'bortus-api-secret-proof.cjs').read_bytes().decode()
        self.a = m.APIRecoveryTransport(self.t, self.journal, programme, self.prerequisite)
        self.addCleanup(self.a.close)

    def close(self):
        fixtures.Tests.close(self)

    def prerequisite(self, action, deadline):
        self.assertEqual(self.deadline, deadline)
        return copy.deepcopy(self.binding)

    def mode(self, **kw):
        state = json.loads(self.api_state.read_text())
        state.update(kw)
        self.api_state.write_text(json.dumps(state))

    def creates(self):
        for kind in ('policy', 'configmap', 'pod'):
            self.a.create(kind)

    def test_real_graph_create_bundle_cas_oracle_conditional_cleanup(self):
        self.creates()
        parts = tuple(bytes([65 + i]) * (200224 if i == 8 else 4096) for i in range(9))
        self.a.bundle(parts)
        self.assertEqual([4096] * 8 + [200224], json.loads(self.api_state.read_text())['lengths'])
        self.assertEqual({'revision': 7, 'snapshot_bytes': 200224, 'valid': True}, self.a.snapshot_status(7, 200224))
        self.a.restore_once()
        self.a.start_etcd_once()
        before = self.a.read_cipher_map(7)
        self.a.add_api()
        self.assertEqual(before, self.a.read_cipher_map(7))
        self.a.wait_tls_ready()
        self.assertFalse(self.a.oracle_once()['overall_acceptance'])
        for kind in ('pod', 'configmap', 'policy'):
            self.a.delete_owned(kind)
        self.assertEqual({}, json.loads(self.api_state.read_text())['resources'])
        self.a.close()
        self.assertTrue(all(p.poll() is not None and (p.stdout is None or p.stdout.closed)
                            for p in self.a.owned))
        record = (self.backend.path / 'record.json').read_text()
        self.assertNotIn('PUBLIC CIPHER', record)
        self.assertNotIn('PRIVATE RESTORE', record)
        self.assertNotIn('AAAA', record)
        self.assertFalse(self.journal.r['overall_acceptance'])
        self.assertTrue(all(v['state'] == 'confirmed' for v in self.journal.r['operations'].values()))

    def test_lost_create_retains_uncertain_no_replay_no_adoption(self):
        self.mode(mode='lost')
        with self.assertRaises(m.RecoveryRefused):
            self.a.create('policy')
        self.assertEqual('uncertain', self.journal.r['operations']['policy-create']['state'])
        calls = len(self.t.jobs)
        self.mode(mode='normal')
        with self.assertRaises(m.RecoveryRefused):
            self.a.create('policy')
        self.assertEqual(calls, len(self.t.jobs))

    def test_pending_is_durable_before_real_child_dispatch(self):
        original = self.t.spawn
        def spawn(*args, **kwargs):
            record = json.loads((self.backend.path / 'record.json').read_text())
            self.assertEqual('pending', record['operations']['policy-create']['state'])
            return original(*args, **kwargs)
        with mock.patch.object(self.t, 'spawn', side_effect=spawn):
            self.a.create('policy')

    def test_fsync_before_dispatch_failure_creates_no_child(self):
        with mock.patch.object(m.backup.os, 'fsync', side_effect=OSError('PUBLIC FAULT')):
            with self.assertRaises(m.RecoveryRefused):
                self.a.create('policy')
        self.assertEqual([], self.t.jobs)

    def test_guard_binding_drift_before_and_after_dispatch(self):
        self.binding['cache_receipt_sha256'] = 'b' * 64
        with self.assertRaises(m.RecoveryRefused):
            self.a.create('policy')
        self.assertEqual([], self.t.jobs)
        self.binding['cache_receipt_sha256'] = 'a' * 64
        original = self.t.spawn
        def spawn(*args, **kwargs):
            child = original(*args, **kwargs)
            self.binding['source_receipt_sha256'] = 'c' * 64
            return child
        with mock.patch.object(self.t, 'spawn', side_effect=spawn):
            with self.assertRaises(m.RecoveryRefused):
                self.a.create('policy')
        self.assertEqual('uncertain', self.journal.r['operations']['policy-create']['state'])

    def test_zero_boolean_or_extra_prerequisite_fields_refuse(self):
        for bad in (True, {}, dict(self.binding, unexpected='a' * 64), dict(self.binding, cache_receipt_sha256=0)):
            with mock.patch.object(self.a, 'prerequisite', return_value=bad):
                with self.assertRaises(m.RecoveryRefused):
                    self.a.current()
        self.assertEqual([], self.t.jobs)

    def test_original_lease_never_renewed_and_hang_reaped(self):
        self.a.close()
        other = m.backup.Ledger(self.runtime, 'abcdef123456')
        self.addCleanup(other.close)
        self.deadline = self.t.deadline = time.monotonic() + .35
        self.journal = m.RecoveryJournal(other)
        self.a = m.APIRecoveryTransport(self.t, self.journal,
            (HERE.parent / 'bortus-api-secret-proof.cjs').read_bytes().decode(), self.prerequisite)
        self.addCleanup(self.a.close)
        self.mode(mode='hang')
        with self.assertRaises(m.RecoveryRefused):
            self.a.create('policy')
        self.assertTrue(all(p.poll() is not None for p in self.a.owned))
        self.assertEqual('uncertain', self.journal.r['operations']['policy-create']['state'])

    def test_no_policy_deletion_while_pod_present(self):
        self.creates()
        calls = len(self.t.jobs)
        with self.assertRaises(m.RecoveryRefused):
            self.a.delete_owned('policy')
        self.assertEqual(calls, len(self.t.jobs))

    def test_no_adoption_of_prior_etcd_record(self):
        other = m.backup.Ledger(self.runtime, 'abcdef123456')
        try:
            other.intent('original', {'public': True})
            with self.assertRaises(m.RecoveryRefused):
                m.RecoveryJournal(other)
            self.assertEqual(1, other.r['abi'])
        finally:
            other.close()

    def test_exact_tool_drift_and_bad_kube_origin_refuse_before_effect(self):
        config = json.loads(self.config.read_text())
        config['clusters'][0]['cluster']['server'] = 'https://not-approved.invalid'
        self.config.write_text(json.dumps(config))
        with self.assertRaises(m.RecoveryRefused):
            self.a.create('policy')
        self.assertEqual([], self.t.jobs)

    def test_private_arguments_and_reply_dropped_from_public_traceback(self):
        marker = b'PUBLIC_PRIVATE_ARGUMENT'
        try:
            self.a.bundle((marker,))
        except m.RecoveryRefused as error:
            self.assertIsNone(error.__context__)
            tb = error.__traceback__
            while tb:
                if tb.tb_frame.f_code.co_filename == m.__file__:
                    self.assertNotIn('PUBLIC_PRIVATE_ARGUMENT', repr(tb.tb_frame.f_locals))
                tb = tb.tb_next
        else:
            self.fail('Expected refusal')

    def test_complete_list_refuses_name_uid_collision_or_explicit_wrong_headers(self):
        self.creates()
        self.mode(badlist=True)
        with self.assertRaises(m.RecoveryRefused):
            self.a.delete_owned('pod')
        self.assertEqual('uncertain', self.journal.r['operations']['pod-delete']['state'])

    def test_deadline_extension_refuses_before_dispatch(self):
        self.t.deadline += 1
        with self.assertRaises(m.RecoveryRefused):
            self.a.create('policy')
        self.assertEqual([], self.t.jobs)

    def test_fresh_uid_spec_drift_and_snapshot_size_refuse(self):
        self.creates()
        parts = tuple(bytes([65 + i]) * (544 if i == 8 else 128) for i in range(9))
        self.a.bundle(parts)
        with self.assertRaises(m.RecoveryRefused):
            self.a.snapshot_status(7, 1056)
        state = json.loads(self.api_state.read_text())
        state['resources']['Pod']['metadata']['uid'] = 'foreign-uid'
        self.api_state.write_text(json.dumps(state))
        with self.assertRaises(m.RecoveryRefused):
            self.a.snapshot_status(7, 544)


if __name__ == '__main__':
    unittest.main()
