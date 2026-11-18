"""Strict kubelet-serving CSR validation shared by manual and future automation.

Only public request material is parsed. Enrollment is a trusted input, never
created from the CSR. The caller must revalidate enrollment before mutation.
"""
import base64
import datetime as dt
import ipaddress

from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID

SIGNER = "kubernetes.io/kubelet-serving"
MAX_LIFETIME = 366 * 86400


def validate_csr(csr, node, enrollment, now=None):
    """Return reason codes; an empty list means eligible, not approved/installed."""
    now = now or dt.datetime.now(dt.timezone.utc)
    failures = []
    meta, spec, status = csr.get("metadata", {}), csr.get("spec", {}), csr.get("status", {})
    node_meta = node.get("metadata", {})
    name = enrollment.get("name")
    uid = enrollment.get("uid")
    ips = enrollment.get("ips", [])
    dns = enrollment.get("dns", [])
    if not name or not uid or not ips or not dns:
        return ["enrollment_invalid"]
    if node_meta.get("name") != name or node_meta.get("uid") != uid or node_meta.get("deletionTimestamp"):
        failures.append("node_identity_changed")
    ready = any(c.get("type") == "Ready" and c.get("status") == "True"
                for c in node.get("status", {}).get("conditions", []))
    if not ready:
        failures.append("node_not_ready")
    observed_ips = {a.get("address") for a in node.get("status", {}).get("addresses", []) if a.get("type") == "InternalIP"}
    observed_dns = {name} | {a.get("address") for a in node.get("status", {}).get("addresses", []) if a.get("type") == "Hostname"}
    if observed_ips != set(ips) or observed_dns != set(dns):
        failures.append("node_addresses_changed")
    if not meta.get("name") or not meta.get("uid") or not meta.get("resourceVersion") or meta.get("deletionTimestamp"):
        failures.append("csr_identity_invalid")
    if status.get("certificate") or status.get("conditions"):
        failures.append("csr_not_pending")
    try:
        created = dt.datetime.fromisoformat(meta["creationTimestamp"].replace("Z", "+00:00"))
        if not 0 <= (now - created).total_seconds() <= 3600:
            failures.append("csr_age_out_of_bounds")
    except (KeyError, ValueError, TypeError):
        failures.append("csr_age_invalid")
    if spec.get("signerName") != SIGNER:
        failures.append("signer_invalid")
    if spec.get("username") != "system:node:" + name:
        failures.append("requester_invalid")
    if set(spec.get("groups", [])) != {"system:nodes", "system:authenticated"}:
        failures.append("groups_invalid")
    usages = spec.get("usages", [])
    if (not isinstance(usages, list) or len(set(usages)) != len(usages) or
            set(usages) not in ({"digital signature", "server auth"},
                               {"digital signature", "key encipherment", "server auth"})):
        failures.append("usages_invalid")
    lifetime = spec.get("expirationSeconds", MAX_LIFETIME)
    if type(lifetime) is not int or not 600 <= lifetime <= MAX_LIFETIME:
        failures.append("lifetime_invalid")
    try:
        raw = spec["request"]
        if not isinstance(raw, str) or len(raw) > 32768:
            return failures + ["request_size_invalid"]
        pem = base64.b64decode(raw, validate=True)
        request = x509.load_pem_x509_csr(pem)
        if pem != request.public_bytes(serialization.Encoding.PEM):
            failures.append("request_encoding_invalid")
        if not request.is_signature_valid:
            failures.append("signature_invalid")
        attributes = list(request.subject)
        expected = {(NameOID.ORGANIZATION_NAME, "system:nodes"), (NameOID.COMMON_NAME, "system:node:" + name)}
        if len(attributes) != 2 or {(a.oid, a.value) for a in attributes} != expected:
            failures.append("subject_invalid")
        key = request.public_key()
        if not (isinstance(key, rsa.RSAPublicKey) and key.key_size >= 2048 or
                isinstance(key, ec.EllipticCurvePublicKey) and key.curve.name in ("secp256r1", "secp384r1")):
            failures.append("public_key_invalid")
        if not isinstance(request.signature_hash_algorithm, (hashes.SHA256, hashes.SHA384, hashes.SHA512)):
            failures.append("signature_algorithm_invalid")
        extensions = list(request.extensions)
        if len(extensions) != 1 or not isinstance(extensions[0].value, x509.SubjectAlternativeName):
            failures.append("extensions_invalid")
        else:
            names = list(extensions[0].value)
            requested_dns = [n.value for n in names if isinstance(n, x509.DNSName)]
            requested_ips = [str(n.value) for n in names if isinstance(n, x509.IPAddress)]
            if (len(names) != len(requested_dns) + len(requested_ips) or
                    len(set(requested_dns)) != len(requested_dns) or len(set(requested_ips)) != len(requested_ips) or
                    set(requested_dns) != set(dns) or
                    set(requested_ips) != {str(ipaddress.ip_address(ip)) for ip in ips}):
                failures.append("sans_invalid")
    except (ValueError, TypeError, KeyError, x509.DuplicateExtension, UnsupportedAlgorithm):
        failures.append("request_invalid")
    return failures


def approval_patch(csr, checked_at):
    """Compare-and-swap the exact reviewed CSR, without replacing other fields."""
    meta = csr["metadata"]
    return [
        {"op": "test", "path": "/metadata/uid", "value": meta["uid"]},
        {"op": "test", "path": "/metadata/resourceVersion", "value": meta["resourceVersion"]},
        {"op": "test", "path": "/spec/request", "value": csr["spec"]["request"]},
        {"op": "add", "path": "/status/conditions", "value": [{
            "type": "Approved", "status": "True", "reason": "BortusValidatedKubeletServing",
            "message": "Exact enrolled node identity, serving-only usages and CSR signature validated.",
            "lastUpdateTime": checked_at,
        }]},
    ]
