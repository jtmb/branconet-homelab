import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { readFileSync } from "node:fs";
const require = createRequire(import.meta.url);
const directory = process.env.BORTUS_ZOD_DIRECTORY ?? path.dirname(require.resolve("zod/package.json"));
const source = process.env.BORTUS_ZOD_SOURCE === "1";
const message = "BORTUS validation budget exceeded";
const cases = ["array-issues", "set-issues", "map-issues", "collection-work", "union-cannot-recover", "catch-cannot-recover", "async-shared-issues"];
for (const format of source ? ["source"] : ["CJS", "ESM"]) {
  const ext = source ? ".ts" : format === "CJS" ? ".cjs" : ".js";
  const prefix = directory + (source ? "/src/" : "/");
  const load = name => format === "CJS" ? require(prefix + name + ext) : import(pathToFileURL(prefix + name + ext).href);
  const core = await load("v4/core/index");
  const { Doc } = format === "CJS" ? require(prefix + "v4/core/doc.js") : await load("v4/core/doc");
  if (format === "CJS") assert.ok(readFileSync(prefix + "v4/core/schemas.cjs", "utf8").includes('const doc_js_1 = require("./doc.js");'), "Actual maintained compiler module binding changed");
  for (const surface of ["root", "v3", "v4", "v4-mini", "v4/mini", "v4/core"]) {
    const v3 = surface === "root" || surface === "v3", raw = surface === "v4/core";
    const api = await load(surface === "root" ? "v3/index" : surface + "/index");
    const number = () => raw ? new core.$ZodNumber({ type: "number", checks: [] }) : api.number();
    const string = () => raw ? new core.$ZodString({ type: "string" }) : api.string();
    const any = () => raw ? new core.$ZodAny({ type: "any" }) : api.any();
    const array = inner => raw ? new core.$ZodArray({ type: "array", element: inner }) : api.array(inner);
    const set = inner => raw ? new core.$ZodSet({ type: "set", valueType: inner }) : api.set(inner);
    const map = (k, v) => raw ? new core.$ZodMap({ type: "map", keyType: k, valueType: v }) : api.map(k, v);
    // Mini/core base objects interpret; use their explicit JIT parent only in the sync JIT case.
    const object = (inner, jitless, async) => !v3 && !jitless && !async && (raw || surface === "v4-mini" || surface === "v4/mini")
      ? new core.$ZodObjectJIT({ type: "object", shape: { value: inner } })
      : raw ? new core.$ZodObject({ type: "object", shape: { value: inner } }) : api.object({ value: inner });
    const union = options => raw ? new core.$ZodUnion({ type: "union", options }) : api.union(options);
    const attach = (schema, check) => schema.check ? schema.check(check) : core.clone(schema, { ...schema._zod.def, checks: [check] });
    const failLeaf = (async, visit) => v3 ? api.any().superRefine(async ? async (_, ctx) => { visit(); await Promise.resolve(); ctx.addIssue({ code: "custom", message: "leaf" }); }
      : (_, ctx) => { visit(); ctx.addIssue({ code: "custom", message: "leaf" }); })
      : attach(any(), { _zod: { def: { check: "custom" }, onattach: [], check: async ? async p => { visit(); await Promise.resolve(); p.issues.push({ code: "custom", message: "leaf", continue: true }); }
        : p => { visit(); p.issues.push({ code: "custom", message: "leaf", continue: true }); } } });
    const catchSchema = schema => v3 ? schema.catch([]) : new core.$ZodCatch({ type: "catch", innerType: schema, catchValue: () => [] });
    const parse = (schema, input, async, jitless, context = {}) => v3 ? (async ? schema.safeParseAsync(input, context) : schema.safeParse(input, context))
      : (async ? core.safeParseAsync(schema, input, { ...context, jitless }) : core.safeParse(schema, input, { ...context, jitless }));
    for (const jitless of v3 ? [true] : [false, true]) for (const async of [false, true]) {
      const label = `${format} ${surface} ${jitless ? "interpreter" : "object-JIT"} ${async ? "async" : "sync"}`;
      for (const kind of cases) {
        if (kind === "async-shared-issues" && !async) continue;
        test(`${label} ${kind} exhausts one shared budget`, async () => {
          let visits = 0, compiled = 0;
          const leaf = failLeaf(kind === "async-shared-issues", () => visits++);
          let child = array(array(leaf)), input = Array.from({ length: 32 }, () => Array(64).fill(0));
          if (kind === "set-issues") { child = array(set(leaf)); input = Array.from({ length: 32 }, () => new Set(Array.from({ length: 64 }, (_, i) => i))); }
          if (kind === "map-issues") { child = array(map(number(), leaf)); input = Array.from({ length: 32 }, () => new Map(Array.from({ length: 64 }, (_, i) => [i, 0]))); }
          if (kind === "collection-work") { child = array(array(number())); input = Array.from({ length: 200 }, () => Array(600).fill(1)); }
          if (kind === "union-cannot-recover") child = union([child, any()]);
          if (kind === "catch-cannot-recover") child = catchSchema(child);
          const schema = object(child, jitless, async), compile = Doc.prototype.compile;
          Doc.prototype.compile = function (...args) { compiled++; return compile.apply(this, args); };
          let result;
          try { result = await parse(schema, { value: input }, async, jitless); } finally { Doc.prototype.compile = compile; }
          assert.equal(result.success, false, "exhaustion was accepted or swallowed");
          assert.equal(result.error.issues.length, 1, "whole-parse terminal issue");
          assert.equal(result.error.issues[0].message, message);
          assert.equal(result.error.issues[0].code, "custom");
          assert.deepEqual(result.error.issues[0].path, []);
          if (kind !== "collection-work") assert.ok(visits > 0 && visits <= (kind === "async-shared-issues" ? 2048 : 1001), "bounded callbacks");
          assert.equal(compiled, !v3 && !jitless && !async ? 1 : 0, "actual object compiler/interpreter selection");
        });
      }
      test(`${label} retains within-budget values, error order and branch semantics`, async () => {
        const nested = array(array(string()));
        const good = [["a", "b", "c"], ["d", "e", "f"]];
        assert.deepEqual((await parse(nested, good, async, jitless)).data, good);
        const bad = await parse(nested, [[0, 1, 2], [3, 4, 5]], async, jitless);
        assert.equal(bad.success, false);
        assert.deepEqual(bad.error.issues.map(i => i.path), [[0, 0], [0, 1], [0, 2], [1, 0], [1, 1], [1, 2]]);
        assert.deepEqual((await parse(union([nested, any()]), [0], async, jitless)).data, [0]);
        assert.deepEqual((await parse(catchSchema(nested), [0], async, jitless)).data, []);
        const numbers = Array.from({ length: 10000 }, (_, i) => i);
        assert.deepEqual((await parse(array(number()), numbers, async, jitless)).data, numbers);
        assert.deepEqual((await parse(set(number()), new Set(numbers), async, jitless)).data, new Set(numbers));
        assert.deepEqual((await parse(map(number(), number()), new Map(numbers.map(i => [i, i])), async, jitless)).data, new Map(numbers.map(i => [i, i])));
        assert.equal((await parse(array(number()), Array(10001).fill(0), async, jitless)).error.issues[0].code, "too_big");
        // Public errors retain ordinary mutable arrays after internal budgeted accumulation.
        const originalLength = bad.error.issues.length;
        bad.error.issues.push(...Array.from({ length: 1200 }, () => ({ code: "custom", message: "external", path: [] })));
        assert.equal(bad.error.issues.length, originalLength + 1200);
      });
      test(`${label} preserves callbacks, explicit errors and independent concurrent parses`, async () => {
        let calls = 0;
        const leaf = failLeaf(async, () => calls++);
        const ctx = {};
        const [small, large, valid] = await Promise.all([
          parse(array(leaf), [0, 1], async, jitless, ctx),
          parse(array(array(string())), Array.from({ length: 32 }, () => Array(64).fill(0)), async, jitless, ctx),
          parse(array(number()), [1, 2, 3], async, jitless, ctx)
        ]);
        assert.equal(small.success, false); assert.equal(calls, 2);
        assert.equal(large.error.issues[0].message, message);
        assert.deepEqual(valid.data, [1, 2, 3]);
        assert.deepEqual(ctx, {});
        assert.deepEqual((await parse(array(number()), [4], async, jitless, ctx)).data, [4]);
        if (v3) {
          let errors = 0;
          const result = await parse(api.array(api.string()).max(0, "size error"), [0], async, jitless, { errorMap: () => { errors++; return { message: "mapped" }; } });
          assert.equal(result.error.issues[0].message, "size error"); assert.equal(errors, 0);
        } else {
          const scalar = number(); assert.equal(scalar._zod.run, scalar._zod.parse, "no-check scalar identity");
          const rewritten = attach(array(number()), core._overwrite(a => a.slice(0, 2)));
          assert.deepEqual((await parse(rewritten, [1, 2, 3], async, jitless)).data, [1, 2]);
        }
      });
    }
  }
}