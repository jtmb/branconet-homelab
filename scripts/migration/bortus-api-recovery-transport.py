"""Explicit isolated API recovery transport. No CLI, material producer or live authority."""
import copy
import functools
import hashlib
import importlib.util
import json
import math
import os
import pathlib
import re
import selectors
import struct
import subprocess
import time


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


backup = load('api_recovery_backup', 'backup-etcd.py')
specs = load('api_recovery_fixed_specs', 'bortus-api-recovery-specs.py')
MAGIC = b'BORTUS-API-PROOF\0'
KINDS = {'policy': ('networking.k8s.io/v1', 'NetworkPolicy',
                   '/apis/networking.k8s.io/v1/namespaces/migration-system/networkpolicies'),
         'configmap': ('v1', 'ConfigMap', '/api/v1/namespaces/migration-system/configmaps'),
         'pod': ('v1', 'Pod', '/api/v1/namespaces/migration-system/pods')}
BINDINGS = {'source_receipt_sha256', 'material_receipt_sha256',
            'cache_receipt_sha256', 'isolation_receipt_sha256'}
ACTIONS = {k + '-' + op for k in KINDS for op in ('create', 'delete')} | {
    'bundle', 'restore', 'etcd-start', 'api-add', 'tls-ready', 'oracle'}

# Public fixed source only: no material interpolation, arbitrary endpoint or
# extra mode in the unchanged CJS oracle. /readyz v1.37.1 returns literal "ok".
TLS_READY_PROGRAM = r"""'use strict';
const https=require('node:https'),tls=require('node:tls'),crypto=require('node:crypto');
const p=require('/program/bortus-api-secret-proof.cjs');
const clock=new p.Clock();let root=null,credentials=null,received=0;
const need=v=>{if(!v)throw new Error('API readiness refused')};
async function header(){
 const parts=[];let count=0;
 const timer=setTimeout(()=>process.stdin.destroy(new Error('API readiness refused')),clock.left());
 try{for await(const part of process.stdin){clock.left();count+=part.length;need(count<=21);parts.push(part)}}finally{clearTimeout(timer)}
 const h=Buffer.concat(parts);need(h.length===21&&h.subarray(0,17).equals(p.MAGIC));clock.narrow(h.readUInt32BE(17));
}
function attempt(){return new Promise((resolve,reject)=>{
 let settled=false,req=null,timer=null;
 const finish=(error,ready)=>{if(settled)return;settled=true;clearTimeout(timer);if(req)req.destroy();error?reject(new Error('API readiness refused')):resolve(ready)};
 timer=setTimeout(()=>finish(null,false),Math.min(2000,clock.left()));
 req=https.request({hostname:'127.0.0.1',port:16443,path:'/readyz',method:'GET',agent:false,
  ...credentials,servername:'',minVersion:'TLSv1.2',rejectUnauthorized:true,
  checkServerIdentity:(_,cert)=>tls.checkServerIdentity('192.168.0.4',cert),
  headers:{Accept:'text/plain','Accept-Encoding':'identity'}},response=>{
  if(![200,500,503].includes(response.statusCode)||(response.headers['content-encoding']||'identity')!=='identity'){response.destroy();finish(true);return}
  const length=response.headers['content-length'];
  if(length!==undefined&&(!/^[0-9]+$/.test(length)||BigInt(length)>4096n)){response.destroy();finish(true);return}
  const chunks=[];let count=0;
  response.on('data',chunk=>{if(settled){response.destroy();return}try{clock.left();count+=chunk.length;received+=chunk.length;
   need(count<=4096&&received<=1048576);if(response.statusCode===200)chunks.push(chunk)}catch(_){response.destroy();finish(true)}});
  response.on('end',()=>{if(settled)return;try{clock.left();root.check();need(length===undefined||BigInt(count)===BigInt(length));
   if(response.statusCode===200){need(String(response.headers['content-type']||'').split(';')[0].trim()==='text/plain'&&Buffer.concat(chunks).equals(Buffer.from('ok')));finish(null,true)}else finish(null,false)
  }catch(_){finish(true)}});
  response.on('aborted',()=>finish(true));response.on('error',()=>finish(true));
 });
 req.on('error',e=>finish(!['ECONNREFUSED','ECONNRESET','ETIMEDOUT'].includes(e.code),false));req.end();
})}
async function main(){try{
 await header();root=new p.MemoryRoot('/proof');
 credentials={ca:root.read('ca.crt'),cert:root.read('admin.crt'),key:root.read('admin.key')};
 const client=new crypto.X509Certificate(credentials.cert),ca=new crypto.X509Certificate(credentials.ca);
 need(client.verify(ca.publicKey)&&client.checkPrivateKey(crypto.createPrivateKey(credentials.key)));
 for(let n=0;n<4096;n++){clock.left();root.check();if(await attempt()){
  root.check();clock.left();process.stdout.write(JSON.stringify({abi:1,ready:true,tls_verified:true,whole_operation_lease_renewed:false,overall_acceptance:false})+'\n');return}
  await new Promise(resolve=>setTimeout(resolve,Math.min(100,clock.left())));
 }
 throw new Error('API readiness refused');
}finally{if(credentials)for(const v of Object.values(credentials))v.fill(0);credentials=null;if(root)root.close()}}
main().catch(()=>{process.exitCode=1});
"""


class RecoveryRefused(RuntimeError):
    def __init__(self, code):
        self.code = code if code in {'configuration', 'deadline', 'ownership', 'prerequisite',
            'replay', 'resource', 'child', 'bound', 'reply', 'durability', 'cleanup'} else 'reply'
        super().__init__('Isolated API recovery refused: ' + self.code)


def need(value, code):
    if not value:
        raise RecoveryRefused(code)


def public(function):
    """Drop the internal exception and all caller material before a fixed refusal."""
    @functools.wraps(function)
    def boundary(*args, **kwargs):
        result = failure = None
        try:
            result = function(*args, **kwargs)
        except RecoveryRefused as error:
            failure = error.code
        except Exception:
            failure = 'reply'
        if failure:
            args = kwargs = result = None
            raise RecoveryRefused(failure) from None
        return result
    return boundary


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class RecoveryJournal:
    """New closed ABI2 record over the existing exclusive/fsynced file backend.

    Only a newly constructed empty Ledger may enter this adapter. Default etcd
    records/methods are unchanged and cannot be reopened or adopted here.
    """
    @public
    def __init__(self, ledger):
        need(type(ledger) is backup.Ledger and specs._exact({
            'abi': 1, 'run_id': ledger.r.get('run_id'), 'phase': 'preparing', 'operations': {},
            'actual_production_checkpoint_accepted': False,
            'confirmation_requires_launcher_terminal0': True}, ledger.r), 'configuration')
        need(re.fullmatch('[0-9a-f]{12}', ledger.r['run_id']) is not None, 'configuration')
        self.backend = ledger
        self.run_id = ledger.r['run_id']
        ledger.r = {'abi': 2, 'domain': 'isolated-api-recovery', 'run_id': ledger.r['run_id'],
                    'operations': {}, 'bindings': None, 'overall_acceptance': False,
                    'confirmation_requires_launcher_terminal0': True}
        self.save()

    @property
    def r(self):
        return self.backend.r

    def save(self):
        r = self.r
        need(set(r) == {'abi', 'domain', 'run_id', 'operations', 'bindings', 'overall_acceptance',
                        'confirmation_requires_launcher_terminal0'} and r['abi'] == 2 and
             r['domain'] == 'isolated-api-recovery' and r['overall_acceptance'] is False and
             r['confirmation_requires_launcher_terminal0'] is True and r['run_id'] == self.run_id,
             'durability')
        need(type(r['operations']) is dict and set(r['operations']) <= ACTIONS, 'durability')
        binding = r['bindings']
        need(binding is None and not r['operations'] or type(binding) is dict and
             set(binding) == BINDINGS and all(type(v) is str and re.fullmatch('[0-9a-f]{64}', v)
             for v in binding.values()), 'durability')
        for action, record in r['operations'].items():
            need(type(record) is dict and set(record) == {'state', 'proposal_sha256', 'identity'} and
                 record['state'] in ('pending', 'confirmed', 'uncertain') and
                 type(record['proposal_sha256']) is str and
                 re.fullmatch('[0-9a-f]{64}', record['proposal_sha256']), 'durability')
            i = record['identity']
            need(i is None or type(i) is dict and set(i) == {'name', 'namespace', 'uid', 'resourceVersion'}
                 and i['namespace'] == specs.NS and all(type(v) is str and
                 re.fullmatch('[A-Za-z0-9_.:-]{1,253}', v) for v in i.values()), 'durability')
        self.backend.save()

    def pending(self, action, proposal, identity=None):
        need(action in ACTIONS and action not in self.r['operations'], 'replay')
        self.r['operations'][action] = {'state': 'pending', 'proposal_sha256': digest(proposal),
                                       'identity': copy.deepcopy(identity)}
        self.save()

    def confirmed(self, action, identity=None):
        need(self.r['operations'][action]['state'] == 'pending', 'replay')
        self.r['operations'][action].update(state='confirmed', identity=copy.deepcopy(identity))
        self.save()

    def uncertain(self, action):
        if action in self.r['operations'] and self.r['operations'][action]['state'] == 'pending':
            self.r['operations'][action]['state'] = 'uncertain'
            self.save()


class APIRecoveryTransport:
    """Borrow Transport/RecoveryJournal; caller owns their eventual close.

    prerequisite(action, deadline) is trusted external authority, returning exactly
    four stable receipt hashes. This module cannot establish those receipts.
    """
    @public
    def __init__(self, transport, journal, programme_text, prerequisite):
        need(type(transport) is backup.Transport and type(journal) is RecoveryJournal and
             callable(prerequisite), 'configuration')
        now = time.monotonic()
        need(type(transport.deadline) in (int, float) and math.isfinite(transport.deadline) and
             now < transport.deadline <= now + 600, 'deadline')
        self.transport, self.journal, self.deadline = transport, journal, transport.deadline
        self.original_deadline = transport.deadline
        self.proposals = specs.proposals(journal.r['run_id'], programme_text)
        self.prerequisite, self.binding = prerequisite, None
        self.owned = []
        self.expected_pod = copy.deepcopy(self.proposals['pod'])
        self.closed = False
        self.failed = False
        self.check('construct')

    def check(self, action):
        need(not self.closed and not self.failed and
             self.transport.deadline == self.deadline == self.original_deadline,
             'deadline')
        backup.left(self.deadline)
        self.transport.check()
        self.journal.backend.owned()
        binding = self.prerequisite(action, self.deadline)
        need(type(binding) is dict and set(binding) == BINDINGS and all(type(v) is str and
             re.fullmatch('[0-9a-f]{64}', v) for v in binding.values()), 'prerequisite')
        if self.binding is None:
            self.binding = copy.deepcopy(binding)
            need(self.journal.r['bindings'] is None, 'replay')
            self.journal.r['bindings'] = copy.deepcopy(binding)
            self.journal.save()
        need(binding == self.binding, 'prerequisite')
        backup.left(self.deadline)

    def _launch(self, args, stdout=subprocess.PIPE):
        descriptors = None
        child = None
        try:
            self.check('transport-dispatch')
            path = backup.RUNTIME / 'admin.conf'
            fd, descriptors, anchors, identity = backup.q.reader.pin_config(path)
            # pin_config validates the exact inherited bytes, TLS CA/client/key,
            # approved origin, protected ownership and stable ancestry itself.
            backup.q.reader.check_pinned(path, fd, identity, anchors)
            child = self.transport.spawn([str(backup.RUNTIME / 'bin/kubectl'),
                '--kubeconfig', '/proc/self/fd/' + str(fd),
                '--request-timeout=' + format(backup.left(self.deadline), '.6f') + 's', *args],
                pass_fds=(fd,), stdout=stdout)
            self.owned.append(child)
            child._api_recovery_pin = (path, fd, identity, anchors, descriptors)
            descriptors = None  # Owned until child closure, including the streaming session.
            backup.q.reader.check_pinned(path, fd, identity, anchors)
            return child
        except Exception:
            if child is not None:
                self._close_child(child)
            raise
        finally:
            if descriptors:
                backup.q.reader.close_descriptors(descriptors)

    def _close_child(self, child):
        failure = False
        try:
            self.transport.children(child)
        except Exception:
            failure = True
        for stream in (child.stdin, child.stdout, child.stderr):
            if stream and not stream.closed:
                try:
                    stream.close()
                except Exception:
                    failure = True
        pin = getattr(child, '_api_recovery_pin', None)
        if pin:
            try:
                backup.q.reader.check_pinned(*pin[:4])
            except Exception:
                failure = True
            try:
                backup.q.reader.close_descriptors(pin[4])
            except Exception:
                failure = True
            child._api_recovery_pin = None
        need(not failure and child.poll() is not None, 'cleanup')

    def _exchange(self, args, chunks=(), maximum=8 * 1024 * 1024, discard=False):
        """Duplex bounded stdin/stdout; material is never argv or a staging file."""
        child = selector = None
        raw = bytearray()
        result = None
        failure = None
        try:
            child = self._launch(args)
            selector = selectors.DefaultSelector()
            os.set_blocking(child.stdout.fileno(), False)
            os.set_blocking(child.stdin.fileno(), False)
            selector.register(child.stdout, selectors.EVENT_READ)
            selector.register(child.stdin, selectors.EVENT_WRITE)
            iterator = iter(chunks)
            pending = memoryview(b'')
            received = 0
            while selector.get_map():
                for key, _ in selector.select(min(.05, backup.left(self.deadline))):
                    if key.fileobj is child.stdin:
                        if not pending:
                            block = next(iterator, None)
                            if block is None:
                                selector.unregister(child.stdin)
                                child.stdin.close()
                                continue
                            need(type(block) is bytes and 0 < len(block) <= 65536, 'bound')
                            pending = memoryview(block)
                        count = os.write(child.stdin.fileno(), pending)
                        need(count > 0, 'child')
                        pending = pending[count:]
                    else:
                        block = os.read(child.stdout.fileno(), 65536)
                        if not block:
                            selector.unregister(child.stdout)
                            continue
                        received += len(block)
                        need(received <= maximum, 'bound')
                        if not discard:
                            raw.extend(block)
            need(child.wait(timeout=backup.left(self.deadline)) == 0, 'child')
            self.transport.check()
            self.check('transport-complete')
            result = bytes(raw) if not discard else None
        except RecoveryRefused as error:
            failure = error.code
        except Exception:
            failure = 'child'
        finally:
            if selector:
                try:
                    selector.close()
                except Exception:
                    failure = 'cleanup'
            if child:
                try:
                    self._close_child(child)
                except Exception:
                    failure = 'cleanup'
        child = chunks = iterator = pending = block = raw = None
        if failure:
            raise RecoveryRefused(failure)
        return result

    def _json(self, args, body=None, maximum=8 * 1024 * 1024):
        raw = b'' if body is None else json.dumps(body, separators=(',', ':')).encode()
        need(len(raw) <= 256 * 1024, 'bound')
        chunks = (raw[i:i + 65536] for i in range(0, len(raw), 65536))
        reply = self._exchange(args, chunks, maximum)
        return backup.decode(reply) if reply else None

    def _path(self, kind):
        need(kind in KINDS, 'configuration')
        return KINDS[kind][2] + '/' + self.proposals[kind]['metadata']['name']

    def _get(self, kind):
        return self._json(['get', '--raw', self._path(kind)])

    def _owned(self, kind, runtime=False):
        operation = self.journal.r['operations'].get(kind + '-create')
        need(operation and operation['state'] == 'confirmed', 'resource')
        obj = self._get(kind)
        proposal = self.expected_pod if kind == 'pod' else self.proposals[kind]
        identity = specs.matches(proposal, obj, operation['identity']['uid'], runtime=runtime)
        return obj, identity

    def _mutate(self, action, proposal, invoke, validate, identity=None):
        self.check(action)
        self.journal.pending(action, proposal, identity)
        try:
            reply = invoke()
            result = validate(reply)
            self.check(action)
            self.journal.confirmed(action, result)
            backup.left(self.deadline)
            return result
        except Exception:
            self.failed = True
            try:
                self.journal.uncertain(action)
            except Exception:
                pass  # A failed flush keeps the previous durable pending record.
            raise

    @public
    def create(self, kind):
        need(kind in KINDS, 'configuration')
        # Explicit order prevents an unprotected/material-bearing Pod.
        if kind != 'policy':
            self._owned('policy')
        if kind == 'pod':
            self._owned('configmap')
        proposal = self.proposals[kind]
        return self._mutate(kind + '-create', proposal,
            lambda: self._json(['create', '--raw', KINDS[kind][2], '-f', '-'], proposal),
            lambda obj: specs.matches(proposal, obj))

    @public
    def current(self, runtime=False):
        self.check('current')
        obj, identity = self._owned('pod', runtime=runtime)
        self.check('current')
        return identity

    def _exec_args(self, container, command, stdin=False):
        return ['exec', '-n', specs.NS, self.proposals['pod']['metadata']['name'],
                '-c', container, *(['-i'] if stdin else []), '--', *command]

    def _header(self):
        milliseconds = min(300000, math.floor(backup.left(self.deadline) * 1000))
        need(milliseconds > 0, 'deadline')
        return MAGIC + struct.pack('>I', milliseconds)

    @public
    def bundle(self, parts):
        need(type(parts) is tuple and len(parts) == 9 and all(type(v) is bytes and
             0 < len(v) <= (512 * 1024 * 1024 if i == 8 else 1048576)
             for i, v in enumerate(parts)), 'bound')
        self._owned('pod', runtime=True)
        def chunks():
            yield self._header()
            for index, value in enumerate(parts):
                yield struct.pack('>BI', index + 1, len(value))
                for start in range(0, len(value), 65536):
                    yield value[start:start + 65536]
            yield b'\0'
        expected = {'abi': 1, 'scope': 'isolated memory bundle only', 'files': 9, 'complete': True,
                    'plaintext_persisted_outside_memory': False, 'overall_acceptance': False}
        def validate(raw):
            need(specs._exact(expected, backup.decode(raw)), 'reply')
            self._owned('pod', runtime=True)
            return None
        result = self._mutate('bundle', {'programme_sha256': specs.PROGRAM_SHA256, 'slots': 9},
            lambda: self._exchange(self._exec_args('utility', ['node', specs.PROGRAM_PATH, '--bundle'],
                                                 True), chunks(), 65536), validate)
        self.delivered_snapshot_bytes = len(parts[8])
        return result

    @public
    def snapshot_status(self, expected_revision, expected_bytes):
        need(type(expected_revision) is int and expected_revision > 0 and type(expected_bytes) is int
             and 32 < expected_bytes <= backup.MAX and expected_bytes % 512 == 32, 'configuration')
        need(self.journal.r['operations'].get('bundle', {}).get('state') == 'confirmed', 'resource')
        need(getattr(self, 'delivered_snapshot_bytes', None) == expected_bytes, 'resource')
        self.check('snapshot-status')
        self._owned('pod', runtime=True)
        obj = self._json(self._exec_args('etcd', specs.SNAPSHOT_STATUS), maximum=65536)
        need(type(obj) is dict and set(obj) == {'hash', 'revision', 'totalKey', 'totalSize', 'version'}
             and all(type(obj[k]) is int for k in ('hash', 'revision', 'totalKey', 'totalSize')) and
             0 <= obj['hash'] <= 0xffffffff and obj['revision'] == expected_revision and
             obj['totalSize'] + 32 == expected_bytes and obj['totalKey'] > 0 and
             obj['version'] == '3.7.0', 'reply')
        self._owned('pod', runtime=True)
        self.check('snapshot-status')
        self.status_validated = True
        self.expected_revision = expected_revision
        return {'revision': obj['revision'], 'snapshot_bytes': expected_bytes, 'valid': True}

    @public
    def restore_once(self):
        need(getattr(self, 'status_validated', False) is True, 'resource')
        self._owned('pod', runtime=True)
        def validate(_):
            self._owned('pod', runtime=True)
            return None
        return self._mutate('restore', {'argv': specs.RESTORE}, lambda: self._exchange(
            self._exec_args('etcd', specs.RESTORE), maximum=1048576, discard=True), validate)

    @public
    def start_etcd_once(self):
        need(self.journal.r['operations'].get('restore', {}).get('state') == 'confirmed', 'resource')
        self.check('etcd-start')
        self._owned('pod', runtime=True)
        self.journal.pending('etcd-start', {'argv': specs.RESTORED_ETCD})
        try:
            child = self._launch(self._exec_args('etcd', specs.RESTORED_ETCD),
                                 stdout=subprocess.DEVNULL)
            child.stdin.close()
            # Remote logging and local streams are discarded before process startup.
            need(child.poll() is None, 'child')
            self.check('etcd-start')
            # Pending remains until an actual complete restored registry is read.
            self.etcd_child = child
        except Exception:
            self.failed = True
            if 'child' in locals():
                self._close_child(child)
            self.journal.uncertain('etcd-start')
            raise

    @public
    def read_cipher_map(self, expected_revision):
        self.check('cipher-map')
        need(type(expected_revision) is int and expected_revision > 0 and
             expected_revision == getattr(self, 'expected_revision', None) and
             getattr(self, 'etcd_child', None) is not None and self.etcd_child.poll() is None, 'resource')
        self._owned('pod', runtime=True)
        obj = self._json(self._exec_args('etcd', specs.REGISTRY), maximum=backup.MAX_REGISTRY)
        result = backup.registry(obj, expected_revision)
        need(sum(len(k) + len(v) for k, v in result.items()) <= backup.MAX_REGISTRY, 'bound')
        self._owned('pod', runtime=True)
        self.check('cipher-map')
        operation = self.journal.r['operations']['etcd-start']
        if operation['state'] == 'pending':
            self.journal.confirmed('etcd-start')
        else:
            need(operation['state'] == 'confirmed', 'resource')
        return result  # Private RAM only; caller compares whole maps before/after API.

    @public
    def add_api(self):
        need(self.journal.r['operations'].get('etcd-start', {}).get('state') == 'confirmed', 'resource')
        obj, identity = self._owned('pod', runtime=True)
        path, body, final = specs.ephemeral_update(self.expected_pod, obj,
                                                 self.proposals['ephemeral_api'], identity['uid'])
        result = self._mutate('api-add', body,
            lambda: self._json(['replace', '--raw', path, '-f', '-'], body),
            lambda reply: specs.matches(final, reply, identity['uid']), identity)
        self.expected_pod = final
        return result  # Submitted admitted spec, not API runtime/readiness proof.

    @public
    def wait_tls_ready(self):
        need(self.journal.r['operations'].get('api-add', {}).get('state') == 'confirmed', 'resource')
        self._owned('pod', runtime=True)
        expected = {'abi': 1, 'ready': True, 'tls_verified': True,
                    'whole_operation_lease_renewed': False, 'overall_acceptance': False}
        def validate(raw):
            need(specs._exact(expected, backup.decode(raw)), 'reply')
            self._owned('pod', runtime=True)
            return None
        return self._mutate('tls-ready', {'programme_sha256': backup.sha(TLS_READY_PROGRAM.encode())},
            lambda: self._exchange(self._exec_args('utility', ['node', '-e', TLS_READY_PROGRAM], True),
                                  (self._header(),), 65536), validate)

    @public
    def oracle_once(self):
        need(self.journal.r['operations'].get('tls-ready', {}).get('state') == 'confirmed', 'resource')
        self._owned('pod', runtime=True)
        result = None
        def validate(raw):
            nonlocal result
            result = backup.decode(raw)
            expected = {'abi': 1, 'scope': 'isolated retained-snapshot API Secret recovery only',
                'secret_count': 0, 'complete_ciphertext_map_unchanged': True,
                'independent_aescbc_protobuf_api_map_equal': True, 'tls_verified': True,
                'plaintext_or_plaintext_hash_returned': False, 'production_current_values_read': False,
                'full_control_plane_or_longhorn_recovery': False, 'overall_acceptance': False}
            need(type(result) is dict and type(result.get('secret_count')) is int and
                 0 <= result['secret_count'] <= 10000, 'reply')
            expected['secret_count'] = result['secret_count']
            need(specs._exact(expected, result), 'reply')
            self._owned('pod', runtime=True)
            return None
        self._mutate('oracle', {'programme_sha256': specs.PROGRAM_SHA256}, lambda: self._exchange(
            self._exec_args('utility', ['node', specs.PROGRAM_PATH, '--oracle'], True),
            (self._header(),), 65536), validate)
        return result

    def _absent(self, kind, identity):
        # Named GET uses --ignore-not-found: raw GET 404 is not JSON/absence.
        while True:
            obj = self._json(['get', KINDS[kind][1].lower(), identity['name'], '-n', specs.NS,
                             '--ignore-not-found', '-o', 'json'])
            if obj is None:
                break
            need(type(obj) is dict and type(obj.get('metadata')) is dict and
                 obj['metadata'].get('uid') == identity['uid'] and
                 obj['metadata'].get('name') == identity['name'] and
                 obj['metadata'].get('namespace') == specs.NS, 'resource')
            time.sleep(min(.05, backup.left(self.deadline)))
        obj = self._json(['get', '--raw', KINDS[kind][2]])
        need(type(obj) is dict and obj.get('apiVersion') == KINDS[kind][0] and
             obj.get('kind') == KINDS[kind][1] + 'List' and type(obj.get('items')) is list and
             len(obj['items']) <= 10000, 'resource')
        meta = obj.get('metadata')
        need(type(meta) is dict and type(meta.get('resourceVersion')) is str and
             re.fullmatch('[A-Za-z0-9_.:-]{1,253}', meta['resourceVersion']) and
             meta.get('continue', '') == '' and type(meta.get('continue', '')) is str and
             type(meta.get('remainingItemCount', 0)) is int and meta.get('remainingItemCount', 0) == 0,
             'resource')
        names, uids = set(), set()
        for item in obj['items']:
            need(type(item) is dict and item.get('apiVersion', KINDS[kind][0]) == KINDS[kind][0]
                 and item.get('kind', KINDS[kind][1]) == KINDS[kind][1], 'resource')
            current = backup.identity(item)
            need(current['namespace'] == specs.NS and current['name'] not in names and
                 current['uid'] not in uids and current['name'] != identity['name'] and
                 current['uid'] != identity['uid'], 'resource')
            names.add(current['name'])
            uids.add(current['uid'])

    @public
    def delete_owned(self, kind):
        need(kind in KINDS, 'configuration')
        # Policy/CM must survive until exact Pod name+UID absence is durable.
        if kind != 'pod' and 'pod-create' in self.journal.r['operations']:
            need(self.journal.r['operations'].get('pod-delete', {}).get('state') == 'confirmed',
                 'resource')
        obj, identity = self._owned(kind)
        body = {'apiVersion': 'v1', 'kind': 'DeleteOptions',
                'preconditions': {'uid': identity['uid'], 'resourceVersion': identity['resourceVersion']}}
        def invoke():
            reply = self._json(['delete', '--raw', self._path(kind), '-f', '-'], body)
            need(type(reply) is dict, 'reply')
            if reply.get('kind') == 'Status':
                details = reply.get('details')
                need(reply.get('apiVersion') == 'v1' and reply.get('status') == 'Success' and
                     type(details) is dict and details.get('name') == identity['name'] and
                     details.get('uid') == identity['uid'] and
                     details.get('kind') == KINDS[kind][2].rsplit('/', 1)[1], 'reply')
            else:
                meta = reply.get('metadata')
                need(reply.get('apiVersion') == KINDS[kind][0] and
                     reply.get('kind') == KINDS[kind][1] and type(meta) is dict and
                     all(meta.get(k) == identity[k] for k in ('name', 'namespace', 'uid')), 'reply')
            self._absent(kind, identity)
        return self._mutate(kind + '-delete', body, invoke, lambda _: identity, identity)

    @public
    def close(self):
        failure = False
        for child in getattr(self, 'owned', []):
            try:
                self._close_child(child)
            except Exception:
                failure = True
        self.closed = True
        need(not failure, 'cleanup')
        # Neither borrowed Transport nor journal is closed here. Remote process
        # death is proved separately by UID/name complete Pod absence, not exec kill.
