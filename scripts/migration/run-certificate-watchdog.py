#!/usr/bin/env python3
"""Read-only off-host detector; explicit arming required, installs nothing."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
import threading

from certificate_watchdog import WatchdogState
from certificate_monitor_process import run_bounded
from certificate_monitor_runtime import H_ROOT, root_managed_file, private_state_file

CODE = Path("/usr/local/libexec/bortus-certificate-watchdog")
STATE = Path("/var/lib/bortus-certificate-watchdog")
CONFIG = Path("/etc/bortus-certificate-watchdog/enrollment.json")
KUBECONFIG = Path("/etc/bortus-certificate-watchdog/kubeconfig.json")
CA = Path("/etc/bortus-certificate-watchdog/cluster-ca.crt")
TOKEN = Path("/run/bortus-certificate-watchdog/token")


def profile(args):
    if args.managed_host:
        if (os.geteuid() == 0 or os.uname().nodename != "node03" or
                Path(__file__).absolute() != CODE / Path(__file__).name or
                args.state_dir != STATE or args.config != CONFIG or args.kubectl is not None):
            raise ValueError("watchdog_managed_profile_required")
        for name in (Path(__file__).name, "certificate_watchdog.py", "certificate_monitor.py",
                     "certificate_monitor_process.py", "certificate_monitor_runtime.py"):
            root_managed_file(CODE / name)
        root_managed_file(CONFIG)
        root_managed_file(KUBECONFIG)
        root_managed_file(CA)
        info = root_managed_file(TOKEN)
        if not 0 < info.st_size <= 16384 or info.st_mode & 0o007:
            raise ValueError("watchdog_private_credential_required")
        expected = {"apiVersion": "v1", "kind": "Config",
                    "clusters": [{"name": "branconet", "cluster": {
                        "server": "https://192.168.0.251:6443", "certificate-authority": str(CA)}}],
                    "users": [{"name": "bortus-certificate-watchdog", "user": {"tokenFile": str(TOKEN)}}],
                    "contexts": [{"name": "watchdog", "context": {
                        "cluster": "branconet", "user": "bortus-certificate-watchdog", "namespace": "bortus"}}],
                    "current-context": "watchdog"}
        if KUBECONFIG.stat().st_size > 16384 or json.loads(KUBECONFIG.read_text()) != expected:
            raise ValueError("watchdog_fixed_kubeconfig_required")
        cli, credential = Path("/usr/local/bin/kubectl"), KUBECONFIG
        root_managed_file(cli)
    else:
        credential = Path(os.environ.get("KUBECONFIG", ""))
        cli = args.kubectl
        if cli is None or not os.access(cli, os.X_OK):
            raise ValueError("watchdog_local_fixture_cli_required")
        if any(H_ROOT.resolve() not in p.resolve().parents for p in
               (args.state_dir, args.config, credential, cli)):
            raise ValueError("watchdog_local_paths_must_remain_on_H")
    if args.config.is_symlink() or args.config.stat().st_size > 4096:
        raise ValueError("watchdog_enrollment_invalid")
    value = json.loads(args.config.read_text())
    if (not isinstance(value, dict) or
            set(value) != {"version", "armed", "observationsUID", "policyUID", "leaseUID"} or
            type(value["version"]) is not int or value["version"] != 1 or type(value["armed"]) is not bool or
            any(not isinstance(value[k], str) or not 1 <= len(value[k]) <= 128
                for k in ("observationsUID", "policyUID", "leaseUID"))):
        raise ValueError("watchdog_enrollment_invalid")
    if not value["armed"]:
        raise ValueError("watchdog_not_armed")
    return value, cli, credential


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--kubectl", type=Path, help="H-only synthetic CLI, never a managed-host override")
    parser.add_argument("--managed-host", action="store_true")
    run = parser.add_mutually_exclusive_group(required=True)
    run.add_argument("--once", action="store_true")
    run.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    try:
        enrollment, cli, credential = profile(args)
        directory = args.state_dir
        if directory.is_symlink():
            raise ValueError("watchdog_private_state_required")
        os.umask(0o077)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o077:
            raise ValueError("watchdog_private_state_required")
        for name in ("watchdog.lock", "watchdog.sqlite", "watchdog.sqlite-journal", "watchdog.sqlite-wal", "watchdog.sqlite-shm"):
            private_state_file(directory / name)
        stopping = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stopping.set())
        signal.signal(signal.SIGINT, lambda *_: stopping.set())
        fd = os.open(directory / "watchdog.lock", os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError("watchdog_already_running") from None
            with sqlite3.connect(directory / "watchdog.sqlite", timeout=1) as db:
                state = WatchdogState(db)
                while not stopping.is_set():
                    inputs = []
                    for endpoint, limit in (
                            ("/api/v1/namespaces/bortus/configmaps/bortus-certificate-observations", 768 * 1024),
                            ("/apis/coordination.k8s.io/v1/namespaces/kube-node-lease/leases/node02", 32768)):
                        try:
                            raw = run_bounded([str(cli), "--kubeconfig", str(credential), "--request-timeout=10s",
                                               "get", "--raw", endpoint], output_limit=limit, timeout=15)
                            inputs.append(json.loads(raw))
                        except Exception:
                            inputs.append(None)  # Fixed coverage gap; never backend error text.
                    result = state.observe(*inputs, enrollment)
                    print(json.dumps(result), flush=True)
                    if args.once:
                        return 0 if all(result[k] == "healthy" for k in ("coverage", "monitorHeartbeat", "node02Lease")) else 1
                    stopping.wait(30)
        return 0
    except Exception:
        print(json.dumps({"state": "watchdog-unavailable", "physicalWorkerFailureProven": False}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
