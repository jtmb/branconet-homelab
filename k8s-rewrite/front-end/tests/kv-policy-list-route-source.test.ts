import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC policy-list GET SOURCE controls; all actual imports inert.
// Only this synchronous callback executes. No HTTP/auth/schema/registry/native/SQL.
type Model = Record<string, any>;
const path = "src/app/api/kv/policies/route.ts";
const compiled = ts.transpileModule(readFileSync(path, "utf8"), {
  fileName: path, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
}).outputText;
const isError = (e: unknown) => Object.prototype.toString.call(e) === "[object Error]";
function opaque(label: string) {
  return new Proxy({}, { get() { throw Error(`PUBLIC unexpected ${label} access`); }, ownKeys() { throw Error(`PUBLIC unexpected ${label} enumeration`); } });
}
function deferred() {
  let resolve!: (value: any) => void;
  const promise = new Promise<any>(yes => { resolve = yes; });
  return { promise, resolve };
}
function fixture() {
  const trace: string[] = [], wrappers: any[][] = [], cursors: Model[] = [], calls: Model[] = [];
  const actor = opaque("actor"), request = opaque("request"), cursor = opaque("cursor");
  const result = opaque("result"), getMarker = opaque("GET marker"), postMarker = opaque("POST marker"), fault = Error("PUBLIC-FAULT");
  const state: Model = { cursor, result, faults: {}, hooks: {} };
  function step(name: string) { trace.push(name); if (state.hooks[name]) state.hooks[name](); if (state.faults[name]) throw state.faults[name]; }
  const method = function(this: unknown, ...args: unknown[]) { calls.push({ receiver: this, args }); step("call"); return state.result; };
  const registry = Object.defineProperty({}, "listPolicies", { get() { step("method"); return state.method; } });
  const cursorFn = function(this: unknown, ...args: unknown[]) { cursors.push({ receiver: this, args }); step("cursor"); return state.cursor; };
  state.method = method; state.cursorFn = cursorFn;
  const http = { kvHuman(...args: any[]) { wrappers.push(args); return wrappers.length === 1 ? getMarker : postMarker; }, get metadataCursor() { step("cursor-get"); return state.cursorFn; } };
  const imports = new Proxy(http, { get(t, key, receiver) { assert.ok(key === "kvHuman" || key === "metadataCursor"); return Reflect.get(t, key, receiver); } });
  const schema = opaque("schema import"), m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, require: (name: string) => {
    if (name === "@/lib/kv-http") return imports;
    assert.equal(name, "@/lib/kv-schemas"); return schema;
  } }, { filename: path, timeout: 5000 });
  assert.equal(wrappers.length, 2); assert.deepEqual(trace, [] as string[]);
  const callback = wrappers[0][0];
  return { state, trace, wrappers, cursors, calls, registry, actor, request, cursor, result, getMarker, postMarker, fault, method, cursorFn, callback, exports: m.exports,
    invoke: (...args: unknown[]) => callback(args.length ? args[0] : registry, args.length > 1 ? args[1] : actor, args.length > 2 ? args[2] : request) as unknown };
}
type Fixture = ReturnType<typeof fixture>;
const order = ["method", "cursor-get", "cursor", "call"];
function exact(f: Fixture, ...values: unknown[]) {
  const [registry, actor, request, cursor] = values.length ? values : [f.registry, f.actor, f.request, f.cursor];
  const c = f.cursors.at(-1)!, m = f.calls.at(-1)!;
  assert.equal(c.receiver, undefined); assert.equal(c.args.length, 1); assert.equal(c.args[0], request);
  assert.equal(m.receiver, registry); assert.equal(m.args.length, 2); assert.equal(m.args[0], actor); assert.equal(m.args[1], cursor);
}

test("human policy-list GET exact synchronous SOURCE delegation", async t => {
  await t.test("nodejs force-dynamic exact GET and inert POST201 wrappers", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["GET", "POST", "dynamic", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    assert.equal(f.wrappers[0].length, 1); assert.equal(typeof f.callback, "function"); assert.equal(f.exports.GET, f.getMarker);
    assert.equal(f.wrappers[1].length, 2); assert.equal(typeof f.wrappers[1][0], "function"); assert.equal(f.wrappers[1][1], 201); assert.equal(f.exports.POST, f.postMarker); assert.deepEqual(f.trace, [] as string[]);
  });
  await t.test("method captured before cursor lookup and exact receiver arguments", () => { const f = fixture(); assert.equal(f.invoke(), f.result); assert.deepEqual(f.trace, order); exact(f); assert.equal(f.cursors.length, 1); assert.equal(f.calls.length, 1); });
  for (const [i, stage] of order.entries()) await t.test(`${stage} synchronous refusal stops every later stage`, () => {
    const f = fixture(); f.state.faults[stage] = f.fault; assert.throws(() => f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, i + 1)); assert.equal(f.calls.length, stage === "call" ? 1 : 0);
  });
  for (const value of [undefined, null]) {
    await t.test(`nullish registry ${String(value)} refuses before cursor lookup`, () => { const f = fixture(); assert.throws(() => f.invoke(value), isError); assert.deepEqual(f.trace, [] as string[]); assert.equal(f.cursors.length, 0); });
    await t.test(`nullish request ${String(value)} passed unread to cursor`, () => { const f = fixture(); assert.equal(f.invoke(f.registry, f.actor, value), f.result); exact(f, f.registry, f.actor, value, f.cursor); assert.deepEqual(f.trace, order); });
  }
  await t.test("missing registry refuses before any cursor lookup", () => { const f = fixture(); assert.throws(() => f.callback(), isError); assert.deepEqual(f.trace, [] as string[]); });
  await t.test("missing actor and request are delegated as undefined", () => { const f = fixture(); assert.equal(f.callback(f.registry), f.result); exact(f, f.registry, undefined, undefined, f.cursor); });
  await t.test("inherited method retains original registry receiver", () => { const f = fixture(), r = Object.create(f.registry); assert.equal(f.invoke(r), f.result); exact(f, r, f.actor, f.request, f.cursor); assert.deepEqual(f.trace, order); });
  await t.test("method getter receives original inherited receiver", () => { const f = fixture(); const proto = Object.defineProperty({}, "listPolicies", { get() { assert.equal(this, r); f.trace.push("method"); return f.method; } }); const r = Object.create(proto); assert.equal(f.invoke(r), f.result); exact(f, r, f.actor, f.request, f.cursor); });
  await t.test("registry proxy only reads listPolicies without enumeration", () => { const f = fixture(); const r = new Proxy({}, { get(_t, k) { assert.equal(k, "listPolicies"); f.trace.push("method"); return f.method; }, ownKeys() { throw f.fault; }, getOwnPropertyDescriptor() { throw f.fault; } }); assert.equal(f.invoke(r), f.result); exact(f, r, f.actor, f.request, f.cursor); assert.deepEqual(f.trace, order); });
  for (const value of [undefined, null, false, 0, "", 7, "PUBLIC", Symbol("PUBLIC"), 3n]) {
    await t.test(`actor ${String(value)} passed unchanged`, () => { const f = fixture(); assert.equal(f.invoke(f.registry, value), f.result); exact(f, f.registry, value, f.request, f.cursor); });
    await t.test(`request ${String(value)} passed unchanged and unread`, () => { const f = fixture(); assert.equal(f.invoke(f.registry, f.actor, value), f.result); exact(f, f.registry, f.actor, value, f.cursor); });
    await t.test(`cursor ${String(value)} passed unchanged`, () => { const f = fixture(); f.state.cursor = value; assert.equal(f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, value); });
    await t.test(`result ${String(value)} returned raw without adoption`, () => { const f = fixture(); f.state.result = value; assert.equal(f.invoke(), value); exact(f); });
  }
  for (const value of [undefined, null, false, 0, "", {}, Symbol("PUBLIC")]) {
    await t.test(`noncallable method ${String(value)} still evaluates cursor first`, () => { const f = fixture(); f.state.method = value; assert.throws(() => f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 3)); assert.equal(f.cursors.length, 1); assert.equal(f.calls.length, 0); });
    await t.test(`noncallable cursor ${String(value)} refuses after method capture`, () => { const f = fixture(); f.state.cursorFn = value; assert.throws(() => f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 2)); assert.equal(f.cursors.length, 0); assert.equal(f.calls.length, 0); });
  }
  await t.test("missing method still evaluates cursor before refusal", () => { const f = fixture(); assert.throws(() => f.invoke(Object.create(null)), isError); assert.deepEqual(f.trace, ["cursor-get", "cursor"]); assert.equal(f.calls.length, 0); });
  for (const value of [false, 0, "PUBLIC", Symbol("PUBLIC"), 3n]) await t.test(`primitive registry ${String(value)} evaluates cursor before missing method refusal`, () => { const f = fixture(); assert.throws(() => f.invoke(value), isError); assert.deepEqual(f.trace, ["cursor-get", "cursor"]); assert.equal(f.calls.length, 0); });
  await t.test("method getter refusal wins over invalid cursor", () => { const f = fixture(); f.state.cursorFn = null; f.state.faults.method = f.fault; assert.throws(() => f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, ["method"]); });
  for (const stage of ["cursor-get", "cursor"]) await t.test(`${stage} refusal wins over noncallable captured method`, () => { const f = fixture(); f.state.method = null; f.state.faults[stage] = f.fault; assert.throws(() => f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, order.indexOf(stage) + 1)); });
  for (const stage of ["cursor-get", "cursor", "call"]) await t.test(`${stage} mutation cannot replace captured method`, () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.method = null; }; assert.equal(f.invoke(), f.result); exact(f); assert.deepEqual(f.trace, order); });
  await t.test("method getter may replace cursor before cursor lookup", () => { const f = fixture(); f.state.hooks.method = () => { f.state.cursorFn = function(this: unknown, ...args: unknown[]) { f.cursors.push({ receiver: this, args }); f.trace.push("cursor"); return f.cursor; }; }; assert.equal(f.invoke(), f.result); exact(f); assert.deepEqual(f.trace, order); });
  await t.test("cursor function captured before cursor-call hook replaces binding", () => { const f = fixture(); f.state.hooks.cursor = () => { f.state.cursorFn = null; }; assert.equal(f.invoke(), f.result); exact(f); });
  await t.test("cursor result captured before method call mutates current cursor", () => { const f = fixture(); f.state.hooks.call = () => { f.state.cursor = opaque("replacement cursor"); }; assert.equal(f.invoke(), f.result); exact(f); });
  await t.test("extra arguments and callback this remain unread", () => { const f = fixture(); assert.equal(f.callback.call(opaque("callback this"), f.registry, f.actor, f.request, opaque("extra")), f.result); exact(f); });
  await t.test("result throwing then getter remains unread at synchronous boundary", () => { const f = fixture(); const v = Object.defineProperty({}, "then", { get() { throw f.fault; } }); f.state.result = v; assert.equal(f.invoke(), v); exact(f); });
  await t.test("result thenable is neither read nor invoked", () => { const f = fixture(); const v = { then() { throw f.fault; } }; f.state.result = v; assert.equal(f.invoke(), v); exact(f); });
  await t.test("cursor then getter remains unread before exact method delegation", () => { const f = fixture(); const v = Object.defineProperty({}, "then", { get() { throw f.fault; } }); f.state.cursor = v; assert.equal(f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, v); });
  await t.test("pending cursor promise passed raw without waiting", async () => { const f = fixture(), d = deferred(), target = { public: "CURSOR" }; f.state.cursor = d.promise; assert.equal(f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, d.promise); assert.deepEqual(f.trace, order); d.resolve(target); assert.equal(await d.promise, target); });
  await t.test("pending result promise returned with exact raw identity", async () => { const f = fixture(), d = deferred(), target = { public: "RESULT" }; f.state.result = d.promise; assert.equal(f.invoke(), d.promise); exact(f); assert.deepEqual(f.trace, order); d.resolve(target); assert.equal(await d.promise, target); });
  await t.test("promised registry is not awaited before method lookup", () => { const f = fixture(); assert.throws(() => f.invoke(Promise.resolve(f.registry)), isError); assert.deepEqual(f.trace, ["cursor-get", "cursor"]); });
  await t.test("two fresh calls refresh method cursor actor request registry and result", () => {
    const f = fixture(); assert.equal(f.invoke(), f.result); const r = { listPolicies: f.method }, a = opaque("fresh actor"), q = opaque("fresh request"), c = opaque("fresh cursor"), v = opaque("fresh result");
    f.state.cursor = c; f.state.result = v; assert.equal(f.invoke(r, a, q), v); exact(f, r, a, q, c); assert.equal(f.calls.length, 2); assert.equal(f.cursors.length, 2);
  });
  for (const stage of order) await t.test(`refused ${stage} does not poison a fresh call`, () => { const f = fixture(); f.state.faults[stage] = f.fault; assert.throws(() => f.invoke(), e => e === f.fault); delete f.state.faults[stage]; assert.equal(f.invoke(), f.result); exact(f); });
  await t.test("reentrant cursor call preserves both captured methods and receivers", () => {
    const f = fixture(), r = { listPolicies: f.method }, a = opaque("inner actor"), q = opaque("inner request"), c = opaque("inner cursor");
    let inner: unknown;
    f.state.cursorFn = function(this: unknown, ...args: unknown[]) { f.cursors.push({ receiver: this, args }); if (args[0] === f.request) { inner = f.callback(r, a, q); return f.cursor; } assert.equal(args[0], q); return c; };
    assert.equal(f.invoke(), f.result); assert.equal(inner, f.result); assert.equal(f.calls.length, 2);
    assert.equal(f.calls[0].receiver, r); assert.deepEqual(f.calls[0].args, [a, c]); assert.equal(f.calls[1].receiver, f.registry); assert.deepEqual(f.calls[1].args, [f.actor, f.cursor]);
  });
  await t.test("interleaved pending results retain original raw promises and captures", async () => {
    const f = fixture(), first = deferred(), second = deferred(); f.state.result = first.promise; const a = f.invoke(); exact(f);
    const r = { listPolicies: f.method }, actor = opaque("second actor"), request = opaque("second request"), cursor = opaque("second cursor"), result = { public: "SECOND" };
    f.state.cursor = cursor; f.state.result = second.promise; const b = f.invoke(r, actor, request); exact(f, r, actor, request, cursor);
    assert.equal(a, first.promise); assert.equal(b, second.promise); second.resolve(result); assert.equal(await b, result); const original = { public: "FIRST" }; first.resolve(original); assert.equal(await a, original);
    assert.equal(f.calls[0].receiver, f.registry); assert.deepEqual(f.calls[0].args, [f.actor, f.cursor]); assert.equal(f.calls.length, 2);
  });
});
