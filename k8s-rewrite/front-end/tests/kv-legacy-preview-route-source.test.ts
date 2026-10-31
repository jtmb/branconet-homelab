import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import vm from "node:vm";
import { createRequire } from "node:module";
const ts: typeof import("typescript") = createRequire(import.meta.url)(process.env.BORTUS_PUBLIC_TYPESCRIPT ?? "typescript");

// NEW finite PUBLIC SOURCE controls: only the captured POST callback executes.
// Actual kvHuman, kvBody, schema, constructor and preview implementations are inert.
type Bag = Record<PropertyKey, unknown>;
type Call = (...args: unknown[]) => unknown;
const raw = readFileSync(fileURLToPath(new URL("../src/app/api/kv/legacy/preview/route.ts", import.meta.url)), "utf8");
const js = ts.transpileModule(raw, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
function forbidden(): never { throw new Error("unselected implementation reached"); }
function unread(): object {
  return new Proxy(Object.create(null) as object, { get: forbidden, ownKeys: forbidden,
    getOwnPropertyDescriptor: forbidden, getPrototypeOf: forbidden, set: forbidden, has: forbidden });
}
function load(httpInput: Bag, schemas: Bag, legacy: Bag) {
  const wraps: { args: unknown[]; token: object }[] = [];
  const http = Object.create(Object.getPrototypeOf(httpInput), Object.getOwnPropertyDescriptors(httpInput)) as Bag;
  Object.defineProperty(http, "kvHuman", { value: function(this: unknown, ...args: unknown[]) {
    assert.equal(this, undefined); const token = Object.freeze({ index: wraps.length }); wraps.push({ args, token }); return token;
  } });
  const m: { exports: Bag } = { exports: {} };
  const requireStub = (id: string) => {
    if (id === "@/lib/kv-http") return http;
    if (id === "@/lib/kv-schemas") return schemas;
    if (id === "@/lib/kv-legacy-access") return legacy;
    throw new Error("unexpected import");
  };
  vm.runInNewContext(js, { module: m, exports: m.exports, require: requireStub }, { timeout: 1000 });
  assert.equal(wraps.length, 1);
  return { callback: wraps[0].args[0] as Call, wraps, exports: m.exports, http };
}
function ctor(instance: object, onConstruct?: (args: unknown[], target: unknown) => void): object {
  return new Proxy(function() {}, { construct(_target, args, target) { onConstruct?.(args, target); return instance; } });
}
function deferred() {
  let resolve!: (value: unknown) => void, reject!: (reason: unknown) => void;
  const promise = new Promise<unknown>((yes,no) => { resolve=yes; reject=no; }); return { promise, resolve, reject };
}
async function rejection(action: () => unknown, expected: unknown) {
  let seen=false; try { await action(); } catch(error) { seen=true; assert.equal(error, expected); } assert.equal(seen,true);
}
async function typeError(action: () => unknown) {
  await assert.rejects(async()=>{ await action(); }, (error: unknown)=>(error as Error)?.name === "TypeError");
}
const scalars: [string,unknown][] = [["undefined",undefined],["null",null],["false",false],["zero",0],["negative zero",-0],
  ["NaN",NaN],["empty",""],["string","public"],["symbol",Symbol("public")],["bigint",7n]];
const identities: [string,unknown][] = [...scalars,["unread",unread()]];

test("human legacy-preview POST finite PUBLIC source controls", async(t)=>{
  await t.test("exact nodejs/default-status wrapper and only POST captured",()=>{
    const h=load(Object.defineProperty({},"kvBody",{get:forbidden}),Object.defineProperty({},"legacyPreview",{get:forbidden}),Object.defineProperty({},"KvLegacyAccess",{get:forbidden}));
    assert.deepEqual(Object.keys(h.exports).sort(),["POST","runtime"]);assert.equal(h.exports.runtime,"nodejs");
    assert.equal(h.exports.POST,h.wraps[0].token);assert.equal(h.wraps[0].args.length,1);
    assert.equal(typeof h.callback,"function");assert.equal(h.callback.length,3);assert.equal(Object.getPrototypeOf(h.callback).constructor.name,"AsyncFunction");
  });
  await t.test("exact capture/call/await/cursor/rest/construct/preview order and receivers",async()=>{
    const events:string[]=[],reg=unread(),actor=unread(),request=unread(),schema=unread(),cursor=unread(),field=unread(),symbol=Symbol("field"),hold=deferred();
    let change:Bag|undefined;
    const body=Object.defineProperties({},{cursor:{enumerable:true,get(){events.push("cursor.get");return cursor;}},field:{enumerable:true,get(){events.push("field.get");return field;}},[symbol]:{enumerable:true,value:field}});
    const instance=Object.defineProperty({},"preview",{get(){events.push("preview.get");return function(this:unknown,...args:unknown[]){events.push("preview.call");assert.equal(this,instance);assert.equal(args.length,3);assert.equal(args[0],actor);change=args[1] as Bag;assert.equal(args[2],cursor);return "ok";};}});
    const constructor=ctor(instance,(args,target)=>{events.push("construct");assert.equal(args.length,1);assert.equal(args[0],reg);assert.equal(target,constructor);});
    const h=load(Object.defineProperty({},"kvBody",{get(){events.push("body.get");return function(this:unknown,...args:unknown[]){events.push("body.call");assert.equal(this,undefined);assert.equal(args.length,2);assert.equal(args[0],request);assert.equal(args[1],schema);return hold.promise;};}}),
      Object.defineProperty({},"legacyPreview",{get(){events.push("schema.get");return schema;}}),Object.defineProperty({},"KvLegacyAccess",{get(){events.push("constructor.get");return constructor;}}));
    const result=Reflect.apply(h.callback,unread(),[reg,actor,request,unread()]);assert.deepEqual(events,["body.get","schema.get","body.call"]);
    hold.resolve(body);assert.equal(await result,"ok");assert.deepEqual(events,["body.get","schema.get","body.call","cursor.get","field.get","constructor.get","construct","preview.get","preview.call"]);
    assert.notEqual(change,body);assert.equal(change?.field,field);assert.equal(change?.[symbol],field);assert.equal(Object.hasOwn(change!,"cursor"),false);assert.equal(Object.hasOwn(change!,"kind"),false);
  });
  for(const slot of ["registry","actor","request","schema"] as const)for(const [label,value] of identities)await t.test(`${slot} ${label} forwarded unread`,async()=>{
    const reg=slot==="registry"?value:unread(),actor=slot==="actor"?value:unread(),request=slot==="request"?value:unread(),schema=slot==="schema"?value:unread();let calls=0;
    const h=load({kvBody(...args:unknown[]){assert.equal(args.length,2);assert.equal(args[0],request);assert.equal(args[1],schema);return {}; }},{legacyPreview:schema},{KvLegacyAccess:ctor({preview(...args:unknown[]){calls++;assert.equal(args.length,3);assert.equal(args[0],actor);assert.equal(args[2],undefined);return "ok";}},args=>{assert.equal(args.length,1);assert.equal(args[0],reg);})});
    assert.equal(await h.callback(reg,actor,request),"ok");assert.equal(calls,1);
  });
  const stages=["body.get","schema.get","body.call","cursor.get","ownKeys","descriptor","field.get","constructor.get","construct","preview.get","preview.call"];
  for(const stage of stages)for(const [label,reason] of identities)await t.test(`${stage} refusal ${label} rejects exactly and stops`,async()=>{
    const events:string[]=[];function step(s:string){events.push(s);if(s===stage)throw reason;}
    const body=new Proxy(Object.defineProperties({},{cursor:{get(){step("cursor.get");return unread();}},field:{enumerable:true,get(){step("field.get");return unread();}}}),{
      ownKeys(target){step("ownKeys");return Reflect.ownKeys(target);},getOwnPropertyDescriptor(target,key){if(key==="field")step("descriptor");return Reflect.getOwnPropertyDescriptor(target,key);}});
    const instance=Object.defineProperty({},"preview",{get(){step("preview.get");return ()=>{step("preview.call");return "ok";};}});
    const h=load(Object.defineProperty({},"kvBody",{get(){step("body.get");return ()=>{step("body.call");return body;};}}),Object.defineProperty({},"legacyPreview",{get(){step("schema.get");return unread();}}),Object.defineProperty({},"KvLegacyAccess",{get(){step("constructor.get");return ctor(instance,()=>step("construct"));}}));
    await rejection(()=>h.callback(unread(),unread(),unread()),reason);assert.deepEqual(events,stages.slice(0,stages.indexOf(stage)+1));
  });
  for(const [label,cursor] of identities)await t.test(`cursor ${label} captured verbatim and excluded from change`,async()=>{
    const h=load({kvBody:()=>({cursor,kind:"grant"})},{legacyPreview:unread()},{KvLegacyAccess:ctor({preview(_a:unknown,change:Bag,seen:unknown){assert.equal(seen,cursor);assert.equal(change.kind,"grant");assert.equal(Object.hasOwn(change,"cursor"),false);return "ok";}})});
    assert.equal(await h.callback(unread(),unread(),unread()),"ok");
  });
  for(const [label,body] of scalars)await t.test(`body ${label} native destructuring semantics only`,async()=>{
    let calls=0;const h=load({kvBody:()=>body},{legacyPreview:unread()},{KvLegacyAccess:ctor({preview(_a:unknown,change:Bag,cursor:unknown){calls++;assert.equal(cursor,undefined);assert.deepEqual(Object.keys(change),typeof body==="string"?Array.from({length:body.length},(_,i)=>String(i)):[]);return "ok";}})});
    if(body==null){await typeError(()=>h.callback(unread(),unread(),unread()));assert.equal(calls,0);}else{assert.equal(await h.callback(unread(),unread(),unread()),"ok");assert.equal(calls,1);}
  });
  await t.test("rest symbols own __proto__ inherited cursor and no discriminator injection",async()=>{
    const symbol=Symbol("public"),cursor=unread(),field=unread(),body=Object.create({cursor,inherited:forbidden}) as Bag;
    Object.defineProperties(body,{kind:{enumerable:true,value:"synthetic"},hidden:{value:unread()},[symbol]:{enumerable:true,value:field}});
    Object.defineProperty(body,"__proto__",{enumerable:true,value:field,configurable:true});
    const h=load({kvBody:()=>body},{legacyPreview:unread()},{KvLegacyAccess:ctor({preview(_a:unknown,change:Bag,seen:unknown){assert.equal(seen,cursor);assert.equal(change.kind,"synthetic");assert.equal(change[symbol],field);assert.equal(change.__proto__,field);assert.equal(Object.hasOwn(change,"__proto__"),true);for(const key of ["cursor","hidden","inherited"])assert.equal(Object.hasOwn(change,key),false);assert.equal(Object.getPrototypeOf(Object.getPrototypeOf(change)),null);return "ok";}})});
    assert.equal(await h.callback(unread(),unread(),unread()),"ok");
  });
  await t.test("rest captured before construction despite body mutation",async()=>{
    const first=unread(),second=unread(),cursor=unread(),body={cursor,field:first};
    const h=load({kvBody:()=>body},{legacyPreview:unread()},{KvLegacyAccess:ctor({preview(_a:unknown,change:Bag,seen:unknown){assert.equal(change.field,first);assert.equal(seen,cursor);return "ok";}},()=>{body.field=second;body.cursor=second;})});assert.equal(await h.callback(unread(),unread(),unread()),"ok");
  });
  for(const [label,invalid] of scalars)for(const stage of ["body","constructor","preview"] as const)await t.test(`noncallable ${stage} ${label} refuses at boundary`,async()=>{
    let constructed=0,lookups=0,schemas=0;
    const h=load({kvBody:stage==="body"?invalid:()=>({})},Object.defineProperty({},"legacyPreview",{get(){schemas++;return unread();}}),{KvLegacyAccess:stage==="constructor"?invalid:ctor(Object.defineProperty({},"preview",{get(){lookups++;return invalid;}}),()=>{constructed++;})});
    await typeError(()=>h.callback(unread(),unread(),unread()));assert.equal(schemas,1);assert.equal(constructed,stage==="preview"?1:0);assert.equal(lookups,stage==="preview"?1:0);
  });
  for(const [label,result] of scalars)await t.test(`preview result ${label} adopted without conversion`,async()=>{
    const h=load({kvBody:()=>({})},{legacyPreview:unread()},{KvLegacyAccess:ctor({preview:()=>result})});assert.equal(await h.callback(unread(),unread(),unread()),result);
  });
  await t.test("body capture precedes schema getter replacing body export",async()=>{
    let original=0,replaced=0;let h:ReturnType<typeof load>;
    h=load({kvBody(){original++;return {}; }},Object.defineProperty({},"legacyPreview",{get(){h.http.kvBody=()=>{replaced++;return {};};return unread();}}),{KvLegacyAccess:ctor({preview:()=>"ok"})});
    assert.equal(await h.callback(unread(),unread(),unread()),"ok");assert.equal(original,1);assert.equal(replaced,0);
  });
  await t.test("preview getter captured once and invoked with constructed receiver",async()=>{
    let gets=0,calls=0;const instance=Object.defineProperty({},"preview",{configurable:true,get(){gets++;Object.defineProperty(instance,"preview",{value:forbidden});return function(this:unknown){assert.equal(this,instance);calls++;return "ok";};}});
    const h=load({kvBody:()=>({})},{legacyPreview:unread()},{KvLegacyAccess:ctor(instance)});assert.equal(await h.callback(unread(),unread(),unread()),"ok");assert.equal(gets,1);assert.equal(calls,1);
  });
  await t.test("constructor export captured once; selected replacement object supplies preview",async()=>{
    let gets=0;const instance={preview(){assert.equal(this,instance);return "ok";}};
    const legacy=Object.defineProperty({},"KvLegacyAccess",{configurable:true,get(){gets++;Object.defineProperty(legacy,"KvLegacyAccess",{value:forbidden});return ctor(instance);}});
    const h=load({kvBody:()=>({})},{legacyPreview:unread()},legacy);assert.equal(await h.callback(unread(),unread(),unread()),"ok");assert.equal(gets,1);
  });
  await t.test("arrow constructor refuses without preview lookup",async()=>{
    const h=load({kvBody:()=>({})},{legacyPreview:unread()},{KvLegacyAccess:()=>forbidden()});await typeError(()=>h.callback(unread(),unread(),unread()));
  });
  for(const [label,result] of scalars)await t.test(`constructor primitive return ${label} uses new receiver`,async()=>{
    let calls=0;function C(this:Bag){this.preview=function(this:Bag){calls++;assert.equal(this.constructor,C);return "ok";};return result;}
    const h=load({kvBody:()=>({})},{legacyPreview:unread()},{KvLegacyAccess:C});assert.equal(await h.callback(unread(),unread(),unread()),"ok");assert.equal(calls,1);
  });
  for(const [label,reason] of identities)for(const stage of ["body","preview"] as const)await t.test(`${stage} rejected promise ${label} preserves reason`,async()=>{
    let calls=0;const h=load({kvBody:()=>stage==="body"?Promise.reject(reason):{}},{legacyPreview:unread()},{KvLegacyAccess:ctor({preview(){calls++;return Promise.reject(reason);}})});
    await rejection(()=>h.callback(unread(),unread(),unread()),reason);assert.equal(calls,stage==="preview"?1:0);
  });
  for(const stage of ["body","preview"] as const)await t.test(`${stage} thenable adoption exact receiver and first settlement`,async()=>{
    let gets=0,calls=0;const target={};const thenable=Object.defineProperty({},"then",{get(){gets++;return function(this:unknown,resolve:Call,reject:Call){assert.equal(this,thenable);calls++;resolve(stage==="body"?{}:target);reject(unread());resolve(unread());throw unread();};}});
    const h=load({kvBody:()=>stage==="body"?thenable:{}},{legacyPreview:unread()},{KvLegacyAccess:ctor({preview:()=>stage==="preview"?thenable:target})});assert.equal(await h.callback(unread(),unread(),unread()),target);assert.equal(gets,1);assert.equal(calls,1);
  });
  for(const stage of ["body","preview"] as const)await t.test(`${stage} throwing then getter rejects exactly`,async()=>{
    const reason=unread(),result=Object.defineProperty({},"then",{get(){throw reason;}});let calls=0;
    const h=load({kvBody:()=>stage==="body"?result:{}},{legacyPreview:unread()},{KvLegacyAccess:ctor({preview(){calls++;return result;}})});await rejection(()=>h.callback(unread(),unread(),unread()),reason);assert.equal(calls,stage==="preview"?1:0);
  });
  await t.test("sequential fresh change objects and construction each call",async()=>{
    const body={cursor:unread(),field:unread()},changes:Bag[]=[],instances:object[]=[];let constructions=0;
    const constructor=new Proxy(function(){},{construct(){constructions++;const instance={preview(_a:unknown,change:Bag,cursor:unknown){assert.equal(this,instance);assert.equal(cursor,body.cursor);changes.push(change);return "ok";}};instances.push(instance);return instance;}});
    const h=load({kvBody:()=>body},{legacyPreview:unread()},{KvLegacyAccess:constructor});assert.equal(await h.callback(unread(),unread(),unread()),"ok");assert.equal(await h.callback(unread(),unread(),unread()),"ok");assert.equal(constructions,2);assert.notEqual(instances[0],instances[1]);assert.notEqual(changes[0],changes[1]);assert.notEqual(changes[0],body);assert.equal(changes[0].field,body.field);
  });
  await t.test("interleaved body completions keep actor registry cursor and change isolated",async()=>{
    const holds=[deferred(),deferred()],regs=[unread(),unread()],actors=[unread(),unread()],reqs=[unread(),unread()],cursors=[unread(),unread()],fields=[unread(),unread()],seen:number[]=[];
    const h=load({kvBody(request:unknown){const i=reqs.indexOf(request as object);assert.ok(i>=0);return holds[i].promise;}},{legacyPreview:unread()},{KvLegacyAccess:new Proxy(function(){},{construct(_t,args){const i=regs.indexOf(args[0] as object);return {preview(actor:unknown,change:Bag,cursor:unknown){seen.push(i);assert.equal(actor,actors[i]);assert.equal(change.field,fields[i]);assert.equal(cursor,cursors[i]);return i;}};}})});
    const a=h.callback(regs[0],actors[0],reqs[0]),b=h.callback(regs[1],actors[1],reqs[1]);holds[1].resolve({cursor:cursors[1],field:fields[1]});assert.equal(await b,1);holds[0].resolve({cursor:cursors[0],field:fields[0]});assert.equal(await a,0);assert.deepEqual(seen,[1,0]);
  });
  await t.test("reentrant body starts fresh callback without outer argument corruption",async()=>{
    const outer=unread(),inner=unread(),outerActor=unread(),innerActor=unread(),outerRequest=unread(),innerRequest=unread();let nested:unknown;const seen:object[]=[];let h:ReturnType<typeof load>;
    h=load({kvBody(request:unknown){if(request===outerRequest){nested=h.callback(inner,innerActor,innerRequest);return {cursor:"outer",field:outer};}assert.equal(request,innerRequest);return {cursor:"inner",field:inner};}},{legacyPreview:unread()},{KvLegacyAccess:new Proxy(function(){},{construct(_t,args){const reg=args[0];return {preview(actor:unknown,change:Bag,cursor:unknown){seen.push(reg as object);assert.equal(change.field,reg);assert.equal(actor,reg===outer?outerActor:innerActor);assert.equal(cursor,reg===outer?"outer":"inner");return reg===outer?"outer":"inner";}};}})});
    assert.equal(await h.callback(outer,outerActor,outerRequest),"outer");assert.equal(await nested,"inner");assert.equal(seen.length,2);assert.equal(seen[0],inner);assert.equal(seen[1],outer);
  });
});
