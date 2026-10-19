import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import { MutationTask, type MutationState } from "../src/lib/mutation-task";

// Actual selected declarations and MutationTask, synthetic hook slots and held
// metadata transport only. No mounted effects, hook lifecycle, DOM or backend.
const filename = "src/app/(dashboard)/secrets/kv/kv-forms.tsx";
const parsed = ts.createSourceFile(filename, readFileSync(filename, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
type Mode = "create" | "edit" | "register";
type Element = { type: string; props: Record<string, unknown> };
const mount = { id: "explicit-mount-a", name: "synthetic", namespaces: ["scope-a", "scope-b"], revision: 7 };
const outputs = Object.fromEntries(["MountForm", "RegisterForm"].map(name => {
  const nodes = parsed.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text === name);
  assert.equal(nodes.length, 1);
  return [name, ts.transpileModule(nodes[0].getText(parsed) + `\nmodule.exports = ${name};`, {
    fileName: filename, compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
  }).outputText];
}));
function walk(value: unknown): Element[] {
  if (Array.isArray(value)) return value.flatMap(walk);
  return value && typeof value === "object" && "props" in value ? [value as Element, ...walk((value as Element).props.children)] : [];
}
function text(value: unknown): string {
  if (Array.isArray(value)) return value.map(text).join("");
  if (value && typeof value === "object" && "props" in value) return text((value as Element).props.children);
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}
function model(mode: Mode) {
  const slots: unknown[] = []; let index = 0, closed = 0;
  let state: MutationState = { busy: false, error: "" };
  let resolve!: (data: unknown) => void, reject!: (error: Error) => void;
  const calls: { url: string; init: RequestInit }[] = [], pending: Promise<void>[] = [], saved: unknown[][] = [];
  const task = new MutationTask({ changed: next => { state = next; }, request: <T,>(url: string, init: RequestInit) => {
    calls.push({ url, init }); return new Promise<unknown>((yes, no) => { resolve = yes; reject = no; }) as Promise<T>;
  } });
  const mutation = { get busy() { return state.busy; }, get error() { return state.error; }, clear: () => task.clear(),
    mutate: <T,>(url: string, init: RequestInit, success: (data: T) => void) => { const promise = task.run(url, init, success); pending.push(promise); return promise; } };
  const component = { exports: undefined as unknown as (props: Record<string, unknown>) => Element };
  const jsx = (type: string, props: Element["props"]): Element => ({ type, props });
  runInNewContext(outputs[mode === "register" ? "RegisterForm" : "MountForm"], {
    module: component, exports: {}, button: "button", input: "input", surface: "surface", ConfirmDialog: "ConfirmDialog", useMutation: () => mutation,
    useState: (initial: unknown) => { const slot = index++; if (!(slot in slots)) slots[slot] = initial;
      return [slots[slot], (value: unknown) => { slots[slot] = typeof value === "function" ? value(slots[slot]) : value; }]; },
    require: (name: string) => { assert.equal(name, "react/jsx-runtime"); return { jsx, jsxs: jsx }; },
  });
  const props = { original: mode === "edit" ? mount : undefined, mount, close: () => { closed++; }, saved: (...args: unknown[]) => { saved.push(args); } };
  function render() { index = 0; return walk(component.exports(props)); }
  function node(type: string, label?: string) { const found = render().find(value => value.type === type && (label === undefined || text(value) === label)); assert(found, `${type} ${label ?? ""} missing`); return found; }
  const inputNodes = () => render().filter(value => value.type === "input" || value.type === "select");
  const draft = () => inputNodes().map(value => value.props.value);
  const enter = (position: number, value: string) => { const item = inputNodes()[position]; assert(item); (item.props.onChange as (event: unknown) => void)({ target: { value } }); };
  const submit = () => { let prevented = false; (node("form").props.onSubmit as (event: unknown) => void)({ preventDefault: () => { prevented = true; } }); assert(prevented); };
  const statuses = () => render().filter(value => value.props.role === "status").map(text);
  const alerts = () => render().filter(value => value.props.role === "alert").map(text);
  const fill = () => {
    if (mode === "register") { for (const [i, value] of ["public/example", "scope-b", "explicit-native", "5", "logical", "exact-key"].entries()) enter(i, value); }
    else { enter(0, "changed-mount"); enter(1, "scope-b, scope-a"); }
  };
  return { render, node, inputNodes, draft, enter, submit, statuses, alerts, fill, calls, task, saved, closed: () => closed,
    present: (value: MutationState) => { state = value; },
    succeed: async () => { resolve({ id: "returned-metadata-only" }); await Promise.all(pending); },
    fail: async (message: string) => { reject(new Error(message)); await Promise.all(pending); } };
}
for (const mode of ["create", "edit", "register"] as const) {
  const statusText = mode === "register" ? "Registering path metadata…" : "Saving mount metadata…";
  test(`${mode}: idle form has no pending announcement and keeps its initial controls`, () => {
    const m = model(mode); try { assert.deepEqual(m.statuses(), []); assert.equal(m.calls.length, 0);
      assert.equal(m.node("button", mode === "register" ? "Register metadata" : "Save mount").props.disabled, true);
      assert.equal(m.inputNodes()[0].props.value, mode === "edit" ? mount.name : "");
    } finally { m.task.dispose(); }
  });
  test(`${mode}: held save announces pending with the exact captured metadata request`, async () => {
    const m = model(mode); try { m.fill(); const draft = m.draft(); m.submit();
      assert.equal(m.calls.length, 1); const call = m.calls[0];
      assert.equal(call.url, mode === "register" ? "/api/kv/paths" : "/api/kv/mounts" + (mode === "edit" ? "/" + mount.id : ""));
      assert.equal(call.init.method, mode === "edit" ? "PATCH" : "POST");
      assert.equal((call.init.headers as Record<string, string>)["Content-Type"], "application/json");
      assert.deepEqual(JSON.parse(String(call.init.body)), mode === "register"
        ? { mountId: mount.id, path: "public/example", namespace: "scope-b", name: "explicit-native", fields: [{ field: "logical", key: "exact-key" }], retention: 5 }
        : { name: "changed-mount", namespaces: ["scope-b", "scope-a"], ...(mode === "edit" ? { revision: 7 } : {}) });
      assert.deepEqual(m.draft(), draft); assert(m.inputNodes().every(item => item.props.disabled === true));
      assert(m.render().filter(item => item.type === "button").every(item => item.props.disabled === true));
      assert.deepEqual(m.statuses(), [statusText]);
    } finally { await m.fail("Synthetic failure"); m.task.dispose(); }
  });
  test(`${mode}: duplicate held submit keeps one request and one announcement`, async () => {
    const m = model(mode); try { m.fill(); m.submit(); m.submit(); assert.equal(m.calls.length, 1); assert.deepEqual(m.statuses(), [statusText]); }
    finally { await m.fail("Synthetic failure"); m.task.dispose(); }
  });
  for (const code of [401, 403, 409, 503]) test(`${mode}: settled ${code} preserves draft and exact error`, async () => {
    const m = model(mode); try { m.fill(); const draft = m.draft(); m.submit(); await m.fail(`Synthetic ${code}`);
      assert.deepEqual(m.statuses(), []); assert.deepEqual(m.alerts(), [`Synthetic ${code}`]); assert.deepEqual(m.draft(), draft);
      assert.equal(m.calls.length, 1); assert.equal(m.saved.length, 0); assert.equal(m.closed(), 0);
    } finally { m.task.dispose(); }
  });
  test(`${mode}: success removes pending and calls the existing saved callback once`, async () => {
    const m = model(mode); try { m.fill(); m.submit(); await m.succeed(); assert.deepEqual(m.statuses(), []); assert.deepEqual(m.alerts(), []);
      assert.equal(m.saved.length, 1); assert.equal(m.calls.length, 1);
      if (mode !== "register") assert.equal(m.saved[0][0], mode === "edit" ? "Mount metadata updated." : "Mount created.");
    } finally { m.task.dispose(); }
  });
  test(`${mode}: disposed task fences late success without invoking the parent`, async () => {
    const m = model(mode); m.fill(); m.submit(); m.task.dispose(); await m.succeed(); assert.equal(m.saved.length, 0); assert.equal(m.closed(), 0);
  });
}
test("mount delete-dialog presentation never uses the save-only pending announcement", () => {
  const m = model("edit"); try {
    (m.node("button", "Delete mount").props.onClick as () => void)();
    m.present({ busy: true, error: "Synthetic dialog error" });
    assert.deepEqual(m.statuses(), []); assert.deepEqual(m.alerts(), []);
    assert.equal(m.node("ConfirmDialog").props.loading, true); assert.equal(m.node("ConfirmDialog").props.error, "Synthetic dialog error");
    assert.equal(m.node("ConfirmDialog").props.confirmName, mount.name); assert.equal(m.calls.length, 0);
    // Do not invoke the destructive callback; only the existing dialog props.
  } finally { m.task.dispose(); }
});
for (const mode of ["create", "edit", "register"] as const) test(`${mode}: invalid metadata stays unsent without a pending announcement`, () => {
  const m = model(mode); try { m.fill(); m.enter(0, mode === "register" ? "../invalid" : "Invalid Mount"); m.submit(); assert.equal(m.calls.length, 0); assert.deepEqual(m.statuses(), []); }
  finally { m.task.dispose(); }
});
