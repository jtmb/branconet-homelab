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
  return { render, node, statuses, alerts, draft, submit, calls, task, mutation, pending,
    update: (next: Partial<Metadata>) => { path = { ...path, ...next }; }, editable: (value: boolean) => { editable = value; },
    succeed: async (data: Metadata = { ...original, revision: 8, retention: 5 }) => { resolve(data); await Promise.all(pending); },
    fail: async (message: string) => { reject(new Error(message)); await Promise.all(pending); }, refreshes: () => refreshes };
}
test("idle metadata form has no pending status and keeps initial draft", () => {
  const m = model(); assert.deepEqual(m.statuses(), []); assert.equal(m.node("input").props.value, "3"); assert.equal(m.node("button", "Save retention").props.disabled, true); m.task.dispose();
});
test("held metadata PATCH announces pending and retains exact captured request", async () => {
  const m = model(); try { m.draft("5"); m.submit();
    assert.equal(m.calls.length, 1); assert.equal(m.calls[0].url, "/api/kv/paths/registered-a"); assert.equal(m.calls[0].init.method, "PATCH");
    assert.deepEqual(JSON.parse(String(m.calls[0].init.body)), { revision: 7, retention: 5 });
    assert.equal((m.calls[0].init.headers as Record<string, string>)["Content-Type"], "application/json");
    assert.equal(m.node("input").props.disabled, true); assert.equal(m.node("button", "Save retention").props.disabled, true);
    assert.deepEqual(m.statuses(), ["Saving retention metadata…"]);
  } finally { await m.fail("Synthetic failure"); m.task.dispose(); }
});
for (const status of [401, 403, 409, 503]) test(`settled ${status} failure removes pending status and retains draft/exact error`, async () => {
  const m = model(); try { m.draft("5"); m.submit(); await m.fail(`Synthetic ${status}`);
    assert.deepEqual(m.statuses(), []); assert.deepEqual(m.alerts(), [`Synthetic ${status}`]);
    assert.equal(m.node("input").props.value, "5"); assert.equal(m.refreshes(), 0); assert.equal(m.calls.length, 1);
  } finally { m.task.dispose(); }
});
test("success removes pending status, uses returned metadata and refreshes once", async () => {
  const m = model(); try { m.draft("5"); m.submit(); await m.succeed();
    assert.deepEqual(m.statuses(), ["Retention metadata saved."]); assert.equal(m.node("input").props.value, "5"); assert.equal(m.refreshes(), 1);
    m.update({ revision: 8, retention: 5 }); assert.deepEqual(m.alerts(), []);
  } finally { m.task.dispose(); }
});
test("metadata conflict preserves draft and reload explicitly replaces snapshot", async () => {
  const m = model(); try { m.draft("5"); m.update({ revision: 9, retention: 6 });
    assert.equal(m.node("input").props.value, "5"); assert.equal(m.node("button", "Save retention").props.disabled, true);
    assert.match(m.alerts()[0], /Metadata revision changed/);
    (m.node("button", "Reload retention").props.onClick as () => void)();
    assert.equal(m.node("input").props.value, "6"); assert.deepEqual(m.alerts(), []);
    m.draft("8"); m.submit(); assert.deepEqual(JSON.parse(String(m.calls[0].init.body)), { revision: 9, retention: 8 });
  } finally { await m.fail("Synthetic failure"); m.task.dispose(); }
});
test("conflict during pending save retains both presentation and existing reload disable", async () => {
  const m = model(); try { m.draft("5"); m.submit(); m.update({ revision: 9, retention: 6 });
    assert.equal(m.node("button", "Reload retention").props.disabled, true); assert.match(m.alerts()[0], /Metadata revision changed/);
    assert.deepEqual(m.statuses(), ["Saving retention metadata…"]);
  } finally { await m.fail("Synthetic 409"); m.task.dispose(); }
});
test("fresh scoped-writer gate remains required for save and reload", () => {
  const m = model(); try { m.draft("5"); m.editable(false); m.submit(); assert.equal(m.calls.length, 0);
    m.update({ revision: 9 }); assert.equal(m.node("button", "Reload retention").props.disabled, true); assert.deepEqual(m.statuses(), []);
  } finally { m.task.dispose(); }
});
for (const value of ["", "0", "101", "3", "1.5", "-2"]) test(`invalid/unchanged retention ${JSON.stringify(value)} stays unsent`, () => {
  const m = model(); try { m.draft(value); m.submit(); assert.equal(m.calls.length, 0); assert.equal(m.node("button", "Save retention").props.disabled, true); assert.deepEqual(m.statuses(), []); } finally { m.task.dispose(); }
});
test("duplicate held submit preserves one request and one pending status", async () => {
  const m = model(); try { m.draft("5"); m.submit(); m.submit(); assert.equal(m.calls.length, 1); assert.deepEqual(m.statuses(), ["Saving retention metadata…"]); } finally { await m.fail("Synthetic failure"); m.task.dispose(); }
});
test("disposed actual mutation task cannot publish a late success or refresh", async () => {
  const m = model(); m.draft("5"); m.submit(); m.task.dispose(); await m.succeed(); assert.equal(m.refreshes(), 0); assert.equal(m.statuses().includes("Retention metadata saved."), false);
});
