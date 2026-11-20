import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC GC preview/commit SOURCE controls. All imports are inert.
// Only the selected callbacks execute; no real wrapper/body/schema/engine runs.
type Model = Record<string, any>;
type Kind = "preview" | "commit";
const paths = { preview: "src/app/api/kv/history/gc/preview/route.ts", commit: "src/app/api/kv/history/gc/route.ts" };
const compiled = Object.fromEntries(Object.entries(paths).map(([k, file]) => [k, ts.transpileModule(readFileSync(file,"utf8"), {
  fileName: file, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
}).outputText]));
function deferred() {
  let resolve!: (value:any)=>void, reject!: (error:unknown)=>void;
  const promise = new Promise<any>((yes,no)=>{resolve=yes;reject=no;});
  return {promise,resolve,reject};
}
const turns = async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
const isError = (e:unknown)=>Object.prototype.toString.call(e)==="[object Error]";
function opaque(label:string) {
  return new Proxy({}, {get(){throw Error(`PUBLIC unexpected ${label} access`);},ownKeys(){throw Error(`PUBLIC unexpected ${label} enumeration`);}});
}
function fixture(kind:Kind) {
  const trace:string[]=[], wrappers:any[][]=[], calls:Model[]=[], engines:unknown[][]=[], bodies:unknown[][]=[];
  const registry=opaque("registry"),actor=opaque("actor"),schema=opaque("schema"),signal=opaque("signal");
  const result=Object.freeze({public:"RESULT"}),fault=Error("PUBLIC-FAULT"), name=kind==="preview"?"gcPreview":"gc";
  const state:Model={pathId:"PUBLIC-PATH",engine:null,method:null,body:null,result,signal,
    bodyGetterFault:null,schemaFault:null,bodyFault:null,engineFault:null,methodFault:null,pathFault:null,signalFault:null,callFault:null,
    rejectBody:false,rejectCall:false,bodyHook:null,pathHook:null,signalHook:null};
  const body=Object.defineProperty({},"pathId",{get(){trace.push("path");if(state.pathHook)state.pathHook();if(state.pathFault)throw state.pathFault;return state.pathId;}});
  const request=new Proxy({}, {get(_t,key){assert.equal(key,"signal");trace.push("signal");if(state.signalHook)state.signalHook();if(state.signalFault)throw state.signalFault;return state.signal;},ownKeys(){throw fault;}});
  function method(this:unknown,...args:unknown[]) {
    trace.push("call");calls.push({receiver:this,args});
    if(state.callFault){if(state.rejectCall)return Promise.reject(state.callFault);throw state.callFault;}return state.result;
  }
  const engine=Object.defineProperty({},name,{get(){trace.push("method");if(state.methodFault)throw state.methodFault;return state.method;}});
  state.engine=engine;state.method=method;state.body=body;
  const wrapped=Object.freeze({public:"INERT-WRAPPER"});
  const http={kvHuman(...args:any[]){wrappers.push(args);return wrapped;},
    get kvBody(){trace.push("body-get");if(state.bodyGetterFault)throw state.bodyGetterFault;return(...args:unknown[])=>{
      trace.push("body");bodies.push(args);if(state.bodyHook)state.bodyHook();
      if(state.bodyFault){if(state.rejectBody)return Promise.reject(state.bodyFault);throw state.bodyFault;}return state.body;
    };},
    kvEngine(...args:unknown[]){trace.push("engine");engines.push(args);if(state.engineFault)throw state.engineFault;return state.engine;}};
  const schemaName=kind==="preview"?"historyGcPreview":"historyGc";
  const schemas=Object.defineProperty({},schemaName,{get(){trace.push("schema");if(state.schemaFault)throw state.schemaFault;return schema;}});
  const m={exports:{} as Model};
  runInNewContext(compiled[kind],{module:m,exports:m.exports,require:(id:string)=>{
    if(id==="@/lib/kv-http")return http;assert.equal(id,"@/lib/kv-schemas");return schemas;
  }},{filename:paths[kind],timeout:5000});
  assert.equal(wrappers.length,1);assert.deepEqual(trace,[] as string[]);
  const callback=wrappers[0][0];
  return {kind,name,state,trace,wrappers,calls,engines,bodies,registry,actor,schema,signal,result,fault,body,request,engine,method,wrapped,exports:m.exports,
    invoke:(...args:unknown[])=>callback(args.length?args[0]:registry,args.length>1?args[1]:actor,args.length>2?args[2]:request) as Promise<unknown>};
}
type Fixture=ReturnType<typeof fixture>;
const order=(kind:Kind)=>["body-get","schema","body","engine","method","path",...(kind==="commit"?["signal"]:[]),"call"];
function exact(f:Fixture,...values:unknown[]) {
  const actor=values.length?values[0]:f.actor,pathId=values.length>1?values[1]:"PUBLIC-PATH",body=values.length>2?values[2]:f.body,
    receiver=values.length>3?values[3]:f.engine,signal=values.length>4?values[4]:f.signal;
  const call=f.calls.at(-1)!;assert.equal(call.receiver,receiver);assert.equal(call.args.length,f.kind==="preview"?2:4);
  assert.equal(call.args[0],actor);assert.equal(call.args[1],pathId);if(f.kind==="commit"){assert.equal(call.args[2],body);assert.equal(call.args[3],signal);}
}

test("human history GC preview/commit exact SOURCE delegation",async t=>{
  for(const kind of ["preview","commit"] as const) {
    await t.test(`${kind} nodejs and exact one default-status inert wrapper`,()=>{
      const f=fixture(kind);assert.deepEqual(Object.keys(f.exports).sort(),["POST","runtime"]);assert.equal(f.exports.runtime,"nodejs");
      assert.equal(f.exports.POST,f.wrapped);assert.equal(f.wrappers[0].length,1);assert.equal(typeof f.wrappers[0][0],"function");assert.deepEqual(f.trace,[] as string[]);
    });
    await t.test(`${kind} exact body/schema before engine method path and signal`,async()=>{
      const f=fixture(kind);assert.equal(await f.invoke(),f.result);exact(f);assert.deepEqual(f.trace,order(kind));
      assert.equal(f.bodies.length,1);assert.equal(f.bodies[0].length,2);assert.equal(f.bodies[0][0],f.request);assert.equal(f.bodies[0][1],f.schema);
      assert.equal(f.engines.length,1);assert.equal(f.engines[0].length,1);assert.equal(f.engines[0][0],f.registry);
    });
    const faults:[string,number][]=[["bodyGetterFault",1],["schemaFault",2],["bodyFault",3],["engineFault",4],["methodFault",5],["pathFault",6],
      ...(kind==="commit"?[["signalFault",7]] as [string,number][]:[]),["callFault",order(kind).length]];
    for(const [field,count] of faults)await t.test(`${kind} ${field} preserves refusal and stops later stages`,async()=>{
      const f=fixture(kind);f.state[field]=f.fault;await assert.rejects(f.invoke(),e=>e===f.fault);
      assert.deepEqual(f.trace,order(kind).slice(0,count));assert.equal(f.calls.length,field==="callFault"?1:0);
    });
    await t.test(`${kind} rejected body promise never acquires engine`,async()=>{
      const f=fixture(kind);f.state.bodyFault=f.fault;f.state.rejectBody=true;await assert.rejects(f.invoke(),e=>e===f.fault);
      assert.deepEqual(f.trace,order(kind).slice(0,3));assert.equal(f.engines.length,0);
    });
    await t.test(`${kind} held body blocks engine and uses fresh engine after resolution`,async()=>{
      const f=fixture(kind),held=deferred();f.state.body=held.promise;const pending=f.invoke();await turns();assert.deepEqual(f.trace,order(kind).slice(0,3));
      const engine={[f.name]:f.method};f.state.engine=engine;held.resolve(f.body);assert.equal(await pending,f.result);exact(f,f.actor,"PUBLIC-PATH",f.body,engine);
    });
    await t.test(`${kind} held body rejection stops engine even if it would refuse`,async()=>{
      const f=fixture(kind),held=deferred();f.state.body=held.promise;f.state.engineFault=Error("UNREACHED");const pending=assert.rejects(f.invoke(),e=>e===f.fault);
      await turns();held.reject(f.fault);await pending;assert.equal(f.engines.length,0);assert.equal(f.calls.length,0);
    });
    await t.test(`${kind} body side effects happen before engine capture`,async()=>{
      const f=fixture(kind),engine={[f.name]:f.method};f.state.bodyHook=()=>{f.state.engine=engine;};await f.invoke();exact(f,f.actor,"PUBLIC-PATH",f.body,engine);
    });
    for(const value of [undefined,null])await t.test(`${kind} nullish body ${String(value)} refuses after engine and method capture`,async()=>{
      const f=fixture(kind);f.state.body=value;await assert.rejects(f.invoke(),isError);assert.deepEqual(f.trace,order(kind).slice(0,5));assert.equal(f.calls.length,0);
    });
    for(const value of [false,0,"",Symbol("PUBLIC-BODY")])await t.test(`${kind} primitive body ${String(value)} yields undefined path without validation`,async()=>{
      const f=fixture(kind);f.state.body=value;await f.invoke();exact(f,f.actor,undefined,value);
    });
    await t.test(`${kind} inherited path getter and missing path avoid enumeration`,async()=>{
      const f=fixture(kind),path=opaque("path");let reads=0;const body=Object.create({get pathId(){reads++;return path;}});
      Object.defineProperty(body,"unused",{get(){throw f.fault;}});f.state.body=body;await f.invoke();exact(f,f.actor,path,body);assert.equal(reads,1);
      const g=fixture(kind);g.state.body={};await g.invoke();exact(g,g.actor,undefined,g.state.body);
    });
    for(const value of [undefined,null,false,0,"",Symbol("PUBLIC-PATH")])await t.test(`${kind} path ${String(value)} passes unchanged`,async()=>{
      const f=fixture(kind);f.state.pathId=value;await f.invoke();exact(f,f.actor,value);
    });
    for(const value of [undefined,null])await t.test(`${kind} nullish engine ${String(value)} refuses before path`,async()=>{
      const f=fixture(kind);f.state.engine=value;await assert.rejects(f.invoke(),isError);assert.deepEqual(f.trace,order(kind).slice(0,4));
    });
    for(const value of [undefined,null,7,{}])await t.test(`${kind} noncallable method ${String(value)} still evaluates arguments`,async()=>{
      const f=fixture(kind);f.state.method=value;await assert.rejects(f.invoke(),isError);assert.deepEqual(f.trace,order(kind).slice(0,-1));assert.equal(f.calls.length,0);
    });
    await t.test(`${kind} path getter refusal wins over noncallable method`,async()=>{
      const f=fixture(kind);f.state.method=null;f.state.pathFault=f.fault;await assert.rejects(f.invoke(),e=>e===f.fault);assert.deepEqual(f.trace,order(kind).slice(0,6));
    });
    await t.test(`${kind} path side effect cannot replace captured method or receiver`,async()=>{
      const f=fixture(kind);f.state.pathHook=()=>{f.state.engine=null;f.state.method=null;};await f.invoke();exact(f);
    });
    await t.test(`${kind} inherited method preserves receiver and ignores engine then`,async()=>{
      const f=fixture(kind),engine=Object.create({[f.name]:f.method});Object.defineProperty(engine,"then",{get(){throw f.fault;}});
      Object.defineProperty(engine,kind==="preview"?"gc":"gcPreview",{get(){throw f.fault;}});f.state.engine=engine;await f.invoke();exact(f,f.actor,"PUBLIC-PATH",f.body,engine);
    });
    await t.test(`${kind} body then getter refusal precedes engine`,async()=>{
      const f=fixture(kind);f.state.body={get then(){throw f.fault;}};await assert.rejects(f.invoke(),e=>e===f.fault);assert.equal(f.engines.length,0);
    });
    await t.test(`${kind} body thenable adopts first resolved input identity`,async()=>{
      const f=fixture(kind);f.state.body={then(resolve:(x:unknown)=>void,reject:(x:unknown)=>void){resolve(f.body);reject(f.fault);resolve(null);}};await f.invoke();exact(f);
    });
    await t.test(`${kind} body only then and path are inspected`,async()=>{
      const f=fixture(kind),reads:PropertyKey[]=[];const body=new Proxy({}, {get(_t,key){reads.push(key);assert.ok(key==="then"||key==="pathId");return key==="pathId"?"PUBLIC-PATH":undefined;},ownKeys(){throw f.fault;}});
      f.state.body=body;await f.invoke();exact(f,f.actor,"PUBLIC-PATH",body);assert.deepEqual(reads,["then","pathId"]);
    });
    for(const value of [undefined,null,false,0,"",Symbol("PUBLIC-RESULT")])await t.test(`${kind} result ${String(value)} adopted unchanged`,async()=>{
      const f=fixture(kind);f.state.result=value;assert.equal(await f.invoke(),value);exact(f);
    });
    await t.test(`${kind} rejected result preserves refusal without retry`,async()=>{
      const f=fixture(kind);f.state.callFault=f.fault;f.state.rejectCall=true;await assert.rejects(f.invoke(),e=>e===f.fault);assert.equal(f.calls.length,1);
    });
    await t.test(`${kind} held result blocks settlement with one call`,async()=>{
      const f=fixture(kind),held=deferred();f.state.result=held.promise;let settled=false;const pending=f.invoke().then(x=>{settled=true;return x;});
      await turns();assert.equal(settled,false);exact(f);held.resolve(f.result);assert.equal(await pending,f.result);assert.equal(f.calls.length,1);
    });
    await t.test(`${kind} held result rejection preserves exact refusal`,async()=>{
      const f=fixture(kind),held=deferred();f.state.result=held.promise;const pending=assert.rejects(f.invoke(),e=>e===f.fault);await turns();held.reject(f.fault);await pending;assert.equal(f.calls.length,1);
    });
    await t.test(`${kind} result thenable adopts resolved identity without raw promise claim`,async()=>{
      const f=fixture(kind);f.state.result={then(resolve:(x:unknown)=>void,reject:(x:unknown)=>void){resolve(f.result);reject(f.fault);resolve(null);}};assert.equal(await f.invoke(),f.result);
    });
    await t.test(`${kind} throwing result then getter preserves refusal`,async()=>{
      const f=fixture(kind);f.state.result={get then(){throw f.fault;}};await assert.rejects(f.invoke(),e=>e===f.fault);assert.equal(f.calls.length,1);
    });
    await t.test(`${kind} fresh calls retain fresh actor registry request body engine and signal`,async()=>{
      const f=fixture(kind);await f.invoke();const actor=opaque("actorB"),registry=opaque("registryB"),signal=opaque("signalB"),request={signal},body={pathId:"PUBLIC-B"},engine={[f.name]:f.method};
      f.state.body=body;f.state.engine=engine;await f.invoke(registry,actor,request);exact(f,actor,"PUBLIC-B",body,engine,signal);
      assert.equal(f.bodies[1][0],request);assert.equal(f.engines[1][0],registry);assert.equal(f.calls.length,2);
    });
    await t.test(`${kind} interleaved bodies use engine at resolution and keep request actor input`,async()=>{
      const f=fixture(kind),a=deferred(),b=deferred(),actorB=opaque("actorB"),registryB=opaque("registryB"),signalB=opaque("signalB"),requestB={signal:signalB},bodyB={pathId:"PUBLIC-B"},engineB={[f.name]:f.method};
      f.state.body=a.promise;const first=f.invoke();f.state.body=b.promise;const second=f.invoke(registryB,actorB,requestB);await turns();assert.equal(f.engines.length,0);
      f.state.engine=engineB;b.resolve(bodyB);await second;exact(f,actorB,"PUBLIC-B",bodyB,engineB,signalB);f.state.engine=f.engine;a.resolve(f.body);await first;exact(f);
      assert.equal(f.engines[0][0],registryB);assert.equal(f.engines[1][0],f.registry);assert.equal(f.bodies[0][0],f.request);assert.equal(f.bodies[1][0],requestB);
    });
    await t.test(`${kind} interleaved held results keep captured arguments`,async()=>{
      const f=fixture(kind),a=deferred(),b=deferred(),bodyB={pathId:"PUBLIC-B"},actorB=opaque("actorB"),resultB={public:"RESULT-B"};
      f.state.result=a.promise;const first=f.invoke();await turns();f.state.body=bodyB;f.state.result=b.promise;const second=f.invoke(f.registry,actorB);await turns();
      b.resolve(resultB);assert.equal(await second,resultB);a.resolve(f.result);assert.equal(await first,f.result);assert.equal(f.calls.length,2);
      assert.equal(f.calls[0].args[0],f.actor);assert.equal(f.calls[0].args[1],"PUBLIC-PATH");assert.equal(f.calls[1].args[0],actorB);assert.equal(f.calls[1].args[1],"PUBLIC-B");
    });
  }
  await t.test("preview never reads request properties",async()=>{const f=fixture("preview");await f.invoke(f.registry,f.actor,opaque("preview request"));exact(f);});
  for(const value of [undefined,null,false,0,"",Symbol("PUBLIC-SIGNAL")])await t.test(`commit signal ${String(value)} passes unchanged`,async()=>{
    const f=fixture("commit");f.state.signal=value;await f.invoke();exact(f,f.actor,"PUBLIC-PATH",f.body,f.engine,value);
  });
  await t.test("commit missing and inherited signal forward exact identities",async()=>{
    const f=fixture("commit");await f.invoke(f.registry,f.actor,{});exact(f,f.actor,"PUBLIC-PATH",f.body,f.engine,undefined);
    let reads=0;const signal=opaque("inherited signal"),request=Object.create({get signal(){reads++;return signal;}});await f.invoke(f.registry,f.actor,request);exact(f,f.actor,"PUBLIC-PATH",f.body,f.engine,signal);assert.equal(reads,1);
  });
  for(const value of [undefined,null])await t.test(`commit nullish request ${String(value)} refuses after path`,async()=>{
    const f=fixture("commit");await assert.rejects(f.invoke(f.registry,f.actor,value),isError);assert.deepEqual(f.trace,order("commit").slice(0,6));assert.equal(f.calls.length,0);
  });
  await t.test("commit signal getter refusal wins over noncallable method",async()=>{
    const f=fixture("commit");f.state.method=null;f.state.signalFault=f.fault;await assert.rejects(f.invoke(),e=>e===f.fault);assert.deepEqual(f.trace,order("commit").slice(0,7));
  });
  await t.test("commit path getter precedes signal getter and can replace its value",async()=>{
    const f=fixture("commit"),signal=opaque("replacement signal");f.state.pathHook=()=>{f.state.signal=signal;};await f.invoke();exact(f,f.actor,"PUBLIC-PATH",f.body,f.engine,signal);
  });
  await t.test("commit signal side effect cannot replace captured receiver method or path",async()=>{
    const f=fixture("commit");f.state.signalHook=()=>{f.state.engine=null;f.state.method=null;f.state.pathId="REPLACED";};await f.invoke();exact(f);
  });
  await t.test("commit reads original request signal after held body resolves",async()=>{
    const f=fixture("commit"),held=deferred(),signal=opaque("late signal");f.state.body=held.promise;const pending=f.invoke();await turns();f.state.signal=signal;held.resolve(f.body);await pending;exact(f,f.actor,"PUBLIC-PATH",f.body,f.engine,signal);
  });
});
