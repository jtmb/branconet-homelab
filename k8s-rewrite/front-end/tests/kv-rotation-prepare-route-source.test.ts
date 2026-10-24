import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC POST SOURCE controls. All imported implementations are inert.
// GET/PATCH are captured but never called. No values, parsing or rotation runs.
type Model = Record<string, any>;
const path = "src/app/api/kv/rotations/route.ts";
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
  return new Proxy({}, { get() { throw Error(`PUBLIC unexpected ${label} access`); }, ownKeys() { throw Error(`PUBLIC unexpected ${label} enumeration`); } });
}
function fixture() {
  const trace: string[] = [], wrappers: any[][] = [], markers: unknown[] = [], engines: unknown[][] = [], bodies: unknown[][] = [], constructions: Model[] = [], calls: Model[] = [];
  const registry = opaque("registry"), actor = opaque("actor"), request = opaque("request"), params = opaque("params"), schema = opaque("schema"), engine = opaque("engine");
  const body = Object.freeze({ public: "INPUT" }), result = Object.freeze({ public: "RESULT" }), fault = Error("PUBLIC-FAULT");
  const state: Model = { ctor: null, engineFn: null, bodyFn: null, engine, rotation: null, method: null, body, result,
    ctorGetterFault: null, engineGetterFault: null, engineFault: null, constructFault: null, methodFault: null, bodyGetterFault: null, schemaFault: null, bodyFault: null, callFault: null,
    rejectBody: false, rejectCall: false, ctorGetterHook: null, engineHook: null, constructHook: null, methodHook: null, bodyGetterHook: null, schemaHook: null, bodyHook: null };
  function method(this: unknown, ...args: unknown[]) {
    trace.push("call"); calls.push({ receiver: this, args });
    if (state.callFault) { if (state.rejectCall) return Promise.reject(state.callFault); throw state.callFault; }
    return state.result;
  }
  const rotation = Object.defineProperty({}, "prepare", { get() { trace.push("method"); if (state.methodHook) state.methodHook(); if (state.methodFault) throw state.methodFault; return state.method; } });
  function Rotations(this: unknown, ...args: unknown[]) {
    trace.push("construct"); constructions.push({ receiver: this, newTarget: new.target, args });
    if (state.constructHook) state.constructHook(); if (state.constructFault) throw state.constructFault; return state.rotation;
  }
  function engineFn(...args: unknown[]) {
    trace.push("engine"); engines.push(args); if (state.engineHook) state.engineHook(); if (state.engineFault) throw state.engineFault; return state.engine;
  }
  state.ctor = Rotations; state.engineFn = engineFn; state.rotation = rotation; state.method = method;
  state.bodyFn = (...args: unknown[]) => {
    trace.push("body"); bodies.push(args); if (state.bodyHook) state.bodyHook();
    if (state.bodyFault) { if (state.rejectBody) return Promise.reject(state.bodyFault); throw state.bodyFault; } return state.body;
  };
  const inert = opaque("unselected import");
  const http = { kvHuman(...args: any[]) { wrappers.push(args); const marker = Object.freeze({ public: `WRAPPER-${markers.length}` }); markers.push(marker); return marker; },
    get kvEngine() { trace.push("engine-get"); if (state.engineGetterFault) throw state.engineGetterFault; return state.engineFn; },
    get kvBody() { trace.push("body-get"); if (state.bodyGetterHook) state.bodyGetterHook(); if (state.bodyGetterFault) throw state.bodyGetterFault; return state.bodyFn; },
    get metadataCursor() { throw fault; } };
  const rotations = { get KvRotations() { trace.push("ctor-get"); if (state.ctorGetterHook) state.ctorGetterHook(); if (state.ctorGetterFault) throw state.ctorGetterFault; return state.ctor; } };
  const schemas = { get rotationPrepare() { trace.push("schema"); if (state.schemaHook) state.schemaHook(); if (state.schemaFault) throw state.schemaFault; return schema; }, get rotationAction() { throw fault; } };
  const imports: Model = { "zod": inert, "@/lib/kv-contract": inert, "@/lib/kv-http": http, "@/lib/kv-rotation": rotations, "@/lib/kv-schemas": schemas, "@/lib/kv-rotation-consumer": inert, "@/lib/k8s": inert };
  const m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, require: (id: string) => { assert.ok(Object.hasOwn(imports, id)); return imports[id]; } }, { filename: path, timeout: 5000 });
  assert.equal(wrappers.length, 3); assert.deepEqual(trace, [] as string[]);
  const callback = wrappers[1][0];
  return { state, trace, wrappers, markers, engines, bodies, constructions, calls, registry, actor, request, params, schema, engine, body, result, fault, method, rotation, Rotations, exports: m.exports,
    invoke: (...args: unknown[]) => callback(args.length ? args[0] : registry, args.length > 1 ? args[1] : actor, args.length > 2 ? args[2] : request, args.length > 3 ? args[3] : params) as Promise<unknown> };
}
type Fixture = ReturnType<typeof fixture>;
const order = ["ctor-get", "engine-get", "engine", "construct", "method", "body-get", "schema", "body", "call"];
function exact(f: Fixture, ...values: unknown[]) {
  const actor = values.length ? values[0] : f.actor, body = values.length > 1 ? values[1] : f.body, rotation = values.length > 2 ? values[2] : f.rotation;
  const call = f.calls.at(-1)!; assert.equal(call.receiver, rotation); assert.equal(call.args.length, 2); assert.equal(call.args[0], actor); assert.equal(call.args[1], body);
}
function construction(f: Fixture, ...values: unknown[]) {
  const engine = values.length ? values[0] : f.engine, c = f.constructions.at(-1)!;
  assert.equal(c.args.length, 1); assert.equal(c.args[0], engine); assert.equal(c.newTarget, f.Rotations);
}
test("human rotation preparation POST exact SOURCE delegation", async t => {
  await t.test("nodejs force-dynamic and exact inert POST status201; siblings captured only", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["GET", "PATCH", "POST", "dynamic", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    for (const [i, name] of ["GET", "POST", "PATCH"].entries()) { assert.equal(f.exports[name], f.markers[i]); assert.equal(typeof f.wrappers[i][0], "function"); assert.equal(f.wrappers[i].length, i === 1 ? 2 : 1); }
    assert.equal(f.wrappers[1][1], 201); assert.deepEqual(f.trace, [] as string[]);
  });
  await t.test("exact constructor engine captured prepare body schema literal4096 await receiver order", async () => {
    const f = fixture(); assert.equal(await f.invoke(), f.result); exact(f); construction(f); assert.deepEqual(f.trace, order);
    assert.equal(f.engines.length, 1); assert.equal(f.engines[0].length, 1); assert.equal(f.engines[0][0], f.registry);
    assert.equal(f.constructions.length, 1); assert.equal(f.bodies.length, 1); assert.equal(f.bodies[0].length, 3); assert.equal(f.bodies[0][0], f.request); assert.equal(f.bodies[0][1], f.schema); assert.equal(f.bodies[0][2], 4096);
  });
  const faults: [string, number][] = [["ctorGetterFault", 1], ["engineGetterFault", 2], ["engineFault", 3], ["constructFault", 4], ["methodFault", 5], ["bodyGetterFault", 6], ["schemaFault", 7], ["bodyFault", 8], ["callFault", 9]];
  for (const [field, count] of faults) await t.test(`${field} exact refusal stops later stages`, async () => {
    const f = fixture(); f.state[field] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, count)); assert.equal(f.calls.length, field === "callFault" ? 1 : 0);
  });
  for (const value of [undefined, null, 7, {}, () => {}]) await t.test(`nonconstructible constructor ${String(value)} evaluates engine only`, async () => {
    const f = fixture(); f.state.ctor = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 3)); assert.equal(f.constructions.length, 0); assert.equal(f.bodies.length, 0);
  });
  await t.test("engine refusal wins over nonconstructible constructor", async () => { const f = fixture(); f.state.ctor = null; f.state.engineFault = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 3)); });
  for (const value of [undefined, null, 9, {}]) await t.test(`noncallable engine ${String(value)} prevents construction`, async () => { const f = fixture(); f.state.engineFn = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 2)); assert.equal(f.constructions.length, 0); });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-ENGINE")]) await t.test(`engine ${String(value)} forwarded without inspection`, async () => { const f = fixture(); f.state.engine = value; await f.invoke(); construction(f, value); exact(f); });
  await t.test("constructor getter selects engine before call", async () => { const f = fixture(), engine = opaque("replacement engine"); f.state.ctorGetterHook = () => { f.state.engine = engine; }; await f.invoke(); construction(f, engine); });
  await t.test("engine side effects cannot replace captured constructor", async () => { const f = fixture(); f.state.engineHook = () => { f.state.ctor = null; }; await f.invoke(); construction(f); exact(f); });
  await t.test("construction side effects select instance before prepare lookup", async () => { const f = fixture(), rotation = { prepare: f.method }; f.state.constructHook = () => { f.state.rotation = rotation; }; await f.invoke(); exact(f, f.actor, f.body, rotation); });
  await t.test("inherited prepare retains receiver without reading then", async () => { const f = fixture(), rotation = Object.create({ prepare: f.method }); Object.defineProperty(rotation, "then", { get() { throw f.fault; } }); f.state.rotation = rotation; await f.invoke(); exact(f, f.actor, f.body, rotation); });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-CONSTRUCTOR-RETURN")]) await t.test(`primitive constructor return ${String(value)} uses new instance`, async () => { const f = fixture(); f.state.rotation = value; Object.defineProperty(f.Rotations.prototype, "prepare", { value: f.method }); await f.invoke(); exact(f, f.actor, f.body, f.constructions[0].receiver); construction(f); });
  await t.test("callable returned instance retains prepare receiver", async () => { const f = fixture(), rotation = Object.assign(() => { throw f.fault; }, { prepare: f.method }); f.state.rotation = rotation; await f.invoke(); exact(f, f.actor, f.body, rotation); });
  for (const value of [undefined, null, 7, {}]) await t.test(`noncallable prepare ${String(value)} still awaits body`, async () => { const f = fixture(); f.state.method = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 8)); assert.equal(f.bodies.length, 1); assert.equal(f.calls.length, 0); });
  await t.test("missing prepare still awaits body", async () => { const f = fixture(); f.state.rotation = Object.create(null); await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, [...order.slice(0, 4), ...order.slice(5, 8)]); assert.equal(f.calls.length, 0); });
  await t.test("body refusal wins over noncallable prepare", async () => { const f = fixture(); f.state.method = null; f.state.bodyFault = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 8)); });
  await t.test("held body delays noncallable prepare refusal", async () => { const f = fixture(), held = deferred(); f.state.method = null; f.state.body = held.promise; let settled = false; const pending = assert.rejects(f.invoke(), isError).then(() => { settled = true; }); await turns(); assert.equal(settled, false); assert.deepEqual(f.trace, order.slice(0, 8)); held.resolve(f.body); await pending; });
  for (const value of [undefined, null, 7, {}]) await t.test(`noncallable body ${String(value)} reads schema before refusal`, async () => { const f = fixture(); f.state.bodyFn = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 7)); assert.equal(f.calls.length, 0); });
  await t.test("schema refusal wins over noncallable body", async () => { const f = fixture(); f.state.bodyFn = null; f.state.schemaFault = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 7)); });
  await t.test("method getter cannot replace captured receiver", async () => { const f = fixture(); f.state.methodHook = () => { f.state.rotation = null; }; await f.invoke(); exact(f); });
  await t.test("body getter side effect cannot replace captured prepare", async () => { const f = fixture(); f.state.bodyGetterHook = () => { f.state.method = null; f.state.rotation = null; }; await f.invoke(); exact(f); });
  await t.test("schema getter cannot replace captured body function", async () => { const f = fixture(); f.state.schemaHook = () => { f.state.bodyFn = null; }; await f.invoke(); exact(f); });
  await t.test("body side effects preserve captured instance method engine", async () => { const f = fixture(); f.state.bodyHook = () => { f.state.rotation = null; f.state.method = null; f.state.engine = null; }; await f.invoke(); exact(f); construction(f); });
  await t.test("rejected body promise preserves exact refusal", async () => { const f = fixture(); f.state.bodyFault = f.fault; f.state.rejectBody = true; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 8)); assert.equal(f.calls.length, 0); });
  await t.test("held body retains captured prepare receiver and engine", async () => { const f = fixture(), held = deferred(); f.state.body = held.promise; const pending = f.invoke(); await turns(); assert.deepEqual(f.trace, order.slice(0, 8)); f.state.method = null; f.state.rotation = null; f.state.engine = null; held.resolve(f.body); assert.equal(await pending, f.result); exact(f); construction(f); assert.equal(f.constructions.length, 1); });
  await t.test("held body rejection never invokes prepare", async () => { const f = fixture(), held = deferred(); f.state.body = held.promise; const pending = assert.rejects(f.invoke(), e => e === f.fault); await turns(); held.reject(f.fault); await pending; assert.equal(f.calls.length, 0); });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-BODY")]) await t.test(`resolved input ${String(value)} forwarded whole`, async () => { const f = fixture(); f.state.body = value; await f.invoke(); exact(f, f.actor, value); });
  await t.test("resolved input permits only await then read; no input fields or enumeration", async () => { const f = fixture(), reads: PropertyKey[] = [], body = new Proxy({}, { get(_t, key) { reads.push(key); assert.equal(key, "then"); return undefined; }, ownKeys() { throw f.fault; } }); f.state.body = body; await f.invoke(); exact(f, f.actor, body); assert.deepEqual(reads, ["then"]); });
  await t.test("throwing input then getter prevents prepare", async () => { const f = fixture(); f.state.body = { get then() { throw f.fault; } }; await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.calls.length, 0); });
  await t.test("input thenable adopts first resolved identity", async () => { const f = fixture(); f.state.body = { then(resolve: (v: unknown) => void, reject: (e: unknown) => void) { resolve(f.body); reject(f.fault); resolve(null); } }; await f.invoke(); exact(f); });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-RESULT")]) await t.test(`result ${String(value)} adopted`, async () => { const f = fixture(); f.state.result = value; assert.equal(await f.invoke(), value); exact(f); });
  await t.test("rejected prepare retains refusal without retry", async () => { const f = fixture(); f.state.callFault = f.fault; f.state.rejectCall = true; await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.calls.length, 1); });
  await t.test("held result delays settlement with one prepare call", async () => { const f = fixture(), held = deferred(); f.state.result = held.promise; let settled = false; const pending = f.invoke().then(v => { settled = true; return v; }); await turns(); assert.equal(settled, false); exact(f); held.resolve(f.result); assert.equal(await pending, f.result); assert.equal(f.calls.length, 1); });
  await t.test("held result rejection retained", async () => { const f = fixture(), held = deferred(); f.state.result = held.promise; const pending = assert.rejects(f.invoke(), e => e === f.fault); await turns(); held.reject(f.fault); await pending; assert.equal(f.calls.length, 1); });
  await t.test("result thenable adopts resolved identity only", async () => { const f = fixture(); f.state.result = { then(resolve: (v: unknown) => void, reject: (e: unknown) => void) { resolve(f.result); reject(f.fault); resolve(null); } }; assert.equal(await f.invoke(), f.result); });
  await t.test("throwing result then getter retained", async () => { const f = fixture(); f.state.result = { get then() { throw f.fault; } }; await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.calls.length, 1); });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-ARG")]) await t.test(`registry actor request params ${String(value)} passed without inspection`, async () => { const f = fixture(); await f.invoke(value, value, value, value); assert.equal(f.engines[0][0], value); assert.equal(f.bodies[0][0], value); exact(f, value); construction(f); });
  await t.test("inherited signal and input getters are never read", async () => { const f = fixture(), request = Object.create({ get signal() { throw f.fault; }, get url() { throw f.fault; } }), body = Object.create({ get pathId() { throw f.fault; }, get revision() { throw f.fault; } }); f.state.body = body; await f.invoke(f.registry, f.actor, request); assert.equal(f.bodies[0][0], request); exact(f, f.actor, body); });
  await t.test("fresh calls retain fresh registry actor request engine instance input", async () => { const f = fixture(); await f.invoke(); const registry = opaque("registryB"), actor = opaque("actorB"), request = opaque("requestB"), engine = opaque("engineB"), body = { public: "INPUT-B" }, rotation = { prepare: f.method }; f.state.engine = engine; f.state.rotation = rotation; f.state.body = body; await f.invoke(registry, actor, request); construction(f, engine); exact(f, actor, body, rotation); assert.equal(f.engines[1][0], registry); assert.equal(f.bodies[1][0], request); assert.equal(f.calls.length, 2); });
  await t.test("interleaved bodies keep captured instances engines actors inputs", async () => {
    const f = fixture(), a = deferred(), b = deferred(), bodyB = { public: "INPUT-B" }, resultB = { public: "RESULT-B" }, actorB = opaque("actorB"), registryB = opaque("registryB"), requestB = opaque("requestB"), engineB = opaque("engineB"), rotationB = { prepare: f.method };
    f.state.body = a.promise; const pa = f.invoke(); f.state.engine = engineB; f.state.rotation = rotationB; f.state.body = b.promise; const pb = f.invoke(registryB, actorB, requestB); await turns(); assert.equal(f.calls.length, 0); assert.equal(f.constructions.length, 2); assert.equal(f.constructions[0].args[0], f.engine); assert.equal(f.constructions[1].args[0], engineB);
    f.state.result = resultB; b.resolve(bodyB); assert.equal(await pb, resultB); exact(f, actorB, bodyB, rotationB); f.state.result = f.result; a.resolve(f.body); assert.equal(await pa, f.result); exact(f); assert.equal(f.calls.length, 2);
  });
  await t.test("interleaved result settlement stays with each invocation", async () => { const f = fixture(), a = deferred(), b = deferred(); f.state.result = a.promise; const pa = f.invoke(); await turns(); f.state.result = b.promise; const pb = f.invoke(); await turns(); assert.equal(f.calls.length, 2); b.resolve(f.body); assert.equal(await pb, f.body); a.resolve(f.result); assert.equal(await pa, f.result); });
});
