"""Retire only hash-pinned, inactive, 72-hour-old BuildKit tool copies.

Sources, locks, build state, OCI outputs and failed evidence are never removed.
Regeneration: extract bin/{buildctl,buildkitd,buildkit-runc} from the original
BuildKit v0.34.1 linux-amd64 release archive, verify ARCHIVE and TOOLS below.
Use a fresh build attempt; this command never replays a retired attempt.
"""
import argparse
import datetime
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import time

BASE = Path('/home/james/.local/share/branconet-migration/worker1-image-build-20261023')
ATTEMPTS = ('jackett', 'pihole', 'seerr', 'seerr-r2', 'seerr-r3', 'ytptube', 'ytptube-r2')
ARCHIVE = 'a59539daf547fe0958efe2d07e41c0a6944e1112a66d7e519ec1cf5b673ef15b'
TOOLS = {
    'buildctl': '8e64362dceba989827b23af567915feda10426ebd40611772318662e33bf2bfd',
    'buildkit-runc': '2f5ed1fb8b0d57bf8442767d572229cb0ff29bdcfe279c6a51535a6a84f85eff',
    'buildkitd': 'ca3c5d4fe1defc5df56631e179824f17ddd555f1fcf5057d14dfb87496baa8c3',
}
UUID = '5f1fd363-f7b7-44db-ace5-ad81a25a2926'


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def command(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=45)


def identity(path):
    s = path.lstat()
    return {k: getattr(s, 'st_' + k) for k in ('dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks')}


def sha(path):
    before = identity(path)
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    need(identity(path) == before, 'file_changed_while_hashing')
    return h.hexdigest()


def snapshot():
    records = []
    for name in ATTEMPTS:
        root = BASE / name
        need(root.resolve() == root and root.is_dir(), 'exact_attempt_root')
        sealpath = root / 'build-inputs.json'
        need(sealpath.is_file() and not sealpath.is_symlink(), 'original_seal')
        seal = json.loads(sealpath.read_text())
        need(seal['root'] == str(root) and seal['buildkit_archive_sha256'] == ARCHIVE, 'original_tool_provenance')
        need(seal['root_filesystem']['uuid'] == UUID, 'original_filesystem')
        preserved = {}
        for rel, expected in seal['files'].items():
            p = root / rel
            need(p.resolve() == p and p.is_relative_to(root), 'sealed_source_path')
            if rel.startswith('bin/'):
                need(rel[4:] in TOOLS and TOOLS[rel[4:]] == expected, 'fixed_tool_allowlist')
            else:
                need(p.is_file() and not p.is_symlink() and sha(p) == expected, 'source_or_lock_changed')
                preserved[rel] = {'identity': identity(p), 'sha256': expected}
        tools = root / 'bin'
        need(not tools.is_symlink(), 'tool_directory_symlink')
        if not tools.exists():
            records.append({'root': str(root), 'absent': True, 'preserved': preserved})
            continue
        need(tools.resolve() == tools and tools.is_dir() and set(p.name for p in tools.iterdir()) == set(TOOLS), 'exact_three_tool_directory')
        d = identity(tools)
        need(d['uid'] == 0 and d['dev'] == os.stat('/').st_dev and not d['mode'] & 0o077, 'protected_tool_directory')
        files = []
        for tool, expected in TOOLS.items():
            p = tools / tool
            info = identity(p)
            need(stat.S_ISREG(info['mode']) and info['uid'] == 0 and info['nlink'] == 1 and info['dev'] == d['dev'], 'regular_owned_single_link_tool')
            need(not info['mode'] & 0o077 and time.time_ns() - max(info['mtime_ns'], info['ctime_ns']) >= 72 * 3600 * 10**9, 'tool_mode_or_72_hour_retention')
            need(sha(p) == expected, 'tool_hash_mismatch')
            files.append({'path': str(p), 'identity': info, 'sha256': expected})
        records.append({'root': str(root), 'directory': {'path': str(tools), 'identity': d}, 'files': files,
                        'sealSHA256': sha(sealpath), 'preserved': preserved})
    return records


def idle():
    # Check whole attempt roots; a daemon referencing sibling state also refuses.
    def under(value):
        value = value.removesuffix(' (deleted)')
        return any(value == str(BASE / n) or value.startswith(str(BASE / n) + '/') for n in ATTEMPTS)
    names = sorted({line.split()[0] for line in command('systemctl', 'list-units', '--all', '--state=active,activating,deactivating', '--plain', '--no-legend', '--no-pager').splitlines() if line.strip()})
    need(names and all(re.fullmatch(r'[A-Za-z0-9_.@:\\-]+', n) for n in names), 'unit_inventory')
    raw = command('systemctl', 'show', '--no-pager', '--property=Id,ExecStart,WorkingDirectory', '--', *names)
    units = [dict(line.split('=', 1) for line in b.splitlines() if '=' in line) for b in raw.strip().split('\n\n')]
    need({u.get('Id') for u in units} == set(names), 'incomplete_unit_inventory')
    need(not any(str(BASE / n) in u.get('ExecStart', '') + u.get('WorkingDirectory', '') for u in units for n in ATTEMPTS), 'active_unit_reference')
    checked = 0
    namespaces = set()
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            checked += 1
            commandline = (proc / 'cmdline').read_bytes()
            need(not any(str(BASE / n).encode() in commandline for n in ATTEMPTS), 'process_argument_reference')
            for p in [proc / 'cwd', proc / 'root', proc / 'exe', *(proc / 'fd').iterdir()]:
                try:
                    need(not under(os.readlink(p)), 'active_process_reference')
                except OSError as e:
                    if e.errno not in (errno.ENOENT, errno.ESRCH):
                        raise
            for line in (proc / 'maps').read_text().splitlines():
                fields = line.split(None, 5)
                need(len(fields) != 6 or not under(fields[5]), 'mapped_tool_reference')
            ns = (proc / 'ns/mnt').stat().st_ino
            if ns not in namespaces:
                namespaces.add(ns)
                for line in (proc / 'mountinfo').read_text().splitlines():
                    fields = line.split()
                    # Includes overlay lowerdir/upperdir/workdir as well as bind roots.
                    decoded = re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), line)
                    need(not any(str(BASE / n) in decoded for n in ATTEMPTS), 'mount_reference')
        except OSError as e:
            if e.errno not in (errno.ENOENT, errno.ESRCH):
                raise
    return {'processes': checked, 'mountNamespaces': len(namespaces), 'units': len(units), 'unitInventorySHA256': hashlib.sha256(raw.encode()).hexdigest()}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    need(os.geteuid() == 0 and socket.gethostname() == 'workernode1', 'fixed_worker1_root_scope')
    fs = json.loads(command('findmnt', '--json', '--target', '/', '--output', 'UUID,SOURCE,FSTYPE'))['filesystems'][0]
    need(fs['uuid'] == UUID and fs['fstype'] == 'ext4', 'fixed_root_filesystem')
    locks = []
    try:
        for path in [BASE / 'host-build.lock', *[BASE / n / 'phase.lock' for n in ATTEMPTS]]:
            if path.exists():
                need(path.is_file() and not path.is_symlink(), 'original_lock_type')
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                locks.append(fd)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        records = snapshot()
        proof = idle()
        need(snapshot() == records, 'pre_apply_identity_changed')
        before = os.statvfs('/')
        result = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'filesystem': fs, 'applied': args.apply,
                  'records': records, 'inactivity': proof, 'removed': [], 'removedAllocatedBytes': 0}
        if args.apply:
            for record in records:
                if record.get('absent'):
                    continue
                directory = Path(record['directory']['path'])
                need(identity(directory) == record['directory']['identity'], 'directory_identity_changed')
                fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    for item in record['files']:
                        path = Path(item['path'])
                        need(identity(path) == item['identity'], 'tool_identity_changed')
                        os.unlink(path.name, dir_fd=fd)
                        result['removed'].append(item)
                        result['removedAllocatedBytes'] += item['identity']['blocks'] * 512
                finally:
                    os.close(fd)
                directory.rmdir()
                result['removed'].append(record['directory'])
                result['removedAllocatedBytes'] += record['directory']['identity']['blocks'] * 512
            after = snapshot()
            need(all(r.get('absent') for r in after), 'remaining_tool_copy')
            need([r['preserved'] for r in after] == [r['preserved'] for r in records], 'preserved_source_changed')
        afterfs = os.statvfs('/')
        result['availableBeforeBytes'] = before.f_bavail * before.f_frsize
        result['availableAfterBytes'] = afterfs.f_bavail * afterfs.f_frsize
        print(json.dumps(result))
    finally:
        for fd in locks:
            os.close(fd)


if __name__ == '__main__':
    main()
