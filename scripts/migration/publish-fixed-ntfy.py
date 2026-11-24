#!/usr/bin/env python3
"""Private immutable transport of retained ntfy; no build/export/deployment."""
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
STAGE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/certificates-qualification-20261116")
WORK = STAGE / "ntfy-zlib-fixed"
MANIFEST = "sha256:e26ace78ff6edc73a78e68ef96d8282b4ac80415623671dcee5c9edd764a525e"
TAG = "ntfy-2.38.1-zlib-1.4-r0-e26ace78ff6e"
TARGET = "docker.io/jtmb92/bortus:" + TAG


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(name, data):
    with (WORK / name).open("x") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


def main():
    os.umask(0o077)
    assert not (WORK / "publication-started.json").exists(), "reconcile_existing_publication"
    assert json.loads((STAGE / "delivery-authority.json").read_text())["executeSettledPlan"]
    accepted = json.loads((WORK / "fixed-candidate-acceptance.json").read_text())
    build = json.loads((WORK / "build-result.json").read_text())
    assert accepted["localQualificationPassed"] and accepted["vulnerabilities"] == accepted["secrets"] == 0
    assert accepted["candidateManifest"] == build["candidateManifest"] == MANIFEST
    for name, digest in accepted["evidenceSHA256"].items():
        assert sha(STAGE / name) == digest, "qualified_evidence_changed"
    assert sha(Path(build["exportPath"])) == build["exportSHA256"]
    next_update = dt.datetime.fromisoformat(json.loads((WORK / "security/result.json").read_text())[
        "database"]["NextUpdate"].replace("Z", "+00:00"))
    assert dt.datetime.now(dt.timezone.utc) < next_update, "advisory_snapshot_needs_refresh"
    spec = importlib.util.spec_from_file_location(
        "existing_ntfy_registry_transport", Path(__file__).with_name("publish-qualified-bortus-image.py"))
    publisher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(publisher)
    helper = Path(__file__).with_name("windows-docker-credential-bortus.py")
    publisher.verify_private_repository(helper)
    token = publisher.registry_token(helper)
    previous = publisher.document(token, TAG, missing=True)
    assert previous is None or previous["digest"] == MANIFEST, "no_existing_tag_overwrite"
    image = json.loads(publisher.command(["docker", "image", "inspect", MANIFEST]))[0]
    assert image["Descriptor"]["digest"] == MANIFEST and image["Config"]["User"] == "1000:1000"
    assert publisher.command(["docker", "info", "--format", "{{.DockerRootDir}}"]).decode().strip() == str(
        STAGE.parent.parent / "shared-docker-runtime/docker")
    publisher_stage = Path(json.loads((STAGE / "credential-bootstrap-publisher-result.json").read_text())["stage"])
    baseline = sum(int(publisher.command(["du", "-sx", "-B1", str(path)]).split()[0])
                   for path in (STAGE, publisher_stage))
    assert baseline + 1_000_000_000 + 10_000_000 < 4_250_000_000
    lock = (WORK / "publication.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    binding = {str(p): sha(p) for p in (Path(__file__), helper,
               Path(__file__).with_name("publish-qualified-bortus-image.py"))}
    save("publication-started.json", {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(), "manifest": MANIFEST,
        "tag": TARGET, "privateReadback": True, "sourceSHA256": binding,
        "qualificationSHA256": sha(WORK / "fixed-candidate-acceptance.json"),
        "existingExactTag": previous is not None, "retainedBaselineBytes": baseline,
        "imageRebuiltOrExported": False, "productionChanged": False})
    client = WORK / "publication-client"
    result = {"state": "incomplete", "manifest": MANIFEST, "targetTag": TARGET,
              "productionChanged": False, "credentialsPersisted": False}
    try:
        if previous is None:
            assert not client.exists()
            (client / "bin").mkdir(parents=True, mode=0o700)
            (client / "config").mkdir(mode=0o700)
            (client / "tmp").mkdir(mode=0o700)
            windows = publisher.command(["wslpath", "-w", str(helper)]).decode().strip()
            launcher = client / "bin/docker-credential-bortus-windows"
            launcher.write_text("#!/usr/bin/python3\nimport subprocess,sys\n"
                "p=subprocess.run(" + repr([publisher.PYTHON, "-I", "-B", windows]) +
                "+sys.argv[1:],input=sys.stdin.buffer.read(4097),stdout=sys.stdout.buffer,"
                "stderr=subprocess.DEVNULL)\nraise SystemExit(p.returncode)\n")
            launcher.chmod(0o700)
            (client / "config/config.json").write_text('{"credsStore":"bortus-windows"}\n')
            env = {**os.environ, "DOCKER_CONFIG": str(client / "config"),
                   "PATH": str(client / "bin") + ":/usr/local/bin:/usr/bin:/bin",
                   "TMPDIR": str(client / "tmp")}
            publisher.command(["docker", "tag", MANIFEST, TARGET], env=env)
            with (WORK / "private-push.log").open("xb") as log:
                pushed = subprocess.run(["docker", "push", TARGET], env=env,
                                        stdout=log, stderr=subprocess.STDOUT, timeout=600)
            assert pushed.returncode == 0, "private_push_failed_reconcile_remote"
        token = publisher.registry_token(helper)
        remote = publisher.document(token, TAG)
        assert remote["digest"] == MANIFEST, "registry_rewrote_manifest"
        descriptor = remote["value"]
        assert descriptor["config"]["digest"] == build["candidateConfig"]
        config = publisher.document(token, build["candidateConfig"], kind="blobs")
        assert config["digest"] == build["candidateConfig"]
        assert config["value"]["rootfs"]["diff_ids"] == image["RootFS"]["Layers"]
        assert config["value"]["config"]["User"] == "1000:1000"
        blobs = []
        for layer in descriptor["layers"]:
            request = urllib.request.Request(
                "https://registry-1.docker.io/v2/jtmb92/bortus/blobs/" + layer["digest"],
                headers={"Authorization": "Bearer " + token})
            digest, count = hashlib.sha256(), 0
            with urllib.request.urlopen(request, timeout=60) as stream:
                while block := stream.read(1024 * 1024):
                    count += len(block)
                    assert count <= layer["size"]
                    digest.update(block)
            assert count == layer["size"] and "sha256:" + digest.hexdigest() == layer["digest"]
            blobs.append({"digest": layer["digest"], "bytes": count, "fullReadbackVerified": True})
        publisher.verify_private_repository(helper)
        assert all(sha(Path(p)) == h for p, h in binding.items())
        result.update(state="published-private-verified",
                      reference="docker.io/jtmb92/bortus@" + MANIFEST,
                      privateReadback=True, remoteManifestConfigAndAllLayerBytesVerified=True,
                      config=build["candidateConfig"], layers=blobs, sourceSHA256=binding,
                      qualifiedImageUnchanged=True, imageRebuiltOrExported=False)
    except Exception as error:
        result.update(state="failed-reconcile-before-retry", errorType=type(error).__name__)
        raise
    finally:
        if client.exists():
            assert client.resolve().parent == WORK and not client.is_symlink()
            shutil.rmtree(client)
        result["ephemeralCredentialClientRemoved"] = True
        result["at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        save("publication-result.json", result)
        lock.close()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
