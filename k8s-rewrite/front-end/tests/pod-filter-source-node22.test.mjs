import infrastructureAssert from 'node:assert/strict';
import {readFileSync as infrastructureRead} from 'node:fs';
import {createHash as infrastructureHash} from 'node:crypto';
const infrastructureDigest=x=>infrastructureHash('sha256').update(x).digest('hex');
infrastructureAssert.equal(process.versions.node,'22.23.3');
const infrastructureOriginal=infrastructureRead(new URL('./pod-filter-source.test.ts',import.meta.url),'utf8');
const infrastructureSource=infrastructureRead(new URL('../src/lib/pod-query.ts',import.meta.url),'utf8');
infrastructureAssert.equal(infrastructureDigest(infrastructureOriginal),'b4d89c2f914f1451580452fef494bdf5e781dd1ad55645e073869d7e432e3e4f');
infrastructureAssert.equal(infrastructureDigest(infrastructureSource),'fe5a030155f1be0a0d2f9cce914545233ab8d44fa8e707831697946fa7e7f3c5');
const infrastructureCRLF=infrastructureSource.replaceAll('\n','\r\n');
const infrastructureBegin=infrastructureCRLF.indexOf('export function podFilter(');
const infrastructureNext=infrastructureCRLF.indexOf('\nexport ',infrastructureBegin+1);
infrastructureAssert.equal(infrastructureDigest(infrastructureCRLF.slice(infrastructureBegin,infrastructureNext<0?infrastructureCRLF.length:infrastructureNext)),'a6cbaa0635a0e77d3d2920e75a2fc7f8c26d1719ae3ddb70446e6f39af945abe');
const infrastructureOrder=["default/all type missing accepts both synthetic classifications","default/all type empty accepts both synthetic classifications","default/all type all accepts both synthetic classifications","invalid type \"ALL\" refuses after both initial reads","invalid type \"App\" refuses after both initial reads","invalid type \"SYSTEM\" refuses after both initial reads","invalid type \" all\" refuses after both initial reads","invalid type \"app \" refuses after both initial reads","invalid type \"other\" refuses after both initial reads","invalid type \"0\" refuses after both initial reads","invalid type \"false\" refuses after both initial reads","invalid type \"system\\u0000\" refuses after both initial reads","invalid type \"app,system\" refuses after both initial reads","invalid type \"\\n\" refuses after both initial reads","invalid type \"undefined\" refuses after both initial reads","nonnull namespace \"\" validates before selector construction","nonnull namespace \"work\" validates before selector construction","nonnull namespace \" synthetic \" validates before selector construction","nonnull namespace \"kube-system\" validates before selector construction","namespace dependency failure precedes selector read and is preserved","selector construction failure occurs after namespace validation","selector null is forwarded once to inert factory","selector \"\" is forwarded once to inert factory","selector \"a=b\" is forwarded once to inert factory","selector \"synthetic-invalid(()\" is forwarded once to inert factory","duplicate query keys use the first value from actual URLSearchParams","irrelevant query keys are not read","app filter: work fallback","app filter: system fallback","app filter: synthetic set","app filter: app override in system","app filter: system override in work","app filter: unknown override in system","app filter: case sensitive override","system filter: work fallback","system filter: system fallback","system filter: synthetic set","system filter: app override in system","system filter: system override in work","system filter: unknown override in system","system filter: case sensitive override","nonmatching override undefined uses inert namespace set","nonmatching override null uses inert namespace set","nonmatching override false uses inert namespace set","nonmatching override 0 uses inert namespace set","nonmatching override \"\" uses inert namespace set","nonmatching override [\"app\"] uses inert namespace set","nonmatching override {\"value\":\"system\"} uses inert namespace set","absent metadata resolves to default and app through synthetic set","null metadata resolves to default and app through synthetic set","missing namespace resolves to default and app through synthetic set","empty namespace resolves to default and app through synthetic set","null namespace resolves to default and app through synthetic set","zero namespace resolves to default and app through synthetic set","falsey labels undefined supply a fresh empty map","falsey labels null supply a fresh empty map","falsey labels false supply a fresh empty map","falsey labels 0 supply a fresh empty map","falsey labels \"\" supply a fresh empty map","metadata label object is forwarded without copying","type mismatch shortcircuits namespace and labels conjunction","namespace mismatch shortcircuits label predicate","matching type and namespace evaluate labels last and preserve false","late label dependency error propagates only after both filters match","set dependency fault propagates even under all type","recognized override bypasses failing synthetic namespace set","query configuration is captured before later URLSearchParams mutations","metadata type and namespace are fresh on every predicate call","metadata access order is namespace then labels, with two metadata reads","override getter is read once and before set membership","inherited recognized override is characterized as ordinary property access","metadata getter exception is preserved before classification","override getter exception is preserved before set or labels","synthetic query read fault preserves first-read ordering","empty namespace is retained rather than converted to no filter","separate filter constructions retain distinct selector predicate results"];
let infrastructureCount=0;
function infrastructureControl(name,...args){infrastructureAssert.equal(name,infrastructureOrder[infrastructureCount++]);return test(name,...args);}
// BEGIN EXACT ORIGINAL NATIVE TYPE-ERASED PROJECTION
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
assert.equal(createHash("sha256").update(selected).digest("hex"), "57866795693896ddaa0c677147bdf0e37ca91508add09fd2c906237f398e27ed");
assert.equal((selected.match(/export function /g) || []).length, 1);
const executable = stripTypeScriptTypes(selected.replace("export function podFilter", "function podFilter")) + "\nglobalThis.selectedFilter = podFilter;";
                                                                           
                                                                
                                                                                                                             
class SyntheticCommandError extends Error {
  status        ;
  constructor(status        , message        ) { super(message); this.status = status; }
}
function fixture(options          = {}) {
  const events              = [];
  const context = vm.createContext({
    KubernetesCommandError: SyntheticCommandError,
    validateNamespace: (namespace         ) => { events.push(["namespace", namespace]); if (options.namespaceError) throw options.namespaceError; },
    labelPredicate: (selector         ) => {
      events.push(["factory", selector]); if (options.factoryError) throw options.factoryError;
      return (labels         ) => { events.push(["labels", labels]); if (options.labelError) throw options.labelError; return options.labelResult ?? true; };
    },
    SYSTEM_NAMESPACES: Object.freeze({ has: (namespace         ) => { events.push(["system", namespace]); if (options.setError) throw options.setError; return namespace === "kube-system" || namespace === "synthetic-system"; } }),
  });
  vm.runInContext(executable, context, { timeout: 1000 });
  return { filter: context.selectedFilter          , events };
}
function query(entries                     = [], events              ) {
  const value = new URLSearchParams(entries);
  if (events) {
    const get = value.get.bind(value);
    value.get = (key        ) => { events.push(["get", key]); return get(key); };
  }
  return value;
}
const kinds = (events             ) => events.map(event => event[0]);
const pod = (namespace          = "work", labels          ) => ({ metadata: { namespace, labels } });

for (const [name, entries] of [
  ["missing", []], ["empty", [["type", ""]]], ["all", [["type", "all"]]],
]                                  ) {
  infrastructureControl(`default/all type ${name} accepts both synthetic classifications`, () => {
    const f = fixture(); const predicate = f.filter(query(entries, f.events));
    assert.deepEqual(f.events, [["get", "type"], ["get", "namespace"], ["get", "labelSelector"], ["factory", null]]);
    assert.equal(predicate(pod("work")), true); assert.equal(predicate(pod("kube-system")), true);
  });
}
for (const invalid of ["ALL", "App", "SYSTEM", " all", "app ", "other", "0", "false", "system\0", "app,system", "\n", "undefined"]) {
  infrastructureControl(`invalid type ${JSON.stringify(invalid)} refuses after both initial reads`, () => {
    const f = fixture();
    assert.throws(() => f.filter(query([["type", invalid], ["namespace", "bad"]], f.events)), e => e instanceof SyntheticCommandError && e.status === 400 && e.message === "Invalid pod type");
    assert.deepEqual(f.events, [["get", "type"], ["get", "namespace"]]);
  });
}
for (const namespace of ["", "work", " synthetic ", "kube-system"]) {
  infrastructureControl(`nonnull namespace ${JSON.stringify(namespace)} validates before selector construction`, () => {
    const f = fixture(); f.filter(query([["namespace", namespace], ["labelSelector", "synthetic-selector"]], f.events));
    assert.deepEqual(f.events, [["get", "type"], ["get", "namespace"], ["namespace", namespace], ["get", "labelSelector"], ["factory", "synthetic-selector"]]);
  });
}
infrastructureControl("namespace dependency failure precedes selector read and is preserved", () => {
  const error = new Error("synthetic-namespace"); const f = fixture({ namespaceError: error });
  assert.throws(() => f.filter(query([["namespace", ""]], f.events)), e => e === error);
  assert.deepEqual(kinds(f.events), ["get", "get", "namespace"]);
});
infrastructureControl("selector construction failure occurs after namespace validation", () => {
  const error = new Error("synthetic-factory"); const f = fixture({ factoryError: error });
  assert.throws(() => f.filter(query([["namespace", "work"]], f.events)), e => e === error);
  assert.deepEqual(kinds(f.events), ["get", "get", "namespace", "get", "factory"]);
});
for (const selector of [null, "", "a=b", "synthetic-invalid(()"]) {
  infrastructureControl(`selector ${JSON.stringify(selector)} is forwarded once to inert factory`, () => {
    const f = fixture(); const entries                     = selector === null ? [] : [["labelSelector", selector]];
    f.filter(query(entries)); assert.deepEqual(f.events, [["factory", selector]]);
  });
}
infrastructureControl("duplicate query keys use the first value from actual URLSearchParams", () => {
  const f = fixture(); const p = f.filter(query([["type", "app"], ["type", "bad"], ["namespace", "work"], ["namespace", "else"], ["labelSelector", "first"], ["labelSelector", "second"]]));
  assert.equal(p(pod("work")), true); assert.equal(p(pod("else")), false);
  assert.deepEqual(f.events.slice(0, 2), [["namespace", "work"], ["factory", "first"]]);
});
infrastructureControl("irrelevant query keys are not read", () => {
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
  ]                                                 ) {
    infrastructureControl(`${type} filter: ${name}`, () => {
      const f = fixture(); const p = f.filter(query([["type", type]])); f.events.length = 0;
      assert.equal(p(pod(ns, labels)), type === expected);
      assert.equal(f.events.some(e => e[0] === "system"), setRead);
      assert.equal(f.events.some(e => e[0] === "labels"), type === expected);
    });
  }
}
for (const override of [undefined, null, false, 0, "", ["app"], { value: "system" }]) {
  infrastructureControl(`nonmatching override ${JSON.stringify(override)} uses inert namespace set`, () => {
    const f = fixture(); const p = f.filter(query([["type", "system"]])); f.events.length = 0;
    assert.equal(p(pod("kube-system", { "branconet.io/type": override })), true);
    assert.equal(f.events[0][0], "system");
  });
}
for (const [name, value] of [["absent metadata", {}], ["null metadata", { metadata: null }], ["missing namespace", { metadata: {} }], ["empty namespace", pod("")], ["null namespace", pod(null)], ["zero namespace", pod(0)]]                   ) {
  infrastructureControl(`${name} resolves to default and app through synthetic set`, () => {
    const f = fixture(); const p = f.filter(query([["type", "app"], ["namespace", "default"]])); f.events.length = 0;
    assert.equal(p(value), true); assert.deepEqual(f.events[0], ["system", "default"]);
  });
}
for (const labels of [undefined, null, false, 0, ""]) {
  infrastructureControl(`falsey labels ${JSON.stringify(labels)} supply a fresh empty map`, () => {
    const f = fixture(); const p = f.filter(query()); f.events.length = 0;
    assert.equal(p(pod("work", labels)), true);
    const passed = f.events.find(e => e[0] === "labels")?.[1];
    assert.equal(typeof passed, "object"); assert.equal(Object.keys(passed          ).length, 0);
  });
}
infrastructureControl("metadata label object is forwarded without copying", () => {
  const f = fixture(); const labels = { a: "b" }; const p = f.filter(query()); f.events.length = 0;
  assert.equal(p(pod("work", labels)), true); assert.equal(f.events.find(e => e[0] === "labels")?.[1], labels);
});
infrastructureControl("type mismatch shortcircuits namespace and labels conjunction", () => {
  const f = fixture({ labelError: new Error("must stay inert") }); const p = f.filter(query([["type", "system"], ["namespace", "work"]])); f.events.length = 0;
  assert.equal(p(pod("work")), false); assert.deepEqual(f.events, [["system", "work"]]);
});
infrastructureControl("namespace mismatch shortcircuits label predicate", () => {
  const f = fixture({ labelError: new Error("must stay inert") }); const p = f.filter(query([["namespace", "wanted"]])); f.events.length = 0;
  assert.equal(p(pod("other")), false); assert.deepEqual(f.events, [["system", "other"]]);
});
infrastructureControl("matching type and namespace evaluate labels last and preserve false", () => {
  const f = fixture({ labelResult: false }); const labels = {}; const p = f.filter(query([["type", "app"], ["namespace", "work"]])); f.events.length = 0;
  assert.equal(p(pod("work", labels)), false); assert.deepEqual(f.events, [["system", "work"], ["labels", labels]]);
});
infrastructureControl("late label dependency error propagates only after both filters match", () => {
  const error = new Error("synthetic-label"); const f = fixture({ labelError: error }); const p = f.filter(query());
  assert.throws(() => p(pod()), e => e === error);
});
infrastructureControl("set dependency fault propagates even under all type", () => {
  const error = new Error("synthetic-set"); const f = fixture({ setError: error }); const p = f.filter(query());
  assert.throws(() => p(pod()), e => e === error);
});
infrastructureControl("recognized override bypasses failing synthetic namespace set", () => {
  const f = fixture({ setError: new Error("must stay inert") }); const p = f.filter(query());
  assert.equal(p(pod("work", { "branconet.io/type": "app" })), true);
  assert.equal(f.events.some(e => e[0] === "system"), false);
});
infrastructureControl("query configuration is captured before later URLSearchParams mutations", () => {
  const f = fixture(); const q = query([["type", "app"], ["namespace", "work"], ["labelSelector", "initial"]]); const p = f.filter(q);
  q.set("type", "system"); q.set("namespace", "else"); q.set("labelSelector", "changed");
  assert.equal(p(pod("work")), true); assert.equal(p(pod("else")), false);
  assert.deepEqual(f.events.filter(e => e[0] === "factory"), [["factory", "initial"]]);
});
infrastructureControl("metadata type and namespace are fresh on every predicate call", () => {
  const f = fixture(); const p = f.filter(query([["type", "app"], ["namespace", "work"]]));
  const value = { metadata: { namespace: "work", labels: { "branconet.io/type": "app" } } };
  assert.equal(p(value), true); value.metadata.labels["branconet.io/type"] = "system"; assert.equal(p(value), false);
  value.metadata.labels["branconet.io/type"] = "app"; value.metadata.namespace = "else"; assert.equal(p(value), false);
});
infrastructureControl("metadata access order is namespace then labels, with two metadata reads", () => {
  const f = fixture(); const labels = {}; const metadata = { get namespace() { f.events.push(["ns-get"]); return "work"; }, get labels() { f.events.push(["labels-get"]); return labels; } };
  const value = { get metadata() { f.events.push(["metadata-get"]); return metadata; } };
  const p = f.filter(query()); f.events.length = 0; assert.equal(p(value), true);
  assert.deepEqual(kinds(f.events), ["metadata-get", "ns-get", "metadata-get", "labels-get", "system", "labels"]);
});
infrastructureControl("override getter is read once and before set membership", () => {
  const f = fixture(); const labels = { get "branconet.io/type"() { f.events.push(["override-get"]); return "other"; } };
  const p = f.filter(query()); f.events.length = 0; assert.equal(p(pod("work", labels)), true);
  assert.deepEqual(kinds(f.events), ["override-get", "system", "labels"]);
});
infrastructureControl("inherited recognized override is characterized as ordinary property access", () => {
  const f = fixture(); const labels = Object.create({ "branconet.io/type": "system" }); const p = f.filter(query([["type", "system"]]));
  assert.equal(p(pod("work", labels)), true); assert.equal(f.events.some(e => e[0] === "system"), false);
});
infrastructureControl("metadata getter exception is preserved before classification", () => {
  const error = new Error("synthetic-metadata"); const f = fixture(); const p = f.filter(query()); f.events.length = 0;
  assert.throws(() => p({ get metadata()        { throw error; } }), e => e === error); assert.deepEqual(f.events, []);
});
infrastructureControl("override getter exception is preserved before set or labels", () => {
  const error = new Error("synthetic-override"); const f = fixture(); const p = f.filter(query()); f.events.length = 0;
  assert.throws(() => p(pod("work", { get "branconet.io/type"()        { throw error; } })), e => e === error); assert.deepEqual(f.events, []);
});
infrastructureControl("synthetic query read fault preserves first-read ordering", () => {
  const error = new Error("synthetic-query"); const f = fixture(); const q = query();
  q.get = (key        ) => { f.events.push(["get", key]); if (key === "namespace") throw error; return "all"; };
  assert.throws(() => f.filter(q), e => e === error); assert.deepEqual(f.events, [["get", "type"], ["get", "namespace"]]);
});
infrastructureControl("empty namespace is retained rather than converted to no filter", () => {
  const f = fixture(); const p = f.filter(query([["namespace", ""]])); f.events.length = 0;
  assert.equal(p(pod("")), false); assert.equal(p(pod("default")), false); assert.equal(f.events.some(e => e[0] === "labels"), false);
});
infrastructureControl("separate filter constructions retain distinct selector predicate results", () => {
  const yes = fixture(); const no = fixture({ labelResult: false });
  const a = yes.filter(query([["labelSelector", "one"]])); const b = no.filter(query([["labelSelector", "two"]]));
  assert.equal(a(pod()), true); assert.equal(b(pod()), false);
});

// END EXACT ORIGINAL NATIVE TYPE-ERASED PROJECTION
infrastructureAssert.equal(infrastructureCount,76);
console.log('BORTUS_COMPAT_ORDER '+JSON.stringify({name:'pod-filter',registered:infrastructureCount,exactOrder:true}));
