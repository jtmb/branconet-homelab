"""The shared BORTUS MCP server.

One stdio server for every managed repository. It forwards the three
existing read-only inventory tools to the already pinned Kubernetes
inventory child, and adds exactly one more tool: ``bortus_secrets_run``.
That tool does not return Secret values. It asks the operator-owned local
runner to deliver approved keys to one reviewed container and reports only
a fixed result.
"""

import hashlib
import json
import os
import select
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import kube
import policy

VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
MODERN_VERSION = "2026-07-28"
SUPPORTED_VERSIONS = [MODERN_VERSION, "2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]
META_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
META_CLIENT = "io.modelcontextprotocol/clientInfo"
META_SERVER = "io.modelcontextprotocol/serverInfo"
# A pooled connection can outlive the inventory token. Refresh the kubeconfig
# before it expires and restart the child so it reloads the credential.
RENEW_AFTER_SECONDS = 6 * 3600
REFRESH_HELPER = Path(__file__).resolve().parent / "refresh-kubeconfig.py"
INVENTORY_TOOLS = ("pods_list", "resources_list", "events_list")
MAX_LINE = 65536
CHILD_TIMEOUT = 30
RUN_TIMEOUT = 150
MAX_REPLY = 4096
SERVER_VERSION = "0.2.0"

# Fixed wording for each runner state. The agent never sees cluster text,
# container output or a policy description.
MESSAGES = {
    "invalid_request": "The run request was not valid.",
    "not_authorized": "This run is not authorized.",
    "busy": "The runner is busy; no values were fetched.",
    "credential_unavailable": "Approved configuration could not be loaded.",
    "runtime_unavailable": "The local container runtime is unavailable.",
    "check_failed": "The local check did not pass.",
    "timed_out": "The check did not complete.",
    "cleanup_required": "Runner needs cleanup before another run.",
}

RUN_TOOL = {
    "name": "bortus_secrets_run",
    "description": ("Run one operator-approved local Docker check with Kubernetes-backed "
                    "settings. Returns only a fixed result; values are never returned."),
    "inputSchema": {
        "type": "object",
        "properties": {"profile": {"type": "string",
                                   "pattern": "^[a-z][a-z0-9-]{0,63}$"}},
        "required": ["profile"],
        "additionalProperties": False,
    },
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
                    "openWorldHint": False},
}

GET_TOOL = {
    "name": "bortus_secret_get",
    "description": ("Read one Kubernetes Secret's values for local use, such as an "
                    "environment file or a docker run. Only namespaces and names "
                    "allowed by this machine's scope can be read."),
    "inputSchema": {
        "type": "object",
        "properties": {
            "namespace": {"type": "string"},
            "name": {"type": "string"},
            "keys": {"type": "array", "items": {"type": "string"}, "maxItems": 64},
        },
        "required": ["namespace", "name"],
        "additionalProperties": False,
    },
    "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
}

NAMES_TOOL = {
    "name": "bortus_secret_names",
    "description": "List the Secret names in one namespace that this machine may read.",
    "inputSchema": {
        "type": "object",
        "properties": {"namespace": {"type": "string"}},
        "required": ["namespace"],
        "additionalProperties": False,
    },
    "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
}

SCOPE_MESSAGES = {
    "denied": "That Secret is outside this machine's configured scope.",
    "not_found": "That Secret could not be read.",
    "forbidden": "This machine's Kubernetes identity may not read that Secret.",
    "unavailable": "The Kubernetes API is unavailable.",
    "malformed": "That Secret could not be decoded.",
    "invalid": "Give a namespace and name, and optionally a list of keys.",
}


class StartupError(Exception):
    """The local configuration or the pinned inventory child is unusable."""


class InventoryChild:
    """The pinned inventory server, run from a verified in-memory copy."""

    def __init__(self, binary, expected_sha256, kubeconfig, refresh_helper=REFRESH_HELPER):
        self._process = None
        self._kubeconfig = Path(kubeconfig)
        self._refresh_helper = Path(refresh_helper) if refresh_helper else None
        self._executable = self._open(binary, expected_sha256)
        self._start()

    def _start(self):
        """Start a child with the current kubeconfig contents."""
        config = self._config(self._kubeconfig)
        self._process = subprocess.Popen(
            [f"/proc/self/fd/{self._executable}", "--config",
             f"/proc/self/fd/{config}"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            pass_fds=(self._executable, config), close_fds=True,
            env={"HOME": str(Path.home()), "PATH": "/usr/bin:/bin"})
        os.close(config)
        self._ready = False

    @property
    def ready(self):
        """True once the child has completed its own initialize handshake."""
        return self._ready

    def mark_ready(self):
        """Record that the child handshake completed."""
        self._ready = True

    @property
    def pid(self):
        """Process id of the current child, or None."""
        return self._process.pid if self._process is not None else None

    def ensure_fresh(self):
        """Renew the short-lived inventory token before the child goes stale.

        The child loads the kubeconfig once at startup, so renewal means
        minting a new token with the existing helper and restarting the child.
        A failed refresh leaves the current child in place; the next call
        retries rather than breaking the connection.
        """
        try:
            age = time.time() - self._kubeconfig.stat().st_mtime
        except OSError:
            return
        if age < RENEW_AFTER_SECONDS:
            return
        if self._refresh_helper is not None and self._refresh_helper.is_file():
            try:
                subprocess.run([sys.executable, "-B", str(self._refresh_helper)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=25)
            except (OSError, subprocess.SubprocessError):
                return
            try:
                if time.time() - self._kubeconfig.stat().st_mtime < 60:
                    self.close()
                    self._start()
            except OSError:
                return

    @staticmethod
    def _open(binary, expected_sha256):
        """Hash the pinned executable, then run a sealed copy of those bytes."""
        descriptor = os.open(binary, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as source, os.fdopen(
                os.memfd_create("bortus-inventory", os.MFD_ALLOW_SEALING |
                                getattr(os, "MFD_EXEC", 0)), "w+b") as copy:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 256 * 1024 * 1024:
                raise StartupError("the pinned inventory binary is not a usable file")
            remaining = info.st_size
            while remaining:
                block = source.read(min(remaining, 1024 * 1024))
                if not block:
                    raise StartupError("the pinned inventory binary was truncated")
                copy.write(block)
                remaining -= len(block)
            if source.read(1):
                raise StartupError("the pinned inventory binary changed while read")
            copy.flush()
            import fcntl
            fcntl.fcntl(copy.fileno(), fcntl.F_ADD_SEALS,
                        fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW |
                        fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
            copy.seek(0)
            if hashlib.file_digest(copy, "sha256").hexdigest() != expected_sha256:
                raise StartupError("the inventory binary does not match its pin")
            os.fchmod(copy.fileno(), 0o500)
            return os.dup(copy.fileno())

    @staticmethod
    def _config(kubeconfig):
        """Create the read-only inventory configuration as an inherited fd."""
        config = os.memfd_create("bortus-inventory-config")
        with os.fdopen(os.dup(config), "w") as stream:
            stream.write("read_only = true\n"
                         'toolsets = ["core"]\n'
                         'enabled_tools = ["pods_list", "resources_list", "events_list"]\n'
                         'list_output = "table"\n'
                         f"kubeconfig = {json.dumps(str(kubeconfig))}\n")
        os.lseek(config, 0, os.SEEK_SET)
        return config

    def request(self, message, timeout=CHILD_TIMEOUT):
        """Send one MCP request and read exactly one reply line."""
        self._send(message)
        ready, _, _ = select.select([self._process.stdout], [], [], timeout)
        if not ready:
            raise StartupError("the inventory runtime did not reply in time")
        raw = self._process.stdout.readline(MAX_LINE + 1)
        if not raw or len(raw) > MAX_LINE:
            raise StartupError("the inventory runtime returned no usable reply")
        try:
            reply = json.loads(raw)
        except ValueError:
            raise StartupError("the inventory runtime returned an unreadable reply") from None
        if not isinstance(reply, dict):
            raise StartupError("the inventory runtime returned an unexpected reply")
        return reply

    def notify(self, message):
        """Send a notification; MCP notifications have no reply to read."""
        self._send(message)

    def _send(self, message):
        """Write one framed message to the child, failing if it is gone."""
        if self._process is None or self._process.poll() is not None:
            raise StartupError("the inventory runtime is not available")
        self._process.stdin.write((json.dumps(message) + "\n").encode())
        self._process.stdin.flush()

    def close(self):
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(5)
            except subprocess.TimeoutExpired:
                self._process.kill()


class RunnerClient:
    """Ask the operator-owned runner for one authorized local run."""

    def __init__(self, socket_path):
        self.path = socket_path

    def call(self, profile):
        request = json.dumps({"profile": profile}).encode() + b"\n"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(RUN_TIMEOUT)
            client.connect(self.path)
            client.sendall(request)
            data = b""
            while len(data) <= MAX_REPLY:
                chunk = client.recv(MAX_REPLY + 1 - len(data))
                if not chunk:
                    break
                data += chunk
        if not data or len(data) > MAX_REPLY:
            raise StartupError("the runner returned no usable result")
        reply = json.loads(data)
        if not isinstance(reply, dict) or not isinstance(reply.get("state"), str):
            raise StartupError("the runner returned an unexpected result")
        if reply["state"] != "passed" and reply["state"] not in MESSAGES:
            raise StartupError("the runner returned an unexpected result")
        return reply


class SecretAccess:
    """Serve Secret reads limited to this machine's configured scope."""

    def __init__(self, reader, scope):
        self.reader = reader
        self.scope = scope

    def allowed(self, namespace, name=None):
        """True when the scope names this namespace (and name if given)."""
        for entry in self.scope:
            if entry == "*":
                return True
            parts = entry.split("/", 1)
            if parts[0] != namespace:
                continue
            if len(parts) == 1:
                return True
            if name is not None and parts[1] == name:
                return True
        return False

    def get(self, arguments):
        """Return one Secret's requested values as text."""
        namespace, name = arguments.get("namespace"), arguments.get("name")
        keys = arguments.get("keys")
        if (not isinstance(namespace, str) or not isinstance(name, str)
                or not set(arguments) <= {"namespace", "name", "keys"}
                or not policy.RESOURCE_NAME.fullmatch(namespace)
                or not policy.RESOURCE_NAME.fullmatch(name)
                or (keys is not None and (not isinstance(keys, list) or not keys
                                          or len(keys) > 64
                                          or not all(isinstance(k, str) and
                                                     policy.SECRET_KEY.fullmatch(k) for k in keys)))):
            return self._error("invalid")
        if not self.allowed(namespace, name):
            return self._error("denied")
        try:
            data = self.reader.get(namespace, name)
        except kube.CredentialError as error:
            return self._error(str(error))
        selected = {k: data[k] for k in keys if k in data} if keys else data
        if keys and len(selected) != len(set(keys)):
            return self._error("not_found")
        payload, binary = {}, []
        for key, value in sorted(selected.items()):
            text, is_binary = kube.as_text(value)
            payload[key] = text
            if is_binary:
                binary.append(key)
        result = {"namespace": namespace, "name": name, "data": payload}
        if binary:
            result["base64_keys"] = binary
        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    def names(self, arguments):
        """Return the Secret names in one namespace."""
        namespace = arguments.get("namespace")
        if not isinstance(namespace, str) or not policy.RESOURCE_NAME.fullmatch(namespace):
            return self._error("invalid")
        if not self.allowed(namespace):
            return self._error("denied")
        try:
            names = self.reader.names(namespace)
        except kube.CredentialError as error:
            return self._error(str(error))
        return {"content": [{"type": "text",
                             "text": json.dumps({"namespace": namespace, "names": names})}]}

    @staticmethod
    def _error(reason):
        text = SCOPE_MESSAGES.get(reason, SCOPE_MESSAGES["unavailable"])
        return {"isError": True, "content": [{"type": "text", "text": text}]}


class Session:
    """One client session: inventory child plus the optional tools."""

    def __init__(self, child, runner, secrets=None):
        self.child = child
        self.runner = runner
        self.secrets = secrets
        self.legacy = False

    def _ensure_child(self, params=None):
        """Complete the child's legacy handshake once per child process.

        The pinned inventory server is a legacy MCP peer regardless of which
        era the OpenCode client uses, so the proxy always initializes it
        before forwarding a tool call. A restarted child repeats the handshake.
        """
        if self.child.ready:
            return
        reply = self.child.request({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                    "params": params or {
                                        "protocolVersion": "2025-06-18",
                                        "capabilities": {},
                                        "clientInfo": {"name": "bortus",
                                                       "version": SERVER_VERSION}}})
        if not isinstance(reply.get("result"), dict):
            raise StartupError("the inventory runtime refused initialization")
        self.child.notify({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.child.mark_ready()

    def initialize(self, params):
        self._ensure_child(params)
        version = params.get("protocolVersion")
        self.legacy = True
        return {"protocolVersion": version if isinstance(version, str) and version in VERSIONS
                else "2025-11-25",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "bortus", "version": SERVER_VERSION}}

    def tools(self):
        self.child.ensure_fresh()
        self._ensure_child()
        reply = self.child.request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = reply.get("result", {}).get("tools")
        if not isinstance(tools, list):
            raise StartupError("the inventory runtime did not list its tools")
        allowed = [tool for tool in tools
                   if isinstance(tool, dict) and tool.get("name") in INVENTORY_TOOLS]
        if {tool["name"] for tool in allowed} != set(INVENTORY_TOOLS):
            raise StartupError("the inventory runtime exposed an unexpected tool set")
        if self.secrets:
            allowed += [GET_TOOL, NAMES_TOOL]
        return allowed + ([RUN_TOOL] if self.runner else [])

    def call(self, name, arguments):
        if name in INVENTORY_TOOLS:
            self.child.ensure_fresh()
            self._ensure_child()
            reply = self.child.request({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                        "params": {"name": name, "arguments": arguments}})
            result = reply.get("result")
            if not isinstance(result, dict):
                raise StartupError("the inventory runtime refused the request")
            return result
        if name == "bortus_secret_get" and self.secrets:
            return self.secrets.get(arguments)
        if name == "bortus_secret_names" and self.secrets:
            return self.secrets.names(arguments)
        if name == "bortus_secrets_run" and self.runner:
            return self._run(arguments)
        raise StartupError("the requested tool is not available")

    def _run(self, arguments):
        """Validate the single argument, then report the runner's fixed state."""
        profile = arguments.get("profile") if isinstance(arguments, dict) else None
        if (not isinstance(arguments, dict) or set(arguments) != {"profile"}
                or not isinstance(profile, str) or not profile):
            return {"isError": True, "content": [{"type": "text",
                                                  "text": MESSAGES["invalid_request"]}]}
        try:
            reply = self.runner.call(profile)
        except (OSError, ValueError, StartupError):
            return {"isError": True, "content": [{"type": "text",
                                                  "text": MESSAGES["runtime_unavailable"]}]}
        state = reply["state"]
        if state == "passed":
            return {"content": [{"type": "text", "text": json.dumps(
                {"state": "passed", "run_id": reply.get("run_id")})}]}
        text = MESSAGES.get(state, MESSAGES["runtime_unavailable"])
        return {"isError": True, "content": [{"type": "text", "text": text}]}


def _meta_of(params):
    """Return the request's _meta mapping, or None when absent or invalid."""
    meta = params.get("_meta") if isinstance(params, dict) else None
    return meta if isinstance(meta, dict) else None


def _discover_result():
    """Modern discovery result: versions, capabilities and identity."""
    return {
        "resultType": "complete",
        "supportedVersions": SUPPORTED_VERSIONS,
        "capabilities": {"tools": {}},
        "_meta": {META_SERVER: {"name": "bortus", "version": SERVER_VERSION}},
        "instructions": ("Kubernetes inventory for the homelab cluster, scoped Secret reads, "
                         "and an optional guarded local run. Secret values are returned only "
                         "for namespaces inside this machine's configured scope."),
        "ttlMs": 3600000,
        "cacheScope": "public",
    }


def _modern(result, cache=False):
    """Mark a result as a complete modern result with server identity.

    List results also carry the caching fields the modern schema requires
    (``ttlMs`` and ``cacheScope``); call results must not, because their
    schema is closed.
    """
    decorated = {"resultType": "complete", **result}
    meta = decorated.get("_meta")
    meta = dict(meta) if isinstance(meta, dict) else {}
    meta[META_SERVER] = {"name": "bortus", "version": SERVER_VERSION}
    decorated["_meta"] = meta
    if cache:
        decorated.setdefault("ttlMs", 3600000)
        decorated.setdefault("cacheScope", "public")
    return decorated


def respond(session, message):
    """Answer one JSON-RPC message, or return None for a notification.

    A request that carries modern per-request metadata is served statelessly
    under revision 2026-07-28. A request that opens with ``initialize`` selects
    legacy semantics for this process, so existing clients keep working.
    """
    envelope = {"jsonrpc": "2.0", "id": message.get("id")}
    if message.get("jsonrpc") != "2.0":
        return {**envelope, "error": {"code": -32600, "message": "Invalid request"}}
    if "id" not in message:
        return None
    method = message.get("method")
    params = message.get("params", {})
    if not isinstance(params, dict):
        return {**envelope, "error": {"code": -32602, "message": "Invalid parameters"}}
    meta = _meta_of(params)
    modern = meta is not None and isinstance(meta.get(META_VERSION), str)
    if modern:
        version = meta[META_VERSION]
        if version not in SUPPORTED_VERSIONS:
            return {**envelope, "error": {
                "code": -32022, "message": "Unsupported protocol version",
                "data": {"supported": SUPPORTED_VERSIONS, "requested": version}}}
        if META_CAPABILITIES not in meta or not isinstance(meta[META_CAPABILITIES], dict):
            return {**envelope, "error": {
                "code": -32602,
                "message": "Missing io.modelcontextprotocol/clientCapabilities"}}
    elif method not in ("initialize", "ping") and not session.legacy:
        # Neither era is established: a modern request must declare its version.
        return {**envelope, "error": {"code": -32602, "message": "Missing protocol version"}}
    list_result = False
    try:
        if method == "server/discover":
            result = _discover_result()
            return {**envelope, "result": result}
        if method == "initialize":
            if modern:
                return {**envelope, "error": {
                    "code": -32601, "message": "Method not found",
                    "data": {"supported": SUPPORTED_VERSIONS,
                             "hint": "modern clients do not initialize"}}}
            version = params.get("protocolVersion")
            result = session.initialize({**params, "protocolVersion":
                                         version if isinstance(version, str) and version in VERSIONS
                                         else "2025-11-25"})
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": session.tools()}
            list_result = True
        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            if not isinstance(name, str) or not isinstance(arguments, dict):
                return {**envelope, "error": {"code": -32602, "message": "Invalid parameters"}}
            result = session.call(name, arguments)
        else:
            return {**envelope, "error": {"code": -32601, "message": "Method not found"}}
    except StartupError as exc:
        print(f"BORTUS MCP runtime error: {exc}", file=sys.stderr, flush=True)
        return {**envelope, "error": {"code": -32603,
                                      "message": "The local runtime is unavailable."}}
    return {**envelope, "result": _modern(result, cache=list_result) if modern else result}


def main():
    """Run the stdio loop until the client closes the stream."""
    settings = {name: os.environ.get(name) for name in
                ("BORTUS_INVENTORY_BINARY", "BORTUS_INVENTORY_SHA256",
                 "BORTUS_INVENTORY_KUBECONFIG", "BORTUS_RUNNER_SOCKET",
                 "BORTUS_SECRETS_KUBECONFIG", "BORTUS_SECRET_SCOPE")}
    if not all(settings[name] for name in
               ("BORTUS_INVENTORY_BINARY", "BORTUS_INVENTORY_SHA256",
                "BORTUS_INVENTORY_KUBECONFIG")):
        raise SystemExit("BORTUS needs its pinned inventory settings.")
    child = InventoryChild(settings["BORTUS_INVENTORY_BINARY"],
                           settings["BORTUS_INVENTORY_SHA256"],
                           settings["BORTUS_INVENTORY_KUBECONFIG"])
    runner = RunnerClient(settings["BORTUS_RUNNER_SOCKET"]) if settings["BORTUS_RUNNER_SOCKET"] else None
    secrets = None
    if settings["BORTUS_SECRETS_KUBECONFIG"] and settings["BORTUS_SECRET_SCOPE"]:
        scope = [entry.strip() for entry in settings["BORTUS_SECRET_SCOPE"].split(",")
                 if entry.strip()]
        secrets = SecretAccess(
            kube.SecretReader(kube.KubeconfigTransport(settings["BORTUS_SECRETS_KUBECONFIG"])),
            scope)
    session = Session(child, runner, secrets)
    try:
        while raw := sys.stdin.buffer.readline(MAX_LINE + 1):
            if len(raw) > MAX_LINE:
                raise SystemExit("BORTUS MCP request exceeded the size limit.")
            try:
                message = json.loads(raw)
                reply = respond(session, message if isinstance(message, dict) else {})
            except (ValueError, RecursionError):
                reply = {"jsonrpc": "2.0", "id": None,
                         "error": {"code": -32700, "message": "Parse error"}}
            if reply is not None:
                print(json.dumps(reply), flush=True)
    finally:
        child.close()


if __name__ == "__main__":
    try:
        main()
    except StartupError as error:
        raise SystemExit(f"BORTUS MCP refused to start: {error}") from None
    except (OSError, KeyError, ValueError):
        raise SystemExit("BORTUS MCP refused its local configuration.") from None
