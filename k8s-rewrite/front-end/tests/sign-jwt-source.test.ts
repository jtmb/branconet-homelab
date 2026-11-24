import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

// PUBLIC SOURCE only: dependency names below refer to inert metadata models.
// No original module, runner, constructor, signing implementation or JWT executes.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);
assert.equal(process.version, "v24.18.0");
const raw = readFileSync(fileURLToPath(new URL("../src/lib/auth.ts", import.meta.url)), "utf8");
const source = raw.replaceAll("\r\n", "\n");
assert.ok(raw === source || raw === source.replaceAll("\n", "\r\n"));
assert.equal(createHash("sha256").update(source).digest("hex"), "932034e70f9d0447eb23c38ce91cb799413d289eb0a3bd25f3808c25865f2aff");
const ast = ts.createSourceFile("auth.ts", source, ts.ScriptTarget.Latest, true);
const declarations = ast.statements.filter((n: { name?: { text: string } }) => ts.isFunctionDeclaration(n) && n.name?.text === "signJWT");
assert.equal(declarations.length, 1);
const expected = 'export async function signJWT(\n  payload: { sub: string; username: string; sessionVersion?: number }\n): Promise<string> {\n  return signingKey.run(key => new SignJWT({ ...payload, sessionVersion: payload.sessionVersion ?? 0 })\n    .setProtectedHeader({ alg: "HS256" })\n    .setIssuedAt()\n    .setExpirationTime("7d")\n    .sign(key));\n}';
assert.equal(declarations[0].getText(ast), expected);
const javascript = ts.transpileModule(expected.replace(/^export /, ""), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
assert.ok(!/\b(?:import|require)\s*\(/.test(javascript));
type Stub = (...args: unknown[]) => unknown;
type Selected = (...args: unknown[]) => Promise<unknown>;
type Options = { owner: unknown; constructor: unknown; onOwnerRead?: Stub; onConstructorRead?: Stub };
const forbiddenCalls: string[] = [];
const forbidden: Stub = () => { forbiddenCalls.push("unexpected dependency"); throw new Error("unexpected dependency"); };
test.afterEach(() => { assert.deepEqual(forbiddenCalls, []); });
const key = Object.freeze({ publicCallbackKeyMetadata: true });
const result = Object.freeze({ publicResultMetadata: true });
const payload = () => ({ sub: "PUBLIC_SUBJECT", username: "PUBLIC_USER", sessionVersion: 3 });
const runner = { run: (cb: Stub) => cb(key) };
const methods = ["setProtectedHeader", "setIssuedAt", "setExpirationTime", "sign"] as const;
function load(options: Options): Selected {
  const context = vm.createContext({});
  Object.defineProperties(context, {
    signingKey: { get() { options.onOwnerRead?.(); return options.owner; } },
    SignJWT: { get() { options.onConstructorRead?.(); return options.constructor; } },
  });
  return vm.runInContext('"use strict"; (' + javascript + ')', context);
}
function model(output: unknown = result) {
  const projections: Record<PropertyKey, unknown>[] = [];
  const headers: unknown[] = []; const keys: unknown[] = []; const calls: string[] = [];
  const receivers = methods.map(() => ({} as Record<string, unknown>));
  for (const [i, name] of methods.entries()) Object.defineProperty(receivers[i], name, { configurable: true, get() {
    calls.push(name + ":get");
    return function (this: unknown, ...args: unknown[]) {
      calls.push(name + ":call"); assert.equal(this, receivers[i]);
      assert.equal(args.length, name === "setIssuedAt" ? 0 : 1);
      if (name === "setProtectedHeader") { headers.push(args[0]); assert.deepEqual(Object.keys(args[0] as object), ["alg"]); assert.equal((args[0] as Record<string, unknown>).alg, "HS256"); }
      if (name === "setExpirationTime") assert.equal(args[0], "7d");
      if (name === "sign") keys.push(args[0]);
      return i === 3 ? output : receivers[i + 1];
    };
  } });
  function Constructor(...args: unknown[]) {
    calls.push("construct"); assert.equal(new.target, Constructor); assert.equal(args.length, 1);
    projections.push(args[0] as Record<PropertyKey, unknown>); return receivers[0];
  }
  return { constructor: Constructor, projections, headers, keys, calls, receivers };
}
function deferred() {
  let resolve!: (value: unknown) => void; let reject!: (reason: unknown) => void;
  const promise = new Promise<unknown>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const same = (fault: unknown) => (actual: unknown) => actual === fault;
const typeError = (actual: unknown) => (actual as { name?: string })?.name === "TypeError";

test("exact one-argument declaration and inert chain metadata", async () => {
  const m = model(); const p = payload(); const selected = load({ owner: runner, constructor: m.constructor });
  assert.equal(selected.name, "signJWT"); assert.equal(selected.length, 1); assert.equal(declarations[0].parameters.length, 1);
  assert.equal(await selected(p), result); assert.notEqual(m.projections[0], p);
  assert.deepEqual(Object.keys(m.projections[0]), ["sub", "username", "sessionVersion"]);
  assert.equal(m.projections[0].sub, p.sub); assert.equal(m.projections[0].username, p.username); assert.equal(m.projections[0].sessionVersion, 3);
  assert.equal(m.keys[0], key);
});
test("source-derived receiver and evaluation order", async () => {
  const events: string[] = []; const m = model(); let reads = 0;
  const p = { get sub() { events.push("sub"); return "PUBLIC"; }, get username() { events.push("username"); return ""; }, get sessionVersion() { events.push("version" + ++reads); return reads; } };
  const owner = { get run() { events.push("run:get"); return function (this: unknown, ...args: unknown[]) { assert.equal(this, owner); assert.equal(args.length, 1); events.push("run:call"); const out = (args[0] as Stub)(key); events.push("run:return"); return out; }; } };
  const selected = load({ owner, constructor: m.constructor, onOwnerRead: () => { events.push("owner"); }, onConstructorRead: () => { events.push("constructor"); } });
  assert.equal(await selected(p), result); assert.deepEqual(events, ["owner", "run:get", "run:call", "constructor", "sub", "username", "version1", "version2", "run:return"]);
  assert.deepEqual(m.calls, ["construct", ...methods.flatMap(n => [n + ":get", n + ":call"])]); assert.equal(m.projections[0].sessionVersion, 2);
});
for (const [name, version] of [["missing", undefined], ["null", null], ["zero", 0], ["negative zero", -0], ["positive", 4], ["negative", -2], ["fraction", .5], ["NaN", NaN], ["infinity", Infinity], ["false", false], ["true", true], ["empty string", ""], ["string", "PUBLIC"], ["bigint", 2n], ["symbol", Symbol("PUBLIC")], ["object", key], ["array", []]] as const) test("nullish-only version projection metadata: " + name, async () => {
  const m = model(); const p = { ...payload(), sessionVersion: version }; assert.equal(await load({ owner: runner, constructor: m.constructor })(p), result);
  assert.ok(Object.is(m.projections[0].sessionVersion, version ?? 0)); assert.equal(p.sessionVersion, version);
});
test("absent version becomes own numeric zero", async () => {
  const m = model(); await load({ owner: runner, constructor: m.constructor })({ sub: "PUBLIC", username: "" });
  assert.equal(m.projections[0].sessionVersion, 0); assert.equal(Object.hasOwn(m.projections[0], "sessionVersion"), true);
});
test("spread copies enumerable string and symbol metadata without projection", async () => {
  const symbol = Symbol("PUBLIC"); const marker = {}; const p = { ...payload(), extra: marker, [symbol]: key }; const m = model();
  await load({ owner: runner, constructor: m.constructor })(p); assert.equal(m.projections[0].extra, marker); assert.equal(m.projections[0][symbol], key); assert.equal(Object.getOwnPropertyDescriptor(m.projections[0], symbol)?.enumerable, true);
});
test("inherited version read explicitly while inherited metadata is not spread", async () => {
  const p = Object.assign(Object.create({ sessionVersion: 8, inherited: key }), { sub: "PUBLIC" }); const m = model();
  await load({ owner: runner, constructor: m.constructor })(p); assert.deepEqual(Object.keys(m.projections[0]), ["sub", "sessionVersion"]); assert.equal(m.projections[0].sessionVersion, 8);
});
test("nonenumerable version read once explicitly and copied as data", async () => {
  let reads = 0; const p = Object.defineProperty({}, "sessionVersion", { get() { reads++; return 6; } }); const m = model();
  await load({ owner: runner, constructor: m.constructor })(p); assert.equal(reads, 1); assert.equal(m.projections[0].sessionVersion, 6); assert.equal(Object.getOwnPropertyDescriptor(m.projections[0], "sessionVersion")?.get, undefined);
});
test("own proto-named metadata is data and does not change projection prototype", async () => {
  const p = Object.defineProperty(payload(), "__proto__", { value: key, enumerable: true }); const m = model();
  await load({ owner: runner, constructor: m.constructor })(p); assert.equal(Object.hasOwn(m.projections[0], "__proto__"), true); assert.equal(m.projections[0].__proto__, key); assert.notEqual(Object.getPrototypeOf(m.projections[0]), key);
});
test("getters become writable configurable data and original input remains unchanged", async () => {
  const p = Object.freeze({ get sub() { return key; }, get sessionVersion() { return 2; } }); const m = model(); await load({ owner: runner, constructor: m.constructor })(p);
  const descriptor = Object.getOwnPropertyDescriptor(m.projections[0], "sub")!; assert.equal(descriptor.value, key); assert.equal(descriptor.get, undefined); assert.equal(descriptor.writable, true); assert.equal(descriptor.configurable, true); assert.equal(Object.isFrozen(p), true);
});
test("spread proxy keys descriptors and getters follow ordered own-key semantics", async () => {
  const events: string[] = []; const symbol = Symbol("PUBLIC"); const target = { a: 1, sessionVersion: 2, [symbol]: key };
  const p = new Proxy(target, { ownKeys(t) { events.push("keys"); return Reflect.ownKeys(t); }, getOwnPropertyDescriptor(t, n) { events.push("descriptor:" + String(n)); return Reflect.getOwnPropertyDescriptor(t, n); }, get(t, n, receiver) { events.push("get:" + String(n)); return Reflect.get(t, n, receiver); } });
  const m = model(); await load({ owner: runner, constructor: m.constructor })(p); assert.deepEqual(events, ["keys", "descriptor:a", "get:a", "descriptor:sessionVersion", "get:sessionVersion", "descriptor:Symbol(PUBLIC)", "get:Symbol(PUBLIC)", "get:sessionVersion"]); assert.equal(m.projections[0][symbol], key);
});
for (const field of ["sub", "username", "extra", "sessionVersion"] as const) test("enumerable payload getter fault rejects before constructor call: " + field, async () => {
  const m = model(); const p = Object.defineProperty(payload(), field, { enumerable: true, get() { throw key; } }); await assert.rejects(load({ owner: runner, constructor: m.constructor })(p), same(key)); assert.deepEqual(m.calls, []);
});
test("explicit second version getter fault rejects after completed spread", async () => {
  let reads = 0; const p = { get sessionVersion() { if (++reads === 2) throw key; return 1; } }; const m = model(); await assert.rejects(load({ owner: runner, constructor: m.constructor })(p), same(key)); assert.equal(reads, 2); assert.deepEqual(m.calls, []);
});
for (const trap of ["ownKeys", "getOwnPropertyDescriptor", "get"] as const) test("payload proxy fault retains exact rejection: " + trap, async () => {
  const p = new Proxy(payload(), { [trap]() { throw key; } }); const m = model(); let bindings = 0;
  await assert.rejects(load({ owner: runner, constructor: m.constructor, onConstructorRead: () => { bindings++; } })(p), same(key)); assert.equal(bindings, 1); assert.deepEqual(m.calls, []);
});
for (const p of [null, undefined]) test("nullish payload spread completes but explicit version access refuses: " + p, async () => { const m = model(); let bindings = 0; await assert.rejects(load({ owner: runner, constructor: m.constructor, onConstructorRead: () => { bindings++; } })(p), typeError); assert.equal(bindings, 1); assert.deepEqual(m.calls, []); });
for (const [name, p] of [["false", false], ["number", 7], ["bigint", 7n], ["symbol", Symbol("PUBLIC")], ["string", "PUBLIC"]] as const) test("primitive metadata characterizes spread without validity claim: " + name, async () => {
  const m = model(); await load({ owner: runner, constructor: m.constructor })(p); assert.equal(m.projections[0].sessionVersion, 0); assert.deepEqual(Object.keys(m.projections[0]), typeof p === "string" ? ["0", "1", "2", "3", "4", "5", "sessionVersion"] : ["sessionVersion"]);
});
for (const [name, owner] of [["null", null], ["undefined", undefined], ["absent", {}], ["noncallable", { run: 2 }]] as const) test("runner metadata refuses before callback dependencies: " + name, async () => {
  const m = model(); await assert.rejects(load({ owner, constructor: m.constructor, onConstructorRead: forbidden })(payload()), typeError); assert.deepEqual(m.calls, []);
});
for (const kind of ["getter", "call"] as const) test("runner fault rejects exact identity: " + kind, async () => {
  const owner = kind === "getter" ? { get run() { throw key; } } : { run() { throw key; } }; const m = model(); await assert.rejects(load({ owner, constructor: m.constructor, onConstructorRead: forbidden })(payload()), same(key)); assert.deepEqual(m.calls, []);
});
test("runner rejection propagates without callback work", async () => { const m = model(); await assert.rejects(load({ owner: { run: () => Promise.reject(key) }, constructor: m.constructor, onConstructorRead: forbidden })(payload()), same(key)); });
test("runner controls callback admission and return identity", async () => { const m = model(); assert.equal(await load({ owner: { run: () => result }, constructor: m.constructor, onConstructorRead: forbidden })(payload()), result); assert.deepEqual(m.calls, []); });
test("runner receives one non-async arrow that cannot be constructed", async () => {
  const m = model(); const owner = { run(cb: Stub) { assert.equal(cb.length, 1); assert.equal(Object.hasOwn(cb, "prototype"), false); assert.throws(() => Reflect.construct(cb, []), typeError); const out = cb(key); assert.equal(out, result); return out; } };
  assert.equal(await load({ owner, constructor: m.constructor })(payload()), result);
});
for (const [name, constructor] of [["null", null], ["undefined", undefined], ["object", {}], ["arrow", () => result]] as const) test("nonconstructible binding evaluates payload before refusal: " + name, async () => {
  let reads = 0; const p = { get sessionVersion() { reads++; return 2; } }; await assert.rejects(load({ owner: runner, constructor })(p), typeError); assert.equal(reads, 2);
});
test("constructor fault rejects exactly after payload evaluation", async () => {
  let reads = 0; function Constructor() { throw key; } await assert.rejects(load({ owner: runner, constructor: Constructor })({ get sessionVersion() { reads++; return 2; } }), same(key)); assert.equal(reads, 2);
});
for (const [i, stage] of methods.entries()) {
  for (const kind of ["getter", "call", "noncallable"] as const) test("chain boundary " + stage + " " + kind + " stops later stages", async () => {
    const m = model(); Object.defineProperty(m.receivers[i], stage, { get() { m.calls.push("fault:get"); if (kind === "getter") throw key; return kind === "noncallable" ? 3 : function () { m.calls.push("fault:call"); throw key; }; } });
    await assert.rejects(load({ owner: runner, constructor: m.constructor })(payload()), kind === "noncallable" ? typeError : same(key));
    assert.deepEqual(m.calls, ["construct", ...methods.slice(0, i).flatMap(n => [n + ":get", n + ":call"]), "fault:get", ...(kind === "call" ? ["fault:call"] : [])]);
  });
  if (i < 3) test("null return from " + stage + " refuses next receiver", async () => {
    const m = model(); Object.defineProperty(m.receivers[i], stage, { value: () => null }); await assert.rejects(load({ owner: runner, constructor: m.constructor })(payload()), typeError); assert.equal(m.keys.length, 0);
  });
  test("intermediate receiver " + i + " is used synchronously without then adoption", async () => {
    const m = model(); Object.defineProperty(m.receivers[i], "then", { get: forbidden }); assert.equal(await load({ owner: runner, constructor: m.constructor })(payload()), result);
  });
}
test("sign return passes directly through callback before outer adoption", async () => {
  const gate = deferred(); let reads = 0; const thenable = { get then() { reads++; return (yes: (value: unknown) => void) => { gate.promise.then(yes); }; } }; const m = model(thenable);
  const owner = { run(cb: Stub) { const out = cb(key); assert.equal(out, thenable); assert.equal(reads, 0); return out; } };
  const pending = load({ owner, constructor: m.constructor })(payload()); assert.equal(reads, 1); gate.resolve(result); assert.equal(await pending, result);
});
test("sign rejection is adopted by outer async return", async () => { const m = model({ then(_yes: unknown, no: (reason: unknown) => void) { no(key); } }); await assert.rejects(load({ owner: runner, constructor: m.constructor })(payload()), same(key)); });
test("runner can replace ignored sign metadata without adoption", async () => { const ignored = Object.defineProperty({}, "then", { get: forbidden }); const m = model(ignored); const owner = { run(cb: Stub) { assert.equal(cb(key), ignored); return result; } }; assert.equal(await load({ owner, constructor: m.constructor })(payload()), result); });
test("runner may catch a synchronous callback fault", async () => { function Constructor() { throw key; } const owner = { run(cb: Stub) { try { return cb(key); } catch (error) { assert.equal(error, key); return result; } } }; assert.equal(await load({ owner, constructor: Constructor })(payload()), result); });
test("held callback reads payload when invoked rather than at admission", async () => {
  const m = model(); let callback!: Stub; const gate = deferred(); const p = payload(); let reads = 0;
  const pending = load({ owner: { run(cb: Stub) { callback = cb; return gate.promise; } }, constructor: m.constructor, onConstructorRead: () => { reads++; } })(p);
  assert.equal(reads, 0); p.sessionVersion = 8; gate.resolve(callback(key)); assert.equal(await pending, result); assert.equal(m.projections[0].sessionVersion, 8);
});
test("multiple callback invocations make independent fresh projection and header", async () => {
  const m = model(); const keys = [key, Object.freeze({ publicAlternateKeyMetadata: true })]; const owner = { run(cb: Stub) { cb(keys[0]); return cb(keys[1]); } };
  await load({ owner, constructor: m.constructor })(payload()); assert.equal(m.projections.length, 2); assert.notEqual(m.projections[0], m.projections[1]); assert.notEqual(m.headers[0], m.headers[1]); assert.deepEqual(m.keys, keys);
});
test("fresh sequential calls observe changed payload without cache", async () => { const m = model(); const p = payload(); const selected = load({ owner: runner, constructor: m.constructor }); await selected(p); p.sessionVersion = 9; await selected(p); assert.equal(m.projections[0].sessionVersion, 3); assert.equal(m.projections[1].sessionVersion, 9); assert.notEqual(m.projections[0], m.projections[1]); });
test("concurrent retained callbacks keep independent payload and key metadata", async () => {
  const callbacks: Stub[] = []; const gates = [deferred(), deferred()]; const m = model(); const selected = load({ owner: { run(cb: Stub) { callbacks.push(cb); return gates[callbacks.length - 1].promise; } }, constructor: m.constructor });
  const a = selected({ sub: "PUBLIC_A", sessionVersion: 1 }); const b = selected({ sub: "PUBLIC_B", sessionVersion: 2 }); const secondKey = {};
  gates[1].resolve(callbacks[1](secondKey)); assert.equal(await b, result); gates[0].resolve(callbacks[0](key)); assert.equal(await a, result);
  assert.equal(m.projections[0].sub, "PUBLIC_B"); assert.equal(m.projections[1].sub, "PUBLIC_A"); assert.deepEqual(m.keys, [secondKey, key]);
});
