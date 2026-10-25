"""Resume one failed 144 GiB growth only after natural, complete loop detachment."""
import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import uuid

OUTSIDE = Path('/home/brajam/.local/share/branconet-migration/local-build-storage-20261025')
SOURCE = OUTSIDE / 'grow144-source-970142267f95'
SOURCE_SHA = '970142267f95f7f903c093ca57fe2958c56a55fc921404891f9d00c236f2e0bb'
FAILED = OUTSIDE / 'offline-grow144-0ce6f9e2cbf74c6fabaa415f63d16a29.json'
FAILED_SHA = 'd8f36ad7c87fc2c36a9b0898ba1a6b5a5f796ba01cd79dcad9107cf27307351f'
SETUP_SHA = '1992fdc6134ef44a8dc54f68da7559d386a8bb34bd4504fa15cf3164d79a4b8b'
WRAPPER_SHA = '69374497f82cc334857b54091523e5e518155b21998d1d009d90c3cf2bd4a008'
# Read-only observation after the final namespace naturally closed: unmount
# metadata flush changed backing mtime, not its inode, size or archive inputs.
DETACHED_MTIME_NS = 1792943668475508900


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verify_sources():
    need(sha(SOURCE / 'source-manifest.json') == SOURCE_SHA, 'original_source_manifest')
    files = json.loads((SOURCE / 'source-manifest.json').read_bytes())
    for name, row in files.items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'source_relative_path')
        p = SOURCE / name
        need(p.resolve() == p and p.stat().st_size == row['size'] and sha(p) == row['sha256'],
             'original_frozen_source')
    need(files['setup.py']['sha256'] == SETUP_SHA
         and files['offline-grow144.py']['sha256'] == WRAPPER_SHA, 'exact_original_helpers')
    installed = Path('/usr/local/libexec/branconet-migration/mount-build-storage.py')
    info = installed.lstat()
    need(installed.resolve() == installed and stat.S_ISREG(info.st_mode) and info.st_uid == 0
         and not info.st_mode & 0o077 and sha(installed) == SETUP_SHA, 'installed_fenced_helper')
    spec = importlib.util.spec_from_file_location('original_grow144', SOURCE / 'offline-grow144.py')
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    return original


def detached_census(original):
    """No namespace mutation: any renewed hold is a refusal."""
    need(not original.MOUNT.is_mount() and not any(original.MOUNT.iterdir()), 'global_mount_stays_empty')
    loops = json.loads(original.run(['losetup', '--json', '--list', '--output',
                                    'NAME,BACK-FILE,DIO,LOG-SEC']))['loopdevices']
    need(not any(r['back-file'] == str(original.IMAGE) or r['name'] == '/dev/loop0' for r in loops),
         'original_loop_fully_detached_not_reused')
    loop_node = Path('/dev/loop0').stat()
    need(stat.S_ISBLK(loop_node.st_mode), 'original_loop_device_node')
    device = loop_node.st_rdev
    mount_device = str(os.major(device)) + ':' + str(os.minor(device))
    offenders = set()
    namespaces = set()
    build_names = {'buildkitd', 'buildctl', 'docker-buildx',
                   'local-build-offloaded-image.py', 'local-build-security-image.py'}
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal():
            continue
        try:
            ns = os.readlink(p / 'ns/mnt')
            if ns not in namespaces:
                for line in (p / 'mountinfo').read_text().splitlines():
                    fields = line.split()
                    need(fields[2] != mount_device and fields[4] != str(original.MOUNT)
                         and not fields[4].startswith(str(original.MOUNT) + '/')
                         and str(original.IMAGE) not in fields, 'remaining_namespace_mount')
                namespaces.add(ns)
            if (p / 'comm').read_text().strip() in build_names:
                offenders.add(int(p.name))
            if any(Path(os.fsdecode(a)).name in build_names
                   for a in (p / 'cmdline').read_bytes().split(b'\0') if a):
                offenders.add(int(p.name))
            for link in [p / 'cwd', p / 'root', p / 'exe', *(p / 'fd').iterdir()]:
                try:
                    if link.stat().st_dev == device:
                        offenders.add(int(p.name))
                except FileNotFoundError:
                    pass
            for line in (p / 'maps').read_text().splitlines():
                major, minor = line.split(None, 5)[3].split(':')
                if os.makedev(int(major, 16), int(minor, 16)) == device:
                    offenders.add(int(p.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            need(False, 'process_namespace_visibility')
    need(not offenders, 'active_reference_or_builder_count_' + str(len(offenders)))
    need(not original.loop_state() and not original.MOUNT.is_mount(), 'detached_census_end')
    return {'namespace_count': len(namespaces), 'active_reference_count': 0,
            'namespace_unmount_performed': False, 'processes_stopped': False}


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('--apply', action='store_true')
    a.add_argument('--resume-source-manifest-sha256', required=True)
    args = a.parse_args()
    need(args.apply and os.getuid() == 0, 'explicit_root_resume')
    os.umask(0o077)
    os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    os.environ['PATH'] = '/usr/sbin:/usr/bin:/sbin:/bin'
    os.environ['LC_ALL'] = 'C'
    own = Path(__file__).resolve().parent
    need(OUTSIDE in own.parents, 'resume_source_outside_f')
    mp = own / 'source-manifest.json'
    need(sha(mp) == args.resume_source_manifest_sha256, 'resume_source_manifest')
    for name, row in json.loads(mp.read_bytes()).items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'resume_relative_path')
        p = own / name
        need(p.resolve() == p and p.stat().st_size == row['size'] and sha(p) == row['sha256'],
             'resume_source_hash')
    original = verify_sources()
    need(Path.cwd() != original.MOUNT and original.MOUNT not in Path.cwd().parents, 'outside_cwd')
    need(sha(FAILED) == FAILED_SHA, 'exact_failed_receipt')
    failed = json.loads(FAILED.read_bytes())
    need(failed['status'] == 'failed' and failed['operation'] == 'normal_unmount'
         and failed['reason'] == 'backing_fully_detached'
         and failed['source_manifest_sha256'] == SOURCE_SHA, 'exact_refused_operation')
    preservation = json.loads((SOURCE / 'preservation-inputs.json').read_bytes())
    expected = [{'name': row['name'], 'hash_and_metadata_equal': True,
                 'complete_age_authentication': bool(row.get('age_authenticated'))}
                for row in preservation['files']]
    need(failed['preserved_before'] == expected and len(expected) == 13
         and sum(r['complete_age_authentication'] for r in expected) == 4, 'complete_prior_preservation')
    li = original.LOCK.lstat()
    need(original.LOCK.resolve() == original.LOCK and stat.S_ISREG(li.st_mode)
         and li.st_uid == 1000 and li.st_nlink == 1, 'existing_build_lock')
    lock = os.open(original.LOCK, os.O_RDWR | os.O_NOFOLLOW)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    need((os.fstat(lock).st_dev, os.fstat(lock).st_ino) == (li.st_dev, li.st_ino), 'same_build_lock')
    receipt = OUTSIDE / ('offline-resume144-' + uuid.uuid4().hex + '.json')
    record = {'status': 'started', 'operation': 'detached_preflight',
              'failed_receipt_sha256': FAILED_SHA, 'original_source_manifest_sha256': SOURCE_SHA,
              'resume_source_manifest_sha256': args.resume_source_manifest_sha256,
              'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'no_mount_or_process_removed_by_resume': True}
    def save():
        receipt.write_text(json.dumps(record, sort_keys=True, indent=2) + '\n')
        receipt.chmod(0o600)
        os.chown(receipt, 1000, 1000)
    save()
    try:
        record['census'] = detached_census(original)
        detached_backing = {**failed['before']['backing'], 'mtime_ns': DETACHED_MTIME_NS}
        need(original.identity(original.IMAGE) == detached_backing, 'exact_detached_128_backing')
        record['detached_backing'] = detached_backing
        header = original.run(['dumpe2fs', '-h', str(original.IMAGE)]).decode()
        fields = dict((k.strip(), v.strip()) for k, v in
                      (line.split(':', 1) for line in header.splitlines() if ':' in line))
        need(fields.get('Filesystem UUID') == original.FS_UUID and fields.get('Filesystem state') == 'clean'
             and int(fields['Block count']) * int(fields['Block size']) == 128 * original.GIB,
             'original_128_geometry_uuid')
        need(sha(original.AGE) == original.AGE_SHA, 'pinned_age')
        # SSH key metadata/hash is available outside F even in this detached state.
        for row in preservation['files']:
            p = Path(row['path'])
            if p in [original.KEY, original.KEY.with_suffix('.pub')]:
                need(original.identity(p) == row['identity'] and sha(p) == row['sha256'], 'original_key')
        need(os.statvfs(original.IMAGE.parent).f_bavail * os.statvfs(original.IMAGE.parent).f_frsize
             >= 31 * original.GIB, 'physical_f_16_growth_plus_15_reserve')
        c_free = int(original.run(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
                                   '-NoProfile', '-NonInteractive', '-Command', '(Get-PSDrive C).Free']).strip())
        need(c_free >= 15 * original.GIB, 'windows_c_15_gib')
        record['windows_c_free_before'] = c_free
        detached_census(original)
        need(original.identity(original.IMAGE) == detached_backing, 'pre_growth_backing')
        record['operation'] = 'offline_check_growth_remount'; save()
        child = subprocess.run(['/usr/bin/python3', '-B', str(SOURCE / 'setup.py'), '--apply',
                                '--grow-existing-gib', '144', '--grow-existing-inode', str(original.INODE),
                                '--offline-lock-fd', str(lock)], pass_fds=(lock,),
                               stdin=subprocess.DEVNULL, capture_output=True)
        receipt.with_suffix('.setup.stdout').write_bytes(child.stdout)
        receipt.with_suffix('.setup.stderr').write_bytes(child.stderr)
        need(child.returncode == 0, 'setup_failed_retain_offline_state_for_review')
        record['setup_receipt'] = json.loads(child.stdout)
        after = original.mount_state(144 * original.GIB)
        need({k: v for k, v in after['backing'].items() if k not in ['bytes', 'mtime_ns']}
             == {k: v for k, v in failed['before']['backing'].items() if k not in ['bytes', 'mtime_ns']},
             'same_original_backing_identity')
        record['after'] = after
        record['operation'] = 'full_original_preservation_after'; save()
        record['preserved_after'] = original.preserve(preservation)
        need(record['preserved_after'] == failed['preserved_before'], 'original_full_preservation')
        need(sha(FAILED) == FAILED_SHA, 'failed_receipt_retained')
        verify_sources()
        record['native_free_after'] = os.statvfs(original.MOUNT).f_bavail * os.statvfs(original.MOUNT).f_frsize
        need(record['native_free_after'] >= 27 * original.GIB, 'next_build_12_plus_15_floor')
        record.update(status='completed', operation='same_inode_growth_original_preservation_verified')
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
