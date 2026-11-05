import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import type { QuerySnapshot } from "../src/lib/query-store";

// Select only actual public path-query keys, denial projection, and its QueryState.
// Synthetic snapshots/JSX only: no React hooks/effects, forms, DOM or requests.
type Element = { type: string; props: Record<string, unknown> };
const parse = (file: string) => ts.createSourceFile(file, readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const browser = parse("src/app/(dashboard)/secrets/kv/kv-browser.tsx");
const ui = parse("src/app/(dashboard)/secrets/kv/kv-ui.tsx");
const detail = browser.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === "PathDetail");
assert(detail && ts.isFunctionDeclaration(detail) && detail.body);
const declarations = detail.body.statements.filter(ts.isVariableStatement).flatMap(node => [...node.declarationList.declarations]);
const declaration = (name: string) => { const node = declarations.find(node => node.name.getText(browser) === name); assert(node?.initializer); return `const ${name} = ${node.initializer.getText(browser)};`; };
const states: ts.JsxSelfClosingElement[] = [];
function select(node: ts.Node) {
  if (ts.isJsxSelfClosingElement(node) && node.tagName.getText(browser) === "QueryState" && node.attributes.properties.some(prop => ts.isJsxAttribute(prop) && prop.name.getText(browser) === "label" && prop.initializer && ts.isStringLiteral(prop.initializer) && prop.initializer.text === "path metadata")) states.push(node);
  ts.forEachChild(node, select);
}
select(detail.body); assert.equal(states.length, 1);
const helpers = ui.statements.filter(node => ts.isFunctionDeclaration(node) && ["usable", "QueryState"].includes(node.name?.text ?? ""));
assert.equal(helpers.length, 2);
const output = ts.transpileModule(helpers.map(node => node.getText(ui)).join("\n") + `\nfunction project(id) { ${["pathQuery", "capabilities", "permitted", "path"].map(declaration).join("\n")} return { path, element: ${states[0].getText(browser)} }; }\nmodule.exports = { project, QueryState };`, {
  fileName: "selected-public-path.tsx", compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;
const metadata = { id: "selected-a", path: "public/example", namespace: "synthetic", name: "metadata-only", revision: 7, retention: 3, fields: [{ field: "public-field", key: "exact-key" }] };
const snapshot = (overrides: Partial<QuerySnapshot> = {}): QuerySnapshot => ({ data: undefined, error: undefined, status: undefined, loading: false, refreshing: false, stale: false, updatedAt: 1000, ...overrides });
function walk(value: unknown): Element[] {
  if (Array.isArray(value)) return value.flatMap(walk);
  return value && typeof value === "object" && "props" in value ? [value as Element, ...walk((value as Element).props.children)] : [];
}
function text(value: unknown): string {
  if (Array.isArray(value)) return value.map(text).join("");
  if (value && typeof value === "object" && "props" in value) return text((value as Element).props.children);
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}
function model(pathQuery: QuerySnapshot, capabilities: QuerySnapshot, id = "selected-a") {
  let retries = 0;
  const retry = () => { retries++; };
  const pathInput = { ...pathQuery, refetch: retry }, calls: string[] = [];
  const component = { exports: {} as { project: (id: string) => { path: unknown; element: Element }; QueryState: (props: Record<string, unknown>) => Element } };
  const jsx = (type: string, props: Element["props"]): Element => ({ type, props });
  runInNewContext(output, { module: component, exports: component.exports, button: "button", useQuery: (url: string) => {
    calls.push(url);
    if (url === `/api/kv/paths/${id}`) return pathInput;
    assert.equal(url, `/api/kv/paths/${id}/capabilities`); return capabilities;
  }, require: (name: string) => { assert.equal(name, "react/jsx-runtime"); return { jsx, jsxs: jsx, Fragment: "fragment" }; } });
  const result = component.exports.project(id), props = result.element.props;
  const projected = props.query as QuerySnapshot;
  for (const key of ["status", "error", "loading", "refreshing", "stale", "updatedAt"] as const) assert.equal(projected[key], pathInput[key]);
  assert.equal(props.retry, retry); assert.equal(props.label, "path metadata");
  assert.deepEqual(calls, [`/api/kv/paths/${id}`, `/api/kv/paths/${id}/capabilities`]);
  return { ...result, nodes: walk(component.exports.QueryState(props)), retryCount: () => retries };
}
const statuses = (nodes: Element[]) => nodes.filter(node => node.props.role === "status").map(text);
for (const denied of [401, 403]) for (const failure of [409, 503]) for (const stale of [false, true]) {
  test(`capability ${denied}, retained path ${failure}, stale ${stale}: no claim of hidden metadata`, () => {
    const result = model(snapshot({ data: metadata, error: "Synthetic failure", status: failure, stale, refreshing: true }), snapshot({ status: denied }));
    assert.equal(result.path, undefined);
    const alert = result.nodes.find(node => node.props.role === "alert"); assert(alert);
    assert.deepEqual({ alert: text(alert), statuses: statuses(result.nodes) }, { alert: "path metadata unavailable: Synthetic failure Retry path metadata", statuses: ["Refreshing path metadata…"] });
    const retry = result.nodes.find(node => node.type === "button"); assert(retry); assert.equal(retry.props.disabled, undefined);
    (retry.props.onClick as () => void)(); assert.equal(result.retryCount(), 1);
  });
}
for (const failure of [409, 503]) for (const stale of [false, true]) test(`ordinary retained ${failure} metadata and stale ${stale} remain visible`, () => {
  const result = model(snapshot({ data: metadata, error: "Synthetic failure", status: failure, stale }), snapshot({ status: 200 }));
  assert.equal(result.path, metadata);
  assert.equal(text(result.nodes.find(node => node.props.role === "alert")), "path metadata unavailable: Synthetic failure Previously loaded metadata is shown. Retry path metadata");
  assert.deepEqual(statuses(result.nodes), stale ? ["Previously loaded path metadata metadata is stale."] : []);
});
for (const denied of [200, 401, 403]) test(`initial no-data loading under capability ${denied} retains initial status`, () => {
  const result = model(snapshot({ loading: true, refreshing: true, stale: true }), snapshot({ status: denied }));
  assert.equal(result.path, undefined); assert.deepEqual(statuses(result.nodes), ["Loading path metadata…"]);
  assert.equal(result.nodes.some(node => node.props.role === "alert"), false);
});
for (const failure of [401, 403, 409, 503]) test(`no usable path at ${failure} never claims retained body`, () => {
  const result = model(snapshot({ data: failure < 409 ? metadata : undefined, status: failure, error: "Synthetic failure", stale: true }), snapshot({ status: 200 }));
  assert.equal(result.path, undefined); assert.deepEqual(statuses(result.nodes), []);
  assert.equal(text(result.nodes.find(node => node.props.role === "alert")), "path metadata unavailable: Synthetic failure Retry path metadata");
});
for (const id of ["selected-a", "selected-b"]) test(`exact selected identity ${id} has no permitted collection-page dependency`, () => {
  const selected = { ...metadata, id };
  const result = model(snapshot({ data: selected, status: 200 }), snapshot({ status: 200 }), id);
  assert.equal(result.path, selected); assert.deepEqual(statuses(result.nodes), []);
});
