import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
import { Buffer as NativeBuffer } from "node:buffer";

// Only this export is compiled. No kv-contract module/import/neighbor executes.
const requireDependency = createRequire(import.meta.url);
const ts = requireDependency(process.env.BORTUS_SOURCE_TYPESCRIPT || "typescript") as typeof import("typescript");
const raw = fs.readFileSync(new URL("../src/lib/kv-contract.ts", import.meta.url), "utf8");
const selected = raw.match(/^export function logicalPath\(value: unknown, allowRoot = false\): string \{[\s\S]*?^\}/m);
assert.ok(selected, "exact named export required");
const compiled = ts.transpileModule(selected[0], { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ESNext } }).outputText;

function fixture(fault = "", nfcMismatch = false, utf8Mismatch = false) {
  const events: string[] = [];
  const sentinel = new Error("synthetic builtin refusal");
  const hit = (stage: string) => { events.push(stage); if (fault === stage) throw sentinel; };
  class InertKvError extends Error {
    status: number;
    constructor(status: number, message: string) { hit("error:new"); super(message); this.status = status; }
  }
  const bufferFacade = Object.defineProperty({}, "from", { get() {
    hit("buffer:get");
    return (value: string) => {
      hit("buffer:call");
      return Object.defineProperty({}, "toString", { get() {
        hit("utf8:get");
        return (encoding: string) => { hit("utf8:call"); assert.equal(encoding, "utf8"); return utf8Mismatch ? "synthetic mismatch" : NativeBuffer.from(value).toString("utf8"); };
      } });
    };
  } });
  const sandbox = { exports: {}, Buffer: bufferFacade, hit, nfcMismatch, InertKvError };

  const context = vm.createContext(sandbox);
  vm.runInContext(`
    const KvError = InertKvError;
    const normalizeOriginal = String.prototype.normalize;
    const splitOriginal = String.prototype.split;
    const regexOriginal = RegExp.prototype.test;
    const someOriginal = Array.prototype.some;
    Object.defineProperty(String.prototype, 'normalize', { configurable: true, get() {
      hit('normalize:get'); return function(form) { hit('normalize:call'); if (form !== 'NFC') throw Error('wrong normalization'); return nfcMismatch ? 'synthetic mismatch' : normalizeOriginal.call(this, form); };
    }});
    Object.defineProperty(String.prototype, 'split', { configurable: true, get() {
      hit('split:get'); return function(separator) { hit('split:call'); if (separator !== '/') throw Error('wrong separator'); return splitOriginal.call(this, separator); };
    }});
    Object.defineProperty(RegExp.prototype, 'test', { configurable: true, get() {
      hit('regex:get'); return function(value) { hit('regex:call'); return regexOriginal.call(this, value); };
    }});
    Object.defineProperty(Array.prototype, 'some', { configurable: true, get() {
      hit('some:get'); return function(callback) { hit('some:call'); return someOriginal.call(this, (segment, index) => { hit('segment:' + index); return callback(segment); }); };
    }});
  `, context);
  vm.runInContext(compiled, context);
  const fn = (sandbox.exports as { logicalPath: (value: unknown, allowRoot?: boolean) => string }).logicalPath;
  const call = (value: unknown, allowRoot?: boolean) => fn(value, allowRoot);
  return { call, events, sentinel, InertKvError };
}

const checked = ["normalize:get", "normalize:call", "regex:get", "regex:call", "buffer:get", "buffer:call", "utf8:get", "utf8:call"];
const segmented = [...checked, "split:get", "split:call", "some:get", "some:call"];
function denied(value: unknown, allowRoot = false) {
  const f = fixture();
  assert.throws(() => f.call(value, allowRoot), (e: unknown) => e instanceof f.InertKvError && e.status === 400 && e.message === "Invalid logical path");
  assert.deepEqual(f.events.slice(-1), ["error:new"]);
  return f;
}

for (const [name, value] of [["undefined", undefined], ["null", null], ["false", false], ["true", true], ["zero", 0], ["NaN", NaN], ["bigint", 1n], ["symbol", Symbol("synthetic")]] as const) {
  test(`non-string ${name} rejects without builtin access`, () => assert.deepEqual(denied(value).events, ["error:new"]));
}
for (const [name, value] of [
  ["one", "api"], ["slash", "apps/api"], ["NFC", "caf\u00e9/api"], ["astral", "apps/\ud83d\ude00"],
  ["dotfile", ".env"], ["three dots", "..."], ["internal dots", "v1.2/service"], ["case", "Apps/API"],
  ["C1", "app\u0080"], ["nonbreaking space", "app\u00a0"], ["segment128", "x".repeat(128)],
  ["astral128units", "\ud83d\ude00".repeat(64)], ["32segments", Array(32).fill("a").join("/")],
  ["512units", ["a".repeat(128), ...Array(3).fill("b".repeat(127))].join("/")],
] as const) {
  test(`valid ${name} returns exact input`, () => { const f = fixture(); assert.equal(f.call(value), value); assert.equal(f.events.includes("error:new"), false); });
}
for (const [name, value] of [
  ["empty", ""], ["leading slash", "/api"], ["trailing slash", "api/"], ["empty segment", "api//key"],
  ["dot", "."], ["dotdot", ".."], ["internal dot", "api/./key"], ["internal dotdot", "api/../key"],
  ["percent", "a%2Fb"], ["backslash", "a\\b"], ["NUL", "a\u0000b"], ["tab", "a\tb"],
  ["newline", "a\nb"], ["space", "a b"], ["DEL", "a\u007fb"], ["decomposed", "cafe\u0301"],
  ["lone high surrogate", "a\ud800"], ["lone low surrogate", "a\udfff"],
  ["segment129", "x".repeat(129)], ["astral130units", "\ud83d\ude00".repeat(65)],
  ["33segments", Array(33).fill("a").join("/")], ["513units", ["a".repeat(128), "b".repeat(128), ...Array(2).fill("c".repeat(127))].join("/")],
] as const) { test(`invalid ${name} refuses fixed400`, () => { denied(value); }); }

test("overlength stops before normalize", () => assert.deepEqual(denied("x".repeat(513)).events, ["error:new"]));
test("NFC mismatch stops before regex", () => assert.deepEqual(denied("e\u0301").events, [...checked.slice(0, 2), "error:new"]));
test("regex refusal stops before Buffer", () => assert.deepEqual(denied("a%b").events, [...checked.slice(0, 4), "error:new"]));
test("malformed UTF8 roundtrip stops before split", () => assert.deepEqual(denied("a\ud800").events, [...checked, "error:new"]));
test("default and explicitfalse empty refuse after builtin checks", () => {
  for (const root of [undefined, false]) { const f = fixture(); assert.throws(() => f.call("", root), f.InertKvError); assert.deepEqual(f.events, [...checked, "error:new"]); }
});
test("allowRoot empty returns after checks without split", () => { const f = fixture(); assert.equal(f.call("", true), ""); assert.deepEqual(f.events, checked); });
test("allowRoot never bypasses nonempty validation", () => { for (const value of ["/", "a%", "a/..", "x".repeat(513)]) denied(value, true); });
test("segmentcount refuses before some", () => assert.deepEqual(denied(Array(33).fill("a").join("/")).events, [...checked, "split:get", "split:call", "error:new"]));
test("some visits segments left-to-right and shortcircuits", () => assert.deepEqual(denied("ok/../later").events, [...segmented, "segment:0", "segment:1", "error:new"]));
test("success visits all segments after both builtin chains", () => { const f = fixture(); assert.equal(f.call("a/b/c"), "a/b/c"); assert.deepEqual(f.events, [...segmented, "segment:0", "segment:1", "segment:2"]); });
test("inert builtin NFC mismatch is respected", () => { const f = fixture("", true); assert.throws(() => f.call("a"), f.InertKvError); assert.deepEqual(f.events, [...checked.slice(0, 2), "error:new"]); });
test("inert builtin UTF8 mismatch is respected", () => { const f = fixture("", false, true); assert.throws(() => f.call("a"), f.InertKvError); assert.deepEqual(f.events, [...checked, "error:new"]); });
for (const [i, stage] of [...segmented, "segment:0"].entries()) {
  test(`builtin refusal ${stage} propagates unchanged and stops`, () => {
    const f = fixture(stage); assert.throws(() => f.call("a/b"), e => e === f.sentinel);
    assert.deepEqual(f.events, [...segmented, "segment:0"].slice(0, i + 1));
  });
}
test("refusals create fresh fixed errors from direct inert binding", () => { const f = fixture(); const errors: unknown[] = []; for (let i = 0; i < 2; i++) { try { f.call(null); } catch (e) { errors.push(e); } } assert.equal(errors.length, 2); assert.notEqual(errors[0], errors[1]); assert.ok(errors.every(e => e instanceof f.InertKvError && e.status === 400 && e.message === "Invalid logical path")); assert.deepEqual(f.events, ["error:new", "error:new"]); });
test("error constructor invocation refusal propagates unchanged", () => { const f = fixture("error:new"); assert.throws(() => f.call(null), e => e === f.sentinel); assert.deepEqual(f.events, ["error:new"]); });
test("fresh calls repeat complete validation after prior success and refusal", () => {
  const f = fixture(); assert.equal(f.call("a"), "a"); assert.throws(() => f.call("a%"), f.InertKvError); f.events.length = 0;
  assert.equal(f.call("b/c"), "b/c"); assert.deepEqual(f.events, [...segmented, "segment:0", "segment:1"]);
});
