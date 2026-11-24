#!/usr/bin/env python3
"""Recreate the three preview Pods under the same images after the Worker 1 rename."""

import hashlib
import json
from pathlib import Path
import runpy
import shlex
import shutil
import subprocess
import sys
import uuid

tools = runpy.run_path(str(Path(__file__).with_name("rehearse-veyra-preview-reseed.py")))
call, decrypt, read_manifest = (tools[key] for key in ("call", "decrypted", "read_manifest"))
PREVIEWS, SSH, FLAGS = (tools[key] for key in ("PREVIEWS", "SSH", "ARCHIVE_FLAGS"))
ROOT = Path("/mnt/f/branconet-migration-artifacts/maintenance-storage-20261025")
GATE = "await-restored-state"
MARKER = "branconet.lan/preview-restore"
PYTHON = "python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1"


def manifests(directory):
    receipt = json.loads((directory / "receipt.json").read_text())
    archive = directory / receipt["artifacts"]["pod_specs"]["file"]
    raw = subprocess.check_output(decrypt(archive), timeout=20)
    objects = json.loads(raw)["items"]
    if {p["metadata"]["name"] for p in objects} != PREVIEWS or set(receipt["empty_dir_volumes"]) != PREVIEWS:
        raise ValueError("Unexpected checkpoint preview inventory.")
    result = []
    for pod in objects:
        metadata, spec = pod["metadata"], pod["spec"]
        name = metadata["name"]
        if (metadata["uid"] != receipt["pod_uids"][name] or metadata.get("ownerReferences")
                or spec.pop("nodeName") != "workernode1"
                or spec["nodeSelector"] not in ({"kubernetes.io/hostname": "workernode1"},
                                               {"branconet.lan/node-id": "node02"})
                or any("terminated" not in s["state"] for s in pod["status"].get("ephemeralContainerStatuses", []))):
            raise ValueError("The preview identity or ephemeral container state changed.")
        spec["nodeSelector"] = {"branconet.lan/node-id": "node02"}
        for key in ("ephemeralContainers", "priority", "serviceAccount"):
            spec.pop(key, None)
        spec["volumes"] = [v for v in spec["volumes"] if v["name"] != "migration-handoff"]
        if {v["name"] for v in spec["volumes"] if "emptyDir" in v} != set(receipt["empty_dir_volumes"][name]):
            raise ValueError("Checkpoint and preview volumes differ.")
        spec["volumes"].append({"name": "migration-handoff", "emptyDir": {"medium": "Memory", "sizeLimit": "1Mi"}})
        spec["initContainers"] = [{
            "name": GATE, "image": PYTHON, "imagePullPolicy": "Never",
            "command": ["python3", "-B", "-c",
                        "from pathlib import Path\nimport time\nwhile not Path('/handoff/verified').exists(): time.sleep(.2)"],
            "resources": {"requests": {"cpu": "10m", "memory": "24Mi"}, "limits": {"cpu": "100m", "memory": "48Mi"}},
            "securityContext": {"runAsUser": 65534, "runAsGroup": 65534, "runAsNonRoot": True,
                                "allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                                "capabilities": {"drop": ["ALL"]}},
            "volumeMounts": [{"name": "migration-handoff", "mountPath": "/handoff", "readOnly": True}]
            + [{"name": volume, "mountPath": "/restore/" + volume, "readOnly": True}
               for volume in receipt["empty_dir_volumes"][name]],
        }]
        result.append({"apiVersion": "v1", "kind": "Pod", "metadata": {
            "namespace": "ingenium", "name": name, "labels": metadata["labels"],
            "annotations": {MARKER: directory.name}}, "spec": spec})
    return receipt, result


def host(uid, names, action, node):
    if str(uuid.UUID(uid)) != uid:
        raise ValueError("Invalid replacement Pod UID.")
    validate = r'''set -euo pipefail
test "$(hostname -s)" = "$2"
root="/var/lib/kubelet/pods/$1/volumes/kubernetes.io~empty-dir"
shift 2
test -d "$root" && test "$(realpath "$root")" = "$root"
for name in "$@"; do
    [[ "$name" =~ ^[a-z][a-z0-9-]*$ ]]
    path="$root/$name"
    test "$(realpath "$path")" = "$path"
    test "$(findmnt -n -o FSTYPE -T "$path")" = tmpfs
done
'''
    commands = {
        "write": 'exec tar -x -f - -C "$root" --same-owner --same-permissions --numeric-owner --xattrs --xattrs-include="*" --acls --delay-directory-restore',
        "read": 'exec tar ' + shlex.join(FLAGS) + ' -C "$root" -cf - -- "$@"',
        "release": 'set -C; (umask 022; : > "$root/migration-handoff/verified")',
    }
    remote = shlex.join(("sudo", "-S", "-p", "", "--", "bash", "-c", validate + commands[action],
                         "reseed", uid, node, *names))
    return (*SSH[:-1], "james@192.168.0.6", remote)


def restore(directory, pod, receipt, password, node):
    name = pod["metadata"]["name"]
    encoded = json.dumps(pod).encode()
    current = call("get", "pod", name, "--ignore-not-found", "-o", "json")
    current = json.loads(current or call("create", "-f", "-", "-o", "json", body=encoded))
    if current["metadata"]["annotations"].get(MARKER) != directory.name or current["metadata"].get("deletionTimestamp"):
        raise ValueError("The existing Pod is not this migration's replacement.")
    intended_mounts = {m["name"] for m in pod["spec"]["initContainers"][0]["volumeMounts"]}
    actual_mounts = {m["name"] for m in current["spec"]["initContainers"][0]["volumeMounts"]}
    if actual_mounts != intended_mounts:
        if any("waiting" not in c["state"] for c in current["status"].get("containerStatuses", [])):
            raise ValueError("The old restore gate has an active workload.")
        evict_pod(name, current["metadata"]["uid"])
        call("wait", "--for=delete", "pod/" + name, "--timeout=60s", timeout=65)
        current = json.loads(call("create", "-f", "-", "-o", "json", body=encoded))
    statuses = current.get("status", {}).get("initContainerStatuses", [])
    if not any(s["name"] == GATE and s["state"].get("terminated", {}).get("exitCode") == 0 for s in statuses):
        call("wait", "--for=jsonpath={.status.initContainerStatuses[0].state.running.startedAt}",
             "pod/" + name, "--timeout=90s", timeout=100)
        current = json.loads(call("get", "pod", name, "-o", "json"))
        if current["spec"]["nodeName"] != node or current["spec"]["initContainers"][0]["image"] != PYTHON:
            raise ValueError("The replacement did not reach the expected node and restore gate.")
        uid = current["metadata"]["uid"]
        names = receipt["empty_dir_volumes"][name]
        meta = receipt["artifacts"][name]
        archive = directory / meta["file"]
        if archive.resolve(strict=True).parent != directory:
            raise ValueError("Unexpected checkpoint artifact path.")
        with archive.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != meta["ciphertext_sha256"]:
                raise ValueError("Ciphertext checksum mismatch.")
        with subprocess.Popen(decrypt(archive), stdout=subprocess.PIPE) as source:
            expected = read_manifest(source)
        if {p.parts[0] for p in expected} != set(names):
            raise ValueError("The archive contains an unexpected volume.")
        with subprocess.Popen(decrypt(archive), stdout=subprocess.PIPE) as source:
            with subprocess.Popen(host(uid, names, "write", node), stdin=subprocess.PIPE) as worker:
                worker.stdin.write(password)
                shutil.copyfileobj(source.stdout, worker.stdin, length=1024 * 1024)
                worker.stdin.close()
                if source.wait(timeout=20) or worker.wait(timeout=60):
                    raise ValueError("Preview volume restore failed.")
        with subprocess.Popen(host(uid, names, "read", node), stdin=subprocess.PIPE, stdout=subprocess.PIPE) as source:
            source.stdin.write(password)
            source.stdin.close()
            if read_manifest(source) != expected:
                raise ValueError("Preview restore readback differs from its checkpoint.")
        subprocess.run(host(uid, ["migration-handoff"], "release", node), input=password, check=True, timeout=20)
    call("wait", "--for=condition=Ready", "pod/" + name, "--timeout=110s", timeout=115)
    print(f"{name}: restored and Ready on {node}", flush=True)


def evict_pod(name, uid):
    request = {"apiVersion": "policy/v1", "kind": "Eviction", "metadata": {"name": name},
               "deleteOptions": {"preconditions": {"uid": uid}}}
    call("create", "--raw", f"/api/v1/namespaces/ingenium/pods/{name}/eviction",
         "-f", "-", body=json.dumps(request).encode())


def evict(receipt, directory):
    node = json.loads(call("get", "node", "workernode1", "-o", "json"))
    if not node["spec"].get("unschedulable"):
        raise ValueError("Cordon Worker 1 before evicting the protected previews.")
    current = json.loads(call("get", "pods", *sorted(PREVIEWS), "-o", "json"))["items"]
    if {p["metadata"]["name"]: p["metadata"]["uid"] for p in current} != receipt["pod_uids"]:
        raise ValueError("Preview identities changed after the checkpoint.")
    for meta in receipt["artifacts"].values():
        archive = directory / meta["file"]
        if archive.resolve(strict=True).parent != directory:
            raise ValueError("Checkpoint artifact escaped its directory.")
        with archive.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != meta["ciphertext_sha256"]:
                raise ValueError("Checkpoint readback failed.")
    for name, uid in receipt["pod_uids"].items():
        evict_pod(name, uid)
        print(f"{name}: normal eviction accepted", flush=True)
    call("wait", "--for=delete", *("pod/" + name for name in sorted(PREVIEWS)),
         "--timeout=110s", timeout=115)


def main():
    mode, given = sys.argv[1:]
    directory = Path(given).resolve(strict=True)
    if directory.parent != ROOT or not directory.name.startswith("veyra-preview-checkpoint-"):
        raise ValueError("Unexpected checkpoint path.")
    receipt, pods = manifests(directory)
    if mode == "--check":
        for pod in pods:
            pod["metadata"]["name"] += "-migration-check"
            call("create", "--dry-run=server", "-f", "-", body=json.dumps(pod).encode())
            print(pod["metadata"]["name"] + ": strict admission passed")
    elif mode == "--evict":
        evict(receipt, directory)
    elif mode in ("--restore", "--rollback"):
        node = "node02" if mode == "--restore" else "workernode1"
        password = sys.stdin.buffer.readline(1024).rstrip(b"\r\n") + b"\n"
        if len(password) < 2:
            raise ValueError("Missing existing worker privilege credential.")
        for pod in pods:
            restore(directory, pod, receipt, password, node)
    else:
        raise ValueError("Use --check, --evict or --restore.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        sys.exit(f"Preview migration stopped: {type(error).__name__}")
