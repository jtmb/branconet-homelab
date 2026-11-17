"""Fixed ConfigMap policy/observation channel; no Secret or CSR mutations."""
import datetime as dt
import json

NAMESPACE = "bortus"
POLICY_NAME = "bortus-certificate-policy"
OBSERVATIONS_NAME = "bortus-certificate-observations"


def config_map(value, name):
    if not isinstance(value, dict) or value.get("kind") != "ConfigMap":
        raise ValueError("control_config_invalid")
    metadata = value.get("metadata", {})
    if metadata.get("name") != name or metadata.get("namespace") != NAMESPACE:
        raise ValueError("control_identity_mismatch")
    if not all(isinstance(metadata.get(field), str) and 0 < len(metadata[field]) <= 512 for field in ("uid", "resourceVersion")):
        raise ValueError("control_identity_invalid")
    if not isinstance(value.get("data"), dict):
        raise ValueError("control_data_invalid")
    return metadata, value["data"]


def policy_view(value):
    metadata, data = config_map(value, POLICY_NAME)
    raw = data.get("policy.json")
    if not isinstance(raw, str) or len(raw) > 4096:
        raise ValueError("policy_size_invalid")
    policy = json.loads(raw)
    if (not isinstance(policy, dict) or
            set(policy) != {"version", "mode", "scanIntervalSeconds", "expiryWarningDays"} or
            type(policy["version"]) is not int or policy["version"] != 1 or
            policy["mode"] not in ("paused", "monitor") or
            type(policy["scanIntervalSeconds"]) is not int or not 60 <= policy["scanIntervalSeconds"] <= 900 or
            type(policy["expiryWarningDays"]) is not int or not 1 <= policy["expiryWarningDays"] <= 30):
        raise ValueError("policy_invalid")
    return {"uid": metadata["uid"], "revision": metadata["resourceVersion"], "desired": policy}


def control_cycle(monitor, read_resource, get_map, patch_map, now=None, probe=None, endpoints=()):
    """Acknowledge effective policy only through a CAS-published snapshot.

    get_map/patch_map are restricted by the runner to the two fixed resources.
    Durable local run history is committed before publishing. A failed publish
    does not repeat a recent scan, and cannot produce a false fresh heartbeat.

    probe/endpoints are optional: when supplied, kubeadm/kubelet serving
    certificate expiry is watched on the same cadence and threshold as
    cert-manager Certificates, via a live TLS handshake only (see
    certificate_monitor_tls_probe.py). Omitting them changes nothing.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    view = policy_view(get_map(POLICY_NAME))
    policy = view["desired"]
    previous = monitor.db.execute("SELECT uid, revision FROM certificate_monitor_policy WHERE singleton=1").fetchone()
    snapshot = monitor.snapshot(now)
    run = snapshot["lastRun"]
    age = float("inf")
    if run:
        try:
            age = (now - dt.datetime.fromisoformat(run["startedAt"].replace("Z", "+00:00"))).total_seconds()
        except ValueError:
            pass
    if policy["mode"] == "monitor" and (
            previous != (view["uid"], view["revision"]) or
            not run or run["state"] == "interrupted" or
            not 0 <= age < policy["scanIntervalSeconds"]):
        monitor.scan(read_resource, now, expiry_warning_days=policy["expiryWarningDays"])
        if probe is not None and endpoints:
            monitor.scan_tls_endpoints(probe, endpoints, now, expiry_warning_days=policy["expiryWarningDays"])
    with monitor.db:
        monitor.db.execute("INSERT OR REPLACE INTO certificate_monitor_policy VALUES (1, ?, ?, ?)",
                           (view["uid"], view["revision"], json.dumps(policy, sort_keys=True)))
    # Do not acknowledge a revision that changed while inventory was being read.
    current = policy_view(get_map(POLICY_NAME))
    if (current["uid"], current["revision"]) != (view["uid"], view["revision"]):
        raise ValueError("policy_changed_during_scan")
    metadata, _ = config_map(get_map(OBSERVATIONS_NAME), OBSERVATIONS_NAME)
    snapshot = monitor.snapshot(now)
    snapshot.update(version=1, heartbeatAt=now.isoformat(), mode=policy["mode"],
                    policy={"uid": view["uid"], "revision": view["revision"]})
    payload = json.dumps(snapshot, separators=(",", ":"))
    if len(payload.encode()) > 512 * 1024:
        raise ValueError("snapshot_too_large")
    patch = [
        {"op": "test", "path": "/metadata/uid", "value": metadata["uid"]},
        {"op": "test", "path": "/metadata/resourceVersion", "value": metadata["resourceVersion"]},
        {"op": "add", "path": "/data/snapshot.json", "value": payload},
    ]
    patch_map(OBSERVATIONS_NAME, patch)
    return {"policyRevision": view["revision"], "mode": policy["mode"],
            "runState": snapshot["lastRun"]["state"] if snapshot["lastRun"] else "not-run"}
