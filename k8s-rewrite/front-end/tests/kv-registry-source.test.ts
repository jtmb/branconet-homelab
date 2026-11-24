import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";

// PUBLIC SOURCE only: select one factory declaration; real imports/services never run.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);
const source = readFileSync(new URL("../src/lib/kv-http.ts", import.meta.url), "utf8");
const ast = ts.createSourceFile("kv-http.ts", source, ts.ScriptTarget.Latest, true);
const selected = ast.statements.filter((s: { name?: { getText(): string } }) => ts.isFunctionDeclaration(s) && s.name?.getText() === "kvRegistry");
assert.equal(selected.length, 1);
const declaration = selected[0];
const js = ts.transpileModule(declaration.getText().replace(/^export /, ""), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
type Call = (this: unknown, ...args: unknown[]) => unknown;
type Scope = { invoke: () => unknown; replace: (name: string, value: unknown) => void };
const names = ["KvRegistry", "prisma", "secretNamespaces", "kvConfig"];
function select(bindings: Record<string, unknown>): Scope {
  const setters = names.map(n => `case ${JSON.stringify(n)}: ${n} = value; break;`).join("\n");
  return new Function(...names, '"use strict";\n' + js + "\nreturn {invoke:kvRegistry,replace(name,value){switch(name){" + setters + "default:throw Error('unknown binding')}}};")(...names.map(n => bindings[n])) as Scope;
}
function opaque(label: string): object {
  return new Proxy(Object.create(null), { get(_t, key) { throw Error(label + " read " + String(key)); }, ownKeys() { throw Error(label + " ownKeys"); }, getPrototypeOf() { throw Error(label + " prototype"); } });
}
const stages = ["namespaces", "config", "construct"];
const examples = [undefined, null, false, true, 0, -0, -1, NaN, "", "public", 1n, Symbol("public"), {}, [], opaque("public")];
type Options = { prisma?: unknown; namespaces?: unknown; config?: unknown; result?: object; at?: (stage: string) => void };
function rig(o: Options = {}) {
  const events: string[] = [];
  const hit = (s: string) => { events.push(s); o.at?.(s); };
  const values = Object.fromEntries(["prisma", "namespaces", "config"].map(k => [k, Object.hasOwn(o, k) ? o[k as keyof Options] : opaque(k)]));
  const result = o.result ?? opaque("result");
  const constructor: Call = new Proxy(function PublicRegistry() {}, { construct(_target, args, newTarget): object {
    hit("construct"); assert.equal(newTarget, constructor); assert.equal(args.length, 3);
    assert.equal(args[0], values.prisma); assert.equal(args[1], values.namespaces); assert.equal(args[2], values.config); return result;
  }, apply() { throw Error("called rather than constructed"); } });
  const scope = select({ KvRegistry: constructor, prisma: values.prisma,
    secretNamespaces: function (this: unknown, ...args: unknown[]) { assert.equal(this, undefined); assert.equal(args.length, 0); hit("namespaces"); return values.namespaces; },
    kvConfig: function (this: unknown, ...args: unknown[]) { assert.equal(this, undefined); assert.equal(args.length, 0); hit("config"); return values.config; },
  });
  return { scope, events, values, result, constructor, invoke: () => scope.invoke() };
}
function catches(fn: () => unknown, failure: unknown) {
  let caught = false;
  try { fn(); } catch (error) { caught = true; assert.equal(error, failure); }
  assert.equal(caught, true);
}
test("kvRegistry finite PUBLIC SOURCE factory controls", async t => {
  await t.test("exact exported synchronous zero-parameter factory; inert selection", () => {
    assert.deepEqual(declaration.modifiers.map((m: { kind: number }) => m.kind), [ts.SyntaxKind.ExportKeyword]);
    assert.equal(declaration.parameters.length, 0); assert.equal(declaration.body.statements.length, 1);
    assert.equal(declaration.body.statements[0].getText(), "return new KvRegistry(prisma, secretNamespaces(), kvConfig());");
    select(Object.fromEntries(names.map(n => [n, () => { throw Error("selection executed " + n); }])));
  });
  await t.test("exact order, zero-argument unbound delegates, three constructor args and newTarget", () => {
    const r = rig(); assert.equal(r.invoke(), r.result); assert.deepEqual(r.events, stages);
  });
  for (const field of ["prisma", "namespaces", "config"] as const) for (const [i, value] of examples.entries()) {
    await t.test(field + " original uncoerced identity " + i, () => {
      const r = rig({ [field]: value }); assert.equal(r.invoke(), r.result); assert.deepEqual(r.events, stages);
    });
  }
  for (const stage of stages) for (const [i, failure] of examples.entries()) {
    await t.test(stage + " exact exception and refusal prefix " + i, () => {
      const r = rig({ at(s) { if (s === stage) throw failure; } }); catches(r.invoke, failure);
      assert.deepEqual(r.events, stages.slice(0, stages.indexOf(stage) + 1));
    });
  }
  for (const kind of ["namespaces", "config"] as const) for (const [i, value] of [undefined, null, 0, {}, "public"].entries()) {
    await t.test(kind + " noncallable stops at exact stage " + i, () => {
      const r = rig(); r.scope.replace(kind === "namespaces" ? "secretNamespaces" : "kvConfig", value);
      assert.throws(r.invoke, TypeError); assert.deepEqual(r.events, kind === "namespaces" ? [] : ["namespaces"]);
    });
  }
  for (const [i, ctor] of [undefined, null, 0, {}, () => ({}), async () => ({})].entries()) {
    await t.test("nonconstructor is checked after argument evaluation " + i, () => {
      const r = rig(); r.scope.replace("KvRegistry", ctor); assert.throws(r.invoke, TypeError); assert.deepEqual(r.events, ["namespaces", "config"]);
    });
  }
  await t.test("argument refusal precedes even nonconstructor rejection", () => {
    const failure = opaque("refusal"); const r = rig({ at(s) { if (s === "config") throw failure; } });
    r.scope.replace("KvRegistry", undefined); catches(r.invoke, failure); assert.deepEqual(r.events, ["namespaces", "config"]);
  });
  for (const [i, primitive] of examples.filter(x => x === null || typeof x !== "object" && typeof x !== "function").entries()) {
    await t.test("ordinary constructor primitive return retains fresh instance " + i, () => {
      const events: string[] = []; const values = [opaque("prisma"), opaque("ns"), opaque("config")]; const receivers: unknown[] = [];
      function Constructor(this: unknown, ...args: unknown[]) { assert.equal(new.target, Constructor); assert.deepEqual(args, values); receivers.push(this); events.push("construct"); return primitive; }
      const s = select({ KvRegistry: Constructor, prisma: values[0], secretNamespaces() { events.push("namespaces"); return values[1]; }, kvConfig() { events.push("config"); return values[2]; } });
      const first = s.invoke(), second = s.invoke(); assert.equal(first, receivers[0]); assert.equal(second, receivers[1]); assert.notEqual(first, second);
      assert.equal(Object.getPrototypeOf(first), Constructor.prototype); assert.deepEqual(events, [...stages, ...stages]);
    });
  }
  for (const [i, result] of [{}, [], opaque("constructor result"), function publicResult() {}, Object.defineProperty({}, "then", { get() { throw Error("then read"); } })].entries()) {
    await t.test("ordinary constructor object result returned untouched " + i, () => {
      const r = rig(); const constructor = function () { return result; }; r.scope.replace("KvRegistry", constructor);
      assert.equal(r.invoke(), result); assert.deepEqual(r.events, ["namespaces", "config"]);
    });
  }
  for (const field of ["namespaces", "config"] as const) {
    await t.test(field + " thenable argument remains untouched", () => {
      const value = Object.defineProperty({}, "then", { get() { throw Error("then read"); } });
      const r = rig({ [field]: value }); assert.equal(r.invoke(), r.result); assert.deepEqual(r.events, stages);
    });
    await t.test(field + " promise argument remains same object", async () => {
      const value = Promise.resolve("public"); const r = rig({ [field]: value }); assert.equal(r.invoke(), r.result); assert.deepEqual(r.events, stages); await value;
    });
  }
  for (const kind of ["resolved", "rejected"] as const) {
    await t.test("constructor " + kind + " promise returned synchronously", async () => {
      const failure = {}; const result = kind === "resolved" ? Promise.resolve("public") : Promise.reject(failure);
      const handled = result.catch(e => { assert.equal(e, failure); });
      const r = rig({ result }); assert.equal(r.invoke(), result); assert.deepEqual(r.events, stages); await handled;
    });
  }
  for (const stage of ["namespaces", "config"] as const) {
    await t.test(stage + " cannot replace already captured constructor or prisma", () => {
      const r = rig({ at(s) { if (s === stage) { r.scope.replace("KvRegistry", () => { throw Error("replacement used"); }); r.scope.replace("prisma", opaque("replacement prisma")); } } });
      assert.equal(r.invoke(), r.result); assert.deepEqual(r.events, stages);
    });
  }
  await t.test("namespace callback selects current later config binding", () => {
    const events: string[] = []; const prisma = opaque("prisma"), ns = opaque("ns"), cfg = opaque("cfg"), result = opaque("result");
    const later: Call = function (...args) { assert.equal(this, undefined); assert.equal(args.length, 0); events.push("later config"); return cfg; };
    const constructor: Call = new Proxy(function Constructor() {}, { construct(_t, args, nt): object { assert.equal(nt, constructor); assert.equal(args.length, 3); assert.equal(args[0], prisma); assert.equal(args[1], ns); assert.equal(args[2], cfg); events.push("construct"); return result; } });
    const s = select({ KvRegistry: constructor, prisma, secretNamespaces() { events.push("namespaces"); s.replace("kvConfig", later); return ns; }, kvConfig() { throw Error("old config used"); } });
    assert.equal(s.invoke(), result); assert.deepEqual(events, ["namespaces", "later config", "construct"]);
  });
  await t.test("each call freshly captures all bindings", () => {
    const r = rig(); assert.equal(r.invoke(), r.result); const second = rig();
    r.scope.replace("KvRegistry", second.constructor); r.scope.replace("prisma", second.values.prisma);
    r.scope.replace("secretNamespaces", () => second.values.namespaces); r.scope.replace("kvConfig", () => second.values.config);
    assert.equal(r.invoke(), second.result); assert.deepEqual(r.events, stages); assert.deepEqual(second.events, ["construct"]);
  });
  await t.test("class construction preserves receiver and exact inputs", () => {
    const r = rig(); let receiver: unknown;
    class PublicRegistry { constructor(...args: unknown[]) { receiver = this; assert.equal(new.target, PublicRegistry); assert.equal(args.length, 3); assert.equal(args[0], r.values.prisma); assert.equal(args[1], r.values.namespaces); assert.equal(args[2], r.values.config); } }
    r.scope.replace("KvRegistry", PublicRegistry); const result = r.invoke(); assert.equal(result, receiver); assert.equal(Object.getPrototypeOf(result), PublicRegistry.prototype); assert.deepEqual(r.events, ["namespaces", "config"]);
  });
  await t.test("normal prototype read follows arguments and uses captured constructor", () => {
    const events: string[] = []; const proto = {}; let receiver: unknown;
    const target = function (this: unknown) { receiver = this; assert.equal(new.target, ctor); events.push("body"); };
    target.prototype = proto;
    const ctor = new Proxy(target, { get(_target, key, recv) { assert.equal(key, "prototype"); events.push("prototype"); assert.equal(recv, ctor); return proto; } });
    const s = select({ KvRegistry: ctor, prisma: opaque("prisma"), secretNamespaces() { events.push("namespaces"); return opaque("ns"); }, kvConfig() { events.push("config"); return opaque("cfg"); } });
    const result = s.invoke(); assert.equal(result, receiver); assert.equal(Object.getPrototypeOf(result), proto); assert.deepEqual(events, ["namespaces", "config", "prototype", "body"]);
  });
  for (const failure of [undefined, null, Symbol("failure"), opaque("failure")]) {
    await t.test("prototype read exception propagates without body " + typeof failure, () => {
      const events: string[] = []; const ctor = new Proxy(function () { throw Error("body executed"); }, { get(_target, key) { assert.equal(key, "prototype"); events.push("prototype"); throw failure; } });
      const s = select({ KvRegistry: ctor, prisma: {}, secretNamespaces() { events.push("namespaces"); return {}; }, kvConfig() { events.push("config"); return {}; } });
      catches(s.invoke, failure); assert.deepEqual(events, ["namespaces", "config", "prototype"]);
    });
  }
  for (const stage of stages) {
    await t.test(stage + " reentrant call completes before outer resumes", () => {
      let nesting = false; let inner: unknown;
      const r = rig({ at(s) { if (s === stage && !nesting) { nesting = true; inner = r.invoke(); nesting = false; } } });
      // One constructor delegate remains captured for both invocations; neither result is awaited.
      assert.equal(r.invoke(), r.result); assert.equal(inner, r.result);
      const at = stages.indexOf(stage); assert.deepEqual(r.events, [...stages.slice(0, at + 1), ...stages, ...stages.slice(at + 1)]);
    });
    await t.test(stage + " reentrant failure propagates with exact prefix", () => {
      let nesting = false; const failure = opaque("nested failure");
      const r = rig({ at(s) { if (nesting && s === "namespaces") throw failure; if (s === stage && !nesting) { nesting = true; r.invoke(); } } });
      catches(r.invoke, failure); assert.deepEqual(r.events, [...stages.slice(0, stages.indexOf(stage) + 1), "namespaces"]);
    });
  }
});
