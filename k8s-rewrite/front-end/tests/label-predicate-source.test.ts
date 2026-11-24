import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

type Labels = Record<string, string>;
type Predicate = (selector: string | null) => (labels: Labels) => boolean;
const source = readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), "../src/lib/pod-query.ts"), "utf8");
const selected = source.match(/^export function labelPredicate\(selector: string \| null\): \(labels: Record<string, string>\) => boolean \{[\s\S]*?^\}/m)?.[0];
assert.ok(selected);
const declaration = stripTypeScriptTypes(selected.replace(/^export /, ""));
function fixture(options: { rejectKey?: string; rejectValue?: string; failOwn?: boolean; failKey?: boolean; failValue?: boolean; failError?: boolean } = {}) {
  const events: string[] = [];
  const rejected = new Error("synthetic selector refusal");
  const fault = new Error("synthetic dependency fault");
  const predicate = vm.runInNewContext(`${declaration}\nlabelPredicate;`, {
    selectorError: () => { events.push("error"); if (options.failError) throw fault; return rejected; },
    validKey: (key: string) => { events.push(`key:${key}`); if (options.failKey) throw fault; if (key === options.rejectKey) throw rejected; },
    validValue: (value: string) => { events.push(`value:${value}`); if (options.failValue) throw fault; return value !== options.rejectValue; },
    Object: { hasOwn: (labels: Labels, key: string) => { events.push(`own:${key}`); if (options.failOwn) throw fault; return Object.hasOwn(labels, key); } },
  }) as Predicate;
  return { predicate, events, rejected, fault };
}
const labels = (entries: Labels = {}): Labels => Object.assign(Object.create(null), entries);
for (const selector of [null, ""]) test(`empty ${String(selector)} bypasses all dependencies`, () => {
  const f = fixture({ failKey: true, failValue: true, failOwn: true, failError: true });
  const p = f.predicate(selector); assert.equal(p(labels()), true); assert.equal(p(labels({ a: "x" })), true); assert.deepEqual(f.events, []);
});
for (const [selector, sample, expected] of [
  ["a", {}, false], ["a", { a: "" }, true], ["a", { a: "x" }, true],
  ["!a", {}, true], ["!a", { a: "" }, false],
  ["a=x", { a: "x" }, true], ["a=x", {}, false], ["a=x", { a: "y" }, false],
  ["a==x", { a: "x" }, true], ["a!=x", {}, true], ["a!=x", { a: "y" }, true], ["a!=x", { a: "x" }, false],
  ["a=", { a: "" }, true], ["a==", {}, false], ["a!=", { a: "" }, false],
  ["a in (x,y)", { a: "x" }, true], ["a in (x,y)", { a: "y" }, true], ["a in (x,y)", { a: "z" }, false], ["a in (x,y)", {}, false],
  ["a notin (x,y)", {}, true], ["a notin (x,y)", { a: "x" }, false], ["a notin (x,y)", { a: "z" }, true],
  [" a = x ", { a: "x" }, true], ["a\tin\t( x , y )", { a: "y" }, true],
  ["a in(x)", { a: "x" }, true], ["a notin(x)", {}, true],
  ["a=x,b=y", { a: "x", b: "y" }, true], ["a=x,b=y", { a: "x", b: "z" }, false],
  ["a=x,a!=x", { a: "x" }, false], ["a in (x,x)", { a: "x" }, true],
  ["public.example/key_1=x.y-z_0", { "public.example/key_1": "x.y-z_0" }, true],
] as [string, Labels, boolean][]) test(`synthetic selector ${selector} ${JSON.stringify(sample)}`, () => {
  const f = fixture(); assert.equal(f.predicate(selector)(labels(sample)), expected);
});
for (const selector of [" ", ",", "a,", ",a", "a,,b", "a===x", "a > x", "a in ()", "a in ( )", "a in (,x)", "a in (x,)", "a in (x,,y)", "a in ((x))", "a in (x", "a IN (x)", "a notIn (x)", "!a=x", "!a!=x", "!a in (x)", "!!a", "a?", "a=x/y", "a=x y", "a in (x)tail", "a=(x)", "a\nb"]) test(`synthetic syntax refusal ${JSON.stringify(selector)}`, () => {
  const f = fixture(); assert.throws(() => f.predicate(selector), e => e === f.rejected);
});
test("selector 2048 limit is inclusive before key dependency", () => { const f = fixture(); assert.equal(f.predicate("k".repeat(2048))(labels()), false); assert.equal(f.events[0], `key:${"k".repeat(2048)}`); });
test("selector 2049 refuses before key dependency", () => { const f = fixture(); assert.throws(() => f.predicate("k".repeat(2049)), e => e === f.rejected); assert.deepEqual(f.events, ["error"]); });
for (const count of [20, 21]) test(`requirement count ${count}`, () => { const f = fixture(); const s = Array(count).fill("a").join(","); if (count === 20) { assert.equal(f.predicate(s)(labels({ a: "" })), true); assert.equal(f.events.filter(e => e === "key:a").length, 20); } else { assert.throws(() => f.predicate(s), e => e === f.rejected); assert.deepEqual(f.events, ["error"]); } });
for (const count of [64, 65]) test(`set value count ${count}`, () => { const f = fixture(); const s = `a in (${Array(count).fill("x").join(",")})`; if (count === 64) { assert.equal(f.predicate(s)(labels({ a: "x" })), true); assert.equal(f.events.filter(e => e === "value:x").length, 64); } else { assert.throws(() => f.predicate(s), e => e === f.rejected); assert.deepEqual(f.events, ["key:a", "error"]); } });
test("key validation precedes absent/operator refusal", () => { const f = fixture(); assert.throws(() => f.predicate("!a=x"), e => e === f.rejected); assert.deepEqual(f.events, ["key:a", "error"]); });
test("syntax refusal precedes key validation", () => { const f = fixture({ failKey: true }); assert.throws(() => f.predicate("?"), e => e === f.rejected); assert.deepEqual(f.events, ["error"]); });
test("key dependency refusal is propagated without error wrapping", () => { const f = fixture({ rejectKey: "a" }); assert.throws(() => f.predicate("a=x"), e => e === f.rejected); assert.deepEqual(f.events, ["key:a"]); });
test("equality validates empty value", () => { const f = fixture({ rejectValue: "" }); assert.throws(() => f.predicate("a="), e => e === f.rejected); assert.deepEqual(f.events, ["key:a", "value:", "error"]); });
test("set validation stops at first false", () => { const f = fixture({ rejectValue: "bad" }); assert.throws(() => f.predicate("a in (x,bad,z)"), e => e === f.rejected); assert.deepEqual(f.events, ["key:a", "value:x", "value:bad", "error"]); });
test("set empty stops before value validator", () => { const f = fixture(); assert.throws(() => f.predicate("a in (,x)"), e => e === f.rejected); assert.deepEqual(f.events, ["key:a", "error"]); });
for (const mode of ["failKey", "failValue", "failError", "failOwn"] as const) test(`immediate ${mode} fault propagates`, () => { const f = fixture({ [mode]: true }); assert.throws(() => mode === "failOwn" ? f.predicate("a")(labels()) : f.predicate(mode === "failError" ? "?" : "a=x"), e => e === f.fault); });
for (const selector of ["a", "a=x", "a in (x)", "!a", "a!=x", "a notin (x)"]) test(`inherited keys excluded ${selector}`, () => { const f = fixture(); const l = Object.create({ a: "x" }) as Labels; assert.equal(f.predicate(selector)(l), selector.startsWith("!") || selector.includes("!=") || selector.includes("notin")); });
test("all requirements compile before labels are inspected", () => { const f = fixture(); f.predicate("a=x,b in (y,z)"); assert.deepEqual(f.events, ["key:a", "value:x", "key:b", "value:y", "value:z"]); });
test("predicate conjunction stops on first false", () => { const f = fixture(); const p = f.predicate("a=x,b=y"); f.events.length = 0; assert.equal(p(labels()), false); assert.deepEqual(f.events, ["own:a"]); });
test("fresh calls observe changed label value without revalidation", () => { const f = fixture(); const p = f.predicate("a=x"); const l = labels({ a: "x" }); f.events.length = 0; assert.equal(p(l), true); l.a = "y"; assert.equal(p(l), false); delete l.a; assert.equal(p(l), false); assert.deepEqual(f.events, ["own:a", "own:a", "own:a"]); });
for (const selector of ["a=x", "a in (x)", "a!=x", "a notin (x)"]) test(`missing own key skips label getter ${selector}`, () => { const f = fixture(); const l = new Proxy(labels(), { get() { throw new Error("must not read missing property"); } }); assert.equal(f.predicate(selector)(l), selector.includes("!=") || selector.includes("notin")); });
test("existence does not read own property value", () => { const f = fixture(); const l = labels(); Object.defineProperty(l, "a", { get() { throw new Error("not read"); } }); assert.equal(f.predicate("a")(l), true); assert.equal(f.predicate("!a")(l), false); });
test("own value getter fault propagates", () => { const f = fixture(); const l = labels(); Object.defineProperty(l, "a", { get() { throw f.fault; } }); assert.throws(() => f.predicate("a=x")(l), e => e === f.fault); });
test("prototype-special keys use own semantics", () => { const f = fixture(); const l = labels(); Object.defineProperty(l, "__proto__", { value: "x", enumerable: true }); assert.equal(f.predicate("__proto__=x")(l), true); assert.equal(f.predicate("constructor")(l), false); });
test("later syntax failure cannot return partial predicate", () => { const f = fixture(); assert.throws(() => f.predicate("a=x,?"), e => e === f.rejected); assert.deepEqual(f.events, ["key:a", "value:x", "error"]); });
