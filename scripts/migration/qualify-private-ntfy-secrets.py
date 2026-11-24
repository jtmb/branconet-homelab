#!/usr/bin/env python3
"""Database-independent exact-image secret qualification, not CVE approval.

Uses the existing approved scanner, one bounded H export, and a metadata-only
template. Does not execute/pull the image or read production credentials.
Existing attempts must be reconciled, never overwritten.
"""
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import tarfile
import time

REPO = Path(__file__).resolve().parents[2]
STAGE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/certificates-qualification-20261116")
WORK = STAGE / "ntfy-security-secrets"
TOOL = Path("/home/brajam/.local/share/branconet-migration/audit20261023-20261023T203418Z/bin/trivy").resolve()
TOOL_SHA = "d1dfca6ae10a1ad4540bb94e64f0510077c47008920a9b554986b39dca573d83"
MANIFEST = "sha256:6ceb27333175e3ce7d021bb883658858f2b8b883db316a73d0755dfa0b306fc4"
IMAGE = "docker.io/binwiederhier/ntfy@" + MANIFEST
UNIT = "bortus-ntfy-secret-qualification"
# Never serialize image Config/Env, secret Match or source Code lines.
TEMPLATE = """[
{{- range $i, $r := . -}}
{{if $i}},{{end}}{"Target":{{toJson $r.Target}},"Class":{{toJson $r.Class}},"Type":{{toJson $r.Type}},"Secrets":[
{{- range $j, $s := $r.Secrets -}}
{{if $j}},{{end}}{"RuleID":{{toJson $s.RuleID}},"Category":{{toJson $s.Category}},"Severity":{{toJson $s.Severity}},"StartLine":{{$s.StartLine}},"EndLine":{{$s.EndLine}}}
{{- end -}}]}
{{- end -}}]
"""


def save(name, value):
    with (WORK / name).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(args, **kwargs):
    return subprocess.check_output(args, stderr=subprocess.PIPE, timeout=30, **kwargs)


def main():
    if WORK.exists():
        raise RuntimeError("existing_secret_attempt_requires_reconciliation")
    assert sha(TOOL) == TOOL_SHA
    acceptance = json.loads((STAGE / "ntfy-server-isolated-acceptance.json").read_text())
    assert acceptance["registryBinding"]["linuxAMD64Manifest"] == MANIFEST
    descriptor = json.loads(run(["docker", "image", "inspect", IMAGE, "--format", "{{json .Descriptor}}"]))
    assert descriptor["digest"] == MANIFEST
    publisher = Path(json.loads((STAGE / "credential-bootstrap-publisher-result.json").read_text())["stage"])
    baseline = sum(int(run(["du", "-sx", "-B1", str(p)]).split()[0]) for p in (STAGE, publisher))
    # Export, scanner expansion/cache/logs are inside the carried 1 GB reserve,
    # not an additional allowance. Export itself is limited to 200 MB.
    assert baseline + 1_000_000_000 < 4_000_000_000
    os.umask(0o077)
    WORK.mkdir(mode=0o700)
    binding = sha(Path(__file__))
    index = sha(REPO / ".git/index")
    save("started.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(),
                         "sourceSHA256": binding, "image": IMAGE,
                         "scannerSHA256": TOOL_SHA, "baselineBytes": baseline,
                         "retainedRuntimeReserveBytes": 1_000_000_000,
                         "stageCeilingBytes": 4_000_000_000,
                         "scope": "secret only; vulnerability database not used"})
    for folder in ("cache", "tmp", "home", "docker-config"):
        (WORK / folder).mkdir()
    (WORK / "empty.yaml").write_text("{}\n")
    (WORK / "no-ignore").write_text("")
    (WORK / "metadata.tpl").write_text(TEMPLATE)
    archive = WORK / "exact-image.tar"

    def export_limit():
        resource.setrlimit(resource.RLIMIT_FSIZE, (200_000_000, 200_000_000))

    with archive.open("xb") as output, (WORK / "export.stderr").open("xb") as errors:
        subprocess.run(["docker", "image", "save", IMAGE], stdout=output,
                       stderr=errors, timeout=90, check=True, preexec_fn=export_limit)
    layer_rows = []
    with tarfile.open(archive) as contents:
        names = contents.getnames()
        assert len(names) == len(set(names))
        member_name = "blobs/sha256/" + MANIFEST.split(":")[1]
        manifest_raw = contents.extractfile(member_name).read(65537)
        assert hashlib.sha256(manifest_raw).hexdigest() == MANIFEST.split(":")[1]
        manifest = json.loads(manifest_raw)
        assert manifest["config"]["digest"] == acceptance["registryBinding"]["config"]
        for descriptor in [manifest["config"], *manifest["layers"]]:
            member = contents.getmember("blobs/sha256/" + descriptor["digest"].split(":")[1])
            assert member.size == descriptor["size"]
            stream = contents.extractfile(member)
            assert hashlib.file_digest(stream, "sha256").hexdigest() == descriptor["digest"].split(":")[1]
            if descriptor not in manifest["layers"]:
                continue
            stream = contents.extractfile(member)
            expanded = gzip.GzipFile(fileobj=stream) if descriptor["mediaType"].endswith("gzip") else stream
            byte_count = 0
            with expanded:
                while chunk := expanded.read(1024 * 1024):
                    byte_count += len(chunk)
                    assert byte_count < 300_000_000
            layer_rows.append({"digest": descriptor["digest"], "compressedBytes": member.size,
                               "uncompressedTarBytes": byte_count})
    save("image-input.json", {"archiveSHA256": sha(archive), "archiveBytes": archive.stat().st_size,
                              "manifest": MANIFEST, "layers": layer_rows,
                              "imageExecuted": False, "imagePulled": False})
    env = {"PATH": "/usr/bin:/bin", "HOME": str(WORK / "home"),
           "DOCKER_CONFIG": str(WORK / "docker-config"), "TMPDIR": str(WORK / "tmp"),
           "XDG_CACHE_HOME": str(WORK / "cache"), "GOMAXPROCS": "2",
           "GOMEMLIMIT": "512MiB", "LANG": "C", "LC_ALL": "C"}
    synthetic = {"SchemaVersion": 2, "ArtifactName": "redaction-check",
                 "ArtifactType": "container_image", "Metadata": {
                     "ImageConfig": {"config": {"Env": ["REDACTION_SENTINEL_ENV"]}}},
                 "Results": [{"Target": "synthetic-only", "Class": "secret", "Type": "",
                              "Secrets": [{"RuleID": "synthetic-rule", "Category": "synthetic",
                                           "Severity": "HIGH", "StartLine": 1, "EndLine": 1,
                                           "Match": "REDACTION_SENTINEL_MATCH",
                                           "Code": {"Lines": [{"Content": "REDACTION_SENTINEL_CODE"}]}}]}]}
    save("redaction-input.json", synthetic)
    converted = run([str(TOOL), "--config", str(WORK / "empty.yaml"), "convert",
                     "--format", "template", "--template", "@" + str(WORK / "metadata.tpl"),
                     str(WORK / "redaction-input.json")], env=env)
    assert b"REDACTION_SENTINEL" not in converted
    projected = json.loads(converted)
    assert projected[0]["Secrets"][0]["RuleID"] == "synthetic-rule"
    save("redaction-result.json", {"secretMatchOmitted": True, "sourceCodeOmitted": True,
                                   "imageEnvironmentOmitted": True, "findingMetadataPreserved": True})
    command = [str(TOOL), "image", "--input", str(archive), "--platform", "linux/amd64",
               "--config", str(WORK / "empty.yaml"), "--cache-dir", str(WORK / "cache"),
               "--scanners", "secret", "--secret-config", str(WORK / "empty.yaml"),
               "--offline-scan", "--skip-db-update", "--skip-java-db-update",
               "--skip-version-check", "--disable-telemetry", "--ignorefile", str(WORK / "no-ignore"),
               "--timeout", "7m", "--parallel", "2", "--no-progress", "--debug",
               "--format", "template", "--template", "@" + str(WORK / "metadata.tpl"),
               "--output", str(WORK / "results.json")]
    props = ["MemoryMax=1G", "MemorySwapMax=0", "CPUQuota=200%", "TasksMax=64",
             "LimitFSIZE=400M", "RuntimeMaxSec=480", "KillMode=control-group"]
    launch = ["systemd-run", "--user", "--unit", UNIT, "--wait", "--pipe",
              "--working-directory", str(WORK)]
    for prop in props:
        launch += ["--property", prop]
    launch += ["/usr/bin/env", "-i", *[k + "=" + v for k, v in env.items()], *command]
    with (WORK / "scanner.stderr").open("xb") as errors:
        process = subprocess.Popen(launch, stdout=errors, stderr=errors)
        samples = []
        while process.poll() is None:
            show = subprocess.run(["systemctl", "--user", "show", UNIT,
                                  "--property=ControlGroup,MemoryMax,MemorySwapMax,CPUQuotaPerSecUSec,TasksMax,ActiveState"],
                                 capture_output=True, text=True, timeout=10)
            values = dict(line.split("=", 1) for line in show.stdout.splitlines() if "=" in line)
            group = values.get("ControlGroup")
            if group:
                root = Path("/sys/fs/cgroup") / group.lstrip("/")
                sample = {}
                for name in ("memory.max", "memory.swap.max", "cpu.max", "pids.max", "memory.current"):
                    path = root / name
                    if path.exists():
                        sample[name] = path.read_text().strip()
                if sample:
                    samples.append(sample)
            time.sleep(.2)
        code = process.wait()
    save("resources.json", {"launchProperties": props, "kernelSamples": samples, "exit": code})
    assert code == 0, "scanner_failed_not_clean"
    assert samples and all(s.get("memory.max") == "1073741824" and
                           s.get("memory.swap.max") == "0" and s.get("pids.max") == "64" and
                           s.get("cpu.max") == "200000 100000" for s in samples)
    results = json.loads((WORK / "results.json").read_text())
    assert isinstance(results, list)
    errors = (WORK / "scanner.stderr").read_text()
    assert "Secret scanning is enabled" in errors
    result = {"secretScanCompleted": True, "secretFindings": sum(len(r["Secrets"]) for r in results),
              "resultTargets": len(results), "scannerSHA256": TOOL_SHA,
              "image": IMAGE, "databaseUsed": False, "currentVulnerabilityAcceptance": False,
              "sourceSHA256": binding, "sourceUnchanged": sha(Path(__file__)) == binding,
              "indexUnchanged": sha(REPO / ".git/index") == index,
              "reportSHA256": sha(WORK / "results.json"), "kernelSamples": len(samples),
              "productionActivated": False, "next": "fresh advisory DB admission required"}
    save("result.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
