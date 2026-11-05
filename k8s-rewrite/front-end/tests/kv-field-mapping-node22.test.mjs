// DISTINCT NEW PUBLIC69 controls (68 leaf plus parent); historical controls remain frozen.
let count = 0;
const control = (...args) => { count++; return test(...args); };
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
const require = createRequire(import.meta.url);
const ts = require('typescript');
const text = readFileSync(path.resolve("src/lib/kv-contract.ts"), "utf8");
const ast = ts.createSourceFile("kv-contract.ts", text, ts.ScriptTarget.Latest, true);
const selected = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === "fieldMapping");
assert.equal(selected.length, 1);
const declaration = selected[0];
assert.ok(ts.isFunctionDeclaration(declaration));
assert.ok(declaration.modifiers?.some(node => node.kind === ts.SyntaxKind.ExportKeyword));
assert.equal(process.version, 'v22.23.3');
assert.equal(ts.version, '5.9.3');
assert.equal(declaration.getText(ast), "export function fieldMapping(value: unknown, namespace: string, name: string): { field: string; key: string }[] {\n  if (!Array.isArray(value) || !value.length || value.length > 64) throw new KvError(400, \"Map between one and 64 fields\");\n  const fields = new Set<string>(), keys = new Set<string>();\n  return value.map(item => {\n    if (!item || typeof item !== \"object\" || typeof item.field !== \"string\" || typeof item.key !== \"string\" ||\n      !/^[A-Za-z0-9._-]{1,253}$/.test(item.field))\n      throw new KvError(400, \"Invalid field mapping\");\n    validateTarget({ namespace, name, key: item.key });\n    if (fields.has(item.field) || keys.has(item.key)) throw new KvError(400, \"Field mapping must be unique\");\n    fields.add(item.field); keys.add(item.key);\n    return { field: item.field, key: item.key };\n  });\n}");
const script = ts.transpileModule(declaration.getText(ast).replace(/^export\s+/, ""), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
}).outputText + "\nfieldMapping;";
class InertError extends Error {
    status;
    constructor(status, message) { super(message); this.status = status; }
}
function fixture(bindings = {}) {
    const calls = [];
    const fn = vm.runInNewContext(script, {
        KvError: InertError,
        validateTarget(target) { calls.push(target); },
        ...bindings,
    }, { timeout: 1000 });
    return { fn, calls };
}
const invoke = (fn, value) => fn(value, "synthetic-ns", "synthetic-name");
const pairs = (value) => value.map(x => [x.field, x.key]);
const row = (field = "alpha", key = "key-a") => ({ field, key });
function refuses(fn, message) {
    assert.throws(fn, error => error instanceof InertError && error.status === 400 && error.message === message);
}
control("exact fieldMapping source with inert immediate bindings", async (t) => {
    const badArrays = [undefined, null, false, true, 0, 1, "", "x", 1n, Symbol("public"), {}, { length: 1 }, () => [], new Set(), new Uint8Array(1)];
    for (const [i, value] of badArrays.entries())
        await t.test(`nonarray ${i}`, () => {
            const { fn, calls } = fixture();
            refuses(() => invoke(fn, value), "Map between one and 64 fields");
            assert.equal(calls.length, 0);
        });
    for (const n of [0, 65])
        await t.test(`array length refuses ${n}`, () => {
            const { fn, calls } = fixture();
            refuses(() => invoke(fn, Array.from({ length: n }, (_, i) => row(`f${i}`, `k${i}`))), "Map between one and 64 fields");
            assert.equal(calls.length, 0);
        });
    for (const n of [1, 2, 64])
        await t.test(`dense success ${n}`, () => {
            const { fn, calls } = fixture();
            const input = Array.from({ length: n }, (_, i) => Object.freeze(row(`f${i}`, `k${i}`)));
            Object.freeze(input);
            const result = invoke(fn, input);
            assert.equal(result.length, n);
            assert.notEqual(result, input);
            for (let i = 0; i < n; i++) {
                assert.notEqual(result[i], input[i]);
                assert.equal(result[i].field, `f${i}`);
                assert.equal(result[i].key, `k${i}`);
                assert.deepEqual(Object.keys(result[i]), ["field", "key"]);
                assert.equal(calls[i].namespace, "synthetic-ns");
                assert.equal(calls[i].name, "synthetic-name");
                assert.equal(calls[i].key, `k${i}`);
                assert.deepEqual(Object.keys(calls[i]), ["namespace", "name", "key"]);
                if (i)
                    assert.notEqual(calls[i], calls[i - 1]);
            }
        });
    for (const field of ["A", "z", "0", ".", "_", "-", "Aa09._-", "x".repeat(253)])
        await t.test(`accepted field ${field.length}/${field[0]}`, () => {
            const { fn, calls } = fixture();
            assert.equal(invoke(fn, [row(field)])[0].field, field);
            assert.equal(calls.length, 1);
        });
    for (const [i, field] of ["", "x".repeat(254), "a b", "a/b", "é", "a\n", "\ta", "a:b", "💡"].entries())
        await t.test(`invalid field ${i}`, () => {
            const { fn, calls } = fixture();
            refuses(() => invoke(fn, [row(field)]), "Invalid field mapping");
            assert.equal(calls.length, 0);
        });
    const badItems = [undefined, null, false, true, 0, 1, "x", Symbol("public"), 1n, () => row(), {}, { field: 1, key: "a" }, { field: "a", key: 1 }, { field: new String("a"), key: "a" }, { field: "a" }];
    for (const [i, item] of badItems.entries())
        await t.test(`invalid item ${i}`, () => {
            const { fn, calls } = fixture();
            refuses(() => invoke(fn, [item]), "Invalid field mapping");
            assert.equal(calls.length, 0);
        });
    await t.test("distinct field and key namespaces, case sensitivity, order", () => {
        const { fn } = fixture();
        assert.deepEqual(pairs(invoke(fn, [row("a", "b"), row("b", "a"), row("A", "B")])), [["a", "b"], ["b", "a"], ["A", "B"]]);
    });
    for (const input of [[row("a", "x"), row("a", "y")], [row("a", "x"), row("b", "x")]])
        await t.test(`duplicate ${input[1].field}/${input[1].key}`, () => {
            const { fn, calls } = fixture();
            refuses(() => invoke(fn, input), "Field mapping must be unique");
            assert.equal(calls.length, 2);
        });
    await t.test("target fault precedes duplicate check and escapes identically", () => {
        const fault = Object.freeze({ public: "target-fault" });
        let calls = 0;
        const { fn } = fixture({ validateTarget() { if (++calls === 2)
                throw fault; } });
        assert.throws(() => invoke(fn, [row(), row()]), e => e === fault);
        assert.equal(calls, 2);
    });
    await t.test("target return is ignored; no promise consumption", () => {
        let thenReads = 0;
        const { fn } = fixture({ validateTarget() { return { get then() { thenReads++; throw Error("unreachable"); } }; } });
        assert.equal(invoke(fn, [row()])[0].field, "alpha");
        assert.equal(thenReads, 0);
    });
    await t.test("invalid field stops before target or key coercion", () => {
        let coercions = 0;
        const key = { toString() { coercions++; throw Error("unreachable"); } };
        const { fn, calls } = fixture();
        refuses(() => invoke(fn, [{ field: "bad field", key }]), "Invalid field mapping");
        assert.equal(coercions, 0);
        assert.equal(calls.length, 0);
    });
    await t.test("item getters and set operations expose exact source ordering", () => {
        const trace = [];
        let id = 0;
        class TracedSet extends Set {
            id = ++id;
            constructor() { super(); trace.push(`new${id + 1}`); }
            has(value) { trace.push(`has${this.id}:${value}`); return super.has(value); }
            add(value) { trace.push(`add${this.id}:${value}`); return super.add(value); }
        }
        const { fn } = fixture({ Set: TracedSet, validateTarget() { trace.push("target"); } });
        const item = { get field() { trace.push("field"); return "a"; }, get key() { trace.push("key"); return "k"; } };
        invoke(fn, [item]);
        assert.deepEqual(trace, ["new2", "new3", "field", "key", "field", "key", "target", "field", "has1:a", "key", "has2:k", "field", "add1:a", "key", "add2:k", "field", "key"]);
    });
    for (const property of ["field", "key"])
        await t.test(`getter fault ${property}`, () => {
            const fault = Object.freeze({ property });
            const item = { ...row(), get [property]() { throw fault; } };
            const { fn, calls } = fixture();
            assert.throws(() => invoke(fn, [item]), e => e === fault);
            assert.equal(calls.length, 0);
        });
    await t.test("array length reads short circuit before constructors and map", () => {
        const reads = [];
        const input = new Proxy([row()], { get(target, key, receiver) { reads.push(String(key)); return Reflect.get(target, key, receiver); } });
        const { fn } = fixture();
        invoke(fn, input);
        assert.deepEqual(reads.slice(0, 3), ["length", "length", "map"]);
    });
    await t.test("map fault propagates unchanged", () => {
        const fault = Object.freeze({ public: "map" });
        const input = [row()];
        Object.defineProperty(input, "map", { get() { throw fault; } });
        const { fn, calls } = fixture();
        assert.throws(() => invoke(fn, input), e => e === fault);
        assert.equal(calls.length, 0);
    });
    await t.test("custom map receiver and return characterize source only", () => {
        const input = [row()];
        const sentinel = [];
        let receiver;
        Object.defineProperty(input, "map", { value: function () { receiver = this; return sentinel; } });
        const { fn, calls } = fixture();
        assert.equal(invoke(fn, input), sentinel);
        assert.equal(receiver, input);
        assert.equal(calls.length, 0);
    });
    await t.test("sparse map behavior characterizes synthetic arrays only", () => {
        const input = new Array(2);
        input[1] = row();
        const { fn, calls } = fixture();
        const result = invoke(fn, input);
        assert.equal(result.length, 2);
        assert.equal(0 in result, false);
        assert.equal(result[1].field, "alpha");
        assert.equal(calls.length, 1);
    });
    await t.test("error constructor receives exact fixed arguments and newTarget", () => {
        const captured = [];
        const targets = [];
        class ErrorBinding {
            constructor(...args) { captured.push(args); targets.push(new.target); }
        }
        const { fn } = fixture({ KvError: ErrorBinding });
        assert.throws(() => invoke(fn, []), e => e instanceof ErrorBinding);
        assert.equal(captured.length, 1);
        assert.equal(captured[0].length, 2);
        assert.equal(captured[0][0], 400);
        assert.equal(captured[0][1], "Map between one and 64 fields");
        assert.equal(targets[0], ErrorBinding);
    });
    await t.test("fresh calls have no uniqueness state leakage", () => {
        const { fn } = fixture();
        const first = invoke(fn, [row()]);
        const second = invoke(fn, [row()]);
        assert.notEqual(first, second);
        assert.notEqual(first[0], second[0]);
    });
    await t.test("reentrant target call keeps independent sets", () => {
        let active = false;
        let fn;
        let inner = [];
        fn = fixture({ validateTarget() { if (!active) {
                active = true;
                inner = invoke(fn, [row()]);
                active = false;
            } } }).fn;
        const outer = invoke(fn, [row()]);
        assert.equal(inner[0].field, "alpha");
        assert.equal(outer[0].field, "alpha");
        assert.notEqual(inner[0], outer[0]);
    });
});
assert.equal(count, 1);
