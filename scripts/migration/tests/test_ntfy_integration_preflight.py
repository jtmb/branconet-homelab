"""Public projection/fail-closed inventory tests; not live integration proof."""
import copy
import decimal
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ntfy_integration_preflight import ENDPOINTS, collect, quantity


def inputs():
    return {
        "traefik": {
            "metadata": {"uid": "edge-uid"},
            "spec": {"replicas": 2, "template": {"metadata": {"labels": {"app": "traefik"}},
                "spec": {"containers": [{"name": "traefik", "image": "pinned-edge",
                    "args": ["--providers.file.directory=/etc/traefik/dynamic",
                             "--entrypoints.websecure.address=:8443", "--api.secret=SENTINEL"]}],
                    "volumes": [{"name": "dashboard-config", "secret": {
                        "secretName": "traefik-dashboard-config", "defaultMode": 420}}]}}},
            "status": {"readyReplicas": 2}},
        "edge_namespace": {"metadata": {"uid": "edge-ns"}},
        "tcp_crd": {"items": []},
        "storage": {"metadata": {"uid": "class-uid"}, "provisioner": "driver.longhorn.io",
            "reclaimPolicy": "Retain", "volumeBindingMode": "Immediate",
            "parameters": {"encrypted": "true", "numberOfReplicas": "2", "fsType": "ext4",
                           "secretAccessKey": "SENTINEL", "fromBackup": ""}},
        "issuer": {"metadata": {"uid": "issuer-uid"}, "spec": {"ca": {"secretName": "private-ca"}},
                   "status": {"conditions": [{"type": "Ready", "status": "True", "message": "SENTINEL"}]}},
        "calico": {"metadata": {"uid": "cni"}, "status": {
            "desiredNumberScheduled": 3, "numberReady": 3},
            "spec": {"template": {"spec": {"containers": [{"image": "calico"}]}}}},
        "node": {"metadata": {"uid": "node"}, "spec": {},
                 "status": {"allocatable": {"cpu": "8"}, "conditions": [
                     {"type": "Ready", "status": "True", "message": "SENTINEL"}]}},
        "pods": {"items": [
            {"spec": {"containers": [{"env": [{"value": "SENTINEL"}],
                "resources": {"requests": {"cpu": "125m", "memory": "1Mi"}}}],
                "initContainers": [{"resources": {"requests": {"cpu": "250m", "memory": "2Mi"}}}],
                "resources": {"requests": {"cpu": "50m", "memory": "3Mi"}},
                "overhead": {"cpu": "5m", "memory": "1Mi"}}},
            {"status": {"phase": "Succeeded"}, "spec": {"containers": [
                {"resources": {"requests": {"cpu": "8", "memory": "4Gi"}}}]}}]},
        "longhorn_node": {"status": {"diskStatus": {"disk": {
            "storageAvailable": 1000, "storageMaximum": 2000, "storageScheduled": 500,
            "private": "SENTINEL"}}}},
        "namespace": {"items": []},
    }


class PreflightTests(unittest.TestCase):
    def scan(self, data):
        lookup = {endpoint: data[name] for name, endpoint in ENDPOINTS.items()}
        called = []

        def reader(endpoint):
            called.append(endpoint)
            return copy.deepcopy(lookup[endpoint])

        result = collect(reader)
        self.assertEqual(called, list(ENDPOINTS.values()))
        self.assertEqual(len(set(called)), 10)
        self.assertFalse(any("/secrets" in url or "/exec" in url for url in called))
        return result

    def test_projection_omits_backend_values_and_unsafe_arguments(self):
        result = self.scan(inputs())
        self.assertNotIn("SENTINEL", json.dumps(result))
        self.assertEqual(result["traefik"]["dynamicVolume"], [{
            "name": "dashboard-config", "secretReference": "traefik-dashboard-config",
            "defaultMode": 420, "alreadyProjected": False}])
        self.assertEqual(result["storageClass"]["parameters"],
                         {"encrypted": "true", "numberOfReplicas": "2", "fsType": "ext4"})

    def test_file_route_needs_mount_approval_not_an_uninstalled_crd(self):
        result = self.scan(inputs())
        self.assertFalse(result["activationReady"])
        self.assertTrue(result["traefik"]["fileProviderEnabled"])
        self.assertFalse(result["traefik"]["tcpCRDPresent"])
        self.assertFalse(result["traefik"]["crdProviderEnabled"])
        self.assertIn("private_route_mount_upgrade_not_applied", result["blockers"])
        self.assertFalse(result["ntfyServingTLS"]["projectionAloneProvesRenewal"])

    def test_even_available_providers_do_not_grant_activation(self):
        data = inputs()
        data["traefik"]["spec"]["template"]["spec"]["containers"][0]["args"].append(
            "--providers.kubernetescrd=true")
        data["tcp_crd"]["items"] = [{"metadata": {"name": "ingressroutetcps.traefik.io"}}]
        data["namespace"]["items"] = [{"metadata": {"name": "bortus-notifications"}}]
        result = self.scan(data)
        self.assertTrue(result["traefik"]["tcpCRDPresent"])
        self.assertTrue(result["traefik"]["crdProviderEnabled"])
        self.assertIn("registry_publication_not_authorized_or_verified", result["blockers"])
        self.assertTrue(result["productionNtfyNamespacePresent"])
        self.assertFalse(result["activationReady"])

    def test_declared_requests_include_init_overhead_not_completed_pods_or_usage(self):
        result = self.scan(inputs())["node01"]
        self.assertEqual(result["conservativeDeclaredCPUMilli"], 430)
        self.assertEqual(result["conservativeDeclaredMemoryBytes"], 7 * 1024**2)
        self.assertFalse(result["metricsOrSchedulerFitClaimed"])

    def test_incomplete_pod_inventory_cannot_publish_capacity(self):
        data = inputs()
        data["pods"]["metadata"] = {"continue": "next-page"}
        with self.assertRaisesRegex(AssertionError, "pod_inventory_incomplete"):
            self.scan(data)

    def test_reader_failure_propagates_without_a_partial_success_record(self):
        def unavailable(endpoint):
            raise RuntimeError("unavailable")
        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            collect(unavailable)

    def test_cpu_and_memory_units(self):
        for raw, expected in [("150m", "0.150"), ("1Gi", str(1024**3)),
                              ("100M", "100000000"), ("25u", "0.000025"), ("1e3", "1000")]:
            with self.subTest(raw=raw):
                self.assertEqual(quantity(raw), decimal.Decimal(expected))


if __name__ == "__main__":
    unittest.main()
