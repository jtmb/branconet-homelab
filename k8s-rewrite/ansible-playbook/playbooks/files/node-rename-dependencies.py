"""Identify workload and local storage references to a retiring Kubernetes node."""
import json
import subprocess
import sys


def resources(kinds):
    output = subprocess.check_output(
        ["kubectl", "get", kinds, "-A", "-o", "json"], text=True, timeout=25
    )
    return json.loads(output)["items"]


def identity(item):
    metadata = item["metadata"]
    namespace = metadata.get("namespace")
    name = metadata["name"]
    return f'{item["kind"]}/{namespace}/{name}' if namespace else f'{item["kind"]}/{name}'


def references(terms, node):
    for term in terms:
        for clause, key in (("matchExpressions", "kubernetes.io/hostname"), ("matchFields", "metadata.name")):
            if any(entry["key"] == key and node in entry.get("values", [])
                   for entry in term.get(clause, [])):
                return True
    return False


def pod_template(item):
    spec = item["spec"]
    if item["kind"] == "CronJob":
        spec = spec["jobTemplate"]["spec"]
    return spec["template"]["spec"]


def inspect(node):
    hard, advisory, unmanaged = [], [], []
    for item in resources("deployments,statefulsets,daemonsets,jobs,cronjobs"):
        if item["kind"] == "Job" and any(
                state["type"] in ("Complete", "Failed") and state["status"] == "True"
                for state in item.get("status", {}).get("conditions", [])):
            continue
        template = pod_template(item)
        affinity = template.get("affinity", {}).get("nodeAffinity", {})
        required = affinity.get("requiredDuringSchedulingIgnoredDuringExecution", {}).get("nodeSelectorTerms", [])
        preferred = [rule["preference"] for rule in affinity.get("preferredDuringSchedulingIgnoredDuringExecution", [])]
        if (template.get("nodeName") == node
                or template.get("nodeSelector", {}).get("kubernetes.io/hostname") == node
                or references(required, node)):
            hard.append(identity(item))
        if references(preferred, node):
            advisory.append(identity(item))

    for item in resources("pods"):
        metadata = item["metadata"]
        if (item["spec"].get("nodeName") == node and not metadata.get("ownerReferences")
                and not metadata.get("annotations", {}).get("kubernetes.io/config.mirror")
                and item.get("status", {}).get("phase") not in ("Succeeded", "Failed")):
            volumes = item["spec"].get("volumes", [])
            local_state = [v["name"] for v in volumes if "emptyDir" in v or "hostPath" in v]
            unmanaged.append({"pod": identity(item), "local_state": sorted(local_state)})

    pinned_volumes = [
        identity(item) for item in resources("persistentvolumes")
        if references(item["spec"].get("nodeAffinity", {}).get("required", {}).get("nodeSelectorTerms", []), node)
    ]
    return {"hard_workloads": sorted(hard), "preferred_workloads": sorted(advisory),
            "unmanaged_pods": sorted(unmanaged, key=lambda item: item["pod"]),
            "pinned_volumes": sorted(pinned_volumes)}


if __name__ == "__main__":
    print(json.dumps(inspect(sys.argv[1])))
