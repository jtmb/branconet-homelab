#!/usr/bin/env python3
"""Deduplicate all bytes of the inactive legacy image and verify a streamed restore.

Never retires the original. No mounts, source extraction, new build or full copy.
"""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
import time

RUN = Path(r'H:\AgentArtifacts\projects\branconet\runs\branconet-wsl-stage-20261113T215208Z')
RAW = Path(r'H:\AgentArtifacts\projects\bortus\builds\native-build-20261025\native-build-20261025.ext4')
REPO = RAW.parent / 'native-build-20261025.restic'
KEY = RUN / 'private' / 'native-image-restic.password'
RECEIPT = RUN / 'SWARM-native-image-restic.json'
EXE = RUN / 'tools' / 'restic-0.19.1' / 'restic.exe'
EXPECTED = 'f3a3dd396d05a9a327199e6cb1f6c56207c24b663882d8aa0dbd7dc06c59d944'
EXE_SHA = 'b0dd1fd21eea5d8fe1325f55f7118213c21f36de8a261e04c0624a5ab9fd7830'
BYTES = 163_208_757_248
CAP = 80_000_000_000
FLOOR = 15 * 1024**3
OTHER_PROJECT = 30_000_000_000


def tree_bytes(path):
    return sum(p.stat().st_size for p in path.rglob('*') if p.is_file())


def main():
    if os.name != 'nt' or RECEIPT.exists() or REPO.exists() or KEY.exists():
        raise RuntimeError('Existing state must be reconciled; do not duplicate preservation')
    if hashlib.sha256(EXE.read_bytes()).hexdigest() != EXE_SHA:
        raise RuntimeError('Pinned official Restic binary changed')
    if RAW.is_symlink() or RAW.stat().st_size != BYTES or RAW.stat().st_nlink != 1:
        raise RuntimeError('Original identity differs')
    if shutil.disk_usage('C:/').free < FLOOR or shutil.disk_usage('H:/').free - CAP - OTHER_PROJECT < FLOOR:
        raise RuntimeError('Combined physical peak does not fit')
    associated = subprocess.check_output(['wsl.exe', '-d', 'Ubuntu', '-u', 'root', '--exec',
        '/usr/sbin/losetup', '--associated', str(RAW).replace('H:', '/mnt/h').replace('\\', '/')], text=True)
    if associated.strip():
        raise RuntimeError('Original is mounted/loop-associated')
    metadata = json.loads(subprocess.check_output(['pwsh.exe', '-NoProfile', '-Command',
        "$p='" + str(RAW) + "'; $f=Get-Item -LiteralPath $p; [pscustomobject]@{sddl=(Get-Acl -LiteralPath $p).Sddl; creationUtc=$f.CreationTimeUtc.ToString('o'); lastWriteUtc=$f.LastWriteTimeUtc.ToString('o'); attributes=[int]$f.Attributes; streams=@(Get-Item -LiteralPath $p -Stream * | Select-Object Stream,Length)} | ConvertTo-Json -Compress"], text=True))
    if len(metadata['streams']) != 1 or metadata['streams'][0]['Stream'] != ':$DATA':
        raise RuntimeError('Additional original streams need preservation')
    KEY.parent.mkdir(exist_ok=True)
    KEY.write_text(secrets.token_urlsafe(48) + '\n')
    subprocess.run(['pwsh.exe', '-NoProfile', '-Command',
        "$p='" + str(KEY) + "'; $a=New-Object System.Security.AccessControl.FileSecurity; $sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User; $a.SetOwner($sid); $a.SetAccessRuleProtection($true,$false); $a.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($sid,'FullControl','Allow'))); Set-Acl -LiteralPath $p -AclObject $a"], check=True, capture_output=True)
    env = os.environ.copy()
    env.update(TEMP=str(RUN / 'temp'), TMP=str(RUN / 'temp'), TMPDIR=str(RUN / 'temp'),
               RESTIC_REPOSITORY=str(REPO), RESTIC_PASSWORD_FILE=str(KEY), GOMAXPROCS='2')
    base = [str(EXE), '--no-cache']
    record = dict(owner='BORTUS Delivery and Cluster Operations', state='initializing',
        raw_source=str(RAW), raw_bytes=BYTES, source_sha256_expected=EXPECTED,
        repository=str(REPO), password_file=str(KEY), source_metadata=metadata,
        repository_cap_bytes=CAP, other_project_reservation=OTHER_PROJECT,
        restic_version='0.19.1', restic_exe_sha256=EXE_SHA,
        source_removed=False, new_mount=False, new_build=False,
        remaining_consumer='Full recovery of mixed legacy members until owner reconciliation preserves unique source/data/failure evidence',
        end_condition='Retire this capsule only after every retained member has verified replacement or proven regeneration',
        restore_recipe='Use the pinned restic executable, repository and protected password file with dump <snapshot> /native-build-20261025.ext4 --target <admitted recovery path>; verify restored SHA256 and length, then restore recorded SDDL/timestamps. Never pipe binary through text PowerShell redirection.')
    def save():
        RECEIPT.write_text(json.dumps(record, indent=2) + '\n')
    save()
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(RAW), 0x80000000, 1, None, 3, 0x08000000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    import msvcrt
    fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    stopped = threading.Event()
    child = None
    def watch():
        while not stopped.wait(2):
            if tree_bytes(REPO) > CAP or shutil.disk_usage('H:/').free < OTHER_PROJECT + FLOOR:
                record['failure'] = 'Owned backup stopped at bounded repository/physical reserve'
                if child is not None and child.poll() is None:
                    child.terminate()
                return
    try:
        subprocess.run(base + ['init', '--repository-version', '2'], env=env,
                       check=True, capture_output=True, timeout=30)
        record['state'] = 'backing-up'
        save()
        with os.fdopen(fd, 'rb', buffering=0) as source, \
             (RUN / 'SWARM-native-image-restic-backup.jsonl').open('w') as log, \
             (RUN / 'SWARM-native-image-restic-backup.stderr').open('w') as err:
            child = subprocess.Popen(base + ['--json', 'backup', '--stdin', '--stdin-filename', RAW.name,
                '--tag', 'mixed-legacy-full-byte-preservation', '--no-scan'], stdin=subprocess.PIPE,
                stdout=log, stderr=err, env=env)
            watcher = threading.Thread(target=watch, daemon=True)
            watcher.start()
            digest = hashlib.sha256()
            count = 0
            while data := source.read(8 * 1024**2):
                child.stdin.write(data)
                digest.update(data)
                count += len(data)
            child.stdin.close()
            code = child.wait()
            if code or count != BYTES or digest.hexdigest() != EXPECTED:
                raise RuntimeError('Backup/source checksum did not pass')
        summary = [json.loads(line) for line in (RUN / 'SWARM-native-image-restic-backup.jsonl').read_text().splitlines()
                   if '"message_type":"summary"' in line or '"message_type": "summary"' in line][-1]
        snapshot = summary['snapshot_id']
        record.update(state='verifying-full-restore', snapshot=snapshot,
                      source_sha256=digest.hexdigest(), backup_summary=summary)
        save()
        with (RUN / 'SWARM-native-image-restic-restore.stderr').open('w') as err:
            child = subprocess.Popen(base + ['dump', snapshot, '/' + RAW.name], env=env,
                                     stdout=subprocess.PIPE, stderr=err)
            restored = hashlib.sha256()
            restored_bytes = 0
            while data := child.stdout.read(8 * 1024**2):
                restored.update(data)
                restored_bytes += len(data)
            if child.wait() or restored_bytes != BYTES or restored.hexdigest() != EXPECTED:
                raise RuntimeError('Exact full-byte reconstructed restore failed')
        record.update(state='verified-original-retained', reconstructed_sha256=restored.hexdigest(),
            reconstructed_bytes=restored_bytes, repository_bytes=tree_bytes(REPO),
            h_free_after=shutil.disk_usage('H:/').free, verified_unix=time.time())
        save()
        print(json.dumps({k:record[k] for k in ['state','snapshot','repository_bytes','reconstructed_bytes','reconstructed_sha256']}))
    except BaseException as error:
        record.update(state='failed-original-retained', error=type(error).__name__ + ': ' + str(error))
        save()
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait()
        raise
    finally:
        stopped.set()
        # fd normally belongs to the source context; close if init failed first.
        try:
            os.close(fd)
        except OSError:
            pass


if __name__ == '__main__':
    main()
