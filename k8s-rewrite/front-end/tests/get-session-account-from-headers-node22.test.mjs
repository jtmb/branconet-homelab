import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import vm from 'node:vm';

// Distinct PUBLIC selected-declaration controls; historical75 remain frozen.
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
const declarations = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === 'getSessionAccountFromHeaders');
assert.equal(declarations.length, 1);
const node = declarations[0];
assert.deepEqual(node.modifiers.map(node => node.kind), [ts.SyntaxKind.ExportKeyword, ts.SyntaxKind.AsyncKeyword]);
assert.deepEqual(node.parameters.map(node => node.getText(ast)), ['cookieHeader: string | null']);
const declaration = node.getText(ast);
assert.equal(declaration, "export async function getSessionAccountFromHeaders(cookieHeader: string | null): Promise<SessionAccount | null> {\n  if (!cookieHeader) return null;\n  const token = cookieHeader.match(new RegExp(`(?:^|;\\\\s*)${AUTH_COOKIE}=([^;]*)`))?.[1];\n  if (!token) return null;\n  const payload = await verifyJWT(token);\n  return payload ? currentAccount(payload) : null;\n}");
assert.equal(digest(declaration), 'a7cfd66966923e43f6273b5869bdfd42c2d3812184fa9db460da4b7abe7c0ec1');
assert.equal(digest(declaration.replaceAll('\n', '\r\n')), 'c69767132acd5ef6b7b577484e7c729f8f9e3a7f7015e51650c0ee5b2094929a');
const selected = declaration.replace(/^export\s+/, '');
const compiled = ts.transpileModule(selected, { reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } });
assert.equal(compiled.diagnostics.length, 0);
const javascript = compiled.outputText.trim();
assert.ok(!javascript.includes('import(') && !javascript.includes('require('));
let count = 0;
const control = (...args) => { count++; return test(...args); };
const forbiddenCalls = [];
const forbidden = () => { forbiddenCalls.push("unexpected dependency"); throw new Error("unexpected dependency"); };
test.afterEach(() => { assert.deepEqual(forbiddenCalls, []); });
function load(options = {}) {
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
    let resolve;
    let reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
}
control("only selected async declaration; no account projection or additional argument forwarding", async () => {
    const payload = Object.freeze({ publicPayload: true });
    let calls = 0;
    const f = load({ verify: () => payload, current: (...args) => { calls++; assert.equal(args.length, 1); assert.equal(args[0], payload); return result; } });
    assert.equal(f.name, "getSessionAccountFromHeaders");
    assert.equal(f.length, 1);
    assert.equal(declarations[0].body.statements.length, 5);
    assert.equal(await f(header, "PUBLIC_IGNORED"), result);
    assert.equal(calls, 1);
});
for (const [name, value] of [["null", null], ["undefined", undefined], ["empty", ""], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["zero bigint", 0n]])
    control("falsy header avoids all dependencies: " + name, async () => {
        assert.equal(await load({ regexp: forbidden })(value), null);
    });
for (const text of ["PUBLIC_OTHER", "Botrus_auth_token=PUBLIC_LABEL", "xbotrus_auth_token=PUBLIC_LABEL", " botrus_auth_token=PUBLIC_LABEL", "botrus_auth_token", "botrus_auth_token=", "botrus_auth_token =PUBLIC_LABEL", "botrus_auth_token=;botrus_auth_token=PUBLIC_SECOND"])
    control("absent or first-empty synthetic label refuses: " + text, async () => {
        assert.equal(await load()(text), null);
    });
for (const [text, label] of [[header, "PUBLIC_LABEL"], [header + ";other=PUBLIC_OTHER", "PUBLIC_LABEL"], ["other=PUBLIC_OTHER;botrus_auth_token=PUBLIC_LABEL", "PUBLIC_LABEL"], ["other=PUBLIC_OTHER; \tbotrus_auth_token=PUBLIC_LABEL", "PUBLIC_LABEL"], ["other=PUBLIC_OTHER;\nbotrus_auth_token=PUBLIC_LABEL", "PUBLIC_LABEL"], [header + ";botrus_auth_token=PUBLIC_SECOND", "PUBLIC_LABEL"], ["botrus_auth_token=PUBLIC=LABEL", "PUBLIC=LABEL"], ["botrus_auth_token=%50UBLIC_LABEL", "%50UBLIC_LABEL"], ["botrus_auth_token=\"PUBLIC_LABEL\"", "\"PUBLIC_LABEL\""], ["botrus_auth_token= PUBLIC_LABEL ", " PUBLIC_LABEL "]])
    control("exact first regex capture forwarded without decoding: " + text, async () => {
        const p = Object.freeze({ publicPayload: true });
        let verified = 0;
        let current = 0;
        assert.equal(await load({ verify: function (...args) { assert.equal(this, undefined); assert.equal(args.length, 1); assert.equal(args[0], label); verified++; return p; }, current: function (...args) { assert.equal(this, undefined); assert.equal(args.length, 1); assert.equal(args[0], p); current++; return result; } })(text), result);
        assert.equal(verified, 1);
        assert.equal(current, 1);
    });
control("capture match then construct regex then invoke exact receiver then index then verifier then account", async () => {
    const events = [];
    let regex;
    const p = Object.freeze({ publicPayload: true });
    function Constructor(...args) { events.push("construct"); assert.equal(args.length, 1); assert.equal(args[0], "(?:^|;\\s*)botrus_auth_token=([^;]*)"); regex = new RegExp(args[0]); return regex; }
    const h = { get match() { events.push("member"); return function (...args) { events.push("call"); assert.equal(this, h); assert.equal(args.length, 1); assert.equal(args[0], regex); assert.equal(regex.flags, ""); return { get 1() { events.push("index"); return "PUBLIC_LABEL"; } }; }; } };
    assert.equal(await load({ regexp: Constructor, verify: () => { events.push("verify"); return p; }, current: () => { events.push("current"); return result; } })(h), result);
    assert.deepEqual(events, ["member", "construct", "call", "index", "verify", "current"]);
});
for (const [name, value] of [["null", null], ["undefined", undefined], ["missing index", {}], ["empty array", []]])
    control("nullish match or missing capture refuses: " + name, async () => { assert.equal(await load()({ match: () => value }), null); });
for (const [name, value] of [["null", null], ["undefined", undefined], ["empty", ""], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["zero bigint", 0n]])
    control("falsy synthetic capture avoids verifier: " + name, async () => { assert.equal(await load()({ match: () => ({ 1: value }) }), null); });
for (const [name, value] of [["null", null], ["undefined", undefined], ["empty", ""], ["false", false], ["zero", 0], ["negative zero", -0], ["NaN", NaN], ["zero bigint", 0n]])
    control("awaited falsy verifier payload avoids account: " + name, async () => { assert.equal(await load({ verify: () => value })(header), null); });
for (const [name, value] of [["object", Object.freeze({ publicPayload: true })], ["string", "PUBLIC_PAYLOAD"], ["number", 1], ["boolean", true], ["bigint", 1n]])
    control("truthy inert verifier payload forwarded unchanged: " + name, async () => { assert.equal(await load({ verify: () => value, current: (...args) => { assert.equal(args.length, 1); assert.equal(args[0], value); return result; } })(header), result); });
for (const [name, value] of [["number", 1], ["boolean", true], ["missing match", {}], ["noncallable match", { match: 1 }]])
    control("truthy malformed inert header rejects before verifier: " + name, async () => { await assert.rejects(load()(value), { name: "TypeError" }); });
for (const position of ["member", "construct", "call", "index"])
    control("pre-verifier fault propagates exactly and stops later stages: " + position, async () => {
        const fault = Object.freeze({ publicFault: position });
        const events = [];
        const visit = (stage) => { events.push(stage); if (position === stage)
            throw fault; };
        function Constructor() { visit("construct"); return /PUBLIC/; }
        const h = { get match() { visit("member"); return () => { visit("call"); return { get 1() { visit("index"); return "PUBLIC_LABEL"; } }; }; } };
        await assert.rejects(load({ regexp: Constructor })(h), (e) => e === fault);
        assert.deepEqual(events, ["member", "construct", "call", "index"].slice(0, ["member", "construct", "call", "index"].indexOf(position) + 1));
    });
for (const asynchronous of [false, true])
    control("verifier fault has no catch or account fallback; async=" + asynchronous, async () => {
        const fault = Object.freeze({ publicFault: "VERIFY" });
        await assert.rejects(load({ verify: () => { if (asynchronous)
                return Promise.reject(fault); throw fault; } })(header), (e) => e === fault);
    });
for (const asynchronous of [false, true])
    control("account fault has no catch or fallback; async=" + asynchronous, async () => {
        const fault = Object.freeze({ publicFault: "ACCOUNT" });
        await assert.rejects(load({ verify: () => ({ publicPayload: true }), current: () => { if (asynchronous)
                return Promise.reject(fault); throw fault; } })(header), (e) => e === fault);
    });
control("verifier await fences account invocation until payload fulfillment", async () => {
    const gate = deferred();
    const p = Object.freeze({ publicPayload: true });
    let calls = 0;
    const pending = load({ verify: () => gate.promise, current: (value) => { calls++; assert.equal(value, p); return result; } })(header);
    await Promise.resolve();
    assert.equal(calls, 0);
    gate.resolve(p);
    assert.equal(await pending, result);
    assert.equal(calls, 1);
});
control("pending verifier rejection retains reason and never calls account", async () => {
    const gate = deferred();
    const fault = Object.freeze({ publicFault: "PENDING_VERIFY" });
    const checked = assert.rejects(load({ verify: () => gate.promise })(header), (e) => e === fault);
    gate.reject(fault);
    await checked;
});
control("verifier thenable is adopted once before passing exact payload", async () => {
    let reads = 0;
    let calls = 0;
    const p = Object.freeze({ publicPayload: true });
    const thenable = { get then() { reads++; return function (resolve) { assert.equal(this, thenable); calls++; resolve(p); }; } };
    assert.equal(await load({ verify: () => thenable, current: (value) => { assert.equal(value, p); return result; } })(header), result);
    assert.equal(reads, 1);
    assert.equal(calls, 1);
});
for (const stage of ["verify", "current"])
    control("then getter failure propagates exact reason: " + stage, async () => {
        const fault = Object.freeze({ publicFault: "THEN" });
        const value = { get then() { throw fault; } };
        await assert.rejects(load({ verify: () => stage === "verify" ? value : ({ publicPayload: true }), current: () => value })(header), (e) => e === fault);
    });
control("account return adoption waits for pending fulfillment without projecting properties", async () => {
    const gate = deferred();
    let settled = false;
    const pending = load({ verify: () => ({ publicPayload: true }), current: () => gate.promise })(header);
    const observed = pending.then((v) => { settled = true; assert.equal(v, result); });
    await Promise.resolve();
    assert.equal(settled, false);
    gate.resolve(result);
    await observed;
});
control("account custom thenable is adopted once with exact receiver and outcome", async () => {
    let reads = 0;
    let calls = 0;
    const value = { get then() { reads++; return function (resolve) { assert.equal(this, value); calls++; resolve(result); }; } };
    const pending = load({ verify: () => ({ publicPayload: true }), current: () => value })(header);
    await pending.then((v) => { assert.equal(v, result); });
    assert.equal(reads, 1);
    assert.equal(calls, 1);
});
control("payload properties and account authorization fields stay unread", async () => {
    const trap = () => { forbiddenCalls.push("projection"); throw new Error("unused"); };
    const p = { get sub() { return trap(); }, get sessionVersion() { return trap(); } };
    const u = { get id() { return trap(); }, get role() { return trap(); }, get engineAdmin() { return trap(); } };
    assert.equal(await load({ verify: () => p, current: (v) => { assert.equal(v, p); return u; } })(header), u);
});
control("each invocation re-verifies and obtains fresh account result", async () => {
    let count = 0;
    const one = Object.freeze({ publicResult: 1 });
    const two = Object.freeze({ publicResult: 2 });
    const f = load({ verify: () => (++count === 1 ? { publicPayload: 1 } : { publicPayload: 2 }), current: () => count === 1 ? one : two });
    assert.equal(await f(header), one);
    assert.equal(await f(header), two);
    assert.equal(count, 2);
});
control("concurrent verifier completions retain their own payload and result", async () => {
    const a = deferred();
    const b = deferred();
    const pa = Object.freeze({ publicPayload: "A" });
    const pb = Object.freeze({ publicPayload: "B" });
    const ra = Object.freeze({ publicResult: "A" });
    const rb = Object.freeze({ publicResult: "B" });
    const events = [];
    const f = load({ verify: (v) => { events.push(String(v)); return v === "PUBLIC_A" ? a.promise : b.promise; }, current: (p) => p === pa ? ra : p === pb ? rb : forbidden() });
    const first = f("botrus_auth_token=PUBLIC_A");
    const second = f("botrus_auth_token=PUBLIC_B");
    b.resolve(pb);
    assert.equal(await second, rb);
    a.resolve(pa);
    assert.equal(await first, ra);
    assert.deepEqual(events, ["PUBLIC_A", "PUBLIC_B"]);
});
assert.equal(count, 75);
