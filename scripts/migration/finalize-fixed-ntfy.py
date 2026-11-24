#!/usr/bin/env python3
"""Finalize the retained successful offline install without replaying it.

The fast install's kernel sampler missed its process. Preserve that failed
observer; record install HostConfig separately from a deterministic read-only
candidate audit with a start barrier. Never retrospectively claim a sample.
"""
import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time

spec = importlib.util.spec_from_file_location("fixed_builder", Path(__file__).with_name("prepare-fixed-ntfy.py"))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def main():
    w, run, save = b.WORK, b.run, b.save
    assert not (w / "build-result.json").exists()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", choices=("initial", "apk-db-path", "committed-config"), default="initial")
    attempt = parser.parse_args().attempt
    start_name = "finalize-started.json" if attempt == "initial" else "finalize-started-" + attempt + ".json"
    assert not (w / start_name).exists()
    pins = json.loads(b.INPUTS.read_text())
    retained = json.loads((w / "build-retained-container-apk-db-check.json").read_text())["id"]
    info = json.loads(run(["docker", "inspect", retained]))[0]
    assert info["Name"] == "/" + b.NAME and info["Config"]["Labels"]["bortus.task"] == "ntfy-fixed-candidate"
    assert info["State"]["Status"] == "exited" and info["State"]["ExitCode"] == 0
    assert info["Config"]["Image"] == pins["baseImage"] and info["HostConfig"]["NetworkMode"] == "none"
    host = info["HostConfig"]
    assert host["Memory"] == host["MemorySwap"] == 1073741824 and host["NanoCpus"] == 2000000000
    assert host["PidsLimit"] == 64
    log = (w / "install-apk-db-check.log").read_text()
    assert log.count("/tmp/zlib-fixed.apk: OK") == 2 and "1.3.2-r1 -> 1.4-r0" in log
    assert "WARNING" not in log
    paths = [Path(__file__), Path(b.__file__), b.INPUTS, b.INPUTS.with_name("Dockerfile"),
             b.INPUTS.with_name(".dockerignore")]
    binding = {str(p): b.sha(p) for p in paths}
    index = b.sha(b.REPO / ".git/index")
    save(start_name, {"sourceSHA256": binding, "retainedInstallContainer": retained,
                                 "installReplay": False, "originalKernelSampler": "No live sample; observer failed",
                                 "actualInstallHostConfig": {k: host[k] for k in ("Memory", "MemorySwap", "NanoCpus", "PidsLimit", "NetworkMode")}})
    base = None
    audit = None
    try:
        if attempt == "committed-config":
            pending = json.loads((w / "committed-image-pending.json").read_text())
            assert b.sha(w / "install-finalized.json") == pending["installedLayerFinalizedSHA256"]
            installed = json.loads((w / "install-finalized.json").read_text())
            assert installed["vendorSignatureVerified"] and installed["apkHookPayloadsUnchanged"]
            before = installed["ntfyExecutableSHA256Before"]
            assert before == installed["ntfyExecutableSHA256After"]
            candidate = json.loads(run(["docker", "image", "inspect", pending["image"]["id"]]))[0]
            assert candidate["Descriptor"] == pending["image"]["descriptor"]
            assert candidate["RootFS"] == pending["image"]["rootfs"]
        else:
            base = run(["docker", "create", "--pull=never", "--network", "none", "--read-only",
                        "--name", b.NAME + "-base-reader", pins["baseImage"]]).decode().strip()
            before, after = b.binary_sha(base), b.binary_sha(retained)
            assert before == after
            old, new = b.packages(base), b.packages(retained)
            assert set(old) == set(new) and {n for n in old if old[n] != new[n]} == {"zlib"}
            assert new["zlib"] == "1.4-r0"
            delta = run(["docker", "diff", retained]).decode().splitlines()
            script_archives = []
            for container in (base, retained):
                data = run(["docker", "cp", container + ":/lib/apk/db/scripts.tar.gz", "-"])
                with tarfile.open(fileobj=io.BytesIO(data)) as copied:
                    payload = copied.extractfile(copied.getmembers()[0]).read()
                with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as scripts:
                    script_archives.append({m.name: {"sha256": b.hashlib.sha256(scripts.extractfile(m).read()).hexdigest(),
                                                     "mode": m.mode, "uid": m.uid, "gid": m.gid}
                                            for m in scripts if m.isfile()})
            assert script_archives[0] == script_archives[1], "apk_hook_payload_changed"
            allowed = {"/etc", "/etc/apk", "/etc/apk/world", "/lib", "/lib/apk", "/lib/apk/db",
                       "/lib/apk/db/installed", "/lib/apk/db/lock", "/lib/apk/db/scripts.tar.gz",
                       "/lib/apk/db/triggers", "/usr", "/usr/lib", "/usr/lib/libz.so.1",
                       "/usr/lib/libz.so.1.3.2", "/usr/lib/libz.so.1.4", "/var", "/var/log",
                       "/var/log/apk.log", "/tmp"}
            assert all(line[2:] in allowed for line in delta), "unexpected_filesystem_delta_requires_review"
            save("install-finalized.json", {"vendorSignatureVerified": True, "installedZlib": new["zlib"],
                                           "packageCount": len(new), "onlyChangedPackage": "zlib",
                                           "ntfyExecutableSHA256Before": before, "ntfyExecutableSHA256After": after,
                                           "filesystemDelta": delta, "apkHookPayloadsUnchanged": True,
                                           "installKernelSample": "unobserved, not retroactively claimed"})
            run(["docker", "commit", "--change", "USER 1000:1000", "--change", 'ENTRYPOINT ["ntfy"]',
                 "--change", "CMD []", "--change", "LABEL org.bortus.ntfy.zlib=1.4-r0", retained, b.TAG])
            candidate = json.loads(run(["docker", "image", "inspect", b.TAG]))[0]
        assert candidate["Config"]["User"] == "1000:1000" and candidate["Config"]["Entrypoint"] == ["ntfy"]
        assert not candidate["Config"].get("Cmd")
        image_ref = candidate.get("Descriptor", {}).get("digest") or candidate["Id"]
        audit = run(["docker", "create", "-i", "--pull=never", "--name", b.NAME + "-audit",
                     "--label", "bortus.task=ntfy-fixed-candidate", "--network", "none", "--read-only",
                     "--cpus", "2", "--memory", "1g", "--memory-swap", "1g", "--pids-limit", "64",
                     "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--entrypoint", "/bin/sh",
                     image_ref, "-ec", 'read -r release; test "$release" = go; test "$(id -u)" = 1000']).decode().strip()
        process = subprocess.Popen(["docker", "start", "-ai", audit], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        started = time.monotonic()
        while True:
            current = json.loads(run(["docker", "inspect", audit]))[0]
            pid = current["State"]["Pid"]
            if pid:
                membership = Path(f"/proc/{pid}/cgroup").read_text().split("::", 1)[1].strip()
                group = Path("/sys/fs/cgroup") / membership.lstrip("/")
                sample = {name: (group / name).read_text().strip()
                          for name in ("memory.max", "memory.swap.max", "cpu.max", "pids.max")}
                break
            assert time.monotonic() - started < 15
            time.sleep(.05)
        assert sample == {"memory.max": "1073741824", "memory.swap.max": "0",
                          "cpu.max": "200000 100000", "pids.max": "64"}
        process.communicate(input=b"go\n", timeout=15)
        assert process.returncode == 0
        assert json.loads(run(["docker", "inspect", audit]))[0]["State"]["ExitCode"] == 0
        save("candidate-readonly-resource-audit.json", {"passed": True, "kernelLimits": sample,
                                                      "defaultNonrootUser": True, "startBarrier": True,
                                                      "notARetroactiveInstallSample": True})
        archive = w / "candidate-image.tar"
        with archive.open("xb") as output:
            subprocess.run(["docker", "image", "save", b.TAG], stdout=output, stderr=subprocess.PIPE,
                           check=True, timeout=90)
        assert archive.stat().st_size < 200_000_000
        with tarfile.open(archive) as content:
            raw = content.extractfile("blobs/sha256/" + image_ref.split(":")[1]).read()
            assert "sha256:" + b.hashlib.sha256(raw).hexdigest() == image_ref
            manifest = json.loads(raw)
            for blob in [manifest["config"], *manifest["layers"]]:
                member = content.getmember("blobs/sha256/" + blob["digest"].split(":")[1])
                assert member.size == blob["size"]
                assert "sha256:" + b.hashlib.file_digest(content.extractfile(member), "sha256").hexdigest() == blob["digest"]
        assert b.sha(b.REPO / ".git/index") == index and all(b.sha(Path(p)) == h for p, h in binding.items())
        save("build-result.json", {"built": True, "candidateImage": image_ref,
                                  "candidateManifest": image_ref, "candidateConfig": manifest["config"]["digest"],
                                  "localTag": b.TAG, "baseImage": pins["baseImage"], "baseConfig": pins["baseConfig"],
                                  "packageSHA256": pins["packageSHA256"], "zlibVersion": "1.4-r0",
                                  "vendorSignatureVerified": True, "ntfyExecutableUnchanged": True,
                                  "ntfySHA256": before, "defaultUser": "1000:1000", "sourceSHA256": binding,
                                  "indexUnchanged": True, "exportPath": str(archive), "exportSHA256": b.sha(archive),
                                  "exportBytes": archive.stat().st_size, "exportAllBlobsVerified": True,
                                  "publishedOrDeployed": False,
                                  "qualificationLimit": "Install limits configured; deterministic actual read-only candidate kernel audit passed separately"})
        run(["docker", "rm", retained])
    finally:
        for container in [base, audit]:
            if container:
                current = json.loads(run(["docker", "inspect", container]))[0]
                if current["State"]["Running"]:
                    run(["docker", "stop", "--time", "5", container])
                run(["docker", "rm", container])
    print((w / "build-result.json").read_text())


if __name__ == "__main__":
    main()
