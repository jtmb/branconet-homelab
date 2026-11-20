"""Pod-pinning semantics for the Certificates UI release verifier.

Regression test for the 2026-11-18 finding: the verifier compared a digest
prefix against the desired template and then exec'd into whichever pod the
deployment selector picked, so a rollout could pass against a healthy old
pod before the new image served anything. select_verified_pod must now
require the exact pinned image on a Ready pod of the deployment's current
ReplicaSet, after the deployment is fully reconciled.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "rel", Path(__file__).resolve().parents[1] / "verify-certificates-ui-release.py")
REL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REL)

DIGEST = REL.EXPECTED_IMAGE[REL.EXPECTED_IMAGE.index("sha256:"):]
OLD_IMAGE = "docker.io/jtmb92/bortus@sha256:" + "0" * 64


def deployment(generation=2, observed=2, revision="2", image=REL.EXPECTED_IMAGE):
    return {"metadata": {"name": "bortus", "uid": "deploy-uid", "generation": generation,
                         "annotations": {"deployment.kubernetes.io/revision": revision}},
            "spec": {"template": {"spec": {"containers": [{"name": "bortus", "image": image}]}}},
            "status": {"observedGeneration": observed, "readyReplicas": 1}}


def replicaset(uid, revision, owner="deploy-uid"):
    return {"metadata": {"name": f"rs-{revision}", "uid": uid,
                         "annotations": {"deployment.kubernetes.io/revision": revision},
                         "ownerReferences": [{"uid": owner}]}}


def pod(name, owner, image, ready=True, phase="Running"):
    return {"metadata": {"name": name, "ownerReferences": [{"uid": owner}]},
            "spec": {"containers": [{"name": "bortus", "image": image}]},
            "status": {"phase": phase,
                       "containerStatuses": [{"ready": ready, "restartCount": 0,
                                              "imageID": "docker.io/jtmb92/bortus@" + image[image.index("sha256:"):] if "sha256:" in image else ""}]}}


class PodPinningTests(unittest.TestCase):
    def test_new_release_requires_its_own_immutable_pin(self):
        rs = replicaset("rs-new", "2")
        current = pod("bortus-next", "rs-new", OLD_IMAGE)
        deployed = deployment(image=OLD_IMAGE)
        self.assertIsNone(REL.select_verified_pod(deployed, [rs], [current])[0])
        self.assertEqual(REL.select_verified_pod(deployed, [rs], [current], OLD_IMAGE), (current, []))

    def test_healthy_old_pod_cannot_pass_a_partial_rollout(self):
        # The exact 2026-11-18 finding: old pod Ready and already containing
        # the routes, new pod not Ready yet. The verifier must refuse.
        old_rs = replicaset("rs-old-uid", "1")
        new_rs = replicaset("rs-new-uid", "2")
        old_pod = pod("bortus-old", "rs-old-uid", OLD_IMAGE, ready=True)
        new_pod = pod("bortus-new", "rs-new-uid", REL.EXPECTED_IMAGE, ready=False)
        selected, reasons = REL.select_verified_pod(
            deployment(), [old_rs, new_rs], [old_pod, new_pod])
        self.assertIsNone(selected)
        self.assertIn("current_rollout_has_no_ready_pod", reasons)

    def test_a_fully_reconciled_rollout_returns_its_own_ready_pod(self):
        rs = replicaset("rs-2-uid", "2")
        current = pod("bortus-abc", "rs-2-uid", REL.EXPECTED_IMAGE, ready=True)
        old = pod("bortus-old", "rs-old-uid", OLD_IMAGE, ready=True)
        selected, reasons = REL.select_verified_pod(deployment(), [replicaset("rs-old-uid", "1"), rs], [old, current])
        self.assertEqual(selected["metadata"]["name"], "bortus-abc")
        self.assertEqual(reasons, [])

    def test_an_unreconciled_deployment_is_refused(self):
        rs = replicaset("rs-2-uid", "2")
        current = pod("bortus-abc", "rs-2-uid", REL.EXPECTED_IMAGE, ready=True)
        selected, reasons = REL.select_verified_pod(
            deployment(observed=1), [rs], [current])
        self.assertIsNone(selected)
        self.assertIn("deployment_not_reconciled", reasons)

    def test_a_wrong_pinned_digest_is_refused_even_with_a_ready_pod(self):
        # Guards against verifying the wrong release: the digest must match
        # exactly, never by prefix.
        rs = replicaset("rs-2-uid", "2")
        current = pod("bortus-abc", "rs-2-uid", "docker.io/jtmb92/bortus@" + DIGEST, ready=True)
        selected, reasons = REL.select_verified_pod(
            deployment(image="docker.io/jtmb92/bortus@" + DIGEST[:-1] + "f"),
            [rs], [current])
        self.assertIsNone(selected)
        self.assertIn("desired_image_is_not_the_pinned_digest", reasons)

    def test_a_ready_current_pod_running_the_old_image_is_refused(self):
        rs = replicaset("rs-2-uid", "2")
        wrong = pod("bortus-abc", "rs-2-uid", OLD_IMAGE, ready=True)
        selected, reasons = REL.select_verified_pod(deployment(), [rs], [wrong])
        self.assertIsNone(selected)
        self.assertIn("ready_pod_does_not_run_the_pinned_image", reasons)


if __name__ == "__main__":
    unittest.main()
