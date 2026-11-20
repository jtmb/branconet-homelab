#!/usr/bin/env python3
"""Explicit local-H or fixed managed-host outbox delivery; installs nothing."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import sqlite3
import stat
import sys
import syslog
import threading

from certificate_monitor_notifications import (NotificationError, OutboxDelivery,
                                              publish_ntfy, validate_destination)
from certificate_monitor_process import run_bounded
from certificate_monitor_runtime import (H_ROOT, HOST_CODE, HOST_STATE,
                                         private_state_file, root_managed_file)

CONFIG = Path("/etc/bortus-certificate-monitor/notifications.json")
TOKEN = Path("/etc/bortus-certificate-monitor/notification-token")
CA = Path("/etc/bortus-certificate-monitor/notification-ca.crt")
PUBLIC_FAILURES = frozenset((
    "notification_config_invalid", "notification_event_invalid",
    "notification_credential_invalid", "notification_not_acknowledged",
    "notification_response_limit", "notification_ack_invalid",
    "notification_transport_unavailable", "notification_managed_profile_required",
    "notification_private_token_required", "notification_ca_invalid",
    "process_timeout", "process_failed", "process_unavailable",
    "process_input_limit", "process_output_limit", "process_stderr_limit",
    "process_io_failed",
))


def report_delivery_failure(error, phase):
    """Journal only a fixed code, never exception/backend text or private input."""
    reason = str(error)
    public = reason if reason in PUBLIC_FAILURES else "notification_unavailable"
    try:
        # Child stdout/stderr is deliberately bounded/captured by run_bounded.
        # A local journal message makes failures visible without exposing either.
        record = {
            "notificationFailure": public, "phase": phase,
            "humanReceiptVerified": False}
        stage, kind = getattr(error, "transport_stage", None), getattr(error, "transport_kind", None)
        if stage in ("configuration", "trust-context", "request", "response",
                     "response-read", "response-decode") and kind in (
                         "trust", "tls", "timeout", "permission", "os", "unexpected"):
            record.update(transportStage=stage, transportKind=kind)
        syslog.syslog(syslog.LOG_ERR, json.dumps(record))
    except OSError:
        pass  # Diagnostic availability must not change outbox retry semantics.


def profile(config_path, state, managed, watchdog=False):
    script = Path(__file__).absolute()
    code = Path("/usr/local/libexec/bortus-certificate-watchdog") if watchdog else HOST_CODE
    expected_state = Path("/var/lib/bortus-certificate-watchdog") if watchdog else HOST_STATE
    config_root = Path("/etc/bortus-certificate-watchdog") if watchdog else CONFIG.parent
    if managed:
        if (os.geteuid() == 0 or script != code / script.name or
                config_path != config_root / "notifications.json" or state != expected_state):
            raise NotificationError("notification_managed_profile_required")
        for name in (script.name, "certificate_monitor_notifications.py", "certificate_monitor.py",
                     "certificate_monitor_process.py", "certificate_monitor_runtime.py"):
            root_managed_file(code / name)
        root_managed_file(config_path)
    elif H_ROOT.resolve() not in state.resolve().parents or H_ROOT.resolve() not in config_path.resolve().parents:
        raise NotificationError("notification_local_paths_must_remain_on_H")
    if config_path.is_symlink() or config_path.stat().st_size > 4096:
        raise NotificationError("notification_config_invalid")
    config = json.loads(config_path.read_text())
    validate_destination(config)
    token, ca = Path(config["tokenFile"]), Path(config["caFile"])
    if managed:
        if token != config_root / "notification-token" or ca != config_root / "notification-ca.crt":
            raise NotificationError("notification_fixed_credential_paths_required")
        root_managed_file(token)
        root_managed_file(ca)
    elif any(H_ROOT.resolve() not in path.resolve().parents for path in (token, ca)):
        raise NotificationError("notification_local_paths_must_remain_on_H")
    info = token.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
            info.st_mode & (0o027 if managed else 0o077) or not 1 <= info.st_size <= 4096):
        raise NotificationError("notification_private_token_required")
    if ca.is_symlink() or ca.stat().st_size > 256 * 1024:
        raise NotificationError("notification_ca_invalid")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--managed-host", action="store_true")
    parser.add_argument("--watchdog", action="store_true", help="Use the independent watchdog's state/profile")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true")
    group.add_argument("--loop", action="store_true")
    group.add_argument("--send", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        config = profile(args.config, args.state_dir, args.managed_host, args.watchdog)
        if args.send:
            raw = sys.stdin.buffer.read(4097)
            if len(raw) > 4096:
                raise NotificationError("notification_event_limit")
            result = publish_ntfy(config, json.loads(raw), token=Path(config["tokenFile"]).read_text().strip(),
                                  ca_file=Path(config["caFile"]))
            print(json.dumps(result), flush=True)
            return 0
        state = args.state_dir
        if state.is_symlink() or state.stat().st_uid != os.getuid() or state.stat().st_mode & 0o077:
            raise NotificationError("notification_private_state_required")
        database = "watchdog.sqlite" if args.watchdog else "monitor.sqlite"
        for name in ("notification.lock", database, database + "-journal", database + "-wal", database + "-shm"):
            private_state_file(state / name)
        # Never create a new/empty replacement monitor DB or initialize scans.
        if not (state / database).is_file():
            raise NotificationError("notification_existing_state_required")
        stopping = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stopping.set())
        signal.signal(signal.SIGINT, lambda *_: stopping.set())
        os.umask(0o077)
        fd = os.open(state / "notification.lock", os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise NotificationError("notification_already_running") from None
            with sqlite3.connect((state / database).resolve().as_uri() + "?mode=rw", uri=True, timeout=1) as db:
                delivery = OutboxDelivery(db)

                def send(event):
                    if stopping.is_set():
                        raise NotificationError("notification_stopping")
                    command = [sys.executable, "-B", str(Path(__file__).absolute()),
                               "--config", str(args.config), "--state-dir", str(state), "--send"]
                    if args.managed_host:
                        command.append("--managed-host")
                    if args.watchdog:
                        command.append("--watchdog")
                    try:
                        return json.loads(run_bounded(command, data=json.dumps(event).encode(),
                                                      output_limit=1024, stderr_limit=1024, timeout=10))
                    except Exception as error:
                        report_delivery_failure(error, "child")
                        raise

                while not stopping.is_set():
                    result = delivery.deliver(send)
                    print(json.dumps(result), flush=True)
                    if args.once:
                        return 1 if result["failed"] else 0
                    stopping.wait(60)
        return 0
    except Exception as error:
        if args.send:
            report_delivery_failure(error, "transport")
        reason = str(error) if isinstance(error, NotificationError) else "notification_unavailable"
        print(json.dumps({"state": "notification-unavailable", "reason": reason,
                          "humanReceiptVerified": False}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
