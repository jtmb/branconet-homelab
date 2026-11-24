import datetime as dt
import json
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from certificate_monitor import CertificateMonitor, RESOURCES, HISTORY_ROWS, MAX_DATABASE_BYTES

NOW = dt.datetime(2026, 11, 16, 12, tzinfo=dt.timezone.utc)


def source(resource):
    if resource == RESOURCES[1]:
        return {"items": []}
    return {"items": [{
        "metadata": {"uid": "cert-uid", "name": "lan-tls", "namespace": "whoami"},
        "spec": {}, "status": {"notAfter": "2026-11-17T00:00:00Z",
                               "conditions": [{"type": "Ready", "status": "True"}]},
        "sensitive_extra": "must-not-persist",
    }]}


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.monitor = CertificateMonitor(self.db)

    def test_scan_is_durable_deduplicates_alerts_and_projects_only_metadata(self):
        self.assertEqual(self.monitor.scan(source, NOW)["state"], "complete")
        self.assertEqual(self.monitor.snapshot(NOW)["notificationsPending"], 1)
        restarted = CertificateMonitor(self.db)
        restarted.scan(source, NOW + dt.timedelta(minutes=5))
        snapshot = restarted.snapshot(NOW + dt.timedelta(minutes=5))
        self.assertEqual(snapshot["notificationsPending"], 1)
        self.assertNotIn("must-not-persist", json.dumps(snapshot))
        self.assertEqual(snapshot["observations"][0]["state"], "warning")
        self.assertTrue(all(not s["stale"] for s in snapshot["sources"]))

    def test_api_loss_preserves_last_observations_but_marks_source_unavailable(self):
        self.monitor.scan(source, NOW)
        def broken(resource):
            raise RuntimeError("private-backend-output")
        self.assertEqual(self.monitor.scan(broken, NOW + dt.timedelta(minutes=1))["state"], "partial")
        self.monitor.scan(broken, NOW + dt.timedelta(minutes=2))
        snapshot = self.monitor.snapshot(NOW + dt.timedelta(minutes=20))
        self.assertEqual(len(snapshot["observations"]), 1)
        self.assertTrue(all(s["stale"] and not s["available"] for s in snapshot["sources"]))
        self.assertEqual(snapshot["notificationsPending"], 3)
        self.assertNotIn("private-backend-output", json.dumps(snapshot))

    def test_successful_empty_source_removes_stale_observations_without_affecting_other_sources(self):
        self.monitor.scan(source, NOW)
        self.monitor.scan(lambda resource: {"items": []}, NOW + dt.timedelta(minutes=1))
        self.assertEqual(self.monitor.snapshot(NOW)["observations"], [])

    def test_interrupted_scan_is_recorded_not_replayed_as_a_mutation(self):
        self.db.execute("INSERT INTO certificate_monitor_runs VALUES ('interrupted-one', ?, NULL, 'running')", (NOW.isoformat(),))
        self.db.commit()
        CertificateMonitor(self.db)
        self.assertEqual(self.db.execute("SELECT state FROM certificate_monitor_runs WHERE id='interrupted-one'").fetchone()[0], "interrupted")

    def test_history_is_finite_without_discarding_pending_notifications(self):
        old = (NOW - dt.timedelta(days=1)).isoformat()
        self.db.executemany("INSERT INTO certificate_monitor_runs VALUES (?, ?, ?, 'complete')",
                            [(f"run-{index}", old, old) for index in range(HISTORY_ROWS + 50)])
        self.db.executemany("INSERT INTO certificate_monitor_outbox VALUES (?, 'fixture', ?, 'warning', ?, ?)",
                            [(f"delivered-{index}", str(index), old, old)
                             for index in range(HISTORY_ROWS + 50)])
        self.db.execute("INSERT INTO certificate_monitor_outbox VALUES ('undelivered', 'fixture', 'pending', 'warning', ?, NULL)", (old,))
        self.db.commit()
        self.monitor.scan(lambda _: {"items": []}, NOW)
        self.assertEqual(self.db.execute("SELECT count(*) FROM certificate_monitor_runs").fetchone()[0], HISTORY_ROWS)
        self.assertEqual(self.db.execute("SELECT count(*) FROM certificate_monitor_outbox WHERE delivered_at IS NOT NULL").fetchone()[0], HISTORY_ROWS)
        self.assertEqual(self.db.execute("SELECT id FROM certificate_monitor_outbox WHERE delivered_at IS NULL").fetchone()[0], "undelivered")

    def test_sqlite_growth_limit_refuses_extra_output_without_losing_existing_state(self):
        self.monitor.scan(source, NOW)
        with self.assertRaises(sqlite3.OperationalError):
            with self.db:
                self.db.execute("CREATE TABLE pressure (payload BLOB)")
                self.db.execute("INSERT INTO pressure VALUES (zeroblob(?))", (MAX_DATABASE_BYTES,))
        self.assertEqual(self.monitor.snapshot(NOW)["notificationsPending"], 1)
        self.assertEqual(len(self.monitor.snapshot(NOW)["observations"]), 1)
        page_size = self.db.execute("PRAGMA page_size").fetchone()[0]
        self.assertLessEqual(self.db.execute("PRAGMA max_page_count").fetchone()[0] * page_size, MAX_DATABASE_BYTES)


if __name__ == "__main__":
    unittest.main()
