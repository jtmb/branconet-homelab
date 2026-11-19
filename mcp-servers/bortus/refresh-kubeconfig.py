"""Issue a short-lived token through the existing operator access path."""
import base64
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

SSH = ("ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-p", "2002", "james@192.168.0.4")
NAMESPACE = "flux-system"
ACCOUNT = "kubernetes-mcp-inventory"
DIRECTORY = Path.home() / ".config/branconet-kubernetes-inventory"
DESTINATION = DIRECTORY / "kubeconfig.json"


def read_operator(command):
    return subprocess.check_output((*SSH, command), text=True, timeout=15).strip()


def main():
    DIRECTORY.mkdir(mode=0o700, exist_ok=True)
    directory_info = DIRECTORY.lstat()
    if not stat.S_ISDIR(directory_info.st_mode) or directory_info.st_uid != os.getuid() or directory_info.st_mode & 0o077:
        raise ValueError("The inventory credential directory must be private.")
    if DESTINATION.is_symlink():
        raise ValueError("The inventory kubeconfig may not be a symlink.")

    ca = json.loads(read_operator(f"kubectl -n {NAMESPACE} get configmap kube-root-ca.crt -o json"))["data"]["ca.crt"]
    duration = os.environ.get("BORTUS_INVENTORY_TOKEN_DURATION", "12h")
    token = read_operator(f"kubectl -n {NAMESPACE} create token {ACCOUNT} --duration={duration}")
    if not token or token.count(".") != 2:
        raise ValueError("The API did not issue an inventory token.")
    config = {
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [{"name": "branconet", "cluster": {
            "server": "https://192.168.0.251:6443",
            "certificate-authority-data": base64.b64encode(ca.encode()).decode(),
        }}],
        "users": [{"name": ACCOUNT, "user": {"token": token}}],
        "contexts": [{"name": ACCOUNT, "context": {
            "cluster": "branconet", "user": ACCOUNT, "namespace": NAMESPACE,
        }}],
        "current-context": ACCOUNT,
    }
    pending = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=DIRECTORY, delete=False) as file:
            pending = Path(file.name)
            json.dump(config, file)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(pending, DESTINATION)
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)
    print("Refreshed the private Kubernetes inventory kubeconfig.")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError, OSError, subprocess.SubprocessError):
        raise SystemExit("Kubernetes inventory credential refresh failed.") from None
