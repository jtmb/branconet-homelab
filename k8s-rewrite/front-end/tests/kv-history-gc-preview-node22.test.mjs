// DISTINCT NEW PUBLIC54 controls (53 leaf plus parent); historical controls remain frozen.
let count = 0;
const control = (...args) => { count++; return test(...args); };
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
// Finite PUBLIC SOURCE controls. Only the selected POST initializer executes.
// All real imports, body/schema validation, registry and engine services stay inert.
const require = createRequire(import.meta.url);
const ts = require('typescript');
const source = readFileSync(new URL("../src/app/api/kv/history/gc/preview/route.ts", import.meta.url), "utf8");
const ast = ts.createSourceFile("route.ts", source, ts.ScriptTarget.Latest, true);
const variables = ast.statements.flatMap((s) => s.declarationList?.declarations ?? []);
const post = variables.find((d) => d.name.getText() === "POST");
assert.ok(post);
assert.equal(post.initializer.expression.getText(), "kvHuman");
assert.equal(post.initializer.arguments.length, 1);
const callback = post.initializer.arguments[0];
assert.ok(ts.isArrowFunction(callback));
assert.equal(callback.modifiers.length, 1);
assert.equal(callback.modifiers[0].kind, ts.SyntaxKind.AsyncKeyword);
assert.deepEqual(callback.parameters.map((p) => p.name.getText()), ["registry", "actor", "request"]);
assert.equal(process.version, 'v22.23.3');
assert.equal(ts.version, '5.9.3');
assert.equal(post.initializer.getText(), "kvHuman(async (registry, actor, request) => {\n  const input = await kvBody(request, historyGcPreview);\n  return kvEngine(registry).gcPreview(actor, input.pathId);\n})");
const js = ts.transpileModule("return (" + post.initializer.getText() + ");", { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
function select(deps) {
    let captured;
    const returned = {};
    const wrapper = function (...args) {
        assert.equal(this, undefined);
        assert.equal(args.length, 1);
        assert.equal(typeof args[0], "function");
        captured = args[0];
        return returned;
    };
    const result = new Function("kvHuman", "kvBody", "kvEngine", "historyGcPreview", '"use strict";\n' + js)(wrapper, deps.kvBody, deps.kvEngine, deps.historyGcPreview);
    assert.equal(result, returned);
    assert.ok(captured);
    return captured;
}
function opaque(label) {
    return new Proxy(Object.create(null), { get() { throw new Error(label + " read"); }, ownKeys() { throw new Error(label + " keys"); }, getPrototypeOf() { throw new Error(label + " prototype"); } });
}
function deferred() {
    let resolve;
    let reject;
    const promise = new Promise((a, b) => { resolve = a; reject = b; });
    return { promise, resolve, reject };
}
const turn = () => Promise.resolve();
control("human history-GC-preview POST finite SOURCE controls", async (t) => {
    await t.test("exact import/export and wrapper boundary", () => {
        const imports = ast.statements.filter((s) => ts.isImportDeclaration(s));
        assert.deepEqual(imports.map((s) => s.getText()), [
            'import { kvBody, kvEngine, kvHuman } from "@/lib/kv-http";',
            'import { historyGcPreview } from "@/lib/kv-schemas";',
        ]);
        assert.equal(variables.length, 2);
        assert.equal(variables[0].name.getText(), "runtime");
        assert.equal(variables[0].initializer.getText(), '"nodejs"');
        assert.equal(ast.statements.length, 4);
        const statements = callback.body.statements;
        assert.equal(statements.length, 2);
        assert.equal(statements[0].getText(), "const input = await kvBody(request, historyGcPreview);");
        assert.equal(statements[1].getText(), "return kvEngine(registry).gcPreview(actor, input.pathId);");
        select({ kvBody() { throw Error("wrapper ran body"); }, kvEngine() { throw Error("wrapper ran engine"); }, historyGcPreview: opaque("schema") });
    });
    for (const pathId of [undefined, null, false, true, 0, -1, "", "public/path", Symbol("public-path"), {}, [], opaque("pathId")]) {
        await t.test("exact arguments and opaque identity for synthetic pathId " + typeof pathId + ":" + (pathId === null ? "null" : typeof pathId === "object" ? "object" : String(pathId)), async () => {
            const events = [];
            const registry = opaque("registry"), actor = opaque("actor"), request = opaque("request"), schema = opaque("schema");
            const result = opaque("result");
            // A nonthenable result is required because async return must inspect then.
            const final = { result };
            const input = Object.defineProperty({}, "pathId", { get() { events.push("pathId"); return pathId; } });
            const engine = Object.defineProperty({}, "gcPreview", { get() {
                    events.push("method");
                    return function (...args) {
                        events.push("call");
                        assert.equal(this, engine);
                        assert.deepEqual(args, [actor, pathId]);
                        return final;
                    };
                } });
            const handler = select({ kvBody: function (...args) { events.push("body"); assert.equal(this, undefined); assert.deepEqual(args, [request, schema]); return input; }, kvEngine: function (...args) { events.push("engine"); assert.equal(this, undefined); assert.deepEqual(args, [registry]); return engine; }, historyGcPreview: schema });
            const pending = handler(registry, actor, request);
            assert.ok(pending instanceof Promise);
            assert.deepEqual(events, ["body"]);
            assert.equal(await pending, final);
            assert.deepEqual(events, ["body", "engine", "method", "pathId", "call"]);
        });
    }
    for (const kind of ["plain", "resolved", "pending", "thenable"]) {
        await t.test("body " + kind + " adoption fences all downstream reads", async () => {
            const events = [], hold = deferred(), id = {};
            const input = Object.defineProperty({}, "pathId", { get() { events.push("path"); return id; } });
            let body = input;
            if (kind === "resolved")
                body = Promise.resolve(input);
            if (kind === "pending")
                body = hold.promise;
            if (kind === "thenable")
                body = { then(resolve) { events.push("then"); resolve(input); } };
            const handler = select({ kvBody() { events.push("body"); return body; }, kvEngine() { events.push("engine"); return { gcPreview(...args) { assert.equal(args[1], id); events.push("call"); return "ok"; } }; }, historyGcPreview: {} });
            const p = handler({}, {}, {});
            assert.deepEqual(events, ["body"]);
            if (kind === "pending") {
                await turn();
                assert.deepEqual(events, ["body"]);
                hold.resolve(input);
            }
            assert.equal(await p, "ok");
            assert.deepEqual(events, kind === "thenable" ? ["body", "then", "engine", "path", "call"] : ["body", "engine", "path", "call"]);
        });
    }
    for (const kind of ["throw", "reject", "then-getter", "then-call"]) {
        await t.test("body refusal " + kind + " stops before engine and input", async () => {
            const failure = {}, events = [];
            const handler = select({ kvBody() {
                    events.push("body");
                    if (kind === "throw")
                        throw failure;
                    if (kind === "reject")
                        return Promise.reject(failure);
                    if (kind === "then-getter")
                        return Object.defineProperty({}, "then", { get() { events.push("then"); throw failure; } });
                    return { then() { events.push("then"); throw failure; } };
                }, kvEngine() { throw Error("forbidden engine"); }, historyGcPreview: {} });
            const p = handler(opaque("registry"), opaque("actor"), opaque("request"));
            await assert.rejects(p, x => x === failure);
            assert.deepEqual(events, kind.startsWith("then") ? ["body", "then"] : ["body"]);
        });
    }
    for (const kind of ["engine-throw", "engine-null", "engine-undefined", "method-getter", "method-null", "method-number", "input-null", "input-undefined", "path-getter", "invoke-throw", "invoke-reject"]) {
        await t.test("downstream refusal exact stop " + kind, async () => {
            const events = [], failure = {};
            const input = kind === "input-null" ? null : kind === "input-undefined" ? undefined : Object.defineProperty({}, "pathId", { get() { events.push("path"); if (kind === "path-getter")
                    throw failure; return "id"; } });
            const handler = select({ kvBody() { events.push("body"); return input; }, kvEngine() {
                    events.push("engine");
                    if (kind === "engine-throw")
                        throw failure;
                    if (kind === "engine-null")
                        return null;
                    if (kind === "engine-undefined")
                        return undefined;
                    return Object.defineProperty({}, "gcPreview", { get() {
                            events.push("method");
                            if (kind === "method-getter")
                                throw failure;
                            if (kind === "method-null")
                                return null;
                            if (kind === "method-number")
                                return 42;
                            return () => { events.push("invoke"); if (kind === "invoke-reject")
                                return Promise.reject(failure); throw failure; };
                        } });
                }, historyGcPreview: {} });
            const p = handler({}, {}, {});
            const typeError = ["engine-null", "engine-undefined", "method-null", "method-number", "input-null", "input-undefined"].includes(kind);
            await assert.rejects(p, x => typeError ? x instanceof TypeError : x === failure);
            const expected = ["body", "engine"];
            if (!kind.startsWith("engine-"))
                expected.push("method");
            if (!kind.startsWith("engine-") && !["method-getter", "input-null", "input-undefined"].includes(kind))
                expected.push("path");
            if (kind.startsWith("invoke-"))
                expected.push("invoke");
            assert.deepEqual(events, expected);
        });
    }
    for (const kind of ["inherited-path", "inherited-method", "input-proxy", "engine-proxy", "missing-path", "primitive-input", "captured-method"]) {
        await t.test("property semantics " + kind, async () => {
            const events = [], actor = {}, id = {};
            let engine;
            const method = function (...args) { events.push("call"); assert.equal(this, engine); assert.deepEqual(args, [actor, ["missing-path", "primitive-input"].includes(kind) ? undefined : id]); return "done"; };
            const base = { gcPreview: method };
            engine = kind === "inherited-method" ? Object.create(base) : { ...base };
            if (kind === "engine-proxy")
                engine = new Proxy(engine, { get(target, key, receiver) { events.push(String(key)); return Reflect.get(target, key, receiver); } });
            let input = { pathId: id };
            if (kind === "inherited-path")
                input = Object.create({ pathId: id });
            if (kind === "missing-path")
                input = {};
            if (kind === "primitive-input")
                input = 4;
            if (kind === "input-proxy")
                input = new Proxy({ pathId: id }, { get(target, key, receiver) { events.push(String(key)); return Reflect.get(target, key, receiver); }, ownKeys() { throw Error("enumeration forbidden"); } });
            if (kind === "captured-method")
                input = Object.defineProperty({}, "pathId", { get() { Object.defineProperty(engine, "gcPreview", { value() { throw Error("replacement ran"); } }); events.push("replace"); return id; } });
            const handler = select({ kvBody() { return input; }, kvEngine() { return engine; }, historyGcPreview: {} });
            assert.equal(await handler({}, actor, opaque("request")), "done");
            assert.deepEqual(events, kind === "engine-proxy" ? ["gcPreview", "call"] : kind === "input-proxy" ? ["then", "pathId", "call"] : kind === "captured-method" ? ["replace", "call"] : ["call"]);
        });
    }
    for (const kind of ["plain", "resolved", "pending", "thenable", "then-getter-throw", "then-reject", "settle-once"]) {
        await t.test("async result adoption " + kind, async () => {
            const hold = deferred(), final = {}, failure = {}, events = [];
            let value = final;
            if (kind === "resolved")
                value = Promise.resolve(final);
            if (kind === "pending")
                value = hold.promise;
            if (kind === "thenable")
                value = { then(resolve) { events.push("then"); resolve(final); } };
            if (kind === "then-getter-throw")
                value = Object.defineProperty({}, "then", { get() { events.push("then"); throw failure; } });
            if (kind === "then-reject")
                value = { then(_resolve, reject) { events.push("then"); reject(failure); } };
            if (kind === "settle-once")
                value = { then(resolve, reject) { events.push("then"); resolve(final); reject(failure); resolve({}); throw failure; } };
            const handler = select({ kvBody() { return { pathId: "id" }; }, kvEngine() { return { gcPreview() { events.push("invoke"); return value; } }; }, historyGcPreview: {} });
            const p = handler({}, {}, {});
            if (kind === "pending") {
                await turn();
                assert.deepEqual(events, ["invoke"]);
                hold.resolve(final);
            }
            if (["then-getter-throw", "then-reject"].includes(kind))
                await assert.rejects(p, x => x === failure);
            else
                assert.equal(await p, final);
            assert.deepEqual(events, ["thenable", "then-getter-throw", "then-reject", "settle-once"].includes(kind) ? ["invoke", "then"] : ["invoke"]);
        });
    }
    await t.test("same callback fresh calls and independent engine identities", async () => {
        const seen = [];
        const handler = select({ kvBody(request) { return { pathId: request }; }, kvEngine(registry) { return { gcPreview(actor, id) { const result = { registry, actor, id }; seen.push(result); return result; } }; }, historyGcPreview: {} });
        for (let i = 0; i < 3; i++) {
            const registry = {}, actor = {}, request = {};
            assert.deepEqual(await handler(registry, actor, request), { registry, actor, id: request });
        }
        assert.equal(new Set(seen).size, 3);
    });
    await t.test("one callback interleaved bodies and reverse result settlement", async () => {
        const bodies = [deferred(), deferred()], results = [deferred(), deferred()], actors = [{}, {}], registries = [{}, {}], requests = [{}, {}], ids = [{}, {}], events = [];
        const handler = select({ kvBody(request) { const i = requests.indexOf(request); events.push("body" + i); return bodies[i].promise; }, kvEngine(registry) { const i = registries.indexOf(registry); events.push("engine" + i); return { gcPreview(...args) { assert.deepEqual(args, [actors[i], ids[i]]); events.push("call" + i); return results[i].promise; } }; }, historyGcPreview: {} });
        const a = handler(registries[0], actors[0], requests[0]), b = handler(registries[1], actors[1], requests[1]);
        assert.deepEqual(events, ["body0", "body1"]);
        bodies[1].resolve({ pathId: ids[1] });
        await turn();
        bodies[0].resolve({ pathId: ids[0] });
        await turn();
        assert.deepEqual(events, ["body0", "body1", "engine1", "call1", "engine0", "call0"]);
        const x = {}, y = {};
        results[0].resolve(x);
        results[1].resolve(y);
        assert.equal(await a, x);
        assert.equal(await b, y);
    });
    for (const stage of ["body", "engine", "method", "path", "invoke"]) {
        await t.test("same callback synchronous reentrancy at " + stage, async () => {
            const outer = {}, inner = {}, final = {}, innerFinal = {}, events = [];
            let nested, did = false;
            const reenter = (at) => { if (at === stage && !did) {
                did = true;
                events.push("reenter");
                nested = handler(inner, inner, inner);
            } };
            const handler = select({ kvBody(request) { if (request === outer)
                    reenter("body"); return Object.defineProperty({}, "pathId", { get() { if (request === outer)
                        reenter("path"); return request; } }); }, kvEngine(registry) { if (registry === outer)
                    reenter("engine"); const engine = Object.defineProperty({}, "gcPreview", { get() { if (registry === outer)
                        reenter("method"); return function (actor, id) { assert.equal(this, engine); assert.equal(actor, registry); assert.equal(id, registry); if (registry === outer)
                        reenter("invoke"); events.push(registry === outer ? "outer" : "inner"); return registry === outer ? final : innerFinal; }; } }); return engine; }, historyGcPreview: {} });
            assert.equal(await handler(outer, outer, outer), final);
            assert.ok(nested);
            assert.equal(await nested, innerFinal);
            assert.equal(events.filter(x => x === "reenter").length, 1);
            assert.equal(events.filter(x => x === "outer").length, 1);
            assert.equal(events.filter(x => x === "inner").length, 1);
        });
    }
});
assert.equal(count, 1);
