#!/usr/bin/env python3
"""Capture the three migration-blocking Veyra preview emptyDirs without evicting them."""

import datetime
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import uuid

HOME = Path.home()
AGE = HOME / ".local/share/branconet-migration/bin/age"
AGE_SHA = "eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c"
KEY = HOME / ".ssh/id_ed25519"
OUTPUT = Path("/mnt/f/branconet-migration-artifacts/maintenance-storage-20261025")
PODS = ("veyra-preview", "veyra-composer-preview", "veyra-workspace-preview-r14")
SSH = ("ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
       "-o", "ConnectTimeout=8", "-p", "2002")
ARCHIVE = r"""
set -euo pipefail
test "$(hostname -s)" = workernode1
path="/var/lib/kubelet/pods/$1/volumes/kubernetes.io~empty-dir/state"
test -d "$path" && test "$(realpath "$path")" = "$path"
test "$(findmnt -rn -o TARGET | awk -v p="$path/" 'index($0,p)==1 {n++} END {print n+0}')" = 0
exec timeout 45 tar --format=pax --pax-option=delete=atime,delete=ctime,exthdr.name=%d/PaxHeaders/%f   --atime-preserve=system --sort=name --numeric-owner --one-file-system --xattrs --acls -C "$path" -cf - .
"""

ARCHIVE_ALL = r"""
set -euo pipefail
test "$(hostname -s)" = workernode1
path="/var/lib/kubelet/pods/$1/volumes/kubernetes.io~empty-dir"
shift
test -d "$path" && test "$(realpath "$path")" = "$path"
for name in "$@"; do
    [[ "$name" =~ ^[a-z][a-z0-9-]*$ ]]
    dir="$path/$name"
    test "$(realpath "$dir")" = "$dir"
    test "$(findmnt -n -o FSTYPE -T "$dir")" = tmpfs
    test "$(findmnt -rn -o TARGET | awk -v p="$dir/" 'index($0,p)==1 {n++} END {print n+0}')" = 0
done
exec timeout 70 tar --format=pax --pax-option=delete=atime,delete=ctime,exthdr.name=%d/PaxHeaders/%f     --atime-preserve=system --sort=name --numeric-owner --one-file-system --xattrs --acls -C "$path" -cf - -- "$@"
"""


def volume_names(specs):
    return {p["metadata"]["name"]: sorted(v["name"] for v in p["spec"]["volumes"]
            if "emptyDir" in v and v["name"] != "migration-handoff") for p in json.loads(specs)["items"]}


def digest_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inventory():
    command = shlex.join(("kubectl", "-n", "ingenium", "get", "pods", *PODS, "-o", "json"))
    raw = subprocess.check_output((*SSH, "james@192.168.0.4", command), timeout=15)
    objects = json.loads(raw)["items"]
    identities = {}
    for pod in objects:
        meta, spec = pod["metadata"], pod["spec"]
        name, uid = meta["name"], meta["uid"]
        if (name not in PODS or name in identities or str(uuid.UUID(uid)) != uid
                or meta.get("deletionTimestamp") or meta.get("ownerReferences")
                or spec["nodeName"] != "workernode1" or pod["status"]["phase"] != "Running"
                or not any(v["name"] == "state" and v.get("emptyDir") == {"medium": "Memory", "sizeLimit": "512Mi"} for v in spec["volumes"])):
            raise ValueError("Unexpected preview identity.")
        identities[name] = uid
    if set(identities) != set(PODS):
        raise ValueError("The preview inventory is incomplete.")
    return raw, identities


def archive_command(uid, names=()):
    script = ARCHIVE_ALL if names else ARCHIVE
    remote = shlex.join(("sudo", "-S", "-p", "", "--", "bash", "-c", script, "archive", uid, *names))
    return (*SSH, "james@192.168.0.6", remote)


def capture(uid, password, sink=None, names=()):
    digest = hashlib.sha256()
    size = 0
    with subprocess.Popen(archive_command(uid, names), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL) as reader:
        try:
            reader.stdin.write(password)
            reader.stdin.close()
            for block in iter(lambda: reader.stdout.read(1024 * 1024), b""):
                size += len(block)
                if size > 512 * 1024 * 1024:
                    raise ValueError("Preview exceeds the capture limit.")
                digest.update(block)
                if sink is not None:
                    sink.write(block)
            if reader.wait(timeout=5) != 0 or size == 0:
                raise ValueError("Worker archive read failed.")
        finally:
            if reader.poll() is None:
                reader.kill()
                reader.wait()
    return size, digest.hexdigest()


def save(path, producer):
    partial = path.with_suffix(".partial")
    target = partial.open("xb")
    try:
        with target, subprocess.Popen(
            (str(AGE), "-R", str(KEY.with_suffix(".pub"))), stdin=subprocess.PIPE, stdout=target,
            stderr=subprocess.DEVNULL
        ) as encrypt:
            try:
                expected = producer(encrypt.stdin)
                encrypt.stdin.close()
                if encrypt.wait(timeout=15) != 0:
                    raise ValueError("Archive encryption failed.")
            finally:
                if encrypt.poll() is None:
                    encrypt.kill()
                    encrypt.wait()
        with subprocess.Popen((str(AGE), "-d", "-i", str(KEY), str(partial)),
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as decrypt:
            digest = hashlib.sha256()
            size = 0
            for block in iter(lambda: decrypt.stdout.read(1024 * 1024), b""):
                size += len(block)
                digest.update(block)
            if decrypt.wait(timeout=15) != 0 or (size, digest.hexdigest()) != expected:
                raise ValueError("Authenticated backup verification failed.")
        if path.exists():
            raise ValueError("The encrypted backup destination already exists.")
        partial.rename(path)
        return {"file": path.name, "plaintext_bytes": size, "ciphertext_bytes": path.stat().st_size,
                "ciphertext_sha256": digest_file(path)}
    finally:
        partial.unlink(missing_ok=True)


def main():
    if sys.argv[1:] not in ([], ["--all-volumes"]):
        raise ValueError("Unknown preview capture mode.")
    all_volumes = sys.argv[1:] == ["--all-volumes"]
    if OUTPUT.resolve(strict=True) != OUTPUT or shutil.disk_usage(OUTPUT).free < 16 * 1024 ** 3:
        raise ValueError("The approved backup volume lacks headroom or is redirected.")
    if digest_file(AGE) != AGE_SHA or KEY.stat().st_mode & 0o077:
        raise ValueError("Encryption tool or identity validation failed.")
    password = sys.stdin.buffer.readline(1024).rstrip(b"\r\n")
    if not password:
        raise ValueError("Missing existing node credential.")
    password += b"\n"
    specs, identities = inventory()
    names_by_pod = volume_names(specs) if all_volumes else {}
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = OUTPUT / f"veyra-preview-checkpoint-{stamp}"
    directory.mkdir(exist_ok=False)
    receipt = {}
    for name in PODS:
        uid = identities[name]
        names = names_by_pod.get(name, ())
        before = capture(uid, password, names=names)

        def checked_copy(sink):
            copied = capture(uid, password, sink, names)
            if copied != before or capture(uid, password, names=names) != copied:
                raise ValueError("The preview changed during capture.")
            return copied

        receipt[name] = save(directory / f"{name}.tar.age", checked_copy)
        print(f"Verified stable encrypted capture: {name}", flush=True)
    current_specs, current_identities = inventory()
    if current_identities != identities or (all_volumes and volume_names(current_specs) != names_by_pod):
        raise ValueError("Preview identity changed during capture.")

    def copy_specs(sink):
        sink.write(specs)
        return len(specs), hashlib.sha256(specs).hexdigest()

    receipt["pod_specs"] = save(directory / "pod-specs.json.age", copy_specs)
    with (directory / "receipt.json").open("x") as stream:
        data = {"captured_at_utc": stamp, "pod_uids": identities, "artifacts": receipt}
        if all_volumes:
            data["empty_dir_volumes"] = names_by_pod
        json.dump(data, stream, indent=2)
        stream.write("\n")
    print(f"Completed preview checkpoint: {directory}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
        print(f"Preview capture stopped: {type(exc).__name__}. Preserve any completed encrypted artifacts.", file=sys.stderr)
        sys.exit(1)
