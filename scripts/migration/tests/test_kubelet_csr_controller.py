"""Observation/approval boundary and durable exactly-once controller state."""
import base64
import copy
import datetime as dt
import importlib.util
import ipaddress
import json
import sqlite3
import sys
import unittest
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kubelet_csr_controller import (ControllerError, ControllerState, decide,
                                   enrollment, verify_issued)

NOW = dt.datetime(2026, 11, 17, 2, tzinfo=dt.timezone.utc)
UID = "csr-uid-1"
KEY = ec.generate_private_key(ec.SECP256R1())
ISSUER = ec.generate_private_key(ec.SECP256R1())
TRUSTED = {"version": 1, "name": "node01", "uid": "node-uid",
           "ips": ["192.168.0.4"], "dns": ["node01"]}


def request_bytes():
    builder = x509.CertificateSigningRequestBuilder().subject_name(x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "system:nodes"),
        x509.NameAttribute(NameOID.COMMON_NAME, "system:node:node01")]))
    builder = builder.add_extension(x509.SubjectAlternativeName([
        x509.DNSName("node01"), x509.IPAddress(ipaddress.ip_address("192.168.0.4"))]),
        critical=False)
    return builder.sign(KEY, hashes.SHA256())


def fixture(name="csr-one"):
    csr = {"metadata": {"name": name, "uid": UID, "resourceVersion": "7",
                        "creationTimestamp": NOW.isoformat()},
           "spec": {"request": base64.b64encode(request_bytes().public_bytes(
                        serialization.Encoding.PEM)).decode(),
                    "username": "system:node:node01",
                    "groups": ["system:nodes", "system:authenticated"],
                    "signerName": "kubernetes.io/kubelet-serving",
                    "usages": ["digital signature", "server auth"]}}
    node = {"metadata": {"name": "node01", "uid": "node-uid"}, "status": {
        "conditions": [{"type": "Ready", "status": "True"}],
        "addresses": [{"type": "InternalIP", "address": "192.168.0.4"},
                      {"type": "Hostname", "address": "node01"}]}}
    return csr, node


class DecisionTests(unittest.TestCase):
    def test_observation_is_eligible_but_never_approves(self):
        csr, node = fixture()
        observed = decide(csr, node, TRUSTED, mode="observe", now=NOW)
        self.assertTrue(observed["eligible"])
        state = ControllerState(sqlite3.connect(":memory:"))
        state.record(observed)
        self.assertFalse(state.approval_allowed(observed, "observe"))
        self.assertEqual(state.summary(), {"observed": 1, "approved": 0,
                                           "issuedVerified": 0, "pendingApproval": 1})

    def test_enrollment_must_be_trusted_and_complete(self):
        csr, node = fixture()
        for broken in ({}, TRUSTED | {"version": 2}, TRUSTED | {"ips": []},
                       TRUSTED | {"dns": ["node01", "node01"]}, TRUSTED | {"hostname": "x"}):
            with self.subTest(broken=sorted(broken)):
                with self.assertRaisesRegex(ControllerError, "enrollment_invalid"):
                    decide(csr, node, broken, mode="observe", now=NOW)

    def test_diagnostic_named_objects_are_never_approval_eligible(self):
        csr, node = fixture("bortus-csr-diagnostic")
        verdict = decide(csr, node, TRUSTED, mode="observe", now=NOW)
        self.assertFalse(verdict["eligible"])
        self.assertIn("diagnostic_object", verdict["reasons"])

    def test_unknown_mode_is_refused(self):
        csr, node = fixture()
        with self.assertRaisesRegex(ControllerError, "controller_mode_invalid"):
            decide(csr, node, TRUSTED, mode="auto", now=NOW)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.state = ControllerState(sqlite3.connect(":memory:"))
        csr, node = fixture()
        self.csr, self.node = csr, node
        self.verdict = self.state.record(decide(csr, node, TRUSTED, mode="approve", now=NOW))

    def test_one_approval_per_csr_uid_survives_restarts_and_retries(self):
        self.assertTrue(self.state.approval_allowed(self.verdict, "approve"))
        patch = self.state.mark_approved(self.csr, NOW.isoformat())
        self.assertEqual(patch[0]["value"], UID)
        self.assertFalse(self.state.approval_allowed(self.verdict, "approve"))
        # A recreated object with the same UID but new request bytes stays refused.
        changed = copy.deepcopy(self.verdict)
        changed["requestSHA256"] = "0" * 64
        changed = self.state.record(changed)
        self.assertFalse(changed["eligible"])
        self.assertIn("request_changed_after_observation", changed["reasons"])
        self.assertFalse(self.state.approval_allowed(changed, "approve"))
        self.assertEqual(self.state.summary()["approved"], 1)

    def test_issuance_never_registers_without_approval(self):
        with self.assertRaisesRegex(ControllerError, "issuance_without_approval_record"):
            self.state.mark_issued_verified(UID, NOW.isoformat())
        self.state.mark_approved(self.csr, NOW.isoformat())
        self.assertEqual(self.state.mark_issued_verified(UID, NOW.isoformat()), 1)
        self.assertEqual(self.state.summary()["issuedVerified"], 1)

    def test_ineligible_verdict_never_approves(self):
        csr, node = fixture()
        node["metadata"]["uid"] = "replacement"
        verdict = self.state.record(decide(csr, node, TRUSTED, mode="approve", now=NOW))
        self.assertFalse(verdict["eligible"])
        self.assertFalse(self.state.approval_allowed(verdict, "approve"))


class IssuedCertificateTests(unittest.TestCase):
    def certificate(self, dns=("node01",), ips=("192.168.0.4",), usage=ExtendedKeyUsageOID.SERVER_AUTH):
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "system:node:node01")])
        builder = (x509.CertificateBuilder().subject_name(subject)
                   .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ca")]))
                   .public_key(KEY.public_key()).serial_number(1)
                   .not_valid_before(NOW - dt.timedelta(minutes=1))
                   .not_valid_after(NOW + dt.timedelta(hours=1))
                   .add_extension(x509.SubjectAlternativeName(
                       [x509.DNSName(n) for n in dns] +
                       [x509.IPAddress(ipaddress.ip_address(i)) for i in ips]), critical=False)
                   .add_extension(x509.ExtendedKeyUsage([usage]), critical=False))
        der = builder.sign(ISSUER, hashes.SHA256())
        return base64.b64encode(der.public_bytes(serialization.Encoding.PEM)).decode()

    def test_matching_issued_certificate_verifies_and_mismatches_do_not(self):
        ok, reason = verify_issued({"status": {"certificate": self.certificate()}}, TRUSTED, NOW)
        self.assertEqual((ok, reason), (True, None))
        for bad in ({"status": {"certificate": self.certificate(dns=("node02",))}},
                    {"status": {"certificate": self.certificate(ips=("192.168.0.9",))}},
                    {"status": {"certificate": self.certificate(usage=ExtendedKeyUsageOID.CLIENT_AUTH)}},
                    {"status": {"certificate": "not-a-certificate"}}, {"status": {}}):
            with self.subTest(case=str(bad)[:40]):
                ok, reason = verify_issued(bad, TRUSTED, NOW)
                self.assertFalse(ok)
                self.assertTrue(reason)


class ServedCertificateTests(unittest.TestCase):
    def served(self, dns=("node01",), ips=("192.168.0.4",)):
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "system:node:node01")])
        issuer_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ca")])
        builder = (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer_name)
                   .public_key(KEY.public_key()).serial_number(2)
                   .not_valid_before(NOW - dt.timedelta(minutes=5))
                   .not_valid_after(NOW + dt.timedelta(hours=1))
                   .add_extension(x509.SubjectAlternativeName(
                       [x509.DNSName(n) for n in dns] +
                       [x509.IPAddress(ipaddress.ip_address(i)) for i in ips]), critical=False)
                   .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False))
        peer = builder.sign(ISSUER, hashes.SHA256())
        issuer = (x509.CertificateBuilder()
                  .subject_name(issuer_name).issuer_name(issuer_name)
                  .public_key(ISSUER.public_key()).serial_number(3)
                  .not_valid_before(NOW - dt.timedelta(days=1))
                  .not_valid_after(NOW + dt.timedelta(days=30))
                  .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                  .sign(ISSUER, hashes.SHA256()))
        return (peer.public_bytes(serialization.Encoding.DER),
                issuer.public_bytes(serialization.Encoding.DER))

    def test_served_certificate_requires_chain_identities_and_usage(self):
        from kubelet_csr_controller import verify_served
        ok, reason, fingerprint = verify_served(self.served(), TRUSTED, NOW)
        self.assertEqual((ok, reason), (True, None))
        self.assertEqual(len(fingerprint), 64)
        for dns, ips, expected in (
                (("node02",), ("192.168.0.4",), "served_identities_mismatch"),
                (("node01",), ("192.168.0.9",), "served_identities_mismatch"),
                ((), (), "served_identities_mismatch")):
            with self.subTest(expected=expected):
                ok, reason, _ = verify_served(self.served(dns, ips), TRUSTED, NOW)
                self.assertFalse(ok)
                self.assertEqual(reason, expected)

    def test_wrong_issuer_foreign_signature_expiry_and_garbage_are_refused(self):
        from kubelet_csr_controller import verify_served
        peer, issuer = self.served()
        other = x509.load_der_x509_certificate(issuer)
        ok, reason, _ = verify_served((peer, peer), TRUSTED, NOW)
        self.assertFalse(ok)
        self.assertIn(reason, ("served_issuer_mismatch", "served_signature_invalid"))
        ok, reason, _ = verify_served((b"not-a-certificate", issuer), TRUSTED, NOW)
        self.assertEqual((ok, reason), (False, "served_certificate_unverifiable"))
        ok, reason, _ = verify_served(self.served(), TRUSTED, NOW + dt.timedelta(days=2))
        self.assertEqual((ok, reason), (False, "served_certificate_not_currently_valid"))


class MultiNodeEnrollmentTests(unittest.TestCase):
    """node01/node03 rollout: each machine is watched before it is trusted."""

    def test_v1_file_stays_valid_and_v2_carries_a_per_node_switch(self):
        from kubelet_csr_controller import enrollment_set
        self.assertEqual(enrollment_set(TRUSTED), {"node01": (TRUSTED, True)})
        v2 = {"version": 2, "nodes": [
            {k: v for k, v in TRUSTED.items() if k != "version"} | {"approve": False},
            {"name": "node02", "uid": "u2", "ips": ["192.168.0.6"], "dns": ["node02"], "approve": True}]}
        loaded = enrollment_set(v2)
        self.assertEqual(loaded["node01"], (TRUSTED, False))
        self.assertTrue(loaded["node02"][1])

    def test_v2_refuses_duplicates_missing_switch_and_extra_keys(self):
        from kubelet_csr_controller import enrollment_set
        base = {k: v for k, v in TRUSTED.items() if k != "version"}
        for broken in ({"version": 2, "nodes": []},
                       {"version": 2, "nodes": [base]},
                       {"version": 2, "nodes": [base | {"approve": "yes"}]},
                       {"version": 2, "nodes": [base | {"approve": True}] * 2},
                       {"version": 2, "nodes": [base | {"approve": True}], "extra": 1}):
            with self.subTest(broken=broken):
                with self.assertRaisesRegex(ControllerError, "enrollment_invalid"):
                    enrollment_set(broken)


class CycleTests(unittest.TestCase):
    """The real runner cycle() with kubectl replaced by an in-memory API."""

    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "csr_runner_cycle", Path(__file__).parents[1] / "run-kubelet-csr-controller.py")
        self.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runner)
        self.csr, self.node = fixture()
        self.patches, self.fail_patch = [], False
        self.state = ControllerState(sqlite3.connect(":memory:"))

        def fake(binary, config, args, data=None, limit=None):
            if args[:3] == ["get", "csr", "-o"]:
                return {"items": [copy.deepcopy(self.csr)]}
            if args[:2] == ["get", "csr"]:
                current = copy.deepcopy(self.csr)
                return current
            if args[:2] == ["get", "node"]:
                return copy.deepcopy(self.node)
            if args[:2] == ["patch", "csr"]:
                if self.fail_patch:
                    raise RuntimeError("api refused")
                self.patches.append(json.loads(data))
                return {}
            raise AssertionError(args)
        self.runner.kubectl = fake

    def run_cycle(self, enrolled, mode="approve", flag=True):
        return self.runner.cycle("kubectl", "cfg", self.state, enrolled, mode, flag, now=NOW)

    def test_watch_only_machine_is_checked_but_never_approved(self):
        result = self.run_cycle({"node01": (TRUSTED, False)})
        self.assertTrue(result["verdicts"][0]["eligible"])
        self.assertFalse(result["verdicts"][0]["approved"])
        self.assertEqual(self.patches, [])

    def test_approve_switch_on_approves_exactly_once(self):
        first = self.run_cycle({"node01": (TRUSTED, True)})
        self.assertTrue(first["verdicts"][0]["approved"])
        self.run_cycle({"node01": (TRUSTED, True)})
        self.assertEqual(len(self.patches), 1)

    def test_machine_not_on_the_list_is_recorded_and_never_approved(self):
        other = TRUSTED | {"name": "node03", "ips": ["192.168.0.5"], "dns": ["node03"]}
        result = self.run_cycle({"node03": (other, True)})
        self.assertEqual(result["verdicts"][0]["reasons"], ["node_not_enrolled"])
        self.assertEqual(self.patches, [])

    def test_request_naming_another_machine_is_refused_even_with_switch_on(self):
        # node01's credentials asking for node03's address must not pass.
        self.node["status"]["addresses"][0]["address"] = "192.168.0.5"
        result = self.run_cycle({"node01": (TRUSTED | {"ips": ["192.168.0.5"]}, True)})
        self.assertFalse(result["verdicts"][0]["eligible"])
        self.assertEqual(self.patches, [])

    def test_definite_patch_failure_releases_the_exactly_once_row(self):
        # Regression: this path used an undefined `meta` and crashed with
        # NameError, leaving the CSR wedged with a recorded approval.
        self.fail_patch = True
        with self.assertRaisesRegex(RuntimeError, "api refused"):
            self.run_cycle({"node01": (TRUSTED, True)})
        self.assertIsNone(self.state.db.execute(
            "SELECT 1 FROM kubelet_csr_approvals WHERE csr_uid=?", (UID,)).fetchone())
        self.fail_patch = False
        self.assertTrue(self.run_cycle({"node01": (TRUSTED, True)})["verdicts"][0]["approved"])


class OldCryptographyTests(unittest.TestCase):
    def test_validity_works_without_the_utc_properties(self):
        # node02's cryptography 3.4.8 only has the naive not_valid_* attributes.
        from kubelet_csr_controller import _validity

        class Old:
            not_valid_before = dt.datetime(2026, 11, 1)
            not_valid_after = dt.datetime(2027, 11, 1)
        before, after = _validity(Old())
        self.assertEqual(after, dt.datetime(2027, 11, 1, tzinfo=dt.timezone.utc))
        self.assertEqual(before.tzinfo, dt.timezone.utc)


class RunnerSourceTests(unittest.TestCase):
    def test_runner_requires_observation_default_and_refuses_approve_without_flag(self):
        spec = importlib.util.spec_from_file_location(
            "csr_runner", Path(__file__).parents[1] / "run-kubelet-csr-controller.py")
        source = (Path(__file__).parents[1] / "run-kubelet-csr-controller.py").read_text()
        self.assertIn('default="observe"', source)
        self.assertIn('parser.error' if False else 'approval_flag_requires_approve_mode', source)
        self.assertIn('"patch", "csr", name, "--subresource=approval"', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rows = [{"metadata": {"name": "a"}, "spec": {"signerName": "kubernetes.io/kubelet-serving"}},
                {"metadata": {"name": "b"}, "spec": {"signerName": "kubernetes.io/kube-apiserver-client"}},
                {"metadata": {"name": "c"}, "spec": {"signerName": "kubernetes.io/kubelet-serving"},
                 "status": {"certificate": "issued"}},
                {"metadata": {"name": "d"}, "spec": {"signerName": "kubernetes.io/kubelet-serving"},
                 "status": {"conditions": [{"type": "Denied", "status": "True"}]}}]
        self.assertEqual([r["metadata"]["name"] for r in module.pending(rows)], ["a"])


if __name__ == "__main__":
    unittest.main()
