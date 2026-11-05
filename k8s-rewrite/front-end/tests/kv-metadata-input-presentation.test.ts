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
const mountGuidance = "Enter a lowercase mount name starting with a letter (1–63 letters, digits or hyphens) and 1–128 unique namespaces. Namespace names use lowercase letters, digits or hyphens, start and end with a letter or digit, and contain at most 63 characters.";
const unchangedGuidance = "Change the mount name or namespace scopes to enable Save mount.";
const registerGuidance = "Complete a valid logical path, namespace, Secret name and unique field/native-key mappings. Optional retention must be a whole number from 1 to 100; leave it blank to use the operator default.";
function description(m: ReturnType<typeof model>, mode: Mode) {
  const id = mode === "register" ? "kv-register-save-guidance" : "kv-mount-save-guidance";
  const matches = m.render().filter(node => node.props.id === id);
  assert.equal(matches.length, 1, "exactly one save guidance paragraph");
  assert.equal(matches[0].type, "p");
  assert.equal(m.node("form").props["aria-describedby"], id);
  assert.equal(m.node("button", mode === "register" ? "Register metadata" : "Save mount").props["aria-describedby"], id);
  return text(matches[0]);
}
function noDescription(m: ReturnType<typeof model>, mode: Mode) {
  assert.equal(m.render().filter(node => node.props.id === "kv-register-save-guidance" || node.props.id === "kv-mount-save-guidance").length, 0);
  assert.equal(m.node("form").props["aria-describedby"], undefined);
  assert.equal(m.node("button", mode === "register" ? "Register metadata" : "Save mount").props["aria-describedby"], undefined);
}
for (const mode of ["create", "edit", "register"] as const) {
  test(mode + ": each visible input keeps exactly one wrapping label and its text", () => {
    const m = model(mode);
    try {
      const tree = m.render();
      const controls = tree.filter(node => node.type === "input" || node.type === "select");
      const labels = tree.filter(node => node.type === "label");
      assert.equal(labels.length, controls.length);
      for (const control of controls) {
        const parents = labels.filter(label => walk(label.props.children).includes(control));
        assert.equal(parents.length, 1); assert(text(parents[0]).trim().length > 0);
      }
      assert.equal(m.calls.length, 0);
    } finally { m.task.dispose(); }
  });
  test(mode + ": initial save-disabled explanation links the form and button", () => {
    const m = model(mode);
    try {
      assert.equal(description(m, mode), mode === "edit" ? unchangedGuidance : mode === "register" ? registerGuidance : mountGuidance);
      assert.equal(m.node("button", mode === "register" ? "Register metadata" : "Save mount").props.disabled, true);
      assert.deepEqual(m.alerts(), []); assert.deepEqual(m.statuses(), []); assert.equal(m.calls.length, 0);
    } finally { m.task.dispose(); }
  });
  test(mode + ": valid changed metadata removes guidance and enables the same save", () => {
    const m = model(mode);
    try { m.fill(); noDescription(m, mode); assert.equal(m.node("button", mode === "register" ? "Register metadata" : "Save mount").props.disabled, false); assert.equal(m.calls.length, 0); }
    finally { m.task.dispose(); }
  });
  test(mode + ": busy state removes guidance and dangling description references", () => {
    const m = model(mode);
    try { m.present({ busy: true, error: "" }); noDescription(m, mode); assert.equal(m.node("button", mode === "register" ? "Register metadata" : "Save mount").props.disabled, true); assert.equal(m.calls.length, 0); }
    finally { m.task.dispose(); }
  });
  test(mode + ": ordinary failure remains exact after a draft becomes invalid", async () => {
    const m = model(mode);
    try {
      m.fill(); m.submit(); await m.fail("Synthetic metadata conflict");
      m.enter(0, mode === "register" ? "../invalid" : "Invalid Mount");
      const draft = m.draft(); m.submit();
      assert.equal(description(m, mode), mode === "register" ? registerGuidance : mountGuidance);
      assert.deepEqual(m.alerts(), ["Synthetic metadata conflict"]); assert.deepEqual(m.draft(), draft);
      assert.equal(m.calls.length, 1); assert.equal(m.saved.length, 0); assert.equal(m.closed(), 0);
    } finally { m.task.dispose(); }
  });
}
for (const [label, position, value] of [
  ["uppercase name", 0, "Invalid"], ["overlong name", 0, "a".repeat(64)],
  ["empty namespaces", 1, ""], ["duplicate namespaces", 1, "scope-a, scope-a"],
  ["invalid namespace", 1, "-bad"], ["uppercase namespace", 1, "Scope"],
  ["overlong namespace", 1, "a".repeat(64)],
  ["too many namespaces", 1, Array.from({ length: 129 }, (_, i) => "ns-" + i).join(",")],
] as const) test("mount: " + label + " explains disabled save without altering draft or sending", () => {
  const m = model("create"); try {
    m.fill(); m.enter(position, value); const before = m.draft();
    assert.equal(description(m, "create"), mountGuidance); m.submit();
    assert.deepEqual(m.draft(), before); assert.equal(m.calls.length, 0);
    assert.equal(m.node("button", "Save mount").props.disabled, true);
  } finally { m.task.dispose(); }
});
for (const [label, position, value] of [
  ["dot path", 0, "../invalid"], ["empty segment", 0, "public//example"],
  ["encoded path", 0, "public/%2f"], ["non-normalized path", 0, "public/é"],
  ["missing namespace", 1, ""], ["invalid Secret name", 2, "Invalid_Name"],
  ["zero retention", 3, "0"], ["leading-zero retention", 3, "01"],
  ["fractional retention", 3, "1.5"], ["excess retention", 3, "101"],
  ["invalid field", 4, "bad field"], ["invalid native key", 5, "bad/key"],
] as const) test("registration: " + label + " explains disabled save without altering draft or sending", () => {
  const m = model("register"); try {
    m.fill(); m.enter(position, value); const before = m.draft();
    assert.equal(description(m, "register"), registerGuidance); m.submit();
    assert.deepEqual(m.draft(), before); assert.equal(m.calls.length, 0);
    assert.equal(m.node("button", "Register metadata").props.disabled, true);
  } finally { m.task.dispose(); }
});
for (const [field, key] of [["logical", "other-key"], ["other-field", "exact-key"]]) test("registration: duplicate mapping " + field + "/" + key + " retains explicit rows", () => {
  const m = model("register"); try {
    m.fill(); (m.node("button", "Add field mapping").props.onClick as () => void)();
    m.enter(6, field); m.enter(7, key); const before = m.draft();
    assert.equal(description(m, "register"), registerGuidance); m.submit();
    assert.deepEqual(m.draft(), before); assert.equal(m.calls.length, 0);
  } finally { m.task.dispose(); }
});
for (const value of ["", "1", "100"]) test("registration: valid retention " + (value || "default") + " preserves exact payload semantics", async () => {
  const m = model("register"); try {
    m.fill(); m.enter(3, value); noDescription(m, "register"); m.submit();
    const body = JSON.parse(String(m.calls[0].init.body));
    assert.deepEqual(body, { mountId: mount.id, path: "public/example", namespace: "scope-b", name: "explicit-native",
      fields: [{ field: "logical", key: "exact-key" }], ...(value ? { retention: Number(value) } : {}) });
    await m.succeed(); assert.equal(m.saved.length, 1);
  } finally { m.task.dispose(); }
});
test("edit: reverting the draft restores unchanged guidance without upgrading the revision", () => {
  const m = model("edit"); try {
    m.fill(); noDescription(m, "edit");
    m.enter(0, mount.name); m.enter(1, mount.namespaces.join(", "));
    assert.equal(description(m, "edit"), unchangedGuidance); m.submit(); assert.equal(m.calls.length, 0);
  } finally { m.task.dispose(); }
});
test("mount: valid namespace/name boundaries keep Save enabled", () => {
  const m = model("create"); try {
    m.enter(0, "a".repeat(63)); m.enter(1, Array.from({ length: 128 }, (_, i) => i === 0 ? "a".repeat(63) : "ns-" + i).join(","));
    noDescription(m, "create"); assert.equal(m.node("button", "Save mount").props.disabled, false); assert.equal(m.calls.length, 0);
  } finally { m.task.dispose(); }
});