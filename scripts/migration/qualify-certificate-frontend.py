#!/usr/bin/env python3
"""Qualify current frontend in place, with one H dependency tree and no image pull.

Requires the specific bounded H qualification-stage authorization recorded in
the migration plan. It does not deploy or grant production credentials. Source
is mounted read-only; empty ignored source directories are mountpoints only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "k8s-rewrite/front-end"
STORE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files")
STAGE = STORE / "bortus-operator-recovery/certificates-qualification-20261116"
IMAGE = "sha256:c4d5523090a817b7aa86d2111241fdd4f66d1e27782b44160e6aa63b357ecb2d"
NAME = "bortus-certificate-qualification"
CEILING = 4_000_000_000
COMMANDS = {
    "install": ["npm", "ci", "--include=dev", "--ignore-scripts", "--no-audit", "--no-fund"],
    "prepare": ["node", "-e",
                "const cp=require('node:child_process');for(const file of "
                "['patch-zod-collections.mjs','patch-minimatch-compat.mjs'])"
                "cp.execFileSync(process.execPath,['scripts/'+file],{stdio:'inherit'});"],
    "generate": ["node", "node_modules/prisma/build/index.js", "generate"],
    "build": ["npm", "run", "build"],
    "lint": ["npm", "run", "lint"],
    "build-serial": ["npm", "run", "build", "--", "--no-lint"],
    "build-context": ["npm", "run", "build", "--", "--no-lint"],
    "fixture": ["node", "tests/certificate-application-fixture.mjs"],
    "typecheck": ["node", "node_modules/typescript/bin/tsc", "--noEmit", "--incremental", "false"],
}


def usage():
    result = subprocess.run(["du", "-sx", "-B1", str(STAGE)], capture_output=True,
                            text=True, check=True, timeout=20)
    return int(result.stdout.split()[0])


def receipt(path, value):
    with path.open("x") as output:
        json.dump(value, output, indent=2)
        output.write("\n")


def source_fingerprint():
    digest = hashlib.sha256()
    files = []
    for name in ["src", "scripts", "tests", "prisma", "native", "runtime", "public"]:
        files.extend(path for path in (SOURCE / name).rglob("*")
                     if path.is_file() and not path.is_symlink())
    files.extend(path for path in SOURCE.iterdir()
                 if path.is_file() and not path.is_symlink() and
                 (path.name in ("package.json", "package-lock.json", "next-env.d.ts") or
                  path.name.startswith(("next.config.", "tsconfig.", "tailwind.config.",
                                        "postcss.config.", "eslint.config."))))
    for path in sorted(files):
        relative = str(path.relative_to(SOURCE))
        data = path.read_bytes()
        digest.update(relative.encode() + b"\0" + hashlib.sha256(data).digest())
    return {"sha256": digest.hexdigest(), "files": len(files)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=COMMANDS)
    parser.add_argument("--attempt", default="", help="Named correction; retain prior step logs/results")
    parser.add_argument("--lint-attempt", default="", help="Matching named lint receipt for build")
    parser.add_argument("--build-attempt", default="", help="Matching named context-build receipt for fixture")
    args = parser.parse_args()
    if any(value and not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", value)
           for value in (args.attempt, args.lint_attempt, args.build_attempt)):
        parser.error("attempt must be a short lowercase path-safe label")
    label = args.step + ("-" + args.attempt if args.attempt else "")
    if Path("/sys/fs/ext4/loop0/errors_count").read_text().strip() != "0":
        raise RuntimeError("shared_store_errors_require_recovery")
    if STAGE.stat().st_uid != os.getuid() or STAGE.stat().st_mode & 0o077:
        raise RuntimeError("private_stage_required")
    if STAGE.stat().st_dev != STORE.stat().st_dev:
        raise RuntimeError("stage_not_on_existing_H_store")
    filesystem = os.statvfs(STAGE)
    if filesystem.f_bavail * filesystem.f_frsize < CEILING + 15 * 1024**3:
        raise RuntimeError("store_free_space_floor")
    subprocess.run(["docker", "image", "inspect", IMAGE], check=True, stdout=subprocess.DEVNULL)
    existing = subprocess.check_output(
        ["docker", "ps", "-a", "--filter", "name=^/" + NAME + "$", "--format", "{{.ID}}"], text=True).strip()
    if existing:
        raise RuntimeError("existing_task_container_requires_reconciliation")
    index_hash = hashlib.sha256((REPO / ".git/index").read_bytes()).hexdigest()
    lock_hash = hashlib.sha256((SOURCE / "package-lock.json").read_bytes()).hexdigest()
    source_binding = source_fingerprint()
    if args.step in ("build-serial", "build-context"):
        lint_label = "lint" + ("-" + args.lint_attempt if args.lint_attempt else "")
        lint = json.loads((STAGE / (lint_label + "-result.json")).read_text())
        if lint["exit"] != 0 or lint["boundedFailure"] or lint["sourceUnchanged"] != source_binding:
            raise RuntimeError("full_matching_source_lint_required_before_serial_build")
    docker_ignore = hashlib.sha256((SOURCE / ".dockerignore").read_bytes()).hexdigest()
    if args.step == "build-context":
        ignore_lines = (SOURCE / ".dockerignore").read_text().splitlines()
        if "tests" not in ignore_lines or any(line.startswith("!tests") for line in ignore_lines):
            raise RuntimeError("tests_not_excluded_by_actual_release_context")
    before = usage()
    # These are substage reserves inside, not additions to, the total ceiling.
    reserve = {"install": 2_400_000_000, "prepare": 30_000_000, "generate": 250_000_000,
               "build": 1_400_000_000, "build-serial": 1_400_000_000, "build-context": 1_400_000_000,
               "lint": 20_000_000, "typecheck": 20_000_000, "fixture": 200_000_000}[args.step]
    if before + reserve > CEILING:
        raise RuntimeError("substage_reserve_not_admitted")
    for directory in ["node_modules", "next", "native", "runtime", "tmp", "npm", "logs", "home", "cache"]:
        (STAGE / directory).mkdir(mode=0o700, exist_ok=True)
    for directory in ["node_modules", ".next"]:
        target = SOURCE / directory
        if target.exists() and (not target.is_dir() or target.is_symlink() or any(target.iterdir())):
            raise RuntimeError("source_mountpoint_not_empty")
        target.mkdir(exist_ok=True)
    build_info = SOURCE / "tsconfig.tsbuildinfo"
    expected = STAGE / "tsconfig.tsbuildinfo"
    if not os.path.lexists(build_info):
        build_info.symlink_to(expected)
    elif not build_info.is_symlink() or build_info.readlink() != expected:
        raise RuntimeError("existing_build_info_not_owned")
    log_path = STAGE / "logs" / (label + ".log")
    result_path = STAGE / (label + "-result.json")
    if log_path.exists() or result_path.exists():
        raise RuntimeError("prior_step_evidence_exists_do_not_repeat")
    cmd = ["docker", "run", "--pull=never", "--rm", "--name", NAME, "--read-only",
           "--user", f"{os.getuid()}:{os.getgid()}", "--cpus", "2", "--memory", "1g",
           "--memory-swap", "1g", "--pids-limit", "256", "--ulimit", "core=0",
           "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--workdir", "/work",
           "--mount", f"type=bind,src={SOURCE},dst=/work,readonly",
           "--mount", f"type=bind,src={STAGE},dst={STAGE}",
           "--mount", f"type=bind,src={STAGE},dst=/artifacts",
           # The pinned compiler deliberately sanitizes TMPDIR. Its standard
           # /tmp path must still land on H without changing compiler inputs.
           "--mount", f"type=bind,src={STAGE / 'tmp'},dst=/tmp"]
    for host, guest in [("node_modules", "node_modules"), ("next", ".next"),
                        ("native", "native"), ("runtime", "runtime")]:
        cmd += ["--mount", f"type=bind,src={STAGE / host},dst=/work/{guest}"]
    for relative in ["native/secret-flat-selector.c", "runtime/direct-account-reader-worker.cjs"]:
        cmd += ["--mount", f"type=bind,src={SOURCE / relative},dst=/work/{relative},readonly"]
    if args.step == "build-context":
        empty_tests = STAGE / "release-excluded-tests"
        empty_tests.mkdir(mode=0o700, exist_ok=True)
        if any(empty_tests.iterdir()):
            raise RuntimeError("release_exclusion_mount_not_empty")
        cmd += ["--mount", f"type=bind,src={empty_tests},dst=/work/tests,readonly"]
    if args.step == "fixture":
        build_label = "build-context" + ("-" + args.build_attempt if args.build_attempt else "")
        build = json.loads((STAGE / (build_label + "-result.json")).read_text())
        if build["exit"] != 0 or build["boundedFailure"] or build["sourceUnchanged"] != source_binding:
            raise RuntimeError("matching_successful_build_required_for_application_fixture")
        cmd += ["--network", "host"]
    environment = {
        "HOME": "/artifacts/home", "TMPDIR": "/artifacts/tmp", "TMP": "/artifacts/tmp",
        "NPM_CONFIG_CACHE": "/artifacts/npm", "NPM_CONFIG_LOGS_DIR": "/artifacts/logs",
        "XDG_CACHE_HOME": "/artifacts/cache", "NEXT_TELEMETRY_DISABLED": "1",
        "DATABASE_URL": "file:/artifacts/synthetic-build.db", "CIRCLE_NODE_TOTAL": "2",
        "BOTRUS_JWT_SECRET": os.urandom(32).hex(),
    }
    if args.step in ("typecheck", "build-serial", "build-context"):
        # Change the per-process heap within the unchanged 1-GiB cgroup. Full
        # ESLint is a required matching-source gate, not waived by --no-lint.
        environment["NODE_OPTIONS"] = "--max-old-space-size=768"
    if args.step == "fixture":
        # Preserve earlier synthetic metadata while reusing the same build.
        fixture_name = "application-fixture" + ("-" + args.attempt if args.attempt else "")
        if (STAGE / fixture_name).exists():
            raise RuntimeError("prior_fixture_state_exists_choose_fresh_attempt")
        environment["BORTUS_CERTIFICATE_FIXTURE_DIR"] = "/artifacts/" + fixture_name
    for key, value in environment.items():
        cmd += ["--env", f"{key}={value}"]
    # Use the image's supported entrypoint; only this fixed source command runs.
    cmd += [IMAGE, *COMMANDS[args.step]]
    receipt(STAGE / (label + "-started.json"),
            {"step": args.step, "attempt": args.attempt, "image": IMAGE, "source": source_binding,
             "lockSHA256": lock_hash, "indexSHA256": index_hash,
             "stageCeilingBytes": CEILING, "productionConnected": False})
    started = time.monotonic()
    peak = before
    bounded_failure = None
    with log_path.open("xb") as log:
        process = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        while process.poll() is None:
            try:
                used = usage()
                peak = max(peak, used)
                if used > CEILING - 64_000_000:
                    bounded_failure = "incremental_stage_ceiling"
                elif time.monotonic() - started > 900:
                    bounded_failure = "qualification_step_timeout"
                elif Path("/sys/fs/ext4/loop0/errors_count").read_text().strip() != "0":
                    bounded_failure = "shared_store_error"
            except (OSError, subprocess.SubprocessError):
                bounded_failure = "stage_observation_failed"
            if bounded_failure:
                # Only stop our exact container after confirming its image.
                checked = subprocess.run(["docker", "inspect", NAME], capture_output=True, text=True, timeout=10)
                if checked.returncode == 0:
                    container = json.loads(checked.stdout)[0]
                    if container["Config"]["Image"] != IMAGE or container["Config"]["WorkingDir"] != "/work":
                        raise RuntimeError("owned_container_identity_changed")
                    subprocess.run(["docker", "stop", "--timeout", "5", NAME], check=True, timeout=15)
                process.terminate()
                break
            time.sleep(2)
        code = process.wait(timeout=20)
    after = usage()
    peak = max(peak, after)
    assert hashlib.sha256((REPO / ".git/index").read_bytes()).hexdigest() == index_hash
    assert hashlib.sha256((SOURCE / "package-lock.json").read_bytes()).hexdigest() == lock_hash
    assert source_fingerprint() == source_binding
    assert hashlib.sha256((SOURCE / ".dockerignore").read_bytes()).hexdigest() == docker_ignore
    result = {"step": args.step, "attempt": args.attempt, "exit": code, "boundedFailure": bounded_failure,
              "wallSeconds": round(time.monotonic() - started, 2), "beforeBytes": before,
              "afterBytes": after, "observedPeakBytes": peak, "stageCeilingBytes": CEILING,
              "image": IMAGE, "sourceReadOnly": True, "lockUnchanged": True,
              "indexUnchanged": True, "sourceUnchanged": source_binding, "productionConnected": False}
    result["releaseContext"] = {"dockerIgnoreSHA256": docker_ignore,
                                "excludedTestsAsInDockerBuild": args.step == "build-context"}
    receipt(result_path, result)
    print(json.dumps(result), flush=True)
    return 0 if code == 0 and not bounded_failure else 1


if __name__ == "__main__":
    raise SystemExit(main())
