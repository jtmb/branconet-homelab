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
  return { focused, attachRefs: (detach = false) => { const nodes = inputNodes(); for (let i = 4; i < nodes.length; i += 2) { const ref = nodes[i].props.ref; if (typeof ref === "function") ref(detach ? null : { focus: () => focused.push((i - 4) / 2 + 1) }); } }, render, node, inputNodes, draft, enter, submit, statuses, alerts, fill, calls, task, saved, closed: () => closed,
    present: (value: MutationState) => { state = value; },
    succeed: async () => { resolve({ id: "returned-metadata-only" }); await Promise.all(pending); },
    fail: async (message: string) => { reject(new Error(message)); await Promise.all(pending); } };
}

function rowNodes(m: ReturnType<typeof model>) {
  return m.render().filter(n => n.type === "div" && String(n.props.className).includes("sm:grid-cols-"));
}
function keys(m: ReturnType<typeof model>) { return rowNodes(m).map(n => n.key); }
function pairs(m: ReturnType<typeof model>) { return m.draft().slice(4); }
function fillPairs(m: ReturnType<typeof model>, count: number) {
  grow(m, count);
  for (let i = 0; i < count; i++) { m.enter(4 + 2 * i, "field-" + i); m.enter(5 + 2 * i, "key-" + i); }
}
function click(m: ReturnType<typeof model>, label: string) {
  const n=m.node("button",label); assert.equal(n.props.disabled,false); (n.props.onClick as () => void)();
}
function rows(m: ReturnType<typeof model>) { return rowNodes(m).length; }
function grow(m: ReturnType<typeof model>, count: number) { while (rows(m)<count) click(m,"Add field mapping"); }
function remove(m: ReturnType<typeof model>, position: number) {
  const n=m.render().find(n=>n.props["aria-label"]==="Remove field mapping "+position);
  assert(n); assert.equal(n.props.disabled,false); (n.props.onClick as () => void)();
}
for (const [count,position] of [[3,2],[4,2],[4,3],[64,32],[64,1],[64,64]]) test("surviving identities and exact drafts after removing "+position+" of "+count,()=>{
 const m=model("register"); try {
  m.fill(); fillPairs(m,count); const beforeKeys=keys(m), before=pairs(m);
  assert.equal(new Set(beforeKeys).size,count); assert(beforeKeys.every(k=>k!==undefined));
  remove(m,position);
  assert.deepEqual(keys(m),beforeKeys.filter((_,i)=>i!==position-1));
  assert.deepEqual(pairs(m),before.filter((_,i)=>Math.floor(i/2)!==position-1));
  assert.equal(m.calls.length,0); assert.equal(m.saved.length,0);
 } finally {m.task.dispose();}
});
for (const count of [1,3,64]) test("typing either draft preserves all "+count+" identities",()=>{
 const m=model("register"); try {fillPairs(m,count);const before=keys(m);m.enter(4,"edited-field");m.enter(5,"edited-key");assert.deepEqual(keys(m),before);assert.equal(new Set(keys(m)).size,count);} finally {m.task.dispose();}
});
test("remove middle, edit survivor, add and remove again keeps associations",()=>{
 const m=model("register");try{
  m.fill();fillPairs(m,4);const initial=keys(m);remove(m,2);
  m.enter(6,"edited-survivor");m.enter(7,"exact-survivor-key");
  assert.deepEqual(keys(m),[initial[0],initial[2],initial[3]]);
  assert.deepEqual(pairs(m),["field-0","key-0","edited-survivor","exact-survivor-key","field-3","key-3"]);
  click(m,"Add field mapping"); const added=keys(m)[3];
  assert(!initial.includes(added));assert.deepEqual(keys(m).slice(0,3),[initial[0],initial[2],initial[3]]);
  m.enter(10,"new-field");m.enter(11,"new-key");remove(m,1);
  assert.deepEqual(keys(m),[initial[2],initial[3],added]);
  assert.deepEqual(pairs(m),["edited-survivor","exact-survivor-key","field-3","key-3","new-field","new-key"]);
 }finally{m.task.dispose();}
});
test("removed last identity is not reassigned on later add",()=>{
 const m=model("register");try{fillPairs(m,3);const before=keys(m);remove(m,3);click(m,"Add field mapping");assert(!before.includes(keys(m)[2]));assert.deepEqual(keys(m).slice(0,2),before.slice(0,2));}finally{m.task.dispose();}
});
for (const retention of ["","7"]) test("identity remains local in exact registration payload retention "+retention,async()=>{
 const m=model("register");try{
  m.fill();m.enter(3,retention);fillPairs(m,3);remove(m,2);click(m,"Add field mapping");m.enter(8,"replacement");m.enter(9,"replacement-native");
  const before=keys(m);m.submit();m.submit();assert.equal(m.calls.length,1);
  assert.equal(m.calls[0].url,"/api/kv/paths");assert.equal(m.calls[0].init.method,"POST");
  assert.deepEqual(JSON.parse(m.calls[0].init.body as string),{mountId:mount.id,path:"public/example",namespace:"scope-b",name:"explicit-native",fields:[{field:"field-0",key:"key-0"},{field:"field-2",key:"key-2"},{field:"replacement",key:"replacement-native"}],...(retention?{retention:7}:{})});
  assert.deepEqual(keys(m),before);await m.succeed();assert.equal(m.saved.length,1);assert.equal(m.closed(),0);
 }finally{m.task.dispose();}
});
for(const message of ["Synthetic conflict","Synthetic service unavailable"])test("ordinary failure preserves identities and exact drafts: "+message,async()=>{
 const m=model("register");try{m.fill();fillPairs(m,3);remove(m,2);const before=keys(m),draft=m.draft();m.submit();await m.fail(message);assert.deepEqual(keys(m),before);assert.deepEqual(m.draft(),draft);assert.deepEqual(m.alerts(),[message]);assert.equal(m.saved.length,0);m.enter(6,"retry-field");assert.deepEqual(keys(m),before);}finally{m.task.dispose();}
});
test("busy and ordinary status renders do not change identities",()=>{
 const m=model("register");try{fillPairs(m,4);remove(m,2);const before=keys(m),draft=m.draft();m.present({busy:true,error:""});assert.deepEqual(keys(m),before);assert(m.inputNodes().every(n=>n.props.disabled));m.present({busy:false,error:"Synthetic status"});assert.deepEqual(keys(m),before);assert.deepEqual(m.draft(),draft);assert.equal(m.calls.length,0);}finally{m.task.dispose();}
});
test("middle removal preserves requested positional focus and current numbered labels",()=>{
 const m=model("register");try{fillPairs(m,4);m.attachRefs();m.focused.length=0;const before=keys(m);remove(m,2);m.attachRefs(true);m.attachRefs();m.attachRefs();assert.deepEqual(m.focused,[2]);assert.deepEqual(keys(m),[before[0],before[2],before[3]]);const labels=m.render().filter(n=>n.type==="label").map(text);for(let i=1;i<=3;i++){assert(labels.includes("Field "+i));assert(labels.includes("Native key "+i));}assert.equal(m.calls.length,0);}finally{m.task.dispose();}
});
test("new form instance starts with an independent local row identity",()=>{
 const a=model("register"),b=model("register");try{fillPairs(a,3);fillPairs(b,3);const before=keys(b),draft=b.draft();remove(a,2);assert.deepEqual(keys(b),before);assert.deepEqual(b.draft(),draft);assert.equal(a.calls.length+b.calls.length,0);}finally{a.task.dispose();b.task.dispose();}
});
