#!/usr/bin/env python3
"""Receive the original host alert, then retire only its exact diagnostic CSR."""
import argparse
import base64
import datetime as dt
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import ssl
import time

SPEC = importlib.util.spec_from_file_location(
    "monitor_notification_api", Path(__file__).with_name("stage-ntfy-cluster.py"))
API = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(API)
WORK = API.STAGE / "monitor-host-activation"
NAME = "bortus-notification-qualification-v1"
UID = "41826f46-7da9-4d4f-b879-6dcb4103901c"
EVENT = "2621e9b0-57d3-4ff0-935f-d29a61151e48"
POLICY = {"version": 1, "mode": "monitor", "scanIntervalSeconds": 300,
          "expiryWarningDays": 7}


def save(name, value):
    with (WORK / name).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def subscriber(uncertain=False):
    if uncertain:
        failure = json.loads((WORK / "sender-diagnostics-native-retry-result.json").read_text())
        assert failure["event"][0] == EVENT and failure["event"][2] == UID
        row = failure["event"]
    else:
        accepted = json.loads((WORK / "monitor-sender-recovered-result.json").read_text())
        assert accepted["passed"] and accepted["originalEventAcknowledged"][0] == EVENT
        assert accepted["originalEventAcknowledged"][2] == UID
        row = accepted["originalEventAcknowledged"]
    expected = dict(zip(("id", "resource", "uid", "state", "createdAt"),
                        row[:5]))
    auth = API.call(["get", "secret", "private-ntfy-auth", "-n",
                     "bortus-notifications", "-o", "json"])
    assert auth["metadata"]["uid"] == "29ce9801-a320-4352-b7ef-6808c8df3887"
    token = base64.b64decode(auth["data"]["subscriber-token"], validate=True).decode()
    ca = base64.b64decode(API.run_bounded(API.BASE + [
        "get", "secret", "private-ntfy-tls", "-n", "bortus-notifications",
        "-o", r"jsonpath={.data.ca\.crt}"], output_limit=16384, timeout=20))
    context = ssl.create_default_context(cadata=ca.decode())
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    connection = http.client.HTTPSConnection(
        "notifications.branconet.lan", 443, context=context, timeout=8)
    try:
        connection.request("GET", "/bortus-certificates/json?poll=1&since=all",
                           headers={"Authorization": "Bearer " + token})
        response = connection.getresponse()
        assert response.status == 200, "subscriber_not_authorized"
        payload = response.read(1024 * 1024 + 1)
        assert len(payload) <= 1024 * 1024, "subscriber_response_limit"
        received = []
        for line in payload.splitlines():
            row = json.loads(line)
            if row.get("event") != "message":
                continue
            try:
                message = json.loads(row.get("message", ""))
            except (ValueError, TypeError):
                continue
            if isinstance(message, dict) and message.get("id") == EVENT:
                assert row["topic"] == "bortus-certificates" and message == expected
                received.append({"ntfyID": row["id"], "time": row["time"]})
        if not uncertain:
            assert received, "original_event_not_received"
        save("native-subscriber-uncertainty-result.json" if uncertain else "native-subscriber-result.json", {
            "passed": bool(received), "authenticatedNativeSubscriber": True,
            "trustedNormalDNS_HTTPS": True, "event": expected,
            "receivedMessages": received, "observedCopies": len(received),
            "duplicateCopies": max(0, len(received) - 1),
            "atLeastOnceNotExactlyOnce": True, "humanReceiptVerified": False,
            "diagnosticOnlyNotCSRRetirementAuthority": uncertain,
            "noPublishOrCredentialPersistence": True})
        print(json.dumps({"subscriberReceipt": "PASS" if received else "not observed", "eventID": EVENT,
                          "csrUID": UID, "observedCopies": len(received),
                          "humanReceiptVerified": False}, indent=2))
    finally:
        connection.close()
        token = auth = payload = None


def retire_refresh():
    assert json.loads((WORK / "native-subscriber-result.json").read_text())["passed"]
    obj = API.call(["get", "certificatesigningrequest", NAME, "-o", "json"])
    assert obj["metadata"]["uid"] == UID
    assert obj["metadata"]["labels"]["bortus.jtmb.cc/qualification"] == "monitor-notifications-v1"
    assert not obj["metadata"].get("ownerReferences") and not obj["metadata"].get("finalizers")
    assert obj["spec"]["signerName"] == "qualification.bortus.jtmb.cc/notifications"
    assert obj["spec"]["usages"] == ["digital signature"]
    intent = json.loads((WORK / "native-alert-intent.json").read_text())
    assert hashlib.sha256(base64.b64decode(obj["spec"]["request"])).hexdigest() == intent["publicCSR_SHA256"]
    assert not obj.get("status", {}).get("certificate")
    assert not obj.get("status", {}).get("conditions"), "unexpected_CSR_lifecycle_state"
    pin = API.metadata(obj)
    save("diagnostic-csr-retirement-intent.json", {
        "exactObject": pin, "syntheticKeyDiscarded": True,
        "noApprovalIssuanceOwnersOrFinalizers": True, "subscriberConsumerComplete": True,
        "deletePreconditions": ["uid", "resourceVersion"]})
    result = API.call(["delete", "--raw=/apis/certificates.k8s.io/v1/"
                       "certificatesigningrequests/" + NAME, "-f", "-"], {
        "apiVersion": "v1", "kind": "DeleteOptions",
        "preconditions": {"uid": UID, "resourceVersion": pin["resourceVersion"]}})
    assert not API.call(["get", "certificatesigningrequests",
                         "--field-selector", "metadata.name=" + NAME, "-o", "json"])["items"]
    save("diagnostic-csr-retirement-result.json", {
        "passed": True, "removed": pin, "freshUIDAndResourceVersionGuard": True,
        "deleteResponseKind": result["kind"], "exactNameAbsent": True,
        "productionCertificatesSecretsAndDataUnchanged": True})
    # A same-policy audited CAS requests a fresh scan without changing the
    # accepted thresholds or normal interval, or touching the durable outbox.
    cm = API.call(["get", "configmap", "bortus-certificate-policy", "-n", "bortus", "-o", "json"])
    assert cm["metadata"]["uid"] == "e3ba9899-ec24-45a5-9a47-5e9f72a853ed"
    assert json.loads(cm["data"]["policy.json"]) == POLICY
    audit = json.loads(cm["data"]["audit.json"])
    audit.append({"actor": "operator:notification-qualification-cleanup",
                  "at": dt.datetime.now(dt.timezone.utc).isoformat(),
                  "previousRevision": cm["metadata"]["resourceVersion"],
                  "policy": POLICY})
    updated = API.call(["patch", "configmap", "bortus-certificate-policy", "-n", "bortus",
                        "--type=json", "--patch-file=/dev/stdin", "-o", "json"], [
        {"op": "test", "path": "/metadata/uid", "value": cm["metadata"]["uid"]},
        {"op": "test", "path": "/metadata/resourceVersion", "value": cm["metadata"]["resourceVersion"]},
        {"op": "test", "path": "/data/policy.json", "value": cm["data"]["policy.json"]},
        {"op": "replace", "path": "/data/audit.json",
         "value": json.dumps(audit[-50:], separators=(",", ":"))}])
    save("cleanup-policy-refresh-result.json", {
        "passed": True, "policy": API.metadata(updated), "desired": POLICY,
        "auditOnlyCAS": True, "freshCompleteInventoryStillRequired": True})
    print(json.dumps({"exactDiagnosticCSRRetired": True, "uid": UID,
                      "auditedRefreshCAS": "PASS", "policyUnchanged": POLICY}, indent=2))


def fresh_inventory():
    from certificate_monitor import RESOURCES, normalize
    refresh = json.loads((WORK / "cleanup-policy-refresh-result.json").read_text())
    assert refresh["passed"]
    expected = {"uid": refresh["policy"]["uid"], "revision": refresh["policy"]["resourceVersion"]}
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        obj = API.call(["get", "configmap", "bortus-certificate-observations",
                        "-n", "bortus", "-o", "json"])
        assert obj["metadata"]["uid"] == "64476136-f3c9-44f0-9619-f0eaf3e1af47"
        snapshot = json.loads(obj["data"]["snapshot.json"])
        if snapshot.get("policy") == expected and snapshot.get("lastRun", {}).get("state") == "complete":
            break
        time.sleep(2)
    else:
        raise RuntimeError("fresh_inventory_ack_timeout")
    now = dt.datetime.now(dt.timezone.utc)
    assert snapshot["mode"] == "monitor"
    assert 0 <= (now - dt.datetime.fromisoformat(snapshot["heartbeatAt"])).total_seconds() < 90
    assert len(snapshot["sources"]) == 2 and all(
        source["available"] and not source["stale"] for source in snapshot["sources"])
    actual, counts = [], {}
    for resource in RESOURCES:
        value = API.call(["get", resource, "-A", "-o", "json"])
        records = normalize(resource, value, now, POLICY["expiryWarningDays"])
        actual.extend(records)
        counts[resource] = len(records)
    comparison = lambda records: sorted((row["resource"], row["uid"], row["state"]) for row in records)
    assert comparison(snapshot["observations"]) == comparison(actual), "operator_inventory_drift"
    assert not any(row["uid"] == UID for row in actual + snapshot["observations"])
    assert counts[RESOURCES[1]] == 0, "new_current_CSR_requires_separate_review"
    assert all(row["state"] == "healthy" for row in actual)
    cm = API.call(["get", "configmap", "bortus-certificate-policy", "-n", "bortus", "-o", "json"])
    assert cm["metadata"]["uid"] == expected["uid"] and cm["metadata"]["resourceVersion"] == expected["revision"]
    assert json.loads(cm["data"]["policy.json"]) == POLICY
    save("fresh-inventory-result.json", {
        "passed": True, "policy": expected, "desiredPolicyUnchanged": POLICY,
        "freshCompleteRun": snapshot["lastRun"], "heartbeatAt": snapshot["heartbeatAt"],
        "sources": snapshot["sources"], "operatorReadCounts": counts,
        "observedUIDsAndStatesMatchActualInventory": True,
        "allCurrentCertificatesHealthy": True, "currentCSRs": 0,
        "diagnosticCSRAbsent": True, "notificationsPending": snapshot["notificationsPending"],
        "staticUIDeliveryLabelsNotReleaseQualified": True,
        "noServiceRestartOrPolicyChange": True})
    print(json.dumps({"freshInventory": "PASS", "operatorReadCounts": counts,
                      "diagnosticCSRAbsent": True, "currentCSRs": 0,
                      "notificationsPending": snapshot["notificationsPending"]}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["subscriber", "subscriber-diagnose", "retire-refresh",
                                        "fresh-inventory"])
    phase = parser.parse_args().phase
    save("finish-" + phase + "-started.json", {
        "sourceSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reconcileBeforeRetry": True})
    if phase in ("subscriber", "subscriber-diagnose"):
        subscriber(uncertain=phase == "subscriber-diagnose")
    elif phase == "retire-refresh":
        retire_refresh()
    else:
        fresh_inventory()


if __name__ == "__main__":
    main()
