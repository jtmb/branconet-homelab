"""Isolated diagnostic resources; never alter production namespaces or claims."""
import copy
import yaml

NAMESPACE = "bortus-ntfy-qualify"
EDGE = "bortus-ntfy-edge-qualify"
DENIED = "bortus-ntfy-denied-qualify"
OWNER = "ntfy-integration-v1"
NAME = "ntfy-qualification.invalid"
LABEL = "bortus.jtmb.cc/qualification"


def resource(kind, name, namespace=None, api="v1", **fields):
    metadata = {"name": name, "labels": {LABEL: OWNER}}
    if namespace:
        metadata["namespace"] = namespace
    return {"apiVersion": api, "kind": kind, "metadata": metadata, **fields}


def objects(server_text, image, edge_image):
    result = [resource("Namespace", n) for n in (NAMESPACE, EDGE, DENIED)]
    result.extend([
        resource("Issuer", "synthetic-selfsigned", NAMESPACE, "cert-manager.io/v1",
                 spec={"selfSigned": {}}),
        resource("Certificate", "synthetic-ca", NAMESPACE, "cert-manager.io/v1", spec={
            "isCA": True, "commonName": "ntfy-qualification-ca", "secretName": "synthetic-ca",
            "duration": "24h", "renewBefore": "1h",
            "issuerRef": {"kind": "Issuer", "name": "synthetic-selfsigned"},
            "privateKey": {"algorithm": "ECDSA", "size": 256}}),
        resource("Issuer", "synthetic-ca", NAMESPACE, "cert-manager.io/v1",
                 spec={"ca": {"secretName": "synthetic-ca"}}),
        resource("Certificate", "synthetic-leaf", NAMESPACE, "cert-manager.io/v1", spec={
            "secretName": "synthetic-leaf", "duration": "4h", "renewBefore": "1h",
            "dnsNames": [NAME], "issuerRef": {"kind": "Issuer", "name": "synthetic-ca"},
            "privateKey": {"algorithm": "ECDSA", "size": 256, "rotationPolicy": "Always"}}),
    ])
    claim = resource("PersistentVolumeClaim", "private-ntfy-qualification-cache", NAMESPACE, spec={
        "accessModes": ["ReadWriteOnce"], "storageClassName": "longhorn",
        "resources": {"requests": {"storage": "1Gi"}}})
    claim["metadata"]["annotations"] = {
        "helm.sh/resource-policy": "keep", "kustomize.toolkit.fluxcd.io/prune": "disabled"}
    result.append(claim)
    server = yaml.safe_load(server_text)
    server["base-url"] = "https://" + NAME
    result.append(resource("ConfigMap", "ntfy-config", NAMESPACE, data={
        "server.yml": yaml.safe_dump(server, sort_keys=False)}))
    security = {"runAsNonRoot": True, "runAsUser": 1000, "runAsGroup": 1000,
                "fsGroup": 1000, "seccompProfile": {"type": "RuntimeDefault"}}
    container_security = {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                          "capabilities": {"drop": ["ALL"]}}
    ntfy = {"name": "ntfy", "image": image, "imagePullPolicy": "Never",
            "args": ["serve", "--config", "/etc/ntfy/server.yml"],
            "securityContext": container_security,
            "resources": {"requests": {"cpu": "50m", "memory": "64Mi", "ephemeral-storage": "16Mi"},
                          "limits": {"cpu": "250m", "memory": "256Mi", "ephemeral-storage": "64Mi"}},
            "env": [{"name": "NTFY_AUTH_USERS", "valueFrom": {"secretKeyRef": {"name": "ntfy-auth", "key": "users"}}},
                    {"name": "NTFY_AUTH_TOKENS", "valueFrom": {"secretKeyRef": {"name": "ntfy-auth", "key": "tokens"}}}],
            "ports": [{"name": "https", "containerPort": 8443}],
            "readinessProbe": {"httpGet": {"path": "/v1/health", "port": "https", "scheme": "HTTPS"},
                               "periodSeconds": 3, "timeoutSeconds": 2},
            "livenessProbe": {"httpGet": {"path": "/v1/health", "port": "https", "scheme": "HTTPS"},
                              "initialDelaySeconds": 15, "periodSeconds": 10},
            "volumeMounts": [{"name": n, "mountPath": d, "readOnly": ro}
                            for n, d, ro in (("config", "/etc/ntfy", True), ("tls", "/tls", True),
                                             ("cache", "/cache", False), ("auth", "/auth", False),
                                             ("tmp", "/tmp", False))]}
    pod = {"automountServiceAccountToken": False, "activeDeadlineSeconds": 900,
           "terminationGracePeriodSeconds": 10, "securityContext": security,
           "nodeSelector": {"kubernetes.io/hostname": "node01"}, "containers": [ntfy],
           "volumes": [{"name": "config", "configMap": {"name": "ntfy-config"}},
                       {"name": "tls", "secret": {"secretName": "synthetic-leaf", "defaultMode": 288}},
                       {"name": "cache", "persistentVolumeClaim": {"claimName": "private-ntfy-qualification-cache"}},
                       {"name": "auth", "emptyDir": {"medium": "Memory", "sizeLimit": "16Mi"}},
                       {"name": "tmp", "emptyDir": {"medium": "Memory", "sizeLimit": "8Mi"}}]}
    backend = resource("Pod", "private-ntfy", NAMESPACE, spec=pod)
    backend["metadata"]["labels"]["app"] = "ntfy-qualification"
    result.append(backend)
    result.append(resource("Service", "private-ntfy", NAMESPACE, spec={
        "selector": {"app": "ntfy-qualification"}, "ports": [{"port": 443, "targetPort": 8443}],
        "type": "ClusterIP"}))
    result.append(resource("NetworkPolicy", "ntfy-isolation", NAMESPACE, "networking.k8s.io/v1", spec={
        "podSelector": {"matchLabels": {"app": "ntfy-qualification"}}, "policyTypes": ["Ingress", "Egress"],
        "egress": [], "ingress": [{"from": [{"namespaceSelector": {"matchLabels": {
            "kubernetes.io/metadata.name": EDGE}}, "podSelector": {"matchLabels": {"role": "edge"}}}],
            "ports": [{"protocol": "TCP", "port": 8443}]}]}))
    dynamic = {"tcp": {"routers": {"qualification": {"entryPoints": ["websecure"],
        "rule": "HostSNI(`" + NAME + "`)", "service": "qualification", "tls": {"passthrough": True}}},
        "services": {"qualification": {"loadBalancer": {"servers": [
            {"address": "private-ntfy." + NAMESPACE + ".svc.cluster.local:443"}]}}}},
        "http": {"routers": {"control": {"entryPoints": ["web"], "rule": "Path(`/control`)",
            "service": "noop@internal", "middlewares": ["control"]}},
            "middlewares": {"control": {"redirectRegex": {
                "regex": ".*", "replacement": "https://control.invalid/checked", "permanent": True}}}}}
    result.append(resource("ConfigMap", "edge-config", EDGE, data={
        "qualification.yaml": yaml.safe_dump(dynamic, sort_keys=False)}))
    edge_pod = {"automountServiceAccountToken": False, "activeDeadlineSeconds": 900,
        "terminationGracePeriodSeconds": 10, "securityContext": security,
        "nodeSelector": {"kubernetes.io/hostname": "node02"},
        "containers": [{"name": "traefik", "image": edge_image, "imagePullPolicy": "Never",
            "securityContext": copy.deepcopy(container_security),
            "args": ["--providers.file.directory=/etc/traefik/dynamic", "--providers.file.watch=true",
                     "--entrypoints.web.address=:8000", "--entrypoints.websecure.address=:8443",
                     "--ping=true", "--ping.entrypoint=health", "--entrypoints.health.address=:9000",
                     "--accesslog=false", "--log.level=ERROR"],
            "resources": {"requests": {"cpu": "50m", "memory": "64Mi"},
                          "limits": {"cpu": "500m", "memory": "512Mi"}},
            "volumeMounts": [{"name": "dynamic", "mountPath": "/etc/traefik/dynamic", "readOnly": True},
                             {"name": "tmp", "mountPath": "/tmp"}],
            "readinessProbe": {"httpGet": {"path": "/ping", "port": 9000}, "periodSeconds": 3}}],
        "volumes": [{"name": "dynamic", "configMap": {"name": "edge-config"}},
                    {"name": "tmp", "emptyDir": {"medium": "Memory", "sizeLimit": "8Mi"}}]}
    edge_resource = resource("Pod", "ntfy-edge", EDGE, spec=edge_pod)
    edge_resource["metadata"]["labels"].update({
        "app": "ntfy-edge", "role": "edge", "istio.io/dataplane-mode": "ambient"})
    edge_resource["metadata"]["annotations"] = {"ambient.istio.io/bypass-inbound-capture": "true"}
    result.append(edge_resource)
    result.append(resource("Service", "ntfy-edge", EDGE, spec={
        "type": "ClusterIP", "selector": {"app": "ntfy-edge"},
        "ports": [{"name": "https", "port": 443, "targetPort": 8443},
                  {"name": "http", "port": 80, "targetPort": 8000}]}))
    for name, namespace, role, node in (
            ("allowed-probe", EDGE, "edge", "node02"), ("unselected-probe", EDGE, "other", "node02"),
            ("same-namespace-probe", NAMESPACE, "other", "node01"),
            ("denied-probe", DENIED, "other", "node02")):
        probe = resource("Pod", name, namespace, spec={
            "automountServiceAccountToken": False, "activeDeadlineSeconds": 720, "restartPolicy": "Never",
            "securityContext": security, "nodeSelector": {"kubernetes.io/hostname": node},
            "containers": [{"name": "probe", "image": image, "imagePullPolicy": "Never",
                "command": ["/bin/sh", "-ec", "sleep 700"], "securityContext": container_security,
                "resources": {"requests": {"cpu": "5m", "memory": "16Mi"},
                              "limits": {"cpu": "50m", "memory": "64Mi"}}}]})
        probe["metadata"]["labels"]["role"] = role
        result.append(probe)
    return result
