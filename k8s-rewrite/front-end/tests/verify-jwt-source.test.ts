import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

// PUBLIC SOURCE controls only. All dependency calls below are injected metadata
// models. No original module, initializer, key runner or JWT verifier is imported.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);
assert.equal(process.version, "v24.18.0");
const raw = readFileSync(fileURLToPath(new URL("../src/lib/auth.ts", import.meta.url)), "utf8");
const source = raw.replaceAll("\r\n", "\n");
assert.ok(raw === source || raw === source.replaceAll("\n", "\r\n"));
assert.equal(createHash("sha256").update(source).digest("hex"), "932034e70f9d0447eb23c38ce91cb799413d289eb0a3bd25f3808c25865f2aff");
const ast = ts.createSourceFile("auth.ts", source, ts.ScriptTarget.Latest, true);
const declarations = ast.statements.filter((n: { name?: { text: string } }) => ts.isFunctionDeclaration(n) && n.name?.text === "verifyJWT");
assert.equal(declarations.length, 1);
const declaration = declarations[0].getText(ast);
const expected = 'export async function verifyJWT(\n  token: string\n): Promise<{ sub: string; username: string; sessionVersion: number } | null> {\n  try {\n    const { payload } = await signingKey.run(key => Promise.resolve(verifyHS256Profile(token, key)));\n    const sessionVersion = payload.sessionVersion ?? 0;\n    if (typeof payload.sub !== "string" || !payload.sub || typeof payload.username !== "string" ||\n      typeof sessionVersion !== "number" || !Number.isSafeInteger(sessionVersion) || sessionVersion < 0) return null;\n    return { sub: payload.sub, username: payload.username, sessionVersion };\n  } catch {\n    return null;\n  }\n}';
assert.equal(declaration, expected);
const javascript = ts.transpileModule(declaration.replace(/^export /, ""), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
assert.ok(!/\b(?:import|require)\s*\(/.test(javascript));

type Stub = (...args: unknown[]) => unknown;
type Selected = (...args: unknown[]) => Promise<unknown>;
type Options = { keyOwner?: unknown; verify?: unknown; promiseModel?: unknown; numberModel?: unknown; onKeyRead?: Stub; onVerifyRead?: Stub; onPromiseRead?: Stub; onNumberRead?: Stub };
const forbiddenCalls: string[] = [];
const forbidden: Stub = () => { forbiddenCalls.push("unexpected dependency"); throw new Error("unexpected dependency"); };
test.afterEach(() => { assert.deepEqual(forbiddenCalls, []); });
const label = "PUBLIC_INPUT_LABEL";
const key = Object.freeze({ publicKeyMetadata: true });
const valid = () => ({ sub: "PUBLIC_SUBJECT", username: "PUBLIC_USER", sessionVersion: 3 });
function load(options: Options): Selected {
  const context = vm.createContext({});
  const intrinsicPromise = vm.runInContext("Promise", context);
  const intrinsicNumber = vm.runInContext("Number", context);
  Object.defineProperties(context, {
    signingKey: { get() { options.onKeyRead?.(); return Object.hasOwn(options, "keyOwner") ? options.keyOwner : forbidden; } },
    verifyHS256Profile: { get() { options.onVerifyRead?.(); return Object.hasOwn(options, "verify") ? options.verify : forbidden; } },
    Promise: { get() { options.onPromiseRead?.(); return Object.hasOwn(options, "promiseModel") ? options.promiseModel : intrinsicPromise; } },
    Number: { get() { options.onNumberRead?.(); return Object.hasOwn(options, "numberModel") ? options.numberModel : intrinsicNumber; } },
  });
  return vm.runInContext('"use strict"; (' + javascript + ')', context);
}
const runner = { run: (callback: (value: unknown) => unknown) => callback(key) };
const successful = (payload: unknown, options: Options = {}) => load({ keyOwner: runner, verify: () => ({ payload }), ...options });
function projected(value: unknown, sub: unknown, username: unknown, sessionVersion: unknown) {
  assert.ok(value && typeof value === "object");
  assert.deepEqual(Object.keys(value), ["sub", "username", "sessionVersion"]);
  const result = value as Record<string, unknown>;
  assert.equal(result.sub, sub); assert.equal(result.username, username); assert.equal(result.sessionVersion, sessionVersion);
}
function deferred() {
  let resolve!: (value: unknown) => void; let reject!: (reason: unknown) => void;
  const promise = new Promise<unknown>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

test("exact one-argument async declaration and fresh named projection", async () => {
  const payload = { ...valid(), extra: "PUBLIC_EXTRA" }; const selected = successful(payload);
  assert.equal(selected.name, "verifyJWT"); assert.equal(selected.length, 1); assert.equal(declarations[0].parameters.length, 1);
  const result = await selected(label); assert.notEqual(result, payload); projected(result, payload.sub, payload.username, 3);
});
test("member capture callback await and repeated projection getter order", async () => {
  const events: string[] = []; let subReads = 0; let userReads = 0;
  const payload = { get sessionVersion() { events.push("version"); return 4; }, get sub() { events.push("sub" + ++subReads); return "PUBLIC_S"; }, get username() { events.push("user" + ++userReads); return "PUBLIC_U"; } };
  const promiseModel = { get resolve() { events.push("resolve-member"); return function (this: unknown, ...args: unknown[]) { assert.equal(this, promiseModel); assert.equal(args.length, 1); events.push("resolve-call"); return args[0]; }; } };
  const numberModel = { get isSafeInteger() { events.push("integer-member"); return function (this: unknown, ...args: unknown[]) { assert.equal(this, numberModel); assert.deepEqual(args, [4]); events.push("integer-call"); return true; }; } };
  const owner = { get run() { events.push("run-member"); return function (this: unknown, ...args: unknown[]) {
    assert.equal(this, owner); assert.equal(args.length, 1); events.push("run-call");
    const result = (args[0] as Stub)(key); events.push("run-return"); return result;
  }; } };
  const selected = load({ keyOwner: owner, promiseModel, numberModel,
    onKeyRead: () => { events.push("key-binding"); }, onPromiseRead: () => { events.push("promise-binding"); },
    onVerifyRead: () => { events.push("verify-binding"); }, onNumberRead: () => { events.push("number-binding"); },
    verify: function (this: unknown, ...args: unknown[]) { assert.equal(this, undefined); assert.equal(args.length, 2); assert.equal(args[0], label); assert.equal(args[1], key); events.push("verify-call"); return { get payload() { events.push("payload"); return payload; } }; } });
  projected(await selected(label), "PUBLIC_S", "PUBLIC_U", 4);
  assert.deepEqual(events, ["key-binding", "run-member", "run-call", "promise-binding", "resolve-member", "verify-binding", "verify-call", "resolve-call", "run-return", "payload", "version", "sub1", "sub2", "user1", "number-binding", "integer-member", "integer-call", "sub3", "user2"]);
});
for (const [name, payload] of [["null", null], ["undefined", undefined], ["false", false], ["true", true], ["zero", 0], ["number", 7], ["string", "PUBLIC"], ["bigint", 1n], ["symbol", Symbol("PUBLIC")]] as const) test("invalid payload metadata refuses: " + name, async () => { assert.equal(await successful(payload)(label), null); });
for (const [name, sub] of [["null", null], ["missing", undefined], ["false", false], ["number", 3], ["bigint", 1n], ["symbol", Symbol("PUBLIC")], ["object", {}], ["array", []], ["function", () => {}], ["empty", ""]] as const) test("invalid subject short-circuits username: " + name, async () => {
  const payload = { sub, get sessionVersion() { return 0; }, get username() { forbidden(); return ""; } };
  assert.equal(await successful(payload)(label), null);
});
for (const [name, username] of [["null", null], ["missing", undefined], ["false", false], ["number", 3], ["bigint", 1n], ["symbol", Symbol("PUBLIC")], ["object", {}], ["array", []], ["function", () => {}]] as const) test("invalid username refuses before integer predicate: " + name, async () => {
  assert.equal(await successful({ sub: "PUBLIC", username, sessionVersion: 0 }, { onNumberRead: forbidden })(label), null);
});
for (const [name, sessionVersion] of [["null", null], ["undefined", undefined]] as const) test("nullish version defaults to zero: " + name, async () => {
  projected(await successful({ sub: "PUBLIC", username: "", sessionVersion })(label), "PUBLIC", "", 0);
});
test("missing version defaults to zero", async () => { projected(await successful({ sub: "PUBLIC", username: "" })(label), "PUBLIC", "", 0); });
for (const [name, sessionVersion] of [["false", false], ["true", true], ["empty", ""], ["numeric string", "0"], ["bigint", 0n], ["object", {}], ["array", []], ["symbol", Symbol("PUBLIC")]] as const) test("nonnumeric version refuses without coercion or integer predicate: " + name, async () => {
  assert.equal(await successful({ ...valid(), sessionVersion }, { onNumberRead: forbidden })(label), null);
});
for (const [name, sessionVersion] of [["negative", -1], ["negative infinity", -Infinity], ["infinity", Infinity], ["NaN", NaN], ["fraction", 0.5], ["unsafe", Number.MAX_SAFE_INTEGER + 1]] as const) test("invalid numeric version refuses: " + name, async () => { assert.equal(await successful({ ...valid(), sessionVersion })(label), null); });
for (const [name, sessionVersion] of [["zero", 0], ["negative zero", -0], ["positive", 1], ["maximum safe", Number.MAX_SAFE_INTEGER]] as const) test("valid numeric version preserved: " + name, async () => { projected(await successful({ sub: "PUBLIC", username: "", sessionVersion })(label), "PUBLIC", "", sessionVersion); });
for (const sub of ["PUBLIC", " ", "__proto__", "PUBLIC_\u03a9"]) test("nonempty subject preserved without normalization: " + sub, async () => { projected(await successful({ sub, username: "", sessionVersion: 0 })(label), sub, "", 0); });
for (const binding of ["onKeyRead", "onVerifyRead", "onPromiseRead", "onNumberRead"] as const) test("inert dependency binding fault is caught: " + binding, async () => { assert.equal(await successful(valid(), { [binding]: () => { throw key; } })(label), null); });
for (const [name, keyOwner] of [["null", null], ["missing run", {}], ["noncallable run", { run: 2 }], ["run getter", { get run() { throw key; } }], ["run throw", { run() { throw key; } }], ["run reject", { run() { return Promise.reject(key); } }]] as const) test("runner metadata fault caught before verifier: " + name, async () => { assert.equal(await load({ keyOwner, verify: forbidden })(label), null); });
for (const [name, runResult] of [["null", null], ["undefined", undefined], ["empty", {}], ["payload getter", { get payload() { throw key; } }]] as const) test("runner return metadata refuses without invoking callback: " + name, async () => { assert.equal(await load({ keyOwner: { run: () => runResult }, verify: forbidden })(label), null); });
for (const asynchronous of [false, true]) test("injected verifier fault caught; asynchronous=" + asynchronous, async () => { assert.equal(await successful(valid(), { verify: () => { if (asynchronous) return Promise.reject(key); throw key; } })(label), null); });
test("noncallable verifier is caught", async () => { assert.equal(await successful(valid(), { verify: {} })(label), null); });
for (const [name, promiseModel] of [["null", null], ["missing resolve", {}], ["noncallable resolve", { resolve: 1 }], ["resolve getter", { get resolve() { throw key; } }], ["resolve throw", { resolve() { throw key; } }]] as const) test("Promise model faults caught: " + name, async () => {
  let calls = 0; assert.equal(await successful(valid(), { promiseModel, verify: () => { calls++; return { payload: valid() }; } })(label), null);
  assert.equal(calls, name === "missing resolve" || name === "noncallable resolve" || name === "resolve throw" ? 1 : 0);
});
for (const [name, numberModel] of [["null", null], ["missing predicate", {}], ["noncallable predicate", { isSafeInteger: 1 }], ["getter fault", { get isSafeInteger() { throw key; } }], ["call fault", { isSafeInteger() { throw key; } }], ["false", { isSafeInteger: () => false }]] as const) test("integer predicate model fault or refusal: " + name, async () => { assert.equal(await successful(valid(), { numberModel })(label), null); });
for (const field of ["sessionVersion", "sub", "username"] as const) test("payload property fault caught: " + field, async () => { const payload = valid(); Object.defineProperty(payload, field, { get() { throw key; } }); assert.equal(await successful(payload)(label), null); });
for (const [field, count] of [["sub", 2], ["sub", 3], ["username", 2]] as const) test("repeated getter fault caught at " + field + " read " + count, async () => { const payload = valid(); let reads = 0; Object.defineProperty(payload, field, { get() { if (++reads === count) throw key; return "PUBLIC"; } }); assert.equal(await successful(payload)(label), null); assert.equal(reads, count); });
test("version read precedes malformed subject refusal", async () => { let reads = 0; assert.equal(await successful({ get sessionVersion() { reads++; return 0; }, sub: 1, get username() { forbidden(); return ""; } })(label), null); assert.equal(reads, 1); });
test("captured version is read once and output is projected only after validation", async () => {
  let reads = 0; const payload = { sub: "PUBLIC", username: "", get sessionVersion() { reads++; return 2; }, get extra() { forbidden(); return 1; }, get then() { forbidden(); return undefined; } };
  projected(await successful(payload)(label), "PUBLIC", "", 2); assert.equal(reads, 1);
});
test("repeated subject and username getters retain source projection semantics", async () => { let s = 0; let u = 0; projected(await successful({ sessionVersion: 0, get sub() { return ["PUBLIC_VALID", "PUBLIC_VALID", "PUBLIC_OUTPUT"][s++]; }, get username() { return ["", "PUBLIC_OUTPUT_USER"][u++]; } })(label), "PUBLIC_OUTPUT", "PUBLIC_OUTPUT_USER", 0); assert.equal(s, 3); assert.equal(u, 2); });
test("held runner result is awaited before payload access", async () => {
  const gate = deferred(); let reads = 0;
  const pending = load({ keyOwner: { run: () => gate.promise }, verify: forbidden })(label);
  await Promise.resolve(); assert.equal(reads, 0);
  gate.resolve({ get payload() { reads++; return valid(); } }); projected(await pending, "PUBLIC_SUBJECT", "PUBLIC_USER", 3); assert.equal(reads, 1);
});
test("injected verifier thenable is adopted before metadata projection", async () => {
  const gate = deferred(); let resolveCalls = 0;
  const pending = successful(valid(), { verify: () => ({ then(resolve: (value: unknown) => void) { resolveCalls++; gate.promise.then(resolve); } }) })(label);
  await Promise.resolve(); assert.equal(resolveCalls, 1); gate.resolve({ payload: valid() }); projected(await pending, "PUBLIC_SUBJECT", "PUBLIC_USER", 3);
});
test("thenable runner rejection is caught", async () => { assert.equal(await load({ keyOwner: { run: () => ({ then(_yes: unknown, no: (reason: unknown) => void) { no(key); } }) }, verify: forbidden })(label), null); });
test("runner may return its metadata without invoking callback", async () => { projected(await load({ keyOwner: { run: () => ({ payload: valid() }) }, verify: forbidden })(label), "PUBLIC_SUBJECT", "PUBLIC_USER", 3); });
test("runner callback uses each supplied key without substitution", async () => {
  const keys = [key, Object.freeze({ publicAlternateKey: true })]; const seen: unknown[] = [];
  const selected = load({ keyOwner: { run: (cb: Stub) => { cb(keys[0]); return cb(keys[1]); } }, verify: (...args: unknown[]) => { seen.push(args[1]); return { payload: valid() }; } });
  projected(await selected(label), "PUBLIC_SUBJECT", "PUBLIC_USER", 3); assert.deepEqual(seen, keys);
});
test("input label and callback key forwarded unchanged with no coercion", async () => {
  const input = Object.freeze({ publicInputMetadata: true }); const owner = { run: (cb: Stub) => cb(key) };
  const selected = load({ keyOwner: owner, verify: (...args: unknown[]) => { assert.equal(args.length, 2); assert.equal(args[0], input); assert.equal(args[1], key); return { payload: valid() }; } });
  projected(await selected(input, "PUBLIC_IGNORED"), "PUBLIC_SUBJECT", "PUBLIC_USER", 3);
});
test("fresh sequential decisions and new projections without cache", async () => {
  let calls = 0; const payload = valid(); const selected = successful(payload, { verify: () => { calls++; return { payload }; } });
  const a = await selected(label); payload.sessionVersion = 4; const b = await selected(label); assert.equal(calls, 2); assert.notEqual(a, b); projected(a, "PUBLIC_SUBJECT", "PUBLIC_USER", 3); projected(b, "PUBLIC_SUBJECT", "PUBLIC_USER", 4);
});
test("concurrent runner results remain paired and independent", async () => {
  const gates = [deferred(), deferred()]; let calls = 0;
  const selected = load({ keyOwner: { run: () => gates[calls++].promise }, verify: forbidden }); const a = selected("PUBLIC_A"); const b = selected("PUBLIC_B");
  assert.equal(calls, 2); gates[1].resolve({ payload: { sub: "PUBLIC_B", username: "", sessionVersion: 2 } }); projected(await b, "PUBLIC_B", "", 2);
  gates[0].resolve({ payload: { sub: "PUBLIC_A", username: "", sessionVersion: 1 } }); projected(await a, "PUBLIC_A", "", 1);
});
