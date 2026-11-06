"""Hold verified NAS originals read-only during exact closed-file duplicate retirement.

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
import socket
import threading
import sys
import re

F = Path(r'\\wsl.localhost\Ubuntu\home\brajam\.local\share\branconet-migration\local-image-build-offload-20261025')
LINUX = '/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/'
NAS = Path(r'\\TRUENAS\plex_smb_share\downloads')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def linux(path):
    return LINUX + path.relative_to(F).as_posix()


def owned_io(path):
    # Change only the Windows I/O spelling, never semantic paths or Linux args.
    path=Path(path)
    need(path.is_absolute() and path.is_relative_to(F) and '..' not in path.parts, 'owned_extended_unc_io')
    text=str(path)
    need(text.startswith('\\\\') and not text.startswith('\\\\?\\'), 'normal_unc_semantics_required')
    return Path('\\\\?\\UNC\\' + text[2:])


def closed_path_failure(reference, digest, run):
    need(reference==run/'path0.json' and run.name=='workernode2', 'exact_closed_path_failure')
    raw=owned_io(reference).read_bytes()
    need(hashlib.sha256(raw).hexdigest()==digest=='99b425348f9398e838bbc5700d62099c794c2d8d96a50fa7cace5e3b4f3b470c', 'closed_path_witness_hash')
    witness=json.loads(raw)
    need(witness['schemaVersion']==1 and witness['scope']=='closed-file-offload-path-carrier-failure' and witness['node']=='workernode2' and witness['errorType']=='FileNotFoundError', 'path_failure_scope')
    need(all(witness[key] is False for key in ('proofCreated','childStarted','fileAttemptsCreated','nativeGuardsFailed')), 'no_submitted_or_native_failure')
    expected={'source':('lock0.py','89a2e78385d481c945fe7cfc0ec05da56bcad533048e155a41ade5aaf25b21ba'),
              'log':('retirement-invocation.log','ebedb8d1e9139d35c4a363e2565a5139cda6f2dc844c0ab54c1a397611b1d2d6'),
              'owner':('nas-lock-operator-ownership.json','6b98c828f8816b5c6745389f9308e62b9dd0c4a9dbb06641315eeca045fca069')}
    payloads={}
    for key,(name,pinned) in expected.items():
        path=run/name
        need(witness[key]['path']==linux(path) and witness[key]['sha256']==pinned, 'original_path_failure_binding')
        payloads[key]=owned_io(path).read_bytes()
        need(hashlib.sha256(payloads[key]).hexdigest()==pinned, 'original_path_failure_evidence_unchanged')
    original=json.loads(payloads['owner'])
    need(original['sourceSHA256']==expected['source'][1] and original['root']==str(run), 'original_owner_binding')
    log=payloads['log'].decode('utf8')
    need("event('nas_read_lock_verified'" in log and "with events.open('a', encoding='utf8')" in log and 'FileNotFoundError: [Errno 2]' in log and 'nas-retirement-lock-events-ddf6f7ba099e4981811561f007ecc492.jsonl' in log, 'exact_pre_child_event_open_failure')
    names={path.name for path in owned_io(run).iterdir()}
    need(not any(name.startswith(('file-','nas-retirement-proof-','retirement-result-')) or re.fullmatch(r'retirement-[0-9a-f]{32}-(operator[.]json|ownership[.]json|ansible-scratch)',name) for name in names), 'no_original_child_or_file_attempt')
    need('nas-retirement-lock-events-ddf6f7ba099e4981811561f007ecc492.jsonl' not in names, 'original_event_write_never_created')
    return {'witness':{'path':str(reference),'sha256':digest},'originalEvidence':witness,'outcome':'closed-controller-path-carrier-before-proof-child-or-file-attempt','nativeGuardFailureReclassified':False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--copy-receipt', type=Path, required=True)
    p.add_argument('--child-operator', type=Path, required=True)
    p.add_argument('--remote-helper', type=Path, required=True)
    p.add_argument('--safety-source', type=Path, required=True)
    p.add_argument('--file-profile', type=Path, required=True)
    p.add_argument('--reviewed-controller-transition', type=Path, required=True)
    p.add_argument('--reviewed-controller-transition-sha256', required=True)
    p.add_argument('--fresh-recovery-checkpoint', type=Path, required=True)
    p.add_argument('--fresh-recovery-checkpoint-sha256', required=True)
    p.add_argument('--after-closed-path-carrier-failure',type=Path)
    p.add_argument('--after-closed-path-carrier-failure-sha256')
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    need(bool(a.after_closed_path_carrier_failure)==bool(a.after_closed_path_carrier_failure_sha256), 'paired_path_closure_required')
    password=sys.stdin.buffer.readline(130).removesuffix(b'\n')
    need(0<len(password)<=128 and not any(x in password for x in (b'\n',b'\r',b'\0')), 'protected_stdin_required')
    need(os.name == 'nt', 'windows_only')
    for path in (a.copy_receipt, a.child_operator, a.remote_helper, a.safety_source):
        need(path.resolve().is_relative_to(F.resolve()) and path.is_file(), 'existing_owned_source')
    need(shutil.disk_usage('C:\\').free >= 15 * 1024**3 and shutil.disk_usage(F).free >= 15 * 1024**3 + 128 * 1024**2, 'controller_space')
    os.environ.update(TEMP=str(F / 'operator-control/tmp'), TMP=str(F / 'operator-control/tmp'))
    copy = json.loads(a.copy_receipt.read_text())
    need(a.file_profile.resolve().is_relative_to(F.resolve()) and a.file_profile.is_file(), 'owned_file_profile')
    need(copy['status']=='completed' and copy['scope']=='closed-file-offload' and copy['completeNASReadbackAuthenticated'] and copy['everyFileIndependentlyRestored'], 'complete_closed_file_backup')
    need(hashlib.sha256(a.file_profile.read_bytes()).hexdigest()==copy['profileSHA256'], 'file_profile_changed')
    profile=json.loads(a.file_profile.read_text());node=profile['node']
    need(node in ('masternode','workernode2') and profile['scope']=='closed-file-offload', 'fixed_node_profile')
    expected=F/'platform-upstream-review-20261027/autonomous-hardening-20261028/closed-file-offload'/node
    need(a.file_profile==expected/'profile.json' and a.copy_receipt==expected/'backup-receipt.json' and a.remote_helper==expected/'offload-frozen.py' and a.safety_source==expected/'safety-frozen.py' and a.child_operator==expected/'runner-frozen.py', 'exact_owned_inputs')
    for path,digest in ((a.reviewed_controller_transition,a.reviewed_controller_transition_sha256),(a.fresh_recovery_checkpoint,a.fresh_recovery_checkpoint_sha256)):
        need(path.resolve().is_relative_to(F.resolve()) and hashlib.sha256(path.read_bytes()).hexdigest()==digest, 'bound_recovery_input')
    restored=expected/'restore-receipt.json';need(hashlib.sha256(restored.read_bytes()).hexdigest()==copy['restoreReceiptSHA256'], 'independent_restore_receipt_changed')
    restore=json.loads(restored.read_text())
    need(restore['status']=='completed' and restore['scratchReconciled'] and restore['everyFileIndependentlyRestored'] and len(restore['restoredFiles'])==len(profile['files']), 'complete_independent_restore')
    need({(row['archiveName'],row['sha256'],row['bytes']) for row in restore['restoredFiles']}=={(row['archiveName'],row['sha256'],row['identity']['size']) for row in profile['files']}, 'restore_exact_file_set')
    archive=Path(copy['archive']);need(archive.name=='sha256-'+copy['archiveSHA256']+'.age', 'content_addressed_archive')
    nas_base=Path(r'\\TRUENAS\plex_smb_share\Branconet-Recovery-Backups\2026-10-25\ciphertexts')
    files=[{'source':{'name':archive.name,'sha256':copy['archiveSHA256']},'nasPath':str(archive),'nasBytes':copy['archiveBytes'],'nasSHA256':copy['archiveSHA256']}]
    need(hashlib.sha256(a.remote_helper.read_bytes()).hexdigest()==copy['helperSHA256'] and hashlib.sha256(a.safety_source.read_bytes()).hexdigest()==copy['safetySHA256'], 'backup_source_binding')
    run = a.copy_receipt.parent
    closure=closed_path_failure(a.after_closed_path_carrier_failure,a.after_closed_path_carrier_failure_sha256,run) if a.after_closed_path_carrier_failure else None
    owner=run/('nas-lock-path-repair-ownership.json' if closure else 'nas-lock-operator-ownership.json')
    need(not owned_io(owner).exists(), 'prior_native_lock_attempt_preserved')
    with owned_io(owner).open('x',encoding='utf8') as out:
        json.dump({'closedPathCarrierFailure':closure,'owner':'closed-file-offload','root':str(run),'physicalUUID':'3c792469-ea0e-4a2c-98e8-1185b141607b','sourceSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'childSHA256':hashlib.sha256(a.child_operator.read_bytes()).hexdigest(),'profileSHA256':copy['profileSHA256'],'backupReceiptSHA256':hashlib.sha256(a.copy_receipt.read_bytes()).hexdigest(),'operation':'NAS immutable read handles plus finite duplicate retirement','protected':'All original prior generations and recovery evidence; per-target refusal cannot be retried'},out,indent=2);out.flush();os.fsync(out.fileno())
    token = uuid.uuid4().hex
    proofpath = run / ('nas-retirement-proof-' + token + '.json')
    events = run / ('nas-retirement-lock-events-' + token + '.jsonl')
    def event(name, **data):
        with owned_io(events).open('a', encoding='utf8') as out:
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
    listener=None
    server=None
    stop=threading.Event()
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
            item['nativeIdentity']=after
            native_stat=target.stat()
            item['nativeStat']={'dev':native_stat.st_dev,'ino':native_stat.st_ino,'mtime_ns':native_stat.st_mtime_ns,'size':native_stat.st_size}
            event('nas_read_lock_verified', index=index, bytes=count, sha256=h.hexdigest())
        listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM);listener.bind(('127.0.0.1',0));listener.listen(4);listener.settimeout(1)
        def serve():
            while not stop.is_set():
                try:connection,_=listener.accept()
                except socket.timeout:continue
                except OSError:return
                with connection:
                    connection.settimeout(5)
                    try:
                        raw=b''
                        while not raw.endswith(b'\n') and len(raw)<=4096:
                            block=connection.recv(4096-len(raw)+1)
                            if not block:break
                            raw+=block
                        need(len(raw)<=4096, 'bounded_lock_challenge')
                        query=json.loads(raw)
                        need(query['token']==token and len(query['nonce'])==32, 'lock_challenge_token')
                        actual=[information(handle) for handle in handles]
                        need(actual==[item['nativeIdentity'] for item in files], 'held_nas_identity_changed')
                        answer={'nonce':query['nonce'],'token':token,'nativePID':os.getpid(),'active':True,'epoch':time.time(),'identities':actual}
                        connection.sendall(json.dumps(answer).encode())
                    except Exception:
                        stop.set()
                        return
        server=threading.Thread(target=serve,daemon=True);server.start()
        proof = {'schema': 1, 'scope':'closed-file-offload','node':node,'lockEndpoint':{'host':'127.0.0.1','port':listener.getsockname()[1]}, 'copyStatus': 'completed', 'copyReceiptSHA256': hashlib.sha256(a.copy_receipt.read_bytes()).hexdigest(),
                 'nasReadLocksHeld': True, 'nasVerificationEpoch': time.time(), 'nativePID': os.getpid(), 'token': token, 'files': files}
        if a.file_profile:
            proof.update(journalCanonicalProfileSHA256=hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                         journalBackup=copy, independentRestoreVerified=True)
        with owned_io(proofpath).open('x', encoding='utf8') as out:
            json.dump(proof, out, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        command = ['wsl', '-d', 'Ubuntu', '-u', 'root', '--cd', '/home/brajam', '--exec', '/usr/sbin/runuser', '-u', 'brajam',
                   '--', '/home/brajam/.local/share/branconet-migration/venv/bin/python3.12', '-B', linux(a.child_operator), '--proof', linux(proofpath),
                   '--remote-helper', linux(a.remote_helper), '--safety-source', linux(a.safety_source), '--node', node,
                   '--reviewed-controller-transition',linux(a.reviewed_controller_transition),'--reviewed-controller-transition-sha256',a.reviewed_controller_transition_sha256,
                   '--fresh-recovery-checkpoint',linux(a.fresh_recovery_checkpoint),'--fresh-recovery-checkpoint-sha256',a.fresh_recovery_checkpoint_sha256]
        if a.apply:
            command.append('--apply')
        if a.file_profile:
            command.extend(['--file-profile', linux(a.file_profile)])
        event('reviewed_child_started', apply=a.apply, nativePID=os.getpid(), proof=str(proofpath))
        child = subprocess.Popen(command,stdin=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
        child.stdin.write(password+b'\n');child.stdin.close();password=None
        status = child.wait()
        need(not stop.is_set(), 'native_lock_challenge_failed')
        need(status == 0, 'retirement_child_failed_original_or_partial_evidence_retained')
        for handle, item in zip(handles, files):
            need(information(handle)==item['nativeIdentity'], 'locked_nas_identity_changed')
        event('child_completed_with_nas_locks_held', apply=a.apply)
        print(json.dumps({'status': 'completed', 'proof': str(proofpath), 'nasFilesPreserved': len(files), 'apply': a.apply}))
    finally:
        password=None
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=30)
        stop.set()
        if listener is not None:listener.close()
        if server is not None:server.join(timeout=6)
        for handle in handles:
            kernel.CloseHandle(handle)
        event('nas_read_locks_released')


if __name__ == '__main__':
    main()
