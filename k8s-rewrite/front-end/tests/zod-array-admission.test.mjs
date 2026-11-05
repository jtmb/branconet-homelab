import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import Module from "node:module";

const require = createRequire(import.meta.url);
const { z } = require("zod/v3");
const { boundedArray } = require("../src/lib/bounded-array.ts");
const schemas = require("../src/lib/kv-schemas.ts");
const transfer = require("../src/lib/kv-transfer.ts");
const { automationRequest } = require("../src/lib/kv-automation.ts");
const { kvBody, kvAdminMetadataBody } = require("../src/lib/kv-http.ts");
const { kvErrorResponse } = require("../src/lib/kv-http.ts");

test("oversize admission creates one size issue without parsing any element", () => {
  let visits = 0;
  const inner = z.array(z.preprocess(value => { visits++; return value; }, z.string())).max(8);
  const result = boundedArray(inner).safeParse(Array(4096).fill(0));
  assert.equal(visits, 0, "oversize array reached element parser");
  assert.equal(result.success, false);
  assert.equal(result.error.issues.length, 1);
  assert.equal(result.error.issues[0].code, "too_big");
  assert.equal(result.error.issues[0].maximum, 8);
});

test("async admission refuses before starting element work", async () => {
  let visits = 0;
  const schema = boundedArray(z.array(z.string().refine(async () => { visits++; return true; })).max(2));
  const result = await schema.safeParseAsync(Array(32).fill("value"));
  assert.equal(visits, 0, "oversize async array reached element parser");
  assert.equal(result.success, false);
  assert.equal(result.error.issues.length, 1);
});

test("construction refuses absent or invalid finite upper bounds", () => {
  for (const schema of [z.array(z.string()), z.array(z.string()).min(1),
    z.array(z.string()).max(Infinity), z.array(z.string()).max(-1), z.array(z.string()).max(1.5)])
    assert.throws(() => boundedArray(schema), /requires a finite upper bound/);
});

test("in-bound outputs and all original issues retain exact parity", async () => {
  const original = z.array(z.object({ value: z.string().min(2) }).strict()).min(1).max(3);
  const guarded = boundedArray(original);
  for (const input of [null, {}, "array", [], [{ value: "ok" }], [{ value: 0 }],
    [{ value: "x", extra: true }, { value: "" }], [{ value: "aa" }, { value: "bb" }, { value: "cc" }]]) {
    const normalize = result => result.success ? { data: result.data } : { issues: result.error.issues };
    assert.deepEqual(normalize(guarded.safeParse(input)), normalize(original.safeParse(input)));
    assert.deepEqual(normalize(await guarded.safeParseAsync(input)), normalize(await original.safeParseAsync(input)));
  }
});

test("exact, zero and combined bounds reject before refinements with original messages", () => {
  for (const original of [z.array(z.string()).length(2, "exact size"), z.array(z.string()).max(0, "empty only"),
    z.array(z.string()).max(3).length(2, "exact size"), z.array(z.string()).max(1, "maximum size").length(2)]) {
    let reads = 0;
    const input = Array(5).fill(0);
    Object.defineProperty(input, 0, { get() { reads++; return 0; } });
    const result = boundedArray(original).safeParse(input);
    assert.equal(result.success, false);
    assert.equal(reads, 0);
    const expected = original.safeParse(Array(5).fill("ok")).error.issues.filter(issue => issue.code === "too_big");
    assert.ok(expected.some(issue => issue.message === result.error.issues[0].message));
  }
});

test("nested and union admissions retain paths and prevent later refinements", () => {
  let refined = 0;
  const nested = boundedArray(z.array(boundedArray(z.array(z.string()).max(2))).max(2));
  const schema = z.object({ values: nested }).strict().refine(() => { refined++; return true; });
  const invalid = schema.safeParse({ values: [["a", "b", "c"]] });
  assert.equal(invalid.success, false);
  assert.equal(refined, 0);
  assert.deepEqual(invalid.error.issues[0].path, ["values", 0]);
  const branch = z.discriminatedUnion("kind", [z.object({ kind: z.literal("a"), values: nested }), z.object({ kind: z.literal("b") })]);
  assert.deepEqual(branch.parse({ kind: "a", values: [["ok"]] }), { kind: "a", values: [["ok"]] });
  assert.deepEqual(z.object({ values: nested }).partial().extend({ id: z.string() }).parse({ id: "ok" }), { id: "ok" });
});

function arraySites(roots) {
  const seen = new Set(), sites = [];
  function walk(schema, admission) {
    if (!(schema instanceof z.ZodType) || seen.has(schema)) return;
    seen.add(schema);
    const def = schema._def;
    if (schema instanceof z.ZodArray) { sites.push({ schema, admission }); walk(def.type); }
    else if (schema instanceof z.ZodEffects) walk(def.schema, def.effect.type === "preprocess" ? schema : undefined);
    else if (schema instanceof z.ZodObject) Object.values(schema.shape).forEach(value => walk(value));
    else if (schema instanceof z.ZodUnion || schema instanceof z.ZodDiscriminatedUnion) [...schema.options].forEach(value => walk(value));
    else if (schema instanceof z.ZodOptional || schema instanceof z.ZodNullable || schema instanceof z.ZodDefault) walk(def.innerType);
  }
  roots.forEach(schema => walk(schema));
  return sites;
}

test("all sixteen actual application array sites admit their original bound before element reads", () => {
  const sites = arraySites([...Object.values(schemas), ...Object.values(transfer), automationRequest]);
  assert.equal(sites.length, 16);
  for (const { schema, admission } of sites) {
    assert.ok(admission, "actual application array has no admission wrapper");
    const maximum = schema._def.maxLength.value;
    const input = Array(maximum + 1).fill(0);
    let reads = 0;
    Object.defineProperty(input, 0, { get() { reads++; return 0; } });
    const result = admission.safeParse(input);
    assert.equal(result.success, false);
    assert.equal(reads, 0);
    assert.equal(result.error.issues.length, 1);
    assert.equal(result.error.issues[0].maximum, maximum);
  }
});

test("actual optional, partial, nested transfer and automation schemas preserve valid shapes", () => {
  const id = "11111111-1111-4111-8111-111111111111";
  assert.deepEqual(schemas.mountUpdate.parse({ revision: 1, name: "main" }), { revision: 1, name: "main" });
  assert.deepEqual(schemas.dataChange.parse({ fields: [] }), { fields: [] });
  const bundle = { format: "bortus-kv", version: 1, documents: [{ mountId: id, path: "app/key", namespace: "default", name: "app",
    mappings: [{ field: "password", key: "password" }], fields: [{ field: "password", encoding: "utf8", value: "synthetic" }] }] };
  assert.deepEqual(transfer.bundleSchema.parse(bundle), bundle);
  assert.deepEqual(automationRequest.parse({ operation: "update", pathId: id, fields: [] }), { operation: "update", pathId: id, fields: [] });
  assert.equal(schemas.policyCreateRequest.safeParse({ principal: "writer", mountId: id, prefix: "", effect: "allow", actions: ["read"] }).success, true);
});

function originalModule(name) {
  const ts = require("typescript");
  const filename = path.resolve(import.meta.dirname, "../src/lib/" + name + ".ts");
  let text = fs.readFileSync(filename, "utf8");
  const source = ts.createSourceFile(filename, text, ts.ScriptTarget.Latest, true), edits = [];
  function visit(node) {
    if (ts.isImportDeclaration(node) && node.moduleSpecifier.text === "./bounded-array") edits.push([node.getFullStart(), node.end, ""]);
    if (ts.isCallExpression(node) && node.expression.getText(source) === "boundedArray") {
      assert.equal(node.arguments.length, 1);
      edits.push([node.getStart(source), node.arguments[0].getStart(source), ""], [node.arguments[0].end, node.end, ""]);
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
  for (const [start, end, value] of edits.sort((a, b) => b[0] - a[0])) text = text.slice(0, start) + value + text.slice(end);
  const loaded = new Module(filename);
  loaded.filename = filename;
  loaded.paths = Module._nodeModulePaths(path.dirname(filename));
  loaded._compile(ts.transpileModule(text, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText, filename);
  return loaded.exports;
}

test("actual schemas retain original in-bound validation results", () => {
  const originalSchemas = originalModule("kv-schemas");
  const originalTransfer = originalModule("kv-transfer");
  const id = "11111111-1111-4111-8111-111111111111";
  const corpus = [undefined, null, [], {}, { revision: 1 }, { name: "main", namespaces: ["default"] },
    { name: "main", namespaces: [0] }, { name: "main", namespaces: [] }, { fields: [{ field: "key", encoding: "utf8", value: "synthetic" }] },
    { fields: [{ field: "key", encoding: "bad", value: 0 }] }, { principal: "writer", mountId: id, prefix: "", effect: "allow", actions: ["read"] },
    { principal: "writer", mountId: id, prefix: "", effect: "allow", actions: ["invalid"] }, { pathId: id }, { versions: [0, 1] }];
  const normalize = result => result.success ? { data: result.data } : { issues: result.error.issues };
  for (const [current, original] of [[schemas, originalSchemas], [transfer, originalTransfer]])
    for (const [name, schema] of Object.entries(current)) {
      if (!(schema instanceof z.ZodType)) continue;
      assert.ok(original[name] instanceof z.ZodType);
      for (const input of corpus) assert.deepEqual(normalize(schema.safeParse(input)), normalize(original[name].safeParse(input)), name);
    }
});

test("actual KV body retains fixed redacted 400 and body-size precedence", async () => {
  const body = JSON.stringify({ name: "main", namespaces: Array(129).fill("private-synthetic-marker") });
  const request = () => new Request("http://bortus.invalid/api/kv/mounts", { method: "POST", headers: { "content-type": "application/json" }, body });
  let error;
  try { await kvBody(request(), schemas.mountCreate); } catch (caught) { error = caught; }
  assert.equal(error.status, 400);
  assert.equal(error.message, "Invalid KV request fields");
  const response = kvErrorResponse(error);
  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { error: "Invalid KV request fields" });
  await assert.rejects(kvBody(request(), schemas.mountCreate, 8), { status: 413, message: "KV request exceeds the body limit" });
});

test("larger administrator-body read still checks authority before reading", async () => {
  let read = false;
  const request = { get headers() { read = true; throw new Error("body read before authority"); } };
  const denied = new Error("synthetic denied");
  await assert.rejects(kvAdminMetadataBody({ admin: async () => { throw denied; } }, {}, request, schemas.mountCreate), error => error === denied);
  assert.equal(read, false);
});

test("source census refuses unguarded application arrays, sets, maps and alternate Zod imports", () => {
  const ts = require("typescript");
  let arrays = 0;
  function check(file) {
    const text = fs.readFileSync(file, "utf8"), source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true);
    function visit(node) {
      if (ts.isImportDeclaration(node) && node.moduleSpecifier.text.startsWith("zod")) {
        assert.equal(node.moduleSpecifier.text, "zod/v3");
        const bindings = node.importClause?.namedBindings;
        assert.ok(bindings && ts.isNamedImports(bindings));
        assert.deepEqual(bindings.elements.map(item => item.name.text), ["z"]);
      }
      if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression) && node.expression.expression.getText(source) === "z") {
        const kind = node.expression.name.text;
        assert.ok(!["set", "map"].includes(kind), "new container needs explicit admission review");
        if (kind === "array") {
          arrays++;
          let current = node;
          while (ts.isPropertyAccessExpression(current.parent) && ts.isCallExpression(current.parent.parent)) current = current.parent.parent;
          assert.ok(ts.isCallExpression(current.parent) && current.parent.expression.getText(source) === "boundedArray",
            "array schema lacks outer boundedArray admission: " + file);
        }
      }
      ts.forEachChild(node, visit);
    }
    visit(source);
  }
  function walk(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const file = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(file);
      else if (/\.tsx?$/.test(file)) check(file);
    }
  }
  walk(path.resolve(import.meta.dirname, "../src"));
  assert.equal(arrays, 16);
});


test("combined bounds keep original issue priority at each rejected length", async () => {
  for (const original of [z.array(z.string()).max(1, "maximum").length(2, "exact"),
    z.array(z.string()).length(2, "exact").max(1, "maximum"),
    z.array(z.string()).max(2, "maximum").length(2, "exact"),
    z.array(z.string()).max(3, "maximum").length(2, "exact"),
    z.array(z.string()).max(0, "empty").length(2),
    z.array(z.string()).max(1).length(0, "none")]) {
    const upper = Math.min(...[original._def.maxLength, original._def.exactLength]
      .filter(bound => bound !== null).map(bound => bound.value));
    for (let length = upper + 1; length <= 5; length++) {
      const baseline = original.safeParse(Array(length).fill("ok"));
      assert.equal(baseline.success, false);
      const expected = baseline.error.issues.find(issue => issue.code === "too_big");
      assert.ok(expected);
      const fields = issue => ({ code: issue.code, maximum: issue.maximum, type: issue.type,
        inclusive: issue.inclusive, exact: issue.exact, message: issue.message, path: issue.path });
      for (const asyncParse of [false, true]) {
        let reads = 0, visits = 0;
        const element = z.string().superRefine(() => { visits++; });
        const guarded = boundedArray(new z.ZodArray({ ...original._def, type: element }));
        const input = Array(length).fill("ok");
        Object.defineProperty(input, 0, { get() { reads++; return "ok"; } });
        const schema = z.object({ values: guarded });
        const result = asyncParse ? await schema.safeParseAsync({ values: input }) : schema.safeParse({ values: input });
        assert.equal(result.success, false);
        assert.equal(reads, 0, "rejected array element was read");
        assert.equal(visits, 0, "rejected array element refinement ran");
        assert.equal(result.error.issues.length, 1);
        assert.equal(result.error.issues[0].fatal, true);
        assert.deepEqual(fields(result.error.issues[0]), { ...fields(expected), path: ["values"] });
      }
    }
  }
});
