#!/usr/bin/env python3
"""Finite worker2-only USN-8956-1 controller. No apply without reviewed qualification."""
import argparse
import base64
import datetime
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import runpy
import shlex
import stat
import subprocess
import sys
import tarfile
import uuid

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H = F / 'platform-upstream-review-20261027/worker2-brotli-host-20261028'
VOLUME = '3c792469-ea0e-4a2c-98e8-1185b141607b'
HOST = 'workernode2'
IP = '192.168.0.5'
ROOT_UUID = '960bc2c7-2a7e-4bc2-b2c5-dbb6d71207f4'
OLD = '1.0.9-2build6'
VERSION = '1.0.9-2ubuntu0.1'
PACKAGE = 'libbrotli1'
DEB = Path('/var/cache/apt/archives') / 'libbrotli1_1.0.9-2ubuntu0.1_amd64.deb'
REFERENCE = F / 'node-cleanup-20261027/master-generated-cleanup/reference-full-properties.py'
REFERENCE_SHA = '3dcde82583df9e8217a4e39ef88d810ff955690d1dbf0a1581000f9984a9df87'
SIGNED_DEB_SHA = '908295e77a65219a62114c3c79690a3c99712274d1317c3ba47ffa2f8ea52ca5'
CONTROL_TAR_SHA = '6df6adccf4ad7139eca21fcb2136c0c102a600f8d03d014005bc1728452705de'
TRIGGER_SHA = '5d84abb82775d01b9d3656b045595eb316da0f59d5b007e4612bca4ef0d057b3'
REFUSED_SOURCE_SHA = '9c189cce682424f5b49162da85e299ab62b4c852944c16996c10c9ac388376ee'
REFUSED_RECEIPT = 'apply-0313dea68b364a2b89bb97b75d2af501.json'
REFUSED_RECEIPT_SHA = '01f34d1784ef9839c1a09140abd1d9ad604742fbda22d0c1f84b6375e956bb95'
ORIGINAL_INTENT_SHA = 'e2d3f07495d7574ed93e4f0908d78c3fb24f3bf3228da2b4640db73b69f65fe0'
TRIGGER_REVIEW_SHA = 'ebf56a9c673b70138507cb7f0efb0ba9555d2079331d8a8d41e2d137afabd610'
PEAK = 64 * 1024**2
MARGIN = 512 * 1024**2
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-o', 'IdentitiesOnly=yes',
       '-o', 'ForwardAgent=no', '-o', 'ConnectTimeout=15', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002']
APT = ['apt-get', '--no-remove', '--only-upgrade', '--no-install-recommends',
       '--no-install-suggests', '-t', 'jammy-security',
       '-o', 'APT::Get::AllowUnauthenticated=false',
       '-o', 'Acquire::AllowInsecureRepositories=false',
       '-o', 'Acquire::AllowDowngradeToInsecureRepositories=false',
       '-o', 'APT::Get::allow-Downgrades=false',
       '-o', 'APT::Get::AutomaticRemove=false', '-o', 'DPkg::Lock::Timeout=0',
       '-o', 'APT::Keep-Downloaded-Packages=true',
       '-o', 'Binary::apt-get::APT::Keep-Downloaded-Packages=true',
       '-o', 'Acquire::Retries=0', '-o', 'Acquire::http::Timeout=30',
       '-o', 'Acquire::https::Timeout=30', '-o', 'Dpkg::Options::=--force-confold',
       '-o', 'Dpkg::Options::=--force-confdef']


def need(value, reason):
    if not value:
        raise ValueError(reason)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def run(args, timeout=90):
    p = subprocess.run(args, capture_output=True, timeout=timeout,
                       env={**os.environ, 'LC_ALL': 'C', 'PYTHONDONTWRITEBYTECODE': '1'})
    need(p.returncode == 0, 'read_failed:' + args[0])
    need(len(p.stdout) < 8 * 1024**2, 'bounded_read')
    return p.stdout.decode().strip()


def snapshot():
    need(run(['hostname']) == HOST, 'worker2_hostname')
    need(run(['findmnt', '-n', '-o', 'UUID', '/']) == ROOT_UUID, 'worker2_root_uuid')
    addresses = json.loads(run(['ip', '-j', '-4', 'address', 'show']))
    need(IP in {a['local'] for link in addresses for a in link['addr_info']}, 'worker2_address')
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    need(release.get('VERSION_CODENAME') == 'jammy' and release.get('ID') == 'ubuntu', 'ubuntu_jammy')
    need(run(['dpkg', '--print-architecture']) == 'amd64', 'amd64')
    packages = {}
    for line in run(['dpkg-query', '-W', '-f=${Package}\t${Architecture}\t${Version}\t${db:Status-Status}\n']).splitlines():
        name, arch, version, state = line.split('\t')
        if state == 'installed':
            packages[name + ':' + arch] = version
    services = {}
    for name in ['kubelet', 'containerd-k8s', 'ssh']:
        fields = 'MainPID,ActiveState,SubState,ExecMainStartTimestampMonotonic,NRestarts,FragmentPath'
        row = dict(line.split('=', 1) for line in run(['systemctl', 'show', name, '--property=' + fields]).splitlines())
        need(row['ActiveState'] == 'active' and int(row['MainPID']) > 0, 'required_service:' + name)
        services[name] = row
    files = ['/opt/containerd-k8s/bin/containerd', '/etc/containerd-k8s/config.toml',
             '/var/lib/kubelet/config.yaml', '/etc/ssh/sshd_config']
    kernel = run(['uname', '-r'])
    need(kernel == '5.15.0-198-generic', 'running_kernel_preserved')
    hashes = {}
    for path in files:
        try:
            hashes[path] = sha(path)
        except OSError:
            raise ValueError('protected_hash_unreadable:' + path) from None
    return {'host': HOST, 'rootUUID': ROOT_UUID, 'kernel': kernel,
            'bootID': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'services': services, 'packages': packages,
            'protectedHashes': hashes,
            'rebootRequired': Path('/run/reboot-required').exists(),
            'rebootPackagesSHA256': sha('/run/reboot-required.pkgs') if Path('/run/reboot-required.pkgs').exists() else None,
            'policyRcD': sha('/usr/sbin/policy-rc.d') if Path('/usr/sbin/policy-rc.d').exists() else None}


def cache_entry():
    if not DEB.exists():
        need(not DEB.is_symlink(), 'dangling_archive_link')
        return {'exists': False}
    s = DEB.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and not DEB.is_symlink(), 'archive_regular_single_link')
    return {'exists': True, 'bytes': s.st_size, 'allocatedBytes': s.st_blocks * 512,
            'sha256': sha(DEB), 'inode': s.st_ino, 'device': s.st_dev}


def candidate_policy():
    import apt
    need(run(['hostname']) == HOST and run(['findmnt', '-n', '-o', 'UUID', '/']) == ROOT_UUID, 'worker2_candidate_target')
    need(not run(['dpkg', '--audit']), 'dpkg_clean')
    cache = apt.Cache(memonly=True)
    package = cache[PACKAGE]
    candidate = package.candidate
    need(package.is_installed and package.installed.version in [OLD, VERSION], 'reviewed_installed_version')
    need(candidate.version == VERSION and candidate.architecture == 'amd64', 'exact_candidate')
    origins = [{'origin': o.origin, 'archive': o.archive, 'trusted': o.trusted}
               for o in candidate.origins if o.origin == 'Ubuntu' and o.archive == 'jammy-security' and o.trusted]
    need(bool(origins), 'trusted_signed_jammy_security_origin')
    digest = candidate.record['SHA256']
    need(re.fullmatch('[a-f0-9]{64}', digest) and 0 < candidate.size < 4 * 1024**2
         and candidate.installed_size < 16 * 1024**2, 'signed_package_bounds')
    plan = run(APT + ['--simulate', 'install', PACKAGE + '=' + VERSION])
    installs, configs = [], []
    for line in plan.splitlines():
        need(not line.startswith(('Remv ', 'Purg ')), 'simulation_removes_package')
        if line.startswith('Inst '):
            need(re.fullmatch(r'Inst libbrotli1 \[1\.0\.9-2build6\] \(1\.0\.9-2ubuntu0\.1 (?:Ubuntu:22\.04/jammy-updates, )?Ubuntu:22\.04/jammy-security \[amd64\]\)', line), 'exact_single_install')
            installs.append(PACKAGE)
        if line.startswith('Conf '):
            need(re.fullmatch(r'Conf libbrotli1 \(1\.0\.9-2ubuntu0\.1 (?:Ubuntu:22\.04/jammy-updates, )?Ubuntu:22\.04/jammy-security \[amd64\]\)', line), 'exact_single_configure')
            configs.append(PACKAGE)
    expected = [] if package.installed.version == VERSION else [PACKAGE]
    need(installs == expected and configs == expected, 'no_dependency_or_unrelated_configuration')
    archive = cache_entry()
    if archive['exists']:
        need(archive['sha256'] == digest and archive['bytes'] == candidate.size, 'existing_cache_matches_signed_package')
    partial = DEB.parent / 'partial' / DEB.name
    try:
        partial_state = 'present' if partial.exists() or partial.is_symlink() else 'absent'
    except PermissionError:
        partial_state = 'requires_privileged_read'
    space = os.statvfs('/')
    need(space.f_bfree * space.f_frsize >= space.f_blocks * space.f_frsize // 4 + 1 + MARGIN + PEAK,
         'original_root_longhorn_floor_plus_margin_and_peak')
    return {'installedVersion': package.installed.version, 'origins': origins, 'candidateSHA256': digest,
            'candidateBytes': candidate.size, 'candidateInstalledBytes': candidate.installed_size,
            'plannedInst': installs, 'plannedConf': configs, 'simulation': plan,
            'cacheBefore': archive, 'partialArchiveBefore': partial_state, 'rootAvailableBytes': space.f_bavail * space.f_frsize,
            'rootFreeBytes': space.f_bfree * space.f_frsize, 'rootCapacityBytes': space.f_blocks * space.f_frsize}


def preflight():
    result = candidate_policy()
    need(result['partialArchiveBefore'] == 'absent', 'preexisting_or_unreadable_partial_archive_preserved')
    result['state'] = snapshot()
    return result


def safe_cleanup(before, signed, guard_source):
    result = {'path': str(DEB), 'removedBytes': 0, 'removedAllocatedBytes': 0,
              'platformChecks': 'Linux process argv/cwd/root/exe/FDs/maps, all observed mount namespaces, all active unit properties; SFTP included in process/FD checks. Native Linux APT archive, not a Windows-mapped path.'}
    if before['exists']:
        return {**result, 'retained': 'preexisting native package cache; never owned',
                'preexistingUnchanged': cache_entry() == before}
    if not DEB.exists():
        return {**result, 'state': 'no downloaded archive remains'}
    locks = []
    try:
        need(os.geteuid() == 0 and DEB.resolve() == DEB and DEB.parent == Path('/var/cache/apt/archives'), 'exact_native_archive_path')
        need(all(p.resolve() == p and not p.is_symlink() for p in DEB.parents), 'archive_ancestry_no_symlink')
        for name in ['/var/lib/dpkg/lock-frontend', '/var/lib/dpkg/lock', '/var/cache/apt/archives/lock']:
            fd = os.open(name, os.O_RDWR | os.O_NOFOLLOW)
            locks.append(fd)
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        now = cache_entry()
        need(now['sha256'] == signed['candidateSHA256'] and now['bytes'] == signed['candidateBytes'], 'signed_archive_identity_before_cleanup')
        need(DEB.stat().st_uid == 0, 'native_archive_owner')
        need(not os.listxattr(DEB), 'archive_has_no_extended_attributes')
        need(hashlib.sha256(guard_source.encode()).hexdigest() == REFERENCE_SHA, 'pinned_cleanup_reference')
        namespace = {'__name__': 'worker2_cleanup_reference'}
        exec(compile(guard_source, '<pinned-cleanup-reference>', 'exec'), namespace)
        namespace['BASE'] = DEB.parent
        namespace['ATTEMPTS'] = (DEB.name,)
        original_command = namespace['command']
        def all_unit_properties(*args):
            # Retain the pinned completeness check but inspect every property.
            args = tuple(a for a in args if a != '--property=Id,ExecStart,WorkingDirectory')
            return original_command(*args)
        namespace['command'] = all_unit_properties
        result['referenceChecks'] = namespace['idle']()
        for process in Path('/proc').glob('[0-9]*'):
            for fd in (process / 'fd').glob('*'):
                try:
                    s = fd.stat()
                except (FileNotFoundError, ProcessLookupError):
                    continue
                need((s.st_dev, s.st_ino) != (now['device'], now['inode']), 'active_archive_reader')
        need(str(DEB) not in [line.split()[4] for line in Path('/proc/self/mountinfo').read_text().splitlines()], 'archive_mount_reference')
        need(cache_entry() == now, 'archive_unchanged_at_delete')
        DEB.unlink()
        return {**result, 'removedBytes': now['bytes'], 'removedAllocatedBytes': now['allocatedBytes'],
                'state': 'new signed reproducible archive removed',
                'regenerate': 'apt-get --download-only --only-upgrade install libbrotli1=1.0.9-2ubuntu0.1'}
    except Exception as exc:
        return {**result, 'retained': str(exc) if isinstance(exc, ValueError) else type(exc).__name__, 'retryDeletion': False}
    finally:
        for fd in locks:
            os.close(fd)


def inspect_deb(expected):
    entry = cache_entry()
    need(entry['exists'] and entry['sha256'] == expected['candidateSHA256']
         and entry['bytes'] == expected['candidateBytes'], 'download_matches_signed_apt_metadata')
    raw = subprocess.check_output(['dpkg-deb', '--ctrl-tarfile', str(DEB)])
    need(len(raw) < 1024**2, 'bounded_control_archive')
    need(entry['sha256'] == SIGNED_DEB_SHA and hashlib.sha256(raw).hexdigest() == CONTROL_TAR_SHA,
         'exact_reviewed_signed_control_archive')
    scripts = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for item in archive:
            name = item.name.removeprefix('./')
            if name in ['preinst', 'postinst', 'prerm', 'postrm', 'config']:
                need(item.isfile() and item.size < 65536, 'bounded_maintainer_script')
                data = archive.extractfile(item).read()
                # This simple shared library is expected to use only the ldconfig
                # trigger. Do not introduce a policy-rc.d file or accept new scripts.
                need(not data.strip(), 'unexpected_package_maintainer_script:' + name)
                scripts[name] = hashlib.sha256(data).hexdigest()
            elif name == 'triggers':
                data = archive.extractfile(item).read()
                need(data == b'# Triggers added by dh_makeshlibs/13.6ubuntu1\nactivate-noawait ldconfig\n'
                     and hashlib.sha256(data).hexdigest() == TRIGGER_SHA, 'only_exact_reviewed_ldconfig_trigger')
                scripts[name] = hashlib.sha256(data).hexdigest()
    need(scripts.get('triggers') == TRIGGER_SHA, 'reviewed_trigger_present')
    return {'archive': entry, 'controlTarSHA256': CONTROL_TAR_SHA, 'controlScripts': scripts}


def apply_remote(expected):
    result = {'installerStarted': False, 'installerExitCode': None, 'errors': [], 'packageInstalled': False}
    guard_source = expected.pop('guardSource')
    need(hashlib.sha256(guard_source.encode()).hexdigest() == REFERENCE_SHA, 'pinned_cleanup_reference_before_install')
    before_cache = expected['cacheBefore']
    try:
        need(os.geteuid() == 0, 'privileged_apply_required')
        fresh = preflight()
        need(fresh['state'] == expected['state'] and fresh['candidateSHA256'] == expected['candidateSHA256']
             and fresh['cacheBefore'] == before_cache, 'reviewed_preflight_not_changed')
        if not fresh['plannedInst']:
            result['state'] = 'already_fixed_no_install'
        else:
            env = {**os.environ, 'LC_ALL': 'C', 'DEBIAN_FRONTEND': 'noninteractive', 'NEEDRESTART_MODE': 'l'}
            p = subprocess.run(APT + ['--assume-yes', '--download-only', 'install', PACKAGE + '=' + VERSION], capture_output=True, env=env)
            result['downloadExitCode'] = p.returncode
            result['downloadOutputSHA256'] = hashlib.sha256(p.stdout + p.stderr).hexdigest()
            need(p.returncode == 0, 'exact_package_download_failed')
            result['signedDebInspection'] = inspect_deb(fresh)
            need(preflight()['state'] == fresh['state'], 'host_changed_before_install')
            result['installerStarted'] = True
            p = subprocess.run(APT + ['--assume-yes', '--no-download', 'install', PACKAGE + '=' + VERSION], capture_output=True, env=env)
            result['installerExitCode'] = p.returncode
            result['installerOutputSHA256'] = hashlib.sha256(p.stdout + p.stderr).hexdigest()
            need(p.returncode == 0, 'exact_package_install_failed')
    except Exception as exc:
        result['errors'].append(str(exc) if isinstance(exc, ValueError) else type(exc).__name__)
    finally:
        try:
            after = snapshot()
            result['after'] = after
            result['packageInstalled'] = after['packages'].get('libbrotli1:amd64') == VERSION
            old = expected['state']
            changed = [{'package': p, 'before': old['packages'].get(p), 'after': after['packages'].get(p)}
                       for p in sorted(set(old['packages']) | set(after['packages'])) if old['packages'].get(p) != after['packages'].get(p)]
            result['changedPackages'] = changed
            result['hostFieldsUnchanged'] = all(old[k] == after[k] for k in old if k != 'packages')
            result['exactPackageDiff'] = changed == ([] if not expected['plannedInst'] else [{'package': 'libbrotli1:amd64', 'before': OLD, 'after': VERSION}])
            result['dpkgAuditClean'] = not run(['dpkg', '--audit'])
        except Exception as exc:
            result['errors'].append('after_observation:' + (str(exc) if isinstance(exc, ValueError) else type(exc).__name__))
        result['cacheReconciliation'] = safe_cleanup(before_cache, expected, guard_source)
        partial = DEB.parent / 'partial' / DEB.name
        result['partialArchive'] = {'path': str(partial), 'exists': partial.exists(),
                                    'retainedReason': 'partial bytes are not a verified signed archive; no deletion attempted'}
        space = os.statvfs('/')
        result['rootFreeBytesAfter'] = space.f_bfree * space.f_frsize
        result['rootFloorAndMarginAfter'] = space.f_blocks * space.f_frsize // 4 + 1 + MARGIN
        result['rootHeadroomPreserved'] = result['rootFreeBytesAfter'] >= result['rootFloorAndMarginAfter']
    result['accepted'] = (not result['errors'] and result['packageInstalled'] and result.get('exactPackageDiff')
                          and result.get('hostFieldsUnchanged') and result.get('dpkgAuditClean') and result['rootHeadroomPreserved']
                          and result['cacheReconciliation'].get('preexistingUnchanged', True))
    return result


def remote_call(ip, source, mode, request=None, password=None):
    request = request or {}
    expression = ('candidate_policy()' if mode == 'candidate' else 'preflight()' if mode == 'qualify'
                  else 'snapshot()' if mode == 'observe' else 'apply_remote(json.loads(' + repr(json.dumps(request)) + '))')
    code = source + '\ntry:\n print(json.dumps(' + expression + '))\nexcept Exception as exc:\n print(json.dumps({"remoteFailure":str(exc) if isinstance(exc,ValueError) else type(exc).__name__}))\n'
    # Module source does not dispatch its CLI when imported into this RAM namespace.
    wrapped = "exec(compile(" + repr(code) + ", '<worker2-brotli-memory>', 'exec'), {'__name__':'worker2_brotli_memory'})"
    args = ['python3', '-B', '-c', wrapped]
    if password is not None:
        args = ['sudo', '-S', '-p', '', '--', *args]
    p = subprocess.run(SSH + ['james@' + ip, shlex.join(args)], input=None if password is None else password + b'\n',
                       capture_output=True, timeout=None if mode == 'apply' else 180)
    need(p.returncode == 0, 'remote_' + mode + '_failed_exit_' + str(p.returncode))
    need(len(p.stdout) < 8 * 1024**2, 'remote_metadata_limit')
    value = json.loads(p.stdout)
    need('remoteFailure' not in value, 'remote_' + mode + ':' + value.get('remoteFailure', ''))
    return value


def cluster():
    def kube(words):
        p = subprocess.run(SSH + ['james@192.168.0.4', shlex.join(['kubectl', *words, '-o', 'json', '--request-timeout=20s'])], capture_output=True, timeout=45)
        need(p.returncode == 0, 'normal_master_kubectl_read')
        return json.loads(p.stdout)
    expected = {'masternode': 'f2df6169-4592-4544-b62c-74d89f598648', 'workernode1': 'e8d4555f-7cea-445f-b84f-6416964045a9', 'workernode2': 'eda66e65-f388-4b97-b64f-a709cda81894'}
    nodes = {}
    for n in kube(['get', 'nodes'])['items']:
        name = n['metadata']['name']; conditions = {c['type']: c['status'] for c in n['status']['conditions']}
        need(expected.get(name) == n['metadata']['uid'], 'original_node_identity')
        need(conditions.get('Ready') == 'True' and all(conditions.get(k) == 'False' for k in ['MemoryPressure', 'DiskPressure', 'PIDPressure'])
             and conditions.get('NetworkUnavailable', 'False') == 'False' and not n['spec'].get('unschedulable', False), 'three_ready_uncordoned_nodes_without_pressure')
        nodes[name] = {'uid': n['metadata']['uid'], 'conditions': conditions, 'nodeInfo': n['status']['nodeInfo']}
    need(set(nodes) == set(expected), 'exact_three_nodes')
    settings = kube(['-n', 'longhorn-system', 'get', 'settings.longhorn.io', 'storage-minimal-available-percentage'])
    need(settings['value'] == '25', 'original_longhorn_floor_unchanged')
    disks = {}
    for n in kube(['-n', 'longhorn-system', 'get', 'nodes.longhorn.io'])['items']:
        name = n['metadata']['name']
        need(name in expected, 'longhorn_node_identity')
        for key, d in n['status']['diskStatus'].items():
            floor = d['storageMaximum'] // 4 + 1
            need(d['storageAvailable'] >= floor + MARGIN + (PEAK if name == HOST else 0), 'longhorn_floor_margin_peak:' + name)
            disks[name + '/' + key] = {'available': d['storageAvailable'], 'floor': floor, 'margin': MARGIN, 'payloadPeak': PEAK if name == HOST else 0}
    need({key.split('/')[0] for key in disks} == set(expected), 'three_longhorn_nodes')
    return {'nodes': nodes, 'longhornMinimumAvailablePercent': 25, 'disks': disks}


def write_new(path, data):
    need(path.parent == H and path.resolve().parent == H and not path.is_symlink(), 'exact_metadata_output')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(data, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def reviewed_preinstall_refusal(path):
    """Exactly one known no-installer refusal; never an uncertain-action retry."""
    need(path == H / REFUSED_RECEIPT and path.resolve() == path and not path.is_symlink()
         and sha(path) == REFUSED_RECEIPT_SHA, 'exact_reviewed_preinstall_receipt')
    need(not (H / 'apply-intent-r2.json').exists(), 'second_reviewed_attempt_already_dispatched')
    intent_path = H / 'apply-intent.json'
    need(not intent_path.is_symlink() and sha(intent_path) == ORIGINAL_INTENT_SHA, 'original_intent_unchanged')
    intent = json.loads(intent_path.read_bytes())
    old = json.loads(path.read_bytes()); remote = old['remote']
    need(old['mode'] == 'apply' and old['status'] == 'not_accepted' and old['applied'] is False
         and old['controllerSHA256'] == REFUSED_SOURCE_SHA and old['installationDispatchAttempted'] is True,
         'reviewed_original_dispatch_identity')
    need(intent['receipt'] == str(path) and intent['controllerSHA256'] == REFUSED_SOURCE_SHA
         and intent['qualificationSHA256'] == old['qualificationSHA256'] and intent['uncertainReplayForbidden'] is True,
         'original_intent_receipt_binding')
    need(remote['installerStarted'] is False and remote['installerExitCode'] is None
         and remote['errors'] == ['only_ldconfig_trigger'] and remote['downloadExitCode'] == 0
         and remote['packageInstalled'] is False and remote['accepted'] is False,
         'definitive_known_preinstaller_refusal_only')
    need(remote['changedPackages'] == [] and remote['hostFieldsUnchanged'] is True
         and remote['dpkgAuditClean'] is True and remote['after'] == old['preflight']['state']
         and remote['after']['packages']['libbrotli1:amd64'] == OLD
         and remote['rootHeadroomPreserved'] is True and not remote['partialArchive']['exists'],
         'complete_unchanged_host_and_package_state')
    need(old['clusterNodesUnchanged'] is True
         and old['clusterBefore']['nodes'] == old['clusterAfter']['nodes'], 'complete_unchanged_cluster_state')
    cache = old['preflight']['cacheBefore']; cleanup = remote['cacheReconciliation']
    need(cache['exists'] is True and cache['sha256'] == SIGNED_DEB_SHA and cache['bytes'] == 315370
         and cache['inode'] == 786371 and old['preflight']['candidateSHA256'] == SIGNED_DEB_SHA
         and cleanup['retained'] == 'preexisting native package cache; never owned'
         and cleanup['preexistingUnchanged'] is True and cleanup['removedBytes'] == 0
         and cleanup['removedAllocatedBytes'] == 0 and cleanup['path'] == str(DEB),
         'existing_signed_archive_preserved_no_cleanup_refusal')
    review_path = H / 'signed-package-trigger-review.json'
    need(review_path.resolve() == review_path and not review_path.is_symlink()
         and sha(review_path) == TRIGGER_REVIEW_SHA, 'actual_public_trigger_review_binding')
    review = json.loads(review_path.read_bytes())
    need(review['archiveSHA256'] == SIGNED_DEB_SHA and review['controlTarSHA256'] == CONTROL_TAR_SHA
         and review['triggerSHA256'] == TRIGGER_SHA, 'exact_reviewed_control_hashes')
    return old


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['candidate', 'qualify', 'apply', 'observe'])
    parser.add_argument('--qualification', type=Path)
    parser.add_argument('--privileged-read', action='store_true', help='TTY-only sudo for root-readable protected configuration hashes')
    parser.add_argument('--reviewed-preinstall-refusal', type=Path,
                        help='Only the fixed complete hash-bound no-installer trigger-format refusal may use one r2 intent')
    args = parser.parse_args()
    source_path = Path(__file__).resolve()
    repository = source_path.parents[5]
    source = source_path.read_text()
    need(os.geteuid() == 1000 and F.is_mount() and run(['findmnt', '-n', '-o', 'UUID', '-T', str(F)]) == VOLUME, 'existing_owned_F_volume')
    H.mkdir(mode=0o700, parents=True, exist_ok=True)
    need(H.resolve() == H and H.stat().st_uid == os.getuid() and not H.stat().st_mode & 0o077, 'private_exact_task_root')
    ownership = H / 'ownership.json'
    if not ownership.exists():
        write_new(ownership, {'owner': 'worker2_brotli_security', 'root': str(H), 'volumeUUID': VOLUME,
                  'controllerPeakBytes': 2 * 1024**2, 'hostPeakBytes': PEAK,
                  'protected': 'all source/prior receipts/credentials/runtime config/PVCs/NAS/user data and preexisting package cache',
                  'generated': 'metadata only here; one signed native APT archive on worker2, removed if newly created and safe; installed package/dpkg state is required runtime',
                  'regenerate': 'same controller qualify/apply; exact pinned trusted native package version; no compiler/dependency copies'})
    record = {'mode': args.mode, 'startedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'controllerSHA256': sha(source_path), 'status': 'started', 'applied': False}
    destination = H / (args.mode + '-' + uuid.uuid4().hex + '.json')
    password = None
    try:
        record['clusterBefore'] = cluster()
        helper = repository / 'k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py'
        retry = None
        need(not args.reviewed_preinstall_refusal or args.mode == 'apply', 'reviewed_refusal_only_with_apply')
        if args.mode == 'apply':
            if args.reviewed_preinstall_refusal:
                retry = reviewed_preinstall_refusal(args.reviewed_preinstall_refusal)
                need(record['clusterBefore']['nodes'] == retry['clusterAfter']['nodes'], 'reviewed_refusal_cluster_still_unchanged')
            else:
                need(not (H / 'apply-intent.json').exists(), 'prior_apply_intent_requires_observation_no_replay')
        if args.privileged_read or args.mode == 'apply':
            need(args.mode != 'candidate', 'candidate_does_not_require_privilege')
            record['privilegeHelperSHA256'] = sha(helper)
            password = runpy.run_path(str(helper))['privilege_input']()
        if args.mode == 'candidate':
            record['candidate'] = remote_call(IP, source, 'candidate')
            record['status'] = 'candidate_observed_not_qualified'
        elif args.mode == 'observe':
            record['state'] = remote_call(IP, source, 'observe', password=password)
            record['status'] = 'observed_only'
        elif args.mode == 'qualify':
            record['preflight'] = remote_call(IP, source, 'qualify', password=password)
            record['status'] = 'qualified'
        else:
            q = args.qualification
            need(q is not None and q.parent == H and q.resolve() == q and q.is_file() and not q.is_symlink(), 'exact_prior_qualification_required')
            prior = json.loads(q.read_bytes())
            need(prior['status'] == 'qualified' and prior['controllerSHA256'] == record['controllerSHA256'], 'reviewed_source_and_qualification')
            need(prior.get('privilegeHelperSHA256') == record.get('privilegeHelperSHA256'), 'reviewed_privilege_helper_unchanged')
            record['qualificationSHA256'] = sha(q)
            record['preflight'] = remote_call(IP, source, 'qualify', password=password)
            need(record['preflight']['state'] == prior['preflight']['state']
                 and record['preflight']['candidateSHA256'] == prior['preflight']['candidateSHA256'], 'fresh_matches_reviewed_qualification')
            if retry is not None:
                need(record['preflight']['state'] == retry['remote']['after']
                     and record['preflight']['cacheBefore'] == retry['preflight']['cacheBefore']
                     and record['preflight']['candidateSHA256'] == SIGNED_DEB_SHA,
                     'reviewed_refusal_host_signed_archive_still_unchanged')
                record['reviewedPreinstallRefusal'] = {'receiptSHA256': REFUSED_RECEIPT_SHA,
                    'originalIntentSHA256': ORIGINAL_INTENT_SHA, 'triggerReviewSHA256': TRIGGER_REVIEW_SHA,
                    'controlTarSHA256': CONTROL_TAR_SHA, 'triggerSHA256': TRIGGER_SHA}
            need(REFERENCE.resolve() == REFERENCE and not REFERENCE.is_symlink() and sha(REFERENCE) == REFERENCE_SHA,
                 'pinned_existing_cleanup_reference_before_transport')
            record['cleanupReferenceSHA256'] = REFERENCE_SHA
            packet = {**record['preflight'], 'guardSource': REFERENCE.read_bytes().decode()}
            # Write once BEFORE dispatch. Any interrupted/uncertain invocation can
            # only observe afterwards; never automatically replay an installer.
            intent_name = 'apply-intent-r2.json' if retry is not None else 'apply-intent.json'
            write_new(H / intent_name, {'qualification': str(q), 'qualificationSHA256': sha(q),
                      'controllerSHA256': record['controllerSHA256'], 'receipt': str(destination), 'startedAt': record['startedAt'],
                      'uncertainReplayForbidden': True,
                      'reviewedPreinstallRefusal': record.get('reviewedPreinstallRefusal')})
            record['installationDispatchAttempted'] = True
            record['applied'] = None  # Unknown until a complete remote receipt returns.
            record['remote'] = remote_call(IP, source, 'apply', packet, password)
            record['applied'] = record['remote'].get('installerStarted', False)
            record['clusterAfter'] = cluster()
            record['clusterNodesUnchanged'] = record['clusterBefore']['nodes'] == record['clusterAfter']['nodes']
            record['status'] = 'accepted' if record['remote']['accepted'] and record['clusterNodesUnchanged'] else 'not_accepted'
    except BaseException as exc:
        record['status'] = 'failed_or_uncertain'
        record['error'] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        record['automaticReplayAllowed'] = False
    finally:
        password = None
        record['finishedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write_new(destination, record)
    print(json.dumps({'status': record['status'], 'receipt': str(destination), 'applied': record['applied'], 'error': record.get('error')}))
    return 0 if record['status'] in ['candidate_observed_not_qualified', 'qualified', 'accepted', 'observed_only'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
