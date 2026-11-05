import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import type * as TypeScript from "typescript";

// Only the selected declaration is evaluated. Real module imports stay inert.
const compilerPath = process.env.BORTUS_SOURCE_TYPESCRIPT;
assert.ok(compilerPath, "a frozen compiler path is required");
const ts = createRequire(import.meta.url)(compilerPath) as typeof TypeScript;
const text = readFileSync(new URL("../src/lib/kv-contract.ts", import.meta.url), "utf8");
const file = ts.createSourceFile("kv-contract.ts", text, ts.ScriptTarget.Latest, true);
const selected = file.statements.filter((node): node is TypeScript.FunctionDeclaration =>
  ts.isFunctionDeclaration(node) && node.name?.text === "requireGuarded");
assert.equal(selected.length, 1);
assert.ok(selected[0].modifiers?.some(m => m.kind === ts.SyntaxKind.ExportKeyword));
assert.equal(selected[0].parameters.length, 1);
assert.equal(selected[0].parameters[0].type?.getText(file), "KvConfig");
const declaration = selected[0].getText(file).replace(/^export /, "");
const compiled = ts.transpileModule(declaration, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  reportDiagnostics: true,
});
assert.deepEqual(compiled.diagnostics, []);
type Guard = (config: unknown) => undefined;
const makeGuard = (errorBinding: unknown): Guard =>
  new Function("KvError", compiled.outputText + "\nreturn requireGuarded;")(errorBinding) as Guard;
const message = "KV value changes require externally verified guarded adoption";
function fixture() {
  const constructions: unknown[][] = [];
  class InertError {
    status: unknown;
    message: unknown;
    constructor(...args: unknown[]) {
      constructions.push(args);
      this.status = args[0];
      this.message = args[1];
    }
  }
  return { guard: makeGuard(InertError), constructions, InertError };
}
function caught(fn: () => unknown): unknown {
  try { fn(); } catch (error) { return error; }
  assert.fail("expected a synchronous throw");
}
const falsey: [string, unknown][] = [
  ["false", false], ["undefined", undefined], ["null", null], ["positive zero", 0],
  ["negative zero", -0], ["NaN", NaN], ["zero bigint", 0n], ["empty string", ""],
];
const truthy: [string, unknown][] = [
  ["true", true], ["one", 1], ["negative one", -1], ["Infinity", Infinity],
  ["nonzero bigint", 1n], ["false string", "false"], ["zero string", "0"],
  ["whitespace", " "], ["symbol", Symbol("synthetic")], ["object", {}],
  ["array", []], ["function", () => undefined], ["boxed false", Object(false)],
  ["boxed zero", Object(0)], ["boxed empty", Object("")], ["inert promise", Promise.resolve(1)],
];

test("exact requireGuarded source with synthetic configuration and inert errors only", async t => {
  for (const [label, value] of falsey) {
    await t.test("falsey flag refuses: " + label, () => {
      const f = fixture(); const config = Object.freeze({ guardedAdoption: value });
      const error = caught(() => f.guard(config));
      assert.ok(error instanceof f.InertError);
      assert.deepEqual(f.constructions, [[403, message]]);
      assert.equal(error.status, 403); assert.equal(error.message, message);
      assert.deepEqual(config, { guardedAdoption: value });
    });
  }
  for (const [label, value] of truthy) {
    await t.test("truthy synthetic flag returns undefined: " + label, () => {
      const f = fixture(); assert.equal(f.guard(Object.freeze({ guardedAdoption: value })), undefined);
      assert.deepEqual(f.constructions, []);
    });
  }
  for (const value of [null, undefined]) {
    await t.test("nullish argument fails before inert constructor: " + String(value), () => {
      const f = fixture(); assert.ok(caught(() => f.guard(value)) instanceof TypeError);
      assert.deepEqual(f.constructions, []);
    });
  }
  for (const [label, value] of [["number", 1], ["boolean", true], ["string", "synthetic"], ["symbol", Symbol("arg")], ["bigint", 1n]] as const) {
    await t.test("non-null primitive argument has absent flag: " + label, () => {
      const f = fixture(); assert.ok(caught(() => f.guard(value)) instanceof f.InertError);
      assert.deepEqual(f.constructions, [[403, message]]);
    });
  }
  for (const value of [false, true]) {
    await t.test("single inherited nonenumerable getter with original receiver: " + value, () => {
      const f = fixture(); const seen: unknown[] = [];
      const prototype = Object.defineProperty({}, "guardedAdoption", {
        get(this: unknown) { seen.push(this); return value; },
      });
      const config = Object.create(prototype);
      const descriptors = Object.getOwnPropertyDescriptors(config);
      if (value) assert.equal(f.guard(config), undefined);
      else assert.ok(caught(() => f.guard(config)) instanceof f.InertError);
      assert.deepEqual(seen, [config]); assert.deepEqual(Object.getOwnPropertyDescriptors(config), descriptors);
      assert.equal(f.constructions.length, value ? 0 : 1);
    });
    await t.test("proxy permits only exactly one flag get: " + value, () => {
      const f = fixture(); const events: unknown[] = [];
      let config: object;
      config = new Proxy({}, {
        get(target, key, receiver) { events.push([key, receiver === config, target]); return value; },
        has() { assert.fail("has"); }, ownKeys() { assert.fail("ownKeys"); },
        getOwnPropertyDescriptor() { assert.fail("descriptor"); },
        getPrototypeOf() { assert.fail("prototype"); }, set() { assert.fail("set"); },
        defineProperty() { assert.fail("defineProperty"); }, deleteProperty() { assert.fail("delete"); },
      });
      if (value) assert.equal(f.guard(config), undefined);
      else assert.ok(caught(() => f.guard(config)) instanceof f.InertError);
      assert.equal(events.length, 1); assert.deepEqual((events[0] as unknown[]).slice(0, 2), ["guardedAdoption", true]);
    });
  }
  for (const [label, failure] of [["object", {}], ["error", new Error("synthetic")], ["undefined", undefined], ["null", null], ["symbol", Symbol("throw")], ["primitive", 17]] as const) {
    await t.test("flag getter throw identity propagates before constructor: " + label, () => {
      const f = fixture(); let reads = 0;
      assert.equal(caught(() => f.guard({ get guardedAdoption() { reads++; throw failure; } })), failure);
      assert.equal(reads, 1); assert.deepEqual(f.constructions, []);
    });
  }
  await t.test("object flag invokes no coercion or then hooks", () => {
    const f = fixture(); const value = new Proxy({}, { get() { assert.fail("coercion or promise hook"); } });
    assert.equal(f.guard({ guardedAdoption: value }), undefined); assert.deepEqual(f.constructions, []);
  });
  await t.test("revoked flag object remains truthy without trap access", () => {
    const f = fixture(); const r = Proxy.revocable({}, {}); r.revoke();
    assert.equal(f.guard({ guardedAdoption: r.proxy }), undefined); assert.deepEqual(f.constructions, []);
  });
  await t.test("revoked configuration throws before constructor", () => {
    const f = fixture(); const r = Proxy.revocable({}, {}); r.revoke();
    assert.ok(caught(() => f.guard(r.proxy)) instanceof TypeError); assert.deepEqual(f.constructions, []);
  });
  await t.test("absent flag on null prototype refuses", () => {
    const f = fixture(); assert.ok(caught(() => f.guard(Object.create(null))) instanceof f.InertError);
    assert.deepEqual(f.constructions, [[403, message]]);
  });
  await t.test("own flag masks throwing inherited flag", () => {
    const f = fixture(); const config = Object.create({ get guardedAdoption() { return assert.fail("inherited read"); } });
    Object.defineProperty(config, "guardedAdoption", { value: true });
    assert.equal(f.guard(config), undefined);
  });
  await t.test("getter read is not repeated despite changing next result", () => {
    const f = fixture(); let reads = 0;
    const config = { get guardedAdoption() { reads++; return reads === 1; } };
    assert.equal(f.guard(config), undefined); assert.equal(reads, 1);
    assert.ok(caught(() => f.guard(config)) instanceof f.InertError); assert.equal(reads, 2);
  });
  await t.test("fresh calls observe false true false without caching", () => {
    const f = fixture(); const config = { guardedAdoption: false };
    const first = caught(() => f.guard(config)); config.guardedAdoption = true;
    assert.equal(f.guard(config), undefined); config.guardedAdoption = false;
    const last = caught(() => f.guard(config)); assert.notEqual(first, last);
    assert.deepEqual(f.constructions, [[403, message], [403, message]]);
  });
  await t.test("constructor sees exact args and original newTarget after flag read", () => {
    const events: unknown[] = [];
    function ErrorBinding(this: object, ...args: unknown[]) {
      events.push(["construct", args, new.target]);
    }
    const guard = makeGuard(ErrorBinding);
    const config = { get guardedAdoption() { events.push("get"); return false; } };
    const thrown = caught(() => guard(config)); assert.ok(thrown instanceof ErrorBinding);
    assert.deepEqual(events, ["get", ["construct", [403, message], ErrorBinding]]);
  });
  await t.test("constructor explicit object result is thrown without inspection", () => {
    const result = new Proxy({}, { get() { assert.fail("inspect thrown result"); } });
    function ErrorBinding() { return result; }
    assert.equal(caught(() => makeGuard(ErrorBinding)({ guardedAdoption: false })), result);
  });
  await t.test("constructor throw identity propagates unchanged", () => {
    const failure = Symbol("constructor failure");
    function ErrorBinding() { throw failure; }
    assert.equal(caught(() => makeGuard(ErrorBinding)({ guardedAdoption: false })), failure);
  });
  for (const [label, binding] of [["undefined", undefined], ["null", null], ["object", {}], ["arrow", () => undefined]] as const) {
    await t.test("invalid constructor unused on allowed flag: " + label, () => {
      const guard = makeGuard(binding); assert.equal(guard({ guardedAdoption: true }), undefined);
      assert.ok(caught(() => guard({ guardedAdoption: false })) instanceof TypeError);
    });
  }
  await t.test("reentrant getter completes inner refusal then outer success", () => {
    const f = fixture(); const events: string[] = [];
    const config = { get guardedAdoption() {
      events.push("outer get"); assert.ok(caught(() => f.guard({ guardedAdoption: false })) instanceof f.InertError);
      events.push("inner refused"); return true;
    } };
    assert.equal(f.guard(config), undefined); assert.deepEqual(events, ["outer get", "inner refused"]);
    assert.deepEqual(f.constructions, [[403, message]]);
  });
  await t.test("reentrant constructor can invoke an allowed inner call", () => {
    const events: unknown[] = []; let guard: Guard;
    function ErrorBinding(this: object, ...args: unknown[]) {
      events.push(args); assert.equal(guard({ guardedAdoption: true }), undefined);
    }
    guard = makeGuard(ErrorBinding); assert.ok(caught(() => guard({ guardedAdoption: false })) instanceof ErrorBinding);
    assert.deepEqual(events, [[403, message]]);
  });
});
