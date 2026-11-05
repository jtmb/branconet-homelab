import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync,readdirSync} from 'node:fs';
import {join} from 'node:path';
import {planFromInputs as previousPlan,executionFor as previousExecution,executionBatches} from './kv-policy-allows-unit-plan.mjs';
export {executionBatches};
export const portableFixture='tests/secret-flat-summary-node22.test.mjs';
export const qualifiedNativeSHA256='8dde4ce66cf7045bfa7d5c0c0fb8ad3ff3d98809fbe24b76487b520ea664f6c2';
export const compatibilityReplacements=Object.freeze([
 Object.freeze({original:'tests/kv-prefix-matches-source.test.ts',current:'tests/kv-prefix-matches-source-node22.test.mjs',sha256:'446015417745eb4bdf96f3220025679dee34d2c5aa79c1da7775164fb2a9232b',controls:39}),
 Object.freeze({original:'tests/pod-filter-source.test.ts',current:'tests/pod-filter-source-node22.test.mjs',sha256:'b4d89c2f914f1451580452fef494bdf5e781dd1ad55645e073869d7e432e3e4f',controls:76}),
]);
const digest=text=>createHash('sha256').update(text).digest('hex');
export function planFromInputs(names,read){
 const prior=previousPlan(names,read);
 for(const row of compatibilityReplacements){
  assert.ok(prior.discovered.includes(row.original),'Missing historical input: '+row.original);
  assert.ok(prior.discovered.includes(row.current),'Missing replacement: '+row.current);
  assert.equal(digest(read(row.original).replaceAll('\r\n','\n')),row.sha256,'Historical input changed: '+row.original);
 }
 const replacements=[...prior.replacements,...compatibilityReplacements];
 const mapped=new Map(compatibilityReplacements.map(r=>[r.original,r.current]));
 const selected=[...new Set(prior.selected.map(name=>mapped.get(name)??name))];
 assert.equal(selected.length,prior.selected.length-2);
 return {...prior,replacements,selected,retainedUnmapped:prior.discovered.filter(name=>!replacements.some(r=>r.original===name||r.current===name)),scope:'61 explicit projections; original fixtures and prior59 projections/58 planners/VM children preserved. Node22 qualification is separate from original Node24. Not a suite pass.'};
}
export function unitTestPlan(root){return planFromInputs(readdirSync(join(root,'tests')),name=>readFileSync(join(root,name),'utf8'));}
export function executionFor(plan,args){
 if(args.length===0)return plan.selected;
 if(args.length===2&&args[0]==='--group'){
  if(args[1]==='legacy-route-copy')return ['tests/kv-legacy-preview-route-source.test.ts','tests/kv-legacy-principal-patch-route-source.test.ts'];
  if(args[1]==='aggregate-source-node22')return compatibilityReplacements.map(r=>r.current);
 }
 return previousExecution(plan,args);
}
export function artifactStages(selected,batches=executionBatches(selected)){
 assert.equal(new Set(selected).size,selected.length,'duplicate selected file');
 assert.equal(selected.filter(f=>f===portableFixture).length,1,'portable fixture required exactly once');
 assert.deepEqual(batches.flatMap(b=>b.files),selected,'original batch coverage/order');
 const retained=batches.map(b=>({kind:'units',files:b.files.filter(f=>f!==portableFixture),flags:[...b.flags],requires:'native-pinned'})).filter(b=>b.files.length);
 const stages=[{kind:'portable',files:[portableFixture],flags:[],requires:'native-absent'},{kind:'prepare-native',files:[],flags:[],requires:'native-absent',command:['node','scripts/build-secret-flat-native.mjs']},...retained];
 assert.deepEqual(retained.flatMap(b=>b.files),selected.filter(f=>f!==portableFixture));
 assert.deepEqual(stages.flatMap(s=>s.files).sort(),[...selected].sort());return stages;
}
export function assertArtifactState(stage,state){
 if(stage.requires==='native-absent'){assert.equal(state.exists,false,'addon must genuinely be absent');return;}
 assert.equal(stage.requires,'native-pinned','unknown artifact phase');assert.equal(state.exists,true,'genuine addon required');
 assert.equal(state.regularFile,true,'native addon must be regular');assert.equal(state.sha256,qualifiedNativeSHA256,'native provenance mismatch');
}
