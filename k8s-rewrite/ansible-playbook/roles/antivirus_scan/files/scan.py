#!/usr/bin/env python3
"""Finite, report-only ClamAV scan of host files and mounted local application data."""
import datetime
import hashlib
import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import sys

ROOT = pathlib.Path('/var/lib/branconet-antivirus')
generation = sys.argv[1]
only_volume = sys.argv[2].split('=', 1)[1] if len(sys.argv) == 3 and sys.argv[2].startswith('--only-volume=') else ''
if not re.fullmatch(r'[a-z0-9][a-z0-9-]{7,60}', generation) or os.getuid() != 0:
    raise SystemExit('Invalid finite scan identity or caller')
if only_volume and not re.fullmatch(r'pvc-[a-f0-9-]{36}', only_volume):
    raise SystemExit('Invalid supplemental volume identity')
work = ROOT / generation
work.mkdir(mode=0o700)  # Exclusive creation: no overwritten or replayed attempts.
status = {'hostname': socket.gethostname(), 'scanId': generation,
          'startedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'status': 'updating-signatures', 'destructiveActions': False}
scratch_identity = None

def record():
    temporary = work / 'status.new'
    temporary.write_text(json.dumps(status, indent=2) + '\n')
    temporary.replace(work / 'status.json')

def command(args, log, timeout=None):
    with (work / log).open('x') as stream:
        return subprocess.run(args, stdout=stream, stderr=subprocess.STDOUT,
                              timeout=timeout, check=False).returncode

record()
try:
    # Prevent competing database writers. Freshclam is enabled after the finite update.
    subprocess.run(['systemctl', 'stop', 'clamav-freshclam'], check=True)
    result = command(['freshclam', '--stdout'], 'freshclam.log', timeout=1800)
    status['signatureUpdateExitCode'] = result
    if result:
        raise RuntimeError('Freshclam failed; inspect preserved updater log')
    subprocess.run(['systemctl', 'enable', '--now', 'clamav-freshclam'], check=True,
                   stdout=subprocess.DEVNULL)
    status['scannerVersion'] = subprocess.check_output(['clamscan', '--version'], text=True).strip()
    status['databases'] = []
    for p in pathlib.Path('/var/lib/clamav').iterdir():
        if p.suffix in {'.cvd', '.cld', '.cud'}:
            status['databases'].append({'name': p.name, 'bytes': p.stat().st_size,
                                        'mtime': p.stat().st_mtime})
    mounts = json.loads(subprocess.check_output(
        ['findmnt', '-J', '-o', 'TARGET,SOURCE,FSTYPE,MAJ:MIN,FSROOT'], text=True))
    entries = []
    def visit(items):
        for item in items:
            entries.append({k: v for k, v in item.items() if k != 'children'})
            visit(item.get('children', []))
    visit(mounts['filesystems'])
    # Scan mounted plaintext local filesystems once, preferring whole CSI staging mounts.
    selected = {}
    network = []
    for m in entries:
        target = m['target']
        if m['fstype'] in {'cifs', 'nfs', 'nfs4', 'smb3', 'glusterfs'}:
            network.append(m)
        if m['fstype'] not in {'ext4', 'xfs', 'btrfs', 'vfat', 'squashfs', 'tmpfs'}:
            continue
        if target.startswith(('/proc', '/sys', '/dev/')) and target != '/dev/shm':
            continue
        if m.get('fsroot') != '/' or '/volume-subpaths/' in target:
            continue
        # CSI pod aliases duplicate staging mounts. They are not separately scanned.
        key = (m['maj:min'], m.get('fsroot'))
        previous = selected.get(key)
        score = (0 if target == '/' else 1 if '/globalmount' in target else 2, len(target))
        if previous is None or score < previous[0]:
            selected[key] = (score, m)
    roots = sorted({m['target'] for _, m in selected.values()})
    if only_volume:
        roots = sorted({m['target'] for _, m in selected.values()
                        if m['fstype'] == 'ext4' and m['source'] == '/dev/mapper/' + only_volume})
        if len(roots) != 1:
            raise RuntimeError('Expected one whole mounted plaintext supplemental volume')
    if not only_volume and '/' not in roots:
        raise RuntimeError('Root filesystem missing from scan scope')
    status.update({'status': 'scanning', 'scanRoots': roots, 'networkMountsExcluded': network,
                   'scope': 'All host local files, unpacked container images and mounted plaintext local application filesystems',
                   'exclusions': ['virtual proc/sys/dev filesystems except /dev/shm',
                                  'network NAS shares (not node-local filesystems)',
                                  'encrypted Longhorn raw backing images (mounted plaintext is scanned)',
                                  'duplicate CSI pod aliases and volume-subpath aliases',
                                  'scanner signatures/results and its bounded temporary mount'],
                   'engineLimits': {'maxFileMiB': 2048, 'maxExpandedScanMiB': 4096,
                                    'maxArchiveFiles': 100000, 'maxRecursion': 32,
                                    'maxFileScanMs': 600000}})
    if only_volume:
        status.update({'scope': 'Supplemental relocated mounted plaintext volume',
                       'supplementalVolume': only_volume})
    record()
    scratch = work / 'tmp'
    scratch.mkdir(mode=0o700)
    # Reserve all scratch space before scanning; never format an existing file or device.
    free = os.statvfs(work)
    if free.f_bavail * free.f_frsize < 15 * 1024**3 + 4 * 1024**3 + 512 * 1024**2:
        raise RuntimeError('Insufficient capacity for reserved scratch plus 15 GiB floor')
    image = work / 'scratch.ext4'
    fd = os.open(image, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.posix_fallocate(fd, 0, 4 * 1024**3)
        info = os.fstat(fd)
        scratch_identity = (info.st_dev, info.st_ino)
    finally:
        os.close(fd)
    status['scratchAllocatedBytes'] = image.stat().st_blocks * 512
    record()
    subprocess.run(['mkfs.ext4', '-q', '-F', '-m', '0', '-E',
                    'nodiscard,lazy_itable_init=0,lazy_journal_init=0',
                    '-L', 'branconet-av', str(image)], check=True)
    if image.stat().st_blocks * 512 < 4 * 1024**3:
        raise RuntimeError('Scratch reservation was not retained after formatting')
    subprocess.run(['mount', '-o', 'loop,nosuid,nodev,noexec', str(image), str(scratch)], check=True)
    args = ['clamscan', '--recursive=yes', '--cross-fs=no', '--follow-dir-symlinks=0',
            '--follow-file-symlinks=0', '--infected', '--official-db-only=yes',
            '--fail-if-cvd-older-than=2', '--alert-exceeds-max=yes', '--max-filesize=2048M',
            '--max-scansize=4096M', '--max-recursion=32', '--max-files=100000',
            '--max-scantime=600000', '--tempdir=' + str(scratch),
            '--exclude-dir=^/var/lib/(clamav|branconet-antivirus)(/|$)',
            '--exclude-dir=^/var/lib/kubelet/pods/[^/]+/(volume-subpaths|volumes/kubernetes.io~csi)(/|$)',
            '--exclude=^/var/lib/longhorn/replicas/[^/]+/volume-(head|snap)-.*[.]img$',
            *roots]
    status['arguments'] = args
    record()
    status['exitCode'] = command(args, 'clamscan.log')
    log = (work / 'clamscan.log').read_text(errors='replace')
    found = [line for line in log.splitlines() if line.endswith(' FOUND')]
    status['detections'] = [line for line in found if 'Heuristics.Limits.Exceeded' not in line]
    status['limitAlerts'] = [line for line in found if 'Heuristics.Limits.Exceeded' in line]
    status['errors'] = [line for line in log.splitlines() if 'ERROR' in line or 'WARNING' in line]
    status['summary'] = log.rsplit('SCAN SUMMARY', 1)[-1].strip()
    status['logSha256'] = hashlib.sha256((work / 'clamscan.log').read_bytes()).hexdigest()
    status['status'] = 'completed' if status['exitCode'] in (0, 1) else 'scan-error'
except Exception as error:
    status['status'] = 'failed'
    status['failure'] = type(error).__name__ + ': ' + str(error)
finally:
    scratch = work / 'tmp'
    if scratch.is_mount():
        cleanup = subprocess.run(['umount', str(scratch)], capture_output=True, text=True)
        status['scratchUnmountExitCode'] = cleanup.returncode
    if scratch.exists() and not scratch.is_mount():
        try:
            scratch.rmdir()
            status['scratchRemoved'] = True
        except OSError:
            status['scratchRetained'] = 'Nonempty temporary directory; no recursive cleanup attempted'
    image = work / 'scratch.ext4'
    if image.exists() and scratch_identity:
        info = image.lstat()
        loops = subprocess.run(['losetup', '-j', str(image)], capture_output=True, text=True)
        if (not image.is_symlink() and (info.st_dev, info.st_ino) == scratch_identity
                and not scratch.is_mount() and loops.returncode == 0 and not loops.stdout.strip()):
            status['scratchImageAllocatedBytesRemoved'] = info.st_blocks * 512
            image.unlink()
        else:
            status['scratchImageRetained'] = 'Identity, mount or live loop-device safety check failed'
    status['completedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record()
sys.exit(0 if status['status'] == 'completed' else 2)
