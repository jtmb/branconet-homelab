"""Minimal Docker Engine API client for the private runner's socket.

Only the calls the runner needs exist: negotiate, create, start, inspect,
list by ownership label and remove. The client talks to one Unix socket
explicitly so an agent-controlled ``DOCKER_HOST`` cannot redirect it, and it
never sends caller-supplied options.
"""

import http.client
import json
import socket

# Fixed run limits from the contract. They are deliberately not profile
# options: a profile chooses what runs, not how much of the host it may take.
MEMORY_BYTES = 512 * 1024 * 1024
NANO_CPUS = 1_000_000_000
PIDS_LIMIT = 64
TIMEOUT = 30


class EngineError(Exception):
    """The private container engine refused or misbehaved."""


class _UnixConnection(http.client.HTTPConnection):
    """HTTP over one Unix domain socket."""

    def __init__(self, socket_path, timeout=TIMEOUT):
        super().__init__("localhost", timeout=timeout)
        self._socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self._socket_path)


class Engine:
    """Bounded client for the runner-owned Docker Engine socket."""

    def __init__(self, socket_path):
        self._socket_path = socket_path
        self._version = None

    def request(self, method, path, body=None):
        """Perform one request and return the decoded JSON reply."""
        connection = _UnixConnection(self._socket_path)
        headers = {"Host": "docker"}
        payload = None
        if body is not None:
            payload = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        try:
            connection.request(method, path, body=payload, headers=headers)
            response = connection.getresponse()
            data = response.read(1024 * 1024 + 1)
        except OSError:
            raise EngineError("unavailable") from None
        finally:
            connection.close()
        if len(data) > 1024 * 1024:
            raise EngineError("unavailable")
        if response.status >= 400:
            # The body may echo request details; never surface it.
            raise EngineError("refused")
        try:
            return json.loads(data) if data.strip() else {}
        except (ValueError, RecursionError):
            raise EngineError("unavailable") from None

    def negotiate(self):
        """Pin one API version once, as Docker requires for non-ping calls."""
        reply = self.request("GET", "/version")
        version = reply.get("ApiVersion")
        if not isinstance(version, str) or not version.startswith("1."):
            raise EngineError("unavailable")
        self._version = f"/v{version}"

    def _prefix(self):
        if self._version is None:
            self.negotiate()
        return self._version

    def ping(self):
        """Cheap liveness check used at startup and before admission opens."""
        self.request("GET", "/_ping" if self._version is None else f"{self._version}/_ping")

    def create(self, run_id, profile, env, mounts):
        """Create one labelled container from the approved profile only."""
        host = {
            "NetworkMode": profile["network"],
            "Memory": MEMORY_BYTES,
            "NanoCpus": NANO_CPUS,
            "PidsLimit": PIDS_LIMIT,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"],
            "AutoRemove": False,
        }
        if mounts:
            host["Binds"] = [f"{source}:/run/secrets/{target}:ro" for source, target in mounts]
        config = {
            "Image": profile["image_digest"],
            "Env": [f"{name}={value}" for name, value in env],
            "Labels": {"bortus-runner": "bortus", "bortus-run": run_id},
            "HostConfig": host,
            "AttachStdout": False,
            "AttachStderr": False,
            "Tty": False,
            "OpenStdin": False,
        }
        if profile.get("command"):
            config["Cmd"] = list(profile["command"])
        reply = self.request("POST", f"{self._prefix()}/containers/create?name=bortus-{run_id}",
                             config)
        identifier = reply.get("Id")
        if not isinstance(identifier, str) or not identifier:
            raise EngineError("unavailable")
        return identifier

    def start(self, identifier):
        self.request("POST", f"{self._prefix()}/containers/{identifier}/start")

    def inspect(self, identifier):
        """Return (running, exit_code, started) for one container."""
        reply = self.request("GET", f"{self._prefix()}/containers/{identifier}/json")
        state = reply.get("State")
        if not isinstance(state, dict):
            raise EngineError("unavailable")
        return (state.get("Running") is True, state.get("ExitCode"),
                state.get("StartedAt") not in (None, ""))

    def address(self, identifier):
        """Return the container's bridge address, or None when it has none."""
        reply = self.request("GET", f"{self._prefix()}/containers/{identifier}/json")
        settings = reply.get("NetworkSettings")
        if not isinstance(settings, dict):
            return None
        candidates = [settings.get("IPAddress")]
        networks = settings.get("Networks")
        if isinstance(networks, dict):
            candidates.extend(value.get("IPAddress") for value in networks.values()
                              if isinstance(value, dict))
        for address in candidates:
            if isinstance(address, str) and address:
                return address
        return None

    def remove(self, identifier):
        """Force-remove one container; ignoring an absent one is the caller's job."""
        self.request("DELETE", f"{self._prefix()}/containers/{identifier}?force=1&v=1")

    def owned(self):
        """List container ids labelled as owned by this runner."""
        query = '{"label":["bortus-runner=bortus"]}'
        reply = self.request("GET", f"{self._prefix()}/containers/json?all=1&filters={query}")
        if not isinstance(reply, list):
            raise EngineError("unavailable")
        return [row["Id"] for row in reply
                if isinstance(row, dict) and isinstance(row.get("Id"), str)]
