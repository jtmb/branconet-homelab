---
{"version":1,"scope":"branconet-homelab","id":"lan-dhcp-allocation","title":"Approved LAN DHCP allocation and rollback","tags":["dhcp","network","rollback"],"kind":"decision","updated":"2026-11-14","verified":"2026-11-14","sources":["docs/MIGRATION-PLAN.md","k8s-rewrite/ansible-playbook/playbooks/lan-dhcp-handoff.yml","k8s-rewrite/ansible-playbook/templates/lan-dhcp.conf.j2"]}
---

The operator approved the freed upper LAN range with `.246` explicitly excluded.
The allocation consists of `.200–.245` and `.247–.250`. Preserve the original five
reservations and gateway, and advertise both existing LAN DNS resolvers.

Only one DHCP server may serve the LAN. Disable and verify router DHCP before
starting the standalone replacement. For rollback, stop and verify the replacement
listener before restoring router DHCP. Verify the actual client lease and queries
to both advertised resolvers. Do not treat a silent address probe as evidence that
an offline device released an address.

Current rollout results and unfinished work belong in the migration plan, rather
than this durable decision note. This note grants no additional authority.
