"""Closed quiescent phase packets; borrowed continuity, no mutation or live acceptance."""
import copy
import hashlib
import importlib.util
import json
import math
import os
import pathlib
import re
import sys
import time
import types


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module); return module


HERE = pathlib.Path(__file__).parent
interval = load('phase_interval', HERE / 'bortus-quiescent-interval.py')
admission = load('phase_admission', HERE / 'bortus-admission-operator.py')
ready = load('phase_ready', HERE / 'schema-current-writer-v1/current-schema-producer.py')
validator = admission.validator
PHASES = ('legacy-approved', 'forward-compatible')
FIELDS = {'phase', 'image', 'source_sha256', 'qualification_receipt_sha256', 'contract', 'policy_pins'}
PIN_FIELDS = {'uid', 'resourceVersion', 'spec_sha256', 'binding_uid', 'binding_resourceVersion', 'binding_spec_sha256'}


class Refused(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__('Quiescent phase refused: ' + code)


def need(ok, code):
    if not ok: raise Refused(code)


def sha(raw): return hashlib.sha256(raw).hexdigest()
def digest(value): return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def binding_checked(value):
    validator.bounded(value)
    need(type(value) is dict and set(value) == FIELDS and value['phase'] in PHASES and
         interval.cold.valid_digest(value['image']) and digest(value['source_sha256']) and
         digest(value['qualification_receipt_sha256']), 'binding')
    validator.contract_checked(value['contract'])
    need(value['image'] in value['contract']['approved_image_references'], 'binding')
    pins = value['policy_pins']
    need(type(pins) is dict and set(pins) == set(interval.quiescent.POLICIES), 'binding')
    identities = []
    for pin in pins.values():
        need(type(pin) is dict and set(pin) == PIN_FIELDS and
             validator.uid(pin['uid']) and validator.uid(pin['binding_uid']) and
             digest(pin['spec_sha256']) and digest(pin['binding_spec_sha256']) and
             all(type(pin[k]) is str and 0 < len(pin[k]) <= 256 and
                 all(32 < ord(c) < 127 for c in pin[k]) for k in ('resourceVersion', 'binding_resourceVersion')), 'binding')
        identities.extend((pin['uid'], pin['binding_uid']))
    need(len(set(identities)) == 6, 'binding')
    return copy.deepcopy(value)


class PhaseQualifier:
    """Construct the graph through interval exports; root owns all qualification proof."""
    def __init__(self, observer, archive_callback, legacy_binding, verify_binding, *,
                 ready_directory, reader_path, manifest_path, interval_module=None):
        failure = None
        try:
            graph = interval if interval_module is None else interval_module
            need(type(graph) is types.ModuleType and pathlib.Path(graph.__file__).resolve() ==
                 pathlib.Path(interval.__file__).resolve(), 'configuration')
            need(type(observer) is graph.watch.Observer and
                 type(archive_callback) is graph.archive.QuiescentArchive and
                 archive_callback.quiescent is graph.quiescent and callable(verify_binding), 'configuration')
            observer.prerequisite()
            self.graph, self.observer, self.archive = graph, observer, archive_callback
            self.deadline, self.journal = observer.deadline, observer.journal
            self.bindings = {'legacy-approved': binding_checked(legacy_binding)}
            need(legacy_binding['phase'] == 'legacy-approved', 'binding')
            self.verify_binding = verify_binding
            self.directory = pathlib.Path(ready_directory)
            self.reader_path, self.manifest_path = pathlib.Path(reader_path), pathlib.Path(manifest_path)
            self.guard_api = admission.API(observer.transport.options)
            self.ready_api = ready.VerifiedAPI(observer.transport.options)
            self.operation = None; self.archive_pin = self.cipher_pin = None
            self.archive_result = self.archive_receipt = None
            self.active = self.closed = self.failed = False
            self.inode = self.saved_sha = None
            self.state = {'abi': 1, 'bindings': self.bindings, 'calls': [], 'archive_schema': None,
                          'overall_acceptance': False}
            with self.journal.control_lock:
                self.journal._owned()
                fd = os.open('phase-qualification.json', os.O_CREAT | os.O_EXCL | os.O_RDWR |
                             os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.journal.directory_fd)
                try:
                    info = os.fstat(fd); self.inode = (info.st_dev, info.st_ino); os.fsync(fd)
                finally: os.close(fd)
                os.fsync(self.journal.directory_fd); self._save()
        except Exception: failure = 'configuration'
        observer = archive_callback = legacy_binding = verify_binding = interval_module = graph = None
        if failure: self = ready_directory = reader_path = manifest_path = None
        if failure: raise Refused(failure) from None

    def _bounded(self):
        need(not self.closed and not self.failed and type(self.deadline) in (int, float) and
             math.isfinite(self.deadline) and time.monotonic() < self.deadline, 'deadline')
        self.observer.prerequisite()

    def _save(self):
        self.journal._owned()
        fd = os.open('phase-qualification.json', os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=self.journal.directory_fd)
        try:
            info = os.fstat(fd)
            need((info.st_dev, info.st_ino) == self.inode and info.st_uid == os.getuid() and
                 info.st_mode & 0o777 == 0o600 and info.st_nlink == 1 and info.st_size <= 65536, 'ownership')
            old = os.read(fd, 65537)
            need(self.saved_sha is None or sha(old) == self.saved_sha, 'ownership')
            raw = validator.canonical(self.state) + b'\n'; need(len(raw) <= 65536, 'bounds')
            os.lseek(fd, 0, os.SEEK_SET)
            need(os.write(fd, raw) == len(raw), 'ownership')
            os.ftruncate(fd, len(raw)); os.fsync(fd); os.fsync(self.journal.directory_fd)
            named = os.stat('phase-qualification.json', dir_fd=self.journal.directory_fd, follow_symlinks=False)
            need((named.st_dev, named.st_ino) == self.inode, 'ownership'); self.saved_sha = sha(raw)
        finally: os.close(fd)

    def bind(self, operation):
        failure = None
        try:
            self._bounded()
            need(self.operation is None and type(operation) is self.graph.quiescent.QuiescentCheckpoint and
                 operation.journal is self.journal and operation.trace is self.observer.trace and
                 operation.deadline == self.deadline and operation.archive_callback is self.archive and
                 type(operation.client) is self.graph.IntervalClient and operation.client.observer is self.observer,
                 'configuration')
            self.operation = operation
            self._binding(self.bindings['legacy-approved'])
        except Exception: self.failed = True; failure = 'configuration'
        self = operation = None
        if failure: raise Refused(failure) from None

    def _binding(self, value):
        baseline = self.operation.r['baseline']; contract = value['contract']
        need(contract['protected_pvc_names'] == baseline['protected_claim_names'], 'binding')
        legacy = baseline['legacy_image']; approved = contract['approved_image_references']
        need((value['phase'] == PHASES[0] and legacy in approved) or
             (value['phase'] == PHASES[1] and legacy not in approved and value['image'] != legacy), 'binding')

    def authorize_forward(self, value):
        failure = None
        try:
            self._bounded(); need(self.operation is not None and not self.active and
                PHASES[1] not in self.bindings and
                self.operation.r.get('quiescent', {}).get('state') == 'guard-transition-open', 'replay')
            checked = binding_checked(value); need(checked['phase'] == PHASES[1], 'binding'); self._binding(checked)
            for name, pin in checked['policy_pins'].items():
                original = self.bindings[PHASES[0]]['policy_pins'][name]
                need(pin['uid'] == original['uid'] and pin['binding_uid'] == original['binding_uid'], 'guard')
            self.bindings[PHASES[1]] = checked
            with self.journal.control_lock: self._save()
            self._bounded()
        except Exception: self.failed = True; failure = 'binding'
        value = None
        if failure: raise Refused(failure) from None

    def _guards(self, binding, deadline):
        for expected in validator.reviewed_renders(binding['contract']):
            self._bounded()
            kind, name = expected['kind'], expected['metadata']['name']
            obj = self.guard_api.guard(kind, name, deadline=deadline)
            validator.bounded(obj); meta = obj.get('metadata') if type(obj) is dict else None
            pin = binding['policy_pins'][name]; policy = kind == validator.POLICY
            need(type(meta) is dict and obj.get('apiVersion') == validator.API and obj.get('kind') == kind and
                 meta.get('name') == name and not meta.get('namespace') and not meta.get('deletionTimestamp') and
                 meta.get('uid') == pin['uid' if policy else 'binding_uid'] and
                 meta.get('resourceVersion') == pin['resourceVersion' if policy else 'binding_resourceVersion'], 'guard')
            actual = validator.canonical_spec(kind, obj.get('spec'))
            need(actual == validator.canonical_spec(kind, expected['spec']) and
                 sha(actual) == pin['spec_sha256' if policy else 'binding_spec_sha256'], 'guard')
            if policy:
                status = obj.get('status'); generation = meta.get('generation')
                need(type(generation) is int and generation > 0 and type(status) is dict and
                     type(status.get('observedGeneration')) is int and status['observedGeneration'] == generation and
                     type(status.get('typeChecking')) is dict and
                     set(status['typeChecking']) <= {'expressionWarnings'} and
                     status['typeChecking'].get('expressionWarnings', []) == [], 'guard')
            self._bounded()

    def _read_pin(self, path, expected, maximum=65536):
        pin = self.graph.archive.Pin(path, maximum)
        try:
            raw = os.read(pin.fd, maximum + 1); pin.check()
            need(len(raw) == os.fstat(pin.fd).st_size and sha(raw) == expected, 'schema')
            value = json.loads(raw); validator.bounded(value)
            return pin, value
        except Exception: pin.close(); raise

    def _ready_schema(self, deadline):
        floor = time.monotonic_ns()
        result = ready.collect(self.directory, self.reader_path, self.manifest_path, deadline,
                               floor, self.ready_api.get)
        need(type(result) is dict and set(result) == {'path', 'sha256', 'receipt'} and digest(result['sha256']) and
             pathlib.Path(result['path']).parent == self.directory and
             re.fullmatch('schema-metadata-[0-9a-f]{12}\\.json', pathlib.Path(result['path']).name), 'schema')
        pin, receipt = self._read_pin(result['path'], result['sha256'])
        try:
            expected = {'abi', 'scope', 'writer', 'migration_count', 'unfinished_migration_count',
                'rolled_back_migration_count', 'historical_migrations_match', 'topology_match', 'writer_unchanged',
                'collector_source_sha256', 'migration_manifest_sha256', 'observed_monotonic_ns', 'metadata_only'}
            need(type(receipt) is dict and set(receipt) == expected and receipt == result['receipt'] and
                 type(receipt['abi']) is int and receipt['abi'] == 1 and
                 receipt['scope'] == 'actual-current-writer-schema-metadata-only' and
                 type(receipt['migration_count']) is int and receipt['migration_count'] == 7 and
                 all(type(receipt[k]) is int and receipt[k] == 0 for k in
                     ('unfinished_migration_count', 'rolled_back_migration_count')) and
                 all(receipt[k] is True for k in ('historical_migrations_match', 'topology_match', 'writer_unchanged', 'metadata_only')) and
                 receipt['collector_source_sha256'] == ready.READER_SHA and receipt['migration_manifest_sha256'] == ready.MANIFEST_SHA and
                 type(receipt['observed_monotonic_ns']) is int and floor <= receipt['observed_monotonic_ns'] <= time.monotonic_ns(), 'schema')
            writer = receipt['writer']; baseline = self.operation.r['baseline']
            need(type(writer) is dict and set(writer) == {'name', 'namespace', 'uid', 'resourceVersion', 'image'} and
                 all(writer[k] == baseline['writer'][k] for k in ('name', 'namespace', 'uid')) and
                 writer['image'] == baseline['legacy_image'] and type(writer['resourceVersion']) is str and
                 0 < len(writer['resourceVersion']) <= 256, 'schema')
            self.last_ready_writer = copy.deepcopy(writer)
            return result['sha256'], 'fresh Ready-writer schema'
        finally: pin.close()

    def _archive_schema(self):
        operation = self.operation
        need(operation.r.get('sqlite_archive_state') == 'confirmed' and
             operation.r.get('quiescent', {}).get('state') in
             ('captured-zero', 'guard-transition-open', 'entrypoint-pending'), 'schema')
        before = operation.source(stopped=True)
        cipher = operation.r['sqlite_archive']
        if self.archive_result is None:
            need(operation.r['quiescent']['state'] in ('captured-zero', 'guard-transition-open'), 'schema')
            result = self.archive.schema_metadata(operation, self.manifest_path, ready.MANIFEST_SHA, deadline=self.deadline)
            need(type(result) is dict and set(result) == {'schema_receipt_path', 'schema_receipt_sha256', 'schema_migrations'} and
                 type(result['schema_migrations']) is int and result['schema_migrations'] == 7 and
                 digest(result['schema_receipt_sha256']) and pathlib.Path(result['schema_receipt_path']).parent == self.journal.directory and
                 re.fullmatch('quiescent-schema-[0-9a-f]{12}\\.json', pathlib.Path(result['schema_receipt_path']).name), 'schema')
            self.archive_pin, receipt = self._read_pin(result['schema_receipt_path'], result['schema_receipt_sha256'])
            expected = {'abi','scope','run_id','ciphertext_sha256','manifest_sha256','source_identities','schema_migrations',
                'migration_checksums_match','migrations_complete','tables_and_columns_match','tmpfs_cleaned',
                'live_ready_writer_proven','whole_row_preservation_proven','forward_acceptance','producer_sha256'}
            need(type(receipt) is dict and set(receipt) == expected and type(receipt['abi']) is int and receipt['abi'] == 1 and
                 receipt['scope'] == 'authenticated latest quiescent archive schema metadata only' and
                 receipt['run_id'] == operation.r['run_id'] and receipt['ciphertext_sha256'] == cipher['ciphertext_sha256'] and
                 receipt['manifest_sha256'] == ready.MANIFEST_SHA and type(receipt['schema_migrations']) is int and receipt['schema_migrations'] == 7 and
                 all(receipt[k] is True for k in ('migration_checksums_match','migrations_complete','tables_and_columns_match','tmpfs_cleaned')) and
                 all(receipt[k] is False for k in ('live_ready_writer_proven','whole_row_preservation_proven','forward_acceptance')) and
                 receipt['producer_sha256'] == sha(pathlib.Path(self.graph.archive.__file__).read_bytes()), 'schema')
            need(cipher['artifact'] == str(self.journal.directory/'sqlite-files.age'), 'schema')
            self.cipher_pin = self.graph.archive.Pin(cipher['artifact'], self.graph.archive.archive.MAX_TOTAL + 1048576)
            calculated = hashlib.sha256()
            while True:
                self._bounded(); block = os.read(self.cipher_pin.fd, 65536)
                if not block: break
                calculated.update(block)
            self.cipher_pin.check(); need(calculated.hexdigest() == cipher['ciphertext_sha256'], 'schema')
            self.archive_result, self.archive_receipt = result, receipt
            self.state['archive_schema'] = {'receipt_sha256': result['schema_receipt_sha256'],
                'ciphertext_sha256': receipt['ciphertext_sha256'], 'scope': 'static authenticated archive schema; fresh zero-writer fences'}
        self.archive_pin.check(); self.cipher_pin.check()
        receipt = self.archive_receipt
        need(cipher['ciphertext_sha256'] == receipt['ciphertext_sha256'] and
             set(before) == set(receipt['source_identities']) and all(
                 all(before[k].get(f) == receipt['source_identities'][k].get(f) for f in ('name','namespace','uid'))
                 for k in before), 'source')
        after = operation.source(stopped=True)
        need(set(after) == set(before) and all(after[k]['uid'] == before[k]['uid'] for k in before), 'source')
        return self.archive_result['schema_receipt_sha256'], 'static authenticated archive schema; fresh zero-writer fences'

    def _produce(self, phase, deadline):
        self._bounded()
        need(self.operation is not None and not self.active and deadline == self.deadline and
             phase in self.bindings and len(self.state['calls']) < 128, 'configuration')
        self.active = True; binding = copy.deepcopy(self.bindings[phase]); self._binding(binding)
        limit = min(deadline, time.monotonic() + 300)
        reply = self.verify_binding(copy.deepcopy(binding), limit)
        need(type(reply) is dict and validator.canonical(reply) == validator.canonical(binding), 'binding')
        self._guards(binding, limit)
        state = self.operation.r.get('quiescent', {}).get('state')
        need(self.archive_result is None or state in
             ('captured-zero', 'guard-transition-open', 'entrypoint-pending'), 'schema')
        if state in ('captured-zero', 'guard-transition-open', 'entrypoint-pending'):
            schema, scope = self._archive_schema()
        else:
            need(phase == PHASES[0] and state in (None, 'pending'), 'schema')
            schema, scope = self._ready_schema(limit)
        self._bounded(); self._guards(binding, limit)
        reply = self.verify_binding(copy.deepcopy(binding), limit)
        need(type(reply) is dict and validator.canonical(reply) == validator.canonical(binding), 'binding')
        if self.archive_result is not None:
            self._archive_schema()  # Fresh zero-writer/source pin after the remaining long IO.
        else:
            current = ready.snapshot(self.ready_api.get, limit)
            need(current['writer'] == self.last_ready_writer, 'source')
        self._bounded()
        packet = {k: binding[k] for k in ('phase','image','source_sha256','qualification_receipt_sha256','policy_pins')}
        packet.update(schema_receipt_sha256=schema, schema_migrations=7,
            approved_images=binding['contract']['approved_image_references'],
            protected_claim_names=binding['contract']['protected_pvc_names'])
        self.state['calls'].append({'phase': phase, 'schema_receipt_sha256': schema, 'schema_scope': scope,
                                   'packet_sha256': sha(validator.canonical(packet)), 'overall_acceptance': False})
        with self.journal.control_lock: self._save()
        self._bounded(); return copy.deepcopy(packet)

    def __call__(self, phase, deadline):
        result = failure = None
        try: result = self._produce(phase, deadline)
        except Refused as error: failure = error.code
        except Exception: failure = 'qualification'
        finally: self.active = False
        if failure: self.failed = True
        self = phase = deadline = None
        if failure: raise Refused(failure) from None
        return result

    def close(self):
        failure = False
        for pin in (self.archive_pin, self.cipher_pin):
            if pin is not None:
                try: pin.close()
                except Exception: failure = True
        self.archive_pin = self.cipher_pin = None; self.closed = True
        if failure: raise Refused('cleanup') from None
