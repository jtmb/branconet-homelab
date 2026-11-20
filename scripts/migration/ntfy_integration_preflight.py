"""Fixed read-only inventory for ntfy's pending production-like qualification.

No Secret reads, dry-run POST, exec, apply, DNS/registry/host mutation or generic
kubectl passthrough. Projection stores only public integration metadata.
"""
import decimal

ENDPOINTS = {
    "traefik": "/apis/apps/v1/namespaces/traefik/deployments/traefik",
    "edge_namespace": "/api/v1/namespaces/traefik",
    "tcp_crd": "/apis/apiextensions.k8s.io/v1/customresourcedefinitions?fieldSelector=metadata.name%3Dingressroutetcps.traefik.io",
    "storage": "/apis/storage.k8s.io/v1/storageclasses/longhorn",
    "issuer": "/apis/cert-manager.io/v1/clusterissuers/branconet-local-ca",
    "calico": "/apis/apps/v1/namespaces/kube-system/daemonsets/calico-node",
    "node": "/api/v1/nodes/node01",
    "pods": "/api/v1/pods?fieldSelector=spec.nodeName%3Dnode01",
    "longhorn_node": "/apis/longhorn.io/v1beta2/namespaces/longhorn-system/nodes/node01",
    "namespace": "/api/v1/namespaces?fieldSelector=metadata.name%3Dbortus-notifications",
}


def quantity(value):
    """Parse only the Kubernetes units used by declared CPU/memory metadata."""
    factors = {"Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4,
               "Pi": 1024**5, "Ei": 1024**6, "n": .000000001, "u": .000001,
               "m": .001, "k": 1000, "K": 1000, "M": 1000**2,
               "G": 1000**3, "T": 1000**4}
    text = str(value)
    for suffix in sorted(factors, key=len, reverse=True):
        if text.endswith(suffix):
            return decimal.Decimal(text[:-len(suffix)]) * decimal.Decimal(str(factors[suffix]))
    return decimal.Decimal(text)


def collect(reader):
    values = {name: reader(endpoint) for name, endpoint in ENDPOINTS.items()}
    edge = values["traefik"]
    pod = edge["spec"]["template"]["spec"]
    container = next(c for c in pod["containers"] if c["name"] == "traefik")
    args = container.get("args", [])
    allowed_flags = ("--providers.kubernetesingress", "--providers.kubernetescrd",
                     "--providers.file.", "--entrypoints.", "--ping")
    public_args = [a for a in args if a.startswith(allowed_flags)]
    volumes = []
    for volume in pod.get("volumes", []):
        if volume["name"] == "dashboard-config":
            # References/modes only, never resolve the Secret's data.
            volumes.append({"name": volume["name"], "secretReference": volume.get("secret", {}).get("secretName"),
                            "defaultMode": volume.get("secret", {}).get("defaultMode", 420),
                            "alreadyProjected": "projected" in volume})
    sc = values["storage"]
    params = sc.get("parameters", {})
    public_parameters = {k: params[k] for k in ("encrypted", "numberOfReplicas", "fsType",
                         "dataLocality", "nodeSelector", "diskSelector") if k in params}
    issuer = values["issuer"]
    node = values["node"]
    request_cpu, request_memory = decimal.Decimal(0), decimal.Decimal(0)
    pods = values["pods"]
    assert not pods.get("metadata", {}).get("continue"), "pod_inventory_incomplete"
    for item in pods["items"]:
        if item.get("status", {}).get("phase") in ("Succeeded", "Failed"):
            continue
        spec = item["spec"]
        # Conservatively sum all init + pod-level requests as well; this is an
        # upper-bound declaration inventory, not scheduler/metrics acceptance.
        requests = [c.get("resources", {}).get("requests", {}) for c in
                    spec.get("containers", []) + spec.get("initContainers", [])]
        requests += [spec.get("resources", {}).get("requests", {}), spec.get("overhead", {})]
        for request in requests:
            request_cpu += quantity(request.get("cpu", "0"))
            request_memory += quantity(request.get("memory", "0"))
    status = values["calico"]["status"]
    disk_status = values["longhorn_node"].get("status", {}).get("diskStatus", {})
    file_provider = any(a.startswith("--providers.file.directory=") for a in args)
    crd_provider = any(a == "--providers.kubernetescrd" or a == "--providers.kubernetescrd=true" for a in args)
    crd_present = bool(values["tcp_crd"].get("items"))
    blockers = ["registry_publication_not_authorized_or_verified",
                "private_route_mount_upgrade_not_applied",
                "native_dynamic_file_key_collision_not_checked",
                "ntfy_restart_on_tls_rotation_not_qualified",
                "live_networkpolicy_storage_resource_and_attended_checks_unrun"]
    # The inactive source now uses the file provider. Missing optional CRD
    # support remains capability metadata, not a dependency of that route.
    if not file_provider:
        blockers.append("file_provider_not_enabled")
    return {
        "readOnly": True, "activationReady": False, "blockers": blockers,
        "traefik": {"uid": edge["metadata"]["uid"], "image": container["image"], "args": public_args,
                    "replicas": edge["spec"].get("replicas"), "readyReplicas": edge.get("status", {}).get("readyReplicas", 0),
                    "namespaceUID": values["edge_namespace"]["metadata"]["uid"],
                    "podLabels": edge["spec"]["template"]["metadata"].get("labels", {}),
                    "fileProviderEnabled": file_provider, "crdProviderEnabled": crd_provider,
                    "tcpCRDPresent": crd_present, "dynamicVolume": volumes},
        "storageClass": {"uid": sc["metadata"]["uid"], "provisioner": sc["provisioner"],
                         "reclaimPolicy": sc.get("reclaimPolicy"), "volumeBindingMode": sc.get("volumeBindingMode"),
                         "parameters": public_parameters, "fromBackupPresent": bool(params.get("fromBackup"))},
        "issuer": {"uid": issuer["metadata"]["uid"], "caIssuer": "ca" in issuer["spec"],
                   "ready": any(c.get("type") == "Ready" and c.get("status") == "True"
                                for c in issuer.get("status", {}).get("conditions", []))},
        "calico": {"uid": values["calico"]["metadata"]["uid"], "desired": status.get("desiredNumberScheduled"),
                   "ready": status.get("numberReady"),
                   "images": [c["image"] for c in values["calico"]["spec"]["template"]["spec"]["containers"]]},
        "node01": {"uid": node["metadata"]["uid"], "allocatable": node["status"]["allocatable"],
                   "taints": node["spec"].get("taints", []),
                   "conditions": [{k: c.get(k) for k in ("type", "status")} for c in node["status"]["conditions"]],
                   "conservativeDeclaredCPUMilli": int(request_cpu * 1000),
                   "conservativeDeclaredMemoryBytes": int(request_memory),
                   "metricsOrSchedulerFitClaimed": False},
        "longhornDisks": [{"name": name, **{k: d.get(k) for k in
                            ("storageAvailable", "storageMaximum", "storageScheduled")}}
                          for name, d in disk_status.items()],
        "productionNtfyNamespacePresent": bool(values["namespace"].get("items")),
        "ntfyServingTLS": {"upstreamVersion": "2.38.1",
                           "source": "https://github.com/binwiederhier/ntfy/blob/v2.38.1/server/server.go#L518",
                           "behavior": "http.Server.ListenAndServeTLS(CertFile,KeyFile); serving certificate loads at start",
                           "projectionAloneProvesRenewal": False, "restartAndEndpointFingerprintProofRequired": True},
    }
