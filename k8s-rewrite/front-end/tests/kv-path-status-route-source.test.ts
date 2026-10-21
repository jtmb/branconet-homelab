import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { test } from "node:test";
import type TypeScript from "typescript";

// Evaluate only the selected source with inert imports. No real kv-http code runs.
const requireTool = createRequire(import.meta.url);
const ts: typeof TypeScript = requireTool(process.env.BORTUS_SOURCE_TYPESCRIPT || "typescript");
const route = "src/app/api/kv/paths/[id]/status/route.ts";
const source = readFileSync(resolve(process.cwd(), route), "utf8");
const ast = ts.createSourceFile(route, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
assert.equal(ast.statements.length, 4);
assert(ts.isImportDeclaration(ast.statements[0]));
assert.equal(ast.statements[0].moduleSpecifier.getText(ast), '"@/lib/kv-http"');
assert.equal(ast.statements[3].getText(ast), "export const GET = kvHuman(async (registry, actor, _request, { id }) => kvEngine(registry).status(actor, id));");
const compiled = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  fileName: route, reportDiagnostics: true,
});
assert.equal(compiled.diagnostics?.length, 0);

type Callback = (registry: any, actor: any, request: any, params: any) => Promise<any>;
type Factory = (this: unknown, ...args: any[]) => any;
type Wrapper = (this: unknown, callback: Callback, ...rest: unknown[]) => unknown;
function evaluate(factory: any = () => ({ status: () => undefined }), wrapper?: Wrapper, factoryRead?: () => any) {
  let selected!: Callback;
  const calls: unknown[][] = [];
  const exports: any = {};
  const imports: string[] = [];
  const kvHuman = function (this: unknown, callback: Callback, ...rest: unknown[]) {
    assert.equal(this, undefined);
    calls.push([callback, ...rest]); selected = callback;
    return wrapper ? Reflect.apply(wrapper, this, [callback, ...rest]) : callback;
  };
  const inertModule = Object.defineProperty({ kvHuman }, "kvEngine", { get() { return factoryRead ? factoryRead() : factory; } });
  const inertRequire = (name: string) => { imports.push(name); assert.equal(name, "@/lib/kv-http"); return inertModule; };
  new Function("require", "exports", compiled.outputText)(inertRequire, exports);
  assert.deepEqual(imports, ["@/lib/kv-http"]);
  assert.deepEqual(Object.keys(exports).sort(), ["GET", "dynamic", "runtime"]);
  assert.equal(exports.runtime, "nodejs"); assert.equal(exports.dynamic, "force-dynamic");
  assert.equal(calls.length, 1); assert.equal(calls[0].length, 1); assert.equal(typeof selected, "function");
  return { selected, exports };
}
function unread(label: string): any {
  return new Proxy(Object.create(null), {
    get() { throw new Error(`${label}:get`); }, has() { throw new Error(`${label}:has`); },
    ownKeys() { throw new Error(`${label}:ownKeys`); }, getPrototypeOf() { throw new Error(`${label}:prototype`); },
    getOwnPropertyDescriptor() { throw new Error(`${label}:descriptor`); },
  });
}
async function reason(promise: Promise<unknown>, expected: unknown) {
  let rejected = false;
  await promise.then(() => assert.fail("expected rejection"), actual => { rejected = true; assert(Object.is(actual, expected)); });
  assert(rejected);
}
function deferred() {
  let resolve!: (value: any) => void; let reject!: (value: any) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const identities: unknown[] = [undefined, null, false, true, 0, -0, NaN, Infinity, "", "a/b", Symbol("id"), {}, [], () => 0];
const noncallables = [undefined, null, false, 0, "status", Symbol("method"), {}, []];

test("human path-status GET selected source", { concurrency: false }, async t => {
  const run = async (name: string, body: () => void | Promise<void>) => { await t.test(name, body); };
  for (const [index, marker] of identities.entries()) {
    await run(`wrapper return identity ${index}`, () => {
      const { exports } = evaluate(undefined, function () { assert.equal(this, undefined); return marker; });
      assert(Object.is(exports.GET, marker));
    });
    await run(`id forwarding identity ${index}`, async () => {
      const actor = unread("actor"); const registry = unread("registry"); const result = {};
      const engine = { status(this: unknown, ...args: unknown[]) { assert.equal(this, engine); assert.equal(args.length, 2); assert.equal(args[0], actor); assert(Object.is(args[1], marker)); return result; } };
      const factory: Factory = function (...args) { assert.equal(this, undefined); assert.equal(args.length, 1); assert.equal(args[0], registry); return engine; };
      assert.equal(await evaluate(factory).selected(registry, actor, unread("request"), { id: marker }), result);
    });
    await run(`actor forwarding identity ${index}`, async () => {
      const id = unread("id"); const result = {};
      const engine = { status(this: unknown, ...args: unknown[]) { assert.equal(this, engine); assert.equal(args.length, 2); assert(Object.is(args[0], marker)); assert.equal(args[1], id); return result; } };
      assert.equal(await evaluate(() => engine).selected(unread("registry"), marker, unread("request"), { id }), result);
    });
    await run(`registry forwarding identity ${index}`, async () => {
      const factory: Factory = function (...args) { assert.equal(this, undefined); assert.equal(args.length, 1); assert(Object.is(args[0], marker)); return { status: () => 7 }; };
      assert.equal(await evaluate(factory).selected(marker, unread("actor"), unread("request"), { id: unread("id") }), 7);
    });
    await run(`result forwarding identity ${index}`, async () => {
      const p = evaluate(() => ({ status: () => marker })).selected(unread("registry"), unread("actor"), unread("request"), {});
      assert(p instanceof Promise); assert(Object.is(await p, marker));
    });
    await run(`id getter refusal identity ${index}`, async () => {
      let reads = 0;
      const params = Object.defineProperty({}, "id", { get() { throw marker; } });
      await reason(evaluate(undefined, undefined, () => { reads++; return assert.fail("factory read"); }).selected(unread("registry"), unread("actor"), unread("request"), params), marker);
      assert.equal(reads, 0);
    });
    await run(`factory import getter refusal identity ${index}`, async () => {
      const order: string[] = [];
      const params = Object.defineProperty({}, "id", { get() { order.push("id"); return unread("id"); } });
      const { selected } = evaluate(undefined, undefined, () => { order.push("factory-get"); throw marker; });
      await reason(selected(unread("registry"), unread("actor"), unread("request"), params), marker);
      assert.deepEqual(order, ["id", "factory-get"]);
    });
    await run(`factory call refusal identity ${index}`, async () => {
      await reason(evaluate(() => { throw marker; }).selected(unread("registry"), unread("actor"), unread("request"), {}), marker);
    });
    await run(`status getter refusal identity ${index}`, async () => {
      const order: string[] = [];
      const engine = Object.defineProperty({}, "status", { get() { order.push("status-get"); assert.equal(this, engine); throw marker; } });
      await reason(evaluate(() => { order.push("factory-call"); return engine; }).selected(unread("registry"), unread("actor"), unread("request"), {}), marker);
      assert.deepEqual(order, ["factory-call", "status-get"]);
    });
    await run(`status call refusal identity ${index}`, async () => {
      const engine = { status(this: unknown) { assert.equal(this, engine); throw marker; } };
      let p!: Promise<unknown>; assert.doesNotThrow(() => { p = evaluate(() => engine).selected(unread("registry"), unread("actor"), unread("request"), {}); });
      await reason(p, marker);
    });
    await run(`promise rejection identity ${index}`, async () => {
      await reason(evaluate(() => ({ status: () => Promise.reject(marker) })).selected({}, {}, unread("request"), {}), marker);
    });
  }
  await run("wrapper refusal remains module evaluation refusal", () => {
    const marker = {}; assert.throws(() => evaluate(undefined, () => { throw marker; }), error => error === marker);
  });
  await run("callback is async nonconstructable arity four and lexical this", async () => {
    const { selected } = evaluate(); assert.equal(selected.length, 4);
    assert.equal(Object.prototype.toString.call(selected), "[object AsyncFunction]");
    assert.throws(() => Reflect.construct(selected, []), TypeError);
    assert.equal(await Reflect.apply(selected, unread("this"), [{}, {}, unread("request"), {}]), undefined);
  });
  for (const params of [undefined, null]) {
    await run(`nullish params refuse before factory ${String(params)}`, async () => {
      let reads = 0;
      await assert.rejects(evaluate(undefined, undefined, () => { reads++; return assert.fail("factory"); }).selected({}, {}, unread("request"), params), TypeError);
      assert.equal(reads, 0);
    });
  }
  for (const [index, params] of [false, true, 0, -0, NaN, Infinity, "", "x", Symbol("params"), 1n].entries()) {
    await run(`primitive params box without coercion ${index}`, async () => {
      const engine = { status(_actor: unknown, id: unknown) { assert.equal(id, undefined); return 8; } };
      assert.equal(await evaluate(() => engine).selected({}, {}, unread("request"), params), 8);
    });
  }
  await run("binding order factory capture call status capture call", async () => {
    const order: string[] = []; const actor = {}; const id = {}; const registry = unread("registry"); const result = {};
    const engine = Object.defineProperty({}, "status", { get() { order.push("status-get"); assert.equal(this, engine); return function (this: unknown, ...args: unknown[]) { order.push("status-call"); assert.equal(this, engine); assert.deepEqual(args, [actor, id]); return result; }; } });
    const factory: Factory = function (...args) { order.push("factory-call"); assert.equal(this, undefined); assert.deepEqual(args, [registry]); return engine; };
    const params = Object.defineProperty({}, "id", { get() { order.push("id"); assert.equal(this, params); return id; } });
    const { selected } = evaluate(undefined, undefined, () => { order.push("factory-get"); return factory; });
    const p = selected(registry, actor, unread("request"), params);
    assert.deepEqual(order, ["id", "factory-get", "factory-call", "status-get", "status-call"]); assert.equal(await p, result);
  });
  await run("id getter replaces factory before capture", async () => {
    let factory = () => ({ status: () => 1 });
    const params = Object.defineProperty({}, "id", { get() { factory = () => ({ status: () => 2 }); return 3; } });
    assert.equal(await evaluate(undefined, undefined, () => factory).selected({}, {}, unread("request"), params), 2);
  });
  await run("factory capture survives self replacement during call", async () => {
    let count = 0; let factory: Factory;
    factory = function () { count++; factory = () => ({ status: () => 2 }); return { status: () => 1 }; };
    const { selected } = evaluate(undefined, undefined, () => factory);
    assert.equal(await selected({}, {}, unread("request"), {}), 1); assert.equal(await selected({}, {}, unread("request"), {}), 2); assert.equal(count, 1);
  });
  await run("inherited id uses original params receiver once", async () => {
    let n = 0; const id = {}; let params: object;
    const proto = Object.defineProperty({}, "id", { get() { n++; assert.equal(this, params); return id; } }); params = Object.create(proto);
    assert.equal(await evaluate(() => ({ status: (_a: unknown, i: unknown) => i === id })).selected({}, {}, unread("request"), params), true); assert.equal(n, 1);
  });
  await run("params proxy reads only id with original receiver", async () => {
    const id = unread("id"); const order: string[] = []; let params: object;
    params = new Proxy({}, { get(_target, key, receiver) { assert.equal(key, "id"); assert.equal(receiver, params); order.push("id"); return id; }, has() { return assert.fail("has"); }, ownKeys() { return assert.fail("keys"); }, getPrototypeOf() { return assert.fail("prototype"); }, getOwnPropertyDescriptor() { return assert.fail("descriptor"); } });
    assert.equal(await evaluate(() => ({ status: (_a: unknown, i: unknown) => i === id })).selected({}, {}, unread("request"), params), true); assert.deepEqual(order, ["id"]);
  });
  await run("own id leaves unrelated string symbol and then getters unread", async () => {
    const params = Object.defineProperties({ id: 3 }, { extra: { get() { return assert.fail("extra"); } }, then: { get() { return assert.fail("then"); } }, [Symbol("extra")]: { get() { return assert.fail("symbol"); } } });
    assert.equal(await evaluate(() => ({ status: (_a: unknown, id: unknown) => id })).selected({}, {}, unread("request"), params), 3);
  });
  await run("factory apply trap gets exact undefined receiver and original registry", async () => {
    const registry = unread("registry"); const engine = { status: () => 9 }; let n = 0;
    const factory = new Proxy(function () {}, { apply(_target, receiver, args) { n++; assert.equal(receiver, undefined); assert.equal(args.length, 1); assert.equal(args[0], registry); return engine; }, get() { return assert.fail("factory property"); } });
    assert.equal(await evaluate(factory).selected(registry, unread("actor"), unread("request"), {}), 9); assert.equal(n, 1);
  });
  for (const [index, value] of noncallables.entries()) {
    await run(`noncallable factory rejects after id ${index}`, async () => {
      const order: string[] = []; const params = Object.defineProperty({}, "id", { get() { order.push("id"); return 1; } });
      await assert.rejects(evaluate(value, undefined, () => { order.push("factory-get"); return value; }).selected({}, {}, unread("request"), params), TypeError); assert.deepEqual(order, ["id", "factory-get"]);
    });
    await run(`noncallable status rejects without invoking identity internals ${index}`, async () => {
      const engine = { status: value }; await assert.rejects(evaluate(() => engine).selected(unread("registry"), unread("actor"), unread("request"), { id: unread("id") }), TypeError);
    });
  }
  for (const engine of [undefined, null]) {
    await run(`nullish engine rejects status lookup ${String(engine)}`, async () => { await assert.rejects(evaluate(() => engine).selected(unread("registry"), unread("actor"), unread("request"), {}), TypeError); });
  }
  await run("factory class refuses ordinary call", async () => { await assert.rejects(evaluate(class {}).selected({}, {}, unread("request"), {}), TypeError); });
  await run("status class refuses ordinary call", async () => { await assert.rejects(evaluate(() => ({ status: class {} })).selected({}, {}, unread("request"), {}), TypeError); });
  await run("inherited status getter and method use engine receiver", async () => {
    let engine: object; let reads = 0;
    const proto = Object.defineProperty({}, "status", { get() { reads++; assert.equal(this, engine); return function (this: unknown) { assert.equal(this, engine); return 11; }; } }); engine = Object.create(proto);
    assert.equal(await evaluate(() => engine).selected({}, {}, unread("request"), {}), 11); assert.equal(reads, 1);
  });
  await run("engine proxy reads only status original receiver", async () => {
    let engine: object; const order: string[] = [];
    engine = new Proxy({}, { get(_target, key, receiver) { assert.equal(key, "status"); assert.equal(receiver, engine); order.push("status"); return function (this: unknown) { assert.equal(this, engine); return 12; }; }, has() { return assert.fail("has"); }, ownKeys() { return assert.fail("keys"); }, getPrototypeOf() { return assert.fail("prototype"); }, getOwnPropertyDescriptor() { return assert.fail("descriptor"); } });
    assert.equal(await evaluate(() => engine).selected({}, {}, unread("request"), {}), 12); assert.deepEqual(order, ["status"]);
  });
  await run("status callable proxy receives engine actor id exactly", async () => {
    const actor = unread("actor"); const id = unread("id"); let n = 0; let engine: object;
    const status = new Proxy(function () {}, { apply(_t, receiver, args) { n++; assert.equal(receiver, engine); assert.equal(args.length, 2); assert.equal(args[0], actor); assert.equal(args[1], id); return 13; }, get() { return assert.fail("method property"); } }); engine = { status };
    assert.equal(await evaluate(() => engine).selected(unread("registry"), actor, unread("request"), { id }), 13); assert.equal(n, 1);
  });
  await run("id and status are captured once despite mutation", async () => {
    const params = { id: 1 }; let reads = 0;
    const engine = Object.defineProperty({}, "status", { configurable: true, get() { reads++; params.id = 2; Object.defineProperty(engine, "status", { value: () => 99 }); return (_a: unknown, id: unknown) => id; } });
    assert.equal(await evaluate(() => engine).selected({}, {}, unread("request"), params), 1); assert.equal(reads, 1);
  });
  await run("factory return thenable is not awaited before status lookup", async () => {
    const engine = Object.defineProperty({ status: () => 14 }, "then", { get() { return assert.fail("factory result then"); } });
    assert.equal(await evaluate(() => engine).selected({}, {}, unread("request"), {}), 14);
  });
  await run("async factory promise is used as engine rather than awaited", async () => {
    let calls = 0; const engine = { status() { calls++; return 1; } };
    await assert.rejects(evaluate(async () => engine).selected({}, {}, unread("request"), {}), TypeError); assert.equal(calls, 0);
  });
  await run("promise factory result own status is callable synchronously", async () => {
    const engine = Object.assign(Promise.resolve(1), { status(this: unknown) { assert.equal(this, engine); return 15; } });
    assert.equal(await evaluate(() => engine).selected({}, {}, unread("request"), {}), 15);
  });
  await run("fresh invocations read factory and status on every call", async () => {
    let reads = 0; let calls = 0; let statusReads = 0;
    const { selected } = evaluate(undefined, undefined, () => { reads++; return () => { calls++; return Object.defineProperty({}, "status", { get() { statusReads++; return () => statusReads; } }); }; });
    assert.equal(await selected({}, {}, unread("request"), {}), 1); assert.equal(await selected({}, {}, unread("request"), {}), 2); assert.deepEqual([reads, calls, statusReads], [2, 2, 2]);
  });
  await run("refused invocation cannot retain another call id or engine", async () => {
    const marker = {}; let count = 0; const { selected } = evaluate(() => { if (++count === 1) throw marker; return { status: (_a: unknown, id: unknown) => id }; });
    await reason(selected({}, {}, unread("request"), { id: 1 }), marker); assert.equal(await selected({}, {}, unread("request"), { id: 2 }), 2);
  });
  await run("reentrant id getter keeps both call bindings", async () => {
    const seen: unknown[] = []; const { selected } = evaluate(() => ({ status: (a: unknown, id: unknown) => { seen.push([a, id]); return id; } }));
    let inner!: Promise<unknown>; const outerActor = {}; const innerActor = {};
    const params = Object.defineProperty({}, "id", { get() { inner = selected({}, innerActor, unread("inner-request"), { id: 2 }); return 1; } });
    assert.equal(await selected({}, outerActor, unread("outer-request"), params), 1); assert.equal(await inner, 2); assert.deepEqual(seen, [[innerActor, 2], [outerActor, 1]]);
  });
  await run("reentrant factory retains outer engine and arguments", async () => {
    const outer = {}; const inner = {}; const seen: unknown[] = []; let nested!: Promise<unknown>; let selected!: Callback;
    const factory = (registry: unknown) => { if (registry === outer) nested = selected(inner, 2, unread("inner-request"), { id: 20 }); return { status: (a: unknown, id: unknown) => { seen.push([registry, a, id]); return id; } }; };
    selected = evaluate(factory).selected; assert.equal(await selected(outer, 1, unread("outer-request"), { id: 10 }), 10); assert.equal(await nested, 20); assert.deepEqual(seen, [[inner, 2, 20], [outer, 1, 10]]);
  });
  await run("interleaved pending calls settle independently in reverse order", async () => {
    const one = deferred(); const two = deferred(); const seen: unknown[] = []; let n = 0;
    const { selected } = evaluate(() => { const d = n++ === 0 ? one : two; return { status: (a: unknown, id: unknown) => { seen.push([a, id]); return d.promise; } }; });
    const a = selected({}, 1, unread("request"), { id: 10 }); const b = selected({}, 2, unread("request"), { id: 20 });
    let aDone = false; a.then(() => { aDone = true; }); two.resolve(22); assert.equal(await b, 22); assert.equal(aDone, false); one.resolve(11); assert.equal(await a, 11); assert.deepEqual(seen, [[1, 10], [2, 20]]);
  });
  await run("returned promise is adopted with a distinct async promise", async () => {
    const d = deferred(); const p = evaluate(() => ({ status: () => d.promise })).selected({}, {}, unread("request"), {}); assert.notEqual(p, d.promise); d.resolve(16); assert.equal(await p, 16);
  });
  await run("thenable getter is captured once then invoked with original receiver", async () => {
    const order: string[] = []; const result = {}; let value: object;
    value = Object.defineProperty({}, "then", { get() { order.push("get"); assert.equal(this, value); return function (this: unknown, yes: (x: unknown) => void, no: (x: unknown) => void) { order.push("call"); assert.equal(this, value); assert.equal(typeof no, "function"); yes(result); }; } });
    const p = evaluate(() => ({ status: () => value })).selected({}, {}, unread("request"), {}); assert.deepEqual(order, ["get"]); assert.equal(await p, result); assert.deepEqual(order, ["get", "call"]);
  });
  for (const [index, marker] of identities.entries()) {
    await run(`then getter refusal identity ${index}`, async () => {
      const value = Object.defineProperty({}, "then", { get() { throw marker; } }); await reason(evaluate(() => ({ status: () => value })).selected({}, {}, unread("request"), {}), marker);
    });
    await run(`then call refusal identity ${index}`, async () => {
      const value = { then() { throw marker; } }; await reason(evaluate(() => ({ status: () => value })).selected({}, {}, unread("request"), {}), marker);
    });
    await run(`then rejection identity ${index}`, async () => {
      const value = { then(_yes: unknown, no: (x: unknown) => void) { no(marker); } }; await reason(evaluate(() => ({ status: () => value })).selected({}, {}, unread("request"), {}), marker);
    });
  }
  for (const [index, then] of noncallables.entries()) {
    await run(`noncallable result then preserves object identity ${index}`, async () => { const value = { then }; assert.equal(await evaluate(() => ({ status: () => value })).selected({}, {}, unread("request"), {}), value); });
  }
  await run("thenable first settlement wins over rejection and later throw", async () => {
    const result = {}; const value = { then(yes: (x: unknown) => void, no: (x: unknown) => void) { yes(result); no({}); throw {}; } };
    assert.equal(await evaluate(() => ({ status: () => value })).selected({}, {}, unread("request"), {}), result);
  });
  await run("thenable rejection wins over later fulfillment", async () => {
    const marker = {}; const value = { then(yes: (x: unknown) => void, no: (x: unknown) => void) { no(marker); yes({}); } };
    await reason(evaluate(() => ({ status: () => value })).selected({}, {}, unread("request"), {}), marker);
  });
  await run("nested thenable adopts only returned result", async () => {
    const result = {}; const value = { then(yes: (x: unknown) => void) { yes({ then(next: (x: unknown) => void) { next(result); } }); } };
    assert.equal(await evaluate(() => ({ status: () => value })).selected(unread("registry"), unread("actor"), unread("request"), { id: unread("id") }), result);
  });
});
