import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import type { QuerySnapshot } from "../src/lib/query-store";

// Only the public mapping table and adjacent mapping-length explanation are
// selected. No component mount, hook/effect lifecycle, forms or native queries.
type Element = { type: string; props: Record<string, unknown> };
const file = "src/app/(dashboard)/secrets/kv/kv-browser.tsx";
const source = ts.createSourceFile(file, readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const ui = ts.createSourceFile("ui.tsx", readFileSync("src/app/(dashboard)/secrets/kv/kv-ui.tsx", "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const detail = source.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === "PathDetail");
assert(detail && ts.isFunctionDeclaration(detail) && detail.body);
const declarations = detail.body.statements.filter(ts.isVariableStatement).flatMap(node => [...node.declarationList.declarations]);
const declaration = (name: string) => { const node = declarations.find(node => node.name.getText(source) === name); assert(node?.initializer); return `const ${name} = ${node.initializer.getText(source)};`; };
const bodies: ts.JsxFragment[] = [];
function select(node: ts.Node) {
  if (ts.isBinaryExpression(node) && node.left.getText(source) === "path" && ts.isJsxFragment(node.right)) bodies.push(node.right);
  ts.forEachChild(node, select);
}
select(detail.body); assert.equal(bodies.length, 1);
const children = bodies[0].children.filter(node =>
  (ts.isJsxSelfClosingElement(node) && node.tagName.getText(source) === "MetadataTable" && node.getText(source).includes('label="KV field mappings"')) ||
  (ts.isJsxExpression(node) && !!node.expression && node.expression.getText(source).includes("path.fields.length")));
assert.equal(children.filter(ts.isJsxSelfClosingElement).length, 1);
const helpers = ui.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === "usable"); assert.equal(helpers.length, 1);
const code = ts.transpileModule(helpers[0].getText(ui) + `\nfunction project(id) { ${["pathQuery", "capabilities", "permitted", "path"].map(declaration).join("\n")} return { path, body: path && <>${children.map(node => node.getText(source)).join("\n")}</> }; }\nmodule.exports = project;`, {
  fileName: "public-mapping-snapshot.tsx", compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;
const explanation = "No field mappings are recorded in this path metadata snapshot. This does not establish whether native data exists.";
const path = { id: "selected-a", mountId: "mount-a", path: "public/example", namespace: "synthetic", name: "metadata-only", revision: 7, retention: 3, fields: [] as { field: string; key: string }[] };
const snapshot = (data: unknown, overrides: Partial<QuerySnapshot> = {}): QuerySnapshot => ({ data, error: undefined, status: 200, loading: false, refreshing: false, stale: false, updatedAt: 100000, ...overrides });
function walk(value: unknown): Element[] {
  if (Array.isArray(value)) return value.flatMap(walk);
  return value && typeof value === "object" && "props" in value ? [value as Element, ...walk((value as Element).props.children)] : [];
}
function text(value: unknown): string {
  if (Array.isArray(value)) return value.map(text).join("");
  if (value && typeof value === "object" && "props" in value) return text((value as Element).props.children);
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}
function model(pathQuery = snapshot(path), capabilities = snapshot({ pathId: path.id, revision: 7, permissions: {} }), id = path.id) {
  const component = { exports: undefined as unknown as (id: string) => { path: unknown; body: Element } };
  const calls: string[] = [], before = JSON.stringify({ pathQuery, capabilities });
  const jsx = (type: string, props: Element["props"]): Element => ({ type, props });
  runInNewContext(code, { module: component, exports: {}, MetadataTable: "MetadataTable", useQuery: (url: string) => {
    calls.push(url); if (url === `/api/kv/paths/${id}`) return pathQuery;
    assert.equal(url, `/api/kv/paths/${id}/capabilities`); return capabilities;
  }, require: (name: string) => { assert.equal(name, "react/jsx-runtime"); return { jsx, jsxs: jsx, Fragment: "fragment" }; } });
  const result = component.exports(id), nodes = walk(result.body);
  assert.deepEqual(calls, [`/api/kv/paths/${id}`, `/api/kv/paths/${id}/capabilities`]);
  assert.equal(JSON.stringify({ pathQuery, capabilities }), before);
  return { ...result, nodes, table: nodes.find(node => node.type === "MetadataTable"), paragraphs: nodes.filter(node => node.type === "p") };
}
function expectEmpty(m: ReturnType<typeof model>, original: unknown) {
  assert.equal(m.path, original); assert(m.table); assert.equal(JSON.stringify(m.table.props.rows), "[]");
  assert.equal(m.paragraphs.length, 1); assert.equal(text(m.paragraphs[0]), explanation);
  for (const key of ["role", "id", "aria-live", "aria-describedby", "tabIndex", "onClick"]) assert.equal(m.paragraphs[0].props[key], undefined);
  assert.equal(m.nodes.some(node => ["button", "input", "form"].includes(node.type)), false);
}
for (const [label, overrides] of [
  ["fresh", {}], ["stale", { stale: true }], ["refreshing", { refreshing: true }],
  ["expired", { updatedAt: 0 }], ["retained503", { status: 503, error: "Synthetic unavailable", stale: true }],
  ["retained409", { status: 409, error: "Synthetic conflict", stale: true }],
] as const) test(`${label} empty saved metadata explains the snapshot without native-state claims`, () => {
  expectEmpty(model(snapshot(path, overrides)), path);
});
for (const [label, capabilities] of [
  ["missing capabilities", snapshot(undefined, { loading: true })],
  ["capabilities error", snapshot(undefined, { status: 503, error: "Synthetic unavailable" })],
  ["capabilities stale", snapshot({ permissions: {} }, { stale: true })],
  ["update permitted", snapshot({ pathId: path.id, revision: 7, permissions: { update: true } })],
  ["update denied", snapshot({ pathId: path.id, revision: 7, permissions: { update: false } })],
  ["capability identity mismatch", snapshot({ pathId: "other", revision: 8, permissions: {} })],
] as const) test(`${label} preserves ordinary empty public metadata explanation`, () => {
  expectEmpty(model(snapshot(path), capabilities), path);
});
for (const denied of [401, 403]) for (const target of ["path", "capabilities"] as const) test(`${target} denial${denied} hides empty metadata and has no orphan explanation`, () => {
  const blocked = snapshot(path, { status: denied, error: "Synthetic denial", stale: true });
  const m = target === "path" ? model(blocked) : model(snapshot(path), blocked);
  assert.equal(m.path, undefined); assert.equal(m.table, undefined); assert.equal(m.paragraphs.length, 0);
});
for (const state of ["loading", "failure"] as const) test(`no path data during ${state} has no empty mapping claim`, () => {
  const m = model(snapshot(undefined, state === "loading" ? { loading: true } : { status: 503, error: "Synthetic unavailable" }));
  assert.equal(m.path, undefined); assert.equal(m.table, undefined); assert.equal(m.paragraphs.length, 0);
});
for (const fields of [
  [{ field: "public-field", key: "exact-key" }],
  [{ field: "z_field", key: "x.y" }, { field: "A-field", key: "_Exact_" }],
] as const) test(`${fields.length} explicit mappings retain exact rows and columns without empty explanation`, () => {
  const selected = { ...path, fields }; const m = model(snapshot(selected)); assert.equal(m.path, selected); assert(m.table);
  assert.equal(JSON.stringify(m.table.props.rows), JSON.stringify(fields.map(item => ({ id: item.field, field: item.field, key: item.key }))));
  assert.equal(m.table.props.label, "KV field mappings"); assert.equal(m.table.props.actions, undefined);
  assert.equal(JSON.stringify(m.table.props.columns), JSON.stringify([{ key: "field", label: "Logical field" }, { key: "key", label: "Exact native key" }]));
  assert.equal(m.paragraphs.length, 0);
});
test("exact selected identity and returned public metadata object remain unchanged", () => {
  const selected = { ...path, id: "selected-b", path: "other/exact", revision: 12, namespace: "other-ns", name: "other-name" };
  expectEmpty(model(snapshot(selected), snapshot({ pathId: selected.id }), selected.id), selected);
});
test("nonempty to empty to nonempty public snapshots retain table identity and exact source rows", () => {
  const selected = { ...path, fields: [{ field: "same-field", key: "same_key" }] };
  const before = model(snapshot(selected)), empty = model(), after = model(snapshot(selected));
  assert.equal(before.table?.type, empty.table?.type); assert.equal(empty.table?.type, after.table?.type);
  assert.equal(JSON.stringify(before.table?.props.rows), JSON.stringify(after.table?.props.rows));
  assert.equal(before.paragraphs.length, 0); expectEmpty(empty, path); assert.equal(after.paragraphs.length, 0);
});
