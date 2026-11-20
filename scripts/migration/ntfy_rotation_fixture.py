"""Narrow namespace-only rotation identity and bounded Job/CronJob templates."""
import copy
from ntfy_cluster_fixture import NAMESPACE, EDGE, LABEL, OWNER, resource

ACCOUNT = "ntfy-rotation-qualification"
SOURCE = "ntfy-rotation-controller"
RUNTIME = "docker.io/jtmb92/bortus@sha256:e7539b9e79aebe0024f0cfc70dc0a8f2fe89354ab7ffcf9df7a822ffcc343f77"


def identity():
    return [
        resource("ServiceAccount", ACCOUNT, NAMESPACE, automountServiceAccountToken=False),
        resource("Role", ACCOUNT, NAMESPACE, "rbac.authorization.k8s.io/v1", rules=[
            {"apiGroups": ["apps"], "resources": ["deployments"], "resourceNames": ["private-ntfy"],
             "verbs": ["get", "patch"]},
            {"apiGroups": [""], "resources": ["secrets"], "resourceNames": ["synthetic-leaf"],
             "verbs": ["get"]},
            {"apiGroups": ["cert-manager.io"], "resources": ["certificates"],
             "resourceNames": ["synthetic-leaf"], "verbs": ["get"]},
            # Only public requests; known exact revision is fetched without LIST.
            {"apiGroups": ["cert-manager.io"], "resources": ["certificaterequests"], "verbs": ["get"]},
        ]),
        resource("RoleBinding", ACCOUNT, NAMESPACE, "rbac.authorization.k8s.io/v1",
            roleRef={"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": ACCOUNT},
            subjects=[{"kind": "ServiceAccount", "namespace": NAMESPACE, "name": ACCOUNT}]),
        resource("NetworkPolicy", ACCOUNT, NAMESPACE, "networking.k8s.io/v1", spec={
            "podSelector": {"matchLabels": {"app": ACCOUNT}}, "policyTypes": ["Ingress", "Egress"],
            "ingress": [], "egress": [
                {"to": [{"ipBlock": {"cidr": "192.168.0.4/32"}}],
                 "ports": [{"protocol": "TCP", "port": 6443}]},
                {"to": [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": EDGE}},
                          "podSelector": {"matchLabels": {"role": "edge"}}}],
                 "ports": [{"protocol": "TCP", "port": 8443}]},
            ]}),
    ]


def job(name, script="controller.mjs"):
    pod = {"serviceAccountName": ACCOUNT, "automountServiceAccountToken": False,
        "restartPolicy": "Never", "terminationGracePeriodSeconds": 5,
        "nodeSelector": {"kubernetes.io/hostname": "node02"},
        "securityContext": {"runAsNonRoot": True, "runAsUser": 1000, "runAsGroup": 1000,
                            "fsGroup": 1000, "seccompProfile": {"type": "RuntimeDefault"}},
        "containers": [{"name": "rotation", "image": RUNTIME, "imagePullPolicy": "Never",
            "command": ["node", "/controller/" + script],
            "env": [{"name": "NODE_DISABLE_COMPILE_CACHE", "value": "1"}],
            "resources": {"requests": {"cpu": "25m", "memory": "48Mi"},
                          "limits": {"cpu": "100m", "memory": "128Mi"}},
            "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                                "capabilities": {"drop": ["ALL"]}},
            "volumeMounts": [{"name": "source", "mountPath": "/controller", "readOnly": True},
                            {"name": "credentials", "mountPath": "/var/run/rotation", "readOnly": True},
                            {"name": "public-leaf", "mountPath": "/serving", "readOnly": True},
                            {"name": "tmp", "mountPath": "/tmp"}]}],
        "volumes": [
            {"name": "source", "configMap": {"name": SOURCE}},
            {"name": "credentials", "projected": {"defaultMode": 288, "sources": [
                {"serviceAccountToken": {"path": "token", "expirationSeconds": 600,
                    "audience": "https://kubernetes.default.svc.cluster.local"}},
                {"configMap": {"name": "kube-root-ca.crt", "items": [{"key": "ca.crt", "path": "ca.crt"}]}},
            ]}},
            {"name": "public-leaf", "secret": {"secretName": "synthetic-leaf",
                "items": [{"key": "tls.crt", "path": "tls.crt"}, {"key": "ca.crt", "path": "ca.crt"}]}},
            {"name": "tmp", "emptyDir": {"medium": "Memory", "sizeLimit": "8Mi"}},
        ]}
    return resource("Job", name, NAMESPACE, "batch/v1", spec={
        "backoffLimit": 0, "activeDeadlineSeconds": 60,
        "template": {"metadata": {"labels": {LABEL: OWNER, "app": ACCOUNT}}, "spec": pod}})


def cron():
    template = copy.deepcopy(job("unused")["spec"])
    return resource("CronJob", ACCOUNT, NAMESPACE, "batch/v1", spec={
        "schedule": "* * * * *", "timeZone": "Etc/UTC", "concurrencyPolicy": "Forbid",
        "startingDeadlineSeconds": 30, "successfulJobsHistoryLimit": 2,
        "failedJobsHistoryLimit": 2, "suspend": True,
        "jobTemplate": {"metadata": {"labels": {LABEL: OWNER, "app": ACCOUNT}}, "spec": template}})
