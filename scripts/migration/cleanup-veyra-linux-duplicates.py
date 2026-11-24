#!/usr/bin/env python3
"""Retire exact public TSX duplicates in the existing Veyra task root only."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import time

ROOT = Path('/home/brajam/.local/state/ingenium-release/skill-zen-fix-1792810845')
PHASE = ROOT / 'real-gmail-ui/veyra-phase-1'
APP = PHASE.parent / 'prd-ui-fixes'
TARGET = PHASE / 'tmp/tsx-1000'
PEER = ROOT / 't/tsx-1000'
RECEIPT = PHASE / 'evidence/linux-public-duplicate-cleanup-20261105.json'
WINPY = '/mnt/c/Users/james/AppData/Local/Programs/Python/Python312/python.exe'
OWNER = '01a18518-24e7-7ce3-b620-f9ca775bfd1c'


def need(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def call(args):
    return subprocess.check_output(args, timeout=30)


def free_windows():
    return int(call([WINPY, '-I', '-B', '-c', "import shutil;print(shutil.disk_usage('C:/').free)"]))


def aggregate():
    return int(call(['/usr/bin/du', '-x', '-s', '-B1', '--', str(ROOT)]).split(None, 1)[0])


def refs(target, identities):
    """Metadata only: do not open private application/recovery payloads."""
    needles = [os.fsencode(target), ('\\\\wsl.localhost\\Ubuntu' + str(target).replace('/', '\\')).encode(),
               ('\\\\wsl$\\Ubuntu' + str(target).replace('/', '\\')).encode()]
    count = 0
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            state = (proc / 'stat').read_text().split(') ', 1)[1].split()[0]
            if state in ['Z', 'X']:
                continue
            for name in ['cmdline', 'environ', 'maps', 'mountinfo']:
                value = (proc / name).read_bytes()
                need(not any(needle in value for needle in needles), 'Active ' + name + ' reference PID ' + proc.name)
            for item in [proc / 'cwd', proc / 'root', proc / 'exe', *list((proc / 'fd').iterdir())]:
                try:
                    value = os.readlink(item)
                    metadata = item.stat()
                except (FileNotFoundError, ProcessLookupError):
                    continue
                need(not any(needle in os.fsencode(value) for needle in needles), 'Active process handle PID ' + proc.name)
                need((metadata.st_dev, metadata.st_ino) not in identities, 'Active inode handle PID ' + proc.name)
            count += 1
        except (FileNotFoundError, ProcessLookupError):
            continue
        except OSError:
            try:
                state = (proc / 'stat').read_text().split(') ', 1)[1].split()[0]
            except (FileNotFoundError, ProcessLookupError):
                continue
            if state in ['Z', 'X']:
                continue
            raise
    need(os.fsencode(target) not in Path('/proc/self/mountinfo').read_bytes(), 'Active local mount reference')
    need(os.fsencode(target) not in Path('/proc/net/unix').read_bytes(), 'Active socket reference')
    identifiers = call(['docker', 'ps', '-aq']).decode().split()
    for identifier in identifiers:
        mounts = json.loads(call(['docker', 'inspect', '--format', '{{json .Mounts}}', identifier]))
        for mount in mounts:
            source = Path(mount['Source']).resolve()
            need(not target.is_relative_to(source) and not source.is_relative_to(target),
                 'Existing container mount reference ' + identifier[:12])
    return {'liveProcessesInspected': count, 'existingContainersInspected': len(identifiers),
            'namespaces': 'Every observed live process mountinfo; handles/inodes include WSL file-serving processes'}


def main():
    need(os.getuid() == 0, 'Root is required for complete reference metadata, not private payload access')
    need(ROOT.resolve() == ROOT and ROOT.stat().st_ino == 12798666 and ROOT.stat().st_dev == 2096, 'Task root identity changed')
    need(json.loads((PHASE / 'output-ownership.json').read_text())['activeOwner']['threadId'] ==
         '01a188fc-d3ed-7dc2-ab95-e0eed8a793ec', 'Coordinator ownership changed')
    need(not RECEIPT.exists(), 'Existing cleanup attempt must not be replayed')
    record = {'owner': OWNER, 'scope': 'Independent phase/tmp TSX cache duplicates; ROOT/t is preserved as the reconstruction source',
              'soleRoot': str(ROOT), 'physicalVolume': 'Ubuntu ext4 VHDX on Windows C: EE22980A',
              'outputCeilingBytes': 2 * 1024**2, 'regeneration': 'Restore each exact recorded retained peer byte-for-byte into its original target path; retained source/lock and original cache JSON survive',
              'protected': 'All source/locks/unique evidence/models/voice environments/private recovery/rejected targets/Native outputs',
              'before': {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'linuxAllocatedBytes': aggregate(),
                         'windowsFreeBytes': free_windows(), 'destinationFreeBytes': os.statvfs(ROOT).f_bavail * os.statvfs(ROOT).f_frsize},
              'planned': [], 'removed': [], 'retained': [], 'emptyDirectoriesRemoved': [], 'windowsRecoveryClaimed': False}
    record['heldPrefix'] = {'path': str(ROOT / 't'), 'reason': 'No complete permitted earlier-refusal registry clears ROOT/t; preserve per coordinator guidance'}
    record['permittedControlRegistryReview'] = {'records': 362, 'knownTargetPrefixRefusals': [],
        'inaccessibleRecordNotRetried': str(PHASE / 'evidence/home-browser-scratch-reconciliation.json')}
    need(record['before']['windowsFreeBytes'] >= 15 * 1024**3 and record['before']['destinationFreeBytes'] >= 15 * 1024**3, 'Storage floors unavailable')
    locks = [APP / 'package.json', APP / 'package-lock.json', APP / 'services/veyra-api/Cargo.lock', APP / 'services/veyra-swarm/Cargo.lock']
    protected = {str(path): sha(path) for path in locks}
    record['protectedSourceLocks'] = protected
    receipt_identity = None

    def save():
        nonlocal receipt_identity
        body = (json.dumps(record, indent=2) + '\n').encode()
        need(len(body) <= record['outputCeilingBytes'], 'Minimal receipt ceiling exceeded')
        flags = os.O_WRONLY | os.O_NOFOLLOW | (os.O_CREAT | os.O_EXCL if receipt_identity is None else 0)
        fd = os.open(RECEIPT, flags, 0o600)
        try:
            metadata = os.fstat(fd)
            identity = (metadata.st_dev, metadata.st_ino)
            need(receipt_identity is None or receipt_identity == identity, 'Receipt identity changed')
            need(metadata.st_nlink == 1, 'Receipt has outside hard link')
            receipt_identity = identity
            os.fchown(fd, 1000, 1000)  # Keep this new sanitized control record readable by its task owner.
            os.fchmod(fd, 0o600)
            os.ftruncate(fd, 0)
            with os.fdopen(os.dup(fd), 'wb') as output:
                output.write(body)
                output.flush()
                os.fsync(output.fileno())
        finally:
            os.close(fd)

    need(TARGET.resolve() == TARGET and PEER.resolve() == PEER and TARGET.is_relative_to(ROOT) and
         not TARGET.is_relative_to(ROOT / 't') and not (ROOT / 't').is_relative_to(TARGET), 'Candidate escaped or touched held prefix')
    for path in sorted(TARGET.iterdir()):
        info = path.lstat()
        peer = PEER / path.name
        try:
            need(stat.S_ISREG(info.st_mode) and info.st_uid == 1000 and info.st_mode & 0o044 and info.st_nlink == 1, 'Not an independent public task-owned regular cache')
            need(time.time() - max(info.st_mtime, info.st_ctime) >= 72 * 3600, 'Older-copy inactivity window unavailable')
            need(peer.resolve() == peer and peer.is_file() and not peer.is_symlink(), 'Exact retained public peer missing')
            peer_info = peer.lstat()
            need(peer_info.st_uid == 1000 and peer_info.st_mode & 0o044 and
                 (info.st_dev, info.st_ino) != (peer_info.st_dev, peer_info.st_ino), 'Retained peer is not a separate public copy')
            payload = json.loads(path.read_text())
            need(set(payload) == {'code', 'warnings', 'map'} and isinstance(payload['code'], str), 'Unqualified transform format')
            digest = sha(path)
            need(digest == sha(peer), 'Exact retained peer bytes differ')
            row = {'path': str(path), 'peer': str(peer), 'bytes': info.st_size, 'linuxAllocatedBytes': info.st_blocks * 512,
                   'sha256': digest, 'device': info.st_dev, 'inode': info.st_ino, 'mtimeNs': info.st_mtime_ns,
                   'peerDevice': peer_info.st_dev, 'peerInode': peer_info.st_ino, 'regeneration': 'Byte-for-byte restore from unchanged retained peer; JSON includes original code/warnings/source map',
                   'lastConsumer': 'Old task-only transform cache; exact retained primary copy remains; complete references must pass before unlink'}
            record['planned'].append(row)
        except Exception as error:
            record['retained'].append({'path': str(path), 'reason': str(error), 'linuxAllocatedBytes': info.st_blocks * 512})
    save()
    for row in record['planned']:
        path, peer = Path(row['path']), Path(row['peer'])
        try:
            record['referenceChecks'] = refs(TARGET, {(r['device'], r['inode']) for r in record['planned']} |
                                            {(TARGET.stat().st_dev, TARGET.stat().st_ino)})
            need(all(sha(Path(name)) == digest for name, digest in protected.items()), 'Original source/locks changed')
            info = path.lstat()
            need((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_nlink) ==
                 (row['device'], row['inode'], row['bytes'], row['mtimeNs'], 1), 'Original duplicate identity changed')
            need(sha(path) == row['sha256'] == sha(peer), 'Duplicate/retained peer bytes changed')
            need((peer.stat().st_dev, peer.stat().st_ino) == (row['peerDevice'], row['peerInode']), 'Retained peer identity changed')
            record['nextUnlink'] = row['path']
            save()
            path.unlink()
            record['removed'].append(row)
            record.pop('nextUnlink', None)
            need(sha(peer) == row['sha256'], 'Retained original peer changed after unlink')
        except Exception as error:
            record['retained'].append({'path': str(path), 'reason': str(error), 'linuxAllocatedBytes': row['linuxAllocatedBytes']})
            record.pop('nextUnlink', None)
            save()
            break  # No same-target retry or alternate parent/child deletion.
        save()
    for directory in [TARGET, TARGET.parent]:
        try:
            if any(directory.iterdir()):
                continue
            info = directory.lstat()
            need(directory.resolve() == directory and directory.is_relative_to(ROOT) and info.st_uid == 1000, 'Empty directory ownership changed')
            refs(directory, {(info.st_dev, info.st_ino)})
            directory.rmdir()
            record['emptyDirectoriesRemoved'].append({'path': str(directory), 'linuxAllocatedBytes': info.st_blocks * 512})
        except Exception as error:
            record['retained'].append({'path': str(directory), 'reason': str(error)})
    need(all(sha(Path(name)) == digest for name, digest in protected.items()), 'Original source/locks changed across cleanup')
    for row in record['removed']:
        need(sha(Path(row['peer'])) == row['sha256'], 'Retained reconstruction source changed')
    record['linuxAllocatedBytesRemoved'] = sum(row['linuxAllocatedBytes'] for row in record['removed'] + record['emptyDirectoriesRemoved'])
    record['after'] = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'linuxAllocatedBytes': aggregate(),
                       'windowsFreeBytes': free_windows(), 'destinationFreeBytes': os.statvfs(ROOT).f_bavail * os.statvfs(ROOT).f_frsize}
    record['sourceLocksAndRetainedPeersPreserved'] = True
    save()
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
