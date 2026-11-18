---
name: node-host-ops
description: Use when running Ansible against node01/node02/node03 (branconet.lan cluster hosts) for anything beyond kubectl - systemd services, host packages, firewall rules, credential brokers. Covers the inventory, SSH port, sudo password handling, and the preflight/apply/remove pattern.
---

# Operating on the cluster hosts directly

## Inventory

`k8s-rewrite/ansible-playbook/inventory/production.ini`:

| Alias | `kubernetes_node_name` | IP | SSH port |
|---|---|---|---|
| masternode | node01 | 192.168.0.4 | 2002 |
| workernode1 | node02 | 192.168.0.6 | 2002 |
| workernode2 | node03 | 192.168.0.5 | 2002 |

`ansible_user=james`, key `~/.ssh/id_ed25519`. Plain `ssh -p 2002 <ip>` as
the `brajam` WSL user will fail — use `ansible`/`ansible-playbook -i
inventory/production.ini` so the inventory vars apply, or pass
`-u james -i ~/.ssh/id_ed25519` explicitly.

## Read-only checks don't need sudo

`ansible ... -m command -a "systemctl is-active X" -e "ansible_become=false"`
works without a password and is enough to confirm current state (is a
service running, is a port listening) before deciding whether a privileged
change is even needed. Always do this first.

## Privileged changes need the sudo password

Playbooks in this repo expect
`ansible_become_password: "{{ lookup('ansible.builtin.env', 'BRANCONET_MIGRATION_SUDO_PASSWORD') }}"`
or an equivalent stdin-supplied value — **never** a hardcoded password or one
embedded in a command line (visible in `ps`/shell history).

**Don't ask James for it.** It is already stored in his vaulted native
Secrets. `scripts/migration/saved-node-credential.py` reads it in memory
(`existing_password()`), and `--check-sudo` confirms it works on all three
nodes without printing it. Pass it to `ansible-playbook` through the process
environment of a small wrapper, or to `sudo -S` on stdin (see
`scripts/migration/qualify-node-csr-rollout.py`). Never write it to a file,
log or chat. (Asking James for it on 2026-11-17 was a mistake; see RULES.md
Rule 1.)

## The hash-guarded play pattern

Every existing privileged play in this repo
(`certificate-monitor-delivery-state.yml`,
`certificate-monitor-tls-expiry.yml`, `csr-controller-host.yml`, etc.)
follows the same shape:

1. `assert` the target host's `kubernetes_node_name` matches what's
   expected — refuse to run against the wrong node.
2. `sha256sum`/`stat.checksum` the **currently installed** file(s) and
   `assert` they equal an explicit pinned "before" hash (or are absent, for
   a genuinely new file). This refuses to silently overwrite content that
   has drifted from what you reviewed.
3. Copy the new file(s) from this repo's `scripts/migration/` (via
   `{{ playbook_dir }}/../../../scripts/migration/...`), explicit
   `owner/group/mode`.
4. Assert the installed content now contains an expected marker (e.g. a
   function name) — confirms the copy actually landed, not just that the
   task reported success.
5. Compile-check (`python3 -B -c "import ast,sys;ast.parse(...)"`) before
   restarting anything.
6. Restart the specific systemd unit, then poll `systemctl is-active` with
   retries until it reports `active` — don't declare success on the restart
   task alone.

Always `--syntax-check` a new play before running it, and prefer
`--check`/a dry run when the play supports one.

## Don't expand scope silently

Standing up a brand-new privileged service (a new systemd unit, a new
credential broker, a new host identity) on an additional node is a
significant infrastructure change, not a routine fix — even under broad
"work autonomously" authorization, flag it as a separate decision rather
than building it as a side effect of an unrelated task. A **read-only check**
of whether existing coverage reaches a given node is always in scope.
