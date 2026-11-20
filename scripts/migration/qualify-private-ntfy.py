#!/usr/bin/env python3
"""Qualify the pinned real ntfy image locally; never deploy or use live credentials.

One exclusive H attempt, private internal Docker network, loopback TLS only.
Interrupted attempts must be reconciled from started/result/container records.
"""
import argparse
import datetime as dt
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import select
import secrets
import socket
import socketserver
import ssl
import string
import subprocess
import time
import threading
import traceback
import urllib.request

import yaml

from certificate_monitor_notifications import PinnedHTTPSConnection, event_message, publish_ntfy
from ntfy_acl_contract import USERS, validate_material

REPO = Path(__file__).resolve().parents[2]
STAGE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/certificates-qualification-20261116")
CHART = Path("/mnt/c/Users/james/AppData/Local/BORTUS/repos/branconet-charts/flux/private-ntfy/resources.yaml")
INDEX = "sha256:038da2be5e668fee6d36a62884eea48975e1b71c29a56964e5298c1b9165a573"
MANIFEST = "sha256:6ceb27333175e3ce7d021bb883658858f2b8b883db316a73d0755dfa0b306fc4"
IMAGE = "docker.io/binwiederhier/ntfy@" + MANIFEST
CONFIG_ID = "sha256:758c18e6e6d58133f2684ca182aff417324db8df43511b4d8c52354fa341c6a1"
NODE = "sha256:c4d5523090a817b7aa86d2111241fdd4f66d1e27782b44160e6aa63b357ecb2d"
LABEL = "bortus.task=ntfy-server-qualification"


class LoopbackForwarder(socketserver.ThreadingTCPServer):
    """Byte-only forwarding into the owned internal network; never terminates TLS."""
    allow_reuse_address = False
    daemon_threads = True


class ForwardBytes(socketserver.BaseRequestHandler):
    def handle(self):
        backend = None
        try:
            backend = socket.create_connection(self.server.backend, timeout=3)
            self.request.settimeout(3)
            backend.settimeout(3)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                readable, _, _ = select.select([self.request, backend], [], [], 1)
                for source in readable:
                    data = source.recv(65536)
                    if not data:
                        return
                    (backend if source is self.request else self.request).sendall(data)
        except OSError:
            pass
        finally:
            if backend is not None:
                backend.close()


def command(args, *, data=None, timeout=30, check=True):
    p = subprocess.run(args, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if check and p.returncode:
        # No argv/backend output in exceptions; environment and stdin can contain synthetic secrets.
        raise RuntimeError("fixture_command_failed")
    return p


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def registry_binding():
    base = "https://registry-1.docker.io/v2/binwiederhier/ntfy/manifests/"
    with urllib.request.urlopen(
            "https://auth.docker.io/token?service=registry.docker.io&scope=repository:binwiederhier/ntfy:pull",
            timeout=20) as response:
        auth = json.loads(response.read(65537))
    headers = {"Authorization": "Bearer " + auth["token"],
               "Accept": "application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.docker.distribution.manifest.v2+json"}
    values = {}
    for digest in (INDEX, MANIFEST):
        with urllib.request.urlopen(urllib.request.Request(base + digest, headers=headers), timeout=20) as response:
            raw = response.read(1048577)
        if len(raw) > 1048576 or "sha256:" + hashlib.sha256(raw).hexdigest() != digest:
            raise RuntimeError("registry_manifest_bytes_mismatch")
        values[digest] = json.loads(raw)
    if (values[MANIFEST]["config"]["digest"] != CONFIG_ID or
            not any(v["digest"] == MANIFEST and v["platform"]["architecture"] == "amd64" and
                    v["platform"]["os"] == "linux" for v in values[INDEX]["manifests"])):
        raise RuntimeError("registry_platform_config_binding_mismatch")
    return {"index": INDEX, "linuxAMD64Manifest": MANIFEST, "config": CONFIG_ID,
            "manifestBytesVerified": True}


def main():
    global MANIFEST, IMAGE, CONFIG_ID
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--candidate-record", type=Path, help="Explicit verified local vendor-fixed build result")
    args = parser.parse_args()
    candidate = None
    if args.candidate_record:
        if args.candidate_record.resolve() != STAGE / "ntfy-zlib-fixed/build-result.json":
            parser.error("Only the explicit owned fixed-candidate record is supported")
        candidate = json.loads(args.candidate_record.read_text())
        if not (candidate["built"] and candidate["vendorSignatureVerified"] and
                candidate["ntfyExecutableUnchanged"] and candidate["exportAllBlobsVerified"]):
            parser.error("Candidate build evidence is incomplete")
        MANIFEST, IMAGE, CONFIG_ID = (candidate["candidateManifest"], candidate["candidateImage"],
                                      candidate["candidateConfig"])
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,25}", args.attempt):
        parser.error("Short lowercase attempt required")
    work = STAGE / ("ntfy-server-" + args.attempt)
    if work.exists():
        parser.error("Existing attempt requires reconciliation, not replay")
    os.umask(0o077)
    publisher = Path(json.loads((STAGE / "credential-bootstrap-publisher-result.json").read_text())["stage"])
    used = sum(int(command(["du", "-sx", "-B1", str(p)]).stdout.split()[0]) for p in (STAGE, publisher))
    ceiling = 4_250_000_000 if candidate else 4_000_000_000
    if used + 1_000_000_000 > ceiling:
        raise RuntimeError("qualification_peak_not_admitted")
    if Path("/sys/fs/ext4/loop0/errors_count").read_text().strip() != "0":
        raise RuntimeError("H_store_error_requires_reconciliation")
    expected_root = str(STAGE.parents[1] / "shared-docker-runtime/docker")
    if json.loads(command(["docker", "info", "--format", "{{json .DockerRootDir}}"]).stdout) != expected_root:
        raise RuntimeError("existing_H_daemon_required")
    if command(["docker", "ps", "-aq", "--filter", "label=" + LABEL]).stdout.strip():
        raise RuntimeError("existing_task_container_requires_reconciliation")
    work.mkdir(mode=0o700)
    name = "bortus-ntfy-" + args.attempt
    network = name + "-internal"
    index_before = hashlib.sha256((REPO / ".git/index").read_bytes()).hexdigest()
    binding = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (
        Path(__file__), CHART, REPO / "scripts/migration/certificate_monitor_notifications.py",
        REPO / "scripts/migration/ntfy_acl_contract.py")}
    if candidate:
        binding[str(args.candidate_record)] = hashlib.sha256(args.candidate_record.read_bytes()).hexdigest()
    already = command(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"], check=False)
    preexisting = already.returncode == 0
    write(work / "started.json", {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(), "sourceSHA256": binding,
        "indexSHA256": index_before, "registryIndex": INDEX, "manifest": MANIFEST,
        "expectedConfigID": CONFIG_ID, "preexistingImage": preexisting,
        "stageBytesBefore": used, "incrementalRuntimeReserveBytes": 1_000_000_000,
        "combinedCeilingBytes": ceiling, "productionConnected": False,
        "runtimeContainment": "Existing H daemon/containerd configuration; private internal network, loopback publishing",
        "privateRuntimeStat": "Earlier permission denial preserved; public daemon/config paths used, no permission change"})
    containers, secrets_to_redact, logs = [], [], []
    proxies = {}
    network_created = False
    result = {}
    try:
        registry = ({"kind": "local-vendor-fixed", "linuxAMD64Manifest": MANIFEST,
                     "config": CONFIG_ID, "baseImage": candidate["baseImage"],
                     "exportAllBlobsVerified": True} if candidate else registry_binding())
        if not preexisting:
            if candidate:
                raise RuntimeError("fixed_candidate_not_present_no_pull_fallback")
            command(["docker", "pull", "--platform", "linux/amd64", IMAGE], timeout=180)
        image = json.loads(command(["docker", "image", "inspect", IMAGE]).stdout)[0]
        # The current containerd image store exposes the manifest as image ID.
        # Require its descriptor and raw registry content binding, not an alias.
        if (image.get("Descriptor", {}).get("digest") != MANIFEST or
                image["Id"] not in (MANIFEST, CONFIG_ID) or
                image["Architecture"] != "amd64" or image["Os"] != "linux"):
            raise RuntimeError("pinned_image_identity_mismatch")
        if image["Size"] > 500_000_000:
            raise RuntimeError("pinned_image_exceeds_reserved_footprint")
        if candidate and image["Config"]["User"] != "1000:1000":
            raise RuntimeError("fixed_candidate_default_user_mismatch")
        write(work / "image.json", {"id": image["Id"], "sizeBytes": image["Size"], "repoDigests": image["RepoDigests"],
                                    "newlyPulled": not preexisting, "registryBinding": registry})
        version = command(["docker", "run", "--rm", "--pull=never", "--network", "none",
                           "--read-only", *( [] if candidate else ["--user", "1000:1000"]), "--cpus", ".25",
                           "--memory", "256m", "--memory-swap", "256m", "--pids-limit", "64", "--cap-drop", "ALL",
                           "--security-opt", "no-new-privileges", IMAGE, "--version"]).stdout.decode()
        if "2.38.1" not in version:
            raise RuntimeError("ntfy_version_mismatch")
        for folder in ("config", "tls", "cache", "tmp", "auth-first", "auth-restart"):
            (work / folder).mkdir(mode=0o700)
        resources = list(yaml.safe_load_all(CHART.read_text()))
        config = next(v for v in resources if v and v["kind"] == "ConfigMap")["data"]["server.yml"]
        (work / "config/server.yml").write_text(config)
        command(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                 "-subj", "/CN=notifications.lan", "-addext", "subjectAltName=DNS:notifications.lan",
                 "-keyout", str(work / "tls/tls.key"), "-out", str(work / "tls/tls.crt")])
        passwords = [secrets.token_urlsafe(30) for _ in USERS]
        secrets_to_redact.extend(passwords)
        code = ("const fs=require('fs'),b=require('/bcryptjs');"
                "console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(p=>b.hashSync(p,10))));")
        helper_name = name + "-hash"
        helper = command([
            "docker", "create", "--name", helper_name, "--label", LABEL,
            "--pull=never", "-i", "--network", "none", "--read-only",
            "--user", "1000:1000", "--cpus", ".5", "--memory", "256m", "--memory-swap", "256m",
            "--pids-limit", "32", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--mount", f"type=bind,src={STAGE / 'node_modules/bcryptjs'},dst=/bcryptjs,readonly",
            NODE, "node", "-e", code], timeout=120).stdout.decode().strip()
        hashes = json.loads(command(["docker", "start", "-ai", helper],
                                    data=json.dumps(passwords).encode(), timeout=120).stdout)
        command(["docker", "rm", helper])
        secrets_to_redact.extend(hashes)
        tokens = ["tk_" + "".join(secrets.choice(string.ascii_letters + string.digits + "-_") for _ in range(29)) for _ in USERS]
        secrets_to_redact.extend(tokens)
        material = {"users": ",".join(f"{u}:{h}:user" for u, h in zip(USERS, hashes)),
                    "tokens": ",".join(f"{u}:{t}" for u, t in zip(USERS, tokens))}
        validate_material(material)
        env = work / "synthetic.env"
        env.write_text("NTFY_AUTH_USERS=" + material["users"] + "\nNTFY_AUTH_TOKENS=" + material["tokens"] + "\n")
        command(["docker", "network", "create", "--internal", "--label", LABEL, network])
        network_created = True
        n = json.loads(command(["docker", "network", "inspect", network]).stdout)[0]
        if not n["Internal"]:
            raise RuntimeError("internal_network_required")

        def start(phase):
            container_name = name + "-" + phase
            run = ["docker", "run", "-d", "--pull=never", "--name", container_name, "--label", LABEL,
                   "--network", network, "--read-only", *( [] if candidate else ["--user", "1000:1000"]),
                   "--cpus", ".25", "--memory", "256m", "--memory-swap", "256m", "--pids-limit", "64",
                   "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--ulimit", "core=0",
                   "--log-opt", "max-size=256k", "--log-opt", "max-file=1", "--env-file", str(env)]
            for host, guest, readonly in (("config", "/etc/ntfy", True), ("tls", "/tls", True),
                                         ("cache", "/cache", False), ("tmp", "/tmp", False),
                                         ("auth-" + phase, "/auth", False)):
                run += ["--mount", f"type=bind,src={work / host},dst={guest}" + (",readonly" if readonly else "")]
            container = command(run + [IMAGE, "serve", "--config", "/etc/ntfy/server.yml"]).stdout.decode().strip()
            containers.append(container)
            write(work / ("container-" + phase + ".json"), {"id": container, "name": container_name, "image": image["Id"],
                                                           "authStore": "fresh synthetic ephemeral store", "cacheStore": "same H fixture"})
            info = json.loads(command(["docker", "inspect", container]).stdout)[0]
            address = info["NetworkSettings"]["Networks"][network]["IPAddress"]
            if not address:
                raise RuntimeError("internal_fixture_address_missing")
            proxy = LoopbackForwarder(("127.0.0.1", 0), ForwardBytes)
            proxy.backend = (address, 8443)
            thread = threading.Thread(target=proxy.serve_forever, daemon=True)
            thread.start()
            proxies[container] = (proxy, thread)
            port = proxy.server_address[1]
            return container, port

        def request(port, method, path, token=None, body=None, *, hostname="notifications.lan", trusted=True):
            context = ssl.create_default_context(cafile=str(work / "tls/tls.crt")) if trusted else ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            target = __import__("urllib.parse", fromlist=["urlsplit"]).urlsplit(f"https://{hostname}:{port}/unused")
            connection = PinnedHTTPSConnection(target, "127.0.0.1", context)
            try:
                headers = {"Authorization": "Bearer " + token} if token is not None else {}
                connection.request(method, path, body=body, headers=headers)
                response = connection.getresponse()
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise RuntimeError("fixture_response_limit")
                return response.status, raw
            finally:
                connection.close()

        def await_ready(container, port):
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                info = json.loads(command(["docker", "inspect", container]).stdout)[0]
                if not info["State"]["Running"]:
                    raise RuntimeError("ntfy_server_exited_before_ready")
                try:
                    if request(port, "GET", "/v1/health")[0] == 200:
                        return
                except (OSError, http.client.HTTPException):
                    pass
                time.sleep(.1)
            raise RuntimeError("ntfy_readiness_timeout")

        container, port = start("first")
        await_ready(container, port)
        denials = []
        topics = ("bortus-certificates", "bortus-monitor-health")
        events = []
        for index, topic in enumerate(topics):
            event = {"id": "fixture-event-" + str(index), "resource": "monitor-heartbeat",
                     "uid": "fixture-node02", "state": "missed", "createdAt": dt.datetime.now(dt.timezone.utc).isoformat()}
            destination = {"version": 1, "url": f"https://notifications.lan:{port}/{topic}", "address": "127.0.0.1",
                           "caFile": str(work / "tls/tls.crt"), "tokenFile": str(env)}
            if publish_ntfy(destination, event, token=tokens[index], ca_file=work / "tls/tls.crt") != {"accepted": True}:
                raise RuntimeError("publisher_not_accepted")
            events.append(event_message(event))
        # Effective permissions are tested through the real HTTP endpoints, not the syntax helper.
        for who, token, allowed_reads, allowed_writes in (
                ("monitor", tokens[0], (), (topics[0],)), ("watchdog", tokens[1], (), (topics[1],)),
                ("subscriber", tokens[2], topics, ()), ("anonymous", None, (), ()),
                ("invalid-token", "tk_" + "0" * 29, (), ())):
            for topic in (*topics, "unrelated-topic"):
                for action in ("read", "write"):
                    allowed = topic in (allowed_reads if action == "read" else allowed_writes)
                    if allowed:
                        continue  # Positive sends/reads are checked with message identity below.
                    status, _ = request(port, "GET" if action == "read" else "POST",
                                        "/" + topic + ("/json?poll=1&since=all" if action == "read" else ""),
                                        token, b"must-not-publish" if action == "write" else None)
                    if status not in (401, 403):
                        raise RuntimeError("effective_acl_denial_failed")
                    denials.append({"identity": who, "topic": topic, "action": action, "status": status})

        def received(port):
            messages = []
            for topic, expected in zip(topics, events):
                status, raw = request(port, "GET", "/" + topic + "/json?poll=1&since=all", tokens[2])
                if status != 200:
                    raise RuntimeError("subscriber_read_failed")
                rows = [json.loads(line) for line in raw.splitlines() if line]
                matching = [v for v in rows if v.get("event") == "message" and v.get("topic") == topic and v.get("message") == expected]
                if len(matching) != 1 or len(rows) != 1:
                    raise RuntimeError("subscriber_message_or_denied_write_mismatch")
                messages.append({"topic": topic, "serverMessageID": matching[0]["id"]})
            return messages

        first_messages = received(port)
        tls_checks = {}
        for check, options in (("untrustedCARejected", {"trusted": False}), ("wrongHostnameRejected", {"hostname": "wrong.invalid"})):
            try:
                request(port, "GET", "/v1/health", **options)
            except ssl.SSLCertVerificationError:
                tls_checks[check] = True
            else:
                raise RuntimeError("tls_trust_or_hostname_failure")
        plain = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        try:
            plain.request("GET", "/v1/health")
            response = plain.getresponse()
            if response.status != 400:
                raise RuntimeError("plaintext_not_rejected")
            tls_checks["plaintextRejected"] = True
        finally:
            plain.close()
        command(["docker", "stop", "--time", "10", container])
        proxy, thread = proxies.pop(container)
        proxy.shutdown()
        proxy.server_close()
        thread.join(timeout=5)
        log = command(["docker", "logs", container])
        logs.append((log.stdout + log.stderr).decode(errors="replace"))
        command(["docker", "rm", container])
        containers.remove(container)
        container, restart_port = start("restart")
        await_ready(container, restart_port)
        if received(restart_port) != first_messages:
            raise RuntimeError("persistent_cache_message_identity_changed")
        result = {"passed": True, "imageID": image["Id"], "registryBinding": registry, "imageSizeBytes": image["Size"],
                  "sourceSHA256": binding, "version": "2.38.1", "sourceConfigUnmodified": True,
                  "internalNetwork": True, "publishAddress": "127.0.0.1",
                  "hostAccess": "Loopback byte-only forwarder; no Docker host-port publish or TLS termination",
                  "resources": {
                      "memoryBytes": 268435456, "swapBytes": 0, "cpuQuota": ".25", "pids": 64,
                      "uid": 1000, "readOnlyRoot": True, "capabilities": "none"},
                  "tls": tls_checks | {"trustedHostnameTLS12OrNewer": True},
                  "positiveTopicPublishes": 2, "authenticatedSubscriberTopicsReceived": first_messages,
                  "effectiveDenials": denials, "isolatedRestartPreservesMessageIDs": True,
                  "freshAuthStoreReprovisionedOnRestart": True, "humanOrPhoneReceipt": False,
                  "productionConnected": False, "noProductionActivation": True}
    except Exception as error:
        result = {"passed": False, "reason": str(error) if isinstance(error, RuntimeError) else type(error).__name__,
                  "failureFrames": [{"file": Path(frame.filename).name, "line": frame.lineno}
                                    for frame in traceback.extract_tb(error.__traceback__)],
                  "outcomeRequiresReconciliation": True, "productionConnected": False, "sourceSHA256": binding}
    finally:
        # Never log synthetic credential hashes from an interrupted helper.
        checked = command(["docker", "inspect", name + "-hash"], check=False)
        if checked.returncode == 0:
            helper_info = json.loads(checked.stdout)[0]
            if (helper_info["Config"]["Image"] != NODE or
                    helper_info["Config"]["Labels"].get("bortus.task") != "ntfy-server-qualification" or
                    not any(m["Source"] == str(STAGE / "node_modules/bcryptjs") and
                            m["Destination"] == "/bcryptjs" and not m["RW"] for m in helper_info["Mounts"])):
                raise RuntimeError("hash_helper_ownership_mismatch")
            if helper_info["State"]["Running"]:
                command(["docker", "stop", "--time", "5", helper_info["Id"]])
            command(["docker", "rm", helper_info["Id"]])
        for proxy, thread in proxies.values():
            proxy.shutdown()
            proxy.server_close()
            thread.join(timeout=5)
        for container in list(containers):
            command(["docker", "stop", "--time", "10", container], check=False)
            p = command(["docker", "logs", container], check=False)
            logs.append((p.stdout + p.stderr).decode(errors="replace"))
            command(["docker", "rm", container])
            containers.remove(container)
        if network_created:
            command(["docker", "network", "rm", network])
        safe_log = "\n".join(logs)
        for value in secrets_to_redact:
            safe_log = safe_log.replace(value, "[REDACTED]")
        (work / "sanitized-server.log").write_text(safe_log[:131072])
        result["fixtureContainersAndNetworkRemoved"] = True
        result["indexUnchanged"] = hashlib.sha256((REPO / ".git/index").read_bytes()).hexdigest() == index_before
        result["sourceUnchanged"] = all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in binding.items())
        result["syntheticPayloadCleanupRequired"] = True
        result["imageRetirementReviewRequired"] = not preexisting
        write(work / "result.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("sourceSHA256", "effectiveDenials")}, indent=2))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
