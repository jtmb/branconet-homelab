import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from test_certificate_monitor_credentials import NOW, UID, issued_token
from certificate_monitor_credentials import (
    CredentialError, ScopeViolation, WATCHDOG_ACCOUNT, permissions, refresh)

SUBJECT = "system:serviceaccount:bortus:" + WATCHDOG_ACCOUNT
SPEC = importlib.util.spec_from_file_location(
    "watchdog_broker", Path(__file__).parents[1] / "refresh-certificate-watchdog-credential.py")
BROKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BROKER)


class WatchdogCredentials(unittest.TestCase):
    def setUp(self):
        self.published, self.quarantined = [], []
        self.response = issued_token(sub=SUBJECT, **{"kubernetes.io": {
            "namespace": "bortus", "serviceaccount": {"name": WATCHDOG_ACCOUNT, "uid": UID}}})
        self.subject = {"status": {"userInfo": {
            "username": SUBJECT, "uid": UID,
            "groups": ["system:serviceaccounts", "system:serviceaccounts:bortus", "system:authenticated"]}}}

    def access(self, token, attrs):
        allowed = attrs.get("verb") == "get" and (
            (attrs.get("group") == "" and attrs.get("resource") == "configmaps"
             and attrs.get("namespace") == "bortus" and attrs.get("name") == "bortus-certificate-observations")
            or (attrs.get("group") == "coordination.k8s.io" and attrs.get("resource") == "leases"
                and attrs.get("namespace") == "kube-node-lease" and attrs.get("name") == "node02"))
        return {"status": {"allowed": allowed}}

    def run_refresh(self, **overrides):
        args = dict(profile="watchdog", pinned_uid=UID, read_uid=lambda: UID,
                    mint=lambda body: self.response, review_subject=lambda token: self.subject,
                    review_access=self.access, probe_reads=lambda token: None,
                    publish=self.published.append, quarantine=lambda: self.quarantined.append(True), now=NOW)
        args.update(overrides)
        return refresh(**args)

    def test_only_two_exact_gets_publish_an_independent_identity(self):
        result = self.run_refresh()
        self.assertEqual(result["subject"], SUBJECT)
        self.assertEqual(sum(row["expectedAllowed"] for row in result["permissionChecks"]), 2)
        self.assertEqual(len(self.published), 1)
        self.assertNotIn(self.published[0], json.dumps(result))
        self.assertIn((False, ("patch", "", "configmaps", "bortus",
                              "bortus-certificate-observations", "")), permissions("watchdog"))

    def test_monitor_token_cannot_be_reused_as_watchdog(self):
        self.response = issued_token()
        with self.assertRaises(ScopeViolation):
            self.run_refresh()
        self.assertFalse(self.published)
        self.assertEqual(self.quarantined, [True])

    def test_monitor_writer_privilege_quarantines_watchdog_candidate(self):
        def broadened(token, attrs):
            if attrs.get("verb") == "patch" and attrs.get("resource") == "configmaps":
                return {"status": {"allowed": True}}
            return self.access(token, attrs)
        with self.assertRaisesRegex(ScopeViolation, "effective_permission_mismatch"):
            self.run_refresh(review_access=broadened)
        self.assertFalse(self.published)
        self.assertEqual(self.quarantined, [True])

    def test_recreated_observation_resource_is_not_silently_enrolled(self):
        api = BROKER.api_type(object)()
        api.enrollment = {"observationsUID": "original", "policyUID": "policy", "leaseUID": "lease"}
        api.candidate = SimpleNamespace(config_path=Path("/synthetic/config"))
        api.metadata_counts = {}
        api.command = lambda *args, **kwargs: {"kind": "ConfigMap", "metadata": {
            "namespace": "bortus", "name": "bortus-certificate-observations", "uid": "recreated"}}
        with self.assertRaisesRegex(ScopeViolation, "enrolled_resource_recreated"):
            api.reads("synthetic")

    def test_unknown_profile_never_mints(self):
        calls = []
        with self.assertRaisesRegex(CredentialError, "credential_profile_invalid"):
            self.run_refresh(profile="unreviewed", mint=lambda body: calls.append(body))
        self.assertFalse(calls)
