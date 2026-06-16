# kubectl Cheat Sheet — Branconet Homelab (K8s)

## Cluster Info

```bash
# Where am I?
kubectl cluster-info

# All nodes
kubectl get nodes -o wide

# Node details
kubectl describe node <node-name>

# Top nodes (if metrics-server is running)
kubectl top nodes
```

## Namespace Convention

Every Flux repository = one namespace with the **same name**.  
`charts/<name>/` → namespace `<name>`.

```bash
kubectl get ns

kubectl get all -n plex
kubectl get all -n traefik
kubectl get all -n whoami
kubectl get all -n http-echo
kubectl get all -n nginx-hello
kubectl get all -n longhorn-system
kubectl get all -n flux-system
```

## Switching Context

```bash
# Set default namespace for a session
kubectl config set-context --current --namespace=plex

# Run one command in a namespace
kubectl -n plex get pods
```

## Workloads (Deployments / Pods)

```bash
# All pods across all namespaces
kubectl get pods -A

# Pods in one namespace with IPs and node placement
kubectl get pods -n plex -o wide

# Describe a pod (events at the bottom — look for ImagePullBackOff, CrashLoopBackOff)
kubectl describe pod <pod-name> -n plex

# Pod logs
kubectl logs <pod-name> -n plex

# Follow logs (tail -f)
kubectl logs -f <pod-name> -n plex

# Previous crashed container logs
kubectl logs <pod-name> -n plex --previous

# Multi-container pod — specify container
kubectl logs <pod-name> -c <container-name> -n plex

# Exec into a pod
kubectl exec -it <pod-name> -n plex -- /bin/sh

# Delete a pod (Deployment will recreate it)
kubectl delete pod <pod-name> -n plex

# Restart a deployment (rolling restart)
kubectl rollout restart deployment <name> -n plex

# Scale a deployment
kubectl scale deployment <name> --replicas=0 -n plex   # stop
kubectl scale deployment <name> --replicas=1 -n plex   # start
```

## Services & Networking

```bash
# Services in a namespace
kubectl get svc -n plex

# Endpoints (check if service can reach pods)
kubectl get endpoints -n plex

# Port-forward to local machine
kubectl port-forward svc/<service-name> 8080:80 -n plex
# Then open http://localhost:8080

# Ingresses
kubectl get ingress -A
kubectl describe ingress <name> -n plex
```

## Storage (CSI SMB Driver)

```bash
# PersistentVolumeClaims
kubectl get pvc -A

# PersistentVolumes
kubectl get pv

# StorageClasses
kubectl get sc
# Expected: `smb` — CSI SMB driver, source: //192.168.0.8/k8s-share

# Describe a PVC to see bound PV and mount details
kubectl describe pvc <pvc-name> -n plex

# SMB credentials — managed by Secrets Engine, per-namespace
kubectl get secret smb-creds -n plex -o yaml
# (username/password come from DB secret_plex_smb-creds_*)

# Check CSI driver health
kubectl get pods -n kube-system | grep smb
kubectl logs -n kube-system daemonset/csi-smb-node -c smb
```

## Secrets (Secrets Engine → K8s)

```bash
# All secrets in a namespace
kubectl get secrets -n plex

# Inspect a secret (decodes base64)
kubectl get secret smb-creds -n plex -o jsonpath='{.data.username}' | base64 -d
kubectl get secret smb-creds -n plex -o jsonpath='{.data.password}' | base64 -d

# Secrets are annotated prune=disabled — they survive FluxCD reconciliation
kubectl get secret <name> -n <ns> -o jsonpath='{.metadata.annotations}'
```

## FluxCD

```bash
# Flux resources (always in flux-system namespace)
kubectl get gitrepositories -n flux-system
kubectl get kustomizations -n flux-system

# Check Flux health
kubectl describe gitrepository <name> -n flux-system
kubectl describe kustomization <name> -n flux-system

# Manually trigger a Flux reconciliation
kubectl annotate gitrepository <name> -n flux-system \
  reconcile.fluxcd.io/requestedAt="$(date -Iseconds)" --overwrite

# Suspend / resume Flux for a repo (stops auto-sync)
kubectl patch kustomization <name> -n flux-system -p '{"spec":{"suspend":true}}' --type=merge
kubectl patch kustomization <name> -n flux-system -p '{"spec":{"suspend":false}}' --type=merge

# Check what Flux applied (all resources in target namespace)
kubectl get all -n plex
```

## Events & Troubleshooting

```bash
# All cluster events (recent first)
kubectl get events -A --sort-by='.lastTimestamp'

# Events in a namespace
kubectl get events -n plex --sort-by='.lastTimestamp'

# Watch events live
kubectl get events -n plex -w

# Describe anything for deep status
kubectl describe <resource> <name> -n <ns>

# Check why a pod won't start (Conditions + Events at bottom)
kubectl describe pod <pod-name> -n plex | tail -40

# Resource usage (if metrics-server running)
kubectl top pods -n plex
kubectl top nodes
```

## Nuke & Restore

```bash
# Delete entire namespace (cascading — removes EVERYTHING)
kubectl delete namespace plex

# Delete ALL resources in a namespace but keep the namespace
kubectl delete all --all -n plex

# Force-delete a stuck namespace (if finalizers hang)
kubectl get namespace plex -o json | \
  jq '.spec.finalizers = []' | \
  kubectl replace --raw "/api/v1/namespaces/plex/finalize" -f -

# Resync from Flux after a manual nuke
kubectl annotate gitrepository plex -n flux-system \
  reconcile.fluxcd.io/requestedAt="$(date -Iseconds)" --overwrite
```

## Ansible (kubeconfig path)

```bash
# Local (laptop)
kubectl --kubeconfig ~/.kube/config get nodes

# On master node
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf get nodes
```

## Quick Aliases

Add to `~/.bashrc`:

```bash
alias k='kubectl'
alias kgp='kubectl get pods'
alias kgpa='kubectl get pods -A'
alias kgs='kubectl get svc'
alias kgn='kubectl get nodes'
alias kga='kubectl get all'
alias kd='kubectl describe'
alias kl='kubectl logs'
alias klf='kubectl logs -f'
alias ke='kubectl exec -it'
alias kns='kubectl config set-context --current --namespace'

# Namespace shortcuts
alias kplex='kubectl -n plex'
alias ktraef='kubectl -n traefik'
alias kflux='kubectl -n flux-system'
alias klong='kubectl -n longhorn-system'
```

## Common Patterns

```bash
# Restart all pods in a namespace
kubectl rollout restart deployment -n plex

# Check if a pod can reach the SMB server
kubectl exec -it <pod-name> -n plex -- sh -c 'ping -c 2 192.168.0.8'

# Test SMB mount from inside a pod
kubectl exec -it <pod-name> -n plex -- sh -c 'ls /mnt/media'

# Watch Flux reconcile after git push
kubectl get kustomization plex -n flux-system -w

# Find pods with restarts
kubectl get pods -A | awk '$5 > 0'

# Disk usage on nodes
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.allocatable.ephemeral-storage}{"\n"}{end}'

# Delete all completed/failed jobs
kubectl delete pods -A --field-selector=status.phase=Failed
kubectl delete pods -A --field-selector=status.phase=Succeeded
```
