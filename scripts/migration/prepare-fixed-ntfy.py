#!/usr/bin/env python3
"""Bounded offline APK derivative, equivalent to the source Dockerfile recipe.

The shared BuildKit driver has no per-build memory/CPU flags. Use an exact
task-owned constrained install container plus commit, not a new builder/tool.
No production mounts/credentials or registry publication.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time

REPO = Path(__file__).resolve().parents[2]
STAGE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/certificates-qualification-20261116")
WORK = STAGE / "ntfy-zlib-fixed"
NAME = "bortus-ntfy-zlib-fixed-build"
TAG = "bortus-local/ntfy:2.38.1-zlib-1.4-r0"
INPUTS = REPO / "images/private-ntfy-zlib/inputs.json"
ATTEMPT = "initial"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(args, **kwargs):
    return subprocess.check_output(args, stderr=subprocess.PIPE, timeout=90, **kwargs)


def save(name, value):
    if ATTEMPT != "initial" and name != "build-result.json":
        name = name.removesuffix(".json") + "-" + ATTEMPT + ".json"
    with (WORK / name).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def binary_sha(container):
    process = subprocess.Popen(["docker", "cp", container + ":/usr/bin/ntfy", "-"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
        member = archive.next()
        assert member.isfile()
        digest = hashlib.file_digest(archive.extractfile(member), "sha256").hexdigest()
        for _ in archive:
            pass
    assert process.wait(timeout=30) == 0
    return digest


def packages(container):
    data = run(["docker", "cp", container + ":/lib/apk/db/installed", "-"])
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        text = archive.extractfile(archive.getmembers()[0]).read(1024 * 1024).decode()
    result = {}
    for stanza in text.split("\n\n"):
        fields = dict(line.split(":", 1) for line in stanza.splitlines() if ":" in line)
        if "P" in fields:
            result[fields["P"]] = fields["V"]
    return result


def main():
    global ATTEMPT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", choices=("initial", "apk-db-check"), default="initial")
    ATTEMPT = parser.parse_args().attempt
    started_name = "build-started.json" if ATTEMPT == "initial" else "build-started-" + ATTEMPT + ".json"
    assert not (WORK / started_name).exists(), "reconcile_existing_build_not_replay"
    if ATTEMPT != "initial":
        assert (WORK / "build-initial-failure.json").is_file()
    pins = json.loads(INPUTS.read_text())
    package = WORK / pins["package"]
    assert sha(package) == pins["packageSHA256"] and package.stat().st_size == pins["packageBytes"]
    approval = json.loads((STAGE / "ntfy-security-vuln-approval.json").read_text())
    assert approval["approved"] and approval["stageCeilingBytes"] == 4_250_000_000
    publisher = Path(json.loads((STAGE / "credential-bootstrap-publisher-result.json").read_text())["stage"])
    used = sum(int(run(["du", "-sx", "-B1", str(p)]).split()[0]) for p in (STAGE, publisher))
    assert used + 1_773_903_872 + 1_000_000_000 + 50_000_000 < 4_250_000_000
    assert Path("/sys/fs/ext4/loop0/errors_count").read_text().strip() == "0"
    assert not run(["docker", "ps", "-aq", "--filter", "name=^/" + NAME + "$"]).strip()
    assert subprocess.run(["docker", "image", "inspect", TAG], capture_output=True).returncode != 0
    index = sha(REPO / ".git/index")
    paths = [Path(__file__), INPUTS, INPUTS.with_name("Dockerfile"), INPUTS.with_name(".dockerignore")]
    source = {str(p): sha(p) for p in paths}
    existed = subprocess.run(["docker", "image", "inspect", pins["baseImage"]],
                             capture_output=True).returncode == 0
    save("build-started.json", {"sourceSHA256": source, "indexSHA256": index,
                              "baseImage": pins["baseImage"], "baseAlreadyPresent": existed,
                              "packageSHA256": pins["packageSHA256"], "tag": TAG,
                              "method": "Resource-bounded offline install container and commit, not shared BuildKit execution",
                              "reservedPeakBytes": used + 1_773_903_872 + 1_000_000_000 + 50_000_000,
                              "productionConnected": False})
    if not existed:
        # New fixed-candidate input acquisition, not replay of the old scan.
        run(["docker", "pull", "--platform", "linux/amd64", pins["baseImage"]])
    inspect = json.loads(run(["docker", "image", "inspect", pins["baseImage"]]))[0]
    assert inspect["Descriptor"]["digest"] == pins["baseImage"].split("@")[1]
    install = (
        "set -eu\n"
        f"echo '{pins['packageSHA256']}  /tmp/zlib-fixed.apk' | sha256sum -c -\n"
        "apk verify /tmp/zlib-fixed.apk\n"
        "apk --repositories-file /dev/null add --no-cache --no-network /tmp/zlib-fixed.apk\n"
        "rm /tmp/zlib-fixed.apk\n")
    created = run(["docker", "create", "--name", NAME, "--label", "bortus.task=ntfy-fixed-candidate",
                   "--pull=never", "--network", "none", "--user", "0:0",
                   "--cpus", "2", "--memory", "1g", "--memory-swap", "1g", "--pids-limit", "64",
                   "--cap-drop", "ALL", "--cap-add", "CHOWN", "--cap-add", "FOWNER", "--cap-add", "DAC_OVERRIDE",
                   "--security-opt", "no-new-privileges", "--log-opt", "max-size=256k",
                   "--log-opt", "max-file=1", "--entrypoint", "/bin/sh", pins["baseImage"], "-ec", install]).decode().strip()
    save("build-container.json", {"id": created, "name": NAME, "base": pins["baseImage"]})
    before = binary_sha(created)
    before_packages = packages(created)
    run(["docker", "cp", str(package), created + ":/tmp/zlib-fixed.apk"])
    completed = False
    try:
        log_name = "install.log" if ATTEMPT == "initial" else "install-" + ATTEMPT + ".log"
        with (WORK / log_name).open("xb") as output:
            process = subprocess.Popen(["docker", "start", "-a", created], stdout=output, stderr=subprocess.STDOUT)
            samples = []
            while process.poll() is None:
                state = json.loads(run(["docker", "inspect", created]))[0]
                pid = state["State"]["Pid"]
                if pid:
                    try:
                        membership = Path(f"/proc/{pid}/cgroup").read_text().split("::", 1)[1].strip()
                        group = Path("/sys/fs/cgroup") / membership.lstrip("/")
                        if (group / "memory.max").exists():
                            samples.append({name: (group / name).read_text().strip()
                                            for name in ("memory.max", "memory.swap.max", "cpu.max", "pids.max")})
                    except (FileNotFoundError, ProcessLookupError):
                        pass
                time.sleep(.1)
            assert process.wait(timeout=15) == 0
        state = json.loads(run(["docker", "inspect", created]))[0]
        assert state["State"]["ExitCode"] == 0
        assert samples and all(s["memory.max"] == "1073741824" and s["memory.swap.max"] == "0" and
                               s["cpu.max"] == "200000 100000" and s["pids.max"] == "64" for s in samples)
        after = binary_sha(created)
        assert before == after, "ntfy_executable_changed"
        after_packages = packages(created)
        assert set(before_packages) == set(after_packages)
        assert {p for p in before_packages if before_packages[p] != after_packages[p]} == {"zlib"}
        assert after_packages["zlib"] == "1.4-r0"
        delta = run(["docker", "diff", created]).decode().splitlines()
        allowed = {"/etc", "/etc/apk", "/etc/apk/world", "/lib", "/lib/apk", "/lib/apk/db",
                   "/lib/apk/db/installed", "/lib/apk/db/lock", "/lib/apk/db/scripts.tar.gz",
                   "/lib/apk/db/triggers", "/usr", "/usr/lib", "/usr/lib/libz.so.1",
                   "/usr/lib/libz.so.1.3.2", "/usr/lib/libz.so.1.4", "/var", "/var/log",
                   "/var/log/apk.log", "/tmp"}
        assert all(line[2:] in allowed for line in delta), "unexpected_filesystem_delta_requires_review"
        save("install-result.json", {"vendorSignatureVerificationPassed": True,
                                    "zlibVersion": "1.4-r0", "ntfySHA256Before": before, "ntfySHA256After": after,
                                    "kernelSamples": samples, "filesystemDelta": delta,
                                    "onlyPackageVersionChanged": "zlib", "packageCount": len(after_packages)})
        run(["docker", "commit", "--change", "USER 1000:1000", "--change", 'ENTRYPOINT ["ntfy"]',
             "--change", "CMD []", "--change", "LABEL org.bortus.ntfy.zlib=1.4-r0", created, TAG])
        candidate = json.loads(run(["docker", "image", "inspect", TAG]))[0]
        assert candidate["Config"]["User"] == "1000:1000" and candidate["Config"]["Entrypoint"] == ["ntfy"]
        assert not candidate["Config"].get("Cmd")
        image_ref = candidate.get("Descriptor", {}).get("digest") or candidate["Id"]
        archive = WORK / "candidate-image.tar"
        with archive.open("xb") as output:
            subprocess.run(["docker", "image", "save", TAG], stdout=output,
                           stderr=subprocess.PIPE, check=True, timeout=90)
        assert archive.stat().st_size < 200_000_000
        with tarfile.open(archive) as content:
            raw = content.extractfile("blobs/sha256/" + image_ref.split(":")[1]).read()
            assert "sha256:" + hashlib.sha256(raw).hexdigest() == image_ref
            manifest = json.loads(raw)
            for blob in [manifest["config"], *manifest["layers"]]:
                member = content.getmember("blobs/sha256/" + blob["digest"].split(":")[1])
                assert member.size == blob["size"]
                assert "sha256:" + hashlib.file_digest(content.extractfile(member), "sha256").hexdigest() == blob["digest"]
        assert sha(REPO / ".git/index") == index and all(sha(Path(p)) == h for p, h in source.items())
        save("build-result.json", {"built": True, "candidateImage": image_ref,
                                  "candidateManifest": image_ref, "candidateConfig": manifest["config"]["digest"],
                                  "localTag": TAG, "baseImage": pins["baseImage"], "baseConfig": pins["baseConfig"],
                                  "package": pins["package"], "packageSHA256": pins["packageSHA256"],
                                  "zlibVersion": "1.4-r0", "vendorSignatureVerified": True,
                                  "ntfyExecutableUnchanged": True, "ntfySHA256": before,
                                  "defaultUser": "1000:1000", "sourceSHA256": source, "indexUnchanged": True,
                                  "exportPath": str(archive), "exportSHA256": sha(archive), "exportBytes": archive.stat().st_size,
                                  "exportAllBlobsVerified": True, "publishedOrDeployed": False})
        completed = True
    finally:
        state = json.loads(run(["docker", "inspect", created]))[0]
        if state["State"]["Running"]:
            run(["docker", "stop", "--time", "5", created])
        if completed:
            run(["docker", "rm", created])
        else:
            save("build-retained-container.json", {"id": created, "running": False,
                                                  "consumer": "Diagnose unfinished fixed-candidate attempt without replaying installation"})
    print((WORK / "build-result.json").read_text())


if __name__ == "__main__":
    main()
