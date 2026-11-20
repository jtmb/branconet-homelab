#!/usr/bin/env python3
"""Rehearse a protected Veyra preview backup into a disposable Kubernetes tmpfs."""

from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import sys
import tarfile
import uuid

NAMESPACE = "ingenium"
SSH = ("ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-p", "2002",
       "james@192.168.0.4")
AGE = Path.home() / ".local/share/branconet-migration/bin/age"
KEY = Path.home() / ".ssh/id_ed25519"
ARCHIVE_FLAGS = ("--format=pax", "--pax-option=delete=atime,delete=ctime,exthdr.name=%d/PaxHeaders/%f",
                 "--atime-preserve=system", "--sort=name", "--numeric-owner", "--one-file-system",
                 "--xattrs", "--acls")
PREVIEWS = {"veyra-preview", "veyra-composer-preview", "veyra-workspace-preview-r14"}


def command(*args):
    return (*SSH, shlex.join(("kubectl", "-n", NAMESPACE, *args)))


def call(*args, body=None, timeout=90):
    return subprocess.run(command(*args), input=body, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          timeout=timeout, check=True).stdout


def archive_manifest(stream):
    manifest = {}
    with tarfile.open(fileobj=stream, mode="r|*") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or path in manifest:
                raise ValueError("Unexpected archive path.")
            if member.issym():
                target = PurePosixPath(member.linkname)
                if target.is_absolute() or ".." in target.parts:
                    raise ValueError("Unexpected symbolic link target.")
            elif not (member.isfile() or member.isdir()):
                raise ValueError("Unexpected archive member type.")
            manifest[path] = {
                "type": member.type, "owner": (member.uid, member.gid), "mode": member.mode,
                "mtime": Decimal(member.pax_headers.get("mtime", member.mtime)),
                "link": member.linkname,
                "attributes": {k: v for k, v in member.pax_headers.items() if
                               k.startswith(("SCHILY.xattr.", "SCHILY.acl.", "LIBARCHIVE.xattr."))},
                "content": hashlib.file_digest(archive.extractfile(member), "sha256").hexdigest()
                if member.isfile() else None,
            }
    while stream.read(1024 * 1024):
        pass
    return manifest


def decrypted(archive):
    return (str(AGE), "-d", "-i", str(KEY), str(archive))


def read_manifest(process):
    manifest = archive_manifest(process.stdout)
    if process.wait(timeout=15):
        raise ValueError("Archive producer failed.")
    return manifest


def worker_command(uid, preview, operation):
    if str(uuid.UUID(uid)) != uid or preview not in PREVIEWS:
        raise ValueError("Unexpected restore target.")
    prepare = (
        'set -euo pipefail; test "$(hostname -s)" = workernode1; '
        'root="/var/lib/kubelet/pods/$1/volumes/kubernetes.io~empty-dir/state"; '
        'test -d "$root" && test "$(realpath "$root")" = "$root"; '
        'test "$(findmnt -n -o FSTYPE -T "$root")" = tmpfs; '
        'target="$root/$2"; '
    )
    if operation == "write":
        action = (
            'mkdir -- "$target"; '
            'exec tar --extract --file=- --directory="$target" --same-owner --same-permissions '
            '--numeric-owner --xattrs --xattrs-include="*" --acls --delay-directory-restore'
        )
    else:
        action = (
            'test -d "$target" && test "$(realpath "$target")" = "$target"; '
            'exec tar ' + shlex.join(ARCHIVE_FLAGS) + ' -C "$target" -cf - .'
        )
    remote = shlex.join(("sudo", "-S", "-p", "", "--", "bash", "-c", prepare + action, "restore", uid, preview))
    return (*SSH[:-1], "james@192.168.0.6", remote)


def restore(uid, directory, preview, artifact, password, volume_names=()):
    archive = directory / artifact["file"]
    if archive.resolve(strict=True).parent != directory:
        raise ValueError("Backup path escaped its checkpoint.")
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != artifact["ciphertext_sha256"]:
            raise ValueError("Ciphertext checksum mismatch.")
    with subprocess.Popen(decrypted(archive), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as source:
        expected = read_manifest(source)
    if volume_names and {path.parts[0] for path in expected if path.parts} != set(volume_names):
        raise ValueError("Archive volume names do not match the checkpoint receipt.")
    with subprocess.Popen(decrypted(archive), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as source, subprocess.Popen(
        worker_command(uid, preview, "write"), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ) as worker:
        try:
            worker.stdin.write(password)
            for block in iter(lambda: source.stdout.read(1024 * 1024), b""):
                worker.stdin.write(block)
            worker.stdin.close()
            if source.wait(timeout=15) or worker.wait(timeout=45):
                raise ValueError("Volume reseed failed.")
        finally:
            for process in (source, worker):
                if process.poll() is None:
                    process.kill()
                    process.wait()
    with subprocess.Popen(worker_command(uid, preview, "read"), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL) as source:
        source.stdin.write(password)
        source.stdin.close()
        actual = read_manifest(source)
    if volume_names:
        actual.pop(PurePosixPath("."))
    differences = Counter()
    for path in expected.keys() | actual.keys():
        if path not in expected or path not in actual:
            differences["membership"] += 1
        else:
            differences.update(key for key in expected[path] if expected[path][key] != actual[path][key])
    if differences:
        raise ValueError(f"{preview}: restore differences {dict(differences)}")
    print(f"{preview}: {len(actual)} entries match data, ownership, permissions, timestamps and attributes", flush=True)


def rehearsal(directory, password):
    checkpoint = json.loads((directory / "receipt.json").read_text())
    receipt = checkpoint["artifacts"]
    volume_names = checkpoint.get("empty_dir_volumes", {})
    if set(receipt) != PREVIEWS | {"pod_specs"}:
        raise ValueError("Unexpected checkpoint inventory.")
    name = "preview-reseed-" + uuid.uuid4().hex[:10]
    labels = {"migration-rehearsal": name}
    metadata = {"name": name, "labels": labels}
    policy = {"apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy", "metadata": metadata,
              "spec": {"podSelector": {"matchLabels": labels}, "policyTypes": ["Ingress", "Egress"]}}
    pod = {"apiVersion": "v1", "kind": "Pod", "metadata": metadata,
           "spec": {"nodeName": "workernode1", "restartPolicy": "Never", "activeDeadlineSeconds": 420,
                    "automountServiceAccountToken": False, "securityContext": {"seccompProfile": {"type": "RuntimeDefault"}},
                    "containers": [{"name": "restore", "image": "python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1",
                                    "command": ["python3", "-B", "-c", "import time; time.sleep(420)"],
                                    "resources": {"requests": {"cpu": "25m", "memory": "192Mi"},
                                                  "limits": {"cpu": "500m", "memory": "360Mi"}},
                                    "securityContext": {"runAsUser": 65534, "runAsGroup": 65534, "runAsNonRoot": True, "allowPrivilegeEscalation": False,
                                                        "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}},
                                    "volumeMounts": [{"name": "state", "mountPath": "/restore", "readOnly": True}]}],
                    "volumes": [{"name": "state", "emptyDir": {"medium": "Memory", "sizeLimit": "256Mi"}}]}}
    gate = dict(pod["spec"]["containers"][0])
    gate["name"] = "await-restored-state"
    gate["command"] = ["python3", "-B", "-c", "from pathlib import Path\nimport time\np = Path('/handoff/verified')\nwhile not p.is_file():\n    time.sleep(0.2)\n"]
    gate["volumeMounts"] = [*gate["volumeMounts"],
                            {"name": "handoff", "mountPath": "/handoff", "readOnly": True}]
    pod["spec"]["initContainers"] = [gate]
    pod["spec"]["volumes"].append(
        {"name": "handoff", "emptyDir": {"medium": "Memory", "sizeLimit": "1Mi"}}
    )
    created = []
    print(f"Isolated restore rehearsal: {name}", flush=True)
    try:
        for path, obj in ((f"/apis/networking.k8s.io/v1/namespaces/{NAMESPACE}/networkpolicies/{name}", policy),
                          (f"/api/v1/namespaces/{NAMESPACE}/pods/{name}", pod)):
            response = json.loads(call("create", "-f", "-", "-o", "json", body=json.dumps(obj).encode()))
            created.append((path, response["metadata"]["uid"]))
        init = "await-restored-state"
        call("wait", "--for=jsonpath={.status.initContainerStatuses[0].state.running.startedAt}",
             "pod/" + name, "--timeout=75s", timeout=80)
        if call("exec", name, "-c", init, "--", "stat", "-fc", "%T", "/restore").strip() != b"tmpfs":
            raise ValueError("Restore volume is not memory-backed.")
        check = ('import os,socket,sys; s=socket.socket(); s.settimeout(2); '
                 'sys.exit(0 if s.connect_ex((os.environ["KUBERNETES_SERVICE_HOST"],443)) else 1)')
        call("exec", name, "-c", init, "--", "python3", "-B", "-c", check, timeout=10)
        pod_uid = created[-1][1]
        for preview in sorted(PREVIEWS):
            restore(pod_uid, directory, preview, receipt[preview], password, volume_names.get(preview, ()))
        status = json.loads(call("get", "pod", name, "-o", "json"))["status"]
        if any(item.get("state", {}).get("running") for item in status.get("containerStatuses", [])):
            raise ValueError("Main container started before state verification.")
        gate_command = (
            'set -eu; test "$(hostname -s)" = workernode1; '
            'p="/var/lib/kubelet/pods/$1/volumes/kubernetes.io~empty-dir/handoff"; '
            'test -d "$p" && test "$(realpath "$p")" = "$p"; '
            'test "$(findmnt -n -o FSTYPE -T "$p")" = tmpfs; '
            'set -C; (umask 022; : > "$p/verified")'
        )
        remote = shlex.join(("sudo", "-S", "-p", "", "--", "bash", "-c", gate_command, "release", pod_uid))
        subprocess.run((*SSH[:-1], "james@192.168.0.6", remote), input=password,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=15)
        call("wait", "--for=condition=Ready", "pod/" + name, "--timeout=45s", timeout=50)
        print("Main container became Ready only after the verified-state gate was released.", flush=True)
    finally:
        for path, uid in reversed(created):
            options = {"apiVersion": "v1", "kind": "DeleteOptions", "preconditions": {"uid": uid}}
            call("delete", "--raw", path, "-f", "-", body=json.dumps(options).encode(), timeout=25)
            if "/pods/" in path:
                call("wait", "--for=delete", "pod/" + name, "--timeout=45s", timeout=50)
        print("Exact temporary restore resources removed.", flush=True)


if __name__ == "__main__":
    try:
        checkpoint = Path(sys.argv[1]).resolve(strict=True)
        expected_parent = Path("/mnt/f/branconet-migration-artifacts/maintenance-storage-20261025")
        if checkpoint.parent != expected_parent or not checkpoint.name.startswith("veyra-preview-checkpoint-"):
            raise ValueError("Unexpected checkpoint location.")
        password = sys.stdin.buffer.readline(1024).rstrip(b"\r\n") + b"\n"
        if len(password) < 2:
            raise ValueError("Missing existing worker privilege credential.")
        rehearsal(checkpoint, password)
    except ValueError as error:
        sys.exit(str(error))
    except (KeyError, OSError, subprocess.SubprocessError, tarfile.TarError):
        sys.exit("Restore rehearsal stopped before qualification.")
