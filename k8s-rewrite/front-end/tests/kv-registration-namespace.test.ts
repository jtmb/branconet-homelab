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
function model(mode: Mode) {
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
  const props = { original: mode === "edit" ? mount : undefined, mount: { ...mount, namespaces: [...mount.namespaces] }, close: () => { closed++; }, saved: (...args: unknown[]) => { saved.push(args); } };
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

function selected(m: ReturnType<typeof model>) { return m.node("select"); }
function options(m: ReturnType<typeof model>) { return m.render().filter(n => n.type === "option"); }
function identities(m: ReturnType<typeof model>) { return m.render().filter(n => n.type === "div" && String(n.props.className).includes("sm:grid-cols-")).map(n => n.key); }
function namespaceNotice(m: ReturnType<typeof model>) { return m.render().find(n => n.props.id === "kv-register-namespace-scope"); }
function click(m: ReturnType<typeof model>, label: string) { const n = m.node("button",label); assert.equal(n.props.disabled,false); (n.props.onClick as () => void)(); }
function body(m: ReturnType<typeof model>) { return JSON.parse(m.calls.at(-1)!.init.body as string); }

test("initial namespace placeholder stays explicit and blocked", () => {
 const m=model("register");try{assert.equal(selected(m).props.value,"");assert.equal(m.node("button","Register metadata").props.disabled,true);assert.equal(namespaceNotice(m),undefined);assert.equal(options(m).length,3);m.submit();assert.equal(m.calls.length,0);}finally{m.task.dispose();}
});
for(const scopes of [["scope-b","scope-a"],["scope-a","scope-b","scope-c"],["scope-b"]])test("allowed selected namespace retains exact draft on metadata change "+scopes.join(","),()=>{
 const m=model("register");try{m.fill();const draft=m.draft(),keys=identities(m);m.scopes(scopes);assert.deepEqual(m.draft(),draft);assert.deepEqual(identities(m),keys);assert.equal(m.node("button","Register metadata").props.disabled,false);assert.equal(namespaceNotice(m),undefined);assert.equal(m.calls.length,0);assert.equal(selected(m).props.value,"scope-b");}finally{m.task.dispose();}
});
for(const scopes of [["scope-a"],[],["scope-b-suffix"]])test("removed selected namespace blocks direct submit without discarding drafts "+scopes.join(","),()=>{
 const m=model("register");try{m.fill();const draft=m.draft(),keys=identities(m);m.scopes(scopes);assert.equal(m.node("button","Register metadata").props.disabled,true);m.submit();assert.equal(m.calls.length,0);assert.deepEqual(m.draft(),draft);assert.deepEqual(identities(m),keys);assert.equal(m.saved.length,0);assert.equal(m.closed(),0);}finally{m.task.dispose();}
});
test("out of scope selection has an exact disabled option and linked explanation",()=>{
 const m=model("register");try{m.fill();m.scopes(["scope-a"]);const orphan=options(m).find(n=>n.props.value==="scope-b");assert(orphan);assert.equal(orphan.props.disabled,true);assert.equal(text(orphan),"scope-b (outside current mount scope)");const notice=namespaceNotice(m);assert(notice);assert.equal(notice.props.role,"status");assert.equal(text(notice),"The selected namespace is outside the current mount scope. Choose an allowed namespace to register metadata; your other drafts are retained.");assert.equal(selected(m).props["aria-describedby"],notice.props.id);assert.equal(m.calls.length,0);}finally{m.task.dispose();}
});
test("returning scope restores the exact draft without choosing or submitting",()=>{
 const m=model("register");try{m.fill();const draft=m.draft();m.scopes(["scope-a"]);m.scopes(["scope-b","scope-a"]);assert.deepEqual(m.draft(),draft);assert.equal(namespaceNotice(m),undefined);assert.equal(selected(m).props["aria-describedby"],undefined);assert.equal(options(m).filter(n=>text(n)==="scope-b").length,1);assert.equal(m.node("button","Register metadata").props.disabled,false);assert.equal(m.calls.length,0);}finally{m.task.dispose();}
});
for(const retention of ["","7"])test("explicit allowed reselection sends exact metadata only, retention "+retention,async()=>{
 const m=model("register");try{m.fill();m.enter(3,retention);const before=m.draft();m.scopes(["scope-a"]);m.enter(1,"scope-a");assert.deepEqual(m.draft(),before.map((v,i)=>i===1?"scope-a":v));assert.equal(namespaceNotice(m),undefined);m.submit();m.submit();assert.equal(m.calls.length,1);assert.equal(m.calls[0].url,"/api/kv/paths");assert.equal(m.calls[0].init.method,"POST");assert.deepEqual(body(m),{mountId:mount.id,path:"public/example",namespace:"scope-a",name:"explicit-native",fields:[{field:"logical",key:"exact-key"}],...(retention?{retention:7}:{})});await m.succeed();assert.equal(m.saved.length,1);assert.equal(m.closed(),0);}finally{m.task.dispose();}
});
test("empty selection after scope removal returns to ordinary guidance",()=>{
 const m=model("register");try{m.fill();m.scopes(["scope-a"]);m.enter(1,"");assert.equal(namespaceNotice(m),undefined);assert.equal(selected(m).props["aria-describedby"],undefined);assert.equal(options(m).length,2);assert.equal(m.node("button","Register metadata").props.disabled,true);m.submit();assert.equal(m.calls.length,0);}finally{m.task.dispose();}
});
test("busy scope change keeps captured request and hides idle scope guidance",async()=>{
 const m=model("register");try{m.fill();m.submit();m.scopes(["scope-a"]);assert.equal(selected(m).props.disabled,true);assert.equal(namespaceNotice(m),undefined);assert.equal(selected(m).props["aria-describedby"],undefined);assert.deepEqual(m.statuses(),["Registering path metadata…"]);assert.equal(body(m).namespace,"scope-b");assert.equal(m.calls.length,1);await m.fail("Synthetic scope conflict");assert.equal(m.node("button","Register metadata").props.disabled,true);assert(namespaceNotice(m));assert.deepEqual(m.alerts(),["Synthetic scope conflict"]);m.submit();assert.equal(m.calls.length,1);}finally{m.task.dispose();}
});
test("ordinary failure and exact drafts survive scope removal and restoration",async()=>{
 const m=model("register");try{m.fill();const draft=m.draft(),keys=identities(m);m.submit();await m.fail("Synthetic unavailable");m.scopes(["scope-a"]);m.scopes(["scope-b"]);assert.deepEqual(m.alerts(),["Synthetic unavailable"]);assert.deepEqual(m.draft(),draft);assert.deepEqual(identities(m),keys);assert.equal(m.calls.length,1);assert.equal(m.saved.length,0);assert.equal(m.node("button","Register metadata").props.disabled,false);}finally{m.task.dispose();}
});
test("mapping identity and consumed focus requests survive namespace changes",()=>{
 const m=model("register");try{m.fill();click(m,"Add field mapping");m.enter(6,"second");m.enter(7,"native-second");m.attachRefs();const keys=identities(m),draft=m.draft(),focus=[...m.focused];m.scopes(["scope-a"]);assert.deepEqual(identities(m),keys);assert.deepEqual(m.draft(),draft);m.attachRefs();assert.deepEqual(m.focused,focus);m.scopes(["scope-b"]);assert.deepEqual(identities(m),keys);assert.deepEqual(m.draft(),draft);}finally{m.task.dispose();}
});
test("restored namespace payload retains exact sixty-four mappings",async()=>{
 const m=model("register");try{m.fill();while(identities(m).length<64)click(m,"Add field mapping");for(let i=0;i<64;i++){m.enter(4+2*i,"field-"+i);m.enter(5+2*i,"key-"+i);}const keys=identities(m);m.scopes(["scope-a"]);m.submit();assert.equal(m.calls.length,0);m.scopes(["scope-b"]);m.submit();assert.equal(m.calls.length,1);assert.deepEqual(body(m).fields,Array.from({length:64},(_,i)=>({field:"field-"+i,key:"key-"+i})));assert.deepEqual(identities(m),keys);await m.succeed();}finally{m.task.dispose();}
});