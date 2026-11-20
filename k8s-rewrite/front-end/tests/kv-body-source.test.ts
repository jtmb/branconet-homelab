import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC source controls. Plain request/reader models, inert schema
// and all imported dependencies, controlled timers; no Request or transport.
type Value = Record<string, any>;
function deferred() {
  let resolve!: (value?: any) => void, reject!: (error: unknown) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const turns = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
const bytes = (value: string) => new Uint8Array(Buffer.from(value, "utf8"));
const file = "src/lib/kv-http.ts";
const compiled = ts.transpileModule(readFileSync(file, "utf8"), { fileName: file,
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
function fixture() {
  const calls: string[] = [], cancel = deferred(), read = deferred();
  const data = { public: "SCHEMA-RESULT" }, timer = { public: "TIMER" };
  const state: Value = { length: null, type: "application/json", noBody: false,
    chunks: [bytes("{}")], pendingRead: false, readError: null, cancelMode: "resolve",
    schemaOK: true, schemaError: null, headerError: null, acquireError: null };
  let index = 0, callback!: () => void, active = false, parsed: unknown;
  class InertError extends Error { constructor(readonly status: number, message: string) { super(message); } }
  const forbidden = () => { throw new Error("UNSELECTED-INERT-DEPENDENCY"); };
  const dependencies: Value = {
    "./auth": { getSession: forbidden }, "./db": {},
    "./kv-registry": { KvRegistry: forbidden },
    "./kv-contract": { KV_BODY_BYTES: 512 * 1024, KV_ADMIN_METADATA_BODY_BYTES: 3 * 1024 * 1024,
      KvError: InertError, KvMutationError: InertError, kvConfig: forbidden },
    "./kv-native-engine": { KvNativeEngine: forbidden },
    "./secret-client": { createSecretTransport: forbidden, secretNamespaces: forbidden },
    "./secret-references": { listAliases: forbidden },
    "./secret-http": { secretErrorResponse: forbidden, secretResponse: forbidden },
  };
  const reader = {
    read: () => { calls.push("read"); if (state.readError) throw state.readError;
      if (state.pendingRead) return read.promise;
      return Promise.resolve(index < state.chunks.length ? { done: false, value: state.chunks[index++] } : { done: true }); },
    cancel: () => { calls.push("cancel");
      return state.cancelMode === "pending" ? cancel.promise : state.cancelMode === "reject" ? Promise.reject(new Error("PUBLIC-CANCEL-FAILURE")) : Promise.resolve(); },
    releaseLock: () => { calls.push("release"); },
  };
  const request = {
    headers: { get: (name: string) => { calls.push(name); if (state.headerError) throw state.headerError;
      assert(["content-length", "content-type"].includes(name)); return name === "content-length" ? state.length : state.type; } },
    get body() { calls.push("body"); return state.noBody ? null : { getReader: () => {
      calls.push("acquire"); if (state.acquireError) throw state.acquireError; return reader;
    } }; },
  };
  const schema = { safeParse: (value: unknown) => { calls.push("schema"); parsed = value;
    if (state.schemaError) throw state.schemaError;
    return state.schemaOK ? { success: true, data } : { success: false, error: "PUBLIC-UNEXPOSED-SCHEMA-DETAIL" }; } };
  const m = { exports: {} as Value };
  runInNewContext(compiled, { module: m, exports: m.exports, Buffer, TextDecoder,
    require: (name: string) => { assert(Object.hasOwn(dependencies, name)); return dependencies[name]; },
    setTimeout: (fn: () => void, ms: number) => { calls.push("timer"); assert.equal(ms, 20000); callback = fn; active = true; return timer; },
    clearTimeout: (id: unknown) => { calls.push("clear"); assert.equal(id, timer); active = false; },
  }, { filename: file, timeout: 5000 });
  assert.deepEqual(calls, []);
  return { calls: calls as string[], state, data, cancel, read, reader, parsed: () => parsed,
    start: (maximum?: number) => m.exports.kvBody(request, schema, maximum) as Promise<unknown>,
    expire: () => { assert(active); callback(); }, active: () => active };
}
async function refusal(f: ReturnType<typeof fixture>, status: number, message: string, maximum?: number) {
  await assert.rejects(f.start(maximum), (e: any) => e.status === status && e.message === message);
  assert(!f.calls.includes("schema"));
}
function cleaned(f: ReturnType<typeof fixture>) {
  assert.deepEqual(f.calls.slice(-2), ["clear", "release"]);
  assert.equal(f.calls.filter(x => x === "release").length, 1); assert.equal(f.active(), false);
}
const limit = "KV request exceeds the body limit";
test("kvBody bounded plain-reader source contract", async t => {
  for (const length of ["", "-1", "+1", "1.0", " 2", "2 ", "1e3", "Infinity", "NaN", "٢", "524289", "9".repeat(320)]) {
    await t.test(`declared length refusal ${JSON.stringify(length)}`, async () => {
      const f = fixture(); f.state.length = length; await refusal(f, 413, limit);
      assert.deepEqual(f.calls, ["content-length"]);
    });
  }
  for (const type of [null, "text/plain", "application/jsonp", "application/problem+json", ""]) {
    await t.test(`media type refuses ${JSON.stringify(type)} before acquisition`, async () => {
      const f = fixture(); f.state.type = type; await refusal(f, 400, "JSON request body required");
      assert(!f.calls.includes("acquire")); assert(!f.calls.includes("timer"));
    });
  }
  await t.test("missing body refuses before reader acquisition", async () => {
    const f = fixture(); f.state.noBody = true; await refusal(f, 400, "JSON request body required");
    assert(!f.calls.includes("acquire")); assert(!f.calls.includes("timer"));
  });
  for (const key of ["headerError", "acquireError"]) {
    await t.test(`${key} propagates before timer and lock ownership`, async () => {
      const f = fixture(), error = new Error("PUBLIC-PRE-READER"); f.state[key] = error;
      await assert.rejects(f.start(), e => e === error); assert(!f.calls.includes("timer")); assert(!f.calls.includes("release"));
    });
  }
  for (const length of [null, "0", "0002", "2"]) {
    await t.test(`accepted header ${JSON.stringify(length)} delegates exact parsed input and result`, async () => {
      const f = fixture(); f.state.length = length; f.state.type = " Application/JSON ; charset=utf-8";
      assert.equal(await f.start(), f.data); assert.equal(JSON.stringify(f.parsed()), "{}"); cleaned(f);
      assert(!f.calls.includes("cancel")); assert.equal(f.calls.filter(x => x === "schema").length, 1);
    });
  }
  for (const size of [512 * 1024, 512 * 1024 + 1]) {
    await t.test(`streamed default boundary ${size} bytes`, async () => {
      const f = fixture(); f.state.chunks = [bytes('"' + "p".repeat(size - 2) + '"')];
      if (size === 512 * 1024) { assert.equal(await f.start(), f.data); assert.equal((f.parsed() as string).length, size - 2); }
      else { await refusal(f, 413, limit); assert(f.calls.includes("cancel")); }
      cleaned(f);
    });
  }
  await t.test("declared length never substitutes for actual byte count", async () => {
    const f = fixture(); f.state.length = "2"; f.state.chunks = [bytes("{} ")];
    await refusal(f, 413, limit, 2); cleaned(f);
  });
  for (const maximum of [4, 3]) {
    await t.test(`UTF8 byte accounting with explicit maximum ${maximum}`, async () => {
      const f = fixture(); f.state.chunks = [bytes('"é"')];
      if (maximum === 4) { assert.equal(await f.start(maximum), f.data); assert.equal(f.parsed(), "é"); }
      else await refusal(f, 413, limit, maximum);
      cleaned(f);
    });
  }
  for (const count of [4096, 4097]) {
    await t.test(`empty chunks still count at ${count} boundary`, async () => {
      const f = fixture(); f.state.chunks = [...Array.from({ length: count - 1 }, () => new Uint8Array()), bytes("{}")];
      if (count === 4096) assert.equal(await f.start(), f.data); else await refusal(f, 413, limit);
      cleaned(f);
    });
  }
  for (const value of ["", "{", "{}{}", "undefined", "[1,]", "\u0000{}"] ) {
    await t.test(`malformed JSON refuses fixed error ${JSON.stringify(value)}`, async () => {
      const f = fixture(); f.state.chunks = [bytes(value)]; await refusal(f, 400, "Invalid KV JSON body"); cleaned(f);
    });
  }
  for (const value of [[0xc0, 0xaf], [0x22, 0xc3, 0x22], [0x22, 0xf0, 0x9f], [0xff], [0xed, 0xa0, 0x80]]) {
    await t.test(`fatal UTF8 refuses ${value.join("-")}`, async () => {
      const f = fixture(); f.state.chunks = [new Uint8Array(value)]; await refusal(f, 400, "Invalid KV JSON body"); cleaned(f);
    });
  }
  await t.test("split UTF8 code point is decoded only after assembly", async () => {
    const f = fixture(); f.state.chunks = [new Uint8Array([0x22, 0xc3]), new Uint8Array([0xa9, 0x22])];
    assert.equal(await f.start(), f.data); assert.equal(f.parsed(), "é"); cleaned(f);
  });
  for (const value of ["null", "true", "7", '"public"', "[]", '{"public":1}']) {
    await t.test(`JSON shape ${value} is delegated to inert schema`, async () => {
      const f = fixture(); f.state.chunks = [bytes(value)]; assert.equal(await f.start(), f.data);
      assert.equal(JSON.stringify(f.parsed()), value); cleaned(f);
    });
  }
  await t.test("schema failure returns fixed error and cleans owned reader", async () => {
    const f = fixture(); f.state.schemaOK = false;
    await assert.rejects(f.start(), (e: any) => e.status === 400 && e.message === "Invalid KV request fields"); cleaned(f);
  });
  await t.test("schema throw propagates without returned data", async () => {
    const f = fixture(), error = new Error("PUBLIC-SCHEMA-THROW"); f.state.schemaError = error;
    await assert.rejects(f.start(), e => e === error); cleaned(f);
  });
  for (const pending of [false, true]) {
    await t.test(`${pending ? "rejected" : "throwing"} read clears timer and lock`, async () => {
      const f = fixture(), error = new Error("PUBLIC-READ-REFUSAL"); f.state.pendingRead = pending;
      if (!pending) f.state.readError = error;
      const p = f.start(); if (pending) f.read.reject(error);
      await assert.rejects(p, e => e === error); cleaned(f); assert(!f.calls.includes("schema"));
    });
  }
  for (const cancelMode of ["resolve", "pending", "reject"]) {
    await t.test(`deadline refuses 408 independently of ${cancelMode} cancellation`, async () => {
      const f = fixture(); f.state.pendingRead = true; f.state.cancelMode = cancelMode;
      const p = f.start(); await turns(); assert(!f.calls.includes("schema")); f.expire();
      await assert.rejects(p, (e: any) => e.status === 408 && e.message === "KV request body timed out");
      assert.deepEqual(f.calls.slice(-3), ["cancel", "clear", "release"]); cleaned(f);
      f.cancel.resolve(); f.read.resolve({ done: true }); await turns(); assert(!f.calls.includes("schema"));
    });
  }
  for (const cancelMode of ["pending", "reject"]) {
    await t.test(`overflow preserves immediate 413 despite ${cancelMode} cancellation`, async () => {
      const f = fixture(); f.state.chunks = [bytes("{} ")]; f.state.cancelMode = cancelMode;
      let observed: any; const p = f.start(2).then(v => { observed = { value: v }; }, e => { observed = e; });
      await turns();
      try { assert.equal(observed?.status, 413); assert.equal(observed?.message, limit); cleaned(f);
        assert(!f.calls.includes("schema")); assert.equal(f.calls.filter(x => x === "cancel").length, 1);
      } finally { f.cancel.resolve(); await p; }
    });
  }
});
