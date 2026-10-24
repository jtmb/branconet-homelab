import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

const path = "src/app/api/kv/legacy/grants/route.ts";
const compiled = ts.transpileModule(readFileSync(path, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
type Model = Record<string, any>;
const isError = (e: unknown) => Object.prototype.toString.call(e) === "[object Error]";
function opaque(label: string) { return new Proxy(Object.create(null), { get() { throw Error("unread " + label); }, ownKeys() { throw Error("unenumerated " + label); }, getOwnPropertyDescriptor() { throw Error("undescribed " + label); } }); }
function deferred() { let resolve!: (v: unknown) => void; const promise = new Promise<unknown>(r => { resolve = r; }); return { promise, resolve }; }
function fixture() {
  const trace: string[] = [], wrappers: any[][] = [], constructions: Model[] = [], calls: Model[] = [], cursors: Model[] = [];
  const registry = opaque("registry"), actor = opaque("actor"), request = opaque("request"), cursor = opaque("cursor"), result = opaque("result");
  const getMarker = opaque("GET marker"), postMarker = opaque("POST marker"), fault = Error("PUBLIC-FAULT");
  const state: Model = { cursor, result, faults: {}, hooks: {}, explicitReturn: true };
  function step(name: string) { trace.push(name); if (state.hooks[name]) state.hooks[name](); if (state.faults[name]) throw state.faults[name]; }
  const method = function(this: unknown, ...args: unknown[]) { calls.push({ receiver: this, args }); step("call"); return state.result; };
  const proto = Object.defineProperty({}, "grants", { get() { step("method"); return state.method; } });
  const instance = Object.create(proto);
  const ctor = function(this: unknown, ...args: unknown[]) { constructions.push({ receiver: this, args, target: new.target }); step("construct"); return state.explicitReturn ? state.instance : undefined; };
  ctor.prototype = proto;
  const cursorFn = function(this: unknown, ...args: unknown[]) { cursors.push({ receiver: this, args }); step("cursor"); return state.cursor; };
  Object.assign(state, { method, ctor, instance, cursorFn });
  const http = { kvHuman(...args: any[]) { wrappers.push(args); return wrappers.length === 1 ? getMarker : postMarker; }, get metadataCursor() { step("cursor-get"); return state.cursorFn; } };
  const imports = new Proxy(http, { get(t, k, receiver) { assert.ok(k === "kvHuman" || k === "metadataCursor"); return Reflect.get(t, k, receiver); } });
  const legacy: Model = { get KvLegacyAccess() { step("constructor-get"); return state.ctor; } };
  const schemas = opaque("schema import"), m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, require: (name: string) => {
    if (name === "@/lib/kv-http") return imports;
    if (name === "@/lib/kv-legacy-access") return legacy;
    assert.equal(name, "@/lib/kv-schemas"); return schemas;
  } }, { filename: path, timeout: 5000 });
  assert.equal(wrappers.length, 2); assert.deepEqual(trace, [] as string[]);
  const callback = wrappers[0][0];
  return { state, trace, wrappers, constructions, calls, cursors, registry, actor, request, cursor, result, getMarker, postMarker, fault, method, ctor, instance, proto, legacy, cursorFn, callback, exports: m.exports,
    invoke: (...args: unknown[]) => callback(args.length ? args[0] : registry, args.length > 1 ? args[1] : actor, args.length > 2 ? args[2] : request) as unknown };
}
type Fixture = ReturnType<typeof fixture>;
const order = ["constructor-get", "construct", "method", "cursor-get", "cursor", "call"];
function exact(f: Fixture, registry: unknown = f.registry, actor: unknown = f.actor, request: unknown = f.request, cursor: unknown = f.cursor, receiver: unknown = f.instance) {
  const n = f.constructions.at(-1)!, c = f.cursors.at(-1)!, m = f.calls.at(-1)!;
  assert.equal(n.args.length, 1); assert.equal(n.args[0], registry); assert.equal(n.target, f.ctor);
  assert.equal(c.receiver, undefined); assert.equal(c.args.length, 1); assert.equal(c.args[0], request);
  assert.equal(m.receiver, receiver); assert.equal(m.args.length, 2); assert.equal(m.args[0], actor); assert.equal(m.args[1], cursor);
}

test("human legacy-grant-list GET exact synchronous SOURCE delegation", async t => {
  await t.test("nodejs force-dynamic GET and inert POST201 exact wrappers", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["GET", "POST", "dynamic", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    assert.equal(f.wrappers[0].length, 1); assert.equal(typeof f.callback, "function"); assert.equal(f.exports.GET, f.getMarker);
    assert.equal(f.wrappers[1].length, 2); assert.equal(typeof f.wrappers[1][0], "function"); assert.equal(f.wrappers[1][1], 201); assert.equal(f.exports.POST, f.postMarker);
    assert.deepEqual(f.trace, [] as string[]);
  });
  await t.test("construct then capture grants before cursor with exact receiver and arguments", () => { const f = fixture(); assert.equal(f.invoke(), f.result); exact(f); assert.deepEqual(f.trace, order); assert.equal(f.constructions.length, 1); assert.equal(f.calls.length, 1); assert.equal(f.cursors.length, 1); });
  for (const [i, stage] of order.entries()) await t.test(`${stage} synchronous refusal stops later stages`, () => {
    const f = fixture(); f.state.faults[stage] = f.fault; assert.throws(() => f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, i + 1)); assert.equal(f.calls.length, stage === "call" ? 1 : 0);
  });
  const values = [undefined, null, false, 0, "", 7, "PUBLIC", Symbol("PUBLIC"), 3n];
  for (const [i, value] of values.entries()) {
    await t.test(`registry public scalar ${i} delegated unread to constructor`, () => { const f = fixture(); assert.equal(f.invoke(value), f.result); assert.equal(f.constructions[0].args[0], value); assert.deepEqual(f.trace, order); });
    await t.test(`actor public scalar ${i} delegated unread`, () => { const f = fixture(); assert.equal(f.invoke(f.registry, value), f.result); assert.equal(f.calls[0].args[0], value); assert.deepEqual(f.trace, order); });
    await t.test(`request public scalar ${i} delegated unread to cursor`, () => { const f = fixture(); assert.equal(f.invoke(f.registry, f.actor, value), f.result); assert.equal(f.cursors[0].args[0], value); assert.deepEqual(f.trace, order); });
    await t.test(`cursor public scalar ${i} delegated unchanged`, () => { const f = fixture(); f.state.cursor = value; assert.equal(f.invoke(), f.result); assert.equal(f.calls[0].args[1], value); });
    await t.test(`result public scalar ${i} returned raw`, () => { const f = fixture(); f.state.result = value; assert.equal(f.invoke(), value); exact(f); });
    await t.test(`constructor primitive return ${i} retains newly allocated receiver`, () => { const f = fixture(); f.state.instance = value; assert.equal(f.invoke(), f.result); const n = f.constructions[0]; assert.equal(Object.getPrototypeOf(n.receiver), f.proto); exact(f, f.registry, f.actor, f.request, f.cursor, n.receiver); assert.deepEqual(f.trace, order); });
  }
  await t.test("missing arguments pass exactly undefined without lookup", () => { const f = fixture(); assert.equal(f.callback(), f.result); assert.equal(f.constructions[0].args[0], undefined); assert.equal(f.cursors[0].args[0], undefined); assert.equal(f.calls[0].args[0], undefined); assert.equal(f.calls[0].args[1], f.cursor); });
  await t.test("callback this and extra argument remain unread", () => { const f = fixture(); assert.equal(f.callback.call(opaque("this"), f.registry, f.actor, f.request, opaque("extra")), f.result); exact(f); });
  for (const [i, value] of [undefined, null, false, 0, "", {}, Symbol("PUBLIC"), () => fakes()].entries()) {
    await t.test(`nonconstructor binding ${i} refuses before method or cursor`, () => { const f = fixture(); f.state.ctor = value; assert.throws(() => f.invoke(), isError); assert.deepEqual(f.trace, ["constructor-get"]); assert.equal(f.constructions.length, 0); });
  }
  function fakes() { throw Error("arrow constructor body must remain inert"); }
  for (const [i, value] of [undefined, null, false, 0, "", {}, Symbol("PUBLIC")].entries()) {
    await t.test(`noncallable grants ${i} evaluates cursor before refusing`, () => { const f = fixture(); f.state.method = value; assert.throws(() => f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 5)); assert.equal(f.cursors.length, 1); assert.equal(f.calls.length, 0); });
    await t.test(`noncallable cursor ${i} refuses after grants capture`, () => { const f = fixture(); f.state.cursorFn = value; assert.throws(() => f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 4)); assert.equal(f.cursors.length, 0); assert.equal(f.calls.length, 0); });
  }
  await t.test("constructor object return replaces allocated receiver", () => { const f = fixture(); const x = { grants: f.method }; f.state.instance = x; assert.equal(f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.cursor, x); assert.deepEqual(f.trace, ["constructor-get", "construct", "cursor-get", "cursor", "call"]); });
  await t.test("constructor function return is exact grants receiver", () => { const f = fixture(); const x = Object.assign(function() { throw f.fault; }, { grants: f.method }); f.state.instance = x; assert.equal(f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.cursor, x); });
  await t.test("constructor ignored return uses new receiver", () => { const f = fixture(); f.state.explicitReturn = false; assert.equal(f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.cursor, f.constructions[0].receiver); });
  await t.test("inherited constructor getter receives original module receiver", () => { const f = fixture(); delete f.legacy.KvLegacyAccess; Object.setPrototypeOf(f.legacy, Object.defineProperty({}, "KvLegacyAccess", { get() { assert.equal(this, f.legacy); f.trace.push("constructor-get"); return f.ctor; } })); assert.equal(f.invoke(), f.result); exact(f); assert.deepEqual(f.trace, order); });
  await t.test("constructor can replace instance before grants lookup", () => { const f = fixture(), x = { grants: f.method }; f.state.hooks.construct = () => { f.state.instance = x; }; assert.equal(f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.cursor, x); });
  await t.test("inherited grants getter receives exact constructed return object", () => { const f = fixture(); const x = Object.create(Object.defineProperty({}, "grants", { get() { assert.equal(this, x); f.trace.push("method"); return f.method; } })); f.state.instance = x; assert.equal(f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.cursor, x); assert.deepEqual(f.trace, order); });
  await t.test("returned proxy only reads grants without enumeration", () => { const f = fixture(); const x = new Proxy({}, { get(_t, key) { assert.equal(key, "grants"); f.trace.push("method"); return f.method; }, ownKeys() { throw f.fault; }, getOwnPropertyDescriptor() { throw f.fault; } }); f.state.instance = x; assert.equal(f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.cursor, x); assert.deepEqual(f.trace, order); });
  await t.test("returned object missing grants evaluates cursor before refusal", () => { const f = fixture(); f.state.instance = Object.create(null); assert.throws(() => f.invoke(), isError); assert.deepEqual(f.trace, ["constructor-get", "construct", "cursor-get", "cursor"]); });
  for (const stage of ["constructor-get", "construct", "method"]) await t.test(`${stage} refusal wins over invalid cursor`, () => { const f = fixture(); f.state.cursorFn = null; f.state.faults[stage] = f.fault; assert.throws(() => f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, order.indexOf(stage) + 1)); });
  for (const stage of ["cursor-get", "cursor"]) await t.test(`${stage} refusal wins over noncallable captured grants`, () => { const f = fixture(); f.state.method = null; f.state.faults[stage] = f.fault; assert.throws(() => f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, order.indexOf(stage) + 1)); });
  for (const stage of ["cursor-get", "cursor", "call"]) await t.test(`${stage} mutation cannot replace captured grants or receiver`, () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.method = null; f.state.instance = null; }; assert.equal(f.invoke(), f.result); exact(f); assert.deepEqual(f.trace, order); });
  await t.test("constructor mutation cannot replace captured constructor", () => { const f = fixture(); f.state.hooks.construct = () => { f.state.ctor = null; }; assert.equal(f.invoke(), f.result); exact(f); });
  await t.test("grants getter can replace later cursor binding", () => { const f = fixture(); const replacement = function(this: unknown, ...args: unknown[]) { f.cursors.push({ receiver: this, args }); f.trace.push("cursor"); return f.cursor; }; f.state.hooks.method = () => { f.state.cursorFn = replacement; }; assert.equal(f.invoke(), f.result); exact(f); assert.deepEqual(f.trace, order); });
  await t.test("cursor function remains captured while its body replaces binding", () => { const f = fixture(); f.state.hooks.cursor = () => { f.state.cursorFn = null; }; assert.equal(f.invoke(), f.result); exact(f); });
  await t.test("cursor result remains captured during grants call mutation", () => { const f = fixture(); f.state.hooks.call = () => { f.state.cursor = opaque("replacement cursor"); }; assert.equal(f.invoke(), f.result); exact(f); });
  await t.test("raw result throwing then getter is unread", () => { const f = fixture(); const x = Object.defineProperty({}, "then", { get() { throw f.fault; } }); f.state.result = x; assert.equal(f.invoke(), x); exact(f); });
  await t.test("raw result then method is not called", () => { const f = fixture(); const x = { then() { throw f.fault; } }; f.state.result = x; assert.equal(f.invoke(), x); exact(f); });
  await t.test("raw cursor throwing then getter remains unread", () => { const f = fixture(); const x = Object.defineProperty({}, "then", { get() { throw f.fault; } }); f.state.cursor = x; assert.equal(f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, x); });
  await t.test("promised constructor return is not adopted", () => { const f = fixture(); f.state.instance = Promise.resolve({ grants: f.method }); assert.throws(() => f.invoke(), isError); assert.deepEqual(f.trace, ["constructor-get", "construct", "cursor-get", "cursor"]); });
  await t.test("promise constructor return with own grants is exact receiver", () => { const f = fixture(); const x = Object.assign(Promise.resolve(null), { grants: f.method }); f.state.instance = x; assert.equal(f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.cursor, x); });
  await t.test("pending cursor promise passed raw without waiting", async () => { const f = fixture(), d = deferred(), x = { public: "CURSOR" }; f.state.cursor = d.promise; assert.equal(f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, d.promise); d.resolve(x); assert.equal(await d.promise, x); });
  await t.test("pending result promise returned as exact original promise", async () => { const f = fixture(), d = deferred(), x = { public: "RESULT" }; f.state.result = d.promise; assert.equal(f.invoke(), d.promise); exact(f); d.resolve(x); assert.equal(await d.promise, x); });
  for (const stage of order) await t.test(`refused ${stage} does not poison fresh call`, () => { const f = fixture(); f.state.faults[stage] = f.fault; assert.throws(() => f.invoke(), e => e === f.fault); delete f.state.faults[stage]; assert.equal(f.invoke(), f.result); exact(f); });
  await t.test("fresh calls construct independently and refresh all captures", () => { const f = fixture(); assert.equal(f.invoke(), f.result); const r = opaque("fresh registry"), a = opaque("fresh actor"), q = opaque("fresh request"), c = opaque("fresh cursor"), x = Object.create(f.proto), v = opaque("fresh result"); f.state.instance = x; f.state.cursor = c; f.state.result = v; assert.equal(f.invoke(r, a, q), v); exact(f, r, a, q, c, x); assert.notEqual(f.constructions[0].receiver, f.constructions[1].receiver); assert.equal(f.calls.length, 2); });
  await t.test("reentrant cursor preserves outer constructed receiver and method", () => {
    const f = fixture(), x = Object.create(f.proto), r = opaque("inner registry"), a = opaque("inner actor"), q = opaque("inner request"), c = opaque("inner cursor"); let inner: unknown;
    f.state.cursorFn = function(this: unknown, ...args: unknown[]) { f.cursors.push({ receiver: this, args }); if (args[0] === f.request) { f.state.instance = x; inner = f.callback(r, a, q); return f.cursor; } assert.equal(args[0], q); return c; };
    assert.equal(f.invoke(), f.result); assert.equal(inner, f.result); assert.equal(f.calls.length, 2); assert.equal(f.calls[0].receiver, x); assert.deepEqual(f.calls[0].args, [a, c]); assert.equal(f.calls[1].receiver, f.instance); assert.deepEqual(f.calls[1].args, [f.actor, f.cursor]); assert.equal(f.constructions[0].args[0], f.registry); assert.equal(f.constructions[1].args[0], r);
  });
  await t.test("interleaved results retain raw promises and original constructed receivers", async () => {
    const f = fixture(), first = deferred(), second = deferred(); f.state.result = first.promise; const a = f.invoke(); exact(f);
    const x = Object.create(f.proto), r = opaque("second registry"), actor = opaque("second actor"), request = opaque("second request"), cursor = opaque("second cursor"), result = { public: "SECOND" };
    f.state.instance = x; f.state.cursor = cursor; f.state.result = second.promise; const b = f.invoke(r, actor, request); exact(f, r, actor, request, cursor, x);
    assert.equal(a, first.promise); assert.equal(b, second.promise); second.resolve(result); assert.equal(await b, result); const original = { public: "FIRST" }; first.resolve(original); assert.equal(await a, original); assert.equal(f.calls[0].receiver, f.instance); assert.deepEqual(f.calls[0].args, [f.actor, f.cursor]);
  });
});
