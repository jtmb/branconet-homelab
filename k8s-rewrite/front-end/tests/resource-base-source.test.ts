import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire, stripTypeScriptTypes } from "node:module";
import test from "node:test";
import vm from "node:vm";

// Infrastructure binding is mandatory. No application module is imported/evaluated.
const compiler = process.env.BORTUS_SOURCE_TYPESCRIPT;
assert.ok(compiler, "explicit BORTUS_SOURCE_TYPESCRIPT infrastructure binding required");
const ts = createRequire(import.meta.url)(compiler) as typeof import("typescript");
const source = readFileSync(new URL("../src/lib/resource-capabilities.ts", import.meta.url), "utf8");
const ast = ts.createSourceFile("resource-capabilities.ts", source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
const declarations = ast.statements.filter((s): s is import("typescript").FunctionDeclaration =>
  ts.isFunctionDeclaration(s) && s.name?.text === "resourceBase" &&
  !!s.modifiers?.some(m => m.kind === ts.SyntaxKind.ExportKeyword));
assert.equal(declarations.length, 1);
const selected = stripTypeScriptTypes(declarations[0].getText(ast).replace(/^export\s+/, ""));
type SourceFunction = (type: unknown, namespace: unknown, name: unknown) => string;
type Encoder = (value: unknown) => unknown;
const records = {
  pod: { collection: "pods", namespaced: true },
  deployment: { collection: "deployments", namespaced: true },
  namespace: { collection: "namespaces", namespaced: false },
  node: { collection: "nodes", namespaced: false },
  ingress: { collection: "ingresses", namespaced: true },
  service: { collection: "services", namespaced: true },
  pvc: { collection: "volumes", namespaced: true },
} as const;
// Synthetic inert public records; the actual registry initializer remains inert.
function load(registry: unknown = records, encoder: Encoder = value => encodeURIComponent(value as string)) {
  return vm.runInNewContext(`(${selected})`, {
    RESOURCE_CAPABILITIES: registry, encodeURIComponent: encoder,
  }, { timeout: 1000 }) as SourceFunction;
}
const cases = [
  ["plain", "public-name", "public-name"], ["space", "public name", "public%20name"],
  ["slash", "public/name", "public%2Fname"], ["percent", "public%2Fname", "public%252Fname"],
  ["query", "public?name", "public%3Fname"], ["fragment", "public#name", "public%23name"],
  ["unicode", "caf\u00e9", "caf%C3%A9"], ["astral", "public-\u{1f680}", "public-%F0%9F%9A%80"],
  ["empty", "", ""], ["reserved", "a:b@c&d=e+f", "a%3Ab%40c%26d%3De%2Bf"],
] as const;
for (const [type, capability] of Object.entries(records)) {
  for (const [label, name, encoded] of cases) {
    test(`${type} name ${label}: exact source string using synthetic registry`, () => {
      const expected = `/api/cluster/${capability.collection}/${capability.namespaced ? "public-ns/" : ""}${encoded}`;
      assert.equal(load()(type, "public-ns", name), expected);
    });
  }
  test(`${type}: namespace encoding and calls follow namespaced branch`, () => {
    const calls: unknown[] = [];
    const f = load(records, value => { calls.push(value); return encodeURIComponent(value as string); });
    assert.equal(f(type, "public/ns?#%", "public/name"),
      `/api/cluster/${capability.collection}/${capability.namespaced ? "public%2Fns%3F%23%25/" : ""}public%2Fname`);
    assert.deepEqual(calls, capability.namespaced ? ["public/ns?#%", "public/name"] : ["public/name"]);
  });
}
for (const [label, namespace, encoded] of cases) {
  test(`namespaced namespace ${label}`, () => {
    assert.equal(load()("pod", namespace, "public-name"), `/api/cluster/pods/${encoded}/public-name`);
  });
}
test("captured capability: registry read once, collection coercion before namespaced, namespace before name", () => {
  const order: string[] = [];
  const registry = new Proxy({}, { get: (_target, key) => {
    order.push(`registry:${String(key)}`);
    return {
      get collection() { order.push("collection"); return { toString() { order.push("collection:coerce"); return "public-collection"; } }; },
      get namespaced() { order.push("namespaced"); return true; },
    };
  } });
  const f = load(registry, value => { order.push(`encode:${String(value)}`); return { toString() { order.push(`result:${String(value)}`); return `public-${String(value)}`; } }; });
  assert.equal(f("pod", "ns", "name"), "/api/cluster/public-collection/public-ns/public-name");
  assert.deepEqual(order, ["registry:pod", "collection", "collection:coerce", "namespaced", "encode:ns", "result:ns", "encode:name", "result:name"]);
});
test("cluster-scoped branch skips hostile namespace coercion and namespace encoder", () => {
  const namespace = { toString() { throw new Error("namespace must remain inert"); } };
  assert.equal(load()("node", namespace, "public-node"), "/api/cluster/nodes/public-node");
});
test("namespaced lone surrogate fails in namespace before name encoding", () => {
  const calls: unknown[] = [];
  const f = load(records, value => { calls.push(value); return encodeURIComponent(value as string); });
  assert.throws(() => f("pod", "\ud800", "public-name"), URIError);
  assert.deepEqual(calls, ["\ud800"]);
});
test("cluster-scoped lone surrogate namespace is skipped", () => {
  assert.equal(load()("node", "\ud800", "public-node"), "/api/cluster/nodes/public-node");
});
for (const type of ["pod", "node"]) {
  test(`${type}: name lone surrogate propagates builtin failure`, () => {
    assert.throws(() => load()(type, "public-ns", "\udfff"), URIError);
  });
}
for (const step of ["registry", "collection", "collection-coercion", "namespaced", "namespace-encode", "namespace-result", "name-encode", "name-result"] as const) {
  test(`immediate ${step} failure propagates unchanged and stops all later work`, () => {
    const marker = new Error(`public-${step}`);
    const order: string[] = [];
    const hit = (label: string) => { order.push(label); if (label === step) throw marker; };
    const registry = new Proxy({}, { get: () => {
      hit("registry");
      return {
        get collection() { hit("collection"); return { toString() { hit("collection-coercion"); return "public"; } }; },
        get namespaced() { hit("namespaced"); return true; },
      };
    } });
    const f = load(registry, value => {
      const prefix = value === "public-ns" ? "namespace" : "name";
      hit(`${prefix}-encode`);
      return { toString() { hit(`${prefix}-result`); return "public"; } };
    });
    assert.throws(() => f("pod", "public-ns", "public-name"), error => error === marker);
    const all = ["registry", "collection", "collection-coercion", "namespaced", "namespace-encode", "namespace-result", "name-encode", "name-result"];
    assert.deepEqual(order, all.slice(0, all.indexOf(step) + 1));
  });
}
for (const namespaced of [false, 0, "", null, undefined, true, 1, "public", {}]) {
  test(`synthetic namespaced truthiness ${String(namespaced)}`, () => {
    const calls: unknown[] = [];
    const f = load({ pod: { collection: "public", namespaced } }, value => { calls.push(value); return value; });
    assert.equal(f("pod", "public-ns", "public-name"), `/api/cluster/public/${namespaced ? "public-ns/" : ""}public-name`);
    assert.deepEqual(calls, namespaced ? ["public-ns", "public-name"] : ["public-name"]);
  });
}
test("runtime unknown type fails before encoder; outside ResourceType contract", () => {
  const calls: unknown[] = [];
  assert.throws(() => load(records, x => { calls.push(x); return x; })("public-unknown", "public-ns", "public-name"),
    error => typeof error === "object" && error !== null && "name" in error && error.name === "TypeError");
  assert.deepEqual(calls, []);
});
test("type key coercion occurs once before registry read; synthetic characterization only", () => {
  const order: string[] = [];
  const type = { toString() { order.push("type"); return "pod"; } };
  const registry = new Proxy(records, { get: (target, key) => { order.push(`registry:${String(key)}`); return Reflect.get(target, key); } });
  assert.equal(load(registry)(type, "public-ns", "public-name"), "/api/cluster/pods/public-ns/public-name");
  assert.deepEqual(order, ["type", "registry:pod"]);
});
test("encoder binding is read again for name after namespace call", () => {
  const sandbox = { RESOURCE_CAPABILITIES: records };
  const order: string[] = [];
  let reads = 0;
  Object.defineProperty(sandbox, "encodeURIComponent", { get() {
    const n = ++reads;
    order.push(`get:${n}`);
    return (value: unknown) => { order.push(`call:${n}:${String(value)}`); return `public-${n}`; };
  } });
  const f = vm.runInNewContext(`(${selected})`, sandbox, { timeout: 1000 }) as SourceFunction;
  assert.equal(f("pod", "public-ns", "public-name"), "/api/cluster/pods/public-1/public-2");
  assert.deepEqual(order, ["get:1", "call:1:public-ns", "get:2", "call:2:public-name"]);
});
test("valid Unicode strings are not normalized by this source helper", () => {
  assert.equal(load()("pod", "public-ns", "e\u0301"), "/api/cluster/pods/public-ns/e%CC%81");
});
test("literal dot name remains builtin behavior only; no HTTP routing claim", () => {
  assert.equal(load()("pod", "public-ns", ".."), "/api/cluster/pods/public-ns/..");
});
