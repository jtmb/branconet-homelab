"""Port-selection semantics for the plaintext restriction helper.

Regression test for the 2026-11-18 finding: rules for published Service ports
matched the *translated* pod port at the forward hook, so every profile whose
published port differs from its pod target port was a silent no-op (operator
traffic passed with all rule counters at 0). Published ports are now matched
pre-NAT in a prerouting chain at -110 (before kube-proxy's destination rewrite
in the NAT hook at -100), scoped to the three node IP destinations. Host
listeners keep the historical input-hook text.
"""
import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "plain", Path(__file__).resolve().parents[1] / "plaintext_restriction.py")
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)

# Published Service port -> pod target port, from the live cluster inventory.
TRANSLATED = {
    "vaultwarden": (8096, 80),
    "mealie": (8089, 9000),
    "aplb": (8082, 80),
    "minecraft-website": (8083, 80),
    "ruckus-bot": (8088, 8080),
    "web-apps-local": (8080, 80),
}


class PortMatchTests(unittest.TestCase):
    def test_service_profiles_match_pre_nat_in_prerouting(self):
        for profile, spec in HELPER.PROFILES.items():
            with self.subTest(profile=profile):
                self.assertIn(spec["hook"], ("input", "prerouting"))
                if spec["hook"] == "prerouting":
                    HELPER.select(profile)
                    self.assertIn("hook prerouting priority -110", HELPER.RULES)
                    # Destination scope keeps pod/node egress to other
                    # addresses on the same port untouched.
                    for ip in HELPER.NODE_IPS:
                        self.assertIn(ip, HELPER.RULES)

    def test_input_profile_keeps_its_previous_rule_text(self):
        HELPER.select("core")
        self.assertIn("chain input", HELPER.RULES)
        self.assertIn("type filter hook input priority -10", HELPER.RULES)
        self.assertIn("tcp dport { 32158, 32359, 9090 }", HELPER.RULES)
        self.assertNotIn("ip daddr", HELPER.RULES)

    def test_every_translated_service_is_covered_by_a_prerouting_profile(self):
        prerouting_ports = {p for spec in HELPER.PROFILES.values()
                             if spec["hook"] == "prerouting" for p in spec["ports"]}
        for profile, (published, _) in TRANSLATED.items():
            with self.subTest(profile=profile):
                self.assertIn(published, prerouting_ports,
                              f"{profile} publishes {published}; a prerouting profile must cover it")

    def test_published_port_not_the_translated_pod_port_is_rejected(self):
        # The vaultwarden pod listens on 80; the rule must carry the
        # *published* 8096, never the pod port.
        HELPER.select("vaultwarden")
        rules = HELPER.RULES
        self.assertIn("tcp dport { 8096 }", rules)
        self.assertNotIn("tcp dport { 80 }", rules)

    def test_render_keeps_the_owned_comment_and_apply_output(self):
        for profile in HELPER.PROFILES:
            with self.subTest(profile=profile):
                HELPER.select(profile)
                rules = HELPER.RULES
                self.assertIn(f"table inet {HELPER.TABLE}", rules)
                self.assertIn(f'comment "{HELPER.OWNER}"', rules)
                self.assertIn("restricted-node-ip-ports", rules)

    def test_same_port_profiles_also_move_to_prerouting(self):
        # Untranslated services (3306, 3003, 9617) were effective before and
        # must remain restricted after the hook move.
        HELPER.select("ruckus-db")
        self.assertIn("hook prerouting priority -110", HELPER.RULES)
        self.assertIn("tcp dport { 3306 }", HELPER.RULES)


if __name__ == "__main__":
    unittest.main()
