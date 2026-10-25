"""Create one new build-only ext4 image on F; never format an existing device."""
import argparse
import datetime
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


def run(args):
    p = subprocess.run(args, capture_output=True, timeout=180, env={**os.environ, 'LC_ALL': 'C'})
    need(p.returncode == 0 and len(p.stdout) <= 1024 ** 2, 'bounded_storage_operation')
    return p.stdout


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--apply', action='store_true')
    a.add_argument('--mount-existing', action='store_true')
    a.add_argument('--resume-empty-inode', type=int, default=0)
    args = a.parse_args()
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
    need(IMAGE.resolve() == IMAGE and stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size == SIZE, 'exact_existing_backing_regular_file')
    fs = run(['blkid', '-p', '-o', 'export', str(IMAGE)]).decode()
    fields = dict(line.split('=', 1) for line in fs.splitlines() if '=' in line)
    need(fields.get('UUID') == UUID and fields.get('TYPE') == 'ext4', 'exact_ext4_backing_identity')
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
              'backingFile': str(IMAGE), 'backingFileBytes': SIZE, 'backingDevice': info.st_dev, 'backingInode': info.st_ino,
              'filesystemUUID': UUID, 'mount': live[0], 'clusterNodesChanged': False, 'existingProcessesStopped': False,
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    record.update(initialized=initialize, mounted=not already, directIO=True, directIOChanged=not previous_dio)
    p = out / ('storage-' + uuid.uuid4().hex + '.json')
    p.write_text(json.dumps(record, sort_keys=True, indent=2) + '\n')
    os.chown(p, 1000, 1000)
    print(json.dumps({**record, 'receipt': str(p), 'receiptSHA256': hashlib.sha256(p.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
