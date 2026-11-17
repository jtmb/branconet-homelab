#!/usr/bin/env python3
"""Run metadata-only scans locally on H or from a fixed managed host installation.

No scheduler is installed by this command. Use a scoped KUBECONFIG supplied by
the operator. This runner never approves CSRs, renews certificates or reads
Secrets. --loop --control-plane retains the exclusive lock and publishes policy
heartbeats; always-on placement/service qualification is still required.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import sqlite3
import threading

from certificate_monitor import CertificateMonitor, RESOURCES
from certificate_monitor_control import control_cycle, POLICY_NAME, OBSERVATIONS_NAME, NAMESPACE
from certificate_monitor_process import run_bounded
from certificate_monitor_runtime import runtime_paths, private_state_file
from certificate_monitor_tls_probe import probe_tls_expiry

# Fixed cluster node IPs (k8s-rewrite/ansible-playbook/inventory/production.ini).
# A live TLS handshake only; no host file access, no credentials, no change to
# the monitor's existing UID998/no-capabilities privilege boundary.
NODE_TLS_ENDPOINTS = tuple(
    (node + ":" + kind, (ip, port))
    for node, ip in (("node01", "192.168.0.4"), ("node02", "192.168.0.6"), ("node03", "192.168.0.5"))
    for kind, port in (("apiserver", 6443), ("kubelet", 10250))
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", required=True, type=Path)
    execution = parser.add_mutually_exclusive_group(required=True)
    execution.add_argument("--once", action="store_true")
    execution.add_argument("--loop", action="store_true", help="Publish a heartbeat every 60 seconds; install no service")
    parser.add_argument("--control-plane", action="store_true", help="Consume fixed policy and publish durable observations")
    parser.add_argument("--managed-host", action="store_true", help="Only for the fixed root-managed unprivileged installation")
    parser.add_argument("--kubectl", type=Path, help="Local qualification only: explicitly supplied executable on H")
    args = parser.parse_args()
    if not os.environ.get("KUBECONFIG"):
        parser.error("Supply a scoped KUBECONFIG; no ambient administrator fallback is used")
    if args.loop and not args.control_plane:
        parser.error("--loop requires --control-plane so pause/interval policy remains authoritative")
    try:
        directory, kubectl = runtime_paths(managed_host=args.managed_host, script=Path(__file__),
                                          state_dir=args.state_dir, kubectl=args.kubectl, environ=os.environ)
    except (OSError, ValueError):
        parser.error("Runtime/credential paths do not match the selected deployment profile")
    os.umask(0o077)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o077:
        parser.error("state-dir must be private and owned by the runner")
    for name in ("monitor.lock", "monitor.sqlite", "monitor.sqlite-journal", "monitor.sqlite-wal", "monitor.sqlite-shm"):
        private_state_file(directory / name)
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())

    def read(resource):
        if resource not in RESOURCES:
            raise ValueError("resource_not_allowed")
        command = [str(kubectl), "--request-timeout=20s", "get", resource]
        if resource == RESOURCES[0]:
            command.append("-A")
        return json.loads(run_bounded(command + ["-o", "json"], output_limit=2 * 1024 * 1024))

    def get_map(name):
        if name not in (POLICY_NAME, OBSERVATIONS_NAME):
            raise ValueError("control_target_not_allowed")
        return json.loads(run_bounded(
            [str(kubectl), "--request-timeout=20s", "get", "configmap", name, "-n", NAMESPACE, "-o", "json"],
            output_limit=768 * 1024))

    def patch_map(name, patch):
        if name != OBSERVATIONS_NAME:
            raise ValueError("control_mutation_not_allowed")
        run_bounded([str(kubectl), "--request-timeout=20s", "patch", "configmap", name, "-n", NAMESPACE,
                     "--type=json", "--patch-file=/dev/stdin"], data=json.dumps(patch).encode(),
                    output_limit=16384)

    lock_fd = os.open(directory / "monitor.lock", os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, "a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"state": "already-running", "heartbeatPublished": False}), flush=True)
            return 1
        with sqlite3.connect(directory / "monitor.sqlite") as connection:
            monitor = CertificateMonitor(connection)
            while not stopping.is_set():
                try:
                    if args.control_plane:
                        outcome = control_cycle(monitor, read, get_map, patch_map,
                                               probe=probe_tls_expiry, endpoints=NODE_TLS_ENDPOINTS)
                        print(json.dumps(outcome), flush=True)
                        failed = outcome["mode"] == "monitor" and outcome["runState"] != "complete"
                    else:
                        outcome = monitor.scan(read)
                        print(json.dumps({"outcome": outcome, "snapshot": monitor.snapshot()}), flush=True)
                        failed = outcome["state"] != "complete"
                except Exception:
                    # Do not leak subprocess stderr/request payloads, or manufacture a heartbeat on failure.
                    print(json.dumps({"state": "control-unavailable", "heartbeatPublished": False}), flush=True)
                    failed = True
                if args.once:
                    return 1 if failed else 0
                stopping.wait(60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
