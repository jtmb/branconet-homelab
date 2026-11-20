import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { MetadataCache } from "../src/lib/metadata-cache";
import { AliasCatalog, ALIAS_FILE_BYTES, MAX_ALIASES, readAliasFile } from "../src/lib/alias-catalog";
import { probeSecretScopes } from "../src/lib/readiness";
import { SecretError } from "../src/lib/cluster-secrets";

const status = (expected: number) => (error: unknown) => error instanceof SecretError && error.status === expected;
const ref = (index: number) => ({ alias: "original_alias_" + String(index).padStart(5,"0"), namespace: "apps", name: "imported", key: "key_"+index });

test("alias catalog coalesces 603 mappings, indexes exact spelling, isolates callers and invalidates mutations", async()=>{
  let now=0,loads=0,rows=Array.from({length:603},(_,i)=>ref(i));
  const catalog=new AliasCatalog(async()=>{loads++;return [rows];},()=>now);
  const results=await Promise.all(Array.from({length:40},()=>catalog.resolve("file-a",ref(602).alias)));assert.equal(loads,1);assert(results.every(r=>r?.key==="key_602"));
  const listed=await catalog.list("file-a");listed[0].key="caller-change";assert.equal((await catalog.resolve("file-a",ref(0).alias))?.key,"key_0");
  rows=[...rows,ref(603)];assert.equal(await catalog.resolve("file-a",ref(603).alias),null);catalog.invalidate();assert.equal((await catalog.resolve("file-a",ref(603).alias))?.key,"key_603");assert.equal(loads,2);
  now=10001;await catalog.list("file-a");assert.equal(loads,3);await catalog.list("file-b");assert.equal(loads,4);
});
test("alias metadata rejects malformed/conflicting/over-limit sources and never serves an expired failed snapshot",async()=>{
  let now=0,fail=false,loads=0;
  const catalog=new AliasCatalog(async()=>{loads++;if(fail)throw new SecretError(503,"Metadata source unavailable");return [[ref(1)]];},()=>now);
  await catalog.list("");fail=true;now=10001;await assert.rejects(catalog.resolve("",ref(1).alias),status(503));await assert.rejects(catalog.list(""),status(503));assert.equal(loads,2);
  fail=false;now=12002;assert.equal((await catalog.list("")).length,1);assert.equal(loads,3);
  await assert.rejects(new AliasCatalog(async()=>[[ref(1),{...ref(1),key:"other"}]]).list(""),status(409));
  await assert.rejects(new AliasCatalog(async()=>[[null as any]]).list(""),status(503));
  await assert.rejects(new AliasCatalog(async()=>[Array.from({length:MAX_ALIASES+1},(_,i)=>ref(i))]).list(""),status(503));
  await assert.rejects(new AliasCatalog(async()=>[Array.from({length:6000},(_,i)=>ref(i)),Array.from({length:5000},(_,i)=>ref(i+6000))]).list(""),status(503));
});
test("metadata invalidation drops in-flight state and deadline workers retain their slot until settled",async()=>{
  let finish!:(value:number)=>void,loads=0,now=0;
  const cache=new MetadataCache(async()=>{loads++;if(loads===1)return new Promise<number>(resolve=>{finish=resolve;});return 2;},100,20,()=>now);
  const first=cache.get("key");await assert.rejects(first,status(503));assert.equal(loads,1);now=3000;
  await assert.rejects(cache.get("key"),status(503));assert.equal(loads,1);finish(1);await new Promise(resolve=>setImmediate(resolve));
  assert.equal(await cache.get("key"),2);assert.equal(loads,2);
  let complete!:(value:string)=>void;
  const raced=new MetadataCache(async()=>new Promise<string>(resolve=>{complete=resolve;}));const pending=raced.get("a");await Promise.resolve();raced.invalidate();complete("old");await assert.rejects(pending,status(503));
});
test("alias file reads enforce size, row count, fatal UTF-8 and named-field projection",async()=>{
  const dir=await mkdtemp(path.join(tmpdir(),"bortus-alias-bounds-")),file=path.join(dir,"aliases.json"),signal=new AbortController().signal;
  try {
    await writeFile(file,JSON.stringify([{...ref(1),privateValue:"synthetic other-key payload"}]));
    const catalog=new AliasCatalog(async()=>[await readAliasFile(file,signal)]);assert(!JSON.stringify(await catalog.list(file)).includes("synthetic other-key payload"));
    await writeFile(file,Buffer.from([0xff]));await assert.rejects(readAliasFile(file,signal),status(503));
    await writeFile(file,"x".repeat(ALIAS_FILE_BYTES+1));await assert.rejects(readAliasFile(file,signal),status(503));
    await writeFile(file,JSON.stringify(Array(MAX_ALIASES+1).fill({})));await assert.rejects(readAliasFile(file,signal),status(503));
    const abort=new AbortController();abort.abort();await assert.rejects(readAliasFile(file,abort.signal),status(503));
  }finally{await rm(dir,{recursive:true,force:true});}
});
test("readiness scope probing caps active workers at four and propagates a single whole-native deadline",async()=>{
  let active=0,maximum=0;const seen=new Set<string>(),deadline=Date.now()+1000;
  await probeSecretScopes(Array.from({length:18},(_,i)=>"ns-"+i),async(ns,received)=>{assert.equal(received,deadline);seen.add(ns);maximum=Math.max(maximum,++active);await new Promise(resolve=>setImmediate(resolve));active--;},deadline);
  assert.equal(maximum,4);assert.equal(active,0);assert.equal(seen.size,18);
  let calls=0;await assert.rejects(probeSecretScopes(["apps"],async()=>{calls++;},Date.now()-1),status(503));assert.equal(calls,0);
});
test("failed readiness stops further scopes and keeps outstanding probes attached until settled",async()=>{
  let finish!:()=>void, settled=false;const calls:string[]=[];
  const pending=probeSecretScopes(Array.from({length:18},(_,i)=>"ns-"+i),async ns=>{
    calls.push(ns);if(ns==="ns-0")throw new SecretError(503,"Scope unavailable");
    await new Promise<void>(resolve=>{if(ns==="ns-1")finish=resolve;else setImmediate(resolve);});
  }).finally(()=>{settled=true;});
  await new Promise(resolve=>setImmediate(resolve));assert.equal(settled,false);assert.equal(calls.length,4);
  finish();await assert.rejects(pending,status(503));assert.equal(calls.length,4);assert.equal(settled,true);
});
