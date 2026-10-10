#!/usr/bin/env python3
"""Exact-blob, bounded whole-Next-server checkpoint comparison; never builds images."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import tarfile
import time
import uuid

HERE = pathlib.Path(__file__).resolve().parent
EXPORT_COMMIT = 'a82a6cb'
DEFAULT_IMAGE = 'sha256:f628f5688b3fafb391d8d99c9b16aee4d9162aa5aaa121c3ae340f5bc8c2a678'
BASELINE = '51e8cd66379c1f40a95ea02f4da7c8aed848f2a4'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def extract(source, target):
    with tarfile.open(source) as archive:
        for item in archive:
            candidate = target / item.name
            if not candidate.resolve().is_relative_to(target.resolve()) or not item.isfile():
                raise RuntimeError('Unsafe source archive entry')
        archive.extractall(target, filter='data')

def source_manifest(folder):
    return {str(p.relative_to(folder)): sha(p.read_bytes()) for p in sorted(folder.rglob('*')) if p.is_file()}

def unchanged(folder, manifest):
    return all((folder / name).is_file() and sha((folder / name).read_bytes()) == expected for name, expected in manifest.items())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', type=pathlib.Path, required=True)
    parser.add_argument('--exporter', type=pathlib.Path, required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--baseline', default=BASELINE)
    parser.add_argument('--image', default=DEFAULT_IMAGE)
    parser.add_argument('--report', type=pathlib.Path, required=True)
    parser.add_argument('--resume', type=pathlib.Path)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--runs', type=int, default=3)
    args = parser.parse_args()
    if os.name != 'posix' or not all(re.fullmatch('[0-9a-f]{40}', commit) for commit in [args.baseline, args.candidate]):
        raise RuntimeError('Linux and full immutable source SHAs required')
    if args.runs < 3 or args.runs > 5 or not re.fullmatch('sha256:[0-9a-f]{64}', args.image):
        raise RuntimeError('Use three to five runs and an existing immutable image ID')
    os.umask(0o077)
    protected = pathlib.Path.home() / '.cache' / 'bortus-controlled-perf'
    protected.mkdir(mode=0o700, parents=True, exist_ok=True)
    work = args.resume.resolve() if args.resume else protected / ('run-' + uuid.uuid4().hex[:12])
    if not work.is_relative_to(protected.resolve()):
        raise RuntimeError('Benchmark work must remain inside its protected namespace')
    if not args.resume:
        work.mkdir(mode=0o700)
    record_path = work / 'record.json'
    record = json.loads(record_path.read_text()) if args.resume else {
        'scope': 'fixed-synthetic-workload whole Next production server checkpoint comparison',
        'baseline_commit': args.baseline, 'candidate_commit': args.candidate, 'candidate_is_final': False,
        'image': args.image, 'started_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'steps': [], 'sources': {}, 'measurements': [], 'production_commands': False, 'image_builds': False,
        'runtime_limits': {'cpu_quota': 2, 'cpu_affinity': sorted(os.sched_getaffinity(0))[:2], 'memory_bytes': 1073741824, 'swap_bytes': 0, 'pids': 256},
        'build_limits': {'cpu_quota': 4, 'memory_bytes': 4294967296, 'pids': 256, 'next_workers': 4},
        'limitations': [
            'Exact committed checkpoint, not the final integrated candidate or live before/after.',
            'HTTP loopback + fixed-delay fake CLI and verified-TLS synthetic native API; no real cluster/ingress.',
            'CPU quota/affinity does not reserve physical cores or eliminate host contention.',
            'Cgroup totals include driver, mock native API, Next server, Prisma/CLI children and file cache; actual Next PID RSS/HWM is reported separately.',
            'Fresh-process cache cold is not OS cache cold; source builds are excluded from runtime cgroups.',
            'Browser polling/hidden lifecycle, DOM/render/LCP/transfer and actual zoom are not inferred from HTTP server measurements.',
            'Different error outcomes cannot support a valid latency speedup comparison.',
        ],
    }
    if (record['baseline_commit'], record['candidate_commit'], record['image']) != (args.baseline, args.candidate, args.image):
        raise RuntimeError('Resume provenance mismatch')
    exporter = args.exporter.resolve()
    spec = importlib.util.spec_from_file_location('bortus_exact_export', exporter)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    charts = exporter.parents[1]
    committed = module.git(charts, 'show', EXPORT_COMMIT + ':scripts/export_bortus_source.py')
    if committed != exporter.read_bytes():
        raise RuntimeError('Protected exporter differs from reviewed charts commit')
    record['exporter'] = {'charts_commit': module.git(charts, 'rev-parse', EXPORT_COMMIT).decode().strip(), 'script_sha256': sha(committed), 'raw_blob_bytes': True}
    runner_hash = sha(pathlib.Path(__file__).read_bytes())
    harness_hash = sha((HERE / 'whole-server.mjs').read_bytes())
    if args.resume and record.get('runtime_harness_sha256') != harness_hash:
        previous = { 'runtime_harness_sha256': record.get('runtime_harness_sha256'), 'runner_sha256': record.get('runner_sha256'), 'measurements': record['measurements'], 'failed_measurements': [] }
        for item in record['steps']:
            if not item['passed'] and re.fullmatch('(baseline|candidate)-run-[1-5]', item['phase']):
                result = work / (item['phase'] + '.json')
                if result.is_file():
                    previous['failed_measurements'].append(json.loads(result.read_text()))
        record.setdefault('prior_harness_attempts', []).append(previous)
        record['measurements'] = []
        record.pop('measurement_complete', None)
        record.pop('failure', None)
    record['runner_sha256'] = runner_hash
    record['runtime_harness_sha256'] = harness_hash
    cpus = ','.join(map(str, record['runtime_limits']['cpu_affinity']))
    build_cpus = ','.join(map(str, sorted(os.sched_getaffinity(0))[:4]))
    def save():
        record_path.write_text(json.dumps(record, indent=2) + '\n')
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(record, indent=2) + '\n')
    def step(name, command, timeout):
        print(json.dumps({'phase': name, 'state': 'started'}), flush=True)
        start = time.perf_counter()
        log = work / (name + '-' + uuid.uuid4().hex[:6] + '.log')
        try:
            result = subprocess.run(command, capture_output=True, timeout=timeout)
            output, error, code = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as exc:
            output, error, code = exc.stdout or b'', exc.stderr or b'', 124
            if '--name' in command:
                owned = command[command.index('--name') + 1]
                if owned.startswith('bortus-perf-') and owned.endswith(work.name):
                    identity = subprocess.run(['docker', 'inspect', '--format', '{{.Name}}', owned], capture_output=True, timeout=15)
                    if identity.returncode == 0 and identity.stdout.decode().strip() == '/' + owned:
                        subprocess.run(['docker', 'stop', '--time', '5', owned], capture_output=True, timeout=15)
        log.write_bytes(output + b'\n' + error)
        item = {'phase': name, 'exit_code': code, 'elapsed_seconds': round(time.perf_counter() - start, 3), 'passed': code == 0}
        record['steps'].append(item)
        save()
        print(json.dumps(item), flush=True)
        if code:
            raise RuntimeError('Benchmark phase failed; protected output retained, no source/assertion changes')
        return output
    try:
        record['docker_image_inspect'] = json.loads(step('inspect-image', ['docker', 'inspect', args.image], 30))[0]['Id']
        for label, commit in [('baseline', args.baseline), ('candidate', args.candidate)]:
            folder = work / label
            if label not in record['sources']:
                archive = work / (label + '.tar.gz')
                info = module.export(args.repository, commit, archive, False)
                folder.mkdir(mode=0o700)
                extract(archive, folder)
                manifest = source_manifest(folder)
                record['sources'][label] = {**{k: v for k, v in info.items() if k != 'output'}, 'archive_sha256': sha(archive.read_bytes()),
                    'source_manifest': manifest, 'source_file_count': len(manifest), 'build_passed': False}
                save()
            info = record['sources'][label]
            if not unchanged(folder, info['source_manifest']):
                raise RuntimeError('Committed source bytes changed before qualification')
            if not info['build_passed']:
                command = ['docker', 'run', '--rm', '--pull', 'never', '--name', 'bortus-perf-build-' + label + '-' + work.name,
                    '--cpus', '4', '--cpuset-cpus', build_cpus, '--memory', '4g', '--memory-swap', '4g', '--pids-limit', '256',
                    '--user', str(os.getuid()) + ':' + str(os.getgid()), '--mount', 'type=bind,src=' + str(folder) + ',dst=/app', '--workdir', '/app',
                    '-e', 'NEXT_TELEMETRY_DISABLED=1', '-e', 'DATABASE_URL=file:/tmp/bortus-perf-build.db', '-e', 'CIRCLE_NODE_TOTAL=4',
                    '--entrypoint', 'bash', args.image, '-lc', 'npm ci && npm run build']
                step('build-' + label, command, 900)
                if not unchanged(folder, info['source_manifest']):
                    raise RuntimeError('Build changed an immutable exported source byte')
                info['build_passed'] = True
                info['standalone_server_sha256'] = sha((folder / '.next/standalone/server.js').read_bytes())
                save()
        if not args.prepare_only:
            # Alternating order reduces ordering bias; each observation gets a fresh cgroup and server processes.
            for run in range(args.runs):
                for label in (['baseline', 'candidate'] if run % 2 == 0 else ['candidate', 'baseline']):
                    name = label + '-run-' + str(run + 1)
                    if any(m['label'] == label and m['run'] == run + 1 for m in record['measurements']):
                        continue
                    if sha((HERE / 'whole-server.mjs').read_bytes()) != harness_hash or not unchanged(work / label, record['sources'][label]['source_manifest']):
                        raise RuntimeError('Frozen driver or application source changed during measurements')
                    command = ['docker', 'run', '--rm', '--pull', 'never', '--network', 'none', '--name', 'bortus-perf-' + name + '-' + work.name,
                        '--cpus', '2', '--cpuset-cpus', cpus, '--memory', '1g', '--memory-swap', '1g', '--pids-limit', '256',
                        '--user', str(os.getuid()) + ':' + str(os.getgid()), '--mount', 'type=bind,src=' + str(work / label) + ',dst=/app,readonly',
                        '--mount', 'type=bind,src=' + str(HERE) + ',dst=/harness,readonly', '--mount', 'type=bind,src=' + str(work) + ',dst=/results',
                        '--workdir', '/app', '-e', 'BORTUS_PERF_LABEL=' + label, '-e', 'BORTUS_PERF_RUN=' + str(run + 1),
                        '--entrypoint', 'node', args.image, '/harness/whole-server.mjs']
                    step(name, command, 600)
                    result = json.loads((work / (name + '.json')).read_text())
                    result['runtime_harness_sha256'] = harness_hash
                    record['measurements'].append(result)
                    save()
            record['measurement_complete'] = True
        record['passed'] = True
    except Exception as exc:
        record['passed'] = False
        # Deliberately omit arbitrary subprocess/server bodies and environment.
        record['failure'] = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        raise
    finally:
        save()
        print(json.dumps({'protected_work': str(work), 'report': str(args.report), 'passed': record.get('passed', False)}), flush=True)

if __name__ == '__main__':
    main()
