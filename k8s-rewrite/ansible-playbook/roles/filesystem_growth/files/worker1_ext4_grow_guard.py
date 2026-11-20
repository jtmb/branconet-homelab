#!/usr/bin/env python3
"""Operator artifact: inspect by default; source-only until reviewed dispatch."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import stat
import subprocess
import sys
import uuid

HOST = 'workernode1'
LV = '/dev/mapper/ubuntu--vg-ubuntu--lv'
FS_UUID = '5f1fd363-f7b7-44db-ace5-ad81a25a2926'
DEVICE_BYTES = 253906386944
ORIGINAL_BLOCK_COUNT = 26214400
ORIGINAL_FEATURES = set('has_journal ext_attr resize_inode dir_index filetype needs_recovery extent 64bit flex_bg sparse_super large_file huge_file dir_nlink extra_isize metadata_csum'.split())
OUT = Path('/home/james/.local/share/branconet-migration/fs-growth-worker1-20261023')
OFFICIAL_SOURCE = 'https://raw.githubusercontent.com/tytso/e2fsprogs/v1.46.5/resize/resize2fs.8.in'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def command(args):
    p = subprocess.run(args, text=True, capture_output=True, timeout=30,
                       env={**os.environ, 'LC_ALL': 'C'})
    require(p.returncode == 0, f'{args[0]} inspection failed: {p.stderr[:1000]}')
    return p.stdout


def mount(target):
    data = json.loads(command(['findmnt', '-J', '-T', target, '-o',
                               'SOURCE,FSTYPE,TARGET,UUID,OPTIONS']))['filesystems']
    require(len(data) == 1, 'Expected one containing filesystem')
    return data[0]


def inspect():
    require(socket.gethostname() == HOST, 'Wrong hostname')
    require(os.geteuid() == 0, 'Root required for read-only superblock inspection')
    root = mount('/')
    lh = mount('/var/lib/longhorn')
    for m in [root, lh]:
        require(m['source'] == LV and m['target'] == '/', 'Unexpected containing root mount')
        require(m['fstype'] == 'ext4' and m['uuid'] == FS_UUID, 'Filesystem identity mismatch')
        require('rw' in m['options'].split(','), 'Filesystem is not mounted read-write')
    require(stat.S_ISBLK(os.stat(LV).st_mode), 'Pinned LV is not a block device')
    devbytes = int(command(['blockdev', '--getsize64', LV]).strip())
    require(devbytes == DEVICE_BYTES, 'Existing LV byte size changed')
    block = json.loads(command(['lsblk', '-dn', '-b', '-J', '-o',
                                'NAME,TYPE,SIZE,FSTYPE,UUID', LV]))['blockdevices']
    require(len(block) == 1 and block[0]['type'] == 'lvm', 'Expected existing LVM device')
    require(block[0]['size'] == DEVICE_BYTES and block[0]['uuid'] == FS_UUID,
            'lsblk identity mismatch')
    raw = command(['tune2fs', '-l', LV])
    fields = {}
    for line in raw.splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
            fields[key.strip()] = value.strip()
    require(fields.get('Filesystem UUID') == FS_UUID, 'Superblock UUID mismatch')
    require(fields.get('Filesystem state') == 'clean', 'Superblock is not clean; stop for review')
    require(int(fields.get('FS Error count', '0')) == 0, 'Filesystem errors require separate review')
    features = fields.get('Filesystem features', '').split()
    require({'has_journal', 'extent'}.issubset(features), 'Expected journalled ext4 features')
    bs = int(fields['Block size'])
    count = int(fields['Block count'])
    require(bs == 4096 and 0 < count * bs <= DEVICE_BYTES, 'Unexpected filesystem geometry')
    require(count in [ORIGINAL_BLOCK_COUNT, DEVICE_BYTES // bs],
            'Filesystem block count is neither the reviewed original nor complete target')
    if count == ORIGINAL_BLOCK_COUNT:
        require(set(features) == ORIGINAL_FEATURES, 'Original filesystem features changed')
    v = os.statvfs('/')
    return {'observedUTC': utc(), 'hostname': HOST,
            'bootID': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'rootMount': root, 'longhornContainingMount': lh,
            'device': LV, 'resolvedDevice': str(Path(LV).resolve()),
            'deviceBytes': devbytes, 'filesystemUUID': FS_UUID,
            'filesystemBlockSize': bs, 'filesystemBlockCount': count,
            'filesystemSuperblockBytes': count * bs,
            'targetBlockCount': DEVICE_BYTES // bs,
            'filesystemState': fields['Filesystem state'], 'features': features,
            'statvfs': {'capacityBytes': v.f_frsize * v.f_blocks,
                        'freeBytes': v.f_frsize * v.f_bfree,
                        'nonrootAvailableBytes': v.f_frsize * v.f_bavail},
            'dfBytes': command(['df', '-B1', '/', '/var/lib/longhorn']),
            'superblockReadOnlyOutput': raw}


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('--apply', action='store_true', default=False)
    a.add_argument('--reviewed-preflight', type=Path)
    a.add_argument('--reviewed-preflight-sha256')
    args = a.parse_args()
    require(socket.gethostname() == HOST and os.geteuid() == 0,
            'Run only as root on verified workernode1')
    require(not OUT.is_symlink(), 'Receipt directory must not be a symlink')
    OUT.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(OUT.resolve() == OUT, 'Receipt path identity changed')
    operator = pwd.getpwnam('james')
    os.chmod(OUT, 0o700)
    os.chown(OUT, operator.pw_uid, operator.pw_gid)
    lock = OUT / 'guard.lock'
    require(not lock.is_symlink(), 'Lock must not be a symlink')
    with lock.open('a') as guard_lock:
        os.chmod(lock, 0o600)
        os.chown(lock, operator.pw_uid, operator.pw_gid)
        fcntl.flock(guard_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ident = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        receipt_path = OUT / (ident + '.json')
        receipt = {'startedUTC': utc(), 'applyRequested': args.apply,
                   'state': 'inspecting', 'officialSource': OFFICIAL_SOURCE,
                   'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   'scope': 'Only online ext4 growth on pinned existing worker1 LV. No LV/partition changes, force, shrink, fsck, data deletion, or Longhorn mutation.'}

        def save():
            temp = receipt_path.with_suffix('.tmp')
            with temp.open('w') as f:
                json.dump(receipt, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(temp, 0o600)
            os.chown(temp, operator.pw_uid, operator.pw_gid)
            temp.replace(receipt_path)
            directory_fd = os.open(OUT, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)

        try:
            before = inspect()
            receipt['before'] = before
            receipt['state'] = 'inspection_passed'
            save()
            if not args.apply:
                print(json.dumps({'state': receipt['state'], 'receipt': str(receipt_path),
                                  'receiptSHA256': hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
                                  'filesystemBlockCount': before['filesystemBlockCount'],
                                  'targetBlockCount': before['targetBlockCount']}))
                return 0
            require(args.reviewed_preflight is not None and args.reviewed_preflight_sha256,
                    'Apply requires the reviewed inspection receipt and its exact SHA256')
            review_bytes = args.reviewed_preflight.read_bytes()
            require(hashlib.sha256(review_bytes).hexdigest() == args.reviewed_preflight_sha256,
                    'Reviewed receipt SHA256 mismatch')
            reviewed = json.loads(review_bytes)
            require(reviewed.get('state') == 'inspection_passed' and not reviewed.get('applyRequested'),
                    'Expected a read-only inspection receipt')
            require(reviewed.get('sourceSHA256') == receipt['sourceSHA256'], 'Source changed since inspection')
            baseline = reviewed['before']
            for key in ['hostname', 'bootID', 'device', 'deviceBytes', 'filesystemUUID', 'filesystemBlockSize']:
                require(before[key] == baseline[key], 'Identity changed since review: ' + key)
            receipt['reviewedPreflight'] = str(args.reviewed_preflight)
            receipt['reviewedPreflightSHA256'] = args.reviewed_preflight_sha256
            if before['filesystemBlockCount'] == before['targetBlockCount']:
                receipt.update(state='already_at_existing_device_size', endedUTC=utc())
                save()
                print(json.dumps({'state': receipt['state'], 'receipt': str(receipt_path)}))
                return 0
            require(before['filesystemBlockCount'] == baseline['filesystemBlockCount'],
                    'Filesystem geometry changed after review')
            require(before['filesystemBlockCount'] < before['targetBlockCount'], 'Growth only')
            for entry in Path('/proc').iterdir():
                if entry.name.isdigit():
                    try:
                        require((entry / 'comm').read_text().strip() != 'resize2fs',
                                'An existing resize2fs process requires observation; do not overlap')
                    except (FileNotFoundError, ProcessLookupError):
                        pass
            stdout_path = OUT / (ident + '.resize.stdout')
            stderr_path = OUT / (ident + '.resize.stderr')
            cmd = ['resize2fs', LV]
            receipt.update(state='resize_starting', command=cmd)
            save()
            with stdout_path.open('x') as stdout, stderr_path.open('x') as stderr:
                for p in [stdout_path, stderr_path]:
                    os.chmod(p, 0o600)
                    os.chown(p, operator.pw_uid, operator.pw_gid)
                proc = subprocess.Popen(cmd, stdout=stdout, stderr=stderr,
                                        env={**os.environ, 'LC_ALL': 'C'}, start_new_session=True)
                receipt.update(state='resize_running', resizePID=proc.pid,
                               stdout=str(stdout_path), stderr=str(stderr_path))
                save()
                try:
                    code = proc.wait(timeout=300)
                except subprocess.TimeoutExpired:
                    # Never kill a filesystem resize to satisfy a monitoring timeout.
                    receipt.update(state='resize_still_running_requires_observation', observedUTC=utc())
                    save()
                    print(json.dumps({'state': receipt['state'], 'pid': proc.pid, 'receipt': str(receipt_path)}))
                    return 75
            receipt['resizeExitCode'] = code
            receipt['after'] = inspect()
            receipt['endedUTC'] = utc()
            require(code == 0, 'resize2fs returned nonzero; preserve output and inspect')
            require(receipt['after']['filesystemBlockCount'] == before['targetBlockCount'],
                    'Expected full existing-device filesystem size not observed')
            receipt['state'] = 'online_filesystem_growth_verified'
            save()
            print(json.dumps({'state': receipt['state'], 'receipt': str(receipt_path),
                              'before': before['statvfs'], 'after': receipt['after']['statvfs']}))
            return 0
        except Exception as exc:
            receipt.update(state='failed_preserve_evidence', error=str(exc), observedUTC=utc())
            save()
            raise


if __name__ == '__main__':
    sys.exit(main())
