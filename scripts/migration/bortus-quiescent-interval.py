"""Lease-bound cold client with borrowed live observer; no CLI or phase authority."""
import copy
import hashlib
import json
import math
import os
import pathlib
import selectors
import signal
import stat
import subprocess
import time

import importlib.util
import sys


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module); return module


watch = load('interval_observer', 'bortus-quiescent-watch.py')
archive = load('interval_archive_tools', 'bortus-quiescent-archive.py')
quiescent = watch.quiescent
cold = quiescent.cold
RUNTIME = cold.RUNTIME
spawn = subprocess.Popen
MAX_OUTPUT = 8 * 1024 * 1024
MAX_INPUT = 1024 * 1024
MAX_DISPATCHES = 10000


class Refused(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__('Quiescent interval refused: ' + code)


def need(value, code):
    if not value: raise Refused(code)


class IntervalClient(cold.Client):
    """Construct from this module's watch exports; outer caller owns observer/journal."""
    def __init__(self, observer, *, deadline):
        failure = None
        try:
            need(type(observer) is watch.Observer and type(observer.journal) is watch.ControlJournal,
                 'configuration')
            need(type(deadline) in (int, float) and math.isfinite(deadline) and
                 deadline == observer.deadline and time.monotonic() < deadline <= time.monotonic()+2100,
                 'deadline')
            observer.prerequisite()
            self.observer, self.journal, self.deadline = observer, observer.journal, deadline
            self._lease = deadline
            self.closed = False; self.active = False; self.inode = None; self.digest = None
            self.state = {'abi': 1, 'lease_id': observer.state['lease_id'],
                          'run_id': self.journal.record['run_id'], 'dispatches': [],
                          'data_acceptance': False}
            with self.journal.control_lock:
                self.journal._owned()
                fd = os.open('interval-client.json', os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,
                             0o600, dir_fd=self.journal.directory_fd)
                try:
                    i = os.fstat(fd); self.inode = (i.st_dev, i.st_ino); os.fsync(fd)
                finally: os.close(fd)
                os.fsync(self.journal.directory_fd)
                self._save()
        except Refused as error: failure = error.code
        except Exception: failure = 'initialization'
        observer = None
        if failure: raise Refused(failure)

    def _disk(self):
        self.journal._owned()
        fd = os.open('interval-client.json', os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,
                     dir_fd=self.journal.directory_fd)
        try:
            i = os.fstat(fd)
            need(stat.S_ISREG(i.st_mode) and stat.S_IMODE(i.st_mode) == 0o600 and
                 i.st_uid == os.getuid() and i.st_nlink == 1 and (i.st_dev, i.st_ino) == self.inode and
                 i.st_size <= 4*1024*1024, 'ownership')
            raw = os.read(fd, 4*1024*1024+1)
            now = os.fstat(fd); named = os.stat('interval-client.json', dir_fd=self.journal.directory_fd,
                                                follow_symlinks=False)
            fields = ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_uid','st_nlink')
            need(all(getattr(i,k) == getattr(now,k) == getattr(named,k) for k in fields) and
                 len(raw) == i.st_size and self.digest == hashlib.sha256(raw).hexdigest(), 'ownership')
        finally: os.close(fd)

    def _save(self):
        self.journal._owned()
        raw = (json.dumps(self.state, sort_keys=True, separators=(',', ':'))+'\n').encode()
        need(len(raw) <= 4*1024*1024, 'bound')
        if self.digest is not None: self._disk()
        name = 'interval-client-next.json'
        fd = os.open(name, os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW, 0o600,
                     dir_fd=self.journal.directory_fd)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as out: out.write(raw); out.flush(); os.fsync(fd)
            i = os.fstat(fd)
        finally: os.close(fd)
        if self.digest is not None: self._disk()
        os.replace(name, 'interval-client.json', src_dir_fd=self.journal.directory_fd,
                   dst_dir_fd=self.journal.directory_fd)
        self.inode = (i.st_dev, i.st_ino); self.digest = hashlib.sha256(raw).hexdigest()
        os.fsync(self.journal.directory_fd)

    def _before(self):
        need(not self.closed and self.deadline == self._lease == self.observer.deadline and
             time.monotonic() < self._lease, 'deadline')
        self.observer.prerequisite()
        with self.journal.control_lock: self._disk()

    def _control_reply(self, kind, obj):
        if kind not in watch.SCOPES: return
        projection = self.observer._project(kind, obj)
        with self.observer.condition:
            until = min(self.deadline, time.monotonic()+3)
            while True:
                self.observer._live()
                if self.observer.trace.latest.get(kind) == projection['resourceVersion']: break
                need(time.monotonic() < until, 'trace_rv')
                self.observer.condition.wait(min(.05, until-time.monotonic()))

    def _read_args(self, kind, name, namespace):
        r = self.journal.record; ids = r['baseline']['identities']
        fixed = {'pvc': ('bortus-data', 'bortus'), 'pv': (ids['pv']['name'], None),
                 'storageclass': ('longhorn', None),
                 'volumes.longhorn.io': (ids['longhorn_volume']['name'], 'longhorn-system'),
                 'backuptargets.longhorn.io': ('default', 'longhorn-system'),
                 'snapshots.longhorn.io': (r['snapshot_name'], 'longhorn-system'),
                 'backups.longhorn.io': (r['backup_name'], 'longhorn-system'),
                 'pod': (r['holder_proposal']['metadata']['name'], 'bortus'),
                 'replicaset': (ids['replica_set']['name'], 'bortus')}
        fixed.update({k: (v[1], v[2]) for k, v in cold.RESOURCES.items()})
        if kind == 'pvs':
            need(name is None and namespace is None, 'scope')
            return ['get', '--raw', '/api/v1/persistentvolumes?limit=10001']
        if kind == 'pods':
            need(name is None and namespace == 'bortus', 'scope')
            return ['get', '--raw', '/api/v1/namespaces/bortus/pods?limit=10001']
        need(kind in fixed and (name, namespace) == fixed[kind], 'scope')
        return ['get', kind, name] + (['-n', namespace] if namespace else []) + ['-o', 'json']

    def _intent(self, action, body):
        r = self.journal.record
        with self.journal.control_lock:
            self.journal._owned()
            raw, inode = self.journal._read('journal.json', 1024*1024)
            need(inode == self.journal.journal_inode and
                 quiescent.sha(json.loads(raw)) == quiescent.sha(r), 'intent_not_durable')
        if action in cold.RESOURCES:
            entry = r['controls'][action]; intent = entry.get('intent', {})
            uid, rv, field = entry['identity']['uid'], intent.get('resourceVersion'), cold.RESOURCES[action][3]
            need(intent.get('state') == 'pending' and watch.text(rv), 'intent')
            first = [{'op':'test','path':'/metadata/uid','value':uid},
                     {'op':'test','path':'/metadata/resourceVersion','value':rv}]
            tail = {'op':'add','path':'/spec/'+field,'value':intent['to']}
            expected = first+[{'op':'test','path':'/spec/'+field,'value':intent['from']},tail]
            need(quiescent.sha(body) in (quiescent.sha(expected),quiescent.sha(first+[tail])), 'cas')
            need(type(intent['from']) is type(quiescent.TARGETS[action]) and
                 type(intent['to']) is type(quiescent.TARGETS[action]), 'cas')
            allowed = intent['to'] == quiescent.TARGETS[action]
            if action == 'kustomization' and intent['from'] is True and intent['to'] is False:
                owner = r.get('quiescent', {}).get('owner_resume_intent', {})
                allowed = owner.get('state') == 'pending' and owner.get('identity', {}).get('uid') == uid and self.observer.trace.owner_resume_authorized
            need(allowed and intent['from'] != intent['to'], 'cas')
            return uid, rv
        if action == 'holder-delete':
            intent = r.get('holder_delete_intent', {}); i = intent.get('identity', {})
            need(intent.get('state') == 'pending' and
                 all(i.get(k) == r.get('holder_identity', {}).get(k) for k in ('name','namespace','uid')) and
                 body == {'apiVersion':'v1','kind':'DeleteOptions', 'preconditions':{
                     'uid':i.get('uid'),'resourceVersion':i.get('resourceVersion')}}, 'intent')
            return i['uid'], i['resourceVersion']
        label = action.removeprefix('create-')
        need(label in ('holder','snapshot','backup') and r.get(label+'_create_state') == 'pending' and
             label+'_identity' not in r, 'intent')
        if label == 'holder': expected = r['holder_proposal']
        else:
            volume = r['baseline']['identities']['longhorn_volume']['name']
            expected = {'apiVersion':'longhorn.io/v1beta2','kind':'Snapshot' if label=='snapshot' else 'Backup',
                'metadata':{'name':r[label+'_name'],'namespace':'longhorn-system','labels':{
                    'bortus-checkpoint':r['run_id']}},
                'spec':{'volume':volume,'createSnapshot':True,'labels':{'bortus-consistency':'cold-writer-stopped'}}}
            if label == 'backup':
                expected['metadata']['labels'].update({'backup-volume':volume,'backup-target':'default'})
                expected['spec']={'snapshotName':r['snapshot_name'],'backupMode':'full',
                                  'labels':{'bortus-consistency':'cold-writer-stopped'}}
        need(quiescent.sha(body) == quiescent.sha(expected), 'proposal')
        return None, None

    def _child(self, action, args, body, persistent, expected):
        child = selector = None; fds = []; output = bytearray(); failure = None; result = None
        try:
            path = RUNTIME/'admin.conf'
            fd, fds, anchors, fingerprint = archive.reader.pin_config(path)
            archive.reader.check_pinned(path, fd, fingerprint, anchors)
            self._before()
            if persistent: need(self._intent(action, body) == expected, 'intent')
            end = min(self.deadline, time.monotonic()+20)
            left = end-time.monotonic(); need(left > 0, 'deadline')
            data = b'' if body is None else json.dumps(body, allow_nan=False, separators=(',', ':')).encode()
            need(len(data) <= MAX_INPUT, 'bound')
            argv = [str(RUNTIME/'bin/kubectl'), '--kubeconfig', '/proc/self/fd/'+str(fd),
                    '--request-timeout='+str(left)+'s', *args]
            child = spawn(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          pass_fds=(fd,), start_new_session=True)
            selector = selectors.DefaultSelector()
            os.set_blocking(child.stdout.fileno(), False); selector.register(child.stdout, selectors.EVENT_READ)
            os.set_blocking(child.stdin.fileno(), False)
            pending = memoryview(data)
            if pending: selector.register(child.stdin, selectors.EVENT_WRITE)
            else: child.stdin.close()
            while selector.get_map():
                self._before(); need(time.monotonic() < end, 'deadline')
                for key, _ in selector.select(min(.05, end-time.monotonic())):
                    if key.fileobj is child.stdin:
                        n = os.write(child.stdin.fileno(), pending[:65536]); pending = pending[n:]
                        if not pending: selector.unregister(child.stdin); child.stdin.close()
                    else:
                        raw = os.read(child.stdout.fileno(), min(65536, MAX_OUTPUT-len(output)+1))
                        need(len(output)+len(raw) <= MAX_OUTPUT, 'bound')
                        if raw: output.extend(raw)
                        else: selector.unregister(child.stdout)
            need(child.wait(timeout=max(0, end-time.monotonic())) == 0, 'transport')
            archive.reader.check_pinned(path, fd, fingerprint, anchors)
            self._before()
            result = json.loads(output)
            need(type(result) is dict, 'reply')
        except Refused as error: failure = error.code
        except Exception: failure = 'transport'
        finally:
            if selector:
                try: selector.close()
                except Exception: failure = 'cleanup'
            if child:
                # The session is exclusively created above. Also stop descendants
                # holding a pipe after the direct child has already exited.
                try: os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                except Exception: failure = 'cleanup'
            try: archive.Children(self.deadline)(child)
            except Exception: failure = 'cleanup'
            if child:
                for stream in (child.stdin, child.stdout, child.stderr):
                    if stream:
                        try: stream.close()
                        except Exception: failure = 'cleanup'
            try: archive.reader.close_descriptors(fds)
            except Exception: failure = 'cleanup'
        body = output = data = pending = None
        return (None if failure else result), failure

    def _dispatch(self, action, args, body, kind=None, persistent=False):
        need(not self.active, 'concurrent'); self.active = True
        entry = None
        try:
            self._before()
            uid = rv = None
            if persistent: uid, rv = self._intent(action, body)
            proposal = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            intent_key = action + (':'+json.dumps(body[-1]['value']) if action in cold.RESOURCES else '')
            with self.journal.control_lock:
                self._disk(); need(len(self.state['dispatches']) < MAX_DISPATCHES, 'bound')
                if action != 'read':
                    need(not any(e['intent_key']==intent_key for e in self.state['dispatches']), 'replay')
                entry = {'action':action,'intent_key':intent_key,'proposal_sha256':proposal,'state':'pending','uid':uid,'resourceVersion':rv}
                self.state['dispatches'].append(entry); self._save()
            value, failure = self._child(action, args, body, persistent, (uid,rv))
            if failure: raise Refused(failure)
            self._before()
            if kind: self._control_reply(kind, value)
            if action.startswith('create-') or action == 'dry-run-holder':
                need(value.get('apiVersion') == body['apiVersion'] and value.get('kind') == body['kind'] and
                     value.get('metadata',{}).get('name') == body['metadata']['name'] and
                     value['metadata'].get('namespace') == body['metadata']['namespace'], 'reply')
                if action != 'dry-run-holder': cold.identity(value)
            with self.journal.control_lock: entry['state']='confirmed'; self._save()
            return value
        except Exception:
            if entry:
                with self.journal.control_lock:
                    entry['state']='uncertain'; self._save()
            raise
        finally: self.active = False

    def _public(self, action, args, body=None, kind=None, persistent=False):
        value = failure = None
        try: value = self._dispatch(action, args, body, kind, persistent)
        except Refused as error: failure = error.code
        except Exception: failure = 'operation'
        args = body = None
        if failure: value = None; raise Refused(failure)
        return value

    def get(self, kind, name=None, namespace=None):
        failure = None; args = value = None
        try:
            args = self._read_args(kind, name, namespace)
            value = self._public('read', args, kind=kind)
            if kind == 'pods': cold.preflight.complete_pods(value)
        except Refused as error: failure = error.code
        except Exception: failure = 'read'
        name = namespace = args = None
        if failure: value = None; raise Refused(failure)
        return value

    def change(self, kind, name, ns, patch):
        failure = value = None
        try:
            need(kind in cold.RESOURCES and (name, ns) == cold.RESOURCES[kind][1:3], 'scope')
            value = self._public(kind, ['patch',kind,name,'-n',ns,'--type=json','--patch-file=/dev/stdin','-o','json'], patch, kind, True)
        except Refused as error: failure = error.code
        except Exception: failure = 'operation'
        patch = None
        if failure: value = None; raise Refused(failure)
        return value

    def create(self, body, dry_run=False):
        failure = value = None
        try:
            need(type(dry_run) is bool, 'scope')
            label = 'holder' if body.get('metadata',{}).get('name') == self.journal.record['holder_proposal']['metadata']['name'] else None
            if label is None: label = next((k for k in ('snapshot','backup') if body.get('metadata',{}).get('name') == self.journal.record[k+'_name']), None)
            need(label is not None, 'scope')
            if dry_run: need(label == 'holder' and quiescent.sha(body) == quiescent.sha(self.journal.record['holder_proposal']) and self.journal.record.get('quiescent',{}).get('state')=='pending', 'proposal')
            action = 'dry-run-holder' if dry_run else 'create-'+label
            value = self._public(action, ['create','-f','-','-o','json']+(['--dry-run=server'] if dry_run else []), body, persistent=not dry_run)
            need(value.get('apiVersion') == body['apiVersion'] and value.get('kind') == body['kind'] and
                 value.get('metadata',{}).get('name') == body['metadata']['name'] and value['metadata'].get('namespace') == body['metadata']['namespace'], 'reply')
            if not dry_run: cold.identity(value)
        except Refused as error: failure = error.code
        except Exception: failure = 'reply'
        body = None
        if failure: value = None; raise Refused(failure)
        return value

    def delete_holder(self, obj):
        failure = value = None
        try:
            i = cold.identity(obj); r = self.journal.record
            need(all(i[k] == r.get('holder_identity',{}).get(k) for k in ('name','namespace','uid')) and i['namespace']=='bortus', 'intent')
            fresh = self.get('pod', i['name'], 'bortus')
            need(cold.identity(fresh) == i and not fresh['metadata'].get('deletionTimestamp'), 'intent')
            value = self._public('holder-delete', ['delete','--raw','/api/v1/namespaces/bortus/pods/'+i['name'],'-f','-'],
                {'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':i['uid'],'resourceVersion':i['resourceVersion']}}, persistent=True)
        except Refused as error: failure = error.code
        except Exception: failure = 'operation'
        obj = None
        if failure: value = None; raise Refused(failure)
        return value

    def request(self, args, body):
        args = body = None
        raise Refused('scope')

    def close(self):
        need(not self.active, 'concurrent')
        self.closed = True  # Borrowed observer/journal remain independently owned.
