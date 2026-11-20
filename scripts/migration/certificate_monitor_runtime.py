"""Fixed runtime paths for local H qualification and an unprivileged host service.

The host profile is available only from the root-managed installation, never
as a way to redirect local development output outside the authorized H store.
Credentials are provisioned/refreshed externally; this module never mints them.
"""
import json
import os
from pathlib import Path
import stat

H_ROOT = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files")
HOST_CODE = Path("/usr/local/libexec/bortus-certificate-monitor")
HOST_STATE = Path("/var/lib/bortus-certificate-monitor")
HOST_CONFIG = Path("/etc/bortus-certificate-monitor/kubeconfig.json")
HOST_CA = Path("/etc/bortus-certificate-monitor/cluster-ca.crt")
HOST_TOKEN = Path("/run/bortus-certificate-monitor/token")
HOST_KUBECTL = Path("/usr/local/bin/kubectl")
LOCAL_KUBECTL = Path("/home/brajam/.local/share/branconet-migration/bin/kubectl")
HOST_SOURCES = ("run-certificate-monitor.py", "certificate_monitor.py",
                "certificate_monitor_control.py", "certificate_monitor_process.py",
                "certificate_monitor_runtime.py")


def root_managed_file(path):
    """Reject symlinks and non-root-writable code/config; return metadata only."""
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError("host_file_not_root_managed")
    for parent in path.parents:
        info_parent = parent.lstat()
        if (not stat.S_ISDIR(info_parent.st_mode) or info_parent.st_uid != 0 or
                info_parent.st_mode & 0o022):
            raise ValueError("host_parent_not_root_managed")
    return info


def validate_host_config(value):
    """Exactly one CA-verified VIP/identity; no exec plugin or ambient fallback."""
    expected = {
        "apiVersion": "v1", "kind": "Config",
        "clusters": [{"name": "branconet", "cluster": {
            "server": "https://192.168.0.251:6443", "certificate-authority": str(HOST_CA)}}],
        "users": [{"name": "bortus-certificate-monitor", "user": {"tokenFile": str(HOST_TOKEN)}}],
        "contexts": [{"name": "monitor", "context": {
            "cluster": "branconet", "user": "bortus-certificate-monitor", "namespace": "bortus"}}],
        "current-context": "monitor",
    }
    if value != expected:
        raise ValueError("host_kubeconfig_not_scoped_profile")


def runtime_paths(*, managed_host, script, state_dir, kubectl, environ):
    if not environ.get("KUBECONFIG"):
        raise ValueError("explicit_scoped_kubeconfig_required")
    if managed_host:
        if script.absolute() != HOST_CODE / "run-certificate-monitor.py" or os.geteuid() == 0:
            raise ValueError("unprivileged_managed_installation_required")
        if state_dir.absolute() != HOST_STATE or state_dir.resolve() != HOST_STATE:
            raise ValueError("fixed_host_state_required")
        for name in HOST_SOURCES:
            root_managed_file(HOST_CODE / name)
        if environ["KUBECONFIG"] != str(HOST_CONFIG) or kubectl is not None:
            raise ValueError("fixed_host_credential_and_cli_required")
        config_info = root_managed_file(HOST_CONFIG)
        if config_info.st_size > 16 * 1024:
            raise ValueError("host_config_size_limit")
        validate_host_config(json.loads(HOST_CONFIG.read_text()))
        root_managed_file(HOST_CA)
        token_info = root_managed_file(HOST_TOKEN)
        if not 0 < token_info.st_size <= 16 * 1024 or token_info.st_mode & 0o007:
            raise ValueError("private_external_token_required")
        root_managed_file(HOST_KUBECTL)
        return HOST_STATE, HOST_KUBECTL

    directory = state_dir.resolve()
    if H_ROOT.resolve() not in directory.parents:
        raise ValueError("local_state_must_remain_on_H")
    binary = LOCAL_KUBECTL
    if kubectl is not None:
        # An explicit H fixture CLI allows exercising the real entrypoint without
        # a production identity. It does not alter the managed-host executable.
        binary = kubectl.resolve()
        if H_ROOT.resolve() not in binary.parents or not binary.is_file() or not os.access(binary, os.X_OK):
            raise ValueError("local_fixture_cli_must_be_executable_on_H")
    return directory, binary


def private_state_file(path):
    """Do not follow pre-existing lock/database aliases or open public state."""
    if path.is_symlink():
        raise ValueError("state_file_symlink_refused")
    if path.exists():
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("state_file_not_private")
