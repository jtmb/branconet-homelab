import { test } from "node:test";
import assert from "node:assert/strict";
import { deploymentPods, deploymentState, podRestarts } from "../src/lib/deployment-state";

test("rolling deployment combines arbitrary old and new ReplicaSet owners without foreign or orphan pods", () => {
  const deployment = { metadata: { name: "api", namespace: "apps", uid: "deployment-current", generation: 7 }, spec: { replicas: 3 },
    status: { observedGeneration: 7, replicas: 4, readyReplicas: 3, updatedReplicas: 2, availableReplicas: 3 } };
  const replicaSet = (name: string, uid: string, owner: string, namespace = "apps", controller = true) => ({ metadata: {
    name, uid, namespace, ownerReferences: [{ kind: "Deployment", uid: owner, controller }],
  } });
  const sets = [replicaSet("unrelated-old-revision", "rs-old", "deployment-current"),
    replicaSet("arbitrary-new-revision", "rs-new", "deployment-current"),
    replicaSet("api-matching-name", "rs-foreign", "deployment-foreign"),
    replicaSet("cross-namespace", "rs-cross", "deployment-current", "other"),
    replicaSet("not-controller", "rs-not-controller", "deployment-current", "apps", false)];
  const pod = (name: string, owner: string, namespace = "apps", controller = true) => ({ metadata: {
    name, namespace, labels: { app: "api" }, ownerReferences: [{ kind: "ReplicaSet", uid: owner, controller }],
  } });
  const old = { ...pod("does-not-start-with-api", "rs-old"), status: {
    containerStatuses: [{ restartCount: 4 }, { restartCount: 2 }], initContainerStatuses: [{ restartCount: 1 }],
  } };
  const fresh = { ...pod("different-revision-name", "rs-new"), status: {
    containerStatuses: [{ restartCount: 3 }, { restartCount: 0 }], initContainerStatuses: [{ restartCount: 2 }],
  } };
  const pending = pod("new-pending-without-status", "rs-new");
  const foreign = { ...pod("api-false-prefix", "rs-foreign"), status: { containerStatuses: [{ restartCount: 999 }] } };
  const orphan = { metadata: { name: "api-orphan", namespace: "apps", labels: { app: "api" } } };
  const selected = deploymentPods(deployment, [old, foreign, fresh, orphan, pod("wrong-namespace", "rs-cross", "other"),
    pod("wrong-controller", "rs-old", "apps", false), pod("unowned-replicaset", "rs-not-controller"), pending], sets);
  assert.deepEqual(selected, [old, fresh, pending]);
  assert.equal(selected.reduce((total, item) => total + podRestarts(item), 0), 12);
  assert.deepEqual(deploymentPods({ metadata: { name: "api", namespace: "apps" } }, [old, fresh], sets), []);
  assert.equal(deploymentState(deployment).state, "Updating");
  assert.equal(deploymentState(deployment).ready, "3/3");
});

test("missing deployment status cannot report desired replicas as observed or ready", () => {
  assert.deepEqual(deploymentState({ metadata: { generation: 7 }, spec: { replicas: 3 } }), {
    state: "Reconciling", health: "Progressing", desiredReplicas: 3, observedReplicas: 0, readyReplicas: 0,
    updatedReplicas: 0, availableReplicas: 0, generation: 7, observedGeneration: 0, ready: "0/3", upToDate: 0, available: 0,
  });
  assert.deepEqual(deploymentState({}), {
    state: "Updating", health: "Progressing", desiredReplicas: 1, observedReplicas: 0, readyReplicas: 0,
    updatedReplicas: 0, availableReplicas: 0, generation: 0, observedGeneration: 0, ready: "0/1", upToDate: 0, available: 0,
  });
});

test("zero desired replicas distinguish incomplete observation, draining pods and completed scale-down", () => {
  const deployment = { metadata: { generation: 7 }, spec: { replicas: 0 } };
  assert.equal(deploymentState(deployment).state, "Reconciling");
  assert.deepEqual(deploymentState({ ...deployment, status: { observedGeneration: 7 } }), {
    state: "Scaled down", health: "Healthy", desiredReplicas: 0, observedReplicas: 0, readyReplicas: 0,
    updatedReplicas: 0, availableReplicas: 0, generation: 7, observedGeneration: 7, ready: "0/0", upToDate: 0, available: 0,
  });
  const draining = deploymentState({ ...deployment, status: {
    observedGeneration: 7, replicas: 2, readyReplicas: 1, updatedReplicas: 0, availableReplicas: 1,
  } });
  assert.equal(draining.state, "Scaling down");
  assert.equal(draining.health, "Progressing");
  assert.equal(draining.desiredReplicas, 0);
  assert.equal(draining.observedReplicas, 2);
  assert.equal(draining.ready, "1/0");
});
