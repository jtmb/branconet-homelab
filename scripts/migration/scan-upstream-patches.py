#!/usr/bin/env python3
"""Bounded exact public patch scans, reusing authenticated local scanner inputs."""
import argparse
import collections
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid

BASE = Path('/home/brajam/.local/share/branconet-migration')
ROOT = BASE / 'upstream-patch-scans-20261025'
INPUT = BASE / 'local-oci-scan-20261024'
INPUT_SHA = 'bb09fc12f7a1c488e7a53c6020bfc84cd5b44a80a608876ba76ed420c06e6ef6'
IMAGES = {
    'phpmyadmin': 'docker.io/library/phpmyadmin:5.2.3-apache@sha256:62a50b1419fe55b9b4c3cd6f5aed03a18f8f5b4a236f24735d76400bea75a5ff',
    'wordpress': 'docker.io/library/wordpress:7.1.3-php8.3-apache@sha256:d42f63cb89ad0eab272c4b393164e63830d0df270009907919f7dcce52b1a20b',
    'redis': 'docker.io/library/redis:8.6.7-alpine@sha256:7033ad495c19b6bca38aea38f9130d1a3d5b647ac94f3ebe644c8c0fb804e039',
    'nginx': 'docker.io/library/nginx:1.30.6@sha256:a7675fcee220f59b4a99f7098c06a0d5d999c2c0ee37c0211efb780536e5cb20',
    'coredns': 'registry.k8s.io/coredns/coredns:v1.14.7@sha256:7efd3c635b03efd68c4e8398fc45f0d993d0e9ab016f72c1cefb0fd6d01aa286',
    'plex': 'ghcr.io/linuxserver/plex:1.43.5.11029-6bf8af3f0-ls329@sha256:8f655bad7dcbc5398a78f70a5af12600b4ed3424f901566ed1eaa6710e9e2334',
}


def need(value, reason):
    if not value:
        raise ValueError(reason)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(path, record):
    tmp = path.with_name(path.name + '-' + uuid.uuid4().hex + '.tmp')
    with tmp.open('x') as out:
        json.dump(record, out, sort_keys=True, indent=2)
        out.flush()
        os.fsync(out.fileno())
    tmp.replace(path)


def measured(unit):
    fields = ['ControlGroup', 'MemoryMax', 'MemorySwapMax', 'TasksMax', 'PrivateNetwork',
              'NoNewPrivileges', 'ProtectSystem', 'ProtectHome', 'RuntimeMaxUSec']
    p = subprocess.run(['systemctl', '--user', 'show', unit, *['--property=' + x for x in fields]],
                       capture_output=True, text=True, timeout=15, check=True)
    values = dict(line.split('=', 1) for line in p.stdout.splitlines() if '=' in line)
    group = values['ControlGroup']
    need(group.startswith('/user.slice/user-1000.slice/user@1000.service/') and group.endswith('/' + unit)
         and Path('/proc/self/cgroup').read_text().strip() == '0::' + group, 'owned_actual_cgroup')
    cg = Path('/sys/fs/cgroup') / group.lstrip('/')
    actual = {n: (cg / n).read_text().strip() for n in ['memory.max', 'memory.swap.max', 'pids.max', 'cpu.max']}
    need(actual['memory.max'] == '1073741824' and actual['memory.swap.max'] == '0'
         and actual['pids.max'] == '128', 'memory_swap_tasks_bounds')
    quota, period = actual['cpu.max'].split()
    need(quota != 'max' and int(quota) <= 2 * int(period) and os.getpriority(os.PRIO_PROCESS, 0) == 10, 'cpu_nice_bounds')
    need(values['PrivateNetwork'] == 'no' and values['NoNewPrivileges'] == 'yes'
         and values['ProtectSystem'] == 'strict' and values['ProtectHome'] == 'tmpfs'
         and values['RuntimeMaxUSec'] in ['15min', '900s'], 'isolation_and_deadline')
    need(not Path('/home/brajam/.ssh').exists() and not os.access('/mnt/c/Users', os.R_OK | os.X_OK), 'credentials_hidden')
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    need(all(int(status[n].strip(), 16) == 0 for n in ['CapEff', 'CapPrm', 'CapAmb']), 'no_capabilities')
    return {'systemd': values, 'cgroup': actual, 'memoryEvents': (cg / 'memory.events').read_text()}


def run(service, attempt, unit):
    path = ROOT / attempt
    receipt = path / 'receipt.json'
    record = {'service': service, 'image': IMAGES[service], 'sourceKind': 'upstream-registry',
              'startedUTC': utc(), 'scanComplete': False, 'securityAcceptance': False,
              'sourceSHA256': sha(Path(__file__)), 'actionsUsed': False, 'deploymentPerformed': False}
    child = None
    save(receipt, record)
    try:
        helper = INPUT / 'helpers' / INPUT_SHA / 'scan-local-oci.py'
        need(sha(helper) == INPUT_SHA, 'input_verifier_identity')
        spec = importlib.util.spec_from_file_location('retained_local_inputs', helper)
        inputs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(inputs)
        with (INPUT / 'scan.lock').open('rb') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            record.update(resourceBefore=measured(unit), inputProof=inputs.inputs(), filesystemBefore=inputs.reserve())
            need(0 <= inputs.age_hours(record['inputProof']['vulnerabilityDB']) <= 24, 'fresh_vulnerability_database')
            cache = path / 'cache'
            for name in ['db', 'java-db']:
                need((cache / name).is_symlink() and (cache / name).resolve() == INPUT / 'cache' / name, 'readonly_database_binding')
            output = path / 'results.json'
            cmd = [str(INPUT / 'bin/trivy'), 'image', '--image-src', 'remote', '--platform', 'linux/amd64',
                   '--config', str(INPUT / 'trivy-empty.yaml'), '--cache-dir', str(cache), '--scanners', 'vuln',
                   '--offline-scan', '--skip-db-update', '--skip-java-db-update', '--ignorefile', str(INPUT / 'no-ignore'),
                   '--timeout', '7m', '--parallel', '2', '--quiet', '--no-progress', '--list-all-pkgs',
                   '--format', 'template', '--template', '@' + str(INPUT / 'results.tpl'), '--output', str(output), IMAGES[service]]
            env = {'PATH': '/usr/bin:/bin', 'HOME': str(path / 'home'), 'DOCKER_CONFIG': str(path / 'docker-config'),
                   'TMPDIR': str(path / 'tmp'), 'GOMAXPROCS': '2', 'GOMEMLIMIT': '512MiB',
                   'TRIVY_SKIP_VERSION_CHECK': 'true', 'LANG': 'C', 'LC_ALL': 'C'}
            record.update(state='scanning', command=cmd)
            save(receipt, record)
            start = time.monotonic()
            with (path / 'scanner.stderr').open('xb') as errors:
                child = subprocess.Popen(cmd, cwd=path, env=env, stdin=subprocess.DEVNULL,
                                         stdout=subprocess.DEVNULL, stderr=errors, start_new_session=True)
                while child.poll() is None:
                    inputs.reserve()
                    size = sum(p.lstat().st_blocks * 512 for p in path.rglob('*') if p.is_file() and not p.is_symlink())
                    need(size <= 2 * 1024 ** 3, 'two_GiB_attempt_allocation')
                    need(time.monotonic() - start < 480, 'scan_observation_deadline')
                    need(not output.exists() or output.stat().st_size <= 64 * 1024 ** 2, 'report_bound')
                    need((path / 'scanner.stderr').stat().st_size <= 16 * 1024 ** 2, 'diagnostic_bound')
                    time.sleep(2)
            record['scannerExitCode'] = child.returncode
            need(child.returncode == 0, 'scanner_failed_not_clean')
            need(0 < output.stat().st_size <= 64 * 1024 ** 2, 'bounded_nonempty_results')
            results = json.loads(output.read_bytes())
            need(isinstance(results, list) and results and all(isinstance(x, dict) for x in results), 'results_only_shape')
            rows = [v for r in results for v in r.get('Vulnerabilities') or []]
            need(sha(Path(__file__)) == record['sourceSHA256'], 'frozen_source_retained')
            record.update(scanComplete=True, state='completed', resultsSHA256=sha(output),
                          severityCounts=dict(collections.Counter(v['Severity'] for v in rows)),
                          fixableCriticalHigh=sum(v['Severity'] in ['CRITICAL', 'HIGH'] and bool(v.get('FixedVersion')) for v in rows),
                          resourceAfter=measured(unit), filesystemAfter=inputs.reserve(), inputProofAfter=inputs.inputs())
    except Exception as error:
        record.update(state='failed_not_clean', errorCategory=str(error) if isinstance(error, ValueError) else type(error).__name__)
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=10)
        record['endedUTC'] = utc()
        save(receipt, record)
    return 0 if record['scanComplete'] else 1


def main():
    global ROOT, INPUT, INPUT_SHA
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--service', choices=IMAGES, required=True)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--run-attempt')
    p.add_argument('--unit')
    p.add_argument('--storage-profile', choices=['legacy', 'offloaded'], default='legacy')
    a = p.parse_args()
    if a.storage_profile == 'offloaded':
        mount = BASE / 'local-image-build-offload-20261025'
        need(mount.is_mount(), 'dedicated_native_scan_mount')
        ROOT = mount / 'upstream-patch-scans'
        INPUT = mount / 'local-oci-scan'
        INPUT_SHA = '684d2c949ccc2eec67b1fb521c4e34f21c15e41d0fe0a8640459ea3e4080d4ca'
    need(a.apply and os.getuid() == 1000, 'explicit_operator_execution')
    os.umask(0o077)
    if a.run_attempt:
        need(a.run_attempt == Path(a.run_attempt).name and len(a.run_attempt) == 32, 'attempt_identity')
        return run(a.service, a.run_attempt, a.unit)
    ROOT.mkdir(mode=0o700, exist_ok=True)
    need(ROOT.resolve() == ROOT and ROOT.stat().st_uid == 1000 and ROOT.stat().st_mode & 0o077 == 0, 'private_native_root')
    attempt = uuid.uuid4().hex
    path = ROOT / attempt
    path.mkdir(mode=0o700)
    for name in ['home', 'docker-config', 'tmp', 'cache']:
        (path / name).mkdir(mode=0o700)
    (path / 'docker-config/config.json').write_text('{"auths":{}}\n')
    for name in ['db', 'java-db']:
        (path / 'cache' / name).symlink_to(INPUT / 'cache' / name, target_is_directory=True)
    source = path / 'scan-upstream-patches.py'
    source.write_bytes(Path(__file__).read_bytes())
    source.chmod(0o500)
    unit = 'branconet-upstream-patch-' + attempt + '.service'
    cmd = ['systemd-run', '--user', '--unit=' + unit, '--service-type=exec',
           '--property=MemoryMax=1G', '--property=MemorySwapMax=0', '--property=CPUQuota=200%',
           '--property=TasksMax=128', '--property=Nice=10', '--property=RuntimeMaxSec=900',
           '--property=TimeoutStopSec=30', '--property=KillMode=control-group', '--property=LimitFSIZE=4294967296',
           '--property=PrivateUsers=yes', '--property=PrivateNetwork=no', '--property=PrivateDevices=yes',
           '--property=NoNewPrivileges=yes', '--property=ProtectSystem=strict', '--property=ProtectHome=tmpfs',
           '--property=BindReadOnlyPaths=' + str(INPUT.parent if a.storage_profile == 'offloaded' else INPUT) + ' /run/user/1000/bus /run/user/1000/systemd/private', '--property=BindPaths=' + str(path),
           '--property=ReadWritePaths=' + str(path),
           '--property=InaccessiblePaths=-/root -/mnt/c/Users -/run/docker.sock -/var/run/docker.sock -/run/containerd -/run/containerd-k8s',
           '--property=NoExecPaths=' + str(path / 'cache') + ' ' + str(path / 'tmp'),
           '--property=StandardOutput=append:' + str(path / 'unit.log'), '--property=StandardError=append:' + str(path / 'unit.log'),
           '--', '/usr/bin/env', '-i', 'PATH=/usr/bin:/bin', 'LANG=C', 'LC_ALL=C',
           'XDG_RUNTIME_DIR=/run/user/1000', 'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus',
           '/usr/bin/python3', '-I', '-B', str(source), '--apply', '--service', a.service,
           '--storage-profile', a.storage_profile,
           '--run-attempt', attempt, '--unit', unit]
    result = subprocess.run(cmd, capture_output=True, timeout=20)
    record = {'unit': unit, 'attempt': attempt, 'service': a.service, 'sourceSHA256': sha(source),
              'storageProfile': a.storage_profile,
              'startExitCode': result.returncode, 'receipt': str(path / 'receipt.json'), 'scanComplete': False}
    save(path / 'launch.json', record)
    print(json.dumps(record))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
