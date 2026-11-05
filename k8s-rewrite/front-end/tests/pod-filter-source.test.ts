import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import vm from "node:vm";
import { createHash } from "node:crypto";

// NEW finite source controls. No application module or neighboring declaration imports.
const raw = readFileSync(new URL("../src/lib/pod-query.ts", import.meta.url), "utf8");
const begin = raw.indexOf("export function podFilter(");
assert.ok(begin >= 0);
const next = raw.indexOf("\nexport ", begin + 1);
const selected = raw.slice(begin, next < 0 ? raw.length : next);
assert.equal(createHash("sha256").update(selected).digest("hex"), "a6cbaa0635a0e77d3d2920e75a2fc7f8c26d1719ae3ddb70446e6f39af945abe");
assert.equal((selected.match(/export function /g) || []).length, 1);
const executable = stripTypeScriptTypes(selected.replace("export function podFilter", "function podFilter")) + "\nglobalThis.selectedFilter = podFilter;";
type Pod = { metadata?: { namespace?: unknown; labels?: unknown } | null };
type Filter = (query: URLSearchParams) => (pod: Pod) => boolean;
type Options = { namespaceError?: Error; factoryError?: Error; labelError?: Error; setError?: Error; labelResult?: boolean };
class SyntheticCommandError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}
function fixture(options: Options = {}) {
  const events: unknown[][] = [];
  const context = vm.createContext({
    KubernetesCommandError: SyntheticCommandError,
    validateNamespace: (namespace: unknown) => { events.push(["namespace", namespace]); if (options.namespaceError) throw options.namespaceError; },
    labelPredicate: (selector: unknown) => {
      events.push(["factory", selector]); if (options.factoryError) throw options.factoryError;
      return (labels: unknown) => { events.push(["labels", labels]); if (options.labelError) throw options.labelError; return options.labelResult ?? true; };
    },
    SYSTEM_NAMESPACES: Object.freeze({ has: (namespace: unknown) => { events.push(["system", namespace]); if (options.setError) throw options.setError; return namespace === "kube-system" || namespace === "synthetic-system"; } }),
  });
  vm.runInContext(executable, context, { timeout: 1000 });
  return { filter: context.selectedFilter as Filter, events };
}
function query(entries: [string, string][] = [], events?: unknown[][]) {
  const value = new URLSearchParams(entries);
  if (events) {
    const get = value.get.bind(value);
    value.get = (key: string) => { events.push(["get", key]); return get(key); };
  }
  return value;
}
const kinds = (events: unknown[][]) => events.map(event => event[0]);
const pod = (namespace: unknown = "work", labels?: unknown) => ({ metadata: { namespace, labels } });

for (const [name, entries] of [
  ["missing", []], ["empty", [["type", ""]]], ["all", [["type", "all"]]],
] as [string, [string, string][]][]) {
  test(`default/all type ${name} accepts both synthetic classifications`, () => {
    const f = fixture(); const predicate = f.filter(query(entries, f.events));
    assert.deepEqual(f.events, [["get", "type"], ["get", "namespace"], ["get", "labelSelector"], ["factory", null]]);
    assert.equal(predicate(pod("work")), true); assert.equal(predicate(pod("kube-system")), true);
  });
}
for (const invalid of ["ALL", "App", "SYSTEM", " all", "app ", "other", "0", "false", "system\0", "app,system", "\n", "undefined"]) {
  test(`invalid type ${JSON.stringify(invalid)} refuses after both initial reads`, () => {
    const f = fixture();
    assert.throws(() => f.filter(query([["type", invalid], ["namespace", "bad"]], f.events)), e => e instanceof SyntheticCommandError && e.status === 400 && e.message === "Invalid pod type");
    assert.deepEqual(f.events, [["get", "type"], ["get", "namespace"]]);
  });
}
for (const namespace of ["", "work", " synthetic ", "kube-system"]) {
  test(`nonnull namespace ${JSON.stringify(namespace)} validates before selector construction`, () => {
    const f = fixture(); f.filter(query([["namespace", namespace], ["labelSelector", "synthetic-selector"]], f.events));
    assert.deepEqual(f.events, [["get", "type"], ["get", "namespace"], ["namespace", namespace], ["get", "labelSelector"], ["factory", "synthetic-selector"]]);
  });
}
test("namespace dependency failure precedes selector read and is preserved", () => {
  const error = new Error("synthetic-namespace"); const f = fixture({ namespaceError: error });
  assert.throws(() => f.filter(query([["namespace", ""]], f.events)), e => e === error);
  assert.deepEqual(kinds(f.events), ["get", "get", "namespace"]);
});
test("selector construction failure occurs after namespace validation", () => {
  const error = new Error("synthetic-factory"); const f = fixture({ factoryError: error });
  assert.throws(() => f.filter(query([["namespace", "work"]], f.events)), e => e === error);
  assert.deepEqual(kinds(f.events), ["get", "get", "namespace", "get", "factory"]);
});
for (const selector of [null, "", "a=b", "synthetic-invalid(()"]) {
  test(`selector ${JSON.stringify(selector)} is forwarded once to inert factory`, () => {
    const f = fixture(); const entries: [string, string][] = selector === null ? [] : [["labelSelector", selector]];
    f.filter(query(entries)); assert.deepEqual(f.events, [["factory", selector]]);
  });
}
test("duplicate query keys use the first value from actual URLSearchParams", () => {
  const f = fixture(); const p = f.filter(query([["type", "app"], ["type", "bad"], ["namespace", "work"], ["namespace", "else"], ["labelSelector", "first"], ["labelSelector", "second"]]));
  assert.equal(p(pod("work")), true); assert.equal(p(pod("else")), false);
  assert.deepEqual(f.events.slice(0, 2), [["namespace", "work"], ["factory", "first"]]);
});
test("irrelevant query keys are not read", () => {
  const f = fixture(); f.filter(query([["unknown", "text"]], f.events));
  assert.deepEqual(f.events.filter(e => e[0] === "get").map(e => e[1]), ["type", "namespace", "labelSelector"]);
});
for (const type of ["app", "system"]) {
  for (const [name, ns, labels, expected, setRead] of [
    ["work fallback", "work", {}, "app", true],
    ["system fallback", "kube-system", {}, "system", true],
    ["synthetic set", "synthetic-system", {}, "system", true],
    ["app override in system", "kube-system", { "branconet.io/type": "app" }, "app", false],
    ["system override in work", "work", { "branconet.io/type": "system" }, "system", false],
    ["unknown override in system", "kube-system", { "branconet.io/type": "other" }, "system", true],
    ["case sensitive override", "work", { "branconet.io/type": "System" }, "app", true],
  ] as [string, unknown, unknown, string, boolean][]) {
    test(`${type} filter: ${name}`, () => {
      const f = fixture(); const p = f.filter(query([["type", type]])); f.events.length = 0;
      assert.equal(p(pod(ns, labels)), type === expected);
      assert.equal(f.events.some(e => e[0] === "system"), setRead);
      assert.equal(f.events.some(e => e[0] === "labels"), type === expected);
    });
  }
}
for (const override of [undefined, null, false, 0, "", ["app"], { value: "system" }]) {
  test(`nonmatching override ${JSON.stringify(override)} uses inert namespace set`, () => {
    const f = fixture(); const p = f.filter(query([["type", "system"]])); f.events.length = 0;
    assert.equal(p(pod("kube-system", { "branconet.io/type": override })), true);
    assert.equal(f.events[0][0], "system");
  });
}
for (const [name, value] of [["absent metadata", {}], ["null metadata", { metadata: null }], ["missing namespace", { metadata: {} }], ["empty namespace", pod("")], ["null namespace", pod(null)], ["zero namespace", pod(0)]] as [string, Pod][]) {
  test(`${name} resolves to default and app through synthetic set`, () => {
    const f = fixture(); const p = f.filter(query([["type", "app"], ["namespace", "default"]])); f.events.length = 0;
    assert.equal(p(value), true); assert.deepEqual(f.events[0], ["system", "default"]);
  });
}
for (const labels of [undefined, null, false, 0, ""]) {
  test(`falsey labels ${JSON.stringify(labels)} supply a fresh empty map`, () => {
    const f = fixture(); const p = f.filter(query()); f.events.length = 0;
    assert.equal(p(pod("work", labels)), true);
    const passed = f.events.find(e => e[0] === "labels")?.[1];
    assert.equal(typeof passed, "object"); assert.equal(Object.keys(passed as object).length, 0);
  });
}
test("metadata label object is forwarded without copying", () => {
  const f = fixture(); const labels = { a: "b" }; const p = f.filter(query()); f.events.length = 0;
  assert.equal(p(pod("work", labels)), true); assert.equal(f.events.find(e => e[0] === "labels")?.[1], labels);
});
test("type mismatch shortcircuits namespace and labels conjunction", () => {
  const f = fixture({ labelError: new Error("must stay inert") }); const p = f.filter(query([["type", "system"], ["namespace", "work"]])); f.events.length = 0;
  assert.equal(p(pod("work")), false); assert.deepEqual(f.events, [["system", "work"]]);
});
test("namespace mismatch shortcircuits label predicate", () => {
  const f = fixture({ labelError: new Error("must stay inert") }); const p = f.filter(query([["namespace", "wanted"]])); f.events.length = 0;
  assert.equal(p(pod("other")), false); assert.deepEqual(f.events, [["system", "other"]]);
});
test("matching type and namespace evaluate labels last and preserve false", () => {
  const f = fixture({ labelResult: false }); const labels = {}; const p = f.filter(query([["type", "app"], ["namespace", "work"]])); f.events.length = 0;
  assert.equal(p(pod("work", labels)), false); assert.deepEqual(f.events, [["system", "work"], ["labels", labels]]);
});
test("late label dependency error propagates only after both filters match", () => {
  const error = new Error("synthetic-label"); const f = fixture({ labelError: error }); const p = f.filter(query());
  assert.throws(() => p(pod()), e => e === error);
});
test("set dependency fault propagates even under all type", () => {
  const error = new Error("synthetic-set"); const f = fixture({ setError: error }); const p = f.filter(query());
  assert.throws(() => p(pod()), e => e === error);
});
test("recognized override bypasses failing synthetic namespace set", () => {
  const f = fixture({ setError: new Error("must stay inert") }); const p = f.filter(query());
  assert.equal(p(pod("work", { "branconet.io/type": "app" })), true);
  assert.equal(f.events.some(e => e[0] === "system"), false);
});
test("query configuration is captured before later URLSearchParams mutations", () => {
  const f = fixture(); const q = query([["type", "app"], ["namespace", "work"], ["labelSelector", "initial"]]); const p = f.filter(q);
  q.set("type", "system"); q.set("namespace", "else"); q.set("labelSelector", "changed");
  assert.equal(p(pod("work")), true); assert.equal(p(pod("else")), false);
  assert.deepEqual(f.events.filter(e => e[0] === "factory"), [["factory", "initial"]]);
});
test("metadata type and namespace are fresh on every predicate call", () => {
  const f = fixture(); const p = f.filter(query([["type", "app"], ["namespace", "work"]]));
  const value = { metadata: { namespace: "work", labels: { "branconet.io/type": "app" } } };
  assert.equal(p(value), true); value.metadata.labels["branconet.io/type"] = "system"; assert.equal(p(value), false);
  value.metadata.labels["branconet.io/type"] = "app"; value.metadata.namespace = "else"; assert.equal(p(value), false);
});
test("metadata access order is namespace then labels, with two metadata reads", () => {
  const f = fixture(); const labels = {}; const metadata = { get namespace() { f.events.push(["ns-get"]); return "work"; }, get labels() { f.events.push(["labels-get"]); return labels; } };
  const value = { get metadata() { f.events.push(["metadata-get"]); return metadata; } };
  const p = f.filter(query()); f.events.length = 0; assert.equal(p(value), true);
  assert.deepEqual(kinds(f.events), ["metadata-get", "ns-get", "metadata-get", "labels-get", "system", "labels"]);
});
test("override getter is read once and before set membership", () => {
  const f = fixture(); const labels = { get "branconet.io/type"() { f.events.push(["override-get"]); return "other"; } };
  const p = f.filter(query()); f.events.length = 0; assert.equal(p(pod("work", labels)), true);
  assert.deepEqual(kinds(f.events), ["override-get", "system", "labels"]);
});
test("inherited recognized override is characterized as ordinary property access", () => {
  const f = fixture(); const labels = Object.create({ "branconet.io/type": "system" }); const p = f.filter(query([["type", "system"]]));
  assert.equal(p(pod("work", labels)), true); assert.equal(f.events.some(e => e[0] === "system"), false);
});
test("metadata getter exception is preserved before classification", () => {
  const error = new Error("synthetic-metadata"); const f = fixture(); const p = f.filter(query()); f.events.length = 0;
  assert.throws(() => p({ get metadata(): never { throw error; } }), e => e === error); assert.deepEqual(f.events, []);
});
test("override getter exception is preserved before set or labels", () => {
  const error = new Error("synthetic-override"); const f = fixture(); const p = f.filter(query()); f.events.length = 0;
  assert.throws(() => p(pod("work", { get "branconet.io/type"(): never { throw error; } })), e => e === error); assert.deepEqual(f.events, []);
});
test("synthetic query read fault preserves first-read ordering", () => {
  const error = new Error("synthetic-query"); const f = fixture(); const q = query();
  q.get = (key: string) => { f.events.push(["get", key]); if (key === "namespace") throw error; return "all"; };
  assert.throws(() => f.filter(q), e => e === error); assert.deepEqual(f.events, [["get", "type"], ["get", "namespace"]]);
});
test("empty namespace is retained rather than converted to no filter", () => {
  const f = fixture(); const p = f.filter(query([["namespace", ""]])); f.events.length = 0;
  assert.equal(p(pod("")), false); assert.equal(p(pod("default")), false); assert.equal(f.events.some(e => e[0] === "labels"), false);
});
test("separate filter constructions retain distinct selector predicate results", () => {
  const yes = fixture(); const no = fixture({ labelResult: false });
  const a = yes.filter(query([["labelSelector", "one"]])); const b = no.filter(query([["labelSelector", "two"]]));
  assert.equal(a(pod()), true); assert.equal(b(pod()), false);
});
