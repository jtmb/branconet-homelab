import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import https from "node:https";
import http from "node:http";
import net from "node:net";
import { EventEmitter, once } from "node:events";
import { KubeConfig } from "@kubernetes/client-node";
import { SecretStore, SecretListBudget, SecretError, SECRET_LIST_MAX_BYTES, secretSummary } from "../src/lib/cluster-secrets";
import { createSecretTransport, nativeSecrets, nativeRequestDiagnostics } from "../src/lib/secret-client";
import { nativeTlsFixture } from "./helpers/native-tls";

const error503 = (error: unknown) => error instanceof SecretError && error.status === 503;
const idle = () => assert.deepEqual(nativeRequestDiagnostics(), { active: 0, queued: 0, maxConcurrent: 4, maxQueued: 64 });
async function traceAgents(operation: (entries: { agent: https.Agent; connections: number; destroyed: number }[]) => Promise<void>,
  before?: (config: KubeConfig, call: number) => void,
  after?: (options: https.RequestOptions, call: number) => void) {
  const original = KubeConfig.prototype.applyToHTTPSOptions;
  const entries: { agent: https.Agent; connections: number; destroyed: number }[] = []; let calls = 0;
  KubeConfig.prototype.applyToHTTPSOptions = async function (options) {
    const call = ++calls; before?.(this, call); await original.call(this, options); after?.(options, call);
    assert(options.agent && typeof options.agent === "object");
    const agent = options.agent as https.Agent, entry = { agent, connections: 0, destroyed: 0 };
    const connect = agent.createConnection.bind(agent), destroy = agent.destroy.bind(agent);
    agent.createConnection = (options, callback) => { entry.connections++; return connect(options, callback); };
    agent.destroy = () => { entry.destroyed++; destroy(); };
    entries.push(entry);
  };
  try { await operation(entries); }
  finally { KubeConfig.prototype.applyToHTTPSOptions = original; for (const entry of entries) entry.agent.destroy(); }
}
const agentsClosed = (entries: { agent: https.Agent; destroyed: number }[]) => {
  assert(entries.every(entry => entry.destroyed > 0), "every SDK-created agent must be torn down");
  assert(entries.every(({ agent }) => [...Object.values(agent.sockets), ...Object.values(agent.freeSockets)].flat().every(socket => !socket || socket.destroyed)), "owned socket must be destroyed");
};
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

test("settled responses discard late end/data/errors without decoding and still charge every delivered byte", { timeout: 30000 }, async () => {
  await fixture(async () => {
    for (const mode of ["oversize", "response-error", "request-error", "cancel", "aggregate", "success"] as const) {
      const budget = new SecretListBudget(), initialBytes = mode === "aggregate" ? SECRET_LIST_MAX_BYTES - 100 : 0;
      budget.bytes = initialBytes;
      const prefix = Buffer.from('{"apiVersion":"v1","kind":"SecretList","metadata":{"continue":""},"items":[]}');
      const late = Buffer.alloc(45), excess = Buffer.alloc(mode === "oversize" ? 4 * 1024 * 1024 : 200);
      const cancelled = new SecretError(503, "Synthetic cancelled response");
      const originalRequest = https.request, originalConcat = Buffer.concat, originalDecode = TextDecoder.prototype.decode, originalParse = JSON.parse;
      let requests = 0, delivered = 0, settlements = 0; const work = { concat: 0, decode: 0, parse: 0 };
      https.request = ((_url: string, _options: https.RequestOptions, receive: (response: http.IncomingMessage) => void) => {
        requests++;
        const request = new EventEmitter() as EventEmitter & { end(): void; setHeader(): void };
        request.setHeader = () => {};
        request.end = () => { setImmediate(() => {
          const response = new EventEmitter() as EventEmitter & { statusCode: number; destroy(): void };
          response.statusCode = 200; response.destroy = () => {};
          receive(response as unknown as http.IncomingMessage);
          // Only the synchronous owned response handlers are observed; SDK/TLS setup remains unchanged.
          Buffer.concat = (...args) => { work.concat++; return originalConcat(...args); };
          TextDecoder.prototype.decode = function (...args) { work.decode++; return originalDecode.apply(this, args); };
          JSON.parse = (...args) => { work.parse++; return originalParse(...args); };
          const data = (chunk: Buffer) => { delivered += chunk.length; response.emit("data", chunk); };
          try {
            data(prefix);
            if (mode === "oversize" || mode === "aggregate") data(excess);
            if (mode === "response-error") response.emit("error", new Error("Synthetic response failure"));
            if (mode === "request-error") request.emit("error", new Error("Synthetic request failure"));
            if (mode === "cancel") budget.fail(cancelled);
            response.emit("end");
            data(late); response.emit("end");
            if (mode !== "response-error") response.emit("error", new Error("Synthetic late response failure"));
            if (mode !== "request-error") request.emit("error", new Error("Synthetic late request failure"));
          } finally { Buffer.concat = originalConcat; TextDecoder.prototype.decode = originalDecode; JSON.parse = originalParse; }
        }); };
        return request;
      }) as unknown as typeof https.request;
      try {
        const pending = createSecretTransport(200).list("late", { budget, visit: () => assert.fail("Synthetic empty/rejected page has no accepted object") }).then(
          value => { settlements++; return value; }, error => { settlements++; throw error; });
        if (mode === "success") assert.deepEqual(await pending, []);
        else await assert.rejects(pending, error => error503(error) && (mode !== "cancel" || error === cancelled));
        assert.equal(settlements, 1); assert.equal(requests, mode === "oversize" ? 5 : 1);
        assert.equal(budget.bytes, initialBytes + delivered); assert.equal(budget.items, 0);
        assert.deepEqual(work, mode === "success" ? { concat: 1, decode: 1, parse: 1 } : { concat: 0, decode: 0, parse: 0 });
        if (mode === "aggregate") assert(budget.bytes > SECRET_LIST_MAX_BYTES && budget.signal.aborted);
        idle();
      } finally { https.request = originalRequest; Buffer.concat = originalConcat; TextDecoder.prototype.decode = originalDecode; JSON.parse = originalParse; budget.finish(); }
    }
  });
});

test("full-list keepalive shares at most four TLS connections only within one complete operation", { timeout: 30000 }, async () => {
  await fixture(async native => {
    const scopes = Array.from({ length: 18 }, (_, i) => "pool-" + i);
    process.env.BORTUS_SECRET_NAMESPACES = scopes.join(",");
    for (const scope of scopes) native.seed(scope, "object", Object.fromEntries([["__proto__", ""], ["binary", "/wA="], ["empty", ""]]));
    await traceAgents(async entries => {
      const first = await nativeSecrets().list();
      assert.equal(first.length, 18); assert.deepEqual(first.map(row => row.namespace), scopes);
      assert(first.every(row => JSON.stringify(row.keys) === JSON.stringify(["__proto__", "binary", "empty"])));
      assert.equal(entries.length, 18); assert.equal(entries.filter(entry => entry.connections).length, 1);
      assert(entries[0].connections > 0 && entries[0].connections <= 4);
      assert.equal(entries[0].agent.maxSockets, 4); assert.equal(entries[0].agent.maxTotalSockets, 4); assert.equal(entries[0].agent.maxFreeSockets, 4);
      agentsClosed(entries); idle();
      assert.deepEqual(await nativeSecrets().list(), first);
      assert.equal(entries.length, 36); assert.equal(entries.filter(entry => entry.connections).length, 2);
      assert.notEqual(entries[0].agent, entries[18].agent); agentsClosed(entries); idle();
    });
  }, 12);
});

test("pooled requests refresh SDK authorization and fail closed when its next credential is withdrawn", { timeout: 30000 }, async () => {
  await fixture(async native => {
    for (let i = 0; i < 21; i++) native.seed("auth", "object-" + i, { field: "" });
    await traceAgents(async entries => {
      await assert.rejects(createSecretTransport().list("auth"), error => error503(error) && (error as Error).message === "Kubernetes credentials or Secret RBAC denied access");
      assert.equal(entries.length, 2); assert.equal(native.calls.length, 2);
      assert.equal(entries[0].connections, 1); assert.equal(entries[1].connections, 0);
      agentsClosed(entries); idle();
    }, (config, call) => { if (call === 2) Object.assign(config.getCurrentUser()!, { token: "synthetic-withdrawn-credential" }); });
  });
});

test("cancelled SDK authentication destroys late agents without a request or interference with unrelated reads", { timeout: 30000 }, async () => {
  await fixture(async native => {
    native.seed("race", "object", { field: "" });
    for (const rejectLate of [false, true]) {
    const priorCalls = native.calls.length;
    const original = KubeConfig.prototype.applyToHTTPSOptions;
    let release!: () => void, entered!: () => void, completed!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; }), started = new Promise<void>(resolve => { entered = resolve; }), late = new Promise<void>(resolve => { completed = resolve; });
    let calls = 0, lateAgent: https.Agent | undefined, lateDestroyed = 0;
    KubeConfig.prototype.applyToHTTPSOptions = async function (options) {
      if (++calls !== 1) { await original.call(this, options); return; }
      entered(); await gate; await original.call(this, options);
      lateAgent = options.agent as https.Agent; const destroy = lateAgent.destroy.bind(lateAgent);
      lateAgent.destroy = () => { lateDestroyed++; destroy(); }; completed();
      if (rejectLate) throw new Error("Synthetic late SDK failure");
    };
    try {
      const budget = new SecretListBudget(), pending = createSecretTransport().list("race", { budget });
      const rejected = assert.rejects(pending, error => error503(error) && (error as Error).message === "Synthetic authentication cancellation");
      await started; budget.fail(new SecretError(503, "Synthetic authentication cancellation")); await rejected;
      assert.equal(native.calls.length, priorCalls); idle();
      assert.equal((await createSecretTransport().read("race", "object")).metadata?.name, "object");
      assert.equal(native.calls.length, priorCalls + 1); idle();
      release(); await late; await new Promise<void>(resolve => setImmediate(resolve));
      assert(lateAgent && lateDestroyed > 0); assert.equal(Object.keys(lateAgent.sockets).length, 0);
      assert.equal(native.calls.length, priorCalls + 1); idle();
    } finally { release(); KubeConfig.prototype.applyToHTTPSOptions = original; lateAgent?.destroy(); }
    }
    await traceAgents(async entries => {
      await assert.rejects(createSecretTransport().list("race"), error503); assert.equal(native.calls.length, 2);
      assert.equal(entries.length, 1); assert.equal(entries[0].connections, 0); agentsClosed(entries); idle();
    }, undefined, options => { options.rejectUnauthorized = false; });
    await traceAgents(async entries => {
      const budget = new SecretListBudget();
      budget.onFinish = () => { throw new SecretError(503, "Synthetic pool registration failure"); };
      await assert.rejects(createSecretTransport().list("race", { budget }), error503);
      assert.equal(native.calls.length, 2); assert.equal(entries.length, 1);
      assert.equal(entries[0].connections, 0); agentsClosed(entries); idle();
    });
  });
});

test("fresh security-option changes never reuse the earlier trusted connection", { timeout: 30000 }, async () => {
  await fixture(async native => {
    for (let i = 0; i < 21; i++) native.seed("trust", "object-" + i, { field: "" });
    await traceAgents(async entries => {
      await assert.rejects(createSecretTransport().list("trust"), error503);
      assert.equal(entries.length, 2); assert.equal(entries[0].connections, 1); assert.equal(entries[1].connections, 1);
      agentsClosed(entries); idle();
    }, undefined, (options, call) => {
      if (call === 2) { options.ca = Buffer.from("synthetic untrusted CA"); (options.agent as https.Agent).options.ca = options.ca; }
    });
    await traceAgents(async entries => {
      assert.equal((await createSecretTransport().list("trust")).length, 21);
      assert.equal(entries.length, 2); assert(entries.every(entry => entry.connections === 1)); agentsClosed(entries); idle();
    }, undefined, (options, call) => {
      if (call === 2) { options.servername = "localhost"; (options.agent as https.Agent).options.servername = "localhost"; }
    });
  });
});

test("client-certificate and real HTTP proxy agents retain fresh request boundaries", { timeout: 30000 }, async () => {
  await fixture(async native => {
    for (let i = 0; i < 21; i++) native.seed("boundary", "object-" + i, { field: "" });
    const cert = await readFile(path.join(path.dirname(native.config), "native-cert.pem")), key = await readFile(path.join(path.dirname(native.config), "native-key.pem"));
    let mutualRequests = 0;
    const mutual = https.createServer({ cert, key, ca: cert, requestCert: true, rejectUnauthorized: true }, (request, response) => {
      assert((request.socket as import("node:tls").TLSSocket).authorized); mutualRequests++;
      const url = new URL(request.url || "/", "https://localhost"), limit = Number(url.searchParams.get("limit")), offset = Number(url.searchParams.get("continue") || 0);
      const records = [...native.objects.values()], page = records.slice(offset, offset + limit);
      response.writeHead(200, { "Content-Type": "application/json" }); response.end(JSON.stringify({ kind: "SecretList", apiVersion: "v1", metadata: { continue: offset + limit < records.length ? String(offset + limit) : "" }, items: page }));
    });
    mutual.listen(0, "127.0.0.1"); await once(mutual, "listening");
    const originalConfig = await readFile(native.config), config = JSON.parse(originalConfig.toString("utf8"));
    config.clusters[0].cluster.server = "https://127.0.0.1:" + (mutual.address() as net.AddressInfo).port;
    Object.assign(config.users[0].user, { "client-certificate": path.join(path.dirname(native.config), "native-cert.pem"), "client-key": path.join(path.dirname(native.config), "native-key.pem") });
    await writeFile(native.config, JSON.stringify(config));
    try {
      await traceAgents(async entries => {
        assert.equal((await createSecretTransport().list("boundary")).length, 21); assert.equal(mutualRequests, 2);
        assert.equal(entries.length, 2); assert(entries.every(entry => entry.connections === 1 && !Reflect.get(entry.agent, "keepAlive"))); agentsClosed(entries); idle();
      });
    } finally { await writeFile(native.config, originalConfig); mutual.closeAllConnections(); await new Promise<void>(resolve => mutual.close(() => resolve())); }
    const connections = new Set<net.Socket>(); let tunnels = 0;
    const proxy = http.createServer((_request, response) => { response.writeHead(405); response.end(); });
    proxy.on("connection", socket => { connections.add(socket); socket.once("close", () => connections.delete(socket)); });
    proxy.on("connect", (request, downstream, head) => {
      tunnels++; const [host, port] = (request.url || "").split(":");
      const upstream = net.connect(Number(port), host); connections.add(upstream); upstream.once("close", () => connections.delete(upstream));
      upstream.once("error", () => downstream.destroy()); downstream.once("error", () => upstream.destroy());
      upstream.once("connect", () => { downstream.write("HTTP/1.1 200 Connection Established\r\n\r\n"); if (head.length) upstream.write(head); downstream.pipe(upstream); upstream.pipe(downstream); });
    });
    proxy.listen(0, "127.0.0.1"); await once(proxy, "listening");
    try {
      await traceAgents(async entries => {
        assert.equal((await createSecretTransport().list("boundary")).length, 21); assert.equal(tunnels, 2);
        assert.equal(entries.length, 2); assert(entries.every(entry => entry.agent.constructor !== https.Agent && !Reflect.get(entry.agent, "keepAlive"))); agentsClosed(entries); idle();
      }, config => { Object.assign(config.getCurrentCluster()!, { proxyUrl: "http://127.0.0.1:" + (proxy.address() as net.AddressInfo).port }); });
    } finally { for (const socket of connections) socket.destroy(); await new Promise<void>(resolve => proxy.close(() => resolve())); }
  });
});

test("externally owned list budgets explicitly finish or expire their connection pools", { timeout: 30000 }, async () => {
  await fixture(async native => {
    native.seed("finish", "object", { field: "" });
    await traceAgents(async entries => {
      const budget = new SecretListBudget(); await createSecretTransport().list("finish", { budget });
      assert.equal(entries[0].destroyed, 0); budget.finish(); agentsClosed(entries); idle();
      const expiring = new SecretListBudget(Date.now() + 100); await createSecretTransport().list("finish", { budget: expiring });
      assert.equal(entries[1].destroyed, 0); await new Promise(resolve => setTimeout(resolve, 120));
      assert(expiring.signal.aborted); agentsClosed(entries); idle();
    });
  });
});

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
