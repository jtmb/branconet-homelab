#!/usr/bin/python3
"""Keep the dedicated Seerr jail attached to the current Traefik CRI logs."""
from pathlib import Path
import re
import subprocess

JAIL = "branconet-traefik-lan"
CONTAINERS = Path("/var/log/containers")
PODS = Path("/var/log/pods")
EMPTY_LOG = "/run/branconet-traefik-ban/fail2ban-empty.log"
LOG_NAME = re.compile(r"(traefik-[a-z0-9]+-[a-z0-9]+)_traefik_traefik-[a-f0-9]{64}\.log")


def fail2ban(*args):
    return subprocess.run(
        ["/usr/bin/fail2ban-client", *args],
        check=True, capture_output=True, text=True, timeout=5,
    ).stdout


def current_logs(directory, pods):
    current = set()
    for path in directory.iterdir():
        name = LOG_NAME.fullmatch(path.name)
        if name is None or not path.is_symlink():
            continue
        try:
            target = path.resolve(strict=True).relative_to(pods)
        except (FileNotFoundError, ValueError):
            continue
        if (len(target.parts) == 3
                and target.parts[0].startswith(f"traefik_{name[1]}_")
                and target.parts[1] == "traefik"
                and re.fullmatch(r"[0-9]+\.log", target.parts[2])
                and path.is_file()):
            current.add(str(path))
    return current


def main():
    output = fail2ban("get", JAIL, "logpath").strip()
    if output == "No file is currently monitored":
        existing = set()
    else:
        lines = output.splitlines()
        if (not lines or lines[0] != "Current monitored log file(s):"
                or any(not line.startswith(("|- ", "`- ")) for line in lines[1:])):
            raise ValueError("Unexpected Fail2Ban log path response.")
        existing = {line[3:] for line in lines[1:]}
    desired = current_logs(CONTAINERS, PODS) | {EMPTY_LOG}
    for path in sorted(desired - existing):
        fail2ban("set", JAIL, "addlogpath", path, "tail")
    for path in sorted(existing - desired):
        if Path(path).parent == CONTAINERS and LOG_NAME.fullmatch(Path(path).name):
            fail2ban("set", JAIL, "dellogpath", path)
    print(f"{len(desired) - 1} live Traefik CRI log(s) monitored.")


if __name__ == "__main__":
    main()
