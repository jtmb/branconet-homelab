import { test } from "node:test";
import assert from "node:assert/strict";
import { createKubectlClient, KubernetesCommandError, validateNamespace, validateResourceName } from "../src/lib/kubectl-client";
import { clusterRoute } from "../src/lib/cluster-http";

test("structured kubectl preserves argument boundaries, patches and file paths", async () => {
  const calls: string[][] = [];
  const client = createKubectlClient(async (args, options) => {
    calls.push(args);
    assert.equal(options.maxBuffer, 2 * 1024 * 1024);
    return { stdout: "" };
  }, () => true, () => ["--kubeconfig", "C:/test path/config"]);
  const patch = JSON.stringify({ spec: { suspend: true } });
  assert.equal(await client.exec(["patch", "gitrepository", "source", "-p", patch]), "");
  await client.exec(["apply", "-f", "C:/test path/manifest.yaml"]);
  assert.deepEqual(calls, [
    ["--kubeconfig", "C:/test path/config", "patch", "gitrepository", "source", "-p", patch],
    ["--kubeconfig", "C:/test path/config", "apply", "-f", "C:/test path/manifest.yaml"],
  ]);
});

test("resource boundaries reject option and path injection before execution", async () => {
  let calls = 0;
  const client = createKubectlClient(async () => { calls++; return { stdout: "" }; }, () => true, () => []);
  for (const name of ["", "--raw=/api/v1/secrets", "apps --server x", "apps/name", "apps%2Fname", "a..b", "a.-b", "a\0b", "A", "a".repeat(254)]) {
    assert.throws(() => validateResourceName(name), { status: 400 });
  }
  for (const ns of ["a.b", "a".repeat(64), "-apps", "apps "]) assert.throws(() => validateNamespace(ns), { status: 400 });
  assert.equal(validateResourceName("node.example.local"), "node.example.local");
  assert.equal(validateNamespace("apps-1"), "apps-1");
  for (const args of [[], "get pods", ["get", "a\0b"]]) await assert.rejects(client.exec(args as string[]), { status: 400 });
  assert.equal(calls, 0);
});

test("failed subprocess output never becomes a successful mutation or public error", async () => {
  const marker = "private-value-marker";
  for (const [error, status] of [
    [{ code: 1, stdout: marker, stderr: marker }, 502],
    [{ code: "ENOENT", message: marker }, 503],
    [{ killed: true, stdout: marker }, 504],
    [{ code: "ERR_CHILD_PROCESS_STDIO_MAXBUFFER", stderr: marker }, 502],
    [{ code: 1, stderr: `Forbidden ${marker}` }, 403],
    [{ code: 1, stderr: `NotFound ${marker}` }, 404],
    [null, 502],
  ] as const) {
    const client = createKubectlClient(async () => { throw error; }, () => true, () => []);
    let actual: unknown;
    try { await client.exec(["delete", "pod", "demo"]); } catch (caught) { actual = caught; }
    assert.ok(actual instanceof KubernetesCommandError);
    assert.equal(actual.status, status);
    assert.ok(!String(actual).includes(marker) && !JSON.stringify(actual).includes(marker));
    const response = await clusterRoute(async () => { throw actual; });
    assert.equal(response.status, status);
    assert.ok(!(await response.text()).includes(marker));
  }
  const unavailable = createKubectlClient(async () => { throw Error("must not execute"); }, () => false, () => []);
  await assert.rejects(unavailable.exec(["get", "nodes"]), { status: 503 });
});
