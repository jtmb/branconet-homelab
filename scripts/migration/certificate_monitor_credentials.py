"""Short-lived credential qualification; no values in results, errors or logs.

JWT parsing checks the TokenRequest response contract, not its signature.
The authenticated API's SelfSubjectReview is the independent token verifier.
"""
import base64
import datetime as dt
import json
import re

NAMESPACE = "bortus"
ACCOUNT = "bortus-certificate-monitor"
WATCHDOG_ACCOUNT = "bortus-certificate-watchdog"
SUBJECT = f"system:serviceaccount:{NAMESPACE}:{ACCOUNT}"
AUDIENCE = "https://kubernetes.default.svc.cluster.local"
REQUEST_SECONDS = 3600


class CredentialError(RuntimeError):
    """Fixed public reason code, never token/config/backend data."""


class ScopeViolation(CredentialError):
    """Known unsafe identity/permission: quarantine the active token."""


def account_for(profile):
    if profile == "monitor":
        return ACCOUNT
    if profile == "watchdog":
        return WATCHDOG_ACCOUNT
    if profile == "csr":
        return "bortus-csr-controller"
    raise CredentialError("credential_profile_invalid")


def permissions(profile="monitor"):
    """Representative effective boundaries, not an exhaustive RBAC proof."""
    account = account_for(profile)
    allow = [
        ("list", "cert-manager.io", "certificates", "", "", ""),
        ("get", "cert-manager.io", "certificates", NAMESPACE, "qualification-probe", ""),
        ("list", "certificates.k8s.io", "certificatesigningrequests", "", "", ""),
        ("get", "certificates.k8s.io", "certificatesigningrequests", "", "qualification-probe", ""),
        ("get", "", "configmaps", NAMESPACE, "bortus-certificate-policy", ""),
        ("get", "", "configmaps", NAMESPACE, "bortus-certificate-observations", ""),
        ("patch", "", "configmaps", NAMESPACE, "bortus-certificate-observations", ""),
    ]
    deny = [
        ("list", "", "secrets", "", "", ""),
        ("get", "", "secrets", NAMESPACE, "bortus-jwt", ""),
        ("get", "", "secrets", "default", "qualification-probe", ""),
        ("patch", "", "configmaps", NAMESPACE, "bortus-certificate-policy", ""),
        ("get", "", "configmaps", NAMESPACE, "unrelated-config", ""),
        ("patch", "", "configmaps", NAMESPACE, "unrelated-config", ""),
        ("create", "", "configmaps", NAMESPACE, "", ""),
        ("delete", "", "configmaps", NAMESPACE, "bortus-certificate-observations", ""),
        ("create", "", "serviceaccounts", NAMESPACE, account, "token"),
        ("update", "certificates.k8s.io", "certificatesigningrequests", "", "qualification-probe", "approval"),
        ("approve", "certificates.k8s.io", "signers", "", "kubernetes.io/kubelet-serving", ""),
        ("sign", "certificates.k8s.io", "signers", "", "kubernetes.io/kubelet-serving", ""),
        ("create", "", "pods", NAMESPACE, "", ""),
        ("create", "", "pods", NAMESPACE, "qualification-probe", "exec"),
        ("get", "", "nodes", "", "node02", "proxy"),
        ("patch", "apps", "deployments", NAMESPACE, "bortus", ""),
        ("escalate", "rbac.authorization.k8s.io", "clusterroles", "", "cluster-admin", ""),
        ("bind", "rbac.authorization.k8s.io", "clusterroles", "", "cluster-admin", ""),
        ("impersonate", "", "users", "", "system:admin", ""),
    ]
    if profile == "watchdog":
        observations = ("get", "", "configmaps", NAMESPACE, "bortus-certificate-observations", "")
        deny += [row for row in allow if row != observations]
        deny += [
            ("list", "", "configmaps", NAMESPACE, "", ""),
            ("list", "coordination.k8s.io", "leases", "kube-node-lease", "", ""),
            ("get", "coordination.k8s.io", "leases", "kube-node-lease", "node01", ""),
            ("patch", "coordination.k8s.io", "leases", "kube-node-lease", "node02", ""),
            ("get", "", "nodes", "", "node02", ""),
        ]
        allow = [observations, ("get", "coordination.k8s.io", "leases",
                                "kube-node-lease", "node02", "")]
    if profile == "csr":
        # Approval is granted to this profile only for the kubelet-serving signer,
        # and only through the approval subresource. Everything else stays denied.
        allow = [("get", "certificates.k8s.io", "certificatesigningrequests", "", "", ""),
                 ("list", "certificates.k8s.io", "certificatesigningrequests", "", "", ""),
                 ("get", "certificates.k8s.io", "certificatesigningrequests", "", "", "approval"),
                 ("patch", "certificates.k8s.io", "certificatesigningrequests", "", "", "approval"),
                 ("update", "certificates.k8s.io", "certificatesigningrequests", "", "", "approval"),
                 ("approve", "certificates.k8s.io", "signers", "", "kubernetes.io/kubelet-serving", ""),
                 ("get", "", "nodes", "", "", ""),
                 ("list", "", "nodes", "", "", "")]
        deny = [row for row in deny if row[2] not in ("certificatesigningrequests", "nodes", "signers")]
        deny += [
            ("create", "certificates.k8s.io", "certificatesigningrequests", "", "", ""),
            ("update", "certificates.k8s.io", "certificatesigningrequests", "", "", ""),
            ("approve", "certificates.k8s.io", "signers", "", "kubernetes.io/kube-apiserver-client", ""),
            ("sign", "certificates.k8s.io", "signers", "", "kubernetes.io/kubelet-serving", ""),
            ("watch", "certificates.k8s.io", "certificatesigningrequests", "", "", ""),
            ("delete", "certificates.k8s.io", "certificatesigningrequests", "", "", ""),
            ("patch", "", "nodes", "", "node02", ""),
        ]
    return [(True, row) for row in allow] + [(False, row) for row in dict.fromkeys(deny)]


def access_attributes(row):
    verb, group, resource, namespace, name, subresource = row
    value = {"verb": verb, "group": group, "resource": resource}
    for key, part in (("namespace", namespace), ("name", name), ("subresource", subresource)):
        if part:
            value[key] = part
    return value


def token_contract(response, uid, now, *, profile="monitor"):
    account_name = account_for(profile)
    subject = f"system:serviceaccount:{NAMESPACE}:{account_name}"
    try:
        status = response["status"]
        token = status["token"]
        if (not isinstance(token, str) or not 1 <= len(token) <= 16384 or
                not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token)):
            raise ValueError()
        part = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        expiry = dt.datetime.fromisoformat(status["expirationTimestamp"].replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            raise ValueError()
        ttl = (expiry - now).total_seconds()
        numeric = [claims.get(key) for key in ("exp", "iat", "nbf")]
        if (not all(type(value) is int for value in numeric) or not 300 <= ttl <= REQUEST_SECONDS + 60 or
                abs(claims["exp"] - expiry.timestamp()) > 1 or
                not -60 <= now.timestamp() - claims["iat"] <= 120 or
                claims["nbf"] > now.timestamp() + 60):
            raise ValueError()
        account = claims["kubernetes.io"]["serviceaccount"]
        if (claims.get("iss") != AUDIENCE or claims.get("aud") != [AUDIENCE] or
                claims.get("sub") != subject or claims["kubernetes.io"].get("namespace") != NAMESPACE or
                account.get("name") != account_name or account.get("uid") != uid):
            raise ScopeViolation("issued_token_identity_mismatch")
        return token, expiry
    except ScopeViolation:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, UnicodeError):
        raise CredentialError("token_response_invalid") from None


def refresh(*, pinned_uid, read_uid, mint, review_subject, review_access,
            probe_reads, publish, quarantine, now=None, profile="monitor"):
    """Publish only after API-authenticated identity/permissions and UID recheck.

    Review and list probes perform no application mutations. Known unsafe
    identity/permission removes the active owned token; transient failure leaves
    it intact until its existing expiry, and never publishes the candidate.
    """
    account_name = account_for(profile)
    subject_name = f"system:serviceaccount:{NAMESPACE}:{account_name}"
    clock = (lambda: now) if now is not None else lambda: dt.datetime.now(dt.timezone.utc)
    issued_at = clock()
    if not isinstance(pinned_uid, str) or not re.fullmatch(r"[a-zA-Z0-9-]{1,128}", pinned_uid):
        raise CredentialError("enrollment_invalid")
    try:
        if read_uid() != pinned_uid:
            raise ScopeViolation("service_account_recreated")
        response = mint({"apiVersion": "authentication.k8s.io/v1", "kind": "TokenRequest",
                         "spec": {"audiences": [AUDIENCE], "expirationSeconds": REQUEST_SECONDS}})
        token, expires = token_contract(response, pinned_uid, issued_at, profile=profile)
        subject = review_subject(token)
        info = subject.get("status", {}).get("userInfo", {})
        groups = info.get("groups", [])
        if (info.get("username") != subject_name or info.get("uid") != pinned_uid or
                not isinstance(groups, list) or set(groups) != {
                    "system:serviceaccounts", "system:serviceaccounts:bortus", "system:authenticated"}):
            raise ScopeViolation("authenticated_identity_mismatch")
        checked = []
        for expected, row in permissions(profile):
            result = review_access(token, access_attributes(row))
            status = result.get("status", {})
            if status.get("evaluationError") or type(status.get("allowed")) is not bool:
                raise CredentialError("access_review_incomplete")
            if status["allowed"] is not expected:
                raise ScopeViolation("effective_permission_mismatch")
            checked.append({"expectedAllowed": expected, "attributes": access_attributes(row)})
        probe_reads(token)  # Actual non-mutating metadata reads, not just reviews.
        if read_uid() != pinned_uid:
            raise ScopeViolation("service_account_recreated")
        if (expires - clock()).total_seconds() < 300:
            raise CredentialError("credential_expiry_too_close")
        publish(token)
        return {"state": "credential-refreshed", "subject": subject_name, "serviceAccountUID": pinned_uid,
                "expiresAt": expires.isoformat(), "permissionChecks": checked,
                "tokenPersistedInGitOrSQLite": False}
    except ScopeViolation:
        quarantine()
        raise
