#!/bin/bash
# Seed the database with current Ansible variables and node info
# Run from: k8s-rewrite/front-end/

API="http://localhost:4000/api/vars"

echo "=== Seeding vars into DB ==="

# Kubernetes version settings (category: kubernetes)
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"k8s_version","value":"v1.30.0","category":"kubernetes","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"calico_version","value":"v3.28.0","category":"kubernetes","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"traefik_version","value":"v2.11.0","category":"traefik","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"crictl_version","value":"v1.30.0","category":"kubernetes","encrypted":false}' > /dev/null

# Cluster networking (category: networking)
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"cluster_cidr","value":"10.244.0.0/16","category":"networking","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"pod_network_cidr","value":"10.244.0.0/16","category":"networking","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"service_cidr","value":"10.96.0.0/12","category":"networking","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"cluster_domain","value":"cluster.local","category":"networking","encrypted":false}' > /dev/null

# DNS servers for systemd-resolved (category: dns)
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"dns_servers","value":"192.168.0.4 192.168.0.5 8.8.8.8","category":"dns","encrypted":false}' > /dev/null

# Storage settings (category: storage)
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"storage_class","value":"local-path","category":"storage","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"default_storage_size","value":"1Gi","category":"storage","encrypted":false}' > /dev/null

# Longhorn distributed block storage (category: longhorn)
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"longhorn_version","value":"v1.7.2","category":"longhorn","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"longhorn_replicas","value":"2","category":"longhorn","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"longhorn_default_storage_class","value":"longhorn","category":"longhorn","encrypted":false}' > /dev/null

# Container runtime (category: runtime)
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"containerd_cgroup_driver","value":"true","category":"runtime","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"containerd_log_level","value":"info","category":"runtime","encrypted":false}' > /dev/null

# Traefik settings
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"traefik_log_level","value":"INFO","category":"traefik","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"traefik_accesslog","value":"true","category":"traefik","encrypted":false}' > /dev/null

# CoreDNS settings (category: kubernetes)
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"coredns_replicas","value":"2","category":"kubernetes","encrypted":false}' > /dev/null

# Cluster name
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"cluster_name","value":"branconet-k8s","category":"kubernetes","encrypted":false}' > /dev/null

# Kubeconfig path (category: kubernetes)
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"kubeconfig_path","value":"/root/.kube","category":"kubernetes","encrypted":false}' > /dev/null

# Ansible connection settings (category: ansible)
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"ansible_become_password","value":"Jbranco2002!","category":"ansible","encrypted":true}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"ansible_ssh_private_key_file","value":"/home/brajam/.ssh/id_ed25519","category":"ansible","encrypted":false}' > /dev/null

# GitOps / FluxCD settings
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"github_token","value":"","category":"general","encrypted":true}' > /dev/null

# NFS storage (category: nfs)
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"nfs_enabled","value":"true","category":"nfs","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"nfs_server_path","value":"/srv/nfs-share","category":"nfs","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"nfs_provisioner_version","value":"v4.0.2","category":"nfs","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"nfs_storage_class","value":"nfs-client","category":"nfs","encrypted":false}' > /dev/null

# Samba storage (category: samba)
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"samba_enabled","value":"true","category":"samba","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"samba_share_path","value":"/srv/samba-share","category":"samba","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"samba_share_name","value":"k8s-share","category":"samba","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"samba_username","value":"k8s-user","category":"samba","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"samba_password","value":"k8s-pass","category":"samba","encrypted":true}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"smb_storage_class","value":"smb","category":"samba","encrypted":false}' > /dev/null

# Helm (category: helm)
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"helm_version","value":"v3.16.0","category":"helm","encrypted":false}' > /dev/null

# Kubernetes Secrets (category: secret)
# Convention: secret_<namespace>_<name>_<key>
# These are deployed as K8s Secret objects by the secrets Ansible role
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"secret_plex_smb-creds_username","value":"james","category":"secret","encrypted":true}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"secret_plex_smb-creds_password","value":"Jbranco2002!","category":"secret","encrypted":true}' > /dev/null

echo ""
echo "=== Seeding node into DB ==="
curl -s -X POST "http://localhost:4000/api/cluster/nodes" -H "Content-Type: application/json" -d '{"name":"node1","hostname":"node1","ipAddress":"45.79.160.12","role":"master","status":"ready","cpu":1,"memory":1}' > /dev/null

# Node inventory variables (category: kubernetes)
# Pattern: node_<key>_<field> — synced to Nodes table on deploy
#   name     = user-chosen display name
#   hostname = actual machine hostname
#   ip       = Ansible connection IP
#   role     = master | worker
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"node_u1_name","value":"U1 Tower","category":"kubernetes","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"node_u1_hostname","value":"u1","category":"kubernetes","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"node_u1_ip","value":"192.168.1.10","category":"kubernetes","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"node_u1_role","value":"master","category":"kubernetes","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"node_u2_name","value":"U2 Mini","category":"kubernetes","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"node_u2_hostname","value":"u2","category":"kubernetes","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"node_u2_ip","value":"192.168.1.11","category":"kubernetes","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"node_u2_role","value":"worker","category":"kubernetes","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"node_u3_name","value":"U3 Pi","category":"kubernetes","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"node_u3_hostname","value":"u3","category":"kubernetes","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"node_u3_ip","value":"192.168.1.12","category":"kubernetes","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"node_u3_role","value":"worker","category":"kubernetes","encrypted":false}' > /dev/null

echo ""
echo "=== Done seeding ==="
echo "Variables:"
curl -s "$API" | python3 -m json.tool 2>/dev/null | head -30
echo "..."
echo ""
echo "Nodes:"
curl -s "http://localhost:4000/api/cluster/nodes" | python3 -m json.tool 2>/dev/null
