import datetime as dt
import json
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from certificate_monitor import CertificateMonitor
from certificate_monitor_control import control_cycle, policy_view, POLICY_NAME, OBSERVATIONS_NAME

NOW = dt.datetime(2026, 11, 16, 12, tzinfo=dt.timezone.utc)


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.monitor = CertificateMonitor(self.db)
        self.desired = {"version": 1, "mode": "monitor", "scanIntervalSeconds": 300, "expiryWarningDays": 7}
        self.revision = "10"
        self.reads = 0
        self.published = []

    def get(self, name):
        return {"kind": "ConfigMap", "metadata": {"name": name, "namespace": "bortus",
                "uid": name + "-uid", "resourceVersion": self.revision},
                "data": {"policy.json": json.dumps(self.desired)} if name == POLICY_NAME else {}}

    def read(self, resource):
        self.reads += 1
        return {"items": []}

    def publish(self, name, patch):
        self.assertEqual(name, OBSERVATIONS_NAME)
        self.assertEqual(patch[0]["path"], "/metadata/uid")
        self.assertEqual(patch[1]["value"], self.revision)
        self.published.append(json.loads(patch[-1]["value"]))

    def test_pause_acknowledgement_and_resume_respect_operator_policy(self):
        self.desired["mode"] = "paused"
        control_cycle(self.monitor, self.read, self.get, self.publish, NOW)
        self.assertEqual(self.reads, 0)
        self.assertEqual(self.published[-1]["mode"], "paused")
        self.desired["mode"] = "monitor"; self.revision = "11"
        control_cycle(self.monitor, self.read, self.get, self.publish, NOW + dt.timedelta(seconds=60))
        self.assertEqual(self.reads, 2)
        self.assertEqual(self.published[-1]["policy"]["revision"], "11")

    def test_restart_does_not_repeat_recent_scan_but_updates_heartbeat(self):
        control_cycle(self.monitor, self.read, self.get, self.publish, NOW)
        restarted = CertificateMonitor(self.db)
        control_cycle(restarted, self.read, self.get, self.publish, NOW + dt.timedelta(seconds=60))
        self.assertEqual(self.reads, 2)
        self.assertEqual(len(self.published), 2)
        self.assertNotEqual(self.published[0]["heartbeatAt"], self.published[1]["heartbeatAt"])

    def test_policy_drift_during_scan_refuses_acknowledgement(self):
        def changed(resource):
            self.revision = "11"
            return {"items": []}
        with self.assertRaisesRegex(ValueError, "policy_changed_during_scan"):
            control_cycle(self.monitor, changed, self.get, self.publish, NOW)
        self.assertEqual(self.published, [])

    def test_failed_publication_is_not_replayed_as_a_scan(self):
        def failed(name, patch):
            raise RuntimeError("unknown publication outcome")
        with self.assertRaises(RuntimeError):
            control_cycle(self.monitor, self.read, self.get, failed, NOW)
        control_cycle(self.monitor, self.read, self.get, self.publish, NOW + dt.timedelta(seconds=60))
        self.assertEqual(self.reads, 2)

    def test_interrupted_scan_is_replaced_on_restart_without_waiting_for_interval(self):
        control_cycle(self.monitor, self.read, self.get, self.publish, NOW)
        self.db.execute(
            "INSERT INTO certificate_monitor_runs VALUES ('crashed-scan', ?, NULL, 'running')",
            ((NOW + dt.timedelta(seconds=20)).isoformat(),))
        self.db.commit()
        restarted = CertificateMonitor(self.db)
        outcome = control_cycle(restarted, self.read, self.get, self.publish, NOW + dt.timedelta(seconds=60))
        self.assertEqual(self.reads, 4)
        self.assertEqual(outcome["runState"], "complete")
        self.assertEqual(self.published[-1]["lastRun"]["state"], "complete")
        self.assertEqual(self.db.execute(
            "SELECT state FROM certificate_monitor_runs WHERE id='crashed-scan'").fetchone()[0], "interrupted")

    def test_warning_threshold_is_effective_and_invalid_policies_do_not_fall_back(self):
        self.desired["expiryWarningDays"] = 20
        def read(resource):
            if resource.startswith("certificatesigningrequests"):
                return {"items": []}
            return {"items": [{"metadata": {"uid": "c1", "name": "tls", "namespace": "whoami"},
                    "status": {"notAfter": (NOW + dt.timedelta(days=15)).isoformat(),
                               "conditions": [{"type": "Ready", "status": "True"}]}}]}
        control_cycle(self.monitor, read, self.get, self.publish, NOW)
        self.assertEqual(self.published[-1]["observations"][0]["state"], "warning")
        for invalid in ["approve-all", ""]:
            self.desired["mode"] = invalid
            with self.assertRaises(ValueError):
                policy_view(self.get(POLICY_NAME))

    def test_tls_endpoints_share_the_same_cadence_and_warning_threshold_as_the_api_scan(self):
        self.desired["expiryWarningDays"] = 20
        def probe(host, port):
            return {"notAfter": (NOW + dt.timedelta(days=15)).isoformat()}
        control_cycle(self.monitor, self.read, self.get, self.publish, NOW,
                      probe=probe, endpoints=[("node01:apiserver", ("192.168.0.4", 6443))])
        tls_rows = [o for o in self.published[-1]["observations"] if o["resource"] == "tls-endpoint"]
        self.assertEqual(len(tls_rows), 1)
        self.assertEqual(tls_rows[0]["state"], "warning")

    def test_omitting_probe_and_endpoints_changes_nothing(self):
        control_cycle(self.monitor, self.read, self.get, self.publish, NOW)
        self.assertFalse(any(o["resource"] == "tls-endpoint" for o in self.published[-1]["observations"]))


if __name__ == "__main__":
    unittest.main()
