"""Owned durable three-control TLS observer; no CLI, mutation or data acceptance."""
import copy
import hashlib
import http.client
import importlib.util
import json
import math
import os
import pathlib
import socket
import ssl
import stat
import threading
import time
import uuid
from urllib.parse import urlencode, urlsplit


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


quiescent = load('quiescent_observer_source', 'bortus-quiescent-source.py')
watch = load('quiescent_observer_decoder', 'bortus-restore-watch.py')
credentials = load('quiescent_observer_credentials', 'bortus-operator-mtls.py')
ORIGIN = 'https://192.168.0.4:6443'
SCOPES = {
    'deployment': ('apps/v1', 'Deployment', 'bortus', 'bortus', '/apis/apps/v1/namespaces/bortus/deployments'),
    'helmrelease': ('helm.toolkit.fluxcd.io/v2', 'HelmRelease', 'flux-system', 'bortus',
                    '/apis/helm.toolkit.fluxcd.io/v2/namespaces/flux-system/helmreleases'),
    'kustomization': ('kustomize.toolkit.fluxcd.io/v1', 'Kustomization', 'flux-system', 'migration-releases',
                      '/apis/kustomize.toolkit.fluxcd.io/v1/namespaces/flux-system/kustomizations')}
MAX_FRAME = 1024 * 1024
MAX_BYTES = 8 * 1024 * 1024
MAX_EVENTS = 9997  # Plus three initial LIST projections fits ControlTrace's 10000 bound.


class ObserverRefused(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__('Quiescent observer refused: ' + code)


def need(value, code):
    if not value: raise ObserverRefused(code)


def text(value, limit=256):
    return type(value) is str and 0 < len(value) <= limit and all(32 <= ord(c) < 127 for c in value)


class ControlJournal(quiescent.cold.Journal):
    """One short lock for descriptor/file identity and durable sidecar saves, never TLS IO."""
    def __init__(self, directory, record=None):
        self.control_lock = threading.RLock()
        super().__init__(directory, record)

    def save(self):
        with self.control_lock: return super().save()

    def close(self):
        with self.control_lock: return super().close()


class TLSControls:
    def __init__(self, options, approved_origin=ORIGIN):
        result, failure = None, None
        try: result = self._configure(options, approved_origin)
        except Exception: failure = 'configuration'
        approved_origin = None
        if failure:
            options = None
            raise ObserverRefused(failure)
        self.host, self.port, self.options = result

    @staticmethod
    def _configure(options, approved_origin):
        origin = urlsplit(approved_origin)
        need(callable(options) and (approved_origin == ORIGIN or
             (origin.scheme == 'https' and origin.hostname in ('localhost', '127.0.0.1') and
              origin.port is not None and origin.path == '' and not origin.query and
              not origin.fragment and not origin.username and not origin.password)), 'configuration')
        return origin.hostname, origin.port or 443, options

    def _request(self, key, query, deadline):
        connection = response = None
        failure = None
        try:
            need(time.monotonic() < deadline, 'deadline')
            context, headers = self.options()  # Fresh verified operator options on every connection.
            need(type(context) is ssl.SSLContext and context.check_hostname and
                 context.verify_mode == ssl.CERT_REQUIRED and context.minimum_version >= ssl.TLSVersion.TLSv1_2
                 and type(headers) is dict and set(headers) <= {'Authorization'} and
                 all(text(v, 16384) for v in headers.values()), 'tls')
            need(time.monotonic() < deadline, 'deadline')
            connection = http.client.HTTPSConnection(self.host, self.port, context=context,
                timeout=min(30, deadline-time.monotonic()))
            connection.connect()
            connection._owned_socket = connection.sock
            need(isinstance(connection.sock, ssl.SSLSocket) and connection.sock.getpeercert() and
                 connection.sock.version() in ('TLSv1.2', 'TLSv1.3'), 'tls')
            need(time.monotonic() < deadline, 'deadline')
            connection.sock.settimeout(min(30, deadline-time.monotonic()))
            connection.request('GET', SCOPES[key][4]+'?'+urlencode(query),
                headers={'Accept':'application/json', 'Accept-Encoding':'identity', **headers})
            headers = None
            need(time.monotonic()<deadline,'deadline')
            connection._owned_socket.settimeout(min(30,deadline-time.monotonic()))
            response = connection.getresponse()
            need(time.monotonic() < deadline, 'deadline')
            need(response.status != 410, 'history_gap')
            need(response.status == 200 and response.getheader('Content-Encoding','identity') == 'identity'
                 and response.getheader('Content-Type','').split(';',1)[0].strip() == 'application/json', 'http')
            return (connection, response), None
        except ObserverRefused as error: failure = error.code
        except Exception: failure = 'transport'
        for owned in (response, connection):
            if owned:
                try: owned.close()
                except Exception: failure = 'cleanup'
        return None, failure

    def request(self, key, query, deadline):
        result, failure = self._request(key, query, deadline)
        if failure: raise ObserverRefused(failure)
        return result

    def initial(self, key, deadline):
        connection, response = self.request(key, {'fieldSelector':'metadata.name='+SCOPES[key][3],
                                                 'limit':2}, deadline)
        value, failure = None, None
        try:
            parts, count = [], 0
            while True:
                need(time.monotonic() < deadline, 'deadline')
                connection._owned_socket.settimeout(min(30,deadline-time.monotonic()))
                raw = response.read(min(65536, MAX_FRAME-count+1)); count += len(raw)
                need(count <= MAX_FRAME, 'list_bound')
                if not raw: break
                parts.append(raw)
            value = (watch.decode(b''.join(parts)), count)
        except ObserverRefused as error: failure = error.code
        except Exception: failure = 'list'
        for owned in (response, connection):
            try: owned.close()
            except Exception: failure = 'cleanup'
        return (None if failure else value), failure


class Observer:
    def __init__(self, journal, pins, transport, *, deadline):
        failure = None
        try: self._initialize(journal, pins, transport, deadline)
        except ObserverRefused as error: failure = error.code
        except Exception: failure = 'initialization'
        pins = None
        if failure: raise ObserverRefused(failure)

    def _initialize(self, journal, pins, transport, deadline):
        need(type(journal) is ControlJournal and type(transport) is TLSControls and
             type(deadline) in (int,float) and math.isfinite(deadline) and
             time.monotonic() < deadline <= time.monotonic()+2100, 'configuration')
        self.journal, self.transport, self.deadline = journal, transport, deadline
        self.lock = journal.control_lock
        self.condition = threading.Condition(self.lock)
        self.streams, self.threads, self.ready_events = {}, {}, {}
        self.trace = None
        self.stopping = False
        self.inode = self.digest = None
        self.state = {'abi':1, 'phase':'starting', 'failure':None, 'run_id':journal.record['run_id'],
            'collector_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
            'lease_id':uuid.uuid4().hex, 'pins':{}, 'collection_rvs':{},
            'watch_handles':{}, 'initial':{}, 'observations':[], 'list_bytes':0, 'watch_bytes':0, 'frames':0,
            'data_acceptance':False}
        # Validate pins before dispatch without constructing caller-supplied fake readiness.
        probe = quiescent.ControlTrace(pins, {'source_sha256':self.state['collector_sha256'],
            'receipt_sha256':'0'*64, 'collection_rvs':{k:'pending' for k in SCOPES},
            'watch_handles':{k:'pending' for k in SCOPES}})
        need(all(pins[k]['name'] == SCOPES[k][3] and pins[k]['namespace'] == SCOPES[k][2]
                 and text(pins[k]['uid']) for k in SCOPES) and pins['deployment']['original'] == 1,
             'configuration')
        self.state['pins'] = copy.deepcopy(pins)
        with self.lock:
            journal._owned()
            need('quiescent' not in journal.record, 'replay')
            fd = os.open('control-watch.json', os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,
                         0o600, dir_fd=journal.directory_fd)
            try:
                info=os.fstat(fd); self.inode=(info.st_dev,info.st_ino); os.fsync(fd)
            finally: os.close(fd)
            os.fsync(journal.directory_fd)
            self._save()

    def _disk(self):
        self.journal._owned()
        fd=os.open('control-watch.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,
                   dir_fd=self.journal.directory_fd)
        try:
            info=os.fstat(fd)
            need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1 and
                 stat.S_IMODE(info.st_mode)==0o600 and info.st_size<=MAX_BYTES and
                 (info.st_dev,info.st_ino)==self.inode, 'ownership')
            raw=os.read(fd,MAX_BYTES+1)
            after=os.fstat(fd)
            need(len(raw)==info.st_size and len(raw)<=MAX_BYTES and
                 all(getattr(after,k)==getattr(info,k) for k in
                     ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink')) and
                 (self.digest is None or hashlib.sha256(raw).hexdigest()==self.digest),
                 'ownership')
            return raw
        finally: os.close(fd)

    def _save(self):
        self._disk()
        need(set(self.state)=={'abi','phase','failure','run_id','collector_sha256','lease_id','pins',
            'collection_rvs','watch_handles','initial','observations','list_bytes','watch_bytes','frames',
            'data_acceptance'} and self.state['abi']==1 and self.state['data_acceptance'] is False and
            self.state['phase'] in ('starting','ready','failed','closed') and
            self.state['run_id']==self.journal.record['run_id'] and
            quiescent.digest(self.state['collector_sha256']) and text(self.state['lease_id'],32) and
            (self.state['failure'] is None or text(self.state['failure'],64)) and
            all(type(self.state[k]) is int and 0<=self.state[k]<=limit for k,limit in
                (('list_bytes',3*MAX_FRAME),('watch_bytes',MAX_BYTES),('frames',MAX_EVENTS))) and
            all(type(self.state[k]) is dict and set(self.state[k])<=set(SCOPES) and
                all(text(v) for v in self.state[k].values()) for k in ('collection_rvs','watch_handles')) and
            len(self.state['observations'])<=MAX_EVENTS and
            all(set(e) in ({'type','resource','uid','resourceVersion','spec_sha256','value','sequence'},
                          {'type','resource','resourceVersion','sequence'}) and
                e['resource'] in SCOPES and text(e['resourceVersion']) and type(e['sequence']) is int and
                0<e['sequence']<=self.state['frames'] and
                ((e['type']=='BOOKMARK' and 'value' not in e) or
                 (e['type']=='MODIFIED' and e.get('uid')==self.state['pins'][e['resource']]['uid'] and
                  e.get('spec_sha256')==self.state['pins'][e['resource']]['spec_sha256'] and
                  type(e.get('value')) is type(quiescent.TARGETS[e['resource']])))
                for e in self.state['observations']),
            'proof_schema')
        raw=(json.dumps(self.state,separators=(',',':'),sort_keys=True)+'\n').encode()
        need(len(raw)<=MAX_BYTES,'proof_bound')
        name='control-watch-'+uuid.uuid4().hex+'.next'
        fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=self.journal.directory_fd)
        try:
            with os.fdopen(fd,'wb',closefd=False) as out:
                out.write(raw);out.flush();os.fsync(fd);info=os.fstat(fd); inode=(info.st_dev,info.st_ino)
        finally:os.close(fd)
        self._disk()
        os.replace(name,'control-watch.json',src_dir_fd=self.journal.directory_fd,dst_dir_fd=self.journal.directory_fd)
        os.fsync(self.journal.directory_fd)
        self.inode,self.digest=inode,hashlib.sha256(raw).hexdigest()
        self._disk()

    def _fail(self, code):
        with self.lock:
            if self.trace: self.trace.fail()
            if self.state['failure'] is None:
                self.state.update(phase='failed',failure=code)
                try:self._save()
                except Exception:pass  # In-memory refusal remains sticky when durable IO itself failed.
            self.condition.notify_all()

    def _project(self, key, obj, *, typed=False):
        api,kind,ns,name,_=SCOPES[key]
        need(type(obj) is dict and obj.get('apiVersion',api if typed else None)==api and
             obj.get('kind',kind if typed else None)==kind, 'shape')
        meta=obj.get('metadata'); body=obj.get('spec')
        need(type(meta) is dict and type(body) is dict and meta.get('name')==name and meta.get('namespace')==ns
             and meta.get('uid')==self.state['pins'][key]['uid'] and text(meta.get('resourceVersion')) and
             not meta.get('deletionTimestamp'), 'identity')
        field=quiescent.cold.RESOURCES[key][3]; value=body.get(field,False if field=='suspend' else None)
        need(type(value) is type(quiescent.TARGETS[key]) and
             quiescent.control_spec(obj,key)==self.state['pins'][key]['spec_sha256'],'spec')
        return {'type':'MODIFIED','resource':key,'uid':meta['uid'],'resourceVersion':meta['resourceVersion'],
                'spec_sha256':self.state['pins'][key]['spec_sha256'],'value':value}

    def _transition(self, projection):
        key=projection['resource']
        previous=self.state['initial'][key]['value']
        for event in reversed(self.state['observations']):
            if event['resource']==key and 'value' in event:
                previous=event['value'];break
        if previous==projection['value']:return
        entry=self.journal.record.get('controls',{}).get(key,{})
        intent=entry.get('intent',{})
        need(entry.get('identity',{}).get('uid')==projection['uid'] and
             intent.get('state') in ('pending','confirmed') and
             type(intent.get('from')) is type(previous) and intent['from']==previous and
             type(intent.get('to')) is type(projection['value']) and intent['to']==projection['value'],
             'unowned_transition')
        if key=='kustomization' and projection['value'] is False:
            owner=self.journal.record.get('quiescent',{}).get('owner_resume_intent',{})
            need(owner.get('state') in ('pending','confirmed') and
                 owner.get('identity',{}).get('uid')==projection['uid'] and self.trace is not None and
                 self.trace.owner_resume_authorized, 'unowned_transition')

    def _start(self):
        need(self.state['phase']=='starting' and not self.streams,'replay')
        for key in SCOPES:
            need(self.state['failure'] is None and time.monotonic()<self.deadline, 'not_live')
            result,failure=self.transport.initial(key,self.deadline)
            if failure: raise ObserverRefused(failure)
            obj,count=result; api,kind,_,_,_=SCOPES[key]; meta=obj.get('metadata')
            need(obj.get('apiVersion')==api and obj.get('kind')==kind+'List' and type(meta) is dict and
                 text(meta.get('resourceVersion')) and meta['resourceVersion']!='0' and
                 meta.get('continue','')=='' and ('remainingItemCount' not in meta or
                 type(meta['remainingItemCount']) is int and meta['remainingItemCount']==0) and
                 type(obj.get('items')) is list and len(obj['items'])==1,'list')
            projection=self._project(key,obj['items'][0],typed=True)
            need(projection['value']==self.state['pins'][key]['original'],'initial_control')
            with self.lock:
                self.state['list_bytes']+=count
                self.state['collection_rvs'][key]=meta['resourceVersion']
                self.state['initial'][key]=projection
                self._save()
            stream=self.transport.request(key,{'fieldSelector':'metadata.name='+SCOPES[key][3], 'watch':'true',
                'resourceVersion':meta['resourceVersion'], 'allowWatchBookmarks':'true',
                'timeoutSeconds':max(1,int(self.deadline-time.monotonic()))},self.deadline)
            self.streams[key]=stream  # Own before deadline/socket/durability checks can throw.
            need(time.monotonic()<self.deadline,'deadline')
            stream[0]._owned_socket.settimeout(self.deadline-time.monotonic())
            self.ready_events[key]=threading.Event()
            with self.lock:
                self.state['watch_handles'][key]=uuid.uuid4().hex
                self._save()
            thread=threading.Thread(target=self._read,args=(key,),name='bortus-control-'+key,daemon=True)
            self.threads[key]=thread;thread.start()
            need(self.ready_events[key].wait(min(3,max(0,self.deadline-time.monotonic()))),'reader_start')
        with self.lock:
            self._live(starting=True)
            self.state['phase']='ready';self._save()
            ready={'source_sha256':self.state['collector_sha256'],'receipt_sha256':self.digest,
                'collection_rvs':self.state['collection_rvs'],'watch_handles':self.state['watch_handles']}
            self.trace=quiescent.ControlTrace(self.state['pins'],ready)
            for event in self.state['initial'].values():self.trace.observe(event)
            for event in self.state['observations']:
                if 'value' in event:self.trace.observe({k:v for k,v in event.items() if k!='sequence'})
            self._trace_check=self.trace.check
            self.trace.check=self.check
            return self

    def start(self):
        failure=None
        try:return self._start()
        except ObserverRefused as error:failure=error.code
        except Exception:failure='start'
        self._fail(failure)
        try:self.close()
        except Exception:pass
        raise ObserverRefused(failure)

    def _read(self,key):
        connection,response=self.streams[key]
        self.ready_events[key].set()
        try:
            while not self.stopping:
                need(time.monotonic()<self.deadline,'deadline')
                connection._owned_socket.settimeout(self.deadline-time.monotonic())
                raw=response.readline(MAX_FRAME+1)
                with self.lock:
                    if self.stopping:return
                    self.state['watch_bytes']+=len(raw);self.state['frames']+=1
                    need(self.state['watch_bytes']<=MAX_BYTES and len(raw)<=MAX_FRAME and
                         self.state['frames']<=MAX_EVENTS,'overflow')
                    need(raw and raw.endswith(b'\n'),'eof')
                    need(time.monotonic()<self.deadline,'deadline')
                    event=watch.decode(raw)
                    need(set(event)=={'type','object'},'event')
                    if event['type']=='ERROR':
                        need(not (type(event['object']) is dict and event['object'].get('code')==410),'history_gap')
                        raise ObserverRefused('watch_error')
                    if event['type']=='BOOKMARK':
                        obj=event['object'];meta=obj.get('metadata') if type(obj) is dict else None
                        need(type(meta) is dict and set(meta)=={'resourceVersion'} and text(meta['resourceVersion']),
                             'bookmark')
                        projection={'resource':key,'type':'BOOKMARK','resourceVersion':meta['resourceVersion']}
                    else:
                        need(event['type'] in ('ADDED','MODIFIED'),'event')
                        projection=self._project(key,event['object'])
                        self._transition(projection)
                        if self.trace:self.trace.observe(projection)
                    projection['sequence']=self.state['frames']
                    self.state['observations'].append(projection)
                    self._save();self.condition.notify_all()
        except ObserverRefused as error:
            if not self.stopping:self._fail(error.code)
        except Exception:
            if not self.stopping:self._fail('deadline' if time.monotonic()>=self.deadline else 'read')
        finally:
            for owned in (response,connection):
                try:owned.close()
                except Exception:
                    if not self.stopping:self._fail('cleanup')

    def _live(self,*,starting=False):
        need(not self.stopping and self.state['failure'] is None and
             self.state['phase'] in (('starting','ready') if starting else ('ready',)) and
             time.monotonic()<self.deadline and set(self.threads)==set(SCOPES) and
             all(t.is_alive() for t in self.threads.values()),'not_live')
        self._disk()

    def check(self,identities,*,stopped):
        failure=None
        try:
            with self.condition:
                until=min(self.deadline,time.monotonic()+3)
                while True:
                    self._live()
                    if all(self.trace.latest.get(k)==identities[k]['resourceVersion'] for k in SCOPES):break
                    need(time.monotonic()<until,'observation_rv')
                    self.condition.wait(min(.05,until-time.monotonic()))
                self._trace_check(identities,stopped=stopped)
        except ObserverRefused as error:failure=error.code
        except Exception:failure='trace'
        identities=None
        if failure:
            self._fail(failure);raise ObserverRefused(failure)

    def prerequisite(self):
        failure=None;value=None
        try:
            with self.lock:
                self._live()
                value={'lease_id':self.state['lease_id'],'durable_record_sha256':self.digest,
                    'sequence':self.state['frames'],'collection_rvs':copy.deepcopy(self.state['collection_rvs']),
                    'data_acceptance':False}
        except Exception:failure='not_live'
        if failure:
            self._fail(failure);raise ObserverRefused(failure)
        return value

    def close(self):
        with self.lock:
            self.stopping=True
            if self.trace:self.trace.fail()
            self.condition.notify_all()
        failed=False
        for connection,response in list(self.streams.values()):
            try:connection._owned_socket.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            except Exception:failed=True
            for owned in (response,connection):
                try:owned.close()
                except Exception:failed=True
        for thread in self.threads.values():
            if thread is not threading.current_thread():thread.join(3)
            if thread.is_alive():failed=True
        with self.lock:
            if self.state['failure'] is None:
                self.state['phase']='closed'
                try:self._save()
                except Exception:failed=True
        if failed:raise ObserverRefused('cleanup')
