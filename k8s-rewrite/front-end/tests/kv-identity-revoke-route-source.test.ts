import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC selected DELETE SOURCE controls. Every imported implementation is inert.
type Model = Record<string, any>;
const path = "src/app/api/kv/identities/[id]/route.ts";
const compiled = ts.transpileModule(readFileSync(path, "utf8"), {
  fileName: path, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
}).outputText;
const isError = (e: unknown) => Object.prototype.toString.call(e) === "[object Error]";
function opaque(label: string) { return new Proxy({}, { get() { throw Error(`PUBLIC unexpected ${label} read`); }, ownKeys() { throw Error(`PUBLIC unexpected ${label} enumeration`); } }); }
function deferred() {
  let resolve!: (v: any) => void, reject!: (e: any) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function fixture() {
  const trace: string[] = [], wrappers: any[][] = [], bodies: Model[] = [], calls: Model[] = [];
  const id = opaque("id"), revision = opaque("revision"), actor = opaque("actor"), request = opaque("request"), schema = opaque("schema");
  const result = { public: "RESULT" }, marker = opaque("DELETE marker"), fault = Error("PUBLIC-FAULT");
  const state: Model = { id, revision, result, faults: {}, hooks: {} };
  function step(name: string) { trace.push(name); if (state.hooks[name]) state.hooks[name](); if (state.faults[name]) throw state.faults[name]; }
  const params = Object.defineProperty({}, "id", { get() { step("id"); return state.id; } });
  const input = Object.defineProperties({}, {
    revision: { get() { step("revision"); return state.revision; } },
    publicUnused: { enumerable: true, get() { throw fault; } },
    [Symbol("PUBLIC-unused")]: { enumerable: true, get() { throw fault; } }
  });
  const method = function(this: unknown, ...args: unknown[]) { calls.push({ receiver: this, args }); step("call"); return state.result; };
  const registry = Object.defineProperty({}, "revokeIdentity", { get() { step("method"); return state.method; } });
  const body = function(this: unknown, ...args: unknown[]) { bodies.push({ receiver: this, args }); step("body"); return state.input; };
  Object.assign(state, { input, method, body, schema });
  const imports = new Proxy({ kvHuman(...args: any[]) { wrappers.push(args); return marker; }, get kvBody() { step("body-get"); return state.body; } }, {
    get(t, k, receiver) { assert.ok(k === "kvHuman" || k === "kvBody"); return Reflect.get(t, k, receiver); }
  });
  const schemas = new Proxy(Object.defineProperty({}, "identityRevoke", { get() { step("schema-get"); return state.schema; } }), {
    get(t, k, receiver) { assert.equal(k, "identityRevoke"); return Reflect.get(t, k, receiver); }
  });
  const m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, require: (name: string) => {
    if (name === "@/lib/kv-http") return imports;
    assert.equal(name, "@/lib/kv-schemas"); return schemas;
  } }, { filename: path, timeout: 5000 });
  assert.equal(wrappers.length, 1); assert.deepEqual(trace, [] as string[]);
  const callback = wrappers[0][0];
  return { id, revision, actor, request, schema, result, marker, fault, params, input, method, registry, body, state, trace, wrappers, bodies, calls, callback, exports: m.exports,
    invoke: (...args: unknown[]) => callback(args.length ? args[0] : registry, args.length > 1 ? args[1] : actor, args.length > 2 ? args[2] : request, args.length > 3 ? args[3] : params) as Promise<unknown> };
}
type Fixture = ReturnType<typeof fixture>;
const order = ["id", "body-get", "schema-get", "body", "method", "revision", "call"];
function exact(f: Fixture, ...overrides: unknown[]) {
  const [registry, actor, request, schema, id, revision] = [f.registry, f.actor, f.request, f.schema, f.id, f.revision].map((v, i) => i < overrides.length ? overrides[i] : v);
  const b = f.bodies.at(-1)!, m = f.calls.at(-1)!;
  assert.equal(b.receiver, undefined); assert.equal(b.args.length, 2); assert.equal(b.args[0], request); assert.equal(b.args[1], schema);
  assert.equal(m.receiver, registry); assert.equal(m.args.length, 3); assert.equal(m.args[0], actor); assert.equal(m.args[1], id); assert.equal(m.args[2], revision);
}
test("human identity-revoke DELETE exact asynchronous SOURCE delegation", async t => {
  await t.test("exact nodejs default-status DELETE wrapper with no dynamic export", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["DELETE", "runtime"]); assert.equal(f.exports.runtime, "nodejs");
    assert.equal(Object.hasOwn(f.exports, "dynamic"), false); assert.equal(f.wrappers[0].length, 1); assert.equal(typeof f.callback, "function"); assert.equal(f.exports.DELETE, f.marker);
  });
  await t.test("entry id body schema await method revision and call exact order", async () => {
    const f = fixture(), p = f.invoke(); assert.deepEqual(f.trace, order.slice(0, 4)); assert.equal(f.calls.length, 0);
    assert.equal(await p, f.result); assert.deepEqual(f.trace, order); exact(f);
  });
  for (const [i, stage] of order.entries()) await t.test(`${stage} refusal preserves reason and stops later work`, async () => {
    const f = fixture(); f.state.faults[stage] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault);
    assert.deepEqual(f.trace, order.slice(0, i + 1)); assert.equal(f.calls.length, stage === "call" ? 1 : 0);
  });
  for (const value of [undefined, null, false, 0, "", 7, "PUBLIC", Symbol("PUBLIC"), 3n]) {
    await t.test(`actor ${String(value)} passes unread`, async () => { const f = fixture(); assert.equal(await f.invoke(f.registry, value), f.result); exact(f, f.registry, value); });
    await t.test(`request ${String(value)} passes unread`, async () => { const f = fixture(); assert.equal(await f.invoke(f.registry, f.actor, value), f.result); exact(f, f.registry, f.actor, value); });
    await t.test(`schema ${String(value)} captured unchanged`, async () => { const f = fixture(); f.state.schema = value; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, value); });
    await t.test(`id ${String(value)} captured unread`, async () => { const f = fixture(); f.state.id = value; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, value); });
    await t.test(`revision ${String(value)} captured unread`, async () => { const f = fixture(); f.state.revision = value; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, f.id, value); });
    await t.test(`result ${String(value)} asynchronously adopted`, async () => { const f = fixture(); f.state.result = value; assert.equal(await f.invoke(), value); exact(f); });
  }
  for (const value of [undefined, null]) {
    await t.test(`nullish params ${String(value)} refuses before imports`, async () => { const f = fixture(); await assert.rejects(f.invoke(f.registry, f.actor, f.request, value), isError); assert.deepEqual(f.trace, [] as string[]); });
    await t.test(`nullish input ${String(value)} captures method then refuses revision`, async () => { const f = fixture(); f.state.input = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 5)); });
    await t.test(`nullish registry ${String(value)} refuses after body before revision`, async () => { const f = fixture(); await assert.rejects(f.invoke(value), isError); assert.deepEqual(f.trace, order.slice(0, 4)); assert.equal(f.bodies.length, 1); });
  }
  await t.test("missing fourth argument refuses before body access", async () => { const f = fixture(); await assert.rejects(f.callback(), isError); assert.deepEqual(f.trace, [] as string[]); });
  for (const value of [undefined, null, false, 0, "", {}, Symbol("PUBLIC")]) {
    await t.test(`noncallable body ${String(value)} reads schema before refusal`, async () => { const f = fixture(); f.state.body = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 3)); assert.equal(f.bodies.length, 0); });
    await t.test(`noncallable revoke ${String(value)} reads revision before refusal`, async () => { const f = fixture(); f.state.method = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 6)); assert.equal(f.calls.length, 0); });
  }
  await t.test("schema refusal wins over noncallable captured body", async () => { const f = fixture(); f.state.body = null; f.state.faults["schema-get"] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 3)); });
  await t.test("id refusal wins over body refusal", async () => { const f = fixture(); f.state.faults.id = f.fault; f.state.faults["body-get"] = Error("PUBLIC-LATER"); await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, ["id"]); });
  await t.test("method refusal wins over revision refusal", async () => { const f = fixture(); f.state.faults.method = f.fault; f.state.faults.revision = Error("PUBLIC-LATER"); await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 5)); });
  await t.test("revision refusal wins over noncallable captured revoke", async () => { const f = fixture(); f.state.method = null; f.state.faults.revision = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 6)); });
  for (const stage of ["schema-get", "body"]) await t.test(`${stage} cannot replace captured body`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.body = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("body getter may replace schema before lookup", async () => { const f = fixture(), schema = opaque("replacement schema"); f.state.hooks["body-get"] = () => { f.state.schema = schema; }; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, schema); });
  await t.test("id getter may replace body before capture", async () => { const f = fixture(); f.state.hooks.id = () => { f.state.body = function(...args: unknown[]) { f.bodies.push({ receiver: undefined, args }); f.trace.push("body"); return f.input; }; }; assert.equal(await f.invoke(), f.result); exact(f); });
  for (const stage of ["body-get", "schema-get", "body", "method", "revision"]) await t.test(`${stage} cannot replace already captured id`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.id = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  for (const stage of ["body-get", "schema-get", "body"]) await t.test(`${stage} may replace method before lookup`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.method = function(this: unknown, ...args: unknown[]) { f.calls.push({ receiver: this, args }); f.trace.push("replacement-call"); return f.result; }; }; assert.equal(await f.invoke(), f.result); exact(f); assert.equal(f.trace.at(-1), "replacement-call"); });
  await t.test("revision getter cannot replace captured method", async () => { const f = fixture(); f.state.hooks.revision = () => { f.state.method = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("method getter may replace revision before lookup", async () => { const f = fixture(), revision = opaque("replacement revision"); f.state.hooks.method = () => { f.state.revision = revision; }; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, f.id, revision); });
  await t.test("inherited method getter receives exact registry", async () => { const f = fixture(); const proto = Object.defineProperty({}, "revokeIdentity", { get() { assert.equal(this, registry); return f.method; } }); const registry = Object.create(proto); assert.equal(await f.invoke(registry), f.result); exact(f, registry); });
  await t.test("registry proxy selects only revokeIdentity without enumeration", async () => { const f = fixture(); const registry = new Proxy({}, { get(_t, key) { assert.equal(key, "revokeIdentity"); return f.method; }, ownKeys() { throw f.fault; } }); assert.equal(await f.invoke(registry), f.result); exact(f, registry); });
  await t.test("missing method refuses after revision without fallback", async () => { const f = fixture(); await assert.rejects(f.invoke(Object.create(null)), isError); assert.deepEqual(f.trace, ["id", "body-get", "schema-get", "body", "revision"]); });
  for (const value of [false, 0, "PUBLIC", Symbol("PUBLIC"), 3n]) await t.test(`primitive registry ${String(value)} selects missing method`, async () => { const f = fixture(); await assert.rejects(f.invoke(value), isError); assert.deepEqual(f.trace, ["id", "body-get", "schema-get", "body", "revision"]); });
  for (const params of [false, 0, "PUBLIC", Symbol("PUBLIC"), 3n, {}, Object.create(null)]) await t.test(`missing id on ${Object.prototype.toString.call(params)} passes undefined`, async () => { const f = fixture(); assert.equal(await f.invoke(f.registry, f.actor, f.request, params), f.result); exact(f, f.registry, f.actor, f.request, f.schema, undefined); assert.deepEqual(f.trace, order.slice(1)); });
  await t.test("inherited id getter receives original params", async () => { const f = fixture(); const params = Object.create(Object.defineProperty({}, "id", { get() { assert.equal(this, params); return f.id; } })); assert.equal(await f.invoke(f.registry, f.actor, f.request, params), f.result); exact(f); });
  await t.test("params proxy reads only id without enumeration", async () => { const f = fixture(); const params = new Proxy({}, { get(_t, k) { assert.equal(k, "id"); return f.id; }, ownKeys() { throw f.fault; } }); assert.equal(await f.invoke(f.registry, f.actor, f.request, params), f.result); exact(f); });
  await t.test("inherited revision getter receives original input", async () => { const f = fixture(); const input = Object.create(Object.defineProperty({}, "revision", { get() { assert.equal(this, input); return f.revision; } })); f.state.input = input; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("nonenumerable revision is selected", async () => { const f = fixture(); f.state.input = Object.defineProperty({}, "revision", { value: f.revision }); assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("missing revision passes undefined", async () => { const f = fixture(); f.state.input = Object.create(null); assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, f.id, undefined); });
  await t.test("input proxy reads then and revision only with no enumeration descriptors or symbols", async () => {
    const f = fixture(), seen: PropertyKey[] = [];
    f.state.input = new Proxy({}, { get(_t, key) { seen.push(key); if (key === "then") return undefined; if (key === "revision") return f.revision; throw f.fault; }, ownKeys() { throw f.fault; }, getOwnPropertyDescriptor() { throw f.fault; } });
    assert.equal(await f.invoke(), f.result); exact(f); assert.deepEqual(seen, ["then", "revision"]);
  });
  for (const value of [false, 0, 7, 3n, Symbol("PUBLIC"), "", "PUBLIC"]) await t.test(`primitive input ${String(value)} passes missing revision`, async () => { const f = fixture(); f.state.input = value; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, f.id, undefined); });
  await t.test("pending body prevents method and revision reads", async () => { const f = fixture(), d = deferred(); f.state.input = d.promise; const p = f.invoke(); assert.deepEqual(f.trace, order.slice(0, 4)); d.resolve(f.input); assert.equal(await p, f.result); exact(f); });
  await t.test("body rejection preserves reason before method read", async () => { const f = fixture(), d = deferred(); f.state.input = d.promise; const p = f.invoke(); d.reject(f.fault); await assert.rejects(p, e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 4)); });
  await t.test("throwing body then getter refuses before method read", async () => { const f = fixture(); f.state.input = Object.defineProperty({}, "then", { get() { throw f.fault; } }); await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 4)); });
  await t.test("body thenable adopts input with original then receiver", async () => { const f = fixture(); const value = { then(this: unknown, yes: (x: unknown) => void) { assert.equal(this, value); yes(f.input); } }; f.state.input = value; assert.equal(await f.invoke(), f.result); exact(f); });
  for (const key of ["id", "revision"] as const) await t.test(`${key} promise passes raw without adoption`, async () => { const f = fixture(), d = deferred(); f.state[key] = d.promise; assert.equal(await f.invoke(), f.result); assert.equal(f.calls[0].args[key === "id" ? 1 : 2], d.promise); d.resolve(null); await d.promise; });
  await t.test("pending revoke result adopts exact resolved identity", async () => { const f = fixture(), d = deferred(), target = { public: "ADOPTED" }; f.state.result = d.promise; const p = f.invoke(); await Promise.resolve(); assert.equal(f.calls.length, 1); d.resolve(target); assert.equal(await p, target); });
  await t.test("revoke rejection preserves exact reason", async () => { const f = fixture(), d = deferred(); f.state.result = d.promise; const p = f.invoke(); await Promise.resolve(); d.reject(f.fault); await assert.rejects(p, e => e === f.fault); });
  await t.test("result thenable receives exact receiver and adopts identity", async () => { const f = fixture(), target = { public: "THENABLE" }; const value = { then(this: unknown, yes: (x: unknown) => void) { assert.equal(this, value); yes(target); } }; f.state.result = value; assert.equal(await f.invoke(), target); });
  await t.test("throwing result then getter preserves reason", async () => { const f = fixture(); f.state.result = Object.defineProperty({}, "then", { get() { throw f.fault; } }); await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.calls.length, 1); });
  await t.test("extra arguments and callback this remain unread", async () => { const f = fixture(); assert.equal(await f.callback.call(opaque("this"), f.registry, f.actor, f.request, f.params, opaque("extra")), f.result); exact(f); });
  await t.test("fresh calls reread current schema body method and revision", async () => { const f = fixture(); await f.invoke(); const actor = opaque("new actor"), request = opaque("new request"), schema = opaque("new schema"), id = opaque("new id"), revision = opaque("new revision"), registry = { revokeIdentity: f.method }, result = { public: "NEW" }; Object.assign(f.state, { input: { revision }, schema, result }); assert.equal(await f.invoke(registry, actor, request, { id }), result); exact(f, registry, actor, request, schema, id, revision); assert.equal(f.bodies.length, 2); });
  for (const stage of order) await t.test(`refused ${stage} does not poison fresh call`, async () => { const f = fixture(); f.state.faults[stage] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); delete f.state.faults[stage]; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("interleaved bodies retain original actors requests schemas ids revisions and receivers", async () => { const f = fixture(), one = deferred(), two = deferred(); f.state.input = one.promise; const p = f.invoke(); const actor = opaque("two actor"), request = opaque("two request"), schema = opaque("two schema"), id = opaque("two id"), revision = opaque("two revision"), registry = { revokeIdentity: f.method }; Object.assign(f.state, { input: two.promise, schema }); const q = f.invoke(registry, actor, request, { id }); two.resolve({ revision }); assert.equal(await q, f.result); exact(f, registry, actor, request, schema, id, revision); one.resolve(f.input); assert.equal(await p, f.result); assert.equal(f.calls[1].receiver, f.registry); assert.deepEqual(f.calls[1].args, [f.actor, f.id, f.revision]); assert.equal(f.bodies[0].args[0], f.request); assert.equal(f.bodies[0].args[1], f.schema); assert.equal(f.bodies[1].args[0], request); assert.equal(f.bodies[1].args[1], schema); });
  await t.test("interleaved pending results adopt their independent identities", async () => { const f = fixture(), one = deferred(), two = deferred(), a = { public: "ONE" }, b = { public: "TWO" }; f.state.result = one.promise; const p = f.invoke(); await Promise.resolve(); f.state.result = two.promise; const q = f.invoke(); await Promise.resolve(); assert.equal(f.calls.length, 2); two.resolve(b); assert.equal(await q, b); one.resolve(a); assert.equal(await p, a); });
});
