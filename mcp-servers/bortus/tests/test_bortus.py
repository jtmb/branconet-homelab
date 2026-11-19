"""Focused tests for the shared BORTUS MCP.

Every test here protects a contract from 02_DOMAIN_AND_PRODUCT_CONTRACTS.md:
a denied request must never fetch or start anything, an approved run must
deliver values into the container and leave nothing behind, and the caller
must never receive a value in any form. Synthetic markers stand in for real
credentials; nothing touches a cluster.
"""

import base64
import importlib.util
import json
import os
import socket
import socketserver
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import engine
import kube
import policy
import runner
import server


MARKER = "marker-7d1f3b9e-do-not-print"


def write_private(path, text):
    """Create a policy file with the ownership and mode the runner requires."""
    path.write_text(text)
    os.chmod(path, 0o600)
    return str(path)


def profile(**overrides):
    """Return one valid profile document for tests to bend."""
    document = {
        "id": "local-smoke",
        "image_digest": "example.test/app@sha256:" + "a" * 64,
        "bindings": [
            {"namespace": "testing", "secret": "example", "key": "api_token",
             "delivery": "env", "destination": "EXAMPLE_TOKEN"},
        ],
        "probe": {"kind": "running", "seconds": 1},
        "timeout_seconds": 20,
    }
    document.update(overrides)
    return document


def profiles_document(*items):
    return json.dumps({"version": 1, "profiles": list(items) or [profile()]})


def grants_document(uid=1000, profile_id="local-smoke", ttl=600):
    return json.dumps({"version": 1, "grants": [
        {"uid": uid, "profile": profile_id, "expires_at": time.time() + ttl}]})


def secret_object(namespace, name, data):
    return json.dumps({"kind": "Secret", "metadata": {"namespace": namespace, "name": name},
                       "data": {key: base64.b64encode(value).decode()
                                for key, value in data.items()}})


class FakeTransport:
    """Record requests and answer from a fixed map of paths."""

    def __init__(self, responses):
        self.responses = responses
        self.paths = []

    def get(self, path, limit=None):
        self.paths.append(path)
        status, body = self.responses.get(path, (404, b"{}"))
        return status, body


class FakeSource:
    """Stand-in for the Kubernetes reader with optional hook behaviour."""

    def __init__(self, objects=None, error=None, hook=None):
        self.objects = objects or {}
        self.error = error
        self.hook = hook
        self.calls = []

    def fetch(self, bindings):
        self.calls.append(list(bindings))
        if self.hook:
            self.hook()
        if self.error:
            raise self.error
        return self.objects


class FakeEngine:
    """Deterministic container engine for runner tests."""

    def __init__(self, remove_error=False, gate=None):
        self.created = []
        self.removed = []
        self.started = []
        self.remove_error = remove_error
        self.gate = gate
        self.owned_ids = []
        self.running = True

    def owned(self):
        return list(self.owned_ids)

    def create(self, run_id, profile_doc, env, mounts):
        self.created.append({"run_id": run_id, "image": profile_doc["image_digest"],
                             "env": dict(env), "mounts": list(mounts)})
        return f"container-{run_id}"

    def start(self, identifier):
        self.started.append(identifier)
        if self.gate is not None:
            self.gate.wait(5)

    def inspect(self, identifier):
        return (True, 0, True)

    def address(self, identifier):
        return None

    def remove(self, identifier):
        if self.remove_error:
            raise engine.EngineError("refused")
        self.removed.append(identifier)


class PolicyTests(unittest.TestCase):
    """Schema and grant decisions are the first access control layer."""

    def test_unknown_profile_field_is_rejected(self):
        with self.assertRaises(policy.PolicyError):
            policy.load_profiles(profiles_document(profile(extra="x")))

    def test_image_must_be_digest_pinned(self):
        with self.assertRaises(policy.PolicyError):
            policy.load_profiles(profiles_document(profile(image_digest="example.test/app:latest")))

    def test_duplicate_destination_is_rejected(self):
        bindings = [
            {"namespace": "testing", "secret": "a", "key": "k", "delivery": "env",
             "destination": "TOKEN"},
            {"namespace": "testing", "secret": "b", "key": "k", "delivery": "env",
             "destination": "TOKEN"},
        ]
        with self.assertRaises(policy.PolicyError):
            policy.load_profiles(profiles_document(profile(bindings=bindings)))

    def test_tcp_probe_requires_bridge_network(self):
        with self.assertRaises(policy.PolicyError):
            policy.load_profiles(profiles_document(
                profile(probe={"kind": "tcp", "port": 80}, network="none")))

    def test_grant_expiry_must_be_bounded(self):
        for ttl in (0, 10, 25 * 3600):
            with self.assertRaises(policy.PolicyError):
                policy.load_grants(grants_document(ttl=ttl))

    def test_authorize_denies_unknown_expired_and_unapproved(self):
        profiles = policy.load_profiles(profiles_document())
        live = policy.load_profiles(profiles_document(profile(runtime_mode="live")))
        grants = policy.load_grants(grants_document(ttl=600))
        now = time.time()

        self.assertEqual(policy.authorize(profiles, grants, 999, "local-smoke", now),
                         (None, "not_authorized"))
        self.assertEqual(policy.authorize(profiles, grants, 1000, "other", now),
                         (None, "not_authorized"))
        self.assertEqual(policy.authorize(profiles, grants, 1000, "local-smoke",
                                          now + 3600), (None, "not_authorized"))
        self.assertEqual(policy.authorize(live, grants, 1000, "local-smoke", now),
                         (None, "not_authorized"))
        self.assertIsNotNone(policy.authorize(profiles, grants, 1000, "local-smoke", now)[0])


class SecretSourceTests(unittest.TestCase):
    """Only the named objects and keys are read, with size rules applied."""

    def test_exact_paths_and_unlisted_keys_ignored(self):
        transport = FakeTransport({
            "/api/v1/namespaces/testing/secrets/example":
                (200, secret_object("testing", "example",
                                    {"api_token": MARKER.encode(), "other": b"ignored"}).encode())})
        source = kube.SecretSource(transport)
        profile_doc = policy.load_profiles(profiles_document())["local-smoke"]
        objects = source.fetch(profile_doc["bindings"])
        deliveries = kube.materialize(profile_doc["bindings"], objects)
        self.assertEqual(transport.paths, ["/api/v1/namespaces/testing/secrets/example"])
        self.assertEqual(len(deliveries), 1)
        self.assertEqual(deliveries[0].data, MARKER.encode())
        self.assertNotIn("ignored", repr(deliveries))

    def test_missing_key_is_a_fixed_error(self):
        transport = FakeTransport({
            "/api/v1/namespaces/testing/secrets/example":
                (200, secret_object("testing", "example", {"unrelated": b"x"}).encode())})
        profile_doc = policy.load_profiles(profiles_document())["local-smoke"]
        objects = kube.SecretSource(transport).fetch(profile_doc["bindings"])
        with self.assertRaises(kube.CredentialError):
            kube.materialize(profile_doc["bindings"], objects)

    def test_404_and_oversized_reply_are_unavailable(self):
        profile_doc = policy.load_profiles(profiles_document())["local-smoke"]
        with self.assertRaises(kube.CredentialError):
            kube.SecretSource(FakeTransport({})).fetch(profile_doc["bindings"])
        big = FakeTransport({"/api/v1/namespaces/testing/secrets/example":
                             (200, b" " * (kube.MAX_OBJECT_BYTES + 1))})
        with self.assertRaises(kube.CredentialError):
            kube.SecretSource(big).fetch(profile_doc["bindings"])


class RunnerTests(unittest.TestCase):
    """The runner is the trust boundary: it must fail closed everywhere."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.run_root = self.root / "runs"
        self.run_root.mkdir(mode=0o700)
        self.profiles = write_private(self.root / "profiles.json", profiles_document())
        self.grants = write_private(self.root / "grants.json", grants_document())
        self.objects = {("testing", "example"): json.loads(
            secret_object("testing", "example", {"api_token": MARKER.encode()}))}
        self.source = FakeSource(self.objects)
        self.engine = FakeEngine()
        self.audit = self.root / "audit.jsonl"

    def tearDown(self):
        self.directory.cleanup()

    def make(self, source=None, engine=None):
        return runner.Runner(self.profiles, self.grants, None,
                             engine or self.engine, self.run_root,
                             audit_path=str(self.audit), source=source or self.source)

    def test_authorized_run_passes_delivers_and_cleans(self):
        instance = self.make()
        result = instance.handle(1000, {"profile": "local-smoke"})
        self.assertEqual(result["state"], "passed")
        self.assertEqual(len(self.engine.created), 1)
        self.assertEqual(self.engine.created[0]["env"], {"EXAMPLE_TOKEN": MARKER})
        self.assertEqual(self.engine.removed, [f"container-{result['run_id']}"])
        self.assertFalse(any(self.run_root.iterdir()))
        self.assertNotIn(MARKER, json.dumps(result))
        self.assertNotIn(MARKER, self.audit.read_text())

    def test_wrong_uid_never_fetches_or_starts(self):
        instance = self.make()
        self.assertEqual(instance.handle(4242, {"profile": "local-smoke"})["state"],
                         "not_authorized")
        self.assertEqual(self.source.calls, [])
        self.assertEqual(self.engine.created, [])

    def test_unknown_profile_and_extra_field_never_fetch(self):
        instance = self.make()
        self.assertEqual(instance.handle(1000, {"profile": "nope"})["state"], "not_authorized")
        self.assertEqual(instance.handle(1000, {"profile": "local-smoke", "image": "x"})["state"],
                         "invalid_request")
        self.assertEqual(self.source.calls, [])
        self.assertEqual(self.engine.created, [])

    def test_revocation_between_fetch_and_launch_never_starts(self):
        def revoke():
            write_private(self.root / "grants.json", json.dumps({"version": 1, "grants": []}))

        instance = self.make(source=FakeSource(self.objects, hook=revoke))
        self.assertEqual(instance.handle(1000, {"profile": "local-smoke"})["state"],
                         "not_authorized")
        self.assertEqual(self.engine.created, [])
        self.assertFalse(any(self.run_root.iterdir()))

    def test_busy_second_call_never_fetches(self):
        gate = threading.Event()
        instance = self.make(engine=FakeEngine(gate=gate))
        thread = threading.Thread(target=instance.handle,
                                  args=(1000, {"profile": "local-smoke"}))
        thread.start()
        for _ in range(200):
            if instance.engine.created:
                break
            time.sleep(0.01)
        fetched = len(instance.source.calls)
        self.assertEqual(instance.handle(1000, {"profile": "local-smoke"})["state"], "busy")
        self.assertEqual(len(instance.source.calls), fetched)
        gate.set()
        thread.join(10)

    def test_cleanup_failure_closes_admission(self):
        instance = self.make(engine=FakeEngine(remove_error=True))
        self.assertEqual(instance.handle(1000, {"profile": "local-smoke"})["state"],
                         "cleanup_required")
        self.assertTrue(instance.closed)
        self.assertEqual(instance.handle(1000, {"profile": "local-smoke"})["state"],
                         "cleanup_required")
        self.assertEqual(len(instance.engine.created), 1)

    def test_credential_error_maps_to_fixed_state(self):
        instance = self.make(source=FakeSource(error=kube.CredentialError("missing")))
        self.assertEqual(instance.handle(1000, {"profile": "local-smoke"})["state"],
                         "credential_unavailable")
        self.assertEqual(self.engine.created, [])

    def test_recover_removes_only_its_own_containers(self):
        self.engine.owned_ids = ["owned-1", "owned-2"]
        self.make().recover()
        self.assertEqual(self.engine.removed, ["owned-1", "owned-2"])
        failing = self.make(engine=FakeEngine(remove_error=True))
        failing.engine.owned_ids = ["owned-3"]
        with self.assertRaises(runner.CleanupRequired):
            failing.recover()
        self.assertTrue(failing.closed)


class SecretAccessTests(unittest.TestCase):
    """Direct reads obey the machine scope before any request is made."""

    NAMESPACE = "testing"
    NAME = "example"
    PATH = "/api/v1/namespaces/testing/secrets/example"

    def access(self, scope, body=None, status=200):
        transport = FakeTransport({self.PATH: (status, body if body is not None else json.dumps({
            "kind": "Secret", "data": {"token": base64.b64encode(b"abc").decode(),
                                       "blob": base64.b64encode(b"\xff\xfe").decode()},
        }).encode())})
        return server.SecretAccess(kube.SecretReader(transport), scope), transport

    def test_out_of_scope_denies_without_reading(self):
        instance, transport = self.access(["other-namespace"])
        result = instance.get({"namespace": self.NAMESPACE, "name": self.NAME})
        self.assertTrue(result["isError"])
        self.assertEqual(result["content"][0]["text"], server.SCOPE_MESSAGES["denied"])
        self.assertEqual(transport.paths, [])

    def test_named_entry_allows_only_that_secret(self):
        instance, transport = self.access(["testing/example"])
        allowed = instance.get({"namespace": "testing", "name": "example"})
        self.assertFalse(allowed.get("isError"))
        other = instance.get({"namespace": "testing", "name": "other"})
        self.assertTrue(other["isError"])
        self.assertEqual(other["content"][0]["text"], server.SCOPE_MESSAGES["denied"])
        self.assertEqual(transport.paths, [self.PATH])

    def test_allowed_read_returns_values_and_marks_binary(self):
        instance, transport = self.access(["*"])
        result = instance.get({"namespace": self.NAMESPACE, "name": self.NAME})
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["data"]["token"], "abc")
        self.assertEqual(payload["base64_keys"], ["blob"])
        self.assertEqual(transport.paths, [self.PATH])

    def test_key_filter_and_unknown_key(self):
        instance, _ = self.access(["*"])
        filtered = json.loads(instance.get({"namespace": self.NAMESPACE, "name": self.NAME,
                                            "keys": ["token"]})["content"][0]["text"])
        self.assertEqual(sorted(filtered["data"]), ["token"])
        missing = instance.get({"namespace": self.NAMESPACE, "name": self.NAME,
                                "keys": ["nope"]})
        self.assertTrue(missing["isError"])
        self.assertEqual(missing["content"][0]["text"], server.SCOPE_MESSAGES["not_found"])

    def test_bad_arguments_are_rejected(self):
        instance, transport = self.access(["*"])
        for arguments in ({"namespace": "../x", "name": "y"}, {"namespace": "a"},
                          {"namespace": "a", "name": "b", "keys": ["bad key"]},
                          {"namespace": "a", "name": "b", "extra": 1}):
            self.assertTrue(instance.get(arguments)["isError"], arguments)
        self.assertEqual(transport.paths, [])

    def test_names_listing_respects_scope(self):
        body = json.dumps({"kind": "SecretList", "items": [
            {"metadata": {"name": "a"}}, {"metadata": {"name": "b"}}]}).encode()
        transport = FakeTransport({"/api/v1/namespaces/testing/secrets": (200, body)})
        instance = server.SecretAccess(kube.SecretReader(transport), ["testing"])
        result = instance.names({"namespace": "testing"})
        self.assertEqual(json.loads(result["content"][0]["text"])["names"], ["a", "b"])
        denied = instance.names({"namespace": "other"})
        self.assertEqual(denied["content"][0]["text"], server.SCOPE_MESSAGES["denied"])


class ServerTests(unittest.TestCase):
    """The stdio layer exposes exactly the intended tools and fixed text."""

    class Child:
        def __init__(self):
            self.sent = []
            self.ready = False

        def ensure_fresh(self):
            """The fake child never renews credentials."""

        def mark_ready(self):
            """Record the handshake so repeated calls do not re-initialize."""
            self.ready = True

        def notify(self, message):
            self.sent.append(message)

        def request(self, message, timeout=30):
            self.sent.append(message)
            if "id" not in message:
                return {}
            if message["method"] == "initialize":
                return {"jsonrpc": "2.0", "id": message["id"],
                        "result": {"protocolVersion": "2025-06-18",
                                   "capabilities": {"tools": {}},
                                   "serverInfo": {"name": "inventory", "version": "1"}}}
            if message["method"] == "tools/list":
                return {"jsonrpc": "2.0", "id": message["id"], "result": {"tools": [
                    {"name": "events_list", "inputSchema": {}},
                    {"name": "pods_list", "inputSchema": {}},
                    {"name": "resources_list", "inputSchema": {}},
                ]}}
            return {"jsonrpc": "2.0", "id": message["id"],
                    "result": {"content": [{"type": "text", "text": "{}"}]}}

    class Runner:
        def __init__(self, reply):
            self.reply = reply
            self.profiles = []

        def call(self, profile):
            self.profiles.append(profile)
            return self.reply

    def session(self, reply=None, with_runner=True):
        instance = server.Session(self.Child(),
                                  self.Runner(reply or {"state": "passed", "run_id": "abc"})
                                  if with_runner else None)
        return instance

    def test_tools_list_is_inventory_plus_one_run_tool(self):
        names = [tool["name"] for tool in self.session().tools()]
        self.assertEqual(sorted(names), ["bortus_secrets_run", "events_list",
                                         "pods_list", "resources_list"])

    def test_tools_list_without_runner_hides_run_tool(self):
        names = [tool["name"] for tool in self.session(with_runner=False).tools()]
        self.assertNotIn("bortus_secrets_run", names)
        self.assertEqual(len(names), 3)

    def test_initialize_reports_bortus(self):
        result = self.session().initialize({"protocolVersion": "2025-06-18"})
        self.assertEqual(result["serverInfo"]["name"], "bortus")

    def test_run_passes_profile_and_returns_only_fixed_state(self):
        session = server.Session(self.Child(), self.Runner({"state": "passed", "run_id": "abc"}))
        result = session.call("bortus_secrets_run", {"profile": "local-smoke"})
        self.assertEqual(json.loads(result["content"][0]["text"]),
                         {"state": "passed", "run_id": "abc"})

    def test_run_rejects_extra_arguments_without_calling_runner(self):
        fake = self.Runner({"state": "passed", "run_id": "abc"})
        session = server.Session(self.Child(), fake)
        result = session.call("bortus_secrets_run", {"profile": "x", "image": "y"})
        self.assertTrue(result["isError"])
        self.assertEqual(fake.profiles, [])

    def test_denied_state_uses_fixed_text(self):
        session = server.Session(self.Child(), self.Runner({"state": "not_authorized"}))
        result = session.call("bortus_secrets_run", {"profile": "local-smoke"})
        self.assertTrue(result["isError"])
        self.assertEqual(result["content"][0]["text"], server.MESSAGES["not_authorized"])

    def test_unreachable_runner_is_reported_as_runtime_unavailable(self):
        class Broken:
            def call(self, profile):
                raise OSError("no socket")
        session = server.Session(self.Child(), Broken())
        result = session.call("bortus_secrets_run", {"profile": "local-smoke"})
        self.assertEqual(result["content"][0]["text"], server.MESSAGES["runtime_unavailable"])

    # -- modern protocol (2026-07-28) and legacy coexistence -----------------

    META = {"io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": {}}

    def test_discover_advertises_modern_and_legacy_versions(self):
        session = self.session(with_runner=False)
        reply = server.respond(session, {"jsonrpc": "2.0", "id": "d1",
                                         "method": "server/discover",
                                         "params": {"_meta": self.META}})
        result = reply["result"]
        self.assertEqual(result["supportedVersions"][0], "2026-07-28")
        self.assertIn("2025-11-25", result["supportedVersions"])
        self.assertEqual(result["resultType"], "complete")
        self.assertEqual(result["_meta"][server.META_SERVER]["name"], "bortus")

    def test_modern_tools_list_needs_no_initialize(self):
        session = self.session(with_runner=False)
        reply = server.respond(session, {"jsonrpc": "2.0", "id": 2, "method": "tools/list",
                                         "params": {"_meta": self.META}})
        self.assertEqual(reply["result"]["resultType"], "complete")
        self.assertEqual(sorted(tool["name"] for tool in reply["result"]["tools"]),
                         ["events_list", "pods_list", "resources_list"])

    def test_unsupported_version_is_rejected_with_supported_list(self):
        session = self.session(with_runner=False)
        reply = server.respond(session, {"jsonrpc": "2.0", "id": 3, "method": "tools/list",
                                         "params": {"_meta": {
                                             **self.META,
                                             "io.modelcontextprotocol/protocolVersion": "1900-01-01"}}})
        self.assertEqual(reply["error"]["code"], -32022)
        self.assertIn("2026-07-28", reply["error"]["data"]["supported"])

    def test_missing_client_capabilities_is_invalid_params(self):
        session = self.session(with_runner=False)
        reply = server.respond(session, {"jsonrpc": "2.0", "id": 4, "method": "tools/list",
                                         "params": {"_meta": {
                                             "io.modelcontextprotocol/protocolVersion": "2026-07-28"}}})
        self.assertEqual(reply["error"]["code"], -32602)

    def test_legacy_initialize_still_answers_without_result_type(self):
        session = self.session(with_runner=False)
        reply = server.respond(session, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                         "params": {"protocolVersion": "2025-06-18",
                                                    "capabilities": {},
                                                    "clientInfo": {"name": "legacy", "version": "1"}}})
        self.assertEqual(reply["result"]["protocolVersion"], "2025-06-18")
        self.assertNotIn("resultType", reply["result"])
        self.assertTrue(session.legacy)
        follow = server.respond(session, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertNotIn("resultType", follow["result"])


class CredentialRefreshStreamTests(unittest.TestCase):
    """A token refresh must never consume the client's MCP request stream.

    Regression for 2026-11-19: launch.py ran the refresh helper with the
    client's stdin, the helper's ssh read it, and OpenCode's first
    server/discover vanished, so every pooled connection timed out and fell
    back to a per-directory one. Each case runs the real function in a child
    process whose stdin holds one pending request, with a stand-in helper that
    drains stdin the way ssh does; the request must still be readable after.
    """

    PENDING = '{"jsonrpc": "2.0", "id": 1, "method": "server/discover"}'

    def pending_after_refresh(self, body):
        """Run `body` against a stale kubeconfig; return the line read afterwards."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            helper = root / "helper.py"
            helper.write_text("import sys\nsys.stdin.read()\n")
            kubeconfig = root / "kubeconfig.json"
            kubeconfig.write_text("{}")
            stale = time.time() - 7 * 3600  # past both the 30-minute and 6-hour thresholds
            os.utime(kubeconfig, (stale, stale))
            script = "\n".join([
                "import sys",
                f"sys.path.insert(0, {str(HERE.parent)!r})",
                "from pathlib import Path",
                f"helper, kubeconfig = Path({str(helper)!r}), Path({str(kubeconfig)!r})",
                body,
                "print(sys.stdin.readline().strip())"])
            result = subprocess.run([sys.executable, "-B", "-c", script], input=self.PENDING + "\n",
                                    capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_launcher_refresh_leaves_the_first_request_unread(self):
        """launch.refresh_if_stale runs before exec, ahead of server/discover."""
        body = "import launch\nlaunch.REFRESH_HELPER = helper\nlaunch.refresh_if_stale(str(kubeconfig))"
        self.assertEqual(self.pending_after_refresh(body), self.PENDING)

    def test_runtime_renewal_leaves_queued_requests_unread(self):
        """InventoryChild.ensure_fresh renews mid-session, with later requests queued."""
        body = ("import server\nchild = object.__new__(server.InventoryChild)\n"
                "child._kubeconfig, child._refresh_helper = kubeconfig, helper\n"
                "child.ensure_fresh()")
        self.assertEqual(self.pending_after_refresh(body), self.PENDING)

    def test_refresh_helper_ssh_never_reads_stdin(self):
        """The helper itself also refuses stdin, in case a caller forgets."""
        spec = importlib.util.spec_from_file_location("refresh_kubeconfig",
                                                      HERE.parent / "refresh-kubeconfig.py")
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        self.assertIn("-n", helper.SSH)
        with mock.patch.object(helper.subprocess, "check_output", return_value="ok\n") as call:
            helper.read_operator("true")
        self.assertIs(call.call_args.kwargs.get("stdin"), subprocess.DEVNULL)


class InventoryStreamTests(unittest.TestCase):
    """A failed inventory call must not leave the child's stream out of step.

    Regression for 2026-11-19: an unpaged pods_list reply exceeded MAX_LINE,
    the proxy read only its first 64 KiB, and the next call read the rest as
    its own reply and failed. A timed-out call could likewise hand its late
    reply (same fixed id) to the next caller. The real request() runs here
    against a scripted stand-in for the pinned binary.
    """

    SCRIPT = "\n".join([
        "import json, sys, time",
        "for line in sys.stdin:",
        "    m = json.loads(line)",
        "    if m['method'] == 'big':",
        "        print(json.dumps({'jsonrpc': '2.0', 'id': m['id'], 'result': {'pad': 'x' * 70000}}), flush=True)",
        "    elif m['method'] == 'slow':",
        "        time.sleep(1.5)",
        "        print(json.dumps({'jsonrpc': '2.0', 'id': m['id'], 'result': {'late': True}}), flush=True)",
        "    else:",
        "        print(json.dumps({'jsonrpc': '2.0', 'id': m['id'], 'result': {'method': m['method']}}), flush=True)"])

    class Stand_in(server.InventoryChild):
        """InventoryChild whose child process is SCRIPT instead of the pinned binary."""

        def __init__(self, script):
            self._process = None
            self._script = script
            self.starts = 0
            # No credential to renew: ensure_fresh treats a missing kubeconfig as current.
            self._kubeconfig, self._refresh_helper = Path("/nonexistent/kubeconfig"), None
            self._start()

        def _start(self):
            """Count starts so a test can prove the child was replaced."""
            self.starts += 1
            self._process = subprocess.Popen([sys.executable, "-B", "-c", self._script],
                                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                             stderr=subprocess.DEVNULL)
            self._ready = False

    def setUp(self):
        self.child = self.Stand_in(self.SCRIPT)
        self.addCleanup(self.child.close)

    def test_oversized_reply_restarts_the_child_and_the_next_call_is_answered(self):
        """The tail of a too-large reply is never read as the next answer."""
        with self.assertRaises(server.ReplyTooLarge):
            self.child.request({"jsonrpc": "2.0", "id": 3, "method": "big"})
        self.assertEqual(self.child.starts, 2)
        reply = self.child.request({"jsonrpc": "2.0", "id": 3, "method": "next"})
        self.assertEqual(reply["result"], {"method": "next"})

    def test_late_reply_to_a_timed_out_call_is_never_returned_for_the_next_one(self):
        """Same fixed id, so only a restart keeps the late reply away from the next caller."""
        with self.assertRaises(server.StartupError):
            self.child.request({"jsonrpc": "2.0", "id": 3, "method": "slow"}, timeout=0.3)
        self.assertEqual(self.child.starts, 2)
        time.sleep(1.6)  # long enough for the old child's late reply to have been written
        reply = self.child.request({"jsonrpc": "2.0", "id": 3, "method": "next"})
        self.assertEqual(reply["result"], {"method": "next"})

    def test_session_turns_an_oversized_reply_into_guidance(self):
        """The caller learns to page or filter instead of seeing 'runtime unavailable'."""
        session = server.Session(self.child, None)
        self.child.mark_ready()
        with mock.patch.object(self.child, "request", side_effect=server.ReplyTooLarge("big")):
            result = session.call("pods_list", {})
        self.assertTrue(result["isError"])
        self.assertIn("limit", result["content"][0]["text"])
        self.assertIn("fieldSelector", result["content"][0]["text"])


class UnixHTTPServer(socketserver.ThreadingUnixStreamServer):
    """Tiny Docker-shaped HTTP endpoint on a Unix socket for client tests."""

    daemon_threads = True
    allow_reuse_address = True


class EngineClientTests(unittest.TestCase):
    """The Engine client must speak the documented paths and pin a version."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = str(Path(self.directory.name) / "docker.sock")
        calls = self.calls = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                calls.append(("GET", self.path))
                body = {"ApiVersion": "1.47"} if self.path == "/version" else (
                    [] if "containers/json" in self.path else {"Id": "cid"})
                self._reply(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                self.rfile.read(length)
                calls.append(("POST", self.path))
                self._reply({"Id": "cid"})

            def do_DELETE(self):
                calls.append(("DELETE", self.path))
                self._reply({})

            def _reply(self, body):
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = UnixHTTPServer(self.path, Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.directory.cleanup()

    def test_negotiate_create_start_remove(self):
        client = engine.Engine(self.path)
        client.negotiate()
        profile_doc = policy.load_profiles(profiles_document())["local-smoke"]
        identifier = client.create("run1", profile_doc, [("A", "b")],
                                   [("/staged/token", "token")])
        client.start(identifier)
        client.remove(identifier)
        self.assertEqual(self.calls[0], ("GET", "/version"))
        self.assertIn(("POST", "/v1.47/containers/create?name=bortus-run1"), self.calls)
        self.assertIn(("POST", "/v1.47/containers/cid/start"), self.calls)
        self.assertIn(("DELETE", "/v1.47/containers/cid?force=1&v=1"), self.calls)


class RealDockerTests(unittest.TestCase):
    """Deliver a synthetic marker through the real local Docker engine.

    Skipped unless a local Docker socket and the small ``alpine:3.20`` image
    are present. This proves the injection path itself: the container exits
    non-zero when either binding is missing, and the runner removes it.
    """

    SOCKET = "/var/run/docker.sock"

    def setUp(self):
        if not Path(self.SOCKET).exists():
            self.skipTest("no local Docker socket")
        try:
            probe = engine.Engine(self.SOCKET)
            probe.negotiate()
        except engine.EngineError:
            self.skipTest("local Docker engine unavailable")
        # Only containers created by this test are removed afterwards, so a
        # concurrent runner's container is never touched.
        self.before = set(probe.owned())
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.run_root = self.root / "runs"
        self.run_root.mkdir(mode=0o700)
        self.check = ("test -s /run/secrets/token && "
                      "test \"$EXAMPLE_TOKEN\" = \"$(cat /run/secrets/token)\" && "
                      "test \"$EXAMPLE_TOKEN\" = \"" + MARKER + "\" && exec sleep 8")
        image = self.local_digest()
        self.profiles = write_private(self.root / "profiles.json", profiles_document(profile(
            image_digest=image,
            probe={"kind": "running", "seconds": 2},
            network="none",
            command=["sh", "-c", self.check],
            bindings=[
                {"namespace": "testing", "secret": "example", "key": "api_token",
                 "delivery": "env", "destination": "EXAMPLE_TOKEN"},
                {"namespace": "testing", "secret": "example", "key": "api_token",
                 "delivery": "file", "destination": "token"},
            ])))
        self.grants = write_private(self.root / "grants.json", grants_document())
        objects = {("testing", "example"): json.loads(
            secret_object("testing", "example", {"api_token": MARKER.encode()}))}
        self.instance = runner.Runner(self.profiles, self.grants, None,
                                      engine.Engine(self.SOCKET), self.run_root,
                                      source=FakeSource(objects))

    def local_digest(self):
        """Return a local-only digest reference for the small test image."""
        import subprocess
        info = json.loads(subprocess.check_output(
            ["docker", "image", "inspect", "alpine:3.20"], text=True))[0]
        for reference in info.get("RepoDigests") or []:
            if reference.startswith("alpine@"):
                return reference
        return f"alpine@{info['Id']}"

    def tearDown(self):
        client = engine.Engine(self.SOCKET)
        for identifier in set(client.owned()) - self.before:
            client.remove(identifier)
        self.directory.cleanup()

    def test_delivery_reaches_container_and_nothing_is_left_behind(self):
        result = self.instance.handle(1000, {"profile": "local-smoke"})
        self.assertEqual(result["state"], "passed")
        self.assertEqual(engine.Engine(self.SOCKET).owned(), [])
        self.assertFalse(any(self.run_root.iterdir()))
        self.assertNotIn(MARKER, json.dumps(result))

    def test_missing_binding_fails_the_check_and_still_cleans(self):
        objects = {("testing", "example"): json.loads(
            secret_object("testing", "example", {"api_token": b"different"}))}
        failing = runner.Runner(self.profiles, self.grants, None,
                                engine.Engine(self.SOCKET), self.run_root,
                                source=FakeSource(objects))
        result = failing.handle(1000, {"profile": "local-smoke"})
        self.assertEqual(result["state"], "check_failed")
        self.assertEqual(engine.Engine(self.SOCKET).owned(), [])
        self.assertFalse(any(self.run_root.iterdir()))


if __name__ == "__main__":
    unittest.main()
