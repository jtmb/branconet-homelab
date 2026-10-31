// DISTINCT NEW63 complete PUBLIC policy allowance controls; no application module import.
import infrastructureAssert from 'node:assert/strict';
import { createHash as infrastructureHash } from 'node:crypto';
import { readFileSync as infrastructureRead } from 'node:fs';
import { createRequire as infrastructureRequire } from 'node:module';
infrastructureAssert.equal(process.version, 'v22.23.3');
const infrastructureCompilerPath = infrastructureRequire(import.meta.url).resolve('typescript');
infrastructureAssert.match(infrastructureCompilerPath, /\/node_modules\/typescript\/lib\/typescript\.js$/);
infrastructureAssert.equal(infrastructureRequire(import.meta.url)(infrastructureCompilerPath).version, '5.9.3');
for (const [path, hash] of [
  [
    "tests/kv-policy-allows-source.test.ts",
    "8c03b92c5488d2646ab2107965767b0a8105a3636d2a712f30065764c33857f2"
  ],
  [
    "src/lib/kv-contract.ts",
    "7cbd65c81eafda98df791c3029d65757b91c9ed5278756e7ba16e1966e744199"
  ]
]) {
 infrastructureAssert.equal(infrastructureHash('sha256').update(infrastructureRead(new URL('../' + path, import.meta.url))).digest('hex'), hash, path);
}
let count = 0;
const control = (...args) => { count++; return test(...args); };
// BEGIN EXACT ORIGINAL TYPE-ERASED PROJECTION
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { createRequire } from "node:module";
import test from "node:test";
// Only this exact source export executes. Every neighboring export stays inert.
const require = createRequire(import.meta.url);
const ts = require(infrastructureCompilerPath);
const sourcePath = path.resolve(import.meta.dirname, "../src/lib/kv-contract.ts");
const text = fs.readFileSync(sourcePath, "utf8");
const source = ts.createSourceFile(sourcePath, text, ts.ScriptTarget.Latest, true);
const declarations = source.statements.filter((node) => ts.isFunctionDeclaration(node) && node.name?.text === "policyAllows");
assert.equal(declarations.length, 1);
const declaration = declarations[0];
assert.ok(declaration.modifiers?.some(m => m.kind === ts.SyntaxKind.ExportKeyword));
assert.ok(!declaration.asteriskToken && !declaration.modifiers?.some(m => m.kind === ts.SyntaxKind.AsyncKeyword));
const selected = declaration.getText(source).replace(/^export\s+/, "");
const compiled = ts.transpileModule(selected, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
const script = new vm.Script(`(function(logicalPath, parseActions, prefixMatches, KvError) { ${compiled}; return policyAllows; })`);
class FixedError extends Error {
    status;
    constructor(status, message) { super(message); this.status = status; }
}
function harness(options = {}) {
    const events = [];
    const context = vm.createContext(Object.create(null), { codeGeneration: { strings: false, wasm: false } });
    const includes = options.effects ?? function (value) {
        events.push(["effect", value]);
        return Array.prototype.includes.call(this, value);
    };
    const arrayPrototype = new vm.Script("Array.prototype").runInContext(context);
    Object.defineProperty(arrayPrototype, "includes", { value: includes, configurable: true, writable: true });
    const logicalPath = (value, root) => { events.push(["path", value, root]); return options.validate ? options.validate(value, root) : value; };
    const parseActions = raw => {
        events.push(["actions", raw]);
        if (options.parse)
            return options.parse(raw);
        assert.equal(raw, '["read"]');
        return ["read"];
    };
    const prefixMatches = (prefix, value) => { events.push(["prefix", prefix, value]); return options.prefix ? options.prefix(prefix, value) : true; };
    const factory = script.runInContext(context);
    const invoke = factory(logicalPath, parseActions, prefixMatches, options.error ?? FixedError);
    return { events, invoke, context };
}
const scope = () => ({ mountId: "mount-public", path: "apps/api" });
const rule = (changes = {}) => ({ mountId: "mount-public", prefix: "apps", effect: "allow", actions: '["read"]', ...changes });
const actions = ["list", "read", "create", "update", "delete", "rollback", "reconcile", "destroy", "export", "rotate"];
const sentinel = Object.freeze({ synthetic: "refusal" });
control("empty rules deny after requested-path validation", () => {
    const h = harness();
    assert.equal(h.invoke([], scope(), "read"), false);
    assert.deepEqual(h.events, [["path", "apps/api", undefined]]);
});
for (const action of actions)
    control(`synthetic parsed membership controls ${action}`, () => {
        const h = harness({ parse: () => [action] });
        assert.equal(h.invoke([rule()], scope(), action), true);
        assert.equal(h.invoke([rule({ effect: "deny" })], scope(), action), false);
        const other = action === "read" ? "list" : "read";
        assert.equal(h.invoke([rule()], scope(), other), false);
    });
for (const [mountId, expected] of [[null, true], ["mount-public", true], ["other", false], ["MOUNT-PUBLIC", false], ["", false]]) {
    control(`mount comparison ${String(mountId)}`, () => {
        const h = harness();
        assert.equal(h.invoke([rule({ mountId })], scope(), "read"), expected);
        assert.equal(h.events.some(e => e[0] === "prefix"), expected);
        assert.deepEqual(h.events.slice(0, 4), [["path", "apps/api", undefined], ["effect", "allow"], ["actions", '["read"]'], ["path", "apps", true]]);
    });
}
control("scope mount is exact even when empty", () => { const h = harness(); assert.equal(h.invoke([rule({ mountId: "" })], { ...scope(), mountId: "" }, "read"), true); });
control("nonmatching inert prefix denies and skips membership", () => {
    let membership = 0;
    const parsed = ["read"];
    parsed.includes = () => { membership++; return true; };
    const h = harness({ parse: () => parsed, prefix: () => false });
    assert.equal(h.invoke([rule()], scope(), "read"), false);
    assert.equal(membership, 0);
});
control("mount mismatch skips prefix and membership after metadata validation", () => {
    const h = harness({ prefix: () => { throw sentinel; }, parse: () => { const a = []; a.includes = () => { throw sentinel; }; return a; } });
    assert.equal(h.invoke([rule({ mountId: "other" })], scope(), "read"), false);
    assert.equal(h.events.length, 4);
});
control("matching rule has exact source call order", () => {
    const h = harness();
    assert.equal(h.invoke([rule()], scope(), "read"), true);
    assert.deepEqual(h.events, [["path", "apps/api", undefined], ["effect", "allow"], ["actions", '["read"]'], ["path", "apps", true], ["prefix", "apps", "apps/api"]]);
});
control("validators' transformed returns are ignored", () => {
    const h = harness({ validate: () => "ignored-transformation" });
    assert.equal(h.invoke([rule()], scope(), "read"), true);
    assert.deepEqual(h.events.at(-1), ["prefix", "apps", "apps/api"]);
});
control("empty prefix is passed to inert validation with allowRoot", () => {
    const h = harness();
    assert.equal(h.invoke([rule({ prefix: "" })], scope(), "read"), true);
    assert.deepEqual(h.events.slice(-2), [["path", "", true], ["prefix", "", "apps/api"]]);
});
for (const [label, rows, expected] of [
    ["allow then deny", [rule(), rule({ effect: "deny" })], false],
    ["deny then allow", [rule({ effect: "deny" }), rule()], false],
    ["two allows", [rule(), rule()], true],
    ["mismatched deny then allow", [rule({ effect: "deny", mountId: "other" }), rule()], true],
    ["allow then mismatched deny", [rule(), rule({ effect: "deny", mountId: "other" })], true],
    ["only mismatches", [rule({ mountId: "other" }), rule({ mountId: "elsewhere" })], false],
])
    control(`accumulation ${label}`, () => { const h = harness(); assert.equal(h.invoke(rows, scope(), "read"), expected); });
control("matching deny closes iterator and skips every later rule", () => {
    const events = [];
    const rows = { *[Symbol.iterator]() { try {
            events.push("first");
            yield rule({ effect: "deny" });
            events.push("later");
            throw sentinel;
        }
        finally {
            events.push("closed");
        } } };
    const h = harness();
    assert.equal(h.invoke(rows, scope(), "read"), false);
    assert.deepEqual(events, ["first", "closed"]);
});
control("allow continues into a later refusal", () => {
    const h = harness();
    assert.throws(() => h.invoke([rule(), rule({ effect: "corrupt" })], scope(), "read"), e => e instanceof FixedError && e.status === 503 && e.message === "KV policy metadata unavailable");
});
for (const effect of ["", "ALLOW", "Deny", "corrupt", "allow ", "__proto__"])
    control(`fixed failure for corrupt effect ${JSON.stringify(effect)}`, () => {
        const h = harness({ parse: () => { throw sentinel; } });
        assert.throws(() => h.invoke([rule({ effect, mountId: "other" })], scope(), "read"), e => e instanceof FixedError && e.status === 503 && e.message === "KV policy metadata unavailable");
        assert.equal(h.events.length, 2);
    });
control("requested path refusal precedes even iterator access", () => {
    const h = harness({ validate: () => { throw sentinel; } });
    const rows = Object.defineProperty({}, Symbol.iterator, { get() { assert.fail("iterator accessed"); } });
    assert.throws(() => h.invoke(rows, scope(), "read"), e => e === sentinel);
    assert.equal(h.events.length, 1);
});
control("rule prefix refusal precedes mount access", () => {
    const h = harness({ validate: (v, root) => { if (root)
            throw sentinel; return v; } });
    const r = rule();
    Object.defineProperty(r, "mountId", { get() { assert.fail("mount accessed"); } });
    assert.throws(() => h.invoke([r], scope(), "read"), e => e === sentinel);
    assert.equal(h.events.length, 4);
});
control("parser refusal precedes prefix access even for unrelated mount", () => {
    const h = harness({ parse: () => { throw sentinel; } });
    const r = rule({ mountId: "other" });
    Object.defineProperty(r, "prefix", { get() { assert.fail("prefix accessed"); } });
    assert.throws(() => h.invoke([r], scope(), "read"), e => e === sentinel);
    assert.equal(h.events.length, 3);
});
control("prefix binding refusal propagates unchanged", () => { const h = harness({ prefix: () => { throw sentinel; } }); assert.throws(() => h.invoke([rule()], scope(), "read"), e => e === sentinel); });
control("action membership uses its returned-array receiver", () => {
    const parsed = [];
    let called = false;
    parsed.includes = function (value) { assert.equal(this, parsed); assert.equal(value, "read"); called = true; return true; };
    const h = harness({ parse: () => parsed });
    assert.equal(h.invoke([rule()], scope(), "read"), true);
    assert.ok(called);
});
control("membership lookup refusal propagates unchanged", () => {
    const parsed = [];
    Object.defineProperty(parsed, "includes", { get() { throw sentinel; } });
    const h = harness({ parse: () => parsed });
    assert.throws(() => h.invoke([rule()], scope(), "read"), e => e === sentinel);
});
control("membership call refusal propagates unchanged", () => {
    const parsed = [];
    parsed.includes = () => { throw sentinel; };
    const h = harness({ parse: () => parsed });
    assert.throws(() => h.invoke([rule()], scope(), "read"), e => e === sentinel);
});
control("effect literal includes receiver and refusal are explicit inert builtins", () => {
    const h = harness({ effects: function (value) { assert.deepEqual(Array.from(this), ["allow", "deny"]); assert.equal(value, "allow"); throw sentinel; } });
    assert.throws(() => h.invoke([rule()], scope(), "read"), e => e === sentinel);
    assert.equal(h.events.length, 1);
});
for (const field of ["effect", "actions", "prefix", "mountId"])
    control(`synthetic rule ${field} getter refusal propagates`, () => {
        const r = rule();
        Object.defineProperty(r, field, { get() { throw sentinel; } });
        const h = harness();
        assert.throws(() => h.invoke([r], scope(), "read"), e => e === sentinel);
    });
for (const field of ["path", "mountId"])
    control(`synthetic scope ${field} getter refusal propagates`, () => {
        const s = scope();
        Object.defineProperty(s, field, { get() { throw sentinel; } });
        const h = harness();
        assert.throws(() => h.invoke([rule()], s, "read"), e => e === sentinel);
    });
control("null global mount skips scope mount getter", () => {
    const s = scope();
    Object.defineProperty(s, "mountId", { get() { throw sentinel; } });
    const h = harness();
    assert.equal(h.invoke([rule({ mountId: null })], s, "read"), true);
});
control("matching effect is reread after membership", () => {
    const r = rule();
    let reads = 0;
    Object.defineProperty(r, "effect", { get() { reads++; return reads === 1 ? "allow" : "deny"; } });
    const h = harness();
    assert.equal(h.invoke([r], scope(), "read"), false);
    assert.equal(reads, 2);
});
control("nonmatching effect is not reread", () => {
    const r = rule({ mountId: "other" });
    let reads = 0;
    Object.defineProperty(r, "effect", { get() { reads++; if (reads > 1)
            throw sentinel; return "allow"; } });
    const h = harness();
    assert.equal(h.invoke([r], scope(), "read"), false);
    assert.equal(reads, 1);
});
control("source rereads prefix and requested path at prefix dispatch", () => {
    let paths = 0;
    let prefixes = 0;
    const s = scope();
    const r = rule();
    Object.defineProperty(s, "path", { get() { return ++paths === 1 ? "first-path" : "second-path"; } });
    Object.defineProperty(r, "prefix", { get() { return ++prefixes === 1 ? "first-prefix" : "second-prefix"; } });
    const h = harness();
    assert.equal(h.invoke([r], s, "read"), true);
    assert.deepEqual(h.events.at(-1), ["prefix", "second-prefix", "second-path"]);
    assert.equal(paths, 2);
    assert.equal(prefixes, 2);
});
control("fresh calls do not cache allow, deny or parsed actions", () => {
    let parsed = 0;
    const h = harness({ parse: () => { parsed++; return ["read"]; } });
    const r = rule();
    assert.equal(h.invoke([r], scope(), "read"), true);
    r.effect = "deny";
    assert.equal(h.invoke([r], scope(), "read"), false);
    assert.equal(h.invoke([], scope(), "read"), false);
    r.effect = "allow";
    assert.equal(h.invoke([r], scope(), "read"), true);
    assert.equal(parsed, 3);
});
control("each corrupt effect creates a fresh fixed error", () => {
    const h = harness();
    const errors = [];
    for (let i = 0; i < 2; i++) {
        try {
            h.invoke([rule({ effect: "bad" })], scope(), "read");
            assert.fail("expected refusal");
        }
        catch (e) {
            errors.push(e);
        }
    }
    assert.notEqual(errors[0], errors[1]);
    for (const e of errors)
        assert.ok(e instanceof FixedError && e.status === 503 && e.message === "KV policy metadata unavailable");
});
control("direct inert error-constructor refusal propagates", () => {
    class Refusal extends Error {
        constructor() { super(); throw sentinel; }
    }
    const h = harness({ error: Refusal });
    assert.throws(() => h.invoke([rule({ effect: "bad" })], scope(), "read"), e => e === sentinel);
});
control("iterator acquisition refusal propagates", () => {
    const rows = Object.defineProperty({}, Symbol.iterator, { get() { throw sentinel; } });
    const h = harness();
    assert.throws(() => h.invoke(rows, scope(), "read"), e => e === sentinel);
});
control("iterator next refusal propagates after allow", () => {
    const rows = { *[Symbol.iterator]() { yield rule(); throw sentinel; } };
    const h = harness();
    assert.throws(() => h.invoke(rows, scope(), "read"), e => e === sentinel);
});
control("metadata refusal closes the iterator", () => {
    let closed = false;
    const rows = { *[Symbol.iterator]() { try {
            yield rule({ effect: "bad" });
        }
        finally {
            closed = true;
        } } };
    const h = harness();
    assert.throws(() => h.invoke(rows, scope(), "read"), e => e instanceof FixedError);
    assert.ok(closed);
});
control("frozen supported inputs remain unchanged", () => {
    const r = Object.freeze(rule());
    const s = Object.freeze(scope());
    const rows = Object.freeze([r]);
    const before = JSON.stringify({ rows, s });
    const h = harness();
    assert.equal(h.invoke(rows, s, "read"), true);
    assert.equal(JSON.stringify({ rows, s }), before);
});
control("nested independent calls keep local accumulator state", () => {
    let nested = false;
    let h;
    h = harness({ prefix: () => { if (!nested) {
            nested = true;
            assert.equal(h.invoke([], scope(), "read"), false);
        } return true; } });
    assert.equal(h.invoke([rule()], scope(), "read"), true);
    assert.ok(nested);
});
control("VM blocks constructor-generated code", () => {
    const h = harness();
    assert.throws(() => new vm.Script("(function(){}).constructor('return 1')()").runInContext(h.context), /Code generation from strings disallowed/);
});
// END EXACT ORIGINAL TYPE-ERASED PROJECTION
infrastructureAssert.equal(count, 63);
