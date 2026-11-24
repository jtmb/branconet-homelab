#!/usr/bin/env bash
set -euo pipefail

# Provision SSH keys on u1, u2, u3 — password-authenticated servers.
# Usage: ./provision-ssh-keys.sh
# Prompts for the password once, then copies ~/.ssh/id_ed25519.pub to all 3.

# ── Configuration ────────────────────────────────────────────────────────────
declare -A SERVERS=(
  [u1]="192.168.0.25"
  [u2]="192.168.0.27"
  [u3]="192.168.0.26"
)
USERNAME="${SSH_USER:-brajam}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519.pub}"

# ── Pre-flight ───────────────────────────────────────────────────────────────
if [[ ! -f "$SSH_KEY" ]]; then
  echo "ERROR: SSH public key not found at $SSH_KEY"
  exit 1
fi

if ! command -v sshpass &>/dev/null; then
  echo "sshpass is not installed. Installing…"
  sudo apt-get update -qq && sudo apt-get install -y sshpass
fi

# ── Get password securely (once) ─────────────────────────────────────────────
read -rsp "Enter SSH password for all servers: " SSHPASS
echo
export SSHPASS

SSHPASS_WRAPPER=$(command -v sshpass)

# ── Provision each server ────────────────────────────────────────────────────
FAILED=()
for NAME in u1 u2 u3; do
  IP="${SERVERS[$NAME]}"
  echo -n "[$NAME] $IP — "

  if "$SSHPASS_WRAPPER" -e ssh -o StrictHostKeyChecking=accept-new \
       -o ConnectTimeout=5 "$USERNAME@$IP" \
       "grep -qF '$(awk '{print $1" "$2}' "$SSH_KEY")' ~/.ssh/authorized_keys 2>/dev/null" 2>/dev/null; then
    echo "key already present (skipped)"
  elif "$SSHPASS_WRAPPER" -e ssh-copy-id -o StrictHostKeyChecking=accept-new \
       -o ConnectTimeout=5 -i "${SSH_KEY%.pub}" "$USERNAME@$IP" >/dev/null 2>&1; then
    echo "provisioned ✓"
  else
    echo "FAILED ✗"
    FAILED+=("$NAME")
  fi
done

# ── Cleanup ──────────────────────────────────────────────────────────────────
unset SSHPASS

# ── Summary ──────────────────────────────────────────────────────────────────
echo
echo "═══════════════════════════════════════════════"
if [[ ${#FAILED[@]} -eq 0 ]]; then
  echo "All 3 servers provisioned successfully."
else
  echo "FAILED: ${FAILED[*]}"
  exit 1
fi
