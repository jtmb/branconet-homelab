"""Read-only verification before a helper-only refresh; no scanner or transfer."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import stat
import sys

ROOT = Path('/home/james/.local/share/branconet-migration/worker1-oci-scan-20261023')
FILES = {
    'bin/trivy': (176029856, 'd1dfca6ae10a1ad4540bb94e64f0510077c47008920a9b554986b39dca573d83', 0o500),
    'cache/db/trivy.db': (1628737536, '6fd7f9c44ff3120e0d15d5b5b2234e1ff1c9e7a6b56b4e776041f93faf1f6f17', 0o400),
    'cache/db/metadata.json': (150, 'd2caf386c5ec60a3fc13376aebe5cd9a236f4c20940e3eec361d4c51c544bce9', 0o400),
    'cache/java-db/trivy-java.db': (1560596480, '728fa5500d93bb1a592f8477b8a2c9494c712bcfe6b603c9fef5386d5433cc3d', 0o400),
    'cache/java-db/metadata.json': (153, '0f5c76eb37d3cee66cb7da09f8238dd5bab2b0d0eb5f05cf37006af7a4234957', 0o400),
    'results.tpl': (15, 'd5a74b8473128e4c4c58d0329523c990adfff71452c9039592190ae6ddb84e8e', 0o500),
    'no-ignore': (0, hashlib.sha256(b'').hexdigest(), 0o400),
    'trivy-empty.yaml': (3, hashlib.sha256(b'{}\n').hexdigest(), 0o400),
}


def need(value):
    if not value:
        raise ValueError('installed_scanner_input_identity_refused')


def fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
            info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode), info.st_nlink)


def directory(path, uid, gid):
    need(path.resolve() == path)
    info = path.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == uid and info.st_gid == gid
         and stat.S_IMODE(info.st_mode) == 0o700)


def main():
    need(socket.gethostname() == 'workernode1' and os.geteuid() == 0)
    need(len(sys.argv) == 2 and sys.argv[1].isdigit())
    helper_bytes = int(sys.argv[1])
    need(0 < helper_bytes <= 256 * 1024)
    owner = pwd.getpwnam('james')
    for relative in ['', 'bin', 'cache', 'cache/db', 'cache/java-db', 'tmp', 'home', 'docker-config', 'attempts']:
        directory(ROOT / relative, owner.pw_uid, owner.pw_gid)
    directory(ROOT / 'helpers', 0, 0)
    space = os.statvfs(ROOT)
    floor = space.f_blocks * space.f_frsize // 4 + 8 * 1024 ** 3
    # Keep the original floor intact while accounting only for the small helper
    # transfer/atomic copy and a conservatively bounded new JSON seal.
    required = floor + 2 * (helper_bytes + 64 * 1024)
    need(space.f_bavail * space.f_frsize >= required)
    need(space.f_favail >= max(250000, space.f_files // 10))
    verified = {}
    for relative, (size, sha, mode) in FILES.items():
        path = ROOT / relative
        need(path.resolve() == path)
        before = path.lstat()
        need(stat.S_ISREG(before.st_mode) and before.st_uid == 0 and before.st_gid == 0
             and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == mode and before.st_size == size)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            need(fingerprint(os.fstat(fd)) == fingerprint(before))
            digest = hashlib.sha256()
            count = 0
            with os.fdopen(os.dup(fd), 'rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
                    count += len(block)
                    need(count <= size)
            need(count == size and digest.hexdigest() == sha)
            need(fingerprint(os.fstat(fd)) == fingerprint(path.lstat()) == fingerprint(before))
        finally:
            os.close(fd)
        verified[relative] = {'bytes': size, 'sha256': sha, 'mode': oct(mode), 'rootOwned': True}
    print(json.dumps({'state': 'installed_inputs_verified', 'files': verified,
                      'filesystemFloorBytes': floor, 'requiredAvailableBytes': required,
                      'helperBytes': helper_bytes, 'scannerExecuted': False,
                      'inputsCopiedOrChanged': False}, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Installed scanner input verification refused; no inputs changed')
