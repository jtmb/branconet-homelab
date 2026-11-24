#!/usr/bin/env python3
"""Add the already-running Worker 1 kubelet to the control plane in place."""

import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
import time

base = runpy.run_path(str(Path(__file__).with_name("promote-worker2-control-plane.py")))
root, kube = base["root"], base["kube"]
members, local_health, metadata = base["members"], base["local_health"], base["metadata"]
remove_secret, wait_for, ready = base["remove_secret"], base["wait_for"], base["ready"]
MASTER, ETCD = base["MASTER"], base["ETCD"]
WORKER = "192.168.0.6"
NODE = "workernode1"
BACKUP = "/etc/kubernetes/.branconet-worker1-promotion"
PREVIEWS = ("veyra-preview", "veyra-composer-preview", "veyra-workspace-preview-r14")
PRECHECK = r"""
set -euo pipefail
test "$(hostname -s)" = workernode1
test -s /etc/kubernetes/kubelet.conf
test -s /etc/kubernetes/encryption-config.json
test ! -e /etc/kubernetes/admin.conf
test ! -e /var/lib/etcd
test -z "$(find /etc/kubernetes/manifests -mindepth 1 -maxdepth 1 -print -quit)"
grep -qx 'staticPodPath: /etc/kubernetes/manifests' /var/lib/kubelet/config.yaml
systemctl is-active --quiet kubelet
test "$(ss -Hln '( sport = :6443 or sport = :2379 or sport = :2380 or sport = :10257 or sport = :10259 )')" = ''
umask 077
mkdir "$1"
cp -a -- /etc/kubernetes/pki "$1/pki"
sha256sum /etc/kubernetes/kubelet.conf /var/lib/kubelet/config.yaml > "$1/kubelet.sha256"
"""


def node():
    return json.loads(kube("get", "node", NODE, "-o", "json"))


def previews():
    objects = json.loads(kube("-n", "ingenium", "get", "pods", *PREVIEWS, "-o", "json"))["items"]
    identities = {}
    for pod in objects:
        if pod["spec"]["nodeName"] != NODE or pod["metadata"].get("deletionTimestamp"):
            raise RuntimeError("Unexpected preview placement.")
        status = pod["status"].get("containerStatuses", [])
        if not status or not all(item["ready"] for item in status):
            raise RuntimeError("A preview is outside its ready baseline.")
        identities[pod["metadata"]["name"]] = (
            pod["metadata"]["uid"], sorted((item["name"], item["containerID"], item["restartCount"]) for item in status)
        )
    if set(identities) != set(PREVIEWS):
        raise RuntimeError("Incomplete preview inventory.")
    return identities


def storage_ready():
    volumes = json.loads(kube("-n", "longhorn-system", "get", "volumes", "-o", "json"))["items"]
    return all(v["status"].get("robustness") != "faulted" and
               (v["status"].get("state") != "attached" or v["status"].get("robustness") == "healthy") for v in volumes)


def undo(password, original_ids):
    local_health(password)
    current = members(password)
    if not original_ids.issubset({item["ID"] for item in current}):
        raise RuntimeError("Unexpected etcd membership, preserving all running members.")
    candidate = [m for m in current if m["ID"] not in original_ids]
    if candidate:
        if len(candidate) != 1 or candidate[0]["peerURLs"] != [f"https://{WORKER}:2380"]:
            raise RuntimeError("Unexpected additional member, preserving all running members.")
        root(MASTER, password, "bash", "-c", ETCD, "etcd", "member", "remove", f'{candidate[0]["ID"]:x}')
        local_health(password)
    script = r"""
set -euo pipefail
test "$(hostname -s)" = workernode1
test -d "$1" && test "$(realpath "$1")" = "$1"
mkdir "$1/failed-join"
for name in kube-apiserver kube-controller-manager kube-scheduler etcd; do
    file="/etc/kubernetes/manifests/$name.yaml"
    if [ -e "$file" ]; then mv -- "$file" "$1/failed-join/"; fi
done
# Leave freshly generated PKI and data protected until static pods stop and can be inspected.
sha256sum -c "$1/kubelet.sha256" >/dev/null
"""
    root(WORKER, password, "bash", "-c", script, "rollback", BACKUP)
    kube("label", "node", NODE, "node-role.kubernetes.io/control-plane-",
         "node.kubernetes.io/exclude-from-external-load-balancers-")


def main(password):
    initial = members(password)
    if {m["name"] for m in initial if not m.get("isLearner")} != {"masternode", "workernode2"} or len(initial) != 2:
        raise RuntimeError("Expected exactly two existing etcd voters.")
    local_health(password)
    current = node()
    if (ready(current) != "True" or current["spec"].get("unschedulable") or current["spec"].get("taints") or
            "node-role.kubernetes.io/control-plane" in current["metadata"]["labels"] or metadata("kubeadm-certs")):
        raise RuntimeError("Worker 1 is outside the required starting state.")
    node_uid = current["metadata"]["uid"]
    original_previews = previews()
    disks = ("-n", "longhorn-system", "get", "nodes.longhorn.io", NODE, "-o", "json")
    storage_before = json.loads(kube(*disks))
    print("Waiting for Worker 2 replica recovery before the in-place join", flush=True)
    wait_for(storage_ready, "attached Longhorn volumes to return Healthy", 360)
    root(WORKER, password, "bash", "-c", PRECHECK, "prepare", BACKUP)
    token_id = None
    upload = None
    join_started = False
    try:
        pin = root(MASTER, password, "bash", "-o", "pipefail", "-c",
                   "openssl x509 -in /etc/kubernetes/pki/ca.crt -pubkey -noout | openssl pkey -pubin -outform DER | sha256sum").decode().split()[0]
        if not re.fullmatch(r"[0-9a-f]{64}", pin):
            raise RuntimeError("Invalid CA pin.")
        token = root(MASTER, password, "kubeadm", "token", "create", "--ttl=12m",
                     "--description=worker1-control-plane-join").decode().strip()
        if not re.fullmatch(r"[a-z0-9]{6}[.][a-z0-9]{16}", token):
            raise RuntimeError("Unexpected bootstrap credential format.")
        token_id = token.split(".")[0]
        key_output = root(MASTER, password, "kubeadm", "init", "phase", "upload-certs", "--upload-certs").decode()
        upload = metadata("kubeadm-certs")
        keys = re.findall(r"^[0-9a-f]{64}$", key_output, re.M)
        if len(keys) != 1 or len(upload) != 2 or not re.fullmatch(r"bootstrap-token-[a-z0-9]{6}", upload[1]):
            raise RuntimeError("Could not bind the certificate upload.")
        config = {"apiVersion": "kubeadm.k8s.io/v1beta4", "kind": "JoinConfiguration",
                  "skipPhases": ["kubelet-start", "kubelet-wait-bootstrap"],
                  "controlPlane": {"localAPIEndpoint": {"advertiseAddress": WORKER, "bindPort": 6443},
                                   "certificateKey": keys[0]},
                  "nodeRegistration": {"name": NODE, "criSocket": "unix:///run/containerd-k8s/containerd.sock",
                                       "taints": [], "ignorePreflightErrors":
                                       ["FileAvailable--etc-kubernetes-kubelet.conf", "Port-10250"]},
                  "discovery": {"bootstrapToken": {"apiServerEndpoint": "k8s-api.branconet.lan:6443",
                                                  "token": token, "caCertHashes": ["sha256:" + pin]}}}
        print("Joining Worker 1 while keeping its current kubelet and preview containers running", flush=True)
        join_started = True
        root(WORKER, password, "timeout", "170", "kubeadm", "join", "--config=/dev/stdin",
             data=json.dumps(config).encode() + b"\n", timeout=180)
        after = node()
        if after["metadata"]["uid"] != node_uid or ready(after) != "True":
            raise RuntimeError("The original Node identity or health changed.")
        storage_after = json.loads(kube(*disks))
        if (storage_after["metadata"]["uid"] != storage_before["metadata"]["uid"] or
                storage_after["spec"]["disks"] != storage_before["spec"]["disks"]):
            raise RuntimeError("Longhorn node or disk identity changed.")
        if previews() != original_previews:
            raise RuntimeError("Preview Pod or container identity changed.")
        if {m["name"] for m in members(password) if not m.get("isLearner")} != {"masternode", "workernode2", NODE}:
            raise RuntimeError("Expected three etcd voting members.")
        local_health(password)
        root(WORKER, password, "sha256sum", "-c", BACKUP + "/kubelet.sha256")
        kube("--server=https://" + WORKER + ":6443", "get", "--raw=/readyz")
        kube("--server=https://" + WORKER + ":6443", "-n", "kube-system", "get", "secret",
             "bootstrap-token-" + token_id, "-o", "name")
        kube("label", "node", NODE, "node.kubernetes.io/exclude-from-external-load-balancers-")
        print("Three voting members verified. Worker 1 preview Pod UIDs, containers and restart counts are unchanged.", flush=True)
    except (RuntimeError, OSError, subprocess.SubprocessError, KeyError, ValueError) as error:
        print(str(error), flush=True)
        diagnostic = getattr(error, "diagnostic", "")
        for code in sorted(set(re.findall(r"\[(?:ERROR|WARNING) ([A-Za-z0-9_.-]+)\]", diagnostic))):
            print("Kubeadm check:", code, flush=True)
        if join_started:
            undo(password, {m["ID"] for m in initial})
            print("Removed only the Worker 1 addition and preserved its running kubelet.", flush=True)
        raise
    finally:
        if upload:
            remove_secret("kubeadm-certs", upload[0])
            owner = metadata(upload[1])
            if owner:
                remove_secret(upload[1], owner[0])
        if token_id:
            root(MASTER, password, "kubeadm", "token", "delete", token_id)
        print("Scoped bootstrap credentials cleaned up", flush=True)


if __name__ == "__main__":
    password = sys.stdin.buffer.readline(1024).rstrip(b"\r\n") + b"\n"
    if len(password) < 2:
        sys.exit("Missing existing privilege credential.")
    try:
        main(password)
    except (RuntimeError, OSError, subprocess.SubprocessError, KeyError, ValueError) as error:
        sys.exit(f"Worker 1 cutover stopped: {error}")
