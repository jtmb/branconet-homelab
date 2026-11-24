#!/usr/bin/env python3
"""Seed only the private Pi-hole standby while its DNS process is gated."""

import json
import re
import shlex
import subprocess
import sys
import uuid

SSH = ("ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-p", "2002",
       "james@192.168.0.4")
FILES = ("gravity.db", "pihole.toml", "custom.list")
MARKER = "/etc/pihole/.branconet-primary-seeded-v1"


def command(*args):
    return (*SSH, shlex.join(("kubectl", "-n", "pihole", *args)))


def kube(*args, timeout=20):
    result = subprocess.run(command(*args), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            check=True, timeout=timeout)
    return result.stdout


def pod_for(label):
    objects = json.loads(kube("get", "pods", "-l", f"app={label}", "-o", "json"))["items"]
    if len(objects) != 1 or objects[0]["metadata"].get("deletionTimestamp"):
        raise ValueError(f"Expected one active {label} Pod.")
    return objects[0]


def main():
    primary = pod_for("pihole")
    standby = pod_for("pihole-secondary")
    name = primary["metadata"]["name"]
    target = standby["metadata"]["name"]
    if not all(c["ready"] for c in primary["status"]["containerStatuses"]):
        raise ValueError("Primary DNS is outside its Ready baseline.")
    gate = [c for c in standby["status"].get("initContainerStatuses", [])
            if c["name"] == "await-dns-seed" and c.get("state", {}).get("running")]
    claims = [v["persistentVolumeClaim"]["claimName"] for v in standby["spec"]["volumes"]
              if "persistentVolumeClaim" in v]
    if len(gate) != 1 or claims != ["pihole-secondary-data-1"]:
        raise ValueError("Standby is not gated on its dedicated claim.")
    if primary["spec"]["nodeName"] == standby["spec"]["nodeName"]:
        raise ValueError("Primary and standby were placed on the same node.")

    read_primary = ("exec", name, "-c", "pihole", "--")
    gated = ("exec", target, "-c", "await-dns-seed", "--")
    source_checks = ("sh", "-ec", "cd /etc/pihole; test ! -s gravity.db-journal; "
                     "test ! -s gravity.db-wal; sha256sum -- " + " ".join(FILES))
    checksums = kube(*read_primary, *source_checks).decode().strip()
    lines = checksums.splitlines()
    if len(lines) != len(FILES) or not all(re.fullmatch(r"[0-9a-f]{64}  " + re.escape(name), line)
                                          for line, name in zip(lines, FILES)):
        raise ValueError("Unexpected DNS seed inventory.")

    work = "/etc/pihole/.branconet-dns-seed-" + uuid.uuid4().hex[:12]
    kube(*gated, "sh", "-ec", "test ! -e " + MARKER + '; umask 077; mkdir -- "$1"', "seed", work)
    committed = False
    try:
        with subprocess.Popen(command(*read_primary, "tar", "-C", "/etc/pihole", "-cf", "-", *FILES),
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as producer:
            result = subprocess.run(command("exec", "-i", target, "-c", "await-dns-seed", "--",
                                            "tar", "-C", work, "-xf", "-"),
                                    stdin=producer.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=120)
            if result.returncode or producer.wait(timeout=10):
                raise ValueError("The DNS seed transfer failed.")
        if kube(*read_primary, *source_checks).decode().strip() != checksums:
            raise ValueError("The primary DNS inputs changed during the copy.")
        if pod_for("pihole")["metadata"]["uid"] != primary["metadata"]["uid"] or (
                pod_for("pihole-secondary")["metadata"]["uid"] != standby["metadata"]["uid"]):
            raise ValueError("A DNS Pod was replaced during the transfer.")
        commit = r"""
set -eu
work="$1"
cd "$work"
test "$(sha256sum -- gravity.db pihole.toml custom.list)" = "$2"
test "$(pihole-FTL sqlite3 gravity.db 'PRAGMA quick_check;')" = ok
for name in gravity.db pihole.toml custom.list; do
  if [ -e "/etc/pihole/$name" ]; then
    cmp -- "$name" "/etc/pihole/$name"
  fi
done
for name in gravity.db pihole.toml custom.list; do
  if [ ! -e "/etc/pihole/$name" ]; then mv -- "$name" "/etc/pihole/$name"; fi
done
test "$(cd /etc/pihole; sha256sum -- gravity.db pihole.toml custom.list)" = "$2"
for name in gravity.db pihole.toml custom.list; do
  if [ -f "$work/$name" ]; then rm -- "$work/$name"; fi
done
rmdir -- "$work"
set -C
umask 077
: > /etc/pihole/.branconet-primary-seeded-v1
"""
        kube(*gated, "sh", "-ec", commit, "seed", work, checksums, timeout=60)
        committed = True
    finally:
        if not committed:
            cleanup = r"""
set -eu
case "$1" in /etc/pihole/.branconet-dns-seed-*) ;; *) exit 1;; esac
test -d "$1" && test "$(realpath "$1")" = "$1"
for name in gravity.db pihole.toml custom.list; do
  if [ -f "$1/$name" ]; then rm -- "$1/$name"; fi
done
rmdir -- "$1"
"""
            try:
                kube(*gated, "sh", "-ec", cleanup, "cleanup", work)
            except (OSError, subprocess.SubprocessError):
                print(f"Inspect the seed transaction on the standby: {work}", file=sys.stderr)
    print("Standby configuration and filtering database matched the primary capture.")
    kube("rollout", "status", "deployment/pihole-secondary", "--timeout=100s", timeout=110)
    print("Private Pi-hole standby is Ready.")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        sys.exit(str(error))
    except (OSError, KeyError, subprocess.SubprocessError):
        sys.exit("Standby seeding stopped before DNS admission.")
