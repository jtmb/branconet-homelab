#!/usr/bin/env python3
"""Fail-closed same-bookworm maintenance of the pinned FlareSolverr image."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

ROOT = Path("/usr/share/branconet-security/flaresolverr")
BASE = "ghcr.io/flaresolverr/flaresolverr@sha256:c80ae007ce2ccdcd217a12426e4f039ef763ff90738c808d38810c3e59323767"
MINIMUM = "156.0.8078.47"
DRIVER = Path("/app/chromedriver")


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def guard_repository(uri, suites, components):
    value = urlsplit(uri)
    if (value.scheme not in ("http", "https") or value.username or value.password
            or value.port or value.query or value.fragment
            or value.hostname not in ("deb.debian.org", "security.debian.org")
            or value.path.rstrip("/") not in ("/debian", "/debian-security")
            or not suites or not set(suites) <= {"bookworm", "bookworm-updates", "bookworm-security"}
            or components != ["main"]):
        raise RuntimeError("Repository is outside the existing Debian 12 main/security track")
    if ("bookworm-security" in suites) != (value.path.rstrip("/") == "/debian-security"):
        raise RuntimeError("Security suite/repository mismatch")


def guard_sources():
    paths = [Path("/etc/apt/sources.list")]
    paths += sorted(Path("/etc/apt/sources.list.d").glob("*.list"))
    paths += sorted(Path("/etc/apt/sources.list.d").glob("*.sources"))
    active = 0
    sources = {}
    for path in paths:
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("Unexpected APT source file type")
        text = path.read_text()
        sources[str(path)] = {"sha256": digest(path), "content": text}
        if path.suffix == ".sources":
            for paragraph in re.split(r"\n\s*\n", text.strip()):
                fields = {}
                for line in paragraph.splitlines():
                    if not line.strip() or line.lstrip().startswith("#"):
                        continue
                    if line[0].isspace() or ":" not in line:
                        raise RuntimeError("Unexpected folded APT source field")
                    key, value = line.split(":", 1)
                    if key in fields:
                        raise RuntimeError("Duplicate APT source field")
                    fields[key] = value.strip()
                if not fields or fields.get("Enabled", "yes") == "no":
                    continue
                if (fields.get("Types") != "deb" or fields.get("Enabled", "yes") != "yes"
                        or set(fields) - {"Types", "URIs", "Suites", "Components", "Signed-By", "Enabled"}
                        or fields.get("Signed-By") != "/usr/share/keyrings/debian-archive-keyring.gpg"):
                    raise RuntimeError("Unexpected APT source options")
                for uri in fields.get("URIs", "").split():
                    guard_repository(uri, fields.get("Suites", "").split(), fields.get("Components", "").split())
                    active += 1
        else:
            for line in text.splitlines():
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) != 4 or parts[0] != "deb":
                    raise RuntimeError("Unexpected legacy APT source options")
                guard_repository(parts[1], [parts[2]], [parts[3]])
                active += 1
    if not active:
        raise RuntimeError("No accepted Debian repository")
    return sources


def protected_files():
    result = {}
    # /app/chromedriver is intentionally replaced from the upgraded package.
    # Everything else in the vendor application and /usr/local Python is frozen.
    for root in (Path("/app"), Path("/usr/local"), Path("/package.json")):
        if not root.exists() or root.is_symlink():
            raise RuntimeError("Missing or unexpected vendor application root")
        paths = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in paths:
            if path == DRIVER:
                continue
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                continue
            item = {"mode": stat.S_IMODE(info.st_mode), "uid": info.st_uid, "gid": info.st_gid}
            if stat.S_ISLNK(info.st_mode):
                item["symlink"] = os.readlink(path)
            elif stat.S_ISREG(info.st_mode):
                item["sha256"] = digest(path)
            else:
                raise RuntimeError("Unexpected vendor application file type")
            result[str(path)] = item
    return result


def packages():
    return command("dpkg-query", "-W", "-f=${binary:Package}\t${Version}\n").splitlines()


def main():
    if sys.argv[1:] not in (["before"], ["after"]):
        raise RuntimeError("Expected before or after")
    phase = sys.argv[1]
    release = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
    if release.get("ID", "").strip('"') != "debian" or release.get("VERSION_ID", "").strip('"') != "12":
        raise RuntimeError("Expected immutable Debian 12 base")
    if command("dpkg", "--print-architecture") != "amd64":
        raise RuntimeError("Only the reviewed linux/amd64 image is supported")
    sources = guard_sources()
    if phase == "before":
        ROOT.mkdir(parents=True, exist_ok=True)
        if (ROOT / "before.json").exists():
            raise RuntimeError("Refusing to replace original maintenance evidence")
        driver = DRIVER.lstat()
        if not stat.S_ISREG(driver.st_mode) or stat.S_IMODE(driver.st_mode) != 0o755:
            raise RuntimeError("Unexpected vendor driver file")
        write("before.json", {"base": BASE, "sources": sources, "packages": packages(),
              "protectedFiles": protected_files(), "driver": {"sha256": digest(DRIVER),
              "mode": stat.S_IMODE(driver.st_mode), "uid": driver.st_uid, "gid": driver.st_gid}})
        return
    before = json.loads((ROOT / "before.json").read_text())
    if before["sources"] != sources or before["protectedFiles"] != protected_files():
        raise RuntimeError("APT sources or frozen vendor/Python files changed")
    versions = {name: command("dpkg-query", "-W", "-f=${Version}", name)
                for name in ("chromium", "chromium-common", "chromium-driver")}
    if len(set(versions.values())) != 1:
        raise RuntimeError("Browser/common/driver package versions differ")
    version = versions["chromium"]
    subprocess.run(["dpkg", "--compare-versions", version, "ge", MINIMUM], check=True)
    installed = Path("/usr/bin/chromedriver")
    if not stat.S_ISREG(installed.lstat().st_mode) or not stat.S_ISREG(DRIVER.lstat().st_mode):
        raise RuntimeError("Unexpected upgraded/vendor driver file type")
    # The vendor relocated the original driver. Refresh that exact application
    # path, retaining its original ownership/mode and no other application file.
    fd, temporary = tempfile.mkstemp(prefix=".chromedriver-security-", dir=DRIVER.parent)
    try:
        with os.fdopen(fd, "wb") as target, installed.open("rb") as source:
            shutil.copyfileobj(source, target)
        os.chmod(temporary, before["driver"]["mode"])
        os.chown(temporary, before["driver"]["uid"], before["driver"]["gid"])
        os.replace(temporary, DRIVER)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)
    browser = command("/usr/bin/chromium", "--version")
    driver = command(str(DRIVER), "--version")
    browser_version = re.search(r"\b(\d+\.\d+\.\d+\.\d+)\b", browser)
    driver_version = re.search(r"\b(\d+\.\d+\.\d+\.\d+)\b", driver)
    if (not browser_version or not driver_version
            or browser_version[1] != driver_version[1]
            or version.split("-", 1)[0].split(":")[-1] != browser_version[1]
            or digest(DRIVER) != digest(installed)):
        raise RuntimeError("Actual browser and relocated driver do not match upgraded packages")
    if before["protectedFiles"] != protected_files():
        raise RuntimeError("Frozen vendor/Python files changed during verification")
    write("after.json", {"base": BASE, "packages": packages(), "versions": versions,
          "browser": browser, "driver": driver, "driverSHA256": digest(DRIVER),
          "protectedFiles": protected_files(), "protectedFilesUnchanged": True,
          "pythonDependenciesChanged": False})


if __name__ == "__main__":
    main()
