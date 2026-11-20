import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import vm from 'node:vm';

// Distinct PUBLIC selected-declaration controls; historical85 remain frozen.
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
const declarations = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'getSessionAccount');
assert.equal(declarations.length, 1);
const node = declarations[0];
assert.deepEqual(node.modifiers.map(node => node.kind), [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword]);
assert.deepEqual(node.parameters.map(node => node.getText(ast)), []);
const declaration = node.getText(ast);
assert.equal(declaration, "export async function getSessionAccount(): Promise<SessionAccount | null> {\n  let payload;\n  try {\n    const { cookies } = await import(\"next/headers\");\n    const token = (await cookies()).get(AUTH_COOKIE)?.value;\n    if (!token) return null;\n    payload = await verifyJWT(token);\n  } catch { return null; }\n  // Database failure remains an availability error, never an authenticated snapshot.\n  return payload ? currentAccount(payload) : null;\n}");
assert.equal(digest(declaration), 'f4aaee30541b78bba1c73a98f2c2f64b1ac3a335955088c69e9a63ebbe888675');
assert.equal(digest(declaration.replaceAll('\n', '\r\n')), 'd22f6eec338eb33daed089d05e30e3876e21b2e6e6772d5973117d41077bd258');
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
const forbiddenCalls = [];
const forbidden = () => { forbiddenCalls.push("unexpected injected dependency"); throw new Error("unexpected injected dependency"); };
test.afterEach(() => { assert.deepEqual(forbiddenCalls, []); });
const cookieName = "botrus_auth_token";
const label = "PUBLIC_COOKIE_LABEL";
const payload = Object.freeze({ publicPayload: true });
const account = Object.freeze({ publicAccount: true });
const falsy = [["null", null], ["undefined", undefined], ["empty", ""], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["zero bigint", 0n]];
function load(options = {}) {
    const context = vm.createContext({});
    Object.defineProperties(context, {
        AUTH_COOKIE: { get() { options.onName?.(); return cookieName; } },
        verifyJWT: { get() { options.onVerifyRead?.(); return Object.hasOwn(options, "verify") ? options.verify : forbidden; } },
        currentAccount: { get() { options.onCurrentRead?.(); return Object.hasOwn(options, "current") ? options.current : forbidden; } },
    });
    return vm.runInContext('"use strict"; (' + javascript + ')', context, {
        importModuleDynamically: async (specifier) => {
            assert.equal(specifier, "next/headers");
            options.onImport?.(specifier);
            await options.importGate?.();
            const binding = Object.hasOwn(options, "cookies") ? options.cookies : forbidden;
            const namespace = new vm.SyntheticModule(["cookies"], function () { this.setExport("cookies", binding); }, { context });
            await namespace.link(() => { throw new Error("inert module cannot have imports"); });
            await namespace.evaluate();
            return namespace;
        },
    });
}
const store = (value = label) => ({ get: () => ({ value }) });
const successful = (options = {}) => load({ cookies: () => store(), verify: () => payload, current: () => account, ...options });
function deferred() {
    let resolve;
    let reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
}
control("exact zero-argument async declaration ignores extra arguments and preserves account identity", async () => {
    const selected = successful();
    assert.equal(selected.name, "getSessionAccount");
    assert.equal(selected.length, 0);
    assert.equal(declarations[0].parameters.length, 0);
    assert.equal(declarations[0].body.statements.length, 3);
    assert.equal(await selected("PUBLIC_IGNORED"), account);
});
control("import cookies store member name receiver value verifier and current-account evaluation order", async () => {
    const events = [];
    const jar = { get get() {
            events.push("get-member");
            return function (...args) {
                assert.equal(this, jar);
                assert.equal(args.length, 1);
                assert.equal(args[0], cookieName);
                events.push("get-call");
                return { get value() { events.push("value"); return label; } };
            };
        } };
    const selected = load({ onImport: (...args) => { assert.deepEqual(args, ["next/headers"]); events.push("import"); },
        cookies: function (...args) { assert.equal(this, undefined); assert.equal(args.length, 0); events.push("cookies"); return jar; },
        onName: () => { events.push("name"); }, onVerifyRead: () => { events.push("verify-member"); },
        verify: function (...args) { assert.equal(this, undefined); assert.equal(args.length, 1); assert.equal(args[0], label); events.push("verify"); return payload; },
        onCurrentRead: () => { events.push("current-member"); },
        current: function (...args) { assert.equal(this, undefined); assert.equal(args.length, 1); assert.equal(args[0], payload); events.push("current"); return account; } });
    assert.equal(await selected(), account);
    assert.deepEqual(events, ["import", "cookies", "get-member", "name", "get-call", "value", "verify-member", "verify", "current-member", "current"]);
});
for (const asynchronous of [false, true])
    control("import fault is caught; asynchronous=" + asynchronous, async () => {
        assert.equal(await load(asynchronous ? { importGate: () => Promise.reject(payload) } : { onImport: () => { throw payload; } })(), null);
    });
for (const [name, value] of falsy)
    control("noncallable cookies binding is caught: " + name, async () => { assert.equal(await load({ cookies: value })(), null); });
for (const asynchronous of [false, true])
    control("cookies fault is caught; asynchronous=" + asynchronous, async () => {
        assert.equal(await load({ cookies: () => { if (asynchronous)
                return Promise.reject(payload); throw payload; } })(), null);
    });
for (const [name, value] of falsy)
    control("invalid awaited cookie-store metadata is caught: " + name, async () => { assert.equal(await load({ cookies: () => value })(), null); });
for (const [name, jar] of [["missing get", {}], ["noncallable get", { get: payload }], ["get getter throws", { get get() { throw payload; } }], ["get call throws", { get: () => { throw payload; } }]])
    control("store member/call failure refuses before verifier: " + name, async () => { assert.equal(await load({ cookies: () => jar })(), null); });
for (const value of [null, undefined])
    control("nullish get result avoids value access: " + String(value), async () => { assert.equal(await load({ cookies: () => ({ get: () => value }) })(), null); });
control("get result itself is not awaited", async () => { assert.equal(await load({ cookies: () => ({ get: () => Promise.resolve({ value: label }) }) })(), null); });
control("value getter fault is caught", async () => { assert.equal(await load({ cookies: () => ({ get: () => ({ get value() { throw payload; } }) }) })(), null); });
for (const [name, value] of falsy)
    control("falsy label refuses without verifier: " + name, async () => { assert.equal(await load({ cookies: () => ({ get: () => ({ value }) }) })(), null); });
for (const value of [" PUBLIC ", "PUBLIC%20LABEL", "PUBLIC=LABEL", true, payload])
    control("truthy label forwarded unchanged: " + String(value), async () => {
        assert.equal(await load({ cookies: () => store(value), verify: (...args) => { assert.equal(args.length, 1); assert.equal(args[0], value); return payload; }, current: () => account })(), account);
    });
for (const asynchronous of [false, true])
    control("verifier fault is caught; asynchronous=" + asynchronous, async () => { assert.equal(await successful({ verify: () => { if (asynchronous)
            return Promise.reject(payload); throw payload; } })(), null); });
for (const [name, value] of falsy)
    control("falsy awaited payload avoids current-account read: " + name, async () => { assert.equal(await load({ cookies: () => store(), verify: () => value, onCurrentRead: forbidden })(), null); });
for (const value of [payload, "PUBLIC_PAYLOAD", true, 1, 1n])
    control("truthy payload forwards unchanged: " + String(value), async () => {
        assert.equal(await successful({ verify: () => value, current: (...args) => { assert.equal(args.length, 1); assert.equal(args[0], value); return account; } })(), account);
    });
for (const [name, value] of [...falsy, ["account", account]])
    control("current-account fulfilled result is adopted unchanged: " + name, async () => { assert.equal(await successful({ current: () => value })(), value); });
for (const asynchronous of [false, true])
    control("current-account fault propagates outside catch; asynchronous=" + asynchronous, async () => {
        const fault = Object.freeze({ publicFault: "CURRENT" });
        await assert.rejects(successful({ current: () => { if (asynchronous)
                return Promise.reject(fault); throw fault; } })(), (e) => e === fault);
    });
for (const value of [null, undefined, 1])
    control("noncallable current-account binding rejects outside catch: " + String(value), async () => { await assert.rejects(successful({ current: value })(), { name: "TypeError" }); });
for (const stage of ["import", "cookies", "verify"])
    control("await fence delays later work: " + stage, async () => {
        const gate = deferred(), entered = deferred();
        let later = 0, settled = false;
        const pending = () => { entered.resolve(true); return gate.promise; };
        const options = { cookies: () => store(), verify: () => payload, current: () => account };
        if (stage === "import") {
            options.importGate = pending;
            options.cookies = () => { later++; return store(); };
        }
        if (stage === "cookies") {
            options.cookies = pending;
            options.verify = () => { later++; return payload; };
        }
        if (stage === "verify") {
            options.verify = pending;
            options.current = () => { later++; return account; };
        }
        const promise = load(options)();
        void promise.then(() => { settled = true; });
        await entered.promise;
        assert.equal(later, 0);
        assert.equal(settled, false);
        gate.resolve(stage === "cookies" ? store() : stage === "verify" ? payload : undefined);
        assert.equal(await promise, account);
        assert.equal(later, 1);
    });
for (const rejected of [false, true])
    control("direct return adopts pending current-account result; rejected=" + rejected, async () => {
        const gate = deferred(), entered = deferred();
        let settled = false;
        const promise = successful({ current: () => { entered.resolve(true); return gate.promise; } })();
        void promise.then(() => { settled = true; }, () => { settled = true; });
        await entered.promise;
        assert.equal(settled, false);
        if (rejected) {
            gate.reject(payload);
            await assert.rejects(promise, (e) => e === payload);
        }
        else {
            gate.resolve(account);
            assert.equal(await promise, account);
        }
    });
control("cookie-name getter fault is caught after get member but before get call", async () => {
    const events = [];
    assert.equal(await load({ cookies: () => ({ get get() { events.push("member"); return forbidden; } }), onName: () => { events.push("name"); throw payload; } })(), null);
    assert.deepEqual(events, ["member", "name"]);
});
control("verifier binding getter fault is caught", async () => { assert.equal(await successful({ onVerifyRead: () => { throw payload; } })(), null); });
control("current-account binding getter fault propagates", async () => { let reads = 0; await assert.rejects(successful({ onCurrentRead: () => { reads++; throw payload; } })(), { name: "ReferenceError", message: "currentAccount is not defined" }); assert.equal(reads, 1); });
control("verifier then getter fault is caught by await", async () => { assert.equal(await successful({ verify: () => ({ get then() { throw payload; } }) })(), null); });
control("current-account then getter fault rejects outside catch", async () => { await assert.rejects(successful({ current: () => ({ get then() { throw payload; } }) })(), (e) => e === payload); });
control("payload and account properties are not projected or inspected", async () => {
    const opaque = new Proxy(Object.create(null), { get(_target, key) { if (key === "then")
            return undefined; throw payload; } });
    const result = new Proxy(Object.create(null), { get(_target, key) { if (key === "then")
            return undefined; throw payload; } });
    assert.equal(await successful({ verify: () => opaque, current: (...args) => { assert.equal(args[0], opaque); return result; } })(), result);
});
control("successive calls freshly import read verify and resolve current account", async () => {
    let imports = 0, reads = 0, verifies = 0, currents = 0;
    const selected = load({ onImport: () => { imports++; }, cookies: () => { reads++; return store(); }, verify: () => { verifies++; return payload; }, current: () => { currents++; return currents === 1 ? account : null; } });
    assert.equal(await selected(), account);
    assert.equal(await selected(), null);
    assert.deepEqual([imports, reads, verifies, currents], [2, 2, 2, 2]);
});
control("concurrent calls retain independent current-account results and completion order", async () => {
    const first = deferred(), second = deferred(), entered = deferred();
    let calls = 0;
    const other = Object.freeze({ publicAccount: "SECOND" });
    const selected = successful({ current: () => { calls++; if (calls === 2)
            entered.resolve(true); return calls === 1 ? first.promise : second.promise; } });
    const a = selected(), b = selected();
    await entered.promise;
    second.resolve(other);
    assert.equal(await b, other);
    first.resolve(account);
    assert.equal(await a, account);
});
assert.equal(count, 85);
