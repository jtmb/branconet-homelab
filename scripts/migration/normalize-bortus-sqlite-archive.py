#!/usr/bin/env python3
"""Authenticate a cold archive and normalize only its private tmpfs copy."""
import argparse
import hashlib
import importlib.util
import json
import math
import os
import pathlib
import sqlite3
import stat
import struct
import subprocess
import sys
import tempfile
import time

spec = importlib.util.spec_from_file_location('sqlite_archive',
    pathlib.Path(__file__).with_name('bortus-sqlite-archive.py'))
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


class RecoveryError(Exception):
    pass


def require(condition):
    if not condition:
        raise RecoveryError('sqlite_archive_normalization_failed')


def identity(path):
    item = path.lstat()
    return (item.st_dev, item.st_ino, item.st_uid)


def tmpfs_parent(parent):
    parent = pathlib.Path(parent)
    require(os.name == 'posix' and str(parent) == '/dev/shm' and
            parent.resolve() == parent and parent.is_dir())
    entries = pathlib.Path('/proc/self/mountinfo').read_text().splitlines()
    require(any(line.split()[4] == '/dev/shm' and line.split(' - ', 1)[1].split()[0] == 'tmpfs'
                for line in entries))
    return parent


def cleanup(directory, expected_identity):
    """Remove only four owned files and the exact empty tmpfs directory; never recurse."""
    directory = pathlib.Path(directory)
    require(directory.parent == tmpfs_parent(directory.parent) and
            directory.name.startswith('bortus-sqlite-') and identity(directory) == tuple(expected_identity))
    require(stat.S_IMODE(directory.lstat().st_mode) == 0o700)
    entries = list(directory.iterdir())
    require(all(p.name in archive.FILES and stat.S_ISREG(p.lstat().st_mode) and
                p.lstat().st_uid == os.getuid() for p in entries))
    for path in entries:
        require(identity(directory) == tuple(expected_identity))
        path.unlink()
    directory.rmdir()


def validate_wal(directory, deadline):
    """Refuse damaged current-generation WAL; SQLite handles legitimate stale tails."""
    path = directory / 'bortus.db-wal'
    if not path.exists() or not path.stat().st_size:
        return None
    with path.open('rb') as stream:
        header = stream.read(32)
        require(len(header) == 32)
        magic, version, page_size, _, salt1, salt2, expected0, expected1 = struct.unpack('>8I', header)
        require(magic in (0x377f0682, 0x377f0683) and version == 3007000 and
                512 <= page_size <= 65536 and page_size & (page_size - 1) == 0)
        require((path.stat().st_size - 32) % (24 + page_size) == 0)
        with (directory / 'bortus.db').open('rb') as database:
            db_header = database.read(100)
        db_page_size = int.from_bytes(db_header[16:18], 'big')
        require(page_size == (65536 if db_page_size == 1 else db_page_size))
        order = '<' if magic == 0x377f0682 else '>'

        def checksum(data, seed):
            left, right = seed
            for a, b in struct.iter_unpack(order + 'II', data):
                left = (left + a + right) & 0xffffffff
                right = (right + b + left) & 0xffffffff
            return left, right

        running = checksum(header[:24], (0, 0))
        require(running == (expected0, expected1))
        committed_size = None
        stale = False
        while frame := stream.read(24 + page_size):
            require(time.monotonic() < deadline and len(frame) == 24 + page_size)
            page, size, fsalt1, fsalt2, check0, check1 = struct.unpack('>6I', frame[:24])
            if (fsalt1, fsalt2) != (salt1, salt2):
                stale = True
                continue
            # After a reset, leftover old-salt frames are legitimate; a new-salt frame
            # returning after that tail or a damaged current checksum is ambiguous.
            require(not stale and page > 0)
            running = checksum(frame[24:], checksum(frame[:8], running))
            require(running == (check0, check1))
            if size:
                committed_size = size
        return committed_size


def normalize(source, expected_ciphertext_sha256, identity_file, *, age, parent='/dev/shm', seconds=60,
              deadline=None):
    directory = directory_identity = decryptor = reader = connection = None
    try:
        require(type(seconds) is int and 1 <= seconds <= 300)
        now = time.monotonic()
        require(deadline is None or (type(deadline) in (int, float) and math.isfinite(deadline) and
                                    now < deadline <= now + 300))
        deadline = min(now + seconds, deadline) if deadline is not None else now + seconds
        parent = tmpfs_parent(parent)
        require(len(expected_ciphertext_sha256) == 64 and
                all(c in '0123456789abcdef' for c in expected_ciphertext_sha256))
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as encrypted:
            before = os.fstat(encrypted.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_size <= archive.MAX_TOTAL + 1024 * 1024)
            cipher_hash = hashlib.sha256()
            while block := encrypted.read(archive.CHUNK):
                require(time.monotonic() < deadline)
                cipher_hash.update(block)
            require(cipher_hash.hexdigest() == expected_ciphertext_sha256)
            encrypted.seek(0)
            directory = pathlib.Path(tempfile.mkdtemp(prefix='bortus-sqlite-', dir=parent))
            directory_identity = identity(directory)
            # mkdtemp creates mode700; pin ownership before fallible initialization.
            require(directory_identity[2] == os.getuid() and
                    stat.S_IMODE(directory.lstat().st_mode) == 0o700)
            directory.chmod(0o700)

            def file_factory(name, size):
                require(identity(directory) == directory_identity and name in archive.FILES)
                space = os.statvfs(directory)
                require(size <= space.f_bavail * space.f_frsize)
                fd = os.open(directory / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
                return os.fdopen(fd, 'wb')

            # Read the already hashed, pinned inode through stdin; do not reopen its pathname.
            decryptor = subprocess.Popen([str(age), '-d', '-i', str(identity_file)],
                stdin=encrypted, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            reader = archive.Pipe(decryptor.stdout, deadline, True)
            metadata, _ = archive.transfer(reader, None, file_factory=file_factory)
            require(decryptor.wait(timeout=max(0.01, deadline - time.monotonic())) == 0)
            after = os.fstat(encrypted.fileno())
            require(all(getattr(before, k) == getattr(after, k)
                        for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')))
        # This is a new private memory copy; the source database/volume is never opened by SQLite.
        database = directory / 'bortus.db'
        committed_size = validate_wal(directory, deadline)
        connection = sqlite3.connect(database, timeout=1)
        connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        connection.execute('PRAGMA trusted_schema=OFF')
        checkpoint = connection.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
        require(checkpoint is not None and checkpoint[0] == 0)
        require(list(connection.execute('PRAGMA integrity_check')) == [('ok',)])
        require(connection.execute('PRAGMA foreign_key_check').fetchone() is None)
        if committed_size is not None:
            require(connection.execute('PRAGMA page_count').fetchone()[0] == committed_size)
        connection.close()
        connection = None
        require(database.stat().st_size <= archive.MAX_FILE and time.monotonic() < deadline)
        require(all(not (directory / name).exists() or (directory / name).stat().st_size == 0
                    for name in ('bortus.db-wal', 'bortus.db-journal')))
        require(identity(directory) == directory_identity)
        result = {'temporary_directory': str(directory), 'temporary_directory_identity': list(directory_identity),
                  'database_path': str(database), 'ciphertext_sha256': expected_ciphertext_sha256,
                  'archive_files': metadata['files'], 'archive_plaintext_bytes': metadata['total_bytes'],
                  'authenticated_decryption': True, 'sqlite_checkpointed': True, 'sqlite_integrity': 'ok',
                  'foreign_keys_valid': True, 'plaintext_storage': 'private_tmpfs',
                  'current_wal_checksums_verified': True,
                  'persistent_plaintext_written': False, 'production_database_opened': False,
                  'whole_row_preservation_proven': False, 'independent_native_volume_restore_proven': False}
        directory = None  # Caller owns the qualified memory copy until comparison and exact cleanup.
        return result
    except Exception:
        raise RecoveryError('sqlite_archive_normalization_failed') from None
    finally:
        if connection:
            connection.close()
        if reader:
            reader.close()
        archive.stop_owned(decryptor)
        if decryptor and decryptor.stdout and not decryptor.stdout.closed:
            decryptor.stdout.close()
        if directory:
            cleanup(directory, directory_identity)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--archive')
    mode.add_argument('--cleanup-report')
    parser.add_argument('--ciphertext-sha256')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.cleanup_report:
        require(args.ciphertext_sha256 is None and args.output is None)
        report_path = pathlib.Path(args.cleanup_report)
        require(report_path.stat().st_size <= 16384)
        result = json.loads(report_path.read_text())
        require(result['plaintext_storage'] == 'private_tmpfs' and
                result['database_path'] == str(pathlib.Path(result['temporary_directory']) / 'bortus.db'))
        cleanup(result['temporary_directory'], result['temporary_directory_identity'])
        return
    require(args.ciphertext_sha256 is not None and args.output is not None)
    output = pathlib.Path(args.output)
    require(not os.path.lexists(output))
    runtime = pathlib.Path.home() / '.local/share/branconet-migration'
    result = normalize(args.archive, args.ciphertext_sha256,
        pathlib.Path.home() / '.ssh/id_ed25519', age=runtime / 'bin/age')
    try:
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    except Exception:
        cleanup(result['temporary_directory'], result['temporary_directory_identity'])
        raise RecoveryError('sqlite_archive_normalization_failed') from None


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('sqlite_archive_normalization_failed', file=sys.stderr)
        sys.exit(1)
