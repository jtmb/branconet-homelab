#!/usr/bin/env python3
"""Move the existing qualified OCI input to H under its recorded release.

Preserve the original access path; never build, import, publish or run an image.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import time

SOURCE = Path('/home/brajam/.local/share/branconet-migration/next-security-01a1740e/a19-secret-capacity-01a1797a/final-image-session-exception-diagnostic/dependency-v182-audit/candidate-pod-summary-root.oci.tar')
PARENT = Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/release-v2-12dce115-inputs')
DEST = PARENT / SOURCE.name
TEMP = PARENT / (SOURCE.name + '.migrating')
BACKUP = SOURCE.with_name(SOURCE.name + '.migration-original-20261114')
RUN = Path('/mnt/h/AgentArtifacts/projects/branconet/runs/branconet-wsl-stage-20261113T215208Z')
RECEIPT = RUN / 'SWARM-qualified-oci-H-migration.json'
SHA = 'cf0d950a263b4ae63911f51560980fdce2211f7836852495bc2f189523e934dc'
SIZE = 497_920_000


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def metadata(path):
    s = path.stat()
    return dict(uid=s.st_uid, gid=s.st_gid, mode=stat.S_IMODE(s.st_mode),
                bytes=s.st_size, mtime_ns=s.st_mtime_ns,
                xattrs={name:os.getxattr(path,name).hex() for name in os.listxattr(path)})


def no_consumers(path):
    p = subprocess.run(['/usr/bin/fuser', str(path)], capture_output=True, text=True)
    if p.returncode != 1 or p.stdout.strip() or p.stderr.strip():
        raise RuntimeError('Source reference check did not clear; preserve both copies')
    device = path.stat().st_dev
    dev = str(os.major(device)) + ':' + str(os.minor(device))
    namespaces = set()
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            ns = os.readlink(proc / 'ns/mnt')
            if ns in namespaces:
                continue
            text = (proc / 'mountinfo').read_text()
            namespaces.add(ns)
        except (FileNotFoundError, ProcessLookupError):
            continue
        for line in text.splitlines():
            fields = line.split()
            if fields[2] == dev and fields[3] != '/' and path.is_relative_to(Path(fields[3])):
                raise RuntimeError('Source is exposed in an existing mount; retain it')
    return len(namespaces)


def main():
    if os.geteuid() != 0 or RECEIPT.exists() or any(p.exists() for p in (DEST,TEMP,BACKUP)):
        raise RuntimeError('Existing state requires reconciliation, not another copy')
    if SOURCE.is_symlink() or not SOURCE.is_file() or SOURCE.stat().st_nlink != 1:
        raise RuntimeError('Expected exact original regular file')
    release = json.loads((RUN/'BORTUS-EXPANDED-RELEASE-MAP-20261113.json').read_text(encoding='utf-8-sig'))
    if not any(SOURCE.is_relative_to(Path(p)) for p in release['releasedConditional'] if p.startswith('/')):
        raise RuntimeError('No recorded conditional migration release')
    refused = [Path(r['path']) for r in release['refusedExact'] if r['path'].startswith('/')]
    refused += [Path(p) for p in release['additionalProtectedExact'] if p.startswith('/')]
    if any(SOURCE == p or SOURCE.is_relative_to(p) for p in refused):
        raise RuntimeError('Exact refusal/protected runtime scope overrides migration')
    if not PARENT.is_dir() or command('/usr/bin/findmnt','-T',str(PARENT),'-n','-o','SOURCE,FSTYPE') != '/dev/loop0 ext4':
        raise RuntimeError('Existing H input store unavailable')
    if command('/usr/sbin/blkid','-s','UUID','-o','value','/dev/loop0') != 'e4c3cddc-ace6-4f27-a8b8-23278c17b53f':
        raise RuntimeError('H store identity changed')
    before = metadata(SOURCE)
    source_allocated = SOURCE.stat().st_blocks * 512
    if before['bytes'] != SIZE or digest(SOURCE) != SHA:
        raise RuntimeError('Qualified source identity changed')
    namespaces = no_consumers(SOURCE)
    record = dict(owner='BORTUS Delivery and Cluster Operations',state='copying',source=str(SOURCE),
        destination=str(DEST),sha256=SHA,bytes=SIZE,original_metadata=before,
        release_authority='BORTUS-EXPANDED-RELEASE-MAP-20261113.json: releasedConditional next-security prefix; exceptions preserved',
        purpose='Existing qualified input on H; no new image or build',new_mount=False,
        source_mount_namespaces_checked=namespaces,started_unix=time.time())
    def save():
        RECEIPT.write_text(json.dumps(record,indent=2)+'\n')
    save()
    subprocess.run(['/usr/bin/rsync','-aHAX','--',str(SOURCE),str(TEMP)],check=True,capture_output=True)
    if digest(TEMP) != SHA or metadata(TEMP) != before or metadata(SOURCE) != before:
        raise RuntimeError('Preservation equality failed; original and H copy retained')
    namespaces = no_consumers(SOURCE)
    TEMP.rename(DEST)
    SOURCE.rename(BACKUP)
    try:
        SOURCE.symlink_to(DEST)
        if SOURCE.resolve() != DEST or digest(SOURCE) != SHA or metadata(DEST) != before:
            raise RuntimeError('Original access path did not verify')
    except BaseException:
        if SOURCE.is_symlink():
            SOURCE.unlink()
        BACKUP.rename(SOURCE)
        record['state']='original-path-restored-H-copy-retained'
        save()
        raise
    # The sole original inode still exists until its fresh reference check clears.
    no_consumers(BACKUP)
    BACKUP.unlink()
    record.update(state='completed',original_path_compatible=True,original_physical_removed=True,
        source_namespace_count=namespaces,source_logical_bytes_removed=SIZE,
        linux_allocated_source_removed=source_allocated,
        windows_C_recovery_claim=False,completed_unix=time.time())
    save()
    print(json.dumps(record))


if __name__ == '__main__':
    main()
