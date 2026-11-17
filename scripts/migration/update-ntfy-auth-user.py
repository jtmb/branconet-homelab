#!/usr/bin/env python3
"""Safely change one ntfy user's password hash in the private-ntfy-auth Secret.

Guards against the F3 incident (2026-11-17): a hand-edited users value
omitted the required ":role" suffix and crash-looped the server for ~6
minutes. This script validates the "name:hash:role" format before writing,
guards the write with the Secret's resourceVersion, restarts the deployment,
and reverts automatically if the pod does not reach Ready.

Usage:
    python3 -B -I update-ntfy-auth-user.py <username> <password-file>

The password is read from a file (never argv/env) and is never written to
disk, logs, or this script's own output; only the resulting bcrypt hash and
operation outcome are printed.
"""
import base64
import json
import re
import subprocess
import sys
import time
from pathlib import Path

KUBECTL = ["/home/brajam/.local/share/branconet-migration/bin/kubectl",
           "--kubeconfig", "/home/brajam/.local/share/branconet-migration/admin.conf"]
NAMESPACE = "bortus-notifications"
SECRET = "private-ntfy-auth"
DEPLOY = "private-ntfy"
ENTRY_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}:\$2[aby]\$[0-9]{2}\$[A-Za-z0-9./]{53}:(user|admin)$")


def kubectl(*args, input_bytes=None):
    result = subprocess.run(KUBECTL + list(args), capture_output=True, timeout=120, input=input_bytes)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode()[-500:])
    return result.stdout


def get_secret():
    raw = kubectl("get", "secret", SECRET, "-n", NAMESPACE, "-o", "json")
    return json.loads(raw)


def pod_ready():
    raw = kubectl("get", "pods", "-n", NAMESPACE, "-o", "json")
    pods = json.loads(raw)["items"]
    for pod in pods:
        name = pod["metadata"]["name"]
        if not name.startswith(DEPLOY + "-") or "rotation" in name:
            continue
        status = (pod["status"].get("containerStatuses") or [{}])[0]
        if pod["status"].get("phase") == "Running" and status.get("ready"):
            return True, name
    return False, None


def hash_password(password: str) -> str:
    result = subprocess.run(
        KUBECTL + ["-n", NAMESPACE, "exec", "-i", "deploy/" + DEPLOY, "--", "sh", "-c", "ntfy user hash"],
        input=(password + "\n" + password + "\n").encode(), capture_output=True, timeout=60)
    for line in (result.stdout or b"").decode().splitlines():
        line = line.strip()
        if line.startswith("$2"):
            return line
    raise RuntimeError("hash_failed")


def main():
    if len(sys.argv) != 3:
        print("usage: update-ntfy-auth-user.py <username> <password-file>", file=sys.stderr)
        return 2
    username, password_path = sys.argv[1], Path(sys.argv[2])
    password = password_path.read_text().rstrip("\n")
    if not password:
        print("empty password", file=sys.stderr)
        return 2

    before_ready, before_pod = pod_ready()
    if not before_ready:
        print("refusing to change credentials while the pod is not healthy", file=sys.stderr)
        return 1

    secret = get_secret()
    raw = base64.b64decode(secret["data"]["users"]).decode()
    entries = raw.split(",")
    usernames = [e.partition(":")[0] for e in entries]
    if username not in usernames:
        print(f"username {username!r} not found in existing entries", file=sys.stderr)
        return 1

    new_hash = hash_password(password)
    role = next(e.rsplit(":", 1)[1] for e in entries if e.partition(":")[0] == username)
    new_entry = f"{username}:{new_hash}:{role}"
    if not ENTRY_RE.match(new_entry):
        print("new entry failed format validation; aborting without writing", file=sys.stderr)
        return 1

    new_entries = [new_entry if e.partition(":")[0] == username else e for e in entries]
    for e in new_entries:
        if not ENTRY_RE.match(e):
            print(f"refusing to write: existing entry fails format validation: {e.partition(':')[0]}", file=sys.stderr)
            return 1
    new_raw = ",".join(new_entries)

    backup_dir = Path("/tmp/opencode")
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / f"ntfy-users-before-{int(time.time())}.b64"
    backup_path.write_text(secret["data"]["users"])
    backup_path.chmod(0o600)

    patch = {"metadata": {"resourceVersion": secret["metadata"]["resourceVersion"]},
              "data": {"users": base64.b64encode(new_raw.encode()).decode()}}
    kubectl("-n", NAMESPACE, "patch", "secret", SECRET, "--type=merge", "-p", json.dumps(patch))

    kubectl("-n", NAMESPACE, "rollout", "restart", "deploy/" + DEPLOY)
    deadline = time.monotonic() + 180
    ready = False
    while time.monotonic() < deadline:
        ready, _ = pod_ready()
        if ready:
            break
        time.sleep(5)

    if not ready:
        print("new pod did not become ready; reverting users value", file=sys.stderr)
        revert_secret = get_secret()
        revert_patch = {"metadata": {"resourceVersion": revert_secret["metadata"]["resourceVersion"]},
                         "data": {"users": secret["data"]["users"]}}
        kubectl("-n", NAMESPACE, "patch", "secret", SECRET, "--type=merge", "-p", json.dumps(revert_patch))
        kubectl("-n", NAMESPACE, "rollout", "restart", "deploy/" + DEPLOY)
        print(json.dumps({"passed": False, "reverted": True, "backup": str(backup_path)}, indent=2))
        return 1

    print(json.dumps({"passed": True, "username": username, "newHashBcryptPrefix": new_hash[:7],
                        "backup": str(backup_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
