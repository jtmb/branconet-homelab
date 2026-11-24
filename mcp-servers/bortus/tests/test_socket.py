"""End-to-end check over the runner's real Unix socket.

The MCP layer and the runner talk over a Unix domain socket and the runner
identifies its peer with SO_PEERCRED. This test starts the real socket
server, sends requests the way ``server.RunnerClient`` does, and checks the
authorization result, the fixed error shapes and cleanup. It uses a
synthetic Secret source and a real local Docker container, so it proves the
wiring without a cluster or real credentials.
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import engine
import runner
import server

MARKER = "socket-marker-4c8a1e"
SOCKET = "/var/run/docker.sock"


class FakeSource:
    """Return the synthetic object regardless of the requested bindings."""

    def __init__(self, objects):
        self.objects = objects

    def fetch(self, bindings):
        return self.objects


class SocketTests(unittest.TestCase):
    """The socket path must authorize, run and answer in fixed terms."""

    def setUp(self):
        if not Path(SOCKET).exists():
            self.skipTest("no local Docker socket")
        # Only remove containers this test created, never a concurrent runner's.
        self.before = set(engine.Engine(SOCKET).owned())
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.run_root = self.root / "runs"
        self.run_root.mkdir(mode=0o700)
        self.socket_path = str(self.root / "runner.sock")
        self.profiles = self.write("profiles.json", json.dumps({"version": 1, "profiles": [{
            "id": "socket-smoke",
            "image_digest": self.local_digest(),
            "bindings": [{"namespace": "testing", "secret": "example", "key": "api_token",
                          "delivery": "env", "destination": "EXAMPLE_TOKEN"}],
            "probe": {"kind": "running", "seconds": 2},
            "network": "none",
            "timeout_seconds": 30,
            "command": ["sh", "-c", f'test "$EXAMPLE_TOKEN" = "{MARKER}" && exec sleep 10'],
        }]}))
        self.grants = self.write("grants.json", json.dumps({"version": 1, "grants": [
            {"uid": os.getuid(), "profile": "socket-smoke",
             "expires_at": time.time() + 600}]}))
        objects = {("testing", "example"): {
            "kind": "Secret",
            "data": {"api_token": __import__("base64").b64encode(MARKER.encode()).decode()}}}
        instance = runner.Runner(self.profiles, self.grants, None,
                                 engine.Engine(SOCKET), self.run_root,
                                 source=FakeSource(objects))
        threading.Thread(target=runner.serve, args=(instance, self.socket_path),
                         daemon=True).start()
        for _ in range(400):
            if Path(self.socket_path).exists():
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
                        probe.connect(self.socket_path)
                    break
                except OSError:
                    pass
            time.sleep(0.01)

    def tearDown(self):
        client = engine.Engine(SOCKET)
        for identifier in set(client.owned()) - self.before:
            client.remove(identifier)
        self.directory.cleanup()

    def write(self, name, text):
        path = self.root / name
        path.write_text(text)
        os.chmod(path, 0o600)
        return str(path)

    def local_digest(self):
        info = json.loads(subprocess.check_output(
            ["docker", "image", "inspect", "alpine:3.20"], text=True))[0]
        for reference in info.get("RepoDigests") or []:
            if reference.startswith("alpine@"):
                return reference
        return f"alpine@{info['Id']}"

    def raw(self, payload):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(60)
            client.connect(self.socket_path)
            client.sendall(payload)
            return json.loads(client.recv(4096))

    def test_authorized_call_passes_over_the_socket(self):
        reply = server.RunnerClient(self.socket_path).call("socket-smoke")
        self.assertEqual(reply["state"], "passed")
        self.assertNotIn(MARKER, json.dumps(reply))
        self.assertEqual(engine.Engine(SOCKET).owned(), [])
        self.assertFalse(any(self.run_root.iterdir()))

    def test_unknown_profile_and_bad_shape_never_authorize(self):
        self.assertEqual(server.RunnerClient(self.socket_path).call("other")["state"],
                         "not_authorized")
        self.assertEqual(self.raw(b'{"profile":"socket-smoke","image":"x"}\n')["state"],
                         "invalid_request")
        self.assertEqual(self.raw(b"not json\n")["state"], "invalid_request")
        self.assertEqual(engine.Engine(SOCKET).owned(), [])


if __name__ == "__main__":
    unittest.main()
