import base64
import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from certificate_monitor_credentials import (ACCOUNT, AUDIENCE, SUBJECT, CredentialError,
                                             ScopeViolation, refresh)
from certificate_monitor_runtime import H_ROOT

NOW = dt.datetime(2026, 11, 16, 12, tzinfo=dt.timezone.utc)
UID = "11111111-2222-3333-4444-555555555555"


def issued_token(**changes):
    claims = {"iss": AUDIENCE, "aud": [AUDIENCE], "sub": SUBJECT,
              "iat": int(NOW.timestamp()), "nbf": int(NOW.timestamp()),
              "exp": int(NOW.timestamp()) + 3600,
              "kubernetes.io": {"namespace": "bortus", "serviceaccount": {"name": ACCOUNT, "uid": UID}}}
    claims.update(changes)
    encode = lambda value: base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
    return {"status": {"token": encode({"alg": "RS256"}) + "." + encode(claims) + ".synthetic",
                       "expirationTimestamp": (NOW + dt.timedelta(hours=1)).isoformat()}}


class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.published = []
        self.quarantined = []
        self.minted = []
        self.subject = {"status": {"userInfo": {
            "username": SUBJECT, "uid": UID,
            "groups": ["system:serviceaccounts", "system:serviceaccounts:bortus", "system:authenticated"]}}}
        self.response = issued_token()

    def access(self, token, attributes):
        # A fixture of the reviewed metadata role, independent of the probe
        # matrix. This models checks; it is not effective live RBAC acceptance.
        group, resource, verb = (attributes.get(key) for key in ("group", "resource", "verb"))
        allowed = (group in ("cert-manager.io", "certificates.k8s.io") and
                   resource in ("certificates", "certificatesigningrequests") and verb in ("get", "list"))
        if group == "" and resource == "configmaps" and attributes.get("namespace") == "bortus":
            name = attributes.get("name")
            allowed = (verb == "get" and name in ("bortus-certificate-policy", "bortus-certificate-observations") or
                       verb == "patch" and name == "bortus-certificate-observations")
        return {"status": {"allowed": bool(allowed)}}

    def run_refresh(self, **overrides):
        def mint(body):
            self.minted.append(body)
            return self.response
        dependencies = dict(pinned_uid=UID, read_uid=lambda: UID, mint=mint,
                            review_subject=lambda token: self.subject, review_access=self.access,
                            probe_reads=lambda token: None, publish=self.published.append,
                            quarantine=lambda: self.quarantined.append(True), now=NOW)
        dependencies.update(overrides)
        return refresh(**dependencies)

    def test_one_hour_credential_publishes_only_after_identity_permissions_reads_and_uid_recheck(self):
        events = []
        def uid():
            events.append("uid")
            return UID
        result = self.run_refresh(read_uid=uid, probe_reads=lambda token: events.append("reads"),
                                  publish=lambda token: (events.append("publish"), self.published.append(token)))
        self.assertEqual(events, ["uid", "reads", "uid", "publish"])
        self.assertEqual(len(self.published), 1)
        self.assertEqual(self.minted[0]["spec"], {"audiences": [AUDIENCE], "expirationSeconds": 3600})
        self.assertNotIn(self.published[0], json.dumps(result))
        self.assertEqual(sum(row["expectedAllowed"] for row in result["permissionChecks"]), 7)
        self.assertGreater(len(result["permissionChecks"]), 20)

    def test_broadened_role_or_missing_required_permission_quarantines_without_publishing(self):
        for broad in (True, False):
            with self.subTest(broad=broad):
                self.published.clear()
                self.quarantined.clear()
                def access(token, attributes):
                    if broad and attributes["resource"] == "secrets":
                        return {"status": {"allowed": True}}
                    if not broad and attributes["resource"] == "certificates":
                        return {"status": {"allowed": False}}
                    return self.access(token, attributes)
                with self.assertRaisesRegex(ScopeViolation, "effective_permission_mismatch"):
                    self.run_refresh(review_access=access)
                self.assertFalse(self.published)
                self.assertEqual(self.quarantined, [True])

    def test_recreated_account_before_mint_or_during_qualification_never_publishes(self):
        for values in (["changed"], [UID, "changed"]):
            with self.subTest(values=values):
                self.published.clear()
                sequence = iter(values)
                with self.assertRaisesRegex(ScopeViolation, "service_account_recreated"):
                    self.run_refresh(read_uid=lambda: next(sequence))
                self.assertFalse(self.published)

    def test_wrong_issuer_audience_subject_or_authenticated_groups_fails_closed(self):
        for claim, value in (("aud", ["wrong"]), ("iss", "wrong"), ("sub", "system:admin")):
            with self.subTest(claim=claim):
                self.response = issued_token(**{claim: value})
                with self.assertRaises(ScopeViolation):
                    self.run_refresh()
                self.assertFalse(self.published)
        self.response = issued_token()
        self.subject = copy.deepcopy(self.subject)
        self.subject["status"]["userInfo"]["groups"].append("system:masters")
        with self.assertRaisesRegex(ScopeViolation, "authenticated_identity_mismatch"):
            self.run_refresh()
        self.assertFalse(self.published)

    def test_expired_overlong_or_malformed_token_response_never_publishes(self):
        cases = [issued_token(exp=int(NOW.timestamp()) - 10), {"status": {"token": "private-token-fixture"}},
                 {"status": {"token": "x" * 17000, "expirationTimestamp": NOW.isoformat()}}]
        overlong = issued_token(exp=int(NOW.timestamp()) + 86400)
        overlong["status"]["expirationTimestamp"] = (NOW + dt.timedelta(days=1)).isoformat()
        cases.append(overlong)
        for value in cases:
            with self.subTest(case=len(value["status"].get("token", ""))):
                self.response = value
                with self.assertRaises(CredentialError) as error:
                    self.run_refresh()
                self.assertNotIn("private-token-fixture", str(error.exception))
                self.assertFalse(self.published)

    def test_transient_or_incomplete_review_preserves_active_credential_and_publishes_nothing(self):
        for callback in (lambda token, attr: {"status": {"allowed": False, "evaluationError": "unavailable"}},
                         lambda token, attr: {"status": {}}):
            with self.assertRaisesRegex(CredentialError, "access_review_incomplete"):
                self.run_refresh(review_access=callback)
        self.assertFalse(self.published)
        self.assertFalse(self.quarantined)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        root = Path(os.environ["BORTUS_MONITOR_TEST_ROOT"]).resolve()
        if H_ROOT.resolve() not in root.parents:
            raise RuntimeError("Explicit H test output required")
        root.mkdir(mode=0o700, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="credentials-", dir=root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        spec = importlib.util.spec_from_file_location("credential_broker", SCRIPTS / "refresh-certificate-monitor-credential.py")
        self.broker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.broker)

    def test_atomic_publication_and_failed_candidate_cleanup_preserve_complete_credentials(self):
        active = self.root / "token"
        active.write_text("old-synthetic")
        ca = self.root / "public-ca.crt"
        pending = self.broker.CandidateFiles(self.root, os.getgid(), ca_path=ca)
        with active.open() as old_reader:
            pending.prepare("new-synthetic")
            self.assertNotIn("new-synthetic", pending.config_path.read_text())
            self.assertEqual(json.loads(pending.config_path.read_text())["clusters"][0]["cluster"]["certificate-authority"], str(ca))
            self.assertFalse(pending.token_path.stat().st_mode & 0o077)
            pending.publish("new-synthetic")
            self.assertEqual(old_reader.read(), "old-synthetic")
            self.assertEqual(active.read_text(), "new-synthetic")
            self.assertEqual(active.stat().st_mode & 0o777, 0o640)
            self.assertTrue(pending.published)
        pending.close()
        failed = self.broker.CandidateFiles(self.root, os.getgid())
        failed.prepare("rejected-synthetic")
        failed.close()
        self.assertEqual(active.read_text(), "new-synthetic")
        self.assertEqual([p.name for p in self.root.iterdir()], ["token"])

    def test_local_checkout_cannot_invoke_root_broker_or_mint_credentials(self):
        result = subprocess.run([sys.executable, "-B", str(SCRIPTS / "refresh-certificate-monitor-credential.py")],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["reason"], "fixed_root_installation_required")
        self.assertFalse(json.loads(result.stdout)["candidatePublished"])


if __name__ == "__main__":
    unittest.main()
