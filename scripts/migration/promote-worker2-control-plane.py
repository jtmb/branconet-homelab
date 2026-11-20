#!/usr/bin/env python3
"""Promote Worker 2 without replacing its Kubernetes Node or Longhorn disks."""

import json
import re
import shlex
import subprocess
import sys
import time

MASTER = "192.168.0.4"
WORKER = "192.168.0.5"
NODE = "workernode2"
BACKUP = "/etc/kubernetes/.branconet-worker2-promotion"
SSH = ("ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
       "-o", "ConnectTimeout=8", "-p", "2002")
CRI = "/opt/containerd-k8s/bin/crictl"
ETCD = """
set -euo pipefail
c=$(/opt/containerd-k8s/bin/crictl --config /dev/null --runtime-endpoint unix:///run/containerd-k8s/containerd.sock ps -o json |
    jq -er '[.containers[] | select(.labels["io.kubernetes.pod.name"]=="etcd-masternode" and .labels["io.kubernetes.container.name"]=="etcd") | .id] | if length == 1 then .[0] else error("unexpected etcd containers") end')
exec /opt/containerd-k8s/bin/crictl --config /dev/null --runtime-endpoint unix:///run/containerd-k8s/containerd.sock exec "$c" etcdctl \
    --endpoints=https://127.0.0.1:2379 --cacert=/etc/kubernetes/pki/etcd/ca.crt \
    --cert=/etc/kubernetes/pki/etcd/healthcheck-client.crt --key=/etc/kubernetes/pki/etcd/healthcheck-client.key "$@"
"""


def remote(host, *argv, data=None, timeout=30):
    result = subprocess.run((*SSH, "james@" + host, shlex.join(argv)), input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode:
        error = RuntimeError(f"Remote command failed on {host}: {argv[0]} ({result.returncode})")
        error.diagnostic = result.stderr.decode(errors="replace")
        raise error
    return result.stdout


def root(host, password, *argv, data=b"", timeout=30):
    return remote(host, "sudo", "-S", "-p", "", "--", *argv, data=password + data, timeout=timeout)


def kube(*args, data=None, timeout=30):
    return remote(MASTER, "kubectl", *args, data=data, timeout=timeout)


def node():
    return json.loads(kube("get", "node", NODE, "-o", "json"))


def members(password):
    return json.loads(root(MASTER, password, "bash", "-c", ETCD, "etcd", "member", "list", "-w", "json"))["members"]


def local_health(password):
    root(MASTER, password, "bash", "-c", ETCD, "etcd", "endpoint", "health")


def wait_for(predicate, description, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(2)
    raise RuntimeError("Timed out: " + description)


def ready(current):
    return next((entry["status"] for entry in current["status"]["conditions"] if entry["type"] == "Ready"), None)


def remove_secret(name, uid):
    data = json.dumps({"apiVersion": "v1", "kind": "DeleteOptions", "preconditions": {"uid": uid}}).encode()
    kube("delete", "--raw", "/api/v1/namespaces/kube-system/secrets/" + name, "-f", "-", data=data)


def metadata(name):
    return kube("-n", "kube-system", "get", "secret", name, "--ignore-not-found",
                "-o", 'jsonpath={.metadata.uid}{"\t"}{.metadata.ownerReferences[0].name}').decode().strip().split()


def prepare_worker(password):
    script = """
set -euo pipefail
test "$(hostname -s)" = workernode2
test -f /etc/kubernetes/kubelet.conf
test ! -e /etc/kubernetes/admin.conf
test ! -e /etc/kubernetes/bootstrap-kubelet.conf
test ! -e /var/lib/etcd
test -z "$(find /etc/kubernetes/manifests -mindepth 1 -maxdepth 1 -type f -print -quit)"
umask 077
mkdir "$1"
paths=(/etc/kubernetes/kubelet.conf /etc/kubernetes/pki /var/lib/kubelet/config.yaml /var/lib/kubelet/kubeadm-flags.env)
for p in /var/lib/kubelet/instance-config.yaml /var/lib/kubelet/pki; do
  if [ -e "$p" ]; then paths+=("$p"); fi
done
cp -a --parents -- "${paths[@]}" "$1"
systemctl stop kubelet
mv -- /etc/kubernetes/kubelet.conf "$1/live-kubelet.conf"
"""
    root(WORKER, password, "bash", "-c", script, "prepare", BACKUP)


def rollback(password, baseline_id):
    local_health(password)
    current = members(password)
    if sum(item["ID"] == baseline_id for item in current) != 1:
        raise RuntimeError("Original etcd member identity changed.")
    extra = [item for item in current if item["ID"] != baseline_id]
    if extra:
        if len(extra) != 1 or extra[0]["peerURLs"] != [f"https://{WORKER}:2380"]:
            raise RuntimeError("Unexpected etcd membership. Preserve running members.")
        root(MASTER, password, "bash", "-c", ETCD, "etcd", "member", "remove", f'{extra[0]["ID"]:x}')
        local_health(password)
    script = """
set -euo pipefail
test "$(hostname -s)" = workernode2
test -d "$1" && test "$(realpath "$1")" = "$1"
if [ ! -f "$1/live-kubelet.conf" ]; then
  systemctl start kubelet
  exit
fi
systemctl stop kubelet
mkdir "$1/failed-join"
for p in /etc/kubernetes/pki /etc/kubernetes/manifests /etc/kubernetes/admin.conf \
         /etc/kubernetes/super-admin.conf /etc/kubernetes/bootstrap-kubelet.conf \
         /etc/kubernetes/controller-manager.conf /etc/kubernetes/scheduler.conf /etc/kubernetes/kubelet.conf \
         /var/lib/etcd /var/lib/kubelet/pki /var/lib/kubelet/instance-config.yaml; do
  if [ -e "$p" ]; then
    mkdir -p "$1/failed-join$(dirname "$p")"
    mv -- "$p" "$1/failed-join$p"
  fi
done
cp -a -- "$1/etc/kubernetes/." /etc/kubernetes/
cp -a -- "$1/var/lib/kubelet/." /var/lib/kubelet/
install -d -m 0755 /etc/kubernetes/manifests
systemctl start kubelet
"""
    root(WORKER, password, "bash", "-c", script, "rollback", BACKUP)
    kube("label", "node", NODE, "node-role.kubernetes.io/control-plane-",
         "node.kubernetes.io/exclude-from-external-load-balancers-")
    wait_for(lambda: ready(node()) == "True", "original worker readiness", 90)


def main(password):
    current = node()
    uid = current["metadata"]["uid"]
    labels = current["metadata"]["labels"]
    if ready(current) != "True" or current["spec"].get("unschedulable") or current["spec"].get("taints"):
        raise RuntimeError("Worker state is outside the approved starting topology.")
    if any(label in labels for label in ("node-role.kubernetes.io/control-plane", "node.kubernetes.io/exclude-from-external-load-balancers")):
        raise RuntimeError("Unexpected preexisting worker labels.")
    if metadata("kubeadm-certs"):
        raise RuntimeError("An unrelated kubeadm certificate upload is present.")
    initial = members(password)
    if len(initial) != 1 or initial[0].get("isLearner") or initial[0]["name"] != "masternode":
        raise RuntimeError("Unexpected starting etcd topology.")
    local_health(password)
    baseline_id = initial[0]["ID"]
    longhorn_args = ("-n", "longhorn-system", "get", "nodes.longhorn.io", NODE, "-o", "json")
    longhorn_before = json.loads(kube(*longhorn_args))
    volumes = json.loads(kube("-n", "longhorn-system", "get", "volumes", "-o", "json"))["items"]
    if any(v["status"].get("robustness") == "faulted" or
           (v["status"].get("state") == "attached" and v["status"].get("robustness") != "healthy") for v in volumes):
        raise RuntimeError("Longhorn is outside its healthy baseline.")

    root(WORKER, password, "test", "!", "-e", BACKUP)
    prepared = False
    safe_to_uncordon = True
    bootstrap_id = None
    upload = None
    print("Draining Worker 2 using normal eviction", flush=True)
    try:
        kube("drain", NODE, "--ignore-daemonsets", "--delete-emptydir-data", "--timeout=150s", timeout=160)
        print("Worker 2 drained", flush=True)
        kube("-n", "bortus", "rollout", "status", "deployment/bortus", "--timeout=75s", timeout=80)
        local_health(password)
        pin = root(MASTER, password, "bash", "-o", "pipefail", "-c",
                   "openssl x509 -in /etc/kubernetes/pki/ca.crt -pubkey -noout | openssl pkey -pubin -outform DER | sha256sum").decode().split()[0]
        if not re.fullmatch(r"[0-9a-f]{64}", pin):
            raise RuntimeError("Invalid cluster CA pin.")
        token = root(MASTER, password, "kubeadm", "token", "create", "--ttl=12m",
                     "--description=worker2-control-plane-join").decode().strip()
        if not re.fullmatch(r"[a-z0-9]{6}[.][a-z0-9]{16}", token):
            raise RuntimeError("Unexpected bootstrap credential format.")
        bootstrap_id = token.split(".")[0]
        key_output = root(MASTER, password, "kubeadm", "init", "phase", "upload-certs", "--upload-certs").decode()
        upload = metadata("kubeadm-certs")
        keys = re.findall(r"^[0-9a-f]{64}$", key_output, re.M)
        if len(keys) != 1 or len(upload) != 2 or not re.fullmatch(r"bootstrap-token-[a-z0-9]{6}", upload[1]):
            raise RuntimeError("Could not bind the temporary certificate upload.")
        cert_key = keys[0]
        prepared = True
        prepare_worker(password)
        wait_for(lambda: ready(node()) in ("False", "Unknown"), "existing Node to report NotReady", 100)
        print("Existing node object is retained and the old kubelet is stopped", flush=True)
        config = {"apiVersion": "kubeadm.k8s.io/v1beta4", "kind": "JoinConfiguration",
                  "controlPlane": {"localAPIEndpoint": {"advertiseAddress": WORKER, "bindPort": 6443},
                                   "certificateKey": cert_key},
                  "nodeRegistration": {"name": NODE, "criSocket": "unix:///run/containerd-k8s/containerd.sock",
                                       "taints": []},
                  "discovery": {"bootstrapToken": {"apiServerEndpoint": "k8s-api.branconet.lan:6443",
                                                  "token": token, "caCertHashes": ["sha256:" + pin]}}}
        print("Joining Worker 2 to the control plane", flush=True)
        root(WORKER, password, "timeout", "170", "kubeadm", "join", "--config=/dev/stdin",
             data=json.dumps(config).encode() + b"\n", timeout=180)
        wait_for(lambda: ready(node()) == "True", "promoted node readiness", 90)
        current = node()
        if current["metadata"]["uid"] != uid or "node-role.kubernetes.io/control-plane" not in current["metadata"]["labels"]:
            raise RuntimeError("The existing node identity was not preserved.")
        longhorn_after = json.loads(kube(*longhorn_args))
        if (longhorn_after["metadata"]["uid"] != longhorn_before["metadata"]["uid"] or
                longhorn_after["spec"]["disks"] != longhorn_before["spec"]["disks"]):
            raise RuntimeError("The Longhorn disk identity or configuration changed.")
        peer = [m for m in members(password) if m["name"] == NODE and not m.get("isLearner")]
        if len(peer) != 1 or peer[0]["peerURLs"] != [f"https://{WORKER}:2380"]:
            raise RuntimeError("Worker 2 has not joined as the expected etcd voter.")
        local_health(password)
        kube("--server=https://" + WORKER + ":6443", "get", "--raw=/readyz")
        kube("--server=https://" + WORKER + ":6443", "-n", "kube-system", "get", "secret",
             "bootstrap-token-" + bootstrap_id, "-o", "name")
        kube("label", "node", NODE, "node.kubernetes.io/exclude-from-external-load-balancers-")
        print("Worker 2 is Ready as a voting control plane. Original Node and Longhorn identities verified.", flush=True)
    except (RuntimeError, OSError, subprocess.SubprocessError, KeyError, ValueError) as error:
        print(str(error), flush=True)
        diagnostic = getattr(error, "diagnostic", "")
        for code in sorted(set(re.findall(r"\[(?:ERROR|WARNING) ([A-Za-z0-9_.-]+)\]", diagnostic))):
            print("Kubeadm check:", code, flush=True)
        if prepared:
            safe_to_uncordon = False
            rollback(password, baseline_id)
            safe_to_uncordon = True
            print("Original worker restored and etcd rollback verified", flush=True)
        raise
    finally:
        if safe_to_uncordon:
            kube("uncordon", NODE)
        if upload:
            remove_secret("kubeadm-certs", upload[0])
            owner = metadata(upload[1])
            if owner:
                remove_secret(upload[1], owner[0])
        if bootstrap_id:
            root(MASTER, password, "kubeadm", "token", "delete", bootstrap_id)
        print("Scoped bootstrap credentials cleaned up", flush=True)


if __name__ == "__main__":
    password = sys.stdin.buffer.readline(1024).rstrip(b"\r\n") + b"\n"
    if len(password) < 2:
        sys.exit("Missing existing privilege credential.")
    try:
        main(password)
    except (RuntimeError, OSError, subprocess.SubprocessError, KeyError, ValueError) as error:
        sys.exit(f"Worker 2 cutover stopped: {error}")
