import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

// PUBLIC SOURCE only. Every dependency/account below is inert synthetic metadata.
// Never import the original module or execute real session/account/ORM operations.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);
assert.equal(process.version, "v24.18.0");
const raw = readFileSync(fileURLToPath(new URL("../src/lib/permissions.ts", import.meta.url)), "utf8");
const source = raw.replaceAll("\r\n", "\n");
assert.ok(raw === source || raw === source.replaceAll("\n", "\r\n"));
assert.equal(createHash("sha256").update(source).digest("hex"), "c894d04fa4cbcfaa09e97f1248100b671b29927b13950a4e964b0135a994b704");
const ast = ts.createSourceFile("permissions.ts", source, ts.ScriptTarget.Latest, true);
const declarations = ast.statements.filter((n: { name?: { text: string } }) => ts.isFunctionDeclaration(n) && n.name?.text === "getCurrentRole");
assert.equal(declarations.length, 1);
const expected = 'export async function getCurrentRole(): Promise<"readonly" | "write" | null> {\n  const session = await getSession();\n  if (!session) return null;\n\n  const user = await prisma.user.findUnique({\n    where: { id: session.id },\n    select: { role: true },\n  });\n\n  return user?.role === "readonly" || user?.role === "write" ? user.role : null;\n}';
assert.equal(declarations[0].getText(ast), expected);
const javascript = ts.transpileModule(expected.replace(/^export /, ""), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
assert.ok(!/\b(?:import|require)\s*\(/.test(javascript));
type Stub = (...args: unknown[]) => unknown;
type Selected = (...args: unknown[]) => Promise<unknown>;
type Query = { where: { id: unknown }; select: { role: true } };
const marker = Object.freeze({ publicMetadata: true });
const same = (fault: unknown) => (actual: unknown) => actual === fault;
const typeError = (actual: unknown) => (actual as { name?: string })?.name === "TypeError";
function load(dependency: unknown, store: unknown): Selected {
  const factory = vm.runInNewContext('(function (getSession, prisma) { "use strict"; return (' + javascript + '); })', {});
  return factory(dependency, store);
}
function model(session: unknown = { id: marker }, output: unknown = { role: "write" }) {
  const calls: Query[] = []; let sessionCalls = 0;
  const user = { findUnique(this: unknown, ...args: unknown[]) {
    assert.equal(this, user); assert.equal(args.length, 1);
    const q = args[0] as Query; calls.push(q);
    assert.deepEqual(Object.keys(q), ["where", "select"]);
    assert.deepEqual(Object.keys(q.where), ["id"]); assert.deepEqual(Object.keys(q.select), ["role"]);
    assert.equal(q.select.role, true); return output;
  } };
  const dependency = function (this: unknown, ...args: unknown[]) { assert.equal(this, undefined); assert.equal(args.length, 0); sessionCalls++; return session; };
  return { selected: load(dependency, { user }), calls, count: () => sessionCalls };
}
function deferred() {
  let resolve!: (value: unknown) => void; let reject!: (reason: unknown) => void;
  const promise = new Promise<unknown>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

test("exact zero-parameter declaration, detached dependency and one scoped argument", async () => {
  const m = model(); assert.equal(m.selected.name, "getCurrentRole"); assert.equal(m.selected.length, 0); assert.equal(declarations[0].parameters.length, 0);
  assert.equal(await m.selected("ignored"), "write"); assert.equal(m.count(), 1); assert.equal(m.calls.length, 1); assert.equal(m.calls[0].where.id, marker);
});
for (const [name, session] of [["undefined", undefined], ["null", null], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["empty string", ""], ["zero bigint", 0n]] as const) test("falsy session skips store: " + name, async () => {
  assert.equal(await load(() => session, new Proxy({}, { get() { assert.fail("store reached"); } }))(), null);
});
for (const [name, session] of [["empty object", {}], ["true", true], ["number", 4], ["negative", -1], ["infinity", Infinity], ["string", "PUBLIC"], ["bigint", 3n], ["symbol", Symbol("PUBLIC")], ["array", []], ["function", function () {}]] as const) test("truthy metadata session uses absent id unchanged: " + name, async () => {
  const m = model(session); assert.equal(await m.selected(), "write"); assert.equal(m.calls[0].where.id, undefined);
});
for (const [name, id] of [["undefined", undefined], ["null", null], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["empty", ""], ["string", "PUBLIC"], ["bigint", 2n], ["symbol", Symbol("PUBLIC")], ["object", marker], ["array", []]] as const) test("id identity without coercion: " + name, async () => {
  const m = model({ id }); assert.equal(await m.selected(), "write"); assert.ok(Object.is(m.calls[0].where.id, id));
});
for (const role of ["readonly", "write"]) test("exact accepted role metadata: " + role, async () => { assert.equal(await model({ id: marker }, { role }).selected(), role); });
for (const [name, role] of [["missing", undefined], ["null", null], ["false", false], ["true", true], ["zero", 0], ["number", 1], ["empty", ""], ["case", "Write"], ["space", "write "], ["prefix", "readonly-extra"], ["object", marker], ["boxed", Object("write")], ["array", ["write"]], ["symbol", Symbol("write")], ["bigint", 1n]] as const) test("strict role comparison refuses metadata: " + name, async () => { assert.equal(await model({ id: marker }, { role }).selected(), null); });
for (const [name, output] of [["undefined", undefined], ["null", null], ["false", false], ["zero", 0], ["NaN", NaN], ["empty", ""], ["bigint", 0n]] as const) test("nullish optional and nonnullish primitive account: " + name, async () => {
  assert.equal(await load(() => ({ id: marker }), { user: { findUnique: () => output } })(), null);
});
test("source-derived member, argument and receiver evaluation order", async () => {
  const events: string[] = []; let roleReads = 0;
  const output = { get role() { events.push("role" + ++roleReads); return "write"; } };
  const session = { get id() { events.push("id"); return marker; } };
  const user = { get findUnique() { events.push("method:get"); return function (this: unknown, ...args: unknown[]) { events.push("method:call"); assert.equal(this, user); assert.equal(args.length, 1); assert.equal((args[0] as Query).where.id, marker); return output; }; } };
  const store = { get user() { events.push("user:get"); return user; } };
  const selected = load(() => { events.push("session:call"); return session; }, store);
  const pending = selected(); assert.deepEqual(events, ["session:call"]);
  assert.equal(await pending, "write"); assert.deepEqual(events, ["session:call", "user:get", "method:get", "id", "method:call", "role1", "role2", "role3"]);
});
test("readonly short circuit reads role twice and does not revalidate final value", async () => {
  let reads = 0; const m = model({ id: marker }, { get role() { return ++reads === 1 ? "readonly" : marker; } });
  assert.equal(await m.selected(), marker); assert.equal(reads, 2);
});
test("write second comparison and third final read remain independent", async () => {
  let reads = 0; const values = ["other", "write", marker]; const m = model({ id: marker }, { get role() { return values[reads++]; } });
  assert.equal(await m.selected(), marker); assert.equal(reads, 3);
});
test("readonly on second comparison does not satisfy the write predicate", async () => {
  let reads = 0; assert.equal(await model({ id: marker }, { get role() { return ++reads === 1 ? "other" : "readonly"; } }).selected(), null); assert.equal(reads, 2);
});
test("truthy role object is never coerced", async () => {
  const role = { [Symbol.toPrimitive]() { assert.fail("coercion"); } }; assert.equal(await model({ id: marker }, { role }).selected(), null);
});
test("inherited role metadata is read", async () => { assert.equal(await model({ id: marker }, Object.create({ role: "readonly" })).selected(), "readonly"); });
test("unrelated metadata accessors remain untouched", async () => {
  const m = model({ id: marker, get unused() { return assert.fail("session unused"); } }, { role: "write", get password() { return assert.fail("unselected metadata"); } });
  assert.equal(await m.selected(), "write");
});
test("query and both nested objects are fresh for every call", async () => {
  const m = model(); await m.selected(); await m.selected(); assert.equal(m.count(), 2);
  for (const key of ["where", "select"] as const) assert.notEqual(m.calls[0][key], m.calls[1][key]); assert.notEqual(m.calls[0], m.calls[1]);
});
test("method capture precedes id and retains receiver after property replacement", async () => {
  const user: { findUnique: Stub } = { findUnique: function (this: unknown) { assert.equal(this, user); return { role: "write" }; } };
  const session = { get id() { user.findUnique = () => { assert.fail("replacement called"); }; return marker; } };
  assert.equal(await load(() => session, { user })(), "write");
});
test("id read once and never from query metadata again", async () => {
  let reads = 0; const m = model({ get id() { reads++; return marker; } }); assert.equal(await m.selected(), "write"); assert.equal(reads, 1);
});
for (const site of ["session throw", "session reject", "user getter", "method getter", "id getter", "method throw", "method reject"] as const) test("fault identity propagates without retry: " + site, async () => {
  const fault = Object.freeze({ publicFault: site }); let calls = 0;
  const dependency = () => { calls++; if (site === "session throw") throw fault; if (site === "session reject") return Promise.reject(fault); return { get id() { if (site === "id getter") throw fault; return marker; } }; };
  const store = { get user() { if (site === "user getter") throw fault; return { get findUnique() { if (site === "method getter") throw fault; return () => { if (site === "method throw") throw fault; if (site === "method reject") return Promise.reject(fault); assert.fail("unexpected path"); }; } }; } };
  await assert.rejects(load(dependency, store)(), same(fault)); assert.equal(calls, 1);
});
for (const nth of [1, 2, 3]) test("role accessor fault identity on read " + nth, async () => {
  const fault = { publicFaultRead: nth }; let reads = 0;
  const output = { get role() { if (++reads === nth) throw fault; return reads === 1 ? "other" : "write"; } };
  await assert.rejects(model({ id: marker }, output).selected(), same(fault)); assert.equal(reads, nth);
});
for (const dependency of [undefined, null, false, 4, {}]) test("noncallable session dependency refuses: " + String(dependency), async () => { await assert.rejects(load(dependency, {})(), typeError); });
for (const method of [undefined, null, false, 4, {}]) test("noncallable method refuses after evaluating argument: " + String(method), async () => {
  let reads = 0; await assert.rejects(load(() => ({ get id() { reads++; return marker; } }), { user: { findUnique: method } })(), typeError); assert.equal(reads, 1);
});
for (const [i, store] of [null, undefined, { user: null }, { user: undefined }].entries()) test("missing store path refuses without id access: " + i, async () => {
  await assert.rejects(load(() => ({ get id() { return assert.fail("id reached"); } }), store)(), typeError);
});
test("session await fences all store evaluation", async () => {
  const gate = deferred(); let reached = false; const selected = load(() => gate.promise, { get user() { reached = true; return { findUnique: () => ({ role: "write" }) }; } });
  const p = selected(); await Promise.resolve(); assert.equal(reached, false); gate.resolve({ id: marker }); assert.equal(await p, "write"); assert.equal(reached, true);
});
test("account await fences role reads", async () => {
  const gate = deferred(); let reads = 0; const selected = load(() => ({ id: marker }), { user: { findUnique: () => gate.promise } });
  const p = selected(); await Promise.resolve(); assert.equal(reads, 0); gate.resolve({ get role() { reads++; return "readonly"; } }); assert.equal(await p, "readonly"); assert.equal(reads, 2);
});
for (const stage of ["session", "account", "final role"] as const) test("thenable getter fault propagation: " + stage, async () => {
  const fault = { publicThenableFault: stage }; const bad = { get then() { throw fault; } };
  let reads = 0; const selected = load(() => stage === "session" ? bad : { id: marker }, { user: { findUnique: () => stage === "account" ? bad : { get role() { return ++reads === 1 ? "readonly" : bad; } } } });
  await assert.rejects(selected(), same(fault));
});
test("final role thenable is adopted after successful comparison", async () => {
  let reads = 0; const thenable = { then(resolve: Stub) { resolve(marker); } };
  assert.equal(await model({ id: marker }, { get role() { return ++reads === 1 ? "readonly" : thenable; } }).selected(), marker); assert.equal(reads, 2);
});
test("session and account thenables preserve await settlement", async () => {
  const thenable = (value: unknown) => ({ then(resolve: Stub) { resolve(value); } });
  assert.equal(await load(() => thenable({ id: marker }), { user: { findUnique: () => thenable({ role: "write" }) } })(), "write");
});
test("fresh dependency lookup repeats and role changes are not cached", async () => {
  let n = 0; const selected = load(() => ({ id: marker }), { get user() { return { findUnique: () => ({ role: ++n === 1 ? "write" : "readonly" }) }; } });
  assert.equal(await selected(), "write"); assert.equal(await selected(), "readonly"); assert.equal(n, 2);
});
test("concurrent pending sessions and accounts remain isolated", async () => {
  const sessions = [deferred(), deferred()]; const rows = [deferred(), deferred()]; let calls = 0; const ids: unknown[] = [];
  const selected = load(() => sessions[calls++].promise, { user: { findUnique: (q: Query) => { ids.push(q.where.id); return rows[q.where.id === "A" ? 0 : 1].promise; } } });
  const a = selected(); const b = selected(); assert.notEqual(a, b); sessions[1].resolve({ id: "B" }); await Promise.resolve(); sessions[0].resolve({ id: "A" }); await Promise.resolve();
  rows[0].resolve({ role: "readonly" }); rows[1].resolve({ role: "write" }); assert.equal(await a, "readonly"); assert.equal(await b, "write"); assert.deepEqual(ids, ["B", "A"]);
});
test("revoked synthetic proxy fails before retry", async () => {
  const { proxy, revoke } = Proxy.revocable({}, {}); revoke(); await assert.rejects(load(() => ({ id: marker }), proxy)(), typeError);
});
