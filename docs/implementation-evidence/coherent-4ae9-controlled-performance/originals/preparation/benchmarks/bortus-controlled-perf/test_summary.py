import copy
import importlib.util
import json
import pathlib
import unittest

folder = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('controlled_perf_summary', folder / 'summarize.py')
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)
record = json.loads((folder.parents[1] / 'docs/implementation-evidence/bortus-controlled-perf.json').read_text())


class EvidenceIntegrityTests(unittest.TestCase):
    def test_refuses_duplicate_unpaired_and_mixed_harness_measurements(self):
        for corruption in ['duplicate', 'unpaired', 'harness']:
            with self.subTest(corruption=corruption):
                changed = copy.deepcopy(record)
                if corruption == 'duplicate':
                    changed['measurements'].append(changed['measurements'][0])
                elif corruption == 'unpaired':
                    changed['measurements'].pop()
                else:
                    changed['measurements'][0]['runtime_harness_sha256'] = 'different'
                with self.assertRaises(ValueError):
                    summary.summarize(changed)

    def test_refuses_fixture_drift_and_incomplete_profiles(self):
        for corruption in ['fixture', 'incomplete']:
            with self.subTest(corruption=corruption):
                changed = copy.deepcopy(record)
                if corruption == 'fixture':
                    changed['measurements'][0]['profiles'][0]['fixture']['secret_objects'] += 1
                else:
                    changed['measurements'][0]['profiles'][0]['completed'] = False
                with self.assertRaises(ValueError):
                    summary.summarize(changed)

    def test_failed_capacity_and_different_outages_never_become_latency_speedups(self):
        result = summary.summarize(record)
        large = next(profile for profile in result['profiles'] if profile['fixture']['name'] == 'metadata-10000')
        for phase in large['phases']:
            if phase['name'].startswith('cold-pods'):
                self.assertFalse(phase['valid_equivalent_success_latency_comparison'])
                self.assertEqual(phase['baseline']['statuses'], [200])
                self.assertEqual(phase['candidate']['statuses'], [503])
        small = next(profile for profile in result['profiles'] if profile['fixture']['name'] == 'audit-small')
        outage = next(phase for phase in small['phases'] if phase['name'] == 'outage-two-sequential')
        self.assertFalse(outage['valid_equivalent_success_latency_comparison'])


if __name__ == '__main__':
    unittest.main()
