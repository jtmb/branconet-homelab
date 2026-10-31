#!/usr/bin/env python3
"""Validate complete, comparable measurement sets before deriving metadata-only statistics."""
import argparse
import hashlib
import json
import math
import pathlib
import statistics


def distribution(values):
    return {'median': statistics.median(values), 'min': min(values), 'max': max(values)}


def rank(values, percentile):
    return sorted(values)[math.ceil(len(values) * percentile) - 1]


def summarize(record):
    if not record.get('passed') or not record.get('measurement_complete'):
        raise ValueError('Qualification is incomplete')
    measurements = record['measurements']
    keys = [(item['label'], item['run']) for item in measurements]
    runs = sorted({run for _, run in keys})
    if len(keys) != len(set(keys)) or not 3 <= len(runs) <= 5 or runs != list(range(1, len(runs) + 1)):
        raise ValueError('Require three to five unique complete alternating pairs')
    expected = [('baseline', run) for run in runs] + [('candidate', run) for run in runs]
    if set(keys) != set(expected):
        raise ValueError('Unpaired measurements')
    for item in measurements:
        if not item.get('passed') or item.get('failures') or item['runtime_harness_sha256'] != record['runtime_harness_sha256']:
            raise ValueError('Failed or mixed-harness observations')
        if len(item['profiles']) != 6 or not all(profile.get('completed') for profile in item['profiles']):
            raise ValueError('Incomplete workload profiles')
        if item['enforced_limits'] != measurements[0]['enforced_limits'] or item['definitions'] != measurements[0]['definitions']:
            raise ValueError('Runtime/input definitions changed')
    fixtures = [profile['fixture'] for profile in measurements[0]['profiles']]
    for item in measurements:
        if [profile['fixture'] for profile in item['profiles']] != fixtures:
            raise ValueError('Fixture size or expected workload changed')
    result = {
        'baseline_commit': record['baseline_commit'], 'candidate_commit': record['candidate_commit'],
        'candidate_is_final': record['candidate_is_final'], 'runs_per_source': len(runs),
        'runtime_harness_sha256': record['runtime_harness_sha256'],
        'aggregation': 'Each statistic is computed per run, then median/min/max across runs. HTTP p50/p95 use nearest rank. Workflow elapsed includes body validation and phase observer work; HTTP latency stops at full body receipt.',
        'cgroup_scope': measurements[0]['definitions']['cgroup_scope'], 'profiles': [], 'whole_run': {},
    }
    for label in ['baseline', 'candidate']:
        subset = [item for item in measurements if item['label'] == label]
        result['whole_run'][label] = {
            'cgroup_peak_mib': distribution([item['cgroup_memory_peak_bytes'] / 1048576 for item in subset]),
            'cgroup_cpu_seconds': distribution([item['cgroup_cpu']['usage_usec'] / 1000000 for item in subset]),
            'cgroup_throttled_ms': distribution([item['cgroup_cpu']['throttled_usec'] / 1000 for item in subset]),
            'oom_observed': any('oom_kill 0' not in item['cgroup_memory_events'] for item in subset),
        }
    for index, fixture in enumerate(fixtures):
        profile_result = {'fixture': fixture, 'phases': []}
        profiles = [item['profiles'][index] for item in measurements]
        phase_names = [phase['name'] for phase in profiles[0]['phases']]
        if any([phase['name'] for phase in profile['phases']] != phase_names for profile in profiles):
            raise ValueError('Phase sequence changed')
        for phase_index, name in enumerate(phase_names):
            phases = [profile['phases'][phase_index] for profile in profiles]
            valid = all(
                phase.get('comparison_is_latency_speedup_valid', True)
                and phase.get('equivalent_expected_inventory', True)
                and all(request.get('equivalent_expected_inventory', True) and request['status'] == 200 for request in phase['requests'])
                for phase in phases
            )
            phase_result = {'name': name, 'valid_equivalent_success_latency_comparison': valid}
            for label in ['baseline', 'candidate']:
                selected = [item['profiles'][index]['phases'][phase_index] for item in measurements if item['label'] == label]
                metrics = {
                    'workflow_elapsed_ms': distribution([phase['elapsed_ms'] for phase in selected]),
                    'http_p50_ms': distribution([rank([request['elapsed_ms'] for request in phase['requests']], .5) for phase in selected]),
                    'http_p95_ms': distribution([rank([request['elapsed_ms'] for request in phase['requests']], .95) for phase in selected]),
                    'http_response_body_bytes_total': distribution([sum(request['response_body_bytes'] for request in phase['requests']) for phase in selected]),
                    'http_requests': distribution([len(phase['requests']) for phase in selected]),
                    'statuses': sorted({request['status'] for phase in selected for request in phase['requests']}),
                    'cli_calls': distribution([phase['cli_calls'] for phase in selected]),
                    'native_api_calls': distribution([phase['native_api_calls'] for phase in selected]),
                    'cgroup_cpu_ms': distribution([phase['cgroup_cpu_usage_usec'] / 1000 for phase in selected]),
                    'server_cpu_ms': distribution([phase['server_cpu_ticks'] * 1000 / item['clock_ticks_per_second'] for phase, item in zip(selected, [item for item in measurements if item['label'] == label])]),
                    'server_rss_mib_at_phase_end': distribution([phase['server_rss_kib'] / 1024 for phase in selected]),
                    'server_hwm_mib': distribution([phase['server_peak_rss_kib'] / 1024 for phase in selected]),
                    'observed_container_process_count_max': distribution([phase['observed_process_count_max'] for phase in selected]),
                }
                for optional in ['native_produced_response_body_bytes', 'native_returned_objects_including_retries', 'native_metadata_only_calls']:
                    if optional in selected[0]:
                        metrics[optional] = distribution([phase[optional] for phase in selected])
                phase_result[label] = metrics
            profile_result['phases'].append(phase_result)
        # Historical driver name is preserved; these are end-of-workload samples, not idle steady-state RSS.
        profile_result['end_window_rss_mib'] = {
            label: distribution([item['profiles'][index]['steady_rss_kib']['p50'] / 1024 for item in measurements if item['label'] == label])
            for label in ['baseline', 'candidate']
        }
        result['profiles'].append(profile_result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('record', type=pathlib.Path)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    raw = args.record.read_bytes()
    result = summarize(json.loads(raw))
    result['raw_record_sha256'] = hashlib.sha256(raw).hexdigest()
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
