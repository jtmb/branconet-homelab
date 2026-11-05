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


const explanation = "Use a nonempty NFC-normalized path of at most 512 characters with 1–32 slash-separated segments, each at most 128 characters. Segments cannot be empty or equal to '.' or '..'. Percent signs, backslashes, ASCII spaces and ASCII control characters (including DEL) are not allowed.";
function pathGuidance(m: ReturnType<typeof model>, expected: boolean) {
 const found = m.render().filter(n => n.props.id === "kv-register-path-guidance");
 assert.equal(found.length, expected ? 1 : 0, "path guidance visibility");
 assert.equal(m.inputNodes()[0].props["aria-describedby"], expected ? "kv-register-path-guidance" : undefined, "path input association");
 if (expected) { assert.equal(found[0].type, "p"); assert.equal(found[0].props.role, undefined); assert.equal(text(found[0]), explanation); }
}
const invalidPaths = [
 "", "/leading", "trailing/", "double//segment", ".", "..", "parent/../child", "parent/./child",
 "percent%value", "back\\slash", "has space", "has\0nul", "has\ttab", "has\nnewline", "has\x1fcontrol", "has\x7fdel",
 "e\u0301/non-nfc", "a".repeat(129), Array.from({length:33}, () => "a").join("/"),
 ["a".repeat(128),"b".repeat(128),"c".repeat(128),"d".repeat(126)].join("/"),
];
for (const path of invalidPaths) test("invalid logical path has linked field guidance and no request: "+JSON.stringify(path).slice(0,60), () => {
 const m = model("register"); try { m.fill(); m.enter(0,path); pathGuidance(m,true);
 assert.equal(m.node("button","Register metadata").props.disabled,true);
 assert.equal(m.node("form").props["aria-describedby"],"kv-register-save-guidance");
 assert.equal(m.node("button","Register metadata").props["aria-describedby"],"kv-register-save-guidance");
 m.submit(); assert.equal(m.calls.length,0); assert.equal(m.inputNodes()[0].props.value,path);
 assert.deepEqual(m.draft(),[path,"scope-b","explicit-native","5","logical","exact-key"]);
 } finally { m.task.dispose(); }
});
const validPaths = [
 "a", "team/service", "é/秘密", "a".repeat(128), Array.from({length:32},()=>"a").join("/"),
 ["a".repeat(128),"b".repeat(128),"c".repeat(128),"d".repeat(125)].join("/"),
 "😀".repeat(64), "a-b_c.d", "x\u00a0y", "x\u0085y",
];
for (const path of validPaths) test("valid logical path boundaries retain exact drafts and no field guidance: "+JSON.stringify(path).slice(0,60), () => {
 const m=model("register"); try { m.fill(); m.enter(0,path); pathGuidance(m,false);
 assert.equal(m.node("button","Register metadata").props.disabled,false);
 assert.equal(m.node("form").props["aria-describedby"],undefined);
 assert.equal(m.inputNodes()[0].props.value,path); assert.equal(m.calls.length,0);
 } finally { m.task.dispose(); }
});
test("path-specific guidance follows only path validity while other drafts remain invalid",()=>{
 const m=model("register");try { pathGuidance(m,true);m.enter(0,"valid/path");pathGuidance(m,false);
 assert.equal(m.node("button","Register metadata").props.disabled,true);
 assert.equal(m.node("form").props["aria-describedby"],"kv-register-save-guidance");
 m.enter(0,"invalid//path");pathGuidance(m,true);m.enter(0,"valid/path");pathGuidance(m,false);assert.equal(m.calls.length,0);
 }finally{m.task.dispose();}
});
test("busy invalid path hides paragraph and reference, then idle restores both without requests",()=>{
 const m=model("register");try {m.fill();m.enter(0,"invalid//path");const draft=m.draft();pathGuidance(m,true);
 m.present({busy:true,error:""});pathGuidance(m,false);assert(m.inputNodes().every(n=>n.props.disabled));
 assert.equal(m.node("form").props["aria-describedby"],undefined);
 m.present({busy:false,error:""});pathGuidance(m,true);assert.deepEqual(m.draft(),draft);assert.equal(m.calls.length,0);
 }finally{m.task.dispose();}
});
test("path wrapping label, max length, autofocus and cancel callback are retained",()=>{
 const m=model("register");try {const label=m.render().find(n=>n.type==="label"&&text(n)==="Logical path");assert(label);
 assert.equal(walk(label.props.children).filter(n=>n.type==="input").length,1);
 assert.equal(m.inputNodes()[0].props.maxLength,512);assert.equal(m.inputNodes()[0].props.autoFocus,true);
 (m.node("button","Cancel registration").props.onClick as ()=>void)();assert.equal(m.closed(),1);assert.equal(m.calls.length,0);
 }finally{m.task.dispose();}
});
test("captured registration payload stays exact while busy path draft changes, with one saved callback",async()=>{
 const m=model("register");try {m.fill();m.enter(0,"é/exact");m.submit();m.submit();assert.equal(m.calls.length,1);
 assert.equal(m.calls[0].url,"/api/kv/paths");assert.equal(m.calls[0].init.method,"POST");
 assert.deepEqual(JSON.parse(String(m.calls[0].init.body)),{mountId:mount.id,path:"é/exact",namespace:"scope-b",name:"explicit-native",fields:[{field:"logical",key:"exact-key"}],retention:5});
 const captured=String(m.calls[0].init.body);m.enter(0,"invalid//draft");pathGuidance(m,false);
 await m.succeed();pathGuidance(m,true);assert.equal(String(m.calls[0].init.body),captured);assert.equal(m.calls.length,1);
 assert.equal(m.saved.length,1);assert.equal(m.closed(),0);assert.equal(m.inputNodes()[0].props.value,"invalid//draft");
 }finally{m.task.dispose();}
});
test("valid path preserves optional-retention omission and the captured mount notice",async()=>{
 const m=model("register");try {m.fill();m.enter(3,"");pathGuidance(m,false);m.submit();
 assert.deepEqual(JSON.parse(String(m.calls[0].init.body)),{mountId:mount.id,path:"public/example",namespace:"scope-b",name:"explicit-native",fields:[{field:"logical",key:"exact-key"}]});
 assert(m.render().some(n=>n.type==="p"&&text(n).includes("Mount metadata revision 7 was captured when registration opened.")));
 await m.succeed();assert.equal(m.saved.length,1);
 }finally{m.task.dispose();}
});
for(const status of [400,409,503])test("ordinary registration refusal preserves exact error and drafts with path guidance "+status,async()=>{
 const m=model("register");try {m.fill();m.submit();const captured=String(m.calls[0].init.body);await m.fail("Synthetic metadata refusal "+status);
 m.enter(0,"invalid//draft");const draft=m.draft();pathGuidance(m,true);assert.deepEqual(m.alerts(),["Synthetic metadata refusal "+status]);
 m.submit();assert.equal(m.calls.length,1);assert.equal(String(m.calls[0].init.body),captured);assert.deepEqual(m.draft(),draft);
 assert.equal(m.saved.length,0);assert.equal(m.closed(),0);
 }finally{m.task.dispose();}
});
