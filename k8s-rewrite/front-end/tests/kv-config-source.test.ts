import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";

// PUBLIC SOURCE: select only kvConfig; real imports/configuration/services stay inert.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT!);
const source = readFileSync(new URL("../src/lib/kv-contract.ts", import.meta.url), "utf8");
const ast = ts.createSourceFile("kv-contract.ts", source, ts.ScriptTarget.Latest, true);
const selected = ast.statements.filter((s: { name?: { getText(): string } }) => ts.isFunctionDeclaration(s) && s.name?.getText() === "kvConfig");
assert.equal(selected.length, 1);
const declaration = selected[0];
const js = ts.transpileModule(declaration.getText().replace(/^export /, ""), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
type Config = { historyNamespace: unknown; retention: number; maxRetention: number; guardedAdoption: boolean };
type Scope = { invoke: (...args: unknown[]) => Config; replace: (name: string, value: unknown) => void };
const names = ["validateTarget", "KvError", "process", "Number", "String"];
function select(bindings: Record<string, unknown>): Scope {
  const setters = names.map(n => `case ${JSON.stringify(n)}: ${n} = value; break;`).join("\n");
  return new Function(...names, '"use strict";\n' + js + "\nreturn {invoke:kvConfig,replace(name,value){switch(name){" + setters + "default:throw Error('unknown binding')}}};")(...names.map(n => bindings[n])) as Scope;
}
function catches(fn: () => unknown, expected: unknown) {
  let caught = false;
  try { fn(); } catch (e) { caught = true; assert.equal(e, expected); }
  assert.equal(caught, true);
}
function opaque(label: string): object {
  return new Proxy(Object.create(null), { get(_t, key) { throw Error(label + " read " + String(key)); }, ownKeys() { throw Error(label + " ownKeys"); }, getPrototypeOf() { throw Error(label + " prototype"); } });
}
const H = "BORTUS_HISTORY_NAMESPACE", R = "BORTUS_KV_RETENTION", M = "BORTUS_KV_MAX_RETENTION", G = "BORTUS_KV_GUARDED_ADOPTION";
const prefix = [H, "target", R, M];
type Options = { values?: Record<string, unknown>; at?: (stage: string, count: number) => void; value?: (key: string, count: number) => unknown; targetResult?: unknown };
function rig(o: Options = {}) {
  const events: string[] = [], targets: unknown[] = [];
  const counts: Record<string, number> = {};
  const hit = (key: string) => { const count = counts[key] = (counts[key] ?? 0) + 1; events.push(key); o.at?.(key, count); return count; };
  const env = new Proxy(Object.create(null), {
    get(_t, key) { assert.equal(typeof key, "string"); const n = hit(String(key)); return o.value ? o.value(String(key), n) : o.values?.[String(key)]; },
    set() { throw Error("environment write"); }, ownKeys() { throw Error("environment enumeration"); }, getPrototypeOf() { throw Error("environment prototype"); },
  });
  class PublicError { readonly status: unknown; readonly message: unknown; constructor(status: unknown, message: unknown) { this.status = status; this.message = message; hit("error"); } }
  const scope = select({ validateTarget: function (this: unknown, ...args: unknown[]) {
    assert.equal(this, undefined); assert.equal(args.length, 1); targets.push(args[0]); hit("target"); return o.targetResult;
  }, KvError: PublicError, process: { get env() { hit("process.env"); return env; } }, Number, String });
  const invoke = () => scope.invoke(env);
  return { scope, env, events, targets, counts, PublicError, invoke };
}
function result(r: ReturnType<typeof rig>, expected: Partial<Config> = {}) {
  const config = r.invoke();
  assert.deepEqual(config, { historyNamespace: "bortus-history", retention: 20, maxRetention: 100, guardedAdoption: false, ...expected });
  return config;
}
function refuses(r: ReturnType<typeof rig>, message = "Invalid KV retention configuration") {
  assert.throws(r.invoke, e => e instanceof r.PublicError && e.status === 503 && e.message === message);
}
const failures = [undefined, null, false, 0, "public failure", Symbol("public"), opaque("failure")];

test("kvConfig finite PUBLIC SOURCE configuration controls", async t => {
  await t.test("exact exported synchronous default parameter; selection stays inert", () => {
    assert.deepEqual(declaration.modifiers.map((m: { kind: number }) => m.kind), [ts.SyntaxKind.ExportKeyword]);
    assert.equal(declaration.parameters.length, 1);
    assert.equal(declaration.parameters[0].getText(), "env: Readonly<Record<string, string | undefined>> = process.env");
    assert.equal(declaration.type.getText(), "KvConfig");
    const r = rig({ at() { throw Error("selection executed source"); } });
    assert.deepEqual(r.events, []); assert.equal(r.scope.invoke.length, 0); assert.equal(r.scope.invoke.name, "kvConfig");
  });
  await t.test("defaults read only four named properties in source order", () => {
    const r = rig(); result(r); assert.deepEqual(r.events, [...prefix, G, G]);
    assert.deepEqual(r.targets, [{ namespace: "bortus-history", name: "validation", key: "validation" }]);
  });
  for (const [i, value] of [undefined, null, false, 0, -0, NaN, ""].entries()) {
    await t.test("namespace || fallback without coercion " + i, () => { result(rig({ values: { [H]: value } })); });
  }
  for (const [i, value] of ["public-history", " ", 1, true, Symbol("namespace"), {}, opaque("namespace")].entries()) {
    await t.test("truthy namespace passed unchanged to target seam " + i, () => {
      const r = rig({ values: { [H]: value } }); result(r, { historyNamespace: value });
      assert.equal((r.targets[0] as { namespace: unknown }).namespace, value);
    });
  }
  for (const mode of ["omitted", "undefined"] as const) {
    await t.test("default uses synthetic process binding for " + mode, () => {
      const r = rig(); const config = mode === "omitted" ? r.scope.invoke() : r.scope.invoke(undefined);
      assert.equal(config.retention, 20); assert.deepEqual(r.events, ["process.env", ...prefix, G, G]);
    });
  }
  await t.test("explicit env never touches default process", () => {
    const r = rig(); r.scope.replace("process", opaque("unused process")); result(r);
  });
  await t.test("default process refusal stops all environment stages", () => {
    const failure = opaque("default failure"); const r = rig(); r.scope.replace("process", { get env() { throw failure; } });
    catches(() => r.scope.invoke(), failure); assert.deepEqual(r.events, []);
  });
  for (const stage of ["process.env", H, "target", R, M, G]) for (const [i, failure] of failures.entries()) {
    await t.test(stage + " exact thrown identity and refusal prefix " + i, () => {
      const r = rig({ at(key) { if (key === stage) throw failure; } });
      catches(stage === "process.env" ? () => r.scope.invoke() : r.invoke, failure);
      const order = stage === "process.env" ? [stage] : [...prefix, G];
      assert.deepEqual(r.events, order.slice(0, order.indexOf(stage) + 1));
    });
  }
  for (const n of [1, 2, 3]) for (const [i, failure] of failures.entries()) {
    await t.test("guarded getter refusal occurrence " + n + " identity " + i, () => {
      const r = rig({ values: { [G]: "false" }, at(key, count) { if (key === G && count === n) throw failure; } });
      catches(r.invoke, failure); assert.deepEqual(r.events, [...prefix, ...Array(n).fill(G)]);
    });
  }
  for (const key of [R, M]) {
    for (const value of [undefined, null]) await t.test(key + " nullish fallback " + String(value), () => { result(rig({ values: { [key]: value } })); });
    for (const raw of ["1", "2", "20", "99", "100"]) await t.test(key + " positive decimal boundary " + raw, () => {
      const values = { [R]: "1", [M]: "100", [key]: raw }; const r = rig({ values });
      result(r, { retention: Number(values[R]), maxRetention: Number(values[M]) });
    });
    const bad = ["", "0", "00", "01", "-1", "+1", "1.0", "1e1", "1E1", "0x10", " 1", "1 ", "\n1", "1\t", "1_0", "NaN", "Infinity", "101", "99999999999999999999999999999999", "ï¼‘", "Ù¡", "1\0", false, true, 0, -1, 1.5, NaN, Infinity, Symbol("retention")];
    for (const [i, raw] of bad.entries()) await t.test(key + " rejects invalid public grammar " + i, () => {
      const r = rig({ values: { [key]: raw } });
      if (typeof raw === "symbol") assert.throws(r.invoke, TypeError); else refuses(r);
      assert.deepEqual(r.events, key === R ? [H, "target", R, ...(typeof raw === "symbol" ? [] : ["error"])] : [...prefix, ...(typeof raw === "symbol" ? [] : ["error"])]);
    });
  }
  for (const key of [R, M]) for (const suffix of ["\n", "\r", "\r\n", "\u2028", "\u2029"]) await t.test(key + " rejects final line terminator without multiline flag " + JSON.stringify(suffix), () => {
    const r = rig({ values: { [R]: "1", [M]: "100", [key]: "2" + suffix } });
    refuses(r); assert.deepEqual(r.events, key === R ? [H, "target", R, "error"] : [...prefix, "error"]);
  });
  for (const [retention, maximum] of [[20, 19], [100, 1], [2, 1]]) await t.test("retention greater than max refuses before adoption " + retention + "/" + maximum, () => {
    const r = rig({ values: { [R]: String(retention), [M]: String(maximum) } }); refuses(r); assert.deepEqual(r.events, [...prefix, "error"]);
  });
  for (const n of [1, 20, 100]) await t.test("equal retention/max accepted " + n, () => { result(rig({ values: { [R]: String(n), [M]: String(n) } }), { retention: n, maxRetention: n }); });
  for (const raw of ["true", "false"]) await t.test("exact guarded adoption string " + raw, () => {
    const r = rig({ values: { [G]: raw } }); result(r, { guardedAdoption: raw === "true" }); assert.deepEqual(r.events, [...prefix, G, G, G]);
  });
  for (const [i, raw] of ["", "TRUE", "False", " true", "true ", "1", "0", null, false, true, 0, 1, {}, ["true"], opaque("guarded value")].entries()) {
    await t.test("guarded invalid strict value without coercion " + i, () => {
      const r = rig({ values: { [G]: raw } }); refuses(r, "Invalid guarded adoption configuration"); assert.deepEqual(r.events, [...prefix, G, G, "error"]);
    });
  }
  for (const [values, expected, reads] of [
    [[undefined, "true"], true, 2], [["true", "false", "true"], true, 3], [["false", "true", false], false, 3],
  ] as const) await t.test("repeated adoption getters retain ECMAScript source semantics " + String(values), () => {
    const r = rig({ value(key, count) { return key === G ? values[count - 1] : undefined; } });
    result(r, { guardedAdoption: expected }); assert.equal(r.counts[G], reads);
  });
  await t.test("second adoption getter validation refusal prevents third read", () => {
    const r = rig({ value(key, n) { return key === G ? n === 1 ? "true" : "invalid" : undefined; } });
    refuses(r, "Invalid guarded adoption configuration"); assert.equal(r.counts[G], 2);
  });
  await t.test("retention numeric coercions occur regex then limit then result", () => {
    const coercions: string[] = []; const value = { [Symbol.toPrimitive](hint: string) { coercions.push(hint); return "20"; } };
    result(rig({ values: { [R]: value } })); assert.deepEqual(coercions, ["string", "number", "number"]);
  });
  for (const [raw, expected] of [["invalid", ["string"]], ["101", ["string", "number"]]] as const) await t.test("retention coercion short circuit " + raw, () => {
    const coercions: string[] = []; const value = { [Symbol.toPrimitive](hint: string) { coercions.push(hint); return raw; } };
    refuses(rig({ values: { [R]: value } })); assert.deepEqual(coercions, expected);
  });
  for (const occurrence of [1, 2, 3]) for (const failure of failures) await t.test("numeric coercion exact thrown identity occurrence " + occurrence + " type " + typeof failure, () => {
    let calls = 0; const value = { [Symbol.toPrimitive]() { if (++calls === occurrence) throw failure; return "20"; } };
    const r = rig({ values: { [R]: value } }); catches(r.invoke, failure); assert.equal(calls, occurrence); assert.deepEqual(r.events, [H, "target", R]);
  });
  await t.test("number fallback calls String only for nullish raw values", () => {
    const r = rig(); const calls: unknown[] = []; r.scope.replace("String", (n: unknown) => { calls.push(n); return String(n); }); result(r); assert.deepEqual(calls, [20, 100]);
    const explicit = rig({ values: { [R]: "20", [M]: "100" } }); explicit.scope.replace("String", () => { throw Error("unexpected fallback"); }); result(explicit);
  });
  await t.test("validator return including thenable remains ignored without assimilation", () => {
    result(rig({ targetResult: opaque("unused validation return") })); result(rig({ targetResult: Promise.resolve("public") }));
  });
  await t.test("target arguments and result records are fresh ordinary objects", () => {
    const r = rig(); const a = result(r), b = result(r); assert.notEqual(a, b); assert.notEqual(r.targets[0], r.targets[1]);
    assert.equal(Object.getPrototypeOf(a), Object.prototype); assert.deepEqual(Object.keys(a), ["historyNamespace", "retention", "maxRetention", "guardedAdoption"]);
    assert.deepEqual(Object.keys(r.targets[0] as object), ["namespace", "name", "key"]);
  });
  await t.test("frozen and inherited public environments work without enumeration or writes", () => {
    const r = rig(); const values = { [H]: "public-history", [R]: "1", [M]: "2", [G]: "true" };
    for (const env of [Object.freeze({ ...values }), Object.create(values), Object.freeze(Object.assign(Object.create(null), values))]) {
      assert.deepEqual(r.scope.invoke(env), { historyNamespace: "public-history", retention: 1, maxRetention: 2, guardedAdoption: true });
    }
  });
  await t.test("fresh calls read current values without cached results", () => {
    const values: Record<string, unknown> = {}; const r = rig({ values }); result(r); values[R] = "3"; result(r, { retention: 3 });
  });
  await t.test("nested target callback runs an independent complete configuration call", () => {
    let inside = false; const r = rig({ at(key) { if (key === "target" && !inside) { inside = true; assert.equal(r.invoke().retention, 20); } } });
    result(r); assert.deepEqual(r.events, [H, "target", ...prefix, G, G, R, M, G, G]);
  });
  await t.test("later getter effects do not replace captured namespace and retention", () => {
    const values: Record<string, unknown> = { [H]: "first", [R]: "2" }; const r = rig({ values, at(key) { if (key === M) { values[H] = "later"; values[R] = "90"; } } });
    result(r, { historyNamespace: "first", retention: 2 });
  });
  for (const value of [null, undefined]) await t.test("explicit null and synthetic undefined default distinction " + String(value), () => {
    const r = rig(); if (value === null) { assert.throws(() => r.scope.invoke(value), TypeError); assert.deepEqual(r.events, []); } else { r.scope.invoke(value); assert.equal(r.events[0], "process.env"); }
  });
  await t.test("inert KvError constructor receives exact newTarget and fixed arguments", () => {
    const thrown = opaque("error constructed result"); const r = rig({ values: { [R]: "0" } });
    const ctor: object = new Proxy(function PublicFailure() {}, { construct(_t, args, nt) { assert.equal(nt, ctor); assert.deepEqual(args, [503, "Invalid KV retention configuration"]); return thrown; } });
    r.scope.replace("KvError", ctor); catches(r.invoke, thrown);
  });
  await t.test("error constructor refusal identity retained without later reads", () => {
    const failure = opaque("constructor refusal"); const r = rig({ values: { [G]: "invalid" } });
    r.scope.replace("KvError", new Proxy(function PublicFailure() {}, { construct() { throw failure; } }));
    catches(r.invoke, failure); assert.deepEqual(r.events, [...prefix, G, G]);
  });
});
