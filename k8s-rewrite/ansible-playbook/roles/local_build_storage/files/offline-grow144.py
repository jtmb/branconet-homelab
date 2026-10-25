"""Explicit root-only 128 -> 144 GiB offline growth; frozen outside the mount."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import uuid

BASE = Path('/home/brajam/.local/share/branconet-migration')
OUTSIDE = BASE / 'local-build-storage-20261025'
MOUNT = BASE / 'local-image-build-offload-20261025'
IMAGE = Path('/mnt/f/branconet-build-storage/native-build-20261025.ext4')
LOCK = BASE / 'local-image-build-20261024/host-build.lock'
FS_UUID = '3c792469-ea0e-4a2c-98e8-1185b141607b'
INODE = 115123265474727363
GIB = 1024 ** 3
AGE = BASE / 'bin/age'
KEY = Path('/home/brajam/.ssh/id_ed25519')
AGE_SHA = 'eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c'


def need(ok, code):
    if not ok:
        raise ValueError(code)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def run(argv):
    # No timeout for mount/filesystem metadata writes: never kill them mid-write.
    p = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True)
    need(p.returncode == 0 and len(p.stdout) <= 1024 ** 2, 'operation_' + Path(argv[0]).name)
    return p.stdout


def identity(path):
    s = path.lstat()
    need(path.resolve() == path and stat.S_ISREG(s.st_mode) and s.st_nlink == 1,
         'preserved_regular_file')
    return {'inode': s.st_ino, 'bytes': s.st_size, 'mode': stat.S_IMODE(s.st_mode),
            'uid': s.st_uid, 'gid': s.st_gid, 'mtime_ns': s.st_mtime_ns}


def loop_state():
    rows = json.loads(run(['losetup', '--json', '--list', '--output',
                          'NAME,BACK-FILE,DIO,LOG-SEC']))['loopdevices']
    return [r for r in rows if r['back-file'] == str(IMAGE)]


def mount_state(size):
    rows = json.loads(run(['findmnt', '--json', '--mountpoint', str(MOUNT), '--output',
                          'TARGET,SOURCE,FSTYPE,UUID,OPTIONS']))['filesystems']
    need(len(rows) == 1, 'single_mount')
    m = rows[0]
    need(m['target'] == str(MOUNT) and m['fstype'] == 'ext4' and m['uuid'] == FS_UUID
         and {'rw', 'nodev', 'nosuid'} <= set(m['options'].split(',')), 'mount_identity')
    loops = loop_state()
    need(len(loops) == 1 and loops[0]['name'] == m['source']
         and re.fullmatch('/dev/loop[0-9]+', m['source'])
         and loops[0]['dio'] is True and loops[0]['log-sec'] == 512, 'loop_identity')
    s = IMAGE.lstat()
    need(IMAGE.resolve() == IMAGE and stat.S_ISREG(s.st_mode) and s.st_nlink == 1
         and s.st_ino == INODE and s.st_size == size, 'backing_identity')
    header = run(['dumpe2fs', '-h', m['source']]).decode()
    fields = dict((k.strip(), v.strip()) for k, v in
                  (line.split(':', 1) for line in header.splitlines() if ':' in line))
    need(fields.get('Filesystem UUID') == FS_UUID
         and int(fields['Block count']) * int(fields['Block size']) == size,
         'filesystem_geometry')
    return {'mount': m, 'loop': loops[0], 'backing': identity(IMAGE)}


def idle():
    # Root observes all processes, without emitting command lines, FDs or maps.
    # Normal umount supplies the final kernel busy/reference check.
    device = MOUNT.stat().st_dev
    offenders = set()
    build_names = {'buildkitd', 'buildctl', 'docker-buildx',
                   'local-build-offloaded-image.py', 'local-build-security-image.py'}
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal():
            continue
        try:
            comm = (p / 'comm').read_text().strip()
            argv = (p / 'cmdline').read_bytes().split(b'\0')
            if comm in build_names or any(Path(os.fsdecode(a)).name in build_names for a in argv if a):
                offenders.add(int(p.name))
            for link in [p / 'cwd', p / 'root', p / 'exe']:
                try:
                    if link.stat().st_dev == device:
                        offenders.add(int(p.name))
                except FileNotFoundError:
                    pass
            for fd in (p / 'fd').iterdir():
                try:
                    if fd.stat().st_dev == device:
                        offenders.add(int(p.name))
                except FileNotFoundError:
                    pass
            for line in (p / 'maps').read_text().splitlines():
                fields = line.split(None, 5)
                major, minor = fields[3].split(':')
                if os.makedev(int(major, 16), int(minor, 16)) == device:
                    offenders.add(int(p.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            need(False, 'process_reference_visibility')
    need(not offenders, 'active_process_or_build_references_count_' + str(len(offenders)))
    # Reject nested mounts without enumerating or modifying their contents.
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        target = line.split()[4]
        need(not target.startswith(str(MOUNT) + '/'), 'nested_mount')


def preserve(manifest):
    result = []
    for row in manifest['files']:
        p = Path(row['path'])
        need(p == KEY or p == KEY.with_suffix('.pub') or MOUNT in p.parents,
             'finite_preservation_path')
        before = identity(p)
        need(before == row['identity'] and sha(p) == row['sha256'], 'preservation_hash_or_metadata')
        if row.get('age_authenticated'):
            child = subprocess.Popen([str(AGE), '-d', '-i', str(KEY), str(p)],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL)
            count = 0
            for block in iter(lambda: child.stdout.read(1024 * 1024), b''):
                count += len(block)
                # age is encryption, not decompression: plaintext is bounded by
                # the pinned ciphertext length; drain fully for authentication.
            child.stdout.close()
            need(child.wait() == 0 and 0 < count <= before['bytes'] <= 20 * GIB,
                 'complete_age_authentication')
        need(identity(p) == before, 'preservation_read_race')
        result.append({'name': row['name'], 'hash_and_metadata_equal': True,
                       'complete_age_authentication': bool(row.get('age_authenticated'))})
    return result


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('--apply', action='store_true')
    a.add_argument('--source-manifest-sha256', required=True)
    args = a.parse_args()
    need(args.apply and os.getuid() == 0, 'explicit_root_apply')
    os.umask(0o077)
    os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    os.environ['PATH'] = '/usr/sbin:/usr/bin:/sbin:/bin'
    os.environ['LC_ALL'] = 'C'
    source = Path(__file__).resolve().parent
    need(OUTSIDE in source.parents and MOUNT not in source.parents
         and source.stat().st_dev != MOUNT.stat().st_dev
         and Path.cwd() != MOUNT and MOUNT not in Path.cwd().parents, 'outside_source_and_cwd')
    mp = source / 'source-manifest.json'
    need(sha(mp) == args.source_manifest_sha256, 'frozen_manifest_binding')
    files = json.loads(mp.read_bytes())
    for name, row in files.items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'source_relative_path')
        p = source / name
        need(p.resolve() == p and p.stat().st_size == row['size'] and sha(p) == row['sha256'],
             'frozen_source_hash')
    need({'offline-grow144.py', 'setup.py', 'preservation-inputs.json'} <= set(files), 'source_allowlist')
    # Publish the same fenced existing-only startup helper before quiescence.
    # An old unfenced keeper must not remount between detach and resize.
    installed = Path('/usr/local/libexec/branconet-migration/mount-build-storage.py')
    ii = installed.lstat()
    need(installed.resolve() == installed and stat.S_ISREG(ii.st_mode) and ii.st_uid == 0
         and not ii.st_mode & 0o077 and sha(installed) == files['setup.py']['sha256'],
         'installed_remount_helper_same_fenced_source')
    manifest = json.loads((source / 'preservation-inputs.json').read_bytes())
    need(sha(AGE) == AGE_SHA and os.access(AGE, os.X_OK), 'pinned_age')
    li = LOCK.lstat()
    need(LOCK.resolve() == LOCK and stat.S_ISREG(li.st_mode) and li.st_uid == 1000
         and li.st_nlink == 1, 'existing_build_lock')
    lock = os.open(LOCK, os.O_RDWR | os.O_NOFOLLOW)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    need((os.fstat(lock).st_dev, os.fstat(lock).st_ino) == (li.st_dev, li.st_ino), 'held_build_lock')
    record = {'status': 'started', 'source_manifest_sha256': args.source_manifest_sha256,
              'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'operation': 'preflight', 'no_processes_stopped': True,
              'no_caches_or_artifacts_deleted': True}
    receipt = OUTSIDE / ('offline-grow144-' + uuid.uuid4().hex + '.json')
    def save():
        receipt.write_text(json.dumps(record, sort_keys=True, indent=2) + '\n')
        receipt.chmod(0o600)
        os.chown(receipt, 1000, 1000)
    save()
    try:
        before = mount_state(128 * GIB)
        record['before'] = before
        idle()
        need(os.statvfs(IMAGE.parent).f_bavail * os.statvfs(IMAGE.parent).f_frsize >= 31 * GIB,
             'physical_f_growth_retains_15_gib')
        c_free = int(run(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
                          '-NoProfile', '-NonInteractive', '-Command', '(Get-PSDrive C).Free']).strip())
        need(c_free >= 15 * GIB, 'windows_c_15_gib')
        record['windows_c_free_before'] = c_free
        record['operation'] = 'before_preservation'; save()
        record['preserved_before'] = preserve(manifest)
        idle()
        need(mount_state(128 * GIB) == before, 'pre_unmount_identity')
        record['operation'] = 'normal_unmount'; save()
        run(['umount', str(MOUNT)])
        need(not MOUNT.is_mount(), 'unmounted_only_owned_mount')
        associated = loop_state()
        if associated:
            need(len(associated) == 1 and associated[0] == before['loop'], 'same_detach_loop')
            run(['losetup', '--detach', before['loop']['name']])
        need(not loop_state(), 'backing_fully_detached')
        need(not any(MOUNT.iterdir()), 'unmounted_directory_empty')
        record['operation'] = 'offline_check_growth_remount'; save()
        child = subprocess.run(['/usr/bin/python3', '-B', str(source / 'setup.py'), '--apply',
                                '--grow-existing-gib', '144', '--grow-existing-inode', str(INODE),
                                '--offline-lock-fd', str(lock)], pass_fds=(lock,),
                               stdin=subprocess.DEVNULL, capture_output=True)
        (receipt.with_suffix('.setup.stdout')).write_bytes(child.stdout)
        (receipt.with_suffix('.setup.stderr')).write_bytes(child.stderr)
        need(child.returncode == 0, 'setup_failed_retain_offline_state_for_review')
        record['setup_receipt'] = json.loads(child.stdout)
        after = mount_state(144 * GIB)
        need({k: v for k, v in after['backing'].items() if k not in ['bytes', 'mtime_ns']}
             == {k: v for k, v in before['backing'].items() if k not in ['bytes', 'mtime_ns']},
             'original_inode_owner_mode_preserved')
        record['after'] = after
        record['operation'] = 'after_preservation'; save()
        record['preserved_after'] = preserve(manifest)
        need(record['preserved_before'] == record['preserved_after'], 'same_preserved_inputs')
        record['native_free_after'] = os.statvfs(MOUNT).f_bavail * os.statvfs(MOUNT).f_frsize
        need(record['native_free_after'] >= 27 * GIB, 'next_12_gib_build_retains_15_gib')
        record['status'] = 'completed'
        record['operation'] = 'same_inode_growth_and_preservation_verified'
    except Exception as error:
        record['status'] = 'failed'
        record['error_type'] = type(error).__name__
        record['reason'] = str(error) if isinstance(error, ValueError) else 'operation_failed_details_private'
        raise
    finally:
        record['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()
        os.close(lock)
        print(json.dumps({'status': record['status'], 'operation': record['operation'],
                          'receipt': str(receipt), 'receipt_sha256': sha(receipt)}))


if __name__ == '__main__':
    main()
