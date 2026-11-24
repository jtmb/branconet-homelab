import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC SOURCE controls. Only POST/PUT callbacks execute.
// Imports are inert models: no actual body/schema/HTTP/auth/registry/native/DB.
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
function fixture(verb: "POST" | "PUT") {
  const calls: string[] = [], wrappers: any[][] = [], wrapped: unknown[] = [], writes: Model[] = [], engines: unknown[] = [], bodies: unknown[][] = [];
  const registry = untouched("registry"), actor = untouched("actor"), request = untouched("request"), schema = untouched("schema implementation");
  const result = Object.freeze({ public: "RESULT" }), body = Object.freeze({ public: "BODY" }), error = new Error("PUBLIC-FAULT");
  const state: Model = { id: "PUBLIC-PATH", engine: null, method: null, result, body,
    idError: null, engineError: null, methodGetError: null, bodyGetError: null, schemaError: null,
    bodyError: null, bodyReject: false, methodError: null, methodReject: false, bodyHook: null };
  function method(this: unknown, ...args: unknown[]) {
    calls.push("write"); writes.push({ receiver: this, args });
    if (state.methodError) { if (state.methodReject) return Promise.reject(state.methodError); throw state.methodError; }
    return state.result;
  }
  const methodName = verb === "POST" ? "create" : "change";
  const engine = Object.defineProperty({}, methodName, { get() {
    calls.push("method-get"); if (state.methodGetError) throw state.methodGetError; return state.method;
  } });
  state.engine = engine; state.method = method;
  const http = {
    kvHuman(...args: any[]) { wrappers.push(args); const value = Object.freeze({ public: `WRAPPER-${wrappers.length}` }); wrapped.push(value); return value; },
    kvEngine(...args: unknown[]) { calls.push("engine"); assert.equal(args.length, 1); engines.push(args[0]); if (state.engineError) throw state.engineError; return state.engine; },
    get kvBody() {
      calls.push("body-get"); if (state.bodyGetError) throw state.bodyGetError;
      return (...args: unknown[]) => {
        calls.push("body"); bodies.push(args); if (state.bodyHook) state.bodyHook();
        if (state.bodyError) { if (state.bodyReject) return Promise.reject(state.bodyError); throw state.bodyError; }
        return state.body;
      };
    },
  };
  const schemas = { get dataChange() { calls.push("schema"); if (state.schemaError) throw state.schemaError; return schema; },
    get nativeDelete() { throw new Error("PUBLIC DELETE schema must remain inert"); } };
  const m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, require: (name: string) => {
    if (name === "@/lib/kv-http") return http;
    if (name === "@/lib/kv-schemas") return schemas;
    assert.equal(name, "@/lib/kv-contract");
    return { KvError: class { constructor() { throw new Error("PUBLIC inactive constructor"); } } };
  } }, { filename: route, timeout: 5000 });
  assert.equal(wrappers.length, 4); assert.equal(calls.length, 0);
  const params = new Proxy({}, { get(_target, key) {
    assert.equal(key, "id"); calls.push("id"); if (state.idError) throw state.idError; return state.id;
  }, ownKeys() { throw new Error("PUBLIC unexpected parameter enumeration"); } });
  const callback = wrappers[verb === "POST" ? 1 : 2][0];
  return { calls, wrappers, wrapped, writes, engines, bodies, registry, actor, request, schema, engine, method, methodName,
    state, params, body, result, error, exports: m.exports,
    invoke: (...args: unknown[]) => callback(args.length > 3 ? args[3] : registry, args.length > 2 ? args[2] : actor,
      args.length > 1 ? args[1] : request, args.length ? args[0] : params) as Promise<unknown> };
}
function exact(f: ReturnType<typeof fixture>, ...expected: unknown[]) {
  const actor = expected.length ? expected[0] : f.actor, id = expected.length > 1 ? expected[1] : "PUBLIC-PATH";
  const body = expected.length > 2 ? expected[2] : f.body, receiver = expected.length > 3 ? expected[3] : f.engine;
  const seen = f.writes.at(-1)!; assert.equal(seen.receiver, receiver); assert.equal(seen.args.length, 3);
  assert.equal(seen.args[0], actor); assert.equal(seen.args[1], id); assert.equal(seen.args[2], body);
}
const ordered = ["id", "engine", "method-get", "body-get", "schema", "body", "write"];
const isError = (e: unknown) => Object.prototype.toString.call(e) === "[object Error]";

for (const verb of ["POST", "PUT"] as const) test(`human current-value ${verb} exact SOURCE delegation`, async t => {
  await t.test("exact exports and four inert wrappers; POST201 and peers default status", () => {
    const f = fixture(verb); assert.deepEqual(Object.keys(f.exports).sort(), ["DELETE", "GET", "POST", "PUT", "dynamic", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    for (const [i, name] of ["GET", "POST", "PUT", "DELETE"].entries()) {
      assert.equal(f.wrappers[i].length, name === "POST" ? 2 : 1);
      if (name === "POST") assert.equal(f.wrappers[i][1], 201);
      assert.equal(typeof f.wrappers[i][0], "function"); assert.equal(f.exports[name], f.wrapped[i]);
    }
    assert.equal(f.calls.length, 0);
  });
  await t.test("id, original registry, captured method, exact request/schema and resolved body ordering", async () => {
    const f = fixture(verb); assert.equal(await f.invoke(), f.result); exact(f);
    assert.deepEqual(f.calls, ordered); assert.equal(f.engines.length, 1); assert.equal(f.engines[0], f.registry);
    assert.equal(f.bodies.length, 1); assert.equal(f.bodies[0].length, 2);
    assert.equal(f.bodies[0][0], f.request); assert.equal(f.bodies[0][1], f.schema);
  });
  for (const [field, count] of [["idError",1],["engineError",2],["methodGetError",3],["bodyGetError",4],["schemaError",5],["bodyError",6],["methodError",7]] as const)
    await t.test(`exact ${field} refusal stops later stages`, async () => {
      const f = fixture(verb); f.state[field] = f.error; await assert.rejects(f.invoke(), e => e === f.error);
      assert.deepEqual(f.calls, ordered.slice(0, count)); assert.equal(f.writes.length, field === "methodError" ? 1 : 0);
    });
  for (const stage of ["body", "method"]) await t.test(`${stage} rejected promise preserves exact refusal`, async () => {
    const f = fixture(verb); f.state[stage + "Error"] = f.error; f.state[stage + "Reject"] = true;
    await assert.rejects(f.invoke(), e => e === f.error); assert.equal(f.writes.length, stage === "body" ? 0 : 1);
  });
  for (const value of [undefined, null]) await t.test(`nullish params ${String(value)} refuse before delegation`, async () => {
    const f = fixture(verb); await assert.rejects(f.invoke(value), isError); assert.equal(f.calls.length, 0);
  });
  await t.test("missing id forwards undefined without route validation", async () => {
    const f = fixture(verb); await f.invoke({}); exact(f, f.actor, undefined);
    assert.deepEqual(f.calls, ordered.slice(1));
  });
  await t.test("inherited id read once; unrelated params untouched", async () => {
    const f = fixture(verb), id = Object.freeze({ public: "ID" }); let count = 0;
    const params = Object.create({ get id() { count++; return id; } });
    Object.defineProperty(params, "unrelated", { get() { throw f.error; } });
    await f.invoke(params); exact(f, f.actor, id); assert.equal(count, 1);
  });
  for (const id of [null, false, 0, "", Symbol("PUBLIC-ID")]) await t.test(`id ${String(id)} identity forwarded`, async () => {
    const f = fixture(verb); f.state.id = id; await f.invoke(); exact(f, f.actor, id);
  });
  for (const value of [undefined, null]) await t.test(`nullish engine ${String(value)} refuses before body`, async () => {
    const f = fixture(verb); f.state.engine = value; await assert.rejects(f.invoke(), isError);
    assert.deepEqual(f.calls, ["id", "engine"]); assert.equal(f.bodies.length, 0);
  });
  for (const value of [undefined, null, 7, {}]) await t.test(`noncallable method ${String(value)} refuses only after body await`, async () => {
    const f = fixture(verb), held = deferred(); f.state.method = value; f.state.body = held.promise;
    const refusal = assert.rejects(f.invoke(), isError); await turns(); assert.deepEqual(f.calls, ordered.slice(0, 6));
    assert.equal(f.writes.length, 0); held.resolve(f.body); await refusal;
  });
  await t.test("body refusal takes precedence over noncallable captured method", async () => {
    const f = fixture(verb); f.state.method = null; f.state.bodyError = f.error;
    await assert.rejects(f.invoke(), e => e === f.error); assert.deepEqual(f.calls, ordered.slice(0, 6));
  });
  await t.test("inherited method gets original engine receiver", async () => {
    const f = fixture(verb), engine = Object.create({ [f.methodName]: f.method }); f.state.engine = engine;
    await f.invoke(); exact(f, f.actor, "PUBLIC-PATH", f.body, engine);
  });
  await t.test("thenable engine is used immediately without then access", async () => {
    const f = fixture(verb), engine = { [f.methodName]: f.method, get then() { throw f.error; } }; f.state.engine = engine;
    await f.invoke(); exact(f, f.actor, "PUBLIC-PATH", f.body, engine);
  });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-BODY")]) await t.test(`body ${String(value)} forwarded without schema execution or property reads`, async () => {
    const f = fixture(verb); f.state.body = value; await f.invoke(); exact(f, f.actor, "PUBLIC-PATH", value);
  });
  await t.test("body protocol then read only; nested data never inspected", async () => {
    const f = fixture(verb); let count = 0;
    const body = new Proxy({}, { get(_target, key) { assert.equal(key, "then"); count++; return undefined; }, ownKeys() { throw f.error; } });
    f.state.body = body; await f.invoke(); exact(f, f.actor, "PUBLIC-PATH", body); assert.equal(count, 1);
  });
  await t.test("held body blocks method; captures receiver/method/actor/id before awaiting", async () => {
    const f = fixture(verb), held = deferred(), actor = untouched("captured actor"); f.state.body = held.promise;
    const pending = f.invoke(f.params, f.request, actor); await turns(); assert.equal(f.writes.length, 0);
    f.state.id = "PUBLIC-LATER"; f.state.engine = untouched("later engine"); f.state.method = () => { throw f.error; };
    held.resolve(f.body); assert.equal(await pending, f.result); exact(f, actor); assert.deepEqual(f.calls, ordered);
  });
  await t.test("body hook cannot replace captured method or receiver", async () => {
    const f = fixture(verb); f.state.bodyHook = () => { f.state.method = () => { throw f.error; }; f.state.engine = null; };
    await f.invoke(); exact(f); assert.equal(f.writes.length, 1);
  });
  await t.test("method getter mutation cannot replace its captured return", async () => {
    const f = fixture(verb), engine = Object.defineProperty({}, f.methodName, { get() {
      f.calls.push("method-get"); f.state.method = () => { throw f.error; }; return f.method;
    } }); f.state.engine = engine; await f.invoke(); exact(f, f.actor, "PUBLIC-PATH", f.body, engine);
  });
  await t.test("id getter changes engine before method capture", async () => {
    const f = fixture(verb), engine = { [f.methodName]: f.method };
    await f.invoke({ get id() { f.state.engine = engine; return "PUBLIC-GETTER"; } }); exact(f, f.actor, "PUBLIC-GETTER", f.body, engine);
  });
  await t.test("held body refusal preserves exact identity with no method call", async () => {
    const f = fixture(verb), held = deferred(); f.state.body = held.promise;
    const refusal = assert.rejects(f.invoke(), e => e === f.error); await turns(); held.reject(f.error); await refusal; assert.equal(f.writes.length, 0);
  });
  await t.test("body thenable adopts exact resolved model", async () => {
    const f = fixture(verb); let count = 0; f.state.body = { then(resolve: (v: unknown) => void) { count++; resolve(f.body); } };
    await f.invoke(); exact(f); assert.equal(count, 1);
  });
  await t.test("body then getter refusal preserves exact error", async () => {
    const f = fixture(verb); f.state.body = { get then() { throw f.error; } };
    await assert.rejects(f.invoke(), e => e === f.error); assert.equal(f.writes.length, 0);
  });
  for (const value of [undefined, null, false, 0, "", NaN, Symbol("PUBLIC-RESULT")]) await t.test(`result ${String(value)} adopted`, async () => {
    const f = fixture(verb); f.state.result = value; assert.equal(await f.invoke(), value); exact(f);
  });
  await t.test("held result cannot settle early; resolves exact model", async () => {
    const f = fixture(verb), held = deferred(); f.state.result = held.promise; let settled = false;
    const pending = f.invoke().finally(() => { settled = true; }); await turns(); exact(f); assert.equal(settled, false);
    held.resolve(f.result); assert.equal(await pending, f.result); assert.equal(settled, true);
  });
  await t.test("held result rejection preserves exact error and never retries", async () => {
    const f = fixture(verb), held = deferred(); f.state.result = held.promise;
    const refusal = assert.rejects(f.invoke(), e => e === f.error); await turns(); held.reject(f.error); await refusal; assert.equal(f.writes.length, 1);
  });
  await t.test("result thenable resolves exact identity", async () => {
    const f = fixture(verb); let count = 0; f.state.result = { then(resolve: (v: unknown) => void) { count++; resolve(f.result); } };
    assert.equal(await f.invoke(), f.result); assert.equal(count, 1);
  });
  await t.test("result then getter refusal preserves exact rejection", async () => {
    const f = fixture(verb); f.state.result = { get then() { throw f.error; } };
    await assert.rejects(f.invoke(), e => e === f.error); assert.equal(f.writes.length, 1);
  });
  await t.test("fresh call repeats engine/method/body lookups after refusal", async () => {
    const f = fixture(verb); f.state.methodGetError = f.error; await assert.rejects(f.invoke(), e => e === f.error);
    f.state.methodGetError = null; f.state.id = "PUBLIC-FRESH"; await f.invoke(); exact(f, f.actor, "PUBLIC-FRESH"); assert.equal(f.engines.length, 2);
  });
  await t.test("interleaved bodies/results retain separate receiver/method/actor/id/body", async () => {
    const f = fixture(verb), one = deferred(), two = deferred(), outOne = deferred(), outTwo = deferred();
    const a = untouched("actor one"), b = untouched("actor two"), x = Object.freeze({ public: "BODY1" }), y = Object.freeze({ public: "BODY2" });
    const r = Object.freeze({ public: "RESULT1" }), s = Object.freeze({ public: "RESULT2" });
    const e1 = { [f.methodName]: function(this: unknown, ...args: unknown[]) { f.writes.push({ receiver: this, args }); return outOne.promise; } };
    const e2 = { [f.methodName]: function(this: unknown, ...args: unknown[]) { f.writes.push({ receiver: this, args }); return outTwo.promise; } };
    f.state.engine = e1; f.state.body = one.promise; const p = f.invoke({ id: "ONE" }, f.request, a);
    f.state.engine = e2; f.state.body = two.promise; const q = f.invoke({ id: "TWO" }, f.request, b);
    assert.equal(f.writes.length, 0); two.resolve(y); await turns(); exact(f, b, "TWO", y, e2);
    one.resolve(x); await turns(); exact(f, a, "ONE", x, e1); assert.equal(f.writes.length, 2);
    outTwo.resolve(s); assert.equal(await q, s); outOne.resolve(r); assert.equal(await p, r);
  });
});
