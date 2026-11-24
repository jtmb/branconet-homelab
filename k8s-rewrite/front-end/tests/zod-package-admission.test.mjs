import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
const require = createRequire(import.meta.url);
const directory = process.env.BORTUS_ZOD_DIRECTORY;
const cjs = directory ? require(directory + "/v3/index.cjs") : require("zod/v3");
const esm = await import(directory ? pathToFileURL(directory + "/v3/index.js").href : "zod/v3");
const entry = ["array-max", "array-exact", "array-zero", "set-max", "set-exact",
  "array-default", "set-default", "map-default"];
for (const [format, { z }] of [["CJS", cjs], ["ESM", esm]]) {
  for (const kind of entry) for (const async of [false, true]) {
    test(format + " " + kind + " " + (async ? "async" : "sync") + " rejects before traversal", async () => {
      let visits = 0, enumerations = 0;
      const element = z.preprocess(value => { visits++; return value; }, z.string());
      const item = async ? element.refine(async () => true) : element;
      const count = kind.endsWith("default") ? 10001 : 17;
      let schema, input;
      if (kind.startsWith("array")) {
        schema = z.array(item);
        if (kind.endsWith("max")) schema = schema.max(2);
        if (kind.endsWith("exact")) schema = schema.length(2);
        if (kind.endsWith("zero")) schema = schema.max(0);
        input = Array(count).fill(0);
        Object.defineProperty(input, 0, { get() { enumerations++; return 0; } });
      } else if (kind.startsWith("set")) {
        schema = z.set(item);
        if (kind.endsWith("max")) schema = schema.max(2);
        if (kind.endsWith("exact")) schema = schema.size(2);
        input = new Set(Array.from({ length: count }, (_, index) => index));
        const values = input.values.bind(input);
        input.values = function () { enumerations++; return values(); };
      } else {
        schema = z.map(item, item);
        input = new Map(Array.from({ length: count }, (_, index) => [index, 0]));
        const entries = input.entries.bind(input);
        input.entries = function () { enumerations++; return entries(); };
      }
      const result = async ? await schema.safeParseAsync(input) : schema.safeParse(input);
      assert.equal(visits, 0, "oversized collection reached element validation");
      assert.equal(enumerations, 0, "oversized collection began traversal");
      assert.equal(result.success, false);
      assert.equal(result.error.issues.length, 1);
      assert.equal(result.error.issues[0].code, kind.startsWith("map") ? "custom" : "too_big");
      if (!kind.startsWith("map"))
        assert.equal(result.error.issues[0].maximum, kind.endsWith("default") ? 10000 : kind.endsWith("zero") ? 0 : 2);
    });
  }
  test(format + " admits the unchanged 10000 boundary, defaults and ordered element errors", async () => {
    assert.equal(z.array(z.number()).parse(Array(10000).fill(1)).length, 10000);
    assert.equal(z.set(z.number()).parse(new Set(Array.from({ length: 10000 }, (_, i) => i))).size, 10000);
    assert.equal(z.map(z.number(), z.string()).parse(new Map(Array.from({ length: 10000 }, (_, i) => [i, "ok"]))).size, 10000);
    assert.equal(z.enum(["worker", "master"]).default("worker").parse(undefined), "worker");
    const result = z.array(z.string()).max(3).safeParse([0, null, "ok"]);
    assert.equal(result.success, false);
    assert.deepEqual(result.error.issues.map(issue => issue.path), [[0], [1]]);
    assert.deepEqual(await z.array(z.string().transform(async s => s.toUpperCase())).max(2).parseAsync(["a", "b"]), ["A", "B"]);
  });
}
