import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import path from "node:path";
const require = createRequire(import.meta.url);
const directory = process.env.BORTUS_ZOD_DIRECTORY ?? path.dirname(require.resolve("zod/package.json"));
const source = process.env.BORTUS_ZOD_SOURCE === "1";
for (const format of source ? ["source"] : ["CJS", "ESM"]) {
  const ext = source ? ".ts" : format === "CJS" ? ".cjs" : ".js";
  const prefix = directory + (source ? "/src/" : "/");
  const load = name => format === "CJS" ? require(prefix + name + ext) : import(pathToFileURL(prefix + name + ext).href);
  const core = await load("v4/core/index");
  for (const surface of ["root", "v3", "v4", "v4-mini", "v4/mini", "v4/core"]) {
    const api = await load(surface === "root" ? "v3/index" : surface + "/index");
    const v3 = surface === "root" || surface === "v3", raw = surface === "v4/core";
    const string = () => raw ? new core.$ZodString({ type: "string" }) : api.string();
    for (const kind of ["tuple-rest", "record-issues", "record-work"]) {
      test(`${format} ${surface} ${kind} stops data traversal at the shared budget`, () => {
        let reads = 0, schema, input;
        if (kind === "tuple-rest") {
          schema = v3 ? api.tuple([]).rest(string()) : raw ? new core.$ZodTuple({ type: "tuple", items: [], rest: string() }) : api.tuple([], string());
          input = Array(100001).fill("ok");
          Object.defineProperty(input, 0, { get() { reads++; return "ok"; } });
        } else {
          schema = raw ? new core.$ZodRecord({ type: "record", keyType: string(), valueType: string() }) : api.record(string(), string());
          input = {};
          const count = kind === "record-issues" ? 10000 : 60000;
          for (let i = 0; i < count; i++) Object.defineProperty(input, "k" + i, {
            enumerable: true, get() { reads++; return kind === "record-issues" ? 0 : "ok"; }
          });
        }
        const result = v3 ? schema.safeParse(input) : core.safeParse(schema, input);
        assert.equal(result.success, false);
        assert.equal(result.error.issues.length, 1);
        assert.equal(result.error.issues[0].message, "BORTUS validation budget exceeded");
        assert.deepEqual(result.error.issues[0].path, []);
        if (kind === "tuple-rest") assert.equal(reads, 0, "tuple must reserve before reading rest values");
        else assert.ok(reads <= (kind === "record-issues" ? 1001 : 50001), "record continued reading after exhaustion");
      });
    }
  }
}