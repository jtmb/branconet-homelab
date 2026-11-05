import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC SOURCE controls. The wrapper, body, parser, schema, engine,
// registry, actor and request are inert models. No actual HTTP/auth/native/DB.
type Model = Record<string, any>;
type Kind = "GET" | "DELETE";
const routes = {
  GET: "src/app/api/kv/paths/[id]/versions/[version]/data/route.ts",
  DELETE: "src/app/api/kv/paths/[id]/versions/[version]/route.ts",
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
  const calls: string[] = [], seen: Model = { wrappers: [], reads: [], destroys: [], bodies: [], versions: [] };
  const registry = { public: "REGISTRY" }, actor = { public: "ACTOR" }, signal = { public: "SIGNAL" };
  const schema = { public: "OMITTED-SCHEMA" }, result = { public: "RESULT" }, error = new Error("PUBLIC-FAULT");
  const body = { resourceVersion: "PUBLIC-RV", expectedHead: 3, pathRevision: 5,
    confirmPath: "public/path", sourceUid: "PUBLIC-UID", histories: [{ version: 2, name: "PUBLIC-HISTORY", uid: "PUBLIC-HISTORY-UID" }] };
  const waitingBody = deferred(), waitingResult = deferred();
  const state: Model = { parsed: 2, body, result, engineError: null, methodError: null, methodReject: false,
    methodPending: false, omitError: null, bodyError: null, bodyThrows: false, bodyPending: false,
    versionError: null, signalError: null, idError: null, rawError: null };
  let operation: any;
  const request = new Proxy({}, { get: (_target, key) => {
    assert.equal(key, "signal"); calls.push("signal"); if (state.signalError) throw state.signalError; return signal;
  } });
  const engine = {
    read(...args: unknown[]) { calls.push("read"); seen.reads.push(args); return outcome(); },
    destroy(...args: unknown[]) { calls.push("destroy"); seen.destroys.push(args); return outcome(); },
  };
  function outcome() {
    if (state.methodError) { if (state.methodReject) return Promise.reject(state.methodError); throw state.methodError; }
    return state.methodPending ? waitingResult.promise : state.result;
  }
  const http = {
    kvHuman(...args: any[]) { calls.push("wrap"); seen.wrappers.push(args); operation = args[0]; return operation; },
    kvEngine(r: unknown) { calls.push("engine"); assert.equal(r, registry); if (state.engineError) throw state.engineError; return engine; },
    historyVersion(raw: unknown) { calls.push("version"); seen.versions.push(raw); if (state.versionError) throw state.versionError; return state.parsed; },
    kvBody(...args: unknown[]) {
      calls.push("body"); seen.bodies.push(args);
      if (state.bodyThrows) throw state.bodyError;
      if (state.bodyError) return Promise.reject(state.bodyError);
      return state.bodyPending ? waitingBody.promise : Promise.resolve(state.body);
    },
  };
  const nativeDestroy = { omit(value: unknown) {
    calls.push("omit"); assert.equal(JSON.stringify(value), '{"versions":true}');
    if (state.omitError) throw state.omitError; return schema;
  } };
  const m = { exports: {} as Model };
  runInNewContext(compiled[kind], { module: m, exports: m.exports, require: (name: string) => {
    if (name === "@/lib/kv-http") return http;
    assert.equal(kind, "DELETE"); assert.equal(name, "@/lib/kv-schemas"); return { nativeDestroy };
  } }, { filename: routes[kind], timeout: 5000 });
  assert.deepEqual(calls, ["wrap"]); calls.length = 0;
  const params = { get id() { calls.push("id"); if (state.idError) throw state.idError; return "PUBLIC-PATH"; },
    get version() { calls.push("raw"); if (state.rawError) throw state.rawError; return "PUBLIC-RAW-VERSION"; } };
  return { calls, seen, state, registry, actor, signal, request, schema, result, error, body, waitingBody, waitingResult,
    exports: m.exports, invoke: (p: unknown = params, r: unknown = request, a: unknown = actor) => operation(registry, a, r, p) as Promise<unknown> };
}
function exactDelete(f: ReturnType<typeof fixture>, expectedVersion = f.state.parsed) {
  const args = f.seen.destroys.at(-1); assert.equal(args.length, 4);
  assert.equal(args[0], f.actor); assert.equal(args[1], "PUBLIC-PATH"); assert.equal(args[3], f.signal);
  const options = args[2]; assert.notEqual(options, f.state.body);
  assert.equal(JSON.stringify(options.versions), JSON.stringify([expectedVersion]));
  for (const key of Object.keys(f.state.body)) if (key !== "versions") assert.equal(options[key], f.state.body[key]);
  assert.equal(Object.keys(options).length, Object.keys(f.state.body).filter(k => k !== "versions").length + 1);
}
test("historical GET exact SOURCE delegation", async t => {
  await t.test("exports node runtime, force-dynamic and one default-status human wrapper", () => {
    const f = fixture("GET"); assert.deepEqual(Object.keys(f.exports).sort(), ["GET", "dynamic", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    assert.equal(f.seen.wrappers.length, 1); assert.equal(f.seen.wrappers[0].length, 1); assert.equal(f.exports.GET, f.seen.wrappers[0][0]);
  });
  await t.test("forwards exact actor/path/parsed version, returns exact result and touches no request", async () => {
    const f = fixture("GET"); assert.equal(await f.invoke(), f.result);
    assert.deepEqual(f.calls, ["id", "raw", "engine", "version", "read"]);
    assert.deepEqual(f.seen.reads, [[f.actor, "PUBLIC-PATH", 2]]); assert.deepEqual(f.seen.versions, ["PUBLIC-RAW-VERSION"]);
    assert.equal(f.seen.bodies.length, 0); assert.equal(f.seen.destroys.length, 0);
  });
  for (const field of ["idError", "rawError", "engineError", "versionError", "methodError"]) await t.test(`refusal ${field} propagates and stops later work`, async () => {
    const f = fixture("GET"); f.state[field] = f.error;
    await assert.rejects(f.invoke(), e => e === f.error);
    const expected: Model = { idError: ["id"], rawError: ["id", "raw"], engineError: ["id", "raw", "engine"],
      versionError: ["id", "raw", "engine", "version"], methodError: ["id", "raw", "engine", "version", "read"] };
    assert.deepEqual(f.calls, expected[field]);
  });
  await t.test("read rejected promise preserves exact error", async () => {
    const f = fixture("GET"); f.state.methodError = f.error; f.state.methodReject = true;
    await assert.rejects(f.invoke(), e => e === f.error); assert.equal(f.seen.reads.length, 1);
  });
  await t.test("held read does not deliver early", async () => {
    const f = fixture("GET"); f.state.methodPending = true; let settled = false;
    const pending = f.invoke().finally(() => { settled = true; }); await turns(); assert.equal(settled, false);
    f.waitingResult.resolve(f.result); assert.equal(await pending, f.result); assert.equal(settled, true);
  });
  for (const value of [undefined, null, false, 0, ""]) await t.test(`preserves raw read result ${String(value)}`, async () => {
    const f = fixture("GET"); f.state.result = value; assert.equal(await f.invoke(), value);
  });
  await t.test("repeated invocations retrieve fresh parameters and parsed version after refusal", async () => {
    const f = fixture("GET"); await f.invoke(); f.state.versionError = f.error; await assert.rejects(f.invoke(), e => e === f.error);
    f.state.versionError = null; f.state.parsed = 9; await f.invoke({ id: "PUBLIC-NEXT", version: "NEXT-RAW" });
    assert.deepEqual(f.seen.reads, [[f.actor, "PUBLIC-PATH", 2], [f.actor, "PUBLIC-NEXT", 9]]);
    assert.deepEqual(f.seen.versions, ["PUBLIC-RAW-VERSION", "PUBLIC-RAW-VERSION", "NEXT-RAW"]);
  });
});
test("single-version DELETE exact SOURCE delegation", async t => {
  await t.test("exports node runtime and one default-status human wrapper", () => {
    const f = fixture("DELETE"); assert.deepEqual(Object.keys(f.exports).sort(), ["DELETE", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.seen.wrappers.length, 1);
    assert.equal(f.seen.wrappers[0].length, 1); assert.equal(f.exports.DELETE, f.seen.wrappers[0][0]);
  });
  await t.test("omits only versions, delegates exact body schema/request and preserves captured prerequisites by identity", async () => {
    const f = fixture("DELETE"); assert.equal(await f.invoke(), f.result); exactDelete(f);
    assert.deepEqual(f.calls, ["id", "raw", "engine", "omit", "body", "version", "signal", "destroy"]);
    assert.deepEqual(f.seen.bodies, [[f.request, f.schema]]); assert.deepEqual(f.seen.versions, ["PUBLIC-RAW-VERSION"]);
    assert.equal(f.seen.reads.length, 0); assert.equal(Object.hasOwn(f.body, "versions"), false);
  });
  for (const field of ["idError", "rawError", "engineError", "omitError", "bodyError", "versionError", "signalError", "methodError"]) {
    await t.test(`refusal ${field} propagates and stops later work`, async () => {
      const f = fixture("DELETE"); f.state[field] = f.error; await assert.rejects(f.invoke(), e => e === f.error);
      const sequence = ["id", "raw", "engine", "omit", "body", "version", "signal", "destroy"];
      const stage: Model = { idError: 1, rawError: 2, engineError: 3, omitError: 4, bodyError: 5, versionError: 6, signalError: 7, methodError: 8 };
      assert.deepEqual(f.calls, sequence.slice(0, stage[field]));
    });
  }
  await t.test("synchronous body throw stops parser/signal/destroy", async () => {
    const f = fixture("DELETE"); f.state.bodyThrows = true; f.state.bodyError = f.error;
    await assert.rejects(f.invoke(), e => e === f.error); assert.deepEqual(f.calls, ["id", "raw", "engine", "omit", "body"]);
  });
  await t.test("held body prevents version/signal/destroy until fulfillment", async () => {
    const f = fixture("DELETE"); f.state.bodyPending = true; let settled = false;
    const pending = f.invoke().finally(() => { settled = true; }); await turns(); assert.equal(settled, false);
    assert.deepEqual(f.calls, ["id", "raw", "engine", "omit", "body"]);
    f.waitingBody.resolve(f.body); assert.equal(await pending, f.result); exactDelete(f);
  });
  await t.test("held body rejection preserves refusal without later work", async () => {
    const f = fixture("DELETE"); f.state.bodyPending = true; const pending = f.invoke();
    const refused = assert.rejects(pending, e => e === f.error); await turns(); f.waitingBody.reject(f.error); await refused;
    assert.deepEqual(f.calls, ["id", "raw", "engine", "omit", "body"]);
  });
  await t.test("only delegated schema output is spread, retaining nested and symbol identities", async () => {
    const f = fixture("DELETE"), symbol = Symbol("PUBLIC"); f.state.body = Object.freeze({ ...f.body, [symbol]: f.actor });
    await f.invoke(); exactDelete(f); assert.equal(f.seen.destroys[0][2][symbol], f.actor); assert.equal(Object.isFrozen(f.state.body), true);
  });
  await t.test("route version overrides a model-provided versions array without mutating it", async () => {
    const f = fixture("DELETE"), prior = [41, 42]; f.state.body = { ...f.body, versions: prior };
    await f.invoke(); exactDelete(f); assert.equal(f.state.body.versions, prior); assert.deepEqual(prior, [41, 42]);
  });
  await t.test("body spread getter failure stops version/signal/destroy", async () => {
    const f = fixture("DELETE"); f.state.body = { get resourceVersion() { f.calls.push("spread"); throw f.error; } };
    await assert.rejects(f.invoke(), e => e === f.error); assert.deepEqual(f.calls, ["id", "raw", "engine", "omit", "body", "spread"]);
  });
  await t.test("parameter values are captured before a held body and signal is read after fulfillment", async () => {
    const f = fixture("DELETE"), params = { id: "PUBLIC-BEFORE", version: "BEFORE" }; f.state.bodyPending = true;
    const pending = f.invoke(params); await turns(); params.id = "PUBLIC-AFTER"; params.version = "AFTER";
    f.waitingBody.resolve(f.body); await pending; assert.equal(f.seen.destroys[0][1], "PUBLIC-BEFORE");
    assert.deepEqual(f.seen.versions, ["BEFORE"]); assert.equal(f.calls.filter(x => x === "signal").length, 1);
  });
  await t.test("destroy rejected promise preserves exact error without retry", async () => {
    const f = fixture("DELETE"); f.state.methodError = f.error; f.state.methodReject = true;
    await assert.rejects(f.invoke(), e => e === f.error); assert.equal(f.seen.destroys.length, 1);
  });
  await t.test("held destroy prevents early delivery and forwards exact result", async () => {
    const f = fixture("DELETE"); f.state.methodPending = true; let settled = false;
    const pending = f.invoke().finally(() => { settled = true; }); await turns(); assert.equal(settled, false);
    exactDelete(f); f.waitingResult.resolve(f.result); assert.equal(await pending, f.result);
  });
  for (const value of [undefined, null, false, 0, ""]) await t.test(`preserves raw destroy result ${String(value)}`, async () => {
    const f = fixture("DELETE"); f.state.result = value; assert.equal(await f.invoke(), value);
  });
  await t.test("repeated invocations acquire fresh schema/body/version and retain prior captured options", async () => {
    const f = fixture("DELETE"); await f.invoke(); const first = f.seen.destroys[0][2];
    f.state.bodyError = f.error; await assert.rejects(f.invoke(), e => e === f.error); f.state.bodyError = null;
    f.state.body = { ...f.body, resourceVersion: "PUBLIC-NEXT-RV" }; f.state.parsed = 8; await f.invoke(); exactDelete(f);
    assert.equal(first.resourceVersion, "PUBLIC-RV"); assert.equal(JSON.stringify(first.versions), "[2]");
    assert.equal(f.seen.bodies.length, 3); assert.equal(f.calls.filter(x => x === "omit").length, 3);
  });
  await t.test("independent held/refused invocations cannot deliver another model's result", async () => {
    const a = fixture("DELETE"), b = fixture("DELETE"); a.state.bodyPending = true; b.state.bodyError = b.error;
    const pending = a.invoke(); await turns(); await assert.rejects(b.invoke(), e => e === b.error);
    assert.equal(a.seen.destroys.length, 0); assert.equal(b.seen.destroys.length, 0);
    a.waitingBody.resolve(a.body); assert.equal(await pending, a.result); assert.equal(a.seen.destroys.length, 1); assert.equal(b.seen.destroys.length, 0);
  });
});
