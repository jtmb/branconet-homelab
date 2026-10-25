"""Read-only public OCI staging checks; never imports, unpacks or runs an image."""
import argparse
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat

NAMES = {'seerr', 'ytptube', 'jackett', 'pihole', 'flaresolverr', 'vaultwarden', 'tautulli', 'wordpress', 'nginx', 'phpmyadmin', 'coredns', 'plex', 'unpackerr', 'homepage', 'http-echo', 'qbittorrent-current', 'pihole-exporter', 'mealie', 'qbit-monitor', 'xteve'}
CONTROLLER = Path('/home/brajam/.local/share/branconet-migration/application-artifacts-20261023')
NODE = Path('/home/james/.local/share/branconet-migration/application-artifacts-20261023')
MAX_ARCHIVE = 4 * 1024**3


def need(value):
    if not value:
        raise ValueError('Public artifact staging prerequisite refused')


def fingerprint(info):
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def protected_directory(path, owner):
    need(path.resolve() == path)
    info = path.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == owner and stat.S_IMODE(info.st_mode) == 0o700)


def operator_ancestor(path, owner):
    """Accept the existing operator parent without changing its shared mode."""
    need(path.resolve() == path and not path.is_symlink())
    info = path.lstat()
    mode = stat.S_IMODE(info.st_mode)
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == owner and not mode & 0o002)
    if mode & 0o020:
        group = grp.getgrgid(info.st_gid)
        members = set(group.gr_mem) | {entry.pw_name for entry in pwd.getpwall() if entry.pw_gid == info.st_gid}
        need(members == {pwd.getpwuid(owner).pw_name})


def archive_identity(path, owner, expected_sha, expected_bytes=None):
    need(path.resolve() == path)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == owner and not stat.S_IMODE(before.st_mode) & 0o077)
    need(0 < before.st_size <= MAX_ARCHIVE and (expected_bytes is None or before.st_size == expected_bytes))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        need(fingerprint(os.fstat(fd)) == fingerprint(before))
        digest = hashlib.sha256(); count = 0
        with os.fdopen(os.dup(fd), 'rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block); count += len(block); need(count <= MAX_ARCHIVE)
        need(count == before.st_size and digest.hexdigest() == expected_sha and fingerprint(os.fstat(fd)) == fingerprint(path.lstat()) == fingerprint(before))
    finally:
        os.close(fd)
    return {'archive': str(path), 'archive_bytes': count, 'archive_sha256': expected_sha, 'fingerprint': fingerprint(before), 'mode': oct(stat.S_IMODE(before.st_mode))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['controller', 'node-before', 'node-after'])
    parser.add_argument('--service', choices=sorted(NAMES), required=True)
    parser.add_argument('--generation', default='initial')
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--archive-bytes', type=int)
    parser.add_argument('--uncompressed-layer-bytes', type=int, required=True)
    args = parser.parse_args()
    need(re.fullmatch(r'(initial|r[1-9][0-9]{0,2}|ci[1-9][0-9]{0,14})', args.generation))
    need(re.fullmatch('[0-9a-f]{64}', args.sha256) and 0 < args.uncompressed_layer_bytes <= 16 * 1024**3)
    controller = args.phase == 'controller'
    owner = pwd.getpwnam('brajam' if controller else 'james').pw_uid
    need(os.geteuid() == owner)
    parent = CONTROLLER if controller else NODE
    if controller and args.service in ['plex', 'unpackerr', 'homepage', 'http-echo', 'qbittorrent-current', 'pihole-exporter', 'mealie', 'qbit-monitor', 'xteve']:
        mount = CONTROLLER.parent / 'local-image-build-offload-20261025'
        need(mount.is_mount() and mount.resolve() == mount and mount.stat().st_uid == owner
             and mount.stat().st_dev != os.stat('/').st_dev)
        parent = mount / 'application-artifacts-20261023'
    need(parent.resolve() == parent)
    parent_exists = parent.exists()
    need(not parent.is_symlink())
    if parent_exists:
        protected_directory(parent, owner)
    else:
        need(args.phase == 'node-before')
        operator_ancestor(parent.parent, owner)
    suffix = '' if args.generation == 'initial' else '-' + args.generation
    path = parent / (args.service + '-security-20261023' + suffix + '.oci.tar')
    exists = path.exists(); need(not path.is_symlink())
    result = {'phase': args.phase, 'service': args.service, 'generation': args.generation, 'archive': str(path), 'parent_exists': parent_exists, 'archive_exists': exists, 'imported': False, 'unpacked': False, 'application_started': False}
    if controller or args.phase == 'node-after' or exists:
        need(exists)
        result.update(archive_identity(path, owner, args.sha256, args.archive_bytes))
    if not controller:
        need(args.archive_bytes is not None and 0 < args.archive_bytes <= MAX_ARCHIVE)
        fs = os.statvfs(parent if parent_exists else parent.parent)
        total = fs.f_blocks * fs.f_frsize; available = fs.f_bavail * fs.f_frsize
        floor = (15 * total + 99) // 100 + 1024**3
        required = floor + 2 * args.archive_bytes + args.uncompressed_layer_bytes
        result.update(filesystem_total_bytes=total, filesystem_available_bytes=available, reserve_bytes=floor, required_pre_copy_bytes=required, uncompressed_layer_bytes=args.uncompressed_layer_bytes)
        if args.phase == 'node-before':
            need(available >= required)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(json.dumps({'state': 'refused', 'reason': 'Protected fixed artifact, identity or capacity check failed'}))
        raise SystemExit(1)
