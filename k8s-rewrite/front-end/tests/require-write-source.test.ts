import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

// PUBLIC SOURCE only: requireAccess is inert. No auth/account/response implementation runs.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);
assert.equal(process.version, "v24.18.0");
const raw = readFileSync(fileURLToPath(new URL("../src/lib/permissions.ts", import.meta.url)), "utf8");
const source = raw.replaceAll("\r\n", "\n");
assert.ok(raw === source || raw === source.replaceAll("\n", "\r\n"));
assert.equal(createHash("sha256").update(source).digest("hex"), "c894d04fa4cbcfaa09e97f1248100b671b29927b13950a4e964b0135a994b704");
const ast = ts.createSourceFile("permissions.ts", source, ts.ScriptTarget.Latest, true);
const declarations = ast.statements.filter((n: { name?: { text: string } }) => ts.isFunctionDeclaration(n) && n.name?.text === "requireWrite");
assert.equal(declarations.length, 1);
const expected = "export function requireWrite() { return requireAccess(false); }";
assert.equal(declarations[0].getText(ast), expected);
const javascript = ts.transpileModule(expected.replace(/^export /, ""), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
assert.ok(!/\b(?:import|require)\s*\(/.test(javascript));
type Selected = (...args: unknown[]) => unknown;
function load(dependency: unknown): Selected {
  const factory = vm.runInNewContext('(function (requireAccess) { "use strict"; return (' + javascript + '); })', {});
  return factory(dependency);
}
function model(output: unknown) {
  let calls = 0;
  const dependency = function (this: unknown, ...args: unknown[]) {
    assert.equal(this, undefined); assert.equal(args.length, 1); assert.equal(args[0], false); calls++; return output;
  };
  return { selected: load(dependency), count: () => calls };
}
const marker = Object.freeze({ publicMetadata: true });
const typeError = (actual: unknown) => (actual as { name?: string })?.name === "TypeError";
test("exact synchronous zero-parameter declaration delegates once with literal false", () => {
  const m = model(marker); assert.equal(m.selected.name, "requireWrite"); assert.equal(m.selected.length, 0);
  assert.equal(declarations[0].parameters.length, 0); assert.equal(declarations[0].modifiers.length, 1);
  assert.equal(m.selected(), marker); assert.equal(m.count(), 1);
});
for (const [name, output] of [
  ["undefined", undefined], ["null", null], ["false", false], ["true", true], ["zero", 0],
  ["negative zero", -0], ["NaN", NaN], ["infinity", Infinity], ["empty string", ""],
  ["public string", "PUBLIC"], ["bigint", 7n], ["symbol", Symbol("PUBLIC")], ["object", marker],
  ["array", []], ["function", function publicMetadata() {}],
] as const) test("immediate result identity without coercion: " + name, () => {
  const m = model(output); assert.ok(Object.is(m.selected(), output)); assert.equal(m.count(), 1);
});
for (const [name, receiver] of [
  ["undefined", undefined], ["null", null], ["false", false], ["number", 4],
  ["string", "PUBLIC"], ["symbol", Symbol("PUBLIC")], ["object", marker], ["array", []],
] as const) test("caller receiver does not become dependency receiver: " + name, () => {
  const m = model(marker); assert.equal(Reflect.apply(m.selected, receiver, []), marker); assert.equal(m.count(), 1);
});
for (const [name, dependency] of [
  ["undefined", undefined], ["null", null], ["false", false], ["number", 4], ["empty string", ""],
  ["public string", "PUBLIC"], ["bigint", 7n], ["symbol", Symbol("PUBLIC")], ["object", {}], ["array", []],
] as const) test("noncallable inert dependency throws synchronously: " + name, () => {
  assert.throws(() => load(dependency)(), typeError);
});
for (const [name, fault] of [
  ["undefined", undefined], ["null", null], ["false", false], ["zero", 0], ["string", "PUBLIC failure"],
  ["symbol", Symbol("PUBLIC failure")], ["bigint", 9n], ["object", marker],
] as const) test("exact synchronous fault propagates with no wrapper: " + name, () => {
  let calls = 0; let caught = false;
  try { load(() => { calls++; throw fault; })(); assert.fail("dependency fault swallowed"); }
  catch (actual) { caught = true; assert.ok(Object.is(actual, fault)); }
  assert.equal(caught, true); assert.equal(calls, 1);
});
test("caller arguments are ignored and their properties remain unread", () => {
  const poisoned = new Proxy({}, { get() { return assert.fail("caller metadata read"); } });
  const m = model(marker); assert.equal(m.selected(poisoned, true, "write"), marker); assert.equal(m.count(), 1);
});
test("account and response-shaped result metadata remain entirely inert", () => {
  const output = new Proxy({ id: "PUBLIC", role: "readonly", status: 403 }, {
    get() { return assert.fail("result property read"); }, ownKeys() { return assert.fail("result enumeration"); },
    getPrototypeOf() { return assert.fail("result prototype read"); },
  });
  assert.equal(model(output).selected(), output);
});
test("then accessor is not read and thenable is not assimilated", () => {
  const output = { get then() { return assert.fail("then read"); } };
  assert.equal(model(output).selected(), output);
});
test("callable proxy captures exact one false argument without property access", () => {
  let calls = 0; const target = function () {};
  const dependency = new Proxy(target, {
    get() { return assert.fail("dependency property read"); },
    apply(actualTarget, receiver, args) {
      calls++; assert.equal(actualTarget, target); assert.equal(receiver, undefined);
      assert.equal(args.length, 1); assert.equal(args[0], false); return marker;
    },
  });
  assert.equal(load(dependency)(), marker); assert.equal(calls, 1);
});
test("revoked callable proxy fault propagates synchronously", () => {
  const revocable = Proxy.revocable(function () {}, {}); revocable.revoke();
  assert.throws(() => load(revocable.proxy)(), typeError);
});
test("dependency state changes are observed anew on every call", () => {
  let output: unknown = marker; let calls = 0;
  const selected = load((flag: unknown) => { calls++; assert.equal(flag, false); return output; });
  assert.equal(selected(), marker); output = false; assert.equal(selected(), false);
  output = "PUBLIC"; assert.equal(selected(), "PUBLIC"); assert.equal(calls, 3);
});
test("separate declarations retain their own immediate dependency", () => {
  const a = model(marker), b = model("PUBLIC"); assert.equal(a.selected(), marker);
  assert.equal(b.selected(), "PUBLIC"); assert.equal(a.selected(), marker);
  assert.equal(a.count(), 2); assert.equal(b.count(), 1);
});
test("reentrant immediate calls preserve argument and result identity", () => {
  const events: string[] = []; let inside = false; let selected!: Selected;
  selected = load((flag: unknown) => {
    assert.equal(flag, false); events.push(inside ? "inner" : "outer");
    if (inside) return marker; inside = true;
    const result = selected(); inside = false; return result;
  });
  assert.equal(selected(), marker); assert.deepEqual(events, ["outer", "inner"]);
});
test("pending synthetic Promise is returned by exact identity before settlement", async () => {
  let resolve!: (value: unknown) => void;
  const promise = new Promise<unknown>(yes => { resolve = yes; });
  const selected = model(promise); const result = selected.selected();
  assert.equal(result, promise); assert.equal(selected.count(), 1); resolve(marker);
  assert.equal(await result, marker);
});
test("rejected synthetic Promise is passed through without a new Promise", async () => {
  const fault = Object.freeze({ publicFailure: true });
  const promise = Promise.reject(fault); const selected = model(promise);
  const result = selected.selected(); assert.equal(result, promise);
  await assert.rejects(result as Promise<unknown>, actual => actual === fault); assert.equal(selected.count(), 1);
});

// DISTINCT packaging-integrity control; original52 callbacks unchanged and EXCLUDED.
test("corrected public source package retains all original control bodies and one final newline", () => {
  const self = readFileSync(fileURLToPath(import.meta.url), "utf8");
  const parts = self.split("\n// DISTINCT packaging-integrity control; original52 callbacks unchanged and EXCLUDED.\n");
  assert.equal(parts.length, 2);
  assert.equal(createHash("sha256").update(parts[0]).digest("hex"), "872cd548804420f47e4ba0a2e6af170420e42b28095d0368539838445442bd5a");
  assert.ok(self.endsWith("\n")); assert.ok(!self.endsWith("\n\n"));
  assert.equal(declarations[0].getText(ast), expected);
});
