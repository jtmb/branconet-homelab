import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC SOURCE controls. Only captured POST callbacks execute.
// All imported implementations are inert; no body parsing or schema validation.
type Model = Record<string, any>;
type Kind = "mounts" | "paths";
const routes = { mounts: "src/app/api/kv/mounts/route.ts", paths: "src/app/api/kv/paths/route.ts" };
const compiled = Object.fromEntries(Object.entries(routes).map(([kind, file]) => [kind,
  ts.transpileModule(readFileSync(file, "utf8"), { fileName: file,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText]));
function deferred() {
  let resolve!: (value: any) => void, reject!: (error: unknown) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const turns = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
const sequence = ["method", "bodyMethod", "schema", "body", "invoke"];
const opaque = (name: string) => new Proxy({}, {
  get() { throw Error(`PUBLIC: ${name} inspection forbidden`); },
  ownKeys() { throw Error(`PUBLIC: ${name} enumeration forbidden`); },
});
function fixture(kind: Kind) {
  const calls: string[] = [], seen: Model = { wrappers: [], bodies: [], invocations: [], receivers: [] };
  const actor = opaque("actor"), request = opaque("request"), params = opaque("params"), schema = opaque("schema");
  const body = Object.freeze({ public: "BODY" }), result = Object.freeze({ public: "RESULT" }), fault = Error("PUBLIC-FAULT");
  const state: Model = { body, result, schema, faults: {}, method: undefined };
  const step = (name: string) => { calls.push(name); if (Object.hasOwn(state.faults, name)) throw state.faults[name]; };
  const selected = kind === "mounts" ? "createMount" : "registerPath";
  const registry = new Proxy({}, { get(_target, key) {
    assert.equal(key, selected); step("method");
    return state.method ?? function(this: unknown, ...args: unknown[]) {
      step("invoke"); seen.invocations.push(args); seen.receivers.push(this); return state.result;
    };
  }, ownKeys() { throw Error("PUBLIC: registry enumeration forbidden"); } });
  const wrapped = [() => { throw Error("PUBLIC: GET wrapper inert"); }, () => { throw Error("PUBLIC: POST wrapper inert"); }];
  const http = {
    kvHuman(...args: any[]) { seen.wrappers.push(args); return wrapped[seen.wrappers.length - 1]; },
    get kvBody() {
      step("bodyMethod"); return function(this: unknown, ...args: unknown[]) {
        step("body"); seen.bodies.push({ receiver: this, args }); return state.body;
      };
    },
    metadataCursor() { throw Error("PUBLIC: GET cursor forbidden"); },
  };
  const schemas = new Proxy({}, { get(_target, key) {
    assert.equal(key, kind === "mounts" ? "mountCreate" : "pathCreate"); step("schema"); return state.schema;
  } });
  const m = { exports: {} as Model };
  runInNewContext(compiled[kind], { module: m, exports: m.exports,
    URL() { throw Error("PUBLIC: GET URL forbidden"); }, require: (name: string) => {
      if (name === "@/lib/kv-http") return http;
      assert.equal(name, "@/lib/kv-schemas"); return schemas;
    } }, { filename: routes[kind], timeout: 5000 });
  assert.deepEqual(calls, []);
  return { calls, seen, actor, request, params, schema, registry, state, body, result, fault, wrapped, exports: m.exports,
    invoke: (a: unknown = actor, q: unknown = request, p: unknown = params) => seen.wrappers[1][0](registry, a, q, p) };
}
for (const kind of ["mounts", "paths"] as const) test(`${kind} POST exact SOURCE delegation`, async t => {
  await t.test("registers exact default GET and201 POST wrappers and runtime without operation execution", () => {
    const f = fixture(kind); assert.deepEqual(Object.keys(f.exports).sort(), ["GET", "POST", "dynamic", "runtime"]);
    assert.equal(f.exports.GET, f.wrapped[0]); assert.equal(f.exports.POST, f.wrapped[1]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    assert.equal(f.seen.wrappers.length, 2); assert.equal(f.seen.wrappers[0].length, 1);
    assert.equal(f.seen.wrappers[1].length, 2); assert.equal(f.seen.wrappers[1][1], 201);
    assert.equal(typeof f.seen.wrappers[0][0], "function"); assert.equal(typeof f.seen.wrappers[1][0], "function");
    assert.deepEqual(f.calls, []); assert.deepEqual(f.seen.invocations, []);
  });
  await t.test("delegates exact request and selected schema then actor and resolved body with receiver", async () => {
    const f = fixture(kind), returned = f.invoke(); assert.deepEqual(f.calls, sequence.slice(0, 4));
    assert.equal(await returned, f.result); assert.deepEqual(f.calls, sequence);
    assert.deepEqual(f.seen.bodies[0].args, [f.request, f.schema]); assert.equal(f.seen.bodies[0].receiver, undefined);
    assert.deepEqual(f.seen.invocations, [[f.actor, f.body]]); assert.equal(f.seen.receivers[0], f.registry);
  });
  await t.test("does not inspect actor/request/params/schema or invoke GET/body/schema implementations", async () => {
    const f = fixture(kind); assert.equal(await f.invoke(), f.result); assert.deepEqual(f.calls, sequence);
  });
  for (const stage of sequence) for (const label of ["error", "object"] as const)
    await t.test(`exact ${stage} ${label} refusal stops later source work`, async () => {
      const f = fixture(kind), error = label === "error" ? f.fault : Object.freeze({ public: "REFUSAL" });
      f.state.faults[stage] = error; await assert.rejects(f.invoke(), e => e === error);
      assert.deepEqual(f.calls, sequence.slice(0, sequence.indexOf(stage) + 1)); assert.equal(f.seen.invocations.length, 0);
    });
  for (const body of [undefined, null, false, 0, "", Object.freeze({ public: "RAW-BODY" })])
    await t.test(`body model ${String(body)} forwards unchanged without route validation`, async () => {
      const f = fixture(kind); f.state.body = body; assert.equal(await f.invoke(), f.result);
      assert.equal(f.seen.invocations[0][1], body); assert.deepEqual(f.calls, sequence);
    });
  for (const result of [undefined, null, false, 0, ""])
    await t.test(`resolved result ${String(result)} forwards unchanged`, async () => {
      const f = fixture(kind); f.state.result = result; assert.equal(await f.invoke(), result); assert.deepEqual(f.calls, sequence);
    });
  await t.test("frozen nested result identities remain exact without cloning", async () => {
    const f = fixture(kind), rows = Object.freeze([Object.freeze({ public: "ROW" })]);
    f.state.result = Object.freeze({ rows }); const value = await f.invoke();
    assert.equal(value, f.state.result); assert.equal(value.rows, rows);
  });
  await t.test("held body prevents invocation until exact fulfillment", async () => {
    const f = fixture(kind), hold = deferred(); f.state.body = hold.promise;
    const returned = f.invoke(); let settled = false;
    const observed = returned.then((value: unknown) => { settled = true; return value; });
    await turns(); assert.deepEqual(f.calls, sequence.slice(0, 4)); assert.equal(settled, false);
    hold.resolve(f.body); assert.equal(await observed, f.result); assert.deepEqual(f.seen.invocations, [[f.actor, f.body]]);
  });
  await t.test("held body refusal retains exact identity and never invokes registry", async () => {
    const f = fixture(kind), hold = deferred(); f.state.body = hold.promise;
    const refused = assert.rejects(f.invoke(), e => e === f.fault); await turns();
    assert.deepEqual(f.calls, sequence.slice(0, 4)); hold.reject(f.fault); await refused;
    assert.deepEqual(f.calls, sequence.slice(0, 4)); assert.equal(f.seen.invocations.length, 0);
  });
  await t.test("already rejected body stops registry with exact refusal", async () => {
    const f = fixture(kind); f.state.body = Promise.reject(f.fault);
    await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.calls, sequence.slice(0, 4));
  });
  await t.test("method and actor are captured before await while receiver remains registry", async () => {
    const f = fixture(kind), hold = deferred(), captured: unknown[][] = []; f.state.body = hold.promise;
    f.state.method = function(this: unknown, ...args: unknown[]) { captured.push([this, ...args]); return f.result; };
    const returned = f.invoke(); f.state.method = () => { throw Error("PUBLIC: later method forbidden"); };
    f.state.schema = opaque("later schema"); await turns(); assert.deepEqual(captured, []);
    hold.resolve(f.body); assert.equal(await returned, f.result); assert.deepEqual(captured, [[f.registry, f.actor, f.body]]);
    assert.deepEqual(f.seen.bodies[0].args, [f.request, f.schema]); assert.deepEqual(f.calls, sequence.slice(0, 4));
  });
  await t.test("async callback adopts held registry result and preserves fulfillment identity", async () => {
    const f = fixture(kind), hold = deferred(); f.state.result = hold.promise;
    const returned = f.invoke(); assert.notEqual(returned, hold.promise); let settled = false;
    const observed = returned.then((value: unknown) => { settled = true; return value; }); await turns();
    assert.equal(settled, false); assert.deepEqual(f.calls, sequence);
    hold.resolve(f.result); assert.equal(await observed, f.result); assert.equal(f.seen.invocations.length, 1);
  });
  await t.test("held registry rejection propagates exact identity without retry", async () => {
    const f = fixture(kind), hold = deferred(); f.state.result = hold.promise;
    const refused = assert.rejects(f.invoke(), e => e === f.fault); await turns(); hold.reject(f.fault); await refused;
    assert.deepEqual(f.calls, sequence); assert.equal(f.seen.invocations.length, 1);
  });
  await t.test("already rejected registry result is adopted without error mapping", async () => {
    const f = fixture(kind), hold = deferred(); f.state.result = hold.promise;
    const refused = assert.rejects(f.invoke(), e => e === f.fault); hold.reject(f.fault); await refused;
    assert.deepEqual(f.calls, sequence); assert.equal(f.seen.invocations.length, 1);
  });
  await t.test("fresh call after body refusal reacquires method/schema/body and actor", async () => {
    const f = fixture(kind); f.state.faults.body = f.fault; await assert.rejects(f.invoke(), e => e === f.fault);
    delete f.state.faults.body; const actor = Object.freeze({ public: "NEXT-ACTOR" }), body = Object.freeze({ public: "NEXT-BODY" });
    f.state.body = body; assert.equal(await f.invoke(actor), f.result); assert.deepEqual(f.seen.invocations, [[actor, body]]);
    assert.deepEqual(f.calls, [...sequence.slice(0, 4), ...sequence]);
  });
  await t.test("interleaved held bodies retain distinct actor/request/schema and settle independently", async () => {
    const f = fixture(kind), first = deferred(), second = deferred(), actor = Object.freeze({ public: "NEXT-ACTOR" });
    const request = opaque("second request"), schema = opaque("second schema"), body = Object.freeze({ public: "NEXT-BODY" });
    f.state.body = first.promise; const a = f.invoke(); f.state.body = second.promise; f.state.schema = schema;
    const b = f.invoke(actor, request); second.resolve(body); assert.equal(await b, f.result);
    assert.deepEqual(f.seen.invocations, [[actor, body]]); let settled = false;
    const observed = a.then((value: unknown) => { settled = true; return value; }); await turns(); assert.equal(settled, false);
    first.resolve(f.body); assert.equal(await observed, f.result);
    assert.deepEqual(f.seen.invocations, [[actor, body], [f.actor, f.body]]);
    assert.deepEqual(f.seen.bodies.map((x: Model) => x.args), [[f.request, f.schema], [request, schema]]);
    assert.deepEqual(f.calls, [...sequence.slice(0, 4), ...sequence, "invoke"]);
  });
});
