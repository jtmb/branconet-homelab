import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC GET SOURCE controls. Actual imports never execute.
// No HTTP, authentication, registry, native, SQL, values or recovery operations.
type Model = Record<string, any>;
const path = "src/app/api/kv/operations/[id]/route.ts";
const compiled = ts.transpileModule(readFileSync(path, "utf8"), {
  fileName: path, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
}).outputText;
const isError = (e: unknown) => Object.prototype.toString.call(e) === "[object Error]";
function opaque(label: string) {
  return new Proxy({}, { get() { throw Error(`PUBLIC unexpected ${label} access`); }, ownKeys() { throw Error(`PUBLIC unexpected ${label} enumeration`); } });
}
function deferred() {
  let resolve!: (value: any) => void, reject!: (error: unknown) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const turns = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
function fixture() {
  const trace: string[] = [], wrappers: any[][] = [], engines: Model[] = [], calls: Model[] = [];
  const registry = opaque("registry"), actor = opaque("actor"), request = opaque("request"), id = opaque("id");
  const result = Object.freeze({ public: "RESOLVED" }), marker = Object.freeze({ public: "WRAPPED" }), fault = Error("PUBLIC-FAULT");
  const state: Model = { id, result, faults: {}, hooks: {} };
  function step(name: string) { trace.push(name); if (state.hooks[name]) state.hooks[name](); if (state.faults[name]) throw state.faults[name]; }
  const method = function(this: unknown, ...args: unknown[]) { calls.push({ receiver: this, args }); step("call"); if (state.rejectCall) return Promise.reject(fault); return state.result; };
  const engine = Object.defineProperty({}, "resolve", { get() { step("method"); return state.method; } });
  const params = Object.defineProperty({}, "id", { get() { step("id"); return state.id; } });
  const engineFn = function(this: unknown, ...args: unknown[]) { engines.push({ receiver: this, args }); step("engine"); return state.engine; };
  state.engine = engine; state.method = method; state.engineFn = engineFn;
  const http = { kvHuman(...args: any[]) { wrappers.push(args); return marker; }, get kvEngine() { step("engine-get"); return state.engineFn; } };
  const imports = new Proxy(http, { get(t, key, receiver) { assert.ok(key === "kvHuman" || key === "kvEngine"); return Reflect.get(t, key, receiver); } });
  const m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, require: (name: string) => { assert.equal(name, "@/lib/kv-http"); return imports; } }, { filename: path, timeout: 5000 });
  assert.equal(wrappers.length, 1); assert.deepEqual(trace, [] as string[]);
  const callback = wrappers[0][0];
  return { state, trace, wrappers, engines, calls, registry, actor, request, id, result, marker, fault, engine, params, method, engineFn, callback, exports: m.exports,
    invoke: (...args: unknown[]) => callback(args.length ? args[0] : registry, args.length > 1 ? args[1] : actor, args.length > 2 ? args[2] : request, args.length > 3 ? args[3] : params) as Promise<unknown> };
}
type Fixture = ReturnType<typeof fixture>;
const order = ["id", "engine-get", "engine", "method", "call"];
function exact(f: Fixture, ...values: unknown[]) {
  const [registry, actor, id, engine] = values.length ? values : [f.registry, f.actor, f.id, f.engine];
  const e = f.engines.at(-1)!, c = f.calls.at(-1)!;
  assert.equal(e.receiver, undefined); assert.equal(e.args.length, 1); assert.equal(e.args[0], registry);
  assert.equal(c.receiver, engine); assert.equal(c.args.length, 2); assert.equal(c.args[0], actor); assert.equal(c.args[1], id);
}

test("human operation-resolution GET exact SOURCE delegation", async t => {
  await t.test("nodejs force-dynamic exact default-status GET wrapper with inert imports", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["GET", "dynamic", "runtime"]); assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    assert.equal(f.wrappers[0].length, 1); assert.equal(typeof f.callback, "function"); assert.equal(f.exports.GET, f.marker); assert.deepEqual(f.trace, [] as string[]);
  });
  await t.test("id captured at entry before engine lookup and exact resolve receiver arguments", async () => {
    const f = fixture(); assert.equal(await f.invoke(), f.result); assert.deepEqual(f.trace, order); exact(f); assert.equal(f.engines.length, 1); assert.equal(f.calls.length, 1);
  });
  for (const [i, stage] of order.entries()) await t.test(`${stage} refusal stops every later stage`, async () => {
    const f = fixture(); f.state.faults[stage] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, i + 1)); assert.equal(f.calls.length, stage === "call" ? 1 : 0);
  });
  for (const value of [undefined, null]) {
    await t.test(`nullish fourth argument ${String(value)} refuses before any engine access`, async () => { const f = fixture(); await assert.rejects(f.invoke(f.registry, f.actor, f.request, value), isError); assert.deepEqual(f.trace, [] as string[]); });
    await t.test(`nullish request ${String(value)} remains unread`, async () => { const f = fixture(); await f.invoke(f.registry, f.actor, value); exact(f); assert.deepEqual(f.trace, order); });
    await t.test(`nullish engine ${String(value)} refuses at resolve lookup`, async () => { const f = fixture(); f.state.engine = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 3)); });
  }
  await t.test("missing fourth argument refuses before engine lookup", async () => { const f = fixture(); await assert.rejects(f.callback(f.registry, f.actor, f.request), isError); assert.deepEqual(f.trace, [] as string[]); });
  await t.test("inherited id getter read exactly once at entry", async () => { const f = fixture(); const p = Object.create(f.params); await f.invoke(f.registry, f.actor, f.request, p); exact(f); assert.deepEqual(f.trace, order); });
  await t.test("inherited resolve retains returned engine receiver", async () => { const f = fixture(); const e = Object.create(f.engine); f.state.engine = e; await f.invoke(); exact(f, f.registry, f.actor, f.id, e); assert.deepEqual(f.trace, order); });
  await t.test("missing id delegates undefined without route schema validation", async () => { const f = fixture(); await f.invoke(f.registry, f.actor, f.request, Object.create(null)); exact(f, f.registry, f.actor, undefined, f.engine); assert.deepEqual(f.trace, order.slice(1)); });
  await t.test("proxy fourth argument reads only id without enumeration", async () => { const f = fixture(); const p = new Proxy({}, { get(_t, key) { assert.equal(key, "id"); f.trace.push("id"); return f.id; }, ownKeys() { throw f.fault; }, getOwnPropertyDescriptor() { throw f.fault; } }); await f.invoke(f.registry, f.actor, f.request, p); exact(f); assert.deepEqual(f.trace, order); });
  await t.test("id getter receiver is original fourth argument", async () => { const f = fixture(); const proto = Object.defineProperty({}, "id", { get() { assert.equal(this, p); f.trace.push("id"); return f.id; } }); const p = Object.create(proto); await f.invoke(f.registry, f.actor, f.request, p); exact(f); });
  await t.test("resolve getter receiver is original engine", async () => { const f = fixture(); const e = Object.create(Object.defineProperty({}, "resolve", { get() { assert.equal(this, e); f.trace.push("method"); return f.method; } })); f.state.engine = e; await f.invoke(); exact(f, f.registry, f.actor, f.id, e); });
  for (const value of [undefined, null, false, 0, "", 7, "PUBLIC", Symbol("PUBLIC")]) {
    await t.test(`id ${String(value)} captured without inspection`, async () => { const f = fixture(); f.state.id = value; await f.invoke(); exact(f, f.registry, f.actor, value, f.engine); assert.deepEqual(f.trace, order); });
    await t.test(`registry ${String(value)} passed unchanged to engine`, async () => { const f = fixture(); await f.invoke(value); exact(f, value, f.actor, f.id, f.engine); });
    await t.test(`actor ${String(value)} passed unchanged to resolve`, async () => { const f = fixture(); await f.invoke(f.registry, value); exact(f, f.registry, value, f.id, f.engine); });
    await t.test(`result ${String(value)} adopted unchanged`, async () => { const f = fixture(); f.state.result = value; assert.equal(await f.invoke(), value); exact(f); });
  }
  for (const value of [false, 0, "PUBLIC", Symbol("PUBLIC"), 3n]) await t.test(`primitive fourth argument ${String(value)} has missing id`, async () => { const f = fixture(); await f.invoke(f.registry, f.actor, f.request, value); exact(f, f.registry, f.actor, undefined, f.engine); assert.deepEqual(f.trace, order.slice(1)); });
  for (const value of [undefined, null, false, 0, "", {}, Symbol("PUBLIC")]) {
    await t.test(`noncallable engine factory ${String(value)} refuses after id capture`, async () => { const f = fixture(); f.state.engineFn = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 2)); assert.equal(f.calls.length, 0); });
    await t.test(`noncallable resolve ${String(value)} refuses after method lookup`, async () => { const f = fixture(); f.state.method = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 4)); assert.equal(f.calls.length, 0); });
  }
  await t.test("missing resolve refuses without reading request or id again", async () => { const f = fixture(); f.state.engine = Object.create(null); await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 3)); });
  await t.test("promised engine is not awaited before resolve lookup", async () => { const f = fixture(); f.state.engine = Promise.resolve(f.engine); await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 3)); });
  await t.test("engine then getter is never read", async () => { const f = fixture(); Object.defineProperty(f.engine, "then", { get() { throw f.fault; } }); await f.invoke(); exact(f); });
  await t.test("id refusal wins over noncallable factory", async () => { const f = fixture(); f.state.engineFn = null; f.state.faults.id = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, ["id"]); });
  await t.test("resolve getter refusal wins over invalid method", async () => { const f = fixture(); f.state.method = null; f.state.faults.method = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 4)); });
  for (const stage of ["engine-get", "engine", "method", "call"]) await t.test(`${stage} cannot change already captured id`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.id = opaque("replacement id"); }; await f.invoke(); exact(f); assert.deepEqual(f.trace, order); });
  await t.test("factory captured before factory hook replaces current binding", async () => { const f = fixture(); f.state.hooks.engine = () => { f.state.engineFn = null; }; await f.invoke(); exact(f); });
  await t.test("resolve captured before call hook replaces current method", async () => { const f = fixture(); f.state.hooks.call = () => { f.state.method = null; }; await f.invoke(); exact(f); });
  await t.test("engine captures resolve only after factory returns", async () => { const f = fixture(); const replacement = function(this: unknown, ...args: unknown[]) { f.calls.push({ receiver: this, args }); f.trace.push("call"); return f.result; }; f.state.hooks.engine = () => { f.state.method = replacement; }; assert.equal(await f.invoke(), f.result); exact(f); assert.deepEqual(f.trace, order); });
  await t.test("extra callback arguments and this receiver remain unread", async () => { const f = fixture(); assert.equal(await f.callback.call(opaque("callback this"), f.registry, f.actor, f.request, f.params, opaque("extra")), f.result); exact(f); });
  await t.test("synchronous factory and method complete before async result adoption", async () => { const f = fixture(); const d = deferred(); f.state.result = d.promise; const p = f.invoke(); assert.deepEqual(f.trace, order); exact(f); let settled = false; void p.then(() => { settled = true; }); await turns(); assert.equal(settled, false); d.resolve(f.result); assert.equal(await p, f.result); });
  await t.test("rejected method promise preserves exact reason", async () => { const f = fixture(); f.state.rejectCall = true; await assert.rejects(f.invoke(), e => e === f.fault); exact(f); });
  await t.test("held rejection preserves exact reason without retry", async () => { const f = fixture(); const d = deferred(); f.state.result = d.promise; const p = f.invoke(); const rejected = assert.rejects(p, e => e === f.fault); await turns(); d.reject(f.fault); await rejected; assert.equal(f.calls.length, 1); exact(f); });
  await t.test("throwing result then getter preserves exact reason", async () => { const f = fixture(); f.state.result = Object.defineProperty({}, "then", { get() { throw f.fault; } }); await assert.rejects(f.invoke(), e => e === f.fault); exact(f); });
  await t.test("resolved object identity is adopted without enumerating contents", async () => { const f = fixture(); const target = Object.freeze({ public: "IDENTITY" }); const result = new Proxy(target, { get(t, k, r) { assert.equal(k, "then"); return Reflect.get(t, k, r); }, ownKeys() { throw f.fault; } }); f.state.result = result; assert.equal(await f.invoke(), result); exact(f); });
  await t.test("thenable adopts resolved identity and retains original then receiver", async () => { const f = fixture(); const target = { public: "THENABLE" }; const v = { then(resolve: (x: unknown) => void) { assert.equal(this, v); resolve(target); } }; f.state.result = v; assert.equal(await f.invoke(), target); exact(f); });
  await t.test("two fresh calls do not reuse id engine method actor registry or result", async () => {
    const f = fixture(); await f.invoke(); const id = opaque("fresh id"), actor = opaque("fresh actor"), registry = opaque("fresh registry"), result = Object.freeze({ public: "FRESH" });
    const engine = { resolve: f.method }; f.state.id = id; f.state.engine = engine; f.state.result = result; assert.equal(await f.invoke(registry, actor), result); exact(f, registry, actor, id, engine); assert.equal(f.engines.length, 2); assert.equal(f.calls.length, 2);
  });
  await t.test("failed call does not poison next fresh resolution", async () => { const f = fixture(); f.state.faults.id = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); delete f.state.faults.id; assert.equal(await f.invoke(), f.result); exact(f); assert.equal(f.engines.length, 1); });
  await t.test("interleaved results retain each captured actor id and receiver", async () => {
    const f = fixture(), first = deferred(), second = deferred(); f.state.result = first.promise; const a = f.invoke(); exact(f);
    const id = opaque("second id"), actor = opaque("second actor"), registry = opaque("second registry"), engine = { resolve: f.method }, result = Object.freeze({ public: "SECOND" });
    f.state.id = id; f.state.engine = engine; f.state.result = second.promise; const b = f.invoke(registry, actor); exact(f, registry, actor, id, engine);
    second.resolve(result); assert.equal(await b, result); first.resolve(f.result); assert.equal(await a, f.result); assert.equal(f.calls[0].receiver, f.engine); assert.equal(f.calls[0].args[0], f.actor); assert.equal(f.calls[0].args[1], f.id); assert.equal(f.calls.length, 2);
  });
});
