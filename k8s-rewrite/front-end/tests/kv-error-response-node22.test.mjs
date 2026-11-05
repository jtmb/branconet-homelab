// DISTINCT NEW PUBLIC182 controls (181 leaf plus parent); historical controls remain frozen.
let count = 0;
const control = (...args) => { count++; return test(...args); };
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
// PUBLIC SOURCE only: extract one declaration; all imports and real services stay inert.
const require = createRequire(import.meta.url);
const ts = require('typescript');
const source = readFileSync(new URL("../src/lib/kv-http.ts", import.meta.url), "utf8");
const ast = ts.createSourceFile("kv-http.ts", source, ts.ScriptTarget.Latest, true);
const selected = ast.statements.filter((s) => ts.isFunctionDeclaration(s) && s.name?.getText() === "kvErrorResponse");
assert.equal(selected.length, 1);
const declaration = selected[0];
assert.equal(process.version, 'v22.23.3');
assert.equal(ts.version, '5.9.3');
assert.equal(declaration.getText(), "export function kvErrorResponse(error: unknown) {\n  return error instanceof KvMutationError ? secretResponse({ error: error.message, operationId: error.operationId, outcome: error.outcome }, error.status) : secretErrorResponse(error);\n}");
const js = ts.transpileModule(declaration.getText().replace(/^export /, ""), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
const names = ["KvMutationError", "secretResponse", "secretErrorResponse"];
function select(bindings) {
    const setters = names.map(n => `case ${JSON.stringify(n)}: ${n} = value; break;`).join("\n");
    return new Function(...names, '"use strict";\n' + js + "\nreturn {invoke:kvErrorResponse,replace(name,value){switch(name){" + setters + "default:throw Error('unknown binding')}}};")(...names.map(n => bindings[n]));
}
function opaque(label) {
    return new Proxy(Object.create(null), { get(_t, key) { throw Error(label + " read " + String(key)); }, ownKeys() { throw Error(label + " ownKeys"); }, getPrototypeOf() { throw Error(label + " prototype"); } });
}
const properties = ["message", "operationId", "outcome", "status"];
const stages = ["instance", ...properties, "response"];
const examples = [undefined, null, false, true, 0, -1, NaN, "", "public", 1n, Symbol("public"), {}, [], opaque("public")];
function rig(o = {}) {
    const events = [];
    const hit = (s) => { events.push(s); o.at?.(s); };
    const fields = Object.fromEntries(properties.map(p => [p, o.fields && Object.hasOwn(o.fields, p) ? o.fields[p] : opaque(p)]));
    const target = Object.create(null);
    const error = Object.hasOwn(o, "input") ? o.input : target;
    for (const p of properties)
        Object.defineProperty(target, p, { configurable: true, get() { assert.equal(this, error); hit(p); return fields[p]; } });
    const result = Object.hasOwn(o, "result") ? o.result : opaque("result");
    const classifier = Object.defineProperty({}, Symbol.hasInstance, { value: function (...args) {
            assert.equal(this, classifier);
            assert.equal(args.length, 1);
            assert.equal(args[0], error);
            hit("instance");
            return Object.hasOwn(o, "classification") ? o.classification : true;
        } });
    let payload;
    const bindings = {
        KvMutationError: classifier,
        secretResponse: function (...args) {
            assert.equal(this, undefined);
            hit("response");
            assert.equal(args.length, 2);
            const body = args[0];
            payload = body;
            assert.equal(Object.getPrototypeOf(body), Object.prototype);
            assert.deepEqual(Reflect.ownKeys(body), ["error", "operationId", "outcome"]);
            for (const [key, field] of [["error", "message"], ["operationId", "operationId"], ["outcome", "outcome"]]) {
                const descriptor = Object.getOwnPropertyDescriptor(body, key);
                assert.equal(descriptor.value, fields[field]);
                assert.equal(descriptor.writable, true);
                assert.equal(descriptor.enumerable, true);
                assert.equal(descriptor.configurable, true);
            }
            assert.equal(args[1], fields.status);
            return o.response ? o.response.apply(this, args) : result;
        },
        secretErrorResponse: function (...args) {
            assert.equal(this, undefined);
            hit("fallback");
            assert.equal(args.length, 1);
            assert.equal(args[0], error);
            return o.fallback ? o.fallback.apply(this, args) : result;
        },
    };
    const scope = select(bindings);
    return { error, target, events, fields, result, classifier, bindings, scope, payload: () => payload, invoke: () => scope.invoke(error) };
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
control("kvErrorResponse finite PUBLIC SOURCE controls", async (t) => {
    await t.test("exact exported synchronous declaration and inert selection", () => {
        assert.deepEqual(declaration.modifiers.map((m) => m.kind), [ts.SyntaxKind.ExportKeyword]);
        assert.deepEqual(declaration.parameters.map((p) => p.getText()), ["error: unknown"]);
        assert.equal(declaration.body.statements.length, 1);
        assert.equal(declaration.body.statements[0].getText(), "return error instanceof KvMutationError ? secretResponse({ error: error.message, operationId: error.operationId, outcome: error.outcome }, error.status) : secretErrorResponse(error);");
        select(Object.fromEntries(names.map(n => [n, () => { throw Error("selection executed " + n); }])));
    });
    await t.test("exact field order receivers payload and synchronous opaque result", () => {
        const r = rig();
        assert.equal(r.invoke(), r.result);
        assert.deepEqual(r.events, stages);
    });
    for (const [index, input] of examples.entries()) {
        await t.test("false branch original error identity " + index, () => {
            const r = rig({ input, classification: false });
            assert.equal(r.invoke(), r.result);
            assert.deepEqual(r.events, ["instance", "fallback"]);
        });
    }
    for (const property of properties)
        for (const [index, value] of examples.entries()) {
            await t.test(property + " exact uncoerced identity " + index, () => {
                const r = rig({ fields: { [property]: value } });
                assert.equal(r.invoke(), r.result);
                assert.deepEqual(r.events, stages);
            });
        }
    for (const [index, classification] of [false, 0, -0, 0n, NaN, "", null, undefined, true, 1, -1, "public", {}, [], Symbol("public")].entries()) {
        await t.test("instanceof ToBoolean branch " + index, () => {
            const r = rig({ classification });
            assert.equal(r.invoke(), r.result);
            assert.deepEqual(r.events, classification ? stages : ["instance", "fallback"]);
        });
    }
    for (const stage of stages)
        for (const [index, failure] of [undefined, null, Symbol("failure"), opaque("failure")].entries()) {
            await t.test(stage + " exact refusal prefix " + index, () => {
                const r = rig({ at(s) { if (s === stage)
                        throw failure; } });
                catches(r.invoke, failure);
                assert.deepEqual(r.events, stages.slice(0, stages.indexOf(stage) + 1));
            });
        }
    for (const failure of [undefined, null, Symbol("fallback-failure"), opaque("fallback-failure")]) {
        await t.test("fallback delegate throws exact identity " + String(typeof failure), () => {
            const r = rig({ classification: false, fallback() { throw failure; } });
            catches(r.invoke, failure);
            assert.deepEqual(r.events, ["instance", "fallback"]);
        });
    }
    for (const branch of [true, false])
        for (const [index, result] of examples.entries()) {
            await t.test("branch " + branch + " exact return " + index, () => {
                const r = rig({ classification: branch, result });
                assert.equal(r.invoke(), result);
                assert.deepEqual(r.events, branch ? stages : ["instance", "fallback"]);
            });
        }
    for (const branch of [true, false])
        for (const kind of ["thenable", "resolved", "rejected"]) {
            await t.test("branch " + branch + " returns " + kind + " without adoption", async () => {
                const failure = {};
                const result = kind === "thenable" ? Object.defineProperty({}, "then", { get() { throw Error("then accessed"); } }) : kind === "resolved" ? Promise.resolve("public") : Promise.reject(failure);
                if (kind === "rejected")
                    void result.catch(() => { });
                const r = rig({ classification: branch, result });
                assert.equal(r.invoke(), result);
                assert.deepEqual(r.events, branch ? stages : ["instance", "fallback"]);
                if (kind === "rejected")
                    await assert.rejects(result, e => e === failure);
            });
        }
    await t.test("inherited getters retain the original error receiver", () => {
        const r = rig();
        const error = Object.create(r.target);
        const events = [];
        const parent = Object.create(null);
        for (const property of properties)
            Object.defineProperty(parent, property, { get() { assert.equal(this, error); events.push(property); return r.fields[property]; } });
        Object.setPrototypeOf(error, parent);
        const scope = select({ ...r.bindings, KvMutationError: { [Symbol.hasInstance](e) { assert.equal(e, error); return true; } } });
        assert.equal(scope.invoke(error), r.result);
        assert.deepEqual(events, properties);
    });
    await t.test("missing properties remain own undefined payload fields and status", () => {
        const r = rig({ input: Object.create(null), fields: { message: undefined, operationId: undefined, outcome: undefined, status: undefined } });
        assert.equal(r.invoke(), r.result);
        assert.deepEqual(r.events, ["instance", "response"]);
    });
    await t.test("proxy input receives only four ordered property reads", () => {
        const events = [];
        const values = { message: {}, operationId: Symbol("op"), outcome: false, status: 0 };
        const input = new Proxy(Object.create(null), { get(_target, key, receiver) { assert.equal(receiver, input); events.push(key); assert.ok(properties.includes(key)); return values[key]; }, ownKeys() { throw Error("enumerated error"); }, getPrototypeOf() { throw Error("prototype read"); } });
        const r = rig({ input, fields: values });
        assert.equal(r.invoke(), r.result);
        assert.deepEqual(events, properties);
        assert.deepEqual(r.events, ["instance", "response"]);
    });
    await t.test("fresh ordinary payload per call and binding selection per invocation", () => {
        const r = rig();
        assert.equal(r.invoke(), r.result);
        const first = r.payload();
        assert.equal(r.invoke(), r.result);
        assert.notEqual(r.payload(), first);
        assert.deepEqual(r.events, [...stages, ...stages]);
        const next = {};
        r.scope.replace("secretResponse", function (...args) { assert.equal(this, undefined); assert.equal(args.length, 2); return next; });
        assert.equal(r.invoke(), next);
    });
    for (const property of properties) {
        await t.test("callee captured before " + property + " getter replacement", () => {
            let r;
            const next = {};
            r = rig({ at(stage) { if (stage === property)
                    r.scope.replace("secretResponse", () => next); } });
            assert.equal(r.invoke(), r.result);
            assert.equal(r.invoke(), next);
        });
    }
    for (const branch of [true, false]) {
        await t.test("instance hook replacement precedes branch " + branch + " capture", () => {
            let r;
            const next = {};
            r = rig({ classification: branch, at(stage) { if (stage === "instance")
                    r.scope.replace(branch ? "secretResponse" : "secretErrorResponse", () => next); } });
            assert.equal(r.invoke(), next);
            assert.deepEqual(r.events, branch ? stages.slice(0, -1) : ["instance"]);
        });
    }
    for (const bad of [undefined, null, 0, {}]) {
        await t.test("noncallable response still evaluates every argument " + typeof bad, () => {
            const r = rig();
            r.scope.replace("secretResponse", bad);
            assert.throws(r.invoke, TypeError);
            assert.deepEqual(r.events, stages.slice(0, -1));
        });
        await t.test("noncallable fallback does not read error fields " + typeof bad, () => {
            const r = rig({ classification: false, input: opaque("error") });
            r.scope.replace("secretErrorResponse", bad);
            assert.throws(r.invoke, TypeError);
            assert.deepEqual(r.events, ["instance"]);
        });
    }
    for (const bad of [undefined, null, 0, {}]) {
        await t.test("invalid instanceof RHS propagates before delegates " + typeof bad, () => {
            const r = rig();
            r.scope.replace("KvMutationError", bad);
            assert.throws(r.invoke, TypeError);
            assert.deepEqual(r.events, []);
        });
    }
    for (const branch of [true, false]) {
        await t.test("throwing hasInstance getter preserves exact failure " + branch, () => {
            const failure = {};
            const r = rig({ classification: branch });
            r.scope.replace("KvMutationError", Object.defineProperty({}, Symbol.hasInstance, { get() { throw failure; } }));
            catches(r.invoke, failure);
            assert.deepEqual(r.events, []);
        });
    }
    for (const stage of [...stages, "fallback"]) {
        await t.test("same function reentrancy at " + stage, () => {
            let inside = false, nested, innerPayload;
            let r;
            const branch = stage !== "fallback";
            r = rig({ classification: branch, at(s) { if (s === stage && !inside) {
                    inside = true;
                    nested = r.invoke();
                    innerPayload = r.payload();
                    inside = false;
                } } });
            assert.equal(r.invoke(), r.result);
            assert.equal(nested, r.result);
            const expected = branch ? stages : ["instance", "fallback"];
            const offset = expected.indexOf(stage);
            assert.deepEqual(r.events, [...expected.slice(0, offset + 1), ...expected, ...expected.slice(offset + 1)]);
            if (branch)
                assert.notEqual(r.payload(), innerPayload);
        });
    }
    await t.test("classification can alternate on the same function without cached result", () => {
        const r = rig();
        let calls = 0;
        r.scope.replace("KvMutationError", { [Symbol.hasInstance]() { return ++calls % 2 === 1; } });
        assert.equal(r.invoke(), r.result);
        assert.equal(r.invoke(), r.result);
        assert.equal(r.invoke(), r.result);
        assert.equal(calls, 3);
        assert.deepEqual(r.events, [...stages.slice(1), "fallback", ...stages.slice(1)]);
    });
});
assert.equal(count, 1);
