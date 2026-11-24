#!/usr/bin/env python3
"""Exercise owned routed TLS, policy, cert projection/restart and cache persistence."""
import base64
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import socket
import ssl
import subprocess
import time
from urllib.parse import urlsplit

from certificate_monitor_process import run_bounded, MonitorProcessError
from certificate_monitor_notifications import PinnedHTTPSConnection
from ntfy_cluster_fixture import NAMESPACE, EDGE, DENIED, LABEL, OWNER, NAME

spec = importlib.util.spec_from_file_location("cluster_stage", Path(__file__).with_name("stage-ntfy-cluster.py"))
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)
WORK, BASE, call, save = stage.WORK, stage.BASE, stage.call, stage.save


def public_cert(name):
    raw = run_bounded(BASE + ["get", "secret", name, "-n", NAMESPACE, "-o",
        r"jsonpath={.data.tls\.crt}"], output_limit=16384, timeout=20)
    return base64.b64decode(raw)


def fingerprint(pem):
    text = pem.decode()
    leaf = text[:text.index("-----END CERTIFICATE-----") + len("-----END CERTIFICATE-----")]
    return hashlib.sha256(ssl.PEM_cert_to_DER_cert(leaf)).hexdigest()


def pod(namespace, selector):
    items = call(["get", "pods", "-n", namespace, "-l", selector, "-o", "json"])["items"]
    active = [p for p in items if not p["metadata"].get("deletionTimestamp") and
              p.get("status", {}).get("phase") == "Running"]
    assert len(active) == 1 and active[0]["metadata"]["labels"][LABEL] == OWNER
    return active[0]


def patch(kind, name, namespace, obj, changes):
    assert obj["metadata"]["labels"][LABEL] == OWNER
    operations = [{"op": "test", "path": "/metadata/uid", "value": obj["metadata"]["uid"]},
                  {"op": "test", "path": "/metadata/resourceVersion",
                   "value": obj["metadata"]["resourceVersion"]}, *changes]
    return call(["patch", kind, name, "-n", namespace, "--type=json",
                 "--patch-file=/dev/stdin", "-o", "json"], operations)


def exec_read(namespace, name, args, limit=65536):
    return run_bounded(BASE + ["exec", "-n", namespace, name, "--", *args],
                       output_limit=limit, timeout=15)


def tcp(namespace, name, address, port):
    try:
        exec_read(namespace, name, ["/bin/sh", "-ec",
            'nc -w 3 "$1" "$2" </dev/null >/dev/null', "probe", address, str(port)])
        return True
    except MonitorProcessError:
        return False


def main():
    assert not (WORK / "path-started.json").exists(), "reconcile_started_path_check"
    staged = json.loads((WORK / "stage-result.json").read_text())
    assert staged["staged"]
    deadline = time.monotonic() + 600
    save("path-started.json", {"sourceSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                              "maximumSeconds": 600, "productionChanged": False})
    forward = None
    observations = {}
    try:
        backend = pod(NAMESPACE, "app=ntfy-qualification")
        edge = pod(EDGE, "app=ntfy-edge")
        ca = public_cert("synthetic-ca")
        cafile = WORK / "public-fixture-ca.crt"
        cafile.write_bytes(ca)
        original = fingerprint(public_cert("synthetic-leaf"))
        ports = []
        for _ in range(2):
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                ports.append(listener.getsockname()[1])
        with (WORK / "port-forward.log").open("xb") as output:
            forward = subprocess.Popen(BASE + ["port-forward", "-n", EDGE, "pod/" + edge["metadata"]["name"],
                f"{ports[0]}:8443", f"{ports[1]}:8000", "--address=127.0.0.1"],
                stdout=output, stderr=subprocess.STDOUT)

        def connection(hostname=NAME, trusted=True):
            context = ssl.create_default_context(cafile=str(cafile)) if trusted else ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            return PinnedHTTPSConnection(urlsplit(f"https://{hostname}:{ports[0]}/"),
                                         "127.0.0.1", context)

        def request(method, path, token=None, body=None):
            c = connection()
            try:
                headers = {"Authorization": "Bearer " + token} if token else {}
                c.request(method, path, body=body, headers=headers)
                response = c.getresponse()
                value = response.read(65537)
                assert len(value) <= 65536
                return response.status, value
            finally:
                c.close()

        def served():
            c = connection()
            try:
                c.connect()
                return hashlib.sha256(c.sock.getpeercert(binary_form=True)).hexdigest()
            finally:
                c.close()

        started = time.monotonic()
        while True:
            try:
                if request("GET", "/v1/health")[0] == 200:
                    break
            except (OSError, http.client.HTTPException):
                pass
            assert time.monotonic() - started < 25 and forward.poll() is None
            time.sleep(.25)
        assert served() == original
        tls = {"routedFingerprintEqualsIssuedLeaf": True}
        for label, kwargs in (("wrongCARejected", {"trusted": False}),
                              ("wrongNameRejected", {"hostname": "wrong.invalid"})):
            c = connection(**kwargs)
            try:
                c.connect()
            except ssl.SSLCertVerificationError:
                tls[label] = True
            else:
                raise RuntimeError("routed_trust_rejection_missing")
            finally:
                c.close()
        plain = http.client.HTTPConnection("127.0.0.1", ports[0], timeout=3)
        try:
            plain.request("GET", "/v1/health")
            response = plain.getresponse()
            assert response.status >= 400
        except (OSError, http.client.HTTPException):
            pass
        finally:
            plain.close()
        tls["plaintextRejected"] = True

        def control():
            c = http.client.HTTPConnection("127.0.0.1", ports[1], timeout=5)
            try:
                c.request("GET", "/control")
                r = c.getresponse()
                assert r.status in (301, 302, 307, 308)
                assert r.getheader("Location") == "https://control.invalid/checked"
                return r.status
            finally:
                c.close()

        observations["tls"] = tls
        observations["httpControlBefore"] = control()
        service = call(["get", "service", "private-ntfy", "-n", NAMESPACE, "-o", "json"])
        policy = []
        for ns, name, allowed in ((EDGE, "allowed-probe", True), (EDGE, "unselected-probe", False),
                                   (NAMESPACE, "same-namespace-probe", False), (DENIED, "denied-probe", False)):
            source = call(["get", "pod", name, "-n", ns, "-o", "json"])
            assert source["metadata"]["labels"][LABEL] == OWNER
            assert tcp(ns, name, edge["status"]["podIP"], 8000), "source_positive_control_failed"
            for target, port in ((service["spec"]["clusterIP"], 443), (backend["status"]["podIP"], 8443)):
                outcome = tcp(ns, name, target, port)
                assert outcome == allowed, "network_policy_outcome_mismatch"
                policy.append({"source": name, "namespace": ns, "node": source["spec"]["nodeName"],
                               "target": target, "port": port, "connected": outcome})
        observations["policy"] = policy
        observations["ambientEdge"] = {"podUID": edge["metadata"]["uid"],
            "node": edge["spec"]["nodeName"], "labels": edge["metadata"]["labels"],
            "routeFromAmbientSelectedEdgeSucceeded": True}
        observations["hostProbeException"] = "Kubelet HTTPS probes Ready; not treated as ordinary-pod access"
        backend_name = backend["metadata"]["name"]
        dns = exec_read(NAMESPACE, backend_name, ["cat", "/etc/resolv.conf"]).decode()
        dns_ip = next(line.split()[1] for line in dns.splitlines() if line.startswith("nameserver"))
        assert tcp(EDGE, "allowed-probe", dns_ip, 53)
        assert not tcp(NAMESPACE, backend_name, dns_ip, 53)
        exec_read(EDGE, "allowed-probe", ["timeout", "5", "nslookup", "kubernetes.default.svc.cluster.local"])
        try:
            exec_read(NAMESPACE, backend_name, ["timeout", "5", "nslookup", "kubernetes.default.svc.cluster.local"])
        except MonitorProcessError:
            pass
        else:
            raise RuntimeError("target_dns_egress_allowed")
        assert tcp(EDGE, "allowed-probe", "192.168.0.6", 2002)
        assert not tcp(NAMESPACE, backend_name, "192.168.0.6", 2002)
        observations["egress"] = {"dnsTCPAndUDPDeniedWithPositiveControls": True,
            "ownedLANNodeTCPDeniedWithPositiveControl": True, "unsolicitedPublicScan": False}
        resource_data = exec_read(NAMESPACE, backend_name, ["/bin/sh", "-ec",
            "id -u; for f in memory.max memory.swap.max cpu.max pids.max memory.current memory.events; "
            "do echo $f; cat /sys/fs/cgroup/$f; done; "
            "grep -E '^(CapEff|NoNewPrivs|Seccomp|VmRSS):' /proc/1/status; "
            "awk '$2==\"/\" || $2==\"/auth\" || $2==\"/tmp\" {print $2,$3,$4}' /proc/mounts"]).decode()
        assert resource_data.startswith("1000\n")
        assert "268435456" in resource_data and "25000 100000" in resource_data
        observations["actualResourceMetadata"] = resource_data
        tokens = json.loads((WORK / "synthetic-client.json").read_text())["tokens"]
        status, raw = request("POST", "/bortus-certificates", tokens[0], b"isolated-route-persistence")
        assert status == 200
        message_id = json.loads(raw)["id"]
        status, raw = request("GET", "/bortus-certificates/json?poll=1&since=all", tokens[2])
        assert status == 200 and any(json.loads(line).get("id") == message_id for line in raw.splitlines())
        observations["machineReceipt"] = {"id": message_id, "attendedReceipt": False}
        leaf = call(["get", "certificate", "synthetic-leaf", "-n", NAMESPACE, "-o", "json"])
        old_revision = leaf["status"]["revision"]
        patch("certificate", "synthetic-leaf", NAMESPACE, leaf, [{
            "op": "replace", "path": "/spec/dnsNames", "value": [NAME, "ntfy-rotation.invalid"]}])
        renewal_deadline = time.monotonic() + 120
        while time.monotonic() < renewal_deadline:
            leaf = call(["get", "certificate", "synthetic-leaf", "-n", NAMESPACE, "-o", "json"])
            renewed = fingerprint(public_cert("synthetic-leaf"))
            if leaf.get("status", {}).get("revision", 0) > old_revision and renewed != original:
                break
            time.sleep(2)
        else:
            raise RuntimeError("synthetic_cert_reissue_timeout")
        projection_deadline = time.monotonic() + 120
        while time.monotonic() < projection_deadline:
            projected = exec_read(NAMESPACE, backend_name, ["cat", "/tls/tls.crt"])
            if fingerprint(projected) == renewed:
                break
            time.sleep(2)
        else:
            raise RuntimeError("synthetic_projection_timeout")
        assert served() == original, "startup_tls_behavior_differed_reconcile"
        previous = call(["get", "pod", "private-ntfy", "-n", NAMESPACE, "-o", "json"])
        assert previous["metadata"]["uid"] == backend["metadata"]["uid"]
        assert previous["metadata"]["labels"][LABEL] == OWNER
        call(["delete", "--raw", f"/api/v1/namespaces/{NAMESPACE}/pods/private-ntfy", "-f", "-"],
             {"apiVersion": "v1", "kind": "DeleteOptions",
              "preconditions": {"uid": previous["metadata"]["uid"],
                                "resourceVersion": previous["metadata"]["resourceVersion"]}})
        deleted_deadline = time.monotonic() + 40
        while time.monotonic() < deleted_deadline:
            remaining = call(["get", "pods", "-n", NAMESPACE,
                              "--field-selector=metadata.name=private-ntfy", "-o", "json"])
            if not remaining["items"]:
                break
            time.sleep(1)
        else:
            raise RuntimeError("owned_pod_deletion_timeout")
        replacement = {"apiVersion": "v1", "kind": "Pod", "metadata": {
            "name": "private-ntfy", "namespace": NAMESPACE, "labels": previous["metadata"]["labels"],
            "annotations": {"bortus.jtmb.cc/verified-leaf": renewed}}, "spec": previous["spec"]}
        replacement["spec"].pop("nodeName", None)
        call(["create", "-f", "-", "-o", "json"], replacement)
        ready_deadline = time.monotonic() + 120
        while time.monotonic() < ready_deadline:
            try:
                current = pod(NAMESPACE, "app=ntfy-qualification")
                if current["metadata"]["uid"] != backend["metadata"]["uid"] and served() == renewed:
                    break
            except (OSError, AssertionError, http.client.HTTPException):
                pass
            time.sleep(2)
        else:
            raise RuntimeError("new_endpoint_fingerprint_timeout")
        status, raw = request("GET", "/bortus-certificates/json?poll=1&since=all", tokens[2])
        assert status == 200 and any(json.loads(line).get("id") == message_id for line in raw.splitlines())
        claim = call(["get", "pvc", "private-ntfy-qualification-cache", "-n", NAMESPACE, "-o", "json"])
        assert claim["metadata"]["uid"] == staged["claim"]["uid"]
        observations["renewal"] = {"certManagerIssuedNewRevision": leaf["status"]["revision"],
            "projectedFingerprint": renewed, "oldServedAfterProjection": original,
            "servedAfterGuardedRecreate": renewed, "oldPodUID": backend["metadata"]["uid"],
            "newPodUID": current["metadata"]["uid"], "autonomousRotationControllerInstalled": False}
        observations["retainedCache"] = {"messageIDPreserved": message_id, "claimUID": claim["metadata"]["uid"],
            "authStoreRecreated": True, "claimReplaced": False}
        observations["httpControlAfter"] = control()
        assert time.monotonic() < deadline
        save("path-result.json", {"passed": True, "observations": observations, "productionChanged": False,
            "remaining": ["Actual DB-cap/refusal and bounded load evidence", "Safe unattended renewal controller",
                          "Attended subscriber/reader and later monitor/watchdog/lifecycle/network phases"]})
        print((WORK / "path-result.json").read_text())
    except Exception as error:
        save("path-failure.json", {"reason": type(error).__name__, "observations": observations,
                                   "reconcileBeforeRetry": True, "productionChanged": False})
        raise
    finally:
        if forward:
            forward.terminate()
            try:
                forward.wait(timeout=10)
            except subprocess.TimeoutExpired:
                forward.kill()
                forward.wait(timeout=5)


if __name__ == "__main__":
    main()
