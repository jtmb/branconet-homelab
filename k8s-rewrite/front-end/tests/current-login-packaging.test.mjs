import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire,registerHooks} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {resolve,join} from 'node:path';
import {createHash} from 'node:crypto';
import {loginMetadataDispatch,readPublicSnapshot,projectLoginRegistrations,assertCurrentRunnerInverse,loginPackagingAuthority} from '../scripts/current-login-packaging.mjs';
import {dispatchForBatch,installPackagingHooks,packagingDispatch} from '../scripts/current-packaging-unit-plan.mjs';
const root=resolve(fileURLToPath(new URL('../',import.meta.url))),gitDir=process.env.BORTUS_PACKAGING_PUBLIC_GIT_DIR;
const source=readFileSync(join(root,loginMetadataDispatch.original)),sha=b=>createHash('sha256').update(b).digest('hex');
test('P01 two exact registration spans removed with whole raw inverse',()=>{
 const result=projectLoginRegistrations(source);let inverse=Buffer.from(result);
 for(const span of loginMetadataDispatch.spans){
  const marker=Buffer.from('/* '+span.label+' dispatched to '+loginMetadataDispatch.current+' */\n'),start=inverse.indexOf(marker);assert.ok(start>=0);assert.equal(inverse.indexOf(marker,start+1),-1);inverse=Buffer.concat([inverse.subarray(0,start),source.subarray(span.start,span.end),inverse.subarray(start+marker.length)]);
 }assert.deepEqual(inverse,source);assert.equal(sha(source),loginMetadataDispatch.sourceSHA256);
});
test('P02 all other14 original metadata statements and declarations retain exact AST text',()=>{
 const ts=createRequire(import.meta.url)(process.env.BORTUS_SOURCE_TYPESCRIPT),parse=b=>{const a=ts.createSourceFile('meta.mjs',b.toString(),ts.ScriptTarget.ES2022,true,ts.ScriptKind.JS);assert.equal(a.parseDiagnostics.length,0);return a;};
 const before=parse(source),after=parse(projectLoginRegistrations(source));const retained=before.statements.filter(n=>!loginMetadataDispatch.spans.some(s=>n.getStart(before)===s.start&&n.end<=s.end));assert.equal(before.statements.length-retained.length,2);assert.deepEqual(after.statements.map(n=>n.getText(after)),retained.map(n=>n.getText(before)));
 const registrations=after.statements.filter(n=>ts.isExpressionStatement(n)&&ts.isCallExpression(n.expression)&&n.expression.expression.getText(after)==='test');assert.equal(registrations.length,14);
});
test('P03 raw metadata mutations and string coercion refuse',()=>{
 assert.throws(()=>projectLoginRegistrations(source.toString()),/Raw Buffer/);for(const index of [0,7720,8194,source.length-1]){const b=Buffer.from(source);b[index]^=1;assert.throws(()=>projectLoginRegistrations(b),/metadata changed/);}
});
test('P04 PUBLIC authority absence unknown commits and inaccessible Git refuse',()=>{
 assert.throws(()=>readPublicSnapshot(undefined),/Explicit readonly/);assert.throws(()=>readPublicSnapshot(gitDir,'unknown'),/Unknown public/);assert.throws(()=>readPublicSnapshot('/missing-authority'),/PUBLIC Git/);
});
test('P05 runner mutation and unknown historical runner refuse without normalization',()=>{
 const current=readPublicSnapshot(gitDir),old=readPublicSnapshot(gitDir,loginPackagingAuthority.historicalCommit),runner='scripts/run-compatible-unit-tests.mjs';
 assert.throws(()=>assertCurrentRunnerInverse(Buffer.concat([current.read(runner),Buffer.from('\n')]),old.read(runner)),/Current runner changed/);assert.throws(()=>assertCurrentRunnerInverse(current.read(runner),Buffer.alloc(0)),/Historical runner changed/);
});
test('P06 new routing retains50 prior rows and targets only login metadata',()=>{
 assert.equal(packagingDispatch.length,50);const d=dispatchForBatch(root,[loginMetadataDispatch.original]);assert.deepEqual(JSON.parse(d.env.BORTUS_PACKAGING_DISPATCH).callers,[loginMetadataDispatch.original]);assert.equal(d.flags[0],'--import');
});
test('P07 real hook observes two replacements before inert module evaluation',async()=>{
 const target=pathToFileURL(join(root,loginMetadataDispatch.original)).href;const hook=installPackagingHooks({root,callers:[loginMetadataDispatch.original]});let observed=0;
 const observer=registerHooks({load(url,ctx,next){const r=next(url,ctx);if(url!==target)return r;assert.deepEqual(Buffer.from(r.source),projectLoginRegistrations(source));observed++;return {format:'module',shortCircuit:true,source:'export const observed = 2;'};}});
 try{assert.equal((await import(target)).observed,2);assert.equal(observed,1);}finally{observer.deregister();hook.deregister();}
});
