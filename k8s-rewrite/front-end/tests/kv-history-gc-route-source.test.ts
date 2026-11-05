import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";

// Finite PUBLIC SOURCE controls: only this POST initializer runs. All real
// imports, kvHuman, body/schema, registry and native engine services stay inert.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);
const source = readFileSync(new URL("../src/app/api/kv/history/gc/route.ts", import.meta.url), "utf8");
const ast = ts.createSourceFile("route.ts", source, ts.ScriptTarget.Latest, true);
const variables = ast.statements.flatMap((s: { declarationList?: { declarations: unknown[] } }) => s.declarationList?.declarations ?? []);
const post = variables.find((d: { name: { getText(): string } }) => d.name.getText() === "POST");
assert.ok(post);
assert.equal(post.initializer.expression.getText(), "kvHuman");
assert.equal(post.initializer.arguments.length, 1);
const callback = post.initializer.arguments[0];
assert.ok(ts.isArrowFunction(callback));
assert.deepEqual(callback.parameters.map((p: { name: { getText(): string } }) => p.name.getText()), ["registry", "actor", "request"]);
assert.equal(callback.modifiers.length, 1);
assert.equal(callback.modifiers[0].kind, ts.SyntaxKind.AsyncKeyword);
const js = ts.transpileModule("return (" + post.initializer.getText() + ");", { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
type Call = (...args: unknown[]) => unknown;
type Handler = (registry: unknown, actor: unknown, request: unknown) => Promise<unknown>;
function select(kvBody: Call, kvEngine: Call, historyGc: unknown): Handler {
  let captured: Handler | undefined;
  const wrapperResult = {};
  const wrapper: Call = function (this: unknown, ...args) {
    assert.equal(this, undefined); assert.equal(args.length, 1);
    assert.equal(typeof args[0], "function"); captured = args[0] as Handler;
    return wrapperResult;
  };
  const returned = new Function("kvHuman", "kvBody", "kvEngine", "historyGc", '"use strict";\n' + js)(wrapper, kvBody, kvEngine, historyGc);
  assert.equal(returned, wrapperResult); assert.ok(captured); return captured;
}
function opaque(label: string): object {
  return new Proxy(Object.create(null), { get() { throw Error(label + " read"); }, ownKeys() { throw Error(label + " keys"); }, getPrototypeOf() { throw Error(label + " prototype"); } });
}
function deferred() {
  let resolve!: (value: unknown) => void, reject!: (reason: unknown) => void;
  const promise = new Promise((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}
const sequence = ["body", "engine", "method", "path", "signal", "call"];
const examples = [undefined, null, false, true, 0, -1, "", "public", Symbol("public"), {}, [], opaque("opaque argument")];
type RigOptions = { pathId?: unknown; signal?: unknown; body?: (input: object) => unknown; result?: unknown; stage?: (name: string) => void };
function rig(o: RigOptions = {}) {
  const events: string[] = [], registry = opaque("registry"), actor = opaque("actor"), schema = opaque("schema");
  const pathId = Object.hasOwn(o, "pathId") ? o.pathId : opaque("pathId");
  const signal = Object.hasOwn(o, "signal") ? o.signal : opaque("signal");
  const final = Object.hasOwn(o, "result") ? o.result : { marker: opaque("result internals") };
  const hit = (name: string) => { events.push(name); o.stage?.(name); };
  const input = Object.defineProperty(Object.create(null), "pathId", { configurable: true, get() { hit("path"); return pathId; } });
  const request = Object.defineProperty(Object.create(null), "signal", { configurable: true, get() { hit("signal"); return signal; } });
  const engine = Object.defineProperty(Object.create(null), "gc", { configurable: true, get() {
    hit("method"); return function (this: unknown, ...args: unknown[]) {
      hit("call"); assert.equal(this, engine); assert.equal(args.length, 4);
      assert.equal(args[0], actor); assert.equal(args[1], pathId); assert.equal(args[2], input); assert.equal(args[3], signal);
      return final;
    };
  } });
  const handler = select(function (this: unknown, ...args) {
    hit("body"); assert.equal(this, undefined); assert.equal(args.length, 2);
    assert.equal(args[0], request); assert.equal(args[1], schema); return o.body ? o.body(input) : input;
  }, function (this: unknown, ...args) {
    hit("engine"); assert.equal(this, undefined); assert.equal(args.length, 1); assert.equal(args[0], registry); return engine;
  }, schema);
  return { events, registry, actor, schema, pathId, signal, final, input, request, engine, handler, invoke: () => handler(registry, actor, request) };
}
function property(kind: string, key: string, value: unknown, events: string[]) {
  const own = Object.defineProperty({}, key, { get() { events.push(key); return value; } });
  if (kind === "own") return own;
  if (kind === "inherited") return Object.create(own);
  if (kind === "proxy") return new Proxy({}, { get(_t, k) { if (k === "then") return undefined; assert.equal(k, key); events.push(key); return value; }, ownKeys() { throw Error("unexpected keys"); } });
  if (kind === "missing") return {};
  if (kind === "false") return false;
  if (kind === "zero") return 0;
  if (kind === "string") return "";
  return Symbol("public primitive");
}

test("human history-GC commit POST finite SOURCE controls", async t => {
  await t.test("exact imports, runtime, async wrapper and source statements", () => {
    const imports = ast.statements.filter((s: unknown) => ts.isImportDeclaration(s));
    assert.deepEqual(imports.map((s: { getText(): string }) => s.getText()), ['import { kvBody, kvEngine, kvHuman } from "@/lib/kv-http";', 'import { historyGc } from "@/lib/kv-schemas";']);
    assert.equal(ast.statements.length, 4); assert.equal(variables.length, 2);
    assert.equal(variables[0].name.getText(), "runtime"); assert.equal(variables[0].initializer.getText(), '"nodejs"');
    assert.deepEqual(callback.body.statements.map((s: { getText(): string }) => s.getText()), ["const input = await kvBody(request, historyGc);", "return kvEngine(registry).gc(actor, input.pathId, input, request.signal);"]);
    select(() => { throw Error("wrapper ran body"); }, () => { throw Error("wrapper ran engine"); }, opaque("schema"));
  });
  for (const [index, value] of examples.entries()) for (const field of ["pathId", "signal"] as const) {
    await t.test("exact four arguments, unbound delegates and opaque " + field + " case " + index, async () => {
      const r = rig({ [field]: value }); const p = r.invoke();
      assert.ok(p instanceof Promise); assert.deepEqual(r.events, ["body"]);
      assert.equal(await p, r.final); assert.deepEqual(r.events, sequence);
    });
  }
  for (const kind of ["plain", "resolved", "pending", "thenable"]) {
    await t.test("body " + kind + " adoption fences engine and both properties", async () => {
      const hold = deferred(); const r = rig({ body: input => kind === "plain" ? input : kind === "resolved" ? Promise.resolve(input) : kind === "pending" ? hold.promise : { then(resolve: (v: unknown) => void) { resolve(input); } } });
      const p = r.invoke(); assert.deepEqual(r.events, ["body"]);
      if (kind === "pending") { await Promise.resolve(); assert.deepEqual(r.events, ["body"]); hold.resolve(r.input); }
      assert.equal(await p, r.final); assert.deepEqual(r.events, sequence);
    });
  }
  for (const kind of ["throw", "reject", "then-getter", "then-call"]) {
    await t.test("body refusal " + kind + " stops engine and signal access", async () => {
      const failure = {}; const r = rig({ body() {
        if (kind === "throw") throw failure;
        if (kind === "reject") return Promise.reject(failure);
        if (kind === "then-getter") return Object.defineProperty({}, "then", { get() { throw failure; } });
        return { then() { throw failure; } };
      } });
      await assert.rejects(r.invoke(), x => x === failure); assert.deepEqual(r.events, ["body"]);
    });
  }
  for (const field of ["pathId", "signal"]) for (const kind of ["own", "inherited", "proxy", "missing", "false", "zero", "string", "symbol"]) {
    await t.test(field + " property semantics " + kind + " retain exact original input", async () => {
      const value = opaque("property value"), e: string[] = [];
      const selected = property(kind, field, value, e), expected = ["own", "inherited", "proxy"].includes(kind) ? value : undefined;
      const input = field === "pathId" ? selected : { pathId: value };
      const request = field === "signal" ? selected : { signal: value };
      const engine = { gc: function (this: unknown, ...args: unknown[]) {
        assert.equal(this, engine); assert.equal(args.length, 4); assert.equal(args[0], actor);
        assert.equal(args[1], field === "pathId" ? expected : value); assert.equal(args[2], input);
        assert.equal(args[3], field === "signal" ? expected : value); return 42;
      } };
      const actor = opaque("actor"), registry = opaque("registry");
      const handler = select(() => input, () => engine, opaque("schema"));
      assert.equal(await handler(registry, actor, request), 42);
      assert.deepEqual(e, expected === value ? [field] : []);
    });
  }
  for (const missing of [null, undefined]) for (const field of ["input", "request"]) {
    await t.test(field + " nullish " + String(missing) + " refuses at correct property", async () => {
      if (field === "request") {
        const e: string[] = []; const input = Object.defineProperty({}, "pathId", { get() { e.push("path"); return "p"; } });
        const h = select(() => input, () => ({ gc() { throw Error("forbidden call"); } }), {});
        await assert.rejects(h({}, {}, missing), TypeError); assert.deepEqual(e, ["path"]);
      } else {
        const r = rig({ body: () => missing });
        await assert.rejects(r.invoke(), TypeError); assert.deepEqual(r.events, ["body", "engine", "method"]);
      }
    });
  }
  for (const stage of sequence) {
    await t.test("exact refusal prefix at " + stage, async () => {
      const failure = {}; const r = rig({ stage: name => { if (name === stage) throw failure; } });
      const p = r.invoke(); assert.ok(p instanceof Promise); await assert.rejects(p, x => x === failure);
      assert.deepEqual(r.events, sequence.slice(0, sequence.indexOf(stage) + 1));
    });
  }
  for (const engine of [null, undefined]) {
    await t.test("nullish engine " + String(engine) + " refuses before path and signal", async () => {
      const h = select(() => Object.defineProperty({}, "pathId", { get() { throw Error("forbidden path"); } }), () => engine, {});
      await assert.rejects(h({}, {}, opaque("request")), TypeError);
    });
  }
  for (const kind of ["inherited", "proxy"]) {
    await t.test("engine method " + kind + " preserves actual receiver and ordering", async () => {
      const e: string[] = [], actor = {}, signal = {}, input = { pathId: {} };
      const method = function (this: unknown, ...args: unknown[]) { assert.equal(this, engine); assert.deepEqual(args, [actor, input.pathId, input, signal]); e.push("call"); return 7; };
      const proto = Object.defineProperty({}, "gc", { get() { e.push("method"); return method; } });
      const engine = kind === "inherited" ? Object.create(proto) : new Proxy({}, { get(_t, k) { assert.equal(k, "gc"); e.push("method"); return method; } });
      assert.equal(await select(() => input, () => engine, {})({}, actor, { signal }), 7); assert.deepEqual(e, ["method", "call"]);
    });
  }
  for (const stage of ["body", "engine"]) for (const missing of [undefined, null, 0, {}]) {
    await t.test("noncallable " + stage + " delegate " + String(missing) + " refuses before subsequent access", async () => {
      const e: string[] = [];
      const body: Call = () => { e.push("body"); return Object.defineProperty({}, "pathId", { get() { throw Error("forbidden path"); } }); };
      const engine: Call = () => { throw Error("forbidden engine"); };
      const h = select(stage === "body" ? missing as Call : body, stage === "engine" ? missing as Call : engine, {});
      await assert.rejects(h(opaque("registry"), opaque("actor"), opaque("request")), TypeError);
      assert.deepEqual(e, stage === "body" ? [] : ["body"]);
    });
  }
  for (const method of [undefined, null, 0, {}]) {
    await t.test("noncallable method still evaluates path then signal " + String(method), async () => {
      const e: string[] = []; const input = Object.defineProperty({}, "pathId", { get() { e.push("path"); return "p"; } });
      const request = Object.defineProperty({}, "signal", { get() { e.push("signal"); return {}; } });
      const h = select(() => input, () => ({ gc: method }), {});
      await assert.rejects(h({}, {}, request), TypeError); assert.deepEqual(e, ["path", "signal"]);
    });
  }
  await t.test("argument refusal precedes noncallable method refusal", async () => {
    const failure = {}, e: string[] = [];
    const h = select(() => Object.defineProperty({}, "pathId", { get() { e.push("path"); throw failure; } }), () => ({ gc: 0 }), {});
    await assert.rejects(h({}, {}, opaque("request")), x => x === failure); assert.deepEqual(e, ["path"]);
  });
  await t.test("method captured before path mutation; signal read after path mutation", async () => {
    const signal = {}, engine = { gc: function (this: unknown, ...args: unknown[]) { assert.equal(this, engine); assert.deepEqual(args, [actor, "p", input, signal]); return 1; } };
    const actor = opaque("actor"), request = { signal: {} };
    const input = Object.defineProperty({}, "pathId", { get() { engine.gc = () => { throw Error("late method"); }; request.signal = signal; return "p"; } });
    assert.equal(await select(() => input, () => engine, {})({}, actor, request), 1);
  });
  for (const kind of ["plain", "resolved", "pending", "thenable", "reject", "then-getter", "then-call"]) {
    await t.test("async result " + kind + " adoption after exactly one gc call", async () => {
      const marker = {}, hold = deferred();
      const result = kind === "plain" ? marker : kind === "resolved" ? Promise.resolve(marker) : kind === "pending" ? hold.promise : kind === "reject" ? { then(_resolve: unknown, reject: (v: unknown) => void) { reject(marker); } } : kind === "then-getter" ? Object.defineProperty({}, "then", { get() { throw marker; } }) : { then(resolve: (v: unknown) => void) { if (kind === "then-call") throw marker; resolve(marker); } };
      const r = rig({ result }); const p = r.invoke();
      if (kind === "pending") { await Promise.resolve(); assert.deepEqual(r.events, sequence); hold.resolve(marker); }
      if (["reject", "then-getter", "then-call"].includes(kind)) await assert.rejects(p, x => x === marker);
      else assert.equal(await p, marker);
      assert.deepEqual(r.events, sequence);
    });
  }
  await t.test("fresh selectors do not share captured identities", async () => {
    const a = rig(), b = rig(); assert.notEqual(a.handler, b.handler);
    assert.equal(await a.invoke(), a.final); assert.equal(await b.invoke(), b.final);
    assert.deepEqual(a.events, sequence); assert.deepEqual(b.events, sequence);
  });
  await t.test("same callback interleaves two body waits without retaining another call input", async () => {
    const holds = [deferred(), deferred()], requests = [{ signal: {} }, { signal: {} }], inputs = [{ pathId: {} }, { pathId: {} }], actors = [{}, {}], registries = [{}, {}];
    const calls: number[] = []; let bodyCalls = 0;
    const h = select((request: unknown) => { const i = requests.indexOf(request as typeof requests[number]); assert.equal(i, bodyCalls++); return holds[i].promise; }, (registry: unknown) => {
      const i = registries.indexOf(registry as object); const engine = { gc: function (this: unknown, ...args: unknown[]) { assert.equal(this, engine); assert.deepEqual(args, [actors[i], inputs[i].pathId, inputs[i], requests[i].signal]); calls.push(i); return i; } }; return engine;
    }, opaque("schema"));
    const a = h(registries[0], actors[0], requests[0]), b = h(registries[1], actors[1], requests[1]);
    assert.deepEqual(calls, []); holds[1].resolve(inputs[1]); assert.equal(await b, 1); assert.deepEqual(calls, [1]);
    holds[0].resolve(inputs[0]); assert.equal(await a, 0); assert.deepEqual(calls, [1, 0]);
  });
  for (const stage of sequence) {
    await t.test("same callback reentrancy during " + stage + " preserves both four-argument calls", async () => {
      const requests = [{ signal: {} }, { signal: {} }], inputs = [{ pathId: {} }, { pathId: {} }], actors = [{}, {}], registries = [{}, {}];
      let launched = false, nested: Promise<unknown> | undefined; const calls: number[] = [];
      const launch = (name: string, i: number) => { if (!launched && i === 0 && name === stage) { launched = true; nested = h(registries[1], actors[1], requests[1]); } };
      for (const i of [0, 1]) {
        const id = inputs[i].pathId, signal = requests[i].signal;
        Object.defineProperty(inputs[i], "pathId", { get() { launch("path", i); return id; } });
        Object.defineProperty(requests[i], "signal", { get() { launch("signal", i); return signal; } });
      }
      const h = select((request: unknown) => { const i = requests.indexOf(request as typeof requests[number]); launch("body", i); return inputs[i]; }, (registry: unknown) => {
        const i = registries.indexOf(registry as object); launch("engine", i);
        const engine = Object.defineProperty({}, "gc", { get() { launch("method", i); return function (this: unknown, ...args: unknown[]) { launch("call", i); assert.equal(this, engine); assert.deepEqual(args, [actors[i], inputs[i].pathId, inputs[i], requests[i].signal]); calls.push(i); return i; }; } }); return engine;
      }, opaque("schema"));
      assert.equal(await h(registries[0], actors[0], requests[0]), 0); assert.ok(nested); assert.equal(await nested, 1);
      assert.equal(launched, true); assert.deepEqual([...calls].sort(), [0, 1]);
    });
  }
});
