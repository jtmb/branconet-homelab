import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import type { QuerySnapshot } from "../src/lib/query-store";

// Actual public parent declarations/retention JSX with inert child components.
// No React mount, effects, DOM, requests, backend or native operation.
type Element = { type: string; props: Record<string, unknown> };
const filename = "src/app/(dashboard)/secrets/kv/kv-browser.tsx";
const source = ts.createSourceFile(filename, readFileSync(filename, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const ui = ts.createSourceFile("ui.tsx", readFileSync("src/app/(dashboard)/secrets/kv/kv-ui.tsx", "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const detail = source.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === "PathDetail");
assert(detail && ts.isFunctionDeclaration(detail) && detail.body);
const declarations = detail.body.statements.filter(ts.isVariableStatement).flatMap(node => [...node.declarationList.declarations]);
const declaration = (name: string) => { const node = declarations.find(node => node.name.getText(source) === name); assert(node?.initializer); return `const ${name} = ${node.initializer.getText(source)};`; };
const helpers = ui.statements.filter(node => ts.isFunctionDeclaration(node) && ["usable", "fresh"].includes(node.name?.text ?? ""));
assert.equal(helpers.length, 2);
const branches: ts.BinaryExpression[] = [];
function select(node: ts.Node) {
  if (ts.isBinaryExpression(node) && node.left.getText(source) === "session.canKvWrite && caps?.permissions.update") branches.push(node);
  ts.forEachChild(node, select);
}
select(detail.body); assert.equal(branches.length, 1);
const output = ts.transpileModule(helpers.map(node => node.getText(ui)).join("\n") + `\nfunction project(id) { ${["session", "pathQuery", "capabilities", "permitted", "path", "caps", "canUpdate"].map(declaration).join("\n")} return { path, canUpdate, body: path && (${branches[0].getText(source)}) }; }\nmodule.exports = project;`, {
  fileName: "public-retention-parent.tsx", compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;
const path = { id: "selected-a", mountId: "mount-a", path: "public/example", namespace: "synthetic", name: "metadata-only", revision: 7, retention: 3, fields: [{ field: "public-field", key: "exact-key" }] };
const caps = { pathId: path.id, revision: 7, permissions: { update: true } };
const now = 100000;
const explanation = "Saving and reloading retention are currently unavailable. Refresh path metadata, capabilities and session information before trying again. Editing the draft does not change saved metadata.";
const snapshot = (data: unknown, overrides: Partial<QuerySnapshot> = {}): QuerySnapshot => ({ data, error: undefined, status: 200, loading: false, refreshing: false, stale: false, updatedAt: now, ...overrides });
function walk(value: unknown): Element[] {
  if (Array.isArray(value)) return value.flatMap(walk);
  return value && typeof value === "object" && "props" in value ? [value as Element, ...walk((value as Element).props.children)] : [];
}
function text(value: unknown): string {
  if (Array.isArray(value)) return value.map(text).join("");
  if (value && typeof value === "object" && "props" in value) return text((value as Element).props.children);
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}
function model(pathQuery = snapshot(path), capabilities = snapshot(caps), canKvWrite = true, id = path.id) {
  const component = { exports: undefined as unknown as (id: string) => { path: unknown; canUpdate: unknown; body: Element } };
  const calls: string[] = [];
  const jsx = (type: string, props: Element["props"]): Element => ({ type, props });
  runInNewContext(output, { module: component, exports: {}, RetentionForm: "RetentionForm", useSession: () => ({ canKvWrite }),
    Date: { now: () => now }, useQuery: (url: string) => { calls.push(url); if (url === `/api/kv/paths/${id}`) return pathQuery; assert.equal(url, `/api/kv/paths/${id}/capabilities`); return capabilities; },
    require: (name: string) => { assert.equal(name, "react/jsx-runtime"); return { jsx, jsxs: jsx, Fragment: "fragment" }; },
  });
  const result = component.exports(id), nodes = walk(result.body);
  assert.deepEqual(calls, [`/api/kv/paths/${id}`, `/api/kv/paths/${id}/capabilities`]);
  return { ...result, nodes, form: nodes.find(node => node.type === "RetentionForm"), paragraphs: nodes.filter(node => node.type === "p") };
}
for (const [label, pathInput, capsInput] of [
  ["stale path", snapshot(path, { stale: true }), snapshot(caps)],
  ["stale capabilities", snapshot(path), snapshot(caps, { stale: true })],
  ["expired path at exact boundary", snapshot(path, { updatedAt: now - 15000 }), snapshot(caps)],
  ["expired capabilities at exact boundary", snapshot(path), snapshot(caps, { updatedAt: now - 15000 })],
  ["older path", snapshot(path, { updatedAt: now - 15001 }), snapshot(caps)],
  ["older capabilities", snapshot(path), snapshot(caps, { updatedAt: now - 15001 })],
  ["path error", snapshot(path, { status: 503, error: "Synthetic unavailable" }), snapshot(caps)],
  ["capability error", snapshot(path), snapshot(caps, { status: 503, error: "Synthetic unavailable" })],
  ["conflict metadata", snapshot(path, { status: 409, error: "Synthetic conflict" }), snapshot(caps)],
  ["capability revision mismatch", snapshot(path), snapshot({ ...caps, revision: 8 })],
  ["returned path revision mismatch", snapshot({ ...path, revision: 8, retention: 6 }), snapshot(caps)],
] as const) test(`${label} explains existing disabled editability with retained public metadata`, () => {
  const m = model(pathInput, capsInput);
  assert.equal(m.canUpdate, false); assert(m.form); assert.equal(m.form.props.editable, false);
  assert.equal(m.form.props.path, pathInput.data); assert.equal(m.path, pathInput.data);
  assert.equal(m.paragraphs.length, 1); assert.equal(text(m.paragraphs[0]), explanation);
  assert.equal(m.paragraphs[0].props.role, undefined); assert.equal(m.paragraphs[0].props.id, undefined);
  assert.equal(m.nodes.some(node => node.type === "button"), false);
});
for (const [label, pathInput, capsInput, writer] of [
  ["no capability data", snapshot(path), snapshot(undefined, { loading: true }), true],
  ["update permission absent", snapshot(path), snapshot({ ...caps, permissions: {} }), true],
  ["update permission false", snapshot(path), snapshot({ ...caps, permissions: { update: false } }), true],
  ["writer unavailable", snapshot(path), snapshot(caps), false],
  ["no path data", snapshot(undefined, { loading: true }), snapshot(caps), true],
  ["path denial401", snapshot(path, { status: 401, error: "Synthetic denial" }), snapshot(caps), true],
  ["path denial403", snapshot(path, { status: 403, error: "Synthetic denial" }), snapshot(caps), true],
  ["capability denial401", snapshot(path), snapshot(caps, { status: 401, error: "Synthetic denial" }), true],
  ["capability denial403", snapshot(path), snapshot(caps, { status: 403, error: "Synthetic denial" }), true],
] as const) test(`${label} preserves existing hidden form and has no orphan explanation`, () => {
  const m = model(pathInput, capsInput, writer); assert.equal(m.form, undefined); assert.equal(m.paragraphs.length, 0);
});
test("fresh permitted metadata has original exact path and editable form without explanation", () => {
  const m = model(); assert.equal(m.canUpdate, true); assert(m.form); assert.equal(m.form.props.path, path); assert.equal(m.form.props.editable, true); assert.equal(m.paragraphs.length, 0);
});
test("in-flight refresh within successful-read age preserves existing editable state", () => {
  const m = model(snapshot(path, { refreshing: true, updatedAt: now - 14999 }), snapshot(caps, { refreshing: true, updatedAt: now - 14999 }));
  assert.equal(m.canUpdate, true); assert.equal(m.form?.props.editable, true); assert.equal(m.paragraphs.length, 0);
});
test("selected identity and exact metadata object remain owned by the original queries", () => {
  const other = { ...path, id: "selected-b", revision: 9, retention: 5 };
  const m = model(snapshot(other, { stale: true }), snapshot({ ...caps, pathId: other.id, revision: 9 }), true, other.id);
  assert.equal(m.form?.props.path, other); assert.equal(text(m.paragraphs[0]), explanation);
});
test("pathId-only capability mismatch preserves original editability expression without new authority claim", () => {
  const m = model(snapshot(path), snapshot({ ...caps, pathId: "different-path" }));
  assert.equal(m.canUpdate, true); assert.equal(m.form?.props.editable, true); assert.equal(m.paragraphs.length, 0);
});
test("public stale snapshots are not mutated or replaced by the explanatory parent", () => {
  const p = snapshot(path, { stale: true }), c = snapshot(caps, { stale: true });
  const before = JSON.stringify({ p, c }); const m = model(p, c);
  assert.equal(JSON.stringify({ p, c }), before); assert.equal(m.form?.props.path, path); assert.equal(text(m.paragraphs[0]), explanation);
});
test("stale to fresh metadata transition keeps exact form child identity and clears explanation", () => {
  const stale = model(snapshot(path, { stale: true }), snapshot(caps)), current = model();
  assert.equal(stale.form?.type, current.form?.type); assert.equal(stale.form?.props.path, current.form?.props.path);
  assert.equal(stale.form?.props.key, undefined); assert.equal(current.form?.props.key, undefined);
  assert.equal(text(stale.paragraphs[0]), explanation); assert.equal(current.paragraphs.length, 0);
});
