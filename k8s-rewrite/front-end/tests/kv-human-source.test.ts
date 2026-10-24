import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC source controls. Request/context/actor and every dependency
// below are plain models. No actual authentication, response, registry or I/O.
type Model = Record<string, any>;
function deferred() {
  let resolve!: (value?: any) => void, reject!: (error: unknown) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const turns = async () => { for (let i = 0; i < 16; i++) await Promise.resolve(); };
const file = "src/lib/kv-http.ts";
const compiled = ts.transpileModule(readFileSync(file, "utf8"), { fileName: file,
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
function fixture() {
  const calls: string[] = [], sessions = deferred(), current = deferred(), params = deferred(), operation = deferred();
  const actor = { id: "PUBLIC-HUMAN", sessionVersion: 7 }, request = new Proxy({}, {
    get() { throw new Error("REQUEST-MUST-REMAIN-UNTOUCHED"); },
  });
  const config = { public: "CONFIG" }, namespaces = ["PUBLIC-NAMESPACE"], database = { public: "INERT-DB" };
  const result = { public: "RESULT" }, response = { public: "RESPONSE" }, errorResponse = { public: "ERROR-RESPONSE" };
  const error = new Error("PUBLIC-MODEL-REFUSAL"), values = { id: "PUBLIC-PATH" };
  const state: Model = { sessionPending: false, session: actor, sessionError: null, sessionThrows: false,
    currentPending: false, currentError: null, currentThrows: false, currentResult: {},
    params: Promise.resolve(values), paramsError: null, paramsReads: 0,
    operationPending: false, operationError: null, operationThrows: false, result,
    namespacesError: null, configError: null, constructorError: null,
    responseError: null, errorResponseError: null };
  const seen: Model = { currentActors: [], arguments: [], responses: [], errors: [], registries: [] };
  class InertError extends Error { constructor(readonly status: number, message: string) { super(message); } }
  class InertMutationError extends InertError {
    constructor(status: number, message: string, readonly operationId: string, readonly outcome: string) { super(status, message); }
  }
  class Registry {
    constructor(db: unknown, ns: unknown, cfg: unknown) {
      calls.push("construct"); assert.equal(db, database); assert.equal(ns, namespaces); assert.equal(cfg, config);
      if (state.constructorError) throw state.constructorError;
      seen.registries.push(this);
    }
    current(value: unknown) {
      calls.push("current"); seen.currentActors.push(value); assert(seen.registries.includes(this));
      if (state.currentThrows) throw state.currentError;
      if (state.currentError) return Promise.reject(state.currentError);
      return state.currentPending ? current.promise : Promise.resolve(state.currentResult);
    }
  }
  const forbidden = () => { throw new Error("UNSELECTED-INERT-IMPLEMENTATION"); };
  const dependencies: Model = {
    "./auth": { getSession: () => {
      calls.push("session"); if (state.sessionThrows) throw state.sessionError;
      if (state.sessionError) return Promise.reject(state.sessionError);
      return state.sessionPending ? sessions.promise : Promise.resolve(state.session);
    } },
    "./db": { default: database }, "./kv-registry": { KvRegistry: Registry },
    "./kv-contract": { KV_BODY_BYTES: 512 * 1024, KV_ADMIN_METADATA_BODY_BYTES: 3 * 1024 * 1024,
      KvError: InertError, KvMutationError: InertMutationError,
      kvConfig: () => { calls.push("config"); if (state.configError) throw state.configError; return config; } },
    "./kv-native-engine": { KvNativeEngine: forbidden },
    "./secret-client": { createSecretTransport: forbidden,
      secretNamespaces: () => { calls.push("namespaces"); if (state.namespacesError) throw state.namespacesError; return namespaces; } },
    "./secret-references": { listAliases: forbidden },
    "./secret-http": {
      secretResponse: (value: unknown, status: number) => { calls.push("response"); seen.responses.push([value, status]);
        if (state.responseError) throw state.responseError; return response; },
      secretErrorResponse: (value: unknown) => { calls.push("error"); seen.errors.push(value);
        if (state.errorResponseError) throw state.errorResponseError; return errorResponse; },
    },
  };
  const context = { get params() { calls.push("params"); state.paramsReads++;
    if (state.paramsError) throw state.paramsError; return state.params; } };
  const invoke = (registry: unknown, who: unknown, req: unknown, resolved: unknown) => {
    calls.push("operation"); seen.arguments.push([registry, who, req, resolved]);
    if (state.operationThrows) throw state.operationError;
    if (state.operationError) return Promise.reject(state.operationError);
    return state.operationPending ? operation.promise : Promise.resolve(state.result);
  };
  const m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports,
    require: (name: string) => { assert(Object.hasOwn(dependencies, name)); return dependencies[name]; },
  }, { filename: file, timeout: 5000 });
  assert.deepEqual(calls, []);
  const wrap = (status?: number) => status === undefined ? m.exports.kvHuman(invoke) : m.exports.kvHuman(invoke, status);
  return { calls, state, seen, actor, request, context, values, result, response, errorResponse, error,
    sessions, current, params, operation, wrap, InertMutationError, exports: m.exports,
    start: (ctx: unknown = context) => wrap()(request, ctx) as Promise<unknown> };
}
function onlyError(f: ReturnType<typeof fixture>, error: unknown) {
  assert.equal(f.seen.arguments.length, 0); assert.equal(f.seen.responses.length, 0);
  assert.equal(f.seen.errors.length, 1); assert.equal(f.seen.errors[0], error);
}
const prefix = ["session", "namespaces", "config", "construct", "current"];
test("kvHuman orders fresh plain-model gates and delegates results/errors", async t => {
  await t.test("factory is inert until invocation", () => {
    const f = fixture(); assert.equal(typeof f.wrap(), "function"); assert.deepEqual(f.calls, []);
  });
  await t.test("held session prevents registry, context and operation access", async () => {
    const f = fixture(); f.state.sessionPending = true; f.state.paramsError = f.error;
    const p = f.start(); let settled = false; void p.then(() => { settled = true; });
    await turns(); assert.deepEqual(f.calls, ["session"]); assert.equal(settled, false);
    f.sessions.resolve(null); assert.equal(await p, f.errorResponse);
    assert.deepEqual(f.calls, ["session", "error"]); assert.equal(f.seen.errors[0].status, 401);
  });
  for (const session of [null, undefined]) {
    await t.test(`missing session ${String(session)} refuses before registry`, async () => {
      const f = fixture(); f.state.session = session; f.state.paramsError = f.error;
      assert.equal(await f.start(), f.errorResponse); assert.deepEqual(f.calls, ["session", "error"]);
      assert.equal(f.seen.errors[0].status, 401); assert.equal(f.seen.errors[0].message, "Authentication required");
      assert.equal(f.seen.arguments.length, 0); assert.equal(f.seen.responses.length, 0);
    });
  }
  for (const mode of ["throw", "reject", "held-reject"]) {
    await t.test(`session ${mode} delegates exact refusal without context access`, async () => {
      const f = fixture(); f.state.paramsError = new Error("UNREACHABLE");
      if (mode === "held-reject") f.state.sessionPending = true;
      else { f.state.sessionError = f.error; f.state.sessionThrows = mode === "throw"; }
      const p = f.start(); if (mode === "held-reject") { await turns(); assert.deepEqual(f.calls, ["session"]); f.sessions.reject(f.error); }
      assert.equal(await p, f.errorResponse); onlyError(f, f.error); assert.deepEqual(f.calls, ["session", "error"]);
    });
  }
  for (const stage of ["namespaces", "config", "constructor"]) {
    await t.test(`${stage} setup failure is mapped before current or parameters`, async () => {
      const f = fixture(); f.state[stage + "Error"] = f.error;
      assert.equal(await f.start(), f.errorResponse); onlyError(f, f.error);
      const n = stage === "namespaces" ? 2 : stage === "config" ? 3 : 4;
      assert.deepEqual(f.calls, [...prefix.slice(0, n), "error"]); assert.equal(f.seen.currentActors.length, 0);
    });
  }
  await t.test("held current gets exact actor and blocks context until settlement", async () => {
    const f = fixture(); f.state.currentPending = true; f.state.params = f.params.promise;
    const p = f.start(); let settled = false; void p.then(() => { settled = true; });
    await turns(); assert.deepEqual(f.calls, prefix); assert.equal(f.seen.currentActors[0], f.actor); assert.equal(settled, false);
    f.current.resolve({ public: "IGNORED-CURRENT-RESULT" }); await turns();
    assert.deepEqual(f.calls, [...prefix, "params", "params"]); assert.equal(settled, false); assert.equal(f.seen.arguments.length, 0);
    f.params.resolve(f.values); assert.equal(await p, f.response);
    assert.deepEqual(f.calls, [...prefix, "params", "params", "operation", "response"]);
  });
  for (const mode of ["throw", "reject", "held-reject"]) {
    await t.test(`current ${mode} blocks parameters and delegates exact refusal`, async () => {
      const f = fixture(); f.state.paramsError = new Error("UNREACHABLE");
      if (mode === "held-reject") f.state.currentPending = true;
      else { f.state.currentError = f.error; f.state.currentThrows = mode === "throw"; }
      const p = f.start(); if (mode === "held-reject") { await turns(); assert.deepEqual(f.calls, prefix); f.current.reject(f.error); }
      assert.equal(await p, f.errorResponse); onlyError(f, f.error); assert.deepEqual(f.calls, [...prefix, "error"]);
    });
  }
  for (const value of [undefined, null, false, 0]) {
    await t.test(`current settlement value ${String(value)} is ignored`, async () => {
      const f = fixture(); f.state.currentResult = value;
      assert.equal(await f.start(), f.response); assert.equal(f.seen.arguments.length, 1);
      assert.equal(f.seen.arguments[0][1], f.actor);
    });
  }
  await t.test("successful operation receives exact registry actor request and resolved record", async () => {
    const f = fixture(); assert.equal(await f.start(), f.response);
    assert.equal(f.seen.arguments.length, 1); const args = f.seen.arguments[0];
    assert.equal(args[0], f.seen.registries[0]); assert.equal(args[1], f.actor);
    assert.equal(args[2], f.request); assert.equal(args[3], f.values);
    assert.equal(f.seen.responses[0][0], f.result); assert.equal(f.seen.responses[0][1], 200);
    assert.deepEqual(f.calls, [...prefix, "params", "params", "operation", "response"]);
  });
  for (const ctx of [undefined, null, {}, { params: null }, { params: undefined }]) {
    await t.test(`absent parameter model ${JSON.stringify(ctx)} delegates empty record`, async () => {
      const f = fixture(); assert.equal(await f.wrap()(f.request, ctx), f.response);
      assert.equal(JSON.stringify(f.seen.arguments[0][3]), "{}");
      assert.deepEqual(f.calls, [...prefix, "operation", "response"]);
    });
  }
  await t.test("empty parameter defaults are new for each invocation", async () => {
    const f = fixture(), handler = f.wrap(); await handler(f.request, {}); await handler(f.request, {});
    assert.notEqual(f.seen.arguments[0][3], f.seen.arguments[1][3]);
  });
  await t.test("plain parameter record is awaited and passed by identity", async () => {
    const f = fixture(); f.state.params = f.values; assert.equal(await f.start(), f.response);
    assert.equal(f.seen.arguments[0][3], f.values);
  });
  await t.test("parameter getter throw occurs after current and before operation", async () => {
    const f = fixture(); f.state.paramsError = f.error; assert.equal(await f.start(), f.errorResponse);
    onlyError(f, f.error); assert.deepEqual(f.calls, [...prefix, "params", "error"]);
  });
  await t.test("deferred parameter rejection is mapped without operation or response", async () => {
    const f = fixture(); f.state.params = f.params.promise; const p = f.start(); await turns();
    assert.deepEqual(f.calls, [...prefix, "params", "params"]); f.params.reject(f.error);
    assert.equal(await p, f.errorResponse); onlyError(f, f.error);
  });
  await t.test("held operation delays response and returns exact eventual identity", async () => {
    const f = fixture(); f.state.operationPending = true; const p = f.start(); await turns();
    assert.deepEqual(f.calls, [...prefix, "params", "params", "operation"]); assert.equal(f.seen.responses.length, 0);
    f.operation.resolve(f.result); assert.equal(await p, f.response); assert.equal(f.seen.responses[0][0], f.result);
  });
  for (const mode of ["throw", "reject", "held-reject"]) {
    await t.test(`operation ${mode} delegates exact error`, async () => {
      const f = fixture(); if (mode === "held-reject") f.state.operationPending = true;
      else { f.state.operationError = f.error; f.state.operationThrows = mode === "throw"; }
      const p = f.start(); if (mode === "held-reject") { await turns(); assert.equal(f.seen.responses.length, 0); f.operation.reject(f.error); }
      assert.equal(await p, f.errorResponse); assert.equal(f.seen.arguments.length, 1);
      assert.equal(f.seen.responses.length, 0); assert.equal(f.seen.errors[0], f.error);
    });
  }
  for (const value of [false, 0, "", { public: "EXACT-RESULT" }]) {
    await t.test(`non-nullish result ${JSON.stringify(value)} preserves identity`, async () => {
      const f = fixture(); f.state.result = value; assert.equal(await f.start(), f.response);
      assert.equal(f.seen.responses[0][0], value);
    });
  }
  for (const value of [null, undefined]) {
    await t.test(`nullish result ${String(value)} gets success default`, async () => {
      const f = fixture(); f.state.result = value; assert.equal(await f.start(), f.response);
      assert.equal(JSON.stringify(f.seen.responses[0][0]), '{"success":true}');
    });
  }
  await t.test("success defaults are newly allocated per invocation", async () => {
    const f = fixture(), handler = f.wrap(); f.state.result = null; await handler(f.request, f.context); await handler(f.request, f.context);
    assert.notEqual(f.seen.responses[0][0], f.seen.responses[1][0]);
  });
  for (const status of [201, 202, 204]) {
    await t.test(`explicit response status ${status} is delegated exactly`, async () => {
      const f = fixture(); assert.equal(await f.wrap(status)(f.request, f.context), f.response);
      assert.equal(f.seen.responses[0][0], f.result); assert.equal(f.seen.responses[0][1], status);
    });
  }
  await t.test("response model throw is delegated to error mapper", async () => {
    const f = fixture(); f.state.responseError = f.error; assert.equal(await f.start(), f.errorResponse);
    assert.equal(f.seen.responses.length, 1); assert.equal(f.seen.errors[0], f.error);
    assert.deepEqual(f.calls.slice(-2), ["response", "error"]);
  });
  await t.test("mapper failure rejects with its exact error without recursion", async () => {
    const f = fixture(); f.state.currentError = f.error; const mapperError = new Error("PUBLIC-MAPPER-FAILURE");
    f.state.errorResponseError = mapperError; await assert.rejects(f.start(), e => e === mapperError);
    assert.equal(f.calls.filter(x => x === "error").length, 1); assert.equal(f.seen.arguments.length, 0);
  });
  for (const value of [null, undefined, "PUBLIC-THROWN-STRING"]) {
    await t.test(`unknown thrown value ${String(value)} delegates unchanged`, async () => {
      const f = fixture(); f.state.operationPending = true; const p = f.start(); await turns(); f.operation.reject(value);
      assert.equal(await p, f.errorResponse); assert.equal(f.seen.errors.length, 1); assert.equal(f.seen.errors[0], value);
    });
  }
  await t.test("mutation error delegates fixed fields and its status through response model", async () => {
    const f = fixture(), error = new f.InertMutationError(409, "PUBLIC-CONFLICT", "PUBLIC-OP", "unknown");
    f.state.operationError = error; assert.equal(await f.start(), f.response); assert.equal(f.seen.errors.length, 0);
    assert.equal(JSON.stringify(f.seen.responses[0][0]), '{"error":"PUBLIC-CONFLICT","operationId":"PUBLIC-OP","outcome":"unknown"}');
    assert.equal(f.seen.responses[0][1], 409);
  });
  await t.test("same handler refreshes session registry and actor for every call", async () => {
    const f = fixture(), handler = f.wrap(), other = { id: "PUBLIC-SECOND", sessionVersion: 8 };
    await handler(f.request, f.context); f.state.session = other; await handler(f.request, f.context);
    assert.equal(f.calls.filter(x => x === "session").length, 2); assert.equal(f.calls.filter(x => x === "current").length, 2);
    assert.notEqual(f.seen.registries[0], f.seen.registries[1]);
    assert.equal(f.seen.currentActors[0], f.actor); assert.equal(f.seen.currentActors[1], other);
    assert.equal(f.seen.arguments[0][1], f.actor); assert.equal(f.seen.arguments[1][1], other);
  });
  await t.test("later missing session refuses without reusing earlier success", async () => {
    const f = fixture(), handler = f.wrap(); await handler(f.request, f.context); f.state.session = null;
    assert.equal(await handler(f.request, f.context), f.errorResponse); assert.equal(f.seen.arguments.length, 1);
    assert.equal(f.seen.registries.length, 1); assert.equal(f.seen.errors[0].status, 401);
  });
  await t.test("later current refusal blocks a previously successful handler", async () => {
    const f = fixture(), handler = f.wrap(); await handler(f.request, f.context); f.state.currentError = f.error;
    assert.equal(await handler(f.request, f.context), f.errorResponse); assert.equal(f.seen.arguments.length, 1);
    assert.equal(f.seen.registries.length, 2); assert.equal(f.seen.errors[0], f.error);
  });
  await t.test("same-handler concurrent calls retain captured actors across held current", async () => {
    const f = fixture(), handler = f.wrap(), other = { id: "PUBLIC-CONCURRENT", sessionVersion: 9 };
    f.state.currentPending = true; const first = handler(f.request, f.context); await turns();
    assert.equal(f.seen.arguments.length, 0); f.state.session = other; f.state.currentPending = false;
    const second = handler(f.request, f.context); assert.equal(await second, f.response);
    assert.equal(f.seen.arguments[0][1], other); f.current.resolve(); assert.equal(await first, f.response);
    assert.equal(f.seen.arguments[1][1], f.actor); assert.notEqual(f.seen.arguments[0][0], f.seen.arguments[1][0]);
  });
  await t.test("independent held and refused models do not release each other", async () => {
    const a = fixture(), b = fixture(); a.state.currentPending = true; b.state.currentError = b.error;
    const first = a.start(); assert.equal(await b.start(), b.errorResponse); await turns();
    assert.deepEqual(a.calls, prefix); assert.equal(a.seen.arguments.length, 0);
    a.current.resolve(); assert.equal(await first, a.response); assert.equal(b.seen.arguments.length, 0);
  });
});
