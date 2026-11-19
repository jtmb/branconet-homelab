"""Start the shared BORTUS MCP from the private local configuration.

Both Codex and OpenCode point at this one file. It validates that the
local configuration is a private file owned by the caller, renames the
pinned inventory settings, and then replaces itself with ``server.py`` so
no credential or argument is visible in a process list.
"""

import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ALLOWED = {"MCP_BINARY", "MCP_SHA256", "MCP_KUBECONFIG", "BORTUS_RUNNER_SOCKET",
           "BORTUS_SECRETS_KUBECONFIG", "BORTUS_SECRET_SCOPE"}
REQUIRED = {"MCP_BINARY", "MCP_SHA256", "MCP_KUBECONFIG"}
# The inventory token is short-lived by design. Refresh it before starting a
# child so a new session does not inherit an expired credential; if the
# refresh path is unavailable the cached file is used as-is.
MAX_TOKEN_AGE_SECONDS = 30 * 60
REFRESH_HELPER = HERE / "refresh-kubeconfig.py"


def checked(path):
    """Return a private regular file owned by this user, or raise."""
    if not path.is_absolute() or path.is_symlink():
        raise ValueError()
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError()
    if info.st_mode & 0o077:
        raise ValueError()
    return path


def settings():
    """Read and validate the private key/value configuration."""
    source = checked(HERE / ".env")
    if source.stat().st_size > 8192:
        raise ValueError()
    values = {}
    for line in source.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or key in values or key not in ALLOWED:
            raise ValueError()
        values[key] = value
    if not REQUIRED <= set(values):
        raise ValueError()
    enabled = {
        "BORTUS_INVENTORY_BINARY": values["MCP_BINARY"],
        "BORTUS_INVENTORY_SHA256": values["MCP_SHA256"],
        "BORTUS_INVENTORY_KUBECONFIG": values["MCP_KUBECONFIG"],
    }
    if "BORTUS_RUNNER_SOCKET" in values:
        enabled["BORTUS_RUNNER_SOCKET"] = values["BORTUS_RUNNER_SOCKET"]
    for key in ("BORTUS_SECRETS_KUBECONFIG", "BORTUS_SECRET_SCOPE"):
        if key in values:
            enabled[key] = values[key]
    if not Path(enabled["BORTUS_INVENTORY_BINARY"]).is_absolute():
        raise ValueError()
    if not re.fullmatch("[0-9a-f]{64}", enabled["BORTUS_INVENTORY_SHA256"]):
        raise ValueError()
    if not Path(enabled["BORTUS_INVENTORY_KUBECONFIG"]).is_absolute():
        raise ValueError()
    if ("BORTUS_RUNNER_SOCKET" in enabled
            and not Path(enabled["BORTUS_RUNNER_SOCKET"]).is_absolute()):
        raise ValueError()
    return enabled


def refresh_if_stale(kubeconfig):
    """Mint a fresh inventory token when the cached one is old; never fatal.

    stdin is the MCP stream from the client. The helper's ssh would read it
    and forward the client's first request (server/discover) to the remote
    command, so the server never answered it; the helper must get /dev/null.
    """
    try:
        if time.time() - Path(kubeconfig).stat().st_mtime < MAX_TOKEN_AGE_SECONDS:
            return
        if not REFRESH_HELPER.is_file():
            return
        subprocess.run([sys.executable, "-B", str(REFRESH_HELPER)], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
    except (OSError, subprocess.SubprocessError):
        pass


def main():
    """Validate the configuration, then exec the stdio server in place."""
    enabled = settings()
    refresh_if_stale(enabled["BORTUS_INVENTORY_KUBECONFIG"])
    environment = {
        "HOME": str(Path.home()),
        "PATH": "/usr/bin:/bin",
        **enabled,
    }
    os.execve(sys.executable, [sys.executable, "-B", str(HERE / "server.py")],
              environment)


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, ValueError):
        sys.exit("BORTUS MCP refused its local configuration or executable pin.")
