#!/usr/bin/env python3
"""Archive only the already-qualified, stopped NEW tmpfs copy. No SQL or mutations."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[2]
BASE = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
PRIVATE = BASE / 'acceptance-ruckus-20261025'
OUTPUT = BASE / 'ruckus-upgraded-cold-20261025'
SHARED = ROOT / 'k8s-rewrite/ansible-playbook/roles/metube_state_backup/files'
OBSERVER = '/home/james/.local/share/branconet-migration/acceptance-ruckus-20261025/copy-observer-3284b56f3d7e.py'
OBSERVER_SHA = '3284b56f3d7e7f0a570d84823a3a5b3a1c8067249156450bc061af2dadda3751'
PINS = {'metube_state_backup.py': '3f78c704a0b6e13b86c233aa79d00b09b8ef4f4937fcc9208427f9442ef8ff1d',
        'pod_reader.py': 'e01e156492af261f3e8abe9f1ccca4e3ab1ac1d24eacda092fbd17b4ee10cb54'}
MAX_DATA = 384 * 1024**2
ORIGINAL = 'mysql:5.7.41@sha256:bf18020f32cc5d8f5e2add516d52fbf3afc3de431457076340e938596c528171'


def need(ok, code):
    if not ok:
        raise RuntimeError(code)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_shared():
    for name, expected in PINS.items():
        need(digest(SHARED / name) == expected, 'shared_source_pin')
    spec = importlib.util.spec_from_file_location('archive_primitives', SHARED / 'metube_state_backup.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def remote(shared, args, data=None, streaming=False):
    child = subprocess.Popen(shared.SSH + [shlex.join(args)], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if streaming:
        if data:
            child.stdin.write(data)
        child.stdin.close()
        return child
    out, _ = child.communicate(data, timeout=180)
    if child.returncode != 0:
        try:
            diagnostic = json.loads(out)
            code = diagnostic.get('guard_stage', 'unknown')
            need(isinstance(code, str) and code.replace('_', '').isalnum(), 'invalid_guard_diagnostic')
        except (ValueError, TypeError):
            code = 'unknown'
        raise RuntimeError('remote_read_guard_' + code)
    need(len(out) <= 8 * 1024**2, 'remote_read_bound')
    return out


GUARD = r'''import hashlib,importlib.util,json,sys,types
stage='input'
def filtered_error(kind,value,tb):
 print(json.dumps({'guard_stage':stage,'error_type':kind.__name__}))
sys.excepthook=filtered_error
x=json.load(sys.stdin)
stage='observer_pin'
p=x['observer'];assert hashlib.sha256(open(p,'rb').read()).hexdigest()==x['observer_sha256']
s=importlib.util.spec_from_file_location('qualified_observer',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
stage='copy_contract'
copy=m.copy_guard(types.SimpleNamespace(namespace=x['state']['namespace'],pod_uid=x['state']['pod_uid']))
stage='copy_identity'
assert copy==x['copy_identity']
stage='original_cold_contract'
live,_=m.live_guard(x['original_image'],cold=True)
stage='original_zero_status'
db=m.get('deployment','ruckus-db');assert all(db['status'].get(k,0)==0 for k in ('replicas','readyReplicas','updatedReplicas','availableReplicas'))
stage='native_secret'
values,native=m.native(bytes.fromhex(x['key_hex']));del values
assert native==x['native_secret']
for side in ['old','new']:
 stage=side+'_server_stopped'
 m.call(['-n',x['state']['namespace'],'exec','qualifier','-c',side,'--','/bin/sh','-c',
 'set -eu; test ! -e /run/qual/launch.pid; test ! -e /run/qual/mysqld.pid; for f in /proc/[0-9]*/comm; do read -r n < "$f" || continue; case "$n" in mysqld|mysqld_safe) p=${f%/comm}; z=$(sed -n "s/^State:[[:space:]]*//p" "$p/status"); test "$z" = "Z (zombie)";; esac; done'])
print(json.dumps({'copy_identity':copy,'source_identity':live,'native_secret':native,'both_servers_stopped':True}))
'''


def guard(shared, state, expected, native):
    body = {'observer': OBSERVER, 'observer_sha256': OBSERVER_SHA, 'state': state,
            'copy_identity': expected, 'original_image': ORIGINAL, 'native_secret': native,
            'key_hex': (PRIVATE / 'hmac-key.hex').read_text().strip()}
    return json.loads(remote(shared, ['python3', '-B', '-c', GUARD], shared.canonical(body)))


def decrypt(shared, cipher):
    child = subprocess.Popen([str(shared.AGE), '-d', '-i', str(shared.IDENTITY), str(cipher)],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    manifest = shared.verify_archive(child.stdout)
    trailing = 0
    for block in iter(lambda: child.stdout.read(65536), b''):
        trailing += len(block)
        need(trailing <= 1024**2 and not any(block), 'archive_trailing_bytes')
    need(child.wait(timeout=30) == 0, 'age_full_authentication')
    need(manifest['total_file_bytes'] <= MAX_DATA and not manifest['excluded_new_paths'], 'bounded_full_scope')
    need(all(p == 'data-0' or p.startswith('data-0/') for p in manifest['entries']), 'exact_data_root')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive-qualified-new', action='store_true', required=True)
    parser.parse_args()
    os.umask(0o077)
    shared = load_shared()
    cfree = int(subprocess.check_output(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
        '-NoProfile', '-NonInteractive', '-Command', '(Get-PSDrive C).Free'], timeout=30).decode().strip())
    need(cfree >= 15 * 1024**3 and BASE.is_mount(), 'capacity_or_approved_mount')
    fs = os.statvfs(BASE)
    need(fs.f_bavail * fs.f_frsize >= MAX_DATA + 16 * 1024**3, 'destination_15GiB_after_stage')
    pins = [(p, shared.protected(p, p == shared.IDENTITY)) for p in (shared.AGE, shared.IDENTITY, shared.RECIPIENT)]
    need(digest(shared.AGE) == shared.AGE_SHA256, 'age_binary_pin')
    OUTPUT.mkdir(mode=0o700, exist_ok=True)
    need(OUTPUT.resolve() == OUTPUT and OUTPUT.stat().st_uid == os.getuid() and not OUTPUT.stat().st_mode & 0o077, 'private_output')
    run = OUTPUT / ('archive-' + uuid.uuid4().hex)
    run.mkdir(mode=0o700)
    receipt = {'status': 'started', 'operation': 'source_proofs', 'schema_version': 1,
               'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'controller_sha256': digest(Path(__file__)), 'shared_source_sha256': PINS,
               'windows_c_free_before': cfree, 'destination_free_before': fs.f_bavail * fs.f_frsize,
               'no_sql': True, 'no_cluster_resource_mutations': True, 'source_pvc_mounted': False}

    def save():
        temp = run / ('receipt-' + uuid.uuid4().hex + '.tmp')
        with temp.open('x') as f:
            json.dump(receipt, f, indent=2, sort_keys=True)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(temp, run / 'receipt.json')

    save()
    try:
        state = json.loads((PRIVATE / 'copy-run.json').read_bytes())
        names = ['normal-old-02', 'normal-new-02', 'normal-comparison-02',
                 'stop-old-qualified-archive-01', 'stop-new-qualified-archive-01']
        proofs = {name: json.loads((PRIVATE / (name + '.json')).read_bytes()) for name in names}
        need(all(p['status'] == 'passed' for p in proofs.values()), 'qualified_and_stopped_receipts')
        need(all(proofs['normal-comparison-02']['comparison'].values()), 'normal_auth_exact_comparison')
        identity = proofs['normal-new-02']['copy_identity']
        need(all(proofs[n]['copy_identity'] == identity for n in names if n != 'normal-comparison-02'), 'qualified_copy_identity')
        need(identity['pod_uid'] == state['pod_uid'], 'copy_run_uid')
        native = proofs['normal-new-02']['native_secret']
        need(native == proofs['normal-old-02']['native_secret'], 'qualified_native_secret')
        originals = [p for p in (BASE / 'ruckus-cold-20261025').glob('*/receipt.json')
                     if digest(p) == state['backup_receipt_sha256']]
        need(len(originals) == 1, 'original_cold_receipt_pin')
        cold = json.loads(originals[0].read_bytes())
        need(cold['status'] == 'completed' and cold['cold_archive_verified'] and cold['temporary_pod_deleted'], 'original_cold_complete')
        original = Path(cold['archive_path'])
        need(digest(original) == cold['archive_sha256'] == state['archive_sha256'], 'original_cipher_preserved')
        receipt.update(copy_run_sha256=digest(PRIVATE / 'copy-run.json'),
                       qualification_receipts={n: digest(PRIVATE / (n + '.json')) for n in names},
                       original_receipt=str(originals[0]), original_receipt_sha256=digest(originals[0]),
                       original_archive_sha256=cold['archive_sha256'])
        before = guard(shared, state, identity, native)
        receipt['before'] = before
        receipt['operation'] = 'full_clone_inventory'; save()
        program = "__name__='qualified_archive_reader'\n" + (SHARED / 'pod_reader.py').read_text()
        program += "\nROOTS={'data-0':'/copies/new/data-0'}\nEXCLUDED=set()\nMAX_BYTES=384*1024**2\n"
        program += "try:\n if sys.argv[1]=='inventory': print(json.dumps(inventory(False),sort_keys=True))\n elif sys.argv[1]=='archive':\n  raw=sys.stdin.buffer.read(MAX_MANIFEST_BYTES+1);need(len(raw)<=MAX_MANIFEST_BYTES);archive(json.loads(raw))\n else: raise ValueError()\nexcept Exception: raise SystemExit(1)\n"
        command = ['kubectl', '-n', state['namespace'], 'exec', '-i', 'qualifier', '-c', 'reader', '--', 'python3', '-B', '-c', program]
        manifest = json.loads(remote(shared, command + ['inventory']))
        need(manifest['total_file_bytes'] <= MAX_DATA and not manifest['excluded_new_paths'], 'full_clone_bound')
        need(guard(shared, state, identity, native) == before, 'prestream_guards')
        receipt['operation'] = 'encrypted_full_clone_stream'; save()
        cipher = run / 'ruckusdb-5.7.44-qualified-data-0.tar.age'
        producer = remote(shared, command + ['archive'], shared.canonical(manifest), streaming=True)
        with cipher.open('xb') as target:
            encryptor = subprocess.Popen([str(shared.AGE), '-R', str(shared.RECIPIENT)], stdin=producer.stdout,
                                         stdout=target, stderr=subprocess.DEVNULL)
            producer.stdout.close()
            need(encryptor.wait(timeout=600) == 0 and producer.wait(timeout=30) == 0, 'encrypted_stream_complete')
            target.flush(); os.fsync(target.fileno())
        receipt['operation'] = 'authenticate_and_reobserve'; save()
        need(decrypt(shared, cipher) == manifest, 'decrypted_exact_manifest')
        need(json.loads(remote(shared, command + ['inventory'])) == manifest, 'unchanged_complete_clone')
        need(guard(shared, state, identity, native) == before, 'poststream_guards')
        need(digest(original) == cold['archive_sha256'], 'original_cipher_still_preserved')
        for path, ident in pins:
            need(shared.protected(path, path == shared.IDENTITY) == ident, 'key_tool_identity_stable')
        load_shared()
        need(digest(Path(__file__)) == receipt['controller_sha256'], 'controller_stable')
        receipt.update(status='completed', operation='complete', archive_path=str(cipher),
                       archive_sha256=digest(cipher), archive_bytes=cipher.stat().st_size,
                       manifest_sha256=hashlib.sha256(shared.canonical(manifest)).hexdigest(),
                       file_bytes=manifest['total_file_bytes'], file_count=sum(v['kind'] == 'file' for v in manifest['entries'].values()),
                       entry_count=len(manifest['entries']), excluded_paths=[], cold_archive_verified=True,
                       complete_inventory_unchanged=True, both_servers_stopped_after=True)
        save()
    except Exception as error:
        receipt.update(status='failed', error_type=type(error).__name__,
                       error_code=str(error) if isinstance(error, RuntimeError) else 'filtered_error',
                       source_lines=[f.lineno for f in traceback.extract_tb(error.__traceback__) if f.filename == __file__])
        save()
        print(json.dumps({'status': 'failed', 'receipt': str(run / 'receipt.json'), 'operation': receipt['operation'], 'error': receipt['error_code']}))
        raise SystemExit(1)
    print(json.dumps({k: receipt[k] for k in ('status', 'archive_path', 'archive_sha256', 'archive_bytes', 'manifest_sha256', 'file_bytes', 'file_count')} | {'receipt': str(run / 'receipt.json')}))


if __name__ == '__main__':
    main()
