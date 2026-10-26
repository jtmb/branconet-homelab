#!/usr/bin/env python3
"""Windows-only bounded ciphertext pipe to the existing recovery destination.

No keys, plaintext, media traversal, mount changes or deletion. A failed partial
is retained. The controller authenticates and compares every decrypted member.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

DESTINATION = Path(r'\\TRUENAS\plex_smb_share\Branconet-Recovery-Backups\2026-10-25\ciphertexts')
ROOT = Path(r'\\wsl.localhost\Ubuntu\home\brajam\.local\share\branconet-migration\local-image-build-offload-20261025')
MAXIMUM = 16 * 1024**3 + 64 * 1024**2
FLOOR = 15 * 1024**3


def need(ok):
    if not ok:
        raise ValueError('Plex ciphertext transport refused')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=['preflight', 'write', 'read'])
    p.add_argument('run_id')
    p.add_argument('--sha256')
    p.add_argument('--bytes', type=int)
    a = p.parse_args()
    need(os.name == 'nt' and uuid.UUID(a.run_id).hex == a.run_id)
    need(DESTINATION.is_dir() and ROOT.is_dir())
    # Build-only process environment; preserve the user's environment/settings.
    os.environ.update(TEMP=str(ROOT / 'operator-control/tmp'), TMP=str(ROOT / 'operator-control/tmp'))
    need(shutil.disk_usage('C:\\').free >= FLOOR)
    need(shutil.disk_usage(ROOT).free >= FLOOR + 128 * 1024**2)
    target = DESTINATION / ('plex-upstream-' + a.run_id + '.tar.age')
    partial = target.with_suffix('.age.partial')
    if a.operation == 'preflight':
        need(shutil.disk_usage(DESTINATION).free >= FLOOR + MAXIMUM)
        need(not target.exists() and not partial.exists())
        print(json.dumps({'passed': True, 'destination': str(target), 'maxCiphertextBytes': MAXIMUM,
                          'nasFreeBytes': shutil.disk_usage(DESTINATION).free,
                          'windowsCFreeBytes': shutil.disk_usage('C:\\').free,
                          'taskRootFreeBytes': shutil.disk_usage(ROOT).free}))
        return
    if a.operation == 'write':
        need(not target.exists() and not partial.exists())
        need(shutil.disk_usage(DESTINATION).free >= FLOOR + MAXIMUM)
        h = hashlib.sha256()
        total = 0
        with partial.open('xb') as out:
            for block in iter(lambda: sys.stdin.buffer.read(1024**2), b''):
                if total == 0:
                    need(block.startswith(b'age-encryption.org/v1\n'))
                total += len(block)
                need(total <= MAXIMUM and shutil.disk_usage(DESTINATION).free >= FLOOR + len(block))
                out.write(block)
                h.update(block)
            need(total > 0)
            out.flush()
            os.fsync(out.fileno())
        need(not target.exists() and partial.stat().st_size == total)
        partial.rename(target)
        print(json.dumps({'path': str(target), 'bytes': total, 'sha256': h.hexdigest(),
                          'sourceOrPartialDeleted': False, 'plaintextWritten': False}))
        return
    need(a.bytes is not None and 0 < a.bytes <= MAXIMUM and a.sha256 is not None
         and len(a.sha256) == 64 and set(a.sha256) <= set('0123456789abcdef'))
    before = target.stat()
    need(before.st_size == a.bytes and not partial.exists())
    h = hashlib.sha256()
    total = 0
    with target.open('rb') as inp:
        for block in iter(lambda: inp.read(1024**2), b''):
            total += len(block)
            need(total <= a.bytes)
            sys.stdout.buffer.write(block)
            h.update(block)
    sys.stdout.buffer.flush()
    after = target.stat()
    need((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
         and total == a.bytes and h.hexdigest() == a.sha256)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(type(e).__name__ + ': ciphertext transport failed; existing data and any partial retained', file=sys.stderr)
        raise SystemExit(1)
