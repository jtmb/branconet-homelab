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
import threading
import socket
import re

BASE = pathlib.Path('/home/james/.local/share/branconet-migration/worker1-image-build-20261023')
SERVICES = ('seerr', 'ytptube', 'jackett', 'pihole')
LOCK_SHA = '9665b245267e7c864210bdf85f1098c0891f30946c64b3781f44077fff0b7811'
ROOT = PREFIX = SERVICE = None
ATTEMPT = 'initial'


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
    if socket.gethostname() != 'workernode1':
        raise ValueError('actual worker hostname differs from workernode1')
    if root != ROOT or root.resolve() != root:
        raise ValueError('build root identity changed')
    if root.is_symlink() or root.stat().st_uid != 0 or root.stat().st_mode & 0o077:
        raise ValueError('build root must remain root-owned and protected')
    seal = json.loads((root / 'build-inputs.json').read_text())
    if seal['root'] != str(ROOT) or seal['unit_prefix'] != PREFIX:
        raise ValueError('setup scope changed')
    for name, expected in seal['files'].items():
        path = root / name
        if path.is_symlink() or not path.is_file() or digest(path) != expected:
            raise ValueError('sealed input changed')
    if seal.get('service') != SERVICE or seal.get('buildkit_archive_sha256') != 'a59539daf547fe0958efe2d07e41c0a6944e1112a66d7e519ec1cf5b673ef15b':
        raise ValueError('sealed service or tool provenance changed')
    if seal.get('attempt', 'initial') != ATTEMPT:
        raise ValueError('sealed attempt changed')
    filesystem_pin = json.loads(subprocess.check_output(['/usr/bin/findmnt', '--json', '--target', '/', '--output', 'UUID,SOURCE,FSTYPE'], text=True))['filesystems'][0]
    if not filesystem_pin.get('uuid') or filesystem_pin != seal.get('root_filesystem'):
        raise ValueError('actual root filesystem UUID/source/type differs from setup seal')
    if ' AS runtime' not in (root / 'context/Dockerfile').read_text():
        raise ValueError('recipe requires a named runtime stage')
    if SERVICE == 'seerr' and digest(root / 'context/pnpm-lock.yaml') != LOCK_SHA:
        raise ValueError('exact independently exported frozen Seerr lock required')
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


def filesystem(root, expected=None, starting=False):
    stats = os.statvfs(root)
    identity = {'device': os.stat(root).st_dev, 'fsid': stats.f_fsid}
    if identity != {'device': os.stat('/').st_dev, 'fsid': os.statvfs('/').f_fsid}:
        raise ValueError('builder must remain on the worker root filesystem')
    total = stats.f_blocks * stats.f_frsize
    floor = max((total * 3 + 9) // 10, 32 * 1024 ** 3)
    data = dict(identity, total_bytes=total, available_bytes=stats.f_bavail * stats.f_frsize,
                reserve_bytes=floor, inode_free_fraction=stats.f_favail / stats.f_files)
    if expected and any(data[k] != expected[k] for k in ['device', 'fsid', 'total_bytes']):
        raise ValueError('build filesystem identity or size changed')
    minimum = floor + (20 * 1024 ** 3 if starting else 0)
    if data['available_bytes'] < minimum or data['inode_free_fraction'] < (0.15 if starting else 0.10):
        raise ValueError('filesystem reserve violated: ' + json.dumps(data, sort_keys=True))
    return data


def run_phase(phase, root, seal):
    # One build across all four fresh service identities on this worker.
    host_lock = (BASE / 'host-build.lock').open('a')
    fcntl.flock(host_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    lock = (root / 'phase.lock').open('a')
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    if any((root / name).exists() for name in ['runtime-attempt.json', 'runtime-started.json', 'runtime-finished.json', 'runtime-build.log', 'runtime-daemon.log', 'state', 'runtime.sock', SERVICE + '-security-20261023.oci.tar']):
        raise ValueError('prior attempt retained; replay or overwrite is forbidden')
    write_new(root / 'runtime-attempt.json', {'service': SERVICE, 'phase': phase,
              'requested_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
    initial_fs = filesystem(root, starting=True)
    cgroup, limits = bounded_cgroup(phase)
    started = {'phase': phase, 'service': SERVICE, 'started_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               'cgroup': cgroup, 'limits': limits, 'filesystem': initial_fs, 'max_parallelism': 2,
               'files': seal['files'], 'frozen_lock_sha256': LOCK_SHA if SERVICE == 'seerr' else None}
    write_new(root / 'runtime-started.json', started)
    env = {'PATH': str(root / 'bin') + ':/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': str(root / 'empty-home'),
           'DOCKER_CONFIG': str(root / 'empty-home/.docker'), 'LANG': 'C.UTF-8'}
    daemon = client = None
    result = {'phase': phase, 'service': SERVICE, 'exit_code': 1}
    finished = threading.Event()
    guard_failure = []

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt()

    def monitor():
        while not finished.wait(2):
            try:
                filesystem(root, expected=initial_fs)
                archive = root / (SERVICE + '-security-20261023.oci.tar')
                if archive.exists() and archive.stat().st_size > 4 * 1024 ** 3:
                    raise ValueError('OCI archive exceeds the reviewed 4 GiB bound')
                for log in root.glob('runtime-*.log'):
                    if log.stat().st_size > 64 * 1024 ** 2:
                        raise ValueError('build log exceeds the reviewed 64 MiB bound')
            except BaseException as error:
                guard_failure.append(str(error))
                try:
                    write_new(root / 'runtime-capacity-abort.json', {'reason': str(error), 'unit': PREFIX + '-runtime.service'})
                except OSError:
                    pass  # A full filesystem must never prevent the exact-unit stop.
                # Exact unit scope includes supervisor, daemon/client and OCI sibling cgroups.
                try:
                    stopped = subprocess.run(['systemctl', 'kill', '--kill-whom=all', '--signal=SIGTERM', PREFIX + '-runtime.service'],
                                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False)
                    if stopped.returncode:
                        raise RuntimeError('systemd exact-unit kill failed')
                except (OSError, subprocess.TimeoutExpired, RuntimeError):
                    (pathlib.Path('/sys/fs/cgroup' + cgroup) / 'cgroup.kill').write_text('1')
                return

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    watcher = threading.Thread(target=monitor, daemon=True)
    watcher.start()
    try:
        version = subprocess.run([str(root / 'bin/buildkitd'), '--version'], env=env, capture_output=True, text=True, check=True).stdout
        if 'v0.34.1' not in version:
            raise ValueError('unexpected BuildKit version')
        config = root / 'buildkitd.toml'
        config_text = '[worker.oci]\n  enabled = true\n  gc = true\n  max-parallelism = 2\n  reservedSpace = "1GiB"\n  maxUsedSpace = "20GiB"\n  minFreeSpace = ' + str(initial_fs['reserve_bytes']) + '\n[worker.containerd]\n  enabled = false\n'
        with config.open('x') as stream:
            stream.write(config_text)
        address = 'unix://' + str(root / 'runtime.sock')
        with (root / 'runtime-daemon.log').open('x') as daemon_log, (root / 'runtime-build.log').open('x') as build_log:
            daemon = subprocess.Popen([str(root / 'bin/buildkitd'), '--config', str(config), '--root', str(root / 'state'),
                '--addr', address, '--oci-worker=true', '--containerd-worker=false', '--oci-worker-snapshotter=native',
                '--oci-worker-net=host', '--oci-worker-binary=' + str(root / 'bin/buildkit-runc'),
                '--oci-max-parallelism=2', '--cdi-disabled'], env=env, stdout=daemon_log, stderr=subprocess.STDOUT)
            for _ in range(60):
                if daemon.poll() is not None:
                    raise RuntimeError('standalone daemon exited before readiness')
                probe = subprocess.run([str(root / 'bin/buildctl'), '--addr', address, 'debug', 'workers'], env=env, capture_output=True, timeout=10)
                if probe.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise TimeoutError('standalone daemon readiness deadline exceeded')
            archive = root / (SERVICE + '-security-20261023.oci.tar')
            argv = [str(root / 'bin/buildctl'), '--addr', address, 'build', '--frontend', 'dockerfile.v0',
                '--local', 'context=' + str(root / 'context'), '--local', 'dockerfile=' + str(root / 'context'),
                '--opt', 'target=runtime', '--opt', 'platform=linux/amd64', '--opt', 'cgroup-parent=' + cgroup,
                '--output', 'type=oci,dest=' + str(archive), '--metadata-file', str(root / 'runtime-build-metadata.json')]
            client = subprocess.Popen(argv, env=env, stdout=build_log, stderr=subprocess.STDOUT)
            result['exit_code'] = client.wait()
            if result['exit_code'] == 0:
                # BuildKit explicitly sets export modes, bypassing our umask.
                os.chmod(archive, 0o600)
                os.chmod(root / 'runtime-build-metadata.json', 0o600)
                verify_inputs(root)
                if archive.stat().st_size > 4 * 1024 ** 3:
                    raise ValueError('completed OCI archive exceeds 4 GiB')
                result.update(oci_sha256=digest(archive), oci_bytes=archive.stat().st_size,
                              filesystem=filesystem(root, expected=initial_fs))
    except BaseException as error:
        result['exit_code'] = result.get('exit_code') or 1
        result['error_type'] = type(error).__name__
        result['capacity_abort'] = guard_failure
    finally:
        for child in [client, daemon]:
            if child and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
        finished.set()
        result['completed_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        result['memory_events'] = pathlib.Path('/sys/fs/cgroup' + cgroup + '/memory.events').read_text()
        write_new(root / 'runtime-finished.json', result)
    print(json.dumps(result, sort_keys=True))
    return result['exit_code']


def main():
    global ROOT, PREFIX, SERVICE, ATTEMPT
    phase, path, prefix, service = sys.argv[1:]
    ATTEMPT = 'initial' if pathlib.Path(path).name == service else pathlib.Path(path).name.removeprefix(service + '-')
    if not re.fullmatch(r'initial|r[1-9][0-9]{0,2}', ATTEMPT):
        raise ValueError('invalid attempt identity')
    if service not in SERVICES:
        raise ValueError('unsupported service')
    SERVICE = service
    suffix = '' if ATTEMPT == 'initial' else '-' + ATTEMPT
    ROOT = BASE / (service + suffix)
    PREFIX = 'bortus-worker1-' + service + '-build-20261023' + suffix
    if prefix != PREFIX or phase not in ['runtime', 'status', 'stop']:
        raise ValueError('unsupported builder phase')
    root = pathlib.Path(path); seal = verify_inputs(root)
    if phase == 'runtime':
        return run_phase(phase, root, seal)
    units = {p: unit_status(PREFIX + '-' + p + '.service') for p in ['runtime']}
    if phase == 'stop':
        for p, state in units.items():
            if state.get('ActiveState') in ['active', 'activating', 'deactivating']:
                if str(root / 'build_phase.py') not in state.get('ExecStart', ''):
                    raise ValueError('unit command ownership changed; refuse stop')
                subprocess.run(['systemctl', 'stop', PREFIX + '-' + p + '.service'], check=True, timeout=60)
        units = {p: unit_status(PREFIX + '-' + p + '.service') for p in ['runtime']}
    receipts = {p: json.loads((root / (p + '-finished.json')).read_text()) for p in ['runtime'] if (root / (p + '-finished.json')).is_file()}
    started = {p: json.loads((root / (p + '-started.json')).read_text()) for p in ['runtime'] if (root / (p + '-started.json')).is_file()}
    print(json.dumps({'root': str(root), 'units': units, 'started': started, 'receipts': receipts}, sort_keys=True))
    return 0


if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'state': 'refused', 'error_type': type(error).__name__, 'reason': str(error)}))
        raise SystemExit(1)
