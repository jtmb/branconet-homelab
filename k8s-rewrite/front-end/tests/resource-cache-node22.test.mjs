// DISTINCT NEW five PUBLIC selected-copy controls; historical callbacks remain frozen.
// Infrastructure only: select exact copied declarations. Original modules stay inert.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
const ts = createRequire(import.meta.url)('typescript');
assert.equal(ts.version, '5.9.3');
const pin = (path, hash) => {
  const source = readFileSync(new URL('../' + path, import.meta.url), 'utf8').replaceAll('\r\n', '\n');
  assert.equal(createHash('sha256').update(source).digest('hex'), hash, path);
  return ts.createSourceFile(path, source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
};
const cacheAST = pin('src/lib/resource-cache.ts', 'd8ffefde0b8b2449b9c038e9547a330ffe7dc060dcb9a410c97696e08382bbb9');
const responseAST = pin('src/lib/cluster-response.ts', 'e64a9e7ea57e98b4af22e6eda30925c5e81d6d9a9cfbd5e12140c1c0405983bd');
const metadataAST = pin('src/lib/cluster-metadata.ts', '4ad9462cc00380744b9680c6aa1e7315bd50553cd9988faf491ae65711fee24a');
const declaration = (tree, name) => {
  const found = tree.statements.filter(n => (ts.isClassDeclaration(n) || ts.isFunctionDeclaration(n)) ? n.name?.text === name : ts.isVariableStatement(n) && n.declarationList.declarations.some(d => ts.isIdentifier(d.name) && d.name.text === name));
  assert.equal(found.length, 1, name);
  return found[0].getText(tree).replace(/^export\s+/, '');
};
const selected = [declaration(cacheAST, 'ClusterResourceCache'), ...['clusterAvailability', 'clusterUnavailable', 'fields', 'clusterResponse'].map(n => declaration(responseAST, n)), ...['pick', 'publicClusterMetadata'].map(n => declaration(metadataAST, n))].join('\n');
const lowered = ts.transpileModule(selected, { reportDiagnostics: true, compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, useDefineForClassFields: true } });
assert.equal(lowered.diagnostics.length, 0);
// Inert PUBLIC facades only. No actual kubectl-client error initializer or Next implementation.
class KubernetesCommandError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
const NextResponse = Object.freeze({ json: (body, init) => new Response(JSON.stringify(body), init) });
const { ClusterResourceCache, clusterResponse, clusterUnavailable } = vm.runInNewContext(`"use strict";\n${lowered.outputText}\n({ ClusterResourceCache, clusterResponse, clusterUnavailable })`, { KubernetesCommandError, NextResponse }, { timeout: 1000 });
let count = 0;
const control = (...args) => { count++; return test(...args); };
// BEGIN EXACT ORIGINAL TYPE-ERASED PROJECTION
import { test } from "node:test";
import assert from "node:assert/strict";



control("concurrent requested resources coalesce without unrelated cold fanout", async () => {
    let now = 1000;
    const calls = [];
    const cache = new ClusterResourceCache(async (resource) => { calls.push(resource); return { items: resource === "pods" ? [{ metadata: { name: "example" } }] : [] }; }, () => now);
    await Promise.all(Array.from({ length: 20 }, () => cache.read(["pods", "nodes"])));
    assert.deepEqual(calls.sort(), ["nodes", "pods"]);
    const hot = await cache.read(["pods"]);
    assert.equal(hot.pods?.availability.state, "healthy");
    assert.equal(calls.length, 2);
    now += 10001;
    await cache.read(["pods"]);
    assert.equal(calls.length, 3);
    assert.equal(cache.diagnostics().nodes.state, "stale");
});
control("failure backoff preserves labelled bounded stale data and never invents empty success", async () => {
    let now = 1000, fail = false, calls = 0;
    const cache = new ClusterResourceCache(async () => { calls++; if (fail)
        throw new KubernetesCommandError(502, "Kubernetes command failed"); return { items: [{ metadata: { name: "kept" } }] }; }, () => now);
    await cache.read(["pods"]);
    fail = true;
    now += 10001;
    const stale = (await cache.read(["pods"])).pods;
    assert.equal(stale.availability.state, "stale");
    assert.equal(stale.availability.staleAgeMs, 10001);
    assert.equal(stale.value?.items[0].metadata.name, "kept");
    const before = calls;
    await Promise.all(Array.from({ length: 20 }, () => cache.read(["pods"])));
    assert.equal(calls, before);
    now += 1000;
    assert.equal((await cache.read(["pods"])).pods?.availability.retryAfterMs, 2000);
    now += 130000;
    const expired = (await cache.read(["pods"])).pods;
    assert.equal(expired.availability.state, "unavailable");
    assert.equal(expired.value, undefined);
    const unavailable = clusterUnavailable({ availability: { pods: expired.availability } }, "pods");
    assert.equal(unavailable.status, 503);
    assert.ok(!(await unavailable.text()).includes('"pods":[]'));
    const response = clusterResponse({ availability: { pods: stale.availability } }, { pods: stale.value.items }, ["pods"]);
    assert.equal(response.status, 200);
    assert.ok(response.headers.get("Warning"));
    assert.equal((await response.json()).availability.state, "stale");
});
control("optional missing API, partial fields and true empty resources remain distinct", async () => {
    let now = 1000, calls = 0;
    const cache = new ClusterResourceCache(async (resource) => {
        calls++;
        if (resource === "longhorn")
            throw new KubernetesCommandError(404, "Kubernetes resource not found");
        if (resource === "pods")
            throw Error("private-native-marker");
        return { items: [] };
    }, () => now);
    const result = await cache.read(["nodes", "pods", "longhorn"]);
    assert.equal(result.nodes?.availability.state, "empty");
    assert.equal(result.longhorn?.availability.state, "unsupported");
    assert.equal(result.longhorn?.availability.retryAfterMs, 300000);
    assert.ok(!JSON.stringify(cache.diagnostics()).includes("private-native-marker"));
    const response = clusterResponse({ availability: Object.fromEntries(Object.entries(result).map(([resource, data]) => [resource, data.availability])) }, { nodes: [], pods: [], longhornVolumes: 0 }, ["nodes"]);
    const body = await response.json();
    assert.equal(body.availability.state, "partial");
    assert.deepEqual(body.nodes, []);
    assert.equal(body.pods, null);
    assert.equal(body.longhornVolumes, null);
    now += 2000;
    await cache.read(["longhorn"]);
    assert.equal(calls, 3);
});
control("mutation invalidation prevents an older in-flight snapshot from repopulating cache", async () => {
    const resolvers = [];
    const cache = new ClusterResourceCache(() => new Promise(resolve => resolvers.push(resolve)));
    const old = cache.read(["pods"]);
    cache.invalidate();
    const fresh = cache.read(["pods"]);
    resolvers[1]({ items: [{ id: "after-mutation" }] });
    await fresh;
    resolvers[0]({ items: [{ id: "before-mutation" }] });
    await old;
    assert.equal((await cache.read(["pods"])).pods?.value?.items[0].id, "after-mutation");
    assert.equal(resolvers.length, 2);
});
control("invalid and oversized lists fail without truncation", async () => {
    for (const value of [{ items: null }, { items: Array(10001).fill({}) }]) {
        const cache = new ClusterResourceCache(async () => value);
        const result = await cache.read(["pods"]);
        assert.equal(result.pods?.availability.state, "unavailable");
        assert.equal(result.pods?.value, undefined);
    }
});
// END EXACT ORIGINAL TYPE-ERASED PROJECTION
assert.equal(count, 5);
