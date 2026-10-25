#!/usr/bin/env python3
"""Finite Ruckus5.7.44 HA recovery. Resource changes remain operator/Flux owned.

Plans are inert. Runtime phases require stdin HMAC key and hash-bound receipts.
Only the explicit restore phase writes data, solely through the new subPath.
"""
import argparse
import datetime
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import stat
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FBASE = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = FBASE / 'ruckus-ha-recovery-20261025'
CHILD = 'security-data-20261025'
OLD = 'ruckus-db-data-0'
CURRENT = 'ruckus-db-data-0-security-20261025'
MAX_DATA = 384 * 1024**2
GUEST_RESERVE = 256 * 1024**2
PINS = {
    'scripts/migration/archive-ruckusdb-qualified-copy.py': 'b656020f87eb36a32cc194a25052ef8d42047cdb4585e29616779bd513e05c7f',
    'scripts/migration/qualify-ruckusdb-copies.py': '74bb2fc2feaf400d211dfc62410c3846c43f3e46f69b06ba8ddff42c3686749c',
    'k8s-rewrite/ansible-playbook/roles/metube_state_backup/files/metube_state_backup.py': '3f78c704a0b6e13b86c233aa79d00b09b8ef4f4937fcc9208427f9442ef8ff1d',
    'k8s-rewrite/ansible-playbook/roles/metube_state_backup/files/pod_reader.py': 'e01e156492af261f3e8abe9f1ccca4e3ab1ac1d24eacda092fbd17b4ee10cb54',
}
HISTORICAL = FBASE / 'ruckus-cold-20261025/ruckus-db-cold-15c183ff106b46048a1f77c17ae0e266/receipt.json'
HISTORICAL_SHA = '67b4e67f6c89fac850b2581ee871cc812dff37602943b36f8ab72b560c82dd74'
INSPECTION = FBASE / 'ruckus-original-ro-inspection-20261025/560ef15e180b/original-readonly-inventory.json'
INSPECTION_SHA = '09cbd79d10a3553226ad6ae90f4a618ad60eb89f34f3ff7982dabd72c5ebcfff'
REATTACHED_INSPECTION = FBASE / 'ruckus-ha-operations-20261025/original-cold-actual-inventory.json'
REATTACHED_SHA = 'e3d7f0b1369a7c91694ef0e8142509a1aa892d78be977e50415183acb571559b'


def need(ok, code):
    if not ok:
        raise RuntimeError(code)


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def check_sources():
    for path, expected in PINS.items():
        need(digest(ROOT / path) == expected, 'pinned_dependency_source')
    files = [HERE / 'ruckus-ha-recovery.py', HERE / 'ruckus-ha-recovery-remote.py']
    return {p.name: digest(p) for p in files}


def private(path, existing=True):
    need(path.is_absolute() and path.resolve() == path and path.is_relative_to(OUT), 'exact_f_output_path')
    if existing:
        s = path.lstat(); need(s.st_uid == os.getuid() and not s.st_mode & 0o077 and not path.is_symlink(), 'private_owned_path')


def save(path, value):
    private(path, False)
    with path.open('x') as f:
        json.dump(value, f, sort_keys=True, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())


def capacity(launch=False, pending=0):
    need(FBASE.is_mount() and FBASE.resolve() == FBASE, 'approved_f_mount')
    # Mount identity is checked before creating any task directory/subprocess.
    mounts = [line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines()]
    rows = [row for row in mounts if row[4] == str(FBASE)]
    need(len(rows) == 1 and rows[0][rows[0].index('-') + 1] == 'ext4', 'native_ext4_mount')
    backing = Path('/mnt/f/branconet-build-storage/native-build-20261025.ext4')
    need(backing.stat().st_ino == 115123265474727363 and backing.stat().st_size == 144 * 1024**3, 'same_144GiB_backing_inode')
    loop = Path('/sys/dev/block') / rows[0][2] / 'loop/backing_file'
    need(loop.read_text().strip() == str(backing), 'exact_task_loop_backing')
    free = os.statvfs(FBASE); native = free.f_bavail * free.f_frsize
    need(native >= 15 * 1024**3 + pending and free.f_favail >= 32768, 'native_f_reserve')
    physical = os.statvfs('/mnt/f'); need(physical.f_bavail * physical.f_frsize >= 15 * 1024**3 + pending, 'physical_f_reserve')
    if launch:
        c = os.statvfs('/mnt/c'); need(c.f_bavail * c.f_frsize >= 15 * 1024**3, 'windows_c_launch_floor')
    return {'native_free': native, 'physical_free': physical.f_bavail * physical.f_frsize}


def environment(run):
    for name in ('home', 'tmp', 'cache'):
        (run / name).mkdir(mode=0o700)
    for name, folder in [('HOME', 'home'), ('TMPDIR', 'tmp'), ('TMP', 'tmp'), ('TEMP', 'tmp'), ('XDG_CACHE_HOME', 'cache')]:
        os.environ[name] = str(run / folder)
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'


def plan(shared, mode, run_id):
    need(mode in ('cold', 'restore', 'after') and re.fullmatch('[a-f0-9]{12}', run_id), 'finite_plan')
    name = 'ruckus-ha-' + mode + '-' + run_id
    labels = {'branconet.net/ruckus-ha-recovery': name}
    mounts = [{'name': 'original', 'mountPath': '/original-ro', 'readOnly': True}]
    volumes = [{'name': 'original', 'persistentVolumeClaim': {'claimName': OLD, 'readOnly': mode != 'restore'}}]
    if mode == 'cold':
        volumes.append({'name': 'current', 'persistentVolumeClaim': {'claimName': CURRENT, 'readOnly': True}})
        mounts.append({'name': 'current', 'mountPath': '/current-ro', 'readOnly': True})
    if mode == 'restore':
        mounts.append({'name': 'original', 'mountPath': '/restore', 'subPath': CHILD})
    caps = ['DAC_OVERRIDE'] + (['CHOWN', 'FOWNER'] if mode == 'restore' else [])
    pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name, 'namespace': 'ruckus', 'labels': labels},
           'spec': {'nodeSelector': {'kubernetes.io/hostname': 'workernode2'}, 'restartPolicy': 'Never',
                    'activeDeadlineSeconds': 1800, 'automountServiceAccountToken': False, 'enableServiceLinks': False,
                    'hostNetwork': False, 'hostPID': False, 'hostIPC': False,
                    'securityContext': {'supplementalGroupsPolicy': 'Strict', 'seccompProfile': {'type': 'RuntimeDefault'}},
                    'volumes': volumes, 'containers': [{'name': 'reader', 'image': shared.OLD, 'imagePullPolicy': 'Never',
                    'command': ['python3', '-B', '-c', 'import time;time.sleep(1800)'],
                    'securityContext': {'runAsUser': 0, 'runAsGroup': 0, 'allowPrivilegeEscalation': False,
                                        'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL'], 'add': caps}},
                    'resources': {'requests': {'cpu': '25m', 'memory': '32Mi'}, 'limits': {'cpu': '500m', 'memory': '512Mi'}},
                    'volumeMounts': mounts}]}}
    policy = {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
              'metadata': {'name': name, 'namespace': 'ruckus', 'labels': labels},
              'spec': {'podSelector': {'matchLabels': labels}, 'policyTypes': ['Ingress', 'Egress'], 'ingress': [], 'egress': []}}
    return {'apiVersion': 'v1', 'kind': 'List', 'items': [policy, pod]}


def reader_command(reader, program):
    return ['kubectl', '-n', 'ruckus', 'exec', '-i', reader['plan']['items'][1]['metadata']['name'], '-c', 'reader', '--', 'python3', '-B', '-c', program]


def reader_source(archiver, root, exclude=False):
    need(root in ('/original-ro', '/current-ro', '/restore'), 'finite_reader_root')
    source = "__name__='ha_reader'\n" + (archiver.SHARED / 'pod_reader.py').read_text()
    source += '\nROOTS=' + repr({'data-0': root}) + '\nMAX_BYTES=384*1024**2\n'
    source += 'EXCLUDED=' + repr({'data-0/' + CHILD} if exclude else set()) + '\n'
    return source


def inventory(archiver, shared, reader, root, exclude=False):
    source = reader_source(archiver, root, exclude)
    source += "\nassert os.statvfs('/original-ro').f_flag & os.ST_RDONLY\n"
    if root == '/current-ro':
        source += "assert os.statvfs('/current-ro').f_flag & os.ST_RDONLY\n"
    if exclude:
        source += "p=pathlib.Path('/original-ro/security-data-20261025');assert p.is_dir() and not p.is_symlink()\n"
    source += 'print(json.dumps(inventory(' + repr(exclude) + '),sort_keys=True))\n'
    return json.loads(archiver.remote(shared, reader_command(reader, source)))


def sibling_identity(archiver, shared, reader):
    program = """import json,os,pathlib,stat
p=pathlib.Path('/original-ro/security-data-20261025');assert p.is_dir() and not p.is_symlink()
s=p.stat();assert os.statvfs('/original-ro').f_flag & os.ST_RDONLY
print(json.dumps({'inode':s.st_ino,'mode':stat.S_IMODE(s.st_mode),'uid':s.st_uid,'gid':s.st_gid,'mtime_ns':s.st_mtime_ns}))
"""
    return json.loads(archiver.remote(shared, reader_command(reader, program)))


def wait_encrypted(writer, producer, cipher):
    deadline = time.monotonic() + 600
    try:
        while writer.poll() is None:
            capacity(pending=1024**2)
            need(cipher.stat().st_size <= MAX_DATA + 16 * 1024**2, 'cipher_size_bound')
            need(time.monotonic() < deadline, 'archive_deadline')
            time.sleep(0.2)
        need(writer.returncode == 0 and producer.wait(timeout=30) == 0, 'cold_stream_complete')
    finally:
        # Only processes created by this call, never a service/app/reader Pod.
        for child in (writer, producer):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait(timeout=10)


def portable(manifest):
    return dict(manifest, entries={n: {k: v for k, v in row.items() if k != 'fingerprint'} for n, row in manifest['entries'].items()})


def original_equal(before, after, child_allowed):
    # Preserve inode/ctime/size as well as the explicit full-file metadata.
    # Device numbers can change when CSI reattaches; only the filesystem root's
    # mtime/ctime/directory-size can change through adding the one sibling.
    need(not before['excluded_new_paths'], 'fresh_original_complete')
    wanted = ['data-0/' + CHILD] if child_allowed else []
    need(sorted(after['excluded_new_paths']) == wanted, 'only_owned_sibling_excluded')
    need(set(before['entries']) == set(after['entries']), 'no_old_path_added_or_lost')
    for name, row in before['entries'].items():
        a, b = dict(row), dict(after['entries'][name])
        af, bf = a.pop('fingerprint'), b.pop('fingerprint')
        if child_allowed and name == 'data-0':
            a.pop('mtime_ns'); b.pop('mtime_ns')
            need(af[1] == bf[1], 'original_root_inode')
        else:
            need(af[1:] == bf[1:], 'old_inode_size_mtime_ctime')
        need(a == b, 'old_file_bytes_mode_owner_link')
    need(before['total_file_bytes'] == after['total_file_bytes'], 'old_total_bytes')


def target_gate(archiver, shared, reader, bytes_needed):
    program = """import json,os,pathlib,stat
a=pathlib.Path('/original-ro');b=a/'security-data-20261025';r=pathlib.Path('/restore')
assert os.statvfs(a).f_flag & os.ST_RDONLY
assert not os.statvfs(r).f_flag & os.ST_RDONLY
assert b.is_dir() and not b.is_symlink() and r.is_dir() and not r.is_symlink()
s=b.stat();t=r.stat();assert(s.st_dev,s.st_ino)==(t.st_dev,t.st_ino)
assert not list(r.iterdir())
v=os.statvfs(r);free=v.f_bavail*v.f_frsize
assert free >= """ + str(bytes_needed + GUEST_RESERVE) + """
assert v.f_favail >= 8192
print(json.dumps({'target_inode':s.st_ino,'target_dev':s.st_dev,'target_uid':s.st_uid,'target_gid':s.st_gid,'target_mode':stat.S_IMODE(s.st_mode),'guest_free_before':free}))
"""
    return json.loads(archiver.remote(shared, reader_command(reader, program)))


def restore_program(copies, gate, bytes_needed):
    source = copies.RESTORE
    replacements = {
        "expected=sys.stdin.buffer.readline().decode().strip();side=sys.argv[1];assert side in ['old','new']":
        "expected=sys.stdin.buffer.readline().decode().strip();side='ha-original-new-sibling'",
        "root=pathlib.Path('/copies')/side;assert root.is_dir() and not root.is_symlink() and not list(root.iterdir())":
        "root=pathlib.Path('/restore');assert root.is_dir() and not root.is_symlink() and not list(root.iterdir())\n"
        "s=root.stat();assert(s.st_dev,s.st_ino)==" + repr((gate['target_dev'], gate['target_inode'])) + "\n"
        "assert os.statvfs('/original-ro').f_flag & os.ST_RDONLY\n"
        "v=os.statvfs(root);assert v.f_bavail*v.f_frsize>=" + str(bytes_needed + GUEST_RESERVE),
        "fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);h=hashlib.sha256();count=0":
        "v=os.statvfs(root);assert v.f_bavail*v.f_frsize >= m.size+" + str(GUEST_RESERVE) + "\n   "
        "fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);h=hashlib.sha256();count=0",
        "target=root/name;assert target.parent.resolve().is_relative_to(root.resolve())":
        "target=root/pathlib.PurePosixPath(name).relative_to('data-0');assert target==root or target.parent.resolve().is_relative_to(root.resolve())",
        "assert m.isdir();target.mkdir(mode=0o700);dirs.append((target,row))":
        "assert m.isdir()\n   if target!=root:target.mkdir(mode=0o700)\n   dirs.append((target,row))",
        "socket_link=name=='data-0/mysql.sock' and m.linkname=='/var/run/mysqld/mysqld.sock'":
        "socket_link=name=='data-0/data-0/mysql.sock' and m.linkname=='/var/run/mysqld/mysqld.sock'",
    }
    for old, new in replacements.items():
        need(source.count(old) == 1, 'exact_restore_preimage'); source = source.replace(old, new)
    return source


def historical_original(archiver, shared, original):
    """Authenticate the old complete archive and bind precisely the observed drift."""
    need(digest(HISTORICAL) == HISTORICAL_SHA and digest(INSPECTION) == INSPECTION_SHA, 'historical_receipts_pinned')
    receipt = json.loads(HISTORICAL.read_bytes())
    need(receipt['status'] == 'completed' and receipt['cold_archive_verified'] and receipt['temporary_pod_deleted'], 'historical_cold_complete')
    cipher = Path(receipt['archive_path'])
    need(cipher.resolve() == cipher and cipher.is_relative_to(FBASE) and digest(cipher) == receipt['archive_sha256'], 'historical_cipher_retained')
    historical = archiver.decrypt(shared, cipher)
    need(hashlib.sha256(shared.canonical(historical)).hexdigest() == receipt['manifest_sha256'], 'historical_manifest')
    inspected = json.loads(INSPECTION.read_bytes())['manifest']
    a, b = portable(historical), portable(inspected)
    need(a['entries']['data-0']['mtime_ns'] == 1792938130383078658 and b['entries']['data-0']['mtime_ns'] == 1792950954781991637, 'exact_recorded_historical_root_drift')
    a['entries']['data-0']['mtime_ns'] = b['entries']['data-0']['mtime_ns']
    need(a == b, 'historical_only_recorded_root_mtime_difference')
    # This second RO attachment changed only the root's mtime/ctime. Preserve
    # the separately recorded observation, without claiming its cause. Every
    # descendant and every other root identity/metadata field remains exact.
    need(digest(REATTACHED_INSPECTION) == REATTACHED_SHA, 'reattached_inspection_pin')
    reattached = json.loads(REATTACHED_INSPECTION.read_bytes())
    expected = json.loads(json.dumps(inspected))
    expected['entries']['data-0']['mtime_ns'] = 1792952912251269525
    expected['entries']['data-0']['fingerprint'][3:] = [1792952912251269525, 1792952912251269525]
    original_equal(expected, reattached, False)
    original_equal(reattached, original, False)
    return {'receipt_sha256': HISTORICAL_SHA, 'cipher_sha256': receipt['archive_sha256'], 'inspection_sha256': INSPECTION_SHA,
            'reattached_inspection_sha256': REATTACHED_SHA,
            'historical_root_mtime_ns': 1792938130383078658, 'fresh_root_mtime_ns': original['entries']['data-0']['mtime_ns']}


def read_proof(path, expected, key, sources):
    private(path); need(re.fullmatch('[a-f0-9]{64}', expected or '') and digest(path) == expected, 'proof_sha')
    value = json.loads(path.read_bytes()); signature = value.pop('receipt_hmac')
    need(hmac.compare_digest(signature, hmac.new(key, b'ruckus-ha-receipt\0' + canonical(value), hashlib.sha256).hexdigest()), 'proof_hmac')
    # One authenticated baseline predates reader API-default normalization and
    # the pinned RO root-timestamp observation. Baseline has no reader/policy
    # branch; its normal-auth SQL and identity code is byte-for-byte unchanged.
    # Preserve that exact receipt/HMAC rather than restarting a quiesced DB.
    original_baseline = (
        expected == '63ced125ab7f5e61c88f9df3d1d2cbf3af8244c48a5a19a6d662640e9bc1f345'
        and value['phase'] == 'baseline'
        and value['sources'] == {
            'ruckus-ha-recovery.py': 'e858765cafd86aee725409155ea45372cd526eaaf78c2d1b090d8ab7ad50c0d6',
            'ruckus-ha-recovery-remote.py': '2becdcfa8d707bff89c42f48ebbb1c8d564d8f3e90347474312ea814f3c5925b',
        }
    )
    need(value['status'] == 'passed' and (value['sources'] == sources or original_baseline), 'passed_same_source_proof')
    return value


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('phase', choices=['baseline', 'plan-cold', 'cold', 'plan-restore', 'restore', 'plan-after', 'after', 'restart'])
    ap.add_argument('--baseline', type=Path); ap.add_argument('--baseline-sha256')
    ap.add_argument('--cold', type=Path); ap.add_argument('--cold-sha256')
    ap.add_argument('--restored', type=Path); ap.add_argument('--restored-sha256')
    ap.add_argument('--previous', type=Path); ap.add_argument('--previous-sha256')
    ap.add_argument('--reader-run-id'); ap.add_argument('--reader-pod-uid'); ap.add_argument('--reader-policy-uid')
    ap.add_argument('--execute-new-sibling-restore', action='store_true')
    a = ap.parse_args(); resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); os.umask(0o077); sys.dont_write_bytecode = True
    sources = check_sources(); capacity(launch=True, pending=1024**3)
    OUT.mkdir(mode=0o700, exist_ok=True); private(OUT)
    run = OUT / (a.phase + '-' + uuid.uuid4().hex); run.mkdir(mode=0o700); environment(run)
    key = bytes.fromhex(sys.stdin.readline().strip()); need(len(key) == 32, 'stdin_key_only')
    archiver = load_module(HERE / 'archive-ruckusdb-qualified-copy.py', 'ha_archive'); shared = archiver.load_shared()
    tool_pins = [(p, shared.protected(p, p == shared.IDENTITY)) for p in (shared.AGE, shared.IDENTITY, shared.RECIPIENT)]
    need(digest(shared.AGE) == shared.AGE_SHA256, 'age_pin')
    receipt = {'schema_version': 1, 'status': 'failed', 'phase': a.phase, 'sources': sources,
               'started_at': now(), 'contract': 'old-files-preserved-new-sibling-parent-metadata-changed', 'dependencies': PINS}
    try:
        proofs = {}
        for name in ('baseline', 'cold', 'restored', 'previous'):
            path = getattr(a, name)
            if path:
                proofs[name] = read_proof(path, getattr(a, name + '_sha256'), key, sources)
                receipt[name + '_sha256'] = digest(path)
        if a.phase != 'baseline':
            need('baseline' in proofs and proofs['baseline']['phase'] == 'baseline', 'fresh_baseline_required')
        if a.phase in ('plan-restore', 'restore', 'after', 'restart', 'plan-after'):
            need('cold' in proofs and proofs['cold']['phase'] == 'cold' and proofs['cold']['baseline_sha256'] == receipt['baseline_sha256'], 'cold_baseline_lineage')
        if a.phase in ('after', 'restart', 'plan-after'):
            need('restored' in proofs and proofs['restored']['phase'] == 'restore' and proofs['restored']['cold_sha256'] == receipt['cold_sha256'], 'restore_cold_lineage')
        if a.phase.startswith('plan-'):
            mode = a.phase[5:]; run_id = uuid.uuid4().hex[:12]
            save(run / 'plan.json', plan(shared, mode, run_id))
            receipt.update(status='passed', reader_run_id=run_id, plan_path=str(run / 'plan.json'), plan_sha256=digest(run / 'plan.json'))
        else:
            need(a.execute_new_sibling_restore == (a.phase == 'restore'), 'explicit_restore_only')
            reader = None
            if a.phase != 'baseline':
                mode = 'after' if a.phase in ('after', 'restart') else a.phase
                need(a.reader_run_id and a.reader_pod_uid and a.reader_policy_uid, 'recorded_reader_uids_required')
                reader = {'plan': plan(shared, mode, a.reader_run_id), 'pod_uid': a.reader_pod_uid, 'policy_uid': a.reader_policy_uid}
                receipt['reader'] = reader
            request = {'phase': a.phase, 'key_hex': key.hex(), 'reader': reader,
                       'baseline_identity': proofs.get('baseline', {}).get('observation', {}).get('identity')}
            remote_source = (HERE / 'ruckus-ha-recovery-remote.py').read_text()

            def guard(sql=False):
                body = dict(request, sql=sql)
                return json.loads(archiver.remote(shared, ['python3', '-B', '-c', remote_source], canonical(body)))

            before = guard(sql=a.phase in ('baseline', 'after', 'restart'))
            receipt['observation'] = before
            if a.phase == 'baseline':
                need(before['state']['administrative'] is False, 'normal_auth_only')
            elif a.phase == 'cold':
                original = inventory(archiver, shared, reader, '/original-ro')
                need('data-0/' + CHILD not in original['entries'] and not original['excluded_new_paths'], 'new_sibling_absent')
                receipt['historical_original'] = historical_original(archiver, shared, original)
                manifest = inventory(archiver, shared, reader, '/current-ro')
                need(not manifest['excluded_new_paths'] and manifest['total_file_bytes'] <= MAX_DATA, 'complete_current_scope')
                need(manifest['entries'].get('data-0/data-0', {}).get('kind') == 'directory', 'current_application_directory')
                need(guard() == before, 'prearchive_guards')
                program = reader_source(archiver, '/current-ro') + '\narchive(json.load(sys.stdin))\n'
                cipher = run / 'current-5.7.44-complete-claim.tar.age'
                producer = archiver.remote(shared, reader_command(reader, program), canonical(manifest), streaming=True)
                with cipher.open('xb') as dst:
                    encryptor = subprocess.Popen([str(shared.AGE), '-R', str(shared.RECIPIENT)], stdin=producer.stdout, stdout=dst, stderr=subprocess.DEVNULL)
                    producer.stdout.close()
                    wait_encrypted(encryptor, producer, cipher)
                    dst.flush(); os.fsync(dst.fileno())
                need(archiver.decrypt(shared, cipher) == manifest, 'full_authenticated_cold')
                need(inventory(archiver, shared, reader, '/current-ro') == manifest, 'current_cold_stable')
                original_equal(original, inventory(archiver, shared, reader, '/original-ro'), False)
                save(run / 'original.json', original); save(run / 'current.json', manifest)
                receipt.update(archive_path=str(cipher), archive_sha256=digest(cipher), manifest_path=str(run / 'current.json'),
                               manifest_sha256=digest(run / 'current.json'), original_path=str(run / 'original.json'),
                               original_sha256=digest(run / 'original.json'), fully_authenticated=True)
            else:
                cold = proofs['cold']
                for name in ('archive', 'manifest', 'original'):
                    path = Path(cold[name + '_path']); private(path); need(digest(path) == cold[name + '_sha256'], 'cold_input_' + name)
                cipher = Path(cold['archive_path']); manifest = json.loads(Path(cold['manifest_path']).read_bytes())
                original = json.loads(Path(cold['original_path']).read_bytes())
                need(archiver.decrypt(shared, cipher) == manifest, 'retained_cold_reauthenticated')
                original_equal(original, inventory(archiver, shared, reader, '/original-ro', True), True)
                if a.phase == 'restore':
                    gate = target_gate(archiver, shared, reader, manifest['total_file_bytes']); receipt['target_gate'] = gate
                    copies = load_module(HERE / 'qualify-ruckusdb-copies.py', 'ha_exact_restore')
                    program = restore_program(copies, gate, manifest['total_file_bytes'])
                    receipt['restore_program_sha256'] = hashlib.sha256(program.encode()).hexdigest()
                    need(guard() == before, 'prewrite_guards')
                    receiver = subprocess.Popen(shared.SSH + [__import__('shlex').join(reader_command(reader, program))], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    receiver.stdin.write((hashlib.sha256(shared.canonical(manifest)).hexdigest() + '\n').encode()); receiver.stdin.flush()
                    dec = subprocess.Popen([str(shared.AGE), '-d', '-i', str(shared.IDENTITY), str(cipher)], stdout=receiver.stdin, stderr=subprocess.DEVNULL)
                    receiver.stdin.close(); need(dec.wait(timeout=600) == 0, 'restore_decryption_authenticated')
                    need(receiver.wait(timeout=30) == 0, 'exclusive_restore_complete')
                    result = json.loads(receiver.stdout.read(1024**2)); need(result['restored'], 'restore_result')
                    observed = inventory(archiver, shared, reader, '/restore')
                    need(portable(observed) == portable(manifest), 'all_restored_bytes_and_metadata')
                    receipt['restore_result'] = result
                    receipt['new_sibling_identity'] = sibling_identity(archiver, shared, reader)
                    need(receipt['new_sibling_identity']['inode'] == gate['target_inode'], 'same_owned_sibling_inode')
                else:
                    need(sibling_identity(archiver, shared, reader) == proofs['restored']['new_sibling_identity'], 'same_owned_sibling_after_start')
                    need(before['state'] == proofs['baseline']['observation']['state'], 'fresh_full_sql_state_equal')
                    if a.phase == 'restart':
                        need('previous' in proofs and proofs['previous']['phase'] == 'after', 'after_receipt_required')
                        previous = proofs['previous']; need(previous['restored_sha256'] == receipt['restored_sha256'] and previous['baseline_sha256'] == receipt['baseline_sha256'], 'restart_lineage')
                        need(before['pod']['uid'] != previous['observation']['pod']['uid'], 'actual_new_pod_uid')
                        need(datetime.datetime.fromisoformat(before['pod']['created_at'].replace('Z', '+00:00')) > datetime.datetime.fromisoformat(previous['finished_at']), 'actual_restart_after_observation')
                        need(before['state'] == previous['observation']['state'], 'restart_state_preserved')
                        receipt['actual_restart_verified'] = True
                original_equal(original, inventory(archiver, shared, reader, '/original-ro', True), True)
                need(digest(cipher) == cold['archive_sha256'], 'cold_cipher_retained')
                receipt['original_old_files_preserved'] = True
            after_guard = guard()
            need({k: v for k, v in before.items() if k != 'state'} == after_guard, 'phase_guards_stable')
            receipt['status'] = 'passed'
        need(check_sources() == sources, 'source_stability')
        for path, value in tool_pins:
            need(shared.protected(path, path == shared.IDENTITY) == value, 'tool_key_identity_stable')
        capacity()
    except Exception as error:
        receipt['status'] = 'failed'
        receipt['error_code'] = str(error) if isinstance(error, RuntimeError) else type(error).__name__
    receipt['finished_at'] = now()
    receipt['receipt_hmac'] = hmac.new(key, b'ruckus-ha-receipt\0' + canonical(receipt), hashlib.sha256).hexdigest()
    save(run / 'receipt.json', receipt)
    print(json.dumps({'status': receipt['status'], 'receipt': str(run / 'receipt.json'), 'receipt_sha256': digest(run / 'receipt.json')}))
    return 0 if receipt['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
