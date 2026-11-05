import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

// PUBLIC synthetic labels only; no original imports, initializer, neighbours or auth services execute.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);
assert.equal(process.version, "v24.18.0");
const raw = readFileSync(fileURLToPath(new URL("../src/lib/auth.ts", import.meta.url)), "utf8");
const source = raw.replaceAll("\r\n", "\n");
assert.ok(raw === source || raw === source.replaceAll("\n", "\r\n"));
assert.equal(createHash("sha256").update(source).digest("hex"), "932034e70f9d0447eb23c38ce91cb799413d289eb0a3bd25f3808c25865f2aff");
const ast = ts.createSourceFile("auth.ts", source, ts.ScriptTarget.Latest, true);
const declarations = ast.statements.filter((n: { name?: { text: string } }) => ts.isFunctionDeclaration(n) && n.name?.text === "getSessionAccountFromHeaders");
assert.equal(declarations.length, 1);
const declaration = declarations[0].getText(ast);
const expectedDeclaration = "export async function getSessionAccountFromHeaders(cookieHeader: string | null): Promise<SessionAccount | null> {\n  if (!cookieHeader) return null;\n  const token = cookieHeader.match(new RegExp(`(?:^|;\\\\s*)${AUTH_COOKIE}=([^;]*)`))?.[1];\n  if (!token) return null;\n  const payload = await verifyJWT(token);\n  return payload ? currentAccount(payload) : null;\n}";
assert.equal(declaration, expectedDeclaration);
const javascript = ts.transpileModule(declaration.replace(/^export /, ""), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
assert.ok(!javascript.includes("import(") && !javascript.includes("require("));
type Selected = (...args: unknown[]) => Promise<unknown>;
type Stub = (...args: unknown[]) => unknown;
const forbiddenCalls: string[] = [];
const forbidden: Stub = () => { forbiddenCalls.push("unexpected dependency"); throw new Error("unexpected dependency"); };
test.afterEach(() => { assert.deepEqual(forbiddenCalls, []); });
function load(options: { verify?: unknown; current?: unknown; regexp?: unknown; cookie?: unknown } = {}): Selected {
  return vm.runInNewContext('"use strict"; (' + javascript + ')', {
    verifyJWT: Object.hasOwn(options, "verify") ? options.verify : forbidden,
    currentAccount: Object.hasOwn(options, "current") ? options.current : forbidden,
    RegExp: Object.hasOwn(options, "regexp") ? options.regexp : RegExp,
    AUTH_COOKIE: Object.hasOwn(options, "cookie") ? options.cookie : "botrus_auth_token",
  });
}
const header = "botrus_auth_token=PUBLIC_LABEL";
const result = Object.freeze({ publicResult: true });
function deferred() {
  let resolve!: (value: unknown) => void; let reject!: (value: unknown) => void;
  const promise = new Promise<unknown>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

test("only selected async declaration; no account projection or additional argument forwarding", async () => {
  const payload = Object.freeze({ publicPayload: true }); let calls = 0;
  const f = load({ verify: () => payload, current: (...args: unknown[]) => { calls++; assert.equal(args.length, 1); assert.equal(args[0], payload); return result; } });
  assert.equal(f.name, "getSessionAccountFromHeaders"); assert.equal(f.length, 1); assert.equal(declarations[0].body.statements.length, 5);
  assert.equal(await f(header, "PUBLIC_IGNORED"), result); assert.equal(calls, 1);
});
for (const [name, value] of [["null", null], ["undefined", undefined], ["empty", ""], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["zero bigint", 0n]] as const) test("falsy header avoids all dependencies: " + name, async () => {
  assert.equal(await load({ regexp: forbidden })(value), null);
});
for (const text of ["PUBLIC_OTHER", "Botrus_auth_token=PUBLIC_LABEL", "xbotrus_auth_token=PUBLIC_LABEL", " botrus_auth_token=PUBLIC_LABEL", "botrus_auth_token", "botrus_auth_token=", "botrus_auth_token =PUBLIC_LABEL", "botrus_auth_token=;botrus_auth_token=PUBLIC_SECOND"]) test("absent or first-empty synthetic label refuses: " + text, async () => {
  assert.equal(await load()(text), null);
});
for (const [text, label] of [[header, "PUBLIC_LABEL"], [header + ";other=PUBLIC_OTHER", "PUBLIC_LABEL"], ["other=PUBLIC_OTHER;botrus_auth_token=PUBLIC_LABEL", "PUBLIC_LABEL"], ["other=PUBLIC_OTHER; \tbotrus_auth_token=PUBLIC_LABEL", "PUBLIC_LABEL"], ["other=PUBLIC_OTHER;\nbotrus_auth_token=PUBLIC_LABEL", "PUBLIC_LABEL"], [header + ";botrus_auth_token=PUBLIC_SECOND", "PUBLIC_LABEL"], ["botrus_auth_token=PUBLIC=LABEL", "PUBLIC=LABEL"], ["botrus_auth_token=%50UBLIC_LABEL", "%50UBLIC_LABEL"], ["botrus_auth_token=\"PUBLIC_LABEL\"", "\"PUBLIC_LABEL\""], ["botrus_auth_token= PUBLIC_LABEL ", " PUBLIC_LABEL "]] as const) test("exact first regex capture forwarded without decoding: " + text, async () => {
  const p = Object.freeze({ publicPayload: true }); let verified = 0; let current = 0;
  assert.equal(await load({ verify: function (this: unknown, ...args: unknown[]) { assert.equal(this, undefined); assert.equal(args.length, 1); assert.equal(args[0], label); verified++; return p; }, current: function (this: unknown, ...args: unknown[]) { assert.equal(this, undefined); assert.equal(args.length, 1); assert.equal(args[0], p); current++; return result; } })(text), result);
  assert.equal(verified, 1); assert.equal(current, 1);
});
test("capture match then construct regex then invoke exact receiver then index then verifier then account", async () => {
  const events: string[] = []; let regex!: RegExp; const p = Object.freeze({ publicPayload: true });
  function Constructor(this: unknown, ...args: unknown[]) { events.push("construct"); assert.equal(args.length, 1); assert.equal(args[0], "(?:^|;\\s*)botrus_auth_token=([^;]*)"); regex = new RegExp(args[0] as string); return regex; }
  const h = { get match() { events.push("member"); return function (this: unknown, ...args: unknown[]) { events.push("call"); assert.equal(this, h); assert.equal(args.length, 1); assert.equal(args[0], regex); assert.equal(regex.flags, ""); return { get 1() { events.push("index"); return "PUBLIC_LABEL"; } }; }; } };
  assert.equal(await load({ regexp: Constructor, verify: () => { events.push("verify"); return p; }, current: () => { events.push("current"); return result; } })(h), result);
  assert.deepEqual(events, ["member", "construct", "call", "index", "verify", "current"]);
});
for (const [name, value] of [["null", null], ["undefined", undefined], ["missing index", {}], ["empty array", []]] as const) test("nullish match or missing capture refuses: " + name, async () => { assert.equal(await load()({ match: () => value }), null); });
for (const [name, value] of [["null", null], ["undefined", undefined], ["empty", ""], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["zero bigint", 0n]] as const) test("falsy synthetic capture avoids verifier: " + name, async () => { assert.equal(await load()({ match: () => ({ 1: value }) }), null); });
for (const [name, value] of [["null", null], ["undefined", undefined], ["empty", ""], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["zero bigint", 0n]] as const) test("awaited falsy verifier payload avoids account: " + name, async () => { assert.equal(await load({ verify: () => value })(header), null); });
for (const [name, value] of [["object", Object.freeze({ publicPayload: true })], ["string", "PUBLIC_PAYLOAD"], ["number", 1], ["boolean", true], ["bigint", 1n]] as const) test("truthy inert verifier payload forwarded unchanged: " + name, async () => { assert.equal(await load({ verify: () => value, current: (...args: unknown[]) => { assert.equal(args.length, 1); assert.equal(args[0], value); return result; } })(header), result); });
for (const [name, value] of [["number", 1], ["boolean", true], ["missing match", {}], ["noncallable match", { match: 1 }]] as const) test("truthy malformed inert header rejects before verifier: " + name, async () => { await assert.rejects(load()(value), { name: "TypeError" }); });
for (const position of ["member", "construct", "call", "index"] as const) test("pre-verifier fault propagates exactly and stops later stages: " + position, async () => {
  const fault = Object.freeze({ publicFault: position }); const events: string[] = [];
  const visit = (stage: string) => { events.push(stage); if (position === stage) throw fault; };
  function Constructor() { visit("construct"); return /PUBLIC/; }
  const h = { get match() { visit("member"); return () => { visit("call"); return { get 1() { visit("index"); return "PUBLIC_LABEL"; } }; }; } };
  await assert.rejects(load({ regexp: Constructor })(h), (e: unknown) => e === fault);
  assert.deepEqual(events, ["member", "construct", "call", "index"].slice(0, ["member", "construct", "call", "index"].indexOf(position) + 1));
});
for (const asynchronous of [false, true]) test("verifier fault has no catch or account fallback; async=" + asynchronous, async () => {
  const fault = Object.freeze({ publicFault: "VERIFY" });
  await assert.rejects(load({ verify: () => { if (asynchronous) return Promise.reject(fault); throw fault; } })(header), (e: unknown) => e === fault);
});
for (const asynchronous of [false, true]) test("account fault has no catch or fallback; async=" + asynchronous, async () => {
  const fault = Object.freeze({ publicFault: "ACCOUNT" });
  await assert.rejects(load({ verify: () => ({ publicPayload: true }), current: () => { if (asynchronous) return Promise.reject(fault); throw fault; } })(header), (e: unknown) => e === fault);
});
test("verifier await fences account invocation until payload fulfillment", async () => {
  const gate = deferred(); const p = Object.freeze({ publicPayload: true }); let calls = 0;
  const pending = load({ verify: () => gate.promise, current: (value: unknown) => { calls++; assert.equal(value, p); return result; } })(header);
  await Promise.resolve(); assert.equal(calls, 0); gate.resolve(p); assert.equal(await pending, result); assert.equal(calls, 1);
});
test("pending verifier rejection retains reason and never calls account", async () => {
  const gate = deferred(); const fault = Object.freeze({ publicFault: "PENDING_VERIFY" });
  const checked = assert.rejects(load({ verify: () => gate.promise })(header), (e: unknown) => e === fault); gate.reject(fault); await checked;
});
test("verifier thenable is adopted once before passing exact payload", async () => {
  let reads = 0; let calls = 0; const p = Object.freeze({ publicPayload: true });
  const thenable = { get then() { reads++; return function (this: unknown, resolve: (v: unknown) => void) { assert.equal(this, thenable); calls++; resolve(p); }; } };
  assert.equal(await load({ verify: () => thenable, current: (value: unknown) => { assert.equal(value, p); return result; } })(header), result); assert.equal(reads, 1); assert.equal(calls, 1);
});
for (const stage of ["verify", "current"] as const) test("then getter failure propagates exact reason: " + stage, async () => {
  const fault = Object.freeze({ publicFault: "THEN" }); const value = { get then() { throw fault; } };
  await assert.rejects(load({ verify: () => stage === "verify" ? value : ({ publicPayload: true }), current: () => value })(header), (e: unknown) => e === fault);
});
test("account return adoption waits for pending fulfillment without projecting properties", async () => {
  const gate = deferred(); let settled = false;
  const pending = load({ verify: () => ({ publicPayload: true }), current: () => gate.promise })(header);
  const observed = pending.then((v: unknown) => { settled = true; assert.equal(v, result); });
  await Promise.resolve(); assert.equal(settled, false); gate.resolve(result); await observed;
});
test("account custom thenable is adopted once with exact receiver and outcome", async () => {
  let reads = 0; let calls = 0;
  const value = { get then() { reads++; return function (this: unknown, resolve: (v: unknown) => void) { assert.equal(this, value); calls++; resolve(result); }; } };
  const pending = load({ verify: () => ({ publicPayload: true }), current: () => value })(header);
  await pending.then((v: unknown) => { assert.equal(v, result); }); assert.equal(reads, 1); assert.equal(calls, 1);
});
test("payload properties and account authorization fields stay unread", async () => {
  const trap = () => { forbiddenCalls.push("projection"); throw new Error("unused"); };
  const p = { get sub() { return trap(); }, get sessionVersion() { return trap(); } }; const u = { get id() { return trap(); }, get role() { return trap(); }, get engineAdmin() { return trap(); } };
  assert.equal(await load({ verify: () => p, current: (v: unknown) => { assert.equal(v, p); return u; } })(header), u);
});
test("each invocation re-verifies and obtains fresh account result", async () => {
  let count = 0; const one = Object.freeze({ publicResult: 1 }); const two = Object.freeze({ publicResult: 2 });
  const f = load({ verify: () => (++count === 1 ? { publicPayload: 1 } : { publicPayload: 2 }), current: () => count === 1 ? one : two });
  assert.equal(await f(header), one); assert.equal(await f(header), two); assert.equal(count, 2);
});
test("concurrent verifier completions retain their own payload and result", async () => {
  const a = deferred(); const b = deferred(); const pa = Object.freeze({ publicPayload: "A" }); const pb = Object.freeze({ publicPayload: "B" });
  const ra = Object.freeze({ publicResult: "A" }); const rb = Object.freeze({ publicResult: "B" }); const events: string[] = [];
  const f = load({ verify: (v: unknown) => { events.push(String(v)); return v === "PUBLIC_A" ? a.promise : b.promise; }, current: (p: unknown) => p === pa ? ra : p === pb ? rb : forbidden() });
  const first = f("botrus_auth_token=PUBLIC_A"); const second = f("botrus_auth_token=PUBLIC_B");
  b.resolve(pb); assert.equal(await second, rb); a.resolve(pa); assert.equal(await first, ra); assert.deepEqual(events, ["PUBLIC_A", "PUBLIC_B"]);
});
