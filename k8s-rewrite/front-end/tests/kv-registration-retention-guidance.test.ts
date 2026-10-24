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


const explanation = "Optional retention must be a whole number from 1 to 100; leave it blank to use the operator default. The server enforces the operator-configured maximum.";
function retentionGuidance(m: ReturnType<typeof model>, expected: boolean) {
  const found = m.render().filter(n => n.props.id === "kv-register-retention-guidance");
  assert.equal(found.length, expected ? 1 : 0, "retention guidance visibility");
  assert.equal(m.inputNodes()[3].props["aria-describedby"], expected ? "kv-register-retention-guidance" : undefined, "retention input association");
  if (expected) { assert.equal(found[0].type, "p"); assert.equal(found[0].props.role, undefined); assert.equal(text(found[0]), explanation); }
}
const invalidRetention = ["0", "00", "01", "-1", "+1", "101", "999", "1.0", "1.5", "1e1", "0x10", " 5", "5 ", " ", "\t", "5\n", "NaN", "Infinity", "five", "١", "５", "1/2", "1_0", "9".repeat(309)];
for (const retention of invalidRetention) test("invalid optional retention has linked guidance and no request: " + JSON.stringify(retention).slice(0,60), () => {
  const m = model("register"); try {
    m.fill(); m.enter(3, retention); retentionGuidance(m, true);
    assert.equal(m.node("button", "Register metadata").props.disabled, true);
    assert.equal(m.node("form").props["aria-describedby"], "kv-register-save-guidance");
    assert.equal(m.node("button", "Register metadata").props["aria-describedby"], "kv-register-save-guidance");
    m.submit(); assert.equal(m.calls.length, 0); assert.deepEqual(m.draft(), ["public/example", "scope-b", "explicit-native", retention, "logical", "exact-key"]);
  } finally { m.task.dispose(); }
});
for (const retention of ["", "1", "2", "5", "10", "99", "100"]) test("valid optional retention preserves exact metadata payload: " + JSON.stringify(retention), async () => {
  const m = model("register"); try {
    m.fill(); m.enter(3, retention); retentionGuidance(m, false);
    assert.equal(m.node("button", "Register metadata").props.disabled, false);
    assert.equal(m.node("form").props["aria-describedby"], undefined);
    m.submit(); assert.equal(m.calls.length, 1); assert.equal(m.calls[0].url, "/api/kv/paths"); assert.equal(m.calls[0].init.method, "POST");
    assert.deepEqual(JSON.parse(String(m.calls[0].init.body)), { mountId: mount.id, path: "public/example", namespace: "scope-b", name: "explicit-native", fields: [{ field: "logical", key: "exact-key" }], ...(retention ? { retention: Number(retention) } : {}) });
    await m.succeed(); assert.equal(m.saved.length, 1); assert.equal(m.closed(), 0);
  } finally { m.task.dispose(); }
});
test("optional retention guidance follows only retention while other inputs remain invalid", () => {
  const m = model("register"); try {
    retentionGuidance(m, false); assert.equal(m.node("button", "Register metadata").props.disabled, true);
    m.enter(3, "0"); retentionGuidance(m, true); m.enter(3, "100"); retentionGuidance(m, false);
    assert.equal(m.node("button", "Register metadata").props.disabled, true); assert.equal(m.node("form").props["aria-describedby"], "kv-register-save-guidance");
    m.enter(3, "01"); retentionGuidance(m, true); m.enter(3, ""); retentionGuidance(m, false); assert.equal(m.calls.length, 0);
  } finally { m.task.dispose(); }
});
test("busy invalid retention hides paragraph and reference then idle restores exact drafts", () => {
  const m = model("register"); try {
    m.fill(); m.enter(3, "101"); const draft = m.draft(); retentionGuidance(m, true);
    m.present({ busy: true, error: "" }); retentionGuidance(m, false); assert(m.inputNodes().every(n => n.props.disabled));
    assert.equal(m.node("form").props["aria-describedby"], undefined);
    m.present({ busy: false, error: "" }); retentionGuidance(m, true); assert.deepEqual(m.draft(), draft); assert.equal(m.calls.length, 0);
  } finally { m.task.dispose(); }
});
test("retention label numeric input mode cancel and logical-path autofocus remain intact", () => {
  const m = model("register"); try {
    const label = m.render().find(n => n.type === "label" && text(n) === "Retention (optional)"); assert(label);
    assert.equal(walk(label.props.children).filter(n => n.type === "input").length, 1);
    assert.equal(m.inputNodes()[3].props.inputMode, "numeric"); assert.equal(m.inputNodes()[3].props.autoFocus, undefined);
    assert.equal(m.inputNodes()[0].props.autoFocus, true); (m.node("button", "Cancel registration").props.onClick as () => void)();
    assert.equal(m.closed(), 1); assert.equal(m.calls.length, 0);
  } finally { m.task.dispose(); }
});
test("captured retention request stays exact across busy draft changes and duplicate submission", async () => {
  const m = model("register"); try {
    m.fill(); m.submit(); m.submit(); assert.equal(m.calls.length, 1); const captured = String(m.calls[0].init.body);
    m.enter(3, "101"); retentionGuidance(m, false); await m.succeed(); retentionGuidance(m, true);
    assert.equal(String(m.calls[0].init.body), captured); assert.equal(m.calls.length, 1); assert.equal(m.saved.length, 1);
    assert.equal(m.closed(), 0); assert.equal(m.inputNodes()[3].props.value, "101");
  } finally { m.task.dispose(); }
});
for (const status of [400, 409, 503]) test("ordinary retention registration refusal retains error and drafts " + status, async () => {
  const m = model("register"); try {
    m.fill(); m.submit(); const captured = String(m.calls[0].init.body); await m.fail("Synthetic metadata refusal " + status);
    m.enter(3, "101"); const draft = m.draft(); retentionGuidance(m, true); assert.deepEqual(m.alerts(), ["Synthetic metadata refusal " + status]);
    m.submit(); assert.equal(m.calls.length, 1); assert.equal(String(m.calls[0].init.body), captured);
    assert.deepEqual(m.draft(), draft); assert.equal(m.saved.length, 0); assert.equal(m.closed(), 0);
  } finally { m.task.dispose(); }
});
test("logical-path native-name and retention explanations remain independently linked", () => {
  const m = model("register"); try {
    m.enter(3, "0"); retentionGuidance(m, true);
    assert(m.render().some(n => n.props.id === "kv-register-path-guidance")); assert(m.render().some(n => n.props.id === "kv-register-name-guidance"));
    m.enter(0, "valid/path"); m.enter(2, "valid-name"); retentionGuidance(m, true);
    assert(!m.render().some(n => n.props.id === "kv-register-path-guidance")); assert(!m.render().some(n => n.props.id === "kv-register-name-guidance"));
    m.enter(3, ""); retentionGuidance(m, false); assert.equal(m.calls.length, 0);
  } finally { m.task.dispose(); }
});
test("retention guidance preserves captured mount notice and all other drafts", () => {
  const m = model("register"); try {
    m.fill(); m.enter(3, "101"); retentionGuidance(m, true); const draft = m.draft();
    assert(m.render().some(n => n.type === "p" && text(n).includes("Mount metadata revision 7 was captured when registration opened.")));
    m.present({ busy: false, error: "Synthetic unchanged ordinary error" }); retentionGuidance(m, true);
    assert.deepEqual(m.draft(), draft); assert.deepEqual(m.alerts(), ["Synthetic unchanged ordinary error"]); assert.equal(m.calls.length, 0);
  } finally { m.task.dispose(); }
});
