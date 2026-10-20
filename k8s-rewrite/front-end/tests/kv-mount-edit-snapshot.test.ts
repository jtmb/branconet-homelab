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

const parentFilename="src/app/(dashboard)/secrets/kv/kv-browser.tsx";
const parentSource=ts.createSourceFile(parentFilename,readFileSync(parentFilename,"utf8"),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
const parentNode=parentSource.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==="KvBrowser");assert(parentNode);
const parentOutput=ts.transpileModule(parentNode.getText(parentSource)+"\nmodule.exports=KvBrowser;",{fileName:parentFilename,compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022}}).outputText;
function parentModel() {
 const captured={...mount,namespaces:[...mount.namespaces]};let items=[captured],index=0,refIndex=0,refreshes=0,focuses=0,canWrite=true;
 const slots:unknown[]=[[],[],"","","",captured,undefined,undefined,"",false,0],writes:number[]=[],queries:string[]=[];
 const component={exports:undefined as unknown as ()=>Element};
 const refs=Array.from({length:5},()=>({current:{isConnected:true,focus:()=>{focuses++;}}}));
 const jsx=(type:string,props:Element["props"],key?:unknown):Element=>({type,props,key});
 runInNewContext(parentOutput,{module:component,exports:{},URLSearchParams,
  require:(name:string)=>{assert.equal(name,"react/jsx-runtime");return {jsx,jsxs:jsx};},
  useState:()=>{const slot=index++;return [slots[slot],(value:unknown)=>{writes.push(slot);slots[slot]=typeof value==="function"?value(slots[slot]):value;}];},
  useRef:()=>refs[refIndex++],useCallback:(fn:unknown)=>fn,useEffect:()=>{},
  useSession:()=>({data:{authenticated:true},canWrite,canKvWrite:true}),
  useQuery:(url:string)=>{queries.push(url);assert(["/api/kv/mounts","/api/kv/paths"].includes(url));return {data:{items:url.endsWith("mounts")?items:[],nextCursor:null},refetch:()=>{},updatedAt:Date.now()};},
  usable:(q:{data:unknown})=>q.data,fresh:()=>true,refetchKvMetadata:()=>{refreshes++;},
  Link:"a",MetadataTable:"MetadataTable",CursorControls:"CursorControls",QueryState:"QueryState",MountForm:"MountForm",RegisterForm:"RegisterForm",PathDetail:"PathDetail",input:"input",button:"button",surface:"surface",
 });
 function render(){index=0;refIndex=0;return walk(component.exports());}
 function registration(){const n=render().find(n=>n.type==="MountForm");assert(n);return n;}
 return {captured,slots,writes,queries,registration,render,refreshes:()=>refreshes,focuses:()=>focuses,administrator:(value:boolean)=>{canWrite=value;},
  update:(next:typeof captured[])=>{items=next;},
  refresh:()=>{const n=render().find(n=>n.type==="button"&&text(n)==="Refresh KV metadata");assert(n);(n.props.onClick as ()=>void)();},
  reopen:(id:string)=>{const table=render().find(n=>n.type==="MetadataTable"&&n.props.label==="KV mounts");assert(table);const actions=(table.props.actions as (row:{id:string})=>Element)({id});const n=walk(actions).find(n=>n.type==="button"&&text(n).startsWith("Edit "));assert(n);(n.props.onClick as (event:unknown)=>void)({currentTarget:refs[4].current});},
 };
}
function checkNotice(m: ReturnType<typeof model>, revision: number) {
 const found=m.render().find(n=>n.type==="p"&&text(n).includes("Refreshing the mount list does not update this edit form."));
 assert(found,"captured mount edit explanation missing");assert.equal(found.props.role,undefined);
 assert(text(found).includes(`Mount metadata revision ${revision} was captured when editing opened.`));
 assert(text(found).includes("Cancel and reopen the mount edit to use refreshed metadata; the server checks the submitted revision and current permissions."));
}
for(const revision of [1,7,2147483647])test("mount edit explains exact captured revision "+revision,()=>{
 const m=model("edit",{...mount,revision});try{checkNotice(m,revision);assert.equal(m.calls.length,0);}finally{m.task.dispose();}
});
for(const change of ["renamed","scope-removed","scope-expanded","absent","same-revision"])test("list refresh retains mount edit target and drafts: "+change,()=>{
 const p=parentModel(),m=model("edit");try{m.fill();const draft=m.draft();const next={...p.captured,name:change==="renamed"?"renamed-public":p.captured.name,namespaces:change==="scope-removed"?["scope-a"]:["scope-a","scope-b","scope-c"],revision:change==="same-revision"?7:8};
 p.update(change==="absent"?[]:[next]);p.refresh();const edit=p.registration();assert.equal(edit.props.original,p.captured);assert.equal(edit.key,p.captured.id);assert.deepEqual(p.writes,[10]);assert.equal(p.refreshes(),1);assert.equal(p.focuses(),0);
 assert.deepEqual(m.draft(),draft);checkNotice(m,7);assert.equal(m.calls.length,0);assert.equal(m.saved.length,0);assert.equal(m.closed(),0);
 assert.equal(p.queries.every(url=>["/api/kv/mounts","/api/kv/paths"].includes(url)),true);
 }finally{m.task.dispose();}
});
test("held mount metadata request keeps exact captured ID revision name and scopes",async()=>{
 const m=model("edit");try{m.fill();const draft=m.draft();m.submit();m.submit();checkNotice(m,7);assert.deepEqual(m.statuses(),["Saving mount metadata…"]);assert.equal(m.calls.length,1);assert.equal(m.calls[0].url,"/api/kv/mounts/"+mount.id);assert.equal(m.calls[0].init.method,"PATCH");assert.deepEqual(JSON.parse(String(m.calls[0].init.body)),{name:"changed-mount",namespaces:["scope-b","scope-a"],revision:7});
 assert(m.inputNodes().every(n=>n.props.disabled));assert.deepEqual(m.draft(),draft);await m.succeed();assert.deepEqual(m.saved,[["Mount metadata updated."]]);assert.equal(m.closed(),0);assert.equal(m.calls.length,1);
 }finally{m.task.dispose();}
});
for(const status of [400,409,503])test("ordinary mount metadata error retains drafts and captured explanation "+status,async()=>{
 const m=model("edit");try{m.fill();const draft=m.draft();m.submit();const sent=String(m.calls[0].init.body);await m.fail("Synthetic metadata refusal "+status);checkNotice(m,7);assert.deepEqual(m.draft(),draft);assert.deepEqual(m.alerts(),["Synthetic metadata refusal "+status]);assert.equal(String(m.calls[0].init.body),sent);assert.equal(m.calls.length,1);assert.equal(m.saved.length,0);assert.equal(m.closed(),0);}finally{m.task.dispose();}
});
test("new mount creation has no edit snapshot claim and keeps POST payload",async()=>{
 const m=model("create");try{assert.equal(m.render().some(n=>n.type==="p"&&text(n).includes("captured when editing opened")),false);m.fill();m.submit();assert.equal(m.calls[0].url,"/api/kv/mounts");assert.equal(m.calls[0].init.method,"POST");assert.deepEqual(JSON.parse(String(m.calls[0].init.body)),{name:"changed-mount",namespaces:["scope-b","scope-a"]});await m.succeed();assert.deepEqual(m.saved,[["Mount created."]]);}finally{m.task.dispose();}
});
test("cancel returns focus and explicit reopen takes refreshed mount snapshot",()=>{
 const p=parentModel(),updated={...p.captured,name:"new-public",namespaces:["scope-a"],revision:8};p.update([updated]);(p.registration().props.close as ()=>void)();assert.equal(p.render().some(n=>n.type==="MountForm"),false);assert.equal(p.focuses(),1);p.reopen(updated.id);assert.equal(p.registration().props.original,updated);assert.equal(p.registration().key,updated.id);assert.equal(p.refreshes(),0);assert.deepEqual(p.writes,[5,6,6,5]);
});
test("parent administrator presentation gate still excludes a scoped writer",()=>{
 const p=parentModel();p.administrator(false);assert.equal(p.render().some(n=>n.type==="MountForm"),false);const table=p.render().find(n=>n.type==="MetadataTable"&&n.props.label==="KV mounts");assert(table);const actions=walk((table.props.actions as (row:{id:string})=>Element)({id:p.captured.id}));assert.equal(actions.some(n=>n.type==="button"&&text(n).startsWith("Edit ")),false);assert(actions.some(n=>n.type==="button"&&text(n).startsWith("Register path in ")));assert.equal(p.writes.length,0);
});
