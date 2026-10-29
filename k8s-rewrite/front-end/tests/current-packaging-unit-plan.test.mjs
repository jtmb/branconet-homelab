import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,readdirSync} from 'node:fs';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';
import {unitTestPlan as previousPlan,executionFor as previousExecution} from '../scripts/auth-register-current-unit-plan.mjs';
import {packagingDispatch,withPackagingDispatch,unitTestPlan,executionFor,projectRegistration,assertPublicAuthority,artifactStages} from '../scripts/current-packaging-unit-plan.mjs';
const root=fileURLToPath(new URL('../',import.meta.url));
const ts=createRequire(import.meta.url)(process.env.BORTUS_SOURCE_TYPESCRIPT);
const parse=bytes=>{const ast=ts.createSourceFile('caller.mjs',bytes.toString(),ts.ScriptTarget.ES2022,true,ts.ScriptKind.JS);assert.equal(ast.parseDiagnostics.length,0);return ast;};
test('D01 prior selection and all63 functional mappings remain exact',()=>{
 const prior=previousPlan(root),plan=unitTestPlan(root);assert.deepEqual(plan.selected,prior.selected);assert.deepEqual(plan.replacements,prior.replacements);assert.equal(plan.replacements.length,63);assert.deepEqual(plan.terminalReplacements,prior.terminalReplacements);assert.equal(plan.packagingDispatch.length,50);
 for(const r of packagingDispatch)for(const p of [r.original,r.current,r.metadata])assert.equal(plan.selected.filter(n=>n===p).length,1);
});
test('D02 missing or duplicate caller/projection/metadata is refused',()=>{
 const prior=previousPlan(root);
 for(const r of packagingDispatch)for(const p of [r.original,r.current,r.metadata])assert.throws(()=>withPackagingDispatch({...prior,selected:prior.selected.filter(n=>n!==p)}),/Required packaging input/);
 assert.throws(()=>withPackagingDispatch({...prior,selected:[...prior.selected,prior.selected[0]]}),/Duplicate selected/);
});
test('D03 explicit packaging group preserves selected order and150 distinct files',()=>{
 const plan=unitTestPlan(root),group=executionFor(plan,['--group','current-packaging']);assert.equal(group.length,150);assert.equal(new Set(group).size,150);assert.deepEqual(group,plan.selected.filter(n=>group.includes(n)));
});
test('D04 existing functional group and argument errors survive delegation',()=>{
 const plan=unitTestPlan(root);
 for(const group of ['auth-register-current-source','aggregate-source-node22','legacy-route-copy'])assert.deepEqual(executionFor(plan,['--group',group]),previousExecution(plan,['--group',group]));
 assert.throws(()=>executionFor(plan,['--group','unknown-dispatch-group']));
});
test('D05 explicit complete PUBLIC Git authority required before planning',()=>{
 assert.throws(()=>assertPublicAuthority(undefined),/Explicit readonly/);assert.throws(()=>assertPublicAuthority('/not-a-git-authority'),/PUBLIC Git/);
 assert.equal(assertPublicAuthority(process.env.BORTUS_PACKAGING_PUBLIC_GIT_DIR).files,986);
});
test('D06 portable and native stage contracts retain original coverage',()=>{
 const plan=unitTestPlan(root),prior=previousPlan(root);assert.deepEqual(artifactStages(plan.selected),artifactStages(prior.selected));
});
test('D07 raw-only bridge rejects string input and unknown caller',()=>{
 assert.throws(()=>projectRegistration('',packagingDispatch[0]),/Raw Buffer/);assert.throws(()=>projectRegistration(Buffer.alloc(0),{...packagingDispatch[0]}),/Unknown packaging caller/);
 assert.equal(readdirSync(join(root,'tests')).includes('current-packaging-unit-plan.test.mjs'),true);
});
for(const row of packagingDispatch){
 test('D08 exact registration inverse and neighbour AST preservation '+row.original,()=>{
  const bytes=readFileSync(join(root,row.original)),copy=Buffer.from(bytes),output=projectRegistration(bytes,row),before=parse(bytes),after=parse(output);
  assert.deepEqual(bytes,copy);const replacement=Buffer.from('/* Packaging registration dispatched to '+row.current+'; neighbours retained. */');
  assert.deepEqual(output.subarray(0,row.start),bytes.subarray(0,row.start));assert.deepEqual(output.subarray(row.start+replacement.length),bytes.subarray(row.end));
  const remaining=before.statements.filter(n=>!(n.getStart(before)===row.start&&n.end<=row.end));
  assert.equal(remaining.length,before.statements.length-1);assert.deepEqual(after.statements.map(n=>n.getText(after)),remaining.map(n=>n.getText(before)));
  assert.deepEqual(Buffer.concat([output.subarray(0,row.start),bytes.subarray(row.start,row.end),output.subarray(row.start+replacement.length)]),bytes);
 });
 test('D09 raw tamper refusal '+row.original,()=>{
  const bytes=readFileSync(join(root,row.original)),changed=Buffer.from(bytes);changed[row.start]^=1;assert.throws(()=>projectRegistration(changed,row),/raw bytes changed/);
  assert.throws(()=>projectRegistration(Buffer.concat([bytes,Buffer.from('\n')]),row),/raw bytes changed/);
 });
}
