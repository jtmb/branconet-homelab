"""Finite PUBLIC receipt-content controls; no transport, archives or old suites."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('overlay_receipt_audit_public',
    HERE / 'bortus-compiled-overlay-receipt-audit.py')
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)


def raw(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def pin(value):
    return hashlib.sha256(value).hexdigest()


class ReceiptAuditControls(unittest.TestCase):
    def setUp(self):
        for target in ('subprocess.Popen', 'subprocess.run', 'os.system', 'socket.socket'):
            guard = mock.patch(target, side_effect=AssertionError('external execution forbidden'))
            guard.start()
            self.addCleanup(guard.stop)
        self.contract_raw = (HERE / 'contracts/compiled-overlay-7940e9e1-v1.json').read_bytes()
        self.contract = json.loads(self.contract_raw)
        c = self.contract
        self.records = {}
        self.records['export'] = {
            'format': 'bortus-compiled-overlay-adapter/v1', 'purpose': 'export', 'phase': 'completed',
            'owner': '00000000-0000-4000-8000-000000000001', 'source_commit': c['source_commit'],
            'contract_sha256': pin(self.contract_raw), 'save_exit_code': 0,
            'packaging_record': {'format': 'bortus-compiled-overlay-staging/v1',
                'purpose': 'export-contract', 'contract': copy.deepcopy(c),
                'runtime_qualified': False, 'deployed': False},
            'archive_path': '/synthetic-fixture/never-open-this-image.tar',
            'runtime_qualified': False, 'deployed': False}
        ep = pin(raw(self.records['export']))
        replies = []
        for i, host in enumerate(('192.168.0.4', '192.168.0.5', '192.168.0.6'), 1):
            reply = {'format': 'bortus-compiled-overlay-adapter/v1', 'purpose': 'node-preload',
                'phase': 'completed', 'host': host, 'ordinal': i,
                'contract_sha256': pin(self.contract_raw), 'export_execution_sha256': ep,
                'source_commit': c['source_commit'], 'archive_sha256': c['archive_sha256'],
                'archive_bytes': c['archive_bytes'], 'manifest_digest': c['manifest_digest'],
                'raw_config_digest': c['raw_config_digest'], 'import_exit_code': 0,
                'packaging_content_matches': True, 'runtime_qualified': False, 'deployed': False}
            replies.append(reply)
            node = dict(reply, owner=f'00000000-0000-4000-8000-{i+1:012}', nodes=[])
            node.update({s + '_exit_code': 0 for s in (
                'images-before', 'images-preimport', 'images-after', 'manifest', 'config')})
            self.records[f'node-{i}'] = node
        self.records['preload'] = {'format': 'bortus-compiled-overlay-adapter/v1', 'purpose': 'preload',
            'phase': 'completed', 'owner': '00000000-0000-4000-8000-000000000005',
            'source_commit': c['source_commit'], 'contract_sha256': pin(self.contract_raw),
            'export_execution_sha256': ep, 'source_sha256': {
                'io': '2bb52cbd84ce93aa946eab25c68992e9ded90927a3097d7d245b66baf2e95493',
                'contract': '234a58a1f6ecdbf53ffeca1812881b1107bcd4d47ca38b02350cd35638209f45',
                'node': '26766ee11768fd48ea6a5ade1f92d12f5fc5cb3fabbbcf11948591553dcefd2d'},
            'nodes': replies, 'runtime_qualified': False, 'deployed': False,
            **{h + '_exit_code': 0 for h in ('192.168.0.4', '192.168.0.5', '192.168.0.6')}}

    def inputs(self, evidence='public-synthetic'):
        receipts = {k: raw(v) if v is not None else None for k, v in self.records.items()}
        selection = {'format': 'bortus-compiled-overlay-receipt-selection/v1', 'evidence_class': evidence,
            'contract_sha256': pin(self.contract_raw),
            'export_sha256': pin(receipts['export']) if receipts['export'] else None,
            'preload_sha256': pin(receipts['preload']) if receipts['preload'] else None,
            'nodes': [{'host': host, 'ordinal': i,
                       'sha256': pin(receipts[f'node-{i}']) if receipts[f'node-{i}'] else None}
                      for i, host in enumerate(('192.168.0.4', '192.168.0.5', '192.168.0.6'), 1)],
            'runtime_qualified': False, 'deployed': False}
        return selection, receipts

    def run_audit(self, evidence='public-synthetic'):
        s, r = self.inputs(evidence)
        return A.audit(self.contract_raw, pin(self.contract_raw), raw(s), pin(raw(s)), r, evidence)

    def partial(self, purpose, phase, **extra):
        return {'format': 'bortus-compiled-overlay-adapter/v1', 'purpose': purpose, 'phase': phase,
                'owner': {'export': '00000000-0000-4000-8000-000000000001',
                          'preload': '00000000-0000-4000-8000-000000000005',
                          'node': '00000000-0000-4000-8000-000000000002'}[purpose],
                'source_commit': self.contract['source_commit'], 'nodes': [],
                'runtime_qualified': False, 'deployed': False, **extra}

    def test_complete_synthetic_is_only_content(self):
        result = self.run_audit()
        self.assertEqual(result['content_status'], 'completed-content-consistent')
        self.assertTrue(result['synthetic_source_only'])
        for k in ('actual_transport_proven', 'current_node_state_proven', 'archive_bytes_reverified',
                  'provenance_authenticated', 'execution_authorized', 'runtime_qualified', 'deployed'):
            self.assertIs(result[k], False)

    def test_externally_observed_claim_does_not_authenticate(self):
        result = self.run_audit('externally-observed')
        self.assertFalse(result['actual_transport_proven'])
        self.assertFalse(result['provenance_authenticated'])

    def test_synthetic_cannot_satisfy_external_selection(self):
        s, r = self.inputs()
        with self.assertRaises(ValueError):
            A.audit(self.contract_raw, pin(self.contract_raw), raw(s), pin(raw(s)), r, 'externally-observed')

    def test_all_missing_reports_every_slot(self):
        self.records = dict.fromkeys(self.records)
        result = self.run_audit()
        self.assertEqual(set(result['receipt_phases'].values()), {'missing'})
        self.assertEqual(result['content_status'], 'incomplete')

    def test_partial_export_states_not_complete(self):
        for phase in ('validating', 'pending', 'refused', 'uncertain'):
            with self.subTest(phase=phase):
                self.records = dict.fromkeys(self.records)
                self.records['export'] = self.partial('export', phase)
                self.assertEqual(self.run_audit()['receipt_phases']['export'], phase)

    def test_partial_node_states_not_complete(self):
        self.records['preload'] = None
        self.records['node-2'] = self.records['node-3'] = None
        for phase in ('validating', 'pending', 'refused', 'uncertain'):
            with self.subTest(phase=phase):
                self.records['node-1'] = self.partial('node', phase)
                self.assertEqual(self.run_audit()['receipt_phases']['node-1'], phase)

    def test_lost_controller_reply_stays_uncertain(self):
        controller = self.records['preload']
        controller['phase'] = 'uncertain'
        controller['failure'] = 'preload_failed'
        controller['nodes'] = controller['nodes'][:1] + [{'host': '192.168.0.5', 'ordinal': 2, 'phase': 'uncertain'}]
        result = self.run_audit()
        self.assertEqual(result['content_status'], 'incomplete')
        self.assertEqual(result['controller_node_phase_disagreements'], [2, 3])
        self.assertEqual(result['receipt_phases']['node-1'], 'completed')

    def test_export_final_persistence_failure_stays_uncertain(self):
        self.records['export'].update(phase='uncertain', failure='export_failed')
        for key in ('preload', 'node-1', 'node-2', 'node-3'): self.records[key] = None
        result = self.run_audit()
        self.assertEqual(result['content_status'], 'incomplete')
        self.assertEqual(result['receipt_phases']['export'], 'uncertain')

    def test_node_final_persistence_failure_stays_uncertain(self):
        self.records['node-1'].update(phase='uncertain', failure='node_staging_failed')
        self.records['preload'] = self.records['node-2'] = self.records['node-3'] = None
        result = self.run_audit()
        self.assertEqual(result['content_status'], 'incomplete')
        self.assertEqual(result['receipt_phases']['node-1'], 'uncertain')

    def test_uncertain_final_payload_still_checks_identity(self):
        self.records['node-1'].update(phase='uncertain', failure='node_staging_failed', raw_config_digest='sha256:'+'0'*64)
        self.records['preload'] = self.records['node-2'] = self.records['node-3'] = None
        with self.assertRaises(ValueError): self.run_audit()

    def test_original_gates_and_clauses_retained(self):
        r = self.run_audit()
        self.assertEqual(len(r['original_A01_A22_acceptance']), 22)
        self.assertEqual(len(r['unresolved_delivery_gates']), 21)
        self.assertTrue(r['four_findings_unresolved'] and r['prior_32_and_earlier_one_unresolved'])
        self.assertFalse(r['overall_CI_qualified'])
        self.assertTrue(r['all_44_original_clauses_preserved'] and r['full_goal_active'])

    def test_no_archive_or_execution_access(self):
        with mock.patch('builtins.open', side_effect=AssertionError('no reads')):
            self.run_audit()

    def test_missing_and_extra_fields_refused_for_each_receipt(self):
        for key in self.records:
            for mode in ('missing', 'extra'):
                old = copy.deepcopy(self.records[key])
                with self.subTest(key=key, mode=mode):
                    if mode == 'missing': del self.records[key]['runtime_qualified']
                    else: self.records[key]['synthetic'] = True
                    with self.assertRaises(ValueError): self.run_audit()
                self.records[key] = old

    def test_scope_type_confusion_refused(self):
        for key in self.records:
            for field in ('runtime_qualified', 'deployed'):
                for value in (True, 0, None, 'false'):
                    with self.subTest(key=key, field=field, value=value):
                        self.records[key][field] = value
                        with self.assertRaises(ValueError): self.run_audit()
                    self.records[key][field] = False

    def test_manifest_config_archive_and_source_drift(self):
        for field in ('manifest_digest', 'raw_config_digest', 'archive_sha256', 'source_commit'):
            old = self.records['node-1'][field]
            self.records['node-1'][field] = '0' * len(old)
            with self.subTest(field=field), self.assertRaises(ValueError): self.run_audit()
            self.records['node-1'][field] = old

    def test_node_size_ordinal_exit_types(self):
        for field, value in (('archive_bytes', float(self.contract['archive_bytes'])),
                             ('ordinal', True), ('import_exit_code', False), ('manifest_exit_code', 1)):
            old = self.records['node-1'][field]
            self.records['node-1'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.run_audit()
            self.records['node-1'][field] = old

    def test_host_and_order_confusion(self):
        self.records['preload']['nodes'].reverse()
        with self.assertRaises(ValueError): self.run_audit()

    def test_node_receipts_cannot_swap_hosts(self):
        self.records['node-1'], self.records['node-2'] = self.records['node-2'], self.records['node-1']
        with self.assertRaises(ValueError): self.run_audit()

    def test_export_execution_pin_confusion(self):
        self.records['node-1']['export_execution_sha256'] = '0' * 64
        with self.assertRaises(ValueError): self.run_audit()

    def test_packaging_record_not_export_execution(self):
        self.records['export'] = self.records['export']['packaging_record']
        with self.assertRaises(ValueError): self.run_audit()

    def test_planned_envelope_not_node_execution(self):
        self.records['node-1'] = {'format': 'bortus-compiled-overlay-staging/v1', 'purpose': 'preload-contract',
                                  'contract': self.contract, 'host': '192.168.0.4', 'ordinal': 1}
        with self.assertRaises(ValueError): self.run_audit()

    def test_source_qualification_not_execution(self):
        self.records['preload'] = {'sourceQualified': True, 'finalFrozenControlsPassed': 33}
        with self.assertRaises(ValueError): self.run_audit()

    def test_legacy_protocol_refused(self):
        self.records['export']['format'] = 'bortus-release-v2'
        with self.assertRaises(ValueError): self.run_audit()

    def test_packaging_recipe_and_layer_order_drift(self):
        p = self.records['export']['packaging_record']['contract']
        for field, value in (('recipe', 'release-v2'), ('ordered_diff_ids', list(reversed(p['ordered_diff_ids']))),
                             ('labels', {}), ('archive_bytes', 991703040)):
            old = p[field]; p[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.run_audit()
            p[field] = old

    def test_tooling_source_drift(self):
        self.records['preload']['source_sha256']['node'] = '0' * 64
        with self.assertRaises(ValueError): self.run_audit()

    def test_export_save_exit_bool_refused(self):
        self.records['export']['save_exit_code'] = False
        with self.assertRaises(ValueError): self.run_audit()

    def test_completed_requires_completed_export(self):
        self.records['export'] = None
        with self.assertRaises(ValueError): self.run_audit()

    def test_duplicate_owner_refused(self):
        self.records['node-1']['owner'] = self.records['node-2']['owner']
        with self.assertRaises(ValueError): self.run_audit()

    def test_failed_node_then_later_completion_refused(self):
        self.records['preload']['phase'] = 'uncertain'
        self.records['preload']['nodes'][0] = {'host': '192.168.0.4', 'ordinal': 1, 'phase': 'uncertain'}
        with self.assertRaises(ValueError): self.run_audit()

    def test_selection_duplicate_keys_and_nonfinite_refused(self):
        _, r = self.inputs()
        for data in (b'{"format":1,"format":2}', b'{"x":NaN}'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                A.audit(self.contract_raw, pin(self.contract_raw), data, pin(data), r, 'public-synthetic')

    def test_nested_duplicate_receipt_keys_refused(self):
        s, r = self.inputs()
        r['node-1'] = b'{"a":{"b":1,"b":2}}'
        s['nodes'][0]['sha256'] = pin(r['node-1'])
        with self.assertRaises(ValueError):
            A.audit(self.contract_raw, pin(self.contract_raw), raw(s), pin(raw(s)), r, 'public-synthetic')

    def test_independent_pins_required(self):
        s, r = self.inputs()
        for key in ('contract', 'selection', 'receipt'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                rr = dict(r)
                if key == 'receipt': rr['node-1'] += b' '
                A.audit(self.contract_raw, '0' * 64 if key == 'contract' else pin(self.contract_raw),
                        raw(s), '0' * 64 if key == 'selection' else pin(raw(s)), rr, 'public-synthetic')

    def test_altered_contract_even_with_fresh_pin_refused(self):
        c = copy.deepcopy(self.contract); c['recipe'] = 'different'
        s, r = self.inputs()
        with self.assertRaises(ValueError):
            A.audit(raw(c), pin(raw(c)), raw(s), pin(raw(s)), r, 'public-synthetic')

    def test_selection_shape_types_and_order_refused(self):
        for mut in ('extra', 'missing', 'ordinal', 'host', 'pin'):
            s, r = self.inputs()
            if mut == 'extra': s['execution_authorized'] = True
            if mut == 'missing': del s['deployed']
            if mut == 'ordinal': s['nodes'][0]['ordinal'] = True
            if mut == 'host': s['nodes'][1]['host'] = '192.168.0.4'
            if mut == 'pin': s['nodes'][1]['sha256'] = True
            with self.subTest(mut=mut), self.assertRaises(ValueError):
                A.audit(self.contract_raw, pin(self.contract_raw), raw(s), pin(raw(s)), r, 'public-synthetic')

    def test_extra_receipt_unselected_bytes_and_selected_missing(self):
        for mut in ('extra', 'unselected', 'missing'):
            s, r = self.inputs()
            if mut == 'extra': r['other'] = b'{}'
            if mut == 'unselected': s['nodes'][0]['sha256'] = None
            if mut == 'missing': r['node-1'] = None
            with self.subTest(mut=mut), self.assertRaises(ValueError):
                A.audit(self.contract_raw, pin(self.contract_raw), raw(s), pin(raw(s)), r, 'public-synthetic')

    def test_metadata_bound(self):
        with self.assertRaises(ValueError): A.pinned(b' ' * (A.C.MAX_METADATA + 1), pin(b' ' * (A.C.MAX_METADATA + 1)))

    def test_read_only_file_reader_and_refusals(self):
        with tempfile.TemporaryDirectory(dir='/home/brajam/.cache') as tmp:
            p = pathlib.Path(tmp) / 'receipt.json'; p.write_bytes(b'{}'); p.chmod(0o600)
            before = p.stat()
            self.assertEqual(A.read_file(p), b'{}')
            self.assertEqual(before.st_mtime_ns, p.stat().st_mtime_ns)
            link = p.with_name('symlink.json'); link.symlink_to(p)
            with self.assertRaises(OSError): A.read_file(link)
            hard = p.with_name('hardlink.json'); os.link(p, hard)
            with self.assertRaises(ValueError): A.read_file(p)
            hard.unlink(); p.chmod(0o666)
            with self.assertRaises(ValueError): A.read_file(p)
            with self.assertRaises(ValueError): A.read_file(pathlib.Path('relative.json'))

    def test_cli_public_complete_and_missing_exit_codes(self):
        with tempfile.TemporaryDirectory(dir='/home/brajam/.cache') as tmp:
            root = pathlib.Path(tmp)
            def write(name, data):
                p = root / name; p.write_bytes(data); p.chmod(0o600); return str(p)
            s, r = self.inputs()
            args = ['--contract', write('contract.json', self.contract_raw), '--contract-sha256', pin(self.contract_raw),
                    '--selection', write('selection.json', raw(s)), '--selection-sha256', pin(raw(s)),
                    '--evidence-class', 'public-synthetic']
            for k, data in r.items(): args += ['--' + k, write(k + '.json', data)]
            output = io.StringIO()
            with contextlib.redirect_stdout(output): self.assertEqual(A.main(args), 0)
            self.assertFalse(json.loads(output.getvalue())['actual_transport_proven'])
            self.records = dict.fromkeys(self.records); s, _ = self.inputs()
            args = args[:10]
            write('selection.json', raw(s)); args[7] = pin(raw(s))
            with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(A.main(args), 2)

    def test_cli_redacts_invalid_input(self):
        with mock.patch.object(A, 'read_file', side_effect=ValueError('PUBLIC-SENTINEL')):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = A.main(['--contract', '/public', '--contract-sha256', '0' * 64,
                    '--selection', '/public', '--selection-sha256', '0' * 64, '--evidence-class', 'public-synthetic'])
            self.assertEqual(code, 1)
            self.assertNotIn('PUBLIC-SENTINEL', err.getvalue())


if __name__ == '__main__':
    unittest.main()
