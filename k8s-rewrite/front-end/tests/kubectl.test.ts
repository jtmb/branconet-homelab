import { test } from "node:test";
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
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

test("process pool bounds concurrency, queue capacity and queue deadlines", async () => {
  let release!: (value: { stdout: string }) => void;
  let calls = 0;
  const client = createKubectlClient(async () => { calls++; return new Promise(resolve => { release = resolve; }); }, () => true, () => [], { concurrent: 1, queued: 1 });
  const first = client.exec(["get", "pods"], 1000);
  await new Promise(resolve => setImmediate(resolve));
  const queued = client.exec(["get", "nodes"], 30);
  try {
    await assert.rejects(client.exec(["get", "services"]), { status: 503 });
    await assert.rejects(queued, { status: 504 });
    assert.equal(calls, 1, "timed out queue entry started a subprocess");
    assert.equal(client.diagnostics().queued, 0);
  } finally { release({ stdout: "done" }); await first; }
  assert.equal(client.diagnostics().active, 0);
  let concurrent = 0, peak = 0;
  const bounded = createKubectlClient(async () => {
    concurrent++; peak = Math.max(peak, concurrent);
    await new Promise(resolve => setTimeout(resolve, 5));
    concurrent--; return { stdout: "{}" };
  }, () => true, () => [], { concurrent: 2, queued: 10 });
  await Promise.all(Array.from({ length: 8 }, () => bounded.exec(["get", "pods"])));
  assert.equal(peak, 2);
  assert.equal(bounded.diagnostics().queued, 0);
});

test("JSON reads reject invalid output instead of producing null success", async () => {
  for (const stdout of ["", "private-response-marker", "null", "42"]) {
    const client = createKubectlClient(async () => ({ stdout }), () => true, () => []);
    await assert.rejects(client.json(["get", "pods"]), { status: 502, message: "Invalid Kubernetes JSON response" });
  }
});

test("real child output and timeout bounds produce fixed errors", async () => {
  const run = promisify(execFile);
  const oversized = createKubectlClient((_, options) => run(process.execPath, ["-e", "process.stdout.write('fake-output-marker'.repeat(200000))"], options), () => true, () => []);
  await assert.rejects(oversized.exec(["get", "pods"]), { status: 502, message: "Cluster response exceeds the size limit" });
  const stalled = createKubectlClient((_, options) => run(process.execPath, ["-e", "setTimeout(()=>{},10000)"], options), () => true, () => []);
  await assert.rejects(stalled.exec(["get", "pods"], 100), { status: 504, message: "Kubernetes request timed out" });
  assert.equal(stalled.diagnostics().active, 0);
});
