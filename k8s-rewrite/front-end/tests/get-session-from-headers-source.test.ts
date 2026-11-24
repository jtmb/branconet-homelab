import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

// PUBLIC SOURCE controls. Strings below are inert parser metadata; no token,
// credential, real Headers/cookie store, verifier or account implementation runs.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);
assert.equal(process.version, "v24.18.0");
const raw = readFileSync(fileURLToPath(new URL("../src/lib/auth.ts", import.meta.url)), "utf8");
const source = raw.replaceAll("\r\n", "\n");
assert.ok(raw === source || raw === source.replaceAll("\n", "\r\n"));
assert.equal(createHash("sha256").update(source).digest("hex"), "932034e70f9d0447eb23c38ce91cb799413d289eb0a3bd25f3808c25865f2aff");
const ast = ts.createSourceFile("auth.ts", source, ts.ScriptTarget.Latest, true);
const declarations = ast.statements.filter((n: { name?: { text: string } }) => ts.isFunctionDeclaration(n) && n.name?.text === "getSessionFromHeaders");
assert.equal(declarations.length, 1);
const declaration = declarations[0].getText(ast);
assert.equal(createHash("sha256").update(declaration).digest("hex"), "46335e19c65ac7f64ae3d6bb3854bf373aca39d6c9aeb83833378e0d389c23e9");
const javascript = ts.transpileModule(declaration.replace(/^export /, ""), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
assert.ok(!javascript.includes("import ") && !javascript.includes("require("));
type Selected = (header: unknown, ...extra: unknown[]) => Promise<unknown>;
type Stub = (...args: unknown[]) => unknown;
const cookie = "botrus_auth_token";
const header = (value = "PUBLIC_STUB_A") => cookie + "=" + value;
const payload = Object.freeze({ publicIdentity: "VERIFIER_METADATA" });
const session = Object.freeze({ publicIdentity: "ACCOUNT_METADATA" });
const fail: Stub = () => assert.fail("unreachable synthetic binding");
function load(verify: Stub = fail, current: Stub = fail, RegExpBinding: unknown = RegExp): Selected {
  return vm.runInNewContext("(" + javascript + ")", { AUTH_COOKIE: cookie, verifyJWT: verify, currentSession: current, RegExp: RegExpBinding });
}
function deferred() {
  let resolve!: (value: unknown) => void;
  let reject!: (value: unknown) => void;
  const promise = new Promise<unknown>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

test("one pinned async declaration, one parameter and seven ordered statements", () => {
  const selected = load();
  assert.equal(selected.name, "getSessionFromHeaders");
  assert.equal(selected.length, 1);
  assert.equal(declarations[0].parameters.length, 1);
  assert.equal(declarations[0].body.statements.length, 7);
});
const falsy = [["null", null], ["empty", ""], ["undefined", undefined], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["zero bigint", 0n]] as const;
for (const [name, value] of falsy) test("falsy header metadata short circuits: " + name, async () => {
  const forbiddenRegExp = new Proxy(function PublicRegExp() {}, { construct() { assert.fail("unexpected construction"); } });
  assert.equal(await load(fail, fail, forbiddenRegExp)(value), null);
});
const absent = ["unrelated=PUBLIC", "xbotrus_auth_token=PUBLIC", "botrus_auth_token_suffix=PUBLIC", "BOTRUS_AUTH_TOKEN=PUBLIC", "botrus_auth_token =PUBLIC", " botrus_auth_token=PUBLIC", "a=PUBLIC,botrus_auth_token=PUBLIC", "botrus_auth_token"];
for (const value of absent) test("exact parser rejects nonmatching public metadata: " + value, async () => {
  assert.equal(await load()(value), null);
});
const matches = [
  [header(), "PUBLIC_STUB_A"], ["a=PUBLIC;" + header(), "PUBLIC_STUB_A"],
  ["a=PUBLIC; " + header(), "PUBLIC_STUB_A"], ["a=PUBLIC;\t " + header(), "PUBLIC_STUB_A"],
  [header() + ";a=PUBLIC", "PUBLIC_STUB_A"], [header("PUBLIC=TAIL"), "PUBLIC=TAIL"],
  [header("PUBLIC%20TEXT"), "PUBLIC%20TEXT"], [header(" PUBLIC "), " PUBLIC "],
  [header("0"), "0"], [header("PUBLIC,TAIL"), "PUBLIC,TAIL"],
  [header("PUBLIC_FIRST") + ";" + header("PUBLIC_SECOND"), "PUBLIC_FIRST"],
  ["a=PUBLIC;\n" + header(), "PUBLIC_STUB_A"],
] as const;
for (const [value, extracted] of matches) test("exact source passes parser metadata unchanged: " + JSON.stringify(value), async () => {
  const calls: string[] = [];
  const selected = load((...args) => { assert.equal(args.length, 1); assert.equal(args[0], extracted); calls.push("verify"); return payload; }, (...args) => { assert.equal(args.length, 1); assert.equal(args[0], payload); calls.push("current"); return session; });
  assert.equal(await selected(value), session);
  assert.deepEqual(calls, ["verify", "current"]);
});
for (const value of [header(""), header("") + ";" + header("PUBLIC_LATER")]) test("empty first capture refuses without duplicate fallback: " + value, async () => {
  assert.equal(await load()(value), null);
});
for (const [name, value] of falsy) test("falsy verifier metadata refuses account lookup: " + name, async () => {
  assert.equal(await load(() => value)(header()), null);
});
const truthy = [["object", payload], ["public text", "PUBLIC_PAYLOAD"], ["one", 1], ["bigint", 1n], ["symbol", Symbol("public payload")], ["array", []], ["function", () => undefined]] as const;
for (const [name, value] of truthy) test("truthy verifier metadata is forwarded by identity: " + name, async () => {
  assert.equal(await load(() => value, (seen) => { assert.equal(seen, value); return session; })(header()), session);
});
test("verifier promise is awaited before current metadata lookup", async () => {
  const pending = deferred(); const events: string[] = [];
  const result = load(() => { events.push("verify"); return pending.promise; }, (seen) => { assert.equal(seen, payload); events.push("current"); return session; })(header());
  assert.deepEqual(events, ["verify"]);
  pending.resolve(payload);
  assert.equal(await result, session);
  assert.deepEqual(events, ["verify", "current"]);
});
test("current metadata promise is adopted and no intermediate identity is released", async () => {
  const pending = deferred(); let called = false; let settled = false;
  const result = load(() => payload, () => { called = true; return pending.promise; })(header());
  result.then(() => { settled = true; });
  await Promise.resolve(); assert.equal(called, true); assert.equal(settled, false);
  pending.resolve(session); assert.equal(await result, session);
});
test("synchronous verifier fault is an identical rejection without current lookup", async () => {
  const fault = Object.freeze({ publicFault: "verify" });
  let result!: Promise<unknown>;
  assert.doesNotThrow(() => { result = load(() => { throw fault; })(header()); });
  await assert.rejects(result, (seen: unknown) => seen === fault);
});
test("asynchronous verifier fault is an identical rejection", async () => {
  const fault = Symbol("public verifier rejection");
  await assert.rejects(load(() => Promise.reject(fault))(header()), (seen: unknown) => seen === fault);
});
test("synchronous current metadata fault is an identical rejection", async () => {
  const fault = Object.freeze({ publicFault: "current" });
  await assert.rejects(load(() => payload, () => { throw fault; })(header()), (seen: unknown) => seen === fault);
});
test("asynchronous current metadata fault is an identical rejection", async () => {
  const fault = Symbol("public current rejection");
  await assert.rejects(load(() => payload, () => Promise.reject(fault))(header()), (seen: unknown) => seen === fault);
});
test("current null result stays null without replacing it with verifier metadata", async () => {
  assert.equal(await load(() => payload, () => null)(header()), null);
});
test("source forwards unexpected current metadata unchanged without validation claim", async () => {
  assert.equal(await load(() => payload, () => undefined)(header()), undefined);
});
test("match receiver, regexp source and flags are exact with no mutation", async () => {
  let receiver: unknown; let reads = 0; let calls = 0;
  const metadata = Object.freeze({ get match() { reads++; return function(this: unknown, ...args: unknown[]) { receiver = this; calls++; assert.equal(args.length, 1); const pattern = args[0] as RegExp; assert.equal(pattern.source, "(?:^|;\\s*)botrus_auth_token=([^;]*)"); assert.equal(pattern.flags, ""); return null; }; } });
  assert.equal(await load()(metadata), null); assert.equal(receiver, metadata); assert.equal(reads, 1); assert.equal(calls, 1);
});
test("match getter fault rejects identically before verifier", async () => {
  const fault = Symbol("public match getter");
  await assert.rejects(load()({ get match() { throw fault; } }), (seen: unknown) => seen === fault);
});
test("match call fault rejects identically before verifier", async () => {
  const fault = Symbol("public match call");
  await assert.rejects(load()({ match() { throw fault; } }), (seen: unknown) => seen === fault);
});
test("regexp construction fault rejects identically before match invocation", async () => {
  const fault = Symbol("public regexp construction");
  const binding = new Proxy(function PublicRegExp() {}, { construct() { throw fault; } });
  await assert.rejects(load(fail, fail, binding)({ match: fail }), (seen: unknown) => seen === fault);
});
test("optional match capture is read once and no other result property is inspected", async () => {
  const result = new Proxy({}, { get(_target, key) { assert.equal(key, "1"); return "PUBLIC_CAPTURE"; }, set() { assert.fail("write"); }, ownKeys() { assert.fail("enumeration"); } });
  let reads = 0;
  const selected = load((value) => { reads++; assert.equal(value, "PUBLIC_CAPTURE"); return payload; }, () => session);
  assert.equal(await selected({ match() { return result; } }), session); assert.equal(reads, 1);
});
test("capture getter fault rejects identically", async () => {
  const fault = Symbol("public capture getter");
  await assert.rejects(load()({ match() { return { get 1() { throw fault; } }; } }), (seen: unknown) => seen === fault);
});
test("fresh verifier and account decisions are obtained on every invocation", async () => {
  let verified = true; let current: unknown = session; let verifyCalls = 0; let currentCalls = 0;
  const selected = load(() => { verifyCalls++; return verified ? payload : null; }, () => { currentCalls++; return current; });
  assert.equal(await selected(header()), session); current = null;
  assert.equal(await selected(header()), null); current = session; verified = false;
  assert.equal(await selected(header()), null); verified = true;
  assert.equal(await selected(header()), session); assert.equal(verifyCalls, 4); assert.equal(currentCalls, 3);
});
test("simultaneous calls retain their own payload and out of order current results", async () => {
  const first = deferred(); const second = deferred(); const a = Object.freeze({ public: "A" }); const b = Object.freeze({ public: "B" });
  const selected = load(value => value === "PUBLIC_A" ? a : b, seen => seen === a ? first.promise : second.promise);
  const one = selected(header("PUBLIC_A")); const two = selected(header("PUBLIC_B"));
  second.resolve(b); assert.equal(await two, b); first.resolve(a); assert.equal(await one, a);
});
test("fresh calls return distinct promises even for a synchronous null branch", async () => {
  const selected = load(); const first = selected(null); const second = selected(null);
  assert.notEqual(first, second); assert.deepEqual(await Promise.all([first, second]), [null, null]);
});
test("unused this and extra argument metadata stays opaque", async () => {
  const opaque = new Proxy({}, { get() { assert.fail("unused property access"); } });
  assert.equal(await load(() => payload, () => session).call(opaque, header(), opaque), session);
});
test("nonthenable payload properties remain opaque to the selected declaration", async () => {
  const opaque = new Proxy({}, { get(_target, key) { assert.equal(key, "then"); return undefined; }, ownKeys() { assert.fail("enumeration"); } });
  assert.equal(await load(() => opaque, seen => { assert.equal(seen, opaque); return session; })(header()), session);
});
