# Kubernetes Cluster Setup Playbook

A complete Ansible playbook for deploying a 3-node Kubernetes cluster with Longhorn distributed storage on Ubuntu LTS nodes.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Directory Structure](#directory-structure)
- [Configuration](#configuration)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)

## Overview

This playbook automates the installation of:

| Component | Purpose |
|-----------|---------|
| **Bootstrap** | System packages, containerd runtime, sysctl networking |
| **Kubernetes** | kubeadm, kubelet, kubectl binaries + cluster init/join |
| **Network** | Calico CNI for pod networking |
| **DNS** | CoreDNS for service discovery and DNS resolution |
| **GitOps** | Fleet/FluxCD controller for GitOps management |
| **Storage** | Longhorn distributed block storage |
| **Ingress** | Traefik ingress controller with TLS termination |

## Prerequisites

- Ubuntu 20.04, 22.04, or 24.04 LTS on all nodes
- Ansible 2.9+ installed on control node
- SSH access to all cluster nodes (passwordless recommended)
- At least 16GB RAM per node
- Modern CPU (Intel 10th gen+ / AMD Ryzen 3000+)

## Quick Start

```bash
# From the playbook directory:
cd k8s-rewrite/ansible-playbook

# Run the complete playbook on all nodes:
ansible-playbook playbooks/site.yml -i inventory/production.ini

# Or run specific roles only (using tags):
ansible-playbook playbooks/site.yml -i inventory/production.ini --tags bootstrap,kubernetes
```

## Directory Structure

```
ansible-playbook/
├── README.md                      # This file
├── ansible.cfg                    # Ansible configuration
├── inventory/
│   └── production.ini             # Cluster node inventory (edit with your IPs)
├── group_vars/
│   ├── all.yml                    # Global variables for all environments
│   └── production.yml             # Production-specific overrides
├── playbooks/
│   └── site.yml                   # Main playbook entry point
└── roles/
    ├── bootstrap/                 # System packages, containerd, sysctl
    │   ├── tasks/main.yml
    │   ├── handlers/main.yml
    │   ├── templates/
    │   ├── defaults/main.yml
    │   └── meta/main.yml
    ├── kubernetes/                # kubeadm, kubelet, kubectl + cluster init/join
    │   ├── tasks/main.yml
    │   ├── handlers/main.yml
    │   ├── templates/
    │   ├── defaults/main.yml
    │   └── meta/main.yml
    ├── network/                   # Calico CNI for pod networking
    │   ├── tasks/main.yml
    │   ├── handlers/main.yml
    │   ├── templates/
    │   ├── defaults/main.yml
    │   └── meta/main.yml
    ├── dns/                       # CoreDNS for service discovery
    │   ├── tasks/main.yml
    │   ├── handlers/main.yml
    │   ├── templates/
    │   ├── defaults/main.yml
    │   └── meta/main.yml
    ├── gitops/                    # Fleet/FluxCD GitOps controller
    │   ├── tasks/main.yml
    │   ├── handlers/main.yml
    │   ├── templates/
    │   ├── defaults/main.yml
    │   └── meta/main.yml
    ├── storage/                   # Longhorn distributed block storage
    │   ├── tasks/main.yml
    │   ├── handlers/main.yml
    │   ├── templates/
    │   ├── defaults/main.yml
    │   └── meta/main.yml
    └── ingress/                   # Traefik ingress controller
        ├── tasks/main.yml
        ├── handlers/main.yml
        ├── templates/
        ├── defaults/main.yml
        └── meta/main.yml
```

## Configuration

Edit `group_vars/all.yml` to customize your cluster:

```yaml
# Kubernetes Version Settings
k8s_version: "1.30.0"
calico_version: "v3.28.0"
longhorn_version: "v1.6.2"
traefik_version: "v2.11.0"
fleet_version: "latest"

# Cluster Networking
cluster_cidr: "10.244.0.0/16"
pod_network_cidr: "10.244.0.0/16"
service_cidr: "10.96.0.0/12"
cluster_domain: "cluster.local"

# Node Configuration
master_node_name: "master"
worker_node_names:
  - "worker1"
  - "worker2"

# Storage Settings
storage_class: "longhorn"
default_storage_size: "50Gi"

# Container Runtime
containerd_cgroup_driver: "systemd"
containerd_log_level: "info"

# Kubernetes Components (Enable/Disable)
enable_fleet: true
enable_calico: true
enable_longhorn: true
enable_traefik: true
enable_coredns: true

# Longhorn Settings
longhorn_default_replica_count: 2
longhorn_default_resource_request_cpu: "500m"
longhorn_default_resource_request_memory: "512Mi"
longhorn_default_resource_limit_cpu: "1000m"
longhorn_default_resource_limit_memory: "1Gi"

# Traefik Settings
traefik_log_level: "INFO"
traefik_accesslog: true

# CoreDNS Settings
coredns_replicas: 2

# Cluster Name (used in kubeadm init)
cluster_name: "branconet-k8s"

# Kubeconfig Path
kubeconfig_path: "/root/.kube/config"
```

## Usage

### Full Installation

Run the complete playbook on all nodes:

```bash
ansible-playbook playbooks/site.yml -i inventory/production.ini
```

### Install Specific Components Only

Use tags to install specific components:

```bash
# Install only prerequisites and Kubernetes binaries
ansible-playbook playbooks/site.yml -i inventory/production.ini --tags bootstrap,kubernetes

# Install only networking (Calico)
ansible-playbook playbooks/site.yml -i inventory/production.ini --tags network

# Install only Longhorn storage
ansible-playbook playbooks/site.yml -i inventory/production.ini --tags storage

# Install only Traefik ingress
ansible-playbook playbooks/site.yml -i inventory/production.ini --tags ingress

# Install only CoreDNS
ansible-playbook playbooks/site.yml -i inventory/production.ini --tags dns

# Install only GitOps (Fleet)
ansible-playbook playbooks/site.yml -i inventory/production.ini --tags gitops
```

### Dry Run (Check Mode)

Verify the playbook without making changes:

```bash
ansible-playbook playbooks/site.yml -i inventory/production.ini --check
```

### Verbose Output

See detailed output for debugging:

```bash
ansible-playbook playbooks/site.yml -i inventory/production.ini -vvv
```

### Skip Specific Roles

Skip certain roles during installation:

```bash
# Skip networking and fleet (already installed)
ansible-playbook playbooks/site.yml -i inventory/production.ini --skip-tags network,gitops
```

### Run on Specific Hosts

Target specific nodes:

```bash
# Run only on master node
ansible-playbook playbooks/site.yml -i inventory/production.ini -l master

# Run only on worker nodes
ansible-playbook playbooks/site.yml -i inventory/production.ini -l worker1,worker2
```

## Inventory File

Edit `inventory/production.ini` to match your cluster nodes:

```ini
# Kubernetes Cluster Inventory - Production
# Edit this file with your actual node IP addresses and hostnames

[all]
master ansible_host=192.168.1.10 ansible_user=root ansible_python_interpreter=/usr/bin/python3
worker1 ansible_host=192.168.1.11 ansible_user=root ansible_python_interpreter=/usr/bin/python3
worker2 ansible_host=192.168.1.12 ansible_user=root ansible_python_interpreter=/usr/bin/python3

[groups]
master = master
workers = worker1,worker2
k8s_nodes = master,worker1,worker2

[vars]
ansible_connection=ssh
ansible_ssh_common_args='-o StrictHostKeyChecking=no'
```

## Troubleshooting

### Check Playbook Status

```bash
ansible-playbook playbooks/site.yml -i inventory/production.ini --list-hosts
```

### View Task Results

```bash
ansible-playbook playbooks/site.yml -i inventory/production.ini --diff
```

### Debug Specific Role

```bash
ansible-playbook playbooks/site.yml -i inventory/production.ini --tags bootstrap -vvv
```

### Manual Verification

After installation, verify on the master node:

```bash
# Check nodes
kubectl get nodes

# Check all pods
kubectl get pods -A

# Check Longhorn
kubectl get pods -n longhorn-system

# Check Traefik
kubectl get pods -n traefik-system

# Check CoreDNS
kubectl get pods -n kube-system -l k8s-app=coredns

# Check Fleet
kubectl get pods -n fleet-system

# Check Calico
kubectl get pods -n kube-system -l k8s-app=calico
```

### Common Issues

**Issue: "Connection refused" when running kubectl**

```bash
# Fix: Create admin kubeconfig (run on master)
kubeadm init --config /etc/kubernetes/admin.conf
mkdir -p ~/.kube
cp /root/.kube/config ~/.kube/config
export KUBECONFIG=~/.kube/config
```

**Issue: Calico pods stuck in Pending**

```bash
# Check node status
kubectl get nodes

# Check if CNI is installed
kubectl get pods -n kube-system -l k8s-app=calico

# Restart Calico if needed
kubectl rollout restart daemonset calico-node -n kube-system
```

**Issue: Longhorn pods not starting**

```bash
# Check node labels
kubectl get nodes --show-labels

# Add required labels to all nodes
kubectl label nodes <node-name> node.longhorn.io/storage-class=longhorn
```

**Issue: Containerd not running**

```bash
# Check containerd service status
systemctl status containerd

# Restart containerd
sudo systemctl restart containerd
```

## Next Steps

After cluster installation:

1. **Deploy your applications** using Fleet or kubectl (separate GitOps repo)
2. **Configure Traefik routes** for external access
3. **Set up monitoring** with Prometheus/Grafana
4. **Create PersistentVolumeClaims** using Longhorn storage

## License

MIT License - See LICENSE file for details.