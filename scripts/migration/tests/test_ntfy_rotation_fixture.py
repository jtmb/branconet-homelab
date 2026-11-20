from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ntfy_cluster_fixture import NAMESPACE
from ntfy_rotation_fixture import identity, job, cron


class RotationFixtureTests(unittest.TestCase):
    def test_identity_cannot_list_secrets_approve_or_mint_and_patches_only_one_deployment(self):
        items = identity()
        self.assertFalse(any(o["kind"] in ("Secret", "ClusterRole", "ClusterRoleBinding") for o in items))
        role = next(o for o in items if o["kind"] == "Role")
        self.assertEqual(role["metadata"]["namespace"], NAMESPACE)
        for rule in role["rules"]:
            self.assertFalse(set(rule["verbs"]) & {"list", "watch", "create", "delete", "update", "approve"})
            if "patch" in rule["verbs"]:
                self.assertEqual(rule["resources"], ["deployments"])
                self.assertEqual(rule["resourceNames"], ["private-ntfy"])
            if rule["resources"] == ["secrets"]:
                self.assertEqual(rule["resourceNames"], ["synthetic-leaf"])
        self.assertEqual([r for r in role["rules"] if r["resources"] == ["certificaterequests"]][0]["verbs"], ["get"])

    def test_job_has_audience_bound_token_public_only_certificate_and_actual_deadline(self):
        spec = job("diagnostic")["spec"]
        self.assertEqual(spec["activeDeadlineSeconds"], 60)
        self.assertEqual(spec["backoffLimit"], 0)
        pod = spec["template"]["spec"]
        self.assertFalse(pod["automountServiceAccountToken"])
        self.assertEqual(pod["restartPolicy"], "Never")
        token = next(v for v in pod["volumes"] if v["name"] == "credentials")["projected"]["sources"][0]["serviceAccountToken"]
        self.assertEqual(token["expirationSeconds"], 600)
        self.assertEqual(token["audience"], "https://kubernetes.default.svc.cluster.local")
        public = next(v for v in pod["volumes"] if v["name"] == "public-leaf")["secret"]["items"]
        self.assertEqual({v["key"] for v in public}, {"tls.crt", "ca.crt"})
        container = pod["containers"][0]
        self.assertTrue(container["securityContext"]["readOnlyRootFilesystem"])
        self.assertEqual(container["securityContext"]["capabilities"]["drop"], ["ALL"])
        self.assertEqual(container["resources"]["limits"], {"cpu": "100m", "memory": "128Mi"})

    def test_cron_starts_suspended_has_no_overlap_or_unbounded_catchup(self):
        c = cron()["spec"]
        self.assertTrue(c["suspend"])
        self.assertEqual(c["concurrencyPolicy"], "Forbid")
        self.assertEqual(c["startingDeadlineSeconds"], 30)
        self.assertEqual(c["jobTemplate"]["spec"]["activeDeadlineSeconds"], 60)
        self.assertEqual(c["successfulJobsHistoryLimit"], 2)
        self.assertEqual(c["failedJobsHistoryLimit"], 2)


if __name__ == "__main__":
    unittest.main()
