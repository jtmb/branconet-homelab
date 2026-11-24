import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import { MutationTask, type MutationState } from "../src/lib/mutation-task";

// Actual standalone RetentionForm declaration and MutationTask with synthetic
// hook slots, metadata and held transport. No React effects/DOM/backend/native.
const filename = "src/app/(dashboard)/secrets/kv/kv-forms.tsx";
const parsed = ts.createSourceFile(filename, readFileSync(filename, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const selected = parsed.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === "RetentionForm");
assert.equal(selected.length, 1);
const output = ts.transpileModule(selected[0].getText(parsed) + "\nmodule.exports = RetentionForm;", {
  fileName: filename, compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;
type Element = { type: string; props: Record<string, unknown> };
type Metadata = { id: string; mountId: string; revision: number; retention: number; path: string; namespace: string; name: string; fields: { field: string; key: string }[] };
const original: Metadata = { id: "registered-a", mountId: "mount-a", revision: 7, retention: 3, path: "public/example", namespace: "synthetic", name: "metadata-only", fields: [{ field: "logical", key: "exact-key" }] };
function walk(value: unknown): Element[] {
  if (Array.isArray(value)) return value.flatMap(walk);
  return value && typeof value === "object" && "props" in value ? [value as Element, ...walk((value as Element).props.children)] : [];
}
function text(value: unknown): string {
  if (Array.isArray(value)) return value.map(text).join("");
  if (value && typeof value === "object" && "props" in value) return text((value as Element).props.children);
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}
function model() {
  const slots: unknown[] = []; let index = 0, path = { ...original }, editable = true, refreshes = 0;
  let state: MutationState = { busy: false, error: "" };
  let resolve!: (data: Metadata) => void, reject!: (error: Error) => void;
  const calls: { url: string; init: RequestInit }[] = [], pending: Promise<void>[] = [];
  const task = new MutationTask({ changed: next => { state = next; }, request: <T,>(url: string, init: RequestInit) => {
    calls.push({ url, init }); return new Promise<Metadata>((yes, no) => { resolve = yes; reject = no; }) as Promise<T>;
  } });
  const mutation = { get busy() { return state.busy; }, get error() { return state.error; }, clear: () => task.clear(),
    mutate: <T,>(url: string, init: RequestInit, success: (data: T) => void) => { const promise = task.run(url, init, success); pending.push(promise); return promise; } };
  const component = { exports: undefined as unknown as (props: { path: Metadata; editable: boolean }) => Element };
  const jsx = (type: string, props: Element["props"]): Element => ({ type, props });
  runInNewContext(output, { module: component, exports: {}, button: "button", input: "input", useMutation: () => mutation,
    refetchKvMetadata: () => { refreshes++; }, useState: (initial: unknown) => {
      const slot = index++; if (!(slot in slots)) slots[slot] = initial;
      return [slots[slot], (value: unknown) => { slots[slot] = value; }];
    }, require: (name: string) => { assert.equal(name, "react/jsx-runtime"); return { jsx, jsxs: jsx }; } });
  function render() { index = 0; return walk(component.exports({ path, editable })); }
  function node(type: string, label?: string) { const found = render().find(value => value.type === type && (label === undefined || text(value) === label)); assert(found, `${type} ${label ?? ""} missing`); return found; }
  const statuses = () => render().filter(value => value.props.role === "status").map(text);
  const alerts = () => render().filter(value => value.props.role === "alert").map(text);
  const draft = (value: string) => (node("input").props.onChange as (event: unknown) => void)({ target: { value } });
  const submit = () => { let prevented = false; (node("form").props.onSubmit as (event: unknown) => void)({ preventDefault: () => { prevented = true; } }); assert(prevented); };
  return { render, node, statuses, alerts, draft, submit, calls, task, mutation, pending, present: (next: MutationState) => { state = next; }, snapshot: () => { render(); return slots[0]; }, currentPath: () => path,
    update: (next: Partial<Metadata>) => { path = { ...path, ...next }; }, editable: (value: boolean) => { editable = value; },
    succeed: async (data: Metadata = { ...original, revision: 8, retention: 5 }) => { resolve(data); await Promise.all(pending); },
    fail: async (message: string) => { reject(new Error(message)); await Promise.all(pending); }, refreshes: () => refreshes };
}
// These selected-declaration checks do not mount React, execute useMutation
// lifecycle or establish DOM, browser, HTTP, backend, native or actual AT evidence.
const invalidHelp = "Retention must be a whole number from 1 to 100. The server enforces the operator-configured maximum.";
const unchangedHelp = "Change retention to enable Save retention.";
const helpId = "kv-retention-save-guidance";
function guidance(m: ReturnType<typeof model>, expected?: string) {
  const found = m.render().filter(n => n.props.id === helpId);
  assert.equal(found.length, expected === undefined ? 0 : 1, "guidance visibility");
  for (const n of [m.node("input"), m.node("button", "Save retention")]) assert.equal(n.props["aria-describedby"], expected === undefined ? undefined : helpId, "field/save association");
  if (expected !== undefined) { assert.equal(found[0].type, "p"); assert.equal(found[0].props.role, undefined); assert.equal(text(found[0]), expected); }
}
const invalid = ["", "0", "00", "01", "-1", "+1", "101", "999", "1.0", "1.5", "1e1", "0x10", " 5", "5 ", " ", "\t", "5\n", "NaN", "Infinity", "five", "١", "５", "1/2", "1_0", "9".repeat(309)];
for (const value of invalid) test("invalid retention has linked field/save help and stays unsent: " + JSON.stringify(value).slice(0,60), () => {
  const m = model(); try { m.draft(value); guidance(m, invalidHelp); assert.equal(m.node("input").props.value, value); assert.equal(m.node("button", "Save retention").props.disabled, true); m.submit(); assert.equal(m.calls.length, 0); assert.deepEqual(m.alerts(), []); assert.deepEqual(m.statuses(), []); } finally { m.task.dispose(); }
});
for (const value of ["1", "2", "4", "5", "10", "99", "100"]) test("valid changed retention clears help and captures exact metadata PATCH: " + value, async () => {
  const m = model(); try { m.draft(value); guidance(m); assert.equal(m.node("button", "Save retention").props.disabled, false); m.submit(); assert.equal(m.calls.length, 1); assert.equal(m.calls[0].url, "/api/kv/paths/registered-a"); assert.equal(m.calls[0].init.method, "PATCH"); assert.deepEqual(JSON.parse(String(m.calls[0].init.body)), { revision: 7, retention: Number(value) }); assert.deepEqual(m.statuses(), ["Saving retention metadata…"]); guidance(m); } finally { await m.fail("Synthetic failure"); m.task.dispose(); }
});
test("initial unchanged retention has linked help without mutation", () => {
  const m = model(); try { guidance(m, unchangedHelp); assert.equal(m.node("input").props.value, "3"); assert.equal(m.node("button", "Save retention").props.disabled, true); m.submit(); assert.equal(m.calls.length, 0); } finally { m.task.dispose(); }
});
test("help follows invalid, unchanged and valid drafts without side effects", () => {
  const m = model(); try { for (const [value, help] of [["", invalidHelp], ["5", undefined], ["3", unchangedHelp], ["101", invalidHelp], ["100", undefined]] as const) { m.draft(value); guidance(m, help); assert.equal(m.node("input").props.value, value); } assert.equal(m.calls.length, 0); assert.equal(m.refreshes(), 0); } finally { m.task.dispose(); }
});
for (const value of ["", "3", "5"]) test("noneditable gate suppresses help and requests: " + JSON.stringify(value), () => {
  const m = model(); try { m.draft(value); m.editable(false); guidance(m); m.submit(); assert.equal(m.calls.length, 0); assert.equal(m.node("button", "Save retention").props.disabled, true); m.editable(true); guidance(m, value === "" ? invalidHelp : value === "3" ? unchangedHelp : undefined); } finally { m.task.dispose(); }
});
for (const value of ["", "3", "5"]) test("stale path suppresses save help and preserves draft until explicit reload: " + JSON.stringify(value), () => {
  const m = model(); try { const captured = m.snapshot(); m.draft(value); m.update({ revision: 9, retention: 6 }); guidance(m); assert.equal(m.snapshot(), captured); assert.equal(m.node("input").props.value, value); assert.match(m.alerts()[0], /Metadata revision changed/); m.submit(); assert.equal(m.calls.length, 0); (m.node("button", "Reload retention").props.onClick as () => void)(); assert.equal(m.snapshot(), m.currentPath()); assert.equal(m.node("input").props.value, "6"); guidance(m, unchangedHelp); assert.deepEqual(m.alerts(), []); } finally { m.task.dispose(); }
});
for (const value of ["", "3", "5"]) test("busy presentation removes field/save references: " + JSON.stringify(value), () => {
  const m = model(); try { m.draft(value); m.present({ busy: true, error: "" }); guidance(m); assert.equal(m.node("input").props.value, value); assert.equal(m.node("input").props.disabled, true); assert.equal(m.node("button", "Save retention").props.disabled, true); assert.deepEqual(m.statuses(), ["Saving retention metadata…"]); assert.equal(m.calls.length, 0); } finally { m.task.dispose(); }
});
for (const status of [400, 409, 503]) test("ordinary failure preserves exact error, draft, snapshot and request with subsequent field help: " + status, async () => {
  const m = model(); try { const captured = m.snapshot(); m.draft("5"); m.submit(); const payload = String(m.calls[0].init.body); await m.fail("Synthetic metadata refusal " + status); guidance(m); assert.equal(m.snapshot(), captured); assert.equal(m.node("input").props.value, "5"); assert.deepEqual(m.alerts(), ["Synthetic metadata refusal " + status]); m.draft("101"); guidance(m, invalidHelp); m.submit(); assert.equal(m.calls.length, 1); assert.equal(String(m.calls[0].init.body), payload); assert.equal(m.refreshes(), 0); } finally { m.task.dispose(); }
});
test("same-revision replacement metadata preserves captured object and unchanged comparison", () => {
  const m = model(); try { const captured = m.snapshot(); m.update({ retention: 6 }); assert.equal(m.snapshot(), captured); guidance(m, unchangedHelp); m.draft("6"); guidance(m); assert.equal(m.node("button", "Save retention").props.disabled, false); assert.equal(m.calls.length, 0); } finally { m.task.dispose(); }
});
test("success and returned metadata use unchanged guidance while preserving saved status", async () => {
  const m = model(); try { m.draft("5"); m.submit(); guidance(m); await m.succeed(); guidance(m); assert.match(m.alerts()[0], /Metadata revision changed/); assert.deepEqual(m.statuses(), ["Retention metadata saved."]); m.update({ revision: 8, retention: 5 }); guidance(m, unchangedHelp); assert.equal(m.refreshes(), 1); assert.deepEqual(m.statuses(), ["Retention metadata saved."]); m.draft("5"); guidance(m, unchangedHelp); assert.deepEqual(m.statuses(), []); m.draft("6"); guidance(m); assert.equal(m.calls.length, 1); } finally { m.task.dispose(); }
});
test("reload is still disabled for busy and noneditable stale metadata", () => {
  const m = model(); try { m.draft(""); m.update({ revision: 9 }); m.editable(false); guidance(m); assert.equal(m.node("button", "Reload retention").props.disabled, true); m.editable(true); m.present({ busy: true, error: "" }); guidance(m); assert.equal(m.node("button", "Reload retention").props.disabled, true); assert.equal(m.node("input").props.value, ""); assert.equal(m.calls.length, 0); } finally { m.task.dispose(); }
});
