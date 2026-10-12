"""Pure phase faults, actual protected files and a shared live localhost TLS graph."""
import copy, hashlib, http.server, importlib.util, json, os, pathlib, ssl, subprocess, sys, tempfile, threading, time, unittest, uuid
from unittest import mock
import test_bortus_quiescent_source as f
import test_bortus_quiescent_watch as wf

HERE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location('quiescent_phase_tests', HERE.parent/'bortus-quiescent-phase.py')
m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m)


def binding(phase='legacy-approved'):
    contract = {'namespace':'bortus','guarded_service_account':'bortus-kv',
        'protected_pvc_names':['bortus-data','bortus-restore-123456abcdef'],
        'protected_secret_names':['bortus-runtime','bortus-operator-access'],
        'approved_image_references':[f.FINAL,f.LEGACY] if phase == m.PHASES[0] else [f.FINAL]}
    renders = m.validator.reviewed_renders(contract); pins = {}
    for index, obj in enumerate(renders):
        name, kind = obj['metadata']['name'], obj['kind']; pin = pins.setdefault(name,{})
        prefix = '' if kind == m.validator.POLICY else 'binding_'
        pin[prefix+'uid'] = str(uuid.UUID(int=index+1))
        pin['resourceVersion' if not prefix else 'binding_resourceVersion'] = 'opaque-'+str(index)
        pin[prefix+'spec_sha256'] = m.sha(m.validator.canonical_spec(kind,obj['spec']))
    return {'phase':phase,'image':f.FINAL,'source_sha256':'3'*64,
        'qualification_receipt_sha256':'4'*64,'contract':contract,'policy_pins':pins}


def objects(b):
    result = m.validator.reviewed_renders(b['contract'])
    for obj in result:
        policy = obj['kind'] == m.validator.POLICY; p = b['policy_pins'][obj['metadata']['name']]
        obj['metadata'].update(uid=p['uid' if policy else 'binding_uid'],
            resourceVersion=p['resourceVersion' if policy else 'binding_resourceVersion'],generation=1)
        if policy: obj['status']={'observedGeneration':1,'typeChecking':{'expressionWarnings':[]}}
    return result


class Guards:
    def __init__(self, cert, key, responses):
        self.responses = responses; self.calls = []; owner = self
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*_): pass
            def do_GET(self):
                owner.calls.append(self.path)
                obj = next(o for o in owner.responses if self.path.endswith('/'+o['metadata']['name']) and
                    ('policybindings/' in self.path) == (o['kind'] == m.validator.BINDING))
                raw = json.dumps(obj).encode(); self.send_response(200)
                self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
                self.end_headers();self.wfile.write(raw)
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
        context.load_verify_locations(cafile=str(cert));context.verify_mode=ssl.CERT_REQUIRED
        self.server.socket=context.wrap_socket(self.server.socket,server_side=True)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01});self.thread.start()
    @property
    def origin(self): return 'https://localhost:'+str(self.server.server_port)
    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2);assert not self.thread.is_alive()


@unittest.skipUnless(os.name == 'posix', 'protected POSIX files/local TLS required')
class PhaseTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(dir=pathlib.Path.home());self.addCleanup(self.folder.cleanup)
        self.root=pathlib.Path(self.folder.name);self.root.chmod(0o700)
        self.b=binding();self.q=object.__new__(m.PhaseQualifier)
        self.q.graph=m.interval;self.q.deadline=time.monotonic()+1000
        self.q.closed=self.q.failed=self.q.active=False
        self.q.bindings={m.PHASES[0]:self.b};self.q.verify_binding=lambda b,d:copy.deepcopy(b)
        self.q.observer=mock.Mock();self.q.operation=mock.Mock()
        self.q.operation.r={'run_id':'123456abcdef','baseline':{'legacy_image':f.LEGACY,
            'protected_claim_names':self.b['contract']['protected_pvc_names'],
            'writer':{'name':'bortus-public','namespace':'bortus','uid':'public-writer'}}}
        self.q.archive_pin=self.q.cipher_pin=self.q.archive_result=self.q.archive_receipt=None
        self.q.archive=object.__new__(m.interval.archive.QuiescentArchive)
        self.q.state={'abi':1,'bindings':self.q.bindings,'calls':[],'archive_schema':None,'overall_acceptance':False}
        self.q.journal=mock.Mock(directory=self.root);self.q.journal.control_lock=threading.RLock()
        self.q.journal.directory_fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY);self.addCleanup(os.close,self.q.journal.directory_fd)
        self.q.inode=self.q.saved_sha=None
        fd=os.open(self.root/'phase-qualification.json',os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600)
        self.q.inode=(os.fstat(fd).st_dev,os.fstat(fd).st_ino);os.close(fd);self.q._save()
        self.addCleanup(self.q.close)
        self.q.directory=self.root;self.q.reader_path=self.root/'reader';self.q.manifest_path=self.root/'manifest'
        self.q.ready_api=mock.Mock()
        self.guard_objects=objects(self.b)
        self.q.guard_api=mock.Mock()
        self.q.guard_api.guard.side_effect=lambda k,n,deadline:copy.deepcopy(next(o for o in self.guard_objects if o['kind']==k and o['metadata']['name']==n))

    def receipt(self, *, floor=None):
        r={'abi':1,'scope':'actual-current-writer-schema-metadata-only',
            'writer':self.q.operation.r['baseline']['writer']|{'image':f.LEGACY,'resourceVersion':'opaque-writer'},
            'migration_count':7,'unfinished_migration_count':0,'rolled_back_migration_count':0,
            'historical_migrations_match':True,'topology_match':True,'writer_unchanged':True,
            'collector_source_sha256':m.ready.READER_SHA,'migration_manifest_sha256':m.ready.MANIFEST_SHA,
            'observed_monotonic_ns':time.monotonic_ns() if floor is None else floor,'metadata_only':True}
        path=self.root/('schema-metadata-'+uuid.uuid4().hex[:12]+'.json')
        raw=json.dumps(r).encode();path.write_bytes(raw);path.chmod(0o600)
        return {'path':str(path),'sha256':m.sha(raw),'receipt':r}

    def call(self, result=None):
        with mock.patch.object(m.ready,'collect',side_effect=lambda *a: self.receipt() if result is None else result),\
             mock.patch.object(m.ready,'snapshot',side_effect=lambda *_:{'writer':self.q.last_ready_writer}):
            return self.q(m.PHASES[0],self.q.deadline)

    def capture(self):
        ids={k:{'name':k,'namespace':'bortus','uid':'public-'+k,'resourceVersion':'opaque'} for k in m.interval.quiescent.CONTROL_KEYS}
        self.q.operation.source.side_effect=lambda **kw: copy.deepcopy(ids)
        cipher=self.root/'sqlite-files.age';cipher.write_bytes(b'PUBLIC CIPHERTEXT FIXTURE');cipher.chmod(0o600)
        self.q.operation.r.update(quiescent={'state':'captured-zero'},sqlite_archive_state='confirmed',
            sqlite_archive={'artifact':str(cipher),'ciphertext_sha256':m.sha(cipher.read_bytes())})
        receipt={'abi':1,'scope':'authenticated latest quiescent archive schema metadata only',
            'run_id':'123456abcdef','ciphertext_sha256':m.sha(cipher.read_bytes()),'manifest_sha256':m.ready.MANIFEST_SHA,
            'source_identities':ids,'schema_migrations':7,'migration_checksums_match':True,'migrations_complete':True,
            'tables_and_columns_match':True,'tmpfs_cleaned':True,'live_ready_writer_proven':False,
            'whole_row_preservation_proven':False,'forward_acceptance':False,
            'producer_sha256':m.sha(pathlib.Path(m.interval.archive.__file__).read_bytes())}
        path=self.root/'quiescent-schema-123456abcdef.json';raw=json.dumps(receipt).encode();path.write_bytes(raw);path.chmod(0o600)
        self.q.archive.schema_metadata=mock.Mock(return_value={'schema_receipt_path':str(path),
            'schema_receipt_sha256':m.sha(raw),'schema_migrations':7})
        return path,cipher,ids

    def test_fresh_ready_receipt_and_subordinate_deadline(self):
        deadlines=[]
        def collect(*args):deadlines.append(args[3]);return self.receipt()
        with mock.patch.object(m.ready,'collect',side_effect=collect),\
             mock.patch.object(m.ready,'snapshot',side_effect=lambda *_:{'writer':self.q.last_ready_writer}):
            a=self.q(m.PHASES[0],self.q.deadline);b=self.q(m.PHASES[0],self.q.deadline)
        self.assertNotEqual(a['schema_receipt_sha256'],b['schema_receipt_sha256'])
        self.assertTrue(all(0<d-time.monotonic()<=300 for d in deadlines));self.assertEqual(24,self.q.guard_api.guard.call_count)
        self.assertEqual(7,a['schema_migrations'])

    def test_stale_ready_receipt_refused(self):
        with self.assertRaises(m.Refused):self.call(self.receipt(floor=1))

    def test_forward_exact_stability_and_static_schema_label(self):
        self.capture();self.q(m.PHASES[0],self.q.deadline)
        self.q.operation.r['quiescent']['state']='guard-transition-open'
        forward=binding(m.PHASES[1]);self.q.authorize_forward(forward);self.guard_objects=objects(forward)
        a=self.q(m.PHASES[1],self.q.deadline)
        self.q.operation.r['quiescent']['state']='entrypoint-pending'
        b=self.q(m.PHASES[1],self.q.deadline)
        self.assertEqual(a,b);self.q.archive.schema_metadata.assert_called_once()
        self.assertTrue(self.q.state['calls'][-1]['schema_scope'].startswith('static authenticated'))

    def test_no_first_schema_creation_in_entrypoint_pending(self):
        self.capture();self.q.operation.r['quiescent']['state']='entrypoint-pending'
        with self.assertRaises(m.Refused):self.q(m.PHASES[0],self.q.deadline)
        self.q.archive.schema_metadata.assert_not_called()

    def test_guard_rv_uid_spec_warnings_generation_drift(self):
        for field in ('rv','uid','spec','warnings','generation'):
            with self.subTest(field=field):
                self.q.failed=False;self.guard_objects=objects(self.b);obj=self.guard_objects[0]
                if field=='rv':obj['metadata']['resourceVersion']='new'
                elif field=='uid':obj['metadata']['uid']=str(uuid.uuid4())
                elif field=='spec':obj['spec']['failurePolicy']='Ignore'
                elif field=='warnings':obj['status']['typeChecking']['expressionWarnings']=[{'warning':'PUBLIC'}]
                else:obj['status']['observedGeneration']=0
                with self.assertRaises(m.Refused):self.call()

    def test_external_boolean_and_changed_source_refuse(self):
        for result in (True,self.b|{'source_sha256':'5'*64}):
            self.q.failed=False;self.q.verify_binding=lambda *_: result
            with self.assertRaises(m.Refused):self.call()

    def test_guard_after_schema_drift_refuses(self):
        count=[0]
        def collect(*_):self.guard_objects[0]['metadata']['resourceVersion']='after';return self.receipt()
        with mock.patch.object(m.ready,'collect',side_effect=collect),self.assertRaises(m.Refused):
            self.q(m.PHASES[0],self.q.deadline)

    def test_forward_replacement_or_legacy_member_refuse(self):
        self.capture();self.q.operation.r['quiescent']['state']='guard-transition-open'
        for key in ('uid','legacy'):
            self.q.failed=False;candidate=binding(m.PHASES[1])
            if key=='uid':candidate['policy_pins'][next(iter(candidate['policy_pins']))]['uid']=str(uuid.uuid4())
            else:candidate['contract']['approved_image_references'].append(f.LEGACY)
            with self.assertRaises(m.Refused):self.q.authorize_forward(candidate)

    def test_forward_once_no_repin(self):
        self.capture();self.q.operation.r['quiescent']['state']='guard-transition-open'
        self.q.authorize_forward(binding(m.PHASES[1]))
        with self.assertRaises(m.Refused):self.q.authorize_forward(binding(m.PHASES[1]))

    def test_cipher_or_schema_replacement_refuses(self):
        for which in ('cipher','schema'):
            self.q.failed=False;self.q.close();self.q.closed=False
            self.q.archive_result=self.q.archive_receipt=None
            path,cipher,_=self.capture();self.q(m.PHASES[0],self.q.deadline)
            target=path if which=='schema' else cipher;replacement=target.with_suffix('.replacement')
            replacement.write_bytes(target.read_bytes());replacement.chmod(0o600);os.replace(replacement,target)
            with self.assertRaises(m.Refused):self.q(m.PHASES[0],self.q.deadline)

    def test_archive_source_uid_drift(self):
        _,_,ids=self.capture();self.q(m.PHASES[0],self.q.deadline)
        ids['deployment']['uid']='replacement'
        with self.assertRaises(m.Refused):self.q(m.PHASES[0],self.q.deadline)

    def test_missing_archive_confirmation_and_phase_regression_refuse(self):
        for fault in ('confirmation','regression'):
            self.q.failed=False;self.q.close();self.q.closed=False
            self.q.archive_result=self.q.archive_receipt=None
            self.capture();self.q(m.PHASES[0],self.q.deadline)
            if fault=='confirmation':self.q.operation.r['sqlite_archive_state']='pending'
            else:self.q.operation.r['quiescent']['state']='pending'
            with self.assertRaises(m.Refused):self.q(m.PHASES[0],self.q.deadline)

    def test_ready_writer_replacement_after_schema_refuses(self):
        with mock.patch.object(m.ready,'collect',side_effect=lambda *_:self.receipt()),\
             mock.patch.object(m.ready,'snapshot',return_value={'writer':{'uid':'replacement'}}),\
             self.assertRaises(m.Refused):self.q(m.PHASES[0],self.q.deadline)

    def test_zero_writer_failure_after_guard_io_refuses(self):
        self.capture()
        def verify(b,d):
            if self.q.archive_result is not None:self.q.operation.source.side_effect=RuntimeError('PRIVATE')
            return b
        self.q.verify_binding=verify
        with self.assertRaises(m.Refused):self.q(m.PHASES[0],self.q.deadline)

    def test_no_deadline_renewal_or_late_external_return(self):
        with self.assertRaises(m.Refused):self.q(m.PHASES[0],self.q.deadline+1)
        self.q.failed=False
        def verify(b,d):self.q.deadline=time.monotonic()-1;return b
        self.q.verify_binding=verify
        with self.assertRaises(m.Refused):self.call()

    def test_sidecar_inode_hash_fsync_and_sticky_failure(self):
        for fault in ('replace','hash','flush'):
            self.q.failed=False
            if fault=='replace':
                p=self.root/'sidecar-new';p.write_bytes((self.root/'phase-qualification.json').read_bytes());p.chmod(0o600)
                os.replace(p,self.root/'phase-qualification.json')
            elif fault=='hash':(self.root/'phase-qualification.json').write_bytes(b'{}')
            with mock.patch.object(os,'fsync',side_effect=OSError('PUBLIC')) if fault=='flush' else mock.patch.object(m,'digest',wraps=m.digest):
                with self.assertRaises(m.Refused):self.call()
            with self.assertRaises(m.Refused):self.call()

    def test_cleanup_attempts_both_pins_without_closing_borrowed_observer(self):
        a,b=mock.Mock(),mock.Mock();a.close.side_effect=OSError('PUBLIC')
        self.q.archive_pin,self.q.cipher_pin=a,b
        with self.assertRaises(m.Refused):self.q.close()
        a.close.assert_called_once();b.close.assert_called_once();self.q.observer.close.assert_not_called()

    def test_fixed_refusal_frames_drop_raw_response_arguments(self):
        marker='PRIVATE_RESPONSE_NOT_FOR_PUBLIC';self.guard_objects[0]['spec']['private']=marker
        try:self.call()
        except m.Refused as error:
            tb=error.__traceback__
            while tb:
                if tb.tb_frame.f_code.co_name=='__call__':
                    self.assertIsNone(tb.tb_frame.f_locals['self']);self.assertIsNone(tb.tb_frame.f_locals['phase'])
                tb=tb.tb_next
            self.assertNotIn(marker,str(error));self.assertIsNone(error.__context__)
        else:self.fail('refusal required')

    def test_constructor_actual_shared_observer_and_guard_tls_graph(self):
        cert,key=self.root/'cert',self.root/'key'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-subj','/CN=localhost',
            '-addext','subjectAltName=DNS:localhost','-keyout',str(key),'-out',str(cert),'-days','1'],
            check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
        def options():
            context=ssl.create_default_context(cafile=str(cert));context.minimum_version=ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(cert,key);return context,{}
        c,oldj,old,_=f.prepare();record=copy.deepcopy(oldj.record)
        record['baseline']['protected_claim_names']=self.b['contract']['protected_pvc_names']
        w=m.interval.watch;control_objects={k:copy.deepcopy(c.resources[k]) for k in w.SCOPES}
        for k,o in control_objects.items():o.update(apiVersion=w.SCOPES[k][0],kind=w.SCOPES[k][1])
        control=wf.Fixture(cert,key,control_objects);self.addCleanup(control.close)
        guards=Guards(cert,key,objects(self.b));self.addCleanup(guards.close)
        journal=w.ControlJournal(self.root/'actual-run',record).open(new=True);self.addCleanup(journal.close)
        deadline=time.monotonic()+15
        observer=w.Observer(journal,old.pins,w.TLSControls(options,control.origin),deadline=deadline)
        self.addCleanup(observer.close);observer.start()
        client=m.interval.IntervalClient(observer,deadline=deadline);self.addCleanup(client.close)
        archive=object.__new__(m.interval.archive.QuiescentArchive);archive.quiescent=m.interval.quiescent
        producer=m.PhaseQualifier(observer,archive,self.b,lambda b,d:copy.deepcopy(b),
            ready_directory=self.root,reader_path=self.root/'reader',manifest_path=self.root/'manifest')
        # Only route the existing fixed read-only client to the owned TLS fixture.
        producer.guard_api.host,producer.guard_api.port='localhost',guards.server.server_port
        self.addCleanup(producer.close)
        operation=m.interval.quiescent.QuiescentCheckpoint(client,journal,observer.trace,producer,archive,deadline=deadline)
        producer.bind(operation)
        def receipt(*_):
            result=self.receipt();result['receipt']['writer'].update({k:record['baseline']['writer'][k] for k in ('name','namespace','uid')})
            result['receipt']['writer']['image']=f.LEGACY
            raw=json.dumps(result['receipt']).encode();pathlib.Path(result['path']).write_bytes(raw);result['sha256']=m.sha(raw)
            return result
        with mock.patch.object(m.ready,'collect',side_effect=receipt),\
             mock.patch.object(m.ready,'snapshot',side_effect=lambda *_:{'writer':producer.last_ready_writer}):
            packet=operation.qualification(m.PHASES[0])
        self.assertEqual(12,len(guards.calls));self.assertIs(operation.trace,observer.trace)
        self.assertEqual(7,packet['schema_migrations']);self.assertFalse(producer.state['overall_acceptance'])
        with self.assertRaises(m.Refused):producer.bind(operation)


if __name__ == '__main__': unittest.main()
