import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC PATCH SOURCE controls. Actual imports and GET/POST stay inert.
// No body parsing, schema validation, credentials, generation or consumer execution.
type Model = Record<string, any>;
const path = "src/app/api/kv/rotations/route.ts";
const compiled = ts.transpileModule(readFileSync(path, "utf8"), {
  fileName: path, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
}).outputText;
const actions = ["generate", "acknowledge", "cancel", "resolve"] as const;
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
function fixture(action: string = "generate") {
  const trace: string[] = [], wrappers: any[][] = [], markers: unknown[] = [], engines: unknown[][] = [], bodies: unknown[][] = [], constructions: Model[] = [], consumers: Model[] = [], calls: Model[] = [];
  const registry = opaque("registry"), actor = opaque("actor"), request = opaque("request"), params = opaque("params"), schema = opaque("schema"), engine = opaque("engine"), consumer = opaque("consumer"), rotationId = opaque("rotationId"), revision = opaque("revision"), confirmPath = opaque("confirmPath");
  const result = Object.freeze({ public: "RESULT" }), fault = Error("PUBLIC-FAULT");
  const state: Model = { action, engine, consumer, rotationId, revision, confirmPath, schema, result, kubectl: opaque("kubectl"), faults: {}, hooks: {}, methods: {} };
  function step(name: string) { trace.push(name); if (state.hooks[name]) state.hooks[name](); if (state.faults[name]) throw state.faults[name]; }
  const body = Object.defineProperties({}, Object.fromEntries(["action", "rotationId", "revision", "confirmPath"].map(name => [name, { get() { step(name); return state[name]; }, configurable: true }])));
  state.body = body;
  function methodFor(name: string) {
    return function(this: unknown, ...args: unknown[]) { calls.push({ name, receiver: this, args }); step("call"); if (state.rejectCall) return Promise.reject(fault); return state.result; };
  }
  const methods = Object.fromEntries(actions.map(name => [name, methodFor(name)])); state.methods = { ...methods };
  const rotation = Object.defineProperties({}, Object.fromEntries(actions.map(name => [name, { get() { step("method:" + name); return state.methods[name]; } }])));
  function Rotations(this: unknown, ...args: unknown[]) { constructions.push({ receiver: this, newTarget: new.target, args }); step("construct"); return state.rotation; }
  function Consumer(this: unknown, ...args: unknown[]) { consumers.push({ receiver: this, newTarget: new.target, args }); step("consumer-construct"); return state.consumer; }
  state.ctor = Rotations; state.consumerCtor = Consumer; state.rotation = rotation;
  state.engineFn = (...args: unknown[]) => { engines.push(args); step("engine"); return state.engine; };
  state.bodyFn = (...args: unknown[]) => { bodies.push(args); step("body"); if (state.rejectBody) return Promise.reject(fault); return state.body; };
  const inert = opaque("unselected import");
  const http = { kvHuman(...args: any[]) { wrappers.push(args); const marker = Object.freeze({ public: `WRAPPER-${markers.length}` }); markers.push(marker); return marker; },
    get kvEngine() { step("engine-get"); return state.engineFn; }, get kvBody() { step("body-get"); return state.bodyFn; }, get metadataCursor() { throw fault; } };
  const imports: Model = { "zod": inert, "@/lib/kv-contract": inert, "@/lib/kv-http": http,
    "@/lib/kv-rotation": { get KvRotations() { step("ctor-get"); return state.ctor; } },
    "@/lib/kv-schemas": { get rotationPrepare() { throw fault; }, get rotationAction() { step("schema"); return state.schema; } },
    "@/lib/kv-rotation-consumer": { get KubectlRotationConsumer() { step("consumer-ctor-get"); return state.consumerCtor; } },
    "@/lib/k8s": { get kubectlJSON() { step("kubectl-get"); return state.kubectl; } } };
  const m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, require: (id: string) => {
      // Canonical inert dependency name; application uses the supported v3 export.
      id = id === "zod/v3" ? "zod" : id; assert.ok(Object.hasOwn(imports, id)); return imports[id]; } }, { filename: path, timeout: 5000 });
  assert.equal(wrappers.length, 3); assert.deepEqual(trace, [] as string[]);
  const callback = wrappers[2][0];
  return { state, trace, wrappers, markers, engines, bodies, constructions, consumers, calls, registry, actor, request, params, schema, engine, consumer, body, result, fault, methods, rotation, rotationId, revision, confirmPath, Rotations, Consumer, exports: m.exports,
    invoke: (...args: unknown[]) => callback(args.length ? args[0] : registry, args.length > 1 ? args[1] : actor, args.length > 2 ? args[2] : request, args.length > 3 ? args[3] : params) as Promise<unknown> };
}
type Fixture = ReturnType<typeof fixture>;
const prefix = ["body-get", "schema", "body", "ctor-get", "engine-get", "engine", "consumer-ctor-get", "kubectl-get", "consumer-construct", "construct", "action"];
function order(action: string) { return [...prefix, "method:" + action, "rotationId", ...(action === "cancel" ? ["revision", "confirmPath"] : []), "call"]; }
function exact(f: Fixture, action: string, ...values: unknown[]) {
  const actor = values.length ? values[0] : f.actor, input = values.length > 1 ? values[1] : f.body, rotation = values.length > 2 ? values[2] : f.rotation;
  const c = f.calls.at(-1)!; assert.equal(c.name, action); assert.equal(c.receiver, rotation);
  const expected = action === "cancel" ? [actor, f.state.rotationId, f.state.revision, f.state.confirmPath] : action === "resolve" ? [actor, f.state.rotationId] : [actor, f.state.rotationId, input];
  assert.equal(c.args.length, expected.length); expected.forEach((v, i) => assert.equal(c.args[i], v));
}
function construction(f: Fixture, ...values: unknown[]) {
  const engine = values.length ? values[0] : f.engine, consumer = values.length > 1 ? values[1] : f.consumer, kubectl = values.length > 2 ? values[2] : f.state.kubectl;
  const c = f.constructions.at(-1)!, d = f.consumers.at(-1)!;
  assert.equal(c.args.length, 2); assert.equal(c.args[0], engine); assert.equal(c.args[1], consumer); assert.equal(c.newTarget, f.Rotations);
  assert.equal(d.args.length, 1); assert.equal(d.args[0], kubectl); assert.equal(d.newTarget, f.Consumer);
}
test("human rotation action PATCH exact SOURCE delegation", async t => {
  await t.test("nodejs force-dynamic default PATCH wrapper and inert POST201; siblings never invoked", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["GET", "PATCH", "POST", "dynamic", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    for (const [i, name] of ["GET", "POST", "PATCH"].entries()) { assert.equal(f.exports[name], f.markers[i]); assert.equal(typeof f.wrappers[i][0], "function"); assert.equal(f.wrappers[i].length, i === 1 ? 2 : 1); }
    assert.equal(f.wrappers[1][1], 201); assert.deepEqual(f.trace, [] as string[]);
  });
  for (const action of actions) {
    await t.test(`${action} exact await construction receiver and arguments`, async () => {
      const f = fixture(action); assert.equal(await f.invoke(), f.result); exact(f, action); construction(f); assert.deepEqual(f.trace, order(action));
      assert.equal(f.engines.length, 1); assert.equal(f.engines[0].length, 1); assert.equal(f.engines[0][0], f.registry);
      assert.equal(f.bodies.length, 1); assert.equal(f.bodies[0].length, 3); assert.equal(f.bodies[0][0], f.request); assert.equal(f.bodies[0][1], f.schema); assert.equal(f.bodies[0][2], 4096);
      assert.equal(f.constructions.length, 1); assert.equal(f.consumers.length, 1); assert.equal(f.calls.length, 1);
    });
    for (const stage of ["method:" + action, "rotationId", ...(action === "cancel" ? ["revision", "confirmPath"] : []), "call"]) await t.test(`${action} ${stage} fault stops later reads`, async () => {
      const f = fixture(action); f.state.faults[stage] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); const sequence = order(action); assert.deepEqual(f.trace, sequence.slice(0, sequence.indexOf(stage) + 1)); assert.equal(f.calls.length, stage === "call" ? 1 : 0);
    });
    for (const value of [undefined, null, 7, {}]) await t.test(`${action} noncallable method ${String(value)} evaluates exact arguments first`, async () => {
      const f = fixture(action); f.state.methods[action] = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order(action).slice(0, -1)); assert.equal(f.calls.length, 0);
    });
    await t.test(`${action} missing method still reads arguments`, async () => { const f = fixture(action); f.state.rotation = Object.create(null); await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order(action).filter(x => x !== "method:" + action && x !== "call")); });
    await t.test(`${action} inherited method retains original receiver`, async () => { const f = fixture(action), rotation = Object.create({ [action]: f.methods[action] }); Object.defineProperty(rotation, "then", { get() { throw f.fault; } }); f.state.rotation = rotation; await f.invoke(); exact(f, action, f.actor, f.body, rotation); });
    await t.test(`${action} method getter side effect preserves captured receiver`, async () => { const f = fixture(action); f.state.hooks["method:" + action] = () => { f.state.rotation = null; }; await f.invoke(); exact(f, action); });
    await t.test(`${action} input getter cannot replace captured method`, async () => { const f = fixture(action); f.state.hooks.rotationId = () => { f.state.methods[action] = null; f.state.rotation = null; }; await f.invoke(); exact(f, action); });
    await t.test(`${action} argument refusal wins over noncallable method`, async () => { const f = fixture(action); f.state.methods[action] = null; f.state.faults.rotationId = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order(action).slice(0, prefix.length + 2)); });
    await t.test(`${action} action getter selects fresh method on captured receiver`, async () => { const f = fixture(action); f.state.methods[action] = null; f.state.hooks.action = () => { f.state.methods[action] = f.methods[action]; f.state.rotation = null; }; await f.invoke(); exact(f, action); });
    await t.test(`${action} action getter selects method only after both constructions`, async () => { const f = fixture(action), rotation = { [action]: f.methods[action] }; f.state.hooks.construct = () => { f.state.rotation = rotation; }; await f.invoke(); exact(f, action, f.actor, f.body, rotation); assert.deepEqual(f.trace, order(action).filter(x => x !== "method:" + action)); });
    await t.test(`${action} rejected method result retains exact refusal`, async () => { const f = fixture(action); f.state.rejectCall = true; await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.calls.length, 1); });
    await t.test(`${action} held result settles once with adopted identity`, async () => { const f = fixture(action), d = deferred(); f.state.result = d.promise; let settled = false; const p = f.invoke().then(v => { settled = true; return v; }); await turns(); assert.equal(settled, false); exact(f, action); d.resolve(f.result); assert.equal(await p, f.result); assert.equal(f.calls.length, 1); });
    await t.test(`${action} held result rejection never retries`, async () => { const f = fixture(action), d = deferred(); f.state.result = d.promise; const p = assert.rejects(f.invoke(), e => e === f.fault); await turns(); d.reject(f.fault); await p; assert.equal(f.calls.length, 1); });
    await t.test(`${action} thenable result adopts first resolved identity`, async () => { const f = fixture(action); f.state.result = { then(resolve: (v: unknown) => void, reject: (e: unknown) => void) { resolve(f.result); reject(f.fault); resolve(null); } }; assert.equal(await f.invoke(), f.result); });
    await t.test(`${action} throwing result then getter preserves refusal`, async () => { const f = fixture(action); f.state.result = { get then() { throw f.fault; } }; await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.calls.length, 1); });
    for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-RESULT")]) await t.test(`${action} result ${String(value)} adopted`, async () => { const f = fixture(action); f.state.result = value; assert.equal(await f.invoke(), value); exact(f, action); });
    for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-ARG")]) await t.test(`${action} opaque argument ${String(value)} passed whole`, async () => { const f = fixture(action); f.state.rotationId = value; f.state.revision = value; f.state.confirmPath = value; await f.invoke(value, value, value, value); assert.equal(f.engines[0][0], value); assert.equal(f.bodies[0][0], value); exact(f, action, value); });
  }
  for (const [i, stage] of prefix.entries()) await t.test(`${stage} fault stops at exact construction stage`, async () => { const f = fixture(); f.state.faults[stage] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, prefix.slice(0, i + 1)); assert.equal(f.calls.length, 0); });
  for (const value of [undefined, null, 7, {}]) await t.test(`noncallable body ${String(value)} reads schema first`, async () => { const f = fixture(); f.state.bodyFn = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, prefix.slice(0, 2)); });
  await t.test("schema refusal wins over noncallable body", async () => { const f = fixture(); f.state.bodyFn = null; f.state.faults.schema = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, prefix.slice(0, 2)); });
  await t.test("schema getter cannot replace captured body function", async () => { const f = fixture(); f.state.hooks.schema = () => { f.state.bodyFn = null; }; await f.invoke(); exact(f, "generate"); });
  await t.test("rejected body prevents every constructor lookup", async () => { const f = fixture(); f.state.rejectBody = true; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, prefix.slice(0, 3)); });
  await t.test("held body delays all construction and uses fresh dependencies after resolution", async () => { const f = fixture(), d = deferred(), engine = opaque("engineB"), consumer = opaque("consumerB"); f.state.body = d.promise; const p = f.invoke(); await turns(); assert.deepEqual(f.trace, prefix.slice(0, 3)); f.state.engine = engine; f.state.consumer = consumer; d.resolve(f.body); assert.equal(await p, f.result); construction(f, engine, consumer); exact(f, "generate"); });
  await t.test("held body rejection prevents all constructors", async () => { const f = fixture(), d = deferred(); f.state.body = d.promise; const p = assert.rejects(f.invoke(), e => e === f.fault); await turns(); d.reject(f.fault); await p; assert.deepEqual(f.trace, prefix.slice(0, 3)); });
  await t.test("body thenable adopts only first resolved input", async () => { const f = fixture(); f.state.body = { then(resolve: (v: unknown) => void, reject: (e: unknown) => void) { resolve(f.body); reject(f.fault); resolve(null); } }; await f.invoke(); exact(f, "generate"); });
  await t.test("throwing body then getter prevents constructors", async () => { const f = fixture(); f.state.body = { get then() { throw f.fault; } }; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, prefix.slice(0, 3)); });
  for (const value of [undefined, null, 7, {}, () => {}]) await t.test(`nonconstructible rotations ${String(value)} still evaluates engine and consumer`, async () => { const f = fixture(); f.state.ctor = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, prefix.slice(0, 9)); assert.equal(f.consumers.length, 1); assert.equal(f.constructions.length, 0); });
  await t.test("consumer refusal wins over nonconstructible rotations", async () => { const f = fixture(); f.state.ctor = null; f.state.faults["consumer-construct"] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, prefix.slice(0, 9)); });
  for (const value of [undefined, null, 7, {}, () => {}]) await t.test(`nonconstructible consumer ${String(value)} still captures kubectl`, async () => { const f = fixture(); f.state.consumerCtor = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, prefix.slice(0, 8)); assert.equal(f.constructions.length, 0); });
  await t.test("kubectl getter refusal wins over nonconstructible consumer", async () => { const f = fixture(); f.state.consumerCtor = null; f.state.faults["kubectl-get"] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, prefix.slice(0, 8)); });
  for (const value of [undefined, null, 7, {}]) await t.test(`noncallable engine ${String(value)} stops before consumer`, async () => { const f = fixture(); f.state.engineFn = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, prefix.slice(0, 5)); });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-DEPENDENCY")]) {
    await t.test(`schema ${String(value)} delegated without validation`, async () => { const f = fixture(); f.state.schema = value; await f.invoke(); assert.equal(f.bodies[0][1], value); });
    await t.test(`engine ${String(value)} forwarded unchanged`, async () => { const f = fixture(); f.state.engine = value; await f.invoke(); construction(f, value); });
    await t.test(`kubectl ${String(value)} forwarded without invocation`, async () => { const f = fixture(); f.state.kubectl = value; await f.invoke(); construction(f, f.engine, f.consumer, value); });
    await t.test(`primitive consumer return ${String(value)} uses constructed consumer`, async () => { const f = fixture(); f.state.consumer = value; await f.invoke(); construction(f, f.engine, f.consumers[0].receiver); });
    await t.test(`primitive rotations return ${String(value)} uses constructed receiver`, async () => { const f = fixture(); f.state.rotation = value; Object.defineProperty(f.Rotations.prototype, "generate", { value: f.methods.generate }); await f.invoke(); exact(f, "generate", f.actor, f.body, f.constructions[0].receiver); });
  }
  await t.test("engine hook cannot replace captured rotations constructor", async () => { const f = fixture(); f.state.hooks.engine = () => { f.state.ctor = null; }; await f.invoke(); construction(f); });
  await t.test("kubectl getter cannot replace captured consumer constructor", async () => { const f = fixture(); f.state.hooks["kubectl-get"] = () => { f.state.consumerCtor = null; }; await f.invoke(); construction(f); });
  await t.test("consumer construction cannot replace captured rotations constructor or engine", async () => { const f = fixture(); f.state.hooks["consumer-construct"] = () => { f.state.ctor = null; f.state.engine = null; }; await f.invoke(); construction(f); });
  await t.test("callable rotations object is only method receiver", async () => { const f = fixture(), rotation = Object.assign(() => { throw f.fault; }, { generate: f.methods.generate }); f.state.rotation = rotation; await f.invoke(); exact(f, "generate", f.actor, f.body, rotation); });
  await t.test("callable consumer returned object forwarded without invocation", async () => { const f = fixture(), consumer = () => { throw f.fault; }; f.state.consumer = consumer; await f.invoke(); construction(f, f.engine, consumer); });
  for (const value of [undefined, null, false, 0, "", "GENERATE", "unknown", Symbol("PUBLIC-ACTION"), {}]) await t.test(`unknown modeled action ${String(value)} returns undefined with no method or input fields`, async () => { const f = fixture(); f.state.action = value; assert.equal(await f.invoke(), undefined); assert.deepEqual(f.trace, prefix); assert.equal(f.calls.length, 0); });
  for (const value of [undefined, null]) await t.test(`nullish resolved input ${String(value)} constructs before action refusal`, async () => { const f = fixture(); f.state.body = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, prefix.slice(0, 10)); });
  for (const value of [false, 0, "", Symbol("PUBLIC-INPUT")]) await t.test(`primitive resolved input ${String(value)} unknown action`, async () => { const f = fixture(); f.state.body = value; assert.equal(await f.invoke(), undefined); assert.deepEqual(f.trace, prefix.slice(0, 10)); });
  await t.test("inherited input fields and exact whole input forwarded", async () => { const f = fixture("cancel"), input = Object.create(f.body); f.state.body = input; await f.invoke(); exact(f, "cancel", f.actor, input); assert.deepEqual(f.trace, order("cancel")); });
  await t.test("generate does not read revision confirmPath or irrelevant fields", async () => { const f = fixture(); for (const name of ["revision", "confirmPath"]) Object.defineProperty(f.body, name, { get() { throw f.fault; } }); await f.invoke(); exact(f, "generate"); });
  await t.test("resolve reads no revision confirmPath or whole input fields", async () => { const f = fixture("resolve"); for (const name of ["revision", "confirmPath"]) Object.defineProperty(f.body, name, { get() { throw f.fault; } }); await f.invoke(); exact(f, "resolve"); });
  await t.test("cancel getter order changes later arguments without replacing method", async () => { const f = fixture("cancel"), revision = opaque("revisionB"), path = opaque("confirmPathB"); f.state.hooks.rotationId = () => { f.state.revision = revision; f.state.methods.cancel = null; }; f.state.hooks.revision = () => { f.state.confirmPath = path; }; await f.invoke(); exact(f, "cancel"); assert.equal(f.calls[0].args[2], revision); assert.equal(f.calls[0].args[3], path); });
  await t.test("fresh calls use new engine consumer instance actor input", async () => { const f = fixture(); await f.invoke(); const engine = opaque("engineB"), consumer = opaque("consumerB"), actor = opaque("actorB"), registry = opaque("registryB"), request = opaque("requestB"), body = Object.create(f.body), rotation = { generate: f.methods.generate }; Object.assign(f.state, { engine, consumer, body, rotation }); await f.invoke(registry, actor, request); construction(f, engine, consumer); exact(f, "generate", actor, body, rotation); assert.equal(f.engines[1][0], registry); assert.equal(f.bodies[1][0], request); assert.equal(f.calls.length, 2); });
  await t.test("interleaved bodies construct only after own resolution with own actor input", async () => {
    const f = fixture(), a = deferred(), b = deferred(), actorB = opaque("actorB"), registryB = opaque("registryB"), requestB = opaque("requestB"), bodyB = Object.create(f.body), rotationB = { generate: f.methods.generate }, engineB = opaque("engineB"), consumerB = opaque("consumerB");
    f.state.body = a.promise; const pa = f.invoke(); f.state.body = b.promise; const pb = f.invoke(registryB, actorB, requestB); await turns(); assert.equal(f.constructions.length, 0); assert.equal(f.consumers.length, 0);
    Object.assign(f.state, { engine: engineB, consumer: consumerB, rotation: rotationB }); b.resolve(bodyB); assert.equal(await pb, f.result); construction(f, engineB, consumerB); exact(f, "generate", actorB, bodyB, rotationB); assert.equal(f.engines[0][0], registryB);
    Object.assign(f.state, { engine: f.engine, consumer: f.consumer, rotation: f.rotation }); a.resolve(f.body); assert.equal(await pa, f.result); construction(f); exact(f, "generate"); assert.equal(f.engines[1][0], f.registry); assert.equal(f.calls.length, 2);
  });
  await t.test("interleaved method results settle independently", async () => { const f = fixture(), a = deferred(), b = deferred(); f.state.result = a.promise; const pa = f.invoke(); await turns(); f.state.result = b.promise; const pb = f.invoke(); await turns(); assert.equal(f.calls.length, 2); b.resolve(f.body); assert.equal(await pb, f.body); a.resolve(f.result); assert.equal(await pa, f.result); });
});
