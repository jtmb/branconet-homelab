"""Stream the fixed legacy Plex trees to NAS and restore every entry privately.

Windows transports bytes through the existing NAS access. No source deletion,
local payload archive, image pull, new credential or publication route is used.
"""
import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

F = Path(r'\\wsl.localhost\Ubuntu\home\brajam\.local\share\branconet-migration\local-image-build-offload-20261025')
LINUX = '/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/'
RUN = F / 'node-cleanup-20261027/worker2-legacy-plex-preservation'
NAS = Path(r'\\TRUENAS\plex_smb_share\Branconet-Recovery-Backups\2026-10-25\ciphertexts')
FLOOR = 15 * 1024**3


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def linux(path):
    return LINUX + path.relative_to(F).as_posix()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--helper', type=Path, required=True)
    parser.add_argument('--safety-source', type=Path, required=True)
    a = parser.parse_args()
    need(os.name == 'nt', 'existing_windows_nas_transport')
    need(a.profile == RUN / 'profile.json' and a.helper == RUN / 'archive-frozen.py'
         and a.safety_source == RUN / 'reference-frozen.py', 'exact_owned_inputs')
    for path in (a.profile, a.helper, a.safety_source):
        need(path.resolve().is_relative_to(F.resolve()) and path.is_file(), 'owned_input_files')
    need(0 < a.profile.stat().st_size <= 192 * 1024**2, 'bounded_profile_size')
    raw_profile = a.profile.read_bytes()
    profile = json.loads(raw_profile)
    need(profile['schema'] == 1 and profile['filesystem']['uuid'] == '960bc2c7-2a7e-4bc2-b2c5-dbb6d71207f4'
         and profile['roots'] == ['plex2/config', 'plex2/config.old']
         and 0 < len(profile['rows']) <= 150000 and profile['fileBytes'] <= 16 * 1024**3
         and profile['maxFileBytes'] <= 512 * 1024**2, 'fixed_bounded_original_trees')
    depth = max(len(Path(row['relative']).parts) for row in profile['rows'])
    largest_member = max(row['identity']['size'] for row in profile['rows'] if row['kind'] == 'file')
    need(largest_member == profile['maxFileBytes'], 'measured_largest_member')
    restore_budget = (503 + depth) * 4096 + max(256 * 1024**2, largest_member) + 64 * 1024**2
    need(shutil.disk_usage('C:\\').free >= FLOOR and shutil.disk_usage(F).free >= FLOOR + restore_budget,
         'controller_space_floor')
    maximum = profile['fileBytes'] + len(raw_profile) + len(profile['rows']) * 8192 + 16 * 1024**2
    need(NAS.is_dir() and shutil.disk_usage(NAS).free >= FLOOR + maximum, 'approved_nas_space')
    os.environ.update(TEMP=str(F / 'operator-control/tmp'), TMP=str(F / 'operator-control/tmp'))
    receipt = RUN / 'backup-receipt.json'
    need(not receipt.exists(), 'prior_backup_outcome_preserved')
    token = uuid.uuid4().hex
    partial = NAS / ('legacy-plex-' + token + '.age.partial')
    result = {'status': 'started', 'owner': '01a12045-bf7e-73b3-8557-752d17c72ffd',
              'profileSHA256': hashlib.sha256(raw_profile).hexdigest(),
              'helperSHA256': hashlib.sha256(a.helper.read_bytes()).hexdigest(),
              'referenceSHA256': hashlib.sha256(a.safety_source.read_bytes()).hexdigest(),
              'partial': str(partial), 'sourceOriginalsDeleted': False, 'restoreWorkingBudgetBytes': restore_budget}
    events = RUN / 'backup-events.jsonl'

    def event(name, **values):
        record = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'event': name, **values}
        with events.open('a', encoding='utf8') as out:
            out.write(json.dumps(record) + '\n')
            out.flush()
            os.fsync(out.fileno())
        print(json.dumps(record), flush=True)

    children = []
    try:
        event('encrypted_stream_started', maximumBytes=maximum, sourceFiles=profile['counts']['file'])
        command = ['wsl', '-d', 'Ubuntu', '-u', 'root', '--cd', '/home/brajam', '--exec', '/usr/sbin/runuser', '-u', 'brajam',
                   '--', '/usr/bin/python3', '-B', linux(a.helper), 'encrypt', '--profile', linux(a.profile)]
        producer = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        children.append(producer)
        event('source_process_started', nativeOperatorPID=os.getpid(), sourceWSLProcessPID=producer.pid)
        value = hashlib.sha256()
        count = 0
        reported = 0
        with partial.open('xb') as out:
            for block in iter(lambda: producer.stdout.read(1024**2), b''):
                count += len(block)
                need(count <= maximum, 'encrypted_stream_byte_bound')
                out.write(block)
                value.update(block)
                if count - reported >= 512 * 1024**2:
                    event('encrypted_stream_progress', bytes=count)
                    reported = count
            out.flush()
            os.fsync(out.fileno())
        need(producer.wait(timeout=120) == 0 and count > 0, 'complete_source_archive_stream')
        result['sourceDiagnosticsSHA256'] = hashlib.sha256(producer.stderr.read()).hexdigest()
        final = NAS / ('sha256-' + value.hexdigest() + '.age')
        need(not final.exists() and partial.stat().st_size == count, 'new_verified_ciphertext_name')
        partial.rename(final)
        result.update(archive=str(final), archiveBytes=count, archiveSHA256=value.hexdigest())
        event('ciphertext_published', bytes=count, sha256=value.hexdigest())
        safe = a.safety_source.read_bytes()
        command = ['wsl', '-d', 'Ubuntu', '-u', 'root', '--cd', '/home/brajam', '--exec', '/usr/bin/systemd-run',
                   '--quiet', '--wait', '--pipe', '--collect', '--unit=branconet-legacy-plex-restore-' + token,
                   '--property=MemoryMax=1073741824', '--property=MemorySwapMax=0', '--property=CPUQuota=100%',
                   '--property=TasksMax=64', '--property=UMask=0077', '--property=PrivateNetwork=true',
                   '--property=ProtectSystem=strict', '--property=ReadWritePaths=' + linux(RUN),
                   '/usr/bin/env', 'TMPDIR=' + linux(RUN), 'TMP=' + linux(RUN), 'TEMP=' + linux(RUN),
                   '/usr/bin/python3', '-B', linux(a.helper), 'verify', '--profile', linux(a.profile),
                   '--safety-source', base64.b64encode(safe).decode(), '--safety-sha256', hashlib.sha256(safe).hexdigest()]
        event('independent_restore_started', unit='branconet-legacy-plex-restore-' + token,
              memoryLimitBytes=1073741824, sourceCounts=profile['counts'])
        verifier = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        children.append(verifier)
        event('restore_process_started', nativeOperatorPID=os.getpid(), restoreWSLProcessPID=verifier.pid)
        readback, read, reported = hashlib.sha256(), 0, 0
        before = final.stat()
        with final.open('rb') as inp:
            for block in iter(lambda: inp.read(1024**2), b''):
                verifier.stdin.write(block)
                readback.update(block)
                read += len(block)
                if read - reported >= 512 * 1024**2:
                    event('nas_restore_readback_progress', bytes=read)
                    reported = read
        verifier.stdin.close()
        status = verifier.wait(timeout=7200)
        stdout, stderr = verifier.stdout.read(), verifier.stderr.read()
        result.update(restoreProcessExit=status, restoreDiagnosticsSHA256=hashlib.sha256(stderr).hexdigest())
        need(status == 0 and read == count and readback.hexdigest() == value.hexdigest(), 'full_nas_readback_and_restore')
        after = final.stat()
        need((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'nas_source_unchanged')
        restored = json.loads((RUN / 'restore-receipt.json').read_text())
        need(restored['status'] == 'completed' and restored['completeAgeAuthentication']
             and restored['everyEntryIndependentlyRestored'] and restored['scratchReconciled']
             and restored['counts'] == profile['counts'], 'complete_all_entry_restore_receipt')
        need(hashlib.sha256(a.profile.read_bytes()).hexdigest() == result['profileSHA256'], 'original_profile_unchanged')
        key = json.loads((F / 'operator-control/smb-mealie-copy-status.json').read_text())['keyBackup']
        need(key['verifiedUnprotectInRAM'], 'existing_recovery_key_qualification')
        result.update(status='completed', completeNASReadbackAuthenticated=True, everyEntryIndependentlyRestored=True,
                      counts=restored['counts'], restoreReceiptSHA256=hashlib.sha256((RUN / 'restore-receipt.json').read_bytes()).hexdigest(),
                      sourceCanonicalProfileSHA256=restored['sourceProfileSHA256'], existingRecoveryKeyBackup=key,
                      localPayloadArchiveCreated=False, maximumFileRestoreBytes=profile['maxFileBytes'])
        event('backup_and_restore_completed', counts=restored['counts'])
    except Exception as error:
        result.update(status='failed', errorCategory=str(error) if isinstance(error, ValueError) else type(error).__name__)
        raise
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=30)
        with receipt.open('x', encoding='utf8') as out:
            json.dump(result, out, indent=2)
            out.write('\n')
        print(json.dumps({'status': result['status'], 'receipt': str(receipt),
                          'archiveBytes': result.get('archiveBytes'), 'sourceOriginalsDeleted': False}), flush=True)


if __name__ == '__main__':
    main()
