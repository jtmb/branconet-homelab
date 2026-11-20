import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import vm from "node:vm";
import { createRequire } from "node:module";
const ts: typeof import("typescript") = createRequire(import.meta.url)(process.env.BORTUS_PUBLIC_TYPESCRIPT ?? "typescript");

// Finite PUBLIC SOURCE controls. All real imported implementations stay inert;
// sibling GET is captured but never invoked. No HTTP, schema or registry access.
type Bag = Record<PropertyKey, unknown>;
type Call = (...args: unknown[]) => unknown;
const routePath = fileURLToPath(new URL("../src/app/api/kv/legacy/route.ts", import.meta.url));
const raw = readFileSync(routePath, "utf8");
const js = ts.transpileModule(raw, { compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
}}).outputText;
function forbidden(): never { throw new Error("unselected implementation reached"); }
function unread(): object {
  return new Proxy(Object.create(null) as object, {
    get: forbidden, ownKeys: forbidden, getOwnPropertyDescriptor: forbidden,
    getPrototypeOf: forbidden, set: forbidden, has: forbidden,
  });
}
function load(httpInput: Bag, schemas: Bag, legacy: Bag) {
  const wraps: { args: unknown[]; token: object }[] = [];
  const http = Object.create(Object.getPrototypeOf(httpInput), Object.getOwnPropertyDescriptors(httpInput)) as Bag;
  Object.defineProperty(http, "kvHuman", { value: function(this: unknown, ...args: unknown[]) {
    assert.equal(this, undefined); const token = Object.freeze({ index: wraps.length });
    wraps.push({ args, token }); return token;
  } });
  const sandboxModule: { exports: Bag } = { exports: {} };
  const requireStub = (id: string) => {
    if (id === "@/lib/kv-http") return http;
    if (id === "@/lib/kv-schemas") return schemas;
    if (id === "@/lib/kv-legacy-access") return legacy;
    throw new Error("unexpected import");
  };
  vm.runInNewContext(js, { module: sandboxModule, exports: sandboxModule.exports, require: requireStub }, { timeout: 1000 });
  assert.equal(wraps.length, 2);
  return { callback: wraps[1].args[0] as Call, wraps, exports: sandboxModule.exports, http };
}
function ctor(instance: object, onConstruct?: (args: unknown[], target: unknown) => void): object {
  return new Proxy(function() {}, { construct(_target, args, newTarget) {
    onConstruct?.(args, newTarget); return instance;
  } });
}
function deferred() {
  let resolve!: (value: unknown) => void, reject!: (reason: unknown) => void;
  const promise = new Promise<unknown>((yes,no) => { resolve=yes; reject=no; });
  return { promise, resolve, reject };
}
async function rejection(action: () => unknown, expected: unknown) {
  let seen=false;
  try { await action(); } catch(error) { seen=true; assert.equal(error,expected); }
  assert.equal(seen,true);
}
async function typeError(action: () => unknown) {
  await assert.rejects(async () => { await action(); }, (error: unknown) => (error as Error)?.name === "TypeError");
}
const scalars: [string, unknown][] = [
  ["undefined",undefined],["null",null],["false",false],["zero",0],["negative zero",-0],
  ["NaN",NaN],["empty",""],["string","public"],["symbol",Symbol("public")],["bigint",7n],
];
const identities: [string, unknown][] = [...scalars,["unread",unread()]];

test("human legacy-principal PATCH finite PUBLIC source controls", async (t) => {
  await t.test("exact nodejs/dynamic/default-status wrappers and only PATCH selected", () => {
    const h=load(Object.defineProperty({},"kvAdminMetadataBody",{get:forbidden}),
      Object.defineProperty({},"legacyPrincipal",{get:forbidden}),
      Object.defineProperty({},"KvLegacyAccess",{get:forbidden}));
    assert.deepEqual(Object.keys(h.exports).sort(),["GET","PATCH","dynamic","runtime"]);
    assert.equal(h.exports.runtime,"nodejs");assert.equal(h.exports.dynamic,"force-dynamic");
    assert.equal(h.exports.GET,h.wraps[0].token);assert.equal(h.exports.PATCH,h.wraps[1].token);
    for(const w of h.wraps){assert.equal(w.args.length,1);assert.equal(typeof w.args[0],"function");}
    assert.equal(h.callback.length,3);assert.equal(Object.getPrototypeOf(h.callback).constructor.name,"AsyncFunction");
    assert.equal(Object.getPrototypeOf(h.wraps[0].args[0]).constructor.name,"Function");
  });
  await t.test("exact capture/call/await/rest/construct/commit order and receivers", async () => {
    const events:string[]=[],registry=unread(),actor=unread(),request=unread(),schema=unread(),impact=unread();
    const hold=deferred(),symbol=Symbol("field"),field=unread(); let payload:Bag|undefined;
    const body=Object.defineProperties({},{legacyImpact:{enumerable:true,get(){events.push("impact.get");return impact;}},
      field:{enumerable:true,get(){events.push("field.get");return field;}},[symbol]:{enumerable:true,value:field}});
    const instance=Object.defineProperty({},"commit",{get(){events.push("commit.get");return function(this:unknown,...args:unknown[]){
      events.push("commit.call");assert.equal(this,instance);assert.equal(args.length,3);assert.equal(args[0],actor);
      payload=args[1] as Bag;assert.equal(args[2],impact);return "result";
    };}});
    const constructor=ctor(instance,(args,target)=>{events.push("construct");assert.equal(args.length,1);assert.equal(args[0],registry);assert.equal(target,constructor);});
    let h:ReturnType<typeof load>;
    const http=Object.defineProperty({},"kvAdminMetadataBody",{get(){events.push("body.get");return function(this:unknown,...args:unknown[]){
      events.push("body.call");assert.equal(this,undefined);assert.equal(args.length,4);
      for(const [i,value] of [registry,actor,request,schema].entries())assert.equal(args[i],value);return hold.promise;
    };}});
    h=load(http,Object.defineProperty({},"legacyPrincipal",{get(){events.push("schema.get");return schema;}}),
      Object.defineProperty({},"KvLegacyAccess",{get(){events.push("constructor.get");return constructor;}}));
    const result=Reflect.apply(h.callback,unread(),[registry,actor,request,unread()]);
    assert.deepEqual(events,["body.get","schema.get","body.call"]);
    hold.resolve(body);assert.equal(await result,"result");
    assert.deepEqual(events,["body.get","schema.get","body.call","impact.get","field.get","constructor.get","construct","commit.get","commit.call"]);
    assert.equal(payload?.kind,"principal");assert.equal(payload?.field,field);assert.equal(payload?.[symbol],field);
    assert.equal(Object.hasOwn(payload!,"legacyImpact"),false);assert.notEqual(payload,body);
  });
  for(const slot of ["registry","actor","request","schema"] as const)for(const [label,value] of identities){
    await t.test(`${slot} ${label} forwarded without inspection`,async()=>{
      const reg=slot==="registry"?value:unread(),actor=slot==="actor"?value:unread(),request=slot==="request"?value:unread(),schema=slot==="schema"?value:unread();
      let calls=0;
      const instance={commit(...args:unknown[]){calls++;assert.equal(args.length,3);assert.equal(args[0],actor);return "ok";}};
      const h=load({kvAdminMetadataBody(...args:unknown[]){assert.equal(args.length,4);for(const [i,x] of [reg,actor,request,schema].entries())assert.equal(args[i],x);return {}; }},
        {legacyPrincipal:schema},{KvLegacyAccess:ctor(instance,args=>{assert.equal(args.length,1);assert.equal(args[0],reg);})});
      assert.equal(await h.callback(reg,actor,request),"ok");assert.equal(calls,1);
    });
  }
  const stages=["body.get","schema.get","body.call","impact.get","ownKeys","descriptor","field.get","constructor.get","construct","commit.get","commit.call"];
  for(const stage of stages)for(const [label,reason] of identities){
    await t.test(`${stage} refusal ${label} rejects exactly and stops later work`,async()=>{
      const events:string[]=[];function step(name:string){events.push(name);if(name===stage)throw reason;}
      const body=new Proxy(Object.defineProperties({}, {legacyImpact:{get(){step("impact.get");return unread();}},
        field:{enumerable:true,get(){step("field.get");return unread();}}}),{
        ownKeys(target){step("ownKeys");return Reflect.ownKeys(target);},
        getOwnPropertyDescriptor(target,key){if(key==="field")step("descriptor");return Reflect.getOwnPropertyDescriptor(target,key);},
      });
      const instance=Object.defineProperty({},"commit",{get(){step("commit.get");return ()=>{step("commit.call");return "ok";};}});
      const h=load(Object.defineProperty({},"kvAdminMetadataBody",{get(){step("body.get");return ()=>{step("body.call");return body;};}}),
        Object.defineProperty({},"legacyPrincipal",{get(){step("schema.get");return unread();}}),
        Object.defineProperty({},"KvLegacyAccess",{get(){step("constructor.get");return ctor(instance,()=>step("construct"));}}));
      await rejection(()=>h.callback(unread(),unread(),unread()),reason);
      assert.deepEqual(events,stages.slice(0,stages.indexOf(stage)+1));
    });
  }
  for(const [label,impact] of identities)await t.test(`impact ${label} captured verbatim and omitted from input`,async()=>{
    const h=load({kvAdminMetadataBody:()=>({legacyImpact:impact,enabled:false})},{legacyPrincipal:unread()},
      {KvLegacyAccess:ctor({commit(...args:unknown[]){assert.equal(args.length,3);assert.equal(args[2],impact);
        const input=args[1] as Bag;assert.equal(input.kind,"principal");assert.equal(input.enabled,false);assert.equal(Object.hasOwn(input,"legacyImpact"),false);return "ok";}})});
    assert.equal(await h.callback(unread(),unread(),unread()),"ok");
  });
  for(const [label,body] of scalars)await t.test(`body ${label} exact rest semantics without schema execution`,async()=>{
    let calls=0;const h=load({kvAdminMetadataBody:()=>body},{legacyPrincipal:unread()},
      {KvLegacyAccess:ctor({commit(_actor:unknown,input:Bag,impact:unknown){calls++;assert.equal(impact,undefined);
        assert.equal(input.kind,"principal");assert.deepEqual(Object.keys(input),typeof body==="string"?[...Array.from({length:body.length},(_,i)=>String(i)),"kind"]:["kind"]);
        return "ok";}})});
    if(body==null){await typeError(()=>h.callback(unread(),unread(),unread()));assert.equal(calls,0);}
    else{assert.equal(await h.callback(unread(),unread(),unread()),"ok");assert.equal(calls,1);}
  });
  await t.test("rest includes enumerable symbols and own __proto__, excludes inherited and nonenumerable fields; kind spread precedence",async()=>{
    const symbol=Symbol("public"),impact=unread(),field=unread();
    const body=Object.create({legacyImpact:impact,inherited:forbidden}) as Bag;
    Object.defineProperties(body,{kind:{enumerable:true,value:"synthetic override"},hidden:{value:unread()},
      [symbol]:{enumerable:true,value:field}});
    Object.defineProperty(body,"__proto__",{enumerable:true,value:field});
    const h=load({kvAdminMetadataBody:()=>body},{legacyPrincipal:unread()},{KvLegacyAccess:ctor({commit(_actor:unknown,input:Bag,seen:unknown){
      assert.equal(seen,impact);assert.equal(input.kind,"synthetic override");assert.equal(input[symbol],field);assert.equal(input.__proto__,field);
      assert.equal(Object.hasOwn(input,"__proto__"),true);assert.equal(Object.hasOwn(input,"hidden"),false);assert.equal(Object.hasOwn(input,"inherited"),false);
      assert.equal(Object.getPrototypeOf(Object.getPrototypeOf(input)),null);return "ok";
    }})});assert.equal(await h.callback(unread(),unread(),unread()),"ok");
  });
  await t.test("rest is captured before constructor; descriptor changes after capture cannot replace values",async()=>{
    const first=unread(),second=unread(),impact=unread(),body={legacyImpact:impact,field:first};
    const h=load({kvAdminMetadataBody:()=>body},{legacyPrincipal:unread()},{KvLegacyAccess:ctor({commit(_actor:unknown,input:Bag,seen:unknown){
      assert.equal(input.field,first);assert.equal(seen,impact);return "ok";
    }},()=>{body.field=second;body.legacyImpact=second;})});assert.equal(await h.callback(unread(),unread(),unread()),"ok");
  });
  for(const [label,invalid] of scalars){
    for(const stage of ["body","constructor","commit"] as const)await t.test(`noncallable ${stage} ${label} refuses at selected boundary`,async()=>{
      let constructs=0,calls=0;
      const h=load({kvAdminMetadataBody:stage==="body"?invalid:()=>({})},{legacyPrincipal:unread()},
        {KvLegacyAccess:stage==="constructor"?invalid:ctor(Object.defineProperty({},"commit",{get(){calls++;return invalid;}}),()=>{constructs++;})});
      await typeError(()=>h.callback(unread(),unread(),unread()));
      assert.equal(constructs,stage==="commit"?1:0);assert.equal(calls,stage==="commit"?1:0);
    });
  }
  for(const [label,result] of scalars)await t.test(`commit result ${label} adopted without conversion`,async()=>{
    const h=load({kvAdminMetadataBody:()=>({})},{legacyPrincipal:unread()},{KvLegacyAccess:ctor({commit:()=>result})});
    assert.equal(await h.callback(unread(),unread(),unread()),result);
  });
  await t.test("body/schema function captured before schema getter can replace body export",async()=>{
    let original=0,replaced=0;const http:Bag={kvAdminMetadataBody(){original++;return {};}};
    let h:ReturnType<typeof load>;
    h=load(http,Object.defineProperty({},"legacyPrincipal",{get(){h.http.kvAdminMetadataBody=()=>{replaced++;return {};};return unread();}}),
      {KvLegacyAccess:ctor({commit:()=>"ok"})});
    assert.equal(await h.callback(unread(),unread(),unread()),"ok");assert.equal(original,1);assert.equal(replaced,0);
    assert.equal(await h.callback(unread(),unread(),unread()),"ok");assert.equal(original,1);assert.equal(replaced,1);
  });
  await t.test("inherited body/schema/constructor getters preserve defining receiver and constructed commit receiver",async()=>{
    let bodyReceiver:unknown,schemaReceiver:unknown,constructorReceiver:unknown;
    const schemas=Object.create(Object.defineProperty({},"legacyPrincipal",{get(){schemaReceiver=this;return unread();}})) as Bag;
    const legacy=Object.create(Object.defineProperty({},"KvLegacyAccess",{get(){constructorReceiver=this;return ctor({commit:()=>"ok"});}})) as Bag;
    const h=load(Object.create(Object.defineProperty({},"kvAdminMetadataBody",{get(){bodyReceiver=this;return ()=>({});}})) as Bag,schemas,legacy);
    assert.equal(await h.callback(unread(),unread(),unread()),"ok");assert.equal(bodyReceiver,h.http);assert.equal(schemaReceiver,schemas);assert.equal(constructorReceiver,legacy);
  });
  await t.test("arrow constructor fails without being called",async()=>{
    let called=false;const h=load({kvAdminMetadataBody:()=>({})},{legacyPrincipal:unread()},{KvLegacyAccess:()=>{called=true;return {};}});
    await typeError(()=>h.callback(unread(),unread(),unread()));assert.equal(called,false);
  });
  for(const [label,value] of scalars)await t.test(`constructor trap primitive ${label} rejects before commit lookup`,async()=>{
    const constructor=new Proxy(function(){},{construct(){return value as object;}});
    const h=load({kvAdminMetadataBody:()=>({})},{legacyPrincipal:unread()},{KvLegacyAccess:constructor});
    await typeError(()=>h.callback(unread(),unread(),unread()));
  });
  await t.test("constructor may return a function object with inherited commit",async()=>{
    const instance=function(){};Object.setPrototypeOf(instance,{commit(this:unknown){assert.equal(this,instance);return "ok";}});
    const h=load({kvAdminMetadataBody:()=>({})},{legacyPrincipal:unread()},{KvLegacyAccess:ctor(instance)});
    assert.equal(await h.callback(unread(),unread(),unread()),"ok");
  });
  await t.test("synchronous body refusal is delivered by rejected async result",async()=>{
    const reason=unread(),h=load({kvAdminMetadataBody(){throw reason;}},{legacyPrincipal:unread()},{KvLegacyAccess:forbidden});
    let result:unknown;assert.doesNotThrow(()=>{result=h.callback(unread(),unread(),unread());});await rejection(()=>result,reason);
  });
  await t.test("body ownKeys invalid duplicates refuse before constructor",async()=>{
    const body=new Proxy({field:1},{ownKeys(){return ["field","field"];}});
    const h=load({kvAdminMetadataBody:()=>body},{legacyPrincipal:unread()},Object.defineProperty({},"KvLegacyAccess",{get:forbidden}));
    await typeError(()=>h.callback(unread(),unread(),unread()));
  });
  for(const stage of ["body","commit"] as const){
    await t.test(`${stage} pending thenable adoption and exactly-once settle`,async()=>{
      const hold=deferred();let thenCalls=0,commits=0;const body={legacyImpact:unread()},result=Object.freeze({public:true});
      const thenable={then(resolve:(x:unknown)=>void,reject:(x:unknown)=>void){thenCalls++;hold.promise.then(()=>{resolve(stage==="body"?body:result);reject("late refusal");resolve("late result");});}};
      const h=load({kvAdminMetadataBody:()=>stage==="body"?thenable:body},{legacyPrincipal:unread()},
        {KvLegacyAccess:ctor({commit(){commits++;return stage==="commit"?thenable:result;}})});
      const p=h.callback(unread(),unread(),unread());let settled=false;Promise.resolve(p).then(()=>{settled=true;});
      await Promise.resolve();await Promise.resolve();assert.equal(settled,false);assert.equal(commits,stage==="body"?0:1);
      hold.resolve(undefined);assert.equal(await p,result);assert.equal(thenCalls,1);assert.equal(commits,1);
    });
    for(const [label,reason] of identities)await t.test(`${stage} rejected promise ${label} propagates exact reason`,async()=>{
      let commits=0;const h=load({kvAdminMetadataBody:()=>stage==="body"?Promise.reject(reason):{}},{legacyPrincipal:unread()},
        {KvLegacyAccess:ctor({commit(){commits++;return Promise.reject(reason);}})});
      await rejection(()=>h.callback(unread(),unread(),unread()),reason);assert.equal(commits,stage==="body"?0:1);
    });
    await t.test(`${stage} throwing then getter refuses exactly`,async()=>{
      const reason=unread(),thenable=Object.defineProperty({},"then",{get(){throw reason;}});
      const h=load({kvAdminMetadataBody:()=>stage==="body"?thenable:{}},{legacyPrincipal:unread()},
        {KvLegacyAccess:ctor({commit:()=>thenable})});await rejection(()=>h.callback(unread(),unread(),unread()),reason);
    });
  }
  await t.test("fresh constructor/schema/body and inherited commit reads on each call",async()=>{
    let schemaGets=0,bodyGets=0,ctorGets=0,constructs=0,commits=0;
    const prototype=Object.defineProperty({},"commit",{get(){commits++;return function(this:unknown){assert.equal(Object.getPrototypeOf(this),prototype);return commits;};}});
    const h=load(Object.defineProperty({},"kvAdminMetadataBody",{get(){bodyGets++;return ()=>({});}}),
      Object.defineProperty({},"legacyPrincipal",{get(){schemaGets++;return unread();}}),
      Object.defineProperty({},"KvLegacyAccess",{get(){ctorGets++;return ctor(Object.create(prototype),()=>{constructs++;});}}));
    assert.equal(await h.callback(unread(),unread(),unread()),1);assert.equal(await h.callback(unread(),unread(),unread()),2);
    assert.deepEqual([schemaGets,bodyGets,ctorGets,constructs,commits],[2,2,2,2,2]);
  });
  await t.test("interleaved bodies preserve captured actor/request/impact/input and independent results",async()=>{
    const holds=[deferred(),deferred()],actors=[unread(),unread()],requests=[unread(),unread()],impacts=[unread(),unread()];
    const results=[Object.freeze({index:0}),Object.freeze({index:1})],inputs:Bag[]=[],order:number[]=[];let bodies=0;
    const h=load({kvAdminMetadataBody(_reg:unknown,actor:unknown,request:unknown){const i=bodies++;assert.equal(actor,actors[i]);assert.equal(request,requests[i]);return holds[i].promise;}},
      {legacyPrincipal:unread()},{KvLegacyAccess:ctor({commit(actor:unknown,input:Bag,impact:unknown){const i=actors.indexOf(actor as object);assert.equal(impact,impacts[i]);assert.equal(input.index,i);inputs.push(input);order.push(i);return results[i];}})});
    const p0=h.callback(unread(),actors[0],requests[0]),p1=h.callback(unread(),actors[1],requests[1]);
    holds[1].resolve({legacyImpact:impacts[1],index:1});assert.equal(await p1,results[1]);
    holds[0].resolve({legacyImpact:impacts[0],index:0});assert.equal(await p0,results[0]);
    assert.deepEqual(order,[1,0]);assert.notEqual(inputs[0],inputs[1]);
  });
  for(const stage of ["body.call","impact.get","construct","commit.get","commit.call"]){
    await t.test(`reentrant ${stage} preserves outer and inner identities`,async()=>{
      const outer=unread(),inner=unread(),results=[Object.freeze({index:0}),Object.freeze({index:1})];
      let started=false,nested:unknown,h:ReturnType<typeof load>;const seen:unknown[]=[],inputs:Bag[]=[];
      function enter(name:string){if(name===stage&&!started){started=true;nested=h.callback(unread(),inner,unread());}}
      const instance=Object.defineProperty({},"commit",{get(){enter("commit.get");return (actor:unknown,input:Bag)=>{
        enter("commit.call");seen.push(actor);inputs.push(input);return results[actor===outer?0:1];
      };}});
      h=load({kvAdminMetadataBody(_registry:unknown,actor:unknown){enter("body.call");return Object.defineProperty({actor},"legacyImpact",{get(){enter("impact.get");return actor;}});}},
        {legacyPrincipal:unread()},{KvLegacyAccess:ctor(instance,()=>enter("construct"))});
      assert.equal(await h.callback(unread(),outer,unread()),results[0]);assert.equal(await nested,results[1]);
      assert.equal(seen.length,2);assert.equal(seen.includes(outer),true);assert.equal(seen.includes(inner),true);assert.notEqual(inputs[0],inputs[1]);
      for(let i=0;i<seen.length;i++)assert.equal(inputs[i].actor,seen[i]);
    });
  }
});
