import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import type { QuerySnapshot } from "../src/lib/query-store";

// Evaluate only public snapshot declarations and the actual summary JSX.
// No React mount/effects, requests, forms, native handlers or private workbench.
type Element = { type: string; props: { children?: unknown } };
const parse = (file: string) => ts.createSourceFile(file, readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const browser = parse("src/app/(dashboard)/secrets/kv/kv-browser.tsx");
const ui = parse("src/app/(dashboard)/secrets/kv/kv-ui.tsx");
const detail = browser.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === "PathDetail");
assert(detail && ts.isFunctionDeclaration(detail) && detail.body);
const declarations = detail.body.statements.filter(ts.isVariableStatement).flatMap(node => [...node.declarationList.declarations]);
const names = ["pathQuery", "capabilities", "permitted", "path", "caps", "freshCapabilities", "summaryCapabilities"];
const selected = names.flatMap(name => {
  const node = declarations.find(node => node.name.getText(browser) === name);
  if (name === "summaryCapabilities" && !node) return [];
  assert(node?.initializer); return [`const ${name} = ${node.initializer.getText(browser)};`];
});
const returned = detail.body.statements.find(ts.isReturnStatement)?.expression;
assert(returned && ts.isJsxElement(returned));
const summaries = returned.children.filter(node => ts.isJsxExpression(node) && node.getText(browser).includes("Allowed actions:"));
assert.equal(summaries.length, 1);
const summary = summaries[0]; assert(ts.isJsxExpression(summary) && summary.expression);
const helpers = ui.statements.filter(node => ts.isFunctionDeclaration(node) && ["usable", "fresh"].includes(node.name?.text ?? ""));
assert.equal(helpers.length, 2);
const output = ts.transpileModule(helpers.map(node => node.getText(ui)).join("\n") + `\nfunction project(id) { ${selected.join("\n")} return ${summary.expression.getText(browser)}; }\nmodule.exports = { project };`, {
  fileName: "public-capability-summary.tsx", compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;
const now = 20000;
const path = { id: "selected-a", mountId: "mount-exact", path: "public/example", namespace: "synthetic", name: "metadata-only", revision: 7, retention: 3, fields: [{ field: "public-field", key: "exact-key" }] };
const caps = { pathId: "selected-a", revision: 7, permissions: { read: true, list: false, update: true }, nativeMutationEnabled: true, initializationAllowed: false, guardVerification: "operator-assertion" };
const snapshot = (data: unknown, overrides: Partial<QuerySnapshot> = {}): QuerySnapshot => ({ data, error: undefined, status: 200, loading: false, refreshing: false, stale: false, updatedAt: now, ...overrides });
function text(value: unknown): string {
  if (Array.isArray(value)) return value.map(text).join("");
  if (value && typeof value === "object" && "props" in value) return text((value as Element).props.children);
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}
function model(pathQuery = snapshot(path), capabilities = snapshot(caps), id = "selected-a") {
  const component = { exports: {} as { project: (id: string) => unknown } }, calls: string[] = [];
  const jsx = (type: string, props: Element["props"]): Element => ({ type, props });
  runInNewContext(output, { module: component, exports: component.exports, Date: { now: () => now }, useQuery: (url: string) => {
    calls.push(url);
    if (url === `/api/kv/paths/${id}`) return pathQuery;
    assert.equal(url, `/api/kv/paths/${id}/capabilities`); return capabilities;
  }, require: (name: string) => { assert.equal(name, "react/jsx-runtime"); return { jsx, jsxs: jsx, Fragment: "fragment" }; } });
  const result = text(component.exports.project(id));
  assert.deepEqual(calls, [`/api/kv/paths/${id}`, `/api/kv/paths/${id}/capabilities`]);
  return result;
}
const unavailable = "Current allowed actions and native mutation status are unavailable. Refresh path metadata and capabilities for this selection. External admission/RBAC verification is still required.";
for (const enabled of [true, false]) test(`fresh matching public snapshot, operator assertion ${enabled}`, () => {
  assert.equal(model(snapshot(path), snapshot({ ...caps, nativeMutationEnabled: enabled })), `Allowed actions: read, update.Native value mutations ${enabled ? "enabled by operator assertion" : "disabled"}. External admission/RBAC verification is still required.`);
});
test("fresh matching empty permission set reports none", () => {
  assert.match(model(snapshot(path), snapshot({ ...caps, permissions: { read: false, update: false } })), /^Allowed actions: none\./);
});
test("fresh matching different selected identity preserves exact query ownership", () => {
  assert.match(model(snapshot({ ...path, id: "selected-b" }), snapshot({ ...caps, pathId: "selected-b" }), "selected-b"), /^Allowed actions: read, update\./);
});
for (const [label, pathInput, capsInput] of [
  ["stale capability", snapshot(path), snapshot(caps, { stale: true })],
  ["stale path", snapshot(path, { stale: true }), snapshot(caps)],
  ["expired capability", snapshot(path), snapshot(caps, { updatedAt: now - 15000 })],
  ["expired path", snapshot(path, { updatedAt: now - 15000 }), snapshot(caps)],
  ["old capability", snapshot(path), snapshot(caps, { updatedAt: now - 15001 })],
  ["ordinary capability error", snapshot(path), snapshot(caps, { error: "Synthetic unavailable", status: 503 })],
  ["ordinary path error", snapshot(path, { error: "Synthetic unavailable", status: 503 }), snapshot(caps)],
  ["no capability", snapshot(path), snapshot(undefined, { loading: true })],
  ["no path", snapshot(undefined, { loading: true }), snapshot(caps)],
  ["different capability path", snapshot(path), snapshot({ ...caps, pathId: "other-selected" })],
  ["different metadata revision", snapshot(path), snapshot({ ...caps, revision: 8 })],
  ["returned path revision changed", snapshot({ ...path, revision: 8 }), snapshot(caps)],
] as const) test(`${label} qualifies both claims without exposing retained permissions`, () => {
  assert.equal(model(pathInput, capsInput), unavailable);
});
for (const status of [401, 403]) for (const retained of [true, false]) test(`capability denial ${status}, retained ${retained}`, () => {
  assert.equal(model(snapshot(path), snapshot(retained ? caps : undefined, { status, error: "Synthetic denial" })), unavailable);
});
for (const status of [401, 403]) test(`path denial ${status} suppresses capability summary`, () => {
  assert.equal(model(snapshot(path, { status, error: "Synthetic denial" }), snapshot(caps)), unavailable);
});
test("in-flight refresh within original successful-read age retains usable summary", () => {
  assert.match(model(snapshot(path, { refreshing: true, updatedAt: now - 14999 }), snapshot(caps, { refreshing: true, updatedAt: now - 14999 })), /^Allowed actions: read, update\./);
});
test("ordinary stale error keeps caller public metadata and permissions intact", () => {
  const pathInput = snapshot(path, { stale: true, error: "Synthetic unavailable", status: 503 });
  const capsInput = snapshot(caps, { stale: true, error: "Synthetic unavailable", status: 503 });
  assert.equal(model(pathInput, capsInput), unavailable);
  assert.equal(pathInput.data, path); assert.equal(capsInput.data, caps);
  assert.equal(path.retention, 3); assert.equal(caps.permissions.update, true);
});
