#!/usr/bin/env python3
"""One real kubelet-serving issuance: validate, approve once, match fingerprints.

The managed service keeps observing; only this operator-driven run approves the
single CSR created here. Kubelet's own serving material is never replaced.
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
WORK = STAGE / "kubelet-csr-observation"
NODE = "192.168.0.6"
KUBECTL = "/home/brajam/.local/share/branconet-migration/bin/kubectl"
SPEC = importlib.util.spec_from_file_location(
    "renewal_api", Path(__file__).with_name("stage-ntfy-cluster.py"))
API = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(API)

CREATE = r'''
import base64,hashlib,ipaddress,json,os,stat,subprocess
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
directory=Path('/run/bortus-csr-qualification')
directory.mkdir(mode=0o700,exist_ok=True);os.chmod(directory,0o700)
key=ec.generate_private_key(ec.SECP256R1())
key_path=directory/'key.pem'
fd=os.open(key_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'wb') as stream:
    stream.write(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
builder=x509.CertificateSigningRequestBuilder().subject_name(x509.Name([
    x509.NameAttribute(NameOID.ORGANIZATION_NAME,'system:nodes'),
    x509.NameAttribute(NameOID.COMMON_NAME,'system:node:node02')]))
builder=builder.add_extension(x509.SubjectAlternativeName([
    x509.DNSName('node02'),x509.IPAddress(ipaddress.ip_address('192.168.0.6'))]),critical=False)
pem=builder.sign(key,hashes.SHA256()).public_bytes(serialization.Encoding.PEM)
obj={'apiVersion':'certificates.k8s.io/v1','kind':'CertificateSigningRequest',
     'metadata':{'generateName':'kubelet-renewal-qualification-'},
     'spec':{'request':base64.b64encode(pem).decode(),'signerName':'kubernetes.io/kubelet-serving',
             'usages':['digital signature','server auth'],'expirationSeconds':600}}
q=subprocess.run(['kubectl','--kubeconfig','/etc/kubernetes/kubelet.conf','create','-f','-','-o','json'],
                 input=json.dumps(obj),capture_output=True,text=True,timeout=30)
if q.returncode:raise SystemExit(q.stderr[:400])
value=json.loads(q.stdout)
print(json.dumps({'name':value['metadata']['name'],'uid':value['metadata']['uid'],
 'username':value['spec']['username'],'requestSHA256':hashlib.sha256(pem).hexdigest(),
 'keyMode':oct(stat.S_IMODE(key_path.lstat().st_mode))}))
'''

WRITE_CERT = r'''
import json,os
from pathlib import Path
path=Path('/run/bortus-csr-qualification/issued.pem')
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'wb') as stream:stream.write(__import__('base64').b64decode(CERT))
print(json.dumps({'written':True,'mode':oct(os.stat(path).st_mode&0o777)}))
'''

SERVE_MATCH = r'''
import hashlib,json,socket,ssl,threading
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import serialization
directory=Path('/run/bortus-csr-qualification');cert_path=directory/'issued.pem'
issued_der=x509.load_pem_x509_certificate(cert_path.read_bytes()).public_bytes(serialization.Encoding.DER)
issued_fp=hashlib.sha256(issued_der).hexdigest()
server=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);server.minimum_version=ssl.TLSVersion.TLSv1_2
server.load_cert_chain(str(cert_path),str(directory/'key.pem'))
listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
listener.bind(('127.0.0.1',0));listener.listen(1);port=listener.getsockname()[1]
def serve():
    try:
        conn,_=listener.accept()
        with server.wrap_socket(conn,server_side=True) as tls:tls.recv(8)
    except Exception:pass
thread=threading.Thread(target=serve,daemon=True);thread.start()
client=ssl.create_default_context(cafile='/etc/kubernetes/pki/ca.crt');client.minimum_version=ssl.TLSVersion.TLSv1_2
with socket.create_connection(('127.0.0.1',port),timeout=8) as raw:
    with client.wrap_socket(raw,server_hostname='node02') as tls:
        served_der=tls.getpeercert(binary_form=True);version=tls.version()
listener.close();thread.join(timeout=5)
print(json.dumps({'issuedFingerprint':issued_fp,
 'servedFingerprint':hashlib.sha256(served_der).hexdigest(),
 'match':hashlib.sha256(served_der).hexdigest()==issued_fp,'tlsVersion':version}))
'''

KUBELET_STILL = r'''
import hashlib,json,socket,ssl
ctx=ssl.create_default_context(cafile='/etc/kubernetes/pki/ca.crt')
with socket.create_connection(('127.0.0.1',10250),timeout=8) as raw:
    with ctx.wrap_socket(raw,server_hostname='node02') as tls:
        der=tls.getpeercert(binary_form=True)
print(json.dumps({'kubeletServingFingerprint':hashlib.sha256(der).hexdigest()}))
'''

CLEANUP = r'''
import json,shutil
from pathlib import Path
directory=Path('/run/bortus-csr-qualification')
removed=sorted(p.name for p in directory.iterdir())
shutil.rmtree(directory)
print(json.dumps({'removed':removed,'absent':not directory.exists()}))
'''


def save(name, value):
    with (WORK / name).open("x") as stream:
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
    parser.add_argument("phase", choices=["approve-issue", "verify-served", "retire"])
    args = parser.parse_args()
    prefix = WORK / ("renewal-" + args.phase)
    assert not prefix.with_suffix(".started.json").exists(), "reconcile_existing_phase"
    assert json.loads((WORK / "live-qualification-acceptance.json").read_text())["passed"]
    if args.phase == "verify-served":
        assert json.loads((WORK / "renewal-approve-issue.result.json").read_text())["passed"]
    if args.phase == "retire":
        assert json.loads((WORK / "renewal-verify-served.result.json").read_text())["passed"]
    prefix.with_suffix(".started.json").write_text(json.dumps({
        "phase": args.phase, "approvalMode": "operator-single-csr",
        "managedServiceMode": "observe",
        "sourceSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, indent=2) + "\n")
    spec = importlib.util.spec_from_file_location(
        "saved_csr_renewal", ROOT / "scripts/migration/saved-node-credential.py")
    saved = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(saved)
    password = saved.existing_password()
    try:
        if args.phase == "approve-issue":
            assert not API.call(["get", "certificatesigningrequests", "-o", "json"])["items"], \
                "existing_csrs_require_review"
            fixture = remote(password, CREATE)
            assert fixture["username"] == "system:node:node02"
            run = subprocess.run([
                "/home/brajam/.local/share/branconet-migration/venv/bin/python", "-B",
                str(ROOT / "scripts/migration/run-kubelet-csr-controller.py"),
                "--state-dir", str(WORK / "state"),
                "--enrollment-file", str(WORK / "enrollment-node02.json"),
                "--kubectl", KUBECTL, "--once", "--mode", "approve", "--approval-enabled"],
                capture_output=True, text=True, timeout=120)
            assert run.returncode == 0, run.stderr[-400:]
            cycle = json.loads(run.stdout)
            approved = [v for v in cycle["verdicts"] if v.get("approved")]
            assert cycle["approvalEnabled"] is True and len(approved) == 1
            assert approved[0]["csr"]["uid"] == fixture["uid"] and approved[0]["eligible"]
            deadline = time.monotonic() + 120
            issued = None
            while time.monotonic() < deadline:
                obj = API.call(["get", "certificatesigningrequest", fixture["name"], "-o", "json"])
                conditions = [c.get("type") for c in obj.get("status", {}).get("conditions", [])]
                assert "Denied" not in conditions and "Failed" not in conditions, conditions
                if obj.get("status", {}).get("certificate"):
                    issued = obj
                    break
                time.sleep(3)
            assert issued, "issuance_not_observed"
            from kubelet_csr_controller import verify_issued
            ok, reason = verify_issued(
                issued, json.loads((WORK / "enrollment-node02.json").read_text()))
            assert ok, reason
            from cryptography import x509
            from cryptography.hazmat.primitives import serialization
            der = x509.load_pem_x509_certificate(
                base64.b64decode(issued["status"]["certificate"])).public_bytes(
                serialization.Encoding.DER)
            fingerprint = hashlib.sha256(der).hexdigest()
            written = remote(password, "CERT=" + repr(issued["status"]["certificate"]) + "\n" + WRITE_CERT)
            assert written["written"]
            value = {"passed": True, "fixture": fixture, "cycle": cycle,
                     "approvedVerdict": approved[0], "issuedCertificateVerified": True,
                     "issuedFingerprintSHA256": fingerprint,
                     "issuedNotAfter": issued["status"].get("notAfter"),
                     "singleApprovalOnly": cycle["state"]["approved"] == 1}
            save("renewal-approve-issue.result.json", value)
            print(json.dumps({k: value[k] for k in (
                "issuedCertificateVerified", "issuedFingerprintSHA256",
                "issuedNotAfter", "singleApprovalOnly")}, indent=2))
        elif args.phase == "verify-served":
            served = remote(password, SERVE_MATCH)
            assert served["match"] is True, served
            kubelet = remote(password, KUBELET_STILL)
            baseline = json.loads((WORK / "served-endpoint-result.json").read_text())
            assert kubelet["kubeletServingFingerprint"] == baseline["fingerprintSHA256"], \
                "kubelet_serving_material_changed"
            value = {"passed": True, "servedMatchesIssued": True,
                     "issuedFingerprintSHA256": served["issuedFingerprint"],
                     "servedFingerprintSHA256": served["servedFingerprint"],
                     "tlsVersion": served["tlsVersion"],
                     "kubeletServingFingerprintUnchanged": kubelet["kubeletServingFingerprint"],
                     "kubeletServingMaterialReplaced": False,
                     "scope": "issued material served from a bounded listener; kubelet "
                              "serverTLSBootstrap adoption is still a separate gate"}
            save("renewal-verify-served.result.json", value)
            print(json.dumps(value, indent=2))
        else:
            fixture = json.loads((WORK / "renewal-approve-issue.result.json").read_text())["fixture"]
            obj = API.call(["get", "certificatesigningrequest", fixture["name"], "-o", "json"])
            assert obj["metadata"]["uid"] == fixture["uid"]
            API.call(["delete", "--raw=/apis/certificates.k8s.io/v1/certificatesigningrequests/"
                      + fixture["name"], "-f", "-"],
                     {"apiVersion": "v1", "kind": "DeleteOptions",
                      "preconditions": {"uid": fixture["uid"],
                                        "resourceVersion": obj["metadata"]["resourceVersion"]}})
            remaining = API.call(["get", "certificatesigningrequests", "-o", "json"])["items"]
            cleanup = remote(password, CLEANUP)
            value = {"passed": True, "retired": fixture, "remainingCSRs": len(remaining),
                     "nodeKeyAndCertificateRemoved": cleanup,
                     "approvalFlagNotEphemeral": False,
                     "managedServiceMode": "observe"}
            save("renewal-retire.result.json", value)
            print(json.dumps(value, indent=2))
    except Exception as error:
        (WORK / ("renewal-" + args.phase + ".failure.json")).write_text(json.dumps({
            "reason": str(error) if isinstance(error, RuntimeError) else type(error).__name__,
            "outcomeRequiresReconciliation": True}, indent=2) + "\n")
        raise
    finally:
        password = None


if __name__ == "__main__":
    main()
