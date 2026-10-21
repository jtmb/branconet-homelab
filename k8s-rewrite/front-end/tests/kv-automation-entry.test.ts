import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC route-caller source controls. Every imported dependency is
// inert; the request is a plain model, with no HTTP or credential transport.
type Value = Record<string, any>;
function deferred() {
  let resolve!: (value: any) => void, reject!: (reason: unknown) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function fixture() {
  const calls: string[] = [], auth = deferred(), body = deferred(), dispatch = deferred();
  const actor = { id: "public-owner", sessionVersion: 7, identityId: "public-identity" };
  const input = { operation: "status", pathId: "public-path" }, result = { public: "result" };
  const engine = {}, schema = {}, success = {}, failure = {};
  const state: Value = { header: "PUBLIC-INERT-HEADER", registryError: null, headerError: null,
    authError: null, engineError: null, bodyError: null, dispatchError: null,
    responseError: null, errorResponseError: null };
  let caught: unknown;
  const registry = { authenticateIdentity: (header: unknown) => {
    calls.push("authenticate"); assert.equal(header, state.header);
    if (state.authError) throw state.authError;
    return auth.promise;
  } };
  const request = { headers: { get: (name: string) => {
    calls.push("header"); assert.equal(name, "authorization");
    if (state.headerError) throw state.headerError;
    return state.header;
  } } };
  const dependencies: Value = {
    "@/lib/kv-http": {
      kvRegistry: () => { calls.push("registry"); if (state.registryError) throw state.registryError; return registry; },
      kvEngine: (r: unknown) => { calls.push("engine"); assert.equal(r, registry); if (state.engineError) throw state.engineError; return engine; },
      kvBody: (r: unknown, s: unknown) => { calls.push("body"); assert.equal(r, request); assert.equal(s, schema); if (state.bodyError) throw state.bodyError; return body.promise; },
      kvErrorResponse: (error: unknown) => { calls.push("error"); caught = error; if (state.errorResponseError) throw state.errorResponseError; return failure; },
    },
    "@/lib/kv-automation": { automationRequest: schema,
      runAutomation: (e: unknown, a: unknown, i: unknown) => {
        calls.push("dispatch"); assert.equal(e, engine); assert.equal(a, actor); assert.equal(i, input);
        if (state.dispatchError) throw state.dispatchError;
        return dispatch.promise;
      } },
    "@/lib/secret-http": { secretResponse: (r: unknown) => {
      calls.push("response"); assert.equal(r, result); if (state.responseError) throw state.responseError; return success;
    } },
  };
  const file = "src/app/api/kv/automation/route.ts", m = { exports: {} as Value };
  const output = ts.transpileModule(readFileSync(file, "utf8"), { fileName: file,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  runInNewContext(output, { module: m, exports: m.exports, require: (name: string) => {
    assert(Object.hasOwn(dependencies, name), `Unselected route dependency: ${name}`); return dependencies[name];
  } }, { filename: file, timeout: 5000 });
  assert.deepEqual(calls, []);
  const post = () => m.exports.POST(request as unknown as Request);
  return { calls, auth, body, dispatch, actor, input, result, state, success, failure, post,
    runtime: m.exports.runtime, caught: () => caught };
}
const turn = async () => { await Promise.resolve(); await Promise.resolve(); };
const prefix = ["registry", "header", "authenticate"];

test("automation route awaits authentication before dependent calls", async t => {
  await t.test("module load is inert and retains Node runtime", () => {
    const f = fixture(); assert.equal(f.runtime, "nodejs"); assert.deepEqual(f.calls, []);
  });
  await t.test("pending authentication reaches no downstream dependency", async () => {
    const f = fixture(), p = f.post(); await turn(); assert.deepEqual(f.calls, prefix);
    f.auth.resolve(f.actor); await turn(); assert.deepEqual(f.calls, [...prefix, "engine", "body"]);
    f.body.resolve(f.input); await turn(); assert.deepEqual(f.calls, [...prefix, "engine", "body", "dispatch"]);
    f.dispatch.resolve(f.result); assert.equal(await p, f.success);
    assert.deepEqual(f.calls, [...prefix, "engine", "body", "dispatch", "response"]);
  });
  for (const status of [401, 403]) {
    await t.test(`deferred authentication refusal ${status} bypasses engine body dispatch`, async () => {
      const f = fixture(), error = Object.assign(new Error("PUBLIC-AUTH-REFUSAL"), { status });
      const p = f.post(); await turn(); assert.deepEqual(f.calls, prefix);
      f.auth.reject(error); assert.equal(await p, f.failure); assert.equal(f.caught(), error);
      assert.deepEqual(f.calls, [...prefix, "error"]);
    });
  }
  await t.test("unknown authentication rejection is forwarded without dependent calls", async () => {
    const f = fixture(), error = new Error("PUBLIC-INERT-FAILURE"), p = f.post();
    f.auth.reject(error); assert.equal(await p, f.failure); assert.equal(f.caught(), error);
    assert.deepEqual(f.calls, [...prefix, "error"]);
  });
  await t.test("synchronous authentication throw bypasses dependent calls", async () => {
    const f = fixture(); f.state.authError = new Error("PUBLIC-SYNC-REFUSAL");
    assert.equal(await f.post(), f.failure); assert.equal(f.caught(), f.state.authError);
    assert.deepEqual(f.calls, [...prefix, "error"]);
  });
  await t.test("absent header is forwarded to inert authentication", async () => {
    const f = fixture(); f.state.header = null; const p = f.post(); await turn();
    assert.deepEqual(f.calls, prefix); const error = new Error("PUBLIC-MISSING-HEADER");
    f.auth.reject(error); assert.equal(await p, f.failure); assert.equal(f.caught(), error);
    assert.deepEqual(f.calls, [...prefix, "error"]);
  });
  for (const [key, expected] of [["registryError", ["registry", "error"]], ["headerError", ["registry", "header", "error"]]] as const) {
    await t.test(`${key} stops before authentication`, async () => {
      const f = fixture(); f.state[key] = new Error("PUBLIC-PREAUTH-FAILURE");
      assert.equal(await f.post(), f.failure); assert.equal(f.caught(), f.state[key]); assert.deepEqual(f.calls, expected);
    });
  }
  await t.test("engine construction failure after authentication prevents body and dispatch", async () => {
    const f = fixture(); f.state.engineError = new Error("PUBLIC-ENGINE-FAILURE");
    const p = f.post(); f.auth.resolve(f.actor); assert.equal(await p, f.failure);
    assert.equal(f.caught(), f.state.engineError); assert.deepEqual(f.calls, [...prefix, "engine", "error"]);
  });
  await t.test("pending body prevents dispatch and response", async () => {
    const f = fixture(), p = f.post(); f.auth.resolve(f.actor); await turn();
    assert.deepEqual(f.calls, [...prefix, "engine", "body"]);
    const error = new Error("PUBLIC-BODY-REFUSAL"); f.body.reject(error);
    assert.equal(await p, f.failure); assert.equal(f.caught(), error);
    assert.deepEqual(f.calls, [...prefix, "engine", "body", "error"]);
  });
  await t.test("synchronous body failure prevents dispatch", async () => {
    const f = fixture(); f.state.bodyError = new Error("PUBLIC-BODY-THROW");
    const p = f.post(); f.auth.resolve(f.actor); assert.equal(await p, f.failure);
    assert.equal(f.caught(), f.state.bodyError); assert.deepEqual(f.calls, [...prefix, "engine", "body", "error"]);
  });
  for (const mode of ["throw", "reject"] as const) {
    await t.test(`inert dispatch ${mode} prevents success response`, async () => {
      const f = fixture(), error = new Error("PUBLIC-DISPATCH-FAILURE");
      if (mode === "throw") f.state.dispatchError = error;
      const p = f.post(); f.auth.resolve(f.actor); f.body.resolve(f.input);
      if (mode === "reject") { await turn(); f.dispatch.reject(error); }
      assert.equal(await p, f.failure); assert.equal(f.caught(), error);
      assert.deepEqual(f.calls, [...prefix, "engine", "body", "dispatch", "error"]);
    });
  }
  await t.test("response construction failure uses the route error boundary", async () => {
    const f = fixture(); f.state.responseError = new Error("PUBLIC-RESPONSE-FAILURE");
    const p = f.post(); f.auth.resolve(f.actor); f.body.resolve(f.input); f.dispatch.resolve(f.result);
    assert.equal(await p, f.failure); assert.equal(f.caught(), f.state.responseError);
    assert.deepEqual(f.calls, [...prefix, "engine", "body", "dispatch", "response", "error"]);
  });
  await t.test("error responder failure propagates without downstream fallback", async () => {
    const f = fixture(); f.state.authError = new Error("PUBLIC-AUTH-THROW");
    const error = new Error("PUBLIC-ERROR-RESPONDER-THROW"); f.state.errorResponseError = error;
    await assert.rejects(f.post(), e => e === error); assert.equal(f.caught(), f.state.authError);
    assert.deepEqual(f.calls, [...prefix, "error"]);
  });
});
