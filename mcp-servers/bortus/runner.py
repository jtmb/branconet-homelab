"""Privileged local runner: authorize, fetch, deliver, check, clean up.

This process is the trust boundary. It is started by the operator under a
Unix identity the agent session must not be able to become, it owns the
Docker socket and the Kubernetes credential, and it answers a narrow
newline-delimited request on its own Unix socket. The only thing it returns
is a fixed result code and an opaque run id.
"""

import json
import os
import socket
import struct
import sys
import threading
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import kube
import policy

MAX_REQUEST_BYTES = 512
RESPONSE_LIMIT = 4096
PROBE_INTERVAL = 0.05


class CleanupRequired(Exception):
    """A previous run's resources could not be verified removed."""


class Busy(Exception):
    """Another run holds the runner."""


class Deadline(Exception):
    """The run exceeded its approved time budget."""


def _fixed(reason):
    return {"state": reason, "run_id": None}


class Runner:
    """Serialized, bounded execution of one approved profile at a time."""

    def __init__(self, profiles_path, grants_path, kubeconfig_path, engine, run_root,
                 socket_path=None, audit_path=None, clock=time.monotonic, source=None):
        self.profiles_path = str(profiles_path)
        self.grants_path = str(grants_path)
        # A source is injectable so tests can prove the delivery path with
        # synthetic values and a real container runtime.
        self.source = source or kube.SecretSource(kube.KubeconfigTransport(kubeconfig_path))
        self.engine = engine
        self.run_root = Path(run_root)
        self.socket_path = socket_path
        self.audit_path = audit_path
        self.clock = clock
        self.lock = threading.Lock()
        self.active = None
        self.closed = False

    # -- policy ---------------------------------------------------------
    def load(self):
        profiles = policy.load_profiles(policy.read_private(self.profiles_path,
                                                            policy.MAX_POLICY_BYTES))
        grants = policy.load_grants(policy.read_private(self.grants_path,
                                                       policy.MAX_POLICY_BYTES))
        return profiles, grants

    def audit(self, uid, profile, state, started):
        """Append a value-free audit line; never fail a run because of it."""
        if not self.audit_path:
            return
        record = json.dumps({"ts": round(time.time(), 3), "uid": uid,
                             "profile": profile, "state": state,
                             "elapsed_ms": int((self.clock() - started) * 1000)})
        try:
            descriptor = os.open(self.audit_path,
                                 os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, "a") as log:
                log.write(record + "\n")
        except OSError:
            pass

    # -- admission and recovery ----------------------------------------
    def recover(self):
        """Remove containers this runner owned before a crash, then open.

        Only containers carrying this runner's ownership label are touched;
        anything else in the engine belongs to another owner. Staged values
        live in the runner's private root, so leftovers there are cleared too.
        """
        try:
            for identifier in self.engine.owned():
                if not self._remove(identifier):
                    raise CleanupRequired()
            if self.run_root.exists():
                for staging in self.run_root.iterdir():
                    if staging.is_dir() and not staging.is_symlink():
                        for child in staging.iterdir():
                            child.unlink()
                        staging.rmdir()
        except CleanupRequired:
            self.closed = True
            raise
        except Exception:
            self.closed = True
            raise CleanupRequired() from None
        self.closed = False

    def _reserve(self):
        if self.closed:
            raise CleanupRequired()
        if not self.lock.acquire(blocking=False):
            raise Busy()
        try:
            if self.active is not None:
                raise Busy()
            self.active = uuid.uuid4().hex[:16]
            return self.active
        except Exception:
            self.lock.release()
            raise

    def _release(self):
        self.active = None
        self.lock.release()

    # -- one run --------------------------------------------------------
    def handle(self, peer_uid, request):
        """Execute one request from a peer and return the safe result."""
        started = self.clock()
        profile_id = request.get("profile") if isinstance(request, dict) else None
        if (not isinstance(request, dict) or set(request) != {"profile"}
                or not isinstance(profile_id, str)
                or not policy.PROFILE_ID.fullmatch(profile_id)):
            return _fixed("invalid_request")
        try:
            profiles, grants = self.load()
        except (policy.PolicyError, OSError):
            return _fixed("not_authorized")
        profile, reason = policy.authorize(profiles, grants, peer_uid, profile_id)
        if reason:
            return _fixed(reason)
        try:
            run_id = self._reserve()
        except Busy:
            return _fixed("busy")
        except CleanupRequired:
            return _fixed("cleanup_required")
        try:
            result = self._execute(profile, peer_uid, run_id, started)
        finally:
            self._release()
        self.audit(peer_uid, profile_id, result["state"], started)
        return result

    def _execute(self, profile, peer_uid, run_id, started):
        """Run one profile and always attempt cleanup before answering."""
        deadline = started + profile["timeout_seconds"]
        staging = self.run_root / run_id
        container = None
        state = "runtime_unavailable"
        try:
            objects = self.source.fetch(profile["bindings"])
            deliveries = kube.materialize(profile["bindings"], objects)
            # Values are no longer needed once copied into the staging area
            # and environment list; drop the parsed objects promptly.
            del objects
            env, mounts = self._stage(run_id, deliveries)
            del deliveries
            # Revocation barrier: a grant withdrawn while the values were
            # being fetched must prevent the container from starting.
            profiles, grants = self.load()
            _, reason = policy.authorize(profiles, grants, peer_uid, profile["id"])
            self._check_deadline(deadline)
            if reason:
                state = reason
            else:
                container = self.engine.create(run_id, profile, env, mounts)
                del env
                self.engine.start(container)
                state = self._probe(container, profile, deadline)
        except kube.CredentialError:
            state = "credential_unavailable"
        except Deadline:
            state = "timed_out"
        except (kube.KubeconfigError, CleanupRequired):
            state = "runtime_unavailable"
        except OSError:
            state = "runtime_unavailable"
        except Exception:
            state = "runtime_unavailable"
        finally:
            cleaned = self._clean(container, staging)
        if not cleaned:
            self.closed = True
            return _fixed("cleanup_required")
        return {"state": state, "run_id": run_id} if state == "passed" else _fixed(state)

    def _stage(self, run_id, deliveries):
        """Write file deliveries into a private directory and build env pairs."""
        env, mounts = [], []
        files = [item for item in deliveries if item.kind == "file"]
        if files:
            (self.run_root / run_id).mkdir(mode=0o700, parents=True, exist_ok=False)
        for item in deliveries:
            if item.kind == "env":
                env.append((item.destination, item.data.decode("utf-8")))
                continue
            path = self.run_root / run_id / item.destination
            # The value must be readable by the container's own user. The
            # container drops all capabilities, including CAP_DAC_OVERRIDE,
            # so a 0400 file owned by the runner is not readable inside it.
            # Host-side protection comes from the 0700 directory, which is
            # the only path bound into the container.
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(item.data)
            mounts.append((str(path), item.destination))
        return env, mounts

    def _check_deadline(self, deadline):
        if self.clock() >= deadline:
            raise Deadline()

    def _probe(self, container, profile, deadline):
        """Run the approved check until it passes or the budget expires."""
        probe = profile["probe"]
        if probe["kind"] == "running":
            until = min(deadline, self.clock() + probe["seconds"])
            while self.clock() < until:
                running, exit_code, started = self.engine.inspect(container)
                if exit_code not in (None, 0) or (started and not running):
                    return "check_failed"
                time.sleep(PROBE_INTERVAL)
            running, _, _ = self.engine.inspect(container)
            return "passed" if running else "check_failed"
        while True:
            self._check_deadline(deadline)
            running, exit_code, started = self.engine.inspect(container)
            if exit_code not in (None, 0) or (started and not running):
                return "check_failed"
            if running and self._ready(container, probe):
                return "passed"
            time.sleep(PROBE_INTERVAL)

    def _ready(self, container, probe):
        """Attempt one readiness probe against the container's private address."""
        address = self.engine.address(container)
        if not address:
            return False
        try:
            with socket.create_connection((address, probe["port"]), timeout=0.5) as stream:
                if probe["kind"] == "tcp":
                    return True
                request = (f"GET {probe['path']} HTTP/1.1\r\nHost: {address}\r\n"
                           "Connection: close\r\n\r\n").encode("ascii")
                stream.sendall(request)
                head = stream.recv(64)
            return head.startswith(b"HTTP/1.") and int(head.split(b" ", 2)[1]) in probe["status"]
        except (OSError, ValueError, IndexError):
            return False

    def _remove(self, container):
        """Force-remove one container, retrying a transient engine conflict."""
        for attempt in range(3):
            try:
                self.engine.remove(container)
                return True
            except Exception:
                time.sleep(0.3 * (attempt + 1))
        return False

    def _clean(self, container, staging):
        """Remove the owned container and staged values; report success."""
        removed = True if container is None else self._remove(container)
        cleared = True
        if staging.exists():
            for child in staging.iterdir():
                try:
                    child.unlink()
                except OSError:
                    cleared = False
            if cleared:
                try:
                    staging.rmdir()
                except OSError:
                    cleared = False
        return removed and cleared


def peer_uid(connection):
    """Return the connected peer's uid using the kernel's credential check."""
    raw = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    _, uid, _ = struct.unpack("3i", raw)
    return uid


def serve(runner, socket_path):
    """Accept requests on the runner socket until the process is stopped."""
    path = Path(socket_path)
    if path.exists() or path.is_symlink():
        raise SystemExit("The runner socket path already exists; remove a stale socket first.")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    os.chmod(path, 0o666)
    server.listen(8)

    def handle_connection(connection):
        try:
            connection.settimeout(5)
            data = connection.recv(MAX_REQUEST_BYTES + 1)
            if len(data) > MAX_REQUEST_BYTES:
                reply = _fixed("invalid_request")
            else:
                try:
                    request = json.loads(data.split(b"\n", 1)[0])
                except (ValueError, RecursionError):
                    reply = _fixed("invalid_request")
                else:
                    reply = runner.handle(peer_uid(connection),
                                          request if isinstance(request, dict) else {})
            connection.sendall(json.dumps(reply).encode()[:RESPONSE_LIMIT])
        except (OSError, ValueError):
            pass
        finally:
            connection.close()

    while True:
        connection, _ = server.accept()
        threading.Thread(target=handle_connection, args=(connection,), daemon=True).start()


def main():
    """Start the operator-owned runner from explicit environment settings."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import engine

    settings = {name: os.environ.get(name) for name in
                ("BORTUS_PROFILES", "BORTUS_GRANTS", "BORTUS_KUBECONFIG",
                 "BORTUS_RUNNER_SOCKET", "BORTUS_RUN_ROOT", "BORTUS_DOCKER_SOCKET",
                 "BORTUS_AUDIT_LOG")}
    if not all(settings[name] for name in
               ("BORTUS_PROFILES", "BORTUS_GRANTS", "BORTUS_KUBECONFIG",
                "BORTUS_RUNNER_SOCKET", "BORTUS_RUN_ROOT", "BORTUS_DOCKER_SOCKET")):
        raise SystemExit("BORTUS runner needs its profiles, grants, kubeconfig, "
                         "socket, run root and Docker socket settings.")
    runner = Runner(settings["BORTUS_PROFILES"], settings["BORTUS_GRANTS"],
                    settings["BORTUS_KUBECONFIG"],
                    engine.Engine(settings["BORTUS_DOCKER_SOCKET"]),
                    settings["BORTUS_RUN_ROOT"], settings["BORTUS_RUNNER_SOCKET"],
                    settings["BORTUS_AUDIT_LOG"])
    try:
        runner.recover()
    except Exception:
        raise SystemExit("BORTUS runner refused to start: cleanup of its own "
                         "previous containers could not be verified.") from None
    serve(runner, settings["BORTUS_RUNNER_SOCKET"])


if __name__ == "__main__":
    main()
