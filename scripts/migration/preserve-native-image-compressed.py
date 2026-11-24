#!/usr/bin/env python3
"""Losslessly preserve an inactive legacy carrier; never remove its raw source."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

SOURCE = Path(r'H:\AgentArtifacts\projects\bortus\builds\native-build-20261025\native-build-20261025.ext4')
TARGET = SOURCE.with_suffix('.ext4.zst')
PARTIAL = SOURCE.with_suffix('.ext4.zst.partial')
RUN = Path(r'H:\AgentArtifacts\projects\branconet\runs\branconet-wsl-stage-20261113T215208Z')
RECEIPT = RUN / 'SWARM-native-image-capsule.json'
EXPECTED = 'f3a3dd396d05a9a327199e6cb1f6c56207c24b663882d8aa0dbd7dc06c59d944'
MAX_COMPRESSED = 48_000_000_000
WORKER = r'''
import sys,hashlib,json
from compression import zstd
if sys.argv[1]=='compress':
 with zstd.ZstdFile(sys.stdout.buffer,'wb',level=1) as f:
  while b:=sys.stdin.buffer.read(8*1024**2):f.write(b)
else:
 h=hashlib.sha256();n=0
 with zstd.ZstdFile(sys.stdin.buffer,'rb') as f:
  while b:=f.read(8*1024**2):h.update(b);n+=len(b)
 print(json.dumps({'sha256':h.hexdigest(),'bytes':n}))
'''
COMMAND = ['wsl.exe', '-d', 'Ubuntu', '-u', 'brajam', '--cd', '/home/brajam',
           '--exec', 'python3', '-B', '-u', '-c', WORKER]


def main():
    if os.name != 'nt':
        raise RuntimeError('Use the native Windows controller for H file access')
    if any(p.exists() for p in (TARGET, PARTIAL, RECEIPT)):
        raise RuntimeError('Existing capsule state must be reconciled, not overwritten')
    source_stat = SOURCE.stat()
    if source_stat.st_size != 163_208_757_248 or source_stat.st_nlink != 1 or SOURCE.is_symlink():
        raise RuntimeError('Original carrier identity differs')
    if shutil.disk_usage('H:/').free < MAX_COMPRESSED + 15 * 1024**3 or shutil.disk_usage('C:/').free < 15 * 1024**3:
        raise RuntimeError('Preservation peak/reserve does not fit')
    associated = subprocess.check_output(['wsl.exe', '-d', 'Ubuntu', '-u', 'root', '--cd', '/home/brajam',
        '--exec', '/usr/sbin/losetup', '--associated', str(SOURCE).replace('H:', '/mnt/h').replace('\\', '/')], text=True)
    if associated.strip():
        raise RuntimeError('Raw carrier is still associated with a loop device')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    # Permit other readers, but no concurrent writer or deletion of this source.
    handle = kernel.CreateFileW(str(SOURCE), 0x80000000, 1, None, 3, 0x08000000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    import msvcrt
    fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    record = {'owner': 'BORTUS Delivery and Cluster Operations', 'state': 'compressing',
        'source': str(SOURCE), 'target': str(TARGET), 'source_bytes': source_stat.st_size,
        'source_stat': {'device': source_stat.st_dev, 'inode': source_stat.st_ino,
                       'mtime_ns': source_stat.st_mtime_ns, 'ctime_ns': source_stat.st_ctime_ns},
        'purpose': 'Full-byte preservation of all unknown source, data and metadata; no member deletion',
        'maximum_capsule_bytes': MAX_COMPRESSED, 'raw_source_removed': False,
        'restore_recipe': 'Stream this .zst through Python3.14 compression.zstd.ZstdFile into the original raw path only after a separately admitted recovery capacity check; compare reconstructed SHA256 and bytes with this receipt.',
        'consumer': 'Lossless legacy member reconciliation and recovery; retire carrier only after all required members are mapped and preserved',
        'new_mount': False, 'new_build': False}
    def save():
        RECEIPT.write_text(json.dumps(record, indent=2) + '\n')
    save()
    failed = []
    h = hashlib.sha256()
    with os.fdopen(fd, 'rb') as source, (RUN / 'logs' / 'SWARM-native-image-codec.log').open('ab') as log:
        output = PARTIAL.open('xb')
        acl = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
            "$ErrorActionPreference='Stop'; $a=Get-Acl -LiteralPath '" + str(SOURCE) + "'; "
            "Set-Acl -LiteralPath '" + str(PARTIAL) + "' -AclObject $a; "
            "$f=Get-Item -LiteralPath '" + str(SOURCE) + "'; "
            "[pscustomobject]@{sddl=$a.Sddl;creationUtc=$f.CreationTimeUtc.ToString('o');"
            "lastWriteUtc=$f.LastWriteTimeUtc.ToString('o');attributes=[int]$f.Attributes}|ConvertTo-Json -Compress"],
            check=True, capture_output=True, text=True)
        record['source_windows_metadata'] = json.loads(acl.stdout)
        save()
        process = subprocess.Popen(COMMAND + ['compress'], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=log)
        def consume():
            try:
                total = 0
                with output:
                    for raw in iter(lambda: process.stdout.read(1024 * 1024), b''):
                        total += len(raw)
                        if total > MAX_COMPRESSED:
                            raise RuntimeError('Capsule exceeds bounded preservation peak')
                        if total % (64 * 1024 * 1024) < len(raw) and shutil.disk_usage('H:/').free < 15 * 1024**3:
                            raise RuntimeError('H reserve reached; preserve original and stop only this codec')
                        output.write(raw)
                    output.flush()
                    os.fsync(output.fileno())
                record['capsule_bytes'] = total
            except BaseException as exc:
                failed.append(type(exc).__name__)
                process.kill()
        reader = threading.Thread(target=consume)
        reader.start()
        try:
            count = 0
            for raw in iter(lambda: source.read(8 * 1024 * 1024), b''):
                h.update(raw)
                count += len(raw)
                process.stdin.write(raw)
            process.stdin.close()
            code = process.wait()
            reader.join()
            if code or failed or count != source_stat.st_size or h.hexdigest() != EXPECTED:
                raise RuntimeError('Source identity or compression did not verify')
            current = SOURCE.stat()
            if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (
                    source_stat.st_dev, source_stat.st_ino, source_stat.st_size, source_stat.st_mtime_ns):
                raise RuntimeError('Original source changed')
            record.update(state='verifying', source_sha256=h.hexdigest(), source_bytes_read=count)
            save()
            with PARTIAL.open('rb') as compressed:
                verify = subprocess.run(COMMAND + ['verify'], stdin=compressed,
                    stdout=subprocess.PIPE, stderr=log, check=True, text=True)
            actual = json.loads(verify.stdout)
            if actual != {'sha256': h.hexdigest(), 'bytes': count}:
                raise RuntimeError('Reconstructed capsule differs from the entire raw image')
            if TARGET.exists():
                raise RuntimeError('Destination appeared; preserve both files')
            PARTIAL.rename(TARGET)
            record.update(state='verified-preservation', reconstructed=actual,
                          completed_unix=time.time(), raw_source_removed=False)
            save()
            print(json.dumps({'state': record['state'], 'source_bytes': count,
                              'capsule_bytes': record['capsule_bytes'], 'exact_reconstruction': True}), flush=True)
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait()
            reader.join()
            record.update(state='failed-preserve-original', source_sha256=h.hexdigest())
            save()
            raise


if __name__ == '__main__':
    main()
