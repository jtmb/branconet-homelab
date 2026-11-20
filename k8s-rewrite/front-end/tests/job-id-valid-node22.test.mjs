import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { createContext, runInContext } from "node:vm";
import test from "node:test";

// Distinct PUBLIC255 controls; original controls remain frozen and unevaluated.
// Only selected declaration executes; modules/imports/initializers/neighbours inert.
assert.equal(process.version, "v22.23.3");
const ts = createRequire(import.meta.url)("typescript");
assert.equal(ts.version, "5.9.3");
const sourcePath = fileURLToPath(new URL("../src/lib/job-output.ts", import.meta.url));
const source = readFileSync(sourcePath, "utf8");
const parsed = ts.createSourceFile(sourcePath, source, ts.ScriptTarget.ESNext, true, ts.ScriptKind.TS);
const declarations = parsed.statements.filter((node) => ts.isFunctionDeclaration(node) && node.name?.text === "jobIdValid");
assert.equal(declarations.length, 1);
const declaration = declarations[0];
assert.ok(declaration.modifiers?.some((modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword));
assert.ok(declaration.body);
const selected = declaration.getText(parsed).replace(/\r\n/g, "\n");
assert.equal(selected, 'export function jobIdValid(value: string | null): value is string {\n  return typeof value === "string" && /^[A-Za-z0-9_-]{1,128}$/.test(value);\n}');
const executable = ts.transpileModule(selected.replace(/^export\s+/, ""), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
}).outputText;
export {};
let count = 0;
const control = (...args) => { count++; return test(...args); };
function fresh() {
    const context = createContext(Object.create(null), { codeGeneration: { strings: false, wasm: false } });
    const guard = runInContext(executable + "\njobIdValid;", context, { timeout: 1000 });
    return { context, guard };
}
const ordinary = fresh().guard;
function member(value) {
    if (value === null || value.length === 0 || value.length > 128)
        return false;
    return Array.from(value).every((character) => {
        const code = character.charCodeAt(0);
        return (code >= 65 && code <= 90) || (code >= 97 && code <= 122) || (code >= 48 && code <= 57) || code === 95 || code === 45;
    });
}
control("only the exact exported declaration is selected; no app module initializers run", () => {
    assert.equal(declaration.parameters.length, 1);
    assert.ok(declaration.type && ts.isTypePredicateNode(declaration.type));
    assert.equal(declaration.type.getText(parsed), "value is string");
    assert.equal(declaration.parameters[0].type?.getText(parsed), "string | null");
});
for (let code = 0; code < 128; code++) {
    control(`ASCII singleton ${code}`, () => {
        const value = String.fromCharCode(code);
        assert.equal(ordinary(value), member(value));
    });
}
for (const length of [0, 1, 2, 63, 64, 127, 128, 129, 256]) {
    control(`PUBLIC mixed identifier length ${length}`, () => {
        const value = "PUBLIC_job-09AZaz_".repeat(16).slice(0, length);
        assert.equal(value.length, length);
        assert.equal(ordinary(value), member(value));
    });
}
for (const value of ["A", "Z", "a", "z", "0", "9", "_", "-"]) {
    for (const length of [127, 128, 129]) {
        control(`boundary character ${value.charCodeAt(0)} length ${length}`, () => {
            assert.equal(ordinary(value.repeat(length)), length <= 128);
        });
    }
}
const excluded = ["\0", "\n", "\r", "\r\n", "\t", " ", ".", "/", "\\", ":", "%", "?", "#", "\u007f", "\u0085", "\u00a0", "\u00e9", "e\u0301", "\u200b", "\u2028", "\u2029", "\ufeff", "\uFF21", "\uD800", "\uDC00", "\uD83D\uDE80"];
for (const [index, fragment] of excluded.entries()) {
    for (const position of ["prefix", "middle", "suffix"]) {
        control(`excluded PUBLIC fragment ${index} at ${position}`, () => {
            const value = position === "prefix" ? fragment + "PUBLIC_09" : position === "middle" ? "PUBLIC" + fragment + "_09" : "PUBLIC_09" + fragment;
            assert.equal(ordinary(value), false);
        });
    }
}
control("null short circuits before even reading RegExp test", () => {
    const { context, guard } = fresh();
    const trace = [];
    context.lookup = () => { trace.push("get:test"); throw new Error("PUBLIC inert getter fault"); };
    runInContext('Object.defineProperty(RegExp.prototype, "test", { get: lookup });', context);
    assert.equal(guard(null), false);
    assert.deepEqual(trace, []);
});
for (const value of ["PUBLIC_09", "", "PUBLIC_09\n", "x".repeat(129)]) {
    control(`string reaches getter then test unchanged; length ${value.length}`, () => {
        const { context, guard } = fresh();
        const trace = [];
        context.lookup = function () {
            trace.push("get:test");
            return function (input) {
                trace.push(["call:test", input, this.source, this.flags, this.lastIndex]);
                return false;
            };
        };
        runInContext('Object.defineProperty(RegExp.prototype, "test", { get: lookup });', context);
        assert.equal(guard(value), false);
        assert.deepEqual(trace, ["get:test", ["call:test", value, "^[A-Za-z0-9_-]{1,128}$", "", 0]]);
    });
}
for (const phase of ["getter", "method"]) {
    control(`immediate inert ${phase} fault propagates by identity`, () => {
        const { context, guard } = fresh();
        const fault = new Error("PUBLIC immediate fault");
        const trace = [];
        context.lookup = () => {
            trace.push("get:test");
            if (phase === "getter")
                throw fault;
            return () => { trace.push("call:test"); throw fault; };
        };
        runInContext('Object.defineProperty(RegExp.prototype, "test", { get: lookup });', context);
        assert.throws(() => guard("PUBLIC_09"), (error) => error === fault);
        assert.deepEqual(trace, phase === "getter" ? ["get:test"] : ["get:test", "call:test"]);
    });
}
control("noncallable injected test gives the realm TypeError", () => {
    const { context, guard } = fresh();
    runInContext('Object.defineProperty(RegExp.prototype, "test", { value: null });', context);
    const realmTypeError = runInContext("TypeError", context);
    assert.throws(() => guard("PUBLIC_09"), realmTypeError);
});
for (const result of [false, true, null, 0, 1, "PUBLIC inert result"]) {
    control(`inert test replacement return is passed through: ${String(result)}`, () => {
        const { context, guard } = fresh();
        context.replacement = () => result;
        runInContext('Object.defineProperty(RegExp.prototype, "test", { value: replacement });', context);
        assert.equal(guard("PUBLIC_09"), result);
    });
}
control("each call creates a new unflagged literal; no test receiver state survives", () => {
    const { context, guard } = fresh();
    const receivers = [];
    context.replacement = function (value) {
        receivers.push(this);
        assert.equal(this.lastIndex, 0);
        this.lastIndex = 27;
        return value === "PUBLIC_09";
    };
    runInContext('Object.defineProperty(RegExp.prototype, "test", { value: replacement });', context);
    assert.equal(guard("PUBLIC_09"), true);
    assert.equal(guard("PUBLIC_09"), true);
    assert.equal(receivers.length, 2);
    assert.notEqual(receivers[0], receivers[1]);
});
assert.equal(count, 255);
