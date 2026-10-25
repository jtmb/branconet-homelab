#!/usr/bin/env python3
"""Explicit one-digest cached-runtime audit; no BORTUS application execution."""
import argparse
import collections
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
import uuid

BASE = Path('/home/brajam/.local/share/branconet-migration')
FBASE = BASE/'local-image-build-offload-20261025'
ROOT = FBASE/'bortus-cached-runtime-audit-20261025'
CROOT = BASE/'local-oci-scan-20261024'
REMOTE = '/home/james/.local/share/branconet-migration/bortus-cached-runtime-audit-20261025'
DEPENDENCY_SHA = 'ee456fd2be0fefcd0108e782771cc54b79ca9692ffaf7c4e57b6f29608094a06'
DEPENDENCY = CROOT/'helpers'/DEPENDENCY_SHA/'scan-local-oci.py'
DIGEST = 'sha256:3b076fb9b7fb64fd760691c0120f29d4e363d4ccb9910a596ff211bfc3ea0879'
REF = 'docker.io/library/bortus@'+DIGEST
POD = 'bortus-5c55f6d5b5-h9z6t'
POD_UID = 'b802cc5f-ca3f-49b2-a3f5-2cd95d2a97bc'
SSH = ['ssh', '-o', 'ControlMaster=no', '-o', 'ControlPath=none', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'IdentitiesOnly=yes',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002']
GIB = 1024**3
SCRATCH_CAP = 8*GIB
RETAINED_FLOOR = 15*GIB
SCAN_WORK = ROOT/'scan-attempts'
SCAN_LOCK = ROOT/'scan.lock'
STORAGE_POLICY = {
    'profile':'finite-native-F-cached-runtime-audit-v1',
    'writableRoot':str(ROOT), 'readOnlyInputs':str(CROOT),
    'rpcSocketRoot':str(FBASE), 'rpcDirectoryPattern':'r[0-9a-f]{7}',
    'rpcDirectoryContents':'registered owner0700 directories; bounded zero-byte AF_UNIX listeners only',
    'aggregateScratchCapBytes':SCRATCH_CAP, 'retainedNativeAndPhysicalFBytes':RETAINED_FLOOR,
    'launchNativeAndPhysicalFBytes':RETAINED_FLOOR+SCRATCH_CAP,
    'windowsCLaunchFloorBytes':RETAINED_FLOOR,
    'replacesOnlyThisWrapperPriorPolicy':'CROOT aggregate8GiB; native25percent-plus8GiB reserve',
    'sharedScannerAndPinnedPrimitivesChanged':False,
}



def need(value, code):
    if not value:
        raise ValueError(code)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024**2), b''):
            h.update(b)
    return h.hexdigest()


def save(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    path.chmod(0o600)


def directory(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    s = path.lstat()
    need(path.resolve() == path and stat.S_ISDIR(s.st_mode) and s.st_uid == 1000 and
         stat.S_IMODE(s.st_mode) == 0o700, 'private_directory')


def approved_mount():
    need(FBASE.resolve() == FBASE and FBASE.is_mount() and FBASE.stat().st_dev != Path('/').stat().st_dev,
         'approved_external_mount')
    need(not ROOT.exists() or (ROOT.resolve() == ROOT and ROOT.stat().st_dev == FBASE.stat().st_dev),
         'audit_root_on_native_F')


def audit_reserve(extra=0, launch=False):
    """Wrapper-local F policy; never repoint or modify the pinned C input helper."""
    approved_mount()
    need(0 <= extra <= SCRATCH_CAP, 'bounded_stage_estimate')
    native, physical = os.statvfs(FBASE), os.statvfs('/mnt/f')
    required = RETAINED_FLOOR + (SCRATCH_CAP if launch else extra)
    native_free, physical_free = native.f_bavail*native.f_frsize, physical.f_bavail*physical.f_frsize
    need(native_free >= required and physical_free >= required, 'native_and_physical_F_retained_floor')
    need(native.f_favail >= max(250000, native.f_files//10), 'inode_reserve')
    allocated = 0
    if ROOT.exists():
        for folder, dirs, files in os.walk(ROOT, followlinks=False):
            for name in dirs:
                q = Path(folder)/name
                if q.is_symlink():
                    rel = str(q.relative_to(ROOT))
                    need(re.fullmatch(r'scan-attempts/bortus-cached-[0-9a-f]{12}/cache/(db|java-db)', rel)
                         and q.resolve() == CROOT/'cache'/name, 'only_readonly_pinned_DB_links')
                else:
                    need(q.stat().st_dev == FBASE.stat().st_dev, 'no_nested_scratch_filesystem')
            for name in files:
                q = Path(folder)/name
                st = q.lstat()
                need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_dev == FBASE.stat().st_dev,
                     'owned_audit_regular_file')
                allocated += st.st_blocks*512
                if re.fullmatch(r'attempts/[0-9a-f]{12}/controller-(probe|export)/rpc-path.json', str(q.relative_to(ROOT))):
                    need(st.st_size <= 1024, 'bounded_RPC_registry')
                    rpc = Path(json.loads(q.read_text())['path'])
                    ri = rpc.lstat()
                    need(rpc.parent == FBASE and re.fullmatch(r'r[0-9a-f]{7}', rpc.name)
                         and rpc.resolve() == rpc and stat.S_ISDIR(ri.st_mode)
                         and ri.st_uid == 1000 and stat.S_IMODE(ri.st_mode) == 0o700
                         and ri.st_dev == FBASE.stat().st_dev, 'owned_native_F_RPC_registry')
                    entries = list(rpc.iterdir())
                    need(len(entries) <= 16, 'bounded_RPC_sockets')
                    for endpoint in entries:
                        ei = endpoint.lstat()
                        need(re.fullmatch(r'listener-[a-z0-9_]{8}', endpoint.name)
                             and stat.S_ISSOCK(ei.st_mode) and ei.st_uid == 1000
                             and ei.st_nlink == 1 and ei.st_size == 0,
                             'RPC_directory_contains_only_local_listener_sockets')
                        allocated += ei.st_blocks*512
    need(allocated <= SCRATCH_CAP and allocated+extra <= SCRATCH_CAP, 'audit_8GiB_aggregate_budget')
    return {'storagePolicy':STORAGE_POLICY, 'nativeFAvailableBytes':native_free,
            'physicalFAvailableBytes':physical_free, 'requiredAvailableBytes':required,
            'allocatedAuditBytes':allocated, 'projectedAdditionalBytes':extra,
            'freeInodes':native.f_favail}


def launch_capacity(extra, scan=False):
    r = subprocess.run(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
                        '-NoProfile', '-NonInteractive', '-Command', '(Get-PSDrive C).Free'],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20, check=True)
    free_c = int(r.stdout.strip())
    need(free_c >= RETAINED_FLOOR, 'Windows_C_launch_floor_no_scratch')
    capacity = audit_reserve(extra, launch=scan)
    return {**capacity, 'windowsCFreeBytes':free_c}


def controller_env(dest, phase):
    runtime = dest/('controller-'+phase)
    directory(runtime)
    for name in ['tmp', 'home', 'cache', 'ansible-local', 'ansible-control']:
        directory(runtime/name)
    return dict(os.environ, HOME=str(runtime/'home'), TMPDIR=str(runtime/'tmp'),
                TEMP=str(runtime/'tmp'), TMP=str(runtime/'tmp'), XDG_CACHE_HOME=str(runtime/'cache'),
                ANSIBLE_HOME=str(runtime/'home/.ansible'), ANSIBLE_LOCAL_TEMP=str(runtime/'ansible-local'),
                ANSIBLE_SSH_CONTROL_PATH_DIR=str(runtime/'ansible-control'),
                # The inherited ansible.cfg pins /tmp/ansible-*; disable socket
                # multiplexing for this finite audit rather than write there.
                ANSIBLE_SSH_CONTROL_PATH='none',
                ANSIBLE_SSH_ARGS='-C -o ControlMaster=no -o ControlPersist=no -o ControlPath=none',
                PYTHONDONTWRITEBYTECODE='1')


class SourcePreflightRefused(Exception):
    """Carries only an allowlisted public relative filename and fixed code."""


def phase_source_preflight(repo, dest):
    # Pure local source check before reading credential stdin or starting any
    # subprocess. Keep a public-only F receipt even when outer Ansible no_log
    # censors its command result. Never overwrite an earlier failed attempt.
    required = {
        'scripts/migration/export-bortus-cached-runtime.py':
            '123fefe74afa045c04d5b69d675271b7e8d842dde2444a088007eb47a542790f',
        'k8s-rewrite/ansible-playbook/playbooks/bortus-cached-runtime-audit.yml':
            '87e74963180701c2cbc841a8c0b5a33a0fabfaa76bd58c6359f4929333edb644',
    }
    for relative, expected in required.items():
        candidate = repo/relative
        code = None
        try:
            if not candidate.is_file() or candidate.is_symlink():
                code = 'required_source_missing_or_not_regular'
            elif sha(candidate) != expected:
                code = 'required_source_sha256_mismatch'
        except OSError:
            code = 'required_source_unreadable'
        if code:
            approved_mount()
            directory(ROOT)
            directory(ROOT/'attempts')
            directory(dest)
            public = {'status':'refused', 'code':code, 'file':relative}
            save(dest/'source-preflight-refusal.json', public)
            raise SourcePreflightRefused(json.dumps(public))


RPC_BOOTSTRAP = r"""import multiprocessing, os, runpy, stat, sys
from pathlib import Path
root = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
rpc = Path(os.environ['BORTUS_AUDIT_RPC_TEMP'])
info = rpc.lstat()
assert root.is_mount() and rpc.parent == root and rpc.resolve() == rpc
assert stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() == 1000
assert stat.S_IMODE(info.st_mode) == 0o700 and info.st_dev == root.stat().st_dev
assert len(os.fsencode(str(rpc / 'listener-12345678'))) <= 107
assert not any(rpc.iterdir())
# Installed CPython get_temp_dir honors this process-local value. Preseeding
# avoids its extra pymp-XXXXXXXX component without patching Ansible/stdlib.
multiprocessing.current_process()._config['tempdir'] = str(rpc)
cli = '/home/brajam/.local/share/branconet-migration/venv/bin/ansible-playbook'
sys.argv = [cli, *sys.argv[1:]]
runpy.run_path(cli, run_name='__main__')
"""


def rpc_tempdir(dest, phase):
    approved_mount()
    # Eight-character direct-child name leaves exactly 107 bytes for the
    # installed stdlib's listener-XXXXXXXX socket, including the full F root.
    rpc = FBASE/('r'+uuid.uuid4().hex[:7])
    rpc.mkdir(mode=0o700)  # exclusive; never reuse a failed attempt's directory
    info = rpc.lstat()
    need(rpc.resolve() == rpc and rpc.parent == FBASE and stat.S_ISDIR(info.st_mode)
         and info.st_uid == 1000 and stat.S_IMODE(info.st_mode) == 0o700
         and info.st_dev == FBASE.stat().st_dev, 'exclusive_native_F_RPC_directory')
    need(len(os.fsencode(str(rpc/'listener-12345678'))) <= 107, 'RPC_UNIX_socket_path_bound')
    save(dest/('controller-'+phase)/'rpc-path.json', {'path':str(rpc)})
    return rpc


def live_guard():
    # kubectl output and any nonselected fields remain only in master process RAM.
    code = '''import subprocess,json
p=json.loads(subprocess.check_output(['kubectl','-n','bortus','get','pod','bortus-5c55f6d5b5-h9z6t','-o','json'],stderr=subprocess.DEVNULL))
c=next(x for x in p['spec']['containers'] if x['name']=='bortus')
s=next(x for x in p['status']['containerStatuses'] if x['name']=='bortus')
print(json.dumps({'podUID':p['metadata']['uid'],'node':p['spec']['nodeName'],'image':c['image'],'imageID':s['imageID'],'ready':s['ready']}))
'''
    r = subprocess.run(SSH+['james@192.168.0.4', 'python3 -I -B -'], input=code,
                       capture_output=True, text=True, timeout=30)
    need(r.returncode == 0, 'master_live_metadata')
    data = json.loads(r.stdout)
    need(data == {'podUID':POD_UID, 'node':'workernode2', 'image':REF, 'imageID':REF, 'ready':True},
         'exact_original_running_identity')
    return data


def remote_receipt(attempt, phase):
    path = REMOTE+'/attempts/'+attempt+'/'+phase+'.json'
    r = subprocess.run(SSH+['james@192.168.0.5', 'cat '+path], capture_output=True, timeout=30)
    need(r.returncode == 0 and len(r.stdout) <= 1024**2, 'remote_receipt_available')
    return json.loads(r.stdout), r.stdout


def run_remote(a, dest, repo, request):
    phase = a.phase
    before = live_guard()
    capacity = launch_capacity(0 if phase == 'probe' else a.estimated_bytes)
    if phase == 'export':
        previous = dest/'probe.json'
        need(re.fullmatch('[0-9a-f]{64}', a.probe_sha256) and sha(previous) == a.probe_sha256, 'reviewed_probe_hash')
        probe = json.loads(previous.read_text())
        need(probe['coverage'] == 'complete_cached_root_closure_verified_not_scanned', 'complete_cache_probe')
        need(a.estimated_bytes == probe['closure']['projectedArchiveBytes'] and a.estimated_bytes <= 2*GIB, 'exact_projected_bytes')
    else:
        need(not (dest/'probe.json').exists(), 'new_probe_only')
    ansible = repo/'k8s-rewrite/ansible-playbook'
    env = dict(controller_env(dest, phase), ANSIBLE_CONFIG=str(ansible/'ansible.cfg'), ANSIBLE_NOCOLOR='1')
    env['BRANCONET_MIGRATION_SUDO_PASSWORD'] = request.pop('sudo_password')
    raw = None
    variables = {'bortus_cache_apply':True, 'bortus_cache_phase':phase, 'bortus_cache_attempt':a.attempt,
                 'bortus_cache_probe_sha256':a.probe_sha256}
    rpc = rpc_tempdir(dest, phase)
    env['BORTUS_AUDIT_RPC_TEMP'] = str(rpc)
    command = [str(BASE/'venv/bin/python'), '-B', '-c', RPC_BOOTSTRAP,
               'playbooks/bortus-cached-runtime-audit.yml', '--limit', 'workernode2',
               '--extra-vars', json.dumps(variables)]
    log = dest/(phase+'.operator.log')
    record = {'sourceKind':'existing-node-containerd-runtime-cache', 'phase':phase, 'image':REF,
              'before':before, 'capacity':capacity, 'coverage':'unknown', 'controllerSHA256':sha(Path(__file__)),
              'rpcTempDirectory':str(rpc), 'rpcSocketPathMaximumBytes':107,
              'readerSHA256':sha(repo/'scripts/migration/export-bortus-cached-runtime.py'),
              'playbookSHA256':sha(ansible/'playbooks/bortus-cached-runtime-audit.yml')}
    try:
        with log.open('xb') as out:
            child = subprocess.Popen(command, cwd=ansible, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=out)
            env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
            record['ansiblePID'] = child.pid
            record['exitCode'] = child.wait(timeout=1020)
        audit_reserve()
        receipt, receipt_raw = remote_receipt(a.attempt, phase)
        need(receipt['helperSHA256'] == record['readerSHA256'] and receipt['image'] == REF and receipt['attempt'] == a.attempt,
             'node_source_and_scope')
        with (dest/(phase+'.json')).open('xb') as f:
            f.write(receipt_raw)
        record['remoteReceiptSHA256'] = sha(dest/(phase+'.json'))
        record['after'] = live_guard()
        need(record['exitCode'] == 0, 'node_phase_failed_receipt_retained')
        if phase == 'export':
            need(receipt['coverage'] == 'complete_cached_root_closure_exported_not_scanned', 'complete_export')
            launch_capacity(receipt['archiveBytes'])
            archive = dest/'runtime.oci.tar'
            need(not archive.exists(), 'new_controller_archive')
            # Stream only this exact root-owned export; no SFTP tree traversal or slurp double-copy.
            with archive.open('xb') as f:
                p = subprocess.run(SSH+['james@192.168.0.5', 'cat '+REMOTE+'/attempts/'+a.attempt+'/runtime.oci.tar'],
                                   stdout=f, stderr=subprocess.DEVNULL, timeout=600)
            need(p.returncode == 0 and archive.stat().st_size == receipt['archiveBytes'] and
                 sha(archive) == receipt['archiveSHA256'], 'transport_archive_identity')
            archive.chmod(0o400)
            record['afterTransfer'] = live_guard()
        record['coverage'] = receipt['coverage']
    finally:
        env.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
        save(dest/(phase+'.controller.json'), record)
    print(json.dumps({'attempt':a.attempt, 'phase':phase, 'receipt':str(dest/(phase+'.json')),
                      'receiptSHA256':record['remoteReceiptSHA256'], 'coverage':record['coverage']}))


def dependency():
    need(DEPENDENCY.resolve() == DEPENDENCY and sha(DEPENDENCY) == DEPENDENCY_SHA, 'exact_existing_scanner_primitives')
    spec = importlib.util.spec_from_file_location('cached_runtime_primitives', DEPENDENCY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scan_worker(a, dest):
    m = dependency()
    work = SCAN_WORK/('bortus-cached-'+a.attempt)
    audit_reserve(launch=True)
    work.mkdir(mode=0o700)
    record = {'sourceKind':'existing-node-containerd-runtime-cache', 'image':REF, 'coverage':'unknown',
              'helperSHA256':sha(Path(__file__)), 'primitivesSHA256':DEPENDENCY_SHA,
              'exportReceiptSHA256':a.receipt_sha256, 'archiveSHA256':a.archive_sha256,
              'storagePolicy':STORAGE_POLICY}
    child = None
    lock = None
    try:
        need(SCAN_LOCK.resolve() == SCAN_LOCK and stat.S_ISREG(SCAN_LOCK.lstat().st_mode)
             and SCAN_LOCK.stat().st_uid == 1000 and stat.S_IMODE(SCAN_LOCK.stat().st_mode) == 0o600, 'F_scan_lock_identity')
        lock = SCAN_LOCK.open('r+')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        record['limits'] = m.limits('branconet-bortus-cached-scan-'+a.attempt+'.service')
        record['inputs'] = m.inputs()
        need(0 <= m.age_hours(record['inputs']['vulnerabilityDB']) <= 24, 'fresh_core_DB_max24hours')
        java_next = datetime.datetime.fromisoformat(record['inputs']['javaDB']['NextUpdate'].replace('Z', '+00:00'))
        need(0 <= m.age_hours(record['inputs']['javaDB']) and datetime.datetime.now(datetime.timezone.utc) < java_next,
             'pinned_Java_DB_not_past_its_declared_update_window')
        receipt_path, archive = dest/'export.json', dest/'runtime.oci.tar'
        need(sha(receipt_path) == a.receipt_sha256, 'export_receipt_pin')
        receipt = json.loads(receipt_path.read_text())
        need(receipt['coverage'] == 'complete_cached_root_closure_exported_not_scanned' and receipt['image'] == REF,
             'cached_runtime_source_provenance')
        need(receipt['archiveSHA256'] == a.archive_sha256 and archive.stat().st_size == receipt['archiveBytes'] <= 2*GIB
             and sha(archive) == a.archive_sha256, 'archive_pin')
        initial_archive = archive.stat()
        record['capacity'] = audit_reserve(archive.stat().st_size*2)
        record['runtimeIdentity'] = m.selected_layout(archive, DIGEST, work/'selected-oci')
        audit_reserve()
        for process in Path('/proc').iterdir():
            if process.name.isdigit():
                try:
                    need((process/'comm').read_text().strip() != 'trivy', 'another_scanner_is_running')
                except (FileNotFoundError, ProcessLookupError):
                    pass
        for name in ['tmp', 'home', 'cache', 'docker-config']:
            (work/name).mkdir(mode=0o700)
        (work/'cache/db').symlink_to(CROOT/'cache/db', target_is_directory=True)
        (work/'cache/java-db').symlink_to(CROOT/'cache/java-db', target_is_directory=True)
        (work/'docker-config/config.json').write_text('{"auths":{}}\n')
        env = {'PATH':'/usr/bin:/bin', 'LANG':'C', 'LC_ALL':'C', 'GOMAXPROCS':'2', 'GOMEMLIMIT':'512MiB',
               'HOME':str(work/'home'), 'TMPDIR':str(work/'tmp'), 'TEMP':str(work/'tmp'), 'TMP':str(work/'tmp'),
               'DOCKER_CONFIG':str(work/'docker-config'),
               'XDG_CACHE_HOME':str(work/'cache')}
        # Results-only template omits image config/history; vuln scanner never scans secrets or executes an app.
        command = [str(CROOT/'bin/trivy'), 'image', '--input', str(work/'selected-oci'), '--platform', 'linux/amd64',
                   '--config', str(CROOT/'trivy-empty.yaml'), '--cache-dir', str(work/'cache'),
                   '--scanners', 'vuln', '--offline-scan', '--skip-db-update', '--skip-java-db-update',
                   '--ignorefile', str(CROOT/'no-ignore'), '--timeout', '7m', '--parallel', '2', '--quiet',
                   '--no-progress', '--list-all-pkgs', '--format', 'template', '--template', '@'+str(CROOT/'results.tpl'),
                   '--output', str(work/'results.json')]
        started = time.monotonic()
        with (work/'stderr.log').open('xb') as err:
            child = subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=err, start_new_session=True)
            while child.poll() is None:
                need(time.monotonic()-started < 480, 'scanner_wall_timeout')
                audit_reserve()
                for path, cap in [(work/'results.json',64*1024**2), (work/'stderr.log',16*1024**2)]:
                    need(not path.exists() or path.stat().st_size <= cap, 'bounded_report')
                time.sleep(2)
        need(child.returncode == 0, 'scanner_failed_no_raw_diagnostics')
        result_path = work/'results.json'
        need(result_path.stat().st_size <= 64*1024**2, 'final_report_size')
        results = json.loads(result_path.read_text())
        need(isinstance(results, list) and 0 < len(results) <= 65536, 'nonempty_component_coverage_and_result_items')
        counts = collections.Counter()
        rows = 0
        for target in results:
            need(not target.get('Secrets') and not target.get('Misconfigurations'), 'scanner_scope')
            findings = target.get('Vulnerabilities') or []
            rows += len(findings)
            need(rows <= 250000, 'finding_items')
            counts.update(x['Severity'] for x in findings)
        need(m.inputs() == record['inputs'], 'immutable_inputs_after_scan')
        final_archive = archive.stat()
        need((initial_archive.st_ino, initial_archive.st_size, initial_archive.st_mtime_ns) ==
             (final_archive.st_ino, final_archive.st_size, final_archive.st_mtime_ns) and
             sha(receipt_path) == a.receipt_sha256, 'source_identity_after_scan')
        record['limitsAfter'] = m.limits('branconet-bortus-cached-scan-'+a.attempt+'.service')
        audit_reserve()
        record.update(coverage='scanned_exact_cached_linux_amd64_runtime', severityCounts=dict(counts),
                      resultsSHA256=sha(result_path), results=str(result_path), securityAcceptance=False)
    except Exception as error:
        record['failureCategory'] = str(error) if isinstance(error, ValueError) else type(error).__name__
    finally:
        if child and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        if lock:
            lock.close()
        save(work/'status.json', record)
    return 0 if record['coverage'] == 'scanned_exact_cached_linux_amd64_runtime' else 1


def launch_scan(a, dest):
    need(re.fullmatch('[0-9a-f]{64}', a.receipt_sha256) and re.fullmatch('[0-9a-f]{64}', a.archive_sha256), 'reviewed_archive_and_receipt_pins')
    capacity = launch_capacity(0, scan=True)
    before = live_guard()
    need(not (SCAN_WORK/('bortus-cached-'+a.attempt)).exists(), 'exclusive_scan_attempt')
    directory(SCAN_WORK)
    if not SCAN_LOCK.exists():
        with SCAN_LOCK.open('x'):
            pass
        SCAN_LOCK.chmod(0o600)
    need(SCAN_LOCK.resolve() == SCAN_LOCK and stat.S_ISREG(SCAN_LOCK.lstat().st_mode)
         and SCAN_LOCK.stat().st_uid == 1000 and stat.S_IMODE(SCAN_LOCK.stat().st_mode) == 0o600, 'F_scan_lock_identity')
    unit_log = dest/'scan.unit.log'
    with unit_log.open('x'):
        pass
    unit_log.chmod(0o600)
    source_sha = sha(Path(__file__))
    frozen_dir = ROOT/'helpers'/source_sha
    directory(frozen_dir)
    frozen = frozen_dir/'audit.py'
    if not frozen.exists():
        with frozen.open('xb') as f:
            f.write(Path(__file__).read_bytes())
        frozen.chmod(0o500)
    need(sha(frozen) == source_sha, 'frozen_source')
    unit = 'branconet-bortus-cached-scan-'+a.attempt+'.service'
    props = ['Type=exec', 'MemoryMax=1073741824', 'MemorySwapMax=0', 'CPUQuota=200%', 'TasksMax=128',
             'Nice=10', 'UMask=0077', 'RuntimeMaxSec=900', 'TimeoutStopSec=30', 'KillMode=control-group',
             'LimitFSIZE=4294967296', 'PrivateUsers=yes', 'PrivateNetwork=yes', 'PrivateDevices=yes',
             'NoNewPrivileges=yes', 'ProtectSystem=strict', 'ProtectHome=read-only', 'ProtectKernelTunables=yes',
             'ProtectKernelModules=yes', 'ProtectControlGroups=yes',
             'ReadWritePaths='+str(SCAN_WORK)+' '+str(SCAN_LOCK)+' '+str(unit_log),
             'ReadOnlyPaths='+str(ROOT)+' '+str(CROOT),
             'NoExecPaths='+str(SCAN_WORK)+' '+str(CROOT/'cache'),
             'InaccessiblePaths=-/home/brajam/.ssh -/root -/mnt/c/Users -/run/docker.sock -/run/containerd -/run/containerd-k8s /tmp /var/tmp',
             'StandardOutput=append:'+str(dest/'scan.unit.log'), 'StandardError=append:'+str(dest/'scan.unit.log')]
    command = ['systemd-run', '--user', '--unit='+unit]+['--property='+x for x in props]
    command += ['--', '/usr/bin/env', '-i', 'PATH=/usr/bin:/bin', 'LANG=C', 'LC_ALL=C', 'GOMAXPROCS=2', 'GOMEMLIMIT=512MiB',
                'XDG_RUNTIME_DIR=/run/user/1000', 'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus',
                'HOME='+str(SCAN_WORK/('bortus-cached-'+a.attempt)/'home'),
                'TMPDIR='+str(SCAN_WORK/('bortus-cached-'+a.attempt)/'tmp'),
                'TEMP='+str(SCAN_WORK/('bortus-cached-'+a.attempt)/'tmp'),
                'TMP='+str(SCAN_WORK/('bortus-cached-'+a.attempt)/'tmp'),
                'XDG_CACHE_HOME='+str(SCAN_WORK/('bortus-cached-'+a.attempt)/'cache'),
                '/usr/bin/python3', '-I', '-B', str(frozen), '--phase', 'scan-worker', '--apply', '--attempt', a.attempt,
                '--receipt-sha256', a.receipt_sha256, '--archive-sha256', a.archive_sha256]
    r = subprocess.run(command, env=controller_env(dest, 'scan-launch'), capture_output=True, timeout=20)
    record = {'unit':unit, 'startExitCode':r.returncode, 'helperSHA256':source_sha, 'capacity':capacity, 'before':before,
              'archiveSHA256':a.archive_sha256, 'exportReceiptSHA256':a.receipt_sha256, 'coverage':'unknown_until_status'}
    save(dest/'scan.launch.json', record)
    print(json.dumps(record))
    return r.returncode


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', choices=['probe', 'export', 'scan', 'status', 'scan-worker'], required=True)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--attempt', required=True)
    p.add_argument('--probe-sha256', default='')
    p.add_argument('--estimated-bytes', type=int, default=0)
    p.add_argument('--receipt-sha256', default='')
    p.add_argument('--archive-sha256', default='')
    a = p.parse_args()
    os.umask(0o077)
    need(os.getuid() == 1000 and re.fullmatch('[0-9a-f]{12}', a.attempt), 'fixed_native_operator_attempt')
    dest = ROOT/'attempts'/a.attempt
    if a.phase == 'status':
        status = SCAN_WORK/('bortus-cached-'+a.attempt)/'status.json'
        need(status.is_file(), 'scan_status_not_yet_available')
        data = json.loads(status.read_text())
        data['currentLiveIdentity'] = live_guard()
        print(json.dumps(data))
        return 0
    need(a.apply, 'explicit_apply_required')
    if a.phase == 'scan-worker':
        return scan_worker(a, dest)
    request = None
    if a.phase in ['probe', 'export']:
        phase_source_preflight(Path(__file__).resolve().parents[2], dest)
        raw = sys.stdin.buffer.read(65537)
        need(len(raw) <= 65536, 'bounded_password_stdin')
        request = json.loads(raw)
        raw = None
        need(set(request) == {'sudo_password'} and isinstance(request['sudo_password'], str) and request['sudo_password'], 'stdin_contract')
    launch_capacity(0)
    directory(ROOT)
    directory(ROOT/'attempts')
    directory(dest)
    # All subsequent controller subprocesses inherit explicit F scratch paths.
    os.environ.update(controller_env(dest, a.phase))
    if a.phase in ['probe', 'export']:
        repo = Path(__file__).resolve().parents[2]
        return run_remote(a, dest, repo, request)
    return launch_scan(a, dest)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SourcePreflightRefused as error:
        raise SystemExit(str(error))
    except Exception:
        raise SystemExit('Cached-runtime audit refused; retain all receipts. No raw credential or image-config diagnostics emitted.')
