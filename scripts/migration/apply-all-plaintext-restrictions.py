#!/usr/bin/python3
"""Re-apply every reviewed plaintext-restriction profile at boot.

Runs the installed helper once per profile so the helper's own ownership and
table checks remain the only authority. Idempotent: profiles already present are
deleted and recreated identically. Never widens or reorders unrelated firewall
state, and exits non-zero if any profile cannot be applied.
"""
import json
import subprocess
import sys

HELPER = "/usr/local/libexec/branconet-plaintext-restriction"
PROFILES = ("core", "pihole-exporter", "ruckus-db", "ruckus-bot", "mealie",
            "minecraft-website", "aplb", "web-apps-local", "vaultwarden")


def main():
    applied, failures = [], []
    for profile in PROFILES:
        result = subprocess.run(["/usr/bin/python3", "-B", HELPER, profile, "apply"],
                                capture_output=True, text=True, timeout=60)
        state = None
        try:
            state = json.loads(result.stdout or "{}")
        except ValueError:
            state = {"state": "unparsed", "raw": (result.stdout or "")[:120]}
        if result.returncode == 0 and state.get("state") == "restriction-applied":
            applied.append(profile)
        else:
            failures.append({"profile": profile, "returncode": result.returncode,
                             "result": state, "stderr": (result.stderr or "")[:160]})
    print(json.dumps({"applied": applied, "failures": failures,
                      "profiles": len(PROFILES)}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
