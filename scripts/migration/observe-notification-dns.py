#!/usr/bin/env python3
"""Read-only exact-source/Flux and serial DNS checkpoint observation."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

import yaml

SPEC = importlib.util.spec_from_file_location(
    "notification_dns_transport", Path(__file__).with_name("stage-ntfy-cluster.py"))
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
WORK = BASE.STAGE / "ntfy-dns-delivery"
PRIVATE = Path("/mnt/c/Users/james/AppData/Local/BORTUS/repos/branconet-charts")
STATUS = Path("/mnt/f/branconet-migration-artifacts/maintenance-storage-20261025/"
              "branconet-charts-local-ci-state/status.json")


def save(name, value):
    with (WORK / name).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["secondary", "primary"])
    phase = parser.parse_args().phase
    assert not (WORK / f"{phase}-observe-started.json").exists(), "reconcile_started_phase"
    source = json.loads((WORK / f"{phase}-push-result.json").read_text())["sourceSHA"]
    before = json.loads((WORK / "preflight.json").read_text())
    save(f"{phase}-observe-started.json", {
        "sourceSHA": source, "maximumSeconds": 420, "readOnly": True,
        "driverSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    deadline = time.monotonic() + 420
    try:
        publisher = None
        while time.monotonic() < deadline:
            try:
                current = json.loads(STATUS.read_text())
            except (ValueError, FileNotFoundError):
                time.sleep(1)
                continue
            if current.get("sourceSHA") == source and current.get("finishedUTC"):
                publisher = current
                break
            time.sleep(2)
        assert publisher and publisher.get("passed") and publisher.get("phase") == "published_await_flux"
        save(f"{phase}-publisher-result.json", publisher)
        stage = Path(publisher["stage"])
        assert json.loads((stage / "check.json").read_text())["checks"][3]["testCount"] == 44
        while time.monotonic() < deadline:
            flux = BASE.call(["get", "kustomization.kustomize.toolkit.fluxcd.io",
                              "migration-releases", "-n", "flux-system", "-o", "json"])
            if (flux.get("status", {}).get("lastAppliedRevision", "").endswith(source)
                    and any(c["type"] == "Ready" and c["status"] == "True"
                            and c.get("observedGeneration") == flux["metadata"]["generation"]
                            for c in flux.get("status", {}).get("conditions", []))):
                break
            time.sleep(3)
        else:
            raise RuntimeError("exact_source_flux_timeout")
        deployments = BASE.call(["get", "deployment", "pihole", "pihole-secondary",
                                 "-n", "pihole", "-o", "json"])["items"]
        for obj in deployments:
            prior = next(v for v in before["deployments"] if v["name"] == obj["metadata"]["name"])
            assert obj["metadata"]["uid"] == prior["uid"]
            expected = "lan-dns-records-v3" if phase == "secondary" and obj["metadata"]["name"] == "pihole" else "lan-dns-records-v4"
            refs = [v["configMapRef"]["name"] for c in obj["spec"]["template"]["spec"]["containers"]
                    for v in c.get("envFrom", []) if "configMapRef" in v]
            assert refs == [expected]
            assert obj["status"]["observedGeneration"] == obj["metadata"]["generation"]
            assert obj["status"]["updatedReplicas"] == obj["status"]["availableReplicas"] == 1
            if phase == "secondary" and obj["metadata"]["name"] == "pihole":
                assert obj["metadata"]["generation"] == prior["generation"]
        claims = BASE.call(["get", "pvc", "-n", "pihole", "-o", "json"])["items"]
        assert {o["metadata"]["uid"]: o["spec"].get("volumeName") for o in claims} == {
            o["uid"]: o["volumeName"] for o in before["claims"]}
        data = yaml.safe_load((PRIVATE / "flux/releases/foundation/lan-dns-records-v3.yaml").read_text())["data"]
        expected = {}
        for line in data["FTLCONF_dns_hosts"].splitlines():
            address, host = line.split()
            expected.setdefault(host, []).append(address)
        for line in data["FTLCONF_dns_cnameRecords"].splitlines():
            host, target = line.split(",")
            expected[host] = expected[target]
        params = {"expected": expected, "phase": phase}
        remote = r'''
import ipaddress,json,subprocess
count=0
servers=['10.96.11.155','10.97.190.57','192.168.0.253','192.168.0.5']
for server in servers:
 for transport in ['+notcp','+tcp']:
  checks=dict(PARAMS['expected'])
  if server=='10.97.190.57' or (PARAMS['phase']=='primary' and server!='192.168.0.5'):
   checks['notifications.branconet.lan']=['192.168.0.252']
  checks['doubleclick.net']=['0.0.0.0']
  checks['example.com']=None
  for name,want in checks.items():
   q=subprocess.run(['dig','@'+server,name,'A','+short','+time=2','+tries=1',transport],capture_output=True,text=True,timeout=4)
   addresses=[]
   for line in q.stdout.splitlines():
    try: addresses.append(str(ipaddress.IPv4Address(line)))
    except ipaddress.AddressValueError: pass
   assert q.returncode==0 and (set(addresses)==set(want) if want is not None else bool(addresses)), (server,transport,name)
   count+=1
print(json.dumps({'passed':True,'directTCP_UDPChecks':count,'legacyNames':len(PARAMS['expected']),'allFourPathsVerified':True,'newNameVerifiedOnQualifiedBackends':True,'independentNewNameNotYetClaimed':True}))
'''
        command = ["ssh", "-p", "2002", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                   "-o", "ConnectTimeout=8", "-i", "/home/brajam/.ssh/id_ed25519",
                   "james@192.168.0.4", "python3 -B -c " + shlex.quote("PARAMS=" + repr(params) + "\n" + remote)]
        queries = json.loads(subprocess.check_output(command, timeout=180))
        result = {"passed": True, "phase": phase, "sourceSHA": source,
                  "publisherStage": str(stage), "queries": queries,
                  "claimUIDsAndVolumeBindingsPreserved": True,
                  "primaryUntouched": phase == "secondary",
                  "deployments": [BASE.metadata(o) for o in deployments],
                  "nativeAuthAndRotationChanged": False}
        save(f"{phase}-result.json", result)
        print(json.dumps(result, indent=2))
    except Exception as error:
        save(f"{phase}-observe-failure.json", {
            "errorType": type(error).__name__, "sourceSHA": source,
            "readOnlyObserver": True, "reconcileBeforeRetry": True})
        raise


if __name__ == "__main__":
    main()
