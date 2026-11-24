#!/usr/bin/env python3
"""Fixed node03 wrapper of the existing bounded broker/resource/timer observer."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex

from certificate_monitor_process import run_bounded

ROOT = Path(__file__).resolve().parents[2]
STAGE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/"
             "bortus-operator-recovery/certificates-qualification-20261116")
WORK = STAGE / "watchdog-host-activation"
SOURCE = ROOT / "scripts/migration/qualify-node02-credential-service.py"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["once", "timer", "observe", "inspect"])
    args = parser.parse_args()
    prefix = WORK / ("credential-" + args.phase)
    assert not prefix.with_suffix(".started.json").exists(), "reconcile_existing_phase"
    assert json.loads((WORK / "credential-host-stage-result.json").read_text())["passed"]
    started = json.loads((WORK / "credential-host-stage-started.json").read_text())
    files = {}
    for name, expected in started["sourceSHA256"].items():
        assert hashlib.sha256((ROOT / "scripts/migration" / name).read_bytes()).hexdigest() == expected
        files["/usr/local/libexec/bortus-certificate-watchdog/" + name] = expected
    for name in ("bortus-certificate-watchdog-credential.service",
                 "bortus-certificate-watchdog-credential.timer"):
        files["/etc/systemd/system/" + name] = hashlib.sha256(
            (ROOT / "k8s-rewrite/ansible-playbook/playbooks/files" / name).read_bytes()).hexdigest()
    if args.phase == "timer":
        once = json.loads((WORK / "credential-once.result.json").read_text())
        assert (once.get("phase") == "once" and once.get("state") != "qualification-failed"
                and once.get("resourceSampleCount", 0) > 0 and once.get("processSecurity"))
    spec = importlib.util.spec_from_file_location("shared_broker_qualification", SOURCE)
    shared = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared)
    params = {"profile": "watchdog", "phase": args.phase, "files": files,
              "uid": started["qualifiedServiceAccountUID"],
              "publicEnrollment": started["publicEnrollment"]}
    if args.phase == "observe":
        baseline = json.loads((WORK / "credential-timer.result.json").read_text())
        assert "expectedPeriodicDueUSec" in baseline
        params["baseline"] = baseline
    prefix.with_suffix(".started.json").write_text(json.dumps({
        "phase": args.phase, "host": "node03", "files": files,
        "sharedCollectorSHA256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "sourceSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "detectorOrSenderActivation": False}, indent=2) + "\n")
    spec = importlib.util.spec_from_file_location("saved_watchdog_qualification",
                                                 ROOT / "scripts/migration/saved-node-credential.py")
    saved = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(saved)
    password = saved.existing_password()
    try:
        code = "PARAMS=" + repr(params) + "\n" + shared.REMOTE
        raw = run_bounded([
            "ssh", "-p", "2002", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ConnectTimeout=8", "-i", "/home/brajam/.ssh/id_ed25519", "james@192.168.0.5",
            "sudo -S -p '' /usr/bin/python3 -B -c " + shlex.quote(code)],
            data=(password + "\n").encode(), output_limit=256 * 1024,
            timeout=1800 if args.phase == "observe" else 530)
        result = json.loads(raw)
        prefix.with_suffix(".result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        if result.get("state") == "qualification-failed":
            return 1
    except Exception as error:
        prefix.with_suffix(".failure.json").write_text(json.dumps({
            "phase": args.phase, "reason": type(error).__name__,
            "outcomeRequiresReconciliation": True}, indent=2) + "\n")
        raise RuntimeError("watchdog_broker_outcome_requires_reconciliation") from None
    finally:
        password = None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
