import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// NEW finite PUBLIC import callback SOURCE controls. Every import is inert.
// No real wrapper, body parser, schema, registry, engine or transfer executes.
type Model = Record<string, any>;
const path = "src/app/api/kv/import/route.ts";
const compiled = ts.transpileModule(readFileSync(path,"utf8"), {
  fileName:path, compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}
}).outputText;
function deferred() {
  let resolve!:(value:any)=>void,reject!:(error:unknown)=>void;
  const promise=new Promise<any>((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};
}
const turns=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
const isError=(e:unknown)=>Object.prototype.toString.call(e)==="[object Error]";
function opaque(label:string) {
  return new Proxy({}, {get(){throw Error(`PUBLIC unexpected ${label} access`);},ownKeys(){throw Error(`PUBLIC unexpected ${label} enumeration`);}});
}
function fixture() {
  const trace:string[]=[],wrappers:any[][]=[],engines:unknown[][]=[],bodies:unknown[][]=[],constructions:Model[]=[],calls:Model[]=[];
  const registry=opaque("registry"),actor=opaque("actor"),schema=opaque("schema"),signal=opaque("signal"),engine=opaque("engine");
  const body=Object.freeze({public:"INPUT"}),result=Object.freeze({public:"RESULT"}),fault=Error("PUBLIC-FAULT");
  const state:Model={ctor:null,engineFn:null,bodyFn:null,engine,signal,transfer:null,method:null,body,result,
    bytes:16384,bytesFault:null,bytesHook:null,schemaHook:null,ctorGetterFault:null,engineGetterFault:null,engineFault:null,signalFault:null,constructFault:null,methodFault:null,
    bodyGetterFault:null,schemaFault:null,bodyFault:null,callFault:null,rejectBody:false,rejectCall:false,
    ctorGetterHook:null,engineHook:null,signalHook:null,constructHook:null,methodHook:null,bodyHook:null};
  const request=new Proxy({}, {get(_t,key){assert.equal(key,"signal");trace.push("signal");if(state.signalHook)state.signalHook();if(state.signalFault)throw state.signalFault;return state.signal;},ownKeys(){throw fault;}});
  function method(this:unknown,...args:unknown[]) {
    trace.push("call");calls.push({receiver:this,args});
    if(state.callFault){if(state.rejectCall)return Promise.reject(state.callFault);throw state.callFault;}return state.result;
  }
  const transfer=Object.defineProperty({},"import",{get(){trace.push("method");if(state.methodHook)state.methodHook();if(state.methodFault)throw state.methodFault;return state.method;}});
  function Transfer(this:unknown,...args:unknown[]) {
    trace.push("construct");constructions.push({receiver:this,newTarget:new.target,args});
    if(state.constructHook)state.constructHook();if(state.constructFault)throw state.constructFault;return state.transfer;
  }
  function engineFn(...args:unknown[]) {
    trace.push("engine");engines.push(args);if(state.engineHook)state.engineHook();if(state.engineFault)throw state.engineFault;return state.engine;
  }
  state.ctor=Transfer;state.engineFn=engineFn;state.transfer=transfer;state.method=method;
  const wrapped=Object.freeze({public:"INERT-WRAPPER"});
  state.bodyFn=(...args:unknown[])=>{
      trace.push("body");bodies.push(args);if(state.bodyHook)state.bodyHook();
      if(state.bodyFault){if(state.rejectBody)return Promise.reject(state.bodyFault);throw state.bodyFault;}return state.body;
  };
  const http={kvHuman(...args:any[]){wrappers.push(args);return wrapped;},
    get kvEngine(){trace.push("engine-get");if(state.engineGetterFault)throw state.engineGetterFault;return state.engineFn;},
    get kvBody(){trace.push("body-get");if(state.bodyGetterFault)throw state.bodyGetterFault;return state.bodyFn;}};
  const transfers={get KvTransfer(){trace.push("ctor-get");if(state.ctorGetterHook)state.ctorGetterHook();if(state.ctorGetterFault)throw state.ctorGetterFault;return state.ctor;},
    get importSchema(){trace.push("schema");if(state.schemaHook)state.schemaHook();if(state.schemaFault)throw state.schemaFault;return schema;},
    get KV_TRANSFER_BYTES(){trace.push("bytes");if(state.bytesHook)state.bytesHook();if(state.bytesFault)throw state.bytesFault;return state.bytes;}};
  const m={exports:{} as Model};
  runInNewContext(compiled,{module:m,exports:m.exports,require:(id:string)=>{
    if(id==="@/lib/kv-http")return http;assert.equal(id,"@/lib/kv-transfer");return transfers;
  }},{filename:path,timeout:5000});
  assert.equal(wrappers.length,1);assert.deepEqual(trace,[] as string[]);
  const callback=wrappers[0][0];
  return {state,trace,wrappers,engines,bodies,constructions,calls,registry,actor,schema,signal,engine,body,result,fault,request,method,transfer,Transfer,wrapped,exports:m.exports,
    invoke:(...args:unknown[])=>callback(args.length?args[0]:registry,args.length>1?args[1]:actor,args.length>2?args[2]:request) as Promise<unknown>};
}
type Fixture=ReturnType<typeof fixture>;
const order=["ctor-get","engine-get","engine","signal","construct","method","body-get","schema","bytes","body","call"];
function exact(f:Fixture,...values:unknown[]) {
  const actor=values.length?values[0]:f.actor,body=values.length>1?values[1]:f.body,transfer=values.length>2?values[2]:f.transfer;
  const call=f.calls.at(-1)!;assert.equal(call.receiver,transfer);assert.equal(call.args.length,2);assert.equal(call.args[0],actor);assert.equal(call.args[1],body);
}
function construction(f:Fixture,...values:unknown[]) {
  const engine=values.length?values[0]:f.engine,signal=values.length>1?values[1]:f.signal;
  const c=f.constructions.at(-1)!;assert.equal(c.args.length,2);assert.equal(c.args[0],engine);assert.equal(c.args[1],signal);assert.equal(c.newTarget,f.Transfer);
}

test("human import commit exact SOURCE delegation",async t=>{
  await t.test("nodejs and exact one default-status inert wrapper",()=>{
    const f=fixture();assert.deepEqual(Object.keys(f.exports).sort(),["POST","runtime"]);assert.equal(f.exports.runtime,"nodejs");
    assert.equal(f.exports.POST,f.wrapped);assert.equal(f.wrappers[0].length,1);assert.equal(typeof f.wrappers[0][0],"function");assert.deepEqual(f.trace,[] as string[]);
  });
  await t.test("exact constructor engine signal method body schema and call order",async()=>{
    const f=fixture();assert.equal(await f.invoke(),f.result);exact(f);construction(f);assert.deepEqual(f.trace,order);
    assert.equal(f.engines.length,1);assert.equal(f.engines[0].length,1);assert.equal(f.engines[0][0],f.registry);
    assert.equal(f.constructions.length,1);assert.equal(f.bodies.length,1);assert.equal(f.bodies[0].length,3);assert.equal(f.bodies[0][0],f.request);assert.equal(f.bodies[0][1],f.schema);assert.equal(f.bodies[0][2],81920);
  });
  const faults:[string,number][]=[["ctorGetterFault",1],["engineGetterFault",2],["engineFault",3],["signalFault",4],["constructFault",5],["methodFault",6],["bodyGetterFault",7],["schemaFault",8],["bytesFault",9],["bodyFault",10],["callFault",11]];
  for(const [field,count] of faults)await t.test(`${field} preserves exact refusal and stops later stages`,async()=>{
    const f=fixture();f.state[field]=f.fault;await assert.rejects(f.invoke(),e=>e===f.fault);assert.deepEqual(f.trace,order.slice(0,count));assert.equal(f.calls.length,field==="callFault"?1:0);
  });
  for(const value of [undefined,null,7,{},()=>{}])await t.test(`nonconstructible constructor ${String(value)} evaluates engine and signal only`,async()=>{
    const f=fixture();f.state.ctor=value;await assert.rejects(f.invoke(),isError);assert.deepEqual(f.trace,order.slice(0,4));assert.equal(f.constructions.length,0);assert.equal(f.bodies.length,0);
  });
  await t.test("signal refusal wins over nonconstructible constructor",async()=>{
    const f=fixture();f.state.ctor=null;f.state.signalFault=f.fault;await assert.rejects(f.invoke(),e=>e===f.fault);assert.deepEqual(f.trace,order.slice(0,4));
  });
  await t.test("engine refusal wins over nonconstructible constructor",async()=>{
    const f=fixture();f.state.ctor=null;f.state.engineFault=f.fault;await assert.rejects(f.invoke(),e=>e===f.fault);assert.deepEqual(f.trace,order.slice(0,3));
  });
  for(const value of [undefined,null,9,{}])await t.test(`noncallable engine ${String(value)} prevents signal and construction`,async()=>{
    const f=fixture();f.state.engineFn=value;await assert.rejects(f.invoke(),isError);assert.deepEqual(f.trace,order.slice(0,2));assert.equal(f.constructions.length,0);
  });
  for(const value of [undefined,null,false,0,"",Symbol("PUBLIC-ENGINE")])await t.test(`engine result ${String(value)} forwarded without inspection`,async()=>{
    const f=fixture();f.state.engine=value;await f.invoke();construction(f,value);exact(f);
  });
  await t.test("constructor getter side effect precedes engine selection",async()=>{
    const f=fixture(),engine=opaque("replacement engine");f.state.ctorGetterHook=()=>{f.state.engine=engine;};await f.invoke();construction(f,engine);
  });
  await t.test("engine side effects cannot replace captured constructor",async()=>{
    const f=fixture();f.state.engineHook=()=>{f.state.ctor=null;};await f.invoke();construction(f);exact(f);
  });
  await t.test("signal side effects cannot replace captured constructor or engine",async()=>{
    const f=fixture();f.state.signalHook=()=>{f.state.ctor=null;f.state.engine=null;};await f.invoke();construction(f);exact(f);
  });
  await t.test("engine runs before signal getter and can replace its value",async()=>{
    const f=fixture(),signal=opaque("replacement signal");f.state.engineHook=()=>{f.state.signal=signal;};await f.invoke();construction(f,f.engine,signal);
  });
  for(const value of [undefined,null,false,0,"",Symbol("PUBLIC-SIGNAL")])await t.test(`signal ${String(value)} forwarded unchanged`,async()=>{
    const f=fixture();f.state.signal=value;await f.invoke();construction(f,f.engine,value);
  });
  await t.test("missing and inherited signal do not enumerate request",async()=>{
    const f=fixture(),missing={};await f.invoke(f.registry,f.actor,missing);construction(f,f.engine,undefined);assert.equal(f.bodies[0][0],missing);
    let reads=0;const signal=opaque("inherited signal"),request=Object.create({get signal(){reads++;return signal;}});await f.invoke(f.registry,f.actor,request);construction(f,f.engine,signal);assert.equal(f.bodies[1][0],request);assert.equal(reads,1);
  });
  for(const value of [undefined,null])await t.test(`nullish request ${String(value)} refuses after engine`,async()=>{
    const f=fixture();await assert.rejects(f.invoke(f.registry,f.actor,value),isError);assert.deepEqual(f.trace,order.slice(0,3));assert.equal(f.constructions.length,0);
  });
  await t.test("constructor side effect selects transfer before method lookup",async()=>{
    const f=fixture(),transfer={import:f.method};f.state.constructHook=()=>{f.state.transfer=transfer;};await f.invoke();exact(f,f.actor,f.body,transfer);
  });
  await t.test("inherited method preserves original transfer receiver and ignores then",async()=>{
    const f=fixture(),transfer=Object.create({import:f.method});Object.defineProperty(transfer,"then",{get(){throw f.fault;}});f.state.transfer=transfer;await f.invoke();exact(f,f.actor,f.body,transfer);
  });
  for(const value of [undefined,null,false,0,"",Symbol("PUBLIC-CONSTRUCTOR-RETURN")])await t.test(`primitive constructor return ${String(value)} uses new instance`,async()=>{
    const f=fixture();f.state.transfer=value;Object.defineProperty(f.Transfer.prototype,"import",{value:f.method});await f.invoke();exact(f,f.actor,f.body,f.constructions[0].receiver);construction(f);
  });
  for(const value of [undefined,null,7,{}])await t.test(`noncallable import ${String(value)} still awaits exact body`,async()=>{
    const f=fixture();f.state.method=value;await assert.rejects(f.invoke(),isError);assert.deepEqual(f.trace,order.slice(0,10));assert.equal(f.calls.length,0);assert.equal(f.bodies.length,1);
  });
  await t.test("body refusal wins over noncallable captured import",async()=>{
    const f=fixture();f.state.method=null;f.state.bodyFault=f.fault;await assert.rejects(f.invoke(),e=>e===f.fault);assert.deepEqual(f.trace,order.slice(0,10));
  });
  await t.test("held body does not call noncallable import before resolution",async()=>{
    const f=fixture(),held=deferred();f.state.method=null;f.state.body=held.promise;let settled=false;const pending=assert.rejects(f.invoke(),isError).then(()=>{settled=true;});await turns();assert.equal(settled,false);assert.deepEqual(f.trace,order.slice(0,10));held.resolve(f.body);await pending;
  });
  await t.test("transfer returned thenable is not adopted before import lookup",async()=>{
    const f=fixture(),transfer={import:f.method,get then(){throw f.fault;}};f.state.transfer=transfer;await f.invoke();exact(f,f.actor,f.body,transfer);
  });
  await t.test("missing import still evaluates and awaits body",async()=>{
    const f=fixture();f.state.transfer=Object.create(null);await assert.rejects(f.invoke(),isError);assert.deepEqual(f.trace,[...order.slice(0,5),...order.slice(6,10)]);assert.equal(f.calls.length,0);
  });
  await t.test("callable object returned from constructor keeps its import receiver",async()=>{
    const f=fixture(),transfer=Object.assign(()=>{throw f.fault;},{import:f.method});f.state.transfer=transfer;await f.invoke();exact(f,f.actor,f.body,transfer);
  });
  for(const value of [undefined,null,7,{}])await t.test(`noncallable body ${String(value)} reads schema and limit before refusal`,async()=>{
    const f=fixture();f.state.bodyFn=value;await assert.rejects(f.invoke(),isError);assert.deepEqual(f.trace,order.slice(0,9));assert.equal(f.calls.length,0);
  });
  await t.test("schema refusal wins over noncallable body",async()=>{
    const f=fixture();f.state.bodyFn=null;f.state.schemaFault=f.fault;await assert.rejects(f.invoke(),e=>e===f.fault);assert.deepEqual(f.trace,order.slice(0,8));
  });
  await t.test("method getter effects cannot replace original receiver",async()=>{
    const f=fixture();f.state.methodHook=()=>{f.state.transfer=null;};await f.invoke();exact(f);
  });
  await t.test("body side effects cannot replace captured transfer method engine or signal",async()=>{
    const f=fixture();f.state.bodyHook=()=>{f.state.transfer=null;f.state.method=null;f.state.engine=null;f.state.signal=null;};await f.invoke();exact(f);construction(f);
  });
  await t.test("rejected body promise preserves refusal after one construction",async()=>{
    const f=fixture();f.state.bodyFault=f.fault;f.state.rejectBody=true;await assert.rejects(f.invoke(),e=>e===f.fault);assert.deepEqual(f.trace,order.slice(0,10));assert.equal(f.constructions.length,1);assert.equal(f.calls.length,0);
  });
  await t.test("held body retains captured method receiver engine and early signal",async()=>{
    const f=fixture(),held=deferred();f.state.body=held.promise;const pending=f.invoke();await turns();assert.deepEqual(f.trace,order.slice(0,10));
    f.state.method=null;f.state.transfer=null;f.state.engine=null;f.state.signal=null;held.resolve(f.body);assert.equal(await pending,f.result);exact(f);construction(f);assert.equal(f.constructions.length,1);
  });
  await t.test("held body rejection does not invoke captured method",async()=>{
    const f=fixture(),held=deferred();f.state.body=held.promise;const pending=assert.rejects(f.invoke(),e=>e===f.fault);await turns();held.reject(f.fault);await pending;assert.equal(f.calls.length,0);assert.equal(f.constructions.length,1);
  });
  for(const value of [undefined,null,false,0,"",Symbol("PUBLIC-BODY")])await t.test(`resolved input ${String(value)} forwarded unchanged without property access`,async()=>{
    const f=fixture();f.state.body=value;await f.invoke();exact(f,f.actor,value);
  });
  await t.test("resolved input only then is inspected without bundle read or enumeration",async()=>{
    const f=fixture(),reads:PropertyKey[]=[];const body=new Proxy({}, {get(_t,key){reads.push(key);assert.equal(key,"then");return undefined;},ownKeys(){throw f.fault;}});f.state.body=body;await f.invoke();exact(f,f.actor,body);assert.deepEqual(reads,["then"]);
  });
  await t.test("body throwing then getter prevents import call",async()=>{
    const f=fixture();f.state.body={get then(){throw f.fault;}};await assert.rejects(f.invoke(),e=>e===f.fault);assert.equal(f.calls.length,0);
  });
  await t.test("body thenable adopts first resolved input identity",async()=>{
    const f=fixture();f.state.body={then(resolve:(x:unknown)=>void,reject:(x:unknown)=>void){resolve(f.body);reject(f.fault);resolve(null);}};await f.invoke();exact(f);
  });
  for(const value of [undefined,null,false,0,"",Symbol("PUBLIC-RESULT")])await t.test(`result ${String(value)} adopted unchanged`,async()=>{
    const f=fixture();f.state.result=value;assert.equal(await f.invoke(),value);exact(f);
  });
  await t.test("rejected import preserves exact refusal without retry",async()=>{
    const f=fixture();f.state.callFault=f.fault;f.state.rejectCall=true;await assert.rejects(f.invoke(),e=>e===f.fault);assert.equal(f.calls.length,1);
  });
  await t.test("held result blocks settlement with one import call",async()=>{
    const f=fixture(),held=deferred();f.state.result=held.promise;let settled=false;const pending=f.invoke().then(x=>{settled=true;return x;});await turns();assert.equal(settled,false);exact(f);held.resolve(f.result);assert.equal(await pending,f.result);assert.equal(f.calls.length,1);
  });
  await t.test("held result rejection preserves exact refusal",async()=>{
    const f=fixture(),held=deferred();f.state.result=held.promise;const pending=assert.rejects(f.invoke(),e=>e===f.fault);await turns();held.reject(f.fault);await pending;assert.equal(f.calls.length,1);
  });
  await t.test("result thenable adopts resolved identity without raw promise claim",async()=>{
    const f=fixture();f.state.result={then(resolve:(x:unknown)=>void,reject:(x:unknown)=>void){resolve(f.result);reject(f.fault);resolve(null);}};assert.equal(await f.invoke(),f.result);
  });
  await t.test("throwing result then getter preserves refusal",async()=>{
    const f=fixture();f.state.result={get then(){throw f.fault;}};await assert.rejects(f.invoke(),e=>e===f.fault);assert.equal(f.calls.length,1);
  });
  await t.test("fresh calls retain fresh registry actor request engine signal transfer and body",async()=>{
    const f=fixture();await f.invoke();const registry=opaque("registryB"),actor=opaque("actorB"),engine=opaque("engineB"),signal=opaque("signalB"),request={signal},body={public:"INPUT-B"},transfer={import:f.method};
    f.state.engine=engine;f.state.transfer=transfer;f.state.body=body;await f.invoke(registry,actor,request);construction(f,engine,signal);exact(f,actor,body,transfer);assert.equal(f.engines[1][0],registry);assert.equal(f.bodies[1][0],request);assert.equal(f.calls.length,2);
  });
  await t.test("interleaved bodies keep early captured transfers engines signals and per-call input",async()=>{
    const f=fixture(),a=deferred(),b=deferred(),registryB=opaque("registryB"),actorB=opaque("actorB"),engineB=opaque("engineB"),signalB=opaque("signalB"),requestB={signal:signalB},bodyB={public:"INPUT-B"},transferB={import:f.method};
    f.state.body=a.promise;const first=f.invoke();f.state.engine=engineB;f.state.transfer=transferB;f.state.body=b.promise;const second=f.invoke(registryB,actorB,requestB);await turns();assert.equal(f.constructions.length,2);assert.equal(f.calls.length,0);
    f.state.method=null;f.state.transfer=null;f.state.engine=null;b.resolve(bodyB);await second;exact(f,actorB,bodyB,transferB);a.resolve(f.body);await first;exact(f);
    assert.equal(f.constructions[0].args[0],f.engine);assert.equal(f.constructions[0].args[1],f.signal);assert.equal(f.constructions[1].args[0],engineB);assert.equal(f.constructions[1].args[1],signalB);assert.equal(f.engines[0][0],f.registry);assert.equal(f.engines[1][0],registryB);assert.equal(f.bodies[0][0],f.request);assert.equal(f.bodies[1][0],requestB);
  });
  await t.test("interleaved results settle independently with original arguments and receivers",async()=>{
    const f=fixture(),a=deferred(),b=deferred(),actorB=opaque("actorB"),bodyB={public:"INPUT-B"},resultB={public:"RESULT-B"},transferB={import:f.method};
    f.state.result=a.promise;const first=f.invoke();await turns();f.state.body=bodyB;f.state.transfer=transferB;f.state.result=b.promise;const second=f.invoke(f.registry,actorB);await turns();b.resolve(resultB);assert.equal(await second,resultB);a.resolve(f.result);assert.equal(await first,f.result);assert.equal(f.calls.length,2);
    assert.equal(f.calls[0].receiver,f.transfer);assert.equal(f.calls[0].args[0],f.actor);assert.equal(f.calls[0].args[1],f.body);assert.equal(f.calls[1].receiver,transferB);assert.equal(f.calls[1].args[0],actorB);assert.equal(f.calls[1].args[1],bodyB);
  });

  await t.test("throwing own bundle getter is never inspected",async()=>{
    const f=fixture(),body={get bundle(){throw f.fault;}};f.state.body=body;await f.invoke();exact(f,f.actor,body);
  });
  await t.test("throwing inherited bundle getter is never inspected",async()=>{
    const f=fixture(),body=Object.create({get bundle(){throw f.fault;}});f.state.body=body;await f.invoke();exact(f,f.actor,body);
  });
  await t.test("noncallable import refuses without reading bundle after body adoption",async()=>{
    const f=fixture();f.state.method=null;f.state.body={get bundle(){throw f.fault;}};await assert.rejects(f.invoke(),isError);assert.equal(f.calls.length,0);assert.deepEqual(f.trace,order.slice(0,10));
  });
  await t.test("held body retains whole resolved input and never reads bundle",async()=>{
    const f=fixture(),held=deferred(),body={get bundle(){throw f.fault;}};f.state.body=held.promise;const pending=f.invoke();await turns();assert.equal(f.calls.length,0);held.resolve(body);await pending;exact(f,f.actor,body);
  });
  await t.test("callable input is forwarded without invocation or bundle inspection",async()=>{
    const f=fixture(),body=()=>{throw f.fault;};Object.defineProperty(body,"bundle",{get(){throw f.fault;}});f.state.body=body;await f.invoke();exact(f,f.actor,body);
  });
  await t.test("input mutation during held adoption keeps the resolved object identity",async()=>{
    const f=fixture(),held=deferred(),body={public:"BEFORE"};f.state.body=held.promise;const pending=f.invoke();body.public="AFTER";held.resolve(body);await pending;exact(f,f.actor,body);assert.equal((f.calls[0].args[1] as Model).public,"AFTER");
  });
  const limits:[unknown,unknown][]=[[undefined,NaN],[null,65536],[false,65536],[true,65537],[0,65536],[-2,65534],[1.5,65537.5],[Infinity,Infinity],[NaN,NaN],["32","3265536"]];
  for(const [value,expected] of limits)await t.test(`exact addition for inert limit ${String(value)}`,async()=>{
    const f=fixture();f.state.bytes=value;await f.invoke();assert.equal(f.bodies[0][2],expected);exact(f);
  });
  for(const value of [1n,Symbol("PUBLIC-LIMIT")])await t.test(`incompatible arithmetic ${String(value)} prevents body delegation`,async()=>{
    const f=fixture();f.state.bytes=value;await assert.rejects(f.invoke(),isError);assert.deepEqual(f.trace,order.slice(0,9));assert.equal(f.bodies.length,0);assert.equal(f.calls.length,0);
  });
  await t.test("limit getter refusal wins over noncallable body",async()=>{
    const f=fixture();f.state.bodyFn=null;f.state.bytesFault=f.fault;await assert.rejects(f.invoke(),e=>e===f.fault);assert.deepEqual(f.trace,order.slice(0,9));
  });
  await t.test("limit primitive conversion runs once with default hint before body call",async()=>{
    const f=fixture();let reads=0;f.state.bytes={[Symbol.toPrimitive](hint:string){reads++;assert.equal(hint,"default");assert.deepEqual(f.trace,order.slice(0,9));return 9;}};await f.invoke();assert.equal(reads,1);assert.equal(f.bodies[0][2],65545);exact(f);
  });
  await t.test("limit arithmetic refusal preserves exact identity and prevents body",async()=>{
    const f=fixture();f.state.bytes={[Symbol.toPrimitive](){throw f.fault;}};await assert.rejects(f.invoke(),e=>e===f.fault);assert.equal(f.bodies.length,0);assert.equal(f.calls.length,0);
  });
  await t.test("schema getter selects limit after body function is captured",async()=>{
    const f=fixture();f.state.schemaHook=()=>{f.state.bodyFn=null;f.state.bytes=4;};await f.invoke();assert.equal(f.bodies[0][2],65540);exact(f);
  });
  await t.test("limit conversion effects cannot replace captured body receiver method or signal",async()=>{
    const f=fixture();f.state.bytes={[Symbol.toPrimitive](){f.state.bodyFn=null;f.state.method=null;f.state.transfer=null;f.state.signal=null;return 6;}};await f.invoke();assert.equal(f.bodies[0][2],65542);exact(f);construction(f);
  });
  await t.test("fresh calls capture fresh schema-independent limits",async()=>{
    const f=fixture();await f.invoke();f.state.bytes=7;await f.invoke();assert.equal(f.bodies[0][2],81920);assert.equal(f.bodies[1][2],65543);assert.equal(f.calls.length,2);
  });
});
