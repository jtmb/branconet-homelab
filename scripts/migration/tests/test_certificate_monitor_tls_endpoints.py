import datetime as dt
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from certificate_monitor import CertificateMonitor, normalize_tls_endpoint
from certificate_monitor_tls_probe import probe_tls_expiry, ProbeError

NOW = dt.datetime(2026, 11, 16, 12, tzinfo=dt.timezone.utc)


def healthy(*_args):
    return {"notAfter": "2027-06-01T00:00:00Z"}


def warning_soon(*_args):
    return {"notAfter": (NOW + dt.timedelta(days=10)).isoformat()}


def expired(*_args):
    return {"notAfter": (NOW - dt.timedelta(days=1)).isoformat()}


def unreachable(*_args):
    raise RuntimeError("connection refused")


class NormalizeTlsEndpointTests(unittest.TestCase):
    def test_rejects_shapes_outside_the_fixed_single_field_contract(self):
        for bad in [{}, {"notAfter": "2027-01-01T00:00:00Z", "extra": 1}, {"other": "x"}, "not-a-dict",
                    {"notAfter": "not-a-date"}, {"notAfter": 123}]:
            with self.assertRaises(ValueError):
                normalize_tls_endpoint("node01:apiserver", bad, NOW)

    def test_classifies_healthy_warning_and_expired_from_notAfter_alone(self):
        self.assertEqual(normalize_tls_endpoint("n", {"notAfter": "2027-06-01T00:00:00Z"}, NOW)["state"], "healthy")
        self.assertEqual(normalize_tls_endpoint("n", {"notAfter": (NOW + dt.timedelta(days=10)).isoformat()}, NOW,
                                                 expiry_warning_days=30)["state"], "warning")
        self.assertEqual(normalize_tls_endpoint("n", {"notAfter": (NOW - dt.timedelta(days=1)).isoformat()}, NOW)["state"],
                         "expired")


class ScanTlsEndpointsTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.monitor = CertificateMonitor(self.db)

    def test_healthy_endpoint_produces_no_alert(self):
        result = self.monitor.scan_tls_endpoints(healthy, [("node01:apiserver", ())], NOW)
        self.assertEqual(result["state"], "complete")
        self.assertEqual(self.monitor.snapshot(NOW)["notificationsPending"], 0)
        self.assertEqual(self.monitor.snapshot(NOW)["observations"][0]["resource"], "tls-endpoint")

    def test_warning_and_expired_each_produce_exactly_one_alert_and_dedupe_on_rescan(self):
        self.monitor.scan_tls_endpoints(warning_soon, [("node01:kubelet", ())], NOW, expiry_warning_days=30)
        self.assertEqual(self.monitor.snapshot(NOW)["notificationsPending"], 1)
        self.monitor.scan_tls_endpoints(warning_soon, [("node01:kubelet", ())], NOW + dt.timedelta(minutes=5),
                                        expiry_warning_days=30)
        self.assertEqual(self.monitor.snapshot(NOW)["notificationsPending"], 1, "no duplicate alert for same state")
        self.monitor.scan_tls_endpoints(expired, [("node01:kubelet", ())], NOW + dt.timedelta(minutes=10))
        self.assertEqual(self.monitor.snapshot(NOW)["notificationsPending"], 2, "state change produces a new alert")

    def test_unreachable_endpoint_is_an_unavailable_alert_not_a_crash(self):
        result = self.monitor.scan_tls_endpoints(unreachable, [("node03:apiserver", ())], NOW)
        self.assertEqual(result["state"], "partial")
        self.assertEqual(result["unavailable"], ["node03:apiserver"])
        self.assertEqual(self.monitor.snapshot(NOW)["notificationsPending"], 1)

    def test_recovery_from_unavailable_to_healthy_does_not_alert_again(self):
        self.monitor.scan_tls_endpoints(unreachable, [("node02:kubelet", ())], NOW)
        self.monitor.scan_tls_endpoints(healthy, [("node02:kubelet", ())], NOW + dt.timedelta(minutes=5))
        self.assertEqual(self.monitor.snapshot(NOW)["notificationsPending"], 1, "only the original unavailable alert")

    def test_independent_endpoints_do_not_interfere(self):
        self.monitor.scan_tls_endpoints(healthy, [("node01:apiserver", ()), ("node01:kubelet", ())], NOW)
        self.monitor.scan_tls_endpoints(expired, [("node01:apiserver", ()), ("node01:kubelet", ())],
                                        NOW + dt.timedelta(minutes=5))
        self.assertEqual(self.monitor.snapshot(NOW)["notificationsPending"], 2)


class ProbeTlsExpiryTests(unittest.TestCase):
    def test_rejects_invalid_host_and_port_before_connecting(self):
        with self.assertRaises(ProbeError):
            probe_tls_expiry("not a host!", 443)
        with self.assertRaises(ProbeError):
            probe_tls_expiry("node01", 0)
        with self.assertRaises(ProbeError):
            probe_tls_expiry("node01", 70000)

    def test_unreachable_port_raises_fixed_code_not_backend_detail(self):
        with self.assertRaises(ProbeError) as ctx:
            probe_tls_expiry("127.0.0.1", 1, timeout=1)
        self.assertEqual(str(ctx.exception), "tls_probe_unreachable")


if __name__ == "__main__":
    unittest.main()
