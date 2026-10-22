import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

// PUBLIC inert payload/account metadata only. Lift one declaration; original
// imports, module initializers, reader implementation and authentication stay inert.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);
assert.equal(process.version, "v24.18.0");
const raw = readFileSync(fileURLToPath(new URL("../src/lib/auth.ts", import.meta.url)), "utf8");
const source = raw.replaceAll("\r\n", "\n");
assert.ok(raw === source || raw === source.replaceAll("\n", "\r\n"));
assert.equal(createHash("sha256").update(source).digest("hex"), "932034e70f9d0447eb23c38ce91cb799413d289eb0a3bd25f3808c25865f2aff");
const ast = ts.createSourceFile("auth.ts", source, ts.ScriptTarget.Latest, true);
const declarations = ast.statements.filter((n: { name?: { text: string } }) => ts.isFunctionDeclaration(n) && n.name?.text === "currentSession");
assert.equal(declarations.length, 1);
const declaration = declarations[0].getText(ast);
assert.equal(createHash("sha256").update(declaration).digest("hex"), "8e96b84b6ffffe1cb5fbd5b9b4a4ace86568ca0d5586b3da274d751798095032");
const javascript = ts.transpileModule(declaration, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
assert.ok(!javascript.includes("import(") && !javascript.includes("require("));
type Selected = (...args: unknown[]) => Promise<unknown>;
type Stub = (...args: unknown[]) => unknown;
const forbiddenCalls: string[] = [];
const forbidden: Stub = () => { forbiddenCalls.push("unexpected injected reader"); throw new Error("unexpected injected reader"); };
test.afterEach(() => { assert.deepEqual(forbiddenCalls, []); });
function load(...readers: unknown[]): Selected {
  const reader = readers.length ? readers[0] : { readSession: forbidden };
  return vm.runInNewContext("(" + javascript + ")", { directAccountReader: reader });
}
const payload = (version: unknown = 7) => ({ sub: "PUBLIC_SUBJECT", username: "UNUSED_PAYLOAD_NAME", sessionVersion: version });
const user = (version: unknown = 7) => ({ id: "PUBLIC_ID", username: "PUBLIC_CURRENT_NAME", sessionVersion: version });
function projected(actual: unknown, expected: { id: unknown; username: unknown; sessionVersion: unknown }) {
  assert.ok(actual && typeof actual === "object");
  const value = actual as Record<string, unknown>;
  assert.deepEqual(Object.keys(value), ["id", "username", "sessionVersion"]);
  assert.equal(value.id, expected.id); assert.equal(value.username, expected.username); assert.equal(value.sessionVersion, expected.sessionVersion);
}
function deferred() {
  let resolve!: (value: unknown) => void;
  let reject!: (value: unknown) => void;
  const promise = new Promise<unknown>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const falsy = [["null", null], ["undefined", undefined], ["empty", ""], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["zero bigint", 0n]] as const;

test("pinned one-parameter async declaration and fresh projection", async () => {
  const selected = load({ readSession: () => user() });
  assert.equal(selected.name, "currentSession"); assert.equal(selected.length, 1);
  assert.equal(declarations[0].parameters.length, 1); assert.equal(declarations[0].body.statements.length, 3);
  const first = await selected(payload()); const second = await selected(payload(), "PUBLIC_UNUSED");
  projected(first, user()); projected(second, user()); assert.notEqual(first, second);
});
test("member before subject; exact reader receiver/argument; version comparison before ordered projection", async () => {
  const events: string[] = [];
  const identity = { publicSubject: "UNCOERCED" };
  const p = { get sub() { events.push("sub"); return identity; }, get sessionVersion() { events.push("payload-version"); return 7; }, get username() { forbiddenCalls.push("payload-name"); throw new Error("unused"); } };
  const u = { get sessionVersion() { events.push("user-version"); return 7; }, get id() { events.push("id"); return "PUBLIC_ID"; }, get username() { events.push("name"); return "PUBLIC_CURRENT_NAME"; } };
  const reader = { get readSession() { events.push("member"); return function (this: unknown, ...args: unknown[]) { assert.equal(this, reader); assert.equal(args.length, 1); assert.equal(args[0], identity); events.push("call"); return u; }; } };
  const result = await load(reader)(p); projected(result, user()); assert.notEqual(result, u);
  assert.deepEqual(events, ["member", "sub", "call", "user-version", "payload-version", "id", "name", "user-version"]);
});
for (const [name, value] of falsy) test("falsy awaited account short-circuits all version/projection reads: " + name, async () => {
  const p = { sub: "PUBLIC_SUBJECT", get sessionVersion() { forbiddenCalls.push("version-after-falsy"); throw new Error("unused"); } };
  assert.equal(await load({ readSession: () => value })(p), null);
});
for (const [name, value] of [["string", "7"], ["other", 8], ["missing", undefined], ["null", null], ["boolean", true], ["bigint", 7n], ["NaN", NaN], ["object", {}]] as const) test("strict unequal version refuses before projection: " + name, async () => {
  const u = { sessionVersion: value, get id() { forbiddenCalls.push("id-after-mismatch"); throw new Error("unused"); }, get username() { forbiddenCalls.push("name-after-mismatch"); throw new Error("unused"); } };
  assert.equal(await load({ readSession: () => u })(payload()), null);
});
for (const [name, version] of [["number", 7], ["zero", 0], ["string metadata", "PUBLIC_VERSION"], ["undefined metadata", undefined], ["null metadata", null], ["boolean metadata", false], ["bigint metadata", 3n], ["object identity metadata", {}]] as const) test("equal inert version metadata uses strict equality without extra validation: " + name, async () => {
  const p = { sub: "PUBLIC_SUBJECT", sessionVersion: version }; const u = { id: "PUBLIC_ID", username: "PUBLIC_CURRENT_NAME", sessionVersion: version };
  projected(await load({ readSession: () => u })(p), u);
});
test("positive and negative zero versions compare equal; returned value comes from current account", async () => {
  const result = await load({ readSession: () => user(-0) })(payload(0));
  projected(result, user(-0)); assert.ok(Object.is((result as { sessionVersion: unknown }).sessionVersion, -0));
});
test("two NaN metadata versions refuse under strict inequality", async () => { assert.equal(await load({ readSession: () => user(NaN) })(payload(NaN)), null); });
for (const [name, subject] of [["undefined", undefined], ["null", null], ["empty", ""], ["number", 3], ["object", {}]] as const) test("subject metadata forwarded unchanged without coercion: " + name, async () => {
  let calls = 0;
  const selected = load({ readSession: (...args: unknown[]) => { calls++; assert.equal(args.length, 1); assert.equal(args[0], subject); return user(); } });
  projected(await selected({ sub: subject, sessionVersion: 7 }), user()); assert.equal(calls, 1);
});
for (const [name, reader] of [["null", null], ["undefined", undefined], ["missing member", {}], ["noncallable", { readSession: 1 }]] as const) test("invalid inert reader rejects: " + name, async () => { await assert.rejects(load(reader)(payload()), { name: "TypeError" }); });
for (const [name, p] of [["null", null], ["undefined", undefined]] as const) test("invalid payload rejects before reader call: " + name, async () => { await assert.rejects(load()(p), { name: "TypeError" }); });
test("reader-member fault precedes payload access and propagates exact fault", async () => {
  const fault = Object.freeze({ publicFault: "MEMBER" });
  const selected = load({ get readSession() { throw fault; } });
  const p = { get sub() { forbiddenCalls.push("sub-after-member-fault"); throw new Error("unused"); } };
  await assert.rejects(selected(p), (e: unknown) => e === fault);
});
test("subject getter fault propagates without calling captured member", async () => {
  const fault = Object.freeze({ publicFault: "SUBJECT" });
  await assert.rejects(load({ readSession: forbidden })({ get sub() { throw fault; } }), (e: unknown) => e === fault);
});
for (const asynchronous of [false, true]) test("reader fault propagates exact identity, async=" + asynchronous, async () => {
  const fault = Object.freeze({ publicFault: "READ" });
  await assert.rejects(load({ readSession: () => { if (asynchronous) return Promise.reject(fault); throw fault; } })(payload()), (e: unknown) => e === fault);
});
for (const position of ["user-version-first", "payload-version", "id", "username", "user-version-second"] as const) test("ordered metadata getter fault propagates and stops later reads: " + position, async () => {
  const events: string[] = []; const fault = Object.freeze({ publicFault: position }); let versions = 0;
  const read = (name: string, value: unknown) => { events.push(name); if (name === position) throw fault; return value; };
  const u = { get sessionVersion() { return read(++versions === 1 ? "user-version-first" : "user-version-second", 7); }, get id() { return read("id", "PUBLIC_ID"); }, get username() { return read("username", "PUBLIC_CURRENT_NAME"); } };
  const p = { sub: "PUBLIC_SUBJECT", get sessionVersion() { return read("payload-version", 7); } };
  await assert.rejects(load({ readSession: () => u })(p), (e: unknown) => e === fault);
  const expected = ["user-version-first", "payload-version", "id", "username", "user-version-second"];
  assert.deepEqual(events, expected.slice(0, expected.indexOf(position) + 1));
});
test("await fence prevents version/projection reads until read fulfills", async () => {
  const gate = deferred(); const events: string[] = []; let settled = false;
  const pending = load({ readSession: () => { events.push("read"); return gate.promise; } })({ sub: "PUBLIC_SUBJECT", get sessionVersion() { events.push("version"); return 7; } });
  void pending.then(() => { settled = true; }); await Promise.resolve();
  assert.deepEqual(events, ["read"]); assert.equal(settled, false); gate.resolve(user()); projected(await pending, user()); assert.deepEqual(events, ["read", "version"]);
});
test("pending read rejection skips version access and retains rejection identity", async () => {
  const gate = deferred(); const fault = Object.freeze({ publicFault: "PENDING" });
  const pending = load({ readSession: () => gate.promise })({ sub: "PUBLIC_SUBJECT", get sessionVersion() { forbiddenCalls.push("version-after-rejection"); throw new Error("unused"); } });
  const rejected = assert.rejects(pending, (e: unknown) => e === fault); gate.reject(fault); await rejected;
});
test("custom read thenable is assimilated once before metadata decision", async () => {
  let calls = 0; const account = user();
  const thenable = { then(resolve: (value: unknown) => void) { calls++; resolve(account); } };
  projected(await load({ readSession: () => thenable })(payload()), account); assert.equal(calls, 1);
});
test("awaited read then-getter fault propagates", async () => {
  const fault = Object.freeze({ publicFault: "THEN" });
  await assert.rejects(load({ readSession: () => ({ get then() { throw fault; } }) })(payload()), (e: unknown) => e === fault);
});
test("projection rereads version and uses current account fields rather than payload username", async () => {
  let reads = 0; const u = { id: "PUBLIC_NEW_ID", username: "PUBLIC_NEW_NAME", get sessionVersion() { return ++reads === 1 ? 7 : 9; } };
  projected(await load({ readSession: () => u })(payload()), { id: "PUBLIC_NEW_ID", username: "PUBLIC_NEW_NAME", sessionVersion: 9 }); assert.equal(reads, 2);
});
test("projection values are copied unchanged and unrelated fields are not read", async () => {
  const id = Object.freeze({ publicField: "ID" }); const username = Object.freeze({ publicField: "NAME" });
  const u = { id, username, sessionVersion: 7, get role() { forbiddenCalls.push("role"); throw new Error("unused"); }, get passwordHash() { forbiddenCalls.push("password"); throw new Error("unused"); }, get then() { return undefined; } };
  projected(await load({ readSession: () => u })(payload()), u);
});
test("same selected function makes fresh allow/refuse/allow decisions with no user cache", async () => {
  const values = [user(), null, user(8)]; let calls = 0;
  const selected = load({ readSession: () => values[calls++] });
  projected(await selected(payload()), user()); assert.equal(await selected(payload()), null); projected(await selected(payload(8)), user(8)); assert.equal(calls, 3);
});
test("concurrent calls keep their own payloads and out-of-order account results", async () => {
  const a = deferred(); const b = deferred(); const subjects: unknown[] = [];
  const selected = load({ readSession: (sub: unknown) => { subjects.push(sub); return sub === "PUBLIC_A" ? a.promise : b.promise; } });
  const pa = selected({ sub: "PUBLIC_A", sessionVersion: 7 }); const pb = selected({ sub: "PUBLIC_B", sessionVersion: 8 });
  b.resolve(user(7)); assert.equal(await pb, null); a.resolve(user(7)); projected(await pa, user(7)); assert.deepEqual(subjects, ["PUBLIC_A", "PUBLIC_B"]);
});
test("captured read member is retained even if subject getter replaces reader member", async () => {
  const reader = { readSession: () => user() };
  const p = { get sub() { reader.readSession = forbidden as () => ReturnType<typeof user>; return "PUBLIC_SUBJECT"; }, sessionVersion: 7 };
  projected(await load(reader)(p), user());
});
