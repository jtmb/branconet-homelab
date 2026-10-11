import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { SecretStore, SecretListBudget, SecretError, SECRET_LIST_MAX_BYTES, type SecretTransport, type SecretListOptions } from "../src/lib/cluster-secrets";
import { createSecretTransport, nativeRequestDiagnostics } from "../src/lib/secret-client";
import { nativeTlsFixture } from "./helpers/native-tls";

const unavailable = async (): Promise<never> => { throw new Error("Value/mutation access is forbidden in the list-only fixture"); };

test("complete 100-namespace scope shares item/deadline limits and serial projection, with no value/annotation results", async () => {
  const namespaces = Array.from({ length: 100 }, (_, i) => "scope-" + i);
  let active = 0, maximum = 0;
  const budgets: SecretListBudget[] = [], calls: string[] = [];
  const transport: SecretTransport = { read: unavailable, create: unavailable, replace: unavailable, async list(namespace: string, options?: SecretListOptions) {
    active++; maximum = Math.max(maximum, active); calls.push(namespace); budgets.push(options!.budget!);
    await new Promise(resolve => setImmediate(resolve)); active--;
    return [{ apiVersion: "v1", kind: "Secret", metadata: { namespace, name: "credential", annotations: { private: "synthetic-private-capacity" } }, data: { password: "cHJpdmF0ZQ==" } }];
  } };
  const result = await new SecretStore(transport, namespaces).list();
  assert.equal(result.length, 100); assert.equal(maximum, 1); assert.deepEqual(calls, namespaces);
  assert.equal(new Set(budgets).size, 1); assert.equal(new Set(budgets.map(budget => budget.deadline)).size, 1);
  assert.equal(budgets[0].items, 100); assert(budgets[0].bytes > 0 && budgets[0].bytes < SECRET_LIST_MAX_BYTES);
  assert(!JSON.stringify(result).includes("synthetic-private-capacity")); assert(!JSON.stringify(result).includes("cHJpdmF0ZQ=="));
  calls.length = 0;
  transport.list = async namespace => { calls.push(namespace); return Array.from({ length: 6000 }, (_, i) => ({ apiVersion: "v1", kind: "Secret", metadata: { namespace, name: "item-" + i }, data: {} })); };
  await assert.rejects(new SecretStore(transport, namespaces).list(), error => error instanceof SecretError && error.status === 503 && error.message.includes("aggregate item"));
  assert.deepEqual(calls, namespaces.slice(0, 2));
});

test("aggregate bytes cannot reset between namespaces; expired/invalid budgets fail closed", async () => {
  const calls: string[] = [], payload = Buffer.alloc(256 * 1024, 3).toString("base64");
  const transport: SecretTransport = { read: unavailable, create: unavailable, replace: unavailable, async list(namespace: string) {
    calls.push(namespace); return Array.from({ length: 50 }, (_, i) => ({ apiVersion: "v1", kind: "Secret", metadata: { namespace, name: "item-" + i }, data: { blob: payload } }));
  } };
  await assert.rejects(new SecretStore(transport, ["first", "second", "unstarted"]).list(), error => error instanceof SecretError && error.status === 503 && error.message.includes("aggregate byte"));
  assert.deepEqual(calls, ["first", "second"]);
  assert.throws(() => new SecretListBudget(Date.now() - 1).remainingBytes(), /timed out/);
  assert.throws(() => new SecretListBudget().consumeBytes(NaN), /aggregate byte/);
});

test("verified TLS lists keep maximum-size history enumeration metadata-only and large flat objects operable", { timeout: 30000 }, async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-secret-capacity-"));
  const previous = process.env.KUBECONFIG; let native: Awaited<ReturnType<typeof nativeTlsFixture>> | undefined;
  try {
    native = await nativeTlsFixture(dir); process.env.KUBECONFIG = native.config;
    const payload = Buffer.alloc(256 * 1024, 7).toString("base64");
    for (let i = 0; i < 25; i++) {
      native.seed("history", "history-" + i, { blob: payload }, { immutable: true, metadata: { annotations: { "bortus.io/kv-history": "synthetic-fixed-ownership" } } });
      native.seed("apps", "current-" + i, { blob: payload });
    }
    const twentyHistories = [...native.objects.values()].filter(item => item.metadata?.namespace === "history").slice(0, 20);
    assert(Buffer.byteLength(JSON.stringify({ apiVersion: "v1", kind: "SecretList", items: twentyHistories })) > 4 * 1024 * 1024);
    const transport = createSecretTransport(), metadata = await transport.listMetadata("history");
    assert.equal(metadata.length, 25); assert(!JSON.stringify(metadata).includes(payload));
    assert(native.calls.filter(call => call.path.includes("/history/")).every(call => call.metadata));
    const scopes = ["apps", ...Array.from({ length: 99 }, (_, i) => "scope-" + i)];
    for (const namespace of scopes.slice(1)) native.seed(namespace, "small", { field: "AQ==" });
    const before = native.calls.length, budgets: SecretListBudget[] = [], rawList = transport.list.bind(transport);
    transport.list = async (namespace, options) => { budgets.push(options!.budget!); const full = await rawList(namespace, options); assert.equal(full.length, 0); return full; };
    const rawSummaries = transport.listSummaries!.bind(transport);
    transport.listSummaries = async (namespace, options) => { budgets.push(options!.budget!); const summary = await rawSummaries(namespace, options); assert.equal(summary.length, 0); return summary; };
    let maximumActive = 0;
    const sampler = setInterval(() => { maximumActive = Math.max(maximumActive, nativeRequestDiagnostics().active); }, 1);
    let summaries: Awaited<ReturnType<SecretStore["list"]>>;
    try { summaries = await new SecretStore(transport, scopes).list(); } finally { clearInterval(sampler); }
    assert.equal(summaries.length, 124); assert.equal(native.calls.length - before, 103); assert(!JSON.stringify(summaries).includes(payload));
    assert.deepEqual(native.calls.slice(before, before + 4).map(call => call.limit), [20, 10, 10, 10]);
    assert(maximumActive <= 1); assert.equal(new Set(budgets).size, 1); assert.equal(budgets[0].items, 124); assert(budgets[0].bytes < SECRET_LIST_MAX_BYTES);
    for (const namespace of ["byte-a", "byte-b", "byte-c", "unstarted"]) for (let i = 0; i < 32; i++) native.seed(namespace, "large-" + i, { blob: payload });
    const beforeOverflow = native.calls.length;
    await assert.rejects(new SecretStore(transport, ["byte-a", "byte-b", "byte-c", "unstarted"]).list(), error => error instanceof SecretError && error.status === 503);
    assert(!native.calls.slice(beforeOverflow).some(call => call.path.includes("/unstarted/")));
    assert.equal(nativeRequestDiagnostics().active, 0); assert.equal(nativeRequestDiagnostics().queued, 0);
  } finally {
    if (previous === undefined) delete process.env.KUBECONFIG; else process.env.KUBECONFIG = previous;
    await native?.close();
    if (path.dirname(path.resolve(dir)) !== path.resolve(tmpdir()) || !path.basename(dir).startsWith("bortus-secret-capacity-")) throw new Error("Unsafe Secret capacity cleanup target");
    await rm(dir, { recursive: true, force: true });
  }
});

test("adaptive GET retries keep the cursor, charge rejected bytes and support the flat maximum record", { timeout: 30000 }, async context => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-secret-adaptive-"));
  const previous = process.env.KUBECONFIG; let native: Awaited<ReturnType<typeof nativeTlsFixture>> | undefined;
  try {
    native = await nativeTlsFixture(dir); process.env.KUBECONFIG = native.config;
    for (let i = 0; i < 20; i++) native.seed("mixed", "small-" + i, { field: "AQ==" });
    const payload = Buffer.alloc(256 * 1024, 7).toString("base64");
    for (let i = 0; i < 25; i++) native.seed("mixed", "large-" + i, { field: payload });
    const transport = createSecretTransport(), budget = new SecretListBudget(), summaries: unknown[] = [];
    await transport.list("mixed", { budget, visit: secret => { summaries.push({ name: secret.metadata?.name, keys: Object.keys(secret.data || {}) }); } });
    assert.equal(summaries.length, 45); assert.equal(new Set(summaries.map(item => (item as { name: string }).name)).size, 45);
    assert.deepEqual(summaries.map(item => (item as { name: string }).name), [...Array.from({ length: 20 }, (_, i) => "small-" + i), ...Array.from({ length: 25 }, (_, i) => "large-" + i)]);
    assert.deepEqual(native.calls.map(call => [call.limit, call.offset]), [[20, 0], [20, 20], [10, 20], [10, 30], [10, 40]]);
    const acceptedBytes = native.calls.filter((_, index) => index !== 1).reduce((sum, call) => sum + call.responseBytes, 0);
    assert(budget.bytes > acceptedBytes + 4 * 1024 * 1024, "Rejected prefix bytes remain charged"); assert.equal(budget.items, 45);
    assert(!JSON.stringify(summaries).includes(payload));
    const before = native.calls.length, maximum = Buffer.alloc(1024 * 1024, 11).toString("base64");
    for (let i = 0; i < 3; i++) native.seed("maximum", "flat-" + i, { field: maximum });
    const maxBudget = new SecretListBudget(), start = performance.now(), identities: { namespace: string; name: string }[] = [];
    await transport.list("maximum", { budget: maxBudget, visit: secret => { identities.push({ namespace: secret.metadata!.namespace!, name: secret.metadata!.name! }); } });
    const maximumCalls = native.calls.slice(before);
    assert.deepEqual(identities, [{ namespace: "maximum", name: "flat-0" }, { namespace: "maximum", name: "flat-1" }, { namespace: "maximum", name: "flat-2" }]);
    assert.equal(new Set(identities.map(item => item.name)).size, 3);
    assert.deepEqual(maximumCalls.map(call => call.limit), [20, 2, 2]); assert.deepEqual(maximumCalls.map(call => call.offset), [0, 0, 2]);
    const maximumAcceptedBytes = maximumCalls.slice(1).reduce((sum, call) => sum + call.responseBytes, 0);
    assert.equal(maxBudget.items, 3); assert(maxBudget.bytes > maximumAcceptedBytes + 4 * 1024 * 1024 && maxBudget.bytes < SECRET_LIST_MAX_BYTES);
    context.diagnostic(JSON.stringify({ fixture: "Three one-MiB decoded flat records; verified loopback TLS", requests: maximumCalls.length, receivedWireBytes: maxBudget.bytes, elapsedMs: performance.now() - start }));
    const beforeRefusal = native.calls.length;
    native.seed("invalid-large", "oversized", { field: Buffer.alloc(4 * 1024 * 1024, 13).toString("base64") });
    await assert.rejects(transport.list("invalid-large"), error => error instanceof SecretError && error.status === 503 && error.message === "Kubernetes Secret response exceeds the size limit");
    assert.deepEqual(native.calls.slice(beforeRefusal).map(call => call.limit), [20, 10, 5, 2, 1]);
    assert.equal(nativeRequestDiagnostics().active, 0); assert.equal(nativeRequestDiagnostics().queued, 0);
  } finally {
    if (previous === undefined) delete process.env.KUBECONFIG; else process.env.KUBECONFIG = previous;
    await native?.close();
    if (path.dirname(path.resolve(dir)) !== path.resolve(tmpdir()) || !path.basename(dir).startsWith("bortus-secret-adaptive-")) throw new Error("Unsafe adaptive Secret cleanup target");
    await rm(dir, { recursive: true, force: true });
  }
});

test("334-object/18-namespace fixture restores batching and preserves the shared deadline", { timeout: 30000 }, async context => {
  const dir = await mkdtemp(path.join(tmpdir(), "bortus-secret-count-"));
  const previous = process.env.KUBECONFIG; let native: Awaited<ReturnType<typeof nativeTlsFixture>> | undefined;
  try {
    native = await nativeTlsFixture(dir, 12); process.env.KUBECONFIG = native.config;
    const scopes = Array.from({ length: 18 }, (_, i) => "namespace-" + i);
    for (let i = 0; i < 334; i++) native.seed(scopes[i % scopes.length], "secret-" + i, { field: "c3ludGhldGlj" });
    const transport = createSecretTransport(), start = performance.now();
    const summaries = await new SecretStore(transport, scopes).list(), elapsedMs = performance.now() - start;
    assert.equal(summaries.length, 334); assert.equal(native.calls.length, 18); assert(native.calls.every(call => call.limit === 20));
    const wireBytes = native.calls.reduce((sum, call) => sum + call.responseBytes, 0);
    assert(wireBytes < SECRET_LIST_MAX_BYTES); assert(elapsedMs < 15000);
    context.diagnostic(JSON.stringify({ fixture: "334 small synthetic Secrets across 18 namespaces, verified loopback TLS, fixed 12ms producer delay", objects: 334,
      namespaces: 18, requests: native.calls.length, wireBytes, elapsedMs, previousOneObjectRequests: 334, previousOneObjectFocusedElapsedMs: 9132.1211,
      limitations: ["Earlier run used the same synthetic producer delay and shape; host timing is uncontrolled", "Separate controlled Linux RSS qualification is required", "Higher-latency APIs can exceed the unchanged shared 15-second deadline"] }));
    const before = native.calls.length, budget = new SecretListBudget(Date.now() + 5);
    await assert.rejects(transport.list(scopes[0], { budget, visit: () => {} }), error => error instanceof SecretError && error.status === 503);
    assert(native.calls.length - before <= 1); assert.equal(nativeRequestDiagnostics().active, 0); assert.equal(nativeRequestDiagnostics().queued, 0);
  } finally {
    if (previous === undefined) delete process.env.KUBECONFIG; else process.env.KUBECONFIG = previous;
    await native?.close();
    if (path.dirname(path.resolve(dir)) !== path.resolve(tmpdir()) || !path.basename(dir).startsWith("bortus-secret-count-")) throw new Error("Unsafe Secret request-count cleanup target");
    await rm(dir, { recursive: true, force: true });
  }
});
