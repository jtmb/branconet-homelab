import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC SOURCE controls: only PATCH callbacks execute. All imports,
// wrappers, body/schema/registry implementations and requests are inert models.
type Model = Record<string, any>;
type Kind = "mounts" | "paths";
const routes = { mounts: "src/app/api/kv/mounts/[id]/route.ts", paths: "src/app/api/kv/paths/[id]/route.ts" };
const compiled = Object.fromEntries(Object.entries(routes).map(([kind, file]) => [kind,
  ts.transpileModule(readFileSync(file, "utf8"), { fileName: file,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText]));
function deferred() {
  let resolve!: (value: any) => void, reject!: (error: unknown) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const turns = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
const opaque = (label: string) => new Proxy({}, {
  get() { throw Error(`PUBLIC: ${label} inspection forbidden`); },
  ownKeys() { throw Error(`PUBLIC: ${label} enumeration forbidden`); },
});
const prefix = ["id", "bodyMethod", "schema", "body"];
const mountTail = ["revision", "ownKeys", "descriptor:name", "get:name", "descriptor:namespace", "get:namespace", "descriptor:hidden", "method", "invoke"];
const pathTail = ["method", "revision", "retention", "invoke"];
function fixture(kind: Kind) {
  const calls: string[] = [], seen: Model = { wrappers: [], bodies: [], invocations: [], receivers: [] };
  const actor = opaque("actor"), request = opaque("request"), schema = opaque("schema"), id = opaque("id");
  const result = Object.freeze({ public: "RESULT" }), revision = Object.freeze({ public: "REVISION" });
  const name = Object.freeze({ public: "NAME" }), namespace = Object.freeze({ public: "NAMESPACE" }), retention = Object.freeze({ public: "RETENTION" });
  const state: Model = { result, schema, id, faults: {}, method: undefined };
  const step = (label: string) => { calls.push(label); if (Object.hasOwn(state.faults, label)) throw state.faults[label]; };
  const target = Object.create({ inherited: "PUBLIC-INHERITED" });
  Object.defineProperties(target, {
    revision: { enumerable: true, configurable: true, value: revision },
    name: { enumerable: true, configurable: true, value: name },
    namespace: { enumerable: true, configurable: true, value: namespace },
    retention: { enumerable: false, configurable: true, value: retention },
    hidden: { enumerable: false, configurable: true, value: "PUBLIC-HIDDEN" },
  });
  if (kind === "mounts") delete target.retention;
  const body = new Proxy(target, {
    get(obj, key, receiver) {
      if (key === "then") return undefined;
      if (key === "revision" || key === "retention") step(String(key));
      else step(`get:${String(key)}`);
      return Reflect.get(obj, key, receiver);
    },
    ownKeys(obj) { step("ownKeys"); return Reflect.ownKeys(obj); },
    getOwnPropertyDescriptor(obj, key) { step(`descriptor:${String(key)}`); return Reflect.getOwnPropertyDescriptor(obj, key); },
  });
  state.body = body;
  const methodName = kind === "mounts" ? "changeMount" : "changeRetention";
  const registry = new Proxy({}, { get(_target, key) {
    assert.equal(key, methodName); step("method");
    return state.method ?? function(this: unknown, ...args: unknown[]) {
      step("invoke"); seen.invocations.push(args); seen.receivers.push(this); return state.result;
    };
  }, ownKeys() { throw Error("PUBLIC: registry enumeration forbidden"); } });
  const params = new Proxy({}, { get(_target, key) { assert.equal(key, "id"); step("id"); return state.id; },
    ownKeys() { throw Error("PUBLIC: params enumeration forbidden"); } });
  const wrapped = [() => { throw Error("PUBLIC: wrapper zero inert"); }, () => { throw Error("PUBLIC: wrapper one inert"); }];
  const http = {
    kvHuman(...args: any[]) { seen.wrappers.push(args); return wrapped[seen.wrappers.length - 1]; },
    get kvBody() { step("bodyMethod"); return function(this: unknown, ...args: unknown[]) {
      step("body"); seen.bodies.push({ receiver: this, args }); return state.body;
    }; },
  };
  const schemas = new Proxy({}, { get(_target, key) {
    assert.equal(key, kind === "mounts" ? "mountUpdate" : "pathUpdate"); step("schema"); return state.schema;
  } });
  const m = { exports: {} as Model };
  runInNewContext(compiled[kind], { module: m, exports: m.exports, require: (name: string) => {
    if (name === "@/lib/kv-http") return http;
    assert.equal(name, "@/lib/kv-schemas"); return schemas;
  } }, { filename: routes[kind], timeout: 5000 });
  assert.deepEqual(calls, []);
  return { calls, seen, actor, request, schema, id, revision, name, namespace, retention, result, body, target,
    registry, params, state, wrapped, exports: m.exports, sequence: [...prefix, ...(kind === "mounts" ? mountTail : pathTail)],
    invoke: (a: unknown = actor, q: unknown = request, p: unknown = params) => seen.wrappers[kind === "mounts" ? 0 : 1][0](registry, a, q, p) };
}
for (const kind of ["mounts", "paths"] as const) test(`${kind} PATCH exact SOURCE delegation`, async t => {
  await t.test("registers exact default-status wrappers and nodejs runtime without other operations", () => {
    const f = fixture(kind), other = kind === "mounts" ? "DELETE" : "GET", patch = kind === "mounts" ? 0 : 1;
    assert.deepEqual(Object.keys(f.exports).sort(), [other, "PATCH", "runtime"].sort());
    assert.equal(f.exports.PATCH, f.wrapped[patch]); assert.equal(f.exports[other], f.wrapped[1 - patch]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.seen.wrappers.length, 2);
    for (const args of f.seen.wrappers) { assert.equal(args.length, 1); assert.equal(typeof args[0], "function"); }
    assert.deepEqual(f.calls, []); assert.deepEqual(f.seen.invocations, []);
  });
  await t.test("delegates request/schema then exact captured actor/id/revision with original receiver", async () => {
    const f = fixture(kind), returned = f.invoke(); assert.deepEqual(f.calls, prefix);
    assert.equal(await returned, f.result); assert.deepEqual(f.calls, f.sequence);
    assert.deepEqual(f.seen.bodies[0].args, [f.request, f.schema]); assert.equal(f.seen.bodies[0].receiver, undefined);
    const args = f.seen.invocations[0]; assert.equal(args.length, 4);
    assert.equal(args[0], f.actor); assert.equal(args[1], f.id); assert.equal(args[2], f.revision);
    assert.equal(f.seen.receivers[0], f.registry);
    if (kind === "paths") assert.equal(args[3], f.retention);
    else { assert.notEqual(args[3], f.body); assert.deepEqual(Reflect.ownKeys(args[3]), ["name", "namespace"]);
      assert.equal(args[3].name, f.name); assert.equal(args[3].namespace, f.namespace); }
  });
  for (const stage of [...prefix, ...(kind === "mounts" ? mountTail : pathTail)]) for (const type of ["error", "object"])
    await t.test(`exact ${stage} ${type} refusal stops all later source work`, async () => {
      const f = fixture(kind), fault = type === "error" ? Error("PUBLIC-FAULT") : Object.freeze({ public: "REFUSAL" });
      f.state.faults[stage] = fault; await assert.rejects(f.invoke(), e => e === fault);
      assert.deepEqual(f.calls, f.sequence.slice(0, f.sequence.indexOf(stage) + 1)); assert.equal(f.seen.invocations.length, 0);
    });
  await t.test("held body prevents registry retrieval and body property inspection", async () => {
    const f = fixture(kind), hold = deferred(); f.state.body = hold.promise;
    const returned = f.invoke(); let settled = false;
    const observed = returned.then((v: unknown) => { settled = true; return v; });
    await turns(); assert.equal(settled, false); assert.deepEqual(f.calls, prefix);
    hold.resolve(f.body); assert.equal(await observed, f.result); assert.deepEqual(f.calls, f.sequence);
  });
  for (const label of ["held", "already-rejected"])
    await t.test(`${label} body refusal retains identity without registry/property access`, async () => {
      const f = fixture(kind), fault = Object.freeze({ public: "BODY-REFUSAL" }), hold = deferred();
      f.state.body = label === "held" ? hold.promise : Promise.reject(fault);
      const refused = assert.rejects(f.invoke(), e => e === fault); await turns();
      assert.deepEqual(f.calls, prefix); if (label === "held") hold.reject(fault); await refused;
      assert.deepEqual(f.calls, prefix); assert.equal(f.seen.invocations.length, 0);
    });
  await t.test("id captured before body await; registry method retrieved freshly after fulfillment", async () => {
    const f = fixture(kind), hold = deferred(), laterId = opaque("later id"), captured: unknown[][] = [];
    f.state.body = hold.promise; f.state.method = () => { throw Error("PUBLIC: old method forbidden"); };
    const returned = f.invoke(); f.state.id = laterId; f.state.schema = opaque("later schema");
    f.state.method = function(this: unknown, ...args: unknown[]) { captured.push([this, ...args]); return f.result; };
    await turns(); assert.deepEqual(captured, []); assert.deepEqual(f.calls, prefix);
    hold.resolve(f.body); assert.equal(await returned, f.result); assert.equal(captured.length, 1);
    assert.equal(captured[0][0], f.registry); assert.equal(captured[0][1], f.actor); assert.equal(captured[0][2], f.id);
    assert.deepEqual(f.seen.bodies[0].args, [f.request, f.schema]);
  });
  for (const value of [undefined, null, false, 0, ""])
    await t.test(`resolved result ${String(value)} is adopted unchanged`, async () => {
      const f = fixture(kind); f.state.result = value; assert.equal(await f.invoke(), value); assert.deepEqual(f.calls, f.sequence);
    });
  await t.test("frozen nested result retains object identities", async () => {
    const f = fixture(kind), rows = Object.freeze([Object.freeze({ public: "ROW" })]);
    f.state.result = Object.freeze({ rows }); const value = await f.invoke();
    assert.equal(value, f.state.result); assert.equal(value.rows, rows);
  });
  await t.test("async callback adopts held result without claiming raw promise identity", async () => {
    const f = fixture(kind), hold = deferred(); f.state.result = hold.promise;
    const returned = f.invoke(); assert.notEqual(returned, hold.promise); let settled = false;
    const observed = returned.then((v: unknown) => { settled = true; return v; }); await turns();
    assert.equal(settled, false); assert.deepEqual(f.calls, f.sequence); hold.resolve(f.result); assert.equal(await observed, f.result);
  });
  for (const label of ["held", "already-rejected"])
    await t.test(`${label} registry refusal retains exact identity with no retry`, async () => {
      const f = fixture(kind), hold = deferred(), fault = Object.freeze({ public: "RESULT-REFUSAL" });
      f.state.result = label === "held" ? hold.promise : Promise.reject(fault);
      const refused = assert.rejects(f.invoke(), e => e === fault); await turns();
      assert.deepEqual(f.calls, f.sequence); if (label === "held") hold.reject(fault); await refused;
      assert.equal(f.seen.invocations.length, 1); assert.deepEqual(f.calls, f.sequence);
    });
  await t.test("fresh calls do not reuse id/body/method/result models", async () => {
    const f = fixture(kind); assert.equal(await f.invoke(), f.result);
    const next = Object.freeze({ public: "NEXT" }); f.state.id = next; f.state.result = next;
    assert.equal(await f.invoke(), next); assert.equal(f.seen.invocations.length, 2);
    assert.equal(f.seen.invocations[0][1], f.id); assert.equal(f.seen.invocations[1][1], next);
    assert.deepEqual(f.calls, [...f.sequence, ...f.sequence]);
  });
  await t.test("interleaved bodies retain separate actor/id/request/schema arguments", async () => {
    const f = fixture(kind), first = deferred(), second = deferred(), actor2 = opaque("actor two"), request2 = opaque("request two"), id2 = opaque("id two");
    f.state.body = first.promise; const one = f.invoke();
    f.state.body = second.promise; f.state.id = id2; const two = f.invoke(actor2, request2);
    await turns(); assert.deepEqual(f.calls, [...prefix, ...prefix]);
    second.resolve(f.body); assert.equal(await two, f.result); assert.equal(f.seen.invocations[0][0], actor2); assert.equal(f.seen.invocations[0][1], id2);
    first.resolve(f.body); assert.equal(await one, f.result); assert.equal(f.seen.invocations[1][0], f.actor); assert.equal(f.seen.invocations[1][1], f.id);
    assert.deepEqual(f.seen.bodies.map((x: Model) => x.args), [[f.request, f.schema], [request2, f.schema]]);
  });
  for (const body of [undefined, null])
    await t.test(`nullish body ${String(body)} refuses at the exact property boundary`, async () => {
      const f = fixture(kind); f.state.body = body; await assert.rejects(f.invoke(), e => (e as Error).name === "TypeError");
      assert.deepEqual(f.calls, kind === "mounts" ? prefix : [...prefix, "method"]); assert.equal(f.seen.invocations.length, 0);
    });
  for (const body of [false, 0, ""])
    await t.test(`primitive body ${String(body)} receives no route validation`, async () => {
      const f = fixture(kind); f.state.body = body; assert.equal(await f.invoke(), f.result);
      const args = f.seen.invocations[0]; assert.equal(args[2], undefined);
      if (kind === "mounts") assert.deepEqual(Reflect.ownKeys(args[3]), []); else assert.equal(args[3], undefined);
      assert.deepEqual(f.calls, [...prefix, "method", "invoke"]);
    });
  await t.test("null params refuse before body or registry access", async () => {
    const f = fixture(kind); await assert.rejects(f.invoke(f.actor, f.request, null), e => (e as Error).name === "TypeError"); assert.deepEqual(f.calls, []);
  });
  if (kind === "mounts") {
    await t.test("rest copies own enumerable string/symbol values, excludes revision/inherited/hidden and safely owns __proto__", async () => {
      const f = fixture(kind), symbol = Symbol("PUBLIC"), value = Object.freeze({ public: "EXTRA" });
      const body = Object.create({ inherited: value });
      Object.defineProperties(body, { revision: { value: f.revision, enumerable: true },
        visible: { get: () => value, enumerable: true }, hidden: { value, enumerable: false },
        [symbol]: { value, enumerable: true } });
      // Define __proto__ explicitly as an own data property.
      Object.defineProperty(body, "__proto__", { value, enumerable: true });
      f.state.body = body; assert.equal(await f.invoke(), f.result); const input = f.seen.invocations[0][3];
      assert.deepEqual(Reflect.ownKeys(input), ["visible", "__proto__", symbol]);
      for (const key of Reflect.ownKeys(input)) {
        const d = Object.getOwnPropertyDescriptor(input, key)!; assert.equal(d.value, value);
        assert.equal(d.enumerable, true); assert.equal(d.configurable, true); assert.equal(d.writable, true);
      }
      assert.equal(Object.hasOwn(input, "revision"), false); assert.equal(Object.hasOwn(input, "inherited"), false); assert.equal(Object.hasOwn(input, "hidden"), false);
    });
    await t.test("rest getters finish before changeMount is retrieved", async () => {
      const f = fixture(kind), expected = Object.freeze({ public: "AFTER-REST" });
      f.state.body = { revision: f.revision, get name() { f.state.method = function(this: unknown, ...args: unknown[]) {
        assert.equal(this, f.registry); assert.equal(args[3] && (args[3] as Model).name, f.name); return expected;
      }; return f.name; } };
      assert.equal(await f.invoke(), expected);
    });
  } else {
    await t.test("changeRetention getter precedes revision and retention; captures method before getters mutate it", async () => {
      const f = fixture(kind), seen: unknown[][] = [];
      f.state.method = function(this: unknown, ...args: unknown[]) { seen.push([this, ...args]); return f.result; };
      f.state.body = { get revision() { f.state.method = () => { throw Error("PUBLIC: later method forbidden"); }; return f.revision; },
        get retention() { return f.retention; }, get extra() { throw Error("PUBLIC: extra inspection forbidden"); } };
      assert.equal(await f.invoke(), f.result); assert.deepEqual(seen, [[f.registry, f.actor, f.id, f.revision, f.retention]]);
    });
    await t.test("reads revision then retention with body receiver and no enumeration", async () => {
      const f = fixture(kind), seen: unknown[] = [];
      const body = { get revision() { seen.push(this); return f.revision; }, get retention() { seen.push(this); return f.retention; } };
      f.state.body = new Proxy(body, { ownKeys() { throw Error("PUBLIC: body enumeration forbidden"); } });
      assert.equal(await f.invoke(), f.result); assert.equal(seen.length, 2); assert.equal(seen[0], f.state.body); assert.equal(seen[1], f.state.body);
    });
  }
});
