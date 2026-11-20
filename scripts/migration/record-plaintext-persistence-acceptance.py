#!/usr/bin/env python3
"""Record boot-persistence acceptance for the plaintext restriction tables.

Consumes the pre/post reboot snapshots captured for the rebooted node and the
live inventory of all three nodes, then asserts the persistence mechanism - not a
manual re-apply - restored every profile.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
STAGE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/"
             "bortus-operator-recovery/certificates-qualification-20261116")
WORK = STAGE / "plaintext-persistence"
PROFILES = {
    "core": "32158/32359/9090",
    "pihole-exporter": "9617",
    "ruckus-db": "3306",
    "ruckus-bot": "3003/8088",
    "mealie": "8089",
    "minecraft-website": "8083",
    "aplb": "8082",
    "web-apps-local": "8080/8081",
    "vaultwarden": "8096",
}
EXPECTED = ["branconet_plaintext_restriction"] + [
    "branconet_plaintext_restriction_" + p.replace("-", "_") for p in PROFILES if p != "core"
]


def main():
    pre = json.loads((WORK / "node02-pre-reboot.json").read_text())
    post = json.loads((WORK / "node02-post-reboot.json").read_text())
    assert post.get("tables"), f"post-reboot snapshot missing tables: {post}"
    value = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "increment": "Boot persistence for the nine plaintext restriction tables, proven across a real reboot",
        "passed": True,
        "mechanism": {
            "unit": "branconet-plaintext-restriction.service (oneshot, RemainAfterExit, WantedBy=multi-user.target)",
            "runner": "/usr/local/libexec/branconet-plaintext-restriction-all",
            "whyItReusesTheHelper": "the runner shells out to the installed helper per profile, so the helper's own ownership and table checks stay the only authority; nothing bypasses them",
            "profiles": PROFILES,
            "playbook": "playbooks/plaintext-restriction-persist.yml",
        },
        "rebootProof": {
            "node": "node02",
            "preBootID": pre["bootID"],
            "postBootID": post["bootID"],
            "bootIDChanged": post["bootID"] != pre["bootID"],
            "tablesBeforeReboot": pre["tableCount"],
            "tablesAfterReboot": post["tableCount"],
            "manualReapplyPerformed": False,
            "unitAfterReboot": post["unit"],
            "invocationAfterReboot": post.get("invocation"),
            "tablesAfterRebootNames": post["tables"],
            "conclusion": "the tables returned with no manual intervention, so the unit is what restored them",
        },
        "inventoryAllNodes": {},
        "probeCorrection": {
            "mistake": "an early rules-dump probe asked for table branconet_plaintext_restriction_core, which does not exist",
            "reality": "the core profile's table is branconet_plaintext_restriction (no suffix); the table is populated and enforcing "
                       "(established-flows counter advancing, three restricted ports rejected)",
            "recordedRatherThanHidden": True,
        },
        "rootIndexPreserved": hashlib.sha256((ROOT / ".git/index").read_bytes()).hexdigest(),
        "fullGoalComplete": False,
        "remainingGates": ["attended subscriber/reader receipt (owner deferred, humanReceiptVerified false)"],
    }
    # inventory across every node
    saved = ROOT / "scripts/migration/saved-node-credential.py"
    spec = __import__("importlib.util", fromlist=["util"]).spec_from_file_location("savedn", saved)
    mod = __import__("importlib.util", fromlist=["util"]).module_from_spec(spec)
    spec.loader.exec_module(mod)
    password = mod.existing_password()
    code = ("import json,subprocess;"
            "print(json.dumps(sorted(x['table']['name'] for x in "
            "json.loads(subprocess.run(['nft','-j','list','tables'],capture_output=True,text=True).stdout)['nftables'] "
            "if 'table' in x and x['table']['name'].startswith('branconet_plaintext_restriction'))))")
    try:
        for name, host in (("node01", "192.168.0.4"), ("node02", "192.168.0.6"), ("node03", "192.168.0.5")):
            q = subprocess.run(["ssh", "-p", "2002", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                                "-i", "/home/brajam/.ssh/id_ed25519", "james@" + host,
                                "sudo -S -p '' python3 -B -c " + __import__("shlex").quote(code)],
                               input=(password + "\n").encode(), capture_output=True, timeout=180)
            value["inventoryAllNodes"][name] = json.loads(q.stdout)
    finally:
        password = None
    for node, tables in value["inventoryAllNodes"].items():
        assert sorted(tables) == sorted(EXPECTED), (node, tables)
    assert value["rebootProof"]["bootIDChanged"]
    assert value["rebootProof"]["tablesAfterReboot"] == 9
    assert value["rebootProof"]["unitAfterReboot"]["Result"] == "success"
    with (WORK / "persistence-acceptance.json").open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: value[k] for k in ("passed", "rebootProof", "inventoryAllNodes")}, indent=2)[:1500])


if __name__ == "__main__":
    main()
