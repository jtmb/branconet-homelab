import importlib.util
import pathlib
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "inspect-bortus-release-rbac.py"
SPEC = importlib.util.spec_from_file_location("release_rbac", SOURCE)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def role(name, namespace=None):
    return {"metadata": {"name": name, "namespace": namespace, "uid": "role-uid",
                         "resourceVersion": "7"},
            "rules": [{"apiGroups": [""], "resources": ["secrets"], "verbs": ["get"]}]}


def binding(name, subjects, namespace="bortus", ref_kind="Role", ref_name="native"):
    return {"metadata": {"name": name, "namespace": namespace, "uid": "binding-uid",
                         "resourceVersion": "9"}, "subjects": subjects,
            "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": ref_kind,
                        "name": ref_name}}


class RbacInventoryTests(unittest.TestCase):
    def test_direct_username_and_group_grants_with_unrelated_subjects_preserved(self):
        snapshot = {"roles": [role("native", "bortus")], "clusterroles": [role("discovery")],
                    "rolebindings": [
                        binding("direct", [{"kind": "ServiceAccount", "name": "bortus"},
                                           {"kind": "ServiceAccount", "name": "unrelated"}]),
                        binding("username", [{"kind": "User", "name": "system:serviceaccount:bortus:bortus"}])],
                    "clusterrolebindings": [binding("group", [{"kind": "Group", "name": "system:authenticated"}],
                                                     None, "ClusterRole", "discovery")]}
        result = AUDIT.inventory(snapshot, "bortus", "bortus")
        self.assertEqual(result["matchingBindingCount"], 3)
        self.assertEqual(result["unresolvedRoleCount"], 0)
        direct = next(g for g in result["grants"] if g["binding"]["name"] == "direct")
        self.assertEqual(direct["unmatchedSubjectCount"], 1)
        self.assertEqual(direct["binding"]["resourceVersion"], "9")
        self.assertEqual(direct["roleResourceVersion"], "7")
        self.assertEqual(direct["scope"], "bortus")
        self.assertEqual(result["grants"][0]["scope"], "cluster")
        self.assertEqual(len(snapshot["rolebindings"][0]["subjects"]), 2)

    def test_namespace_boundary_and_clusterrole_scoping(self):
        subject = {"kind": "ServiceAccount", "name": "bortus"}
        snapshot = {"roles": [], "clusterroles": [role("native")], "clusterrolebindings": [],
                    "rolebindings": [
                        binding("other-account", [subject], "other", "ClusterRole"),
                        binding("explicit-account", [{**subject, "namespace": "bortus"}], "other", "ClusterRole"),
                        binding("other-group", [{"kind": "Group", "name": "system:serviceaccounts:other"}], "other", "ClusterRole"),
                        binding("namespace-group", [{"kind": "Group", "name": "system:serviceaccounts:bortus"}], "other", "ClusterRole")]}
        result = AUDIT.inventory(snapshot, "bortus", "bortus")
        self.assertEqual([g["binding"]["name"] for g in result["grants"]],
                         ["explicit-account", "namespace-group"])
        self.assertTrue(all(g["scope"] == "other" for g in result["grants"]))

    def test_missing_role_is_explicit_and_aggregation_is_not_a_convergence_claim(self):
        subject = {"kind": "Group", "name": "system:serviceaccounts"}
        aggregated = {**role("aggregate"), "aggregationRule": {"clusterRoleSelectors": []}}
        snapshot = {"roles": [], "clusterroles": [aggregated], "rolebindings": [],
                    "clusterrolebindings": [binding("missing", [subject], None, "ClusterRole", "absent"),
                                            binding("aggregate", [subject], None, "ClusterRole", "aggregate")]}
        result = AUDIT.inventory(snapshot, "bortus", "bortus")
        self.assertEqual(result["unresolvedRoleCount"], 1)
        missing = next(g for g in result["grants"] if g["binding"]["name"] == "missing")
        self.assertFalse(missing["roleResolved"])
        self.assertEqual(missing["rules"], [])
        self.assertTrue(result["grants"][0]["aggregationRulePresent"])
        self.assertTrue(any("not proof" in line for line in result["limitations"]))


if __name__ == "__main__":
    unittest.main()
