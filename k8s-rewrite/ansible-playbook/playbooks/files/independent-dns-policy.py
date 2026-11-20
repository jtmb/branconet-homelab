#!/usr/bin/python3
"""Stage an integrity-checked Pi-hole gravity copy for the standalone resolver."""
import argparse
from contextlib import closing
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time

MAX_BYTES = 128 * 1024**2
FREE_FLOOR = 20 * 1024**3
STAGING_MOUNT = re.compile(
    r"/var/lib/kubelet/plugins/kubernetes\.io/csi/driver\.longhorn\.io/[a-f0-9]{64}/globalmount"
)


def locate(volume):
    if not re.fullmatch(r"pvc-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", volume):
        raise ValueError("Expected the exact Longhorn PVC volume ID.")
    mapper = "/dev/mapper/" + volume
    process = subprocess.run(
        ["findmnt", "-J", "-l", "-S", mapper, "-o", "TARGET,SOURCE,FSTYPE,FSROOT"],
        capture_output=True, text=True, timeout=5,
    )
    if process.returncode:
        raise ValueError("The standby's encrypted Longhorn volume is not mounted here.")
    mounts = [row for row in json.loads(process.stdout)["filesystems"]
              if row["source"] == mapper and row["fstype"] == "ext4" and row["fsroot"] == "/"
              and STAGING_MOUNT.fullmatch(row["target"])]
    if len(mounts) != 1:
        raise ValueError("Could not identify one exact standby CSI staging mount.")
    source = Path(mounts[0]["target"]) / "gravity.db"
    if not stat.S_ISREG(source.lstat().st_mode):
        raise ValueError("The source gravity database is not a regular file.")
    return source


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def backup(source, candidate):
    deadline = time.monotonic() + 30

    def enforce_deadline(*_):
        if time.monotonic() > deadline:
            raise ValueError("The SQLite backup did not complete in time.")

    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=3)) as reader:
        with closing(sqlite3.connect(candidate)) as writer:
            reader.backup(writer, pages=256, progress=enforce_deadline, sleep=.05)
            if writer.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise ValueError("The candidate gravity database failed its SQLite integrity check.")
            groups = writer.execute('SELECT count(*) FROM "group" WHERE enabled=1').fetchone()[0]
            clients = writer.execute("SELECT count(*) FROM client").fetchone()[0]
            domains = writer.execute("SELECT count(*) FROM gravity").fetchone()[0]
            if groups != 1 or clients != 0 or domains == 0:
                raise ValueError("Filtering policy differs from the standalone resolver qualification.")
    if candidate.stat().st_size > MAX_BYTES:
        raise ValueError("The completed snapshot exceeds the policy size bound.")
    return domains


def refresh(volume, state):
    info = state.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Use the operator-owned private policy directory.")
    if shutil.disk_usage(state).free < FREE_FLOOR + MAX_BYTES:
        raise ValueError("The worker cannot retain the required free-space floor after refresh.")
    lock_fd = os.open(state / "refresh.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        source = locate(volume)
        initial = source.lstat()
        if not 0 < initial.st_size <= MAX_BYTES:
            raise ValueError("The source gravity database exceeds the policy size bound.")
        destination = state / "gravity.db"
        if destination.exists() or destination.is_symlink():
            previous = destination.lstat()
            if (not stat.S_ISREG(previous.st_mode) or previous.st_uid != os.getuid()
                    or previous.st_mode & 0o077 or previous.st_nlink != 1):
                raise ValueError("The last-good policy is not a private regular file.")
        # The staged copy is never an FTL writable database. A resolver consumes a separate copy.
        with tempfile.TemporaryDirectory(prefix=".gravity-stage-", dir=state) as work:
            candidate = Path(work) / "gravity.db"
            domains = backup(source, candidate)
            fresh = locate(volume).lstat()
            if (initial.st_dev, initial.st_ino) != (fresh.st_dev, fresh.st_ino):
                raise ValueError("The standby database changed identity during refresh.")
            digest = checksum(candidate)
            if destination.exists() and checksum(destination) == digest:
                return {"updated": False, "domains": domains, "sha256": digest}
            candidate.chmod(0o600)
            with candidate.open("rb") as stream:
                os.fsync(stream.fileno())
            os.replace(candidate, destination)
            directory = os.open(state, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            return {"updated": True, "domains": domains, "sha256": digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--volume", required=True)
    parser.add_argument("--state", type=Path, required=True)
    options = parser.parse_args()
    print(json.dumps(refresh(options.volume, options.state)))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.SubprocessError) as error:
        print(str(error) if type(error) is ValueError else "The gravity policy refresh failed.", file=sys.stderr)
        sys.exit(1)
