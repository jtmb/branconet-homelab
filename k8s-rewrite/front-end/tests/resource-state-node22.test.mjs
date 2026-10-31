// DISTINCT NEW three PUBLIC selected-copy controls. Original application modules stay inert.
import infrastructureAssert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
const ts = createRequire(import.meta.url)('typescript');
infrastructureAssert.equal(ts.version, '5.9.3');
const pin = (path, hash) => {
  const text = readFileSync(new URL('../' + path, import.meta.url), 'utf8').replaceAll('\r\n', '\n');
  infrastructureAssert.equal(createHash('sha256').update(text).digest('hex'), hash, path);
  return ts.createSourceFile(path, text, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
};
const deploymentAST = pin('src/lib/deployment-state.ts', '4cc5bd9d3a53f0777839292504d7be172bac1324ef8c2f1ca16544536407a8a6');
const podAST = pin('src/lib/pod-query.ts', 'fe5a030155f1be0a0d2f9cce914545233ab8d44fa8e707831697946fa7e7f3c5');
const validatorAST = pin('src/lib/kubectl-client.ts', '60bc16a6c345cc20c6fc14ffef12ddeb59a84496482f7c84fd48aa6a68d0e584');
const declaration = (tree, name) => {
  const matches = tree.statements.filter(n => (ts.isFunctionDeclaration(n) && n.name?.text === name) || (ts.isVariableStatement(n) && n.declarationList.declarations.length === 1 && n.declarationList.declarations[0].name.getText(tree) === name));
  infrastructureAssert.equal(matches.length, 1, name);
  return matches[0].getText(tree).replace(/^export\s+/, '');
};
const lower = text => {
  const result = ts.transpileModule(text, { reportDiagnostics: true, compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, useDefineForClassFields: true } });
  infrastructureAssert.equal(result.diagnostics.length, 0);
  return result.outputText;
};
class KubernetesCommandError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
const selections = [
  [deploymentAST, ['deploymentPods', 'count', 'deploymentState', 'podRestarts']],
  [podAST, ['SYSTEM_NAMESPACES', 'selectorError', 'validValue', 'validKey', 'labelPredicate', 'podFilter']],
  [validatorAST, ['validateResourceName', 'validateNamespace']],
];
const selectedSource = lower(selections.flatMap(([tree, names]) => names.map(name => declaration(tree, name))).join('\n'));
const { deploymentPods, deploymentState, podRestarts, labelPredicate, podFilter } = vm.runInNewContext('"use strict";\n' + selectedSource + '\n({ deploymentPods, deploymentState, podRestarts, labelPredicate, podFilter })', { KubernetesCommandError }, { timeout: 1000 });
let count = 0;
const control = (...args) => { count++; return test(...args); };
// BEGIN EXACT ORIGINAL TYPE-ERASED PROJECTION
import { test } from "node:test";
import assert from "node:assert/strict";


control("deployment ownership follows controller UIDs across ambiguous names and labels", () => {
    const dep = { metadata: { name: "api-worker", namespace: "apps", uid: "dep-w" } };
    const sets = [
        { metadata: { name: "api-worker-rs", namespace: "apps", uid: "rs-w", ownerReferences: [{ kind: "Deployment", uid: "dep-w", controller: true }] } },
        { metadata: { name: "api-rs", namespace: "apps", uid: "rs-a", ownerReferences: [{ kind: "Deployment", uid: "dep-a", controller: true }] } },
        { metadata: { name: "cross-ns", namespace: "other", uid: "rs-other", ownerReferences: [{ kind: "Deployment", uid: "dep-w", controller: true }] } },
    ];
    const pod = (name, uid, namespace = "apps", controller = true) => ({ metadata: { name, namespace, labels: { app: "same" }, ownerReferences: [{ kind: "ReplicaSet", uid, controller }] } });
    const owned = pod("a-name-with-no-deployment-prefix", "rs-w");
    assert.deepEqual(deploymentPods(dep, [owned, pod("api-worker-false-prefix", "rs-a"), pod("cross-ns", "rs-other", "other"), pod("non-controller", "rs-w", "apps", false), pod("invalid-reference")], sets), [owned]);
    assert.equal(podRestarts({ status: { containerStatuses: [{ restartCount: 7 }], initContainerStatuses: [{ restartCount: 2 }] } }), 9);
});
control("desired replicas, observed generation, zero and paused/failure states are distinct", () => {
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
control("pod type overrides, namespaces and label expressions are actually enforced", () => {
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
    for (const query of ["type=invalid", "namespace=apps%20--raw", "labelSelector=tier%20in%20()", "labelSelector=app=worker,", "labelSelector=!app=worker", "labelSelector=bad/key/path=x"])
        assert.throws(() => podFilter(new URLSearchParams(query)), { status: 400 });
});
// END EXACT ORIGINAL TYPE-ERASED PROJECTION
assert.equal(count, 3);
