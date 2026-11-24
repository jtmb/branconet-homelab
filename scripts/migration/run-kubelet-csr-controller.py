#!/usr/bin/env python3
"""Observation-first kubelet-serving CSR controller; no CA or blanket approval.

Observation mode records strict verdicts and mutates nothing. Approval mode is
inert unless the reviewed enablement flag is supplied, the enrollment record is
an explicit operator file, and the durable state has no earlier approval for
that exact CSR UID/request. Installed-certificate verification is a separate,
explicitly reported step.
"""
import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import signal
import sqlite3
import threading
import time

from certificate_monitor_process import run_bounded
from kubelet_csr_controller import (ControllerError, ControllerState, decide,
                                   enrollment_set, requester_node, verify_issued)

RUNTIME = Path("/home/brajam/.local/share/branconet-migration")
SIGNER = "kubernetes.io/kubelet-serving"
HOST_STATE = Path("/var/lib/bortus-csr-controller")


def kubectl(binary, config, args, data=None, limit=2 * 1024 ** 2):
    command = [str(binary), "--kubeconfig", str(config), "--request-timeout=15s", *args]
    raw = run_bounded(command, data=data, output_limit=limit, timeout=25)
    return json.loads(raw) if raw.strip() else None


def pending(rows):
    """Only Pending kubelet-serving requests are ever considered."""
    return [row for row in rows if row.get("spec", {}).get("signerName") == SIGNER
            and not row.get("status", {}).get("certificate")
            and not row.get("status", {}).get("conditions")
            and not row.get("metadata", {}).get("deletionTimestamp")]


def unenrolled_verdict(csr, claimed, mode, now):
    """Record a request from a machine that is not on the enrollment list.

    It is kept as durable evidence but is never eligible, so it can never be
    approved no matter what mode the controller runs in.
    """
    import hashlib
    meta = csr.get("metadata", {})
    raw = csr.get("spec", {}).get("request")
    return {"mode": mode,
            "csr": {"name": meta.get("name"), "uid": meta.get("uid"),
                    "resourceVersion": meta.get("resourceVersion")},
            "node": claimed or "unknown",
            "requestSHA256": hashlib.sha256((raw if isinstance(raw, str) else "").encode()).hexdigest(),
            "eligible": False, "reasons": ["node_not_enrolled"],
            "checkedAt": now.isoformat()}


def cycle(binary, config, state, enrolled, mode, approval_enabled, now=None):
    """One observe/approve pass over pending kubelet-serving CSRs.

    `enrolled` is enrollment_set(): {node name: (trusted record, approve)}.
    Each request is checked against the enrollment of the machine that the
    API server says sent it. Approval additionally needs approve mode, the
    global --approval-enabled flag, and that machine's own approve switch.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    listed = kubectl(binary, config, ["get", "csr", "-o", "json"])["items"]
    verdicts = []
    for row in pending(listed):
        name = row["metadata"]["name"]
        # Re-read the exact objects before deciding; never trust a list snapshot.
        csr = kubectl(binary, config, ["get", "csr", name, "-o", "json"])
        claimed = requester_node(csr)
        if claimed not in enrolled:
            verdict = state.record(unenrolled_verdict(csr, claimed, mode, now))
            verdicts.append(verdict | {"approved": False, "nodeApprovalEnabled": False})
            continue
        trusted, node_approve = enrolled[claimed]
        node = kubectl(binary, config, ["get", "node", trusted["name"], "-o", "json"])
        verdict = decide(csr, node, trusted, mode=mode, now=now)
        verdict = state.record(verdict) | {"nodeApprovalEnabled": node_approve}
        if (mode == "approve" and approval_enabled and node_approve and
                state.approval_allowed(verdict, mode)):
            patch = state.mark_approved(csr, now.isoformat())
            try:
                kubectl(binary, config, ["patch", "csr", name, "--subresource=approval",
                                         "--type=json", "--patch-file=/dev/stdin"],
                        data=json.dumps(patch).encode())
            except Exception:
                # The patch may have applied even when the CLI exits nonzero.
                # Confirm cluster truth before reporting an uncertain outcome.
                current = kubectl(binary, config, ["get", "csr", name, "-o", "json"])
                if not any(c.get("type") == "Approved"
                           for c in current.get("status", {}).get("conditions", [])):
                    # Definite failure: release the exactly-once row so a later
                    # cycle can retry instead of wedging this CSR permanently.
                    # (Was `meta["uid"]`, an undefined name: a definite failure
                    # crashed with NameError and wedged the CSR instead.)
                    state.release_approval(csr["metadata"]["uid"])
                    raise
            verdict = verdict | {"approved": True}
        else:
            verdict = verdict | {"approved": False}
        verdicts.append(verdict)
    # Issued certificates are verified separately from approval.
    issued = []
    for row in [r for r in listed if r.get("status", {}).get("certificate")]:
        name, uid = row["metadata"]["name"], row["metadata"]["uid"]
        if not state.db.execute("SELECT 1 FROM kubelet_csr_decisions WHERE csr_uid=? AND approved_at IS NOT NULL",
                                (uid,)).fetchone():
            continue
        claimed = requester_node(row)
        if claimed not in enrolled:
            continue
        ok, reason = verify_issued(row, enrolled[claimed][0], now)
        record = {"csr": name, "issuedVerified": ok, "reason": reason}
        if ok:
            state.mark_issued_verified(uid, now.isoformat())
        issued.append(record)
    return {"mode": mode, "approvalEnabled": bool(mode == "approve" and approval_enabled),
            "pending": len(verdicts), "verdicts": verdicts, "issued": issued,
            "state": state.summary(), "csrMutationPerformed": any(v.get("approved") for v in verdicts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--enrollment-file", type=Path, required=True)
    parser.add_argument("--kubectl", type=Path, help="Fixture CLI allowed only on H")
    parser.add_argument("--managed-host", action="store_true")
    parser.add_argument("--mode", choices=["observe", "approve"], default="observe")
    parser.add_argument("--approval-enabled", action="store_true",
                        help="Operator decision after positive and negative qualification")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true")
    group.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()
    try:
        if not 30 <= args.interval <= 900:
            raise ControllerError("controller_interval_invalid")
        if args.approval_enabled and args.mode != "approve":
            raise ControllerError("approval_flag_requires_approve_mode")
        if args.enrollment_file.is_symlink() or args.enrollment_file.stat().st_size > 8192:
            raise ControllerError("enrollment_file_invalid")
        trusted = enrollment_set(json.loads(args.enrollment_file.read_text()))
        state_dir = args.state_dir
        if args.managed_host:
            if os.geteuid() == 0 or state_dir != HOST_STATE or args.kubectl is not None:
                raise ControllerError("controller_managed_profile_required")
            from certificate_monitor_runtime import root_managed_file
            code = Path("/usr/local/libexec/bortus-csr-controller")
            if Path(__file__).absolute() != code / Path(__file__).name:
                raise ControllerError("controller_managed_installation_required")
            for name in ("run-kubelet-csr-controller.py", "kubelet_csr_controller.py",
                         "kubelet_csr_policy.py", "certificate_monitor_process.py"):
                root_managed_file(code / name)
            config = Path("/etc/bortus-csr-controller/kubeconfig.json")
            ca = Path("/etc/bortus-csr-controller/cluster-ca.crt")
            token = Path("/run/bortus-csr-controller/token")
            root_managed_file(config)
            root_managed_file(ca)
            if args.enrollment_file != Path("/etc/bortus-csr-controller/enrollment.json"):
                raise ControllerError("controller_fixed_enrollment_required")
            expected = {
                "apiVersion": "v1", "kind": "Config",
                "clusters": [{"name": "branconet", "cluster": {
                    "server": "https://192.168.0.251:6443",
                    "certificate-authority": str(ca)}}],
                "users": [{"name": "bortus-csr-controller",
                           "user": {"tokenFile": str(token)}}],
                "contexts": [{"name": "csr-controller", "context": {
                    "cluster": "branconet", "user": "bortus-csr-controller",
                    "namespace": "bortus"}}],
                "current-context": "csr-controller"}
            if config.stat().st_size > 16384 or json.loads(config.read_text()) != expected:
                raise ControllerError("controller_fixed_kubeconfig_required")
            info = root_managed_file(token)
            if not 0 < info.st_size <= 16384 or info.st_mode & 0o007:
                raise ControllerError("controller_private_credential_required")
            binary = Path("/usr/local/bin/kubectl")
            root_managed_file(binary)
        else:
            from certificate_monitor_runtime import H_ROOT
            if H_ROOT.resolve() not in state_dir.resolve().parents:
                raise ControllerError("controller_local_state_must_remain_on_H")
            if args.kubectl is None or not os.access(args.kubectl, os.X_OK):
                raise ControllerError("controller_fixture_cli_required")
            binary, config = args.kubectl, RUNTIME / "admin.conf"
        if state_dir.is_symlink():
            raise ControllerError("controller_private_state_required")
        os.umask(0o077)
        state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if state_dir.stat().st_uid != os.getuid() or state_dir.stat().st_mode & 0o077:
            raise ControllerError("controller_private_state_required")
        stopping = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stopping.set())
        signal.signal(signal.SIGINT, lambda *_: stopping.set())
        lock = state_dir / "controller.lock"
        for name in ("controller.lock", "csr-controller.sqlite", "csr-controller.sqlite-journal",
                     "csr-controller.sqlite-wal", "csr-controller.sqlite-shm"):
            path = state_dir / name
            if path.is_symlink():
                raise ControllerError("controller_state_alias_refused")
        fd = os.open(lock, os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ControllerError("controller_already_running") from None
            with sqlite3.connect(state_dir / "csr-controller.sqlite", timeout=2) as db:
                state = ControllerState(db)
                while not stopping.is_set():
                    result = cycle(binary, config, state, trusted, args.mode, args.approval_enabled)
                    print(json.dumps(result), flush=True)
                    if args.once:
                        return 0
                    stopping.wait(args.interval)
        return 0
    except Exception as error:
        reason = str(error) if isinstance(error, ControllerError) else "controller_unavailable"
        print(json.dumps({"state": "controller-unavailable", "reason": reason,
                          "csrMutationPerformed": False}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
