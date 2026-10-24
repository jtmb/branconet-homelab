"""Exactly two official core patch images; reuse verified public inputs, never deploy."""
import argparse
import collections
import datetime
import fcntl
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import signal
import socket
import stat
import subprocess
import time
import urllib.request
import urllib.parse

BASE = Path('/home/james/.local/share/branconet-migration')
ROOT = BASE / 'vendor-core-scan-20261024'
INPUT = BASE / 'vendor-cert-manager-scan-20261024/inputs'
OWNER = pwd.getpwnam('james')
TOOL_SHA = 'd1dfca6ae10a1ad4540bb94e64f0510077c47008920a9b554986b39dca573d83'
FILES = {
    'bin/trivy': (176029856, TOOL_SHA),
    'cache/db/trivy.db': (1628737536, '6fd7f9c44ff3120e0d15d5b5b2234e1ff1c9e7a6b56b4e776041f93faf1f6f17'),
    'cache/db/metadata.json': (150, 'd2caf386c5ec60a3fc13376aebe5cd9a236f4c20940e3eec361d4c51c544bce9'),
    'results.tpl': (15, 'd5a74b8473128e4c4c58d0329523c990adfff71452c9039592190ae6ddb84e8e'),
}
IMAGES = {
    'etcd': ('0d27b9478551f431f82d1e0ddb6c87ad07ebae8b904c637f3a99213349523910', 'b4a41c6864baf573f5213dce18b2a95e1002ec6c5a1a26ad900c2ea166ac6d0b'),
    'coredns': ('7efd3c635b03efd68c4e8398fc45f0d993d0e9ab016f72c1cefb0fd6d01aa286', '2329f5f0e7e79fbe56dcdf11ecc4337ee2476bb251095bc275fe9461cb88a55b'),
}
REPOSITORIES = {'etcd': 'etcd', 'coredns': 'coredns/coredns'}
TAGS = {'etcd': '3.7.3-0', 'coredns': 'v1.14.7'}
RELEASES = {'etcd': 'https://github.com/etcd-io/etcd/releases/tag/v3.7.3',
            'coredns': 'https://github.com/coredns/coredns/releases/tag/v1.14.7'}
# Observed on workernode1 at2026-10-24T05:21:45UTC, with both index SHA chains.
REDIRECT_HOST = 'us-east5-docker.pkg.dev'



def need(ok, category):
    if not ok:
        raise ValueError(category)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def regular(path, uid, mode=None):
    need(path.is_absolute() and path.resolve() == path, 'path_identity')
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid == uid and not info.st_mode & 0o022, 'file_identity')
    if mode is not None:
        need(stat.S_IMODE(info.st_mode) == mode, 'file_mode')
    return info


def write(path, value):
    # Update only the current exclusively created attempt's own receipt.
    temp = path.with_name(path.name + '.next-' + str(os.getpid()) + '-' + str(time.monotonic_ns()))
    with temp.open('x') as stream:
        os.chmod(temp, 0o600)
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def reserve(extra=0):
    info = os.statvfs(ROOT)
    free = info.f_bavail * info.f_frsize
    floor = info.f_blocks * info.f_frsize // 4 + 8 * 1024 ** 3
    need(free >= floor + extra, 'capacity_reserve')
    need(info.f_favail >= max(250000, info.f_files // 10), 'inode_reserve')
    return {'availableBytes': free, 'requiredReserveBytes': floor, 'freeInodes': info.f_favail}


def verify_inputs(root, full=True):
    result = {}
    for relative, (size, digest) in FILES.items():
        path = root / relative
        info = regular(path, 0)
        need(info.st_size == size, 'input_size')
        if full:
            need(sha(path) == digest, 'input_sha256')
        result[relative] = {'bytes': size, 'sha256': digest, 'device': info.st_dev,
                            'inode': info.st_ino, 'mtimeNS': info.st_mtime_ns}
    return result


def private_group():
    group = grp.getgrgid(OWNER.pw_gid)
    members = set(group.gr_mem) | {p.pw_name for p in pwd.getpwall() if p.pw_gid == OWNER.pw_gid}
    need(members == {'james'}, 'operator_primary_group_not_private')


def setup():
    need(os.geteuid() == 0, 'root_setup_required')
    private_group()
    # Existing public input snapshot is verified in place; never copied/chmodded.
    verify_inputs(INPUT)
    for relative in ['', 'bin', 'cache', 'cache/db']:
        path = INPUT / relative
        info = path.lstat()
        need(path.resolve() == path and stat.S_ISDIR(info.st_mode)
             and info.st_uid == 0 and info.st_gid == OWNER.pw_gid
             and stat.S_IMODE(info.st_mode) == 0o750, 'existing_input_directory')
    lock = INPUT / 'batch.lock'
    regular(lock, 0, 0o440)
    need(lock.stat().st_size == 0, 'existing_shared_lock')
    reserve()
    print(json.dumps({'state': 'existing_inputs_verified_no_scan', 'sourceKind': 'upstream-registry',
                      'inputHashes': verify_inputs(INPUT), 'inputsCopiedOrChanged': False,
                      'securityAcceptance': False}))


def attempt_path(attempt):
    need(re.fullmatch('[0-9a-f]{12}', attempt), 'attempt_identity')
    return ROOT / 'attempts' / attempt


def checked_attempt(attempt):
    path = attempt_path(attempt)
    info = path.lstat()
    need(path.resolve() == path and stat.S_ISDIR(info.st_mode)
         and info.st_uid == OWNER.pw_uid and stat.S_IMODE(info.st_mode) == 0o700, 'attempt_directory')
    receipt = path / 'receipt.json'
    regular(receipt, receipt.lstat().st_uid, 0o600)
    need(receipt.lstat().st_uid in [0, OWNER.pw_uid], 'receipt_owner')
    return path


def prepare(attempt):
    need(os.geteuid() == 0, 'root_prepare_required')
    verify_inputs(INPUT)
    reserve(2 * 1024 ** 3)
    path = attempt_path(attempt)
    path.mkdir(mode=0o700)  # Never reuse, overwrite or resume a prior attempt.
    os.chown(path, OWNER.pw_uid, OWNER.pw_gid)
    for name in ['home', 'docker-config', 'tmp', 'cache']:
        item = path / name
        item.mkdir(mode=0o700)
        os.chown(item, OWNER.pw_uid, OWNER.pw_gid)
    for name in ['db']:
        os.symlink(INPUT / 'cache' / name, path / 'cache' / name)
    for name, content in [('trivy-empty.yaml', '{}\n'), ('no-ignore', ''), ('docker-config/config.json', '{"auths":{}}\n')]:
        item = path / name
        with item.open('x') as stream:
            stream.write(content)
        os.chown(item, OWNER.pw_uid, OWNER.pw_gid)
        os.chmod(item, 0o400)
    write(path / 'receipt.json', {'sourceKind': 'upstream-registry', 'state': 'prepared',
          'attempt': attempt, 'preparedUTC': utc(), 'scanComplete': False, 'securityAcceptance': False})
    os.chown(path / 'receipt.json', OWNER.pw_uid, OWNER.pw_gid)
    print(json.dumps({'state': 'prepared', 'attempt': attempt, 'root': str(path)}))


def unit_state(attempt):
    unit = 'branconet-vendor-core-scan-' + attempt + '.service'
    args = ['systemctl', 'show', unit]
    for name in ['LoadState', 'ActiveState', 'SubState', 'Result', 'ControlGroup', 'User',
                 'MemoryMax', 'MemorySwapMax', 'CPUQuotaPerSecUSec', 'TasksMax',
                 'RuntimeMaxUSec', 'ProtectHome', 'ProtectSystem', 'PrivateNetwork', 'NoNewPrivileges',
                 'PrivateDevices', 'CapabilityBoundingSet', 'BindPaths', 'BindReadOnlyPaths',
                 'ReadWritePaths', 'NoExecPaths', 'InaccessiblePaths', 'LimitFSIZE']:
        args += ['-p', name]
    proc = subprocess.run(args, capture_output=True, text=True, timeout=15)
    need(proc.returncode == 0, 'unit_metadata')
    return dict(line.split('=', 1) for line in proc.stdout.splitlines() if '=' in line)


def limits(attempt):
    state = unit_state(attempt)
    group = '/system.slice/branconet-vendor-core-scan-' + attempt + '.service'
    need(state['ControlGroup'] == group and Path('/proc/self/cgroup').read_text().strip() == '0::' + group, 'owned_cgroup')
    need(state['User'] == 'james' and os.geteuid() == OWNER.pw_uid, 'unprivileged_worker')
    need(state['ProtectHome'] == 'tmpfs' and state['ProtectSystem'] == 'strict'
         and state['PrivateNetwork'] == 'no' and state['NoNewPrivileges'] == 'yes', 'unit_isolation')
    need(state['PrivateDevices'] == 'yes' and state['CapabilityBoundingSet'] == '', 'unprivileged_devices_caps')
    need(not Path('/home/james/.ssh').exists() and not Path('/home/james/.kube').exists(), 'operator_home_must_be_hidden')
    need(state['RuntimeMaxUSec'] in ['15min', '900s'], 'runtime_bound')
    base = Path('/sys/fs/cgroup') / group.lstrip('/')
    observed = {n: (base / n).read_text().strip() for n in ['memory.max', 'memory.swap.max', 'cpu.max', 'pids.max']}
    need(observed['memory.max'] == '1073741824' and observed['memory.swap.max'] == '0'
         and observed['pids.max'] == '128', 'memory_tasks_bounds')
    quota, period = map(int, observed['cpu.max'].split())
    need(quota == 2 * period and os.getpriority(os.PRIO_PROCESS, 0) == 10, 'cpu_nice_bounds')
    need(os.environ.get('GOMAXPROCS') == '2' and os.environ.get('GOMEMLIMIT') == '512MiB', 'go_bounds')
    return {'systemd': state, 'cgroupFiles': observed}


class ManifestRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, repository, digest):
        self.repository, self.digest, self.chain = repository, digest, []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
        path = '/v2/' + self.repository + '/manifests/sha256:' + self.digest
        target = '/v2/k8s-artifacts-prod/images/' + self.repository + '/manifests/sha256:' + self.digest
        query = urllib.parse.parse_qs(new.query, strict_parsing=True)
        need(len(self.chain) == 0 and code == 307, 'unexpected_registry_redirect_count_or_code')
        need(old.scheme == 'https' and old.hostname == 'registry.k8s.io' and old.path == path
             and not old.query and not old.fragment and old.port in [None, 443]
             and old.username is None and old.password is None, 'registry_redirect_source')
        need(new.scheme == 'https' and new.hostname == REDIRECT_HOST and new.path == target
             and not new.fragment and new.port in [None, 443]
             and new.username is None and new.password is None, 'registry_redirect_destination')
        need(set(query) <= {'rid'} and all(len(v) == 1 and re.fullmatch('[0-9a-f]{1,128}', v[0])
                                          for v in query.values()), 'registry_redirect_query')
        need(not req.has_header('Authorization') and not req.has_header('Cookie'), 'public_manifest_credentials')
        self.chain.append({'httpStatus': code, 'from': urllib.parse.urlunsplit(old),
                           'to': urllib.parse.urlunsplit((new.scheme, new.netloc, new.path, '', '')),
                           'queryKeys': sorted(query)})
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def source_proof(component, folder):
    index, manifest = IMAGES[component]
    repository = REPOSITORIES[component]
    url = 'https://registry.k8s.io/v2/' + repository + '/manifests/'
    documents, redirects = {}, {}
    for label, digest in [('index', index), ('amd64Manifest', manifest)]:
        redirect = ManifestRedirect(repository, digest)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), redirect)
        request = urllib.request.Request(url + 'sha256:' + digest, headers={'Accept':
            'application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json'})
        with opener.open(request, timeout=20) as response:
            data = response.read(2 * 1024 * 1024 + 1)
        need(len(data) <= 2 * 1024 * 1024 and hashlib.sha256(data).hexdigest() == digest, 'registry_digest')
        with (folder / (label + '.json')).open('xb') as output:
            output.write(data)
        documents[label] = json.loads(data)
        redirects[label] = redirect.chain
    choices = [v['digest'] for v in documents['index']['manifests']
               if v.get('platform', {}).get('os') == 'linux' and v.get('platform', {}).get('architecture') == 'amd64']
    need(choices == ['sha256:' + manifest] and documents['amd64Manifest']['schemaVersion'] == 2, 'platform_binding')
    return {'repository': repository, 'tag': TAGS[component], 'indexDigest': 'sha256:' + index,
            'amd64ManifestDigest': 'sha256:' + manifest, 'configDigest': documents['amd64Manifest']['config']['digest'],
            'primaryRegistry': 'https://registry.k8s.io', 'manifestRedirects': redirects,
            'upstreamRelease': RELEASES[component], 'signatureVerified': False}


def disk_bound(path):
    total = entries = 0
    for folder, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [n for n in dirs if not (Path(folder) / n).is_symlink()]
        for name in files:
            info = (Path(folder) / name).lstat()
            need(stat.S_ISREG(info.st_mode), 'unexpected_scan_file_type')
            total += info.st_size
            entries += 1
    need(total <= 2 * 1024 ** 3 and entries <= 100000, 'attempt_disk_bound')
    return {'logicalBytes': total, 'files': entries}


def other_scanner(owned=None):
    for path in Path('/proc').iterdir():
        if path.name.isdigit() and int(path.name) != owned:
            try:
                need((path / 'comm').read_text().strip() != 'trivy', 'another_scanner_running')
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                pass


def reject_java(results):
    # Keep language analysis enabled. A surprise Java artifact cannot be called
    # clean merely because this fixed Go-only input snapshot has no Java DB.
    for result in results:
        kind = str(result.get('Type', '')).lower()
        need(not re.search(r'java|maven|gradle|(^|[-_])jar($|[-_])|^pom$', kind), 'unexpected_java_requires_review')
        for row in [result] + (result.get('Packages') or []) + (result.get('Vulnerabilities') or []):
            need(str(row.get('Language', '')).lower() != 'java', 'unexpected_java_requires_review')
            for field in ['Identifier', 'PkgIdentifier']:
                purl = str((row.get(field) or {}).get('PURL', '')).lower()
                need(not purl.startswith(('pkg:maven/', 'pkg:gradle/')), 'unexpected_java_requires_review')
            for field in ['Target', 'FilePath', 'PkgPath']:
                need(not re.search(r'\.(jar|war|ear)(?:$|[!/])|\.pom$', str(row.get(field, '')).lower()),
                     'unexpected_java_requires_review')


def run(attempt):
    path = checked_attempt(attempt)
    receipt = path / 'receipt.json'
    record = json.loads(receipt.read_text())
    need(record['state'] == 'prepared' and record['attempt'] == attempt
         and record['sourceKind'] == 'upstream-registry', 'prepared_attempt_required')
    child = None
    started = time.monotonic()
    def stop(signum, frame):
        raise ValueError('unit_stop_requested')
    signal.signal(signal.SIGTERM, stop)
    try:
        with (INPUT / 'batch.lock').open('rb') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            record.update(state='validating', startedUTC=utc(), helperSHA256=sha(Path(__file__)),
                          resourceProof=limits(attempt), inputProof=verify_inputs(INPUT), components=[],
                          publicInputOrigin=str(INPUT), inputSnapshot=str(INPUT),
                          upstreamReleases=RELEASES)
            need((INPUT / 'results.tpl').read_text().strip() == '{{ toJson . }}', 'results_only_template')
            metadata = json.loads((INPUT / 'cache/db/metadata.json').read_text())
            updated = re.sub(r'(\.\d{6})\d+(?=[+-]|$)', r'\1', metadata['UpdatedAt'].replace('Z', '+00:00'))
            age = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(updated)).total_seconds() / 3600
            need(0 <= age <= 24, 'frozen_database_older_than_24_hours')
            record.update(database=metadata, databaseAgeHours=age, filesystemBefore=reserve())
            for name in ['db']:
                need((path / 'cache' / name).is_symlink() and os.readlink(path / 'cache' / name) == str(INPUT / 'cache' / name), 'db_binding')
            for name in ['docker-config/config.json', 'trivy-empty.yaml', 'no-ignore']:
                regular(path / name, OWNER.pw_uid, 0o400)
            need(not list((path / 'home').iterdir()), 'new_home_must_be_empty')
            need((path / 'docker-config/config.json').read_text() == '{"auths":{}}\n'
                 and (path / 'trivy-empty.yaml').read_text() == '{}\n'
                 and (path / 'no-ignore').read_bytes() == b'', 'empty_scanner_configuration')
            for component, (index, _) in IMAGES.items():
                other_scanner()
                reserve()
                folder = path / component
                folder.mkdir(mode=0o700)
                proof = source_proof(component, folder)
                reference = 'registry.k8s.io/' + REPOSITORIES[component] + ':' + TAGS[component] + '@sha256:' + index
                output = folder / 'results.json'
                error = folder / 'scanner.stderr'
                cmd = [str(INPUT / 'bin/trivy'), 'image', '--image-src', 'remote', '--platform', 'linux/amd64',
                       '--config', str(path / 'trivy-empty.yaml'), '--cache-dir', str(path / 'cache'),
                       '--scanners', 'vuln', '--offline-scan', '--skip-db-update', '--skip-java-db-update',
                       '--ignorefile', str(path / 'no-ignore'), '--timeout', '7m', '--parallel', '2',
                       '--quiet', '--no-progress', '--list-all-pkgs', '--format', 'template',
                       '--template', '@' + str(INPUT / 'results.tpl'), '--output', str(output), reference]
                env = {'PATH': '/usr/bin:/bin', 'HOME': str(path / 'home'), 'DOCKER_CONFIG': str(path / 'docker-config'),
                       'TMPDIR': str(path / 'tmp'), 'XDG_CACHE_HOME': str(path / 'cache'),
                       'GOMAXPROCS': '2', 'GOMEMLIMIT': '512MiB', 'TRIVY_SKIP_VERSION_CHECK': 'true', 'LANG': 'C', 'LC_ALL': 'C'}
                item = {'component': component, 'image': reference, 'sourceKind': 'upstream-registry',
                        'sourceProof': proof, 'startedUTC': utc(), 'scannerCommand': cmd, 'state': 'scanning'}
                record['components'].append(item)
                record['state'] = 'scanning'
                write(receipt, record)
                with error.open('xb') as errors:
                    child = subprocess.Popen(cmd, cwd=folder, env=env, stdin=subprocess.DEVNULL,
                                             stdout=subprocess.DEVNULL, stderr=errors, start_new_session=True)
                    image_started = time.monotonic()
                    while child.poll() is None:
                        reserve()
                        disk_bound(path)
                        other_scanner(child.pid)
                        need(time.monotonic() - image_started < 480 and time.monotonic() - started < 840, 'scan_deadline')
                        need(not output.exists() or output.stat().st_size <= 64 * 1024 ** 2, 'results_size')
                        need(error.stat().st_size <= 16 * 1024 ** 2, 'diagnostic_size')
                        time.sleep(2)
                item.update(scannerExitCode=child.returncode, endedUTC=utc())
                need(child.returncode == 0, 'scanner_failed_not_clean')
                regular(output, OWNER.pw_uid)
                regular(error, OWNER.pw_uid)
                need(error.stat().st_size <= 16 * 1024 ** 2, 'diagnostic_size')
                disk_bound(path)
                need(0 < output.stat().st_size <= 64 * 1024 ** 2, 'results_size')
                results = json.loads(output.read_text())
                need(isinstance(results, list) and results and all(isinstance(r, dict) for r in results), 'results_only_shape')
                reject_java(results)
                need(any(r.get('Type') == 'gobinary' for r in results), 'go_binary_coverage_missing')
                findings = [v for r in results for v in r.get('Vulnerabilities') or []]
                item.update(state='scanned', resultsSHA256=sha(output), resultsBytes=output.stat().st_size,
                            severityCounts=dict(collections.Counter(v['Severity'] for v in findings)),
                            fixableCriticalHighRows=sum(v['Severity'] in ['CRITICAL', 'HIGH'] and bool(v.get('FixedVersion')) for v in findings),
                            reportRedaction='Results only; no ImageConfig/Env/history/labels serialized')
                write(receipt, record)
                child = None
            need(verify_inputs(INPUT) == record['inputProof'], 'inputs_changed_during_scan')
            record.update(state='complete', scanComplete=True, endedUTC=utc(), resourceProofAfter=limits(attempt),
                          filesystemAfter=reserve(), attemptUsage=disk_bound(path), securityAcceptance=False)
            write(receipt, record)
    except Exception as exc:
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
        category = str(exc) if isinstance(exc, ValueError) and re.fullmatch('[a-z0-9_]+', str(exc)) else 'scan_refused_or_failed'
        record.update(state='failed', endedUTC=utc(), failureCategory=category, scanComplete=False, securityAcceptance=False)
        write(receipt, record)
        raise SystemExit(1)


def status(attempt):
    path = checked_attempt(attempt)
    record = json.loads((path / 'receipt.json').read_text())
    need(record['sourceKind'] == 'upstream-registry', 'source_kind')
    unit = unit_state(attempt)
    if record['state'] not in ['complete', 'failed'] and unit.get('ActiveState') in ['failed', 'inactive']:
        record.update(state='failed', scanComplete=False, securityAcceptance=False,
                      endedUTC=utc(), failureCategory='unit_terminated_without_complete_receipt', terminalUnitState=unit)
        write(path / 'receipt.json', record)
    print(json.dumps({'sourceKind': 'upstream-registry', 'attempt': attempt, 'state': record['state'],
          'scanComplete': record.get('scanComplete', False), 'securityAcceptance': False,
          'receipt': str(path / 'receipt.json'), 'receiptSHA256': sha(path / 'receipt.json'),
          'components': [{k: r.get(k) for k in ['component', 'state', 'severityCounts', 'resultsSHA256']} for r in record.get('components', [])],
          'unit': unit}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['setup', 'prepare', 'run', 'status'])
    parser.add_argument('--attempt', default='')
    args = parser.parse_args()
    need(socket.gethostname() == 'workernode1', 'worker1_only')
    code = Path(__file__).resolve()
    regular(code, 0, 0o440)
    need(code == ROOT / 'helpers' / sha(code) / 'scan_vendor.py', 'content_addressed_source')
    need(ROOT.resolve() == ROOT and ROOT.lstat().st_uid == 0
         and ROOT.lstat().st_gid == OWNER.pw_gid
         and stat.S_IMODE(ROOT.lstat().st_mode) == 0o750, 'root_directory_identity')
    os.umask(0o077)
    if args.phase == 'setup':
        setup()
    elif args.phase == 'prepare':
        prepare(args.attempt)
    elif args.phase == 'run':
        run(args.attempt)
    else:
        status(args.attempt)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        category = str(error) if isinstance(error, ValueError) and re.fullmatch('[a-z0-9_]+', str(error)) else 'invalid_input_or_unavailable_prerequisite'
        raise SystemExit('Official core vendor scan refused: ' + category)
