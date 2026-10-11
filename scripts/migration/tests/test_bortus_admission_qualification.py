"""Pure public fixtures; no API/SSH/operator/Node/Docker calls."""
import copy
import importlib.util
import json
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('admission_metadata', HERE.parent / 'bortus-admission-qualification.py')
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        fixture = json.loads((HERE / 'fixtures/bortus-admission-render-v1.json').read_text())
        self.contract, self.renders = fixture['contract'], fixture['renders']
        self.actual = copy.deepcopy(self.renders); self.pins = []
        for index, obj in enumerate(self.actual, 1):
            meta = obj['metadata']; meta.update(uid=f'00000000-0000-0000-0000-{index:012d}', resourceVersion='opaque-' + str(index), generation=2)
            self.pins.append({key: obj[key] if key == 'kind' else meta[key] for key in ('kind', 'name', 'uid')})
            if obj['kind'] == a.POLICY: obj['status'] = {'observedGeneration': 2, 'typeChecking': {}}
        self.outcomes = []
        for case in a.probe_catalog(self.contract):
            if case['expected_outcome'] == 'allowed':
                result = dict(http_status=201, outcome='allowed', attribution=None, other_failure=None)
            else:
                name = 'bortus-kv-guard-' + a.KINDS[case['kind']]
                pins = {(p['kind'], p['name']): p['uid'] for p in self.pins}
                result = dict(http_status=403, outcome='guard_denied', other_failure=None,
                    attribution=dict(source='api_guard_rejection', reason='Forbidden', policy_name=name,
                        binding_name=name, policy_uid=pins[(a.POLICY, name)], binding_uid=pins[(a.BINDING, name)], validation_index=0))
            self.outcomes.append(dict(case=case, result=result))

    def evaluate(self):
        return a.evaluate(self.renders, self.actual, self.contract, self.outcomes, pinned_guard_identities=self.pins)

    def refused(self, code=None):
        with self.assertRaises(a.AdmissionRefused) as failure: self.evaluate()
        if code: self.assertEqual(code, failure.exception.code)

    def test_matches_independent_chart_renders_and_keeps_acceptance_false(self):
        self.assertEqual(self.renders, a.reviewed_renders(self.contract))
        result = self.evaluate()
        self.assertEqual(6, len(result.guards)); self.assertEqual(40, len(result.case_ids))
        self.assertTrue(result.metadata_validated); self.assertFalse(result.actual_enforcement_accepted)
        self.assertFalse(result.overall_live_restore_acceptance)
        self.assertTrue(all(len(g.spec_sha256) == 64 for g in result.guards))

    def test_joint_corpus_covers_every_required_family_reference_form_and_class(self):
        coverage = a.coverage_map(self.contract)
        self.assertEqual(40, coverage['maximum_cases'])
        categories = coverage['categories']
        for kind in a.KINDS: self.assertIn('workload:' + kind, categories)
        for reference in self.contract['protected_pvc_names'] + self.contract['protected_secret_names']:
            self.assertIn('reference:' + reference, categories)
        for scenario in ('legacy-new-principal', 'legacy-default-principal', 'mutable-tag-label',
                         'registry-alias', 'pullPolicy-Always', 'legacy-init', 'legacy-ephemeral',
                         'deprecated-serviceAccount-alias', 'oldObject-reference-removal'):
            self.assertIn('scenario:' + scenario, categories)
        for secret in ('bortus-runtime', 'bortus-operator-access'):
            for form in ('env', 'envFrom', 'volume', 'projected', 'imagePullSecret', 'azureFile',
                         'csi', 'flexVolume', 'cephfs', 'rbd', 'iscsi', 'scaleIO', 'storageos'):
                self.assertTrue(any(c['scenario'] == 'legacy-default-secret-' + form and
                    c['protected_reference'] == secret for c in a.probe_catalog(self.contract)))
        removals = [c for c in a.probe_catalog(self.contract) if c['scenario'] == 'oldObject-reference-removal']
        self.assertEqual(4, len(removals)); self.assertTrue(all(c['operation'] == 'UPDATE' for c in removals))
        self.assertTrue(all(c['kind'] == 'Deployment' for c in removals))
        ephemeral = [c for c in a.probe_catalog(self.contract) if c['scenario'] == 'legacy-ephemeral']
        self.assertEqual(1, len(ephemeral)); self.assertEqual('bortus-kv', ephemeral[0]['protected_reference'])
        self.assertEqual(self.contract['protected_pvc_names'], coverage['structural_only_ephemeral_claim_names'])
        self.assertEqual(2, sum(c['expected_outcome'] == 'allowed' for c in a.probe_catalog(self.contract)))
        self.assertEqual([], coverage['structural_only_extra_secret_names'])
        self.contract['protected_secret_names'].append('extra-reviewed-access')
        self.assertEqual(['extra-reviewed-access'], a.coverage_map(self.contract)['structural_only_extra_secret_names'])
        self.assertEqual(40, len(a.probe_catalog(self.contract)))

    def test_empty_or_omitted_warning_list_valid_but_missing_typecheck_refuses(self):
        for obj in self.actual:
            if obj['kind'] == a.POLICY: obj['status']['typeChecking']['expressionWarnings'] = []
        self.evaluate()
        self.actual[0]['status'].pop('typeChecking'); self.refused('typechecking')

    def test_warning_and_stale_generation_refuse(self):
        self.actual[0]['status']['typeChecking']['expressionWarnings'] = [{'fieldRef':'spec.validations[0].expression', 'warning':'PUBLIC PRIVATE DETAIL'}]
        self.refused('typechecking')
        self.actual[0]['status']['typeChecking'] = {}; self.actual[0]['status']['observedGeneration'] = 1
        self.refused('typechecking')

    def test_server_default_empty_selectors_match_all_but_nonempty_selectors_refuse(self):
        expected = {g.name + g.kind: g.spec_sha256 for g in self.evaluate().guards}
        for obj in self.actual:
            if obj['kind'] == a.POLICY:
                obj['spec']['matchConstraints'].update(namespaceSelector={}, objectSelector={})
        current = {g.name + g.kind: g.spec_sha256 for g in self.evaluate().guards}
        self.assertEqual(expected, current)
        self.actual[0]['spec']['matchConstraints']['objectSelector'] = {'matchLabels': {'exempt': 'true'}}
        self.refused('spec')

    def test_admission_uid_replacement_deletion_and_namespace_refuse(self):
        for key, value in [('uid', '99999999-0000-0000-0000-000000000001'), ('deletionTimestamp', 'PUBLIC DATE'), ('namespace', 'bortus')]:
            original = copy.deepcopy(self.actual)
            self.actual[0]['metadata'][key] = value; self.refused('identity'); self.actual = original

    def test_resource_versions_are_opaque_and_may_advance(self):
        self.actual[0]['metadata']['resourceVersion'] = 'not-a-number:second'
        self.actual[2]['metadata']['resourceVersion'] = '0'
        result = self.evaluate(); self.assertIn('not-a-number:second', [g.resource_version for g in result.guards])
        self.actual[0]['metadata']['resourceVersion'] = True; self.refused('identity')

    def test_duplicate_missing_extra_wrong_kind_and_policy_refuse(self):
        for mutate in (lambda: self.actual.pop(), lambda: self.actual.append(copy.deepcopy(self.actual[0])),
                       lambda: self.actual.__setitem__(1, copy.deepcopy(self.actual[0])),
                       lambda: self.actual[0].update(kind='Pod'),
                       lambda: self.actual[1]['spec'].update(policyName='wrong-policy')):
            original = copy.deepcopy(self.actual); mutate(); self.refused(); self.actual = original

    def test_spec_drift_cannot_match_even_weakened_expected_render(self):
        mutations = [lambda s: s.update(failurePolicy='Ignore'),
            lambda s: s['matchConstraints'].update(matchPolicy='Exact'),
            lambda s: s['matchConstraints'].update(namespaceSelector={'matchLabels':{'exempt':'true'}}),
            lambda s: s['matchConstraints']['resourceRules'][0].update(resources=['pods']),
            lambda s: s['matchConditions'][0].update(expression='true'),
            lambda s: s['validations'][0].update(expression='true'),
            lambda s: s['variables'][8].update(expression='false')]
        for mutate in mutations:
            original = copy.deepcopy(self.actual); mutate(self.actual[0]['spec']); self.refused('spec')
            self.renders[0]['spec'] = copy.deepcopy(self.actual[0]['spec']); self.refused('render')
            self.actual = original; self.renders = copy.deepcopy(a.reviewed_renders(self.contract))
        self.actual[1]['spec']['validationActions'] = ['Warn']; self.refused('spec')

    def test_required_original_restore_and_secret_references_and_images(self):
        for key, values in [('protected_pvc_names', ['bortus-data']),
            ('protected_secret_names', ['bortus-runtime']), ('approved_image_references', []),
            ('approved_image_references', ['fixture.invalid/bortus:tag@sha256:' + 'a' * 64])]:
            original = copy.deepcopy(self.contract); self.contract[key] = values; self.refused('contract'); self.contract = original
        self.renders[0]['spec']['variables'][0]['expression'] = '["alternate.invalid/bortus@sha256:' + 'a' * 64 + '"]'
        self.refused('render')

    def test_missing_duplicate_extra_or_changed_probe_cannot_pass(self):
        for mutate in (lambda: self.outcomes.pop(), lambda: self.outcomes.append(copy.deepcopy(self.outcomes[0])),
            lambda: self.outcomes.__setitem__(1, copy.deepcopy(self.outcomes[0])),
            lambda: self.outcomes[0]['case'].update(operation='UPDATE')):
            original = copy.deepcopy(self.outcomes); mutate(); self.refused('probes'); self.outcomes = original

    def test_false_boolean_forged_shortcut_not_an_outcome(self):
        self.outcomes[0]['result'] = True; self.refused('attribution')
        self.outcomes[0]['result'] = {'http_status':201, 'outcome':'allowed', 'attribution':None, 'other_failure':None, 'passed':True}
        self.refused('attribution')

    def test_403_requires_guard_attribution_not_rbac_schema_or_immutable_failure(self):
        negative = next(p for p in self.outcomes if p['case']['expected_outcome'] == 'guard_denied')
        original = copy.deepcopy(negative['result'])
        for key, value in [('attribution', None), ('attribution', True), ('http_status', 422),
            ('other_failure', 'RBAC'), ('other_failure', 'schema'), ('other_failure', 'immutable')]:
            negative['result'][key] = value; self.refused('attribution'); negative['result'] = copy.deepcopy(original)

    def test_wrong_guard_names_uids_reason_or_index_refuse(self):
        negative = next(p for p in self.outcomes if p['case']['expected_outcome'] == 'guard_denied')
        original = copy.deepcopy(negative['result'])
        for key, value in [('policy_name','other'), ('binding_name','other'), ('policy_uid',self.pins[1]['uid']),
            ('binding_uid',self.pins[0]['uid']), ('validation_index',True), ('source','generic403'), ('reason','Invalid')]:
            negative['result']['attribution'][key] = value; self.refused('attribution'); negative['result'] = copy.deepcopy(original)

    def test_public_refusal_frames_clear_all_raw_arguments_and_private_warning(self):
        self.actual[0]['status']['typeChecking']['expressionWarnings'] = [{'warning':'PUBLIC PRIVATE WARNING SENTINEL'}]
        try: self.evaluate()
        except a.AdmissionRefused as error:
            self.assertIsNone(error.__context__)
            self.assertNotIn('PUBLIC PRIVATE', str(error))
            tb = error.__traceback__; frames = []
            while tb:
                if tb.tb_frame.f_code.co_name == 'evaluate' and tb.tb_frame.f_code.co_filename == a.__file__:
                    frames.append(dict(tb.tb_frame.f_locals))
                tb = tb.tb_next
            self.assertEqual(1, len(frames))
            for key in ('expected_renders','actual_gets','contract','probe_outcomes','pinned_guard_identities'):
                self.assertIsNone(frames[0][key])
        else: self.fail('must refuse warning')

    def test_closed_outputs_never_return_raw_objects_or_values(self):
        self.actual[0]['metadata']['annotations'] = {'public-private-fixture':'PUBLIC PRIVATE SENTINEL'}
        result = self.evaluate(); self.assertNotIn('PUBLIC PRIVATE', repr(result))
        self.assertTrue(all(set(g._fields) == {'kind','name','uid','resource_version','spec_sha256'} for g in result.guards))

    def test_bounded_deep_oversized_and_nonbuiltin_inputs_refuse(self):
        original = self.actual
        for raw in ('X' * (65536 + 1), 1.5, tuple(original)):
            self.actual = raw; self.refused('bounds')
        deep = []
        for _ in range(30): deep = [deep]
        self.actual = deep; self.refused('bounds'); self.actual = original


if __name__ == '__main__': unittest.main()
