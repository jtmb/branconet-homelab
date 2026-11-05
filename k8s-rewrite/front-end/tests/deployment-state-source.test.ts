import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire, stripTypeScriptTypes } from "node:module";
import test from "node:test";
import vm from "node:vm";

// Finite PUBLIC SOURCE controls. Only this declaration executes; its real
// count helper, all neighbors, credentials and services remain inaccessible.
const require = createRequire(import.meta.url);
const ts = require(process.env.BORTUS_SOURCE_TYPESCRIPT || "typescript") as typeof import("typescript");
const source = readFileSync(new URL("../src/lib/deployment-state.ts", import.meta.url), "utf8");
const parsed = ts.createSourceFile("deployment-state.ts", source, ts.ScriptTarget.Latest, true);
const selected = parsed.statements.filter((node): node is import("typescript").FunctionDeclaration =>
  ts.isFunctionDeclaration(node) && node.name?.text === "deploymentState");
assert.equal(selected.length, 1);
assert.ok(selected[0].modifiers?.some(node => node.kind === ts.SyntaxKind.ExportKeyword));
assert.ok(selected[0].body);
assert.equal(selected[0].parameters.length, 1);
assert.equal(selected[0].parameters[0].name.getText(parsed), "deployment");
const declaration = selected[0].getText(parsed).replace(/^export\s+/, "");
const script = new vm.Script(`(${stripTypeScriptTypes(declaration)})`, { filename: "selected-deploymentState.js" });
type Row = Record<string, any>;
type Count = (value: unknown, fallback?: unknown) => unknown;
type Call = { value: unknown; args: unknown[]; receiver: unknown };
const baseValues = [3, 3, 3, 3, 3, 2, 2];
function fixture(): Row {
  return { metadata: { generation: 2 }, spec: { replicas: 3 }, status: {
    replicas: 3, readyReplicas: 3, updatedReplicas: 3, availableReplicas: 3, observedGeneration: 2, conditions: [],
  } };
}
function evaluate(input: unknown, values: unknown[] = baseValues, injected?: Count) {
  const calls: Call[] = [];
  const inert: Count = function (this: unknown, value: unknown) {
    const args = Array.from(arguments);
    calls.push({ value, args, receiver: this });
    return injected ? Reflect.apply(injected, undefined, args) : values[calls.length - 1];
  };
  const fn = script.runInNewContext({ count: inert }) as (deployment: unknown) => Row;
  return { result: { ...fn(input) }, calls };
}
function state(input: unknown, values: unknown[] = baseValues) { return evaluate(input, values).result; }
function trap(label: string, events: string[]) {
  const error = new Error(label);
  return { error, get() { events.push(label); throw error; } };
}
function throwsNamed(body: () => unknown, name: string) {
  assert.throws(body, (error: unknown) => (error as Error).name === name);
}

test("exact exported declaration and immutable numeric projection", () => {
  const input = fixture(); const before = JSON.stringify(input);
  const { result, calls } = evaluate(input);
  assert.deepEqual(result, { state: "Ready", health: "Healthy", desiredReplicas: 3, observedReplicas: 3,
    readyReplicas: 3, updatedReplicas: 3, availableReplicas: 3, generation: 2, observedGeneration: 2,
    ready: "3/3", upToDate: 3, available: 3 });
  assert.deepEqual(Object.keys(result), ["state", "health", "desiredReplicas", "observedReplicas", "readyReplicas",
    "updatedReplicas", "availableReplicas", "generation", "observedGeneration", "ready", "upToDate", "available"]);
  assert.deepEqual(calls.map(c => c.args), [[3, 1], [3], [3], [3], [3], [2], [2]]);
  assert.ok(calls.every(c => c.receiver === undefined));
  assert.equal(JSON.stringify(input), before);
});

const cases: { name: string; values?: unknown[]; alter?: (d: Row) => void; state: string; health: string }[] = [
  { name: "ready", state: "Ready", health: "Healthy" },
  { name: "deleting wins failure paused and lag", alter: d => { d.metadata.deletionTimestamp = "public"; d.spec.paused = true; d.status.conditions = [{ type: "ReplicaFailure", status: "True" }]; }, values: [3, 1, 1, 1, 1, 9, 1], state: "Deleting", health: "Degraded" },
  { name: "deleting without failure", alter: d => { d.metadata.deletionTimestamp = "public"; }, state: "Deleting", health: "Progressing" },
  { name: "failure wins paused", alter: d => { d.spec.paused = true; d.status.conditions = [{ type: "ReplicaFailure", status: "True" }]; }, state: "Failed", health: "Degraded" },
  { name: "paused wins generation lag", alter: d => { d.spec.paused = true; }, values: [3, 3, 3, 3, 3, 3, 2], state: "Paused", health: "Progressing" },
  { name: "generation lag wins replica readiness", values: [3, 3, 3, 3, 3, 3, 2], state: "Reconciling", health: "Progressing" },
  { name: "generation ahead permits ready", values: [3, 3, 3, 3, 3, 2, 3], state: "Ready", health: "Healthy" },
  { name: "all strict zeros scaled down", values: [0, 0, 0, 0, 0, 2, 2], state: "Scaled down", health: "Healthy" },
  { name: "negative zeros remain strict zero", values: [-0, -0, -0, -0, -0, 2, 2], state: "Scaled down", health: "Healthy" },
  { name: "nonzero observed scales down", values: [0, 1, 0, 0, 0, 2, 2], state: "Scaling down", health: "Progressing" },
  { name: "nonzero ready scales down", values: [0, 0, 1, 0, 0, 2, 2], state: "Scaling down", health: "Progressing" },
  { name: "nonzero updated scales down", values: [0, 0, 0, 1, 0, 2, 2], state: "Scaling down", health: "Progressing" },
  { name: "nonzero available scales down", values: [0, 0, 0, 0, 1, 2, 2], state: "Scaling down", health: "Progressing" },
  { name: "updated below desired", values: [3, 3, 2, 2, 2, 2, 2], state: "Updating", health: "Progressing" },
  { name: "only observed short", values: [3, 2, 3, 3, 3, 2, 2], state: "Progressing", health: "Progressing" },
  { name: "only ready short", values: [3, 3, 2, 3, 3, 2, 2], state: "Progressing", health: "Progressing" },
  { name: "only available short", values: [3, 3, 3, 3, 2, 2, 2], state: "Progressing", health: "Progressing" },
  { name: "updated above desired", values: [3, 3, 3, 4, 3, 2, 2], state: "Progressing", health: "Progressing" },
];
for (const c of cases) test(`state priority: ${c.name}`, () => {
  const d = fixture(); c.alter?.(d);const r = state(d, c.values || baseValues);
  assert.equal(r.state, c.state);assert.equal(r.health, c.health);
});

const conditions: { name: string; rows: unknown[]; state: string }[] = [
  { name: "replica true", rows: [{ type: "ReplicaFailure", status: "True" }], state: "Failed" },
  { name: "replica false", rows: [{ type: "ReplicaFailure", status: "False" }], state: "Ready" },
  { name: "replica boolean is not string", rows: [{ type: "ReplicaFailure", status: true }], state: "Ready" },
  { name: "progress deadline", rows: [{ type: "Progressing", status: "False", reason: "ProgressDeadlineExceeded" }], state: "Failed" },
  { name: "progress true", rows: [{ type: "Progressing", status: "True", reason: "ProgressDeadlineExceeded" }], state: "Ready" },
  { name: "progress other reason", rows: [{ type: "Progressing", status: "False", reason: "Other" }], state: "Ready" },
  { name: "available false is not failure", rows: [{ type: "Available", status: "False" }], state: "Ready" },
  { name: "missing type", rows: [{}], state: "Ready" },
  { name: "case sensitive", rows: [{ type: "replicafailure", status: "True" }], state: "Ready" },
  { name: "failure after unrelated", rows: [{ type: "Unknown" }, { type: "ReplicaFailure", status: "True" }], state: "Failed" },
];
for (const c of conditions) test(`conditions: ${c.name}`, () => {
  const d = fixture();d.status.conditions = c.rows;assert.equal(state(d).state, c.state);
});

for (const value of [undefined, null, false, 0, "", NaN]) test(`falsy conditions default: ${String(value)}`, () => {
  const d = fixture();d.status.conditions = value;assert.equal(state(d).state, "Ready");
});
for (const value of [{}, true, 1, "x", { some: null }]) test(`truthy malformed some: ${JSON.stringify(value)}`, () => {
  const d = fixture();d.status.conditions = value;throwsNamed(() => state(d), "TypeError");
});
for (const value of [null, undefined]) test(`nullish deployment refuses: ${String(value)}`, () => throwsNamed(() => state(value), "TypeError"));
for (const field of ["spec", "status", "metadata"]) test(`optional null ${field} delegates undefined to inert count`, () => {
  const d = fixture();d[field] = null;const r = evaluate(d);
  const indexes = field === "spec" ? [0] : field === "metadata" ? [5] : [1, 2, 3, 4, 6];
  for (const i of indexes) assert.equal(r.calls[i].value, undefined);
  assert.equal(r.result.state, "Ready");
});

test("fresh section reads and count calls retain complete source order", () => {
  const events: string[] = [];
  const part = (label: string, values: Row) => new Proxy(values, { get(o,k,r) { events.push(`${label}.${String(k)}`);return Reflect.get(o,k,r); } });
  const d = new Proxy(fixture(), { get(o,k,r) {events.push(String(k));return part(String(k), Reflect.get(o,k,r));} });
  let n = 0;const r = evaluate(d, baseValues, function (value, fallback) {events.push(`count${++n}:${String(value)}:${String(fallback)}`);return baseValues[n - 1];});
  assert.equal(r.result.state, "Ready");
  assert.deepEqual(events, ["spec","spec.replicas","count1:3:1","status","status.replicas","count2:3:undefined",
    "status","status.readyReplicas","count3:3:undefined","status","status.updatedReplicas","count4:3:undefined",
    "status","status.availableReplicas","count5:3:undefined","metadata","metadata.generation","count6:2:undefined",
    "status","status.observedGeneration","count7:2:undefined","status","status.conditions","metadata","metadata.deletionTimestamp","spec","spec.paused"]);
});

for (let index = 0; index < 7; index++) test(`count fault ${index + 1} stops later reads and calls`, () => {
  let n = 0;const error = new Error(`count${index}`);const d = fixture();
  Object.defineProperty(d.status, "conditions", { get() { assert.fail("later conditions read"); } });
  assert.throws(() => evaluate(d, baseValues, () => { if (n++ === index) throw error;return 3; }), e => e === error);
  assert.equal(n, index + 1);
});

test("some uses original receiver and one callback, before state branch reads", () => {
  const d = fixture();const events: string[] = [];const list = { some(callback: (row: Row) => boolean) {
    assert.equal(this, list);events.push("some");assert.equal(arguments.length, 1);
    assert.equal(callback({ type: "Unknown" }), false);assert.equal(callback({ type: "ReplicaFailure", status: "True" }), true);return true;
  } };
  d.status.conditions = list;Object.defineProperty(d.metadata,"deletionTimestamp",{ get() { events.push("deletion");return true; } });
  assert.equal(state(d).health,"Degraded");assert.deepEqual(events,["some","deletion"]);
});
test("real Array.some short circuits before later poison", () => {
  const d=fixture();const rows=[{ type:"ReplicaFailure",status:"True" }];Object.defineProperty(rows,1,{get(){assert.fail("later entry");},enumerable:true});rows.length=2;
  d.status.conditions=rows;assert.equal(state(d).state,"Failed");
});
test("Array.some skips holes and observes inherited entries", () => {
  const d=fixture();const rows=new Array(2);const proto=Object.create(Array.prototype);proto[1]={type:"ReplicaFailure",status:"True"};Object.setPrototypeOf(rows,proto);
  d.status.conditions=rows;assert.equal(state(d).state,"Failed");
});
test("callback type is freshly read on the second alternative", () => {
  const d=fixture();const events:string[]=[];let n=0;const row={get type(){events.push("type");return ++n===1?"Other":"Progressing";},get status(){events.push("status");return "False";},get reason(){events.push("reason");return "ProgressDeadlineExceeded";}};
  d.status.conditions=[row];assert.equal(state(d).state,"Failed");assert.deepEqual(events,["type","type","status","reason"]);
});
test("matching replica condition never reads type twice or reason", () => {
  const d=fixture();const events:string[]=[];d.status.conditions=[{get type(){events.push("type");return "ReplicaFailure";},get status(){events.push("status");return "True";},get reason(){return assert.fail("reason");}}];
  assert.equal(state(d).state,"Failed");assert.deepEqual(events,["type","status"]);
});
test("failed replica status proceeds to fresh type without reading reason", () => {
  const d=fixture();const events:string[]=[];d.status.conditions=[{get type(){events.push("type");return "ReplicaFailure";},get status(){events.push("status");return "False";},get reason(){return assert.fail("reason");}}];
  assert.equal(state(d).state,"Ready");assert.deepEqual(events,["type","status","type"]);
});
for (const slot of ["type", "status", "reason"]) test(`condition ${slot} fault remains original`, () => {
  const d=fixture();const events:string[]=[];const t=trap(slot,events);const row:Row={type:"Progressing",status:"False",reason:"ProgressDeadlineExceeded"};Object.defineProperty(row,slot,{get:t.get});d.status.conditions=[row];
  assert.throws(()=>state(d),e=>e===t.error);assert.deepEqual(events,[slot]);
});
test("null condition fails before deletion even when deleting", () => {
  const d=fixture();d.status.conditions=[null];Object.defineProperty(d.metadata,"deletionTimestamp",{get(){assert.fail("deletion after condition fault");}});throwsNamed(()=>state(d),"TypeError");
});
test("some getter failure precedes deletion and pause", () => {
  const d=fixture();const events:string[]=[];const t=trap("some",events);d.status.conditions=Object.defineProperty({},"some",{get:t.get});Object.defineProperty(d.metadata,"deletionTimestamp",{get(){assert.fail("deletion");}});
  assert.throws(()=>state(d),e=>e===t.error);assert.deepEqual(events,["some"]);
});
test("some method failure propagates unchanged", () => {
  const d=fixture();const error=new Error("some public fault");d.status.conditions={some(){throw error;}};assert.throws(()=>state(d),e=>e===error);
});
test("captured replica values survive later condition mutation", () => {
  const d=fixture();d.status.conditions={some(){d.status.readyReplicas=99;d.spec.replicas=99;return false;}};
  const r=state(d);assert.equal(r.ready,"3/3");assert.equal(r.readyReplicas,3);assert.equal(r.state,"Ready");
});
test("later metadata and paused reads observe condition mutation", () => {
  const d=fixture();d.status.conditions={some(){d.metadata={deletionTimestamp:"public"};d.spec={paused:true};return false;}};assert.equal(state(d).state,"Deleting");
});
for(const value of [false,0,"",null,undefined]) test(`falsy deletion permits pause: ${String(value)}`,()=>{
  const d=fixture();d.metadata.deletionTimestamp=value;d.spec.paused=true;assert.equal(state(d).state,"Paused");
});
test("deletion short circuits poisoned paused field",()=>{
  const d=fixture();d.metadata.deletionTimestamp=true;Object.defineProperty(d.spec,"paused",{get(){assert.fail("paused");}});assert.equal(state(d).state,"Deleting");
});
test("failure short circuits poisoned paused field",()=>{
  const d=fixture();d.status.conditions=[{type:"ReplicaFailure",status:"True"}];Object.defineProperty(d.spec,"paused",{get(){assert.fail("paused");}});assert.equal(state(d).state,"Failed");
});
test("generation comparison uses captured observed before generation",()=>{
  const d=fixture();const events:string[]=[];const observed={valueOf(){events.push("observed");return 1;}};const generation={valueOf(){events.push("generation");return 2;}};
  const r=state(d,[3,3,3,3,3,generation,observed]);assert.equal(r.state,"Reconciling");assert.deepEqual(events,["observed","generation"]);
});
test("generation coercion failure precedes ready formatting",()=>{
  const d=fixture();const error=new Error("generation public fault");const v={valueOf(){throw error;}};assert.throws(()=>state(d,[3,3,3,3,3,v,1]),e=>e===error);
});
test("deletion bypasses generation coercion while preserving count calls",()=>{
  const d=fixture();d.metadata.deletionTimestamp=true;const v={valueOf(){assert.fail("generation coercion");}};const r=evaluate(d,[3,3,3,3,3,v,v]);assert.equal(r.calls.length,7);assert.equal(r.result.state,"Deleting");
});
test("ready template converts captured ready then desired after state selection",()=>{
  const d=fixture();d.spec.paused=true;const events:string[]=[];const desired={toString(){events.push("desired");return "D";}};const ready={toString(){events.push("ready");return "R";}};
  const r=state(d,[desired,3,ready,3,3,2,2]);assert.equal(r.ready,"R/D");assert.equal(r.state,"Paused");assert.deepEqual(events,["ready","desired"]);assert.equal(r.desiredReplicas,desired);assert.equal(r.readyReplicas,ready);
});
test("ready template coercion error is not caught",()=>{
  const d=fixture();d.spec.paused=true;const error=new Error("public template fault");const ready={toString(){throw error;}};assert.throws(()=>state(d,[3,3,ready,3,3,2,2]),e=>e===error);
});
test("strict zero comparison does not accept string zeros from inert count",()=>{
  const d=fixture();assert.equal(state(d,[0,"0",0,0,0,2,2]).state,"Scaling down");assert.equal(state(d,["0",0,0,0,0,2,2]).state,"Progressing");
});
test("shared nonnumeric captured values remain strict-equal Ready",()=>{
  const d=fixture();assert.equal(state(d,["3","3","3","3","3",2,2]).state,"Ready");
});
test("NaN count output cannot pass strict readiness",()=>assert.equal(state(fixture(),[NaN,NaN,NaN,NaN,NaN,2,2]).state,"Progressing"));
test("inherited Deployment metadata is read without own-property restriction",()=>{
  const d=Object.create(fixture());assert.equal(state(d).state,"Ready");
});
test("missing sections pass undefined arguments without invoking real count",()=>{
  const {result,calls}=evaluate({});assert.ok(calls.every(c=>c.value===undefined));assert.equal(result.state,"Ready");assert.deepEqual(calls[0].args,[undefined,1]);
});

for (const [section,field,priorCalls] of [["spec","replicas",0],["status","replicas",1],["status","readyReplicas",2],
  ["status","updatedReplicas",3],["status","availableReplicas",4],["metadata","generation",5],["status","observedGeneration",6],
  ["status","conditions",7],["metadata","deletionTimestamp",7],["spec","paused",7]] as const) test(`ordered field fault: ${section}.${field}`,()=>{
  const d=fixture();let calls=0;const error=new Error(`public ${section}.${field}`);Object.defineProperty(d[section],field,{get(){throw error;}});
  assert.throws(()=>evaluate(d,baseValues,()=>baseValues[calls++]),e=>e===error);assert.equal(calls,priorCalls);
});
test("fresh status root can disappear after first count without reusing old root",()=>{
  const d=fixture();let reads=0;const original=d.status;Object.defineProperty(d,"status",{get(){return ++reads===1?original:null;}});
  const r=evaluate(d);assert.equal(reads,6);assert.deepEqual(r.calls.map(c=>c.value),[3,3,undefined,undefined,undefined,2,undefined]);assert.equal(r.result.state,"Ready");
});
test("deletion uses fresh metadata after captured generation",()=>{
  const d=fixture();let reads=0;Object.defineProperty(d,"metadata",{get(){return ++reads===1?{generation:2}:{deletionTimestamp:true};}});
  const r=evaluate(d);assert.equal(reads,2);assert.equal(r.calls[5].value,2);assert.equal(r.result.state,"Deleting");
});
test("paused uses fresh spec after captured desired",()=>{
  const d=fixture();let reads=0;Object.defineProperty(d,"spec",{get(){return ++reads===1?{replicas:3}:{paused:true};}});
  const r=evaluate(d);assert.equal(reads,2);assert.equal(r.result.state,"Paused");assert.equal(r.result.desiredReplicas,3);
});
for(const value of [true,"public",{},1]) test(`truthy custom some controls failed health: ${typeof value}`,()=>{
  const d=fixture();d.status.conditions={some(){return value;}};assert.equal(state(d).state,"Failed");assert.equal(state(d).health,"Degraded");
});
test("typed symbol from inert count fails only during relational comparison",()=>{
  throwsNamed(()=>state(fixture(),[3,3,3,3,3,Symbol("public"),2]),"TypeError");
});
