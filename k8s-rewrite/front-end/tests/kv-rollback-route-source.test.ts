import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC rollback POST SOURCE controls. Every dependency is inert.
// No actual wrapper/body/schema/registry/engine/HTTP/auth/native/DB executes.
type Model = Record<string, any>;
const route = "src/app/api/kv/paths/[id]/rollback/route.ts";
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
  const trace: string[] = [], wrappers: any[][] = [], changes: Model[] = [], engines: unknown[][] = [], bodies: unknown[][] = [];
  const registry = opaque("registry"), actor = opaque("actor"), request = opaque("request"), schema = opaque("schema implementation");
  const body = Object.freeze({ public: "BODY" }), result = Object.freeze({ public: "RESULT" }), fault = new Error("PUBLIC-FAULT");
  const state: Model = { id: "PUBLIC-ID", engine: null, method: null, body, result, idFault: null, engineFault: null,
    methodFault: null, bodyGetterFault: null, schemaFault: null, bodyFault: null, changeFault: null,
    rejectBody: false, rejectChange: false, bodyHook: null };
  function method(this: unknown, ...args: unknown[]) {
    trace.push("change"); changes.push({ receiver: this, args });
    if (state.changeFault) { if (state.rejectChange) return Promise.reject(state.changeFault); throw state.changeFault; }
    return state.result;
  }
  const engine = Object.defineProperty({}, "change", { get() {
    trace.push("change-get"); if (state.methodFault) throw state.methodFault; return state.method;
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
  const schemas = { get nativeRollback() { trace.push("schema"); if (state.schemaFault) throw state.schemaFault; return schema; } };
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
  return { trace, wrappers, changes, engines, bodies, registry, actor, request, schema, body, result, fault,
    state, engine, method, params, wrapped, exports: m.exports,
    invoke: (...args: unknown[]) => callback(args.length > 3 ? args[3] : registry, args.length > 2 ? args[2] : actor,
      args.length > 1 ? args[1] : request, args.length ? args[0] : params) as Promise<unknown> };
}
type Fixture = ReturnType<typeof fixture>;
function exact(f: Fixture, ...values: unknown[]) {
  const actor = values.length ? values[0] : f.actor, id = values.length > 1 ? values[1] : "PUBLIC-ID";
  const body = values.length > 2 ? values[2] : f.body, receiver = values.length > 3 ? values[3] : f.engine;
  const call = f.changes.at(-1)!; assert.equal(call.receiver, receiver); assert.equal(call.args.length, 4);
  assert.equal(call.args[0], actor); assert.equal(call.args[1], id); assert.equal(call.args[2], body); assert.equal(call.args[3], "rollback");
}
const order = ["id", "engine", "change-get", "body-get", "schema", "body", "change"];
const isError = (e: unknown) => Object.prototype.toString.call(e) === "[object Error]";
test("human rollback POST exact SOURCE delegation", async t => {
  await t.test("nodejs export, exact single default-status inert wrapper", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["POST", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.POST, f.wrapped);
    assert.equal(f.wrappers[0].length, 1); assert.equal(typeof f.wrappers[0][0], "function"); assert.deepEqual(f.trace, []);
  });
  await t.test("ordered id/engine/method/body/schema plus exact registry/request/schema and four change arguments", async () => {
    const f = fixture(); assert.equal(await f.invoke(), f.result); exact(f); assert.deepEqual(f.trace, order);
    assert.equal(f.engines.length, 1); assert.equal(f.engines[0].length, 1); assert.equal(f.engines[0][0], f.registry);
    assert.equal(f.bodies.length, 1); assert.equal(f.bodies[0].length, 2); assert.equal(f.bodies[0][0], f.request); assert.equal(f.bodies[0][1], f.schema);
  });
  for (const [field, count] of [["idFault",1],["engineFault",2],["methodFault",3],["bodyGetterFault",4],["schemaFault",5],["bodyFault",6],["changeFault",7]] as const)
    await t.test(`${field} preserves exact refusal and stops later stages`, async () => {
      const f = fixture(); f.state[field] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault);
      assert.deepEqual(f.trace, order.slice(0, count)); assert.equal(f.changes.length, field === "changeFault" ? 1 : 0);
    });
  for (const stage of ["Body", "Change"]) await t.test(`rejected ${stage} promise keeps refusal identity`, async () => {
    const f = fixture(); f.state[stage === "Body" ? "bodyFault" : "changeFault"] = f.fault; f.state["reject"+stage] = true;
    await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.changes.length, stage === "Change" ? 1 : 0);
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
  for (const value of [undefined, null, 7, {}]) await t.test(`noncallable change ${String(value)} evaluated after held body`, async () => {
    const f = fixture(), held = deferred(); f.state.method = value; f.state.body = held.promise;
    const refused = assert.rejects(f.invoke(), isError); await turns(); assert.deepEqual(f.trace, order.slice(0, 6));
    assert.equal(f.changes.length, 0); held.resolve(f.body); await refused;
  });
  await t.test("body rejection precedes noncallable method refusal", async () => {
    const f = fixture(); f.state.method = null; f.state.bodyFault = f.fault;
    await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 6));
  });
  await t.test("inherited change retains exact engine receiver", async () => {
    const f = fixture(), e = Object.create({ change: f.method }); f.state.engine = e; await f.invoke(); exact(f, f.actor, "PUBLIC-ID", f.body, e);
  });
  await t.test("engine then is never inspected", async () => {
    const f = fixture(), e = { change: f.method, get then() { throw f.fault; } }; f.state.engine = e; await f.invoke(); exact(f, f.actor, "PUBLIC-ID", f.body, e);
  });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-BODY")]) await t.test(`body ${String(value)} forwarded without validation`, async () => {
    const f = fixture(); f.state.body = value; await f.invoke(); exact(f, f.actor, "PUBLIC-ID", value);
  });
  await t.test("await reads body then protocol only and never grouped data", async () => {
    const f = fixture(); let reads = 0;
    const body = new Proxy({}, { get(_t, key) { assert.equal(key, "then"); reads++; return undefined; }, ownKeys() { throw f.fault; } });
    f.state.body = body; await f.invoke(); exact(f, f.actor, "PUBLIC-ID", body); assert.equal(reads, 1);
  });
  await t.test("body throwing then getter refuses without change", async () => {
    const f = fixture(); f.state.body = { get then() { throw f.fault; } };
    await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.changes.length, 0);
  });
  await t.test("body thenable adopts first resolved identity", async () => {
    const f = fixture(); f.state.body = { then(resolve: (x: unknown) => void, reject: (x: unknown) => void) { resolve(f.body); reject(f.fault); resolve(null); } };
    await f.invoke(); exact(f);
  });
  await t.test("held body blocks change; captured receiver/method survive replacement", async () => {
    const f = fixture(), held = deferred(); f.state.body = held.promise;
    const pending = f.invoke(); await turns(); assert.deepEqual(f.trace, order.slice(0, 6)); assert.equal(f.changes.length, 0);
    f.state.engine = opaque("replacement engine"); f.state.method = () => { throw f.fault; };
    held.resolve(f.body); assert.equal(await pending, f.result); exact(f); assert.deepEqual(f.trace, order);
  });
  await t.test("body side effects cannot replace previously captured method", async () => {
    const f = fixture(); f.state.bodyHook = () => { f.state.method = null; f.state.engine = null; };
    await f.invoke(); exact(f);
  });
  await t.test("held rejected body preserves exact error and never changes", async () => {
    const f = fixture(), held = deferred(); f.state.body = held.promise; const pending = assert.rejects(f.invoke(), e => e === f.fault);
    await turns(); held.reject(f.fault); await pending; assert.equal(f.changes.length, 0);
  });
  for (const value of [undefined, null, false, 0, "", Symbol("PUBLIC-RESULT")]) await t.test(`result ${String(value)} adopted unchanged`, async () => {
    const f = fixture(); f.state.result = value; assert.equal(await f.invoke(), value); exact(f);
  });
  await t.test("held result stays pending after exactly one change", async () => {
    const f = fixture(), held = deferred(); f.state.result = held.promise; let settled = false;
    const pending = f.invoke().then(x => { settled = true; return x; }); await turns(); assert.equal(settled, false); exact(f);
    assert.equal(f.changes.length, 1); held.resolve(f.result); assert.equal(await pending, f.result);
  });
  await t.test("held result rejection propagates without retry", async () => {
    const f = fixture(), held = deferred(); f.state.result = held.promise; const pending = assert.rejects(f.invoke(), e => e === f.fault);
    await turns(); held.reject(f.fault); await pending; assert.equal(f.changes.length, 1);
  });
  await t.test("result thenable first resolve wins; no raw promise identity claim", async () => {
    const f = fixture(); f.state.result = { then(resolve: (x: unknown) => void, reject: (x: unknown) => void) { resolve(f.result); reject(f.fault); resolve(null); } };
    assert.equal(await f.invoke(), f.result); assert.equal(f.changes.length, 1);
  });
  await t.test("result throwing then getter propagates after one change", async () => {
    const f = fixture(); f.state.result = { get then() { throw f.fault; } };
    await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.changes.length, 1);
  });
  await t.test("fresh invocations re-read id/engine/method/body with distinct input identities", async () => {
    const f = fixture(); await f.invoke(); const body = Object.freeze({ public: "BODY-2" }), actor = opaque("actor-2"), request = opaque("request-2");
    f.state.id = "PUBLIC-ID-2"; f.state.body = body; await f.invoke(f.params, request, actor);
    exact(f, actor, "PUBLIC-ID-2", body); assert.equal(f.bodies[1][0], request); assert.deepEqual(f.trace, [...order, ...order]);
  });
  await t.test("interleaved held bodies preserve per-call engine/actor/id/request/input identities", async () => {
    const f = fixture(), a = deferred(), b = deferred(), actorB = opaque("actor-B"), requestB = opaque("request-B"), bodyB = Object.freeze({ public: "BODY-B" });
    f.state.body = a.promise; const first = f.invoke(); await turns();
    const engineB = { change: f.method }; f.state.engine = engineB; f.state.body = b.promise;
    const second = f.invoke({ id: "PUBLIC-B" }, requestB, actorB); await turns(); assert.equal(f.changes.length, 0);
    b.resolve(bodyB); assert.equal(await second, f.result); exact(f, actorB, "PUBLIC-B", bodyB, engineB);
    a.resolve(f.body); assert.equal(await first, f.result); exact(f); assert.equal(f.changes.length, 2);
    assert.equal(f.bodies[0][0], f.request); assert.equal(f.bodies[1][0], requestB);
  });
  await t.test("interleaved results settle independently without automatic retries", async () => {
    const f = fixture(), a = deferred(), b = deferred(); f.state.result = a.promise;
    const first = f.invoke(); await turns(); f.state.result = b.promise; const second = f.invoke({ id: "PUBLIC-B" }); await turns();
    const secondResult = Object.freeze({ public: "RESULT-B" }); b.resolve(secondResult); assert.equal(await second, secondResult);
    a.resolve(f.result); assert.equal(await first, f.result); assert.equal(f.changes.length, 2);
  });
});
