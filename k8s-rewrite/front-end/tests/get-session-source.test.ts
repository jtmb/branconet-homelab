import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

// PUBLIC inert metadata only. The dynamic import hook supplies a synthetic
// namespace containing one injected binding. No Next module or real cookie,
// credential, JWT verifier, account implementation or module initializer runs.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);
assert.equal(process.version, "v24.18.0");
assert.ok(process.execArgv.includes("--experimental-vm-modules"));
const raw = readFileSync(fileURLToPath(new URL("../src/lib/auth.ts", import.meta.url)), "utf8");
const source = raw.replaceAll("\r\n", "\n");
assert.ok(raw === source || raw === source.replaceAll("\n", "\r\n"));
assert.equal(createHash("sha256").update(source).digest("hex"), "932034e70f9d0447eb23c38ce91cb799413d289eb0a3bd25f3808c25865f2aff");
const ast = ts.createSourceFile("auth.ts", source, ts.ScriptTarget.Latest, true);
const declarations = ast.statements.filter((n: { name?: { text: string } }) => ts.isFunctionDeclaration(n) && n.name?.text === "getSession");
assert.equal(declarations.length, 1);
const declaration = declarations[0].getText(ast);
assert.equal(createHash("sha256").update(declaration).digest("hex"), "6cd70c711513cd394769ee0aa9b5fec47bdb3ead195c091dec8fc466d27ce8f9");
const javascript = ts.transpileModule(declaration.replace(/^export /, ""), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
assert.equal((javascript.match(/import\("next\/headers"\)/g) ?? []).length, 1);
assert.ok(!javascript.includes("require("));
type Stub = (...args: unknown[]) => unknown;
type Selected = (...args: unknown[]) => Promise<unknown>;
type Options = { cookies?: unknown; verify?: Stub; current?: Stub; onImport?: Stub; importGate?: Stub };
const cookieName = "botrus_auth_token";
const token = "PUBLIC_COOKIE_METADATA";
const payload = Object.freeze({ publicIdentity: "VERIFIER_METADATA" });
const session = Object.freeze({ publicIdentity: "ACCOUNT_METADATA" });
const forbiddenCalls: string[] = [];
const fail: Stub = () => { forbiddenCalls.push("unexpected synthetic callee"); throw new Error("unreachable synthetic binding"); };
test.afterEach(() => { assert.deepEqual(forbiddenCalls, []); });
function load(options: Options = {}): Selected {
  const context = vm.createContext({ AUTH_COOKIE: cookieName, verifyJWT: options.verify ?? fail, currentSession: options.current ?? fail });
  return vm.runInContext("(" + javascript + ")", context, {
    importModuleDynamically: async (specifier: string) => {
      assert.equal(specifier, "next/headers");
      options.onImport?.(specifier);
      await options.importGate?.();
      const binding = Object.hasOwn(options, "cookies") ? options.cookies : fail;
      const namespace = new vm.SyntheticModule(["cookies"], function () { this.setExport("cookies", binding); }, { context });
      await namespace.link(() => { throw new Error("synthetic module must have no imports"); });
      await namespace.evaluate();
      return namespace;
    },
  });
}
function deferred() {
  let resolve!: (value: unknown) => void;
  let reject!: (value: unknown) => void;
  const promise = new Promise<unknown>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const store = (...values: unknown[]) => ({ get: () => ({ value: values.length ? values[0] : token }) });
const successful = (extra: Options = {}) => load({ cookies: () => store(), verify: () => payload, current: () => session, ...extra });
const falsy = [["null", null], ["undefined", undefined], ["empty", ""], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["zero bigint", 0n]] as const;

test("pinned async zero-parameter declaration retains try/catch and ignored extra arguments", async () => {
  const selected = successful();
  assert.equal(selected.name, "getSession"); assert.equal(selected.length, 0);
  assert.equal(declarations[0].parameters.length, 0);
  assert.equal(declarations[0].body.statements.length, 1);
  assert.equal(await selected("PUBLIC_UNUSED"), session);
});
test("dynamic namespace, cookies call, store member/receiver/name, value, verifier and account order", async () => {
  const events: string[] = [];
  const publicStore = { get get() { events.push("get-member"); return function (this: unknown, ...args: unknown[]) {
    assert.equal(this, publicStore); assert.equal(args.length, 1); assert.equal(args[0], cookieName); events.push("get-call");
    return { get value() { events.push("value"); return token; } };
  }; } };
  const selected = load({ onImport: (...args) => { assert.equal(args.length, 1); events.push("import"); },
    cookies: function (this: unknown, ...args: unknown[]) { assert.equal(this, undefined); assert.equal(args.length, 0); events.push("cookies"); return publicStore; },
    verify: (...args) => { assert.equal(args.length, 1); assert.equal(args[0], token); events.push("verify"); return payload; },
    current: (...args) => { assert.equal(args.length, 1); assert.equal(args[0], payload); events.push("current"); return session; } });
  assert.equal(await selected(), session);
  assert.deepEqual(events, ["import", "cookies", "get-member", "get-call", "value", "verify", "current"]);
});
test("dynamic import hook synchronous fault returns null", async () => { assert.equal(await load({ onImport: () => { throw payload; } })(), null); });
test("dynamic import hook awaited rejection returns null", async () => { assert.equal(await load({ importGate: () => Promise.reject(payload) })(), null); });
for (const [name, value] of falsy) test("noncallable synthetic cookies binding refuses: " + name, async () => { assert.equal(await load({ cookies: value })(), null); });
test("cookies synchronous fault returns null", async () => { assert.equal(await load({ cookies: () => { throw payload; } })(), null); });
test("cookies awaited rejection returns null", async () => { assert.equal(await load({ cookies: () => Promise.reject(payload) })(), null); });
for (const [name, value] of falsy) test("invalid fulfilled store metadata returns null: " + name, async () => { assert.equal(await load({ cookies: () => value })(), null); });
test("store missing get member returns null", async () => { assert.equal(await load({ cookies: () => ({}) })(), null); });
test("store noncallable get member returns null", async () => { assert.equal(await load({ cookies: () => ({ get: payload }) })(), null); });
test("store get member fault returns null", async () => { assert.equal(await load({ cookies: () => ({ get get() { throw payload; } }) })(), null); });
test("store get call fault returns null", async () => { assert.equal(await load({ cookies: () => ({ get: () => { throw payload; } }) })(), null); });
for (const value of [null, undefined]) test("nullish get result skips value access: " + String(value), async () => { assert.equal(await load({ cookies: () => ({ get: () => value }) })(), null); });
test("get result is not awaited", async () => { assert.equal(await load({ cookies: () => ({ get: () => Promise.resolve({ value: token }) }) })(), null); });
test("value member fault returns null", async () => { assert.equal(await load({ cookies: () => ({ get: () => ({ get value() { throw payload; } }) }) })(), null); });
for (const [name, value] of falsy) test("falsy token metadata stops before verifier: " + name, async () => { assert.equal(await load({ cookies: () => store(value) })(), null); });
for (const value of [" PUBLIC ", "PUBLIC%20METADATA", "PUBLIC=METADATA", true, payload]) test("truthy token metadata forwards unchanged: " + String(value), async () => {
  assert.equal(await load({ cookies: () => store(value), verify: (...args) => { assert.equal(args.length, 1); assert.equal(args[0], value); return payload; }, current: () => session })(), session);
});
test("verifier synchronous fault returns null", async () => { assert.equal(await successful({ verify: () => { throw payload; } })(), null); });
test("verifier awaited rejection returns null", async () => { assert.equal(await successful({ verify: () => Promise.reject(payload) })(), null); });
for (const [name, value] of falsy) test("falsy verifier metadata stops before account lookup: " + name, async () => { assert.equal(await load({ cookies: () => store(), verify: () => value })(), null); });
for (const value of [payload, "PUBLIC_PAYLOAD", true, 1]) test("truthy verifier metadata identity forwards: " + String(value), async () => {
  assert.equal(await successful({ verify: () => value, current: (...args) => { assert.equal(args.length, 1); assert.equal(args[0], value); return session; } })(), session);
});
for (const [name, value] of [...falsy, ["session", session]] as const) test("fulfilled current result adopted unchanged: " + name, async () => { assert.equal(await successful({ current: () => value })(), value); });
test("current synchronous fault is caught inside declaration", async () => { assert.equal(await successful({ current: () => { throw session; } })(), null); });
test("current awaited rejection is caught inside declaration", async () => { assert.equal(await successful({ current: () => Promise.reject(session) })(), null); });
for (const stage of ["import", "cookies", "verify", "current"] as const) test("await fence prevents later work and premature settlement: " + stage, async () => {
  const gate = deferred(), entered = deferred(); let later = 0, settled = false;
  const waiting = () => { entered.resolve(true); return gate.promise; };
  const options: Options = { cookies: () => store(), verify: () => payload, current: () => session };
  if (stage === "import") { options.importGate = waiting; options.cookies = () => { later++; return store(); }; }
  if (stage === "cookies") { options.cookies = waiting; options.verify = () => { later++; return payload; }; }
  if (stage === "verify") { options.verify = waiting; options.current = () => { later++; return session; }; }
  if (stage === "current") options.current = waiting;
  const promise = load(options)(); void promise.then(() => { settled = true; });
  await entered.promise; assert.equal(later, 0); assert.equal(settled, false);
  gate.resolve(stage === "cookies" ? store() : stage === "verify" ? payload : stage === "current" ? session : undefined);
  assert.equal(await promise, session); assert.equal(later, stage === "current" ? 0 : 1);
});
test("fresh decisions reuse no cookie verifier or current-session result", async () => {
  let reads = 0, verifies = 0, currents = 0;
  const selected = load({ cookies: () => { reads++; return store(); }, verify: () => { verifies++; return payload; }, current: () => { currents++; return currents === 1 ? session : null; } });
  assert.equal(await selected(), session); assert.equal(await selected(), null);
  assert.deepEqual([reads, verifies, currents], [2, 2, 2]);
});
test("concurrent invocations keep independent awaited payloads and results", async () => {
  const a = deferred(), b = deferred(), entered = deferred(); let calls = 0;
  const second = Object.freeze({ publicIdentity: "SECOND_ACCOUNT_METADATA" });
  const selected = successful({ current: () => { calls++; if (calls === 2) entered.resolve(true); return calls === 1 ? a.promise : b.promise; } });
  const first = selected(), next = selected(); await entered.promise;
  b.resolve(second); assert.equal(await next, second); a.resolve(session); assert.equal(await first, session);
});
