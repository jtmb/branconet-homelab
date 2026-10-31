import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

// Only inert PUBLIC payload/account metadata and one lifted declaration execute.
// No original import, initializer, neighbouring function or reader executes.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);
assert.equal(process.version, "v24.18.0");
const raw = readFileSync(fileURLToPath(new URL("../src/lib/auth.ts", import.meta.url)), "utf8");
const source = raw.replaceAll("\r\n", "\n");
assert.ok(raw === source || raw === source.replaceAll("\n", "\r\n"));
assert.equal(createHash("sha256").update(source).digest("hex"), "932034e70f9d0447eb23c38ce91cb799413d289eb0a3bd25f3808c25865f2aff");
const ast = ts.createSourceFile("auth.ts", source, ts.ScriptTarget.Latest, true);
const declarations = ast.statements.filter((n: { name?: { text: string } }) => ts.isFunctionDeclaration(n) && n.name?.text === "currentAccount");
assert.equal(declarations.length, 1);
const declaration = declarations[0].getText(ast);
const expectedDeclaration = "async function currentAccount(payload: NonNullable<Awaited<ReturnType<typeof verifyJWT>>>): Promise<SessionAccount | null> {\n  const user = await directAccountReader.readAccount(payload.sub);\n  if (!user || user.sessionVersion !== payload.sessionVersion) return null;\n  return user;\n}";
assert.equal(declaration, expectedDeclaration);
const javascript = ts.transpileModule(declaration, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
assert.ok(!javascript.includes("import(") && !javascript.includes("require("));
type Selected = (...args: unknown[]) => Promise<unknown>;
type Stub = (...args: unknown[]) => unknown;
const forbiddenCalls: string[] = [];
const forbidden: Stub = () => { forbiddenCalls.push("unexpected injected reader"); throw new Error("unexpected injected reader"); };
test.afterEach(() => { assert.deepEqual(forbiddenCalls, []); });
function load(...readers: unknown[]): Selected {
  return vm.runInNewContext("(" + javascript + ")", { directAccountReader: readers.length ? readers[0] : { readAccount: forbidden } });
}
const payload = (version: unknown = 7) => ({ sub: "PUBLIC_SUBJECT", username: "PUBLIC_OLD_NAME", sessionVersion: version });
const account = (version: unknown = 7) => ({ id: "PUBLIC_ID", username: "PUBLIC_CURRENT_NAME", sessionVersion: version, role: "readonly", engineAdmin: false });
function deferred() {
  let resolve!: (value: unknown) => void; let reject!: (value: unknown) => void;
  const promise = new Promise<unknown>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

test("one async declaration returns the identical account including authorization metadata", async () => {
  const u = account(); const selected = load({ readAccount: () => u });
  assert.equal(selected.name, "currentAccount"); assert.equal(selected.length, 1);
  assert.equal(declarations[0].parameters.length, 1); assert.equal(declarations[0].body.statements.length, 3);
  assert.equal(await selected(payload()), u); assert.equal(await selected(payload(), "PUBLIC_UNUSED"), u);
});
test("capture member then subject then call; exact receiver and argument; ordered version reads only", async () => {
  const events: string[] = []; const subject = Object.freeze({ publicSubject: true });
  const u = { get sessionVersion() { events.push("user-version"); return 7; }, get role() { forbiddenCalls.push("role-read"); throw new Error("unused"); }, get engineAdmin() { forbiddenCalls.push("admin-read"); throw new Error("unused"); } };
  const p = { get sub() { events.push("subject"); return subject; }, get sessionVersion() { events.push("payload-version"); return 7; }, get username() { forbiddenCalls.push("payload-name"); throw new Error("unused"); } };
  const reader = { get readAccount() { events.push("member"); return function (this: unknown, ...args: unknown[]) { assert.equal(this, reader); assert.equal(args.length, 1); assert.equal(args[0], subject); events.push("call"); return u; }; } };
  assert.equal(await load(reader)(p), u); assert.deepEqual(events, ["member", "subject", "call", "user-version", "payload-version"]);
});
for (const [name, value] of [["null", null], ["undefined", undefined], ["empty", ""], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["zero bigint", 0n]] as const) test("falsy awaited account refuses before payload version: " + name, async () => {
  const p = { sub: "PUBLIC_SUBJECT", get sessionVersion() { forbiddenCalls.push("version-after-falsy"); throw new Error("unused"); } };
  assert.equal(await load({ readAccount: () => value })(p), null);
});
for (const [name, value] of [["string", "7"], ["other", 8], ["missing", undefined], ["null", null], ["boolean", true], ["bigint", 7n], ["NaN", NaN], ["object", {}]] as const) test("strict unequal account version returns null: " + name, async () => {
  const u = { sessionVersion: value, get role() { forbiddenCalls.push("role-on-refusal"); throw new Error("unused"); } };
  assert.equal(await load({ readAccount: () => u })(payload()), null);
});
for (const [name, version] of [["number", 7], ["zero", 0], ["string metadata", "PUBLIC_VERSION"], ["undefined metadata", undefined], ["null metadata", null], ["boolean metadata", false], ["bigint metadata", 3n], ["object identity metadata", {}]] as const) test("equal inert versions return account identity without extra validation: " + name, async () => {
  const u = { sessionVersion: version, role: "PUBLIC_ROLE", engineAdmin: "PUBLIC_FLAG" };
  assert.equal(await load({ readAccount: () => u })({ sub: "PUBLIC_SUBJECT", sessionVersion: version }), u);
});
test("positive and negative zero compare equal", async () => { const u = account(-0); assert.equal(await load({ readAccount: () => u })(payload(0)), u); });
test("two NaN versions refuse", async () => { assert.equal(await load({ readAccount: () => account(NaN) })(payload(NaN)), null); });
for (const [name, subject] of [["undefined", undefined], ["null", null], ["empty", ""], ["number", 3], ["object", {}]] as const) test("subject is forwarded unchanged once: " + name, async () => {
  let calls = 0; const u = account();
  const selected = load({ readAccount: (...args: unknown[]) => { calls++; assert.equal(args.length, 1); assert.equal(args[0], subject); return u; } });
  assert.equal(await selected({ sub: subject, sessionVersion: 7 }), u); assert.equal(calls, 1);
});
for (const [name, reader] of [["null", null], ["undefined", undefined], ["missing member", {}], ["noncallable", { readAccount: 1 }]] as const) test("invalid inert reader rejects: " + name, async () => { await assert.rejects(load(reader)(payload()), { name: "TypeError" }); });
for (const [name, p] of [["null", null], ["undefined", undefined]] as const) test("invalid payload rejects without reader call: " + name, async () => { await assert.rejects(load()(p), { name: "TypeError" }); });
test("member getter fault occurs before subject and retains exact rejection", async () => {
  const fault = Object.freeze({ publicFault: "MEMBER" });
  await assert.rejects(load({ get readAccount() { throw fault; } })({ get sub() { forbiddenCalls.push("late-subject"); throw new Error("unused"); } }), (e: unknown) => e === fault);
});
test("subject getter fault prevents captured reader invocation", async () => {
  const fault = Object.freeze({ publicFault: "SUBJECT" });
  await assert.rejects(load({ readAccount: forbidden })({ get sub() { throw fault; } }), (e: unknown) => e === fault);
});
for (const asynchronous of [false, true]) test("reader fault propagates with exact identity; asynchronous=" + asynchronous, async () => {
  const fault = Object.freeze({ publicFault: "READER" });
  await assert.rejects(load({ readAccount: () => { if (asynchronous) return Promise.reject(fault); throw fault; } })(payload()), (e: unknown) => e === fault);
});
for (const position of ["account-version", "payload-version"] as const) test("version getter fault stops later reads: " + position, async () => {
  const events: string[] = []; const fault = Object.freeze({ publicFault: position });
  const read = (name: string) => { events.push(name); if (name === position) throw fault; return 7; };
  await assert.rejects(load({ readAccount: () => ({ get sessionVersion() { return read("account-version"); } }) })({ sub: "PUBLIC_SUBJECT", get sessionVersion() { return read("payload-version"); } }), (e: unknown) => e === fault);
  assert.deepEqual(events, position === "account-version" ? ["account-version"] : ["account-version", "payload-version"]);
});
test("pending reader prevents all version checks until fulfillment", async () => {
  const gate = deferred(); const events: string[] = []; const u = account(); let settled = false;
  const pending = load({ readAccount: () => { events.push("call"); return gate.promise; } })({ sub: "PUBLIC_SUBJECT", get sessionVersion() { events.push("version"); return 7; } });
  void pending.then(() => { settled = true; }); await Promise.resolve(); assert.deepEqual(events, ["call"]); assert.equal(settled, false);
  gate.resolve(u); assert.equal(await pending, u); assert.deepEqual(events, ["call", "version"]);
});
test("pending reader rejection preserves exact reason and skips version", async () => {
  const gate = deferred(); const fault = Object.freeze({ publicFault: "PENDING" });
  const pending = load({ readAccount: () => gate.promise })({ sub: "PUBLIC_SUBJECT", get sessionVersion() { forbiddenCalls.push("version-after-reject"); throw new Error("unused"); } });
  const rejected = assert.rejects(pending, (e: unknown) => e === fault); gate.reject(fault); await rejected;
});
test("custom reader thenable is assimilated once before comparison", async () => {
  let calls = 0; const u = account();
  assert.equal(await load({ readAccount: () => ({ then(resolve: (v: unknown) => void) { calls++; resolve(u); } }) })(payload()), u); assert.equal(calls, 1);
});
test("reader then getter fault propagates before comparison", async () => {
  const fault = Object.freeze({ publicFault: "AWAIT_THEN" });
  await assert.rejects(load({ readAccount: () => ({ get then() { throw fault; } }) })(payload()), (e: unknown) => e === fault);
});
test("account version is read once; return does not project or reread fields", async () => {
  let reads = 0; const u = { get sessionVersion() { reads++; return reads === 1 ? 7 : 9; }, get id() { forbiddenCalls.push("id"); throw new Error("unused"); }, get username() { forbiddenCalls.push("username"); throw new Error("unused"); } };
  assert.equal(await load({ readAccount: () => u })(payload()), u); assert.equal(reads, 1);
});
test("authorization metadata is preserved by reference without role/admin access", async () => {
  const u = { sessionVersion: 7, get role() { forbiddenCalls.push("role"); throw new Error("unused"); }, get engineAdmin() { forbiddenCalls.push("engineAdmin"); throw new Error("unused"); } };
  assert.equal(await load({ readAccount: () => u })(payload()), u);
});
test("fresh calls re-read and observe allow/refuse/allow without account cache", async () => {
  const first = account(); const last = account(8); const values = [first, null, last]; let calls = 0;
  const selected = load({ readAccount: () => values[calls++] });
  assert.equal(await selected(payload()), first); assert.equal(await selected(payload()), null); assert.equal(await selected(payload(8)), last); assert.equal(calls, 3);
});
test("concurrent decisions keep separate payloads and out-of-order results", async () => {
  const a = deferred(); const b = deferred(); const subjects: unknown[] = []; const u = account();
  const selected = load({ readAccount: (sub: unknown) => { subjects.push(sub); return sub === "PUBLIC_A" ? a.promise : b.promise; } });
  const pa = selected({ sub: "PUBLIC_A", sessionVersion: 7 }); const pb = selected({ sub: "PUBLIC_B", sessionVersion: 8 });
  b.resolve(account(7)); assert.equal(await pb, null); a.resolve(u); assert.equal(await pa, u); assert.deepEqual(subjects, ["PUBLIC_A", "PUBLIC_B"]);
});
test("subject getter replacement cannot replace already captured reader member", async () => {
  const u = account(); const reader = { readAccount: () => u };
  const p = { get sub() { reader.readAccount = forbidden as () => ReturnType<typeof account>; return "PUBLIC_SUBJECT"; }, sessionVersion: 7 };
  assert.equal(await load(reader)(p), u);
});
test("payload version is read after pending account fulfills", async () => {
  const gate = deferred(); const p = payload(6); const u = account();
  const pending = load({ readAccount: () => gate.promise })(p); p.sessionVersion = 7; gate.resolve(u); assert.equal(await pending, u);
});
test("thenable repeated settlement cannot replace first fulfilled account", async () => {
  const first = account(); const later = account(8);
  const result = await load({ readAccount: () => ({ then(resolve: (v: unknown) => void, reject: (e: unknown) => void) { resolve(first); resolve(later); reject("PUBLIC_LATE"); } }) })(payload());
  assert.equal(result, first);
});
test("return Promise adoption reads then again after successful version decision", async () => {
  const events: string[] = []; let reads = 0;
  const u = { get then() { events.push("then" + ++reads); return undefined; }, get sessionVersion() { events.push("version"); return 7; } };
  let result: unknown;
  await load({ readAccount: () => u })(payload()).then(value => { result = value; });
  assert.equal(result, u); assert.deepEqual(events, ["then1", "version", "then2"]);
});
test("return adoption then-getter fault rejects after otherwise matching metadata", async () => {
  let reads = 0; const fault = Object.freeze({ publicFault: "RETURN_THEN" });
  const u = { sessionVersion: 7, get then() { if (++reads === 2) throw fault; return undefined; } };
  await assert.rejects(load({ readAccount: () => u })(payload()), (e: unknown) => e === fault); assert.equal(reads, 2);
});
test("mismatch skips return-adoption then access", async () => {
  let reads = 0; const u = { sessionVersion: 8, get then() { if (++reads > 1) { forbiddenCalls.push("then-after-refusal"); throw new Error("unused"); } return undefined; } };
  assert.equal(await load({ readAccount: () => u })(payload()), null); assert.equal(reads, 1);
});
test("return adoption follows synthetic thenable acquired only after comparison", async () => {
  let reads = 0; const adopted = Object.freeze({ publicResult: "ADOPTED" });
  const u = { sessionVersion: 7, get then() { return ++reads === 1 ? undefined : (resolve: (v: unknown) => void) => resolve(adopted); } };
  assert.equal(await load({ readAccount: () => u })(payload()), adopted); assert.equal(reads, 2);
});
