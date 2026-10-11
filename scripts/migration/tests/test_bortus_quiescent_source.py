"""Synthetic API/archive callbacks and actual POSIX journal faults only."""
import copy
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value
m = load('quiescent_test_source', HERE.parent / 'bortus-quiescent-source.py')
f = load('quiescent_test_fixtures', HERE / 'test_bortus_cold_checkpoint.py')
LEGACY, FINAL = f.IMAGE, 'registry.example/bortus@sha256:' + 'b' * 64


class Client(f.FakeClient):
    trace = None
    def get(self, kind, name=None, namespace=None):
        obj = super().get(kind, name, namespace)
        if self.trace and kind in m.CONTROL_KEYS:
            field = m.cold.RESOURCES[kind][3]
            self.trace.observe({'type': 'MODIFIED', 'resource': kind, 'uid': obj['metadata']['uid'],
                'resourceVersion': obj['metadata']['resourceVersion'], 'spec_sha256': m.control_spec(obj, kind),
                'value': obj['spec'].get(field, False)})
        return obj
    def create(self, body, dry_run=False):
        result = super().create(body, dry_run)
        if body['kind'] == 'Backup' and not dry_run:
            extra = {'volumeName': 'pvc-fixture', 'snapshotName': body['spec']['snapshotName'],
                     'volumeSize': '1073741824', 'backupTargetName': 'default'}
            self.owned[body['metadata']['name']]['status'].update(extra)
            result['status'].update(extra)
        return result


def prepare(journal_factory=f.MemoryJournal):
    c = Client()
    c.resources['pvc']['spec']['resources'] = {'requests': {'storage': '1Gi'}}
    c.resources['volumes.longhorn.io']['spec'].update(dataEngine='v1', size='1073741824', Standby=False)
    c.resources['deployment']['spec']['template']['spec']['containers'][0]['image'] = LEGACY
    c.resources['storageclass'] = {'metadata': {'name': 'longhorn', 'namespace': None,
        'uid': 'longhorn-sc-uid', 'resourceVersion': 'opaque-sc'}, 'provisioner': 'driver.longhorn.io',
        'reclaimPolicy': 'Retain', 'parameters': {'encrypted': 'true'}}
    expected = m.cold.preflight.evaluate(copy.deepcopy(c.objects), 'bortus-data-uid')
    r = m.cold.prepare(c, expected, f.IMAGE, '123456abcdef')
    r['baseline'].update(legacy_image=LEGACY, protected_claim_names=['bortus-data', 'bortus-restore-fixture'])
    r['baseline']['quiescent_storage_pins'] = {}
    for kind in ('pvc', 'pv', 'storageclass'):
        obj = c.resources[kind]
        body = obj['spec'] if kind != 'storageclass' else {k: v for k, v in obj.items()
            if k not in ('apiVersion', 'kind', 'metadata')}
        r['baseline']['quiescent_storage_pins'][kind] = {k: obj['metadata'][k]
            for k in ('name', 'namespace', 'uid')} | {'spec_sha256': m.sha(body)}
    pins = {k: m.cold.identity(c.resources[k]) | {'spec_sha256': m.control_spec(c.resources[k], k),
        'original': c.resources[k]['spec'].get(m.cold.RESOURCES[k][3], False)} for k in m.CONTROL_KEYS}
    trace = m.ControlTrace(pins, {'source_sha256': '1'*64, 'receipt_sha256': '2'*64,
        'collection_rvs': {k: 'opaque-list' for k in m.CONTROL_KEYS},
        'watch_handles': {k: 'opaque-handle-'+k for k in m.CONTROL_KEYS}})
    c.trace = trace
    clock = [0]
    def sleep(seconds): clock[0] += seconds
    def qualify(phase, deadline):
        return {'phase': phase, 'image': FINAL, 'source_sha256': '3'*64,
            'qualification_receipt_sha256': '4'*64, 'schema_receipt_sha256': '5'*64, 'schema_migrations': 7,
            'approved_images': [FINAL, LEGACY] if phase == 'legacy-approved' else [FINAL],
            'protected_claim_names': r['baseline']['protected_claim_names'],
            'policy_pins': {k: {'uid': k+'-uid', 'resourceVersion': 'opaque-policy-rv',
                'spec_sha256': '6'*64, 'binding_uid': k+'-binding-uid',
                'binding_resourceVersion': 'opaque-binding-rv', 'binding_spec_sha256': '7'*64} for k in m.POLICIES}}
    def archive(op, deadline):
        assert deadline == 2000 and op.cold() and c.resources['deployment']['spec']['replicas'] == 0
        return {'artifact': '/public/sqlite.age', 'ciphertext_sha256': '8'*64, 'files': ['bortus.db'],
            'plaintext_bytes': 8192, 'authenticated_decryption_equal': True, 'plaintext_persisted': False,
            'sqlite_integrity_or_row_preservation_proven': False, 'nas_artifact': '/public/nas.age', 'nas_ciphertext_equal': True}
    j = journal_factory(r)
    op = m.QuiescentCheckpoint(c, j, trace, qualify, archive, deadline=2000,
                               sleep=sleep, monotonic=lambda: clock[0])
    return c, j, op, clock


class QuiescentTests(unittest.TestCase):
    def test_full_backup_stays_zero_then_compatible_once_only(self):
        c, j, op, _ = prepare()
        self.assertFalse(op.capture_quiescent()['forward_acceptance'])
        self.assertEqual('captured-zero', j.record['quiescent']['state'])
        self.assertTrue(j.record['encrypted_nas_backup_complete'])
        self.assertFalse(j.record['writer_resumed_ready'])
        self.assertEqual([0], [x[3] for x in c.calls if x[:2] == ('change', 'deployment')])
        self.assertEqual([], c.resources['pods']['items'])
        self.assertFalse(op.open_guard_transition()['forward_acceptance'])
        self.assertEqual(False, c.resources['kustomization']['spec']['suspend'])
        self.assertTrue(c.resources['helmrelease']['spec']['suspend'])
        calls = []
        def launch(binding, deadline):
            self.assertEqual('entrypoint-pending', j.saved[-1]['quiescent']['state'])
            self.assertNotIn(LEGACY, binding['approved_images'])
            calls.append(1)
            return {'dispatch_receipt_sha256': '9'*64}
        self.assertFalse(op.dispatch_entrypoint(launch)['forward_acceptance'])
        for call in (lambda: op.dispatch_entrypoint(launch), op.capture_quiescent, op.resume):
            with self.assertRaises(m.QuiescentRefused): call()
        self.assertEqual([1], calls)

    def test_ambiguous_stop_not_replayed_or_resumed(self):
        for when in ('before', 'after'):
            c, j, op, _ = prepare(); c.fail_change = ('deployment', when)
            with self.assertRaises(m.QuiescentRefused): op.capture_quiescent()
            self.assertEqual('uncertain', j.record['controls']['deployment']['intent']['state'])
            self.assertFalse(any(x[0] == 'create' and x[1] == 'Snapshot' for x in c.calls))
            self.assertFalse(any(x[:2] == ('change', 'deployment') and x[3] == 1 for x in c.calls))
            with self.assertRaises(m.QuiescentRefused): op.capture_quiescent()

    def test_archive_failure_retains_zero_holder_pending(self):
        c, j, op, _ = prepare()
        def bad(*_): raise ValueError('PRIVATE_CALLBACK_VALUE')
        op.archive_callback = bad
        with self.assertRaises(m.QuiescentRefused): op.capture_quiescent()
        self.assertEqual(0, c.resources['deployment']['spec']['replicas'])
        self.assertEqual('pending', j.record['sqlite_archive_state'])
        self.assertFalse(any(x[0] == 'delete-holder' for x in c.calls))

    def test_current_writer_template_claim_alias_drift_before_mutation(self):
        for kind in ('writer', 'template', 'claim', 'alias'):
            c, _, op, _ = prepare()
            if kind == 'writer': c.resources['pods']['items'][0]['metadata']['uid'] = 'new-writer'
            elif kind == 'template': c.resources['deployment']['spec']['template']['spec']['containers'][0]['env'] = []
            elif kind == 'claim': c.resources['pvc']['metadata']['uid'] = 'new-claim'
            else:
                alias = copy.deepcopy(c.resources['pvs']['items'][0]); alias['metadata'].update(name='alias', uid='alias-uid')
                c.resources['pvs']['items'].append(alias)
            with self.subTest(kind=kind), self.assertRaises(m.QuiescentRefused): op.capture_quiescent()
            self.assertEqual([], c.calls)

    def test_final_legacy_schema_policy_or_protected_claim_drift_refused(self):
        for kind in ('legacy', 'schema', 'policy', 'claims', 'bool'):
            _, _, op, _ = prepare(); op.capture_quiescent(); op.open_guard_transition(); old = op.qualify
            def bad(phase, deadline):
                value = old(phase, deadline)
                if kind == 'legacy': value['approved_images'].append(LEGACY)
                elif kind == 'schema': value['schema_migrations'] = 11
                elif kind == 'policy': value['policy_pins'][m.POLICIES[0]]['uid'] = 'replacement'
                elif kind == 'claims': value['protected_claim_names'] = ['bortus-data']
                else: return True
                return value
            op.qualify = bad
            with self.subTest(kind=kind), self.assertRaises(m.QuiescentRefused):
                op.dispatch_entrypoint(lambda *_: self.fail('must not dispatch'))

    def test_sticky_watch_resume_gap_uid_spec_bad_type(self):
        for kind in ('resume', 'gap', 'uid', 'spec', 'type', 'missing'):
            _, _, op, _ = prepare(); op.capture_quiescent(); op.open_guard_transition()
            if kind == 'gap': op.trace.fail()
            else:
                event = {'type': 'MODIFIED', 'resource': 'deployment', 'uid': op.pins['deployment']['uid'],
                    'resourceVersion': 'opaque-not-number', 'spec_sha256': op.pins['deployment']['spec_sha256'], 'value': 0}
                if kind == 'resume': event['value'] = 1
                elif kind == 'uid': event['uid'] = 'replacement'
                elif kind == 'spec': event['spec_sha256'] = '0'*64
                elif kind == 'type': event['value'] = False
                else: event.pop('value')
                with self.assertRaises(m.QuiescentRefused): op.trace.observe(event)
            with self.subTest(kind=kind), self.assertRaises(m.QuiescentRefused):
                op.dispatch_entrypoint(lambda *_: self.fail('must not dispatch'))

    def test_entrypoint_lost_reply_uncertain_no_retry(self):
        _, j, op, _ = prepare(); op.capture_quiescent(); op.open_guard_transition(); calls = []
        def launch(*_): calls.append(1); raise RuntimeError('PRIVATE_ENTRYPOINT_ERROR')
        with self.assertRaises(m.QuiescentRefused): op.dispatch_entrypoint(launch)
        self.assertEqual('entrypoint-uncertain', j.record['quiescent']['state'])
        with self.assertRaises(m.QuiescentRefused): op.dispatch_entrypoint(launch)
        self.assertEqual([1], calls)

    def test_reopened_captured_interval_cannot_be_adopted(self):
        c, j, op, _ = prepare(); op.capture_quiescent()
        with self.assertRaises(m.QuiescentRefused):
            m.QuiescentCheckpoint(c, j, op.trace, op.qualify, op.archive_callback,
                                  deadline=2000, monotonic=lambda: 0)

    def test_storage_pins_cannot_substitute_a_different_healthy_claim(self):
        for kind in ('pvc', 'pv', 'storageclass'):
            c, j, op, _ = prepare()
            j.record['baseline']['quiescent_storage_pins'][kind]['name'] = 'foreign'
            with self.subTest(kind=kind), self.assertRaises(m.QuiescentRefused):
                m.QuiescentCheckpoint(c, j, op.trace, op.qualify, op.archive_callback,
                                      deadline=2000, monotonic=lambda: 0)
            self.assertEqual([], c.calls)

    def test_late_or_malformed_launch_reply_is_uncertain(self):
        for late in (False, True):
            _, j, op, clock = prepare(); op.capture_quiescent(); op.open_guard_transition()
            def launch(*_):
                if late: clock[0] = 2001
                return {'dispatch_receipt_sha256': '9'*64} if late else {'success': True}
            with self.assertRaises(m.QuiescentRefused): op.dispatch_entrypoint(launch)
            self.assertEqual('entrypoint-uncertain', j.record['quiescent']['state'])

    def test_deadline_during_archive_no_snapshot(self):
        c, _, op, clock = prepare(); old = op.archive_callback
        def late(*args): value = old(*args); clock[0] = 2001; return value
        op.archive_callback = late
        with self.assertRaises(m.QuiescentRefused): op.capture_quiescent()
        self.assertFalse(any(x[0] == 'create' and x[1] == 'Snapshot' for x in c.calls))

    def test_incomplete_pods_or_foreign_consumer_no_dispatch(self):
        for kind in ('continue', 'foreign'):
            c, _, op, _ = prepare(); op.capture_quiescent(); op.open_guard_transition()
            if kind == 'continue': c.resources['pods']['metadata']['continue'] = 'more'
            else: c.resources['pods']['items'].append(copy.deepcopy(f.fixtures.fixture()[4]['items'][0]))
            with self.subTest(kind=kind), self.assertRaises(m.QuiescentRefused):
                op.dispatch_entrypoint(lambda *_: self.fail('must not dispatch'))

    def test_explicit_storage_shape_and_secret_reference_spec_drift(self):
        for kind in ('size', 'engine', 'standby', 'sc', 'claim-capacity', 'pv-spec'):
            c, _, op, _ = prepare()
            if kind == 'size': c.resources['volumes.longhorn.io']['spec']['size'] = '2Gi'
            elif kind == 'engine': c.resources['volumes.longhorn.io']['spec']['dataEngine'] = 'v2'
            elif kind == 'standby': c.resources['volumes.longhorn.io']['spec']['Standby'] = True
            elif kind == 'sc': c.resources['storageclass']['parameters']['encryption-secret'] = 'foreign'
            elif kind == 'claim-capacity': c.resources['pvc']['spec']['resources']['requests']['storage'] = '2Gi'
            else: c.resources['pv']['spec']['csi']['volumeAttributes'] = {'foreign': 'metadata'}
            with self.subTest(kind=kind), self.assertRaises(m.QuiescentRefused): op.capture_quiescent()
            self.assertEqual([], c.calls)

    def test_get_rv_latest_opaque_observation_and_overflow_sticky(self):
        c, _, op, _ = prepare()
        for key in m.CONTROL_KEYS: c.get(key)
        ids = {key: m.cold.identity(c.resources[key]) for key in m.CONTROL_KEYS}
        op.trace.latest['deployment'] = 'opaque-different'
        with self.assertRaises(m.QuiescentRefused): op.trace.check(ids, stopped=False)
        op.trace.count = 10000
        with self.assertRaises(m.QuiescentRefused): c.get('deployment')
        self.assertEqual('watch', op.trace.failure)

    def test_raw_callback_failure_frames_and_unknown_archive_fields_not_returned(self):
        import traceback
        for malformed in (False, True):
            _, j, op, _ = prepare(); original = op.archive_callback
            def callback(*args):
                private = 'PRIVATE_CALLBACK_PAYLOAD_91'
                if not malformed: raise RuntimeError(private)
                value = original(*args); value['private'] = private; return value
            op.archive_callback = callback
            try: op.capture_quiescent()
            except m.QuiescentRefused as error:
                rendered = ''.join(traceback.format_exception(error))
                self.assertNotIn('PRIVATE_CALLBACK_PAYLOAD_91', rendered)
                self.assertIsNone(error.__cause__)
                self.assertNotIn('PRIVATE_CALLBACK_PAYLOAD_91', json.dumps(j.record))
            else: self.fail('expected refusal')

    @unittest.skipUnless(os.name == 'posix', 'Actual POSIX durability')
    def test_actual_pending_disk_before_launch_and_flush_fault_no_launch(self):
        for fault in (False, True):
            with tempfile.TemporaryDirectory() as parent:
                directory = pathlib.Path(parent) / '123456abcdef'
                _, j, op, _ = prepare(lambda r: m.cold.Journal(directory, r).open(new=True))
                try:
                    op.capture_quiescent(); op.open_guard_transition(); seen = []
                    def launch(*_):
                        seen.append(json.loads((directory/'journal.json').read_text())['quiescent']['state'])
                        return {'dispatch_receipt_sha256': '9'*64}
                    old = os.fsync
                    def flush(fd):
                        if fault and os.fstat(fd).st_ino == directory.stat().st_ino: raise OSError('PUBLIC_FSYNC_FAULT')
                        return old(fd)
                    with mock.patch.object(m.cold.os, 'fsync', side_effect=flush):
                        if fault:
                            with self.assertRaises(m.QuiescentRefused): op.dispatch_entrypoint(launch)
                        else: op.dispatch_entrypoint(launch)
                    self.assertEqual([] if fault else ['entrypoint-pending'], seen)
                finally: j.close()

    def test_owner_only_transition_once_and_lost_reply_never_replayed(self):
        for outcome in (None, 'before', 'after'):
            c, j, op, _ = prepare(); op.capture_quiescent()
            if outcome: c.fail_change = ('kustomization', outcome)
            if outcome:
                with self.assertRaises(m.QuiescentRefused): op.open_guard_transition()
                self.assertEqual('uncertain', j.record['quiescent']['owner_resume_intent']['state'])
            else: op.open_guard_transition()
            with self.assertRaises(m.QuiescentRefused): op.open_guard_transition()
            self.assertEqual(0, c.resources['deployment']['spec']['replicas'])
            self.assertIs(True, c.resources['helmrelease']['spec']['suspend'])
            self.assertEqual(1, len([x for x in c.calls if x[:2] == ('change','kustomization') and x[3] is False]))

    def test_unauthorized_owner_resume_or_hr_resume_is_sticky(self):
        for key in ('helmrelease', 'kustomization'):
            c, _, op, _ = prepare(); op.capture_quiescent()
            c.resources[key]['spec']['suspend'] = False
            with self.assertRaises(m.QuiescentRefused): c.get(key)
            self.assertEqual('watch', op.trace.failure)

    def test_owner_phase_required_before_entrypoint(self):
        _, _, op, _ = prepare(); op.capture_quiescent()
        with self.assertRaises(m.QuiescentRefused):
            op.dispatch_entrypoint(lambda *_: self.fail('must not dispatch'))


if __name__ == '__main__': unittest.main()
