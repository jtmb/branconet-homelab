import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createContext, runInContext, type Context } from "node:vm";
import ts from "typescript";
import type * as Kubectl from "../src/lib/kubectl-client";

const compiled = ts.transpileModule(readFileSync("src/lib/kubectl-client.ts", "utf8"), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText;

function load(context: Context): typeof Kubectl {
  const exports = {};
  runInContext(`(function(exports) { ${compiled}\n})`, context)(exports);
  return exports as typeof Kubectl;
}

test("independent route module loads recognize errors from the retained kubectl client", async () => {
  const context = createContext({});
  const first = load(context);
  const client = first.createKubectlClient(async () => { throw Error("synthetic private process output"); }, () => true, () => []);
  const second = load(context);
  assert.equal(first.KubernetesCommandError, second.KubernetesCommandError);
  await assert.rejects(client.exec(["scale", "deployment/demo"]), error => {
    assert.ok(error instanceof second.KubernetesCommandError);
    assert.equal(error.status, 502);
    assert.equal(error.message, "Kubernetes command failed");
    return true;
  });
  assert.equal(Object.assign(Error("untrusted"), { status: 502 }) instanceof second.KubernetesCommandError, false);
  assert.notEqual(load(createContext({})).KubernetesCommandError, second.KubernetesCommandError);
});
