#!/usr/bin/python3
"""Fixed host-input restriction for specific node-IP ports (nft, atomic).

Two hook models, chosen per profile:

* ``input`` (host listeners, e.g. MetalLB health-check ports): the packet is
  delivered locally, never rewritten, so ``tcp dport`` sees the real port.

* ``prerouting`` at priority -110 (published Service ports): kube-proxy
  rewrites the destination to the pod address/port in the NAT hook at
  priority -100, so a filter at the forward/input hook only ever sees the
  *translated* pod port. Matching the *published* port there is a silent
  no-op whenever the two differ (2026-11-18 finding: vaultwarden 8096->80,
  mealie 8089->9000, aplb 8082->80, minecraft-website 8083->80,
  web-apps 8080/8081->80 and ruckus-bot 8088->8080 were all unrestricted
  while their rule counters sat at zero). A prerouting chain at -110 runs
  before that rewrite, so ``tcp dport`` there is the port the client
  originally contacted. Prerouting sees every entering packet, so those
  rules are additionally scoped to the three node IP destinations — pod or
  node egress to any other address on the same port is untouched.

Only each profile's reviewed ports are matched. Everything else keeps its
current policy, so this cannot widen or reorder unrelated host firewall
state. ``nft --check`` (used by the ``check`` action and the deploying
playbook's ``validate``) refuses on kernels lacking ``ct``/hook support
before anything is applied.
"""
import json
import os
import subprocess
import sys

NODE_IPS = ("192.168.0.4", "192.168.0.5", "192.168.0.6")
PROFILES = {
    # host listeners terminate on the node itself -> input hook, real port
    "core": {"ports": (32158, 32359, 9090), "hook": "input"},
    # published Service ports: matched pre-NAT in prerouting (see module doc)
    "pihole-exporter": {"ports": (9617,), "hook": "prerouting"},
    # database port published on every node IP; no LAN client is intended
    "ruckus-db": {"ports": (3306,), "hook": "prerouting"},
    # bot service publishes both its HTTP and secondary port on every node IP
    "ruckus-bot": {"ports": (3003, 8088), "hook": "prerouting"},
    # recipe app; normal access is through the ingress hostname, not node IPs
    "mealie": {"ports": (8089,), "hook": "prerouting"},
    # static marketing site; zero node-IP clients measured over 120s per node
    "minecraft-website": {"ports": (8083,), "hook": "prerouting"},
    # second static site; also zero measured node-IP clients
    "aplb": {"ports": (8082,), "hook": "prerouting"},
    # these two only ever showed node-self polling, and the node IPs stay allowed
    "web-apps-local": {"ports": (8080, 8081), "hook": "prerouting"},
    # credential vault: owner-approved restriction after zero measured node-IP
    # clients; sporadic client sync is accepted as a known trade-off
    "vaultwarden": {"ports": (8096,), "hook": "prerouting"},
}
OWNER_SUFFIX = "v1"
ALLOWED = ("127.0.0.1", "192.168.0.4", "192.168.0.5", "192.168.0.6", "192.168.0.13")
# Forwarded Service traffic reaches the destination node with a pod-network source
# (measured), so in-cluster consumers must be allowed explicitly.
POD_CIDR = "10.244.0.0/16"
# input profiles keep the historical -10; prerouting profiles must run before
# kube-proxy's destination rewrite in the NAT hook at -100.
PROFILE_PRIORITY = {"input": -10, "prerouting": -110}
PROFILE = "core"
TABLE = "branconet_plaintext_restriction"
OWNER = f"branconet plaintext restriction {OWNER_SUFFIX}"
PORTS = PROFILES[PROFILE]["ports"]
HOOK = PROFILES[PROFILE]["hook"]
PRIORITY = PROFILE_PRIORITY[HOOK]


def render():
    restricted = "tcp dport { " + ", ".join(str(p) for p in PORTS) + " }"
    if HOOK == "input":
        # Host listeners: unchanged historical rule text, no address scope.
        return f'''table inet {TABLE} {{
 comment "{OWNER}"
 chain {HOOK} {{
  type filter hook {HOOK} priority {PRIORITY}; policy accept;
  ct state established,related counter accept comment "existing-flows"
  ip saddr {{ {', '.join(ALLOWED)} }} {restricted} counter accept comment "allowed-admin-and-cluster"
  ip saddr {POD_CIDR} {restricted} counter accept comment "allowed-cluster-pods"
  {restricted} counter reject comment "restricted-node-ip-ports"
 }}
}}
'''
    # Published Service ports: pre-NAT matching, scoped to node IP destinations
    # so pod/node egress to other addresses on the same port is untouched.
    nodes = "{ " + ", ".join(NODE_IPS) + " }"
    return f'''table inet {TABLE} {{
 comment "{OWNER}"
 chain {HOOK} {{
  type filter hook {HOOK} priority {PRIORITY}; policy accept;
  ct state established,related counter accept comment "existing-flows"
  ip saddr {{ {', '.join(ALLOWED)} }} ip daddr {nodes} {restricted} counter accept comment "allowed-admin-and-cluster"
  ip saddr {POD_CIDR} ip daddr {nodes} {restricted} counter accept comment "allowed-cluster-pods"
  ip daddr {nodes} {restricted} counter reject comment "restricted-node-ip-ports"
 }}
}}
'''


RULES = render()


def select(profile):
    global PROFILE, TABLE, OWNER, PORTS, HOOK, PRIORITY, RULES
    if profile not in PROFILES:
        raise ValueError("restriction_profile_invalid")
    PROFILE = profile
    TABLE = "branconet_plaintext_restriction" + ("" if profile == "core" else "_" + profile.replace("-", "_"))
    OWNER = f"branconet plaintext restriction {profile} {OWNER_SUFFIX}"
    PORTS = PROFILES[profile]["ports"]
    HOOK = PROFILES[profile]["hook"]
    PRIORITY = PROFILE_PRIORITY[HOOK]
    RULES = render()


def run(args, data=None):
    result = subprocess.run(args, input=data, capture_output=True, timeout=15)
    if result.returncode:
        raise ValueError("firewall_command_failed")
    return result.stdout


def present():
    tables = json.loads(run(["nft", "-j", "list", "tables"]))["nftables"]
    if not any(v.get("table", {}).get("name") == TABLE for v in tables
               if v.get("table", {}).get("family") == "inet"):
        return False
    listing = run(["nft", "-a", "list", "table", "inet", TABLE]).decode()
    if f'comment "{OWNER}"' not in listing or "restricted-node-ip-ports" not in listing:
        raise ValueError("firewall_table_ownership_unknown")
    return True


def main():
    if os.geteuid() != 0 or len(sys.argv) != 3 or sys.argv[2] not in ("check", "apply", "remove"):
        raise ValueError("root_fixed_action_required")
    if os.uname().nodename not in ("node01", "node02", "node03"):
        raise ValueError("fixed_cluster_host_required")
    select(sys.argv[1])
    action = sys.argv[2]
    exists = present()
    if action == "check":
        run(["nft", "--check", "-f", "-"], RULES.encode())
        print(json.dumps({"state": "rules-would-apply", "alreadyPresent": exists}))
        return
    if action == "apply":
        body = (f"delete table inet {TABLE}\n" if exists else "") + RULES
        run(["nft", "--check", "-f", "-"], body.encode())
        run(["nft", "-f", "-"], body.encode())
        if not present():
            raise ValueError("firewall_not_installed")
        print(json.dumps({"state": "restriction-applied", "profile": PROFILE, "hook": HOOK,
                          "priority": PRIORITY, "ports": list(PORTS),
                          "allowedSources": list(ALLOWED), "nodeDestinations": list(NODE_IPS)
                          if HOOK == "prerouting" else None}))
        return
    if not exists:
        print(json.dumps({"state": "restriction-not-present"}))
        return
    run(["nft", "delete", "table", "inet", TABLE])
    print(json.dumps({"state": "restriction-removed"}))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"state": "restriction-unavailable",
                          "reason": str(error) if isinstance(error, ValueError) else "restriction_failed"}))
        raise SystemExit(1)
