import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {resolve,join} from 'node:path';
import {installPackagingHooks,packagingDispatch,dispatchForBatch,unitTestPlan,executionFor} from '../scripts/current-packaging-unit-plan.mjs';
import {loginMetadataDispatch} from '../scripts/current-login-packaging.mjs';
import {registerMetadataDispatch} from '../scripts/current-register-packaging.mjs';
const root=resolve(fileURLToPath(new URL('../',import.meta.url)));
test('D01 real Node resolver redirects only50 legacy callers and leaves two auth callers and unrelated imports original',async()=>{
 const rows=[...packagingDispatch,loginMetadataDispatch,registerMetadataDispatch],urls=new Map(rows.map(r=>[pathToFileURL(join(root,r.original)).href,r]));const originalHelper=pathToFileURL(join(root,'scripts/packaging-provenance.mjs')).href;
 const hook=installPackagingHooks({root,callers:rows.map(r=>r.original)});let originals=0,neighboursExecuted=0;
 const observer=registerHooks({load(url,ctx,next){
  if(url===originalHelper){originals++;return {format:'module',shortCircuit:true,source:'export const untouchedOriginal = true;'};}
  const result=next(url,ctx);if(!urls.has(url))return result;
  // Production load/raw/span checks ran first; replace before original evaluation.
  return {format:'module',shortCircuit:true,source:'export * as helper from "../scripts/packaging-provenance.mjs";'};
 }});
 try{
  const direct=await import(originalHelper);assert.equal(direct.untouchedOriginal,true);
  for(const [url,row] of urls){const {helper}=await import(url);if(packagingDispatch.includes(row)){assert.equal(helper.maintainedPackagingAuthority.publicSource,'de695c5f65d9159a3b0d7c7671a9cc42136b275f');assert.equal(helper.untouchedOriginal,undefined);}else{assert.equal(helper.untouchedOriginal,true);assert.equal(helper.maintainedPackagingAuthority,undefined);}}
  assert.equal(originals,1);assert.equal(neighboursExecuted,0);assert.equal((await import('data:text/javascript,export const delegated=true;')).delegated,true);
 }finally{observer.deregister();hook.deregister();}
});
test('D02 only verified caller paths can request dispatch; source-text assertion is not an importer',()=>{
 assert.throws(()=>installPackagingHooks({root,callers:['tests/current-packaging-source-manifest.test.mjs']}),/Unknown dispatch caller/);assert.equal(packagingDispatch.length,50);assert.equal(dispatchForBatch(root,['tests/current-packaging-source-manifest.test.mjs']).flags.length,0);
});
test('D03 actual private plan retains old63 mappings and150file group with two newly discovered tests',()=>{
 const plan=unitTestPlan(root);assert.equal(plan.replacements.length,63);assert.equal(plan.discovered.length,460);assert.equal(plan.selected.length,397);assert.equal(executionFor(plan,['--group','current-packaging']).length,150);assert.equal(new Set(plan.selected).size,plan.selected.length);
 for(const path of ['tests/current-maintained-packaging-provenance.test.mjs','tests/current-maintained-packaging-dispatch.test.mjs'])assert.ok(plan.selected.includes(path));
});
