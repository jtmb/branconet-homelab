#!/usr/bin/env python3
"""Original-equivalent restricted OCI process specification for producer RUN.

Uses the original pinned BuildKit runc binary and its pinned Moby seccomp data.
No host tool bind, unrestricted capability set, host proc/sys write access,
Docker socket, credential environment or device passthrough enters an image RUN.
Actual OCI isolation/runtime acceptance remains necessary before compilation.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import resource
import subprocess

PROFILE_SHA = '785b2429264afba4d594320337cb17f144f3c7d51585f9805eef72e28f4f9334'
# Docker/containerd default build capabilities; notably no SYS_ADMIN,
# SYS_MODULE, SYS_PTRACE, SYS_RAWIO, BPF, PERFMON or DAC_READ_SEARCH.
CAPABILITIES = ['CAP_CHOWN', 'CAP_DAC_OVERRIDE', 'CAP_FSETID', 'CAP_FOWNER',
    'CAP_MKNOD', 'CAP_NET_RAW', 'CAP_SETGID', 'CAP_SETUID', 'CAP_SETFCAP',
    'CAP_SETPCAP', 'CAP_NET_BIND_SERVICE', 'CAP_SYS_CHROOT', 'CAP_KILL', 'CAP_AUDIT_WRITE']
MASKED = ['/proc/acpi', '/proc/asound', '/proc/interrupts', '/proc/kcore',
    '/proc/keys', '/proc/latency_stats', '/proc/timer_list', '/proc/timer_stats',
    '/proc/sched_debug', '/proc/scsi', '/sys/firmware', '/sys/devices/virtual/powercap']
READ_ONLY = ['/proc/bus', '/proc/fs', '/proc/irq', '/proc/sys', '/proc/sysrq-trigger']


def need(value, message):
    if not value:
        raise RuntimeError(message)


def seccomp():
    path = Path(__file__).with_name('veyra-linux-seccomp-v0.2.4.json')
    raw = path.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == PROFILE_SHA, 'Original BuildKit-pinned Moby profile changed')
    original = json.loads(raw)
    need(platform.machine() == 'x86_64', 'Original Linux/amd64 executor required')
    kernel = tuple(map(int, re.match(r'([0-9]+)\.([0-9]+)', platform.release()).groups()))
    selected = [row for row in original['archMap'] if row['architecture'] == 'SCMP_ARCH_X86_64']
    need(len(selected) == 1, 'Original seccomp architecture is ambiguous')
    result = {key: copy.deepcopy(value) for key, value in original.items() if key not in ['archMap', 'syscalls']}
    result['architectures'] = [selected[0]['architecture'], *selected[0]['subArchitectures']]
    result['syscalls'] = []
    caps = set(CAPABILITIES)
    for source in original['syscalls']:
        inc, exc = source.get('includes') or {}, source.get('excludes') or {}
        need(set(inc) <= {'arches', 'caps', 'minKernel'} and set(exc) <= {'arches', 'caps', 'minKernel'},
             'Unknown original seccomp condition must not be ignored')
        if ('amd64' in exc.get('arches', []) or caps.intersection(exc.get('caps', [])) or
                'minKernel' in exc and kernel >= tuple(map(int, exc['minKernel'].split('.')))):
            continue
        if (inc.get('arches') and 'amd64' not in inc['arches'] or
                inc.get('caps') and not set(inc['caps']) <= caps or
                'minKernel' in inc and kernel < tuple(map(int, inc['minKernel'].split('.')))):
            continue
        result['syscalls'].append({key: copy.deepcopy(value) for key, value in source.items()
                                   if key not in ['includes', 'excludes']})
    need(result['defaultAction'] == 'SCMP_ACT_ERRNO' and result['syscalls'],
         'Original syscall allowlist was disabled')
    return result


def specification(producer, argv, environment, identity):
    producer.guard()
    need(re.fullmatch(r'veyra-(probe-)?(budget|swarm|rust|node|image)-[0-9]+(?:-[a-z][a-z0-9-]{0,30})?', identity),
         'Exact owned OCI identity required')
    need(all(isinstance(key, str) and isinstance(value, str) and '\0' not in key + value and '=' not in key
             for key, value in environment.items()), 'Explicit cleared build environment required')
    path = Path(__file__).with_name('veyra-linux-cgroup-limits.py')
    spec = importlib.util.spec_from_file_location('veyra_effective_cgroups', path)
    limits = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(limits)
    effective = limits.current()
    current_group = effective['unitPath']
    need(current_group and current_group != '/' and '..' not in Path(current_group).parts,
         'Original bounded parent cgroup required, never host-global OCI placement')
    cgroup = Path('/sys/fs/cgroup') / current_group.lstrip('/')
    need(not (cgroup / 'cgroup.procs').read_text().strip(),
         'Delegate a controller subgroup; OCI siblings must stay inside the original bounded unit')
    capabilities = {key: list(CAPABILITIES) for key in ['bounding', 'effective', 'permitted']}
    capabilities.update(inheritable=[], ambient=[])
    devices = [('/dev/null', 1, 3), ('/dev/zero', 1, 5), ('/dev/full', 1, 7),
               ('/dev/random', 1, 8), ('/dev/urandom', 1, 9), ('/dev/tty', 5, 0)]
    limit = min(resource.getrlimit(resource.RLIMIT_NOFILE)[0], 1048576)
    return {'ociVersion': '1.2.0', 'hostname': identity,
        'root': {'path': str(producer.root), 'readonly': False},
        'process': {'terminal': False, 'user': {'uid': 0, 'gid': 0, 'umask': 18},
            'args': argv, 'cwd': producer.cwd,
            'env': [key + '=' + value for key, value in environment.items()],
            'capabilities': capabilities, 'noNewPrivileges': True,
            'rlimits': [{'type': 'RLIMIT_NOFILE', 'hard': limit, 'soft': limit}]},
        'mounts': [
            {'destination': '/proc', 'type': 'proc', 'source': 'proc', 'options': ['nosuid', 'noexec', 'nodev']},
            {'destination': '/dev', 'type': 'tmpfs', 'source': 'tmpfs', 'options': ['nosuid', 'strictatime', 'mode=755', 'size=65536k']},
            {'destination': '/dev/pts', 'type': 'devpts', 'source': 'devpts', 'options': ['nosuid', 'noexec', 'newinstance', 'ptmxmode=0666', 'mode=0620', 'gid=5']},
            {'destination': '/dev/shm', 'type': 'tmpfs', 'source': 'shm', 'options': ['nosuid', 'noexec', 'nodev', 'mode=1777', 'size=65536k']},
            {'destination': '/sys', 'type': 'sysfs', 'source': 'sysfs', 'options': ['nosuid', 'noexec', 'nodev', 'ro']},
            {'destination': '/sys/fs/cgroup', 'type': 'cgroup', 'source': 'cgroup', 'options': ['nosuid', 'noexec', 'nodev', 'ro']},
            *[{'destination': '/etc/' + name, 'type': 'bind', 'source': '/etc/' + name,
               'options': ['rbind', 'ro', 'nosuid', 'nodev', 'noexec']} for name in ['resolv.conf', 'hosts']]],
        'linux': {'namespaces': [{'type': key} for key in ['pid', 'mount', 'ipc', 'uts', 'cgroup']],
            # Network intentionally matches the original explicit host-network
            # BuildKit worker; no host namespace is used for PID/mount/proc/sys.
            'cgroupsPath': current_group.rstrip('/') + '/' + identity,
            'rootfsPropagation': 'rprivate', 'maskedPaths': MASKED,
            'readonlyPaths': READ_ONLY, 'seccomp': seccomp(),
            'devices': [{'path': name, 'type': 'c', 'major': major, 'minor': minor,
                         'fileMode': 438, 'uid': 0, 'gid': 0} for name, major, minor in devices],
            'resources': {'memory': {'limit': 4294967296, 'swap': 4294967296},
                'cpu': {'quota': 150000, 'period': 100000}, 'pids': {'limit': 512},
                'devices': [{'allow': False, 'access': 'rwm'},
                    *[{'allow': True, 'type': 'c', 'major': major, 'minor': minor, 'access': 'rwm'}
                      for _, major, minor in devices],
                    {'allow': True, 'type': 'c', 'major': 136, 'access': 'rwm'},
                    {'allow': True, 'type': 'c', 'major': 5, 'minor': 2, 'access': 'rwm'}]}}}


def run(producer, argv, environment, log):
    operator = producer.operator
    runtime = operator.TOOLS / 'bin/buildkit-runc'
    need(runtime.resolve() == runtime and operator.sha(runtime) == operator.BINARIES['buildkit-runc'][1],
         'Original exact pinned OCI runtime required; never substitute the host runtime')
    identity = ('veyra-probe-' if producer.closed_probe else 'veyra-') + producer.stage + '-' + str(producer.sequence)
    if not producer.closed_probe and producer.attempt != 'initial':
        identity += '-' + producer.attempt
    bundle = operator.WORK / ('oci-' + identity)
    need(not bundle.exists(), 'Prior OCI instruction/failure must be reconciled, never overwritten')
    bundle.mkdir(mode=0o700)
    config = specification(producer, argv, environment, identity)
    config_path = bundle / 'config.json'
    with config_path.open('x') as output:
        json.dump(config, output, indent=2)
    state = operator.WORK / 'oci-state'
    state.mkdir(mode=0o700, exist_ok=True)
    child = subprocess.Popen([str(runtime), '--root', str(state), 'run', '--bundle', str(bundle), identity],
        stdin=subprocess.DEVNULL, stdout=log, stderr=log, cwd=operator.WORK, start_new_session=True)
    birth = operator.birth(child.pid)
    producer.proof.setdefault('ociRuns', []).append({'id': identity, 'pid': child.pid,
        'startTicks': birth, 'configSha256': operator.sha(config_path),
        'runtimeSha256': operator.sha(runtime), 'seccompSourceSha256': PROFILE_SHA,
        'originalExitCode': None})
    row = producer.proof['ociRuns'][-1]
    producer.record()
    try:
        while child.poll() is None:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                producer.guard()
        row['originalExitCode'] = child.returncode
        producer.record()
        need(child.returncode == 0, 'Actual restricted OCI instruction failed; preserve original log/state')
    finally:
        if child.poll() is None:
            need(operator.birth(child.pid) == birth, 'Original OCI launcher identity changed; do not signal')
            # Only this verified instruction ID may be stopped. Do not signal
            # a shared runtime daemon or another container/process.
            stopped = subprocess.run([str(runtime), '--root', str(state), 'kill', identity, 'TERM'],
                                     stdout=log, stderr=log, timeout=10)
            row['ownedStopExitCode'] = stopped.returncode
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                producer.record()
                raise RuntimeError('Owned OCI instruction did not stop; retain state/filesystem and do not advance')
        row['launcherTerminal'] = child.poll() is not None
        producer.record()
        # State/bundle retirement stays under the original reference, source,
        # diagnostic and last-consumer checks in the complete executor.
