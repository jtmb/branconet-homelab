#!/usr/bin/env python3
"""Finite read-only USN-8555-1 preflight/observation; no account/config commands."""
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

VERSION = '37.2ubuntu~22.04.1'
PACKAGES = ('ubuntu-advantage-tools', 'ubuntu-pro-client', 'ubuntu-pro-client-l10n')
NODES = {
    'masternode': 'f2df6169-4592-4544-b62c-74d89f598648',
    'workernode1': 'e8d4555f-7cea-445f-b84f-6416964045a9',
    'workernode2': 'eda66e65-f388-4b97-b64f-a709cda81894',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(argv):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=90,
                            env={**os.environ, 'LC_ALL': 'C'})
    require(result.returncode == 0, 'read-only command refused: ' + argv[0])
    return result.stdout.strip()


def digest(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def service(name):
    fields = ('ActiveState', 'SubState', 'MainPID', 'ExecMainStartTimestampMonotonic',
              'FragmentPath', 'UnitFileState')
    raw = run(['systemctl', 'show', name, '--property=' + ','.join(fields)])
    return dict(line.split('=', 1) for line in raw.splitlines())


def snapshot():
    release = dict(line.split('=', 1) for line in pathlib.Path('/etc/os-release').read_text().splitlines()
                   if '=' in line)
    require(release.get('ID', '').strip('"') == 'ubuntu'
            and release.get('VERSION_ID', '').strip('"') == '22.04'
            and release.get('VERSION_CODENAME', '').strip('"') == 'jammy', 'Ubuntu Jammy only')
    require(run(['dpkg', '--print-architecture']) == 'amd64', 'amd64 only')
    raw = run(['dpkg-query', '-W', '-f=${Package}\t${Architecture}\t${Version}\t${db:Status-Status}\n'])
    packages = {}
    for line in raw.splitlines():
        name, arch, version, status = line.split('\t')
        if status == 'installed':
            packages[name + ':' + arch] = version
    runtime = run(['/opt/containerd-k8s/bin/containerd', '--version'])
    require(runtime.split()[2] == 'v2.4.2', 'unexpected active runtime version')
    services = {name: service(name) for name in (
        'containerd-k8s.service', 'kubelet.service', 'containerd.service', 'docker.service', 'glusterd.service')}
    for name in ('containerd-k8s.service', 'kubelet.service'):
        require(services[name]['ActiveState'] == 'active' and int(services[name]['MainPID']) > 0,
                'required service not active: ' + name)
    for name in ('containerd.service', 'docker.service', 'glusterd.service'):
        require(services[name]['ActiveState'] == 'inactive' and services[name]['MainPID'] == '0',
                'legacy service not inactive: ' + name)
    kernel = run(['uname', '-r'])
    require(kernel == '5.15.0-198-generic', 'unexpected running kernel')
    return {
        'host': run(['hostname']), 'os': 'ubuntu22.04-jammy-amd64', 'kernel': kernel,
        'bootID': pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'runtimeVersion': runtime, 'runtimeBinarySHA256': digest('/opt/containerd-k8s/bin/containerd'),
        'runtimeConfigSHA256': digest('/etc/containerd-k8s/config.toml'),
        'services': services, 'packages': packages,
        'rebootRequired': pathlib.Path('/run/reboot-required').exists(),
        'rebootPackagesSHA256': digest('/run/reboot-required.pkgs')
        if pathlib.Path('/run/reboot-required.pkgs').exists() else None,
        'policyRcD': {'exists': pathlib.Path('/usr/sbin/policy-rc.d').exists(),
                      'sha256': digest('/usr/sbin/policy-rc.d')
                      if pathlib.Path('/usr/sbin/policy-rc.d').exists() else None},
    }


def preflight():
    import apt
    state = snapshot()
    require(state['host'] in ('workernode1', 'workernode2'), 'worker hosts only')
    cache = apt.Cache(memonly=True)
    origins, expected = {}, []
    for name in PACKAGES:
        require(name in cache, 'package absent from cache: ' + name)
        package = cache[name]
        versions = [v for v in package.versions if v.version == VERSION]
        require(len(versions) == 1, 'exact security version absent: ' + name)
        security = [o for o in versions[0].origins if o.origin == 'Ubuntu'
                    and o.archive == 'jammy-security' and o.trusted]
        require(bool(security), 'trusted Ubuntu security origin absent: ' + name)
        origins[name] = [{'origin': o.origin, 'archive': o.archive, 'trusted': o.trusted} for o in security]
        old = package.installed.version if package.is_installed else None
        require(old in (None, '30~22.04', VERSION), 'unreviewed installed version: ' + name)
        require(old is not None or name == 'ubuntu-pro-client', 'unexpected missing package: ' + name)
        if old != VERSION:
            expected.append(name)
    require(not run(['dpkg', '--audit']), 'dpkg audit is not empty')
    plan = run(['apt-get', '--simulate', '--no-remove', '-t', 'jammy-security', 'install']
               + [name + '=' + VERSION for name in PACKAGES])
    require(not re.search(r'^Remv\s', plan, re.M), 'simulation removes packages')
    installs = []
    for line in plan.splitlines():
        if line.startswith('Inst '):
            match = re.fullmatch(r'Inst ([a-z0-9+.-]+)(?: \[[^\]]+\])? \(([^ ]+) (.+)\)(?: \[.*\])?', line)
            require(match is not None, 'unrecognized simulation install row')
            name, version, origin = match.groups()
            require(name in PACKAGES and version == VERSION
                    and 'Ubuntu:22.04/jammy-security' in origin, 'simulation outside pinned security set')
            installs.append(name)
        elif line.startswith('Conf '):
            require(line.split()[1] in PACKAGES, 'simulation configures unrelated package')
    require(sorted(installs) == sorted(expected), 'simulation install set mismatch')
    return {'state': state, 'origins': origins, 'plannedInst': installs,
            'exactVersion': VERSION, 'simulation': plan}


def cluster():
    data = json.loads(run(['kubectl', 'get', 'nodes', '-o', 'json', '--request-timeout=20s']))
    require(len(data['items']) == 3, 'expected three nodes')
    nodes = {}
    for node in data['items']:
        name = node['metadata']['name']
        require(name in NODES and node['metadata']['uid'] == NODES[name], 'node identity changed')
        conditions = {x['type']: x['status'] for x in node['status']['conditions']}
        require(conditions.get('Ready') == 'True', 'node not Ready: ' + name)
        require(all(conditions.get(x) == 'False' for x in ('MemoryPressure', 'DiskPressure', 'PIDPressure')),
                'node pressure present/unknown: ' + name)
        require(conditions.get('NetworkUnavailable', 'False') == 'False', 'node network unavailable')
        require(not node['spec'].get('unschedulable', False), 'node cordon changed')
        nodes[name] = {'uid': node['metadata']['uid'], 'conditions': conditions,
                       'unschedulable': False, 'nodeInfo': {
                           key: node['status']['nodeInfo'][key] for key in
                           ('bootID', 'kernelVersion', 'kubeletVersion', 'containerRuntimeVersion')}}
    require(set(nodes) == set(NODES), 'node set mismatch')
    return nodes


def verify(data):
    before, after = data['before']['state'], data['after']
    expected = {name: VERSION for name in PACKAGES}
    for key in set(before) - {'packages'}:
        require(before[key] == after[key], 'preserved host field changed: ' + key)
    require(data['nodesBefore'] == data['nodesAfter'], 'node identity/health/runtime changed')
    changed = []
    for key in sorted(set(before['packages']) | set(after['packages'])):
        old, new = before['packages'].get(key), after['packages'].get(key)
        name = key.split(':')[0]
        if old != new:
            # The reviewed transitional tools package changes architecture to all.
            # A vanished old architecture key is allowed only with its exact replacement.
            replacement = [v for k, v in after['packages'].items() if k.split(':')[0] == name]
            require(name in expected and replacement == [VERSION]
                    and new in (None, VERSION), 'unrelated installed package change: ' + key)
            changed.append({'package': key, 'before': old, 'after': new})
    for name in PACKAGES:
        versions = [value for key, value in after['packages'].items() if key.split(':')[0] == name]
        require(versions == [VERSION], 'final exact version missing: ' + name)
    return {'passed': True, 'version': VERSION, 'changedPackages': changed,
            'host': after['host'], 'preservedHostFields': sorted(set(before) - {'packages'}),
            'nodesPreserved': True}


if __name__ == '__main__':
    try:
        mode = sys.argv[1]
        if mode == 'preflight':
            result = preflight()
        elif mode == 'snapshot':
            result = snapshot()
        elif mode == 'cluster':
            result = cluster()
        elif mode == 'verify':
            result = verify(json.load(sys.stdin))
        else:
            raise ValueError('unsupported mode')
        print(json.dumps(result, sort_keys=True))
    except Exception as exc:
        # Do not emit raw subprocess output, configuration contents or environment.
        print(json.dumps({'passed': False, 'error': str(exc) if isinstance(exc, ValueError)
                          else type(exc).__name__}), file=sys.stderr)
        sys.exit(1)
