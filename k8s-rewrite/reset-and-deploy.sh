#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# reset-and-deploy.sh — Full iteration loop for K8s deploy
#
# Flow:
#  1. Destroy/recreate VM (terraform) or reset (kubeadm reset)
#  2. Run ansible playbook site.yml from scratch
#  3. If it fails, print error summary and exit
#  4. Fix playbook errors, re-run this script
#
# Usage:
#  ./reset-and-deploy.sh                  # uses existing VM
#  LINODE_TOKEN=abc123 ./reset-and-deploy.sh  # terraform destroy+create
# ──────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ANSIBLE_DIR="$SCRIPT_DIR/ansible-playbook"
TF_DIR="$SCRIPT_DIR/terraform"
INVENTORY_FILE="$ANSIBLE_DIR/inventory/production.ini"
PLAYBOOK="$ANSIBLE_DIR/playbooks/site.yml"
SSH_KEY="$HOME/.ssh/cardventory_deploy"
SSH_USER="root"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }

# ──────────────────────────────────────────
# Step 1: Get the VM IP
# ──────────────────────────────────────────

get_vm_ip() {
    grep 'ansible_host=' "$INVENTORY_FILE" | head -1 | sed 's/.*ansible_host=//' | awk '{print $1}'
}

VM_IP=$(get_vm_ip)

# ──────────────────────────────────────────
# Step 2: Destroy & recreate (terraform) or reset existing
# ──────────────────────────────────────────

if [ -f "$TF_DIR/terraform.tfvars" ] && [ -n "${LINODE_TOKEN:-}" ]; then
    log "=== TERRAFORM: Destroy old VM ==="
    cd "$TF_DIR"
    echo "linode_token = \"$LINODE_TOKEN\"" > terraform.auto.tfvars

    terraform init -upgrade
    terraform destroy -auto-approve || true

    log "=== TERRAFORM: Create fresh VM ==="
    terraform apply -auto-approve

    NEW_IP=$(terraform output -raw instance_ip)
    log "New VM IP: $NEW_IP"

    # Update inventory
    sed -i "s/ansible_host=[0-9.]*/ansible_host=$NEW_IP/" "$INVENTORY_FILE"

    # Wait for SSH
    log "Waiting for SSH on $NEW_IP..."
    for i in $(seq 1 30); do
        if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
               -i "$SSH_KEY" "${SSH_USER}@${NEW_IP}" "echo ready" 2>/dev/null; then
            ok "SSH is up"
            break
        fi
        sleep 5
    done

else
    log "=== RESET: kubeadm reset on existing VM ($VM_IP) ==="

    ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "${SSH_USER}@${VM_IP}" bash -s <<'RESET_SCRIPT'
set -e
echo "==> Running kubeadm reset..."
kubeadm reset -f 2>/dev/null || true

echo "==> Cleaning up Kubernetes files..."
rm -rf /etc/kubernetes /root/.kube /var/lib/kubelet /var/lib/etcd \
       /etc/cni/net.d /root/kubeadm-init-output.txt \
       /etc/systemd/system/kubelet.service /var/lib/kubelet/config.yaml
rm -f  /etc/systemd/system/kubelet.service

echo "==> Killing any lingering processes..."
pkill -f kube-apiserver 2>/dev/null || true
pkill -f etcd 2>/dev/null || true
pkill -f kube-controller 2>/dev/null || true
pkill -f kube-scheduler 2>/dev/null || true
pkill -f kubelet 2>/dev/null || true
pkill -f kube-proxy 2>/dev/null || true
pkill -f containerd 2>/dev/null || true
sleep 3

echo "==> Restarting containerd..."
systemctl restart containerd 2>/dev/null || true
sleep 2

echo "==> Clean iptables..."
iptables -F && iptables -t nat -F && iptables -t mangle -F && iptables -X || true
ip link delete cni0 2>/dev/null || true
ip link delete flannel.1 2>/dev/null || true

echo "==> Removing CNI configs..."
rm -rf /etc/cni/net.d/*

echo "==> Pruning containers..."
crictl rm --all 2>/dev/null || true
crictl stopp 2>/dev/null || true

echo "==> RESET COMPLETE =="
RESET_SCRIPT

    ok "VM reset complete"
fi

# ──────────────────────────────────────────
# Step 3: Run the ansible playbook
# ──────────────────────────────────────────

log "=== ANSIBLE: Running site.yml ==="
cd "$ANSIBLE_DIR"

set +e  # don't exit on ansible failure — we want to see the recap
ansible-playbook \
    -i "$INVENTORY_FILE" \
    "$PLAYBOOK" \
    -u "$SSH_USER" \
    --private-key "$SSH_KEY" \
    2>&1 | tee /tmp/k8s-deploy-output.txt
ANSIBLE_EXIT=$?
set -e

# ──────────────────────────────────────────
# Step 4: Show results
# ──────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $ANSIBLE_EXIT -eq 0 ]; then
    ok "PLAYBOOK COMPLETED SUCCESSFULLY! 🎉"
    echo ""
    grep "PLAY RECAP" /tmp/k8s-deploy-output.txt -A 10 || true
else
    err "PLAYBOOK FAILED — fix the errors and re-run this script"

    echo ""
    echo "━━━ ERRORS ━━━"
    grep -E 'fatal:|FAILED|\[ERROR\]|unreachable' /tmp/k8s-deploy-output.txt | tail -20 || true

    echo ""
    echo "━━━ PLAY RECAP ━━━"
    grep "PLAY RECAP" /tmp/k8s-deploy-output.txt -A 10 || true
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exit $ANSIBLE_EXIT
