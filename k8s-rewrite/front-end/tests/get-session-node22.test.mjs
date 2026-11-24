import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import vm from 'node:vm';

// Distinct PUBLIC selected-declaration controls; historical74 remain frozen.
// Module/imports/initializers/neighbours/Kubernetes/HTTP/backend/recovery stay inert.
assert.equal(process.version, 'v22.23.3');
const ts = createRequire(import.meta.url)('typescript');
assert.equal(ts.version, '5.9.3');
const digest = value => createHash('sha256').update(value).digest('hex');
const raw = readFileSync(new URL('../src/lib/auth.ts', import.meta.url), 'utf8');
const source = raw.replaceAll('\r\n', '\n');
assert.ok(raw === source || raw === source.replaceAll('\n', '\r\n'));
assert.equal(digest(source), '932034e70f9d0447eb23c38ce91cb799413d289eb0a3bd25f3808c25865f2aff');
assert.equal(digest(source.replaceAll('\n', '\r\n')), 'f190c4ba27ee2069a799ed9aa5cd37e6a69ebba70bcd05f927c3ad8eeecdc7d8');
const ast = ts.createSourceFile('auth.ts', source, ts.ScriptTarget.Latest, true);
assert.equal(ast.parseDiagnostics.length, 0);
const declarations = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'getSession');
assert.equal(declarations.length, 1);
const node = declarations[0];
assert.deepEqual(node.modifiers.map(node => node.kind), [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword]);
assert.deepEqual(node.parameters.map(node => node.getText(ast)), []);
const declaration = node.getText(ast);
assert.equal(declaration, "export async function getSession(): Promise<Session | null> {\n  try {\n    const { cookies } = await import(\"next/headers\");\n    const cookieStore = await cookies();\n    const token = cookieStore.get(AUTH_COOKIE)?.value;\n    if (!token) return null;\n    const payload = await verifyJWT(token);\n    if (!payload) return null;\n    return await currentSession(payload);\n  } catch {\n    return null;\n  }\n}");
assert.equal(digest(declaration), '6cd70c711513cd394769ee0aa9b5fec47bdb3ead195c091dec8fc466d27ce8f9');
assert.equal(digest(declaration.replaceAll('\n', '\r\n')), '0e6fe908caa03705097f6d72407d12ab1b2d8ce33e5d85f9a4fbb013fed46d37');
const selected = declaration.replace(/^export\s+/, '');
const compiled = ts.transpileModule(selected, { reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
assert.equal(compiled.diagnostics.length, 0);
const javascript = compiled.outputText.trim();
assert.equal((javascript.match(/import\("next\/headers"\)/g) ?? []).length, 1);
assert.ok(!javascript.includes('require('));
assert.ok(process.execArgv.includes('--experimental-vm-modules'));
let count = 0;
const control = (...args) => { count++; return test(...args); };
const cookieName = "botrus_auth_token";
const token = "PUBLIC_COOKIE_METADATA";
const payload = Object.freeze({ publicIdentity: "VERIFIER_METADATA" });
const session = Object.freeze({ publicIdentity: "ACCOUNT_METADATA" });
const forbiddenCalls = [];
const fail = () => { forbiddenCalls.push("unexpected synthetic callee"); throw new Error("unreachable synthetic binding"); };
test.afterEach(() => { assert.deepEqual(forbiddenCalls, []); });
function load(options = {}) {
    const context = vm.createContext({ AUTH_COOKIE: cookieName, verifyJWT: options.verify ?? fail, currentSession: options.current ?? fail });
    return vm.runInContext("(" + javascript + ")", context, {
        importModuleDynamically: async (specifier) => {
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
    let resolve;
    let reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
}
const store = (...values) => ({ get: () => ({ value: values.length ? values[0] : token }) });
const successful = (extra = {}) => load({ cookies: () => store(), verify: () => payload, current: () => session, ...extra });
const falsy = [["null", null], ["undefined", undefined], ["empty", ""], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["zero bigint", 0n]];
control("pinned async zero-parameter declaration retains try/catch and ignored extra arguments", async () => {
    const selected = successful();
    assert.equal(selected.name, "getSession");
    assert.equal(selected.length, 0);
    assert.equal(declarations[0].parameters.length, 0);
    assert.equal(declarations[0].body.statements.length, 1);
    assert.equal(await selected("PUBLIC_UNUSED"), session);
});
control("dynamic namespace, cookies call, store member/receiver/name, value, verifier and account order", async () => {
    const events = [];
    const publicStore = { get get() {
            events.push("get-member");
            return function (...args) {
                assert.equal(this, publicStore);
                assert.equal(args.length, 1);
                assert.equal(args[0], cookieName);
                events.push("get-call");
                return { get value() { events.push("value"); return token; } };
            };
        } };
    const selected = load({ onImport: (...args) => { assert.equal(args.length, 1); events.push("import"); },
        cookies: function (...args) { assert.equal(this, undefined); assert.equal(args.length, 0); events.push("cookies"); return publicStore; },
        verify: (...args) => { assert.equal(args.length, 1); assert.equal(args[0], token); events.push("verify"); return payload; },
        current: (...args) => { assert.equal(args.length, 1); assert.equal(args[0], payload); events.push("current"); return session; } });
    assert.equal(await selected(), session);
    assert.deepEqual(events, ["import", "cookies", "get-member", "get-call", "value", "verify", "current"]);
});
control("dynamic import hook synchronous fault returns null", async () => { assert.equal(await load({ onImport: () => { throw payload; } })(), null); });
control("dynamic import hook awaited rejection returns null", async () => { assert.equal(await load({ importGate: () => Promise.reject(payload) })(), null); });
for (const [name, value] of falsy)
    control("noncallable synthetic cookies binding refuses: " + name, async () => { assert.equal(await load({ cookies: value })(), null); });
control("cookies synchronous fault returns null", async () => { assert.equal(await load({ cookies: () => { throw payload; } })(), null); });
control("cookies awaited rejection returns null", async () => { assert.equal(await load({ cookies: () => Promise.reject(payload) })(), null); });
for (const [name, value] of falsy)
    control("invalid fulfilled store metadata returns null: " + name, async () => { assert.equal(await load({ cookies: () => value })(), null); });
control("store missing get member returns null", async () => { assert.equal(await load({ cookies: () => ({}) })(), null); });
control("store noncallable get member returns null", async () => { assert.equal(await load({ cookies: () => ({ get: payload }) })(), null); });
control("store get member fault returns null", async () => { assert.equal(await load({ cookies: () => ({ get get() { throw payload; } }) })(), null); });
control("store get call fault returns null", async () => { assert.equal(await load({ cookies: () => ({ get: () => { throw payload; } }) })(), null); });
for (const value of [null, undefined])
    control("nullish get result skips value access: " + String(value), async () => { assert.equal(await load({ cookies: () => ({ get: () => value }) })(), null); });
control("get result is not awaited", async () => { assert.equal(await load({ cookies: () => ({ get: () => Promise.resolve({ value: token }) }) })(), null); });
control("value member fault returns null", async () => { assert.equal(await load({ cookies: () => ({ get: () => ({ get value() { throw payload; } }) }) })(), null); });
for (const [name, value] of falsy)
    control("falsy token metadata stops before verifier: " + name, async () => { assert.equal(await load({ cookies: () => store(value) })(), null); });
for (const value of [" PUBLIC ", "PUBLIC%20METADATA", "PUBLIC=METADATA", true, payload])
    control("truthy token metadata forwards unchanged: " + String(value), async () => {
        assert.equal(await load({ cookies: () => store(value), verify: (...args) => { assert.equal(args.length, 1); assert.equal(args[0], value); return payload; }, current: () => session })(), session);
    });
control("verifier synchronous fault returns null", async () => { assert.equal(await successful({ verify: () => { throw payload; } })(), null); });
control("verifier awaited rejection returns null", async () => { assert.equal(await successful({ verify: () => Promise.reject(payload) })(), null); });
for (const [name, value] of falsy)
    control("falsy verifier metadata stops before account lookup: " + name, async () => { assert.equal(await load({ cookies: () => store(), verify: () => value })(), null); });
for (const value of [payload, "PUBLIC_PAYLOAD", true, 1])
    control("truthy verifier metadata identity forwards: " + String(value), async () => {
        assert.equal(await successful({ verify: () => value, current: (...args) => { assert.equal(args.length, 1); assert.equal(args[0], value); return session; } })(), session);
    });
for (const [name, value] of [...falsy, ["session", session]])
    control("fulfilled current result adopted unchanged: " + name, async () => { assert.equal(await successful({ current: () => value })(), value); });
control("current synchronous fault is caught inside declaration", async () => { assert.equal(await successful({ current: () => { throw session; } })(), null); });
control("current awaited rejection is caught inside declaration", async () => { assert.equal(await successful({ current: () => Promise.reject(session) })(), null); });
for (const stage of ["import", "cookies", "verify", "current"])
    control("await fence prevents later work and premature settlement: " + stage, async () => {
        const gate = deferred(), entered = deferred();
        let later = 0, settled = false;
        const waiting = () => { entered.resolve(true); return gate.promise; };
        const options = { cookies: () => store(), verify: () => payload, current: () => session };
        if (stage === "import") {
            options.importGate = waiting;
            options.cookies = () => { later++; return store(); };
        }
        if (stage === "cookies") {
            options.cookies = waiting;
            options.verify = () => { later++; return payload; };
        }
        if (stage === "verify") {
            options.verify = waiting;
            options.current = () => { later++; return session; };
        }
        if (stage === "current")
            options.current = waiting;
        const promise = load(options)();
        void promise.then(() => { settled = true; });
        await entered.promise;
        assert.equal(later, 0);
        assert.equal(settled, false);
        gate.resolve(stage === "cookies" ? store() : stage === "verify" ? payload : stage === "current" ? session : undefined);
        assert.equal(await promise, session);
        assert.equal(later, stage === "current" ? 0 : 1);
    });
control("fresh decisions reuse no cookie verifier or current-session result", async () => {
    let reads = 0, verifies = 0, currents = 0;
    const selected = load({ cookies: () => { reads++; return store(); }, verify: () => { verifies++; return payload; }, current: () => { currents++; return currents === 1 ? session : null; } });
    assert.equal(await selected(), session);
    assert.equal(await selected(), null);
    assert.deepEqual([reads, verifies, currents], [2, 2, 2]);
});
control("concurrent invocations keep independent awaited payloads and results", async () => {
    const a = deferred(), b = deferred(), entered = deferred();
    let calls = 0;
    const second = Object.freeze({ publicIdentity: "SECOND_ACCOUNT_METADATA" });
    const selected = successful({ current: () => { calls++; if (calls === 2)
            entered.resolve(true); return calls === 1 ? a.promise : b.promise; } });
    const first = selected(), next = selected();
    await entered.promise;
    b.resolve(second);
    assert.equal(await next, second);
    a.resolve(session);
    assert.equal(await first, session);
});
assert.equal(count, 74);
