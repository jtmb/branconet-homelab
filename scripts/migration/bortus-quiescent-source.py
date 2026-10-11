"""Separate cold-without-resume interval; no CLI or implicit forward authorization."""
import copy
import hashlib
import importlib.util
import json
import math
import pathlib
import re
import time


spec = importlib.util.spec_from_file_location('quiescent_cold',
    pathlib.Path(__file__).with_name('checkpoint-bortus-volume.py'))
cold = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cold)

CONTROL_KEYS = ('deployment', 'helmrelease', 'kustomization')
TARGETS = {'deployment': 0, 'helmrelease': True, 'kustomization': True}
POLICIES = ('bortus-kv-guard-pods', 'bortus-kv-guard-templates', 'bortus-kv-guard-cronjobs')


class QuiescentRefused(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__('Quiescent source refused: ' + code)


def need(value, code):
    if not value:
        raise QuiescentRefused(code)


def digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def control_spec(obj, key):
    value = copy.deepcopy(obj['spec'])
    value.pop(cold.RESOURCES[key][3], None)
    return sha(value)


class ControlTrace:
    """Bounded projected observations supplied by a trusted durable watch producer.

    This object does not establish TLS readiness or event continuity itself. The
    producer must open all three watches from complete LIST RVs before mutation,
    persist each event, and call fail on EOF/ERROR/410/gap/overflow/fsync failure.
    RVs are opaque: latest-observed equality is checked, never numeric ordering.
    """
    def __init__(self, pins, readiness):
        need(type(pins) is dict and set(pins) == set(CONTROL_KEYS), 'watch')
        need(all(type(p) is dict and set(p) == {'name', 'namespace', 'uid', 'resourceVersion',
            'spec_sha256', 'original'} and digest(p['spec_sha256']) and
            type(p['original']) is type(TARGETS[k]) and
            all(type(p[f]) is str and 0 < len(p[f]) <= 256 for f in ('name', 'uid', 'resourceVersion'))
            and p['namespace'] == ('bortus' if k == 'deployment' else 'flux-system')
            for k, p in pins.items()), 'watch')
        need(type(readiness) is dict and set(readiness) == {
            'source_sha256', 'receipt_sha256', 'collection_rvs', 'watch_handles'} and
            digest(readiness['source_sha256']) and digest(readiness['receipt_sha256']) and
            all(type(readiness[k]) is dict and set(readiness[k]) == set(CONTROL_KEYS)
                and all(type(v) is str and 0 < len(v) <= 256 for v in readiness[k].values())
                for k in ('collection_rvs', 'watch_handles')), 'watch')
        self.pins = copy.deepcopy(pins)
        self.readiness = copy.deepcopy(readiness)
        self.latest, self.stopped, self.failure, self.count = {}, set(), None, 0
        self.owner_resume_authorized = self.owner_resumed = False

    def authorize_owner_resume(self):
        need(self.failure is None and self.stopped == set(CONTROL_KEYS) and
             self.pins['kustomization']['original'] is False and not self.owner_resume_authorized, 'watch')
        self.owner_resume_authorized = True

    def fail(self):
        self.failure = 'watch'

    def observe(self, event):
        failure = None
        try:
            need(self.failure is None and self.count < 10000, 'watch')
            need(type(event) is dict and set(event) == {
                'type', 'resource', 'uid', 'resourceVersion', 'spec_sha256', 'value'}, 'watch')
            key = event['resource']
            need(key in CONTROL_KEYS and event['type'] in ('ADDED', 'MODIFIED'), 'watch')
            pin = self.pins[key]
            need(event['uid'] == pin['uid'] and event['spec_sha256'] == pin['spec_sha256'] and
                 type(event['resourceVersion']) is str and 0 < len(event['resourceVersion']) <= 256,
                 'watch')
            value = event['value']
            owner_transition = key == 'kustomization' and self.owner_resume_authorized
            need(type(value) is type(TARGETS[key]) and
                 ((owner_transition and value is False) or
                 (value == TARGETS[key] or (key not in self.stopped and value == pin['original']))),
                 'watch')
            need(not (key == 'kustomization' and self.owner_resumed and value is True), 'watch')
            if owner_transition and value is False: self.owner_resumed = True
            if value == TARGETS[key]: self.stopped.add(key)
            self.latest[key] = event['resourceVersion']
            self.count += 1
        except Exception:
            self.fail()
            failure = 'watch'
        event = None
        if failure: raise QuiescentRefused(failure)

    def check(self, identities, *, stopped):
        need(self.failure is None and set(self.latest) == set(CONTROL_KEYS) and
             (not stopped or self.stopped == set(CONTROL_KEYS)) and
             all(identities[k]['resourceVersion'] == self.latest[k] for k in CONTROL_KEYS), 'watch')


class QuiescentCheckpoint(cold.Checkpoint):
    """Compose existing cold primitives without calling capture(), resume(), or CLI.

    The outer owner closes its journal/watch/transport. No automatic restoration
    is safe after legacy withdrawal or an ambiguous entrypoint dispatch.
    """
    def __init__(self, client, journal, trace, qualify, archive, *, deadline,
                 sleep=time.sleep, monotonic=time.monotonic):
        super().__init__(client, journal, sleep, monotonic)
        need('quiescent' not in self.r, 'replay')
        need(type(trace) is ControlTrace and callable(qualify) and callable(archive), 'configuration')
        need(type(deadline) in (int, float) and math.isfinite(deadline) and
             monotonic() < deadline <= monotonic() + 2100, 'deadline')
        self.trace, self.qualify, self.archive_callback, self.deadline = trace, qualify, archive, deadline
        self.pins = trace.pins
        self.legacy_binding = None
        self.final_binding = None
        self.storage_pins = self.r['baseline']['quiescent_storage_pins']
        need(type(self.storage_pins) is dict and set(self.storage_pins) == {'pvc', 'pv', 'storageclass'}
             and all(type(p) is dict and set(p) == {'name', 'namespace', 'uid', 'spec_sha256'} and
                     digest(p['spec_sha256']) and type(p['uid']) is str and 0 < len(p['uid']) <= 256
                     for p in self.storage_pins.values()), 'configuration')
        for kind, source_key in (('pvc', 'claim'), ('pv', 'pv')):
            need(all(self.storage_pins[kind][f] == self.r['baseline']['identities'][source_key][f]
                     for f in ('name', 'namespace', 'uid')), 'configuration')
        need(self.storage_pins['storageclass']['name'] == 'longhorn' and
             self.storage_pins['storageclass']['namespace'] is None, 'configuration')

    def bounded(self):
        need(self.monotonic() < self.deadline, 'deadline')

    def wait(self, predicate, seconds):
        until = min(self.deadline, self.monotonic() + seconds)
        while True:
            self.bounded()
            value = predicate()
            self.bounded()
            if value: return value
            need(self.monotonic() < until, 'deadline')
            self.sleep(min(2, until - self.monotonic()))

    def qualification(self, phase):
        value = self.qualify(phase, self.deadline)
        need(type(value) is dict and set(value) == {'phase', 'image', 'source_sha256',
            'qualification_receipt_sha256', 'schema_receipt_sha256', 'schema_migrations',
            'policy_pins', 'approved_images', 'protected_claim_names'} and value['phase'] == phase and
            cold.valid_digest(value['image']) and digest(value['source_sha256']) and
            digest(value['qualification_receipt_sha256']) and digest(value['schema_receipt_sha256']) and
            type(value['schema_migrations']) is int and value['schema_migrations'] == 7 and
            type(value['protected_claim_names']) is list and
            value['protected_claim_names'] == self.r['baseline']['protected_claim_names'] and
            'bortus-data' in value['protected_claim_names'] and
            type(value['approved_images']) is list and 0 < len(value['approved_images']) <= 8 and
            len(set(value['approved_images'])) == len(value['approved_images']) and
            all(cold.valid_digest(i) for i in value['approved_images']) and
            value['image'] in value['approved_images'], 'qualification')
        pins = value['policy_pins']
        need(type(pins) is dict and set(pins) == set(POLICIES) and all(
            type(p) is dict and set(p) == {'uid', 'resourceVersion', 'spec_sha256', 'binding_uid',
                                          'binding_resourceVersion', 'binding_spec_sha256'} and
            digest(p['spec_sha256']) and digest(p['binding_spec_sha256']) and
            all(type(p[k]) is str and 0 < len(p[k]) <= 256 for k in (
                'uid', 'resourceVersion', 'binding_uid', 'binding_resourceVersion')) for p in pins.values()),
            'qualification')
        legacy = self.r['baseline']['legacy_image']
        need((phase == 'legacy-approved' and legacy in value['approved_images']) or
             (phase == 'forward-compatible' and legacy not in value['approved_images'] and
              value['image'] != legacy), 'qualification')
        if self.legacy_binding is not None:
            for name in POLICIES:
                for key in ('uid', 'binding_uid'):
                    need(pins[name][key] == self.legacy_binding['policy_pins'][name][key], 'qualification')
        self.bounded()
        return copy.deepcopy(value)

    def source(self, *, stopped, holder=False):
        self.bounded()
        self.storage()
        for kind, ns in (('pvc', 'bortus'), ('pv', None), ('storageclass', None)):
            pin = self.storage_pins[kind]
            obj = self.client.get(kind, pin['name'], ns)
            body = obj.get('spec') if kind != 'storageclass' else {
                k: v for k, v in obj.items() if k not in ('apiVersion', 'kind', 'metadata')}
            need(cold.same_id(obj, pin) and not obj['metadata'].get('deletionTimestamp') and
                 sha(body) == pin['spec_sha256'], 'source')
            if kind == 'pvc':
                need(body.get('storageClassName') == 'longhorn' and
                     body.get('resources', {}).get('requests', {}).get('storage') == '1Gi', 'source')
        volume = self.client.get('volumes.longhorn.io',
            self.r['baseline']['identities']['longhorn_volume']['name'], 'longhorn-system')
        need(volume['spec'].get('dataEngine') == 'v1' and volume['spec'].get('size') == '1073741824' and
             volume['spec'].get('Standby') is False, 'source')
        identities = {}
        for key in CONTROL_KEYS:
            kind, name, ns, field = cold.RESOURCES[key]
            obj = self.client.get(kind, name, ns)
            identities[key] = cold.identity(obj)
            pin = self.pins[key]
            need(cold.same_id(obj, pin) and not obj['metadata'].get('deletionTimestamp') and
                 control_spec(obj, key) == pin['spec_sha256'], 'source')
            desired = TARGETS[key] if stopped else pin['original']
            if stopped and key == 'kustomization' and self.r.get('quiescent', {}).get(
                    'owner_resume_intent', {}).get('state') == 'confirmed':
                desired = False
            actual = obj['spec'].get(field, False if field == 'suspend' else None)
            need(type(actual) is type(desired) and actual == desired, 'source')
        self.trace.check(identities, stopped=stopped)
        pods = cold.preflight.complete_pods(self.client.get('pods', namespace='bortus'))
        active = [p for p in pods if cold.preflight.uses_claim(p) and
                  p['status']['phase'] not in ('Succeeded', 'Failed')]
        if stopped:
            if holder:
                need(self.cold(), 'source')
            else:
                need(not active and all(p['metadata']['uid'] != self.r['baseline']['writer']['uid'] and
                    p['metadata']['name'] != self.r['baseline']['writer']['name'] for p in pods), 'source')
        self.bounded()
        return identities

    def _capture_quiescent(self):
        need('quiescent' not in self.r and 'holder_create_state' not in self.r, 'replay')
        self.source(stopped=False)
        fresh = self.client.inspect(self.r['baseline']['identities']['claim']['uid'],
                                    self.r['holder_proposal']['spec']['containers'][0]['image'])
        need(fresh['writer'] == self.r['baseline']['writer'], 'source')
        deployment = self.client.get('deployment', 'bortus', 'bortus')
        images = deployment['spec']['template']['spec'].get('containers')
        need(type(images) is list and len(images) == 1 and
             images[0].get('image') == self.r['baseline']['legacy_image'], 'source')
        for key in ('claim', 'pv', 'longhorn_volume', *CONTROL_KEYS):
            need(all(fresh['identities'][key][f] == self.r['baseline']['identities'][key][f]
                     for f in ('name', 'namespace', 'uid')), 'source')
        self.legacy_binding = self.qualification('legacy-approved')
        self.r['quiescent'] = {'state': 'pending', 'watch_binding': self.trace.readiness,
            'legacy_binding': self.legacy_binding, 'forward_acceptance': False}
        self.journal.save()
        body = self.r['holder_proposal']
        self.client.create(body, dry_run=True)
        self.create_owned('holder', body)
        self.wait(lambda: self.holder()['status']['phase'] == 'Running', 180)
        for key in ('kustomization', 'helmrelease', 'deployment'):
            self.qualification('legacy-approved')
            old = self.r['controls'][key]['original']
            if old != TARGETS[key]: self.control(key, old, TARGETS[key])
        self.wait(self.cold, 180)
        self.source(stopped=True, holder=True)
        self.r['sqlite_archive_state'] = 'pending'
        self.journal.save()
        result = self.archive_callback(self, self.deadline)
        need(type(result) is dict and set(result) == {'artifact', 'ciphertext_sha256', 'files',
            'plaintext_bytes', 'authenticated_decryption_equal', 'plaintext_persisted',
            'sqlite_integrity_or_row_preservation_proven', 'nas_artifact', 'nas_ciphertext_equal'} and
            result.get('authenticated_decryption_equal') is True and
             result.get('nas_ciphertext_equal') is True and result.get('plaintext_persisted') is False and
             result.get('sqlite_integrity_or_row_preservation_proven') is False and
             type(result['files']) is list and 'bortus.db' in result['files'] and
             len(set(result['files'])) == len(result['files']) and
             all(f in ('bortus.db', 'bortus.db-wal', 'bortus.db-shm') for f in result['files']) and
             type(result['plaintext_bytes']) is int and 0 < result['plaintext_bytes'] <= 1073741824 and
             all(type(result[k]) is str and 0 < len(result[k]) <= 4096 for k in ('artifact', 'nas_artifact'))
             and digest(result.get('ciphertext_sha256')), 'archive')
        self.source(stopped=True, holder=True)
        self.r['sqlite_archive'], self.r['sqlite_archive_state'] = result, 'confirmed'
        self.journal.save()
        volume = self.r['baseline']['identities']['longhorn_volume']['name']
        snapshot = {'apiVersion': 'longhorn.io/v1beta2', 'kind': 'Snapshot', 'metadata': {
            'name': self.r['snapshot_name'], 'namespace': 'longhorn-system',
            'labels': {'bortus-checkpoint': self.r['run_id']}}, 'spec': {'volume': volume,
            'createSnapshot': True, 'labels': {'bortus-consistency': 'cold-writer-stopped'}}}
        self.create_owned('snapshot', snapshot)
        def snapshot_done():
            self.source(stopped=True, holder=True)
            obj = self.client.get('snapshots.longhorn.io', self.r['snapshot_name'], 'longhorn-system')
            need(cold.same_id(obj, self.r['snapshot_identity']) and not obj['metadata'].get('deletionTimestamp')
                 and all(obj['spec'].get(k) == v for k, v in snapshot['spec'].items()) and
                 not obj.get('status', {}).get('error'), 'snapshot')
            return obj.get('status', {}).get('readyToUse') is True
        self.wait(snapshot_done, 300)
        self.r['cold_snapshot_ready'] = True
        self.journal.save()
        backup = {'apiVersion': 'longhorn.io/v1beta2', 'kind': 'Backup', 'metadata': {
            'name': self.r['backup_name'], 'namespace': 'longhorn-system', 'labels': {
                'backup-volume': volume, 'backup-target': 'default', 'bortus-checkpoint': self.r['run_id']}},
            'spec': {'snapshotName': self.r['snapshot_name'], 'backupMode': 'full',
                     'labels': {'bortus-consistency': 'cold-writer-stopped'}}}
        self.create_owned('backup', backup)
        def backup_done():
            self.source(stopped=True, holder=True)
            obj = self.client.get('backups.longhorn.io', self.r['backup_name'], 'longhorn-system')
            status = obj.get('status', {})
            need(cold.same_id(obj, self.r['backup_identity']) and not obj['metadata'].get('deletionTimestamp')
                 and all(obj['spec'].get(k) == backup['spec'][k] for k in ('snapshotName', 'backupMode'))
                 and obj['spec'].get('labels', {}).get('bortus-consistency') == 'cold-writer-stopped'
                 and not status.get('error') and status.get('state') != 'Error', 'backup')
            if status.get('state') != 'Completed': return False
            need(status.get('volumeName') == volume and status.get('snapshotName') == self.r['snapshot_name']
                 and status.get('volumeSize') == '1073741824' and status.get('backupTargetName') == 'default', 'backup')
            # Reuse the exact reviewed credential-free NAS URL parser without invoking ReadySourceFence.
            loader = importlib.util.spec_from_file_location('quiescent_restore_preflight',
                pathlib.Path(__file__).with_name('inspect-bortus-independent-restore.py'))
            preflight = importlib.util.module_from_spec(loader)
            loader.loader.exec_module(preflight)
            preflight.url_matches(status.get('url'), self.r['backup_name'], volume)
            self.r['backup_url'] = status['url']
            return True
        self.wait(backup_done, 1800)
        self.r['encrypted_nas_backup_complete'] = True
        self.journal.save()
        self.release_holder()
        identities = self.source(stopped=True)
        self.r['quiescent'].update(state='captured-zero', source=identities,
                                  ciphertext_sha256=result['ciphertext_sha256'])
        self.journal.save()
        return {'scope': 'quiescent current-data checkpoint only', 'forward_acceptance': False}

    def _open_guard_transition(self):
        need(self.r.get('quiescent', {}).get('state') == 'captured-zero' and
             'owner_resume_intent' not in self.r['quiescent'], 'replay')
        ids = self.source(stopped=True)
        self.qualification('legacy-approved')
        self.r['quiescent']['owner_resume_intent'] = {'identity': ids['kustomization'], 'state': 'pending'}
        self.journal.save()
        self.trace.authorize_owner_resume()
        try:
            self.control('kustomization', True, False)
        except Exception:
            self.r['quiescent']['owner_resume_intent']['state'] = 'uncertain'
            self.journal.save()
            raise QuiescentRefused('owner_resume') from None
        self.r['quiescent']['owner_resume_intent']['state'] = 'confirmed'
        self.journal.save()
        self.source(stopped=True)
        self.r['quiescent']['state'] = 'guard-transition-open'
        self.journal.save()
        return {'guard_owner_active': True, 'forward_acceptance': False}

    def _dispatch(self, launch):
        need(callable(launch) and self.r.get('quiescent', {}).get('state') == 'guard-transition-open', 'replay')
        self.source(stopped=True)
        binding = self.qualification('forward-compatible')
        self.r['quiescent'].update(state='entrypoint-pending', final_binding=binding)
        self.journal.save()  # Durable intent before the single caller-owned launch.
        self.source(stopped=True)
        need(self.qualification('forward-compatible') == binding, 'qualification')
        try:
            result = launch(binding, self.deadline)
            self.bounded()
            need(type(result) is dict and set(result) == {'dispatch_receipt_sha256'} and
                 digest(result['dispatch_receipt_sha256']), 'entrypoint')
        except Exception:
            self.r['quiescent']['state'] = 'entrypoint-uncertain'
            self.journal.save()
            raise QuiescentRefused('entrypoint') from None
        self.r['quiescent'].update(state='entrypoint-submitted', dispatch_receipt_sha256=result['dispatch_receipt_sha256'])
        self.journal.save()
        return {'entrypoint_submitted': True, 'forward_acceptance': False}

    def _public(self, method, argument=None):
        failure, value = None, None
        try:
            value = method() if argument is None else method(argument)
        except QuiescentRefused as error:
            failure = error.code
        except Exception:
            failure = 'operation'
        return value if not failure else None, failure

    def capture_quiescent(self):
        value, failure = self._public(self._capture_quiescent)
        if failure: raise QuiescentRefused(failure)
        return value

    def dispatch_entrypoint(self, launch):
        value, failure = self._public(self._dispatch, launch)
        launch = None
        if failure: raise QuiescentRefused(failure)
        return value

    def open_guard_transition(self):
        value, failure = self._public(self._open_guard_transition)
        if failure: raise QuiescentRefused(failure)
        return value

    def resume(self):
        raise QuiescentRefused('separate_recovery_required')

    def capture(self):
        raise QuiescentRefused('use_capture_quiescent')
