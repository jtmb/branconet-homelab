import base64
import copy
import datetime as dt
import ipaddress
import sys
import unittest
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kubelet_csr_policy import approval_patch, validate_csr

NOW = dt.datetime(2026, 11, 16, 12, tzinfo=dt.timezone.utc)


class CsrPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = ec.generate_private_key(ec.SECP256R1())

    def request(self, subject=None, names=None, extra=False):
        subject = subject if subject is not None else [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "system:nodes"),
            x509.NameAttribute(NameOID.COMMON_NAME, "system:node:node01"),
        ]
        names = names if names is not None else [
            x509.DNSName("node01"), x509.IPAddress(ipaddress.ip_address("192.168.0.4")),
        ]
        builder = x509.CertificateSigningRequestBuilder().subject_name(x509.Name(subject))
        builder = builder.add_extension(x509.SubjectAlternativeName(names), critical=False)
        if extra:
            builder = builder.add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        raw = builder.sign(self.key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM)
        return base64.b64encode(raw).decode()

    def fixture(self):
        csr = {
            "metadata": {"name": "csr-one", "uid": "csr-uid", "resourceVersion": "42", "creationTimestamp": NOW.isoformat()},
            "spec": {"request": self.request(), "username": "system:node:node01",
                     "groups": ["system:nodes", "system:authenticated"],
                     "signerName": "kubernetes.io/kubelet-serving", "usages": ["digital signature", "server auth"]},
        }
        node = {"metadata": {"name": "node01", "uid": "node-uid"}, "status": {
            "conditions": [{"type": "Ready", "status": "True"}],
            "addresses": [{"type": "InternalIP", "address": "192.168.0.4"}, {"type": "Hostname", "address": "node01"}],
        }}
        enrollment = {"name": "node01", "uid": "node-uid", "ips": ["192.168.0.4"], "dns": ["node01"]}
        return csr, node, enrollment

    def test_real_signed_request_and_cas_approval(self):
        csr, node, enrollment = self.fixture()
        self.assertEqual(validate_csr(csr, node, enrollment, NOW), [])
        patch = approval_patch(csr, NOW.isoformat())
        self.assertEqual(patch[0], {"op": "test", "path": "/metadata/uid", "value": "csr-uid"})
        self.assertEqual(patch[1]["value"], "42")
        self.assertEqual(patch[2]["value"], csr["spec"]["request"])
        self.assertEqual(patch[-1]["value"][0]["type"], "Approved")

    def test_extra_subject_and_san_identities_are_refused(self):
        csr, node, enrollment = self.fixture()
        for request in [
            self.request(subject=[x509.NameAttribute(NameOID.ORGANIZATION_NAME, "system:nodes"),
                                  x509.NameAttribute(NameOID.COMMON_NAME, "system:node:node01"),
                                  x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "extra")]),
            self.request(names=[x509.DNSName("node01"), x509.IPAddress(ipaddress.ip_address("192.168.0.4")),
                                x509.UniformResourceIdentifier("spiffe://unexpected")]),
            self.request(names=[x509.DNSName("node01")]),
            self.request(extra=True),
        ]:
            with self.subTest(request=request[:20]):
                csr["spec"]["request"] = request
                self.assertTrue(validate_csr(csr, node, enrollment, NOW))

    def test_requester_signer_client_usage_and_lifetime_cannot_expand_approval(self):
        baseline, node, enrollment = self.fixture()
        for field, value, reason in [
            ("username", "system:node:node02", "requester_invalid"),
            ("signerName", "kubernetes.io/kube-apiserver-client", "signer_invalid"),
            ("groups", ["system:nodes", "system:masters"], "groups_invalid"),
            ("usages", ["digital signature", "server auth", "client auth"], "usages_invalid"),
            ("expirationSeconds", 86400 * 500, "lifetime_invalid"),
        ]:
            with self.subTest(field=field):
                csr = copy.deepcopy(baseline); csr["spec"][field] = value
                self.assertIn(reason, validate_csr(csr, node, enrollment, NOW))

    def test_node_recreation_address_changes_and_terminal_requests_fail_closed(self):
        csr, node, enrollment = self.fixture()
        node["metadata"]["uid"] = "replacement"
        self.assertIn("node_identity_changed", validate_csr(csr, node, enrollment, NOW))
        node["metadata"]["uid"] = enrollment["uid"]
        node["status"]["addresses"][0]["address"] = "192.168.0.99"
        self.assertIn("node_addresses_changed", validate_csr(csr, node, enrollment, NOW))
        for status in [{"certificate": "already-issued"}, {"conditions": [{"type": "Denied", "status": "True"}]}]:
            csr["status"] = status
            self.assertIn("csr_not_pending", validate_csr(csr, node, enrollment, NOW))

    def test_stale_and_malformed_requests_never_qualify(self):
        csr, node, enrollment = self.fixture()
        self.assertIn("csr_age_out_of_bounds", validate_csr(csr, node, enrollment, NOW + dt.timedelta(hours=2)))
        csr["spec"]["request"] = "not base64"
        self.assertIn("request_invalid", validate_csr(csr, node, enrollment, NOW))

    def test_tampered_signature_is_rejected_without_openssl_text_parsing(self):
        csr, node, enrollment = self.fixture()
        parsed = x509.load_pem_x509_csr(base64.b64decode(csr["spec"]["request"]))
        der = bytearray(parsed.public_bytes(serialization.Encoding.DER))
        der[-1] ^= 1
        # Still valid ASN.1, but no longer signed by the embedded public key.
        tampered = x509.load_der_x509_csr(bytes(der))
        csr["spec"]["request"] = base64.b64encode(tampered.public_bytes(serialization.Encoding.PEM)).decode()
        self.assertIn("signature_invalid", validate_csr(csr, node, enrollment, NOW))


if __name__ == "__main__":
    unittest.main()
