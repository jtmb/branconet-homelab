#!/bin/bash
# Seed the database with current Ansible variables and node info
# Run from: k8s-rewrite/front-end/

API="http://localhost:4000/api/vars"

echo "=== Seeding vars into DB ==="

# Kubernetes version settings (category: kubernetes)
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"k8s_version","value":"v1.30.0","category":"kubernetes","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"calico_version","value":"v3.28.0","category":"kubernetes","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"traefik_version","value":"v2.11.0","category":"kubernetes","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"crictl_version","value":"v1.30.0","category":"kubernetes","encrypted":false}' > /dev/null

# Cluster networking (category: networking)
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"cluster_cidr","value":"10.244.0.0/16","category":"networking","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"pod_network_cidr","value":"10.244.0.0/16","category":"networking","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"service_cidr","value":"10.96.0.0/12","category":"networking","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"cluster_domain","value":"cluster.local","category":"networking","encrypted":false}' > /dev/null

# Node configuration (category: general)
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"master_node_name","value":"node1","category":"general","encrypted":false}' > /dev/null

# Storage settings (category: storage)
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"storage_class","value":"local-path","category":"storage","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"default_storage_size","value":"1Gi","category":"storage","encrypted":false}' > /dev/null

# Container runtime (category: runtime)
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"containerd_cgroup_driver","value":"true","category":"runtime","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"containerd_log_level","value":"info","category":"runtime","encrypted":false}' > /dev/null

# Traefik settings
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"traefik_log_level","value":"INFO","category":"traefik","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"traefik_accesslog","value":"true","category":"traefik","encrypted":false}' > /dev/null

# CoreDNS settings
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"coredns_replicas","value":"2","category":"general","encrypted":false}' > /dev/null

# Cluster name
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"cluster_name","value":"branconet-k8s","category":"kubernetes","encrypted":false}' > /dev/null

# Kubeconfig path
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"kubeconfig_path","value":"/root/.kube","category":"general","encrypted":false}' > /dev/null

# GitOps / FluxCD settings
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"github_user","value":"jtmb","category":"general","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"github_repo","value":"branconet-homelab","category":"general","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"github_branch","value":"main","category":"general","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"gitops_path","value":"k8s-rewrite/02-applications","category":"general","encrypted":false}' > /dev/null
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{"key":"github_token","value":"","category":"general","encrypted":true}' > /dev/null

echo ""
echo "=== Seeding node into DB ==="
curl -s -X POST "http://localhost:4000/api/cluster/nodes" -H "Content-Type: application/json" -d '{"hostname":"node1","ipAddress":"45.79.160.12","role":"master","status":"ready","cpu":1,"memory":1}' > /dev/null

echo ""
echo "=== Done seeding ==="
echo "Variables:"
curl -s "$API" | python3 -m json.tool 2>/dev/null | head -30
echo "..."
echo ""
echo "Nodes:"
curl -s "http://localhost:4000/api/cluster/nodes" | python3 -m json.tool 2>/dev/null
