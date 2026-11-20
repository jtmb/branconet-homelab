"""Request or inspect Longhorn's rebuild-before-removal evacuation."""
from collections import defaultdict
import json
import subprocess
import sys

NODE = "masternode"
KUBECTL = ["kubectl", "-n", "longhorn-system"]


def kube(*args):
    return json.loads(subprocess.check_output([*KUBECTL, *args, "-o", "json"], timeout=20))


def status(node):
    replicas = kube("get", "replicas.longhorn.io")["items"]
    volumes = kube("get", "volumes.longhorn.io")["items"]
    healthy_nodes, untouched_empty_nodes = defaultdict(set), defaultdict(set)
    for replica in replicas:
        spec = replica["spec"]
        if spec.get("failedAt") or replica["metadata"].get("deletionTimestamp"):
            continue
        if spec.get("healthyAt"):
            healthy_nodes[spec["volumeName"]].add(spec["nodeID"])
        elif (spec["nodeID"] and spec["nodeID"] != NODE and not spec.get("lastHealthyAt")
              and not spec.get("lastFailedAt") and replica["status"]["currentState"] == "stopped"):
            untouched_empty_nodes[spec["volumeName"]].add(spec["nodeID"])
    deficient, empty = [], []
    for volume in volumes:
        name = volume["metadata"]["name"]
        health = volume["status"]
        if (health["state"] == "detached" and int(health["actualSize"]) == 0
                and len(untouched_empty_nodes[name]) == 2):
            empty.append(name)
        elif len(healthy_nodes[name]) < 2 or (health["state"] == "attached" and health["robustness"] != "healthy"):
            deficient.append(name)
    remaining = sum(replica["spec"]["nodeID"] == NODE for replica in replicas)
    scheduled = sum(len(disk.get("scheduledReplica", {})) for disk in node["status"]["diskStatus"].values())
    backing = sum(len(disk.get("scheduledBackingImage", {})) for disk in node["status"]["diskStatus"].values())
    report = {
        "replicas_remaining": remaining, "disk_replicas_remaining": scheduled, "backing_images_remaining": backing,
        "volumes_below_protection": len(deficient), "uninitialized_empty_volumes": len(empty),
        "scheduling_enabled": node["spec"]["allowScheduling"],
        "eviction_requested": node["spec"]["evictionRequested"],
    }
    report["evacuation_complete"] = (not any((remaining, scheduled, backing, deficient)) and
                                      report["eviction_requested"] and not report["scheduling_enabled"])
    print(json.dumps(report), flush=True)
    return report


def main():
    action = sys.argv[1]
    assert action in {"status", "start"}
    node = kube("get", "nodes.longhorn.io", NODE)
    baseline = status(node)
    if action == "status" or baseline["eviction_requested"]:
        return
    assert baseline["scheduling_enabled"] and baseline["volumes_below_protection"] == 0
    assert baseline["replicas_remaining"] == baseline["disk_replicas_remaining"] == 8
    assert baseline["backing_images_remaining"] == 0
    capacity = {"__name__": "rename_capacity"}
    exec(compile(sys.argv[2], "node-rename-capacity.py", "exec"), capacity)
    if not capacity["assess"](NODE):
        raise SystemExit("Replica evacuation capacity no longer passes.")
    node = kube("get", "nodes.longhorn.io", NODE)
    patch = [
        {"op": "test", "path": "/metadata/resourceVersion", "value": node["metadata"]["resourceVersion"]},
        {"op": "test", "path": "/spec/allowScheduling", "value": True},
        {"op": "test", "path": "/spec/evictionRequested", "value": False},
        {"op": "replace", "path": "/spec/allowScheduling", "value": False},
        {"op": "replace", "path": "/spec/evictionRequested", "value": True},
    ]
    changed = kube("patch", "nodes.longhorn.io", NODE, "--type=json", "-p", json.dumps(patch))
    assert changed["metadata"]["uid"] == node["metadata"]["uid"]
    assert changed["spec"]["evictionRequested"] and not changed["spec"]["allowScheduling"]
    print("EVACUATION_REQUESTED", flush=True)


if __name__ == "__main__":
    main()
