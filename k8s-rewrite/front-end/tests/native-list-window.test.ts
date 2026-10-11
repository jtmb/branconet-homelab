import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { SecretStore, SecretListBudget, SecretError, SECRET_LIST_MAX_BYTES, secretSummary } from "../src/lib/cluster-secrets";
import { createSecretTransport, nativeSecrets, nativeRequestDiagnostics } from "../src/lib/secret-client";
import { nativeTlsFixture } from "./helpers/native-tls";

const error503 = (error: unknown) => error instanceof SecretError && error.status === 503;
const idle = () => assert.deepEqual(nativeRequestDiagnostics(), { active: 0, queued: 0, maxConcurrent: 4, maxQueued: 64 });
async function fixture(operation: (native: Awaited<ReturnType<typeof nativeTlsFixture>>) => Promise<void>, delay = 0) {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-native-window-"));
  const keys = ["KUBECONFIG", "BORTUS_SECRET_NAMESPACES", "BORTUS_HISTORY_NAMESPACE"] as const;
  const previous = Object.fromEntries(keys.map(key => [key, process.env[key]]));
  let native: Awaited<ReturnType<typeof nativeTlsFixture>> | undefined;
  try { native = await nativeTlsFixture(dir, delay); process.env.KUBECONFIG = native.config; await operation(native); }
  finally {
    for (const key of keys) { if (previous[key] === undefined) delete process.env[key]; else process.env[key] = previous[key]; }
    await native?.close();
    if (path.dirname(path.resolve(dir)) !== path.resolve(tmpdir()) || !path.basename(dir).startsWith("bortus-native-window-")) throw Error("Unsafe native window fixture cleanup");
    await rm(dir, { recursive: true, force: true });
  }
}

test("production 200-object windows return exact 1000/10000-object TLS inventories with bounded calls", { timeout: 30000 }, async () => {
  await fixture(async native => {
    const scopes = Array.from({ length: 18 }, (_, i) => "scope-" + i);
    process.env.BORTUS_SECRET_NAMESPACES = [...scopes, "history"].join(","); process.env.BORTUS_HISTORY_NAMESPACE = "history";
    for (const count of [1000, 10000]) {
      native.reset();
      const expected: ReturnType<typeof secretSummary>[] = [];
      for (let i = 0; i < count; i++) {
        const data = i % 17 === 0 ? {} : Object.fromEntries(["__proto__", "constructor", "toString", "empty", "binary", "original_under_score"].map(key => [key, key === "empty" ? "" : Buffer.from([0xff, 0, i % 256]).toString("base64")]));
        native.seed(scopes[i % 18], "object-" + i, data, { type: i % 11 ? "Opaque" : "kubernetes.io/tls", immutable: i % 7 === 0, metadata: { annotations: { private: "synthetic-window-hidden-annotation" } } });
        // Fixture parameters define the oracle independently of the production projection.
        expected.push({ namespace: scopes[i % 18], name: "object-" + i, resourceVersion: String(i + 1), type: i % 11 ? "Opaque" : "kubernetes.io/tls", immutable: i % 7 === 0,
          keys: i % 17 === 0 ? [] : ["__proto__", "binary", "constructor", "empty", "original_under_score", "toString"] });
      }
      native.seed("history", "hidden", { field: "" });
      const rows = await nativeSecrets().list();
      const ordered = scopes.flatMap(scope => expected.filter(row => row.namespace === scope));
      assert.deepEqual(rows, ordered); assert.equal(new Set(rows.map(row => row.namespace + "/" + row.name)).size, count);
      assert(!JSON.stringify(rows).includes("synthetic-window-hidden-annotation")); assert(rows.every(row => !("data" in row || "annotations" in row)));
      assert.equal(native.calls.length, count === 1000 ? 18 : 54);
      assert(native.calls.every(call => call.method === "GET" && call.limit === 200 && !call.metadata && !call.path.includes("/history/")));
      assert(native.calls.every(call => call.responseBytes < 4 * 1024 * 1024)); idle();
    }
  });
});

test("200-to-10 reductions retain zero/nonzero cursors and charge mixed-size rejected prefixes", { timeout: 30000 }, async () => {
  await fixture(async native => {
    for (const smallCount of [20, 200]) {
      native.reset(); const expected: ReturnType<typeof secretSummary>[] = [];
      for (let i = 0; i < smallCount; i++) {
        native.seed("mixed", "small-" + i, { field: "" });
        expected.push({ namespace: "mixed", name: "small-" + i, resourceVersion: String(i + 1), type: "Opaque", immutable: false, keys: ["field"] });
      }
      const payload = Buffer.alloc(256 * 1024, 7).toString("base64");
      for (let i = 0; i < 25; i++) {
        native.seed("mixed", "large-" + i, { field: payload });
        expected.push({ namespace: "mixed", name: "large-" + i, resourceVersion: String(smallCount + i + 1), type: "Opaque", immutable: false, keys: ["field"] });
      }
      const budget = new SecretListBudget(), rows: ReturnType<typeof secretSummary>[] = [];
      assert.deepEqual(await createSecretTransport(200).list("mixed", { budget, visit: record => rows.push(secretSummary(record)) }), []);
      assert.deepEqual(rows, expected); assert.equal(new Set(rows.map(row => row.name)).size, smallCount + 25); assert.equal(budget.items, smallCount + 25);
      const expectedCalls = smallCount === 20 ? [[200, 0], [10, 0], [10, 10], [10, 20], [10, 30], [10, 40]] : [[200, 0], [200, 200], [10, 200], [10, 210], [10, 220]];
      assert.deepEqual(native.calls.map(call => [call.limit, call.offset]), expectedCalls);
      const rejectedIndex = smallCount === 20 ? 0 : 1;
      const acceptedBytes = native.calls.filter((_, index) => index !== rejectedIndex).reduce((sum, call) => sum + call.responseBytes, 0);
      assert(budget.bytes > acceptedBytes + 4 * 1024 * 1024); assert(budget.bytes < SECRET_LIST_MAX_BYTES);
      assert(!JSON.stringify(rows).includes(payload)); idle();
    }
  });
});

test("200 windows preserve large-record successful limits and the four-reduction response refusal", { timeout: 30000 }, async () => {
  await fixture(async native => {
    for (const [count, size, expectedLimits] of [[25, 256 * 1024, [200, 10, 10, 10]], [3, 1024 * 1024, [200, 10, 5, 2, 2]]] as const) {
      native.reset(); const payload = Buffer.alloc(size, 11).toString("base64"), expected: ReturnType<typeof secretSummary>[] = [];
      for (let i = 0; i < count; i++) {
        native.seed("large", "object-" + i, { payload });
        expected.push({ namespace: "large", name: "object-" + i, resourceVersion: String(i + 1), type: "Opaque", immutable: false, keys: ["payload"] });
      }
      const budget = new SecretListBudget(), rows: ReturnType<typeof secretSummary>[] = [];
      await createSecretTransport(200).list("large", { budget, visit: record => rows.push(secretSummary(record)) });
      assert.deepEqual(rows, expected); assert.equal(budget.items, count); assert(budget.bytes < SECRET_LIST_MAX_BYTES);
      assert.deepEqual(native.calls.map(call => call.limit), expectedLimits); assert(native.calls.every(call => call.method === "GET" && !call.metadata)); idle();
    }
    native.reset(); native.seed("oversized", "object", { payload: Buffer.alloc(4 * 1024 * 1024, 13).toString("base64") });
    const budget = new SecretListBudget();
    await assert.rejects(createSecretTransport(200).list("oversized", { budget, visit: () => assert.fail("Over-cap page must not be parsed/projected") }), error => error503(error) && (error as Error).message === "Kubernetes Secret response exceeds the size limit");
    assert.deepEqual(native.calls.map(call => call.limit), [200, 10, 5, 2, 1]); assert.equal(budget.items, 0);
    assert(budget.bytes > 20 * 1024 * 1024 && budget.bytes < SECRET_LIST_MAX_BYTES); idle();
  });
});

test("one rejected prefix plus 80 quarter-MiB records stays within the unchanged aggregate ceiling", { timeout: 30000 }, async () => {
  await fixture(async native => {
    const payload = Buffer.alloc(256 * 1024, 7).toString("base64");
    for (let i = 0; i < 80; i++) native.seed("near-limit", "object-" + i, { payload });
    const budget = new SecretListBudget(), rows: ReturnType<typeof secretSummary>[] = [];
    await createSecretTransport(200).list("near-limit", { budget, visit: record => rows.push(secretSummary(record)) });
    assert.equal(rows.length, 80); assert.equal(new Set(rows.map(row => row.name)).size, 80); assert.equal(budget.items, 80);
    assert.deepEqual(native.calls.map(call => call.limit), [200, ...Array(8).fill(10)]);
    const acceptedBytes = native.calls.slice(1).reduce((sum, call) => sum + call.responseBytes, 0);
    assert(budget.bytes > acceptedBytes + 4 * 1024 * 1024); assert(budget.bytes < SECRET_LIST_MAX_BYTES); idle();
    native.reset();
    for (let i = 0; i < 96; i++) native.seed("over-limit", "object-" + i, { payload });
    const over = new SecretListBudget();
    await assert.rejects(createSecretTransport(200).list("over-limit", { budget: over, visit: () => {} }), error => error503(error) && (error as Error).message.includes("aggregate byte"));
    assert(over.signal.aborted); assert(over.bytes > SECRET_LIST_MAX_BYTES); assert(over.items < 96); idle();
  });
});

test("batched production inventory rejects object10001 and invalid window configuration without partial results", { timeout: 30000 }, async () => {
  await fixture(async native => {
    const scopes = Array.from({ length: 18 }, (_, i) => "scope-" + i);
    process.env.BORTUS_SECRET_NAMESPACES = scopes.join(","); process.env.BORTUS_HISTORY_NAMESPACE = "history";
    for (let i = 0; i < 10001; i++) native.seed(scopes[i % 18], "object-" + i, {});
    let result;
    await assert.rejects(async () => { result = await nativeSecrets().list(); }, error => error503(error) && (error as Error).message.includes("aggregate item"));
    assert.equal(result, undefined); idle();
    const previousCalls = native.calls.length;
    for (const limit of [0, 1, 201, NaN]) assert.throws(() => createSecretTransport(limit as 20), /Invalid Kubernetes Secret list page limit/);
    assert.equal(native.calls.length, previousCalls);
  });
});

test("batched cancellation aborts owned active/queued TLS requests while an unrelated read completes", { timeout: 30000 }, async () => {
  await fixture(async native => {
    native.seed("apps", "blocker", { field: "" });
    const transport = createSecretTransport(200), raw = transport.list.bind(transport), budgets: SecretListBudget[] = [];
    const unrelated = transport.read("apps", "blocker");
    transport.list = (namespace, options) => { budgets.push(options!.budget!); return raw(namespace, options); };
    const pending = new SecretStore(transport, ["a", "b", "c", "d", "unstarted"], undefined, 4).list();
    const reject = assert.rejects(pending, error => error503(error) && (error as Error).message === "Kubernetes Secret list timed out");
    const until = Date.now() + 2000;
    while (native.calls.length < 4 && Date.now() < until) await new Promise(resolve => setTimeout(resolve, 1));
    assert.equal(native.calls.length, 4); assert.equal(nativeRequestDiagnostics().active, 4); assert.equal(nativeRequestDiagnostics().queued, 1);
    assert.equal(new Set(budgets).size, 1); budgets[0].fail(new SecretError(503, "Kubernetes Secret list timed out"));
    await reject; assert.equal(nativeRequestDiagnostics().queued, 0); assert.equal(nativeRequestDiagnostics().active, 1);
    assert.equal((await unrelated).metadata?.name, "blocker");
    assert.equal(native.calls.length, 4); assert(!native.calls.some(call => call.path.includes("/d/") || call.path.includes("/unstarted/"))); idle();
  }, 300);
});
