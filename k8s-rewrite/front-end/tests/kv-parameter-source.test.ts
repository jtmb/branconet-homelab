import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC source controls. URL/request/error objects are plain models;
// all imports are inert. No HTTP Request, URL decoding, authority, schema or I/O.
type Model = Record<string, any>;
const file = "src/lib/kv-http.ts";
const compiled = ts.transpileModule(readFileSync(file, "utf8"), { fileName: file,
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
function fixture(cursor: string | null = null) {
  const calls: unknown[] = [], ordinary = new Error("PUBLIC-MODEL-FAULT");
  const state: Model = { cursor, urlError: null, constructorError: null, paramsError: null, getError: null };
  const sentinel = { public: "URL-INPUT" };
  class InertError extends Error { constructor(readonly status: number, message: string) { super(message); } }
  class InertMutationError extends InertError {}
  const forbidden = () => { throw new Error("UNSELECTED-DEPENDENCY"); };
  const dependencies: Model = {
    "./auth": { getSession: forbidden }, "./db": { default: {} },
    "./kv-registry": { KvRegistry: forbidden }, "./kv-native-engine": { KvNativeEngine: forbidden },
    "./kv-contract": { KvError: InertError, KvMutationError: InertMutationError,
      KV_BODY_BYTES: 524288, KV_ADMIN_METADATA_BODY_BYTES: 3145728, kvConfig: forbidden },
    "./secret-client": { createSecretTransport: forbidden, secretNamespaces: forbidden },
    "./secret-references": { listAliases: forbidden },
    "./secret-http": { secretResponse: forbidden, secretErrorResponse: forbidden },
  };
  class PlainURL {
    constructor(value: unknown) {
      calls.push(["URL", value]); assert.equal(value, sentinel);
      if (state.constructorError) throw state.constructorError;
    }
    get searchParams() {
      calls.push("searchParams"); if (state.paramsError) throw state.paramsError;
      return { get: (key: string) => {
        calls.push(["get", key]); assert.equal(key, "cursor");
        if (state.getError) throw state.getError; return state.cursor;
      } };
    }
  }
  const request = new Proxy({}, { get: (_target, key) => {
    assert.equal(key, "url"); calls.push("request.url");
    if (state.urlError) throw state.urlError; return sentinel;
  } });
  const m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, URL: PlainURL,
    require: (name: string) => { assert(Object.hasOwn(dependencies, name)); return dependencies[name]; },
  }, { filename: file, timeout: 5000 });
  assert.deepEqual(calls, []);
  return { state, calls, ordinary, sentinel, InertError, history: m.exports.historyVersion as (raw: string) => number,
    cursor: () => m.exports.metadataCursor(request) as string | undefined };
}
function refusal(invoke: () => unknown, f: ReturnType<typeof fixture>, message: string) {
  assert.throws(invoke, (e: any) => e instanceof f.InertError && e.status === 400 && e.message === message);
}
const validVersions: Array<[string, number]> = [
  ["1", 1], ["9", 9], ["10", 10], ["99", 99], ["100", 100],
  ["999999999999999", 999999999999999], ["1000000000000000", 1000000000000000],
  ["9007199254740990", 9007199254740990], ["9007199254740991", Number.MAX_SAFE_INTEGER],
];
const invalidVersions = ["", "0", "00", "01", "0001", "-1", "+1", "1.0", "1.1", "1e2", "1E2", "0x10", "0b10",
  " 1", "1 ", "\t1", "1\t", "\n1", "1\n", "1\r", "1\r\n", "1\u2028", "1\u2029", "1\u0000", "1_0", "1/2",
  "NaN", "Infinity", "١", "１", "9007199254740992", "9007199254740993", "9999999999999999", "10000000000000000"];
test("historyVersion exact string refusal and safe numeric boundaries", async t => {
  for (const [raw, expected] of validVersions) await t.test(`accept ${raw}`, () => {
    const f = fixture(); assert.equal(f.history(raw), expected); assert.deepEqual(f.calls, []);
  });
  for (let i = 0; i < invalidVersions.length; i++) await t.test(`refuse public case ${i}`, () => {
    const f = fixture(); refusal(() => f.history(invalidVersions[i]), f, "Invalid history version");
    assert.deepEqual(f.calls, []);
  });
  await t.test("repeated valid/refused calls retain no parsed version", () => {
    const f = fixture(); assert.equal(f.history("1"), 1);
    refusal(() => f.history("01"), f, "Invalid history version");
    assert.equal(f.history("9007199254740991"), Number.MAX_SAFE_INTEGER);
    refusal(() => f.history("9007199254740992"), f, "Invalid history version");
    assert.equal(f.history("2"), 2); assert.deepEqual(f.calls, []);
  });
});
const validCursors = ["A", "z", "0", "_", "-", "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-",
  "A".repeat(127), "-".repeat(128)];
const invalidCursors = ["", "A".repeat(129), "A B", " A", "A ", "A+", "A/", "A=", "A.", "A%", "A?", "A#", "A&", "A:",
  "A\n", "A\r", "A\r\n", "A\t", "A\u0000", "A\u2028", "A\u2029", "é", "Ａ", "😀"];
test("metadataCursor exact plain URL/request model delegation and refusals", async t => {
  await t.test("absent cursor returns undefined after one exact URL lookup", () => {
    const f = fixture(); assert.equal(f.cursor(), undefined);
    assert.deepEqual(f.calls, ["request.url", ["URL", f.sentinel], "searchParams", ["get", "cursor"]]);
  });
  for (let i = 0; i < validCursors.length; i++) await t.test(`accept unchanged cursor ${i}`, () => {
    const f = fixture(validCursors[i]); assert.equal(f.cursor(), validCursors[i]);
    assert.deepEqual(f.calls, ["request.url", ["URL", f.sentinel], "searchParams", ["get", "cursor"]]);
  });
  for (let i = 0; i < invalidCursors.length; i++) await t.test(`refuse public cursor ${i}`, () => {
    const f = fixture(invalidCursors[i]); refusal(f.cursor, f, "Invalid metadata cursor");
    assert.deepEqual(f.calls, ["request.url", ["URL", f.sentinel], "searchParams", ["get", "cursor"]]);
  });
  for (const [fault, count] of [["urlError", 1], ["constructorError", 2], ["paramsError", 3], ["getError", 4]] as const) {
    await t.test(`preserve ordinary ${fault} and stop later accesses`, () => {
      const f = fixture(); f.state[fault] = f.ordinary; assert.throws(f.cursor, e => e === f.ordinary);
      assert.equal(f.calls.length, count);
    });
  }
  await t.test("every call retrieves a fresh model cursor after success, absence, refusal and failure", () => {
    const f = fixture("A"); assert.equal(f.cursor(), "A"); f.state.cursor = null; assert.equal(f.cursor(), undefined);
    f.state.cursor = "bad/"; refusal(f.cursor, f, "Invalid metadata cursor");
    f.state.urlError = f.ordinary; assert.throws(f.cursor, e => e === f.ordinary);
    f.state.urlError = null; f.state.cursor = "B_2-"; assert.equal(f.cursor(), "B_2-");
    assert.equal(f.calls.filter(x => x === "request.url").length, 5);
  });
  await t.test("separate fixtures cannot supply another request's cursor", () => {
    const a = fixture("FIRST"), b = fixture("SECOND"); assert.equal(a.cursor(), "FIRST");
    b.state.cursor = "bad/"; refusal(b.cursor, b, "Invalid metadata cursor");
    a.state.cursor = "NEXT"; assert.equal(a.cursor(), "NEXT"); b.state.cursor = null; assert.equal(b.cursor(), undefined);
  });
});
