"""Bounded TLS LIST/watch and durable restore prerequisites; no live CLI or data proof."""
import copy
from dataclasses import dataclass
import hashlib
import http.client
import importlib.util
import json
import os
import pathlib
import socket
import ssl
import stat
import threading
import time
from urllib.parse import urlencode, urlsplit
import uuid


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


completion = load('bortus_watch_completion', 'bortus-restore-completion.py')
ownership = load('bortus_watch_ownership', 'bortus-restore-journal.py')
PATH = '/apis/longhorn.io/v1beta2/namespaces/longhorn-system/volumes'
MAX_LIST_PAGES = 32
MAX_LIST_ITEMS = 4096
MAX_LIST_BYTES = 8 * 1024 * 1024
MAX_FRAME_BYTES = 1024 * 1024
MAX_WATCH_BYTES = 8 * 1024 * 1024
MAX_WATCH_FRAMES = 4096
MAX_PROOF_BYTES = 8 * 1024 * 1024
MAX_DEPTH = 32
LEASE_SECONDS = 2100


class WatchRefused(RuntimeError):
    """Fixed public failure code only; never propagate TLS/API/input errors."""

    def __init__(self, code, received_bytes=0):
        self.code = code
        self.received_bytes = received_bytes  # Scalar accounting only; never rejected body data.
        super().__init__('Restore watch refused: ' + code)


def require(ok, code):
    if not ok:
        raise WatchRefused(code)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'json_duplicate')
        result[key] = value
    return result


def decode(raw):
    # Depth is checked before JSON allocation; escapes inside strings are not structure.
    depth = 0
    quoted = escaped = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            require(depth <= MAX_DEPTH, 'json_depth')
        elif byte in (93, 125):
            depth -= 1
            require(depth >= 0, 'json_shape')
    require(depth == 0 and not quoted, 'json_shape')
    try:
        value = json.loads(raw.decode('utf-8', errors='strict'), object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(WatchRefused('json_shape')))
    except WatchRefused:
        raise
    except Exception:
        raise WatchRefused('json_shape') from None
    require(type(value) is dict, 'json_shape')
    return value


def volume_identity(obj):
    require(type(obj) is dict and
            obj.get('apiVersion', completion.API_VERSION) == completion.API_VERSION and
            obj.get('kind', 'Volume') == 'Volume', 'volume_shape')
    meta = obj.get('metadata')
    require(type(meta) is dict, 'volume_identity')
    result = {k: meta.get(k) for k in ('name', 'namespace', 'uid', 'resourceVersion')}
    require(completion._name(result['name']) and completion._uid(result['uid']) and
            result['namespace'] == 'longhorn-system' and
            completion._text(result['resourceVersion'], 256), 'volume_identity')
    return result


@dataclass(frozen=True)
class Source:
    backup_url: str
    backup: object
    original_volume_uid: str
    original_volume_handle: str
    original_pv_uid: str
    original_claim_uid: str

    def expected(self, name, uid):
        return completion.RestoreExpectation(name, uid, 'longhorn-system', self.backup_url,
            self.backup, self.original_volume_uid, self.original_volume_handle, completion.SIZE_BYTES)


@dataclass(frozen=True)
class Prerequisite:
    """An informational reference; perform_create verifies the live owned lease itself."""
    lease_id: str
    collection_resource_version: str
    durable_record_sha256: str
    sequence: int
    data_acceptance: bool = False


class WatchJournal(ownership.Journal):
    """Serialize journal replacement with the reader's sidecar ownership checks."""
    def __init__(self, directory):
        super().__init__(directory)
        self.watch_lock = threading.RLock()

    def save(self):
        with self.watch_lock:
            return super().save()

    def close(self):
        with self.watch_lock:
            return super().close()


class TLSAPI:
    """Direct TLS only; fresh caller-supplied context/headers for every connection.

    No credential parser, proxy/exec fallback, redirects, credential file writing,
    environment proxy, response/error logging, connection pool or credential cache.
    The future executor must qualify its approved kubeconfig adapter separately.
    """

    def __init__(self, approved_origin, options):
        try:
            origin = urlsplit(approved_origin)
            require(origin.scheme == 'https' and origin.hostname and not origin.username and
                    not origin.password and not origin.query and not origin.fragment and
                    origin.path in ('', '/') and callable(options), 'tls_configuration')
            self.host, self.port = origin.hostname, origin.port or 443
        except Exception:
            raise WatchRefused('tls_configuration') from None
        self.options = options

    def _request(self, query, deadline):
        connection = response = None
        try:
            require(time.monotonic() < deadline, 'deadline')
            context, headers = self.options()
            require(type(context) is ssl.SSLContext and context.check_hostname and
                    context.verify_mode == ssl.CERT_REQUIRED and
                    context.minimum_version >= ssl.TLSVersion.TLSv1_2 and
                    type(headers) is dict and set(headers) <= {'Authorization'}, 'tls_configuration')
            require(all(type(v) is str and 0 < len(v) <= 16384 and
                        all(32 <= ord(c) < 127 for c in v) for v in headers.values()), 'tls_configuration')
            timeout = min(30, deadline - time.monotonic())
            require(timeout > 0, 'deadline')
            connection = http.client.HTTPSConnection(self.host, self.port, context=context, timeout=timeout)
            connection.connect()
            connection._bortus_socket = connection.sock  # Retain ownership even on Connection: close.
            require(isinstance(connection.sock, ssl.SSLSocket) and connection.sock.getpeercert() and
                    connection.sock.version() in ('TLSv1.2', 'TLSv1.3'), 'tls_verification')
            connection.request('GET', PATH + '?' + urlencode(query),
                               headers={'Accept': 'application/json', 'Accept-Encoding': 'identity', **headers})
            # Do not retain credentials alongside the returned stream.
            headers = None
            response = connection.getresponse()
            require(response.status != 410, 'history_gap')
            require(response.status == 200 and
                    response.getheader('Content-Type', '').split(';', 1)[0].strip() == 'application/json' and
                    response.getheader('Content-Encoding', 'identity') == 'identity', 'http_response')
            return connection, response
        except WatchRefused:
            if response: response.close()
            if connection: connection.close()
            raise
        except Exception:
            if response: response.close()
            if connection: connection.close()
            raise WatchRefused('tls_request') from None

    def list_page(self, continuation, remaining, deadline):
        query = {'limit': 128}
        if continuation: query['continue'] = continuation
        connection, response = self._request(query, deadline)
        try:
            parts, count = [], 0
            while True:
                require(time.monotonic() < deadline, 'deadline')
                piece = response.read(min(65536, remaining - count + 1))
                count += len(piece)
                if count > remaining:
                    raise WatchRefused('list_byte_bound', count)
                if not piece: break
                parts.append(piece)
            return decode(b''.join(parts)), count
        except WatchRefused as error:
            raise WatchRefused(error.code, count) from None
        except http.client.IncompleteRead as error:
            raise WatchRefused('list_read', count + len(error.partial)) from None
        except Exception:
            raise WatchRefused('list_read', count) from None
        finally:
            response.close(); connection.close()

    def open_watch(self, collection_rv, deadline):
        return self._request({'watch': 'true', 'resourceVersion': collection_rv,
                              'allowWatchBookmarks': 'true', 'timeoutSeconds': LEASE_SECONDS}, deadline)


class Collector:
    """Own one non-restarting stream, bounded projections and fsynced sidecar.

    The existing restore Journal owns the run directory/lock. It is never modified
    here except through its original perform() API. No caller boolean is accepted
    as readiness. This observer is not a restored-data/admission/image executor.
    """

    def __init__(self, journal, transport, source):
        require(type(journal) is WatchJournal and type(transport) is TLSAPI and
                type(source) is Source, 'configuration')
        try:
            completion._expected(source.expected('pending-restore', str(uuid.uuid4())))
            require(completion._uid(source.original_pv_uid) and
                    completion._uid(source.original_claim_uid), 'configuration')
            journal._owned()
            require(journal.record['operations'] == {}, 'reopen_not_ready')
        except Exception:
            raise WatchRefused('configuration') from None
        self.journal, self.transport, self.source = journal, transport, source
        self.lock = journal.watch_lock
        self.reader_started = threading.Event()
        self.deadline = time.monotonic() + LEASE_SECONDS
        self.connection = self.response = self.thread = None
        self.inode = self.digest = self.expected = None
        self.stopping = False
        self.state = {'abi': 2, 'phase': 'starting', 'failure': None,
            'lease_id': str(uuid.uuid4()), 'run_id': journal.record['run_id'],
            'checkpoint_sha256': journal.record['checkpoint_journal_sha256'],
            'proposal_sha256': journal.record['reviewed_proposal_sha256'],
            'collector_sha256': hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
            'collection_rv': None, 'list_bytes': 0, 'frames': 0, 'watch_bytes': 0,
            'sequence': 0, 'baseline': [], 'observations': [], 'authorizations': [],
            'target': None, 'metadata_eligible': False, 'data_acceptance': False}
        try:
            fd = os.open('watch.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=journal.fd)
            info = os.fstat(fd); self.inode = (info.st_dev, info.st_ino); os.close(fd)
            self._save()
        except Exception:
            raise WatchRefused('durability') from None

    def _disk(self):
        self.journal._owned()
        fd = os.open('watch.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.journal.fd)
        try:
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
                    stat.S_IMODE(info.st_mode) == 0o600 and info.st_size <= MAX_PROOF_BYTES and
                    (info.st_dev, info.st_ino) == self.inode, 'ownership')
            with os.fdopen(fd, 'rb', closefd=False) as stream: raw = stream.read(MAX_PROOF_BYTES + 1)
            require(len(raw) <= MAX_PROOF_BYTES and
                    (self.digest is None or hashlib.sha256(raw).hexdigest() == self.digest), 'ownership')
            return raw
        finally:
            os.close(fd)

    def _save(self):
        self._disk()
        self._validate_state()
        raw = (json.dumps(self.state, separators=(',', ':')) + '\n').encode()
        require(len(raw) <= MAX_PROOF_BYTES, 'proof_bound')
        name = 'watch-' + uuid.uuid4().hex + '.next'
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=self.journal.fd)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as stream:
                stream.write(raw); stream.flush(); os.fsync(fd)
                info = os.fstat(fd); inode = (info.st_dev, info.st_ino)
        finally:
            os.close(fd)
        self._disk()
        os.replace(name, 'watch.json', src_dir_fd=self.journal.fd, dst_dir_fd=self.journal.fd)
        os.fsync(self.journal.fd)
        self.inode, self.digest = inode, hashlib.sha256(raw).hexdigest()
        self._disk()

    def _validate_state(self):
        """Closed persisted metadata ABI; never serialize arbitrary caller fields."""
        s = self.state
        require(type(s) is dict and set(s) == {'abi', 'phase', 'failure', 'lease_id', 'run_id',
            'checkpoint_sha256', 'proposal_sha256', 'collector_sha256', 'collection_rv', 'list_bytes',
            'frames', 'watch_bytes', 'sequence', 'baseline', 'observations', 'authorizations',
            'target', 'metadata_eligible', 'data_acceptance'}, 'proof_schema')
        require(s['abi'] == 2 and s['phase'] in ('starting', 'ready', 'bound', 'eligible', 'failed', 'closed') and
                completion._uid(s['lease_id']) and s['run_id'] == self.journal.record['run_id'] and
                s['checkpoint_sha256'] == self.journal.record['checkpoint_journal_sha256'] and
                s['proposal_sha256'] == self.journal.record['reviewed_proposal_sha256'] and
                s['collector_sha256'] == hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest() and
                (s['collection_rv'] is None or completion._text(s['collection_rv'], 256)) and
                type(s['metadata_eligible']) is bool and s['data_acceptance'] is False, 'proof_schema')
        require(s['failure'] is None or s['failure'] in {'configuration', 'durability', 'ownership',
            'deadline', 'list_shape', 'list_rv', 'list_item_bound', 'list_incomplete', 'list_page_bound',
            'list_byte_bound', 'list_read', 'history_gap', 'tls_configuration', 'tls_verification',
            'tls_request', 'http_response', 'reader_start', 'watch_start', 'event_shape', 'watch_error',
            'volume_shape', 'volume_identity', 'conditions_shape', 'bookmark_shape', 'watch_eof',
            'watch_byte_bound', 'watch_frame_bound', 'watch_read', 'proof_bound', 'proof_schema',
            'json_duplicate', 'json_depth', 'json_shape', 'target_event_bound', 'target_drift',
            'prerequisite', 'binding', 'seal'}, 'proof_schema')
        require(all(type(s[k]) is int and 0 <= s[k] <= limit for k, limit in
            [('list_bytes', MAX_LIST_BYTES + 1), ('frames', MAX_WATCH_FRAMES + 1),
             ('watch_bytes', MAX_WATCH_BYTES + MAX_FRAME_BYTES + 1), ('sequence', MAX_WATCH_FRAMES)]),
             'proof_schema')
        for key, limit in [('baseline', MAX_LIST_ITEMS), ('observations', MAX_WATCH_FRAMES),
                           ('authorizations', 3)]:
            require(type(s[key]) is list and len(s[key]) <= limit, 'proof_schema')
        for identity in s['baseline'] + ([s['target']] if s['target'] is not None else []):
            require(type(identity) is dict and set(identity) == {'name', 'namespace', 'uid', 'resourceVersion'},
                    'proof_schema')
            volume_identity({'metadata': identity})
        for p in s['observations']:
            require(type(p) is dict and set(p) == {'type', 'identity', 'source_matches', 'spec_matches',
                'flags_valid', 'flags', 'status_valid', 'restore_failure', 'deleting'} and
                p['type'] in ('ADDED', 'MODIFIED', 'DELETED'), 'proof_schema')
            volume_identity({'metadata': p['identity']})
            require(set(p['identity']) == {'name', 'namespace', 'uid', 'resourceVersion'} and
                all(type(p[k]) is bool for k in ('source_matches', 'spec_matches', 'flags_valid',
                                                'status_valid', 'restore_failure', 'deleting')) and
                type(p['flags']) is dict and set(p['flags']) <= {'restoreInitiated', 'restoreRequired'} and
                all(type(v) is bool for v in p['flags'].values()), 'proof_schema')
        seen = set()
        for a in s['authorizations']:
            require(type(a) is dict and set(a) == {'action', 'sequence', 'prior_record_sha256'} and
                    a['action'] in ('storageclass_create', 'claim_create', 'holder_create') and
                    a['action'] not in seen and type(a['sequence']) is int and
                    0 <= a['sequence'] <= MAX_WATCH_FRAMES and type(a['prior_record_sha256']) is str and
                    len(a['prior_record_sha256']) == 64 and
                    all(c in '0123456789abcdef' for c in a['prior_record_sha256']), 'proof_schema')
            seen.add(a['action'])

    def _fail(self, code):
        with self.lock:
            if self.state['failure'] is None:
                self.state['failure'] = code
                self.state['phase'] = 'failed'
                self.state['metadata_eligible'] = False
                try: self._save()
                except Exception: pass  # Prior unsealed record cannot become eligibility.
        self._shutdown_socket()

    def _shutdown_socket(self):
        owned_socket = getattr(self.connection, '_bortus_socket', None)
        if owned_socket:
            try: owned_socket.shutdown(socket.SHUT_RDWR)
            except OSError: pass
        if self.connection: self.connection.close()

    def _live(self):
        require(self.state['failure'] is None and not self.stopping and
                self.state['phase'] in ('ready', 'bound', 'eligible') and
                self.reader_started.is_set() and self.thread and self.thread.is_alive() and
                time.monotonic() < self.deadline, 'watch_not_live')
        self._disk()

    def start(self):
        require(self.state['phase'] == 'starting', 'start_once')
        try:
            continuation = None
            names, uids, tokens = set(), set(), set()
            for page in range(MAX_LIST_PAGES):
                try:
                    obj, size = self.transport.list_page(continuation,
                        MAX_LIST_BYTES - self.state['list_bytes'], self.deadline)
                except WatchRefused as error:
                    self.state['list_bytes'] += error.received_bytes
                    raise
                self.state['list_bytes'] += size
                require(obj.get('apiVersion') == completion.API_VERSION and obj.get('kind') == 'VolumeList' and
                        type(obj.get('metadata')) is dict and type(obj.get('items')) is list, 'list_shape')
                meta = obj['metadata']; rv = meta.get('resourceVersion')
                require(completion._text(rv, 256), 'list_rv')
                if page == 0: self.state['collection_rv'] = rv
                require(rv == self.state['collection_rv'], 'list_rv')
                for item in obj['items']:
                    identity = volume_identity(item)
                    require(identity['name'] not in names and identity['uid'] not in uids and
                            len(names) < MAX_LIST_ITEMS, 'list_item_bound')
                    names.add(identity['name']); uids.add(identity['uid'])
                    self.state['baseline'].append(identity)
                continuation = meta.get('continue', '')
                require(type(continuation) is str and len(continuation) <= 8192, 'list_shape')
                if not continuation:
                    require('remainingItemCount' not in meta or
                            type(meta['remainingItemCount']) is int and meta['remainingItemCount'] == 0,
                            'list_incomplete')
                    break
                require(continuation not in tokens, 'list_incomplete'); tokens.add(continuation)
            else:
                raise WatchRefused('list_page_bound')
            self.connection, self.response = self.transport.open_watch(self.state['collection_rv'], self.deadline)
            self.thread = threading.Thread(target=self._read, name='bortus-owned-restore-watch', daemon=True)
            self.thread.start()
            require(self.reader_started.wait(2), 'reader_start')
            with self.lock:
                require(self.state['failure'] is None and self.thread.is_alive(), 'reader_start')
                self.state['phase'] = 'ready'; self._save(); self._live()
            return self
        except WatchRefused as error:
            self._fail(error.code); raise
        except Exception:
            self._fail('watch_start'); raise WatchRefused('watch_start') from None

    def _project(self, event):
        require(set(event) == {'type', 'object'}, 'event_shape')
        kind, obj = event['type'], event['object']
        require(kind in ('ADDED', 'MODIFIED', 'DELETED', 'BOOKMARK', 'ERROR'), 'event_shape')
        if kind == 'ERROR': raise WatchRefused('watch_error')
        require(type(obj) is dict, 'event_shape')
        if kind == 'BOOKMARK':
            meta = obj.get('metadata', {})
            require(obj.get('apiVersion') == completion.API_VERSION and obj.get('kind') == 'Volume' and
                    type(meta) is dict and completion._text(meta.get('resourceVersion'), 256), 'bookmark_shape')
            return None
        identity = volume_identity(obj)
        spec, status = obj.get('spec', {}), obj.get('status', {})
        require(type(spec) is dict and type(status) is dict, 'volume_shape')
        conditions = status.get('conditions', [])
        if conditions is None: conditions = []
        require(type(conditions) is list and len(conditions) <= completion.MAX_CONDITIONS and
                all(type(c) is dict for c in conditions), 'conditions_shape')
        seen = set()
        for condition in conditions:
            name = condition.get('type')
            require(completion._text(name, 128) and name not in seen and
                    condition.get('status') in ('True', 'False', 'Unknown') and
                    all(type(condition[k]) is str and len(condition[k]) <= 4096 for k in
                        ('reason', 'message', 'lastProbeTime', 'lastTransitionTime') if k in condition),
                    'conditions_shape')
            seen.add(name)
        fields = ('restoreInitiated', 'restoreRequired')
        flags = {k: status[k] for k in fields if k in status and type(status[k]) is bool}
        flags_valid = (all(k not in status for k in fields) or
                       all(k in status and type(status[k]) is bool for k in fields))
        status_valid = (
            ('state' not in status or (type(status['state']) is str and status['state'] in
                ('', 'creating', 'attached', 'detached', 'attaching', 'detaching'))) and
            ('robustness' not in status or (type(status['robustness']) is str and
                status['robustness'] in ('', 'unknown', 'healthy', 'degraded'))) and
            ('isStandby' not in status or status['isStandby'] is False))
        return {'type': kind, 'identity': identity,
            'source_matches': spec.get('fromBackup') == self.source.backup_url,
            'spec_matches': spec.get('encrypted') is True and type(spec.get('numberOfReplicas')) is int and
                spec['numberOfReplicas'] == 2 and spec.get('size') == completion.SIZE_BYTES and
                spec.get('dataEngine') == 'v1' and spec.get('Standby') is False and 'standby' not in spec,
            'flags_valid': flags_valid, 'flags': flags, 'status_valid': status_valid,
            'restore_failure': any(c.get('type') == 'Restore' and c.get('reason') == 'RestoreFailure'
                                   for c in conditions),
            'deleting': obj['metadata'].get('deletionTimestamp') is not None or status.get('state') == 'deleting'}

    def _target_events(self):
        target = self.state['target']
        observations = [p for p in self.state['observations'] if p['identity']['name'] == target['name'] or
                        p['identity']['uid'] == target['uid']]
        require(0 < len(observations) <= completion.MAX_EVENTS, 'target_event_bound')
        result = []
        for p in observations:
            require(p['identity']['name'] == target['name'] and p['identity']['uid'] == target['uid'] and
                    p['source_matches'] and p['spec_matches'] and p['flags_valid'] and p['status_valid'] and
                    not p['restore_failure'] and not p['deleting'] and p['type'] != 'DELETED', 'target_drift')
            result.append({'type': p['type'], 'object': {'apiVersion': completion.API_VERSION, 'kind': 'Volume',
                'metadata': p['identity'], 'spec': {'fromBackup': self.source.backup_url, 'encrypted': True,
                    'numberOfReplicas': 2, 'size': completion.SIZE_BYTES, 'dataEngine': 'v1', 'Standby': False},
                'status': p['flags']}})
        return result

    def _validate_target_trace(self):
        try:
            completion.evaluate_restore_transition(self.expected, self._target_events(),
                watch_started_before_create=True, longhorn_version=completion.LONGHORN_VERSION,
                api_version=completion.API_VERSION)
        except completion.RestoreTransitionRefused as error:
            require(error.code == 'completion_unobserved', 'target_drift')

    def _read(self):
        self.reader_started.set()
        try:
            while not self.stopping:
                require(time.monotonic() < self.deadline, 'deadline')
                raw = self.response.readline(MAX_FRAME_BYTES + 1)
                with self.lock:
                    self.state['watch_bytes'] += len(raw)
                    require(self.state['watch_bytes'] <= MAX_WATCH_BYTES and len(raw) <= MAX_FRAME_BYTES,
                            'watch_byte_bound')
                    if self.stopping: return
                    require(time.monotonic() < self.deadline, 'deadline')
                    require(raw and raw.endswith(b'\n'), 'watch_eof')
                    self.state['frames'] += 1
                    require(self.state['frames'] <= MAX_WATCH_FRAMES, 'watch_frame_bound')
                    projection = self._project(decode(raw))
                    if projection is not None: self.state['observations'].append(projection)
                    self.state['sequence'] += 1
                    if self.state['target'] is not None: self._validate_target_trace()
                    self._save()
        except WatchRefused as error:
            if not self.stopping: self._fail(error.code)
        except http.client.IncompleteRead as error:
            with self.lock:
                self.state['watch_bytes'] += len(error.partial)
            if not self.stopping: self._fail('watch_read')
        except Exception:
            if not self.stopping: self._fail('watch_read')
        finally:
            if self.response: self.response.close()
            if self.connection: self.connection.close()

    def before_create(self, action):
        require(action in ('storageclass_create', 'claim_create', 'holder_create'), 'action')
        with self.lock:
            try:
                self._live()
                require(action not in self.journal.record['operations'] and
                        action not in [x['action'] for x in self.state['authorizations']], 'no_replay')
                if action == 'claim_create':
                    require(self.journal.record['operations'].get('storageclass_create', {}).get('state') ==
                            'confirmed', 'create_order')
                if action == 'holder_create':
                    require(self.expected is not None and self.state['metadata_eligible'], 'create_order')
                proof = Prerequisite(self.state['lease_id'], self.state['collection_rv'], self.digest,
                                     self.state['sequence'])
                self.state['authorizations'].append({'action': action, 'sequence': proof.sequence,
                                                     'prior_record_sha256': proof.durable_record_sha256})
                self._save()
                return proof
            except Exception:
                self._fail('prerequisite'); raise WatchRefused('prerequisite') from None

    def prerequisite(self):
        with self.lock:
            self._live()
            return Prerequisite(self.state['lease_id'], self.state['collection_rv'], self.digest,
                                self.state['sequence'])

    def perform_create(self, action, mutate, validate):
        """Gate journal/API dispatch using this real live lease, not a supplied proof."""
        self.before_create(action)
        def guarded(intent):
            with self.lock: self._live()
            # Keep draining while the caller's bounded API callback is in flight.
            result = mutate(intent)
            with self.lock: self._live()
            return result
        result = self.journal.perform(action, guarded, validate)
        with self.lock: self._live()
        return result

    def bind_target(self, claim, pv, volume):
        with self.lock:
            try:
                self._live()
                require(self.expected is None, 'bind_once')
                owned = self.journal.record['operations'].get('claim_create', {})
                current_claim = ownership.identity(claim)
                require(owned.get('state') == 'confirmed' and all(current_claim[k] == owned['identity'][k]
                        for k in ('name', 'namespace', 'uid')) and
                        claim.get('status', {}).get('phase') == 'Bound' and
                        claim.get('spec', {}).get('storageClassName') == self.journal.record['target_name'] and
                        not claim['metadata'].get('deletionTimestamp'), 'claim_binding')
                pmeta, pspec = pv.get('metadata', {}), pv.get('spec', {})
                ref, csi = pspec.get('claimRef', {}), pspec.get('csi', {})
                vmeta = volume_identity(volume)
                require(pmeta.get('name') == claim['spec'].get('volumeName') and
                        completion._uid(pmeta.get('uid')) and completion._text(pmeta.get('resourceVersion'), 256) and
                        pmeta.get('namespace') in (None, '') and not pmeta.get('deletionTimestamp') and
                        ref.get('uid') == claim['metadata']['uid'] and ref.get('name') == claim['metadata']['name'] and
                        ref.get('namespace') == 'bortus' and pspec.get('persistentVolumeReclaimPolicy') == 'Retain' and
                        csi.get('driver') == 'driver.longhorn.io' and csi.get('volumeHandle') == vmeta['name'] and
                        pmeta['uid'] != self.source.original_pv_uid and
                        claim['metadata']['uid'] != self.source.original_claim_uid and
                        not any(x['uid'] == vmeta['uid'] or x['name'] == vmeta['name'] for x in self.state['baseline']),
                        'volume_binding')
                expected = self.source.expected(vmeta['name'], vmeta['uid']); completion._expected(expected)
                current = self._project({'type': 'MODIFIED', 'object': volume})
                require(current['source_matches'] and current['spec_matches'] and current['flags_valid'] and current['status_valid'] and
                        not current['restore_failure'] and not current['deleting'], 'volume_binding')
                self.expected = expected; self.state['target'] = vmeta
                self._validate_target_trace()  # Earlier events bind only through confirmed UID replies.
                self.state['phase'] = 'bound'; self._save()
            except Exception:
                self._fail('binding'); raise WatchRefused('binding') from None

    def seal(self, fresh_volume):
        with self.lock:
            try:
                self._live(); require(self.expected is not None, 'unbound')
                current = self._project({'type': 'MODIFIED', 'object': fresh_volume})
                events = self._target_events()
                require(current['identity'] == events[-1]['object']['metadata'] and current['source_matches'] and
                        current['spec_matches'] and current['flags_valid'] and current['status_valid'] and not current['deleting'] and
                        not current['restore_failure'] and current['flags'] == events[-1]['object']['status'], 'seal_rv')
                result = completion.evaluate_restore_transition(self.expected, events,
                    watch_started_before_create=True, longhorn_version=completion.LONGHORN_VERSION,
                    api_version=completion.API_VERSION)
                self.state['metadata_eligible'] = True; self.state['phase'] = 'eligible'; self._save()
                return result
            except Exception:
                self._fail('seal'); raise WatchRefused('seal') from None

    def close(self):
        self.stopping = True
        self._shutdown_socket()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(3)
            require(not self.thread.is_alive(), 'reader_cleanup')
        with self.lock:
            if self.state['failure'] is None:
                self.state['phase'] = 'closed'
                try: self._save()
                except Exception: self._fail('durability')
