import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC wrapper-source controls. The administrator, request, reader
// and schema are plain models; every imported implementation remains inert.
type Model = Record<string, any>;
function deferred() {
  let resolve!: (value?: any) => void, reject!: (error: unknown) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const turns = async () => { for (let i = 0; i < 16; i++) await Promise.resolve(); };
const bytes = (text: string) => new Uint8Array(Buffer.from(text, "utf8"));
const file = "src/lib/kv-http.ts";
const compiled = ts.transpileModule(readFileSync(file, "utf8"), { fileName: file,
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
function fixture() {
  const calls: string[] = [], actors: unknown[] = [], gate = deferred(), read = deferred(), cancel = deferred();
  const actor = { id: "PUBLIC-HUMAN", sessionVersion: 7 }, data = { public: "SCHEMA-RESULT" };
  const timer = { public: "TIMER" }, error = new Error("PUBLIC-MODEL-REFUSAL");
  const state: Model = { adminPending: true, adminError: null, adminThrows: false, adminResult: {},
    length: null, type: "application/json", chunks: [bytes("{}")], noBody: false,
    pendingRead: false, readError: null, schemaOK: true, schemaError: null,
    headerError: null, cancelMode: "resolve" };
  let index = 0, active = false, callback!: () => void, parsed: unknown;
  class InertError extends Error { constructor(readonly status: number, message: string) { super(message); } }
  const forbidden = () => { throw new Error("UNSELECTED-INERT-IMPLEMENTATION"); };
  const dependencies: Model = {
    "./auth": { getSession: forbidden }, "./db": {}, "./kv-registry": { KvRegistry: forbidden },
    "./kv-contract": { KV_BODY_BYTES: 512 * 1024, KV_ADMIN_METADATA_BODY_BYTES: 3 * 1024 * 1024,
      KvError: InertError, KvMutationError: InertError, kvConfig: forbidden },
    "./kv-native-engine": { KvNativeEngine: forbidden },
    "./secret-client": { createSecretTransport: forbidden, secretNamespaces: forbidden },
    "./secret-references": { listAliases: forbidden },
    "./secret-http": { secretErrorResponse: forbidden, secretResponse: forbidden },
  };
  const registry = { admin(value: unknown) {
    calls.push("admin"); assert.equal(this, registry); actors.push(value); assert.equal(value, actor);
    if (state.adminThrows) throw state.adminError;
    if (state.adminError) return Promise.reject(state.adminError);
    return state.adminPending ? gate.promise : Promise.resolve(state.adminResult);
  } };
  const reader = {
    read: () => { calls.push("read"); if (state.readError) throw state.readError;
      return state.pendingRead ? read.promise : Promise.resolve(index < state.chunks.length ? { done: false, value: state.chunks[index++] } : { done: true }); },
    cancel: () => { calls.push("cancel"); return state.cancelMode === "pending" ? cancel.promise :
      state.cancelMode === "reject" ? Promise.reject(error) : Promise.resolve(); },
    releaseLock: () => { calls.push("release"); },
  };
  const request = {
    get headers() { calls.push("headers"); return { get: (name: string) => {
      calls.push(name); if (state.headerError) throw state.headerError;
      assert(["content-length", "content-type"].includes(name)); return name === "content-length" ? state.length : state.type;
    } }; },
    get body() { calls.push("body"); return state.noBody ? null : { getReader: () => { calls.push("acquire"); return reader; } }; },
  };
  const schema = { safeParse: (value: unknown) => { calls.push("schema"); parsed = value;
    if (state.schemaError) throw state.schemaError;
    return state.schemaOK ? { success: true, data } : { success: false, error: "PUBLIC-UNEXPOSED-DETAIL" }; } };
  const m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, Buffer, TextDecoder,
    require: (name: string) => { assert(Object.hasOwn(dependencies, name)); return dependencies[name]; },
    setTimeout: (fn: () => void, ms: number) => { calls.push("timer"); assert.equal(ms, 20000); active = true; callback = fn; return timer; },
    clearTimeout: (id: unknown) => { calls.push("clear"); assert.equal(id, timer); active = false; },
  }, { filename: file, timeout: 5000 });
  assert.equal(calls.length, 0);
  return { calls, actors, actor, state, data, error, gate, read, cancel, parsed: () => parsed,
    start: () => m.exports.kvAdminMetadataBody(registry, actor, request, schema) as Promise<unknown>,
    expire: () => { assert(active); callback(); }, active: () => active };
}
function cleaned(f: ReturnType<typeof fixture>) {
  assert.deepEqual(f.calls.slice(-2), ["clear", "release"]); assert.equal(f.active(), false);
  assert.equal(f.calls.filter(x => x === "release").length, 1);
}
async function statusRefusal(p: Promise<unknown>, status: number, message: string) {
  await assert.rejects(p, (e: any) => e.status === status && e.message === message);
}
const maximum = 3 * 1024 * 1024, limit = "KV request exceeds the body limit";
test("kvAdminMetadataBody authorizes before plain-reader delegation", async t => {
  for (const reason of ["missing-account", "changed-session", "readonly", "scoped-writer", "automation-identity", "unavailable"]) {
    await t.test(`pending and rejected administrator model ${reason} consumes nothing`, async () => {
      const f = fixture(), error = Object.assign(new Error("PUBLIC-" + reason), { status: reason === "unavailable" ? 503 : 403 });
      f.state.length = "9".repeat(320); f.state.headerError = f.error;
      const p = f.start(); let settled = false; const rejected = assert.rejects(p, e => e === error).then(() => { settled = true; });
      await turns(); assert.deepEqual(f.calls, ["admin"]); assert.equal(settled, false); assert.equal(f.actors[0], f.actor);
      f.gate.reject(error); await rejected; assert.deepEqual(f.calls, ["admin"]);
    });
  }
  await t.test("synchronous administrator throw also precedes all request access", async () => {
    const f = fixture(); f.state.adminThrows = true; f.state.adminError = f.error;
    await assert.rejects(f.start(), e => e === f.error); assert.deepEqual(f.calls, ["admin"]);
  });
  await t.test("immediate rejected administrator promise never delegates", async () => {
    const f = fixture(); f.state.adminError = f.error;
    await assert.rejects(f.start(), e => e === f.error); assert.deepEqual(f.calls, ["admin"]);
  });
  await t.test("resolved gate delegates exact input and returns schema result identity", async () => {
    const f = fixture(), p = f.start(); await turns(); assert.deepEqual(f.calls, ["admin"]);
    f.gate.resolve({ public: "ADMIN-RESULT-IGNORED" }); assert.equal(await p, f.data);
    assert.equal(f.calls[1], "headers"); assert.equal(JSON.stringify(f.parsed()), "{}");
    assert.equal(f.calls.filter(x => x === "admin").length, 1); assert.equal(f.calls.filter(x => x === "schema").length, 1); cleaned(f);
  });
  for (const result of [undefined, null, false]) {
    await t.test(`authorization uses gate settlement rather than result truthiness ${String(result)}`, async () => {
      const f = fixture(); f.state.adminPending = false; f.state.adminResult = result;
      assert.equal(await f.start(), f.data); cleaned(f);
    });
  }
  for (const size of [512 * 1024 + 1, maximum, maximum + 1]) {
    for (const declared of [false, true]) {
      await t.test(`${declared ? "declared" : "streamed"} metadata delegation boundary ${size}`, async () => {
        const f = fixture(); f.state.adminPending = false;
        f.state.chunks = [bytes('"' + "p".repeat(size - 2) + '"')]; if (declared) f.state.length = String(size);
        if (size <= maximum) { assert.equal(await f.start(), f.data); assert.equal((f.parsed() as string).length, size - 2); cleaned(f); }
        else { await statusRefusal(f.start(), 413, limit); assert(!f.calls.includes("schema"));
          if (declared) assert(!f.calls.includes("acquire")); else cleaned(f); }
        assert.equal(f.calls[0], "admin");
      });
    }
  }
  for (const key of ["headerError", "readError", "schemaError"]) {
    await t.test(`delegated ${key} preserves exact rejection without admin retry`, async () => {
      const f = fixture(); f.state.adminPending = false; f.state[key] = f.error;
      await assert.rejects(f.start(), e => e === f.error); assert.equal(f.calls.filter(x => x === "admin").length, 1);
      if (key !== "headerError") cleaned(f); else assert(!f.calls.includes("acquire"));
    });
  }
  for (const kind of ["media", "missing", "json", "utf8", "schema"]) {
    await t.test(`delegated ${kind} refuses after administrator settlement`, async () => {
      const f = fixture(); f.state.adminPending = false;
      if (kind === "media") f.state.type = "text/plain";
      if (kind === "missing") f.state.noBody = true;
      if (kind === "json") f.state.chunks = [bytes("{")];
      if (kind === "utf8") f.state.chunks = [new Uint8Array([0xff])];
      if (kind === "schema") f.state.schemaOK = false;
      const message = kind === "media" || kind === "missing" ? "JSON request body required" : kind === "schema" ? "Invalid KV request fields" : "Invalid KV JSON body";
      await statusRefusal(f.start(), 400, message); assert.equal(f.calls[0], "admin");
      if (kind !== "media" && kind !== "missing") cleaned(f); else assert(!f.calls.includes("acquire"));
    });
  }
  await t.test("pending delegated read does not resolve wrapper early", async () => {
    const f = fixture(); f.state.adminPending = false; f.state.pendingRead = true;
    let settled = false; const p = f.start().then(value => { settled = true; return value; });
    await turns(); assert.equal(settled, false); assert(f.active()); assert(!f.calls.includes("schema"));
    f.state.pendingRead = false; f.read.resolve({ done: false, value: bytes("{}") }); f.state.chunks = [];
    assert.equal(await p, f.data); cleaned(f);
  });
  await t.test("pending read rejection propagates through wrapper and cleans lock", async () => {
    const f = fixture(); f.state.adminPending = false; f.state.pendingRead = true;
    const p = assert.rejects(f.start(), e => e === f.error); await turns(); f.read.reject(f.error); await p; cleaned(f);
  });
  await t.test("delegated controlled deadline remains fixed408", async () => {
    const f = fixture(); f.state.adminPending = false; f.state.pendingRead = true; f.state.cancelMode = "pending";
    const p = statusRefusal(f.start(), 408, "KV request body timed out"); await turns(); f.expire(); await p;
    assert(f.calls.includes("cancel")); cleaned(f); assert(!f.calls.includes("schema"));
  });
  for (const mode of ["pending", "reject"]) {
    await t.test(`metadata overflow retains qualified kvBody fixed413 with ${mode} cancellation`, async () => {
      const f = fixture(); f.state.adminPending = false; f.state.cancelMode = mode;
      f.state.chunks = [new Uint8Array(maximum + 1)]; let settled = false;
      const p = statusRefusal(f.start(), 413, limit).then(() => { settled = true; });
      await turns(); assert.equal(settled, true); await p; cleaned(f); assert(!f.calls.includes("schema"));
    });
  }
  await t.test("each invocation reenters administrator gate after earlier success", async () => {
    const f = fixture(); f.state.adminPending = false; assert.equal(await f.start(), f.data);
    const before = f.calls.length; f.state.adminError = f.error;
    await assert.rejects(f.start(), e => e === f.error); assert.deepEqual(f.calls.slice(before), ["admin"]); assert.equal(f.actors.length, 2);
  });
  await t.test("a refused invocation does not cache refusal or skip a fresh later gate", async () => {
    const f = fixture(); f.state.adminError = f.error; await assert.rejects(f.start(), e => e === f.error);
    f.state.adminError = null; f.state.adminPending = false; assert.equal(await f.start(), f.data); assert.equal(f.actors.length, 2); cleaned(f);
  });
  await t.test("concurrent independent actor models do not share pending authority", async () => {
    const held = fixture(), ready = fixture(); ready.state.adminPending = false;
    const pending = assert.rejects(held.start(), e => e === held.error);
    assert.equal(await ready.start(), ready.data); assert.deepEqual(held.calls, ["admin"]);
    held.gate.reject(held.error); await pending; assert.deepEqual(held.calls, ["admin"]); cleaned(ready);
  });
});
