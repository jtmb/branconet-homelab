"""Create one new build-only ext4 image on F; never format an existing device."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import uuid

BASE = Path('/home/brajam/.local/share/branconet-migration')
PARENT = Path('/mnt/f/branconet-build-storage')
IMAGE = PARENT / 'native-build-20261025.ext4'
MOUNT = BASE / 'local-image-build-offload-20261025'
UUID = '3c792469-ea0e-4a2c-98e8-1185b141607b'
SIZE = 96 * 1024 ** 3


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def run(args, timeout=180):
    p = subprocess.run(args, capture_output=True, timeout=timeout, env={**os.environ, 'LC_ALL': 'C'})
    need(p.returncode == 0 and len(p.stdout) <= 1024 ** 2, 'bounded_storage_operation')
    return p.stdout


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--apply', action='store_true')
    a.add_argument('--mount-existing', action='store_true')
    a.add_argument('--resume-empty-inode', type=int, default=0)
    a.add_argument('--grow-existing-gib', type=int, choices=[128])
    a.add_argument('--grow-existing-inode', type=int, default=0)
    args = a.parse_args()
    need(not args.grow_existing_gib or (IMAGE.exists() and args.resume_empty_inode == 0
         and args.grow_existing_inode > 0), 'explicit_existing_only_growth_identity')
    need(not args.mount_existing or (IMAGE.exists() and args.resume_empty_inode == 0), 'existing_only_mount_never_creates_or_formats')
    need(args.apply and os.getuid() == 0 and 'microsoft' in Path('/proc/sys/kernel/osrelease').read_text().lower(), 'explicit_wsl_storage_scope')
    os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    os.umask(0o077)
    need(PARENT.is_dir() and PARENT.resolve() == PARENT and BASE.is_dir() and BASE.resolve() == BASE, 'exact_existing_parents')
    v = os.statvfs(PARENT)
    # Remounting our already allocated file consumes no second 96 GiB image.
    # Keep the creation estimate separate from the existing-only startup path.
    retained_reserve = 15 * 1024 ** 3
    new_file = not IMAGE.exists()
    estimated_allocation = SIZE if new_file else 0
    need(v.f_bavail * v.f_frsize >= estimated_allocation + retained_reserve,
         'backing_creation_or_existing_mount_retained_reserve')
    if new_file:
        c_free = int(run(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
                          '-NoProfile', '-NonInteractive', '-Command',
                          '(Get-PSDrive C).Free']).decode().strip())
        need(c_free >= retained_reserve, 'new_allocation_windows_c_minimum_15_gib')
    if MOUNT.exists():
        need(MOUNT.resolve() == MOUNT and MOUNT.is_dir(), 'owned_mountpoint_no_alias')
    else:
        MOUNT.mkdir(mode=0o700)
    mounts = json.loads(run(['findmnt', '--json', '--target', str(MOUNT), '--output', 'TARGET,SOURCE,FSTYPE,UUID,OPTIONS']))['filesystems']
    need(len(mounts) == 1, 'single_containing_mount')
    already = mounts[0]['target'] == str(MOUNT)
    created = False
    initialize = False
    if not IMAGE.exists():
        need(not already and not any(MOUNT.iterdir()), 'new_empty_mount_and_backing_file')
        fd = os.open(IMAGE, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            need(stat.S_ISREG(os.fstat(fd).st_mode) and os.fstat(fd).st_nlink == 1, 'new_regular_file_only')
            os.ftruncate(fd, SIZE)
            os.fsync(fd)
        finally:
            os.close(fd)
        created = True
        initialize = True
    elif args.resume_empty_inode:
        s = IMAGE.lstat()
        need(not already and not any(MOUNT.iterdir()) and stat.S_ISREG(s.st_mode)
             and s.st_nlink == 1 and s.st_ino == args.resume_empty_inode and s.st_size == SIZE, 'exact_own_uninitialized_file')
        probe = subprocess.run(['blkid', '-p', '-o', 'export', str(IMAGE)], capture_output=True, timeout=30)
        need(probe.returncode == 2 and not probe.stdout, 'no_existing_filesystem_signature')
        with IMAGE.open('rb') as f:
            need(not any(f.read(1024 ** 2)), 'unchanged_zero_initialized_header')
        initialize = True
    if initialize:
        # -F is restricted to our new regular file, never a block device.
        # Avoid discarding the entire NTFS backing file before formatting.
        run(['mkfs.ext4', '-F', '-q', '-E', 'nodiscard', '-m', '0', '-U', UUID, '-L', 'branconet-build', str(IMAGE)])
    info = IMAGE.lstat()
    need(IMAGE.resolve() == IMAGE and stat.S_ISREG(info.st_mode) and info.st_nlink == 1
         and info.st_size in [SIZE, 128 * 1024**3], 'exact_existing_backing_regular_file')
    fs = run(['blkid', '-p', '-o', 'export', str(IMAGE)]).decode()
    fields = dict(line.split('=', 1) for line in fs.splitlines() if '=' in line)
    need(fields.get('UUID') == UUID and fields.get('TYPE') == 'ext4', 'exact_ext4_backing_identity')
    size_before = info.st_size
    expanded = False
    if args.grow_existing_gib:
        need(not created and not initialize and info.st_ino == args.grow_existing_inode,
             'original_existing_growth_inode')
        target_size = args.grow_existing_gib * 1024**3
        header = run(['dumpe2fs', '-h', str(IMAGE)]).decode()
        header_fields = dict((k.strip(), v.strip()) for k, v in
                             (line.split(':', 1) for line in header.splitlines() if ':' in line))
        fs_bytes = int(header_fields['Block count']) * int(header_fields['Block size'])
        need(0 < fs_bytes <= target_size and info.st_size <= target_size, 'growth_never_shrinks')
        if info.st_size < target_size or fs_bytes < target_size:
            # The operator must first quiesce and normally unmount only this
            # task-owned build filesystem. Never resize through a live loop.
            need(not already and not run(['losetup', '--associated', str(IMAGE)]).strip(),
                 'offline_unmounted_build_filesystem_required')
            lock_path = BASE / 'local-image-build-20261024/host-build.lock'
            lock_info = lock_path.lstat()
            need(lock_path.resolve() == lock_path and stat.S_ISREG(lock_info.st_mode)
                 and lock_info.st_uid == 1000 and lock_info.st_nlink == 1,
                 'existing_operator_build_lock')
            lock_fd = os.open(lock_path, os.O_RDWR | os.O_NOFOLLOW)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                growth = target_size - info.st_size
                physical = os.statvfs(PARENT)
                need(physical.f_bavail * physical.f_frsize >= growth + retained_reserve,
                     'growth_estimate_retains_physical_15_gib')
                c_free = int(run(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
                                 '-NoProfile', '-NonInteractive', '-Command',
                                 '(Get-PSDrive C).Free']).decode().strip())
                need(c_free >= retained_reserve, 'growth_windows_c_minimum_15_gib')
                evidence = BASE / 'local-build-storage-20261025'
                evidence.mkdir(mode=0o700, exist_ok=True)
                run_id = uuid.uuid4().hex
                undo = evidence / ('offline-grow-' + run_id + '.e2undo')
                check = subprocess.run(['e2fsck', '-p', '-f', '-z', str(undo), str(IMAGE)],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                (evidence / ('offline-grow-' + run_id + '.log')).write_bytes(check.stdout)
                need(check.returncode in [0, 1], 'offline_filesystem_check_requires_review')
                if growth:
                    fd = os.open(IMAGE, os.O_RDWR | os.O_NOFOLLOW)
                    try:
                        held = os.fstat(fd)
                        need((held.st_dev, held.st_ino, held.st_size, held.st_nlink)
                             == (info.st_dev, info.st_ino, size_before, 1),
                             'held_original_growth_file')
                        os.ftruncate(fd, target_size)
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                # Metadata writes must finish; observation deadlines must never
                # kill a filesystem resize. The standalone controller owns it.
                run(['resize2fs', str(IMAGE)], timeout=None)
                info = IMAGE.lstat()
                need(info.st_size == target_size and info.st_ino == args.grow_existing_inode,
                     'same_grown_backing_file')
                expanded = True
            finally:
                os.close(lock_fd)
    if not already:
        need(not any(MOUNT.iterdir()), 'no_hidden_existing_mountpoint_data')
        run(['mount', '-o', 'loop,nodev,nosuid', str(IMAGE), str(MOUNT)])
    live = json.loads(run(['findmnt', '--json', '--mountpoint', str(MOUNT), '--output', 'TARGET,SOURCE,FSTYPE,UUID,OPTIONS']))['filesystems']
    need(len(live) == 1 and live[0]['fstype'] == 'ext4' and live[0]['uuid'] == UUID
         and live[0]['source'].startswith('/dev/loop') and {'rw', 'nodev', 'nosuid'} <= set(live[0]['options'].split(',')), 'actual_dedicated_mount')
    loop = json.loads(run(['losetup', '--json', '--list', '--output', 'NAME,BACK-FILE,DIO,LOG-SEC', live[0]['source']]))['loopdevices']
    need(len(loop) == 1 and loop[0]['back-file'] == str(IMAGE), 'actual_loop_backing_file')
    previous_dio = loop[0]['dio']
    need(type(previous_dio) is bool and loop[0]['log-sec'] == 512, 'exact_loop_io_geometry')
    if not previous_dio:
        # Reconfigure only this verified loop, without detaching/unmounting or
        # changing sectors/filesystem/data. The kernel quiesces the I/O queue;
        # unsupported backing files fail instead of weakening capacity guards.
        run(['losetup', '--direct-io=on', live[0]['source']])
    verified_loop = json.loads(run(['losetup', '--json', '--list', '--output', 'NAME,BACK-FILE,DIO,LOG-SEC', live[0]['source']]))['loopdevices']
    need(len(verified_loop) == 1 and verified_loop[0]['back-file'] == str(IMAGE)
         and verified_loop[0]['dio'] is True and verified_loop[0]['log-sec'] == 512,
         'verified_direct_io_mode')
    os.chown(MOUNT, 1000, 1000)
    os.chmod(MOUNT, 0o700)
    out = BASE / 'local-build-storage-20261025'
    out.mkdir(mode=0o700, exist_ok=True)
    os.chown(out, 1000, 1000)
    record = {'created': created, 'passed': True, 'observedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'backingFile': str(IMAGE), 'backingFileBytes': info.st_size, 'backingDevice': info.st_dev, 'backingInode': info.st_ino,
              'filesystemUUID': UUID, 'mount': live[0], 'clusterNodesChanged': False, 'existingProcessesStopped': False,
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    record.update(initialized=initialize, mounted=not already, directIO=True, directIOChanged=not previous_dio,
                  expanded=expanded, backingFileBytesBefore=size_before,
                  nativeFreeBytes=os.statvfs(MOUNT).f_bavail * os.statvfs(MOUNT).f_frsize)
    p = out / ('storage-' + uuid.uuid4().hex + '.json')
    p.write_text(json.dumps(record, sort_keys=True, indent=2) + '\n')
    os.chown(p, 1000, 1000)
    print(json.dumps({**record, 'receipt': str(p), 'receiptSHA256': hashlib.sha256(p.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
