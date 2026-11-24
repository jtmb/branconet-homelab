#!/usr/bin/env python3
"""Per-machine qualification for unattended kubelet-serving renewal (node01/node03).

Two phases, run in order for one machine at a time:

watch NODE
    The machine must be watch-only in the node02 controller's enrollment.
    Using the machine's own kubelet identity (so the API server records the
    real requester), create two serving requests: one asking for exactly the
    machine's own name/address, one also claiming another machine's address.
    Pass when the controller records the first as eligible and the second as
    ineligible, approves neither, and both test requests are then deleted.

renew NODE
    The machine's approve switch must be on. Move kubelet's current serving
    certificate aside (root-only backup), restart kubelet so it asks for a
    real replacement, and pass only when the node02 service approved that
    request by itself, the signer issued it, and the certificate the machine
    actually serves on :10250 is that issued certificate. On any failure the
    backup is restored and kubelet restarted. For node03 the LAN DHCP and DNS
    services it also hosts are checked afterwards.

The admin password is read in memory from the existing vaulted native Secret
(saved-node-credential.py) and only ever written to sudo's stdin.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import socket
import ssl
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
WORK = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/"
            "bortus-operator-recovery/certificates-qualification-20261116/kubelet-multinode-rollout")
NODES = {"node01": "192.168.0.4", "node02": "192.168.0.6", "node03": "192.168.0.5"}
OTHER = {"node01": "192.168.0.5", "node03": "192.168.0.4"}
CONTROLLER = "192.168.0.6"
KUBECTL = ["/home/brajam/.local/share/branconet-migration/bin/kubectl", "--kubeconfig",
           "/home/brajam/.local/share/branconet-migration/admin.conf", "--request-timeout=20s"]
BACKUP = "/root/bortus-kubelet-pki-backup-multinode"


def password():
    """Vaulted admin password, in memory only."""
    spec = importlib.util.spec_from_file_location("saved", ROOT / "scripts/migration/saved-node-credential.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.existing_password()


def root_python(host, code, secret, timeout=300):
    """Run `code` as root on host; returns parsed JSON from its last stdout line."""
    result = subprocess.run(
        ["ssh", "-p", "2002", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
         "-o", "ConnectTimeout=10", "-i", "/home/brajam/.ssh/id_ed25519", "james@" + host,
         "sudo -S -p '' /usr/bin/python3 -B -c " + shlex.quote(code)],
        input=(secret + "\n").encode(), capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("remote_failed: " + result.stderr.decode()[-800:])
    return json.loads(result.stdout.decode().strip().splitlines()[-1])


def kubectl(*args):
    result = subprocess.run(KUBECTL + list(args), capture_output=True, timeout=40)
    if result.returncode:
        raise RuntimeError("kubectl_failed: " + result.stderr.decode()[-400:])
    return json.loads(result.stdout) if result.stdout.strip() else None


def enrollment_switches(secret):
    """The approve switch for every enrolled machine, read as root on node02."""
    value = root_python(CONTROLLER, "import json;print(json.dumps(json.load(open("
                        "'/etc/bortus-csr-controller/enrollment.json'))))", secret)
    assert value["version"] == 2, "enrollment_not_multinode"
    return {n["name"]: n["approve"] for n in value["nodes"]}


def controller_lines(since):
    """Controller cycle outputs since a journal timestamp (no privilege needed)."""
    result = subprocess.run(
        ["ssh", "-p", "2002", "-o", "BatchMode=yes", "-i", "/home/brajam/.ssh/id_ed25519",
         "james@" + CONTROLLER, "journalctl -u bortus-csr-controller.service -o cat --no-pager --since " +
         shlex.quote(since)], capture_output=True, timeout=40)
    lines = []
    for raw in result.stdout.decode().splitlines():
        if raw.startswith("{"):
            try:
                lines.append(json.loads(raw))
            except ValueError:
                pass
    return lines


def save(name, value):
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / name
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
    return path


# Runs as root on the machine being tested. Uses the kubelet's own client
# certificate so the API server records the real node identity as requester.
CREATE_REQUESTS = r'''
import base64,http.client,ipaddress,json,ssl,time
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
NODE, OWN, OTHER, STAMP = %(node)r, %(own)r, %(other)r, %(stamp)r
ctx = ssl.create_default_context(cafile='/etc/kubernetes/pki/ca.crt')
ctx.load_cert_chain('/var/lib/kubelet/pki/kubelet-client-current.pem')
made = []
for suffix, ips in (('own', [OWN]), ('wrong', [OWN, OTHER])):
    key = ec.generate_private_key(ec.SECP256R1(), default_backend())   # discarded after signing
    names = [x509.DNSName(NODE)] + [x509.IPAddress(ipaddress.ip_address(i)) for i in ips]
    request = (x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'system:nodes'),
                                 x509.NameAttribute(NameOID.COMMON_NAME, 'system:node:' + NODE)]))
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .sign(key, hashes.SHA256(), default_backend()))
    body = {'apiVersion': 'certificates.k8s.io/v1', 'kind': 'CertificateSigningRequest',
            'metadata': {'name': NODE + '-renewal-check-' + STAMP + '-' + suffix},
            'spec': {'request': base64.b64encode(request.public_bytes(serialization.Encoding.PEM)).decode(),
                     'signerName': 'kubernetes.io/kubelet-serving',
                     'usages': ['digital signature', 'server auth']}}
    conn = http.client.HTTPSConnection('192.168.0.251', 6443, context=ctx, timeout=20)
    conn.request('POST', '/apis/certificates.k8s.io/v1/certificatesigningrequests', json.dumps(body),
                 {'Content-Type': 'application/json'})
    reply = conn.getresponse(); data = json.loads(reply.read()); conn.close()
    assert reply.status == 201, ('create_failed', reply.status, data.get('message'))
    made.append({'kind': suffix, 'name': data['metadata']['name'], 'uid': data['metadata']['uid'],
                 'requester': data['spec']['username']})
print(json.dumps({'created': made}))
'''

ROTATE = r'''
import json,os,shutil,subprocess,time
from pathlib import Path
pki = Path('/var/lib/kubelet/pki'); backup = Path(%(backup)r)
backup.mkdir(mode=0o700, exist_ok=True)
current = pki / 'kubelet-server-current.pem'
saved = []
for item in sorted(pki.glob('kubelet-server-*.pem')):
    target = backup / item.name
    if item.is_symlink():
        target.write_text(json.dumps({'symlink_to': os.readlink(item)}))
    else:
        shutil.copy2(item, target)
    os.chmod(target, 0o600); saved.append(item.name)
for item in sorted(pki.glob('kubelet-server-*.pem')):
    item.unlink()
subprocess.run(['systemctl', 'restart', 'kubelet.service'], check=True, capture_output=True, timeout=120)
time.sleep(3)
state = subprocess.check_output(['systemctl', 'is-active', 'kubelet.service'], text=True).strip()
print(json.dumps({'backedUpAndRemoved': saved, 'backup': str(backup), 'kubelet': state}))
'''

RESTORE = r'''
import json,os,shutil,subprocess
from pathlib import Path
pki = Path('/var/lib/kubelet/pki'); backup = Path(%(backup)r); restored = []
for item in sorted(pki.glob('kubelet-server-*.pem')):
    item.unlink()
for item in sorted(backup.iterdir()):
    text = item.read_bytes()
    if text.startswith(b'{"symlink_to"'):
        os.symlink(json.loads(text)['symlink_to'], pki / item.name)
    else:
        shutil.copy2(item, pki / item.name); os.chmod(pki / item.name, 0o600)
    restored.append(item.name)
subprocess.run(['systemctl', 'restart', 'kubelet.service'], check=True, capture_output=True, timeout=120)
print(json.dumps({'restored': restored}))
'''

LAN_SERVICES = r'''
import json,subprocess
def active(unit): return subprocess.run(['systemctl','is-active',unit],capture_output=True,text=True).stdout.strip()
listeners = subprocess.check_output(['ss','-ulpn'], text=True)
print(json.dumps({'dhcpService': active('branconet-lan-dhcp.service'),
                  'dhcpListening': any(':67 ' in l and 'dnsmasq' in l for l in listeners.splitlines()),
                  'kubelet': active('kubelet.service')}))
'''


def lan_dns():
    """Ask both advertised LAN resolvers from *this* machine, like a LAN client.

    node03's own :53 cannot be probed from node03 itself: external queries
    reach its resolver through a PREROUTING redirect that local traffic skips.
    """
    import struct
    query = struct.pack(">HHHHHH", 0x4242, 0x0100, 1, 0, 0, 0) + b"".join(
        bytes([len(p)]) + p.encode() for p in "bortus.branconet.lan".split(".")) + b"\x00" + struct.pack(">HH", 1, 1)
    answers = {}
    for server in ("192.168.0.5", "192.168.0.253"):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(4)
        s.sendto(query, (server, 53)); reply = s.recv(512); s.close()
        answers[server] = {"rcode": reply[3] & 0xF, "answers": struct.unpack(">H", reply[6:8])[0]}
    return answers



def served_certificate(ip):
    """DER of the leaf certificate a machine actually serves on :10250."""
    ctx = ssl._create_unverified_context()
    with socket.create_connection((ip, 10250), timeout=10) as raw:
        with ctx.wrap_socket(raw, server_hostname=ip) as tls:
            return tls.getpeercert(binary_form=True)


def cluster_ca():
    from cryptography import x509
    raw = subprocess.run(["/bin/sh", "-c", "grep certificate-authority-data "
                          "/home/brajam/.local/share/branconet-migration/admin.conf | awk '{print $2}'"],
                         capture_output=True, text=True).stdout.strip()
    return x509.load_pem_x509_certificate(base64.b64decode(raw))


def watch(node, secret):
    switches = enrollment_switches(secret)
    assert switches.get(node) is False, "node_must_be_watch_only_for_this_phase"
    since = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(time.time() - 5))
    stamp = time.strftime("%Y%m%d%H%M%S")
    created = root_python(NODES[node], CREATE_REQUESTS % {
        "node": node, "own": NODES[node], "other": OTHER[node], "stamp": stamp}, secret)["created"]
    wanted = {row["name"]: row for row in created}
    seen = {}
    try:
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline and len(seen) < len(wanted):
            for cycle in controller_lines(since):
                for verdict in cycle.get("verdicts", []):
                    if verdict["csr"]["name"] in wanted:
                        seen[verdict["csr"]["name"]] = verdict
            time.sleep(10)
    finally:
        cleanup = []
        for row in created:
            current = kubectl("get", "csr", row["name"], "-o", "json")
            assert current["metadata"]["uid"] == row["uid"], "csr_replaced_before_cleanup"
            assert not current.get("status", {}).get("certificate"), "test_csr_was_issued"
            subprocess.run(KUBECTL + ["delete", "csr", row["name"], "--wait=true"], check=True,
                           capture_output=True, timeout=60)
            cleanup.append({"name": row["name"], "uid": row["uid"], "deleted": True,
                            "approvedConditionPresent": any(c.get("type") == "Approved" for c in
                                                            current.get("status", {}).get("conditions", []))})
    own = next(seen[r["name"]] for r in created if r["kind"] == "own")
    wrong = next(seen[r["name"]] for r in created if r["kind"] == "wrong")
    result = {
        "phase": "watch", "node": node, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "requester": created[0]["requester"],
        "ownRequest": {"eligible": own["eligible"], "reasons": own["reasons"], "approved": own["approved"]},
        "wrongAddressRequest": {"eligible": wrong["eligible"], "reasons": wrong["reasons"],
                                "approved": wrong["approved"]},
        "cleanup": cleanup,
    }
    result["passed"] = (own["eligible"] and not own["approved"] and not wrong["eligible"]
                        and "sans_invalid" in wrong["reasons"] and not wrong["approved"]
                        and not any(c["approvedConditionPresent"] for c in cleanup))
    return result


def renew(node, secret):
    from cryptography import x509
    switches = enrollment_switches(secret)
    assert switches.get(node) is True, "node_approve_switch_must_be_on"
    ip = NODES[node]
    before = hashlib.sha256(served_certificate(ip)).hexdigest()
    since = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(time.time() - 5))
    started = time.time()
    rotated = root_python(ip, ROTATE % {"backup": BACKUP}, secret)
    try:
        csr = None
        deadline = time.monotonic() + 420
        while time.monotonic() < deadline:
            rows = [r for r in kubectl("get", "csr", "-o", "json")["items"]
                    if r["spec"].get("username") == "system:node:" + node
                    and r["spec"].get("signerName") == "kubernetes.io/kubelet-serving"
                    and r["metadata"]["creationTimestamp"] >= time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(started - 5))]
            issued = [r for r in rows if r.get("status", {}).get("certificate")]
            if issued:
                csr = issued[-1]
                break
            time.sleep(10)
        assert csr, "no_issued_renewal_within_deadline"
        # The controller prints its cycle summary only after the cycle ends, so
        # the issued certificate can be visible before the log line. Wait for it
        # (first attempt on 2026-11-18 raced this and rolled back needlessly).
        approvals, deadline = [], time.monotonic() + 180
        while not approvals and time.monotonic() < deadline:
            approvals = [v for c in controller_lines(since) for v in c.get("verdicts", [])
                         if v["csr"]["name"] == csr["metadata"]["name"] and v.get("approved")]
            if not approvals:
                time.sleep(10)
        assert approvals, "approval_not_by_controller_service"
        issued_der = x509.load_pem_x509_certificate(base64.b64decode(csr["status"]["certificate"])).public_bytes(
            __import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]).Encoding.DER)
        served = None
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            served = served_certificate(ip)
            if served == issued_der:
                break
            time.sleep(5)
        assert served == issued_der, "served_certificate_is_not_the_issued_one"
        leaf = x509.load_der_x509_certificate(served)
        ca = cluster_ca()
        sans = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        verify_lines = [i for c in controller_lines(since) for i in c.get("issued", [])
                        if i["csr"] == csr["metadata"]["name"]]
    except Exception:
        restored = root_python(ip, RESTORE % {"backup": BACKUP}, secret)
        save(f"renew-{node}-rolled-back.json", {"node": node, "restored": restored, "rotated": rotated})
        raise
    result = {
        "phase": "renew", "node": node, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rotation": rotated, "csr": csr["metadata"]["name"], "approvedBy": "bortus-csr-controller.service",
        "operatorCommands": 0, "servedBefore": before, "servedAfter": hashlib.sha256(served).hexdigest(),
        "servedEqualsIssued": True, "issuer": leaf.issuer.rfc4514_string(),
        "issuerIsClusterCA": leaf.issuer == ca.subject,
        "sans": {"dns": [n.value for n in sans if isinstance(n, x509.DNSName)],
                 "ips": [str(n.value) for n in sans if isinstance(n, x509.IPAddress)]},
        "controllerIssuedVerification": verify_lines[-1] if verify_lines else None,
        "nodeReady": any(c["type"] == "Ready" and c["status"] == "True"
                         for c in kubectl("get", "node", node, "-o", "json")["status"]["conditions"]),
    }
    if node == "node03":
        result["lanServices"] = root_python(ip, LAN_SERVICES, secret) | {"dns": lan_dns()}
    result["passed"] = (result["issuerIsClusterCA"] and result["nodeReady"]
                        and result["sans"] == {"dns": [node], "ips": [ip]}
                        and result["servedBefore"] != result["servedAfter"])
    if node == "node03":
        lan = result["lanServices"]
        result["passed"] = result["passed"] and lan["dhcpService"] == "active" and lan["dhcpListening"] \
            and all(v["rcode"] == 0 and v["answers"] > 0 for v in lan["dns"].values())
    return result


def verify(node, secret):
    """Read-only: prove the machine's *current* serving certificate came from
    an approver-approved renewal in the last 2 hours. Changes nothing."""
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding
    ip = NODES[node]
    rows = sorted((r for r in kubectl("get", "csr", "-o", "json")["items"]
                   if r["spec"].get("username") == "system:node:" + node
                   and r.get("status", {}).get("certificate")),
                  key=lambda r: r["metadata"]["creationTimestamp"])
    assert rows, "no_issued_renewal_found"
    csr = rows[-1]
    issued_der = x509.load_pem_x509_certificate(base64.b64decode(csr["status"]["certificate"])).public_bytes(Encoding.DER)
    served = served_certificate(ip)
    since = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(time.time() - 7200))
    cycles = controller_lines(since)
    approved = any(v["csr"]["name"] == csr["metadata"]["name"] and v.get("approved")
                   for c in cycles for v in c.get("verdicts", []))
    checked = [i for c in cycles for i in c.get("issued", []) if i["csr"] == csr["metadata"]["name"]]
    leaf = x509.load_der_x509_certificate(served)
    sans = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    result = {"phase": "verify", "node": node, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "csr": csr["metadata"]["name"], "approvedByControllerService": approved,
              "approvalReason": [c.get("reason") for c in csr["status"].get("conditions", [])],
              "servedEqualsIssued": served == issued_der,
              "served": hashlib.sha256(served).hexdigest(),
              "issuerIsClusterCA": leaf.issuer == cluster_ca().subject,
              "sans": {"dns": [n.value for n in sans if isinstance(n, x509.DNSName)],
                       "ips": [str(n.value) for n in sans if isinstance(n, x509.IPAddress)]},
              "controllerIssuedVerification": checked[-1] if checked else None,
              "nodeReady": any(c["type"] == "Ready" and c["status"] == "True"
                               for c in kubectl("get", "node", node, "-o", "json")["status"]["conditions"])}
    ok = (approved and result["servedEqualsIssued"] and result["issuerIsClusterCA"] and result["nodeReady"]
          and result["sans"] == {"dns": [node], "ips": [ip]})
    if node == "node03":
        lan = root_python(ip, LAN_SERVICES, secret) | {"dns": lan_dns()}
        result["lanServices"] = lan
        ok = ok and lan["dhcpService"] == "active" and lan["dhcpListening"] and \
            all(v["rcode"] == 0 and v["answers"] > 0 for v in lan["dns"].values())
    result["passed"] = ok
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("phase", choices=["watch", "renew", "verify"])
    parser.add_argument("node", choices=["node01", "node03"])
    args = parser.parse_args()
    secret = password()
    try:
        result = {"watch": watch, "renew": renew, "verify": verify}[args.phase](args.node, secret)
    finally:
        secret = None
    path = save(f"{args.phase}-{args.node}-{time.strftime('%Y%m%dT%H%M%S')}.json", result)
    print(json.dumps(result, indent=2))
    print("evidence:", path)
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
