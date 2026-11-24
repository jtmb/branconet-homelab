#!/usr/bin/env python3
"""Separate fixed node03 broker; two exact reads, never monitor authority."""
import fcntl
import grp
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

from certificate_monitor_credentials import (
    AUDIENCE, CredentialError, ScopeViolation, WATCHDOG_ACCOUNT, refresh)
from certificate_monitor_runtime import root_managed_file

CODE = Path("/usr/local/libexec/bortus-certificate-watchdog")
CONFIG = Path("/etc/bortus-certificate-watchdog")
CA = CONFIG / "cluster-ca.crt"
ENROLLMENT = CONFIG / "identity.json"
RUNTIME = Path("/run/bortus-certificate-watchdog")
TOKEN = RUNTIME / "token"
BOOTSTRAP = Path("/etc/kubernetes/admin.conf")
CLI = Path("/usr/local/bin/kubectl")
SOURCES = (
    "certificate_monitor_credentials.py", "certificate_monitor_runtime.py",
    "certificate_monitor_process.py", "refresh-certificate-monitor-credential.py",
    "refresh-certificate-watchdog-credential.py",
)


def shared_adapter():
    # Import only the reviewed API/file primitives, never its monitor main().
    path = CODE / "refresh-certificate-monitor-credential.py"
    root_managed_file(path)
    spec = importlib.util.spec_from_file_location("watchdog_shared_api", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def api_type(base):
    class WatchdogApi(base):
        def read_uid(self):
            obj = self.command(self.bootstrap, ["get", "serviceaccount", WATCHDOG_ACCOUNT,
                                                "-n", "bortus", "-o", "json"])
            meta = obj.get("metadata", {})
            if (obj.get("kind") != "ServiceAccount" or meta.get("name") != WATCHDOG_ACCOUNT
                    or meta.get("namespace") != "bortus" or not isinstance(meta.get("uid"), str)):
                raise CredentialError("service_account_response_invalid")
            return meta["uid"]

        def mint(self, body):
            self.token_requests += 1
            return self.command(self.bootstrap, ["create", "--raw",
                "/api/v1/namespaces/bortus/serviceaccounts/" + WATCHDOG_ACCOUNT + "/token",
                "-f", "-"], body)

        def reads(self, token):
            for endpoint, kind, namespace, name, uid in (
                ("/api/v1/namespaces/bortus/configmaps/bortus-certificate-observations",
                 "ConfigMap", "bortus", "bortus-certificate-observations",
                 self.enrollment["observationsUID"]),
                ("/apis/coordination.k8s.io/v1/namespaces/kube-node-lease/leases/node02",
                 "Lease", "kube-node-lease", "node02", self.enrollment["leaseUID"]),
            ):
                obj = self.command(self.candidate.config_path, ["get", "--raw", endpoint],
                                   limit=768 * 1024 if kind == "ConfigMap" else 32768)
                metadata = obj.get("metadata", {})
                if (obj.get("kind") != kind or metadata.get("namespace") != namespace
                        or metadata.get("name") != name):
                    raise CredentialError("watchdog_metadata_response_invalid")
                if metadata.get("uid") != uid:
                    raise ScopeViolation("watchdog_enrolled_resource_recreated")
                if kind == "ConfigMap":
                    try:
                        policy_uid = json.loads(obj["data"]["snapshot.json"])["policy"]["uid"]
                    except (KeyError, TypeError, ValueError):
                        raise CredentialError("watchdog_observations_uninitialized") from None
                    if policy_uid != self.enrollment["policyUID"]:
                        raise ScopeViolation("watchdog_enrolled_policy_recreated")
                self.metadata_counts[kind] = 1
    return WatchdogApi


def main():
    candidate = None
    try:
        if (os.geteuid() != 0 or os.uname().nodename != "node03"
                or Path(__file__).absolute() != CODE / Path(__file__).name):
            raise CredentialError("fixed_watchdog_root_installation_required")
        for name in SOURCES:
            root_managed_file(CODE / name)
        if root_managed_file(ENROLLMENT).st_size > 4096:
            raise CredentialError("enrollment_size_limit")
        value = json.loads(ENROLLMENT.read_text())
        if (set(value) != {"version", "serviceAccountUID", "audience", "kubectlSHA256",
                          "observationsUID", "policyUID", "leaseUID"}
                or type(value["version"]) is not int or value["version"] != 1
                or value["audience"] != AUDIENCE
                or any(not isinstance(value[k], str) or not re.fullmatch(r"[-A-Za-z0-9]{1,128}", value[k])
                       for k in ("serviceAccountUID", "observationsUID", "policyUID", "leaseUID"))
                or not isinstance(value["kubectlSHA256"], str)
                or not re.fullmatch(r"[a-f0-9]{64}", value["kubectlSHA256"])):
            raise CredentialError("watchdog_enrollment_invalid")
        root_managed_file(CLI)
        if hashlib.sha256(CLI.read_bytes()).hexdigest() != value["kubectlSHA256"]:
            raise CredentialError("kubectl_pin_mismatch")
        root_managed_file(CA)
        if root_managed_file(BOOTSTRAP).st_mode & 0o077:
            raise CredentialError("watchdog_private_bootstrap_required")
        info = RUNTIME.lstat()
        group = grp.getgrnam(WATCHDOG_ACCOUNT).gr_gid
        if (not RUNTIME.is_dir() or RUNTIME.is_symlink() or info.st_uid != 0
                or info.st_gid != group or info.st_mode & 0o027):
            raise CredentialError("private_watchdog_root_runtime_required")
        if TOKEN.exists() or TOKEN.is_symlink():
            info = root_managed_file(TOKEN)
            if info.st_nlink != 1 or info.st_gid != group or info.st_mode & 0o007:
                raise CredentialError("active_token_ownership_invalid")
        lock_path = RUNTIME / ".refresh.lock"
        if lock_path.exists() or lock_path.is_symlink():
            root_managed_file(lock_path)
        os.umask(0o077)
        fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print(json.dumps({"state": "watchdog-credential-refresh-already-running"}))
                return 0
            shared = shared_adapter()
            candidate = shared.CandidateFiles(RUNTIME, group, ca_path=CA)
            api = api_type(shared.ApiQualification)(BOOTSTRAP, CLI, CA, candidate)
            api.enrollment = value

            def quarantine():
                if TOKEN.exists():
                    root_managed_file(TOKEN)
                    TOKEN.unlink()
                    candidate.sync_directory()

            result = refresh(
                profile="watchdog", pinned_uid=value["serviceAccountUID"], read_uid=api.read_uid,
                mint=api.mint, review_subject=api.subject, review_access=api.access,
                probe_reads=api.reads, publish=candidate.publish, quarantine=quarantine)
            result["metadataCounts"] = api.metadata_counts
            print(json.dumps(result))
            return 0
    except Exception as error:
        print(json.dumps({"state": "watchdog-credential-unavailable",
                          "reason": str(error) if isinstance(error, CredentialError) else "broker_unavailable",
                          "candidatePublished": bool(candidate and candidate.published)}))
        return 1
    finally:
        if candidate is not None:
            candidate.close()


if __name__ == "__main__":
    raise SystemExit(main())
