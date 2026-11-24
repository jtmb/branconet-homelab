import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC POST SOURCE controls; actual imports and sibling GET are inert.
// No body/schema parsing, values, consumer operations, backend or network execution.
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
  return new Proxy({}, { get() { throw Error(`PUBLIC unexpected ${label} access`); }, ownKeys() { throw Error(`PUBLIC unexpected ${label} enumeration`); } });
}
function fixture() {
  const trace: string[] = [], wrappers: any[][] = [], markers: unknown[] = [], bodies: unknown[][] = [], engines: unknown[][] = [], rotations: Model[] = [], consumers: Model[] = [], calls: Model[] = [], errors: Model[] = [];
  const registry = opaque("registry"), actor = opaque("actor"), schema = opaque("schema"), engine = opaque("engine"), consumer = opaque("consumer"), id = opaque("id"), signal = opaque("signal");
  const result = Object.freeze({ public: "RESULT" }), fault = Error("PUBLIC-FAULT"), refusal = Error("PUBLIC-TARGET-REFUSAL");
  const state: Model = { schema, engine, consumer, inputId: id, firstId: id, secondId: id, signal, result, refusal, kubectl: opaque("kubectl"), faults: {}, hooks: {} };
  function step(name: string) { trace.push(name); if (state.hooks[name]) state.hooks[name](); if (state.faults[name]) throw state.faults[name]; }
  const input = Object.defineProperty({}, "rotationId", { get() { step("input-id"); return state.inputId; } });
  const request = new Proxy({}, { get(_t, k) { assert.equal(k, "signal"); step("signal"); return state.signal; }, ownKeys() { throw fault; } });
  let idReads = 0;
  const params = new Proxy({}, { get(_t, k) { assert.equal(k, "id"); const n = ++idReads; assert.ok(n <= 2); step("id" + n); return n === 1 ? state.firstId : state.secondId; }, ownKeys() { throw fault; } });
  const method = function(this: unknown, ...args: unknown[]) { calls.push({ receiver: this, args }); step("call"); if (state.rejectCall) return Promise.reject(fault); return state.result; };
  const rotation = Object.defineProperty({}, "reload", { get() { step("method"); return state.method; } });
  function Rotations(this: unknown, ...args: unknown[]) { rotations.push({ receiver: this, args, newTarget: new.target }); step("construct"); return state.rotation; }
  function Consumer(this: unknown, ...args: unknown[]) { consumers.push({ receiver: this, args, newTarget: new.target }); step("consumer-construct"); return state.consumer; }
  function TargetError(this: unknown, ...args: unknown[]) { errors.push({ receiver: this, args, newTarget: new.target }); step("error-construct"); return state.refusal; }
  state.input = input; state.method = method; state.rotation = rotation; state.ctor = Rotations; state.consumerCtor = Consumer; state.errorCtor = TargetError;
  state.bodyFn = (...args: unknown[]) => { bodies.push(args); step("body"); if (state.rejectBody) return Promise.reject(fault); return state.input; };
  state.engineFn = (...args: unknown[]) => { engines.push(args); step("engine"); return state.engine; };
  const imports: Model = {
    "@/lib/kv-http": { kvHuman(...args: any[]) { wrappers.push(args); const marker = Object.freeze({ public: `WRAPPER-${markers.length}` }); markers.push(marker); return marker; }, get kvBody() { step("body-get"); return state.bodyFn; }, get kvEngine() { step("engine-get"); return state.engineFn; } },
    "@/lib/kv-schemas": { get rotationReload() { step("schema"); return state.schema; } },
    "@/lib/kv-contract": { get KvError() { step("error-get"); return state.errorCtor; } },
    "@/lib/kv-rotation": { get KvRotations() { step("ctor-get"); return state.ctor; } },
    "@/lib/kv-rotation-consumer": { get KubectlRotationConsumer() { step("consumer-ctor-get"); return state.consumerCtor; } },
    "@/lib/k8s": { get kubectlJSON() { step("kubectl-get"); return state.kubectl; } }
  };
  const m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, require: (name: string) => { assert.ok(Object.hasOwn(imports, name)); return imports[name]; } }, { filename: path, timeout: 5000 });
  assert.equal(wrappers.length, 2); assert.deepEqual(trace, [] as string[]);
  const callback = wrappers[1][0];
  return { state, trace, wrappers, markers, bodies, engines, rotations, consumers, calls, errors, registry, actor, schema, engine, consumer, id, signal, input, request, params, method, rotation, result, fault, refusal, Rotations, Consumer, TargetError, exports: m.exports,
    invoke: (...args: unknown[]) => { idReads = 0; return callback(args.length ? args[0] : registry, args.length > 1 ? args[1] : actor, args.length > 2 ? args[2] : request, args.length > 3 ? args[3] : params) as Promise<unknown>; } };
}
type Fixture = ReturnType<typeof fixture>;
const order = ["body-get", "schema", "body", "input-id", "id1", "ctor-get", "engine-get", "engine", "consumer-ctor-get", "kubectl-get", "consumer-construct", "construct", "method", "id2", "signal", "call"];
function exact(f: Fixture, ...values: unknown[]) {
  const expected = [values.length ? values[0] : f.actor, values.length > 1 ? values[1] : f.id, values.length > 2 ? values[2] : f.input, values.length > 3 ? values[3] : f.signal];
  const c = f.calls.at(-1)!; assert.equal(c.receiver, values.length > 4 ? values[4] : f.rotation); assert.equal(c.args.length, 4); expected.forEach((v, i) => assert.equal(c.args[i], v));
}
function construction(f: Fixture, ...values: unknown[]) {
  const e = values.length ? values[0] : f.engine, c = values.length > 1 ? values[1] : f.consumer, k = values.length > 2 ? values[2] : f.state.kubectl;
  const r = f.rotations.at(-1)!, d = f.consumers.at(-1)!;
  assert.equal(r.newTarget, f.Rotations); assert.equal(r.args.length, 2); assert.equal(r.args[0], e); assert.equal(r.args[1], c);
  assert.equal(d.newTarget, f.Consumer); assert.equal(d.args.length, 1); assert.equal(d.args[0], k);
}
function mismatch(f: Fixture) { assert.equal(f.errors.length, 1); const e = f.errors[0]; assert.equal(e.newTarget, f.TargetError); assert.equal(e.args.length, 2); assert.equal(e.args[0], 400); assert.equal(e.args[1], "Rotation target must match the route"); assert.equal(f.rotations.length, 0); assert.equal(f.consumers.length, 0); assert.equal(f.engines.length, 0); assert.equal(f.calls.length, 0); }

test("human rotation consumer reload POST exact SOURCE delegation", async t => {
  await t.test("nodejs force-dynamic exact default POST and inert GET wrappers", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["GET", "POST", "dynamic", "runtime"]); assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    for (const [i, name] of ["GET", "POST"].entries()) { assert.equal(f.wrappers[i].length, 1); assert.equal(typeof f.wrappers[i][0], "function"); assert.equal(f.exports[name], f.markers[i]); } assert.deepEqual(f.trace, [] as string[]);
  });
  await t.test("exact body await two id reads construction receiver and four arguments", async () => {
    const f = fixture(); assert.equal(await f.invoke(), f.result); assert.deepEqual(f.trace, order); exact(f); construction(f); assert.equal(f.errors.length, 0);
    assert.equal(f.bodies.length, 1); assert.equal(f.bodies[0].length, 3); assert.equal(f.bodies[0][0], f.request); assert.equal(f.bodies[0][1], f.schema); assert.equal(f.bodies[0][2], 4096);
    assert.equal(f.engines.length, 1); assert.equal(f.engines[0].length, 1); assert.equal(f.engines[0][0], f.registry); assert.equal(f.calls.length, 1);
  });
  for (const [i, name] of order.entries()) await t.test(`${name} refusal stops all later stages`, async () => {
    const f = fixture(); f.state.faults[name] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, i + 1)); assert.equal(f.calls.length, name === "call" ? 1 : 0);
  });
  await t.test("mismatch throws exactly constructed instance before any engine or consumer", async () => { const f = fixture(); f.state.inputId = opaque("other id"); await assert.rejects(f.invoke(), e => e === f.refusal); assert.deepEqual(f.trace, [...order.slice(0, 5), "error-get", "error-construct"]); mismatch(f); });
  for (const name of ["error-get", "error-construct"]) await t.test(`${name} refusal replaces target refusal only`, async () => { const f = fixture(); f.state.inputId = null; f.state.faults[name] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, [...order.slice(0, 5), "error-get", ...(name === "error-construct" ? [name] : [])]); assert.equal(f.rotations.length, 0); });
  for (const value of [undefined, null, 7, {}, () => {}]) await t.test(`nonconstructible error ${String(value)} stops without construction`, async () => { const f = fixture(); f.state.inputId = null; f.state.errorCtor = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, [...order.slice(0, 5), "error-get"]); assert.equal(f.errors.length, 0); assert.equal(f.rotations.length, 0); });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC")]) {
    await t.test(`same target ${String(value)} strict equality passes`, async () => { const f = fixture(); f.state.inputId = value; f.state.firstId = value; f.state.secondId = value; await f.invoke(); exact(f, f.actor, value); });
    await t.test(`second id ${String(value)} passed independently without a second comparison`, async () => { const f = fixture(); f.state.secondId = value; await f.invoke(); exact(f, f.actor, value); assert.deepEqual(f.trace, order); });
    await t.test(`signal ${String(value)} passed unchanged`, async () => { const f = fixture(); f.state.signal = value; await f.invoke(); exact(f, f.actor, f.id, f.input, value); });
    await t.test(`engine ${String(value)} passed without inspection`, async () => { const f = fixture(); f.state.engine = value; await f.invoke(); construction(f, value); });
    await t.test(`kubectl ${String(value)} passed without invocation`, async () => { const f = fixture(); f.state.kubectl = value; await f.invoke(); construction(f, f.engine, f.consumer, value); });
    await t.test(`consumer primitive return ${String(value)} uses new receiver`, async () => { const f = fixture(); f.state.consumer = value; await f.invoke(); construction(f, f.engine, f.consumers[0].receiver); });
    await t.test(`rotation primitive return ${String(value)} uses new receiver`, async () => { const f = fixture(); f.state.rotation = value; Object.defineProperty(f.Rotations.prototype, "reload", { value: f.method }); await f.invoke(); exact(f, f.actor, f.id, f.input, f.signal, f.rotations[0].receiver); });
    await t.test(`result ${String(value)} is adopted`, async () => { const f = fixture(); f.state.result = value; assert.equal(await f.invoke(), value); exact(f); });
    await t.test(`error primitive return ${String(value)} throws new receiver`, async () => { const f = fixture(); f.state.inputId = null; f.state.refusal = value; await assert.rejects(f.invoke(), e => e === f.errors[0].receiver); mismatch(f); });
  }
  for (const [left, right] of [[0, "0"], [false, 0], [null, undefined], [NaN, NaN], [Symbol("PUBLIC"), Symbol("PUBLIC")], [{}, {}]]) await t.test(`strict target mismatch ${String(left)} and ${String(right)}`, async () => { const f = fixture(); f.state.inputId = left; f.state.firstId = right; await assert.rejects(f.invoke(), e => e === f.refusal); mismatch(f); });
  await t.test("strict target equality never coerces matching object", async () => { const f = fixture(); await f.invoke(); exact(f); });
  for (const value of [undefined, null]) {
    await t.test(`nullish input ${String(value)} prevents even first params read`, async () => { const f = fixture(); f.state.input = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 3)); assert.equal(f.errors.length, 0); });
    await t.test(`nullish params ${String(value)} still reads input target first`, async () => { const f = fixture(); await assert.rejects(f.invoke(f.registry, f.actor, f.request, value), isError); assert.deepEqual(f.trace, order.slice(0, 4)); });
    await t.test(`nullish request ${String(value)} delegates to body before signal refusal`, async () => { const f = fixture(); await assert.rejects(f.invoke(f.registry, f.actor, value), isError); assert.deepEqual(f.trace, order.slice(0, 14)); assert.equal(f.bodies[0][0], value); });
  }
  for (const value of [7, false, "PUBLIC", Symbol("PUBLIC")]) await t.test(`primitive input ${String(value)} is unparsed and mismatches by missing target`, async () => { const f = fixture(); f.state.input = value; await assert.rejects(f.invoke(), e => e === f.refusal); mismatch(f); assert.deepEqual(f.trace, ["body-get", "schema", "body", "id1", "error-get", "error-construct"]); });
  await t.test("inherited input target and params id accepted without own-property restriction", async () => { const f = fixture(), input = Object.create({ rotationId: f.id }), params = Object.create({ id: f.id }); f.state.input = input; await f.invoke(f.registry, f.actor, f.request, params); exact(f, f.actor, f.id, input); });
  await t.test("missing input target equals missing params id without schema validation", async () => { const f = fixture(), input = Object.create(null); f.state.input = input; await f.invoke(f.registry, f.actor, f.request, Object.create(null)); exact(f, f.actor, undefined, input); });
  await t.test("inherited method keeps returned rotation as receiver", async () => { const f = fixture(), r = Object.create({ reload: f.method }); Object.defineProperty(r, "then", { get() { throw f.fault; } }); f.state.rotation = r; await f.invoke(); exact(f, f.actor, f.id, f.input, f.signal, r); });
  for (const value of [undefined, null, 8, {}]) {
    await t.test(`noncallable body ${String(value)} still reads schema`, async () => { const f = fixture(); f.state.bodyFn = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 2)); });
    await t.test(`noncallable engine ${String(value)} prevents consumer lookup`, async () => { const f = fixture(); f.state.engineFn = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 7)); });
    await t.test(`noncallable reload ${String(value)} still reads fresh second id and signal`, async () => { const f = fixture(); f.state.method = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, -1)); });
  }
  for (const value of [undefined, null, 9, {}, () => {}]) {
    await t.test(`nonconstructible rotation ${String(value)} still constructs consumer`, async () => { const f = fixture(); f.state.ctor = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 11)); assert.equal(f.consumers.length, 1); });
    await t.test(`nonconstructible consumer ${String(value)} still captures kubectl`, async () => { const f = fixture(); f.state.consumerCtor = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 10)); assert.equal(f.rotations.length, 0); });
  }
  await t.test("missing reload still reads arguments in order", async () => { const f = fixture(); f.state.rotation = Object.create(null); await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.filter(x => x !== "method" && x !== "call")); });
  for (const stage of ["schema", "id2", "signal", "kubectl-get", "consumer-construct"]) await t.test(`${stage} refusal wins over selected noncallable`, async () => {
    const f = fixture(); if (stage === "schema") f.state.bodyFn = null; else if (stage === "kubectl-get") f.state.consumerCtor = null; else if (stage === "consumer-construct") f.state.ctor = null; else f.state.method = null;
    f.state.faults[stage] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, order.indexOf(stage) + 1));
  });
  const captured: [string, string][] = [["schema", "bodyFn"], ["input-id", "input"], ["engine-get", "ctor"], ["engine", "ctor"], ["kubectl-get", "consumerCtor"], ["consumer-construct", "engine"], ["method", "rotation"], ["id2", "method"], ["signal", "method"]];
  for (const [stage, field] of captured) await t.test(`${stage} cannot replace captured ${field}`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state[field] = null; }; await f.invoke(); exact(f); construction(f); });
  await t.test("body getter chooses fresh schema before its capture", async () => { const f = fixture(), s = opaque("fresh schema"); f.state.hooks["body-get"] = () => { f.state.schema = s; }; await f.invoke(); assert.equal(f.bodies[0][1], s); });
  await t.test("input getter selects first params id before equality", async () => { const f = fixture(), id = opaque("fresh matching id"); f.state.inputId = id; f.state.hooks["input-id"] = () => { f.state.firstId = id; }; await f.invoke(); exact(f); });
  await t.test("first id can change second id while comparison still uses its captured value", async () => { const f = fixture(), id = opaque("second id"); f.state.hooks.id1 = () => { f.state.secondId = id; }; await f.invoke(); exact(f, f.actor, id); });
  await t.test("constructor getter chooses fresh engine before evaluation", async () => { const f = fixture(), e = opaque("fresh engine"); f.state.hooks["ctor-get"] = () => { f.state.engine = e; }; await f.invoke(); construction(f, e); });
  await t.test("engine may choose consumer constructor before capture", async () => { const f = fixture(); f.state.consumerCtor = null; f.state.hooks.engine = () => { f.state.consumerCtor = f.Consumer; }; await f.invoke(); construction(f); });
  await t.test("consumer constructor getter selects kubectl before capture", async () => { const f = fixture(), k = opaque("fresh kubectl"); f.state.hooks["consumer-ctor-get"] = () => { f.state.kubectl = k; }; await f.invoke(); construction(f, f.engine, f.consumer, k); });
  await t.test("kubectl getter chooses consumer result before construction", async () => { const f = fixture(), c = opaque("fresh consumer"); f.state.hooks["kubectl-get"] = () => { f.state.consumer = c; }; await f.invoke(); construction(f, f.engine, c); });
  await t.test("rotation construction chooses instance before method capture", async () => { const f = fixture(), r = { reload: f.method }; f.state.hooks.construct = () => { f.state.rotation = r; }; await f.invoke(); exact(f, f.actor, f.id, f.input, f.signal, r); });
  await t.test("method capture precedes fresh second id then signal", async () => { const f = fixture(), id = opaque("second id"), s = opaque("fresh signal"); f.state.hooks.method = () => { f.state.secondId = id; }; f.state.hooks.id2 = () => { f.state.signal = s; }; await f.invoke(); exact(f, f.actor, id, f.input, s); });
  await t.test("signal getter cannot replace already captured second id", async () => { const f = fixture(); f.state.hooks.signal = () => { f.state.secondId = null; }; await f.invoke(); exact(f); });
  await t.test("mismatch error getter selects returned refusal without touching constructors", async () => { const f = fixture(), r = Object.freeze({ public: "OTHER-REFUSAL" }); f.state.inputId = null; f.state.hooks["error-get"] = () => { f.state.refusal = r; }; await assert.rejects(f.invoke(), e => e === r); mismatch(f); });
  await t.test("rejected body never checks targets or constructs anything", async () => { const f = fixture(); f.state.rejectBody = true; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 3)); });
  await t.test("held body blocks target reads and all construction", async () => { const f = fixture(), d = deferred(); f.state.input = d.promise; const p = f.invoke(); await turns(); assert.deepEqual(f.trace, order.slice(0, 3)); assert.equal(f.rotations.length, 0); d.resolve(f.input); assert.equal(await p, f.result); exact(f); assert.deepEqual(f.trace, order); });
  await t.test("held body uses fresh ids and constructors after resolution", async () => { const f = fixture(), d = deferred(), id = opaque("fresh id"), e = opaque("fresh engine"); f.state.input = d.promise; const p = f.invoke(); await turns(); f.state.inputId = id; f.state.firstId = id; f.state.secondId = id; f.state.engine = e; d.resolve(f.input); await p; exact(f, f.actor, id); construction(f, e); });
  await t.test("held body rejection never retries", async () => { const f = fixture(), d = deferred(); f.state.input = d.promise; const p = assert.rejects(f.invoke(), e => e === f.fault); await turns(); d.reject(f.fault); await p; assert.deepEqual(f.trace, order.slice(0, 3)); assert.equal(f.bodies.length, 1); });
  await t.test("body thenable adopts first input and ignores later rejection", async () => { const f = fixture(); f.state.input = { then(resolve: (v: unknown) => void, reject: (e: unknown) => void) { resolve(f.input); reject(f.fault); resolve(null); } }; await f.invoke(); exact(f); assert.equal(f.bodies.length, 1); });
  await t.test("throwing body then getter prevents target access", async () => { const f = fixture(); f.state.input = { get then() { throw f.fault; } }; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 3)); });
  await t.test("rejected method result retains exact refusal", async () => { const f = fixture(); f.state.rejectCall = true; await assert.rejects(f.invoke(), e => e === f.fault); exact(f); assert.equal(f.calls.length, 1); });
  await t.test("held result preserves four captured arguments and adopted identity", async () => { const f = fixture(), d = deferred(); f.state.result = d.promise; let settled = false; const p = f.invoke().then(v => { settled = true; return v; }); await turns(); assert.equal(settled, false); exact(f); f.state.secondId = null; f.state.signal = null; f.state.input = null; d.resolve(f.result); assert.equal(await p, f.result); exact(f); assert.equal(f.calls.length, 1); });
  await t.test("held result rejection never retries reload", async () => { const f = fixture(), d = deferred(); f.state.result = d.promise; const p = assert.rejects(f.invoke(), e => e === f.fault); await turns(); d.reject(f.fault); await p; assert.equal(f.calls.length, 1); });
  await t.test("result thenable adopts only first resolved identity", async () => { const f = fixture(); f.state.result = { then(resolve: (v: unknown) => void, reject: (e: unknown) => void) { resolve(f.result); reject(f.fault); resolve(null); } }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("throwing result then getter retains exact refusal", async () => { const f = fixture(); f.state.result = { get then() { throw f.fault; } }; await assert.rejects(f.invoke(), e => e === f.fault); exact(f); });
  await t.test("result proxy receives exactly two then reads across VM and host", async () => { const f = fixture(), reads: PropertyKey[] = [], r = new Proxy({}, { get(_t, k) { reads.push(k); assert.equal(k, "then"); return undefined; }, ownKeys() { throw f.fault; } }); f.state.result = r; assert.equal(await f.invoke(), r); assert.deepEqual(reads, ["then", "then"]); exact(f); });
  await t.test("sequential calls use fresh body target engine consumer rotation signal and actor", async () => { const f = fixture(); await f.invoke(); const input = { rotationId: f.id }, e = opaque("engine2"), c = opaque("consumer2"), r = { reload: f.method }, s = opaque("signal2"), a = opaque("actor2"), result = Object.freeze({ public: "RESULT2" }); f.state.input = input; f.state.engine = e; f.state.consumer = c; f.state.rotation = r; f.state.signal = s; f.state.result = result; assert.equal(await f.invoke(f.registry, a), result); exact(f, a, f.id, input, s, r); construction(f, e, c); assert.equal(f.bodies.length, 2); assert.equal(f.calls.length, 2); });
  await t.test("interleaved held inputs retain each whole input request and params", async () => {
    const f = fixture(), one = deferred(), two = deferred(), id1 = opaque("id1"), id2 = opaque("id2"), s1 = opaque("s1"), s2 = opaque("s2"), a1 = opaque("a1"), a2 = opaque("a2"), input1 = { rotationId: id1 }, input2 = { rotationId: id2 }, r1 = { signal: s1 }, r2 = { signal: s2 };
    f.state.input = one.promise; const first = f.invoke(f.registry, a1, r1, { id: id1 }); f.state.input = two.promise; const second = f.invoke(f.registry, a2, r2, { id: id2 }); await turns(); assert.equal(f.calls.length, 0);
    two.resolve(input2); await second; exact(f, a2, id2, input2, s2); one.resolve(input1); await first; exact(f, a1, id1, input1, s1); assert.equal(f.calls.length, 2);
  });
  await t.test("interleaved held results retain each receiver and four captured arguments", async () => {
    const f = fixture(), one = deferred(), two = deferred(), id2 = opaque("id2"), s2 = opaque("s2"), a2 = opaque("a2"), input2 = { rotationId: id2 }, rotation2 = { reload: f.method }, result2 = Object.freeze({ public: "RESULT2" });
    f.state.result = one.promise; const first = f.invoke(); await turns(); exact(f); f.state.input = input2; f.state.rotation = rotation2; f.state.result = two.promise; const second = f.invoke(f.registry, a2, { signal: s2 }, { id: id2 }); await turns(); exact(f, a2, id2, input2, s2, rotation2);
    two.resolve(result2); assert.equal(await second, result2); one.resolve(f.result); assert.equal(await first, f.result); assert.equal(f.calls[0].receiver, f.rotation); assert.equal(f.calls[0].args[2], f.input); assert.equal(f.calls.length, 2);
  });
  await t.test("target refusal does not poison a fresh matching call", async () => { const f = fixture(); f.state.inputId = null; await assert.rejects(f.invoke(), e => e === f.refusal); f.state.inputId = f.id; assert.equal(await f.invoke(), f.result); exact(f); assert.equal(f.calls.length, 1); });
});
