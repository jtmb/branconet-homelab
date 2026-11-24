import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { readFileSync } from "node:fs";
const require = createRequire(import.meta.url);
const directory = process.env.BORTUS_ZOD_DIRECTORY ?? path.dirname(require.resolve("zod/package.json"));
const source = process.env.BORTUS_ZOD_SOURCE === "1";
const surfaces = ["v4", "v4-mini", "v4/mini", "v4/core"];
const cases = ["array-max", "array-exact", "array-zero", "array-default",
  "set-max", "set-exact", "set-default", "map-max", "map-exact", "map-default"];
for (const format of source ? ["source"] : ["CJS", "ESM"]) {
  const extension = source ? ".ts" : format === "CJS" ? ".cjs" : ".js";
  const prefix = directory + (source ? "/src/" : "/");
  const load = async name => format === "CJS" ? require(prefix + name + "/index" + extension)
    : import(pathToFileURL(prefix + name + "/index" + extension).href);
  const core = await load("v4/core");
  const { Doc } = format === "CJS" ? require(prefix + "v4/core/doc.js")
    : await import(pathToFileURL(prefix + "v4/core/doc" + extension).href);
  if (format === "CJS") assert.ok(readFileSync(prefix + "v4/core/schemas.cjs", "utf8").includes('const doc_js_1 = require("./doc.js");'), "Actual maintained compiler module binding changed");
  test("G79 " + format + " actual compiler distinguishes base, JIT, async and jitless paths", async () => {
    for (const useJIT of [false, true]) for (const jitless of [false, true]) for (const async of [false, true]) {
      let compiled = 0;
      const child = new core.$ZodArray({ type: "array", element: new core.$ZodNumber({ type: "number", checks: [] }) });
      const parent = new core[useJIT ? "$ZodObjectJIT" : "$ZodObject"]({ type: "object", shape: { value: child } });
      const compile = Doc.prototype.compile;
      Doc.prototype.compile = function (...args) { compiled++; return compile.apply(this, args); };
      let result;
      try { result = async ? await core.safeParseAsync(parent, { value: [1, 2] }, { jitless })
        : core.safeParse(parent, { value: [1, 2] }, { jitless }); }
      finally { Doc.prototype.compile = compile; }
      assert.equal(result.success, true);
      assert.deepEqual(result.data, { value: [1, 2] });
      assert.equal(compiled, useJIT && !jitless && !async ? 1 : 0, "genuine compiler selection across all parent paths");
    }
  });

  for (const surface of surfaces) {
    const api = await load(surface);
    const raw = surface === "v4/core";
    const string = () => raw ? new core.$ZodString({ type: "string" }) : api.string();
    const number = () => raw ? new core.$ZodNumber({ type: "number", checks: [] }) : api.number();
    const array = el => raw ? new core.$ZodArray({ type: "array", element: el }) : api.array(el);
    const set = el => raw ? new core.$ZodSet({ type: "set", valueType: el }) : api.set(el);
    const map = el => raw ? new core.$ZodMap({ type: "map", keyType: el, valueType: el }) : api.map(el, el);
    const attach = (schema, ...checks) => schema.check ? schema.check(...checks)
      : core.clone(schema, { ...schema._zod.def, checks: [...(schema._zod.def.checks ?? []), ...checks] });
    // Preserve base/interpreter coverage; explicitly request the maintained sync JIT constructor.
    const object = (child, jitless, async) => !jitless && !async && (raw || surface === "v4-mini" || surface === "v4/mini")
      ? new core.$ZodObjectJIT({ type: "object", shape: { value: child } })
      : raw ? new core.$ZodObject({ type: "object", shape: { value: child } }) : api.object({ value: child });
    const label = format + " " + surface;
    for (const jitless of [false, true]) for (const async of [false, true]) for (const kind of cases) {
      test(label + " " + kind + " " + (jitless ? "interpreter" : "object-JIT") + " " + (async ? "async" : "sync") + " rejects before traversal", async () => {
        let visits = 0, traversal = 0, later = 0, compiled = 0;
        const element = string(), run = element._zod.run;
        element._zod.run = async ? async (p, c) => { visits++; return run(p, c); }
          : (p, c) => { visits++; return run(p, c); };
        const count = kind.endsWith("default") ? 10001 : 17;
        let schema, input;
        const maximum = kind.endsWith("default") ? 10000 : kind.endsWith("zero") ? 0 : 2;
        if (kind.startsWith("array")) {
          schema = array(element); input = Array(count).fill(0);
          Object.defineProperty(input, 0, { get() { traversal++; return 0; } });
          if (!kind.endsWith("default")) schema = attach(schema, kind.endsWith("exact") ? core._length(maximum, { error: "size error" }) : core._maxLength(maximum, { error: "size error" }));
        } else {
          schema = kind.startsWith("set") ? set(element) : map(element);
          input = kind.startsWith("set") ? new Set(Array.from({ length: count }, (_, i) => i))
            : new Map(Array.from({ length: count }, (_, i) => [i, i]));
          const iterator = input[Symbol.iterator].bind(input);
          input[Symbol.iterator] = function () { traversal++; return iterator(); };
          if (!kind.endsWith("default")) schema = attach(schema, kind.endsWith("exact") ? core._size(maximum, { error: "size error" }) : core._maxSize(maximum, { error: "size error" }));
        }
        schema = attach(schema, { _zod: { def: { check: "custom" }, onattach: [], check() { later++; } } });
        const parent = object(schema, jitless, async), compile = Doc.prototype.compile;
        Doc.prototype.compile = function (...args) { compiled++; return compile.apply(this, args); };
        let result;
        try { result = async ? await core.safeParseAsync(parent, { value: input }, { jitless })
          : core.safeParse(parent, { value: input }, { jitless }); }
        finally { Doc.prototype.compile = compile; }
        assert.equal(visits, 0, "oversized container reached a child validator");
        assert.equal(traversal, 0, "oversized container began traversal");
        assert.equal(later, 0, "later check received raw unparsed values");
        assert.equal(compiled, !jitless && !async ? 1 : 0, "actual object parser path");
        assert.equal(result.success, false);
        assert.equal(result.error.issues.length, 1);
        const issue = result.error.issues[0];
        assert.equal(issue.code, "too_big"); assert.equal(issue.maximum, maximum);
        assert.deepEqual(issue.path, ["value"]);
        if (!kind.endsWith("default")) assert.equal(issue.message, "size error");
      });
    }
    test(label + " preserves admitted values, lower bounds, issue order and default boundary", async () => {
      for (const make of [array, set, map]) {
        const schema = make(number()), entries = Array.from({ length: 10000 }, (_, i) => i);
        const value = make === array ? entries : make === set ? new Set(entries) : new Map(entries.map(i => [i, i]));
        const result = core.safeParse(schema, value);
        assert.equal(result.success, true);
        assert.equal(make === array ? result.data.length : result.data.size, 10000);
        assert.deepEqual(result.data, value);
      }
      const a = attach(array(string()), core._maxLength(3));
      const result = core.safeParse(a, [0, null, "ok"]);
      assert.equal(result.success, false); assert.deepEqual(result.error.issues.map(i => i.path), [[0], [1]]);
      assert.equal(core.safeParse(attach(array(string()), core._length(2)), ["one"]).error.issues[0].code, "too_small");
      assert.equal(core.safeParse(attach(set(string()), core._size(2)), new Set(["one"])).error.issues[0].code, "too_small");
      assert.deepEqual(await core.parseAsync(attach(array(string()), core._maxLength(2)), ["a", "b"]), ["a", "b"]);
    });
    test(label + " preserves overwrite/refinement barrier and conditional checks", () => {
      const rewrite = core._overwrite(value => value.slice(0, 2));
      const schema = attach(array(number()), rewrite, core._maxLength(2));
      assert.deepEqual(core.parse(schema, [1, 2, 3]), [1, 2]);
      const conditional = attach(array(number()), core._maxLength(2, { when: () => false }));
      assert.deepEqual(core.parse(conditional, [1, 2, 3]), [1, 2, 3]);
      let refined = 0;
      const before = { _zod: { def: { check: "custom" }, onattach: [], check() { refined++; } } };
      const laterBound = attach(array(number()), before, core._maxLength(2));
      const result = core.safeParse(laterBound, [1, 2, 3]);
      assert.equal(refined, 1); assert.equal(result.error.issues[0].code, "too_big");
    });
    test(label + " preserves type precedence, custom error redaction and admitted async transforms", async () => {
      for (const [make, wrong] of [[array, {}], [set, []], [map, new Set()]]) {
        const result = core.safeParse(make(string()), wrong);
        assert.equal(result.success, false); assert.equal(result.error.issues[0].code, "invalid_type");
      }
      const input = Array(10001).fill("private-marker");
      const result = core.safeParse(array(string()), input);
      assert.equal(result.success, false);
      assert.equal(result.error.issues[0].input, undefined);
      assert.ok(!JSON.stringify(result).includes("private-marker"));
    });
  }
}
