"""One retained BuildKit phase, entirely inside its bounded transient service."""
import fcntl
import hashlib
import json
import os
import pathlib
import signal
import subprocess
import sys
import time

ROOT = pathlib.Path('/home/james/.local/share/branconet-migration/seerr-build-20261023')
PREFIX = 'bortus-seerr-build-20261023'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_new(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def unit_status(unit):
    result = subprocess.run(['systemctl', 'show', unit, '-p', 'ActiveState', '-p', 'SubState', '-p', 'Result', '-p', 'ControlGroup', '-p', 'MemoryCurrent', '-p', 'TasksCurrent', '-p', 'MemoryMax', '-p', 'MemorySwapMax', '-p', 'CPUQuotaPerSecUSec', '-p', 'TasksMax', '-p', 'ExecStart'], capture_output=True, text=True, timeout=30)
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


def verify_inputs(root):
    if root != ROOT or root.resolve() != root:
        raise ValueError('build root identity changed')
    seal = json.loads((root / 'build-inputs.json').read_text())
    if seal['root'] != str(ROOT) or seal['unit_prefix'] != PREFIX:
        raise ValueError('setup scope changed')
    for name, expected in seal['files'].items():
        path = root / name
        if path.is_symlink() or not path.is_file() or digest(path) != expected:
            raise ValueError('sealed input changed')
    return seal


def bounded_cgroup(phase):
    expected = '/system.slice/' + PREFIX + '-' + phase + '.service'
    actual = pathlib.Path('/proc/self/cgroup').read_text().strip().split('::', 1)[1]
    if actual != expected:
        raise ValueError('phase is outside its exact systemd service')
    group = pathlib.Path('/sys/fs/cgroup' + expected)
    limits = {name: (group / name).read_text().strip() for name in ['memory.max', 'memory.swap.max', 'cpu.max', 'pids.max', 'cpuset.cpus.effective']}
    quota, period = map(int, limits['cpu.max'].split())
    if limits['memory.max'] != '3221225472' or limits['memory.swap.max'] != '0' or limits['pids.max'] != '512' or quota * 2 != period * 3:
        raise ValueError('actual service resource limits differ from reviewed limits')
    if os.sched_getaffinity(0) != {0, 1}:
        raise ValueError('actual CPU affinity differs from the reviewed two-CPU set')
    # cgroup v2 forbids internal processes when enabling domain controllers.
    # Keep supervisor/daemon/client in a child, and OCI executions in sibling
    # buildkit children beneath the same resource-limited service ancestor.
    control = group / 'control'; control.mkdir(exist_ok=False)
    (control / 'cgroup.procs').write_text(str(os.getpid()))
    available = set((group / 'cgroup.controllers').read_text().split())
    if not {'cpu', 'memory', 'pids'} <= available:
        raise ValueError('required cgroup controllers are unavailable')
    (group / 'cgroup.subtree_control').write_text('+cpu +memory +pids')
    return expected, limits


def run_phase(phase, root, seal):
    lock = (root / 'phase.lock').open('a')
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    if phase == 'runtime':
        previous = json.loads((root / 'lock-finished.json').read_text())
        if previous.get('exit_code') != 0 or digest(root / 'context/pnpm-lock.yaml') != previous.get('lock_sha256'):
            raise ValueError('runtime requires the exact successful exported lock')
    cgroup, limits = bounded_cgroup(phase)
    started = {'phase': phase, 'started_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'cgroup': cgroup, 'limits': limits, 'max_parallelism': 2, 'files': seal['files']}
    write_new(root / (phase + '-started.json'), started)
    env = {'PATH': str(root / 'bin') + ':/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': str(root / 'empty-home'), 'DOCKER_CONFIG': str(root / 'empty-home/.docker'), 'LANG': 'C.UTF-8'}
    daemon = client = None; result = {'phase': phase, 'exit_code': 1}
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    try:
        version = subprocess.run([str(root / 'bin/buildkitd'), '--version'], env=env, capture_output=True, text=True, check=True).stdout
        if 'v0.34.1' not in version:
            raise ValueError('unexpected BuildKit version')
        address = 'unix://' + str(root / (phase + '.sock'))
        with (root / (phase + '-daemon.log')).open('x') as daemon_log, (root / (phase + '-build.log')).open('x') as build_log:
            daemon = subprocess.Popen([str(root / 'bin/buildkitd'), '--root', str(root / 'state'), '--addr', address, '--oci-worker=true', '--containerd-worker=false', '--oci-worker-snapshotter=native', '--oci-worker-net=host', '--oci-worker-binary=' + str(root / 'bin/buildkit-runc'), '--oci-max-parallelism=2', '--oci-worker-gc=false', '--cdi-disabled'], env=env, stdout=daemon_log, stderr=subprocess.STDOUT)
            for _ in range(60):
                if daemon.poll() is not None:
                    raise RuntimeError('standalone daemon exited before readiness')
                probe = subprocess.run([str(root / 'bin/buildctl'), '--addr', address, 'debug', 'workers'], env=env, capture_output=True, timeout=10)
                if probe.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise TimeoutError('standalone daemon readiness deadline exceeded')
            output = 'type=local,dest=' + str(root / 'lock-output') if phase == 'lock' else 'type=oci,dest=' + str(root / 'seerr-security-20261023.oci.tar')
            # v0.34.1's Dockerfile frontend supports cgroup-parent; OCI spec
            # generation places executions at <parent>/buildkit/<id>.
            command = [str(root / 'bin/buildctl'), '--addr', address, 'build', '--frontend', 'dockerfile.v0', '--local', 'context=' + str(root / 'context'), '--local', 'dockerfile=' + str(root / 'context'), '--opt', 'target=' + phase, '--opt', 'platform=linux/amd64', '--opt', 'cgroup-parent=' + cgroup, '--output', output, '--metadata-file', str(root / (phase + '-build-metadata.json'))]
            client = subprocess.Popen(command, env=env, stdout=build_log, stderr=subprocess.STDOUT)
            result['exit_code'] = client.wait()
            if result['exit_code'] == 0 and phase == 'lock':
                exported = root / 'lock-output/pnpm-lock.yaml'
                with exported.open('rb') as source, os.fdopen(os.open(root / 'context/pnpm-lock.yaml', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as target:
                    target.write(source.read()); target.flush(); os.fsync(target.fileno())
                result['lock_sha256'] = digest(exported)
            elif result['exit_code'] == 0:
                archive = root / 'seerr-security-20261023.oci.tar'
                result.update(oci_sha256=digest(archive), oci_bytes=archive.stat().st_size)
    except BaseException as error:
        result['exit_code'] = result.get('exit_code') or 1
        result['error_type'] = type(error).__name__
    finally:
        for child in [client, daemon]:
            if child and child.poll() is None:
                child.terminate()
                try: child.wait(timeout=20)
                except subprocess.TimeoutExpired: child.kill(); child.wait()
        result['completed_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        result['memory_events'] = pathlib.Path('/sys/fs/cgroup' + cgroup + '/memory.events').read_text()
        write_new(root / (phase + '-finished.json'), result)
    print(json.dumps(result, sort_keys=True))
    return result['exit_code']


def main():
    phase, path, prefix = sys.argv[1:]
    if prefix != PREFIX or phase not in ['lock', 'runtime', 'status', 'stop']:
        raise ValueError('unsupported builder phase')
    root = pathlib.Path(path); seal = verify_inputs(root)
    if phase in ['lock', 'runtime']:
        return run_phase(phase, root, seal)
    units = {p: unit_status(PREFIX + '-' + p + '.service') for p in ['lock', 'runtime']}
    if phase == 'stop':
        for p, state in units.items():
            if state.get('ActiveState') in ['active', 'activating', 'deactivating']:
                if str(root / 'build_phase.py') not in state.get('ExecStart', ''):
                    raise ValueError('unit command ownership changed; refuse stop')
                subprocess.run(['systemctl', 'stop', PREFIX + '-' + p + '.service'], check=True, timeout=60)
        units = {p: unit_status(PREFIX + '-' + p + '.service') for p in ['lock', 'runtime']}
    receipts = {p: json.loads((root / (p + '-finished.json')).read_text()) for p in ['lock', 'runtime'] if (root / (p + '-finished.json')).is_file()}
    started = {p: json.loads((root / (p + '-started.json')).read_text()) for p in ['lock', 'runtime'] if (root / (p + '-started.json')).is_file()}
    print(json.dumps({'root': str(root), 'units': units, 'started': started, 'receipts': receipts}, sort_keys=True))
    return 0


if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'state': 'refused', 'error_type': type(error).__name__}))
        raise SystemExit(1)
