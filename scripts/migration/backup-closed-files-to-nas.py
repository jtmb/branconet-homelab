"""Stream the fixed closed-file catalog encrypted to the approved NAS and restore every file.

No source deletion. Only one <=256 MiB recovered file exists locally at a time.
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
import sys

F = Path(r'\\wsl.localhost\Ubuntu\home\brajam\.local\share\branconet-migration\local-image-build-offload-20261025')
LINUX = '/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/'
NAS = Path(r'\\TRUENAS\plex_smb_share\Branconet-Recovery-Backups\2026-10-25\ciphertexts')
FLOOR = 15 * 1024**3


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def linux(path):
    return LINUX + path.relative_to(F).as_posix()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile', type=Path, required=True)
    p.add_argument('--helper', type=Path, required=True)
    p.add_argument('--safety-source', type=Path, required=True)
    a = p.parse_args()
    password=sys.stdin.buffer.readline(130).removesuffix(b'\n')
    need(0<len(password)<=128 and not any(x in password for x in (b'\n',b'\r',b'\0')), 'protected_stdin_required')
    password=None  # James has verified read access; encryption needs no sudo.
    need(os.name == 'nt', 'windows_operator')
    for path in (a.profile, a.helper, a.safety_source):
        need(path.resolve().is_relative_to(F.resolve()) and path.is_file(), 'owned_sources')
    need(hashlib.sha256(a.helper.read_bytes()).hexdigest()=='4442d412cc2d07728f90f7b85c364c444608b28c24caa6c97dd0e7b20a8da278' and hashlib.sha256(a.safety_source.read_bytes()).hexdigest()=='09fbe87185c078f7e31e3501e502ae4600a00da77b892b940d09c3903250a92c', 'frozen_source_pins')
    profile = json.loads(a.profile.read_text())
    nodes = {'960bc2c7-2a7e-4bc2-b2c5-dbb6d71207f4': 'workernode2',
             '763cda3d-0777-4b03-a882-9d21060466e3': 'masternode'}
    node = nodes.get(profile['filesystem']['uuid'])
    need(profile['schema'] == 1 and profile['scope']=='closed-file-offload' and node and profile.get('node', node) == node
         and 0 < len(profile['files']) <= 32 and profile['fileBytes'] <= 3 * 1024**3, 'bounded_source_profile')
    run_expected=F/'platform-upstream-review-20261027/autonomous-hardening-20261028/closed-file-offload'/node
    need(a.profile==run_expected/'profile.json' and a.helper==run_expected/'offload-frozen.py' and a.safety_source==run_expected/'safety-frozen.py', 'exact_owned_sources')
    need(all(0<row['identity']['size']<=256*1024**2 for row in profile['files']), 'one_file_restore_bound')
    need(shutil.disk_usage('C:\\').free >= FLOOR and shutil.disk_usage(F).free >= FLOOR + 384 * 1024**2, 'controller_space')
    maximum = profile['fileBytes'] + 8 * 1024**2
    need(NAS.is_dir() and shutil.disk_usage(NAS).free >= FLOOR + maximum, 'approved_nas_space')
    os.environ.update(TEMP=str(F / 'operator-control/tmp'), TMP=str(F / 'operator-control/tmp'))
    run = a.profile.parent
    receipt = run / 'backup-receipt.json'
    need(not receipt.exists(), 'prior_backup_preserved')
    token = uuid.uuid4().hex
    partial = NAS / ('closed-file-offload-' + token + '.age.partial')
    result = {'status': 'started', 'owner': 'closed-file-offload', 'scope':'closed-file-offload', 'node':node, 'profileSHA256': hashlib.sha256(a.profile.read_bytes()).hexdigest(),
              'helperSHA256': hashlib.sha256(a.helper.read_bytes()).hexdigest(), 'safetySHA256':hashlib.sha256(a.safety_source.read_bytes()).hexdigest(),'sourceSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'partial': str(partial), 'sourceOriginalsDeleted': False}
    ownership=run/'backup-ownership.json'
    need(not ownership.exists() and not (run/'archive-events.jsonl').exists(), 'prior_backup_attempt_preserved')
    with ownership.open('x',encoding='utf8') as out:
        json.dump({'owner':'closed-file-offload','root':str(run),'physicalUUID':'3c792469-ea0e-4a2c-98e8-1185b141607b','inputs':result,'peakLocalBytes':384*1024**2,'outputs':['backup-receipt.json','restore-receipt.json','archive-events.jsonl','restore-scratch'], 'NASPartial':str(partial),'regeneration':'Exact profile source stream encrypted with pinned existing age; never replay a failed safety qualification','protected':'Original files, immutable profile/source evidence, existing DPAPI key backup and NAS ciphertext; no local full plaintext archive'},out,indent=2);out.flush();os.fsync(out.fileno())
    events = run / 'archive-events.jsonl'
    def event(name, **values):
        with events.open('a', encoding='utf8') as out:
            out.write(json.dumps({'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'event': name, **values}) + '\n')
            out.flush()
            os.fsync(out.fileno())
    children = []
    try:
        need(not partial.exists(), 'new_nas_partial')
        event('encrypted_stream_started', partial=str(partial), maximumBytes=maximum)
        command = ['wsl', '-d', 'Ubuntu', '-u', 'root', '--cd', '/home/brajam', '--exec', '/usr/sbin/runuser', '-u', 'brajam',
                   '--', '/usr/bin/python3', '-B', linux(a.helper), '--mode', 'encrypt', '--profile', linux(a.profile)]
        producer = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        children.append(producer)
        value = hashlib.sha256()
        count = 0
        with partial.open('xb') as out:
            for block in iter(lambda: producer.stdout.read(1024**2), b''):
                if count == 0:
                    need(block.startswith(b'age-encryption.org/v1\n'), 'encrypted_stream_required')
                count += len(block)
                need(count <= maximum, 'ciphertext_bound')
                out.write(block)
                value.update(block)
            out.flush()
            os.fsync(out.fileno())
        need(producer.wait(timeout=60) == 0 and count > 0, 'source_and_encryption_completed')
        final = NAS / ('sha256-' + value.hexdigest() + '.age')
        need(not final.exists() and partial.stat().st_size == count, 'new_complete_ciphertext')
        partial.rename(final)
        result.update(archive=str(final), archiveBytes=count, archiveSHA256=value.hexdigest())
        event('ciphertext_published', bytes=count, sha256=value.hexdigest())
        safe = a.safety_source.read_bytes()
        command = ['wsl', '-d', 'Ubuntu', '-u', 'root', '--cd', '/home/brajam', '--exec', '/usr/bin/systemd-run',
                   '--quiet', '--wait', '--pipe', '--collect', '--unit=branconet-closed-file-restore-' + token,
                   '--property=MemoryMax=268435456', '--property=MemorySwapMax=0', '--property=CPUQuota=100%',
                   '--property=TasksMax=64', '--property=UMask=0077', '--property=PrivateNetwork=true', '/usr/bin/env',
                   'TMPDIR=' + LINUX + 'operator-control/tmp', 'TMP=' + LINUX + 'operator-control/tmp', 'TEMP=' + LINUX + 'operator-control/tmp',
                   '/usr/bin/python3', '-B', linux(a.helper), '--mode', 'verify', '--profile', linux(a.profile),
                   '--safety-source', base64.b64encode(safe).decode(), '--safety-sha256', hashlib.sha256(safe).hexdigest()]
        event('independent_restore_started', unit='branconet-closed-file-restore-' + token, maximumMemoryBytes=268435456)
        verifier = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        children.append(verifier)
        readback = hashlib.sha256()
        read = 0
        original = final.stat()
        with final.open('rb') as inp:
            for block in iter(lambda: inp.read(1024**2), b''):
                verifier.stdin.write(block)
                readback.update(block)
                read += len(block)
        verifier.stdin.close()
        status = verifier.wait(timeout=1200)
        stdout, stderr = verifier.stdout.read(), verifier.stderr.read()
        result['restoreProcessExit'] = status
        result['restoreDiagnosticsSHA256'] = hashlib.sha256(stderr).hexdigest()
        need(status == 0 and read == count and readback.hexdigest() == value.hexdigest(), 'nas_authentication_and_independent_restore')
        after = final.stat()
        need((original.st_size, original.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'nas_ciphertext_changed')
        restored = json.loads((run / 'restore-receipt.json').read_text())
        need(restored['status'] == 'completed' and restored['completeAgeAuthentication'] and restored['everyFileIndependentlyRestored'] and restored['scratchReconciled'], 'complete_restore_receipt')
        need(len(restored['restoredFiles']) == len(profile['files']), 'every_selected_file_restored')
        need({(row['archiveName'],row['sha256'],row['bytes']) for row in restored['restoredFiles']}=={(row['archiveName'],row['sha256'],row['identity']['size']) for row in profile['files']}, 'restore_each_exact_file')
        need(all(row['numericMetadataVerified'] and row['xattrsVerified'] for row in restored['restoredFiles']), 'restore_each_file_metadata')
        need(hashlib.sha256(a.helper.read_bytes()).hexdigest()==result['helperSHA256'] and hashlib.sha256(a.safety_source.read_bytes()).hexdigest()==result['safetySHA256'] and hashlib.sha256(a.profile.read_bytes()).hexdigest()==result['profileSHA256'], 'frozen_sources_unchanged')
        key = json.loads((F / 'operator-control/smb-mealie-copy-status.json').read_text())['keyBackup']
        need(key['verifiedUnprotectInRAM'], 'existing_recovery_key_backup')
        result.update(status='completed', completeNASReadbackAuthenticated=True, everyJournalIndependentlyRestored=True,
                      restoredFiles=len(restored['restoredFiles']), restoreReceiptSHA256=hashlib.sha256((run / 'restore-receipt.json').read_bytes()).hexdigest(),
                      existingRecoveryKeyBackup=key, localArchiveCreated=False, maximumPlaintextScratchBytes=268435456, everyFileIndependentlyRestored=True)
        event('backup_and_restore_completed', files=result['restoredFiles'])
    except Exception as error:
        result.update(status='failed', errorCategory=str(error) if isinstance(error, ValueError) else type(error).__name__)
        raise
    finally:
        password=None
        for child in children:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=30)
        with receipt.open('x', encoding='utf8') as out:
            json.dump(result, out, indent=2)
            out.write('\n')
        print(json.dumps({'status': result['status'], 'receipt': str(receipt), 'archiveBytes': result.get('archiveBytes'), 'sourceOriginalsDeleted': False}))


if __name__ == '__main__':
    main()
