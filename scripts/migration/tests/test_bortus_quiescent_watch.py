"""Actual owned localhost mTLS, POSIX durability and controlled metadata only."""
import copy
import http.server
import importlib.util
import json
import os
import pathlib
import queue
import ssl
import subprocess
import tempfile
import threading
import time
import traceback
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit

HERE=pathlib.Path(__file__).resolve().parent
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
m=load('quiescent_watch_test',HERE.parent/'bortus-quiescent-watch.py')
f=load('quiescent_watch_fixture',HERE/'test_bortus_quiescent_source.py')


class Fixture:
    def __init__(self,cert,key,objects,*,pages=None,status=200,early=False):
        self.objects=copy.deepcopy(objects);self.pages=pages or {}
        self.status=status;self.early=early
        self.queues={k:queue.Queue() for k in m.SCOPES}
        self.stop=threading.Event();self.requests=[];self.fresh=[]
        self.closed={k:threading.Event() for k in m.SCOPES};self.errors=0
        owner=self
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*_):pass
            def handle(self):
                try:super().handle()
                except (OSError,ssl.SSLError):pass  # Expected explicit owned socket cancellation.
            def do_GET(self):
                parsed=urlsplit(self.path);query=parse_qs(parsed.query)
                key=next(k for k,v in m.SCOPES.items() if v[4]==parsed.path)
                owner.requests.append((key,query))
                owner.fresh.append(self.headers.get('Authorization')=='Bearer PUBLIC_ROTATION_'+str(len(owner.requests)))
                if query.get('watch')!=['true']:
                    api,kind,_,_,_=m.SCOPES[key]
                    page=owner.pages.get(key,{'apiVersion':api,'kind':kind+'List',
                        'metadata':{'resourceVersion':'list-'+key,'continue':''},'items':[owner.objects[key]]})
                    raw=page if type(page) is bytes else json.dumps(page).encode()
                    self.send_response(200);self.send_header('Content-Type','application/json')
                    self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
                self.send_response(owner.status);self.send_header('Content-Type','application/json')
                self.send_header('Transfer-Encoding','chunked');self.end_headers()
                if owner.status!=200:self.wfile.write(b'0\r\n\r\n');return
                if owner.early:
                    obj=copy.deepcopy(owner.objects[key]);obj['metadata']['resourceVersion']='early-'+key
                    owner.send(key,obj)
                try:
                    while not owner.stop.is_set():
                        try:raw=owner.queues[key].get(timeout=.01)
                        except queue.Empty:continue
                        if raw is None:self.wfile.write(b'0\r\n\r\n');return
                        self.wfile.write(format(len(raw),'x').encode()+b'\r\n'+raw+b'\r\n');self.wfile.flush()
                except (OSError,ssl.SSLError):pass
                finally:owner.closed[key].set()
        class Server(http.server.ThreadingHTTPServer):
            daemon_threads=True
            def handle_error(self,*_):owner.errors+=1
        self.server=Server(('127.0.0.1',0),Handler)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
        context.load_verify_locations(cafile=str(cert));context.verify_mode=ssl.CERT_REQUIRED
        self.server.socket=context.wrap_socket(self.server.socket,server_side=True)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01});self.thread.start()
    @property
    def origin(self):return 'https://localhost:'+str(self.server.server_port)
    def send(self,key,obj=None,kind='MODIFIED',raw=None):
        self.queues[key].put(raw if raw is not None else json.dumps({'type':kind,'object':obj}).encode()+b'\n')
    def close(self):
        self.stop.set();self.server.shutdown();self.server.server_close();self.thread.join(2)
        for key,query in self.requests:
            if query.get('watch')==['true'] and self.status==200:
                assert self.closed[key].wait(2)
        assert not self.thread.is_alive() and self.errors==0


@unittest.skipUnless(os.name=='posix','Actual owned POSIX/local mTLS required')
class ObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.certificates=tempfile.TemporaryDirectory(prefix='quiescent-public-cert-')
        cls.cert=pathlib.Path(cls.certificates.name)/'fixture.pem';cls.key=cls.cert.with_name('fixture-key.pem')
        mask=os.umask(0o077)
        try:subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
            '-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost',
            '-keyout',str(cls.key),'-out',str(cls.cert)],check=True,capture_output=True,timeout=10)
        finally:os.umask(mask)
    @classmethod
    def tearDownClass(cls):cls.certificates.cleanup()
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(prefix='quiescent-owned-run-')
        client,record,op,_=f.prepare()
        self.record=copy.deepcopy(record.record)
        self.objects={k:copy.deepcopy(client.resources[k]) for k in m.SCOPES}
        for k,obj in self.objects.items():obj.update(apiVersion=m.SCOPES[k][0],kind=m.SCOPES[k][1])
        self.pins=copy.deepcopy(op.pins)
        self.directory=pathlib.Path(self.folder.name)/'run'
        self.journal=m.ControlJournal(self.directory,self.record).open(new=True)
        self.fixture=self.observer=None;self.option_calls=0
    def tearDown(self):
        if self.observer:self.observer.close()
        if self.fixture:self.fixture.close()
        self.journal.close();self.folder.cleanup()
    def options(self):
        self.option_calls+=1
        context=ssl.create_default_context(cafile=str(self.cert));context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(self.cert,self.key)
        return context,{'Authorization':'Bearer PUBLIC_ROTATION_'+str(self.option_calls)}
    def create(self,*,lease=5,pages=None,status=200,early=False,start=True):
        self.fixture=Fixture(self.cert,self.key,self.objects,pages=pages,status=status,early=early)
        transport=m.TLSControls(self.options,self.fixture.origin)
        self.observer=m.Observer(self.journal,self.pins,transport,deadline=time.monotonic()+lease)
        if start:self.observer.start()
        return self.observer
    def wait(self,predicate):
        until=time.monotonic()+2
        while not predicate():
            if time.monotonic()>until:self.fail('Bounded local fixture timeout')
            time.sleep(.005)
    def ids(self):
        return {k:m.quiescent.cold.identity(obj) for k,obj in self.objects.items()}
    def send(self,key,*,value=None,rv='opaque-new',intent=True):
        old=self.objects[key]['spec'].get(m.quiescent.cold.RESOURCES[key][3],False)
        obj=copy.deepcopy(self.objects[key]);obj['metadata']['resourceVersion']=rv
        if value is not None:
            obj['spec'][m.quiescent.cold.RESOURCES[key][3]]=value
            if intent:
                self.journal.record['controls'][key]['intent']={'from':old,'to':value,'state':'pending',
                    'resourceVersion':self.objects[key]['metadata']['resourceVersion']}
                self.journal.save()
        self.objects[key]=obj;self.fixture.send(key,obj)
    def stopped(self):
        for key in m.SCOPES:self.send(key,value=m.quiescent.TARGETS[key],rv='stop-'+key)
        self.observer.check(self.ids(),stopped=True)
    def test_actual_three_mtls_streams_fresh_options_collection_rvs_and_durable_projection(self):
        o=self.create();o.check(self.ids(),stopped=False)
        self.assertEqual(6,self.option_calls);self.assertTrue(all(self.fixture.fresh))
        for key,query in self.fixture.requests:
            self.assertEqual(['metadata.name='+m.SCOPES[key][3]],query['fieldSelector'])
            if query.get('watch')==['true']:self.assertEqual(['list-'+key],query['resourceVersion'])
        self.stopped();proof=o.prerequisite()
        self.assertFalse(proof['data_acceptance'])
        raw=(self.directory/'control-watch.json').read_text()
        self.assertNotIn('spec"',raw);self.assertEqual(3,json.loads(raw)['frames'])
    def test_early_events_retained_before_all_readers_ready(self):
        o=self.create(early=True)
        self.wait(lambda:len(o.state['observations'])==3)
        for key in m.SCOPES:self.objects[key]['metadata']['resourceVersion']='early-'+key
        o.check(self.ids(),stopped=False);self.assertEqual(3,o.trace.count-3)
    def test_quiet_stream_exceeds_short_idle_threshold_then_explicit_closure(self):
        o=self.create(lease=2);time.sleep(.15)  # Fixture threshold .05s; no bookmark requirement.
        o.prerequisite();before=time.monotonic();o.close()
        self.assertLess(time.monotonic()-before,1)
        self.assertTrue(all(not t.is_alive() for t in o.threads.values()))
        self.assertEqual('closed',json.loads((self.directory/'control-watch.json').read_text())['phase'])
    def test_fixed_lease_expires_without_bookmarks_or_deadline_reset(self):
        o=self.create(lease=.35);self.wait(lambda:o.state['failure'] is not None)
        with self.assertRaises(m.ObserverRefused):o.prerequisite()
        self.assertEqual(6,len(self.fixture.requests))

    def test_late_valid_bookmark_cannot_renew_original_read_lease(self):
        o=self.create(lease=.6);deadline=o.deadline
        time.sleep(max(0,deadline-time.monotonic()-.12))
        for key in m.SCOPES:
            self.fixture.send(key,{'metadata':{'resourceVersion':'late-bookmark'}},kind='BOOKMARK')
        self.wait(lambda:len(o.state['observations'])==3)
        self.wait(lambda:o.state['failure'] is not None)
        self.assertLess(time.monotonic(),deadline+.15)
        self.assertEqual('deadline',o.state['failure']);self.assertEqual(deadline,o.deadline)
        o.close();self.assertTrue(all(not t.is_alive() for t in o.threads.values()))
    def test_explicit_owner_only_transition_requires_durable_intent_and_no_regression(self):
        o=self.create();self.stopped();o.trace.authorize_owner_resume()
        self.journal.record['quiescent']={'owner_resume_intent':{
            'identity':self.ids()['kustomization'],'state':'pending'}};self.journal.save()
        self.send('kustomization',value=False,rv='owner-open')
        o.check(self.ids(),stopped=True)
        self.send('helmrelease',value=False,rv='forbidden')
        self.wait(lambda:o.state['failure'] is not None)
        with self.assertRaises(m.ObserverRefused):o.prerequisite()
    def test_external_stop_without_intent_is_sticky(self):
        o=self.create();self.send('deployment',value=0,intent=False)
        self.wait(lambda:o.state['failure'] is not None)
        self.assertEqual('unowned_transition',o.state['failure'])
    def test_watch_lag_matches_exact_opaque_get_rv(self):
        o=self.create();obj=copy.deepcopy(self.objects['deployment']);obj['metadata']['resourceVersion']='opaque-z'
        self.objects['deployment']=obj
        sender=threading.Thread(target=lambda:(time.sleep(.05),self.fixture.send('deployment',obj)))
        sender.start();o.check(self.ids(),stopped=False);sender.join(1)
        self.assertEqual('opaque-z',o.trace.latest['deployment'])
    def test_uid_or_uncontrolled_spec_drift_is_sticky_and_private_payload_not_saved(self):
        o=self.create();obj=copy.deepcopy(self.objects['deployment'])
        obj['spec']['PRIVATE_SYNTHETIC_PAYLOAD']='PRIVATE_VALUE_21'
        self.fixture.send('deployment',obj);self.wait(lambda:o.state['failure'] is not None)
        self.assertNotIn('PRIVATE_VALUE_21',(self.directory/'control-watch.json').read_text())
        try:o.prerequisite()
        except m.ObserverRefused as error:
            self.assertNotIn('PRIVATE_VALUE_21',''.join(traceback.format_exception(error)))
            self.assertIsNone(error.__context__)
    def test_error410_is_sticky_no_relist(self):
        o=self.create();self.fixture.send('deployment',{'code':410,'message':'PRIVATE_STATUS'},kind='ERROR')
        self.wait(lambda:o.state['failure'] is not None)
        self.assertEqual('history_gap',o.state['failure']);self.assertEqual(6,len(self.fixture.requests))
        self.assertNotIn('PRIVATE_STATUS',(self.directory/'control-watch.json').read_text())
    def test_eof_is_sticky(self):
        o=self.create();self.fixture.queues['deployment'].put(None)
        self.wait(lambda:o.state['failure'] is not None)
        self.assertEqual('eof',o.state['failure'])
    def test_deleted_and_duplicate_json_refused(self):
        o=self.create();self.fixture.send('deployment',self.objects['deployment'],kind='DELETED')
        self.wait(lambda:o.state['failure'] is not None);self.assertEqual('event',o.state['failure'])
    def test_bound_overflow(self):
        o=self.create()
        with mock.patch.object(m,'MAX_BYTES',o.state['watch_bytes']+1):
            self.fixture.send('deployment',self.objects['deployment'])
            self.wait(lambda:o.state['failure'] is not None)
        self.assertEqual('overflow',o.state['failure'])
    def test_actual_fsync_failure_invalidates_borrowed_trace(self):
        o=self.create();original=os.fsync
        def flush(fd):
            if os.fstat(fd).st_ino==self.directory.stat().st_ino:raise OSError('PUBLIC_FAULT')
            return original(fd)
        with mock.patch.object(m.os,'fsync',side_effect=flush):
            self.fixture.send('deployment',self.objects['deployment'])
            self.wait(lambda:o.state['failure'] is not None)
        self.assertEqual('watch',o.trace.failure)
        with self.assertRaises(m.ObserverRefused):o.prerequisite()
    def test_replaced_sidecar_and_reopen_refuse(self):
        o=self.create();path=self.directory/'control-watch.json'
        replacement=self.directory/'substitute';replacement.write_bytes(path.read_bytes());replacement.chmod(0o600)
        os.replace(replacement,path)
        with self.assertRaises(m.ObserverRefused):o.prerequisite()
        with self.assertRaises(m.ObserverRefused):
            m.Observer(self.journal,self.pins,o.transport,deadline=time.monotonic()+5)
    def test_http410_start_closes_all_newly_owned_resources(self):
        with self.assertRaises(m.ObserverRefused):self.create(status=410)
        self.assertEqual('history_gap',self.observer.state['failure']);self.assertEqual({},self.observer.threads)
    def test_incomplete_typed_list_refused_before_watch(self):
        api,kind,_,_,_=m.SCOPES['deployment']
        pages={'deployment':{'apiVersion':api,'kind':kind+'List','metadata':{
            'resourceVersion':'opaque','continue':'more'},'items':[self.objects['deployment']]}}
        with self.assertRaises(m.ObserverRefused):self.create(pages=pages)
        self.assertEqual(1,len(self.fixture.requests))
    def test_typed_item_headers_may_be_omitted_only_under_correct_list(self):
        obj=copy.deepcopy(self.objects['deployment']);obj.pop('apiVersion');obj.pop('kind')
        pages={'deployment':{'apiVersion':'apps/v1','kind':'DeploymentList',
            'metadata':{'resourceVersion':'opaque-list'},'items':[obj]}}
        o=self.create(pages=pages);o.prerequisite()
        self.fixture.send('deployment',obj);self.wait(lambda:o.state['failure'] is not None)
        self.assertEqual('shape',o.state['failure'])
    def test_deadline_after_http200_stream_is_owned_and_closed(self):
        o=self.create(start=False);request=o.transport.request
        def late(key,query,deadline):
            result=request(key,query,deadline)
            if query.get('watch')=='true':o.deadline=time.monotonic()-1
            return result
        with mock.patch.object(o.transport,'request',side_effect=late),self.assertRaises(m.ObserverRefused):o.start()
        self.assertEqual(1,len(o.streams));self.assertTrue(o.stopping)

    def test_duplicate_json_names_are_refused_not_interpreted(self):
        o=self.create();self.fixture.send('deployment',raw=b'{"type":"MODIFIED","type":"BOOKMARK","object":{}}\n')
        self.wait(lambda:o.state['failure'] is not None)
        self.assertEqual([],o.state['observations'])

    def test_replacement_uid_refused_even_same_spec_and_name(self):
        o=self.create();obj=copy.deepcopy(self.objects['helmrelease']);obj['metadata']['uid']='foreign-uid'
        self.fixture.send('helmrelease',obj);self.wait(lambda:o.state['failure'] is not None)
        self.assertEqual('identity',o.state['failure'])

    def test_plain_error_never_stores_message_or_private_frames(self):
        o=self.create();self.fixture.send('kustomization',{'code':403,'message':'PRIVATE_ERROR_32'},kind='ERROR')
        self.wait(lambda:o.state['failure'] is not None)
        self.assertEqual('watch_error',o.state['failure'])
        self.assertNotIn('PRIVATE_ERROR_32',(self.directory/'control-watch.json').read_text())

    def test_bookmarks_are_durable_but_not_object_rv_substitutes(self):
        o=self.create();self.fixture.send('deployment',{'metadata':{'resourceVersion':'bookmark-z'}},kind='BOOKMARK')
        self.wait(lambda:len(o.state['observations'])==1)
        o.check(self.ids(),stopped=False)
        self.assertEqual('BOOKMARK',o.state['observations'][0]['type'])
        self.assertNotEqual('bookmark-z',o.trace.latest['deployment'])

    def test_insecure_fresh_options_refused_before_any_http_dispatch(self):
        o=self.create(start=False)
        def bad():return ssl._create_unverified_context(),{}
        o.transport.options=bad
        with self.assertRaises(m.ObserverRefused):o.start()
        self.assertEqual([],self.fixture.requests)

    def test_initial_fsync_fault_keeps_owned_sidecar_and_closes_fd(self):
        transport=m.TLSControls(self.options,'https://localhost:1')
        before=len(list(pathlib.Path('/proc/self/fd').iterdir()));original=os.fsync
        def fail(fd):
            if os.fstat(fd).st_ino==self.directory.stat().st_ino:raise OSError('PUBLIC_INIT_FAULT')
            return original(fd)
        with mock.patch.object(m.os,'fsync',side_effect=fail),self.assertRaises(m.ObserverRefused):
            m.Observer(self.journal,self.pins,transport,deadline=time.monotonic()+2)
        self.assertEqual(before,len(list(pathlib.Path('/proc/self/fd').iterdir())))
        self.assertTrue((self.directory/'control-watch.json').exists())

    def test_actual_get_mismatch_is_sticky_without_numeric_rv_sort(self):
        o=self.create();ids=self.ids();ids['deployment']['resourceVersion']='opaque-never-observed'
        o.deadline=time.monotonic()+.1
        with self.assertRaises(m.ObserverRefused):o.check(ids,stopped=False)
        self.assertIsNotNone(o.state['failure']);self.assertEqual(6,len(self.fixture.requests))

    def test_collection_missing_rv_refused_before_watch(self):
        pages={'deployment':{'apiVersion':'apps/v1','kind':'DeploymentList','metadata':{},
                             'items':[self.objects['deployment']]}}
        with self.assertRaises(m.ObserverRefused):self.create(pages=pages)
        self.assertEqual(1,len(self.fixture.requests))


if __name__=='__main__':unittest.main()
