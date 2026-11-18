#!/usr/bin/env python3
"""Controlled kubelet serving-certificate rotation on node02 (approval gated).

Moves kubelet's current serving file aside with a root-only backup, restarts
kubelet so it requests a fresh serving CSR, approves exactly that CSR through the
validated controller for the enrolled node only, and verifies the certificate
kubelet serves equals the issued certificate. Restores the backup and restarts
kubelet if any stage fails before acceptance. Artifacts are attempt-scoped so a
reconciled retry never overwrites earlier evidence.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
STAGE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/"
             "bortus-operator-recovery/certificates-qualification-20261116")
WORK = STAGE / "kubelet-servertlsbootstrap"
CSR_WORK = STAGE / "kubelet-csr-observation"
NODE = "192.168.0.6"
KUBECTL = "/home/brajam/.local/share/branconet-migration/bin/kubectl"
# Per-attempt backup: a refusal or failure must never restore a previous
# attempt's certificate (2026-11-18 review finding — the fixed shared path let
# a pre-flight refusal overwrite the serving file with an older backup).
BACKUP = Path("/root/bortus-kubelet-pki-backup") / "attempt"
SPEC = importlib.util.spec_from_file_location(
    "rotation_api", Path(__file__).with_name("stage-ntfy-cluster.py"))
API = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(API)

ASIDE = r'''
import json,os,shutil,subprocess,time
from pathlib import Path
pki=Path('/var/lib/kubelet/pki');backup=Path(BACKUP)
# A fresh, verified backup per attempt. Refuse rather than reuse: restoring a
# previous attempt's certificate over a different current one is the defect
# this structure exists to prevent.
backup.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
if backup.exists():
    raise SystemExit('per_attempt_backup_already_exists_refusing_reuse')
backup.mkdir(mode=0o700)
items=[]
for source in sorted(pki.glob('kubelet-server-*.pem')):
    if source.is_symlink():
        items.append({'name':source.name,'symlink_to':os.readlink(source)})
    else:
        shutil.copy2(source,backup/source.name);os.chmod(backup/source.name,0o600)
        items.append({'name':source.name})
(backup/'manifest.json').write_text(json.dumps({'items':items}))
for source in sorted(pki.glob('kubelet-server-*.pem')):
    source.unlink()
subprocess.run(['systemctl','restart','kubelet.service'],check=True,capture_output=True,timeout=120)
time.sleep(3)
state=subprocess.check_output(['systemctl','is-active','kubelet.service'],text=True).strip()
print(json.dumps({'backedUp':items,'backup':str(backup),'kubelet':state}))
'''

RESTORE = r'''
import json,os,shutil,subprocess
from pathlib import Path
pki=Path('/var/lib/kubelet/pki');backup=Path(BACKUP)
manifest=json.loads((backup/'manifest.json').read_text())
restored=[]
for entry in manifest['items']:
    dest=pki/entry['name']
    if dest.is_symlink() or dest.exists(): dest.unlink()
    if entry.get('symlink_to'):
        os.symlink(entry['symlink_to'],dest)
    else:
        shutil.copy2(backup/entry['name'],dest);os.chmod(dest,0o600)
    restored.append(entry['name'])
subprocess.run(['systemctl','restart','kubelet.service'],check=True,capture_output=True,timeout=120)
print(json.dumps({'restored':restored,'backup':str(backup)}))
'''

SERVED = r'''
import hashlib,json,socket,ssl
from cryptography import x509
# Capture the served certificate without verification: kubelet legitimately
# serves its self-signed certificate while a rotation request is pending, and
# the fingerprint comparison (not TLS trust) is the evidence here.
ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
with socket.create_connection(('127.0.0.1',10250),timeout=8) as raw:
    with ctx.wrap_socket(raw,server_hostname='node02') as tls:
        der=tls.getpeercert(binary_form=True);version=tls.version()
cert=x509.load_der_x509_certificate(der)
names=cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
print(json.dumps({'fingerprintSHA256':hashlib.sha256(der).hexdigest(),
 'dns':sorted(n.value for n in names if isinstance(n,x509.DNSName)),
 'ips':sorted(str(n.value) for n in names if isinstance(n,x509.IPAddress)),
 'notAfter':(cert.not_valid_after_utc if hasattr(cert,'not_valid_after_utc') else
             cert.not_valid_after.replace(tzinfo=__import__('datetime').timezone.utc)).isoformat(),
 'issuer':cert.issuer.rfc4514_string(),'tlsVersion':version,
 'clusterCaSigned':cert.issuer.rfc4514_string()=='CN=kubernetes'}))
'''


def save(stem, name, value):
    with (WORK / (stem + "-" + name + ".json")).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def remote(password, code, timeout=180):
    result = subprocess.run([
        "ssh", "-p", "2002", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", "ConnectTimeout=8", "-i", "/home/brajam/.ssh/id_ed25519", "james@" + NODE,
        "sudo -S -p '' /usr/bin/python3 -B -c " + shlex.quote(code)],
        input=(password + "\n").encode(), capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("remote_step_failed")
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt", help="Short path-safe attempt label")
    args = parser.parse_args()
    attempt = args.attempt
    if not attempt.replace("-", "").isalnum() or len(attempt) > 24:
        raise SystemExit("short path-safe attempt label required")
    # Per-attempt backup directory: a refusal must never touch the serving
    # files, and a failure must restore only this attempt's own backup.
    backup = str(BACKUP / attempt)
    stem = "rotation-" + attempt
    started = WORK / (stem + ".started.json")
    assert not started.exists(), "reconcile_existing_rotation"
    assert not (WORK / (stem + ".result.json")).exists()
    assert json.loads((CSR_WORK / "renewal-acceptance.json").read_text())["passed"]
    pre = json.loads((WORK / "pre-state.json").read_text())
    assert pre["serverTLSBootstrap"] is True
    pre_served = json.loads((CSR_WORK / "served-endpoint-result.json").read_text())
    started.write_text(json.dumps({
        "attempt": attempt, "preServedFingerprint": pre_served["fingerprintSHA256"],
        "backupPath": backup, "approvalMode": "operator-single-csr",
        "node": "node02", "automaticRollbackOnFailure": True}, indent=2) + "\n")
    spec = importlib.util.spec_from_file_location(
        "saved_csr_rotation", ROOT / "scripts/migration/saved-node-credential.py")
    saved = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(saved)
    password = saved.existing_password()
    accepted = False
    aside_done = False
    try:
        # Retire only unapproved pendings this rotation could have produced.
        cutoff = pre["at"]
        stale = [o for o in API.call(["get", "certificatesigningrequests", "-o", "json"])["items"]
                 if o["spec"].get("username") == "system:node:node02"
                 and o["spec"].get("signerName") == "kubernetes.io/kubelet-serving"
                 and not o.get("status", {}).get("conditions")
                 and not o.get("status", {}).get("certificate")
                 and o["metadata"]["creationTimestamp"] >= cutoff]
        retired = []
        for o in stale:
            API.call(["delete", "--raw=/apis/certificates.k8s.io/v1/"
                      "certificatesigningrequests/" + o["metadata"]["name"], "-f", "-"],
                     {"apiVersion": "v1", "kind": "DeleteOptions",
                      "preconditions": {"uid": o["metadata"]["uid"],
                                        "resourceVersion": o["metadata"]["resourceVersion"]}})
            retired.append({"name": o["metadata"]["name"], "uid": o["metadata"]["uid"]})
        if retired:
            save(stem, "retired-stale", {"retired": retired})
        # Everything above this line changes nothing on the host: a refusal
        # here must not restore (or overwrite) any certificate.
        assert not API.call(["get", "certificatesigningrequests", "-o", "json"])["items"], \
            "unrelated_csrs_require_review"
        aside = remote(password, "BACKUP=" + repr(backup) + "\n" + ASIDE, timeout=180)
        aside_done = True
        save(stem, "aside", aside)
        deadline = time.monotonic() + 300
        csr = None
        while time.monotonic() < deadline:
            rows = [o for o in API.call(["get", "certificatesigningrequests", "-o", "json"])["items"]
                    if o["spec"].get("username") == "system:node:node02"
                    and o["spec"].get("signerName") == "kubernetes.io/kubelet-serving"
                    and not o.get("status", {}).get("certificate")
                    and not o.get("status", {}).get("conditions")]
            if rows:
                csr = rows[0]
                break
            time.sleep(3)
        if not csr:
            raise RuntimeError("kubelet_did_not_request_serving_csr")
        save(stem, "csr-request", {"name": csr["metadata"]["name"],
                                   "uid": csr["metadata"]["uid"],
                                   "username": csr["spec"]["username"],
                                   "signer": csr["spec"]["signerName"]})
        run = subprocess.run([
            "/home/brajam/.local/share/branconet-migration/venv/bin/python", "-B",
            str(ROOT / "scripts/migration/run-kubelet-csr-controller.py"),
            "--state-dir", str(CSR_WORK / "state"),
            "--enrollment-file", str(CSR_WORK / "enrollment-node02.json"),
            "--kubectl", KUBECTL, "--once", "--mode", "approve", "--approval-enabled"],
            capture_output=True, text=True, timeout=120)
        current = API.call(["get", "certificatesigningrequest",
                            csr["metadata"]["name"], "-o", "json"])
        approved_in_cluster = any(c.get("type") == "Approved"
                                  for c in current.get("status", {}).get("conditions", []))
        save(stem, "approval", {"exit": run.returncode,
                                "stdout": run.stdout[-800:], "stderr": run.stderr[-400:],
                                "approvedInCluster": approved_in_cluster,
                                "exitCodeTrustworthy": run.returncode == 0})
        assert approved_in_cluster, "approval_not_recorded_in_cluster"
        deadline = time.monotonic() + 300
        issued_fingerprint = None
        served = None
        while time.monotonic() < deadline:
            obj = API.call(["get", "certificatesigningrequest",
                            csr["metadata"]["name"], "-o", "json"])
            conditions = [c.get("type") for c in obj.get("status", {}).get("conditions", [])]
            assert "Denied" not in conditions and "Failed" not in conditions, conditions
            raw = obj.get("status", {}).get("certificate")
            if raw:
                from cryptography import x509
                from cryptography.hazmat.primitives import serialization
                if issued_fingerprint is None:
                    der = x509.load_pem_x509_certificate(base64.b64decode(raw)).public_bytes(
                        serialization.Encoding.DER)
                    issued_fingerprint = hashlib.sha256(der).hexdigest()
                current = remote(password, SERVED, timeout=60)
                if current["fingerprintSHA256"] == issued_fingerprint:
                    served = current
                    break
            time.sleep(5)
        if not served:
            raise RuntimeError("kubelet_did_not_serve_issued_certificate")
        from kubelet_csr_controller import verify_issued
        ok, reason = verify_issued(
            obj, json.loads((CSR_WORK / "enrollment-node02.json").read_text()))
        assert ok, reason
        assert served["dns"] == ["node02"] and served["ips"] == ["192.168.0.6"]
        assert served["fingerprintSHA256"] == issued_fingerprint
        assert served["fingerprintSHA256"] != pre_served["fingerprintSHA256"]
        accepted = True
        value = {"passed": True, "attempt": attempt,
                 "preServedFingerprint": pre_served["fingerprintSHA256"],
                 "aside": aside, "kubeletRequestedCSR": csr["metadata"]["name"],
                 "requestingIdentity": csr["spec"]["username"],
                 "issuedFingerprintSHA256": issued_fingerprint,
                 "servedAfter": served, "issuedEqualsServed": True,
                 "approvalScope": "enrolled node02 only, one CSR",
                 "backupPath": backup,
                 "backupRetainedUntilNextSuccessfulRotation": True,
                 "approvalEnabledForService": False}
        save(stem, "result", value)
        print(json.dumps({k: value[k] for k in (
            "preServedFingerprint", "kubeletRequestedCSR", "requestingIdentity",
            "issuedFingerprintSHA256", "issuedEqualsServed")}, indent=2))
        print(json.dumps(served, indent=2))
    except Exception as error:
        (WORK / (stem + ".failure.json")).write_text(json.dumps({
            "attempt": attempt,
            "reason": str(error) if isinstance(error, RuntimeError) else type(error).__name__,
            "backupPath": backup, "acceptedBeforeFailure": accepted,
            "servingFilesChanged": aside_done}, indent=2) + "\n")
        # Only this attempt changed the serving files, so only this attempt's
        # backup may be restored. A pre-flight refusal (aside_done false)
        # leaves the host untouched — restoring here would overwrite the
        # current certificate with an older one.
        if not accepted and aside_done:
            try:
                restored = remote(password, "BACKUP=" + repr(backup) + "\n" + RESTORE, timeout=180)
                (WORK / (stem + "-rollback.json")).write_text(
                    json.dumps(restored, indent=2) + "\n")
            except Exception as restore_error:
                # Never swallow a failed rollback: the node may be serving a
                # self-signed interim certificate and the operator must see it.
                (WORK / (stem + "-rollback-failed.json")).write_text(json.dumps({
                    "attempt": attempt, "backupPath": backup,
                    "rollbackError": type(restore_error).__name__,
                    "operatorActionRequired": "inspect kubelet serving state on node02"},
                    indent=2) + "\n")
                raise RuntimeError("rollback_failed_inspect_node02") from error
        raise
    finally:
        password = None


if __name__ == "__main__":
    main()
