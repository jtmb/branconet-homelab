"""Hold verified NAS originals read-only during exact legacy-copy retirement.

Windows operator only. Source deletion is delegated to the reviewed WSL/Ansible
helper while these handles remain open; ordinary media reads remain allowed.
"""
import argparse
import ctypes
from ctypes import wintypes
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

F = Path(r'\\wsl.localhost\Ubuntu\home\brajam\.local\share\branconet-migration\local-image-build-offload-20261025')
LINUX = '/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/'
NAS = Path(r'\\TRUENAS\plex_smb_share\downloads')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def linux(path):
    return LINUX + path.relative_to(F).as_posix()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--copy-receipt', type=Path, required=True)
    p.add_argument('--child-operator', type=Path, required=True)
    p.add_argument('--remote-helper', type=Path, required=True)
    p.add_argument('--safety-source', type=Path, required=True)
    p.add_argument('--journal-profile', type=Path)
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    need(os.name == 'nt', 'windows_only')
    for path in (a.copy_receipt, a.child_operator, a.remote_helper, a.safety_source):
        need(path.resolve().is_relative_to(F.resolve()) and path.is_file(), 'existing_owned_source')
    need(shutil.disk_usage('C:\\').free >= 15 * 1024**3 and shutil.disk_usage(F).free >= 15 * 1024**3 + 128 * 1024**2, 'controller_space')
    os.environ.update(TEMP=str(F / 'operator-control/tmp'), TMP=str(F / 'operator-control/tmp'))
    copy = json.loads(a.copy_receipt.read_text())
    if a.journal_profile:
        need(a.journal_profile.resolve().is_relative_to(F.resolve()) and a.journal_profile.is_file(), 'owned_journal_profile')
        need(copy['status'] == 'completed' and copy['completeNASReadbackAuthenticated'] and copy['everyJournalIndependentlyRestored'], 'complete_journal_backup')
        need(hashlib.sha256(a.journal_profile.read_bytes()).hexdigest() == copy['profileSHA256'], 'journal_profile_changed')
        restored = a.copy_receipt.with_name('restore-receipt.json')
        need(hashlib.sha256(restored.read_bytes()).hexdigest() == copy['restoreReceiptSHA256'], 'independent_restore_receipt_changed')
        profile = json.loads(a.journal_profile.read_text())
        restore = json.loads(restored.read_text())
        need(restore['status'] == 'completed' and restore['scratchReconciled'] and len(restore['restoredFiles']) == len(profile['files']), 'every_journal_restore_required')
        archive = Path(copy['archive'])
        need(archive.name == 'sha256-' + copy['archiveSHA256'] + '.age', 'content_addressed_journal_archive')
        nas_base = Path(r'\\TRUENAS\plex_smb_share\Branconet-Recovery-Backups\2026-10-25\ciphertexts')
        files = [{'source': {'name': archive.name, 'sha256': copy['archiveSHA256']}, 'nasPath': str(archive),
                  'nasBytes': copy['archiveBytes'], 'nasSHA256': copy['archiveSHA256']}]
    else:
        need(copy['status'] == 'completed' and copy['originalSourcesUnchanged'] and len(copy['files']) == 2, 'complete_copy_receipt')
        files = copy['files']
        nas_base = NAS
    run = a.copy_receipt.parent
    token = uuid.uuid4().hex
    proofpath = run / ('nas-retirement-proof-' + token + '.json')
    events = run / ('nas-retirement-lock-events-' + token + '.jsonl')
    def event(name, **data):
        with events.open('a', encoding='utf8') as out:
            out.write(json.dumps({'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'event': name, **data}) + '\n')
            out.flush()
            os.fsync(out.fileno())
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    class FileInfo(ctypes.Structure):
        _fields_ = [('attributes', wintypes.DWORD), ('creation', wintypes.FILETIME),
                    ('access', wintypes.FILETIME), ('write', wintypes.FILETIME),
                    ('volume', wintypes.DWORD), ('sizeHigh', wintypes.DWORD),
                    ('sizeLow', wintypes.DWORD), ('links', wintypes.DWORD),
                    ('indexHigh', wintypes.DWORD), ('indexLow', wintypes.DWORD)]
    kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(FileInfo)]
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel.ReadFile.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    def information(handle):
        value = FileInfo()
        need(kernel.GetFileInformationByHandle(handle, ctypes.byref(value)), 'nas_handle_information_unavailable')
        return {'size': value.sizeHigh * 2**32 + value.sizeLow, 'volume': value.volume,
                'index': value.indexHigh * 2**32 + value.indexLow,
                'writeTime': value.write.dwHighDateTime * 2**32 + value.write.dwLowDateTime}
    handles = []
    child = None
    try:
        for index, item in enumerate(files):
            target = Path(item['nasPath'])
            need(target == nas_base / item['source']['name'] and target.is_file() and not target.is_symlink(), 'canonical_nas_file')
            # GENERIC_READ, FILE_SHARE_READ only, OPEN_EXISTING. Deny new writes
            # and deletion on the Samba share while retaining normal readers.
            handle = kernel.CreateFileW(str(target), 0x80000000, 1, None, 3, 0x08000000, None)
            need(handle not in (None, ctypes.c_void_p(-1).value), 'nas_read_lock_failed')
            handles.append(handle)
            before = information(handle)
            for access in (0x40000000, 0x00010000):
                probe = kernel.CreateFileW(str(target), access, 7, None, 3, 0, None)
                if probe not in (None, ctypes.c_void_p(-1).value):
                    kernel.CloseHandle(probe)
                    raise ValueError('nas_write_or_delete_guard_not_enforced')
                need(ctypes.get_last_error() == 32, 'nas_guard_sharing_violation_required')
            h = hashlib.sha256()
            count = 0
            buffer = ctypes.create_string_buffer(1024**2)
            read = wintypes.DWORD()
            while True:
                need(kernel.ReadFile(handle, buffer, len(buffer), ctypes.byref(read), None), 'nas_locked_read_failed')
                if not read.value:
                    break
                h.update(buffer.raw[:read.value])
                count += read.value
            after = information(handle)
            need(count == item['nasBytes'] and h.hexdigest() == item['source']['sha256'] == item['nasSHA256'], 'nas_full_sha256_changed')
            need(before == after, 'nas_identity_changed')
            event('nas_read_lock_verified', index=index, bytes=count, sha256=h.hexdigest())
        proof = {'schema': 1, 'copyStatus': 'completed', 'copyReceiptSHA256': hashlib.sha256(a.copy_receipt.read_bytes()).hexdigest(),
                 'nasReadLocksHeld': True, 'nasVerificationEpoch': time.time(), 'nativePID': os.getpid(), 'token': token, 'files': files}
        if a.journal_profile:
            proof.update(journalCanonicalProfileSHA256=hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                         journalBackup=copy, independentRestoreVerified=True)
        with proofpath.open('x', encoding='utf8') as out:
            json.dump(proof, out, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        command = ['wsl', '-d', 'Ubuntu', '-u', 'root', '--cd', '/home/brajam', '--exec', '/usr/sbin/runuser', '-u', 'brajam',
                   '--', '/usr/bin/python3', '-B', linux(a.child_operator), '--proof', linux(proofpath),
                   '--remote-helper', linux(a.remote_helper), '--safety-source', linux(a.safety_source)]
        if a.apply:
            command.append('--apply')
        if a.journal_profile:
            command.extend(['--journal-profile', linux(a.journal_profile)])
        event('reviewed_child_started', apply=a.apply, nativePID=os.getpid(), proof=str(proofpath))
        child = subprocess.Popen(command)
        status = child.wait()
        need(status == 0, 'retirement_child_failed_original_or_partial_evidence_retained')
        for handle, item in zip(handles, files):
            need(information(handle)['size'] == item['nasBytes'], 'locked_nas_size_changed')
        event('child_completed_with_nas_locks_held', apply=a.apply)
        print(json.dumps({'status': 'completed', 'proof': str(proofpath), 'nasFilesPreserved': len(files), 'apply': a.apply}))
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=30)
        for handle in handles:
            kernel.CloseHandle(handle)
        event('nas_read_locks_released')


if __name__ == '__main__':
    main()
