"""Failure diagnostics cannot expose transport exception text or alter retries."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import json

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
    "notification_dispatch_diagnostics", ROOT / "deliver-certificate-notifications.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
import certificate_monitor_notifications as TRANSPORT


class DiagnosticTests(unittest.TestCase):
    def test_only_fixed_failure_codes_reach_journal(self):
        with patch.object(MODULE.syslog, "syslog") as log:
            MODULE.report_delivery_failure(ValueError("private token/endpoint/backend"), "transport")
            MODULE.report_delivery_failure(RuntimeError("process_timeout"), "child")
        messages = [json.loads(c.args[1]) for c in log.call_args_list]
        self.assertEqual([m["notificationFailure"] for m in messages],
                         ["notification_unavailable", "process_timeout"])
        self.assertNotIn("private token", str(messages))

    def test_missing_journal_does_not_change_failure_handling(self):
        with patch.object(MODULE.syslog, "syslog", side_effect=OSError("unavailable")):
            MODULE.report_delivery_failure(RuntimeError("notification_transport_unavailable"), "transport")

    def test_transport_annotations_are_allowlisted(self):
        error = RuntimeError("notification_transport_unavailable")
        error.transport_stage = "private endpoint/token"
        error.transport_kind = "private backend text"
        with patch.object(MODULE.syslog, "syslog") as log:
            MODULE.report_delivery_failure(error, "transport")
        self.assertNotIn("private", log.call_args.args[1])

    def test_request_timeout_is_classified_without_exception_text(self):
        config = {"version": 1, "url": "https://localhost/topic", "address": "127.0.0.1",
                  "caFile": "/synthetic/ca", "tokenFile": "/synthetic/token"}
        event = {"id": "event", "resource": "monitor-heartbeat", "uid": "coverage",
                 "state": "missed", "createdAt": "2026-11-17T00:00:00Z"}
        with patch.object(TRANSPORT.ssl, "create_default_context"), \
                patch.object(TRANSPORT, "PinnedHTTPSConnection") as connection:
            connection.return_value.request.side_effect = TimeoutError("private transport data")
            with self.assertRaises(TRANSPORT.NotificationError) as caught:
                TRANSPORT.publish_ntfy(config, event, token="synthetic", ca_file="/synthetic/ca")
        self.assertEqual(str(caught.exception), "notification_transport_unavailable")
        self.assertEqual(caught.exception.transport_stage, "request")
        self.assertEqual(caught.exception.transport_kind, "timeout")
        with patch.object(MODULE.syslog, "syslog") as log:
            MODULE.report_delivery_failure(caught.exception, "transport")
        self.assertEqual(json.loads(log.call_args.args[1])["transportKind"], "timeout")
        self.assertNotIn("private transport data", log.call_args.args[1])
