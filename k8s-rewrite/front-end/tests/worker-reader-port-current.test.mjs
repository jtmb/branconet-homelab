import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createRequire,Module} from 'node:module';
import {fileURLToPath} from 'node:url';
import {Worker,SHARE_ENV} from 'node:worker_threads';
import {DatabaseSync} from 'node:sqlite';
import {spawnSync} from 'node:child_process';
import {createWorkerPortSourceReader,workerPortSourceAuthority} from '../scripts/current-worker-port-source.mjs';
const require=createRequire(import.meta.url),ts=require('typescript'),root=fileURLToPath(new URL('../',import.meta.url));
assert.equal(process.version,'v22.23.3');assert.equal(ts.version,'5.9.3');
const source=fs.readFileSync(path.join(root,'src/lib/worker-account-reader.ts'),'utf8');
const compiled=ts.transpileModule(source,{reportDiagnostics:true,compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,strict:true,esModuleInterop:true}});
assert.equal(compiled.diagnostics.length,0);assert.equal(compiled.outputText.split('require("./direct-account-core")').length,2);
const file=path.join(root,'runtime/worker-account-port-controls.cjs'),runtime=new Module(file);runtime.filename=file;runtime.paths=Module._nodeModulePaths(path.dirname(file));runtime._compile(compiled.outputText.replace('require("./direct-account-core")','require("./direct-account-core.cjs")'),file);
const {WorkerAccountReader}=runtime.exports;
const unavailable=/^Error: Account authorization unavailable$/;
const postProbe=`const{workerData,parentPort}=require('node:worker_threads');const port=workerData.settlementPort??parentPort,post=port.postMessage,latch=new Int32Array(workerData.latch);port.postMessage=function(message,...rest){const result=Reflect.apply(post,this,[message,...rest]);if(message?.kind==='settled'){Atomics.store(latch,0,message.id);Atomics.notify(latch,0);}return result;};`;

test('worker port exact raw cohorts retain historical authority and reject mixed/tampered bytes',()=>{
 const gitDir=process.env.BORTUS_PACKAGING_PUBLIC_GIT_DIR;assert.ok(gitDir,'Explicit readonly PUBLIC Git authority required');
 const entries=workerPortSourceAuthority.entries,old=new Map(),current=new Map();
 for(const entry of entries){const r=spawnSync('git',['-c','safe.directory='+gitDir,'--git-dir='+gitDir,'show',workerPortSourceAuthority.historicalPublicSource+':k8s-rewrite/front-end/'+entry.path],{maxBuffer:1024*1024,timeout:20000});assert.equal(r.status,0);old.set(entry.path,Buffer.from(r.stdout));current.set(entry.path,fs.readFileSync(path.join(root,entry.path)));}
 const importer=new URL('file:///worker-port-fixture/'),reader=map=>url=>{assert.ok(url.href.startsWith(importer.href));const name=decodeURIComponent(url.pathname.slice(importer.pathname.length));assert.ok(map.has(name));return Buffer.from(map.get(name));};
 for(const map of [old,current]){const wrapped=createWorkerPortSourceReader(reader(map));for(const entry of entries)assert.deepEqual(wrapped(new URL(entry.path,importer)),old.get(entry.path));}
 for(let mask=1;mask<7;mask++){const mixed=new Map(entries.map((entry,index)=>[entry.path,(mask&(1<<index)?current:old).get(entry.path)]));assert.throws(()=>createWorkerPortSourceReader(reader(mixed))(new URL(entries[0].path,importer)),/Unknown or mixed/);}
 for(const entry of entries){const changed=new Map(current);changed.set(entry.path,Buffer.concat([changed.get(entry.path),Buffer.from('\n')]));assert.throws(()=>createWorkerPortSourceReader(reader(changed))(new URL(entry.path,importer)),/Unknown or mixed/);}
 const changedRepresentation=new Map(current);changedRepresentation.set(entries[0].path,Buffer.from(changedRepresentation.get(entries[0].path).toString().replaceAll('\n','\r\n')));assert.throws(()=>createWorkerPortSourceReader(reader(changedRepresentation))(new URL(entries[0].path,importer)),/Unknown or mixed/);
 const stable=createWorkerPortSourceReader(reader(current)),first=stable(new URL(entries[0].path,importer));first[0]^=1;assert.deepEqual(stable(new URL(entries[0].path,importer)),old.get(entries[0].path));
 const changing=new Map(current),strict=createWorkerPortSourceReader(reader(changing));strict(new URL(entries[0].path,importer));changing.set(entries[1].path,old.get(entries[1].path));assert.throws(()=>strict(new URL(entries[1].path,importer)),/raw input changed/);
});

for(const kind of ['fresh','cancel','rotate'])test('worker port pending reply service preserves '+kind+' authority and actual settlement ownership',async()=>{
 const work=fs.mkdtempSync(path.join(os.tmpdir(),'bortus-worker-port-')),one=path.join(work,'one.db'),two=path.join(work,'two.db'),probe=path.join(work,'post-probe.cjs');fs.writeFileSync(probe,postProbe);const original=process.env.DATABASE_URL;
 const writer=new DatabaseSync(one),other=new DatabaseSync(two);for(const [db,version]of[[writer,0],[other,2]])db.exec(`CREATE TABLE users(id TEXT PRIMARY KEY,username TEXT,sessionVersion INTEGER,role TEXT,engineAdmin BOOLEAN);INSERT INTO users VALUES('public','public',${version},'write',1)`);
 process.env.DATABASE_URL='file:'+one;const latchBuffer=new SharedArrayBuffer(4),latch=new Int32Array(latchBuffer);const reader=new WorkerAccountReader(undefined,work,path.join(root,'runtime/direct-account-reader-worker.cjs'),(file,settlementPort)=>new Worker(file,{env:SHARE_ENV,workerData:{settlementPort,latch:latchBuffer},transferList:[settlementPort],execArgv:['--require',probe]}));const abort=new AbortController();const first=reader.readSession('public',abort.signal);first.catch(()=>{});let done=false;
 try{
  assert.notEqual(Atomics.wait(latch,0,0,2000),'timed-out','Actual worker post-return deadline');assert.equal(Atomics.load(latch,0),1);assert.equal(reader.activity().active,1);
  if(kind==='cancel')abort.abort();if(kind==='rotate')process.env.DATABASE_URL='file:'+two;else writer.exec("UPDATE users SET sessionVersion=1,role='readonly',engineAdmin=0");
  const second=reader.readAccount('public');assert.equal(reader.activity().active,1);assert.equal(reader.activity().queued,kind==='fresh'?0:1,'Ready settlement is serviced, but cancellation/config refusal retains ownership until actual discard acknowledgement');
  if(kind==='fresh')assert.deepEqual(await first,{id:'public',username:'public',sessionVersion:0});else await assert.rejects(first,unavailable);
  assert.deepEqual(await second,{id:'public',username:'public',sessionVersion:kind==='rotate'?2:1,role:kind==='rotate'?'write':'readonly',engineAdmin:kind==='rotate'});
  await reader.close();done=true;assert.deepEqual(reader.activity(),{active:0,queued:0,closing:false,closeFailed:false});assert.equal(reader.responsePort,undefined);assert.equal(reader.transferredPort,undefined);
 }finally{if(!done)await reader.close().catch(()=>{});writer.close();other.close();if(original===undefined)delete process.env.DATABASE_URL;else process.env.DATABASE_URL=original;}
});

test('worker port invalid pending reply poisons without yielding authority',async()=>{
 const work=fs.mkdtempSync(path.join(os.tmpdir(),'bortus-worker-port-bad-')),original=process.env.DATABASE_URL;process.env.DATABASE_URL='file:'+path.join(work,'unused.db');const buffer=new SharedArrayBuffer(4),view=new Int32Array(buffer);
 const reader=new WorkerAccountReader(undefined,work,path.join(root,'runtime/direct-account-reader-worker.cjs'),(_file,port)=>new Worker(`const{workerData}=require('node:worker_threads');workerData.port.postMessage({kind:'settled',id:999,refused:false,closeFailed:false,row:null});const view=new Int32Array(workerData.buffer);Atomics.store(view,0,1);Atomics.notify(view,0);`,{eval:true,workerData:{port,buffer},transferList:[port]}));const first=reader.readSession('public');first.catch(()=>{});
 try{assert.notEqual(Atomics.wait(view,0,0,2000),'timed-out');const next=reader.readSession('public');await assert.rejects(first,unavailable);await assert.rejects(next,unavailable);await assert.rejects(reader.close(),unavailable);assert.equal(reader.activity().closeFailed,true);assert.equal(reader.responsePort,undefined);assert.equal(reader.transferredPort,undefined);}
 finally{await reader.close().catch(()=>{});if(original===undefined)delete process.env.DATABASE_URL;else process.env.DATABASE_URL=original;}
});
