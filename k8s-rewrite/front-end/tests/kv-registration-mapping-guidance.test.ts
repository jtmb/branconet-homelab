import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import { MutationTask, type MutationState } from "../src/lib/mutation-task";

// Actual selected declarations and MutationTask, synthetic hook slots and held
// metadata transport plus manually attached synthetic refs only. No mounted React, DOM or backend.
const filename = "src/app/(dashboard)/secrets/kv/kv-forms.tsx";
const parsed = ts.createSourceFile(filename, readFileSync(filename, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
type Mode = "create" | "edit" | "register";
type Element = { type: string; key?: unknown; props: Record<string, unknown> };
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
function model(mode: Mode, originalMount = mount) {
  const slots: unknown[] = []; const focused: number[] = []; let index = 0, closed = 0;
  let state: MutationState = { busy: false, error: "" };
  let resolve!: (data: unknown) => void, reject!: (error: Error) => void;
  const calls: { url: string; init: RequestInit }[] = [], pending: Promise<void>[] = [], saved: unknown[][] = [];
  const task = new MutationTask({ changed: next => { state = next; }, request: <T,>(url: string, init: RequestInit) => {
    calls.push({ url, init }); return new Promise<unknown>((yes, no) => { resolve = yes; reject = no; }) as Promise<T>;
  } });
  const mutation = { get busy() { return state.busy; }, get error() { return state.error; }, clear: () => task.clear(),
    mutate: <T,>(url: string, init: RequestInit, success: (data: T) => void) => { const promise = task.run(url, init, success); pending.push(promise); return promise; } };
  const component = { exports: undefined as unknown as (props: Record<string, unknown>) => Element };
  const jsx = (type: string, props: Element["props"], key?: unknown): Element => ({ type, props, key });
  runInNewContext(outputs[mode === "register" ? "RegisterForm" : "MountForm"], {
    module: component, exports: {}, button: "button", input: "input", surface: "surface", ConfirmDialog: "ConfirmDialog", useMutation: () => mutation,
    useState: (initial: unknown) => { const slot = index++; if (!(slot in slots)) slots[slot] = initial;
      return [slots[slot], (value: unknown) => { slots[slot] = typeof value === "function" ? value(slots[slot]) : value; }]; },
    require: (name: string) => { assert.equal(name, "react/jsx-runtime"); return { jsx, jsxs: jsx }; },
  });
  const props = { original: mode === "edit" ? originalMount : undefined, mount: { ...mount, namespaces: [...mount.namespaces] }, close: () => { closed++; }, saved: (...args: unknown[]) => { saved.push(args); } };
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
  return { scopes: (namespaces: string[]) => { props.mount = { ...props.mount, namespaces, revision: props.mount.revision + 1 }; }, focused, attachRefs: (detach = false) => { const nodes = inputNodes(); for (let i = 4; i < nodes.length; i += 2) { const ref = nodes[i].props.ref; if (typeof ref === "function") ref(detach ? null : { focus: () => focused.push((i - 4) / 2 + 1) }); } }, render, node, inputNodes, draft, enter, submit, statuses, alerts, fill, calls, task, saved, closed: () => closed,
    present: (value: MutationState) => { state = value; },
    succeed: async () => { resolve({ id: "returned-metadata-only" }); await Promise.all(pending); },
    fail: async (message: string) => { reject(new Error(message)); await Promise.all(pending); } };
}



const explanation = "Use 1–253 letters, digits, dots, underscores or hyphens for each field and native key. Field names must be unique, and native keys must be unique within this registration.";
function guidance(m: ReturnType<typeof model>, expected: boolean) {
  const found = m.render().filter(n => n.props.id === "kv-register-mapping-guidance");
  assert.equal(found.length, expected ? 1 : 0, "mapping guidance visibility");
  for (const input of m.inputNodes().slice(4)) assert.equal(input.props["aria-describedby"], expected ? "kv-register-mapping-guidance" : undefined, "mapping input association");
  if (expected) { assert.equal(found[0].type, "p"); assert.equal(found[0].props.role, undefined); assert.equal(text(found[0]), explanation); }
}
function add(m: ReturnType<typeof model>) {
  const button = m.node("button", "Add field mapping"); assert.equal(button.props.disabled, false); (button.props.onClick as () => void)();
}
const invalid = ["", " ", "a b", "a/b", "a\\b", "a:b", "%", "é", "字段", "a\t", "a\n", "\0", "a".repeat(254)];
for (const position of [4, 5]) for (const value of invalid) test(`invalid mapping input ${position}: ${JSON.stringify(value).slice(0,60)}`, () => {
  const m = model("register"); try {
    m.fill(); m.enter(position, value); guidance(m, true);
    assert.equal(m.node("button", "Register metadata").props.disabled, true); m.submit(); assert.equal(m.calls.length, 0);
    assert.equal(m.node("form").props["aria-describedby"], "kv-register-save-guidance");
    assert.equal(m.inputNodes()[position].props.value, value);
  } finally { m.task.dispose(); }
});
for (const value of ["a", "A0", ".", "_", "-", "a._-9", "a".repeat(253)]) test(`valid mapping preserves exact pairs: ${value.slice(0,35)}`, async () => {
  const m = model("register"); try {
    m.fill(); m.enter(4, value); m.enter(5, value); guidance(m, false);
    assert.equal(m.node("button", "Register metadata").props.disabled, false); m.submit();
    assert.equal(m.calls.length, 1); assert.equal(m.calls[0].url, "/api/kv/paths"); assert.equal(m.calls[0].init.method, "POST");
    assert.deepEqual(JSON.parse(String(m.calls[0].init.body)), { mountId: mount.id, path: "public/example", namespace: "scope-b", name: "explicit-native", fields: [{ field: value, key: value }], retention: 5 });
    guidance(m, false); await m.succeed(); assert.equal(m.saved.length, 1);
  } finally { m.task.dispose(); }
});
for (const position of [6, 7]) test(`duplicate ${position === 6 ? "field" : "native key"} explains separate uniqueness without editing drafts`, () => {
  const m = model("register"); try {
    m.fill(); add(m); m.enter(6, "second"); m.enter(7, "second-key");
    m.enter(position, position === 6 ? "logical" : "exact-key"); guidance(m, true); m.submit(); assert.equal(m.calls.length, 0);
    const before = m.draft(); assert.equal(m.node("button", "Register metadata").props.disabled, true); assert.deepEqual(m.draft(), before);
    m.enter(position, position === 6 ? "LOGICAL" : "EXACT-KEY"); guidance(m, false); assert.equal(m.node("button", "Register metadata").props.disabled, false);
    assert.equal(m.focused.length, 0); m.attachRefs(); assert.deepEqual(m.focused, [2]); m.attachRefs(); assert.deepEqual(m.focused, [2]);
  } finally { m.task.dispose(); }
});
test("invalid guidance hides while busy, then restores beside ordinary errors with exact drafts", () => {
  const m = model("register"); try {
    m.fill(); m.enter(4, "bad field"); const draft = m.draft(); guidance(m, true);
    m.present({ busy: true, error: "" }); guidance(m, false); assert(m.inputNodes().every(n => n.props.disabled === true));
    m.present({ busy: false, error: "ordinary metadata conflict" }); guidance(m, true); assert.deepEqual(m.alerts(), ["ordinary metadata conflict"]); assert.deepEqual(m.draft(), draft); assert.equal(m.calls.length, 0);
    m.enter(4, "fixed"); guidance(m, false); assert.equal(m.node("button", "Register metadata").props.disabled, false);
  } finally { m.task.dispose(); }
});
test("captured pending metadata request stays exact through changed drafts and ordinary rejection", async () => {
  const m = model("register"); try {
    m.fill(); m.enter(3, ""); m.submit(); const captured = String(m.calls[0].init.body);
    m.enter(4, "bad field"); guidance(m, false); assert.equal(String(m.calls[0].init.body), captured);
    assert.deepEqual(JSON.parse(captured), { mountId: mount.id, path: "public/example", namespace: "scope-b", name: "explicit-native", fields: [{ field: "logical", key: "exact-key" }] });
    await m.fail("ordinary metadata outage"); guidance(m, true); assert.deepEqual(m.alerts(), ["ordinary metadata outage"]); assert.equal(m.inputNodes()[4].props.value, "bad field"); assert.equal(m.calls.length, 1); assert.equal(m.saved.length, 0); assert.equal(m.closed(), 0);
  } finally { m.task.dispose(); }
});
test("64-row guidance coexists with original limit and surviving stable identities", () => {
  const m = model("register"); try {
    m.fill(); while ((m.inputNodes().length - 4) / 2 < 64) add(m);
    guidance(m, true); assert.equal(m.node("fieldset").props["aria-describedby"], "kv-register-mapping-limit");
    assert.equal(m.node("button", "Add field mapping").props["aria-describedby"], "kv-register-mapping-limit");
    for (let row = 1; row < 64; row++) { m.enter(4 + row * 2, `field-${row}`); m.enter(5 + row * 2, `key-${row}`); }
    guidance(m, false); const before = m.render().filter(n => n.type === "div" && n.key !== undefined).map(n => n.key);
    const remove = m.render().find(n => n.type === "button" && n.props["aria-label"] === "Remove field mapping 32"); assert(remove); (remove.props.onClick as () => void)();
    assert.deepEqual(m.render().filter(n => n.type === "div" && n.key !== undefined).map(n => n.key), before.filter((_, i) => i !== 31));
    guidance(m, false); assert.equal(m.node("fieldset").props["aria-describedby"], undefined); assert.equal(m.calls.length, 0);
    m.attachRefs(); assert.deepEqual(m.focused, [32]); m.attachRefs(); assert.deepEqual(m.focused, [32]);
  } finally { m.task.dispose(); }
});
test("unrelated invalid path, name, retention and namespace keep mapping guidance absent", () => {
  const m = model("register"); try {
    m.fill(); m.enter(0, ""); m.enter(1, "outside"); m.enter(2, "INVALID"); m.enter(3, "0"); guidance(m, false);
    assert.equal(m.node("button", "Register metadata").props.disabled, true); m.submit(); assert.equal(m.calls.length, 0);
  } finally { m.task.dispose(); }
});
