#!/usr/bin/env python3
"""Preserve exact closed node01 journals before bounded test-volume admission.

Reuse original archived-journal ownership/stability/no-open-FD checks and
authenticated encrypted recovery. No rotation, workload stop or threshold change.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import shlex
import subprocess
import tarfile
from decimal import Decimal

SCRIPTS = Path(__file__).resolve().parent
STAGE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/certificates-qualification-20261116")
WORK = STAGE / "ntfy-node01-journal-preservation"


def main():
    assert not WORK.exists(), "reconcile_existing_preservation"
    spec = importlib.util.spec_from_file_location("original_journal_preserver",
                                                SCRIPTS / "preserve-node03-archived-journals.py")
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    old.SSH = [*old.SSH[:-1], "james@192.168.0.4"]
    password = old.saved_password()
    rows = old.query(password, "inspect")["files"]
    assert 0 < len(rows) <= 6 and sum(r["bytes"] for r in rows) <= 600_000_000
    publisher = Path(json.loads((STAGE / "credential-bootstrap-publisher-result.json").read_text())["stage"])
    used = sum(int(subprocess.check_output(["du", "-sx", "-B1", str(p)]).split()[0])
               for p in (STAGE, publisher))
    assert used + 1_000_000_000 + 650_000_000 < 4_250_000_000
    os.umask(0o077)
    WORK.mkdir(mode=0o700)

    def save(name, data):
        with (WORK / name).open("x") as out:
            json.dump(data, out, indent=2)
            out.write("\n")

    save("started.json", {"host": "node01", "files": rows, "retainedBaselineBytes": used,
                         "archiveMaximumBytes": 650_000_000, "sourceRetired": False,
                         "reason": "Preserve history and recover Longhorn's unchanged 25% free-space floor for new test claim"})
    source = encryptor = decryptor = None
    try:
        command = ["sudo", "-S", "-k", "-p", "", "nice", "-n", "10", "tar",
                   "--format=pax", "--gzip", "--acls", "--xattrs", "--xattrs-include=*",
                   "--numeric-owner", "--atime-preserve=system", "-C", "/var/log/journal",
                   "-cf", "-", "--"] + [r["relative"] for r in rows]
        source = subprocess.Popen(old.SSH + [shlex.join(command)], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        source.stdin.write((password + "\n").encode())
        source.stdin.close()
        partial = WORK / "closed-journals.tar.gz.age.partial"

        def output_limit():
            resource.setrlimit(resource.RLIMIT_FSIZE, (650_000_000, 650_000_000))

        encryptor = subprocess.Popen([str(old.RUNTIME / "bin/age"), "-R",
            "/home/brajam/.ssh/id_ed25519.pub", "-o", str(partial)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            preexec_fn=output_limit)
        incoming = old.HashedPipe(source.stdout)
        while block := incoming.read(1024 * 1024):
            encryptor.stdin.write(block)
        encryptor.stdin.close()
        assert source.wait(timeout=30) == encryptor.wait(timeout=30) == 0
        with partial.open("rb") as stream:
            os.fsync(stream.fileno())
        decryptor = subprocess.Popen([str(old.RUNTIME / "bin/age"), "-d", "-i",
            "/home/brajam/.ssh/id_ed25519", str(partial)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        recovered = old.HashedPipe(decryptor.stdout)
        expected, seen = {r["relative"]: r for r in rows}, set()
        with tarfile.open(fileobj=recovered, mode="r|gz") as archive:
            for member in archive:
                assert member.name in expected and member.name not in seen and member.isfile()
                row = expected[member.name]
                assert (member.size, member.uid, member.gid, member.mode) == (
                    row["bytes"], row["uid"], row["gid"], row["mode"])
                assert int(Decimal(member.pax_headers.get("mtime", str(member.mtime))) * 10**9) == row["mtime_ns"]
                digest = hashlib.sha256()
                with archive.extractfile(member) as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                assert digest.hexdigest() == row["sha256"]
                # Preserve every recorded ACL/xattr entry, including binary
                # values in the encrypted PAX stream, without printing values.
                pax_names = {n.removeprefix("SCHILY.xattr.") for n in member.pax_headers
                             if n.startswith("SCHILY.xattr.")}
                assert set(row["xattr_names"]) <= pax_names | {"system.posix_acl_access", "system.posix_acl_default"}
                seen.add(member.name)
        while recovered.read(1024 * 1024):
            pass
        assert decryptor.wait(timeout=30) == 0 and seen == set(expected)
        assert incoming.hashed.digest() == recovered.hashed.digest()
        final = WORK / "closed-journals.tar.gz.age"
        partial.rename(final)
        with final.open("rb") as stream:
            encrypted_sha = hashlib.file_digest(stream, "sha256").hexdigest()
        save("preserved.json", {"allOriginalFileHashesEqual": True, "authenticatedTarStreamEqual": True,
                               "metadataPreserved": True, "ciphertextSHA256": encrypted_sha,
                               "ciphertextBytes": final.stat().st_size, "plaintextPersisted": False,
                               "restore": "age -d with retained operator SSH identity, then tar preserving numeric ownership/ACL/xattrs",
                               "retentionConsumer": "Unique original node01 historical system journals; encrypted recovery copy"})
        old.query(password, "inspect", rows)
        save("retirement-intent.json", {"exactFiles": [r["relative"] for r in rows],
                                       "preservedAndRechecked": True, "noOpenFDs": True})
        retired = old.query(password, "retire", rows)
        assert set(retired["removed"]) == set(expected)
        save("result.json", {"passed": True, "host": "node01", "sourceRetired": True,
                            "filesPreserved": len(rows), "ciphertextBytes": final.stat().st_size,
                            "ciphertextSHA256": encrypted_sha, "plaintextPersisted": False,
                            "allocatedBytesRemoved": retired["allocated_bytes_removed"],
                            "thresholdOrActiveJournalOrWorkloadChanged": False})
        print((WORK / "result.json").read_text())
    finally:
        password = None
        for process in (source, encryptor, decryptor):
            old.stop(process)


if __name__ == "__main__":
    main()
