import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC SOURCE controls: only the DELETE callback executes.
// Actual wrappers, body/schema implementations, registry, engine and KvError are inert models.
type Model = Record<string, any>;
const route = "src/app/api/kv/paths/[id]/data/route.ts";
const compiled = ts.transpileModule(readFileSync(route, "utf8"), { fileName: route,
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
function deferred() {
  let resolve!: (v: any) => void, reject!: (e: unknown) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const turns = async () => { for (let i = 0; i < 16; i++) await Promise.resolve(); };
function untouched(label: string) {
  return new Proxy({}, { get() { throw Error(`PUBLIC unexpected ${label} read`); }, ownKeys() { throw Error(`PUBLIC unexpected ${label} enumeration`); } });
}
function fixture() {
  const calls: string[] = [], wrappers: any[][] = [], wrapped: unknown[] = [], bodies: unknown[][] = [],
    paths: Model[] = [], engines: unknown[][] = [], writes: Model[] = [], errors: unknown[][] = [];
  const actor = untouched("actor"), request = untouched("request"), schema = untouched("schema implementation");
  const error = Error("PUBLIC-FAULT"), result = Object.freeze({ public: "RESULT" });
  const state: Model = { id: "PUBLIC-ID", confirm: "PUBLIC/PATH", logical: "PUBLIC/PATH", body: null, path: null,
    engine: null, method: null, pathMethod: null, result, reject: null, hook: null };
  function step(name: string) {
    calls.push(name);
    if (state.hook) state.hook(name);
    if (state.fault === name) throw error;
  }
  const body = new Proxy({}, { get(_target, key) {
    if (key === "then") return undefined;
    assert.equal(key, "confirmPath"); step("confirm-get"); return state.confirm;
  }, ownKeys() { throw error; } });
  const path = new Proxy({}, { get(_target, key) {
    if (key === "then") return undefined;
    assert.equal(key, "path"); step("path-value"); return state.logical;
  }, ownKeys() { throw error; } });
  function pathMethod(this: unknown, ...args: unknown[]) {
    step("path-call"); paths.push({ receiver: this, args });
    if (state.reject === "path") return Promise.reject(error);
    return state.path;
  }
  const registry = new Proxy({}, { get(_target, key) {
    assert.equal(key, "path"); step("path-get"); return state.pathMethod;
  }, ownKeys() { throw error; } });
  function method(this: unknown, ...args: unknown[]) {
    step("write"); writes.push({ receiver: this, args });
    if (state.reject === "result") return Promise.reject(error);
    return state.result;
  }
  const engine = new Proxy({}, { get(_target, key) {
    assert.equal(key, "change"); step("method-get"); return state.method;
  }, ownKeys() { throw error; } });
  Object.assign(state, { body, path, engine, method, pathMethod });
  const http = {
    kvHuman(...args: any[]) { wrappers.push(args); const value = Object.freeze({ public: `WRAPPER-${wrappers.length}` }); wrapped.push(value); return value; },
    get kvBody() { step("body-get"); return (...args: unknown[]) => {
      step("body-call"); bodies.push(args); if (state.reject === "body") return Promise.reject(error); return state.body;
    }; },
    kvEngine(...args: unknown[]) { step("engine"); engines.push(args); return state.engine; },
  };
  const schemas = { get nativeDelete() { step("schema"); return schema; },
    get dataChange() { throw Error("PUBLIC inactive POST/PUT schema"); } };
  const contract = { get KvError() { step("error-get"); return class PublicError extends Error {
    status: unknown;
    constructor(...args: any[]) { step("error-new"); errors.push(args); super(args[1]); this.status = args[0]; }
  }; } };
  const m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, require: (name: string) => {
    if (name === "@/lib/kv-http") return http;
    if (name === "@/lib/kv-schemas") return schemas;
    assert.equal(name, "@/lib/kv-contract"); return contract;
  } }, { filename: route, timeout: 5000 });
  assert.equal(wrappers.length, 4); assert.equal(calls.length, 0);
  const params = new Proxy({}, { get(_target, key) { assert.equal(key, "id"); step("id"); return state.id; }, ownKeys() { throw error; } });
  const callback = wrappers[3][0];
  return { calls, wrappers, wrapped, bodies, paths, engines, writes, errors, actor, request, schema, error, result,
    body, path, registry, engine, method, pathMethod, state, params, exports: m.exports,
    invoke: (...args: unknown[]) => callback(args.length > 3 ? args[3] : registry, args.length > 2 ? args[2] : actor,
      args.length > 1 ? args[1] : request, args.length ? args[0] : params) as Promise<unknown> };
}
type Fixture = ReturnType<typeof fixture>;
const ordered = ["id", "body-get", "schema", "body-call", "path-get", "path-call", "confirm-get", "path-value", "engine", "method-get", "write"];
const isError = (e: unknown) => Object.prototype.toString.call(e) === "[object Error]";
function exact(f: Fixture, ...expected: unknown[]) {
  const actor = expected.length ? expected[0] : f.actor, id = expected.length > 1 ? expected[1] : "PUBLIC-ID";
  const body = expected.length > 2 ? expected[2] : f.body, engine = expected.length > 3 ? expected[3] : f.engine;
  const seen = f.writes.at(-1)!; assert.equal(seen.receiver, engine); assert.equal(seen.args.length, 4);
  assert.equal(seen.args[0], actor); assert.equal(seen.args[1], id); assert.equal(seen.args[2], body); assert.equal(seen.args[3], "delete");
}
function mismatch(f: Fixture) {
  return assert.rejects(f.invoke(), (e: any) => e.status === 400 && e.message === "Exact logical path confirmation required");
}

test("human current-value DELETE exact SOURCE delegation", async t => {
  await t.test("four exact inert wrappers, POST201/default peers, runtime and dynamic exports", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["DELETE", "GET", "POST", "PUT", "dynamic", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    for (const [i, verb] of ["GET", "POST", "PUT", "DELETE"].entries()) {
      assert.equal(f.exports[verb], f.wrapped[i]); assert.equal(typeof f.wrappers[i][0], "function");
      assert.equal(f.wrappers[i].length, verb === "POST" ? 2 : 1); if (verb === "POST") assert.equal(f.wrappers[i][1], 201);
    }
    assert.equal(f.calls.length, 0);
  });
  await t.test("exact ordered body/path/confirmation/engine delegation and original receivers", async () => {
    const f = fixture(); assert.equal(await f.invoke(), f.result); exact(f); assert.deepEqual(f.calls, ordered);
    assert.equal(f.bodies.length, 1); assert.equal(f.bodies[0].length, 2); assert.equal(f.bodies[0][0], f.request); assert.equal(f.bodies[0][1], f.schema);
    assert.equal(f.paths.length, 1); assert.equal(f.paths[0].receiver, f.registry); assert.equal(f.paths[0].args.length, 1); assert.equal(f.paths[0].args[0], "PUBLIC-ID");
    assert.equal(f.engines.length, 1); assert.equal(f.engines[0].length, 1); assert.equal(f.engines[0][0], f.registry); assert.equal(f.errors.length, 0);
  });
  for (const [i, stage] of ordered.entries()) await t.test(`${stage} getter/call refusal stops all later stages`, async () => {
    const f = fixture(); f.state.fault = stage; await assert.rejects(f.invoke(), e => e === f.error);
    assert.deepEqual(f.calls, ordered.slice(0, i + 1)); assert.equal(f.writes.length, 0);
  });
  for (const stage of ["body", "path", "result"]) await t.test(`${stage} rejected promise preserves exact error without retry`, async () => {
    const f = fixture(); f.state.reject = stage; await assert.rejects(f.invoke(), e => e === f.error);
    assert.deepEqual(f.calls, ordered.slice(0, stage === "body" ? 4 : stage === "path" ? 6 : 11));
    assert.equal(f.writes.length, stage === "result" ? 1 : 0);
  });
  for (const value of [undefined, null]) await t.test(`nullish params ${String(value)} refuse before imports`, async () => {
    const f = fixture(); await assert.rejects(f.invoke(value), isError); assert.equal(f.calls.length, 0);
  });
  await t.test("missing id forwarded exactly as undefined; no route validation", async () => {
    const f = fixture(); await f.invoke({}); exact(f, f.actor, undefined); assert.equal(f.paths[0].args[0], undefined); assert.deepEqual(f.calls, ordered.slice(1));
  });
  await t.test("inherited id read once with unrelated params untouched", async () => {
    const f = fixture(), id = Object.freeze({ public: "ID" }); let reads = 0;
    const params = Object.create({ get id() { reads++; return id; } }); Object.defineProperty(params, "other", { get() { throw f.error; } });
    await f.invoke(params); exact(f, f.actor, id); assert.equal(f.paths[0].args[0], id); assert.equal(reads, 1);
  });
  for (const id of [null, false, 0, "", Symbol("PUBLIC-ID")]) await t.test(`opaque id ${String(id)} reaches both delegates unchanged`, async () => {
    const f = fixture(); f.state.id = id; await f.invoke(); exact(f, f.actor, id); assert.equal(f.paths[0].args[0], id);
  });
  for (const value of [undefined, null]) await t.test(`nullish registry ${String(value)} refuses after body awaiting`, async () => {
    const f = fixture(), held = deferred(); f.state.body = held.promise;
    const refusal = assert.rejects(f.invoke(f.params, f.request, f.actor, value), isError); await turns(); assert.deepEqual(f.calls, ordered.slice(0, 4));
    held.resolve(f.body); await refusal; assert.equal(f.engines.length, 0);
  });
  for (const value of [undefined, null, 3, {}]) await t.test(`noncallable path ${String(value)} refuses after body without confirmations`, async () => {
    const f = fixture(); f.state.pathMethod = value; await assert.rejects(f.invoke(), isError);
    assert.deepEqual(f.calls, ordered.slice(0, 5)); assert.equal(f.engines.length, 0);
  });
  for (const value of [undefined, null]) await t.test(`nullish body ${String(value)} still awaits path before refusal`, async () => {
    const f = fixture(), held = deferred(); f.state.body = value; f.state.path = held.promise;
    const refusal = assert.rejects(f.invoke(), isError); await turns(); assert.deepEqual(f.calls, ordered.slice(0, 6));
    held.resolve(f.path); await refusal; assert.equal(f.engines.length, 0);
  });
  for (const value of [undefined, null]) await t.test(`nullish path ${String(value)} refuses after confirm read`, async () => {
    const f = fixture(); f.state.path = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.calls, ordered.slice(0, 7));
  });
  for (const [confirm, logical] of [["PUBLIC/OTHER", "PUBLIC/PATH"], ["1", 1], [0, false], [undefined, null], [NaN, NaN], [{}, {}]])
    await t.test(`strict confirmation mismatch ${String(confirm)} / ${String(logical)} uses fixed KvError400`, async () => {
      const f = fixture(); f.state.confirm = confirm; f.state.logical = logical; await mismatch(f);
      assert.deepEqual(f.calls, [...ordered.slice(0, 8), "error-get", "error-new"]); assert.deepEqual(f.errors, [[400, "Exact logical path confirmation required"]]);
      assert.equal(f.engines.length, 0); assert.equal(f.writes.length, 0);
    });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-MATCH"), Object.freeze({ public: "SAME" })])
    await t.test(`identical modeled confirmation ${String(value)} delegates without route coercion`, async () => {
      const f = fixture(); f.state.confirm = value; f.state.logical = value; await f.invoke(); exact(f); assert.deepEqual(f.calls, ordered);
    });
  await t.test("confirmation mismatch never coerces objects", async () => {
    const f = fixture(); f.state.confirm = untouched("confirm coercion"); f.state.logical = untouched("path coercion"); await mismatch(f); assert.equal(f.engines.length, 0);
  });
  for (const stage of ["error-get", "error-new"]) await t.test(`${stage} refusal preserves exact model error; no engine delegation`, async () => {
    const f = fixture(); f.state.confirm = "PUBLIC/OTHER"; f.state.fault = stage;
    await assert.rejects(f.invoke(), e => e === f.error); assert.equal(f.engines.length, 0); assert.equal(f.writes.length, 0);
    assert.deepEqual(f.calls, [...ordered.slice(0, 8), "error-get", ...(stage === "error-new" ? ["error-new"] : [])]);
  });
  for (const value of [undefined, null]) await t.test(`nullish engine ${String(value)} refuses only after matching confirmations`, async () => {
    const f = fixture(); f.state.engine = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.calls, ordered.slice(0, 9));
  });
  for (const value of [undefined, null, 7, {}]) await t.test(`noncallable change ${String(value)} refuses after confirmation and capture`, async () => {
    const f = fixture(); f.state.method = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.calls, ordered.slice(0, 10));
  });
  await t.test("inherited path method receives original registry", async () => {
    const f = fixture(), registry = Object.create({ path: f.pathMethod }); await f.invoke(f.params, f.request, f.actor, registry);
    assert.equal(f.paths[0].receiver, registry); assert.equal(f.engines[0][0], registry); exact(f);
  });
  await t.test("inherited change receives original engine without awaiting engine", async () => {
    const f = fixture(), engine = Object.create({ change: f.method, get then() { throw f.error; } }); f.state.engine = engine;
    await f.invoke(); exact(f, f.actor, "PUBLIC-ID", f.body, engine);
  });
  await t.test("inherited confirmation fields are read once and unrelated fields untouched", async () => {
    const f = fixture(); let one = 0, two = 0;
    const body = Object.create({ get confirmPath() { one++; return "PUBLIC/PATH"; } });
    const path = Object.create({ get path() { two++; return "PUBLIC/PATH"; } });
    for (const object of [body, path]) Object.defineProperty(object, "other", { get() { throw f.error; } });
    f.state.body = body; f.state.path = path; await f.invoke(); exact(f, f.actor, "PUBLIC-ID", body); assert.equal(one, 1); assert.equal(two, 1);
  });
  await t.test("held body prevents registry lookup and captures actor/id while later path method remains fresh", async () => {
    const f = fixture(), held = deferred(), actor = untouched("captured actor"); f.state.body = held.promise;
    const pending = f.invoke(f.params, f.request, actor); await turns(); assert.deepEqual(f.calls, ordered.slice(0, 4));
    f.state.id = "PUBLIC-LATER"; const pathMethod = function(this: unknown, ...args: unknown[]) { f.paths.push({ receiver: this, args }); return f.path; };
    f.state.pathMethod = pathMethod; held.resolve(f.body); await pending; exact(f, actor); assert.equal(f.paths[0].args[0], "PUBLIC-ID");
  });
  await t.test("held path prevents confirmation and engine access; captures original path method call", async () => {
    const f = fixture(), held = deferred(); f.state.path = held.promise; const pending = f.invoke(); await turns();
    assert.deepEqual(f.calls, ordered.slice(0, 6)); f.state.pathMethod = () => { throw f.error; };
    held.resolve(f.path); await pending; exact(f); assert.equal(f.paths.length, 1);
  });
  await t.test("body refusal precedes a throwing path getter", async () => {
    const f = fixture(); f.state.reject = "body"; f.state.fault = "path-get"; await assert.rejects(f.invoke(), e => e === f.error); assert.deepEqual(f.calls, ordered.slice(0, 4));
  });
  await t.test("path refusal precedes a throwing confirmation getter", async () => {
    const f = fixture(); f.state.reject = "path"; f.state.fault = "confirm-get"; await assert.rejects(f.invoke(), e => e === f.error); assert.deepEqual(f.calls, ordered.slice(0, 6));
  });
  await t.test("confirm getter executes before path getter and may change its current value", async () => {
    const f = fixture(); f.state.confirm = "PUBLIC/NEXT"; f.state.hook = (stage: string) => { if (stage === "confirm-get") f.state.logical = "PUBLIC/NEXT"; };
    await f.invoke(); exact(f); assert.deepEqual(f.calls, ordered);
  });
  await t.test("path getter cannot retroactively replace captured confirmation", async () => {
    const f = fixture(); f.state.hook = (stage: string) => { if (stage === "path-value") f.state.confirm = "PUBLIC/LATER"; };
    await f.invoke(); exact(f); assert.deepEqual(f.calls, ordered);
  });
  await t.test("matching confirmations precede fresh engine/method lookup", async () => {
    const f = fixture(), engine = { change: f.method }; f.state.hook = (stage: string) => { if (stage === "path-value") f.state.engine = engine; };
    await f.invoke(); exact(f, f.actor, "PUBLIC-ID", f.body, engine);
  });
  await t.test("change getter captures returned method and original receiver despite mutation", async () => {
    const f = fixture(), engine = Object.defineProperty({}, "change", { get() { f.state.engine = null; f.state.method = null; return f.method; } });
    f.state.engine = engine; await f.invoke(); exact(f, f.actor, "PUBLIC-ID", f.body, engine);
  });
  await t.test("path getter captures returned method and original registry despite mutation", async () => {
    const f = fixture(), registry = Object.defineProperty({}, "path", { get() { f.state.pathMethod = null; return f.pathMethod; } });
    await f.invoke(f.params, f.request, f.actor, registry); exact(f); assert.equal(f.paths[0].receiver, registry); assert.equal(f.engines[0][0], registry);
  });
  for (const stage of ["body", "path"]) {
    await t.test(`${stage} thenable adopts exact resolved identity`, async () => {
      const f = fixture(); let calls = 0; f.state[stage] = { then(resolve: (v: unknown) => void) { calls++; resolve(stage === "body" ? f.body : f.path); } };
      await f.invoke(); exact(f); assert.equal(calls, 1);
    });
    await t.test(`${stage} then getter refusal prevents subsequent stages`, async () => {
      const f = fixture(); f.state[stage] = { get then() { throw f.error; } };
      await assert.rejects(f.invoke(), e => e === f.error); assert.deepEqual(f.calls, ordered.slice(0, stage === "body" ? 4 : 6));
    });
    await t.test(`${stage} held rejection preserves exact error without downstream work`, async () => {
      const f = fixture(), held = deferred(); f.state[stage] = held.promise;
      const refusal = assert.rejects(f.invoke(), e => e === f.error); await turns(); held.reject(f.error); await refusal;
      assert.deepEqual(f.calls, ordered.slice(0, stage === "body" ? 4 : 6));
    });
  }
  for (const value of [undefined, null, false, 0, "", NaN, Symbol("PUBLIC-RESULT")]) await t.test(`result ${String(value)} is adopted unchanged`, async () => {
    const f = fixture(); f.state.result = value; assert.equal(await f.invoke(), value); exact(f);
  });
  await t.test("held result cannot settle before resolution and adopts exact resolved object", async () => {
    const f = fixture(), held = deferred(); f.state.result = held.promise; let settled = false;
    const pending = f.invoke().finally(() => { settled = true; }); await turns(); exact(f); assert.equal(settled, false);
    held.resolve(f.result); assert.equal(await pending, f.result); assert.equal(settled, true);
  });
  await t.test("held result rejection preserves exact error without repeating change", async () => {
    const f = fixture(), held = deferred(); f.state.result = held.promise;
    const refusal = assert.rejects(f.invoke(), e => e === f.error); await turns(); held.reject(f.error); await refusal; assert.equal(f.writes.length, 1);
  });
  await t.test("result thenable adopts exact resolved identity", async () => {
    const f = fixture(); let count = 0; f.state.result = { then(resolve: (v: unknown) => void) { count++; resolve(f.result); } };
    assert.equal(await f.invoke(), f.result); assert.equal(count, 1);
  });
  await t.test("result then getter refusal preserves exact error", async () => {
    const f = fixture(); f.state.result = { get then() { throw f.error; } }; await assert.rejects(f.invoke(), e => e === f.error); assert.equal(f.writes.length, 1);
  });
  await t.test("fresh call after mismatch rereads body/path/confirmations and delegates once", async () => {
    const f = fixture(); f.state.confirm = "PUBLIC/OTHER"; await mismatch(f); f.state.confirm = "PUBLIC/PATH";
    await f.invoke(); exact(f); assert.equal(f.bodies.length, 2); assert.equal(f.paths.length, 2); assert.equal(f.writes.length, 1);
  });
  await t.test("fresh call after path refusal repeats body and path lookup", async () => {
    const f = fixture(); f.state.fault = "path-get"; await assert.rejects(f.invoke(), e => e === f.error); f.state.fault = null;
    await f.invoke(); exact(f); assert.equal(f.bodies.length, 2); assert.equal(f.paths.length, 1); assert.equal(f.writes.length, 1);
  });
  await t.test("interleaved bodies/paths/results retain exact per-call identities and settle independently", async () => {
    const f = fixture(), b1 = deferred(), b2 = deferred(), p1 = deferred(), p2 = deferred(), r1 = deferred(), r2 = deferred();
    const body1 = Object.freeze({ confirmPath: "PUBLIC/ONE" }), body2 = Object.freeze({ confirmPath: "PUBLIC/TWO" });
    const actor1 = untouched("actor one"), actor2 = untouched("actor two"), result1 = Object.freeze({ public: "ONE" }), result2 = Object.freeze({ public: "TWO" });
    f.state.body = b1.promise; const one = f.invoke({ id: "PUBLIC-ONE" }, f.request, actor1); await turns();
    f.state.body = b2.promise; const two = f.invoke({ id: "PUBLIC-TWO" }, f.request, actor2); await turns();
    f.state.path = p2.promise; b2.resolve(body2); await turns();
    f.state.path = p1.promise; b1.resolve(body1); await turns();
    assert.equal(f.paths.length, 2); assert.equal(f.paths[0].args[0], "PUBLIC-TWO"); assert.equal(f.paths[1].args[0], "PUBLIC-ONE");
    const e1 = { change: function(this: unknown, ...args: unknown[]) { f.writes.push({ receiver: this, args }); return r1.promise; } };
    const e2 = { change: function(this: unknown, ...args: unknown[]) { f.writes.push({ receiver: this, args }); return r2.promise; } };
    f.state.engine = e1; p1.resolve(Object.freeze({ path: "PUBLIC/ONE" })); await turns(); exact(f, actor1, "PUBLIC-ONE", body1, e1);
    f.state.engine = e2; p2.resolve(Object.freeze({ path: "PUBLIC/TWO" })); await turns(); exact(f, actor2, "PUBLIC-TWO", body2, e2);
    r2.resolve(result2); assert.equal(await two, result2); r1.resolve(result1); assert.equal(await one, result1); assert.equal(f.writes.length, 2);
  });
});
