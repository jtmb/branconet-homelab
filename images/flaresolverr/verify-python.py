#!/usr/bin/env python3
"""Separate Python-phase preservation proof; does not rewrite OS-only receipts."""
import email.parser
import importlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

_spec = importlib.util.spec_from_file_location("flaresolverr_os_preservation", Path(__file__).with_name("verify-os.py"))
_os_proof = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_os_proof)
DRIVER, ROOT = _os_proof.DRIVER, _os_proof.ROOT
digest, protected_files = _os_proof.digest, _os_proof.protected_files

OLD = {"certifi": "2026.7.22", "urllib3": "2.7.0", "setuptools": "79.0.1"}
NEW = {"certifi": "2026.10.19", "urllib3": "2.8.0", "setuptools": "83.0.0"}
SITE = Path("/usr/local/lib/python3.11/site-packages")
UC = {
    "/app/undetected_chromedriver/__init__.py": "7c2ebaa66f65b040434d398d2982a9e133e663ee81911c30ab97afbc48a03a44",
    "/app/undetected_chromedriver/patcher.py": "5d993d8bb629576d733b390027d6aa4bbc99293bb5955e6279acb76fc3d4c8ee",
    "/app/flaresolverr.py": "297a018024702e6fd41ab80aca9ac2fe968fe3e28afe5abdc00bc34ca0ceda0f",
}
VENDORS = {
    "jaraco_context": ("6.1.0", "jaraco/context/__init__.py", "6ebd727581a8d57aff3eed5a9ee11d77e42b8d48b3fc46392ffe44e02d372f8c"),
    "wheel": ("0.46.3", "wheel/__init__.py", "53078abe17b84b23fbcc5c83a18a3c04ebb04c0eaadfefd6a4c998d8d34ee787"),
}


def snapshot():
    tree = protected_files()
    # Unlike the OS phase, the relocated, already upgraded driver is now frozen.
    info = DRIVER.stat()
    tree[str(DRIVER)] = {"sha256": digest(DRIVER), "mode": info.st_mode & 0o7777,
                         "uid": info.st_uid, "gid": info.st_gid}
    return tree


def distributions(expected):
    result = {}
    for name, version in expected.items():
        dist = importlib.metadata.distribution(name)
        if dist.version != version or not dist.files:
            raise RuntimeError("Unexpected reviewed distribution/version")
        allowed = {name, name + "-" + version + ".dist-info"}
        if name == "setuptools":
            allowed |= {"_distutils_hack", "pkg_resources", "distutils-precedence.pth"}
        paths = []
        for item in dist.files:
            path = Path(os.path.abspath(dist.locate_file(item)))
            relative = path.relative_to(SITE)
            if relative.parts[0] not in allowed or path.is_symlink():
                raise RuntimeError("Distribution RECORD escaped its exact reviewed roots")
            paths.append(str(path))
        result[name] = {"version": dist.version, "paths": sorted(paths)}
    return result


def imports():
    if sys.version_info[:2] != (3, 11) or Path(sys.executable).resolve() != Path("/usr/local/bin/python").resolve():
        raise RuntimeError("Unexpected vendor Python interpreter")
    for path, expected in UC.items():
        if digest(Path(path)) != expected:
            raise RuntimeError("Reviewed Flare/UC import source changed")
    # Source review: only __main__ starts the server/browser. The vendored UC
    # patcher uses packaging.version, not removed setuptools pkg_resources.
    sys.path.insert(0, "/app")
    loaded = {}
    for name in ("certifi", "urllib3", "requests", "selenium", "undetected_chromedriver", "flaresolverr"):
        module = importlib.import_module(name)
        loaded[name] = str(Path(module.__file__).resolve())
    if loaded["undetected_chromedriver"] != "/app/undetected_chromedriver/__init__.py" or loaded["flaresolverr"] != "/app/flaresolverr.py":
        raise RuntimeError("Unexpected application import resolution")
    for name in ("certifi", "urllib3"):
        if loaded[name] != str(SITE / name / "__init__.py") or importlib.metadata.version(name) != NEW[name]:
            raise RuntimeError("Updated runtime dependency was not imported")
    # Execute the actual fixed vendor modules, not just their metadata.
    importlib.import_module("setuptools")
    vendor = SITE / "setuptools/_vendor"
    for name, (version, code, expected) in VENDORS.items():
        metadata = email.parser.Parser().parsestr((vendor / (name + "-" + version + ".dist-info/METADATA")).read_text())
        if metadata["Version"] != version or digest(vendor / code) != expected:
            raise RuntimeError("Fixed setuptools vendor code/metadata mismatch")
        module = importlib.import_module("setuptools._vendor." + ("jaraco.context" if name == "jaraco_context" else name))
        if Path(module.__file__).resolve() != vendor / code:
            raise RuntimeError("Unexpected fixed vendor import resolution")
    # Parse the actual replaced trust store; no network or certificate bypass.
    import ssl
    import certifi
    context = ssl.create_default_context(cafile=certifi.where())
    if not context.get_ca_certs():
        raise RuntimeError("Updated certifi bundle has no usable CA certificates")
    return {"imports": loaded, "fixedVendorCodeAndImports": True, "trustStoreParsed": True}


def write_once(name, value):
    with (ROOT / name).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main():
    if sys.argv[1:] not in (["before"], ["after"], ["runtime"]):
        raise RuntimeError("Expected before, after or runtime")
    phase = sys.argv[1]
    if phase == "runtime":
        if os.geteuid() == 0:
            raise RuntimeError("Final runtime import check must run as the inherited nonroot user")
        distributions(NEW)
        print(json.dumps({"nonrootImports": imports(), "uid": os.geteuid()}, sort_keys=True))
        return
    if phase == "before":
        os_after = json.loads((ROOT / "after.json").read_text())
        if os_after.get("protectedFilesUnchanged") is not True or os_after.get("pythonDependenciesChanged") is not False:
            raise RuntimeError("Original OS-phase preservation receipt is missing")
        write_once("python-before.json", {"tree": snapshot(), "distributions": distributions(OLD),
                   "osBeforeSHA256": digest(ROOT / "before.json"), "osAfterSHA256": digest(ROOT / "after.json")})
        return
    before = json.loads((ROOT / "python-before.json").read_text())
    for name, key in (("before.json", "osBeforeSHA256"), ("after.json", "osAfterSHA256")):
        if digest(ROOT / name) != before[key]:
            raise RuntimeError("Original OS-phase receipt changed")
    current = distributions(NEW)
    old_paths = {path for dist in before["distributions"].values() for path in dist["paths"]}
    new_paths = {path for dist in current.values() for path in dist["paths"]}
    if any(os.path.lexists(path) for path in old_paths - new_paths):
        raise RuntimeError("Superseded distribution files remain installed")
    allowed = {path for collection in (before["distributions"], current)
               for dist in collection.values() for path in dist["paths"]}
    tree = snapshot()
    if {k: v for k, v in before["tree"].items() if k not in allowed} != {k: v for k, v in tree.items() if k not in allowed}:
        raise RuntimeError("Unreviewed application/interpreter/dependency file changed")
    checks = imports()
    if snapshot() != tree:
        raise RuntimeError("Import checks changed protected files")
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
    write_once("python-after.json", {"osBeforeSHA256": before["osBeforeSHA256"],
               "osAfterSHA256": before["osAfterSHA256"], "pythonBeforeSHA256": digest(ROOT / "python-before.json"),
               "distributions": current, "unrelatedFilesUnchanged": True,
               "applicationAndRelocatedDriverUnchanged": True, "checks": checks})


if __name__ == "__main__":
    main()
