#!/usr/bin/env python3
"""Phase-specific live controller qualification; no production objects."""
import argparse
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time
import yaml

from certificate_monitor_process import run_bounded, MonitorProcessError
from ntfy_cluster_fixture import NAMESPACE, EDGE, LABEL, OWNER, NAME, objects, resource
from ntfy_rotation_fixture import ACCOUNT, SOURCE, identity, job, cron

spec = importlib.util.spec_from_file_location("rotation_stage_transport", Path(__file__).with_name("stage-ntfy-cluster.py"))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
ROOT, STAGE, call, metadata = base.ROOT, base.STAGE, base.call, base.metadata
WORK = STAGE / "ntfy-controller-qualification"
OLD = STAGE / "ntfy-cluster-qualification"


def save(name, value):
    with (WORK / name).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def own(obj):
    assert obj["metadata"]["labels"].get(LABEL) == OWNER
    return obj


def create(obj, receipt):
    ns = obj["metadata"].get("namespace")
    query = ["get", obj["kind"], "--field-selector", "metadata.name=" + obj["metadata"]["name"], "-o", "json"]
    if ns:
        query += ["-n", ns]
    assert not call(query)["items"], "existing_unreconciled_rotation_object"
    save(receipt + "-intent.json", {"kind": obj["kind"], **metadata(obj)})
    reply = call(["create", "-f", "-", "-o", "json"], obj)
    save(receipt + "-created.json", {"kind": obj["kind"], **metadata(reply)})
    return reply


def patch(kind, name, obj, changes):
    own(obj)
    return call(["patch", kind, name, "-n", NAMESPACE, "--type=json",
                 "--patch-file=/dev/stdin", "-o", "json"], [
        {"op": "test", "path": "/metadata/uid", "value": obj["metadata"]["uid"]},
        {"op": "test", "path": "/metadata/resourceVersion", "value": obj["metadata"]["resourceVersion"]},
        *changes])


def await_ready():
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        deploy = own(call(["get", "deployment", "private-ntfy", "-n", NAMESPACE, "-o", "json"]))
        edge = own(call(["get", "pod", "ntfy-edge", "-n", EDGE, "-o", "json"]))
        if deploy.get("status", {}).get("readyReplicas") == 1 and any(
                c.get("type") == "Ready" and c.get("status") == "True"
                for c in edge.get("status", {}).get("conditions", [])):
            return deploy
        time.sleep(2)
    raise RuntimeError("rotation_fixture_readiness_timeout")


def run_job(name, script="controller.mjs"):
    obj = create(job(name, script), name)
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        current = own(call(["get", "job", name, "-n", NAMESPACE, "-o", "json"]))
        if current.get("status", {}).get("succeeded") or current.get("status", {}).get("failed"):
            break
        time.sleep(1)
    else:
        raise RuntimeError("rotation_job_timeout")
    raw = run_bounded(base.BASE + ["logs", "-n", NAMESPACE, "job/" + name],
                      output_limit=65536, timeout=20)
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    assert len(rows) == 1
    result = {"job": metadata(obj), "status": current.get("status"), "observation": rows[0]}
    save(name + "-result.json", result)
    assert current.get("status", {}).get("succeeded") == 1, "rotation_job_failed_preserve_metadata"
    return result


def public_uid():
    raw = run_bounded(base.BASE + ["get", "secret", "synthetic-leaf", "-n", NAMESPACE,
                      "-o", "jsonpath={.metadata.uid}"], output_limit=1024, timeout=20)
    return raw.decode()


def refresh_source(extra=None):
    source = own(call(["get", "configmap", SOURCE, "-n", NAMESPACE, "-o", "json"]))
    data = dict(source["data"])
    data.update({p.name: p.read_text() for p in (ROOT / "automation/certificate-rotation").glob("*.mjs")
                 if not p.name.endswith(".test.mjs")})
    if extra:
        data.update(extra)
    return patch("configmap", SOURCE, source, [{"op": "replace", "path": "/data", "value": data}])


def backend_pod():
    items = call(["get", "pods", "-n", NAMESPACE, "-l", "app=ntfy-qualification", "-o", "json"])["items"]
    current = [o for o in items if not o["metadata"].get("deletionTimestamp")
               and o.get("status", {}).get("phase") == "Running"]
    assert len(current) == 1
    return own(current[0])


def public_leaf():
    import base64
    raw = run_bounded(base.BASE + ["get", "secret", "synthetic-leaf", "-n", NAMESPACE,
                      "-o", r"jsonpath={.data.tls\.crt}"], output_limit=16384, timeout=20)
    return base64.b64decode(raw)


def leaf_sha(pem):
    import ssl
    text = pem.decode()
    first = text[:text.index("-----END CERTIFICATE-----") + len("-----END CERTIFICATE-----")]
    return hashlib.sha256(ssl.PEM_cert_to_DER_cert(first)).hexdigest()


def reissue(names, phase):
    cert = own(call(["get", "certificate", "synthetic-leaf", "-n", NAMESPACE, "-o", "json"]))
    revision = cert["status"]["revision"]
    before = backend_pod()
    patch("certificate", "synthetic-leaf", cert,
          [{"op": "replace", "path": "/spec/dnsNames", "value": names}])
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        current = own(call(["get", "certificate", "synthetic-leaf", "-n", NAMESPACE, "-o", "json"]))
        if current.get("status", {}).get("revision", 0) > revision:
            pem = public_leaf()
            projected = run_bounded(base.BASE + ["exec", "-n", NAMESPACE,
                before["metadata"]["name"], "--", "cat", "/tls/tls.crt"], output_limit=16384, timeout=20)
            if leaf_sha(pem) == leaf_sha(projected):
                result = {"revision": current["status"]["revision"], "fingerprint": leaf_sha(pem),
                          "podUIDBeforeRollout": before["metadata"]["uid"],
                          "certificateUID": current["metadata"]["uid"]}
                save(phase + "-issued-projected.json", result)
                return result
        time.sleep(2)
    raise RuntimeError("controller_fixture_reissue_projection_timeout")


def wait_replacement(old_uid):
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        try:
            obj = backend_pod()
            if obj["metadata"]["uid"] != old_uid and any(
                    c.get("type") == "Ready" and c.get("status") == "True"
                    for c in obj.get("status", {}).get("conditions", [])):
                return obj
        except AssertionError:
            pass
        time.sleep(2)
    raise RuntimeError("controller_rollout_readiness_timeout")


def stage():
    assert not WORK.exists(), "reconcile_existing_rotation_stage"
    old = json.loads((OLD / "stage-result.json").read_text())
    for row in old["created"]:
        if row["kind"] in ("Namespace", "Certificate", "ConfigMap", "PersistentVolumeClaim", "Service"):
            args = ["get", row["kind"], row["name"], "-o", "json"]
            if row["namespace"]:
                args += ["-n", row["namespace"]]
            assert own(call(args))["metadata"]["uid"] == row["uid"]
    assert not call(["get", "pods", "-n", NAMESPACE, "-l", LABEL + "=" + OWNER, "-o", "json"])["items"]
    WORK.mkdir(mode=0o700)
    save("started.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": "Narrow controller actual identity, observation, renewal, schedule and interruption against retained fixture",
        "previousFixtureReused": True, "productionChanged": False,
        "sourceSHA256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (ROOT / "automation/certificate-rotation").glob("*.mjs")}})
    # Source-backed projection is public JS plus identity/enrollment metadata.
    data = {p.name: p.read_text() for p in (ROOT / "automation/certificate-rotation").glob("*.mjs")
            if not p.name.endswith(".test.mjs")}
    principal = None
    for index, obj in enumerate(identity()):
        reply = create(obj, "identity-" + str(index))
        if obj["kind"] == "ServiceAccount":
            principal = reply
    data["identity.json"] = json.dumps({"namespace": NAMESPACE, "account": ACCOUNT,
                                      "serviceAccountUID": principal["metadata"]["uid"]})
    # The identity diagnostic does not consume an enrollment document.
    create(resource("ConfigMap", SOURCE, NAMESPACE, data=data), "controller-source")
    identity_result = run_job("rotation-identity", "identity-check.mjs")
    assert identity_result["observation"]["passed"]
    save("identity-result.json", identity_result)
    print(json.dumps(identity_result, indent=2))


def observe():
    assert (WORK / "identity-result.json").exists() and not (WORK / "observe-started.json").exists()
    save("observe-started.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "productionChanged": False})
    publication = json.loads((STAGE / "ntfy-zlib-fixed/publication-result.json").read_text())
    preflight = json.loads((STAGE / "ntfy-integration-preparation/preflight-result.json").read_text())
    cm = own(call(["get", "configmap", "ntfy-config", "-n", NAMESPACE, "-o", "json"]))
    fixture = objects(cm["data"]["server.yml"], publication["reference"], preflight["traefik"]["image"])
    backend = next(o for o in fixture if o["kind"] == "Pod" and o["metadata"]["name"] == "private-ntfy")
    backend["spec"].pop("activeDeadlineSeconds")
    # Deployment is required to qualify the actual rollout adapter. An external
    # bounded driver owns this diagnostic target and teardown; production off.
    deployment = resource("Deployment", "private-ntfy", NAMESPACE, "apps/v1", spec={
        "replicas": 1, "strategy": {"type": "Recreate"},
        "selector": {"matchLabels": {"app": "ntfy-qualification"}},
        "template": {"metadata": {"labels": backend["metadata"]["labels"]}, "spec": backend["spec"]}})
    target = create(deployment, "rotation-backend")
    create(next(o for o in fixture if o["kind"] == "Pod" and o["metadata"]["name"] == "ntfy-edge"), "rotation-edge")
    await_ready()
    cert = own(call(["get", "certificate", "synthetic-leaf", "-n", NAMESPACE, "-o", "json"]))
    edge_service = own(call(["get", "service", "ntfy-edge", "-n", EDGE, "-o", "json"]))
    # Public CA only; no private key is fetched by this controller/enrollment.
    import ssl
    ca = run_bounded(base.BASE + ["get", "secret", "synthetic-leaf", "-n", NAMESPACE,
                     "-o", r"jsonpath={.data.ca\.crt}"], output_limit=16384, timeout=20)
    import base64
    ca_der = ssl.PEM_cert_to_DER_cert(base64.b64decode(ca).decode())
    enrollment = {"mode": "observe", "namespace": NAMESPACE, "certificateName": "synthetic-leaf",
        "secretName": "synthetic-leaf", "deploymentName": "private-ntfy",
        "certificateUID": cert["metadata"]["uid"], "secretUID": public_uid(),
        "deploymentUID": target["metadata"]["uid"], "expectedImage": publication["reference"],
        "caFingerprint": hashlib.sha256(ca_der).hexdigest(),
        "allowedDNS": [NAME, "ntfy-rotation.invalid", "ntfy-controller.invalid", "ntfy-interruption.invalid"],
        "serverName": NAME, "endpointAddress": edge_service["spec"]["clusterIP"]}
    refresh_source({"enrollment.json": json.dumps(enrollment)})
    observed = run_job("rotation-observe-initial")
    assert observed["observation"]["state"] == "verified"
    save("observation-result.json", {"passed": True, "enrollment": enrollment,
                                    "result": observed, "productionChanged": False})
    print(json.dumps(observed, indent=2))


def resume_observe():
    assert not (WORK / "observation-result.json").exists()
    old = json.loads((WORK / "initial-observe-failure.json").read_text())
    assert old["jobStatus"]["succeeded"] == 1 and old["outputBytes"] == 0
    save("observe-symlink-resume-started.json", {"reason": "ConfigMap main symlink detection; no resource/PKI/identity replay",
        "sourceSHA256": hashlib.sha256((ROOT / "automation/certificate-rotation/controller.mjs").read_bytes()).hexdigest()})
    await_ready()
    source = refresh_source()
    enrollment = json.loads(source["data"]["enrollment.json"])
    assert enrollment["mode"] == "observe"
    observed = run_job("rotation-observe-symlink")
    assert observed["observation"]["state"] == "verified"
    save("observation-result.json", {"passed": True, "enrollment": enrollment,
                                    "result": observed, "productionChanged": False,
                                    "initialSilentEntrypointFailurePreserved": True})
    print(json.dumps(observed, indent=2))


def renew(resume=False):
    assert (WORK / "observation-result.json").exists() and not (WORK / "renewal-result.json").exists()
    if resume:
        previous = json.loads((WORK / "renewal-driver-failure.json").read_text())
        assert previous["renewalMutationDispatched"] is False
        assert not (WORK / "renewal-issued-projected.json").exists()
    else:
        assert not (WORK / "renew-started.json").exists()
    save("renew-resume-started.json" if resume else "renew-started.json", {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(), "productionChanged": False,
        "resumeReason": "Correct helper arity before first renewal mutation" if resume else None})
    initial = own(call(["get", "deployment", "private-ntfy", "-n", NAMESPACE, "-o", "json"]))
    projected = reissue([NAME, "ntfy-rotation.invalid", "ntfy-controller.invalid"], "renewal")
    observed = run_job("rotation-observe-renewed")
    assert observed["observation"]["state"] == "observing"
    unchanged = own(call(["get", "deployment", "private-ntfy", "-n", NAMESPACE, "-o", "json"]))
    assert unchanged["metadata"]["generation"] == initial["metadata"]["generation"]
    assert backend_pod()["metadata"]["uid"] == projected["podUIDBeforeRollout"]
    enrollment = json.loads((WORK / "observation-result.json").read_text())["enrollment"]
    enrollment["mode"] = "auto"
    refresh_source({"enrollment.json": json.dumps(enrollment)})
    requested = run_job("rotation-auto-renewal")
    assert requested["observation"]["state"] == "requested"
    assert requested["observation"]["fingerprint"] == projected["fingerprint"]
    replacement = wait_replacement(projected["podUIDBeforeRollout"])
    verified = run_job("rotation-verify-renewal")
    assert verified["observation"]["state"] == "verified"
    assert verified["observation"]["fingerprint"] == projected["fingerprint"]
    final = own(call(["get", "deployment", "private-ntfy", "-n", NAMESPACE, "-o", "json"]))
    assert final["metadata"]["generation"] == initial["metadata"]["generation"] + 1
    save("renewal-result.json", {"passed": True, "observeDidNotMutate": True,
        "singleGuardedRolloutGeneration": final["metadata"]["generation"],
        "oldPodUID": projected["podUIDBeforeRollout"], "newPodUID": replacement["metadata"]["uid"],
        "fingerprint": projected["fingerprint"], "revision": projected["revision"],
        "actualControllerIssuedPatch": True, "actualTrustedEndpointVerified": True, "productionChanged": False})
    print((WORK / "renewal-result.json").read_text())


def interrupt():
    assert (WORK / "renewal-result.json").exists() and not (WORK / "interrupt-started.json").exists()
    save("interrupt-started.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "productionChanged": False})
    projected = reissue([NAME, "ntfy-rotation.invalid", "ntfy-controller.invalid",
                         "ntfy-interruption.invalid"], "interruption")
    obj = create(job("rotation-interruption", "interruption-check.mjs"), "rotation-interruption")
    deadline = time.monotonic() + 50
    while time.monotonic() < deadline:
        try:
            raw = run_bounded(base.BASE + ["logs", "-n", NAMESPACE, "job/rotation-interruption"],
                              output_limit=16384, timeout=10)
            lines = [json.loads(v) for v in raw.splitlines() if v.strip()]
            if any(v.get("qualificationBarrier") == "acknowledged-patch-before-completion" for v in lines):
                break
        except MonitorProcessError:
            pass
        time.sleep(.5)
    else:
        raise RuntimeError("interruption_barrier_not_reached")
    current = own(call(["get", "job", "rotation-interruption", "-n", NAMESPACE, "-o", "json"]))
    patch("job", "rotation-interruption", current,
          [{"op": "add", "path": "/spec/suspend", "value": True}])
    before = own(call(["get", "deployment", "private-ntfy", "-n", NAMESPACE, "-o", "json"]))
    assert before["spec"]["template"]["metadata"]["annotations"][
        "bortus.jtmb.cc/requested-serving-fingerprint"] == projected["fingerprint"]
    stopped_deadline = time.monotonic() + 30
    while time.monotonic() < stopped_deadline:
        pods = call(["get", "pods", "-n", NAMESPACE, "-l", "job-name=rotation-interruption", "-o", "json"])["items"]
        if not pods or all(p.get("status", {}).get("phase") in ("Succeeded", "Failed") for p in pods):
            break
        time.sleep(1)
    else:
        raise RuntimeError("interrupted_worker_not_stopped")
    replacement = wait_replacement(projected["podUIDBeforeRollout"])
    recovered = run_job("rotation-recovery")
    assert recovered["observation"]["state"] == "verified"
    assert recovered["observation"]["fingerprint"] == projected["fingerprint"]
    after = own(call(["get", "deployment", "private-ntfy", "-n", NAMESPACE, "-o", "json"]))
    assert after["metadata"]["generation"] == before["metadata"]["generation"]
    save("interruption-result.json", {"passed": True, "interruptedJob": metadata(obj),
        "barrier": "after acknowledged patch before client completion; not a claimed TCP response-loss test",
        "actualWorkerStopped": True, "recoveryObservedDurableAnnotationAndEndpoint": True,
        "noDuplicateRollout": True, "generation": after["metadata"]["generation"],
        "newPodUID": replacement["metadata"]["uid"], "fingerprint": projected["fingerprint"],
        "productionChanged": False})
    print((WORK / "interruption-result.json").read_text())


def scheduled():
    assert (WORK / "interruption-result.json").exists() and not (WORK / "schedule-started.json").exists()
    obj = create(cron(), "rotation-schedule")
    save("schedule-started.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(),
                                 "cron": metadata(obj), "manualRunsDoNotCount": True})
    patch("cronjob", ACCOUNT, obj, [{"op": "replace", "path": "/spec/suspend", "value": False}])
    observed = {}
    deadline = time.monotonic() + 190
    try:
        while time.monotonic() < deadline:
            jobs = call(["get", "jobs", "-n", NAMESPACE, "-o", "json"])["items"]
            for item in jobs:
                if item["metadata"]["uid"] in observed or item.get("status", {}).get("succeeded") != 1:
                    continue
                if not any(o.get("kind") == "CronJob" and o.get("uid") == obj["metadata"]["uid"]
                           for o in item["metadata"].get("ownerReferences", [])):
                    continue
                raw = run_bounded(base.BASE + ["logs", "-n", NAMESPACE, "job/" + item["metadata"]["name"]],
                                  output_limit=16384, timeout=20)
                result = json.loads(raw)
                assert result["state"] == "verified"
                observed[item["metadata"]["uid"]] = {"job": metadata(item),
                    "scheduledTimestamp": item["metadata"].get("annotations", {}).get(
                        "batch.kubernetes.io/cronjob-scheduled-timestamp"),
                    "startTime": item["status"].get("startTime"), "result": result}
                save("scheduled-observation-" + str(len(observed)) + ".json", observed[item["metadata"]["uid"]])
            if len(observed) >= 2:
                break
            time.sleep(2)
        assert len(observed) >= 2, "two_native_scheduled_executions_not_observed"
        save("schedule-result.json", {"passed": True, "cronUID": obj["metadata"]["uid"],
            "nativeScheduledExecutions": list(observed.values()), "manualStartCounted": False,
            "windowsOrWSLNeededToExecuteCron": False, "productionControllerInstalled": False})
        print((WORK / "schedule-result.json").read_text())
    finally:
        current = own(call(["get", "cronjob", ACCOUNT, "-n", NAMESPACE, "-o", "json"]))
        patch("cronjob", ACCOUNT, current, [{"op": "replace", "path": "/spec/suspend", "value": True}])
        save("schedule-paused.json", {"uid": current["metadata"]["uid"], "qualificationSchedulerSuspended": True})


def cleanup():
    assert (WORK / "schedule-result.json").exists() and (WORK / "schedule-paused.json").exists()
    assert not (WORK / "cleanup-result.json").exists()
    owned = []
    for record in sorted(WORK.glob("*-created.json")):
        obj = json.loads(record.read_text())
        owned.append(obj)
    # Scheduled Jobs are owned through the exact recorded CronJob UID, not
    # adopted from a namespace-wide label.
    schedule = json.loads((WORK / "schedule-result.json").read_text())
    for observed in schedule["nativeScheduledExecutions"]:
        owned.append({"kind": "Job", **observed["job"]})
    unique = {(o["kind"], o["namespace"], o["name"]): o for o in owned}
    cron_obj = own(call(["get", "cronjob", ACCOUNT, "-n", NAMESPACE, "-o", "json"]))
    assert cron_obj["metadata"]["uid"] == schedule["cronUID"] and cron_obj["spec"]["suspend"]
    jobs = call(["get", "jobs", "-n", NAMESPACE, "-o", "json"])["items"]
    for obj in jobs:
        key = ("Job", NAMESPACE, obj["metadata"]["name"])
        if key in unique:
            assert obj["metadata"]["uid"] == unique[key]["uid"]
            assert obj.get("status", {}).get("active", 0) == 0
    save("cleanup-intent.json", {"exactObjects": list(unique.values()),
        "schedulerSuspended": True, "noActiveOwnedJobs": True,
        "retain": "Pre-existing fixture namespaces/PKI/native auth/config/claim; no blanket namespace/PVC deletion"})
    endpoints = {
        "RoleBinding": ("/apis/rbac.authorization.k8s.io/v1", "rolebindings"),
        "Role": ("/apis/rbac.authorization.k8s.io/v1", "roles"),
        "CronJob": ("/apis/batch/v1", "cronjobs"), "Job": ("/apis/batch/v1", "jobs"),
        "Deployment": ("/apis/apps/v1", "deployments"), "Pod": ("/api/v1", "pods"),
        "ServiceAccount": ("/api/v1", "serviceaccounts"), "ConfigMap": ("/api/v1", "configmaps"),
        "NetworkPolicy": ("/apis/networking.k8s.io/v1", "networkpolicies"),
    }
    priority = ["RoleBinding", "CronJob", "Job", "Deployment", "Pod",
                "Role", "ServiceAccount", "ConfigMap", "NetworkPolicy"]
    removed, absent = [], []
    for obj in sorted(unique.values(), key=lambda v: priority.index(v["kind"])):
        items = call(["get", obj["kind"], "-n", obj["namespace"], "--field-selector",
                      "metadata.name=" + obj["name"], "-o", "json"])["items"]
        if not items:
            absent.append(obj)
            continue
        current = own(items[0])
        assert current["metadata"]["uid"] == obj["uid"]
        prefix, plural = endpoints[obj["kind"]]
        call(["delete", "--raw", f"{prefix}/namespaces/{obj['namespace']}/{plural}/{obj['name']}", "-f", "-"],
             {"apiVersion": "v1", "kind": "DeleteOptions", "propagationPolicy": "Foreground",
              "preconditions": {"uid": obj["uid"], "resourceVersion": current["metadata"]["resourceVersion"]}})
        removed.append(obj)
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        active = []
        for ns in (NAMESPACE, EDGE):
            active += call(["get", "pods", "-n", ns, "-l", LABEL + "=" + OWNER, "-o", "json"])["items"]
        if not active:
            break
        time.sleep(2)
    assert not active
    save("cleanup-result.json", {"passed": True, "exactObjectsRemoved": removed,
        "alreadyAbsent": absent, "diagnosticPodsRemaining": 0,
        "qualificationRoleAndSchedulerRemoved": True,
        "preexistingFixturePKINativeAuthClaimAndNamespacesRetained": True,
        "tokenValuesRetainedOutsidePods": False, "immediateServerTokenRevocationClaimed": False,
        "productionChanged": False})
    print((WORK / "cleanup-result.json").read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("identity", "observe", "resume-observe", "renew", "resume-renew", "interrupt", "schedule", "cleanup"))
    phase = parser.parse_args().phase
    os.umask(0o077)
    assert json.loads((STAGE / "delivery-authority.json").read_text())["executeSettledPlan"]
    if phase == "identity":
        stage()
    elif phase == "observe":
        observe()
    elif phase == "resume-observe":
        resume_observe()
    elif phase == "renew":
        renew()
    elif phase == "resume-renew":
        renew(resume=True)
    elif phase == "interrupt":
        interrupt()
    elif phase == "schedule":
        scheduled()
    else:
        cleanup()


if __name__ == "__main__":
    main()
