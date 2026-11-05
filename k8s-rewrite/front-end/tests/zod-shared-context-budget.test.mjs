import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import path from "node:path";
const require = createRequire(import.meta.url);
const directory = process.env.BORTUS_ZOD_DIRECTORY ?? path.dirname(require.resolve("zod/package.json"));
const source = process.env.BORTUS_ZOD_SOURCE === "1";
const pairs = source ? [["source", "CJS"], ["CJS", "source"], ["source", "ESM"], ["ESM", "source"]] : [["CJS", "ESM"], ["ESM", "CJS"]];
const load = (mode, name) => mode === "CJS" ? require(directory + "/" + name + ".cjs")
  : import(pathToFileURL(directory + (mode === "source" ? "/src/" : "/") + name + (mode === "source" ? ".ts" : ".js")).href);
for (const [parentMode, childMode] of pairs) for (const surface of ["root", "v3", "v4", "v4-mini", "v4/mini", "v4/core"]) {
  const v3 = surface === "root" || surface === "v3", raw = surface === "v4/core";
  const name = surface === "root" ? "v3/index" : surface + "/index";
  const parent = await load(parentMode, name), child = await load(childMode, name), core = await load(parentMode, "v4/core/index");
  const numbers = api => raw ? new api.$ZodArray({ type: "array", element: new api.$ZodArray({ type: "array", element: new api.$ZodNumber({ type: "number", checks: [] }) }) }) : api.array(api.array(api.number()));
  const schema = raw ? new parent.$ZodObject({ type: "object", shape: { left: numbers(parent), right: numbers(child) } }) : parent.object({ left: numbers(parent), right: numbers(child) });
  const parse = (value, async) => v3 ? (async ? schema.safeParseAsync(value) : schema.safeParse(value)) : (async ? core.safeParseAsync(schema, value) : core.safeParse(schema, value));
  for (const async of [false, true]) {
    const label = `${parentMode}/${childMode} ${surface} ${async ? "async interpreter" : "sync default-object-path"}`;
    test(`${label} shares120200 collection slots across formats`, async () => {
      const value = { left: Array.from({ length: 100 }, () => Array(600).fill(1)), right: Array.from({ length: 100 }, () => Array(600).fill(1)) };
      const result = await parse(value, async);
      assert.equal(result.success, false, "mixed formats split one parse into independent budgets");
      assert.equal(result.error.issues.length, 1);
      assert.equal(result.error.issues[0].message, "BORTUS validation budget exceeded");
      assert.deepEqual(result.error.issues[0].path, []);
    });
    test(`${label} retains small mixed-format values, error order and fresh parse state`, async () => {
      const value = { left: [[1, 2]], right: [[3, 4]] };
      assert.deepEqual((await parse(value, async)).data, value);
      const result = await parse({ left: [["x"]], right: [["y"]] }, async);
      assert.equal(result.success, false);
      assert.deepEqual(result.error.issues.map(i => i.path), [["left", 0, 0], ["right", 0, 0]]);
      assert.deepEqual((await parse(value, async)).data, value);
    });
  }
}