#!/usr/bin/env python3
"""One actual watchdog identity proof; candidate credentials stay in sealed RAM."""
import base64
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

from certificate_monitor_credentials import (
    CredentialError, ScopeViolation, WATCHDOG_ACCOUNT, refresh)
from certificate_monitor_process import run_bounded

SPEC = importlib.util.spec_from_file_location(
    "watchdog_identity_api", Path(__file__).with_name("stage-ntfy-cluster.py"))
API = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(API)
WORK = API.STAGE / "watchdog-host-activation"
CLI = API.BASE[0]
# Stable Linux UAPI values; some retained Python builds omit these names.
# Kernel-reported seals are mandatory, not a best-effort compatibility path.
ADD_SEALS = getattr(fcntl, "F_ADD_SEALS", 1033)
GET_SEALS = getattr(fcntl, "F_GET_SEALS", 1034)
REQUIRED_SEALS = 0x01 | 0x02 | 0x04 | 0x08


def save(name, value):
    with (WORK / name).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    assert json.loads((WORK / "identity-flux-result.json").read_text())["passed"]
    pins = json.loads((WORK / "identity-flux-result.json").read_text())
    preflight = json.loads((WORK / "preflight-result.json").read_text())
    save("effective-identity-started.json", {
        "serviceAccountUID": pins["serviceAccount"]["uid"],
        "sourceSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "tokenLifetimeSeconds": 3600, "sealedMemoryOnly": True,
        "noHostInstallOrCredentialPublication": True})
    ca_obj = API.call(["get", "configmap", "kube-root-ca.crt", "-n", "bortus", "-o", "json"])
    ca = ca_obj["data"]["ca.crt"].encode()
    assert hashlib.sha256(ca).hexdigest() == preflight[
        "rootBootstrapAndPublicToolMetadata"]["/etc/kubernetes/pki/ca.crt"]["sha256"]
    fd = None
    qualified = False
    denial_count = 0

    def prepare(token):
        nonlocal fd
        if fd is not None:
            return
        config = {
            "apiVersion": "v1", "kind": "Config",
            "clusters": [{"name": "api", "cluster": {
                "server": "https://192.168.0.251:6443",
                "certificate-authority-data": base64.b64encode(ca).decode()}}],
            "users": [{"name": "candidate", "user": {"token": token}}],
            "contexts": [{"name": "candidate", "context": {"cluster": "api", "user": "candidate"}}],
            "current-context": "candidate"}
        fd = os.memfd_create("watchdog-candidate", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
        os.fchmod(fd, 0o600)
        raw = json.dumps(config).encode()
        with os.fdopen(os.dup(fd), "wb") as stream:
            stream.write(raw)
        os.lseek(fd, 0, os.SEEK_SET)
        fcntl.fcntl(fd, ADD_SEALS, REQUIRED_SEALS)
        if fcntl.fcntl(fd, GET_SEALS) & REQUIRED_SEALS != REQUIRED_SEALS:
            raise CredentialError("sealed_candidate_config_required")

    def command(args, body=None, limit=768 * 1024):
        assert fd is not None
        cmd = [CLI, "--kubeconfig", f"/proc/{os.getpid()}/fd/{fd}",
               "--server=https://192.168.0.251:6443", "--request-timeout=15s", *args]
        raw = run_bounded(cmd, data=json.dumps(body).encode() if body is not None else None,
                          output_limit=limit, timeout=20)
        return json.loads(raw)

    def subject(token):
        prepare(token)
        return command(["create", "--raw", "/apis/authentication.k8s.io/v1/selfsubjectreviews",
                        "-f", "-"], {"apiVersion": "authentication.k8s.io/v1",
                                     "kind": "SelfSubjectReview", "spec": {}})

    def access(token, attributes):
        return command(["create", "--raw", "/apis/authorization.k8s.io/v1/selfsubjectaccessreviews",
                        "-f", "-"], {"apiVersion": "authorization.k8s.io/v1",
                                     "kind": "SelfSubjectAccessReview",
                                     "spec": {"resourceAttributes": attributes}})

    def uid():
        obj = API.call(["get", "serviceaccount", WATCHDOG_ACCOUNT, "-n", "bortus", "-o", "json"])
        return obj["metadata"]["uid"]

    def reads(token):
        nonlocal denial_count
        for endpoint, kind, expected_uid in (
            ("/api/v1/namespaces/bortus/configmaps/bortus-certificate-observations",
             "ConfigMap", preflight["observations"]["uid"]),
            ("/apis/coordination.k8s.io/v1/namespaces/kube-node-lease/leases/node02",
             "Lease", preflight["lease"]["uid"]),
        ):
            obj = command(["get", "--raw", endpoint])
            if obj.get("kind") != kind or obj.get("metadata", {}).get("uid") != expected_uid:
                raise ScopeViolation("watchdog_enrolled_resource_recreated")
        paths = [
            "/api/v1/namespaces/bortus/configmaps/bortus-certificate-policy",
            "/api/v1/namespaces/bortus/configmaps",
            "/apis/cert-manager.io/v1/certificates",
            "/apis/coordination.k8s.io/v1/namespaces/kube-node-lease/leases/node01",
            "/api/v1/namespaces/default/pods",
            "/apis/certificates.k8s.io/v1/certificatesigningrequests",
        ]
        commands = [(["get", "--raw", path], None) for path in paths]
        commands.append((["patch", "configmap", "bortus-certificate-observations", "-n", "bortus",
                          "--type=json", "--dry-run=server", "--patch-file=/dev/stdin", "-o", "json"],
                         [{"op": "test", "path": "/metadata/uid",
                           "value": preflight["observations"]["uid"]}]))
        for args, body in commands:
            # Outputs are inspected only in memory to distinguish actual
            # Forbidden from a connectivity/authentication failure.
            result = subprocess.run(
                [CLI, "--kubeconfig", f"/proc/{os.getpid()}/fd/{fd}",
                 "--request-timeout=15s", *args],
                input=json.dumps(body).encode() if body is not None else None,
                capture_output=True, timeout=20)
            if (not result.returncode or len(result.stdout) + len(result.stderr) > 65536
                    or b"(Forbidden)" not in result.stderr):
                raise ScopeViolation("watchdog_actual_denial_not_established")
            denial_count += 1

    def publish(token):
        nonlocal qualified
        qualified = True  # Qualification only; never publish a host credential.

    try:
        result = refresh(
            profile="watchdog", pinned_uid=pins["serviceAccount"]["uid"], read_uid=uid,
            mint=lambda body: API.call(["create", "--raw",
                "/api/v1/namespaces/bortus/serviceaccounts/" + WATCHDOG_ACCOUNT + "/token",
                "-f", "-"], body),
            review_subject=subject, review_access=access, probe_reads=reads,
            publish=publish, quarantine=lambda: None)
        assert qualified
        result.update(passed=True, effectiveAllowChecks=2,
                      effectiveDenyChecks=sum(not row["expectedAllowed"] for row in result["permissionChecks"]),
                      actualExactReads=2, actualForbiddenChecks=denial_count,
                      candidateConfigSealedInRAM=True, hostCredentialPublished=False,
                      diskCredentialPayloadCreated=False, noRevocationClaim=True)
        save("effective-identity-result.json", result)
        print(json.dumps({key: result[key] for key in (
            "passed", "subject", "serviceAccountUID", "effectiveAllowChecks", "effectiveDenyChecks",
            "actualExactReads", "actualForbiddenChecks", "candidateConfigSealedInRAM",
            "hostCredentialPublished")}, indent=2))
    except Exception as error:
        save("effective-identity-failure.json", {
            "reason": str(error) if isinstance(error, CredentialError) else "qualification_failed",
            "hostCredentialPublished": False, "reconcileBeforeRetry": True})
        raise RuntimeError("watchdog_identity_qualification_failed") from None
    finally:
        if fd is not None:
            os.close(fd)


if __name__ == "__main__":
    main()
