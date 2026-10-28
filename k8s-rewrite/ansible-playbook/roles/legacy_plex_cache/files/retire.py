"""Clear generated photo thumbnails from one inactive legacy Plex config only."""
import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import time

BASE = Path('/var/plex-stack/plex2')
ROOT = BASE / 'config.old'
CACHE = ROOT / 'Library/Application Support/Plex Media Server/Cache/PhotoTranscoder'
UUID = '960bc2c7-2a7e-4bc2-b2c5-dbb6d71207f4'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def ident(path):
    s = path.lstat()
    return {k: getattr(s, 'st_' + k) for k in ('dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks')}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def inventory():
    need(CACHE.resolve() == CACHE and CACHE.is_dir(), 'canonical_existing_cache')
    preserved = hashlib.sha256()
    outside_count = 0
    # No values are read or emitted from original settings, databases or metadata.
    # Identity/ctime proves these inactive original files remain untouched.
    def walk_error(error):
        raise error
    for parent, dirs, files in os.walk(ROOT, followlinks=False, onerror=walk_error):
        parent = Path(parent)
        dirs.sort()
        files.sort()
        if parent == CACHE:
            dirs[:] = []
            continue
        for name in dirs + files:
            p = parent / name
            if p == CACHE:
                continue
            outside_count += 1
            need(outside_count < 1000000, 'outside_inventory_bound')
            preserved.update(encoded([str(p.relative_to(ROOT)), ident(p)]))
    entries = []
    retained = []
    scanned = 0
    for parent, dirs, files in os.walk(CACHE, followlinks=False, onerror=walk_error):
        parent = Path(parent)
        dirs.sort()
        files.sort()
        for name in dirs + files:
            p = parent / name
            scanned += 1
            need(scanned <= 300000, 'cache_entry_bound')
            need(p.resolve() == p and p.is_relative_to(CACHE), 'cache_entry_canonical')
            s = ident(p)
            need(s['dev'] == os.stat('/').st_dev, 'cache_filesystem_changed')
            need(stat.S_ISDIR(s['mode']) or stat.S_ISREG(s['mode']), 'cache_entry_type')
            if stat.S_ISREG(s['mode']):
                need(time.time_ns() - max(s['mtime_ns'], s['ctime_ns']) >= 72 * 3600 * 10**9, '72_hour_file_retention')
                need(s['nlink'] == 1, 'hardlinked_cache_refused')
                with p.open('rb') as stream:
                    magic = stream.read(16)
                image = magic.startswith((b'\xff\xd8\xff', b'\x89PNG\r\n\x1a\n', b'GIF87a', b'GIF89a')) or magic[:4] == b'RIFF' and magic[8:12] == b'WEBP'
                if image:
                    entries.append({'path': str(p), 'identity': s})
                else:
                    retained.append({'path': str(p), 'identity': s, 'reason': 'image_format_not_qualified'})
    return {'entries': entries, 'retained': retained, 'outsideEntryCount': outside_count, 'outsideIdentitySHA256': preserved.hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--safety-source', required=True)
    parser.add_argument('--safety-sha256', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-plan')
    args = parser.parse_args()
    need(os.geteuid() == 0 and socket.gethostname() == 'workernode2', 'fixed_worker2_scope')
    os.setpriority(os.PRIO_PROCESS, 0, 15)
    safety = base64.b64decode(args.safety_source, validate=True)
    need(hashlib.sha256(safety).hexdigest() == args.safety_sha256, 'safety_source_identity')
    common = {'__name__': 'retired_tools_reference_checks'}
    exec(compile(safety, '<reviewed-reference-checks>', 'exec'), common)
    common.update(BASE=BASE, ATTEMPTS=('config.old',))
    fs = json.loads(common['command']('findmnt', '--json', '--target', '/', '--output', 'UUID,SOURCE,FSTYPE'))['filesystems'][0]
    need(fs['uuid'] == UUID and fs['fstype'] == 'ext4', 'pinned_worker2_filesystem')
    proof = common['idle']()
    plan = inventory()
    fingerprint = hashlib.sha256(encoded({'filesystem': fs, 'inventory': plan, 'safetySHA256': args.safety_sha256})).hexdigest()
    result = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'filesystem': fs,
              'cache': str(CACHE), 'inactivity': proof, 'plan': plan, 'planSHA256': fingerprint,
              'applied': args.apply, 'removed': [], 'removedAllocatedBytes': 0}
    if not args.apply:
        print(json.dumps(result))
        return
    need(args.expected_plan == fingerprint, 'reviewed_plan_changed')
    common['idle']()
    need(inventory() == plan, 'pre_apply_inventory_changed')
    before = os.statvfs('/')
    try:
        # Remove only proved generated image files. Keep all directories and
        # every entry that failed image-format qualification.
        entries = plan['entries']
        for entry in entries:
            path = Path(entry['path'])
            s = ident(path)
            need(s == entry['identity'] and stat.S_ISREG(s['mode']), 'cache_file_identity_changed')
            fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                need(os.stat(path.name, dir_fd=fd, follow_symlinks=False).st_ino == s['ino'], 'opened_parent_file_identity')
                os.unlink(path.name, dir_fd=fd)
            finally:
                os.close(fd)
            result['removed'].append(entry)
            result['removedAllocatedBytes'] += entry['identity']['blocks'] * 512
        after = inventory()
        need(not after['entries'] and after['retained'] == plan['retained'] and after['outsideIdentitySHA256'] == plan['outsideIdentitySHA256'] and after['outsideEntryCount'] == plan['outsideEntryCount'], 'original_data_identity_changed')
        result['originalDataIdentitiesPreserved'] = True
    finally:
        afterfs = os.statvfs('/')
        result['availableBeforeBytes'] = before.f_bavail * before.f_frsize
        result['availableAfterBytes'] = afterfs.f_bavail * afterfs.f_frsize
        print(json.dumps(result))


if __name__ == '__main__':
    main()
