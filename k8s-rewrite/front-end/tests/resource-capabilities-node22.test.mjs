// DISTINCT NEW three PUBLIC selected-copy controls; historical callbacks remain frozen.
// Infrastructure selects exact copied app declarations and the minimal pure YAML module closure.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { dirname, resolve, relative } from 'node:path';
import { pathToFileURL } from 'node:url';
import vm from 'node:vm';
const require = createRequire(import.meta.url), ts = require('typescript');
assert.equal(ts.version, '5.9.3');
const digest = source => createHash('sha256').update(source).digest('hex');
const pin = (path, hash) => {
  const source = readFileSync(new URL('../' + path, import.meta.url), 'utf8').replaceAll('\r\n', '\n');
  assert.equal(digest(source), hash, path);
  return ts.createSourceFile(path, source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
};
const capabilityAST = pin('src/lib/resource-capabilities.ts', '48bcb1e2cfa2619facdd494d9123df6368099e6d602ec5b85016dc82c88feda7');
const yamlAST = pin('src/lib/resource-yaml.ts', '556b2e5b9c72d95276019f60b9a09efdc87c61d331580265529984ad933d8cf3');
const runtimeAST = pin('src/lib/runtime-capabilities.ts', 'a53ca135150bfff5bf9da32818814f1c7c8b13f1db9edd5c56db69185d0540d2');
const dependencyAST = (path, hash) => {
  const source = readFileSync(path, 'utf8'); assert.equal(digest(source), hash, path);
  return ts.createSourceFile(path, source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.JS);
};
const depRoot = dirname(require.resolve('@kubernetes/client-node/dist/serializer.js'));
const dependencyYamlAST = dependencyAST(resolve(depRoot, 'yaml.js'), 'b25bdd3a2ef2a9c1c672354a759fe88d1a91e64d39d9b6fcaef1ca03d485fedd');
const dependencyUtilAST = dependencyAST(resolve(depRoot, 'util.js'), 'eff5a07b76cfdbc2621ff511486af9ffd6d7458c355c3baf0b81f92a65c32aed');
// Pin the complete original pure model registry. No selected registry or model rewrites.
const pureFiles = new Map();
function readPure(path) {
  const name = relative(depRoot, path).replaceAll('\\', '/');
  assert.ok(name === 'serializer.js' || /^gen\/models\/[^/]+\.js$/.test(name), name);
  if (pureFiles.has(name)) return;
  const text = readFileSync(path, 'utf8'); pureFiles.set(name, digest(text));
  const tree = ts.createSourceFile(path, text, ts.ScriptTarget.ES2022, true, ts.ScriptKind.JS);
  for (const n of tree.statements) if ((ts.isImportDeclaration(n) || ts.isExportDeclaration(n)) && n.moduleSpecifier) {
    assert.ok(n.moduleSpecifier.text.startsWith('.'), name);
    readPure(resolve(dirname(path), n.moduleSpecifier.text));
  }
}
readPure(resolve(depRoot, 'serializer.js'));
assert.equal(pureFiles.size, 719);
assert.equal(digest(JSON.stringify(Object.fromEntries([...pureFiles].sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)))), 'a7f9b91dd36ffb30c8dd127be25a52d2af4dd4fe7aeb637da2b627bfc4d9c0a0');
const parserPath = resolve(dirname(require.resolve('js-yaml/package.json')), 'dist/js-yaml.mjs');
assert.equal(digest(readFileSync(parserPath)), 'cea276c7e15f409a1adbe5d177aba7824398a474f7cf702bd57962c7d570636f');
const yaml = (await import(pathToFileURL(parserPath).href)).default;
const { ObjectSerializer } = await import(pathToFileURL(resolve(depRoot, 'serializer.js')).href);
const declaration = (tree, name) => {
  const found = tree.statements.filter(n => ts.isFunctionDeclaration(n) ? n.name?.text === name : ts.isVariableStatement(n) && n.declarationList.declarations.some(d => ts.isIdentifier(d.name) && d.name.text === name));
  assert.equal(found.length, 1, name);
  return found[0].getText(tree).replace(/^export\s+/, '');
};
const selected = [declaration(capabilityAST, 'RESOURCE_CAPABILITIES'), declaration(capabilityAST, 'resourceBase'), declaration(dependencyUtilAST, 'getSerializationType'), declaration(dependencyUtilAST, 'groupVersion'), declaration(dependencyYamlAST, 'loadAllYaml'), declaration(yamlAST, 'validateResourceYaml'), declaration(runtimeAST, 'runtimeCapabilities')].join('\n');
const lowered = ts.transpileModule(selected, { reportDiagnostics: true, compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
assert.equal(lowered.diagnostics.length, 0);
class KubernetesCommandError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
const factory = vm.runInThisContext(`(function(yaml, ObjectSerializer, KubernetesCommandError, Buffer, process) { "use strict";\n${lowered.outputText}\nreturn { RESOURCE_CAPABILITIES, resourceBase, validateResourceYaml, runtimeCapabilities }; })`, { timeout: 1000 });
const { RESOURCE_CAPABILITIES, resourceBase, validateResourceYaml, runtimeCapabilities } = factory(yaml, ObjectSerializer, KubernetesCommandError, Buffer, process);
let count = 0;
const control = (...args) => { count++; return test(...args); };
// BEGIN EXACT ORIGINAL TYPE-ERASED PROJECTION
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";



control("every declared resource read/edit/delete/action capability has a matching handler", () => {
    for (const [type, capability] of Object.entries(RESOURCE_CAPABILITIES)) {
        const target = type === "node" ? "[hostname]" : capability.namespaced ? "[namespace]/[name]" : "[name]";
        const root = `src/app/api/cluster/${capability.collection}/${target}`;
        assert.ok(existsSync(`${root}/yaml/route.ts`), `${type} YAML route`);
        if (capability.delete)
            assert.ok(existsSync(`${root}/delete/route.ts`), `${type} delete route`);
        if (capability.logs)
            assert.ok(existsSync(`${root}/logs/route.ts`), `${type} log route`);
        if (capability.actions.length)
            assert.ok(existsSync(`${root}/action/route.ts`), `${type} action route`);
        assert.ok(resourceBase(type, "apps", "name --raw").endsWith("name%20--raw"));
    }
    assert.ok(existsSync("src/app/api/cluster/pods/[namespace]/[name]/exec/route.ts"));
});
control("resource YAML cannot switch identity/kind, apply a list, or bypass resourceVersion", () => {
    const valid = 'apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: demo\n  namespace: apps\n  resourceVersion: "10"\nspec:\n  replicas: 0\n';
    assert.equal(validateResourceYaml("deployment", "demo", "apps", valid), valid);
    for (const invalid of [
        valid.replace("name: demo", "name: other"), valid.replace("namespace: apps", "namespace: other"),
        valid.replace("kind: Deployment", "kind: Secret"), valid.replace("apiVersion: apps/v1", "apiVersion: v1"),
        `${valid}\n---\n${valid}`, "kind: [", null, "x".repeat(262145),
    ])
        assert.throws(() => validateResourceYaml("deployment", "demo", "apps", invalid), { status: 400 });
    assert.throws(() => validateResourceYaml("deployment", "demo", "apps", valid.replace('  resourceVersion: "10"\n', "")), { status: 428 });
    assert.throws(() => validateResourceYaml("deployment", "demo", "apps", valid.replace('resourceVersion: "10"', "resourceVersion: 10")), { status: 428 });
});
control("runtime capability flags match provisioning and shell server boundaries", () => {
    assert.deepEqual(runtimeCapabilities({}, "linux"), { provisioning: true, operatorShell: true, podExec: true });
    assert.equal(runtimeCapabilities({}, "win32").operatorShell, false);
    assert.equal(runtimeCapabilities({ KUBERNETES_SERVICE_HOST: "fixture" }, "linux").provisioning, false);
    assert.deepEqual(runtimeCapabilities({ BORTUS_DISABLE_PROVISIONING: "true", BORTUS_DISABLE_OPERATOR_SHELL: "true", BORTUS_DISABLE_POD_EXEC: "true" }, "linux"), { provisioning: false, operatorShell: false, podExec: false });
});
// END EXACT ORIGINAL TYPE-ERASED PROJECTION
assert.equal(count, 3);
