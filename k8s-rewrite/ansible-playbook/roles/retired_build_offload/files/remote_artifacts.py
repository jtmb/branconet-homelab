"""New read/stream/exact-cache-clear program; never executes a retired helper."""
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys

BASE = Path('/home/james/.local/share/branconet-migration')
TREES = {'b5d6d1': BASE / 'root-custom-kubectl-build-20261012-b5d6d1',
         'f73dc0': BASE / 'root-custom-kubectl-build-20261012-f73dc0'}
CACHES = {'b5d6d1': 'kubectl-security-a4cc69125f81/cache',
          'f73dc0': 'kubectl-security-53c90b1e408a/cache'}


def need(condition, category='refused'):
    if not condition:
        raise ValueError(category)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def under(value):
    value = value.removesuffix(' (deleted)')
    return any(value == str(root) or value.startswith(str(root) + '/') for root in TREES.values())


def command(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=30)


def idle(additional_units):
    # Full active inventory is checked in RAM; raw ExecStart values are never emitted.
    names = [line.split()[0] for line in command('systemctl', 'list-units', '--all',
             '--state=active,activating,deactivating', '--plain', '--no-legend', '--no-pager').splitlines() if line.strip()]
    names = sorted(set(names + additional_units))
    need(all(re.fullmatch(r'[A-Za-z0-9_.@:\\-]+', n) for n in names), 'unexpected_unit_name')
    raw = command('systemctl', 'show', '--no-pager', '--property=Id,ActiveState,SubState,ExecStart,WorkingDirectory', '--', *names)
    units = [dict(line.split('=', 1) for line in block.splitlines() if '=' in line) for block in raw.strip().split('\n\n')]
    need({u.get('Id') for u in units} == set(names), 'incomplete_unit_inventory')
    for unit in units:
        matches = any(str(root) in unit.get('ExecStart', '') + unit.get('WorkingDirectory', '') for root in TREES.values())
        if matches or unit.get('Id') in additional_units:
            need(unit.get('ActiveState') not in ('active', 'activating', 'deactivating'), 'owned_build_unit_active')
    references = []
    pids = 0
    mounts = set()
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            pids += 1
            for name in ('cwd', 'root', 'exe'):
                try:
                    if under(os.readlink(proc / name)):
                        references.append({'pid': int(proc.name), 'kind': name})
                except OSError as error:
                    if error.errno not in (errno.ENOENT, errno.ESRCH):
                        raise
            for fd in (proc / 'fd').iterdir():
                try:
                    if under(os.readlink(fd)):
                        references.append({'pid': int(proc.name), 'kind': 'fd'})
                except OSError as error:
                    if error.errno not in (errno.ENOENT, errno.ESRCH):
                        raise
            for line in (proc / 'maps').read_text().splitlines():
                fields = line.split(None, 5)
                if len(fields) == 6 and under(fields[5]):
                    references.append({'pid': int(proc.name), 'kind': 'mapped-file'})
            namespace = (proc / 'ns/mnt').stat().st_ino
            if namespace not in mounts:
                mounts.add(namespace)
                for line in (proc / 'mountinfo').read_text().splitlines():
                    fields = line.split()
                    decoded = [re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), p) for p in (fields[3], fields[4], fields[-2])]
                    need(not any(under(p) for p in decoded), 'mount_references_retired_tree')
        except OSError as error:
            if error.errno not in (errno.ENOENT, errno.ESRCH):
                raise
    need(not references, 'process_references_retired_tree')
    fs = json.loads(command('/usr/bin/findmnt', '--json', '--target', '/', '--output', 'UUID,SOURCE,FSTYPE'))['filesystems'][0]
    need(fs.get('uuid') and fs.get('fstype') == 'ext4', 'unexpected_master_root_filesystem')
    capacity = os.statvfs('/')
    return {'unit_count': len(units), 'unit_inventory_sha256': hashlib.sha256(raw.encode()).hexdigest(),
            'processes_checked': pids, 'mount_namespaces_checked': len(mounts),
            'matching_references': references, 'root_filesystem': fs,
            'root_total_bytes': capacity.f_blocks * capacity.f_frsize,
            'root_available_bytes': capacity.f_bavail * capacity.f_frsize,
            'root_free_inode_fraction': capacity.f_favail / capacity.f_files}


def snapshot(key):
    root = TREES[key]
    need(root.resolve() == root and not root.is_symlink(), 'source_path_identity')
    original = root.lstat()
    need(stat.S_ISDIR(original.st_mode) and original.st_uid == 0 and not original.st_mode & 0o022, 'source_owner_or_mode')
    cache = root / CACHES[key]
    need(cache.resolve() == cache and cache.is_dir() and not cache.is_symlink(), 'exact_cache_identity')
    digest = hashlib.sha256()
    count = size = cache_bytes = allocated = 0
    direct_children = {}
    inner_children = {}
    allocated_inodes = set()
    cache_inodes = set()
    root_device = original.st_dev

    def walk(path):
        nonlocal count, size, cache_bytes, allocated
        info = path.lstat()
        need(info.st_dev == root_device, 'nested_filesystem_in_source')
        need(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or stat.S_ISFIFO(info.st_mode), 'unarchivable_special_entry')
        count += 1
        need(count <= 500000, 'source_entry_bound')
        regular = stat.S_ISREG(info.st_mode)
        inode = (info.st_dev, info.st_ino)
        block_bytes = info.st_blocks * 512 if inode not in allocated_inodes else 0
        allocated_inodes.add(inode)
        allocated += block_bytes
        relative = path.relative_to(root)
        for collection, length in ((direct_children, 1), (inner_children, 2)):
            if len(relative.parts) >= length:
                name = '/'.join(relative.parts[:length])
                tally = collection.setdefault(name, {'allocated_bytes': 0, 'logical_file_bytes': 0})
                tally['allocated_bytes'] += block_bytes
                tally['logical_file_bytes'] += info.st_size if regular else 0
        if (path == cache or cache in path.parents) and inode not in cache_inodes:
            cache_bytes += info.st_blocks * 512
            cache_inodes.add(inode)
        if regular:
            size += info.st_size
        need(size <= 16 * 1024 ** 3, 'source_byte_bound')
        item = [str(path.relative_to(root)), info.st_dev, info.st_ino, info.st_mode,
                info.st_uid, info.st_gid, info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns]
        if path.is_symlink():
            item.append(os.readlink(path))
        digest.update(encoded(item) + b'\n')
        if stat.S_ISDIR(info.st_mode):
            descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NOATIME)
            try:
                with os.scandir(descriptor) as entries:
                    names = sorted(entry.name for entry in entries)
                for name in names:
                    walk(path / name)
            finally:
                os.close(descriptor)

    walk(root)
    ci = cache.lstat()
    return {'root': str(root), 'root_device': original.st_dev, 'root_inode': original.st_ino,
            'metadata_sha256': digest.hexdigest(), 'entries': count, 'logical_bytes': size,
            'cache': str(cache), 'cache_inode': ci.st_ino, 'cache_device': ci.st_dev,
            'cache_allocated_bytes': cache_bytes, 'allocated_bytes': allocated,
            'direct_children': direct_children, 'inner_children': inner_children}


def archive(key, units):
    before_idle = idle(units)
    before = snapshot(key)
    root = TREES[key]
    argv = ['ionice', '-c', '3', 'nice', '-n', '10', 'tar', '--format=posix', '--acls',
            '--xattrs', '--xattrs-include=*', '--selinux', '--numeric-owner', '--sparse',
            '--atime-preserve=system', '-C', str(BASE), '-cf', '-', '--', root.name]
    child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)

    def stop(_signal, _frame):
        raise InterruptedError()

    for number in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(number, stop)
    sha = hashlib.sha256()
    count = 0
    try:
        for chunk in iter(lambda: child.stdout.read(1024 ** 2), b''):
            count += len(chunk)
            need(count <= 18 * 1024 ** 3, 'tar_stream_bound')
            sha.update(chunk)
            sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()
        need(child.wait(timeout=30) == 0, 'gnu_tar_failed_or_changed_source')
        after = snapshot(key)
        need(before == after, 'source_changed_during_archive')
        after_idle = idle(units)
        need(before_idle['root_filesystem'] == after_idle['root_filesystem'], 'master_root_filesystem_changed')
        print(json.dumps({'state': 'stream-complete-source-stable', 'source': before,
              'stream_sha256': sha.hexdigest(), 'stream_bytes': count,
              'before_idle': before_idle, 'after_idle': after_idle}), file=sys.stderr, flush=True)
    finally:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()


def clear_cache(key, proof, units):
    observed = idle(units)
    need(observed['root_filesystem'] == proof['after_idle']['root_filesystem'], 'master_root_filesystem_changed')
    current = snapshot(key)
    need(current == proof['source'], 'source_changed_after_verified_archive')
    root = TREES[key]
    cache = root / CACHES[key]
    need(shutil.rmtree.avoids_symlink_attacks, 'fd_safe_rmtree_unavailable')
    # Parent descriptor pins the selected cache directory; no tree or other path is deleted.
    parent = os.open(cache.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        entry = os.stat(cache.name, dir_fd=parent, follow_symlinks=False)
        need(entry.st_ino == current['cache_inode'] and entry.st_dev == current['cache_device'] and stat.S_ISDIR(entry.st_mode), 'cache_replaced')
        shutil.rmtree(cache.name, dir_fd=parent)
    finally:
        os.close(parent)
    fs = os.statvfs('/')
    return {'state': 'only-reviewed-cache-directory-removed', 'selected_cache': str(cache),
            'source_root_retained': root.is_dir(), 'root_available_bytes': fs.f_bavail * fs.f_frsize}


def main():
    need(os.geteuid() == 0 and socket.gethostname() == 'masternode', 'exact_privileged_master_required')
    mode, key, specification = sys.argv[1:]
    settings = json.loads(specification)
    units = settings.get('additional_units', [])
    need(isinstance(units, list) and len(units) <= 20 and all(isinstance(u, str) and u.endswith('.service') for u in units), 'invalid_additional_units')
    need(mode in ('inspect', 'archive', 'clear-cache') and key in TREES, 'exact_scope_required')
    os.nice(10)
    if mode == 'archive':
        archive(key, units)
    elif mode == 'inspect':
        print(json.dumps({'idle': idle(units), 'source': snapshot(key)}))
    else:
        print(json.dumps(clear_cache(key, settings['proof'], units)))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'state': 'refused', 'error_type': type(error).__name__,
              'category': str(error) if isinstance(error, ValueError) else 'prerequisite_or_io_failure'}), file=sys.stderr)
        raise SystemExit(1)
