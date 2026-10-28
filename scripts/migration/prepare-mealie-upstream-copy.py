#!/usr/bin/env python3
"""Prepare one upstream Mealie filesystem for isolated migration, never deployment."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import urllib.request

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'upstream-mealie-20261026'
CONTROL = ROOT / 'operator-control'
IMAGE = 'ghcr.io/mealie-recipes/mealie:v3.29.0@sha256:78eb28b8776d0bad40c5e605c72b3f4f5976793e491558c7dcbdfc04c835d4bc'
TOOL_URL = 'https://github.com/google/go-containerregistry/releases/download/v0.22.1/go-containerregistry_Linux_x86_64.tar.gz'
TOOL_ARCHIVE_SHA = '0ab7a1d6932a213aed964ce97666c3077fe691c8606413674a8b3e0b9ec4cda0'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def main():
    assert sys.argv[1:] == ['--apply'] and os.getuid() == 1000
    assert OUT.resolve() == OUT and OUT.is_mount() and OUT.stat().st_dev != Path('/').stat().st_dev
    assert Path('/proc/self/cgroup').read_text().strip().endswith('/branconet-mealie-copy-prepare-r2-20261026.service')
    group = Path('/sys/fs/cgroup') / Path('/proc/self/cgroup').read_text().strip().removeprefix('0::').lstrip('/')
    assert (group / 'memory.max').read_text().strip() == str(1024**3)
    assert (group / 'memory.swap.max').read_text().strip() == '0'
    assert not Path('/home/brajam/.ssh').exists() and not os.access('/mnt/c/Users', os.R_OK | os.X_OK)
    os.umask(0o077)
    for name in ['home', 'tmp', 'docker-config']:
        assert (OUT / name).is_dir() and not (OUT / name).stat().st_mode & 0o077
    free = os.statvfs(OUT)
    assert free.f_bavail * free.f_frsize >= 20 * 1024**3
    receipt = OUT / 'prepare.json'
    assert not receipt.exists()
    report = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'passed': False,
              'sourceSHA256': sha(Path(__file__)), 'image': IMAGE, 'productionChanged': False,
              'deploymentImageSource': False, 'purpose': 'Isolated vendor migration qualification only'}
    try:
        archive = OUT / 'go-containerregistry-v0.22.1.tar.gz'
        assert not archive.exists()
        with urllib.request.urlopen(TOOL_URL, timeout=60) as response, archive.open('xb') as target:
            total = 0
            for block in iter(lambda: response.read(1024**2), b''):
                total += len(block)
                assert total <= 32 * 1024**2
                target.write(block)
        assert sha(archive) == TOOL_ARCHIVE_SHA
        crane = OUT / 'crane'
        assert not crane.exists()
        with tarfile.open(archive, 'r:gz') as bundle:
            member = bundle.getmember('crane')
            assert member.isfile() and member.size <= 64 * 1024**2
            with crane.open('xb') as stream:
                stream.write(bundle.extractfile(member).read())
        crane.chmod(0o500)
        report['tool'] = {'url': TOOL_URL, 'archiveSHA256': TOOL_ARCHIVE_SHA,
                          'path': str(crane), 'sha256': sha(crane)}
        filesystem = OUT / 'vendor-rootfs.tar'
        assert not filesystem.exists()
        errors = OUT / 'export.stderr'
        with filesystem.open('xb') as target, errors.open('xb') as error:
            child = subprocess.Popen([str(crane), 'export', '--platform=linux/amd64', IMAGE, '-'],
                                     stdout=target, stderr=error)
            try:
                assert child.wait(timeout=480) == 0
            finally:
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=15)
        assert 0 < filesystem.stat().st_size <= 2 * 1024**3
        rootfs = OUT / 'vendor-rootfs'
        rootfs.mkdir(mode=0o700)
        # Tar can write only the new output directory; absolute symlinks cannot
        # reach a writable host filesystem. No host home, socket or network exists.
        cmd = ['/usr/bin/bwrap', '--unshare-all', '--new-session', '--die-with-parent',
               '--ro-bind', '/usr', '/usr', '--symlink', 'usr/bin', '/bin',
               '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/lib64', '/lib64',
               '--ro-bind', str(filesystem), '/image.tar', '--bind', str(rootfs), '/out',
               '--bind', str(OUT / 'tmp'), '/tmp', '--chdir', '/out', '--',
               '/usr/bin/tar', '--extract', '--file=/image.tar', '--no-same-owner', '--no-same-permissions']
        with (OUT / 'extract.stderr').open('xb') as error:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=error, check=True, timeout=240)
        installed = rootfs / 'opt/mealie/lib/python3.14/site-packages/mealie/db/init_db.py'
        if not installed.exists():
            installed = rootfs / 'opt/mealie/lib64/python3.14/site-packages/mealie/db/init_db.py'
        source = CONTROL / 'mealie-vendor-mealie_db_init_db.py'
        assert installed.is_file() and sha(installed) == sha(source)
        report.update(passed=True, filesystemArchive=str(filesystem), filesystemArchiveSHA256=sha(filesystem),
                      filesystemArchiveBytes=filesystem.stat().st_size, rootfs=str(rootfs),
                      installedMigrationSourceSHA256=sha(installed), allOutputsInsideDeclaredRoot=True)
    except Exception as error:
        report['failureCategory'] = type(error).__name__
    finally:
        with receipt.open('x') as stream:
            json.dump(report, stream, indent=2)
        print(json.dumps(report), flush=True)
    return int(not report['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
