"""Synthetic outbox and real loopback HTTPS; no infrastructure or live alerts."""
import datetime as dt
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from certificate_monitor import CertificateMonitor, RESOURCES
from certificate_monitor_notifications import (NotificationError, OutboxDelivery,
                                              event_message, publish_ntfy, validate_destination)

NOW = dt.datetime(2026, 11, 16, 12, tzinfo=dt.timezone.utc)
EVENT = dict(id="fixture-event", resource=RESOURCES[0], uid="fixture-cert",
             state="warning", createdAt=NOW.isoformat())


def seed(db):
    CertificateMonitor(db)
    db.execute("INSERT INTO certificate_monitor_outbox VALUES (?,?,?,?,?,NULL)",
               tuple(EVENT[key] for key in ("id", "resource", "uid", "state", "createdAt")))
    db.commit()


class OutboxTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        seed(self.db)

    def test_failure_stays_pending_and_backoff_survives_new_dispatcher(self):
        calls = []
        def fail(event):
            calls.append(event)
            raise RuntimeError("private-backend-response")
        result = OutboxDelivery(self.db).deliver(fail, NOW)
        self.assertEqual((result["failed"], result["pending"]), (1, 1))
        self.assertNotIn("private-backend", json.dumps(result))
        OutboxDelivery(self.db).deliver(fail, NOW + dt.timedelta(seconds=59))
        self.assertEqual(len(calls), 1)
        OutboxDelivery(self.db).deliver(lambda event: {"accepted": True}, NOW + dt.timedelta(seconds=60))
        self.assertIsNotNone(self.db.execute("SELECT delivered_at FROM certificate_monitor_outbox").fetchone()[0])
        self.assertEqual(self.db.execute("SELECT count(*) FROM certificate_monitor_delivery_retry").fetchone()[0], 0)

    def test_unknown_accepted_outcome_retries_same_event_without_claiming_exactly_once(self):
        calls = []
        def uncertain(event):
            calls.append(event["id"])
            # The server may have accepted it before the reply was lost.
            raise TimeoutError()
        delivery = OutboxDelivery(self.db)
        delivery.deliver(uncertain, NOW)
        def ack(event):
            calls.append(event["id"])
            return {"accepted": True}
        delivery.deliver(ack, NOW + dt.timedelta(minutes=1))
        delivery.deliver(ack, NOW + dt.timedelta(minutes=2))
        self.assertEqual(calls, ["fixture-event", "fixture-event"])

    def test_dispatcher_does_not_interrupt_active_monitor_or_hold_write_lock_during_send(self):
        self.db.execute("INSERT INTO certificate_monitor_runs VALUES ('active',?,NULL,'running')", (NOW.isoformat(),))
        self.db.commit()
        def ack(event):
            self.assertFalse(self.db.in_transaction)
            return {"accepted": True}
        OutboxDelivery(self.db).deliver(ack, NOW)
        self.assertEqual(self.db.execute("SELECT state FROM certificate_monitor_runs").fetchone()[0], "running")

    def test_wrong_ack_and_unbounded_batches_are_refused(self):
        result = OutboxDelivery(self.db).deliver(lambda event: {"accepted": False}, NOW)
        self.assertEqual(result["pending"], 1)
        with self.assertRaises(NotificationError):
            OutboxDelivery(self.db).deliver(lambda event: None, NOW, limit=100)

    def test_tls_endpoint_events_deliver_and_unknown_resources_still_refuse(self):
        # Regression (2026-11-18): scan_tls_endpoints() queues
        # tls-endpoint rows (kubeadm/kubelet serving-certificate expiry), but
        # event_message rejected that resource, so the alert never reached
        # the topic and stayed pending forever behind its retry backoff.
        from certificate_monitor import TLS_ENDPOINT_RESOURCE
        seen = []
        def ack(event):
            seen.append(event)
            return {"accepted": True}
        tls_event = dict(id="tls-fixture-event", resource=TLS_ENDPOINT_RESOURCE,
                         uid="tls-endpoint:node01:apiserver", state="warning",
                         createdAt=NOW.isoformat())
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        CertificateMonitor(db)
        db.execute("INSERT INTO certificate_monitor_outbox VALUES (?,?,?,?,?,NULL)",
                   tuple(tls_event[key] for key in ("id", "resource", "uid", "state", "createdAt")))
        db.commit()
        result = OutboxDelivery(db).deliver(ack, NOW)
        self.assertEqual((result["acceptedByServer"], result["failed"], result["pending"]), (1, 0, 0))
        self.assertEqual(seen[0]["uid"], "tls-endpoint:node01:apiserver")
        self.assertIsNotNone(db.execute("SELECT delivered_at FROM certificate_monitor_outbox").fetchone()[0])
        for bad in ({"resource": "nodes"}, {"resource": "pods"}, {"resource": "tls-endpoints"}):
            with self.subTest(bad=bad), self.assertRaises(NotificationError):
                event_message(tls_event | bad)
        # The Kubernetes resources keep flowing unchanged.
        event_message(dict(id="k", resource=RESOURCES[0], uid="c", state="expired",
                           createdAt=NOW.isoformat()))

    def test_destination_refuses_public_address_plaintext_credentials_redirect_parameters(self):
        base = dict(version=1, url="https://notify.lan/certificates", address="192.168.0.20",
                    caFile="/public-ca", tokenFile="/private-token")
        validate_destination(base)
        for change in ({"address": "1.1.1.1"}, {"url": "http://notify.lan/certificates"},
                       {"url": "https://user:password@notify.lan/certificates"},
                       {"url": "https://notify.lan/certificates?forward=elsewhere"}):
            with self.subTest(change=change), self.assertRaises(NotificationError):
                validate_destination(base | change)


class Receiver(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        raw = self.rfile.read(min(int(self.headers["Content-Length"]), 4096))
        self.server.calls.append({"path": self.path, "body": raw, "authorization": self.headers.get("Authorization")})
        mode = self.server.mode
        if mode in (302, 401, 503):
            self.send_response(mode)
            self.send_header("Location", "https://public.invalid/no-forward")
            self.end_headers()
            return
        result = dict(id="synthetic-ack", event="message", topic=self.path[1:], message=raw.decode())
        if mode == "mismatch":
            result["topic"] = "unrelated"
        body = b"x" * 16385 if mode == "oversize" else json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class HTTPSDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(os.environ["BORTUS_MONITOR_TEST_ROOT"]).resolve()
        from certificate_monitor_runtime import H_ROOT
        if H_ROOT.resolve() not in root.parents:
            raise RuntimeError("H-only test output required")
        root.mkdir(mode=0o700, exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(prefix="notify-https-", dir=root)
        cls.root = Path(cls.temp.name)
        cls.ca, key = cls.root / "ca.crt", cls.root / "key.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                        "-days", "1", "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost",
                        "-keyout", str(key), "-out", str(cls.ca)],
                       check=True, capture_output=True, timeout=15)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(cls.ca, key)
        cls.server.socket = context.wrap_socket(cls.server.socket, server_side=True)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.config = dict(version=1, url=f"https://localhost:{cls.server.server_port}/certificates",
                          address="127.0.0.1", caFile=str(cls.ca), tokenFile=str(cls.root / "token"))
        (cls.root / "token").write_text("synthetic-private-token")
        (cls.root / "token").chmod(0o600)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.temp.cleanup()

    def setUp(self):
        self.server.calls = []
        self.server.mode = "ok"

    def send(self, config=None, ca=None):
        return publish_ntfy(config or self.config, EVENT, token="synthetic-private-token", ca_file=ca or self.ca)

    def test_actual_https_ack_requires_matching_topic_body_and_trust(self):
        self.assertEqual(self.send(), {"accepted": True})
        self.assertEqual(self.server.calls[0]["authorization"], "Bearer synthetic-private-token")
        self.assertEqual(json.loads(self.server.calls[0]["body"]), EVENT)
        for config, ca in [(self.config | {"url": self.config["url"].replace("localhost", "wrong.invalid")}, self.ca),
                           (self.config, Path("/etc/ssl/certs/ca-certificates.crt"))]:
            with self.subTest(url=config["url"]), self.assertRaisesRegex(NotificationError, "notification_transport_unavailable"):
                self.send(config, ca)
        self.assertEqual(len(self.server.calls), 1)

    def test_actual_redirect_auth_failure_mismatch_and_oversize_do_not_ack(self):
        for mode in (302, 401, 503, "mismatch", "oversize"):
            self.server.mode = mode
            with self.subTest(mode=mode), self.assertRaises(NotificationError):
                self.send()
        self.assertEqual(len(self.server.calls), 5)  # No redirect was followed.

    def test_real_cli_persistence_no_replay_and_exclusive_notification_lock(self):
        with tempfile.TemporaryDirectory(prefix="cli-", dir=self.root) as directory:
            state = Path(directory)
            with sqlite3.connect(state / "monitor.sqlite") as db:
                seed(db)
                db.execute("INSERT INTO certificate_monitor_runs VALUES ('active',?,NULL,'running')", (NOW.isoformat(),))
                db.commit()
            (state / "monitor.sqlite").chmod(0o600)
            config = state / "config.json"
            config.write_text(json.dumps(self.config))
            command = [sys.executable, "-B", str(SCRIPTS / "deliver-certificate-notifications.py"),
                       "--config", str(config), "--state-dir", str(state), "--once"]
            for _ in range(2):
                result = subprocess.run(command, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(json.loads(result.stdout)["humanReceiptVerified"])
            self.assertEqual(len(self.server.calls), 1)
            with sqlite3.connect(state / "monitor.sqlite") as db:
                self.assertIsNotNone(db.execute("SELECT delivered_at FROM certificate_monitor_outbox").fetchone()[0])
                self.assertEqual(db.execute("SELECT state FROM certificate_monitor_runs").fetchone()[0], "running")
            with (state / "notification.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = subprocess.run(command, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(json.loads(result.stdout)["reason"], "notification_already_running")
            self.assertEqual(len(self.server.calls), 1)

    def test_watchdog_sender_uses_its_own_state_and_accepts_fixed_recovery_event(self):
        from certificate_watchdog import WatchdogState
        with tempfile.TemporaryDirectory(prefix="watchdog-send-", dir=self.root) as directory:
            state = Path(directory)
            with sqlite3.connect(state / "watchdog.sqlite") as db:
                WatchdogState(db)
                event = EVENT | {"state": "recovered"}
                db.execute("INSERT INTO certificate_monitor_outbox VALUES (?,?,?,?,?,NULL)",
                           tuple(event[k] for k in ("id", "resource", "uid", "state", "createdAt")))
                db.commit()
            (state / "watchdog.sqlite").chmod(0o600)
            config = state / "config.json"
            config.write_text(json.dumps(self.config))
            p = subprocess.run([sys.executable, "-B", str(SCRIPTS / "deliver-certificate-notifications.py"),
                "--watchdog", "--config", str(config), "--state-dir", str(state), "--once"],
                capture_output=True, text=True, timeout=15)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertEqual(json.loads(p.stdout)["acceptedByServer"], 1)
            self.assertFalse((state / "monitor.sqlite").exists())
            self.assertEqual(json.loads(self.server.calls[0]["body"])["state"], "recovered")


if __name__ == "__main__":
    unittest.main()
