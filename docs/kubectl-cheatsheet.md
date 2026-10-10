# kubectl checks for BORTUS

Run these against the intended operator context. Substitute the actual namespace and resource names; the application does not impose a namespace-per-repository convention.

```bash
kubectl config current-context
kubectl cluster-info
kubectl get nodes -o wide
kubectl get pods -A
kubectl get deployments,services,ingresses -A
kubectl get pvc -A
kubectl get storageclasses
kubectl get events -A --sort-by='.lastTimestamp'
```

For a selected workload:

```bash
kubectl describe pod <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --tail=100
kubectl logs <pod-name> -n <namespace> --previous
kubectl describe pvc <pvc-name> -n <namespace>
```

For the BORTUS ServiceAccount, check each allowed Secret namespace independently:

```bash
kubectl auth can-i list secrets -n <allowed-namespace> --as=system:serviceaccount:bortus:bortus
kubectl auth can-i create secrets -n <allowed-namespace> --as=system:serviceaccount:bortus:bortus
kubectl auth can-i update secrets -n <allowed-namespace> --as=system:serviceaccount:bortus:bortus
kubectl get secrets -n <allowed-namespace>
```

Adjust the ServiceAccount namespace/name if your deployment differs. Impersonation checks require an operator permitted to impersonate that account. Native key deletion uses update and keeps empty objects; whole-Secret delete permission is not required.

For Flux:

```bash
kubectl get gitrepositories,kustomizations -n flux-system
kubectl describe gitrepository <name> -n flux-system
kubectl describe kustomization <name> -n flux-system
```

Do not include Secret data, decoded credentials, kubeconfig contents or credential-bearing application logs in reports. See [connection guide](CONNECTING-TO-A-CLUSTER.md) and [deployment contract](BORTUS-DEPLOYMENT.md).