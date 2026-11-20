#!/usr/bin/env python3
"""Online inode growth of the existing sparse H filesystem, without relocation."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

BACKING = Path(r'H:\AgentArtifacts\projects\branconet\builds\wsl-artifact-store\branconet-artifacts.ext4')
WSL_BACKING = '/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/branconet-artifacts.ext4'
MOUNT = '/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files'
RUN = Path(r'H:\AgentArtifacts\projects\branconet\runs\branconet-wsl-stage-20261113T215208Z')
RECEIPT = RUN / 'SWARM-docker-H-sparse-inode-growth.json'
OLD = 384 * 1024**3
NEW = 2560 * 1024**3
RESERVED_OTHER_PROJECT = 30_000_000_000
RESERVED_PRESERVATION = 80_000_000_000
FLOOR = 15 * 1024**3
METADATA_BUDGET = 8 * 1024**3


def linux(*args):
    if args[0] in ('losetup', 'blkid', 'resize2fs'):
        args = ('/usr/sbin/' + args[0], *args[1:])
    return subprocess.check_output(['wsl.exe', '-d', 'Ubuntu', '-u', 'root', '--exec', *args], text=True).strip()


def allocated(path):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    fn = kernel.GetCompressedFileSizeW
    fn.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    fn.restype = wintypes.DWORD
    high = wintypes.DWORD()
    ctypes.set_last_error(0)
    low = fn(str(path), ctypes.byref(high))
    if low == 0xffffffff and ctypes.get_last_error():
        raise ctypes.WinError(ctypes.get_last_error())
    return (high.value << 32) | low


def set_eof(size):
    # Python's Windows truncate uses _chsize_s, which writes zero buffers when
    # extending. Use native EOF directly so a sparse extension stays unallocated.
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                             ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    k.CreateFileW.restype = wintypes.HANDLE
    k.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong, ctypes.c_void_p, wintypes.DWORD]
    k.SetEndOfFile.argtypes = [wintypes.HANDLE]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    h = k.CreateFileW(str(BACKING), 0x40000000, 3, None, 3, 0, None)
    if h == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not k.SetFilePointerEx(h, size, None, 0) or not k.SetEndOfFile(h):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        k.CloseHandle(h)


def recover_unused_extension():
    r = json.loads(RECEIPT.read_text())
    if r['state'] != 'preflight-passed' or linux('/usr/sbin/blockdev', '--getsize64', '/dev/loop0') != str(OLD):
        raise RuntimeError('Device was resized; do not truncate')
    if not OLD <= BACKING.stat().st_size < NEW:
        raise RuntimeError('Unexpected partial extension')
    r['interrupted_python_truncate'] = dict(partial_length=BACKING.stat().st_size,
        physical_before_recovery=allocated(BACKING), device_bytes=OLD,
        reason='Python _chsize_s zero-filled unused extension; own helper stopped before loop/FS resize')
    set_eof(OLD)
    r['interrupted_python_truncate']['physical_after_recovery'] = allocated(BACKING)
    r['state'] = 'preflight-zero-fill-recovered'
    RECEIPT.write_text(json.dumps(r, indent=2) + '\n')
    print(json.dumps({'state': r['state'], 'logical_bytes': BACKING.stat().st_size,
                      'h_free': shutil.disk_usage('H:/').free}))


def main():
    previous = json.loads(RECEIPT.read_text()) if RECEIPT.exists() else {}
    if os.name != 'nt' or previous.get('state') not in (None, 'preflight-zero-fill-recovered'):
        raise RuntimeError('Use Windows; reconcile an existing receipt instead of repeating growth')
    before = BACKING.stat()
    attrs = ctypes.windll.kernel32.GetFileAttributesW(str(BACKING))
    if before.st_size != OLD or BACKING.is_symlink() or not attrs & 0x200:
        raise RuntimeError('Expected existing 384GiB sparse file only')
    if linux('losetup', '-n', '-O', 'BACK-FILE', '/dev/loop0') != WSL_BACKING:
        raise RuntimeError('Loop device identity changed')
    if linux('findmnt', '-T', MOUNT, '-n', '-o', 'SOURCE,FSTYPE') != '/dev/loop0 ext4':
        raise RuntimeError('Existing mount identity changed')
    if linux('blkid', '-s', 'UUID', '-o', 'value', '/dev/loop0') != 'e4c3cddc-ace6-4f27-a8b8-23278c17b53f':
        raise RuntimeError('Filesystem identity changed')
    host_free = shutil.disk_usage('H:/').free
    if min(shutil.disk_usage('C:/').free, host_free) < FLOOR:
        raise RuntimeError('Physical reserve unavailable')
    if host_free - RESERVED_OTHER_PROJECT - RESERVED_PRESERVATION - METADATA_BUDGET < FLOOR:
        raise RuntimeError('Combined physical peak does not fit')
    baseline_alloc = allocated(BACKING)
    record = dict(owner='BORTUS Delivery and Cluster Operations', state='preflight-passed',
                  backing=str(BACKING), mount=MOUNT, uuid='e4c3cddc-ace6-4f27-a8b8-23278c17b53f',
                  old_logical_bytes=OLD, new_logical_bytes=NEW, physical_before=baseline_alloc,
                  h_free_before=host_free, metadata_budget=METADATA_BUDGET,
                  other_project_reservation=RESERVED_OTHER_PROJECT,
                  preservation_reservation=RESERVED_PRESERVATION,
                  new_disk=False, new_mount=False, services_stopped=False)
    if previous.get('interrupted_python_truncate'):
        record['interrupted_python_truncate'] = previous['interrupted_python_truncate']
    def save():
        RECEIPT.write_text(json.dumps(record, indent=2) + '\n')
    save()
    set_eof(NEW)
    with BACKING.open('rb', buffering=0) as f:
        delta = allocated(BACKING) - baseline_alloc
        f.seek(NEW - 4096)
        tail = f.read(4096)
        if delta > 1024**2 or tail != bytes(4096):
            # No device/FS resize has occurred: rollback only our unused extension.
            set_eof(OLD)
            record.update(state='extension-reverted-before-device-resize', extension_allocation_delta=delta)
            save()
            raise RuntimeError('Sparse extension did not remain unallocated')
    record.update(state='sparse-extension-verified', extension_allocation_delta=delta)
    save()
    # DrvFS can cache the old inode size across the native Windows EOF update.
    # Refresh that view and verify the loop capacity before resizing ext4.
    for attempt in range(3):
        if linux('/usr/bin/stat', '-c', '%s', WSL_BACKING) != str(NEW):
            raise RuntimeError('DrvFS has not observed the sparse EOF update')
        linux('losetup', '--set-capacity', '/dev/loop0')
        if linux('/usr/sbin/blockdev', '--getsize64', '/dev/loop0') == str(NEW):
            break
        time.sleep(1)
    else:
        record['state'] = 'sparse-extension-device-capacity-pending'
        save()
        raise RuntimeError('Device capacity has not observed new EOF; no filesystem resize attempted')
    record['state'] = 'online-resize-running'
    save()
    with (RUN / 'SWARM-docker-H-sparse-inode-growth.log').open('w') as log:
        subprocess.run(['wsl.exe', '-d', 'Ubuntu', '-u', 'root', '--exec',
                        '/usr/sbin/resize2fs', '/dev/loop0'], stdout=log, stderr=log, check=True)
    stat = json.loads(linux('python3', '-B', '-c',
        'import os,json; s=os.statvfs(' + repr(MOUNT) + '); print(json.dumps(dict(inodes=s.f_files,free_inodes=s.f_favail,free_bytes=s.f_bavail*s.f_frsize)))'))
    record.update(state='verification-pending', filesystem=stat, physical_after=allocated(BACKING),
                  h_free_after=shutil.disk_usage('H:/').free, completed_unix=time.time())
    record['physical_growth_bytes'] = record['physical_after'] - baseline_alloc
    save()
    if stat['free_inodes'] < 1_000_000 or record['physical_growth_bytes'] > METADATA_BUDGET:
        raise RuntimeError('Growth completed; observed admission bounds require reconciliation')
    record['state'] = 'completed'
    save()
    print(json.dumps(record))


if __name__ == '__main__':
    if sys.argv[1:] == ['--recover-unused-extension']:
        recover_unused_extension()
    else:
        main()
