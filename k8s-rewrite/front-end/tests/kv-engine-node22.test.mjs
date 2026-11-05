// DISTINCT NEW PUBLIC128 controls (127 leaf plus parent); historical controls remain frozen.
let count = 0;
const control = (...args) => { count++; return test(...args); };
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
// PUBLIC SOURCE: only this exact declaration runs; real imports/services stay inert.
const require = createRequire(import.meta.url);
const ts = require('typescript');
const source = readFileSync(new URL("../src/lib/kv-http.ts", import.meta.url), "utf8");
const ast = ts.createSourceFile("kv-http.ts", source, ts.ScriptTarget.Latest, true);
const selected = ast.statements.filter((s) => ts.isFunctionDeclaration(s) && s.name?.getText() === "kvEngine");
assert.equal(selected.length, 1);
const declaration = selected[0];
assert.equal(process.version, 'v22.23.3');
assert.equal(ts.version, '5.9.3');
assert.equal(declaration.getText(), "export function kvEngine(registry: KvRegistry) { return new KvNativeEngine(registry, createSecretTransport(), listAliases); }");
const js = ts.transpileModule(declaration.getText().replace(/^export /, ""), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
const names = ["KvNativeEngine", "createSecretTransport", "listAliases"];
function select(bindings) {
    const setters = names.map(n => `case ${JSON.stringify(n)}: ${n} = value; break;`).join("\n");
    return new Function(...names, '"use strict";\n' + js + "\nreturn {invoke:kvEngine,replace(name,value){switch(name){" + setters + "default:throw Error('unknown binding')}}};")(...names.map(n => bindings[n]));
}
function opaque(label) {
    return new Proxy(Object.create(null), { get(_t, key) { throw Error(label + " read " + String(key)); }, ownKeys() { throw Error(label + " ownKeys"); }, getPrototypeOf() { throw Error(label + " prototype"); } });
}
const examples = [undefined, null, false, true, 0, -0, -1, NaN, "", "public", 1n, Symbol("public"), {}, [], opaque("public")];
const stages = ["transport", "construct"];
function rig(o = {}) {
    const events = [];
    const hit = (s) => { events.push(s); o.at?.(s); };
    const values = Object.fromEntries(["registry", "transport", "aliases"].map(k => [k, Object.hasOwn(o, k) ? o[k] : opaque(k)]));
    const result = o.result ?? opaque("result");
    const constructor = new Proxy(function PublicEngine() { }, { construct(_target, args, newTarget) {
            hit("construct");
            assert.equal(newTarget, constructor);
            assert.equal(args.length, 3);
            assert.equal(args[0], values.registry);
            assert.equal(args[1], values.transport);
            assert.equal(args[2], values.aliases);
            return result;
        }, apply() { throw Error("called rather than constructed"); } });
    const scope = select({ KvNativeEngine: constructor, listAliases: values.aliases,
        createSecretTransport: function (...args) { assert.equal(this, undefined); assert.equal(args.length, 0); hit("transport"); return values.transport; },
    });
    return { scope, events, values, result, constructor, invoke: () => scope.invoke(values.registry) };
}
function catches(fn, failure) {
    let caught = false;
    try {
        fn();
    }
    catch (error) {
        caught = true;
        assert.equal(error, failure);
    }
    assert.equal(caught, true);
}
control("kvEngine finite PUBLIC SOURCE factory controls", async (t) => {
    await t.test("exact exported synchronous one-parameter factory; selection has no effects", () => {
        assert.deepEqual(declaration.modifiers.map((m) => m.kind), [ts.SyntaxKind.ExportKeyword]);
        assert.equal(declaration.parameters.length, 1);
        assert.equal(declaration.parameters[0].getText(), "registry: KvRegistry");
        assert.equal(declaration.body.statements.length, 1);
        assert.equal(declaration.body.statements[0].getText(), "return new KvNativeEngine(registry, createSecretTransport(), listAliases);");
        const s = select(Object.fromEntries(names.map(n => [n, () => { throw Error("selection executed " + n); }])));
        assert.equal(s.invoke.length, 1);
        assert.equal(s.invoke.name, "kvEngine");
    });
    await t.test("unbound zero-argument transport precedes construction with exact identities/newTarget", () => {
        const r = rig();
        assert.equal(r.invoke(), r.result);
        assert.deepEqual(r.events, stages);
    });
    for (const field of ["registry", "transport", "aliases"])
        for (const [i, value] of examples.entries()) {
            await t.test(field + " original identity without coercion or inspection " + i, () => {
                const r = rig({ [field]: value });
                assert.equal(r.invoke(), r.result);
                assert.deepEqual(r.events, stages);
            });
        }
    for (const stage of stages)
        for (const [i, failure] of examples.entries()) {
            await t.test(stage + " exact thrown identity and refusal prefix " + i, () => {
                const r = rig({ at(s) { if (s === stage)
                        throw failure; } });
                catches(r.invoke, failure);
                assert.deepEqual(r.events, stages.slice(0, stages.indexOf(stage) + 1));
            });
        }
    for (const [i, value] of [undefined, null, 0, {}, "public"].entries()) {
        await t.test("noncallable transport refuses before construction " + i, () => {
            const r = rig();
            r.scope.replace("createSecretTransport", value);
            assert.throws(r.invoke, TypeError);
            assert.deepEqual(r.events, []);
        });
    }
    for (const [i, ctor] of [undefined, null, 0, {}, () => ({}), async () => ({})].entries()) {
        await t.test("nonconstructor is checked after transport evaluation " + i, () => {
            const r = rig();
            r.scope.replace("KvNativeEngine", ctor);
            assert.throws(r.invoke, TypeError);
            assert.deepEqual(r.events, ["transport"]);
        });
    }
    await t.test("transport refusal takes precedence over nonconstructor rejection", () => {
        const failure = opaque("transport refusal");
        const r = rig({ at(s) { if (s === "transport")
                throw failure; } });
        r.scope.replace("KvNativeEngine", undefined);
        catches(r.invoke, failure);
        assert.deepEqual(r.events, ["transport"]);
    });
    await t.test("transport cannot replace the already captured constructor", () => {
        const r = rig({ at(s) { if (s === "transport")
                r.scope.replace("KvNativeEngine", () => { throw Error("late constructor used"); }); } });
        assert.equal(r.invoke(), r.result);
        assert.deepEqual(r.events, stages);
    });
    await t.test("transport selects the later alias binding without calling either alias function", () => {
        const registry = opaque("registry"), transport = opaque("transport"), result = opaque("result");
        const events = [];
        const alias = () => { throw Error("alias called"); };
        const ctor = new Proxy(function PublicEngine() { }, { construct(_target, args, nt) {
                assert.equal(nt, ctor);
                assert.equal(args.length, 3);
                assert.equal(args[0], registry);
                assert.equal(args[1], transport);
                assert.equal(args[2], alias);
                events.push("construct");
                return result;
            } });
        const s = select({ KvNativeEngine: ctor, listAliases() { throw Error("old alias called"); }, createSecretTransport() { events.push("transport"); s.replace("listAliases", alias); return transport; } });
        assert.equal(s.invoke(registry), result);
        assert.deepEqual(events, stages);
    });
    await t.test("alias is captured before constructor effects", () => {
        const r = rig({ at(s) { if (s === "construct")
                r.scope.replace("listAliases", opaque("replacement alias")); } });
        assert.equal(r.invoke(), r.result);
        assert.deepEqual(r.events, stages);
    });
    await t.test("each invocation freshly resolves constructor, transport and alias with its own registry", () => {
        const r = rig(), next = rig();
        assert.equal(r.invoke(), r.result);
        r.scope.replace("KvNativeEngine", next.constructor);
        r.scope.replace("createSecretTransport", () => next.values.transport);
        r.scope.replace("listAliases", next.values.aliases);
        assert.equal(r.scope.invoke(next.values.registry), next.result);
        assert.deepEqual(r.events, stages);
        assert.deepEqual(next.events, ["construct"]);
    });
    for (const [i, primitive] of examples.filter(x => x === null || typeof x !== "object" && typeof x !== "function").entries()) {
        await t.test("ordinary constructor primitive return retains a fresh instance " + i, () => {
            const r = rig();
            const receivers = [];
            function Constructor(...args) { assert.equal(new.target, Constructor); assert.equal(args.length, 3); assert.equal(args[0], r.values.registry); assert.equal(args[1], r.values.transport); assert.equal(args[2], r.values.aliases); receivers.push(this); return primitive; }
            r.scope.replace("KvNativeEngine", Constructor);
            const first = r.invoke(), second = r.invoke();
            assert.equal(first, receivers[0]);
            assert.equal(second, receivers[1]);
            assert.notEqual(first, second);
            assert.equal(Object.getPrototypeOf(first), Constructor.prototype);
            assert.deepEqual(r.events, ["transport", "transport"]);
        });
    }
    for (const [i, result] of [{}, [], opaque("constructor result"), function publicResult() { }, Object.defineProperty({}, "then", { get() { throw Error("then read"); } })].entries()) {
        await t.test("ordinary constructor object result returned untouched " + i, () => {
            const r = rig();
            r.scope.replace("KvNativeEngine", function () { return result; });
            assert.equal(r.invoke(), result);
            assert.deepEqual(r.events, ["transport"]);
        });
    }
    await t.test("class construction preserves receiver and original inputs", () => {
        const r = rig();
        let receiver;
        class PublicEngine {
            constructor(...args) { receiver = this; assert.equal(new.target, PublicEngine); assert.equal(args.length, 3); assert.equal(args[0], r.values.registry); assert.equal(args[1], r.values.transport); assert.equal(args[2], r.values.aliases); }
        }
        r.scope.replace("KvNativeEngine", PublicEngine);
        const result = r.invoke();
        assert.equal(result, receiver);
        assert.equal(Object.getPrototypeOf(result), PublicEngine.prototype);
        assert.deepEqual(r.events, ["transport"]);
    });
    for (const field of ["registry", "transport", "aliases"]) {
        await t.test(field + " thenable is never assimilated", () => {
            const value = Object.defineProperty({}, "then", { get() { throw Error("then read"); } });
            const r = rig({ [field]: value });
            assert.equal(r.invoke(), r.result);
            assert.deepEqual(r.events, stages);
        });
        await t.test(field + " Promise remains the original object", async () => {
            const value = Promise.resolve("public");
            const r = rig({ [field]: value });
            assert.equal(r.invoke(), r.result);
            assert.deepEqual(r.events, stages);
            await value;
        });
    }
    for (const kind of ["resolved", "rejected"]) {
        await t.test("constructor " + kind + " Promise returned synchronously", async () => {
            const failure = {};
            const result = kind === "resolved" ? Promise.resolve("public") : Promise.reject(failure);
            const handled = result.catch(e => { assert.equal(e, failure); });
            const r = rig({ result });
            assert.equal(r.invoke(), result);
            assert.deepEqual(r.events, stages);
            await handled;
        });
    }
    await t.test("prototype read follows transport and uses captured constructor", () => {
        const events = [];
        const proto = {};
        let receiver;
        const target = function () { receiver = this; assert.equal(new.target, ctor); events.push("body"); };
        target.prototype = proto;
        const ctor = new Proxy(target, { get(_target, key, recv) { assert.equal(key, "prototype"); events.push("prototype"); assert.equal(recv, ctor); return proto; } });
        const s = select({ KvNativeEngine: ctor, createSecretTransport() { events.push("transport"); return opaque("transport"); }, listAliases: opaque("aliases") });
        const result = s.invoke(opaque("registry"));
        assert.equal(result, receiver);
        assert.equal(Object.getPrototypeOf(result), proto);
        assert.deepEqual(events, ["transport", "prototype", "body"]);
    });
    for (const [i, failure] of [undefined, null, Symbol("failure"), opaque("failure")].entries()) {
        await t.test("prototype refusal preserves identity and prevents body " + i, () => {
            const events = [];
            const ctor = new Proxy(function () { throw Error("body executed"); }, { get(_target, key) { assert.equal(key, "prototype"); events.push("prototype"); throw failure; } });
            const s = select({ KvNativeEngine: ctor, createSecretTransport() { events.push("transport"); return {}; }, listAliases: {} });
            catches(() => s.invoke({}), failure);
            assert.deepEqual(events, ["transport", "prototype"]);
        });
    }
    for (const stage of stages) {
        await t.test(stage + " reentrancy keeps the outer registry and argument identities", () => {
            let entered = false;
            const next = rig();
            const r = rig({ at(s) {
                    if (s !== stage || entered)
                        return;
                    entered = true;
                    r.scope.replace("KvNativeEngine", next.constructor);
                    r.scope.replace("createSecretTransport", () => next.values.transport);
                    r.scope.replace("listAliases", next.values.aliases);
                    assert.equal(r.scope.invoke(next.values.registry), next.result);
                    r.scope.replace("listAliases", r.values.aliases);
                } });
            assert.equal(r.invoke(), r.result);
            assert.deepEqual(r.events, stages);
            assert.deepEqual(next.events, ["construct"]);
        });
    }
    await t.test("extra factory arguments and caller receiver do not reach the engine", () => {
        const r = rig();
        const invoke = r.scope.invoke;
        assert.equal(invoke.call(opaque("caller"), r.values.registry, opaque("extra")), r.result);
        assert.deepEqual(r.events, stages);
    });
});
assert.equal(count, 1);
