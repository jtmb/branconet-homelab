import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC destroy POST SOURCE controls. Every dependency is inert.
// No actual wrapper/body/schema/registry/engine/HTTP/auth/native/DB executes.
type Model = Record<string, any>;
const route = "src/app/api/kv/paths/[id]/destroy/route.ts";
const compiled = ts.transpileModule(readFileSync(route, "utf8"), { fileName: route,
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
function deferred() {
  let resolve!: (value: any) => void, reject!: (error: unknown) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const turns = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
function opaque(label: string) {
  return new Proxy({}, { get() { throw new Error(`PUBLIC unexpected ${label} access`); },
    ownKeys() { throw new Error(`PUBLIC unexpected ${label} enumeration`); } });
}
function fixture() {
  const trace: string[] = [], wrappers: any[][] = [], destroys: Model[] = [], engines: unknown[][] = [], bodies: unknown[][] = [];
  const registry = opaque("registry"), actor = opaque("actor"), schema = opaque("schema implementation");
  const body = Object.freeze({ public: "BODY" }), result = Object.freeze({ public: "RESULT" }), fault = new Error("PUBLIC-FAULT");
  const signal = opaque("signal");
  const state: Model = { signal, signalFault: null, id: "PUBLIC-ID", engine: null, method: null, body, result, idFault: null, engineFault: null,
    methodFault: null, bodyGetterFault: null, schemaFault: null, bodyFault: null, destroyFault: null,
    rejectBody: false, rejectDestroy: false, bodyHook: null };
  const request = new Proxy({}, { get(_target, key) {
    assert.equal(key, "signal"); trace.push("signal"); if (state.signalFault) throw state.signalFault; return state.signal;
  }, ownKeys() { throw fault; } });
  function method(this: unknown, ...args: unknown[]) {
    trace.push("destroy"); destroys.push({ receiver: this, args });
    if (state.destroyFault) { if (state.rejectDestroy) return Promise.reject(state.destroyFault); throw state.destroyFault; }
    return state.result;
  }
  const engine = Object.defineProperty({}, "destroy", { get() {
    trace.push("destroy-get"); if (state.methodFault) throw state.methodFault; return state.method;
  } });
  state.engine = engine; state.method = method;
  const wrapped = Object.freeze({ public: "INERT-POST" });
  const http = {
    kvHuman(...args: any[]) { wrappers.push(args); return wrapped; },
    kvEngine(...args: unknown[]) { trace.push("engine"); engines.push(args); if (state.engineFault) throw state.engineFault; return state.engine; },
    get kvBody() { trace.push("body-get"); if (state.bodyGetterFault) throw state.bodyGetterFault;
      return (...args: unknown[]) => {
        trace.push("body"); bodies.push(args); if (state.bodyHook) state.bodyHook();
        if (state.bodyFault) { if (state.rejectBody) return Promise.reject(state.bodyFault); throw state.bodyFault; }
        return state.body;
      };
    },
  };
  const schemas = { get nativeDestroy() { trace.push("schema"); if (state.schemaFault) throw state.schemaFault; return schema; } };
  const m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, require: (name: string) => {
    if (name === "@/lib/kv-http") return http;
    assert.equal(name, "@/lib/kv-schemas"); return schemas;
  } }, { filename: route, timeout: 5000 });
  assert.equal(wrappers.length, 1); assert.deepEqual(trace, [] as string[]);
  const params = new Proxy({}, { get(_target, key) {
    assert.equal(key, "id"); trace.push("id"); if (state.idFault) throw state.idFault; return state.id;
  }, ownKeys() { throw fault; } });
  const callback = wrappers[0][0];
  return { trace, wrappers, destroys, engines, bodies, registry, actor, request, schema, body, result, fault,
    state, engine, method, params, signal, wrapped, exports: m.exports,
    invoke: (...args: unknown[]) => callback(args.length > 3 ? args[3] : registry, args.length > 2 ? args[2] : actor,
      args.length > 1 ? args[1] : request, args.length ? args[0] : params) as Promise<unknown> };
}
type Fixture = ReturnType<typeof fixture>;
function exact(f: Fixture, ...values: unknown[]) {
  const actor = values.length ? values[0] : f.actor, id = values.length > 1 ? values[1] : "PUBLIC-ID";
  const body = values.length > 2 ? values[2] : f.body, receiver = values.length > 3 ? values[3] : f.engine;
  const call = f.destroys.at(-1)!; assert.equal(call.receiver, receiver); assert.equal(call.args.length, 4);
  assert.equal(call.args[0], actor); assert.equal(call.args[1], id); assert.equal(call.args[2], body); assert.equal(call.args[3], values.length > 4 ? values[4] : f.signal);
}
function requestWithSignal(signal: unknown, trace: string[]) {
  return new Proxy({}, { get(_target, key) { assert.equal(key, "signal"); trace.push("signal"); return signal; },
    ownKeys() { throw new Error("PUBLIC request enumeration"); } });
}
const order = ["id", "engine", "destroy-get", "body-get", "schema", "body", "signal", "destroy"];
const isError = (e: unknown) => Object.prototype.toString.call(e) === "[object Error]";
test("human destroy POST exact SOURCE delegation", async t => {
  await t.test("nodejs export, exact single default-status inert wrapper", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["POST", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.POST, f.wrapped);
    assert.equal(f.wrappers[0].length, 1); assert.equal(typeof f.wrappers[0][0], "function"); assert.deepEqual(f.trace, []);
  });
  await t.test("ordered id/engine/method/body/schema plus exact registry/request/schema and four destroy arguments including original signal", async () => {
    const f = fixture(); assert.equal(await f.invoke(), f.result); exact(f); assert.deepEqual(f.trace, order);
    assert.equal(f.engines.length, 1); assert.equal(f.engines[0].length, 1); assert.equal(f.engines[0][0], f.registry);
    assert.equal(f.bodies.length, 1); assert.equal(f.bodies[0].length, 2); assert.equal(f.bodies[0][0], f.request); assert.equal(f.bodies[0][1], f.schema);
  });
  for (const [field, count] of [["idFault",1],["engineFault",2],["methodFault",3],["bodyGetterFault",4],["schemaFault",5],["bodyFault",6],["signalFault",7],["destroyFault",8]] as const)
    await t.test(`${field} preserves exact refusal and stops later stages`, async () => {
      const f = fixture(); f.state[field] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault);
      assert.deepEqual(f.trace, order.slice(0, count)); assert.equal(f.destroys.length, field === "destroyFault" ? 1 : 0);
    });
  for (const stage of ["Body", "Destroy"]) await t.test(`rejected ${stage} promise keeps refusal identity`, async () => {
    const f = fixture(); f.state[stage === "Body" ? "bodyFault" : "destroyFault"] = f.fault; f.state["reject"+stage] = true;
    await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.destroys.length, stage === "Destroy" ? 1 : 0);
  });
  for (const value of [undefined, null]) await t.test(`nullish params ${String(value)} refuse before engine`, async () => {
    const f = fixture(); await assert.rejects(f.invoke(value), isError); assert.deepEqual(f.trace, []);
  });
  await t.test("missing id forwards undefined; inherited getter read once without enumeration", async () => {
    const f = fixture(); await f.invoke({}); exact(f, f.actor, undefined);
    const g = fixture(), id = opaque("id"); let reads = 0;
    const p = Object.create({ get id() { reads++; return id; } });
    Object.defineProperty(p, "unused", { get() { throw g.fault; } }); await g.invoke(p); exact(g, g.actor, id); assert.equal(reads, 1);
  });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-ID")]) await t.test(`id ${String(value)} forwarded unchanged`, async () => {
    const f = fixture(); f.state.id = value; await f.invoke(); exact(f, f.actor, value);
  });
  for (const value of [undefined, null]) await t.test(`nullish engine ${String(value)} refuses before body`, async () => {
    const f = fixture(); f.state.engine = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, ["id", "engine"]);
  });
  for (const value of [undefined, null, 7, {}]) await t.test(`noncallable destroy ${String(value)} evaluated after held body`, async () => {
    const f = fixture(), held = deferred(); f.state.method = value; f.state.body = held.promise;
    const refused = assert.rejects(f.invoke(), isError); await turns(); assert.deepEqual(f.trace, order.slice(0, 6));
    assert.equal(f.destroys.length, 0); held.resolve(f.body); await refused; assert.deepEqual(f.trace, order.slice(0, 7));
  });
  await t.test("body rejection precedes noncallable method refusal", async () => {
    const f = fixture(); f.state.method = null; f.state.bodyFault = f.fault;
    await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 6));
  });
  await t.test("inherited destroy retains exact engine receiver", async () => {
    const f = fixture(), e = Object.create({ destroy: f.method }); f.state.engine = e; await f.invoke(); exact(f, f.actor, "PUBLIC-ID", f.body, e);
  });
  await t.test("engine then is never inspected", async () => {
    const f = fixture(), e = { destroy: f.method, get then() { throw f.fault; } }; f.state.engine = e; await f.invoke(); exact(f, f.actor, "PUBLIC-ID", f.body, e);
  });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-BODY")]) await t.test(`body ${String(value)} forwarded without validation`, async () => {
    const f = fixture(); f.state.body = value; await f.invoke(); exact(f, f.actor, "PUBLIC-ID", value);
  });
  await t.test("await reads body then protocol only and never grouped data", async () => {
    const f = fixture(); let reads = 0;
    const body = new Proxy({}, { get(_t, key) { assert.equal(key, "then"); reads++; return undefined; }, ownKeys() { throw f.fault; } });
    f.state.body = body; await f.invoke(); exact(f, f.actor, "PUBLIC-ID", body); assert.equal(reads, 1);
  });
  await t.test("body throwing then getter refuses without destroy", async () => {
    const f = fixture(); f.state.body = { get then() { throw f.fault; } };
    await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.destroys.length, 0);
  });
  await t.test("body thenable adopts first resolved identity", async () => {
    const f = fixture(); f.state.body = { then(resolve: (x: unknown) => void, reject: (x: unknown) => void) { resolve(f.body); reject(f.fault); resolve(null); } };
    await f.invoke(); exact(f);
  });
  await t.test("held body blocks destroy; captured receiver/method survive replacement", async () => {
    const f = fixture(), held = deferred(); f.state.body = held.promise;
    const pending = f.invoke(); await turns(); assert.deepEqual(f.trace, order.slice(0, 6)); assert.equal(f.destroys.length, 0);
    f.state.engine = opaque("replacement engine"); f.state.method = () => { throw f.fault; };
    held.resolve(f.body); assert.equal(await pending, f.result); exact(f); assert.deepEqual(f.trace, order);
  });
  await t.test("body side effects cannot replace previously captured method", async () => {
    const f = fixture(); f.state.bodyHook = () => { f.state.method = null; f.state.engine = null; };
    await f.invoke(); exact(f);
  });
  await t.test("held rejected body preserves exact error and never destroys", async () => {
    const f = fixture(), held = deferred(); f.state.body = held.promise; const pending = assert.rejects(f.invoke(), e => e === f.fault);
    await turns(); held.reject(f.fault); await pending; assert.equal(f.destroys.length, 0);
  });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-RESULT")]) await t.test(`result ${String(value)} adopted unchanged`, async () => {
    const f = fixture(); f.state.result = value; assert.equal(await f.invoke(), value); exact(f);
  });
  await t.test("held result stays pending after exactly one destroy", async () => {
    const f = fixture(), held = deferred(); f.state.result = held.promise; let settled = false;
    const pending = f.invoke().then(x => { settled = true; return x; }); await turns(); assert.equal(settled, false); exact(f);
    assert.equal(f.destroys.length, 1); held.resolve(f.result); assert.equal(await pending, f.result);
  });
  await t.test("held result rejection propagates without retry", async () => {
    const f = fixture(), held = deferred(); f.state.result = held.promise; const pending = assert.rejects(f.invoke(), e => e === f.fault);
    await turns(); held.reject(f.fault); await pending; assert.equal(f.destroys.length, 1);
  });
  await t.test("result thenable first resolve wins; no raw promise identity claim", async () => {
    const f = fixture(); f.state.result = { then(resolve: (x: unknown) => void, reject: (x: unknown) => void) { resolve(f.result); reject(f.fault); resolve(null); } };
    assert.equal(await f.invoke(), f.result); assert.equal(f.destroys.length, 1);
  });
  await t.test("result throwing then getter propagates after one destroy", async () => {
    const f = fixture(); f.state.result = { get then() { throw f.fault; } };
    await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.destroys.length, 1);
  });
  await t.test("fresh invocations re-read id/engine/method/body with distinct input identities", async () => {
    const f = fixture(); await f.invoke(); const body = Object.freeze({ public: "BODY-2" }), actor = opaque("actor-2"), request = requestWithSignal(f.signal, f.trace);
    f.state.id = "PUBLIC-ID-2"; f.state.body = body; await f.invoke(f.params, request, actor);
    exact(f, actor, "PUBLIC-ID-2", body); assert.equal(f.bodies[1][0], request); assert.deepEqual(f.trace, [...order, ...order]);
  });
  await t.test("interleaved held bodies preserve per-call engine/actor/id/request/input identities", async () => {
    const f = fixture(), a = deferred(), b = deferred(), actorB = opaque("actor-B"), requestB = requestWithSignal(f.signal, f.trace), bodyB = Object.freeze({ public: "BODY-B" });
    f.state.body = a.promise; const first = f.invoke(); await turns();
    const engineB = { destroy: f.method }; f.state.engine = engineB; f.state.body = b.promise;
    const second = f.invoke({ id: "PUBLIC-B" }, requestB, actorB); await turns(); assert.equal(f.destroys.length, 0);
    b.resolve(bodyB); assert.equal(await second, f.result); exact(f, actorB, "PUBLIC-B", bodyB, engineB);
    a.resolve(f.body); assert.equal(await first, f.result); exact(f); assert.equal(f.destroys.length, 2);
    assert.equal(f.bodies[0][0], f.request); assert.equal(f.bodies[1][0], requestB);
  });
  await t.test("interleaved results settle independently without automatic retries", async () => {
    const f = fixture(), a = deferred(), b = deferred(); f.state.result = a.promise;
    const first = f.invoke(); await turns(); f.state.result = b.promise; const second = f.invoke({ id: "PUBLIC-B" }); await turns();
    const secondResult = Object.freeze({ public: "RESULT-B" }); b.resolve(secondResult); assert.equal(await second, secondResult);
    a.resolve(f.result); assert.equal(await first, f.result); assert.equal(f.destroys.length, 2);
  });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-SIGNAL")]) await t.test(`signal ${String(value)} forwarded untouched`, async () => {
    const f = fixture(); f.state.signal = value; await f.invoke(); exact(f, f.actor, "PUBLIC-ID", f.body, f.engine, value);
    assert.deepEqual(f.trace, order);
  });
  await t.test("signal object is not validated, awaited, enumerated or inspected", async () => {
    const f = fixture(), signal = opaque("original signal"); f.state.signal = signal;
    await f.invoke(); exact(f, f.actor, "PUBLIC-ID", f.body, f.engine, signal);
  });
  await t.test("held body prevents signal read and observes signal identity at body resolution", async () => {
    const f = fixture(), held = deferred(), signal = opaque("late signal"); f.state.body = held.promise;
    const pending = f.invoke(); await turns(); assert.deepEqual(f.trace, order.slice(0, 6));
    f.state.signal = signal; held.resolve(f.body); assert.equal(await pending, f.result);
    exact(f, f.actor, "PUBLIC-ID", f.body, f.engine, signal); assert.deepEqual(f.trace, order);
  });
  await t.test("body-side signal replacement is read after the resolved body", async () => {
    const f = fixture(), signal = opaque("body-selected signal"); f.state.bodyHook = () => { f.state.signal = signal; };
    await f.invoke(); exact(f, f.actor, "PUBLIC-ID", f.body, f.engine, signal); assert.deepEqual(f.trace, order);
  });
  await t.test("signal getter cannot replace captured destroy method or receiver", async () => {
    const f = fixture(), signal = opaque("getter signal");
    const request = Object.defineProperty({}, "signal", { get() {
      f.trace.push("signal"); f.state.method = null; f.state.engine = null; return signal;
    } });
    await f.invoke(f.params, request); exact(f, f.actor, "PUBLIC-ID", f.body, f.engine, signal);
    assert.deepEqual(f.trace, order);
  });
  await t.test("signal refusal precedes noncallable destroy refusal after body", async () => {
    const f = fixture(); f.state.method = null; f.state.signalFault = f.fault;
    await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 7)); assert.equal(f.destroys.length, 0);
  });
  await t.test("body rejection prevents signal access and wins over signal refusal", async () => {
    const f = fixture(); f.state.bodyFault = f.fault; f.state.signalFault = new Error("PUBLIC later signal refusal");
    await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 6));
  });
  for (const request of [undefined, null]) await t.test(`nullish request ${String(request)} reaches body before signal refusal`, async () => {
    const f = fixture(); await assert.rejects(f.invoke(f.params, request), isError);
    assert.deepEqual(f.trace, order.slice(0, 6)); assert.equal(f.bodies[0][0], request); assert.equal(f.destroys.length, 0);
  });
  await t.test("missing signal forwards undefined and inherited signal getter is read exactly once", async () => {
    const f = fixture(); await f.invoke(f.params, {}); exact(f, f.actor, "PUBLIC-ID", f.body, f.engine, undefined);
    const g = fixture(), signal = opaque("inherited signal"); let reads = 0;
    const request = Object.create({ get signal() { reads++; g.trace.push("signal"); return signal; } });
    Object.defineProperty(request, "unused", { get() { throw g.fault; } });
    await g.invoke(g.params, request); exact(g, g.actor, "PUBLIC-ID", g.body, g.engine, signal); assert.equal(reads, 1); assert.deepEqual(g.trace, order);
  });
  await t.test("held rejected body never reads a newly faulting signal", async () => {
    const f = fixture(), held = deferred(); f.state.body = held.promise;
    const pending = assert.rejects(f.invoke(), e => e === f.fault); await turns(); f.state.signalFault = new Error("PUBLIC later signal fault");
    held.reject(f.fault); await pending; assert.deepEqual(f.trace, order.slice(0, 6)); assert.equal(f.destroys.length, 0);
  });
  await t.test("fresh invocations observe new signal identities once per call", async () => {
    const f = fixture(), signal = opaque("fresh signal"); await f.invoke(); f.state.signal = signal; await f.invoke();
    exact(f, f.actor, "PUBLIC-ID", f.body, f.engine, signal); assert.deepEqual(f.trace, [...order, ...order]); assert.equal(f.destroys[0].args[3], f.signal);
  });
  await t.test("interleaved bodies read each original request signal only when that body resolves", async () => {
    const f = fixture(), a = deferred(), b = deferred(), actorB = opaque("distinct actor"), signalB = opaque("distinct signal"), bodyB = Object.freeze({ public: "DISTINCT-BODY" });
    let signalA: unknown = f.signal, readsA = 0, readsB = 0;
    const requestA = { get signal() { readsA++; return signalA; } }, requestB = { get signal() { readsB++; return signalB; } };
    f.state.body = a.promise; const first = f.invoke(f.params, requestA); await turns();
    const engineB = { destroy: f.method }; f.state.engine = engineB; f.state.body = b.promise;
    const second = f.invoke({ id: "DISTINCT-B" }, requestB, actorB); await turns(); assert.equal(readsA, 0); assert.equal(readsB, 0);
    b.resolve(bodyB); assert.equal(await second, f.result); exact(f, actorB, "DISTINCT-B", bodyB, engineB, signalB); assert.equal(readsA, 0); assert.equal(readsB, 1);
    signalA = opaque("signal A after B"); a.resolve(f.body); assert.equal(await first, f.result); exact(f, f.actor, "PUBLIC-ID", f.body, f.engine, signalA);
    assert.equal(readsA, 1); assert.equal(readsB, 1); assert.equal(f.bodies[0][0], requestA); assert.equal(f.bodies[1][0], requestB);
  });
  await t.test("held result retains originally passed signal after later replacement", async () => {
    const f = fixture(), held = deferred(); f.state.result = held.promise; const first = f.invoke(); await turns();
    f.state.signal = opaque("later signal"); exact(f); held.resolve(f.result); assert.equal(await first, f.result); assert.equal(f.destroys.length, 1);
  });

});
