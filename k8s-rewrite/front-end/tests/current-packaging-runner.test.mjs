import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {resolve,join} from 'node:path';
import {registerHooks} from 'node:module';
import {dispatchForBatch,packagingDispatch,installPackagingHooks,unitTestPlan,projectRegistration} from '../scripts/current-packaging-unit-plan.mjs';
import {main,qualificationFingerprint,validatePortableProof} from '../scripts/run-compatible-unit-tests.mjs';
const root=fileURLToPath(new URL('../',import.meta.url));
test('R01 batch dispatch carries exact caller subset and clears inherited context otherwise',()=>{
 const files=[packagingDispatch[0].original,packagingDispatch[2].original],dispatch=dispatchForBatch(root,files);assert.equal(dispatch.flags[0],'--import');assert.match(dispatch.flags[1],/current-packaging-unit-plan.mjs$/);assert.deepEqual(JSON.parse(dispatch.env.BORTUS_PACKAGING_DISPATCH).callers,files);
 assert.deepEqual(dispatchForBatch(root,['tests/unrelated.test.mjs']),{flags:[],env:{BORTUS_PACKAGING_DISPATCH:''}});
});
test('R02 preload refuses invented or duplicate caller contexts',()=>{
 assert.throws(()=>installPackagingHooks({root:resolve(root),callers:['tests/invented.mjs']}),/Unknown dispatch caller/);
 assert.throws(()=>installPackagingHooks({root:resolve(root),callers:[packagingDispatch[0].original,packagingDispatch[0].original]}),/Duplicate dispatch caller/);
});
test('R03 actual runner plan entry uses new planner without executing tests',()=>{
 const original=console.log,lines=[];try{console.log=x=>lines.push(x);main(['--plan']);}finally{console.log=original;}
 assert.equal(lines.length,1);const result=JSON.parse(lines[0]);assert.equal(result.plan.packagingDispatch.length,50);assert.equal(result.stages[0].requires,'native-absent');assert.equal(result.plan.publicAuthority.files,986);
});
test('R04 changed dispatch is bound into real qualification fingerprint',()=>{
 const plan=unitTestPlan(root),before=qualificationFingerprint(root,plan);assert.notEqual(qualificationFingerprint(root,{...plan,packagingDispatch:[]}),before);assert.notEqual(qualificationFingerprint(root,{...plan,publicAuthority:{}}),before);
});
test('R05 original portable proof semantics still reject stale phase and source',()=>{
 const context={runId:'new-finite-only',sourceFingerprint:'current',node:'22.23.3',nodeSHA256:'runtime'},proof={schema:1,phase:'portable-passed',...context,portable:{tests:5,pass:5,fail:0,cancelled:0,skipped:0,todo:0}};
 validatePortableProof(proof,context);assert.throws(()=>validatePortableProof({...proof,phase:'complete'},context));assert.throws(()=>validatePortableProof({...proof,sourceFingerprint:'old'},context));
});
test('R06 runner actual child argv/env integrates preload and retains VM scheduling',()=>{
 const s=readFileSync(new URL('../scripts/run-compatible-unit-tests.mjs',import.meta.url),'utf8');assert.ok(s.includes("from './current-packaging-unit-plan.mjs'"));assert.ok(s.includes("'--import','tsx',...dispatch.flags,'--test',...scheduling,...batch.files"));assert.ok(s.includes('env:{...process.env,...dispatch.env}'));assert.ok(s.includes("['--test-concurrency=1']"));
 assert.equal(createHash('sha256').update(readFileSync(process.execPath)).digest('hex'),'fde6a4bf8d0562f7751d1a2d6cb9b417c4cfe107bbcb0aa3e9a24e125e348f48');
});

// Observe the real synchronous hook chain, then return an inert module before
// evaluation. No original module, callback or neighbour executes in this test.
test('R07 actual preload hook routes50 exact URLs and delegates unrelated modules',async()=>{
 const absoluteRoot=resolve(root),rows=new Map(packagingDispatch.map(r=>[pathToFileURL(join(absoluteRoot,r.original)).href,r]));
 const hook=installPackagingHooks({root:absoluteRoot,callers:packagingDispatch.map(r=>r.original)}),seen=[];
 const observer=registerHooks({load(url,context,nextLoad){
  const loaded=nextLoad(url,context),row=rows.get(url);if(!row)return loaded;
  assert.equal(loaded.format,'module');assert.equal(loaded.shortCircuit,true);
  assert.deepEqual(Buffer.from(loaded.source),projectRegistration(readFileSync(fileURLToPath(url)),row));seen.push(row.original);
  return {format:'module',shortCircuit:true,source:'export const observed = true;'};
 }});
 try{
  for(const url of rows.keys())assert.equal((await import(url)).observed,true);
  assert.deepEqual(seen,packagingDispatch.map(r=>r.original));
  assert.equal((await import('data:text/javascript,export const delegated = 17;')).delegated,17);
 }finally{observer.deregister();hook.deregister();}
});
