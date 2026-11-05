import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC GET SOURCE controls. Every imported implementation is inert.
// POST is captured and never invoked. No values, parsing or consumer operation.
type Model = Record<string, any>;
const path = "src/app/api/kv/rotations/[id]/consumer/route.ts";
const compiled = ts.transpileModule(readFileSync(path, "utf8"), {
  fileName: path, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
}).outputText;
function deferred() {
  let resolve!: (value: any) => void, reject!: (error: unknown) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const turns = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
const isError = (e: unknown) => Object.prototype.toString.call(e) === "[object Error]";
function opaque(label: string) {
  return new Proxy({}, { get() { throw Error(`PUBLIC unexpected ${label} read`); }, ownKeys() { throw Error(`PUBLIC unexpected ${label} enumeration`); } });
}
function fixture() {
  const trace: string[] = [], wrappers: any[][] = [], markers: unknown[] = [], engines: unknown[][] = [], consumers: Model[] = [], rotations: Model[] = [], calls: Model[] = [];
  const registry = opaque("registry"), actor = opaque("actor"), request = opaque("request"), engine = opaque("engine"), consumer = opaque("consumer"), id = opaque("id");
  const result = Object.freeze({ public: "RESULT" }), fault = Error("PUBLIC-FAULT");
  const state: Model = { faults: {}, hooks: {}, ctor: null, engineFn: null, consumerCtor: null, kubectl: null, engine, consumer, rotation: null, method: null, id, result, rejectCall: false };
  function stage(name: string) { trace.push(name); if (state.hooks[name]) state.hooks[name](); if (state.faults[name]) throw state.faults[name]; }
  function method(this: unknown, ...args: unknown[]) { stage("call"); calls.push({ receiver: this, args }); if (state.rejectCall) return Promise.reject(fault); return state.result; }
  const rotation = Object.defineProperty({}, "consumerPreview", { get() { stage("method"); return state.method; } });
  const params = Object.defineProperty({}, "id", { get() { stage("id"); return state.id; } });
  function Rotations(this: unknown, ...args: unknown[]) { stage("construct"); rotations.push({ receiver: this, newTarget: new.target, args }); return state.rotation; }
  function Consumer(this: unknown, ...args: unknown[]) { stage("consumer-construct"); consumers.push({ receiver: this, newTarget: new.target, args }); return state.consumer; }
  function engineFn(...args: unknown[]) { stage("engine"); engines.push(args); return state.engine; }
  function kubectl() { throw Error("PUBLIC kubectl must remain inert"); }
  state.ctor = Rotations; state.consumerCtor = Consumer; state.engineFn = engineFn; state.kubectl = kubectl; state.rotation = rotation; state.method = method;
  const http = { kvHuman(...args: any[]) { wrappers.push(args); const marker = Object.freeze({ public: `WRAPPER-${markers.length}` }); markers.push(marker); return marker; },
    get kvEngine() { stage("engine-get"); return state.engineFn; }, get kvBody() { throw fault; } };
  const imports: Model = { "@/lib/kv-http": http,
    "@/lib/kv-rotation": { get KvRotations() { stage("ctor-get"); return state.ctor; } },
    "@/lib/kv-rotation-consumer": { get KubectlRotationConsumer() { stage("consumer-ctor-get"); return state.consumerCtor; } },
    "@/lib/k8s": { get kubectlJSON() { stage("kubectl-get"); return state.kubectl; } },
    "@/lib/kv-schemas": opaque("schema import"), "@/lib/kv-contract": opaque("contract import") };
  const m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, require: (name: string) => { assert.ok(Object.hasOwn(imports, name)); return imports[name]; } }, { filename: path, timeout: 5000 });
  assert.equal(wrappers.length, 2); assert.deepEqual(trace, [] as string[]);
  const callback = wrappers[0][0];
  return { state, trace, wrappers, markers, engines, consumers, rotations, calls, registry, actor, request, params, engine, consumer, id, result, fault, method, rotation, Rotations, Consumer, kubectl, exports: m.exports,
    invoke: (...args: unknown[]) => callback(args.length ? args[0] : registry, args.length > 1 ? args[1] : actor, args.length > 2 ? args[2] : request, args.length > 3 ? args[3] : params) as Promise<unknown> };
}
type Fixture = ReturnType<typeof fixture>;
const order = ["ctor-get", "engine-get", "engine", "consumer-ctor-get", "kubectl-get", "consumer-construct", "construct", "method", "id", "call"];
function exact(f: Fixture, ...args: unknown[]) {
  const actor = args.length ? args[0] : f.actor, id = args.length > 1 ? args[1] : f.id, receiver = args.length > 2 ? args[2] : f.rotation;
  const call = f.calls.at(-1)!; assert.equal(call.receiver, receiver); assert.equal(call.args.length, 2); assert.equal(call.args[0], actor); assert.equal(call.args[1], id);
}
function construction(f: Fixture, ...args: unknown[]) {
  const engine = args.length ? args[0] : f.engine, consumer = args.length > 1 ? args[1] : f.consumer, kubectl = args.length > 2 ? args[2] : f.kubectl;
  const r = f.rotations.at(-1)!, c = f.consumers.at(-1)!;
  assert.equal(r.newTarget, f.Rotations); assert.equal(r.args.length, 2); assert.equal(r.args[0], engine); assert.equal(r.args[1], consumer);
  assert.equal(c.newTarget, f.Consumer); assert.equal(c.args.length, 1); assert.equal(c.args[0], kubectl);
}

test("human rotation consumer-preview GET exact SOURCE delegation", async t => {
  await t.test("nodejs force-dynamic exact default-status GET and inert POST wrappers", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["GET", "POST", "dynamic", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    for (const [i, name] of ["GET", "POST"].entries()) { assert.equal(f.exports[name], f.markers[i]); assert.equal(f.wrappers[i].length, 1); assert.equal(typeof f.wrappers[i][0], "function"); }
    assert.deepEqual(f.trace, [] as string[]);
  });
  await t.test("exact lookup construction receiver and actor/id order with unread request", async () => {
    const f = fixture(); assert.equal(await f.invoke(), f.result); exact(f); construction(f); assert.deepEqual(f.trace, order);
    assert.equal(f.engines.length, 1); assert.equal(f.engines[0].length, 1); assert.equal(f.engines[0][0], f.registry);
    assert.equal(f.rotations.length, 1); assert.equal(f.consumers.length, 1); assert.equal(f.calls.length, 1);
  });
  for (const [i, name] of order.entries()) await t.test(`${name} exact refusal prevents later stages`, async () => {
    const f = fixture(); f.state.faults[name] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, i + 1)); assert.equal(f.calls.length, 0);
  });
  for (const value of [undefined, null, 7, {}, () => {}]) await t.test(`nonconstructible rotation ${String(value)} still constructs consumer`, async () => {
    const f = fixture(); f.state.ctor = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 6)); assert.equal(f.rotations.length, 0); assert.equal(f.consumers.length, 1);
  });
  for (const name of ["engine", "consumer-ctor-get", "kubectl-get", "consumer-construct"]) await t.test(`${name} refusal wins over nonconstructible rotation`, async () => {
    const f = fixture(); f.state.ctor = null; f.state.faults[name] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, order.indexOf(name) + 1));
  });
  for (const value of [undefined, null, 8, {}]) await t.test(`noncallable engine ${String(value)} prevents consumer lookup`, async () => {
    const f = fixture(); f.state.engineFn = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 2)); assert.equal(f.consumers.length, 0);
  });
  for (const value of [undefined, null, 9, {}, () => {}]) await t.test(`nonconstructible consumer ${String(value)} still reads kubectl function`, async () => {
    const f = fixture(); f.state.consumerCtor = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 5)); assert.equal(f.rotations.length, 0);
  });
  await t.test("kubectl refusal wins over nonconstructible consumer", async () => { const f = fixture(); f.state.consumerCtor = null; f.state.faults["kubectl-get"] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 5)); });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC")]) {
    await t.test(`engine ${String(value)} passed without inspection`, async () => { const f = fixture(); f.state.engine = value; await f.invoke(); construction(f, value); exact(f); });
    await t.test(`kubectl ${String(value)} passed without invocation`, async () => { const f = fixture(); f.state.kubectl = value; await f.invoke(); construction(f, f.engine, f.consumer, value); exact(f); });
    await t.test(`consumer primitive return ${String(value)} uses new receiver`, async () => { const f = fixture(); f.state.consumer = value; await f.invoke(); construction(f, f.engine, f.consumers[0].receiver); exact(f); });
    await t.test(`rotation primitive return ${String(value)} uses new receiver`, async () => { const f = fixture(); f.state.rotation = value; Object.defineProperty(f.Rotations.prototype, "consumerPreview", { value: f.method }); await f.invoke(); exact(f, f.actor, f.id, f.rotations[0].receiver); construction(f); });
    await t.test(`id ${String(value)} passed unchanged without validation`, async () => { const f = fixture(); f.state.id = value; await f.invoke(); exact(f, f.actor, value); });
  }
  const changes: [string, string][] = [["engine-get", "ctor"], ["engine", "ctor"], ["consumer-ctor-get", "ctor"], ["kubectl-get", "consumerCtor"], ["consumer-construct", "consumerCtor"], ["construct", "ctor"], ["method", "rotation"], ["id", "method"], ["id", "rotation"]];
  for (const [stage, field] of changes) await t.test(`${stage} cannot replace captured ${field}`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state[field] = null; }; await f.invoke(); exact(f); construction(f); });
  await t.test("ctor getter chooses engine before engine lookup", async () => { const f = fixture(), engine = opaque("fresh engine"); f.state.hooks["ctor-get"] = () => { f.state.engine = engine; }; await f.invoke(); construction(f, engine); });
  await t.test("engine chooses consumer ctor before its capture", async () => { const f = fixture(); f.state.consumerCtor = null; f.state.hooks.engine = () => { f.state.consumerCtor = f.Consumer; }; await f.invoke(); construction(f); });
  await t.test("consumer ctor getter selects fresh kubectl", async () => { const f = fixture(), fn = () => { throw f.fault; }; f.state.hooks["consumer-ctor-get"] = () => { f.state.kubectl = fn; }; await f.invoke(); construction(f, f.engine, f.consumer, fn); });
  await t.test("kubectl getter selects consumer result before construction", async () => { const f = fixture(), c = opaque("fresh consumer"); f.state.hooks["kubectl-get"] = () => { f.state.consumer = c; }; await f.invoke(); construction(f, f.engine, c); });
  await t.test("consumer construction cannot replace captured engine", async () => { const f = fixture(); f.state.hooks["consumer-construct"] = () => { f.state.engine = null; }; await f.invoke(); construction(f); });
  await t.test("rotation construction selects instance before method lookup", async () => { const f = fixture(), r = { consumerPreview: f.method }; f.state.hooks.construct = () => { f.state.rotation = r; }; await f.invoke(); exact(f, f.actor, f.id, r); });
  await t.test("method getter chooses fresh id before id read", async () => { const f = fixture(), id = opaque("fresh id"); f.state.hooks.method = () => { f.state.id = id; }; await f.invoke(); exact(f, f.actor, id); });
  await t.test("inherited method retains instance receiver without then read", async () => { const f = fixture(), r = Object.create({ consumerPreview: f.method }); Object.defineProperty(r, "then", { get() { throw f.fault; } }); f.state.rotation = r; await f.invoke(); exact(f, f.actor, f.id, r); });
  await t.test("callable returned rotation is not invoked", async () => { const f = fixture(), r = Object.assign(() => { throw f.fault; }, { consumerPreview: f.method }); f.state.rotation = r; await f.invoke(); exact(f, f.actor, f.id, r); });
  await t.test("callable returned consumer is passed without then read", async () => { const f = fixture(), c = () => { throw f.fault; }; Object.defineProperty(c, "then", { get() { throw f.fault; } }); f.state.consumer = c; await f.invoke(); construction(f, f.engine, c); });
  for (const value of [undefined, null, 3, {}]) await t.test(`noncallable method ${String(value)} reads id before refusal`, async () => { const f = fixture(); f.state.method = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 9)); assert.equal(f.calls.length, 0); });
  await t.test("missing method still reads id", async () => { const f = fixture(); f.state.rotation = Object.create(null); await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, [...order.slice(0, 7), "id"]); });
  await t.test("id refusal wins over noncallable method", async () => { const f = fixture(); f.state.method = null; f.state.faults.id = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 9)); });
  for (const value of [undefined, null]) await t.test(`nullish params ${String(value)} refuse after method lookup`, async () => { const f = fixture(); await assert.rejects(f.invoke(f.registry, f.actor, f.request, value), isError); assert.deepEqual(f.trace, order.slice(0, 8)); });
  for (const value of [false, 0, "", Symbol("PUBLIC-PARAMS"), Object.create(null)]) await t.test(`params ${String(value === null ? null : typeof value)} missing id forwards undefined`, async () => { const f = fixture(); await f.invoke(f.registry, f.actor, f.request, value); exact(f, f.actor, undefined); });
  await t.test("inherited id getter uses original params receiver exactly once", async () => { const f = fixture(); let count = 0; const p = Object.create({ get id() { count++; assert.equal(this, p); return f.id; } }); await f.invoke(f.registry, f.actor, f.request, p); exact(f); assert.equal(count, 1); });
  await t.test("params only id is inspected", async () => { const f = fixture(), reads: PropertyKey[] = [], p = new Proxy({}, { get(_t, k) { reads.push(k); assert.equal(k, "id"); return f.id; }, ownKeys() { throw f.fault; } }); await f.invoke(f.registry, f.actor, f.request, p); exact(f); assert.deepEqual(reads, ["id"]); });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-ARG"), Object.freeze({ public: "ARG" })]) {
    await t.test(`registry ${String(typeof value)} delegated exactly`, async () => { const f = fixture(); await f.invoke(value); assert.equal(f.engines[0][0], value); exact(f); });
    await t.test(`actor ${String(typeof value)} delegated exactly`, async () => { const f = fixture(); await f.invoke(f.registry, value); exact(f, value); });
    await t.test(`request ${String(typeof value)} never read`, async () => { const f = fixture(); await f.invoke(f.registry, f.actor, value); exact(f); });
  }
  await t.test("registry engine consumer id then getters are never inspected", async () => {
    const f = fixture(); const value = () => Object.defineProperty({}, "then", { get() { throw f.fault; } });
    const registry = value(), engine = value(), consumer = value(), id = value(); f.state.engine = engine; f.state.consumer = consumer; f.state.id = id;
    await f.invoke(registry); construction(f, engine, consumer); exact(f, f.actor, id); assert.equal(f.engines[0][0], registry);
  });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-RESULT"), Object.freeze({ public: "RESULT2" })]) await t.test(`result ${String(typeof value)} adopts resolved identity`, async () => { const f = fixture(); f.state.result = value; assert.equal(await f.invoke(), value); exact(f); });
  await t.test("method rejected promise keeps exact refusal without retry", async () => { const f = fixture(); f.state.rejectCall = true; await assert.rejects(f.invoke(), e => e === f.fault); exact(f); assert.equal(f.calls.length, 1); });
  await t.test("held method result settles once with resolved identity", async () => { const f = fixture(), d = deferred(); f.state.result = d.promise; let settled = false; const p = f.invoke().then(v => { settled = true; return v; }); await turns(); assert.equal(settled, false); exact(f); assert.deepEqual(f.trace, order); d.resolve(f.result); assert.equal(await p, f.result); assert.equal(f.calls.length, 1); });
  await t.test("held method rejection retains exact refusal", async () => { const f = fixture(), d = deferred(); f.state.result = d.promise; const p = assert.rejects(f.invoke(), e => e === f.fault); await turns(); d.reject(f.fault); await p; assert.equal(f.calls.length, 1); });
  await t.test("result thenable adopts first resolution and ignores later rejection", async () => { const f = fixture(); f.state.result = { then(resolve: (x: unknown) => void, reject: (e: unknown) => void) { resolve(f.result); reject(f.fault); resolve(null); } }; assert.equal(await f.invoke(), f.result); exact(f); assert.equal(f.calls.length, 1); });
  await t.test("throwing result then getter retains exact refusal", async () => { const f = fixture(); f.state.result = { get then() { throw f.fault; } }; await assert.rejects(f.invoke(), e => e === f.fault); exact(f); });
  await t.test("result proxy exposes only await then read", async () => { const f = fixture(), reads: PropertyKey[] = [], r = new Proxy({}, { get(_t, k) { reads.push(k); assert.equal(k, "then"); return undefined; }, ownKeys() { throw f.fault; } }); f.state.result = r; assert.equal(await f.invoke(), r); assert.deepEqual(reads, ["then", "then"]); exact(f); });
  await t.test("sequential invocations use fresh engine consumer rotation and id", async () => {
    const f = fixture(); await f.invoke(); const e = opaque("engine2"), c = opaque("consumer2"), id = opaque("id2"), r = { consumerPreview: f.method }, result = Object.freeze({ public: "RESULT2" });
    f.state.engine = e; f.state.consumer = c; f.state.rotation = r; f.state.id = id; f.state.result = result;
    assert.equal(await f.invoke(), result); construction(f, e, c); exact(f, f.actor, id, r); assert.equal(f.engines.length, 2); assert.equal(f.consumers.length, 2); assert.equal(f.rotations.length, 2); assert.equal(f.calls.length, 2);
  });
  await t.test("interleaved results keep per-call instance actor and id", async () => {
    const f = fixture(), one = deferred(), two = deferred(), a = opaque("actor2"), id = opaque("id2"), r = { consumerPreview: f.method }, result = Object.freeze({ public: "RESULT2" });
    f.state.result = one.promise; const first = f.invoke(); exact(f);
    f.state.result = two.promise; f.state.rotation = r; f.state.id = id; const second = f.invoke(f.registry, a); exact(f, a, id, r);
    two.resolve(result); assert.equal(await second, result); one.resolve(f.result); assert.equal(await first, f.result); assert.equal(f.calls.length, 2); assert.equal(f.rotations.length, 2);
  });
  await t.test("refusal does not poison a fresh invocation", async () => { const f = fixture(); f.state.faults.method = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); delete f.state.faults.method; assert.equal(await f.invoke(), f.result); exact(f); assert.equal(f.rotations.length, 2); assert.equal(f.calls.length, 1); });
});
