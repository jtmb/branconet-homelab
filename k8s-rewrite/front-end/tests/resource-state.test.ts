import { test } from "node:test";
import assert from "node:assert/strict";
import { deploymentPods, deploymentState, podRestarts } from "../src/lib/deployment-state";
import { labelPredicate, podFilter } from "../src/lib/pod-query";

test("deployment ownership follows controller UIDs across ambiguous names and labels", () => {
  const dep = { metadata: { name: "api-worker", namespace: "apps", uid: "dep-w" } };
  const sets = [
    { metadata: { name: "api-worker-rs", namespace: "apps", uid: "rs-w", ownerReferences: [{ kind: "Deployment", uid: "dep-w", controller: true }] } },
    { metadata: { name: "api-rs", namespace: "apps", uid: "rs-a", ownerReferences: [{ kind: "Deployment", uid: "dep-a", controller: true }] } },
    { metadata: { name: "cross-ns", namespace: "other", uid: "rs-other", ownerReferences: [{ kind: "Deployment", uid: "dep-w", controller: true }] } },
  ];
  const pod = (name: string, uid?: string, namespace = "apps", controller = true) => ({ metadata: { name, namespace, labels: { app: "same" }, ownerReferences: [{ kind: "ReplicaSet", uid, controller }] } });
  const owned = pod("a-name-with-no-deployment-prefix", "rs-w");
  assert.deepEqual(deploymentPods(dep, [owned, pod("api-worker-false-prefix", "rs-a"), pod("cross-ns", "rs-other", "other"), pod("non-controller", "rs-w", "apps", false), pod("invalid-reference")], sets), [owned]);
  assert.equal(podRestarts({ status: { containerStatuses: [{ restartCount: 7 }], initContainerStatuses: [{ restartCount: 2 }] } }), 9);
});

test("desired replicas, observed generation, zero and paused/failure states are distinct", () => {
  const ready = { metadata: { generation: 2 }, spec: { replicas: 3 }, status: { observedGeneration: 2, replicas: 3, readyReplicas: 3, updatedReplicas: 3, availableReplicas: 3 } };
  assert.equal(deploymentState(ready).state, "Ready");
  assert.equal(deploymentState({ ...ready, status: { ...ready.status, observedGeneration: 1 } }).state, "Reconciling");
  const down = { metadata: { generation: 1 }, spec: { replicas: 0 }, status: { observedGeneration: 1 } };
  assert.equal(deploymentState(down).state, "Scaled down");
  assert.equal(deploymentState(down).ready, "0/0");
  assert.equal(deploymentState({ ...down, status: { ...down.status, replicas: 1 } }).state, "Scaling down");
  assert.equal(deploymentState({ ...ready, spec: { replicas: 4 } }).desiredReplicas, 4);
  assert.equal(deploymentState({ ...ready, spec: { replicas: 4, paused: true } }).state, "Paused");
  assert.equal(deploymentState({ ...ready, status: { ...ready.status, conditions: [{ type: "Progressing", status: "False", reason: "ProgressDeadlineExceeded" }] } }).state, "Failed");
});

test("pod type overrides, namespaces and label expressions are actually enforced", () => {
  const app = { metadata: { namespace: "apps", labels: { app: "worker", tier: "backend" } } };
  const system = { metadata: { namespace: "kube-system", labels: { app: "dns" } } };
  const override = { metadata: { namespace: "apps", labels: { "branconet.io/type": "system", tier: "frontend" } } };
  const pods = [app, system, override];
  assert.deepEqual(pods.filter(podFilter(new URLSearchParams("type=app"))), [app]);
  assert.deepEqual(pods.filter(podFilter(new URLSearchParams("type=system&namespace=apps"))), [override]);
  assert.deepEqual(pods.filter(podFilter(new URLSearchParams("labelSelector=tier%20in%20(backend,frontend),app!=dns"))), [app, override]);
  assert.ok(labelPredicate("!missing,tier notin (frontend),app==worker")(app.metadata.labels));
  assert.ok(labelPredicate("empty=")({ empty: "" }));
  assert.ok(!labelPredicate("empty=")({}));
  for (const query of ["type=invalid", "namespace=apps%20--raw", "labelSelector=tier%20in%20()", "labelSelector=app=worker,", "labelSelector=!app=worker", "labelSelector=bad/key/path=x"]) assert.throws(() => podFilter(new URLSearchParams(query)), { status: 400 });
});
