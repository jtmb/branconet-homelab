"""Resume independent restoration from the existing immutable NAS ciphertext."""
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
R = F / 'node-cleanup-20261027/worker2-legacy-plex-preservation'
L = '/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/node-cleanup-20261027/worker2-legacy-plex-preservation'
NAS = Path(r'\\TRUENAS\plex_smb_share\Branconet-Recovery-Backups\2026-10-25\ciphertexts')


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def main():
    need(os.name == 'nt', 'existing_windows_transport')
    os.environ.update(TEMP=str(F / 'operator-control/tmp'), TMP=str(F / 'operator-control/tmp'))
    original = json.loads((R / 'backup-first-restore-failure.json').read_text())
    profile_raw = (R / 'profile.json').read_bytes()
    profile = json.loads(profile_raw)
    helper = R / 'verify-resume-frozen.py'
    safe = (R / 'reference-frozen.py').read_bytes()
    archive = Path(original['archive'])
    need(archive.parent == NAS and archive.name == 'sha256-' + original['archiveSHA256'] + '.age'
         and archive.stat().st_size == original['archiveBytes'], 'original_completed_ciphertext')
    need(hashlib.sha256(profile_raw).hexdigest() == original['profileSHA256']
         and not (R / 'backup-receipt.json').exists() and not (R / 'restore-receipt.json').exists()
         and not (R / 'restore-batch').exists(), 'preserved_original_inputs_and_reconciled_scratch')
    depth = max(len(Path(row['relative']).parts) for row in profile['rows'])
    budget = (503 + depth) * 4096 + max(256 * 1024**2, profile['maxFileBytes']) + 64 * 1024**2
    need(shutil.disk_usage('C:\\').free >= 15 * 1024**3
         and shutil.disk_usage(F).free >= 15 * 1024**3 + budget, 'unchanged_controller_space_floor')
    result = dict(original, status='started', verifierSHA256=hashlib.sha256(helper.read_bytes()).hexdigest(),
                  restoreWorkingBudgetBytes=budget, resumedExistingCiphertext=True)
    result.pop('errorCategory', None)
    command = ['wsl', '-d', 'Ubuntu', '-u', 'root', '--cd', '/home/brajam', '--exec', '/usr/bin/systemd-run',
               '--quiet', '--wait', '--pipe', '--collect', '--unit=branconet-legacy-plex-resume-' + uuid.uuid4().hex,
               '--property=MemoryMax=1073741824', '--property=MemorySwapMax=0', '--property=CPUQuota=100%',
               '--property=TasksMax=64', '--property=UMask=0077', '--property=PrivateNetwork=true',
               '--property=ProtectSystem=strict', '--property=ReadWritePaths=' + L,
               '/usr/bin/env', 'TMPDIR=' + L, 'TMP=' + L, 'TEMP=' + L,
               '/usr/bin/python3', '-B', L + '/verify-resume-frozen.py', 'verify', '--profile', L + '/profile.json',
               '--safety-source', base64.b64encode(safe).decode(), '--safety-sha256', hashlib.sha256(safe).hexdigest()]
    child = None
    try:
        child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        (R / 'restore-resume-process.json').write_text(json.dumps({'nativePID': os.getpid(), 'WSLPID': child.pid,
            'unit': next(v for v in command if v.startswith('--unit=')), 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat()}))
        digest, count, reported = hashlib.sha256(), 0, 0
        before = archive.stat()
        with archive.open('rb') as source:
            for block in iter(lambda: source.read(1024**2), b''):
                child.stdin.write(block)
                digest.update(block)
                count += len(block)
                if count - reported >= 512 * 1024**2:
                    print(json.dumps({'event': 'NAS_restore_progress', 'bytes': count}), flush=True)
                    reported = count
        child.stdin.close()
        code = child.wait(timeout=7200)
        stdout, stderr = child.stdout.read(), child.stderr.read()
        result.update(restoreProcessExit=code, restoreDiagnosticsSHA256=hashlib.sha256(stderr).hexdigest())
        need(code == 0 and count == original['archiveBytes'] and digest.hexdigest() == original['archiveSHA256'],
             'full_existing_NAS_readback_and_restore')
        after = archive.stat()
        need((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'NAS_unchanged')
        restored_raw = (R / 'restore-receipt.json').read_bytes()
        restored = json.loads(restored_raw)
        need(restored['status'] == 'completed' and restored['completeAgeAuthentication']
             and restored['everyEntryIndependentlyRestored'] and restored['scratchReconciled']
             and restored['counts'] == profile['counts'], 'all_entries_verified')
        key = json.loads((F / 'operator-control/smb-mealie-copy-status.json').read_text())['keyBackup']
        need(key['verifiedUnprotectInRAM'], 'existing_recovery_key_qualification')
        result.update(status='completed', completeNASReadbackAuthenticated=True, everyEntryIndependentlyRestored=True,
                      counts=restored['counts'], restoreReceiptSHA256=hashlib.sha256(restored_raw).hexdigest(),
                      sourceCanonicalProfileSHA256=restored['sourceProfileSHA256'], existingRecoveryKeyBackup=key,
                      localPayloadArchiveCreated=False, maximumFileRestoreBytes=profile['maxFileBytes'])
    except Exception as error:
        result.update(status='failed', errorCategory=str(error) if isinstance(error, ValueError) else type(error).__name__)
        raise
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=30)
        with (R / 'backup-receipt.json').open('x') as out:
            json.dump(result, out, indent=2)
        print(json.dumps({'status': result['status'], 'sourceOriginalsDeleted': False}), flush=True)


if __name__ == '__main__':
    main()
