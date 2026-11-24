#!/usr/bin/env python3
"""Rename the drained first control plane without changing its etcd peer or data."""
import getpass
import json
from pathlib import Path
import runpy
import subprocess
import sys
import time

helpers = runpy.run_path(str(Path(__file__).with_name("promote-worker2-control-plane.py")))
root = helpers["root"]
OLD, NEW = "masternode", "node01"
MASTER, SURVIVOR = "192.168.0.4", "192.168.0.5"
VIP = "https://192.168.0.251:6443"
ADMIN = "/etc/kubernetes/admin.conf"
STAGE = "/etc/kubernetes/.branconet-node01-rename"
CRI = ("/opt/containerd-k8s/bin/crictl", "--config", "/dev/null",
       "--runtime-endpoint", "unix:///run/containerd-k8s/containerd.sock")

HOST_SWITCH = r"""
set -euo pipefail
d=/etc/kubernetes/.branconet-node01-rename
test "$(hostname -s)" = masternode
test -s "$d/node01.kubelet.conf"
test ! -e "$d/original"
test -d /var/lib/etcd/member
test ! -L /var/lib/kubelet/pki
etcd=/etc/kubernetes/manifests/etcd.yaml
grep -qx '    - --name=masternode' "$etcd"
grep -qx '    - --initial-cluster=masternode=https://192.168.0.4:2380' "$etcd"
sed -e 's/--name=masternode$/--name=node01/' -e 's/--initial-cluster=masternode=/--initial-cluster=node01=/' "$etcd" > "$d/etcd.next"
chmod --reference="$etcd" "$d/etcd.next"
kubectl --kubeconfig=/etc/kubernetes/admin.conf create --dry-run=client --validate=false -f "$d/etcd.next" -o name >/dev/null
mkdir -m 700 "$d/original"
cp -a /etc/hosts /etc/hostname /etc/kubernetes/kubelet.conf "$etcd" "$d/original/"
sed -E 's/^(127[.]0[.]1[.]1|192[.]168[.]0[.]4)([[:space:]]+)masternode$/\1\2node01 masternode/' /etc/hosts > "$d/hosts.next"
grep -q '^192[.]168[.]0[.]4[[:space:]]*node01 masternode$' "$d/hosts.next"
systemctl stop kubelet
cri=(/opt/containerd-k8s/bin/crictl --config /dev/null --runtime-endpoint unix:///run/containerd-k8s/containerd.sock)
for component in kube-apiserver kube-controller-manager kube-scheduler etcd; do
  id=$("${cri[@]}" pods --name "^$component-masternode$" --state ready -q)
  test -n "$id"
  test "$(printf '%s\n' "$id" | wc -l)" = 1
  "${cri[@]}" stopp "$id"
done
mv -- /var/lib/kubelet/pki "$d/original/kubelet-pki"
install -d -m 700 /var/lib/kubelet/pki
install -m 600 "$d/node01.kubelet.conf" /etc/kubernetes/kubelet.conf
mv -- "$d/etcd.next" "$etcd"
cat "$d/hosts.next" > /etc/hosts
hostnamectl set-hostname node01
test "$(hostname -s)" = node01
"""

HOST_RESTORE = r"""
set -euo pipefail
d=/etc/kubernetes/.branconet-node01-rename
test -d "$d/original"
systemctl stop kubelet
cri=(/opt/containerd-k8s/bin/crictl --config /dev/null --runtime-endpoint unix:///run/containerd-k8s/containerd.sock)
for component in kube-apiserver kube-controller-manager kube-scheduler etcd; do
  id=$("${cri[@]}" pods --name "^$component-node01$" --state ready -q)
  if [ -n "$id" ]; then
    test "$(printf '%s\n' "$id" | wc -l)" = 1
    "${cri[@]}" stopp "$id"
  fi
done
if [ -d "$d/original/kubelet-pki" ]; then
  if [ -d /var/lib/kubelet/pki ]; then
    test ! -e "$d/new-kubelet-pki"
    mv -- /var/lib/kubelet/pki "$d/new-kubelet-pki"
  fi
  mv -- "$d/original/kubelet-pki" /var/lib/kubelet/pki
fi
cp -a -- "$d/original/kubelet.conf" /etc/kubernetes/kubelet.conf
cp -a -- "$d/original/etcd.yaml" /etc/kubernetes/manifests/etcd.yaml
cat "$d/original/hosts" > /etc/hosts
hostnamectl set-hostname masternode
systemctl start kubelet
systemctl start keepalived
"""

ETCD = r"""
set -euo pipefail
c=$(/opt/containerd-k8s/bin/crictl --config /dev/null --runtime-endpoint unix:///run/containerd-k8s/containerd.sock ps --name '^etcd$' -q)
test "$(printf '%s\n' "$c" | wc -l)" = 1
test -n "$c"
exec /opt/containerd-k8s/bin/crictl --config /dev/null --runtime-endpoint unix:///run/containerd-k8s/containerd.sock exec "$c" etcdctl \
 --endpoints=https://127.0.0.1:2379 --cacert=/etc/kubernetes/pki/etcd/ca.crt \
 --cert=/etc/kubernetes/pki/etcd/healthcheck-client.crt --key=/etc/kubernetes/pki/etcd/healthcheck-client.key "$@"
"""


def main(password, retained_worker=0):
    workers = {
        1: ("workernode1", "node02", "192.168.0.6", "ec68ff17-a66d-41f4-b600-fa0b6bb44005", "node03"),
        2: ("workernode2", "node03", "192.168.0.5", "3e98444f-4c34-438d-a0d3-5181c9c80a15", "workernode1"),
    }
    if retained_worker:
        old_name, new_name, target, disk_id, peer = workers[retained_worker]
        survivor = MASTER
        stage = f"/var/lib/branconet-control-plane-recovery/{new_name}"
        if retained_worker == 1:
            stage += "-retry"
        healthy_nodes = {"node01", peer}
    else:
        old_name, new_name, target, survivor, stage = OLD, NEW, MASTER, SURVIVOR, STAGE
        healthy_nodes = {"workernode1", "workernode2"}

    def host_script(script):
        if not retained_worker:
            return script
        script = script.replace(
            "grep -qx '    - --initial-cluster=masternode=https://192.168.0.4:2380' \"$etcd\"",
            "grep -Eq '^    - --initial-cluster=([^,]+,)*masternode=https://192[.]168[.]0[.]4:2380(,.*)?$' \"$etcd\"")
        script = script.replace("sed -e 's/--name=", "sed -E -e 's/--name=")
        script = script.replace("'s/--initial-cluster=masternode=/--initial-cluster=node01=/'",
                                r"'s/([=,])masternode=/\1node01=/'")
        return (script.replace(STAGE, stage).replace("masternode", old_name).replace("node01", new_name)
                .replace("192[.]168[.]0[.]4", target.replace(".", "[.]")))

    def call(host, *args, **kwargs):
        return root(host, password, *args, **kwargs)

    def kube(*args, server=f"https://{survivor}:6443", **kwargs):
        return call(survivor, "kubectl", f"--kubeconfig={ADMIN}", f"--server={server}", *args, **kwargs)

    def node(name):
        data = kube("get", "node", name, "--ignore-not-found", "-o", "json")
        return json.loads(data) if data.strip() else None

    def members():
        raw = call(survivor, "bash", "-c", ETCD, "etcd", "member", "list", "-w", "json")
        return {m["ID"]: (m["name"], m["peerURLs"], m.get("isLearner", False)) for m in json.loads(raw)["members"]}

    def health():
        call(survivor, "bash", "-c", ETCD, "etcd", "endpoint", "health", "--cluster")

    def wait(check, description, seconds=65):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                if check():
                    return
            except (RuntimeError, subprocess.SubprocessError):
                pass
            time.sleep(2)
        raise RuntimeError(f"Timed out waiting for {description}")

    def remove_node(name, uid):
        body = json.dumps({"apiVersion":"v1","kind":"DeleteOptions","preconditions":{"uid":uid}}).encode()
        kube("delete", "--raw", "/api/v1/nodes/" + name, "-f", "/dev/stdin", data=body)

    def ready(name):
        item = node(name)
        return bool(item and any(c["type"] == "Ready" and c["status"] == "True"
                                 for c in item.get("status", {}).get("conditions", [])))

    def identity(name):
        kube("label", "node", name, "node-role.kubernetes.io/control-plane=", f"branconet.lan/node-id={new_name}")
        if retained_worker:
            kube("label", "node", name, "branconet.lan/edge-announcer=true")
        if "node.kubernetes.io/exclude-from-external-load-balancers" in node(name)["metadata"]["labels"]:
            kube("label", "node", name, "node.kubernetes.io/exclude-from-external-load-balancers-")
        kube("uncordon", name)

    old = node(old_name)
    assert old and old["spec"].get("unschedulable") and not node(new_name), "Unexpected original/new Node state"
    assert all(t["key"] == "node.kubernetes.io/unschedulable" and t["effect"] == "NoSchedule"
               for t in old["spec"].get("taints", [])), "Unexpected original Node taints"
    replica_doc = json.loads(kube("-n", "longhorn-system", "get", "replicas.longhorn.io", "-o", "json"))
    if retained_worker:
        replicas = replica_doc["items"]
        old_replicas = [r for r in replicas if r["spec"]["nodeID"] == old_name]
        assert old_replicas, "Expected retained replicas"
        pod_doc = json.loads(kube("get", "pods", "-A", "--field-selector",
                                  f"spec.nodeName={old_name}", "-o", "json"))
        assert all(p["status"]["phase"] in {"Succeeded", "Failed"}
                   or "kubernetes.io/config.mirror" in p["metadata"].get("annotations", {})
                   or any(o["kind"] == "DaemonSet" for o in p["metadata"].get("ownerReferences", []))
                   for p in pod_doc["items"]), "Complete the normal drain before changing identity"
        volume_doc = json.loads(kube("-n", "longhorn-system", "get", "volumes.longhorn.io", "-o", "json"))
        volumes = {v["metadata"]["name"]: v["status"] for v in volume_doc["items"]}
        for replica in old_replicas:
            spec = replica["spec"]
            volume = spec["volumeName"]
            copies = [r["spec"] for r in replicas if r["spec"]["volumeName"] == volume]
            healthy_survivor = any(r["nodeID"] in healthy_nodes
                                   and r.get("healthyAt") and not r.get("failedAt") for r in copies)
            empty = volumes[volume].get("state") == "detached" and volumes[volume].get("actualSize") == 0
            assert healthy_survivor or (empty and not any(r.get("healthyAt") for r in copies)), volume
        retained = set()
        for replica in old_replicas:
            spec = replica["spec"]
            other_good = {r["spec"]["nodeID"] for r in replicas
                          if r["spec"]["volumeName"] == spec["volumeName"]
                          and r["spec"]["nodeID"] != old_name and r["spec"].get("healthyAt")
                          and not r["spec"].get("failedAt")}
            if not (spec.get("failedAt") and len(other_good) >= 2):
                retained.add(replica["metadata"]["name"])
        assert {r["spec"]["diskID"] for r in old_replicas} == {disk_id}
        assert json.loads(call(target, "cat", "/var/lib/longhorn/longhorn-disk.cfg"))["diskUUID"] == disk_id
    else:
        assert all(r["spec"]["nodeID"] != old_name for r in replica_doc["items"]), "Evacuation no longer complete"
    before = members()
    expected = {old_name, *healthy_nodes}
    assert {value[0] for value in before.values()} == expected
    assert len(before) == 3 and all(not value[2] for value in before.values())
    health()
    after = {key: (new_name if val[0] == old_name else val[0], val[1], val[2]) for key,val in before.items()}
    switch = False
    moved_vip = False
    rejoined = False
    try:
        call(target, "systemctl", "stop", "keepalived")
        moved_vip = True
        wait(lambda: kube("get", "--raw=/readyz", server=VIP).strip() == b"ok", "shared API on a survivor", 25)
        assert b"192.168.0.251/" not in call(target,"ip","-4","-o","address","show")
        print("Shared API answered after moving off the original node.", flush=True)
        switch = True
        call(target, "bash", "-c", host_script(HOST_SWITCH), timeout=120)
        remove_node(old_name, old["metadata"]["uid"])
        wait(lambda: not node(old_name), "old Kubernetes Node removal", 25)
        call(target, "systemctl", "start", "kubelet")
        wait(lambda: ready(new_name), "renamed Kubernetes node readiness", 105)
        kube("cordon", new_name)
        wait(lambda: members() == after, "all original etcd member IDs with the new name", 45)
        health()
        wait(lambda: kube("get", "--raw=/readyz", server=f"https://{target}:6443").strip() == b"ok",
             "renamed local API", 35)
        identity(new_name)
        call(target, "systemctl", "start", "keepalived")
        wait(lambda: kube("get", "--raw=/readyz", server=VIP).strip() == b"ok", "shared API after rejoin", 30)
        print("Renamed host and Kubernetes Node are Ready. Three original etcd voters and the shared API passed.", flush=True)
        rejoined = True
        if retained_worker:
            def disk_reconnected():
                result = json.loads(kube("-n", "longhorn-system", "get", "replicas.longhorn.io", "-o", "json"))
                found = {r["metadata"]["name"] for r in result["items"]
                         if r["spec"]["nodeID"] == new_name and r["spec"]["diskID"] == disk_id}
                return retained <= found

            wait(disk_reconnected, "the retained Longhorn replicas on the same disk", 150)
            print("Longhorn reconnected the original disk and all retained replicas.", flush=True)
    except (Exception, KeyboardInterrupt):
        if rejoined:
            raise
        try:
            call(target, "test", "-d", stage + "/original")
        except RuntimeError:
            switch = False
        if switch:
            print("Rename verification failed. Restoring the original identity.", flush=True)
            replacement = node(new_name)
            if replacement:
                call(target, "systemctl", "stop", "kubelet")
                remove_node(new_name, replacement["metadata"]["uid"])
            call(target, "bash", "-c", host_script(HOST_RESTORE), timeout=120)
            wait(lambda: ready(old_name), "restored original node", 105)
            identity(old_name)
        else:
            if moved_vip:
                call(target, "systemctl", "start", "keepalived")
            kube("uncordon", old_name)
        raise


if __name__ == "__main__":
    choices = {"--apply": 0, "--apply-worker1-retain-disk": 1, "--apply-worker2-retain-disk": 2}
    if len(sys.argv) != 2 or sys.argv[1] not in choices:
        raise SystemExit("Use --apply only after live evacuation and a fresh encrypted checkpoint.")
    try:
        main((getpass.getpass("Control-plane sudo password: ") + "\n").encode(),
             retained_worker=choices[sys.argv[1]])
    except Exception as error:
        raise SystemExit(str(error))
