#!/usr/bin/env python3
"""Fresh-DB exact-export scan under the explicit one-stage 4.25 GB exception.

Separate exclusive database/scan phases preserve interrupted evidence. No image
execution, export/pull, stale-DB fallback, tool install or production mutation.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time
import urllib.request

REPO = Path(__file__).resolve().parents[2]
STAGE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/certificates-qualification-20261116")
WORK = STAGE / "ntfy-security-vuln"
TOOL = Path("/home/brajam/.local/share/branconet-migration/audit20261023-20261023T203418Z/bin/trivy").resolve()
TOOL_SHA = "d1dfca6ae10a1ad4540bb94e64f0510077c47008920a9b554986b39dca573d83"
DB_MANIFEST = "sha256:b046135279316e1119730eacf73cb3d1ff1ca86bbedbb96ddd133ef11684ca8e"
DB_LAYER = "sha256:25ad50ee557465816b386a58125db6d5f8294ab3c5da334983e8d97dbdba473b"
DB_BYTES = 1_773_903_872
LAYER_BYTES = 140_815_146
BASE = "https://mirror.gcr.io/v2/aquasec/trivy-db/"
UNIT = "bortus-ntfy-vulnerability-qualification"
CANDIDATE = None
PUBLISHER = Path(json.loads((STAGE / "credential-bootstrap-publisher-result.json").read_text())["stage"])


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(name, value):
    with (WORK / name).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def allocated(path):
    return int(subprocess.check_output(["du", "-sx", "-B1", str(path)], timeout=20).split()[0])


def usage():
    return allocated(STAGE) + allocated(PUBLISHER)


def freshness(metadata):
    now = dt.datetime.now(dt.timezone.utc)
    updated = dt.datetime.fromisoformat(metadata["UpdatedAt"].replace("Z", "+00:00"))
    next_update = dt.datetime.fromisoformat(metadata["NextUpdate"].replace("Z", "+00:00"))
    assert metadata["Version"] == 2 and -300 <= (now - updated).total_seconds() <= 86400
    assert next_update > now and next_update > updated
    return {"checkedAt": now.isoformat(), "ageSeconds": (now - updated).total_seconds(),
            "nextUpdateInFuture": True}


def inputs():
    approval = json.loads((STAGE / "ntfy-security-vuln-approval.json").read_text())
    assert approval["approved"] and approval["stageCeilingBytes"] == 4_250_000_000
    assert approval["carriedImageRuntimeReserveBytes"] == 1_000_000_000
    assert sha(TOOL) == TOOL_SHA
    if CANDIDATE:
        archive = Path(CANDIDATE["exportPath"])
        assert archive.resolve() == STAGE / "ntfy-zlib-fixed/candidate-image.tar"
        assert CANDIDATE["built"] and CANDIDATE["vendorSignatureVerified"] and CANDIDATE["ntfyExecutableUnchanged"]
        assert sha(archive) == CANDIDATE["exportSHA256"]
    else:
        image = json.loads((STAGE / "ntfy-security-secrets/image-input.json").read_text())
        archive = STAGE / "ntfy-security-secrets/exact-image.tar"
        assert sha(archive) == image["archiveSHA256"]
    assert Path("/sys/fs/ext4/loop0/errors_count").read_text().strip() == "0"
    return approval, archive


class HashedStream:
    def __init__(self, stream):
        self.stream, self.hash, self.count = stream, hashlib.sha256(), 0

    def read(self, size=-1):
        assert 0 <= size <= 2 * 1024 * 1024
        block = self.stream.read(size)
        self.count += len(block)
        assert self.count <= LAYER_BYTES
        self.hash.update(block)
        return block


def database():
    inputs()
    assert not WORK.exists(), "existing_database_attempt_requires_reconciliation"
    retained = usage()
    assert retained + DB_BYTES + 1_000_000_000 < 4_250_000_000
    WORK.mkdir(mode=0o700)
    save("database-started.json", {
        "sourceSHA256": sha(Path(__file__)), "indexSHA256": sha(REPO / ".git/index"),
        "retainedBaselineBytes": retained, "plannedPeakBytes": retained + DB_BYTES + 1_000_000_000,
        "stageCeilingBytes": 4_250_000_000, "carriedImageRuntimeReserveBytes": 1_000_000_000,
        "reserveBreakdown": {"existingImageAndMetadataAllowanceBytes": 500_000_000,
                             "additionalScanWorkspaceAllowanceBytes": 500_000_000},
        "databaseManifest": DB_MANIFEST, "databaseLayer": DB_LAYER,
        "noRetainedCompressedCarrier": True})
    request = urllib.request.Request(BASE + "manifests/" + DB_MANIFEST,
                                    headers={"Accept": "application/vnd.oci.image.manifest.v1+json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(1024 * 1024 + 1)
    assert "sha256:" + hashlib.sha256(raw).hexdigest() == DB_MANIFEST
    manifest = json.loads(raw)
    assert len(manifest["layers"]) == 1
    layer = manifest["layers"][0]
    assert layer["digest"] == DB_LAYER and layer["size"] == LAYER_BYTES
    assert layer["mediaType"].endswith("tar+gzip")
    assert manifest["config"]["digest"] == "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
    (WORK / "db-manifest.json").write_bytes(raw)
    (WORK / "cache").mkdir()
    pending = WORK / "database.pending"
    pending.mkdir()
    observed, seen = {}, set()
    started = time.monotonic()
    with urllib.request.urlopen(BASE + "blobs/" + DB_LAYER, timeout=120) as response:
        hashed = HashedStream(response)
        with tarfile.open(fileobj=hashed, mode="r|gz") as archive:
            for member in archive:
                name = member.name.removeprefix("./")
                assert member.isfile() and name in ("trivy.db", "metadata.json") and name not in seen
                assert member.size == DB_BYTES if name == "trivy.db" else 0 < member.size <= 65536
                seen.add(name)
                member_hash, count = hashlib.sha256(), 0
                stream = archive.extractfile(member)
                with (pending / name).open("xb") as target:
                    while block := stream.read(1024 * 1024):
                        count += len(block)
                        assert count <= member.size and time.monotonic() - started < 600
                        member_hash.update(block)
                        target.write(block)
                    target.flush()
                    os.fsync(target.fileno())
                assert count == member.size
                observed[name] = {"bytes": count, "sha256": member_hash.hexdigest()}
        # Tar iteration can stop before response EOF: hash every remaining byte.
        while hashed.read(1024 * 1024):
            pass
    assert seen == {"trivy.db", "metadata.json"}
    assert hashed.count == LAYER_BYTES and "sha256:" + hashed.hash.hexdigest() == DB_LAYER
    metadata = json.loads((pending / "metadata.json").read_text())
    fresh = freshness(metadata)
    for name in seen:
        assert sha(pending / name) == observed[name]["sha256"]
        (pending / name).chmod(0o400)
    pending.rename(WORK / "cache/db")
    assert usage() + 500_000_000 < 4_250_000_000
    save("database-result.json", {
        "verified": True, "manifest": DB_MANIFEST, "layer": DB_LAYER,
        "compressedBytes": hashed.count, "entireCompressedLayerSHA256Verified": True,
        "files": observed, "metadata": metadata, "freshness": fresh,
        "sourceSHA256": sha(Path(__file__)), "wallSeconds": round(time.monotonic() - started, 2),
        "currentRetainedBytes": usage(), "noCompressedCarrierSaved": True})


def verify_database():
    """Recover a complete-sized interrupted download without writing a copy."""
    inputs()
    assert (WORK / "database-interrupted.json").is_file()
    assert not (WORK / "database-result.json").exists()
    assert not (WORK / "database-verification-started.json").exists()
    pending = WORK / "database.pending"
    assert pending.is_dir() and not pending.is_symlink()
    assert {p.name for p in pending.iterdir()} == {"trivy.db", "metadata.json"}
    snapshots = {}
    for path in pending.iterdir():
        info = path.lstat()
        assert path.is_file() and not path.is_symlink() and info.st_uid == os.getuid() and info.st_nlink == 1
        assert info.st_size == DB_BYTES if path.name == "trivy.db" else 0 < info.st_size <= 65536
        snapshots[path.name] = (info.st_ino, info.st_size, info.st_mtime_ns)
    assert "sha256:" + sha(WORK / "db-manifest.json") == DB_MANIFEST
    save("database-verification-started.json", {
        "sourceSHA256": sha(Path(__file__)), "pendingFilesReused": True,
        "newDatabaseBytesWritten": 0, "completeLayerComparisonRequired": True})
    observed, seen = {}, set()
    started = time.monotonic()
    with urllib.request.urlopen(BASE + "blobs/" + DB_LAYER, timeout=120) as response:
        hashed = HashedStream(response)
        with tarfile.open(fileobj=hashed, mode="r|gz") as archive:
            for member in archive:
                name = member.name.removeprefix("./")
                assert member.isfile() and name in snapshots and name not in seen
                assert member.size == snapshots[name][1]
                seen.add(name)
                source, digest, count = archive.extractfile(member), hashlib.sha256(), 0
                with (pending / name).open("rb") as retained:
                    while block := source.read(1024 * 1024):
                        assert retained.read(len(block)) == block, "interrupted_payload_differs_from_pinned_origin"
                        digest.update(block)
                        count += len(block)
                        assert time.monotonic() - started < 600
                    assert not retained.read(1)
                    os.fsync(retained.fileno())
                assert count == member.size
                observed[name] = {"bytes": count, "sha256": digest.hexdigest()}
        while hashed.read(1024 * 1024):
            pass
    assert seen == set(snapshots)
    assert hashed.count == LAYER_BYTES and "sha256:" + hashed.hash.hexdigest() == DB_LAYER
    metadata = json.loads((pending / "metadata.json").read_text())
    fresh = freshness(metadata)
    for name in seen:
        info = (pending / name).stat()
        assert (info.st_ino, info.st_size, info.st_mtime_ns) == snapshots[name]
        (pending / name).chmod(0o400)
    pending.rename(WORK / "cache/db")
    assert usage() + 500_000_000 < 4_250_000_000
    save("database-result.json", {
        "verified": True, "manifest": DB_MANIFEST, "layer": DB_LAYER,
        "compressedBytes": hashed.count, "entireCompressedLayerSHA256Verified": True,
        "files": observed, "metadata": metadata, "freshness": fresh,
        "sourceSHA256": sha(Path(__file__)), "wallSeconds": round(time.monotonic() - started, 2),
        "currentRetainedBytes": usage(), "noCompressedCarrierSaved": True,
        "interruptedPayloadRecoveredByCompleteByteComparison": True, "newDatabaseBytesWritten": 0})


def scan():
    _, archive = inputs()
    assert not (WORK / "scan-started.json").exists(), "existing_scan_requires_reconciliation"
    db = json.loads((WORK / "database-result.json").read_text())
    assert db["verified"]
    for name, value in db["files"].items():
        assert sha(WORK / "cache/db" / name) == value["sha256"]
    fresh = freshness(db["metadata"])
    baseline = json.loads((WORK / "database-started.json").read_text())["retainedBaselineBytes"]
    for name in ("home", "tmp", "docker-config"):
        (WORK / name).mkdir()
    (WORK / "empty.yaml").write_text("{}\n")
    (WORK / "no-ignore").write_text("")
    template = (REPO / "images/private-ntfy-zlib/security-results.tpl" if CANDIDATE else
                REPO / "k8s-rewrite/ansible-playbook/roles/worker1_oci_scan/files/results.tpl")
    if not CANDIDATE:
        assert template.read_text().strip() == "{{ toJson . }}"
    source, index = sha(Path(__file__)), sha(REPO / ".git/index")
    command = [str(TOOL), "image", "--input", str(archive), "--platform", "linux/amd64",
               "--config", str(WORK / "empty.yaml"), "--cache-dir", str(WORK / "cache"),
               "--scanners", "vuln,secret" if CANDIDATE else "vuln",
               "--secret-config", str(WORK / "empty.yaml"),
               "--offline-scan", "--skip-db-update", "--skip-java-db-update",
               "--skip-version-check", "--disable-telemetry", "--ignorefile", str(WORK / "no-ignore"),
               "--list-all-pkgs", "--timeout", "7m", "--parallel", "2", "--no-progress", "--debug",
               "--format", "template", "--template", "@" + str(template),
               "--output", str(WORK / "results.json")]
    env = {"PATH": "/usr/bin:/bin", "HOME": str(WORK / "home"),
           "DOCKER_CONFIG": str(WORK / "docker-config"), "TMPDIR": str(WORK / "tmp"),
           "XDG_CACHE_HOME": str(WORK / "cache"), "GOMAXPROCS": "2",
           "GOMEMLIMIT": "512MiB", "LANG": "C", "LC_ALL": "C"}
    if CANDIDATE:
        synthetic = {"SchemaVersion": 2, "ArtifactName": "synthetic",
                     "ArtifactType": "container_image", "Metadata": {"ImageConfig": {"config": {
                         "Env": ["SENTINEL_ENV"]}}}, "Results": [{"Target": "synthetic", "Class": "secret",
                         "Type": "", "Packages": [{"Name": "synthetic-package", "Version": "1"}],
                         "Vulnerabilities": [{"VulnerabilityID": "SYNTHETIC-ONLY", "Severity": "HIGH"}],
                         "Secrets": [{"RuleID": "synthetic-rule", "Category": "synthetic", "Severity": "HIGH",
                                      "StartLine": 1, "EndLine": 1, "Match": "SENTINEL_MATCH",
                                      "Code": {"Lines": [{"Content": "SENTINEL_CODE"}]}}]}]}
        save("redaction-input.json", synthetic)
        converted = subprocess.check_output([str(TOOL), "--config", str(WORK / "empty.yaml"),
                                            "convert", "--format", "template", "--template", "@" + str(template),
                                            str(WORK / "redaction-input.json")], env=env, stderr=subprocess.PIPE, timeout=20)
        assert b"SENTINEL_" not in converted
        projected = json.loads(converted)
        assert projected[0]["Secrets"][0]["RuleID"] == "synthetic-rule"
        assert projected[0]["Vulnerabilities"][0]["VulnerabilityID"] == "SYNTHETIC-ONLY"
        assert projected[0]["Packages"][0]["Name"] == "synthetic-package"
        save("redaction-result.json", {"imageEnvMatchAndCodeOmitted": True,
                                       "findingAndPackageMetadataPreserved": True})
    props = ["MemoryMax=1G", "MemorySwapMax=0", "CPUQuota=200%", "TasksMax=64",
             "LimitFSIZE=400M", "RuntimeMaxSec=480", "KillMode=control-group"]
    launch = ["systemd-run", "--user", "--unit", UNIT, "--wait", "--pipe", "--working-directory", str(WORK)]
    for prop in props:
        launch += ["--property", prop]
    launch += ["/usr/bin/env", "-i", *[k + "=" + v for k, v in env.items()], *command]
    save("scan-started.json", {"sourceSHA256": source, "indexSHA256": index, "freshness": fresh,
                              "command": command, "resourceProperties": props, "templateSHA256": sha(template),
                              "filters": "All severities/statuses; no ignore/VEX/unfixed suppression"})
    peak, samples, failure = usage(), [], None
    with (WORK / "scanner.stderr").open("xb") as errors:
        process = subprocess.Popen(launch, stdout=errors, stderr=errors)
        while process.poll() is None:
            try:
                used = usage()
                peak = max(peak, used)
                # Keep BOTH halves of the original full 1 GB reserve: already
                # counted workspace must not be charged a second time.
                assert used <= baseline + DB_BYTES + 500_000_000, "scan_workspace_exceeds_reserve"
                assert used + 500_000_000 <= 4_250_000_000, "stage_ceiling_exceeded"
                assert Path("/sys/fs/ext4/loop0/errors_count").read_text().strip() == "0"
                show = subprocess.run(["systemctl", "--user", "show", UNIT, "--property=ControlGroup"],
                                      capture_output=True, text=True, timeout=10)
                value = show.stdout.strip().removeprefix("ControlGroup=")
                if value.startswith("/"):
                    root = Path("/sys/fs/cgroup") / value.lstrip("/")
                    sample = {}
                    for name in ("memory.max", "memory.swap.max", "cpu.max", "pids.max", "memory.current", "memory.events"):
                        path = root / name
                        if path.exists():
                            sample[name] = path.read_text().strip()
                    if sample:
                        samples.append(sample)
            except Exception as error:
                failure = type(error).__name__ + ":" + str(error)
                subprocess.run(["systemctl", "--user", "stop", UNIT], check=True, timeout=20)
                break
            time.sleep(.2)
        code = process.wait(timeout=30)
    save("resources.json", {"kernelSamples": samples, "exit": code, "boundedFailure": failure,
                            "measuredStagePeakBytes": peak, "existingImageAllowanceBytes": 500_000_000,
                            "chargedObservedPeakBytes": peak + 500_000_000,
                            "fullReservedPlanBytes": baseline + DB_BYTES + 1_000_000_000})
    assert code == 0 and not failure, "scanner_failed_not_clean"
    assert samples and all(s.get("memory.max") == "1073741824" and
                           s.get("memory.swap.max") == "0" and s.get("pids.max") == "64" and
                           s.get("cpu.max") == "200000 100000" for s in samples)
    results = json.loads((WORK / "results.json").read_text())
    assert isinstance(results, list) and results
    types = {r.get("Type") for r in results}
    assert {"alpine", "gobinary"} <= types, "incomplete_component_coverage"
    rows = []
    for target in results:
        assert not target.get("Misconfigurations")
        if not CANDIDATE:
            assert not target.get("Secrets")
        for finding in target.get("Vulnerabilities") or []:
            rows.append({"target": target.get("Target"), "type": target.get("Type"),
                         **{k: finding.get(k) for k in ("VulnerabilityID", "PkgName", "PkgPath", "InstalledVersion",
                                                       "FixedVersion", "Severity", "Status", "PrimaryURL")}})
    for name, value in db["files"].items():
        assert sha(WORK / "cache/db" / name) == value["sha256"]
    save("findings.json", rows)
    result = {"scanCompleted": True, "scannerExit": code, "vulnerabilityRows": len(rows),
              "severityCounts": dict(collections.Counter(r["Severity"] for r in rows)),
              "fixedCriticalHighRows": sum(r["Severity"] in ("CRITICAL", "HIGH") and bool(r["FixedVersion"]) for r in rows),
              "coverage": [{"type": r.get("Type"), "class": r.get("Class"),
                            "packages": len(r.get("Packages") or []),
                            "vulnerabilities": len(r.get("Vulnerabilities") or [])} for r in results],
              "databaseFilesUnchanged": True, "database": db["metadata"], "databaseManifest": DB_MANIFEST,
              "reportSHA256": sha(WORK / "results.json"), "scannerSHA256": TOOL_SHA,
              "sourceSHA256": source, "sourceUnchanged": sha(Path(__file__)) == source,
              "indexUnchanged": sha(REPO / ".git/index") == index,
              "kernelSamples": len(samples), "productionActivated": False,
              "securityDisposition": "assessment required; scanner exit alone is not acceptance"}
    if CANDIDATE:
        zlib = [p for r in results if r.get("Type") == "alpine" for p in r.get("Packages") or []
                if p.get("Name") == "zlib"]
        assert len(zlib) == 1 and zlib[0]["Version"] == "1.4-r0"
        result.update(candidateManifest=CANDIDATE["candidateManifest"], zlibVersion=zlib[0]["Version"],
                      secretFindings=sum(len(r.get("Secrets") or []) for r in results),
                      candidateBuildSHA256=sha(STAGE / "ntfy-zlib-fixed/build-result.json"),
                      templateSHA256=sha(template))
    save("result.json", result)
    print(json.dumps(result, indent=2))


def main():
    global WORK, UNIT, CANDIDATE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("database", "verify-database", "scan"))
    parser.add_argument("--candidate-record", type=Path)
    args = parser.parse_args()
    if args.candidate_record:
        assert args.candidate_record.resolve() == STAGE / "ntfy-zlib-fixed/build-result.json"
        CANDIDATE = json.loads(args.candidate_record.read_text())
        WORK = STAGE / "ntfy-zlib-fixed/security"
        UNIT = "bortus-ntfy-fixed-security"
    os.umask(0o077)
    if args.phase == "database":
        database()
        print((WORK / "database-result.json").read_text())
    elif args.phase == "verify-database":
        verify_database()
        print((WORK / "database-result.json").read_text())
    else:
        scan()


if __name__ == "__main__":
    main()
