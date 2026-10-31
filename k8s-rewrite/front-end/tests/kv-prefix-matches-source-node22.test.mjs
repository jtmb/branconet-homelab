import infrastructureAssert from 'node:assert/strict';
import {readFileSync as infrastructureRead} from 'node:fs';
import {createHash as infrastructureHash} from 'node:crypto';
const infrastructureDigest=x=>infrastructureHash('sha256').update(x).digest('hex');
infrastructureAssert.equal(process.versions.node,'22.23.3');
const infrastructureOriginal=infrastructureRead(new URL('./kv-prefix-matches-source.test.ts',import.meta.url),'utf8');
const infrastructureSource=infrastructureRead(new URL('../src/lib/kv-contract.ts',import.meta.url),'utf8');
infrastructureAssert.equal(infrastructureDigest(infrastructureOriginal),'446015417745eb4bdf96f3220025679dee34d2c5aa79c1da7775164fb2a9232b');
infrastructureAssert.equal(infrastructureDigest(infrastructureSource),'7cbd65c81eafda98df791c3029d65757b91c9ed5278756e7ba16e1966e744199');
const infrastructureOrder=["whole-segment strings [\"\",\"apps\"]","whole-segment strings [\"\",\"apps/api\"]","whole-segment strings [\"apps\",\"apps\"]","whole-segment strings [\"apps\",\"apps/api\"]","whole-segment strings [\"apps/api\",\"apps/api\"]","whole-segment strings [\"apps/api\",\"apps/api/key\"]","whole-segment strings [\"apps/api\",\"apps/api/key/leaf\"]","whole-segment strings [\"apps/api\",\"apps/apiculture\"]","whole-segment strings [\"apps/api\",\"apps/api2\"]","whole-segment strings [\"apps/api\",\"apps/ap\"]","whole-segment strings [\"apps/api\",\"apps\"]","whole-segment strings [\"apps/api\",\"other/api\"]","whole-segment strings [\"apps/api\",\"other/apps/api\"]","whole-segment strings [\"apps/api\",\"apps/other/api\"]","whole-segment strings [\"apps/api\",\"apps/api-key\"]","whole-segment strings [\"apps/api\",\"apps/api_key\"]","whole-segment strings [\"a\",\"ab/c\"]","whole-segment strings [\"a\",\"a/b\"]","whole-segment strings [\"apps/api-key\",\"apps/api-key/key\"]","whole-segment strings [\"apps/api_key\",\"apps/api_key/key\"]","qualified runtime is Node 22.23.3 (separate compatibility projection)","source extraction preserves the exact selected body","validation return undefined never replaces input","validation return false never replaces input","validation return ignored never replaces input","validator stage 1 propagates object unchanged","validator stage 1 propagates string unchanged","validator stage 2 propagates object unchanged","validator stage 2 propagates string unchanged","empty prefix still validates the path before returning","return short circuit avoids builtin lookup [\"\",\"apps/api\"]","return short circuit avoids builtin lookup [\"apps/api\",\"apps/api\"]","builtin lookup follows both validations for apps/api/key","builtin lookup follows both validations for apps/apiculture","builtin lookup error is propagated after both validations","builtin call error is propagated after lookup","noncallable builtin fails without consuming a result","fresh calls repeat both validations with their own strings","a refused call does not cache validation or poison the next call"];
let infrastructureCount=0;
function infrastructureControl(name,...args){infrastructureAssert.equal(name,infrastructureOrder[infrastructureCount++]);return test(name,...args);}
// BEGIN EXACT ORIGINAL NATIVE TYPE-ERASED PROJECTION
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import vm from "node:vm";

// Only this declaration is evaluated. No module import or neighboring body runs.
const source = readFileSync(path.join(process.cwd(), "src/lib/kv-contract.ts"), "utf8");
const declarations = source.match(/^export function prefixMatches\(prefix: string, path: string\): boolean \{[\s\S]*?^\}/gm);
assert.equal(declarations?.length, 1);
const declaration = declarations [0];
const executable = declaration.replace(
  "export function prefixMatches(prefix: string, path: string): boolean",
  "function prefixMatches(prefix, path)",
);
                                                 
                                                            
function fixture(validator            ) {
  const calls              = [];
  const events           = [];
  const context = vm.createContext({
    logicalPath: (...args           ) => {
      calls.push(args);
      events.push(calls.length % 2 ? "prefix" : "path");
      return validator?.(...args);
    },
    events,
  }, { codeGeneration: { strings: false, wasm: false } });
  const match = new vm.Script(`(${executable})`, { filename: "selected-prefixMatches.js" })
    .runInContext(context, { timeout: 1000 })           ;
  return { calls, events, context, match };
}
function installStartsWith(f                            , body        ) {
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
const pairs                                   = [
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
  infrastructureControl(`whole-segment strings ${JSON.stringify([prefix, logical])}`, () => {
    const f = fixture();
    assert.equal(f.match(prefix, logical), expected);
    assert.deepEqual(f.calls, [[prefix, true], [logical]]);
    assert.deepEqual(f.events, ["prefix", "path"]);
  });
}
infrastructureControl("qualified runtime is Node 22.23.3 (separate compatibility projection)", () => assert.equal(process.versions.node, "22.23.3"));
infrastructureControl("source extraction preserves the exact selected body", () => {
  assert.equal(declaration.replaceAll("\r\n", "\n"),
    'export function prefixMatches(prefix: string, path: string): boolean {\n  logicalPath(prefix, true); logicalPath(path);\n  return prefix === "" || path === prefix || path.startsWith(prefix + "/");\n}');
  assert.equal(executable.includes("export "), false);
});
for (const value of [undefined, false, "ignored"]) {
  infrastructureControl(`validation return ${String(value)} never replaces input`, () => {
    const f = fixture(() => value);
    assert.equal(f.match("apps/api", "apps/apiculture"), false);
    assert.deepEqual(f.calls, [["apps/api", true], ["apps/apiculture"]]);
  });
}
for (const stage of [1, 2]) {
  for (const failure of [new Error(`inert-validator-${stage}`), `inert-${stage}`]) {
    infrastructureControl(`validator stage ${stage} propagates ${typeof failure} unchanged`, () => {
      let n = 0;
      const f = fixture(() => { if (++n === stage) throw failure; });
      installStartsWith(f, 'throw new Error("unreachable lookup");');
      assert.throws(() => f.match("apps/api", "apps/api/key"), e => e === failure);
      assert.equal(f.calls.length, stage);
      assert.deepEqual(f.events, stage === 1 ? ["prefix"] : ["prefix", "path"]);
    });
  }
}
infrastructureControl("empty prefix still validates the path before returning", () => {
  const failure = new Error("inert-path-refusal");
  const f = fixture((...args) => { if (args.length === 1) throw failure; });
  assert.throws(() => f.match("", "apps/api"), e => e === failure);
  assert.deepEqual(f.calls, [["", true], ["apps/api"]]);
});
for (const [prefix, logical] of [["", "apps/api"], ["apps/api", "apps/api"]]) {
  infrastructureControl(`return short circuit avoids builtin lookup ${JSON.stringify([prefix, logical])}`, () => {
    const f = fixture();
    installStartsWith(f, 'throw new Error("unreachable lookup");');
    assert.equal(f.match(prefix, logical), true);
    assert.deepEqual(f.events, ["prefix", "path"]);
  });
}
for (const [logical, expected] of [["apps/api/key", true], ["apps/apiculture", false]]         ) {
  infrastructureControl(`builtin lookup follows both validations for ${logical}`, () => {
    const f = fixture();
    installStartsWith(f, `return function (search) {
      events.push("call:" + String(this) + ":" + search + ":" + arguments.length);
      return Reflect.apply(originalStartsWith, this, [search]);
    };`);
    assert.equal(f.match("apps/api", logical), expected);
    assert.deepEqual(f.events, ["prefix", "path", "lookup", `call:${logical}:apps/api/:1`]);
  });
}
infrastructureControl("builtin lookup error is propagated after both validations", () => {
  const f = fixture();
  installStartsWith(f, 'throw "inert-lookup-error";');
  assert.throws(() => f.match("apps/api", "apps/api/key"), e => e === "inert-lookup-error");
  assert.deepEqual(f.events, ["prefix", "path", "lookup"]);
});
infrastructureControl("builtin call error is propagated after lookup", () => {
  const f = fixture();
  installStartsWith(f, 'return function () { events.push("call"); throw "inert-call-error"; };');
  assert.throws(() => f.match("apps/api", "apps/api/key"), e => e === "inert-call-error");
  assert.deepEqual(f.events, ["prefix", "path", "lookup", "call"]);
});
infrastructureControl("noncallable builtin fails without consuming a result", () => {
  const f = fixture();
  installStartsWith(f, 'return null;');
  assert.throws(() => f.match("apps/api", "apps/api/key"), e => typeof e === "object" && e !== null && "name" in e && e.name === "TypeError");
  assert.deepEqual(f.events, ["prefix", "path", "lookup"]);
});
infrastructureControl("fresh calls repeat both validations with their own strings", () => {
  const f = fixture();
  assert.equal(f.match("apps/api", "apps/api/key"), true);
  assert.equal(f.match("apps/api", "apps/apiculture"), false);
  assert.deepEqual(f.calls, [["apps/api", true], ["apps/api/key"], ["apps/api", true], ["apps/apiculture"]]);
});
infrastructureControl("a refused call does not cache validation or poison the next call", () => {
  let refuse = true;
  const failure = new Error("inert-once");
  const f = fixture(() => { if (refuse) throw failure; });
  assert.throws(() => f.match("apps/api", "apps/api/key"), e => e === failure);
  refuse = false;
  assert.equal(f.match("apps/api", "apps/api/key"), true);
  assert.deepEqual(f.calls, [["apps/api", true], ["apps/api", true], ["apps/api/key"]]);
});

// END EXACT ORIGINAL NATIVE TYPE-ERASED PROJECTION
infrastructureAssert.equal(infrastructureCount,39);
console.log('BORTUS_COMPAT_ORDER '+JSON.stringify({name:'prefix-matches',registered:infrastructureCount,exactOrder:true}));
