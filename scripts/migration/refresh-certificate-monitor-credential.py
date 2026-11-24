#!/usr/bin/env python3
"""Root-only external token broker; never invoked by BORTUS or the monitor.

Only the fixed ServiceAccount TokenRequest and non-mutating qualification are
supported. Installation/enrollment/activation are separate operator operations.
"""
import fcntl
import grp
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

from certificate_monitor_credentials import (ACCOUNT, AUDIENCE, NAMESPACE,
                                             CredentialError, refresh)
from certificate_monitor_process import run_bounded
from certificate_monitor_runtime import (HOST_CA, HOST_CODE, HOST_KUBECTL,
                                         HOST_SOURCES, HOST_TOKEN, root_managed_file)

ENROLLMENT = Path("/etc/bortus-certificate-monitor/identity.json")
BOOTSTRAP = Path("/etc/kubernetes/admin.conf")
RUNTIME = HOST_TOKEN.parent
SERVER = "https://192.168.0.251:6443"
BROKER_SOURCES = (*HOST_SOURCES, "certificate_monitor_credentials.py",
                  "refresh-certificate-monitor-credential.py")


class CandidateFiles:
    """Root-private scratch credentials; only the approved token is published."""
    def __init__(self, directory, group, *, ca_path=HOST_CA):
        self.directory, self.group = directory, group
        self.ca_path = ca_path
        self.token_path = None
        self.config_path = None
        self.published = False

    def prepare(self, token):
        if self.token_path is not None:
            return
        fd, name = tempfile.mkstemp(prefix=".pending-token-", dir=self.directory)
        self.token_path = Path(name)
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(token)
            stream.flush()
            os.fsync(stream.fileno())
        fd, name = tempfile.mkstemp(prefix=".pending-config-", dir=self.directory)
        self.config_path = Path(name)
        config = {
            "apiVersion": "v1", "kind": "Config",
            "clusters": [{"name": "api", "cluster": {
                "server": SERVER, "certificate-authority": str(self.ca_path)}}],
            "users": [{"name": "candidate", "user": {"tokenFile": str(self.token_path)}}],
            "contexts": [{"name": "candidate", "context": {"cluster": "api", "user": "candidate"}}],
            "current-context": "candidate",
        }
        with os.fdopen(fd, "w") as stream:
            json.dump(config, stream)
            stream.flush()
            os.fsync(stream.fileno())

    def publish(self, token):
        if self.token_path is None:
            raise CredentialError("candidate_not_qualified")
        # No token bytes enter arguments, logs, Git or SQLite. A same-directory
        # atomic replacement makes readers see the old complete file or new one.
        fd = os.open(self.token_path, os.O_WRONLY | os.O_NOFOLLOW)
        try:
            os.fchown(fd, -1, self.group)
            os.fchmod(fd, 0o640)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(self.token_path, self.directory / "token")
        self.token_path = None
        self.published = True
        self.sync_directory()

    def sync_directory(self):
        fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def close(self):
        for path in (self.token_path, self.config_path):
            if path is not None:
                path.unlink(missing_ok=True)
        self.sync_directory()


class ApiQualification:
    """Same bounded API adapter for the root broker and explicit operator proof."""
    def __init__(self, bootstrap, binary, ca, candidate):
        self.bootstrap, self.binary, self.ca, self.candidate = bootstrap, binary, ca, candidate
        self.deadline = time.monotonic() + 180
        self.token_requests = 0
        self.metadata_counts = {}

    def command(self, config, args, body=None, limit=65536):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise CredentialError("credential_qualification_timeout")
        raw = run_bounded(
            [str(self.binary), "--kubeconfig", str(config), "--server=" + SERVER,
             "--certificate-authority=" + str(self.ca), "--request-timeout=15s", *args],
            data=json.dumps(body).encode() if body is not None else None,
            output_limit=limit, timeout=min(20, remaining))
        return json.loads(raw)

    def read_uid(self):
        value = self.command(self.bootstrap, ["get", "serviceaccount", ACCOUNT, "-n", NAMESPACE, "-o", "json"])
        meta = value.get("metadata", {})
        if (value.get("kind") != "ServiceAccount" or meta.get("name") != ACCOUNT or
                meta.get("namespace") != NAMESPACE or not isinstance(meta.get("uid"), str)):
            raise CredentialError("service_account_response_invalid")
        return meta["uid"]

    def mint(self, body):
        self.token_requests += 1
        return self.command(self.bootstrap, ["create", "--raw",
            f"/api/v1/namespaces/{NAMESPACE}/serviceaccounts/{ACCOUNT}/token", "-f", "-"], body)

    def subject(self, token):
        self.candidate.prepare(token)
        return self.command(self.candidate.config_path, ["create", "--raw",
            "/apis/authentication.k8s.io/v1/selfsubjectreviews", "-f", "-"],
            {"apiVersion": "authentication.k8s.io/v1", "kind": "SelfSubjectReview", "spec": {}})

    def access(self, token, attributes):
        return self.command(self.candidate.config_path, ["create", "--raw",
            "/apis/authorization.k8s.io/v1/selfsubjectaccessreviews", "-f", "-"],
            {"apiVersion": "authorization.k8s.io/v1", "kind": "SelfSubjectAccessReview",
             "spec": {"resourceAttributes": attributes}})

    def reads(self, token):
        for endpoint, expected_kind in (
                ("/apis/cert-manager.io/v1/certificates", "CertificateList"),
                ("/apis/certificates.k8s.io/v1/certificatesigningrequests", "CertificateSigningRequestList")):
            # Generic kubectl get rewrites these to kind: List.
            value = self.command(self.candidate.config_path, ["get", "--raw", endpoint],
                                 limit=2 * 1024 * 1024)
            if (not isinstance(value, dict) or value.get("kind") != expected_kind or
                    not isinstance(value.get("items"), (list, type(None))) or
                    value.get("metadata", {}).get("continue")):
                raise CredentialError("metadata_probe_incomplete")
            self.metadata_counts[expected_kind] = len(value.get("items") or [])


def main():
    candidate = None
    try:
        if os.geteuid() != 0 or Path(__file__).absolute() != HOST_CODE / Path(__file__).name:
            raise CredentialError("fixed_root_installation_required")
        for name in BROKER_SOURCES:
            root_managed_file(HOST_CODE / name)
        if root_managed_file(ENROLLMENT).st_size > 4096:
            raise CredentialError("enrollment_size_limit")
        enrollment = json.loads(ENROLLMENT.read_text())
        if (set(enrollment) != {"version", "serviceAccountUID", "audience", "kubectlSHA256"} or
                type(enrollment["version"]) is not int or enrollment["version"] != 1 or
                enrollment["audience"] != AUDIENCE):
            raise CredentialError("enrollment_invalid")
        root_managed_file(HOST_KUBECTL)
        if hashlib.sha256(HOST_KUBECTL.read_bytes()).hexdigest() != enrollment["kubectlSHA256"]:
            raise CredentialError("kubectl_pin_mismatch")
        root_managed_file(HOST_CA)
        root_managed_file(BOOTSTRAP)
        # RuntimeDirectory is made by the root broker unit, not by the monitor.
        info = RUNTIME.lstat()
        if (not RUNTIME.is_dir() or RUNTIME.is_symlink() or info.st_uid != 0 or
                info.st_mode & 0o027):
            raise CredentialError("private_root_runtime_required")
        group = grp.getgrnam(ACCOUNT).gr_gid
        if info.st_gid != group:
            raise CredentialError("runtime_group_mismatch")
        if HOST_TOKEN.exists() or HOST_TOKEN.is_symlink():
            info = root_managed_file(HOST_TOKEN)
            if info.st_nlink != 1 or info.st_gid != group or info.st_mode & 0o007:
                raise CredentialError("active_token_ownership_invalid")
        lock_path = RUNTIME / ".refresh.lock"
        if lock_path.exists() or lock_path.is_symlink():
            root_managed_file(lock_path)
        os.umask(0o077)
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(lock_fd, "a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print(json.dumps({"state": "credential-refresh-already-running"}))
                return 0
            candidate = CandidateFiles(RUNTIME, group)
            api = ApiQualification(BOOTSTRAP, HOST_KUBECTL, HOST_CA, candidate)

            def quarantine():
                if HOST_TOKEN.exists():
                    root_managed_file(HOST_TOKEN)
                    HOST_TOKEN.unlink()
                    candidate.sync_directory()

            try:
                result = refresh(pinned_uid=enrollment["serviceAccountUID"], read_uid=api.read_uid,
                                 mint=api.mint, review_subject=api.subject, review_access=api.access,
                                 probe_reads=api.reads, publish=candidate.publish, quarantine=quarantine)
                result["metadataCounts"] = api.metadata_counts
            finally:
                candidate.close()
            print(json.dumps(result), flush=True)
        return 0
    except Exception as error:
        reason = str(error) if isinstance(error, CredentialError) else "credential_refresh_unavailable"
        print(json.dumps({"state": "credential-refresh-failed", "reason": reason,
                          "candidatePublished": bool(candidate and candidate.published),
                          "publicationVerified": False}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
