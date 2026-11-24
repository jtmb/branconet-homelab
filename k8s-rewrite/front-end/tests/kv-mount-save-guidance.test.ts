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

function fieldGuidance(m: ReturnType<typeof model>, position: number, expected: boolean) {
 const control=m.inputNodes()[position],id=position===0?"kv-mount-name-guidance":"kv-mount-namespace-guidance";
 const found=m.render().filter(n=>n.props.id===id);
 assert.equal(found.length,expected?1:0,"field guidance visibility "+id);
 assert.equal(control.props["aria-describedby"],expected?id:undefined,"field association "+id);
 if(expected){assert.equal(found[0].type,"p");assert.equal(found[0].props.role,undefined);assert(text(found[0]).includes(position===0?"Mount names must":"Namespace scopes must"));}
}
for(const mode of ["create","edit"] as const){
 for(const value of ["","Upper","0first","has_space","has.dot","a".repeat(64)])test(mode+" identifies invalid mount name only: "+JSON.stringify(value),()=>{
  const m=model(mode);try{m.enter(0,value);m.enter(1,"scope-a, scope-b");fieldGuidance(m,0,true);fieldGuidance(m,1,false);assert.equal(m.node("button","Save mount").props.disabled,true);m.submit();assert.equal(m.calls.length,0);assert.deepEqual(m.draft(),[value,"scope-a, scope-b"]);}finally{m.task.dispose();}
 });
 for(const value of ["","scope-a,scope-a","Upper","-first","last-","has.dot","a".repeat(64),Array.from({length:129},(_,i)=>"ns"+i).join(",")])test(mode+" identifies invalid namespace scope only: "+value.slice(0,40),()=>{
  const m=model(mode);try{m.enter(0,"valid-mount");m.enter(1,value);fieldGuidance(m,0,false);fieldGuidance(m,1,true);assert.equal(m.node("button","Save mount").props.disabled,true);m.submit();assert.equal(m.calls.length,0);assert.deepEqual(m.draft(),["valid-mount",value]);}finally{m.task.dispose();}
 });
 test(mode+" identifies both invalid fields without replacing draft or combined guidance",()=>{
  const m=model(mode);try{m.enter(0,"INVALID");m.enter(1,"not_valid");fieldGuidance(m,0,true);fieldGuidance(m,1,true);const paragraph=m.render().find(n=>n.props.id==="kv-mount-save-guidance");assert(paragraph);assert.equal(m.node("form").props["aria-describedby"],"kv-mount-save-guidance");assert.equal(m.node("button","Save mount").props["aria-describedby"],"kv-mount-save-guidance");m.enter(0,"valid");fieldGuidance(m,0,false);fieldGuidance(m,1,true);m.enter(1,"scope-a");fieldGuidance(m,0,false);fieldGuidance(m,1,false);assert.equal(m.node("button","Save mount").props.disabled,false);assert.equal(m.calls.length,0);}finally{m.task.dispose();}
 });
 test(mode+" busy invalid drafts have no dangling field descriptions",()=>{
  const m=model(mode);try{m.enter(0,"INVALID");m.enter(1,"not_valid");m.present({busy:true,error:""});fieldGuidance(m,0,false);fieldGuidance(m,1,false);assert(m.inputNodes().every(n=>n.props.disabled));assert.equal(m.node("button","Save mount").props.disabled,true);assert.deepEqual(m.draft(),["INVALID","not_valid"]);m.present({busy:false,error:""});fieldGuidance(m,0,true);fieldGuidance(m,1,true);assert.equal(m.calls.length,0);}finally{m.task.dispose();}
 });
 test(mode+" wrapping labels and cancellation remain intact",()=>{
  const m=model(mode);try{const labels=m.render().filter(n=>n.type==="label");assert.equal(labels.length,2);for(const label of labels)assert.equal(walk(label.props.children).filter(n=>n.type==="input").length,1);(m.node("button","Cancel mount edit").props.onClick as ()=>void)();assert.equal(m.closed(),1);assert.equal(m.calls.length,0);}finally{m.task.dispose();}
 });
 test(mode+" captured metadata request remains exact while draft becomes invalid",async()=>{
  const m=model(mode);try{m.fill();m.submit();m.submit();assert.equal(m.calls.length,1);assert.equal(m.calls[0].url,"/api/kv/mounts"+(mode==="edit"?"/"+mount.id:""));assert.equal(m.calls[0].init.method,mode==="edit"?"PATCH":"POST");const payload=String(m.calls[0].init.body);assert.deepEqual(JSON.parse(payload),{name:"changed-mount",namespaces:["scope-b","scope-a"],...(mode==="edit"?{revision:7}:{})});m.enter(0,"INVALID");m.enter(1,"not_valid");fieldGuidance(m,0,false);fieldGuidance(m,1,false);await m.succeed();fieldGuidance(m,0,true);fieldGuidance(m,1,true);assert.equal(String(m.calls[0].init.body),payload);assert.equal(m.calls.length,1);assert.deepEqual(m.saved,[[mode==="edit"?"Mount metadata updated.":"Mount created."]]);assert.equal(m.closed(),0);}finally{m.task.dispose();}
 });
}
for(const [name,scopes] of [["a","0"],["a-","scope-a"],["a".repeat(63),"n".repeat(63)],["valid",Array.from({length:128},(_,i)=>"ns"+i).join(",")]])test("valid boundaries have no field guidance: "+name.slice(0,8)+"/"+scopes.length,()=>{
 const m=model("create");try{m.enter(0,name);m.enter(1,scopes);fieldGuidance(m,0,false);fieldGuidance(m,1,false);assert.equal(m.node("button","Save mount").props.disabled,false);assert.equal(m.calls.length,0);}finally{m.task.dispose();}
});
for(const scopes of ["scope-a, scope-b","scope-a \n scope-b,,"])test("unchanged edit keeps save-only guidance: "+JSON.stringify(scopes),()=>{
 const m=model("edit");try{m.enter(1,scopes);fieldGuidance(m,0,false);fieldGuidance(m,1,false);assert.equal(m.node("button","Save mount").props.disabled,true);assert.equal(m.node("form").props["aria-describedby"],"kv-mount-save-guidance");assert(m.render().some(n=>text(n)==="Change the mount name or namespace scopes to enable Save mount."));m.submit();assert.equal(m.calls.length,0);}finally{m.task.dispose();}
});
for(const status of [400,409,503])test("ordinary failure keeps error draft and captured revision with field-specific help "+status,async()=>{
 const m=model("edit");try{m.fill();m.submit();const payload=String(m.calls[0].init.body);await m.fail("Synthetic metadata refusal "+status);m.enter(0,"INVALID");fieldGuidance(m,0,true);fieldGuidance(m,1,false);assert.deepEqual(m.alerts(),["Synthetic metadata refusal "+status]);assert.deepEqual(m.draft(),["INVALID","scope-b, scope-a"]);assert(m.render().some(n=>n.type==="p"&&text(n).includes("Mount metadata revision 7 was captured when editing opened.")));m.submit();assert.equal(m.calls.length,1);assert.equal(String(m.calls[0].init.body),payload);assert.equal(m.saved.length,0);assert.equal(m.closed(),0);}finally{m.task.dispose();}
});
