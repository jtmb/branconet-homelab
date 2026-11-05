import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC SOURCE controls. Only DELETE callbacks execute; PATCH,
// kvHuman, kvBody, schemas, requests and the registry remain inert models.
type Model = Record<string, any>;
const file = "src/app/api/kv/mounts/[id]/route.ts";
const compiled = ts.transpileModule(readFileSync(file, "utf8"), { fileName: file,
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const sequence = ["id", "method", "bodyMethod", "schema", "body", "revision", "invoke"];
const prefix = sequence.slice(0, 5);
const turns = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
function deferred() {
  let resolve!: (value: any) => void, reject!: (error: unknown) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const opaque = (label: string) => new Proxy({}, {
  get() { throw Error(`PUBLIC: unexpected ${label} read`); },
  ownKeys() { throw Error(`PUBLIC: unexpected ${label} enumeration`); },
});
function fixture() {
  const calls: string[] = [], seen: Model = { wrappers: [], bodies: [], invocations: [], receivers: [] };
  const actor = opaque("actor"), id = opaque("id"), request = opaque("request"), schema = opaque("schema");
  const revision = Object.freeze({ public: "REVISION" }), result = Object.freeze({ public: "RESULT" });
  const state: Model = { id, schema, revision, result, faults: {}, methodSet: false };
  const step = (label: string) => { calls.push(label); if (Object.hasOwn(state.faults, label)) throw state.faults[label]; };
  const body = new Proxy({}, { get(_target, key) {
    if (key === "then") return undefined;
    assert.equal(key, "revision"); step("revision"); return state.revision;
  }, ownKeys() { throw Error("PUBLIC: body enumeration forbidden"); } });
  state.body = body;
  const originalMethod = function(this: unknown, ...args: unknown[]) {
    step("invoke"); seen.invocations.push(args); seen.receivers.push(this); return state.result;
  };
  const registry = new Proxy({}, { get(_target, key) {
    assert.equal(key, "changeMount"); step("method"); state.onMethod?.();
    return state.methodSet ? state.method : originalMethod;
  }, ownKeys() { throw Error("PUBLIC: registry enumeration forbidden"); } });
  const params = new Proxy({}, { get(_target, key) { assert.equal(key, "id"); step("id"); return state.id; },
    ownKeys() { throw Error("PUBLIC: params enumeration forbidden"); } });
  const wrapped = [() => { throw Error("PUBLIC: inert PATCH wrapper"); }, () => { throw Error("PUBLIC: inert DELETE wrapper"); }];
  const http = {
    kvHuman(...args: any[]) { seen.wrappers.push(args); return wrapped[seen.wrappers.length - 1]; },
    get kvBody() { step("bodyMethod"); return function(this: unknown, ...args: unknown[]) {
      step("body"); seen.bodies.push({ receiver: this, args }); return state.body;
    }; },
  };
  const schemas = new Proxy({}, { get(_target, key) {
    assert.equal(key, "removeMetadata"); step("schema"); return state.schema;
  } });
  const m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, require(name: string) {
    if (name === "@/lib/kv-http") return http;
    assert.equal(name, "@/lib/kv-schemas"); return schemas;
  } }, { filename: file, timeout: 5000 });
  assert.deepEqual(calls as unknown, []);
  return { calls, seen, actor, id, request, schema, revision, result, body, state, registry, params,
    originalMethod, wrapped, exports: m.exports,
    invoke: (r: unknown = registry, a: unknown = actor, q: unknown = request, p: unknown = params) => seen.wrappers[1][0](r, a, q, p) };
}
test("mount DELETE exact SOURCE delegation", async t => {
  await t.test("registers two exact default-status wrappers and nodejs runtime without executing PATCH", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["DELETE", "PATCH", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.PATCH, f.wrapped[0]); assert.equal(f.exports.DELETE, f.wrapped[1]);
    assert.equal(f.seen.wrappers.length, 2);
    for (const args of f.seen.wrappers) { assert.equal(args.length, 1); assert.equal(typeof args[0], "function"); }
    assert.notEqual(f.seen.wrappers[0][0], f.seen.wrappers[1][0]); assert.deepEqual(f.calls, []);
  });
  await t.test("captures method before exact body delegation then invokes actor/id/revision/null on original receiver", async () => {
    const f = fixture(), p = f.invoke(); assert.deepEqual(f.calls, prefix);
    assert.equal(await p, f.result); assert.deepEqual(f.calls, sequence);
    assert.equal(f.seen.bodies.length, 1); assert.equal(f.seen.bodies[0].receiver, undefined);
    assert.deepEqual(f.seen.bodies[0].args, [f.request, f.schema]);
    assert.deepEqual(f.seen.invocations, [[f.actor, f.id, f.revision, null]]); assert.equal(f.seen.receivers[0], f.registry);
  });
  for (const stage of sequence) for (const kind of ["error", "object"])
    await t.test(`exact ${stage} ${kind} refusal stops later work`, async () => {
      const f = fixture(), fault = kind === "error" ? Error("PUBLIC-FAULT") : Object.freeze({ public: "REFUSAL" });
      f.state.faults[stage] = fault; await assert.rejects(f.invoke(), e => e === fault);
      assert.deepEqual(f.calls, sequence.slice(0, sequence.indexOf(stage) + 1)); assert.deepEqual(f.seen.invocations, []);
    });
  await t.test("held body prevents revision and invocation while preserving already captured method", async () => {
    const f = fixture(), d = deferred(); f.state.body = d.promise;
    const p = f.invoke(); await turns(); assert.deepEqual(f.calls, prefix);
    f.state.methodSet = true; f.state.method = () => { throw Error("PUBLIC: replacement must not run"); };
    f.state.id = opaque("replacement id"); d.resolve(f.body);
    assert.equal(await p, f.result); assert.deepEqual(f.calls, sequence);
    assert.deepEqual(f.seen.invocations[0], [f.actor, f.id, f.revision, null]);
  });
  await t.test("rejected body preserves refusal identity and never reads revision or invokes", async () => {
    const f = fixture(), d = deferred(), fault = Object.freeze({ public: "BODY-REFUSAL" }); f.state.body = d.promise;
    const p = f.invoke(); d.reject(fault); await assert.rejects(p, e => e === fault); assert.deepEqual(f.calls, prefix);
  });
  for (const value of [undefined, null]) await t.test(`nullish resolved body ${String(value)} refuses after delegation`, async () => {
    const f = fixture(); f.state.body = value;
    await assert.rejects(f.invoke(), e => (e as Error).name === "TypeError"); assert.deepEqual(f.calls, prefix); assert.deepEqual(f.seen.invocations, []);
  });
  for (const value of [undefined, null, 9]) await t.test(`noncallable method ${String(value)} refuses after body revision`, async () => {
    const f = fixture(); f.state.methodSet = true; f.state.method = value;
    await assert.rejects(f.invoke(), e => (e as Error).name === "TypeError"); assert.deepEqual(f.calls, sequence.slice(0, -1));
  });
  for (const [label, value] of Object.entries({ missing: undefined, empty: null, zero: 0, blank: "", text: "PUBLIC", bool: false,
    object: Object.freeze({ public: "REVISION" }), symbol: Symbol("PUBLIC") })) await t.test(`revision ${label} forwards without local coercion or validation`, async () => {
      const f = fixture(); f.state.revision = value; assert.equal(await f.invoke(), f.result);
      assert.equal(f.seen.invocations[0][2], value); assert.equal(f.seen.invocations[0][3], null); assert.deepEqual(f.calls, sequence);
    });
  for (const [label, value] of Object.entries({ absent: undefined, empty: null, zero: 0, blank: "", text: "PUBLIC", bool: false,
    object: Object.freeze({ public: "RESULT" }) })) await t.test(`adopts plain result ${label} by resolved identity`, async () => {
      const f = fixture(); f.state.result = value; assert.equal(await f.invoke(), value); assert.deepEqual(f.calls, sequence);
    });
  await t.test("held method result is adopted without raw promise identity claim", async () => {
    const f = fixture(), d = deferred(); f.state.result = d.promise;
    let settled = false; const p = f.invoke(); void p.then(() => { settled = true; });
    await turns(); assert.equal(settled, false); assert.deepEqual(f.calls, sequence); d.resolve(f.result); assert.equal(await p, f.result);
  });
  await t.test("rejected method result preserves exact refusal without retry", async () => {
    const f = fixture(), d = deferred(), fault = Object.freeze({ public: "METHOD-REFUSAL" }); f.state.result = d.promise;
    const p = f.invoke(); await turns(); d.reject(fault); await assert.rejects(p, e => e === fault); assert.deepEqual(f.calls, sequence);
  });
  await t.test("body thenable resolves before one revision read", async () => {
    const f = fixture(); f.state.body = { then(resolve: (v: unknown) => void) { f.calls.push("bodyThen"); resolve(f.body); } };
    assert.equal(await f.invoke(), f.result); assert.deepEqual(f.calls, [...prefix, "bodyThen", "revision", "invoke"]);
  });
  await t.test("method thenable resolves once to exact identity", async () => {
    const f = fixture(); f.state.result = { then(resolve: (v: unknown) => void) { f.calls.push("resultThen"); resolve(f.result); } };
    assert.equal(await f.invoke(), f.result); assert.deepEqual(f.calls, [...sequence, "resultThen"]);
  });
  await t.test("fresh invocation retrieves a new method and selected schema", async () => {
    const f = fixture(); await f.invoke(); const nextSchema = opaque("next schema"), nextResult = Object.freeze({ public: "NEXT" });
    let receiver: unknown, args: unknown[] = []; f.state.schema = nextSchema; f.state.methodSet = true;
    f.state.method = function(this: unknown, ...a: unknown[]) { receiver = this; args = a; return nextResult; };
    assert.equal(await f.invoke(), nextResult); assert.equal(receiver, f.registry); assert.deepEqual(args, [f.actor, f.id, f.revision, null]);
    assert.equal(f.seen.bodies[1].args[1], nextSchema); assert.equal(f.calls.filter(x => x === "method").length, 2);
  });
  await t.test("interleaved held bodies retain separate captured methods actors ids and requests", async () => {
    const f = fixture(), a = deferred(), b = deferred(), collected: Model[] = [];
    const method = (label: string) => function(this: unknown, ...args: unknown[]) { collected.push({ label, receiver: this, args }); return label; };
    const actorB = opaque("actor B"), idB = opaque("id B"), requestB = opaque("request B"), revB = Object.freeze({ public: "REV-B" });
    f.state.methodSet = true; f.state.method = method("A"); f.state.body = a.promise; const pa = f.invoke();
    f.state.id = idB; f.state.method = method("B"); f.state.body = b.promise; const pb = f.invoke(f.registry, actorB, requestB);
    await turns(); assert.deepEqual(collected, []); b.resolve({ revision: revB }); assert.equal(await pb, "B");
    a.resolve(f.body); assert.equal(await pa, "A");
    assert.deepEqual(collected, [{ label: "B", receiver: f.registry, args: [actorB, idB, revB, null] },
      { label: "A", receiver: f.registry, args: [f.actor, f.id, f.revision, null] }]);
    assert.deepEqual(f.seen.bodies.map((x: Model) => x.args[0]), [f.request, requestB]);
  });
  await t.test("id is captured before a method getter changes params and schema is selected afterward", async () => {
    const f = fixture(), nextSchema = opaque("getter schema"); f.state.onMethod = () => { f.state.id = opaque("changed id"); f.state.schema = nextSchema; };
    await f.invoke(); assert.equal(f.seen.invocations[0][1], f.id); assert.equal(f.seen.bodies[0].args[1], nextSchema); assert.deepEqual(f.calls, sequence);
  });
  await t.test("inherited revision is read without enumerating unrelated or symbol getters", async () => {
    const f = fixture(), body = Object.create({ get revision() { f.calls.push("revision"); return f.revision; } });
    Object.defineProperty(body, "ignored", { enumerable: true, get() { throw Error("PUBLIC: unrelated read"); } });
    Object.defineProperty(body, Symbol("ignored"), { enumerable: true, get() { throw Error("PUBLIC: symbol read"); } });
    f.state.body = body; await f.invoke(); assert.deepEqual(f.calls, sequence); assert.equal(f.seen.invocations[0][2], f.revision);
  });
  await t.test("null context refuses destructuring before registry or body", async () => {
    const f = fixture(); await assert.rejects(f.invoke(f.registry, f.actor, f.request, null), e => (e as Error).name === "TypeError"); assert.deepEqual(f.calls, []);
  });
  await t.test("null registry refuses after id but before body", async () => {
    const f = fixture(); await assert.rejects(f.invoke(null), e => (e as Error).name === "TypeError"); assert.deepEqual(f.calls, ["id"]);
  });
});
