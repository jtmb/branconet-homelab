#!/usr/bin/env python3
"""Create bounded isolated fixture with real cert-manager/Longhorn, not production."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import yaml

from certificate_monitor_process import run_bounded
from ntfy_cluster_fixture import NAMESPACE, EDGE, DENIED, LABEL, OWNER, objects, resource
from ntfy_acl_contract import USERS, validate_material

ROOT = Path(__file__).resolve().parents[2]
STAGE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/certificates-qualification-20261116")
WORK = STAGE / "ntfy-cluster-qualification"
BASE = ["/home/brajam/.local/share/branconet-migration/bin/kubectl", "--kubeconfig",
        "/home/brajam/.local/share/branconet-migration/admin.conf", "--request-timeout=15s"]


def call(args, obj=None, limit=2 * 1024**2):
    raw = run_bounded(BASE + args, data=json.dumps(obj).encode() if obj is not None else None,
                      output_limit=limit, timeout=25)
    return json.loads(raw) if raw.strip() else None


def metadata(obj):
    return {k: obj["metadata"].get(k) for k in ("name", "namespace", "uid", "resourceVersion")}


def save(name, value):
    with (WORK / name).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume-after-validation", action="store_true")
    resume = parser.parse_args().resume_after_validation
    assert not WORK.exists() or resume, "reconcile_existing_cluster_fixture"
    if resume:
        assert (WORK / "stage-failure.json").is_file() and not (WORK / "stage-result.json").exists()
        failure = json.loads((WORK / "deployment-validation-failure.json").read_text())
        assert "activeDeadlineSeconds" in failure["publicDeploymentValidationError"]
    assert json.loads((STAGE / "delivery-authority.json").read_text())["executeSettledPlan"]
    publication = json.loads((STAGE / "ntfy-zlib-fixed/publication-result.json").read_text())
    assert publication["state"] == "published-private-verified"
    assert json.loads((STAGE / "ntfy-zlib-fixed/preload-result.json").read_text())["passed"]
    if not resume:
        for n in (NAMESPACE, EDGE, DENIED):
            assert not call(["get", "namespaces", "--field-selector", "metadata.name=" + n, "-o", "json"])["items"]
    disks = call(["get", "nodes.longhorn.io", "-n", "longhorn-system", "-o", "json"])
    eligible = []
    for node in disks["items"]:
        for disk in node.get("status", {}).get("diskStatus", {}).values():
            if node["spec"].get("allowScheduling") and disk["storageAvailable"] > (
                    disk["storageMaximum"] * .25 + 1024**3 + 64 * 1024**2):
                if any(c["type"] == "Schedulable" and c["status"] == "True" for c in disk["conditions"]):
                    eligible.append(node["metadata"]["name"])
    assert len(set(eligible)) >= 2, "two_healthy_replica_destinations_not_admitted"
    os.umask(0o077)
    if not resume:
        WORK.mkdir(mode=0o700)
        (WORK / "tmp").mkdir()
    preflight = json.loads((STAGE / "ntfy-integration-preparation/preflight-result.json").read_text())
    private = Path("/mnt/c/Users/james/AppData/Local/BORTUS/repos/branconet-charts/flux/private-ntfy/resources.yaml")
    server = next(o for o in yaml.safe_load_all(private.read_text())
                  if o and o["metadata"]["name"] == "private-ntfy-config")["data"]["server.yml"]
    fixture = objects(server, publication["reference"], preflight["traefik"]["image"])
    save("resume-started.json" if resume else "started.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "namespaces": [NAMESPACE, EDGE, DENIED], "owner": OWNER,
        "image": publication["reference"], "eligibleReplicaDestinations": sorted(set(eligible)),
        "resourcePeak": "2Gi replicated test claim, bounded edge/backend/four probes; no production data",
        "deadlineSeconds": 900, "productionMutation": False,
        "sourceSHA256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (
            Path(__file__), Path(__file__).with_name("ntfy_cluster_fixture.py"))}})
    created = json.loads((WORK / "stage-failure.json").read_text())["created"] if resume else []
    for prior in created:
        args = ["get", prior["kind"], prior["name"], "-o", "json"]
        if prior["namespace"]:
            args += ["-n", prior["namespace"]]
        actual = call(args)
        assert actual["metadata"]["uid"] == prior["uid"] and actual["metadata"]["labels"][LABEL] == OWNER

    def create(obj):
        # Intents are durable before requests. Secret responses remain in memory;
        # only identity metadata is written, never values or last-applied data.
        number = len(created)
        suffix = "-resume" if resume else ""
        save(f"create-{number:02d}{suffix}-intent.json", {
            "kind": obj["kind"], "name": obj["metadata"]["name"],
            "namespace": obj["metadata"].get("namespace"), "owner": OWNER})
        reply = call(["create", "-f", "-", "-o", "json"], obj)
        info = {"kind": obj["kind"], **metadata(reply)}
        created.append(info)
        save(f"create-{number:02d}{suffix}-result.json", info)

    try:
        for obj in ([] if resume else fixture[:3]):
            create(obj)
        passwords = [secrets.token_urlsafe(30) for _ in USERS] if not resume else []
        node_code = ("const fs=require('fs'),b=require(" + json.dumps(str(STAGE / "node_modules/bcryptjs")) +
                     ");console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(p=>b.hashSync(p,10))));")
        hashes = json.loads(subprocess.check_output(["node", "-e", node_code],
            input=json.dumps(passwords).encode(), stderr=subprocess.PIPE, timeout=30,
            env={**os.environ, "NODE_DISABLE_COMPILE_CACHE": "1", "TMPDIR": str(WORK / "tmp")})) if not resume else []
        tokens = [secrets.token_urlsafe(22)[:29] for _ in USERS]
        tokens = ["tk_" + token for token in tokens]
        material = {"users": ",".join(f"{u}:{h}:user" for u, h in zip(USERS, hashes)),
                    "tokens": ",".join(f"{u}:{t}" for u, t in zip(USERS, tokens))}
        if not resume:
            validate_material(material)
        # Private short-lived synthetic subscriber material is required by the
        # next phase; do not print or copy into source/argv. Remove at checkpoint.
        if not resume:
            (WORK / "synthetic-client.json").write_text(json.dumps({"tokens": tokens}))
            create(resource("Secret", "ntfy-auth", NAMESPACE, type="Opaque", stringData=material))
        for obj in fixture[3:]:
            if any(old["kind"] == obj["kind"] and old["name"] == obj["metadata"]["name"] and
                   old["namespace"] == obj["metadata"].get("namespace") for old in created):
                continue
            existing = call(["get", obj["kind"], "-n", obj["metadata"]["namespace"],
                             "--field-selector", "metadata.name=" + obj["metadata"]["name"], "-o", "json"])
            assert not existing["items"], "unrecorded_fixture_object_requires_reconciliation"
            create(obj)
        deadline = time.monotonic() + 210
        while time.monotonic() < deadline:
            deploy = call(["get", "pod", "-n", NAMESPACE, "private-ntfy", "-o", "json"])
            edge = call(["get", "pod", "-n", EDGE, "ntfy-edge", "-o", "json"])
            if all(any(c.get("type") == "Ready" and c.get("status") == "True"
                       for c in o.get("status", {}).get("conditions", [])) for o in (deploy, edge)):
                break
            time.sleep(3)
        else:
            raise RuntimeError("fixture_readiness_timeout")
        claim = call(["get", "pvc", "private-ntfy-qualification-cache", "-n", NAMESPACE, "-o", "json"])
        pv = call(["get", "pv", claim["spec"]["volumeName"], "-o", "json"])
        volume = call(["get", "volumes.longhorn.io", pv["spec"]["csi"]["volumeHandle"],
                       "-n", "longhorn-system", "-o", "json"])
        assert pv["spec"]["claimRef"]["uid"] == claim["metadata"]["uid"]
        assert volume["spec"]["encrypted"] and volume["spec"]["numberOfReplicas"] == 2
        assert volume["status"]["robustness"] == "healthy"
        result = {"staged": True, "created": created, "claim": metadata(claim), "pv": metadata(pv),
                  "longhorn": {"name": volume["metadata"]["name"], "uid": volume["metadata"]["uid"],
                    "encrypted": volume["spec"]["encrypted"], "replicas": volume["spec"]["numberOfReplicas"],
                    "robustness": volume["status"]["robustness"]},
                  "productionChanged": False, "next": "Run owned route/policy/rotation/persistence checks before 900s pod deadline",
                  "doNotRecreateOrDeleteRetainedClaim": True}
        save("stage-result.json", result)
        print(json.dumps(result, indent=2))
    except Exception as error:
        save("stage-resume-failure.json" if resume else "stage-failure.json", {"reason": type(error).__name__, "created": created,
                                   "reconcileBeforeRetry": True, "productionChanged": False})
        raise


if __name__ == "__main__":
    main()
