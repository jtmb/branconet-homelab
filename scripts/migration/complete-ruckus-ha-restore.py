#!/usr/bin/env python3
"""Finish ONLY the two recorded SGID directory modes; never replay restore."""
import argparse
import copy
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import resource
import sys
import uuid

FBASE = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
FROZEN = FBASE / 'control-source/ruckus-ha-ro-anchor-20261025'
SOURCE_PINS = {
    'ruckus-ha-recovery.py': 'd7c75aecb6c2e2b60de72f7a8c014839ab779230b781f25880f7c803e4ef11d9',
    'ruckus-ha-recovery-remote.py': '8a383106e0e31bef3f59a25fc1f4e886bf8b4110198ff03f08bdb3a5744ace0d',
}
ROOT = FBASE / 'ruckus-ha-recovery-20261025'
BASELINE = ROOT / 'baseline-830061d53071484cab49ef1c178711b2/receipt.json'
BASELINE_SHA = '63ced125ab7f5e61c88f9df3d1d2cbf3af8244c48a5a19a6d662640e9bc1f345'
COLD = ROOT / 'cold-455be8afe1d7491fa9d787dbd6b85efa/receipt.json'
COLD_SHA = 'e105666f1119f350212f73a5c4e4107e185e2f1894d45448bb535796ceb6f321'
FAILED = ROOT / 'restore-c467d6a6880b4dbc87a227f341d93894/receipt.json'
FAILED_SHA = '6d11cc347fc96b2d76a4d933a23610e59b40d109c543c3b46e51a77deac2c4bc'
FIXES = {'data-0': (0o775, 0o2775), 'data-0/lost+found': (0o770, 0o2770)}


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def require(ok, code):
    if not ok:
        raise RuntimeError(code)


def load_core():
    for name, expected in SOURCE_PINS.items():
        require(digest(FROZEN / 'scripts/migration' / name) == expected, 'frozen_protocol_source')
    spec = importlib.util.spec_from_file_location('ha_frozen_core', FROZEN / 'scripts/migration/ruckus-ha-recovery.py')
    core = importlib.util.module_from_spec(spec); spec.loader.exec_module(core)
    require(core.check_sources() == SOURCE_PINS, 'frozen_dependency_sources')
    return core


def repair_plan(core, shared, run_id):
    original = core.plan(shared, 'restore', run_id)
    result = copy.deepcopy(original)
    caps = result['items'][1]['spec']['containers'][0]['securityContext']['capabilities']['add']
    require(caps == ['DAC_OVERRIDE', 'CHOWN', 'FOWNER'], 'original_three_capabilities')
    caps.append('FSETID')
    stripped = copy.deepcopy(result)
    stripped['items'][1]['spec']['containers'][0]['securityContext']['capabilities']['add'].remove('FSETID')
    require(stripped == original, 'only_FSETID_plan_difference')
    return result


def failed_proof(core, key):
    core.private(FAILED)
    require(digest(FAILED) == FAILED_SHA, 'exact_failed_receipt_sha')
    value = json.loads(FAILED.read_bytes()); signature = value.pop('receipt_hmac')
    require(hmac.compare_digest(signature, hmac.new(key, b'ruckus-ha-receipt\0' + core.canonical(value), hashlib.sha256).hexdigest()), 'failed_receipt_hmac')
    require(value['sources'] == SOURCE_PINS and value['dependencies'] == core.PINS, 'failed_protocol_dependencies')
    require(value['phase'] == 'restore' and value['status'] == 'failed' and value['error_code'] == 'all_restored_bytes_and_metadata', 'only_exact_metadata_failure')
    require(value['baseline_sha256'] == BASELINE_SHA and value['cold_sha256'] == COLD_SHA, 'failed_exact_lineage')
    require(value['target_gate']['target_inode'] == 292, 'recorded_owned_sibling_inode')
    return value


def exact_two_mode_diff(core, observed, expected):
    a, b = core.portable(observed), core.portable(expected)
    require(a['total_file_bytes'] == b['total_file_bytes'] == 213330203 and len(a['entries']) == len(b['entries']) == 298, 'full_exact_restore_scope')
    adjusted = copy.deepcopy(a)
    for name, (old, new) in FIXES.items():
        require(a['entries'][name]['kind'] == b['entries'][name]['kind'] == 'directory', 'only_directory_metadata')
        require(a['entries'][name]['mode'] == old and b['entries'][name]['mode'] == new, 'exact_missing_SGID_preimage')
        adjusted['entries'][name]['mode'] = new
    require(adjusted == b, 'exactly_two_mode_differences_no_other_change')


def repair_program(observed, target_inode):
    # Expected records are taken from the immediately preceding complete hash
    # inventory, never supplied as arbitrary paths or mode arguments by caller.
    expected = {name: observed['entries'][name] for name in FIXES}
    return r"""import json,os,pathlib,stat,sys
stage='metadata_finish_preconditions'
def filtered(kind,value,tb):
 print(json.dumps({'guard_stage':stage,'error_type':kind.__name__}))
sys.excepthook=filtered
expected=""" + repr(expected) + '\ntarget_inode=' + str(target_inode) + r"""
assert os.getuid()==0 and os.getgid()==0
status=dict(line.split(':',1) for line in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in line)
assert int(status['CapEff'].strip(),16)==((1<<0)|(1<<1)|(1<<3)|(1<<4))
flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW
fds=[]
def row(fd):
 s=os.fstat(fd);assert stat.S_ISDIR(s.st_mode)
 return {'kind':'directory','mode':stat.S_IMODE(s.st_mode),'uid':s.st_uid,'gid':s.st_gid,'mtime_ns':s.st_mtime_ns,'fingerprint':[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]}
try:
 ro=os.open('/original-ro',flags);fds.append(ro)
 assert os.fstatvfs(ro).f_flag & os.ST_RDONLY
 anchor=os.open('security-data-20261025',flags,dir_fd=ro);fds.append(anchor)
 root=os.open('/restore',flags);fds.append(root)
 assert not os.fstatvfs(root).f_flag & os.ST_RDONLY
 assert (os.fstat(anchor).st_dev,os.fstat(anchor).st_ino)==(os.fstat(root).st_dev,os.fstat(root).st_ino)
 assert os.fstat(root).st_ino==target_inode
 lost=os.open('lost+found',flags,dir_fd=root);fds.append(lost)
 assert row(root)==expected['data-0'] and row(lost)==expected['data-0/lost+found']
 assert expected['data-0']['mode']==0o775 and expected['data-0/lost+found']['mode']==0o770
 stage='two_directory_fchmod_only'
 os.fchmod(root,0o2775)
 os.fchmod(lost,0o2770)
 after={'data-0':row(root),'data-0/lost+found':row(lost)}
 for name,mode in [('data-0',0o2775),('data-0/lost+found',0o2770)]:
  a=dict(after[name]);b=dict(expected[name]);a['fingerprint']=a['fingerprint'][:4];b['fingerprint']=b['fingerprint'][:4];b['mode']=mode
  assert a==b
 assert os.fstatvfs(ro).f_flag & os.ST_RDONLY
 assert (os.fstat(anchor).st_dev,os.fstat(anchor).st_ino)==(os.fstat(root).st_dev,os.fstat(root).st_ino)
 print(json.dumps({'completed':True,'operations':2,'directories':after},sort_keys=True))
finally:
 for fd in reversed(fds):os.close(fd)
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('phase', choices=['plan', 'complete'])
    ap.add_argument('--reader-run-id', required=True)
    ap.add_argument('--reader-pod-uid'); ap.add_argument('--reader-policy-uid')
    ap.add_argument('--execute-two-directory-mode-repair', action='store_true')
    args = ap.parse_args()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); os.umask(0o077); sys.dont_write_bytecode = True
    core = load_core(); own_path = Path(__file__).resolve(); own_sha = digest(own_path)
    archiver = core.load_module(FROZEN / 'scripts/migration/archive-ruckusdb-qualified-copy.py', 'ha_completion_archive')
    shared = archiver.load_shared()
    plan = repair_plan(core, shared, args.reader_run_id)
    if args.phase == 'plan':
        require(not args.execute_two_directory_mode_repair and not args.reader_pod_uid and not args.reader_policy_uid, 'inert_plan_only')
        print(json.dumps(plan, sort_keys=True, indent=2)); return 0
    require(args.execute_two_directory_mode_repair and args.reader_pod_uid and args.reader_policy_uid, 'explicit_repair_and_new_reader_UIDs')
    core.capacity(launch=True, pending=16 * 1024**2)
    core.OUT.mkdir(mode=0o700, exist_ok=True); core.private(core.OUT)
    run = core.OUT / ('restore-' + uuid.uuid4().hex); run.mkdir(mode=0o700); core.environment(run)
    key = bytes.fromhex(sys.stdin.readline().strip()); require(len(key) == 32, 'existing_HMAC_key_stdin_only')
    receipt = {'schema_version': 1, 'phase': 'restore', 'status': 'failed', 'started_at': core.now(),
               'sources': SOURCE_PINS, 'dependencies': core.PINS,
               'completionKind': 'two-directory-SGID-metadata-finish',
               'completion_helper_sha256': own_sha, 'failed_restore_sha256': FAILED_SHA,
               'baseline_sha256': BASELINE_SHA, 'cold_sha256': COLD_SHA,
               'contract': 'old-files-preserved-new-sibling-parent-metadata-changed'}
    try:
        tool_pins = [(p, shared.protected(p, p == shared.IDENTITY)) for p in (shared.AGE, shared.IDENTITY, shared.RECIPIENT)]
        require(digest(shared.AGE) == shared.AGE_SHA256, 'age_binary_pin')
        baseline = core.read_proof(BASELINE, BASELINE_SHA, key, SOURCE_PINS)
        cold = core.read_proof(COLD, COLD_SHA, key, SOURCE_PINS)
        failed = failed_proof(core, key)
        require(baseline['phase'] == 'baseline' and cold['phase'] == 'cold' and cold['baseline_sha256'] == BASELINE_SHA and cold['fully_authenticated'], 'authenticated_cold_baseline_lineage')
        require(args.reader_pod_uid != failed['reader']['pod_uid'] and args.reader_policy_uid != failed['reader']['policy_uid'] and args.reader_run_id != failed['reader']['plan']['items'][1]['metadata']['name'].rsplit('-',1)[1], 'new_recorded_reader_required')
        reader = {'plan': plan, 'pod_uid': args.reader_pod_uid, 'policy_uid': args.reader_policy_uid}
        receipt['reader'] = reader; receipt['target_gate'] = failed['target_gate']
        request = {'phase': 'restore', 'sql': False, 'key_hex': key.hex(), 'reader': reader, 'baseline_identity': baseline['observation']['identity']}
        remote_source = (FROZEN / 'scripts/migration/ruckus-ha-recovery-remote.py').read_text()
        def guard():
            return json.loads(archiver.remote(shared, ['python3', '-B', '-c', remote_source], core.canonical(request)))
        before = guard(); receipt['observation'] = before
        require(before == failed['observation'], 'same_frozen_claims_native_identities_HA_and_writer_fences')
        for name in ('archive', 'manifest', 'original'):
            path = Path(cold[name + '_path']); core.private(path)
            require(digest(path) == cold[name + '_sha256'], 'cold_input_' + name)
        cipher = Path(cold['archive_path']); manifest = json.loads(Path(cold['manifest_path']).read_bytes())
        original = json.loads(Path(cold['original_path']).read_bytes())
        require(archiver.decrypt(shared, cipher) == manifest, 'full_age_authentication_before_repair')
        core.original_equal(original, core.inventory(archiver, shared, reader, '/original-ro', True), True)
        observed = core.inventory(archiver, shared, reader, '/restore')
        exact_two_mode_diff(core, observed, manifest)
        require(observed['entries']['data-0']['fingerprint'][1] == failed['target_gate']['target_inode'], 'failed_target_inode')
        # The other directory identity was measured in the retained actual inventory.
        require(observed['entries']['data-0/lost+found']['fingerprint'][1] == 598, 'recorded_lost_found_inode')
        core.save(run / 'before-metadata-completion.json', observed)
        program = repair_program(observed, failed['target_gate']['target_inode'])
        receipt['repair_program_sha256'] = hashlib.sha256(program.encode()).hexdigest()
        require(guard() == before and core.check_sources() == SOURCE_PINS and digest(own_path) == own_sha, 'pre_repair_guards_sources')
        result = json.loads(archiver.remote(shared, core.reader_command(reader, program)))
        require(result['completed'] is True and result['operations'] == 2, 'only_two_fchmod_completed')
        receipt['metadata_completion_result'] = result
        after = core.inventory(archiver, shared, reader, '/restore')
        require(core.portable(after) == core.portable(manifest), 'every_restored_byte_and_metadata_exact')
        # Preserve every inode, size, mtime and ctime except the two chmod ctimes.
        for name, prior in observed['entries'].items():
            a, b = prior['fingerprint'], after['entries'][name]['fingerprint']
            require(a[:4] == b[:4] and (name in FIXES or a[4] == b[4]), 'restored_inode_size_mtime_ctime_stability')
        core.save(run / 'after-metadata-completion.json', after)
        receipt['new_sibling_identity'] = core.sibling_identity(archiver, shared, reader)
        require(receipt['new_sibling_identity']['inode'] == failed['target_gate']['target_inode'], 'same_owned_sibling_inode_after')
        core.original_equal(original, core.inventory(archiver, shared, reader, '/original-ro', True), True)
        require(archiver.decrypt(shared, cipher) == manifest, 'full_age_authentication_after_repair')
        for name in ('archive', 'manifest', 'original'):
            require(digest(Path(cold[name + '_path'])) == cold[name + '_sha256'], 'retained_cold_' + name)
        require(guard() == before, 'all_remote_guards_stable')
        require(core.check_sources() == SOURCE_PINS and digest(own_path) == own_sha, 'all_source_hashes_stable')
        for path, identity in tool_pins:
            require(shared.protected(path, path == shared.IDENTITY) == identity, 'tool_key_identity_stable')
        require(digest(BASELINE) == BASELINE_SHA and digest(COLD) == COLD_SHA and digest(FAILED) == FAILED_SHA, 'all_lineage_receipts_retained')
        core.capacity()
        receipt.update(status='passed', original_old_files_preserved=True, fully_authenticated=True,
                       restored_bytes=manifest['total_file_bytes'], restored_entries=len(manifest['entries']))
    except Exception as error:
        receipt['error_code'] = str(error) if isinstance(error, RuntimeError) else type(error).__name__
    receipt['finished_at'] = core.now()
    receipt['receipt_hmac'] = hmac.new(key, b'ruckus-ha-receipt\0' + core.canonical(receipt), hashlib.sha256).hexdigest()
    core.save(run / 'receipt.json', receipt)
    print(json.dumps({'status': receipt['status'], 'receipt': str(run / 'receipt.json'), 'receipt_sha256': digest(run / 'receipt.json')}))
    return 0 if receipt['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
