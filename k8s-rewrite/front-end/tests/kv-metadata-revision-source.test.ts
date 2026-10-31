import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { stripTypeScriptTypes } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";

// Only the selected declaration runs. No production module, import, config or engine runs.
const source = readFileSync(new URL("../src/lib/kv-contract.ts", import.meta.url), "utf8").replaceAll("\r\n", "\n");
const start = source.indexOf("export function metadataRevision(value: unknown): number {");
assert(start >= 0);
const end = source.indexOf("\n}", start) + 2;
assert(end > start);
const declaration = source.slice(start, end);
assert.equal(declaration, [
  "export function metadataRevision(value: unknown): number {",
  '  if (value === undefined || value === null) throw new KvError(428, "Metadata revision required");',
  '  if (!Number.isSafeInteger(value) || Number(value) < 1) throw new KvError(400, "Invalid metadata revision");',
  "  return Number(value);",
  "}",
].join("\n"));
assert.equal(createHash("sha256").update(declaration).digest("hex"), "a9d3e7ee3b48f9b4b0fc7830f088eb7499f57c77cab4ad7bc7c9744a8b7843f2");
const executable = stripTypeScriptTypes(declaration.replace("export ", ""));
type Hooks = {
  safe?: (value: unknown) => unknown;
  convert?: (value: unknown, ordinal: number) => number;
  constructorBinding?: unknown;
  safeGetter?: () => unknown;
};
function fixture(hooks: Hooks = {}) {
  const events: unknown[][] = [];
  let conversions = 0;
  const numeric = Object.assign(function convert(value: unknown): number {
    events.push(["number", value]);
    conversions++;
    return hooks.convert ? hooks.convert(value, conversions) : Number(value);
  }, {
    isSafeInteger(value: unknown): unknown {
      assert.equal(this, numeric);
      events.push(["safe", value]);
      return hooks.safe ? hooks.safe(value) : Number.isSafeInteger(value);
    },
  });
  if (hooks.safeGetter) Object.defineProperty(numeric, "isSafeInteger", { get: hooks.safeGetter });
  class InertError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
      events.push(["error", status, message]);
      assert.equal(new.target, InertError);
    }
  }
  const fn = runInNewContext(`${executable}\nmetadataRevision;`, {
    Number: numeric, KvError: hooks.constructorBinding ?? InertError,
  }, { timeout: 1000 }) as (value?: unknown) => number;
  return { fn, events, InertError };
}
function caught(fn: () => unknown): unknown {
  try { fn(); } catch (error) { return error; }
  return assert.fail("Expected synchronous throw");
}
function refusal(value: unknown, status: number, message: string) {
  const f = fixture();
  const error = caught(() => f.fn(value));
  assert(error instanceof f.InertError);
  assert.equal(error.status, status);
  assert.equal(error.message, message);
  const expected: unknown[][] = [];
  if (value !== undefined && value !== null) {
    expected.push(["safe", value]);
    if (Number.isSafeInteger(value)) expected.push(["number", value]);
  }
  expected.push(["error", status, message]);
  assert.deepEqual(f.events, expected);
}

test("exact metadataRevision finite source controls", async (t) => {
  for (const [name, value] of [["undefined", undefined], ["null", null]] as const) {
    await t.test(`required ${name}`, () => refusal(value, 428, "Metadata revision required"));
  }
  const valid = [1, 2, 3, 9, 42, 65536, 2 ** 32, Number.MAX_SAFE_INTEGER - 1, Number.MAX_SAFE_INTEGER];
  for (const value of valid) {
    await t.test(`positive safe integer ${value}`, () => {
      const f = fixture();
      assert.equal(f.fn(value), value);
      assert.deepEqual(f.events, [["safe", value], ["number", value], ["number", value]]);
    });
  }
  const invalidNumbers = [0, -0, -1, -Number.MAX_SAFE_INTEGER, 0.1, 1.1, Number.MAX_SAFE_INTEGER + 1,
    NaN, Infinity, -Infinity, Number.MIN_VALUE, -Number.MIN_VALUE, Number.MAX_VALUE];
  for (const [index, value] of invalidNumbers.entries()) {
    await t.test(`invalid number ${index}`, () => refusal(value, 400, "Invalid metadata revision"));
  }
  const primitiveCases: [string, unknown][] = [["false", false], ["true", true], ["empty", ""],
    ["digit", "1"], ["zero string", "0"], ["spaced", " 1 "], ["max string", String(Number.MAX_SAFE_INTEGER)],
    ["zero bigint", 0n], ["one bigint", 1n], ["max bigint", BigInt(Number.MAX_SAFE_INTEGER)], ["symbol", Symbol("synthetic")]];
  for (const [name, value] of primitiveCases) {
    await t.test(`non-number primitive ${name}`, () => refusal(value, 400, "Invalid metadata revision"));
  }
  const objects: [string, () => unknown][] = [["object", () => ({})], ["array", () => []], ["singleton", () => [1]],
    ["boxed number", () => Object(1)], ["boxed string", () => Object("1")], ["boxed boolean", () => Object(true)],
    ["date", () => new Date(0)], ["function", () => () => 1], ["null prototype", () => Object.create(null)],
    ["coercion traps", () => ({ [Symbol.toPrimitive]() { return assert.fail("coercion"); }, valueOf() { return assert.fail("valueOf"); }, toString() { return assert.fail("toString"); } })],
    ["then getter", () => ({ get then() { return assert.fail("then read"); } })],
    ["revoked proxy", () => { const p = Proxy.revocable({}, {}); p.revoke(); return p.proxy; }]];
  for (const [name, make] of objects) {
    await t.test(`object refusal without consumption ${name}`, () => refusal(make(), 400, "Invalid metadata revision"));
  }
  await t.test("omitted argument requires revision before builtins", () => {
    const f = fixture(); const error = caught(() => f.fn());
    assert(error instanceof f.InertError); assert.equal(error.status, 428);
    assert.deepEqual(f.events, [["error", 428, "Metadata revision required"]]);
  });
  await t.test("safe-integer builtin failure propagates exact identity", () => {
    const marker = Object.freeze({ failure: "safe" });
    const f = fixture({ safe: () => { throw marker; } });
    assert.equal(caught(() => f.fn(1)), marker); assert.deepEqual(f.events, [["safe", 1]]);
  });
  await t.test("safe-integer property getter failure precedes invocation", () => {
    const marker = Symbol("safe getter");
    const f = fixture({ safeGetter: () => { throw marker; } });
    assert.equal(caught(() => f.fn(1)), marker); assert.deepEqual(f.events, []);
  });
  for (const ordinal of [1, 2]) {
    await t.test(`conversion ${ordinal} failure propagates exact identity`, () => {
      const marker = Object.freeze({ failure: ordinal });
      const f = fixture({ convert: (_value, call) => { if (call === ordinal) throw marker; return 1; } });
      assert.equal(caught(() => f.fn(1)), marker);
      assert.deepEqual(f.events, [["safe", 1], ...Array.from({ length: ordinal }, () => ["number", 1])]);
    });
  }
  await t.test("error constructor failure propagates without a replacement", () => {
    const marker = Object.freeze({ failure: "constructor" });
    const binding = new Proxy(class {}, { construct() { throw marker; } });
    const f = fixture({ constructorBinding: binding });
    assert.equal(caught(() => f.fn(null)), marker); assert.deepEqual(f.events, []);
  });
  await t.test("constructor receives exact args and newTarget", () => {
    const marker = Object.freeze({ error: "inert constructed object" });
    const calls: unknown[][] = [];
    const binding = new Proxy(class {}, { construct(_target, args, newTarget) { calls.push([args, newTarget]); return marker; } });
    const f = fixture({ constructorBinding: binding });
    assert.equal(caught(() => f.fn("1")), marker);
    assert.equal(calls.length, 1);
    const args = calls[0][0] as unknown[];
    assert.equal(args.length, 2);
    assert.equal(args[0], 400);
    assert.equal(args[1], "Invalid metadata revision");
    assert.equal(calls[0][1], binding);
    assert.deepEqual(f.events, [["safe", "1"]]);
  });
  await t.test("repeated successful calls perform every read and conversion", () => {
    const f = fixture(); assert.equal(f.fn(1), 1); assert.equal(f.fn(2), 2);
    assert.deepEqual(f.events, [["safe", 1], ["number", 1], ["number", 1], ["safe", 2], ["number", 2], ["number", 2]]);
  });
  await t.test("repeated refusals construct fresh errors", () => {
    const f = fixture(); const a = caught(() => f.fn(null)); const b = caught(() => f.fn(null));
    assert.notEqual(a, b); assert(a instanceof f.InertError); assert(b instanceof f.InertError);
    assert.deepEqual(f.events, [["error", 428, "Metadata revision required"], ["error", 428, "Metadata revision required"]]);
  });
  await t.test("reentrant builtin call preserves independent argument order", () => {
    let nested = false;
    const f = fixture({ safe: (value) => { if (!nested) { nested = true; assert.equal(f.fn(2), 2); } return Number.isSafeInteger(value); } });
    assert.equal(f.fn(1), 1);
    assert.deepEqual(f.events, [["safe", 1], ["safe", 2], ["number", 2], ["number", 2], ["number", 1], ["number", 1]]);
  });
  await t.test("object proxy receives no get or enumeration or mutation traps", () => {
    const value = new Proxy({}, {
      get() { return assert.fail("get"); }, ownKeys() { return assert.fail("ownKeys"); },
      set() { return assert.fail("set"); }, getPrototypeOf() { return assert.fail("getPrototypeOf"); },
    });
    refusal(value, 400, "Invalid metadata revision");
  });
  await t.test("frozen input remains identical", () => {
    const value = Object.freeze({ synthetic: 1 });
    refusal(value, 400, "Invalid metadata revision"); assert.deepEqual(value, { synthetic: 1 });
  });
  await t.test("synthetic falsey safe result short-circuits conversion", () => {
    const f = fixture({ safe: () => 0 }); const error = caught(() => f.fn(1));
    assert(error instanceof f.InertError); assert.equal(error.status, 400);
    assert.deepEqual(f.events, [["safe", 1], ["error", 400, "Invalid metadata revision"]]);
  });
  await t.test("synthetic negative first conversion refuses before second", () => {
    const f = fixture({ convert: () => -1 }); const error = caught(() => f.fn(1));
    assert(error instanceof f.InertError); assert.equal(error.status, 400);
    assert.deepEqual(f.events, [["safe", 1], ["number", 1], ["error", 400, "Invalid metadata revision"]]);
  });
  await t.test("synthetic conversion return is read a second time", () => {
    const f = fixture({ convert: (_value, ordinal) => ordinal === 1 ? 1 : 17 });
    assert.equal(f.fn(1), 17); assert.deepEqual(f.events, [["safe", 1], ["number", 1], ["number", 1]]);
  });
  await t.test("synthetic NaN comparison characterizes source only", () => {
    const f = fixture({ convert: (_value, ordinal) => ordinal === 1 ? NaN : 19 });
    assert.equal(f.fn(1), 19); assert.deepEqual(f.events, [["safe", 1], ["number", 1], ["number", 1]]);
  });
  await t.test("independent fixtures retain no prior outcome", () => {
    refusal(0, 400, "Invalid metadata revision");
    const f = fixture(); assert.equal(f.fn(3), 3);
    assert.deepEqual(f.events, [["safe", 3], ["number", 3], ["number", 3]]);
  });
});
