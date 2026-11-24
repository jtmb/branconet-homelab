"""Observation-first kubelet-serving CSR controller decisions and durable audit.

Approval is never implied by validation. Observation records the same strict
verdict without mutating the CSR, and the durable state guarantees at most one
approval per CSR UID (no re-approval after recreation or concurrent edits).
"""
import datetime as dt
import hashlib
import json
import sqlite3

from kubelet_csr_policy import SIGNER, approval_patch, validate_csr

MAX_DATABASE_BYTES = 16 * 1024 * 1024
HISTORY_ROWS = 500
ENROLLMENT_KEYS = {"version", "name", "uid", "ips", "dns"}
MODES = ("observe", "approve")


class ControllerError(RuntimeError):
    """Fixed public code only: never CSR bytes, node data or backend output."""


def enrollment(value):
    """Trusted operator input; an incoming CSR must never build this record."""
    try:
        if not isinstance(value, dict) or set(value) != ENROLLMENT_KEYS:
            raise ValueError()
        if type(value["version"]) is not int or value["version"] != 1:
            raise ValueError()
        name, uid = value["name"], value["uid"]
        ips, dns = value["ips"], value["dns"]
        if (not isinstance(name, str) or not 1 <= len(name) <= 253 or
                not isinstance(uid, str) or not 1 <= len(uid) <= 128):
            raise ValueError()
        if (not isinstance(ips, list) or not ips or len(set(ips)) != len(ips) or
                not all(isinstance(row, str) and 1 <= len(row) <= 64 for row in ips)):
            raise ValueError()
        if (not isinstance(dns, list) or not dns or len(set(dns)) != len(dns) or
                not all(isinstance(row, str) and 1 <= len(row) <= 253 for row in dns)):
            raise ValueError()
        return {"version": 1, "name": name, "uid": uid, "ips": list(ips), "dns": list(dns)}
    except (ValueError, TypeError, KeyError):
        raise ControllerError("enrollment_invalid") from None


def enrollment_set(value):
    """Load the operator enrollment file into {node name: (record, approve)}.

    Version 1 (one node dict, as originally installed on node02) stays valid
    and means "this node, approval allowed". Version 2 lists several nodes,
    each with its own explicit approve switch, so a node can be watched before
    it is trusted for unattended approval:

        {"version": 2, "nodes": [{"name": ..., "uid": ..., "ips": [...],
                                  "dns": [...], "approve": false}, ...]}

    Raises ControllerError("enrollment_invalid") for anything else, including
    duplicate node names or a missing/non-boolean approve switch.
    """
    try:
        if isinstance(value, dict) and value.get("version") == 1:
            record = enrollment(value)
            return {record["name"]: (record, True)}
        if (not isinstance(value, dict) or set(value) != {"version", "nodes"} or
                type(value["version"]) is not int or value["version"] != 2 or
                not isinstance(value["nodes"], list) or not 1 <= len(value["nodes"]) <= 16):
            raise ValueError()
        result = {}
        for entry in value["nodes"]:
            if not isinstance(entry, dict) or type(entry.get("approve")) is not bool:
                raise ValueError()
            record = enrollment({k: v for k, v in entry.items() if k != "approve"} | {"version": 1})
            if record["name"] in result:
                raise ValueError()
            result[record["name"]] = (record, entry["approve"])
        return result
    except ControllerError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ControllerError("enrollment_invalid") from None


def requester_node(csr):
    """Node name from the API-server-filled requester identity, or None.

    spec.username is set by the API server from the authenticated client, so
    it selects which enrollment to check against; it never grants anything by
    itself (validate_csr still checks every identity field against it).
    """
    username = csr.get("spec", {}).get("username")
    if isinstance(username, str) and username.startswith("system:node:"):
        name = username[len("system:node:"):]
        if 1 <= len(name) <= 253:
            return name
    return None


def _validity(certificate):
    """(not_before, not_after) as aware UTC datetimes on any cryptography version.

    node02 runs cryptography 3.4.8, which lacks the *_utc properties added in
    42.0; without this fallback every host-side issued/served check failed as
    "unverifiable" (observed 67 times for csr-s7q4l on 2026-11-17).
    """
    if hasattr(certificate, "not_valid_after_utc"):
        return certificate.not_valid_before_utc, certificate.not_valid_after_utc
    return (certificate.not_valid_before.replace(tzinfo=dt.timezone.utc),
            certificate.not_valid_after.replace(tzinfo=dt.timezone.utc))


def _request_digest(csr):
    raw = csr.get("spec", {}).get("request")
    if not isinstance(raw, str):
        raise ControllerError("csr_request_missing")
    return hashlib.sha256(raw.encode()).hexdigest()


def decide(csr, node, trusted, *, mode="observe", now=None):
    """One strict verdict; observation and approval share identical evidence."""
    if mode not in MODES:
        raise ControllerError("controller_mode_invalid")
    trusted = enrollment(trusted)
    failures = validate_csr(csr, node, trusted, now)
    meta = csr.get("metadata", {})
    if meta.get("name") and meta.get("name", "").startswith("bortus-"):
        # A diagnostic/qualification object is never approval-eligible.
        failures = sorted(set(failures) | {"diagnostic_object"})
    verdict = {
        "mode": mode,
        "csr": {"name": meta.get("name"), "uid": meta.get("uid"),
                "resourceVersion": meta.get("resourceVersion")},
        "node": trusted["name"],
        "requestSHA256": _request_digest(csr),
        "eligible": not failures,
        "reasons": failures,
        "checkedAt": (now or dt.datetime.now(dt.timezone.utc)).isoformat(),
    }
    return verdict


class ControllerState:
    """Durable decision history; approval is bounded to one per CSR UID."""

    def __init__(self, connection):
        self.db = connection
        size = self.db.execute("PRAGMA page_size").fetchone()[0]
        maximum = MAX_DATABASE_BYTES // size
        if self.db.execute(f"PRAGMA max_page_count={maximum}").fetchone()[0] > maximum:
            raise ControllerError("controller_database_limit")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS kubelet_csr_decisions (
                csr_uid TEXT PRIMARY KEY, csr_name TEXT NOT NULL, node TEXT NOT NULL,
                request_sha256 TEXT NOT NULL, eligible INTEGER NOT NULL,
                reasons TEXT NOT NULL, first_seen TEXT NOT NULL, last_checked TEXT NOT NULL,
                approved_at TEXT, approved_revision TEXT, issued_verified_at TEXT);
            CREATE TABLE IF NOT EXISTS kubelet_csr_approvals (
                csr_uid TEXT PRIMARY KEY, csr_name TEXT NOT NULL,
                approved_at TEXT NOT NULL, approved_revision TEXT NOT NULL);
        """)

    def record(self, verdict):
        meta, reasons = verdict["csr"], verdict["reasons"]
        if not meta.get("uid") or not meta.get("name"):
            raise ControllerError("csr_identity_invalid")
        previous = self.db.execute(
            "SELECT request_sha256, approved_at FROM kubelet_csr_decisions WHERE csr_uid=?",
            (meta["uid"],)).fetchone()
        if previous and previous[0] != verdict["requestSHA256"]:
            # A changed request under the same UID is a protocol violation; never
            # continue to eligibility, and keep the durable first-seen evidence.
            reasons = sorted(set(reasons) | {"request_changed_after_observation"})
            verdict = verdict | {"eligible": False, "reasons": reasons}
        with self.db:
            self.db.execute("""
                INSERT INTO kubelet_csr_decisions
                (csr_uid,csr_name,node,request_sha256,eligible,reasons,first_seen,last_checked)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(csr_uid) DO UPDATE SET
                    csr_name=excluded.csr_name, node=excluded.node, eligible=excluded.eligible,
                    reasons=excluded.reasons, last_checked=excluded.last_checked""", (
                meta["uid"], meta["name"], verdict["node"], verdict["requestSHA256"],
                int(verdict["eligible"]), json.dumps(reasons, sort_keys=True),
                verdict["checkedAt"], verdict["checkedAt"]))
            self.db.execute("""
                DELETE FROM kubelet_csr_decisions WHERE csr_uid NOT IN
                (SELECT csr_uid FROM kubelet_csr_decisions ORDER BY last_checked DESC LIMIT ?)
            """, (HISTORY_ROWS,))
        return verdict

    def approval_allowed(self, verdict, mode):
        """Observation never approves; approval needs a fresh eligible verdict."""
        if mode != "approve":
            return False
        if not verdict.get("eligible") or verdict.get("mode") != "approve":
            return False
        meta = verdict["csr"]
        previous = self.db.execute(
            "SELECT request_sha256, approved_at FROM kubelet_csr_decisions WHERE csr_uid=?",
            (meta["uid"],)).fetchone()
        if not previous or previous[0] != verdict["requestSHA256"]:
            return False
        # Exactly one approval per CSR UID, even across restarts or retries.
        return self.db.execute(
            "SELECT 1 FROM kubelet_csr_approvals WHERE csr_uid=?", (meta["uid"],)).fetchone() is None

    def mark_approved(self, csr, when):
        meta = csr["metadata"]
        with self.db:
            self.db.execute("INSERT INTO kubelet_csr_approvals VALUES (?,?,?,?)",
                            (meta["uid"], meta["name"], when, meta["resourceVersion"]))
            self.db.execute("""UPDATE kubelet_csr_decisions SET approved_at=?, approved_revision=?
                               WHERE csr_uid=? AND approved_at IS NULL""",
                            (when, meta["resourceVersion"], meta["uid"]))
        return approval_patch(csr, when)

    def release_approval(self, csr_uid):
        """Undo a recorded approval only when the cluster definitively lacks it.

        The exactly-once row is written before the PATCH so an uncertain outcome
        can never double-approve. When the API server confirms the object is NOT
        approved, keeping that row would wedge the CSR forever, so it is cleared
        to allow a later cycle to retry.
        """
        with self.db:
            self.db.execute("DELETE FROM kubelet_csr_approvals WHERE csr_uid=?", (csr_uid,))
            self.db.execute("""UPDATE kubelet_csr_decisions
                               SET approved_at=NULL, approved_revision=NULL
                               WHERE csr_uid=?""", (csr_uid,))
        return True

    def mark_issued_verified(self, csr_uid, when):
        with self.db:
            updated = self.db.execute(
                "UPDATE kubelet_csr_decisions SET issued_verified_at=? WHERE csr_uid=? AND approved_at IS NOT NULL",
                (when, csr_uid)).rowcount
        if updated != 1:
            raise ControllerError("issuance_without_approval_record")
        return updated

    def summary(self):
        row = self.db.execute("""SELECT count(*), coalesce(sum(approved_at IS NOT NULL),0),
                                        coalesce(sum(issued_verified_at IS NOT NULL),0)
                                 FROM kubelet_csr_decisions""").fetchone()
        return {"observed": row[0], "approved": row[1], "issuedVerified": row[2],
                "pendingApproval": row[0] - row[1]}


def verify_issued(csr, trusted, now=None):
    """Issuance is not installation: this checks only the returned certificate."""
    import base64
    import ipaddress

    from cryptography import x509

    trusted = enrollment(trusted)
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        raw = csr.get("status", {}).get("certificate")
        if not isinstance(raw, str) or not 1 <= len(raw) <= 65536:
            raise ValueError()
        certificate = x509.load_pem_x509_certificate(base64.b64decode(raw, validate=True))
        names = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        dns = {n.value for n in names if isinstance(n, x509.DNSName)}
        ips = {str(n.value) for n in names if isinstance(n, x509.IPAddress)}
        if (dns != set(trusted["dns"]) or
                ips != {str(ipaddress.ip_address(row)) for row in trusted["ips"]}):
            return False, "issued_identities_mismatch"
        not_before, not_after = _validity(certificate)
        if not_after <= now:
            return False, "issued_certificate_expired"
        if not_before > now + dt.timedelta(minutes=5):
            return False, "issued_certificate_not_yet_valid"
        usages = certificate.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        if x509.oid.ExtendedKeyUsageOID.SERVER_AUTH not in usages:
            return False, "issued_usage_not_serving"
        return True, None
    except Exception:
        return False, "issued_certificate_unverifiable"



def verify_served(certificate, trusted, now=None):
    """Check the certificate a node actually presents, not just what was issued.

    `certificate` is `(peer_der, issuer_der)` captured by a trusted TLS probe.
    A served certificate is only accepted when it chains to the enrolled issuer,
    carries exactly the enrolled identities, is currently valid and is usable
    for server authentication.
    """
    import datetime as dt
    import hashlib
    import ipaddress

    from cryptography import x509
    from cryptography.exceptions import InvalidSignature

    trusted = enrollment(trusted)
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        peer_der, issuer_der = certificate
        peer = x509.load_der_x509_certificate(peer_der)
        issuer = x509.load_der_x509_certificate(issuer_der)
        if peer.issuer != issuer.subject:
            return False, "served_issuer_mismatch", None
        # Signature check without any private material: verify with the public key.
        try:
            from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
            key = issuer.public_key()
            if isinstance(key, rsa.RSAPublicKey):
                key.verify(peer.signature, peer.tbs_certificate_bytes,
                           padding.PKCS1v15(), peer.signature_hash_algorithm)
            elif isinstance(key, ec.EllipticCurvePublicKey):
                key.verify(peer.signature, peer.tbs_certificate_bytes,
                           ec.ECDSA(peer.signature_hash_algorithm))
            else:
                return False, "served_issuer_key_unsupported", None
        except InvalidSignature:
            return False, "served_signature_invalid", None
        names = peer.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        dns = {n.value for n in names if isinstance(n, x509.DNSName)}
        ips = {str(n.value) for n in names if isinstance(n, x509.IPAddress)}
        if (dns != set(trusted["dns"]) or
                ips != {str(ipaddress.ip_address(row)) for row in trusted["ips"]}):
            return False, "served_identities_mismatch", None
        not_before, not_after = _validity(peer)
        if not not_before <= now <= not_after:
            return False, "served_certificate_not_currently_valid", None
        usages = peer.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        if x509.oid.ExtendedKeyUsageOID.SERVER_AUTH not in usages:
            return False, "served_usage_not_serving", None
        fingerprint = hashlib.sha256(peer_der).hexdigest()
        return True, None, fingerprint
    except Exception:
        return False, "served_certificate_unverifiable", None
