import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC SOURCE controls. Every imported implementation is inert.
// Only GET's callback executes; no HTTP/auth/body/schema/native/DB/value access.
type Model = Record<string, any>;
const route = "src/app/api/kv/paths/[id]/data/route.ts";
const compiled = ts.transpileModule(readFileSync(route, "utf8"), { fileName: route,
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
function deferred() {
  let resolve!: (value: any) => void, reject!: (error: unknown) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const turns = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
function untouched(label: string) {
  return new Proxy({}, { get() { throw new Error(`PUBLIC unexpected ${label} read`); },
    ownKeys() { throw new Error(`PUBLIC unexpected ${label} enumeration`); } });
}
function fixture() {
  const calls: string[] = [], wrappers: any[][] = [], wrapped: unknown[] = [], reads: Model[] = [], engines: unknown[] = [];
  const registry = untouched("registry"), actor = untouched("actor"), request = untouched("request");
  const error = new Error("PUBLIC-FAULT"), result = Object.freeze({ public: "RESULT" });
  const state: Model = { id: "PUBLIC-PATH", idError: null, engineError: null, readError: null,
    methodError: null, methodReject: false, result, engine: null, method: null };
  function method(this: unknown, ...args: unknown[]) {
    calls.push("read"); reads.push({ receiver: this, args });
    if (state.methodError) {
      if (state.methodReject) return Promise.reject(state.methodError);
      throw state.methodError;
    }
    return state.result;
  }
  const engine = { get read() { calls.push("read-get"); if (state.readError) throw state.readError; return state.method; } };
  state.engine = engine; state.method = method;
  const http = {
    kvHuman(...args: any[]) { wrappers.push(args); const result = Object.freeze({ public: `WRAPPER-${wrappers.length}` }); wrapped.push(result); return result; },
    kvEngine(r: unknown) { calls.push("engine"); engines.push(r); if (state.engineError) throw state.engineError; return state.engine; },
    kvBody() { throw new Error("PUBLIC body implementation must remain inert"); },
  };
  const m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, require: (name: string) => {
    if (name === "@/lib/kv-http") return http;
    if (name === "@/lib/kv-schemas") return untouched("schema");
    assert.equal(name, "@/lib/kv-contract");
    return { KvError: class { constructor() { throw new Error("PUBLIC inactive error constructor"); } } };
  } }, { filename: route, timeout: 5000 });
  assert.equal(wrappers.length, 4); assert.equal(calls.length, 0);
  const params = new Proxy({}, { get(_target, key) {
    assert.equal(key, "id"); calls.push("id"); if (state.idError) throw state.idError; return state.id;
  }, ownKeys() { throw new Error("PUBLIC unexpected parameter enumeration"); } });
  return { calls, wrappers, wrapped, reads, engines, registry, actor, request, engine, method, state, params, result, error, exports: m.exports,
    invoke: (...args: unknown[]) => wrappers[0][0](args.length > 3 ? args[3] : registry, args.length > 2 ? args[2] : actor,
      args.length > 1 ? args[1] : request, args.length ? args[0] : params) as Promise<unknown> };
}
function exact(f: ReturnType<typeof fixture>, ...expected: unknown[]) {
  const expectedActor = expected.length ? expected[0] : f.actor, expectedId = expected.length > 1 ? expected[1] : "PUBLIC-PATH";
  const receiver = expected.length > 2 ? expected[2] : f.engine;
  const seen = f.reads.at(-1)!; assert.equal(seen.receiver, receiver); assert.equal(seen.args.length, 2);
  assert.equal(seen.args[0], expectedActor); assert.equal(seen.args[1], expectedId);
}
test("human current-value GET exact SOURCE delegation", async t => {
  await t.test("exports nodejs, force-dynamic and all four exact inert wrapper results", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["DELETE", "GET", "POST", "PUT", "dynamic", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    for (const [index, name] of ["GET", "POST", "PUT", "DELETE"].entries()) {
      assert.equal(f.wrappers[index].length, name === "POST" ? 2 : 1);
      if (name === "POST") assert.equal(f.wrappers[index][1], 201);
      assert.equal(f.exports[name].public, `WRAPPER-${index + 1}`);
      assert.equal(f.exports[name], f.wrapped[index]);
      assert.equal(typeof f.wrappers[index][0], "function");
    }
    assert.notEqual(f.exports.GET, f.wrappers[0][0]);
  });
  await t.test("destructures id before engine/read lookup and exact actor/id invocation", async () => {
    const f = fixture(); assert.equal(await f.invoke(), f.result); exact(f);
    assert.deepEqual(f.calls, ["id", "engine", "read-get", "read"]);
    assert.equal(f.engines.length, 1); assert.equal(f.engines[0], f.registry);
  });
  for (const field of ["idError", "engineError", "readError", "methodError"]) await t.test(`exact ${field} refusal stops later stages`, async () => {
    const f = fixture(); f.state[field] = f.error;
    await assert.rejects(f.invoke(), e => e === f.error);
    const count: Model = { idError: 1, engineError: 2, readError: 3, methodError: 4 };
    assert.deepEqual(f.calls, ["id", "engine", "read-get", "read"].slice(0, count[field]));
    assert.equal(f.reads.length, field === "methodError" ? 1 : 0);
  });
  await t.test("method rejection keeps exact error and does not retry", async () => {
    const f = fixture(); f.state.methodError = f.error; f.state.methodReject = true;
    await assert.rejects(f.invoke(), e => e === f.error); assert.equal(f.reads.length, 1); exact(f);
  });
  for (const value of [undefined, null]) await t.test(`nullish params ${String(value)} refuse before engine`, async () => {
    const f = fixture(); await assert.rejects(f.invoke(value), e => e instanceof Error || Object.prototype.toString.call(e) === "[object Error]");
    assert.equal(f.calls.length, 0); assert.equal(f.reads.length, 0);
  });
  await t.test("missing id is forwarded without route validation or unrelated reads", async () => {
    const f = fixture(); await f.invoke({}); exact(f, f.actor, undefined);
    assert.deepEqual(f.calls, ["engine", "read-get", "read"]);
  });
  await t.test("inherited id is read once without enumeration", async () => {
    const f = fixture(), id = Object.freeze({ public: "ID" }); let count = 0;
    const p = Object.create({ get id() { count++; return id; } });
    Object.defineProperty(p, "other", { get() { throw f.error; } });
    await f.invoke(p); exact(f, f.actor, id); assert.equal(count, 1);
  });
  for (const value of [null, undefined, false, 0, "", Symbol("PUBLIC-ID")]) await t.test(`id identity ${String(value)} is forwarded unchanged`, async () => {
    const f = fixture(); f.state.id = value; await f.invoke(); exact(f, f.actor, value);
  });
  for (const value of [null, undefined]) await t.test(`nullish engine ${String(value)} refuses before method`, async () => {
    const f = fixture(); f.state.engine = value;
    await assert.rejects(f.invoke(), e => Object.prototype.toString.call(e) === "[object Error]");
    assert.deepEqual(f.calls, ["id", "engine"]); assert.equal(f.reads.length, 0);
  });
  for (const value of [null, undefined, 7, {}]) await t.test(`noncallable read ${String(value)} refuses after lookup`, async () => {
    const f = fixture(); f.state.method = value;
    await assert.rejects(f.invoke(), e => Object.prototype.toString.call(e) === "[object Error]");
    assert.deepEqual(f.calls, ["id", "engine", "read-get"]); assert.equal(f.reads.length, 0);
  });
  await t.test("inherited read receives the original engine receiver", async () => {
    const f = fixture(), engine = Object.create({ read: f.method }); f.state.engine = engine;
    await f.invoke(); exact(f, f.actor, "PUBLIC-PATH", engine);
    assert.deepEqual(f.calls, ["id", "engine", "read"]);
  });
  await t.test("request, registry, actor and unused params are never inspected", async () => {
    const f = fixture(); await f.invoke(); exact(f); assert.equal(f.engines[0], f.registry);
    assert.equal(f.reads.length, 1);
  });
  for (const value of [undefined, null, false, 0, "", NaN, Symbol("PUBLIC-RESULT")]) await t.test(`adopts raw result ${String(value)}`, async () => {
    const f = fixture(); f.state.result = value; assert.equal(await f.invoke(), value); assert.equal(f.reads.length, 1);
  });
  await t.test("frozen nested result resolves by identity without inspection", async () => {
    const f = fixture(), value = untouched("result");
    // Promise resolution must inspect then; allow precisely that protocol read.
    const nested = Object.freeze({ public: value }); f.state.result = nested;
    assert.equal(await f.invoke(), nested); assert.equal(nested.public, value);
  });
  await t.test("held result cannot fulfill early and resolves to the exact model", async () => {
    const f = fixture(), held = deferred(); f.state.result = held.promise; let settled = false;
    const pending = f.invoke().finally(() => { settled = true; }); await turns(); assert.equal(settled, false);
    exact(f); held.resolve(f.result); assert.equal(await pending, f.result); assert.equal(settled, true);
  });
  await t.test("held rejection preserves exact refusal without retry", async () => {
    const f = fixture(), held = deferred(); f.state.result = held.promise;
    const refused = assert.rejects(f.invoke(), e => e === f.error); await turns(); held.reject(f.error); await refused;
    assert.equal(f.reads.length, 1);
  });
  await t.test("thenable engine is used immediately without awaiting its then", async () => {
    const f = fixture(), engine = { read: f.method, get then() { throw f.error; } };
    f.state.engine = engine; await f.invoke(); exact(f, f.actor, "PUBLIC-PATH", engine);
  });
  await t.test("read thenable result is adopted with exact resolved identity", async () => {
    const f = fixture(); let count = 0;
    f.state.result = { then(resolve: (value: unknown) => void) { count++; resolve(f.result); } };
    assert.equal(await f.invoke(), f.result); assert.equal(count, 1);
  });
  await t.test("then getter refusal is adopted as exact rejection", async () => {
    const f = fixture(); f.state.result = { get then() { throw f.error; } };
    await assert.rejects(f.invoke(), e => e === f.error); assert.equal(f.reads.length, 1);
  });
  await t.test("fresh calls retrieve engine and method again after a refusal", async () => {
    const f = fixture(); f.state.readError = f.error; await assert.rejects(f.invoke(), e => e === f.error);
    f.state.readError = null; const engine = { read: f.method }; f.state.engine = engine; f.state.id = "PUBLIC-FRESH";
    await f.invoke(); exact(f, f.actor, "PUBLIC-FRESH", engine); assert.equal(f.engines.length, 2);
  });
  await t.test("id and actor are captured before a held result settles", async () => {
    const f = fixture(), held = deferred(), actor = untouched("other actor"); f.state.result = held.promise;
    const pending = f.invoke(f.params, f.request, actor); await turns(); f.state.id = "PUBLIC-AFTER";
    held.resolve(f.result); await pending; exact(f, actor, "PUBLIC-PATH");
  });
  await t.test("interleaved invocations retain separate engine receivers and arguments", async () => {
    const f = fixture(), first = deferred(), second = deferred(), firstEngine = { read: f.method }, secondEngine = { read: f.method };
    const a = untouched("first actor"), b = untouched("second actor"), x = { public: "FIRST" }, y = { public: "SECOND" };
    f.state.engine = firstEngine; f.state.result = first.promise; const p = f.invoke({ id: "FIRST" }, f.request, a);
    f.state.engine = secondEngine; f.state.result = second.promise; const q = f.invoke({ id: "SECOND" }, f.request, b);
    assert.equal(f.reads.length, 2); assert.equal(f.reads[0].receiver, firstEngine); assert.equal(f.reads[1].receiver, secondEngine);
    assert.equal(f.reads[0].args[0], a); assert.equal(f.reads[0].args[1], "FIRST"); exact(f, b, "SECOND", secondEngine);
    second.resolve(y); assert.equal(await q, y); first.resolve(x); assert.equal(await p, x);
  });
  await t.test("id getter can change engine before delegation and lookup", async () => {
    const f = fixture(), engine = { read: f.method };
    await f.invoke({ get id() { f.state.engine = engine; return "PUBLIC-GETTER"; } });
    exact(f, f.actor, "PUBLIC-GETTER", engine);
  });
  await t.test("read getter can replace later method without changing captured call", async () => {
    const f = fixture(); let count = 0;
    f.state.engine = { get read() { count++; f.state.method = () => { throw f.error; }; return f.method; } };
    await f.invoke(); exact(f, f.actor, "PUBLIC-PATH", f.state.engine); assert.equal(count, 1);
  });
  await t.test("alternate registry is passed exactly without any property reads", async () => {
    const f = fixture(), registry = untouched("alternate registry"); await f.invoke(f.params, f.request, f.actor, registry);
    assert.equal(f.engines[0], registry); exact(f);
  });
});
