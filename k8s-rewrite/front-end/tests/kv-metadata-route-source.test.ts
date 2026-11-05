import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC SOURCE controls. All imported implementations are inert.
// Plain parameter/request models only; no HTTP/auth/registry/native/SQL execution.
type Model = Record<string, any>;
type Kind = "status" | "versions";
const routes = {
  status: "src/app/api/kv/paths/[id]/status/route.ts",
  versions: "src/app/api/kv/paths/[id]/versions/route.ts",
};
const compiled = Object.fromEntries(Object.entries(routes).map(([kind, file]) => [kind,
  ts.transpileModule(readFileSync(file, "utf8"), { fileName: file,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText]));
function deferred() {
  let resolve!: (value: any) => void, reject!: (error: unknown) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const turns = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
function fixture(kind: Kind) {
  const calls: string[] = [], seen: Model = { wrappers: [], engines: [], invocations: [], receivers: [] };
  const registry = Object.freeze({ public: "REGISTRY" }), actor = Object.freeze({ public: "ACTOR" });
  const result = Object.freeze({ public: "RESULT" }), error = new Error("PUBLIC-FAULT");
  const state: Model = { result, idError: null, engineError: null, getterError: null, methodError: null };
  const request = new Proxy({}, { get() { throw Error("PUBLIC: request access forbidden"); } });
  let operation: any;
  const wrapped = () => { throw Error("PUBLIC: wrapper model is not an HTTP handler"); };
  const engine = Object.defineProperties({}, {
    [kind]: { get() {
      calls.push("method"); if (state.getterError) throw state.getterError;
      return function(this: unknown, ...args: unknown[]) {
        calls.push("invoke"); seen.invocations.push(args); seen.receivers.push(this);
        if (state.methodError) throw state.methodError; return state.result;
      };
    } },
    [kind === "status" ? "versions" : "status"]: { get() { throw Error("PUBLIC: wrong method"); } },
  });
  const http = {
    kvHuman(...args: any[]) { calls.push("wrap"); seen.wrappers.push(args); operation = args[0]; return wrapped; },
    kvEngine(r: unknown) { calls.push("engine"); seen.engines.push(r); if (state.engineError) throw state.engineError; return engine; },
    metadataCursor() { throw Error("PUBLIC: cursor parser forbidden"); },
    kvBody() { throw Error("PUBLIC: body parser forbidden"); },
    historyVersion() { throw Error("PUBLIC: version parser forbidden"); },
    kvRegistry() { throw Error("PUBLIC: registry construction forbidden"); },
  };
  const m = { exports: {} as Model };
  runInNewContext(compiled[kind], { module: m, exports: m.exports, require: (name: string) => {
    assert.equal(name, "@/lib/kv-http"); return http;
  } }, { filename: routes[kind], timeout: 5000 });
  assert.deepEqual(calls, ["wrap"]); calls.length = 0;
  const params = { get id() { calls.push("id"); if (state.idError) throw state.idError; return "PUBLIC-PATH"; } };
  return { calls, seen, registry, actor, result, error, request, params, state, engine, wrapped, exports: m.exports,
    invoke: (p: unknown = params, a: unknown = actor, r: unknown = registry, q: unknown = request) => operation(r, a, q, p) as Promise<unknown> };
}

for (const kind of ["status", "versions"] as const) test(`${kind} GET exact SOURCE delegation`, async t => {
  await t.test("exports node runtime, force-dynamic and the exact default-status human wrapper result", () => {
    const f = fixture(kind); assert.deepEqual(Object.keys(f.exports).sort(), ["GET", "dynamic", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    assert.equal(f.seen.wrappers.length, 1); assert.equal(f.seen.wrappers[0].length, 1);
    assert.equal(typeof f.seen.wrappers[0][0], "function"); assert.equal(f.exports.GET, f.wrapped);
    assert.deepEqual(f.seen.engines, []); assert.deepEqual(f.seen.invocations, []);
  });
  await t.test("forwards exact registry, actor and path with the selected engine receiver and exact result", async () => {
    const f = fixture(kind); assert.equal(await f.invoke(), f.result);
    assert.deepEqual(f.calls, ["id", "engine", "method", "invoke"]);
    assert.deepEqual(f.seen.engines, [f.registry]); assert.deepEqual(f.seen.invocations, [[f.actor, "PUBLIC-PATH"]]);
    assert.deepEqual(f.seen.receivers, [f.engine]);
  });
  await t.test("reads only id: cursor/version/body/signal, parameter enumeration and request access are absent", async () => {
    const f = fixture(kind), reads: PropertyKey[] = [];
    const params = new Proxy({}, { get(_target, key) { reads.push(key); assert.equal(key, "id"); return "PUBLIC-PROXY"; },
      ownKeys() { throw Error("PUBLIC: parameter enumeration forbidden"); } });
    assert.equal(await f.invoke(params), f.result); assert.deepEqual(reads, ["id"]);
    assert.deepEqual(f.seen.invocations, [[f.actor, "PUBLIC-PROXY"]]);
  });
  for (const [field, sequence] of [
    ["idError", ["id"]], ["engineError", ["id", "engine"]],
    ["getterError", ["id", "engine", "method"]], ["methodError", ["id", "engine", "method", "invoke"]],
  ] as const) await t.test(`exact ${field} refusal stops later source work`, async () => {
    const f = fixture(kind); f.state[field] = f.error;
    await assert.rejects(f.invoke(), e => e === f.error); assert.deepEqual(f.calls, [...sequence]);
    assert.equal(f.seen.invocations.length, field === "methodError" ? 1 : 0);
  });
  await t.test("rejected engine-method promise preserves the exact error without retry", async () => {
    const f = fixture(kind); f.state.result = Promise.reject(f.error);
    await assert.rejects(f.invoke(), e => e === f.error);
    assert.deepEqual(f.calls, ["id", "engine", "method", "invoke"]); assert.equal(f.seen.invocations.length, 1);
  });
  await t.test("held method result prevents early delivery and preserves fulfillment identity", async () => {
    const f = fixture(kind), wait = deferred(); f.state.result = wait.promise; let settled = false;
    const pending = f.invoke().finally(() => { settled = true; }); await turns(); assert.equal(settled, false);
    assert.deepEqual(f.calls, ["id", "engine", "method", "invoke"]); wait.resolve(f.result);
    assert.equal(await pending, f.result); assert.equal(settled, true); assert.equal(f.seen.invocations.length, 1);
  });
  await t.test("held method rejection preserves refusal and performs no additional work", async () => {
    const f = fixture(kind), wait = deferred(); f.state.result = wait.promise;
    const pending = f.invoke(), refused = assert.rejects(pending, e => e === f.error);
    await turns(); wait.reject(f.error); await refused;
    assert.deepEqual(f.calls, ["id", "engine", "method", "invoke"]); assert.equal(f.seen.invocations.length, 1);
  });
  for (const value of [undefined, null, false, 0, ""]) await t.test(`raw method result ${String(value)} is unchanged`, async () => {
    const f = fixture(kind); f.state.result = value; assert.equal(await f.invoke(), value);
    assert.equal(f.seen.invocations.length, 1);
  });
  await t.test("frozen result and nested model identities are returned without cloning or mutation", async () => {
    const f = fixture(kind), rows = Object.freeze([Object.freeze({ public: "ROW" })]);
    const result = Object.freeze({ public: "FROZEN", rows }); f.state.result = result;
    assert.equal(await f.invoke(), result); assert.equal(result.rows, rows); assert.equal(Object.isFrozen(result), true);
  });
  await t.test("fresh repeated invocations after refusal reacquire registry, actor, id and result", async () => {
    const f = fixture(kind); await f.invoke(); f.state.engineError = f.error; await assert.rejects(f.invoke(), e => e === f.error);
    f.state.engineError = null; const registry = { public: "NEXT-REGISTRY" }, actor = { public: "NEXT-ACTOR" }, result = { public: "NEXT-RESULT" };
    f.state.result = result; assert.equal(await f.invoke({ id: "PUBLIC-NEXT" }, actor, registry), result);
    assert.deepEqual(f.seen.engines, [f.registry, f.registry, registry]);
    assert.deepEqual(f.seen.invocations, [[f.actor, "PUBLIC-PATH"], [actor, "PUBLIC-NEXT"]]);
  });
  await t.test("id is captured before held result and subsequent parameter mutation is not reread", async () => {
    const f = fixture(kind), wait = deferred(), params = { id: "PUBLIC-BEFORE" }; f.state.result = wait.promise;
    const pending = f.invoke(params); await turns(); params.id = "PUBLIC-AFTER"; wait.resolve(f.result);
    assert.equal(await pending, f.result); assert.deepEqual(f.seen.invocations, [[f.actor, "PUBLIC-BEFORE"]]);
  });
  await t.test("interleaved held invocations retain their own captured arguments and settlement", async () => {
    const f = fixture(kind), first = deferred(), second = deferred(), actor = { public: "SECOND-ACTOR" };
    f.state.result = first.promise; const a = f.invoke({ id: "PUBLIC-FIRST" });
    f.state.result = second.promise; const b = f.invoke({ id: "PUBLIC-SECOND" }, actor);
    let firstSettled = false; const observedA = a.finally(() => { firstSettled = true; });
    const secondResult = { public: "SECOND" }; second.resolve(secondResult); assert.equal(await b, secondResult);
    await turns(); assert.equal(firstSettled, false); first.resolve(f.result); assert.equal(await observedA, f.result);
    assert.deepEqual(f.seen.invocations, [[f.actor, "PUBLIC-FIRST"], [actor, "PUBLIC-SECOND"]]);
  });
});
