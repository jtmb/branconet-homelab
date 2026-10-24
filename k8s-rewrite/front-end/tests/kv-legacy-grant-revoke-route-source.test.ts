import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC source controls. Actual imported implementations never execute.
type Model = Record<string, any>;
const path = "src/app/api/kv/legacy/grants/[id]/route.ts";
const compiled = ts.transpileModule(readFileSync(path, "utf8"), {
  fileName: path, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
}).outputText;
const isError = (e: unknown) => Object.prototype.toString.call(e) === "[object Error]";
function opaque(label: string) { return new Proxy({}, { get() { throw Error(`PUBLIC unexpected ${label} read`); }, ownKeys() { throw Error(`PUBLIC unexpected ${label} enumeration`); } }); }
function deferred() {
  let resolve!: (value: any) => void, reject!: (reason: any) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function fixture() {
  const actor = opaque("actor"), request = opaque("request"), registry = opaque("registry"), schema = opaque("schema"), id = opaque("id"), revision = opaque("revision"), impact = opaque("impact");
  const result = { public: "RESULT" }, marker = { public: "WRAPPER" }, fault = Error("PUBLIC refusal");
  const wrappers: any[][] = [], bodies: Model[] = [], constructions: Model[] = [], calls: Model[] = [], trace: string[] = [];
  const state: Model & { constructor: any } = { id, revision, impact, result, faults: {}, hooks: {} };
  function step(name: string) { trace.push(name); state.hooks[name]?.(); if (state.faults[name]) throw state.faults[name]; }
  const params = Object.defineProperty({}, "id", { get() { step("id"); return state.id; } });
  const input = Object.defineProperties({}, {
    revision: { get() { step("revision"); return state.revision; } },
    legacyImpact: { get() { step("impact"); return state.impact; } },
    unused: { enumerable: true, get() { throw fault; } },
    [Symbol("PUBLIC-unused")]: { enumerable: true, get() { throw fault; } }
  });
  const method = function(this: unknown, ...args: unknown[]) { calls.push({ receiver: this, args }); step("commit"); return state.result; };
  const constructor = function(this: unknown, ...args: unknown[]) { constructions.push({ receiver: this, args, target: new.target }); step("construct"); return state.constructed; };
  Object.defineProperty(constructor.prototype, "commit", { configurable: true, get() { step("commit-get"); return state.method; } });
  const instance = Object.create(constructor.prototype);
  const body = function(this: unknown, ...args: unknown[]) { bodies.push({ receiver: this, args }); step("body"); return state.input; };
  Object.assign(state, { input, body, schema, constructor, constructed: instance, method });
  const imports = new Proxy({ kvHuman(...args: any[]) { wrappers.push(args); return marker; }, get kvAdminMetadataBody() { step("body-get"); return state.body; } }, {
    get(target, key, receiver) { assert.ok(key === "kvHuman" || key === "kvAdminMetadataBody"); return Reflect.get(target, key, receiver); }
  });
  const schemas = new Proxy(Object.defineProperty({}, "legacyRevoke", { get() { step("schema-get"); return state.schema; } }), {
    get(target, key, receiver) { assert.equal(key, "legacyRevoke"); return Reflect.get(target, key, receiver); }
  });
  const legacy = new Proxy(Object.defineProperty({}, "KvLegacyAccess", { get() { step("constructor-get"); return state.constructor; } }), {
    get(target, key, receiver) { assert.equal(key, "KvLegacyAccess"); return Reflect.get(target, key, receiver); }
  });
  const sandboxModule = { exports: {} as Model };
  runInNewContext(compiled, { module: sandboxModule, exports: sandboxModule.exports, require: (name: string) => {
    if (name === "@/lib/kv-http") return imports;
    if (name === "@/lib/kv-schemas") return schemas;
    assert.equal(name, "@/lib/kv-legacy-access"); return legacy;
  } }, { filename: path, timeout: 5000 });
  assert.equal(wrappers.length, 1); assert.deepEqual(trace, [] as string[]);
  const callback = wrappers[0][0];
  return { actor, request, registry, schema, id, revision, impact, result, marker, fault, wrappers, bodies, constructions, calls, trace, state, params, input, body, method, constructor, instance, callback, exports: sandboxModule.exports,
    invoke: (...args: unknown[]) => callback(args.length ? args[0] : registry, args.length > 1 ? args[1] : actor, args.length > 2 ? args[2] : request, args.length > 3 ? args[3] : params) as Promise<unknown> };
}
type Fixture = ReturnType<typeof fixture>;
const order = ["id", "body-get", "schema-get", "body", "revision", "impact", "constructor-get", "construct", "commit-get", "commit"];
function exact(f: Fixture, ...overrides: unknown[]) {
  const [registry, actor, request, schema, id, revision, impact, instance] = [f.registry, f.actor, f.request, f.schema, f.id, f.revision, f.impact, f.instance].map((value, i) => i < overrides.length ? overrides[i] : value);
  const b = f.bodies.at(-1)!, c = f.constructions.at(-1)!, m = f.calls.at(-1)!;
  assert.equal(b.receiver, undefined); assert.equal(b.args.length, 4);
  [registry, actor, request, schema].forEach((value, i) => assert.equal(b.args[i], value));
  assert.equal(c.args.length, 1); assert.equal(c.args[0], registry); assert.equal(c.target, f.constructor);
  assert.equal(m.receiver, instance); assert.equal(m.args.length, 3); assert.equal(m.args[0], actor); assert.equal(m.args[2], impact);
  const change = m.args[1]; assert.deepEqual(Reflect.ownKeys(change), ["kind", "grantId", "revision"]);
  assert.equal(change.kind, "revoke"); assert.equal(change.grantId, id); assert.equal(change.revision, revision);
  for (const key of ["kind", "grantId", "revision"]) { const d = Object.getOwnPropertyDescriptor(change, key)!; assert.ok(d.writable && d.enumerable && d.configurable); }
}

test("human legacy-grant-revoke DELETE exact asynchronous SOURCE delegation", async t => {
  await t.test("exact nodejs default-status DELETE wrapper and absent dynamic export", () => {
    const f = fixture(); assert.deepEqual(Object.keys(f.exports).sort(), ["DELETE", "runtime"]); assert.equal(f.exports.runtime, "nodejs");
    assert.equal(Object.hasOwn(f.exports, "dynamic"), false); assert.equal(f.wrappers[0].length, 1); assert.equal(typeof f.callback, "function"); assert.equal(f.exports.DELETE, f.marker);
  });
  await t.test("entry id body schema await revision impact constructor commit exact order", async () => {
    const f = fixture(), p = f.invoke(); assert.deepEqual(f.trace, order.slice(0, 4)); assert.equal(f.constructions.length, 0);
    assert.equal(await p, f.result); assert.deepEqual(f.trace, order); exact(f);
  });
  for (const [i, stage] of order.entries()) await t.test(`${stage} refusal preserves reason and stops later work`, async () => {
    const f = fixture(); f.state.faults[stage] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault);
    assert.deepEqual(f.trace, order.slice(0, i + 1)); assert.equal(f.calls.length, stage === "commit" ? 1 : 0);
  });
  for (const value of [undefined, null, false, 0, "", 7, "PUBLIC", Symbol("PUBLIC"), 3n]) {
    await t.test(`registry ${String(value)} delegated unread`, async () => { const f = fixture(); assert.equal(await f.invoke(value), f.result); exact(f, value); });
    await t.test(`actor ${String(value)} delegated unread`, async () => { const f = fixture(); assert.equal(await f.invoke(f.registry, value), f.result); exact(f, f.registry, value); });
    await t.test(`request ${String(value)} delegated unread`, async () => { const f = fixture(); assert.equal(await f.invoke(f.registry, f.actor, value), f.result); exact(f, f.registry, f.actor, value); });
    await t.test(`schema ${String(value)} delegated unchanged`, async () => { const f = fixture(); f.state.schema = value; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, value); });
    await t.test(`id ${String(value)} captured unchanged`, async () => { const f = fixture(); f.state.id = value; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, value); });
    await t.test(`revision ${String(value)} captured unchanged`, async () => { const f = fixture(); f.state.revision = value; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, f.id, value); });
    await t.test(`impact ${String(value)} captured unchanged`, async () => { const f = fixture(); f.state.impact = value; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, f.id, f.revision, value); });
    await t.test(`result ${String(value)} asynchronously adopted`, async () => { const f = fixture(); f.state.result = value; assert.equal(await f.invoke(), value); exact(f); });
  }
  for (const value of [undefined, null]) {
    await t.test(`nullish params ${String(value)} refuses before imports`, async () => { const f = fixture(); await assert.rejects(f.invoke(f.registry, f.actor, f.request, value), isError); assert.deepEqual(f.trace, [] as string[]); });
    await t.test(`nullish input ${String(value)} refuses before constructor`, async () => { const f = fixture(); f.state.input = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 4)); });
  }
  await t.test("missing fourth argument refuses before body lookup", async () => { const f = fixture(); await assert.rejects(f.callback(), isError); assert.deepEqual(f.trace, [] as string[]); });
  for (const value of [undefined, null, false, 0, "", {}, Symbol("PUBLIC")]) {
    await t.test(`noncallable body ${String(value)} reads schema then refuses`, async () => { const f = fixture(); f.state.body = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 3)); });
    await t.test(`nonconstructor ${String(value)} refuses after captured input`, async () => { const f = fixture(); f.state.constructor = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 7)); });
    await t.test(`noncallable commit ${String(value)} refuses after getter`, async () => { const f = fixture(); f.state.method = value; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 9)); });
  }
  await t.test("arrow constructor refuses without executing arrow body", async () => { const f = fixture(); f.state.constructor = () => { throw f.fault; }; await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 7)); });
  for (const [earlier, later] of [["id", "body-get"], ["schema-get", "body"], ["revision", "impact"], ["impact", "constructor-get"], ["constructor-get", "construct"], ["construct", "commit-get"]]) await t.test(`${earlier} refusal wins over ${later}`, async () => { const f = fixture(); f.state.faults[earlier] = f.fault; f.state.faults[later] = Error("PUBLIC LATER"); await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.trace.at(-1), earlier); });
  await t.test("schema getter refusal wins over noncallable captured body", async () => { const f = fixture(); f.state.body = null; f.state.faults["schema-get"] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 3)); });
  for (const stage of ["schema-get", "body"]) await t.test(`${stage} cannot replace captured body`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.body = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("body getter may replace schema before lookup", async () => { const f = fixture(), schema = opaque("replacement schema"); f.state.hooks["body-get"] = () => { f.state.schema = schema; }; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, schema); });
  for (const stage of order.slice(1)) await t.test(`${stage} cannot replace entry captured id`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.id = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("revision getter may replace impact before capture", async () => { const f = fixture(), impact = opaque("replacement impact"); f.state.hooks.revision = () => { f.state.impact = impact; }; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, f.id, f.revision, impact); });
  for (const stage of ["impact", "constructor-get", "construct", "commit-get", "commit"]) await t.test(`${stage} cannot replace captured revision`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.revision = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  for (const stage of ["constructor-get", "construct", "commit-get", "commit"]) await t.test(`${stage} cannot replace captured impact`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.impact = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  for (const stage of ["construct", "commit-get", "commit"]) await t.test(`${stage} cannot replace captured constructor`, async () => { const f = fixture(); f.state.hooks[stage] = () => { f.state.constructor = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("constructor getter can replace instance method before lookup", async () => { const f = fixture(); f.state.hooks["constructor-get"] = () => { f.state.method = function(this: unknown, ...args: unknown[]) { f.calls.push({ receiver: this, args }); return f.result; }; }; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("commit getter can replace future method without changing captured call", async () => { const f = fixture(); f.state.hooks.commit = () => { f.state.method = null; }; assert.equal(await f.invoke(), f.result); exact(f); });
  for (const value of [undefined, null, false, 0, "PUBLIC", Symbol("PUBLIC"), 3n]) await t.test(`constructor primitive return ${String(value)} keeps constructed receiver`, async () => { const f = fixture(); f.state.constructed = value; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, f.id, f.revision, f.impact, f.constructions[0].receiver); });
  await t.test("constructor object return replaces receiver exactly", async () => { const f = fixture(); const returned = { commit: f.method }; f.state.constructed = returned; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, f.id, f.revision, f.impact, returned); assert.notEqual(returned, f.constructions[0].receiver); });
  await t.test("constructor callable return replaces receiver without calling function", async () => { const f = fixture(); const returned = Object.assign(() => { throw f.fault; }, { commit: f.method }); f.state.constructed = returned; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, f.id, f.revision, f.impact, returned); });
  await t.test("constructed inherited commit getter has exact returned receiver", async () => { const f = fixture(); const returned = Object.create(Object.defineProperty({}, "commit", { get() { assert.equal(this, returned); return f.method; } })); f.state.constructed = returned; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, f.id, f.revision, f.impact, returned); });
  await t.test("constructed proxy reads only commit without enumeration or then", async () => { const f = fixture(); const returned = new Proxy({}, { get(_t, key) { assert.equal(key, "commit"); return f.method; }, ownKeys() { throw f.fault; }, getOwnPropertyDescriptor() { throw f.fault; } }); f.state.constructed = returned; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, f.id, f.revision, f.impact, returned); });
  await t.test("missing constructed commit refuses without fallback", async () => { const f = fixture(); f.state.constructed = Object.create(null); await assert.rejects(f.invoke(), isError); assert.deepEqual(f.trace, order.slice(0, 8)); });
  await t.test("constructor proxy observes exact construct arguments and newTarget", async () => { const f = fixture(); const proxy: any = new Proxy(f.constructor, { construct(target, args, newTarget) { assert.equal(target, f.constructor); assert.equal(args.length, 1); assert.equal(args[0], f.registry); assert.equal(newTarget, proxy); return f.instance; } }); f.state.constructor = proxy; assert.equal(await f.invoke(), f.result); assert.equal(f.calls[0].receiver, f.instance); assert.equal(f.constructions.length, 0); });
  for (const params of [false, 0, "PUBLIC", Symbol("PUBLIC"), 3n, {}, Object.create(null)]) await t.test(`missing id on ${Object.prototype.toString.call(params)} passes undefined`, async () => { const f = fixture(); assert.equal(await f.invoke(f.registry, f.actor, f.request, params), f.result); exact(f, f.registry, f.actor, f.request, f.schema, undefined); assert.deepEqual(f.trace, order.slice(1)); });
  await t.test("inherited id getter receives exact params", async () => { const f = fixture(); const params = Object.create(Object.defineProperty({}, "id", { get() { assert.equal(this, params); return f.id; } })); assert.equal(await f.invoke(f.registry, f.actor, f.request, params), f.result); exact(f); });
  await t.test("params proxy reads only id without enumeration", async () => { const f = fixture(); const params = new Proxy({}, { get(_t, key) { assert.equal(key, "id"); return f.id; }, ownKeys() { throw f.fault; } }); assert.equal(await f.invoke(f.registry, f.actor, f.request, params), f.result); exact(f); });
  await t.test("inherited input getters retain input receiver and order", async () => { const f = fixture(), seen: string[] = []; const input = Object.create(Object.defineProperties({}, { revision: { get() { assert.equal(this, input); seen.push("revision"); return f.revision; } }, legacyImpact: { get() { assert.equal(this, input); seen.push("impact"); return f.impact; } } })); f.state.input = input; assert.equal(await f.invoke(), f.result); exact(f); assert.deepEqual(seen, ["revision", "impact"]); });
  await t.test("nonenumerable input fields selected without copying others", async () => { const f = fixture(); f.state.input = Object.defineProperties({}, { revision: { value: f.revision }, legacyImpact: { value: f.impact }, unused: { get() { throw f.fault; }, enumerable: true } }); assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("input proxy reads then revision impact only without descriptors", async () => { const f = fixture(), seen: PropertyKey[] = []; f.state.input = new Proxy({}, { get(_t, key) { seen.push(key); if (key === "then") return undefined; if (key === "revision") return f.revision; if (key === "legacyImpact") return f.impact; throw f.fault; }, ownKeys() { throw f.fault; }, getOwnPropertyDescriptor() { throw f.fault; } }); assert.equal(await f.invoke(), f.result); exact(f); assert.deepEqual(seen, ["then", "revision", "legacyImpact"]); });
  for (const value of [false, 0, 7, 3n, Symbol("PUBLIC"), "", "PUBLIC", {}, Object.create(null)]) await t.test(`input ${Object.prototype.toString.call(value)} passes both absent fields undefined`, async () => { const f = fixture(); f.state.input = value; assert.equal(await f.invoke(), f.result); exact(f, f.registry, f.actor, f.request, f.schema, f.id, undefined, undefined); });
  await t.test("pending body blocks revision impact constructor and commit", async () => { const f = fixture(), d = deferred(); f.state.input = d.promise; const p = f.invoke(); assert.deepEqual(f.trace, order.slice(0, 4)); d.resolve(f.input); assert.equal(await p, f.result); exact(f); });
  await t.test("body rejection preserves exact reason before constructor", async () => { const f = fixture(), d = deferred(); f.state.input = d.promise; const p = f.invoke(); d.reject(f.fault); await assert.rejects(p, e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 4)); });
  await t.test("throwing body then getter refuses before input field access", async () => { const f = fixture(); f.state.input = Object.defineProperty({}, "then", { get() { throw f.fault; } }); await assert.rejects(f.invoke(), e => e === f.fault); assert.deepEqual(f.trace, order.slice(0, 4)); });
  await t.test("body thenable adopts input with exact then receiver", async () => { const f = fixture(); const value = { then(this: unknown, yes: (x: unknown) => void) { assert.equal(this, value); yes(f.input); } }; f.state.input = value; assert.equal(await f.invoke(), f.result); exact(f); });
  for (const field of ["id", "revision", "impact"] as const) await t.test(`${field} promise passes raw without adoption`, async () => { const f = fixture(), d = deferred(); f.state[field] = d.promise; assert.equal(await f.invoke(), f.result); const change = f.calls[0].args[1]; assert.equal(field === "impact" ? f.calls[0].args[2] : change[field === "id" ? "grantId" : "revision"], d.promise); d.resolve(null); await d.promise; });
  await t.test("pending commit result adopts exact resolved identity", async () => { const f = fixture(), d = deferred(), target = { public: "ADOPTED" }; f.state.result = d.promise; const p = f.invoke(); await Promise.resolve(); assert.equal(f.calls.length, 1); d.resolve(target); assert.equal(await p, target); });
  await t.test("commit result rejection preserves exact reason", async () => { const f = fixture(), d = deferred(); f.state.result = d.promise; const p = f.invoke(); await Promise.resolve(); d.reject(f.fault); await assert.rejects(p, e => e === f.fault); });
  await t.test("commit result thenable has exact receiver and adopted identity", async () => { const f = fixture(), target = { public: "THENABLE" }; const value = { then(this: unknown, yes: (x: unknown) => void) { assert.equal(this, value); yes(target); } }; f.state.result = value; assert.equal(await f.invoke(), target); });
  await t.test("throwing commit result then getter preserves exact reason", async () => { const f = fixture(); f.state.result = Object.defineProperty({}, "then", { get() { throw f.fault; } }); await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.calls.length, 1); });
  await t.test("extra arguments and callback this remain unread", async () => { const f = fixture(); assert.equal(await f.callback.call(opaque("this"), f.registry, f.actor, f.request, f.params, opaque("extra")), f.result); exact(f); });
  await t.test("fresh calls use fresh change objects and current captured inputs", async () => { const f = fixture(); await f.invoke(); const first = f.calls[0].args[1], revision = opaque("new revision"), impact = opaque("new impact"), id = opaque("new id"), actor = opaque("new actor"), registry = opaque("new registry"), request = opaque("new request"), schema = opaque("new schema"); Object.assign(f.state, { revision, impact, schema }); assert.equal(await f.invoke(registry, actor, request, { id }), f.result); exact(f, registry, actor, request, schema, id, revision, impact); assert.notEqual(f.calls[1].args[1], first); });
  await t.test("commit mutation of change cannot poison a later call", async () => { const f = fixture(); f.state.hooks.commit = () => { f.calls.at(-1)!.args[1].grantId = null; }; await f.invoke(); delete f.state.hooks.commit; assert.equal(await f.invoke(), f.result); exact(f); assert.notEqual(f.calls[0].args[1], f.calls[1].args[1]); });
  for (const stage of order) await t.test(`refused ${stage} does not poison fresh call`, async () => { const f = fixture(); f.state.faults[stage] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault); delete f.state.faults[stage]; assert.equal(await f.invoke(), f.result); exact(f); });
  await t.test("interleaved bodies retain original registry actor request schema id and fields", async () => { const f = fixture(), one = deferred(), two = deferred(); f.state.input = one.promise; const p = f.invoke(); const registry = opaque("two registry"), actor = opaque("two actor"), request = opaque("two request"), schema = opaque("two schema"), id = opaque("two id"), revision = opaque("two revision"), impact = opaque("two impact"); Object.assign(f.state, { input: two.promise, schema }); const q = f.invoke(registry, actor, request, { id }); two.resolve({ revision, legacyImpact: impact }); assert.equal(await q, f.result); exact(f, registry, actor, request, schema, id, revision, impact); one.resolve(f.input); assert.equal(await p, f.result); const call = f.calls[1], construct = f.constructions[1]; assert.equal(construct.args[0], f.registry); assert.equal(call.args[0], f.actor); assert.equal(call.args[1].grantId, f.id); assert.equal(call.args[1].revision, f.revision); assert.equal(call.args[2], f.impact); assert.equal(f.bodies[0].args[3], f.schema); });
  await t.test("interleaved pending results adopt independent identities", async () => { const f = fixture(), one = deferred(), two = deferred(), a = { public: "ONE" }, b = { public: "TWO" }; f.state.result = one.promise; const p = f.invoke(); await Promise.resolve(); f.state.result = two.promise; const q = f.invoke(); await Promise.resolve(); two.resolve(b); assert.equal(await q, b); one.resolve(a); assert.equal(await p, a); assert.notEqual(f.calls[0].args[1], f.calls[1].args[1]); });
  await t.test("reentrant entry from id getter keeps separate captured ids and changes", async () => { const f = fixture(); let nested!: Promise<unknown>; const id = opaque("nested id"); f.state.hooks.id = () => { delete f.state.hooks.id; nested = f.invoke(f.registry, f.actor, f.request, { id }); }; const p = f.invoke(); assert.equal(await nested, f.result); assert.equal(await p, f.result); assert.equal(f.calls[0].args[1].grantId, id); assert.equal(f.calls[1].args[1].grantId, f.id); assert.notEqual(f.calls[0].args[1], f.calls[1].args[1]); });
});
