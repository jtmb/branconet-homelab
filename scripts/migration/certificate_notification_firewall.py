#!/usr/bin/python3
"""Root-only fixed sender cgroup policy; no credentials, API or address discovery."""
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys

TABLE = "bortus_certificate_notifications"
OWNER = "bortus certificate notifications v1"
GROUP = "/system.slice/bortus-certificate-notifications.service"
CGROUP = Path("/sys/fs/cgroup") / GROUP.lstrip("/")
UNIT = "bortus-certificate-notifications.service"
HOST = "node02"
ACCOUNT = "bortus-certificate-monitor"
ACCOUNT_UID = 998
RULES = f'''table inet {TABLE} {{
 comment "{OWNER}"
 chain output {{
  type filter hook output priority 10; policy accept;
  socket cgroupv2 level 2 "{GROUP.lstrip('/')}" meta nfproto ipv4 meta l4proto tcp ct original ip daddr 192.168.0.252 ct original proto-dst 443 counter accept comment "fixed-original-notification-destination"
  socket cgroupv2 level 2 "{GROUP.lstrip('/')}" counter reject comment "sender-deny-other-ip-egress"
 }}
}}
'''


def run(args, data=None):
    result = subprocess.run(args, input=data, capture_output=True, timeout=10)
    if result.returncode:
        raise ValueError("firewall_command_failed")
    return result.stdout


def current():
    entries = json.loads(run(["nft", "-j", "list", "tables"]))["nftables"]
    if not any(v.get("table", {}).get("family") == "inet" and
               v.get("table", {}).get("name") == TABLE for v in entries):
        return False
    # The installed nft version omits table comments from JSON; inspect only
    # this exact public table, not unrelated firewall rules.
    lines = run(["nft", "-a", "list", "table", "inet", TABLE]).decode().splitlines()
    if not any(line.strip() == f'comment "{OWNER}"' for line in lines):
        raise ValueError("firewall_table_ownership_unknown")
    if not any("fixed-original-notification-destination" in line for line in lines):
        raise ValueError("firewall_rule_ownership_unknown")
    return True


def main():
    if os.geteuid() != 0 or sys.argv[1:] not in (["start"], ["stop"]):
        raise ValueError("root_fixed_action_required")
    if os.uname().nodename != HOST or pwd.getpwnam(ACCOUNT).pw_uid != ACCOUNT_UID:
        raise ValueError("fixed_host_identity_required")
    existing = current()
    if sys.argv[1] == "start":
        if not CGROUP.is_dir() or CGROUP.is_symlink():
            raise ValueError("sender_cgroup_absent")
        group = run(["systemctl", "show", UNIT, "--property=ControlGroup", "--value"]).decode().strip()
        if group != GROUP:
            raise ValueError("sender_cgroup_identity_changed")
        rules = (f"delete table inet {TABLE}\n" if existing else "") + RULES
        run(["nft", "--check", "-f", "-"], rules.encode())
        # nft applies the whole replace transaction atomically. A failed
        # check/apply leaves any prior owned table intact; no fallback allow.
        run(["nft", "-f", "-"], rules.encode())
        if not current():
            raise ValueError("firewall_not_installed")
        print(json.dumps({"state": "fixed-original-destination-enforced"}))
    elif existing:
        # ExecStopPost runs only after the sender/children stop. Never remove
        # protection while an unrelated or surviving worker uses this cgroup.
        pids = {int(v) for v in (CGROUP / "cgroup.procs").read_text().split()} if CGROUP.exists() else set()
        if pids - {os.getpid()}:
            raise ValueError("sender_consumers_still_present")
        run(["nft", "delete", "table", "inet", TABLE])
        print(json.dumps({"state": "ended-sender-policy-removed"}))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"state": "firewall-unavailable",
                          "reason": str(error) if isinstance(error, ValueError) else "firewall_operation_failed"}))
        raise SystemExit(1)
