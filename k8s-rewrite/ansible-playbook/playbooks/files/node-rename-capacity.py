"""Fail closed if either survivor cannot hold a second Longhorn replica."""
import json
import subprocess
import sys
from collections import defaultdict

GIB = 2**30


def resources(kind):
    data = subprocess.check_output(
        ["kubectl", "-n", "longhorn-system", "get", kind, "-o", "json"], text=True, timeout=20
    )
    return json.loads(data)["items"]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def assess(candidate, reservation_overrides=None):
    reservation_overrides = reservation_overrides or {}
    nodes = {n["metadata"]["name"]: n for n in resources("nodes.longhorn.io")}
    require(len(nodes) == 3 and candidate in nodes, "Require three Longhorn nodes and an exact candidate.")
    settings = {s["metadata"]["name"]: s["value"] for s in resources("settings.longhorn.io")}
    overprovisioning = int(settings["storage-over-provisioning-percentage"])
    floor_percent = int(settings["storage-minimal-available-percentage"])
    require(settings["replica-soft-anti-affinity"] == "false", "Require hard node replica separation.")
    require(not resources("backingimages.longhorn.io"), "Review backing image placement separately.")
    allow_empty_node = settings["allow-empty-node-selector-volume"] == "true"
    allow_empty_disk = settings["allow-empty-disk-selector-volume"] == "true"

    replicas = defaultdict(list)
    for replica in resources("replicas.longhorn.io"):
        spec = replica["spec"]
        if not spec.get("failedAt") and not replica["metadata"].get("deletionTimestamp"):
            replicas[spec["volumeName"]].append(spec["nodeID"])

    incoming = {name: [] for name in nodes if name != candidate}
    volumes = resources("volumes.longhorn.io")
    require(bool(volumes), "No Longhorn volumes were returned.")
    for volume in volumes:
        name = volume["metadata"]["name"]
        spec, status = volume["spec"], volume["status"]
        copies = replicas[name]
        require(len(copies) == len(set(copies)) == spec["numberOfReplicas"] == 2
                and set(copies) <= nodes.keys(), f"{name} lacks two distinct live replica placements.")
        require(spec.get("replicaSoftAntiAffinity") in (None, "", "ignored", "disabled"),
                f"{name} has a replica separation override that requires review.")
        require((status["state"], status["robustness"]) in
                {("attached", "healthy"), ("detached", "unknown")},
                f"{name} is not in an accepted state for a capacity estimate.")
        size = int(spec["size"])
        actual = int(status["actualSize"])
        if candidate in copies:
            target, = incoming.keys() - set(copies)
            incoming[target].append((size, actual, volume))

    print(f"{candidate}: evaluating {len(volumes)} volumes on two surviving nodes", flush=True)
    enough = True
    for name, required in sorted(incoming.items()):
        node = nodes[name]
        disks = node["spec"]["disks"]
        require(node["spec"]["allowScheduling"] and not node["spec"].get("evictionRequested")
                and len(disks) == 1, f"{name} does not have the supported single-disk layout.")
        disk, config = next(iter(disks.items()))
        require(config["allowScheduling"] and not config.get("evictionRequested"),
                f"{name} has an ineligible target disk.")
        node_tags = set(node["spec"].get("tags") or [])
        disk_tags = set(config.get("tags") or [])
        for _, _, volume in required:
            spec = volume["spec"]
            required_node = set(spec.get("nodeSelector") or [])
            required_disk = set(spec.get("diskSelector") or [])
            node_matches = required_node <= node_tags and (required_node or not node_tags or allow_empty_node)
            disk_matches = required_disk <= disk_tags and (required_disk or not disk_tags or allow_empty_disk)
            if not node_matches or not disk_matches:
                enough = False
                pvc = volume["status"].get("kubernetesStatus", {}).get("pvcName")
                identifier = pvc or volume["metadata"]["name"]
                print(f"{name}: placement excludes {identifier} "
                      f"(node tags {sorted(required_node)}, disk tags {sorted(required_disk)})", flush=True)
        status = node["status"]["diskStatus"][disk]
        require(any(c["type"] == "Ready" and c["status"] == "True" for c in status["conditions"]),
                f"{name} disk is not Ready.")
        maximum = status["storageMaximum"]
        available = status["storageAvailable"]
        scheduled = status["storageScheduled"]
        reservation = reservation_overrides.get(name, config["storageReserved"])
        cap = (maximum - reservation) * overprovisioning // 100
        floor = maximum * floor_percent // 100
        logical_incoming = sum(size for size, _, _ in required)
        physical_incoming = sum(actual for _, actual, _ in required)
        logical_margin = cap - scheduled - logical_incoming
        physical_margin = available - floor - physical_incoming
        enough = enough and logical_margin >= 0 and physical_margin > 0
        print(f"{name}: {len(required)} incoming replicas, scheduled margin "
              f"{logical_margin / GIB:+.2f} GiB, estimated free-space margin "
              f"{physical_margin / GIB:+.2f} GiB", flush=True)
        print(f"  scheduled {scheduled / GIB:.2f} + incoming {logical_incoming / GIB:.2f}"
              f" / cap {cap / GIB:.2f} GiB", flush=True)
        print(f"  available {available / GIB:.2f} - estimated incoming {physical_incoming / GIB:.2f}"
              f" / minimum free {floor / GIB:.2f} GiB", flush=True)
    return enough


if __name__ == "__main__":
    if not assess(sys.argv[1]):
        raise SystemExit("Longhorn capacity gate failed. Do not drain or retire this node.")
    print("Longhorn capacity estimate passed. Verify live eviction and the other rename gates separately.")
