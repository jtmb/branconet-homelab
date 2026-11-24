import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { test } from "node:test";
import type TypeScript from "typescript";

// Compile only this selected route. The real import is replaced before evaluation.
const requireTool = createRequire(import.meta.url);
const ts: typeof TypeScript = requireTool(process.env.BORTUS_SOURCE_TYPESCRIPT || "typescript");
const route = "src/app/api/kv/paths/[id]/capabilities/route.ts";
const source = readFileSync(resolve(process.cwd(), route), "utf8");
const ast = ts.createSourceFile(route, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
assert.equal(ast.statements.length, 4);
assert(ts.isImportDeclaration(ast.statements[0]));
assert.equal(ast.statements[0].moduleSpecifier.getText(ast), '"@/lib/kv-http"');
const compiled = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  fileName: route, reportDiagnostics: true,
});
assert.equal(compiled.diagnostics?.length, 0);

type Callback = (registry: any, actor: any, request: any, params: any) => Promise<any>;
type Wrapper = (this: unknown, callback: Callback, ...rest: unknown[]) => unknown;
function evaluate(wrapper?: Wrapper) {
  let selected!: Callback;
  const calls: unknown[][] = [];
  const exports: any = {};
  const imports: string[] = [];
  const kvHuman = function (this: unknown, callback: Callback, ...rest: unknown[]) {
    assert.equal(this, undefined);
    calls.push([callback, ...rest]);
    selected = callback;
    return wrapper ? Reflect.apply(wrapper, this, [callback, ...rest]) : callback;
  };
  const inertRequire = (name: string) => {
    imports.push(name);
    assert.equal(name, "@/lib/kv-http");
    return { kvHuman };
  };
  new Function("require", "exports", compiled.outputText)(inertRequire, exports);
  assert.deepEqual(imports, ["@/lib/kv-http"]);
  assert.equal(exports.runtime, "nodejs");
  assert.equal(exports.dynamic, "force-dynamic");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].length, 1);
  assert.equal(typeof selected, "function");
  return { selected, exports };
}
function unread(label: string): any {
  return new Proxy(Object.create(null), {
    get() { throw new Error(`${label}:get`); },
    has() { throw new Error(`${label}:has`); },
    ownKeys() { throw new Error(`${label}:ownKeys`); },
    getPrototypeOf() { throw new Error(`${label}:prototype`); },
    getOwnPropertyDescriptor() { throw new Error(`${label}:descriptor`); },
  });
}
async function reason(promise: Promise<unknown>, expected: unknown) {
  let rejected = false;
  await promise.then(() => assert.fail("expected rejection"), actual => {
    rejected = true; assert(Object.is(actual, expected));
  });
  assert(rejected);
}
function deferred() {
  let resolve!: (value: any) => void;
  let reject!: (value: any) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const identities: unknown[] = [undefined, null, false, true, 0, -0, NaN, Infinity, "", "a/b", Symbol("id"), {}, [], () => 0];

test("human path-capabilities GET selected source", { concurrency: false }, async t => {
  const selectedNames = new Set([
    "params proxy reads only id; unrelated fields symbols and prototype untouched",
    "registry proxy reads only capabilities and uses original receiver",
  ]);
  const run = async (name: string, body: () => void | Promise<void>) => {
    if (!process.env.BORTUS_SELECTED_SOURCE_ONLY || selectedNames.has(name)) await t.test(name, body);
  };
  for (const [index, marker] of identities.entries()) {
    await run(`wrapper return identity ${index}`, () => {
      const { exports } = evaluate(function () { assert.equal(this, undefined); return marker; });
      assert(Object.is(exports.GET, marker));
    });
  }
  await run("wrapper refusal is module evaluation refusal", () => {
    const marker = {};
    assert.throws(() => evaluate(function () { throw marker; }), error => error === marker);
  });
  await run("selected callback is async, nonconstructable and arity four", () => {
    const { selected } = evaluate();
    assert.equal(selected.length, 4);
    assert.equal(Object.prototype.toString.call(selected), "[object AsyncFunction]");
    assert.throws(() => Reflect.construct(selected, []), TypeError);
  });
  for (const [index, id] of identities.entries()) {
    await run(`exact id forwarding ${index}`, async () => {
      const { selected } = evaluate(); const actor = unread("actor"); const request = unread("request");
      const result = {}; const registry = { capabilities(this: unknown, ...args: unknown[]) {
        assert.equal(this, registry); assert.equal(args.length, 2);
        assert.equal(args[0], actor); assert(Object.is(args[1], id)); return result;
      } };
      assert.equal(await selected(registry, actor, request, { id }), result);
    });
    await run(`exact actor forwarding ${index}`, async () => {
      const { selected } = evaluate(); const id = unread("id"); const result = {};
      const registry = { capabilities(this: unknown, ...args: unknown[]) {
        assert.equal(this, registry); assert.equal(args.length, 2);
        assert(Object.is(args[0], id === null ? null : identities[index]));
        assert.equal(args[1], id); return result;
      } };
      assert.equal(await selected(registry, id === null ? null : identities[index], unread("request"), { id }), result);
    });
  }
  await run("parameter id precedes method capture and synchronous invocation", async () => {
    const order: string[] = []; const id = {}; const actor = {}; const result = {};
    const registry = Object.defineProperty({}, "capabilities", { get() {
      order.push("method"); assert.equal(this, registry);
      return function (this: unknown, a: unknown, i: unknown) { order.push("call"); assert.equal(this, registry); assert.equal(a, actor); assert.equal(i, id); return result; };
    } });
    const params = Object.defineProperty({}, "id", { get() { order.push("id"); assert.equal(this, params); return id; } });
    const p = evaluate().selected(registry, actor, unread("request"), params);
    assert.deepEqual(order, ["id", "method", "call"]);
    assert.equal(await p, result);
  });
  for (const params of [undefined, null]) {
    await run(`nullish parameters refuse before registry ${String(params)}`, async () => {
      const p = evaluate().selected(unread("registry"), unread("actor"), unread("request"), params);
      await assert.rejects(p, TypeError);
    });
  }
  for (const [index, marker] of identities.entries()) {
    await run(`id getter refusal identity ${index}`, async () => {
      const params = Object.defineProperty({}, "id", { get() { throw marker; } });
      await reason(evaluate().selected(unread("registry"), unread("actor"), unread("request"), params), marker);
    });
    await run(`method getter refusal identity ${index}`, async () => {
      const order: string[] = [];
      const params = Object.defineProperty({}, "id", { get() { order.push("id"); return unread("id"); } });
      const registry = Object.defineProperty({}, "capabilities", { get() { order.push("method"); throw marker; } });
      await reason(evaluate().selected(registry, unread("actor"), unread("request"), params), marker);
      assert.deepEqual(order, ["id", "method"]);
    });
    await run(`method synchronous refusal identity ${index}`, async () => {
      const registry = { capabilities() { throw marker; } };
      await reason(evaluate().selected(registry, unread("actor"), unread("request"), { id: unread("id") }), marker);
    });
    await run(`async fulfillment identity ${index}`, async () => {
      assert(Object.is(await evaluate().selected({ capabilities: () => marker }, unread("actor"), unread("request"), {}), marker));
    });
    await run(`async rejection identity ${index}`, async () => {
      const d = deferred(); const p = evaluate().selected({ capabilities: () => d.promise }, null, null, {});
      d.reject(marker); await reason(p, marker);
    });
  }
  for (const [index, value] of [undefined, null, false, 0, "", {}, [], Symbol("method")].entries()) {
    await run(`noncallable method ${index}`, async () => {
      let reads = 0;
      const params = Object.defineProperty({}, "id", { get() { reads++; return unread("id"); } });
      await assert.rejects(evaluate().selected({ capabilities: value }, unread("actor"), unread("request"), params), TypeError);
      assert.equal(reads, 1);
    });
  }
  for (const registry of [null, undefined]) {
    await run(`nullish registry after id ${String(registry)}`, async () => {
      let reads = 0; const params = Object.defineProperty({}, "id", { get() { reads++; return {}; } });
      await assert.rejects(evaluate().selected(registry, null, unread("request"), params), TypeError); assert.equal(reads, 1);
    });
  }
  for (const params of [false, 0, "abc", Symbol("params"), 1n]) {
    await run(`primitive parameter boxing ${typeof params}`, async () => {
      assert.equal(await evaluate().selected({ capabilities: (_actor: unknown, id: unknown) => id }, null, unread("request"), params), undefined);
    });
  }
  await run("inherited id and inherited method preserve concrete receivers", async () => {
    const id = {}; const params = Object.create({ get id() { assert.equal(this, params); return id; } });
    const registry = Object.create({ get capabilities() { assert.equal(this, registry); return function (this: unknown, actor: unknown, actual: unknown) { assert.equal(this, registry); assert.equal(actor, null); return actual; }; } });
    assert.equal(await evaluate().selected(registry, null, unread("request"), params), id);
  });
  await run("params proxy reads only id; unrelated fields symbols and prototype untouched", async () => {
    const id = unread("id"); const keys: PropertyKey[] = [];
    const params = new Proxy(Object.create(null), { get(_target, key) { keys.push(key); assert.equal(key, "id"); return id; } });
    assert.equal(await evaluate().selected({ capabilities: (_a: unknown, actual: unknown) => { assert.equal(actual, id); return "ok"; } }, unread("actor"), unread("request"), params), "ok");
    assert.deepEqual(keys, ["id"]);
  });
  await run("registry proxy reads only capabilities and uses original receiver", async () => {
    const keys: PropertyKey[] = [];
    const registry: any = new Proxy(Object.create(null), { get(_target, key) { keys.push(key); assert.equal(key, "capabilities"); return function (this: unknown) { assert.equal(this, registry); return "ok"; }; } });
    assert.equal(await evaluate().selected(registry, unread("actor"), unread("request"), { id: unread("id") }), "ok");
    assert.deepEqual(keys, ["capabilities"]);
  });
  await run("selected body ignores callback this and excess arguments", async () => {
    const cb = evaluate().selected;
    const p = Reflect.apply(cb, unread("callback this"), [{ capabilities: () => "ok" }, unread("actor"), unread("request"), {}, unread("extra")]);
    assert.equal(await p, "ok");
  });
  await run("bound method retains its intrinsic bound receiver", async () => {
    const bound = {}; const fn = function (this: unknown) { assert.equal(this, bound); return "ok"; }.bind(bound);
    assert.equal(await evaluate().selected({ capabilities: fn }, null, null, {}), "ok");
  });
  await run("method replaced during getter remains captured once", async () => {
    const registry: any = {};
    Object.defineProperty(registry, "capabilities", { configurable: true, get() {
      Object.defineProperty(registry, "capabilities", { value: () => assert.fail("replacement called") });
      return function (this: unknown) { assert.equal(this, registry); return "captured"; };
    } });
    assert.equal(await evaluate().selected(registry, null, null, {}), "captured");
  });
  await run("id getter mutation is visible to subsequent method capture", async () => {
    const registry = { capabilities: () => "before" };
    const params = { get id() { registry.capabilities = () => "after"; return 0; } };
    assert.equal(await evaluate().selected(registry, null, null, params), "after");
  });
  await run("fresh calls capture current method independently", async () => {
    const cb = evaluate().selected; const registry = { capabilities: () => "first" };
    assert.equal(await cb(registry, null, null, {}), "first"); registry.capabilities = () => "second";
    assert.equal(await cb(registry, null, null, {}), "second"); assert.notEqual(evaluate().selected, cb);
  });
  await run("id getter reentry preserves both original argument sets", async () => {
    const cb = evaluate().selected; let nested!: Promise<unknown>; const seen: unknown[][] = [];
    const registry = { capabilities(this: unknown, actor: unknown, id: unknown) { assert.equal(this, registry); seen.push([actor, id]); return id; } };
    const a = {}; const b = {}; const outerId = {}; const innerId = {};
    const params = { get id() { nested = cb(registry, b, unread("inner request"), { id: innerId }); return outerId; } };
    assert.equal(await cb(registry, a, unread("outer request"), params), outerId); assert.equal(await nested, innerId);
    assert.deepEqual(seen, [[b, innerId], [a, outerId]]);
  });
  await run("method getter reentry captures independent methods and receivers", async () => {
    const cb = evaluate().selected; const inner = { capabilities: () => "inner" }; let nested!: Promise<unknown>;
    const outer = { get capabilities() { nested = cb(inner, null, null, {}); return function (this: unknown) { assert.equal(this, outer); return "outer"; }; } };
    assert.equal(await cb(outer, null, null, {}), "outer"); assert.equal(await nested, "inner");
  });
  await run("interleaved calls adopt only their own pending results", async () => {
    const cb = evaluate().selected; const first = deferred(); const second = deferred(); let calls = 0;
    const registry = { capabilities() { return ++calls === 1 ? first.promise : second.promise; } };
    const p = cb(registry, null, null, {}); const q = cb(registry, null, null, {}); let settled = false;
    void p.then(() => { settled = true; }); second.resolve("second"); assert.equal(await q, "second"); assert.equal(settled, false);
    first.resolve("first"); assert.equal(await p, "first"); assert.equal(calls, 2);
  });
  await run("returned Promise is adopted into a distinct callback Promise", async () => {
    const d = deferred(); const p = evaluate().selected({ capabilities: () => d.promise }, null, null, {});
    assert.notEqual(p, d.promise); d.resolve("ok"); assert.equal(await p, "ok");
  });
  await run("then getter captured synchronously and then called asynchronously once", async () => {
    const order: string[] = []; const result = { get then() { order.push("get then"); assert.equal(this, result); return function (this: unknown, yes: (x: unknown) => void, no: (x: unknown) => void) { order.push("call then"); assert.equal(this, result); yes("first"); no("late"); yes("later"); }; } };
    const p = evaluate().selected({ capabilities: () => result }, null, null, {});
    assert.deepEqual(order, ["get then"]); assert.equal(await p, "first"); assert.deepEqual(order, ["get then", "call then"]);
  });
  await run("then getter refusal preserves exact reason", async () => {
    const marker = {}; const result = { get then(): never { throw marker; } };
    await reason(evaluate().selected({ capabilities: () => result }, null, null, {}), marker);
  });
  await run("then refusal preserves exact reason and receiver", async () => {
    const marker = {}; const result = { then(this: unknown) { assert.equal(this, result); throw marker; } };
    await reason(evaluate().selected({ capabilities: () => result }, null, null, {}), marker);
  });
  await run("noncallable then returns same object without probing other fields", async () => {
    for (const then of [undefined, null, false, 0, "", {}]) {
      const result = { then, get body(): never { return assert.fail("body read"); } };
      assert.equal(await evaluate().selected({ capabilities: () => result }, null, null, {}), result);
    }
  });
  await run("thenable fulfillment ignores subsequent throw", async () => {
    const result = { then(yes: (x: unknown) => void) { yes("ok"); throw new Error("late"); } };
    assert.equal(await evaluate().selected({ capabilities: () => result }, null, null, {}), "ok");
  });
});
