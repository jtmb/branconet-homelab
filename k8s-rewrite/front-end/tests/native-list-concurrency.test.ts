import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import type { V1Secret } from "@kubernetes/client-node";
import { SecretStore, SecretListBudget, SecretError, SECRET_LIST_MAX_BYTES, type SecretTransport } from "../src/lib/cluster-secrets";
import { createSecretTransport, nativeSecrets, nativeRequestDiagnostics } from "../src/lib/secret-client";
import { nativeTlsFixture } from "./helpers/native-tls";

const forbidden = async (): Promise<never> => { throw Error("Unexpected value or mutation request"); };
const deferred = () => { let resolve!: () => void; const promise = new Promise<void>(done => { resolve = done; }); return { promise, resolve }; };
const error503 = (error: unknown) => error instanceof SecretError && error.status === 503;

test("four workers share a budget, keep configured order and expose exact keys only", async () => {
  const scopes = Array.from({ length: 18 }, (_, i) => "scope-" + i), gate = deferred();
  let active = 0, maximum = 0;
  const budgets: SecretListBudget[] = [], calls: string[] = [];
  const data = Object.fromEntries(["__proto__", "constructor", "toString", "empty", "binary", "original_under_score"].map(key => [key, key === "empty" ? "" : Buffer.from([0xff, 0, 1]).toString("base64")]));
  const transport: SecretTransport = { read: forbidden, create: forbidden, replace: forbidden, async list(namespace, options) {
    active++; maximum = Math.max(maximum, active); calls.push(namespace); budgets.push(options!.budget!);
    if (calls.length === 4) gate.resolve();
    try {
      await gate.promise; await new Promise(resolve => setImmediate(resolve));
      const item: V1Secret = { metadata: { namespace, name: "exact", resourceVersion: "7", annotations: { private: "synthetic-hidden-annotation" } }, type: "Opaque", immutable: true, data };
      options!.budget!.consumeBytes(Buffer.byteLength(JSON.stringify(item))); options!.budget!.consumeItems(1);
      options!.visit!(item); return [];
    } finally { active--; }
  } };
  const rows = await new SecretStore(transport, scopes, undefined, 4).list();
  assert.equal(maximum, 4); assert.equal(active, 0); assert.deepEqual(rows.map(row => row.namespace), scopes);
  assert.equal(new Set(budgets).size, 1); assert.equal(budgets[0].items, 18); assert(budgets[0].bytes < SECRET_LIST_MAX_BYTES);
  for (const row of rows) { assert.deepEqual(row.keys, Object.keys(data).sort()); assert.equal(row.resourceVersion, "7"); assert.equal(row.immutable, true); }
  assert(!JSON.stringify(rows).includes("synthetic-hidden-annotation")); assert(!JSON.stringify(rows).includes(data.binary));
});

test("concurrent item/byte quota crossings fail the whole result and start no later scope", async () => {
  for (const quota of ["items", "bytes"] as const) {
    const gate = deferred(), calls: string[] = [], budgets: SecretListBudget[] = [];
    const transport: SecretTransport = { read: forbidden, create: forbidden, replace: forbidden, async list(namespace, options) {
      calls.push(namespace); budgets.push(options!.budget!); if (calls.length === 4) gate.resolve(); await gate.promise;
      if (quota === "items") options!.budget!.consumeItems(3000);
      else options!.budget!.consumeBytes(SECRET_LIST_MAX_BYTES / 4 + 1);
      return [];
    } };
    let result;
    await assert.rejects(async () => { result = await new SecretStore(transport, ["a", "b", "c", "d", "unstarted"], undefined, 4).list(); }, error => error503(error) && (error as Error).message.includes("aggregate"));
    assert.equal(result, undefined); assert.deepEqual(calls, ["a", "b", "c", "d"]);
    assert.equal(new Set(budgets).size, 1); assert(budgets.every(budget => budget.signal.aborted));
    if (quota === "bytes") { const previous = budgets[0].bytes; assert.throws(() => budgets[0].consumeBytes(17), /aggregate/); assert.equal(budgets[0].bytes, previous + 17); }
  }
});

test("a denied scope cancels its siblings, redacts native errors and returns no partial metadata", async () => {
  const gate = deferred(), calls: string[] = []; let active = 0;
  const transport: SecretTransport = { read: forbidden, create: forbidden, replace: forbidden, async list(namespace, options) {
    calls.push(namespace); active++; if (calls.length === 4) gate.resolve();
    try {
      if (namespace === "denied") { await gate.promise; throw { code: 403, body: "synthetic-private-error-body" }; }
      await new Promise<void>((_, reject) => options!.budget!.signal.addEventListener("abort", () => reject(options!.budget!.signal.reason), { once: true }));
      return [];
    } finally { active--; }
  } };
  await assert.rejects(new SecretStore(transport, ["denied", "b", "c", "d", "unstarted"], undefined, 4).list(), error => error503(error) && (error as Error).message === "Kubernetes credentials or Secret RBAC denied access");
  assert.equal(active, 0); assert.deepEqual(calls, ["denied", "b", "c", "d"]);
});

test("invalid concurrency and out-of-scope requests fail before transport work", async () => {
  let calls = 0;
  const transport: SecretTransport = { read: forbidden, create: forbidden, replace: forbidden, async list() { calls++; return []; } };
  for (const concurrency of [0, 9, NaN, 1.5]) await assert.rejects(new SecretStore(transport, ["apps"], undefined, concurrency).list(), error503);
  await assert.rejects(new SecretStore(transport, ["apps"], undefined, 4).list("outside"), error => error instanceof SecretError && error.status === 403);
  assert.equal(calls, 0);
});

async function tlsFixture(operation: (native: Awaited<ReturnType<typeof nativeTlsFixture>>) => Promise<void>, delay = 0) {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-native-parallel-"));
  const keys = ["KUBECONFIG", "BORTUS_SECRET_NAMESPACES", "BORTUS_HISTORY_NAMESPACE"] as const;
  const previous = Object.fromEntries(keys.map(key => [key, process.env[key]]));
  let native: Awaited<ReturnType<typeof nativeTlsFixture>> | undefined;
  try { native = await nativeTlsFixture(dir, delay); process.env.KUBECONFIG = native.config; await operation(native); }
  finally {
    for (const key of keys) { if (previous[key] === undefined) delete process.env[key]; else process.env[key] = previous[key]; }
    await native?.close();
    if (path.dirname(path.resolve(dir)) !== path.resolve(tmpdir()) || !path.basename(dir).startsWith("bortus-native-parallel-")) throw Error("Unsafe native parallel fixture cleanup");
    await rm(dir, { recursive: true, force: true });
  }
}

test("production native factory opts into bounded TLS parallelism and excludes history", { timeout: 30000 }, async () => {
  await tlsFixture(async native => {
    const scopes = Array.from({ length: 18 }, (_, i) => "scope-" + i);
    process.env.BORTUS_SECRET_NAMESPACES = [...scopes, "history"].join(","); process.env.BORTUS_HISTORY_NAMESPACE = "history";
    const expected = new Map<string, { keys: string[]; rv: string; immutable: boolean }>();
    for (let i = 0; i < 334; i++) {
      const data = i % 13 === 0 ? {} : Object.fromEntries(["__proto__", "constructor", "toString", "empty", "binary", "original_under_score"].map(key => [key, key === "empty" ? "" : Buffer.from([0xff, 0, i % 256]).toString("base64")]));
      const item = native.seed(scopes[i % 18], "object-" + i, data, { immutable: i % 7 === 0, metadata: { annotations: { private: "synthetic-only-private-annotation" } } });
      expected.set(scopes[i % 18] + "/object-" + i, { keys: Object.keys(data).sort(), rv: item.metadata!.resourceVersion!, immutable: i % 7 === 0 });
    }
    native.seed("history", "hidden", { field: "" });
    let maximum = 0;
    const observer = setInterval(() => { maximum = Math.max(maximum, nativeRequestDiagnostics().active); }, 1);
    let rows;
    try { rows = await nativeSecrets().list(); } finally { clearInterval(observer); }
    assert.equal(rows.length, 334); assert.equal(maximum, 8);
    assert.equal(new Set(rows.map(row => row.namespace + "/" + row.name)).size, 334);
    for (const row of rows) {
      const reference = expected.get(row.namespace + "/" + row.name)!;
      assert.deepEqual(row.keys, reference.keys); assert.equal(row.resourceVersion, reference.rv); assert.equal(row.immutable, reference.immutable);
      assert.equal(row.type, "Opaque"); assert.equal("data" in row || "annotations" in row || "managedFields" in row, false);
    }
    assert.equal(native.calls.length, 18); assert(native.calls.every(call => call.method === "GET" && call.limit === 200 && !call.metadata && !call.path.includes("/history/")));
    assert.deepEqual(nativeRequestDiagnostics(), { active: 0, queued: 0, maxConcurrent: 8, maxQueued: 64 });
  }, 30);
});

test("TLS queue stays capped at 64; cancelled listings drain without aborting other reads", { timeout: 30000 }, async () => {
  await tlsFixture(async native => {
    native.seed("apps", "blocker", { field: "" });
    const transport = createSecretTransport();
    const blockers = Promise.all(Array.from({ length: 8 }, () => transport.read("apps", "blocker")));
    assert.equal(nativeRequestDiagnostics().active, 8);
    const budgets = Array.from({ length: 65 }, () => new SecretListBudget());
    const queued = Promise.allSettled(budgets.map(budget => transport.list("apps", { budget, visit: () => {} })));
    assert.equal(nativeRequestDiagnostics().queued, 64);
    for (const budget of budgets) budget.fail(new SecretError(503, "Kubernetes Secret list cancelled"));
    const results = await queued;
    assert(results.every(result => result.status === "rejected" && error503(result.reason)));
    assert(results.some(result => result.status === "rejected" && result.reason.message === "Kubernetes Secret request queue is full"));
    assert.equal(nativeRequestDiagnostics().queued, 0); assert.equal(nativeRequestDiagnostics().active, 8);
    assert.equal((await blockers).length, 8);
    assert.equal(native.calls.length, 8); assert(native.calls.every(call => call.path.endsWith("/blocker")));
    assert.deepEqual(nativeRequestDiagnostics(), { active: 0, queued: 0, maxConcurrent: 8, maxQueued: 64 });
  }, 200);
});

test("parallel TLS retry prefixes share the byte ceiling and leave no native work after rejection", { timeout: 30000 }, async () => {
  await tlsFixture(async native => {
    const scopes = ["quota-a", "quota-b", "quota-c", "quota-d", "unstarted"];
    const payload = Buffer.alloc(256 * 1024, 7).toString("base64");
    for (const scope of scopes.slice(0, 4)) for (let i = 0; i < 24; i++) native.seed(scope, "record-" + i, { payload });
    const transport = createSecretTransport(), raw = transport.list.bind(transport), budgets: SecretListBudget[] = [];
    transport.list = async (namespace, options) => { budgets.push(options!.budget!); return raw(namespace, options); };
    const rawSummaries = transport.listSummaries!.bind(transport);
    transport.listSummaries = async (namespace, options) => { budgets.push(options!.budget!); return rawSummaries(namespace, options); };
    await assert.rejects(new SecretStore(transport, scopes, undefined, 4).list(), error => error503(error) && (error as Error).message.includes("aggregate byte"));
    assert.equal(new Set(budgets).size, 1); assert(budgets[0].signal.aborted); assert(budgets[0].bytes > SECRET_LIST_MAX_BYTES);
    assert(!native.calls.some(call => call.path.includes("/unstarted/")));
    for (const scope of scopes.slice(0, 4)) {
      const calls = native.calls.filter(call => call.path.includes("/" + scope + "/"));
      assert.equal(calls[0].limit, 20); assert(calls.some(call => call.limit === 10));
      assert(calls.every(call => call.method === "GET" && [20, 10].includes(call.limit!)));
    }
    assert.deepEqual(nativeRequestDiagnostics(), { active: 0, queued: 0, maxConcurrent: 8, maxQueued: 64 });
  });
});
