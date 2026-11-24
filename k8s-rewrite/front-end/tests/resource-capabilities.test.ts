import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { RESOURCE_CAPABILITIES, resourceBase, type ResourceType } from "../src/lib/resource-capabilities";
import { validateResourceYaml } from "../src/lib/resource-yaml";
import { runtimeCapabilities } from "../src/lib/runtime-capabilities";

test("every declared resource read/edit/delete/action capability has a matching handler", () => {
  for (const [type, capability] of Object.entries(RESOURCE_CAPABILITIES)) {
    const target = type === "node" ? "[hostname]" : capability.namespaced ? "[namespace]/[name]" : "[name]";
    const root = `src/app/api/cluster/${capability.collection}/${target}`;
    assert.ok(existsSync(`${root}/yaml/route.ts`), `${type} YAML route`);
    if (capability.delete) assert.ok(existsSync(`${root}/delete/route.ts`), `${type} delete route`);
    if (capability.logs) assert.ok(existsSync(`${root}/logs/route.ts`), `${type} log route`);
    if (capability.actions.length) assert.ok(existsSync(`${root}/action/route.ts`), `${type} action route`);
    assert.ok(resourceBase(type as ResourceType, "apps", "name --raw").endsWith("name%20--raw"));
  }
  assert.ok(existsSync("src/app/api/cluster/pods/[namespace]/[name]/exec/route.ts"));
});

test("resource YAML cannot switch identity/kind, apply a list, or bypass resourceVersion", () => {
  const valid = 'apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: demo\n  namespace: apps\n  resourceVersion: "10"\nspec:\n  replicas: 0\n';
  assert.equal(validateResourceYaml("deployment", "demo", "apps", valid), valid);
  for (const invalid of [
    valid.replace("name: demo", "name: other"), valid.replace("namespace: apps", "namespace: other"),
    valid.replace("kind: Deployment", "kind: Secret"), valid.replace("apiVersion: apps/v1", "apiVersion: v1"),
    `${valid}\n---\n${valid}`, "kind: [", null, "x".repeat(262145),
  ]) assert.throws(() => validateResourceYaml("deployment", "demo", "apps", invalid), { status: 400 });
  assert.throws(() => validateResourceYaml("deployment", "demo", "apps", valid.replace('  resourceVersion: "10"\n', "")), { status: 428 });
  assert.throws(() => validateResourceYaml("deployment", "demo", "apps", valid.replace('resourceVersion: "10"', "resourceVersion: 10")), { status: 428 });
});

test("runtime capability flags match provisioning and shell server boundaries", () => {
  assert.deepEqual(runtimeCapabilities({}, "linux"), { provisioning: true, operatorShell: true, podExec: true });
  assert.equal(runtimeCapabilities({}, "win32").operatorShell, false);
  assert.equal(runtimeCapabilities({ KUBERNETES_SERVICE_HOST: "fixture" }, "linux").provisioning, false);
  assert.deepEqual(runtimeCapabilities({ BORTUS_DISABLE_PROVISIONING: "true", BORTUS_DISABLE_OPERATOR_SHELL: "true", BORTUS_DISABLE_POD_EXEC: "true" }, "linux"), { provisioning: false, operatorShell: false, podExec: false });
});
