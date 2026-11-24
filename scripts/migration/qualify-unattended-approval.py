#!/usr/bin/env python3
"""Prove unattended kubelet-serving CSR approval end to end.

A genuine rotation is forced on node02 by moving kubelet's serving material
aside. The managed service (approve mode) must approve the resulting CSR with no
operator command; kubelet must then serve the issued certificate. The operator
only observes. Rollback restores the backup if the run does not reach acceptance.
"""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
STAGE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/"
             "bortus-operator-recovery/certificates-qualification-20261116")
WORK = STAGE / "csr-unattended-approval"
BACKUP = "/root/bortus-kubelet-pki-backup-unattended"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/migration" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROT = load("rot", "qualify-kubelet-rotation.py")
API = ROT.API
WORK.mkdir(mode=0o700, exist_ok=True)


def save(name, value):
    with (WORK / name).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def csrs():
    return API.call(["get", "certificatesigningrequests", "-o", "json"])["items"]


def main():
    assert not (WORK / "unattended.started.json").exists(), "reconcile_existing_attempt"
    assert json.loads((WORK / "enable-result.json").read_text())["passed"]
    existing = csrs()
    assert not existing, f"review_existing_csrs:{[c['metadata']['name'] for c in existing]}"
    pre = json.loads((STAGE / "kubelet-csr-observation" / "served-endpoint-result.json").read_text())
    started = {"preServedFingerprint": pre["fingerprintSHA256"], "backupPath": BACKUP,
               "operatorApprovalCommands": 0, "approverMustBe": "bortus-csr-controller.service"}
    save("unattended.started.json", started)

    saved = load("saved_cred", "saved-node-credential.py")
    password = saved.existing_password()
    accepted = False
    try:
        aside = ROT.remote(password, "BACKUP=" + repr(BACKUP) + "\n" + ROT.ASIDE, timeout=180)
        save("unattended-aside.json", aside)

        deadline = time.monotonic() + 300
        csr = None
        while time.monotonic() < deadline:
            rows = [o for o in csrs()
                    if o["spec"].get("username") == "system:node:node02"
                    and o["spec"].get("signerName") == "kubernetes.io/kubelet-serving"]
            if rows:
                csr = rows[0]
                break
            time.sleep(3)
        assert csr, "kubelet_did_not_request_csr"
        name, uid = csr["metadata"]["name"], csr["metadata"]["uid"]
        save("unattended-csr.json", {"name": name, "uid": uid,
                                     "username": csr["spec"]["username"],
                                     "approvedAtObservationStart": any(
                                         c.get("type") == "Approved"
                                         for c in csr.get("status", {}).get("conditions", []))})

        # Wait for the SERVICE to approve. The operator never patches.
        deadline = time.monotonic() + 300
        approved = None
        while time.monotonic() < deadline:
            obj = API.call(["get", "certificatesigningrequest", name, "-o", "json"])
            conditions = [c for c in obj.get("status", {}).get("conditions", [])]
            assert not any(c.get("type") in ("Denied", "Failed") for c in conditions), conditions
            if any(c.get("type") == "Approved" for c in conditions):
                approved = obj
                break
            time.sleep(3)
        assert approved, "service_did_not_approve_within_timeout"
        save("unattended-approved.json", {"name": name, "uid": uid,
                                          "conditions": [c.get("type") for c in
                                                         approved["status"]["conditions"]],
                                          "approvedByOperatorCommand": False})

        # Wait for issuance, then for kubelet to actually serve it.
        deadline = time.monotonic() + 300
        issued_fp = None
        served = None
        while time.monotonic() < deadline:
            obj = API.call(["get", "certificatesigningrequest", name, "-o", "json"])
            raw = obj.get("status", {}).get("certificate")
            if raw:
                from cryptography import x509
                from cryptography.hazmat.primitives import serialization
                if issued_fp is None:
                    der = x509.load_pem_x509_certificate(
                        base64.b64decode(raw)).public_bytes(serialization.Encoding.DER)
                    issued_fp = hashlib.sha256(der).hexdigest()
                current = ROT.remote(password, ROT.SERVED, timeout=60)
                if current["fingerprintSHA256"] == issued_fp:
                    served = current
                    break
            time.sleep(5)
        assert served, "kubelet_did_not_serve_issued_certificate"
        assert issued_fp != pre["fingerprintSHA256"], "fingerprint_did_not_change"
        assert served["dns"] == ["node02"] and served["ips"] == ["192.168.0.6"]

        # The approval must exist in the controller's own durable state.
        state = ROT.remote(password, (
            "import json,sqlite3\n"
            "from pathlib import Path\n"
            "p=Path('/var/lib/bortus-csr-controller/csr-controller.sqlite')\n"
            "with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=5) as db:\n"
            "    row=db.execute('SELECT csr_uid,approved_at FROM kubelet_csr_decisions WHERE csr_uid=?',(UID_,)).fetchone()\n"
            "    rows=db.execute('SELECT csr_uid,approved_at,approved_revision FROM kubelet_csr_approvals').fetchall()\n"
            "print(json.dumps({'decision':row,'approvals':rows,'count':len(rows)}))\n").replace("UID_", repr(uid)), timeout=60)
        assert state["decision"] and state["decision"][1], state
        accepted = True
        value = {
            "passed": True,
            "preServedFingerprint": pre["fingerprintSHA256"],
            "issuedFingerprintSHA256": issued_fp,
            "servedAfter": served,
            "issuedEqualsServed": True,
            "csr": {"name": name, "uid": uid, "requestingIdentity": csr["spec"]["username"]},
            "approvalSource": "bortus-csr-controller.service (managed, approve mode)",
            "operatorApprovalCommands": 0,
            "controllerState": state,
            "aside": aside,
            "backupPath": BACKUP,
        }
        save("unattended.result.json", value)
        print(json.dumps({k: value[k] for k in
                          ("preServedFingerprint", "issuedFingerprintSHA256",
                           "issuedEqualsServed", "operatorApprovalCommands")}, indent=2))
        print(json.dumps(served, indent=2))
    except Exception as error:
        save("unattended.failure.json", {"reason": str(error) if isinstance(error, RuntimeError)
                                         else type(error).__name__,
                                         "acceptedBeforeFailure": accepted})
        if not accepted:
            try:
                restored = ROT.remote(password, "BACKUP=" + repr(BACKUP) + "\n" + ROT.RESTORE,
                                      timeout=180)
                save("unattended-rollback.json", restored)
            except Exception:
                pass
        raise
    finally:
        password = None


if __name__ == "__main__":
    main()
