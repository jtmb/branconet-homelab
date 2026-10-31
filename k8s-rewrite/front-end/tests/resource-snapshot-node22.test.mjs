// DISTINCT NEW one PUBLIC selected-copy control. Original application modules stay inert.
import infrastructureAssert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
const ts = createRequire(import.meta.url)('typescript');
infrastructureAssert.equal(ts.version, '5.9.3');
const pin = (path, hash) => {
  const text = readFileSync(new URL('../' + path, import.meta.url), 'utf8').replaceAll('\r\n', '\n');
  infrastructureAssert.equal(createHash('sha256').update(text).digest('hex'), hash, path);
  return ts.createSourceFile(path, text, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
};
const cacheAST = pin('src/lib/resource-cache.ts', 'd8ffefde0b8b2449b9c038e9547a330ffe7dc060dcb9a410c97696e08382bbb9');
const clusterAST = pin('src/lib/cluster-cache.ts', '2bbb6109dff38bbba691f601646cebd1691bbf55bae36639f4e88573ff38ceb0');
const declaration = (tree, name) => {
  const matches = tree.statements.filter(n => (ts.isClassDeclaration(n) || ts.isFunctionDeclaration(n)) && n.name?.text === name);
  infrastructureAssert.equal(matches.length, 1, name);
  return matches[0].getText(tree).replace(/^export\s+/, '');
};
const lower = text => {
  const result = ts.transpileModule(text, { reportDiagnostics: true, compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, useDefineForClassFields: true } });
  infrastructureAssert.equal(result.diagnostics.length, 0);
  return result.outputText;
};
class KubernetesCommandError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
const cacheSource = lower(declaration(cacheAST, 'ClusterResourceCache'));
const { ClusterResourceCache } = vm.runInNewContext('"use strict";\n' + cacheSource + '\n({ ClusterResourceCache })', { KubernetesCommandError }, { timeout: 1000 });
// Isolated fixture globals. No actual process-wide cache singleton is initialized.
const globalThis = Object.create(null);
const selectedFunctions = lower(['getCachedClusterResource', 'invalidateCache'].map(name => declaration(clusterAST, name)).join('\n'));
const selectedModuleURL = 'data:text/javascript,' + encodeURIComponent('export function bind(resourcesCache) {\n' + selectedFunctions + '\nreturn { getCachedClusterResource, invalidateCache };\n}');
async function selectedImport(name) {
  infrastructureAssert.equal(name, '../src/lib/cluster-cache');
  infrastructureAssert.ok(globalThis.__bortusResources instanceof ClusterResourceCache);
  const namespace = await import(selectedModuleURL);
  return namespace.bind(globalThis.__bortusResources);
}
let count = 0;
const control = (...args) => { count++; return test(...args); };
// BEGIN EXACT ORIGINAL TYPE-ERASED PROJECTION
import { test } from "node:test";
import assert from "node:assert/strict";


control("resource-only warm read skips overview derivation and preserves TTL, stale expiry and invalidation", async () => {
    let now = 1000, calls = 0, overviewReads = 0, fail = false;
    const pods = [{ metadata: { name: "one" }, get status() { overviewReads++; throw Error("Overview must not scan resource-only read"); } }];
    const cache = new ClusterResourceCache(async (resource) => { assert.equal(resource, "pods"); calls++; if (fail)
        throw new KubernetesCommandError(502, "Kubernetes command failed"); return { items: pods }; }, () => now);
    globalThis.__bortusResources = cache;
    const { getCachedClusterResource, invalidateCache } = await selectedImport("../src/lib/cluster-cache");
    const first = await getCachedClusterResource("pods");
    await Promise.all(Array.from({ length: 20 }, () => getCachedClusterResource("pods")));
    assert.equal(calls, 1);
    assert.equal(overviewReads, 0);
    assert.equal(first.value?.items, pods);
    fail = true;
    now += 10001;
    assert.equal((await getCachedClusterResource("pods")).availability.state, "stale");
    now += 120001;
    assert.equal((await getCachedClusterResource("pods")).availability.state, "unavailable");
    fail = false;
    invalidateCache();
    assert.equal((await getCachedClusterResource("pods")).availability.state, "healthy");
    assert.equal(overviewReads, 0);
});
// END EXACT ORIGINAL TYPE-ERASED PROJECTION
assert.equal(count, 1);
