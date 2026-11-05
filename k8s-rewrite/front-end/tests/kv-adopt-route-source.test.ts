import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC adoption GET/POST SOURCE controls. All imports are inert.
// No actual wrapper/body/schema/registry/engine/HTTP/auth/native/DB executes.
type Model = Record<string, any>;
type Verb = "GET" | "POST";
const route = "src/app/api/kv/paths/[id]/adopt/route.ts";
const compiled = ts.transpileModule(readFileSync(route, "utf8"), { fileName: route,
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
function deferred() {
  let resolve!: (value: any) => void, reject!: (error: unknown) => void;
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const turns = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
function opaque(label: string) {
  return new Proxy({}, { get() { throw new Error(`PUBLIC unexpected ${label} access`); },
    ownKeys() { throw new Error(`PUBLIC unexpected ${label} enumeration`); } });
}
function fixture(verb: Verb) {
  const trace: string[] = [], wrappers: any[][] = [], calls: Model[] = [], engines: unknown[][] = [], bodies: unknown[][] = [];
  const registry = opaque("registry"), actor = opaque("actor"), request = opaque("request"), schema = opaque("schema implementation");
  const body = Object.freeze({ public: "BODY" }), result = Object.freeze({ public: "RESULT" }), fault = new Error("PUBLIC-FAULT");
  const name = verb === "GET" ? "adoptionPreview" : "adopt";
  const state: Model = { id: "PUBLIC-ID", engine: null, method: null, body, result,
    idFault: null, engineFault: null, methodFault: null, bodyGetterFault: null,
    schemaFault: null, bodyFault: null, callFault: null, rejectBody: false, rejectCall: false, bodyHook: null };
  function method(this: unknown, ...args: unknown[]) {
    trace.push("call"); calls.push({ receiver: this, args });
    if (state.callFault) { if (state.rejectCall) return Promise.reject(state.callFault); throw state.callFault; }
    return state.result;
  }
  const engine = Object.defineProperty({}, name, { get() {
    trace.push("method-get"); if (state.methodFault) throw state.methodFault; return state.method;
  } });
  state.engine = engine; state.method = method;
  const wrapped = [Object.freeze({ public: "INERT-GET" }), Object.freeze({ public: "INERT-POST" })];
  const http = {
    kvHuman(...args: any[]) { wrappers.push(args); return wrapped[wrappers.length - 1]; },
    kvEngine(...args: unknown[]) { trace.push("engine"); engines.push(args); if (state.engineFault) throw state.engineFault; return state.engine; },
    get kvBody() { trace.push("body-get"); if (state.bodyGetterFault) throw state.bodyGetterFault;
      return (...args: unknown[]) => {
        trace.push("body"); bodies.push(args); if (state.bodyHook) state.bodyHook();
        if (state.bodyFault) { if (state.rejectBody) return Promise.reject(state.bodyFault); throw state.bodyFault; }
        return state.body;
      };
    },
  };
  const schemas = { get nativeAdopt() { trace.push("schema"); if (state.schemaFault) throw state.schemaFault; return schema; } };
  const m = { exports: {} as Model };
  runInNewContext(compiled, { module: m, exports: m.exports, require: (name: string) => {
    if (name === "@/lib/kv-http") return http;
    assert.equal(name, "@/lib/kv-schemas"); return schemas;
  } }, { filename: route, timeout: 5000 });
  assert.equal(wrappers.length, 2); assert.deepEqual(trace, [] as string[]);
  const params = new Proxy({}, { get(_target, key) {
    assert.equal(key, "id"); trace.push("id"); if (state.idFault) throw state.idFault; return state.id;
  }, ownKeys() { throw fault; } });
  const callback = wrappers[verb === "GET" ? 0 : 1][0];
  return { verb, name, trace, wrappers, calls, engines, bodies, registry, actor, request, schema, body, result, fault,
    state, engine, method, params, wrapped, exports: m.exports,
    invoke: (...args: unknown[]) => callback(args.length > 3 ? args[3] : registry, args.length > 2 ? args[2] : actor,
      args.length > 1 ? args[1] : request, args.length ? args[0] : params) as Promise<unknown> };
}
type Fixture = ReturnType<typeof fixture>;
function exact(f: Fixture, ...values: unknown[]) {
  const actor = values.length ? values[0] : f.actor, id = values.length > 1 ? values[1] : "PUBLIC-ID";
  const body = values.length > 2 ? values[2] : f.body, receiver = values.length > 3 ? values[3] : f.engine;
  const call = f.calls.at(-1)!; assert.equal(call.receiver, receiver); assert.equal(call.args.length, f.verb === "GET" ? 2 : 3);
  assert.equal(call.args[0], actor); assert.equal(call.args[1], id); if (f.verb === "POST") assert.equal(call.args[2], body);
}
const order = (verb: Verb) => verb === "GET" ? ["id", "engine", "method-get", "call"] : ["id", "engine", "method-get", "body-get", "schema", "body", "call"];
const isError = (e: unknown) => Object.prototype.toString.call(e) === "[object Error]";

test("human adoption GET/POST exact SOURCE delegation", async t => {
  await t.test("nodejs/force-dynamic exports and exact two default-status inert wrappers", () => {
    const f = fixture("GET"); assert.deepEqual(Object.keys(f.exports).sort(), ["GET", "POST", "dynamic", "runtime"]);
    assert.equal(f.exports.runtime, "nodejs"); assert.equal(f.exports.dynamic, "force-dynamic");
    assert.equal(f.exports.GET, f.wrapped[0]); assert.equal(f.exports.POST, f.wrapped[1]);
    for (const args of f.wrappers) { assert.equal(args.length, 1); assert.equal(typeof args[0], "function"); }
    assert.notEqual(f.wrappers[0][0], f.wrappers[1][0]); assert.deepEqual(f.trace, []);
  });
  for (const verb of ["GET", "POST"] as const) {
    await t.test(`${verb} exact ordering and registry/receiver/arguments`, async () => {
      const f = fixture(verb); assert.equal(await f.invoke(), f.result); exact(f); assert.deepEqual(f.trace, order(verb));
      assert.equal(f.engines.length, 1); assert.equal(f.engines[0].length, 1); assert.equal(f.engines[0][0], f.registry);
      if (verb === "POST") { assert.equal(f.bodies.length, 1); assert.equal(f.bodies[0].length, 2); assert.equal(f.bodies[0][0], f.request); assert.equal(f.bodies[0][1], f.schema); }
      else assert.equal(f.bodies.length, 0);
    });
    const faults: [string, number][] = [["idFault",1],["engineFault",2],["methodFault",3],...(verb === "POST" ? [["bodyGetterFault",4],["schemaFault",5],["bodyFault",6]] as [string,number][] : []),["callFault",order(verb).length]];
    for (const [field,count] of faults) await t.test(`${verb} ${field} preserves refusal and stops later stages`, async () => {
      const f = fixture(verb); f.state[field] = f.fault; await assert.rejects(f.invoke(), e => e === f.fault);
      assert.deepEqual(f.trace, order(verb).slice(0,count)); assert.equal(f.calls.length, field === "callFault" ? 1 : 0);
    });
    await t.test(`${verb} rejected result preserves refusal`, async () => {
      const f = fixture(verb); f.state.callFault = f.fault; f.state.rejectCall = true;
      await assert.rejects(f.invoke(), e => e === f.fault); assert.equal(f.calls.length, 1);
    });
    for (const value of [undefined,null]) await t.test(`${verb} nullish params ${String(value)} refuse before engine`, async () => {
      const f = fixture(verb); await assert.rejects(f.invoke(value),isError); assert.deepEqual(f.trace,[]);
    });
    await t.test(`${verb} missing id and inherited getter forward unchanged without enumeration`, async () => {
      const f = fixture(verb); await f.invoke({}); exact(f,f.actor,undefined);
      const g = fixture(verb), id = opaque("id"); let reads = 0;
      const p = Object.create({ get id() { reads++; return id; } }); Object.defineProperty(p,"unused",{ get() { throw g.fault; } });
      await g.invoke(p); exact(g,g.actor,id); assert.equal(reads,1);
    });
    for (const value of [undefined,null,false,0,"",Symbol("PUBLIC-ID")]) await t.test(`${verb} id ${String(value)} forwarded unchanged`, async () => {
      const f = fixture(verb); f.state.id=value; await f.invoke(); exact(f,f.actor,value);
    });
    for (const value of [undefined,null]) await t.test(`${verb} nullish engine ${String(value)} refuses before body`, async () => {
      const f=fixture(verb); f.state.engine=value; await assert.rejects(f.invoke(),isError); assert.deepEqual(f.trace,["id","engine"]);
    });
    for (const value of [undefined,null,7,{}]) await t.test(`${verb} noncallable method ${String(value)} has exact refusal order`, async () => {
      const f=fixture(verb); f.state.method=value;
      if (verb === "GET") { await assert.rejects(f.invoke(),isError); assert.deepEqual(f.trace,order(verb).slice(0,3)); }
      else { const held=deferred(); f.state.body=held.promise; const pending=assert.rejects(f.invoke(),isError);
        await turns(); assert.deepEqual(f.trace,order(verb).slice(0,6)); held.resolve(f.body); await pending; assert.deepEqual(f.trace,order(verb).slice(0,6)); }
      assert.equal(f.calls.length,0);
    });
    await t.test(`${verb} inherited method uses original engine receiver; engine then not inspected`, async () => {
      const f=fixture(verb), engine=Object.create({ [f.name]:f.method }); Object.defineProperty(engine,"then",{ get() { throw f.fault; } });
      f.state.engine=engine; await f.invoke(); exact(f,f.actor,"PUBLIC-ID",f.body,engine);
    });
    for (const value of [undefined,null,false,0,"",Symbol("PUBLIC-RESULT")]) await t.test(`${verb} result ${String(value)} adopted unchanged`, async () => {
      const f=fixture(verb); f.state.result=value; assert.equal(await f.invoke(),value); exact(f);
    });
    await t.test(`${verb} held result blocks settlement after exactly one call`, async () => {
      const f=fixture(verb), held=deferred(); f.state.result=held.promise; let settled=false;
      const pending=f.invoke().then(x=>{settled=true;return x;}); await turns(); assert.equal(settled,false); exact(f);
      held.resolve(f.result); assert.equal(await pending,f.result); assert.equal(f.calls.length,1);
    });
    await t.test(`${verb} held result rejection propagates without retry`, async () => {
      const f=fixture(verb), held=deferred(); f.state.result=held.promise; const pending=assert.rejects(f.invoke(),e=>e===f.fault);
      await turns(); held.reject(f.fault); await pending; assert.equal(f.calls.length,1);
    });
    await t.test(`${verb} result thenable first resolution identity; no raw promise identity claim`, async () => {
      const f=fixture(verb); f.state.result={ then(resolve:(x:unknown)=>void,reject:(x:unknown)=>void){resolve(f.result);reject(f.fault);resolve(null);} };
      assert.equal(await f.invoke(),f.result); assert.equal(f.calls.length,1);
    });
    await t.test(`${verb} throwing result then getter preserves refusal`, async () => {
      const f=fixture(verb); f.state.result={get then(){throw f.fault;}}; await assert.rejects(f.invoke(),e=>e===f.fault); assert.equal(f.calls.length,1);
    });
    await t.test(`${verb} fresh calls use fresh registry actor id method and request identities`, async () => {
      const f=fixture(verb); await f.invoke(); const actor=opaque("actor2"), registry=opaque("registry2"), request=opaque("request2"), engine={ [f.name]:f.method };
      f.state.id="PUBLIC-ID2"; f.state.engine=engine; await f.invoke(f.params,request,actor,registry); exact(f,actor,"PUBLIC-ID2",f.body,engine);
      assert.equal(f.engines[1][0],registry); assert.deepEqual(f.trace,[...order(verb),...order(verb).filter(x=>x!=="method-get")]);
      if(verb==="POST")assert.equal(f.bodies[1][0],request);
    });
    await t.test(`${verb} interleaved results preserve per-call identities`, async () => {
      const f=fixture(verb), a=deferred(), b=deferred(), resultB=Object.freeze({public:"RESULT-B"}), actorB=opaque("actorB");
      f.state.result=a.promise; const first=f.invoke(); await turns(); f.state.result=b.promise; f.state.id="PUBLIC-B";
      const second=f.invoke(f.params,f.request,actorB); await turns(); assert.equal(f.calls.length,2);
      b.resolve(resultB); assert.equal(await second,resultB); a.resolve(f.result); assert.equal(await first,f.result);
      assert.equal(f.calls[0].args[0],f.actor); assert.equal(f.calls[0].args[1],"PUBLIC-ID"); assert.equal(f.calls[1].args[0],actorB); assert.equal(f.calls[1].args[1],"PUBLIC-B");
    });
  }
  await t.test("GET never reads request or body/schema even when both getters refuse", async () => {
    const f=fixture("GET"); f.state.bodyGetterFault=f.fault; f.state.schemaFault=f.fault; f.state.bodyFault=f.fault;
    assert.equal(await f.invoke(),f.result); assert.deepEqual(f.trace,order("GET")); assert.equal(f.bodies.length,0);
  });
  await t.test("GET captures method before actor/id argument effects; no unrelated method read", async () => {
    const f=fixture("GET"); Object.defineProperty(f.engine,"adopt",{get(){throw f.fault;}}); await f.invoke(); exact(f);
  });
  await t.test("POST never reads adoptionPreview or request properties", async () => {
    const f=fixture("POST"); Object.defineProperty(f.engine,"adoptionPreview",{get(){throw f.fault;}}); await f.invoke(); exact(f);
  });
  for (const value of [undefined,null,false,0,"",Symbol("PUBLIC-BODY")]) await t.test(`POST body ${String(value)} forwarded without validation`,async()=>{
    const f=fixture("POST"); f.state.body=value; await f.invoke(); exact(f,f.actor,"PUBLIC-ID",value);
  });
  await t.test("POST body rejection wins over noncallable adopt",async()=>{
    const f=fixture("POST"); f.state.method=null; f.state.bodyFault=f.fault; await assert.rejects(f.invoke(),e=>e===f.fault); assert.equal(f.calls.length,0);
  });
  await t.test("POST rejected body promise preserves refusal without adoption",async()=>{
    const f=fixture("POST"); f.state.bodyFault=f.fault; f.state.rejectBody=true; await assert.rejects(f.invoke(),e=>e===f.fault); assert.equal(f.calls.length,0);
  });
  await t.test("POST held body captures original method/engine across replacement",async()=>{
    const f=fixture("POST"), held=deferred(); f.state.body=held.promise; const pending=f.invoke(); await turns(); assert.deepEqual(f.trace,order("POST").slice(0,6));
    f.state.engine=opaque("replacement engine"); f.state.method=null; held.resolve(f.body); assert.equal(await pending,f.result); exact(f);
  });
  await t.test("POST body side effects cannot replace captured method or receiver",async()=>{
    const f=fixture("POST"); f.state.bodyHook=()=>{f.state.method=null;f.state.engine=null;}; await f.invoke(); exact(f);
  });
  await t.test("POST held body rejection never invokes adoption",async()=>{
    const f=fixture("POST"),held=deferred(); f.state.body=held.promise; const pending=assert.rejects(f.invoke(),e=>e===f.fault); await turns(); held.reject(f.fault); await pending; assert.equal(f.calls.length,0);
  });
  await t.test("POST body then protocol only; no grouped fields inspected",async()=>{
    const f=fixture("POST"); let reads=0; const body=new Proxy({},{get(_t,key){assert.equal(key,"then");reads++;return undefined;},ownKeys(){throw f.fault;}});
    f.state.body=body; await f.invoke(); exact(f,f.actor,"PUBLIC-ID",body); assert.equal(reads,1);
  });
  await t.test("POST throwing body then getter preserves refusal",async()=>{
    const f=fixture("POST"); f.state.body={get then(){throw f.fault;}}; await assert.rejects(f.invoke(),e=>e===f.fault); assert.equal(f.calls.length,0);
  });
  await t.test("POST body thenable adopts first resolved input identity",async()=>{
    const f=fixture("POST"); f.state.body={then(resolve:(x:unknown)=>void,reject:(x:unknown)=>void){resolve(f.body);reject(f.fault);resolve(null);}}; await f.invoke(); exact(f);
  });
  await t.test("POST interleaved held bodies retain separate method receiver actor id request and resolved input",async()=>{
    const f=fixture("POST"),a=deferred(),b=deferred(), actorB=opaque("actorB"),requestB=opaque("requestB"),bodyB=Object.freeze({public:"BODY-B"}),engineB={adopt:f.method};
    f.state.body=a.promise; const first=f.invoke(); await turns(); f.state.id="PUBLIC-B"; f.state.engine=engineB; f.state.body=b.promise;
    const second=f.invoke(f.params,requestB,actorB); await turns(); assert.equal(f.calls.length,0); b.resolve(bodyB); await second; exact(f,actorB,"PUBLIC-B",bodyB,engineB);
    a.resolve(f.body); await first; exact(f); assert.equal(f.calls.length,2); assert.equal(f.bodies[0][0],f.request); assert.equal(f.bodies[1][0],requestB);
  });
});
