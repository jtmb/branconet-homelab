import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import { NextRequest, NextResponse } from "next/server";
import { clusterRoute } from "../src/lib/cluster-http";
import { KubernetesCommandError, validateNamespace, validateResourceName } from "../src/lib/kubectl-client";

// Execute the actual route with real Next request/response and boundary validators.
// Only authorization/CLI/cache dependencies are controlled; no cluster is contacted.
function fixture(denied = false, failure?: KubernetesCommandError) {
  const calls: { argv: string[]; timeout: number }[] = [];
  let invalidations = 0, authorizationCalls = 0;
  const source = readFileSync(resolve("src/app/api/cluster/deployments/[namespace]/[name]/action/route.ts"), "utf8");
  const exports: Record<string, unknown> = {};
  const dependencies: Record<string, unknown> = {
    "next/server": { NextRequest, NextResponse },
    "@/lib/k8s": { KubernetesCommandError, validateNamespace, validateResourceName, kubectlExec: async (argv: string[], timeout: number) => {
      calls.push({ argv: Array.from(argv), timeout });
      if (failure) throw failure;
      return "";
    } },
    "@/lib/cluster-http": { clusterRoute },
    "@/lib/cluster-cache": { invalidateCache: () => { invalidations++; } },
    "@/lib/permissions": { requireOperator: async () => {
      authorizationCalls++;
      return denied ? NextResponse.json({ error: "Forbidden" }, { status: 403 }) : { id: "synthetic", sessionVersion: 0 };
    } },
  };
  runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, {
    exports, require: (name: string) => { assert.ok(Object.hasOwn(dependencies, name)); return dependencies[name]; },
  });
  const post = exports.POST as (request: NextRequest, context: { params: Promise<{ namespace: string; name: string }> }) => Promise<Response>;
  return {
    calls, state: () => ({ invalidations, authorizationCalls }),
    send: (body: unknown, params = { namespace: "apps", name: "demo" }) => post(new NextRequest("http://localhost/api/cluster/deployments/apps/demo/action", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }), { params: Promise.resolve(params) }),
    post,
  };
}

test("deployment actions reject coerced/inherited/unknown action shapes before execution", async () => {
  const f = fixture();
  for (const action of [["restart"], ["pause"], [], {}, 0, true, null, "__proto__", "constructor", "toString", "restart --server=other", "public-rejected-input"]) {
    const response = await f.send({ action });
    assert.equal(response.status, 400);
    assert.deepEqual(await response.json(), { error: "Invalid deployment action" });
  }
  for (const body of [null, {}, []]) assert.equal((await f.send(body)).status, 400);
  assert.equal(f.calls.length, 0);
  assert.equal(f.state().invalidations, 0);
});

test("all four deployment actions preserve exact argv, timeout and successful empty stdout", async () => {
  const f = fixture();
  for (const [action, command] of [["restart", "restart"], ["rollback", "undo"], ["pause", "pause"], ["resume", "resume"]]) {
    const response = await f.send({ action });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { success: true });
    assert.deepEqual(f.calls.at(-1), { argv: ["rollout", command, "deployment", "demo", "-n", "apps"], timeout: 15000 });
  }
  assert.deepEqual(f.state(), { invalidations: 4, authorizationCalls: 4 });
});

test("deployment target validation rejects flags and separators without CLI work", async () => {
  const f = fixture();
  for (const params of [{ namespace: "apps --server=other", name: "demo" }, { namespace: "apps", name: "--raw=/version" }, { namespace: "apps", name: "demo%2Fother" }]) {
    assert.equal((await f.send({ action: "restart" }, params)).status, 400);
  }
  assert.equal(f.calls.length, 0);
  assert.equal(f.state().invalidations, 0);
});

test("fresh deployment authorization denies before resolving params or reading request body", async () => {
  const f = fixture(true);
  const request = { json: async () => { throw Error("Body must not be read"); } } as unknown as NextRequest;
  let resolutions = 0;
  const context = { params: { then: () => { resolutions++; throw Error("Params must not resolve"); } } as unknown as Promise<{ namespace: string; name: string }> };
  assert.equal((await f.post(request, context)).status, 403);
  assert.equal(f.calls.length, 0);
  assert.equal(resolutions, 0);
  assert.deepEqual(f.state(), { invalidations: 0, authorizationCalls: 1 });
});

test("deployment command refusal preserves typed status and does not invalidate as success", async () => {
  for (const status of [403, 409, 502, 504]) {
    const f = fixture(false, new KubernetesCommandError(status, "Fixed command refusal"));
    const response = await f.send({ action: "restart" });
    assert.equal(response.status, status);
    assert.deepEqual(await response.json(), { error: "Fixed command refusal" });
    assert.equal(f.calls.length, 1);
    assert.equal(f.state().invalidations, 0);
  }
});

test("malformed deployment JSON remains a fixed400 without CLI work", async () => {
  const f = fixture();
  const response = await f.post(new NextRequest("http://localhost/action", { method: "POST", body: "{" }), { params: Promise.resolve({ namespace: "apps", name: "demo" }) });
  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { error: "Invalid request" });
  assert.equal(f.calls.length, 0);
});
