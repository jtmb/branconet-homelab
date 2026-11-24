"""Consequential refusal paths for the fixed root-only sender firewall helper."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parents[1]))

SPEC = importlib.util.spec_from_file_location(
    "notification_firewall", Path(__file__).parents[1] / "certificate_notification_firewall.py")
FIREWALL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIREWALL)


class FirewallRefusals(unittest.TestCase):
    def test_watchdog_wrapper_keeps_a_distinct_fixed_host_account_and_cgroup(self):
        spec = importlib.util.spec_from_file_location(
            "watchdog_firewall", Path(__file__).parents[1] / "certificate_watchdog_firewall.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        profile = SimpleNamespace(TABLE=FIREWALL.TABLE, OWNER=FIREWALL.OWNER,
                                  GROUP=FIREWALL.GROUP, RULES=FIREWALL.RULES)
        module.configure(profile)
        self.assertEqual((profile.HOST, profile.ACCOUNT_UID), ("node03", 997))
        self.assertEqual(profile.ACCOUNT, "bortus-certificate-watchdog")
        self.assertEqual(profile.TABLE, "bortus_watchdog_notifications")
        self.assertNotIn("system.slice/bortus-certificate-notifications.service", profile.RULES)
        self.assertIn("system.slice/bortus-certificate-watchdog-notifications.service", profile.RULES)
        self.assertIn("ct original ip daddr 192.168.0.252 ct original proto-dst 443", profile.RULES)

    def test_foreign_table_is_not_adopted_or_deleted(self):
        tables = json.dumps({"nftables": [{"table": {"family": "inet", "name": FIREWALL.TABLE}}]}).encode()
        foreign = f'table inet {FIREWALL.TABLE} {{\n comment "someone else"\n}}\n'.encode()
        with patch.object(FIREWALL, "run", side_effect=[tables, foreign]) as run:
            with self.assertRaisesRegex(ValueError, "ownership_unknown"):
                FIREWALL.current()
        self.assertEqual(len(run.call_args_list), 2)
        self.assertTrue(all("delete" not in c.args[0] for c in run.call_args_list))

    def context(self):
        return (
            patch.object(FIREWALL.os, "geteuid", return_value=0),
            patch.object(FIREWALL.os, "uname", return_value=SimpleNamespace(nodename="node02")),
            patch.object(FIREWALL.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=998)),
        )

    def test_failed_transaction_check_never_applies_or_deletes(self):
        cgroup = MagicMock()
        cgroup.is_dir.return_value = True
        cgroup.is_symlink.return_value = False

        def command(args, data=None):
            if args[0] == "systemctl":
                return (FIREWALL.GROUP + "\n").encode()
            if "--check" in args:
                raise ValueError("firewall_command_failed")
            self.fail("An apply/delete ran after the refused check")

        a, b, c = self.context()
        with a, b, c, patch.object(FIREWALL.sys, "argv", ["helper", "start"]), \
                patch.object(FIREWALL, "CGROUP", cgroup), \
                patch.object(FIREWALL, "current", return_value=True), \
                patch.object(FIREWALL, "run", side_effect=command) as run:
            with self.assertRaisesRegex(ValueError, "command_failed"):
                FIREWALL.main()
        self.assertEqual(len(run.call_args_list), 2)

    def test_live_other_consumer_prevents_stop_cleanup(self):
        cgroup = MagicMock()
        cgroup.exists.return_value = True
        cgroup.__truediv__.return_value.read_text.return_value = "123\n456\n"
        a, b, c = self.context()
        with a, b, c, patch.object(FIREWALL.os, "getpid", return_value=123), \
                patch.object(FIREWALL.sys, "argv", ["helper", "stop"]), \
                patch.object(FIREWALL, "CGROUP", cgroup), \
                patch.object(FIREWALL, "current", return_value=True), \
                patch.object(FIREWALL, "run") as run:
            with self.assertRaisesRegex(ValueError, "consumers_still_present"):
                FIREWALL.main()
        run.assert_not_called()
