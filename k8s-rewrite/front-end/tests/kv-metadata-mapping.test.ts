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
const limitId = "kv-register-mapping-limit";
const limitText = "Maximum of 64 field mappings reached. Remove a mapping to add another.";
function click(m: ReturnType<typeof model>, label: string) {
  const node = m.node("button", label); assert.equal(node.props.disabled, false);
  (node.props.onClick as () => void)();
}
function rows(m: ReturnType<typeof model>) { return (m.inputNodes().length - 4) / 2; }
function grow(m: ReturnType<typeof model>, count: number) { while (rows(m) < count) click(m, "Add field mapping"); }
function remove(m: ReturnType<typeof model>, position: number) {
  const node = m.render().find(value => value.type === "button" && value.props["aria-label"] === `Remove field mapping ${position}`);
  assert(node); assert.equal(node.props.disabled, false); (node.props.onClick as () => void)();
}
function checkLimit(m: ReturnType<typeof model>, present: boolean) {
  const nodes = m.render().filter(node => node.props.id === limitId);
  assert.equal(nodes.length, present ? 1 : 0);
  if (present) { assert.equal(nodes[0].type, "p"); assert.equal(nodes[0].props.role, "status"); assert.equal(text(nodes[0]), limitText); }
  assert.equal(m.node("fieldset").props["aria-describedby"], present ? limitId : undefined);
  assert.equal(m.node("button", "Add field mapping").props["aria-describedby"], present ? limitId : undefined);
}
for (const count of [1, 2, 63, 64]) test(`mapping count ${count}: exact limit state and numbered row labels`, () => {
  const m = model("register"); try {
    grow(m, count); assert.equal(rows(m), count); assert.equal(text(m.node("legend")), `Field mappings (${count}/64)`);
    checkLimit(m, count === 64); assert.equal(m.node("button", "Add field mapping").props.disabled, count === 64);
    const tree = m.render(), labels = tree.filter(node => node.type === "label");
    for (let i = 1; i <= count; i++) {
      for (const label of [`Field ${i}`, `Native key ${i}`]) { const found = labels.filter(node => text(node) === label); assert.equal(found.length, 1); assert.equal(walk(found[0]).filter(node => node.type === "input").length, 1); }
      const buttons = tree.filter(node => node.type === "button" && node.props["aria-label"] === `Remove field mapping ${i}`);
      assert.equal(buttons.length, 1); assert.equal(buttons[0].props.type, "button"); assert.equal(buttons[0].props.disabled, count === 1);
    }
    assert.equal(m.calls.length, 0); assert.equal(m.closed(), 0); assert.equal(m.saved.length, 0);
  } finally { m.task.dispose(); }
});
test("adding a mapping preserves preceding metadata and starts an empty explicit pair", () => {
  const m = model("register"); try { m.fill(); const draft = m.draft(); click(m, "Add field mapping"); assert.deepEqual(m.draft(), [...draft, "", ""]); assert.equal(m.calls.length, 0); } finally { m.task.dispose(); }
});
for (const position of [1, 2, 3]) test(`removing row ${position} preserves the remaining exact field/key pairs`, () => {
  const m = model("register"); try {
    m.fill(); grow(m, 3); const pairs = [["first", "key-a"], ["second", "key-b"], ["third", "key-c"]];
    pairs.forEach((pair, i) => pair.forEach((value, j) => m.enter(4 + 2 * i + j, value)));
    const before = m.draft().slice(0, 4); remove(m, position);
    assert.deepEqual(m.draft(), [...before, ...pairs.filter((_, i) => i !== position - 1).flat()]);
    assert.equal(text(m.node("legend")), "Field mappings (2/64)"); checkLimit(m, false); assert.equal(m.calls.length, 0);
  } finally { m.task.dispose(); }
});
test("removing from 64 then adding returns the limit guidance without discarding earlier rows", () => {
  const m = model("register"); try { m.fill(); grow(m, 64); checkLimit(m, true); remove(m, 64); checkLimit(m, false); const draft = m.draft(); click(m, "Add field mapping"); checkLimit(m, true); assert.deepEqual(m.draft(), [...draft, "", ""]); assert.equal(m.calls.length, 0); } finally { m.task.dispose(); }
});
for (const count of [1, 63, 64]) test(`busy ${count}-row form omits guidance and dangling references`, () => {
  const m = model("register"); try { grow(m, count); const draft = m.draft(); m.present({ busy: true, error: "" }); checkLimit(m, false); assert.deepEqual(m.statuses(), ["Registering path metadata…"]); assert(m.inputNodes().every(node => node.props.disabled === true)); assert(m.render().filter(node => node.type === "button").every(node => node.props.disabled === true)); assert.deepEqual(m.draft(), draft); assert.equal(m.calls.length, 0); } finally { m.task.dispose(); }
});
for (const retention of ["", "7"]) test(`64 explicit mappings keep exact registration payload with retention '${retention}'`, async () => {
  const m = model("register"); try {
    m.fill(); m.enter(3, retention); grow(m, 64); const fields = Array.from({ length: 64 }, (_, i) => ({ field: `field-${i}`, key: `key-${i}` }));
    fields.forEach((item, i) => { m.enter(4 + 2 * i, item.field); m.enter(5 + 2 * i, item.key); });
    checkLimit(m, true); assert.equal(m.node("button", "Register metadata").props.disabled, false);
    m.submit(); assert.equal(m.calls.length, 1); assert.equal(m.calls[0].url, "/api/kv/paths"); assert.equal(m.calls[0].init.method, "POST");
    assert.deepEqual(JSON.parse(m.calls[0].init.body as string), { mountId: mount.id, path: "public/example", namespace: "scope-b", name: "explicit-native", fields, ...(retention ? { retention: 7 } : {}) });
    checkLimit(m, false); m.submit(); assert.equal(m.calls.length, 1); await m.succeed(); assert.equal(m.saved.length, 1); assert.equal(m.closed(), 0);
  } finally { m.task.dispose(); }
});
for (const error of ["Synthetic conflict", "Synthetic service unavailable"]) test(`64-row ordinary failure preserves exact draft and error: ${error}`, async () => {
  const m = model("register"); try {
    m.fill(); grow(m, 64); for (let i = 0; i < 64; i++) { m.enter(4 + 2 * i, `field-${i}`); m.enter(5 + 2 * i, `key-${i}`); }
    const before = m.draft(); m.submit(); await m.fail(error); checkLimit(m, true); assert.deepEqual(m.alerts(), [error]); assert.deepEqual(m.draft(), before); assert.equal(m.calls.length, 1); assert.equal(m.saved.length, 0); assert.equal(m.closed(), 0);
    remove(m, 64); checkLimit(m, false); assert.deepEqual(m.alerts(), [error]); assert.deepEqual(m.draft(), before.slice(0, -2)); assert.equal(m.calls.length, 1);
  } finally { m.task.dispose(); }
});
for (const duplicate of ["field", "key"]) test(`duplicate ${duplicate} remains invalid at 64 rows while guidance stays separate`, () => {
  const m = model("register"); try {
    m.fill(); grow(m, 64); for (let i = 0; i < 64; i++) { m.enter(4 + 2 * i, `field-${i}`); m.enter(5 + 2 * i, `key-${i}`); }
    m.enter(duplicate === "field" ? 6 : 7, duplicate === "field" ? "field-0" : "key-0"); checkLimit(m, true); assert.equal(m.node("button", "Register metadata").props.disabled, true); m.submit(); assert.equal(m.calls.length, 0);
  } finally { m.task.dispose(); }
});
