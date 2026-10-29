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
  for(const [url,row] of urls){const {helper}=await import(url);if(packagingDispatch.includes(row)){assert.equal(helper.maintainedPackagingAuthority.publicSource,'cb68d87e8c02fded34c3df2421a268d8db170e29');assert.equal(helper.untouchedOriginal,undefined);}else{assert.equal(helper.untouchedOriginal,true);assert.equal(helper.maintainedPackagingAuthority,undefined);}}
  assert.equal(originals,1);assert.equal(neighboursExecuted,0);assert.equal((await import('data:text/javascript,export const delegated=true;')).delegated,true);
 }finally{observer.deregister();hook.deregister();}
});
test('D02 only verified caller paths can request dispatch; source-text assertion is not an importer',()=>{
 assert.throws(()=>installPackagingHooks({root,callers:['tests/current-packaging-source-manifest.test.mjs']}),/Unknown dispatch caller/);assert.equal(packagingDispatch.length,50);assert.equal(dispatchForBatch(root,['tests/current-packaging-source-manifest.test.mjs']).flags.length,0);
});
export function assertMaintainedPlan(plan){
 const ordinary=['tests/scanner-database-update.test.ts','tests/system-report.test.ts'];
 const discovered=ordinary.filter(path=>plan.discovered.includes(path));
 assert.ok(discovered.length===0||discovered.length===2,'Complete known ordinary input pair required');
 assert.deepEqual(plan.selected.filter(path=>ordinary.includes(path)).sort(),discovered,'Ordinary inputs remain selected exactly once');
 assert.ok(plan.discovered.includes('tests/scanner-bundle.test.ts'),'Current scanner bundle input discovered');
 assert.equal(plan.selected.filter(path=>path==='tests/scanner-bundle.test.ts').length,1,'Current scanner bundle input selected exactly once');
 const [discoveredCount,selectedCount]=discovered.length===2?[463,400]:[461,398];
 assert.equal(plan.replacements.length,63);assert.equal(plan.discovered.length,discoveredCount);assert.equal(plan.selected.length,selectedCount);assert.equal(executionFor(plan,['--group','current-packaging']).length,150);assert.equal(new Set(plan.selected).size,plan.selected.length);
 for(const path of ['tests/current-maintained-packaging-provenance.test.mjs','tests/current-maintained-packaging-dispatch.test.mjs'])assert.ok(plan.selected.includes(path));
}
test('D03 actual private or complete public plan retains exact63 mappings and150file group',()=>{
 assertMaintainedPlan(unitTestPlan(root));
});

import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import {projectRegistration,projectDispatchedRegistration,preservedPublicAdditionBinding,projectPreservedPublicAdditions} from '../scripts/current-packaging-unit-plan.mjs';
const additionHash=b=>createHash('sha256').update(b).digest('hex');
test('D04 four PUBLIC expectation leaves preserve the complete frozen caller, all25 entries and every neighbouring assertion',()=>{
 const binding=preservedPublicAdditionBinding,row=packagingDispatch.find(r=>r.original===binding.original),bytes=readFileSync(join(root,row.original)),copy=Buffer.from(bytes);
 assert.ok(Object.isFrozen(binding));assert.ok(Object.isFrozen(binding.changes));assert.equal(binding.changes.length,4);
 assert.deepEqual(binding.changes.map(r=>r.path),['docs/SYSTEM-REPORT-QUALIFICATION.md','docs/SYSTEM-REPORT.md','scripts/provision-scanner.mjs','scripts/scanner-inputs.json']);
 assert.equal(binding.publicSource,'cb68d87e8c02fded34c3df2421a268d8db170e29');
 const functional=projectRegistration(bytes,row),output=projectDispatchedRegistration(bytes,row),offset=binding.start+functional.length-bytes.length,old=bytes.subarray(binding.start,binding.end),current=output.subarray(offset,offset+old.length);
 assert.deepEqual(bytes,copy);assert.equal(additionHash(bytes),binding.sourceSHA256);assert.equal(additionHash(old),binding.historicalMapSHA256);assert.equal(additionHash(current),binding.currentMapSHA256);
 assert.deepEqual(output.subarray(0,offset),functional.subarray(0,offset));assert.deepEqual(output.subarray(offset+old.length),functional.subarray(offset+old.length));
 const oldMap=JSON.parse(old.toString()),currentMap=JSON.parse(current.toString());assert.deepEqual(Object.keys(currentMap),Object.keys(oldMap));assert.equal(Object.keys(currentMap).length,25);
 let inverse=current.toString(),changed=0,unchanged=0;
 for(const name of Object.keys(oldMap)){
  const change=binding.changes.find(r=>r.path===name);
  if(!change){assert.equal(currentMap[name],oldMap[name]);unchanged++;continue;}
  assert.ok(Object.isFrozen(change));assert.equal(oldMap[name],change.historicalSHA256);assert.equal(currentMap[name],change.currentSHA256);changed++;
  const git=execFileSync('git',['--git-dir='+process.env.BORTUS_PACKAGING_PUBLIC_GIT_DIR,'show',binding.publicSource+':k8s-rewrite/front-end/'+name]);
  assert.equal(additionHash(git),change.currentSHA256);assert.deepEqual(readFileSync(join(root,name)),git);
  const before=JSON.stringify(name)+': '+JSON.stringify(change.currentSHA256),after=JSON.stringify(name)+': '+JSON.stringify(change.historicalSHA256);assert.equal(inverse.split(before).length,2);inverse=inverse.replace(before,after);
 }
 assert.equal(changed,4);assert.equal(unchanged,21);assert.deepEqual(Buffer.from(inverse),old);
 const restoredFunctional=Buffer.concat([output.subarray(0,offset),Buffer.from(inverse),output.subarray(offset+current.length)]);assert.deepEqual(restoredFunctional,functional);
 const replacement=Buffer.from('/* Packaging registration dispatched to '+row.current+'; neighbours retained. */');
 assert.deepEqual(Buffer.concat([restoredFunctional.subarray(0,row.start),bytes.subarray(row.start,row.end),restoredFunctional.subarray(row.start+replacement.length)]),bytes);
 const ts=createRequire(import.meta.url)(process.env.BORTUS_SOURCE_TYPESCRIPT),parse=b=>{const a=ts.createSourceFile('caller.mjs',b.toString(),ts.ScriptTarget.ES2022,true,ts.ScriptKind.JS);assert.equal(a.parseDiagnostics.length,0);return a;},before=parse(functional),after=parse(output);
 assert.equal(before.statements.length,after.statements.length);let changedStatements=0;
 for(let i=0;i<before.statements.length;i++){let text=after.statements[i].getText(after);for(const change of binding.changes)text=text.replace(JSON.stringify(change.path)+': '+JSON.stringify(change.currentSHA256),JSON.stringify(change.path)+': '+JSON.stringify(change.historicalSHA256));assert.equal(text,before.statements[i].getText(before));if(after.statements[i].getText(after)!==before.statements[i].getText(before)){changedStatements++;assert.ok(text.startsWith("test('M21 current lineage"));}}
 assert.equal(changedStatements,1);
});
test('D05 PUBLIC metadata projection refuses unknown caller and raw tampering inside or outside the exact map',()=>{
 const binding=preservedPublicAdditionBinding,row=packagingDispatch.find(r=>r.original===binding.original),bytes=readFileSync(join(root,row.original));
 for(const offset of [0,row.start,binding.start,binding.end,bytes.length-1]){const changed=Buffer.from(bytes);changed[offset]^=1;assert.throws(()=>projectPreservedPublicAdditions(changed,row),/raw bytes changed/);}
 assert.throws(()=>projectPreservedPublicAdditions(Buffer.concat([bytes,Buffer.from('\n')]),row),/raw bytes changed/);
 assert.throws(()=>projectPreservedPublicAdditions(bytes.toString(),row),/Raw Buffer/);assert.throws(()=>projectPreservedPublicAdditions(bytes,{...row}),/Unknown packaging caller/);
 assert.throws(()=>projectPreservedPublicAdditions(readFileSync(join(root,packagingDispatch[0].original)),packagingDispatch[0]),/Unknown PUBLIC addition caller/);
 assert.equal(additionHash(readFileSync(join(root,'scripts/packaging-provenance.mjs'))),'a09dccea1580a444fc0ab21fda02b9d049848421d8b0121b0e9cab16eb7fbf15');
});
