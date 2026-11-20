"""Adjust only Worker 2's default Longhorn disk reservation for the master rename."""
import json
import subprocess
import sys

NODE = "workernode2"
DISK = "default-disk-7119ce24364c6cfd"
MAXIMUM = 115702075392
BASELINE = 34710622617
REQUIRED_CAPACITY = 84 * 2**30
PROPOSED = MAXIMUM - REQUIRED_CAPACITY
KUBECTL = ["kubectl", "-n", "longhorn-system"]


def kube(*args):
    return json.loads(subprocess.check_output([*KUBECTL, *args, "-o", "json"], timeout=20))


def get_disk():
    node = kube("get", "nodes.longhorn.io", NODE)
    assert set(node["spec"]["disks"]) == {DISK}, "Worker 2 disk identity changed"
    config = node["spec"]["disks"][DISK]
    status = node["status"]["diskStatus"][DISK]
    assert config["path"] == "/var/lib/longhorn/" and config["allowScheduling"] and not config.get("evictionRequested")
    assert status["storageMaximum"] == MAXIMUM and status["storageScheduled"] <= REQUIRED_CAPACITY
    return node, config["storageReserved"], status["storageScheduled"]


def replace(node, old, new, dry_run=False):
    path = f"/spec/disks/{DISK}/storageReserved"
    patch = [
        {"op": "test", "path": "/metadata/resourceVersion", "value": node["metadata"]["resourceVersion"]},
        {"op": "test", "path": path, "value": old},
        {"op": "replace", "path": path, "value": new},
    ]
    options = ["--dry-run=server"] if dry_run else []
    result = kube("patch", "nodes.longhorn.io", NODE, "--type=json", "-p", json.dumps(patch), *options)
    assert result["spec"]["disks"][DISK]["storageReserved"] == new
    assert {k: v for k, v in result["spec"]["disks"][DISK].items() if k != "storageReserved"} == {
        k: v for k, v in node["spec"]["disks"][DISK].items() if k != "storageReserved"
    }


def main():
    action = sys.argv[1]
    assert action in {"plan", "apply", "rollback"}
    capacity = {"__name__": "rename_capacity"}
    exec(compile(sys.argv[2], "node-rename-capacity.py", "exec"), capacity)
    settings = {s["metadata"]["name"]: s["value"] for s in kube("get", "settings.longhorn.io")["items"]}
    for key, expected in (("storage-over-provisioning-percentage", "100"),
                          ("storage-minimal-available-percentage", "25"),
                          ("replica-soft-anti-affinity", "false"), ("replica-auto-balance", "disabled")):
        assert settings[key] == expected, f"Longhorn protection changed: {key}"
    node, old, scheduled = get_disk()
    assert old in {BASELINE, PROPOSED}, "Unexpected Worker 2 reservation"
    if action == "rollback":
        assert scheduled <= MAXIMUM - BASELINE, "Worker 2 must fit the original reservation before rollback"
        if old != BASELINE:
            replace(node, old, BASELINE)
        assert get_disk()[1] == BASELINE
        print(f"RESULT_CHANGED={str(old != BASELINE).lower()}")
        return
    volumes = kube("get", "volumes.longhorn.io")["items"]
    assert sum(int(v["spec"]["size"]) for v in volumes) == REQUIRED_CAPACITY, "Logical demand changed"
    if not capacity["assess"]("masternode", {NODE: PROPOSED}):
        raise SystemExit("Both surviving disks must pass the projected rename capacity check.")
    if old != PROPOSED:
        replace(node, old, PROPOSED, dry_run=action == "plan")
    if action == "apply":
        try:
            assert get_disk()[1] == PROPOSED and capacity["assess"]("masternode")
        except (Exception, SystemExit):
            current, reservation, scheduled = get_disk()
            if old == BASELINE and reservation == PROPOSED and scheduled <= MAXIMUM - BASELINE:
                replace(current, PROPOSED, BASELINE)
                print("Restored the original reservation after failed verification.", flush=True)
            raise
    print(f"Worker 2 disk reservation: {old} -> {PROPOSED}; required capacity: {REQUIRED_CAPACITY}")
    print(f"RESULT_CHANGED={str(action == 'apply' and old != PROPOSED).lower()}")


if __name__ == "__main__":
    main()
