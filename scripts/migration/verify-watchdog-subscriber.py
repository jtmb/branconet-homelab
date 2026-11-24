#!/usr/bin/env python3
"""Read-only authenticated receipt check for the watchdog health topic."""
import base64
import http.client
import importlib.util
import json
from pathlib import Path
import ssl

SPEC = importlib.util.spec_from_file_location(
    "watchdog_receipt_api", Path(__file__).with_name("stage-ntfy-cluster.py"))
API = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(API)
WORK = API.STAGE / "watchdog-host-activation"
TOPIC = "bortus-monitor-health"


def main():
    missed = dict(zip(("id", "resource", "uid", "state", "createdAt"),
                      json.loads((WORK / "detector-missed-event.json").read_text())["event"][:5]))
    recovered = dict(zip(("id", "resource", "uid", "state", "createdAt"),
                         json.loads((WORK / "detector-recovered-event.json").read_text())["recoveredEvent"][:5]))
    auth = API.call(["get", "secret", "private-ntfy-auth", "-n", "bortus-notifications",
                     "-o", "json"])
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
        connection.request("GET", f"/{TOPIC}/json?poll=1&since=all",
                           headers={"Authorization": "Bearer " + token})
        response = connection.getresponse()
        assert response.status == 200, "subscriber_not_authorized"
        raw = response.read(1024 * 1024 + 1)
        assert len(raw) <= 1024 * 1024, "subscriber_response_limit"
        found = {}
        for line in raw.splitlines():
            row = json.loads(line)
            if row.get("event") != "message" or row.get("topic") != TOPIC:
                continue
            try:
                message = json.loads(row.get("message", ""))
            except (ValueError, TypeError):
                continue
            if not isinstance(message, dict):
                continue
            for name, expected in (("missed", missed), ("recovered", recovered)):
                if message == expected:
                    found.setdefault(name, []).append({"ntfyID": row["id"], "time": row["time"]})
        assert set(found) == {"missed", "recovered"}, "watchdog_events_not_received"
        with (WORK / "watchdog-subscriber-receipt.json").open("x") as stream:
            json.dump({
                "passed": True, "authenticatedNativeSubscriber": True,
                "trustedNormalDNS_HTTPS": True, "topic": TOPIC,
                "received": found,
                "observedCopies": {k: len(v) for k, v in found.items()},
                "atLeastOnceNotExactlyOnce": True,
                "humanReceiptVerified": False,
                "noPublishOrCredentialPersistence": True}, stream, indent=2)
            stream.write("\n")
        print(json.dumps({"watchdogSubscriberReceipt": "PASS",
                          "observedCopies": {k: len(v) for k, v in found.items()},
                          "humanReceiptVerified": False}, indent=2))
    finally:
        connection.close()
        token = auth = raw = None


if __name__ == "__main__":
    main()
