"""Owned loopback HTTPS/POSIX only; no live policies, CEL engine or operator files."""
import copy
import http.server
import importlib.util
import json
import os
import pathlib
import socket
import ssl
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from urllib.parse import urlsplit, parse_qs
import test_bortus_restore_watch as certificates

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('admission_operator_tests', HERE.parent/'bortus-admission-operator.py')
a = importlib.util.module_from_spec(spec); sys.modules[spec.name] = a; spec.loader.exec_module(a)
UID = lambda n: '00000000-0000-0000-0000-' + str(n).zfill(12)


class Server:
    def __init__(self, cert, key, guards, contract):
        self.guards, self.contract = guards, contract
        self.objects, self.requests, self.probes = {}, [], []
        self.failure, self.errors, self.serial = None, 0, 20
        fixture = self
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *_): pass
            def handle(self):
                try: super().handle()
                except (ConnectionResetError, BrokenPipeError, ssl.SSLError): pass
            def execute(self):
                length = int(self.headers.get('Content-Length', '0'))
                body = json.loads(self.rfile.read(length)) if length else None
                fixture.requests.append((self.command,self.path,body,self.headers.get('Authorization')))
                if fixture.failure == 'lost-create' and self.command == 'POST' and '?' not in self.path:
                    self.connection.shutdown(socket.SHUT_RDWR); self.connection.close(); return
                code, value = fixture.respond(self.command,self.path,body)
                raw = json.dumps(value).encode()
                self.send_response(code); self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
            do_GET = do_POST = do_PUT = do_DELETE = execute
        class HTTPS(http.server.ThreadingHTTPServer):
            daemon_threads = False
            def handle_error(self,*_): fixture.errors += 1
        self.server = HTTPS(('127.0.0.1',0),Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.load_cert_chain(cert,key)
        self.server.socket = context.wrap_socket(self.server.socket,server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01}); self.thread.start()
        self.origin = 'https://localhost:'+str(self.server.server_port)

    def respond(self, method, path, body):
        p=urlsplit(path); name=p.path.rsplit('/',1)[1]
        if 'admissionregistration' in p.path:
            return 200,copy.deepcopy(next(o for o in self.guards if o['metadata']['name']==name and
                (o['kind']==a.validator.BINDING)==('bindings/' in p.path)))
        kind=next(k for k,(_,base) in a.WORKLOADS.items() if p.path==base or p.path.startswith(base+'/'))
        if p.query:
            assert parse_qs(p.query)=={'dryRun':['All'],'fieldValidation':['Strict']}
            case=a.validator.probe_catalog(self.contract)[len(self.probes)]; self.probes.append((case,copy.deepcopy(body)))
            assert case['kind']==kind
            if case['expected_outcome']=='allowed': return 201,body
            policy='bortus-kv-guard-'+a.validator.KINDS[kind]
            message=f"ValidatingAdmissionPolicy '{policy}' with binding '{policy}' denied request: {a.MESSAGE}"
            if self.failure=='rbac': message='PRIVATE_SYNTHETIC_RBAC_ERROR'
            return 403,{'apiVersion':'v1','kind':'Status','status':'Failure','reason':'Forbidden','code':403,
                'message':'Workload is forbidden: '+message,'details':{'causes':[{'message':message}]}}
        if method=='GET':
            if p.path==a.WORKLOADS[kind][1]:
                items=[copy.deepcopy(o) for (k,_),o in self.objects.items() if k==kind]
                meta={'resourceVersion':'opaque-list'}
                if self.failure=='incomplete-list': meta['continue']='private-continuation'
                return 200,{'apiVersion':a.WORKLOADS[kind][0],'kind':kind+'List','metadata':meta,'items':items}
            return 200,copy.deepcopy(self.objects[(kind,name)])
        if method in ('POST','PUT'):
            obj=copy.deepcopy(body); name=obj['metadata']['name']; key=(kind,name)
            if method=='POST' and key in self.objects:return 409,{'apiVersion':'v1','kind':'Status','message':'PRIVATE_SYNTHETIC_COLLISION'}
            self.serial+=1
            if method=='PUT': assert obj['metadata']['uid']==self.objects[key]['metadata']['uid'] and obj['metadata']['resourceVersion']==self.objects[key]['metadata']['resourceVersion']
            obj['metadata'].update(uid=self.objects[key]['metadata']['uid'] if key in self.objects else UID(self.serial),resourceVersion='opaque-'+str(self.serial))
            self.objects[key]=obj; return (201 if method=='POST' else 200),copy.deepcopy(obj)
        if method=='DELETE':
            obj=self.objects[(kind,name)]; assert body['preconditions']=={k:obj['metadata'][k] for k in ('uid','resourceVersion')}
            del self.objects[(kind,name)]
            return 200,{'apiVersion':'v1','kind':'Status','status':'Success',
                'details':{'name':name,'uid':obj['metadata']['uid'],'kind':a.WORKLOADS[kind][1].rsplit('/',1)[1]}}
        raise AssertionError('Unexpected fixed fixture route')

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)
        assert not self.thread.is_alive() and self.errors==0


class OperatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): certificates.RestoreWatchTests.setUpClass(); cls.cert,cls.key=certificates.RestoreWatchTests.cert,certificates.RestoreWatchTests.key
    @classmethod
    def tearDownClass(cls): certificates.RestoreWatchTests.tearDownClass()
    def setUp(self):
        fixture=json.loads((HERE/'fixtures/bortus-admission-render-v1.json').read_text())
        self.contract,self.renders=fixture['contract'],fixture['renders']; self.guards=copy.deepcopy(self.renders)
        for n,o in enumerate(self.guards,1):
            o['metadata'].update(uid=UID(n),resourceVersion='opaque-'+str(n),generation=2)
            if o['kind']==a.validator.POLICY:o['status']={'observedGeneration':2,'typeChecking':{}}
        self.server=Server(self.cert,self.key,self.guards,self.contract)
        self.origin=mock.patch.object(a,'APPROVED_ORIGIN',self.server.origin); self.origin.start()
        self.temp=tempfile.TemporaryDirectory(); self.parent=pathlib.Path(self.temp.name); os.chmod(self.parent,0o700)
        self.calls=0; self.deadlines=[]
        self.prepared={'restore_target_name':self.contract['protected_pvc_names'][1], 'checkpoint_run_id':'123456abcdef',
            'source_identities':{'kustomization':{'name':'migration-releases','namespace':'flux-system','uid':UID(19)}},
            'alternate_node_identity':{'name':'alternate-node'}}
        self.fence=object.__new__(a.source.SourceFence); self.fence.checkpoint_sha256='a'*64
        def prepare(*,deadline):self.deadlines.append(deadline);return copy.deepcopy(self.prepared)
        def check(*,deadline):self.deadlines.append(deadline);return {'checkpoint_journal_sha256':'a'*64}
        self.fence.prepare=prepare;self.fence.check=check
    def tearDown(self):self.origin.stop();self.server.close();self.temp.cleanup()
    def options(self):
        self.calls+=1; context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); context.load_verify_locations(cafile=str(self.cert))
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        return context,{'Authorization':'Bearer PUBLIC_ROTATION_'+str(self.calls)}
    def publication(self,deadline):
        self.deadlines.append(deadline)
        return {'chart_commit':'b'*40,'validated_revision':'b'*40,'flux_revision':'b'*40,'ci_success':True,'flux_ready':True,
            'flux_owner':{'kind':'Kustomization',**self.prepared['source_identities']['kustomization'],'resourceVersion':'opaque-flux'},
            'guard_pins':[{'kind':o['kind'],'name':o['metadata']['name'],'uid':o['metadata']['uid'],'resourceVersion':o['metadata']['resourceVersion'],
                'spec_sha256':__import__('hashlib').sha256(a.validator.canonical_spec(o['kind'],o['spec'])).hexdigest()} for o in self.guards],
            'publication_receipt_sha256':'c'*64}
    def operator(self,publication=None):return a.AdmissionOperator(self.fence,self.options,self.contract,self.renders,'b'*40,publication or self.publication)
    def execute(self,operator=None):
        deadline=time.monotonic()+60
        result=(operator or self.operator()).qualify(self.parent/'new-run',deadline=deadline)
        self.assertEqual({deadline},set(self.deadlines));return result
    def refusal(self,callback,code=None):
        try:callback()
        except a.OperatorRefused as error:
            self.assertIsNone(error.__context__);self.assertIsNone(error.__cause__)
            if code:self.assertEqual(code,error.code)
            trace=error.__traceback__
            while trace:
                if trace.tb_frame.f_code.co_filename.endswith('bortus-admission-operator.py'):
                    self.assertNotIn('PRIVATE_SYNTHETIC',repr(trace.tb_frame.f_locals))
                trace=trace.tb_next
            return
        self.fail('Expected refusal')
    def record(self):return json.loads((self.parent/'new-run/record.json').read_text())

    def test_actual_https_joint_pipeline_durable_cleanup_and_false_acceptance(self):
        result=self.execute();self.assertEqual(40,result.collected_cases);self.assertFalse(result.actual_enforcement_accepted)
        self.assertFalse(result.overall_live_restore_acceptance);record=self.record();self.assertEqual('completed',record['phase'])
        self.assertEqual(40,len(record['outcomes']));self.assertEqual(8,len(record['operations']))
        self.assertFalse(self.server.objects);self.assertFalse((self.parent/'new-run/active.lock').exists())
        self.assertEqual(self.calls,len(self.server.requests))
        self.assertEqual(['Bearer PUBLIC_ROTATION_'+str(n) for n in range(1,self.calls+1)],[r[3] for r in self.server.requests])
        actual=[r for r in self.server.requests if r[0]in('POST','PUT') and '?'not in r[1]]
        self.assertEqual(6,len(actual));self.assertTrue(all(r[2]['kind']in('Pod','Deployment') for r in actual))
        for _,_,obj,_ in actual:
            spec=obj['spec']if obj['kind']=='Pod'else obj['spec']['template']['spec']
            self.assertFalse(spec['automountServiceAccountToken']);self.assertNotIn('volumeMounts',spec['containers'][0])
            if obj['kind']=='Deployment':self.assertEqual(0,obj['spec']['replicas'])
        removals=[(case,body)for case,body in self.server.probes if case['scenario']=='oldObject-reference-removal']
        self.assertEqual(4,len(removals));self.assertTrue(all(b['kind']=='Deployment' and 'uid'in b['metadata']for _,b in removals))
        ephemeral=[(case,body)for case,body in self.server.probes if case['scenario']=='legacy-ephemeral']
        self.assertEqual(1,len(ephemeral));case,body=ephemeral[0]
        self.assertEqual('bortus-kv',case['protected_reference']);self.assertEqual('bortus-kv',body['spec']['serviceAccountName'])
        self.assertNotIn('volumes',body['spec'])

    def test_generic_rbac_is_not_guard_attribution_and_no_failure_cleanup_mutation(self):
        self.server.failure='rbac';self.refusal(lambda:self.execute(),'attribution')
        self.assertEqual('refused',self.record()['phase']);self.assertEqual(2,len(self.server.objects))
        self.assertFalse(any(r[0]=='DELETE'for r in self.server.requests))

    def test_lost_reply_retains_uncertain_without_retry_adoption(self):
        self.server.failure='lost-create';self.refusal(lambda:self.execute(),'uncertain')
        self.assertEqual('uncertain',self.record()['operations']['Pod-create']['state'])
        self.assertEqual(1,sum(r[0]=='POST'for r in self.server.requests))
        self.refusal(lambda:self.operator().qualify(self.parent/'new-run',deadline=time.monotonic()+10))
        self.assertEqual(1,sum(r[0]=='POST'for r in self.server.requests))

    def test_publication_false_revision_and_uid_drift_refuse_before_fixture(self):
        for mutate in (lambda p:p.update(flux_ready=False),lambda p:p.update(validated_revision='d'*40),
                       lambda p:p['guard_pins'][0].update(uid=UID(99))):
            def callback(deadline):p=self.publication(deadline);mutate(p);return p
            self.refusal(lambda:self.execute(self.operator(callback)),'publication')
            self.assertFalse(any(r[0]!='GET'for r in self.server.requests))

    def test_typecheck_and_selector_drift_refuse_before_fixture(self):
        self.guards[0]['status']['typeChecking']={'expressionWarnings':[{'warning':'PRIVATE_SYNTHETIC'}]}
        self.refusal(lambda:self.execute(),'guard');self.assertFalse(self.server.objects)

    def test_deadline_and_unverified_tls_no_dispatch(self):
        self.refusal(lambda:self.operator().qualify(self.parent/'new-run',deadline=time.monotonic()-1),'deadline')
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
        api=a.API(lambda:(context,{}),origin=self.server.origin)
        self.refusal(lambda:api.workload('POST','Pod',body={'PRIVATE_SYNTHETIC':'value'},deadline=time.monotonic()+3),'probe')
        self.refusal(lambda:api.guard(a.validator.POLICY,'bortus-kv-guard-pods',deadline=time.monotonic()+3),'transport')
        self.assertEqual([],self.server.requests)

    def test_fixed_scope_refuses_secrets_arbitrary_paths_and_mutating_job(self):
        api=a.API(self.options,origin=self.server.origin)
        for kind,name in [('Secret','x'),('Pod','foreign'),('Job','bortus-admission-123456abcdef-case-1')]:
            self.refusal(lambda:api.workload('PUT',kind,name,{},deadline=time.monotonic()+3),'probe')
        self.assertFalse(self.server.requests)

    def test_incomplete_absence_refuses_not_confirms(self):
        self.server.failure='incomplete-list';self.refusal(lambda:self.execute(),'uncertain')
        self.assertEqual('uncertain',self.record()['operations']['Pod-delete']['state'])
        self.assertIn(('Deployment','bortus-admission-123456abcdef-deployment'),self.server.objects)

    def test_status_wrong_policy_configuration_or_multiple_causes_refuse(self):
        case=next(c for c in a.validator.probe_catalog(self.contract)if c['expected_outcome']=='guard_denied')
        name='bortus-kv-guard-'+a.validator.KINDS[case['kind']]
        message=f"ValidatingAdmissionPolicy '{name}' with binding '{name}' denied request: {a.MESSAGE}"
        obj={'apiVersion':'v1','kind':'Status','status':'Failure','reason':'Forbidden','code':403,
             'message':'PRIVATE_SYNTHETIC '+message,'details':{'causes':[{'message':message}]}}
        pins={(o['kind'],o['metadata']['name']):o['metadata']['uid']for o in self.guards}
        self.assertEqual('guard_denied',a.attributed(403,obj,case,pins)['outcome'])
        for mutate in (lambda o:o.update(reason='Invalid'),lambda o:o['details']['causes'].append({'message':message}),
                       lambda o:o['details']['causes'][0].update(message='PRIVATE_SYNTHETIC_CONFIG')):
            value=copy.deepcopy(obj);mutate(value);self.refusal(lambda:a.attributed(403,value,case,pins),'attribution')

    def test_initialization_fsync_failure_closes_all_owned_descriptors(self):
        before=len(os.listdir('/proc/self/fd'));real=os.fsync;calls=0
        def fail(fd):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('public injected lock fsync')
            return real(fd)
        with mock.patch.object(a.os,'fsync',fail):
            with self.assertRaises(OSError):a.ProbeRun(self.parent/'fault',{})
        self.assertEqual(before,len(os.listdir('/proc/self/fd')))

    def test_pending_file_and_directory_flush_precede_callback(self):
        run=a.ProbeRun(self.parent/'journal',{})
        try:
            called=[]
            def dispatch():
                record=json.loads((run.path/'record.json').read_text());self.assertEqual('pending',record['operations']['one']['state'])
                called.append(True);return {}
            run.perform('one',{'kind':'public'},dispatch,lambda _:None);self.assertEqual([True],called)
            with mock.patch.object(a.os,'fsync',side_effect=OSError('public fault')):
                with self.assertRaises(OSError):run.perform('two',{},lambda:called.append(False),lambda _:None)
            self.assertEqual([True],called)
        finally:
            # A replaced record whose fsync failed remains deliberately uncertain; closure still closes FDs.
            try:run.close()
            except a.OperatorRefused:pass

    def test_same_inode_record_tampering_and_symlink_refuse(self):
        run=a.ProbeRun(self.parent/'journal',{})
        try:
            (run.path/'record.json').write_text('PRIVATE_SYNTHETIC')
            with self.assertRaises(a.OperatorRefused):run.save()
        finally:
            try:run.close()
            except a.OperatorRefused:pass
        (self.parent/'link').symlink_to(self.parent/'journal',target_is_directory=True)
        with self.assertRaises(FileExistsError):a.ProbeRun(self.parent/'link',{})

    def test_fixture_uid_spec_and_complete_collection_shape_refuse(self):
        proposal=a.object_for('Deployment','bortus-admission-123456abcdef-deployment',a.idle_spec(self.contract['approved_image_references'][0],'alternate-node'))
        obj=copy.deepcopy(proposal);obj['metadata'].update(uid=UID(50),resourceVersion='opaque')
        self.assertEqual(UID(50),a.fixture_matches(obj,proposal)['uid'])
        obj['spec']['replicas']=1
        with self.assertRaises(a.OperatorRefused):a.fixture_matches(obj,proposal)


if __name__=='__main__':unittest.main()
