import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// Execute the actual presentation functions, without mounting the workspace or
// running requests. This verifies source semantics, not browser or AT behavior.
type Element = { type: string; props: Record<string, unknown> };
type Render = (props: Record<string, unknown>) => Element;
const filename = "src/components/secrets/kv-administration.tsx";
const source = readFileSync(filename, "utf8");
const parsed = ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const names = ["Cleanup", "Table", "TaskState"];
const declarations = parsed.statements.filter(statement =>
  ts.isFunctionDeclaration(statement) && names.includes(statement.name?.text ?? ""));
assert.equal(declarations.length, names.length);
const output = ts.transpileModule(
  declarations.map(statement => statement.getText(parsed)).join("\n") +
    "\nmodule.exports = { Cleanup, TaskState };",
  { fileName: filename, compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022,
  } },
).outputText;
const component = { exports: {} as Record<string, Render> };
const jsx = (type: string | Render, props: Element["props"]): Element =>
  typeof type === "function" ? type(props) : { type, props };
runInNewContext(output, { module: component, exports: component.exports,
  require: (name: string) => {
    assert.equal(name, "react/jsx-runtime");
    return { jsx, jsxs: jsx };
  },
});
function walk(value: unknown): Element[] {
  return Array.isArray(value) ? value.flatMap(walk)
    : value && typeof value === "object" && "props" in value
      ? [value as Element, ...walk((value as Element).props.children)] : [];
}
function text(value: unknown): string {
  return Array.isArray(value) ? value.map(text).join("")
    : value && typeof value === "object" && "props" in value
      ? text((value as Element).props.children)
      : typeof value === "string" || typeof value === "number" ? String(value) : "";
}
for (const complete of [true, false]) {
  test(`actual Cleanup gives the ${complete ? "complete" : "partial"} outcome summary status semantics only`, () => {
    const result = {
      operationId: "synthetic-operation", outcome: "committed", head: 3,
      resourceVersion: "synthetic-rv", cleanupComplete: complete,
      cleanup: [{ name: "synthetic-history", version: 2,
        outcome: complete ? "deleted" : "retained", status: complete ? 200 : 409 }],
    };
    const root = component.exports.Cleanup({ result });
    const elements = walk(root);
    const statuses = elements.filter(element => element.props.role === "status");
    assert.equal(statuses.length, 1, "The concise asynchronous outcome has one status role");
    const summary = statuses[0];
    assert.equal(summary.type, "p");
    assert.equal(text(summary), `Reference operation synthetic-operation: committed. History cleanup ${complete
      ? "complete" : "partial; retained or uncertain items need inspection"}. Head 3; resourceVersion synthetic-rv.`);
    assert.equal(walk(summary).length, 1, "Only the summary belongs to the status region");
    assert.equal(root.props.role, undefined);
    assert.equal(root.props["aria-live"], undefined);
    assert.equal(elements.filter(element => element.props.role === "alert").length, 0);
    const table = elements.find(element => element.type === "table");
    assert(table);
    assert.equal(table.props.role, undefined);
    assert.equal(table.props["aria-live"], undefined);
    assert.equal(walk(summary).includes(table), false);
    const row = elements.find(element => element.type === "tbody");
    assert(row);
    assert.equal(text(row), `synthetic-historyversion 2${complete ? "deleted200" : "retained409"}`);
    assert.equal(elements.some(element => "tabIndex" in element.props || "autoFocus" in element.props), false);
  });
}
test("actual TaskState preserves idle, pending, error and recovery presentation", () => {
  for (const task of [
    { busy: false, error: "", operationId: "" },
    { busy: true, error: "", operationId: "" },
    { busy: false, error: "Synthetic fixed refusal", operationId: "" },
    { busy: false, error: "Synthetic fixed refusal", operationId: "synthetic-operation" },
  ]) {
    const root = component.exports.TaskState({ task });
    const elements = walk(root);
    assert.equal(root.props["aria-live"], "polite");
    const statuses = elements.filter(element => element.props.role === "status");
    const alerts = elements.filter(element => element.props.role === "alert");
    assert.equal(statuses.length, task.busy ? 1 : 0);
    assert.equal(alerts.length, task.error ? 1 : 0);
    if (task.busy) assert.equal(text(statuses[0]), "Request in progress…");
    if (task.error) assert.equal(text(alerts[0]), task.error);
    assert.equal(text(root).includes("Recovery operation: synthetic-operation. Inspect it before another mutation."), Boolean(task.operationId));
  }
});
