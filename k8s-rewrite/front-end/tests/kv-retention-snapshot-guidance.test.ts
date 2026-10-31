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
const prefix = "This retention draft uses captured path metadata revision ";
const explanation = (revision: number) => `${prefix}${revision}. Refreshing metadata does not replace this draft. If the revision changes, use Reload retention to discard the draft and use the new revision; the server checks the submitted revision and current permissions.`;
function capturedHelp(m: ReturnType<typeof model>, revision: number) {
  const paragraphs = m.render().filter(n => n.type === "p" && text(n).startsWith(prefix));
  assert.equal(paragraphs.length, 1, "one captured-snapshot explanation");
  assert.equal(text(paragraphs[0]), explanation(revision));
  assert.equal(paragraphs[0].props.role, undefined, "ordinary guidance is not a live announcement");
}
test("initial explanation uses the captured revision without issuing a request", () => {
  const m = model(); try { capturedHelp(m, 7); assert.equal(m.node("input").props.value, "3"); assert.equal(m.calls.length, 0); assert.equal(m.refreshes(), 0); assert.deepEqual(m.statuses(), []); assert.deepEqual(m.alerts(), []); } finally { m.task.dispose(); }
});
for (const value of ["", "0", "01", "101", "1.5", "3", "5", "100"]) test("snapshot explanation survives draft changes: " + JSON.stringify(value), () => {
  const m = model(); try { const captured = m.snapshot(); m.draft(value); capturedHelp(m, 7); assert.equal(m.snapshot(), captured); assert.equal(m.node("input").props.value, value); assert.equal(m.calls.length, 0); } finally { m.task.dispose(); }
});
test("same-revision metadata refresh preserves exact captured object and draft", () => {
  const m = model(); try { const captured = m.snapshot(); m.draft("5"); m.update({ retention: 6 }); capturedHelp(m, 7); assert.equal(m.snapshot(), captured); assert.equal(m.node("input").props.value, "5"); assert.equal(m.node("button", "Save retention").props.disabled, false); assert.equal(m.calls.length, 0); } finally { m.task.dispose(); }
});
for (const value of ["", "3", "5"]) test("stale explanation retains captured revision until explicit reload: " + JSON.stringify(value), () => {
  const m = model(); try { const captured = m.snapshot(); m.draft(value); m.update({ revision: 9, retention: 6 }); capturedHelp(m, 7); assert.equal(m.snapshot(), captured); assert.equal(m.node("input").props.value, value); assert.equal(m.node("button", "Save retention").props.disabled, true); m.submit(); assert.equal(m.calls.length, 0); assert.match(m.alerts()[0], /Metadata revision changed/); (m.node("button", "Reload retention").props.onClick as () => void)(); capturedHelp(m, 9); assert.equal(m.snapshot(), m.currentPath()); assert.equal(m.node("input").props.value, "6"); assert.deepEqual(m.alerts(), []); assert.deepEqual(m.statuses(), []); assert.equal(m.refreshes(), 0); } finally { m.task.dispose(); }
});
for (const revision of [0, 1, 123456789]) test("explanation renders exact numeric captured revision: " + revision, () => {
  const m = model(); try { m.update({ revision }); capturedHelp(m, revision); assert.equal(m.calls.length, 0); } finally { m.task.dispose(); }
});
test("editable gate and stale reload restrictions do not replace captured guidance", () => {
  const m = model(); try { m.draft("5"); m.editable(false); capturedHelp(m, 7); m.submit(); assert.equal(m.calls.length, 0); m.update({ revision: 9 }); capturedHelp(m, 7); assert.equal(m.node("button", "Reload retention").props.disabled, true); m.editable(true); capturedHelp(m, 7); assert.equal(m.node("button", "Reload retention").props.disabled, false); } finally { m.task.dispose(); }
});
test("held metadata PATCH and later refresh keep the request's captured revision", async () => {
  const m = model(); try { m.draft("5"); m.submit(); capturedHelp(m, 7); assert.equal(m.calls.length, 1); assert.equal(m.calls[0].url, "/api/kv/paths/registered-a"); assert.equal(m.calls[0].init.method, "PATCH"); assert.deepEqual(JSON.parse(String(m.calls[0].init.body)), { revision: 7, retention: 5 }); m.update({ revision: 10, retention: 8 }); capturedHelp(m, 7); assert.equal(m.node("button", "Reload retention").props.disabled, true); assert.deepEqual(m.statuses(), ["Saving retention metadata…"]); await m.succeed({ ...original, revision: 8, retention: 5 }); capturedHelp(m, 8); assert.equal(m.calls.length, 1); assert.equal(m.refreshes(), 1); assert.deepEqual(m.statuses(), ["Retention metadata saved."]); assert.equal(m.node("input").props.value, "5"); assert.equal(m.node("button", "Save retention").props.disabled, true); } finally { if(m.mutation.busy) await m.fail("Synthetic failure"); m.task.dispose(); }
});
test("ordinary PATCH failure retains captured explanation, draft and error", async () => {
  const m = model(); try { m.draft("5"); m.submit(); capturedHelp(m, 7); await m.fail("Synthetic metadata conflict"); capturedHelp(m, 7); assert.equal(m.node("input").props.value, "5"); assert.deepEqual(m.alerts(), ["Synthetic metadata conflict"]); assert.deepEqual(m.statuses(), []); assert.equal(m.refreshes(), 0); assert.equal(m.calls.length, 1); } finally { if(m.mutation.busy) await m.fail("Synthetic failure"); m.task.dispose(); }
});
test("successful save changes explanation only to returned captured metadata", async () => {
  const m = model(); try { m.draft("5"); m.submit(); capturedHelp(m, 7); const returned = { ...original, revision: 12, retention: 5 }; await m.succeed(returned); capturedHelp(m, 12); assert.equal(m.snapshot(), returned); assert.deepEqual(m.statuses(), ["Retention metadata saved."]); m.draft("6"); capturedHelp(m, 12); assert.deepEqual(m.statuses(), []); assert.equal(m.calls.length, 1); } finally { if(m.mutation.busy) await m.fail("Synthetic failure"); m.task.dispose(); }
});
