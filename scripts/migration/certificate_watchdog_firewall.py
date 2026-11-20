#!/usr/bin/python3
"""Fixed node03-only notifier policy wrapper; no dynamic CLI destination/profile."""
import importlib.util
import json
from pathlib import Path

from certificate_monitor_runtime import root_managed_file

CODE = Path("/usr/local/libexec/bortus-certificate-watchdog")


def configure(module):
    original_table, original_owner, original_group = module.TABLE, module.OWNER, module.GROUP
    module.TABLE = "bortus_watchdog_notifications"
    module.OWNER = "bortus watchdog notifications v1"
    module.UNIT = "bortus-certificate-watchdog-notifications.service"
    module.GROUP = "/system.slice/" + module.UNIT
    module.CGROUP = Path("/sys/fs/cgroup") / module.GROUP.lstrip("/")
    module.HOST, module.ACCOUNT, module.ACCOUNT_UID = "node03", "bortus-certificate-watchdog", 997
    module.RULES = module.RULES.replace(original_table, module.TABLE).replace(
        original_owner, module.OWNER).replace(original_group.lstrip("/"), module.GROUP.lstrip("/"))
    return module


def main():
    if Path(__file__).absolute() != CODE / Path(__file__).name:
        raise ValueError("fixed_watchdog_firewall_installation_required")
    for name in (Path(__file__).name, "certificate_notification_firewall.py", "certificate_monitor_runtime.py"):
        root_managed_file(CODE / name)
    spec = importlib.util.spec_from_file_location("watchdog_fixed_firewall",
                                                CODE / "certificate_notification_firewall.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    configure(module).main()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"state": "watchdog-firewall-unavailable",
                          "reason": "fixed_watchdog_policy_unavailable"}))
        raise SystemExit(1)
