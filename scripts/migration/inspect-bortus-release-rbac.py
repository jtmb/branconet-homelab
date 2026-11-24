#!/usr/bin/env python3
"""Read RBAC bindings/rules for one service account without reading Secrets.

This is a release inventory, not an authorization or revocation proof. It
records direct, username and group grants so release review cannot miss grants
that do not name the ServiceAccount in a binding's subjects.
"""
import argparse
import datetime
import json
import os
import pathlib
import subprocess


def inventory(snapshot, namespace, name):
    username = f"system:serviceaccount:{namespace}:{name}"
    groups = {"system:authenticated", "system:serviceaccounts",
              f"system:serviceaccounts:{namespace}"}
    roles = {(r["metadata"]["namespace"], r["metadata"]["name"]): r
             for r in snapshot["roles"]}
    cluster_roles = {r["metadata"]["name"]: r for r in snapshot["clusterroles"]}
    grants = []
    for binding_kind, items in (("RoleBinding", snapshot["rolebindings"]),
                                ("ClusterRoleBinding", snapshot["clusterrolebindings"])):
        for binding in items:
            metadata = binding["metadata"]
            binding_ns = metadata.get("namespace")
            matched = []
            for subject in binding.get("subjects", []):
                kind = subject.get("kind")
                if kind == "ServiceAccount":
                    selected = (subject.get("name") == name and
                                subject.get("namespace", binding_ns) == namespace)
                elif kind == "User":
                    selected = subject.get("name") == username
                elif kind == "Group":
                    selected = subject.get("name") in groups
                else:
                    selected = False
                if selected:
                    matched.append({k: subject[k] for k in
                                    ("kind", "name", "namespace") if k in subject})
            if not matched:
                continue
            ref = binding["roleRef"]
            if ref.get("apiGroup") != "rbac.authorization.k8s.io":
                role = None
            elif ref.get("kind") == "ClusterRole":
                role = cluster_roles.get(ref.get("name"))
            elif ref.get("kind") == "Role" and binding_kind == "RoleBinding":
                role = roles.get((binding_ns, ref.get("name")))
            else:
                role = None
            # These are RBAC policy metadata, not Secret contents or tokens.
            rules = [] if role is None else [
                {k: rule[k] for k in ("apiGroups", "resources", "verbs",
                                      "resourceNames", "nonResourceURLs") if k in rule}
                for rule in role.get("rules", [])]
            grants.append({
                "binding": {"kind": binding_kind, "namespace": binding_ns,
                            "name": metadata["name"], "uid": metadata.get("uid"),
                            "resourceVersion": metadata.get("resourceVersion")},
                "matchedSubjects": matched,
                "roleRef": {k: ref.get(k) for k in ("apiGroup", "kind", "name")},
                "scope": binding_ns if binding_kind == "RoleBinding" else "cluster",
                "roleResolved": role is not None,
                "roleUid": None if role is None else role["metadata"].get("uid"),
                "roleResourceVersion": None if role is None else role["metadata"].get("resourceVersion"),
                "aggregationRulePresent": role is not None and "aggregationRule" in role,
                "rules": rules,
                "unmatchedSubjectCount": len(binding.get("subjects", [])) - len(matched),
            })
    grants.sort(key=lambda g: (g["binding"]["kind"], g["binding"]["namespace"] or "",
                               g["binding"]["name"]))
    return {
        "checkedAtUtc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope": "read-only RBAC metadata; no credential reads or mutations",
        "principal": username, "groups": sorted(groups), "grants": grants,
        "matchingBindingCount": len(grants),
        "unresolvedRoleCount": sum(not g["roleResolved"] for g in grants),
        "sourceCounts": {k: len(v) for k, v in snapshot.items()},
        "limitations": [
            "Separate resource reads are not an atomic Kubernetes snapshot.",
            "This inventories RBAC grants, not other authorizers or an actual authorization decision.",
            "Aggregated ClusterRole rules are the API's current rules, not proof of controller convergence.",
            "No permissions were revoked. Actual authorization and preservation checks remain required.",
            "Unmatched binding subjects must be preserved during any later reviewed revocation.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kubectl", type=pathlib.Path, required=True)
    parser.add_argument("--kubeconfig", type=pathlib.Path, required=True)
    parser.add_argument("--namespace", default="bortus")
    parser.add_argument("--service-account", default="bortus")
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    snapshot = {}
    for resource in ("roles", "rolebindings", "clusterroles", "clusterrolebindings"):
        command = [str(args.kubectl), "--kubeconfig", str(args.kubeconfig),
                   "--request-timeout=20s", "get", resource]
        if resource in ("roles", "rolebindings"):
            command.append("-A")
        command += ["-o", "json"]
        try:
            result = subprocess.run(command, capture_output=True, timeout=25, check=False)
            if result.returncode:
                raise ValueError("read failed")
            data = json.loads(result.stdout)
            metadata = data.get("metadata", {})
            if metadata.get("continue") or metadata.get("remainingItemCount", 0):
                raise ValueError("incomplete list")
            if not isinstance(data.get("items"), list):
                raise ValueError("invalid list")
            snapshot[resource] = data["items"]
        except (ValueError, TypeError, AttributeError, subprocess.TimeoutExpired, OSError):
            raise SystemExit(f"RBAC inventory failed for {resource}; no report written") from None
    try:
        report = inventory(snapshot, args.namespace, args.service_account)
    except (KeyError, TypeError, AttributeError):
        raise SystemExit("RBAC inventory schema is invalid; no report written") from None
    # Refuse historical evidence overwrite, including accidental reruns.
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    print(json.dumps({"matchingBindings": report["matchingBindingCount"],
                      "unresolvedRoles": report["unresolvedRoleCount"],
                      "report": str(args.output)}))


if __name__ == "__main__":
    main()
