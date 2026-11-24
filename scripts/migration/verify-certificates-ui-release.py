#!/usr/bin/env python3
"""Acceptance for the Certificates UI release (read-only).

Proves the feature is live from three independent angles: the deployment's
desired image is exactly the pinned immutable digest, the routes are present
inside one Ready pod *belonging to the current rollout*, and the HTTP
behaviour through the LAN-CA ingress.

Pod pinning (2026-11-18 review finding): the previous version compared a
digest *prefix* against the desired template and then executed its route
checks against whichever pod `exec deploy/bortus` selected. During a
rollout that could pass against a healthy old pod before the new image
served anything. The verifier now requires the deployment to be fully
reconciled, selects a Ready pod owned by the deployment's *current*
ReplicaSet whose image is exactly the pinned digest, and runs the route
checks on that exact pod name.
"""
import argparse
import base64
import http.client
import json
from pathlib import Path
import re
import ssl
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "migration"))
import importlib.util

SPEC = importlib.util.spec_from_file_location("rel_api", ROOT / "scripts/migration/stage-ntfy-cluster.py")
API = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(API)

# The full immutable image reference of the release being verified — never a
# prefix: a prefix also matches other tags pushed to the same repository.
EXPECTED_IMAGE = "docker.io/jtmb92/bortus@sha256:44a163a948e6c4e9c4cc9fb6b10294429cda42c1ae7802d2ebfd86f2d0b82a27"
NAMESPACE = "bortus"
DEPLOYMENT = "bortus"
HOST = "bortus.branconet.lan"


def kubectl_json(args):
    return API.call(args, limit=8 * 1024 * 1024)


def select_verified_pod(deployment, replicasets, pods, expected_image=EXPECTED_IMAGE):
    """Return (pod_or_None, reasons) for the exact pod that proves the release.

    Refuses mid-rollout states: the deployment must be fully reconciled, and
    the pod must belong to the deployment's current ReplicaSet and run the
    desired image. A healthy old pod satisfies none of that.
    """
    reasons = []
    meta, spec, status = deployment["metadata"], deployment["spec"], deployment.get("status", {})
    desired = spec["template"]["spec"]["containers"][0]["image"]
    if desired != expected_image:
        reasons.append("desired_image_is_not_the_pinned_digest")
    if status.get("observedGeneration") != meta.get("generation"):
        reasons.append("deployment_not_reconciled")
    if reasons:
        # A wrong digest or a mid-rollout deployment must never fall through
        # to pod matching: a healthy old pod satisfies neither guarantee.
        return None, reasons
    revision = meta.get("annotations", {}).get("deployment.kubernetes.io/revision")
    owned = [rs for rs in replicasets
             if any(ref.get("uid") == meta.get("uid")
                    for ref in rs["metadata"].get("ownerReferences", []))]
    current = [rs for rs in owned
                if rs["metadata"].get("annotations", {}).get("deployment.kubernetes.io/revision") == revision]
    if not current:
        reasons.append("current_replicaset_missing")
        return None, reasons
    rs_uid = current[0]["metadata"]["uid"]
    candidates = [pod for pod in pods
                  if any(ref.get("uid") == rs_uid for ref in pod["metadata"].get("ownerReferences", []))]
    if not candidates:
        reasons.append("no_pod_owned_by_current_replicaset")
    ready = [pod for pod in candidates if pod["status"].get("phase") == "Running"
             and all(container.get("ready") for container in pod["status"].get("containerStatuses", []))]
    if not ready:
        reasons.append("current_rollout_has_no_ready_pod")
        return None, reasons
    matching = [pod for pod in ready
                if pod["spec"]["containers"][0]["image"] == desired
                and any(desired[desired.index("sha256:"):] in container.get("imageID", "")
                        for container in pod["status"].get("containerStatuses", []))]
    if not matching:
        reasons.append("ready_pod_does_not_run_the_pinned_image")
        return None, reasons
    return matching[0], reasons


def pod_exec(pod_name, args):
    K = ["/home/brajam/.local/share/branconet-migration/bin/kubectl",
         "--kubeconfig", "/home/brajam/.local/share/branconet-migration/admin.conf"]
    q = subprocess.run(K + ["-n", NAMESPACE, "exec", pod_name, "--", *args],
                       capture_output=True, text=True, timeout=90)
    return q.returncode, (q.stdout or "").strip(), (q.stderr or "")[:200]


def https(path):
    ca = base64.b64decode(API.run_bounded(API.BASE + [
        "get", "secret", "private-ntfy-tls", "-n", "bortus-notifications",
        "-o", r"jsonpath={.data.ca\.crt}"], output_limit=16384, timeout=20))
    ctx = ssl.create_default_context(cadata=ca.decode())
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    connection = http.client.HTTPSConnection(HOST, 443, timeout=10, context=ctx)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return {"status": response.status, "location": response.getheader("Location")}
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-image", default=EXPECTED_IMAGE)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    expected = args.expected_image
    if not re.fullmatch(r"docker\.io/jtmb92/bortus@sha256:[0-9a-f]{64}", expected):
        parser.error("--expected-image must be a full immutable BORTUS reference")
    deployment = kubectl_json(["get", "deployment", DEPLOYMENT, "-n", NAMESPACE, "-o", "json"])
    replicasets = kubectl_json(["get", "replicaset", "-n", NAMESPACE, "-o", "json"])["items"]
    pods = kubectl_json(["get", "pods", "-n", NAMESPACE, "-l", "app=bortus", "-o", "json"])["items"]
    pod, selection_reasons = select_verified_pod(deployment, replicasets, pods, expected)
    pod_name = pod["metadata"]["name"] if pod else None

    routes_ok, route_list = False, []
    api_ok, api_dir = False, "ABSENT"
    if pod_name:
        # Route checks run on the exact verified pod, never a deployment-level
        # exec that could pick any healthy pod.
        code, routes, _ = pod_exec(pod_name, ["sh", "-c", 'ls "/app/.next/server/app/(dashboard)"'])
        if code == 0:
            route_list = sorted(r.replace(".js", "") for r in routes.split()
                                if not r.endswith((".json", ".js")) and not r.startswith("page"))
        routes_ok = "certificates" in route_list
        code_api, api_dir, _ = pod_exec(pod_name, ["sh", "-c",
                                "ls -d /app/.next/server/app/api/certificates 2>/dev/null || echo ABSENT"])
        api_ok = code_api == 0 and api_dir.strip() == "/app/.next/server/app/api/certificates"

    restarts = sum(container.get("restartCount", 0) for container in
                   pod["status"].get("containerStatuses", [])) if pod else None
    api_http = https("/api/certificates")
    page_http = https("/certificates")

    checks = {
        "deploymentDesiredImageIsPinned": deployment["spec"]["template"]["spec"]["containers"][0]["image"] == expected,
        "deploymentFullyReconciled": pod is not None,
        "verifiedPodBelongsToCurrentRollout": pod is not None,
        "verifiedPodRunsPinnedImage": pod is not None,
        "verifiedPodReady": pod is not None,
        "verifiedPodZeroRestarts": restarts == 0,
        "certificatesRouteInVerifiedPod": routes_ok,
        "apiCertificatesInVerifiedPod": api_ok,
        "apiUnauthenticatedIs401Not404": api_http.get("status") == 401,
        "pageIsRedirectNot404": page_http.get("status") in (302, 307, 308),
        "lanCaTrustedForIngress": page_http.get("status") is not None,
    }
    value = {
        "image": deployment["spec"]["template"]["spec"]["containers"][0]["image"],
        "verifiedPod": pod_name,
        "selectionReasons": selection_reasons,
        "restarts": restarts,
        "dashboardRoutes": route_list,
        "apiCertificatesPath": api_dir.strip(),
        "http": {"api": api_http, "page": page_http},
        "checks": checks,
        "passed": all(checks.values()),
    }
    if args.receipt:
        with args.receipt.open("x") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
    print(json.dumps(value, indent=2))
    return 0 if value["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
