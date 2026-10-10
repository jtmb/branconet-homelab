# Connecting BORTUS to a cluster

BORTUS requires externally supplied Kubernetes credentials. It does not bootstrap credentials from SQLite or fetch them over SSH at startup.

## Operator mode

Set `KUBECONFIG` to an operator-managed kubeconfig, or supply `~/.kube/config`. Verify the selected context independently:

```bash
kubectl config current-context
kubectl cluster-info
kubectl get nodes -o wide
```

Native Secret operations use verified HTTPS through the Kubernetes client. HTTP endpoints and kubeconfigs disabling certificate verification are rejected. Other dashboard resources use the installed kubectl with operator kubeconfig or in-cluster credentials.

## In-cluster mode

Mount the ServiceAccount token and CA using the deployment's normal Kubernetes credentials. Permit network access to the API server and DNS. Configure `BORTUS_SECRET_NAMESPACES` explicitly and bind Secret Roles in each allowed namespace to the app's ServiceAccount. Native Secret list access can read values at the Kubernetes API level even though BORTUS returns only metadata to readonly users.

See [deployment contract](BORTUS-DEPLOYMENT.md) for RBAC, runtime Secret references, aliases, probes, storage and network inputs. Resource browsing, Flux and the operator shell require their own appropriate Kubernetes permissions.

## Dashboard access and diagnostics

Use the configured TLS ingress for deployed instances; loopback development uses `http://localhost:4000`. DNS names, node addresses, ingress implementation and firewall rules are deployment inputs. This application merge does not define the live cluster topology.

Check `/api/health/live` for process liveness and `/api/health/ready` for signing/lookup configuration, migrated SQLite and native Secret access across the allowlist. Readiness returns 503 for unavailable dependencies. Probe paths are public and return no credentials.

If resources are missing, check the selected context, namespace allowlist, ServiceAccount permissions, API reachability and CA trust. Never resolve a trust failure by disabling TLS verification. Keep recovery kubeconfig and bootstrap credentials independently available.