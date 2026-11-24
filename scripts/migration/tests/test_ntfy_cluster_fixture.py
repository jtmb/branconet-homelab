import sys
from pathlib import Path
import unittest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ntfy_cluster_fixture import NAMESPACE, EDGE, DENIED, LABEL, OWNER, objects


class ClusterFixtureTests(unittest.TestCase):
    def setUp(self):
        self.items = objects('base-url: https://notifications.lan\nlisten-http: "-"\nlisten-https: ":8443"\n',
                             "private@sha256:fixed", "traefik@sha256:pinned")

    def test_only_isolated_namespaces_no_rbac_secret_or_production_volume_adoption(self):
        for obj in self.items:
            self.assertEqual(obj["metadata"]["labels"][LABEL], OWNER)
            self.assertIn(obj["metadata"].get("namespace", obj["metadata"]["name"]),
                          (NAMESPACE, EDGE, DENIED))
            self.assertNotIn(obj["kind"], ("ClusterRole", "Role", "Secret", "Ingress", "IngressRouteTCP"))
        claim = next(o for o in self.items if o["kind"] == "PersistentVolumeClaim")
        self.assertEqual(claim["spec"]["resources"]["requests"]["storage"], "1Gi")
        self.assertNotIn("volumeName", claim["spec"])
        self.assertNotIn("dataSource", claim["spec"])
        self.assertEqual(claim["metadata"]["annotations"]["helm.sh/resource-policy"], "keep")

    def test_deadlines_nonroot_no_token_and_bounded_resources(self):
        for obj in self.items:
            if obj["kind"] == "Deployment":
                pod = obj["spec"]["template"]["spec"]
            elif obj["kind"] == "Pod":
                pod = obj["spec"]
            else:
                continue
            self.assertFalse(pod["automountServiceAccountToken"])
            self.assertLessEqual(pod["activeDeadlineSeconds"], 900)
            self.assertNotIn("hostNetwork", pod)
            self.assertEqual(pod["securityContext"]["runAsUser"], 1000)
            for container in pod["containers"]:
                self.assertEqual(container["imagePullPolicy"], "Never")
                self.assertEqual(container["securityContext"]["capabilities"]["drop"], ["ALL"])
                self.assertTrue(container["securityContext"]["readOnlyRootFilesystem"])
                self.assertIn("cpu", container["resources"]["limits"])
                self.assertIn("memory", container["resources"]["limits"])

    def test_policy_requires_namespace_and_selected_pod_and_edge_has_no_api_provider(self):
        policy = next(o for o in self.items if o["kind"] == "NetworkPolicy")["spec"]
        self.assertEqual(policy["egress"], [])
        self.assertEqual(policy["ingress"][0]["from"], [{
            "namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": EDGE}},
            "podSelector": {"matchLabels": {"role": "edge"}}}])
        edge = next(o for o in self.items if o["kind"] == "Pod" and o["metadata"]["name"] == "ntfy-edge")
        args = edge["spec"]["containers"][0]["args"]
        self.assertFalse(any("kubernetes" in arg for arg in args))
        config = next(o for o in self.items if o["kind"] == "ConfigMap" and o["metadata"]["namespace"] == EDGE)
        dynamic = yaml.safe_load(config["data"]["qualification.yaml"])
        self.assertEqual(dynamic["tcp"]["routers"]["qualification"]["tls"], {"passthrough": True})
        self.assertIn("control", dynamic["http"]["routers"])


if __name__ == "__main__":
    unittest.main()
