import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import vm from "node:vm";

// Only this declaration is evaluated. No module import or neighboring body runs.
const source = readFileSync(path.join(process.cwd(), "src/lib/kv-contract.ts"), "utf8");
const declarations = source.match(/^export function prefixMatches\(prefix: string, path: string\): boolean \{[\s\S]*?^\}/gm);
assert.equal(declarations?.length, 1);
const declaration = declarations![0];
const executable = declaration.replace(
  "export function prefixMatches(prefix: string, path: string): boolean",
  "function prefixMatches(prefix, path)",
);
type Validator = (...args: unknown[]) => unknown;
type Matcher = (prefix: string, logical: string) => boolean;
function fixture(validator?: Validator) {
  const calls: unknown[][] = [];
  const events: string[] = [];
  const context = vm.createContext({
    logicalPath: (...args: unknown[]) => {
      calls.push(args);
      events.push(calls.length % 2 ? "prefix" : "path");
      return validator?.(...args);
    },
    events,
  }, { codeGeneration: { strings: false, wasm: false } });
  const match = new vm.Script(`(${executable})`, { filename: "selected-prefixMatches.js" })
    .runInContext(context, { timeout: 1000 }) as Matcher;
  return { calls, events, context, match };
}
function installStartsWith(f: ReturnType<typeof fixture>, body: string) {
  new vm.Script(`
    const originalStartsWith = String.prototype.startsWith;
    Object.defineProperty(String.prototype, "startsWith", {
      configurable: true,
      get() {
        events.push("lookup");
        ${body}
      }
    });
  `).runInContext(f.context, { timeout: 1000 });
}
const pairs: Array<[string, string, boolean]> = [
  ["", "apps", true], ["", "apps/api", true],
  ["apps", "apps", true], ["apps", "apps/api", true],
  ["apps/api", "apps/api", true], ["apps/api", "apps/api/key", true],
  ["apps/api", "apps/api/key/leaf", true], ["apps/api", "apps/apiculture", false],
  ["apps/api", "apps/api2", false], ["apps/api", "apps/ap", false],
  ["apps/api", "apps", false], ["apps/api", "other/api", false],
  ["apps/api", "other/apps/api", false], ["apps/api", "apps/other/api", false],
  ["apps/api", "apps/api-key", false], ["apps/api", "apps/api_key", false],
  ["a", "ab/c", false], ["a", "a/b", true],
  ["apps/api-key", "apps/api-key/key", true], ["apps/api_key", "apps/api_key/key", true],
];
for (const [prefix, logical, expected] of pairs) {
  test(`whole-segment strings ${JSON.stringify([prefix, logical])}`, () => {
    const f = fixture();
    assert.equal(f.match(prefix, logical), expected);
    assert.deepEqual(f.calls, [[prefix, true], [logical]]);
    assert.deepEqual(f.events, ["prefix", "path"]);
  });
}
test("qualified runtime is Node 24.18.0", () => assert.equal(process.versions.node, "24.18.0"));
test("source extraction preserves the exact selected body", () => {
  assert.equal(declaration.replaceAll("\r\n", "\n"),
    'export function prefixMatches(prefix: string, path: string): boolean {\n  logicalPath(prefix, true); logicalPath(path);\n  return prefix === "" || path === prefix || path.startsWith(prefix + "/");\n}');
  assert.equal(executable.includes("export "), false);
});
for (const value of [undefined, false, "ignored"]) {
  test(`validation return ${String(value)} never replaces input`, () => {
    const f = fixture(() => value);
    assert.equal(f.match("apps/api", "apps/apiculture"), false);
    assert.deepEqual(f.calls, [["apps/api", true], ["apps/apiculture"]]);
  });
}
for (const stage of [1, 2]) {
  for (const failure of [new Error(`inert-validator-${stage}`), `inert-${stage}`]) {
    test(`validator stage ${stage} propagates ${typeof failure} unchanged`, () => {
      let n = 0;
      const f = fixture(() => { if (++n === stage) throw failure; });
      installStartsWith(f, 'throw new Error("unreachable lookup");');
      assert.throws(() => f.match("apps/api", "apps/api/key"), e => e === failure);
      assert.equal(f.calls.length, stage);
      assert.deepEqual(f.events, stage === 1 ? ["prefix"] : ["prefix", "path"]);
    });
  }
}
test("empty prefix still validates the path before returning", () => {
  const failure = new Error("inert-path-refusal");
  const f = fixture((...args) => { if (args.length === 1) throw failure; });
  assert.throws(() => f.match("", "apps/api"), e => e === failure);
  assert.deepEqual(f.calls, [["", true], ["apps/api"]]);
});
for (const [prefix, logical] of [["", "apps/api"], ["apps/api", "apps/api"]]) {
  test(`return short circuit avoids builtin lookup ${JSON.stringify([prefix, logical])}`, () => {
    const f = fixture();
    installStartsWith(f, 'throw new Error("unreachable lookup");');
    assert.equal(f.match(prefix, logical), true);
    assert.deepEqual(f.events, ["prefix", "path"]);
  });
}
for (const [logical, expected] of [["apps/api/key", true], ["apps/apiculture", false]] as const) {
  test(`builtin lookup follows both validations for ${logical}`, () => {
    const f = fixture();
    installStartsWith(f, `return function (search) {
      events.push("call:" + String(this) + ":" + search + ":" + arguments.length);
      return Reflect.apply(originalStartsWith, this, [search]);
    };`);
    assert.equal(f.match("apps/api", logical), expected);
    assert.deepEqual(f.events, ["prefix", "path", "lookup", `call:${logical}:apps/api/:1`]);
  });
}
test("builtin lookup error is propagated after both validations", () => {
  const f = fixture();
  installStartsWith(f, 'throw "inert-lookup-error";');
  assert.throws(() => f.match("apps/api", "apps/api/key"), e => e === "inert-lookup-error");
  assert.deepEqual(f.events, ["prefix", "path", "lookup"]);
});
test("builtin call error is propagated after lookup", () => {
  const f = fixture();
  installStartsWith(f, 'return function () { events.push("call"); throw "inert-call-error"; };');
  assert.throws(() => f.match("apps/api", "apps/api/key"), e => e === "inert-call-error");
  assert.deepEqual(f.events, ["prefix", "path", "lookup", "call"]);
});
test("noncallable builtin fails without consuming a result", () => {
  const f = fixture();
  installStartsWith(f, 'return null;');
  assert.throws(() => f.match("apps/api", "apps/api/key"), e => typeof e === "object" && e !== null && "name" in e && e.name === "TypeError");
  assert.deepEqual(f.events, ["prefix", "path", "lookup"]);
});
test("fresh calls repeat both validations with their own strings", () => {
  const f = fixture();
  assert.equal(f.match("apps/api", "apps/api/key"), true);
  assert.equal(f.match("apps/api", "apps/apiculture"), false);
  assert.deepEqual(f.calls, [["apps/api", true], ["apps/api/key"], ["apps/api", true], ["apps/apiculture"]]);
});
test("a refused call does not cache validation or poison the next call", () => {
  let refuse = true;
  const failure = new Error("inert-once");
  const f = fixture(() => { if (refuse) throw failure; });
  assert.throws(() => f.match("apps/api", "apps/api/key"), e => e === failure);
  refuse = false;
  assert.equal(f.match("apps/api", "apps/api/key"), true);
  assert.deepEqual(f.calls, [["apps/api", true], ["apps/api", true], ["apps/api/key"]]);
});
