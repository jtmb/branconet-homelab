#!/usr/bin/env python3
"""Collect fixed metadata GETs and bind retained local candidate; applies nothing."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys

from certificate_monitor_process import run_bounded
from ntfy_integration_preflight import collect

REPO = Path(__file__).resolve().parents[2]
STAGE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/certificates-qualification-20261116")
WORK = STAGE / "ntfy-integration-preparation"


def main():
    assert not WORK.exists(), "existing_preparation_requires_reconciliation_not_replay"
    os.umask(0o077)
    WORK.mkdir(mode=0o700)
    candidate = json.loads((STAGE / "ntfy-zlib-fixed/fixed-candidate-acceptance.json").read_text())
    assert candidate["localQualificationPassed"]
    index = hashlib.sha256((REPO / ".git/index").read_bytes()).hexdigest()
    paths = [Path(__file__), Path(__file__).with_name("ntfy_integration_preflight.py")]
    source = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (WORK / "started.json").write_text(json.dumps({"at": dt.datetime.now(dt.timezone.utc).isoformat(),
                                                  "sourceSHA256": source, "indexSHA256": index,
                                                  "readOnly": True, "reservedNewOutputBytes": 1_000_000}, indent=2))
    base = ["/home/brajam/.local/share/branconet-migration/bin/kubectl", "--kubeconfig",
            "/home/brajam/.local/share/branconet-migration/admin.conf", "--request-timeout=15s"]
    calls = []

    def reader(endpoint):
        calls.append(endpoint)
        raw = run_bounded(base + ["get", "--raw", endpoint], output_limit=2 * 1024 * 1024, timeout=20)
        return json.loads(raw)

    result = collect(reader)
    result.update(checkedAt=dt.datetime.now(dt.timezone.utc).isoformat(),
                  candidateManifest=candidate["candidateManifest"], sourceSHA256=source,
                  candidateAcceptanceSHA256=hashlib.sha256(
                      (STAGE / "ntfy-zlib-fixed/fixed-candidate-acceptance.json").read_bytes()).hexdigest(),
                  fixedGETEndpoints=calls, indexUnchanged=hashlib.sha256(
                      (REPO / ".git/index").read_bytes()).hexdigest() == index,
                  noApplyDryRunPOSTExecCredentialOrPublication=True)
    (WORK / "preflight-result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"state": "preparation-incomplete", "reason": type(error).__name__,
                          "productionMutation": False}), file=sys.stderr)
        raise
